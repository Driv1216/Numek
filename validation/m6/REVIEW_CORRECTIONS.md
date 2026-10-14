# M6 focused source-review corrections — 2026-10-11

This pass addresses the eight independently identified issues. M1–M5 historical
evidence and completed M6 analytics were preserved. M6 final acceptance remains
with the user; M7 has not begun.

| Issue | Implementation and result | Focused verification |
|---|---|---|
| 1. Selection | `text_search.select_population` uses disk-backed split/field/kind/length queues, seeded members, priority tiers and round-robin comparison allocation. Reserve missing sides together, reuse represented sides, and disclose unavailable/insufficient sides. Actual selection and later indexed-side populations have separate ledgers. | Explicit/implicit comparison priorities, four split/field strata, 257-unit queue refill, repeatability/changed seed, tiny budgets and unavailable sides. |
| 2. Embedding endpoints | `text_models.allocate_windows` distributes first, last, then spaced interiors across selected parents. Both endpoints are conditional on actual global/per-parent allocation and tokenizer work. Selected, tokenized, embedded, unprocessed and partial parents are recorded by source and declared role. | Independent endpoint allocations under 2/3/4-window limits; evaluation/training parent reservation with a two-window global cap and truthful partial coverage. Existing pinned E5/Lingua tests run offline. |
| 3. Tokenizer work | `tokenizer_vocabulary` uses `AccountedTokenizer`. Rejected emitted tokens stay charged; accepted vocabulary occurrences are separate. Stop after the first rejected whole call and account for unattempted units. | Two attempted five-token calls with a seven-token cap charge ten emitted tokens while retaining only the first five-token vocabulary. |
| 4. Conversation witnesses | `text_diagnostics.conversations` compares per-conversation before/after violation totals. A preceding violation cannot cause a clean conversation to become a witness. | Bad/clean/bad/clean conversations retain only the two bad record locators. |
| 5. Duplicate actions | `text_presentation.executive_summary`, execution profile and copied export profile consolidate equivalent review instructions. Raw/NFC technical findings, counts and references remain distinct; representation totals are not added. | Normalization-only and raw equality control yields one executive action and two technical findings. |
| 6. Unexpected optional faults | Explicit `whole_audit_atomic_fail_closed` publication policy in `text._execute`; cleanup and safe failure are retained. Expected resource stops/exclusions still publish bounded coverage. | Inject a fault after evidence insertion and partial DuckDB index creation; no result is returned, private exception payload is absent, workspace is deleted, and a fresh audit has no stale findings. |
| 7. Report synthesis/density | Completed evidence drives population, ordered review actions and examined/unanswered scope. Continuous topic flow replaces forced topic pages. All eight topics and strict technical JSON remain. `text_private.ExportView` does not mutate completed analysis. | Pure synthesis control, existing API/CLI/browser/export/privacy checks; canonical reprojection and visual inspection of every page of five reports. |
| 8. Canonical documentation | README, ARCHITECTURE, CURRENT_STATE, NUMEK_MASTER_CONTEXT and M6 methodology distinguish legacy in-memory behavior from M4–M6 execution, formats and offline models. Completion is distinguished from user acceptance. | Source-level reconciliation and clean `git diff --check`. |

## Unexpected failure decision

The stricter behavior is retained deliberately rather than implementing an unproven
required-only partial-success path. Native database/tokenizer/model failures can
invalidate shared execution state, and evidence references depend on the same
collector and locators. Discarding the entire unfinished audit preserves atomic
publication without claiming that the connection and metadata remain trustworthy.
No partial index is cached or reused. Already completed historical exports are
untouched. The tradeoff is that required evidence from that failed run is also
unavailable; the operator must repair the fault and rerun. This is a documented
deviation from recoverable optional-stage partial publication, with a concrete
correctness rationale and fault-injection evidence. It does not reinterpret an
unexpected exception as an empty successful investigation.

## New verification and reuse

The authoritative Verification skill guided focused checks followed by one
repository closure run: **400 passed in 33.51 seconds**. Fourteen new correction
regressions join the existing suite. Relevant old M6 foundation, search/model,
closure and interface groups also passed while resolving consequential uncertainties.
Real pinned CPU E5/Lingua checks run with network sockets disabled.

`review_presentation.py` reprojects completed Hindi, SQuAD, SciFact and synthetic
default/excerpt evidence. It verifies unchanged technical evidence/findings/coverage,
completed-analysis digest binding, source-verified safe excerpts and nonmutation.
The five reports are **7, 7, 7, 9 and 9 pages**, down from **10, 10, 10, 11 and 12**.
All **39 pages** were rendered with Poppler and visually inspected, including Unicode,
opaque references, continuing tables, bounded model scope and escaped/bidi-safe
excerpts. Fontconfig emitted cache-directory warnings; canonical rendering completed
and the inspected pages contain legible text. Original files and ledgers are untouched.
The separate [presentation ledger](results/review_corrections/presentation.json)
records both original and new artifact hashes, page counts and QA.

LSH hash/shingle/signature/banding algorithms and the frozen 20×7/1,024 calibration
profile are unchanged, so calibration evidence is reused. Large workload, stress,
model-publisher and existing live-browser evidence are retained without repetition.
Old capacity numbers describe the old selection version and do not certify the new
queue scheduler; the disk-backed queue's correctness is covered by focused tests,
not new capacity claims. Browser routes/UI controls were unchanged; current Flask
integration tests cover the affected shared execution/export path. No new live
browser campaign was needed.

Remaining limits: insufficient budgets cannot guarantee both comparison sides
reach an index/model or both endpoints are embedded; ledgers expose these losses.
Bounded searches do not establish global absence or universal recall. No issue in
this correction scope remains blocked or unresolved; the stricter unexpected-fault
policy is an explicit retained tradeoff.
