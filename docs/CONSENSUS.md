# Consensus Design

One nondeterministic round per evidence package, `gl.vm.run_nondet` in
`adjudicate`. Everything else in the contract is deterministic and never
runs inside the round; the money paths (credits and the one pull payment)
included.

## 1. What the round decides

The round decides meaning: whether the committed documents demonstrate each
semantic requirement, and whether the evidence contradicts itself. It also
carries, as compared facts, everything the leader and the validators can
each establish for themselves from the committed bytes: whether each source
was fetched with the committed hash, how many records a dataset holds and
which columns it carries. The deterministic requirements are recomputed by
every node from those facts; the verdict is recomputed by every node from
the findings. Nothing about money, identity or the deadline is decided in
the round: the reward is a constant of the terms, `deadline_met` was frozen
at commitment from the transaction clock, and the parties were fixed at
creation.

## 2. Leader and validators run the same procedure

The leader authors the complete result by running `_node_derivation` once:
fetch every committed source, verify hashes, parse dataset facts, decide the
deterministic requirements, prompt once for the semantic ones, assemble the
payload in code. Every validator runs the identical function from its own
vantage - its own fetches, its own hashes, its own parse, its own prompt -
and then compares. Reproduction never consults leader content; the leader
payload is only the comparison target.

## 3. The equivalence rule

A validator ratifies a leader result only when, after reproducing the
procedure, these fields agree exactly:

| Compared | Why it is decision-critical |
|---|---|
| `verdict` | what the deterministic contract acts on |
| `deadline_met` | a frozen input; a ratified payload cannot claim another |
| every requirement `finding`, in order | what the verdict derives from |
| per source: `status`, `hash_match`, `byte_count`, `row_count`, `column_count` | whether each node read the same bytes and parsed the same facts |

Never compared: requirement `note` text and the `summary`. Two honest
validators may describe the same finding in different words; they may not
disagree on the finding. Reason codes and the summary are recomputed by code
from compared fields, so they cannot differ once the fields agree.

## 4. The structural gate before reproduction

`_parse_payload` runs on the leader's text before any validator spends a
fetch or a prompt. It refuses a payload that is not the exact schema (key
sets, exact types - a bool never passes as an int), that cites the wrong
agreement, version or evidence hash, that reorders, drops or invents a
requirement or source row, that carries dataset facts on an excluded or
non-dataset source, that reports a deterministic finding the source rows do
not support, that reports a semantic finding with no examined document, or
whose verdict, counts, evidence sufficiency, reason codes or summary do not
recompute from its own rows. A refused payload is a veto without
reproduction (`tests/direct/test_equivalence.py`, the forgery matrix). The
same parser runs again on the ratified text at the contract boundary before
state changes (`_boundary_validate`); a malformed ratified payload reverts
with the package still `PENDING`.

The gate proves well-formedness only. A payload can be internally consistent
and false - a leader claiming 9,000 records with an honestly re-derived
`NOT_QUALIFIED` - and that is what reproduction catches: the validator's own
record count differs, the source rows disagree, veto.

## 5. The result table for leader failures

| Leader result | Validator behaviour |
|---|---|
| `Return(text)` | structural gate, then reproduction and comparison |
| `UserError("[LLM_ERROR] ...")` | always disagree: unusable model output must rotate the leader, never lock bad state |
| `UserError("[TRANSIENT] ...")` | agree only if the validator's own reproduction was transient too |
| `UserError("[EXPECTED] ...")`, `UserError("[EXTERNAL] ...")` | agree only on the identical fixed message |
| anything else (a VM error, an unexpected exception) | disagree |

A validator's own exception propagates; `run_nondet` treats it as a
disagreement. Fail closed.

## 6. What disagreement means

Validator disagreement is a protocol-level outcome, not a verdict. The round
fails, nothing is written, the package stays `PENDING`, and anyone may crank
`adjudicate` again. Honest validators can disagree on a genuinely borderline
semantic criterion; the remedy is a sharper criterion or better evidence,
never a manufactured verdict. The live driver records every
`MAJORITY_DISAGREE` it meets and cranks again (`docs/DEPLOYMENT.md`).

## 7. Prompt discipline

The synthesis prompt is one fixed constant (`SYNTHESIS_PROMPT_HEADER`)
followed by one canonical JSON blob declared untrusted. The blob holds the
agreement's title and objective, the semantic requirements with their
criteria, the dataset facts (computed by code, declared authoritative over
any claim a document makes), and the examined documents. The dataset bytes
themselves never reach the model. The answer is requested as JSON
(`response_format="json"`) and normalized by the same fixed pipeline on
every node. `docs/SECURITY.md` section 4 covers the injection defenses.

## 8. Why the facts travel in the compared rows

Record and column counts are deterministic functions of bytes, so they
belong with `status` and `hash_match` in the compared rows rather than in
the notes: a leader cannot report a record count its own bytes do not have
without every validator's parse disagreeing. It also makes the receipt
auditable by anyone with the bytes - the count in the receipt is the count
the committed file has, and `tests/direct/test_dataset.py` fixes the
parsing rules the count follows.
