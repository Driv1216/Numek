# Numek Current State

Last updated: 2026-06-15  
Current milestone: DataTrust V1  
Status: Milestone 3 dry-run preparation complete; human dry runs not started

## Current Objective

Turn the working DataTrust prototype into a credible, useful reliability report that can satisfy the V1 exit gate.

## What Currently Works

- Python `3.11.15` project environment installed in `.venv`
- Public Python API through `DataTrust`
- Click-based CLI
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
  - strong and review-only heuristic target leakage candidates with reasons
- Transparent sub-scores:
  - completeness
  - uniqueness
  - target balance
  - feature usability
  - leakage risk
- Explained guardrails for strong leakage, missing target labels, severe
  missingness, severe duplicates, and critical sub-scores
- Plain-language top-three risk summaries
- Jinja-based HTML report with six V1 sections
- Synthetic lending-style example dataset
- Generated example report
- Automated test suite
- Separate reproducible `validation/` workspace
- Prepared semantic-column UCI German Credit, Bank Marketing, and Adult CSVs
- Seven deterministic controlled Adult mutations
- Ten generated six-section validation reports with runtime measurements
- Reviewed leakage ledger covering every validation-corpus leakage flag
- Internal isolated Evidently OSS comparison on Adult
- Validation artifact checksum and acceptance verifier
- Separate `validation/dry_runs/` workspace with:
  - uninvolved technical-reviewer quickstart
  - sealed manual-first assessment template
  - technical dry-run evidence form
  - separate non-technical comprehension form
  - facilitator non-assistance and anti-anchoring instructions
  - objective pass/fail, pause, fix, and rerun rules
  - frozen practitioner-round evidence template
- Deterministic SHA-256 release-candidate creation and verification
- Cross-platform reviewer instructions for Windows PowerShell (`py -3.11`) and
  macOS/Linux (`python3.11`) with quoted paths and explicit environment
  executable paths
- Dataset and generated-report SHA-256 identity recorded across both dry runs
- Deterministic allowlist-only clean reviewer packet creation and verification
- Active frozen dry-run candidate `DRY_RUN_RC_002`
- Historical candidate `DRY_RUN_RC_001` preserved as an immutable superseded
  record

## Verified Commands

Run tests:

```bash
.venv/bin/python -m pytest -q
```

Latest verified result:

```text
23 passed
```

Both the project environment and isolated Evidently validation environment use
Python `3.11.15`.

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
- `validation/dry_runs/packets/DRY_RUN_RC_002_REVIEWER_PACKET.zip`
- `METHODOLOGY.md`
- `docs/NUMEK_MASTER_CONTEXT.md`
- `docs/AI_COLLABORATION_PROTOCOL.md`

## Current Limitations

- Supports classification only
- Supports CSV input only
- No real-user validation yet
- No benchmark proving findings match or exceed manual review
- Leakage detection is heuristic
- Leakage classifications still require domain review of feature availability
- No label-noise detection
- No drift detection
- No fairness analysis
- No model calibration analysis
- No JSON report output
- No demo notebook
- HTML report design is functional but not yet polished
- No practitioner-owned CSV validation runs yet
- No technical or non-technical dry run yet
- Windows instructions are prepared but have not yet been exercised by a human
  Windows reviewer

## Milestone 2 Evidence

- UCI German Credit: `1,000 x 21`, report in `0.016305s`
- UCI Bank Marketing: `45,211 x 17`, report in `0.087316s`
- UCI Adult: `48,842 x 15`, report in `0.087798s`
- All ten public and mutation reports contain all six V1 sections and complete
  in under `30s`
- All seven controlled mutation directional assertions pass
- Every leakage flag has a recorded reason and matching reviewed classification
- The corpus exposed and justified one narrow runtime correction:
  `previous_campaign_outcome` is review-only rather than strong leakage
- Evidently OSS `0.7.21` Adult DataSummaryPreset comparison completed in an
  isolated Python `3.11.15` validation environment in `0.433635s` and remains
  internal supporting evidence only

## Immediate Next Task

Conduct the two prepared Milestone 3 human dry runs against unchanged
`DRY_RUN_RC_002` using only `DRY_RUN_RC_002_REVIEWER_PACKET.zip`:

- verify the candidate and clean packet before and after each session
- run one uninvolved technical install/run dry run without founder assistance
- run one separate non-technical comprehension dry run with report only
- confirm both sessions reference the same unchanged generated-report SHA-256
- pause on any objective failure and make only the evidenced targeted fix
- proceed toward practitioner validation only if both dry runs pass on one
  unchanged candidate

## Milestone 3 Preparation Evidence

- Dry-run preparation verifier passes without executing human dry runs
- Clean Python `3.11` quickstart installation and CLI report generation verified
- Quickstart-generated report contains all six V1 sections
- `DRY_RUN_RC_001` is preserved unchanged as historical candidate record
  SHA-256 `9c7b8d7754557a1dc10694068e297d55c484ea374e40640bf1f111486faf0fe1`
- `DRY_RUN_RC_002` identifies `30` candidate files with aggregate SHA-256
  `b8511b890b7beed51ac190c5f2af167d784783fe474824e3b2c3e0e703eac434`
- Clean reviewer packet archive SHA-256:
  `4b2694e0458147a36847b3e8dfe3728c5c54b9f44b0cd81f6c9e5e653c6d4946`
- Packet verification confirms required files are present and prohibited
  reports, validation results/comparisons, internal docs, previous evidence,
  and virtual environments are absent
- Deterministic packet recreation produces the same archive SHA-256
- Clean packet installs and generates a report from paths containing spaces
- Active candidate and packet verification pass after preparation
- No profiling, scoring, risk, report-content, or runtime package behavior was
  changed during preparation
- No human dry-run outcome or practitioner evidence has been fabricated

## V1 Exit Gate

DataTrust V1 passes only when every approved Run, Runtime, Structure and Claims,
Finding Quality, Score Defensibility, and Shareability gate passes in one frozen
practitioner validation round. A `3/5` reviewer result or any gate-level failure
is a V1 failure that requires a fix and a new applicable validation round.
