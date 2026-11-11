# ConfidenceGuard CG4 — Failure discovery and investigation

Current project status (2026-11-04): CG1–CG4 are complete under the approved scope
revision and review corrections. Pending-acceptance language below is historical;
the supported-method boundaries and negative qualification evidence remain in force.

Status: **founder-authorized independent-review correction candidate**. Initial
independent review is complete; H1/H2/M1/L1/D1 corrections are implemented and
internally verified under the approved closure revision below. Targeted independent re-review, the
understanding gate and founder acceptance remain subsequent. Passing tests do not
establish universal recovery, approximate coverage or resource capacity. See
[the correction record](../validation/cg4/REVIEW_CORRECTIONS.md) and the retained
[implementation ledger](../validation/cg4/IMPLEMENTATION_STATUS.md).

CG4 extends ConfidenceGuard with one workflow:

**Prepare evidence → discover on D → investigate/select on S → freeze the entire
hypothesis family → assess on H → revisit immutable evidence.**

D/S/H are CG4 roles. They do not rename or replace CG2's F/S/C/E roles. Prediction
evaluation continues to use CG1–CG3 reducers. Diagnostic learners propose gates;
they do not define metric semantics. Investigation identifies associations, not
causes, and never changes models or policies. CG5, CG6 and CG7 remain outside CG4.

## Approved final closure scope — 2026-10-28

The founder approved [this explicit acceptance revision](../validation/cg4/CLOSURE_SCOPE_REVISION.md).
The full investigation product remains available. New formal confirmation supports
registered finite-sample procedures within their stated assumptions. General BCa,
cluster and ranking-percentile approximations are refused before H metrics because
their general operating envelopes remain inadequately qualified. Historical bytes,
research kernels and negative experiments are preserved; historical approximate
reports show their current standing without rewriting stored findings. This is an
accepted scope change, not successful qualification of failed methods.

The five current-selector synthetic recovery envelopes each passed 40/40 locked
seeds. Unfinished current-selector geometric/objective/history panels remain
unqualified/experimental; old standalone evidence retains its identity. The
landmark method is not promoted. The [method matrix](../validation/cg4/SUPPORTED_METHODS.md),
[qualification matrix](../validation/cg4/QUALIFICATION_MATRIX.md) and
[null-evidence bridge](../validation/cg4/NULL_EVIDENCE_BRIDGE.md) define supported
claims. No automatic full campaign or replacement-method research is required for
this delivery. Independent review and founder acceptance remain subsequent stages.

## Installation and runtime identities

The package requires standard GIL-enabled CPython **3.12 or newer**. Primary
development/qualification uses **3.13.17**, with **3.12.15** as the other required
runtime. The earlier 3.11 environment is retained solely as a comparison baseline.
`pyproject.toml` is authoritative; `setup.py` is a packaging compatibility shim.

The approved CPU locks use PyTorch's exact `+cpu` build where published. DataTrust
and CG4 accept that exact tag alongside the pinned public version and retain the
actual observed runtime identity. This admits no arbitrary local tag or newer
Torch version, and is not cross-platform numerical qualification. Existing macOS
public-version provenance and historical artifact bytes remain unchanged.

Install `.[cg4]` for SciPy, CatBoost and protected columnar evidence. Optional
text/image encoders use the existing `text-embeddings`/`image-embeddings` pins on
3.12/3.13. Python **3.14.9** uses a separate `cg4-encoders-py314` Torch 2.10 profile;
it does not become the accepted DataTrust Torch 2.8 profile. Torch 2.10's macOS
ARM64 wheel requires macOS 14+. The pinned Lingua 2.1.1 package has no compatible
3.14 distribution. Unicode 16 and regex pins remain unchanged; their controlled
3.14 source builds succeeded. These are capability boundaries, not a blanket
3.14 product-support claim.

An exhaustive scalar audit found Python 3.14's built-in case folding differs for
27 characters. The existing DataTrust text representation now uses a frozen
mapping matching every scalar in the accepted CPython 3.11 baseline. Unicode-16
NFC and the pinned regex grapheme rules stay unchanged. This preserves the old
representation rather than changing it under its historical identity.

`constraints/` separates supported direct constraints from exact hashed
qualification locks. The macOS 3.12/3.13 audits record installed distribution
manifest hashes, official package metadata and compatible wheel hashes. A lock
resolution or available wheel does not count as platform execution evidence.
WeasyPrint also needs system PDF/font libraries. Native runtime and fonts belong
in reproduction evidence. Historical artifacts remain readable without optional
learners; reapplying a learned gate requires its admitted runtime.

## Public workflow

Python exposes `InvestigationSpec`, `FeatureViewSpec`,
`DiscoveryRepresentationSpec`, `FailureObjectiveSpec`, `InvestigationLimits`,
`MembershipArtifact`, `ConfirmationSpec` and `FrozenHypothesisSet`.

```python
from confidenceguard import (
    InvestigationSpec, ConfirmationSpec, inspect_investigation, investigate,
    freeze_hypotheses, inspect_confirmation, confirm_investigation,
)

spec = InvestigationSpec.from_dict(specification)
inspection = inspect_investigation(spec)
discovery = investigate(spec, expected_fingerprint=inspection['fingerprint'])
protocol = ConfirmationSpec(
    upstream_independence='declared_independent',
    external_exposure='declared_unexposed',
    declaration_author='Investigation owner',
    declaration_reason='Describe the actual upstream and exposure provenance.',
)
frozen = freeze_hypotheses(discovery, confirmation=protocol)
feasibility = inspect_confirmation(frozen)
assessment = confirm_investigation(frozen,
    expected_fingerprint=feasibility['fingerprint'])
```

Declarations must describe actual evidence; they cannot override observed
contamination. Unknown independence produces a refused formal claim, while
descriptive investigation remains available. Every confirmable objective requires
a metric-specific practical threshold δ. Default subgroup comparison is against
the complement within the frozen eligible scope.

`confidenceguard investigation --help` exposes inspection, discovery, freezing,
confirmation inspection/assessment, reopening, canonical export and private
evidence resolution. `confidenceguard workspace --help` adds typed enrichment,
representation preparation, retained investigations, frozen-region replay,
outcome-only restatement, private annotations and restricted numerical retries.
CLI analytics call Python services. Discovery and confirmation commands write
canonical JSON alongside HTML/PDF and protected evidence bundles.

The local `/api/confidenceguard/v1` API uses revisioned investigation drafts,
opaque source/vector/model handles, owned frozen hypothesis sets and fixed jobs.
The served **Failure investigations** browser view provides guided controls and
complete-spec editors. CSRF, session ownership, worker-busy behavior, cancellation,
stale inspection and workspace attachment rules are shared with the existing app.
Result filtering/pagination never runs a new analysis. A bounded summary projection
opens the browser view; candidate and overlap pages remain available for retained
and session evidence. Complete canonical exports use the same result model.

CG4 defaults its result budget to 256 MiB, preserving explicitly configured limits
and the older milestones' 32 MiB default. Omitted objective units resolve from the
authoritative metric and task (for example nats or squared target units); supplied
incompatible units are refused. No numerical unit conversion is implied.

## Evidence and historical reconstruction

Typed features retain exact lexical/canonical values, explicit missing/invalid/
unavailable/not-retained states, units, semantic roles, ownership, clocks and
normalization identities. Exact integers and decimals do not pass through floats
to define structured gates. Learner conversion is separately frozen. Joins require
unique explicit keys; ambiguous or many-to-many ownership is refused.

Available-at-decision and retrospective views are explicit. Content availability
is separate from the later time an encoder runs. Outcome-derived fields cannot
define independently confirmable membership. Enrichment records actual
acquisition time and catalog sequence; earlier snapshots stay unchanged.

The `declared_information_cutoff_v2` policy retains the normalized per-owner
information cutoff and its valid/missing/invalid state in new typed feature facts,
including enrichment and encoded-content provenance. Live and retained decision
views apply that clock even when it differs from prediction time. An absent or
invalid required retained cutoff makes membership unavailable; prediction time is
not a substitute. New results and affected frozen hypotheses distinguish the
corrected policy. Original results stay readable without changing their bytes;
older cutoff-based discoveries/frozen claims cannot silently create new formal
confirmation under a different interpretation.

New prediction-batch version 2 supports typed retention without changing original
prediction variant identities. Existing version-1 serialization is preserved.
Catalog version 2 requires explicit migration after a verified backup. Accepted
JSONL objects remain unchanged. New typed facts use bounded Zstandard Parquet;
dense vectors use non-object, C-order little-endian NPY shards. SQLite indexes
identity/lifecycle/provenance; disposable DuckDB performs reconstruction. Physical
object hashes and logical row/vector digests serve different integrity checks.
Publication, backup, restore, recovery and transitive deletion cover every codec.

Supplied vectors require keyed metadata, dimensions, precision, normalization,
producer identity and content-availability declarations. Optional offline E5-small
(384 dimensions) and DINOv2-base (768) profiles verify pinned publisher files.
They run bounded CPU execution with no downloads or remote code. Text windows
pool into one event vector; windows do not become independent observations.
Partial text coverage is retained. Encoders do not fit on investigation labels.

## Discovery and frozen membership

Each objective binds its eligible population, conditional denominator, diagnostic
target/proxy, authoritative reducer, comparator, adverse direction and units.
FNR/FPR/precision use their own conditional populations. Calibration uses signed
target residual heads and frozen-bin evaluation. Regression uses signed or
appropriate loss targets; ranking uses D-only proposal proxies followed by exact
AUC/AP evaluation. Uncertainty and paired/historical objectives retain their
original output semantics. A generic error classifier is not a substitute for
independent qualification of these objective families.

For an absolute ceiling objective, a fixed whole-population baseline is admitted
when D has the required conditional support, independently of the chosen discovery
strategies. Uniform failure can exceed a ceiling without exceeding its own mean,
so a heterogeneity learner alone cannot cover this case. The exact empty
conjunction requires no feature/representation and is total on admitted rows.
This adds at most one explicitly inspected candidate per ceiling objective,
uses no search nodes or native fits, and goes through the same authoritative S
evaluation and frozen-family confirmation as other gates. Definition identity is
reported separately from empirical refit stability. A nonadverse baseline is not
automatically shortlisted. Complement/overall objectives do not gain this baseline.

Historical proposals use three D-only targets: current-period base loss,
negated reference-period loss, and finite within-entity current-minus-reference
mean loss where both conditional targets exist. This avoids assuming that
deterioration necessarily creates unusually high current risk. Unpaired rows
remain available to the raw period heads. The entity target is a diagnostic
proxy, including for nonadditive metrics; final historical effects still use the
original event-weighted/shared reducers. Target bindings retain periods,
conditional supports, proxy units, missing pairs and fit-row admission. Structured
targets share one node budget, split among remaining eligible heads, and one
candidate cap; actual CatBoost fits count against the global fit budget.
Geometry inspection exposes per-fit distance budgets and total fit-count ceilings.
These are admission bounds, not capacity guarantees. Full historical recovery
qualification of this revised target policy remains outstanding.

* Structured search uses deterministic exact predicates and conjunctions, packed
  masks, support pruning and bounded D-only disjunctions. Budget exhaustion is
  reported as incomplete search within the admitted predicate class. Weak
  marginal effects do not prune interaction-only branches.
* CatBoost uses frozen CPU profiles, objective-specific targets, explicit numeric
  transforms and collision-safe category/state tags. JSON export/reload precedes
  canonical scoring. Membership is a frozen score threshold/band; category,
  missingness, unseen-category and floating-boundary parity are mandatory.
* The geometric fallback proposes multiscale balls/annuli and bounded unions.
  The landmark graph/kernel method is an **original NUMEK proposal**. Its default
  promotion requires locked complementary-recovery and resource evidence. Research
  about manifold methods does not establish this algorithm's effectiveness.

Transforms/models fit only D. S selects from D-proposed candidates/thresholds using
authoritative adverse effects. There is no automatic D+S refit. Exact-definition
duplicates share work; distinct gates that match an observed mask retain distinct
identities. Reconciliation records effect/support/complexity frontiers, containment,
Jaccard overlap and unique union support. Example selection and approximate
surrogates support investigation. Surrogates do not redefine membership or causes.
Explanation fidelity uses joint gate/surrogate applicability. Current results retain
planned, gate-available, surrogate-available and jointly available support, including
gate members without an applicable surrogate. The legacy `available` field remains
an alias for joint support; older results are not backfilled. Canonical reports show
these denominators beside conditional fidelity. Rare related cells remain protected.
D perturbation stability is separate from locked method qualification.
The current `bounded_D_unit_bootstrap_refits_v2` matches refits within the same
strategy, representation and diagnostic target/head using S features only.
Earlier v1 evidence remains readable but can match across representations and
does not qualify the stricter v2 diagnostic. Neither version uses S outcomes to
choose the stability match.

After the first selected region for an objective, additional default-shortlist
regions must contribute an uncovered S population with sufficient conditional
support and a native adverse effect above the declared practical threshold (or
zero when no practical threshold is supplied). This selection-only evaluation
excludes already covered members explicitly, retains unavailable reasons and does
not change any candidate gate or confirmation population. All retained candidates
remain inspectable/selectable. This prevents overlapping boundary variants from
filling a shortlist solely because each has an adverse aggregate effect.

Current automatic selection is versioned as
`severity_material_excess_support_frontier_v2`. It preserves the first severity
gate and then considers one anchor ranked by
`(native adverse effect − declared practical threshold) × conditional support`
within that objective, subject to the same overlap and marginal-admission checks.
Remaining slots follow the Pareto severity/diversity ordering. Missing thresholds
do not become invented material zeroes. This is a transparent selection heuristic,
not a utility policy or guarantee of recovery. Inspection fingerprints bind its
version. The original broad/narrow panel failed 19/40 against 32/40 required;
retained D/S improvement motivated the revision. Five fresh locked profiles now
pass; other current-selector profiles remain unqualified. Old results preserve
their original selection provenance.

Application returns **member, nonmember or unavailable** with reasons. Geometric
out-of-support observations stay in the planned denominator. A conditional
supported-population claim must freeze that scope and comparator; reports show
coverage against the full planned population. A full-population claim requires
total applicable membership or an independently justified bound. H shortfalls
cannot trigger a new boundary, estimand or comparator.

## Confirmation and numerical feasibility

Whole-entity D/S/H allocation defaults to 50/25/25 with seed 0. Independent-row
allocation requires an explicit design. A frozen hypothesis binds its gate,
metric/δ/direction/units, eligibility, membership scope, comparator/pairing,
sampling/weighting, feature/representation snapshots, outcome policy, family,
inference method and error allocation. Assessment identity additionally binds the
actual evidence snapshot. All hypotheses remain in the multiplicity family,
including unavailable or refused claims.
New `frozen_failure_hypothesis_v2` records also bind canonical observation
interpretation: effective inline outcome authority, status mapping, label/key/clock
bindings, or retained authority/maturity/context policy. Confirmation cannot change
that interpretation, switch supplied/retained contracts, or change the feature-time
view. Retrospective feature cutoffs are canonical instants and remain fixed.
Future H source files and outcome snapshots/cutoffs remain explicit inputs bound by
the inspected population fingerprint and assessment identity before H reservation;
they do not authorize revised eligibility semantics. Predeclared outcome restatements
preserve the original feature snapshot. Existing v1 hypotheses stay readable and
retain their original bytes/identities; their stored specification supplies the
same admission guard on reuse.

Larger oriented effects θ are worse; practical confirmation tests θ > δ. Default
study error is .05. With m frozen hypotheses and c elementary two-sided intervals
for a hypothesis, each component gets α/(mc), with nominal tail α/(2mc). The
20-observation bootstrap-tail safeguard therefore requires 25,600 replicates for
m=32,c=1; 51,200 for c=2; 102,400 for c=4. **20,000 is only a baseline request.**

Fixed-budget policy refuses inadequate B. Nominal admission computes B before H,
within a visible caller maximum (default 200,000). BCa-adjusted tails depend on H
and receive an additional resolution check after reservation. All requested
replicates must be valid; degenerate jackknife/distributions, nonfinite original
statistics, insufficient support, memory/work/deadline exhaustion and adjusted-tail
failure refuse the affected interval. Confidence, the family, estimand and method
are never silently weakened. The 20-tail rule is a numerical safeguard, not a
coverage theorem.

CG4 work admission counts every planned bootstrap-kernel call, including separate
absolute-effect components, and includes the registered ranking setup estimate.
These are versioned computational estimates, not wall-time or memory guarantees;
the supervisor still enforces actual limits. An undersized inspected budget stops
the assessment before H metrics, with the frozen family and confidence unchanged.
This accounting correction does not modify bootstrap draws, interval mathematics or
the qualification status of a method.

Finite procedures include IID Clopper–Pearson Bernoulli intervals, conservative
component composition for registered rate/confusion functions and Hoeffding bounds
for independent contributions with bounds declared before H. H extrema cannot
define those bounds. Inspection rejects unsupported method/metric/sampling
combinations before computing or disclosing H metrics: IID-row finite procedures
cannot correct entity dependence, finite ranking intervals are not registered,
and an unbounded mean requires a separately qualified method. Bounds on a
pointwise proposal loss do not register an interval for a different nonadditive
native metric. Registered F1/calibration composition and declared bounded means
retain their existing procedures. Observed bound violations and insufficient
conditional support still require reserved assessment; they are distinct from
these outcome-independent registration checks.

An explicitly selected `sampling="independent_entity_arms", method="finite"`
supports the narrower design of IID complete entities with at most one potential
observation per frozen comparison arm. Different arms may be dependent within an
entity. Conditional on each arm's eligible size, its contributions are IID across
entities, so the same marginal CP/Hoeffding/component intervals and Bonferroni
composition apply. Event weighting is unchanged. Before H outcomes, inspection
counts potential records before label/class filters and refuses duplicate records
within an arm, missing entity keys or non-entity D/S/H allocation. A design
declaration must guarantee the constraint; passing the observed check cannot prove
IID entities, complete extraction or absence of common shocks. General
`independent_entities` finite inference remains refused, and no one-row sampling or
automatic fallback changes an existing estimand. See the
[design proof, checks and negative evidence](../validation/cg4/ENTITY_ARM_FINITE.md).
The recorded 32,000 positive-panel trials and 400 assumption-violating controls
qualify only this finite design's implementation envelope. Near-threshold effects
can remain inconclusive despite strong-effect power. General unequal-cluster and
unbounded-mean confirmation is deferred by the approved closure revision; the
failed general methods remain refused.

BCa/percentile/whole-entity numerical adapters are research/historical procedures,
not enabled general formal confirmation. They need method-specific qualification. Entity resampling preserves event-weighted
estimands, paired/overlapping groups use common draws, and relevant independent
support includes imbalance/effective-support checks. Moving-block bootstrap is
excluded from CG4 confirmation because CG3's negative coverage evidence remains
unresolved. Unknown temporal dependence/common shocks refuse formal inference.

Qualification has found substantive limits: the locked 200-unit heavy-lognormal
and unequal-cluster panels rejected nominal two-sided coverage after the declared
Holm diagnostic adjustment. SciPy reference intervals agree with the numerical
implementation. These profiles **failed method qualification**; the 30-unit
admission floor is not sufficient evidence of coverage. The other panels do not
establish arbitrary-distribution validity. See the complete
[approximate-procedure evidence](../validation/cg4/results/approximate-panel-summary-v1.json).
The founder explicitly deferred resolving the general operating envelope from
CG4 closure; this is a recorded acceptance-scope change. Component-BCa and bootstrap-t candidates also remain disabled after
retained coverage shortcomings; none can silently replace a frozen method.

R2 discovery uses the versioned `negative_squared_residual_for_r2_v2` proposal
target. Negating squared residuals aligns its direction with the native metric:
lower R2 is adverse, so its diagnostic head favors larger squared errors. This
remains a proposal heuristic because subgroup target variance also affects R2.
Final S/H evaluation uses the unchanged regression reducer, and pointwise error
bounds do not establish an R2 confidence interval. Earlier artifacts retain their
original target metadata and identity; their stored evidence is not rewritten.
The retained [variance counterexample](../validation/cg4/results/r2-variance-counterexample-v105/summary.json)
has D subgroup R2 about -99.00 versus .960 in the background, while mean squared
error is only 1 versus 4. Thus the proposal head alone can rank native R2 failures
incorrectly when target variances differ. The native reducer agrees with independent
arithmetic. This is a proxy limitation, not a new measured learner-recovery failure.
The separately prepared equal-variance 40-seed recovery panel has not yet run.

Simultaneous intervals classify confirmed (L>δ), unreproduced (U≤δ), inconclusive,
or statistically inadmissible claims. Exploratory means no independent assessment.
Cancellation and execution failure are separate job states. Exact intervals remain
conditional on sampling assumptions; approximate intervals are not finite-sample
guarantees. Selective labels establish an observed-label estimand, not unobserved
full-population performance. Frozen conformal output assessment does not establish
conditional conformal coverage.

`retry_confirmation` only resolves recorded numerical insufficiency. It requires
the same family, estimator, seed, population and evidence snapshot, links the prior
record, retains the deterministic draw prefix and reuses unaffected findings.
It is not another independent test or a way to search for favorable findings.

## Exposure, lifecycle and privacy

Optional protected exposure tracking has consent separate from feature retention.
It records D/S use, reserved H, outcome-dependent disclosures, study allocation,
snapshots, declarations and branch continuity. CG1–CG3 workspace analyses/disclosures
reserve exposure first when tracking is enabled. A cancelled/crashed reservation
does not restore freshness. Local overlap checks, declared upstream independence
and exposure continuity are reported separately. **No recorded use does not mean
no earlier use.** Controls are study-scoped; there is no workspace-wide statistical
guarantee or coordination of unobservable external investigations/forks.
Historical overlap checks also disclose whether original source aliases are retained.
When they are incomplete, canonical historical D/S/H comparisons remain observable,
but the local check is marked partial: differently named live-source reuse may be
unobservable. A missing alias or ledger record does not establish untouched evidence.
Upstream/external declarations are never relabeled as system verification.

Deletion remains permitted and makes relevant future continuity incomplete or
unknown. Restores retain lineage but require reconciliation of continuity;
an old backup cannot prove no later exposure. Immutable outcome-only restatements
preserve original prediction/feature/membership evidence. Default restatements and
historical replay are descriptive. Formal repeated looks require a study ID and
`ConfirmationSpec.restatement_schedule`: look IDs, outcome cutoffs and individual
α allocations frozen before the initial H reservation. Initial plus scheduled
allocations cannot exceed the study error budget. `inspect_restatement_confirmation`
and `restate_confirmation` verify the retained original family/reservation/schedule,
uninterrupted local tracking and branch, unchanged planned events and membership,
and the exact scheduled cutoff. A spent look cannot be applied to a new outcome
snapshot with a reset allocation. Restored/interrupted histories without the
required proof refuse scheduled inference. Repeated looks do not need independence
from each other for component Bonferroni control, but each procedure still needs
its original sampling/observation assumptions. This is predeclared study-scoped
reuse, never fresh independent evidence or global fork coordination.

Supervision uses the existing shared local worker lock, bounded staging and
caller-visible search/vector/inference/encoder/resource limits. Defaults remain
two threads, 2 GiB DuckDB, 6 GiB RSS, thirty minutes, 64 GiB workspace and 2 GiB
free-space reserve. S/H are not silently sampled. Hard termination does not
fabricate a completed investigation. Immutable publication is parent-owned and
verified before commit; cancellation and commit visibility retain existing rules.

Vectors, learner parameters/CTRs, landmarks, definitions, rare values, memberships,
notes and examples are protected. Hashes are identifiers, not anonymization.
Conservative disclosure jointly protects related support/effect/overlap evidence
and applies to HTML, embedded JSON, SVG/tooltips and PDF text. A shared import
cannot recover withheld evidence. Learned-artifact export is separate from exact
aggregate disclosure. One result model drives browser and canonical HTML/PDF/JSON;
PDF failure preserves available canonical HTML/JSON.

## Qualification and review boundary

The locked [current protocol](../validation/cg4/qualification_protocol_v2.json) separates fast
correctness/contracts, focused discovery qualification, statistical/full-pipeline
null simulation, capacity measurement and complete product/lifecycle verification.
It records recovery panels, objective-specific criteria, negative/null cases,
out-of-sample membership, geometric coverage, fidelity/stability, comparison budgets
and landmark promotion thresholds. Implementation bugs invalidate affected evidence;
correctly implemented method failures remain negative findings. Targets are not
weakened after observing failures. Unaffected locked evidence may be reused.

The 40-seed curved-region anchor met its locked recovery criterion in 40/40
trials (median H precision .87219, recall .96998). This is evidence for that
anchor, not for every nonlinear objective or landmark promotion. Other completed
archetype/objective panels and their exact scope are recorded in the implementation
ledger. Matched comparisons now include four complete families: categorical and
interaction first-gate coverage can be worse than simpler trees/rules, while
curved/density panels favored the native first gate against all five baselines.
Secondary shortlist-union performance does not replace primary gate comparisons.
Historical current-risk recovery completed at its original profile; unfinished
current-selector/reference-only panels remain unqualified, rather than automatic
delivery campaigns. The 2,000-trial reduced complete-null
panel recorded one false-confirmation family; 200 distinct default-profile runs
recorded none. Neither fixed Holm excess-error diagnostic rejected. Panels are
not pooled, and non-rejection is not proof of nominal control. The exactly enumerable
[partial-null protocol](../validation/cg4/qualify_partial_null.py) keeps true nulls,
alternatives, undefined truth and actual frozen-family sizes separate.

The [simpler-method comparison](../validation/cg4/compare_baselines.py) uses fresh
180000–180039 seed datasets across four archetypes. Depth-two rules, a shallow
tree, one diagnostic learner, outcome-blind clustering and simple balls share
native preprocessing/membership/reducers and the same one-gate S selection rule.
Full native shortlist recovery is secondary and cannot replace an unfavorable
one-gate comparison. Twenty paired-median uncertainty intervals use exact
binomial order-statistic bounds with Bonferroni allocation, conditional on the
declared independent seed-pair design. Development includes weaker native first
gates; superiority is not presumed. Concurrent timings and shared worker RSS
do not establish controlled relative-efficiency ratios.
Fixed-bin calibration illustrates a separate power limitation: recovery passed
40/40 seeds, yet all 184 selected hypotheses were inconclusive under their finite
simultaneous component bounds. Recovery, explanation quality and confirmation
power are separately assessed; no weaker interval or reduced family was substituted.
Scoped Python 3.14 regression execution has 874 passes and one skip, with two
unadmitted original DataTrust model profiles: Lingua 2.1.1 and Torch-2.8 E5.
The separately identified CG4 Torch-2.10 profile does not override those runtime
identities. Linux/Windows lock resolution remains distinct from executed support.

Implementation delivery requires code/docs, qualified required capabilities,
compatibility/regression/security/privacy/lifecycle evidence and a verified
technical-review ZIP. Preparing that ZIP is **not** independent review or acceptance.
The initial independent review and founder-authorized H1/H2/M1/L1/D1 correction
implementation/verification are complete. Targeted independent re-review, the
understanding gate and founder acceptance remain pending; see the correction record.

## Qualification corrections and retry integrity

The original generic joint-BCa contrast failed locked heavy-tail and unequal-cluster
coverage diagnostics despite numerical agreement with SciPy. Formal confirmation
with that profile is currently refused before H outcome access. Its numerical
kernel remains for historical reproducibility and qualification. A separately
identified component-BCa candidate met a separate locked power/availability panel,
but its component means showed undercoverage in a post-hoc retained-trial audit,
including heavy-tail and unequal-cluster cases. It is not an automatic fallback
or an enabled qualified replacement. A separate bootstrap-t prototype uses analytic
unit-influence variance and complete-unit resampling. Its complete 10,000-trial
locked panel failed heavy-skew/asymmetric-arm/mean-ceiling diagnostics despite
all intervals being available. General approximate mean confirmation is an explicit accepted deferral and
cannot support new formal claims. A separate validation-only fixed-time
variance-bound prototype requires externally justified unconditional unit-level
population variance bounds. It adds no general unknown-variance guarantee or
product method. Its assumptions, proof boundary and remaining qualification are
recorded in [the prototype note](../validation/cg4/MOMENT_CANDIDATE.md).
Its 10,000-trial conditional screen passed without rejected excess-error diagnostics,
but heavy-lognormal intervals were wide. Deliberately false bounds and dependence
caused severe failures. No useful-power or general unknown-variance claim follows.

Conservative shareable reports explicitly withhold overlap/unique-union detail;
pair-cell safeguards alone do not qualify all higher-order aggregate combinations.
Protected local reports retain it. An explicit `exact_aggregates_v1` disclosure
policy can retain overlap counts with public region aliases, without learned
artifacts or private identifiers. Missing displayed pairs never establish
disjointness. All audiences use the same canonical report projection.
CG4 shareable Python/CLI/transport exports create no protected reopening bundle,
including under exact aggregate disclosure. Explicit local export retains one.
The accepted CG1–CG3 artifact behavior remains unchanged.

The original landmark proposal failed promotion in the locked curved-region
comparison: after 21 pairs, the observed median IoU gain was -.24853 and even the
maximum attainable 40-pair median was -.16329, below +.10. Its default-profile
promotion is rejected; this is not a completed two-family/resource qualification
or a universal inferiority claim. Product method standing retains the negative
[comparison evidence](../validation/cg4/results/landmark-negative-integrity-v1.json).

Frozen family schema 1.1 binds the complete confirmation protocol, including seed,
replication and support policies, except execution request identity. Legacy 1.0
bytes remain readable; evidence reuse checks still bind their complete applied
protocol. A permitted numerical retry uses the identical family, population,
estimator and deterministic draw prefix. It reserves one larger budget per origin
before H is accessed. A crash resumes that attempt; further extension requires its
insufficient child. Deleted, missing or restored attempt history cannot reset this
chain. Session checks have process scope; protected workspace checks have branch/
study scope and do not prove that unobservable external investigations did not occur.

Qualification protocol v2 corrects a NumPy-scalar CSV generator defect and preserves
the original acceptance targets with untouched seeds. Affected old numeric-feature
panels are retained as invalid-covariate evidence. Valid-vector curved, statistical,
storage and compatibility evidence have separate reuse scopes.

## Execution-boundary and review records

`MembershipArtifact.apply(typed_features, representations, config=..., limits=...)`
applies a frozen gate through the existing supervised worker. Inputs are prepared
typed cells and aligned floating-point vectors/Boolean availability, not raw
unvalidated columns. It returns ternary membership arrays, reasons, optional margins
and execution accounting. Caller thread, row, memory, distance, deadline and
cancellation limits apply. This mathematical application does not establish
independence or confirmation; investigation services retain temporal joins and
evidence provenance. CatBoost training and application honor the caller's thread
limit. `InvestigationLimits.diagnostic_fits` defaults to 512 and counts stability
refits as well as initial fits; exhaustion refuses completion.

Omitted adverse direction resolves to the metric's registered default at inspection
(for example lower precision or larger absolute bias). Explicit directions remain
unchanged. There is no universal practical-effect default: each selected hypothesis
requires an explicit threshold in its metric units before H. The guided candidate
table permits separate thresholds; changing them or the selected family requires
freezing again. Bounds describe pointwise contributions before root/absolute
interval transformations; RMSE contributions therefore have squared target units.

General AUC/AP percentile confirmation is refused before H metrics under the
approved closure revision. Its retained research/historical adapter includes
independent/effective class-support checks, but those checks do not establish
general qualification or register a new formal route. Native AUC/AP evaluation
and exploratory discovery remain available. All frozen hypotheses remain in the
multiplicity family when individual claims refuse assessment.

Paired precision objective v2 uses a common issued-prediction population, with
each model's own predicted-positive denominator inside that base. Intersecting
the predicted-positive sets would erase decision-set differences. For proposals,
D-only reference ratios define `I(positive)*(I(y=target)-precision_D)/P_D(positive)`
for each model; their difference is a diagnostic influence proxy. It is not a
subgroup precision estimator or a qualified recovery guarantee. Shared reducers
recompute both native precisions, and finite component intervals retain distinct
supports and the complete family allocation. Earlier paired-precision records
remain readable; their unqualified population semantics refuse silent freezing,
confirmation or historical replay. A new investigation is required. Single-model
precision and other paired metrics retain their existing definitions.

[Implementation findings](../validation/cg4/CG4_IMPLEMENTATION_FINDINGS.md) records
important bugs, method failures, negative experiments, corrections and limits. The
review ZIP must include that document and its referenced evidence in the hashed
manifest; `validation/cg4/review_inventory.py --zip PATH` checks that inventory.
This packaging check neither reruns qualification nor constitutes independent review.

Exposure history gaps require a current scoped declaration, tied to the workspace's
protected continuity token. An old `declared_unexposed` assertion does not cover a
later restore, deletion or tracking-consent gap. Such declarations qualify missing
history; they never override known exposure or establish system-verified history.
The guided checkbox is off by default. Historical investigation, confirmation and
replay infer their retained workspace when the Python keyword is omitted and
reject redirection to a different workspace. Linked numerical retries retain that
workspace and refuse changed continuity. Legacy families remain readable.

Protected in-process exposure observations are associated with their workspace
instance and durable use record. Deletion releases references for deleted uses;
purge releases that instance's observations. Other owners and standalone uses
remain intact. Untracked observations lack durable row locators, so deletion
releases that workspace's untracked observations and retains a continuity gap.
This is logical deletion of retained references, not physical RAM sanitization.

An authorized browser workspace participates in live CG4 exposure checks even
when result retention is off. Tracking consent and durable result/feature saving
remain separate. With tracking enabled, live CG1/CG2 outcome assessments reserve
observable use before analysis; interrupted jobs retain that reservation. CG2 fit
records F/S/C rather than E. Unkeyed earlier assessments conservatively identify
the whole supplied source, while keyed role reservations retain row separation.
Missing identities or unobservable external copies still do not establish freshness.
Detaching a workspace revokes access to its bound jobs/results, including
idempotent job responses. These controls do not establish workspace-wide error control.

### Guided inputs and frozen diagnostic evidence

Required guided numeric values reject blank/nonfinite entries and preserve explicit
zero; ceilings have no universal default. A composition attempt invalidates stale
family/feasibility/export state. The whole-population ceiling gate is an exact empty
conjunction with no fitted parameters; its identity is distinct from empirical
stability or future effect reliability.

New qualification records retain already computed product diagnostics and assess
frozen explanation surrogates using independent feature rows, with planned/jointly
applicable/unavailable denominators. Prior summaries without these fields remain
unrecorded. Surrogate fidelity can be poor while the exact learned membership is
useful; no universal high-fidelity label or causal interpretation is added.
Current report-only and guided-browser evidence is indexed by verification
manifests v27–v29 in `validation/cg4/results/verification/`. It does not complete
analytical qualification or independent review.

### Supplied outcome-status provenance and observation scope

Explicit outcome-status mappings additionally accept `pending` and `withdrawn`.
The original five-state default mapping and CG1 eligibility/reducer behavior remain
unchanged. CG4's descriptive sidecar preserves canonical status counts, hides
statuses unavailable at the as-of cutoff even when another maturity reason takes
precedence, and keeps the original normalized-row/population identity. CG3 captures
retain the new explicit statuses as immutable outcome facts.

Direct bindings to the outcome status column, including observable byte-identical
source aliases, are outcome-derived evidence and cannot define independently
confirmable membership. This positive check cannot discover arbitrary hidden
upstream transformations. Shareable status counts use fixed labels and the same
joint rare-component protection as their effects. Browser/API/HTML/PDF/JSON retain
`observed_labels` versus `complete_population`; selective labels never establish
rates for unobserved outcomes. Actual exposure and reserved-history controls still
apply to every assessment.

### Legacy origin and canonical inline authority

The existing single-run inline outcome rule is exposed by
`EvaluationSpec.effective_outcomes`; serialized requests, accepted metric semantics
and method identities are unchanged. Normalization, known outcome-feature admission
and exposure reservation use that same authority, so implicit labels cannot bypass
the protected ledger.

Older captures can supply positive outcome-origin evidence through their retained
batch/source metadata even without a later `known_outcome_fields` marker. Legacy
context fallback is positively identified only when every possible recorded source
agrees. Unambiguous single-run captures with exact event-key bindings also recover
original lexical event/entity identities and file aliases from the prediction's
capture operation and retained opportunity identity. Namespace and outcome-definition
versions must match. Ambiguous or missing provenance is not guessed and never proves
independence. Used metadata participates in transitive deletion dependencies; no
original fact/object is rewritten. Synthetic old-source controls and focused
verification are indexed in manifest v34.

### Selection-coverage qualification boundary

The first completed 40-pair interaction baseline panel found native one-gate median
H IoU .13454 versus .49309 for low-order rules. The native-minus-rule median paired
gain was -.24811, with its fixed 20-contrast median interval [-.42155,-.02284]. The
native gate was more precise and much narrower. Its full shortlist union's .99798
median IoU remains a separate secondary result. This does not justify changing
locked selection/acceptance rules using H or claiming universal superiority from
favorable recovery panels. Unfinished comparison families remain unqualified; no automatic continuation is
required under the approved closure revision.
