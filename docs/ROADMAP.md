# Numek Roadmap

Last updated: 2026-06-15  
Current phase: Phase 1 - DataTrust V1 Usable Report

## Current Objective

Make DataTrust credible and useful enough to pass the V1 exit gate.

## Phase 1: DataTrust V1 Usable Report

Status: In progress

Priorities:

1. Complete correctness and trust invariants. **Completed 2026-06-14.**
2. Build a reproducible validation corpus using UCI German Credit, Bank
   Marketing, and Adult plus controlled mutations and runtime measurements.
   **Completed 2026-06-14.**
3. Run one internal adjacent-tool comparison as supporting evidence.
   **Completed 2026-06-14.**
4. Perform one uninvolved technical dry run and one separate non-technical
   comprehension dry run. **Preparation complete; human runs pending.**
5. Freeze a release candidate and run the approved practitioner validation
   round.

Exit gate:

- every approved V1 gate passes in one frozen validation round
- at least `4/5` ML/data reviewers install and run without founder intervention
- three public datasets and two practitioner-owned CSVs report in under `30s`
- finding quality, score defensibility, and shareability thresholds pass
- the separate non-technical reviewer passes all four comprehension questions

Current Phase 1 evidence:

- project and isolated validation environments are reproducible on Python
  `3.11.15`
- three public datasets and seven controlled mutations generate complete
  six-section reports in under `30s`
- all controlled mutation directional assertions pass
- every corpus leakage flag has a reviewed classification
- one internal Evidently `0.7.21` Adult DataSummaryPreset comparison is complete
- objective dry-run materials and facilitator rules are prepared outside
  runtime package code
- historical dry-run candidate `DRY_RUN_RC_001` is preserved
- historical dry-run candidate `DRY_RUN_RC_002` is preserved
- active dry-run candidate `DRY_RUN_RC_003` and its allowlist-only clean
  reviewer packet are frozen and hash-verifiable
- technical dry-run evidence captures the selected Python `>=3.11` command,
  exact environment Python/pip versions, and post-install dependency freeze
- practitioner-owned runs and all dry-run/practitioner gates remain pending

Blocked future work:

- PDF export unless users require it
- hosted SaaS or dashboard
- JSON output
- full visual redesign before dry-run evidence
- demo notebook unless setup evidence requires it
- regression or multilabel support
- production monitoring
- ConfidenceGuard implementation
- HallucinationGuard implementation

## Phase 2: Stronger Dataset Checks

Status: Not started; blocked by Phase 1 exit gate

Potential work:

- stronger leakage detection
- suspicious identifier detection
- missingness pattern analysis
- temporal data checks
- optional Cleanlab label-issue workflow
- richer domain-specific recommendations

## Phase 3: Optional Model Prediction Analysis

Status: Not started; blocked by earlier phases

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
