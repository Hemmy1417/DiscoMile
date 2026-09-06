/**
 * Studio Next toolkit for OpenGrant (GenLayer Studio Next, chain 61997).
 *
 *   node scripts/sn.mjs deploy <contract.py> [--key ROLE]
 *   node scripts/sn.mjs verify <address> <contract.py>
 *   node scripts/sn.mjs write <address> <fn> [argsJson] [--value atto] [--key ROLE] [--expect SUCCESS|ERROR]
 *   node scripts/sn.mjs read <address> <fn> [argsJson]
 *   node scripts/sn.mjs tx <hash>
 *   node scripts/sn.mjs balance <address>
 *   node scripts/sn.mjs fund <address> <atto>
 *   node scripts/sn.mjs code <address>
 *
 * Studio Next refuses any transaction without a fee distribution and a
 * non-zero deposit, and refuses a write that emits a transfer without the
 * message allocations its simulation derives; genlayer-js 2.0.0-rc.1 is the
 * SDK that speaks both. Keys come from .data/keys.json (gitignored; roles
 * CREATOR / YES / NO / THIRD with fields addr / pk). Nothing here prints a
 * private key.
 */
import { createAccount, createClient } from "genlayer-js";
import { studioDevnet } from "genlayer-js/chains";
import { readFileSync } from "node:fs";
import { createHash } from "node:crypto";
import { resolve } from "node:path";

export const RPC = process.env.OPENGRANT_RPC_URL ?? "https://studio-next.genlayer.com/api";
export const chain = () => ({ ...studioDevnet, name: "GenLayer Studio Next", rpcUrls: { default: { http: [RPC] } } });
export const FEE_FLOOR = 10n ** 15n;
export const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
export const sha = (s) => createHash("sha256").update(s, "utf-8").digest("hex");
export const TRANSIENT = /fetch failed|rate limit|429|-32029|timeout|ECONNRESET|socket|network|closed|terminated|other side|unknown rpc|execution slots|SSL/i;

export async function rpc(method, params) {
  const res = await fetch(RPC, {
    method: "POST",
    headers: { "content-type": "application/json", "user-agent": "Mozilla/5.0 opengrant-sn" },
    body: JSON.stringify({ jsonrpc: "2.0", id: 1, method, params }),
  });
  return res.json();
}

export function loadKeys(root = process.cwd()) {
  return JSON.parse(readFileSync(resolve(root, ".data/keys.json"), "utf-8"));
}

export function actor(name, pk) {
  const account = createAccount(pk);
  return { name, account, client: createClient({ chain: chain(), account }), address: account.address };
}

export const reader = () => createClient({ chain: chain() });

export async function view(address, fn, args = [], tries = 6) {
  const r = reader();
  for (let i = 0; ; i++) {
    try {
      return await r.readContract({ address, functionName: fn, args });
    } catch (err) {
      if (i >= tries - 1 || !TRANSIENT.test(String(err?.message ?? err))) throw err;
      await sleep(8_000 * (i + 1));
    }
  }
}

/** The leader entry of a finalized transaction's receipt array. */
export function leaderOf(t) {
  const receipts = t?.consensus_data?.leader_receipt ?? [];
  const arr = Array.isArray(receipts) ? receipts : [receipts];
  return arr.find((r) => r?.mode !== "validator") ?? arr[0];
}

export function votesOf(t) {
  // Studio Next: consensus_data.votes is { validatorAddress: "agree" | "idle" | "disagree" }.
  const votes = t?.consensus_data?.votes;
  if (votes && typeof votes === "object" && !Array.isArray(votes)) {
    return Object.values(votes).map((v) => String(v).toUpperCase());
  }
  const names = t?.consensus_data?.validator_votes_name;
  if (Array.isArray(names)) return names.map(String);
  return [];
}

/** Decode a GenVM result blob (base64; first byte is a tag, the rest is the
 * contract's text - a UserError message on an ERROR receipt). */
export function decodeResult(raw) {
  if (!raw || typeof raw !== "string") return "";
  try {
    const buf = Buffer.from(raw, "base64");
    if (buf.length === 0) return "";
    return buf.subarray(1).toString("utf-8");
  } catch { return ""; }
}

/** The contract's own refusal text inside a fee-simulation error, walking
 * viem's cause chain for the JSON-RPC data the Studio attaches. */
export function refusalText(err) {
  const seen = new Set();
  let e = err;
  for (let i = 0; i < 8 && e && !seen.has(e); i++) {
    seen.add(e);
    const data = e?.data ?? e?.cause?.data;
    const r = data?.receipt?.result ?? data?.result;
    if (typeof r === "string") { const t = decodeResult(r); if (t) return t; }
    const m = String(e?.details ?? e?.shortMessage ?? "");
    const b64 = m.match(/[A-Za-z0-9+/]{16,}={0,2}/);
    if (b64) { const t = decodeResult(b64[0]); if (t && /\[(EXPECTED|LLM_ERROR|TRANSIENT|EXTERNAL)\]/.test(t)) return t; }
    e = e?.cause;
  }
  return "";
}

/** Wait for FINALIZED; return the tx plus a decoded summary. */
export async function landed(hash, label = "tx", maxMinutes = 13) {
  const rounds = Math.ceil((maxMinutes * 60) / 10);
  for (let i = 0; i < rounds; i++) {
    await sleep(10_000);
    let t = null;
    try { t = (await rpc("eth_getTransactionByHash", [hash])).result; } catch { continue; }
    const status = t?.status ?? t?.statusName ?? "";
    if (status === "FINALIZED") {
      const leader = leaderOf(t);
      const summary = {
        hash, status, result_name: t?.result_name ?? "", leader: leader?.execution_result ?? "",
        votes: votesOf(t), stderr_tail: String(leader?.genvm_result?.stderr ?? "").slice(-800),
        result_text: decodeResult(leader?.result).slice(0, 300),
        contract_address: t?.data?.contract_address ?? null,
      };
      return { tx: t, summary };
    }
    if (status === "CANCELED" || status === "UNDETERMINED") {
      return { tx: t, summary: { hash, status, result_name: t?.result_name ?? "", leader: "", votes: votesOf(t), stderr_tail: "" } };
    }
    if (i % 6 === 5) console.log(`   ${label}: still ${status || "pending"} …`);
  }
  throw new Error(`${label}: no finality after ${maxMinutes} min`);
}

export async function feesFor(a, address, fn, args, value) {
  const est = await a.client.estimateTransactionFeesForWrite({ address, functionName: fn, args, value });
  const feeValue = est.feeValue > FEE_FLOOR ? est.feeValue : FEE_FLOOR;
  return { distribution: est.distribution, feeValue, messageAllocations: est.messageAllocations };
}

/**
 * Send a write and wait for finality. A refused write usually dies in the
 * fee SIMULATION (JSON-RPC -32000 with the contract's text base64-inside);
 * we fall back to a plain estimate so the refusal lands on-chain as a
 * finalized ERROR receipt, which is the evidence a wall needs.
 */
export async function write(a, address, fn, args = [], value = 0n) {
  let fees;
  let preflight = null;
  try {
    fees = await feesFor(a, address, fn, args, value);
  } catch (err) {
    preflight = String(err?.message ?? err).slice(0, 300);
    const est = await a.client.estimateTransactionFees();
    fees = { distribution: est.distribution, feeValue: est.feeValue > FEE_FLOOR ? est.feeValue : FEE_FLOOR };
  }
  const hash = await a.client.writeContract({ address, functionName: fn, args, value, fees });
  const { summary } = await landed(hash, fn);
  if (preflight) summary.preflight = preflight;
  return summary;
}

export async function deploy(a, sourcePath) {
  const code = readFileSync(sourcePath, "utf-8");
  if (code.includes("\r")) throw new Error(`${sourcePath} carries CR bytes - normalize to LF before deploying`);
  console.log(`deploying ${sourcePath} (sha256 ${sha(code)}) as ${a.address} on chain ${chain().id}`);
  const est = await a.client.estimateTransactionFees();
  const feeValue = est.feeValue > FEE_FLOOR ? est.feeValue : FEE_FLOOR;
  const hash = await a.client.deployContract({ code, args: [], fees: { distribution: est.distribution, feeValue } });
  console.log(`deploy tx ${hash}`);
  const { summary } = await landed(hash, "deploy");
  return { ...summary, source_sha256: sha(code) };
}

export async function liveCode(address) {
  const r = await rpc("gen_getContractCode", [address]);
  const raw = typeof r.result === "string" ? r.result : (r.result?.code ?? "");
  return raw.startsWith("# ") ? raw : Buffer.from(raw, "base64").toString("utf-8");
}

const isMain = process.argv[1] && resolve(process.argv[1]) === resolve(new URL(import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1"));
if (isMain) {
  const argv = process.argv.slice(2);
  const opt = (name, dflt) => { const i = argv.indexOf(name); return i >= 0 ? argv[i + 1] : dflt; };
  const positional = argv.filter((x, i) => !x.startsWith("--") && !(i > 0 && argv[i - 1].startsWith("--")));
  const [cmd, ...rest] = positional;
  const role = opt("--key", "CREATOR");
  const out = (o) => console.log(JSON.stringify(o, (k, v) => (typeof v === "bigint" ? v.toString() : v), 2));
  if (cmd === "deploy") {
    const a = actor(role, loadKeys()[role].pk);
    out(await deploy(a, rest[0]));
  } else if (cmd === "verify") {
    const live = await liveCode(rest[0]);
    const repo = readFileSync(rest[1], "utf-8");
    console.log(`live sha256 ${sha(live)} (${live.length} chars)`);
    console.log(`repo sha256 ${sha(repo)} (${repo.length} chars)`);
    if (live !== repo) { console.error("verify: NOT byte-identical"); process.exit(1); }
    console.log("verify: byte-for-byte identical");
  } else if (cmd === "write") {
    const a = actor(role, loadKeys()[role].pk);
    const args = rest[2] ? JSON.parse(rest[2]) : [];
    const value = BigInt(opt("--value", "0"));
    const s = await write(a, rest[0], rest[1], args, value);
    out(s);
    const expect = opt("--expect", null);
    if (expect && s.leader !== expect) { console.error(`expected leader ${expect}, got ${s.leader}`); process.exit(1); }
  } else if (cmd === "read") {
    const args = rest[2] ? JSON.parse(rest[2]) : [];
    const v = await view(rest[0], rest[1], args);
    console.log(typeof v === "string" ? v : JSON.stringify(v, (k, x) => (typeof x === "bigint" ? x.toString() : x)));
  } else if (cmd === "tx") {
    const t = (await rpc("eth_getTransactionByHash", [rest[0]])).result;
    out({ status: t?.status ?? t?.statusName, result_name: t?.result_name, leader: leaderOf(t)?.execution_result, votes: votesOf(t), result_text: decodeResult(leaderOf(t)?.result).slice(0, 300), stderr_tail: String(leaderOf(t)?.genvm_result?.stderr ?? "").slice(-800), contract_address: t?.data?.contract_address ?? null });
  } else if (cmd === "balance") {
    const r = await rpc("eth_getBalance", [rest[0], "latest"]);
    console.log(BigInt(r.result).toString());
  } else if (cmd === "fund") {
    out(await rpc("sim_fundAccount", [rest[0], Number(rest[1])]));
  } else if (cmd === "code") {
    process.stdout.write(await liveCode(rest[0]));
  } else {
    console.error("usage: deploy|verify|write|read|tx|balance|fund|code");
    process.exit(2);
  }
}
