# DataTrust

DataTrust is a local-first Python package and browser UI that generates
stakeholder-readable HTML dataset reliability reports. It is designed for an
ML or data lead who needs to explain whether a classification dataset is
reliable enough to use, and why.

DataTrust has no cloud upload, account, database, or saved report history. A CSV
is processed locally and produces a standalone HTML report; the browser's print
dialog provides the Save-as-PDF path.

## Quick Start

```bash
/opt/homebrew/bin/python3.10 -m venv .venv
.venv/bin/python -m pip install --upgrade pip setuptools wheel
.venv/bin/python -m pip install --no-build-isolation -e ".[dev]"
.venv/bin/datatrust ui
```

The UI opens at `http://127.0.0.1:8000/`. It guides the user through upload,
target selection, binary/multiclass confirmation, optional report context, and
report generation. The default upload limit is `100 MiB` and can be changed
with `--max-upload-mib`.

The existing CLI remains available:

```bash
.venv/bin/datatrust audit examples/loan_data.csv --target default --task classification --out examples/report.html
```

Python API:

```python
from datatrust import DataTrust

audit = DataTrust("examples/loan_data.csv", target="default", task="classification")
audit.generate_report("examples/report.html")
```

## What V1 Checks

- Dataset shape, feature type counts, cell-level and row-level missingness
- Exact duplicate groups and feature-identical groups with conflicting labels
- Binary, multiclass, and single-class target evidence, including the
  majority-class baseline and majority-to-minority ratio
- Constant and near-constant columns
- High-cardinality categorical columns
- Numeric quartiles, zero/negative/non-finite counts, and IQR outliers
- Basic target leakage candidates based on column names
- Transparent sub-scores for completeness, uniqueness, target balance,
  feature usability, and leakage risk
- Top three executive risks plus a complete prioritized action plan
- Print-safe target-distribution and feature-missingness visuals

## Positioning

DataTrust is not trying to replace broad observability frameworks such as
Evidently or specialist data-centric AI libraries such as Cleanlab. V1 focuses
on the report and synthesis layer: turning common reliability checks into an
audit-style artifact that a technical lead can share with a non-technical
stakeholder.

See [METHODOLOGY.md](METHODOLOGY.md) for scoring details and limitations.
