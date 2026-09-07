<p align="center"><img src="docs/logo.svg" width="140" alt="Discovery-Milestone"/></p>

# Discovery-Milestone - Scientific Research Milestone Adjudicator

**A reusable GenLayer Intelligent Contract that decides, under validator consensus, whether a researcher delivered the milestone they committed to - from evidence committed to immutable locations and judged against acceptance criteria frozen before the work - and then does the one thing money is allowed to do: credit the predefined reward to the predefined researcher, or the escrow back to the sponsor, on a ledger each party pulls from.**

A sponsor freezes a Discovery Agreement (research objective, the evidence sources the researcher must produce, milestone requirements with acceptance criteria, a deadline, a reward) and escrows exactly the reward. The researcher does the work and commits an evidence package: for every source, an immutable location (a commit-pinned repository file or a Zenodo record file) bound by the sha256 of its bytes. One consensus round per package: every validator re-fetches the sources, verifies the hashes, parses the dataset facts in code, decides the objective requirements in code and judges the semantic ones over the documents, and derives `QUALIFIED` / `NOT_QUALIFIED` / `INCONCLUSIVE` in code from the findings and a deadline taken from the transaction clock. Standalone Intelligent Contract - no frontend, no backend.

Deployment of record: `0x9c99d7aD196F0d05Aa6eF4D56d78d43b54Ae19AB` on GenLayer Studio Next (chain 61997), byte-verified against `contracts/discovery_milestone.py` at commit `dd05ab5b5a70` - `docs/DEPLOYMENT.md`.

## What it is

- **A milestone adjudicator, not a peer reviewer.** It never decides whether a discovery is true or a paper is valid. It decides whether the committed evidence demonstrates the commitment agreed before the work, and the panel is told so explicitly.
- **Facts in code, judgment in consensus.** `ROW_COUNT_MIN`, `COLUMNS_REQUIRED`, `ACCESSIBLE` and `DEADLINE` are decided by contract code from the committed bytes and the transaction clock. `SEMANTIC` requirements name the document they are judged over and are decided by the panel with the code-parsed dataset facts in front of it as authoritative - so an analysis that claims 25,000 observations over a 10,240-row dataset is a contradiction, and a contradiction is `INCONCLUSIVE`, never a reward. A named document that was committed but could not be examined makes its requirement `INCONCLUSIVE` by code: missing evidence is never evidence of absence.
- **Evidence-bound.** Only two location grammars are admitted, character for character: a raw GitHub file pinned to a 40-hex commit, and a Zenodo record file. Both are immutable by construction; the bytes are sha256-bound at commitment and re-verified by every validator before any fact is parsed or any model sees them.
- **A decision primitive with a minimal economic consequence.** Escrow in; on `QUALIFIED` the reward is credited to exactly the named researcher, after the deadline it is credited back to the sponsor otherwise; each party pulls its balance with `claim()`, the contract's only transfer path. Tranches, bonuses and reputation are downstream consumers' business.
- **Consensus on decision fields only.** Validators compare the verdict, the deadline flag, every requirement finding and every source's outcome and facts (status, hash match, byte count, record count, column count); notes are advisory.

## How it works

### For sponsors

1. `create_agreement` with the researcher's address, the objective, 1..8 evidence sources (a `DATASET`, a `METHODOLOGY`, an `ANALYSIS`, a `PUBLICATION` ...), a deadline, the reward in atto, and 1..12 requirements of five kinds. The terms are frozen and hashed.
2. `fund_agreement` with exactly the reward. The whole obligation is reserved now.
3. Wait. Anyone can crank `adjudicate` once the researcher commits a package; anyone can crank `release_reward` after `QUALIFIED`.
4. If nothing qualifies by the deadline, `sponsor_reclaim` credits the escrow back to you - never while a package is under review, never after `QUALIFIED` - and `claim()` pulls it.

### For researchers

1. Do the research. Read the frozen requirements with `get_requirements` and the declared sources with `get_sources`.
2. `submit_evidence` with, for every declared source, an immutable location and the sha256 of its bytes. A late package is recorded as late.
3. Anyone adjudicates. Read `get_verdict` and `get_receipt`.
4. On `NOT_QUALIFIED` or `INCONCLUSIVE` before the deadline, fix and resubmit (up to five packages). On `QUALIFIED`, anyone can credit the reward to your balance, and `claim()` pulls it to your address.

| Verdict | Meaning | Money |
|---|---|---|
| `QUALIFIED` | every requirement `SATISFIED` and the package was on time | the escrow is credited to the researcher's claimable balance |
| `NOT_QUALIFIED` | the package was late, or a requirement is `NOT_SATISFIED` | nothing; resubmittable before the deadline; sponsor reclaims after it |
| `INCONCLUSIVE` | no requirement failed but at least one could not be verified: a source excluded, a document insufficient, or the evidence contradictory | nothing; resubmittable; sponsor reclaims after the deadline |

## Lifecycle

```text
 create_agreement      fund_agreement          submit_evidence          adjudicate (anyone)
 (sponsor)             (sponsor, = reward)     (researcher, 1 package)  one round per package
     |                      |                       |                         |
     v                      v                       v                         v
   DRAFT  ------------>  FUNDED  ------------>  UNDER_REVIEW  ---------->  ADJUDICATED
     |                      |                                              |    |    |
     | sponsor_reclaim      | sponsor_reclaim            QUALIFIED --------+    |    +---- NOT_QUALIFIED / INCONCLUSIVE
     v                      | (after the deadline)       release_reward (anyone)|         submit_evidence (researcher) -> UNDER_REVIEW
 CANCELLED                  v                            -> RELEASED (credited) |         sponsor_reclaim after the deadline -> RECLAIMED (credited)
                        RECLAIMED (credited)
                                                    claim() by any credited address -> the one transfer out
```

| Status | Meaning |
|---|---|
| `DRAFT` | terms frozen, nothing escrowed |
| `FUNDED` | exactly the reward escrowed, awaiting the first package |
| `UNDER_REVIEW` | a package awaits its one consensus round |
| `ADJUDICATED` | a verdict is recorded for the latest package |
| `RELEASED` / `RECLAIMED` / `CANCELLED` | terminal; `RELEASED` and `RECLAIMED` mean the money sits in the party's claimable balance until `claim()` |

## Requirement kinds

| Kind | Decided by | Over |
|---|---|---|
| `ROW_COUNT_MIN` | code | the committed dataset's record count (newline-delimited CSV, quotes honored, header excluded) against the frozen minimum |
| `COLUMNS_REQUIRED` | code | the committed dataset's header against the frozen column list |
| `ACCESSIBLE` | code | whether the named source was fetched with the committed bytes |
| `DEADLINE` | code | whether the package was committed before the deadline (transaction clock) |
| `SEMANTIC` | the validator panel | the document the requirement names (or every examined document), with the dataset facts as authoritative context; a contradiction or injection flag forces `UNVERIFIABLE`; a named document that was committed but could not be examined makes the requirement `UNVERIFIABLE` by code |

## GenLayer consensus functions

| Function | Kind | What runs under consensus |
|---|---|---|
| `adjudicate` | `gl.vm.run_nondet`, one round | leader and every validator: fetch each committed source (`web.get`), size-bound and verify sha256, parse the dataset facts in code, decide the deterministic requirements in code, one JSON synthesis prompt over the examined documents for the `SEMANTIC` requirements, derive the verdict in code; validators veto unless verdict, deadline flag, every finding and every source's outcome and facts agree |

Everything else - creation, funding, commitment, credits, the pull payment, every view - is deterministic.

## Contract

| | |
|---|---|
| Network | GenLayer Studio Next (GenVM v0.6) |
| Chain id | 61997 |
| RPC | `https://studio-next.genlayer.com/api` |
| Address | `0x9c99d7aD196F0d05Aa6eF4D56d78d43b54Ae19AB` |
| Explorer | [contract](https://explorer-studio-dev.genlayer.com/address/0x9c99d7aD196F0d05Aa6eF4D56d78d43b54Ae19AB), [deployment transaction](https://explorer-studio-dev.genlayer.com/tx/0x7d2001fab501f9e53e0e010bba886c58b0854ea52a859e7ad10fdad1d8a02fbc); any hash in `docs/DEPLOYMENT.md` opens at `https://explorer-studio-dev.genlayer.com/tx/<hash>` |
| Source | `contracts/discovery_milestone.py`, byte-verified against the deployment (`docs/DEPLOYMENT.md`) |
| Runner | `py-genlayer:5jycge4q8k23462jtb0b9fyey1s9qz928sz2nbrd9mg4sxqg2qng` |

### Write methods

| Method | Who | Payable | Notes |
|---|---|---|---|
| `create_agreement(id, researcher, title, objective, deadline, reward_atto, source_ids, source_kinds, source_descriptions, requirement_ids, requirement_kinds, requirement_criteria, requirement_sources, requirement_params)` | anyone (becomes the sponsor) | no | freezes the terms; returns `terms_hash` |
| `fund_agreement(id)` | sponsor | yes, exactly `reward_atto` | `DRAFT` -> `FUNDED` |
| `submit_evidence(id, source_ids, urls, content_hashes)` | researcher | no | `FUNDED` or non-qualified `ADJUDICATED` -> `UNDER_REVIEW`; every declared source exactly once; records `deadline_met` from the transaction clock; returns the version |
| `adjudicate(id)` | anyone | no | the consensus round; `UNDER_REVIEW` -> `ADJUDICATED` |
| `release_reward(id)` | anyone | no | credits the escrow to the researcher's claimable balance after `QUALIFIED`; `-> RELEASED` |
| `sponsor_reclaim(id)` | sponsor | no | `DRAFT` -> `CANCELLED`; funded and not qualified, after the deadline -> `RECLAIMED` (escrow credited to the sponsor) |
| `claim()` | any credited address | no | the one transfer out: the caller's whole claimable balance, ledger zeroed first |

### Read methods

`get_agreement(id)`, `get_sources(id)`, `get_requirements(id)`, `get_evidence(id, version)`, `get_receipt(id, version)`, `get_verdict(id)`, `is_qualified(id)`, `get_terms_hash(id)`, `get_claimable(address)`, `get_agreements_by(address, role, offset, limit)`, `get_config()`. Views never revert on unknown ids.

### Consensus guarantees

- One `run_nondet` round per package; validators fully reproduce the procedure and compare the decision fields; prose is never compared; a malformed leader result is refused by a structural gate before any reproduction; the ratified text is re-validated at the contract boundary before it touches state.
- Unusable model output forces leader rotation; validator disagreement writes nothing and the package stays pending.
- `docs/CONSENSUS.md` has the full rule; `docs/PROTOCOL.md` the protocol; `docs/SECURITY.md` the threat model.

## Verified end-to-end

Every line below is read back from the deployment of record on GenLayer Studio Next (`docs/DEPLOYMENT.md` carries every transaction hash and vote; `deploy/live_scenarios_transcript.json` is the machine-readable copy). The evidence is the mock research release in `fixtures/`, committed at `667650fd5a89` of this repository.

```text
SCENARIO A - qualified delivery (DM-LIVE-A-09061902)
  create_agreement   SUCCESS  4 sources, 6 requirements, deadline 2027-06-30T23:59:59Z, reward 0.02 GEN
  fund_agreement     SUCCESS  value 0.02 GEN escrowed
  submit_evidence    SUCCESS  4 hash-bound sources at 667650fd5a89, deadline_met True
  adjudicate         SUCCESS  votes IDLE, AGREE, AGREE, IDLE, AGREE   (cranked by a stranger)
  verdict            QUALIFIED  6/6  M1=SATISFIED M2=SATISFIED M3=SATISFIED M4=SATISFIED M5=SATISFIED M6=SATISFIED
  dataset facts      dataset:EXAMINED (10240 records, 7 columns)
  release_reward     SUCCESS  cranked by a stranger; 0.02 GEN credited to the researcher; RELEASED
  claim              SUCCESS  the researcher pulled 0.02 GEN (balance delta 19873694999999177 atto = credit minus its own fee)
  walls              13 refusals held (stranger funds, inexact deposit, fund twice, stranger submits, reclaim before the deadline, release before any verdict, reclaim while under review, second adjudication, reclaim after qualified, resubmit after qualified, double release, stranger pulls an empty ledger, double pull)

SCENARIO B - not qualified by code (DM-LIVE-B-09061902)
  submit_evidence    SUCCESS  dataset = observations_short.csv (9,000 records)
  adjudicate         SUCCESS  votes AGREE, DISAGREE, AGREE, IDLE, AGREE
  verdict            NOT_QUALIFIED  3/6  M1=NOT_SATISFIED M2=SATISFIED M3=UNVERIFIABLE M4=UNVERIFIABLE M5=SATISFIED M6=SATISFIED
  reason_codes       ['REQUIREMENT_NOT_SATISFIED', 'REQUIREMENT_UNVERIFIABLE', 'EVIDENCE_CONTRADICTORY']   (M1 decided by the contract's record counter, no model involved)
  sponsor_reclaim    SUCCESS  after the deadline; RECLAIMED; 0.02 GEN credited to the sponsor
  claim              SUCCESS  the sponsor pulled it (delta 19873694999999177 atto)
  walls              4 refusals held (release after NOT_QUALIFIED, reclaim before the deadline, resubmit after reclaim, researcher pulls the sponsor's refund)

SCENARIO C - inconclusive, then recovery (DM-LIVE-C-09061902)
  submit v1          SUCCESS  methodology committed under a hash its bytes do not match
  adjudicate v1      SUCCESS  votes DISAGREE, AGREE, AGREE, IDLE, AGREE
  verdict v1         INCONCLUSIVE  methodology HASH_MISMATCH -> M3 UNVERIFIABLE; reason_codes ['REQUIREMENT_UNVERIFIABLE', 'EVIDENCE_HASH_MISMATCH']
  submit v2          SUCCESS  the right hash
  adjudicate v2      SUCCESS  votes AGREE, AGREE, IDLE, IDLE, AGREE
  verdict v2         QUALIFIED; package 1 and its receipt byte-identical afterwards
  release_reward     SUCCESS  RELEASED; claim: the researcher pulled 0.02 GEN

SCENARIO D - late delivery (DM-LIVE-D-09061902)
  submit_evidence    SUCCESS  after the deadline: deadline_met False
  adjudicate         SUCCESS  votes IDLE, IDLE, AGREE, AGREE, AGREE
  verdict            NOT_QUALIFIED  5/6; reason_codes ['DEADLINE_MISSED', 'REQUIREMENT_NOT_SATISFIED']
  sponsor_reclaim    SUCCESS  RECLAIMED; claim: the sponsor pulled 0.02 GEN

SCENARIO E - refusal catalog (DM-LIVE-E-09061902)
  12 refusals landed on-chain as FINALIZED leader-ERROR receipts carrying the
  contract's [EXPECTED] text (unknown agreement, stranger funds, inexact deposit, submit before funding, stranger submits, reclaim before the deadline, release before any verdict, package missing a source, unpinned location, malformed content hash, reclaim while under review, second package while under review)

SCENARIO F - contradictory analysis + injected methodology (DM-LIVE-F-09061902)
  adjudicate         SUCCESS  votes AGREE, IDLE, IDLE, AGREE, AGREE
  verdict            INCONCLUSIVE  4/6  M1=SATISFIED M2=SATISFIED M3=UNVERIFIABLE M4=UNVERIFIABLE M5=SATISFIED M6=SATISFIED
  flags              contradiction_suspected True, injection_suspected True; reason_codes ['REQUIREMENT_UNVERIFIABLE', 'EVIDENCE_CONTRADICTORY', 'INJECTION_SUSPECTED']
  claim proven       the package did not qualify and M4 was not SATISFIED; M1/M2/M5 unaffected
```

> Panel notes recorded on scenario A (advisory, outside equivalence): "Methodology document describes assay protocol, validation procedure, and replicate policy used to produce the dataset." / "Analysis reports results computed on the released dataset; stated 10,240 observations and 8 targets are consistent with dataset facts and methodology.".

```text
python scripts/preflight.py                        clean
pytest tests/direct                                468 passed
genvm-lint lint contracts/discovery_milestone.py   no findings (AST; check cannot load this runner)
python scripts/mutation_check.py                   48 mutants, 48 killed, 0 survived
node scripts/sn.mjs verify                         byte-for-byte identical to the deployment of record
```

## Tech stack

| | |
|---|---|
| Contract | Python, GenVM v0.6 runner (`import genlayer as gl`), `gl.vm.run_nondet`, `gl.nondet.web.get`, `gl.nondet.exec_prompt` with JSON output |
| Evidence hosts | commit-pinned `raw.githubusercontent.com`; `zenodo.org` record files |
| Tests | pytest, Direct Mode against an in-repository stub of the v0.6 SDK; a mutation kill sweep; a deterministic preflight; genvm-lint (AST) |
| Deployment and live evidence | Node 22, genlayer-js 2.0.0-rc.1 (the SDK that speaks Studio Next's fee distribution) |

## Repository

```text
contracts/discovery_milestone.py   the contract (one canonical deployable)
tests/direct/                      Direct Mode suite (stub SDK harness in conftest.py, scenario data in support.py)
fixtures/project/                  the mock open-science release the live agreements cite, pinned by commit
fixtures/variants/                 negative variants (a short dataset; a missing column; a contradictory analysis; an injected methodology)
fixtures/generate.py               the deterministic generator every fixture reproduces from
scripts/sn.mjs                     Studio Next toolkit: deploy | verify | write | read | tx | balance | fund | code
scripts/live_scenarios.mjs         the live scenarios A-F with transcript
scripts/mutation_check.py          the mutation kill sweep
scripts/preflight.py               deterministic repository preflight
examples/consumer.py               three downstream consumers on one gate
deploy/                            live transcript and logs of the deployment of record
docs/                              PROTOCOL, CONSENSUS, SECURITY, INTEGRATION, DEPLOYMENT
.github/workflows/ci.yml           preflight + direct suite + AST lint + mutation sweep; driver scripts npm ci
DECISION.md, SUBMISSION.md
```

## Getting started

```bash
pip install -r requirements.txt
python scripts/preflight.py
python -m pytest tests/direct -q
genvm-lint lint contracts/discovery_milestone.py
python scripts/mutation_check.py
```

Deploying and driving the live scenarios need Node 22 and a funded Studio Next wallet in `.data/keys.json` (never committed):

```bash
cd scripts && npm ci && cd ..
node scripts/sn.mjs deploy contracts/discovery_milestone.py --key CREATOR
node scripts/sn.mjs verify <address> contracts/discovery_milestone.py
node scripts/live_scenarios.mjs <address>
```

`fixtures/generate.py` reproduces every fixture byte for byte; the live agreements cite them at one commit of this repository.

## Security

- Only immutable locations are admitted; every validator re-fetches them and verifies sha256 before any fact is parsed or any model sees a byte; a mismatch excludes the source.
- The dataset facts a semantic requirement depends on are parsed by code and carried in the compared rows, so a document cannot claim a record count the file does not have without every validator's parse disagreeing.
- The deadline is the transaction clock at commitment, frozen into the package and pinned by the structural gate.
- Money is credited only by `release_reward` (to the named researcher) and `sponsor_reclaim` (to the sponsor, after the deadline, never during review or after `QUALIFIED`), and leaves only through `claim()`, which zeroes the caller's ledger before the transfer; the wei invariants hold on every path.
- No owner, no admin, no upgrade path. `docs/SECURITY.md` has the threat model and residual risks.

## Design notes

- The five requirement kinds are the division of labour made explicit: four are code, one is judgment, and the judgment always sees the code's facts. A sponsor who wants a fact settled should write it as a deterministic kind; a criterion that asks whether the science is correct gets `UNVERIFIABLE`.
- Studio Next needs a fee distribution on every transaction and a message allocation for every transfer a write emits; only genlayer-js 2.0.0-rc.1 speaks that, which is why the drivers are Node scripts and there is no gltest suite (verified, not assumed - `docs/DEPLOYMENT.md`).
- The allocation comes from a fee simulation that runs with a predefined transaction datetime well behind the chain, so a transfer inside a clock-gated write can never be allocated. That is why the gates only credit a ledger and the single transfer lives in an ungated `claim()`. The finding was made on this contract's sibling, OpenGrant, and is carried here by design.

## Disclaimer

Discovery-Milestone is a hackathon build on a test network. It adjudicates whether committed evidence demonstrates an agreed commitment; it does not validate science, and its verdicts carry no warranty.
