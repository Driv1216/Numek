# Numek Current State

Last updated: 2026-08-13
Current product baseline: Complete and founder-accepted
Status: DataTrust generates HTML reports through the local UI, CLI, and Python API, with native PDF download in the UI; no next product direction has been selected

## Current Objective

Preserve the completed DataTrust classification workflow as the current product
baseline. The next product objective is intentionally undecided and will be
recorded only after Drivyaansh chooses it. Technical review, product review, and
acceptance review are conducted internally by Drivyaansh and Codex unless
Drivyaansh explicitly requests a separate outside opinion for learning.

## What Currently Works

- Python package metadata now allows Python `>=3.10`
- Public Python API through `DataTrust`
- Click-based CLI
- Loopback-only Flask UI launched with `datatrust ui`
- Guided upload, grouped explainable target selection with no preselection and
  human-readable server-enforced acknowledgement for advanced choices,
  concise selector-specific reasons, automatically detected subtype confirmation,
  compact reliability overview, full HTML report viewing, and native PDF download
- Process-scoped temporary uploads with a configurable `100 MiB` default limit
- Editable installation exposes one `datatrust` command with `ui` and `audit`
  subcommands; a virtual environment is recommended but not required
- CSV ingestion for classification datasets
- Dataset profiling for:
  - shape and data types
  - missingness
  - duplicate rows
  - target class balance
  - constant and near-constant columns
  - high-cardinality categorical columns
  - numeric IQR outliers
  - separate target missingness and labeled-row counts
  - column-level severe missingness
  - row-level feature missingness impact
  - exact duplicate groups and feature-identical conflicting-label groups
  - binary/multiclass/single-class subtype, majority baseline, and class ratio
  - numeric quartiles, zeros, negatives, and non-finite values
  - non-null and most-common-value shares
  - strong and review-only heuristic target leakage candidates with reasons
- Transparent sub-scores:
  - completeness
  - uniqueness
  - target balance
  - feature usability
  - leakage risk
- Explained guardrails for strong leakage, missing target labels, severe
  missingness, severe duplicates, and critical sub-scores
- Additive uncapped `evidence_score` alongside the unchanged guardrailed
  `overall` score
- Plain-language top-three risk summaries and complete prioritized findings
- One deterministic narrative shared by the compact result and report
- Deterministic singular/plural wording across browser, finding, narrative, and
  guardrail copy without changing diagnostic or scoring behavior
- Minimal-before-concentrated missingness language with a narrative-only `1%`
  feature-cell threshold
- Humanized fallback report titles and an intentional clean-report empty state
- Layered eight-topic HTML report with stacked finding blocks, portrait decision
  pages, two print-safe evidence visuals, and a landscape technical appendix
- WeasyPrint-based PDF conversion from the canonical HTML report, cached inside
  the active temporary job and restricted to local report resources
- Synthetic lending-style example dataset
- Generated example report
- Automated test suite with profiler, report, CLI, and Flask UI coverage
- Separate reproducible `validation/` workspace
- Prepared semantic-column UCI German Credit, Bank Marketing, and Adult CSVs
- Eight deterministic controlled Adult mutations
- Eleven generated eight-section validation reports with runtime measurements
- Reviewed leakage ledger covering every validation-corpus leakage flag
- Internal isolated Evidently OSS comparison on Adult
- Validation artifact checksum and acceptance verifier
- Historical `validation/dry_runs/` workspace with RC_003 technical-review
  materials, reviewer packet tooling, and release-candidate archive records
- Historical candidates `DRY_RUN_RC_001`, `DRY_RUN_RC_002`, and
  `DRY_RUN_RC_003` preserved as immutable records
- `DRY_RUN_RC_003` reviewer packet archive and manifest preserved as historical
  technical-review evidence

## Verified Commands

Run tests:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src .venv/bin/python -B -m pytest -q -p no:cacheprovider
```

Latest verified result:

```text
70 passed
```

Generate the sample report:

```bash
.venv/bin/datatrust audit examples/loan_data.csv --target default --task classification --out examples/report.html
```

## Current Artifacts

- `examples/loan_data.csv`
- `examples/report.html`
- `validation/README.md`
- `validation/data/prepared/`
- `validation/data/mutations/`
- `validation/reports/`
- `validation/results/MILESTONE_2_SUMMARY.md`
- `validation/comparison/ADULT_COMPARISON.md`
- `validation/dry_runs/README.md`
- `validation/dry_runs/release_candidates/DRY_RUN_RC_001.json`
- `validation/dry_runs/release_candidates/DRY_RUN_RC_002.json`
- `validation/dry_runs/release_candidates/DRY_RUN_RC_003.json`
- `validation/dry_runs/packets/DRY_RUN_RC_003_REVIEWER_PACKET.zip`
- `validation/dry_runs/evidence/`
- `METHODOLOGY.md`
- `docs/NUMEK_MASTER_CONTEXT.md`
- `docs/AI_COLLABORATION_PROTOCOL.md`

## RC_003 Technical Review Status

RC_003 has completed its founder-accepted technical review and is now
historical evidence, not an active gate.

Returned reviewer evidence received on 2026-08-04 includes:

- manual-first assessment text for dataset alias `spam.csv`
- reviewer-recorded target column `Category`
- reviewer-recorded independent risk band `Low`
- reviewer note: data looked proper, with high class imbalance as the main issue
- generated report file received locally as `spam_report (1).html`
- additional generated report file received locally as `train (1).html`

Important evidence caveat:

- The returned form records `Reviewer ID: 123` and `Candidate ID: 123`.
- It does not record the formal `DRY_RUN_RC_003` candidate ID.
- Historical SHA-256 fields from the old form were left blank.
- Therefore this evidence is preserved as a completed technical review record
  accepted by Drivyaansh, not as a formal sealed protocol artifact.

This caveat does not require another external technical review. The approved
decision is to move forward with product building and internal verification.

## Current Limitations

- Supports classification only
- Supports CSV input only
- Local UI is single-user and non-persistent
- Native PDF download is available in the browser UI only; CLI and Python API
  output remain HTML-only, and Word output is not implemented
- WeasyPrint may require documented native font/rendering prerequisites on
  some operating systems
- Development reloading is intentionally disabled; source/template changes
  require restarting `datatrust ui`
- Leakage detection is heuristic
- Leakage classifications still require domain review of feature availability
- No label-noise detection
- No drift detection
- No fairness analysis
- No model calibration analysis
- No JSON report output
- No demo notebook
- External product-validation questions remain unresolved, deferred, and
  non-blocking

## Validation Corpus Evidence

- UCI German Credit: `1,000 x 21`, report in `0.027824s`
- UCI Bank Marketing: `45,211 x 17`, report in `0.182619s`
- UCI Adult: `48,842 x 15`, report in `0.184440s`
- All eleven public and mutation reports contain all eight report sections and complete
  in under `30s`
- All eight controlled mutation assertions pass, including evidence-only
  conflicting-label detection with unchanged uniqueness
- Every leakage flag has a recorded reason and matching reviewed classification
- The corpus exposed and justified one narrow runtime correction:
  `previous_campaign_outcome` is review-only rather than strong leakage
- Evidently OSS `0.7.21` Adult DataSummaryPreset comparison completed in an
  isolated Python `3.11.15` validation environment in `0.433635s` and remains
  internal supporting evidence only

## Historical Dry-Run Evidence

- Dry-run preparation verifier passed without executing human dry runs
- Clean Python quickstart installation and CLI report generation were verified
- Quickstart-generated report contained all six report sections used at that time
- `DRY_RUN_RC_001` is preserved unchanged as historical candidate record
  SHA-256 `9c7b8d7754557a1dc10694068e297d55c484ea374e40640bf1f111486faf0fe1`
- `DRY_RUN_RC_002` is preserved unchanged as historical candidate record
  SHA-256 `cf73b1285439813fd4db501f442554eabe67cbea5222f8dcded69e3fee7644a0`
- `DRY_RUN_RC_003` identifies `30` candidate files with aggregate SHA-256
  `888cf3b30a82d44c11bb0bad0ddd5be94c5b4f5a97fcc2bc051533ff2b684b96`
- Clean reviewer packet archive SHA-256:
  `ba23513ff44493384bf057cd6235018d7c9e4a41a4e63134f21e075936b042cc`
- Packet verification confirmed required files were present and prohibited
  reports, validation results/comparisons, internal docs, previous evidence,
  and virtual environments were absent
- Deterministic packet recreation produced the same archive SHA-256
- Clean packet installed and generated a report from paths containing spaces
- Selected-interpreter workflow verified with matching environment Python,
  exact pip version, and complete post-install `pip freeze`
- No profiling, scoring, risk, report-content, or runtime package behavior was
  changed during RC_003 preparation
- RC_003 technical review is now completed and archived as historical evidence

## Immediate Next Task

No next product task has been selected. Do not infer one from the historical
roadmap, open questions, prior AI proposals, or older chats. The next objective
begins only after Drivyaansh explicitly chooses it.

For future development, the normal acceptance loop is:

1. Drivyaansh approves the objective.
2. Codex updates the implementation or docs.
3. Codex runs relevant tests and checks.
4. Drivyaansh and Codex review the result internally.
5. Living docs are updated when the verified project state changes.

Do not schedule or require a five-practitioner external validation round before
continuing product work.

## Completed Baseline

Drivyaansh has accepted the current DataTrust classification product state.
Codex verified that:

- the local UI, CLI, and Python API generate a complete HTML report from a CSV
  classification dataset, and the local UI can download that report as PDF
- the generated report contains all eight report sections
- automated tests for implemented behavior pass
- public validation reports and controlled mutation checks remain reproducible
  enough for internal confidence
- unsupported claims are absent from product and docs
- known limitations are documented clearly

External technical review, external product review, and the former
five-practitioner validation round were not acceptance requirements for this
completed baseline.
