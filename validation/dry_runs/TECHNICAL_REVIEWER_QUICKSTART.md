# Uninvolved Technical Reviewer Quickstart

## Your Task

Generate one local DataTrust HTML reliability report from the assigned CSV
within `15` minutes, without assistance from the Numek founder or team.

Use only the clean reviewer packet. Do not request or inspect the full working
repository. DataTrust V1 supports CSV classification datasets only.

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
Record only aliases, dimensions, target, and SHA-256 identities in the evidence
form.

Before the timed run, record the local dataset's SHA-256:

Windows PowerShell:

```powershell
(Get-FileHash -Algorithm SHA256 -LiteralPath "<dataset-path>").Hash.ToLower()
```

macOS:

```bash
shasum -a 256 "<dataset-path>"
```

Linux:

```bash
sha256sum "<dataset-path>"
```

## Before The Timed Run

1. Confirm you have not worked on DataTrust or seen its output for this dataset.
2. Inspect the assigned CSV using your normal local process.
3. Record dataset alias, SHA-256, row count, column count, and target in the
   technical evidence form.
4. Complete `MANUAL_FIRST_ASSESSMENT.md`.
5. Give the completed assessment to the facilitator to seal before seeing any
   DataTrust output.

The manual-first assessment is separate from the `15`-minute install/run timer.

## Check Python Before Timing

Python `3.11` or newer is required.

Windows PowerShell:

```powershell
py -3.11 --version
```

macOS/Linux:

```bash
python3.11 --version
```

If the command is missing or reports an older version, stop before the timed
run. Record the issue and install Python 3.11 from https://www.python.org/downloads/
or ask the facilitator to reschedule after Python is available. Do not silently
fall back to another Python version.

## Windows PowerShell Timed Run

Start the timer immediately before `Set-Location`:

```powershell
Set-Location -LiteralPath "<extracted-reviewer-packet-directory>"
py -3.11 -m venv ".venv"
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
python3.11 -m venv ".venv"
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

## Record The Generated Report Identity

Record the exact report alias and local SHA-256 before the report is given to
the separate non-technical reviewer.

Windows PowerShell:

```powershell
(Get-FileHash -Algorithm SHA256 -LiteralPath "<output-report-path>").Hash.ToLower()
```

macOS:

```bash
shasum -a 256 "<output-report-path>"
```

Linux:

```bash
sha256sum "<output-report-path>"
```

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

- If Python 3.11 is missing, stop before timing and follow the Python
  instructions above.
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
