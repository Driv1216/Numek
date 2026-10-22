# Numek Architecture

Last updated: 2026-10-21
Status: M1 shared foundation, M2 regression, and M3 tabular/annotation intelligence
implemented; M4 comparative/scalable local analysis added. Compatible pandas
classification/M1/M2/M3 defaults are preserved; M5 temporal, M6 text, M7 image and M9 cross-representation reliability share the supervised DuckDB boundary. M8 audio remains deferred.

ConfidenceGuard CG1 is implemented as the independent `confidenceguard` package
in the existing distribution. Python/CLI/JSON transport call its application
services and analytical engine; completed evidence flows separately into disclosure
projections and canonical reports. A private compatibility adapter reuses existing
worker/Workspace/file/publication helpers without extracting `numek_runtime` or
migrating accepted DataTrust engines. The existing host only registers its
blueprints and JSON CSRF boundary, sharing the worker lock and local lifecycle.
Its functional static client consumes `/api/confidenceguard/v1`; analytical code
has no browser-template/Flask dependency. See [CG1 architecture and contracts](CG1_CONFIDENCEGUARD.md).

CG2 extends this boundary through `method_contracts`, `methods`, `method_sources`,
`calibration`, `conformal`, `uncertainty`, `inference`, `fitted` and `membership`.
`engine.open_store` is shared admission/normalization; `MethodStore` extends CG1
relations; transformed variants reuse `analytics.Evidence` and CG1 reducers.
F/S/C/E query separation seals E labels before fitting. Explicit comparison edges
carry common-input/output populations and metric-specific denominators. Safe tagged
extended values retain valid unbounded conformal thresholds while keeping optimizer
parameters finite. Parent-owned application staging preserves atomic publication.
Method digests, application digests and immutable assessments are separate identities.
Protected membership sidecars and imported-method compatibility checks extend provenance.

CG1 1.0 requests/results retain their path; CG2 1.1 requests/results opt into the new
semantics. The existing v1 transport advertises both. Method fitting, application,
independent evaluation, disclosure and exports are thin interfaces over one engine.
CG2 adds no framework, predictor executor, persistent monitoring database or shared
runtime extraction. See [CG2 architecture/methodology](CG2_CONFIDENCEGUARD.md).

ConfidenceGuard now includes opt-in longitudinal reliability within the same product.
CG3 adds protected projected-fact capture before eligibility filtering, frozen
method outputs, an authoritative SQLite catalog, immutable JSONL evidence,
supervised DuckDB reconstruction, revisions/backfill/as-of maturity and immutable
restatements. Reference/current drift, performance/calibration/uncertainty evolution,
declared-cohort mix, qualified resampling and exploratory temporal investigation
share Python/CLI/API/browser and canonical reporting. Standalone CG1/CG2 and
DataTrust history semantics remain intact. See [CG3 contracts and methodology](CG3_CONFIDENCEGUARD.md).
CG3 is complete, including corrections R1–R3, as confirmed by the user on 2026-10-21.

## System Overview And Boundaries

DataTrust is a Python package with one dataset-analysis core and three user
interfaces: public Python API, Click CLI, and a local server-rendered Flask UI.
It analyzes classification, partial annotations, multilabel indicators, multi-output
regression, and target-free CSV readiness with preserved pandas defaults. Opt-in
M4 analysis and split/version comparisons, M5 temporal audits and M6 text audits
use embedded DuckDB execution and a supervised local worker. M6 optionally runs
pinned offline language/embedding models. There is no runtime LLM, persistent
service database or cloud inference dependency.

The flow below describes the pandas compatibility path. M4, M5 and M6 execution
and presentation boundaries are described in their dedicated sections below.

```text
Python API / CLI audit / Flask UI
                |
   DatasetSpec + TaskSpec + AnalysisConfig
                |
   run_analysis: source identity, bounded fidelity, CSV ingestion
                |
   shared DataFrame profiling + explicit interpretation policy
                |
   classification scores / regression and unlabeled scoring not_defined
                |
   AnalysisResult: evidence, outcomes, findings, narrative, coverage
                |
   legacy classification projection / typed JSON / canonical HTML
                |
   collision-safe artifact coordinator + restricted WeasyPrint PDF
```

The browser also uses shared CSV inspection and target-suitability functions
before full analysis. UI preview/configuration does not create a second scoring
pipeline. See [README.md](../README.md) for commands and
[METHODOLOGY.md](../METHODOLOGY.md) for detailed diagnostic/scoring rules.

## Modules And Responsibilities

All runtime modules below live in `src/datatrust/`.

| Module | Responsibility |
|---|---|
| `__init__.py`, `core.py` | Export API/contracts; explicit pandas/M4 dispatch, task policies, legacy projection, completed evidence and artifact conveniences. |
| `contracts.py` | Standard-library specifications, configuration/limits, typed outcomes/evidence/results and discoverable artifacts; strict JSON projection. |
| `ingestion.py` | Shared default-compatible CSV read, bounded original tokens, parsing manifest/source identity, resource preflight, ephemeral DatasetHandle, provisional preview. |
| `profiler.py` | Validate/read CSV; inspect preview and selected target; compute dataset, column, row, class, duplicate, numeric, and name-based leakage evidence. |
| `target_guidance.py` | Assess possible targets using structural values and whole-token name signals; return explainable groups without selecting a target or changing diagnostics. |
| `regression.py` | Frame-based finite target distributions/constraints, precision safeguards, bounded copy/affine/sum identities, canonical groups, and repeated-input variation. No loading, rendering, scoring, or model fitting. |
| `annotations.py` | Resolve roles/effective policy/fingerprints, orthogonal cell states, per-target/row/group coverage, conditional feature semantics, and bounded annotation population contrasts. |
| `numerical.py` | Shared unrounded precision-safe M2 primitives; compatibility wrappers retain M2 results. |
| `multilabel.py` | Indicator decoding, vector/pair evidence, three-valued declared constraints, bounded patterns, observed repeated-input disagreements. |
| `unsupervised.py` | Conditional quantitative eligibility, structural/scale/sparsity evidence and marginal extreme-candidate context without fitted models. |
| `m3.py` | Task dispatch and consolidated findings inside core orchestration; no ingestion/export/scoring engine. |
| `presentation.py`, `templates/m3_report.html` | Bounded completed-evidence projection, presentation QA counts, compact eight-topic reports; computed JSON remains intact. |
| `scoring.py` | Classification only: compute five sub-scores, their evidence-score mean, explained score caps, final score, risk band, and recommended action. |
| `risks.py` | Build complete ordered findings with evidence, modeling impact, recommendation, severity, and score effect; support top-three risk summaries. |
| `narrative.py`, `wording.py` | Produce deterministic interpretation and singular/plural language from existing evidence. |
| `renderer.py`, `templates/report.html` | Render canonical standalone HTML with escaped context, safe name wrapping, print-safe charts, report layers, and generation timestamp. |
| `cli.py` | Expose `audit`, manifest-relative `compare`, and `ui` commands; wrap analysis failures in CLI errors. |
| `web.py`, `templates/ui.html` | Guided browser workflow, session/form protection, temporary job ownership, compact result, report viewing/downloads, and PDF caching. |
| `pdf.py` | Restricted local HTML conversion, source identity checks, unique staging/no-replace publication, actionable failure with surviving artifacts. |

`validation/` is separate engineering/evidence tooling, not a runtime package
dependency. `tests/` exercises implemented contracts and failures. Packaging is
specified in `pyproject.toml`; `setup.py` retains compatibility metadata, and
both currently identify package version 0.1.0 with Python >=3.10. Templates are
included as package data; the console entry point is `datatrust.cli:main`.

## Analysis Flow And Public Contract

`DataTrust(dataset_path, target, task="classification", *, dataset_name=None,
purpose=None, source_filename=None)` stores inputs and sanitizes optional
context. Classification target selection is explicit in the Python API and CLI;
target-free profiling uses `DataTrust.from_spec(..., TaskSpec("dataset_profile"))`.

Legacy classification `analyze()` returns an unchanged in-process dictionary:

| Key | Contents |
|---|---|
| `profile` | Dataset dimensions, per-column metrics, missingness, duplicates/conflicting labels, target distribution/subtype/balance, and strong/review-only leakage evidence. |
| `scores` | `sub_scores`, `evidence_score`, guardrailed `overall`, `risk_level`, `recommended_action`, and `guardrails`. |
| `risks` | First three findings in the complete ordered list, preserving the executive-summary contract. |
| `findings` | Complete prioritized list: code, title, finding, evidence, modeling impact, recommendation, severity, and score effect. |
| `context` | Dataset/report display name, purpose, and original source filename. |
| `narrative` | Overall and score-path explanations, principal evidence, missingness/target/duplicate/leakage interpretations, and finding count. |

`generate_report(output_path)` analyzes and writes canonical HTML, creating the
output directory when needed, and returns the output path. This result dictionary
remains the legacy projection. Typed `analyze_result()` supports strict JSON
through `to_dict()`/`write_json()` and completed-result exports. There is no
remote HTTP analysis API.

### Shared M1 Contracts and Policies

`DatasetSpec` accepts a local row-based CSV and optional context. `TaskSpec`
allows classification/regression with one target or dataset_profile without one. `AnalysisConfig`
contains CSV parsing, bounded fidelity inspection, operational limits, and optional
strict RegressionOptions (expectations, feature availability, relation bounds);
unknown fields/unsupported values are rejected. Standard-library dataclasses
and enums add no runtime dependencies or speculative backend registry.

`run_analysis()` validates, preflights, hashes/inspects original tokens, loads
one DataFrame, profiles it, executes applicable checks, verifies the source
snapshot, and returns `AnalysisResult`. The short-lived `DatasetHandle` is never
serialized or stored between browser requests. Profiling compatibility wrappers
call shared frame-based primitives. Duplicate identity is independent of label
conflict analysis; classification keeps its legacy formulas and order.

Policy IDs are `classification_legacy_2026_08_13` and
`unlabeled_csv_profile_v1`; regression uses `tabular_regression_v1` and schema `1.1`. Classification default pandas calls, six-key result,
scores, findings, narrative, target guidance, and legacy HTML are unchanged.
General profiling covers all columns; finite-only IQR is explicit and scoring is
`not_defined` with null values. Parsing warnings are separate from findings and
scoring. Specification-based classification reports add appendix disclosure
while preserving the eight topics; legacy HTML has no added disclosure.

Results carry schema/method versions, source hash, effective parsing/pandas
version/inferred types/header mapping, bounded fidelity coverage/warnings,
outcomes, referenced measurements, populations/denominators, bounded row
references, and configured/observed execution facts. Applicability and execution
are separate enums. Required failures and allocation errors abort; isolated
optional failures produce explicitly partial reports. Coverage is a list of
completed/unavailable groups and exclusions, not a universal percentage.

The preserved M1 pandas path uses `pandas_in_memory`. Its default unlabeled/regression
safeguards are 100 MiB source, 1 million rows, 1,000 columns, 512 MiB measured frame,
no elapsed limit.
Source/header preflight, limit-plus-one row reading, post-load deep frame
accounting, and cooperative stage deadlines do not guarantee peak memory or
interrupt native operations. Explicit limit objects replace defaults; classification
has no new default analysis limits. M4 reuses the DataFrame-independent result/evidence
boundary for opt-in worker and disk-backed execution, with its own parsing/resource policy.

CSV loading uses pandas' comma-delimited/header defaults and translates common
filesystem, parser, and encoding failures into actionable errors. Profiling
rejects unsupported tasks, zero-row datasets, missing targets, and targets with
no usable labels. Missing target labels are excluded from class statistics and
surfaced separately; dataset-wide completeness still counts missing cells across
all columns, including the target. Row-level feature missingness is separate.

Exact duplicates use complete rows; feature-identical conflicting-label groups
use only labeled rows grouped by feature values. Conflicts are context-review
evidence, not automatic proof of incorrect labels. Leakage classification uses
name tokens/phrases and prior/historical qualifiers; it cannot establish actual
feature availability without domain knowledge.

Scoring averages the five already-computed sub-scores, rounded to two decimal
places, into `evidence_score`, then applies the lowest applicable guardrail cap
for `overall`. Risk bands and recommended actions use that final score.
Strong leakage, a single target class, or no features cap at 49; missing labels,
severe missingness, severe duplicates, or a critical sub-score cap at 69.
Detailed formulas and thresholds remain in methodology and implementation.

## Guided Browser And Job Lifecycle

`datatrust ui` starts Flask on `127.0.0.1` (default port 8000), with debug,
reloading, and threaded serving disabled. The normal command creates a
process-owned `TemporaryDirectory` and cleans all jobs on exit. `create_app()`
accepts a caller-supplied workspace; the CLI runner owns its lifecycle.

The implemented routes form this flow:

1. `GET /` and `POST /upload`: accept a `.csv` filename, normalize its basename,
   replace the session's prior job, write `dataset.csv` under a UUID job
   directory, and show a ten-row preview. Classification retains full inspection
   for target guidance; unlabeled previews load at most ten rows with provisional
   types and bounded token comparison.
2. `GET|POST /configure`: show grouped target options and collect an explicit
   target plus optional name/purpose. Shared target inspection determines
   usable labels and binary/multiclass/single-class subtype. Unlabeled configuration
   accepts parsing overrides and refreshes the provisional preview before confirmation.
3. `GET /confirm` and `POST /generate`: present target facts and enforce the
   advanced-choice acknowledgement before invoking the shared analysis core
   and writing the job's canonical `report.html` plus strict `analysis.json`.
   Unlabeled confirmation instead shows effective parsing, operational safeguards,
   planned checks, and inspection bounds, and requires no target.
4. `GET /result`, `/report`, and `/download`: display a compact deterministic
   decision overview, view the full HTML artifact, or download it.
5. `GET /download/pdf`: convert the existing HTML to `report.pdf` on first
   request; verify artifact identity and HTML digest before cache reuse. JSON is
   available at `/download/json`. Configuration changes invalidate owned artifacts.
6. `POST /new`: remove the current job and return to upload.

`JobStore` holds job dictionaries in memory with paths, inspection,
configuration, completed result (without a DataFrame), artifact identities, and
compact summary. The signed browser session
stores a job ID and form token; datasets remain in local temporary files.
Normal replacement/new-analysis/exit paths clean files. Stale jobs redirect to
upload; absent reports return 404; oversized requests return 413. Generation
errors preserve a usable configuration path, and PDF failure returns to results
with the HTML artifact available.

### Target Guidance Boundary

Options are grouped as outcome-word, other small-class, advanced, or disabled,
preserving original column order within groups. No target is preselected.
The small-class ceiling is `min(20, max(2, labeled_rows // 2))`. Identifier tokens
or at least 20 labeled rows with >=95% distinct values trigger advanced review;
above-ceiling numeric or categorical choices also require acknowledgement.
No usable labels disable a choice. Whole-token outcome signals can elevate
small-class options; generic words and prior/derived qualifiers do not establish
business intent. These are selection heuristics, not dataset findings or penalties.

### M2 Regression Workflow and Evidence

Regression requires an explicit numeric non-boolean target. Shared ingestion
validates declarations/names and finite target coverage; absence of finite targets
is fatal. `profile_tabular_frame` shares structural profiling with an optional
target role, keeping the unlabeled wrapper and classification calculations intact.
Feature diagnostics exclude the target and retain M1 finite-only methods.
`profile["regression"]` contains target statistics, declared expectations/constraints,
relationship witnesses/groups, repetition, and an exact search ledger.

The orchestrator registers precise evidence paths, populations, bounded row
references, method applicability, and execution. Regression `analyze()` returns
the typed dictionary projection; `analyze_result()` returns AnalysisResult.
No classification scorer is called. Scoring is not_defined with null values.
Findings distinguish mathematical facts, declaration violations, and contextual
reviews. Weak arithmetic support never enters relationship priority cards.

Copy checks precede affine identities; pairs are limited by pool/work controls,
with deterministic screen then full-overlap verification. Conservative action
support and variation-relative tolerances are specified in methodology. Canonical
relationship groups retain alternate witnesses/scopes while actions consolidate
by availability. Source-ordered processing bounds transient work; there are no
new registries, frameworks, workers, or persistent stores.

Planned search bounds appear as completed/bounded, separate from partial execution
on unexpected failure/deadline. A relationship-stage interruption retains prior
verified witnesses and marks unfinished candidates. Required failures/memory/source
changes abort; completed-result exports reuse the artifact coordinator unchanged.
Classification and unlabeled status behavior remains unchanged.

Regression UI previews reuse shared safeguarded ingestion and remain provisional.
Selection has no default. Full target confirmation stores only serializable facts,
source hash, and parsing fingerprint. Configuration changes invalidate confirmation
and owned artifacts; generation verifies both source identity and parsing.
Ambiguous category-like numeric outcomes, IDs, constants, and very small populations
require server-enforced acknowledgement. Expectations and feature availability
remain optional user context. Dates stay ordinary columns, without time-series claims.

The canonical regression_report.html renders eight topics, stored coverage/histogram/
quantile aggregates, declarations, distinct relationships and qualified technical
observations, repetition/features, execution, scoring unavailability, and an appendix.
PDF derives from this HTML with portrait decision pages/landscape appendix. JSON
retains unrounded evidence and resolvable measurement references.

## Report Generation And Security Boundaries

The compact UI summary and full report consume the same deterministic narrative.
The HTML renderer uses Jinja autoescaping and safe soft wrapping, plus CSS
bar visuals for target distribution and feature missingness. There is one
interpretation source and no generative narrative service.

The current report's eight topics are Decision Summary, Priority Actions,
Dataset Overview, Target and Label Evidence, Missingness Evidence, Duplicate
and Feature Evidence, Scoring/Methodology/Limitations, and Technical Appendix.
Print rules use A4 portrait for main pages and landscape for the appendix.
Unlabeled reports have eight topics from Review Summary to Technical Appendix,
with parsing warnings and coverage explicitly separate from findings. Generated
timestamps mean HTML bytes are not identical across fresh runs; repeated export
of the same completed result uses its stable timestamp.

PDF is a derivative of the completed HTML, not a separate report-content
implementation. The custom fetcher permits embedded data and file resources
within the report directory and rejects remote resources. WeasyPrint output is
published from a uniquely created destination-directory temporary file through
no-replace hard-link publication. Preflight alone is not relied upon for safety.
New PDF/JSON outputs refuse collisions; canonical HTML may be reused only if
byte-identical. Paths must be distinct and cannot alias source files via resolved
paths, symlinks, or hard links. Direct legacy classification HTML retains explicit
ordinary-file overwrite behavior with source protection.

`ReportArtifacts` records actual paths/reused HTML; `PDFRenderError.artifacts`
exposes surviving HTML/JSON after failure. API, CLI, and UI share the coordinator.
PDF defaults to a deterministic `.html` sibling; no silent renaming or ownership
inference from filenames/markers occurs. Browser regeneration verifies all known
artifact identities before deletion; unrecognized files remain untouched. PDF
cache identity is tied to canonical HTML digest. Remote resources remain rejected.

The UI creates a random secret key and uses session-bound form tokens with
constant-time comparison for POST requests. Flask enforces a configurable
request-size cap (default 100 MiB); download names use `secure_filename`.
Optional report context is stripped and length-limited; explicit names remain
user-supplied, while fallback titles are humanized from the source filename.
These local controls do not provide enterprise authentication or multi-user
isolation. Upload size is not a pandas memory bound, and abrupt process failure
is not a guaranteed cleanup path.

## Dependencies And Validation Architecture

Runtime dependencies are Click, Flask, Jinja2, numpy, pandas, and WeasyPrint (69.x).
NumPy was already present through pandas and is now an explicit numerical dependency.
M4 adds DuckDB (`>=1.5.6,<1.6`) and psutil; optional inference uses the separately
selected `statistics` extra (SciPy). No dependency is installed automatically.
Development dependencies include pytest and pypdf. Native font/rendering
libraries may be required for PDF on some operating systems.

The [validation workspace](../validation/README.md) prepares pinned UCI datasets,
creates deterministic mutations, runs reports, records timings/assertions and
leakage classifications, and verifies stored checksums/evidence. Evidently
0.7.21 is isolated in its own validation environment and is not imported into
the runtime package. Comparison timings describe different artifacts and do
not establish performance superiority.

Historical dry-run tooling manages candidate records and allowlisted reviewer
packets. It remains evidence tooling rather than a current product release gate.
[Historical reviews](history/reviews/README.md) and immutable candidate/packet
records preserve the old six-section implementation separately from current reports.

`validation/unlabeled/` is a separate internal namespace with known synthetic
evidence and temporary label-free views of pinned tables. Frozen M1 regression
fixtures preserve eleven classification results/legacy HTML hashes and 39 stored
artifact checksums. `validation/regression/` pins Concrete and Bike Sharing archives/members/prepared
files, controlled cases, declarations, reproducible hashes, and offline assertions.
XLS conversion uses validation-only xlrd. Existing validation namespaces and
historical reports are retained. Internal tests and visual PDF/browser checks do not establish
external methodology validity or product usefulness.

## Significant Technical Decisions And Evolution

- **2026-06-02:** HTML-first over PDF-first enabled rapid report iteration.
  Transparent sub-scores plus guardrails were chosen over opaque synthesis.
  Local execution avoided initial cloud data handling. These are implemented
  choices that can evolve deliberately; current limits are not future prohibitions.
- **2026-06-14:** corpus semantics exposed `previous_campaign_outcome` as prior
  information. The narrow correction made prior/historical outcome-like names
  review-only while retaining strong post/final outcome candidates.
- **2026-08-05:** add a guided loopback UI while retaining CLI/API contracts.
  Richer evidence and complete findings were added without silently changing
  validated scores, guardrails, or top-three risks. Evidence-only findings can
  enter scoring later when supporting validation and an explicit decision justify it.
- **2026-08-11:** replace the report iframe with a compact score/risk/action
  surface and add native UI PDF for one-click sharing. Keep the full report as
  the evidence artifact and derive PDF from HTML to avoid parallel content sources.
- **2026-08-12:** explainable target grouping avoids assuming business intent;
  server acknowledgement protects advanced selections. Additive evidence score,
  shared deterministic narrative, and layered reporting improve explanation
  while retaining existing analytical decisions and CLI/API target requirements.
- **2026-08-13:** distinct-value wording, advanced-outcome confirmation,
  humanized titles, and clean-report presentation improve usability. The <1%
  missingness narrative rule precedes the 70% concentration rule and changes
  presentation only. `no_major_issues` stays in compatibility outputs even when
  the report displays an empty state.

The archived proposals retain the reasoning about small-row target thresholds,
whole-token matching, explicit heuristic definitions, additive output compatibility,
and ambiguous-schema verification. These are historical reviews; implementation
and tests establish the current technical contract.

## Extension Boundaries For Numek

The shared orchestration, profiling/scoring separation, evidence/finding
separation, and report interfaces provide useful seams for substantial expansion.
New diagnostics can be computed and explained before deciding their scoring
contribution. Additional interfaces can reuse the same analysis rather than
forking interpretation or scoring. Model-input workflows can build on evidence
and reporting abstractions with deliberately designed contracts.

There is no implemented plugin registry, general multimodal engine, model
adapter, ConfidenceGuard/HallucinationGuard package, hosted persistence layer,
or monitoring service. New capabilities may require architectural changes,
compatibility planning, and validation. Their selection follows
[Numek's expansion direction](NUMEK_MASTER_CONTEXT.md); this document describes
existing structure rather than promising a specific future implementation.

## M3 Contracts, Dispatch, And Compatibility

TaskSpec preserves positional kind/target and adds keyword-only targets,
feature_columns, metadata_columns, and group_columns. Strict from_dict rejects
ambiguous contracts. One semantic resolver runs against parsed headers before
analytical dispatch; `from_spec` retains the complete declaration. Input membership
is normalized in source order. Status/group fields become metadata. All target
columns are excluded from input pools, including regression relationship checks.

Equivalent singleton declarations, expected-only annotations, identical explicit
features, and equivalent scalar/mapped numerical expectations select existing
policies and serializers (M1 1.0/M2 1.1). Actual M3 semantics use schema 1.2 and
one of tabular_partial_classification_v1, tabular_annotation_regression_v1,
tabular_multilabel_v1, tabular_multioutput_regression_v1,
tabular_clustering_readiness_v1, tabular_anomaly_readiness_v1, or
 tabular_role_profile_v1. Renderer/projection decisions follow methodology,
including compatible declarations entered through an M3 browser form.

Annotation normalization retains valid observations under unresolved metadata;
known expected requirements remain known when status resolution fails. Required
coverage runs column-by-column with compact row counters. Cohort masks are yielded
one target at a time; no persistent dense annotation or distance matrix exists.
Joint evidence reports matched populations, exclusions, and zero-denominator
reasons. Optional failures produce partial results; invalid annotations are
completed observations; configuration/source/allocation failures abort.

Multi-output relationship generators share M2 work controls and round-robin
candidate scheduling. Separate output-pair, label-pair, cohort, and pattern bounds
record selected/excluded scope and consumption. Planned bounds remain completed
execution. Quantitative feature geometry requires declarations or disclosed
assumptions; numeric storage does not establish semantics. New scoring is undefined.

The browser's source/parsing/effective-specification fingerprints bind confirmation;
meaningful edits invalidate owned artifacts and caches. HTML/PDF derive from a
bounded presentation view, JSON retains every computed record, and ReportArtifacts
exposes presentation QA metadata. Internal PDF page budgets never cut rendered pages.
M3 validation preparation uses openpyxl and bsdtar outside the runtime package;
Linnerud comes from a pinned official release without importing scikit-learn.

## M4 disk execution and comparative scope

`m4_contracts.py` defines strict source roles, alignments, key/evaluation declarations,
advanced selections, resource limits and schema 1.3 results. `core.py` explicitly
dispatches opted-in analysis or `DataTrust.compare()` to `m4_worker.py`; legacy
pandas calls retain the existing serializers and policies. There is no backend
registry, complete-frame fallback or second new engine.

`scalable.py` owns immutable snapshots, structural CSV/token-digest agreement, bounded
C-tokenizer batches, whole-column type inference and exact positional disk relations.
Identifiers/keys resolve before normalization, preserve lexical tokens and default
to empty-only missingness. Numeric keys require finite identity-preserving conversion;
unsafe promotion or incompatible representations block equality instead of merging
units. Group identifiers remain outside quantitative geometry.

`m4_diagnostics.py` implements full-population structural/annotation/readiness checks
and bounded arithmetic, cohort, vector, missingness, dependence, constraint and segment
searches. Declared constraints execute independently of optional arithmetic checks;
regression target expectations join the same deduplicated constraint evaluation.
`comparison.py` applies explicit alignment, grouped overlap/multiset counts,
affected-row unions, schema evidence, empirical CDF/Wasserstein and categorical effects.
Feature/target role transitions are disclosed and remain eligible for qualified
marginal comparisons when representations/declared meanings are compatible;
optional tests retain the existing sampling/method gates. Missing or unselected fields are excluded
with specific reasons, while incompatible distribution methods are separately blocked.
Statistics are optional, declaration-qualified and BH-adjusted across successful job
marginals; conditional evidence stays descriptive.

One spawned worker commits evidence by diagnostic group; parent monitoring can
terminate native operations for cancellation, deadlines, RSS or storage failures.
Preflight uses user-available disk, owned snapshots and a conservative peak estimate
starting at max(4 GiB, six times combined bytes). The ledger charges max(logical,
allocated) bytes once per inode, including database/WAL/spill and uploads. Phase
checks reserve next allocations and exports; table drops are not assumed to shrink
the database. Source aliases count once per input role for combined limits, while
physical storage is deduplicated. Output filesystems reserve 256 MiB plus the
configured free-space reserve. Monitoring and estimates are not OS quotas or guarantees.

`m4_web.py` keeps session-owned sources and completed artifacts, one active worker,
confirmation fingerprints for every source/declaration, retained configuration and
cancellation. Local CSVs are restricted to configured roots with symlink escapes
rejected. Separate uploads retain the per-request cap. Source edits invalidate owned
results; exports verify digest ownership and never reanalyze. `m4_presentation.py`
and the canonical M4 template bound human detail, disclose shortened labels and
exclusions, and retain every computed record in JSON. Runtime artifact publication
protects every source/snapshot alias and keeps no-replace behavior.
M4 executive narratives use committed findings and coverage deterministically,
distinguishing declared violations, supported changes, clean completed scope,
and failed, blocked or bounded methods. They add no analysis or scoring pipeline.


## M5 temporal execution and presentation

`temporal_contracts.py` adds strict temporal-specific inputs/results without extending DatasetSpec. `temporal_normalization.py` preserves exact clocks and bounded CSV/optional Parquet adapters; `temporal_diagnostics.py` covers full structural/schedule/lifecycle populations. `temporal_availability.py`, `temporal_evaluation.py`, `temporal_behavior.py` and `temporal_multivariate.py` implement qualified timing/history/maturity/fold and bounded behavioral evidence. `temporal.py` orchestrates phases and atomic optional commits.

M4 and M5 use `worker.py` supervision and the existing `scalable.py` workspace with optional private phase plans. `distribution_effects.py` shares empirical mathematics while M4 interpretation/inference remains in comparison.py. Renderer/export dispatch explicitly selects schema 1.4; temporal_presentation.py and temporal templates project completed evidence. temporal_web.py registers the dedicated workflow in the same Flask app, sharing the application worker lock with M4. No registry or persistent state is introduced. See [M5 contracts and boundaries](M5_TEMPORAL_RELIABILITY.md).

## M6 text execution and private evidence

Schema 1.5 dispatch is additive; existing serializers and defaults are retained.
`text_contracts` defines explicit inputs, tasks, relationships, coverage and narrow
content/asset/location primitives. `text_normalization` strictly frames CSV/JSONL,
preserves original coordinates and streams private DuckDB relations. A private
workspace adapter reuses resource accounting without applying tabular NA/header
coercion to text. `text_diagnostics` handles required population checks and unique
identity joins. `text_search` selects metadata before loading bounded text, and
provides vocabulary, verified MinHash candidates, repetition and winnowed passages.
`text_models` lazily loads pinned local adapters and source-aligned token windows.

`text.audit_text` uses the shared supervised worker; model/tokenizer state remains
inside RSS/deadline/disk supervision. Scratch relations never become resolver
dependencies. Results return separately bounded private locator metadata;
`text_private` persists an owner-only sidecar and verifies exact source identity
under caller-supplied allowed roots. HTML/PDF/JSON use `text_presentation` and
`text_report.html`; canonical PDF access cannot fetch corpus assets. Disclosure
variants have separate fingerprints and source/asset/model/output protection.
`text_web` uses the existing app worker lock, session ownership and artifact
identity cleanup; uploaded sources remain outside worker scratch.

Selection reserves missing comparison sides together and round-robins declared
split/field/kind/length strata. Later indexing/inference work can still exclude
selected units; separate coverage records that loss. Embedding first/last coverage
is conditional on actual window and tokenizer allocations. Executive review actions
consolidate equivalent raw/NFC instructions without merging technical evidence.
Unexpected optional text faults use `whole_audit_atomic_fail_closed`: no completed
result is published and the workspace is deleted. Unlike recoverable optional
tabular/temporal stages, M6 does not claim safe required-only recovery after a native
fault. Expected budget stops remain completed bounded investigations.

See [M6 detailed behavior and limitations](M6_TEXT_RELIABILITY.md), the pinned
search/model identity files and `validation/m6/runtime-lock.txt`.


## M7 image execution and private evidence

`image_contracts` supplies distinct source/task/annotation/comparison/resource
declarations and schema 1.6 results. `image_sources` plans metadata/media admission,
streams standard adapters and maintains DuckDB identity relations. `image_assets`
verifies root-constrained actual handles and bounded immutable captures, decodes
named raster representations and computes previews/signatures. `image_annotations`
and `image_diagnostics` own structural populations, explicit frames/taxonomies,
composition, exact groups and declared comparisons.

`image_search` indexes seven signature partitions, prioritizes cross-split
populations and charges saturated/capped work. `image_models` verifies pinned
local artifacts and isolates CPU execution. `images` owns one global deadline,
frozen required core, bounded optional model allocation and final byte/membership
verification. Workspace's image source plan estimates owned relation/index/buffer
storage rather than six-times-media storage; existing callers are unchanged.

`image_private` binds protected locator manifests, metadata-free selected previews,
overlays and disclosure variants to canonical artifact identity.
`image_presentation` and `image_report.html` project eight topics without a score.
`image_web` and `image_ui.html` implement standard presets, asynchronous inspection,
one confirmation, private downloads and a session-local opaque inspector, sharing
the existing lock/CSRF/ownership/cancellation lifecycle. Python/CLI/browser reuse
the same engine and exports; CSV DatasetSpec and M6 image associations are unchanged.

No persistent corpus copy, generic modality framework, service or cloud dependency
is introduced. See [detailed contracts and execution boundaries](M7_IMAGE_RELIABILITY.md).

## M9 connected representations and native evidence

`cross_contracts` adds schema 1.7 with explicit relationships, contextual bindings,
reusable document recipes, reconciliation/separation and bounded models.
`cross_sources` owns projected disk-backed records/units/edges/contexts/outcomes,
typed/lexical identities, secure captures and settings-specific extraction reuse.
`cross_documents` retains PDF glyph/cell geometry and DOCX XML locations with
bounded coverage. `cross_diagnostics` resolves joins, all association context,
recipes, precision-safe comparisons, competing values, M5 temporal selection and
supplied separation/ancestry. No public ontology or generic validation engine is added.

`cross` coordinates one required supervised core, isolated optional models and
final integrity publication, retaining peak resources across phases. `cross_models`
adds verified English NLI with M6 E5 retrieval and full paired SigLIP; packaged
qualification pins settings, measured populations and algorithm identity.
Unsupported/unqualified populations abstain. Source mutation, cancellation and
global failures are fatal; an isolated unexpected model fault may publish a
verified partial core. Bounded optional work remains explicit.

`cross_private` resolves originals through owner-only manifests and creates
disclosure variants through shared canonical exporters. `cross_presentation` and
`cross_report.html` project completed evidence without a score. `cross_review`
serializes independent exact-result-bound dispositions; no notes or decisions
alter analytics. `cross_web`/`cross_ui.html` reuse ownership, lock, CSRF,
confirmation, cancellation and collision controls for guided previews, result
reopening and exact evidence/review round-trips. No persistent corpus/vector/review
service is added. See [M9 contracts and limits](M9_CROSS_REPRESENTATION_RELIABILITY.md).

CG3 is complete, including corrections R1–R3, as confirmed by the user on 2026-10-21. See [correction record](../validation/cg3/review-corrections/README.md).
