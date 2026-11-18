# Report Experience Redesign — Stage 0: baseline and technical spikes

Stage 0 of the approved Report Experience Redesign plan, recorded on 2026-11-17. It changes no product code, template, test or
historical artifact. It measures today's reports and settles the technical questions the later stages depend on.
Measurements are from one machine; they are not capacity guarantees.

## Reproduce

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:. .venv/bin/python -B -m validation.report_experience.measure --phase before --runs 3
```

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:. .venv/bin/python -B -m validation.report_experience.summarize --phase before
```

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:. .venv/bin/python -B -m validation.report_experience.spikes.weasy_features
```

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:. .venv/bin/python -B -m validation.report_experience.spikes.hidden_cost --runs 3
```

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:. .venv/bin/python -B -m validation.report_experience.spikes.m5_disclosure
```

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:. .venv/bin/python -B -m validation.report_experience.spikes.browser_fixtures
```

The browser spikes were run in the Claude desktop built-in browser against a local static server: the `report-spikes` entry in the
git-ignored `.claude/launch.json`, which runs `python -m http.server 5421` on this folder. Their observations are recorded in
`spikes/results/browser.json` and `spikes/results/browser_tables.json`.

**Environment:**
- macOS 27, arm64, the project `.venv` (Python 3.11.15).
- WeasyPrint 69.0, pandas 3.0.3, DuckDB 1.5.6.
- Git head `2b3a4365a`.

This is the same interpreter and library set as the WS4 qualification, so the results are directly comparable.

| Path | Contents |
|---|---|
| `cases.py` | The matrix: 25 cases across all ten plan groups |
| `measure.py`, `pdf_probe.py` | Measurement. Each PDF is converted in its own process, so its peak memory is its own |
| `results/before/` | Per-case `metrics.json`, `SUMMARY.md` (all tables), `rows_per_page.json`, and the small cases' HTML, PDF and analysis JSON |
| `spikes/` | Spike scripts, fixtures and `results/` |
| `work.nosync/` (git-ignored) | Generated inputs and the large artifacts. Their digests are in `metrics.json` |

## How the matrix was built

There are two kinds of case.

**Fresh (15 cases).** The analysis is run now with the current code. Covers the core classification, unlabeled,
regression and M3 workflows, the mutations, and the wide, flagged-wide and tall cases.
- The analysis JSON is stored together with a digest that ignores only the measured execution fields listed in
  `measure.VOLATILE` (times, peak memory, `generated_at`, `frame_bytes`).
- Six cases were analysed twice. All six produced identical normalised digests, so the plan's analysis-JSON gate is
  workable as specified.

**Stored (10 cases).** M4, M5, M6, M7 and M9 completed results already recorded by their milestones are re-rendered with
today's templates. This is the same no-reanalysis method those milestones used to refresh their reports.
- The stored JSON files are read only; their SHA-256 is recorded.
- Today's rendering of them does not byte-match the HTML saved beside them, because the templates and the provenance line
  have changed since then. The baseline is today's rendering.

**Not run in Stage 0:**
- 10M × 10 classification. It is reused from WS4 (11 pages, 0.71 s PDF); rows do not drive report length, and 1M × 10 was
  re-measured at 12 pages.
- Fresh re-runs of M4–M9. Their model-dependent analyses are covered by their milestone suites and by the plan's
  changed-files gate.

## Verified findings

Full tables are in [`results/before/SUMMARY.md`](results/before/SUMMARY.md).

### 1. The 416-page report reproduces exactly, and it comes from columns, not rows

| Case | Pages (portrait / landscape) | Technical appendix | PDF time | PDF peak memory |
|---|---|---|---|---|
| Tall 1M × 10 | 12 (8/4) | 4 pages | 0.50 s | 101 MiB |
| Wide 5,000 × 200 | 27 (8/19) | 19 pages | 2.3 s | 221 MiB |
| Wide 5,000 × 1,000 | 92 (9/83) | 83 pages | 10.7 s | 734 MiB |
| Wide 5,000 × 5,000, app path | 416 (14/402) | 402 pages (97%) | 48.2 s | 2.9 GiB |
| Wide 5,000 × 5,000, canonical path | 417 (14/403) | 403 pages (97%) | 50.6 s | 2.4 GiB |

- On full appendix pages the per-column tables print about **26 rows per landscape page** (median over 583 and 576 pages).
- That accounts for roughly 0.08 pages per column, as WS4 found.
- The peak memory of the PDF conversion on its own (2.4–2.9 GiB at 5,000 columns) was not separated in WS4. It is a second
  cost of the same tables.

### 2. Per-column layers are a second, independent growth driver

`wide_flagged_1000` is new and deterministic: 5,000 rows × 1,000 columns, of which 400 are mostly missing, 100 constant
and 100 heavy-tailed. Its 128-page canonical report breaks down as:

| Section | Pages |
|---|---|
| Score explanation and thresholds (one feature-usability contributor row per column × rule) | 19 |
| Preprocessing guidance (one "Observed" line per affected column) | 11 |
| Context and declarations | 3 |
| Technical appendix | 84 |
| Rest of the report | 11 |

These are the units that plan rules R2a, R2b, R4 and R6 consolidate. Without them, removing the appendix duplication
alone would still leave about 35 pages of per-column repetition in this case.

### 3. Bank Full today

The app report (the one users download) is **15 pages**: 12 portrait and 3 landscape appendix pages. The canonical path
is 17 pages, with 5 landscape pages because its disclosure includes the full check table. With the WS4 declarations the
counts are 17 and 19.

Your 13-page recollection is not reproduced by today's code. The 3-page appendix does match. The difference comes from
the guidance and context layers added in WS2/WS3, which now take pages 6–10.

| Page | Fill | Content |
|---|---|---|
| 1 | 91% | Decision summary |
| **2** | **34%** | Overflow of the decision summary, then a forced break |
| 3 | 76% | Priority actions |
| 4 | 88% | Overview and target |
| 5 | 73% | Missingness |
| 6 | 96% | Feature evidence and context |
| 7–10 | 85 / 69 / 72 / 54% | Preprocessing guidance |
| 11–12 | 98 / 80% | Scoring, methodology and thresholds |
| 13–14 | 92 / 98% | Appendix tables (landscape) |
| **15** | **49%** | Provenance (landscape) |

### 4. Forced breaks leave sparse pages

Fill is the vertical extent used on the page, measured by the probe.
- **Classification:** page 2 is under 40% filled in **15 of 18** classification report variants, always the
  decision-summary overflow before the forced break.
- **M5:** every report is exactly **10 pages**, with mean fill of 51–56%. Pages 6, 8 and 9 are under 40% in all three cases
  (one topic per page).
- **M4, M6, M7 and M9:** already compact (4–13 pages, no page under 40%).

### 5. The M5 report silently omits findings beyond its action limit (confirmed)

The stored Beijing result is used unchanged; nothing was lowered. It has **15 findings**. The report shows 5 action cards
and makes **no statement** that more exist.

8 of the 10 other findings leave no trace anywhere in the report, not even their evidence references. Among them are the
PM10, TEMP and PRES window-effect and equal-value-run findings, and a "Consecutive-difference dispersion changed" finding.

Record: `spikes/results/m5_disclosure.json`.

### 6. Finding coverage elsewhere

- Classification, regression, M3, M4 and M9: every finding title appears in the PDF.
- M6 and M7 findings carry family codes, not titles. Every family does appear in the PDF, but as humanised internal codes
  such as "exact duplicates bytes" and "quality expectations". So the gap there is readability, not coverage.
- The title-matching instrument cannot verify M6 and M7. Stage 1's finding index will provide stable keys.

## Spike decisions

### (a) Info links and popover — works as designed

Tested in Chromium 156 (the desktop built-in browser), standalone and inside a same-origin iframe (the app viewer shape).
The anchor-first link with one shared, cloned popover behaved as intended:
- Tab reaches the link.
- Enter and Space open the popover, and focus moves to its heading.
- Escape, an outside click and the Close button all close it, and focus returns to the trigger.
- With the script blocked, the link navigates to the guide entry and the empty popover stays hidden.

Two implementation notes for Stage 3:
- **Positioning.** The browser centres a popover by default. A few lines of script will place it next to its trigger.
- **Timing.** `aria-expanded` resets in the asynchronous `toggle` event, so tests must await that event.

**Not exercised:** Safari, Firefox and `file://`. Only Safari is installed, and driving it needs Remote Automation, a
system setting that was not changed. The design does not depend on them, because the enhancement is feature-detected.

### (b) WeasyPrint 69 print features

**Supported:**
- `target-counter(…, page)` page references.
- Custom-counter references (`[G1]`).
- `string-set` running headers.
- The PDF outline from headings, including `bookmark-level: none`.
- Named landscape pages.

**Two traps, both confirmed:**
1. WeasyPrint **prints popover content and the body of a closed `<details>`** unless they are explicitly hidden in print.
   - The shared shell must hide `[popover]` in print.
   - `<details>` must never be relied on to keep content out of the PDF.
2. A page reference to a target that is hidden in print prints a **silent, broken "p. ."**.
   - A test gate will assert that every page-referenced target is printed, as the plan's manifest rule already requires.

`<template>` contents and JSON data islands are not printed, and the meta CSP is ignored without error.

Record: `spikes/results/weasyprint_features.json` and `.pdf`.

### (c) The cost of screen-only content — decided: JSON data island

The fixture has 120 printed rows plus N screen-only rows in a 12-column evidence table. Times are the median of 3 PDF
runs, each in its own process.

| How the screen-only rows are held | 5,000 rows | 15,000 rows |
|---|---|---|
| Control (none) | 0.69 s, 120 MiB | — |
| Ordinary rows hidden one by one in print | +454%, 602 MiB | +1,407%, 1.5 GiB |
| One hidden container | +439%, 592 MiB | +1,282%, 1.5 GiB |
| `<template>` | +144%, 135 MiB | +591%, 274 MiB |
| **JSON data island** | **−8%, 122 MiB** | **−2%, 126 MiB** |

WeasyPrint does almost all of its work for content that CSS hides. Only the data island meets the plan's threshold
(no more than 15% over control); its differences from the control are within run-to-run noise.

**Decision under plan F.5:**
- Rows that are printed stay ordinary HTML.
- V2 detail rows that the `focused` profile does not print are held in a JSON data island and rendered by the report
  script.
- Without the script, those readers see a notice naming the JSON pointer, and can export the `complete` profile, where
  every row is ordinary HTML.

### (d) Large tables in the browser — decided: paged rendering of matches

**Loading is not the constraint.**
- Today's 5,000-column report (1.75 MB, 10,052 rows) loads in **0.15 s**.
- The 15,000-row fixtures load in 0.26–0.35 s.

**Showing thousands of rows at once is.** By either method (toggling `hidden`, or rebuilding from data):
- about 0.3–0.7 s for 5,000–10,000 rows;
- 1.1–1.7 s for 15,000 rows.

**Decision:**
- Detailed tables render the rows matching the current search and filters from the data, **500 at a time**.
- The table states "Showing 500 of N" and offers "Show more".
- Steady-state filtering measured 11–140 ms.
- 500 is a page size for the screen, not an evidence bound: every row is reachable.

Record: `spikes/results/browser_tables.json`.

### (e) Meta CSP with a script hash — works as designed

`default-src 'none'; img-src data:; style-src 'unsafe-inline'; script-src 'sha256-…'`
- The hashed report script ran.
- A simulated injected inline script and an injected inline event handler were both blocked, in the page and inside the
  iframe.
- Data-URI images and inline style attributes still worked.
- WeasyPrint ignores the policy.

**Not exercised:** `file://` in a real browser tab (the desktop app opens local files as a static preview).

Record: `spikes/results/browser.json`.

### (f) Rows per printed page — baseline for the current layouts

These are pages at least 90% filled and holding one table class:
- `appendix-table` and `wide-table` (7.4 pt, landscape): median **26** rows.
- `check-table`: 23.
- The guidance tables (portrait): 15.

Stage 1 re-measures these values for the new shared print styles and freezes them in `report_print_v1`, as the plan
specifies. The current values only calibrate the method.

Record: `results/before/rows_per_page.json`.

## Consequences for the next stages

These follow from approved plan rules; no new founder decision is needed.

1. **F.5 resolves to option 3.** Screen-only detail is held in a JSON data island with paged rendering. This also removes
   the PDF memory cost of large hidden tables.
2. **Print rules in the shared shell (Stage 1):**
   - Hide `[popover]` in print.
   - Never use `<details>` to keep content out of the PDF.
   - Test that every `target-counter` target is printed.
3. **Stage 2** must consolidate the per-column layers (contributors, guidance "Observed" lists, context tables) as well
   as the appendix. Otherwise column-proportional pages remain (see the `wide_flagged_1000` breakdown in finding 2).
4. **Stage 5** fixes the confirmed M5 omission through the finding index.
5. **Stage 6:** M6 and M7 findings need reader-facing names. Coverage checks key on the finding family, not on the title.
6. **Stage 3:** popover positioning script, and tests that await the `toggle` event.

## Stage 1 — shared foundation (2026-11-17)

Stage 1 adds the shared presentation layer without any report adopting it yet, so no report's content changes.

**What was added:**
- `src/datatrust/report_identity.py`: per-workflow presentation identity.
- `report_format.py`: display filters, moved verbatim from `renderer.py` and still importable from there.
- `report_layout.py`: the `report_print_v1` contract.
- Four template partials: the shell, the evidence table, the report script and the base stylesheet.
- `tests/test_report_layout.py` (56 tests).

**Rendered output changes:**
- The provenance "Presentation" line now names the report's own workflow identity, for example
  `report presentation regression-…`, instead of a digest of every template.
- M4–M9 reports were byte-identical to the Stage 0 renders when re-rendered from the same completed evidence.
- Core, regression, unlabeled and M3 reports differ only in that one line. The 18 M2 golden reports
  (`tests/fixtures/m2_baseline.json`) and the 3 unlabeled golden reports (`tests/fixtures/m1_unlabeled_baseline.json`)
  each reproduce their previous pinned hash exactly when the old line is put back. Their `html_sha256` values were
  re-pinned as presentation-only, and no analytical field changed.
- Tests: the DataTrust suite passed 703 (the 647-test baseline on the committed source, plus 56 new); the separately
  run M9 suite passed 42.

**Rows per printed page with the shared print styles.**
`spikes/rows_per_page.py` measured medians with column names of 10–49 characters:
- landscape evidence table: 24 rows;
- portrait evidence table: 33 rows;
- portrait finding register: 33 rows.

These size the R2b guideline in `report_layout.ROWS_PER_PAGE`. Long names that wrap fit fewer rows; the measured minimum
was 19 landscape rows.

**Browser check of the shared shell** (Chromium, through the `report-spikes` server):
- **Enhancement.** The data-island table drew 80 of 80 rows. A hostile column name was shown as text, nothing was
  injected, and anchors stayed unique.
- **Paging.** At 5,000 rows it showed "Showing 500 of 5,000 columns". "Show more" raised that to 1,000. Typing a filter
  gave 9 matches, and clearing it returned to 500.
- **Script blocked** (through a deliberately wrong CSP hash): the printed rows, the summary, the disclosure and the
  "printed rows only" notice remained visible, and the search tools stayed hidden.

## Stage 2 — tabular reports on the shared contract (2026-11-17)

The full table is in [`results/after_stage2/COMPARISON.md`](results/after_stage2/COMPARISON.md).
- 14 cases were measured with the final code, each in the `focused` (default) and `complete` print profiles.
- Timings are the median of 3 runs; each PDF is converted in its own process.
- The normalised analysis JSON is identical to Stage 0 for every case.

| Case | Before (app) | Focused | Complete | PDF time before → focused | Peak PDF memory before → focused |
|---|---|---|---|---|---|
| 5,000 columns | 416 | 10 | 560 | 50.6 s → 0.50 s | 2,362 → 97 MiB |
| 1,000 columns | 91 | 10 | 118 | 10.7 s → 0.46 s | 734 → 94 MiB |
| 1,000 columns, many flagged | 126 | 26 | 143 | 11.0 s → 1.16 s | 837 → 131 MiB |
| Bike hour (regression) | 27 (canonical) | 18 | 29 | 1.49 s → 0.83 s | 134 → 111 MiB |
| Bank Full | 15 | 15 | 16 | 0.72 s → 0.76 s | 111 → 105 MiB |
| German Credit | 14 | 14 | 15 | 0.66 s → 0.57 s | 110 → 101 MiB |

**Acceptance checks:**
- **Sparse pages.** The only remaining pages under 40% fill are the last portrait page before the landscape appendix (an
  intended part boundary). Large decision and action cards now split instead of leaving blank pages; this removed three
  near-empty opening pages in the flagged case.
- **Findings.** Every finding title is present in the focused PDF.
- **HTML size.** Ordinary reports grew by 16–24 KB. Wide reports carry their complete tables as data islands: 1.75 MB
  became 2.37 MB at 5,000 columns.
- **Visual inspection.** Rasterised pages were inspected for Bank Full, unlabeled German Credit, Bike and the 5,000-column
  case (`work.nosync/stage2/visual/`, not kept in git).

## Stage 3 — "Understand this report" (2026-11-17)

13 tabular cases were re-measured in the focused profile against Stage 2
([`results/after_stage3/COMPARISON.md`](results/after_stage3/COMPARISON.md)). The analysis JSON is identical in every
case.

| Case | Pages, Stage 2 → 3 | PDF time, Stage 2 → 3 |
|---|---|---|
| German Credit | 14 → 16 | 0.57 → 0.89 s |
| Bank Full | 15 → 18 | 0.76 → 0.98 s |
| Unlabeled German Credit | 10 → 12 | 0.50 → 0.63 s |
| Bike hour | 18 → 21 | 0.83 → 1.01 s |
| 5,000 columns | 10 → 13 | 0.50 → 0.72 s |
| Many flagged columns | 26 → 29 | 1.16 → 1.57 s |

**Timing tolerance.** Every case is within the plan's tolerance: the larger of +25% and +0.5 s.

**Two-column guide, measured and dropped.** On German Credit, a two-column Reading guide made the PDF take 1.54 s:
- removing the two columns saved about 0.6 s;
- removing the page references saved about 0.25 s;
- removing both gave 0.68 s.

The guide is printed in one column. The page references are kept.

**Sparse pages.** Every page under 40% fill now sits immediately before the Reading guide or the technical appendix,
checked programmatically for all 13 cases. Three kinds of block may now split instead of leaving blank pages: long
narrative callouts, guidance items, and guardrail cards (one recorded guardrail explanation lists 400 columns).

**Browser check** (Chromium):
- Term links open the shared popover next to the link, with the definition, the "In this report" example and what the
  term does and does not establish. Escape returns focus to the link.
- The header link opens the guide drawer and focuses it. Searching "guardrail" leaves 3 of 24 terms; Escape closes the
  drawer and returns focus to the link.

**Re-pinning.** `repin.py` re-pins presentation-only fixtures after re-asserting every analytical result.

## Stage 4 — M3 and M4 (2026-11-17)

Measured against Stage 0 ([`results/after_stage4/COMPARISON.md`](results/after_stage4/COMPARISON.md)). Each case was
measured in both the focused and complete print profiles.

| Case | Pages before | Pages focused / complete | PDF time before → focused |
|---|---|---|---|
| Scene | 11 | 14 / 20 | 0.43 → 0.60 s |
| M4 contaminated | 4 | 6 / 6 | 0.21 → 0.37 s |
| M4 wide | 4 | 6 / 9 | 0.25 → 0.37 s |
| M4 long headers | 5 | 6 / 6 | 0.20 → 0.31 s |

- **Analysis results:** the analysis JSON is identical in every case.
- **Sparse pages:** the only sparse page (Scene, page 10) sits immediately before the Reading guide.
- **Other workflows:** the eight stored M5–M9 cases re-render byte-identical to Stage 0.
- **Visual check:** the rasterised M4 wide report was inspected (`work.nosync/stage4/m4_wide.png`).

The M3 multilabel test fixture (45 features, 12 labels) exercises every historical limit. Each capped table's
disclosure matches the recorded presentation omissions, and its complete table holds every computed row.

## Stage 5 — M5 temporal (2026-11-17)

Measured against Stage 0 ([`results/after_stage5/COMPARISON.md`](results/after_stage5/COMPARISON.md)).

| Case | Pages before | Pages focused / complete | PDF time before → focused | HTML bytes before → after |
|---|---|---|---|---|
| Retail | 10 | 10 / 85 | 0.56 → 0.80 s | 122 KB → 613 KB |
| Beijing | 10 | 11 / 160 | 0.54 → 0.83 s | 132 KB → 1.09 MB |
| Long headers | 10 | 10 / 806 | 0.58 → 0.92 s | 140 KB → 3.88 MB |

- **Analysis results:** the analysis JSON is identical in every case.
- **Findings:** every finding is in the PDF text (Beijing 15 of 15, where Stage 0 printed 5 action cards and no index).
- **Sparse pages:** only the short tail before the Reading guide (retail p6, Beijing p7: the one-line "Completed scope"
  and "Preprocessing guidance" sections) and each document's last page.
- **Keep-with-next rules:** keeping section labels and "Explained terms" lines with their content removed every
  stranded heading. It costs Beijing one page: 10 pages with labels only, 11 with both rules. Stranded headings were
  judged the worse defect.
- **HTML size:** above the +120 KB review trigger. The growth is the complete topic tables held as screen-only data
  islands, which add no WeasyPrint cost. Long headers holds 5,000+ behavioural rows.
- **Other workflows:** the M6, M7 and M9 stored cases re-render byte-identical to the previous commit.
- **Visual check:** contact sheets in `work.nosync/stage5/`.
- **Candidate for Stage 8:** the same keep-with-next rule for "Explained terms" lines in the shared concept styles. The
  other families were not re-measured with it, so it is not applied there yet.

## Stage 6 — M6 text, M7 image, M9 cross-representation (2026-11-18)

Measured against Stage 0 ([`results/after_stage6/COMPARISON.md`](results/after_stage6/COMPARISON.md)).

| Case | Pages before | Pages focused / complete | PDF time before → focused | HTML bytes before → after |
|---|---|---|---|---|
| M6 SciFact | 7 | 10 / 12 | 0.32 → 0.53 s | 17.5 KB → 61 KB |
| M7 classification | 7 | 10 / 13 | 0.27 → 0.43 s | 18.4 KB → 66 KB |
| M7 overlay | 13 | 18 / 28 | 0.53 → 0.61 s | 34.7 KB → 129 KB |
| M9 PDF financial | 5 | 9 / 20 | 0.21 → 0.37 s | 11.4 KB → 90 KB |
| M9 DOCX financial | 5 | 9 / 19 | 0.18 → 0.37 s | 11.4 KB → 90 KB |

- **Analysis results:** the analysis JSON is identical in every case.
- **Findings:** every finding name is in each PDF (SciFact 3/3, overlay 10/10, M9 2/2). The harness now looks for the
  reader-facing name when a finding records only a family code (`measure.reader_name`); Stage 0 looked for the raw
  code (finding 6).
- **Sparse pages:** only SciFact page 8 (the short tail before the Reading guide) and last pages.
- **Page growth:** mostly the Reading guide (2–3 pages) plus the finding index and disclosure lines. The complete
  tables are listed on screen only in the focused profile.
- **Gate 1b (export evidence):** fresh text, image and cross exports were made with this code and with the previous
  commit (`git archive HEAD`). They are deep-equal once `export_identity`, `export_fingerprint`, timings and per-audit
  opaque ids (canonicalised in first-seen order) are removed. The only additions are
  `export_identity.presentation_identity` and `.print_profile`.
- **Earlier workflows:** M4 and M5 renders equal their Stage 4 and 5 renders apart from identity strings. Scene differs
  only in its fresh timestamps.
- **Visual check:** the SciFact, overlay and PDF-financial contact sheets are in `work.nosync/stage6/`.
  - Keeping each "How to read" term with its definition fixed one split (SciFact pages 1–2).
  - The M9 nested-measurement disclosures read "0 of 2 fields shown": the summary shows counts only, and the fields are
    listed in the complete section.

## Stage 7 — interfaces (2026-11-18)

No report layout changed in this stage, so page counts and timings are as recorded for Stages 2–6. The report script
gained only its `#understand` fragment handler, which moved every identity and the script hash.

**Browser-pane pass.** `datatrust ui --history-dir <scratch>` served one seeded saved classification analysis.

| Check | Result |
|---|---|
| Viewer opens | Focus on Back; 7 outside elements inert |
| Tab, then Enter on “Understand this report” | Drawer open; focus on `#understand` inside the report; fragment `#understand` |
| Escape | Drawer closed and fragment cleared; viewer stays open |
| 375 px viewport, tap | Button and drawer work; drawer 375 px wide; no horizontal overflow |
| Back | Viewer closed; focus on “Open report”; no element left inert |
| Console | No errors, no policy violations |

The button first carried a `title`, which the accessibility tree used as its name. It was removed, so the spoken name
now equals the visible label.

## Stage 8 — closure (2026-11-18)

**Full matrix.** All 25 cases were measured in every variant: `results/after_stage8/` (all cases) and
`results/after_stage8_rule/` (the tabular, M3 and M4 cases after the shared keep-with-next rule). Both have a
`COMPARISON.md` against Stage 0.
- **Analysis JSON:** identical everywhere.
- **Timing and memory:** every ordinary PDF is within max(×1.25, +0.5 s). Every wide case is faster than before, with
  lower peak RSS.
- **Findings:** every finding is in every PDF.

**Sparse pages (focused, excluding last pages).** Each one sits immediately before the Reading guide or the
Technical Appendix:

| Cases | Sparse pages |
|---|---|
| German Credit, Bike Hour | p12 |
| german_unlabeled | p6 |
| Scene | p10 |
| mutation leakage / missingness | p14 / p15 |
| tall_1m | p8, p11 |
| wide_200, wide_1000, wide_5000 | p7, p10 |
| wide_flagged | p19 |
| M5 retail / Beijing | p6 / p7 |
| SciFact | p8 |

**Stranded headings.** A text scan of every tabular, M3 and M4 PDF found 7 pages ending on a heading or an
"Explained terms" line. After moving the rule into the shared concept print styles, it finds 0. The plain-wide cases
gain one page.

**Visual inspection.** All 353 focused pages were rasterised (`work.nosync/stage8/*.png`) and inspected as contact
sheets. Residual: in `wide_flagged_1000`, recorded analysis text that names hundreds of columns prints in full (the
decision summary's principal evidence, guidance "Observed" lines, the score-cap explanation). That text is recorded
analysis output, so a presentation-only redesign leaves it.

**Accessibility pass** (browser pane, German Credit). Before the fix, seven table search boxes shared the name "Find".
Every table control now carries a distinct name, and a test asserts it (`tests/test_tabular_reports.py`).

| Check | Result |
|---|---|
| Term buttons | Enter and Space open the explanation with focus on its heading; Escape closes it, returns focus and resets `aria-expanded` |
| Table filter | Status "Showing 4 of 4 matching columns." through `role="status"` |
| Distinct control names | 21 rendered cases scanned: 0 unnamed or duplicate controls |
| VoiceOver | Not run |

**Validators.** See `docs/CURRENT_STATE.md` (Stage 8): eight pass; M7 and M9 fail identically before and after the
redesign. The M4, M5 and M6 validators write into their committed results, which were restored.

## Review fixes (2026-11-18)

Full matrix after the review fixes: `results/after_review_fixes/COMPARISON.md`. Analysis JSON is identical in all 25
cases, and every finding name is in every PDF.

| Case | Focused pages before → now | PDF time | Note |
|---|---|---|---|
| M5 Beijing | 10 → 23 | 0.54 → 1.37 s (five-run median) | Prints evidence for all 15 findings; over the 1.04 s allowance |
| M5 retail | 10 → 11 | 0.56 → 0.85 s | Evidence for both findings |
| M4 wide | 4 → 7 | 0.25 → 0.51 s | 80 finding-referenced columns individually or grouped |
| wide_flagged_1000 | 128 → 26 | 11.0 → 1.30 s | Long recorded lists print 12 names plus a count |
| wide_5000 | 417 → 14 | 50.6 → 0.74 s | Unchanged by the fixes |

- **Stranded headings:** 0 in all 25 focused PDFs. The scan removes the running-header line (extracted last on each
  page) before checking each page's final line.
- **Sparse pages:** every one sits immediately before the Reading guide or the Technical Appendix.
- **Validators:**
  - `validation.verify`, `unlabeled`, `regression`, `dry_runs`, `m3`, `m4`, `m5`, `m6` and `m7` pass. A full run leaves
    `validation/` unchanged.
  - `m9` stops at the model step: its packaged qualification no longer matches the code since `ba3cf1606`, so models
    abstain. This is a founder decision (`docs/CURRENT_STATE.md`).

