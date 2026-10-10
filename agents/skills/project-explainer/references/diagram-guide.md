# Diagram Guide

Diagrams are part of the explanation, not decoration. Each diagram must answer a distinct question about the **current** project.

Use Mermaid as the canonical portable format unless the user's environment explicitly provides and requests another diagram tool.

Prefer standard Mermaid constructs (`flowchart`, `sequenceDiagram`, `erDiagram`, `stateDiagram-v2`) that render broadly across coding tools.

## Required diagram set for a non-trivial application

Create these unless one is genuinely inapplicable:

### 1. System context / project boundary

Question answered: **What exists around this project, and who/what interacts with it?**

Show the project as one system with users, external systems, repositories/files, third-party services, databases, or other actors around it.

Keep this high-level. Do not put internal classes here.

### 2. Architecture / major runtime components

Question answered: **What are the major technical pieces and how do they communicate?**

Show real runtime boundaries such as browser, frontend, API, worker, model runtime, database, object storage, queue, external service, CLI, scanner/toolbox, or filesystem.

Do not invent microservices where the code is actually one process.

### 3. Code/layer dependency map

Question answered: **How is the implementation organized internally?**

Show meaningful code layers/subsystems and dependency direction. Use actual repository structure where useful.

Avoid one box per source file unless the repository is tiny.

### 4. Data-flow / processing pipeline

Question answered: **How does important information transform as it moves through the system?**

Especially important for data, compiler, parser, AI/ML, RAG, search, ETL, media-processing, analytics, ingestion, and security-analysis projects.

### 5. Runtime feature flow

Question answered: **What happens end to end when the user performs an important action?**

Use either `flowchart` or `sequenceDiagram`. Include actual major files/services where that improves traceability.

For complex applications, create multiple feature-flow diagrams only when the flows are materially different.

### 6. Startup / execution flow

Question answered: **What actually starts when I run this project?**

Show commands/scripts → entrypoints → initialization → route/worker registration → connections → ready state.

## Conditional diagrams

Add these only when supported by the repository and genuinely useful:

### Entity / database relationship diagram

Use when persistent entities and relationships are central to understanding the product.

### State/lifecycle diagram

Use when objects move through meaningful states such as pending → processing → active → expired, or when the project contains explicit lifecycle/state modules.

### Deployment/runtime-environment diagram

Use when deployment topology differs meaningfully from the logical architecture or multiple processes/environments are involved.

### Authentication/authorization flow

Use when identity, sessions, tokens, roles, RLS/policies, OAuth, keyrings, or permission boundaries materially affect how the system works.

### Event/queue/async flow

Use when jobs, queues, pub/sub, webhooks, event buses, thread pools, or background workers are central.

### AI/ML/RAG flow

Use when models, embeddings, vector stores, prompt assembly, inference, reranking, evaluation, or retrieval are central. Make clear which steps happen offline, at ingestion time, or at request time.

### Security/trust-boundary flow

Use when the project itself is security-sensitive or when authorization, sandboxing, scanning, secret handling, privileged operations, or external target boundaries are central to understanding behavior.

Show trusted/untrusted inputs, privilege boundaries, approval points, and external execution boundaries only when supported by repository evidence.

### External-integration sequence

Use when a third-party API or service is a major part of an important feature.

## Diagram quality rules

1. Every box/node must correspond to something real or a clearly labeled conceptual grouping.
2. Use the names a human sees in the repository, but simplify labels when raw identifiers would make the diagram unreadable.
3. Show direction of control/data explicitly.
4. Label important edges when the meaning is not obvious (`HTTP`, `SQL`, `JWT`, `filesystem read`, `scanner output`, `embedding vector`, etc.).
5. Keep a single diagram focused. Split diagrams instead of creating an unreadable mega-diagram.
6. Do not use diagrams to introduce future components or recommendations.
7. If a boundary is inferred rather than explicit, say so in the surrounding explanation.
8. Follow every non-obvious diagram with a short walkthrough explaining how to read it.
9. Prefer 5–15 meaningful nodes. Larger diagrams are acceptable only when the complexity is real and the layout remains readable.
10. Never claim a diagram is an exact deployment diagram if it is only a logical architecture view.
11. The baseline diagrams should collectively cover the major subsystems identified in repository anatomy. If a major subsystem appears nowhere visually, either add it to the relevant diagram or explain why it is intentionally omitted.
12. Feature-flow diagrams should be paired with source-code walkthroughs; the diagram alone does not satisfy the feature-trace requirement.

## Mermaid reliability

- Use simple node IDs and quote labels when necessary.
- Avoid fragile syntax when a normal flowchart communicates the same idea.
- Do not put huge paragraphs inside nodes.
- Keep line breaks in node labels minimal.
- For relationships, use `erDiagram` only when cardinalities are supported by evidence.
- For states, use `stateDiagram-v2` only when transitions are supported by code/schema/tests.
- For sequences, use actors/participants that correspond to real boundaries.

## Diagram captions

Before or after each diagram, state the question it answers in one sentence. Examples:

- “This shows the major runtime pieces, not individual source files.”
- “This traces a search request from the browser to storage and back.”
- “This diagram shows data transformation during ingestion; it is not a deployment diagram.”
