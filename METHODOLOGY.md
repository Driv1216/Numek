# DataTrust Methodology

Last updated: 2026-10-09

DataTrust produces local CSV evidence through classification, annotation-aware partial
workflows, multilabel indicators, multi-output regression, and target-free profiling/readiness. All interfaces export HTML, its derived PDF, and strict JSON. The
report is intended as an early evidence pack, not a formal certification.

## Classification Target Guidance

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
feature diagnostics, change scores, or add guardrails. Classification CLI and
Python calls require an explicit target; general dataset profiling accepts none.

Generated narrative, finding, and guardrail text uses deterministic
singular/plural wording. This presentation logic does not change any metric,
threshold, finding decision, score, or guardrail.

## Classification Scores (Unchanged)

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
HTML/PDF/JSON exports are available in all interfaces; Word output is not implemented.
- Semantic date checks, fuzzy category matching, missingness-pattern mining,
  feature-correlation analysis, and automated cleaning are not implemented.

## Unlabeled CSV Profiling Policy

The single engine uses `classification_legacy_2026_08_13` or
`unlabeled_csv_profile_v1`. Classification retains its legacy IQR population
(including non-finite values) and total-row outlier denominator. General
profiling uses finite-only summaries and IQR with a finite-observation
denominator. IQR requires at least four finite observations and nonzero IQR;
otherwise the check is blocked with a reason, not reported as zero outliers.
Boolean columns are categorical evidence in general profiling.

All columns participate, regardless of names. Evidence includes dimensions,
inferred types, all-cell missingness, affected rows and one/two/three-plus
missing-column buckets; exact repeated rows beyond the first occurrence, groups,
participating rows, largest group, and bounded row references; observed distinct
values, top shares, fully missing/constant/near-constant fields, contextual
cardinality; finite numeric quartiles, zero/negative/non-finite counts, and IQR.
Distinct counts exclude nulls; distinct rates and top-value shares use all rows.
Exact identity uses all parsed columns, including nulls. Missingness and
duplicates concern the **parsed interpretation**, not a claim of original-token
identity. Parsing warnings identify some ways interpretations may differ.

| Unlabeled observation | Interpretation threshold / review priority |
|---|---|
| Fully missing columns | Any: High; redundant constant findings suppressed |
| Column missingness | >=25%: Moderate; >=50%: High |
| All-cell missingness | >=10%: Moderate; >=25%: High |
| Affected rows | >=25%: Moderate; >=50%: High, when not already communicated |
| Exact repeated rows | Any: Low; >=2%: Moderate; >=10%: High |
| Observed constants | One non-null distinct value: Moderate |
| Near constants | >=95% top share, excluding missing-dominated columns: Low |
| Nonnumeric cardinality | >=20 distinct and >=80% distinct rate: Low |
| Non-finite values | Any: High |
| Finite IQR concentration | >=5% finite observations: Moderate |

Findings sort by review priority, fixed check order, then source column order
inside each grouped finding. Severity means review priority. Repetition, rare
values, skew, and cardinality are not automatically defects; nothing is cleaned.
Thresholds are internally tested interpretation rules, not externally validated
reliability cutoffs. Scoring is explicitly `not_defined`, `values=null`, with
reason `No validated scoring policy is defined for unlabeled profiling.` There
are no sub-scores, total, guardrails, risk band, or readiness verdict.

## Parsing Fidelity, Execution, and Coverage

Defaults preserve pandas comma/header inference and NA recognition. Unlabeled
overrides support encoding, exact missing-token policy (`pandas_default`,
`empty_only`, `custom`), and resolved-name string/numeric types. Numeric overrides
reject invalid tokens without silent null coercion. Classification overrides are
outside M1. Source bytes remain untouched throughout a job.

Independent bounded token inspection respects CSV quoting, embedded newlines,
encoding, and blank records. Defaults: 1 MiB, 200 records, 20,000 comparable
cells. Only confidently aligned complete records are compared. Leading-zero
numeric conversion, nonempty tokens becoming null, duplicate/empty source
headers, and incomplete/ambiguous inspection are interpretation review warnings,
separate from findings, severity, and scores. Warnings record observed counts,
scope, setting, and bounded source-hash/parsing-fingerprint/parsed-row references;
they never extrapolate a sampled count or include raw identifier examples.
No warnings observed means only none within the inspected scope. Inspection
failure does not alter classification parsing or create a new fidelity rejection.
Full-source hashing is separate I/O; a changed source aborts analysis.

Check applicability (`applicable`, `not_applicable`, `blocked`, `unsupported`)
and execution (`not_run`, `completed`, `failed`, `skipped`) are separate. Required
loading/nonempty/basic-profile failures abort without a completed report;
allocation failures abort. Isolated optional-check failure can return a report
prominently marked **Analysis incomplete**. Coverage lists completed groups and
unavailable/excluded columns; it is not a universal reliability percentage.
Classification checks are not applicable without a target, and future analyses
remain unsupported. Strict JSON uses null for unavailable values and textual
infinity representations where necessary, never invalid JSON numeric literals.

M1 uses synchronous `pandas_in_memory`. Unlabeled operational defaults are
100 MiB source, 1 million rows, 1,000 columns, 512 MiB loaded frame, no elapsed
limit. Source/header checks precede parsing, row overflow uses limit plus one,
frame accounting occurs after materialization and excludes transient/process
memory, and elapsed checks are cooperative between stages. These safeguards are
configurable, not hard memory/CPU/timeout guarantees. Legacy classification API
and CLI have no new default analysis limits. Result/evidence contain no DataFrame
and retain their meaning for later workers or disk-backed execution.

## Single-Target Regression Policy — `tabular_regression_v1`

Regression uses the shared ingestion, structural/feature evidence, artifact
lifecycle, and result contracts. Its result schema is `1.1`; existing workflows
retain their schema and analytical outputs. `TaskSpec("regression", target)`
requires an explicit numeric non-boolean outcome. String targets require an
explicit valid numeric parsing override. No finite targets is a required-stage
failure; one finite observation, constants, and target-only datasets can complete
with supported descriptive evidence and explicit blocked/not-applicable checks.
No minimum training sample size is claimed.

`RegressionOptions` carries optional `TargetExpectations`, feature availability,
and `RegressionRelationLimits`. Intent is unspecified/continuous/count. Counts
imply nonnegative integers. Inclusive finite ranges and optional nonnegative or
integer requirements must intersect consistently; unknown fields, impossible
ranges, contradictory count declarations, and invalid names/types are rejected.
Units (up to 80 characters) are display context only. All declarations are
identified as user-supplied. Boolean and nonnumeric/categorical storage are excluded from relationships.
Numeric storage alone does not establish semantics; explicit string parsing can
preserve and exclude numeric-looking category codes.

Populations remain separate: all parsed rows, nonmissing targets, finite targets,
constraint-compliant finite targets, and relationship-specific overlaps.
Distributions include every finite target, including constraint violations.
Counts and exact integer equality/distinctness remain exact; analytical regression
evidence is not rounded to six decimals. Scaled arithmetic protects overflow.
Large integers beyond float64 exact precision or variation near floating resolution
block affected calculations; failed arithmetic never becomes zero variation.
Unavailable measurements retain reasons and completed exact facts remain visible.

Finite evidence includes extrema, mean, sample deviation (n >= 2), linear-interpolated
P1/P5/Q1/median/Q3/P95/P99, IQR, central 90% span, modal share, and counts of zero,
negative, integer/noninteger values. Histograms use exact count bars for <=20
values; otherwise Freedman–Diaconis bins capped at 40, Sturges when IQR is zero.
Stored plot aggregates are consumed by HTML/PDF without re-analysis.

Interpretation defaults:

- One distinct value: High constant-target review. Fewer than four finite values:
  Moderate limited-observation review; methods enforce their own support.
- Modal share >=95% with n >=20 or zero IQR with variation: Low concentration
  review. Endpoint share >=10% with n >=20: contextual concentration, distinguishing
  observed extrema from declared bounds. Count zeros are zero concentration;
  neither boundary mass nor skew proves saturation/clipping.
- 1.5-IQR lower/upper candidates need n >=4 and positive IQR. A Low target action
  needs >=5% candidate share. Bowley quartile skewness is descriptive.
- Any missing target: Moderate, or High at >=25% missing. Any infinity: High.
  Any declared constraint violation: High, naming the declaration, per-rule and
  union counts, finite denominator, and bounded source/parsing-anchored row references.
  Undeclared negative continuous values are descriptive only.
- Grid alignment for steps 1/0.1/0.01/0.001 requires n >=20 and >=5 distinct values,
  grid-relative tolerance 1e-8, and reliable representation. The coarsest grid
  reaching 95% is descriptive. No standalone rounding action is generated.

These are internal interpretation rules, not externally validated reliability
cutoffs. Quartile skewness and outlier candidates follow descriptive EDA practice;
[NIST skewness](https://www.itl.nist.gov/div898/handbook/eda/section3/eda35b.htm) and
[NIST potential outliers](https://www.itl.nist.gov/div898/handbook/eda/section3/eda35h.htm)
distinguish shape/candidates from established errors. Instrument-resolution
expectations, mixed precision regimes, generalized dependency discovery, fuzzy
repetition, semantic date checks, and higher-order/nonlinear proxies remain later
work requiring stronger semantic contracts and validation.

### Regression relationships and bounded execution

Only numeric features enter exact copy, affine identity, and two-feature sum checks.
Copies compare original parsed scalars on finite overlap (>=2 rows and >=2 distinct
targets). Affine checks need >=20 pairs and >=5 distinct values in both columns;
deterministic min/max feature anchors derive an arithmetic mapping and the entire
overlap is verified. This is an observed identity check, not a trained model.
Two-feature sums need >=20 three-column finite rows and >=5 distinct targets.

Identity tolerance is 1e-10 of target variation plus a documented float-roundoff
allowance: 32 machine epsilons scaled by normalized affine coefficients, or 32
epsilons for sums. If roundoff exceeds 1e-6 of normalized target spread, the check
is blocked. Tolerance never scales against absolute target magnitude. Pair
screening uses evenly spaced finite-target rows and a conservative full-variation
bound; sparse samples fall back to full-overlap screening. Screening matches
support no conclusion until full verification succeeds.

Actions require >=30 finite overlapping rows, >=5 distinct targets, >=80% coverage
of finite targets, reliable arithmetic, and complete verification. Smaller/sparser
matches remain qualified technical records with explicit non-escalation reasons;
they never enter relationship action cards or executive summaries. Unknown
availability yields Moderate provenance/availability review; declared available
normally yields no relationship action; declared unavailable yields High declared
availability concern. A separate unavailable-column concern does not depend on
weak relationship support. Names alone are Low whole-token prompts, respecting
historical/prior qualifiers. No observed identity establishes leakage or model use.

Canonical groups preserve expressions, columns, populations, tolerances, availability,
and every witness. Exact copy takes precedence over equivalent affine wording;
constant-component sums can fold into the same single-feature mapping when their
support is equal/subsumed. Different mappings/components remain distinct. Action
cards consolidate eligible groups by availability context rather than detection method.

Defaults: 20 million single-feature formula-row comparisons, 20 million pair-sum
comparisons, pair pool <=32 numeric features, and screening <=512 evenly spaced
finite-target rows. Copies run before affine checks. Target-related name cues then
source order select the pair pool; all unordered selected pairs are considered.
Each screened/verified formula row consumes work; unfinished verification supports
no relationship conclusion. The ledger records columns, pool exclusions, candidates,
screens/full overlaps, budgets, stop reasons, and unavailable evidence. Completed
witnesses survive candidate interruption; unsearched candidates remain unknown.

Planned pool/work limits mean `completed` execution with `bounded` relationship
coverage and CLI 0. Insufficient support/unsafe arithmetic are blocked, absent
declarations are not applicable, and both can occur in completed runs. Unexpected
optional failures or global cooperative deadline interruptions mean `partial` and
CLI 2 after available exports. Required/source/resource or memory failures abort
without a completed result; export failures are nonzero and preserve surviving
artifacts. Applicability/execution enums and classification/unlabeled reducers remain
unchanged. Reports distinguish intentional bounds from an Analysis incomplete banner.

Exact duplication includes all parsed columns and nulls. Separately, finite targets
are grouped by all feature values with null identity preserved. Counts, distinct
values, extrema/spans, and bounded examples describe target variation within
repeated inputs; repeated measurements/stochastic outcomes/omitted context can
explain it. At most a Low contextual action occurs; contradictory labels are not
claimed. With no features this check is not applicable.

Regression scoring is exactly `status="not_defined", values=null`, with reason
“No validated scoring policy is defined for regression reliability.” No classification
scoring, guardrails, readiness verdict, training, prediction metrics, or monitoring
is applied. Priority, evidence type (fact/declaration/context), consequences,
actions, references, limitations, and coverage replace composite synthesis.

The browser never preselects the target. Numeric category ambiguity (2–20 distinct
values across >=40 finite observations), category/class/code names, identifier
names, constants, or fewer than four finite values require acknowledgement,
enforced server-side after full safeguarded confirmation. Explicit API/CLI task
selection suffices. Parsing/configuration changes invalidate confirmations and owned
artifacts; generation verifies source hash and parsing fingerprint.

## Internal and External Validation

The classification corpus, frozen result/report regression fixtures, deterministic
unlabeled fixtures, label-free views of pinned public tables, artifact/security
tests, and browser/PDF checks establish internal correctness and compatibility
evidence. Label-free views are derivations, not unlabeled ground truth. These
checks do not establish external method validity, score defensibility, reader
comprehension, customer usefulness, or suitability for a particular deployment.
Historical validation artifacts remain intact and separate. New internal checks
are under `validation/unlabeled/`; run `python -m validation.unlabeled.verify`.
Prediction and model-performance analysis belong to ConfidenceGuard.

## Adjacent Tools

Evidently, Cleanlab, Great Expectations, and ydata-profiling are important
adjacent tools. DataTrust differentiates by packaging reliability findings
into stakeholder-readable risk evidence rather than by claiming novelty in every
individual metric.

## M3 Annotation Semantics And Coverage

M3 remains CSV/tabular and pre-model. New annotation-aware policies separate
three axes: **expectation** (expected/optional/unknown), **observation**
(well-formed/absent/invalid), and **declared status** (unspecified/observed/
intentional absence/unresolved/uncertain validity). Expectation establishes a
requirement, not annotation correctness. Uncertain validity is a declaration;
DataTrust does not verify semantic ground truth.

| Effective expectation | Observation | Status | Treatment |
|---|---|---|---|
| expected | valid | unspecified/observed | Observed and supplied expected; included in descriptive evidence. |
| optional | valid | unspecified/observed | Observed and included; outside expected denominator. |
| unknown | valid | unspecified/unknown | Observed and retained; disclose unresolved expectation. |
| expected | absent | unspecified | Expected annotation unavailable because missing. |
| optional | absent | unspecified | Allowed absence; intention unresolved; no missing-label deficiency. |
| unknown | absent | unspecified/unknown | Unresolved availability/expectation; no missing-label deficiency. |
| optional | absent | intentionally_unlabeled | Explicit intentional absence; no expected-coverage penalty. |
| permitted expectation | valid | intentionally_unlabeled | Retain value; declaration/observation inconsistency. |
| any | absent | observed | Declared observed but absent; no invented annotation. |
| any | valid | uncertain | Retain observation; separately count uncertain validity. |
| any | absent | uncertain | Record uncertain declaration and absence; no measurement. |
| any | invalid | any | Invalid encoding/non-finite value excluded from applicable target measurements. |
| unresolved metadata | valid | missing/unmapped token | Retain observation; separate metadata resolution issue. |

Exact status mappings can override the inherited expectation independently of
status. Canonical `intentionally_unlabeled` sets optional expectation; `unknown`
sets unknown expectation. Custom mappings cannot require an annotation and
simultaneously explicitly declare intentional absence. Missing/unmapped metadata
cannot negate an explicitly expected requirement: populated valid values still
supply it, while absent values enter unavailable expected coverage with reason
`unresolved_status`. Known expected expectation and unresolved status are distinct;
this case is not counted as unknown expectation. Without a known expected
requirement, unresolved metadata leaves expectation unknown.

Counts retain independent, sometimes overlapping flags; they must not be summed
as a single partition. Per-target denominators are:

- Observed coverage: well-formed supplied values / all parsed rows.
- Expected coverage: supplied expected / effective resolved expected requirements;
  unavailable requirements partition into missing, invalid, and unresolved-status
  reasons. Show this denominator beside unknown-expectation population / all rows.
- Uncertain-validity share: uncertain observed / all observed annotations.
- Raw populated, absent, invalid, intentional absence, metadata resolution, and
  declaration inconsistency remain separate counts.

Zero denominators produce null and explicit applicability reasons. Rows report
any/complete/partial/empty observed vectors, observed component histograms,
expected-vector completion restricted to rows with at least one expected component,
expected gaps, unknown components, uncertain observed components, and affected-row
unions. Optional composite groups exclude incomplete keys, distinguish complete
vectors on one row from all targets seen somewhere in the group, and report mixed
states/expected gaps. Pooled coverage weights cells; equally weighted group coverage
averages group fractions. Groups without expected cells are excluded from expected
denominators. Grouping establishes no identity, independence, chronology, or leakage.

Feature diagnostics cover all selected rows; target diagnostics cover valid supplied
annotations. Finite numerical constraint violations remain observed numerical values,
as in M2. Unknown/optional absence has no deficiency severity. Explicit expected gaps
are Moderate, or High when unavailable / expected is at least 25%; invalid encodings
and declaration/observation contradictions are High; unresolved metadata is Moderate.
These are internal review priorities, not validated risk/performance estimates.

Bounded within-file annotation cohorts compare any-observed versus none and per-target
observed versus expected-missing, intentional-absence, and unresolved populations.
Missing/non-finite counts remain available. Quantitative median/IQR contrasts require
20 finite values per cohort and safe arithmetic. Encoded categories are categorical;
with at most 100 observed categories, total variation is
`0.5 * sum(abs(p(category) - q(category)))` over the union vocabulary, with separate
observed categorical denominators. Empty/high-cardinality/small populations disclose
exclusions. Magnitude has no automatic severity, p-value, missingness-mechanism,
representativeness, or deployment-shift interpretation.

## M3 Multilabel Indicators

Targets accept numeric 0/1, boolean values, and exact indicator strings `"0"`/`"1"`.
Parsing occurs first: source tokens converted by pandas are disclosed through the
bounded fidelity review. Other parsed values are invalid; blanks are unknown
assignments, never negative labels. All-zero complete vectors are valid observations.
Per-label distributions use valid known assignments; annotation expectation/status
coverage remains separate.

Complete valid observed vectors support positive-count distributions, cardinality
(mean positive count), and density (cardinality / declared label count). The observed
positive fraction over known cells is a different statistic. Partial vectors without
invalid assignments support positive-count lower/upper bounds. Complete-vector
combinations retain exact frequencies; if the 10,000-pattern cap stops enumeration,
counts describe the processed source prefix, not whole-dataset top combinations.

Label-pair contingency counts `n00,n01,n10,n11` all use the same jointly observed
population. Co-occurrence is `n11 / n`; conditional shares are `n11/(n10+n11)` and
`n11/(n01+n11)`; Jaccard is `n11/(n01+n10+n11)`. Every denominator, coverage, and
unavailable reason is retained. Pairwise populations can differ between label pairs.

Declared minimum/maximum positives, mutual exclusivity, and directed requirements
are evaluated as satisfied, violated, or inconclusive. Unknown/invalid assignments
cannot prove their own value, but other observed assignments can prove a violation.
Constraint feasibility uses a bounded declaration search; contradictions or excessive
validation work reject configuration. Uncertain validity qualifies interpretation
without rewriting recorded assignments. Uncommon combinations/cardinality do not
establish annotation error. Repeated selected inputs require an observed positive and
negative for a label to establish disagreement; complementary partial vectors are
compatible. Disagreements do not prove incorrect labels.

Observed constant labels with at least 20 known assignments generate Moderate support
review; fewer than five positives or negatives with at least 30 known assignments
generate Low review. Thresholds are internal prompts, not training-size requirements.
Findings consolidate affected labels and preserve evidence references/row unions.
List-valued/long-form encodings and multiple independent categorical outputs are deferred.

## M3 Multi-output Numerical Evidence

Every output reuses unrounded precision-safe M2 finite distributions, constraints,
quantiles, histograms, concentration/extreme/grid evidence, and copy/affine/two-input
sum verification. No other target enters its input pool. Declared numerical intent is
per output; undeclared integer outputs do not automatically become counts. Units and
magnitudes are never pooled or averaged into a score. Empty outputs yield coverage
and blocked numerical applicability; empty M3 supervision is allowed.

Joint evidence includes complete/partial/empty finite vectors, component histograms,
expected-vector coverage, constraint-violation row unions, complete-vector repetition,
and per-output variation among repeated selected inputs. Output dependencies use a
separate scope. Pearson requires 20 finite pairs, five distinct values per output,
nonzero variation, and safe paired centered arithmetic; both means use the paired
population. Unsafe precision/overflow blocks it. Output copy/affine identities are
reported without input availability or leakage actions. No three-output sums or general
dependency mining occurs. Associations establish no causation, output expendability,
model performance, or quality of missing annotations.

Input-target actionable identities retain M2 gates: 30 finite overlaps, five distinct
target values, at least 80% finite-target coverage, reliable arithmetic, full verification,
and applicable availability declarations. Observed/expected coverage accompanies the
relationship support. Per-output generators schedule formula candidates round-robin
within shared M2 single-formula/sum budgets; singleton order/results remain unchanged.

## M3 Conditional Unsupervised Readiness

Feature meaning is quantitative/categorical/identifier/unknown when declared. Declared
quantitative fields require numeric, nonboolean storage; no data encoding or transformation
is performed. Declared categories/identifiers never enter geometry. Undeclared integer/
binary fields with at most 20 finite distinct values remain ambiguous. Numeric identifier
name cues combined with high uniqueness create conditional candidates; uniqueness alone
cannot establish identifiers. Other numeric fields enter assumed quantitative summaries,
with explicit representation/units assumptions. Selected inputs are never silently changed.

Clustering/anomaly tasks report types, representation/exclusions, missing/non-finite
incidence, observed dimensions per row, complete finite quantitative rows, missing/constant
and variable dimensions, exact-vector multiplicities/distinct vectors, quantitative zero/
nonzero distributions, separate boolean/binary sparsity, and low-frequency categories.
Unrounded IQR and central-90% spans remain separate by declared/assumed quantitative pools.
Scale ratios need two eligible features, 20 finite observations each, positive IQR, and
safe precision. Ratios at least 10 produce a Low conditional prompt when scale sensitivity
is true/undeclared; declared scale-insensitive methods retain evidence without the action.
Zero-IQR/unsafe fields have explicit exclusions. Ratios depend on units/representation;
they do not prove similarity distortion.

Anomaly readiness additionally reports eligible marginal IQR extreme-candidate
multiplicities and affected-row unions. Rarity/extremes/repetition may be legitimate.
Clustering interpretation concerns weighting and method-sensitive representations;
anomaly interpretation concerns preprocessing and method-dependent treatment. Categorical-only
inputs can support structural evidence. There are no clusters, anomaly scores,
contamination estimates, neighbors, PCA, silhouette, correctness/readiness verdicts, or
recommendations to remove rows solely because they are rare/extreme.

## M3 Policy, Bounds, Reporting, And Validation

Policies follow effective semantics, not specification syntax. Scalar/singleton targets,
identical source-normalized explicit features, empty/default roles, and equivalent scalar/
mapped singleton numerical declarations preserve existing policy/results/scores/schema/HTML.
Explicit expected-only annotation semantics preserve legacy single-target missing-label
behavior. Optional/unknown expectations, role changes, or applicable feature-semantic changes
activate M3. Without those changes legacy no-label/no-finite-target rejection remains.
All M3 methodologies have scoring `not_defined` with null values; legacy classification
scoring is unchanged. Schema 1.2 is used only for actual M3 semantics.

Default M3 pair pools retain the first 32 declared labels/outputs. Separate label-pair,
output-pair, and cohort controls each allow 20 million row-comparison work units.
Output pair accounting reserves three full-row passes for association/copy/affine scope;
M2 formula/sum controls are shared across outputs. Pattern retention is 10,000 distinct
patterns; examples default to five row references. Coverage/normalization uses column-wise
arrays and compact row counters; no persistent dense annotation/distance matrix is built.
Limits record selected/excluded candidates, populations, work and stop reasons. Planned
bounds are completed execution (CLI 0); unexpected optional interruption is partial (CLI 2).
Configuration/source/required/allocation failure aborts. Operational bounds remain safeguards,
not hard memory/time capacity guarantees.

Reports use the completed analytical result without reanalysis. Presentation limits are
five executive actions, six numerical output panels, twenty feature details/table rows,
and one hundred total appendix detail rows. Repetitive checks/findings aggregate by issue,
priority and scope; overlapping populations are not summed. Human omissions state exact
computed/displayed counts; JSON retains computed evidence. Analytical bounds mean scope was
not computed; presentation truncation means computed evidence is omitted from the human
view; execution failures mean applicable work failed. None is substituted for another.
PDF derives from canonical HTML; page budgets never delete rendered pages or hide exclusions.
Presentation QA records limits/counts, while PDF validation records page counts and visual review.

Internal validation preserves frozen classification/M1/M2 results/report hashes and historical
artifacts, independently checks formulas/truth tables/constraints/groups/precision/semantic
recoding/bounds, and exercises equivalent Python/CLI/browser declarations. Public sources
Energy, Scene, and Linnerud are pinned with archive/member/prepared hashes, mappings,
attribution and available license information. Masked and feature-only views are controlled
derivations, not naturally unlabeled or anomaly/cluster ground truth. Pinned Scene reports
must fit eight pages (appendix at most four); wide synthetic reports twelve pages (appendix
at most six), with executive layers at most two pages and readable text/denominators.
Separate runtime, measured frame size, result bytes, work, rendering time, and environment
are recorded. The internal 30-second analytical target excludes rendering and is not a
capacity claim. Minimum-dependency analytical checks are distinct from within-environment
frozen parity; cross-version dtype differences are not hidden to force snapshot agreement.

## M4 comparative and advanced methods

M4 schema 1.3 records base-task policy, scalable_csv_v1 parsing, DuckDB/method
versions, effective declarations, named populations and bounds. Default pandas
contracts remain unchanged. Explicit identifiers and task/comparison group keys
default to exact decoded strings and empty-only missingness. Numeric parsing must
preserve supported integer identity and decimal round-trip identity for keys;
unsafe cross-representation equality is blocked. Identifier semantics are preserved
even when numeric storage is selected.

Accepted task-family support means implemented mathematical paths, not exhaustive
relationship, pattern or subgroup search. Structural populations and configured
overlap definitions use every eligible record. Search pools/work and retained
witnesses remain bounded; selected/excluded scope, support/precision exclusions,
unsearched candidates, planned stopping reasons and human omissions are explicit.
Unexpected applicable failures retain committed evidence in incomplete results;
required-stage, allocation, integrity and worker-termination failures publish no
completed result. No sampling or full-frame fallback substitutes for verification.

Split evidence groups before joining and distinguishes shared distinct groups,
directional participating rows, multiset intersections and affected-row unions.
Record nulls compare equal; incomplete/non-finite declared keys are excluded.
All-missing vectors are separated from informative overlap. Declared separation
violations receive High priority; unknown informative train/evaluation overlap
receives Moderate review. Permitted overlap is descriptive. Overlap is not proof
of leakage, and zero overlap establishes absence only under completed definitions.

Version comparisons retain added/removed fields, roles/storage/declared meanings,
missing/non-finite counts and signed percentage-point changes. Categorical effects
use exact union-vocabulary total variation and new/disappearing category mass.
Quantitative effects use finite full-data empirical CDF distance, exact Wasserstein-1
(the integral of absolute CDF differences), rank/interpolation quantiles, median
shift and reference-range exceedance. W1 retains original units; IQR normalization
is unavailable when unsafe or zero. Numeric category codes retain M3 semantics.
No automatic unit conversion, rename inference or category merging occurs.

Internal defaults require 100 rows/observations per side for distribution review:
missing/non-finite increases of five points, TV/CDF distance 0.10, or W1/reference
IQR 0.25. New/disappearing categories require twenty observations and one percent
mass. These are versioned review defaults, not universally validated cutoffs.
Effects, populations and annotation-selection limitations lead interpretation.

Optional inference requires explicitly independent rows and separately installed
SciPy. Identical sources and known shared/repeated declared units suppress tests.
Two-sided Fisher covers missingness; Pearson chi-square requires every observed
and expected cell at least five; asymptotic two-sample KS requires explicitly
continuous quantitative fields, at least 100 finite values per source and no pooled
ties. BH adjustment spans successful marginal tests across the job. Significance
alone cannot create or raise finding priority; conditional evidence is descriptive.

Advanced missingness uses exact signatures, residual mass, affected unions and
2×2/phi evidence. Pair review requires 100 rows, twenty missing/observed values
per field and |phi| at least 0.5; pattern review requires twenty rows, five percent
share and two missing selected features. Dependencies use full matched populations,
precision-guarded Pearson, explicitly requested matched ranks for Spearman, exact
duplicates, supported categorical functional dependence and bias-corrected Cramér's V.
Default new searches select at most 64 features/128 pairs, sixteen requested
Spearman pairs and one billion job work units. Numerical review requires 100
matched rows, ten distinct values per field, 80% coverage and |correlation| 0.98.
Functional dependence requires at least two source categories, five observations
per category, 100 rows and 80% coverage; unique-value memorization is excluded.

Explicit field/value/composite-uniqueness/order requirements reject contradictory
declarations and qualify proven violations as High-priority declared violations.
Missing, invalid and non-finite states stay separate; ordering uses finite matched
values. Segments are declared categories or reference-derived bins, never automatic
mining: four declarations, 32 levels/bins and 200 job comparisons by default. Mix
effects are separated from conditional effects. Within-file missingness requires
100 subgroup/complement rows and ten-point contrast; IQR concentration requires
100 finite values, safe positive IQR, five-percent candidate share and five-point
concentration difference. No causal, fairness, missingness-mechanism, correctness
or automatic-removal verdict follows.

Resource controls distinguish per-source limits from combined job limits, preserve
legacy explicit ExecutionLimits replacement semantics and count every source role.
Preflight estimates peak simultaneous owned workspace; actual allocated/logical inode
accounting, phase checks and spill/RSS/deadline supervision continue through execution.
A 64 GiB budget does not require 64 GiB free. Estimates are not upper bounds, memory
settings are not process quotas and monitoring can overshoot. Runtime/capacity
objectives and the 1/5 GiB combined-input validation measurements are engineering
evidence for recorded workloads, not guarantees. See validation/m4 for reproducible
mathematics, scope, environment, failures and presentation evidence.


## M5 temporal reliability methodology

Schema 1.4 uses `temporal_reliability_v1`. Observation meaning, scheduling, layout, entities and clocks are independent. Exact clocks, declaration-qualified continuity/history, feature-bound availability/revisions, target maturity, supplied evaluation requirements and configurable behavioral investigations produce evidence without a score. Required stages cover all eligible declared records; optional searches disclose bounds and exclusions.

The complete temporal rules, representations, history-state semantics, sparse-reference qualifications, provisional budgets and failure/publication boundaries are in [M5 temporal reliability](docs/M5_TEMPORAL_RELIABILITY.md). These rules do not alter M1–M4 analytical policy or legacy result schemas. Natural corpus observations and workload timings do not validate universal temporal defect thresholds or capacity guarantees.

## M6–M7 representation-specific methodology

Text schema 1.5 and image schema 1.6 preserve explicit populations, bounded
investigations and exact private evidence without universal reliability scores.
See [M6 text](docs/M6_TEXT_RELIABILITY.md) and [M7 images](docs/M7_IMAGE_RELIABILITY.md)
for the established methods, qualified thresholds and disclosure boundaries.

## M9 cross-representation methodology

Schema 1.7 uses `cross_representation_reliability_v1`. Explicit typed relationships,
context and reusable native PDF/DOCX mappings reconcile supplied facts and retain
all eligible competing values. Deterministic decimals/dates/units/clocks remain
distinct from optional model candidates. Discovery bounds and extraction/context
ambiguity cannot become absence or complete assurance. Authority is a declared
comparison policy, not external truth. Reviews are separate exact-result-bound
snapshots and never ground truth or analytical corrections.

Qualification measures the complete extraction → mapping/context → retrieval →
comparison/model → finding pipeline, with source-family-separated calibration and
held-out populations, explicit abstention and resource exclusions. Current model
profiles cover authored English financial native documents and supplied COCO
caption associations; general semantic validity is not established. Local resource
measurements do not guarantee arbitrary-document capacity. See [M9 complete
contracts, rules and limits](docs/M9_CROSS_REPRESENTATION_RELIABILITY.md) and
[verification evidence](validation/m9/README.md). M1–M7 acceptance is preserved;
M8 audio remains deferred.
