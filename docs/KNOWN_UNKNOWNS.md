# Numek Known Unknowns

Last updated: 2026-08-13

These questions require evidence, not more confident opinions. None of these
questions determines the next product direction or blocks use of the completed
DataTrust baseline.

## Do ML Leads Find The Reliability Report Useful?

Current belief:
An ML/data lead needs a shareable artifact that explains dataset risks to non-technical stakeholders.

Why it matters:
If the report does not fit a real workflow, DataTrust is only an interesting profiler.

Resolution method:
Collect reactions from ML/data practitioners, target users, advisors, or early
customers when such conversations naturally happen.

Evidence required:
Detailed reactions about what they would use, ignore, remove, trust, or forward.

Status:
Deferred and non-blocking

## Is Local-First A Selling Point Or Friction?

Current belief:
Local-first reduces sensitive-data objections, especially in regulated or high-stakes domains.

Why it matters:
Python installation and local environment setup may still create onboarding
friction even though the guided browser UI removes most command-line report
configuration.

Resolution method:
Observe whether users can install DataTrust, start `datatrust ui`, and complete
the guided flow; compare that experience with preferences for a notebook,
Docker, customer-cloud, or hosted upload.

Evidence required:
Workflow preferences and reasons from target users or technical buyers.

Status:
Deferred and non-blocking

## Is The Leakage Heuristic Accurate Enough?

Current belief:
The heuristic catches obvious outcome-like column names but may create false positives across unfamiliar domains.

Why it matters:
Incorrect high-risk leakage warnings can destroy trust in the report.

Resolution method:
Run DataTrust on multiple public or real-world-style datasets and review flagged columns manually.

Evidence required:
A benchmark containing flagged columns, reviewer judgments, and reasons.

Status:
Deferred and non-blocking

## Do The Scoring Weights And Guardrails Feel Defensible?

Current belief:
Transparent scoring and leakage guardrails are directionally correct, but current weights are not externally validated.

Why it matters:
The score is a prominent product output and must align with expert judgment over time.

Resolution method:
Compare DataTrust scores against internal judgment, public examples, future user feedback, and adjacent tools.

Evidence required:
Reviewed reports or report examples showing where the score feels right, too harsh, or too lenient.

Status:
Deferred and non-blocking

## Is Lending-Tech The Best First Customer Segment?

Current belief:
Lending-tech vendors may move faster than traditional NBFCs and need reliability evidence for enterprise buyers.

Why it matters:
The first segment determines language, checks, report design, and distribution.

Resolution method:
Compare urgency and workflow fit across lending-tech vendors, fintech ML teams, and broader AI SaaS teams.

Evidence required:
Concrete willingness to run the tool and share the report internally.

Status:
Deferred and non-blocking

## Resolved: Native PDF Is Required In The Browser UI

Decision:
The local browser UI provides a direct native PDF download generated from the
canonical HTML report. Browser print/save is no longer the product PDF path.

Why it matters:
The founder/co-founder product direction calls for a small UI overview and a
downloadable full PDF report.

Resolution method:
Observe whether the generated PDF fits real sharing and archival workflows.

Evidence required:
Feedback about PDF readability, fidelity, file size, and forwarding behavior.

Status:
Resolved for implementation on 2026-08-11; downstream workflow quality remains
an evidence question, not a product-scope blocker.

## Should Numek Open-Source The Core?

Current belief:
An open-source core may accelerate credibility and inspection, but the business-model consequences are unresolved.

Why it matters:
Trust, adoption, community feedback, and future monetization may all depend on this choice.

Resolution method:
Compare open-source business models and discuss the tradeoff with potential users and advisors.

Evidence required:
A deliberate founder decision informed by credible examples and Numek's likely revenue path.

Status:
Unresolved
