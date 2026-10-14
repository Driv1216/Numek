# DataTrust

Last updated: 2026-10-12

DataTrust is a local-first Python package and browser UI that generates
stakeholder-readable dataset reliability reports. It is designed for an ML or
data lead who needs inspectable classification, partially annotated data,
multilabel classification, multi-output regression, unsupervised CSV evidence, temporal datasets, and text/annotation/conversation/RAG and image/annotation evidence before deciding how to use a dataset.

DataTrust has no cloud upload, account or external database. Local DuckDB workspaces support scalable execution. A source
is processed locally and produces standalone HTML, PDF, and strict JSON
artifacts through Python, CLI, and browser UI. PDF derives from canonical HTML.

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

## Advanced Tabular Tasks (M3)

M3 adds annotation-aware classification/regression, binary-indicator multilabel
classification, multi-output regression, clustering readiness, anomaly-detection
readiness, and profiling with explicit column roles. These are pre-model dataset
diagnostics. New policies have no composite score or universal readiness verdict.
Existing classification, M1, and M2 behavior remains compatible when the effective
roles and declarations are equivalent, including `target="y"` and `targets=("y",)`.

```python
from datatrust import (DataTrust, DatasetSpec, TaskSpec, AnalysisConfig,
                       AnnotationOptions, AnnotationSpec, RegressionOptions,
                       TargetExpectations, FeatureOptions)

result = DataTrust.from_spec(
    DatasetSpec("energy.csv"),
    TaskSpec("regression", targets=("heating_load", "cooling_load"),
             metadata_columns=("building_id",)),
    AnalysisConfig(
        annotations=AnnotationOptions(AnnotationSpec("unknown")),
        regression=RegressionOptions(expectations_by_target={
            "heating_load": TargetExpectations("continuous", minimum=0),
            "cooling_load": TargetExpectations("continuous", minimum=0),
        }),
        features=FeatureOptions({"orientation": "categorical"}),
    ),
).analyze_result()
result.generate_artifacts("energy-review.pdf", format="pdf", json_path="energy-review.json")

labels = DataTrust.from_spec(
    DatasetSpec("scene.csv"),
    TaskSpec("multilabel_classification", targets=("Beach", "Sunset", "Urban")),
).analyze_result()
```

Every target is excluded from input diagnostics. Explicit `feature_columns=()`
is valid; omitted features select remaining columns after targets and metadata.
Group keys and annotation status fields are metadata. Group coverage distinguishes
complete annotations on one row from targets supplied across different rows.

New annotation-aware workflows default to **unknown expectation**. A populated,
well-formed annotation remains in descriptive evidence even with unresolved status
metadata or a declaration of uncertain validity. `expected` requires an annotation;
`optional` permits absence. A blank value is never automatically intentional.
Use `AnnotationSpec(status_column="annotation_state")` for exact canonical tokens
`expected`, `optional`, `observed`, `intentionally_unlabeled`, `unknown`, and
`uncertain`, or supply an explicit token mapping. Per-target declarations override
the shared default. Missing/unrecognized status tokens are reported separately.
See [the state truth table](METHODOLOGY.md#m3-annotation-semantics-and-coverage).

An explicit expected-only singleton declaration with unchanged roles selects the
legacy policy, including scores and missing-label rejection. Unknown/optional
expectations or effective role/semantic changes select M3 schema 1.2. M1 schema
1.0 and M2 schema 1.1 retain their compatible payloads and report presentation.

```bash
datatrust audit data.csv --task multilabel_classification --target Beach --target Urban \
  --out labels.html --json-out labels.json
datatrust audit energy.csv --task regression --target heating_load --target cooling_load \
  --config declarations.json --out outputs.html
datatrust audit data.csv --task clustering --config declarations.json --out inputs.html
datatrust audit data.csv --task anomaly_detection --out anomaly-context.html
datatrust audit data.csv --task-spec task.json --config declarations.json --out review.html
```

`--task-spec` holds the strict TaskSpec object; `--config` holds analytical options.
Explicit `--task`/`--target` flags conflict with `--task-spec`. A task example is
`{"kind":"regression","targets":["heating_load","cooling_load"],"metadata_columns":["building_id"]}`.
A config example is `{"annotations":{"default":{"expectation":"optional"}},"features":{"semantic_types":{"orientation":"categorical"}}}`.
In this tabular task flow, multiple independent categorical outputs are unsupported;
multilabel targets must be binary indicator columns. List-valued and long-form labels
are deferred for these tabular contracts. M6's dedicated text contracts accept
explicitly declared nested multilabel annotations and associated annotation tables.

The browser preserves its default classification flow and provides separate M3
choices. Declare roles, annotation expectations/status, numerical output intent,
and feature meanings before confirming. Confirmation is tied to the source,
parsing, and effective specification. Editing declarations invalidates artifacts.
Declared categorical fields and identifiers never enter quantitative geometry;
undeclared integer/binary codes remain ambiguous. Other inferred numeric geometry
is explicitly conditional on representation and units.

Reports aggregate repetitive findings. Defaults show five executive actions,
six detailed output panels, twenty feature details/rows per table, and at most
one hundred appendix detail rows. Presentation omissions retain computed JSON
evidence; analytical bounds and execution failures are separate. Artifact QA
metadata records the presentation limits and counts. Scene and controlled wide
PDFs are checked against explicit page/readability budgets.

[Validation and reproducibility](validation/m3/README.md) covers pinned public
sources, independent mathematical checks, browser flows, resource measurements,
and PDF inspection. Runtime dependencies are unchanged.

## Unlabeled CSV Profiling (M1)

Select **Unlabeled — profile all columns** in the browser. Preview types are
provisional; refresh the preview after changing parsing, then review the
confirmation and generate. Names such as `label` do not establish roles.
Results include missingness, exact repetition, variation/cardinality, finite
numeric evidence, parsing review warnings, and check coverage. There is no
unlabeled overall score, risk band, guardrail, or readiness verdict.

```bash
datatrust audit data.csv --task unlabeled --out review.html --json-out review.json
datatrust audit data.csv --task unlabeled --format pdf --out review.pdf \
  --html-out canonical.html --json-out analysis.json --config options.json
```

```python
from datatrust import DataTrust, DatasetSpec, TaskSpec, AnalysisConfig, CsvParseOptions

audit = DataTrust.from_spec(
    DatasetSpec("data.csv", dataset_name="Input review"),
    TaskSpec("dataset_profile"),
    AnalysisConfig(parsing=CsvParseOptions(column_types={"account_code": "string"})),
)
result = audit.analyze_result()
print(result.coverage, result.parsing_warnings)
artifacts = result.generate_artifacts("review.pdf", format="pdf", json_path="review.json")
print(artifacts.html_path, artifacts.pdf_path, artifacts.json_path)
# Other completed-result exports never re-analyze:
result.write_json("another-analysis.json")
```

`DataTrust.generate_artifacts(...)` is a one-analysis convenience.
`generate_report(..., format="pdf", html_path=None)` returns a PDF path and uses
the deterministic `.html` sibling. `from_spec(..., TaskSpec("classification",
"label"))` preserves classification calculations and includes parsing disclosure
in its report appendix. Legacy constructor/analyze/HTML presentation remain
compatible. Classification requires one target; regression accepts one or more; target-free tasks reject targets.
Non-default parsing remains unsupported under the compatible legacy classification policy; annotation-aware classification supports declared parsing.

### Parsing and operational configuration

An `options.json` example (unknown fields are rejected):

```json
{
  "parsing": {
    "encoding": "utf-8",
    "missing_policy": "empty_only",
    "column_types": {"account_code": "string", "amount": "numeric"}
  },
  "fidelity_inspection": {"max_bytes": 1048576, "max_records": 200, "max_cells": 20000},
  "limits": {"max_source_bytes": 104857600, "max_rows": 1000000,
             "max_columns": 1000, "max_frame_bytes": 536870912, "max_seconds": null}
}
```

The comma delimiter and inferred header stay fixed. Defaults retain pandas
inference and NA recognition. `empty_only` preserves nonempty tokens including
whitespace; `custom` recognizes exactly `na_values` (include `""` explicitly to
recognize empty cells). String overrides preserve text subject to missing policy;
numeric overrides reject invalid tokens instead of coercing them. Overrides use
resolved column names. Source bytes are never cleaned or rewritten.

Bounded original-token comparison discloses observed leading-zero conversion,
nonempty tokens becoming null, duplicate/empty headers, and inspection limits.
These are review warnings, separate from findings and scores. Counts describe
only inspected tokens; no warnings observed does not establish losslessness.
Source hashing is separate full-file I/O, and a source change aborts analysis.

Unlabeled, regression, and M3 defaults are 100 MiB source, 1,000,000 rows, 1,000 columns, and 512 MiB
measured frame bytes, with no default elapsed-time limit. An explicit `limits`
object replaces these defaults; omitted fields in that object are unset. Source
bytes/header width are checked before loading, rows use limit-plus-one detection,
and frame memory is measured **after** materialization (excluding temporary
allocations and process overhead). Deadlines are cooperative between stages and
cannot interrupt pandas/native operations. These are configurable operational
safeguards, not hard capacity or execution guarantees. Limits govern analysis
stages, not report rendering or PDF conversion. Legacy classification API
and CLI get no new default analysis limits; the browser retains its upload cap.
Use `datatrust ui --config options.json` for UI operational/inspection defaults.

### Artifact safety and failures

New artifact operations refuse existing PDF/JSON destinations and unrelated HTML
destinations. Existing HTML may be reused only when byte-identical to the
canonical HTML for that completed result. A PDF named `review.pdf` defaults to
`review.html`; choose a fresh stem or explicit HTML destination on a collision.
Outputs must be distinct and cannot alias source files, including hard links and
symlinks. Publication does not replace a file created concurrently. Legacy
classification HTML still replaces an ordinary explicitly selected report file,
with source-file protection; implicit PDF siblings never inherit that permission.

On PDF failure, `PDFRenderError.artifacts` exposes retained HTML/JSON paths and
the error names the HTML location. CLI prints surviving paths; browser keeps
available downloads. Browser cache reuse verifies job-owned artifact identity and
the canonical HTML digest. Configuration changes invalidate known owned outputs.
CLI findings do not signal failure; fatal execution returns nonzero and partial
execution returns status 2 after exporting explicitly incomplete evidence.

The legacy pandas path remains synchronous and in memory. M4 adds opt-in
DuckDB spill and supervised execution; M5 temporal and M6 text audits use that
supervised boundary. M5 accepts CSV/optional scalar Parquet; M6 accepts CSV/JSONL
and declared local text/image references, with optional offline language and
embedding models. Prediction-performance analysis remains outside scope.
Validation is internal engineering evidence, not external methodology or customer validation.

## Regression Intelligence (M2)

Select one numeric outcome explicitly. Regression reviews dataset reliability
before training: finite target coverage, variation and distributions, declared
constraints, qualified arithmetic identities, repetition, and shared feature
quality. It defines no overall score, sub-scores, risk band, or readiness verdict.
Classification scoring and its legacy dictionary remain unchanged.

```bash
datatrust audit concrete.csv --task regression --target strength_mpa \
  --format pdf --out strength-review.pdf --json-out strength-review.json
# Optional strict JSON declarations and search bounds:
datatrust audit bike.csv --task regression --target cnt \
  --config regression-options.json --out bike-review.html
```

```python
from datatrust import (
    DataTrust, DatasetSpec, TaskSpec, AnalysisConfig, RegressionOptions,
    TargetExpectations, RegressionRelationLimits,
)

# With unspecified numerical intent:
result = DataTrust("concrete.csv", target="strength_mpa", task="regression").analyze_result()

# With optional user-supplied context:
config = AnalysisConfig(regression=RegressionOptions(
    expectations=TargetExpectations(kind="count", maximum=10000, units="bikes"),
    feature_availability={"casual": "unavailable_at_prediction",
                          "registered": "unavailable_at_prediction"},
    relation_limits=RegressionRelationLimits(max_pair_features=32),
))
result = DataTrust.from_spec(DatasetSpec("bike.csv"), TaskSpec("regression", "cnt"), config).analyze_result()
result.generate_artifacts("bike-review.pdf", format="pdf", json_path="bike-review.json")
```

The matching JSON configuration is:

```json
{
  "regression": {
    "expectations": {"kind": "count", "maximum": 10000, "units": "bikes"},
    "feature_availability": {"casual": "unavailable_at_prediction", "registered": "unavailable_at_prediction"},
    "relation_limits": {"max_single_comparisons": 20000000, "max_pair_comparisons": 20000000,
                        "max_pair_features": 32, "max_screen_rows": 512}
  }
}
```

Intent defaults to `unspecified`; integer observations alone do not establish
count semantics. Count declarations require nonnegative integers. Optional
inclusive `minimum`/`maximum`, `nonnegative`, `integer_required`, and display-only
`units` describe expectations; they never clean data or convert units.
Availability may be `unknown`, `available_at_prediction`, or
`unavailable_at_prediction`. It is user-declared context, not independently verified.
Regression options are rejected for other tasks.

Boolean, categorical, datetime, and string targets are incompatible. Numeric-looking
strings require the existing explicit `numeric` parsing override, which rejects
invalid tokens. Missing/infinite targets remain separately visible; distributions
use every finite value, including declared violations. No finite targets aborts
analysis. Constants and very small populations receive qualified reports rather
than an invented training-sample requirement.

In the browser, choose Regression, refresh parsing if needed, select a target,
optionally declare expectations/availability, and confirm full target facts.
Ambiguous numeric categories, identifier cues, constants, or fewer than four
finite observations require a server-enforced acknowledgement. The UI never
switches tasks or selects a target automatically.

Relationship actions require 30 finite overlapping rows, five distinct targets,
80% coverage of finite targets, and reliable full verification. Small/sparse
matches stay in technical evidence. Equivalent copy/affine/constant-component
witnesses share a relationship group; distinct mappings retain their evidence.
Ordinary integer/fixed-decimal alignment creates no rounding action. Repeated
inputs with different targets are contextual variation, not contradictory labels.

The search ledger names eligible/selected/excluded columns, candidates,
screening, full verification, support, work budgets, and skip reasons. Planned
pool/work bounds are completed runs with bounded coverage (CLI 0). Unexpected
optional failures or cooperative deadline interruptions produce partial reports
(CLI 2 after export); required failures produce no completed result. A negative
relationship result describes only the searched scope. See [methodology](METHODOLOGY.md)
for numerical tolerances and interpretation rules, and [validation](validation/README.md)
for pinned Concrete and Bike Sharing evidence.

## What DataTrust Checks

- Dataset shape, feature type counts, cell-level and row-level missingness
- Exact duplicate groups; classification label conflicts and regression target variation within repeated inputs
- Binary, multiclass, and single-class target evidence, including the
  majority-class baseline and majority-to-minority ratio
- Constant and near-constant columns
- High-cardinality categorical columns
- Numeric quartiles, zero/negative/non-finite counts, and IQR outliers
- Basic target leakage candidates based on column names
- Classification-only sub-scores for completeness, uniqueness, target balance,
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

## Comparative and scalable local analysis (M4)

M4 adds split audits, reference/current comparisons, and advanced single-dataset
constraints, missingness, dependencies and declared segments. All accepted task
families have bounded DuckDB execution paths. Existing calls retain pandas and
schema 1.0/1.1/1.2 behavior; explicit scalable or advanced calls use schema 1.3.
Comparisons report effects and populations without a composite score or risk band.

```python
import json
from pathlib import Path
from datatrust import DataTrust, ComparisonSpec, ComparisonConfig

if __name__ == "__main__":  # required by spawned-worker scripts
    manifest = Path("comparison.json")
    spec = ComparisonSpec.from_dict(json.loads(manifest.read_text()),
                                    base_directory=manifest.parent)
    result = DataTrust.compare(spec, config=ComparisonConfig())
    result.generate_artifacts("review.pdf", format="pdf", json_path="review.json")
```

```bash
datatrust compare --spec comparison.json --out review.pdf --format pdf --json-out review.json
datatrust ui --data-root /path/to/local/csvs
```

See the runnable [comparison manifest](validation/m4/data/comparison.json).
Standalone execution uses `AnalysisConfig(execution=ExecutionOptions())`; adding
`advanced=AdvancedTabularOptions(...)` selects DuckDB even without explicit
execution settings. Explicit pandas with M4-only diagnostics is rejected. Keep
script entry points guarded because scalable jobs use one spawned worker.

Scalable identifier and key declarations preserve decoded lexical content:
`001` differs from `1`, and `NA` remains an identifier. These columns default to
empty-only missingness. Explicit per-column parsing and missing-policy overrides
are recorded; compatible numeric key semantics require finite, identity-preserving
conversion. Identifier semantics never enter quantitative geometry by inference.
Legacy pandas parsing remains unchanged.

Per-source defaults are 5 GiB, ten million rows and 1,000 columns; combined defaults
are 8 GiB and thirty million rows. Both apply, including repeated roles referencing
the same file. Workspace accounting deduplicates physical owned storage. Job
controls include 2 GiB DuckDB memory, a 6 GiB sampled RSS termination threshold,
two threads, thirty minutes, a 64 GiB workspace ceiling, a 2 GiB disk reserve and
32 MiB serialized results. The workspace ceiling does not require 64 GiB free:
preflight starts at the larger of 4 GiB or six times combined source bytes and
checks additional allocation plus reserves. Estimates are not upper bounds.

Full task-family coverage is distinct from exhaustive searches. Coverage records
selected/excluded scope, full populations, precision/support exclusions, planned
search bounds, omitted detail and unexpected failures. Planned bounds complete
bounded execution; partial reports retain committed evidence. Exports use completed
evidence, protect all source aliases and do not reanalyze.

Optional inference requires `ComparisonConfig(inference=True,
sampling="independent_rows")` and the explicitly installed `statistics` extra.
KS also needs aligned `continuous_columns` plus quantitative declarations (or
explicit continuous regression targets), sufficient finite support and no pooled
ties. Identical sources and known repeated/paired declared units suppress tests.
Significance alone does not create or raise finding priority.

[Validation and measurements](validation/m4/README.md) record pinned correctness,
browser/export checks, complete PDF inspection, 1/5 GiB combined-input jobs and
spill/external-sort evidence. Performance and capacity are measured engineering
objectives, never guaranteed capabilities.

## Project Context

- [Current state](docs/CURRENT_STATE.md): implemented capabilities, verified evidence, limitations, and next step.
- [Architecture](docs/ARCHITECTURE.md): technical structure, interfaces, analysis/report flows, and deployment boundaries.
- [Numek master context](docs/NUMEK_MASTER_CONTEXT.md): company thesis, product direction, operating model, and major decisions.


## M5 temporal reliability audits

M5 supports local CSV/Parquet temporal identities, schedules and lifecycle coverage, panel and window investigation, feature-bound timing/revision histories, target maturity and supplied chronological evaluation plans. Unknown timing and assumptions remain explicit; no temporal score or backtest is generated.

```sh
pip install -e '.[parquet]'
datatrust temporal --spec validation/m5/manifests/alfred.json --out temporal.html --json-out temporal.json
datatrust ui
```

Python starts with `DataTrust.audit_temporal(TemporalAuditSpec(...), config=None)`. The browser has a dedicated Temporal audits workflow. Existing M1–M4 inputs and classification policies are preserved. See [M5 contracts, examples and methodology](docs/M5_TEMPORAL_RELIABILITY.md) and [M5 recorded verification](validation/m5/README.md). Resource budgets and investigation defaults remain provisional.

## M6 text reliability intelligence

Use `DataTrust.audit_text(TextAuditSpec(...), TextAnalysisConfig())`,
`datatrust text --spec ... --out ...`, or the browser’s `/text` guided workflow.
CSV/JSONL, supplied tokens/spans, QA, conversations/tools, retrieval provenance
and explicit local text/image associations share the same contracts. HTML/PDF
and strict JSON contain aggregates and opaque references by default. A separate
protected manifest resolves exact local evidence; excerpt disclosure is explicit.
Working optional Lingua and pinned multilingual E5-small adapters operate offline.

See [M6 contracts, methodology and usage](docs/M6_TEXT_RELIABILITY.md) and
[validation evidence](validation/m6/README.md). No universal text reliability score
or semantic correctness guarantee is introduced.


## M7 image reliability intelligence

M1–M6 completion, including M6's understanding gate, is accepted. M7 adds separate
image contracts and `DataTrust.audit_images()`, `datatrust images`, and guided local
browser presets at `/images`. It covers unlabeled and classification images,
detection, bounded segmentation integrity, exact/perceptual repetition, declared
split/group separation and explicit version comparisons. Reports separate facts,
violations and candidates; no image-quality score or automatic label correction
is introduced.

Install `.[images]`; optional `.[image-embeddings]` uses separately provisioned,
pinned offline CPU artifacts. Portable HTML/PDF/JSON remain image-free and omit
supplied labels/paths by default. The local inspector can reveal verified examples
and overlays without authorizing portable disclosure. See [contracts, methods and
usage](docs/M7_IMAGE_RELIABILITY.md) and [engineering evidence](validation/m7/README.md).

## M9 cross-representation reliability intelligence

M1–M7 are accepted; M8 audio is deferred. Use `DataTrust.audit_cross_representation()`,
`datatrust cross-representation --spec audit.json --out report.pdf --format pdf`,
or `/cross-representation` in the browser. Explicit relationships connect records
to native PDF/DOCX, text and images. Reusable field/table recipes operate across
collections while retaining ambiguous context and competing evidence. Exact
identities, decimals/dates/units, availability/version checks and supplied
separation/ancestry remain distinct from optional semantic candidates.

Install `.[documents]`; optional `.[cross-models]` consumes separately provisioned
pinned local CPU models. English financial NLI and supplied COCO image/text
profiles are narrowly qualified; unsupported populations abstain. No general claim
verification, OCR, audio/video or global score is added. Default HTML/PDF/JSON omit
source content. Exact local evidence and independent confirm/dismiss/unresolved
snapshots are available through Python, CLI and browser. See [contracts and examples](docs/M9_CROSS_REPRESENTATION_RELIABILITY.md)
and [measured verification](validation/m9/README.md).
