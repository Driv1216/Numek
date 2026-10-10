# DataTrust Validation Corpus

Last updated: 2026-10-09

This workspace is separate from `src/datatrust/`. It prepares public validation
data, creates deterministic controlled mutations, generates DataTrust reports,
records runtime evidence, and runs one internal adjacent-tool comparison.

Prepared CSVs and reports are validation evidence only. They are not runtime
package inputs or dependencies.

M1 internal unlabeled validation lives separately under `unlabeled/`:

```bash
PYTHONPATH=src .venv/bin/python -m validation.unlabeled.verify
```

It checks analytically known synthetic evidence and temporary label-free views
of the three pinned prepared tables. It does not regenerate classification or
historical reports. Label-free views are derivations, not unlabeled ground truth.
These fixtures and regression checks provide internal correctness evidence;
external methodology validity and customer usefulness remain unestablished.

## Public Sources

- UCI Statlog German Credit, DOI: https://doi.org/10.24432/C5NC77
- UCI Bank Marketing, DOI: https://doi.org/10.24432/C5K306
- UCI Adult, DOI: https://doi.org/10.24432/C5XW20

All three UCI pages identify the datasets as CC BY 4.0. Exact source URLs,
archive names, and pinned checksums live in `sources.json`.

## Reproduce

From the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
python -m validation.prepare --download
python -m validation.mutate
python -m validation.run_validation
```

Once archives exist in the ignored `validation/data/raw/` directory, preparation
can run offline and validates the pinned archive checksums:

```bash
python -m validation.prepare
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
python3 -m venv validation/.venv-evidently
validation/.venv-evidently/bin/python -m pip install --upgrade pip
validation/.venv-evidently/bin/python -m pip install -r validation/requirements-evidently.txt
validation/.venv-evidently/bin/python validation/evidently_compare.py
python -m validation.verify
```

The comparison is internal supporting evidence only. It is not a product acceptance gate.

## Historical RC_003 Review Materials

The separate `dry_runs/` workspace contains the historical RC_003 technical
review materials: cross-platform reviewer quickstart, manual-first
template, technical and non-technical evidence forms, facilitator protocol,
objective pass/fail rules, superseded practitioner evidence template,
allowlist-only clean reviewer packet tooling, and deterministic
release-candidate identification tooling.

RC_003 and its packet are preserved as historical evidence. These commands show
how the candidate was originally produced; they are not active blockers or
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

## M2 Regression Intelligence

`regression/` is a separate namespace; no historical classification/dry-run or
unlabeled artifacts are regenerated. It pins UCI Concrete Compressive Strength
(1,030 × 9 prepared columns, eight inputs, strength in MPa) and Bike Sharing
hour (17,379 × 17) / day (731 × 16), with count target `cnt`. Actual dimensions
come from pinned files. DOI/license/publication attribution and URLs live in
`regression/sources.json`; archive/member/prepared hashes, header conversions,
versions, declarations, and derived controls live in `regression/manifest.json`.

Both Bike tables verify `cnt = casual + registered`. Positive views retain the
components and explicitly declare forecasting-before-outcome availability.
Controls remove only these two components. Calendar/weather association is not
leakage evidence; date columns imply no time-series analysis. Concrete XLS-to-CSV
conversion preserves all observations and uses `xlrd` only during preparation.

```bash
.venv/bin/python -m pip install -r validation/regression/requirements.txt
PYTHONPATH=src .venv/bin/python -m validation.regression.prepare  # pinned local archives
# Add --download only if archives are missing.
PYTHONPATH=src .venv/bin/python -m validation.regression.mutate
PYTHONPATH=src .venv/bin/python -m validation.regression.verify
# Explicitly refresh only owned regression HTML/JSON evidence:
PYTHONPATH=src .venv/bin/python -m validation.regression.verify --write-artifacts
```

Verification works offline once sources are pinned; it validates archives,
members, prepared/mutated inputs, and owned report checksums. Thirteen controlled
cases cover copies/affine identities/sums, sparse support, missing/infinite
outcomes, constants, constraint unions, ordinary decimal precision, heavy tails,
skew, bounded targets, zero-inflated counts, and repeated measurements. The
pytest regression suite additionally exercises numerical reference calculations,
threshold boundaries, false positives, interruptions, interfaces, and artifact safety.

`regression/results/verification.json` records analytical timing, measured frame
memory, environment, comparison work, assertions, and artifact hashes. The internal
30-second engineering target excludes PDF conversion and is not a capacity guarantee.
Browser/PDF presentation evidence lives separately under `regression/results/`.
Six PDF cases contain 76 visually inspected pages; the presentation manifest
records canonical HTML hashes, source snapshots/configuration, PDF hashes, page
dimensions, and rendered contact-sheet hashes. Synthetic presentation inputs are
pinned under `regression/data/presentation/`; report paths retain their original
temporary analysis location. The browser manifest records screenshots from the
real local workflow. Offline verification also checks these evidence hashes.
A partial QA case injects an optional diagnostic failure only in an isolated test
server; no runtime fault-injection setting is shipped. These checks establish
internal implementation correctness, not external method validity or usefulness.

## M3 Tabular Annotation Intelligence

[M3 validation](m3/README.md) pins Energy Efficiency, Scene, and official-release
Linnerud sources with independent vector/pair/numerical mathematics, controlled
annotation masks, conditional feature-only readiness cases, empty supervision,
wide-report budgets, real browser checks, and complete PDF visual inspection.

```bash
PYTHONPATH=src .venv/bin/python -m validation.m3.verify
```

Its separate artifacts preserve all existing historical reports and hashes.

## M4 comparative and scalable local analysis

[M4 validation](m4/README.md) reuses all seven pinned task-family datasets, checks
independent scalable mathematics and controlled comparative/advanced cases, exercises
real browser flows and completed downloads, and records all-page PDF inspection.
Its namespace includes 1/5 GiB combined-input measurements, a spill-heavy 512 MiB
join/group job, a 32 MiB exact external-sort check and a retained allocation failure.
Historical artifacts remain unchanged. Objectives describe measured workloads and
do not guarantee runtime, RSS, disk or arbitrary dataset capacity.
