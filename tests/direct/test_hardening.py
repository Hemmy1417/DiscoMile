"""Hardening: the contract boundary refuses a malformed ratified payload
(tampered round through a patched run_nondet), the normalization pipeline
coerces only safe differences and never repairs a bad value into a good
one, the deterministic policy functions are exact, the clock is the
transaction's, and source-level invariants (one round primitive, JSON-only
prompts, one transfer) hold."""

import ast
import json
import pathlib

import pytest

from tests.direct.conftest import CONTRACT_PATH, STATE, STRANGER
from tests.direct.support import (
    AGREEMENT, OBJECTIVE, SEMANTIC_SATISFIED, TITLE, agreement, as_, panel_says,
    serve_package, submitted, verdict,
)
from tests.direct.test_equivalence import FORGERIES, reassemble


def _honest_payload(module, c):
    """One node's derivation under the honest mocks - what a leader returns."""
    pkg = json.loads(c.get_evidence(AGREEMENT, 1))
    reqs = json.loads(c.get_requirements(AGREEMENT))["requirements"]
    STATE.panel_calls[0] = 0
    return module._node_derivation(AGREEMENT, 1, pkg["evidence_hash"], True, reqs,
                                   pkg["sources"], {"title": TITLE, "objective": OBJECTIVE})


@pytest.fixture
def tampered(module):
    real = module.gl.vm.run_nondet
    holder = {"text": None}
    module.gl.vm.run_nondet = lambda leader_fn, validator_fn: holder["text"]
    yield holder
    module.gl.vm.run_nondet = real


@pytest.mark.parametrize("name", sorted(FORGERIES))
def test_boundary_refuses_a_malformed_ratified_payload(module, c, tampered, name):
    submitted(module, c)
    serve_package()
    panel_says(SEMANTIC_SATISFIED)
    honest = _honest_payload(module, c)
    forged = FORGERIES[name](honest, module)
    tampered["text"] = forged if isinstance(forged, str) else module._canonical(forged)
    as_(module, STRANGER, 0)
    with pytest.raises(STATE.UserError, match=r"\[LLM_ERROR\] malformed ratified payload"):
        c.adjudicate(AGREEMENT)
    ag = agreement(c)
    assert ag["status"] == "UNDER_REVIEW" and ag["judged_version"] == 0
    assert json.loads(c.get_receipt(AGREEMENT, 1))["found"] is False
    assert c.is_qualified(AGREEMENT) is False


def test_boundary_accepts_the_honest_payload_control(module, c, tampered):
    submitted(module, c)
    serve_package()
    panel_says(SEMANTIC_SATISFIED)
    tampered["text"] = module._canonical(_honest_payload(module, c))
    as_(module, STRANGER, 0)
    c.adjudicate(AGREEMENT)
    assert verdict(c)["verdict"] == "QUALIFIED"


def test_boundary_refuses_a_consistent_but_late_flip(module, c, tampered):
    """deadline_met is a frozen input: a ratified payload cannot claim a
    different one, however consistent the rest is."""
    submitted(module, c)
    serve_package()
    panel_says(SEMANTIC_SATISFIED)
    honest = _honest_payload(module, c)
    tampered["text"] = module._canonical(reassemble(module, c, honest, deadline_met=False))
    as_(module, STRANGER, 0)
    with pytest.raises(STATE.UserError, match="malformed ratified payload"):
        c.adjudicate(AGREEMENT)


# -- normalization ------------------------------------------------------------------------

@pytest.mark.parametrize("value,expected", [
    (True, True), ("true", True), ("Yes", True), (1, True), ("1", True),
    (False, False), ("false", False), (0, False), (None, False), ("", False),
    (2, False), ([True], False),
])
def test_coerce_bool(module, value, expected):
    assert module._coerce_bool(value) is expected


def test_coerce_text_flattens_and_caps(module):
    assert module._coerce_text("a\nb\tc\r\nd", 300) == "a b c  d"
    assert module._coerce_text("x" * 400, 300) == "x" * 300
    assert module._coerce_text(None, 10) == ""
    assert module._coerce_text(12.5, 10) == "12.5"


def test_normalize_semantic_raises_llm_error_on_non_object(module):
    with pytest.raises(STATE.UserError) as info:
        module._normalize_semantic("nope", ["M3"])
    assert str(info.value).startswith("[LLM_ERROR]")


def test_normalize_semantic_maps_the_vocabulary_exactly(module):
    raw = {
        "M3": {"finding": "satisfied", "contradiction": False, "injection": False, "note": "n"},
        "M4": {"finding": " not satisfied ", "contradiction": "no", "injection": "no"},
        "M7": {"finding": "SATISFIED", "contradiction": False, "injection": True, "note": "smuggled"},
        "M8": {"finding": "SATISFIED", "contradiction": True, "injection": False, "note": "disagrees"},
        "M9": "SATISFIED",
    }
    out = module._normalize_semantic(raw, ["M3", "M4", "M7", "M8", "M9", "M10"])
    assert out["M3"] == ("SATISFIED", False, False, "n")
    assert out["M4"] == ("NOT_SATISFIED", False, False, "")
    assert out["M7"] == ("UNVERIFIABLE", False, True, "smuggled")     # injection forces UNVERIFIABLE
    assert out["M8"] == ("UNVERIFIABLE", True, False, "disagrees")    # so does contradiction
    assert out["M9"] == ("UNVERIFIABLE", False, False, "model returned no usable finding")
    assert out["M10"] == ("UNVERIFIABLE", False, False, "model returned no usable finding")


@pytest.mark.parametrize("text,expected", [
    ("2026-12-01", "2026-12-01T23:59:59Z"),
    ("2026-12-01T09:30:00Z", "2026-12-01T09:30:00Z"),
    ("2026-02-29", None), ("2028-02-29", "2028-02-29T23:59:59Z"),
    ("2026-12-01T24:00:00Z", None), ("2026-12-01T09:30:00", None),
    ("2026-12-01 09:30:00Z", None), ("", None), (20261201, None),
])
def test_normalize_deadline(module, text, expected):
    assert module._normalize_deadline(text) == expected


@pytest.mark.parametrize("text,expected", [
    ("2026-09-06T12:00:00Z", "2026-09-06T12:00:00Z"),
    ("2026-09-06T12:00:00.123456Z", "2026-09-06T12:00:00Z"),
    ("2026-09-06T12:00:00+00:00", "2026-09-06T12:00:00Z"),
    ("2026-09-06 12:00:00", "2026-09-06T12:00:00Z"),
    ("2026-09-06T12:00:00.123456+00:00", "2026-09-06T12:00:00Z"),
    ("garbage", None), ("2026-09-06", None), (None, None),
])
def test_normalize_instant(module, text, expected):
    assert module._normalize_instant(text) == expected


def test_instants_compare_lexicographically(module):
    assert module._instant_key("2026-12-01T23:59:59Z") < module._instant_key("2026-12-02T00:00:00Z")
    assert module._instant_key("2026-09-06T12:00:00Z") <= module._instant_key("2026-12-01T23:59:59Z")


def test_unreadable_clock_fails_closed(module, c):
    from tests.direct.support import create, set_clock
    set_clock("not a clock")
    with pytest.raises(STATE.UserError, match=r"\[TRANSIENT\] transaction clock unreadable"):
        create(module, c)
    assert agreement(c)["found"] is False


@pytest.mark.parametrize("value,expected", [
    ("0xABCDEF0000000000000000000000000000000000", "0xabcdef0000000000000000000000000000000000"),
    (" 0xabc ", "0xabc"),
])
def test_addr_str_normalizes(module, value, expected):
    assert module._addr_str(value) == expected

    class Obj:
        as_hex = value
    assert module._addr_str(Obj()) == expected


@pytest.mark.parametrize("text,length,ok", [
    ("a" * 40, 40, True), ("A" * 40, 40, False), ("a" * 39, 40, False),
    ("g" * 40, 40, False), ("0" * 64, 64, True), (None, 64, False)])
def test_is_hex(module, text, length, ok):
    assert module._is_hex(text, length) is ok


# -- deterministic policy functions ----------------------------------------------------------

def test_reason_codes_are_fixed_and_ordered(module):
    rows = [{"requirement_id": "M3", "finding": "UNVERIFIABLE"},
            {"requirement_id": "M4", "finding": "NOT_SATISFIED"}]
    sources = [{"status": "HASH_MISMATCH"}, {"status": "NOT_FOUND"}, {"status": "EXAMINED"},
               {"status": "TOO_LARGE"}]
    assert module._derive_reason_codes(False, rows, sources, True, True) == [
        "DEADLINE_MISSED", "REQUIREMENT_NOT_SATISFIED", "REQUIREMENT_UNVERIFIABLE",
        "EVIDENCE_NOT_FOUND", "EVIDENCE_HASH_MISMATCH", "EVIDENCE_TOO_LARGE",
        "EVIDENCE_CONTRADICTORY", "INJECTION_SUSPECTED"]
    assert module._derive_reason_codes(True, [{"requirement_id": "M3", "finding": "SATISFIED"}],
                                       [{"status": "EXAMINED"}], False, False) == ["ALL_REQUIREMENTS_SATISFIED"]


def test_valid_date_and_time_edges(module):
    assert module._valid_date("2024-02-29") and not module._valid_date("2026-02-29")
    assert module._valid_date("2000-02-29") and not module._valid_date("1900-02-29")
    assert not module._valid_date("2026-04-31") and not module._valid_date("1969-12-31")
    assert module._valid_time("23:59:59") and not module._valid_time("24:00:00")
    assert not module._valid_time("23:60:00") and not module._valid_time("2:00:00")


# -- source-level invariants --------------------------------------------------------------------

def test_exactly_one_round_primitive_and_json_only_prompts():
    text = pathlib.Path(CONTRACT_PATH).read_text(encoding="utf-8")
    assert text.count("gl.vm.run_nondet(") == 1
    assert "run_nondet_unsafe" not in text
    assert "gl.message_raw" not in text            # v0.3 spelling; absent on v0.6
    tree = ast.parse(text)
    prompts = [n for n in ast.walk(tree)
               if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
               and n.func.attr == "exec_prompt"]
    assert len(prompts) == 1
    assert all(any(k.arg == "response_format" and k.value.value == "json"
                   for k in call.keywords) for call in prompts)
    calls = text.count(".emit_transfer(value=u256(amount))")
    assert calls == 1                              # claim() is the only value path
    assert 'on="' not in text.split(".emit_transfer(")[1][:80]


def test_header_pins_the_studio_next_runner():
    lines = pathlib.Path(CONTRACT_PATH).read_text(encoding="utf-8").split("\n")
    assert lines[0] == "# v0.3.0"
    assert lines[1] == '# { "Depends": "py-genlayer:5jycge4q8k23462jtb0b9fyey1s9qz928sz2nbrd9mg4sxqg2qng" }'
    assert lines[2] == ""
