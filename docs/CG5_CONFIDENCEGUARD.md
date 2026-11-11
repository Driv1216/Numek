# ConfidenceGuard CG5 — decision policies

## CG5 completion — 2026-11-06

The founder has confirmed CG5 is fully completed, including implementation,
independent review, R01–R09 and D1–D5 corrections, engineering verification and
the implementation understanding gate. This decision supersedes pending-review,
pending-understanding and pending-founder-acceptance language retained below.
CG1–CG5 are complete within their approved scopes; scientific limitations and
source-specific historical evidence remain unchanged. No CG6 work is implied.

The [final implementation explainer](../validation/cg5/CG5_FINAL_IMPLEMENTATION_EXPLAINER.md) covers architecture, source files,
policy semantics, optimization, statistical assessment, four execution scenarios,
corrections, limitations, glossary and 15 technical questions. Its quick
requirements review found all 13 requested areas present and no material issues
in the technical spot-checks; no test suite was rerun for that document review.
The explained 190-file runtime identity is
`7d3f64affcbc9491223e23294482149848f3bd945a7aaefce33af4af7b3fc3b9`.

CG5 is **not founder-accepted**. The 2026-11-04 independent review found material
defects in the original verified source. The authorized targeted correction pass
and its new evidence are recorded in
[the correction ledger](../validation/cg5/review-corrections-20261104/REVIEW_CORRECTIONS.md).
The second independent re-review and targeted D1–D5 corrections are recorded in
[the current correction report](../validation/cg5/defect-corrections-20261105/DEFECT_CORRECTIONS.md).
Original verification receipts remain historical evidence for their original source.

CG5 adds typed offline policy replay, development selection and frozen independent
assessment inside ConfidenceGuard. A policy can be executable without being
empirically feasible, optimal or independently supported. Those states remain
separate throughout Python, CLI, local API, browser and canonical reports.

CG1–CG4 are complete under the project's approved acceptance scope and corrections.
Their historical evidence is preserved. CG4 general BCa/unequal-cluster, ranking
percentile and temporal confirmation remain unqualified; CG5 does not promote them.

## Contracts and actions

Use `PolicySpec`, `PolicyInputSpec`, `PolicyStudySpec`, `PolicyApplicationSpec`,
`PolicyAssessmentSpec`, `PolicyLimits`, `FrozenPolicy` and `FrozenPolicyFamily`.
New schemas use `confidenceguard.policy_*/1.0`; completed results use
`policy_selection_v1`. Existing CG1–CG4 request and artifact meanings remain intact.

A fully bound policy has a single-entry acyclic graph of `action`, `rules`, `accept`
and `capacity` nodes. Predicates are typed comparisons, finite sets, state/region
tests and all/any/not combinations. There is no executable expression, user SQL,
Python callback, loop, randomized mixture or user-loadable optimizer plugin.
Unresolved parameters are allowed only in finite study prototypes. Native score
units, exact integer/decimal feature semantics and whole equal-score groups are
preserved. Tagged all/none cuts replace artificial infinite thresholds.

Binary/multiclass policies emit declared labels, replay supplied actions, threshold
registered inputs, use argmax, or choose from complete-probability expected decision
costs. Regression policies use points, identified quantiles, sample means/medians
or finite numeric actions with absolute, squared, signed, material-error or pinball
loss. Predictive samples can support registered expected numeric losses. Quantiles
do not invent predictive tails. All tasks can abstain or defer to a named process.

Every policy declares terminal fallback and unavailable actions. Strong Kleene
logic governs unknown inputs. An unresolved earlier ordered rule cannot fall
through to a later true rule. Ties abstain by default; `action_order` is an explicit
alternative. Ordered residual routing, overlaps, unresolved predicates and fallback
use remain in protected evidence.

Corrected input identity `policy_input_semantics_v2` also binds upstream decision
rules, thresholds, tie/issuance semantics, supplied prediction mapping, prediction
clock declarations and probability-admission tolerance. Old bound CG5 policies
remain readable; incompatible v1 reapplication refuses instead of silently changing
the old digest. New binding requires an explicit new policy definition/selection.

Each planned opportunity has exactly one issued/abstained/deferred/unavailable
policy action. Original prediction failure, issuance, feature availability and
region applicability remain separate. A supplied incumbent trace does not recover
an executable production rule. Conventional constant-class, supplied and abstain
baselines are retained, including undefined or infeasible comparisons.

## Economics and denominators

Decision costs used by an action change the executable policy digest. Evaluation
costs, objective weights and operational prices affect scoring/study identities,
without changing replayed actions. Complete cost mappings are required wherever
used. Missing abstention/review/failure values are unavailable, never zero.

Evidence bases are explicit: historical observed-outcome proxy loss; model-implied
expected loss; known operational charges; missing-label lower/upper envelopes; and
independent population claims. Do not add quantities with different populations
and call the sum net expected cost. Deferral supplies no reviewer effectiveness.

Coverage and workload use all planned opportunities. Selective accuracy/loss uses
its own eligible issued labeled support. Opportunity recall includes every observed
outcome of the target class and counts non-emission as failure to emit that class.
Precision uses each policy's own predicted-positive denominator, never the
intersection of two policies' positives. All-abstain has undefined selective risk.
The nominee's development profile records issued coverage, label availability and
cohort support. Missing labels never silently shrink a full-opportunity estimand.
`partial_lower`/`partial_upper` bound costs over all opportunities;
`selective_partial_lower`/`selective_partial_upper` use the full issued denominator
and simultaneous numerator/acceptance bounds for population assessment.

## Search and numerical standing

- Grouped sweeps cover admitted distinct scalar groups plus tagged endpoints for
  incremental additive/confusion metrics. General nonincremental metrics use
  finite replay/search rather than inheriting the sweep's cost profile.
- Enumeration is complete only when every member of the declared finite family
  is evaluated. A grid is exact within its grid.
- Fixed residual-cell MILP selects one leaf option per cell. Fixed-denominator
  sums, registered ratio constraints, absolute-bias and worst-window epigraphs
  are supported. Variable-ratio objectives, macro F1, ratio differences and
  arbitrary nonlinear encodings refuse MILP and can use finite/bounded search.
- Bounded adjacent-choice beam search reports best found and explicit termination.
  Incomplete outer routing coverage cannot inherit an inner solver certificate.
- Cell options may reuse fixed subgraphs but cannot enter another parameterized
  cell. Encoded and replayed objectives must agree independently of selection tie
  tolerance before certificate transfer.
- `routing_parameters` on a finite `composition` family identifies outer routing
  choices. Backend `hybrid` (or `auto`) enumerates them and solves admitted inner
  residual-cell MILPs using shared limits. Global standing requires complete outer
  and inner coverage; other graph structures use finite/bounded search or refuse.
- MILP structural/canonical tie refinement enumerates the tied one-hot space under
  the same budgets. Incomplete refinement explicitly qualifies nomination standing.
  Analytical nomination state is separate from displayed candidate detail; bounded
  display retention cannot change weighted or tolerance-based selection.
- For cross-family nomination, MILP/hybrid branches stream the complete potentially
  eligible first-objective envelope into bounded analytical retention, leaving later
  lexicographic priorities unrestricted. Relative tolerances above one require bounded
  whole-family enumeration. Incomplete refinement cannot claim complete nomination.
- A single weighted RMSE transforms its signed weighted tolerance endpoints into
  signed weighted MSE units. Nonlinear mixed RMSE sums refuse this MILP encoding.
- Complete hybrid priority optimization does not establish a complete Pareto frontier;
  its frontier is reported as sampled.
- Pareto MILP uses recorded epsilon-constraint schedules and reports sampled
  nondominated trade-offs. Retained detail omissions are distinct from search
  coverage; low conditional risk does not conceal coverage/workload.

The initial optional MILP profile is SciPy 1.18.1 / bundled HiGHS 1.12.0, single
thread, Boolean `parallel=False`, seed zero, presolve, zero target gaps, 1e-9
feasibility tolerances and 1e-12 small-matrix threshold. Only the expected fixed-key
forwarding warning is admitted. Other warnings, unregistered versions, unsafe
scaling or nonintegral decoding refuse standing. Returned policies are replayed
and checked against original constraints. Optimality concerns the encoded finite
model within recorded floating-point tolerances, not exact arithmetic. Time-limited
incumbents need not repeat identically across machines.

Counters separately bound predicate/event evaluations, action inputs, contribution
cells, expanded states, retained scalar records, dominance pairs and solver matrix,
call, node and elapsed-time allocations. Structural limits are 128 nodes, depth 8
and 16 rules. Defaults include 4,096 finite evaluations, one million scalar cuts,
32 fixed cells, 256 options/cell, 8,192 solver variables/rows, one million nonzeros,
64 solves, 100,000 nodes and 300 aggregate solver seconds. Allocations are bounded
by min(1 GiB, RSS/4). Existing row/class/source/probability limits and sampled worker
RSS, deadline, disk and result-byte controls remain authoritative. No event by
candidate by class tensor is built. Sampled supervision is not a hard real-time
or platform capacity guarantee.

## Independent assessment

Select on S; frozen CG2 F/S/C and CG4 development/exposed evidence cannot become E.
Backends receive admitted S-only frames/statistics, without a database or E accessor.
An E-byte mutation can alter input/assessment identity but cannot adapt selection.
Whole entities stay within roles; complete batches additionally stay whole.

Nominate one policy by default. Freeze exact policies, every required feasibility
constraint, comparators, scopes, practical thresholds, observation rules, sampling,
true contribution bounds, error allocation and scheduled looks before E disclosure.
Omitting a required constraint prevents independent feasibility. Imported missing
membership/provenance remains unknown despite scoped independence declarations.

`preview_policy_assessment` reads only a completed S result and caller-supplied E
size. It shows conditional-support scenarios, multiplicity, illustrative exact
binomial intervals and Hoeffding precision. Optional requested half-widths yield
conditional sample-size calculations. Selection optimism, dependence and shift
can invalidate projections. A preview spends no alpha and predicts no probability
of passing. It can be bound into the frozen family and canonical assessment record.

Default family confidence is 95%, equally allocated by Bonferroni; positive frozen
weights can sum to at most one. Components and refused claims retain their original
allocation. Registered methods are CP Bernoulli intervals, Hoeffding bounded means
and paired additive differences on structurally shared bases, plus conservative
component composition for conditional contrasts, F1, fixed-class summaries, roots,
absolute bias, envelope ratios and worst-window summaries. Observed extrema do not
supply true bounds. Bernoulli inference is selected from registered contribution
semantics, never from an observed zero/one sample. Regression selective risk uses
true-bound Hoeffding inference unless its registered loss is a Bernoulli material-error
indicator. Bounds violations refuse the affected claim. Repeated entities
are checked before label filtering; general unequal-cluster, temporal/common-shock,
unbounded and unsupported nonadditive claims remain descriptive/refused.

Upper constraints are supported when the simultaneous upper bound meets the bound;
lower constraints reverse the rule. Material improvement requires a lower improvement
bound strictly beyond the frozen threshold. Other states distinguish contradicted,
inconclusive, insufficient support/provenance, unsupported design and unavailable
outputs. Different populations retain their qualifications; there is no unrestricted
feasibility seal, causal value, fairness or future-performance guarantee.

Reservations reuse the existing evidence-use ledger and source/canonical aliases.
Saving and tracking consent are separate. Cancelled/failed/deleted/restored analyses
never regain freshness. Standalone runs retain process checks with narrower continuity.
Scheduled outcome looks require a frozen historical study schedule, retained initial
reservation, unchanged prediction/feature/population snapshots and uninterrupted
branch continuity. They spend their preallocated alpha rather than fresh tests.

## Python, CLI and local browser

```python
from confidenceguard import (
    PolicyStudySpec, optimize_policies, inspect_policy_study,
    preview_policy_assessment, freeze_policy_family, assess_policies,
)

study = PolicyStudySpec.from_dict(study_dictionary, base_directory=spec_directory)
inspection = inspect_policy_study(study, config)
selection = optimize_policies(study, config,
                              expected_fingerprint=inspection['fingerprint'])
preview = preview_policy_assessment(selection, assessment_dictionary,
                                    planned_e_size=planned_count)
family = freeze_policy_family(selection, assessment=assessment_dictionary,
                              assessment_preview=preview)
assessment = assess_policies(family, config)
```

Also use `replay_policy`, `inspect_policy_assessment`, `analyze_policy_history`,
`export_frozen_policy`, `inspect_policy_restatement` and `restate_policy_assessment`.
Workspace facade methods retain/reopen families and results using existing catalog
facts and bounded packets, with backup/restore and transitive dependencies.
Outcome-only restatement keeps the original policy and prediction/feature snapshots.
History uses CG3 as-of authority/maturity/revision reconstruction, per-window action
metrics, applicability, compatible mix/drift reducers and supplied-action disagreement.
Historical replay is retrospective; reselection is a separate development study.

`PolicyApplicationSpec.constraints` retains typed replay requirements. Historical
replay intersects each metric's original cohort/region scope with each window and
records feasible, violated and undefined constraint states, support floors, slacks
and worst-window descriptive evidence. The same declarations survive immutable
reopening and outcome-only restatement. API sections `constraint-ledger` and
`worst-windows` paginate those completed records.

Inspection's `backend_admission` uses S-only domains and the execution encoder's
structural, denominator, matrix and scaling checks without running a solver.
Bounded composition and limited outer preflight are explicitly partial guidance.
All analytical execution binds the internally reserved source fingerprint,
including supplied vector/key dependencies, even without earlier caller inspection.

`confidenceguard policy` provides `inspect`, `optimize`, `replay`,
`preview-assessment`, `freeze`, `inspect-assessment`, `assess`, `history`, `open`,
`export`, `evidence`, `restate-history`, `inspect-look` and `assess-look`. Use `--spec`, optional `--config`, explicit output/audience
options and specification-relative source paths. `export --policy-digest ...
--audience local --manifest ...` is a separate protected executable export.

The existing `/api/confidenceguard/v1` exposes revisioned `/policy-studies`, owned
policy/family import/content handles, fixed policy jobs, and paginated completed
candidates, constraints, trade-offs and assessments. Existing CSRF, revisions,
fingerprints, idempotency, worker locking, cancellation and workspace grants apply.
Browser requests never choose workspace, scratch or output paths or solver options.

Open **Decision policies** in the local workbench. Use current evaluation evidence,
compose task-specific actions/economics/constraints, inspect, optimize, review the
nomination, preview, freeze and assess. Complete-spec editing supports advanced
routing, CG4 dependencies and immutable historical selections. Browser code only
authors declarations and renders backend evidence. It performs no analytics.

## Privacy and records

One sealed result and audience projection drive JSON, canonical HTML/SVG and derived
PDF. Protected local records include behavior, economics, input dependencies,
search/certificate scope, feasibility/slacks, nomination and independent claims.
Shareable projections omit executable definitions/cutoffs, cost tables, cohort
values, memberships, paths, identifiers, vectors/examples and arbitrary free text.
Related ranking, dominance and nomination evidence is withheld jointly when needed.
Private economic declarations conservatively withhold the related comparisons together,
including derived feasibility and nomination. Utility decisions can use negative costs
in the complete decision table; evaluation utility remains a separately identified metric.
Exact aggregate disclosure does not export a policy. Shareable exports create no
protected policy bundle; portable imports cannot regain private evidence.

Public claims retain controlled metric/evidence-basis fields, aliases, requirements
and eligible support when their question can be identified safely. Protected
scoped/economic/output-specific claims withhold the conclusion and interval
together. Hidden claims retain their frozen error allocation. Canonical assessment
tables show the question, scope, support, interval and allocation.

Reopening, filtering and exporting completed records never re-fit, optimize, replay
or assess. PDF failure retains correctly owned valid HTML/JSON. Artifact checksums
bind content and dependencies; they do not authenticate an outside producer.

See [verification results and scope](../validation/cg5/VERIFICATION.md). Measurements
and passing checks apply only to their recorded environment, source and workload.

Public claim tables retain defining regression loss, pinball level, units and material
threshold. Controlled generic units are shareable; custom unit text needs an explicit
`DisclosureSpec.display_labels["units:" + original_unit]` public label. Otherwise the
claim conclusion and interval are withheld together, preserving the original alpha.
