# DataTrust V1 Validation Corpus

This workspace is separate from `src/datatrust/`. It prepares public validation
data, creates deterministic controlled mutations, generates DataTrust reports,
records runtime evidence, and runs one internal adjacent-tool comparison.

Prepared CSVs and reports are validation evidence only. They are not runtime
package inputs or dependencies.

## Public Sources

- UCI Statlog German Credit, DOI: https://doi.org/10.24432/C5NC77
- UCI Bank Marketing, DOI: https://doi.org/10.24432/C5K306
- UCI Adult, DOI: https://doi.org/10.24432/C5XW20

All three UCI pages identify the datasets as CC BY 4.0. Exact source URLs,
archive names, and pinned checksums live in `sources.json`.

## Reproduce

From the repository root:

```bash
/opt/homebrew/bin/python3.10 -m venv .venv
.venv/bin/python -m pip install --upgrade pip setuptools wheel
.venv/bin/python -m pip install --no-build-isolation -e ".[dev]"
.venv/bin/python -m validation.prepare --download
.venv/bin/python -m validation.mutate
.venv/bin/python -m validation.run_validation
```

Once archives exist in the ignored `validation/data/raw/` directory, preparation
can run offline and validates the pinned archive checksums:

```bash
.venv/bin/python -m validation.prepare
```

## Outputs

- `data/prepared/`: semantic-column public validation CSVs and manifest
- `data/mutations/`: controlled Adult mutations and manifest
- `reports/`: complete eight-section DataTrust HTML reports
- `results/runtime_measurements.csv`: report-generation timings
- `results/mutation_assertions.json`: expected directional behavior
- `results/leakage_review.csv`: every leakage flag, reason, and reviewed classification
- `results/validation_summary.json`: machine-readable run summary

## Isolated Evidently Comparison

The project and validation environments use Python 3.10 or newer. Evidently is pinned in
its own environment and is never added to DataTrust runtime dependencies.

```bash
/opt/homebrew/bin/python3.10 -m venv validation/.venv-evidently
validation/.venv-evidently/bin/python -m pip install --upgrade pip
validation/.venv-evidently/bin/python -m pip install -r validation/requirements-evidently.txt
validation/.venv-evidently/bin/python validation/evidently_compare.py
.venv/bin/python -m validation.verify
```

The comparison is internal supporting evidence only. It is not a V1 pass gate.

## Historical Milestone 3 / RC_003 Review Materials

The separate `dry_runs/` workspace contains the historical RC_003 technical
review materials: cross-platform reviewer quickstart, manual-first
template, technical and non-technical evidence forms, facilitator protocol,
objective pass/fail rules, superseded practitioner evidence template,
allowlist-only clean reviewer packet tooling, and deterministic
release-candidate identification tooling.

RC_003 and its packet are preserved as historical evidence. These commands show
how the candidate was originally produced; they are not active V1 blockers or
future review requirements:

```bash
.venv/bin/python -m validation.dry_runs.reviewer_packet create \
  --id DRY_RUN_RC_003_REVIEWER_PACKET
.venv/bin/python -m validation.dry_runs.release_candidate create \
  --id DRY_RUN_RC_003 \
  --packet-manifest validation/dry_runs/packets/DRY_RUN_RC_003_REVIEWER_PACKET.manifest.json
.venv/bin/python -m validation.dry_runs.verify
```

Archive verification does not run or simulate human reviews. Completed or
returned evidence belongs under `dry_runs/evidence/` and must never contain
private datasets, private row values, or sensitive screenshots.

The old reviewer packet excluded existing reports, validation results and
comparisons, internal project docs, previous evidence, tests, examples, and
virtual environments. Future product development is reviewed internally by
Drivyaansh and Codex unless Drivyaansh separately requests outside feedback.
