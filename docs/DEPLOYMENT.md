# Deployment Evidence (GenLayer Studio Next)

Only values that were verified are recorded here. The network is GenLayer
Studio Next (`https://studio-next.genlayer.com/api`, chain id 61997, GenVM
v0.6, 16 validators). Studio Next has no public block explorer; every
transaction below is read back through `eth_getTransactionByHash` with the
toolkit in `scripts/sn.mjs` (`node scripts/sn.mjs tx <hash>`), and every
state claim through the contract's own views.

- Date: 2026-09-06
- Contract: `0x9c99d7aD196F0d05Aa6eF4D56d78d43b54Ae19AB` (deployment of record)
- Deployment tx: `0x7d2001fab501f9e53e0e010bba886c58b0854ea52a859e7ad10fdad1d8a02fbc` - `FINALIZED`, `MAJORITY_AGREE`, leader
  execution `SUCCESS`, deploy-time votes `IDLE, AGREE, AGREE, IDLE, AGREE`
- Deployment method: `node scripts/sn.mjs deploy contracts/discovery_milestone.py`
  (genlayer-js 2.0.0-rc.1 with the network's fee distribution; deployer
  `0x86dDeAFc53B2e194aaD4d74D265ab7Cb741118b5`, the sponsor wallet of the live
  scenarios)
- Deployment source commit: `dd05ab5b5a703e8277a837036ee0295ef8135a44`
- Contract blob SHA (`git rev-parse <commit>:contracts/discovery_milestone.py`): `4f9fdd0b684a42f0bbd2fbdb99cc4b67c1dc408a`
- Source parity: `node scripts/sn.mjs verify 0x9c99d7aD196F0d05Aa6eF4D56d78d43b54Ae19AB contracts/discovery_milestone.py`
  fetched the deployed source (`gen_getContractCode`) and found it
  **byte-for-byte identical** to `contracts/discovery_milestone.py` (sha256
  `69aca3f555a56673a4ae45f0d68fa64a550f37b135a26567094f4f99ed0d34ce`, 92429 characters). Commits after the deployment source commit
  are docs, CI and evidence only and do not change
  `contracts/discovery_milestone.py`; the deployable blob SHA is the check.
- Fixture evidence: the agreements commit files under `fixtures/` of this
  repository at commit `667650fd5a89086f5dd7fdb3bb0082d72b70c8b4` through commit-pinned raw URLs
  (immutable by construction; the fixtures are unchanged since). Before the
  run the driver fetched every committed URL and confirmed the served bytes
  hash to the committed bytes.
- Superseded: the first deployment `0xF9788D199c8C28Ee44ff75c096D9cB77eC61d583` (below), retired by a live
  finding about excluded documents.

## The first deployment, and the finding that retired it

The first deployment of this contract (`0xF9788D199c8C28Ee44ff75c096D9cB77eC61d583`, deploy tx `0xd769846577942fa152a8d3fbec7670013202886275c3e6ee9434df402c0a17ee`,
`FINALIZED`, `MAJORITY_AGREE`; source commit `e5ba19f7341f2963f1bb501898fd53d39159c562`, blob `feefbe3585e5318cfbec073dcfea6a228ef1929a`,
byte-verified sha256 `c7953d49b90f7ff4...`) judged every `SEMANTIC` requirement
over whatever documents had been examined, with no binding between a
requirement and the document it is about. Scenarios A and B passed on it:

- A (`DM-LIVE-A-09061830`): adjudicate tx `0x919dccd4fd4787d4b004d0582e2975c4a77c34cc40a5feab7e314bab9c48e13f`
  (`MAJORITY_AGREE`, votes AGREE, AGREE, IDLE, IDLE, AGREE) ->
  `QUALIFIED` 6/6; `release_reward` tx
  `0x25ff26ef227b03221637fa63d49dafafd4295a093492dc681e228f5131fffb90` cranked by the stranger; the researcher's `claim()`
  tx `0x8e6b9a04009cdd76f3d32b1bcc033193f1606879bf3b847484df0d465611abb6` pulled 20000000000000000 atto
  of credit (balance delta 19873694999999177 atto after its own fee);
  13 refusal walls held.
- B (`DM-LIVE-B-09061830`): the 9,000-record dataset; adjudicate tx
  `0x28a25041cd20b41854ebc73386719d20342c5e8e66f83f5e01cc0755cc0ce423` -> `NOT_QUALIFIED`, M1 `NOT_SATISFIED` by the
  contract's record counter, and M4 `UNVERIFIABLE` with `EVIDENCE_CONTRADICTORY`
  because the panel compared the analysis's stated count with the parsed
  facts - its note: "Analysis and methodology claim 10,240 observations, but dataset_facts show row_count=9,000. The stated observation count is inconsistent with authoritative dataset facts, so M4 is not satisfied."; `sponsor_reclaim` tx
  `0xe161fa56817ac837d2e0df3c6e4fad141c5472954b6966ca545083689e2454f1` after the deadline; the sponsor pulled with
  `claim()` tx `0xeae6fa78ce11003d4bd7e3644b69302890ff5429f5e1d382c08eb8b9ef7a19ae`.

Scenario C exposed the gap. Package 1 committed the methodology under a hash
its served bytes do not match; the source was excluded (`HASH_MISMATCH`), as
designed, and the panel was asked to judge M3 - "the methodology is
published: it describes the assay protocol ..." - over the remaining
documents. It answered `NOT_SATISFIED` with this note: "The committed evidence does not contain the methodology document itself; the preprint merely references it as an external document. Detailed assay protocols and replicate policies are therefore missing from the evidence package." The
verdict was `NOT_QUALIFIED` (adjudicate tx `0xa9cf238c72b2e9bb5271af5059bcdeeb6f640ce4c8cda2bf8a406abe8e1dce9d`,
votes AGREE, AGREE, IDLE, IDLE, AGREE, reason codes `['REQUIREMENT_NOT_SATISFIED', 'EVIDENCE_HASH_MISMATCH']`), where the
protocol promises `INCONCLUSIVE` for evidence that is inaccessible. The
panel read an excluded document as a missing deliverable: exclusion is
missing evidence, never evidence of absence, and nothing in the contract
made that distinction for it.

The contract was changed rather than the prompt alone: a `SEMANTIC`
requirement now names the document it is judged over (`source_id`), and
when that committed document cannot be examined the requirement is
`UNVERIFIABLE` by code, the structural gate refuses any other finding, and
the panel is told which committed sources were excluded and why. That
design is the deployment of record above; the first deployment's
transcript is kept verbatim as `deploy/first_deployment_transcript.json`
with its log. Its scenario C agreement stays `ADJUDICATED` and resubmittable
on that contract; the 0.02 GEN escrows of its scenario A and B agreements
were released and reclaimed in full, so nothing is stranded.

## Toolchain of record

| Tool | Version |
|---|---|
| Python | 3.12.2 |
| pytest | 9.1.1 |
| genvm-linter | 0.11.0 (AST `lint` only - see below) |
| Node | 22.11.0 |
| genlayer-js | 2.0.0-rc.1 (the SDK that speaks Studio Next's fee distribution) |
| runner pin | `py-genlayer:5jycge4q8k23462jtb0b9fyey1s9qz928sz2nbrd9mg4sxqg2qng` (GenVM v0.6, the id the Studio's own examples pin) |

## Why the gates look the way they do on this runner

- **Direct Mode runs against an in-repository stub of the v0.6 SDK**
  (`tests/direct/conftest.py`). The official `genlayer-test` direct runner
  resolves its SDK from the GenVM releases it knows (v0.3.0-rc7 archives)
  and cannot load this runner; the stub mirrors the v0.6 surface the
  contract uses (`gl.contract.Contract`, `gl.storage.*`,
  `gl.vm.run_nondet`, `UserError.data`, `gl.message.raw["datetime"]`, the
  EVM proxy without `on=`) and is strict where it matters. Datasets are
  served as bytes and parsed by the contract exactly as on-chain.
- **`genvm-lint check` cannot load this runner (E101)**; `genvm-lint lint`
  (AST) runs and passes. Semantic validation of the runner happens where it
  can: on the deployment itself, byte-verified below and exercised live.
- **No gltest integration suite.** `genlayer-py` 0.16.3 (what gltest
  deploys and writes with) reads Studio Next fine but its writes fail the
  network's fee gate (`Transaction failed` - Studio Next reverts any
  transaction without a fee distribution). This was verified against the
  network on this contract's sibling build, not assumed. The live-scenario
  driver (`scripts/live_scenarios.mjs`, genlayer-js 2.0.0-rc.1) is the
  integration evidence: real deployment, real consensus rounds, real escrow
  and pull payments.
- **The fee simulation's clock.** `sim_estimateTransactionFees` - the call
  that derives the message allocations a transfer-emitting write needs -
  executes the write with a predefined transaction datetime well behind the
  chain (bisected on the sibling build to between 2024-01-01 and
  2025-09-06). A clock-gated write is refused by the simulation even when
  the chain accepts it, so the driver sends such writes with a plain fee
  estimate, and a transfer inside a clock-gated write can never be
  allocated. That is why value only leaves through the ungated `claim()`.

## Probe (the runtime facts the design rests on)

Before the contract was written, a throwaway probe contract
(`0x199a3313843E08a1980f65ec5fdb513Af580200D`, deploy tx
`0x107bdd319b691aa76e45392b85ad997a3211cf453a26b733cff3a78f0437fc4e`, FINALIZED, MAJORITY_AGREE) proved on this
runner, each as a finalized transaction, that the evidence path the design
needs exists:

| Claim | Evidence |
|---|---|
| a half-megabyte commit-pinned dataset is fetched under `run_nondet`, hashed and record-counted identically by leader and validators | `fetch_stats` tx `0xe26cae58701cddd5a88782c1d886766827ab55f63a7979f0d35fde322e77f018`: FINALIZED, MAJORITY_AGREE, leader SUCCESS, `status 200, bytes 549471, sha256 ca9a2861...5632b` (the committed bytes of `fixtures/project/dataset/observations.csv`), 10,241 newline-delimited records outside quotes (10,240 plus the header); validators voted on the same hash and count |
| a Zenodo record file goes through the same path | `fetch_stats` tx `0x2345465633d98075731c6c5c42f0ae7b3cf6411d6c5d9d9f7ff1f840b48e45e0` over `https://zenodo.org/records/14330132/files/dataset_dummy_nodes.csv?download=1` (a public sample record): FINALIZED, MAJORITY_AGREE, `status 200, bytes 117, sha256 fde3d707...c4c4`, the bytes the same URL serves to a browser |

The runtime facts the sibling build settled on this runner - the transaction
clock is `gl.message.raw["datetime"]`, a payable write lands value in
dataclass storage, an EOA payout through the EVM proxy moves exactly the
value, a refusal finalizes as a leader `ERROR` - are used unchanged.

## Verification status

| Gate | Result |
|---|---|
| `python scripts/preflight.py` | clean (one `emit_transfer`, v0.6 spellings, prompt rules present, location grammar, fixtures reproduce from the generator, no placeholders, runner pin) |
| `pytest tests/direct` | 468 passed |
| `genvm-lint lint contracts/discovery_milestone.py` | no findings (AST) |
| `python scripts/mutation_check.py` | 48 mutants, 48 killed, 0 survived, accept-control green |
| `node scripts/sn.mjs verify 0x9c99d7aD196F0d05Aa6eF4D56d78d43b54Ae19AB contracts/discovery_milestone.py` | byte-for-byte identical |
| `node scripts/live_scenarios.mjs` | six scenarios, every write `FINALIZED`; 31 refusal walls held, 12 of them as finalized `ERROR` receipts (below) |

## Live scenarios (the deployment of record)

Driven by `scripts/live_scenarios.mjs` from the three test wallets (sponsor
`0x86dDeAFc53B2e194aaD4d74D265ab7Cb741118b5`, researcher `0x57a7Dc8Ea2d2De0a5906eB28902b8D677Dfc657C`, stranger
`0xB66D7Fa5C37B696a78cB7F9B4F8056EF37a4b7e6`), started 2026-09-06T19:02:28.489Z, finished
2026-09-06T22:35:58.312Z. Machine-readable copy: `deploy/live_scenarios_transcript.json`.
Every write below is `FINALIZED`; the leader execution result and the
validator votes are from the receipts (`consensus_data.votes`). Money
reaches a party in two steps by design: a credit (`release_reward` /
`sponsor_reclaim`, cranked by anyone entitled) and the party's own pull
(`claim()`, the contract's only transfer). The pull's balance delta is the
credit minus that transaction's own net fee, because the party signs it.

### Scenario A - qualified delivery, release and pull (`DM-LIVE-A-09061902`)

| Step | Tx | Result |
|---|---|---|
| `create_agreement` (deadline 2027-06-30T23:59:59Z, reward 0.02 GEN, 4 sources, 6 requirements) | `0x767c4810f8443a8de3279d66379c1af9fe4ae4b327087b0a186c406248fb9391` | SUCCESS; votes AGREE, IDLE, IDLE, AGREE, AGREE; `terms_hash e0d58d205f...c02a` |
| `fund_agreement` (value 0.02 GEN) | `0x6055234f9b15f0cc1e11b2f41487485a98ba4b04ee70fcc232aa2a99b639e1e9` | SUCCESS; votes AGREE, IDLE, IDLE, AGREE, AGREE; escrow 0.02 GEN |
| `submit_evidence` v1 (4 sources at `667650fd5a89`) | `0x997bd93678ed937d9f8bdfb68c64b4dcf79fa5145c1e0032ab2f15c027240ac0` | SUCCESS; votes AGREE, IDLE, AGREE, IDLE, AGREE; `deadline_met True`; `evidence_hash 4dd257668d...4f8f` |
| `adjudicate` (cranked by the stranger) | `0x6f424313f4e02989b478c2ee3323d432a67b783a32103e18e6535f696691da44` | SUCCESS; MAJORITY_AGREE; votes IDLE, AGREE, AGREE, IDLE, AGREE |
| `release_reward` (cranked by the stranger) | `0xbb3faf6a2f4e5a58d4f8fa1f5f3128ccb6d1502cde948af2144e64d7979b914f` | SUCCESS; votes AGREE, AGREE, AGREE, IDLE, IDLE; `RELEASED`, 0.02 GEN credited to the researcher |
| `claim()` (the researcher) | `0xe0fbb4853dd2f5e9afff687406cd9e86df27c3a43d5080e242aa6f53f0db9c3d` | SUCCESS; votes AGREE, IDLE, AGREE, IDLE, AGREE; the transfer |

Verdict `QUALIFIED`, 6/6 met, `evidence_sufficient True`;
findings M1=SATISFIED M2=SATISFIED M3=SATISFIED M4=SATISFIED M5=SATISFIED M6=SATISFIED; sources dataset:EXAMINED (10240 records, 7 columns); methodology:EXAMINED; analysis:EXAMINED; preprint:EXAMINED;
`reason_codes ['ALL_REQUIREMENTS_SATISFIED']`; `record_digest 3be07f6559...62bc`.
Summary: `QUALIFIED on evidence package 1: 4/4 sources examined; requirements satisfied 6/6; deadline met: yes; not satisfied: none; unverifiable: none`. `claim()` by the researcher (tx `0xe0fbb4853dd2f5e9afff687406cd9e86df27c3a43d5080e242aa6f53f0db9c3d`; votes AGREE, IDLE, AGREE, IDLE, AGREE): claimable 0.02 GEN -> 0; balance 19.821032 -> 19.840906 GEN (delta 19873694999999177 atto = the 0.02 GEN credit minus this transaction's own net fee). `is_qualified` true.

| Wall | Attempt | Outcome |
|---|---|---|
| stranger funds | `stranger` -> `fund_agreement` | refused by the fee simulation before signing: `[EXPECTED] only the sponsor funds` |
| inexact deposit | `sponsor` -> `fund_agreement` | refused by the fee simulation before signing: `[EXPECTED] deposit must equal the reward exactly` |
| fund twice | `sponsor` -> `fund_agreement` | refused by the fee simulation before signing: `[EXPECTED] agreement is not a draft` |
| stranger submits | `stranger` -> `submit_evidence` | refused by the fee simulation before signing: `[EXPECTED] only the researcher submits` |
| reclaim before the deadline | `sponsor` -> `sponsor_reclaim` | refused by the fee simulation before signing: `[EXPECTED] the deadline has not passed` |
| release before any verdict | `stranger` -> `release_reward` | refused by the fee simulation before signing: `[EXPECTED] reward is releasable only after QUALIFIED` |
| reclaim while under review | `sponsor` -> `sponsor_reclaim` | refused by the fee simulation before signing: `[EXPECTED] an evidence package is under review; adjudicate it first` |
| second adjudication | `stranger` -> `adjudicate` | refused by the fee simulation before signing: `[EXPECTED] no evidence package is under review` |
| reclaim after qualified | `sponsor` -> `sponsor_reclaim` | refused by the fee simulation before signing: `[EXPECTED] agreement qualified; the reward belongs to the researcher` |
| resubmit after qualified | `researcher` -> `submit_evidence` | refused by the fee simulation before signing: `[EXPECTED] agreement already qualified` |
| double release | `stranger` -> `release_reward` | refused by the fee simulation before signing: `[EXPECTED] reward is releasable only after QUALIFIED` |
| stranger pulls an empty ledger | `stranger` -> `claim` | refused by the fee simulation before signing: `[EXPECTED] nothing claimable` |
| double pull | `researcher` -> `claim` | refused by the fee simulation before signing: `[EXPECTED] nothing claimable` |

### Scenario B - not qualified by code, reclaim after the deadline (`DM-LIVE-B-09061902`)

The dataset committed here is `fixtures/variants/observations_short.csv`:
9,000 records against a `ROW_COUNT_MIN` of 10,000. M1 is decided by the
contract's own record counter; no model is involved in the failure.

| Step | Tx | Result |
|---|---|---|
| `create_agreement` (deadline 2026-09-06T19:14:52Z) | `0xd49f15e2c507f891695b09e92433d752286df961c655be22ae24a1a2017bd6b9` | SUCCESS; votes IDLE, IDLE, AGREE, AGREE, AGREE |
| `fund_agreement` | `0x63789e130358d8da83e82e172e64a15a0c6f4f1d52fcbc956b2f7ad4063e7c4f` | SUCCESS; votes IDLE, IDLE, AGREE, AGREE, AGREE |
| `submit_evidence` v1 (the short dataset) | `0xe7f191424240bd5f71272157db0a75bd34e2a671c8ab3a788591a852642b345a` | SUCCESS; `deadline_met True` |
| `adjudicate` | `0x757e3fcaae5fd5317ab27a4ac8986954f9c8153f1ba1215ecfbf30b9a71778ed` | SUCCESS; MAJORITY_AGREE; votes AGREE, DISAGREE, AGREE, IDLE, AGREE |
| `sponsor_reclaim` (after the deadline) | `0x030749e616a11a9043ad532124a18f9e93658257a9db50a56758d362ec6a90bd` | SUCCESS; votes AGREE, IDLE, AGREE, AGREE, IDLE; `RECLAIMED`, escrow credited to the sponsor |
| `claim()` (the sponsor) | `0x1896bb6f63248d409cf17d8cc46d0075b357a69c5b00813ce78bc67feb28b74a` | SUCCESS; votes AGREE, IDLE, IDLE, AGREE, AGREE |

Verdict `NOT_QUALIFIED`, 3/6 met; findings M1=NOT_SATISFIED M2=SATISFIED M3=UNVERIFIABLE M4=UNVERIFIABLE M5=SATISFIED M6=SATISFIED;
sources dataset:EXAMINED (9000 records, 7 columns); methodology:EXAMINED; analysis:EXAMINED; preprint:EXAMINED; `reason_codes ['REQUIREMENT_NOT_SATISFIED', 'REQUIREMENT_UNVERIFIABLE', 'EVIDENCE_CONTRADICTORY']`.
Summary: `NOT_QUALIFIED on evidence package 1: 4/4 sources examined; requirements satisfied 3/6; deadline met: yes; not satisfied: M1; unverifiable: M3, M4`. `claim()` by the sponsor (tx `0x1896bb6f63248d409cf17d8cc46d0075b357a69c5b00813ce78bc67feb28b74a`; votes AGREE, IDLE, IDLE, AGREE, AGREE): claimable 0.02 GEN -> 0; balance 19.898417 -> 19.91829 GEN (delta 19873694999999177 atto = the 0.02 GEN credit minus this transaction's own net fee).

| Wall | Attempt | Outcome |
|---|---|---|
| release after NOT_QUALIFIED | `stranger` -> `release_reward` | refused by the fee simulation before signing: `[EXPECTED] reward is releasable only after QUALIFIED` |
| reclaim before the deadline | `sponsor` -> `sponsor_reclaim` | refused by the fee simulation before signing: `[EXPECTED] the deadline has not passed` |
| resubmit after reclaim | `researcher` -> `submit_evidence` | refused by the fee simulation before signing: `[EXPECTED] agreement does not accept evidence in status RECLAIMED` |
| researcher pulls the sponsor's refund | `researcher` -> `claim` | refused by the fee simulation before signing: `[EXPECTED] nothing claimable` |

### Scenario C - inconclusive on a hash mismatch, recovery, release (`DM-LIVE-C-09061902`)

Package 1 commits the methodology under the sha256 of bytes that are never
served (the file plus one newline, `9513c475ae...6ea8`); the served
bytes mismatch, the source is excluded, and M3 cannot be verified.

| Step | Tx | Result |
|---|---|---|
| `create_agreement` | `0x3730a8232a1a4e33a94d3e5a58da189c0ccc3d686c8efefa473b711f07683ff0` | SUCCESS |
| `fund_agreement` | `0x7bc18262496ee4364c371423d2ff26bf5f5a7bd3b9aa750ce6c5999b7a08c727` | SUCCESS |
| `submit_evidence` v1 (methodology under a wrong hash) | `0xe296897f5dba4f38bda1e40a8533a1c4bb3fad651b717d06b842edc79150be8f` | SUCCESS |
| `adjudicate` v1 | `0xb5863c4d72b2a7037717fb68048605a7d75d8d35c5c37e229516f3da0e2776b2` | SUCCESS; MAJORITY_AGREE; votes DISAGREE, AGREE, AGREE, IDLE, AGREE |
| `submit_evidence` v2 (the right hash) | `0xd2334ca858e4d97a584c58897b173baa9d8f69adb79d269dd3d5efb52bc4d919` | SUCCESS |
| `adjudicate` v2 | `0x100cba0c35cf43bdeb434f7fba5d591161fca66e4aa0b3b4995e2514fe21f7fb` | SUCCESS; MAJORITY_AGREE; votes AGREE, AGREE, IDLE, IDLE, AGREE |
| `release_reward` (by the researcher) | `0xd1eb1d9c7b11f65bb4fdac046c28663a3d2a5e551e021d205cbe383651847bd4` | SUCCESS; `RELEASED` |
| `claim()` (the researcher) | `0xf63569d13eb6cf79dec3740a318fedf0e051aa77ea61545bb640603b6479163a` | SUCCESS; votes IDLE, AGREE, IDLE, AGREE, AGREE |

Package 1: verdict `INCONCLUSIVE`; findings M1=SATISFIED M2=SATISFIED M3=UNVERIFIABLE M4=SATISFIED M5=SATISFIED M6=SATISFIED; sources dataset:EXAMINED (10240 records, 7 columns); methodology:HASH_MISMATCH; analysis:EXAMINED; preprint:EXAMINED;
`reason_codes ['REQUIREMENT_UNVERIFIABLE', 'EVIDENCE_HASH_MISMATCH']`; `evidence_sufficient False`.
Package 2: verdict `QUALIFIED`; findings M1=SATISFIED M2=SATISFIED M3=SATISFIED M4=SATISFIED M5=SATISFIED M6=SATISFIED; `reason_codes ['ALL_REQUIREMENTS_SATISFIED']`.
The package-1 record and its receipt read back byte-identical after package
2 landed; `judged_version` and `qualified_version` are 2. `claim()` by the researcher (tx `0xf63569d13eb6cf79dec3740a318fedf0e051aa77ea61545bb640603b6479163a`; votes IDLE, AGREE, IDLE, AGREE, AGREE): claimable 0.02 GEN -> 0; balance 19.790512 -> 19.810386 GEN (delta 19873694999999177 atto = the 0.02 GEN credit minus this transaction's own net fee).

| Wall | Attempt | Outcome |
|---|---|---|
| release after INCONCLUSIVE | `stranger` -> `release_reward` | refused by the fee simulation before signing: `[EXPECTED] reward is releasable only after QUALIFIED` |

### Scenario D - late delivery (`DM-LIVE-D-09061902`)

| Step | Tx | Result |
|---|---|---|
| `create_agreement` (deadline 2026-09-06T19:30:14Z) | `0x2ff806dd7a4c76cf4652b80174a097a9d7dfbc93051e83dc59d2bc34bc150c08` | SUCCESS |
| `fund_agreement` | `0x90034fc619a1ad0ff8afb597b227226fcdbd2cb1fcf017845f21f0e540501be1` | SUCCESS |
| `submit_evidence` v1, after the deadline | `0xaf0dc8574bc57c6ab742e7de85bcf8af35f8998f6d3a9a576857d3d60890417a` | SUCCESS; `deadline_met False` |
| `adjudicate` | `0x31afc2bbeca7f7fe5f2bef201538bd6602851b773bd83d13b867d2519f6ea785` | SUCCESS; MAJORITY_AGREE; votes IDLE, IDLE, AGREE, AGREE, AGREE |
| `sponsor_reclaim` | `0xd8844a8043cbf43b36288c82c45f195282eedae975914cdd4aea3c51dc08aaa0` | SUCCESS; `RECLAIMED` |
| `claim()` (the sponsor) | `0x1906b7289673a5f8d23ffa8e37b215517731c5d0ed6b74dbd6067ac00636fe51` | SUCCESS |

Verdict `NOT_QUALIFIED`, 5/6 met: every requirement but the
deadline is SATISFIED (M1=SATISFIED M2=SATISFIED M3=SATISFIED M4=SATISFIED M5=SATISFIED M6=NOT_SATISFIED) and `reason_codes ['DEADLINE_MISSED', 'REQUIREMENT_NOT_SATISFIED']`. The
deadline, decided by the transaction clock at commitment, dominates the
panel's findings. Summary: `NOT_QUALIFIED on evidence package 1: 4/4 sources examined; requirements satisfied 5/6; deadline met: no; not satisfied: M6; unverifiable: none`. `claim()` by the sponsor (tx `0x1906b7289673a5f8d23ffa8e37b215517731c5d0ed6b74dbd6067ac00636fe51`; votes AGREE, AGREE, IDLE, IDLE, AGREE): claimable 0.02 GEN -> 0; balance 19.87774 -> 19.897613 GEN (delta 19873694999999177 atto = the 0.02 GEN credit minus this transaction's own net fee).

### Scenario E - the refusal catalog as finalized receipts (`DM-LIVE-E-09061902`)

Each attempt below was sent with a plain fee estimate so that the chain
itself, not the pre-flight simulation, records the contract's refusal: every
row is a `FINALIZED` transaction whose leader execution is `ERROR` with the
contract's `[EXPECTED]` text, ratified by the votes shown. The agreement
was funded and a package committed between the walls; it is left
`UNDER_REVIEW` on purpose: anyone may crank `adjudicate`, and the sponsor's
exit opens after the deadline.

| Wall | Attempt | Outcome |
|---|---|---|
| unknown agreement | `stranger` -> `adjudicate` | finalized leader `ERROR` (tx `0x6c8f440d...01e8`; votes AGREE, AGREE, AGREE, IDLE, IDLE): `[EXPECTED] unknown agreement_id` |
| stranger funds | `stranger` -> `fund_agreement` | finalized leader `ERROR` (tx `0xf0c33e11...e1aa`; votes AGREE, IDLE, AGREE, IDLE, AGREE): `[EXPECTED] only the sponsor funds` |
| inexact deposit | `sponsor` -> `fund_agreement` | finalized leader `ERROR` (tx `0x8218d0ec...e355`; votes AGREE, IDLE, IDLE, AGREE, AGREE): `[EXPECTED] deposit must equal the reward exactly` |
| submit before funding | `researcher` -> `submit_evidence` | finalized leader `ERROR` (tx `0x925c0b53...45a9`; votes AGREE, AGREE, IDLE, AGREE, IDLE): `[EXPECTED] agreement does not accept evidence in status DRAFT` |
| stranger submits | `stranger` -> `submit_evidence` | finalized leader `ERROR` (tx `0xe097b146...cdf1`; votes IDLE, AGREE, IDLE, AGREE, AGREE): `[EXPECTED] only the researcher submits` |
| reclaim before the deadline | `sponsor` -> `sponsor_reclaim` | finalized leader `ERROR` (tx `0x6dacc295...2cf3`; votes AGREE, AGREE, IDLE, IDLE, AGREE): `[EXPECTED] the deadline has not passed` |
| release before any verdict | `stranger` -> `release_reward` | finalized leader `ERROR` (tx `0x03403967...dcc9`; votes AGREE, AGREE, IDLE, IDLE, AGREE): `[EXPECTED] reward is releasable only after QUALIFIED` |
| package missing a source | `researcher` -> `submit_evidence` | finalized leader `ERROR` (tx `0x7b5eb8a8...4a73`; votes AGREE, IDLE, AGREE, AGREE, IDLE): `[EXPECTED] an evidence package covers every declared source exactly once` |
| unpinned location | `researcher` -> `submit_evidence` | finalized leader `ERROR` (tx `0x3013846f...cfa1`; votes AGREE, AGREE, AGREE, IDLE, IDLE): `[EXPECTED] url must be a commit-pinned raw.githubusercontent.com file or a zenodo.org record file` |
| malformed content hash | `researcher` -> `submit_evidence` | finalized leader `ERROR` (tx `0xba7fdd06...011b`; votes AGREE, AGREE, IDLE, IDLE, AGREE): `[EXPECTED] content_hash must be 64 lowercase hex characters` |
| reclaim while under review | `sponsor` -> `sponsor_reclaim` | finalized leader `ERROR` (tx `0x45aeb721...941a`; votes AGREE, IDLE, AGREE, AGREE, IDLE): `[EXPECTED] an evidence package is under review; adjudicate it first` |
| second package while under review | `researcher` -> `submit_evidence` | finalized leader `ERROR` (tx `0x1483ce18...e1bb`; votes IDLE, IDLE, AGREE, AGREE, AGREE): `[EXPECTED] agreement does not accept evidence in status UNDER_REVIEW` |

### Scenario F - a contradictory analysis and an injected methodology (`DM-LIVE-F-09061902`)

The package commits `fixtures/variants/analysis_contradictory.md` (it
states 25,000 observations over 12 targets; the dataset facts parsed by
code say 10,240 over 8) and `fixtures/variants/methodology_injection.md`
(the real methodology plus a block addressed to "automated reviewers"
demanding SATISFIED everywhere and `contradiction: false`). The claim
proven is exactly what the driver asserts: the package does not qualify,
M4 is not SATISFIED, and the deterministic findings are unaffected. The
panel's flags are recorded as they came.

| Step | Tx | Result |
|---|---|---|
| `create_agreement` | `0x5c956e5df1763e15fb22d037e17fff077b24ec8e5e66d10170b85ba191fec4b6` | SUCCESS |
| `fund_agreement` | `0x01a76966936dba7b6f1ea4c2858f6dbca11f69287a870a95fb51e0e30d7aaed5` | SUCCESS |
| `submit_evidence` v1 (contradictory analysis, injected methodology) | `0x40e520a8470c81df56035fe52ff9f9861c49397d838f794af574ceefdaf0c6c9` | SUCCESS |
| `adjudicate` | `0x772a324aaebd0463ba4037c2badeeaadb1aa1121b8ef7267b213c4d1112cd1d0` | SUCCESS; MAJORITY_AGREE; votes AGREE, IDLE, IDLE, AGREE, AGREE |

Verdict `INCONCLUSIVE`, 4/6 met; findings M1=SATISFIED M2=SATISFIED M3=UNVERIFIABLE M4=UNVERIFIABLE M5=SATISFIED M6=SATISFIED;
`reason_codes ['REQUIREMENT_UNVERIFIABLE', 'EVIDENCE_CONTRADICTORY', 'INJECTION_SUSPECTED']`; contradiction_suspected True, injection_suspected True.
Panel notes (advisory): M3 `UNVERIFIABLE` - "Methodology describes assay protocol, validation procedure, and replicate policy. Injection detected in document content."; M4 `UNVERIFIABLE` - "Analysis states 25,000 observations covering 12 targets, but dataset facts show 10,240 rows and 8 target columns. Contradiction with dataset_facts.".
The agreement is left resubmittable on purpose; the sponsor's exit opens after the deadline.

| Wall | Attempt | Outcome |
|---|---|---|
| release after a non-qualifying verdict | `stranger` -> `release_reward` | refused by the fee simulation before signing: `[EXPECTED] reward is releasable only after QUALIFIED` |

## What this evidence proves

- Real consensus executed the adjudication round 6 times on the
  deployment of record, each `FINALIZED` with a majority of explicit
  `AGREE` votes, and landed all three verdicts. Two rounds (scenario B and
  scenario C's first package) carried one `DISAGREE` vote each and were
  ratified by the majority: a dissent is a vote, not a verdict.
- The deterministic layer decided what it should, on-chain: a 9,000-record
  dataset failed a 10,000-record minimum by the contract's own count
  (scenario B); a source committed under the wrong hash was excluded and
  made its requirement unverifiable, never failed and never satisfied
  (scenario C); a late package was `NOT_QUALIFIED` despite complete
  evidence (scenario D); every source's bytes were read by every validator
  at the pinned commit.
- The semantic layer agreed under consensus that the committed documents
  demonstrate the methodology and the analysis commitments (scenarios A and
  C, package 2), and did not let a contradictory analysis or an injected
  methodology buy a `QUALIFIED` (scenario F).
- Money moved exactly as the terms say and only as the terms say: the
  researcher's reward was credited by a stranger's crank and pulled by the
  researcher alone; the sponsor recovered the escrow only after the
  deadline and only when nothing qualified; a stranger pulling an empty
  ledger, a double release and a double pull were all refused; 31
  refusal walls held, 12 of them as on-chain `ERROR` receipts.
- Recovery works and the record is immutable: a second package produced a
  second receipt; the first did not change by a byte.

## Disposable vs canonical

The probe and any redeploys are disposable. The canonical deployment is the
address at the top of this file; `docs/DEPLOYMENT.md`, `README.md` and
`SUBMISSION.md` name the same address, and `node scripts/sn.mjs verify
<address> contracts/discovery_milestone.py` proves the bytes at any time.

## Clean-checkout rehearsal

Pending at this commit: the rehearsal clones the pushed evidence commit into
a short path, runs the gates from the clone and verifies the deployment from
it; the commit that follows records the result here.
