# Numek Roadmap

Last updated: 2026-08-13
Current status: DataTrust classification baseline completed; next direction undecided

## Completed Product Baseline

DataTrust is a local-first dataset reliability product for CSV classification
workflows. Drivyaansh has accepted the current baseline after implementation
and verification by Codex.

Completed capabilities include:

- public Python API, CLI, and loopback-only browser UI
- grouped, explainable target guidance with no automatic selection
- server-enforced acknowledgement for advanced classification targets
- deterministic binary, multiclass, and single-class subtype detection
- transparent sub-scores, evidence score, guardrails, risk band, and findings
- one shared deterministic narrative for compact and full report surfaces
- canonical standalone HTML report with native browser-UI PDF download
- layered eight-topic report with a portrait decision layer and landscape appendix
- complete technical evidence, limitations, and deterministic language handling
- reproducible public-dataset and controlled-mutation validation corpus
- automated regression coverage and archived historical review evidence

The former mandatory external-review process is not an ongoing release gate.
External feedback may still be gathered when Drivyaansh chooses it as useful
learning evidence.

## Next Direction

No next product objective, phase, or release label is currently approved.

Potential work recorded elsewhere in the repository remains exploratory. It
must not be treated as scheduled, blocked, promised, or automatically next.
Drivyaansh will choose the next objective before implementation planning begins.

When a direction is selected, record it by capability and status rather than by
generic sequential product-version labels. Use actual package or release versions only
where software distribution, compatibility, or immutable release history
requires them.

## Possible Directions Requiring A Future Decision

These are options, not roadmap commitments:

- deeper dataset diagnostics such as stronger leakage review, suspicious
  identifier evidence, temporal checks, missingness patterns, or optional
  label-issue analysis
- model-prediction analysis such as calibration, Brier score, reliability
  diagrams, high-confidence errors, or threshold sensitivity
- workflow expansion such as additional interfaces, formats, deployment modes,
  or supported learning tasks
- customer discovery, product validation, or segment selection
- ConfidenceGuard, HallucinationGuard, or broader Numek platform work

## Planning Rule

Do not infer priority from list order or historical phase numbering. For the
next body of work:

1. Drivyaansh chooses the objective and scope.
2. Codex verifies the repository state relevant to that objective.
3. Proposals are challenged against actual code, tests, and artifacts.
4. Drivyaansh approves the implementation plan.
5. Codex implements and verifies the approved work.
