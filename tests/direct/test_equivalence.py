"""Consensus: the validator against forged leaders.

Two layers. The captured round (a spy wrapped around gl.vm.run_nondet) hands
the REAL validator closure a forged leader result while the mocks describe
the validator's own world, so a leader result can be well-formed and still
be vetoed when the validator's reproduction disagrees. The pure decision
function (_validator_decision, _parse_payload, _vote_on_leader_error) is
driven directly to prove the structural gate refuses before reproduction
and that every error row of the result table behaves."""

import json

import pytest

from tests.direct.conftest import STATE, STRANGER
from tests.direct.support import (
    AGREEMENT, DATASET_SHORT, METHODOLOGY, RAW, SEMANTIC_SATISFIED, as_, dead,
    evidence, page, panel_says, requirements, serve_package, submitted,
)


@pytest.fixture
def captured(module):
    """Wrap gl.vm.run_nondet so the leader and validator closures of the
    last round are kept for replay."""
    real = module.gl.vm.run_nondet
    holder = {}

    def spy(leader_fn, validator_fn):
        holder["leader_fn"] = leader_fn
        holder["validator_fn"] = validator_fn
        return real(leader_fn, validator_fn)
    module.gl.vm.run_nondet = spy
    yield holder
    module.gl.vm.run_nondet = real


def honest_round(module, c):
    """Fund, commit and adjudicate the canonical qualifying package."""
    submitted(module, c)
    serve_package()
    panel_says(SEMANTIC_SATISFIED)
    as_(module, STRANGER, 0)
    c.adjudicate(AGREEMENT)


def frozen_inputs(c):
    pkg = evidence(c)
    reqs = requirements(c)["requirements"]
    return pkg, reqs


def reassemble(module, c, payload, requirement_rows=None, source_rows=None,
               contradiction=None, injection=None, deadline_met=None):
    """Rebuild a structurally consistent payload from altered rows: the only
    way past the structural gate is a payload whose code-derived parts
    recompute. Deterministic findings are recomputed from the source rows
    (COLUMNS_REQUIRED keeps the given finding while its dataset is
    examined, since column names are not carried in the rows)."""
    source_rows = json.loads(json.dumps(source_rows if source_rows is not None else payload["sources"]))
    requirement_rows = json.loads(json.dumps(
        requirement_rows if requirement_rows is not None else payload["requirements"]))
    met = payload["deadline_met"] if deadline_met is None else deadline_met
    reqs = requirements(c)["requirements"]
    for req, row in zip(reqs, requirement_rows):
        if req["kind"] == "COLUMNS_REQUIRED":
            src = module._source_row_for(source_rows, req["source_id"])
            if src is None or src["status"] != "EXAMINED":
                row["finding"] = "UNVERIFIABLE"
        elif req["kind"] != "SEMANTIC":
            row["finding"] = module._deterministic_finding(req, source_rows, {}, met)
    return module._assemble_payload(
        payload["agreement_id"], payload["version"], payload["evidence_hash"], met,
        requirement_rows, source_rows,
        payload["contradiction_suspected"] if contradiction is None else contradiction,
        payload["injection_suspected"] if injection is None else injection)


def with_requirement(payload, rid, **fields):
    rows = json.loads(json.dumps(payload["requirements"]))
    for r in rows:
        if r["requirement_id"] == rid:
            r.update(fields)
    return rows


def with_source(payload, sid, **fields):
    rows = json.loads(json.dumps(payload["sources"]))
    for s in rows:
        if s["source_id"] == sid:
            s.update(fields)
    return rows


def rederived(module, payload, rows, sources=None):
    """A payload whose verdict, counts, reason codes and summary are honestly
    re-derived for altered requirement rows - so ONLY the gate's own
    recomputation of a deterministic finding can refuse it."""
    sources = sources if sources is not None else payload["sources"]
    findings = [r["finding"] for r in rows]
    verdict = module._derive_verdict(payload["deadline_met"], findings)
    examined = sum(1 for s in sources if s["status"] == "EXAMINED")
    out = json.loads(json.dumps(payload))
    out.update({
        "requirements": rows, "sources": sources, "verdict": verdict,
        "requirements_met": sum(1 for f in findings if f == "SATISFIED"),
        "evidence_sufficient": examined == len(sources) and "UNVERIFIABLE" not in findings,
        "reason_codes": module._derive_reason_codes(
            payload["deadline_met"], rows, sources, payload["contradiction_suspected"],
            payload["injection_suspected"]),
        "summary": module._compose_summary(verdict, payload["version"], examined,
                                           len(sources), payload["deadline_met"], rows),
    })
    return out


# -- the captured closure: real validator, real reproduction ----------------------

def test_validator_ratifies_an_agreeing_reproduction(module, c, captured):
    honest_round(module, c)
    honest = captured["leader_fn"]()
    assert captured["validator_fn"](STATE.Return(honest)) is True


def test_validator_vetoes_a_false_not_qualified(module, c, captured):
    """A well-formed leader result reporting M4 NOT_SATISFIED while the
    validator's own synthesis says SATISFIED: veto."""
    honest_round(module, c)
    honest = json.loads(captured["leader_fn"]())
    forged = reassemble(module, c, honest, requirement_rows=with_requirement(
        honest, "M4", finding="NOT_SATISFIED"))
    assert forged["verdict"] == "NOT_QUALIFIED"
    assert captured["validator_fn"](STATE.Return(module._canonical(forged))) is False


def test_validator_vetoes_a_false_qualified(module, c, captured):
    """The leader's honest-looking QUALIFIED result against a validator whose
    own synthesis finds M4 NOT_SATISFIED: veto."""
    honest_round(module, c)
    honest = captured["leader_fn"]()
    panel_says(dict(SEMANTIC_SATISFIED, M4={"finding": "NOT_SATISFIED", "contradiction": False,
                                            "injection": False, "note": "no counts"}))
    assert captured["validator_fn"](STATE.Return(honest)) is False


def test_validator_vetoes_a_source_it_cannot_reproduce(module, c, captured):
    """The leader examined every source; the validator cannot fetch the
    dataset: its source status and deterministic findings differ, veto
    (never ratify what you could not see)."""
    honest_round(module, c)
    honest = captured["leader_fn"]()
    dead("dataset/observations.csv")
    assert captured["validator_fn"](STATE.Return(honest)) is False


def test_validator_vetoes_when_its_dataset_bytes_differ(module, c, captured):
    """The validator is served a different dataset: the hash mismatches, the
    dataset is excluded, M1/M2/M5 differ from the leader's rows: veto."""
    honest_round(module, c)
    honest = captured["leader_fn"]()
    page(RAW + "dataset/observations.csv", DATASET_SHORT)
    assert captured["validator_fn"](STATE.Return(honest)) is False


def test_validator_vetoes_when_its_document_bytes_differ(module, c, captured):
    honest_round(module, c)
    honest = captured["leader_fn"]()
    page(RAW + "methodology.md", METHODOLOGY + "\n")
    assert captured["validator_fn"](STATE.Return(honest)) is False


def test_validator_vetoes_a_forged_record_count(module, c, captured):
    """A leader claiming 9,000 records with an honestly re-derived
    NOT_QUALIFIED passes the structural gate (the gate cannot count bytes)
    and is vetoed by the validator's own count."""
    honest_round(module, c)
    honest = json.loads(captured["leader_fn"]())
    forged = reassemble(module, c, honest, source_rows=with_source(honest, "dataset", row_count=9000))
    assert forged["verdict"] == "NOT_QUALIFIED"
    assert forged["requirements"][0]["finding"] == "NOT_SATISFIED"
    pkg, reqs = frozen_inputs(c)
    assert module._parse_payload(module._canonical(forged), AGREEMENT, 1, pkg["evidence_hash"],
                                 True, reqs, pkg["sources"]) is not None
    assert captured["validator_fn"](STATE.Return(module._canonical(forged))) is False


def test_validator_vetoes_a_forged_column_finding(module, c, captured):
    """M2 NOT_SATISFIED with a re-derived verdict passes the gate (column
    names are not in the rows) and is vetoed by reproduction."""
    honest_round(module, c)
    honest = json.loads(captured["leader_fn"]())
    forged = reassemble(module, c, honest, requirement_rows=with_requirement(
        honest, "M2", finding="NOT_SATISFIED"))
    assert forged["verdict"] == "NOT_QUALIFIED"
    pkg, reqs = frozen_inputs(c)
    assert module._parse_payload(module._canonical(forged), AGREEMENT, 1, pkg["evidence_hash"],
                                 True, reqs, pkg["sources"]) is not None
    assert captured["validator_fn"](STATE.Return(module._canonical(forged))) is False


def test_validator_tolerates_prose_differences(module, c, captured):
    honest_round(module, c)
    honest = json.loads(captured["leader_fn"]())
    forged = reassemble(module, c, honest, requirement_rows=with_requirement(
        honest, "M3", note="worded differently"))
    assert captured["validator_fn"](STATE.Return(module._canonical(forged))) is True


def test_validator_rejects_llm_error_from_leader(module, c, captured):
    honest_round(module, c)
    assert captured["validator_fn"](
        STATE.UserError("[LLM_ERROR] synthesis result is not an object")) is False


def test_validator_rejects_a_vm_error(module, c, captured):
    honest_round(module, c)
    assert captured["validator_fn"](STATE.VMError("out of gas")) is False


# -- the structural gate: refuses before any reproduction -----------------------------

@pytest.fixture
def honest_payload(module, c, captured):
    honest_round(module, c)
    return json.loads(captured["leader_fn"]())


def mutate(payload, **top):
    out = json.loads(json.dumps(payload))
    out.update(top)
    return out


def drop_key(payload, key):
    out = json.loads(json.dumps(payload))
    del out[key]
    return out


FORGERIES = {
    "not_json": lambda p, m: "{not json",
    "not_object": lambda p, m: "[1, 2]",
    "wrong_agreement": lambda p, m: mutate(p, agreement_id="OTHER"),
    "wrong_version": lambda p, m: mutate(p, version=2),
    "bool_version": lambda p, m: mutate(p, version=True),
    "string_version": lambda p, m: mutate(p, version="1"),
    "wrong_schema": lambda p, m: mutate(p, schema_version=2),
    "wrong_evidence_hash": lambda p, m: mutate(p, evidence_hash="b" * 64),
    "unknown_verdict": lambda p, m: mutate(p, verdict="MAYBE"),
    "lowercase_verdict": lambda p, m: mutate(p, verdict="qualified"),
    "deadline_flipped": lambda p, m: mutate(p, deadline_met=False),
    "deadline_as_int": lambda p, m: mutate(p, deadline_met=1),
    "injection_as_int": lambda p, m: mutate(p, injection_suspected=0),
    "contradiction_as_int": lambda p, m: mutate(p, contradiction_suspected=0),
    "sufficient_as_string": lambda p, m: mutate(p, evidence_sufficient="true"),
    "missing_field": lambda p, m: drop_key(p, "sources"),
    "extra_field": lambda p, m: mutate(p, extra=1),
    "requirement_dropped": lambda p, m: mutate(p, requirements=p["requirements"][:-1]),
    "requirement_renamed": lambda p, m: mutate(p, requirements=with_requirement(p, "M3", requirement_id="M9")),
    "requirement_kind_changed": lambda p, m: mutate(p, requirements=with_requirement(p, "M3", kind="ACCESSIBLE")),
    "requirements_reordered": lambda p, m: mutate(p, requirements=list(reversed(p["requirements"]))),
    "unknown_finding": lambda p, m: mutate(p, requirements=with_requirement(p, "M3", finding="MAYBE")),
    "oversized_note": lambda p, m: mutate(p, requirements=with_requirement(p, "M3", note="x" * 241)),
    "requirement_row_extra_key": lambda p, m: mutate(p, requirements=with_requirement(p, "M3", extra=1)),
    "invented_source_row": lambda p, m: mutate(p, sources=p["sources"] + [dict(p["sources"][1], source_id="ghost")]),
    "source_row_dropped": lambda p, m: mutate(p, sources=p["sources"][:-1]),
    "sources_reordered": lambda p, m: mutate(p, sources=list(reversed(p["sources"]))),
    "source_renamed": lambda p, m: mutate(p, sources=with_source(p, "analysis", source_id="analysis2")),
    "source_kind_changed": lambda p, m: mutate(p, sources=with_source(p, "analysis", kind="DATASET")),
    "unknown_source_status": lambda p, m: mutate(p, sources=with_source(p, "analysis", status="SKIPPED")),
    "hash_match_inconsistent": lambda p, m: mutate(p, sources=with_source(p, "analysis", hash_match="MISMATCH")),
    "unknown_hash_match": lambda p, m: mutate(p, sources=with_source(p, "analysis", hash_match="MAYBE")),
    "byte_count_negative": lambda p, m: mutate(p, sources=with_source(p, "analysis", byte_count=-1)),
    "byte_count_as_bool": lambda p, m: mutate(p, sources=with_source(p, "analysis", byte_count=True)),
    "examined_source_with_zero_bytes": lambda p, m: mutate(p, sources=with_source(p, "analysis", byte_count=0)),
    "facts_on_a_text_source": lambda p, m: mutate(p, sources=with_source(p, "analysis", row_count=5)),
    "facts_on_an_excluded_source": lambda p, m: mutate(p, sources=with_source(
        p, "dataset", status="NOT_FOUND", hash_match="UNCHECKED")),
    "examined_count_wrong": lambda p, m: mutate(p, examined_source_count=3),
    "excluded_count_wrong": lambda p, m: mutate(p, excluded_source_count=1),
    "count_as_bool": lambda p, m: mutate(p, examined_source_count=True),
    "met_count_wrong": lambda p, m: mutate(p, requirements_met=5),
    "total_wrong": lambda p, m: mutate(p, requirements_total=7),
    "sufficient_inconsistent": lambda p, m: mutate(p, evidence_sufficient=False),
    # Isolating variants: the source rows stay honest, one deterministic
    # finding is flipped, and verdict / counts / reason codes / summary are
    # re-derived for the flipped finding - so ONLY the gate's recomputation
    # of that finding from the rows can refuse it.
    "accessible_finding_flipped_isolated": lambda p, m: rederived(
        m, p, with_requirement(p, "M5", finding="NOT_SATISFIED")),
    "row_count_finding_flipped_isolated": lambda p, m: rederived(
        m, p, with_requirement(p, "M1", finding="NOT_SATISFIED")),
    "row_count_unverifiable_isolated": lambda p, m: rederived(
        m, p, with_requirement(p, "M1", finding="UNVERIFIABLE")),
    "deadline_finding_flipped_isolated": lambda p, m: rederived(
        m, p, with_requirement(p, "M6", finding="NOT_SATISFIED")),
    "columns_unverifiable_while_examined_isolated": lambda p, m: rederived(
        m, p, with_requirement(p, "M2", finding="UNVERIFIABLE")),
    "semantic_satisfied_without_any_document": lambda p, m: rederived(
        m, p, p["requirements"],
        sources=[dict(s, status="UNAVAILABLE", hash_match="UNCHECKED", byte_count=0,
                      row_count=0, column_count=0) if s["kind"] != "DATASET" else s
                 for s in p["sources"]]),
    "verdict_inconsistent": lambda p, m: mutate(p, verdict="NOT_QUALIFIED"),
    "verdict_inconsistent_summary_adjusted": lambda p, m: mutate(
        p, verdict="NOT_QUALIFIED",
        summary=m._compose_summary("NOT_QUALIFIED", p["version"], p["examined_source_count"],
                                   len(p["sources"]), p["deadline_met"], p["requirements"])),
    "reason_codes_inconsistent": lambda p, m: mutate(p, reason_codes=["DEADLINE_MISSED"]),
    "summary_inconsistent": lambda p, m: mutate(p, summary="all good"),
}


@pytest.mark.parametrize("name", sorted(FORGERIES))
def test_structural_gate_refuses_forgery_without_reproducing(module, c, honest_payload, name):
    forged = FORGERIES[name](honest_payload, module)
    text = forged if isinstance(forged, str) else module._canonical(forged)
    pkg, reqs = frozen_inputs(c)
    args = (AGREEMENT, 1, pkg["evidence_hash"], True, reqs, pkg["sources"])
    assert module._parse_payload(text, *args) is None
    calls = []

    def reproduce():
        calls.append(1)
        return honest_payload
    assert module._validator_decision(STATE.Return(text), reproduce, *args) is False
    assert calls == []


def test_structural_gate_accepts_the_honest_payload(module, c, honest_payload):
    text = module._canonical(honest_payload)
    pkg, reqs = frozen_inputs(c)
    args = (AGREEMENT, 1, pkg["evidence_hash"], True, reqs, pkg["sources"])
    assert module._parse_payload(text, *args) == honest_payload
    calls = []

    def reproduce():
        calls.append(1)
        return honest_payload
    assert module._validator_decision(STATE.Return(text), reproduce, *args) is True
    assert calls == [1]


def test_reassembled_forgeries_are_consistent_yet_vetoed_by_reproduction(module, c, honest_payload):
    """A forgery that passes the gate (internally consistent) is still vetoed
    once the validator reproduces and compares decision fields."""
    forged = reassemble(module, c, honest_payload, requirement_rows=with_requirement(
        honest_payload, "M3", finding="NOT_SATISFIED"))
    text = module._canonical(forged)
    pkg, reqs = frozen_inputs(c)
    args = (AGREEMENT, 1, pkg["evidence_hash"], True, reqs, pkg["sources"])
    assert module._parse_payload(text, *args) is not None
    assert module._validator_decision(STATE.Return(text), lambda: honest_payload, *args) is False


# -- the comparison rule --------------------------------------------------------------------

def test_decision_field_differences_veto(module, c, honest_payload):
    p = honest_payload
    assert module._decision_fields_equal(p, mutate(p, verdict="INCONCLUSIVE")) is False
    assert module._decision_fields_equal(p, mutate(p, deadline_met=False)) is False
    assert module._decision_fields_equal(
        p, mutate(p, requirements=with_requirement(p, "M3", finding="UNVERIFIABLE"))) is False
    for field, value in (("status", "UNAVAILABLE"), ("hash_match", "MISMATCH"),
                         ("byte_count", 1), ("row_count", 9000), ("column_count", 6)):
        assert module._decision_fields_equal(
            p, mutate(p, sources=with_source(p, "dataset", **{field: value}))) is False


def test_prose_differences_do_not_veto(module, c, honest_payload):
    p = honest_payload
    theirs = mutate(p, summary="other words", reason_codes=[],
                    requirements=with_requirement(p, "M3", note="different"))
    assert module._decision_fields_equal(p, theirs) is True


# -- error rows of the result table ----------------------------------------------------------

def test_llm_error_always_disagrees(module):
    def reproduce():
        raise STATE.UserError("[LLM_ERROR] synthesis result is not an object")
    assert module._vote_on_leader_error(
        STATE.UserError("[LLM_ERROR] synthesis result is not an object"), reproduce) is False


def test_transient_agrees_only_with_transient(module):
    leader = STATE.UserError("[TRANSIENT] transaction clock unreadable")

    def own_transient():
        raise STATE.UserError("[TRANSIENT] different wording")

    def own_expected():
        raise STATE.UserError("[EXPECTED] something else")

    def own_success():
        return {}
    assert module._vote_on_leader_error(leader, own_transient) is True
    assert module._vote_on_leader_error(leader, own_expected) is False
    assert module._vote_on_leader_error(leader, own_success) is False


def test_expected_error_needs_identical_text(module):
    leader = STATE.UserError("[EXPECTED] policy refusal")

    def same():
        raise STATE.UserError("[EXPECTED] policy refusal")

    def other():
        raise STATE.UserError("[EXPECTED] other refusal")

    def crash():
        raise RuntimeError("boom")
    assert module._vote_on_leader_error(leader, same) is True
    assert module._vote_on_leader_error(leader, other) is False
    assert module._vote_on_leader_error(leader, crash) is False


def test_non_user_error_result_disagrees(module, c):
    assert module._vote_on_leader_error(STATE.VMError("vm error"), lambda: {}) is False
    assert module._validator_decision(STATE.VMError("vm error"), lambda: {}, AGREEMENT, 1,
                                      "a" * 64, True, [], []) is False


def test_validator_own_exception_propagates_fail_closed(module, c, honest_payload):
    def reproduce():
        raise RuntimeError("validator crashed")
    pkg, reqs = frozen_inputs(c)
    with pytest.raises(RuntimeError):
        module._validator_decision(STATE.Return(module._canonical(honest_payload)),
                                   reproduce, AGREEMENT, 1, pkg["evidence_hash"], True,
                                   reqs, pkg["sources"])


def test_a_vetoed_round_writes_nothing(module, c):
    """Leader and validator see different model answers: the stub run_nondet
    raises the disagreement, the agreement stays UNDER_REVIEW, no receipt."""
    from tests.direct.support import panel_sequence, agreement
    submitted(module, c)
    serve_package()
    panel_sequence(SEMANTIC_SATISFIED,
                   dict(SEMANTIC_SATISFIED, M3={"finding": "NOT_SATISFIED", "contradiction": False,
                                                "injection": False, "note": ""}))
    as_(module, STRANGER, 0)
    with pytest.raises(STATE.UserError, match="validators did not agree"):
        c.adjudicate(AGREEMENT)
    assert agreement(c)["status"] == "UNDER_REVIEW"
    assert json.loads(c.get_receipt(AGREEMENT, 1))["found"] is False
