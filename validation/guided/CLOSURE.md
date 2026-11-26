# Guided Analysis & Evidence Intelligence: closure matrix (Stage 7, 2026-11-25)

This document maps each row of the plan's verification matrix (§O) to its evidence. Stage notes are in `README.md` in this folder. Nothing is committed.

## Per workflow

| Workflow | Guided configuration | Analytical usefulness | Evidence |
|---|---|---|---|
| Classification | **Met.** Reachable from an intent and from Start from a CSV. Target never preselected. Recommended layer has the prediction point and availability, with the consequence stated. Bulk availability needs a confirmation. A role-aware switch states the method. | **Met.** Guidance parity with the report. The summary states availability status first. Scored JSON unchanged. | `test_app_api.py`; Stage 4b; this walkthrough (Start → dashboard → report) |
| Numerical outcome | **Met.** Ranked targets from the whole file. Expectations form and availability. | **Met.** J2: opt-in `regression_dependency_v1`; off byte-identical on 33 cases; on gives the dossier's 4 flags. | `test_input_suggestions.py`, `test_regression_dependency.py` |
| Profile / roles | **Met.** Profile needs no target. A switch to profile with chosen columns names the method. | **Partly met.** The clean-result panel states its scope. "Next analyses" is on the Start page, not in the clean panel. | Stage 4a, Stage 2 |
| Partially labelled | **Met.** Status suggestion (R-STATUS-1) and plain expectation wording (layered). | **Partly met.** No dedicated cohort-contrast sentence. Guidance carries the existing wording. | Stage 4b |
| Several outputs | **Partly met.** Targets suggested from the whole file. Expectations are still JSON under Advanced. | **Met.** Per-output J2 blocks under a shared budget. | `test_regression_dependency.py` |
| Multilabel | **Partly met.** R-MULTI-1 indicator chips. Constraints are still JSON under Advanced. | **Not met.** Cardinality and density are not named in the summary. | Stage 4b |
| Readiness | **Met.** Identifier and free-text chips (ignored). The scale question is explained. | **Met.** J3 readiness v2: coverage and redundancy, bounded, "may be intended", no verdict. Pre-registered cases match. | `test_readiness_v2.py`, `readiness_v2_expectations.md` |
| Split audit | **Met.** Key chips (R-KEY-1). Intent in plain words. Columns that don't align are listed before the run. | **Met.** The separation verdict leads. J1: increases unchanged, decreases recorded as material change. | `test_source_suggestions.py`, `test_comparison_direction.py`; Stage 5a walkthrough (run to High violation) |
| Versions / before-after | **Partly met.** Name-mapping chips (R-MAP-1). Transformations are still JSON. | **Met.** "Changed is not worse" and "fewer findings is not improvement". | Stage 2, Stage 5a |
| Advanced (one large file) | **Not met.** No constraint table; JSON only. | **Met.** Interpretation only, as planned. | n/a |
| Temporal | **Met.** Question-led layers; clock, entity and spacing chips, never applied. | **Met.** Violations come before candidates, which are "not validated defect criteria". | `test_source_suggestions.py` (chip-built spec runs to completion) |
| Text | **Met.** Selector discovery chips. Presets named by objective. | **Met.** Report-order actions; bounded clean summary. | `test_source_suggestions.py`; Stage 5b walkthrough |
| Images | **Met.** Guided comparison and multilabel presets. Box evidence shown, never chosen. | **Partly met.** The annotation-completeness limit comes only from the existing guidance. | `test_source_suggestions.py`; Stage 5b walkthrough |
| Records and documents | **Met.** Key chips. Honest model status (stale, so abstain) shown before selection. | **Met.** Rule outcomes lead; abstention shown. | `test_source_suggestions.py`; Stage 5b walkthrough |

## Global checks

| Check | Status | Evidence |
|---|---|---|
| Methodology on Review equals the recorded methodology | **Met** for every core and M3 mode, including the role-aware switch. | `test_app_api.py::test_the_review_names_the_methodology_the_run_records` |
| Inspection never alters specifications or fingerprints | **Met.** | `test_app_api.py` path parity (9 modes); `test_source_suggestions.py` |
| Ambiguous inputs stay unconfirmed | **Met.** `03/04/2024` dates are never a clock. Several plausible targets are all listed, none preselected. | `test_inspection.py`, `test_input_suggestions.py` |
| No dashboard text contradicts the report | **Met.** One `interpret()` for both. | `test_interpretation.py`, `test_report_interpretation.py` (74 cases) |
| Historical results unchanged, never back-filled | **Met.** Saved report bytes are served as stored. v1 method ids render unchanged. | `test_interpretation.py`; the history serving path |
| CLI and API parity for J changes | **Met.** `--regression-dependency-search`, `ComparisonConfig.methodology`, and the readiness v2 default. | `test_regression_dependency.py`, `test_comparison_direction.py` |
| Revealed content never persists | **Met** (Stage 1 re-drive). | Stage 1 notes |
| Identity preserved: Deep Water, Modules, typography | **Met.** Visual captures at 1440 and 375 px for each changed screen. | `work.nosync/guided/visual/stage4`, `stage5`, `stage6d` |
| Performance: inspection budget met | **Met.** 60 MiB full pass in 1.1 s; head reads 0.2 s. | Stage 3 notes |
| Full suite, plus M9 with CG1 | **Met.** 1,926 passed; M9 with CG1 80 passed. | Final runs |

## Integration walkthrough (Stage 7)

- **Classification, end to end** (fresh server with a data root):
  - Start → Start from a CSV → Category outcome → `churned` → Review ("classification_legacy_2026_08_13") → Generate → dashboard.
  - The served canonical report contains "In brief", and its four summary sentences all appear on the live dashboard.
- **Multi-source entry points:** each of the five intent links (comparison, temporal, text, images, records) opens its flow, with the right heading, from the Start page.
- **Other workflows**, Start to evidence, through earlier walkthroughs and API tests:

  | Workflow | Reached | Where |
  |---|---|---|
  | Numerical outcome | report | Stage 4a |
  | Role-aware classification | confirm | Stage 4b |
  | Split audit | report, with the violation | Stage 5a |
  | Temporal, text, image comparison, records | confirm | Stage 5a and 5b |
  | Temporal, text, image, records | completed run | each workflow's app API test |

- **Console:** CSP messages appeared after a check of mine parsed the report HTML inside the app page. Navigating every flow and the report afterwards added no new messages, and earlier fresh-tab walkthroughs logged none.

## Known gaps (follow-ups, not regressions)

- **Structured editors.** These remain JSON under Advanced:
  - M3 per-target expectations and multilabel constraints;
  - M4 declared transformations and advanced constraints;
  - image split-separation requirements.
- **Interpretation.** No multilabel cardinality and density sentence, and no partially-labelled cohort-contrast sentence.
- **6B presentation.** The dashboard has no table of the search's per-feature checks; the block is in the JSON and report.
- **Consequence ordering** of findings was not changed.
- **M9 model qualification** remains a separate founder decision. The app states that the models' qualification is stale.

## Final runs

- **DataTrust suite** (integration boundary 3): **1,926 passed**, 0 failed.
- **M9 with CG1:** **80 passed** (expected 80).
- **Frontend:** `npm run build:app` clean, with no external requests in the bundle.
