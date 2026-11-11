# CG4 reviewer quickstart

**Preparation in progress.** This file is the reproduction entry point for the
eventual technical-review ZIP. Its existence is not a delivery or qualification
claim. Read `IMPLEMENTATION_STATUS.md`, `CG4_IMPLEMENTATION_FINDINGS.md` and
`docs/CG4_CONFIDENCEGUARD.md` first. Failed methods and unqualified envelopes remain
explicit; preparing an archive does not constitute independent review or acceptance.
Latest runtime source is
`c974f15f6b9644fb4f7ed94434c1ee829cb337fd131fff33bff70974ad3eaf7f`,
with a confirmation work-admission correction. See
`results/verification/work-admission-v106-manifest.json`: 15 focused checks, 20
caller/retry/report checks and seven affected checks each on Python 3.12/3.14.
Numerical interval kernels are unchanged. The v96 wheel described below predates
this correction; rebuild and clean-install the final wheel before delivery. No
current-wheel or complete-current-suite claim is inferred from older receipts.
The latest coherent boundary is source
`7d74efcb284f5bae24f4aef4359eef898f9ace83b179014a8059b537bcf246c1`
with 271 passing CG4 tests. The v96 wheel SHA-256 is
`57584f9dc9ce5198844d7e230bfc2cb954acffc21bff0cc451bdad157845c4ea`;
all 196 runtime/static files match its fresh 83-distribution installation. See
`results/verification/entity-arm-v97-manifest.json` for installed checks, cross-runtime
checks and actual browser/HTML/JSON/PDF evidence. Read `ENTITY_ARM_FINITE.md` before
using the new narrow finite entity design. It does not repair the failed general
cluster/unbounded-mean procedures. All wheels below are development boundaries;
the final review ZIP remains outstanding.
The 19 installed product/correction checks passed without a source-tree override.
The v44 and corrected paired-precision v53 installed-wheel reproductions below
are recorded earlier-boundary evidence. The later selector revision requires a
refreshed final wheel and installation check; no final delivery is claimed here.
The current v61 wheel has a new 83-distribution installation, exact 196-file parity,
28 installed checks and the three-strategy v63 reproduction, with actual tar/CLI
restore and all 19 PDF pages checked. See
`results/verification/selector-installed-reproduction-v66-manifest.json`.
Required method qualification and final ZIP extraction remain separate.

Later correction source
`587d12d2bee5fe896f5f071c41e3f3961164b07ea81e33f02d8f33bb9846e980`
passed 259 CG4 tests. Its v83 wheel (SHA-256
`0bd3be6e39678b7fb98ec17be316e4674388984400caccd18861ef2fc7e9563f`)
passed ten clean installed correction checks with 196-file parity. It includes
pre-H method refusal, the versioned R2 proposal correction, and extended-uncertainty
relation/registration fixes. See
`results/verification/admission-r2-closure-v85-manifest.json`. This is a corrected
development wheel, not final milestone delivery. The earlier v61 report/backup
reproduction keeps its original identity; unchanged evidence is reused in scope.

Use standard GIL-enabled CPython 3.12 or 3.13, with 3.13 as the primary qualification
runtime. Choose the exact interpreter/platform lock in `constraints/`. Python 3.14
has a capability-specific matrix, including a separate encoder identity. A resolved
Linux/Windows lock is not evidence of executed product support. PDF authoring also
requires the recorded native libraries/fonts; existing PDF files remain readable
without authoring dependencies. Model weights and dataset downloads are excluded.
Legacy test-import helpers and required synthetic/accepted CG1 fixtures are
included. Original DataTrust public-table checks such as `verify_all` still require
their pinned external inputs under `validation/data/prepared`; acquisition code is
included, and those data-dependent checks are not claimed to run without inputs.
Use a separate working copy for optional dataset/model acquisition so the extracted
review payload retains its original manifest. Recorded optional-model evidence does
not authorize model downloads or imply the excluded weights are packaged.

From the extracted review root, verify payload integrity before installation:

```sh
python3 -B validation/cg4/review_inventory.py --root .
```

Create the review environment outside the extracted payload, preserving its
manifest. On qualified macOS ARM64/Python 3.13, for example:

```sh
python3.13 -m venv /ABSOLUTE/NEW/cg4-review-environment
/ABSOLUTE/NEW/cg4-review-environment/bin/python -m pip install --require-hashes -r constraints/cg4-macos-arm64-py313.lock
/ABSOLUTE/NEW/cg4-review-environment/bin/python -m pip install --no-deps wheel/datatrust-0.1.0-py3-none-any.whl
/ABSOLUTE/NEW/cg4-review-environment/bin/python -m pip check
/ABSOLUTE/NEW/cg4-review-environment/bin/confidenceguard investigation --help
```

Hashed locks freeze dependencies, not the local project wheel. The wheel is covered
by the review manifest and `evidence/wheel-runtime-parity.json`. Use the separately
published ZIP checksum to verify the original archive; the manifest deliberately
does not hash itself. Source installation is available for inspection, but clean
reproduction must record whether imports came from the wheel or an explicit source
snapshot. Do not allow an editable installation to silently replace either.

To reproduce the source-only wheel build, use a separate build environment with
`constraints/build-python.lock` (setuptools, wheel and packaging), then run
`validation/cg4/build_review_wheel.py --out /ABSOLUTE/NEW/wheel-build`.
The builder refuses prior outputs and records exact source bytes/build tools;
it does not reuse generated egg-info or install project dependencies. A build
does not replace the separate wheel installation and product reproduction checks.

Start with narrow correctness/provenance checks:

```sh
/ABSOLUTE/NEW/cg4-review-environment/bin/python -B -m pytest --import-mode=importlib -q tests/cg4/test_objective_bindings.py tests/cg4/test_confirmation.py tests/cg4/test_reconciliation.py tests/cg4/test_history.py
```

The repository Verification skill is packaged at `agents/skills/verify/skills.md`.
`QUALIFICATION_MATRIX.md` separates current source checks, prior-profile evidence,
new campaigns and unresolved method requirements.
Reuse unaffected recorded campaigns; a fresh reproduction is new computation, not
new independent confirmation of an already exposed population. Do not replace a
locked qualification panel with favorable development seeds or silently change its
source, budget, family, method or acceptance target.

Read-only qualification audits can inspect saved experiments without rerunning them:

```sh
/ABSOLUTE/NEW/cg4-review-environment/bin/python -B validation/cg4/summarize_recovery.py --directory validation/cg4/results/recovery-remaining-group-v2/categorical_numeric_conjunction --out /ABSOLUTE/NEW/categorical-audit.json
/ABSOLUTE/NEW/cg4-review-environment/bin/python -B validation/cg4/summarize_gate_diagnostics.py --directory validation/cg4/results/recovery-remaining-group-v2/categorical_numeric_conjunction --out /ABSOLUTE/NEW/categorical-diagnostics.json
```

Verified `source-capsules.nosync/<identity>` directories contain historical source,
not virtual environments or model caches. Their names/byte hashes bind long-running
campaigns to the actual implementation used. `results/verification` inventories and
linked raw trial files preserve failures and changes of method. Pooled overlapping
gate counts are not independent trials; original H measurements cannot select a
new gate. Simulations diagnose errors and qualification limits, not arbitrary-
distribution guarantees. Matching SciPy establishes numerical agreement only.

Fresh selector qualification is expensive and normally follows the read-only
audits. To reproduce its fixed sequence from the delivered source capsule, use
new output directories and the chosen review interpreter:

```sh
/ABSOLUTE/NEW/cg4-review-environment/bin/python -B validation/cg4/run_locked_qualification.py --python /ABSOLUTE/NEW/cg4-review-environment/bin/python --source-identity 59f6784386f6a7b1db909ddb59f564f5154283198175d2c8f32cf0489078955c qualify_pipeline.py --panel recovery_qualification --archetype broad_moderate_and_narrow_severe --count 40 --workers 4 --out /ABSOLUTE/NEW/broad-panel
/ABSOLUTE/NEW/cg4-review-environment/bin/python -B validation/cg4/run_selection_campaign.py --source-identity 59f6784386f6a7b1db909ddb59f564f5154283198175d2c8f32cf0489078955c --broad-directory /ABSOLUTE/NEW/broad-panel --out /ABSOLUTE/NEW/selector-campaign
```

The driver forwards that actual interpreter, audits the complete first panel,
then runs the remaining panels serially with at most four seed subprocesses per
panel. It refuses changed profiles/records and stops on failed acceptance; it
does not weaken targets, launch replacement seeds or imply qualification success.
Resumed computation on the same fixed observations is not fresh statistical evidence.

`results/review-adversarial-fixtures-v1` deliberately contains unsafe archive-entry
metadata retained as negative evidence. Inspect it with the packaged tests/ZIP
reader; do not extract those nested fixtures. The outer review archive has its own
separate manifest/path checks.

Canonical local/shareable HTML/PDF/JSON and the portable selective-outcome fixture
are under `validation/cg4/results/`. Protected synthetic artifacts remain sensitive
in structure even though they contain no customer evidence. Exact aggregate
authorization does not authorize learned-model or membership disclosure. The
separately verified synthetic backup will be at `examples/synthetic-backup.tar.gz`.
Its installed-wheel reproduction is recorded in `results/review-reproduction-v45/`:
all three discovery strategies, supplied vectors, JSONL/Parquet/NPY retention,
known-exposure refusal, immutable assessment/family restore and canonical reports.
The fixture is deterministic and previously exposed; it cannot demonstrate fresh
statistical confirmation. Restore preserves evidence but cannot prove no later use.
The corrected paired-precision variant is separately retained in
`results/review-reproduction-paired-v55/`, built from the v53 wheel. It checks a .5
adverse precision difference with distinct 120/60 conditional denominators and the
same exposure/immutable-restore controls. Neither reproduction uses the later
selector. To run that fixture with the delivered wheel, add
`--objective paired_precision` to the reproduction command below.
The current-selector reproduction is in `results/review-reproduction-selector-v63/`.
Fifteen raster pages exactly matched the earlier inspected reports; four changed
pages were inspected anew. Exact source/runtime and page-reuse evidence is recorded,
not inferred from a successful renderer exit.

These extraction/restore commands have been exercised with the installed wheel;
choose new destinations outside the extracted review payload:

```sh
/ABSOLUTE/NEW/cg4-review-environment/bin/python -m tarfile --extract examples/synthetic-backup.tar.gz /ABSOLUTE/NEW/backup-extract --filter data
/ABSOLUTE/NEW/cg4-review-environment/bin/confidenceguard workspace --path /ABSOLUTE/NEW/restored-workspace restore --backup /ABSOLUTE/NEW/backup-extract/synthetic-backup
/ABSOLUTE/NEW/cg4-review-environment/bin/python -B validation/cg4/reproduce_review.py --require-wheel --out /ABSOLUTE/NEW/cg4-reproduction
```

Inspect the archive manifest and its recorded regular-file/path checks first.
The original verification archive is also retained under the reproduction results;
the final ZIP will copy it to `examples/`. The last command creates fresh local
synthetic artifacts and never overwrites a prior run. `--require-wheel` refuses
source-tree/editable imports. New reports require the native PDF libraries/fonts
and their own visual inspection; existing reports remain readable without them.
The earlier v44 clean installation has 83 compatible distributions, 196 runtime/static
files byte-equal to the wheel/source, and 19 focused contract/provenance/history
checks passed. These are scoped engineering evidence, not final ZIP extraction
reproduction or closure of the unresolved approximate-inference qualification.

Independent review of the ZIP, review of findings, founder-authorized corrections,
focused correction verification, the understanding gate and founder acceptance
remain subsequent stages. None is completed by the commands above.
