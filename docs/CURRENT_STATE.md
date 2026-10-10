# Numek Current State

Last updated: 2026-10-11
Product status: Classification baseline preserved; M1 shared contracts/unlabeled
profiling, M2 regression, M3 annotation workflows, M4 comparative/scalable analysis, and M5 temporal reliability implemented.
M1–M3 and M3’s understanding gate are accepted by the user. M4 has internal engineering verification.
Project direction: Approved DataTrust expansion architecture and nine-milestone roadmap.
Documentation reset: Completed.

## What Works Now

- **Interfaces:** public `DataTrust` Python API, `datatrust audit` CLI, and guided
  local Flask browser UI through `datatrust ui`; Python package requires 3.10+.
- **Browser workflow:** CSV validation/preview, grouped explainable target
  choices with no preselection, server-enforced acknowledgement for advanced
  targets, automatic binary/multiclass/single-class confirmation, optional
  report context, compact result overview, full HTML view/download, and native PDF.
- **Analysis:** dataset/feature profiling; separate target missingness;
  cell-level and row-level missingness; exact duplicates and feature-identical
  conflicting-label groups; class balance and majority baseline; constants,
  near-constants, cardinality, numeric quartiles/zero/negative/non-finite values,
  IQR outliers, and strong versus review-only name-based leakage evidence.
- **Interpretation:** five transparent sub-scores, uncapped evidence score,
  explained guardrails and final risk band, complete prioritized findings,
  compatible top-three risks, and one deterministic narrative for UI/report.
- **Reports:** canonical standalone eight-topic HTML, print-safe visuals,
  portrait decision pages and landscape technical appendix; Python/CLI/UI PDF
  conversion from canonical HTML using WeasyPrint, plus strict JSON. Humanized fallback titles,
  deterministic grammar, and a designed clean-report state are implemented.
- **Local lifecycle:** loopback-only, single-user UI with process-scoped
  temporary jobs and a configurable default 100 MiB upload limit.
- **Evidence:** three prepared UCI datasets, eight deterministic Adult
  mutations, eleven generated validation reports, reviewed leakage ledger,
  isolated internal Evidently comparison, and preserved historical review records.
- **M1 target-free workflow:** Python specifications/results, conditional CLI
  targets, browser mode and refreshed parsing preview, and eight-topic unlabeled
  HTML/PDF/JSON. All columns participate; no unlabeled scoring policy is invented.
- **M1 disclosures:** bounded source-token fidelity review, explicit parsing
  manifest/source hash, applicability/execution/evidence/coverage, partial reports,
  and configurable operational safeguards with documented enforcement boundaries.
- **M2 regression:** explicit numeric outcome, optional continuous/count expectations
  and range/integer/nonnegative constraints; finite populations, variation,
  quantitative distributions, contextual extremes/concentration/grid evidence,
  bounded copy/affine/two-feature-sum checks, qualified support and availability,
  consolidated relationships, and repeated-input target variation. No scoring.
  Browser confirmation and consistent HTML/PDF/JSON use the shared engine.
- **Artifact lifecycle:** collision-safe no-replace publication, deterministic
  PDF HTML sibling (or explicit path), exact HTML reuse, retained HTML/JSON on PDF
failure, and browser job-owned identity/cache verification and invalidation.

Drivyaansh accepted this baseline on 2026-08-13. The former mandatory external
practitioner-validation round was removed on 2026-08-04. External product and
reader-validation questions remain unresolved; baseline acceptance did not
claim those questions were answered.

## Verified State

Read-only verification on 2026-10-07, before this documentation-only reset:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src .venv/bin/python -B -m pytest -q -p no:cacheprovider
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src .venv/bin/python -B -m validation.verify
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src .venv/bin/python -B -m validation.dry_runs.verify
```

Results at the documentation reset: **70 tests passed**; classification corpus
and historical archive verification passed. M1 verification on 2026-10-09 also
protects exact results and normalized legacy HTML for all eleven classification
cases and checksums for 39 stored evidence files. The separate unlabeled validator
checks known synthetic evidence and label-free German Credit (1,000 x 20), Bank
Marketing (45,211 x 16), and Adult (48,842 x 14). Run it with
`PYTHONPATH=src .venv/bin/python -m validation.unlabeled.verify`.
These are internal engineering checks, not external methodology/customer validation.

M1 verification: **129 tests passed**; classification corpus, historical archive,
and separate unlabeled verifiers passed. A real loopback browser workflow was
exercised; generated PDF text and all nine pages of a long-header report were
visually inspected. Resource defaults are operational safeguards rather than
benchmarked capacity claims. No historical reports were regenerated.

M2 verification on 2026-10-09: **190 tests passed** and all four validators
(classification, historical dry-run archive, unlabeled, and regression) passed.
The regression validator covers 18 pinned public/synthetic cases with independent
quantitative reference checks. Concrete and both Bike tables detect the intended
evidence; Bike component-removed controls pass. Recorded analytical runs took
approximately 0.07 seconds for Concrete, 0.23 seconds for Bike hour, and 0.10 seconds
for Bike day on the recorded local environment, excluding PDF conversion. These
meet the internal 30-second engineering target without establishing capacity guarantees.
Real browser checks cover continuous, count/constrained, ambiguous, bounded, and
partial workflows. All 76 PDF pages across six presentation cases were visually
inspected. Classification legacy results/scores/normalized HTML and historical
artifact hashes remain protected; frozen unlabeled analytical parity also passes.
See `validation/regression/results/verification.json` and the browser/presentation
manifests. These establish internal correctness, not external methodology validity.

Following functional acceptance, the narrow M2 presentation cleanup passes
**193 tests** and all four validators. Executive population metadata is rendered
as prose with single punctuation, empty relationship/example tables have explicit
empty states, and configured source-token limits are labeled expected coverage.
Eight affected pages across four PDF exports were visually inspected; each export
retains an identical saved analytical result. Evidence is under
`validation/regression/results/presentation_cleanup/`. This is the preserved pre-M3 baseline.

Stored corpus results cover German Credit (1,000 × 21), Bank Marketing
(45,211 × 17), and Adult (48,842 × 15); all eight mutation assertions passed.
All eleven reports contain eight topics and recorded generation under 30 seconds.
Detailed timings are historical descriptive measurements, not production
benchmarks or new measurements from this reset.


## M3 Delivered Behavior And Verification

- Strict multi-target TaskSpec and explicit feature/target/metadata/ignored roles;
  source-order normalization and effective-policy compatibility preserve legacy outputs.
- Independent annotation expectation, actual observation, and declared status;
  default unknown expectations in new workflows, intentional/uncertain distinctions,
  per-target/row/group coverage, and bounded population contrasts.
- Multilabel indicator decoding, complete/partial vector evidence, cardinality,
  density, pairwise matched populations, constraints, and repeated-input consistency.
- Reused M2 numerical primitives across outputs, shared relationship budgets,
  finite-vector coverage, declaration unions, and separate output dependencies.
- Conditional feature geometry, categorical/identifier exclusions, scale/sparsity,
  repetition, and marginal anomaly-candidate context without fitted models/verdicts.
- Guided Python/CLI/browser specifications, schema 1.2, completed-result exports,
  compact HTML/PDF projections, and full computed JSON evidence.

M3 tests freeze the current working tree's completed M2 analytical/HTML results,
retain M1/classification fixtures and historical checksums, and independently
assert annotation truth tables, group denominators, indicator mathematics,
Pearson, constraint logic, numerical precision, coding semantics, bounds, and
interface equivalence. Public validation pins Energy (768 × 10), Scene
(2,407 × 300), and Linnerud (20 × 6), plus controlled partial, unsupervised,
empty, and wide derivatives. Source/member/prepared hashes and available license
information are under `validation/m3/manifest.json`.

Measured results, final PDF page budgets, runtime/frame/result sizes, artifact
hashes, browser checks, and visual QA are recorded under `validation/m3/results/`.
These are internal correctness and readability checks; they do not establish
label correctness, model performance, external score validity, or customer value.

## Important Artifacts

- [Usage and installation](../README.md), [methodology](../METHODOLOGY.md),
  [architecture](ARCHITECTURE.md), and [strategic context](NUMEK_MASTER_CONTEXT.md).
- [Synthetic example CSV](../examples/loan_data.csv) and
  [generated example report](../examples/report.html).
- [Validation reproduction guide](../validation/README.md), prepared data under
  `validation/data/prepared/`, controlled inputs under `validation/data/mutations/`,
  and generated reports under `validation/reports/`.
- [Corpus results](../validation/results/MILESTONE_2_SUMMARY.md),
  [leakage ledger](../validation/results/leakage_review.csv),
  [machine-readable summary](../validation/results/validation_summary.json), and
  [internal Adult comparison](../validation/comparison/ADULT_COMPARISON.md).
- [Historical review archive](history/reviews/README.md),
  [dry-run workspace](../validation/dry_runs/README.md), and
  [returned RC_003 review caveats](../validation/dry_runs/evidence/RC003_TECHNICAL_REVIEW_SUMMARY.md).
  Candidate records remain under `validation/dry_runs/release_candidates/`;
  packet ZIPs/manifests remain locally under the ignored `validation/dry_runs/packets/`.

The returned reviewer HTML files are described by the evidence summary; they
were not copied into the repository. Historical six-section review artifacts
remain distinct from the current eight-topic reports.

## Current Implementation Limitations

- CSV classification, partial annotations, multilabel indicators, multi-output regression,
  role-aware profiling, clustering/anomaly readiness, split audits and version comparisons.
  No model-prediction analysis, longitudinal monitoring or non-tabular modalities.
- Regression has no validated overall score, sub-scores, risk band, or readiness verdict.
  Arithmetic relationships are bounded, support-qualified observations; feature
  availability is declared/unknown. General nonlinear/multifeature dependency
  mining and instrument-resolution/quantization semantics are deferred.
- Single-user, non-persistent local UI; no hosted service, accounts, persistent
  database or saved report history. M4 uses an owned temporary DuckDB database,
  one supervised worker and explicit source/configuration reconfirmation.
  Automatic server reloading is disabled.
- HTML/PDF/JSON in all interfaces. Word export and a demo notebook are not implemented.
- WeasyPrint may require native font/rendering prerequisites. Default pandas
  analysis materializes data in memory; opt-in M4/scalable analysis uses bounded
  raw ingestion and disk-backed DuckDB relations, with storage and I/O costs.
- Legacy cooperative safeguards and M4 disk/RSS/deadline supervision are not
  hard process quotas or capacity guarantees. Native operations and monitoring
  can overshoot; source shape/cardinality and available disk constrain execution.
  See usage/methodology for per-source versus combined limits and replacement semantics.
- Heuristic leakage and comparative effects require domain/provenance review.
  M4 implements bounded feature dependencies, missingness patterns and declared
  segments, plus schema/population changes across versions. Proven label error,
  missingness mechanisms, fairness, model calibration, semantic-date/fuzzy-category
  matching and unrestricted nonlinear/subgroup mining remain outside scope.
- Independent market usefulness, reader comprehension, sharing workflows, and
  external score-defensibility evidence remain open product questions.
- Reports do not establish safety, legal compliance, fairness, certification,
  or model correctness.

These limits describe today's implementation and can change through deliberate,
verified product development.

## M3 Internal Verification (2026-10-09)

The complete suite passed 271 tests. After the final presentation and iteration
changes, the focused M3 suite passed 77 tests; the isolated minimum-dependency
suite passed 75 independent M3 tests. All four existing validators and fifteen
pinned M3 cases passed, with classification/M1/M2 parity and historical artifact
hashes preserved. Seven real browser workflows completed, including the explicit
expected-annotation declaration that retains legacy classification behavior.

Every final PDF page was visually inspected: 39 pages across six presentation
cases and six pages from the real browser regression download. Scene is eight
pages and the wide synthetic report is twelve; both meet their page budgets.
Final report refreshes reused completed JSON without reanalysis. Recorded
analytical runs met the internal 30-second target; timings are not capacity
guarantees. See [verification evidence](../validation/m3/results/verification.json),
[presentation review](../validation/m3/results/visual_qa/manifest.json), and
[browser evidence](../validation/m3/results/browser/manifest.json).

## M4 delivered behavior and closure (2026-10-10)

Split, version and advanced standalone workflows share one DuckDB path, with
schema 1.3, declaration-aware lexical identity, full structural populations,
bounded task-family diagnostics, effects/support-led comparisons and optional
qualified inference. Python, manifest-relative CLI and guided local browser flows
export completed HTML/PDF/JSON. Existing pandas contracts and score formulas remain
preserved; comparisons have no aggregate score.

Disk preflight, allocated/logical inode accounting, per-source and combined limits,
phase reservations, spill budgets and parent-supervised RSS/deadline/cancellation
controls are implemented. Resource controls can overshoot; capacity is not guaranteed.
The 64 GiB workspace ceiling is a budget, not a requirement for every job.

Closure ran the full pytest suite and classification/archive, unlabeled, regression,
M3 and new M4 validators. Historical hash checks preserved 194 files. Subsequent
focused M4 verification covered final identity/statistical/report fixes. Real browser
split/version/advanced flows, downloads, configuration retention and cancellation
were exercised; a test-only fixture covered partial exports. All 25 final pages of
six PDF cases were inspected, with one-page executive sections and four/five-page
ordinary, wide and long-header reports. Human projection bounds never discard PDF
pages or computed JSON records.

The recorded 16 GB laptop measurements cover approximately 1 and 5 GiB combined
four-column CSV inputs, a 512 MiB spill-heavy long-key split job and exact quantiles
under 32 MiB engine memory. They establish measured behavior for those workloads,
not arbitrary width/cardinality or exhaustive advanced-search capacity. A retained
128 MiB allocation failure makes that limitation explicit.
See [M4 evidence](../validation/m4/README.md) and its result manifests.

## Previous M4 handoff context

Review M4 thresholds, optional-statistics packaging, local-file roots and resource
defaults against the founder's intended use. M1–M3 acceptance is settled. M4's
internal checks do not establish external method validity or guarantee capacity.
Default-engine replacement, time-series/modalities and prediction/model work remain
separate future decisions.
The 2026-10-11 constraint, role-change and narrative corrections received source-only
review; execution verification was not repeated for this pass.


## M5 temporal reliability — current implementation

M5 now exposes DataTrust.audit_temporal, `datatrust temporal`, and a dedicated local browser workflow. It includes exact clocks/DST, CSV/optional scalar Parquet, independent temporal semantics, full chronology/schedule/lifecycle/panel populations, feature-bound availability and exact-observation revisions, target maturity, supplied static/rolling evaluation plans, configurable window/run/volatility/seasonal/panel/multivariate investigation and canonical HTML/PDF/JSON. Schema 1.4 has no universal score.

Shared changes are confined to worker supervision, private workspace phase planning, pure distribution mathematics, explicit artifact dispatch and application-level browser worker exclusion. Existing public M1–M4 inputs and classification policies remain unchanged. Read [M5 implementation and limits](M5_TEMPORAL_RELIABILITY.md) and [new verification evidence](../validation/m5/README.md). M4's earlier execution closure and subsequent source-only corrections remain separate historical evidence.

Current work is the completed M5 implementation and its recorded verification. Remaining resource and threshold uncertainties are declared engineering/research limits, not claims of validated capacity or universal temporal defects. See the M5 evidence ledger for current execution, reused evidence and historical distinctions.
