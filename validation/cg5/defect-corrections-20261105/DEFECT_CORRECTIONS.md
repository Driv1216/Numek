**CG5 targeted D1–D5 correction report — 5 November 2026**

**Disposition: D1–D5 corrected and verified; ready for focused independent re-review.** CG5 is not declared accepted. This pass is limited to the five defects in the second independent re-review. No CG6, review ZIP, educational implementation report, research campaign or architecture rewrite was started.

The reviewed report is preserved as [CG5_INDEPENDENT_RE_REVIEW_20261105.md](CG5_INDEPENDENT_RE_REVIEW_20261105.md). The original reviewer programs were copied beside it, executed on the unchanged starting runtime, and then executed against the corrections. The raw reproduction logs and regression tests are the evidence, rather than this report's assertions.

**Source and preservation**

Starting runtime: `cecde695823502f5744268d7bb5c62edfe223eb07c2cd819de2fe2e601ed1ef2`.

Corrected runtime: `7d3f64affcbc9491223e23294482149848f3bd945a7aaefce33af4af7b3fc3b9`.

Each identity is SHA-256 of the UTF-8 canonical JSON map from runtime paths to file SHA-256 values, sorted keys and compact comma/colon separators. The runtime contains 190 files. [baseline.json](baseline.json) captures the reviewed working tree; [final-source.json](final-source.json) records the corrected map and exact before/after hashes. Comparison is against the captured modified/untracked runtime, not committed HEAD. No dependency installation or replacement occurred.

Six runtime files changed. The other 184 runtime files, including DataTrust, CG1–CG4 numerical kernels, normalization, history/catalog storage, workers, codecs, schema files, artifact publication and PDF generation, retain their baseline hashes. Existing modified/untracked work is preserved. The new test module, review/correction evidence and small documentation updates are outside the runtime digest.

**D1 — Regression selective-risk inference: corrected**

Before correction, the original public assessment reproduction supported `mean absolute selective loss <= 0.1` after 40 observed zero losses, using a binomial upper bound `0.08809730287880237` despite true declared bounds `[0,10]`. An IID distribution with loss 0 at probability .95 and loss 10 at probability .05 has mean .5; its all-zero sample has probability `.95**40 = .12851215656510312`, exceeding alpha .05.

`policy_metrics.bernoulli_contribution(metric, task)` now registers whether the actual contribution is Bernoulli. Regression selective risk is Bernoulli only for the registered material-error indicator loss. `_interval` selects Clopper–Pearson from that semantic property, rather than checking whether the observed values happen to be 0/1. Absolute, squared, signed and pinball regression losses use the existing true-bound Hoeffding mean procedure; bounds violations still refuse the claim. `method_refusal` uses the same semantic predicate for its statistical dependency admission. Direct claim evidence identifies the procedure actually used; transformed/composed and comparator methods retain their appropriate existing paths.

After correction, the original sample returns **inconclusive**, interval **[0, 2.147347041733688]**, method `bounded_mean_hoeffding`, support 40, and policy support `not_established`. Its true mean .5 is inside the interval. Genuine Bernoulli material-error and classification estimands retain CP inference.

Evidence: [before](reproduce-inference-before.log), [after](reproduce-inference-final.log), [original reproduction](cg5_statistical_probe.py). Regressions include all five registered regression losses, violated bounds, immutable result reopening, public projection and an owned API assessment. The existing CG1–CG4 inference kernels were not edited or newly qualified.

**D2 — Global tolerance nomination: corrected**

Before correction, each MILP family or hybrid branch returned its local tolerance nominee. In the reviewer's example, the family scores were .6 at complexity [4,1] and 0 at [3,1], while an explicit policy scored 1 at [5,0]. With absolute tolerance .65, local selection compressed the family to score 0. That score is outside the global band; the globally eligible .6 policy was lost and the more complex score-1 policy was nominated.

`milp_family` now streams validated objective incumbents and every candidate needed for global tolerance nomination into the existing bounded analytical selection state. It keeps a local result for the internal helper contract but that result no longer compresses cross-family search. `search` connects the stream directly to `keep`/analytical contenders. `hybrid_family` passes the same stream through every outer route, under shared budgets. Direct helper calls retain a bounded candidate set and keep its memory reservation while returned candidates remain live, including multiple calls sharing a budget.

The coverage argument is explicit. For relative tolerance `r <= 1`, `U(x) = x + absolute_tolerance + r*abs(x)` is nondecreasing. Any future global lexicographic reference has first component no larger than a family's literal first optimum. Therefore every globally eligible candidate is inside that family's first-component upper envelope. Later lexicographic components remain unrestricted: their local reference is not a valid global pruning rule. With `r > 1`, this monotonic guarantee is unavailable, so nomination examines the whole admitted one-hot family under the same limits. Exhaustion of candidate, solver, matrix, time or nomination-memory admission cannot inherit complete nomination standing.

After correction, exhaustive enumeration, direct search and public supervised optimization nominate **.6**, with global empirical optimum **1.0**. Tests also cover an independently enumerated second family, hybrid routing, a one-candidate detail pool, a later priority outside its local tie band, weighted selection, relative tolerance above one, and incomplete resource standing. Completed public optimization preserves `tie_coverage`; it reports `incomplete_best_found` when the relevant search is incomplete.

Evidence: [optimization before](reproduce-optimization-before.log), [optimization after](reproduce-optimization-final.log), [reviewer reproduction](cg5_independent_rereview.py). Small exhaustive comparisons, rather than the optimizer's own certificate alone, establish the expected nominee.

**D3 — Weighted RMSE tie certification: corrected**

Before correction, weighted mode disabled the RMSE endpoint transformation. The encoded objective was weighted signed MSE, while its tie bounds were specified in weighted signed RMSE units. The reviewer's empty, incorrectly scaled band was called exhausted even though valid tolerance ties existed.

`encoded_tie_bounds` transforms both endpoints with the correct direction and weight. For positive weight `w` and minimization, the transformation is `w * max(0, endpoint / w)**2`; maximization uses the corresponding negative signed transformation. Zero weight is a constant scalar objective and its finite choices remain eligible for structural/canonical refinement. Overflow or nonfinite transformed endpoints explicitly refuse numerical admission. Mixed nonlinear weighted sums containing RMSE remain explicitly incompatible with this MILP encoding; finite enumeration remains available. No approximate linearization is introduced.

The reviewer's literal optimum remains **2.4186773244895647**, but the canonical tied policy at **3.2171415884290826** is now correctly nominated with absolute tolerance .9. Three tied assignments are examined before a valid encoded infeasibility proof establishes exhaustion. Tests compare against full enumeration at weights 0, .5, 1 and 3, in both directions, and exercise public weighted-RMSE optimization. A solver-call limit yields `solver_optimal_objectives_tie_incomplete`, not complete nomination.

Evidence: the `weighted_rmse` section of [before](reproduce-optimization-before.log) and [after](reproduce-optimization-final.log), plus focused exhaustive and admission regressions.

**D4 — Hybrid frontier completeness: corrected**

The reviewer's 18-combination hybrid example reported `complete_empirical_frontier` despite omitted nondominated coordinates (.4,.6) and (.6,.4).

`policies._optimize_worker` now treats both MILP and hybrid optimization as insufficient evidence for a complete Pareto frontier. Complete literal objective/tie optimization can still retain its separately justified optimizer standing, but the empirical frontier is reported as `sampled_tradeoff_set`. A complete finite-enumeration reference retains `complete_empirical_frontier` only when its existing coverage, retention and dominance requirements are satisfied. No new full-frontier solver is claimed.

The original hybrid reproduction now reports `sampled_tradeoff_set`. Tests compare hybrid optimization with exhaustive finite enumeration and check protected HTML and public optimizer-standing projection. Conservative joint withholding remains active for private/small-component evidence.

**D5 — Public claim semantics: corrected**

Before correction, two pinball levels .1/.9, squared selective risk and a material-error threshold .5 retained public estimates/conclusions/intervals but lost the parameters needed to identify their questions.

`policy_metrics.claim_parameters` records units and the applicable regression loss, pinball level, outcome units and material-error threshold with each local claim. `policy_result.public_claim_parameters` reconstructs those controlled semantics from the full metric/task definition, including older protected results. Public projection includes them only when the claim is interpretable under disclosure. Existing protected scope, economic and output-target rules still apply.

Arbitrary native-unit text remains protected. A fixed controlled vocabulary of generic units is shareable (`fraction`, `count`, `items`, `squared_items`, `dimensionless`, `native_loss_units`, `native_squared_units`). Other native-unit names require an explicitly configured public label through `DisclosureSpec.display_labels['units:' + original_unit]`. When necessary metric/outcome units or a material threshold cannot be identified safely, the claim's estimate, conclusion and interval are withheld together. The original family size and allocation are not redistributed. Public output never echoes the original private mapping key.

The canonical assessment table now shows units/outcome units, loss, pinball level and material threshold. It can render these from retained definitions when older local rows lack the new convenience fields. All four original claims remain interpretable in the safe generic-unit fixture. A private-unit fixture withholds its entire claim; an explicit approved label permits a meaningful public claim. Public imports remain unable to recover protected output.

Evidence: [before](reproduce-projection-before.log), [after](reproduce-projection-final.log), [original reproduction](cg5_projection_probe.py). Owned API, private/public JSON, HTML, import and legacy rendering regressions pass. [qualify_claim_reports.py](qualify_claim_reports.py) checks two synthetic local/shareable PDF/JSON/HTML sets. Both PDF text/privacy checks pass; the three changed-table pages were rendered and visually inspected, with no clipping/overlap. Full legacy PDF qualification was reused, not repeated. The report fixture predates the final direct-hybrid memory-lifetime refinement; its assessment/projection/template components are byte-identical to the final source, so its text/layout evidence remains applicable. See [report checks](reports/verification.json) and [visual QA](reports/visual-qa.json).

**Exact implementation changes**

| File | Changed/new functions or block |
|---|---|
| [policy_metrics.py](/Users/drivyaanshyadav/Desktop/Numek/src/confidenceguard/policy_metrics.py:26) | Added `bernoulli_contribution`, `claim_parameters`. Existing authoritative action/contribution/reducer functions remain unchanged. |
| [policy_assessment.py](/Users/drivyaanshyadav/Desktop/Numek/src/confidenceguard/policy_assessment.py:95) | `method_refusal`, `_interval`, `_assess_worker`: semantic inference admission/dispatch, accurate direct procedure names and complete claim parameters. |
| [policy_optimization.py](/Users/drivyaanshyadav/Desktop/Numek/src/confidenceguard/policy_optimization.py:102) | Added `encoded_tie_bounds`; changed `milp_family`, `hybrid_family` and its `collect`, `search`: valid weighted RMSE bands, global nomination streams/envelopes, bounded retained memory and qualified nomination coverage. Existing `choose`, objective ordering and authoritative replay remain unchanged. |
| [policies.py](/Users/drivyaanshyadav/Desktop/Numek/src/confidenceguard/policies.py:171) | `_optimize_worker`: preserve nomination coverage after replay audit; distinguish hybrid/MILP optimization from complete frontier enumeration. |
| [policy_result.py](/Users/drivyaanshyadav/Desktop/Numek/src/confidenceguard/policy_result.py:19) | Added `public_claim_parameters`; changed `PolicyResult.to_dict`: interpretable controlled parameters, approved unit labels or joint withholding. |
| [policy_sections.html](/Users/drivyaanshyadav/Desktop/Numek/src/confidenceguard/templates/policy_sections.html:8) | Assessment table: show defining regression parameters with retained-definition fallbacks. |

New regression module: [test_defect_corrections.py](/Users/drivyaanshyadav/Desktop/Numek/tests/cg5/test_defect_corrections.py), **13 test functions / 32 cases**. Documentation updates are restricted to `docs/CG5_CONFIDENCEGUARD.md`, `docs/CURRENT_STATE.md`, `docs/NUMEK_MASTER_CONTEXT.md`, `validation/cg5/README.md` and `validation/cg5/VERIFICATION.md`, linking the current correction status and explaining the corrected behavior. This directory contains the review, reproduction programs/logs, manifests, report fixture and verification records.

**Verification and interactions**

The completed final gate passed **121 tests**, with **one known optional-validator skip**, in **265.94 seconds**. It includes all CG5 tests and the existing CG1–CG4 interface modules. The separate retained schema environment passed **107 checks**: 63 CG1–CG4 and 44 CG5. The skip is CG2's optional `jsonschema` import in the analytical environment; its transport-schema examples are covered by the separate schema checks. All **32 new D1–D5 cases** and **27 previous R01–R09 cases** are included in the passing gate. No runtime or new-test bytes changed during the completed gate.

See [final affected log](final-affected-tests.log), [machine-readable verification](verification.json), [CG1–CG4 schema receipt](schema-cg1-cg4.json) and [CG5 schema receipt](schema-cg5.json). `git diff --check` passed. The exact command is recorded in `verification.json`.

The gate uses the retained Python 3.13 / NumPy 2.4.6 / SciPy 1.18.1 / HiGHS 1.12.0 environment and existing native PDF libraries. No broad null/power campaign or new platform/capacity qualification was run. The 576-case suite was not repeated. Unchanged generated schemas and earlier numerical qualification retain their original evidence; existing interface/schema tests supplement them.

The original R01–R09 regression module is included in the final affected gate, together with all CG5 solver/resource, interpreter, metric-oracle, selection, assessment, scheduled-look, upstream and lifecycle/interface tests. These check policy identity, frozen population bindings, mandatory constraint matching, replay/objective certificate transfer, utility envelopes, historical scope/ledger/restatement, reserved fingerprints, disclosure and ownership. Existing CG1–CG4 interface tests check their public/artifact paths without rerunning their unchanged numerical suites.

Intermediate focused checks are retained. One early run found test setup omissions (owned API inspection and intentional conservative withholding); those fixtures were corrected. Another focused check showed the replay audit omitted the newly added nomination-coverage field; `_optimize_worker` now preserves it. A reviewer probe caught a variable-shadowing error introduced during tie-envelope cleanup; the early gate was interrupted, the error repaired and the affected exhaustive cases passed. A later gate was interrupted for the direct-helper memory-reservation correction, whose targeted regression passes. Interrupted logs are diagnostic records, not completed verification gates. Only the final frozen-source gate is the closure result.

**Remaining limitations and readiness**

- The global nomination envelope can be larger than a family's local tie set. Large relative tolerances can require the entire finite family. Existing shared operation, solver, time, matrix and memory limits still apply; exhausted limits yield incomplete standing or an atomic admission refusal.
- Certificates concern registered finite encodings and the recorded SciPy/HiGHS floating-point profile. Mixed weighted nonlinear RMSE sums are refused; no generic nonlinear optimizer was added.
- Hybrid priority optimization does not claim a complete Pareto frontier. Sampled Pareto schedules remain sampled.
- Native unit text without a safe/explicit public label can withhold an otherwise valid claim. Its alpha is not recycled. Protected JSON retains the complete question.
- Statistical support still depends on true predeclared bounds, declared sampling/independence, observation/exposure and frozen populations. There is no causal, future-effectiveness, deployment or founder-acceptance claim. CG4's deferred research remains deferred.
- Earlier immutable analytical results retain their original identity and conclusions; this pass does not silently rewrite historical assessments. New assessments use the corrected dispatch. Newly projecting a protected result can produce a new public projection digest while preserving its origin binding.

**Ready for focused independent re-review of D1–D5.** The original five counterexamples have been reproduced and corrected, the focused interaction regressions pass, and the corrected source identity is fixed above. This is engineering readiness for review, not CG5 acceptance.
