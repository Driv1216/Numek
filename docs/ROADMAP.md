# Numek Roadmap

Last updated: 2026-08-05
Current phase: Phase 1 - DataTrust product building and internal verification

## Current Objective

Make DataTrust useful enough as a local-first dataset reliability product to
keep building from real product behavior, not from a mandatory external review
process.

## Phase 1: DataTrust V1 Usable Report

Status: In progress

Priorities:

1. Complete correctness and trust invariants. **Completed 2026-06-14.**
2. Build a reproducible validation corpus using UCI German Credit, Bank
   Marketing, and Adult plus controlled mutations and runtime measurements.
   **Completed 2026-06-14.**
3. Run one internal adjacent-tool comparison as supporting evidence.
   **Completed 2026-06-14.**
4. Freeze RC_003 and complete a technical review. **Completed and archived as
   historical evidence.**
5. Implement the local report-generation UI and evidence-first report upgrade.
   **Implemented and internally verified 2026-08-05; founder acceptance pending.**

Exit gate:

- Local UI, CLI, and Python API generate a complete HTML report from a CSV
  classification dataset
- all eight report sections are present
- automated tests for implemented V1 behavior pass
- public validation reports and controlled mutation checks remain reproducible
  enough for internal confidence
- product and docs avoid unsupported certification, compliance, fairness,
  label-noise, drift, model-correctness, or legal claims
- Drivyaansh accepts the product state after Codex verification

Removed from the active exit gate:

- mandatory five-practitioner external validation
- `4/5` reviewer thresholds
- required practitioner-owned CSV runs
- required non-technical comprehension dry run
- frozen external validation round as a blocker to product work

Current Phase 1 evidence:

- package metadata allows Python `>=3.10`
- three public datasets and eight controlled mutations generate complete
  eight-section reports in under `30s`
- all controlled mutation directional assertions pass
- every corpus leakage flag has a reviewed classification
- one internal Evidently `0.7.21` Adult DataSummaryPreset comparison is complete
- historical dry-run candidate `DRY_RUN_RC_001` is preserved
- historical dry-run candidate `DRY_RUN_RC_002` is preserved
- historical dry-run candidate `DRY_RUN_RC_003` and its allowlist-only clean
  reviewer packet are preserved as historical evidence
- RC_003 technical review has been completed and archived by founder decision

Deferred, non-blocking evidence questions:

- whether ML/data leads would use or forward the report
- whether local-first setup is a selling point or friction
- whether current scoring weights feel right to domain experts
- whether HTML is sufficient for external stakeholder workflows
- whether lending-tech is the best first segment

Blocked future work:

- generated PDF export beyond the implemented browser print/save path
- hosted SaaS or dashboard
- JSON output
- demo notebook unless setup evidence requires it
- regression or multilabel support
- production monitoring
- ConfidenceGuard implementation
- HallucinationGuard implementation

## Phase 2: Stronger Dataset Checks

Status: Not started; starts only after Drivyaansh accepts the V1 product state

Potential work:

- stronger leakage detection
- suspicious identifier detection
- missingness pattern analysis
- temporal data checks
- optional Cleanlab label-issue workflow
- richer domain-specific recommendations

## Phase 3: Optional Model Prediction Analysis

Status: Not started; blocked by earlier product phases

Potential work:

- calibration metrics
- Brier score
- reliability diagrams
- high-confidence wrong predictions
- threshold sensitivity

## Phase 4: ConfidenceGuard

Status: Not started; strategic future phase

Goal:
Verify whether model confidence, calibration, and behavior remain reliable during real-world deployment.

## Phase 5: HallucinationGuard

Status: Not started; strategic future phase

Goal:
Verify whether LLM outputs are grounded, supported, and safe to trust.

## Phase 6: Broader Numek Reliability Platform

Status: Long-term vision

This phase is earned only after earlier products prove demand.
