# Discovery-Milestone Protocol

The contract is `contracts/discovery_milestone.py`, one canonical
deployable for GenLayer Studio Next (GenVM v0.6). This document is the
protocol it implements: the agreement, the evidence package, the round, the
verdict, the money, the views. Every field name below is the name in the
code and in the views.

## 1. Parties and roles

| Role | Fixed at | Can |
|---|---|---|
| Sponsor | `create_agreement` (the caller) | fund the agreement; reclaim the escrow after the deadline when nothing qualified; cancel an unfunded draft |
| Researcher | `create_agreement` (named by the sponsor) | commit evidence packages; pull a released reward |
| Anyone | - | crank `adjudicate` on a pending package; crank `release_reward` after `QUALIFIED`; read every view |

There is no owner, no admin and no upgrade path. A party is an address; the
contract never looks up identities.

## 2. Lifecycle

```text
 create_agreement (sponsor)          fund_agreement (sponsor, = reward)
   DRAFT ------------------------------> FUNDED
     |                                     |
     | sponsor_reclaim                     | submit_evidence (researcher, package v1)
     v                                     v
 CANCELLED                            UNDER_REVIEW <------------------------------+
                                           |                                      |
                                           | adjudicate (anyone): one consensus   |
                                           | round over package v                 |
                                           v                                      |
                                      ADJUDICATED  verdict QUALIFIED | NOT_QUALIFIED | INCONCLUSIVE
                                           |                                      |
   QUALIFIED: release_reward (anyone) -> RELEASED                                 |
             (terminal; the reward is credited to the researcher's                |
              claimable balance)                                                  |
                                           |                                      |
   NOT_QUALIFIED / INCONCLUSIVE: submit_evidence (researcher) -- next package ----+
                                           |
   FUNDED | ADJUDICATED without QUALIFIED, after the deadline:
             sponsor_reclaim (sponsor) -> RECLAIMED
             (terminal; the escrow is credited to the sponsor's claimable balance)

   Any address with a claimable balance: claim() -> the one transfer out.
```

| Status | Meaning | Who moves it next |
|---|---|---|
| `DRAFT` | Terms frozen, nothing escrowed. | Sponsor: `fund_agreement` or `sponsor_reclaim` (cancel). |
| `FUNDED` | Exactly the reward is escrowed. | Researcher: `submit_evidence`. Sponsor: `sponsor_reclaim` after the deadline. |
| `UNDER_REVIEW` | A package awaits its one round. | Anyone: `adjudicate`. Nobody else - the sponsor cannot reclaim during review. |
| `ADJUDICATED` | A verdict is recorded for the latest package. | `QUALIFIED`: anyone: `release_reward`. Otherwise: researcher: `submit_evidence` (resubmission); sponsor: `sponsor_reclaim` after the deadline. |
| `RELEASED` | The reward was credited to the researcher's claimable balance. Terminal. | The researcher: `claim()` pulls the balance (not an agreement transition). |
| `RECLAIMED` | The escrow was credited to the sponsor's claimable balance. Terminal. | The sponsor: `claim()`. |
| `CANCELLED` | An unfunded draft was withdrawn. Terminal. | Nobody. |

A timely package is always adjudicated before the sponsor can exit: the
sponsor cannot reclaim while a package is under review, and anyone can crank
the round. An absent researcher cannot strand the reward either: a released
credit waits in the ledger until its owner pulls it.

## 3. The Discovery Agreement (frozen terms)

`create_agreement(agreement_id, researcher, title, objective, deadline,
reward_atto, source_ids, source_kinds, source_descriptions, requirement_ids,
requirement_kinds, requirement_criteria, requirement_sources,
requirement_params) -> terms_hash`

| Term | Rule |
|---|---|
| `agreement_id` | 1..64 characters of `A-Z a-z 0-9 . _ -`; unique |
| `researcher` | a 0x address, not the sponsor, not zero |
| `title`, `objective` | single-line printable text, 120 and 600 characters |
| `deadline` | `YYYY-MM-DD` (end of that UTC day) or `YYYY-MM-DDTHH:MM:SSZ`; must be after the transaction clock at creation |
| `reward_atto` | decimal string of atto, 10^15..10^21 |
| sources | 1..8 entries: `source_id` (1..32 identifier characters, unique), `kind` in `DATASET, METHODOLOGY, ANALYSIS, PUBLICATION, REPOSITORY, RECORD`, `description` (240 characters) |
| requirements | 1..12 entries: `requirement_id` (unique), `kind` (section 4), `criterion` (600 characters), `source_id` (the declared source the kind examines; for `SEMANTIC`, the document it is judged over, or empty for every document), `param` (the kind's parameter) |

`terms_hash` is sha256 over the canonical JSON of every term (section 9).
Nothing in the agreement changes afterwards.

## 4. Requirement kinds

Five kinds, four of them decided by contract code from the committed bytes
and the transaction clock, one judged by the validator panel.

| Kind | Examines | `param` | Finding |
|---|---|---|---|
| `ACCESSIBLE` | one declared source | none | `SATISFIED` when the source is fetched with the committed bytes; `NOT_SATISFIED` when it is missing (404) or empty; `UNVERIFIABLE` when it is unreachable, oversized or hash-mismatched |
| `ROW_COUNT_MIN` | one `DATASET` source | a record count, 1..10^9 | `SATISFIED` when the dataset holds at least that many records (section 6); `NOT_SATISFIED` otherwise; `UNVERIFIABLE` when the dataset was not examined |
| `COLUMNS_REQUIRED` | one `DATASET` source | 1..64 distinct column names, comma-separated | `SATISFIED` when every name is a header column of the dataset; `NOT_SATISFIED` when one is absent; `UNVERIFIABLE` when the dataset was not examined |
| `DEADLINE` | the package's `deadline_met` | none | `SATISFIED` when the package was committed on time, else `NOT_SATISFIED` |
| `SEMANTIC` | the document named by `source_id` (or every examined text source when empty), plus the dataset facts | none | the panel's finding (section 7), with a contradiction or injection flag forcing `UNVERIFIABLE`; when the named document was committed but could not be examined, `UNVERIFIABLE` by code, no model involved |

A `DATASET` source is examined by code and never shown to the panel; its
facts (record count, column names, byte count, hash) are. Every other kind
of source is a text document the panel reads. A late package is
`NOT_QUALIFIED` by the verdict rule whether or not the agreement lists a
`DEADLINE` requirement; listing one makes the deadline count among the
requirements a consumer sees as `requirements_met / requirements_total`.

## 5. The evidence package

`submit_evidence(agreement_id, source_ids, urls, content_hashes) -> version`

The researcher commits, for every declared source exactly once, one
immutable location and the sha256 of the bytes at it. Only these locations
are admitted, character for character:

```text
https://raw.githubusercontent.com/<owner>/<repo>/<40-hex commit>/<path>
https://zenodo.org/records/<digits>/files/<filename>?download=1
```

A commit-pinned raw file and a Zenodo record file are immutable by
construction (a new Zenodo version is a new record id); the hash proves the
bytes on top of that. The package is stored in agreement source order with
its `evidence_hash` (section 9), `committed_at` (the transaction clock) and
`deadline_met`, decided here and frozen: `committed_at <= deadline`. Up to
five packages per agreement; a package is allowed while `FUNDED` (the
first) or `ADJUDICATED` without `QUALIFIED` (a resubmission). Packages are
append-only; a prior package and its receipt never change.

## 6. The round

`adjudicate(agreement_id)` runs exactly one `gl.vm.run_nondet` over the
pending package. The leader and every validator execute the same procedure
from their own vantage:

1. **Fetch every committed source** with `gl.nondet.web.get`. Outcomes:
   `NOT_FOUND` (404), `UNAVAILABLE` (any other non-2xx, or an exception),
   `EMPTY` (zero bytes), `TOO_LARGE` (over 4,000,000 bytes, checked before
   hashing), `HASH_MISMATCH` (sha256 of the body differs from the committed
   hash), else `EXAMINED`. Anything but `EXAMINED` is excluded: its bytes
   never enter a fact or a prompt.
2. **Parse the dataset facts in code** for every examined `DATASET`
   source: records are newline-delimited, a newline inside a double-quoted
   field does not end a record, a CR before LF is ignored, a UTF-8
   byte-order mark is ignored, the first record is the header, empty
   records are not counted. The facts are the record count (records after
   the header), the header column names (trimmed, quotes stripped, at most
   64) and the byte count.
3. **Decide the deterministic requirements** (section 4) from the source
   outcomes, the facts, the frozen parameters and `deadline_met`.
4. **Decide in code which semantic requirements can be judged at all.** A
   `SEMANTIC` requirement bound to a `source_id` whose document was not
   examined is `UNVERIFIABLE` by policy - missing evidence is never evidence
   of absence - and is not put to the panel.
5. **One synthesis prompt** for the remaining `SEMANTIC` requirements, over
   this node's own examined text documents (each capped at 8,000
   characters), with the agreement's title and objective, the dataset
   facts, each requirement's `source_id`, and the list of committed sources
   that were excluded (with their outcome) as context. The prompt shell is
   a fixed constant; every variable input travels inside one canonical JSON
   blob declared untrusted. With no examined text document the prompt is
   skipped on every node and the semantic requirements are `UNVERIFIABLE`
   by policy.
6. **Assemble the result in code**: verdict, counts, evidence sufficiency,
   reason codes, summary.

A validator ratifies the leader's result only if it passes the structural
gate and its own reproduction agrees on the decision fields
(`docs/CONSENSUS.md`). The ratified text is parsed again at the contract
boundary before it touches state.

## 7. The panel's answer

The synthesis prompt returns, per semantic requirement:

```json
{"<requirement_id>": {"finding": "SATISFIED" | "NOT_SATISFIED" | "UNVERIFIABLE",
                      "contradiction": true | false, "injection": true | false,
                      "note": "<at most 240 characters>"}}
```

The panel is told which document each requirement is judged over, and
which committed sources were excluded and why, so that an excluded
document is read as missing evidence rather than as a missing deliverable.
Normalization is fixed and identical on every node: a non-object answer is
a model error that forces leader rotation; a missing or off-vocabulary entry
is `UNVERIFIABLE`, never a positive finding; `contradiction` (the evidence
disagrees with itself or with the dataset facts on a fact the requirement
depends on) or `injection` (a document carries instructions aimed at the
adjudicator) forces `UNVERIFIABLE` and is recorded on the receipt. The panel
judges whether the committed documents demonstrate the commitment as
written; it is told explicitly that it is not judging whether the science is
correct, whether a discovery is true, or whether the work would pass peer
review.

## 8. Verdict, counts and reason codes

The verdict is a pure function of `deadline_met` and the findings:

```text
not deadline_met                 -> NOT_QUALIFIED
any finding NOT_SATISFIED        -> NOT_QUALIFIED
any finding UNVERIFIABLE         -> INCONCLUSIVE
otherwise                        -> QUALIFIED
```

`requirements_met` counts `SATISFIED` findings; `requirements_total` is the
number of requirements; `evidence_sufficient` is true only when every source
was examined and no finding is `UNVERIFIABLE`. Reason codes are a fixed
vocabulary in a fixed order:

| Code | When |
|---|---|
| `ALL_REQUIREMENTS_SATISFIED` | no other verdict code applies |
| `DEADLINE_MISSED` | the package was late |
| `REQUIREMENT_NOT_SATISFIED` | at least one `NOT_SATISFIED` |
| `REQUIREMENT_UNVERIFIABLE` | at least one `UNVERIFIABLE` |
| `EVIDENCE_NOT_FOUND`, `EVIDENCE_UNAVAILABLE`, `EVIDENCE_EMPTY`, `EVIDENCE_HASH_MISMATCH`, `EVIDENCE_TOO_LARGE` | a source had that outcome |
| `EVIDENCE_CONTRADICTORY` | the panel flagged a contradiction |
| `INJECTION_SUSPECTED` | the panel flagged an injection |

The receipt (`get_receipt`) carries the verdict, `deadline_met`, one row
per requirement (`requirement_id`, `kind`, `finding`, advisory `note`), one
row per source (`source_id`, `kind`, `status`, `hash_match`, `byte_count`,
`row_count`, `column_count`), the counts, the flags, the reason codes, the
summary, `record_digest` and `decided_at`.

## 9. Hashes

Canonical JSON everywhere: keys sorted, separators `,` and `:`, UTF-8,
sha256 hex.

| Hash | Over |
|---|---|
| `terms_hash` | `{terms_version: 1, agreement_id, sponsor, researcher, title, objective, deadline, reward_atto, sources: [{source_id, kind, description}], requirements: [{requirement_id, kind, criterion, source_id, param}]}` - addresses lowercase 0x hex, `reward_atto` a decimal string, the deadline normalized |
| `evidence_hash` | `{agreement_id, version, sources: [{source_id, url, content_hash}]}` in agreement source order |
| `record_digest` | `{agreement_id, version, evidence_hash, verdict, deadline_met, requirements: [{requirement_id, finding}], sources: [{source_id, status, hash_match, byte_count, row_count, column_count}], reason_codes}` |
| `content_hash` | sha256 of the exact bytes at the committed location |

Every one of them recomputes offline from the views alone
(`tests/direct/test_evidence.py` does exactly that).

## 10. Money

- `fund_agreement` is payable and accepts exactly `reward_atto`; the whole
  obligation is reserved at acceptance, never at settlement. The contract's
  `escrow_total_atto` is the sum of live agreement escrows and
  `ledger_total_atto` the sum of credited, unclaimed balances; a released,
  reclaimed or cancelled agreement holds nothing itself.
- `release_reward` is permissionless and credits the researcher the sponsor
  named at creation - never the caller - once the latest verdict is
  `QUALIFIED`. The agreement settles (`RELEASED`, escrow zeroed,
  `released_atto` recorded) and the amount moves to the researcher's
  claimable balance; a second call finds nothing to credit.
- `sponsor_reclaim` cancels an unfunded draft at any time; for a funded
  agreement it credits the escrow back to the sponsor only after the
  deadline, only when the latest verdict is not `QUALIFIED`, and never while
  a package is under review.
- `claim()` is the one path value leaves the contract: the caller's whole
  claimable balance, zeroed before the transfer is emitted through the EVM
  proxy `_Payee`. It has no clock and no verdict in it - those gates ran
  when the balance was credited. The split is deliberate: on Studio Next a
  write that emits a transfer needs the message allocations its fee
  simulation derives, and that simulation runs with a predefined
  transaction datetime, so a transfer inside a clock-gated write can never
  be allocated (`docs/DEPLOYMENT.md`).
- No owner, no admin, no other value path. The reward amount never enters
  the nondeterministic round.

## 11. Views

Views return canonical JSON strings or typed scalars, never revert on an
unknown id (they answer `{"found": false}`), and read bounded slices only.

| View | Returns |
|---|---|
| `get_agreement(id)` | the agreement record: parties, status, verdict, terms, counts, timestamps, `qualified`, `released`, `resubmittable` |
| `get_sources(id)`, `get_requirements(id)` | the frozen sources and requirements |
| `get_evidence(id, version)` | one committed package: sources with locations and hashes, `committed_at`, `deadline_met`, `evidence_hash`, `status` |
| `get_receipt(id, version)` | the decision record of one package (section 8) |
| `get_verdict(id)` | the compact result a consumer switches on: `verdict`, `requirements_met`, `requirements_total`, `deadline_met`, `evidence_sufficient`, `evidence_version`, `evidence_hash`, `record_digest`, `terms_hash`, parties, money fields, `qualified`, `released`, `resubmittable`, `finalized`, `consumable` |
| `is_qualified(id)` | bool |
| `get_terms_hash(id)` | str, `""` for unknown agreements |
| `get_claimable(address)` | the address's claimable balance in atto, as a decimal string |
| `get_agreements_by(address, role, offset, limit)` | agreement ids where the address is `sponsor` or `researcher`, paged (limit capped at 50) |
| `get_config()` | vocabularies, hosts, caps, escrow and ledger totals, the equivalence / deterministic-responsibility / failure-policy statements |

`consumable` (and `finalized`) is true only when a receipt exists for the
latest package and no package is pending; a pending resubmission makes the
agreement non-consumable until its round lands.
