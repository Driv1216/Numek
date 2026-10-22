# Executed verification ledger

This ledger distinguishes executed checks, reused evidence and source review.
The repository's proportional-verification skill is authoritative. Tests use
`--import-mode=importlib`. Results below are separate runs, not additive test totals.
The delivery reuses valid earlier evidence; unchanged reports were not regenerated
for packaging. Engineering verification does not close independent review or user
acceptance gates.

## Executed and reused closure evidence

| Evidence | Result | Scope / reuse boundary |
|---|---|---|
| Full repository pytest suite | 798 passed, 1 skipped, 6 dependency deprecation warnings; 298.46 s | Shared host/ingestion changes included. Later CG3-specific refinements are covered by affected runs; unrelated model/modality qualification reused. |
| Final affected CG1/CG2/CG3 tests | 124 passed, 1 skipped; 112.73 s | Legacy compatibility plus historical lifecycle/math/interfaces. |
| Delivery CG3 suite | 43 passed; 59.20 s | Capture, selection, inference, analytics, lifecycle, security, disclosure. |
| Final CLI interface checks | 2 passed; 3.95 s | Last runtime edit adds analysis/restatement request IDs; no report/math changes. |
| CG3 review gates | 20 passed; 26.65 s | Focused foundational, lifecycle and privacy gates. |
| Publication/lifecycle gates | 13 passed | Fault boundaries, cancellation, receipts, correction and deletion behavior. |
| Historical checksum verifier | passed | `python -m validation.verify`. |
| Historical dry-run checksum verifier | passed | `python -m validation.dry_runs.verify`. |
| Preserved CG1/CG2 artifacts | 568 files byte-identical; 36 bundles reopened | `results/historical-preservation.json`; no rewrite of original assessments. |
| Schema/OpenAPI/examples | passed | Draft202012Validator over generated contracts/examples, including legacy transport examples; jsonschema 4.26.0 used as a dev-only tool. |
| Independent arithmetic | 18 task/window/metric checks passed | `reference.py`, no engine imports: accuracy, Brier, log loss, MAE/MSE/bias, interval coverage, empirical CRPS from pinned CSVs against existing final JSON. |
| Final PDF visual review | 41 pages rendered and inspected | Binary shareable 10, multiclass shareable 7, regression local 24; all pages contact-sheet reviewed. Canonical HTML/JSON/PDF exports share disclosure projection. |
| Browser stories | completed | Consent; unlabeled retention; delayed label registration/backfill; immutable outcome restatement; comparison/qualifications/support; HTML+JSON export; reopened evidence; multiclass accuracy; regression sample-score timeline; restart-grant refusal/redeem. Screenshots retained. |
| Final wheel | built | Complete source/static/schemas/templates; final CLI edit included. Clean extraction/import/reproduction results are in `evidence/packaging.json`. |

The skip is the existing optional/admission path recorded in pytest output.
Warnings are upstream SWIG/pycocotools deprecations, not hidden test failures.

## Acceptance coverage in tests/source review

- **Capture/identity:** lossless admitted projection before eligibility; frozen
  CG2 outputs before E-only projection; originals removable; lexical keys;
  overlap/canonical conflict; retries/samples/revisions not extra observations;
  matching opportunity/target uniqueness; E-label noninterference control.
- **History:** K versus A, earlier cutoff selection, due/equal follow-up,
  revision withdrawal/order/authority/competing heads, orphan backfill, frozen
  prediction K+A/metadata restatement, retained predecessor bytes, context corrections.
- **Analytics:** drift without deterioration, deterioration without marginal
  drift, Simpson/cohort mix reconciliation, matched variants/contrast evolution,
  task/target/partition/score/output compatibility, sample/quantile and nonfinite
  semantics, changed feature retention, exact actual decision costs.
- **Inference:** fixed-size independent arms; union entity resampling/event weights;
  whole paired bin contributions/noncircular blocks; regular cadence/gaps;
  effective support and class support; Bonferroni family preservation; refusal for
  nonfinite/degenerate/invalid/tail/resource/dependence conditions; sensitivities
  remain exploratory; legacy CG2 procedures/RNG reused unchanged.
- **Lifecycle/security:** injected failure before/after object publication and
  catalog visibility; lost-response receipts; operation/object lock order and
  bounded contention; partial/full purge recovery/dependency closure; no orphan
  promotion or corrupt committed replacement; backup/restore identity;
  future-catalog refusal; authorization attachment, ownership, CSRF/token scope,
  restart/detach/purge invalidation; jointly protected metrics including failure
  count subtraction bypass; no exact hidden shareable chart payloads.
- **Resources:** bounded rows/records/chunks, quota/free-space/cancel, inference
  work, supervised worker RSS/scratch, directory indexes, no silent sampling.
  Reader/parser metadata and filesystem UID/mode/symlink/hardlink rules received
  source review in addition to tests. Local filesystem locking/fsync assumptions
  are a deployment contract; network filesystem behavior is deliberately unsupported.
- **Interfaces:** Python services, Click workspace commands, shared API jobs and
  browser client dispatch reuse one analytical implementation. Inference/advanced
  declarations are exposed through strict JSON contracts; no second browser engine.

## Statistical qualification (executed once; reused)

`statistics.json`: 100 trials/design, nominal confidence 0.90, 1,000 bootstrap
replicates, with Wilson 95% Monte Carlo intervals and refusal rates.

| Design | Empirical coverage | MC interval | Refused |
|---|---:|---|---:|
| IID independent periods | .93 | [.8625, .9657] | 0/100 |
| Unequal whole entities | .92 | [.8500, .9589] | 0/100 |
| AR(1), n=300, primary L=5 | .79 | [.7002, .8583] | 0/100 |
| Deliberately invalid IID serial control | .52 | [.4232, .6154] | 0/100 |

`block-qualification.json`: 100 trials, AR(1) phi=.6, n=1200, primary L=20
coverage .86, MC interval [.7786, .9147]. Exploratory L=10: .87; L=40: .86.
The short-block failure is retained. Neither larger n nor a sensitivity proposal
proves general validity. Support floors do not detect all poor block choices.
No automatic length selection, significance selection or remedial rerun is used.
Change-point controls cover stable, shifted, seasonal, sparse/gapped and
maturity-driven series; candidates remain exploratory.

## Local historical workloads (executed; reused)

| Workload | Record / reconstruct / full-overlap seconds | Persistent bytes | Resource evidence |
|---|---|---:|---|
| 1,000,000 binary opportunities | 748.041 / 382.275 / 569.339 | 7,288,393,728 | worker RSS peak 2,916,958,208; scratch peak 4,554,039,296 |
| 10,000 × 50 classes | 10.361 / 6.015 / 9.507 | 98,840,576 | RSS 532,267,008; scratch 101,351,424 |
| 10,000 regression × 100 samples | 278.619 / 89.068 / 317.661 | 2,672,644,096 | RSS 1,533,362,176; scratch 621,330,432 |
| Sparse backfill: 100 updates / 100,000 history | append 1.213 | see JSON | prediction object hash/size/mtime unchanged; indexed identity query |
| Final canonical-equality overlap: 100,000 | overlap 58.421 | see JSON | 500,000 duplicate facts plus new capture metadata; predictions unchanged |

The million-event reconstruction materialized 4,000,000 selected analytical
records, 1,700,219,878 decoded payload bytes. Record bytes read and checksum
verification bytes were each 3,258,886,548 (99 objects). These are logical read
counters, not measured physical disk IO. One analytical corpus materialization
is reused across windows/metrics; checksum verification is additional reading.
No full historical parse is used just to establish new-import non-overlap, and
backfill does not rewrite predictions. Reconstructed source cutoffs were separately
measured; each new requested assessment can materialize once.

Workload phases ran under concurrent local load. Early large-format measurements
precede later metadata/privacy refinements; the final bounded canonical payload
comparison additionally received the 100k overlap probe. Reusing format/resource
evidence is deliberate, not a claim every timing used exactly the final source hash.
There is no isolated-speed or unlimited-capacity promise. JSONL's measured expansion
is a real product limitation, particularly sample-heavy history.

## Failures corrected during implementation

Early focused checks found clock/correction selection, deleted-assessment listing,
shared insertion admission, sample attempt matching, metadata snapshot retention,
restatement prediction cutoff freezing, and related-family/failure-count disclosure
issues. Those were corrected and the affected coherent gates rerun; passing final
logs are retained. Early synthetic PDF sets were regenerated while disclosure/chart
code was changing. The final delivered set is fixed; packaging reuses it.

No known failing implementation check remains. The short-block undercoverage is
method qualification evidence, not suppressed as a test failure. No general temporal
coverage, missing-label correction or causal/product deployment guarantee is asserted.

## Extracted delivery outcome

The wheel installed into an empty target without downloading dependencies. Both
packages imported from that target; every packaged runtime source/asset matched
the wheel. Three immutable synthetic assessments reopened after backup restore.
A retained-fact binary reconstruction matched all 146 metric/scope/denominator/value
states; numeric values matched at rel=1e-10/abs=1e-12 (largest difference 2.8e-17).
Nine focused extracted tests passed in 6.42 seconds. Eighteen independent arithmetic
checks against existing reports passed. No report was regenerated.

The packaging harness initially used stdin for multiprocessing and exact float
equality; those harness issues were corrected. The already committed reconstruction
was reused through its idempotent receipt, not recomputed. The final inventory
was extracted and verified after adding these packaging records.

## CG3 completion — 2026-10-21

CG3 is complete as confirmed by the user, including R1–R3 corrections. The correction
run recorded 46 passed and one optional skip, with three focused final checks passed.
Existing valid evidence was reused. No tests, report generation or ZIP packaging
were run for this documentation-only completion update.
