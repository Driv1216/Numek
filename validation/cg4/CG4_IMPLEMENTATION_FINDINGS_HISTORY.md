# CG4 implementation findings

**Status: implementation and qualification in progress.** This is an engineering
record for independent review, not a declaration that CG4, independent review or
founder acceptance is complete. Earlier failed experiments remain evidence; they
are not silently replaced by corrected or more favorable runs. Verification is
reused only within its recorded scope. Counts below describe specific panels,
not one combined independent experiment.
The [qualification matrix](QUALIFICATION_MATRIX.md) distinguishes current source
checks, prior-profile evidence, fresh campaigns and outstanding method requirements.

**Review delivery inputs could change after validation — packaging defect.**
Two deliberate synthetic changes reproduced that the earlier builder could
publish a wheel or backup changed after its initial check: it compared the copy
with the changed source instead of the original checked hash. Delivery inputs now
retain their original byte/hash records through capture, and direct symlink/FIFO
inputs refuse before parsing or hashing. Both original-source mutation probes
failed as expected before correction; all 16 focused packaging checks passed
afterward. No customer archive or final CG4 review ZIP was published. The runtime
and numerical methods were unchanged, so their completed verification was reused.
Evidence: [retained pre-correction probes](results/verification/review-delivery-capture-before-v47.txt),
[capture checks](../../tests/cg4/test_review_package.py),
[corrected builder](package_review.py),
[verification inventory](results/verification/review-delivery-capture-v47-manifest.json).

## Statistical methods

**Confirmation inspection understated numerical work — admission bug.** Three
direct failures showed that CG4 omitted the registered ranking-setup cost and
counted separate absolute-effect bootstrap calls as one joint call. In the one-claim
two-component fixture, it reported 16,002,400 instead of 32,004,800 work units.
Inspection now counts all planned calls and the same ranking setup term as the
numerical kernel. Memory remains a labeled estimate; sequential component buffers
are not summed. A public ranking journey confirms that an insufficient budget
refuses before H metrics. Fifteen focused admission/confirmation/discovery checks
and 20 retry/restatement/report/interface checks passed; seven affected checks passed
each on Python 3.12/3.14. Only `feasibility` changed in runtime code, leaving draws,
interval mathematics and failed-method restrictions unchanged. No method was enabled
by this correction. Evidence: [tests](../../tests/cg4/test_confirmation_work_admission.py),
[failure, source and correction inventory](results/verification/work-admission-v106-manifest.json).

**General cluster failure required a narrower explicit design — methodological
adjustment, not a bootstrap repair.** The failed BCa profiles below remain disabled.
A separately frozen `independent_entity_arms` finite design now requires IID complete
entities and at most one potential observation per comparison arm. Outcome-independent
checks reject duplicates before label/class filtering; marginal CP/Hoeffding and
existing composition are unchanged. Nine product checks cover native references,
selective-label duplicates, mixed families and historical replay. The 271-test CG4
closure passed; affected Python 3.12/3.14 checks also passed. In 30,000 locked null
and 2,000 power trials no predeclared excess-error diagnostic rejected; all strong
gate-zero effects confirmed, and 136 scalar references agreed to 9.992e-16.
This does not resolve arbitrary clusters, unbounded means or dependence declarations.
Common-shock and duplicated-row controls intentionally bypassed admission and had
94/200 and 40/200 false-confirmation families. The all-gate power audit also retains
poor near-threshold power: effect .1875 against delta .15 confirmed only 36/2,000.
Before the full run, a tiny shape test's seed overlap was noticed and the full
power panel was assigned untouched seeds; the original development files and
receipt remain. No acceptance target changed. A mixed-family test initially expected
effect 1 although its comparator retained other failures; correcting its independent
reference to 2/3 changed no product code. The browser used known-exposed evidence and
correctly refused inference; HTML/JSON/PDF preserved refusal and private withholding.
Evidence: [design and assumptions](ENTITY_ARM_FINITE.md),
[locked statistical evidence](results/finite-entity-arm-qualification-v93/summary.json),
[negative/power detail](results/verification/finite-entity-arm-power-detail-v95.json),
[prelock development provenance](results/verification/entity-arm-development-prelock-v92/receipt.json),
[product tests](../../tests/cg4/test_entity_arm_confirmation.py),
[source, installation and browser/report verification](results/verification/entity-arm-v97-manifest.json).

**Paired precision erased decision-set differences — CG4 metric/proxy bug.**
The common population incorrectly intersected both models' predicted-positive
conditions. Both precisions then used the same observations, while the pointwise
diagnostic difference was identically zero. A direct D-only fixture reproduced
reported precision 1 versus the correct .5 (reference 1), with 120 instead of
240 proxy-eligible rows. Pairing now uses common issued predictions, then each
model's own predicted-positive denominator. D-only ratio influence targets can
propose regions where the positive sets differ; native reducers still calculate
subgroup precision, and finite intervals use separately allocated Bernoulli
components. New objective identity v2 distinguishes these population semantics.
Old records remain readable; legacy paired-precision gates cannot silently freeze,
confirm or replay under the corrected interpretation. Six direct/integration tests
cover binary/multiclass, missing reference decisions, exact supports, interval
composition and a clearly constructed legacy specimen; eight combined correction
checks passed on Python 3.12/3.14. Broader closure and corrected-objective recovery
qualification remain required. Existing single-model precision and paired-error
campaigns do not qualify this new proxy. Evidence:
[original failures](results/verification/numek-cg4-paired-precision-before-v48.txt),
[independent fixture/references](../../tests/cg4/test_paired_precision.py),
[metric/target correction](../../src/confidenceguard/investigation_objectives.py),
[verification inventory](results/verification/paired-precision-v48-manifest.json).

**Frozen observation interpretation could drift — admission defect.** A synthetic
D/S-only probe showed that explicit confirmation input could reclassify pending
labels as final or change the feature-time view after freezing. No H metrics or
inference were computed by the probe. Shared canonical policy binding now rejects
label/status/key/clock, historical authority/maturity/context and feature-time
changes before an H worker. New hypotheses use definition v2; actual H source/
snapshot identities remain separately inspected and bound. An actual old browser
family remains readable and byte-identical. Fourteen focused checks, 49 caller/API/
retry/exposure checks (12 overlap), and 15 focused checks each on Python 3.12/3.14
passed, including predeclared restatements. The first cross-runtime comprehensive
attempt was deliberately interrupted for this correction and is not a full pass.
Evidence: [original probe](results/frozen-observation-policy-before-correction-v1.json),
[legacy artifact reuse](results/legacy-frozen-observation-policy-read-v1.json),
[portable correction tests](../../tests/cg4/test_frozen_observation_policy.py),
[sources and verification](results/verification/frozen-observation-policy-v40-manifest.json).

**Joint BCa undercoverage — genuine method failure.** In seven locked 1,000-trial
panels, the implemented joint contrast failed excess-noncoverage diagnostics for
heavy-lognormal observations (112 noncoverages among 984 available intervals;
16 refusals) and unequal complete clusters (72/1,000). Holm-adjusted diagnostics
rejected both. Every input passed the existing outer effective-support admission;
these were not accidentally included low-support cases. Twelve independent SciPy
BCa references matched the numerical kernel (maximum difference about 3.6e-15).
The generic joint-BCa profile is therefore refused for formal CG4 confirmation
before H outcome access; its kernel and historical results remain reproducible.
A distinct component-BCa candidate completed 5,000 fresh trials without a rejected
excess-error diagnostic, but refused 468/1,000 heavy-tail and 6/1,000 cluster cases.
It is not enabled or generally qualified. Extreme tails and the remaining
operating envelope are unresolved. Evidence: [joint summary](results/approximate-panel-summary-v1.json),
[support audit](results/approximate-outer-admission-audit-v1.json),
[SciPy reference](results/BCa-SciPy-reference-v1.json),
[component candidate](results/approx-component-qualification-v1/summary.json),
[refusal test](../../tests/cg4/test_confirmation.py).

**Unsupported inference was rejected too late — admission/disclosure defect.**
Focused tests found that inspection admitted finite inference for an entity design,
finite ranking, and unbounded log loss, although the assessment code had no
registered interval for them. Its late refusal followed native H metric evaluation
and disclosure. Method registration is now checked from frozen objective/sampling
semantics during inspection, before H evaluation. Nonadditive native metrics also
refuse there even if their pointwise proposal loss has declared bounds. The family
is retained; registered F1 composition and bounded means remain admitted. Observed
bound violations, conditional support and numerical degeneracy still require
reserved H access. This fixes refusal timing, not the unresolved approximate-mean
coverage problem. Evidence: [tests](../../tests/cg4/test_confirmation_method_admission.py),
[failure/correction and source scope](results/verification/admission-r2-v77-manifest.json).

**R2 proposal direction missed an obvious failure — implementation bug.**
A synthetic regression check produced no shortlisted R2 region despite a native
R2 contrast of −3 versus 1. The shared lower-is-worse head negated an already
adverse squared-error proxy, favoring good predictions. The versioned
`negative_squared_residual_for_r2_v2` target aligns the proxy with native R2 before
shared head/paired/historical transformations. Independent arithmetic checks the
unchanged R2 reducer; the corrected structured search recovers the adverse region.
Only the proposal target/identity changed; historical bytes and native metrics did
not. The residual proxy cannot guarantee R2 recovery when subgroup target variance
changes. These are correctness checks, not a new 40-seed R2 qualification or a
native R2 interval. Evidence: [target/native tests](../../tests/cg4/test_r2_proposal_target.py),
[failed tests and correction evidence](results/verification/admission-r2-v77-manifest.json).
The later [D-only variance counterexample](results/r2-variance-counterexample-v105/summary.json)
records native subgroup R2 -99.0017 versus background .95998, while squared errors
are 1 versus 4. Shared reducers and independent arithmetic agree. This is a genuine
limitation of ordering regions by that proxy; no learner was fitted in this audit,
so it is not a measured recovery failure. The equal-variance recovery protocol uses
new seeds 480000–480039 and remains unrun. Seven affected checks pass each on
Python 3.12/3.14, including generator/reference checks; they are not qualification.

**Extended uncertainty discovery could not read its filtered relation — execution
bug.** A supplied-interval coverage test failed during discovery, before its
intended future-H-only confirmation check. The H-excluding relation was a DuckDB
connection-local temporary table, but the shared streaming reader opens a separate
cursor/connection. The relation is now a regular table inside the same disposable,
protected job database. A direct check verifies exactly 240 D and 240 S loss rows
and no H rows. Registration also shares a pure frozen contribution contract with
the uncertainty adapter, so H-only inspection needs neither D/S losses nor H
outcome reduction. The complete H-only finite assessment passes. Accepted CG2
reducers, uncertainty formulas and durable workspace codecs are unchanged.
The intermediate broad verification run was explicitly stopped while this
coherent correction was completed; it is not recorded as a suite pass.
Evidence: [sealed-loss/future-H tests](../../tests/cg4/test_confirmation_method_admission.py),
[failure and correction receipt](results/verification/admission-r2-v77-manifest.json).

**Component-BCa power does not resolve coverage — genuine candidate limitation.**
The locked 3,000-trial power panel met its unchanged power/availability criteria:
1,000/1,000 normal, 998/1,000 exponential and 888/1,000 unequal-cluster confirmations
for true effect +1, delta .15 and 200 independent units. Refusals remain in the
denominator. However, a post-hoc audit of the earlier 5,000 retained trials found
heavy-lognormal component-mean noncoverage of 66/723 and 73/735 available intervals
at nominal 97.5% confidence; unequal-cluster components also showed excess error.
Good same-law contrast results cannot qualify those component means, ceilings or
asymmetric-arm claims. This audit is exploratory, not a newly locked qualification.
The method remains disabled. A separate studentized-bootstrap prototype also
failed its later locked panel, as recorded below; algebra/parity tests do not
establish coverage or activate it.
Evidence: [power protocol/harness](qualify_component_power.py),
[development results](results/component-power-development-v1/summary.json),
[locked qualification binding](results/component-power-qualification-v1.source-capsule.json),
[completed power panel](results/component-power-qualification-summary-v2.json),
[component-mean audit](results/component-mean-coverage-audit-v1.json),
[prototype](studentized_candidate.py),
[prototype algebra tests](../../tests/cg4/test_studentized_candidate.py),
[input/estimand tests](../../tests/cg4/test_qualification_inputs.py).

**Bootstrap-t did not repair heavy-skew coverage — genuine candidate failure.**
The separate analytic-influence studentized prototype completed 10,000 locked
trials, with all intervals available. At nominal 95% confidence, noncoverage was
107/1,000 for same-law lognormal contrasts, 86/1,000 and 89/1,000 for asymmetric
heavy/light arms, and 74/1,000 for lognormal mean ceilings. Total and relevant
directional-error diagnostics rejected after the predeclared Holm correction.
Independent expanded-resample covariance/parity tests passed, supporting a method
limitation at this 200-unit envelope rather than an identified arithmetic bug.
The 20,000 draws supplied 500 expected observations per nominal tail; increasing
replication is not a demonstrated repair for these sampling-coverage failures.
The prototype remains validation-only; no automatic replacement was enabled and
no screening threshold was weakened. Proper approximate mean confirmation remains
unresolved. Evidence: [locked panel](results/studentized-qualification-v1/summary.json),
[all trial identities/hashes](results/studentized-qualification-integrity-v1.json),
[algebra tests](../../tests/cg4/test_studentized_candidate.py),
[diagnostic denominator tests](../../tests/cg4/test_studentized_panel.py).

**Variance-bound alternative adds an assumption, not a silent repair.** Following
the retained bootstrap failures, a validation-only fixed-time Catoni-score
prototype was introduced. It requires a justified population variance bound for
each unconditional complete-unit contribution, including membership zeroes and
entity-size variation. It cannot estimate that bound from H or reuse an old
frozen method identity. Eight independent numerical/composition checks and three
sampling/diagnostic-contract checks passed. Its locked 10,000-trial conditional
screen completed with all intervals available, two noncoverages and no rejected
excess-error diagnostic. Heavy-lognormal contrast median widths were approximately
10.55–14.01 across family allocations: useful power is not established. Deliberate
assumption violations caused 200/200 noncoverages with understated heavy-tail
variance and 185/200 with a shared unmodelled shock. These are outside its
guarantee and show why caller declarations cannot be treated as verified facts.
Full qualification and useful power remain unestablished; the prototype is not
registered in the product. Evidence:
[assumptions and proof boundary](MOMENT_CANDIDATE.md),
[prototype](moment_candidate.py), [locked protocol](qualify_moment.py),
[independent references](../../tests/cg4/test_moment_candidate.py),
[panel contracts](../../tests/cg4/test_moment_panel.py),
[conditional screen](results/moment-qualification-v1/summary.json),
[assumption-violation controls](results/moment-negative-v1/summary.json),
[verified trial identities/hashes](results/moment-candidate-integrity-v1.json).

**Completed power summary could not serialize — qualification-harness bug.**
After all 3,000 trial files were written, a NumPy Boolean in the completed-panel
acceptance summary caused JSON serialization to fail. Only aggregate scalar types
were corrected. A separate aggregator verifies the original simulation functions,
protocol, runtimes, seeds and all trial hashes before reusing the completed rows.
No simulation or acceptance target changed. Positive and refused-summary branches
now have focused serialization checks. Evidence:
[retained failure](results/verification/component-power-summary-failure-v1.txt),
[verified aggregation](aggregate_component_power.py),
[focused verification manifest](results/verification/statistical-candidate-schema-report-v9-manifest.json).

**Bootstrap budget infeasibility — design correction.** A universal B=20,000 cannot
support the adopted 20-observation tail-resolution rule for 32 hypotheses: one,
two and four elementary two-sided intervals require nominal B of 25,600, 51,200
and 102,400. Admission now accounts for family/components and caller work/memory/
deadline caps. BCa-adjusted tails still require a second check after reserved H
access. No family reduction, replicate discarding or weaker-method substitution
is permitted. This is numerical feasibility, not a bootstrap coverage guarantee.
Evidence: [confirmation code](../../src/confidenceguard/confirmation.py),
[arithmetic and refusal tests](../../tests/cg4/test_discovery.py),
[numerical retry tests](../../tests/cg4/test_numerical_retry.py).

**Temporal dependence remains unsupported for confirmation.** CG3's retained
moving-block undercoverage finding is not repaired by renaming its procedure.
CG4 excludes that method and refuses unsupported serial/common-shock designs.
Whole-entity resampling requires independent complete entities. A separate stationary
Markov negative control deliberately applied the IID interval to 200 correlated
observations: noncoverage was 4,874/10,000 at persistence .8 and 7,878/10,000 at .95,
versus 326/10,000 in its IID control. Marginal failure probability stayed .1.
The corresponding product check refused declared temporal, common-shock and
descriptive designs before H metrics. This is evidence against misuse, not a
failure of the IID theorem or qualification of a temporal remedy. Evidence:
[negative control](results/temporal-IID-negative-v1.json),
[fixed protocol/generator](qualify_temporal_negative.py),
[refusal reference](../../tests/cg4/test_confirmation.py),
[CG3 negative finding](../cg3/DECISIONS.md), [CG4 confirmation tests](../../tests/cg4/test_confirmation.py).

## Benchmark and discovery findings

**Qualification continuation defects — benchmark control, not analytical failures.**
A partial-null launcher watched `131999.json`, while the completed dependency was
named `reduced_full_pipeline_null-interaction_without_marginals-131999.json`.
It remained idle; no experiments were altered. The completed dependency was
verified and the original source-bound campaign started directly. Separately,
adding a benchmark name to the runner allowlist caused the objective controller's
whole-file hash check to reject resumption. A separate record now verifies that
the executable AST is unchanged apart from an additive fixed allowlist, preserving
original group metadata, source/runtime, seeds and budgets. Code review also found
three archived harnesses would skip a saved failed row if its profile matched.
New harnesses require completed status and matching trial identity; legacy
objective resumption preflights saved rows. Three injected worker-failure references
and one allowlist/control-change reference passed. Existing audited panels contained
only completed rows, so their numerical evidence was reused. Evidence:
[original dependency helper](results/verification/numek-cg4-partial-null-after-reduced-v1.py),
[control resumption](resume_objective_campaign.py),
[control reference](../../tests/cg4/test_campaign_resumption.py),
[saved-failure references](../../tests/cg4/test_failed_campaign_reuse.py).

**Reduced null campaign retained a false finding.** One of 2,000 independently
generated investigation families falsely confirmed a zero-effect hypothesis
(seed 130828). All 6,282 hypotheses, including inconclusive claims, remain recorded;
the source/allocation/finding-state audit passed. The family-error Monte Carlo
95% interval is .00001266–.00278264. This is not evidence of an implementation
failure or zero error: the finite procedures allow a declared error probability.
The separate 200 default-size runs subsequently had no false-confirmation families
(Monte Carlo 95% interval [0, .01828]); 111 of their 2,000 claims were inadmissible,
not successful interval coverage. Neither fixed Holm excess-error diagnostic
rejected; this does not prove nominal control, and the two panels are not pooled.
Evidence:
[complete reduced panel audit](results/null-reduced-summary-v1.json),
[default-size audit](results/null-default-summary-v1.json),
[joint diagnostic](results/null-complete-joint-summary-v1.json),
[allocation/state references](../../tests/cg4/test_null_summary.py).

**Fixed-bin calibration recovery did not yield useful confirmation power.** The
unchanged 40-seed panel met the recovery anchor in all trials (median H precision
.99761, recall .98882). Nevertheless, all 184 selected, overlapping calibration
hypotheses were inconclusive under their finite simultaneous component intervals.
Recorded native effects ranged from -.04329 to .33846. This is a power limitation
of this allocation/support/metric envelope, not evidence that recovery failed or
that the conservative bounds are arithmetically wrong. No weaker procedure,
confidence level or reduced family was substituted. Evidence:
[complete calibration panel](results/objective-calibration-bins-summary-v1.json),
[authoritative metric adapters](../../src/confidenceguard/investigation_objectives.py),
[finite composition](../../src/confidenceguard/confirmation.py).

**Simpler baselines sometimes beat the first native gate — development limitation.**
In small categorical development, the first S-selected native gate had H IoU
.075, versus .67308 for a depth-two rule; the native full shortlist also reached
.67308. Selection of a narrow severe gate and recovery of the whole affected
population are different questions. The comparison therefore preserves a matched
one-gate primary result and labels the full shortlist separately. It does not
substitute the favorable union or tune selection using H. Four small workflows
and one 40,000-row curved development completed; the latter native first-gate IoU
was .64957, full-union .84694. Three geometry/protocol/exact-binomial references
and a native S-evidence parity workflow passed. These are development evidence,
not 40-seed superiority, general stability or controlled relative efficiency.
The new four-family comparison uses untouched 180000–180039 seeds and predeclared
multiplicity-adjusted paired-median intervals. Evidence:
[comparison protocol/harness](compare_baselines.py),
[independent boundaries](../../tests/cg4/test_baseline_comparison.py),
[small categorical result](results/baseline-categorical_numeric_conjunction-development-v1/1.json),
[full-size curved development](results/baseline-curved-development-full-v1/2.json),
[S parity workflow](results/baseline-S-parity-development-v2/3.json),
[locked comparison identity](results/baseline-qualification-source-v1.json).

**Invalid generated numeric covariates — benchmark bug.** NumPy scalar `repr`
emitted text such as `np.float64(...)` into CSV coordinates. The product correctly
classified it as invalid; the intended numeric search experiment was wrong.
The generator now writes scalar-float lexical values, checked against its vector
matrix. Affected interaction/objective/null runs remain invalid-covariate evidence
and do not count as the intended qualification. Earlier false-negative recovery
shortcomings cannot establish an algorithmic failure under those inputs. Protocol
v2 keeps the acceptance targets and uses untouched seeds. The valid-vector curved
panel, which excluded those tabular columns, and direct inference/storage panels
are unaffected. Evidence: [archived defective harness](results/pipeline-harness-numpy-repr-defect-v1.zip),
[locked correction](qualification_protocol_v2.json), [input tests](../../tests/cg4/test_qualification_inputs.py).

**First-gate coverage can be worse than a simpler baseline — qualification finding.**
The first completed matched comparison retained all 40 interaction seed pairs.
Native one-gate median H precision was 1 and recall .135 (IoU .135), versus .499
precision/.988 recall for low-order rules (IoU .493). Native-minus-rule median
paired IoU was -.248, with the predeclared 20-contrast interval [-.422,-.023]. Native
full-shortlist union median IoU .998 is a different, secondary result and cannot
replace that comparison. This is a coverage/selection trade-off in the fixed method,
not an identified metric or membership bug. The one-gate native result beat error-
blind clusters and simple balls on this panel; it did not demonstrate an advantage
over the single diagnostic learner. The completed categorical comparison likewise
found native one-gate median IoU .21440 versus .99451 for a shallow tree and .76713
for low-order rules; both allocated paired-difference intervals were negative.
Its native full-shortlist median .98401 remains secondary. Conversely, curved
and density panels favored the native first gate against all five baselines, with
all allocated paired-median lower bounds positive. These are scoped complementary
findings, not universal superiority or controlled timing comparisons. No selector or
acceptance criterion was changed after inspecting H. Evidence:
[fixed family audit](results/baseline-interaction-summary-v1.json),
[categorical comparison](results/baseline-categorical-summary-v1.json),
[curved comparison](results/baseline-curved-summary-v1.json),
[density comparison](results/baseline-density-summary-v1.json),
[protocol and source](compare_baselines.py),
[verification inventory](results/verification/baseline-interaction-complete-v35-manifest.json).

**Approximate explanations and stability can remain weak despite recovery.**
Across the 40 rare-failure trials, 134 selected CatBoost gate occurrences had
median D-perturbation IoU .48606 and held-out surrogate precision .41187/recall
.97255. Across 40 overlapping-region trials, 241 geometric gates had median IoU
.46862 and H surrogate precision .07964/recall .51548. These are gate-occurrence
summaries conditional on S selection; overlapping gates are not independent
replicates. Exact gate application is reproducible, but the simple explanations
are often poor substitutes. Applicability and missing support remain explicit;
the explanation does not define membership. No universal fidelity label or new
acceptance threshold was introduced. Evidence:
[rare diagnostics](results/recovery-rare-diagnostics-v1.json),
[overlapping diagnostics](results/recovery-overlapping-diagnostics-v1.json),
[count/reference audit](summarize_gate_diagnostics.py).

**Recovery shortcomings remain visible — scope-specific method evidence.** Early
development curved trials missed the precision/recall target. After the recorded
selection refinements, a separately locked valid-vector curved anchor achieved
40/40 successes; this qualifies that anchor only. It does not establish landmark
superiority or qualify every objective. The AG News realistic injected journey
also fell short (H precision .218, recall .488, adverse error contrast .057 versus
delta .15). CIFAR-10 was also weak: precision .176, recall .154, contrast .016.
These are representation/injected-region limitations, not demonstrated encoder
execution bugs. Public-data provenance did not support formal confirmation. Natural
and injected journeys are kept separate; benchmark predictor preparation is not
a product execution API. Evidence: [curved summary](results/recovery-curved-summary-v1.json),
[AG News journey](results/realistic-ag-news-v4.json), [CIFAR journey](results/realistic-cifar10-v4.json).
Other required archetypes, objectives and baselines remain open; the later landmark
promotion failure is recorded below.
The corrected interaction-without-marginals panel later completed 40/40 successes
at the same locked thresholds; median H precision .99934, recall .99968. Its
[complete source-checked summary](results/recovery-interaction-summary-v1.json)
qualifies that anchor only, not every strategy or objective.
The heterogeneous-density anchor also completed 40/40 recovery successes (median
H precision .87415, recall .97660). Its 654 unavailable H observations across
the panel remain in planned-population accounting; none was an oracle failure
member. Recovery success does not override a refused full-population confirmation
claim. Evidence: [density summary](results/recovery-density-summary-v1.json).
The parity panel completed 39/40 successes (one seed's H recall .6927 missed the
.70 criterion); high-dimensional nuisance recovery completed 40/40. Both retain
their original source/seed/profile identities and qualify only their declared
archetype. Evidence: [parity summary](results/recovery-parity-summary-v1.json),
[high-dimensional summary](results/recovery-high-dim-summary-v1.json).

**Landmark development under-recovery — original-method shortcoming.** A full
40,000-unit curved-region development case recovered H precision .885 but recall
.377 (IoU .359). This is a development finding, not a completed qualification
failure or an implementation bug established by numerical references. The original
method remains experimental. A separate matched fallback/landmark panel retains
the .10 median-gain criterion, fresh-process membership and independent H scoring.
Its predeclared negative stopping rule applies only when even ideal remaining
paired gains cannot meet that same finite-panel criterion; stopped panels cannot
claim complete uncertainty or resource qualification. The locked comparison
subsequently rejected promotion after 21 curved-region pairs: observed median H
IoU gain was -.24853; the maximum possible final 40-pair median was -.16329,
below the unchanged +.10 requirement. All 42 trial hashes, matched input/budget/
runtime identities and the mathematical stopping bound were checked. This is a
method-profile failure; its algorithmic cause is unresolved, and no implementation
bug or universal inferiority is established. Promotion remains rejected, the
fallback stays selected, and API/report/browser method standing now records this
negative evidence. The 21 fallback trials are reused as a deterministic prefix;
only the remaining 19 original seeds run for its separate recovery panel. Evidence:
[development trial](results/landmark-curved-development-full-v1/development-curved_region-0.json),
[locked comparison](qualify_landmark_comparison.py),
[stopping/allocation tests](../../tests/cg4/test_landmark_comparison.py),
[negative summary](results/landmark-matched-comparison-v1/summary.json),
[identity/stopping audit](results/landmark-negative-integrity-v1.json),
[fallback reuse plan](results/geometric-curved-reuse-plan-v1.json),
[product-standing reference](../../tests/cg4/test_qualification_status.py).

**Runtime provenance overwrote admitted-budget metadata — harness defect.** The
pipeline trial used `profile` for limits, then its wrapper replaced that field
with source/runtime provenance. New trials retain `admitted_limits` and
`admitted_config` separately, and matched comparisons check both. Earlier fixed
budgets can be reconstructed from their immutable source, panel and flags, but
are not mislabeled as retained per-trial budget observations. Recovery/statistical
values are unaffected; those expensive trials were not repeated for metadata.
Evidence: [corrected harness](qualify_pipeline.py),
[original captured source binding](results/recovery-interaction-capsule-v3.source-capsule.json).

**Expensive repeated predicates and incorrect quantile vocabulary — implementation
defects/design adjustments.** A development profile attributed about 184 seconds
to repeated explanation predicates. Bounded operation-local mask caching reduced
that measured component to about 24 seconds under different concurrent load;
this is not a controlled speedup claim. Cached/uncached proposals and legacy
ternary membership were checked independently. Numeric cuts also incorrectly
used unique-value rather than observation-frequency quantiles. They now use exact
observation order statistics; this vocabulary correction is distinguished from
the semantics-preserving cache change. Evidence: [original profile](results/discovery-development-profile-v1.json),
[cached profile](results/discovery-development-profile-cache-v2.json),
[current parity](results/predicate-cache-parity-v2.json),
[quantile tests](../../tests/cg4/test_predicate_cache.py).

**CatBoost float and category boundaries — reproducibility risk.** Trainer scores
and JSON-reloaded scores can differ at tiny floating-point boundaries. Canonical
membership is now defined from the exported/reloaded model before thresholds are
chosen, with exact repeat-reload membership parity. Trainer-roundtrip differences
remain diagnostic evidence. Lexical category identities, missingness, unseen
categories and cross-runtime application have separate checks. This does not
establish recovery usefulness. Evidence: [parity records](results/catboost-parity-v1/),
[method tests](../../tests/cg4/test_methods.py).

## Evidence reuse, execution and disclosure

**Worker cleanup raced scratch free-space polling — execution bug.** Locked
paired-error seed 110020 stopped when a completed child removed its scratch
directory between the parent's existence check and `statvfs`. Its failure record
is preserved. A deterministic test reproduced the race. Free-space polling now
ascends to the containing filesystem on a disappearing path, without hiding
permission/I/O errors or inventing capacity. The correction changes no analytical
kernel. Two direct checks passed, followed by combined correction checks on
Python 3.12/3.14; broader M4/CG4 supervision closure is running. The original
20 completed campaign trials were copied byte-for-byte to a new continuation;
the failed seed is retried once under its same captured algorithm/profile before
the untouched remaining seeds. This is an operational retry, not fresh independent
evidence or a favorable-result replacement. Evidence:
[original failed trial](results/objective-continuous-uncertainty-group-v1/paired_degradation/paired_degradation-110020.json),
[continuation provenance](results/objective-paired-completion-v2/operational-continuation.json),
[deterministic race reference](../../tests/cg4/test_supervisor_cleanup.py),
[verification inventory](results/verification/scratch-cleanup-v49-manifest.json).

**Exposure continuity and retry identity gaps — inference-integrity defects.**
Namespace changes or source renames could evade simple event-only overlap checks;
protected source-instance aliases now survive observable renames and revisions.
The ledger checks protected chunks, counts and digests rather than trusting its
index alone. Families previously did not bind the complete numerical protocol;
schema 1.1 now binds seed, budgets and support policies as well. Numerical retries
preserve the original family and reserve one B per origin before H access, so an
old insufficient parent cannot authorize several favorable-budget searches.
Missing, deleted or restored attempt history refuses that continuation. A
historical ledger commit also advanced K between admission and execution; phases
now retain the frozen effective selection. Evidence:
[exposure tests](../../tests/cg4/test_exposure.py),
[retry tests](../../tests/cg4/test_numerical_retry.py),
[scheduled-look tests](../../tests/cg4/test_scheduled_confirmation.py),
[source-alias verification](results/verification/source-aliases.txt).
Local checks cannot observe independent forks, copied external evidence or other
investigations. Missing history never proves freshness; guarantees remain scoped.

**Stale declarations and omitted workspace bindings — provenance defects.** An old
unexposed declaration could have covered a later restored/deleted-history gap.
Declarations now bind the current continuity token, which changes on restore,
deletion and disabled tracking. The declaration remains external evidence rather
than proof of intact history, and cannot override known contamination. Historical
core APIs now infer the actual source workspace when the optional keyword is
omitted and reject redirection. Numerical retries retain the original protected
workspace and refuse changed continuity. Fifteen focused provenance/retry/schedule
tests passed; old optional-field family bytes remain readable. Evidence:
[gap tests](../../tests/cg4/test_history_gap_declarations.py),
[completed verification](results/verification/numek-cg4-history-gap-closure-v1.txt).

**Deletion left protected identifiers in process memory — privacy defect.** The
transient exposure cache previously merged uses without ownership and retained
their identifiers after durable deletion. Entries now retain workspace/use
ownership and are registered under the catalog operation lock. Tombstones release
only affected retained references; idempotent old receipts cannot repopulate deleted
memberships. Other workspaces and standalone observations remain protected.
Untracked observations have no durable locator, so deletion releases that owner's
untracked entries while retaining the history-gap qualification. Three focused
tests passed, including tombstone interruption/recovery and full purge. The first
test incorrectly expected only `incomplete` instead of also accepting `unavailable`
history; its corrected assertion accepts both refusal reasons. This is logical
reference removal, not a physical memory-wiping guarantee. The broader affected
group passed 16 tests and failed only that corrected assertion; the primary legacy
lifecycle/hash group passed 12. Python 3.12 and 3.14 each passed four focused
deletion/hash checks. These overlapping groups are not one combined campaign.
Evidence:
[deletion tests](../../tests/cg4/test_exposure_deletion.py),
[initial fixture failure](results/verification/numek-cg4-exposure-deletion-diagnosis-v1.txt),
[focused correction](results/verification/numek-cg4-exposure-deletion-correction-v2.txt),
[affected/runtime closure](results/verification/exposure-deletion-closure-v5-manifest.json).

**Exposure tracking depended on result retention — product/provenance defect.**
The supplied-vector browser journey showed an unknown ledger even though an
authorized workspace had tracking enabled: live CG4 jobs attached it only for
retained results. Resolution now binds authorized workspace exposure checks
independently of retention. The same review added reservation before live CG1/CG2
outcome assessments when tracking is enabled, without capturing their features or
changing analytical reducers. CG2 fit scans retain F/S/C separation and leave E
unexposed. Earlier unkeyed CG1 assessments use protected whole-source anchors;
later keyed H queries consult them, while keyed D/S/H reservations never store
those anchors. Shared files alone therefore do not contaminate keyed partitions.
The first focused run found another coupling: freezing tried to save hypotheses
with saving consent off. Explicit retained-state handling now prevents that write.
Four focused tests passed, including failure after reservation and access/idempotency
revocation on detachment. The affected regression group passed 24 tests, and the
four focused live-tracking checks passed on Python 3.12 and 3.14. Evidence:
[observed browser defect](results/browser-supplied-membership-inspection-before-v1.json),
[live API/role tests](../../tests/cg4/test_live_browser_exposure.py),
[initial failure](results/verification/numek-cg4-live-browser-exposure-v1.txt),
[focused correction](results/verification/numek-cg4-live-browser-exposure-v2.txt),
[affected/runtime checks](results/verification/tracking-retention-regression-v8-manifest.json).

**Insufficient result/encoding transport budgets — execution defects.** Full
investigations exceeded the inherited 32 MiB result budget. CG4 now defaults to
256 MiB while preserving explicit caller limits and CG1–CG3 defaults. An encoder
benchmark wrapper also omitted required supervision metadata, then attempted to
return large vectors as JSON. Its corrected wrapper uses owned NPY staging and
validated references; failed attempts remain retained. These wrapper bugs are not
encoder failures. Source capsules now isolate long campaigns from live edits;
source-invalidated trials are not counted. Evidence:
[budget tests](../../tests/cg4/test_predicate_cache.py),
[corrected realistic harness](qualify_realistic_v3.py),
[source runner](run_locked_qualification.py), [campaign bindings](results/recovery-interaction-capsule-v3.source-capsule.json).

**Membership execution and native admission — implementation/security hardening.**
CatBoost had hardcoded two threads even when a caller requested one. Fit and
application now honor the caller limit. Public frozen application now uses the
existing supervised worker with preallocation/alignment/type checks, cancellation
and resource caps. A fit budget includes stability refits. Geometric transforms,
PCA and distance blocks receive memory admission; graph neighbors exclude self
at duplicate landmarks. Stricter validation initially rejected a legitimate NumPy
epsilon scalar; the producer now emits its identical built-in float value.
Malformed dependencies, feature-kind mismatches and overflowing squared geometric
parameters are refused. Evidence: [execution tests](../../tests/cg4/test_membership_execution.py),
[guard tests](../../tests/cg4/test_admission_guards.py),
[initial failed group](results/verification/numek-cg4-membership-execution-v1.txt),
[focused correction](results/verification/numek-cg4-membership-execution-v2.txt),
[fit-budget closure](results/verification/numek-cg4-fit-budget-closure-v1.txt).
Default-profile computational reuse checks are separate from new qualification.

**Objective and product interpretation — contract/UX corrections.** Units now
resolve from authoritative metric/task semantics, including nats and squared
target units; incompatible declarations refuse admission. Default adverse direction
is metric-specific, with explicit overrides preserved. Diagnostic proxy exclusions
are separate from final denominators; direct/byte-identical outcome-field gates
cannot become independent hypotheses. Browser summaries avoid loading the entire
candidate pool. A CSS rule overrode native `hidden` on some labels; the corrected
view now hides irrelevant evidence controls. Historical unclocked labels remained
ineligible; a separately named, actually clocked synthetic authority exercised
later reconstruction without rewriting those facts. Evidence:
[objective tests](../../tests/cg4/test_objective_bindings.py),
[API tests](../../tests/cg4/test_interfaces.py),
[historical browser record](results/browser-historical-workflow-v1.json),
[corrected view](results/browser-historical-restatement-finding-v4.png).
Full privacy/security/browser closure is still required.
Exact predicates also previously reported precision/recall 1 without stating a
basis or handling absent S members. Their explanation now identifies the gate's
definition identity, gives supported/unavailable counts, and leaves those ratios
undefined when their denominators vanish. Membership, authoritative metrics and
approximate-surrogate fitting are unchanged. Evidence:
[identity/availability test](../../tests/cg4/test_reconciliation.py),
[focused verification](results/verification/exact-fidelity-support-v13-manifest.json).

**Incomplete overlap detail and marginal-only disclosure — product/privacy gaps.**
The first 1,000 overlapping pairs could omit relationships within the shortlist,
and neither the report's 40-row table nor the browser's zero-pair hiding rule
made all limits clear. Retention now prioritizes shortlist pairs, counts omitted
detail, and preserves unique union support even with zero pairs. Conservative
export also previously checked marginal supports without checking small nested/
intersecting components. It now audits protected D/S/H ternary memberships and
withholds the related family for rare pair cells or missing/misaligned audit
evidence. Its 16 MiB decoded-membership/256 MiB estimated pair-byte audit limits
also fail conservatively. This is not differential privacy or a guarantee against
external knowledge/repeated releases. Sixteen focused checks, four malformed-input
checks and an actual export-boundary check passed. The plain-language browser
summary was then visually verified with 120 unique S members and zero pairs.
Conservative canonical reports previously omitted overlap without explaining why.
They now explicitly describe withholding, including the unqualified higher-order
release risk. Explicit exact-aggregate authorization retains counts under public
region aliases, with private/free-form fields removed. Fifteen focused rendering,
disclosure and actual export checks passed; report-only replay reuses the saved
browser evidence without repeating analytics. Evidence:
[pair/disclosure tests](../../tests/cg4/test_related_disclosure.py),
[reconciliation tests](../../tests/cg4/test_reconciliation.py),
[verification](results/verification/overlap-disclosure-statistical-reference-v15-manifest.json),
[browser record](results/browser-overlap-identity-v1.json),
[zero-pair view](results/browser-zero-pair-union-v2.png),
[plain-language view](results/browser-overlap-summary-v3.png),
[recorded browser summary](results/browser-overlap-summary-v3.json),
[report-only replay](results/overlap-report-only-replay-v4.json).

**Python shareable export still created a learned reopening bundle — disclosure
inconsistency.** The transport hid CG4 private download handles, but the shared
artifact coordinator still wrote/returned an owner-only reopening bundle through
the direct Python API during shareable export. CG4 now creates that bundle only
for an explicit local export; exact aggregate disclosure alone does not create it.
CG1–CG3's accepted artifact behavior is unchanged. One real CG4 investigation
checked transport, Python, exact-aggregate and local paths; five affected legacy
artifact/reopening cases passed. Previously created protected bundles remain
subject to normal lifecycle/deletion; this correction does not erase old files.
Evidence: [coordinator](../../src/confidenceguard/artifacts.py),
[CG4 interface test](../../tests/cg4/test_interfaces.py),
[CG1 reopening](../../tests/cg1/test_interfaces.py),
[CG2 reopening](../../tests/cg2/test_interfaces.py),
[CG3 exports](../../tests/cg3/test_analytics.py).

**PDF failure hid surviving browser downloads — product integration bug.** The
coordinator preserved HTML/JSON, but the transport omitted the partial-export
reason from its output and CG4's job helper threw on the failed state before
rendering surviving links. Transport now retains the reason; the browser accepts
only this specific failed-export code with registered surviving artifact IDs.
Other failures and cancellation still fail normally. The job remains failed,
and the final message explicitly says the requested export failed. A focused API
fault test verified the failed status, downloadable HTML/JSON and hidden internal
exception. An isolated, visibly labelled browser fault host exercised the actual
supervisor/coordinator/job/download flow using the original protected synthetic
investigation, with no analytics/H rerun. Downloaded survivors exactly matched
the unfailed canonical export. The saved screenshot predates the final wording
clarification; complete final-copy/PDF visual closure remains open. Evidence:
[API test](../../tests/cg4/test_interfaces.py),
[fault helper](browser_export_fault.py),
[captured fault source](results/browser-export-fault-source-v2.json),
[browser observations](results/browser-partial-export-v2-observations.json),
[visible survivors](results/browser-partial-export-bottom-v2.png),
[artifact check](results/browser-partial-export-check-v2.json).

**Protected ledger receipt copied into shareable qualifications — disclosure bug.**
Code review found that scheduled-restatement independence qualifications included
an original protected reservation ID, and the shareable projection copied that
entire dictionary. It now selects a fixed vocabulary of independence states and
limitations, excluding receipt IDs and free-form declarations/future private fields.
Exact private records remain unchanged. Synthetic sentinel checks cover JSON and
the canonical HTML section, preservation of history gaps/restatement limitations,
and unexpected field values. Six focused projection/report checks passed; numerical
campaigns were unaffected and not repeated. Prior exported bytes cannot be changed
retroactively. Evidence: [correction](../../src/confidenceguard/investigation_disclosure.py),
[sentinel tests](../../tests/cg4/test_disclosure_qualifications.py),
[verification](results/verification/studentized-disclosure-recovery-v10-manifest.json).

**Threshold controls and narrow-screen evidence — browser defects.** Re-composing
the confirmation protocol left a stale protected download visible, and the narrow
candidate table broke short headings/values into fragments. Composition now clears
the frozen summary/download; wide evidence tables have bounded, keyboard-scrollable
viewports and visible scroll guidance. A generic API error also concealed the
required corrective action; fixed public messages explain selected admission
failures without echoing exception text or private values. Browser checks exercised
missing thresholds, a frozen .12 threshold, editing invalidation, a current gap
declaration, and horizontal keyboard scrolling at the original 805-pixel width.
Evidence: [browser observations](results/browser-threshold-history-gap-workflow-v2.json),
[before](results/browser-threshold-table-before-v1.png),
[after](results/browser-threshold-table-after-v2.png).
The pinned-model hash check later correctly refused execution but displayed only
`encoder_identity`. Failed CG4 jobs now carry fixed, actionable guidance and the
browser displays it beside the code; original exception text remains private.
Five focused API/contract checks and the targeted browser replay passed. Completed
encoding/discovery was not repeated for this correction. Evidence:
[before](results/browser-dino-wrong-hash-refusal-v1.json),
[after](results/browser-dino-wrong-hash-guidance-v2.json),
[safe-message tests](../../tests/cg4/test_public_job_errors.py),
[verification](results/verification/public-job-refusal-guidance-v11-manifest.json).

**Zero material thresholds were displayed as missing — reporting bug.** A
truthiness-based template default rendered a legitimate delta=0 as “Not frozen,”
including the boundary used in null qualification. The template now distinguishes
zero from missing values. Focused canonical-template checks cover zero, positive,
absent and withheld thresholds; withheld values say “Not disclosed.”
Analytics, identities and stored assessments are unchanged;
unaffected qualification runs were not repeated. Evidence:
[report semantics tests](../../tests/cg4/test_report_semantics.py),
[verification](results/verification/numek-cg4-zero-withheld-threshold-report-v2.txt).

**Offline profile dimensions and schema references — admission/harness corrections.**
Pinned E5/DINO profiles now reject dimensions other than 384/768 respectively,
before execution; supplied-vector dimensionality remains independently declared.
Core, transport and OpenAPI schemas enforce the same condition. Independent
JSON Schema validation runs in a separate five-package hashed environment, without
changing the scientific environments. Its first run incorrectly checked four
response wrappers against inner schemas; correcting that harness boundary yielded
53/53 checks, preserving the original failure. No model output or accepted profile
changed. Evidence: [runtime guards](../../tests/cg4/test_model_evidence.py),
[schema harness](qualify_schemas.py), [first attempt](results/schema-reference-v1.json),
[corrected references](results/schema-reference-v2.json),
[verification lock](../../constraints/schema-verification-macos-arm64-py313.lock).

## Historical discovery corrections

**Uniform failure above a ceiling produced no candidate — discovery design gap.**
A new deterministic supplied-prediction case with every decision wrong reproduced
the failure for both structured and CatBoost-only discovery: each returned zero
candidates. Excess-over-D-mean search has no signal, and constant-target CatBoost
correctly skips fitting. Ceiling objectives now admit one predeclared total
population gate if D conditional support suffices. The empty conjunction has no
feature dependencies; empty disjuncts and extraneous dependencies remain invalid.
It uses the existing metric, selection and confirmation machinery, adds at most
one visible baseline candidate, and performs no fitting. Its stability record is
definition identity, not empirical recovery. Both corrected countercases passed,
including public frozen membership on new rows and independent finite confirmation.
The 24-test affected group also covered a below-ceiling negative control and
empty-gate import guards.
Complement/overall objectives and their existing qualification panels are unchanged.
Broader heterogeneous/continuous-ceiling qualification remains separate. Evidence:
[countercases and controls](../../tests/cg4/test_population_ceiling.py),
[original failure](results/verification/numek-cg4-population-ceiling-countercase-v1.txt),
[corrected workflows](results/verification/numek-cg4-population-ceiling-correction-v2.txt).

**Current-risk-only targets missed a valid deterioration mechanism — design
limitation.** Code inspection and a deterministic countercase showed that a
region can deteriorate because its reference risk was unusually low while current
risk is flat. The former historical learner trained only on current-period loss.
The revised policy proposes current loss, negated reference loss and finite
within-entity period-mean differences. Unpaired rows remain in raw period heads;
paired proxies do not replace event-weighted/native historical metrics. Exact
target/support/period bindings are retained. Structured heads share the original
node and candidate budgets; actual CatBoost fits count against the global cap.
Independent target references and all three strategy countercases passed; a real
retained historical investigation verified native S effects, frozen claims and
invariance to H-only label revisions. A small 1,200-entity reference-only
development trial nevertheless failed recovery (H precision .24176, recall .84615).
That is retained selection/recovery evidence, not a numerical bug or a reason to
tune on H. The former current-only method's positive 40,000-entity development
result does not qualify this revised policy. Revised full-size reference-only
development later achieved H precision/IoU .98752 and recall 1 with no unavailable
membership. This single development result does not replace the small negative
or establish 40-seed qualification. The two locked historical panels are running;
their qualification conclusions remain open. Evidence:
[targets](../../src/confidenceguard/investigation_objectives.py),
[dispatch/budgets](../../src/confidenceguard/investigation.py),
[reference/native/H-isolation tests](../../tests/cg4/test_historical_targets.py),
[historical protocol](qualify_history.py),
[old full-size development](results/history-development-full-v1/0.json),
[small revised-policy negative](results/history-reference-only-development-v1/1.json),
[full-size revised-policy development](results/history-reference-only-development-full-v1/1.json).

**Partial-null development selected mostly alternatives — benchmark shortcoming.**
Taking only top S-ranked candidates gave no true nulls in the first 1- and
10-hypothesis development families, and only one in the 32-hypothesis family.
Zero false confirmations there could provide little evidence about null control.
Before using qualification seeds, protocol 1.1 changed to equally spaced ranks
across the native S ordering, including retained nonshortlisted gates. This uses
neither H outcomes nor mathematical truth for selection. Fresh development
families of 10/32 contained 2/7 null hypotheses alongside 8/25 alternatives;
size one still uses the first rank. Exact rational truth comes from exhaustive
population-cell membership; unavailable/undefined truth remains separate.
Two independent oracle/contract references passed in development. The later locked
1,000-seed panel completed with actual families 1/10/32, zero false-confirmation
families and one interval noncoverage (170660). The size-one subset selected 334
alternatives and no null claims; it is not null-claim error-control evidence.
Size-10/32 subsets contained 676/1,811 null claims alongside alternatives. The fixed
three-diagnostic Holm family is retained. None of these counts proves universal
control. The original records remain retained.
Evidence: [original development](results/partial-null-development-v1),
[revised development](results/partial-null-development-v2),
[locked harness](qualify_partial_null.py),
[truth references](../../tests/cg4/test_partial_null_panel.py),
[complete-panel audit](summarize_partial_null.py),
[completed panel and qualification caveat](results/partial-null-qualification-summary-v2.json).

**Stability could borrow a different representation's gate — attribution defect.**
Refit matching previously maximized S-mask IoU within strategy/head across all
representation inputs. A good gate from B could therefore conceal failure to
recover a candidate originally discovered from A. Version
`bounded_D_unit_bootstrap_refits_v2` requires the same representation as well as
strategy and diagnostic target/head. Two focused countercases prove that a perfect
other-representation gate contributes no match and cannot displace an imperfect
same-representation refit. The 13-test reconciliation/historical group passed.
Earlier v1 records remain readable and are not relabeled as v2 evidence. This is
a bounded product perturbation diagnostic, not a general stability guarantee.
Evidence: [matching](../../src/confidenceguard/investigation_reconciliation.py),
[countercases](../../tests/cg4/test_reconciliation.py),
[verification](results/verification/numek-cg4-historical-stability-coherent-unit-v1.txt).

## Current browser, reporting and diagnostic corrections

**Blank guided numbers became zero — implementation bug.** JavaScript numeric
conversion interpreted an empty ceiling or minimum-membership field as zero;
the ceiling also had an unjustified universal default. An actual browser
composition reproduced `ceiling: 0` from a cleared field. Required numeric controls
now reject blank/nonfinite values, preserve explicit zero and negative values in
objective units, and invalidate stale frozen-family/export state before composition.
The actual event-handler reference test passed; the browser separately rejected a
blank, preserved explicit zero, then inspected and discovered the exact population
gate at ceiling .1 with D/S/H 240 each and H sealed. No inferential claim was run.
Evidence: [old bad composition](results/browser-blank-ceiling-composed-v15.json),
[corrected browser evidence](results/browser-ceiling-evidence-v16.txt),
[handler tests](../../tests/cg4/browser_numeric_controls.cjs),
[verification inventory](results/verification/guided-explicit-numeric-controls-v28-manifest.json).

**Canonical PDF pagination — presentation defects.** Saved-evidence replay exposed
an orphaned candidate introduction and a zero-row overlap table heading on a new
page. Template/CSS changes keep introductions with evidence and omit empty tables.
Nine report semantics tests passed. Three disclosure profiles retained their
privacy/reopening checks; all seven corrected PDF pages were visually inspected.
Actual supervised browser HTML/PDF/JSON downloads were byte-identical to the direct
canonical replay. An initial impression of missing text was not confirmed: saved
rasters were byte/pixel identical. No PDF content defect was inferred from that
preview. Evidence: [replay tool](replay_saved_reports.py),
[visual checks](results/reports-current-source-v4/visual-verification-v1.json),
[browser parity](results/browser-current-downloads-v15-check.json),
[verification inventory](results/verification/canonical-report-pagination-browser-v27-manifest.json).

**Qualification discarded diagnostic detail — evidence-retention gap.** Earlier
recovery summaries omitted already computed stability/fidelity details. New harness
versions retain them and apply the existing frozen surrogate to independent feature
rows, exposing all applicability denominators. Old records remain explicitly
unrecorded; no retrospective values are invented. Nine focused checks passed; a
native computational replay preserved gates, recovery, effects and finite intervals.
The idle remaining-anchor queue changed source before its first trial, preserving
seeds/criteria. Small curved development showed weak approximate H explanations
(precision .047/.114, recall .212/.399), despite useful exact-gate recovery. Those
nuisance-feature surrogates do not define membership and are not labeled high
fidelity; this is an explanatory limitation, not an identified gate-calculation bug.
Evidence: [diagnostic helper](qualification_diagnostics.py),
[negative development evidence](results/diagnostic-retention-development-v1),
[queue transition](results/diagnostic-retention-queue-transition-v1.json),
[verification inventory](results/verification/frozen-diagnostics-retention-v29-manifest.json).
The completed categorical/numeric panel recovered the oracle in 40/40 seeds, but
its 68 selected CatBoost gate occurrences had median perturbation IoU .290 and
frozen H surrogate precision .241/recall .807. These overlapping gates are not
independent trials. The product also now exposes both applicability sources and
gate members without an explanation, rather than showing conditional precision/
recall alone; focused calculation/privacy/report checks passed. Evidence:
[complete recovery](results/recovery-categorical-numeric-summary-v1.json),
[gate diagnostics and retained trial references](results/recovery-categorical-numeric-diagnostics-v1.json),
[correction and audit inventory](results/verification/fidelity-history-categorical-v36-manifest.json).

**Supplied outcome status and displayed estimand — provenance/product gaps.**
Supplied snapshots previously collapsed nonfinal statuses into one eligibility
reason; public and browser summary projections also hid the exact observed-label
scope. Explicit status mappings now admit pending/withdrawn alongside existing
states, leaving the legacy default map and CG1 eligibility reducer unchanged.
CG4 retains a descriptive status sidecar, respects as-of availability independently
of maturity-reason precedence, and exposes safe status counts with joint rare-cell
protection. Direct outcome-status features are now positively identified as
outcome-derived and cannot define confirmable gates. Normalized rows/population
identities are unchanged. A selective-label example omits every H error: the
observed-label claim remains narrow and the full-population claim is refused.
Focused product/disclosure/report, legacy CG1/CG3, numerical-retry, historical-capture,
3.12/3.14 and independent schema checks are recorded separately; their overlapping
counts are not a single new campaign. Missing outcomes still cannot be recovered
or corrected without a justified observation design. Evidence:
[observation/contamination references](../../tests/cg4/test_outcome_observation.py),
[projection privacy references](../../tests/cg4/test_related_disclosure.py),
[independent schema checks](results/schema-reference-v3.json),
[product and compatibility inventory](results/verification/outcome-provenance-scope-product-v32-manifest.json).

**Realistic Wine continuation — source/evidence boundary.** Wine v1 completed but
lacked held-out native effect detail; v2 computed it while source changed and
remains invalidated. A current-source natural/injected rerun supplied the missing
valid detail in 141.65 s. Bank, AG News and CIFAR evidence was reused. Every claimed
runtime source and benchmark harness has an actual retained byte reference; no
missing history was reconstructed. The first new command used a nonexistent
`--dataset` option and ran no analysis; its usage failure is retained. No acceptance
criterion was changed. Evidence: [four fixed journeys/source references](results/realistic-workflow-summary-v2.json),
[retained original Wine](results/realistic-wine-v1.json),
[invalidated Wine](results/realistic-wine-v2.json),
[verification inventory](results/verification/probability-realistic-temporal-evidence-v31-manifest.json).

**Legacy provenance and inline authority — implementation defects.** Older typed
captures lacked a status-derived marker; genuine CG3 binding-context captures also
lacked CG4 source-identity sidecars. Current readers now recover positive origin
information from capture metadata and, for unambiguous single-run/key bindings,
retained opportunity identities. A genuine old-source control reconstructed all
720 event/source identities and refused the outcome-derived gate while preserving
six original objects. The separate typed control kept a same-named, unrelated source
unblocked. Ambiguous origins remain unknown. Testing exposed a real historical-store
`spec.outcomes` crash and an incorrect target-fact lookup; the latter was corrected
to the actual retained opportunity identity. Metadata used for these checks is now
a transitive assessment dependency. Inline outcomes also bypassed ledger reservation:
the hook checked only explicit bindings. One shared property now preserves CG1's
existing implicit authority rule, with unchanged serialized fields and reductions;
subsequent CG4 use detects the prior exposure. Scoped historical/lifecycle, CG1/CG2,
and 3.12/3.13/3.14 checks passed. One context-harness field encoded an omitted control
as false; its audited summary marks it unassessed, preserving the raw result without
inventing a failed or successful experiment. Evidence:
[legacy controls and correction](results/legacy-origin-controls-summary-v1.json),
[old-context identity proof](results/legacy-context-status-capture-v6.json),
[exact recorded focus sources](results/legacy-context-status-v6-recorded-sources.zip),
[legacy producer/control](check_legacy_status_capture.py),
[verification inventory](results/verification/legacy-origin-inline-authority-boundary-v34-manifest.json).
Original aliases can still be absent for ambiguous legacy captures. Confirmation
now labels those local checks partial and preserves that limitation in private/
shareable evidence, browser text and canonical reports. It does not infer freshness
or upgrade declarations to system verification. Six targeted exposure/live/history
checks and two presentation checks passed; numerical methods are unchanged. See
[scope and presentation checks](results/verification/fidelity-history-categorical-v36-manifest.json).

## Compatibility and remaining delivery limits

**Evidence receipt referenced omitted synthetic state — review-packaging defect.**
A read-only payload audit found that the generic `.nosync` exclusion would omit
74 synthetic workspace files named by an earlier verification receipt. The review
inventory now admits only those exact hash/size-verified files within the two
known synthetic fixtures. Environment/cache exclusions remain intact; unknown
excluded paths, traversal, links and changed bytes refuse. Eighteen packaging
checks passed, and the actual inventory now includes all 74 unchanged files.
No analytical campaign was rerun or final ZIP published for this correction.
Evidence: [before](results/review-referenced-state-admission-before-v67.json),
[after](results/review-referenced-state-admission-after-v67.json),
[tests and source](results/verification/review-referenced-state-v67-manifest.json).
The same dependency audit found eight omitted legacy test-helper/fixture paths.
The payload now includes the authored validation code, a synthetic CSV and the
accepted CG1 JSON required by those tests; external tables/weights remain excluded.
Nineteen packaging tests passed, 96 affected cases collected from separate staging,
and the historical CG1 re-export passed using the installed wheel without changing
the stored JSON. Collection is not a 96-test regression pass. See
[before/after and clean-staging evidence](results/verification/review-legacy-fixtures-v68-manifest.json).

**Broad/narrow recovery — selection-method shortcoming.** The complete original
40-seed panel achieved 19 successes, below the locked 32 requirement (median H
precision .99129, recall .68506). A D/S-only replay reproduced its first shortlist:
a broad high-quality candidate existed, but severity ordering filled slots with
narrow variants. The versioned selector preserves the first severity extreme,
then considers a declared-material-excess × conditional-support anchor using the
same availability, overlap and marginal-admission checks. The retained S replay
improved recall from .69277 to .98544 with two gates; this is post-hoc development
evidence, not independent qualification. Exact toy regression, inspection identity,
canonical disclosure and selection checks cover the correction. Fresh locked
panels retain the original acceptance targets; previous failures remain visible.
The earlier AP panel independently completed 40/40 recovery, with 40 approximate
confirmations, at its recorded old profile. Partial old panels (39 paired-error,
26 reference-only-history, 17 paired-precision trials) are not complete evidence;
no termination cause is established. See [failed panel](results/recovery-broad-narrow-summary-v1.json),
[retained diagnostics](results/recovery-broad-narrow-diagnostics-v1.json),
[D/S replay](results/broad-narrow-S-reconciliation-v57.json),
[partial inventory](results/superseded-selection-v1-partial-inventory-v59.json),
[AP audit](results/objective-ranking-ap-summary-v1.json),
[correction and source inventory](results/verification/selector-correction-v59-manifest.json),
[241-test primary closure](results/verification/selector-integrated-v59-manifest.json),
[14 affected checks per runtime and saved PDF inspection](results/verification/selector-runtimes-paired-PDF-v60-manifest.json).
The fresh revised-selector broad/narrow panel subsequently passed **40/40** with
unchanged targets (median independent-H precision .99032, recall .98940; zero
unavailable H membership). Native counts/public SciPy interval composition agreed
for all 87 overlapping finite confirmations. This does not erase the original
failure or qualify other profiles. Individual CatBoost surrogate precision still
fell as low as .19277 and D-perturbation IoU as low as .22481; strong union recovery
does not make every explanation stable or faithful. See
[fresh panel, diagnostics and reference](results/verification/recovery-broad-narrow-selection-v2-v69-manifest.json).
The fresh interaction, parity and categorical/numeric panels also passed 40/40
each at their locked profile. Parity's median H precision was only .75032 despite
recall .99437: roughly a quarter of its predicted members were outside the oracle
region. Passing the .70 recovery thresholds is not precise population recovery.
Native count/public-SciPy composition agreed exactly for all 256 selected claims;
37 were inconclusive. Candidate occurrences overlap, and panel successes cannot
be pooled into an independent universal-recovery claim. See the
[three-panel evidence and reference audit](results/verification/recovery-three-panels-v98-manifest.json).

**Build/reproduction tooling — provenance and fixture defects.** The first new
wheel build produced bytes but could not record a separate `wheel` distribution
version in the scientific environment. A dedicated hash-locked build environment
and preflight now record all three build tools before building from clean sources.
The installed paired-precision reproduction initially supplied one binding for two
runs and was correctly refused before analytics. Fixing the fixture to bind both
runs produced the expected .5 adverse precision difference with distinct 120/60
denominators, known-exposure refusal, mixed-codec backup and immutable restore.
Failed build/fixture evidence is retained; no runtime metric was changed by either
tooling correction. The v53 wheel predates the later selector revision. See
[build evidence](results/wheel-current-v53/verification.json),
[installed reproduction](results/review-reproduction-paired-v55/verification.json),
[tooling evidence inventory](results/verification/selector-correction-v59-manifest.json).
The later v61 wheel includes the selector revision; 28 installed checks, current
browser refusal/downloads, the three-strategy reproduction, all 19 report pages
(15 identical pages reused, four changed pages inspected), and actual tar/CLI
restore of 21 immutable objects have separate
[current installed evidence](results/verification/selector-installed-reproduction-v66-manifest.json)
and [browser evidence](results/verification/browser-selector-paired-v62-manifest.json).
These do not constitute method qualification, final ZIP verification or acceptance.

**Review-tool admission — security defects caught before handoff.** Authored probes
showed that the initial review verifier accepted Windows drive paths and symlink
entry metadata; the wheel checker also followed an external synthetic source link.
No unsafe extraction or customer-data access occurred. Checks now reject portable
path aliases, alternate streams, nonregular members and source escapes before
hashing; the tracked patch also disables Git external helpers and requires a commit
SHA. Twelve focused tests passed, and the same two saved unsafe ZIPs now refuse.
These are review-tool fixes, not a claim to support arbitrary untrusted extraction.
Evidence: [before/after probes and fixtures](results/review-adversarial-fixtures-v1),
[tests](../../tests/cg4/test_review_package.py),
[correction inventory](results/verification/review-admission-v39-manifest.json).

**Official CPU wheel tag rejected by legacy admission — compatibility defect.**
Audit found that Linux/Windows locks select Torch `2.8.0+cpu`, but DataTrust's
literal `2.8.0` check would reject that official CPU build. Text/image admission
now accepts only the exact public pin or its exact `+cpu` form, and records the
actual observed version. Other tags, development builds and Torch 2.10 remain
rejected by the original DataTrust profile. Nine metadata/file-admission tests,
three actual macOS legacy regressions (including offline E5), and pinned DINO file
admission passed. Mac public-version provenance is unchanged; no cross-build
numeric parity or Linux/Windows execution is claimed. The first regression command
selected a nonexistent test and ran none; the corrected invocation is retained.
Evidence: [admission tests](../../tests/cg4/test_datatrust_cpu_build_admission.py),
[DINO admission](results/datatrust-image-runtime-admission-v1.json),
[verification/references](results/verification/datatrust-cpu-build-compatibility-v14-manifest.json).

**Python modernization exposed real platform boundaries.** The isolated runtime
initially lacked native GObject/Pango discovery; the recorded native-library path
resolved the PDF regression. Python 3.12 changed test-only Python-object header
sizes; fixture memory expectations were corrected without changing analytical
results. Python 3.14 added 27 built-in casefold mappings; a bundled mapping keeps
DataTrust's accepted representation. Its separate CG4 Torch 2.10 profile is not
relabeled as the original Torch 2.8 profile. Pinned Lingua remains unavailable on
3.14; unchanged Unicode/regex source builds passed. Linux/Windows locks are
resolution evidence, not executed support. Evidence:
[runtime audits](results/runtime-macos14-arm64-py314-v2.json),
[compatibility log manifest](results/verification/compatibility-and-reference-log-manifest-v2.json),
[Unicode audit code](audit_unicode.py),
[runtime tests](../../tests/cg4/test_runtime_compatibility.py).

At their recorded source boundaries, the 52-test CG4 suite passed on Python 3.12
and 3.14; later execution-boundary changes have focused verification records.
Storage measurements reaching one million rows do not establish million-row
discovery capacity. Required recovery/null/approximate-method/resource campaigns,
final compatibility/product closure and the verified review ZIP remain incomplete.
The final ZIP must contain this document, every referenced test/artifact/source
needed to inspect these findings, and a manifest covering them. Dataset contents,
model weights, environments and credentials remain excluded. Documentation alone
does not require rerunning valid, unaffected verification.
