# Proposal for your decision: which file formats to support next

**Status:** evaluation complete (Workstream 4). **No adapter has been built.** Implementation waits for your decision.
**Evidence:** `validation/ws4/results/format_spikes.json` and `csv_readers.json`, plus the public catalogue counts below, retrieved 2026-10-20.

## What DataTrust reads today

| Workflow | Accepted formats |
|---|---|
| Core and M3 | CSV, any separator. TSV content works, but uploads must be named `.csv`. |
| M4 | CSV |
| M5 | CSV, Parquet |
| M6 | CSV, JSONL |
| M7 | Image folders; CSV, JSONL, COCO and YOLO manifests |
| M9 | CSV, JSONL, Parquet, TXT, PDF, DOCX |

**Gaps:** Excel and Markdown are read nowhere. Parquet is missing from core and M4.

## Demand evidence

*Measured* means public counts retrieved on 2026-10-20. *Hypothesis* means a reasoned expectation without measured support.

| Source | What it shows | Kind |
|---|---|---|
| European data portal (data.europa.eu): 1,753,350 open-government datasets, counted by distribution format | **CSV 281,680**; JSON 102,988; **Excel 96,598** (XLSX 58,321 + XLS 38,277). Parquet is not among the top 20, so it has fewer than 13,970. | Measured |
| Hugging Face Hub, datasets by format filter | **Parquet 526,323**; JSON 96,956; CSV 50,730; text 12,335 | Measured. Partly reflects the Hub's tooling, which writes Parquet by default. |
| Kaggle documentation | Calls CSV the best-supported tabular format and JSON the usual nested format. Kaggle publishes no counts. | Documented, not counted |
| Practitioner surveys | No current survey with format percentages was found; the only one located is a 2002 KDnuggets poll | No usable evidence |
| Enterprise analysts exchange tabular data mostly as Excel workbooks | Consistent with Excel holding about a third of CSV's share in the government portal, but not measured among DataTrust's users | **Hypothesis** |
| ML teams increasingly store training data as Parquet | Consistent with the Hub counts, though biased by Hub tooling | **Hypothesis** (partly measured) |

## What each format preserves or loses (local spikes, no product code)

| Format | Finding |
|---|---|
| **Parquet** | Types survive intact: timestamps, nullable integers, booleans and lists. Leading zeros survive as text, and missing values are explicit. 4.3× smaller than the same CSV (11 MB against 48 MB). DuckDB reads it natively; pandas reads 1M rows in 0.50 s against 0.31 s for CSV. Nested list and struct columns would need a declared policy. |
| **Excel (.xlsx)** | **High ambiguity.** By default a title row becomes the header (`Quarterly export (draft)`). Workbooks have several sheets. Leading-zero IDs `000`, `001` read back as numbers 0 and 1. Formulas read back **empty** unless Excel recalculated and saved them. Merged cells keep their value in the first cell only. Dates are converted. Reading 100k × 10 takes **2.75 s against 0.06 s** for CSV, about 44× slower. `.xlsx` is a zip container, so it needs the same expansion limits M9 applies to DOCX. |
| **JSON / JSONL** | Nested objects become structs. A field that is a number in one record and text in another becomes a generic JSON type. Records with different keys give sparse columns. Flattening needs a declared policy. DuckDB reads it natively, and M6 and M9 already accept JSONL. |
| **Markdown tables** | No parser is installed locally. The table syntax is ambiguous: escaped pipes, short rows, inline formatting. *Markdown documents* are a different need: text extraction for M6 and M9, not table ingestion. |
| **CSV across readers** | Core and M4/M5 agree on **90 of 92** files, including 80 generated edge cases. The two differences: (1) a line holding only a tab in a TSV file is a row of empty cells in core but makes M4/M5 refuse the file with an internal message; (2) a quote followed by text (`"x"y`) is accepted by core under pandas semantics and refused by M4/M5's declared strict quoting. M6 intentionally requires unique, non-empty headers and treats a whitespace-only line as a malformed record; M7 reads manifests strictly. |

## Ranking

The criteria are demand, value, fidelity and ambiguity, cost, and reuse. Scores run from 1 (worst) to 5 (best).

| Rank | Option | Demand | Value | Fidelity / low ambiguity | Low cost | Reuse | Recommendation |
|---|---|---|---|---|---|---|---|
| **1** | **CSV/TSV consistency** | 5 (CSV leads tabular open data) | 4 | 5 | 5 | 5 | **Do first.** Accept `.tsv` and `.txt` names in core with an explicit separator. Make M4/M5's blank-line rule match core's, so a tab-only TSV line is read rather than refused with an internal message. Give M4/M5 structural errors the record and line numbers core already reports. The intentional `"x"y` difference stays, documented. |
| **2** | **Parquet in core and M4** | 4 (measured for ML; government use is low) | 4 | 5 | 4 | 5 | **Do next.** Reuse M5's and M9's Parquet path and DuckDB's native reader. The optional `pyarrow` dependency already exists. Nested columns are excluded and listed, never flattened silently. Fingerprint the file bytes as CSV is today. |
| **3** | **Excel (.xlsx)** | 4 (measured share in government data; enterprise demand is a hypothesis) | 4 | 1 | 2 | 2 | **Later, and only with declarations.** You would name the sheet, the header row and the cell range; formulas would be read as cached values only, with the file refused when values are missing; merged cells would be refused or declared; text columns would stay text. It needs zip-expansion limits, and `openpyxl` would become a declared dependency (installed here but not declared). Until then, the guidance is *"save the sheet as CSV"*, shown when an `.xlsx` is uploaded. |
| **4** | **JSON / JSONL tables in core and M4** | 3 | 3 | 2 | 4 | 4 | **After Parquet, flat JSONL only.** Nested values excluded and listed; mixed-type fields refused or declared. |
| **5** | **Markdown tables** | 1 (no measured demand) | 1 | 2 | 3 | 1 | **Not now.** Markdown documents belong to a separate text-extraction proposal for M6/M9 if you want that. |

**Not now:** legacy `.xls` (binary), ODS, SAS/SPSS/Stata, Arrow/Feather and Avro. None has measured demand, and each would add a dependency.

## The decision we need from you

Which to build first: **CSV/TSV consistency** (recommended, a small change to behaviour), **Parquet in core and M4**, or **Excel with declarations**. Each would get its own proposal with exact behaviour, limits and tests before any code is written.
