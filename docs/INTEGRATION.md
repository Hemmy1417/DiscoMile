# Integrating Discovery-Milestone

A downstream Intelligent Contract consumes Discovery-Milestone through one
view and a handful of field checks. It needs no web access, no prompts, no
equivalence principle, and no knowledge of how research documents were
interpreted.

## 1. The read

```python
# inside the consumer's own write method
import json
import genlayer as gl
from genlayer.types import *

adjudicator = gl.get_contract_at(Address(DISCOVERY_MILESTONE_ADDRESS))
verdict = json.loads(adjudicator.view().get_verdict(agreement_id))
```

`get_verdict` returns:

```json
{
  "schema_version": 1,
  "found": true,
  "agreement_id": "DM-001",
  "sponsor": "0x1111111111111111111111111111111111111111",
  "researcher": "0x2222222222222222222222222222222222222222",
  "status": "RELEASED",
  "verdict": "QUALIFIED",
  "requirements_met": 6,
  "requirements_total": 6,
  "deadline_met": true,
  "evidence_sufficient": true,
  "evidence_version": 1,
  "qualified_version": 1,
  "evidence_hash": "6b8a...",
  "record_digest": "9c3d...",
  "deadline": "2026-12-01T23:59:59Z",
  "terms_version": 1,
  "terms_hash": "0f1e...",
  "reward_atto": "50000000000000000",
  "escrow_atto": "0",
  "released_atto": "50000000000000000",
  "reclaimed_atto": "0",
  "qualified": true,
  "released": true,
  "resubmittable": false,
  "finalized": true,
  "consumable": true
}
```

A typed shortcut exists for the simplest gate: `is_qualified(agreement_id)`
returns a boolean.

## 2. The gate

| Check | Why |
|---|---|
| `found` is true | the agreement exists |
| `terms_hash` equals the hash the consumer agreed to (computed offline from the agreed terms, or recorded when the agreement was created) | the agreement cannot be pointed at different terms |
| `sponsor` and `researcher` are the expected parties | the agreement is the one between the parties the consumer expects |
| `consumable` is true | a verdict exists for the latest package; a pending package is never a basis for action |
| then switch on `verdict` | the consumer's own rules decide what the verdict changes; `requirements_met / requirements_total` and `evidence_sufficient` support graded rules; `released` means the reward has been credited to the researcher's claimable balance (pulled with `claim()`) |

Record `evidence_version` (and `evidence_hash`, `record_digest`) next to
whatever the consumer does, so the package that was rewarded or refused is
auditable later through `get_evidence` and `get_receipt`.

`examples/consumer.py` shows the gate and three consumers.

## 3. Three consumers, one primitive

| Consumer | Rule | What the primitive provides |
|---|---|---|
| Research grant, tranche by tranche | release the next tranche on `QUALIFIED`, close the grant on `NOT_QUALIFIED`, wait on `INCONCLUSIVE` | a three-valued verdict with resubmission semantics and a hard deadline |
| Reproducibility bounty | the bounty's own escrow unlocks only on `QUALIFIED` for an agreement whose requirements are the reproduction artifacts (dataset, code, methodology) | a consensus-backed delivery decision; the bounty keeps its money arithmetic |
| Open-science scoring (competitions, maintenance, research DAO contributions) | score a delivery by `requirements_met`, `evidence_sufficient` and the per-requirement findings | the receipt: one finding per requirement, every source's outcome and facts, fixed reason codes |

Other consumers with the same shape: ecosystem research funds, collaborative
research programs verifying individual or team milestones, prize
committees. None re-implements evidence interpretation, and none needs the
adjudication primitive to change: only the Discovery Agreement changes.

## 4. Opening an agreement from a consumer contract

The sponsor is whoever calls `create_agreement`. A consumer contract that
wants to own the agreement calls the writes from its own write method:

```python
adjudicator = gl.get_contract_at(Address(DISCOVERY_MILESTONE_ADDRESS))
adjudicator.emit(on="accepted").create_agreement(
    agreement_id, researcher, title, objective, deadline, reward_atto,
    source_ids, source_kinds, source_descriptions,
    requirement_ids, requirement_kinds, requirement_criteria,
    requirement_sources, requirement_params)
```

Emitted calls execute after the current transaction; the consumer reads
`get_agreement` later to learn `terms_hash`, or computes it offline (section
6). Funding is a payable write of exactly the reward from the sponsor's
address; the researcher commits packages; anyone cranks `adjudicate` and,
after `QUALIFIED`, `release_reward`; the researcher pulls its balance with
`claim()` (`get_claimable(address)` shows what is waiting).

Alternatively an externally owned account sponsors the agreement and the
consumer pins that account as `sponsor` plus the `terms_hash` it expects.
Either way the consumer trusts the frozen terms, not the caller.

## 5. Writing an agreement that adjudicates well

- Put every fact the data can settle into a deterministic kind:
  `ROW_COUNT_MIN` for "at least N observations", `COLUMNS_REQUIRED` for
  "carries these fields", `ACCESSIBLE` for "publicly released", `DEADLINE`
  for "before the date". Those are decided by code and never rotate.
- Write semantic criteria as checks a reader can make against a document,
  and name that document as the requirement's `source_id`: "the methodology
  describes the assay protocol, the validation procedure and the replicate
  policy", bound to the methodology source, not "the methodology is sound".
  A bound document that cannot be examined makes the requirement
  `UNVERIFIABLE` by code; leave `source_id` empty only for criteria that
  genuinely span every document.
- Make cross-source consistency explicit when it matters: "the observation
  count the analysis states is consistent with the dataset facts" puts the
  code-parsed count in front of the panel as an authoritative fact.
- Never ask whether the science is correct. The prompt refuses that
  framing and the answer will be `UNVERIFIABLE`.

## 6. What not to do

- Do not act on `status == "ADJUDICATED"` alone; read `verdict`.
  `INCONCLUSIVE` and `NOT_QUALIFIED` are consumable outcomes that release
  nothing, and both may be followed by a resubmission (`resubmittable`).
- Do not skip the `terms_hash` check. An agreement id is chosen by its
  creator; only the hash proves which terms were adjudicated.
- Do not treat `ACCEPTED` as final. Wait for the `adjudicate` transaction
  to reach protocol `FINALIZED`, or read from a finalized context.
- Do not read requirement `note` fields as consensus facts. They are the
  leader's bounded text. The compared record is `verdict`, `deadline_met`,
  every requirement `finding`, and per source `status`, `hash_match`,
  `byte_count`, `row_count` and `column_count`.

## 7. Offline recomputation

Canonical JSON everywhere: `json.dumps(obj, sort_keys=True,
separators=(",", ":"))`, UTF-8, sha256 hex.

| Hash | Over |
|---|---|
| `terms_hash` | `{terms_version: 1, agreement_id, sponsor, researcher, title, objective, deadline, reward_atto, sources: [{source_id, kind, description}], requirements: [{requirement_id, kind, criterion, source_id, param}]}` - addresses lowercase 0x hex, `reward_atto` a decimal string, deadline normalized |
| `evidence_hash` | `{agreement_id, version, sources: [{source_id, url, content_hash}]}` in agreement source order |
| `record_digest` | `{agreement_id, version, evidence_hash, verdict, deadline_met, requirements: [{requirement_id, finding}], sources: [{source_id, status, hash_match, byte_count, row_count, column_count}], reason_codes}` |
| `content_hash` | the exact bytes at the committed location |

`tests/direct/test_evidence.py` recomputes all three from the views alone.

## 8. The receipt, for consumers that explain refusals

`get_receipt(agreement_id, version)` returns the verdict, `deadline_met`,
`requirements` (`requirement_id`, `kind`, `finding`, advisory `note`),
`sources` (`source_id`, `kind`, `status`, `hash_match`, `byte_count`,
`row_count`, `column_count`), the examined and excluded counts,
`requirements_met`, `requirements_total`, `evidence_sufficient`,
`contradiction_suspected`, `injection_suspected`, `reason_codes`,
`summary`, `record_digest` and `decided_at`. Reason codes are a fixed
vocabulary (`docs/PROTOCOL.md`, section 8) suitable for switching on; notes
are advisory text.
