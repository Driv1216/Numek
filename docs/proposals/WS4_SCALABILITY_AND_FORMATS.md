# Proposal: Workstream 4. Scalability qualification, format evaluation and delivery checks

**Status:** approved 2026-10-20 (up to 10M rows and 5,000 columns where safe; gaps reported with prioritised fixes, not silently fixed; public format research; one execution). Executed 2026-10-20; see section 6. No product code was changed.
**Depends on:** Workstreams 1 to 3, all complete.

**Kept as they are:**
- supervision, cancellation, memory, disk and spill budgets
- source protection and result limits
- every numeric result and the UI design

**What this workstream will not do:**
- promise any capacity
- switch backends automatically
- commit to a new file-format adapter before you choose one

## 1. What already exists and what does not

### 1.1 Existing measured evidence (reused, not repeated)

| Evidence | Result (this Mac: arm64, 16 GiB) |
|---|---|
| M4 combined inputs, 1 GiB (`validation/m4/results/capacity-1gib.json`) | Completed in 23.5 s, peak worker memory 1.09 GB |
| M4 combined inputs, 5 GiB (`capacity-5gib.json`) | Completed in 122.2 s, peak worker memory 2.80 GB |
| M4 forced spill, exact external ordering (`stress.py`) | Completed, with the full equality verified |
| M5, M6, M7 and M9 benchmark and stress scripts | Present in `validation/m5` to `m9` |

### 1.2 Never measured

- **The in-memory core path** (classification, regression, unlabeled and M3) on large inputs. Classification has **no default limits** (`ExecutionLimits` is `None`); unlabeled profiling defaults to 100 MiB, 1M rows, 1,000 columns and 512 MiB of frame memory.
- **Everything Workstreams 1 to 3 added:**
  - the whole-file structure check
  - contextual evidence and the dependency search
  - the guidance block
  - the deeper reports and their PDFs
- **App overhead:** upload, inspection and history saving.
- **Export cost apart from analysis cost.** The plan asks for them separately, and today they are only measured together.

### 1.3 A scoping probe (exploratory, one run each, on this Mac)

| Shape | File | Analysis | Of which: structure check | Of which: contextual | HTML | JSON | PDF | Process memory |
|---|---|---|---|---|---|---|---|---|
| Tall: 1M rows × 10 | 48 MB | 4.05 s | 0.60 s | **1.40 s** | 0.05 s · 32 KB | 35 KB | 0.4 s · 10 pages | 601 MB |
| Wide: 5,000 rows × 800 | 25 MB | 3.12 s | 0.15 s | 0.82 s | 0.15 s · 301 KB | **933 KB** | **8.0 s · 74 pages** | 714 MB |
| High cardinality: 300k unique IDs and free text | 8 MB | 0.65 s | 0.13 s | 0.15 s | 0.04 s | 31 KB | not run | 771 MB |

**What the probe already shows**
- Contextual evidence is the largest new cost on tall data, about 35 % of the analysis.
- On wide data the **PDF dominates**: 74 pages and 8 s, against 3.1 s of analysis.
- The JSON nears 1 MB at 800 columns.

These are single runs, which is why a proper qualification is needed.

### 1.4 Formats today

| Workflow | Accepted formats |
|---|---|
| Core and M3 | CSV, any single-character separator. TSV content works, but uploads must be named `.csv`. |
| M4 | CSV |
| M5 | CSV, Parquet |
| M6 | CSV, JSONL |
| M7 | Image folders; CSV, JSONL, COCO and YOLO manifests |
| M9 | CSV, JSONL, Parquet, TXT, PDF, DOCX |

**What this means**
- **Excel** and **Markdown** are supported nowhere.
- **Parquet** exists in M5 and M9, but not in core or M4.
- **The CSV readers differ:**
  - Core uses pandas and, since WS1, a strict whole-file check.
  - M4 and M5 use DuckDB, with strict quoting.
  - M6, M7 and M9 have their own readers.
  - Whether all of them treat the same edge cases the same way has never been checked.

## 2. Scalability qualification

### 2.1 Workload matrix

Each workload runs three times, and the median is reported alongside the spread.

| Workload | Sizes | Paths |
|---|---|---|
| **Tall** | 1M, 5M and 10M rows × 10 columns | Core classification and unlabeled; M4 single-source; M4 splits |
| **Wide** | 5,000 rows × 200, 1,000 and 5,000 columns | Core and M4 (5,000 columns exceeds the unlabeled default, so that case is expected to be *refused*, and the refusal is measured) |
| **High cardinality** | 1M rows: unique IDs; free text; 100k-category columns | Core, M4 dependency search, contextual candidates |
| **Long records** | 1 MB fields; embedded line breaks; records near M4's 8 MiB limit | Structure check, M4 ingest |
| **Malformed** | A bad record at the end of 1 GB, and one at the start | Time until refusal: the structure check should stop early, never run a full analysis |
| **Demanding comparisons** | M4 splits with identity overlap at 5M rows; before/after with keys at 5M rows; versions at 5 GiB (reused) | M4 |
| **Other modalities** | Their existing scripts, re-run once, since WS2 and WS3 changed their report layers | M5, M6, M7, M9 |

### 2.2 What is measured, stage by stage

| Stage | Measured |
|---|---|
| **Ingestion** | Digest, structure check, parse, and the M4 snapshot |
| **Analysis** | Profiling, checks, contextual evidence, dependency search, scoring, guidance |
| **Serialisation** | JSON time and size |
| **Export** | HTML render time and size; PDF time, pages and size |
| **App** | Upload, inspection and history save, for one size per shape |

**For every run**
- Peak memory, for the process and for workers.
- Peak workspace and spill.
- The limit reached first, if any, and the completed and bounded scope.
- The environment: machine, OS, Python, pandas, DuckDB and WeasyPrint versions, free memory and disk.

### 2.3 Output

**The files**
- `validation/ws4/run_scalability.py` holds the definitions, frozen before any run.
- Results go to `validation/ws4/results/*.json`.
- A readable *"Measured on this machine"* page, `docs/SCALABILITY.md`, is linked from the README.

**How results are stated**
- Every statement names the environment and the scope that completed. For example: *"1M × 10 classification completed in N s on this Mac; 10M exhausted memory at the parse stage."*
- Nothing is extrapolated into a guarantee.

**Gaps found along the way**
- If a run shows a safeguard gap, it is reported with evidence and a proposed fix. Likely examples:
  - classification has no default limits
  - very wide data produces very long PDFs
- No default or behaviour is changed without your decision (Q2).

## 3. Format evaluation (deliverable: a ranked proposal for you)

**Candidates**
1. **CSV/TSV consistency.** Accept `.tsv` and `.txt` names in core. Check that all six readers agree on encodings, BOMs, separators, quoting and malformed records.
2. **Parquet** in core and M4.
3. **Excel** (`.xlsx`).
4. **JSON / JSONL tables** in core and M4.
5. **Markdown.** Two distinct things are kept apart:
   - *tables* inside Markdown, which is structured-table ingestion
   - *Markdown documents* for M6 and M9, which is text extraction

**Criteria, scored with evidence rather than opinion**

| Criterion | Evidence gathered |
|---|---|
| Practical demand | Format counts from public dataset catalogues (UCI, OpenML, Kaggle, Hugging Face, data.gov), sampled and dated. Plus your view of target users (Q3). |
| Value to supported tasks | Which workflows each format would serve, and whether it removes a conversion step users must do today |
| Fidelity and ambiguity | Throwaway spikes in the scratchpad (not product code) on 3–5 real public files per format, recording what needs a declaration. For example: Excel sheets, header rows, merged cells, date serials and formula results; JSON nesting; Parquet logical types and nullability. |
| Implementation, resource and maintenance cost | New dependencies (size, licence, security exposure such as zip bombs in `.xlsx`), memory per MB, and lines of code by analogy with M5's Parquet path |
| Reuse | What DuckDB already reads natively (Parquet, JSON) versus what needs a new parser (Excel) |

**The result:** `docs/proposals/FORMATS_RANKED.md`, a ranked list with the evidence for each criterion, the declarations each format would need, and an explicit *not now* list.

**No adapter is built in this workstream.** The plan reserves that decision for you.

## 4. Delivery verification across Workstreams 1 to 3

- **An offline wheel install check.** Build the wheel, install it into a fresh environment with no network, then open the app, run Bank Full with declarations, save it, restart, and produce a saved PDF. Packaging now includes the new templates and the rebuilt app.
- **A cross-reader consistency test.** It covers the CSV edge cases from WS1's generated-file comparison against pandas, run through the core, M4, M5 and M6 readers, with every difference documented.
- **A dense and incomplete report check.** Run the very-wide and partial (deadline) cases through all 14 modules and their PDFs.
- **The full suite and the API/classic parity script, once.**

## 5. Questions for you

1. **Sizes.** Should the qualification go up to 10M rows and 5,000 columns on this Mac, with a 30-minute cap per run (recommended)? Or stop at smaller sizes to save time?
2. **Safeguard gaps.** If measurements expose one, such as unbounded classification memory or 70+-page PDFs, should I report it and propose a fix for your decision (recommended, since it changes no behaviour unasked)? Or fix narrowly within this workstream?
3. **Demand evidence.** May I sample public dataset catalogues online for format counts, and should the ranking weigh any target users you have in mind (recommended: both)?
4. **Delivery.** Should I run everything (measurements, ranking, delivery checks) and then pause for your format decision (recommended)? Or pause after the measurements too?

## 6. Execution record (2026-10-20)

**Measurements:** `docs/SCALABILITY.md`, with raw results in `validation/ws4/results/`.
- Every workload completed or was refused by its declared safeguard. No run reached the 12 GiB or 30-minute caps.
- Highlights:
  - **Core:** 10M-row classification in 43.4 s at 3.68 GiB.
  - **Core, wide:** 5,000 columns in 19.0 s of analysis, but **49.8 s and 416 pages of PDF**.
  - **M4:** 10M rows in 106 s at 2.84 GiB. Before/after on 2 × 5M rows reconciles through identities in 120 s.
  - **Malformed last record:** a 1 GB file is refused in 14.3 s at 133 MB.
- **Post-hoc addition** (labelled in the harness): M4 discovering a malformed last record below its 10M-row limit, because its row limit refused the 1 GB file first.

**Formats:** `docs/proposals/FORMATS_RANKED.md`.
- The ranking: CSV/TSV consistency first, then Parquet, Excel with declarations, flat JSONL, and Markdown not now.
- Measured demand comes from data.europa.eu and the Hugging Face Hub. Enterprise and ML demand claims are labelled as hypotheses.

**Delivery checks**
- **Offline wheel.** Built from a clean source copy in 0.7 s and installed with `--no-index --no-deps` into a fresh venv, with dependencies from the local `.venv` only. The installed `datatrust ui`:
  - ran Bank Full with declarations: 69.0, `duration` flagged, `pdays` assessable on 8,257 rows
  - saved it to history
  - restarted, reopened it and produced a saved PDF
- **Dense-evidence browser pass at 1,000 columns:** 14 tiles, no overflow at 1440 px or 390 px, the viewer, and the PDF.
- **Full suite and parity:** reused from the WS3 closure run (728 passed, 1 skipped, plus M9 42; parity identical). No product, frontend or test file changed afterwards; only the re-run WS3 benchmark results did.

### Safeguard gaps, with evidence and prioritised fixes

None of these is changed here. Each fix needs your decision.

| Priority | Gap | Evidence | Proposed fix |
|---|---|---|---|
| **High: resource safety** | **Classification has no default limits** in the library and the CLI (`core.py:154` uses `ExecutionLimits()`, every limit unset). Regression, unlabeled and M3 get defaults. The app is bounded only by the upload limit, which `datatrust ui --max-upload-mib` can raise without any analysis limit following. Memory handlers catch only Python `MemoryError`, which macOS rarely raises, so exhaustion usually means swapping and then the OS ending the process with no DataTrust message. | 0.37 GiB per million rows of a 10-column shape (10M = 3.68 GiB). Explicit limits work: rows, frame, source and deadline each refuse cleanly with a stage. | Give the **CLI and the app** classification defaults matched to unlabeled (100 MiB, 1M rows, 1,000 columns, 512 MiB frame), overridable in `--config`. Add `--max-rows` and `--max-source-mib` to `audit`. Keep the library API default unchanged for compatibility. Optionally add a pre-parse estimate (bytes × measured factor) that refuses before memory is at risk. |
| **High: report scalability** | **Very wide data makes very long PDFs.** 92–97 % of a wide report is two complete per-column appendix tables that repeat the JSON. | 1,000 columns: 91 pages, 9.6 s. 5,000 columns: **416 pages, 49.8 s**, peak 3.4 GiB. The app's PDF request blocks for that long. | Keep complete column evidence in JSON and HTML. In the **PDF** and the printed view, list every column that has a flag or finding, plus a bounded number of others, with a stated *"N more columns in the JSON"*. This preserves analytical depth; only duplication is trimmed. It changes the legacy report body, hence your decision. |
| **Medium: robustness** | **M4/M5 refuse a valid TSV** that contains a line holding only a tab, with an internal message ("digests disagree"). | `validation/ws4/results/csv_readers.json` | Match core's blank-line rule: a whitespace-only line is blank unless the whitespace is the separator. |
| **Medium: diagnostics** | **M4/M5 structural errors name no record or line**, unlike core's. | The post-hoc malformed run | Add the record and line to M4's structure message. |
| **Low: performance** | **Contextual evidence is about a third of tall classification time** (14.0 of 43.4 s at 10M), mostly the per-feature dependency checks. | Stage timings | Vectorise the checks or run them in DuckDB, with identical results verified against the WS3 benchmark. No change in behaviour. |
| **Low: performance** | **The Python structure check costs about 2× the pandas parse** (6.1 s against 3.1 s at 10M; about 75 MB/s). | Stage timings | A faster strict tokenizer is acceptable only if it is proven equivalent on the WS1 generated corpus; otherwise keep it. |
| **Low: app** | **Context suggestions re-read the whole file** (1.0 s at 1M rows), and the upload step only accepts `.csv` names. | App timings; core upload code | Cache the suggestion pass with the inspection. `.tsv` and `.txt` names are covered by the format ranking's first option. |

### Limits of this qualification
- One machine, one or three runs per size, synthetic shapes. Real data with long strings or many categories will use more memory per row.
- Memory exhaustion was deliberately not provoked, to protect this machine. The failure mode beyond physical memory is reasoned from the code and the platform, not observed.
- M5, M6, M7 and M9 at scale rely on their earlier benchmark evidence.
