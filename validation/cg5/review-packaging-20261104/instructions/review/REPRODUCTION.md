# Integrity, environment and optional reviewer reproduction

## Verify before execution

Compare the ZIP SHA-256 with the separately delivered checksum. Extract into a
new empty directory using an archive tool that rejects traversal, symlinks and
special files. The supplied standard-library verifier can then check the archive
again, including an isolated temporary safe extraction:

```sh
python3 -B validation/cg5/package_review.py --verify /ABS/PATH/NUMEK_ConfidenceGuard_CG5_Independent_Technical_Review_20261104.zip
```

[MANIFEST.json](../MANIFEST.json) covers every payload file except itself; the
external checksum covers the complete archive, including that manifest. Do not
edit the delivered snapshot. Make a separate working copy for reviewer changes or
fresh outputs. [Packaging scope](PACKAGING_SCOPE.md) explains historical reference
exceptions and excluded local environments.

## Runtime and dependencies

The executed primary environment is standard CPython **3.13.17**, NumPy **2.4.6**,
SciPy **1.18.1**, bundled HiGHS **1.12.0**, macOS arm64. Python >=3.12 is required.
CG5 MILP admission is narrower than the distribution's compatible SciPy range:
an unregistered solver pair is unavailable, not silently substituted. Optional
models/weights are not installed by CG5. Supplied/offline upstream artifacts are
required; fitting and CG4 rediscovery are outside a policy operation.

For a reviewer choosing to install, use a new environment and the matching lock:

```sh
python3.13 -m venv /tmp/numek-cg5-review
uv pip sync --require-hashes --python /tmp/numek-cg5-review/bin/python constraints/cg4-macos-arm64-py313.lock
uv pip install --no-deps --python /tmp/numek-cg5-review/bin/python wheel/datatrust-0.1.0-py3-none-any.whl
uv pip check --python /tmp/numek-cg5-review/bin/python
```

Those commands are instructions, not installation executed during CG5 packaging.
Use distinct paths if they already exist. Dependencies may require registry access;
environments, package caches and model weights are deliberately not vendored.
Other platform locks preserve resolution context; they do not establish executed
CG5 platform support. Native PDF libraries/fonts are required only for authoring;
existing reports can be inspected without regenerating them. The recorded macOS
native-library setting was `DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib`.

## Existing results first

Read the [verification record](../validation/cg5/VERIFICATION.md),
[executed/reused evidence guide](EVIDENCE_GUIDE.md) and final reports before running
anything. Supplied evidence contains historical absolute paths. Reopening data
objects does not require replay; original evidence resolution or analytical
reproduction may require explicitly binding packaged synthetic sources in a new
working/output directory. Do not edit sealed results to rewrite their paths or
pretend packaged outcomes are fresh independent product evidence.

## Optional tests and fresh synthetic engineering outputs

From a separate extracted working copy, the recorded broad test selection is:

```sh
PYTHONPATH=src:. /tmp/numek-cg5-review/bin/python -B -m pytest --import-mode=importlib \
  tests/cg1 tests/cg2 tests/cg3 tests/cg4 tests/cg5 \
  tests/test_app_api.py tests/test_app_default.py tests/test_web.py -q
```

Use [the verification skill](../agents/skills/verify/skills.md): inspect valid
existing evidence and choose checks based on changes or a concrete uncertainty.
No broad rerun is required merely to read the archive. Focused CG5 checks use
`tests/cg5`; Node must be on PATH for the retained browser JavaScript checks.
A separate schema environment can use
[the schema lock](../constraints/schema-verification-macos-arm64-py313.lock):

```sh
python validation/cg4/qualify_schemas.py --out /ABS/NEW/schema-cg1-cg4.json
python validation/cg5/qualify_schemas.py --out /ABS/NEW/schema-cg5.json
```

For an explicitly chosen fresh synthetic engineering run, the delivered fixtures
and harnesses can write to new destinations:

```sh
PYTHONPATH=src python -B validation/cg5/measure.py --out /ABS/NEW/cg5-workloads
PYTHONPATH=src python -B validation/cg5/finite_diagnostics.py --out /ABS/NEW/cg5-fixed-diagnostics
```

These create engineering examples, not new scientific method qualification or
independent acceptance. Do not run old automatic qualification campaigns simply
because their scripts are included. Do not overwrite immutable completed reports.
The [transport examples](../validation/cg5/examples/) require owned source handles;
use service fixture constructors or register files through the local API/browser.
No client request may supply workspace/scratch/output paths or arbitrary solver options.
