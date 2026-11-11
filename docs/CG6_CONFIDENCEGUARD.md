# ConfidenceGuard CG6

## Completion and founder acceptance — 2026-11-08

The founder has confirmed CG6 is done and accepted. Implementation, engineering
verification, independent review, R1–R6 corrections and the final explanatory
document are complete. This decision supersedes earlier pending-review,
pending-understanding and pending-founder-acceptance language. CG1–CG6 are complete
within their approved scopes.

Read the [final implementation explainer](../validation/cg6/CG6_FINAL_IMPLEMENTATION_EXPLAINER.md)
for the full architecture, source walkthrough, algorithms/statistics, device
behavior, end-to-end examples, corrections, glossary and technical Q&As. The
accepted 230-file runtime identity is
`aa72f09caa5bc5b174db5b4253add54a9fba8b3ecec3309c99f0beb0608fbf6a`.
The [current status](../validation/cg6/IMPLEMENTATION_STATUS.md) separates corrected
verification from reused historical evidence. Actual NVIDIA CUDA qualification
remains pending compatible hardware and nonblocking; CPU/MPS and all scientific
claims retain their recorded scope and limitations. No new tests, benchmarks,
receipts or implementation changes are implied by this acceptance update.

## Independent-review corrections R1–R6

The original independent review required six bounded corrections. Their source,
focused regressions, affected integration/compatibility evidence and explicit
reuse limits are recorded in
[the correction record](../validation/cg6/review-corrections-r1-r6/REVIEW_CORRECTIONS.md).
The original engineering receipts remain historical and are not exact-source
verification of the corrected implementation. The founder's acceptance above is
a later project decision, not a retroactive change to those receipts.

Direct auxiliary application/assessment now admits its artifact through the same
execution contract as attached auxiliaries, before source preparation, inspection
and evidence reservation. This projects additional fields/clocks, rejects known
identifier/outcome inputs and enforces the declared information cutoff. Observable
identical-byte outcome aliases retain their capture-time rejection.

Frozen robustness assessment binds canonical ordered ensemble members, the fixed
complete-common-support arithmetic mean and effective decision defaults. Changed
definitions refuse before E reservation. Imported CG2 methods use the existing
authoritative membership-eligibility helper, including upstream chains: missing,
unavailable or contradicted required membership refuses affected formal claims,
without removing descriptive outputs or reallocating the frozen family alpha.

Numeric auxiliary fit statistics exclude declared missing sentinels, matching
application preprocessing. Gradient attacks bind the actual point/probability
source, indices, class order and activation, including binary complements. Numeric,
tensor and image attacks share this binding. Unsupported or nonfinite differentiable
paths refuse explicitly; no raw-head substitution or probability clipping occurs.
The increasing-point directional surrogate for regression output change is retained;
final objectives and success always use complete candidate replay. Hard-only or
logits-only outputs cannot substitute for the required differentiable analytical
probability channel.

Deterministic CUDA requires the operator to set `CUBLAS_WORKSPACE_CONFIG=:4096:8`
or `:16:8` **before process startup**. Configuration validates this prerequisite
before its seeding/device/allocation calls and records the accepted setting.
Absent/invalid settings refuse with `device_profile`; CPU fallback does not
silently disable determinism. CPU/MPS and explicitly nondeterministic CUDA do not
inherit this prerequisite. These are configuration contracts, not NVIDIA runtime
qualification; actual CUDA qualification remains pending compatible hardware.

Implementation and engineering verification are complete. The approved architecture remains controlled local
execution, three focused subsystems, and the existing supervision, analytics,
catalog, ownership and report boundaries. Engineering completion, independent
review and founder acceptance are separate. The live evidence index is
[the CG6 status record](../validation/cg6/IMPLEMENTATION_STATUS.md).

## Execution and trust

`execution` implements strict `PredictorSpec` and `ExecutionSpec` contracts,
artifact admission, complete preprocessing, normalized keyed outputs, batching,
device selection, execution ledgers, reference qualification and immutable
reopening. Supported adapters are scikit-learn/skops, ONNX, Torch/safetensors and
operator-installed custom predictors. The public methods are `inspect_predictor`,
`register_predictor`, `qualify_predictor` and `execute_predictor`.

Inputs bind event/entity/batch ownership, feature order/types, frozen category
vocabularies and preprocessing, tensor names/layout/dtype, offline tokenization,
image decoding/normalization, source roots and decision-time availability. Model
inputs cannot use known identifiers, role columns, authoritative outcomes or
retrospective fields. Identical-byte source aliases cannot conceal outcome inputs.
No fitting occurs during application.

Outputs distinguish point, labels, probabilities, logits, native scores, residual
scales, quantiles, predictive samples, issuance and auxiliary failure risk. Class
order and any activation/mapping are explicit. Original bound outputs and declared
postprocessing are retained. Abstention preserves latent probabilities. Auxiliary
risk never replaces a primary native score or changes its threshold decision.

Skops uses a reviewed standard-type allowlist; serialization scan results are not
a trust grant. ONNX external weights are enumerated and bounded; unregistered
custom operators are refused. Safetensors require built-in or identified installed
architecture factories. Opaque host registrations bind code/environment identity.
Uploaded manifests cannot request arbitrary imports or remote code. Explicit
local Python/CLI legacy conversion binds trust to exact executable pickle/joblib
bytes; no browser upload authorizes conversion. Supervision is not a security
sandbox.

CPU is the explicit default. `auto` resolves available admitted CUDA, then MPS,
then CPU. Explicit unavailable GPU requests refuse unless CPU fallback was
selected beforehand. Inference fallback restarts the application coherently;
training fallback restarts the entire fit from its initial state. Inference OOM
can halve batches at most three times; training batches do not change silently.
No distributed training, nested DataLoader worker pool or persistent serving is
introduced. Models load once per operation and are reused across batches/scenarios.

## Hardware qualification boundary

CPU, MPS and CUDA implementation state, current-host availability, actual runtime
qualification and scientific method standing are independent fields. Required
Apple GPU execution is PyTorch MPS. ONNX CoreML is optional and is not substituted
for MPS evidence.

Real CPU and MPS checks run on the recorded **CG6-MAC-01** M4 Mac. CUDA code,
provider/device translation, strict/hybrid placement, training integration,
accounting and failure contracts are implemented. Hardware-dependent CUDA tests
remain collected with `not_run_hardware_unavailable` reasons. Controlled provider
substitutes and CPU tests are contract evidence only: they cannot qualify CUDA
execution, numerical parity, allocation, cancellation or performance. Unavailable
external NVIDIA hardware does not block unrelated acceptance.

Same-weight device checks cover complete forward outputs, objective arithmetic,
backward gradients, a controlled optimizer step, finite fitting/checkpoints,
artifact round-trip, selection and cancellation. They do not require matching
training trajectories, learned weights, fixed predictive improvements or a GPU
speedup. Reference parity may remain unestablished if external outputs are absent.

## Auxiliary predictors

`auxiliary` implements fitting, selection, frozen artifacts, application and
independent assessment for conditional absolute-residual scale, conditional
quantiles and explicit failure-risk targets. The primary predictor is frozen.
Tabular inputs and prepared fixed vectors are supported; encoder fine-tuning and
primary-model training are excluded. Public services are `fit_auxiliary`,
`apply_auxiliary` and `assess_auxiliary`.

F alone fits parameters and preprocessing; disjoint predeclared S subroles select
checkpoints/candidates when needed. There is no automatic F+S refit. C computes
final conformal thresholds only after upstream freezing; E assesses independently.
Whole entities and all descendants retain their roles. Known training/selection
or primary-model overlap refuses affected claims; declarations cannot erase it.
Unknown primary training membership permits descriptive application, not invented
independence.

Fitted families are constant baselines, histogram boosting and bounded MLPs;
failure risk additionally admits regularized logistic regression. There is no
separate generic linear scale/quantile learner in the auxiliary candidate registry.
MLP ensembles
default to five independently initialized members. Supplied ensembles retain
member identities, complete common support, disagreement and variability. Neither
variability nor reference agreement becomes calibrated uncertainty or truth.

Scale targets absolute residuals, not conditional standard deviation. The positive
scale floor is explicitly declared before fitting and recorded; the current
implementation does not automatically estimate an F-derived floor. Quantiles
use pinball loss; ordered MLP heads have positive increments. Crossing independent
quantiles refuse by default. Declared rearrangement retains pre-repair evidence.
Fitted scale and quantiles feed unchanged CG2 normalized conformal/CQR through the
completed-prediction bridge. Marginal conformal interpretations retain their
exchangeability qualification.

Failure risk freezes classification/high-confidence/material-regression error or
a distinct execution-failure target. Missing truth is not a nonfailure. Diagnostics
include Brier/log loss (including genuine infinite log loss), prevalence,
calibration bins, AUROC, threshold average precision and risk-coverage thresholds.
Equal risk scores remain whole in ranking/selection diagnostics. These observed
utilities do not establish population or future-risk guarantees.

The locked scientific positive controls are CPU-reference method-integration
checks: five seeds, improvement in at least four, at least 5% median improvement
on the registered primary loss. They are designed learnable problems, not dataset
promises or hardware parity criteria. Their existing receipts must be reused when
later changes do not alter the exercised mathematics.

## Robustness laboratory

`robustness` implements registered missingness/corruption, constrained finite
differences and response curves, categorical substitutions, grouped permutation,
named gradient diagnostics, frozen subsets/mixtures, metamorphic relationships,
text/image transformations and finite attacks. Public services are
`inspect_robustness`, `run_robustness`, `freeze_robustness`, `assess_robustness` and
`stress_policy`.

Every variant binds its original root, scenario, replicate/proposal and materialized
content. Duplicate content can reuse deterministic inference without deleting
proposal accounting. Structural validity, feasibility, applicability, outcome
relation and declared realism are separate. Repairs are declared and revalidated;
feasibility does not establish realism or label preservation.

Unknown outcome relations are the default. Explicit alternatives are declared
label-preserving corruption, authoritative exact-variant outcomes, original-label
reference diagnostics and frozen registered outcome rules. The bounded data-only
outcome registry admits affine regression-unit changes and complete class maps;
it does not execute uploaded expressions. Labels for a pre-attack input cannot
label the final attack candidate. Authoritative final labels bind the exact final
variant identity; candidate-specific unknown labels cannot guide a ground-truth
attack objective. Reference/ensemble predictions never create authoritative truth.

Attacks are finite enumeration, constrained random/coordinate search, bounded
character-deletion text search, FGSM and multi-start L-infinity/L2 PGD over admitted continuous Torch
paths. Exact feasibility and complete preprocessing replay determine candidate
standing. Original/random controls, query/gradient/retry work, invalid proposals,
termination and best-so-far evidence are retained. Own-model and transfer attacks
remain identified by their actor. No failed search establishes universal robustness.
Broader character edits and registered span replacements are transformation
operations; they are not a general semantic or span-optimization attack engine.

Paired additive estimands average replicates within original roots, then average
roots. Native/common-support views keep their denominators. Coverage, efficiency,
confidence, loss and behavioral degradation remain distinct. Unknown transformed
truth cannot establish transformed accuracy or calibration. Nonfinite or missing
contributions never become invented zero loss or universal penalties.

Qualified claims freeze models, transformations, severities, metrics, bounds,
roles, assumptions, budgets and family allocation before E. Existing finite
Bernoulli/bounded-mean kernels apply to genuine original-root contributions;
replicated indicators use bounded means rather than pretending to be independent
Bernoulli trials. Complete bounded entities use the narrow ratio construction
below. Complete capacity worlds replay unchanged CG5 policies and preserve their
compatibility/failure semantics. Every world has one replacement per original
member plus unchanged members; attack samples alone cannot qualify full capacity.

## Bounded-cluster ratio

For independent complete clusters with a true predeclared event bound M and
individual contributions in [a,b], let A be the within-cluster numerator total and
D its denominator count. Then A/M lies in [min(0,a),max(0,b)] and D/M lies in [0,1].
Two Hoeffding intervals at alpha/2 jointly bound their expectations with error at
most alpha. If the denominator lower bound is positive, take the extreme endpoint
ratios and intersect with [a,b]. The estimate remains sum(A)/sum(D), preserving
event weighting. A nonpositive denominator lower bound is inconclusive; observed
maxima cannot supply M; bound violations refuse. This is the registered finite
method, not a general unequal-cluster bootstrap.

The frozen six-design, 2,000-trial-per-design qualification is retained. Assumption-
violating controls are supposed to refuse. No new research campaign or method
shopping is needed to close this implementation.

## Persistence and product boundaries

Catalog **v2** already supplies immutable object inventories, generic facts,
dependencies, parent-owned staging, atomic visibility, recovery, verified backup/
restore and transitive deletion. CG6 adds a bounded `opaque_artifact_bytes_v1`
codec and data-only descriptors, not a mandatory SQL schema migration. Binary
weights/media stream through staging, never large base64 result packets or fact
JSON decoding. Reopening/exporting never deserializes or executes a model.
Unsupported payloads/codecs refuse affected operations. Catalog-v1 workspaces
retain the established backed-up v1-to-v2 migration requirement.

Durable model retention copies bytes by default; explicit reference-only models
retain unchanged-external-file dependencies. Exact materialized inputs are the
default experiment evidence. `outputs_and_recipes` mode discloses weaker reopening
and refuses exact bridges/restatement. Budgets refuse excess retention rather
than silently dropping evidence. Later-outcome restatement reuses sealed outputs,
transformations, validity and memberships without executing models. It creates
new descriptive evidence; old inferential claims are not reissued.

Python and workspace facade methods share the same supervised services. CLI
groups are `predictor`, `auxiliary` and `robustness`. The existing owned loopback
API adds opaque model/auxiliary handles, revisioned drafts, fixed jobs, inspect
fingerprints, cancellation, workspace grants, paging and canonical exports. Browser
controls author contracts and present server evidence; JavaScript performs no
analytics. Model files cannot grant arbitrary paths/imports. Reopening retained
results rebinds copied model bytes and auxiliary handles after workspace relocation.

A single disclosure projection drives JSON, HTML/SVG and derived PDF. Raw inputs,
executables, memberships, witnesses, private definitions and sensitive dependent
findings remain protected. Planned and successful-output accounting remain visible
with their appropriate standing; withheld values do not become zeros.

## Dependencies and finite closure

Primary runtime is Python 3.13.17; a separate clean Python 3.12.15 compatibility
profile is admitted. The inherited CG5 environment and historical locks remain
untouched. CPU and GPU ONNX distributions cannot coexist ambiguously. Mac hash
locks are under `constraints/cg6-runtime-macos-arm64-py31{2,3}.lock`; the separate
Linux CUDA candidate lock is `constraints/cg6-runtime-linux-x86_64-cuda-py313.lock`.
Dependency resolution/imports are not hardware runtime evidence.

Pinned Torch 2.8 and ONNX Runtime GPU 1.26 have a CUDA 12.8/cuDNN 9 candidate
combination according to [PyTorch's release installation matrix](https://pytorch.org/get-started/previous-versions/)
and [ONNX Runtime's CUDA compatibility table](https://onnxruntime.ai/docs/execution-providers/CUDA-ExecutionProvider.html).
Linux cuDNN also needs the system zlib dependency described in
[ONNX Runtime installation requirements](https://onnxruntime.ai/docs/install/).
Actual NVIDIA qualification remains pending compatible hardware.

Verification follows `agents/skills/verify/skills.md`: coherent implementation,
small risk-driven diagnostics, reuse of valid evidence, one comprehensive affected
gate at closure, then targeted repairs and affected broader repeats only. Closure
also requires installed-wheel/optional-dependency checks, old-artifact and mixed-
codec lifecycle checks, real CPU/MPS evidence, actual browser workflows and visual
inspection of every page of the representative final PDF set.

Performance is bound to the observed CG6-MAC-01 hardware record and the frozen
`validation/cg6/performance_protocol.json`. One bounded calibration precedes
measurement. Admitted profiles have explicit sizes/RSS/device/disk/deadline budgets.
Larger reference sizes refused before measurement remain named capacity limits;
a failed measured profile cannot be shrunk and relabeled as the original success.
RSS plus MPS allocation is not distinct physical memory on a unified-memory Mac.
No universal speedup or hardware-independent capacity promise is introduced.
