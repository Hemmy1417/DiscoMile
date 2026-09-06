# Fixtures: the mock research project the live scenarios cite

`project/` is "Open Drug-Discovery Dataset", a mock open-science release:

| File | Role in the agreement |
|---|---|
| `dataset/observations.csv` | the released dataset: 10,240 validated IC50 observations, columns `observation_id, compound_id, target, assay, ic50_nm, replicate, validated` |
| `dataset/schema.json` | the dataset's declared schema (not cited by the scenarios; documents the file) |
| `methodology.md` | the published methodology: assay protocol, validation procedure, replicate policy |
| `analysis.md` | the published analysis: per-target and per-assay counts computed from the released rows |
| `preprint.md` | the publication: abstract, methods, results, data availability |

`variants/` holds the negative cases the scenarios and tests use:

| File | What it breaks |
|---|---|
| `observations_short.csv` | 9,000 rows: fails a `ROW_COUNT_MIN` of 10,000 deterministically |
| `observations_missing_column.csv` | no `validated` column: fails `COLUMNS_REQUIRED` deterministically |
| `analysis_contradictory.md` | claims 25,000 observations over 12 targets: contradicts the dataset facts |
| `methodology_injection.md` | the real methodology plus a prompt-injection block aimed at the panel |

Every file is produced by `generate.py` from a fixed seed, so the analysis
quotes counts computed from the very rows it ships with. Re-running the
script reproduces the files byte for byte. The scenarios cite these files at
one commit of this repository through commit-pinned raw URLs, each bound by
the sha256 of its bytes.
