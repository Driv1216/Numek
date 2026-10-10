# Explanation Output Contract

The final explanation should feel like a guided technical walkthrough, not a generated report template. Adapt depth to project size, but preserve the learning order.

For a medium or large repository, **do not merge major sections simply to shorten the answer**. If necessary, continue in multiple clearly labeled parts rather than removing domain teaching, tech-stack explanation, repository anatomy, important-file coverage, or source-code journeys.

## Language and teaching style

Write in clear, natural, mid-level engineering language.

Assume the user understands programming basics but does not yet understand this repository and may not know its specialist domain.

Use this pattern repeatedly:

**idea → why it exists here → where it lives → how it connects → concrete example**

Technical vocabulary is welcome. Explain a term briefly the first time it matters instead of avoiding it.

Do not use childish metaphors. Do not use unexplained acronym chains. Do not make every paragraph a bullet list.

## Required teaching order

### 1. Project in one minute

Give a compact mental model before detail:

- what the project is;
- who/what uses it;
- the central problem it solves;
- the core input → processing → output story;
- the most important distinction or idea to understand before reading the rest.

### 2. Start from zero: what is this project?

Explain the project as though the user has opened it for the first time.

Describe the real-world/product problem before architecture.

Explain what the user/operator/developer actually gives the system and what they expect back.

### 3. Problem it is trying to solve

Explain why the project exists and what difficulty it addresses.

Separate repository evidence from marketing language or aspirational README wording.

### 4. Domain Primer

Include this when specialized domain knowledge is required.

Teach the concepts **before** later sections rely heavily on them.

For each important concept:

- what it means;
- why it matters here;
- where it appears in this project;
- what nearby concept it is easy to confuse it with.

If the repository uses named scanners, standards, protocols, security catalogues, scoring systems, model types, infrastructure concepts, or other specialist tools, explain what category of thing each one is and its specific role here.

For a specialized medium/large repository, a primer of roughly **5–12 meaningful concepts** is usually appropriate. Use fewer or more only when the project warrants it.

Do not turn this into a generic course on the field.

### 5. What it can do right now

Describe current capabilities from the user/caller perspective first.

For each important capability, briefly explain how the system fulfills it and the important limitation/boundary if one exists.

### 6. Current implementation state

Provide an explicit current-state classification for the important capabilities.

Use these labels when applicable:

- **Implemented**
- **Partially implemented**
- **Documented only**
- **Scaffold/stub**
- **Not found**
- **Uncertain**

A compact table is appropriate here when it improves clarity.

Do not hide this classification inside prose spread across the rest of the answer.

### 7. What it does NOT currently do

Include omissions that matter because docs, UI, naming, nearby code, or the domain could easily make the user assume the capability exists.

This is not a wishlist and must not contain recommendations.

### 8. Core concepts to understand first

Teach the project's own domain and architectural concepts before the tech-stack inventory.

Examples: finding, issue, snapshot, artifact, chunk, embedding run, application version, engagement, policy, job, workspace, evidence, control, priority, lifecycle.

Use the project's actual concepts, not generic placeholders.

Explain important pairs that sound similar but mean different things.

### 9. Tech stack — and why each piece exists here

This section is required for non-trivial projects and must not be reduced to a shallow dependency list.

Group major technologies by role when useful:

- language/runtime;
- frontend/UI;
- API/server;
- database/persistence;
- container/runtime isolation;
- scanners or external CLI tools;
- authentication;
- external APIs/intelligence sources;
- AI/ML/model providers;
- reporting/rendering;
- build/test tooling.

For each major technology, explain:

- what it is;
- what role it plays **in this project**;
- where it is configured/invoked;
- which project parts interact with it;
- whether it is required, optional, conditional, or development-only;
- why the project needs that category of technology.

Avoid shallow rows such as “FastAPI = backend” or “PostgreSQL = database” without context.

### 10. Repository anatomy

Walk from top-level directories into important subsystems.

Show a compact first-party tree when helpful.

For every major directory/subsystem, explain:

- why it exists;
- what responsibility belongs there;
- what it talks to;
- what kinds of files the user will find inside.

For a medium/large repository, this must be more than one summary paragraph.

Group generated data, fixtures, repetitive tests, and vendor content rather than wasting attention on them.

### 11. Important files and what they actually do

Identify the architecturally meaningful files.

For each important file or tightly related group, explain:

- why the file exists;
- who calls/imports it;
- what it calls;
- important functions/classes/routes it owns;
- what input/data it receives;
- what output/state it produces;
- when the user would open this file to understand the project.

For a medium/large repository, aim for enough coverage to represent every major subsystem. Roughly **8–20 important files/groups** is often reasonable, but architecture matters more than hitting a number.

Do not dump every filename. Do not reduce the map to “open these three files first.”

### 12. How all the pieces connect

Explain dependency and communication relationships in prose before or alongside diagrams.

Make boundaries explicit: which component calls which, what crosses the boundary, and what comes back.

Explain which layers are shared by multiple entrypoints such as CLI and web UI.

### 13. How the project starts and runs

Explain the developer/runtime story:

- relevant run commands or scripts;
- entrypoints;
- initialization;
- configuration/env loading;
- route/worker registration;
- database/model/external connections;
- frontend/backend relationship if applicable;
- persistent state versus in-memory state.

Do not present unexecuted commands as proof that the project currently boots successfully.

### 14. Diagrams

Use the selection rules from `diagram-guide.md`.

At minimum for a non-trivial application, aim to cover:

- system context;
- major runtime architecture;
- code/layer relationships;
- data flow;
- important runtime feature flow;
- startup/execution flow.

Add database/state/auth/deployment/AI/async/security-boundary diagrams only when they improve understanding.

Every diagram should be followed by a short explanation of how to read it and what question it answers.

### 15. Trace real features through the source code

This is a **teaching section**, not merely a diagram section.

For a medium or large project, trace **2–4 materially different important capabilities** through actual files and symbols.

For each journey:

1. state what the user/system does;
2. identify the real entrypoint;
3. name the relevant file and function/class/handler at each important hop;
4. explain what that symbol is responsible for in plain language;
5. explain what data enters and leaves the hop;
6. identify storage/external-tool/network boundaries;
7. explain the final result or state change.

A good walkthrough sounds like:

> The user clicks X in `...`. That sends Y to the endpoint implemented by `file.py:function`. That handler validates ..., then calls `service.py:run_scan`, whose job is to .... The service invokes ..., receives ..., converts it into ..., stores it through ..., and the UI later reads ... .

Do not stop at:

`UI → API → service → database`.

Do not skip directly from a filename to the next filename without teaching the responsibility of the important symbol inside it.

### 16. Data model and lifecycle

Include when applicable.

Explain the important entities/data products and how they relate, then explain any meaningful lifecycle/state machine.

Cover:

- where important data is created;
- how its shape changes;
- where it is persisted;
- what is kept only in memory;
- important identifiers/relationships;
- important states and transitions;
- which schema/model/storage files own these concepts.

Do not skip this section when the repository clearly has lifecycle/state modules or stateful workflows.

### 17. Questions a knowledgeable reviewer, teammate, client, interviewer, or professor is likely to ask

Generate **5–10 project-specific questions** based on the repository's actual design, non-obvious choices, boundaries, or likely confusion points.

Answer every question immediately.

Prefer questions such as:

- Why does this project need X instead of simply Y?
- Where does matching/ranking/authentication/scanning actually happen?
- Is feature Z really implemented or only planned?
- What is the difference between two project-specific concepts that look similar?
- Why is a particular state/version/run stored separately?
- Which part is responsible for correctness/security/persistence?

Avoid filler questions whose answers are obvious from the tech-stack list.

### 18. Project Glossary

Near the end, include a concise glossary of important:

- acronyms;
- domain terminology;
- protocols;
- standards;
- technologies;
- tools/scanners;
- project-specific terms.

Only include terms that actually appear in or materially relate to the project.

The glossary is a reference recap; it does **not** replace teaching important concepts earlier.

### 19. Common misconceptions

Provide a concise set of likely misunderstandings in the form:

**Misconception:** …

**Actually:** …

Base them on real architectural/domain ambiguities in this repository.

### 20. Unknowns and things not proven

List meaningful gaps honestly.

Examples:

- a config exists but no active consumer was found;
- docs claim a feature but the current path was not located;
- a service exists but appears unreachable;
- runtime health was not tested;
- an external dependency's behavior cannot be established from the repository alone.

Do not invent uncertainty merely to populate the section.

### 21. If you remember only this

End with a compact mental model of roughly 3–7 ideas that reconstruct the whole project.

The user should be able to use this recap to explain the project aloud.

## Coverage check before finishing

For a medium or large project, do not finish until all of these are true:

- the domain primer taught unfamiliar concepts before relying on them;
- the tech stack has a dedicated explanation;
- every major first-party subsystem appears in repository anatomy;
- architecturally important files are explained beyond filenames;
- current implementation status is explicit;
- at least 2 materially different feature journeys are traced when available;
- important data/state/lifecycle concepts are explained when present;
- diagrams answer distinct questions;
- unknowns and docs/code contradictions are visible.

If the answer would become too long, split the explanation into parts rather than silently dropping these sections.

## Formatting guidance

- Use headings to create a learning progression.
- Prefer cohesive paragraphs over endless nested bullets.
- Use tables only when comparison genuinely improves comprehension.
- Use inline code for real files, commands, types, routes, and identifiers.
- Keep paths exact when they matter, but do not repeat long paths unnecessarily.
- For large projects, summarize repetitive areas and go deep on architecturally important paths.
- Preserve depth on domain concepts, architecture, connections, important files, feature traces, and diagrams before spending space on peripheral files.

## Things that must NOT appear unless separately requested

- feature ideas;
- improvement suggestions;
- refactor recommendations;
- architecture redesigns;
- performance optimization proposals;
- security recommendations;
- “future scope”;
- implementation plans;
- unsolicited code changes.

The purpose of this skill is **understanding the present system**, not steering its future.
