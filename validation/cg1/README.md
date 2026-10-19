# CG1 engineering evidence

Recorded 2026-10-17–18 under the repository's proportional Verification skill.
This is internal correctness, compatibility and workflow evidence. It does not
establish product usefulness, production readiness, fairness, certification,
population representativeness or a capacity ceiling.

## Executed and reused checks

- Full repository suite: **526 passed**, six dependency deprecation warnings,
  about 60 seconds. Use `--import-mode=importlib`: pre-existing M6/M9 test filenames
  otherwise collide during collection. Subsequent CG-only closure additions were
  checked separately: **27 CG1 tests passed** in about six seconds. The final
  unavailable-value presentation adjustment also passed the affected three
  interface/artifact checks. Existing DataTrust engines were not changed.
- Existing `validation.verify` and `validation.dry_runs.verify` passed, preserving
  corpus/historical checksums. Unchanged expensive modality qualification and
  capacity experiments were not rerun.
- Independent scikit-learn references: **24 metrics** across two pinned predictors
  for each of German Credit (binary), Wine (multiclass) and Concrete (regression).
  Sources/prepared predictions, seed, package versions, disjoint fit/calibration/
  evaluation splits, their hashes and expected values are recorded in
  [results/reference.json](results/reference.json). Development predictors do not
  ship as model adapters. Subsequent reference checks reuse those fitted prediction
  fixtures, without fitting again.
- Draft202012 JSON Schemas, synthetic requests/responses and completed exact/
  shareable results validated using a development-only jsonschema target.
  [results/closure.json](results/closure.json) records current analytical runs;
  [results/reports.json](results/reports.json) identifies the final PDF exports.
  A final decimal-endpoint conversion correction passed all 27 focused checks and
  all 24 independent references; reports from unchanged valid prediction values
  retain their earlier verification. OpenAPI and schemas are included in the wheel.
- Live loopback browser: registered local prediction sources, configured and ran
  binary paired/cohort/probability-threshold evaluation; resolved an original row
  without revealing values; created conservative exports. A concurrent export
  request correctly returned `worker_busy`. Multiclass probabilities/abstention
  and regression points/interval-width abstention completed through the same JSON
  workflow. Complete measurement records expand in the client. A confirmation
  made stale by ongoing implementation changes was rejected and refreshed.
  HTTP tests additionally cover uploads, reopening, cancellation, revisions,
  idempotency, wrong-session access, JSON CSRF and unchanged legacy form CSRF.
- Six canonical PDFs, exact and shareable across all three tasks, were rendered
  and **all 83 pages** visually reviewed through page contact sheets. Tables,
  graphs, continuation pages, sparse evidence and withholding variants were
  examined. A misleading structured/unavailable display label was corrected and
  the affected page re-rendered. PDF text checks found no empty pages; portable
  artifacts omit source paths/private references. Final hashes and page counts:
  [results/reports.json](results/reports.json). Exports reuse completed evidence.
- Distribution wheel built without new runtime dependencies; both console entries
  and all static/report/schema assets were verified. Existing distribution name
  and `datatrust` entry point are preserved.

Focused cases cover representations and decision provenance, underflow/zero
probabilities/infinite differences, ties and native score directions, abstained
latent output, selective/unavailable labels, exact Parquet identities, authoritative
outcome conflicts, temporal cutoffs/horizons, canonical context conflicts, matched
ranking/interval populations, repeated entities/Wilson qualifications, cohort
limits/residuals, joint disclosure, bound manifests, source mutation, artifact
collisions and surviving exports after PDF failure.

## Measured resources

| Probe | Shape / setting | Complete evaluate + HTML/JSON | Peak sampled RSS | Peak workspace |
|---|---|---:|---:|---:|
| Ordinary binary | 10,000 rows / 2 classes; 256 MiB DuckDB | 10.5 s | 173 MiB | 19.7 MiB |
| Wide, spill-relevant | 8,000 rows / 48 classes; 64 MiB DuckDB | 9.6 s | 229 MiB | 38.4 MiB |

Neither probe produced observed spill. Exact protected results were approximately
35 KiB/164 KiB; shareable projections 22 KiB/145 KiB; HTML about 19 KiB. These are
measured shapes on this machine, not evidence that 100-million-cell admission or
other configured maxima will complete. The source-to-DuckDB Python normalization
cost remains a scaling consideration. See [results/resources.json](results/resources.json).
Actual spilling and large natural production workloads remain unverified by these
CG-specific probes; established shared supervisor/spill tests remain reused evidence.

## Reproduce proportionately

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:. .venv/bin/python -B -m pytest --import-mode=importlib -q -p no:cacheprovider
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:. .venv/bin/python -B -m validation.verify
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:. .venv/bin/python -B -m validation.dry_runs.verify
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:. .venv/bin/python -B -m validation.cg1.resources
```

`reference.py` uses development-only scikit-learn 1.7.2, numpy 2.4.6, scipy 1.17.1
and jsonschema 4.23.0, installed in an isolated temporary target rather than added
to runtime dependencies. It fits deterministic reference predictors and writes
pinned CSV/specification fixtures. `verify.py` needs only development jsonschema
beyond the project environment; it validates schemas and compares current engine
outputs to the recorded independent values. Add `--pdf` to create representative
reports, optionally `--out` with a **new** output directory. Existing report files
are never overwritten. Running verification is optional maintenance, not a required
ceremony after unrelated changes.

`browser_server.py` is a development-only loopback host on port 8031 with the
fixture directory as its allowed root. It is not installed in the distribution.
Private bundles and rendered QA images are ignored; public prediction fixtures,
reports and evidence ledgers are retained. No source corpus or offline predictor
artifact is embedded in the shipping package.
