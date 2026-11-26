# Results dashboard redesign: representative corpus (Stage 0)

Stage 0 of the approved workflow-specific dashboard redesign. It sets up three things:
- a fixed set of real DataTrust results for every planned dashboard composition;
- a node harness that runs the app's own TypeScript against them;
- a visual baseline of today's results pages.

It changes no product code, template, analytical result or historical artifact.

## What is here

| File | Purpose |
|---|---|
| `cases.json` | 75 cases. Each has a composition (the dashboard that will render it), variant, history workflow and mode, source and tags. |
| `corpus.py` | Materialises every case into `validation/report_experience/work.nosync/dashboard/cases/<name>/`: `analysis.json`, `report.html` (current templates, no reanalysis) and `case.json` (origin, digest, recorded facts). |
| `controlled.py` | Seven small controlled cases where no retained result exists (listed below). |
| `baseline.py` + `capture.mjs` | Save every case into a throwaway history, serve the packaged app on loopback, and capture each saved result headless at five sizes. Chapters are captured at 1440 × 900. |
| `../../tests/dashboard_harness.py` | Manifest helpers and `Node`, which bundles a frontend TypeScript entry with esbuild and calls its exports in node. |
| `../../tests/test_dashboard_cases.py` | Manifest integrity, facts against tags, method against composition, stored copies byte-identical, every case rendered, and the current adapter keeping every core finding reachable. |

## Sources

| Kind | Cases | How built |
|---|---|---|
| **stored** | 55 | The completed JSON a milestone recorded, read only and copied byte for byte. |
| **matrix** | 13 | Rebuilt with the Report Experience builders (`validation/report_experience/cases.py`). Normalised JSON equals the retained `after_review_fixes` JSON for all 9 matrix cases compared. |
| **controlled** | 7 | Built by `controlled.py` (below). |

Four cases are optional and heavy: `wide_flagged_1000`, `wide_5000`, `tall_1m` and `unlabeled_wide`. Build them with `--heavy`; tests skip cases that have not been built.

**Controlled cases.** These are presentation test inputs, not validation claims.
- `classification_partial`: German Credit with declared context. The one optional classification stage (contextual evidence) is made to raise, so the engine publishes its honest partial result. This is an injected fault.
- `annotation_regression_single`: one numerical target with optional annotations (`tabular_annotation_regression_v1`). No retained case existed.
- `m4_before_after`: the German Credit fixture of `tests/test_before_after.py`.
- `m6_clean`, `m9_clean`: zero-finding text and reconciliation runs. No retained clean case existed. M9 uses a decimal rule only, so no model is involved.
- `unlabeled_wide`: the WS4 wide generator profiled without a target.
- `generic_unknown_methodology`: german_credit relabelled `future_method_v9`, schema 9.9. Test-only.

**Coverage.** Every composition has cases with findings or clean results. The corpus as a whole has clean, partial, bounded, High-priority and historical (pre-guidance) cases. Cases that still don't exist:
- a real-data M7 case with findings (findings come only from the synthetic overlay);
- an M9 image–text report;
- a partial M5 or M6 run (M6 cannot be partial by design).

## Reproduce

Build the corpus:
```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:. .venv/bin/python -B -m validation.dashboard.corpus
```
Add the heavy cases:
```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:. .venv/bin/python -B -m validation.dashboard.corpus --heavy wide_flagged_1000 wide_5000 tall_1m unlabeled_wide
```
Run the tests:
```bash
NUMEK_PLATFORM_DSN=skip PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:. .venv/bin/python -B -m pytest -q -p no:cacheprovider tests/test_dashboard_cases.py
```
Capture the baseline (needs Playwright, used from `frontend-visual-lab-v3/node_modules`, and a local Chromium in the Playwright cache):
```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:. .venv/bin/python -B -m validation.dashboard.baseline --label baseline
```

`NUMEK_PLATFORM_DSN=skip` stops `tests/conftest.py` from starting the ConfidenceGuard PostgreSQL cluster for a run that doesn't need it.

**Capture output** goes to `work.nosync/dashboard/visual/<label>/`, which is git-ignored:
- per case, `<size>-first.jpg`, `<size>-full.jpg` and `<size>.txt` (page text);
- `w1440-chapter-NN-*.jpg` and `w1440-chapters.json`;
- `sheets/<case>-sizes.jpg` and `sheets/<case>-chapters.jpg`;
- `capture.json`, with the render state, time and console errors for each page.

Sizes are 1920×1080, 1440×900, 1024×768, 768×1024 and 375×812. Reduced motion is emulated so captures are deterministic. Nothing is revealed, downloaded or changed in the app.

## Baseline (2026-11-24)

**Capture totals:** 75 cases, 375 page captures (five sizes) and 924 chapter captures. Every page rendered and no console errors were recorded. Median render at 1440 × 900 was 553 ms (maximum 663 ms, `multilabel_wide`). Captures are in `work.nosync/dashboard/visual/baseline/`.

These observations come from the captures and confirm the plan's audit (sections A and C):
- **Score tile without a score (D6).** Unlabeled, regression and M3 pages open on a large "No score defined" Score tile. Imbalance, Relationships, Time, Text, Images and Documents read "Not for this data", for example 6 of 14 tiles for `german_unlabeled`.
- **Schematic beside recorded evidence (D16).** `bike_hour`'s Relationships chapter shows a schematic drawing next to the recorded `cnt = casual + registered`.
- **Made-up priorities (D1).** `m7_overlay` Actions label both declared violations ("quality expectations", "split requirements") as **LOW** and the near-duplicate investigation candidate as **MODERATE**. Neither label is recorded in the analysis.
- **New: unknown methodology drawn as classification.** `generic_unknown_methodology`, a saved entry whose mode is classification, is drawn as a fully scored classification page ("91.8 · Low") because the app falls back to the saved mode. Stage 1's resolver must key on the recorded methodology and fall back to the generic composition.

## Stage 1: shared shell, presentation companion, M4–M9 on the shell (2026-11-24)

**Backend (additive, read-only).**
- `src/datatrust/dashboard_companion.py` (`dashboard_companion_v1`) reuses each workflow's `report_view` for finding titles, ranks, the text and image report actions, and concept entries.
- Every report locator is verified against the exact HTML being served:
  - anchors are checked for the id and the finding-index link text;
  - fallbacks are the report section, then the position in the finding index, then none.
- Its cache key is the scope, the analysis and HTML digests, the presentation identity, the print profile and the disclosure context.
- New routes: `GET /core/job/presentation`, `/m4/…`, `/temporal/…`, `/text/…`, `/images/…`, `/cross/…`, `/history/<id>/presentation`.
- Older saved reports (no finding ids or index) honestly get `none`.

**Frontend.**
- `results/{model,normalize,resolve}.ts`, `results/shell/*` (results shell, findings ledger, coverage ledger, report bar), `results/charts/*` and `results/compositions/{common.ts,generic.tsx}`.
- M4, M5, M6, M7 and M9 live and saved results, and unknown methodologies, are drawn on the shell.
- Core and M3 keep the Modules page until Stages 2–3 (approved interim).

**Defects closed:**
- D1: text and image ranks are the recorded evidence meaning, in the report's order.
- D5: a pair is coral only when a finding cites both of its images.
- D9: the composition comes from the recorded methodology; an unknown one is "shown as recorded", not drawn as classification.
- D10: "Open live result" opens the right workflow.
- D14: an unreadable result offers a retry instead of waiting forever.
- No-score wording appears once, under Methodology.

**D8 verified, not a defect.** M7 and M9 jobs record a partial run as job state `completed` with `execution.status: partial` (`image_web.py:168`, `cross_web.py:198`), so partial results already reach Report. The shell shows them as partial (`m7_partial` lists its failed `embeddings` check).

**Checks:**
- **Visual:** 38 cases at five sizes plus every chapter at 1440, and 5 cases with every chapter at 375. No render failures and no console errors.
- **Ledger:** "Evidence" opened and focused the right chapter block in all 26 cases with findings. "In report" opened an anchor that exists in the served report in all 26.
- **Fixed during inspection:** the ledger rank column was too narrow for "Contextual observation"; the earlier-version note moved into the outcome band so the hero stays nearer the fold at 1440 × 900; the temporal chapter uses the shared rank mark.
- **Left for later stages:** raw nanosecond ticks in temporal chapters (Stage 5); generic "Measured" tile faces in M4 (Stage 4); long M7 tile labels (Stage 6); "no score defined" pills in the history rail (Stage 7).

## Stage 2: classification and dataset profile (2026-11-25)

**What changed**
- **Classification composition** (`results/compositions/classification.tsx`), on the shell, live and saved:
  - the reliability score hero shows the overall score and risk band, the governing cap with its explanation, and the sub-score bars with the critical line at 50 and a coral mark at the cap;
  - other tiles: target balance (a ranked class list, replacing the waffle that coloured class 4+ in coral), leakage name review (with recorded context declarations), missing values, repeated rows and label disagreement (recorded counts, no invented group sizes), feature usability (IQR bars, zero-IQR columns, usability points), and a paged, sortable columns table.
- **Dataset profile composition** (`profile.tsx`) for unlabeled and role-aware profiles. The hero counts columns per recorded flag on independent bars, each on its own 0–column-count scale (flags overlap). Other tiles: missing values, repeated rows, variation and cardinality, numeric values, columns, parsing review.
- **Finding routes.** Shared tiles live in `tabular.tsx`. `finding-routes.json` routes every classification, unlabeled and contextual code explicitly; anything else would go to an "Other findings" tile, and every finding is always in the ledger.
- **No-score wording.** For unscored workflows, the summary band leads with the first recorded sentence that doesn't mention a score; the no-score reason appears only under Methodology.

**Defects closed:** D2 (coral class colours), D3 (invented duplicate sizes), D4 (name-length bars), D6 (score tile on unscored runs), D7 ("N of 14 checks apply"), D11 (classification HTML download), and D13 for these workflows (a findings ledger, with full wording).

**Found and fixed during verification**
- `guidance.scope.not_completed` also records *excluded* checks (a method precondition such as zero IQR). The coverage ledger listed them under "Did not complete" and marked the page partial. They now go to "Excluded for a precondition". The projection test now refuses "partial" unless the run is partial or a check failed or was interrupted.
- Contextual findings now count toward their tile's face. Face charts no longer run over tile text or the "Open" mark. A profile field the methodology does not record is left out instead of shown as "Unavailable". "No column has a missing value" replaces "unavailable" when there is nothing to draw.

**Checks**
- **Saved results:** 15 cases at five sizes plus every chapter at 1440, and 2 cases with every chapter at 375. No render failures or console errors.
- **Ledger:** "Evidence" focused the finding in all 11 cases with findings. "In report" opened an existing anchor in 10 of them. In `bank_full_declared` the first finding is contextual and the report gives contextual findings no anchor, so the link honestly falls back to "search the report".
- **Live:** German Credit run through the real Upload → Configure → Confirm → Report flow headlessly, as classification and as unlabeled. Both open the new pages, show no "of 14 checks", offer the HTML download, and "In report" lands on a verified anchor.
- **Not fixed:** a session race in the live app's first load. The first-use "Save / Don't save" request can fail with "A current CSRF token is required" when it is sent before the app's other startup requests finish rewriting the session cookie. This is unrelated to the dashboard and left for a separate decision.

**Tests:** `tests/test_dashboard_tabular.py` (routes and recorded values for every classification and profile case) and the stricter projection test. The DataTrust suite (without ConfidenceGuard and M9) passed 1,370 with 1 skipped; M9 and CG1 passed 80 at Stage 1, and Stage 2 does not touch them.

## Stage 3: numerical outcomes and the M3 compositions; the fixed mosaic retired (2026-11-25)

**What changed**
- **Numerical outcomes** (`compositions/numeric.tsx`): single regression, annotation regression and multi-output regression share one composition. It reads `profile.regression` or each `profile.multioutput_regression.outputs[]` under one shape.
  - The hero is the target's recorded histogram (bins, method, denominator) and quantile strip with the IQR fences; multi-output shows vector completeness and an output picker.
  - **Relationships** quote the recorded expression (Bike Hour: `cnt = casual + registered`, fully verified), replacing the schematic drawing.
  - Other tiles: declared constraints (violating counts over denominators), distribution shape (rounding grids, boundary concentration), output dependencies, repeated inputs, availability and name cues, annotation coverage, and the shared tabular tiles.
- **Annotation** (`annotation.tsx`): annotation coverage per target and per row vector, observed classes, cohort contrasts and repeated inputs. `annotationTile` is shared with the numerical and multilabel compositions.
- **Multilabel** (`multilabel.tsx`): label vectors (completeness, prevalence), cardinality (or the recorded reason it is unavailable), label pairs, declared constraints. Pair-search and combination bounds are stated in coverage.
- **Readiness** (`readiness.tsx`): feature geometry, with the hero saying "No model fitted; no readiness verdict". Other tiles: scale, sparsity, categories, repeated vectors, and extreme candidates for the anomaly variant only.
- **One entry, one route table.** `compositions/index.tsx` (`TabularPage`) now draws every core and M3 result, live and saved. `finding-routes.json` routes every code the core, regression, M3 and contextual engines can emit, dynamic suffixes included. Each composition checks routes against the tiles it actually drew, so a route to a tile a variant doesn't draw goes to "Other findings".
- **Retired:** `results/Mosaic.tsx`, `viz.tsx`, `modules.ts`, `outcome-map.json` (`git rm`). `adapter.ts` keeps only shared readers. The M3 Confirm step's planned-check list is now a short static list.

**Fixed during verification**
- The regression narrative opens with "…not a score or readiness verdict", so "not … score" also counts as a no-score sentence; the summary band leads with the recorded evidence summary.
- The missing-values tile listed target and label columns whose absences are annotation gaps; it now lists feature columns and says target absences are shown with the target's evidence.
- Shorter relationships kicker; thousands separators in constraint counts; "outside at least one feature’s fences".

**Checks**
- **Saved results:** 24 cases at five sizes plus every chapter at 1440, and 3 cases with every chapter at 375. No render failures or console errors.
- **Ledger:** in all 15 cases with findings, "Evidence" focused the finding and "In report" opened an existing anchor.
- **Live:** classification, unlabeled and regression (Bike Hour) runs through the real Upload → Report flow land on their compositions, with no "of 14 checks", an HTML download and a verified report anchor.

**Tests**
- `test_outcome_states.py` was rewritten against the route table and coverage states, keeping its guarantees and `emitted_codes()`.
- `test_dashboard_tabular.py` covers all six tabular compositions against recorded values.
- The Stage 0 harness test now runs the ledger projection.
- The DataTrust suite (without ConfidenceGuard and M9) passed 1,440.

## Stage 4: comparison depth (M4) (2026-11-25)

- **One pure builder.** `roles.tsx` now exports `m4Dashboard(analysis, companion, saved)`; `RolesReport` only waits for the companion and renders the shell. The node harness can therefore check the M4 dashboards against recorded values (`tests/dashboard_entry.ts` exports `comparison` and `structure`).
- **Tile faces state recorded values**, never a generic "Measured":
  - populations, annotation cohorts, overlap row unions, segments and blocked alignment each have a recorded summary;
  - constraints describe their rules and the affected row union;
  - a schema change names the column and its storage change ("z: BIGINT → DOUBLE");
  - a declared violation reads "High · declared requirement violated".
- **Populations.**
  - The face ranks the recorded CDF distances, largest first.
  - The chapter shows CDF distance (quantitative columns) and total variation (categorical columns) as two separate rankings, never mixed. It adds a column table (CDF, TV, normalised W1, median shift, missingness change, review flags) and the recorded quantiles with axis ends and a legend.
  - Coral marks a column only when a finding cites the comparison and the column carries its own `distribution_review` flag.
- **Schema** draws removed columns as dashed outlines.
- **Lead tiles.**
  - Before/after leads with the row lineage: retained, dropped and added identities by the declared key, the recorded reconciliation and the not-improvement statement. Its chapter adds declared transformations, missing values before and after, target classes before and after, and the remaining risks; Roles becomes an ordinary tile.
  - The advanced single-dataset analysis leads with Structure: missing rate per column, or the columns by recorded role when nothing is missing.
- **Coverage.**
  - Recorded check outcomes come from `checks` once, worded with their roles ("Excluded · Columns not aligned · reference ↔ current"). A blocked precondition is an exclusion and never makes a completed run partial; a failed diagnostic does.
  - Unsearched scope is listed under Bounded.
  - A diagnostic status alone no longer gives a tile the coral finding tone.
- **Removed:**
  - a "class shares moved ≥ 2 points" fact the backend never defined;
  - repeated before/after statements in the chapter.

**Checks**
- **Saved results:** all 10 M4 cases captured at five sizes, every chapter at 1440 (97 chapters), and 4 cases with every chapter at 375. No render failures or console errors.
- **Ledger:** in all 9 cases with findings, "Evidence" focused the finding and "In report" opened an existing anchor.

**Tests**
- New `test_dashboard_comparison.py` (20 tests) checks every M4 case against its recorded values. It covers:
  - ledger refs and priorities;
  - "role ↔ role" scope;
  - schema and population faces;
  - before/after lineage;
  - partial versus excluded states;
  - bounded diagnostics.
- The DataTrust suite (without ConfidenceGuard and M9) passed 1,460.

## Stage 5: temporal depth (M5) (2026-11-25)

- **One pure builder.** `results/compositions/temporal.tsx` exports `temporalDashboard(analysis, companion, saved, {live, investigate})`. `m5.tsx` keeps only the flow and `TemporalPage`, which waits for the companion and renders the shell. The node harness exports `temporal`.
- **Ticks in their recorded unit** (`results/ticks.ts`):
  - chronology evidence records `clock_units`: nanoseconds for instants and local date-times, days for civil dates;
  - before this stage the timeline read every tick as nanoseconds, so the civil-date ALFRED panel was misdrawn;
  - instants and durations are now shown as dates and readable spans ("every 1 hour", "15 minutes"), never as raw integers. Spans under three days show the time in UTC (the synthetic wide panel spans four minutes);
  - this fixes the raw nanosecond values that overflowed chapter tables at 375 px.
- **Timeline hero:**
  - The face is the compact span drawing; its label is the observed span and the number of series and entities.
  - The chapter draws each series as an HTML row named by entity and measurement, so labels meet the 11 px minimum at every width. It lists the clock and schedule per source and a retained-series table with formatted first, last and span.
- **Topic tiles state recorded counts:**
  - **Chronology:** clock cells by parse state, backward steps and conflicting identities. The chapter shows clock, precision and value states, ordering (largest backward step as a duration) and repetition.
  - **Continuity:**
    - With a declared schedule: occupied over expected slots (proportion bar, coral when cited), absent slots, longest gap in slots, gap witnesses and schedule cadence.
    - Without one: the tile says "No schedule declared: continuity not assessed", shows the observed spacing between observations, and lists the source once under Not requested. A continuity check that was itself excluded stays listed once, as excluded.
  - **Behavioral investigation:**
    - The face counts window comparisons meeting the configured investigation settings.
    - The chapter shows per-measurement bars (coral where a finding cites that measurement's windows) and the recorded interpretation, the settings, and every comparison (windows, support, CDF, normalised W1, missingness change, which setting was met).
    - It also lists the windows with formatted spans, runs, volatility, within-series comparisons and search scope.
    - Everything is worded as investigation candidates, not defects.
  - **Availability and outcome maturity:** features whose availability is unknown are listed by name ("unknown unless declared; no timestamp is inherited"). Revision histories show comparison states, inconsistencies and units with the recorded agreement meaning.
  - Evidence with no designed view is shown as its own facts and table, with ticks formatted.
- **Long names wrap:** tile names wrap beside their kicker, and the behavior face no longer squeezes a chart under a two-line label.

**Checks**
- **Saved results:** all six M5 cases at five sizes with every chapter at 1440, and four cases with every chapter at 375. No render failures or console errors.
- **Ledger:** in the four cases with findings, "Evidence" focused the finding and "In report" opened an existing anchor.
- **Locators:** every one of the 35 findings routes to the topic holding its cited evidence. Its report locator is an anchor or a stated finding-index position (`test_dashboard_temporal.py`).

**Tests**
- New `test_dashboard_temporal.py` (26 tests) covers, for each case:
  - ledger and priority;
  - topic routing;
  - no raw ticks or score wording on faces;
  - chronology, behavior and availability face counts;
  - continuity only against a declared schedule;
  - the High schedule violation shown as critical;
  - tick units on the timeline;
  - bounded behavioral scope.
- The DataTrust suite (without ConfidenceGuard and M9) passed 1,486.

## Stage 6: text, image and records depth (M6, M7, M9) (2026-11-25)

- **Pure builders.** These live in `results/compositions/`:
  - `text.tsx` (`textDashboard`), `image.tsx` (`imageDashboard`) and `cross.tsx` (`crossDashboard`);
  - `evidence.tsx` holds what they share: record view, finding block, count bars, the report-name lookup and tone.

  The pages (`m6.tsx`, `m7.tsx`, `m9.tsx`) keep the flows and their live, private controls. They pass those controls in as slots:
  - text Reveal and Export excerpts;
  - the image pair viewer with overlays, labels and examples export;
  - the review-target table with Inspect, disclosure and review import and export.

  The builders never touch an API. The node harness exports `text`, `image` and `cross`.
- **Report names from the companion.** `dashboard_companion_v1` now also returns `names`:
  - text and image family titles and evidence-meaning labels (`*_presentation.family_title` / `MEANINGS`);
  - records-and-documents section titles, population names, outcome labels and per-population explanations (`cross_presentation`).

  Tiles, ranks and outcomes use the report's words instead of copies in TypeScript, the same kind of copying that produced the M6/M7 priority defect. Without a companion, the dashboard falls back to the recorded words.
- **Heroes:**
  - Text: **Review actions**, the report's `executive_summary` groups in its order, with their observations. The chapter adds the scope sentences (framed records, lexical selection, semantic embedding).
  - Image: **Decisions**, the report's consequence-grouped executive actions with their facts and action text.
  - Without a companion, both list the recorded findings in recorded order and say so.
  - Records and documents: **Reconciliation**, one row per declared rule with its outcomes in the report's words and a bar over its records (coral for discrepancies and conflicting evidence).
- **Family faces state recorded counts with units**, never "Measured". Examples:
  - "9 invalid items"; "nfc: 2 groups · raw: 2 groups" (representations listed, never added);
  - "8 of 9 assets decoded"; "3 groups · 9 occurrences";
  - "41 records · 0 invalid"; "20 optional judgments".
  - Unlabeled image sets show their recorded annotation state, not "0 valid".
  - Family state charts (reasons, states, roles, decode states, validity, rule violations, judgment outcomes) are drawn in the chapters. On small tiles they collided with the label.
- **Honesty:**
  - Image pairs are coral only when one finding's recorded references include both images. In the overlay case none of the three retained pairs is cited directly, and the chapter says so.
  - Optional model judgments are shown as recorded. When every judgment abstained, the tile reads "All N judgments abstained" with the recorded reasons (test on an abstaining copy of the PDF case). "Not requested" appears only when no claim was selected.
  - A perceptual search stopped at a planned bound is listed under Bounded (`m7_bounded`).
- **Private inspection** stays live-only, inside the chapter that holds the finding; saved entries name references and say why they cannot be resolved.

**Checks**
- **Saved results:** all 21 cases (8 text, 9 image, 4 records) at five sizes with every chapter at 1440 (259 chapters), and 3 cases with every chapter at 375. No render failures or console errors.
- **Ledger:** in all 12 cases with findings, "Evidence" focused the finding and "In report" opened an existing anchor.
- **Not in this stage:** live private inspection (reveal, pair viewer, investigate) was not exercised in a browser; it is unchanged code passed in as a slot. Export and history exclusion remain covered by the existing M6/M7/M9 API tests.

**Tests**
- New `test_dashboard_evidence.py` (55 tests) covers:
  - ledger, ranks and the report's meaning labels;
  - report family names;
  - no "Measured" and no score wording;
  - text actions and image decisions equal to the report's;
  - recorded faces, with representations not added;
  - direct-citation pairs;
  - image bounds and partial states;
  - reconciliation outcomes;
  - the not-requested model judgment;
  - the abstention case;
  - a source check that no reveal path writes to the URL or browser storage.
- The DataTrust suite (without ConfidenceGuard and M9) passed 1,541; `tests/m9` passed 42.

## Stage 7: history, cleanup and closure (2026-11-25)

**History.**
- **One outcome per entry** (`results/outcome.ts`), the same in the rail, the list and the sheet: "Score 91.8 · Low" only where a score was recorded; otherwise "3 findings", "9 findings · 1 High", "Partial" or "No threshold-level findings". The words "no score defined" are gone.
- **Filters:** a Workflow filter uses the index's existing `workflow` parameter. The risk filter is labelled "Classification risk band" and shown only for All, Tabular datasets and M4, the workflows that can carry a band.
- **Saved-analysis sheet:**
  - findings are listed by recorded rank for every workflow, with the report's names from the entry's companion; text and image findings used to be dropped because they record no severity;
  - an unscored entry shows its outcome instead of a "No score" block.
- **Titles and meta lines:** an entry without a recorded name or file is titled by its workflow (never blank). Meta lines no longer start with an empty file name.
- **Layout:** filters fill their cells, and the retention fields fit at 375 px.

**Cleanup.**
- 60 dead selectors were removed from `app.css`: the retired score card, strip, scope notes, chapter evidence tables and the unused records-bar class.
- `familyTile`, `BoundedTable` and `SHADES` were removed from `flow.tsx`.
- `foundation/nk.css` is unchanged: the landing site (`site/windows.tsx`) still lays out its Modules mosaic with `grid-area`, so those selectors are in use.

**Docs.**
- `docs/CURRENT_STATE.md`: a new top section, including the defect ledger closure and known limits.
- `docs/ARCHITECTURE.md`: "Results dashboards and the presentation companion".
- `README.md`: one sentence on the per-workflow results pages.

**Closure checks.**

| Check | Result |
|---|---|
| Analysis, scoring, schemas and report templates | Unchanged. In `src/datatrust` only `api_web.py` changed (+57 lines: the companion routes and cache), plus the new `dashboard_companion.py` and the rebuilt app bundle |
| `tests/fixtures/presentation_identities.json` | Unchanged |
| Render time (navigation to rendered dashboard, including Playwright's 0.5 s network-idle wait, 1440 px) | wide_5000 0.64 s, bank_full 0.57 s, M5 Beijing 0.59 s; every case under the plan's 1.5 s budget |
| Visual captures | Every composition at five sizes, every chapter at 1440, phone chapters for representative cases; History list at 1440 and 375, rail and sheet. No render failures or console errors |
| `test_dashboard_history.py` (16 tests) | Outcomes are worded per workflow and never mention a score that wasn't recorded. Workflow and risk-band filters match the index. Older results saved through the history API's own path (classification 1.0, regression 1.1, M3 1.2, M4–M9 without guidance) reopen on their workflow dashboards with the right "earlier version" note |
| Suites | DataTrust suite (without ConfidenceGuard and M9) passed 1,557; `tests/m9` with `tests/cg1` passed 80 |

**Not covered.**
- Live private inspection (M6 reveal, M7 pair viewer, M9 investigate) was not re-driven in a browser. The code is unchanged and passed in as slots; its export and history exclusions stay covered by the existing API tests.
- The pre-existing CSRF race on first app load is not fixed.
