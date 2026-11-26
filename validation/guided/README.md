# Guided Analysis & Evidence Intelligence: stage notes

The founder-approved plan for this initiative (2026-11-25) has seven stages; the gated analytical work in Stage 6 is split into 6A–6D. Each stage records here what changed, what was verified and what remains. Visual captures go under `validation/report_experience/work.nosync/guided/visual/<stage>/`, which is git-ignored.

## Stage 1: foundations (2026-11-25)

**CSRF first-load race (fixed)**

*Cause*
- The API guard minted the session's CSRF token on every request that lacked one (`session.setdefault`).
- On a cold load the page fires several API requests at once, all without a session cookie. Each minted a different token, and each response set its own cookie.
- `/session` handed the page one token while the browser kept whichever cookie arrived last. The first mutation was then refused until a reload.

*Fix (`src/datatrust/api_web.py`)*
- The token is minted when the app document is served (`shell`), before any script runs. Every API request the page makes therefore carries a cookie that already holds it.
- The guard now only reads the token. `/session` mints one only for clients that call the API directly.
- A missing or stale token is refused with error code `csrf`, before the request does anything.
- `frontend/src/app/api.ts` `call` refetches the session's token and retries once on that code. The retry is safe because the refusal happens before any side effect.

*Tests* (`tests/test_app_api.py`)
- `test_the_csrf_token_is_minted_with_the_app_document_never_by_concurrent_api_requests`
- `test_a_missing_or_stale_csrf_token_is_refused_with_a_code_the_client_can_recover_from`
- Every API suite that posts with a token passed: core, M4, M5, M6, M7, M9, history, delimiters, before/after, contextual and the companion.

**Guidance keys for comparison and temporal findings (already guarded)**
- Comparison (M4) and temporal (M5) findings are matched to guidance by their title.
- `tests/test_guidance.py::test_every_finding_kind_has_an_explicit_entry` already extracts every emitted title from the source, including loop-built and shared-builder titles. It asserts that each maps to a specific catalogue entry and that only `generic_review` is unused. No new test was needed; it passes.

**Live private inspection, re-driven in a browser**
- *Harness:* an in-process server over local fixtures, driven by headless Chromium through the page's own session cookie (Playwright's shared request context).
  - Each job runs through the API.
  - The report page is opened, the chapter controls are used, and the browser state is checked.
- *Text (M6):*
  - "Locate" shows the reference without content. "Reveal text" shows the record in the exact-duplicates chapter.
  - The revealed markup (`<img onerror=…>`) renders as inert text and never runs.
  - "Export excerpts" downloads the selected excerpt.
  - The standard JSON and HTML downloads do not contain the text.
- *Images (M7):*
  - The pair viewer opens in the perceptual near-duplicate chapter. "View this pair locally" shows both images, with the labels toggle on. "Export examples" downloads them.
  - The standard JSON contains no image data.
- *Records and documents (M9):*
  - "Inspect" on a review target shows its evidence rows and excerpts.
  - "Save separate review decision" records the review.
  - The standard JSON does not contain the excerpt.
- *All three:* nothing revealed reaches the URL, `localStorage` or `sessionStorage`, and no console errors occurred apart from the deliberate refusals below.

**Defect found and fixed: image overlay export.**
- On an image set without annotations, "Show compatible supplied overlays" followed by "Export examples" crashed the export route, which returned a generic 500. Viewing the pair locally already refused the same request with a clear 409.
- The export route now refuses with that same 409 (`changed_or_unavailable`, "Evidence changed, is unavailable, or has an unresolved overlay frame."), and the export button shows the server's message.
- The defect predates the dashboard redesign. Test: `tests/m7/test_app_api.py::test_overlay_export_without_a_compatible_frame_is_refused_clearly`.

**Not covered in this stage**
- Saved-entry views of these chapters show references only, and were captured in the dashboard initiative.
- The M9 model judgment controls were not driven, because fresh runs abstain (open founder decision).

## Stage 2: shared interpretation (2026-11-25)

**One deterministic interpretation, `src/datatrust/interpretation.py` (`interpretation_v1`).**
- It is presentation, not analysis. It reads only what a result records: fields, the recorded `finding_guidance_v1` and the methodology. It never creates, removes, re-ranks or recomputes findings or values.
- **`summary`:** per-workflow sentences in the order a reader needs them. Examples:
  - Classification: score and band ("a review-policy score, not a probability"), the governing cap, findings by priority, and prediction-point and availability status.
  - Regression: finite targets, then input relationships that reproduce the target with their availability state, then findings.
  - Comparison: the split intent and declared violations, or "fewer findings do not establish improvement", or "changed is not worse".
  - Temporal: declared violations vs investigation candidates ("not validated defect criteria").
  - Records and documents: assessed record checks that agree.
  - Each sentence lists its facts as JSON pointers. A fact is the value at a pointer, the length of a recorded list, a count of recorded findings by rank or evidence type, a count of mapping entries by state, or a sum of recorded counts. `resolve_fact` recomputes each one from the result.
- **`findings`:** the recorded guidance per finding, keyed by the guidance block's own reference, unchanged. Results saved before guidance existed get none; nothing is back-filled.
- **`more_conclusive`:** the declarations that would let the analysis conclude more, each with what it makes possible. Two sources:
  - recorded unknowns, through `UNKNOWN_RESOLUTION`, a table that maps every catalogue and method unknown to a declaration or explicitly to none;
  - recorded configuration: no prediction point, suggested codes left undeclared, unspecified target expectations, scale sensitivity undeclared, no evaluation intent or identity keys, no declared transformations, no schedule, models not selected, no quality rules.
- **`clean`:** checks completed out of recorded, the review thresholds that were not met (`guidance.policy`) and what is not established.
- **`states`:** the fixed result-state vocabulary.

**Delivery.**
- The presentation companion carries `interpretation` for every known methodology (none for unknown ones), cached with the rest of the companion.
- The dashboards render it and author no interpretation text:
  - **Outcome band:** the summary sentences replace the recorded statement when an interpretation exists.
  - **Finding blocks:** every composition's finding blocks show the recorded guidance (what was observed, why it may matter, check first, options collapsed, not established) through one React context (`results/shell/Interpretation.tsx`). This covers tabular, text, image, records, temporal and comparison.
  - **Ledger:** "Show their wording" adds the first "why it may matter" line.
  - **Clean results:** the ledger states completed checks out of recorded, the thresholds that were not met and the declarations that would add conclusions.
  - **Results with findings:** coverage opens with "What would make this more conclusive". Live results link to the workflow's configuration; saved ones say to supply them in a new run.
- **Reports:** reports already render the same recorded guidance (`guidance_layers.html`). Summary and "more conclusive" sections arrive in Stage 6D, from the same `interpret()`.

**Checks.**
- All 75 cases captured at five sizes with every chapter at 1440 (710 chapters). No render failures or console errors.
- Inspected screens:
  - Bank Marketing: summary band, chapter guidance, and coverage "more conclusive" (prediction point, code meanings).
  - wide_200: clean panel.
  - Bike Hour at 375 px.
- Older results show no guidance blocks; the outcome band's "earlier version" note covers them.

**Tests.**
- New `tests/test_interpretation.py` (167):
  - every recordable unknown maps to exactly one resolution row;
  - every summary number traces to the recorded result, for all cases;
  - guidance is identical to the recorded items, or absent when unrecorded;
  - the companion equals `interpret()`, and an unknown methodology gets none;
  - expected declarations follow the configuration;
  - clean results state their scope;
  - the dashboard carries the companion's interpretation unchanged (node harness).
- **Full suite (integration boundary 1):** 1,727 passed.

## Stage 3: inspection and deferred analysis choice (2026-11-25)

**Input inspection, `src/datatrust/inspection.py` (`input_inspection_v1`).**
- Advisory only. It is stored on the job and returned in the job view (`input_inspection`), and never written into analysis JSON, specifications, fingerprints, reports or history.
- Items are observed facts, structural observations (with their denominator and scope), suggestions (named rule and reason, never applied) or unknowns.
- **Budgets** (`InspectionBudget`):
  - whole file up to 64 MiB and 500,000 rows, otherwise the first 50,000 rows;
  - 500 profiled columns and 2,000 listed;
  - chunked reads of 50,000 rows into per-column accumulators;
  - distinct values capped at 10,000 per column;
  - exact uniqueness (64-bit hashes) for at most 16 columns, identifier-named first;
  - a 4-second deadline checked between chunks.
- A stopped pass states its coverage and never claims "unique" or "constant" for the whole file. A failed inspection is recorded and never blocks the upload.
- **Parsing:**
  - The pass uses the analysis's pandas arguments: `ingestion.csv_read_kwargs` and `apply_column_types`, factored out of `read_csv` and unchanged in behaviour.
  - Before a workflow is chosen it runs under the provisional profile (detected separator, defaults). That profile equals every core workflow's default.
  - The inspection is cached by parse fingerprint and rerun once when parsing changes.
  - Classification reuses its upload frame (`profiler.inspect_csv_dataset(frame_sink=...)`), so the default path reads the file once.
- The rule catalogue (R-ID-1/2, R-TIME-1/2, R-BIN-1, R-MULTI-1, R-CAT-1, R-NUM-1, R-TEXT-1, R-STATUS-1, R-ENTITY-1) and the budgets are documented in `docs/ARCHITECTURE.md`, under "Input Inspection Boundary". R-KEY-1 arrives with Stage 5.
- **Timings** (dev machine, with the test suite running alongside):

  | File | Coverage | Time |
  |---|---|---|
  | Bike Hour, 17,379 rows | full | 0.04 s |
  | 60 MiB, 240,000 rows × 15 columns | full | 1.1 s |
  | 121 MiB and 242 MiB | fallback, first 50,000 rows, disclosed | 0.22 s |

**Upload first, choose the analysis afterwards.**
- `POST /core/uploads` stores, previews and inspects a CSV with no analysis chosen. The job stage is `choose`.
- `POST /core/job/analysis` chooses or changes the analysis without uploading again:
  - declarations for the previous analysis are cleared, as a separator change clears them;
  - the inspection is reused when the parse profile is unchanged;
  - a refused choice restores the previous state.
- Configure and generate refuse a job with no analysis: "Choose an analysis for this file first." The classic routes redirect such a job to upload.
- The one-call `POST /core/jobs` with `mode` is unchanged.
- Frontend: `api.uploadOnly` and `api.chooseAnalysis`, and the `choose` stage in `App.tsx` and `history.tsx`. Nothing in the UI uses them yet; the Start page is Stage 4.

**Tests.**
- New `tests/test_inspection.py` (18):
  - Bike Hour suggestions (R-TIME-1 `dteday`, R-ID-2 `instant`, R-NUM-1 `cnt`/`casual`/`registered`, R-MULTI-1 over `holiday`/`workingday`/`yr`);
  - a fixture for each rule;
  - ambiguous `03/04/2024` dates never suggested as a clock;
  - each budget: rows, bytes, columns, distinct cap, uniqueness tracking, and the deadline with a fake clock;
  - a supplied frame matches a file read;
  - numeric overrides refuse as the analysis does;
  - the fingerprint follows parse options;
  - a single full read on the default classification path (instrumented);
  - reuse until parsing changes;
  - a failure is recorded, not raised.
- `tests/test_app_api.py` (+11):
  - the analysis JSON through upload → choose (after first choosing another analysis) → configure → generate equals the one-call path, after normalising volatile fields, for all nine core and M3 modes;
  - an upload alone is neither configured nor run (API and classic);
  - changing the analysis clears declarations and keeps the file and the inspection.

**Full suite (integration boundary 2):** 1,756 passed.

**Founder gate (open).** Approve the rule catalogue wording and the budget values in "Input Inspection Boundary" before Stage 4 shows suggestions to users.

## Stage 4a: Start page and analysis suggestions (2026-11-25)

The founder approved the 4a gate (`stage4_proposal.md`): the regression grouping, the user-facing names and the Start-page structure. R-ENTITY-1 is to be tightened in Stage 5.

**Backend.**
- `target_guidance.regression_target_groups(inspection)`: the numerical-outcome picker's groups (outcome-word numeric, other numeric, review needed, unavailable), taken from the full-file input inspection. Nothing is preselected.
- `applicability.applicable_analyses(inspection)`: every analysis with a state (can run now, needs more input, probably not useful), a reason and its rules. It never ranks, preselects or blocks.
- Both are in the job view as `suggestions`, and both are advisory.
- **Inspection corrections found while checking real files:**
  - Uniqueness tracking could restart on a later chunk, so Beijing's repeating `time` was called unique. It is now chosen on the first chunk only.
  - **R-ID-2 wording amended:** it now applies only to whole-number and text columns. A fractional measurement (e.g. `total_amount`) is often unique and was being suggested as an identifier, which pushed it out of the numerical-outcome candidates and out of the clustering feature count. Changed in `RULES` and in `docs/ARCHITECTURE.md`.

**Interface.**
- **Step 1 is "Start"** (`frontend/src/app/start.tsx`):
  - before a file: "Start from a CSV" (drop zone, separator) and "I know what I need" (eight intents). The single-CSV intents list their analyses; the multi-source intents open their existing flows;
  - choosing an analysis before the file is read opens it as soon as the file is read: the direct path, equivalent to the old mode-first upload;
  - after a file: the file and its coverage statement, an intent filter row, then "Analyses for this file" in three lists. Each entry shows its reason and rule IDs; "Probably not useful" is collapsed but choosable;
  - "All analyses (15)": a searchable list. It replaces the header's "Other workflows" menu with an "All analyses" link that opens it from anywhere;
  - the current and last-used analyses are marked. Last used is kept per viewer in `localStorage`, guarded.
- **Configure** shows "Analysis: …" with "Change analysis", which returns to the list with the file kept (`POST /core/job/analysis`).
- **Numerical outcome** uses the grouped picker. Review needed and unavailable are collapsed; unavailable cannot be chosen. The old 10-row list remains only as a fallback when the inspection failed.
- The session rail says "choose an analysis" for an uploaded file with no analysis.

**Checked in the browser** (in-process server, generated CSVs):
- **Upload-only flow:** read file → list → Numerical outcome (grouped picker) → total_amount → confirm → report.
- **Changing course:** from the report, "All analyses" opens and focuses the search, and the list marks the current analysis with a note that choosing replaces the session's report. Choosing Category outcome opens Configure without re-uploading.
- **Choose before the file:** a multilabel-first choice opened Configure directly after the file was read.
- **Layout:** 1440 and 375 px, no horizontal overflow, no console or server errors.
- **Captures:** `validation/report_experience/work.nosync/guided/visual/stage4/`.
- **Fixed during inspection:**
  - after upload, the list sat below eight tall intent cards; it is now a compact file bar and a filter row;
  - the All-analyses list inherited pill styles.

**Tests:** `tests/test_input_suggestions.py` (13) and `tests/test_inspection.py` (+2). The focused set (app API, inspection, suggestions, target guidance) gives 78 passed.

**Next: 4b.**
- the three-layer configuration (why / if missing);
- G0 availability with the bulk-confirmation dialog;
- ghost-chip roles;
- the role-aware switch;
- the review panel, with the methodology-equality test.

## Stage 4b: layered configuration, availability, role switch, review (2026-11-25)

**What will run is stated by the server.**
- `api_web.review_view` builds the job view's `review` once an analysis is configured:
  - **methodology:** the confirmation's own `effective_policy` result for M3, the pinned method for core modes;
  - user-facing name, and whether a composite score is computed;
  - targets and prediction point;
  - availability counts, with bulk-declared columns listed apart and the consequence stated;
  - code meanings declared;
  - **"not established by this run":** no prediction point; unknown availability; name-and-bounded-search leakage (scored path); the regression relation scope; scale sensitivity and the no-verdict statement (readiness); an undeclared annotation expectation.
- Presentation only. The bulk list (`availability_bulk`, recorded by `web.record_bulk_availability`) never enters the configuration, the analysis or its fingerprint; a test asserts it.

**Interface.**
- **Three layers** (`frontend/src/app/configure.tsx` `Layer`) on Category outcome, Numerical outcome, Dataset profile and the six M3 analyses. Each layer states why it matters and what is lost without it.
  - **Essential:** the outcome, or the roles.
  - **Recommended context:**
    - the prediction point and availability, for predictive analyses;
    - code meanings, for the profile;
    - label expectations, for the annotation analyses;
    - scale sensitivity, for readiness.
  - **Advanced (collapsed):** CSV interpretation, JSON declarations, name, purpose, conditions and units.
  - Contracts are unchanged: the same form fields reach `configure_core` and `configure_m3`.
- **G0 availability** (`Availability`):
  - every column starts unknown, with a per-column select;
  - several columns can be ticked and marked available only through a dialog that lists them, states the consequence (with a call's duration as the example) and requires "I checked each listed column against the prediction point";
  - columns declared in bulk are tagged, and changing one individually removes its tag;
  - the review lists them separately and repeats the consequence.
- **Role information on the scored paths:**
  - inspection's identifier, time and status observations are shown as information only ("every column other than the target is analysed as a feature");
  - "Switch to role-aware classification", "…numerical outcome" and "…profile with chosen columns" open a dialog that names the destination analysis and when its method applies. Switching keeps the file, carries the outcome as the target (`POST /core/job/analysis` with `target`) and clears other declarations.
- **M3 role suggestions** are chips ("metadata? R-ID-1", "metadata? R-TIME-1", "ignored?" for identifiers and free text in readiness, "target?" for multilabel indicators), accepted one at a time. Every column still starts as a feature.
- **Review panel** on both Confirm pages: "What will run", the targets and declarations, the bulk note, and "Not established by this run".

**Checked in the browser** (generated orders CSV):
- Category outcome Configure in three layers;
- bulk-declaring region, channel and call_duration: the dialog blocks until checked, and the review lists them with the consequence;
- the switch to role-aware classification kept `returned` as the target, and chips offered metadata for `order_id`, `order_date` and `call_duration`; accepting one set it;
- the M3 review named `tabular_partial_classification_v1` with no score;
- regression Configure layers at 1440 px and the recommended layer at 375 px, with no overflow and no console errors.
- **Fixed during inspection:**
  - a unique date column was described as an identifier; time now takes precedence in the notes and chips;
  - the switch dialog now names the analysis it opens.
- **Captures:** `work.nosync/guided/visual/stage4/1440-4b-*`, `375-4b-*`.

**Tests** (`tests/test_app_api.py`, +12):
- the review's methodology equals the run's recorded `methodology_id` for all nine core and M3 modes;
- the role-aware switch keeps the target, and the review names the scored method when nothing beyond its defaults is declared and the role-aware method otherwise; the generated analysis records the same;
- bulk availability is listed apart and never reaches the analysis.

The focused set (app API, contextual, M3 analysis and interfaces, web, inspection, suggestions, target guidance) gives 197 passed.

**Not in 4b.** Structured editors replacing the M3 JSON fields (multi-output expectations table, multilabel constraints form) remain JSON under Advanced. They are candidates for Stage 7 polish or a follow-up.

## Stage 5a: comparison and temporal guided configuration (2026-11-25)

**Source inspection** (`src/datatrust/inspection.py`, advisory; never in specifications or fingerprints):
- `inspect_source`: every comparison (M4) and temporal (M5) source is inspected when added, under `SOURCE_BUDGET`. That is the whole file up to 8 MiB and 20,000 rows, otherwise the first 20,000 rows, disclosed.
- **Parquet:** schema from metadata and the first row batch only. Its column names now fill the source's headers, so column selects work for Parquet too.
- `identity_key_candidates` (R-KEY-1): present in every source and unique in each source's inspected rows.
- `name_mapping_candidates` (R-MAP-1): names that differ only in case, spaces, hyphens or underscores.
- `time_structure`: one bounded read of the clock and small-value-set columns of the inspected rows. It gives:
  - each clock's interpretation: civil date, instant with an offset, local date-time without one, or epoch with its unit;
  - entities;
  - measurement candidates with a type hint;
  - the most common spacing between consecutive distinct times, offered as a schedule choice and never applied.
- **R-ENTITY-1 tightened** (founder decision, Stage 4a):
  - **Before:** a name and type heuristic that matched Beijing's wind direction.
  - **Now:** a pair test. Where times repeat, a column whose values make each (value, time) pair unique, ranked by how closely its distinct count matches how often each time repeats.
  - Where times do not repeat in the inspected rows, the page says one series vs several is not established. This happens with Beijing's head, which holds one station because the file is sorted by station.
- **Corrected during testing:** a timestamp without an offset was first suggested as "local date-time, needs a timezone". The temporal contract only takes a timezone for instant clocks, so the suggestion now says: local date-time, or "instant" plus an IANA timezone if the values are instants.

**Interface.**
- **Comparisons** (`m4.tsx`): Configure is question-led.
  - **Essential, "Which file plays which part?":** roles, with each source's coverage statement.
  - **Recommended:**
    - **Splits:** "What must not be shared between splits?", with the evaluation intent in plain words: not declared, no record, no entity, no group, overlap allowed.
    - **Before/after:** "What did the pipeline do, and how are rows traced?"
    - **Versions:** "How are rows matched?"
    - **Suggestion chips:** R-KEY-1 identity keys.
    - **"Columns that do not align":** listed before the run, from the headers and the declared mapping, with R-MAP-1 mapping chips.
  - **Advanced:** per-source tasks, targets, parsing and mapping JSON, and limits.
- **Temporal** (`m5.tsx`): every field is kept, regrouped per source.
  - **Essential, "When was each record observed, and what was measured?":** clock and measurement chips, then role, clock and measurement fields.
  - **Recommended, "One series or many, and how often should records arrive?":** entity chips or the "not established" statement, the spacing chip ("expect a record every 1 hour from …"), observation and scheduling fields, and feature availability.
  - **Advanced:** CSV parsing; revisions, outcome maturity and fold plans, retitled as questions; JSON import and behaviour settings.

**Checked in the browser:**
- **Temporal:** generated 3-station hourly panel → clock, measurement, entity (`station` ranked first) and spacing chips applied → specification bound and moved to Confirm.
- **Split audit:** train and test with 20 shared customers and differently cased columns → key and both mapping chips applied, after which all columns aligned → "entity disjoint" → run → High "Declared evaluation separation is violated".
- **Layout:** 1440 and 375 px, no overflow, no console errors.
- **Captures:** `work.nosync/guided/visual/stage5/`.

**Tests:**
- `tests/test_inspection.py` (+6): panel entity pair test, a single-series head, epoch and offset clocks, the source budget, Parquet head and metadata, keys and mappings.
- New `tests/test_source_suggestions.py` (2): chip-derived temporal fields form a specification that runs to completion; comparison keys and mappings never enter the specification or configuration.
- A fixed daily cadence on a calendar-date clock was checked to bind.
- **Focused set:** M4, M5, suggestions, inspection, app API, delimiters and app default give 200 passed; M6 and M7 app API pass.

**Next: 5b.**
- **Text:** selector discovery inside framing, and objective-named presets.
- **Images:** manifest columns, box-format evidence, and guided comparison and multilabel presets.
- **Records and documents:** key suggestions and honest model status.

## Stage 5b: text, images, records and documents (2026-11-25)

**Discovery** (`src/datatrust/inspection.py`, advisory; never in specifications or fingerprints):
- `discover_selectors(records)` runs over the records a workflow already reads, at most 128. It reports each selector (a top-level name or a JSON Pointer one level down) with presence and type counts.
- Rules:
  - R-TEXT-1, content;
  - R-ID-1 and R-ID-2, identity; never a path column;
  - **R-SPLIT-1** (new), split vocabulary;
  - R-CAT-1, label;
  - **R-PATH-1** (new), image file extensions;
  - **R-LIST-1** (new), lists of short values, i.e. several labels;
  - **R-BOX-1** (new), lists of objects with four-number boxes.
- `box_evidence` states the box ranges and the formats they are consistent with. It never chooses, because width-height boxes fit any range.

**Text** (`text_web.add_m6_source`, `m6.tsx`):
- The framed records read at add time now feed discovery.
- Presets carry objective names: "A text corpus", "Labelled text, one label", "Labelled text, several labels", "Tagged tokens", "Labelled spans", "Question answering", "Prompts and completions", "Conversations", "A retrieval corpus".
- Configure shows chips for content fields, labels (as annotation rows linked to the declared or suggested content field), record identity and split.

**Images** (`image_web.py`, `m7.tsx`):
- **Manifest discovery** at add time, stored beside the specification's own source dicts. It gives the source headers plus chips for image path, logical identity, split, labels or a labels list, objects, and the box formats the values are consistent with.
- **New guided presets:**
  - "Several labels per image": a manifest with task `multilabel_classification`.
  - "Compare two image sets": folders or manifests, roles reference then current, set automatically. Guided configure builds `ImageComparisonSpec(reference, current)`, with "Align the two sets by logical identity". Before this it was reachable only through the JSON specification.

**Records and documents** (`cross_web.py`, `m9.tsx`):
- **Record discovery** for structured CSV, JSONL and Parquet sources: columns and identifier candidates. The sources list shows them, and the association builder offers left and right key chips for the chosen sources.
- **Model status before selection** (`cross_web.model_status`, read-only from the publisher registry and the current algorithm identity). In this build both optional models report "qualification stale … its judgments abstain", which matches the open founder decision.
- The models' identity hash covers `cross.py`, `cross_models.py`, `cross_documents.py`, `cross_diagnostics.py`, `cross_sources.py` and `cross_contracts.py`. None of them was touched; only `cross_web.py` changed.

**Checked in the browser** (in-process server with a data root):
- **Text:** a labelled reviews JSONL, all four chips applied (label first, then content) → bound to Confirm.
- **Images:** "Compare two image sets", with two manifests added as reference then current → inspection → path and identity chips, split, and box evidence ("consistent with xyxy, xywh … not established").
- **Records and documents:**
  - two record sources, each listing `invoice_id` as a possible key;
  - the left-key chip filled the field;
  - both models reported stale qualification before selection.
- **Layout:** 375 px with no overflow and no console errors.
- **Captures:** `work.nosync/guided/visual/stage5/`.
- **Fixed during inspection:**
  - a path column was also offered as an identity, and the chip showed the wrong rule code;
  - a label chosen before the content field pointed at a missing field.

**Tests** (`tests/test_source_suggestions.py`, +3):
- text discovery, with chip-built rows binding;
- the image comparison preset building the comparison, and manifest discovery with box evidence;
- record key candidates and model status, with discovery absent from the specification.
- The focused set (M6, M7, M9 app API, suggestions, inspection, input suggestions) gives 180 passed.

**Not in 5b.** M7 mapping fields stay free-text inputs; the chips fill them, but there is no header picklist. Image split-separation requirements remain JSON-only.

## Stage 6B: regression dependency search, implemented (2026-11-25)

The founder approved the dossier as recommended:
- **D0:** implement `regression_dependency_v1`;
- **D1:** m = 5;
- **D2:** no tolerant variants;
- **D3:** declared-available is Low.

**Implementation.**
- `src/datatrust/regression_dependency.py`, ported from `validation/regression_dependency/prototype.py` without the ablation switches or tolerant variants.
- **Contract:** `RegressionOptions.dependency_search` (`RegressionDependencyOptions(limits=DependencyLimits())`).
  - `from_dict` accepts `true`, `false` or `{"limits": {...}}` and still refuses other keys.
  - `omit_default_delimiter` leaves the key out of every record when it is off. This covers the M3 declarations, the job view and the specification fingerprint.
- **Wiring:**
  - `core.py` records the block, the check and the evidence for single-target regression. It uses availability from both `feature_availability` and context.
  - `regression.multioutput_evidence` records one block per output under a shared budget, and searches every declared feature, text included.
  - Findings are emitted in `risks.py` (core) and `m3.py` (multi-output), with guidance through the existing `target_relationship`, `target_relationship_unknown` and `deterministic_predictor` entries.
  - Dashboard routes go to the relationships chapter (`finding-routes.json`).
  - **Report catalogue entries are deferred to 6D.** Adding them to `report_catalogue.py` changes the pinned regression presentation identity and the frozen M2 report hashes, so they wait for 6D's single deliberate re-pin. Reports already render the findings without them.
- **Interfaces:**
  - CLI `--regression-dependency-search`.
  - The app's Advanced toggle for "Numerical outcome" and the multi-output M3 Advanced section.
  - The review panel states which relations are searched, with or without the option.
  - Interpretation adds a summary sentence when the search ran, and a "more conclusive" entry (`dependency_search`) when a regression result did not use it.

**Acceptance.**
- **Off is byte-identical.** All 33 retained regression and M3 cases (18 regression, 15 M3) were re-run with the current code and with the same code minus 6B. The normalised analysis JSON is identical for every case. The stored historical JSON cannot serve as the baseline, because earlier stages changed unrelated keys; this comparison isolates 6B.
- **On, the retained corpus raises exactly the dossier's four hand-reviewed flags, and none elsewhere** (20 corpus files):
  - mutation `sum` (`a`);
  - `missing_nonfinite` (`input`);
  - `constraint_union` (`input`);
  - `presentation/partial` (`qa_optional_failure`).
- **Tests:** `tests/test_regression_dependency.py` (31):
  - contract;
  - off adds nothing;
  - the corpus flags;
  - planted families: lookup, binned copy, strict log, step;
  - identifier gate;
  - a permuted target, 5 seeds, raises nothing;
  - severity by declared availability;
  - the budget bound;
  - multi-output shared budget;
  - CLI;
  - the app toggle and the review wording.

**Not done.** The dashboard's relationships chapter shows the new findings, but has no dedicated table of the search's per-feature checks; the block is in the JSON. Reports render the findings; report-level summaries arrive in 6D.

## Stage 6A: direction-preserving comparisons (2026-11-25)

**Change** (`comparison.py`, methodology `m4_local_2026_11_25`):
- Every compared column records `missingness_direction`, `missingness_magnitude` and `missingness_material_decrease`, and the same three fields for non-finite values.
- **Increases** at or beyond the threshold keep the existing "Supported input or annotation populations differ" finding, unchanged.
- **Decreases** at or beyond it are recorded as a `material_changes` measurement (`evidence_type: material_change`, with the possible causes: imputation, back-fill, a changed collection process, row filtering). They never produce a finding or warning.
- `ComparisonConfig.methodology` records the version, and `m4_local_2026_10_10` reproduces v1 output exactly. Advanced single-source analysis keeps `m4_local_2026_10_10`.
- The companion's known methods, the frontend resolver and the dashboard-case composition helper accept both ids.

**Presentation.**
- The populations table adds a direction column (↑/↓, percentage points, "material change") for direction-preserving results only.
- The material-changes check is named "Material changes (not findings)".
- Interpretation adds "N material decreases (missing values in age). A decrease is a material change, not a defect: …". The numbers trace to the recorded measurement.

**Tests:** `tests/test_comparison_direction.py` (6):
- a decrease is a material change, not a finding;
- an increase keeps the finding, and both directions can coexist;
- non-finite decreases follow the same rule;
- small changes record direction only;
- v1 reproduces v1 output, with no direction fields;
- the interpretation sentence traces.

M4, before/after, comparison-dashboard, guidance and interpretation suites give 240 passed.

**Full suite after 6A and 6B:** 1,835 passed and 2 failed.
- **Failures:** `test_m2_parity`'s frozen concrete report hash, and the regression presentation-identity pin.
- **Cause:** both came from the report-catalogue entries above.
- **Fix:** reverting those entries makes both pass. The M2 parity, report layout and 6B tests then give 88 passed. A direction-preserving result renders through the dashboard composition (Node harness) with the material-change sentence.

### Review of 6A and 6B (2026-11-25)

An independent review (a Sonnet subagent, read-only) checked both stages against the dossier and the plan. It confirmed that the port matches the prototype: 60 randomized datasets gave identical status, checks, flags, exclusions and budget.

It found these issues, all fixed and covered by tests.

**6B, important**
- **Declared column meanings never reached the search.**
  - The `declared_identifier` exclusion and the near-unique exemption for declared-categorical columns were dead code.
  - Both callers now pass `features.semantic_types`.
  - Declaring a meaning moves a run to the role-aware method, so the multi-output path carries it too.
- **Single-target findings had no evidence link.**
  - Finding paths pointed at `…/dependency_search/flags/{i}`, while the evidence sits at `…/dependency_search`.
  - The paths now match, so findings link to the `regression_dependency_search` evidence.
  - The evidence denominator now counts feature-target checks, with matching wording.

**6B, minor**
- **Multi-output ignored availability declared through context.** It now merges context and `feature_availability`, as single-target does.
- **Multi-output recorded no check outcome.** Each output with a search now records `regression_dependency_search`.
- **The `partial` status was never produced.** A cooperative interruption now keeps what was searched (status `partial`, with the unsearched features named) instead of dropping the block.
- **`RegressionOptions(dependency_search=False)` raised an error.** It now means off.

**6A, important**
- **Segment-level material changes were summarised as if they applied to the whole file.** The summary now reads source-pair scopes only. Segment records keep their own scope and say "rows of this segment".

**6A, minor**
- **Dashboard tile.** The material-changes tile now sorts after Populations and reads "N material decreases".
- **Methodology validation.** A non-string methodology is now refused with the intended error.

**Re-checks after the fixes**
- Search-off output is still identical to the pre-6B code on all 33 retained cases.
- The affected suites give 467 passed: M4, before/after, comparison dashboard, guidance, interpretation, outcome states, app API, M3, M2 parity, report layout, 6A and 6B.

## Stage 6C: readiness v2, prerequisite evidence (2026-11-25)

The expected results were registered first, in `validation/guided/readiness_v2_expectations.md`, before any 6C code ran on the retained cases.

**Method** (`unsupervised.py`; new runs record `tabular_clustering_readiness_v2` and `tabular_anomaly_readiness_v2`):
- **`complete_case_coverage`:** the share of rows with every quantitative-geometry feature finite. Finding `limited_complete_case_coverage`:
  - Low below 80% (the dependency searches' coverage gate);
  - Moderate below 50% (the column-missingness High boundary).
- **`redundant_quantitative_features`:** exact duplicates, and pairs with |Pearson r| ≥ 0.98 (the existing M4 gate).
  - A pair qualifies only with ≥ 100 rows of finite overlap and ≥ 10 distinct values per column.
  - Finding `redundant_quantitative_features` is Low and worded "may be intended", never a defect.
- **Bounded pair search:** at most 64 features and 2e8 row work (`DependencyLimits`). Declared quantitative features go first, then source order. Beyond the bounds the status is `bounded` and unsearched pairs are counted.
- **Policy:** `guidance.policy` for the v2 methods states every threshold and the "no verdict" rule.
- **Guidance:** new catalogue entries `complete_case_coverage` and `redundant_features`. Their unknowns are mapped (to no declaration) in the interpretation's resolution table.
- **Kept:** "No model is fitted; no readiness verdict" stays in the evidence, the interpretation and the dashboard.
- **v1 results** keep their method id and render unchanged. The companion, dashboard resolver, review panel and case-composition helper accept both versions.

**Presentation**
- The coverage finding routes to the missing-values tile, and the redundancy finding to the geometry hero.
- The geometry chapter lists near-duplicate pairs with r, or "None among N pairs searched", plus unsearched pairs when the search was bounded.
- The interpretation summary states the complete-row count and the number of redundant pairs, both traceable.
- Report catalogue entries for the two new codes are deferred to 6D's re-pin, as in 6B.

**Retained cases match the registered expectations exactly:**

| Case | Complete rows | Redundant pairs | Findings |
|---|---|---|---|
| energy_clustering | 768 of 768 | relative_compactness ≈ surface_area (r = −0.9919); the other inputs have fewer than 10 distinct values | `redundant_quantitative_features`; scale review unchanged; no coverage finding |
| energy_anomaly | 768 of 768 | as above | as above |
| linnerud_clustering | 20 of 20 | none (below the 100-row gate) | scale review only |
| linnerud_anomaly | 20 of 20 | none (below the 100-row gate) | scale review only |

**Tests:** `tests/test_readiness_v2.py` (9):
- coverage at 90%, 70% and 40%;
- exact duplicate and near-collinear pairs found, a looser pair not;
- small and coded columns skipped;
- feature and row-work bounds disclosed;
- declared features searched first;
- the retained-case expectations;
- no verdict, and the thresholds stated in the policy.

A v2 result renders through the readiness composition (Node harness).

**Full suite:** 1,851 passed and 1 failed. The failure was the resolution-table mapping for the new guidance unknowns; it is fixed, and the interpretation, readiness, guidance and outcome-state tests give 205 passed.

**Founder gate (open):** final review of the thresholds and wording above.

## Stage 6D: report intelligence (2026-11-25)

The founder approved the 6C thresholds and wording, and Stage 6D started.

**One source of interpretation for dashboards and reports.**
- The renderer passes `interpret(value, family)` to every report family as `I`.
- A shared macro, `guidance_layers.interpretation`, renders it right after the guidance scope box in all nine families:
  - **"In brief":** the summary sentences;
  - **"A clean result, and its scope":** completed checks out of recorded, the review thresholds not met, and what is not established;
  - **"What would make this more conclusive":** each declaration and what it makes possible, with "Supply these in a new run";
  - the interpretation version.
- The dashboard companion carries the same object. The report authors no interpretation text of its own.

**Catalogue entries deferred from 6B and 6C, now added** (`report_catalogue.FINDING_CONCEPTS`): the three `regression_dependency_*` codes map to `target_relationship`, and `limited_complete_case_coverage` maps to `missingness`.

**Deliberate re-pin.**
- `datatrust.interpretation` joined the shared presentation modules, so every family's identity names it.
- `validation.report_experience.repin` re-asserted every analytical value and changed only HTML hashes:
  - 18 of 18 M2 and 3 of 3 M1 report hashes;
  - all 9 presentation identities.
- The re-pin is named in `docs/CURRENT_STATE.md`.
- Saved reports are not re-rendered: history serves the stored `report.html`, bound by its hash, and never calls the renderer.

**Checks.**
- New `tests/test_report_interpretation.py` covers all 74 dashboard-corpus cases. Each report renders every summary sentence and every "more conclusive" item of `interpret()` unchanged, and a clean result shows its scope. The companion's interpretation equals the one the report rendered.
- Captures (`work.nosync/guided/visual/stage6d/`): Bike Hour "In brief" and the wide_200 clean scope at 1280 px, plus four rendered reports. During inspection a duplicated word ("Interpretation interpretation_v1") was fixed, and the re-pin was re-run on the final template.

**Full suite:** 1,923 passed and 3 failed. The three failures were the pin tests, caught mid-edit while the wording fix landed. After the final re-pin, the pin, M2/M1 baseline, report-layout and report-interpretation tests give 179 passed.

**Not done.** "Consequence ordering" of findings keeps the existing priority order; no re-ordering was introduced.

## Stage 7: closure (2026-11-25)

**Docs**
- `docs/ARCHITECTURE.md` has new sections on the shared interpretation (`interpretation_v1`) and the guided start and configuration. The Input Inspection Boundary, regression dependency search, readiness v2 and direction-preserving comparison sections were added in earlier stages.
- `docs/GETTING_STARTED.md`:
  - the Start page, layers and review;
  - the opt-in dependency search;
  - direction-preserving comparisons;
  - the readiness v2 prerequisites.
- `README.md` has a new "Guided start" line.
- `docs/CURRENT_STATE.md` names the 6D re-pin and the analytical changes.

**Matrix and walkthrough:** `validation/guided/CLOSURE.md` maps every row of plan §O to its evidence, and lists the known gaps as follow-ups.

**Final runs**
- DataTrust suite: 1,926 passed.
- M9 with CG1: 80 passed.
