# Dry-Run Facilitator Instructions

Status: Historical / superseded on 2026-08-04.

These instructions governed the RC_003 dry-run process and are retained as
archived evidence. Future product development reviews are internal to
Drivyaansh and Codex unless Drivyaansh explicitly requests outside feedback.

These instructions protect the dry runs from assistance, anchoring, and
post-hoc reinterpretation.

## Before Either Session

1. Use the historical RC_003 packet only when reviewing the old RC_003 archive.
   Never give an external reviewer the full working repository.
2. Record the candidate ID on every form.
3. Select reviewers who were not involved in DataTrust development.
4. Do not show the internal Evidently comparison or describe expected findings.
5. Do not describe DataTrust as good, reliable, complete, easy, or ready.
6. Confirm the packet excludes existing reports, validation results and
   comparisons, internal project docs, previous evidence, and virtual
   environments.
7. Store completed evidence copies under `validation/dry_runs/evidence/` using
   reviewer IDs, never names or private dataset names.

## Technical Dry Run

1. Provide only the verified clean reviewer packet, assigned eligible CSV path,
   dataset alias, target, output report alias, and blank reviewer-facing forms.
2. Keep DataTrust output hidden until the manual-first assessment is complete.
3. Before timing, confirm the reviewer selected and recorded one installed
   Python command that reports `3.10` or newer. Do not suggest which command to
   select.
4. Confirm environment/version evidence is recorded separately from dataset
   evidence. Confirm dataset evidence records alias, row count, column count,
   and target. Receive the completed manual-first form before DataTrust output
   is viewed.
5. Start the `15`-minute timer immediately before the reviewer begins the
   quickstart's timed install/run steps.
6. Do not answer setup, command, target-selection, interpretation, or product
   questions. Record every question/request verbatim.
7. Permitted responses are limited to: “Please use the written instructions,”
   “I cannot assist during this dry run,” and neutral timer updates if requested.
8. Do not point, type, click, suggest commands, correct mistakes, or confirm
   interpretations.
9. Stop the timer when the CLI confirms the report was written.
10. Confirm the reviewer records exact environment Python, pip version, and
   post-install `pip freeze`, and that environment Python matches the selected
   supported interpreter.
11. Record the generated report alias. Let the reviewer complete the top-risk
   communication and workflow sections without prompting.
12. Apply objective rules.

## Non-Technical Dry Run

1. Use a separate person with no ML/data engineering role and no DataTrust
   development involvement.
2. Give the reviewer only the generated report and blank non-technical
   comprehension form with the exact report alias.
3. Do not explain DataTrust, the dataset, risk bands, report structure, terms,
   limitations, or expected answers.
4. Start a `3`-minute timer when they receive the report.
5. Do not answer questions or redirect attention. Record any question asked.
6. Stop at three minutes even if answers are incomplete.
7. Score answers only against text visible in the report, after time expires.
8. Apply objective rules.

## Prohibited Anchoring

Never reveal or imply:

- expected risk band, score, findings, severity, or recommended action
- whether a reviewer answer is correct while the timer is running
- what previous reviewers found
- desired pass outcome
- that a particular section or phrase should be inspected

## Returning Evidence

Return completed forms as Markdown or PDF copies named:

```text
<candidate-id>_<reviewer-id>_manual-first.<ext>
<candidate-id>_<reviewer-id>_technical-dry-run.<ext>
<candidate-id>_<reviewer-id>_nontechnical-comprehension.<ext>
```

Do not return private CSVs, generated reports from private data, screenshots
containing private data, or raw sensitive values.

The technical and non-technical forms must reference the same report alias.
