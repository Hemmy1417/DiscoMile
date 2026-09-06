#!/usr/bin/env python3
"""Mutation kill check: prove the Direct Mode suite pins each load-bearing
guard, not merely that the code passes today.

For each mutation, the contract is copied to a scratch directory with ONE
guard mechanically broken, and the whole Direct Mode suite runs against
the copy. A mutation is KILLED when the suite fails, SURVIVED when it
passes (an unpinned guard). The run starts with an accept-control: the
unmodified copy must pass, otherwise every kill would be vacuous.

Anchors are code TEXT, never line numbers. An anchor that is not found is
reported as ANCHOR MISSING - that means the guard itself moved or was
deleted, which is its own finding. Every mutation here is observable: a
mutation that an earlier guard makes unobservable (an equivalent mutant)
is a sweep bug, not a suite gap, and does not belong in this list.

Run:  python scripts/mutation_check.py
"""

from __future__ import annotations

import pathlib
import shutil
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]

MUTATIONS = [
    # -- verdict derivation -------------------------------------------------------
    ("late package no longer NOT_QUALIFIED",
     "    if not deadline_met:\n        return VERDICT_NOT_QUALIFIED",
     "    if False:\n        return VERDICT_NOT_QUALIFIED"),
    ("NOT_SATISFIED no longer yields NOT_QUALIFIED",
     "        if finding == FINDING_NOT_SATISFIED:\n            return VERDICT_NOT_QUALIFIED",
     "        if finding == FINDING_NOT_SATISFIED:\n            pass"),
    ("UNVERIFIABLE no longer yields INCONCLUSIVE",
     "        if finding == FINDING_UNVERIFIABLE:\n            return VERDICT_INCONCLUSIVE",
     "        if finding == FINDING_UNVERIFIABLE:\n            pass"),
    # -- the dataset kinds decided in code -----------------------------------------
    ("record-count minimum no longer enforced",
     "        return FINDING_SATISFIED if int(row[\"row_count\"]) >= minimum else FINDING_NOT_SATISFIED",
     "        return FINDING_SATISFIED"),
    ("required column absence no longer NOT_SATISFIED",
     "            if name not in columns:\n                return FINDING_NOT_SATISFIED",
     "            if False:\n                return FINDING_NOT_SATISFIED"),
    ("dataset facts computed on an unexamined source",
     "    if row[\"status\"] != SRC_EXAMINED:\n        return FINDING_UNVERIFIABLE\n    if kind == KIND_ROW_COUNT_MIN:",
     "    if kind == KIND_ROW_COUNT_MIN:"),
    ("ACCESSIBLE no longer NOT_SATISFIED for a missing source",
     "    if status in (SRC_NOT_FOUND, SRC_EMPTY):\n        return FINDING_NOT_SATISFIED",
     "    if False:\n        return FINDING_NOT_SATISFIED"),
    ("deadline requirement no longer follows deadline_met",
     "        return FINDING_SATISFIED if deadline_met else FINDING_NOT_SATISFIED",
     "        return FINDING_SATISFIED"),
    ("header row counted as a record",
     "    return (len(non_empty) - 1, columns[:MAX_COLUMNS])",
     "    return (len(non_empty), columns[:MAX_COLUMNS])"),
    ("empty records counted",
     "    non_empty = [r for r in records if r.strip() != \"\"]",
     "    non_empty = list(records)"),
    ("quoted newlines split records",
     "        if line.count('\"') % 2 == 1:\n            open_quote = not open_quote",
     "        if False:\n            open_quote = not open_quote"),
    # -- evidence integrity --------------------------------------------------------
    ("content hash not verified before facts or prompt",
     "    if hashlib.sha256(body).hexdigest() != content_hash:\n        return (SRC_HASH_MISMATCH, b\"\")",
     "    if False:\n        return (SRC_HASH_MISMATCH, b\"\")"),
    ("404 no longer NOT_FOUND",
     "    if status == 404:\n        return (SRC_NOT_FOUND, b\"\")",
     "    if False:\n        return (SRC_NOT_FOUND, b\"\")"),
    ("size bound removed",
     "    if len(body) > DATA_BYTES_CAP:\n        return (SRC_TOO_LARGE, b\"\")",
     "    if False:\n        return (SRC_TOO_LARGE, b\"\")"),
    ("unpinned repository locations accepted",
     "        if not _is_hex(sha, 40) or not _valid_path(path):\n            return None",
     "        if not _valid_path(path):\n            return None"),
    ("zenodo locations without download=1 accepted",
     "        if not rest.endswith(\"?download=1\"):\n            return None",
     "        if False:\n            return None"),
    # -- the model's answers -----------------------------------------------------------
    ("injection or contradiction flag no longer forces UNVERIFIABLE",
     "        if contradiction or injection:\n            finding = FINDING_UNVERIFIABLE",
     "        if False:\n            finding = FINDING_UNVERIFIABLE"),
    ("off-vocabulary semantic finding snaps to SATISFIED",
     "        finding = SEMANTIC_MAP.get(label, FINDING_UNVERIFIABLE)",
     "        finding = SEMANTIC_MAP.get(label, FINDING_SATISFIED)"),
    ("semantic requirement without any document no longer UNVERIFIABLE",
     "        if len(documents) == 0:\n            requirement_rows.append({",
     "        if False:\n            requirement_rows.append({"),
    # -- consensus -----------------------------------------------------------------------
    ("validator stops comparing source rows",
     "        for key in (\"status\", \"hash_match\", \"byte_count\", \"row_count\", \"column_count\"):\n            if mine[key] != other[key]:\n                return False",
     "        pass"),
    ("validator stops comparing requirement findings",
     "        if own[\"requirements\"][i][\"finding\"] != theirs[\"requirements\"][i][\"finding\"]:\n            return False",
     "        if False:\n            return False"),
    ("gate no longer recomputes the verdict",
     "    if payload[\"verdict\"] != _derive_verdict(payload[\"deadline_met\"], findings):\n        return None",
     "    if False:\n        return None"),
    ("gate no longer pins deadline_met",
     "    if type(payload[\"deadline_met\"]) is not bool \\\n            or payload[\"deadline_met\"] != bool(deadline_met):\n        return None",
     "    if type(payload[\"deadline_met\"]) is not bool:\n        return None"),
    ("gate accepts a bool as the version",
     "    if type(payload[\"version\"]) is not int or payload[\"version\"] != int(version):",
     "    if not isinstance(payload[\"version\"], int) or payload[\"version\"] != int(version):"),
    ("gate no longer recomputes deterministic findings",
     "            expected = _deterministic_finding(req, source_rows, {}, payload[\"deadline_met\"])\n            if row[\"finding\"] != expected:\n                return None",
     "            pass"),
    ("boundary validation removed: ratified text persisted unchecked",
     "    if payload is None:\n        raise gl.vm.UserError(ERROR_LLM + \" malformed ratified payload\")",
     "    if payload is None:\n        payload = json.loads(str(text))"),
    # -- deterministic state --------------------------------------------------------------
    ("deadline no longer taken at commitment",
     "        deadline_met = _instant_key(now) <= _instant_key(ag.deadline)",
     "        deadline_met = True"),
    ("exact deposit check removed",
     "        if value != int(ag.reward_atto):\n            raise gl.vm.UserError(ERROR_EXPECTED + \" deposit must equal the reward exactly\")",
     "        if False:\n            raise gl.vm.UserError(ERROR_EXPECTED + \" deposit must equal the reward exactly\")"),
    ("sponsor check on fund removed",
     "        if self._sender() != ag.sponsor:\n            raise gl.vm.UserError(ERROR_EXPECTED + \" only the sponsor funds\")",
     "        if False:\n            raise gl.vm.UserError(ERROR_EXPECTED + \" only the sponsor funds\")"),
    ("researcher check on submit removed",
     "        if self._sender() != ag.researcher:\n            raise gl.vm.UserError(ERROR_EXPECTED + \" only the researcher submits\")",
     "        if False:\n            raise gl.vm.UserError(ERROR_EXPECTED + \" only the researcher submits\")"),
    ("release no longer requires QUALIFIED",
     "        if ag.status != STATUS_ADJUDICATED or ag.verdict != VERDICT_QUALIFIED:\n            raise gl.vm.UserError(ERROR_EXPECTED + \" reward is releasable only after QUALIFIED\")",
     "        if ag.status != STATUS_ADJUDICATED:\n            raise gl.vm.UserError(ERROR_EXPECTED + \" reward is releasable only after QUALIFIED\")"),
    ("reclaim allowed while under review",
     "        if ag.status == STATUS_UNDER_REVIEW:\n            raise gl.vm.UserError(ERROR_EXPECTED + \" an evidence package is under review; adjudicate it first\")",
     "        if False:\n            raise gl.vm.UserError(ERROR_EXPECTED + \" an evidence package is under review; adjudicate it first\")"),
    ("reclaim allowed after QUALIFIED",
     "        if ag.status == STATUS_ADJUDICATED and ag.verdict == VERDICT_QUALIFIED:\n            raise gl.vm.UserError(ERROR_EXPECTED + \" agreement qualified; the reward belongs to the researcher\")",
     "        if False:\n            raise gl.vm.UserError(ERROR_EXPECTED + \" agreement qualified; the reward belongs to the researcher\")"),
    ("reclaim allowed before the deadline",
     "        if _instant_key(now) <= _instant_key(ag.deadline):\n            raise gl.vm.UserError(ERROR_EXPECTED + \" the deadline has not passed\")",
     "        if False:\n            raise gl.vm.UserError(ERROR_EXPECTED + \" the deadline has not passed\")"),
    ("release does not zero the escrow (double release)",
     "        ag.escrow_atto = u256(0)\n        ag.released_atto = u256(amount)",
     "        ag.released_atto = u256(amount)"),
    ("reward credited to the caller instead of the researcher",
     "        self._credit(ag.researcher, amount)",
     "        self._credit(self._sender(), amount)"),
    ("refund credited to the researcher instead of the sponsor",
     "        self._credit(ag.sponsor, amount)",
     "        self._credit(ag.researcher, amount)"),
    ("claim does not zero the ledger (double pull)",
     "        self.claimable[sender] = u256(0)\n        self.ledger_total_atto",
     "        self.ledger_total_atto"),
    ("claim pays with nothing claimable",
     "        if amount <= 0:\n            raise gl.vm.UserError(ERROR_EXPECTED + \" nothing claimable\")",
     "        if False:\n            raise gl.vm.UserError(ERROR_EXPECTED + \" nothing claimable\")"),
    ("package no longer needs every declared source",
     "        if count != len(declared):\n            raise gl.vm.UserError(ERROR_EXPECTED + \" an evidence package covers every declared source exactly once\")",
     "        if False:\n            raise gl.vm.UserError(ERROR_EXPECTED + \" an evidence package covers every declared source exactly once\")"),
    ("package limit removed",
     "        if int(ag.package_count) >= MAX_PACKAGES:",
     "        if False:"),
    ("resubmission allowed after QUALIFIED",
     "        if ag.status == STATUS_ADJUDICATED and ag.verdict == VERDICT_QUALIFIED:\n            raise gl.vm.UserError(ERROR_EXPECTED + \" agreement already qualified\")",
     "        if False:\n            raise gl.vm.UserError(ERROR_EXPECTED + \" agreement already qualified\")"),
    ("path traversal accepted",
     "        if segment in (\"\", \".\", \"..\"):\n            return False",
     "        if segment == \"\":\n            return False"),
    ("deadline in the past accepted at creation",
     "        if _instant_key(deadline_norm) <= _instant_key(now):\n            raise gl.vm.UserError(ERROR_EXPECTED + \" deadline must be in the future\")",
     "        if False:\n            raise gl.vm.UserError(ERROR_EXPECTED + \" deadline must be in the future\")"),
    ("researcher may equal the sponsor",
     "        if researcher_hex == sponsor:\n            raise gl.vm.UserError(ERROR_EXPECTED + \" researcher must differ from the sponsor\")",
     "        if False:\n            raise gl.vm.UserError(ERROR_EXPECTED + \" researcher must differ from the sponsor\")"),
    ("dataset requirement may name a text source",
     "                if kind in DATASET_KINDS and source_kind_by_id[source_ref] != SOURCE_DATASET:",
     "                if False:"),
]


def run_suite(workdir: pathlib.Path) -> bool:
    completed = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/direct", "-q", "-x",
         "-p", "no:cacheprovider", "--no-header"],
        cwd=workdir, capture_output=True, text=True)
    return completed.returncode == 0


def main() -> None:
    source = (ROOT / "contracts" / "discovery_milestone.py").read_text(encoding="utf-8")
    scratch = pathlib.Path(tempfile.mkdtemp(prefix="discovery-milestone-mutation-"))
    work = scratch / "repo"
    shutil.copytree(ROOT, work, ignore=shutil.ignore_patterns(
        ".git", "__pycache__", ".pytest_cache", "node_modules", ".data", "deploy"))
    target = work / "contracts" / "discovery_milestone.py"

    print("accept-control: unmodified copy must pass ...", flush=True)
    if not run_suite(work):
        print("CONTROL FAILED: the unmodified suite does not pass; aborting")
        sys.exit(1)
    print("control green\n")

    killed = survived = missing = 0
    for name, old, new in MUTATIONS:
        if source.count(old) != 1:
            print(f"ANCHOR MISSING ({source.count(old)} hits): {name}")
            missing += 1
            continue
        target.write_text(source.replace(old, new), encoding="utf-8", newline="\n")
        passed = run_suite(work)
        target.write_text(source, encoding="utf-8", newline="\n")
        if passed:
            print(f"SURVIVED: {name}")
            survived += 1
        else:
            print(f"killed:   {name}")
            killed += 1
    shutil.rmtree(scratch, ignore_errors=True)
    print(f"\nmutations: {killed} killed, {survived} survived, {missing} anchor missing")
    sys.exit(0 if survived == 0 and missing == 0 else 1)


if __name__ == "__main__":
    main()
