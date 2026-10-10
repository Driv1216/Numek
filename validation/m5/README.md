# M5 temporal evidence

The repository Verification skill controls verification frequency and scope. This directory records new M5 evidence separately from M4's execution-verified closure and its later source-only corrections.

Commands use `PYTHONPATH=src` and the repository virtual environment:

```sh
.venv/bin/python validation/m5/download.py
PYTHONPATH=src:. .venv/bin/python validation/m5/prepare.py
PYTHONPATH=src:. .venv/bin/python validation/m5/verify.py
PYTHONPATH=src .venv/bin/python validation/m5/stress.py
PYTHONPATH=src .venv/bin/python validation/m5/benchmark.py --gib 1 --out validation/m5/results/capacity_1gib_csv.json
```

Preparation and downloads are development-only. Runtime audits are local-only. Raw archive, archive-member, prepared-source and declaration hashes pin transformations; changed raw bytes are rejected. Preparation does not clean, impute, aggregate duplicates, or manufacture event schedules.

The corpus retains [Bike Sharing](https://archive.ics.uci.edu/dataset/275/bike+sharing+dataset), [Beijing Multi-Site Air Quality](https://archive.ics.uci.edu/dataset/501/beijing+multi+site+air+quality+data), [ElectricityLoadDiagrams](https://archive.ics.uci.edu/dataset/321/electricityloaddiagrams20112014), [Online Retail](https://archive.ics.uci.edu/dataset/352/online+retail), and an [official archived ALFRED vintage extract](https://alfred.stlouisfed.org/docs/alfred_capturing_data.pdf).

UCI sources carry CC BY 4.0 attribution in the prepared manifest. The ALFRED extract transcribes published BEA GDP figures as facts from page 13 of the official archival presentation; presentation reuse rights are not asserted. It is an illustrative incomplete history, with civil-day availability rather than intraday release certainty. Bike's timezone is an explicit validation assumption. Beijing's supplied NA values remain missing measurements. Electricity's Portuguese local labels, source DST spring zeros, autumn aggregated hours and pre-creation padding remain intact. Retail preserves cancellations and minute-granularity invoice-line events; conversion explicitly rounds Excel serial dates to displayed minutes and does not infer a timezone.

Independent small-data truth tables in `tests/m5` cover exact clocks and DST, arithmetic gaps, absence versus nulls, layout equivalence and counterexamples, feature groups, signed delay, revision ambiguity/state transitions/completeness, maturity, intervals, effects and failure behavior. Public corpus checks independently reconcile source populations and retained counts. Natural data and controlled mutations do not validate universal defect thresholds or model performance.

Capacity records declare rows, widths, normalized cells, settings, full/bounded scope, timings, sampled RSS, spill, workspace and result size. CSV and compressed Parquet cases use the same logical population; file size alone is not a workload definition. Five-minute/30-minute objectives remain hypotheses, and all budgets are provisional. Stress cases include wide expansion, many short histories, skew, revision-heavy keys, enormous gaps, dictionaries, and deliberate decoding/RSS/workspace failures. No completed evidence is published on a required-stage or resource failure.

## Recorded implementation closure

The final coherent M5 pass completed **40 tests**. The consolidated repository run and focused parity repairs are recorded separately in [the evidence ledger](results/evidence_ledger.json); unaffected evidence was reused. No further test runs were started after the founder requested an end to repetitive testing.

All five pinned public cases have completed evidence and eight-page reports in `reports/release`. The controlled sixteen-measurement long-header case also renders eight pages, using disclosed PDF cell abbreviations. The browser confirmation/run/investigation flow and PDF/JSON downloads were exercised; [the result screenshot](reports/browser_result.jpg) records the completed state.

Recorded combined logical 1/5 GiB CSV workloads took about 56/278 seconds, and compressed Parquet workloads about 47/220 seconds. A later 1 GiB Parquet pass took about 41 seconds. These timings belong to the recorded implementation stages and declared narrow workloads; they are not guarantees for arbitrary final scope, width or cardinality. The complete electricity panel retained 51,894,720 cells after bounded materialization resolved earlier engine allocation failures. Detailed settings, phase timings, sampled RSS, provenance, workspace and failures remain in the result records.

The ledger keeps current source hashes, executed commands, retained corpus hashes, rendering evidence and reused measurements separate. M4 execution closure and its later source-only corrections remain unchanged historical evidence.

## GitHub checkpoint (2026-10-11)

The evidence ledger retains the source hashes from its recorded verification.
Ten M5 source/test files in this checkpoint differ from those hashes, so the
recorded runs do not establish verification of every change in this snapshot.
No complete suite was rerun for this push; the request to stop repetitive
testing remains in effect. The existing evidence is preserved as recorded.
