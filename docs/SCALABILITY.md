# DataTrust: measured on this machine

**These are measurements, not guarantees.** They describe one machine on 2026-10-20: Apple silicon (arm64), 10 CPUs, 16 GiB of memory, macOS 27, Python 3.11.15, pandas 3.0.3, DuckDB 1.5.6, WeasyPrint 69.0. Other machines and other data shapes will differ. Nothing here is extrapolated beyond the sizes actually run, and no backend is chosen automatically.

**How the runs were made**
- **Isolation.** Each workload ran in its own process. The parent watched the memory of the whole process tree, M4 workers included.
- **Caps.** A run was stopped above **12 GiB** or **30 minutes**.
- **Escalation.** Sizes grew only after the previous size completed, and a group stopped at its first unexpected outcome.
- **Reproducing them.** The definitions are in `validation/ws4/run_scalability.py`, and every raw result is in `validation/ws4/results/`.
- **What happened.** No run reached either cap.

**Reading the tables**
- Times are in seconds.
- *Analysis* runs from the start of the analysis call to a completed result, so it excludes generating the test data.
- *Peak* is the highest memory of the process tree.
- Data shapes:
  - "tall": 6 numeric and 3 categorical columns plus a binary target
  - "wide": numeric columns, 9 categorical, and a target, over 5,000 rows

## Core (in memory: classification and unlabeled)

| Workload | Source | Analysis | Structure check | Parse | Contextual | JSON | HTML | PDF | Peak |
|---|---|---|---|---|---|---|---|---|---|
| Classification, 1M × 10 (median of 3) | 45 MB | 3.95 | 0.60 | 0.31 | 1.36 | 37 KB | 35 KB | 0.62 s · 10 pages | 0.60 GiB |
| Classification, 5M × 10 | 226 MB | 21.06 | 3.01 | 1.55 | 6.83 | 38 KB | 35 KB | 0.74 s · 11 pages | 2.77 GiB |
| Classification, 10M × 10 | 453 MB | 43.44 | 6.07 | 3.10 | 14.02 | 38 KB | 35 KB | 0.71 s · 11 pages | 3.68 GiB |
| Classification, 5,000 × 200 | 6 MB | 0.93 | 0.04 | 0.04 | 0.24 | 268 KB | 94 KB | 2.15 s · 26 pages | 0.39 GiB |
| Classification, 5,000 × 1,000 | 30 MB | 3.82 | 0.19 | 0.20 | 1.01 | 1.1 MB | 361 KB | 9.59 s · 91 pages | 1.13 GiB |
| Classification, 5,000 × 5,000 | 152 MB | 18.96 | 0.92 | 1.31 | 4.89 | 5.4 MB | 1.7 MB | **49.79 s · 416 pages** | 3.39 GiB |
| Classification, 1M rows, unique IDs and free text, 100k categories | 41 MB | 3.02 | 0.53 | 0.49 | 0.84 | 31 KB | 36 KB | 0.70 s · 12 pages | 0.76 GiB |
| Classification, 1 MB text fields | 5 MB | 0.11 | 0.02 | 0.04 | 0.02 | 31 KB | 36 KB | 0.64 s | 0.22 GiB |
| Classification, 200k records with embedded line breaks | 10 MB | 0.49 | 0.13 | 0.07 | 0.11 | 31 KB | 36 KB | 0.62 s | 0.28 GiB |
| Unlabeled, 1M × 10 (default limits) | 45 MB | 3.94 | 0.61 | 0.32 | 0.70 | 34 KB | 30 KB | 0.58 s · 9 pages | 0.54 GiB |
| Unlabeled, 5M × 10 (default limits) | 226 MB | **refused** at the source-size limit (100 MiB) before parsing | | | | | | | 0.10 GiB |

**Malformed record near the end**
- A 1 GB file (26.2 million records) whose last record is one field short is **refused in 14.3 s**, peaking at 133 MB.
- The message names the record and the line.
- Nothing was analysed, and the frame was never built, because the whole-file structure check streams the file.

## M4 (out of core: DuckDB)

| Workload | Source | Duration | Peak | Result JSON | Notes |
|---|---|---|---|---|---|
| Advanced single source, 1M × 10 | 45 MB | 11.0 | 0.82 GiB | 321 KB | Dependency search on |
| Advanced single source, 5M × 10 | 226 MB | 53.0 | 2.45 GiB | 345 KB | |
| Advanced single source, 10M × 10 | 453 MB | 106.0 | 2.84 GiB | 348 KB | |
| Splits with identity overlap, 2 × 1M | 106 MB | 24.7 | 1.97 GiB | 694 KB | Entity-disjoint intent |
| Splits with identity overlap, 2 × 5M | 537 MB | 123.2 | 3.07 GiB | 705 KB | |
| Before/after with identity keys, 2 × 1M | 106 MB | 25.4 | 1.18 GiB | 691 KB | Reconciles through identities |
| Before/after with identity keys, 2 × 5M | 537 MB | 119.8 | 2.74 GiB | 701 KB | Reconciles through identities |
| A 7 MiB record | 7 MB | 2.5 | 0.40 GiB | 111 KB | Completed |
| A 9 MiB record | — | refused | 0.23 GiB | — | Record-size limit (8 MiB) |
| 1 GB file, 26.2M records | 1 GB | refused in 12.0 s | 0.25 GiB | — | The 10M-row source limit fired before the malformed last record was reached |
| 380 MiB file, malformed last record *(post hoc)* | 380 MiB | refused in 11.4 s | 0.26 GiB | — | Structure check; the message names no record or line |
| Versions, 1 GiB and 5 GiB combined *(earlier evidence, reused)* | 1.07 / 5.35 GB | 23.5 / 122.2 | 1.09 / 2.80 GB | — | `validation/m4/results/capacity-*.json` |

The post-hoc case was added after the frozen run, because M4's row limit refused the 1 GB file before its last record was read.

## The local app (Flask test client, 1M × 10 classification, 45 MB)

| Step | Seconds |
|---|---|
| Upload and inspection | 1.03 |
| Suggested codes for Context (reads the whole file again) | 1.01 |
| Configure | 0.95 |
| Generate, including saving to history | 4.02 |
| PDF on demand | 0.62 |

**Large inputs in the app**
- A 150 MiB upload is **refused** at the 100 MiB upload limit in 0.07 s.
- In a browser, a 1,000-column file uploads in 0.6 s and generates in 4.2 s. All 14 modules open without horizontal overflow at desktop and phone widths, and its PDF takes 9.3 s.

## What these numbers mean

**Core: tall data**
- Classification on tall data grows roughly linearly here: about **4.3 s and 0.37 GiB per million rows** of this 10-column shape.
- On tall data, **contextual evidence** (the dependency search and candidate codes) is about a third of the analysis.
- The whole-file **structure check** costs about twice the pandas parse. It runs at about 75 MB/s, in pure Python.

**Core: wide data**
- Analysis stays modest, but **export dominates**.
- At 5,000 columns the PDF has 416 pages and takes 50 s, against 19 s of analysis.
- **92–97 % of the report** is the two complete per-column tables in the Technical Appendix, which repeat what the JSON holds.

**M4**
- M4 is slower than the in-memory path on the same 10M rows (106 s against 43 s).
- Its memory stays lower (2.8 GiB against 3.7 GiB) and it is bounded by design.

**What was refused**
- These were refused by their declared safeguards, which is correct behaviour:
  - unlabeled data over 100 MiB
  - an M4 source over 10M rows
  - an M4 record over 8 MiB
  - an upload over 100 MiB
  - the malformed last record
- Each refusal took about one second or less, except the two that must read the file to find the problem (12–14 s per GB).

**Not run**
- **M4 on 5,000 columns.** M4's 1,000-column limit refuses it.
- **M5, M6, M7 and M9 at scale.** Their earlier benchmark evidence in `validation/m5` to `m9` is reused. Workstreams 2 and 3 changed only their report layers, whose cost was measured above as negligible next to analysis.
- **Classification beyond 10M rows.** This was deliberately not pushed toward this machine's memory limit (see the safeguard gaps in `docs/proposals/WS4_SCALABILITY_AND_FORMATS.md`).
