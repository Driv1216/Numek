# DataTrust — Portfolio Project Brief

## What the project actually is

**One-sentence description:** DataTrust is a local-first Python package, command-line tool, and browser interface that audits classification CSV datasets and turns reliability checks into stakeholder-readable HTML and PDF evidence reports.

**Problem it solves:** ML and data teams often have raw profiling statistics but no concise, defensible way to explain whether a classification dataset is reliable enough to use, what its most important risks are, and what should be fixed next. DataTrust combines transparent diagnostics, scoring, guardrails, prioritized findings, and deterministic narrative into one shareable report.

**Current status:** Complete and founder-accepted baseline. The implemented classification workflow is stable and tested; no next product direction has been selected. The product is local-only, supports CSV classification datasets, and is not positioned as a formal certification tool.

## Exact technology stack used

### Languages

- Python 3.10+
- HTML and CSS in Jinja templates
- JSON and Markdown for validation artifacts and documentation

### Frontend

- Server-rendered HTML/CSS
- Jinja2 templates
- Flask-based, multi-stage local browser UI
- Print-specific A4 portrait and landscape report layouts

### Backend

- Python
- Flask 3+
- Click 8+ for the CLI
- A public Python API exposed through the `DataTrust` class

### Database

- None. DataTrust deliberately has no database, user accounts, saved history, or persistent server-side state.
- Active browser jobs are held in an in-memory job store and process-owned temporary directories, then deleted when a job is replaced or the UI process exits.

### AI/ML libraries and models

- pandas 1.5+ for CSV ingestion, profiling, aggregation, and deterministic dataset analysis
- No trained ML model is shipped or executed by DataTrust.
- No runtime LLM, embedding model, vector database, semantic-search system, or probabilistic ranking model is used.
- Evidently OSS 0.7.21 was used only in an isolated internal comparison, not as a runtime dependency.

### Infrastructure and DevOps

- Local-first execution on `127.0.0.1`
- Python packaging through `pyproject.toml` and setuptools
- Console entry point: `datatrust`
- pytest automated test suite
- Reproducible validation workspace with manifests, checksums, generated reports, mutation assertions, runtime measurements, and an acceptance verifier
- Git/GitHub repository configured at `github.com/Driv1216/Numek`

### Important tools and frameworks

- Flask
- Click
- pandas
- Jinja2
- WeasyPrint 69.x for native PDF generation
- pypdf in development tests for PDF verification
- pytest

## What I built

This was an individual project. I designed and implemented the product, profiling and scoring logic, browser workflow, CLI and Python interfaces, reporting system, security controls, test suite, validation corpus, and documentation myself.

### Major features and systems

- A dataset profiler for CSV classification data
- A guided browser workflow covering upload, validation, preview, target selection, target confirmation, report generation, results, HTML viewing/download, and PDF download
- A Click CLI for generating canonical HTML reports
- A public Python API for programmatic analysis and report generation
- Explainable target-column guidance that groups plausible outcome columns without automatically selecting one
- Automatic binary, multiclass, or single-class target detection
- Five transparent reliability sub-scores plus an uncapped evidence score and guardrailed final score
- A complete prioritized finding list and a backward-compatible top-three executive risk summary
- Deterministic narrative shared by the compact UI result and the full report
- Eight-section, stakeholder-readable HTML reporting with print-safe visuals and a landscape technical appendix
- Native PDF generation from the same canonical HTML artifact
- A reproducible validation pipeline using public datasets and controlled mutations

### Architecture decisions

- **Local-first and non-persistent:** CSVs never need to be uploaded to a cloud service. The UI binds only to loopback, stores work in a temporary process-owned directory, and removes it on shutdown.
- **One analysis core, three interfaces:** the Python API contains the analysis behavior; the CLI and Flask UI reuse that behavior rather than implementing separate scoring systems.
- **Canonical HTML artifact:** the report renderer produces one authoritative HTML report. Browser PDF output is derived from that exact HTML rather than built from a second report format.
- **Deterministic rather than generative:** findings, score effects, risk bands, recommendations, grammar, and narrative are rule-based and reproducible. No LLM is required to obtain the same report from the same data.
- **Evidence separated from judgment:** observations such as conflicting labels and review-only leakage prompts are surfaced without silently penalizing the score.
- **Guardrails separated from evidence score:** DataTrust exposes the average sub-score as `evidence_score`, then applies explained caps to produce the final `overall` score when severe risks would otherwise contradict a healthy-looking average.
- **Backward-compatible result shape:** existing `profile`, `scores`, and top-three `risks` outputs were retained while complete `findings`, sanitized `context`, and deterministic `narrative` were added.

### Backend and API work

- Implemented the `DataTrust` Python API for analysis and HTML report generation.
- Implemented two CLI subcommands: `datatrust audit` and `datatrust ui`.
- Implemented 10 Flask routes across the local workflow:
  - `GET /`
  - `POST /upload`
  - `GET|POST /configure`
  - `GET /confirm`
  - `POST /generate`
  - `GET /result`
  - `GET /report`
  - `GET /download`
  - `GET /download/pdf`
  - `POST /new`
- Added explicit validation and actionable errors for missing files, non-file paths, empty CSVs, malformed CSVs, unreadable encodings, invalid targets, empty targets, unsupported tasks, stale jobs, oversized uploads, and missing reports.

### Database work

- No database was required by the product architecture.
- Built a process-scoped `JobStore` for active jobs, backed by isolated temporary directories and automatic cleanup.

### ML/AI work

- Built deterministic classification-dataset profiling and target analysis rather than a predictive model.
- Calculated class distributions, class count, majority-class baseline, majority-to-minority ratio, and binary/multiclass/single-class subtype.
- Implemented feature profiling for missingness, cardinality, constants, near-constants, numeric distributions, non-finite values, and IQR outliers.
- Implemented token- and phrase-aware target-leakage heuristics with separate strong and review-only classifications.
- Implemented transparent scoring for completeness, uniqueness, target balance, feature usability, and leakage risk.
- Built controlled mutation tests to verify that specific data problems cause the intended directional changes in scores, findings, and guardrails.
- Used an isolated Evidently comparison to document overlap and differences without making unsupported superiority claims.

### Security and privacy work

- Bound the Flask server to `127.0.0.1` only.
- Kept datasets and reports in process-owned temporary storage with cleanup.
- Generated a random 32-byte Flask secret key at process start.
- Added session-bound anti-CSRF form tokens and constant-time token comparison for every POST request.
- Restricted uploads to `.csv` filenames and enforced a configurable upload cap, defaulting to 100 MiB.
- Normalized and length-limited source filenames and used Werkzeug `secure_filename` for downloads.
- Escaped report metadata through Jinja templating.
- Restricted PDF rendering to local report resources and rejected remote resources.
- Disabled debug mode and source-code reloading in the local UI.

### Unusually difficult parts

- Designing a score that stayed transparent while preventing severe issues from being hidden by healthy averages. This led to the two-stage evidence-score and explained-guardrail design.
- Distinguishing strong leakage evidence from fields that merely deserve human review. For example, validation showed that `previous_campaign_outcome` describes a prior campaign and should be review-only rather than automatically treated as current-target leakage.
- Keeping cell-level missingness, row-level impact, and target-label missingness separate so each tells the correct story and affects scoring appropriately.
- Detecting exact duplicate records separately from feature-identical rows with conflicting labels; the latter may indicate label problems, repeated entities, temporal changes, or omitted context and therefore remains evidence-only.
- Producing one report that works for both non-technical decision-makers and technical reviewers, including portrait decision pages, print-safe charts, and a landscape technical appendix.
- Making HTML and PDF output consistent by deriving the PDF from the canonical HTML while safely handling local resources and platform-specific WeasyPrint failures.

## Numbers and measurable evidence

All numbers below are taken from the repository, generated validation artifacts, or the current automated test run.

| Measure | Defensible result |
|---|---:|
| Automated tests | 70 passing |
| Latest local test runtime | 2.13 seconds |
| Local web routes | 10 route definitions covering 11 method/path combinations |
| CLI subcommands | 2 |
| Supported product interfaces | 3: browser UI, CLI, Python API |
| Transparent sub-scores | 5 |
| Implemented guardrail conditions | 8 |
| Supported prioritized finding types | 14 issue types plus 1 clean-state finding |
| Report sections | 8 |
| Public validation datasets | 3 |
| Controlled dataset mutations | 8 |
| Generated validation reports | 11 |
| Controlled mutation assertions | 8/8 passing |
| Largest validation dataset | 48,842 rows and 15 columns |
| Total rows across the three public datasets | 95,053 |
| Default local upload limit | 100 MiB, configurable |
| Executive risk summary | Top 3 findings, with the complete ordered list also retained |
| Classification states | 3: binary, multiclass, single-class |
| Final risk bands | 4: Low, Moderate, Elevated, High |

### Public validation results

| Dataset | Shape | DataTrust runtime | Final score | Risk band |
|---|---:|---:|---:|---|
| UCI German Credit | 1,000 × 21 | 0.027824 s | 91.84 | Low |
| UCI Bank Marketing | 45,211 × 17 | 0.182619 s | 69.0 | Elevated |
| UCI Adult | 48,842 × 15 | 0.184440 s | 69.0 | Elevated |

All 11 public and mutation reports contained all eight required report sections and completed in under 30 seconds. These runtime figures are descriptive validation measurements, not production benchmarks.

### Controlled mutation results

- **100% feature missingness:** feature-usability score changed from 98.86 to 95.86 and triggered severe-missingness and critical-sub-score guardrails.
- **Duplicate injection:** uniqueness changed from 99.89 to 90.62.
- **Target imbalance:** target-balance score changed from 47.86 to 2.66.
- **Strong leakage:** leakage-risk score changed from 100.0 to 60.0 and triggered the strong-leakage and critical-sub-score guardrails.
- **Review-only leakage:** leakage-risk score remained 100.0, confirming that evidence-only review prompts do not penalize the score.
- **Missing targets:** triggered missing-target-label and critical-sub-score guardrails while keeping target missingness separate from dataset completeness.
- **Constant field:** feature-usability changed from 98.86 to 98.13.
- **Conflicting labels:** surfaced a conflicting-label finding while uniqueness remained unchanged at 99.89.

### Real problems found in validation data

- **Adult:** detected 5 feature-identical groups containing conflicting non-missing labels across 10 rows; this was surfaced as evidence without changing uniqueness.
- **Adult:** detected 49 exact duplicate groups and target imbalance with a 76.07% majority-class baseline and a 3.18:1 majority-to-minority ratio.
- **Bank Marketing:** detected target imbalance with an 88.3% majority-class baseline and a 7.55:1 majority-to-minority ratio.
- **Bank Marketing:** initially flagged `previous_campaign_outcome` as strong leakage. Domain review of the UCI field definition showed it referred to a previous campaign, leading to a narrow, evidence-backed correction: explicitly prior or historical outcome fields are now review-only.
- **German Credit:** identified IQR-based outlier concentration in `duration_months` and `credit_amount`, while producing a 91.84 Low-risk score with no guardrail applied.

## Every current dataset check

### Dataset-level checks

- CSV existence, file type, parsability, encoding readability, non-empty rows, and named columns
- Row count, column count, and feature count
- Numeric and non-numeric feature counts
- Total missing cells and overall cell-level missingness rate
- Rows containing at least one missing feature
- Counts of rows with exactly one, exactly two, or at least three missing features
- Exact duplicate-row count and rate
- Exact duplicate-group count and largest duplicate-group size
- Feature-identical groups with multiple non-missing target labels and the number of rows involved

### Target and label checks

- Target existence and usable-label validation
- Labeled-row count
- Missing-target count and rate
- Class values, counts, and percentages
- Class count
- Binary, multiclass, or single-class subtype
- Majority-class baseline
- Largest- and minority-class percentages
- Majority-to-minority ratio
- Target-column suitability guidance for the browser selector

### Column and feature checks

- Data type and numeric/non-numeric classification
- Feature-versus-target role
- Missing count and rate
- Non-null count
- Unique count and rate
- Constant-column detection
- Near-constant detection at the current 95% most-common-value threshold
- High-cardinality categorical detection
- Most-common value, count, and rate, with sensitive high-cardinality display suppression
- Numeric minimum, first quartile, median, third quartile, and maximum
- Zero count and rate
- Negative-value count and rate
- Positive and negative infinity counts
- IQR-based numeric outlier count and rate
- Strong target-leakage name candidates
- Review-only leakage name candidates
- Human-readable reasons for every leakage classification

## What affects scoring versus what is evidence-only

### Inputs that directly affect the five sub-scores

- **Completeness:** average cell-level missingness across the dataset
- **Uniqueness:** exact duplicate-row percentage
- **Target balance:** deviation of the largest class from an even distribution
- **Feature usability:** severe missingness, constant fields, near-constant fields, high-cardinality categorical fields, and IQR outlier concentration
- **Leakage risk:** strong outcome-like leakage candidates only

### Conditions that can cap the final score

- Strong leakage candidate: cap at 49
- Single-class target: cap at 49
- No feature columns: cap at 49
- Missing target labels: cap at 69
- Feature columns with at least 50% missingness: cap at 69
- Duplicate-row rate of at least 10%: cap at 69
- Dataset-wide missing-cell rate of at least 25%: cap at 69
- Any sub-score at or below 50: cap at 69

### Evidence-only checks

- Row-level feature-missingness reach and one/two/three-plus missing-feature buckets
- Exact duplicate-group count and largest duplicate-group size beyond their duplicate-rate contribution
- Feature-identical groups with conflicting non-missing target labels
- Classification subtype
- Majority-class baseline and majority-to-minority ratio beyond the target-balance calculation
- Per-column non-null and most-common-value shares beyond explicit feature-usability rules
- Numeric quartiles, zero/negative rates, and non-finite counts
- Review-only leakage prompts
- Target-selection guidance; it changes neither findings nor scores

Evidence-only does not mean unimportant. It means the tool shows the observation and asks for review without claiming it is always harmful or automatically changing the score.

## Dataset and report pipeline

1. The UI or API validates and loads a comma-delimited CSV with pandas.
2. The browser upload stage previews the first 10 rows and assesses every column as a possible classification target.
3. The user explicitly selects the target; DataTrust never chooses it automatically.
4. The tool validates usable labels and deterministically confirms binary, multiclass, or single-class classification.
5. The profiler computes dataset-, row-, target-, duplicate-, leakage-, and column-level evidence.
6. The scoring layer calculates five sub-scores and their uncapped mean.
7. Explained guardrails cap the final score when severe conditions are present.
8. The findings layer creates a stable, prioritized action list and top-three executive summary.
9. The narrative layer creates deterministic stakeholder wording from the same analysis object.
10. Jinja renders the canonical, standalone eight-section HTML report.
11. In the browser UI, WeasyPrint converts that canonical HTML artifact into a cached native PDF for download.
12. The temporary job directory is removed when a new analysis replaces it or the process exits.

## UI, API, and CLI coverage

### Browser UI

- Local upload with a configurable size limit
- CSV validation and 10-row preview
- Grouped, explainable target choices with no preselection
- Server-enforced acknowledgement for advanced target choices
- Automatic classification-subtype confirmation
- Optional dataset name and prediction purpose
- Compact reliability result with top-three risks
- Full report view
- Standalone HTML download
- Native PDF download
- Start-new-analysis cleanup flow

### Python API

- `DataTrust(...).analyze()` returns the profile, five sub-scores, evidence and overall scores, guardrails, top-three risks, complete ordered findings, sanitized context, and deterministic narrative.
- `DataTrust(...).generate_report(path)` writes the canonical HTML report.

### CLI

- `datatrust audit <csv> --target <column> --task classification --out <report.html>`
- Optional `--name` and `--purpose` report context
- `datatrust ui` with configurable port, upload limit, and browser-opening behavior

## PDF and report generation

- The report contains eight topics: Decision Summary, Priority Actions, Dataset Overview, Target and Label Evidence, Missingness Evidence, Duplicate and Feature Evidence, Scoring/Methodology/Limitations, and Technical Appendix.
- Main report pages use A4 portrait layout; the technical appendix uses A4 landscape.
- Includes print-safe target-distribution and feature-missingness visuals.
- Long feature names receive safe wrap points for robust layout.
- Report context is escaped, fallback names are humanized, and clean datasets receive an intentional empty state rather than a fabricated warning.
- PDF output is produced with WeasyPrint's native `HTML.write_pdf()` pipeline from the canonical HTML report.
- Remote report resources are rejected during PDF rendering.
- PDF generation failures are reported actionably without destroying the already-generated HTML report.

## AI/ML depth

### Algorithms and models used

- No predictive model is trained by the product.
- Deterministic statistical profiling and rule-based risk synthesis are the core algorithms.
- Target balance is scored from the largest-class deviation from an even class distribution.
- Numeric outliers use the interquartile-range rule.
- Leakage detection uses normalized tokens, phrase matching, outcome qualifiers, prior/historical qualifiers, and overlap with target-name terms.
- Target guidance uses structural properties such as distinct counts, distinct rate, label availability, outcome-word signals, identifier-like behavior, and continuous-looking or many-category behavior.

### Embeddings, semantic search, and ranking

- No embeddings or semantic-search model is used.
- Findings are prioritized with a deterministic ordering and severity tie-break, not learned ranking.
- Target options are deterministically grouped and ordered while preserving source-column order; the system does not predict or preselect the target.

### Preprocessing and feature engineering

- CSV parsing and dtype inference through pandas
- Missing-value separation for target versus feature analysis
- Tokenization and normalization of column names, including phrase-aware leakage checks
- Per-row missing-feature bucket construction
- Duplicate grouping across complete rows and separate grouping across feature-only values
- Numeric quartile, non-finite, zero, negative, and IQR-outlier summaries
- No model-training feature matrix or learned feature engineering is produced.

### Model evaluation

- DataTrust evaluates datasets, not trained models, so accuracy, F1, ROC-AUC, and calibration metrics do not apply to the current product.
- It surfaces majority-class baselines and imbalance ratios to warn when headline accuracy could be misleading.
- The implementation itself is evaluated through automated behavior tests, controlled mutation assertions, public-data reports, reviewed leakage classifications, artifact verification, and an internal adjacent-tool comparison.

### LLM usage

- No LLM is part of the application runtime or report-generation pipeline.
- Report narrative is deterministic and template-driven, ensuring repeatable output and preventing generated claims that are not backed by computed evidence.

## Why this is not a CRUD, tutorial, or basic college project

- It has no CRUD database at all; its core value is an auditable analysis and synthesis pipeline.
- It distinguishes observations, score inputs, guardrails, and human-review prompts instead of collapsing every warning into one opaque score.
- It solves subtle reliability problems such as conflicting labels among feature-identical rows, target-label missingness versus feature missingness, and strong versus review-only leakage evidence.
- It serves three interfaces from one analysis core while maintaining backward-compatible API behavior.
- It generates stakeholder-facing and technical evidence layers from the same deterministic result object.
- It includes deliberate privacy and security boundaries for local data handling.
- It has a separate reproducible validation corpus, controlled fault injection, reviewed leakage ledger, checksums, generated artifacts, and acceptance verification.
- A real validation finding caused a narrow domain-aware correction to leakage logic, demonstrating that the methodology was tested against real dataset semantics rather than only synthetic happy paths.

## Validation and quality

### Automated testing

- 70 tests pass in the current environment (`70 passed in 2.13s`).
- Coverage includes the profiler, scoring, guardrails, findings, narratives, deterministic wording, target guidance, HTML reports, PDF security and output, CLI behavior, Flask UI workflows, upload limits, stale sessions, error handling, cleanup, and validation mutations.

### Validation datasets

- UCI German Credit: 1,000 rows × 21 columns
- UCI Bank Marketing: 45,211 rows × 17 columns
- UCI Adult: 48,842 rows × 15 columns
- Eight deterministic Adult mutations targeting specific reliability failures
- Prepared datasets, source metadata, checksums, mutation manifests, runtime measurements, generated reports, and machine-readable assertion results are retained in the repository.

### Manual and real-world validation

- Every leakage flag in the validation corpus has a recorded reason and reviewed classification.
- The Bank Marketing review produced one evidence-backed implementation correction for prior-campaign outcome fields.
- A completed, founder-accepted RC_003 technical review is retained as historical evidence, including generated reports and reviewer notes.
- Validation on private practitioner-owned datasets and independent external comprehension remain documented open questions, not completed claims.

### Security testing

- Tests cover invalid form tokens, stale jobs, upload limits, invalid extensions, empty CSVs, missing labels, invalid targets, unavailable reports, remote PDF resources, and PDF-rendering failure recovery.

### Browser testing

- Flask test-client coverage exercises the complete local UI workflow, grouped target selection, advanced-choice acknowledgement, subtype confirmation, result display, HTML/PDF downloads, errors, and cleanup.
- No claim is made for automated cross-browser testing through Chrome, Firefox, and Safari.

### Stress and concurrency testing

- The product is intentionally a single-user, non-persistent local application and starts Flask with `threaded=False`.
- No concurrency-load or stress-test result is claimed.
- Runtime validation covers datasets up to 48,842 rows and 15 columns, and the UI enforces a configurable 100 MiB upload limit.

## Links and project status

- **GitHub:** `https://github.com/Driv1216/Numek` is configured as the repository remote. The local repository does not establish whether the GitHub repository is currently public or private, so visibility should be confirmed before publishing this portfolio entry.
- **Deployment:** Local-only; no hosted production deployment is claimed.
- **Demo:** The repository includes `examples/loan_data.csv` and a generated `examples/report.html`. The local browser demo can be started with `datatrust ui` after installation.
- **Team:** Individual project; all product, engineering, validation, and documentation work described here is mine.

## Honest current limitations

- Classification only
- CSV input only
- Single-user and non-persistent local UI
- PDF output through the browser UI only; CLI and Python API produce HTML
- Heuristic leakage detection still requires domain review
- No label-noise detection
- No drift detection
- No fairness or bias analysis
- No model calibration analysis
- No JSON report output, Word export, or demo notebook
- No trained ML model, embeddings, vector search, or runtime LLM
- WeasyPrint may require native system libraries depending on the operating system

## Concise résumé-ready version

**DataTrust | Python, Flask, pandas, Click, Jinja2, WeasyPrint, pytest**

- Built a local-first classification-dataset reliability auditor with browser, CLI, and Python interfaces, generating deterministic eight-section HTML reports and native PDFs without cloud uploads or persistent storage.
- Designed five transparent quality sub-scores and eight explained score guardrails covering missingness, duplicates, class imbalance, feature usability, and heuristic target leakage.
- Implemented 14 prioritized issue types plus a clean-state result, including evidence-only detection for feature-identical rows with conflicting labels and review-only leakage prompts.
- Validated the system with 70 passing tests, three UCI datasets totaling 95,053 rows, eight controlled data mutations, and 11 generated reports; all mutation assertions passed.
- Measured report generation at 0.028–0.184 seconds across public datasets up to 48,842 rows, while documenting the results as validation measurements rather than production benchmarks.
- Secured the local workflow with loopback-only binding, temporary process-scoped storage, anti-CSRF tokens, upload limits, sanitized filenames, automatic cleanup, and remote-resource rejection during PDF rendering.
