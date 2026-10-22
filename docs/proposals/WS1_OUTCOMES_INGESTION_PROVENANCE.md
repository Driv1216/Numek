# Proposal: Workstream 1. Correct outcomes, ingestion integrity, provenance and saved results

**Status:** approved 2026-10-20 with the recommended answers (strict ambiguity rule; the `parsing.structure_validation` field as a documented exception for new results; saved-PDF generation for older entries whose HTML verifies). Implemented 2026-10-20; see section 7.
**Scope:** Workstream 1 of the DataTrust Final Implementation Plan. Workstreams 2 to 4 and the qualification programme each get their own proposal once this one is approved.
**Unchanged:** the UI design, the scoring formulas and thresholds, historical artifacts, ConfidenceGuard, and the comma-file byte identity established in the separator work.

## 1. What I found in the current code

Each item below was reproduced on 2026-10-20 against the working tree.

| # | Defect | Where | Reproduction |
|---|---|---|---|
| D1 | A tile with no finding shows **"No finding"**, even when its check never ran. | `results/adapter.ts` `fromAnalysis` | Regression on Bike hour: `label_conflicts` and `target_leakage` are `not_applicable`, yet the Conflicts and Leakage tiles read "No finding". |
| D2 | A check that was blocked for part of its scope still reads as clean. | Same | Bike hour: `numeric_outliers` is `blocked / zero_iqr` for `holiday`. The Outliers tile gives no sign that a column was excluded. |
| D3 | Findings reach tiles through a regex on the finding code. Unknown codes land in Reports without any marker. | `tileOf()` | M3's `conditional_scale_review` and the annotation codes fall through to Reports. |
| D4 | M3 structured evidence renders as `[object Object]`. | `Mosaic.tsx:90` | M3's annotation findings carry `evidence: [{target, count, denominator}]`. |
| D5 | "No major issues detected" is counted as a finding. | `risks.py:272`, then the adapter and the saved summary | A clean classification run shows "1 finding" on Reports, and the Recent sheet lists it as a finding. |
| D6 | The Score tile and its chart show the **first** guardrail rather than the governing one. | `adapter.ts:91`, `viz.tsx:14` | With several guardrails, the overall score is the minimum cap (`scoring.py:170`), but the UI explains `guardrails[0]`. |
| D7 | Short rows are padded silently. | `ingestion.read_csv` (pandas) | Adding `1,2` rows to a 3-column file completes. The two padded cells are counted as missing, with only a `token_alignment_ambiguous` warning. |
| D8 | An extra leading field becomes an implicit index without notice. | Same | A header of 3 names over 4-field records completes. Pandas takes column 1 as the index and shifts every value one column left. |
| D9 | When automatic separator detection is ambiguous, it silently falls back to comma. | `detect_delimiter` | `a;b\|c` over `1;2\|3` reads as a single comma column. |
| D10 | The report contradicts its own separator note. | `renderer._with_separator_note` + methodology text | The Bank Full report says "CSV separator: semicolon", then "Comma delimiter, inferred header". |
| D11 | Report timestamps have no timezone. | The legacy HTML `strftime`, plus the generic report | "Generated: 2026-10-20T11:25:12". The JSON is UTC, but the HTML doesn't say so. |
| D12 | The saved sheet's summary comes from an index copy, not from the verified JSON. | `api_web._history_meta` → `ReportSheet` | The sheet and the saved view can disagree, and the sheet repeats D5. |
| D13 | A saved PDF exists only if you downloaded one during the live session. | `history.py`, `SavedDownloads` | After a restart there is no way to get a PDF. |

**What is already correct and stays as it is:**
- M4 and M5 already reject records whose width differs from the header (`scalable.py:225`). Core will reuse that rule and message.
- `render_pdf_report` already converts an existing HTML file, guarded by its digest, without the dataset. Saved PDFs reuse it.
- A full width scan of all 100 CSVs under `validation/` and `tests/` found **no** nonconforming file (3.4 s). Strict validation therefore changes no existing benchmark result.
- No existing test pins the lenient padding behaviour.

## 2. Analytical outcomes (D1–D6, D12)

### 2.1 One outcome state per tile, derived from `checks`, never from finding absence

Each tile is driven by an **explicit table** that names its canonical check ids and finding codes. This replaces the regex in `tileOf`.

| State | When | Tile reads (existing tile anatomy) |
|---|---|---|
| **Finding** | At least one canonical finding is mapped to the tile | Severity, plus the count, as today |
| **No finding (completed scope)** | Every mapped check is `applicable` and `completed`, and no finding exists | "No finding · checked N columns" |
| **Incomplete** | Some mapped check is `blocked`, `failed` or `skipped`, or execution is partial | "Partly checked · holiday: zero IQR". This can appear **together with** Finding. |
| **Not assessed** | A mapped check is applicable but `not_run`, or failed outright | "Not assessed", with the canonical reason |
| **Not applicable** | Every mapped check is `not_applicable` | Today's dimmed "Not for this data" treatment, with the canonical reason |

**Rules that keep these states honest:**
- **Missing values stay missing.** A missing count or value is shown as "Unavailable", never as `0`.
- **Unmapped findings stay visible.** A finding whose code isn't in the table still goes to Reports, but labelled **"Unmapped finding"**.
- **A test fails** if any finding code the engines can emit has no mapping.
- **Three kinds of gap stay distinct** in the chapter text:
  - planned bounds (`coverage.relationship_search`, the execution limits)
  - execution failures (`execution.status`, `failed` checks)
  - presentation omissions (the 12-row panel, bounded previews)
- **Hard failures stay hard.** A required analytical or scoring input that is unavailable still raises and produces no completed result.

### 2.2 Specific fixes

- **D4. M3 structured evidence:** evidence given as a list or an object is shown as a compact table of its keys inside the existing chapter. It is never coerced to a string.
- **D5. "No major issues":**
  - `no_major_issues` stays in the canonical JSON as it is. The JSON contract is untouched.
  - The UI treats it as a narrative statement, not a finding. It isn't counted on any tile or in the saved summary.
  - In the saved summary it becomes `is_finding: false`.
- **D6. The governing cap:**
  - The Score tile, its chart and its chapter use `min(cap)`.
  - Every guardrail whose cap equals that minimum is listed as governing.
  - Guardrails with higher caps are listed as "also triggered".
  - Bank Full still reads **69.0 · Elevated**, now explained by the critical-sub-score cap of 69.0.
- **D12. Saved summaries:**
  - The Recent sheet loads the verified `/history/<id>/analysis` and runs the same adapter as the live view.
  - The index keeps its summary only for search and listing.
  - Live and saved views therefore come from the same code over the same bytes.

### 2.3 The other workflows (M4–M9)

The modality views already read their own canonical `coverage` and `partial` states. As part of this workstream I will:
- audit each one against the same five states
- fix any place where a partial, cancelled or bounded run renders as clean

The proposal makes no promise beyond that audit until I've done it.

## 3. Ingestion integrity (D7–D9)

### 3.1 Structural validation of the whole file

Before pandas builds the frame, core runs **one streaming pass** over the whole file:
- It uses `csv.reader`, with the selected encoding and separator and the same quoting rules.
- BOMs and blank lines are handled as pandas handles them.

It **rejects** with `AnalysisError(code="csv_structure", stage="ingestion")` when:
- any record is narrower or wider than the header. The message reuses M4's wording and adds the first offending line number and the two widths. No row is padded or dropped.
- every record is exactly one field wider than the header (the implicit-index shape). The message suggests a missing header name or the wrong separator.

**What it keeps:**
- quoted fields
- embedded newlines
- BOMs
- legitimate single-column files
- all encodings and separators already supported

**What it doesn't touch:**
- the bounded fidelity inspection (`inspect_source_tokens`) stays separate and unchanged
- the source digest, signature checks and resource limits stay as they are

**Recording:** a completed result records `parsing.structure_validation = "complete_source_width_v1"`.
- This is the only new canonical field from this workstream.
- It is left out of the parsing fingerprint, so seals and fingerprints of valid files don't change.
- **Decision needed (Q2):** this addition is a deliberate, versioned exception to the "comma JSON byte-identical" rule.

**Cost:** one extra sequential read of the file. Bank Full takes about 0.1 s. For large files it stays within the existing deadline supervision.

### 3.2 Ambiguous separators ask instead of guessing (D9)

**When detection is ambiguous:**
- `detect_delimiter` returns `ambiguous` with the candidates it found, instead of comma.
- The app's upload then stops on Configure with the existing separator select set to **"Choose a separator"**. Nothing is analysed until you choose.
- For M4, M5 and M9 sources, the source is not admitted. The response is a 422 that names the candidates.

**What counts as ambiguous:** two or more of comma, semicolon, tab and vertical bar each read the sample as at least two consistent columns.

**What doesn't change:**
- A clean comma file still reads as comma.
- An unambiguous semicolon file is still applied automatically.
- The library, the CLI default and explicit choices still default to comma, with no detection.

### 3.3 Changing the parsing invalidates everything that depends on it

Changing the separator (or any other parsing option) already clears the target, the task specification, the result and the artifacts. I'll add tests that pin these three things:
1. A confirmation sealed before the change is rejected as stale.
2. No artifact from the previous parse can be downloaded.
3. M4 and M5 sources re-admitted with a new separator require a fresh confirmation.

## 4. Provenance and saved results (D10–D13)

### 4.1 One true account of how the file was read (D10)

The methodology text reads the separator from `parsing.options.delimiter` (comma when absent), so it can no longer say "Comma delimiter" for a semicolon file. The note under the title stays as it is.

### 4.2 Timestamps (D11)

Report text shows `2026-10-20 11:25:12 UTC`, derived from the canonical `generated_at`. The JSON keeps its existing ISO value. Saved views label both times:
- **"analysed"** for `generated_at`
- **"saved"** for the history time

### 4.3 A provenance block in new reports

This is a small block in the existing Methodology section of new reports. It contains:

| Group | Fields |
|---|---|
| Source | File name, SHA-256 and size |
| Parsing | Encoding, separator, missing-value policy and structure validation |
| Task | Task kind, target and declared roles |
| Analysis | Methodology id and schema version |
| Execution | Rows and columns analysed, backend, limits, and the completed scope |

**Fields with no value:**
- Every value comes from the canonical JSON, and absent values print as "Not recorded".
- Old saved reports are not rewritten. Their saved view shows "Not recorded in this version" for fields they lack, and nothing is invented.

**Presentation and build identity:**
- The DataTrust package version and the app build hash are recorded separately from methodology.
- They go in the report footer and in each new history manifest (`presentation: {package_version, app_build}`).
- They never go in the analysis JSON, so a UI rebuild never looks like a methodology change.

### 4.4 Saved PDFs, generated from the verified saved HTML (D13)

**The endpoint:** `POST /api/datatrust/v1/history/<id>/pdf`
- It requires history access and CSRF.
- It needs no dataset.

**How it works:**
1. Run `verify(id)`. If the entry is altered or missing, return a 409 and convert nothing.
2. Take an exclusive per-entry lock: an in-process lock plus an `O_EXCL` lock file in the entry directory. A concurrent request receives a 409 "already generating".
3. Call `render_pdf_report(saved_html, staging/report.pdf, expected_html_sha256=manifest.html.sha256)`, the existing converter with the existing local-only fetcher.
4. Before attaching, re-check that the entry still exists and still holds that HTML digest. If it was deleted or changed meanwhile, discard the PDF.
5. Attach through the existing `attach()`:
   - The manifest records the PDF with `html_sha256`, binding it to the exact HTML it came from.
   - If the PDF's recorded HTML digest no longer matches, the PDF is treated as stale and never served.
6. Retention and usage count the PDF's bytes.

**When conversion fails:** the converter's message is returned, the HTML stays available, and nothing partial is left behind.

The existing live PDF paths are unchanged.

## 5. Verification (proportionate, following `agents/skills/verify/skills.md`)

**New tests**
- `tests/test_outcome_states.py` (canonical JSON → states, with a TS-side check run through the app build) covering:
  - D1–D6
  - every engine finding code is mapped
  - simultaneous finding and incomplete
  - unavailable values never shown as zero
- `tests/test_csv_structure.py` covering:
  - the D7/D8 shapes rejected with line and widths
  - accepted quoting, embedded newlines, BOM, single column and each separator
  - the ambiguous-detection flow through the app API, plus a 422 for M4 and M5 sources
- `tests/test_saved_pdf.py` covering:
  - generation after a restart, without the dataset
  - the HTML-digest binding
  - concurrent requests
  - deletion during generation
  - an altered entry
  - converter failure
  - retention accounting
- Provenance tests:
  - the methodology text names the semicolon separator
  - the UTC qualifier
  - the provenance block's fields
  - "Not recorded" for old entries

**Regression checks**
- **Bank Full:** statistics, sub-scores, findings and **69.0 · Elevated** are unchanged. A semicolon copy and a comma copy still produce the same evidence.
- **Comma baseline:** compared against `delim-before/`. The only expected difference is the new `structure_validation` field; anything else fails the check.
- **Full suite:** run once at closure, in the usual two invocations.
- **ConfidenceGuard:** its 81 tests, untouched.
- **Parity script:** unchanged.

**Browser checks**
- One headless pass over the 14 tiles for Bank Full, Bike hour regression (the not-applicable and incomplete states) and one M3 annotation run (structured evidence).
- One saved-PDF generation after a server restart.

No screenshots unless you ask for them.

## 6. Questions for you

1. **Ambiguity rule (3.2).** Treat a file as ambiguous whenever two or more separators fit, comma included (recommended)? Or only when comma itself does not fit?
2. **Structure record (3.1).** Accept the one new canonical field `parsing.structure_validation` on new results (recommended, because the plan asks for versioned behaviour)? Or keep the comma JSON byte-identical and record the validation only in the report?
3. **Old saved entries.** Offer saved-PDF generation for entries saved before this change, which have no presentation identity (recommended)? Or only for entries saved after it?

## 7. Implementation record (2026-10-20)

**What was built**

All of D1–D13, plus the M4–M9 audit from section 2.3.

**Outcomes**
- `frontend/src/app/results/outcome-map.json` is the single explicit map. It covers 54 finding codes, 8 tiles' check sets, and humanised reasons.
- `adapter.ts` derives each tile's state from canonical `checks`, with this precedence:
  1. findings, with incompleteness kept alongside
  2. failed or interrupted checks: incomplete, or not assessed if nothing completed
  3. completed checks: no finding within the completed scope, naming excluded scopes
  4. checks blocked for every scope: not assessed
  5. not applicable
- Excluded scopes (a method precondition such as zero IQR) are not failures. Planned search bounds are shown as bounds and never change the state.
- Further fixes:
  - structured M3 evidence renders as a table
  - "no major issues" is no longer counted as a finding
  - the governing cap is the minimum cap
  - the Recent sheet reads the verified JSON
- **Audit result:** the M4–M9 pages build their tiles from evidence and showed only a partial-run banner. They now list every canonical check that failed, was interrupted or excluded a scope above their tiles, at most six lines plus a count.

**Ingestion**
- `validate_csv_structure` streams the whole source:
  - pandas' blank-line rule (spaces and tabs, except the separator itself), double-quote quoting, BOM
  - no field-size limit (pandas has none); the previous limit is restored afterwards
  - a stop at `max_rows + 1`, and the analysis deadline every 100,000 records
- It runs in `load_dataset` and at classification upload.
- After pandas reads, the two record counts must agree. Lone-CR line endings with quoted breaks are the known disagreement, and such files are refused.
- `detect_delimiter` returns `None` when two or more candidates fit, and `resolve_delimiter` raises with the candidates named. Used by app upload, M4/M5 sources and CLI `auto`.

**Provenance**
- The disclosure states the actual separator.
- Report times say UTC. Legacy direct-API renders keep their established bytes.
- `templates/provenance.html` is included in classification, regression, unlabeled and M3 reports. The app's legacy classification HTML gets it before its last section.
- `presentation_identity()` gives the package version and a templates digest. History manifests add the app build.

**Saved PDFs**
- `History.generate_pdf` and `POST /history/<id>/pdf` (CSRF and launch-token access).
- Work happens in `staging/`, so a deletion stays complete.
- The `O_EXCL` lock is abandoned when its process is gone or it is older than 15 minutes; recovery clears it.
- The HTML digest is re-checked under the index lock, and the manifest binds `html_sha256`.
- `file()` refuses a PDF bound to other HTML.

**Deviations from the text above**
- An ambiguous upload is refused at Upload (422, naming the candidates), with the separator select right there. It is not held on Configure in a "Choose a separator" state, so no half-read job exists.
- The provenance table is in core and M3 reports. M4–M9 reports gain UTC times. Their sources, methodology and schema were already stated in their own reports; their saved views show the presentation identity.

**Tests**
- New:
  - `tests/test_csv_structure.py` (37), including a 3,000-file differential check against pandas and the Bank Full regression
  - `tests/test_outcome_states.py` (17), which runs the real adapter through esbuild and node
  - `tests/test_saved_pdf.py` (11)
- Updated, because they pinned superseded behaviour:
  - `tests/test_delimiters.py`: the ambiguous case
  - `tests/test_m1_analysis.py`: a short record is now refused
  - `tests/test_m3_interfaces.py`: the legacy body is unchanged, plus the UTC qualifier and the provenance table
- Re-frozen fixtures `m2_baseline.json` and `m1_unlabeled_baseline.json`, 21 cases. Before re-freezing, each case was shown to differ only by the new field. Rendering with the pre-change templates reproduces the old frozen HTML hash exactly, so the new hashes reflect only the template additions.

**Verification**
- Full suite: 682 passed, 1 skipped, plus M9 42.
- Comma baseline: the only change is `structure_validation`; M4 and M5 JSON are identical.
- API/classic parity holds.
- Bank Full still reads 69.0 · Elevated, with identical sub-scores and findings.
- Headless browser pass: refusals, tiles, cap, structured evidence, and a saved PDF after restart.
