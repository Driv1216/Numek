# DataTrust V1 Methodology

DataTrust V1 produces a local HTML reliability report from a CSV dataset. The
report is intended as an early evidence pack, not a formal certification.

## Scores

All sub-scores are transparent values from 0 to 100. Higher is better.

- **Completeness**: `100 - average_missing_percentage`; severe column-level
  missingness is also surfaced so a fully missing feature cannot disappear
  inside a healthy dataset-wide average
- **Uniqueness**: `100 - duplicate_row_percentage`
- **Target Balance**: for classification, based on how far the largest class is
  from an even class distribution
- **Feature Usability**: penalizes severely missing, constant, near-constant,
  high-cardinality categorical, and numeric outlier-heavy columns
- **Leakage Risk**: penalizes strong outcome-like column-name candidates.
  Generic status, target-related, and explicitly prior or historical
  outcome-like names are review-only prompts and do not automatically reduce
  the score.

Missing target labels are tracked separately, excluded from class counts and
class percentages, and surfaced as a target-label risk. A dataset with no rows
or no usable target labels is rejected with a clear error.

## Evidence-Only Diagnostics

The report also shows evidence that is deliberately not added to the score:

- the percentage of rows containing missing feature values, with one, two, and
  three-or-more missing-feature buckets
- exact duplicate-group counts and largest group size
- feature-identical groups containing multiple non-missing target labels
- classification subtype, majority-class baseline, and
  majority-to-minority ratio
- per-column non-null and most-common-value shares
- numeric quartiles, zero and negative rates, and non-finite counts

Feature-identical rows with different labels are review prompts, not automatic
proof of labeling errors: they may represent repeated entities, time changes,
or missing distinguishing context. Widespread row-level missingness is also a
review finding when cell-level averages would otherwise hide its reach. Neither
finding changes a score or guardrail.

`DataTrust.analyze()` retains its existing `profile`, `scores`, and top-three
`risks` values and adds the complete ordered `findings` list and sanitized
report `context`.

The overall reliability score starts with the average sub-score, then applies
guardrails for high-stakes failure modes. Applied guardrails are returned in
`scores["guardrails"]` and shown in the HTML report with their explanation and
score cap. Strong leakage, a single-class target, or no feature columns cap the
score at `49`; missing target labels, severe feature missingness, severe
dataset-wide missingness, severe duplicates, or a critical sub-score cap it at
`69`. These caps prevent a severe finding from appearing beside a contradictory
Low Risk summary.

Overall risk is derived from the guardrailed score:

- `85-100`: Low risk
- `70-84`: Moderate risk
- `50-69`: Elevated risk
- `0-49`: High risk

## Limitations

- DataTrust V1 does not prove a dataset is safe, compliant, fair, or legally
  acceptable.
- Label-noise detection is not implemented in V1. Future versions may integrate
  Cleanlab-style confident learning workflows when model predictions or
  cross-validated probabilities are available.
- Drift checks require a reference/current split and are outside V1.
- Bias and fairness checks require protected or policy-relevant attributes and
  domain-specific interpretation.
- Leakage detection is token/phrase-aware but remains heuristic in V1. Strong
  and review-only classifications should both be reviewed by a human who knows
  when each field becomes available.
- The local browser UI accepts comma-delimited CSVs with headers, keeps files
  only for the running process, and uses a configurable `100 MiB` default file
  limit. The in-memory pandas representation may be larger than the CSV.
- PDF output depends on the browser's print/save capability. DataTrust does not
  generate a separate PDF or Word document.
- Semantic date checks, fuzzy category matching, missingness-pattern mining,
  feature-correlation analysis, and automated cleaning are not implemented.

## Adjacent Tools

Evidently, Cleanlab, Great Expectations, and ydata-profiling are important
adjacent tools. DataTrust V1 differentiates by packaging reliability findings
into stakeholder-readable risk evidence rather than by claiming novelty in every
individual metric.
