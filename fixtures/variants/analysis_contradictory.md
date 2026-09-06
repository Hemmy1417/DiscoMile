# Analysis

## Summary

This analysis was computed on the released dataset exactly as shipped. The
dataset contains 25,000 validated observations covering 12
protein targets and 2 assay formats, drawn from 2365
distinct compounds.

## Observations per target

| Target | Observations |
|---|---|
| EGFR | 1,257 |
| BRAF | 1,276 |
| KRAS-G12C | 1,305 |
| PIK3CA | 1,268 |
| ALK | 1,281 |
| MEK1 | 1,325 |
| CDK4 | 1,235 |
| JAK2 | 1,293 |

## Observations per assay format

| Assay | Observations |
|---|---|
| biochemical_ic50 | 5,187 |
| cell_viability | 5,053 |

## Potency

4,287 observations (41.9% of the dataset) report an
IC50 below 100 nM. Potency is distributed log-uniformly across the measured
range by construction of the screening library, so the potent fraction should
be read as a property of the library rather than a discovery.

## Reproducibility

Every number above is recomputed by counting rows of the released CSV grouped
by the `target` and `assay` columns; no observation outside the released file
enters the analysis.
