# Uninvolved Technical Reviewer Quickstart

Status: Historical / superseded on 2026-08-04.

This quickstart was used for the RC_003 technical-review process. It is retained
as archived evidence, not as an active requirement for future product progress.

## Your Task

Generate one local DataTrust HTML reliability report from the assigned CSV
within `15` minutes, without assistance from the Numek founder or team.

Use only the clean reviewer packet. Do not request or inspect the full working
repository. DataTrust supports CSV classification datasets only.

Your assignment must state:

- extracted reviewer-packet directory
- dataset path
- dataset alias
- target column name
- output report path and alias

Quote every path because directories and filenames may contain spaces.

## Privacy And Evidence Identity

DataTrust runs locally and does not upload the CSV. Do not send the dataset,
report, screenshots, row values, or private column contents to the facilitator.
Record only aliases, dimensions, target, environment details, commands, errors,
and feedback in the evidence form.

## Before The Timed Run

1. Confirm you have not worked on DataTrust or seen its output for this dataset.
2. Inspect the assigned CSV using your normal local process.
3. Complete `MANUAL_FIRST_ASSESSMENT.md`.
4. Give the completed assessment to the facilitator before seeing any DataTrust
   output.

The manual-first assessment is separate from the `15`-minute install/run timer.

## Select Python Before Timing

Python `3.10` or newer is required.

Select one installed Python command that reports version `3.10` or newer.
Record the OS/version, selected command, and exact Python version in the
Environment And Installation Evidence section. Use that same selection to
create the environment. Do not silently switch interpreters.

Windows PowerShell examples:

```powershell
$PythonExe = "py"
$PythonArgs = @("-3.10")
& $PythonExe @PythonArgs --version
```

Other valid Windows selections may include `@("-3.11")`, `@("-3.12")`, or a quoted full path
to a Python executable. Keep `$PythonExe` and `$PythonArgs` unchanged throughout
the run.

macOS/Linux examples:

```bash
PYTHON_CMD=(python3.10)
"${PYTHON_CMD[@]}" --version
```

Other valid macOS/Linux selections may include `python3.11`, `python3.12`, `python3.13`,
`python3`, or a quoted full executable path. Keep `PYTHON_CMD` unchanged
throughout the run.

If a candidate command is missing or reports Python older than `3.10`, try
another installed command before timing. If no installed command reports
Python `3.10` or newer, stop before the timed run. Record the issue and install
a supported Python from https://www.python.org/downloads/ or reschedule.

## Windows PowerShell Timed Run

Start the timer immediately before `Set-Location`:

```powershell
Set-Location -LiteralPath "<extracted-reviewer-packet-directory>"
& $PythonExe @PythonArgs -m venv ".venv"
& ".venv\Scripts\python.exe" -m pip install --no-build-isolation -e "."
& ".venv\Scripts\datatrust.exe" audit "<dataset-path>" --target "<target-column>" --task classification --out "<output-report-path>"
```

Optional activation command:

```powershell
& ".venv\Scripts\Activate.ps1"
```

Activation is not required when using the explicit executable paths above.

## macOS/Linux Timed Run

Start the timer immediately before `cd`:

```bash
cd "<extracted-reviewer-packet-directory>"
"${PYTHON_CMD[@]}" -m venv ".venv"
".venv/bin/python" -m pip install --no-build-isolation -e "."
".venv/bin/datatrust" audit "<dataset-path>" --target "<target-column>" --task classification --out "<output-report-path>"
```

Optional activation command:

```bash
source ".venv/bin/activate"
```

Activation is not required when using the explicit executable paths above.

Stop the timer when the command confirms the report was written. Open the local
HTML report only after stopping the timer.

## Record Environment And Installation Evidence

After installation, record the exact environment Python version, pip version,
and complete `pip freeze` output in the Environment And Installation Evidence
section. This evidence is separate from private dataset evidence.

Windows PowerShell:

```powershell
& ".venv\Scripts\python.exe" --version
& ".venv\Scripts\python.exe" -m pip --version
& ".venv\Scripts\python.exe" -m pip freeze
```

macOS/Linux:

```bash
".venv/bin/python" --version
".venv/bin/python" -m pip --version
".venv/bin/python" -m pip freeze
```

The environment Python version must match the interpreter selected before
timing and must be Python `3.10` or newer.

## Record Private Dataset Evidence

Record dataset alias, row count, column count, and target in the separate
Private Dataset Evidence section. Do not include private rows or raw values.

## Record The Generated Report Identity

Record the exact report alias and output path.

## Python API Alternative

The CLI is the required dry-run path. After completing it, you may optionally
confirm the public API using the environment's Python executable:

```python
from datatrust import DataTrust

audit = DataTrust("<dataset-path>", target="<target-column>", task="classification")
audit.generate_report("<output-report-path>")
```

## Troubleshooting

Record every error, uncertainty, workaround, and attempted command verbatim.
The facilitator cannot answer setup or product questions during the timed run.

- If no installed command reports Python `3.10` or newer, stop before timing
  and follow the Python instructions above.
- If the environment Python version differs from the selected interpreter,
  stop and record the mismatch.
- If installation fails, record the full error and commands attempted.
- If PowerShell blocks activation, continue with explicit `.venv\Scripts\...`
  executable paths; activation is optional.
- If the target is rejected, verify the exact CSV column name and record the
  mismatch or uncertainty.
- If the dataset is not a CSV classification dataset, stop and mark it
  ineligible rather than converting it.
- If report generation alone exceeds `30` seconds, record the measured time.

Do not use existing generated reports, validation results, adjacent-tool
comparisons, internal project documents, or verbal explanations.
