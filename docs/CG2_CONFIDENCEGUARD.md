# ConfidenceGuard CG2 — Calibration & Uncertainty Methods

Implemented 2026-10-19. Methodology: `calibration_uncertainty_v1`.
CG1 completion, independent review, corrections and its closed understanding gate
are accepted according to the user's implementation authorization. CG2 engineering
verification does not close a new understanding gate on the user's behalf.

## Architecture and compatibility

CG2 extends the existing `confidenceguard` package. It uses `engine.open_store`,
`sources.Store`, the supervised DuckDB workspace, `analytics.Evidence`, CG1
reducers, population lineage, disclosure projection and canonical report template.
It does not introduce another ingestion, evaluation or reporting engine.

`methods.py` composes fit, optional selection, freezing, application and evaluation.
`method_sources.py` extends the normalized relations; `calibration.py`,
`conformal.py`, `uncertainty.py` and `inference.py` implement focused methods.
`fitted.py` and `membership.py` validate data-only artifacts and protected membership.
Browser and CLI services call the same supervised application boundary.

CG1 `evaluation_spec/1.0`, `evaluation_result/1.0`, `prediction_evaluation_v1`,
two-base-run requests and strict constructors remain supported. CG2 explicitly
uses `confidenceguard.evaluation_spec/1.1` or `confidenceguard.study_spec/1.0`,
and returns `confidenceguard.evaluation_result/1.1`. The embedded `evaluation`
is an unchanged CG1 specification. `application_spec/1.0`, `fitted_method/1.0`
and `assessment/1.0` are separate contracts. `/api/confidenceguard/v1` remains
the transport boundary; capabilities advertise supported schemas and extras.
Derived variants and explicit comparison edges do not change CG1's singular
comparison field. Old clients must opt into CG2 schemas.

DataTrust behavior, scores, commands, historical evidence and accepted contracts
are preserved. CG3 history/drift, CG4 automated subgroup discovery, CG5 policy
optimization, CG6 predictor/auxiliary-model execution and CG7 durable monitoring
remain separate roadmap stages. Existing fixed policy replay is retained.

## Probability maps

| Method | Input and mathematical variant | Qualifications |
|---|---|---|
| Identity | Complete probabilities; unchanged map | Included in eligible probability selection families |
| Platt | `sigmoid(a*z+b)`, `a >= 0`; positive-oriented scalar score, raw probability or explicit logit probability | Fit-only standardization; Platt smoothed binary targets; both labels required |
| Isotonic | Exact grouped PAVA with equal-score aggregation | Linear knot interpolation, constant endpoint extrapolation, genuine zero/one outputs; constant maps allowed |
| Beta | `sigmoid(a*log(p)-b*log(1-p)+c)`, `a,b >= 0` | Identity-centered L2, default `1e-6`, recorded; both labels required |
| Temperature | `softmax(logits/T)` or explicitly chosen probability-power scaling | Finite positive T; arbitrary scores are not logits |
| Dirichlet | `softmax(W*log(p)+b)` | Explicit positive identity-centered L2; all declared classes need fit support; can change class order |

Method/algorithm versions specify preprocessing, objective, interpolation,
regularization and numerical conventions. Logarithmic preprocessing uses recorded
epsilon (default `1e-15`) and counts affected cells. Original probabilities are
immutable: a genuine original zero on an observed label retains infinite log loss.
Log probabilities preserve finite losses and ranking when exponentiation underflows.
Numerical overflow is a failure, not evidence of certainty or an infinite threshold.
Optimizers are lazy SciPy dependencies (`statistics` extra); missing dependencies
exclude candidates before freezing their selection populations. No installation
or model execution occurs automatically.

## Exact conformal construction

For n eligible calibration scores and declared decimal coverage c, use exactly
`k = ceil((n+1)*c)`. If k <= n, take the kth order statistic; if k = n+1,
the threshold is positive infinity. No percentile interpolation or rank clamping.
With n = 0 the method is unavailable. Decimal levels are canonicalized without
rounding and ranks use exact rational integer arithmetic.

| Method | Score | Inversion |
|---|---|---|
| LAC | `1-p[y]` | Include candidate labels with score <= threshold |
| APS | Cumulative probability through the candidate's rank | Same inclusive inversion, class-order ties |
| RAPS | APS plus `lambda*max(rank-k_reg,0)` | Fixed finite nonnegative penalty and declared integer cutoff |
| Split regression | `abs(y-mu)` | `[mu-q, mu+q]` |
| Normalized regression | `abs(y-mu)/scale` | `[mu-q*scale, mu+q*scale]`; supplied positive finite scale |
| CQR | `max(lower-y, y-upper)` | `[lower-q, upper+q]`; supplied ordered quantiles with levels |

APS/RAPS are deterministic variants. They do not force nonempty sets, silently
include an extra label, or claim randomized exactness. Signed CQR corrections can
shrink an interval to an empty set. Crossed supplied quantiles are invalid input;
they are not repaired. Auxiliary scale and quantile predictors remain supplied,
frozen and explicitly identified.

Strict JSON uses `{value, value_state}`. Finite values contain finite numbers;
positive/negative infinity contain null values and explicit states. Undefined
evidence additionally explains its reason. Coefficients, temperatures, penalties,
scales and knots must be finite. A conformal threshold accepts tagged positive
infinity only with n >= 1 and k = n+1. An attainable-rank overflow is rejected.
NaN is encoded as `undefined` with reason `not_a_number`, never as an infinity;
explicitly requesting a finite/infinite NaN state is rejected. Undefined values
cannot be fitted thresholds or interval endpoints.

Empty, finite, full-class, unbounded and unavailable outputs are distinct.
Empty intervals have width zero and miss coverage; unbounded intervals have
infinite width and remain eligible for coverage/efficiency. Unavailable output
is a failure, never an empty or zero-width prediction. Legitimate infinite widths
are not dropped to obtain finite summaries or intervals.

Ordinary split-conformal coverage is finite-sample **marginal** coverage under
exchangeability of calibration/future scores with upstream choices fixed
independently of C. It is not a subgroup, batch, realized-calibration-set or future
period guarantee. Dependence, shift, selective labels and training leakage can
invalidate the claim. Cluster bootstrap does not repair conformal validity.

## Separation, selection and populations

Declare a canonical event namespace and explicit event keys. Entity keys are
separate. Roles are F (parameter fitting), S (selection), C (final conformal
calibration) and E (independent evaluation). Unused roles can be absent.
Membership comes from a role column, supplied keyed partitions, or seeded
proportions; entity designs assign whole entities. Prohibited overlaps are rejected.
Invalid/unassigned keys and unavailable labels retain explicit accounting.
Outcome authority, maturity and as-of rules are inherited from CG1. Supplied
training-membership partitions can establish observable overlap checks; unknown
upstream independence remains declared, not proven. E labels are sealed from fit
and selection relations until all methods and final thresholds are frozen.

Each selection family fixes candidates, objective, bindings and tie rules.
After structural/dependency admission, common F and S are intersections of all
admitted inputs and applicable authoritative outcomes. Fit or application failures
do not renegotiate those frozen populations. A candidate must produce a defined
objective on every common-S event; failures disqualify the candidate. Genuine
infinite log loss is a valid extended objective, ranked behind finite objectives.
All-infinite/undefined objectives produce no finite selection conclusion.

Default selection minimizes common-S mean log loss; Brier is explicit. Numerical
ties use rtol `1e-8`, atol `1e-10`, fewer parameters and declared order. The selected
F fit is frozen; no automatic F+S refit. Fitted provenance retains selection
history, population references and objectives. For conformal efficiency selection,
S is divided into declared pilot calibration/evaluation populations; a predeclared
coverage tolerance is required for automatic selection. Pilot thresholds are
discarded and final thresholds come exclusively from C after choices freeze.

Comparisons distinguish declared E, planned common inputs, actual paired outputs,
and each metric's conditional denominator. Both sides are recomputed on the
same actual base. Family-wide common populations are the default; separate
selection families do not become one automatic leaderboard. Cohort comparisons
record cohort-specific planned support. Native metrics are never subtracted
across unequal populations. Input/output failures block primary improvement
claims on the planned population; successful-output evidence is qualified.
Score-only originals have no fabricated original probability loss.

## Evaluation and inference

CG1 proper scores, native ranking, decision metrics and fixed cohorts are reused.
Transformed probability ranking uses its own log-probability ordering, distinct
from supplied native scores. Supplied decisions are retained; replacement policies
require explicit derivation and simulated provenance.

Additional evidence includes frozen-bin reliability/ECE, qualified evaluation-only
binary calibration intercept/slope, pinball loss, strict/inclusive quantile
calibration, central interval scores, standard WIS when median/symmetric pairs
exist, exact empirical-distribution CRPS from sorted samples, and qualified
sample CDF/PIT/rank histograms. Quantile grids do not imply exact full-distribution
CRPS or unknown tails; samples do not imply densities. ECE is descriptive and
bin-dependent, not the default selection criterion. Fit-derived equal-frequency
edges freeze before E is unsealed and retain ties.

Sets/intervals report coverage, empirical-minus-nominal gaps, efficiency,
median/tail width or size, empty/full/unbounded rates, outcome/output availability
and declared cohorts. Supplied intervals and conformal intervals retain distinct
identities; conformal intervals are not reinterpreted as equal-tailed quantiles.

Descriptive output is default. Explicit paired IID or independent-cluster bootstrap
resamples both variants together and recomputes conditional denominators. Cluster
inference keeps the event-weighted estimand, whole-unit membership, unit count and
cluster-size concentration. BCa supports finite smooth mean/ratio contrasts,
including proper scores, MAE, RMSE and compatible efficiency/coverage contrasts.
Tied-score AUC/AP use explicitly named paired percentile intervals.
Inference conditions on frozen artifacts and excludes training, fitting and
selection variability. Degenerate resampling does not imply zero uncertainty.

The confirmatory family never shrinks after observed failures. Bonferroni tails
are `(1-confidence)/(2*m)`. The default engineering admission requires at least
20 expected observations per tail; at 95%, m=10 requires at least 8,000 replicates.
Default B=2,000 is not silently increased or weakened. BCa adjusted tails are
checked again after bias correction and exact sufficient-statistic jackknife.
Insufficient resolution, invalid replicates, nonfinite statistics or degenerate
jackknifes suppress affected intervals without fallback. Larger-B recommendations
are explicitly data-dependent. Practical improvement needs a declared material
threshold; otherwise evidence gives direction/magnitude only.

Computational admission includes units/events, family size, paired contributions,
ranking grouping/sorting, jackknife reductions, retained replicate statistics,
memory and remaining deadline. Versioned work accounting defaults to `1e9` work
units. No generic quadratic jackknife or replicate×event×class tensor. Work is
bounded by admitted batches and shared RSS/disk/deadline controls. Descriptive
evidence survives statistical inference refusal; `inference_required` instead
fails when the requested procedure cannot be admitted or published validly.

## Artifacts, states and interfaces

Fitted methods are strict data-only JSON: no pickle, joblib, dynamic imports or
network retrieval. Loaders check versions, algorithm semantics, dimensions,
finite parameters, knots, exact conformal rank/support, tagged states, parent/model/
task/input identities, byte/depth/element limits, duplicate fields and digests.
Checksums establish integrity, not authenticity or scientific validity.

Method parameters stay `fitted_only`. Independent assessments are immutable
records binding exact method, application, outcomes, populations and result
digests; they do not change mathematical method identity. Evidence views distinguish
fitted-only, independently evaluated and applied-but-unvalidated. Independent
evaluation is evidence presence, not a pass seal. Historical assessments never
validate new inputs or establish future coverage.

Protected fitted collections include optional membership sidecars, preserved by
default and charged to private-result admission. They bind namespace, model,
method digests and hashed event/entity membership in F/S/C. These hashes are
identifiers, not anonymization. Imported matching sidecars check later E overlap;
unavailable or contradicted checks block independent assessment and inference for
affected imported methods and their dependents. Parameter-only imports remain
applicable and descriptively evaluable, with explicit unavailable-check
qualifications; independence declarations do not promote them to independently
evaluated. Fresh in-study fits use their checked current role separation. Passed
membership checks establish only supplied event/entity non-overlap, not hidden
training independence or future exchangeability. Exact reopening rejects
independent-assessment claims with unavailable or missing required checks. Setting
`separation.preserve_membership=false` is an explicit privacy/resource trade-off.

```python
from confidenceguard import study, fit_methods, apply_methods, evaluate

result = study(study_spec)  # embedded CG1 evaluation + roles + methods
fitted = result.private['fitted_methods']
sidecars = result.private['membership_sidecars']
result.generate_artifacts('review.html', audience='shareable')

application_spec = {
    'schema_version': 'confidenceguard.application_spec/1.0',
    'evaluation': new_prediction_evaluation_spec,
    'roles': {'namespace': 'declared-event-namespace', 'proportions': {'E': 1}},
    'fitted_methods': fitted,
    'membership_sidecars': sidecars,
    'output_path': 'new-predictions.jsonl',
}
application = apply_methods(application_spec)  # explicitly unvalidated
```

`fit_methods` returns fitting/selection/calibration evidence; `evaluate` consumes
frozen methods or supplied uncertainty predictions; `study` composes the full
workflow. `ConfidenceGuard` exposes the same static services. Typed contracts
include `ReliabilitySpec`, `MethodStudySpec`, `ApplicationSpec`, `MethodSpec`,
`RoleSpec`, `RepresentationSpec`, `InferenceSpec` and `FittedMethod`.

CLI: `confidenceguard inspect`, `fit`, `apply`, `study`, `evaluate`, `evidence`,
and `ui`. Method commands accept `--spec`, optional `--config`/`--methods`,
`--out`, `--format html|pdf`, `--json-out`, `--audience`; application additionally
uses `--predictions-out`. Saved method collections include protected sidecars.

The browser has guided fit/study, apply and supplied-uncertainty evaluation flows,
explicit bindings, role/assumption declarations, optional selection/inference,
inspection, revision confirmation, cancellation, method import and owned downloads.
Complete JSON remains available for pilot grids/partitions/explicit comparisons.
API jobs add `fit`, `apply`, `study`; `/methods/import`, owned method metadata/
content, `/results/{id}/methods` and `/assessments` retain CSRF/session ownership,
idempotency, the shared worker lock and host-controlled paths.

Application export is a protected immutable JSONL artifact. Parent-owned staging,
source verification, cancellation checks and no-replace commit prevent partial
completed output. A committed export wins a later cancellation. Missing-key input
events remain explicit unavailable rows. Completed reports/reopening/re-exports
consume evidence only: no fitting, selection, calibration or reanalysis.

One conservative projection serves JSON, canonical HTML/SVG and derived PDF.
Fitted parameters, thresholds, knots, membership and resampling detail stay local.
Dependent diagnostics/comparisons are withheld jointly. Reports show matched
comparisons, native populations, method/application states and scope-qualified
conclusions; bounded presentation excerpts do not truncate analytical populations.

## Operating limits and evidence

Defaults admit 16 method candidates and 16 derived variants, configurable.
Shared limits cover sources/rows/classes, sample cells, parameters, optimization,
PAVA state, exact conformity sorting, contributions, result bytes, memory/RSS,
owned spill/disk and deadlines. No silent truncation, automatic repair, refitting
inside fixed-artifact bootstrap or event sampling. NumPy/DuckDB are reused;
SciPy is optional. Seeds, RNG/version, canonical order, dependencies and settings
are recorded; numerical reproducibility is documented, not universal bitwise identity.

See [CG2 engineering evidence](../validation/cg2/README.md). Synthetic/reference
checks qualify mathematics and implementation, not universal method superiority,
production capacity, undisclosed training independence or future exchangeability.
Use fresh E after human-driven method changes; reusing inspected E for selection
invalidates its independent-evaluation declaration.

Excluded: automatic one-vs-rest renormalization, full/jackknife+/CV+/pooled
cross-conformal guarantees, weighted/adaptive/temporal/group/cluster conformal
guarantees, density execution, epistemic decomposition, auxiliary training,
automatic input repair, a universal reliability score or deployment recommendation.
