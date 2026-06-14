# Numek Decisions

Last updated: 2026-06-14

Only decisions explicitly approved by Drivyaansh belong here.

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
DataTrust reaches its V1 exit gate or strong external evidence shows another module has substantially greater urgency.

## 2026-06-02: HTML Is The Canonical V1 Output

Status: Approved

Decision:
Generate HTML reports first. Do not require PDF export for V1.

Reason:
HTML is faster to build, inspect, iterate, and share while the report itself is still evolving.

Rejected alternatives:

- Build PDF first
- Build HTML and PDF simultaneously

Revisit when:
Multiple target users explicitly require PDF before they can share or use the report.

## 2026-06-02: DataTrust Is Local-First

Status: Approved

Decision:
DataTrust V1 runs locally and does not require uploading datasets to a hosted service.

Reason:
Local execution reduces the largest objection around sensitive datasets and avoids premature cloud infrastructure.

Rejected alternatives:

- Hosted SaaS upload flow
- Cloud dashboard as V1

Revisit when:
Real user evidence shows local setup is a larger obstacle than data sensitivity.

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
Use terms such as reliability report, evidence pack, or reliability assessment. Do not call V1 output a certificate.

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

## 2026-06-14: V1 Requires A Frozen All-Gates-Pass Validation Round

Status: Approved

Decision:
Validate one frozen release candidate with two warm-network and three
independent ML/data practitioners, at least two practitioner-owned CSV runs,
three public datasets, and one separate non-technical comprehension reviewer.
Every V1 gate must pass; `3/5` or any gate-level failure is a failure, not a
conditional pass. Scoring, profiling, risk-summary, or report-content changes
invalidate the active practitioner validation round.

Reason:
V1 credibility depends on reproducible evidence, blinded manual-first
assessment, score defensibility, and report comprehension rather than feature
count or visual polish.

Rejected alternatives:

- Conditional V1 pass
- Showing DataTrust output before reviewers record manual expectations
- Treating an adjacent-tool comparison as a V1 pass gate
- Continuing a validation round after report-content or scoring changes

Revisit when:
The frozen validation process has been completed and its evidence supports a
different validation design.
