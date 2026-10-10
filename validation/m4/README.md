# M4 comparative and scalable validation

M4 uses DuckDB 1.5.6 in the recorded Python 3.11.15 environment. Runtime accepts
DuckDB `>=1.5.6,<1.6`; exact validation dependencies are in `requirements.txt`.
The statistics extra is optional at runtime and was installed for inference checks.

```bash
PYTHONPATH=src .venv/bin/python -m pytest tests/m4 -q
PYTHONPATH=src .venv/bin/python -m validation.m4.verify
PYTHONPATH=src .venv/bin/python -m validation.m4.benchmark --gib 1 --out validation/m4/results/capacity-1gib.json
PYTHONPATH=src .venv/bin/python -m validation.m4.benchmark --gib 5 --out validation/m4/results/capacity-5gib.json
PYTHONPATH=src .venv/bin/python -m validation.m4.stress
PYTHONPATH=src .venv/bin/python -m validation.m4.external_sort
```

The validator reuses pinned Adult, Bank Marketing, German Credit, Concrete,
Energy, Scene and Linnerud sources. Independent calculations cover full structural
counts, finite numerical summaries and exact quantiles. Tests cover lexical keys,
NA-like identifiers, fractional and large numeric identity, chunk invariance,
late invalid tokens, incompatible representations, overlap multiplicities and
three-source unions, annotation truth tables, constraints, shared search bounds,
optional statistics, cancellation, disk limits, source protection and exports.
Controlled splits and mutations are engineering fixtures, not natural drift or
evaluation ground truth. Scalable interpretation is compared with pandas only
where canonical populations are compatible.

`verify` refreshes only its own report files after verifying every previous hash.
Runtime exports retain no-replace publication. `refresh_reports` changes human
projections from completed JSON without reanalysis. `render_qa --renderer
/path/to/pdftoppm` renders every PDF page; visual inspection is a separate gate.
The final six cases contain 25 inspected pages: clean, contaminated, shifted,
partial and wide are four pages each; long headers are five. Every executive
layer is one page. Bounds affect presentation and search scope, never PDF page
removal. The visual manifest binds every PNG to its final PDF hash.

The real local browser exercised split, version and advanced selection,
confirmation, worker progress, declaration retention/invalidation, cancellation,
and HTML/PDF/JSON downloads. A test-only partial fixture verified incomplete
result display and all exports; `serve --partial-fixture` is an isolated validation
runner, with no fault-injection setting in the runtime product. Flask tests also
exercise separate uploads, stale confirmations, ownership and symlink-root escapes.
Browser evidence and downloaded artifacts are under `results/browser/`.

`results/closure.json` records the full pytest suite and classification/archive,
unlabeled, regression, M3 and M4 validators, with hash checks on 194 historical
files. A validator collision was repaired by verifying ownership before refreshing
M4-owned reports; the original failed run remains in the log. Subsequent focused
checks cover final M4 fixes; unchanged legacy checks retain their valid evidence.

Capacity records describe **combined inputs** on the recorded 16 GB laptop,
including ingestion. The four-column workload has a repeated context field;
it does not represent every CSV shape, cardinality or advanced search. Inspect
source dimensions, effective budgets, completed coverage, timings, sampled RSS,
workspace and spill in each JSON before generalizing. Advanced work is measured
separately. Objectives are five minutes for approximately 1 GB and thirty for
approximately 5 GB, with sampled worker RSS below 6 GiB; they are not guarantees.

The 512 MiB stress job groups/joins one million distinct long-key rows per source
and records actual spill. The 32 MiB external-sort case verifies seven exact
quantiles for two million values against analytic expectations. The retained
128 MiB failure demonstrates that a smaller memory setting does not guarantee
successful execution, even for a workload that completes under larger settings.
Process monitoring can overshoot and other processes can consume disk after
preflight. None of this evidence establishes external usefulness or universal
validity of the internal review thresholds.

## Recorded capacity results

| Combined source bytes | Rows per source | Columns | Analysis seconds | Peak worker RSS | Peak workspace | Peak spill |
|---:|---:|---:|---:|---:|---:|---:|
| 1,070,174,464 | 1,783,624 | 4 | 23.55 | 1,091,633,152 B | 1,116,332,032 B | 0 B |
| 5,350,872,664 | 8,918,121 | 4 | 122.24 | 2,801,516,544 B | 6,475,595,776 B | 920,092,672 B |

Both recorded jobs completed their configured core scope and met their measured
runtime/RSS objectives. The 5 GiB job exceeded its 2 GiB engine-memory setting and
recorded spill. These records include ingestion and exclude artifact rendering.
