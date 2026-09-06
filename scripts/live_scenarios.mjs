/**
 * Live Studio Next scenarios against a Discovery-Milestone deployment.
 *
 *   node scripts/live_scenarios.mjs <contract> [--fixtures-commit SHA] [--only A,B,C,D,E,F]
 *        [--repo-owner Hemmy1417] [--repo-name DiscoMile]
 *
 * Drives the primitive end to end on the real network with real consensus
 * and archives the evidence (tx hashes, leader execution results, validator
 * votes, stored state, balances) to deploy/live_scenarios_transcript.json:
 *
 *   A  QUALIFIED + release: the six-requirement research agreement, the full
 *      evidence package committed at the fixtures commit -> QUALIFIED 6/6;
 *      release_reward (cranked by a stranger) credits the researcher's
 *      claimable balance; the researcher pulls it with claim(). Thirteen
 *      refusal walls along the way.
 *   B  NOT_QUALIFIED decided in code: the dataset holds 9,000 records against
 *      a ROW_COUNT_MIN of 10,000 -> M1 NOT_SATISFIED by the contract's own
 *      record counter, no model involved; after the deadline the sponsor
 *      reclaims the escrow and pulls it.
 *   C  INCONCLUSIVE + recovery: the methodology is committed under a hash its
 *      served bytes do not match -> EVIDENCE_HASH_MISMATCH, M3 UNVERIFIABLE,
 *      INCONCLUSIVE; package 2 commits the right hash -> QUALIFIED; package 1
 *      and its receipt stay intact; release and pull.
 *   D  Late delivery: the package lands after the deadline -> the deadline
 *      requirement NOT_SATISFIED and DEADLINE_MISSED although every other
 *      requirement is SATISFIED (the deadline is decided by the transaction
 *      clock, never by the model); reclaim and pull.
 *   E  The refusal catalog landed on-chain: each deterministic wall is sent
 *      past the fee simulation so it finalizes as a leader ERROR receipt
 *      carrying the contract's own [EXPECTED] text.
 *   F  Contradiction + injection: the analysis claims 25,000 observations over
 *      12 targets (the dataset facts say 10,240 over 8) and the methodology
 *      carries a prompt injection demanding SATISFIED everywhere. The claim
 *      proven is exactly this: the package does not QUALIFY and M4 is not
 *      SATISFIED; the panel's flags are recorded as they came.
 *
 * Every write waits for FINALIZED and judges the LEADER execution result;
 * every balance claim is read from the chain. Actors are the test wallets in
 * .data/keys.json (sponsor = CREATOR, researcher = YES, stranger = NO).
 */
import { readFileSync, writeFileSync, mkdirSync, existsSync } from "node:fs";
import { createHash } from "node:crypto";
import { resolve } from "node:path";
import { actor, loadKeys, rpc, view, feesFor, landed, FEE_FLOOR, sleep, TRANSIENT, refusalText } from "./sn.mjs";

const argv = process.argv.slice(2);
const opt = (name, dflt) => { const i = argv.indexOf(name); return i >= 0 ? argv[i + 1] : dflt; };
const positional = argv.filter((x, i) => !x.startsWith("--") && !(i > 0 && argv[i - 1].startsWith("--")));
const CONTRACT = positional[0];
if (!CONTRACT) { console.error("usage: node scripts/live_scenarios.mjs <contract> [--fixtures-commit SHA] [--only A,B,C,D,E,F]"); process.exit(2); }

// The commit whose fixture bytes the agreements are bound to. Any later
// commit leaves these URLs immutable.
const FIXTURES_COMMIT = opt("--fixtures-commit", "667650fd5a89086f5dd7fdb3bb0082d72b70c8b4");   // the commit that pins fixtures/
const REPO_OWNER = opt("--repo-owner", "Hemmy1417");
const REPO_NAME = opt("--repo-name", "DiscoMile");
const ONLY = opt("--only", "A,B,C,D,E,F").split(",").map((s) => s.trim().toUpperCase());
const OUT = resolve(process.cwd(), "deploy/live_scenarios_transcript.json");
const RAW = `https://raw.githubusercontent.com/${REPO_OWNER}/${REPO_NAME}/${FIXTURES_COMMIT}/`;
const REWARD = 2n * 10n ** 16n;            // 0.02 GEN

const KEYS = loadKeys();
const SPONSOR = actor("sponsor", KEYS.CREATOR.pk);
const RESEARCHER = actor("researcher", KEYS.YES.pk);
const STRANGER = actor("stranger", KEYS.NO.pk);

const TITLE = "Open Drug-Discovery Dataset";
const OBJECTIVE = "Produce and publicly release a dataset of at least 10,000 validated IC50 observations for small molecules against eight kinase targets, together with the methodology and the analysis required by the research agreement.";
// (source_id, kind, description)
const SOURCES = [
  ["dataset", "DATASET", "The released observations as one CSV file with a header row."],
  ["methodology", "METHODOLOGY", "The published methodology: assay protocol, validation procedure, replicate policy."],
  ["analysis", "ANALYSIS", "The published analysis computed on the released dataset."],
  ["preprint", "PUBLICATION", "The preprint describing the release."],
];
// (requirement_id, kind, criterion, source_id, param)
const REQUIREMENTS = [
  ["M1", "ROW_COUNT_MIN", "The released dataset contains at least 10,000 validated observations.", "dataset", "10000"],
  ["M2", "COLUMNS_REQUIRED", "Every observation carries the required metadata columns: compound_id, target, assay, ic50_nm, validated.", "dataset", "compound_id,target,assay,ic50_nm,validated"],
  ["M3", "SEMANTIC", "The methodology is published: it describes the assay protocol, the validation procedure and the replicate policy used to produce the dataset.", "", ""],
  ["M4", "SEMANTIC", "The analysis is published: it reports results computed on the released dataset, and the observation count and target count it states are consistent with the dataset facts.", "", ""],
  ["M5", "ACCESSIBLE", "The dataset is publicly accessible at the committed location with the committed bytes.", "dataset", ""],
  ["M6", "DEADLINE", "The milestone is completed before the agreed deadline.", "", ""],
];
// source_id -> repository path of the canonical package
const PACKAGE = {
  dataset: "fixtures/project/dataset/observations.csv",
  methodology: "fixtures/project/methodology.md",
  analysis: "fixtures/project/analysis.md",
  preprint: "fixtures/project/preprint.md",
};
const VARIANTS = {
  short: "fixtures/variants/observations_short.csv",
  missing_column: "fixtures/variants/observations_missing_column.csv",
  contradictory: "fixtures/variants/analysis_contradictory.md",
  injection: "fixtures/variants/methodology_injection.md",
};

const PRIOR = existsSync(OUT) ? JSON.parse(readFileSync(OUT, "utf-8")) : null;
const TRANSCRIPT = { network: "studio-next", chain_id: 61997, contract: CONTRACT, fixtures_commit: FIXTURES_COMMIT,
  repository: { owner: REPO_OWNER, name: REPO_NAME }, actors: { sponsor: SPONSOR.address, researcher: RESEARCHER.address, stranger: STRANGER.address },
  started_at: PRIOR?.started_at ?? new Date().toISOString(), scenarios: PRIOR?.scenarios ?? {} };
if (PRIOR) { TRANSCRIPT.resumed_at = (PRIOR.resumed_at ?? []).concat([new Date().toISOString()]); if (PRIOR.vetoes) TRANSCRIPT.vetoes = PRIOR.vetoes; }
const flush = () => { mkdirSync(resolve(process.cwd(), "deploy"), { recursive: true }); writeFileSync(OUT, JSON.stringify(TRANSCRIPT, (k, v) => (typeof v === "bigint" ? v.toString() : v), 2) + "\n"); };
const log = (s) => console.log(s);
const die = (m) => { flush(); console.log("FATAL: " + m); process.exit(1); };
const sha = (b) => createHash("sha256").update(b).digest("hex");
const fileHash = (path) => sha(readFileSync(resolve(process.cwd(), path)));

async function verifyFixtureUrls() {
  const paths = [...Object.values(PACKAGE), ...Object.values(VARIANTS)];
  for (const p of paths) {
    const res = await fetch(RAW + p, { headers: { "user-agent": "Mozilla/5.0 discovery-milestone-live" } });
    const body = Buffer.from(await res.arrayBuffer());
    const served = sha(body), local = fileHash(p);
    if (res.status !== 200 || served !== local) die(`${RAW + p}: status ${res.status}, served ${served.slice(0, 12)}, local ${local.slice(0, 12)}`);
    log(`  fixture verified: ${p} sha256 ${local.slice(0, 16)}... (${body.length} bytes)`);
  }
}

async function jview(fn, args) { const raw = await view(CONTRACT, fn, args); return typeof raw === "string" ? JSON.parse(raw) : raw; }
const balance = async (addr) => BigInt((await rpc("eth_getBalance", [addr, "latest"])).result);

/** Poll a view predicate: Studio Next reads can lag a finalized write. */
async function until(label, fn, tries = 24) {
  for (let i = 0; i < tries; i++) {
    const v = await fn();
    if (v) return v;
    await sleep(5000);
  }
  die(`${label}: view never reflected the write`);
}

const EMITS_TRANSFER = new Set(["claim"]);   // the one pull payment

async function write(a, fn, args, value = 0n, expect = "SUCCESS", label = fn) {
  for (let attempt = 0; attempt < 8; attempt++) {
    let fees, preflight = null;
    try {
      fees = await feesFor(a, CONTRACT, fn, args, value);
    } catch (err) {
      preflight = String(err?.message ?? err).slice(0, 240);
      if (TRANSIENT.test(preflight)) { await sleep(15000); continue; }
      const reason = refusalText(err);
      if (EMITS_TRANSFER.has(fn) && expect === "SUCCESS") {
        // The transfer needs the simulation's message allocations; a plain
        // estimate would land on-chain as "fee no_matching_allocation". The
        // simulation's clock can trail the wall clock, so wait and re-simulate.
        log(`   ${fn}: fee simulation refused (${reason || preflight.slice(0, 80)}); re-simulating in 30s`);
        await sleep(30000); continue;
      }
      const est = await a.client.estimateTransactionFees();
      fees = { distribution: est.distribution, feeValue: est.feeValue > FEE_FLOOR ? est.feeValue : FEE_FLOOR };
    }
    let hash;
    try {
      hash = await a.client.writeContract({ address: CONTRACT, functionName: fn, args, value, fees });
    } catch (err) {
      const msg = String(err?.message ?? err);
      if (TRANSIENT.test(msg) && attempt < 7) { log(`   send failed transiently, retrying: ${msg.slice(0, 100)}`); await sleep(15000); continue; }
      throw err;
    }
    log(`  ${a.name} ${label} tx ${hash} ...`);
    const { summary } = await landed(hash, label);
    if (summary.status !== "FINALIZED") {
      if (attempt < 7) { log(`   ${label}: ${summary.status} - retrying`); await sleep(15000); continue; }
      die(`${label}: ${summary.status}`);
    }
    if (summary.result_name === "MAJORITY_DISAGREE" && attempt < 7) {
      log(`   ${label}: MAJORITY_DISAGREE (vetoed, nothing written) - cranking again`);
      TRANSCRIPT.vetoes = (TRANSCRIPT.vetoes || []).concat([{ fn, hash }]);
      await sleep(15000); continue;
    }
    log(`    leader ${summary.leader}; ${summary.result_name}; votes ${summary.votes.join(", ")}${preflight ? " (fee simulation refused; sent with a plain estimate)" : ""}`);
    if (summary.leader !== expect) { if (summary.stderr_tail) log("    stderr: " + summary.stderr_tail.slice(-400)); die(`${label}: leader ${summary.leader}, expected ${expect}`); }
    const rec = { fn, actor: a.name, tx: hash, leader: summary.leader, result_name: summary.result_name, votes: summary.votes };
    if (summary.result_text && expect === "ERROR") rec.result_text = summary.result_text;
    if (value) rec.value_atto = value.toString();
    if (preflight) rec.preflight = preflight;
    if (summary.stderr_tail && expect === "ERROR") rec.stderr_tail = summary.stderr_tail.slice(-300);
    return rec;
  }
  die(`${label}: gave up`);
}

/** A refusal: the fee simulation usually refuses before signing (recorded as
 * such); when it does not, the write must finalize as a leader ERROR. */
async function wall(name, a, fn, args, value = 0n, onChain = false) {
  log(`  WALL ${name}: ${a.name} ${fn} must be refused`);
  let simulated = null;
  try {
    await feesFor(a, CONTRACT, fn, args, value);
  } catch (err) {
    const msg = String(err?.message ?? err);
    if (!TRANSIENT.test(msg)) {
      simulated = refusalText(err) || msg.slice(0, 200);
      log(`    refused pre-flight by the fee simulation: ${simulated}`);
      if (!onChain) return { wall: name, fn, actor: a.name, refused_at: "simulation", contract_text: simulated };
    }
  }
  // Land the refusal as a finalized ERROR receipt (plain fee estimate, no
  // simulation), so the chain itself records the contract's refusal.
  const rec = await write(a, fn, args, value, "ERROR", `wall:${name}`);
  const out = { wall: name, refused_at: "finalized", contract_text: rec.result_text || simulated || "", ...rec };
  log(`    finalized leader ERROR: ${out.contract_text}`);
  return out;
}

function deadlineIn(seconds) { return new Date(Date.now() + seconds * 1000).toISOString().replace(/\.\d{3}Z$/, "Z"); }
async function waitPast(iso, label) {
  const target = Date.parse(iso) + 150_000;     // margin over the chain clock (the fee simulation trails it)
  while (Date.now() < target) { log(`  waiting for the deadline ${iso} to pass (${label})`); await sleep(20000); }
}

/** (source_ids, urls, content_hashes) for a package: source_id -> path, with
 * optional hash overrides (to commit to bytes other than what is served). */
function packageLists(paths = PACKAGE, hashes = {}) {
  const ids = Object.keys(paths);
  return [ids, ids.map((s) => RAW + paths[s]), ids.map((s) => hashes[s] || fileHash(paths[s]))];
}
function termLists() {
  return [SOURCES.map((s) => s[0]), SOURCES.map((s) => s[1]), SOURCES.map((s) => s[2]),
    REQUIREMENTS.map((r) => r[0]), REQUIREMENTS.map((r) => r[1]), REQUIREMENTS.map((r) => r[2]),
    REQUIREMENTS.map((r) => r[3]), REQUIREMENTS.map((r) => r[4])];
}

/** The party pulls its claimable balance; the balance delta is the credit
 * minus this transaction's own net fee (the puller signs it). */
async function pullLedger(a, key, arc, expected) {
  const claimable = BigInt(String(await view(CONTRACT, "get_claimable", [a.address])));
  if (claimable !== expected) die(`${key}: claimable ${claimable}, expected ${expected}`);
  const before = await balance(a.address);
  arc[key] = await write(a, "claim", []);
  await sleep(20000);
  const after = await balance(a.address);
  const left = BigInt(String(await view(CONTRACT, "get_claimable", [a.address])));
  arc[key].balance = { before: before.toString(), after: after.toString(), delta: (after - before).toString(), claimable_before: claimable.toString(), claimable_after: left.toString() };
  log(`  ${a.name} claim: +${Number((after - before) / 10n ** 12n) / 1e6} GEN (credit ${Number(claimable / 10n ** 12n) / 1e6} minus this transaction's net fee); claimable now ${left}`);
  if (left !== 0n) die(`${key}: ledger not zeroed`);
  if (after - before < expected - 5n * 10n ** 15n || after - before > expected) die(`${key}: delta ${after - before}`);
}

async function createAgreement(id, deadline, arc) {
  arc.create = await write(SPONSOR, "create_agreement",
    [id, RESEARCHER.address, TITLE, OBJECTIVE, deadline, REWARD.toString(), ...termLists()]);
  const ag = await until("create", async () => { const a = await jview("get_agreement", [id]); return a.found ? a : null; });
  if (ag.status !== "DRAFT") die(`${id}: expected DRAFT, got ${ag.status}`);
  arc.terms_hash = ag.terms_hash; arc.deadline = ag.deadline;
  log(`  ${id} DRAFT; terms_hash ${ag.terms_hash.slice(0, 16)}...; deadline ${ag.deadline}`);
}
async function fund(id, arc) {
  arc.fund = await write(SPONSOR, "fund_agreement", [id], REWARD);
  const ag = await until("fund", async () => { const a = await jview("get_agreement", [id]); return a.status === "FUNDED" ? a : null; });
  if (ag.escrow_atto !== REWARD.toString()) die(`${id}: escrow ${ag.escrow_atto}`);
  log(`  FUNDED; escrow ${ag.escrow_atto} atto`);
}
async function submit(id, paths, hashes, arc, key, expectVersion) {
  arc[key] = await write(RESEARCHER, "submit_evidence", [id, ...packageLists(paths, hashes)]);
  const pkg = await until(key, async () => { const p = await jview("get_evidence", [id, expectVersion]); return p.found ? p : null; });
  arc[key].version = pkg.version; arc[key].evidence_hash = pkg.evidence_hash; arc[key].deadline_met = pkg.deadline_met;
  log(`  package v${pkg.version} ${pkg.status}; deadline_met ${pkg.deadline_met}; evidence_hash ${pkg.evidence_hash.slice(0, 16)}...`);
  return pkg;
}
async function adjudicate(id, arc, key, expectVerdict, version) {
  arc[key] = await write(STRANGER, "adjudicate", [id]);
  const v = await until(key, async () => { const x = await jview("get_verdict", [id]); return x.evidence_version === version ? x : null; });
  const rec = await jview("get_receipt", [id, version]);
  arc[key].verdict = v; arc[key].receipt = rec;
  log(`  verdict ${v.verdict} (status ${v.status}); ${v.requirements_met}/${v.requirements_total} met; findings ${rec.requirements.map((r) => r.requirement_id + "=" + r.finding).join(" ")}`);
  log(`  sources ${rec.sources.map((s) => s.source_id + ":" + s.status + (s.kind === "DATASET" ? `(${s.row_count} rows, ${s.column_count} cols)` : "")).join(" ")}; reason_codes ${JSON.stringify(rec.reason_codes)}`);
  log(`  summary: ${rec.summary}`);
  if (expectVerdict && v.verdict !== expectVerdict) die(`${id}: expected ${expectVerdict}, got ${v.verdict}`);
  return { v, rec };
}
const finding = (rec, rid) => rec.requirements.find((r) => r.requirement_id === rid).finding;
const sourceRow = (rec, sid) => rec.sources.find((s) => s.source_id === sid);

async function scenarioA() {
  log("\nSCENARIO A - qualified delivery: release to the researcher, pull");
  const id = `DM-LIVE-A-${TAG}`; const arc = { agreement_id: id };
  TRANSCRIPT.scenarios.A = arc;
  await createAgreement(id, "2027-06-30", arc);
  arc.walls = [];
  arc.walls.push(await wall("stranger funds", STRANGER, "fund_agreement", [id], REWARD));
  arc.walls.push(await wall("inexact deposit", SPONSOR, "fund_agreement", [id], REWARD - 1n));
  await fund(id, arc);
  arc.walls.push(await wall("fund twice", SPONSOR, "fund_agreement", [id], REWARD));
  arc.walls.push(await wall("stranger submits", STRANGER, "submit_evidence", [id, ...packageLists()]));
  arc.walls.push(await wall("reclaim before the deadline", SPONSOR, "sponsor_reclaim", [id]));
  arc.walls.push(await wall("release before any verdict", STRANGER, "release_reward", [id]));
  await submit(id, PACKAGE, {}, arc, "submit", 1);
  arc.walls.push(await wall("reclaim while under review", SPONSOR, "sponsor_reclaim", [id]));
  const { v, rec } = await adjudicate(id, arc, "adjudicate", "QUALIFIED", 1);
  for (const r of rec.requirements) if (r.finding !== "SATISFIED") die(`A: ${r.requirement_id} ${r.finding}`);
  if (rec.sources.some((s) => s.status !== "EXAMINED")) die("A: a source was not examined");
  const ds = sourceRow(rec, "dataset");
  if (ds.row_count !== 10240 || ds.column_count !== 7) die(`A: dataset facts ${ds.row_count} rows, ${ds.column_count} cols`);
  if (v.requirements_met !== 6 || !v.evidence_sufficient || !v.deadline_met) die("A: verdict fields");
  if (!(await view(CONTRACT, "is_qualified", [id]))) die("A: is_qualified false");
  arc.walls.push(await wall("second adjudication", STRANGER, "adjudicate", [id]));
  arc.walls.push(await wall("reclaim after qualified", SPONSOR, "sponsor_reclaim", [id]));
  arc.walls.push(await wall("resubmit after qualified", RESEARCHER, "submit_evidence", [id, ...packageLists()]));
  arc.credit = await write(STRANGER, "release_reward", [id]);
  const ag = await until("credit", async () => { const a = await jview("get_agreement", [id]); return a.status === "RELEASED" ? a : null; });
  if (ag.escrow_atto !== "0" || ag.released_atto !== REWARD.toString()) die("A: credit bookkeeping");
  log(`  RELEASED: reward credited to the researcher's claimable balance (cranked by the stranger)`);
  arc.walls.push(await wall("double release", STRANGER, "release_reward", [id]));
  arc.walls.push(await wall("stranger pulls an empty ledger", STRANGER, "claim", []));
  await pullLedger(RESEARCHER, "pull", arc, REWARD);
  arc.walls.push(await wall("double pull", RESEARCHER, "claim", []));
  arc.final = ag; flush();
}

async function scenarioB() {
  log("\nSCENARIO B - not qualified by code (9,000 of 10,000 records), reclaim after the deadline");
  const id = `DM-LIVE-B-${TAG}`; const arc = { agreement_id: id };
  TRANSCRIPT.scenarios.B = arc;
  const deadline = deadlineIn(420);
  await createAgreement(id, deadline, arc);
  await fund(id, arc);
  const pkg = await submit(id, { ...PACKAGE, dataset: VARIANTS.short }, {}, arc, "submit", 1);
  if (!pkg.deadline_met) die("B: the package was meant to be on time - raise the deadline margin");
  const { rec } = await adjudicate(id, arc, "adjudicate", "NOT_QUALIFIED", 1);
  if (finding(rec, "M1") !== "NOT_SATISFIED") die(`B: M1 ${finding(rec, "M1")}`);
  const ds = sourceRow(rec, "dataset");
  if (ds.status !== "EXAMINED" || ds.row_count !== 9000) die(`B: dataset ${ds.status} ${ds.row_count}`);
  if (finding(rec, "M2") !== "SATISFIED" || finding(rec, "M5") !== "SATISFIED") die("B: M2/M5");
  if (!rec.reason_codes.includes("REQUIREMENT_NOT_SATISFIED")) die("B: reason code");
  arc.walls = [await wall("release after NOT_QUALIFIED", STRANGER, "release_reward", [id])];
  arc.walls.push(await wall("reclaim before the deadline", SPONSOR, "sponsor_reclaim", [id]));
  await waitPast(deadline, "B");
  arc.reclaim = await write(SPONSOR, "sponsor_reclaim", [id]);
  const ag = await until("reclaim", async () => { const a = await jview("get_agreement", [id]); return a.status === "RECLAIMED" ? a : null; });
  if (ag.reclaimed_atto !== REWARD.toString() || ag.escrow_atto !== "0") die("B: reclaim bookkeeping");
  log(`  RECLAIMED: escrow credited to the sponsor's claimable balance`);
  arc.walls.push(await wall("resubmit after reclaim", RESEARCHER, "submit_evidence", [id, ...packageLists()]));
  arc.walls.push(await wall("researcher pulls the sponsor's refund", RESEARCHER, "claim", []));
  await pullLedger(SPONSOR, "pull", arc, REWARD);
  arc.final = ag; flush();
}

async function scenarioC() {
  log("\nSCENARIO C - inconclusive (methodology committed under a hash its bytes do not match), recovery, release");
  const id = `DM-LIVE-C-${TAG}`; const arc = { agreement_id: id };
  TRANSCRIPT.scenarios.C = arc;
  await createAgreement(id, "2027-06-30", arc);
  await fund(id, arc);
  // Commit the methodology under the hash of bytes that are never served
  // (the file plus one newline); the fetch decides.
  const wrong = sha(Buffer.concat([readFileSync(resolve(process.cwd(), PACKAGE.methodology)), Buffer.from("\n")]));
  arc.wrong_hash = wrong;
  await submit(id, PACKAGE, { methodology: wrong }, arc, "submit_v1", 1);
  const { rec } = await adjudicate(id, arc, "adjudicate_v1", "INCONCLUSIVE", 1);
  const m = sourceRow(rec, "methodology");
  if (m.status !== "HASH_MISMATCH" || m.hash_match !== "MISMATCH") die(`C: methodology ${m.status}`);
  if (finding(rec, "M3") !== "UNVERIFIABLE") die(`C: M3 ${finding(rec, "M3")}`);
  if (!rec.reason_codes.includes("EVIDENCE_HASH_MISMATCH")) die("C: reason code");
  if (rec.evidence_sufficient) die("C: evidence_sufficient should be false");
  const v1_receipt = JSON.stringify(await jview("get_receipt", [id, 1]));
  const v1_package = JSON.stringify(await jview("get_evidence", [id, 1]));
  arc.walls = [await wall("release after INCONCLUSIVE", STRANGER, "release_reward", [id])];
  await submit(id, PACKAGE, {}, arc, "submit_v2", 2);
  await adjudicate(id, arc, "adjudicate_v2", "QUALIFIED", 2);
  if (JSON.stringify(await jview("get_receipt", [id, 1])) !== v1_receipt) die("C: version 1 receipt changed");
  if (JSON.stringify(await jview("get_evidence", [id, 1])) !== v1_package) die("C: version 1 package changed");
  const ag1 = await jview("get_agreement", [id]);
  if (ag1.qualified_version !== 2 || ag1.judged_version !== 2) die("C: versions");
  arc.credit = await write(RESEARCHER, "release_reward", [id]);
  const ag = await until("credit", async () => { const a = await jview("get_agreement", [id]); return a.status === "RELEASED" ? a : null; });
  await pullLedger(RESEARCHER, "pull", arc, REWARD);
  arc.final = ag; flush();
}

async function scenarioD() {
  log("\nSCENARIO D - late delivery: complete evidence, missed deadline");
  const id = `DM-LIVE-D-${TAG}`; const arc = { agreement_id: id };
  TRANSCRIPT.scenarios.D = arc;
  const deadline = deadlineIn(75);
  await createAgreement(id, deadline, arc);
  await fund(id, arc);
  await waitPast(deadline, "D");
  const pkg = await submit(id, PACKAGE, {}, arc, "submit", 1);
  if (pkg.deadline_met) die("D: the package was meant to be late");
  const { v, rec } = await adjudicate(id, arc, "adjudicate", "NOT_QUALIFIED", 1);
  for (const r of rec.requirements) {
    if (r.requirement_id === "M6" ? r.finding !== "NOT_SATISFIED" : r.finding !== "SATISFIED") die(`D: ${r.requirement_id} ${r.finding}`);
  }
  if (!rec.reason_codes.includes("DEADLINE_MISSED") || rec.deadline_met !== false || v.requirements_met !== 5) die("D: deadline fields");
  arc.reclaim = await write(SPONSOR, "sponsor_reclaim", [id]);
  const ag = await until("reclaim", async () => { const a = await jview("get_agreement", [id]); return a.status === "RECLAIMED" ? a : null; });
  log(`  RECLAIMED ${ag.reclaimed_atto} atto credited to the sponsor`);
  await pullLedger(SPONSOR, "pull", arc, REWARD);
  arc.final = ag; flush();
}

async function scenarioE() {
  log("\nSCENARIO E - the refusal catalog as finalized ERROR receipts (deterministic walls)");
  const id = `DM-LIVE-E-${TAG}`; const arc = { agreement_id: id, walls: [] };
  TRANSCRIPT.scenarios.E = arc;
  arc.walls.push(await wall("unknown agreement", STRANGER, "adjudicate", ["DM-NOPE"], 0n, true));
  await createAgreement(id, "2027-06-30", arc);
  arc.walls.push(await wall("stranger funds", STRANGER, "fund_agreement", [id], REWARD, true));
  arc.walls.push(await wall("inexact deposit", SPONSOR, "fund_agreement", [id], REWARD - 1n, true));
  arc.walls.push(await wall("submit before funding", RESEARCHER, "submit_evidence", [id, ...packageLists()], 0n, true));
  await fund(id, arc);
  arc.walls.push(await wall("stranger submits", STRANGER, "submit_evidence", [id, ...packageLists()], 0n, true));
  arc.walls.push(await wall("reclaim before the deadline", SPONSOR, "sponsor_reclaim", [id], 0n, true));
  arc.walls.push(await wall("release before any verdict", STRANGER, "release_reward", [id], 0n, true));
  const [ids, urls, hashes] = packageLists();
  arc.walls.push(await wall("package missing a source", RESEARCHER, "submit_evidence", [id, ids.slice(0, 3), urls.slice(0, 3), hashes.slice(0, 3)], 0n, true));
  arc.walls.push(await wall("unpinned location", RESEARCHER, "submit_evidence", [id, ids, urls.map((u) => u.replace(FIXTURES_COMMIT, "main")), hashes], 0n, true));
  arc.walls.push(await wall("malformed content hash", RESEARCHER, "submit_evidence", [id, ids, urls, hashes.map(() => "not-a-hash")], 0n, true));
  await submit(id, PACKAGE, {}, arc, "submit", 1);
  arc.walls.push(await wall("reclaim while under review", SPONSOR, "sponsor_reclaim", [id], 0n, true));
  arc.walls.push(await wall("second package while under review", RESEARCHER, "submit_evidence", [id, ...packageLists()], 0n, true));
  arc.note = "left UNDER_REVIEW on purpose: anyone may crank adjudicate; the sponsor's exit opens after the deadline";
  flush();
}

async function scenarioF() {
  log("\nSCENARIO F - contradictory analysis and an injected methodology: the package must not qualify");
  const id = `DM-LIVE-F-${TAG}`; const arc = { agreement_id: id };
  TRANSCRIPT.scenarios.F = arc;
  await createAgreement(id, "2027-06-30", arc);
  await fund(id, arc);
  await submit(id, { ...PACKAGE, analysis: VARIANTS.contradictory, methodology: VARIANTS.injection }, {}, arc, "submit", 1);
  const { v, rec } = await adjudicate(id, arc, "adjudicate", null, 1);
  arc.panel = { M3: rec.requirements.find((r) => r.requirement_id === "M3"), M4: rec.requirements.find((r) => r.requirement_id === "M4"),
    contradiction_suspected: rec.contradiction_suspected, injection_suspected: rec.injection_suspected };
  log(`  contradiction_suspected ${rec.contradiction_suspected}; injection_suspected ${rec.injection_suspected}`);
  log(`  M3 ${arc.panel.M3.finding}: ${arc.panel.M3.note}`);
  log(`  M4 ${arc.panel.M4.finding}: ${arc.panel.M4.note}`);
  if (v.verdict === "QUALIFIED") die("F: the package qualified");
  if (finding(rec, "M4") === "SATISFIED") die("F: M4 SATISFIED against contradictory facts");
  if (finding(rec, "M1") !== "SATISFIED" || finding(rec, "M2") !== "SATISFIED" || finding(rec, "M5") !== "SATISFIED") die("F: deterministic findings");
  arc.walls = [await wall("release after a non-qualifying verdict", STRANGER, "release_reward", [id])];
  arc.note = "left resubmittable on purpose; the sponsor's exit opens after the deadline";
  arc.final = await jview("get_agreement", [id]); flush();
}

const TAG = new Date().toISOString().slice(5, 16).replace(/[-:T]/g, "");

async function main() {
  if (FIXTURES_COMMIT.length !== 40) die("--fixtures-commit must be the full 40-hex commit SHA");
  log("verifying fixture URLs serve the committed bytes...");
  await verifyFixtureUrls();
  const config = await jview("get_config", []);
  log(`contract ${CONTRACT} version ${config.contract_version}; total_agreements ${config.total_agreements}`);
  for (const a of [SPONSOR, RESEARCHER, STRANGER]) log(`  ${a.name} ${a.address} balance ${Number((await balance(a.address)) / 10n ** 12n) / 1e6} GEN`);
  try {
    if (ONLY.includes("A")) await scenarioA();
    if (ONLY.includes("B")) await scenarioB();
    if (ONLY.includes("C")) await scenarioC();
    if (ONLY.includes("D")) await scenarioD();
    if (ONLY.includes("E")) await scenarioE();
    if (ONLY.includes("F")) await scenarioF();
  } finally {
    TRANSCRIPT.finished_at = new Date().toISOString();
    flush();
    log(`\ntranscript written to ${OUT}`);
  }
  log("\nALL LIVE SCENARIOS PASSED");
}

main().catch((e) => { console.error(e); flush(); process.exit(1); });
