# Numek Master Context

## Changelog

- **2026-06-14: Upgraded the project and validation environments to Python 3.11.** Raised the package minimum to Python 3.11, rebuilt both environments on Python 3.11.15, migrated the isolated comparison to Evidently 0.7.21 and its current DataSummaryPreset API, regenerated validation evidence, and verified the full suite without runtime package changes.
- **2026-06-14: Completed the reproducible validation corpus.** Prepared three pinned UCI datasets, generated seven controlled mutations and ten timed reports, reviewed every leakage flag, completed an isolated Evidently Adult comparison, and corrected one public-corpus false severe leakage classification.
- **2026-06-14: Completed DataTrust V1 correctness invariants.** Added separate target-missingness handling, severe column-missingness evidence, strong versus review-only leakage classification, explained score guardrails, deterministic risk priority, and regression coverage for credibility-breaking contradictions.
- **2026-06-14: Removed dynamic kickoff content.** Removed the stale-prone next-actions list and universal next-chat prompt. Fresh operational context now comes from the living documents and task-specific prompts defined in the collaboration protocol.
- **2026-06-14: Added the multi-AI operating model.** Established Codex as repo master and technical verifier, created living context documents, and defined how ChatGPT, Claude, Codex, and Drivyaansh collaborate.
- **2026-06-02: Initial master context version.** Captures the original Numek first draft, the strategy evolution after critique, the DataTrust V1 implementation, current boundaries, credibility strategy, roadmap, and known unknowns.

## One-Page Summary

Numek is an AI reliability verification company.

The long-term thesis is that companies deploying AI into real decisions need evidence that three things are true:

1. **Data reliability before training:** the data used to train, fine-tune, or evaluate AI is trustworthy enough.
2. **Model reliability during deployment:** the model's confidence and behavior remain reliable under real-world use.
3. **Output reliability after generation:** generated answers, especially LLM outputs, are grounded, cited, and not hallucinated.

The current execution focus is much narrower:

**DataTrust V1:** a local-first Python package that generates an HTML dataset reliability report from a CSV.

The first reader is not a regulator directly. The first reader is an **ML/data lead who needs to explain dataset reliability to a non-technical stakeholder** such as a CTO, VP, risk lead, compliance reviewer, or enterprise customer.

The current strategy is:

**Build one credible report first. Grow into the broader AI reliability platform later.**

## Original First Draft Summary

Original source: `docs/Numek info first draft.pdf`

The first draft framed Numek as an AI reliability platform answering two core questions:

- **Before deployment:** is the training or fine-tuning data actually trustworthy?
- **During/after deployment:** when the model says it is confident, should we believe it?

The draft proposed two original modules:

- **Dataset Quality Explainer:** a pre-deployment dataset audit engine.
- **Model Confidence Auditor:** a post-deployment confidence calibration and drift auditing layer.

Together, these were framed as a trust verification layer for AI systems. The original language positioned Numek around the question:

> How do I know if my AI is lying to me, and why?

The draft identified high-stakes AI contexts, especially fintech, NBFCs, credit scoring, insurance, HR, and regulated decision systems. It emphasized that companies increasingly need documentation around AI risk, data governance, model behavior, and human oversight.

The original product concept included:

- a dataset trust score
- data quality explanations
- calibration metrics
- drift detection
- high-confidence wrong prediction detection
- SHAP-style explanations
- a combined reliability report or "Reliability Certificate"

The original business model ideas included:

- per-audit pricing
- monthly SaaS subscription
- reliability certification
- compliance consulting
- white-label reliability verification for AI vendors

The original MVP recommendation was a local Python package that takes a dataset and trained model artifacts, then outputs a report. That core direction still holds, but the current execution has been narrowed further.

The draft also connected the startup to research. It suggested that calibration, label-noise detection, hallucination benchmarking, and domain-specific reliability methods could become publishable work and credibility signals.

## What Changed Since The Draft

The broad company vision stayed intact, but the execution narrowed.

Key changes:

- **From platform to first artifact:** Numek is still a broad AI reliability company, but V1 is only DataTrust.
- **From certificate to report:** "Reliability Certificate" is avoided for now because it implies authority, legal backing, or accreditation we do not yet have. The current language is reliability report, evidence pack, or model/data risk report.
- **From PDF-first to HTML-first:** HTML is easier to generate, inspect, iterate, and share during V1. PDF export comes later.
- **From opaque trust score to transparent sub-scores:** a single unexplained 0-100 score is dangerous. V1 uses decomposed sub-scores plus guardrails.
- **From regulator as first reader to ML/data lead as first reader:** the first product is for a technical lead who needs to justify reliability upward or outward.
- **From all three pillars at once to DataTrust first:** ConfidenceGuard and HallucinationGuard are future phases, not current implementation targets.
- **Local-first stayed central:** sensitive data should not need to leave the user's machine.
- **Credibility became a central product problem:** because Numek audits trust, Numek itself must earn trust through transparent methodology and evidence.

## Current Company Thesis

Numek is an AI reliability verification layer.

Long-term, Numek maps to the AI lifecycle:

1. **DataTrust:** verifies whether the data is reliable enough to train, fine-tune, or evaluate AI on.
2. **ConfidenceGuard:** verifies whether the model's confidence, calibration, and behavior remain reliable in real-world deployment.
3. **HallucinationGuard:** verifies whether generated LLM outputs are grounded, supported, and safe to trust.

The company can be broad, but the first product must stay narrow.

The first product is DataTrust because it has the lowest integration friction:

- a CSV can be audited locally
- no production logs are required
- no SaaS upload is required
- no model endpoint is required
- the report can become the first demo, sales artifact, and feedback magnet

## What This Is NOT

These boundaries are intentional. They prevent future collaborators, future chats, and future versions of the project from expanding the scope too early.

- **DataTrust is not a data pipeline tool.** It does not move, transform, schedule, or orchestrate data pipelines.
- **DataTrust is not a monitoring service.** V1 does not watch live production data, emit alerts, or run continuously.
- **DataTrust is not a replacement for proper EDA.** It produces reliability evidence, not a complete exploratory data analysis workflow.
- **DataTrust is not a formal compliance certification.** It does not prove legal compliance, regulatory approval, fairness, safety, or audit clearance.
- **Numek is not an MLOps platform.** It is not trying to replace MLflow, Arize, Fiddler, WhyLabs, Datadog, or full model operations stacks.
- **V1 is not a SaaS product.** No hosted dashboard, login system, database, billing, or cloud upload belongs in V1.
- **V1 is not a PDF/export-heavy workflow.** HTML is the canonical V1 output. PDF export can come later after the report itself is good.
- **V1 is not ConfidenceGuard or HallucinationGuard.** Those are roadmap items, not current scope.

The identity boundary is:

**DataTrust turns local dataset checks into stakeholder-readable reliability evidence.**

## Current Product: DataTrust V1

DataTrust V1 is a local-first Python package that reads a CSV and generates an HTML dataset reliability report.

### User

The first user is an ML/data lead.

They need to answer:

> Can I explain whether this dataset is reliable enough to use, and can I show that explanation to someone above me who is not deep in the notebook?

### Job To Be Done

The job is not "profile my dataset" in a generic sense.

The job is:

> Help me produce a clear, defensible reliability report that explains the biggest dataset risks and what to do next.

### Input

- CSV dataset
- target column
- task type, currently `classification`

### Output

- HTML reliability report
- executive summary
- sub-scores
- top risks
- methodology and limitations
- appendix with detailed metrics

### Python API

```python
from datatrust import DataTrust

audit = DataTrust("examples/loan_data.csv", target="default", task="classification")
audit.generate_report("examples/report.html")
```

### CLI

```bash
.venv/bin/datatrust audit examples/loan_data.csv --target default --task classification --out examples/report.html
```

The report is the product. The code exists to produce a report that is worth showing.

## V1 Definition Of Done

DataTrust V1 is done only when every approved gate passes in one frozen
practitioner validation round:

- at least `4/5` ML/data reviewers install and run without founder intervention
- all three public datasets and two practitioner-owned CSVs report in under `30s`
- structure and claims, finding quality, and score defensibility gates pass
- at least `4/5` practitioners would share the report with minor or no edits
- the separate non-technical reviewer passes all four comprehension questions

Any scoring, profiling, risk-summary, or report-content change invalidates the
active practitioner validation round. There is no conditional pass.

Anything not required to reach this condition is V2.

Examples of V2 or later work:

- PDF export
- SaaS dashboard
- live monitoring
- model calibration
- drift detection
- LLM hallucination detection
- enterprise auth
- billing
- formal certification language

## Current Technical State

The current repo contains a working DataTrust V1 package.

Important files:

- `README.md`: product overview and usage
- `METHODOLOGY.md`: scoring details and limitations
- `pyproject.toml`: modern package metadata
- `setup.py`: compatibility shim for editable installs
- `src/datatrust/`: package code
- `src/datatrust/core.py`: public `DataTrust` class
- `src/datatrust/profiler.py`: pandas-based dataset profiling
- `src/datatrust/scoring.py`: sub-scores and guardrails
- `src/datatrust/risks.py`: plain-language top risk summaries
- `src/datatrust/renderer.py`: HTML rendering
- `src/datatrust/cli.py`: Click-based CLI
- `src/datatrust/templates/report.html`: report template
- `examples/loan_data.csv`: synthetic lending-style demo dataset
- `examples/report.html`: generated sample report
- `tests/test_datatrust.py`: automated tests

Current setup and verification commands:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip setuptools wheel
.venv/bin/python -m pip install --no-build-isolation -e ".[dev]"
.venv/bin/python -m pytest -q
```

Generate the sample report:

```bash
.venv/bin/datatrust audit examples/loan_data.csv --target default --task classification --out examples/report.html
```

Current verified test state:

```text
23 passed
```

## Report Anatomy

DataTrust V1 reports have six sections.

### 1. Executive Summary

Communicates the overall reliability score, risk level, recommended next action, and top three findings.

This is the most important section for the non-technical stakeholder.

### 2. Dataset Health

Shows basic dataset condition:

- rows
- columns
- missing cells
- duplicate rows

This section answers whether the dataset has obvious structural quality problems.

### 3. Target & Label Quality

Shows target distribution and class balance.

Missing target labels are tracked separately and excluded from class counts.
Datasets with no usable target labels fail clearly. V1 does not implement true
label-noise detection yet.

### 4. Feature Risk

Shows transparent sub-scores and highlights feature-level risks:

- constant fields
- near-constant fields
- high-cardinality categoricals
- numeric outlier concentration
- strong leakage candidates that affect scoring and guardrails
- review-only leakage prompts that do not automatically reduce the score

### 5. Methodology & Limitations

Explains what was checked, how to interpret the report, and what the report does not prove.

This section is crucial because credibility comes from clarity, not from pretending the tool does more than it does.

### 6. Appendix

Shows detailed per-column metrics:

- column name
- role
- type
- missing rate
- unique count and rate
- constant flag
- high-cardinality flag
- outlier rate

## Methodology And Scoring

DataTrust V1 uses transparent sub-scores from 0 to 100. Higher is better.

Current sub-scores:

- **Completeness:** penalizes missing cells while severe column-level
  missingness is surfaced separately.
- **Uniqueness:** penalizes duplicate rows.
- **Target Balance:** penalizes severe class imbalance.
- **Feature Usability:** penalizes severely missing, constant, near-constant,
  high-cardinality, and outlier-heavy feature columns.
- **Leakage Risk:** penalizes strong token/phrase-aware outcome-like candidates;
  generic status or target-related names remain review-only prompts.

The overall reliability score starts with the average sub-score, then applies guardrails for high-stakes failure modes.

Applied guardrails are returned in `scores["guardrails"]` and shown in the
report. Strong leakage, a single-class target, or no feature columns cap the
score at `49`. Missing target labels, severe missingness, severe duplicates, or
a critical sub-score cap it at `69`.

Risk bands:

- `85-100`: Low risk
- `70-84`: Moderate risk
- `50-69`: Elevated risk
- `0-49`: High risk

Current limitations:

- no label-noise detection yet
- no drift detection yet
- no fairness testing yet
- no model calibration yet
- no production monitoring yet
- no legal or compliance certification
- leakage detection is heuristic and must be reviewed by a human

## Credibility Problem

Credibility is not a side issue for Numek. It is central.

Most tools need trust. Numek sells trust. That means every score, report, and recommendation must be defensible.

The core credibility question is:

> Why should an ML lead trust a reliability score from a new tool with no institutional backing?

### Current Credibility Strategy

V1 earns early trust through transparency:

- transparent sub-scores instead of a black-box trust score
- methodology section in the report
- explicit limitations
- local-first execution so sensitive data does not leave the user's machine
- simple, inspectable checks
- guardrails for high-stakes risks such as target leakage
- code and report structure that can be reviewed

### Credibility Still Missing

Numek does not yet have:

- a research paper
- public benchmarks
- community validation
- expert or advisor review
- pilots with real ML teams
- comparative studies against adjacent tools
- evidence that the scoring weights feel correct to domain experts

### Credibility Milestones

The path to stronger credibility should be:

1. Publish the methodology clearly.
2. Generate reports on public datasets.
3. Benchmark findings against known issues or manual review.
4. Compare outputs with adjacent tools such as Evidently, Cleanlab, Great Expectations, and ydata-profiling.
5. Get feedback from ML leads on whether findings are useful and accurate.
6. Publish a technical note or short paper on dataset reliability reporting.
7. Add expert/advisor review.
8. Version reports and methodology so old results remain interpretable.

Early credibility comes from glass walls: make the method inspectable before asking people to trust the brand.

## Competitor And Adjacent Tool Map

DataTrust is not alone. The adjacent landscape matters.

### Dataset And Data Quality

- **Cleanlab:** strong open-source/data-centric AI library, especially for label issues and data quality.
- **Great Expectations:** data validation and expectations framework.
- **ydata-profiling:** dataset profiling reports.
- **Evidently:** open-source evaluation, monitoring, data quality, drift, and report generation.

### ML Monitoring And Observability

- **Arize:** model observability, evaluations, monitoring.
- **Fiddler:** model performance management, explainability, monitoring, governance.
- **WhyLabs:** data and ML observability, drift, health monitoring.

### LLM Evaluation And Hallucination/Groundedness

- **Ragas:** RAG evaluation framework.
- **TruLens:** LLM/RAG evaluation and tracing.
- **Galileo:** LLM evaluation/observability.
- **Patronus:** LLM evaluation and risk detection.

### DataTrust Differentiation

DataTrust should not claim novelty in every raw metric.

The differentiation is:

- stakeholder-readable reliability evidence
- local-first execution
- report-first workflow
- transparent methodology
- plain-language synthesis
- explicit limitations
- evidence-pack framing for ML leads who need to explain risk upward

Evidently may tell an ML engineer what happened. DataTrust should tell the ML lead what it means, why it matters, and what to do next.

## Roadmap

### Phase 1: DataTrust V1 Usable Report

Goal: make the current local HTML report credible enough to show to ML/data leads.

Focus:

- correctness and trust invariants **completed**
- reproducible three-dataset validation corpus and controlled mutations **completed**
- internal adjacent-tool comparison as supporting evidence **completed**
- technical and non-technical dry runs
- one frozen all-gates-pass practitioner validation round

### Phase 2: Stronger Dataset Checks

Add deeper dataset reliability checks:

- better leakage detection
- schema validation
- suspicious identifiers
- temporal columns
- missingness patterns
- richer outlier interpretation
- optional Cleanlab-based label issue detection

### Phase 3: Optional Model Prediction Analysis

Allow users to provide model predictions or probabilities.

Add:

- calibration metrics
- Brier score
- reliability curve
- high-confidence wrong predictions
- threshold sensitivity

This begins the bridge from DataTrust to ConfidenceGuard.

### Phase 4: ConfidenceGuard

Build model reliability and drift functionality.

Core question:

> Is the model's confidence still reliable in the real world?

Potential checks:

- drift
- calibration
- model performance degradation
- confidence/accuracy mismatch
- segment-level reliability

### Phase 5: HallucinationGuard

Build LLM output reliability functionality.

Core question:

> Is this generated answer grounded in evidence?

Potential checks:

- unsupported claims
- citation quality
- contradiction against source documents
- RAG groundedness
- domain-specific hallucination risk

### Phase 6: Broader Numek Platform

Only after the first modules prove demand, Numek can become a broader reliability platform.

Possible later artifacts:

- versioned reliability reports
- machine-readable report JSON
- customer-cloud deployment
- governance evidence packs
- integrations with model workflows
- enterprise-facing reliability dashboards

## Research Connection

Numek can support both startup progress and academic/research progress.

The research angle matters because credibility is one of the hardest problems for an AI reliability company. A transparent methodology, public benchmarks, and publishable findings can become both product assets and academic assets.

Possible research questions:

- How should reliability scores for tabular AI datasets be composed and validated?
- What is the false positive rate of heuristic leakage detection on real-world datasets?
- How do calibration metrics degrade under distribution shift in financial or lending datasets?
- Can Cleanlab-style confident learning reliably detect label noise in semi-automated datasets?
- What makes a reliability report useful to both technical and non-technical stakeholders?
- How should domain-specific reliability reporting differ in regulated AI contexts?

Possible venues:

- FAccT
- RecSys workshops
- FinNLP
- NeurIPS workshops
- ICLR workshops
- ICML workshops
- ACL/EMNLP workshops for later LLM reliability work

How pilots can become research:

- Run DataTrust on real or realistic datasets.
- Compare DataTrust findings to manual review.
- Track where the report catches issues humans miss.
- Track where it produces false positives.
- Analyze which report sections users trust or ignore.
- Turn the methodology and pilot findings into a technical note or workshop paper.

## Known Unknowns

Known unknowns require evidence, not just decisions.

### Do ML leads actually read reliability reports?

- **Why it matters:** if ML leads do not read or share reports, the product needs a different artifact.
- **How to resolve:** show the report to ML/data leads and ask what they would use, ignore, forward, or remove.
- **Evidence needed:** at least five reactions from target users, including whether they would share it with a stakeholder.

### Is local-first a selling point or friction?

- **Why it matters:** local-first protects sensitive data, but CLI/local setup can be inconvenient.
- **How to resolve:** ask target users whether they prefer CLI, notebook, Docker, local web app, customer-cloud, or hosted upload.
- **Evidence needed:** workflow preferences from at least five ML/data leads or technical buyers.

### Is the leakage heuristic acceptable on real data?

- **Why it matters:** false positives can destroy trust if DataTrust flags legitimate columns as dangerous too often.
- **How to resolve:** test the heuristic on multiple public and real-world-style datasets.
- **Evidence needed:** a small benchmark of flagged columns reviewed by humans.

### Do scoring weights feel correct to domain experts?

- **Why it matters:** a score that feels wrong will not be trusted, even if the raw checks are useful.
- **How to resolve:** show score breakdowns to ML leads and ask whether risk levels match their intuition.
- **Evidence needed:** feedback on at least ten reports or report mockups.

### Is lending-tech the right first customer?

- **Why it matters:** the first segment determines language, report design, metrics, and sales motion.
- **How to resolve:** compare reactions from lending-tech vendors, fintech ML teams, and broader AI SaaS teams.
- **Evidence needed:** concrete evidence of urgency, willingness to run the tool, and willingness to share the report internally.

### Is HTML enough before PDF?

- **Why it matters:** HTML is easier to build, but some stakeholders may expect PDFs.
- **How to resolve:** ask users whether they would share HTML, screenshot it, export it, or require PDF.
- **Evidence needed:** user preference from report review sessions.

## Open Decisions

Open decisions require choosing a direction.

- **Open-source core vs closed source:** likely open-source core is better for credibility, but the business model must be considered.
- **Exact first customer segment:** lending-tech vendors, fintech ML teams, NBFC-facing AI vendors, or broader AI SaaS teams.
- **Cleanlab in V2:** whether to wrap Cleanlab for label-noise detection or keep it as an external recommendation.
- **Evidently interoperability:** whether DataTrust should import/export Evidently-style artifacts or remain independent.
- **Report tone:** technical report, risk memo, executive evidence pack, or a hybrid.
- **Pricing model:** one-time audit, subscription, paid pilots, open-source plus services, or enterprise license.

## Using This Document

This document provides stable background, project identity, history, and long-term direction. It is not the source for the latest operational state or the next task.

For every new planning or review chat:

- keep this document and `AI_COLLABORATION_PROTOCOL.md` in permanent project sources
- paste the latest `CURRENT_STATE.md`, `DECISIONS.md`, `ROADMAP.md`, and `KNOWN_UNKNOWNS.md`
- add a task-specific kickoff prompt using the template in `AI_COLLABORATION_PROTOCOL.md`

The living documents determine where Numek is now. The task-specific prompt determines what the new chat must do next.
