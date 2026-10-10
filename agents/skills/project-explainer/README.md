# Project Explainer Skill

A manual-only, read-only skill for understanding an unfamiliar existing codebase from first principles.

It investigates the repository, reconstructs the current architecture and capabilities from evidence, teaches the project in clear mid-level engineering language, maps important files and connections, traces real feature journeys through actual symbols, and produces architecture/runtime/data diagrams.

It deliberately does **not** propose future features, refactors, improvements, or roadmap ideas.

## Folder structure

```text
project-explainer/
├── SKILL.md
├── agents/
│   └── openai.yaml
└── references/
    ├── analysis-workflow.md
    ├── diagram-guide.md
    └── output-contract.md
```

## Codex installation

For a personal/global skill, copy the entire `project-explainer` folder into your user-level skills directory, commonly:

```text
~/.agents/skills/project-explainer/
```

Restart or reload the coding agent if it does not discover newly added skills immediately.

The included `agents/openai.yaml` sets:

```yaml
allow_implicit_invocation: false
```

so the skill is intended to run only when you deliberately invoke it.

## Invocation

In Codex, explicitly invoke the skill:

```text
$project-explainer
```

That alone should trigger the complete workflow. Extra text is optional and should only be used when you want to change emphasis, for example:

```text
$project-explainer Focus especially on authentication, but still explain the whole project.
```

## Intended behavior

When invoked, the skill should:

1. inspect the repository without modifying it;
2. explain what the project is from zero;
3. teach only the domain knowledge needed for this repository;
4. distinguish documented goals from current implementation;
5. explicitly classify implementation state;
6. explain current capabilities and relevant non-capabilities;
7. explain the tech stack in context;
8. map major directories and architecturally important files;
9. explain how the project starts and keeps state;
10. show how components and data connect;
11. generate appropriate Mermaid diagrams;
12. trace multiple real features through actual files and symbols when the project is complex enough;
13. explain important data models and lifecycles where present;
14. answer 5–10 likely project-specific questions;
15. correct common misconceptions;
16. provide a project glossary;
17. disclose unknowns or claims it could not prove;
18. finish with a compact mental model.

## What changed in this strengthened version

The first real-world test showed that a strong agent could still compress the explanation too aggressively. This version therefore makes the following explicit:

- required sections must not be collapsed just to save tokens;
- specialized-domain concepts must be taught before later sections rely on them;
- tech stack gets its own contextual walkthrough;
- repository anatomy and important files are separate teaching sections;
- important files must be explained by responsibility and connections, not merely named;
- medium/large projects should get 2–4 real source-code feature journeys;
- current implementation status must be shown explicitly;
- lifecycle/state/data modeling must be covered when the codebase contains them;
- if the explanation is large, completeness is preferred over a short summary.

## Other coding agents

The core skill follows the portable `SKILL.md` + `references/` Agent Skills structure, so tools that support the common Agent Skills convention can reuse it.

Manual-only enforcement differs by product. The `SKILL.md` itself explicitly says not to auto-trigger. OpenAI/Codex additionally receives the machine-readable `allow_implicit_invocation: false` policy in `agents/openai.yaml`.
