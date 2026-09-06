"""Deterministic surface: agreement terms, funding, evidence packages,
ownership, lifecycle refusals, paging and views. No consensus round runs
here except where a lifecycle step needs a recorded verdict to reach a
state."""

import json

import pytest

from tests.direct.conftest import RESEARCHER, SPONSOR, STRANGER
from tests.direct.support import (
    AGREEMENT, DATASET, DEADLINE, OBJECTIVE, PACKAGE, RAW, REQUIREMENTS, REWARD,
    SOURCES, TITLE, ZENODO, adjudicated, agreement, as_, create, err, evidence,
    funded, package_lists, requirement_lists, requirements, sent, set_clock,
    sha256_hex, source_lists, sources, submitted, verdict, with_url,
)


# -- create_agreement ------------------------------------------------------------

def test_create_freezes_terms(module, c):
    terms_hash = create(module, c)
    ag = agreement(c)
    assert ag["found"] and ag["status"] == "DRAFT" and ag["verdict"] == ""
    assert ag["sponsor"] == SPONSOR and ag["researcher"] == RESEARCHER
    assert ag["title"] == TITLE and ag["objective"] == OBJECTIVE
    assert ag["deadline"] == "2026-12-01T23:59:59Z"
    assert ag["reward_atto"] == str(REWARD) and ag["escrow_atto"] == "0"
    assert ag["terms_hash"] == terms_hash and len(terms_hash) == 64
    assert c.get_terms_hash(AGREEMENT) == terms_hash
    assert ag["source_count"] == 4 and ag["requirement_count"] == 6
    assert ag["package_count"] == 0 and ag["judged_version"] == 0
    assert ag["qualified"] is False and ag["released"] is False
    assert ag["resubmittable"] is False
    assert ag["created_at"] == "2026-09-06T12:00:00Z"
    srcs = sources(c)["sources"]
    assert [s["source_id"] for s in srcs] == ["dataset", "methodology", "analysis", "preprint"]
    assert srcs[0] == {"source_id": "dataset", "kind": "DATASET",
                       "description": SOURCES[0][2]}
    reqs = requirements(c)["requirements"]
    assert [r["requirement_id"] for r in reqs] == ["M1", "M2", "M3", "M4", "M5", "M6"]
    assert reqs[0] == {"requirement_id": "M1", "kind": "ROW_COUNT_MIN",
                       "criterion": REQUIREMENTS[0][2], "source_id": "dataset",
                       "param": "10000"}
    assert reqs[5]["kind"] == "DEADLINE" and reqs[5]["source_id"] == ""
    assert json.loads(c.get_config())["total_agreements"] == 1
    assert c.is_qualified(AGREEMENT) is False


def test_full_datetime_deadline_is_kept(module, c):
    create(module, c, deadline="2026-12-01T09:30:00Z")
    assert agreement(c)["deadline"] == "2026-12-01T09:30:00Z"


def test_indexes_by_sponsor_and_researcher(module, c):
    create(module, c)
    create(module, c, agreement_id="DM-2")
    by_sponsor = json.loads(c.get_agreements_by(SPONSOR, "sponsor", 0, 10))
    assert by_sponsor["total"] == 2 and by_sponsor["agreement_ids"] == [AGREEMENT, "DM-2"]
    by_researcher = json.loads(c.get_agreements_by(RESEARCHER, "researcher", 0, 1))
    assert by_researcher["agreement_ids"] == [AGREEMENT] and by_researcher["total"] == 2
    assert json.loads(c.get_agreements_by(RESEARCHER, "researcher", 1, 1))["agreement_ids"] == ["DM-2"]
    assert json.loads(c.get_agreements_by(RESEARCHER, "researcher", 5, 1))["agreement_ids"] == []
    assert json.loads(c.get_agreements_by(RESEARCHER, "researcher", 0, 999))["limit"] == 50
    assert json.loads(c.get_agreements_by(RESEARCHER, "researcher", -3, 0))["agreement_ids"] == []
    assert json.loads(c.get_agreements_by(STRANGER, "sponsor", 0, 10))["agreement_ids"] == []
    assert json.loads(c.get_agreements_by(SPONSOR, "owner", 0, 10))["found"] is False
    assert json.loads(c.get_agreements_by("not-an-address", "sponsor", 0, 10))["total"] == 0


def test_duplicate_id_refused_for_anyone(module, c):
    create(module, c)
    with pytest.raises(err(module), match="already exists"):
        create(module, c)
    with pytest.raises(err(module), match="already exists"):
        create(module, c, sender=STRANGER, researcher=SPONSOR)


@pytest.mark.parametrize("field,value,message", [
    ("agreement_id", "", "agreement_id must be"),
    ("agreement_id", "x" * 65, "agreement_id must be"),
    ("agreement_id", "bad id", "agreement_id must be"),
    ("researcher", "0x1234", "researcher must be a 0x address"),
    ("researcher", SPONSOR, "researcher must differ from the sponsor"),
    ("researcher", "0x" + "0" * 40, "zero address"),
    ("title", "", "title is required"),
    ("title", "x" * 121, "title exceeds 120"),
    ("title", "a\nb", "control characters"),
    ("objective", "", "objective is required"),
    ("objective", "x" * 601, "objective exceeds 600"),
    ("objective", "a\tb", "control characters"),
    ("deadline", "2026-13-01", "deadline must be"),
    ("deadline", "2026/12/01", "deadline must be"),
    ("deadline", "2026-12-01T25:00:00Z", "deadline must be"),
    ("deadline", "2026-12-01T09:30:00", "deadline must be"),
    ("deadline", "2026-09-06T12:00:00Z", "deadline must be in the future"),
    ("deadline", "2026-09-05", "deadline must be in the future"),
    ("deadline", "2026-01-01", "deadline must be in the future"),
    ("reward", 0, "reward_atto out of bounds"),
    ("reward", 10 ** 15 - 1, "reward_atto out of bounds"),
    ("reward", 10 ** 21 + 1, "reward_atto out of bounds"),
])
def test_invalid_terms_refused(module, c, field, value, message):
    kwargs = {field: value}
    with pytest.raises(err(module), match=message):
        create(module, c, **kwargs)
    assert agreement(c)["found"] is False


@pytest.mark.parametrize("reward_text,message", [
    ("", "decimal string"), ("1e18", "decimal string"), ("-5", "decimal string"),
    ("1" * 25, "decimal string"), ("0x10", "decimal string"),
])
def test_reward_must_be_a_decimal_string(module, c, reward_text, message):
    sids, skinds, sdescs = source_lists()
    rids, rkinds, criteria, rsources, params = requirement_lists()
    with pytest.raises(err(module), match=message):
        c.create_agreement(AGREEMENT, RESEARCHER, "t", "o", DEADLINE, reward_text,
                           sids, skinds, sdescs, rids, rkinds, criteria, rsources, params)


def _sources(mutate):
    rows = [list(s) for s in SOURCES]
    mutate(rows)
    return [tuple(r) for r in rows]


@pytest.mark.parametrize("mutate,message", [
    (lambda r: r.clear(), "1..8 evidence sources"),
    (lambda r: r.extend([list(r[1])] * 5), "1..8 evidence sources"),
    (lambda r: r[1].__setitem__(0, "dataset"), "duplicate source_id"),
    (lambda r: r[1].__setitem__(0, "bad id"), "source_id must be"),
    (lambda r: r[1].__setitem__(0, "x" * 33), "source_id must be"),
    (lambda r: r[1].__setitem__(1, "VIDEO"), "unsupported source kind"),
    (lambda r: r[1].__setitem__(2, ""), "source description is required"),
    (lambda r: r[1].__setitem__(2, "x" * 241), "source description exceeds 240"),
    (lambda r: r[1].__setitem__(2, "a\rb"), "control characters"),
])
def test_invalid_sources_refused(module, c, mutate, message):
    with pytest.raises(err(module), match=message):
        create(module, c, sources=_sources(mutate))
    assert agreement(c)["found"] is False


def _reqs(mutate):
    rows = [list(r) for r in REQUIREMENTS]
    mutate(rows)
    return [tuple(r) for r in rows]


@pytest.mark.parametrize("mutate,message", [
    (lambda r: r.clear(), "1..12 requirements"),
    (lambda r: r.extend([list(r[2])] * 7), "1..12 requirements"),
    (lambda r: r[1].__setitem__(0, "M1"), "duplicate requirement_id"),
    (lambda r: r[1].__setitem__(0, "bad id"), "requirement_id must be"),
    (lambda r: r[1].__setitem__(0, "x" * 33), "requirement_id must be"),
    (lambda r: r[1].__setitem__(1, "MANUAL"), "unsupported requirement kind"),
    (lambda r: r[1].__setitem__(2, ""), "criterion is required"),
    (lambda r: r[1].__setitem__(2, "x" * 601), "criterion exceeds 600"),
    (lambda r: r[1].__setitem__(2, "a\tb"), "criterion contains control"),
    (lambda r: r[0].__setitem__(3, "ghost"), "ROW_COUNT_MIN requirement must name a declared source_id"),
    (lambda r: r[0].__setitem__(3, ""), "ROW_COUNT_MIN requirement must name a declared source_id"),
    (lambda r: r[0].__setitem__(3, "methodology"), "ROW_COUNT_MIN requirement must name a DATASET source"),
    (lambda r: r[1].__setitem__(3, "preprint"), "COLUMNS_REQUIRED requirement must name a DATASET source"),
    (lambda r: r[0].__setitem__(4, "0"), "ROW_COUNT_MIN param must be a record count"),
    (lambda r: r[0].__setitem__(4, ""), "ROW_COUNT_MIN param must be a record count"),
    (lambda r: r[0].__setitem__(4, "ten"), "ROW_COUNT_MIN param must be a record count"),
    (lambda r: r[0].__setitem__(4, "1000000001"), "ROW_COUNT_MIN param must be a record count"),
    (lambda r: r[0].__setitem__(4, "-5"), "ROW_COUNT_MIN param must be a record count"),
    (lambda r: r[1].__setitem__(4, ""), "COLUMNS_REQUIRED param must list"),
    (lambda r: r[1].__setitem__(4, "a,,b"), "COLUMNS_REQUIRED param must list"),
    (lambda r: r[1].__setitem__(4, "a,a"), "COLUMNS_REQUIRED param must list"),
    (lambda r: r[1].__setitem__(4, 'a,"b"'), "COLUMNS_REQUIRED param must list"),
    (lambda r: r[1].__setitem__(4, ",".join("c%d" % i for i in range(65))), "COLUMNS_REQUIRED param must list"),
    (lambda r: r[1].__setitem__(4, "x" * 65), "COLUMNS_REQUIRED param must list"),
    (lambda r: r[4].__setitem__(4, "yes"), "ACCESSIBLE requirement must leave param empty"),
    (lambda r: r[4].__setitem__(3, "nowhere"), "ACCESSIBLE requirement must name a declared source_id"),
    (lambda r: r[5].__setitem__(3, "dataset"), "DEADLINE requirement must leave source_id empty"),
    (lambda r: r[5].__setitem__(4, "1"), "DEADLINE requirement must leave param empty"),
    (lambda r: r[2].__setitem__(3, "methodology"), "SEMANTIC requirement must leave source_id empty"),
    (lambda r: r[2].__setitem__(4, "strict"), "SEMANTIC requirement must leave param empty"),
])
def test_invalid_requirements_refused(module, c, mutate, message):
    with pytest.raises(err(module), match=message):
        create(module, c, reqs=_reqs(mutate))
    assert agreement(c)["found"] is False


def test_term_lists_must_align(module, c):
    sids, skinds, sdescs = source_lists()
    rids, rkinds, criteria, rsources, params = requirement_lists()
    with pytest.raises(err(module), match="source field lists must have equal length"):
        c.create_agreement(AGREEMENT, RESEARCHER, "t", "o", DEADLINE, str(REWARD),
                           sids, skinds[:2], sdescs, rids, rkinds, criteria, rsources, params)
    with pytest.raises(err(module), match="requirement field lists must have equal length"):
        c.create_agreement(AGREEMENT, RESEARCHER, "t", "o", DEADLINE, str(REWARD),
                           sids, skinds, sdescs, rids, rkinds[:2], criteria, rsources, params)
    with pytest.raises(err(module), match="requirement fields must be lists"):
        c.create_agreement(AGREEMENT, RESEARCHER, "t", "o", DEADLINE, str(REWARD),
                           sids, skinds, sdescs, rids, "SEMANTIC", criteria, rsources, params)


def test_researcher_may_arrive_as_an_address_object(module, c):
    class CliAddress:
        as_hex = RESEARCHER.upper().replace("0X", "0x")
    sids, skinds, sdescs = source_lists()
    rids, rkinds, criteria, rsources, params = requirement_lists()
    c.create_agreement(AGREEMENT, CliAddress(), "t", "o", DEADLINE, str(REWARD),
                       sids, skinds, sdescs, rids, rkinds, criteria, rsources, params)
    assert agreement(c)["researcher"] == RESEARCHER


def test_an_agreement_of_only_deterministic_requirements_is_allowed(module, c):
    reqs = [r for r in REQUIREMENTS if r[1] != "SEMANTIC"]
    create(module, c, reqs=reqs)
    assert agreement(c)["requirement_count"] == 4


# -- fund_agreement ---------------------------------------------------------------

def test_fund_reserves_exactly_the_reward(module, c):
    create(module, c)
    as_(module, SPONSOR, REWARD)
    out = json.loads(c.fund_agreement(AGREEMENT))
    assert out == {"escrow_atto": str(REWARD), "status": "FUNDED"}
    ag = agreement(c)
    assert ag["status"] == "FUNDED" and ag["escrow_atto"] == str(REWARD)
    assert ag["funded_at"] == "2026-09-06T12:00:00Z"
    assert json.loads(c.get_config())["escrow_total_atto"] == str(REWARD)


@pytest.mark.parametrize("value", [REWARD - 1, REWARD + 1, 0])
def test_fund_refuses_an_inexact_deposit(module, c, value):
    create(module, c)
    as_(module, SPONSOR, value)
    with pytest.raises(err(module), match="deposit must equal the reward exactly"):
        c.fund_agreement(AGREEMENT)
    assert agreement(c)["status"] == "DRAFT"


def test_only_the_sponsor_funds(module, c):
    create(module, c)
    for who in (STRANGER, RESEARCHER):
        as_(module, who, REWARD)
        with pytest.raises(err(module), match="only the sponsor funds"):
            c.fund_agreement(AGREEMENT)


def test_fund_twice_refused(module, c):
    funded(module, c)
    as_(module, SPONSOR, REWARD)
    with pytest.raises(err(module), match="not a draft"):
        c.fund_agreement(AGREEMENT)


def test_fund_unknown(module, c):
    as_(module, SPONSOR, REWARD)
    with pytest.raises(err(module), match="unknown agreement_id"):
        c.fund_agreement("nope")


# -- submit_evidence ----------------------------------------------------------------

def test_submit_commits_the_package(module, c):
    funded(module, c)
    as_(module, RESEARCHER, 0)
    ids, urls, hashes = package_lists()
    assert c.submit_evidence(AGREEMENT, ids, urls, hashes) == 1
    ag = agreement(c)
    assert ag["status"] == "UNDER_REVIEW" and ag["package_count"] == 1
    pkg = evidence(c)
    assert pkg["found"] and pkg["version"] == 1 and pkg["status"] == "PENDING"
    assert pkg["deadline_met"] is True
    assert pkg["committed_at"] == "2026-09-06T12:00:00Z"
    assert len(pkg["evidence_hash"]) == 64
    assert [s["source_id"] for s in pkg["sources"]] == ["dataset", "methodology", "analysis", "preprint"]
    assert pkg["sources"][0] == {"source_id": "dataset", "kind": "DATASET",
                                 "url": RAW + "dataset/observations.csv",
                                 "content_hash": sha256_hex(DATASET)}
    assert json.loads(c.get_evidence(AGREEMENT, 2))["found"] is False
    assert json.loads(c.get_evidence(AGREEMENT, 0))["found"] is False


def test_package_order_is_the_agreement_order(module, c):
    funded(module, c)
    as_(module, RESEARCHER, 0)
    ids, urls, hashes = package_lists(order=["preprint", "dataset", "analysis", "methodology"])
    c.submit_evidence(AGREEMENT, ids, urls, hashes)
    assert [s["source_id"] for s in evidence(c)["sources"]] == ["dataset", "methodology", "analysis", "preprint"]


def test_zenodo_record_files_are_accepted_locations(module, c):
    funded(module, c)
    as_(module, RESEARCHER, 0)
    package = with_url("dataset", ZENODO + "observations.csv?download=1")
    c.submit_evidence(AGREEMENT, *package_lists(package))
    assert evidence(c)["sources"][0]["url"] == ZENODO + "observations.csv?download=1"


def test_late_package_is_accepted_but_marked(module, c):
    funded(module, c)
    set_clock("2026-12-02T00:00:00Z")
    as_(module, RESEARCHER, 0)
    c.submit_evidence(AGREEMENT, *package_lists())
    assert evidence(c)["deadline_met"] is False


def test_package_on_the_deadline_second_counts(module, c):
    funded(module, c)
    set_clock("2026-12-01T23:59:59Z")
    as_(module, RESEARCHER, 0)
    c.submit_evidence(AGREEMENT, *package_lists())
    assert evidence(c)["deadline_met"] is True


def test_only_the_researcher_submits(module, c):
    funded(module, c)
    for who in (SPONSOR, STRANGER):
        as_(module, who, 0)
        with pytest.raises(err(module), match="only the researcher submits"):
            c.submit_evidence(AGREEMENT, *package_lists())


def test_submit_needs_funding_first(module, c):
    create(module, c)
    as_(module, RESEARCHER, 0)
    with pytest.raises(err(module), match="does not accept evidence in status DRAFT"):
        c.submit_evidence(AGREEMENT, *package_lists())


def test_submit_while_under_review_refused(module, c):
    submitted(module, c)
    as_(module, RESEARCHER, 0)
    with pytest.raises(err(module), match="does not accept evidence in status UNDER_REVIEW"):
        c.submit_evidence(AGREEMENT, *package_lists())


BAD_URLS = [
    "http://raw.githubusercontent.com/o/r/" + "a" * 40 + "/f.csv",
    "https://github.com/o/r/blob/" + "a" * 40 + "/f.csv",
    "https://raw.githubusercontent.com/o/r/main/f.csv",
    "https://raw.githubusercontent.com/o/r/" + "a" * 39 + "/f.csv",
    "https://raw.githubusercontent.com/o/r/" + "A" * 40 + "/f.csv",
    "https://raw.githubusercontent.com/o/r/" + "a" * 40 + "/../f.csv",
    "https://raw.githubusercontent.com/o/r/" + "a" * 40 + "/",
    "https://raw.githubusercontent.com/-o/r/" + "a" * 40 + "/f.csv",
    "https://raw.githubusercontent.com/o/r.git/" + "a" * 40 + "/f.csv",
    "https://raw.githubusercontent.com/o/r/" + "a" * 40 + "/a b.csv",
    "https://zenodo.org/records/123/files/f.csv",
    "https://zenodo.org/records/abc/files/f.csv?download=1",
    "https://zenodo.org/records/123/f.csv?download=1",
    "https://zenodo.org/records/123/files/a/b.csv?download=1",
    "https://zenodo.org/records/123/files/..?download=1",
    "https://example.org/data.csv",
    "",
    "https://raw.githubusercontent.com/o/r/" + "a" * 40 + "/" + "f" * 400 + ".csv",
]


@pytest.mark.parametrize("url", BAD_URLS)
def test_invalid_locations_refused(module, c, url):
    funded(module, c)
    as_(module, RESEARCHER, 0)
    with pytest.raises(err(module), match="url must be a commit-pinned"):
        c.submit_evidence(AGREEMENT, *package_lists(with_url("dataset", url)))
    assert agreement(c)["status"] == "FUNDED" and agreement(c)["package_count"] == 0


@pytest.mark.parametrize("hashes,message", [
    ({"dataset": "A" * 64}, "content_hash must be 64 lowercase hex"),
    ({"dataset": "a" * 63}, "content_hash must be 64 lowercase hex"),
    ({"dataset": ""}, "content_hash must be 64 lowercase hex"),
])
def test_invalid_hashes_refused(module, c, hashes, message):
    funded(module, c)
    as_(module, RESEARCHER, 0)
    with pytest.raises(err(module), match=message):
        c.submit_evidence(AGREEMENT, *package_lists(hashes=hashes))


def test_package_must_cover_every_source_exactly_once(module, c):
    funded(module, c)
    as_(module, RESEARCHER, 0)
    ids, urls, hashes = package_lists()
    with pytest.raises(err(module), match="covers every declared source exactly once"):
        c.submit_evidence(AGREEMENT, ids[:3], urls[:3], hashes[:3])
    with pytest.raises(err(module), match="covers every declared source exactly once"):
        c.submit_evidence(AGREEMENT, ids + ["extra"], urls + [urls[0]], hashes + [hashes[0]])
    with pytest.raises(err(module), match="duplicate or invalid source_id"):
        c.submit_evidence(AGREEMENT, ["dataset"] * 4, urls, hashes)
    with pytest.raises(err(module), match="missing source preprint"):
        c.submit_evidence(AGREEMENT, ids[:3] + ["ghost"], urls, hashes)
    with pytest.raises(err(module), match="equal length"):
        c.submit_evidence(AGREEMENT, ids, urls[:2], hashes)
    with pytest.raises(err(module), match="evidence fields must be lists"):
        c.submit_evidence(AGREEMENT, "dataset", urls, hashes)
    assert agreement(c)["package_count"] == 0


# -- lifecycle refusals around the round --------------------------------------------

def test_adjudicate_needs_a_pending_package(module, c):
    with pytest.raises(err(module), match="unknown agreement_id"):
        c.adjudicate("nope")
    create(module, c)
    with pytest.raises(err(module), match="no evidence package is under review"):
        c.adjudicate(AGREEMENT)
    as_(module, SPONSOR, REWARD)
    c.fund_agreement(AGREEMENT)
    with pytest.raises(err(module), match="no evidence package is under review"):
        c.adjudicate(AGREEMENT)


def test_second_adjudication_of_a_package_is_impossible(module, c):
    adjudicated(module, c)
    with pytest.raises(err(module), match="no evidence package is under review"):
        c.adjudicate(AGREEMENT)
    assert agreement(c)["judged_version"] == 1


def test_resubmission_after_a_negative_verdict(module, c):
    adjudicated(module, c, answer={
        "M3": {"finding": "NOT_SATISFIED", "contradiction": False, "injection": False,
               "note": "no replicate policy"},
        "M4": {"finding": "SATISFIED", "contradiction": False, "injection": False, "note": ""},
    })
    assert verdict(c)["verdict"] == "NOT_QUALIFIED" and verdict(c)["resubmittable"]
    as_(module, RESEARCHER, 0)
    assert c.submit_evidence(AGREEMENT, *package_lists()) == 2
    ag = agreement(c)
    assert ag["status"] == "UNDER_REVIEW" and ag["package_count"] == 2
    assert ag["judged_version"] == 1
    assert evidence(c, version=1)["status"] == "ADJUDICATED"
    assert evidence(c, version=2)["status"] == "PENDING"
    assert verdict(c)["consumable"] is False and verdict(c)["finalized"] is False


def test_no_resubmission_after_qualified(module, c):
    adjudicated(module, c)
    as_(module, RESEARCHER, 0)
    with pytest.raises(err(module), match="already qualified"):
        c.submit_evidence(AGREEMENT, *package_lists())


def test_package_limit(module, c):
    negative = {rid: {"finding": "UNVERIFIABLE", "contradiction": False,
                      "injection": False, "note": ""} for rid in ("M3", "M4")}
    aid = adjudicated(module, c, answer=negative)
    from tests.direct.support import panel_says, serve_package
    for version in range(2, 6):
        as_(module, RESEARCHER, 0)
        assert c.submit_evidence(aid, *package_lists()) == version
        serve_package()
        panel_says(negative)
        as_(module, STRANGER, 0)
        c.adjudicate(aid)
    as_(module, RESEARCHER, 0)
    with pytest.raises(err(module), match="evidence package limit reached"):
        c.submit_evidence(aid, *package_lists())
    assert agreement(c)["resubmittable"] is False


# -- views on unknown ids never revert -------------------------------------------------

def test_unknown_views_are_empty_envelopes(module, c):
    assert json.loads(c.get_agreement("nope")) == {
        "schema_version": 1, "found": False, "agreement_id": "nope"}
    assert json.loads(c.get_verdict("nope"))["found"] is False
    assert json.loads(c.get_requirements("nope"))["found"] is False
    assert json.loads(c.get_sources("nope"))["found"] is False
    assert json.loads(c.get_evidence("nope", 1))["found"] is False
    assert json.loads(c.get_receipt("nope", 1))["found"] is False
    assert c.is_qualified("nope") is False
    assert c.get_terms_hash("nope") == ""
    assert c.get_claimable(STRANGER) == "0"


def test_verdict_view_before_any_round(module, c):
    funded(module, c)
    v = verdict(c)
    assert v["found"] and v["verdict"] == "" and v["consumable"] is False
    assert v["requirements_met"] == 0 and v["requirements_total"] == 6
    assert v["evidence_version"] == 0 and v["evidence_hash"] == ""
    assert v["evidence_sufficient"] is False and v["finalized"] is False


def test_config_publishes_vocabulary_and_statements(module, c):
    config = json.loads(c.get_config())
    assert config["verdicts"] == ["QUALIFIED", "NOT_QUALIFIED", "INCONCLUSIVE"]
    assert config["findings"] == ["SATISFIED", "NOT_SATISFIED", "UNVERIFIABLE"]
    assert config["requirement_kinds"] == ["ACCESSIBLE", "ROW_COUNT_MIN", "COLUMNS_REQUIRED",
                                           "DEADLINE", "SEMANTIC"]
    assert config["deterministic_kinds"] == ["ACCESSIBLE", "ROW_COUNT_MIN", "COLUMNS_REQUIRED",
                                             "DEADLINE"]
    assert config["source_kinds"] == ["DATASET", "METHODOLOGY", "ANALYSIS", "PUBLICATION",
                                      "REPOSITORY", "RECORD"]
    assert config["evidence_hosts"] == ["raw.githubusercontent.com", "zenodo.org"]
    assert config["caps"]["max_requirements"] == 12
    assert config["caps"]["max_sources"] == 8
    assert config["caps"]["max_packages"] == 5
    assert config["caps"]["source_bytes_examined"] == 4000000
    assert "EVIDENCE_CONTRADICTORY" in config["reason_codes"]
    for key in ("equivalence", "deterministic_responsibilities", "failure_policy"):
        assert len(config[key]) > 100
    assert sent() == []
