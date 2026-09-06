"""Money: the full reward is reserved at funding, every path conserves atto,
credits can only ever go to the researcher the sponsor named (after
QUALIFIED) or back to the sponsor (after the deadline when nothing
qualified), value leaves only through the one pull payment claim(), nothing
pays twice, and no terminal state resurrects."""

import json

import pytest

from tests.direct.conftest import RESEARCHER, SPONSOR, STRANGER
from tests.direct.support import (
    AGREEMENT, REWARD, SEMANTIC_SATISFIED, adjudicated, agreement, as_, conserve,
    create, err, funded, package_lists, panel_says, sent, serve_package,
    set_clock, submitted, verdict,
)

NEGATIVE = {rid: {"finding": "NOT_SATISFIED", "contradiction": False, "injection": False,
                  "note": ""} for rid in ("M3", "M4")}
UNSURE = {rid: {"finding": "UNVERIFIABLE", "contradiction": False, "injection": False,
                "note": ""} for rid in ("M3", "M4")}


def release(module, c, who=STRANGER, aid=AGREEMENT):
    as_(module, who, 0)
    return json.loads(c.release_reward(aid))


def reclaim(module, c, who=SPONSOR, aid=AGREEMENT):
    as_(module, who, 0)
    return json.loads(c.sponsor_reclaim(aid))


def pull(module, c, who):
    as_(module, who, 0)
    return json.loads(c.claim())


def claimable(c, who):
    return int(c.get_claimable(who))


def config(c):
    return json.loads(c.get_config())


# -- reservation, credit, pull -------------------------------------------------------

def test_reward_is_reserved_in_full_at_funding(module, c):
    funded(module, c)
    ag = agreement(c)
    assert ag["escrow_atto"] == str(REWARD)
    assert config(c)["escrow_total_atto"] == str(REWARD)
    assert config(c)["ledger_total_atto"] == "0"
    conserve(c)
    assert sent() == []


def test_qualified_credits_the_researcher_and_the_researcher_pulls_exactly_once(module, c):
    adjudicated(module, c)
    out = release(module, c)
    assert out == {"credited_atto": str(REWARD), "to": RESEARCHER}
    assert sent() == []                                   # a credit moves no value
    assert claimable(c, RESEARCHER) == REWARD
    ag = agreement(c)
    assert ag["status"] == "RELEASED" and ag["escrow_atto"] == "0"
    assert ag["released_atto"] == str(REWARD) and ag["settled_at"] == "2026-09-06T12:00:00Z"
    assert ag["qualified"] is True and ag["released"] is True
    assert c.is_qualified(AGREEMENT) is True
    assert verdict(c)["released"] is True and verdict(c)["finalized"] is True
    assert config(c)["escrow_total_atto"] == "0" and config(c)["ledger_total_atto"] == str(REWARD)
    conserve(c)
    with pytest.raises(err(module), match="releasable only after QUALIFIED"):
        release(module, c)                                # settles once

    assert pull(module, c, RESEARCHER) == {"claimed_atto": str(REWARD), "to": RESEARCHER}
    assert sent() == [(RESEARCHER, REWARD)]
    assert claimable(c, RESEARCHER) == 0
    assert config(c)["ledger_total_atto"] == "0"
    conserve(c)
    with pytest.raises(err(module), match="nothing claimable"):
        pull(module, c, RESEARCHER)
    assert sent() == [(RESEARCHER, REWARD)]


def test_release_is_permissionless_but_only_the_researcher_can_pull(module, c):
    adjudicated(module, c)
    release(module, c, who=SPONSOR)
    assert claimable(c, RESEARCHER) == REWARD
    for who in (SPONSOR, STRANGER):
        with pytest.raises(err(module), match="nothing claimable"):
            pull(module, c, who)
    assert sent() == []
    pull(module, c, RESEARCHER)
    assert sent() == [(RESEARCHER, REWARD)]


@pytest.mark.parametrize("stage", ["draft", "funded", "under_review", "not_qualified",
                                   "inconclusive"])
def test_nothing_releasable_before_qualified(module, c, stage):
    if stage == "draft":
        create(module, c)
    elif stage == "funded":
        funded(module, c)
    elif stage == "under_review":
        submitted(module, c)
    elif stage == "not_qualified":
        adjudicated(module, c, answer=NEGATIVE)
    else:
        adjudicated(module, c, answer=UNSURE)
    with pytest.raises(err(module), match="releasable only after QUALIFIED"):
        release(module, c)
    for who in (SPONSOR, RESEARCHER, STRANGER):
        with pytest.raises(err(module), match="nothing claimable"):
            pull(module, c, who)
    assert sent() == []
    conserve(c)


def test_credits_accumulate_across_agreements(module, c):
    adjudicated(module, c)
    release(module, c)
    adjudicated(module, c, agreement_id="DM-2")
    release(module, c, aid="DM-2")
    assert claimable(c, RESEARCHER) == 2 * REWARD
    pull(module, c, RESEARCHER)
    assert sent() == [(RESEARCHER, 2 * REWARD)]
    conserve(c)


# -- the sponsor's exit ----------------------------------------------------------------

def test_cancel_a_draft_moves_no_money(module, c):
    create(module, c)
    assert reclaim(module, c) == {"status": "CANCELLED", "reclaimed_atto": "0"}
    assert agreement(c)["status"] == "CANCELLED" and sent() == []
    assert claimable(c, SPONSOR) == 0
    conserve(c)


def test_sponsor_cannot_reclaim_a_funded_agreement_before_the_deadline(module, c):
    funded(module, c)
    with pytest.raises(err(module), match="deadline has not passed"):
        reclaim(module, c)
    set_clock("2026-12-01T23:59:59Z")
    with pytest.raises(err(module), match="deadline has not passed"):
        reclaim(module, c)
    assert agreement(c)["status"] == "FUNDED" and sent() == []
    assert claimable(c, SPONSOR) == 0


def test_sponsor_reclaims_after_the_deadline_when_nothing_was_submitted(module, c):
    funded(module, c)
    set_clock("2026-12-02T00:00:00Z")
    assert reclaim(module, c) == {"status": "RECLAIMED", "reclaimed_atto": str(REWARD)}
    assert sent() == []                                   # credited, not transferred
    assert claimable(c, SPONSOR) == REWARD
    ag = agreement(c)
    assert ag["status"] == "RECLAIMED" and ag["escrow_atto"] == "0"
    assert ag["reclaimed_atto"] == str(REWARD)
    conserve(c)
    with pytest.raises(err(module), match="nothing to reclaim in status RECLAIMED"):
        reclaim(module, c)
    pull(module, c, SPONSOR)
    assert sent() == [(SPONSOR, REWARD)]
    assert claimable(c, SPONSOR) == 0
    conserve(c)


@pytest.mark.parametrize("answer", [NEGATIVE, UNSURE])
def test_sponsor_reclaims_after_the_deadline_when_nothing_qualified(module, c, answer):
    adjudicated(module, c, answer=answer)
    with pytest.raises(err(module), match="deadline has not passed"):
        reclaim(module, c)
    set_clock("2026-12-02T00:00:00Z")
    reclaim(module, c)
    assert claimable(c, SPONSOR) == REWARD and claimable(c, RESEARCHER) == 0
    assert agreement(c)["status"] == "RECLAIMED"
    conserve(c)
    as_(module, RESEARCHER, 0)
    with pytest.raises(err(module), match="does not accept evidence in status RECLAIMED"):
        c.submit_evidence(AGREEMENT, *package_lists())
    with pytest.raises(err(module), match="nothing claimable"):
        pull(module, c, RESEARCHER)
    pull(module, c, SPONSOR)
    assert sent() == [(SPONSOR, REWARD)]


def test_sponsor_cannot_reclaim_while_a_package_is_under_review(module, c):
    submitted(module, c)
    set_clock("2027-01-01T00:00:00Z")
    with pytest.raises(err(module), match="under review; adjudicate it first"):
        reclaim(module, c)
    # The permissionless crank resolves it; a timely package still qualifies.
    serve_package()
    panel_says(SEMANTIC_SATISFIED)
    as_(module, STRANGER, 0)
    c.adjudicate(AGREEMENT)
    with pytest.raises(err(module), match="belongs to the researcher"):
        reclaim(module, c)
    release(module, c)
    pull(module, c, RESEARCHER)
    assert sent() == [(RESEARCHER, REWARD)]


def test_sponsor_cannot_reclaim_after_qualified_or_released(module, c):
    adjudicated(module, c)
    set_clock("2027-01-01T00:00:00Z")
    with pytest.raises(err(module), match="belongs to the researcher"):
        reclaim(module, c)
    release(module, c)
    with pytest.raises(err(module), match="nothing to reclaim in status RELEASED"):
        reclaim(module, c)
    assert claimable(c, SPONSOR) == 0 and claimable(c, RESEARCHER) == REWARD


def test_only_the_sponsor_reclaims(module, c):
    funded(module, c)
    set_clock("2027-01-01T00:00:00Z")
    for who in (RESEARCHER, STRANGER):
        with pytest.raises(err(module), match="only the sponsor reclaims"):
            reclaim(module, c, who=who)
    assert agreement(c)["status"] == "FUNDED"


def test_reclaim_unknown(module, c):
    with pytest.raises(err(module), match="unknown agreement_id"):
        reclaim(module, c, aid="nope")


def test_claim_has_no_clock_and_no_agreement(module, c):
    """The pull payment is gated by nothing but the ledger - the time and
    verdict gates ran when the balance was credited."""
    funded(module, c)
    set_clock("2027-01-01T00:00:00Z")
    reclaim(module, c)
    set_clock("2020-01-01T00:00:00Z")                     # any clock, even a bogus past one
    pull(module, c, SPONSOR)
    assert sent() == [(SPONSOR, REWARD)]


# -- invariants: concurrency and post-terminal actions -----------------------------------

def test_two_agreements_are_independent_and_conserved(module, c):
    other_researcher = "0x3333333333333333333333333333333333333333"
    other_sponsor = "0x4444444444444444444444444444444444444444"
    adjudicated(module, c)                                            # DM-001 qualified
    funded(module, c, agreement_id="DM-B", sender=other_sponsor, researcher=other_researcher,
           reward=2 * REWARD)
    assert config(c)["escrow_total_atto"] == str(3 * REWARD)
    conserve(c)
    release(module, c)
    assert config(c)["escrow_total_atto"] == str(2 * REWARD)
    assert config(c)["ledger_total_atto"] == str(REWARD)
    assert agreement(c, "DM-B")["escrow_atto"] == str(2 * REWARD)
    conserve(c)
    with pytest.raises(err(module), match="only the sponsor reclaims"):
        reclaim(module, c, who=other_sponsor)
    set_clock("2027-01-01T00:00:00Z")
    with pytest.raises(err(module), match="only the sponsor reclaims"):
        reclaim(module, c, who=SPONSOR, aid="DM-B")
    reclaim(module, c, who=other_sponsor, aid="DM-B")
    assert claimable(c, other_sponsor) == 2 * REWARD and claimable(c, RESEARCHER) == REWARD
    assert config(c)["escrow_total_atto"] == "0" and config(c)["ledger_total_atto"] == str(3 * REWARD)
    conserve(c)
    pull(module, c, RESEARCHER)
    pull(module, c, other_sponsor)
    assert sent() == [(RESEARCHER, REWARD), (other_sponsor, 2 * REWARD)]
    assert config(c)["ledger_total_atto"] == "0"
    conserve(c)


def test_no_state_resurrects_after_release(module, c):
    adjudicated(module, c)
    release(module, c)
    pull(module, c, RESEARCHER)
    frozen = c.get_agreement(AGREEMENT)
    set_clock("2027-01-01T00:00:00Z")
    for who, action in (
        (STRANGER, lambda: c.release_reward(AGREEMENT)),
        (SPONSOR, lambda: c.sponsor_reclaim(AGREEMENT)),
        (RESEARCHER, lambda: c.submit_evidence(AGREEMENT, *package_lists())),
        (STRANGER, lambda: c.adjudicate(AGREEMENT)),
        (SPONSOR, lambda: c.fund_agreement(AGREEMENT)),
        (RESEARCHER, lambda: c.claim()),
    ):
        as_(module, who, REWARD)
        with pytest.raises(err(module)):
            action()
        assert c.get_agreement(AGREEMENT) == frozen
    assert sent() == [(RESEARCHER, REWARD)]
    conserve(c)


def test_no_state_resurrects_after_reclaim(module, c):
    adjudicated(module, c, answer=NEGATIVE)
    set_clock("2027-01-01T00:00:00Z")
    reclaim(module, c)
    pull(module, c, SPONSOR)
    frozen = c.get_agreement(AGREEMENT)
    for who, action in (
        (STRANGER, lambda: c.release_reward(AGREEMENT)),
        (SPONSOR, lambda: c.sponsor_reclaim(AGREEMENT)),
        (RESEARCHER, lambda: c.submit_evidence(AGREEMENT, *package_lists())),
        (STRANGER, lambda: c.adjudicate(AGREEMENT)),
        (SPONSOR, lambda: c.claim()),
    ):
        as_(module, who, 0)
        with pytest.raises(err(module)):
            action()
        assert c.get_agreement(AGREEMENT) == frozen
    assert sent() == [(SPONSOR, REWARD)]


def test_cancelled_draft_is_terminal(module, c):
    create(module, c)
    reclaim(module, c)
    as_(module, SPONSOR, REWARD)
    with pytest.raises(err(module), match="not a draft"):
        c.fund_agreement(AGREEMENT)
    with pytest.raises(err(module), match="nothing to reclaim in status CANCELLED"):
        reclaim(module, c)


def test_a_credit_never_exceeds_what_was_escrowed(module, c):
    """The credit is the escrow, which equals the reward - never the reward
    constant read back from the terms."""
    adjudicated(module, c)
    c.agreements[AGREEMENT].reward_atto = module.u256(REWARD * 10)   # tampered terms figure
    release(module, c)
    assert claimable(c, RESEARCHER) == REWARD
    pull(module, c, RESEARCHER)
    assert sent() == [(RESEARCHER, REWARD)]
    conserve(c)


def test_get_claimable_handles_unknown_and_malformed_addresses(module, c):
    assert c.get_claimable(STRANGER) == "0"
    assert c.get_claimable("not-an-address") == "0"
    assert c.get_claimable(RESEARCHER.upper().replace("0X", "0x")) == "0"
