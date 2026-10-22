# Reviewer quickstart

Use a local filesystem and Python 3.10+ (qualified here on Python 3.11/macOS arm64).
Read `validation/cg3/DECISIONS.md` before interpreting statistical intervals.
The workspace is sensitive local evidence, not encrypted hosted multi-user storage.

From the extracted ZIP root, verify integrity before installing:

```sh
python3 validation/cg3/verify_package.py --root .
python3 -m venv .review-venv
.review-venv/bin/python -m pip install wheel/datatrust-0.1.0-py3-none-any.whl
.review-venv/bin/python -m pip install 'pytest>=7' 'pypdf>=6,<7'
.review-venv/bin/confidenceguard workspace --help
```

Dependencies come from the normal package registry; the wheel contains the full
runtime and static assets. Optional PDF export requires the system libraries used
by WeasyPrint. Existing reports can be inspected without PDF authoring dependencies.
No predictor/model download or execution is necessary for CG3 reproduction.

A focused reproducibility run (new output path, not inside a live workspace):

```sh
.review-venv/bin/python -m validation.cg3.reference --inputs examples/inputs --reports examples/reports
.review-venv/bin/python -m pytest tests/cg3/test_history.py tests/cg3/test_inference.py --import-mode=importlib -q
.review-venv/bin/python -m validation.cg3.reproduce --out /ABSOLUTE/NEW/cg3-example --events 365 --no-pdf
```

The final command intentionally computes a new assessment. Do not expect generated
assessment IDs, clocks, execution measurements or PDF bytes to equal the pinned
example. Deterministic analytical values and explicit populations should agree.
The independent reference checks existing example values without recomputation.

Restore the packaged synthetic workspace (the archive preserves owner-only modes):

```sh
mkdir /ABSOLUTE/NEW/review-example
 tar -xzf examples/synthetic-backup.tar.gz -C /ABSOLUTE/NEW/review-example
.review-venv/bin/confidenceguard workspace --path /ABSOLUTE/NEW/restored restore --backup /ABSOLUTE/NEW/review-example/backup
.review-venv/bin/confidenceguard ui --workspace /ABSOLUTE/NEW/restored
```

Use the one-time launch link printed locally; a clean shell URL or CSRF token alone
does not authorize history. Restore creates a new storage instance while preserving
analytical identities. The backup contains synthetic projected facts and immutable
assessments; original source files are not needed to open them.

`examples/reproduction.json` records expected assessment identities and specifications.
`examples/expected.json` records task/window values and support. `examples/reports`
contains the already generated local/shareable HTML, JSON and PDF artifacts.
`evidence/pdf-contact-sheets` and `evidence/browser` contain visual evidence.
`evidence/logs` and `validation/cg3/results` contain executed verification records.

For a broader reviewer run, use `pytest tests/cg1 tests/cg2 tests/cg3
--import-mode=importlib`. The existing full-suite/compatibility evidence is recorded
in the ledger; repeating unrelated model/modality qualification is unnecessary.
