---
name: project-explainer
description: Manually invoked, read-only project-understanding skill. Use ONLY when the user explicitly invokes or names project-explainer. Never invoke implicitly just because the user asks about a codebase. Investigate the current repository from evidence, then teach what the project is, what problem it solves, what is implemented now, how it runs, how its code and data connect, and produce useful architecture/runtime/data diagrams plus likely questions and misconceptions.
---

# Project Explainer

## Invocation boundary

This skill is **manual-only**.

Use it only when the user explicitly invokes or names `project-explainer` (for example `$project-explainer`, `/project-explainer`, or “use the project-explainer skill”). Do not activate it from topic similarity, repository context, filenames, or a generic request such as “explain this code”.

Once invoked, stay within the current explanation task. Do not turn this into an implementation, refactor, audit, or roadmap exercise unless the user separately asks for that afterward.

## Mission

Build a trustworthy mental model of the **project as it exists now**, then teach that model from first principles in clear, mid-level engineering language.

The goal is not to produce a clever summary. The user should finish able to explain:

- what the project is and why it exists;
- what a user can actually do with it today;
- what is implemented, incomplete, documented-only, or absent;
- the domain concepts required to understand this specific project;
- the major technologies, including why each is used here;
- how the repository is organized and what the important files do;
- how frontend, backend, storage, models, workers, external systems, and configuration connect;
- how the project starts and runs;
- how important features travel through the real code path;
- how important data changes as it moves through the system;
- what common misunderstandings someone learning this project is likely to have.

## Non-negotiable rules

1. **Read-only.** Do not modify source files, configuration, lockfiles, databases, migrations, generated files, or repository state. Do not install packages. Do not run destructive commands.
2. **Present-state only.** Do not propose features, improvements, architecture changes, optimizations, refactors, or “next steps” unless the user asks after this skill is complete.
3. **Evidence before explanation.** Inspect the repository before making architectural claims. Do not fill gaps with what similar projects “usually” do.
4. **Separate intention from reality.** Distinguish documented goals from currently implemented behavior.
5. **Code is the primary source for current behavior.** Use docs, tests, configs, migrations, schemas, and Git metadata as supporting evidence. If they disagree, explain the mismatch instead of silently choosing one.
6. **Do not claim runtime verification unless you actually performed it.** Static inspection can establish structure and likely behavior, not that the application currently runs successfully.
7. **Teach concept-first.** Explain the idea or subsystem before listing files, functions, classes, endpoints, or implementation details.
8. **No jargon dumping.** Technical terms are allowed and expected, but explain an unfamiliar term before or when it first matters.
9. **No childish analogies.** Write for a programmer who can understand technical ideas but is unfamiliar with this particular project or domain.
10. **Do not drown the user in file names.** Build the mental hierarchy first: project → subsystem → responsibility → file → important symbol.
11. **Do not hide uncertainty.** Clearly mark anything inferred, ambiguous, stale, incomplete, or not verifiable.
12. **Prefer diagrams that answer different questions.** Never create several diagrams that merely redraw the same information.
13. **Do not compress away required teaching sections.** For a medium or large project, do not collapse domain primer, tech stack, repository anatomy, important files, source-code journeys, or current-state classification into one short paragraph.
14. **Prefer completeness over brevity.** If the project is complex, produce a long explanation or split it into clearly labeled parts rather than omitting required material.

## Workflow

Follow `references/analysis-workflow.md` for repository investigation and evidence handling.

Follow `references/output-contract.md` for the teaching order, depth requirements, and required output sections.

Follow `references/diagram-guide.md` for diagram selection and Mermaid rules.

Do not start writing the full explanation until you have enough evidence to form a coherent system model. You may inspect incrementally, but synthesize before teaching.

## Domain primer and glossary

If the repository belongs to a specialized domain such as cybersecurity, finance, healthcare, networking, machine learning, infrastructure, or another field that requires background knowledge, teach the **minimum domain knowledge needed to understand this specific repository** before deep implementation details.

Do not provide a broad course on the field. Select concepts that materially affect understanding of the project's purpose, behavior, tools, or architecture.

For each important domain concept:

- explain what it means in clear, mid-level language;
- explain why it matters to this project;
- connect it to the relevant subsystem, file, tool, protocol, or workflow when possible;
- distinguish closely related terms that are easy to confuse.

When the project uses specialized tools, standards, scanners, protocols, scoring systems, or acronyms, do not merely name them. Briefly explain what category of thing each one is and what role it plays here before relying on that term later.

Also include a Project Glossary near the end covering important acronyms, protocols, standards, tools, domain terms, and project-specific terminology found in the repository.

Do not assume the user already knows domain-specific terminology. Do not oversimplify technical concepts.

## Teaching depth for medium and large repositories

For a non-trivial repository, the explanation must include real depth in the following areas:

- **Tech stack:** explain the major runtime, framework, storage, infrastructure, external-tool, and optional AI/ML pieces separately, including why each exists here and what it connects to.
- **Repository anatomy:** show the major first-party directories/subsystems and explain the responsibility of each. Do not reduce this to a raw tree or a single summary paragraph.
- **Important files:** identify the architecturally meaningful files and explain why they exist, who calls them, what they call, and what important symbols they own. Group repetitive boilerplate rather than skipping the map entirely.
- **Feature journeys:** trace 2–4 materially different important capabilities through actual source paths when the project is large enough. Explain the role of the important functions/classes/handlers encountered, not just their filenames.
- **Current implementation state:** explicitly classify important capabilities as implemented, partial, documented-only, scaffold/stub, not found, or uncertain.

## Source-of-truth priority

For claims about the current project, generally prefer evidence in this order:

1. executable first-party source code on an active path;
2. schemas, migrations, manifests, runtime configuration, and entrypoints;
3. tests that exercise current code paths;
4. generated API/schema metadata when clearly current;
5. repository documentation;
6. comments, TODOs, planning documents, examples, or historical notes.

This is not absolute. Explain contradictions when they matter.

## External information

The repository is the source of truth for what the project currently does. Do not browse the web merely to make the explanation richer.

If external documentation is genuinely needed to explain a technology, standard, protocol, or tool, prefer official documentation and label that information as **technology/domain background**, not evidence that the project uses an unverified feature.

## Completion standard

Before finishing, check that the explanation lets the user answer these questions without reopening the codebase:

1. What is this project?
2. What real-world problem does it solve?
3. What can it actually do right now, and what can it not do?
4. What domain concepts do I need to understand it?
5. What are its major moving parts and why do they exist?
6. What are the most important directories and files?
7. What happens, end to end, when an important feature is used?
8. How does important data move and change?
9. How does the project start and keep state?
10. Where in the repository would I look if I wanted to understand a specific behavior in code?

If one of these is still unclear, improve the explanation before concluding.
