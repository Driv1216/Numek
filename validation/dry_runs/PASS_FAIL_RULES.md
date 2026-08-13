# Objective Dry-Run Pass, Fail, Pause, And Fix Rules

Status: Historical / superseded on 2026-08-04.

These rules governed the RC_003 dry-run process. They are retained as archived
process evidence. They no longer define an active DataTrust exit gate, and
they must not be used to require a new external practitioner validation round.

There is no conditional pass. Human dry runs are evidence collection, not a
request for preference-driven redesign.

## Technical Dry-Run Pass

The technical dry run passes only if every rule passes:

- `T1`: reviewer is uninvolved in DataTrust development
- `T3`: eligible CSV classification dataset and target are used
- `T3a`: dataset alias, row count, column count, and target are recorded
- `T3b`: OS/version, selected Python command, exact selected Python version,
  exact environment Python version, exact pip version, and post-install
  `pip freeze` are recorded separately from private dataset evidence
- `T3c`: the selected command reports Python `3.10` or newer, is used to create
  the environment, and the resulting environment uses that selected interpreter
- `T4`: manual-first assessment is completed before output is viewed
- `T5`: reviewer installs and produces the HTML report within `15` minutes
- `T6`: no founder/team assistance is provided
- `T7`: report opens and contains all six numbered report sections
- `T8`: for every displayed top risk, reviewer can state the finding, why it
  matters, and what to check next without prompting
- `T9`: no unsupported or certification-style claim is identified
- `T10`: generated report alias is recorded

Any failed technical rule fails the technical dry run.

## Non-Technical Dry-Run Pass

The non-technical dry run passes only if every rule passes:

- `N1`: reviewer is separate, non-technical, and uninvolved
- `N3`: reviewer receives only the report and blank form, with no explanation,
  hints, prompts, or anchoring
- `N3a`: report alias matches the technical dry-run evidence
- `N4`: within `3` minutes, reviewer correctly identifies overall risk
- `N5`: within `3` minutes, reviewer correctly identifies the top concerns
- `N6`: within `3` minutes, reviewer correctly identifies the recommended next
  action
- `N7`: within `3` minutes, reviewer correctly identifies what the report does
  not prove

Any failed non-technical rule fails the non-technical dry run.

## Immediate Pause Rules

Do not begin practitioner validation, and stop any active dry-run sequence, if:

- any `T` or `N` rule fails
- a reviewer receives the working repository or prohibited anchoring material
- technical and non-technical report aliases differ
- report generation errors, exceeds the dry-run time limit, or produces an
  incomplete report
- assistance, anchoring, or late manual-first edits contaminate a run
- an unsupported/certification-style claim or credibility-breaking
  contradiction is identified

Contaminated sessions are invalid evidence, not failures attributable to the
reviewer. Repeat them with a new eligible reviewer after correcting the process.

## Fix Classification And Rerun Scope

- Setup or quickstart documentation failure: fix only the documented setup
  blocker, create a new candidate ID, and rerun the technical dry run.
- Report-content clarity or comprehension failure: fix only the evidenced
  blocker, create a new candidate ID, and rerun both technical and
  non-technical dry runs.
- Profiling, scoring, risk-summary, report-content, or template change: create a
  new candidate ID; all earlier candidate evidence becomes diagnostic only.
- Protocol contamination: change no product behavior unless separate evidence
  supports it; repeat the contaminated session with a new reviewer.
- Preference, feature request, visual taste, or out-of-scope request without a
  failed objective rule: record and defer it.

Historical note: this final step is superseded. Do not proceed to or require a
frozen practitioner validation round as an active acceptance gate.
