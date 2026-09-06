# Discovery-Milestone - Intelligent Contract Submission Notes

```text
Category:
Standalone Intelligent Contracts

Title:
Discovery-Milestone - Scientific Research Milestone Adjudicator

One-line thesis:
A reusable GenLayer primitive that decides, under validator consensus,
whether a researcher delivered the milestone they committed to - from
evidence committed to immutable, hash-bound locations and judged against
acceptance criteria frozen before the work - and executes the predefined
financial consequence deterministically.

Repository:
https://github.com/Hemmy1417/DiscoMile

Canonical Studio Next address:
0x9c99d7aD196F0d05Aa6eF4D56d78d43b54Ae19AB

Explorer:
Studio Next has no public explorer; read any transaction with
`node scripts/sn.mjs tx <hash>` and any state with the contract's views.

Deployment transaction:
0x7d2001fab501f9e53e0e010bba886c58b0854ea52a859e7ad10fdad1d8a02fbc
(FINALIZED, MAJORITY_AGREE, leader SUCCESS; source commit dd05ab5,
contract blob 4f9fdd0b684a42f0bbd2fbdb99cc4b67c1dc408a, byte-verified sha256 69aca3f555a56673...)

Why GenLayer:
Escrow, the deadline, whether a committed file is there with the committed
bytes, how many records a dataset holds and which columns it carries are
arithmetic and stay in contract code. Whether a methodology describes the
validation procedure it promised, whether an analysis reports results
computed on the released dataset, whether two documents contradict each
other on a fact the milestone depends on - these are judgments over prose
across several documents. A single model behind a backend would make its
operator the authority on whether a researcher gets paid. GenLayer lets one
leader propose and every validator independently re-fetch, re-verify,
re-parse, re-judge and veto. Without GenLayer, one operator, backend or
model would decide whether the reward moves; Discovery-Milestone removes
that single authority.

Consensus:
One gl.vm.run_nondet round per evidence package. Leader and every
validator run the same procedure: fetch every committed source, size-bound
and verify sha256 before any fact or prompt, parse the dataset facts in
code, decide ACCESSIBLE / ROW_COUNT_MIN / COLUMNS_REQUIRED / DEADLINE in
code, judge the SEMANTIC requirements in one synthesis prompt with the
dataset facts as authoritative context, derive the verdict in code.
Compared exactly: verdict, deadline_met, every finding, and per source its
status, hash match, byte count, record count and column count. Notes are
never compared. A structural gate refuses malformed or ungrounded leader
results before reproduction and runs again at the contract boundary on the
ratified text.

Deterministic responsibilities:
Sponsor and researcher identity; terms immutability and hash; escrow of
exactly the reward at funding; the deadline (transaction clock at
commitment); the evidence location grammar; hash binding; dataset facts;
the four deterministic requirement kinds; whether a semantic requirement's
document was examinable; verdict derivation; counts;
evidence sufficiency; reason codes; summary; record digest; credits to the
named researcher only (after QUALIFIED) or the sponsor only (after the
deadline); one ungated pull payment out; every state transition.

Failure policy:
A committed source that cannot be fetched, is missing, is empty, exceeds
the size bound or mismatches its hash is excluded and never read as
satisfying anything; a semantic requirement whose committed document could not be examined, or with no examinable document at all, is
UNVERIFIABLE (INCONCLUSIVE, resubmittable); a record-count or column
requirement over an excluded dataset is UNVERIFIABLE; an ACCESSIBLE
requirement whose source is missing or empty is NOT_SATISFIED; contradictory
evidence is UNVERIFIABLE; a late package is NOT_QUALIFIED; unusable model
output forces leader rotation; validator disagreement writes nothing. Only
QUALIFIED credits the reward, and only its owner can pull a credited
balance.

Reuse:
Tranche-based research grants (open / close / wait on the three verdicts),
reproducibility bounties (unlock on QUALIFIED), open-science scoring
(per-requirement findings and evidence sufficiency). Each reads
get_verdict, pins terms_hash and the parties, applies its own rules -
docs/INTEGRATION.md, examples/consumer.py.

Tests:
468 Direct Mode tests (tests/direct, stub v0.6 harness) - agreement and
package validation, the adjudication matrix, the CSV record counter and the
location grammar, the forged-leader equivalence matrix, evidence integrity,
escrow and ledger conservation, boundary hardening; 48/48 mutants
killed (scripts/mutation_check.py, accept-control green); preflight clean;
genvm-lint AST lint clean; deployment byte-verified.

Live evidence:
Deployment of record 0x9c99d7aD196F0d05Aa6eF4D56d78d43b54Ae19AB; six scenarios driven from the test
wallets, every write FINALIZED with the leader execution result and validator
votes read from the receipts (docs/DEPLOYMENT.md;
deploy/live_scenarios_transcript.json):
- A qualified (DM-LIVE-A-09061902): adjudicate tx
  0x6f424313f4e02989b478c2ee3323d432a67b783a32103e18e6535f696691da44
  -> QUALIFIED 6/6, votes IDLE, AGREE, AGREE, IDLE, AGREE; release_reward by a
  stranger credited the researcher 0.02 GEN; the researcher's claim()
  pulled it (tx 0xe0fbb4853dd2f5e9afff687406cd9e86df27c3a43d5080e242aa6f53f0db9c3d);
  13 refusal walls held.
- B not qualified by code (DM-LIVE-B-09061902): a 9,000-record dataset
  against ROW_COUNT_MIN 10,000; adjudicate tx
  0x757e3fcaae5fd5317ab27a4ac8986954f9c8153f1ba1215ecfbf30b9a71778ed
  -> NOT_QUALIFIED, M1 NOT_SATISFIED by the contract's record counter,
  votes AGREE, DISAGREE, AGREE, IDLE, AGREE; sponsor_reclaim after the deadline ->
  RECLAIMED; the sponsor's claim() pulled the escrow.
- C inconclusive then recovery (DM-LIVE-C-09061902): methodology committed
  under a wrong hash; v1 adjudicate tx
  0xb5863c4d72b2a7037717fb68048605a7d75d8d35c5c37e229516f3da0e2776b2
  -> INCONCLUSIVE (HASH_MISMATCH, M3 UNVERIFIABLE); v2 adjudicate tx
  0x100cba0c35cf43bdeb434f7fba5d591161fca66e4aa0b3b4995e2514fe21f7fb
  -> QUALIFIED; package 1 byte-identical afterwards; RELEASED and pulled.
- D late (DM-LIVE-D-09061902): committed after the deadline -> NOT_QUALIFIED
  with DEADLINE_MISSED although every other requirement was SATISFIED;
  RECLAIMED and pulled.
- E refusal catalog (DM-LIVE-E-09061902): 12 refusals finalized
  on-chain as leader-ERROR receipts with the contract's [EXPECTED] text.
- F contradiction + injection (DM-LIVE-F-09061902): adjudicate tx
  0x772a324aaebd0463ba4037c2badeeaadb1aa1121b8ef7267b213c4d1112cd1d0
  -> INCONCLUSIVE, M4 UNVERIFIABLE, contradiction_suspected True, injection_suspected True; the package did not qualify.

Limitations:
Evidence is read, not executed; the contract is not a peer reviewer and
never decides whether the science is correct; the researcher chooses which
documents to commit; two evidence hosts (commit-pinned GitHub raw files,
Zenodo record files); dataset facts are record and column counts of a CSV
with a header; honest validators can disagree on borderline criteria, which
surfaces as rotation, never as a verdict; local semantic tooling (genvm-lint
check, gltest) cannot target this runner, so the byte-verified deployment
and the live scenarios are the semantic gate.
```

## Portal description

Discovery-Milestone is a standalone GenLayer Intelligent Contract that
adjudicates whether a researcher delivered the milestone they committed to.
A sponsor freezes a Discovery Agreement - the research objective, the
evidence sources the researcher must produce, milestone requirements with
acceptance criteria, a deadline and a reward - and escrows the reward; the
researcher commits an evidence package of immutable, hash-bound locations
(a dataset, a methodology, an analysis, a publication). Every validator
re-fetches those sources, verifies the hashes, parses the dataset facts in
code, decides the objective requirements in code and judges the semantic
ones over the documents, and the contract derives QUALIFIED, NOT_QUALIFIED
or INCONCLUSIVE deterministically from the findings and a deadline taken
from the transaction clock. It is not an AI peer reviewer: it decides
whether the evidence demonstrates the agreed commitment, never whether the
science is correct. Only QUALIFIED credits the predefined reward to the
predefined researcher; the sponsor reclaims after the deadline otherwise;
each party pulls its balance through the contract's single transfer path.
Grant programs, reproducibility bounties and research DAOs consume the
verdict through one view.
