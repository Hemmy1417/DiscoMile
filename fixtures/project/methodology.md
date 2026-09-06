# Methodology

## Objective

This document describes how the Open Drug-Discovery Dataset was produced. The
dataset reports half-maximal inhibitory concentrations (IC50) for small-molecule
compounds against eight protein targets (EGFR, BRAF, KRAS-G12C, PIK3CA, ALK, MEK1, CDK4, JAK2) in two assay
formats.

## Compound library

2365 distinct compounds were drawn from an in-house library. Each
compound carries a stable identifier of the form C-00000; identifiers are
opaque and do not encode structure.

## Assay protocol

Two assay formats were run for every compound-target pair that passed the
solubility screen:

- `biochemical_ic50`: a purified-enzyme kinase assay read by fluorescence at
  eight concentrations in half-log steps from 1 nM to 50 uM, fitted with a
  four-parameter logistic model.
- `cell_viability`: a 72-hour cell-based viability assay in a target-dependent
  line, same concentration series, same fit.

## Validation procedure

An observation is recorded as validated only when all of the following hold:
the fit converged with a Hill slope between 0.5 and 2.0; the top and bottom
plateaus were within the plate controls; and the replicate agreed with its
sibling replicates within 0.5 log units. Observations that fail any check are
withheld from the released dataset, so the `validated` column of the released
file is uniformly true.

## Replicate policy

Each compound-target-assay combination was measured in up to three
biological replicates, reported as separate observations with `replicate`
1, 2 or 3. Replicates are never averaged in the released file; downstream
users may aggregate as they see fit.

## Release

The released dataset contains 10,240 validated observations in one CSV file
with the columns observation_id, compound_id, target, assay, ic50_nm, replicate, validated. Values are in nanomolar. The file is
released alongside this methodology and the analysis under a permissive
licence.
