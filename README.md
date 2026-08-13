# DataTrust

Last updated: 2026-08-13

DataTrust is a local-first Python package and browser UI that generates
stakeholder-readable dataset reliability reports. It is designed for an ML or
data lead who needs to explain whether a classification dataset is reliable
enough to use, and why.

DataTrust has no cloud upload, account, database, or saved report history. A CSV
is processed locally and produces a standalone HTML report. The browser UI
shows a compact decision overview and can download the complete report as a
native PDF generated from that same HTML artifact.

## Quick Start

Using a virtual environment is recommended so Numek's dependencies stay
isolated from other Python projects:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install .
datatrust ui
```

`pip install .` installs DataTrust and creates the
`datatrust` terminal command. It normally needs to be run only once. The
virtual environment is recommended, not required: if DataTrust is already
installed in the Python environment used by the terminal, `datatrust ui` also
works without activating `.venv`.

Native PDF download uses WeasyPrint. Its Python package is installed with
DataTrust, but some operating systems also require native font and rendering
libraries. Follow the official [WeasyPrint installation
guide](https://doc.courtbouillon.org/weasyprint/stable/first_steps.html) for
macOS, Windows, or Linux if the PDF action reports a missing system dependency.
The implementation uses WeasyPrint's documented
[`HTML.write_pdf()` API](https://doc.courtbouillon.org/weasyprint/stable/api_reference.html).

The UI opens at `http://127.0.0.1:8000/`. It guides the user through upload,
CSV validation and preview, explainable target selection,
binary/multiclass/single-class confirmation, optional report context, a compact
reliability overview, standalone HTML viewing, and native PDF download. Target
choices are grouped into outcome-word, other small-set, and advanced choices;
nothing is preselected, and advanced classification targets require an explicit
outcome confirmation. Binary, multiclass, and single-class subtype is detected
after selection rather than asked of the user. The default upload limit is
`100 MiB` and can be changed with `--max-upload-mib`:

```bash
datatrust ui --port 8080 --max-upload-mib 50 --no-open
```

The server binds only to `127.0.0.1`, stores active jobs in a process-owned
temporary directory, and removes that temporary workspace when the process
shuts down. Stop it with `Ctrl+C`. Automatic source-code reloading is disabled,
so restart the command after changing Python or template files.

The existing CLI remains available:

```bash
datatrust audit examples/loan_data.csv --target default --task classification --out examples/report.html
```

Optional `--name` and `--purpose` values add report context without changing
the analysis or scores.

Python API:

```python
from datatrust import DataTrust

audit = DataTrust("examples/loan_data.csv", target="default", task="classification")
audit.generate_report("examples/report.html")
```

Existing calls remain compatible. Optional `dataset_name` and `purpose`
keyword arguments populate report context. `analyze()` continues to return
`profile`, `scores`, and the top-three `risks`, and also returns the full
ordered `findings` list, sanitized `context`, and deterministic `narrative`.
`scores["evidence_score"]` exposes the sub-score average before any guardrail;
`scores["overall"]` remains the guardrailed result.
Fallback report titles are humanized from the original filename; an explicit
`dataset_name` is retained exactly as supplied.

Native PDF generation is intentionally exposed through the local browser UI
only. The CLI and Python API continue to generate canonical HTML reports.

## What DataTrust Checks

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
- Deterministic narrative shared by the compact result and full report
- A layered eight-topic report with a portrait decision layer and landscape
  technical appendix

## Positioning

DataTrust is not trying to replace broad observability frameworks such as
Evidently or specialist data-centric AI libraries such as Cleanlab. DataTrust focuses
on the report and synthesis layer: turning common reliability checks into an
audit-style artifact that a technical lead can share with a non-technical
stakeholder.

See [METHODOLOGY.md](METHODOLOGY.md) for scoring details and limitations.
