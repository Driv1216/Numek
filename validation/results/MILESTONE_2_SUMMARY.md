# Milestone 2 Validation Summary

Generated and verified on 2026-06-14.

## Public Corpus

| Dataset | Rows | Columns | DataTrust runtime | Overall | Risk band |
|---|---:|---:|---:|---:|---|
| UCI German Credit | 1,000 | 21 | 0.016305s | 91.84 | Low |
| UCI Bank Marketing | 45,211 | 17 | 0.087316s | 69.0 | Elevated |
| UCI Adult | 48,842 | 15 | 0.087798s | 69.0 | Elevated |

Every public report contains all six V1 sections and generated in under `30s`.
Prepared CSV and raw archive checksums are recorded in the manifests and
`sources.json`.

## Controlled Mutations

Seven deterministic Adult mutations cover:

- `100%` feature missingness
- duplicates
- target imbalance
- strong leakage
- review-only leakage
- missing targets
- a constant field

All expected directional assertions pass. Strong leakage triggers the explained
strong-leakage guardrail; review-only leakage leaves the leakage score unchanged.

## Leakage Review

Every leakage-name flag is recorded with DataTrust's reason and a reviewed
classification in `leakage_review.csv`. All generated classifications match the
reviewed classifications after one evidence-backed runtime correction.

The first public-corpus pass classified Bank Marketing's
`previous_campaign_outcome` as strong leakage and capped the report at `49 High
Risk`. UCI documents it as an input from a previous campaign, available before
the current subscription target. DataTrust was narrowly corrected so explicitly
prior or historical outcome-like names are review-only while post/final
outcome-like names remain strong.

## Adjacent-Tool Comparison

One internal Adult comparison was run against Evidently OSS `0.7.21` using its
DataSummaryPreset in `validation/.venv-evidently`. Both validation environments
use Python `3.11.15`.

- DataTrust report runtime: `0.087798s`
- Evidently DataSummaryPreset runtime: `0.433635s`

These values are descriptive, not a performance benchmark. The comparison
documents overlap, divergence, and DataTrust-specific synthesis without claiming
superiority. It is internal supporting evidence only and is not a V1 pass gate.

## Verification

```text
Validation corpus verification passed.
23 passed
```

Still unproven:

- practitioner-owned CSV runs
- technical and non-technical dry runs
- practitioner finding-quality, score-defensibility, and shareability gates
