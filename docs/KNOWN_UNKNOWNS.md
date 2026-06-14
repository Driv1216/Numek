# Numek Known Unknowns

Last updated: 2026-06-14

These questions require evidence, not more confident opinions.

## Do ML Leads Find The Reliability Report Useful?

Current belief:
An ML/data lead needs a shareable artifact that explains dataset risks to non-technical stakeholders.

Why it matters:
If the report does not fit a real workflow, DataTrust is only an interesting profiler.

Resolution method:
Have ML/data practitioners run or review DataTrust and explain what they would use, ignore, remove, or forward.

Evidence required:
At least five detailed reactions, including at least one run on a dataset not created by Numek.

Status:
Unresolved

## Is Local-First A Selling Point Or Friction?

Current belief:
Local-first reduces sensitive-data objections, especially in regulated or high-stakes domains.

Why it matters:
The CLI and local environment setup may create onboarding friction.

Resolution method:
Compare preferences for CLI, notebook, Docker, local web app, customer-cloud, and hosted upload.

Evidence required:
Workflow preferences and reasons from at least five target users.

Status:
Unresolved

## Is The Leakage Heuristic Accurate Enough?

Current belief:
The heuristic catches obvious outcome-like column names but may create false positives across unfamiliar domains.

Why it matters:
Incorrect high-risk leakage warnings can destroy trust in the report.

Resolution method:
Run DataTrust on multiple public datasets and have flagged columns reviewed by humans.

Evidence required:
A benchmark containing flagged columns, reviewer judgments, and reasons.

Status:
Unresolved

## Do The Scoring Weights And Guardrails Feel Defensible?

Current belief:
Transparent scoring and leakage guardrails are directionally correct, but current weights are not externally validated.

Why it matters:
The score is a prominent product output and must align with expert judgment.

Resolution method:
Compare DataTrust scores against human risk assessments and adjacent tools.

Evidence required:
At least ten reviewed reports or a smaller benchmark with strong expert review.

Status:
Unresolved

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
Unresolved

## Is HTML Sufficient Before PDF?

Current belief:
HTML is sufficient for V1 iteration.

Why it matters:
Some stakeholders may require PDF for review or evidence workflows.

Resolution method:
Ask report reviewers how they would share and archive the report.

Evidence required:
Multiple explicit requests for PDF before changing the V1 requirement.

Status:
Unresolved

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

