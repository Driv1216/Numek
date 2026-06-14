# Objective Dry-Run Pass, Fail, Pause, And Fix Rules

There is no conditional pass. Human dry runs are evidence collection, not a
request for preference-driven redesign.

## Technical Dry-Run Pass

The technical dry run passes only if every rule passes:

- `T1`: reviewer is uninvolved in DataTrust development
- `T2`: candidate verification passes before and after the session
- `T3`: eligible CSV classification dataset and target are used
- `T3a`: dataset alias, local SHA-256, row count, column count, and target are
  recorded
- `T4`: manual-first assessment is completed and sealed before output is viewed
- `T5`: reviewer installs and produces the HTML report within `15` minutes
- `T6`: no founder/team assistance is provided
- `T7`: report opens and contains all six numbered V1 sections
- `T8`: for every displayed top risk, reviewer can state the finding, why it
  matters, and what to check next without prompting
- `T9`: no unsupported or certification-style claim is identified
- `T10`: generated report alias and SHA-256 are recorded

Any failed technical rule fails the technical dry run.

## Non-Technical Dry-Run Pass

The non-technical dry run passes only if every rule passes:

- `N1`: reviewer is separate, non-technical, and uninvolved
- `N2`: candidate verification passes before and after the session
- `N3`: reviewer receives only the report and blank form, with no explanation,
  hints, prompts, or anchoring
- `N3a`: report alias and SHA-256 exactly match the technical dry-run evidence,
  and the report hash remains unchanged after the session
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
- candidate verification fails or candidate files change
- clean reviewer packet verification fails or a reviewer receives the working
  repository or prohibited anchoring material
- technical and non-technical report aliases or SHA-256 identities differ
- report generation errors, exceeds the dry-run time limit, or produces an
  incomplete report
- assistance, anchoring, or unsealed manual-first evidence contaminates a run
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

Proceed to a frozen practitioner validation round only after both dry runs pass
on one unchanged candidate.
