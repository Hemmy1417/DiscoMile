# v0.3.0
# { "Depends": "py-genlayer:5jycge4q8k23462jtb0b9fyey1s9qz928sz2nbrd9mg4sxqg2qng" }

# Three downstream consumers on one gate. None of them fetches anything,
# prompts anything or knows how a methodology was read: each reads
# Discovery-Milestone's get_verdict, applies the gate in docs/INTEGRATION.md
# section 2, and then applies its own rule. This file is an illustration of
# the integration shape, not a deployed contract; it compiles and its gate
# logic is the same the tests exercise against the real views.

import genlayer as gl
from genlayer.types import *

import json


DISCOVERY_MILESTONE = "0x0000000000000000000000000000000000000000"   # the deployment of record


def gate(adjudicator, agreement_id: str, expected_terms_hash: str,
         expected_sponsor: str, expected_researcher: str) -> dict:
    """The consumer's gate: the agreement exists, is the agreement between
    the expected parties under the expected terms, and has a consumable
    verdict for its latest evidence package. Returns the verdict payload
    or raises."""
    verdict = json.loads(adjudicator.view().get_verdict(agreement_id))
    if not verdict.get("found"):
        raise gl.vm.UserError("[EXPECTED] unknown agreement")
    if verdict["terms_hash"] != expected_terms_hash:
        raise gl.vm.UserError("[EXPECTED] terms differ from the agreed terms")
    if verdict["sponsor"] != expected_sponsor.lower() \
            or verdict["researcher"] != expected_researcher.lower():
        raise gl.vm.UserError("[EXPECTED] parties differ from the expected parties")
    if not verdict["consumable"]:
        raise gl.vm.UserError("[EXPECTED] no consumable verdict yet")
    return verdict


class TrancheGrant(gl.contract.Contract):
    """A research grant paid tranche by tranche. Each tranche is one
    Discovery Agreement; the next tranche opens on QUALIFIED, the grant
    closes on NOT_QUALIFIED, and INCONCLUSIVE waits for a resubmission.
    Money arithmetic stays in this contract."""

    terms_hashes: gl.storage.TreeMap[str, str]     # agreement_id -> agreed terms hash
    tranche_open: gl.storage.TreeMap[str, bool]    # agreement_id -> next tranche opened
    closed: bool
    sponsor: str
    researcher: str

    def __init__(self, sponsor: str, researcher: str):
        self.sponsor = sponsor.lower()
        self.researcher = researcher.lower()
        self.closed = False

    @gl.public.write
    def settle_tranche(self, agreement_id: str) -> str:
        if self.closed:
            raise gl.vm.UserError("[EXPECTED] grant closed")
        adjudicator = gl.get_contract_at(Address(DISCOVERY_MILESTONE))
        verdict = gate(adjudicator, agreement_id, self.terms_hashes[agreement_id],
                       self.sponsor, self.researcher)
        if verdict["verdict"] == "QUALIFIED":
            self.tranche_open[agreement_id] = True
            return json.dumps({"tranche": "opened", "evidence_version": verdict["evidence_version"],
                               "record_digest": verdict["record_digest"]})
        if verdict["verdict"] == "NOT_QUALIFIED" and not verdict["resubmittable"]:
            self.closed = True
            return json.dumps({"tranche": "closed", "reason": "NOT_QUALIFIED and no resubmission left"})
        return json.dumps({"tranche": "waiting", "verdict": verdict["verdict"],
                           "resubmittable": verdict["resubmittable"]})


class ReproducibilityBounty(gl.contract.Contract):
    """A bounty for reproducing a published result. The bounty's own escrow
    unlocks only on QUALIFIED for an agreement whose requirements are the
    reproduction artifacts. The bounty never reads a document."""

    agreement_id: str
    terms_hash: str
    sponsor: str
    researcher: str
    unlocked: bool

    def __init__(self, agreement_id: str, terms_hash: str, sponsor: str, researcher: str):
        self.agreement_id = agreement_id
        self.terms_hash = terms_hash
        self.sponsor = sponsor.lower()
        self.researcher = researcher.lower()
        self.unlocked = False

    @gl.public.write
    def unlock(self) -> bool:
        adjudicator = gl.get_contract_at(Address(DISCOVERY_MILESTONE))
        verdict = gate(adjudicator, self.agreement_id, self.terms_hash,
                       self.sponsor, self.researcher)
        if verdict["verdict"] != "QUALIFIED" or not verdict["evidence_sufficient"]:
            return False
        self.unlocked = True
        return True


class OpenScienceScoreboard(gl.contract.Contract):
    """Competition or maintenance scoring from the per-requirement findings:
    partial delivery earns partial credit, and evidence sufficiency is a
    multiplier. The scoreboard consumes the receipt as data."""

    scores: gl.storage.TreeMap[str, u256]          # agreement_id -> score out of 100

    def __init__(self):
        pass

    @gl.public.write
    def score(self, agreement_id: str, terms_hash: str, sponsor: str, researcher: str) -> int:
        adjudicator = gl.get_contract_at(Address(DISCOVERY_MILESTONE))
        verdict = gate(adjudicator, agreement_id, terms_hash, sponsor, researcher)
        total = int(verdict["requirements_total"])
        met = int(verdict["requirements_met"])
        points = (100 * met) // total if total > 0 else 0
        if not verdict["evidence_sufficient"]:
            points = points // 2
        if not verdict["deadline_met"]:
            points = points // 2
        self.scores[agreement_id] = u256(points)
        return points
