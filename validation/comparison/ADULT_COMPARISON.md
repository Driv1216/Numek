# Adult Internal Adjacent-Tool Comparison

Generated: 2026-06-14T01:56:19.112560+00:00

This is internal supporting credibility evidence. It is not a product acceptance gate,
does not claim superiority, and must not be shown during blinded practitioner
reviews.

## Execution

- Dataset: prepared UCI Adult, 48842 rows x 15 columns
- DataTrust report runtime: 0.087798s
- Evidently OSS version: 0.7.21, isolated validation environment
- Evidently DataSummaryPreset runtime: 0.433635s

Runtime values are descriptive only because the tools produce different
artifacts and this is not a performance benchmark.

## Overlap

- Both surface dataset shape, missingness, target/column distributions, and
  feature-level data-quality evidence.
- Both create a shareable HTML artifact for offline inspection.
- Both make raw quality evidence inspectable rather than hiding it behind one
  opaque metric.

## Divergence

- Evidently's DataSummaryPreset provides a broad interactive statistical
  profile, including detailed column summaries and correlations.
- DataTrust produces a smaller six-section reliability report with a target
  balance score, heuristic leakage review, deterministic top risks, recommended
  actions, and explained score guardrails.
- DataTrust classifies `marital_status` as a review-only leakage-name prompt;
  this requires human confirmation and is not an Evidently DataSummaryPreset
  concept.
- Neither artifact proves fitness for use, fairness, compliance, or label
  correctness.

## DataTrust-Specific Synthesis

- Adult DataTrust risk band: Elevated (69.0)
- Adult DataTrust top risks: Target imbalance, Numeric outlier concentration, Leakage review prompts
- Applied guardrails: critical_sub_score

The useful distinction to test with practitioners is whether DataTrust's
synthesis and action framing improve review workflow, not whether it computes
more raw profiling metrics than Evidently.
