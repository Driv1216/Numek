# DataTrust

DataTrust is a local-first Python package that generates stakeholder-readable
HTML dataset reliability reports. It is designed for an ML or data lead who
needs to explain whether a dataset is reliable enough to use, and why.

V1 is intentionally small: no cloud, no database, no dashboard, and no PDF
export. A CSV goes in, an HTML reliability report comes out.

## Quick Start

```bash
/opt/homebrew/bin/python3.11 -m venv .venv
.venv/bin/python -m pip install --upgrade pip setuptools wheel
.venv/bin/python -m pip install --no-build-isolation -e ".[dev]"
.venv/bin/datatrust audit examples/loan_data.csv --target default --task classification --out examples/report.html
```

Python API:

```python
from datatrust import DataTrust

audit = DataTrust("examples/loan_data.csv", target="default", task="classification")
audit.generate_report("examples/report.html")
```

## What V1 Checks

- Dataset shape, column types, missingness, and duplicate rows
- Classification target balance
- Constant and near-constant columns
- High-cardinality categorical columns
- Numeric outliers using the IQR rule
- Basic target leakage candidates based on column names
- Transparent sub-scores for completeness, uniqueness, target balance,
  feature usability, and leakage risk
- Top three plain-language risks and a recommended next action

## Positioning

DataTrust is not trying to replace broad observability frameworks such as
Evidently or specialist data-centric AI libraries such as Cleanlab. V1 focuses
on the report and synthesis layer: turning common reliability checks into an
audit-style artifact that a technical lead can share with a non-technical
stakeholder.

See [METHODOLOGY.md](METHODOLOGY.md) for scoring details and limitations.
