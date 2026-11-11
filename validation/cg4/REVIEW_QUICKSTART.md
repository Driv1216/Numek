# CG4 technical-review quickstart

This is the CG4 implementation handoff under the founder's 2026-10-28
[accepted closure revision](CLOSURE_SCOPE_REVISION.md). **Initial independent review
is complete. Founder-authorized corrections are recorded in
[REVIEW_CORRECTIONS.md](REVIEW_CORRECTIONS.md); targeted independent re-review,
the understanding gate and founder acceptance remain pending.**
Start with [supported methods](SUPPORTED_METHODS.md), [qualification](QUALIFICATION_MATRIX.md),
[concise findings](CG4_IMPLEMENTATION_FINDINGS.md) and [methodology](../../docs/CG4_CONFIDENCEGUARD.md).
The historical findings and negative experiments are included, with original source
identities and limitations. A resolved lock or a successful build is not method qualification.

## Corrected review delivery — 2026-10-29

The bounded H1/H2/M1/L1/D1 corrections are implemented and internally verified.
Corrected source: `2247a089ba23fe4c2ea19193c867f0b3f5c65152a9aa995d7b4ab56813339095`.
Use the corrected ZIP and wheel identified in [REVIEW_CORRECTIONS.md](REVIEW_CORRECTIONS.md).
The following original identities/evidence remain preserved for comparison.

## Original reviewed delivery identities and scope

- Runtime/source capsule: `2632e65e5b1b98a3902189fd67b441c35cf97b3239ffc36c78faca2f21997ab8`.
- Final wheel: `wheel/datatrust-0.1.0-py3-none-any.whl` in the archive; SHA-256
  `929d864aec8ebbcaed774d54e4ab120ae81577ff21a9eedc3e14f2906c36f3ad`.
- All 196 runtime/static files match the wheel. Documentation/evidence changes
  after the runtime freeze do not create a new numerical method identity.
- `MANIFEST.json` hashes payload files; the external `.zip.sha256` covers the
  archive, including its manifest. `evidence/source-final.json` compares the
  final product inventory with the recorded dirty-worktree baseline.
- `evidence/tracked-working-tree.patch` is the scoped tracked diff from that
  baseline. Required new/untracked files are included as whole files; the patch
  does not attribute all edits to one author. Unrelated frontend labs are excluded.
- [Final closure receipt](results/verification/final-closure-v118-manifest.json)
  indexes current tests, installation/reproduction, PDF/browser proof and reuse boundaries.

The product retains rich evidence, three discovery strategies, supplied/offline
representations, frozen membership, selection/overlap/history, immutable records,
Python/CLI/API/browser/reports, privacy and supervised lifecycle operations.
New formal confirmation supports registered finite procedures under their stated
assumptions. General BCa/cluster/ranking-percentile formal routes refuse before H
metrics; exploratory native evaluation remains. Narrow finite entity arms do not
establish arbitrary cluster inference. Old approximate records remain readable with
current-standing warnings. Scope deferral is not successful qualification.

Five separate locked current-selector synthetic envelopes passed 40/40 each. Other
unfinished current-selector objective/history/geometric panels remain experimental;
landmark promotion failed. Do not run the historical automatic 28-panel controller
as a delivery requirement. The [null bridge](NULL_EVIDENCE_BRIDGE.md) reuses old
simulations through unchanged finite mathematics and focused current isolation/
freezing checks; old rates are not new-selector empirical rates.

## Integrity and clean installation

Use standard GIL-enabled CPython 3.12/3.13; 3.13 is primary. Select the exact
interpreter/platform lock in `constraints/`. macOS ARM64 execution is recorded;
Linux/Windows lock resolution is not executed support. Python 3.14 has explicit
capability boundaries, including original Lingua/Torch-2.8 limitations and a
separate CG4 Torch-2.10 profile. Native PDF libraries/fonts are also required for
authoring; existing reports remain readable without authoring dependencies.

From the safely extracted root, after comparing the external ZIP checksum:

```sh
python validation/cg4/review_inventory.py --root .
python3.13 -m venv /tmp/numek-cg4-review
uv pip sync --require-hashes --python /tmp/numek-cg4-review/bin/python constraints/cg4-macos-arm64-py313.lock
uv pip install --no-deps --python /tmp/numek-cg4-review/bin/python wheel/datatrust-0.1.0-py3-none-any.whl
uv pip check --python /tmp/numek-cg4-review/bin/python
```

Use a new environment/output path when those names already exist. Installation
may need registry access unless the matching locked wheels are cached. If macOS
file cloning stalls, use `--link-mode copy` with uv; pins/hashes are unchanged. No model
weights, environments, credentials or customer evidence are included. Do not
install broad Transformers extras or silently change runtime/model identities.

## Representative product reproduction

Run outside the source tree, with no editable/source import override. Substitute
an absolute extracted-root path for `/ABS/CG4`:

```sh
cd /tmp
PYTHONPATH= DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib /tmp/numek-cg4-review/bin/python -B /ABS/CG4/validation/cg4/reproduce_review.py --require-wheel --objective paired_precision --out /tmp/numek-cg4-reproduction
```

The native-library path shown is the recorded macOS environment; use the declared
platform's corresponding native setup. The script checks site-packages origins,
all three strategies, the .5 paired-precision contrast with distinct 120/60 positive
denominators, known-exposure refusal before H metrics, two canonical report sets,
three durable codecs, and actual immutable backup/restore. It writes a synthetic
backup archive and `verification.json`. This is a product replay, **not independent
statistical confirmation or a new recovery qualification**. The corrected installed-wheel
[reproduction](results/review-reproduction-corrections-final-20261029/verification.json)
and [synthetic backup](results/review-reproduction-corrections-final-20261029/synthetic-backup.tar.gz)
are included, as is `examples/synthetic-backup.tar.gz`. This correction run reused
the previously verified pinned dependencies through an isolated environment; it
does not claim a new clean dependency resolution. Original clean-install evidence
remains under `results/review-reproduction-final-v117/`.

Inspect the existing reports before authoring more. Representative final PDFs were
rendered/page-inspected separately; JSON/HTML are canonical if a local PDF backend
fails. All fixture populations are deliberately declared previously exposed.
A synthetic namespace cannot establish freshness.

## Focused verification and evidence navigation

The original closure recorded 289 passes and one optional development-validator
skip. The corrected candidate records 313 passes / one skip in that coherent
selection, plus seven added boundary regressions: 320 distinct passes covered in total.
The final narrow H1 changes were rechecked with affected history/confirmation
and retained-dependency tests; unchanged suite checks were reused.
All 63 schema checks passed; 33 affected checks passed on each of Python 3.12/3.14
(26 plus three strict-clock additions and four encoder checks). See [correction evidence](results/review-corrections-20261029/)
for test scope and logs. The repeatable primary selection is:

```sh
PYTHONPATH=src python -B -m pytest --import-mode=importlib -q tests/cg4 tests/cg1/test_interfaces.py tests/cg2/test_interfaces.py tests/cg3/test_interfaces.py
```

The test suite uses Flask local services and Node for browser-client contract checks;
Node must be available on PATH or supplied in the recorded test configuration.
Optional JSON Schema validation uses the separate schema-verification lock.

Run tests according to the Verification skill, not automatically after document
changes. No need to regenerate expensive qualification to inspect retained results.
Public-table legacy tests such as `verify_all` require pinned external datasets
under `validation/data/prepared`; authored acquisition/helpers and required accepted
fixtures are included, but external tables and model weights are not redistributed.
Dataset/model acquisition belongs in a separate working copy to preserve payload hashes.

Source capsules are immutable source-only snapshots under
`validation/cg4/source-capsules.nosync/`, deliberately retained despite the suffix;
they contain no environments/model caches. Qualification trial files name their
actual source/profile/seed. Interrupted trials and failed experiments remain;
completed unaffected seeds are reused, not relabeled independent reruns.

The final ZIP integrity/extraction receipt sits beside the archive because an
archive cannot contain its own final checksum. Packaging/extraction verification
completes delivery preparation; it is not an independent technical review.
