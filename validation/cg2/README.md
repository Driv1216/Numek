# CG2 engineering evidence

Implementation/qualification: 2026-10-19. This directory is new CG2 evidence;
`validation/cg1` and accepted DataTrust history are preserved. The user's CG1
acceptance and closed understanding gate are authoritative. No CG2 understanding
gate, external reader validation, production-capacity certification or universal
method improvement is claimed.

## Executed checks

- Repository suite, required import mode, normal virtual environment:
  **567 passed, 1 skipped**, 91.70 s. The development JSON Schema test skipped
  because its validator was outside that environment; it separately passed when
  the development path was appended without replacing pinned runtime packages.
- Subsequent affected CG2 checks: **29 passed, 1 skipped** (38.23 s), followed by
  focused ancestry/cohort checks. The final CG2 run passed **34 tests, 1 skipped**
  (45.20 s); the schema skip is covered by executed development validation.
  A preceding combined CG1/CG2 run passed **70 tests, 1 skipped** (47.72 s).
  Exact later closure results are recorded in the closure ledger below.
  These are additional affected checks, not a claim that
  the earlier suite ran on later source revisions.
- An initial broad run with a global development directory ahead of the virtual
  environment passed 564 tests and failed four M7 interface checks at pinned
  dependency admission. The first affected M7 test passed after removing that
  directory; the complete normal-environment suite then passed as above.
  No DataTrust code was changed to bypass those checks.
- [Independent qualification](results/final-20261019/verification.json): **38**
  fitting/metric references across binary, multiclass and heteroscedastic regression;
  JSON Schema requests/results/fitted artifacts/assessments; exact reopening;
  canonical local/shareable HTML/JSON/PDF exports.
- Six conformal experiments, **1,200 independent calibration/future trials each**,
  score-specific marginal coverage, efficiency, and Monte Carlo qualified
  undercoverage checks. No universal algorithm superiority test.
- Bootstrap experiments: **160 fresh datasets per design**, 2,500 paired BCa
  replicates. IID and cluster procedures each covered the known effect in 148/160
  trials (92.5%, all intervals available; one-sided undercoverage p=0.1063).
  The deliberately invalid IID-on-dependent-events control covered 95/160 (59.4%).
  These are finite simulation results, not exact confidence-interval accuracy
  guarantees. Availability/refusal is recorded separately.
- [Compatibility](results/history-compatibility-20261019.json): **437** unchanged
  DataTrust source, CG1 test and CG1 historical files relative to the captured
  implementation-start snapshot; all **24** pinned CG1 metric references pass;
  **24** protected legacy bundles reopen. Existing corpus and historical dry-run
  archive verifiers pass. The CG1 reference fitting/generation scripts were not
  rerun and historical artifacts were not rewritten.

Independent references use sklearn sigmoid/isotonic/ranking routines, separate
finite-difference beta/Dirichlet objectives, independent scalar temperature fitting,
manual pinball/WIS formulas and a quadratic empirical-CRPS oracle. Reference tools
are development dependencies, not product execution dependencies. Runtime/dependency
versions, seeds, source hashes and resource records are in the JSON ledger.

Tests exercise safe tagged unbounded thresholds, signed CQR/empty outputs,
nonfinite/overflow rejection, exact decimal ranks, frozen candidate intersections,
failed candidates without population renegotiation, E-label noninterference,
same-base comparisons, cluster units/event weighting, adjusted-tail/work admission,
degenerate bootstrap refusal, sidecar binding/overlap/ancestry, state transitions,
safe loaders, cancelled/no-replace application exports, ownership, CLI/API parity
and historical reopening. Synthetic fixtures execute no base predictor.

## Measured resources

[Ordinary/wide/sample/adjusted probes](results/resources-final-20261019/resources.json)
use 1,200 supplied events with 300 events per F/S/C/E role. Measured values on this
machine, under concurrent verification load:

| Probe | Worker time | Peak sampled RSS | Peak workspace |
|---|---:|---:|---:|
| Binary calibration/selection/LAC | 5.31 s | 280 MiB | 18.5 MiB |
| 24-class temperature/Dirichlet/APS/RAPS | 7.45 s | 318 MiB | 26.5 MiB |
| Regression, 200 samples/event | 56.97 s | 238 MiB | 57.3 MiB |
| Two Bonferroni contrasts, B=4,000 | 2.73 s | 218 MiB | 16.9 MiB |

[Exact-sort spill and resource stop](results/spill-20261019/resources.json):
10 million finite scores, shared supervised workspace, 32 MiB DuckDB limit;
**91,193,344 bytes observed spill**. This isolates CG2's exact order-statistic
reducer rather than claiming full ten-million-row end-to-end fitting capacity.
A separate 32 MiB RSS stop published no completed result. The first spill probes
reported zero because the isolated probe omitted the owned-workspace progress
notification used by the supervisor; that measurement defect was fixed and the
actual probe rerun. Both successful ordinary evidence and failed probe records
remain in their original generated directories.

RSS and storage controls are sampled and may overshoot. These settings and small
workloads are operating evidence, not capacity or speed promises.

## Browser, reports and packaging

Live loopback browser checks exercise guided binary calibration selection plus
LAC, regression scale/quantile/sample bindings, confirmed studies, evidence states,
matched comparisons and owned exports. API/CLI tests separately cover reapplication
as unvalidated, method import/ownership, cancellation, revisions and collisions.
The browser contains no statistical implementation.

Canonical PDFs were generated for local and shareable audiences for all three
task families. Selected PDF QA renders every page of binary/multiclass shareable
and regression local reports; visual inspection covers pagination, repeating table
headers, wrapping, plots and limitations. PDF QA revealed a cohort-support display
problem, corrected in the evaluator and leading report comparison table. Re-exports
consume completed evidence only. Fontconfig emitted cache-directory notices, but
PDF conversion and page rendering completed.

The source wheel builds and includes the CG2 Python modules, method client,
canonical template, contract/OpenAPI/example JSON, existing commands and optional
`statistics` dependency. No new dependency or framework was installed during this
implementation. See `results/closure-ledger.json` for the final source/packaging,
browser and PDF review records and exact later affected test counts.

## Reproduction

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:. .venv/bin/python -B -m pytest --import-mode=importlib
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:. .venv/bin/python -B -m validation.cg2.verify --out /tmp/cg2-new-evidence --reference-path /path/to/development/site-packages --pdf
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:. .venv/bin/python -B -m validation.cg2.resources --out /tmp/cg2-new-resources
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:. .venv/bin/python -B -m validation.verify
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:. .venv/bin/python -B -m validation.dry_runs.verify
```

Output directories must be new. Reuse compatible frozen reference and simulation
evidence after presentation-only changes; do not overwrite historical runs or
repeat unrelated model qualification. The authoritative
[Verification skill](../../agents/skills/verify/skills.md) governs proportionate
verification. Earlier qualification directories remain historical executed evidence;
the final ledger distinguishes executed work, reused work and source review.

Remaining limits: declarations cannot reveal undisclosed training leakage or prove
future exchangeability; cluster intervals cannot establish conformal validity;
fixed-artifact inference omits fitting/selection variability; flexible calibration
can overfit; common-input intersections and privacy protection can greatly reduce
published evidence; repeated human inspection of E requires a new independent
evaluation population for subsequent confirmatory claims. Parameters and membership
hashes are sensitive. Large ingestion/optimizer/resampling capacities need measured
workload-specific qualification.
