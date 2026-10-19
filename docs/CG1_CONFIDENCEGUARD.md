# ConfidenceGuard — CG1 Prediction Evaluation Workbench

Implemented 2026-10-17. Engineering verification is recorded separately in
[validation/cg1/README.md](../validation/cg1/README.md). The subsequent user
instruction accepts CG1 completion, independent review/corrections and its closed
understanding gate. This acceptance is not inferred from internal verification.
M8 audio remains deferred. [CG2](CG2_CONFIDENCEGUARD.md) now extends this evaluator.

ConfidenceGuard is NUMEK's distinct model reliability product. CG1 evaluates supplied
binary classification, multiclass classification and regression artifacts. It does
not fit or execute a model, invent a reliability score, certify a deployment, or
extend DataTrust's dataset specifications and scores.

## Run and integrate

The distribution remains `datatrust`. Refresh an editable install to register the
additional `confidenceguard` console command; no additional runtime dependency is
required. Scalar Parquet uses the existing optional `parquet` extra. From a checkout:

```bash
PYTHONPATH=src .venv/bin/python -m confidenceguard.cli ui --data-root ./predictions
PYTHONPATH=src .venv/bin/python -m confidenceguard.cli inspect --spec evaluation.json
PYTHONPATH=src .venv/bin/python -m confidenceguard.cli evaluate --spec evaluation.json --out report.html --json-out report.json
```

The functional browser is `http://127.0.0.1:8000/confidenceguard`. It uses the same
JSON operations available to the independent design lab. The complete editable
specification exposes advanced clocks, assertions, costs, limits and inference
settings alongside the ordinary field controls. The client expands backend
measurement records and coverage; it calculates no metrics. Visual transformation
remains the design lab's independent work.

```python
from confidenceguard import EvaluationSpec, EvaluationConfig, evaluate

spec = EvaluationSpec.from_dict({
    "task": {"kind": "binary_classification", "outcome_definition": "Observed event",
             "classes": ["no", "yes"], "positive_class": "yes"},
    "sources": [{"id": "predictions", "path": "/absolute/path/predictions.csv"}],
    "runs": [{"id": "candidate", "source": "predictions", "key_columns": ["event_id"],
              "model": {"id": "risk-model", "version": "v2"},
              "prediction": "decision", "probabilities": {"positive_column": "p_yes"}}],
    "outcomes": {"source": "predictions", "column": "outcome", "key_columns": ["event_id"]}
})
result = evaluate(spec, EvaluationConfig())
portable = result.to_dict()             # conservative shareable projection
exact = result.to_private_dict()        # protected local evidence
artifacts = result.generate_artifacts("report.pdf", format="pdf", json_path="report.json")
```

Specifications loaded by CLI resolve source paths relative to their specification
file. Python `inspect`, `evaluate`, `EvaluationResult.from_dict`,
`generate_artifacts`, and `resolve_evidence` use the same application/engine
boundary. Python evaluation performs validation without a mandatory separate
inspection step. Exact resolution requires current authorized roots explicitly.

## Local JSON contract

API root: `/api/confidenceguard/v1`. Bundled definitions and synthetic examples live
in `src/confidenceguard/schemas/`; the running host exposes `/openapi.json`,
`/schemas`, `/examples`, and `/capabilities` under that API root.

Version identities are independent: transport `v1`, evaluation specification
`confidenceguard.evaluation_spec/1.0`, analytical result
`confidenceguard.evaluation_result/1.0`, methodology `prediction_evaluation_v1`,
and disclosure policy `conservative_aggregates_v1`. Strict requests reject unknown
fields; consumers tolerate additive response fields. Method changes do not hide
behind transport revisions.

| Operation | Behavior |
|---|---|
| `GET /session`, `/capabilities` | Session-bound CSRF token, root aliases, versions, representations, effective limits and optional Parquet availability |
| `POST /sources` | Bounded upload or host-root-relative registration; opaque source handles |
| `POST /evaluations`, `GET/PUT /evaluations/{id}` | Typed draft; expected revision on update; no edits during active work |
| `POST /jobs`, `GET /jobs/{id}`, `POST /jobs/{id}/cancel` | Inspect/evaluate/export/resolve-evidence jobs; idempotent request IDs; monotonic progress revisions |
| `GET /results/{id}` | Local or shareable completed projection |
| `GET /results/{id}/{summary,measurements,findings,coverage}` | Completed views; list views paginate and accept bounded run/metric/scope/family/ID filters |
| `GET /results/{id}/artifacts`, `GET /artifacts/{id}/content` | Owned artifact list and identity-verified download; no implicit analysis/conversion |
| `POST /results/import` | Matching protected result/manifest or a permanently shareable-only view |
| `DELETE /evaluations/{id}` | Remove stopped owned evaluation state and artifacts |

Configuration uses `{"spec": {...}, "config": {...}}`, replacing Python source
paths with `{"id": "predictions", "handle": "..."}`. Inspection returns effective
settings and a fingerprint binding source bytes, spec/configuration, method,
outcome content and canonical context. Evaluation requires the same draft revision
and fingerprint. Changed bytes or changed eligible snapshots reject confirmation.
Completed results never change when a draft is revised.

Jobs transition pending → running → succeeded/failed/cancelled, with a transient
cancelling state. The shared worker slot is reserved before admission; busy work
returns `409 worker_busy`, without a durable queue. If commit wins a cancellation
race, success remains success. Unknown totals do not produce invented percentages
or ETAs. Analytical/native failures publish no completed evaluation.

Responses use an `api_version`/`data` envelope, except raw schema/OpenAPI documents
and artifact content. Errors include stable codes, request IDs and field pointers
without source values, SQL or paths. Wrong-session IDs are ownership-safe 404s;
stale/busy state is 409, invalid declarations 422, oversized input 413.

The host is loopback-only. ConfidenceGuard validates Host/Origin and uses its own
session-bound `X-CSRF-Token` for mutations, including uploads. Private responses
are no-store. SameSite/HttpOnly cookies, same-origin static assets and no default
CORS protect the local workflow. A design lab can use a controlled development
proxy. This is not a hosted or multi-user service. Existing DataTrust forms retain
their original CSRF protocol.

## Inputs and populations

Independent contracts describe model/version/preprocessing/calibration identities,
prediction runs, probabilities, native scores, issuance, intervals, authoritative
outcomes, canonical context, fixed cohorts, policies, sampling and disclosure.
CSV framing preserves lexical states; optional Parquet admits flat scalars and
projects required columns in bounded batches. DuckDB holds private disk relations.
Prediction-event identity is distinct from entity identity. Cross-source joins and
paired comparisons require explicit event keys; row-order pairing is forbidden.

Probability-only, score-only, hard-only, point-only, partially labeled and unlabeled
inputs retain supported evidence. A supplied output is distinct from an issued
decision. Abstentions may retain latent probabilities, labels or intervals.
Failed/missing outputs remain in the event ledger; absent outcomes never become
negative labels. Outcome status, availability, maturity and as-of cutoffs determine
eligibility. Unknown/selective label observation cannot establish full-population
performance. Repeated entity declarations suppress row-independent intervals.

| Representation | Established CG1 evidence and explicit decisions |
|---|---|
| Binary probability | Log loss/Brier, ranking and event calibration; explicit inclusive probability threshold derivation/replay |
| Complete multiclass probabilities | Full-vector losses, classwise/top-label calibration; explicit argmax with abstaining or declared class-order ties |
| Native binary score | Tie-aware AUC/AP; explicit native-unit threshold and direction; no probability inference |
| Comparable class scores | Availability/distribution and explicit higher-is-preferred argmax; no probability conversion |
| Hard classification output | Confusion/errors, cohorts, paired decisions and declared action costs |
| Regression point | Point losses, residuals, material-error rules and paired errors |
| Supplied prediction intervals | Coverage, width/misses and applicable central interval score; optional width-based abstention |

No decision is silently derived. A mapped supplied output takes priority and is
never overwritten by a derivation. Supplied-versus-rule mismatches are measured.
Derived decision metrics and policy replays are explicitly simulated. Top-label
calibration is a named diagnostic, not proof of an operational argmax decision.
Binary equality is inclusive; exact maximum ties default to abstention. Ranking
metrics and selection curves retain whole equal-score groups. Probability replay
uses 0.00–1.00 plus all/none endpoints; arbitrary scores use actual native cutoffs
selected without labels. An event-ranking score does not become a correctness
selector without an explicit selection declaration.

Probabilities require explicit positive-event or complete mutually exclusive class
semantics, finite bounded values and sum tolerance 1e-6 by default. No sigmoid,
softmax, clipping or renormalization is applied. Unsafe conversion/underflow is
ineligible. Valid hard decisions survive invalid probability artifacts. True zero
probability for an observed event produces positive-infinite log loss with explicit
JSON value-state, including qualified infinite or indeterminate paired differences.

## Comparison and methodology

Both runs use exactly one frozen authoritative outcome snapshot. Additionally
mapped inline outcomes must assert agreement or be acknowledged non-authoritative
copies. Conflicting assertions block paired performance; conflict rows are not
deleted to manufacture agreement. Explicit stale copies may disagree with visible
counts and provenance. Snapshot names alone do not establish compatible content.

Alignment records shared, left-only/right-only, duplicate and missing identities,
outcome states and each model's output/issuance availability. Native metrics remain
separate from common-eligibility paired values/deltas. Binary ranking pairs on
score availability; probability losses pair on valid probabilities. Supplied
intervals pair only when IDs, nominal coverage, meaning and centrality match.
Unmatched intervals are native evidence, not automatically equivalent intervals.
Matched error transitions retain bounded witnesses for both predictions and the
authoritative outcome. Context is defined once for both runs; conflicting cohort
assertions block the affected cohort, preserving unrelated global evidence.

Known different horizons/information cutoffs block primary same-opportunity
comparison. Unknown timing permits narrowly labeled matched-prediction comparison,
not a fair replacement/generalization claim. Different generation timestamps alone
do not invalidate replay. Training/calibration/selection roles remain visible.

Implemented established metrics include confusion counts, precision/recall/
specificity/F1/balanced accuracy, observed-support macro and support-weighted
summaries; tie-aware ROC-AUC and non-interpolated AP with prevalence; natural-log
loss and binary/unhalved multiclass Brier; ten fixed-bin calibration and
high-confidence failures; MAE/RMSE/bias/median/P90/P95 absolute error, qualified R²,
material errors and supplied interval evaluation. Threshold/abstention curves and
optional empirical costs describe fixed retrospective policies, not causal business
outcomes or optimized policies.

Descriptive evaluation is the default. Explicit independent-row sampling permits
pointwise 95% Wilson intervals for eligible proportions; known repeated entities
block that inference. Support warnings (100 outcomes, 20/bin) are configurable
warnings, not mathematical eligibility gates. ECE is bin-dependent and is not a
universal reliability criterion. Prediction intervals are not confidence intervals
for a mean/parameter. No general significance/bootstrap engine, calibrator fitting,
conformal construction or policy optimization is included in CG1.

Population provenance revision **1.1** binds each population identity to frozen
normalized-source lineage, source interpretation, task/run declarations,
probability tolerance, outcome/context snapshots, eligibility predicate and
`denominator_kind`. Paired projections additionally bind both inputs, selected
side, metric intersection and interval projection; transient SQL table names are
not identities. Exact SQL counts (including reuse of grouped confusion counts)
are checked before publication; a conflicting denominator aborts the evaluation.
Completed-result reopening checks measurement and nested class/comparison ledger
references for this revision.

Precision uses issued predictions of the class; recall uses observed outcomes of
the class; specificity uses observed outcomes outside the positive class. The
share of top-class errors that are high confidence uses **all eligible top-class
errors**, distinct from the high-confidence error rate denominator. Per-class
records carry precision/recall population references and an explicit F1 formula
denominator. Macro/F1 measurement denominators describe evaluation record support;
they are marked `evaluation_support`, not misrepresented as formula denominators.

Paired deltas carry `paired_base_support`, plus left/right population references
and their individual denominators. Conditional precision/recall/high-confidence
subsets can differ within that common base. Forcing the intersection of both
positive decisions would redefine precision and can make its comparison
trivially equal. These deltas are descriptive comparisons of conditionals over a
common base, not differences on identical conditional subsets or paired-inference
claims. Point/probability/ranking intersections remain independently identified.

Each measurement records basis (measured/simulated etc.), interpretation, method
standing/version, population identity/denominator, support, applicability,
value-state, qualifications and private evidence references. Not computed,
inapplicable, unexpected failure, retention bounds, presentation omission and
privacy withholding remain distinct. Unavailable/withheld evidence is never zero.

## Cohorts, private evidence and artifacts

Defaults admit four cohort declarations/32 semantic groups, configurable with
resource-backed limits. Missing/other/out-of-range states count in planning.
Oversized requests fail declaration admission instead of silently selecting top
groups. Every admitted group uses its full eligible population. Exact inventory
records residual populations and distinct-category coverage; overlapping cohort
counts are not summed into an affected-row total. Exact local coverage includes
the original frozen cohort definitions, including prediction-derived status.

Portable output defaults to conservative aggregates: denominators below 10 or
sensitive nonzero components 1–9 withhold associated breakdowns and dependent
rates, differences and sensitive details jointly across models. Safe qualitative
findings and method checks remain visible without exact counts or private values. Protected cohort
partitions and protected confusion/calibration/policy tables are withheld as a
unit; exact workbench evidence remains available locally. HTML, PDF and JSON use
one projection, with public class/run/policy aliases and no hidden exact payload.
The conservative projection withholds exact ROC/PR curves and native ranking,
selection and class-score extrema/quantiles, even when overall support is large:
unique thresholds can reveal individual prediction artifacts and small cumulative
counts. Scalar AUC/AP still use every eligible tied score group; exact local
curves and explicit `exact_aggregates_v1` exports retain their detail. No rounded
curve is presented as equivalent analytical evidence.

Projection revision `cg1_review_corrections_v1` retains known safe findings,
comparison blockers, aliased check statuses, sampling qualifications and
limitations. It strips exact finding counts, private inventories and arbitrary
free text. An infinite-loss finding is retained only when its supporting loss is
disclosed. All HTML/SVG/PDF/JSON share that projection; canonical reports display
method checks and limitations. A disclosed population ledger contains only
references needed by retained measurements, without private SQL or input lineage.

Existing schema/API major versions remain unchanged through additive fields.
Corrected population IDs and paired-delta denominator meanings intentionally
change; consumers must use opaque IDs and `denominator_kind`. Historical artifacts
are immutable. Reopening old conservative JSON verifies its original digest, then
withholds ranking details on re-export, binds a new projection digest and retains
the original digest. Lost findings and corrected population lineage cannot be
reconstructed from old portable JSON; reevaluation is required. Old exact bundles
can still be reopened with their matching manifest and are qualified as legacy.

Explicit alternative disclosure settings are recorded. This is not differential
privacy, anonymity or protection against auxiliary data/cross-export reconstruction.

Owner-only bundles retain exact result and locator manifest, not a source corpus
copy. Canonical analytical and manifest digests bind the bundle; binding fields do
not circularly enter their own digest. Shareable projection digests bind disclosure
variants. A shareable import cannot recover suppressed content or gain exact
resolution. Exact witnesses require unchanged originals in current authorized
roots; excerpts require explicit reveal and are bounded. Reports do not rerun
analysis. Publication refuses overwrite/source alias collisions; PDF failure
preserves valid HTML/JSON and protected artifacts.

## Runtime and resources

`contracts`, `engine`, `sources`, `analytics`, `result`, `disclosure`, `private`,
`artifacts`, `schema`, `transport`, static client and `cli` live in the independent
`confidenceguard` package. Analytical modules import neither Flask nor browser
templates. Jinja is confined to canonical completed-report rendering.

`compat.py` adapts existing supervision, Workspace, resource options, secure file
helpers, lexical CSV framing, scalar Parquet admission, exact clocks, restricted
PDF/publication and protected directories. No `numek_runtime` extraction or accepted
DataTrust engine migration was made. CG explicitly performs its own admission;
an empty legacy Workspace source list is not treated as admission evidence.

Default controls: one supervised worker; 2 GiB DuckDB memory, sampled 6 GiB RSS,
two threads, 30-minute deadline, 64 GiB workspace/2 GiB free reserve; 100-million
probability cells; 64 MiB protected and 32 MiB portable result budgets. Sorted
grouped reductions use all admitted observations for scalar ranking metrics,
retaining at most 201 curve points, five witnesses/group and 100 details by default.
Sampled limits can overshoot and do not promise capacity or security isolation.

## Approved continuation

CG2 now extends this engine with fitting and uncertainty methods; its explicit new
contracts preserve CG1 requests and evidence. CG3 adds opt-in
local immutable history, revisions/maturity-aware windows and drift/mix analysis.
CG4 develops bounded failure discovery with independent confirmation. CG5 adds
policy selection/constraints/frontiers with separate evaluation. CG6 introduces
trusted model adapters and controlled robustness/stress/sensitivity execution.
CG7 adds durable batch ingestion, label updates, monitoring, alert/incident lifecycle
and retention before considering streaming/distribution. Those capabilities remain
approved direction, not CG1 implementation claims.

## First independent review corrections — 2026-10-18

Focused correction source, independent eligibility/privacy tests, before/after
evidence and executed verification are described in
[CG1 review corrections](../validation/cg1/REVIEW_CORRECTIONS.md). The three-task
scope is retained. Acceptance was pending at that handoff. The user's subsequent
authorization accepts CG1 and the closed understanding gate, and CG2 has since
been implemented; this historical review evidence remains preserved.
