# Repository Investigation Workflow

Use this as an evidence-gathering workflow, not as the final answer structure.

## 1. Establish repository scope

Determine the actual project root and whether the workspace contains one application, a monorepo, multiple independent apps, or generated/vendor content.

Inspect, when available:

- top-level directory tree;
- README and architecture/current-state documents;
- package/project manifests;
- lockfiles only to identify dependencies, not to narrate every package;
- Docker/Compose/devcontainer files;
- environment examples and configuration files without exposing secrets;
- build/run scripts;
- CI files when they reveal supported runtimes or verification flow;
- Git branch, HEAD, and working-tree status when useful for describing repository state.

Ignore or de-emphasize vendor, build, cache, virtual-environment, coverage, generated, and dependency directories unless they are architecturally relevant.

## 2. Identify executable boundaries and entrypoints

Find how the system starts and where control first enters each process.

Examples include:

- web frontend bootstrap and router;
- backend application entrypoint and route registration;
- CLI entrypoint;
- worker/queue consumer;
- scheduled job;
- model/inference worker;
- migration entrypoint;
- serverless function;
- mobile application entrypoint.

For each active process, determine:

- what starts it;
- what configuration it needs;
- what it initializes;
- what it connects to;
- what it exposes or consumes.

## 3. Reconstruct the product from the outside in

Before diving into internal files, answer from evidence:

- Who or what uses the project?
- What inputs enter it?
- What outputs leave it?
- What real-world problem is it trying to solve?
- What are the main user-visible or API-visible capabilities?
- Which capabilities are clearly working code paths versus planned/documented claims?

Use routes, commands, UI pages, handlers, services, schemas, tests, and persistence code to verify capabilities.

## 4. Identify required domain knowledge

Determine what specialized knowledge a competent programmer would need before the project makes sense.

Look for:

- domain terminology in README/design docs;
- tool names and dependency names;
- protocols, standards, frameworks, catalogues, scoring systems, and external services;
- domain models and enum names;
- API and CLI terminology;
- comments and tests that reveal expected domain behavior.

Build a **minimal but sufficient domain primer** from this evidence.

For every term that is central to the repository, answer:

- What is it?
- Why does this project care about it?
- Where does it appear in the project?
- What nearby term is it commonly confused with?

Do not postpone all explanation to the glossary. Concepts required to understand later sections should be taught before those sections use them heavily.

Avoid unrelated background material.

## 5. Build the subsystem map

Identify the major architectural areas. Examples:

- UI / presentation;
- API / transport;
- application or use-case orchestration;
- domain/business logic;
- persistence/data-access;
- database/storage;
- authentication/authorization;
- parsing/processing;
- retrieval/search;
- AI/ML/inference;
- security scanning/analysis;
- async jobs/queues;
- integrations/external APIs;
- observability/configuration.

Do not force these categories onto a project that does not use them.

For every subsystem, determine its responsibility and its dependencies on other subsystems.

## 6. Build the technology map

Identify the major technologies that materially participate in runtime behavior or development workflow.

Do not merely list dependencies. Group them by role, for example:

- language/runtime;
- web/UI framework;
- API/server framework;
- database/storage;
- container/runtime isolation;
- scanners/CLI tools;
- authentication;
- external APIs/intelligence sources;
- AI/ML/model providers;
- reporting/rendering;
- test/build tooling.

For each major technology, establish from repository evidence:

- what role it plays here;
- where it is configured or invoked;
- what project component depends on it;
- whether it is required, optional, development-only, or conditional.

## 7. Build the repository and file-responsibility map

Cover all **meaningful first-party areas** at an appropriate level of detail.

First produce the top-level mental map:

- major directories;
- major standalone modules;
- important config/manifests;
- test and example/practice areas;
- generated/data directories that matter to runtime behavior.

Then identify architecturally meaningful files.

- For a small repository, individual-file coverage is appropriate.
- For a medium or large repository, explain every important first-party area and the architecturally meaningful files, while grouping repetitive tests, generated files, boilerplate, fixtures, migration families, and trivial wrappers.
- Do not reduce repository anatomy to one paragraph.
- Never dump a raw file tree and call it an explanation.

For an important file, answer:

- Why does this file exist?
- Who calls or imports it?
- What does it call or depend on?
- What important types/functions/classes/routes does it own?
- What data enters it and leaves it?
- Where does its output go?

Only descend to function/class level when that detail materially improves understanding, but do so for the functions/symbols on the representative feature journeys.

## 8. Trace real feature journeys

Choose the most representative important capabilities and follow them through the code from trigger to final effect.

For a medium or large project, trace 2–4 materially different journeys unless the project genuinely has fewer meaningful flows.

A feature trace should identify, where applicable:

1. user/UI/CLI/API trigger;
2. route/command/handler;
3. validation and authentication;
4. application/service orchestration;
5. domain or processing logic;
6. persistence, external service, model, scanner, or filesystem interaction;
7. transformation/ranking/state change;
8. returned result/event;
9. presentation back to the caller.

For each important hop, explain the **responsibility of the actual function/class/handler**, not only its filename.

A good internal trace looks like:

`trigger → file:symbol → file:symbol → external/storage boundary → result`

Then narrate why each hop exists.

Prefer real symbol/file names from the repository. Do not invent missing layers.

## 9. Trace data, not only control

For important objects or data products, determine:

- where they originate;
- their important representations/schemas;
- where they are transformed;
- where they are persisted;
- which identifiers/relationships connect them;
- what consumes them later.

For AI/RAG/data/security-analysis systems, explicitly trace the important transformation chain that actually exists, such as:

`raw target/input → intake/recon → observations/findings/features → correlation/triage → grouped result/decision → persistence/report`

Do not force this exact chain onto unrelated projects.

## 10. Inspect state and lifecycle where relevant

If the project has statuses, runs, jobs, application states, workflow phases, versioning, immutable snapshots, approvals, remediation stages, or other transitions, identify:

- valid states;
- transition triggers;
- guards/validation;
- persistence of state;
- terminal/expired/error states;
- which file or schema owns the lifecycle.

Do not skip lifecycle analysis merely because the final answer already contains a general architecture diagram.

## 11. Inspect data model and persistence

When persistence exists, understand the model from migrations/schema/ORM definitions or storage code rather than guessing from service names.

Capture:

- major entities/tables/collections/files;
- primary relationships;
- ownership boundaries;
- important constraints;
- version/history patterns;
- where files/blobs/vectors/cache data live;
- what is persistent versus process-memory state.

Do not turn the explanation into a complete schema dump unless the schema itself is the project.

## 12. Determine implementation status carefully

Classify important capabilities as one of:

- **Implemented** — active code path is present and coherent.
- **Partially implemented** — meaningful pieces exist but the capability is incomplete or disconnected.
- **Documented only** — docs claim it, but supporting implementation was not found.
- **Scaffold/stub** — placeholder structure exists without substantive behavior.
- **Not found** — no evidence located after reasonable inspection.
- **Uncertain** — evidence conflicts or the path cannot be established confidently.

Do not equate “file exists” with “feature works”.

Build this classification during investigation so the final answer can present it explicitly instead of scattering limitations across unrelated sections.

## 13. Evidence discipline

While investigating, keep an internal evidence map linking each major claim to concrete repository evidence.

When uncertainty matters, write it plainly in the final explanation. Useful wording includes:

- “The code directly shows …”
- “The README describes …, but I did not find an active code path for it.”
- “This appears to be … because X calls Y, but I could not verify Z.”
- “The schema supports this state, although no UI path currently exposes it.”

Avoid fake precision.

## 14. Safe inspection rules

Allowed by default:

- reading files;
- file/tree/search commands;
- static code navigation;
- Git inspection such as status/log/diff when non-mutating;
- reading tests/configuration/migrations;
- safe metadata queries that do not change state.

Do not by default:

- edit files;
- install dependencies;
- run migrations;
- seed/reset databases;
- start persistent services;
- execute commands that write generated output into the repository;
- run scripts with unknown side effects;
- invoke external APIs that can mutate state.

If the user separately asks for runtime verification, that is a new task and should be handled explicitly.
