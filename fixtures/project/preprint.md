# Open Drug-Discovery Dataset: 10,240 validated IC50 observations across eight kinase targets

## Abstract

We release an open dataset of 10,240 validated half-maximal inhibitory
concentration measurements for 2365 small molecules against eight
protein targets in biochemical and cell-based formats. Every observation
passed a fixed validation procedure described in the accompanying
methodology; failing observations were withheld rather than flagged. The
dataset, methodology and analysis are released together so that the
analysis can be recomputed from the released rows.

## Methods

See the methodology document released with the dataset: two assay formats,
an eight-point half-log concentration series, four-parameter logistic fits,
and a validation procedure covering fit quality, plate controls and replicate
agreement.

## Results

See the analysis document: observation counts per target and per assay
format, and the potent fraction of the library.

## Data availability

The dataset is released as a single CSV file with the columns
observation_id, compound_id, target, assay, ic50_nm, replicate, validated, alongside the methodology and the analysis, under a
permissive licence.
