# CG1 first independent review — focused correction handoff

Implemented 2026-10-18. Founder acceptance and independent re-review remain pending.
CG1's three-task scope is retained; CG2 was not started. No commit or push was made.
The existing CG1 work was already untracked, so the correction patch is relative
to a captured start-of-turn file snapshot, not Git HEAD. Unrelated design labs and
other work were preserved.

## Root causes and corrections

| Finding | Actual cause | Correction |
|---|---|---|
| Population/denominator provenance | `Evidence.add` hashed only run/scope/predicate and overwrote the ledger entry. Precision/recall/specificity used an unconditional decision predicate despite class-conditional denominators. The high-confidence share used the high-confidence subset predicate despite an all-error denominator. Policy methods omitted selector/cost eligibility predicates. Paired temporary relations reused the same local predicates over different intersections and interval remappings. | Frozen normalized-input lineage plus eligibility and denominator meaning define each identity. Exact SQL counts are checked, with grouped confusion counts reused to avoid a scan per class. Conditional predicates, policy predicates and not-evaluated populations are explicit. Nested per-class references identify their denominators. Paired projections bind both runs, intersection and interval remapping. Deltas identify a common paired base and both conditional populations/supports. Reopening validates the revised ledger. |
| Conservative ranking disclosure | The curve's sensitive-count list contained only total positive/negative support. Individual score thresholds and small cumulative cells could survive with large global support. Native extrema/quantiles provided another route to exact scores. | Default conservative exports withhold ROC/PR curves and native ranking/selection/class-score summaries. Authorized local and explicit exact exports retain them. Scalar AUC/AP still use all tied score groups. One projection feeds JSON, HTML/SVG and PDF. Old conservative JSON is hardened on re-export, preserving its original digest as provenance. |
| Portable interpretation loss | The projection synthesized withholding/infinity findings and unconditionally emitted `checks=[]`, discarding useful safe interpretation. | Known finding codes get safe static text and aliased run IDs; known check identities retain applicability/execution/reason statuses. Counts, private inventories, arbitrary free text and category/source values are omitted. Comparison blockers, repeated-entity inference warnings, held-out qualifications, timing and limitations remain. A dependent infinite-loss finding is withheld with its protected loss. Canonical reports display checks and limitations. |

For precision, the left/right positive-decision subsets can differ even within an
identical paired base. Intersecting both positive subsets would redefine precision
and can force an uninformative equal result. The correction explicitly reports
both conditional supports rather than claiming identical conditional events.
No paired significance or automatic model winner is inferred.

## Changed source and contracts

- `src/confidenceguard/analytics.py`: relation lineage, immutable population records,
  exact count checks, conditional predicates/supports and paired delta provenance.
- `engine.py`: final ledger consistency assertion and population provenance marker.
- `result.py`: revised ledger validation on reopening and legacy shareable re-export.
- `disclosure.py`: conservative ranking withholding, safe findings/checks and
  disclosed population references without predicates or source lineage.
- `artifacts.py`, `templates/report.html`: visible method qualifications/limitations.
- `schema.py`, `schemas/contracts.json`, `schemas/openapi.json`: additive denominator
  semantics and protected population definitions; bundled documents regenerated.
- `tests/cg1/test_review_corrections.py`: 11 focused regression cases.
- `validation/cg1/review_corrections.py` and `review_corrections_resources.py`:
  reproducible focused reference/export/privacy and bounded resource evidence.
- CG1 methodology, the methodology index and current-state record were updated.

The result/spec/API major versions and metric formulas remain unchanged.
`coverage.population_provenance_version="1.1"`, `denominator_kind`, population
lineage, class/delta references and `coverage.projection_revision` are additive.
Corrected opaque population IDs intentionally change. Conditional paired-delta
`denominator` now describes common base support; left/right conditional denominators
are explicit in `data`. Consumers must not interpret that base as a conditional
formula denominator. F1/macro support is explicitly distinguished from its formula
or class-aggregation denominator.

Old exact bundles remain loadable with their matching manifests, with legacy
qualification when projected. They cannot acquire corrected lineage without
reevaluation. Old portable JSON cannot recover previously discarded findings.
Re-exported legacy conservative projections receive a new projection digest and
retain `origin_projection_digest`; historical files are never overwritten.

## Before/after evidence

All paths below are relative to `validation/cg1/results/review-corrections/`.

| Evidence | Before | After |
|---|---|---|
| Stored population ledger (`recorded-defects-before.json`; fresh `final-reports/*-local.json`) | 66 binary and 22 multiclass measurement/ledger denominator mismatches | Zero mismatches over 302 binary, 234 multiclass and 181 regression records |
| Full matched analytical values (`historical-metric-comparison.json`) | Historical reference reports | All 717 matched records retain their scalar values/value states; 15 binary and 8 multiclass paired-delta support counts are corrected |
| Executable defect regressions (`before-regressions.txt`, `targeted-final.txt`) | Four selected tests fail against captured original source for ledger inconsistency, curve leakage, dropped qualifications and unsafe legacy re-export | All 11 focused regression cases pass |
| 500 unique-score rows (`final-reports/unique-scores-*`) | Local retained curve includes a cutoff with cumulative count 1 and retained cumulative counts 1–9 | Exact local curve preserved; portable curve/native-score details absent; AUC/AP unchanged; sentinel score absent from portable JSON/HTML/PDF, no ROC polyline in SVG |
| Sensitive qualification case (`final-reports/qualified-shareable.*`) | Old projection retains only withholding text | Train-role, repeated-entity, invalid-probability and conflicting-outcome findings, blockers, aliased checks and limitations survive; sentinel private values absent |

The new tests independently assert row/event membership, not just hash inequality:
class-conditional and high-confidence denominators, three equally sized but
different decision/probability/ranking intersections, and equally sized regression
point/interval intersections after temporary-column remapping. They also check
normalization-setting identity, repeatability, invalid-ledger rejection and
intentional wrong-count publication failure.

## Executed verification

Commands were run with `PYTHONDONTWRITEBYTECODE=1`, `PYTHONPATH=src:.`, and
`.venv/bin/python -B`; no dependencies were installed.

1. `-m pytest tests/cg1 tests/test_web.py -q --tb=short`
   — **50 passed in 8.68s** (`tests-final.txt`). This includes the then-current 10
   new regression tests, all 27 existing CG1 tests and 13 legacy web tests.
2. `-m pytest tests/cg1/test_review_corrections.py -q --tb=short`
   — **11 passed in 1.64s** (`targeted-final.txt`), including one subsequently added
   interval-remapping regression. No product source changed after the 50-test run.
   Thus **51 distinct affected tests** passed across these runs, not 61 distinct tests.
3. `validation/cg1/review_corrections.py --out validation/cg1/results/review-corrections/final-reports --schema-path /opt/homebrew/lib/python3.11/site-packages`
   — **24 pinned independent reference metrics passed**, all local/shareable
   results validated against JSON Schema, protected populations validated, bundled
   schemas/OpenAPI/examples matched their generators. Three real PDF exports and
   their matching HTML/JSON passed the unique-score and qualification privacy
   assertions (`validation-final.txt`, `final-reports/verification.json`). The
   existing system jsonschema installation was reused; predictor fitting was not rerun.
4. `validation/cg1/review_corrections_resources.py --out validation/cg1/results/review-corrections/resource-probes`
   — ordinary binary 10,000 rows / 20,000 probability cells: **11.48s**, sampled peak
   RSS **180,977,664 bytes**, protected result **51,649 bytes**; wide multiclass 8,000
   rows / 384,000 cells: **9.20s**, sampled peak RSS **239,648,768 bytes**, protected
   result **276,280 bytes**. Both succeeded with zero observed spill. Tests ran
   concurrently with part of the ordinary probe; timings are not isolated benchmarks
   or directly comparable speed-regression estimates.
5. `pdftoppm -scale-to 1100 -png <pdf> <prefix>` for all three selected PDFs:
   exact unique-score control (17 pages), conservative unique-score report (15),
   and conservative qualification/blocker report (17). All **49 rendered pages**
   were inspected in nine contact sheets. No clipping/overlap was observed; exact
   local ROC is visible and absent from the conservative report. Existing bounded
   detail excerpts and spacious page-break behavior remain. Contact sheets are
   included in the review ZIP; intermediate individual page rasters stay local.
6. SHA-256 comparison against the correction-start snapshot: **93 DataTrust source
   files byte-for-byte unchanged**, including the preexisting CG1 Flask integration
   (`datatrust-compatibility.json`). No packaging/dependency/shared runtime source
   was changed by these corrections.

The four failing baseline regressions used the same current test definitions with
`PYTHONPATH=/private/tmp/numek-cg1-focused-review/before/src:.` and the filter
`-k 'ledger_matches or conservative_unique or safe_findings or legacy_shareable'`.
Their nonzero exit is expected and demonstrates the original defects.

Previously recorded CG1/full-repository/browser/corpus qualification remains
historical evidence, not newly executed verification. The old 526-test repository
run was **not** repeated. No live browser automation, wheel build, model fitting,
large historical corpus/model qualification or capacity-ceiling experiment was
rerun for these focused changes. Flask/CLI/ownership/cancellation/export regressions
are covered by the existing CG1 and legacy web tests in the affected run.

## Limits and re-review

Conservative score-detail withholding deliberately sacrifices portable ranking
curves; authorized exact output preserves them. This is a disclosure guardrail,
not differential privacy or resistance to every auxiliary-data/cross-export
attack. Generic validation/qualification flags remain visible without exact counts.
Unknown/custom finding text is kept local until an explicit safe projection exists.
Old artifacts already shared cannot be recalled or repaired in place. Historical
population IDs/findings need reevaluation, not guessed reconstruction. Capacity
ceilings, real production usefulness and founder acceptance remain unestablished.
No additional unresolved defect in the three requested correction areas was found
by these checks; independent review remains necessary.
