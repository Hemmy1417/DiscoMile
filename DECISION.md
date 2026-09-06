# Decision Record: why Discovery-Milestone is a standalone Intelligent Contract

## Primitive thesis

Discovery-Milestone is a reusable GenLayer primitive that adjudicates
whether a researcher delivered the milestone they committed to, from
evidence committed to immutable locations and judged against acceptance
criteria frozen before the work, and that executes the predefined financial
consequence deterministically.

The question it answers is the one every research funder, grant program and
science DAO keeps re-implementing by hand: *did they actually deliver what
they promised?* A funding contract can hold money and check that a date
passed; it cannot read a methodology and decide whether the assay protocol
it promised is there, or whether the analysis was computed on the dataset
that was released.

## What it is not

It is not an AI scientist and not an AI peer reviewer. Nothing in the
contract decides whether a discovery is true, whether a paper is
scientifically valid, or whether a result would survive review. The
question is narrower and contractual - does the committed evidence
demonstrate the commitment that was agreed before the work? - and the
prompt says so to the panel in as many words. That narrowness is the
design: it is what makes the verdict defensible, and it is what makes the
verdict something a contract can act on.

## Why deterministic smart contracts are insufficient

A normal contract compares what it can parse. This one parses everything
it can: it counts a dataset's records, reads its header, checks that a
committed file is there with the committed bytes, and decides the deadline
from the transaction clock. Those four requirement kinds never touch a
model. What no deterministic contract can do is decide that a methodology
"describes the validation procedure", that an analysis "reports results
computed on the released dataset", or that two documents contradict each
other on a fact the milestone depends on. Milestone acceptance in research
is a judgment over prose spread across several documents, anchored to facts
in the data. Discovery-Milestone keeps the facts in code and hands only the
judgment to consensus.

## Why one LLM is insufficient

A backend could ask one model. Then whoever operates that backend, or the
model it happens to run, is the authority on whether a researcher gets paid
- a single point that can be wrong, can be gamed by a note to "automated
reviewers" inside a methodology file, and cannot be audited by the parties.
A model also produces well-formed answers with perfect confidence, and a
well-formed answer is not a correct one.

## Why GenLayer is required

GenLayer lets the semantic judgment be proposed by one node and
independently reproduced by others before it becomes state. In
Discovery-Milestone every validator re-fetches the committed sources,
re-verifies their hashes, re-parses the dataset facts, re-judges the
semantic requirements with those facts in front of it, and re-derives the
verdict in code, then votes on the decision-critical fields. A leader that
reports 10,000 records where the file has 9,000, or a validation procedure
that the methodology does not describe, is vetoed by validators that read
the same bytes. Prose differences are tolerated; decision differences are
not.

The delete-GenLayer test: without GenLayer, one operator, backend or model
would decide whether the milestone was delivered and therefore whether the
reward moves. Discovery-Milestone removes that single adjudication
authority by making the decision subject to validator consensus, with
deterministic contract code deciding what the ratified verdict is allowed
to do with the escrow.

## Reuse

Three materially different consumers run on the unchanged primitive
(`docs/INTEGRATION.md`, `examples/consumer.py`):

1. **Tranche-based research grant** - the next tranche opens on
   `QUALIFIED`, the grant closes on `NOT_QUALIFIED`, waits on
   `INCONCLUSIVE`.
2. **Reproducibility bounty** - the bounty's own escrow unlocks on
   `QUALIFIED` for an agreement whose requirements are the reproduction
   artifacts.
3. **Open-science scoring** - per-requirement findings and evidence
   sufficiency score partial delivery for competitions, maintenance
   programs and research DAO contributions.

Each reads one view, pins the terms hash and the parties, and applies its
own rules. Open-data releases, protocol research programs and collaborative
milestones fit the same shape; the contract stays the same and only the
Discovery Agreement changes. The primitive itself carries the minimal
economic consequence - escrow in, reward credited, one pull out - that
makes the verdict load-bearing rather than advisory.

## Scope

There is no frontend, no backend, no database and no indexer. The escrow is
deliberately minimal: exactly the reward in, exactly the reward credited to
exactly the named researcher, or back to the sponsor after the deadline,
and one pull payment out. Anything richer - tranches, bonuses, multi-party
splits, reputation - is a downstream consumer's business. Two Node scripts
exist for reproducible deployment and live evidence on Studio Next, because
the network's fee distribution is only spoken by genlayer-js; nothing else.

## Risks

The hardest technical risks, and what the design does about them:

| Risk | Treatment |
|---|---|
| A document that claims what the data does not show | the record count and the columns are parsed from the bytes by every node and handed to the panel as authoritative facts; a stated count that disagrees is a contradiction, and a contradiction is `UNVERIFIABLE`, never a reward |
| An excluded document read as a missing deliverable (found live on the first deployment: a hash-mismatched methodology was judged "absent" and the package NOT_QUALIFIED where the protocol promises INCONCLUSIVE) | a semantic requirement names the document it is judged over; when that committed document cannot be examined the requirement is `UNVERIFIABLE` by code, and the panel is told which sources were excluded and why |
| Semantic disagreement on a borderline criterion | the vocabulary forces `UNVERIFIABLE` when evidence is insufficient; `UNVERIFIABLE` is `INCONCLUSIVE`, resubmittable, never a payout; persistent disagreement surfaces as rotation, never as a verdict |
| A well-formed but false leader result | structural gate before reproduction, full reproduction, decision-field comparison on facts and findings, boundary re-validation; a fifty-forgery matrix in the tests |
| Prompt injection inside a document | fixed instruction shell, JSON-fenced untrusted data, explicit rules, an injection flag that forces `UNVERIFIABLE` |
| Evidence substitution | only immutable locations are admitted (commit-pinned repository files, Zenodo record files), bytewise sha256 before any fact or prompt, append-only packages |
| Forgeable timestamps | the deadline is decided by the transaction clock at commitment, never by a document or a model |
| Escrow stranding or double payment | full reservation at funding, credits settled before any transfer, one ungated pull payment with the ledger zeroed first, permissionless release crank, sponsor's deterministic exit after the deadline, wei conservation asserted on every path |
| A transfer inside a clock-gated write cannot be allocated on Studio Next (the fee simulation runs with a predefined transaction datetime) | the pull-payment split - gates credit, `claim()` transfers - so the transfer's simulation never needs a clock |
| Runner and tooling drift | one pinned runner (GenVM v0.6, Studio Next); the deployment is byte-verified and exercised live because local semantic tooling cannot load that runner |
