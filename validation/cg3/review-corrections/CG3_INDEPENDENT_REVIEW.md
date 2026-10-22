# NUMEK ConfidenceGuard CG3 — Independent Technical Review

Date: 2026-10-21  
Review basis: user-uploaded `NUMEK_ConfidenceGuard_CG3_Technical_Review(1).zip`, `VERIFICATION_LEDGER(1).md`, CG3 methodology and current project documentation.  
**Decision: CORRECTIONS REQUIRED; CG3 independent acceptance remains open.**

## Independently executed checks

1. Review archive inventory verification: **PASS** — 388 manifest entries, SHA-256 and lengths matched (`python validation/cg3/verify_package.py --root .`).
2. Source-to-wheel parity: **PASS** — all 170 `src/confidenceguard` and `src/datatrust` runtime files/assets present in the wheel and byte-identical to the extracted sources.
3. Independent pinned arithmetic: **PASS** — 18 checks across binary, multiclass and regression sample reports (`python -m validation.cg3.reference --inputs examples/inputs --reports examples/reports`).
4. Inspected recorded browser screenshot and one shareable report PDF contact sheet; inspected example local/shareable JSON outputs, current documentation, core longitudinal source, historical inference and storage, and portions of history selection, service and disclosure code.
5. **Not independently rerun:** 798 repository tests, 43 CG3 tests, source-to-clean-wheel execution, DuckDB-powered reconstructions, lifecycle fault injection and browser journeys. These are Codex's recorded checks, not reviewer-executed checks. Local environment lacked required Flask and DuckDB; dependency installation was blocked by unavailable network DNS. This is an environment limit, not a project defect.

## Finding CG3-R1 — High: material-degradation direction is incorrect for several metrics

**Evidence:** `src/confidenceguard/longitudinal.py:547-553` defines `lower_better` using a small hardcoded list of larger-is-better metrics. `src/confidenceguard/history_contracts.py:356-359` admits arbitrary nonnegative material thresholds for named metrics.

This causes `balanced_accuracy`, `macro_f1_observed_classes`, `support_weighted_f1` and other higher-is-better measures to treat increasing values as adverse and decreasing values as non-adverse. Interval/set coverage requires nominal-level-aware interpretation rather than an unconditional lower-is-better policy. Signed bias should not receive a generic lower-is-better policy.

**Reproduction from the packaged multiclass-local example:**
- Balanced accuracy delta = **-0.023172**. Current computed adverse change = **-0.023172**, while decreased accuracy should be adverse.
- Macro F1 delta = **-0.028659**. Current adverse change = **-0.028659**.
- Support-weighted F1 delta = **-0.035279**. Current adverse change = **-0.035279**.

Configured positive materiality thresholds therefore fail to flag real deterioration for these metrics and may flag improvements instead.

**Requested correction:** Introduce an explicit, tested metric-direction/interpretation policy. Distinguish higher-is-better, lower-is-better, target/nominal-dependent and unsigned or absolute-change comparisons. Refuse unspecified materiality interpretations rather than defaulting every unrecognized metric to lower-is-better. Add tests for improvement/deterioration on accuracy, balanced accuracy, F1 variants, Brier/loss, regression signed bias and conformal coverage.

## Finding CG3-R2 — Medium: class-specific calibration measurements collapse in historical views

**Evidence:** `src/confidenceguard/longitudinal.py:98-104` (`_lookup`) creates a mapping indexed only by the metric string and retains its first measurement. `_temporal` and longitudinal comparison loops consume this mapping (`longitudinal.py:423-431`, `:525-526`).

The packaged `examples/reports/multiclass-local.json` includes **5 different `frozen_bin_ece` measurements** in `reference/overall`, tagged `class:class-0` through `class:class-4`, with different values. Yet the historical timeline contains only **1 `frozen_bin_ece` series** and its overall comparison has only **1 `frozen_bin_ece` contrast**, corresponding to the first class.

The underlying measurements are retained; the error affects comparison/trend completeness and can hide class-specific deterioration.

**Requested correction:** Use a stable metric identity including target, nominal, artifact/method identity and other applicable dimensions; compare only equivalent identities across windows; keep display labels and report references unambiguous. Test multiclass per-class ECE and multi-target/nominal uncertainty measurements.

## Finding CG3-R3 — Medium: all nonzero drift effects become investigation-priority findings

**Evidence:** `src/confidenceguard/longitudinal.py:607-609` produces `distribution_change` with priority `Investigation` whenever `ks_distance > 0` or `total_variation > 0`. No materiality threshold or prioritization evidence is applied at that step.

In real continuous or varying categorical samples, trivial differences are commonplace; this can swamp the investigation summary. The finding wording explicitly avoids claiming degradation, which is positive, but its prioritization is not evidence-sensitive.

**Requested correction:** Preserve every descriptive drift measure, but distinguish ordinary observed changes from materially prioritized investigation candidates. Use declared context-sensitive materiality or evidence-based ranking, with explicit no-threshold/no-confirmation state. Do not introduce universal PSI-style cutoffs or falsely imply a p-value.

## Important qualified findings, not new implementation failures

- **Temporal bootstrap:** Supplied qualification recorded AR(1) empirical coverage of **79% at nominal 90%** for n=300/L=5, versus **52%** for deliberately invalid IID. A larger n=1200/L=20 experiment recorded **86%**. This is negative method-qualification evidence, already disclosed by Codex. No general finite-sample coverage guarantee should be made, and inference should remain explicit, assumption-qualified and secondary to descriptive analysis.
- **Historical storage:** Codex records **7.29 GB** persistent use for **1 million binary opportunities** (748s recording, 382s reconstruction), and **2.67 GB** for **10,000 regression cases × 100 samples**. These are real cost/scale limitations, not independently timed performance here.
- **Shareable-report information loss:** In the packaged sample results, all three conservative-shareable projections contain zero detailed drift and zero mix entries, and one generic `joint_history_withholding` finding, despite richer local results. This may be an intentional conservative privacy design; do not weaken privacy to add detail. Product review should ensure the report remains useful in aggregate terms and explains why evidence was withheld.
- **Visual presentation:** One inspected binary shareable PDF contact sheet was legible but sparse, and an available browser screenshot shows raw comparison JSON. These are limited observations, not a complete UX/browser audit.

## Positive structural observations

The package genuinely contains a unified `confidenceguard` architecture, with dedicated history capture, selection, storage, inference, longitudinal orchestration, shared CLI/API/browser integration, immutable result handling and protected disclosure. The final review artifact includes substantive synthetic reproduction and recorded fault, statistical and workload evidence. Legacy compatibility/preservation evidence is provided, but was not independently rerun here.

## Closure recommendation

Conduct **focused corrections and targeted verification** for R1 and R2. R3 is a worthwhile prioritization correction in the same pass. Preserve all existing scope, historical artifacts, source baseline and the recorded qualification limits. Do not redo broad CG3 planning or unrelated tests. Supply changed source/affected evidence, and record what was actually rerun. Then perform the final understanding gate after independent review is accepted.

This review does not certify security, external statistical validity or production capacity. The ZIP's integrity and the executed reference checks passed, but **CG3 should not be independently accepted until the confirmed logic defects are corrected and verified.**
