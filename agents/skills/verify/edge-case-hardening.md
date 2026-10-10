---
name: dependency-based-edge-case-hardening
description: Plan or conduct deliberately authorized edge-case hardening campaigns across completed, architecturally related milestones. Do not automatically launch a campaign during ordinary feature implementation. Use alongside proportional-verification, which remains authoritative for implementation-time and milestone-closure verification.
---

# Dependency-Based Edge-Case Hardening

## Purpose

Separate **exploratory edge-case discovery and cross-milestone hardening** from routine milestone implementation, without postponing essential correctness or weakening existing verification requirements.

Build ambitious product capabilities continuously; investigate unusual interactions together when the relevant capabilities form a coherent system.

The default rhythm is:

> **Implement milestone → verify essential behavior and close it → implement related milestones → run one bounded hardening campaign at a meaningful integration boundary.**

This is a *companion* to `proportional-verification` (`skills.md` in this directory), **not a replacement**. That skill governs implementation-time checks, failure repair, and risk-appropriate closure. This skill governs **when to group exploratory hardening, what belongs in the campaign, and when to stop**.

---

## 1. Two distinct verification activities

**During ordinary implementation (always):**
- Think through edge cases and design for them. Do not lower reasoning quality.
- Test approved requirements, invariants, affected integration contracts, and concrete defects at the level justified by risk.
- Immediately investigate high-consequence uncertainties that could corrupt subsequent work or mislead users.
- Complete the milestone's verification under `proportional-verification`. A future campaign does **not** replace its closure checks.
- **Do not start open-ended exploratory test generation** or repeatedly widen the test matrix merely because another hypothetical scenario can be imagined.

**During a dedicated hardening campaign (only when authorized):**
- Deliberately explore unusual inputs, boundary combinations, cross-component interactions, stress workloads, and failure recovery.
- Focus on related completed capabilities rather than reproducing each milestone's ordinary test suite.
- Repair validated defects, add durable regression tests where justified, and record remaining limits.

The difference is **the purpose and timing of exploration**, not whether correctness matters.

---

## 2. Choose checkpoints from dependencies, not milestone counts

Group milestones when they share meaningful runtime, data, or semantic boundaries, for example:
- shared contracts and data representations;
- ingestion, execution, persistence, or lifecycle machinery;
- evidence or scoring semantics;
- cross-feature user workflows;
- failure modes that emerge only when the capabilities interact.

A checkpoint is valuable when that cluster is implemented sufficiently to test its interactions *once*, or before a planned architectural transition makes defects costly to address.

**Do not mechanically harden every three, four, or five milestones.** An independent milestone may warrant separate hardening; related milestones may be grouped even if their numbers are not adjacent.

For NUMEK, M1–M4 form a related tabular/comparative foundation, while M5 adds different temporal semantics. Later text, image, audio, and multimodal work should be grouped according to actual implementation dependencies, not an assumed fixed schedule. Existing completed verification remains valid; this skill does not require retroactive campaigns.

The founder/user selects or approves a checkpoint. An agent may **recommend** one when the dependency boundary becomes clear, but must not silently create a new release gate or interrupt an ongoing implementation to run a campaign.

---

## 3. Defer speculative cases, not known correctness problems

When a possible edge case arises during implementation, classify it by **reason to act**, not by how exotic it sounds:

| Case | Action now |
|---|---|
| Explicit requirement or established correctness invariant | Implement and verify appropriately now. |
| Reproducible defect affecting current promised behavior | Repair and test now. |
| Material risk to safety, security, data integrity, financial decisions, provenance, or a foundation other features depend on | Investigate promptly; escalate or block if unresolved. |
| Required repository/user verification | Perform under the existing verification skill. |
| Plausible but unobserved, nonblocking interaction or pathological input beyond the approved guarantees | Record concisely for a future hardening campaign; continue implementation. |
| A new capability disguised as an edge case | Flag as a product-scope decision; do not implement it silently. |

A case may be rare **and** critical. Never defer it solely because it is unusual. Conversely, do not invent an ever-growing list of hypothetical cases and treat every item as a blocker.

A lightweight deferred note is enough: **scenario, affected boundary, reason it might matter, and trigger/priority**. Do not create a new issue, document, or tracking ceremony for every idea; use the repository's existing task/backlog mechanism where available.

---

## 4. Start a campaign with a bounded mission

Before executing an authorized campaign, establish a compact scope:

1. **Boundary:** Which completed milestones/components and cross-feature workflows are in scope?
2. **Risk hypotheses:** Which unknowns are important enough to investigate, based on architecture, observed incidents, or deferred cases?
3. **Evidence to reuse:** Which existing tests, hashes, reports, or benchmarks remain applicable and need not be repeated?
4. **Budget and priority:** What are the available time/compute limits, and which risks come first?
5. **Stopping conditions:** What constitutes enough confidence for this campaign, and what remains acceptable to document rather than fix immediately?

Do not generate a giant speculative matrix before beginning. Start with the highest-value interactions, then expand only if results reveal new significant risk.

A campaign may include adversarial examples, property/metamorphic tests, failure injection, differential checks, cross-milestone integration scenarios, or stress/performance work **when the relevant hypothesis warrants it**. There is no mandatory list of techniques or minimum test count.

---

## 5. Execute without falling into another loop

For each exploration, know which claim or uncertainty it is testing. Prefer the smallest experiment that can distinguish the expected outcomes.

When a defect is found:
1. Reproduce and identify its affected guarantee and blast radius.
2. Decide whether it is a correctness bug, an unsupported input that needs an honest boundary, or an unapproved feature request.
3. Fix genuine in-scope defects and add focused regression evidence.
4. Recheck the directly affected behavior first; broaden only for plausible downstream effects, following `proportional-verification`.
5. Return to the **remaining priority hypotheses**, not to the beginning of the entire test campaign.

Newly imagined scenarios do not automatically expand the campaign. Include them only if evidence changes the risk assessment or the user approves a scope increase.

Do not automatically repeat full suites, regenerate unrelated historical artifacts, or reopen already-verified behavior without an identified invalidating change.

---

## 6. Stop deliberately

End the campaign when its **approved high-priority hypotheses have been investigated to the justified depth** and:
- critical/in-scope correctness defects are resolved, or explicit blockers are escalated;
- affected verification supports the fixes made;
- remaining noncritical unknowns and capacity/coverage limitations are accurately stated; and
- further hypothetical testing offers diminishing value relative to the agreed budget and next product work.

Do **not** require every conceivable edge case to be discovered, every low-priority finding to be fixed, or a new full verification round after every small repair. Do not claim a clean pass if an essential guarantee is still broken; report the limitation or stop as blocked.

At completion, provide a compact account of **what was exercised, what failed and changed, what evidence remains valid, what was deferred, and what was not tested**. Distinguish executed results from source-only review, prior evidence, and unverified assumptions.

---

## 7. Respect the approved product and historical evidence

- Hardening validates promised behavior; it does not expand the product roadmap by stealth.
- Preserve existing compatibility policies and source/artifact history unless an explicit change is approved.
- Avoid unsupported claims of comprehensive safety, reliability, capacity, or method validity.
- Do not retroactively relabel source-only review as execution verification.
- User and mandatory repository requirements still apply. `proportional-verification` remains the authority for verification **during ordinary implementation and at milestone closure**.

---

## Default operating principle

> **Reason about edge cases continuously. Verify essential correctness during each milestone. Explore broadly at approved dependency-based checkpoints. Stop when meaningful risks are addressed, not when imagination runs out.**
