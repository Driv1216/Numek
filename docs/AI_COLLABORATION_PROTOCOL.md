# Numek AI Collaboration Protocol

Last updated: 2026-06-14  
Status: Active  
Owner and final decision-maker: Drivyaansh  
Repository/documentation steward and technical verifier: Codex

## Purpose

Numek uses three AI platforms to improve planning, challenge assumptions, broaden ideas, implement the product, and cross-check decisions:

- ChatGPT app
- Claude
- Codex

The goal is not to make all three systems agree. The goal is to use their different strengths, expose uncertainty through disagreement, and resolve important questions through evidence.

All three systems must work from one shared project reality. The Numek repository is that reality.

## Core Operating Principle

```text
Propose -> Critique -> Verify -> Decide -> Record -> Build -> Test -> Update Context
```

An AI suggestion is not automatically a Numek decision.

Only verified facts and decisions approved by Drivyaansh become canonical project truth.

## Roles

### Drivyaansh: Founder And Final Authority

Drivyaansh:

- defines objectives and success criteria
- chooses priorities
- approves strategic and product decisions
- decides when evidence is sufficient
- resolves disagreements that are preferences rather than factual questions
- prevents planning from replacing building

No AI consensus overrides the founder's decision.

### Codex: Repo Master, Technical Owner, And Verifier

Codex has access to the working repository and is responsible for:

- inspecting actual code, tests, artifacts, and documentation
- implementing approved plans
- running tests and verifying behavior
- reviewing architecture and technical consequences
- cross-checking proposals from ChatGPT and Claude against repo reality
- maintaining living project documentation from verified evidence
- recording approved decisions
- identifying contradictions between docs and implementation

Codex may independently record verified technical facts. Codex must not silently approve strategic decisions on behalf of Drivyaansh.

### ChatGPT App: Product Strategy And Research Partner

ChatGPT is primarily used for:

- product and company strategy
- market and customer research
- business model exploration
- roadmap alternatives
- academic and research directions
- synthesizing complex ideas
- creating structured proposals

Expected outputs should include:

- proposal
- assumptions
- supporting evidence
- alternatives
- risks
- recommended next step

### Claude: Adversarial Reviewer And Alternative Thinker

Claude is primarily used for:

- attacking assumptions
- identifying missing evidence
- exposing scope creep
- finding failure modes
- reviewing positioning and strategy
- proposing meaningfully different alternatives
- checking documents for contradictions

Expected outputs should include:

- strongest arguments against
- hidden assumptions
- failure scenarios
- missing evidence
- alternative proposal
- verdict

### Role Rotation

Roles are defaults, not permanent restrictions.

For major decisions, all three systems may independently analyze the same problem without seeing the others' answers. Disagreements should be investigated rather than settled by majority vote.

## Source Of Truth Hierarchy

When sources disagree, use this hierarchy:

```text
1. Actual repo code, tests, generated artifacts, and verified external evidence
2. Drivyaansh's latest explicitly approved decision
3. CURRENT_STATE.md
4. DECISIONS.md, ROADMAP.md, and KNOWN_UNKNOWNS.md
5. NUMEK_MASTER_CONTEXT.md
6. Current chat conversation
7. Older chat conversations and unapproved AI proposals
```

Chats are temporary thinking rooms. They are not canonical project memory.

## Types Of Project Information

### Verified Truth

Examples:

- code that exists
- tests that passed
- generated reports
- measured benchmark results
- user interview findings
- explicitly approved decisions

Verified truth belongs in canonical repo documentation.

### Working Assumptions

Examples:

- local-first will be attractive to buyers
- ML leads will share reliability reports
- lending-tech is the best initial customer segment
- transparent scoring will create sufficient credibility

Working assumptions belong in `KNOWN_UNKNOWNS.md` with a resolution method and required evidence.

### Ideas And Proposals

Examples:

- add PDF export
- integrate Cleanlab
- open-source the core
- target healthcare
- build ConfidenceGuard early

Ideas remain proposals until reviewed and approved. They must not silently become roadmap commitments.

## Decision Classes

### Small Decisions

Examples:

- helper function names
- isolated bug fixes
- minor report styling
- small internal refactors

Codex may handle these directly while preserving existing architecture and documenting meaningful outcomes.

### Medium Decisions

Examples:

- adding JSON output
- changing report structure
- integrating Cleanlab
- changing scoring weights

Recommended flow:

```text
ChatGPT or Claude proposal -> Codex technical review -> Drivyaansh approval -> Codex implementation
```

### Major Decisions

Examples:

- changing the target customer
- choosing open-source vs closed-source
- starting ConfidenceGuard
- changing the company thesis
- introducing SaaS
- setting pricing strategy

Required flow:

```text
Independent proposals -> adversarial review -> repo/technical verification
-> Drivyaansh decision -> DECISIONS.md -> implementation
```

## Canonical Documents And Update Cadence

### `NUMEK_MASTER_CONTEXT.md`

Purpose: stable project constitution, history, company thesis, product identity, boundaries, and long-term direction.

Update only after major changes, such as:

- company or product thesis changes
- DataTrust moves from V1 to V2
- a major new phase starts
- the target user fundamentally changes
- ConfidenceGuard or HallucinationGuard development begins
- core positioning or identity boundaries change

Do not update it for every feature, test, or small implementation decision.

### `CURRENT_STATE.md`

Purpose: frequently updated operational truth.

Update after meaningful implementation work with:

- what currently works
- latest verified tests and artifacts
- current milestone
- active limitations
- immediate next task

### `DECISIONS.md`

Purpose: record approved decisions and prevent settled questions from being reopened without evidence.

Each decision should include:

```md
## YYYY-MM-DD: Decision title

Status: Approved

Decision:
What was decided.

Reason:
Why it was decided.

Rejected alternatives:
- Alternative

Revisit when:
Specific new evidence or condition that justifies reopening the decision.
```

Only decisions explicitly approved by Drivyaansh should be recorded as approved.

### `KNOWN_UNKNOWNS.md`

Purpose: track questions requiring evidence rather than opinion.

Each item should include:

```md
## Unknown

Current belief:
What we currently suspect.

Why it matters:
Why resolving it affects Numek.

Resolution method:
How it will be tested.

Evidence required:
What would be sufficient to resolve it.

Status:
Unresolved / In progress / Resolved
```

### `ROADMAP.md`

Purpose: current priorities, phase gates, and sequencing.

It should clearly state:

- current phase
- current objective
- exit gate
- immediate priorities
- blocked future phases

Avoid speculative feature dumping.

### `AI_COLLABORATION_PROTOCOL.md`

Purpose: define how Drivyaansh, Codex, ChatGPT, and Claude work together.

Update rarely, only when the collaboration process itself changes.

## New Chat And Source Freshness Workflow

Do not create a new chat after every small code change.

Start a new planning/review chat when:

- beginning a new meaningful objective
- existing conversation context has become stale or confused
- a major implementation cycle completed
- a strategic question needs independent analysis
- project sources have materially changed

Before starting an important new ChatGPT or Claude chat:

1. Finish or pause the current implementation cycle clearly.
2. Ask Codex to verify the repo.
3. Update `CURRENT_STATE.md`.
4. Record approved decisions in `DECISIONS.md`.
5. Update `KNOWN_UNKNOWNS.md` and `ROADMAP.md` if needed.
6. Update `NUMEK_MASTER_CONTEXT.md` only if a major shift occurred.
7. Replace stale project-source uploads in ChatGPT and Claude.
8. Start the chat with a role-specific, task-specific kickoff prompt.

The master context remains available in project sources for stable background. The living docs and kickoff prompt explain where the project is right now and what must happen next.

## Standard New Chat Kickoff Template

```text
Read the attached Numek project sources before responding.

Source hierarchy:
- Treat CURRENT_STATE.md as the latest verified operational state.
- Treat DECISIONS.md as approved decisions.
- Treat ROADMAP.md as the current sequence and priorities.
- Treat KNOWN_UNKNOWNS.md as unresolved evidence questions.
- Treat NUMEK_MASTER_CONTEXT.md as stable background and project identity.

Your role in this chat:
[Product strategist / adversarial reviewer / research analyst / technical reviewer]

Objective:
[One specific objective]

Expected output:
[Proposal / critique / alternatives / risks / acceptance criteria]

Constraints:
- Do not reopen approved decisions without new evidence.
- Do not treat unapproved ideas as project commitments.
- Identify assumptions explicitly.
- Separate evidence questions from preference decisions.
```

## Handoff Format Between AI Platforms

Use a structured handoff instead of pasting entire conversations:

```md
# Handoff

## Objective
The specific decision or task.

## Why
Why it matters now.

## Current State
Relevant verified facts.

## Approved Decisions
Constraints that must be respected.

## Proposed Change
The proposal being reviewed.

## Open Questions
What remains unresolved.

## Requested Role
What this AI should do.

## Required Output
The exact deliverable expected.
```

Important proposals, critiques, or evidence from ChatGPT and Claude must be brought back to Codex through a handoff so they can be checked against the repository.

## Resolving Disagreement

When AIs disagree, do not ask only which AI is correct.

Ask:

1. What assumption causes the disagreement?
2. Can the repo answer it?
3. Can external research answer it?
4. Can a small experiment answer it?
5. Is it a preference Drivyaansh must decide?

If evidence can resolve the disagreement, record it as a known unknown and design the smallest useful test.

AI agreement is not proof. All systems may share the same incorrect assumption.

## Documentation Responsibilities

Codex acts as the repo documentation steward.

After meaningful implementation work, Codex should:

1. inspect the resulting repo state
2. run relevant tests and inspect artifacts
3. update `CURRENT_STATE.md` with verified facts
4. record decisions already approved by Drivyaansh
5. update known unknowns and roadmap status when evidence changed
6. update the master context only after major shifts
7. verify that documentation does not contradict implementation

Codex cannot automatically see conversations in ChatGPT or Claude. Drivyaansh must bring important outputs back as handoffs.

## Security And Sensitive Information

ChatGPT and Claude projects are cloud environments. Do not upload:

- real customer datasets
- credentials or secrets
- personally identifiable information
- regulated financial or health data
- proprietary code or documents unless explicitly considered safe to share

Use sanitized summaries and synthetic datasets for planning. Keep sensitive execution local whenever possible.

## Anti-Patterns To Avoid

- asking all three AIs vague questions and choosing the most impressive answer
- treating AI consensus as proof
- reopening settled decisions without new evidence
- allowing stale uploaded sources to define current state
- letting unapproved proposals enter the roadmap
- updating the master context for every minor change
- spending more time coordinating AIs than building Numek
- using planning documents as a substitute for evidence

## Weekly Operating Rhythm

A useful default rhythm:

```text
Monday: Choose one measurable objective.
Tuesday-Wednesday: Build and test with Codex.
Thursday: Inspect results and update living docs.
Friday: Use ChatGPT for implications/options and Claude for adversarial review.
Weekend: Drivyaansh decides, approved outcomes are recorded, and the next objective is chosen.
```

Weekly review questions:

- What did we learn?
- What did we decide?
- What did we build?
- What evidence changed our beliefs?
- What is the single most important next step?

If the answers are mostly documents and ideas for several weeks, the system is producing motion instead of progress.

