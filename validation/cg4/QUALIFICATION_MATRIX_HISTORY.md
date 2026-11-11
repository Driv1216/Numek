# CG4 qualification and remaining gates

Status recorded 2026-10-28. This is an evidence map, not a claim that CG4 is
complete. Read [implementation findings](CG4_IMPLEMENTATION_FINDINGS.md) for
failures/corrections and [methodology](../../docs/CG4_CONFIDENCEGUARD.md) for assumptions.

## Current implementation boundary

Latest runtime source is
`c974f15f6b9644fb4f7ed94434c1ee829cb337fd131fff33bff70974ad3eaf7f`.
Only confirmation work feasibility changed: separate bootstrap component calls and
registered ranking setup are now counted before H. Fifteen admission/discovery/
confirmation checks, 20 caller/retry/report checks and seven affected checks each
on 3.12/3.14 pass. Numerical kernels and all other runtime files match the preceding
source. See [correction evidence](results/verification/work-admission-v106-manifest.json).
The 271-test full suite and v96 wheel below remain earlier-boundary evidence;
they are not relabeled as a new full closure or current wheel.

The revised automatic selector is
`severity_material_excess_support_frontier_v2`. Its running qualification source is
locked at `59f6784386f6a7b1db909ddb59f564f5154283198175d2c8f32cf0489078955c`.
Later correction source `587d12d2bee5fe896f5f071c41e3f3961164b07ea81e33f02d8f33bb9846e980`
moves unsupported-method refusal before H metrics, versions the R2 proposal target,
and repairs extended-uncertainty loss-table visibility/future-H-only registration.
The preceding entity-design source is
`7d74efcb284f5bae24f4aef4359eef898f9ace83b179014a8059b537bcf246c1`,
adding an explicitly chosen finite one-potential-observation-per-entity/arm design.
It passed 271 CG4 tests, nine product checks on 3.12 and twelve product/tool checks
on 3.14. The new v96 wheel has exact 196-file parity in a fresh 83-distribution
installation; its focused installed checks are recorded in the
[entity-design receipt](results/verification/entity-arm-v97-manifest.json).
All 19 installed product/correction checks passed without a source-tree override.
The eight numerical interval/feasibility functions are unchanged. The campaign
contains no R2 objective and its uncertainty panels use the existing interval
adapters; its source identity is retained, not relabeled. Correction verification
and the new wheel are recorded separately in the findings receipt.
The [241-test closure](results/verification/selector-integrated-v59-manifest.json),
[affected Python 3.12/3.14 checks](results/verification/selector-runtimes-paired-PDF-v60-manifest.json),
[earlier installed-wheel reproduction](results/verification/selector-installed-reproduction-v66-manifest.json)
and [actual browser workflow](results/verification/browser-selector-paired-v62-manifest.json)
cover correctness/product boundaries. They do not establish discovery recovery or
statistical coverage. Later packaging/validation-only corrections have focused checks.

## Discovery and selection

| Evidence | Established within the recorded profile | Remaining gate or limitation |
|---|---|---|
| Broad-moderate/narrow-severe recovery | Original selector: 19/40 successes, below its target; failure retained. Revised selector: fresh 40/40 successes, median H precision .99032/recall .98940 | Qualified only within this locked synthetic profile; other revised-selector panels remain open. No unavailable H records were dropped. |
| Other completed original recovery panels | Recorded original-selector recovery, including retained missed seeds and unavailable membership | Their automatic-shortlist results are not relabeled as current-selector qualification. |
| Objective-specific panels | Original profiles separately assess FNR, FPR, precision, Brier, calibration, regression, ranking and uncertainty | Revised-selector panels use fresh seeds. Unified success does not qualify every learner/objective combination. |
| Paired precision | Corrected common issued base, distinct positive denominators and D-only ratio-influence proposal target; native references/product checks pass | Original corrected-proxy/old-selector campaign is partial. Fresh complete qualification remains required. |
| R2 | The versioned negative-squared-residual proposal respects lower-is-worse R2; native arithmetic, an obvious structured-failure fixture and generator checks pass | No 40-seed recovery or native R2 confidence-interval qualification. A retained variance counterexample reverses the proxy/native ordering; this is not a measured learner-recovery trial. The fresh equal-variance panel is prepared but unrun. |
| Historical deterioration | Current/reference reducers, entity grouping, reference-favorable/difference heads and immutable replay are checked; original current-risk panel passed recovery | Original reference-only panel is partial. Fresh current/reference-only panels and valid complete-entity inference remain separate. |
| Geometric fallback | Original standalone curved-region anchor passed 40/40, within its recorded envelope | This does not qualify every representation/objective or the revised full-engine selector. Unsupported membership stays in planned denominators. |
| NUMEK landmark method | Promotion rejected by predeclared logical futility on 21 curved-region pairs | Experimental, not promoted; no complete two-family or controlled efficiency success claim. Negative evidence is retained. |
| Simpler baselines | Locked first-gate comparisons retain both wins and losses; categorical/interaction comparisons sometimes favor simpler methods | Full shortlist recovery cannot replace the predeclared first-gate comparison. Concurrent trial time is not a controlled efficiency comparison. |
| Explanation and stability | Frozen gate/surrogate applicability and D-perturbation diagnostics are retained | Weak measured fidelity/stability remains visible. Exact membership parity is a separate requirement; no universal high-fidelity label. |

The [fixed fresh-panel driver](run_selection_campaign.py) runs **28 complete panels**:
10 recovery archetypes, 14 objective families, two historical scenarios and the
2,000/200 reduced/default complete-null panels. This is 3,240 planned trials, not
3,240 additional independent claims or a qualification conclusion. The existing
broad/narrow panel is audited first, then 27 panels run serially with up to four
independent seed subprocesses each. Every trial keeps its original per-job limits.
Recovery requires precision and recall at least .70 in at least 32/40 locked
seeds; the original targets are unchanged. The first broad/narrow panel is complete,
with [native/public-SciPy and diagnostic audits](results/verification/recovery-broad-narrow-selection-v2-v69-manifest.json).
Interaction, parity and categorical/numeric conjunction also completed 40/40 each,
with no unavailable H observations. Median H precision/recall were 1/1,
.75032/.99437 and .99919/.99716 respectively. Parity's approximately one-quarter
false-member share remains a limitation despite passing the locked .70 thresholds.
After the user-requested stop, parity was explicitly resumed under the same
source/seeds; interrupted attempts remain in the stop/resumption receipts and are
not called new independent evidence. The campaign has advanced to rare failure.
Execution or acceptance failure stops
the sequence and preserves its evidence. Read its operational profile under
`results/selection-qualification-v2-portable-v65/` before resuming.
The [completed three-panel receipt](results/verification/recovery-three-panels-v98-manifest.json)
preserves all 120 trial hashes and a read-only native/public-SciPy audit of 256
overlapping claims (219 confirmed, 37 inconclusive). No trial was rerun for this audit.

## Confirmation

| Procedure/evidence | Status | Remaining gate or limitation |
|---|---|---|
| Bernoulli component intervals, registered exact composition and bounded Hoeffding routes | Established finite-sample mathematics under the declared assumptions; retained direct simulations/reference checks | Correct population, independence, observation design, bounds and frozen error allocation remain prerequisites. No causal/future guarantee. |
| Explicit independent entity arms, finite method | One potential observation per frozen arm; 30,000 null and 2,000 power trials, 136 scalar references, historical/product/runtime checks | Only IID complete entities under the declared design. Near-threshold power is weak; 400 retained assumption-violating controls show substantial error. No general cluster or unbounded-mean qualification. |
| Original full-pipeline complete nulls | One false-confirmation family in 2,000 reduced runs; none in 200 default runs. Fixed joint excess-error diagnostics did not reject | Original-selector evidence only. Fresh revised-selector complete-null panels remain required; non-rejection is not proof of nominal control. |
| Partial nulls, overlapping claims and families 1/10/32 | Retained 1,000-trial finite-procedure evidence, with one interval noncoverage and no false-confirmation families | The size-one subset contains no null claims. It is not size-one null-control evidence or workspace-wide control. |
| Joint BCa smooth means/ratios | Genuine heavy-tail and unequal-cluster undercoverage; independent SciPy agreement supports method-failure attribution | Product confirmation remains refused. A qualified operating-envelope resolution is an outstanding requirement. |
| Component BCa / bootstrap-t candidates | Power alone did not repair coverage; retained qualification failures | Not enabled. Their failures cannot be erased by choosing a favorable development panel. |
| Ranking percentile bootstrap | Retained AUC/AP approximation evidence under its recorded support/tie/family profiles; original AP recovery passed 40/40 | Approximate, with scoped qualification. It does not confer extreme-tail, arbitrary-support, dependence or generic unbounded-mean guarantees. |
| Known-variance Catoni prototype | Validation-only evidence with explicitly supplied population variance bounds | Adds a substantial assumption and can yield wide intervals. It is not silently substituted for the approved generic mean procedure. |
| CG3 moving-block bootstrap | Excluded from CG4 confirmation; undercoverage remains negative evidence | Unsupported temporal dependence/common shocks refuse claims. |
| Bootstrap feasibility | Family/component allocation, nominal and adjusted tails, invalid replicates, numerical retries and budgets have correctness checks | Monte Carlo tail resolution is not a coverage theorem. No family shrinking, confidence reduction or invalid-replicate deletion. |
| Exposure, restoration and restatement | Protected reuse controls and immutable identity/refusal workflows are implemented and checked | Declarations are not system verification; absent/deleted history never proves freshness. Study-scoped control does not imply workspace-wide control. |

## Delivery and acceptance

Reuse valid unchanged finite-kernel, encoder, legacy, storage and lifecycle
evidence. Fresh selector qualification does not require repeating those campaigns
solely because documentation or packaging changes. The
[packaging reference correction](results/verification/review-referenced-state-v67-manifest.json)
retains exact synthetic evidence without admitting environments/model caches.

Outstanding work includes the fresh selector campaigns, required method-specific
qualification/controlled resource comparisons, the unresolved smooth-mean/complete-
entity inference envelope, final evidence reconciliation and the verified technical-
review ZIP. A required method failure remains an unmet requirement. Independent
technical review, founder-authorized corrections, the understanding gate and founder
acceptance follow implementation delivery and have not occurred.
