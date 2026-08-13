# DataTrust Methodology

Last updated: 2026-08-13

DataTrust produces a local HTML reliability report from a CSV dataset. The
browser UI can convert that same report to a native PDF for download. The
report is intended as an early evidence pack, not a formal certification.

## Target Guidance

The browser UI assesses every column before target selection, but never chooses
a target for the user. It groups structurally plausible small-class columns,
uses conservative whole-token outcome-name signals to explain a subset of those
choices, and separates single-class, identifier-like, continuous-looking, and
many-category columns as advanced choices. Derived-input and historical name
qualifiers suppress outcome-name elevation. Columns with no usable labels are
unavailable, while advanced choices require an explicit acknowledgement that is
also enforced by the server. Pre-selection guidance describes distinct values;
after selection, DataTrust deterministically identifies binary, multiclass, or
single-class classification from the observed target values.

Selector rows use concise outcome-oriented reasons. The exact small-class
ceiling remains part of the deterministic assessment and test contract without
being exposed as internal algorithm terminology in the selector. Advanced
confirmation retains the exact distinct count, labeled-row count, and distinct
rate required for an informed override.

This assessment is selection guidance only. It does not create findings, alter
feature diagnostics, change scores, or add guardrails. The CLI and Python API
continue to require an explicit target.

Generated narrative, finding, and guardrail text uses deterministic
singular/plural wording. This presentation logic does not change any metric,
threshold, finding decision, score, or guardrail.

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

The overall reliability score starts with the average of the already-computed
sub-scores. This uncapped average is returned as `scores["evidence_score"]`.
DataTrust then applies guardrails for high-stakes failure modes. Applied guardrails are returned in
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

## Deterministic Narrative And Report Layers

The compact result and full report consume the same deterministic narrative
object. Static templates explain the overall assessment, evidence-to-final
score path, principal evidence, missingness, target balance, duplicates, and
name-based leakage checks. The templates qualify heuristic boundaries and do
not generate new diagnostic claims. Missing feature-cell rates below `1%` are
described as minimal before the `70%` concentration rule is evaluated. This
narrative threshold does not change findings, scores, or guardrails.

The canonical HTML report is organized into eight topics: Decision Summary,
Priority Actions, Dataset Overview, Target and Label Evidence, Missingness
Evidence, Duplicate and Feature Evidence, Scoring/Methodology/Limitations, and
the Technical Appendix. Main pages use A4 portrait; the appendix uses A4
landscape. PDF remains a derivative of that canonical HTML.
When `no_major_issues` is the only compatibility finding, Priority Actions uses
an intentional empty state while the finding remains available through the API.

## Limitations

- DataTrust does not prove a dataset is safe, compliant, fair, or legally
  acceptable.
- Label-noise detection is not implemented. A future product decision may integrate
  Cleanlab-style confident learning workflows when model predictions or
  cross-validated probabilities are available.
- Drift checks require a reference/current split and are outside the current product.
- Bias and fairness checks require protected or policy-relevant attributes and
  domain-specific interpretation.
- Leakage detection is token/phrase-aware but remains heuristic. Strong
  and review-only classifications should both be reviewed by a human who knows
  when each field becomes available.
- The local browser UI accepts comma-delimited CSVs with headers, keeps files
  only for the running process, and uses a configurable `100 MiB` default file
  limit. The in-memory pandas representation may be larger than the CSV.
- The browser UI generates PDF from the canonical HTML report with WeasyPrint.
  PDF rendering depends on WeasyPrint's native font/rendering prerequisites;
  the CLI and Python API remain HTML-only, and Word output is not implemented.
- Semantic date checks, fuzzy category matching, missingness-pattern mining,
  feature-correlation analysis, and automated cleaning are not implemented.

## Adjacent Tools

Evidently, Cleanlab, Great Expectations, and ydata-profiling are important
adjacent tools. DataTrust differentiates by packaging reliability findings
into stakeholder-readable risk evidence rather than by claiming novelty in every
individual metric.
