# NUMEK Resume Evidence Audit

Audit date: 30 October 2026. Scope: the available local repository, all ten reachable commits on `main`/`origin/main`, current tracked modifications and relevant untracked implementation/evidence. This is a source-and-artifact audit, not a fresh execution certification.

**Assessment:** NUMEK has credible depth as a local data/ML reliability engineering project. Its most compelling evidence is resource-controlled analytical execution, reproducible evidence storage, and careful separation of statistical fitting and assessment. Breadth across modalities is secondary. It is best presented as an independently developed, AI-assisted engineering project, with specific ownership claims limited to work the candidate can personally explain.

## 1. Project Summary

### Purpose and product

NUMEK contains two related tools:

- **DataTrust:** inspects datasets before modeling, exposing missingness, duplicate/conflicting observations, suspicious target relationships, split/version differences, time/availability problems, and text/image/document evidence. It produces inspectable findings and HTML/PDF/JSON reports.
- **ConfidenceGuard:** evaluates supplied predictions and uncertainty, fits post-hoc calibration/conformal methods, and reconstructs historical assessments as outcomes arrive or change. Its newest investigation workflow searches for failure regions using separate discovery, selection and confirmation populations.

The engineering problem is preserving the meaning and provenance of a finding across ingestion, computation, interfaces, historical revisions and disclosure. The software does not establish that every flagged dataset is unsuitable, or that every unflagged dataset is reliable.

### Architecture

Python contracts and application services feed shared analytical implementations exposed through Python APIs, Click commands and loopback Flask APIs. DataTrust retains a pandas compatibility path; advanced workflows use embedded DuckDB and private disk-backed workspaces. Spawned worker processes provide cancellation, deadlines and sampled memory/disk monitoring. Completed results, rather than repeated analysis, feed canonical reports and export projections.

The packaged DataTrust application uses React/TypeScript/Vite. ConfidenceGuard has its own JavaScript browser clients and versioned API. Its history uses an authoritative SQLite catalog with immutable evidence objects; DuckDB reconstructs analytical populations. These storage roles are different from a hosted service database. The runtime has no required cloud inference or LLM service.

Sources: [architecture](docs/ARCHITECTURE.md), [runtime contracts and usage](README.md), [worker supervision](src/datatrust/worker.py), [frontend configuration](frontend/package.json), [catalog/storage](src/confidenceguard/history_storage.py).

### Completion and verification boundaries

| Area | Evidence-backed status |
|---|---|
| DataTrust tabular, comparative, temporal, text, image and cross-representation workflows | Implemented, with historical reference checks, browser/report records and workload measurements. Later corrections have their own narrower verification boundaries. |
| ConfidenceGuard prediction evaluation, calibration/conformal methods and longitudinal history | Implemented. Current project records report CG1–CG3 accepted, including CG3 corrections. Earlier ledgers describing pending acceptance are historical. |
| CG4 failure investigation | Implemented locally, including 29 October review corrections; targeted independent re-review, understanding gate and founder acceptance remain pending in the latest in-repository status. Not a fully accepted release. |
| Audio and subsequent CG5–CG7 scope | Deferred/future; exclude from implemented claims. |
| Hosting, customers, operational adoption and business impact | Not established by the inspected evidence. Local browser operation is demonstrated historically; it is not a public deployment. |

Documentation is uneven: parts of the architecture still describe the earlier server-rendered UI and absence of an HTTP analysis API, whereas current code/README expose the React app and local JSON API. Current source and newer status records take precedence. Package version remains `0.1.0`; this is not evidence of a published package release.

### Candidate contribution and attribution

Git identities are `Driv1216` and `Driv_1216`; all reachable commits use those identities. This supports repository ownership and submission history, not sole manual authorship. The initial commit's `docs/AI_COLLABORATION_PROTOCOL.md` explicitly names Drivyaansh as founder/final decision-maker and Codex as implementer, technical verifier and repository steward; ChatGPT and Claude supported strategy/review. Later evidence repeatedly records founder-approved scope and corrections.

**Defensible attribution:** candidate-owned, AI-assisted project; documented objectives, prioritization, acceptance and scope decisions. System-level accomplishments below are established more strongly than the candidate's personal line-by-line implementation. “Built” bullets are conditional on genuine hands-on understanding and contribution. Do not say “single-handedly implemented,” “invented these algorithms,” or imply independent human review wherever a document merely says “independent.” Reviewer identity/process is not consistently established.

Historical attribution source: `git show 9ee3186:docs/AI_COLLABORATION_PROTOCOL.md`; current [review-correction record](validation/cg4/REVIEW_CORRECTIONS.md). No earlier personal development conversations are available in this chat.

## 2. Technical Stack

Technologies below are present in code, package metadata or recorded execution; optional dependencies are not universal requirements.

| Category | Verified technologies and use |
|---|---|
| Languages | Python; TypeScript/TSX; JavaScript; SQL; HTML/CSS. |
| Application/backend | Flask local HTTP server, Click CLI, standard-library typed/dataclass contracts, Jinja2 reports. JSON Schema/OpenAPI artifacts for ConfidenceGuard. |
| Frontend | React 19, TypeScript 5.9, Vite 6; packaged static DataTrust app; separate plain-JavaScript ConfidenceGuard clients. Design/visual-lab folders are experiments, not separate shipped products. |
| Analytical storage | pandas, NumPy; embedded DuckDB SQL with temporary spill; SQLite history catalog; immutable JSONL evidence; optional Parquet/PyArrow and typed NPY vectors in CG4. No verified Postgres, Redis or hosted database. |
| Statistics/ML | Optional SciPy; probability calibration including Platt, isotonic, beta, temperature and qualified Dirichlet methods; LAC/APS/RAPS and regression split/normalized/CQR conformal inference; paired/cluster bootstrap; longitudinal drift/cohort analysis. CatBoost-based diagnostic discovery in CG4 is conditional/partly experimental. |
| Pretrained inference | PyTorch/Transformers, Safetensors, SentencePiece/tokenizers; pinned multilingual E5-small retrieval/embeddings, DeBERTa NLI, DINOv2 image embeddings, SigLIP image–text comparisons; Lingua language detection. These are pretrained integrations, not original model training. |
| Media/document processing | Pillow, pycocotools, ijson, PyYAML; pdfplumber and python-docx for native documents. No general OCR pipeline. |
| Reliability/runtime | `multiprocessing` spawn, psutil monitoring, SHA-256 identities, filesystem ownership/permission checks, locking, staged publication, local-only model loading. |
| Artifacts/development | WeasyPrint PDF from canonical HTML; setuptools/wheel, Git, pytest; ReportLab and PDF inspection tooling in validation. scikit-learn/Evidently appear in reference/comparison tooling, not as proof the runtime uses their full frameworks. |
| Infrastructure | Local CPU execution; recorded macOS ARM64 measurements. No substantiated Docker/Kubernetes, GPU service, CI/CD deployment or cloud-platform achievement. |

Current package minimum is Python 3.12, with 3.13 primary; much historical evidence used Python 3.11. Python 3.14 support is capability-specific, with model/language-detector limitations. Do not flatten these into a claim of universal platform support.

Sources: [pyproject.toml](pyproject.toml), [frontend package](frontend/package.json), [text model pins](src/datatrust/text_model_artifacts.json), [image model pins](src/datatrust/image_model_artifacts.json), [cross-model pins](src/datatrust/cross_model_artifacts.json), [runtime qualification boundaries](docs/CG4_CONFIDENCEGUARD.md).

## 3. Strongest Engineering Achievements

Rank reflects technical evidence, explanatory clarity and resume usefulness together. “High confidence” means source plus retained supporting evidence, not a new audit-time run or proof of personal authorship.

### 1. Disk-backed analysis with supervised resource and failure boundaries

**Challenge:** dataset comparisons can exceed in-memory processing limits; native analytical calls also need enforceable interruption and safe cleanup.

**Implementation:** an opt-in DuckDB path stages sources into owned workspaces, performs SQL aggregations/joins and exact order statistics, and spills intermediates to disk. A spawned worker is monitored for RSS, elapsed time and scratch/free-space use. Cancellation or required failure prevents a completed result from being published; cleanup checks workspace ownership. The legacy pandas path remains separate rather than silently changing old semantics.

**Outcome:** recorded core comparisons processed 5.35 GB combined synthetic CSV inputs in 122.24 seconds, with approximately 2.61 GiB sampled peak worker RSS and observed disk spill. This establishes one substantial laptop workload, not a universal capacity ceiling or speedup over pandas.

**Evidence/confidence:** high for implementation and historical measured workload: [scalable execution](src/datatrust/scalable.py), [supervisor](src/datatrust/worker.py), [capacity JSON](validation/m4/results/capacity-5gib.json), [scope/limitations](validation/m4/README.md). Later edits were not covered by a fresh identical benchmark here. A retained lower-memory allocation failure is meaningful counterevidence to unlimited scalability.

**SDE relevance:** very high—process lifecycle, SQL, resource management and failure semantics. **AI/ML relevance:** high—supports reproducible dataset analysis at meaningful scale, although it is not distributed training.

### 2. Leakage-aware calibration and uncertainty evaluation

**Challenge:** selecting or calibrating methods using evaluation labels can invalidate the comparison; small-sample conformal ranks and non-finite outputs also require precise treatment.

**Implementation:** ConfidenceGuard separates fitting, selection, conformal calibration and evaluation into F/S/C/E roles; freezes common candidate populations; reuses shared metric reducers; and records fitted methods, applications and independent assessments separately. Exact decimal-derived order ranks avoid floating-point boundary mistakes. Tagged numeric states preserve legitimate unbounded intervals without emitting invalid JSON. E-label noninterference is directly exercised.

**Outcome:** allows users to compare calibrated probabilities and prediction sets/intervals without treating reapplication as independently validated. Separate arithmetic/reference checks corroborate implemented calculations. The evidence supports method correctness on recorded cases, not improved predictive accuracy or future coverage for arbitrary data.

**Evidence/confidence:** high: [method orchestration](src/confidenceguard/methods.py), [conformal primitives](src/confidenceguard/conformal.py), [behavioral controls](tests/cg2/test_methods.py), [reference/simulation evidence](validation/cg2/results/final-20261019/verification.json), [limitations](validation/cg2/README.md).

**SDE relevance:** high—strict contracts, reproducible state and interface consistency. **AI/ML relevance:** very high—evaluation design, calibration, uncertainty quantification and dependence-aware comparison. Best choice for an ML evaluation or applied AI internship.

### 3. Immutable historical evidence with delayed-label reconstruction

**Challenge:** delayed labels, corrections and backfills must change the current interpretation without silently rewriting earlier evidence or counting retries as new observations.

**Implementation:** authoritative SQLite catalog commits control visibility of immutable JSONL objects. Protected staging, file hashes, locks and operation receipts address interrupted publication and lost responses. DuckDB reconstructs as-of populations, outcome maturity and explicit restatements; frozen prediction/method evidence can be reused without refitting. Catalog visibility, rather than file presence, determines committed evidence.

**Outcome:** supports replayable historical assessments, correction/backfill and backup/restore while preserving earlier results. Tests exercise crash boundaries, deleted dependencies, corruption and reconstruction. A recorded sparse backfill updates labels without rewriting the original prediction object.

**Evidence/confidence:** high: [storage](src/confidenceguard/history_storage.py), [longitudinal reconstruction](src/confidenceguard/longitudinal.py), [lifecycle tests](tests/cg3/test_lifecycle.py), [history tests](tests/cg3/test_history.py), [verification ledger](validation/cg3/VERIFICATION_LEDGER.md). Local filesystem assumptions and substantial JSONL storage expansion are explicit limits.

**SDE relevance:** very high—transactional boundaries, persistence, idempotent operation handling and recovery. **AI/ML relevance:** very high—label maturity, temporal evaluation and evidence reproducibility. This is an offline/local history system, not a deployed streaming monitoring service.

### 4. Explainable reconciliation between records and native documents

**Challenge:** a number or claim is meaningful only when matched to the correct entity, period, units, document location and competing evidence; naive joins or semantic similarity can produce misleading agreement.

**Implementation:** explicit relationship/mapping recipes, cardinality/context checks, exact decimal/date/unit reconciliation and native PDF/DOCX locators precede optional E5 retrieval and DeBERTa NLI. Model work is bounded, publisher/runtime identities are pinned, and unsupported populations abstain. Protected manifests resolve local originals separately from portable reports; reviewer decisions cannot alter analytical counts.

**Outcome:** produces inspectable agreements, discrepancies and competing evidence tied to source locations. A recorded end-to-end authored financial example contains 18 revenue agreements, one discrepancy and one conflict. Separate bounded image–caption association qualification demonstrates a narrow pretrained-model application.

**Evidence/confidence:** high for implemented deterministic workflow; moderate for external semantic usefulness: [cross-model implementation](src/datatrust/cross_models.py), [native extraction](src/datatrust/cross_documents.py), [end-to-end artifact](validation/m9/results/end_to_end.json), [qualification and caveats](validation/m9/README.md). Authored English financial controls and planted COCO swaps do not establish general fact-checking accuracy.

**SDE relevance:** high—heterogeneous ingestion, joins, traceability and integrity. **AI/ML relevance:** very high—retrieval/NLI integration and disciplined abstention. Stronger applied AI evidence than simply listing transformer libraries.

### 5. Full-stack workflows that preserve analytical and disclosure contracts

**Challenge:** configuration changes, stale confirmations, report downloads and saved results must refer to the same analysis; sensitive local evidence must not accidentally enter portable artifacts.

**Implementation:** React/TypeScript talks to session-owned Flask jobs; source/configuration fingerprints bind confirmation to analysis. Mutation requests carry CSRF protection, local sources are root-restricted, and completed evidence drives HTML/JSON/PDF. Opt-in DataTrust saved history verifies hashes/sizes and can generate a PDF from verified saved HTML after the dataset is gone. Per-analysis conversion locking handles concurrent requests, abandoned work and deletion during conversion. ConfidenceGuard separately projects local versus shareable evidence.

**Outcome:** makes the analytical tooling usable through a browser while preserving result identity and supporting source-free reopening of saved reports. Prevents stale or altered artifacts from being silently reused. These controls do not constitute encryption or proof of a comprehensive security audit.

**Evidence/confidence:** high for code and historical interface checks: [typed client](frontend/src/app/api.ts), [workflow implementation](frontend/src/app/flow.tsx), [Flask adapter](src/datatrust/api_web.py), [saved history](src/datatrust/history.py), [PDF lifecycle tests](tests/test_saved_pdf.py), [disclosure](src/confidenceguard/disclosure.py). No current interactive browser session was run during this audit.

**SDE relevance:** very high for full-stack; high for backend. **AI/ML relevance:** medium—valuable delivery infrastructure, less distinctive than evaluation/model integration.

### 6. Temporal dataset analysis with explicit availability and maturity semantics

**Challenge:** event time alone cannot establish whether a feature or label was available at prediction time; DST, revisions and incomplete follow-up complicate leakage investigation.

**Implementation:** explicit clocks/timezones, schedule/lifecycle populations, exact-observation revisions, feature-bound availability and target maturity feed supplied static/rolling evaluation-plan checks. These are separate semantics rather than a generic time-series score. Public-corpus and authored controls cover time/availability and lifecycle cases.

**Outcome:** surfaces conditional temporal problems that ordinary null/duplicate profiling misses and makes exclusions visible before temporal evaluation. It diagnoses declared data semantics; it does not recover unknown availability information or prove absence of leakage.

**Evidence/confidence:** high for implemented declared semantics; external correctness depends on declarations: [methodology](docs/M5_TEMPORAL_RELIABILITY.md), [verification](validation/m5/README.md), [temporal controls](tests/m5/test_truth_tables.py).

**SDE relevance:** medium/high—careful domain modeling and time handling. **AI/ML relevance:** high—time-aware data preparation and evaluation integrity. Resume reserve: overlaps with achievement 3 and is harder to explain quickly.

**Why CG4 is not ranked:** nonlinear failure discovery with CatBoost/typed features and D/S/H separation is technically substantial, but current qualification gaps, retained failed approximations and pending acceptance make it a weaker default resume choice. Mention only as an ongoing investigation capability with explicit method limits, not a generally validated failure-discovery algorithm.

## 4. Metrics & Evidence

### Defensible quantitative results

| Result | Meaning and required qualification | Evidence |
|---|---|---|
| 5,350,872,664 combined source bytes; 122.24 s; 2,801,516,544 B sampled worker RSS | Approximately 5.35 GB input, 2.61 GiB worker RSS. Two four-column sources, 8,918,121 rows each; core scope includes ingestion, excludes report rendering. Synthetic repeated-context workload on a 16 GiB macOS ARM64 machine. About 0.86 GiB spill and 6.03 GiB peak workspace; not an all-workflow result. | [Raw capacity record](validation/m4/results/capacity-5gib.json), [method](validation/m4/README.md) |
| 10,000 field reconciliations and 50 native PDF pages in 23.97 s | Authored simple native documents; approximately 0.171 GiB sampled RSS. Not OCR or arbitrary-document capacity. Secondary metric; less compelling than the architecture itself. | [Small workload](validation/m9/results/small_resources.json) |
| 1 million records, 5 million associations, 1,000 native PDF pages in 485.67 s | Association/context/extraction workload, about 2.36 GiB sampled RSS; **not** 1 million field reconciliations. Concurrent local load limits latency interpretation. | [Large workload](validation/m9/results/large_resources.json), [scope](validation/m9/README.md) |
| COCO association-swap precision 235/236 (99.58%), recall 235/235 | Held-out set contains 235 original and 235 planted swapped associations across 47 held-out image families, separate from calibration families. One original pair falsely flagged. This evaluates planted swaps, not caption truth or general semantic correctness. Optional interview evidence; too caveat-heavy for the default bullet. | [Qualification JSON](validation/m9/results/image_qualification.json) |
| Paired IID and cluster bootstrap each covered the known effect in 148/160 simulated datasets; invalid IID-on-dependent control in 95/160 | At nominal 95%, observed coverages are 92.5% and 59.4%. Supports why dependence-aware designs matter; does not prove exact nominal coverage or superiority on real data. | [Simulation record](validation/cg2/results/final-20261019/verification.json) |

These are retained measurements, not newly reproduced results. No before/after speedup or memory reduction is substantiated by the capacity result alone. Prefer one well-scoped scale metric over multiple numbers.

### Material negative evidence and tradeoffs

- Historical temporal bootstrap qualification includes undercoverage: short-block AR(1) coverage was 0.79 for nominal 0.90, with a deliberately invalid IID control at 0.52. Do not claim universally valid temporal confidence intervals. [CG3 ledger](validation/cg3/VERIFICATION_LEDGER.md).
- CG4 general BCa/cluster/ranking approximations are refused for new formal confirmation under the approved closure scope; unfinished geometric/objective/history profiles remain unqualified. Strong synthetic recovery envelopes cannot be generalized to all failure modes. [Current status](docs/CG4_CONFIDENCEGUARD.md), [corrections](validation/cg4/REVIEW_CORRECTIONS.md).
- Later scalability probes distinguish tall, wide, high-cardinality and malformed inputs. A 5,000-column workload generated a 416-page PDF despite completing analysis; scalability of computation does not imply usable report size. Default unlabeled limits also intentionally refuse larger sources. [Probe summary](validation/ws4/results/summary.json).
- Context/dependency fixtures explicitly retain a noisy-copy miss and bounded/unsearched features. Avoid “detects all leakage” or “100% accurate data-quality detection.” [Constructed-case summary](validation/ws3/results/summary.md).
- Immutable JSONL improves auditability but expands storage substantially, particularly for sample-heavy uncertainty history. One million binary opportunities retained roughly 6.79 GiB; this is a tradeoff, not storage optimization. [CG3 workload ledger](validation/cg3/VERIFICATION_LEDGER.md).
- An archived manual-first reviewer assigned a different risk band from the baseline application on a spam dataset. This is limited external feedback, not demonstrated user value or agreement. [Historical review](validation/dry_runs/evidence/RC003_TECHNICAL_REVIEW_SUMMARY.md).

### Audit-time verification limitations

Source, test logic, Git history, package declarations, benchmark JSON and verification records were inspected. Expensive suites, simulations, model inference, PDFs and browser stories were not rerun. The default local `.venv` reports Python 3.11.15, below the current declared minimum; treating it as a valid current qualification environment would be misleading. Historical records using that interpreter remain historical evidence.

Uncommitted changes affect analytical and history modules. No full latest-tree certification follows from earlier passing ledgers, nor was a byte-for-byte comparison of this entire working tree against every historical qualification freeze performed. Historical “passed” descriptions are reported as recorded evidence. No public repository reachability, live demo or hosted service was verified over the network.

## 5. Resume Recommendations

### SDE / Backend / Full-Stack resume

**Select achievements 1, 3 and 5.** They form three distinct stories: resource-managed computation, persistent evidence/recovery, and browser-to-backend delivery. For backend roles, emphasize SQL execution, catalog visibility, crash recovery and immutable state. For full-stack roles, give React/TypeScript and confirmation/export behavior enough space to show integration beyond UI styling.

With only two bullets, use 1 and 3 for backend; 1 and 5 for full-stack. Keep Python, DuckDB, SQLite and Flask as contextual keywords. Avoid forcing every modality into the same bullet.

### AI / ML / Applied AI resume

**Select achievements 2, 4 and 3.** They demonstrate evaluation design, pretrained retrieval/NLI integration and temporal evidence reconstruction. For applied AI roles, lead with 4; for ML evaluation/reliability roles, lead with 2. With two bullets, use 2 and 4.

This project is strongest for applied ML tooling, evaluation and data reliability. It does not currently substantiate original foundation-model training, fine-tuning improvements, research novelty, or serving models at production scale. Multilingual E5 is a real stack detail; East Asian language quality is not established merely by using a multilingual encoder. Use clear international terminology and explain the product in one short line; no regional performance claims follow from this audit.

### Weak claims to avoid

- “Production-grade,” “enterprise-scale,” “deployed globally,” “used by AI teams,” or revenue/user/adoption claims.
- “Improved accuracy,” “reduced latency by X%,” “eliminated leakage,” or “guaranteed calibrated coverage” without an appropriate comparative result and assumptions.
- “Trained an NLP/computer-vision model” when the work integrated pretrained checkpoints; calibration fitting and diagnostic learners should be described separately.
- “99.6% fact-checking accuracy”: the underlying statistic is precision on planted image–caption association swaps.
- “Analyzed 5 GB in two minutes” without the combined-input, synthetic/core-analysis qualification.
- Presenting arbitrary risk-score formulas, test totals, milestone numbers, report page counts or preserved artifact counts as user impact.
- “Built all components from scratch” or “sole engineer” when the history explicitly assigns implementation to AI assistance.

Before using a bullet, be ready to trace one input through the relevant code, explain a failure path, and defend the key design tradeoff. If the personal contribution was limited to specifying/reviewing generated work, use “Led AI-assisted development of …” and describe the concrete decisions you owned instead of claiming hands-on implementation of each subsystem.

## 6. Candidate Resume Bullets

These are system-evidence-backed drafts, conditional on personal contribution as qualified above. They are alternatives for two resume versions, not six bullets to include together. Actual line wrapping depends on the resume layout.

### SDE / Backend / Full-Stack

- Built a supervised Python/DuckDB analysis engine; processed 5.35 GB of combined synthetic CSV inputs in 122 s at 2.61 GiB sampled peak worker RSS, excluding report rendering.
- Implemented SQLite-backed immutable evidence storage with crash recovery and as-of reconstruction, enabling delayed-label updates without rewriting original predictions.
- Connected React/TypeScript workflows to Flask APIs with source-bound confirmation and hash-verified report history, allowing saved reports to reopen without original datasets.

### AI / ML / Applied AI

- Implemented probability calibration and split-conformal evaluation with separate fit, selection, calibration and evaluation populations to prevent evaluation-label reuse during fitting.
- Integrated offline E5 retrieval and DeBERTa NLI with native PDF/DOCX reconciliation, producing source-linked agreement and conflict evidence with abstention outside qualified scopes.
- Built longitudinal prediction evaluation from immutable facts, separating delayed outcomes and revisions from frozen predictions to preserve reproducible historical assessments.

## 7. Project Links & Status

- **Repository remote:** [Driv1216/Numek](https://github.com/Driv1216/Numek). Verified from local Git configuration; public access/remote freshness not checked.
- **Latest local commit:** [ba3cf16](https://github.com/Driv1216/Numek/commit/ba3cf16), “Complete ConfidenceGuard CG3 and integrate NUMEK frontend workflows,” 23 October 2026, 00:46 IST. Local `origin/main` points to the same commit; no fetch was performed.
- **Actual observed development dates:** earliest reachable commit 15 June 2026; initial documentation is dated 14 June. Baseline/browser work appears in August; expanded data workflows and ConfidenceGuard in October. Latest current correction documentation is 29 October. Safe resume date range: **Jun 2026–Present** as of this audit; earlier project conception is not established.
- **Local application:** `datatrust ui`, normally [127.0.0.1:8000/app/](http://127.0.0.1:8000/app/); ConfidenceGuard at [127.0.0.1:8000/confidenceguard](http://127.0.0.1:8000/confidenceguard). These are documented local routes, not currently running or public demos.
- **Portfolio evidence:** [example report](examples/report.html), [M9 report](validation/m9/results/reports/closure/pdf_financial.html), [CG3 review guide](validation/cg3/REVIEW_QUICKSTART.md). Retained artifacts demonstrate local outputs; inspect disclosure before publishing any additional local reports.
- **Readiness:** substantial functional local application and engineering evidence, suitable for an internship portfolio with the above qualifications. CG4 remains a review-correction candidate; broader product adoption, hosted operations and general model validity remain unestablished.

### Reachable history reviewed

| Date (IST) | Commit | Development evidence |
|---|---|---|
| 15 Jun 2026 | `9ee3186`, `9ea8930` | Initial baseline package, validation workspace and frozen dry-run candidate. The initial import already contains working code; Git does not expose every earlier development step. |
| 5 Aug 2026 | `1bbf2e4`, `1799268` | Local UI/evidence-first reports; historical handoff cleanup. |
| 13 Aug 2026 | `5bf2476` | Classification baseline completion. |
| 11 Oct 2026 | `6671eff`, `a6f02c9` | Tabular, comparative/scalable and temporal workflows plus focused correction evidence. |
| 14 Oct 2026 | `7154606` | Text, image and cross-representation workflows. |
| 19 Oct 2026 | `f7a7db0` | ConfidenceGuard prediction evaluation/calibration and statistical integrity work. |
| 23 Oct 2026 | `ba3cf16` | Longitudinal ConfidenceGuard and integrated frontend workflows. |
| Through 29 Oct 2026 | Working tree | CG4 investigation and review corrections, runtime/dependency changes and additional local experiments/evidence; not represented by a subsequent commit. |

The history consists largely of checkpoints/imports, not granular implementation commits. This audit covers the available history and sampled supporting implementations; it cannot reconstruct deleted uncommitted work, unavailable conversations, or each person's precise share of implementation.
