# Numek Master Context

Last updated: 2026-10-21

ConfidenceGuard now includes opt-in longitudinal reliability within the same product.
CG3 adds protected projected-fact capture before eligibility filtering, frozen
method outputs, an authoritative SQLite catalog, immutable JSONL evidence,
supervised DuckDB reconstruction, revisions/backfill/as-of maturity and immutable
restatements. Reference/current drift, performance/calibration/uncertainty evolution,
declared-cohort mix, qualified resampling and exploratory temporal investigation
share Python/CLI/API/browser and canonical reporting. Standalone CG1/CG2 and
DataTrust history semantics remain intact. See [CG3 contracts and methodology](CG3_CONFIDENCEGUARD.md).
CG3 is complete, including corrections R1–R3, as confirmed by the user on 2026-10-21.

## Identity And Company Thesis

Numek is an AI reliability verification company. Its thesis is that teams using
AI for real decisions need inspectable evidence about data before training,
model behavior during deployment, and generated outputs after generation.

The long-term product vision connects three areas:

- **DataTrust:** dataset reliability for training, fine-tuning, and evaluation.
- **ConfidenceGuard:** model confidence, calibration, drift, and behavioral reliability.
- **HallucinationGuard:** grounding, supporting evidence, citations, and contradictions in LLM outputs.

DataTrust is the completed foundation of Numek. ConfidenceGuard CG1 now implements
a distinct supplied-prediction reliability workbench across three task families.
The user has accepted CG1, its independent review/corrections and closed
understanding gate. CG2 now extends that engine with calibration/uncertainty fitting,
explicit separation, reusable artifacts and qualified statistical evaluation.
HallucinationGuard remains product direction, not an implemented module.

## Current Product Posture

Numek has deliberately moved into active, ambitious product expansion beyond
the completed DataTrust baseline. The expansion architecture and nine-milestone
direction are approved: shared foundation, regression, advanced/unlabeled tabular,
deeper tabular diagnostics, time series, text, images, audio, multimodal/specialized
datasets. M1 implements shared contracts and useful unlabeled CSV profiling. M2 now
implements single-target regression across Python, CLI, browser, HTML/PDF/JSON,
with declared expectations, bounded arithmetic relationships, and evidence-based
review priorities. Regression scoring remains undefined. Drivyaansh accepted the M2 functional
implementation on 2026-10-09; the subsequent narrow report-presentation cleanup
preserves its analytical behavior. M3 now implements annotation-aware partial
workflows, multilabel binary indicators, multi-output regression, and conditional
clustering/anomaly readiness, through the shared CSV engine and every interface.
New task scores remain undefined. M1–M6 completion, including M6’s understanding
gate, is accepted. M4 implements comparative reliability and opt-in scalable local
analysis. M5 implements temporal reliability intelligence with exact clocks, local CSV/Parquet, coverage, feature-bound timing/revisions, supplied evaluation and configurable behavioral investigation. M6 adds text corpus, annotation, conversation and retrieval reliability with bounded duplication/model investigations and private evidence resolution; later modalities remain direction. Internal measurements remain
scoped engineering evidence, not external validation or capacity guarantees.
M6’s review, focused corrections and understanding gate are complete and accepted.
M7 now implements local image reliability, bounded segmentation integrity, offline
visual candidates and private investigation. Its measured engineering evidence
does not imply founder acceptance or universal model/search guarantees.

Build substantial capabilities when they strengthen the product. Do not keep
Numek inside the smallest defensible prototype or treat all development beyond
the baseline as remote. Deeper analysis, stronger UX, model-level reliability,
new modules, and architectural expansion are real development directions.

Ambition must be accompanied by coherent architecture, tests, verified evidence,
and transparent limitations. Individual capabilities become commitments through
explicit product decisions; this direction does not approve every candidate
feature. Describe implemented, approved, proposed, and unresolved work accurately.
Current implementation limitations are facts about today's software, not
permanent future product prohibitions.

Numek must earn credibility for its methods and claims. Reliability reports do
not establish legal compliance, regulatory approval, fairness, safety, model
correctness, or certification without appropriate evidence and authority.

## Users, Positioning, And DataTrust's Role

The initial user is an ML/data lead who needs to explain dataset reliability to
a CTO, VP, risk lead, compliance reviewer, or enterprise customer. The job is to
produce a clear reliability report explaining important dataset risks, their
potential modeling impact, and what to investigate next.

DataTrust combines local execution, transparent methodology, prioritized
findings, plain-language synthesis, and technical evidence in a shareable report.
It differentiates through interpretation and workflow rather than novelty in
every underlying metric. Its accepted presentation is a layered hybrid: a fast
decision surface followed by detailed evidence for technical readers.

Lending-tech vendors and fintech ML teams are initial customer hypotheses, not
proven market selection. NBFC-facing AI vendors and broader AI SaaS teams also
remain candidates. The original vision included credit scoring, insurance, HR,
and other high-stakes decision systems. A regulator is not the initial reader.

DataTrust was selected first because local CSV analysis requires no model
endpoint, production logs, or hosted infrastructure. That decision established
a foundation; it does not impose a permanent sequencing restriction on Numek.
The implemented classification workflow is documented in
[CURRENT_STATE.md](CURRENT_STATE.md), with technical structure in
[ARCHITECTURE.md](ARCHITECTURE.md) and usage in [README.md](../README.md).

## Operating Model And Source Of Truth

- **Drivyaansh:** founder, product direction, priorities, and final decisions.
- **ChatGPT:** product strategy, research, planning, architecture discussion,
  critique, and implementation planning.
- **Codex:** repository master, technical planner, implementer, verifier, and
  documentation maintainer.

The working loop is:

**Drivyaansh + ChatGPT decide/plan → Codex inspects/plans/implements → tests and
verification → update project context → continue.**

Codex should challenge technically unsound plans, surface risks, and resolve
factual questions through inspection and evidence. Routine implementation
judgment remains part of its role; strategic decisions belong to Drivyaansh.
No separate AI handoff, consensus, or adversarial-review stage is required.

When sources disagree, use this hierarchy:

1. Actual repository code, tests, generated artifacts, and verified evidence.
2. Drivyaansh's latest explicit decision.
3. [CURRENT_STATE.md](CURRENT_STATE.md) for present operational truth.
4. [ARCHITECTURE.md](ARCHITECTURE.md) for technical design.
5. This document for strategic context and long-term direction.

Documents must not knowingly contradict implementation. A decision to build a
capability does not mean it already exists. Chats and uploaded sources can be
stale; inspect the repository and read the relevant core documents when
starting work. There is no fixed source-upload or kickoff-template ceremony.

After meaningful work, Codex updates current state from verified outcomes,
architecture when technical structure changes, and master context when major
strategic decisions or direction change. Preserve useful evidence and identify
assumptions; AI agreement is not proof. Resolve technical disputes with code,
research, or a relevant experiment, and preference disputes with Drivyaansh.
Use sanitized summaries or synthetic examples for cloud planning; keep private
customer datasets, credentials, personal information, and sensitive proprietary
material out of shared planning sources unless explicitly authorized.

## Major Decisions And Their Rationale

| Date | Decision and continuing significance |
|---|---|
| 2026-06-02 | **DataTrust first.** Chosen for low integration friction over building all three areas at once or starting with model monitoring/LLM analysis. The foundation is now complete; future sequencing follows the new expansion direction. |
| 2026-06-02 | **Local-first execution.** Avoided sensitive-data upload objections and premature hosted infrastructure. Local deployment is implemented; onboarding and customer evidence may justify additional deployment modes. |
| 2026-06-02 | **Canonical HTML reports.** Enabled quick inspection and iteration over PDF-first or simultaneous format implementations. UI PDF was subsequently approved and implemented; HTML remains canonical. |
| 2026-06-02 | **Transparent sub-scores and explained guardrails.** Chosen over an opaque score or raw metrics without synthesis so severe risks cannot be concealed by healthy averages. Methodology may evolve with benchmark or expert evidence. |
| 2026-06-02 | **Reliability report rather than certificate.** Certification language was rejected because Numek lacks the implied institutional/legal authority. Revisit only with appropriate standards alignment, accreditation, institutional backing, or legal review. |
| 2026-06-14 | **Repository documentation as durable memory.** Chosen over relying on chat memory or rewriting strategy after every minor change. The three-document system now carries this principle. |
| 2026-08-04 | **Remove mandatory external practitioner review.** Product building and internal verification take priority. External discovery, advisory review, and pilots can provide learning when chosen; they are not standing acceptance gates. This did not resolve external product-validation questions. |
| 2026-08-05 to 2026-08-13 | **Improve evidence and product presentation while preserving validated analysis.** Added guided UI, richer findings, native UI PDF, explainable target choice, deterministic narrative, and the layered report. Technical rationale and compatibility decisions are recorded in architecture. |
| 2026-08-13 | **Accept the completed DataTrust classification baseline.** Describe ongoing work by capability and status rather than generic sequential product-version labels. Preserve real package versions and immutable candidate IDs. The then-unselected expansion direction is historical, superseded by the decision below. |
| 2026-10-07 | **Active expansion and simpler operation.** Deliberately develop beyond DataTrust with Drivyaansh, ChatGPT, and Codex; consolidate context into three documents and retain useful technical history. Individual next capabilities and sequencing still require deliberate selection. |
| 2026-10-09 | **Approve DataTrust expansion architecture and nine-milestone direction; implement M1.** Shared contracts and useful unlabeled CSV profiling precede regression and broader tasks/modalities. Preserve classification and historical evidence, disclose parsing/coverage/resources, and keep unlabeled scoring undefined. HTML/PDF/JSON share completed evidence across Python, CLI, and UI. Internal verification remains distinct from external method validity and customer usefulness. |

| 2026-10-09 | **Implement the approved DataTrust M2 regression plan.** One shared engine; explicit numerical outcome, optional target/availability declarations, substantial finite distributions and constraints, bounded copy/affine/sum evidence, repeated-input variation, consolidated actions, and canonical exports. Small/sparse relationships stay technical; planned bounds are coverage limitations; ordinary precision is descriptive. Preserve classification scores, M1 parsing/resource/artifact contracts and historical evidence. No regression score or prediction-performance scope. |
| 2026-10-09 | **Implement the revised M3 plan.** Explicit roles, orthogonal annotation expectation/observation/status, unknown defaults for new workflows, effective-semantic compatibility, multilabel and joint numerical evidence, conditional unsupervised representation, bounded resources, compact canonical reports, and independent validation. Preserve classification/M1/M2 and historical artifacts; no new score, modeling, generalized split analysis, or modality framework. |

## Broad Development Direction

The approved sequence has advanced from DataTrust M1–M7/M9 into ConfidenceGuard.
The following broader company directions remain useful context; individual scope
and implementation status are defined by the latest product handoffs below:

- **Deeper dataset analysis:** stronger leakage review, schema checks,
  suspicious identifiers, temporal evidence, missingness patterns, richer
  outlier interpretation, and label-issue analysis where suitable evidence is available.
- **Stronger product UX and workflows:** clearer analysis-to-action experiences,
  additional task/input/export support, reproducible reports, and deployment
  options that address real user needs.
- **Model-level reliability:** predictions or probabilities as inputs,
  calibration, Brier scores, reliability diagrams, high-confidence errors,
  threshold sensitivity, and segment-level reliability.
- **ConfidenceGuard:** model behavior, drift, degradation, and confidence/accuracy
  mismatch, building on justified model-analysis capabilities.
- **HallucinationGuard:** groundedness, unsupported claims, citation quality,
  source contradictions, and domain-specific LLM reliability.
- **Broader platform architecture:** reusable reliability evidence, versioned
  reports, machine-readable output, integrations, customer-cloud deployment,
  dashboards, and governance evidence workflows when justified.

Customer discovery and credibility research can inform capability design
alongside engineering. Neither is an automatic prerequisite for every expansion.

## Credibility, Research, And Adjacent Tools

The foundation includes inspectable methodology, correctness/guardrail tests,
three public UCI datasets, eight controlled mutations, a reviewed leakage ledger,
an internal Evidently comparison, and founder-accepted historical RC_003 review.
See [validation documentation](../validation/README.md) and the
[corpus summary](../validation/results/MILESTONE_2_SUMMARY.md).

These are internal supporting evidence, not independent market validation or a
performance superiority benchmark. Publicly published benchmarks, a research
paper, broader expert/community validation, real-team pilots, and external
scoring-defensibility evidence remain credibility opportunities.

Research should strengthen the product: assess composite scores against manual
review, measure leakage false positives, study calibration under distribution
shift, evaluate label-issue methods, and observe how technical and nontechnical
readers use reports. Domain-specific reliability in lending and other high-stakes
contexts can connect pilots to technical notes, datasets, benchmarks, or papers.
Historical venue candidates include FAccT, RecSys workshops, FinNLP,
NeurIPS/ICLR/ICML workshops, and later ACL/EMNLP workshops for LLM work; these
are research interests, not publication commitments or confirmed opportunities.

The project has considered Cleanlab, Great Expectations, ydata-profiling, and
Evidently for dataset work; Arize, Fiddler, and WhyLabs for model observability;
and Ragas, TruLens, Galileo, and Patronus for LLM evaluation. This is contextual
positioning, not a current competitive assessment. Verify external capabilities
before selecting integrations or making comparative claims. Numek's ambition
can broaden while maintaining explicit interfaces and evidence-based differentiation.

## Unresolved Product Questions

These questions remain open and can guide experiments without reinstating a
mandatory external-validation gate. The expansion direction is already approved.

| Question / current hypothesis | Why it matters and evidence needed |
|---|---|
| **Do ML/data leads use and share the report?** A stakeholder-readable artifact may fill a real workflow gap. | Collect detailed reactions about what readers use, ignore, trust, remove, or forward; measure whether the artifact supports actual decisions. The layered report is implemented, while external usefulness remains unverified. |
| **Is local-first a benefit or onboarding friction?** Sensitive-data concerns favor local execution. | Observe installation and the guided flow; compare notebook, Docker, customer-cloud, and hosted preferences with reasons from target users. |
| **Is the leakage heuristic accurate enough across domains?** Outcome-name checks can produce false positives. | Benchmark flagged columns against human judgments and feature-availability context, retaining reasons for false positives and missed issues. |
| **Are scores and guardrails defensible?** Transparent methods are promising but lack external validation. | Compare internal judgments, public examples, adjacent tools, and expert/user reactions; record where scores seem too harsh or lenient. |
| **Which first customer segment has urgency?** Lending-tech may adopt faster than traditional NBFCs. | Compare lending vendors, fintech teams, NBFC-facing vendors, and broader AI SaaS teams using concrete willingness to run and internally share the tool. |
| **Does native PDF fit sharing and archival?** Implementation was resolved on 2026-08-11. | Observe readability, fidelity, file size, opening, forwarding, and archival failures; implementation alone does not establish workflow quality. |
| **Open-source or closed core?** An open core may help inspection and adoption. | Compare credible business models and monetization consequences, then make an explicit founder decision; current repository visibility is not established here. |
| **Integrations and business model?** Cleanlab and Evidently interoperability may strengthen Numek. | Choose integration scope deliberately; label-issue methods need appropriate prediction evidence. Pricing options include audits, subscriptions, pilots, services, enterprise licensing, consulting, and white-label workflows; none is selected. |

## Historical Context And Evidence

The original draft proposed a Dataset Quality Explainer and Model Confidence
Auditor, combined into a trust verification layer. It included calibration,
drift, high-confidence errors, SHAP-style explanations, dataset trust scores,
and a combined “Reliability Certificate.” The master context historically
referenced `docs/Numek info first draft.pdf`; that PDF is absent from this
checkout. This summary preserves the prior documented history, not a newly
verified reading of the original source.

Execution initially narrowed to local DataTrust and report-first credibility.
Certificate language became reliability-report language. HTML became canonical;
UI PDF followed later. These choices explain the foundation's development and
do not keep today's product direction confined to its original scope.

Important milestones:

- **2026-06-14:** completed correctness invariants and the initial reproducible
  public corpus/comparison, including the evidence-backed correction that
  `previous_campaign_outcome` is review-only. The initial corpus had seven
  mutations and ten reports; the current corpus has eight and eleven.
- **2026-06-14 and 2026-08-02:** validation environments moved to Python 3.11.15
  and Evidently 0.7.21; package minimum later became Python 3.10+.
- **2026-08-04:** accepted RC_003 technical review and superseded the earlier
  frozen all-gates-pass round involving five practitioners and a separate
  nontechnical reader. Historical forms, candidate IDs, hashes, and packets
  remain evidence, not active release requirements.
- **2026-08-05 to 2026-08-13:** expanded the CLI/API foundation into a guided
  browser workflow, richer evidence, native PDF, target guidance, deterministic
  language, and the current eight-topic report; accepted the completed baseline.
- **2026-10-07:** completed context consolidation and adopted active expansion.
  The previous multi-AI coordination process is superseded.

[Historical review originals](history/reviews/README.md) retain useful technical
reasoning. [Dry-run evidence](../validation/dry_runs/README.md) remains in its
original workspace. Its earlier six-section reports describe that historical
implementation, not the current eight-topic report.

The [returned-review summary](../validation/dry_runs/evidence/RC003_TECHNICAL_REVIEW_SUMMARY.md)
records mismatched informal candidate identifiers and blank historical hash
fields; it is founder-accepted review evidence rather than a formally sealed
protocol result. The two returned HTML reports were inspected from local
Downloads paths and summarized, not copied into the repository. Do not imply
those files are repository artifacts or require a new external review because
of these historical caveats.

## M4 settled decisions (2026-10-10)

The user authorized implementation of split audits, version comparisons and advanced
single-dataset analysis on one DuckDB path. Explicit identifiers and group/identity
keys preserve lexical identity by default. Full accepted task-family support remains
distinct from exhaustive analytical search, with bounded work and explicit coverage.
Per-source and combined limits both apply; disk planning estimates and a monitored
64 GiB workspace ceiling govern owned storage. Performance targets are measured
engineering objectives. Default pandas contracts remain frozen; replacement of the
default engine and guaranteed capacity claims are deferred. See the current state,
architecture, methodology and M4 validation evidence for delivered scope.


## M5 implementation handoff — 2026-10-11

The approved Temporal Reliability Intelligence scope is implemented through temporal-specific contracts, exact clocks, schedule/lifecycle/panel populations, feature-bound timing and revision states, maturity, supplied evaluation plans, configurable behavior and local Python/CLI/browser/report experiences. See [M5 implementation](M5_TEMPORAL_RELIABILITY.md). Existing M1–M4 input contracts and analytical policy are preserved; no founder decision or additional acceptance ceremony is required for this implementation. Resource budgets and threshold defaults are provisional. Verification follows the repository skill, with new evidence in validation/m5 and historical M4 execution/source-only records left distinct.

## M6 implementation handoff — 2026-10-11

The user accepted M1–M5 completion, including M5’s understanding gate, and
authorized implementation of the revised M6 plan. Text Reliability Intelligence
is implemented within DataTrust’s shared supervision, evidence, comparison and
artifact architecture. Python/CLI/guided browser and HTML/PDF/strict JSON support
corpora, annotations/QA/generation, conversations and retrieval provenance.

The revised commitments are retained: calibrated bounded MinHash search,
full-population versus selected-population accounting, exact private evidence
resolution, fatal versus recoverable malformed data and reproducible long-document
embedding windows. Optional models work locally with pinned artifacts. There is
no universal score, cloud dependency or premature modality engine. M6 evidence
and measured limits are in `validation/m6/`; canonical behavior is documented in
`docs/M6_TEXT_RELIABILITY.md`. Historical evidence is unchanged. Internal closure
is distinct from universal methodology validity or external product acceptance.


## M7 implementation handoff — 2026-10-12

The founder authorized the complete replacement M7 plan. The implementation uses
separate image contracts and identities, verified coordinate compatibility,
minimal-copy local source handling, full perceptual signature inventory with
work-bounded search, optional pinned offline CPU models, and private-default
Python/CLI/browser HTML/PDF/JSON. Benchmark failures are retained and shipping
configuration follows the agreed recall/review-burden/resource rules. See
`docs/M7_IMAGE_RELIABILITY.md` and `validation/m7/README.md`. Historical M1–M6
evidence remains valid and preserved; later milestones remain deferred.

## M9 implementation handoff — 2026-10-13

The user accepted M1–M7, deliberately deferred M8 audio and authorized the full
M9 plan. M9 is implemented as connected record/document/text/image reliability,
led by reusable native PDF/DOCX reconciliation. Exact relationships, context/clocks,
competing evidence, declared contamination, opt-in qualified English NLI/paired
image-text and independent reviewer snapshots share the local execution/export
boundaries. The guided 20-record/21-PDF story retains 18 agreements, one discrepancy
and one conflict, including mixed status evidence and exact private locators.

Qualification is narrow: authored financial declarations and supplied COCO
caption-association controls; general semantic validity is not established.
Resource budgets/timings remain provisional. OCR, audio/video, external claim
search, model monitoring, persistent review, automatic correction and global
scores remain excluded. See `docs/M9_CROSS_REPRESENTATION_RELIABILITY.md` and
`validation/m9/README.md`. Historical evidence is preserved; no new approval
ceremony is required.

## ConfidenceGuard CG1 handoff — 2026-10-17

The founder approved the revised CG1 three-task scope and CG1–CG7 direction and
explicitly requested implementation. CG1 is implemented as a separate prediction
evaluation product, with Python/CLI, versioned local JSON transport, a functional
API-only browser client and canonical HTML/PDF/JSON. Authoritative outcomes and
canonical cohorts qualify paired comparisons. Supplied/derived/simulated decisions,
probabilities/native scores, label availability, timing and statistical support
remain explicit. Exact private investigation and conservative shareable projections
are distinct. No universal reliability score is introduced.

Infrastructure reuse uses a narrow private adapter; no `numek_runtime` extraction
or accepted DataTrust analytical migration was made. Existing distribution/commands
are preserved, and M8 audio stays deferred. The independent frontend design lab
can replace the functional client via the bundled versioned contracts.

CG2 calibration/uncertainty and CG3 longitudinal/drift now extend this same product.
CG4 deeper investigation, CG5 policy selection, CG6 execution/robustness and CG7
monitoring/operations remain approved continuation. No hosted service, production ingestion, persistent monitor
or direct-model adapter is claimed in CG1. Capacity, natural-workload usefulness of
defaults and later-method qualification remain evidence questions, not new approval
gates. See [CG1 contracts](CG1_CONFIDENCEGUARD.md) and
[verification](../validation/cg1/README.md). Implementation is ready for founder
review; internal verification does not itself establish founder acceptance.

## ConfidenceGuard CG2 handoff — 2026-10-19

The subsequent user instruction explicitly accepts CG1 and authorizes the complete
CG2 plan. CG2 is implemented inside the existing `confidenceguard` package. It adds
monotone calibration maps, temperature/qualified Dirichlet, exact conformal sets and
intervals, quantile/sample evaluation, paired/cluster inference, safe artifact states,
F/S/C/E separation, frozen common populations and protected membership provenance.
All interfaces use the existing supervised evaluator and canonical report/disclosure
path. Original predictions and model identities remain immutable; applied artifacts
are unvalidated until their own qualifying independent assessment. Assessments do
not establish improvement or future coverage.

CG1 schemas/semantics and DataTrust behavior/history are preserved. CG3 longitudinal
analysis is now implemented in the same product; CG4 automated investigation, CG5
policy optimization, CG6 predictor/auxiliary execution and CG7 monitoring remain future
development milestones. M8 audio remains deferred. See
[CG2 contracts](CG2_CONFIDENCEGUARD.md) and [evidence](../validation/cg2/README.md).
The user has subsequently confirmed CG1 and CG2 complete, independently reviewed,
corrected, and their understanding gates closed. CG3 is complete, including corrections R1–R3, as confirmed by the user on 2026-10-21.

CG3 is complete, including corrections R1–R3, as confirmed by the user on 2026-10-21. See [correction record](../validation/cg3/review-corrections/README.md).
