# Numek Decisions

Last updated: 2026-08-13

Only decisions explicitly approved by Drivyaansh belong here.

## 2026-08-13: Treat DataTrust As The Completed Baseline Without Product-Version Labels

Status: Approved and implemented

Decision:
Treat the current DataTrust classification workflow as the completed product
baseline. Do not organize living documentation, planning, or future chats
around generic sequential product-version labels. Describe work by capability
and status instead. No next product direction is currently approved.

Boundaries:

- preserve real package versions and immutable release identifiers where they
  are required for distribution, compatibility, or historical evidence
- preserve the substance of dated historical records while using
  version-neutral language in documentation
- do not infer the next objective from old roadmaps, proposals, or phase order

Reason:
Generic version labels had spread across documentation and chat context, added
maintenance overhead, and implied a fixed next scope that Drivyaansh has not
chosen.

## 2026-08-13: Harden Target Confirmation And Narrative Presentation

Status: Approved and implemented

Decision:
Use nontechnical prediction-outcome language for advanced confirmation, expose
distinct-value terminology before target selection, describe non-zero feature
missingness below `1%` as minimal before applying the `70%` concentration rule,
render a designed clean-report empty state, and humanize filename-based report
titles.

Boundaries:

- the `1%` rule changes narrative only
- `no_major_issues` remains present in compatibility outputs
- explicit report names and source filenames remain unchanged
- scoring, findings, guardrails, target groups, and subtype inference remain unchanged

## 2026-08-12: Explainable Target Guidance And Layered Report

Status: Approved and implemented

Decision:
Keep target choice explicit while grouping columns with deterministic,
conservative suitability explanations. Do not preselect a target. Require a
server-enforced acknowledgement for advanced choices. Add an uncapped evidence
score without changing any scoring decision, use one deterministic narrative
for both result surfaces, and reorganize the canonical report into eight
decision-to-evidence topics with a landscape technical appendix.

Boundaries:

- target guidance does not become a finding, penalty, or guardrail
- the CLI and Python API still require an explicit target
- existing sub-scores, final scores, risk bands, guardrails, findings, and their
  ordering remain unchanged
- HTML remains canonical and PDF remains its derivative
- no regression, automatic target selection, or new dataset diagnostic is added

Reason:
The prior undifferentiated target dropdown exposed technical ambiguity without
helping a non-technical user understand it. The report also needed a faster
decision layer without sacrificing exact evidence or maintaining a second
interpretation source.

## 2026-06-02: DataTrust Is The First Product

Status: Approved

Decision:
Build DataTrust before ConfidenceGuard and HallucinationGuard.

Reason:
DataTrust has the lowest integration friction and can produce a useful local report without production logs, model endpoints, or hosted infrastructure.

Rejected alternatives:

- Build all three Numek pillars simultaneously
- Start with model monitoring
- Start with LLM hallucination detection

Revisit when:
Drivyaansh chooses a new product objective or strong evidence shows another module has substantially greater urgency.

## 2026-06-02: HTML Is The Canonical Output

Status: Approved

Decision:
Generate HTML reports first. Do not initially require PDF export.

Reason:
HTML is faster to build, inspect, iterate, and share while the report itself is still evolving.

Rejected alternatives:

- Build PDF first
- Build HTML and PDF simultaneously

Revisit when:
Multiple target users explicitly require PDF before they can share or use the report.

Current implementation note:
HTML remains the canonical generated artifact. The local UI now converts that
artifact to a native PDF with WeasyPrint; the CLI and Python API remain
HTML-only, and DataTrust does not generate Word documents.

## 2026-08-11: Compact Result Overview And Native UI PDF

Status: Approved and implemented

Decision:
Make the local result page a concise decision surface showing the overall
score, risk band, highest-priority modeling impact, recommended action, and top
three risks. Keep the complete eight-section HTML report as the evidence
artifact and add a genuine PDF download generated from that HTML with
WeasyPrint.

Boundaries:

- do not embed the full report in the result page
- do not add sub-scores, dataset facts, model algorithms, or regression options
  to the compact overview
- expose native PDF through the browser UI only
- preserve existing scoring, findings, CLI, and Python API contracts
- do not redesign the full report beyond print-specific PDF styling

Reason:
The previous iframe made the local UI feel like the full evidence report rather
than a quick answer. A compact overview establishes a clear presentation layer,
while native PDF matches the intended one-click sharing workflow without
creating a second report-content source.

## 2026-06-02: DataTrust Is Local-First

Status: Approved

Decision:
DataTrust runs locally and does not require uploading datasets to a hosted service.

Reason:
Local execution reduces the largest objection around sensitive datasets and avoids premature cloud infrastructure.

Rejected alternatives:

- Hosted SaaS upload flow
- Cloud dashboard in the initial product

Revisit when:
Real user evidence shows local setup is a larger obstacle than data sensitivity.

## 2026-08-05: Add A Local Browser UI Without Replacing Existing Interfaces

Status: Approved and implemented

Decision:
Make a loopback-only browser UI the guided report-generation surface while
preserving the existing `datatrust audit` CLI and `DataTrust` Python API.

Reason:
CSV upload, target selection, classification subtype confirmation, and report
download are easier to understand as a guided flow than as command-line-only
steps. Local processing preserves the existing privacy boundary.

Boundaries:

- bind to `127.0.0.1` only
- keep jobs temporary and process-scoped
- support classification CSV workflows only
- generate standalone HTML; native UI PDF was added by the later 2026-08-11
  decision
- do not add authentication, hosted persistence, Word export, regression, or
  algorithm selection in this release

Revisit when:
Product evidence supports a hosted, persistent, multi-user, or broader task
workflow.

## 2026-08-05: Expand Evidence Without Changing Validated Scores

Status: Approved and implemented

Decision:
Add a complete ordered findings list and richer dataset evidence while keeping
the existing score formulas, thresholds, guardrails, risk bands, and top-three
`risks` contract unchanged.

Reason:
Users need actionable explanations and technical evidence, but new diagnostics
should not silently affect scores before their scoring behavior is separately
validated.

Current evidence-only findings include feature-identical rows with conflicting
labels and widespread row-level feature missingness. The report presents every
finding in its action plan while retaining the top three for executive use.

Revisit when:
Validation evidence supports promoting a diagnostic into scoring or changing
the established formulas.

## 2026-06-02: Use Transparent Sub-Scores And Guardrails

Status: Approved

Decision:
Use decomposed reliability sub-scores with documented methodology and high-stakes guardrails rather than one opaque trust score.

Reason:
An unexplained score is not defensible. Severe risks such as plausible target leakage must not be washed out by otherwise healthy metrics.

Rejected alternatives:

- Single opaque 0-100 trust score
- Raw metrics without synthesis

Revisit when:
Benchmarking or domain-expert feedback supports a better scoring methodology.

## 2026-06-02: Avoid Certification Language

Status: Approved

Decision:
Use terms such as reliability report, evidence pack, or reliability assessment. Do not call DataTrust output a certificate.

Reason:
Certification implies institutional, regulatory, or legal authority that Numek does not currently have.

Rejected alternatives:

- Reliability Certificate
- Compliance Certificate

Revisit when:
Numek gains appropriate standards alignment, accreditation, institutional backing, or legal review.

## 2026-06-14: Use A Multi-AI Collaboration System

Status: Approved

Decision:
Use ChatGPT and Claude primarily for planning, research, alternatives, and critique; use Codex as repo master, technical owner, implementation agent, verifier, and documentation steward. Drivyaansh remains final decision-maker.

Reason:
Clear roles allow independent thinking and cross-checking without allowing the project to split into conflicting realities.

Rejected alternatives:

- Rely on one AI platform for all work
- Treat all AI outputs as equally authoritative
- Use chat history as canonical project memory

Revisit when:
The collaboration system creates more overhead than value or platform capabilities materially change.

## 2026-06-14: Repo Documents Are Canonical Memory

Status: Approved

Decision:
Use the repository and its documentation as durable project memory. Update living documents frequently and the master context only after major changes.

Reason:
AI chats and uploaded project sources become stale. Repo documents provide a shared, inspectable source of truth.

Rejected alternatives:

- Depend on AI conversational memory
- Update the master context after every minor change

Revisit when:
A more reliable automated synchronization system is introduced.

## 2026-06-14: Earlier Plan Required A Frozen All-Gates-Pass Validation Round

Status: Superseded on 2026-08-04

Decision:
The earlier plan required one frozen release candidate with two warm-network
and three independent ML/data practitioners, at least two practitioner-owned
CSV runs, three public datasets, and one separate non-technical comprehension
reviewer.

Reason:
At the time, initial product credibility was framed around formal external validation.

Superseded by:
`2026-08-04: Remove Mandatory External Practitioner Review And Prioritize Product Building`.

Historical preservation:
The old dry-run materials, RC_003 candidate files, hashes, packet, and returned
technical-review evidence remain preserved as historical evidence. They are no
longer active acceptance gates.

## 2026-08-04: Remove Mandatory External Practitioner Review And Prioritize Product Building

Status: Approved

Decision:
Permanently remove the mandatory external technical-review process involving
five ML practitioners from active milestones, blockers, and acceptance gates.
Technical review, product review, and acceptance review required during
development will be conducted internally by Drivyaansh and Codex.

Reason:
Numek is moving from review-process design back into product building. External
review can be useful for learning, but it is no longer a mandatory condition
for product progress or acceptance.

Preserved evidence:
RC_003 has completed its founder-accepted technical review and remains
historical evidence. RC_003 files, hashes, packets, reports, and returned
review evidence must not be deleted or rewritten to fit the new process.

Rejected alternatives:

- Keep the five-practitioner validation round as the product exit gate
- Replace the five-practitioner review with another mandatory external review
- Treat unresolved external product-validation questions as resolved

Revisit when:
Drivyaansh explicitly chooses to run external discovery, advisory review, sales
pilots, or customer validation as learning activities rather than as mandatory
acceptance gates.
