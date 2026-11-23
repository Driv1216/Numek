# Numek Current State

## ConfidenceGuard CG7 — S6 operations (2026-11-23)

**What exists now.** Monitoring signals become **conditions** with a lifecycle: emerging, active, quiescent,
recovered, lapsed or suppressed. Recovery comes only from declared evidence: operational (R1), or an SM2 claim
(R2/R3) bound to the condition. An absent alarm is never recovery.

**Incidents.** P1 and P2 conditions open or join **incidents**, by a versioned priority table that records its
reasons.
- Grouping joins a condition only by a direct link to the incident's anchor (a shared deployment event, or overlap
  of the evaluated populations), so it is never transitive. Anything weaker becomes a related-incident suggestion.
- Each incident keeps an immutable detection dossier and appended knowledge revisions ("as known at detection" or
  "now").
- It follows the H.7 lifecycle, with acknowledgement timers, audited and reversible split and merge, evidence-checked
  resolutions, and reopening on recurrence.

**Notifications** come from a transactional outbox, as signed webhooks or SMTP through the allowlisted egress, with
digests, quiet windows, retries and dead letters (which raise health conditions).

**Running it.** The leader controller schedules monitoring cycles and retention, fires escalations and delivers
notifications. Observation retention (400 days by default) purges unpinned old facts and marks affected
evaluations `summary_only`. Installation backups carry all operations state.

**Results:** platform suite 158 passed; S6 suite 14 passed.

**Not in S6:** structural links, hypotheses and impact-based priority (S7); proposals and interventions (S8); the
API, CLI and console (S9). D-1 remains.

## ConfidenceGuard CG7 — S5 monitoring (2026-11-20)

**What exists now.** Ingested evidence is monitored. A deployment has a versioned monitoring definition: inspect it to
see the frozen reference, each detector's null level, false-alarm budget, expected detection delay and power, and the
refusals; then confirm exactly what was inspected.

**How monitoring runs.** Windows are evaluated when they close (outcome-free measures, drift against the reference,
estimates) and again when their outcomes mature (performance, accountability, outcome detectors). Each evaluation
reads only its own window, under a window-scoped evidence-use reservation; selection equals full-history selection
restricted to the window (equivalence gate).

**Detectors.** SM1 alarms (bounded-mean e-CUSUM with resets, E[false alarms] ≤ α × units) carry fixed wording and
what they do not establish. SM2 establishes R2/R3 recovery claims. Late data creates window revisions and never enters
running detectors. Health and a coverage map state what is and is not monitored; absence of alarms is never presented
as health.

**Qualification.** The locked M.2 protocol ran once and every gating panel passed: exact enumeration over 2^20 paths,
null simulations, SM2 false-claim checks and planner validity. Violation controls are recorded as documented limits.

**Results:** platform suite 144 passed; CG1–CG6 673 passed, 0 failed.

**Not in S5:** coverage-miss, region and deferral statistics; the domain classifier and Neyman guidance (S7);
incidents, notifications and scheduling (S6); the API, CLI and console (S9). D-1 remains.

See [CG7 status](../validation/cg7/IMPLEMENTATION_STATUS.md) and [sequential methods](CG7_SEQUENTIAL_METHODS.md).

## ConfidenceGuard CG7 — S4 ingestion (2026-11-20)

**What exists now.** Production evidence can now flow into CG7. A NUMEK installation (one database, object store and
secrets store) holds one evidence catalog per registered system. Deployments and versioned source contracts feed it.

**Receiving.** Batches arrive by HTTP (per-source service tokens), directory pull, or the `numek_monitor` SDK. Each is
durably acknowledged only after it is encrypted at rest and recorded. Retries are idempotent and conflicting resends
are refused.

**Processing.** Each batch is minimized (undeclared fields are dropped and only counted), checked row by row, and
quarantined per row (encrypted, never logged) or per conflicting fact. Accepted rows publish through the unchanged CG3
capture path.

**Reserve.** Entities are assigned to the namespace's sealed reserve at publication, so reserve-backed studies now
work end to end on ingested data.

**Also in S4:**
- watermarks, lateness and window closure standings;
- deployment events;
- deployment identity standings (declared, registered, spec-compatible, sampled output-consistent with a
  Clopper–Pearson bound, customer-signed statements), with no attestation inferred from agreement;
- 7/30-day retention, with day-key shredding reported honestly (backups still hold the keys);
- installation backups that cover unprocessed batches.

**Results:** platform suite 113 passed; CG1–CG6 673 passed, 0 failed.

**Not in S4:** the operations API beyond ingestion, the console and the CLI (S9); detectors and window evaluation (S5).
D-1 remains for workspace-bound shared catalogs.

See [CG7 status](../validation/cg7/IMPLEMENTATION_STATUS.md).

## ConfidenceGuard CG7 — S3 complete: migration, execution contexts, v2 writer retired (2026-11-20)

**Persistence is platform-only.** Every persistent ConfidenceGuard workspace now lives on the NUMEK platform: a shared
installation via `NUMEK_PLATFORM_DSN`, or the workspace's own P-LOCAL cluster. Catalog v2 is retired as a writer. A v2
workspace is refused with `migration_required` until it is migrated (`confidenceguard workspace migrate`); a read-only
legacy view and the migration tooling remain.

**Migration (S3c).**
- **Replay.** Each v2 operation and deletion becomes the platform publication at the same K, with the same ids,
  request ids, receipts, object bytes and facts. Evidence uses become durable governance records.
- **Validation before cutover.** Structural equality of everything replayed, full byte verification, byte-equal
  reconstruction of every retained fact, identical assessments, deletion previews and evidence-use overlap answers,
  and equal re-execution of every retained CG3 analysis.
- **Cutover.** A single transaction, which requires the passing report.
- **Safety.** Resumable at every boundary, refuses a changed source, and can be abandoned before cutover.

**Execution.** All 36 `compat.supervise` sites now call `ctx.run`. The workbench keeps spawned supervised phases.
Platform jobs and migration validation run phases in-process, with phase-boundary budgets and per-phase governance
isolation. Both give identical results.

**Defect fixed.** CG3 history selection streamed rows in a nondeterministic order.

**Results:** CG1–CG6 671 passed with 2 test-only failures, fixed and rerun; platform suite 99 passed; DataTrust failure set unchanged from the S3d baseline in the same environment (environmental only). No product regressions.

**Tracked limitation D-1.** Shared-installation workspaces keep per-workspace object stores that the installation
backup does not cover. There is no supported installation-wide backup for them, and no production-readiness claim
until D-1 is done (S9/S10).

See [CG7 status](../validation/cg7/IMPLEMENTATION_STATUS.md).

## ConfidenceGuard CG7 — S3d reserve-backed assessments and the platform test port (2026-11-19)

**Reserve-backed assessments.** CG4 confirmations and CG5 policy assessments can now use the sealed reserve end to end, in
the G.8 order:
1. freeze the family;
2. find eligible reserve entities from identities only;
3. reserve and consume them in one transaction;
4. inspect and assess under that study's authority.

One claim exists per family. Retries, scheduled looks and numerical recomputations reuse it. Other families, monitoring
and development reads never see those units. Ordinary workflows are unchanged.

**Test port.** All 30 v2-specific test assertions were replaced by the platform form of the same invariant; none was
removed. Workspace backup tests run on P-LOCAL workspaces, and the shared-installation refusal is a tested contract.

**Product gaps found and fixed by the port:**
- untracked session identifiers are released on deletion and purge;
- evidence-use records cannot be deleted individually;
- a repeated evidence-use request returns its original receipt;
- standalone runs depend on byte-identical retained sources for deletion;
- fact iteration order is deterministic;
- a restore from a missing backup refuses with `backup_changed`.

**Closure gate:**
- CG3–CG6: 592 passed on the platform and 592 on catalog v2, with 0 failures and the same 10 pre-existing skips.
- Platform suite: 85 pass after one fix, which was rerun on its own.

**Remaining:**
- S3c (v2 replay and equivalence validation);
- the `ctx.run` refactor;
- retirement of the v2 writer, which needs S3c.

**Limitations.**
- Reserve entities are registered at publication only from S4.
- Column-based roles cannot use the reserve.
- Shared-installation workspaces cannot be backed up at workspace level.

See [CG7 status](../validation/cg7/IMPLEMENTATION_STATUS.md).

## ConfidenceGuard CG7 — S3b CG4–CG6 storage on the platform (2026-11-19)

CG4, CG5 and CG6 workspaces now run on the NUMEK platform, with v2 deletion, purge, P-LOCAL backup and restore semantics.
Call sites use one storage helper API instead of v2 SQLite internals.

**Governance.**
- Worker reads use access-only reservations (`selection_access`), which record no exposure. As in v2, CG3 analyses record
  outcome exposure only when evidence-use tracking is enabled.
- Confirmation workers inherit scoped study authority. They can read only the sealed-reserve units their own study family
  consumed, within the study's snapshot. All other purposes are refused or have those units withheld.
- A reservation handed to an analysis is never widened to a later snapshot.

**Fixed defects.**
- Unordered DuckDB aggregations made sealed CG3 results non-reproducible. This affected both backends and predates CG7.
- Evidence-use ids collided across workspaces of one installation.

**Results.**
- CG3–CG6 on the platform: 562 passed. Every remaining failure is an obsolete v2-specific test assertion (S3d test port),
  a by-design refusal to back up a workspace on a shared installation, or the replaced v2 lock assertion.
- Platform suite: 80 passed.
- The v2 path still passes.

**Known limitation.** Platform ConfidenceGuard populations do not yet contain reserve entities. Inspection runs before the
study reservation, and entity registration arrives with ingestion in S4. End-to-end reserve-backed confirmations need the
G.8 ordering (reserve and consume first, then inspect).

S3c and S3d remain. See [CG7 status](../validation/cg7/IMPLEMENTATION_STATUS.md).

## ConfidenceGuard CG7 — S3a CG3 on the platform (2026-11-19)

`confidenceguard/platform_catalog.py` runs CG3 workspaces on the NUMEK platform. Existing `Catalog(root)` call sites open it
automatically for platform-bound roots.

- It is a full port of v2 publication semantics, with identities preserved (v2 object and operation ids become platform
  UUIDs; K is the platform sequence).
- CG3 inspect, analyze and restate now reserve the outcome-bearing population before reading, and the saved assessment
  consumes the reservation.

**Results:**
- CG3 on the platform: 59 of 67 pass. The rest are deletion and backup, which are S3b, plus one replaced v2 lock assertion.
- The v2 path is unchanged: CG3 67 passed, CG4–CG6 history tests 21 passed. The platform suite passes 71.

S3b–S3d remain. See [CG7 status](../validation/cg7/IMPLEMENTATION_STATUS.md).

## ConfidenceGuard CG7 — S2 governance before access (2026-11-19)

`numek_platform/governance` adds evidence-use reservations committed **before** any outcome-bearing read, ported from
the ConfidenceGuard ledger:

- overlap and continuity rules;
- scheduled looks;
- study alpha budgets;
- same-family reuse.

It also adds:

- **Durable exposure registries.** History is never deleted by fact purges.
- **Consumption inside the result's publication transaction.** A result cannot exist without its evidence-use records.
- **The namespace-level sealed reserve.** Defaults: 10%, `exclude`. Assignment is materialized at first observation;
  rotation and fraction changes are versioned for new entities only; reallocation and release are explicit; spending is
  at entity level.
- **A governed reader.** It is now the only path to outcome-bearing facts. The plain reader refuses outcomes and hides
  reserve rows.

All 69 platform tests pass. ConfidenceGuard code is unchanged until S3. See
[CG7 status](../validation/cg7/IMPLEMENTATION_STATUS.md).

## ConfidenceGuard CG7 — S1 platform core (2026-11-19)

The founder approved the revised CG7 plan with Addendum R2 and authorized stage S1. `src/numek_platform/` now holds the
shared evidence and execution foundation:

- PostgreSQL as the transactional authority, with an organisation-scoped schema and a global fact index;
- an immutable object store with verify-on-read;
- the fenced publication protocol, with K assigned at commit;
- read pins, purge, compaction and garbage collection;
- jobs, controller and worker hosts;
- identity, audit, secrets and egress;
- backup and restore;
- a managed local PostgreSQL cluster (P-LOCAL);
- the catalog-v2 migration state machine.

**Not changed yet:**
- ConfidenceGuard and DataTrust code. ConfidenceGuard persistence still uses catalog v2 until S3 ports it and migrates
  existing workspaces.
- `pyproject.toml` only gains the `platform` extra, the `numek` script and migration package data.

**Checks:**
- The 56 focused platform tests pass against a real PostgreSQL 17.12. Four defects found during verification were fixed.
- No performance, Linux or independent-review standing is claimed.

See [CG7 status](../validation/cg7/IMPLEMENTATION_STATUS.md).

**Prerequisites for persistent use:**
- PostgreSQL ≥ 16 binaries (installed on this Mac with Homebrew `postgresql@17`).
- The isolated CG7 environment `validation/cg7/py313.nosync`, built from the CG6 Python 3.13 lock plus the platform
  packages. The CG6 qualification environment was not modified.

## DataTrust Report Experience — review fixes (2026-11-18)

Fixes for every finding of the technical review of the redesign, plus the validator problems. All presentation only,
except the validator scripts. Analysis JSON is identical in all 25 matrix cases
(`validation/report_experience/results/after_review_fixes/COMPARISON.md`).

**H1: evidence behind every finding now prints.** The focused PDF prints the rows a recorded finding refers to beyond
a summary view's limit, as a table under each capped one (`report_structured.capped_tables(..., referenced=)`):
- M3 and M4 columns, and M5 evidence records;
- grouped per finding, never merged, and budgeted by `report_print_v1`.

| Case | Before (finding evidence in the default PDF) | Now | Pages |
|---|---|---|---|
| M5 Beijing | 2 of 15 findings | 15 of 15 | 11 → 23 |
| M5 retail | 1 of 2 | 2 of 2 | 10 → 11 |
| M4 wide | 20 of 80 columns | all 80 (individually or in a disclosed summary) | 6 → 7 |

**Moderate fixes:**
- **M1:** every opaque reference kind the analyses define (including `split_`, `field_`, `category_`) is labelled
  protected.
- **M2:** an export that discloses examples gets "Protected evidence" wording that says so.
- **M3:** no duplicate element ids. Units that point elsewhere keep their own id, and row anchors are positional.
- **M4:** complete-profile PDFs above 5,000 rows raise `CompletePrintWarning`. The CLI help and `docs/SCALABILITY.md`
  state the cost (5,000 columns: 564 pages, 49 s, about 2.9 GiB).

**Low fixes:**
- **L1:** "In this report" examples for window effects, Jaccard, shared passages, Hamming distance, duplicate
  candidates, reconciliation outcomes and logical identity.
- **L2:** the M5 appendix disclosure states its print count as well as its screen count.
- **L3:** disclosures name their view ("Detailed view, …"; "Summary view: counts only …").
- **L4:** running section headers on every page after the first.
- **L5:** a test for the `legacy_html=True` path.
- **L6:** recorded lists of more than 20 names print the first 12 plus a disclosed count; the screen text is
  unchanged.
- **L7:** M6 and M7 "No score" wording no longer mentions priorities.
- **L8:** M4 disclosures point to `/profile/columns` or `/profile/sources`.

**Validators.**
- The M4, M5, M6, M7 and M9 validators write into a temporary mirror unless `--refresh` is given (`validation/outputs.py`).
  A full run left `validation/` unchanged.
- M7 passes again. Its disclosure step audits afresh, because a stored private manifest is bound to the disk's device
  number, which changed since 14 October.
- M9 checks the real summary wording and then stops at the model step. See the open decision below.

**Measured** (median of three runs; Beijing re-timed over five):
- Every sparse page sits before an intended boundary or is the last page, and no stranded headings remain.
- Timing is within tolerance except M5 Beijing: 0.54 → 1.37 s against a 1.04 s allowance. Its default PDF now prints
  the evidence for all 15 findings, about a page each, which the discoverability gate requires.

**Open decision: M9 model qualification.**
- Since commit `ba3cf1606` (2026-10-23), M9's packaged model qualification no longer matches the code, so every model
  judgment abstains (`model_not_enabled_or_unqualified`), with or without this redesign.
- Verified: that commit changed only the post-analysis guidance attachment (4 inserted lines and 1 changed line in
  `cross.py` and `cross_contracts.py`).
- The methodology allows a qualification-reuse record for changes outside the semantic pipeline. Recording one, or
  re-qualifying, is left to the founder.

**Tests:** the DataTrust suite passed 801; M9 and CG1 together passed 80.

## DataTrust Report Experience Redesign — Stage 8 closure (2026-11-18)

The redesign (Stages 0–8) is complete. It covers classification, regression, unlabeled, M3, M4, M5, M6, M7 and M9
reports; ConfidenceGuard is excluded and audio is deferred. The work is presentation only.

**Outcome on the full 25-case matrix** (`validation/report_experience/results/after_stage8_rule/` and `after_stage8/`,
against Stage 0):
- **Analysis JSON:** identical in all 25 cases.
- **Findings:** every finding title or reader-facing name appears in every PDF.
- **Wide data:** 5,000 columns went from 417 pages, 50.6 s and 2.4 GiB to 14 pages, 0.74 s and 107 MiB. The `complete`
  profile prints all 564 pages by choice (`docs/SCALABILITY.md`).
- **Timing:** every ordinary report is within its timing tolerance. Every wide case is faster and smaller than before.
- **Sparse pages:** every page under 40% fill sits immediately before an intended part boundary (Reading guide or
  Technical Appendix) or is the last page.
- **Stranded headings:** a PDF scan finds none.
- **Visual check:** all 353 focused pages were inspected as contact sheets (`work.nosync/stage8/`).

**Closure changes:**
- **Shared keep-with-next rule.** Each section's "Explained terms" line now stays with its content and in one piece, in
  every report. This removed 7 stranded headings in tabular reports. It adds one page to the three plain-wide cases (a
  short tail before the Reading guide).
- **Accessibility.**
  - Every table's search box and "Show more" button has its own accessible name ("Find in All columns", "Show more
    columns in All columns"). Before, seven boxes in one report were all named "Find".
  - Tables are labelled by their headings.
  - Keyboard pass: term buttons open and close by Enter, Space and Escape, focus returns to the term, and
    `aria-expanded` resets. Table filters report their results through a polite live region.
  - VoiceOver itself was not run; that needs a person at the Mac.
- **Docs.**
  - ARCHITECTURE: "Report experience (`report_print_v1`)".
  - METHODOLOGY: "Reading reports: coverage, treatment, location".
  - SCALABILITY: the appended wide-data export table.

**Re-pins over the redesign** (all presentation-only, re-asserted by `validation/report_experience/repin.py`):
- every family identity in `tests/fixtures/presentation_identities.json`;
- the 18 `html_sha256` values in `tests/fixtures/m2_baseline.json`;
- the 3 `html_sha256` values in `tests/fixtures/m1_unlabeled_baseline.json`.

The legacy classification hash (`tests/fixtures/m1_classification_baseline.json`) is unchanged.

**Validators.**
- `validation.verify`, `unlabeled`, `regression`, `dry_runs`, `m3`, `m4`, `m5` and `m6` pass.
- `m7` and `m9` fail, and fail identically on the code before this redesign (`git archive HEAD`):
  - **M9:** the validator expects summaries beginning "N review findings.", while `cross_presentation.summary()` has
    said "This review identified N topics…" since an earlier milestone.
  - **M7:** the validator regenerates `validation/m7/results/reports/classification/final.html` in place, and the
    no-overwrite safeguard refuses because the stored file came from an older template.
- The `m4`, `m5` and `m6` validators rewrite their committed results (21 files, plus new M6 report folders) when run.
  Those writes were restored to the committed state, and the new folders were moved out of the repository.
- These validator issues are left for a separate decision.

**Tests:** the DataTrust suite passed 787; M9 and CG1 together passed 80.

**Founder decisions still open:**
- **L1:** whether the plain `DataTrust(path, target).generate_report()` and plain `datatrust audit` HTML should default
  to the current classification report. They stay frozen legacy; `--report-style current` opts in.
- **L4:** reader-facing branding. The per-template wording is kept (for example "NUMEK M5", "DataTrust image evidence").

## DataTrust Report Experience Redesign — Stage 7 (2026-11-18)

The app and the command line now reach the report experience directly.

**App report viewer:**
- An **Understand this report** button opens the report's guide drawer. It appears only when the loaded report has a
  guide; saved reports keep their original bytes.
- The report script opens the guide whenever its URL fragment is `#understand`, so the app never reaches into the report
  page. Closing the guide clears the fragment so the button works again.
- The viewer is now a real modal:
  - content behind it is inert;
  - focus starts on Back;
  - focus returns to the control that opened it.
  Before, keyboard focus stayed on the page behind it.

**Report responses:**
- Every report the app serves (live, M4–M9 and saved) goes through one helper.
- The header policy is `default-src 'none'; img-src data:; style-src 'unsafe-inline'; script-src 'unsafe-inline';
  base-uri 'none'; form-action 'none'; frame-ancestors 'self'`, with `Referrer-Policy: no-referrer`. Before, the header
  carried only `frame-ancestors 'self'`.
- Current reports also keep their own hash-pinned meta policy, so injected script stays blocked.
- Inline script is allowed at header level only so saved reports from earlier versions keep rendering.

**Print profile everywhere:**
- `--print-profile focused|complete` is now accepted by `compare`, `temporal`, `text`, `images` and
  `cross-representation`, as well as `audit`.
- M4 `ComparisonResult.generate_artifacts` and `generate_report` gain `print_profile=` (previously only the renderer
  could print M4's complete tables).
- README "Reading reports, explanations and print profiles" documents the guide, the profiles, the summary-view
  wording and the classification `presentation="current"` / `--report-style current` opt-in.

**Checked in the browser pane:** a saved classification analysis, served by `datatrust ui`.
- **Keyboard:** Tab from Back reaches the button, Enter opens the drawer with focus on the guide, and Escape closes only
  the drawer. Pressing the button again reopens it.
- **Phone width (375 px):** the button and full-width drawer work by tap, and Back returns focus to “Open report” with
  nothing left inert.
- **Console:** no errors or policy violations.
- **Fixed during the pass:** the button's tooltip had replaced its accessible name, so it was removed.

**Tests:** `tests/test_app_api.py` (report headers and the deep-link target), `tests/test_history.py` (saved-report
headers) and `tests/test_modality_reports.py` (print profile on every command and result). The DataTrust suite passed
786; M9 and CG1 together passed 80. The app bundle was rebuilt (`npm run build:app`; the bundle check passed).

## DataTrust Report Experience Redesign — Stage 6 (2026-11-18)

The M6 text, M7 image and M9 cross-representation reports now use the shared shell (CSP, script and print rules),
evidence contract and "Understand this report". Branding and footers are unchanged (founder decision L4 still open).

**Findings:**
- Each report lists every finding in an index.
- M6 and M7 findings record a family code, not a title, so the index gives each a reader-facing name, for example
  "Shared literal passages" or "Perceptual near-duplicate candidates".
- M7 evidence blocks use the same names.
- The M9 action-card limit is now disclosed in the shared wording.

**Summary selections:**
- These workflows have no `PresentationLimits`. Their existing summary selections are disclosed as "Summary view: N of M
  … shown (summary selection)", never as a historical display limit.
- Each disclosure names the HTML section, the JSON pointer and, where opaque references appear, "source content:
  protected, local resolution only".
- Every abbreviated collection is listed in full under "Complete retained evidence", printed in the `complete` profile.
  This covers M6 nested collections, witnesses, coverage strata and phase timings; M7 examples, details and candidates,
  which the summary tables previously left out without saying so; and M9 retained examples, nested measurements and
  coverage.
- All of these are opaque references and counts, already in the export JSON, so the HTML discloses nothing new.

**Concepts:** 19 new concepts:
- shared: protected evidence;
- text: framed records, five-grapheme Jaccard, candidate versus verified pair, shared passages, semantic neighbours,
  language identification;
- images: exact representations, perceptual signature, Hamming distance, duplicate candidate, coordinate frames;
- cross: logical identity, association cardinality, reconciliation outcomes, conflicting supplied evidence, separation,
  model candidates, abstention.

The shared report terms (no score, findings are review evidence, coverage, bounded search, print profile, listed on
screen) now cover these workflows, with methodology variants.

**Exports:**
- `generate_artifacts(..., print_profile=)` is accepted by all three workflows.
- `profile.export_identity` gains `presentation_identity` and `print_profile` (additive), and `canonical_html_sha256`
  binds the profile actually written.
- `text_presentation.display` and `executive_summary` are frozen and pinned by a test.
- Gate 1b: fresh M6, M7 and M9 exports from this code and from the previous commit are deep-equal once export metadata,
  volatile timings and per-audit opaque ids are removed.

**Measured** (`results/after_stage6/COMPARISON.md`, against Stage 0):

| Case | Pages before → focused / complete | PDF time |
|---|---|---|
| SciFact | 7 → 10 / 12 | 0.32 → 0.53 s |
| M7 classification | 7 → 10 / 13 | 0.27 → 0.43 s |
| M7 overlay | 13 → 18 / 28 | 0.53 → 0.61 s |
| M9 PDF / DOCX financial | 5 → 9 / 19–20 | 0.18–0.21 → 0.37 s |

- Every finding name is in each PDF. Timing is within tolerance; analysis JSON is identical.
- The only sparse pages are before the Reading guide (SciFact p8) and last pages.
- HTML grows to 61–129 KB, mostly the Reading guide and complete-evidence data.

**Re-pins and tests:**
- Every presentation identity was re-pinned (shared `report_layout`/`report_structured` changes), along with the M2 and
  unlabeled golden hashes, through `repin.py`.
- `tests/test_modality_reports.py` (25 tests) was added.
- One M7 assertion now uses the reader-facing block name.
- The DataTrust suite passed 784; M9 and CG1 together passed 80.

## DataTrust Report Experience Redesign — Stage 5 (2026-11-17)

The M5 temporal report now uses the shared evidence contract and has "Understand this report".

**Findings and display limits:**
- A finding index lists every finding. This closes the verified Stage 0 gap where findings beyond the five action
  cards were silently omitted (Beijing: 15 findings, 5 cards).
- The cards keep their historical limit, now with a disclosure.
- Every capped topic table carries a "Summary view: N of M rows shown (historical display limit)" disclosure.
- Each capped topic is listed in full in a new "Complete tables and print profile" section, printed in the `complete`
  profile.

**Readability:**
- Recorded nested values read as labelled text ("format: csv · role: dataset") instead of raw JSON or dictionary dumps.
- Per-topic forced page breaks are gone; section labels and term lines stay with their content.

**Concepts:** 11 temporal concepts were added: clock, schedule continuity, windows, window effects, runs, volatility,
seasonality, availability timing, revisions, maturity and folds. Total variation, CDF distance and Wasserstein-1 now
also apply to M5.

**Measured** (`results/after_stage5/COMPARISON.md`, against Stage 0):

| Case | Pages before → focused / complete | PDF time |
|---|---|---|
| Retail | 10 → 10 / 85 | 0.56 → 0.80 s |
| Beijing | 10 → 11 / 160 | 0.54 → 0.83 s |
| Long headers | 10 → 10 / 806 | 0.58 → 0.92 s |

- Every finding is in the PDF. Timing is within tolerance.
- The only sparse pages are the short tail before the Reading guide and each document's last page.
- **HTML size:** canonical HTML grows from 0.12–0.14 MB to 0.6–3.9 MB, because the complete tables are held as screen-only
  data islands. This is above the +120 KB review trigger: a review item, not a failure.
- The analysis JSON is identical, and M6–M9 renders are byte-identical to the previous commit.

**Re-pins and tests:**
- Re-pinned: every presentation identity that includes the shared concept modules. The M2 and unlabeled golden HTML hashes
  were re-pinned through `repin.py`.
- `tests/test_temporal_reports.py` (16 tests) was added.
- The DataTrust suite passed 759; M9 and CG1 together passed 80.

## DataTrust Report Experience Redesign — Stage 4 (2026-11-17)

The M3 (annotation, multilabel, multi-output, readiness) and M4 (comparison and advanced) reports now use the shared
shell and evidence contract and have "Understand this report".

**Display limits:**
- The historical display limits recorded with each result (`PresentationLimits`) keep their meaning.
- Every capped summary table now carries a disclosure, for example "Summary view: 20 of 80 rows shown (historical display
  limit)", with the HTML section and JSON pointer.
- Each capped table is also listed in full in an appendix "Complete tables" section, printed in the `complete` profile.

**Other changes:**
- M4 summary tables put rows referenced by a finding's recorded column list first, ordered by priority. Only the order
  changes, not the limit.
- A finding index lists every finding beyond the action-card limit.
- The forced executive page break is gone.
- 19 concepts were added: annotation axes and coverage, label cardinality and Jaccard, output correlation, central span and
  Bowley skewness, readiness, cohort contrast, overlap, schema change, total variation, CDF distance, Wasserstein-1,
  significance with BH adjustment, and affected-row union.

**Catalogue isolation.** The catalogue data moved to `report_catalogue.py`, which is not an identity module dependency.
Each family's identity covers only the concept entries it uses, so rewording one workflow's concept no longer changes
another's identity; a test proves it.

**Measured** (`results/after_stage4/COMPARISON.md`, against Stage 0):

| Case | Pages | PDF time |
|---|---|---|
| Scene | 11 → 14 | 0.43 → 0.60 s |
| M4 cases | 4–5 → 6 | 0.21–0.25 → 0.31–0.37 s |

Timing is within tolerance. The analysis JSON is identical; M5–M9 reports are byte-identical to Stage 0.

**Re-pins and tests:**
- Presentation-only re-pins (`repin.py`): the 18 M2 and 3 unlabeled golden hashes, and every family identity (a one-off
  change to the catalogue fingerprint format).
- The DataTrust suite passed 743 (7 new). M9 and CG1 together passed 80.

## DataTrust Report Experience Redesign — Stage 3 (2026-11-17)

"Understand this report" is live in the classification, regression and unlabeled reports.

**What was added:**
- `report_concepts.py`: catalogue `report_concepts_v1`, with 32 tabular and evidence-vocabulary concepts and
  methodology-specific variants. For example, the classification IQR rule counts against all rows with non-finite values
  outside the fences; the finite-only rule applies elsewhere.
- `report_context.py`: deterministic "In this report" examples that quote only recorded values, each keyed by its JSON
  pointer, or state why no example is available.
- A per-report concept manifest, built before rendering, that decides every term placement and guide entry.

**On screen:**
- Section headings carry "Explained terms" links. Each opens one shared popover next to the link; it is keyboard
  operable, Escape closes it and focus returns to the link.
- A "How to read this report" box follows the summary.
- The "Understand this report" section opens as a searchable drawer.
- Without script, the links still lead to the guide entries.

**In print:**
- A Reading guide of about two pages comes before the technical appendix.
- The first use of each term names its guide page, and every page reference resolves.

**Methodology:** the new section "Reading Reports: Presentation, Explanations, and Context Layers" documents the
presentation rules.

**Measured** (`validation/report_experience/results/after_stage3/COMPARISON.md`, compared with Stage 2):
- Reports gain 2–4 pages for the guide; Bank Full goes from 15 to 18.
- PDF time stays within the plan's tolerance in every case. A two-column guide was measured at +0.6 s and dropped.
- Long narrative, guidance and guardrail blocks may now split, so every page under 40% filled sits just before the
  Reading guide or the technical appendix.
- The analysis JSON is identical in all 13 cases; M4–M9 reports are unchanged.

**Re-pins and tests:**
- Presentation-only re-pins via `validation/report_experience/repin.py`, which re-asserts each analytical result first:
  the 18 M2 and 3 unlabeled golden HTML hashes, and the identities of the three tabular families. The digest now also
  covers each family's catalogue entries.
- The DataTrust suite passed 736 (16 new). M9 and CG1 together passed 80.

## DataTrust Report Experience Redesign — Stage 2 (2026-11-17)

The classification, regression and unlabeled reports now use the shared evidence contract (`report_print_v1`).

**Which classification report each path produces:**
- `classification_report.html` is the current classification report. The app, the canonical path and every PDF use it.
- The frozen legacy `report.html` stays the default for `DataTrust(path, target).generate_report()` and for a plain
  `datatrust audit` HTML report. `presentation="current"` or `--report-style current` opts in to the current report.

**Print profiles:** `print_profile` / `--print-profile` choose `focused` (the default) or `complete`.

**How the focused PDF handles per-column evidence:**
- Columns that a finding or an analysis flag refers to are printed in signal tables, one per family, most significant
  first, about one page of repetitive rows per group.
- The other columns are summarised using stored values only.
- "All columns" and "Numeric summaries" are complete on screen, drawn in pages from a JSON data island.
- Check ledgers are grouped.
- Per-column guidance lines whose facts are already printed stay on screen, with a disclosure.
- Checks that could not be assessed for a column are printed with their recorded reason.
- The body has no forced page breaks.

**Measured** (`validation/report_experience/results/after_stage2/COMPARISON.md`; one machine, not guarantees):

| Case | Before | After |
|---|---|---|
| 5,000 columns | 416 pages, 48 s, 2.4–3.0 GiB peak PDF memory | 10 pages, 0.50 s, 97 MiB (complete profile: 560 pages, by choice) |
| 1,000 columns | 91 pages | 10 pages |
| Many flagged columns | 126 pages | 26 pages |
| Bike regression | 27 pages | 18 pages |
| Bank Full | 15 pages | 15 pages, no sparse decision page |

The normalised analysis JSON is identical before and after in all 14 measured cases. M4–M9 reports are byte-identical to
Stage 0.

**Presentation-only re-pins** (deliberate content change; every analytical fixture field re-asserted unchanged):
- `html_sha256` for the 18 cases in `m2_baseline.json` and the 3 cases in `m1_unlabeled_baseline.json`.
- Every family in `presentation_identities.json`, because the shared `report_layout.py` changed.

**Updated tests:** four existing tests changed to follow deliberate presentation changes:
- evidence IDs print in the complete profile;
- guidance lines may be held in a data island;
- the app serves the current report;
- the identity checks follow the new template.

**Test results:** the DataTrust suite passed 720. M9 and CG1 together passed 80.

## DataTrust Report Experience Redesign — Stages 0 and 1 (2026-11-17)

The founder-approved Report Experience plan (Revision 2) is in progress.

**Stage 0** (`validation/report_experience/`) measured 25 report cases and settled six technical spikes.
- It reproduced the 416-page report: 5,000 rows × 5,000 columns, with 97% of the pages in the appendix. The cause is
  column count, not row count.
- It confirmed that the M5 report omits findings beyond its action limit without saying so.
- It chose a JSON data island with paged rendering for screen-only evidence. CSS-hidden content still costs WeasyPrint
  +440% time at 5,000 rows.

**Stage 1** adds the shared presentation foundation. No report's content changes yet. New modules:
- `report_identity.py`: per-workflow, dependency-aware presentation identity.
- `report_format.py`: display filters moved from `renderer.py`, still importable from there.
- `report_layout.py`: the `report_print_v1` evidence contract.

There are also four shared template partials.

The provenance "Presentation" line now names each report's workflow identity. Saved-history entries record that same
identity.

**Presentation-only re-pins:**
- `html_sha256` for the 18 cases in `tests/fixtures/m2_baseline.json` and the 3 cases in
  `tests/fixtures/m1_unlabeled_baseline.json`. Every one reproduces its previous hash exactly when the previous provenance
  line is restored.
- New per-workflow pins in `tests/fixtures/presentation_identities.json`.
- Analytical fixture fields are unchanged.

**Tests:** the DataTrust suite passed 703 (the 647-test baseline on the committed source, plus 56 new). The separately
run M9 suite passed 42. M4–M9 reports re-rendered byte-identical to Stage 0.

## CG6 completion and founder acceptance — 2026-11-08

The founder has confirmed CG6 is done and accepted. CG1–CG6 are complete within
their approved scopes; earlier pending-review, pending-understanding and
pending-founder-acceptance statements are superseded. Implementation, engineering
verification, independent review, R1–R6 corrections and the explanatory document
are complete. No additional CG6 gate is pending in the current project state.

The [final implementation explainer](../validation/cg6/CG6_FINAL_IMPLEMENTATION_EXPLAINER.md)
contains all 16 requested areas, six diagrams, complete source navigation,
execution scenarios, algorithms/statistics, correction explanations and 15 Q&As.
The accepted 230-file runtime identity is
`aa72f09caa5bc5b174db5b4253add54a9fba8b3ecec3309c99f0beb0608fbf6a`.
See [the guide](CG6_CONFIDENCEGUARD.md) and
[completion/evidence status](../validation/cg6/IMPLEMENTATION_STATUS.md).

Actual CPU/MPS evidence remains host/runtime-specific. NVIDIA CUDA implementation
and contracts are complete; actual NVIDIA runtime qualification remains pending
compatible hardware and nonblocking. Historical performance/scientific evidence,
scientific limitations and excluded larger workloads retain their original scope.
This is a documentation/acceptance update, with no code or tests changed and no
new verification campaign. Sealed receipts remain unchanged; their documentation
hashes identify the earlier snapshots. CG7 is not authorized by CG6 acceptance.

## CG6 independent-review corrections — 2026-11-08

Historical correction-pass checkpoint; superseded by the acceptance above.

The founder-authorized bounded R1–R6 corrections are implemented and engineering-verified.
See [the correction report](../validation/cg6/review-corrections-r1-r6/REVIEW_CORRECTIONS.md)
for implementation, corrected-source checks and remaining qualification limits.
Original engineering/wheel/performance receipts remain historical-source evidence.
CG1–CG5 acceptance is unchanged; CG6 understanding/founder acceptance is not claimed.

## Historical CG6 implementation checkpoint — 2026-11-07

The approved CG6 implementation and engineering verification are complete within the recorded Mac profiles. Predictor execution, auxiliary fitting/application, robustness, frozen upstream integration, immutable v2 binary retention and product interfaces are present. CPU/MPS evidence and finite CPU scientific controls are separate from CUDA implementation/contract evidence; NVIDIA runtime qualification remains pending hardware and is nonblocking. See [the implementation guide](CG6_CONFIDENCEGUARD.md) and [live verification status](../validation/cg6/IMPLEMENTATION_STATUS.md). No CG6 founder acceptance or independent review is claimed.

## CG5 completion — 2026-11-06

The founder has confirmed CG5 is fully completed, including implementation,
independent review, R01–R09 and D1–D5 corrections, engineering verification and
the implementation understanding gate. This decision supersedes pending-review,
pending-understanding and pending-founder-acceptance language retained below.
CG1–CG5 are complete within their approved scopes; scientific limitations and
source-specific historical evidence remain unchanged. No CG6 work is implied.

The [final implementation explainer](../validation/cg5/CG5_FINAL_IMPLEMENTATION_EXPLAINER.md) covers architecture, source files,
policy semantics, optimization, statistical assessment, four execution scenarios,
corrections, limitations, glossary and 15 technical questions. Its quick
requirements review found all 13 requested areas present and no material issues
in the technical spot-checks; no test suite was rerun for that document review.
The explained 190-file runtime identity is
`7d3f64affcbc9491223e23294482149848f3bd945a7aaefce33af4af7b3fc3b9`.

## Current project decision — 2026-11-04

CG1–CG4 are complete under the founder-approved scope, CG4 closure revision and
review corrections. Older pending-acceptance statements below describe the historical
review workflow and are superseded by that project decision. Scientific refusals
and original qualification evidence remain unchanged.

CG5 is **not founder-accepted**. The fresh independent review reproduced material
optimization, identity, assessment, economic and historical-scope defects on the
original verified source. The founder authorized a targeted R01–R09 correction pass,
including historical constraint ledgers, hybrid routing/leaf optimization, MILP tie
refinement and admission guidance. Corrections and current verification evidence are
recorded in [the correction ledger](../validation/cg5/review-corrections-20261104/REVIEW_CORRECTIONS.md).
The original 549-test gate and original workload measurements remain historical
source-specific evidence. See [current CG5 contracts](CG5_CONFIDENCEGUARD.md).
Focused independent re-review and founder acceptance remain separate; CG6, a ZIP
and the educational implementation report are not part of this correction pass.

The second focused independent CG5 re-review identified D1–D5. The authorized
2026-11-05 correction pass addresses registered regression inference, global
tolerance nomination, weighted RMSE tie bands, hybrid frontier standing and
interpretable public claims. Current source identity, focused verification and
remaining limits are recorded in [the D1–D5 correction report](../validation/cg5/defect-corrections-20261105/DEFECT_CORRECTIONS.md).
This supersedes earlier correction readiness statements for the prior runtime.
CG5 remains pending focused independent re-review and founder acceptance.

## Historical CG4 review record

## CG4 independent-review corrections — 2026-10-29

The founder approved bounded closure with full investigation functionality and
registered finite-sample confirmation. General inadequately qualified approximate
mean/cluster/ranking methods refuse new formal claims; research failures remain
visible. This is an explicit acceptance-scope revision, not passed qualification.
No new statistical replacement research or automatic 28-panel campaign is authorized
for closure. Read the CG4 scope, supported-method and qualification matrices.

Original reviewed runtime: `2632e65e5b1b98a3902189fd67b441c35cf97b3239ffc36c78faca2f21997ab8`.
The founder authorized the five independent-review findings H1/H2/M1/L1/D1 as
a bounded correction scope. The correction record and new delivery identities
are in `validation/cg4/REVIEW_CORRECTIONS.md`. Original evidence remains immutable.
Corrected runtime: `2247a089ba23fe4c2ea19193c867f0b3f5c65152a9aa995d7b4ab56813339095`.
Corrections are implemented and internally verified; targeted independent re-review
and founder acceptance remain pending.
Original closure: 289 passed / one optional schema-validator skip; the separate
schema environment passed all 63 checks. Sixteen affected checks passed each on
Python 3.12/3.14. Five current-selector synthetic recovery profiles each passed
40/40 under unchanged thresholds. Other unfinished profiles remain unqualified;
landmark promotion failed and the geometric fallback is retained. Old null results
are reused through a documented conditional-independence bridge, not relabeled as
new-selector simulations. Weak fidelity/power and negative evidence are retained.

Original reviewed wheel SHA-256: `929d864aec8ebbcaed774d54e4ab120ae81577ff21a9eedc3e14f2906c36f3ad`.
Delivery evidence is indexed by `validation/cg4/REVIEW_QUICKSTART.md` and the final
closure receipt. Packaging-only documentation does not invalidate runtime evidence.
Initial independent review is complete. Founder-authorized corrections and focused
verification precede targeted independent re-review, the understanding gate and
founder acceptance. No self-acceptance is claimed. CG5–CG7 are outside CG4.

Follow `agents/skills/verify/skills.md`: reuse valid evidence and verify changes
proportionally. Preserve `CG4_IMPLEMENTATION_FINDINGS.md`, its historical record,
source identities, failed experiments and original artifact bytes.

Product status: Classification baseline preserved; M1 shared contracts/unlabeled
profiling, M2 regression, M3 annotation workflows, M4 comparative/scalable analysis, M5 temporal reliability, M6 text reliability intelligence, M7 image reliability intelligence and M9 cross-representation reliability implemented.
M1–M7 completion is accepted by the user. M8 audio is deliberately deferred.
M9 has scoped engineering evidence, without general semantic or capacity guarantees.
ConfidenceGuard CG1 is now implemented: a separate, supplied-prediction workbench
for binary classification, multiclass classification and regression, with Python,
CLI, versioned local JSON API and functional browser workflows. It includes
calibration/high-confidence and supplied-interval evidence, declared cohorts,
authoritative-snapshot paired comparison, fixed-policy replay, protected
investigation and consistent shareable HTML/PDF/JSON. No universal score or model
execution is added. CG1 completion, independent review, corrections and its closed
understanding gate are accepted by the user's subsequent instruction. See
[contracts/methodology](CG1_CONFIDENCEGUARD.md) and [measured evidence](../validation/cg1/README.md).
Project direction: Approved DataTrust expansion architecture and nine-milestone roadmap.
Documentation reset: Completed.

ConfidenceGuard now includes opt-in longitudinal reliability within the same product.
CG3 adds protected projected-fact capture before eligibility filtering, frozen
method outputs, an authoritative SQLite catalog, immutable JSONL evidence,
supervised DuckDB reconstruction, revisions/backfill/as-of maturity and immutable
restatements. Reference/current drift, performance/calibration/uncertainty evolution,
declared-cohort mix, qualified resampling and exploratory temporal investigation
share Python/CLI/API/browser and canonical reporting. Standalone CG1/CG2 and
DataTrust history semantics remain intact. See [CG3 contracts and methodology](CG3_CONFIDENCEGUARD.md).
CG3 is complete, including corrections R1–R3, as confirmed by the user on 2026-10-21.

## What Works Now

- **Interfaces:** public `DataTrust` Python API, `datatrust audit` CLI, and guided
  local Flask browser UI through `datatrust ui`; Python package now requires 3.12+,
  with 3.13 primary and capability-specific 3.14 qualification in progress.
- **Browser workflow:** CSV validation/preview, grouped explainable target
  choices with no preselection, server-enforced acknowledgement for advanced
  targets, automatic binary/multiclass/single-class confirmation, optional
  report context, compact result overview, full HTML view/download, and native PDF.
- **Analysis:** dataset/feature profiling; separate target missingness;
  cell-level and row-level missingness; exact duplicates and feature-identical
  conflicting-label groups; class balance and majority baseline; constants,
  near-constants, cardinality, numeric quartiles/zero/negative/non-finite values,
  IQR outliers, and strong versus review-only name-based leakage evidence.
- **Interpretation:** five transparent sub-scores, uncapped evidence score,
  explained guardrails and final risk band, complete prioritized findings,
  compatible top-three risks, and one deterministic narrative for UI/report.
- **Reports:** canonical standalone eight-topic HTML, print-safe visuals,
  portrait decision pages and landscape technical appendix; Python/CLI/UI PDF
  conversion from canonical HTML using WeasyPrint, plus strict JSON. Humanized fallback titles,
  deterministic grammar, and a designed clean-report state are implemented.
- **Local lifecycle:** loopback-only, single-user UI with process-scoped
  temporary jobs and a configurable default 100 MiB upload limit.
- **Evidence:** three prepared UCI datasets, eight deterministic Adult
  mutations, eleven generated validation reports, reviewed leakage ledger,
  isolated internal Evidently comparison, and preserved historical review records.
- **M1 target-free workflow:** Python specifications/results, conditional CLI
  targets, browser mode and refreshed parsing preview, and eight-topic unlabeled
  HTML/PDF/JSON. All columns participate; no unlabeled scoring policy is invented.
- **M1 disclosures:** bounded source-token fidelity review, explicit parsing
  manifest/source hash, applicability/execution/evidence/coverage, partial reports,
  and configurable operational safeguards with documented enforcement boundaries.
- **M2 regression:** explicit numeric outcome, optional continuous/count expectations
  and range/integer/nonnegative constraints; finite populations, variation,
  quantitative distributions, contextual extremes/concentration/grid evidence,
  bounded copy/affine/two-feature-sum checks, qualified support and availability,
  consolidated relationships, and repeated-input target variation. No scoring.
  Browser confirmation and consistent HTML/PDF/JSON use the shared engine.
- **Artifact lifecycle:** collision-safe no-replace publication, deterministic
  PDF HTML sibling (or explicit path), exact HTML reuse, retained HTML/JSON on PDF
failure, and browser job-owned identity/cache verification and invalidation.

Drivyaansh accepted this baseline on 2026-08-13. The former mandatory external
practitioner-validation round was removed on 2026-08-04. External product and
reader-validation questions remain unresolved; baseline acceptance did not
claim those questions were answered.

## Verified State

Read-only verification on 2026-10-07, before this documentation-only reset:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src .venv/bin/python -B -m pytest -q -p no:cacheprovider
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src .venv/bin/python -B -m validation.verify
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src .venv/bin/python -B -m validation.dry_runs.verify
```

Results at the documentation reset: **70 tests passed**; classification corpus
and historical archive verification passed. M1 verification on 2026-10-09 also
protects exact results and normalized legacy HTML for all eleven classification
cases and checksums for 39 stored evidence files. The separate unlabeled validator
checks known synthetic evidence and label-free German Credit (1,000 x 20), Bank
Marketing (45,211 x 16), and Adult (48,842 x 14). Run it with
`PYTHONPATH=src .venv/bin/python -m validation.unlabeled.verify`.
These are internal engineering checks, not external methodology/customer validation.

M1 verification: **129 tests passed**; classification corpus, historical archive,
and separate unlabeled verifiers passed. A real loopback browser workflow was
exercised; generated PDF text and all nine pages of a long-header report were
visually inspected. Resource defaults are operational safeguards rather than
benchmarked capacity claims. No historical reports were regenerated.

M2 verification on 2026-10-09: **190 tests passed** and all four validators
(classification, historical dry-run archive, unlabeled, and regression) passed.
The regression validator covers 18 pinned public/synthetic cases with independent
quantitative reference checks. Concrete and both Bike tables detect the intended
evidence; Bike component-removed controls pass. Recorded analytical runs took
approximately 0.07 seconds for Concrete, 0.23 seconds for Bike hour, and 0.10 seconds
for Bike day on the recorded local environment, excluding PDF conversion. These
meet the internal 30-second engineering target without establishing capacity guarantees.
Real browser checks cover continuous, count/constrained, ambiguous, bounded, and
partial workflows. All 76 PDF pages across six presentation cases were visually
inspected. Classification legacy results/scores/normalized HTML and historical
artifact hashes remain protected; frozen unlabeled analytical parity also passes.
See `validation/regression/results/verification.json` and the browser/presentation
manifests. These establish internal correctness, not external methodology validity.

Following functional acceptance, the narrow M2 presentation cleanup passes
**193 tests** and all four validators. Executive population metadata is rendered
as prose with single punctuation, empty relationship/example tables have explicit
empty states, and configured source-token limits are labeled expected coverage.
Eight affected pages across four PDF exports were visually inspected; each export
retains an identical saved analytical result. Evidence is under
`validation/regression/results/presentation_cleanup/`. This is the preserved pre-M3 baseline.

Stored corpus results cover German Credit (1,000 × 21), Bank Marketing
(45,211 × 17), and Adult (48,842 × 15); all eight mutation assertions passed.
All eleven reports contain eight topics and recorded generation under 30 seconds.
Detailed timings are historical descriptive measurements, not production
benchmarks or new measurements from this reset.


## M3 Delivered Behavior And Verification

- Strict multi-target TaskSpec and explicit feature/target/metadata/ignored roles;
  source-order normalization and effective-policy compatibility preserve legacy outputs.
- Independent annotation expectation, actual observation, and declared status;
  default unknown expectations in new workflows, intentional/uncertain distinctions,
  per-target/row/group coverage, and bounded population contrasts.
- Multilabel indicator decoding, complete/partial vector evidence, cardinality,
  density, pairwise matched populations, constraints, and repeated-input consistency.
- Reused M2 numerical primitives across outputs, shared relationship budgets,
  finite-vector coverage, declaration unions, and separate output dependencies.
- Conditional feature geometry, categorical/identifier exclusions, scale/sparsity,
  repetition, and marginal anomaly-candidate context without fitted models/verdicts.
- Guided Python/CLI/browser specifications, schema 1.2, completed-result exports,
  compact HTML/PDF projections, and full computed JSON evidence.

M3 tests freeze the current working tree's completed M2 analytical/HTML results,
retain M1/classification fixtures and historical checksums, and independently
assert annotation truth tables, group denominators, indicator mathematics,
Pearson, constraint logic, numerical precision, coding semantics, bounds, and
interface equivalence. Public validation pins Energy (768 × 10), Scene
(2,407 × 300), and Linnerud (20 × 6), plus controlled partial, unsupervised,
empty, and wide derivatives. Source/member/prepared hashes and available license
information are under `validation/m3/manifest.json`.

Measured results, final PDF page budgets, runtime/frame/result sizes, artifact
hashes, browser checks, and visual QA are recorded under `validation/m3/results/`.
These are internal correctness and readability checks; they do not establish
label correctness, model performance, external score validity, or customer value.

## Important Artifacts

- [Usage and installation](../README.md), [methodology](../METHODOLOGY.md),
  [architecture](ARCHITECTURE.md), and [strategic context](NUMEK_MASTER_CONTEXT.md).
- [Synthetic example CSV](../examples/loan_data.csv) and
  [generated example report](../examples/report.html).
- [Validation reproduction guide](../validation/README.md), prepared data under
  `validation/data/prepared/`, controlled inputs under `validation/data/mutations/`,
  and generated reports under `validation/reports/`.
- [Corpus results](../validation/results/MILESTONE_2_SUMMARY.md),
  [leakage ledger](../validation/results/leakage_review.csv),
  [machine-readable summary](../validation/results/validation_summary.json), and
  [internal Adult comparison](../validation/comparison/ADULT_COMPARISON.md).
- [Historical review archive](history/reviews/README.md),
  [dry-run workspace](../validation/dry_runs/README.md), and
  [returned RC_003 review caveats](../validation/dry_runs/evidence/RC003_TECHNICAL_REVIEW_SUMMARY.md).
  Candidate records remain under `validation/dry_runs/release_candidates/`;
  packet ZIPs/manifests remain locally under the ignored `validation/dry_runs/packets/`.

The returned reviewer HTML files are described by the evidence summary; they
were not copied into the repository. Historical six-section review artifacts
remain distinct from the current eight-topic reports.

## Current Implementation Limitations

- CSV classification, partial annotations, multilabel indicators, multi-output regression,
  role-aware profiling, clustering/anomaly readiness, split audits and version comparisons.
  M5 adds temporal CSV/Parquet reliability; M6 adds text CSV/JSONL reliability,
  local references and opt-in offline language/embedding models. There is no
  prediction-performance analysis, live longitudinal monitoring or general image/audio engine.
- Regression has no validated overall score, sub-scores, risk band, or readiness verdict.
  Arithmetic relationships are bounded, support-qualified observations; feature
  availability is declared/unknown. General nonlinear/multifeature dependency
  mining and instrument-resolution/quantization semantics are deferred.
- Single-user, non-persistent local UI; no hosted service, accounts, persistent
  service database or saved report history. M4–M6 use owned temporary DuckDB databases,
  one supervised worker and explicit source/configuration reconfirmation.
  Automatic server reloading is disabled.
- HTML/PDF/JSON in all interfaces. Word export and a demo notebook are not implemented.
- WeasyPrint may require native font/rendering prerequisites. Default pandas
  analysis materializes data in memory; opt-in M4 and dedicated M5/M6 analysis use bounded
  raw ingestion and disk-backed DuckDB relations, with storage and I/O costs.
- Legacy cooperative safeguards and M4–M6 disk/RSS/deadline supervision are not
  hard process quotas or capacity guarantees. Native operations and monitoring
  can overshoot; source shape/cardinality and available disk constrain execution.
  See usage/methodology for per-source versus combined limits and replacement semantics.
- Heuristic leakage and comparative effects require domain/provenance review.
  M4 implements bounded feature dependencies, missingness patterns and declared
  segments, plus schema/population changes across versions. Proven label error,
  missingness mechanisms, fairness, model calibration, semantic-date/fuzzy-category
  matching and unrestricted nonlinear/subgroup mining remain outside scope.
- Independent market usefulness, reader comprehension, sharing workflows, and
  external score-defensibility evidence remain open product questions.
- Reports do not establish safety, legal compliance, fairness, certification,
  or model correctness.

These limits describe today's implementation and can change through deliberate,
verified product development.

## M3 Internal Verification (2026-10-09)

The complete suite passed 271 tests. After the final presentation and iteration
changes, the focused M3 suite passed 77 tests; the isolated minimum-dependency
suite passed 75 independent M3 tests. All four existing validators and fifteen
pinned M3 cases passed, with classification/M1/M2 parity and historical artifact
hashes preserved. Seven real browser workflows completed, including the explicit
expected-annotation declaration that retains legacy classification behavior.

Every final PDF page was visually inspected: 39 pages across six presentation
cases and six pages from the real browser regression download. Scene is eight
pages and the wide synthetic report is twelve; both meet their page budgets.
Final report refreshes reused completed JSON without reanalysis. Recorded
analytical runs met the internal 30-second target; timings are not capacity
guarantees. See [verification evidence](../validation/m3/results/verification.json),
[presentation review](../validation/m3/results/visual_qa/manifest.json), and
[browser evidence](../validation/m3/results/browser/manifest.json).

## M4 delivered behavior and closure (2026-10-10)

Split, version and advanced standalone workflows share one DuckDB path, with
schema 1.3, declaration-aware lexical identity, full structural populations,
bounded task-family diagnostics, effects/support-led comparisons and optional
qualified inference. Python, manifest-relative CLI and guided local browser flows
export completed HTML/PDF/JSON. Existing pandas contracts and score formulas remain
preserved; comparisons have no aggregate score.

Disk preflight, allocated/logical inode accounting, per-source and combined limits,
phase reservations, spill budgets and parent-supervised RSS/deadline/cancellation
controls are implemented. Resource controls can overshoot; capacity is not guaranteed.
The 64 GiB workspace ceiling is a budget, not a requirement for every job.

Closure ran the full pytest suite and classification/archive, unlabeled, regression,
M3 and new M4 validators. Historical hash checks preserved 194 files. Subsequent
focused M4 verification covered final identity/statistical/report fixes. Real browser
split/version/advanced flows, downloads, configuration retention and cancellation
were exercised; a test-only fixture covered partial exports. All 25 final pages of
six PDF cases were inspected, with one-page executive sections and four/five-page
ordinary, wide and long-header reports. Human projection bounds never discard PDF
pages or computed JSON records.

The recorded 16 GB laptop measurements cover approximately 1 and 5 GiB combined
four-column CSV inputs, a 512 MiB spill-heavy long-key split job and exact quantiles
under 32 MiB engine memory. They establish measured behavior for those workloads,
not arbitrary width/cardinality or exhaustive advanced-search capacity. A retained
128 MiB allocation failure makes that limitation explicit.
See [M4 evidence](../validation/m4/README.md) and its result manifests.

## Previous M4 handoff context

Review M4 thresholds, optional-statistics packaging, local-file roots and resource
defaults against the founder's intended use. M1–M3 acceptance is settled. M4's
internal checks do not establish external method validity or guarantee capacity.
At that historical handoff, time-series/text work was still future scope. M5
and M6 now implement those capabilities; default-engine replacement, later
modalities and prediction-performance work remain separate decisions.
The 2026-10-11 constraint, role-change and narrative corrections received source-only
review; execution verification was not repeated for this pass.


## M5 temporal reliability — current implementation

M5 now exposes DataTrust.audit_temporal, `datatrust temporal`, and a dedicated local browser workflow. It includes exact clocks/DST, CSV/optional scalar Parquet, independent temporal semantics, full chronology/schedule/lifecycle/panel populations, feature-bound availability and exact-observation revisions, target maturity, supplied static/rolling evaluation plans, configurable window/run/volatility/seasonal/panel/multivariate investigation and canonical HTML/PDF/JSON. Schema 1.4 has no universal score.

Shared changes are confined to worker supervision, private workspace phase planning, pure distribution mathematics, explicit artifact dispatch and application-level browser worker exclusion. Existing public M1–M4 inputs and classification policies remain unchanged. Read [M5 implementation and limits](M5_TEMPORAL_RELIABILITY.md) and [new verification evidence](../validation/m5/README.md). M4's earlier execution closure and subsequent source-only corrections remain separate historical evidence.

M5 implementation and its recorded verification remain historical evidence. Remaining resource and threshold uncertainties are declared engineering/research limits, not claims of universal temporal defects. See the M5 evidence ledger for its execution, reused evidence and historical distinctions.

## M6 delivered capability — 2026-10-11

M1–M5 completion and M5’s understanding gate are accepted by the user. M6 adds
explicit CSV/JSONL text, token/span/QA, generation, conversation and retrieval
contracts through Python, CLI and `/text`, with canonical HTML/PDF and strict JSON.
Required population accounting remains separate from bounded lexical, duplicate,
passage, language and semantic investigations. Local E5-small and Lingua adapters
work offline; Unicode and model/runtime identities are pinned.

Private-default exports bind opaque references to a separate protected manifest.
Exact local resolution, explicit bounded excerpts, integrity checks, artifact
collisions, cache separation and owned cleanup are implemented. There is no text
score, cloud inference or general multimodal ingestion. The four-image fixture
checks only pairing/media/provenance.

The original repository suite passed 385 tests; an additional browser cancellation
regression also passed. Public-corpus accounting, 100 MiB/1 GiB execution, nested
annotation, asset-heavy and model-enabled measurements are recorded under
`validation/m6/results/`. Final presentation/browser and closure records identify
new versus reused evidence, including visual review of all 53 representative PDF
pages. These establish internal engineering confidence,
not universal candidate recall or external product validation. See
[M6 methodology](M6_TEXT_RELIABILITY.md). Historical M1–M5 evidence is preserved.

The focused independent-review corrections subsequently passed **400 repository
tests in 33.51 seconds**, including fourteen new allocation, accounting, witness,
synthesis and unexpected-failure controls. Comparison-side reservations and
split-aware strata replace the earlier global selection limit; embedding coverage
qualifies endpoint shortfalls. Reprojection of completed evidence reduced the five
representative PDFs from 53 to 39 pages, with all pages visually reviewed and all
eight analytical topics retained. Earlier source analytics and capacity/calibration
records remain unchanged; they do not certify the corrected allocation's capacity.
See [correction record](../validation/m6/REVIEW_CORRECTIONS.md). Unexpected optional
faults retain documented whole-audit atomic failure. M7 implementation is now recorded below.


## M7 delivered capability — 2026-10-12

Image Reliability Intelligence has distinct schema 1.6 contracts, secure per-file
immutable evidence, separate assets/occurrences/annotations, explicit frame/taxonomy
compatibility, disk-backed full signature indexing, bounded candidate search,
opt-in offline models, private reports and guided local investigation. Required
failures remain atomic; an isolated optional model fault can return verified
partial core evidence. Portable disclosure requires separate explicit selection.

[Methodology and interfaces](M7_IMAGE_RELIABILITY.md) and the [closure evidence](../validation/m7/README.md)
record benchmark selection, failed model settings, measured search/media costs,
PDF page inspection, browser execution and historical compatibility. Defaults are
resource safeguards, not general capacity guarantees. M1–M6 behavior and historical
artifacts remain preserved. Audio remains deferred; M9 is recorded below.

## M9 delivered capability — 2026-10-13

`DataTrust.audit_cross_representation()`, `cross-representation`, `cross-evidence`,
`cross-review` and the dedicated browser workflow connect local records, text,
native PDF/DOCX and M7 images. Reusable label/section/table recipes, exact
identities/cardinality/context/clocks, decimal/date/unit reconciliation, competing
evidence and declared separation/ancestry produce explainable evidence. The
browser previews at most 20 documents, confirms frozen declarations/sources,
inspects exact native locators and handles independent reviewer snapshots.

Schema 1.7 has no score. Default HTML/PDF/JSON omit source values, claims, paths
and notes; protected manifests resolve originals without storing a document
corpus. Confirm/dismiss/unresolved decisions bind exact results and cannot change
analytical counts. Pinned local CPU model profiles are narrowly qualified for
authored financial English PDF/DOCX and supplied COCO caption associations;
unsupported populations abstain. General natural-document accuracy is not
established. OCR, audio/video, unrestricted verification, model monitoring and
persistent review services are excluded.

Measurements: 10,000 field reconciliations/50 native PDF pages in about 24 seconds;
one million records/five million associations with context checks and 1,000 native
PDF pages in about 486 seconds, 2.36 GiB peak sampled worker RSS and 2.98 GiB peak
workspace. The latter measures association/context/extraction, not million-record
field reconciliation. Concurrent verification load and simple authored pages
limit extrapolation. See [M9 behavior](M9_CROSS_REPRESENTATION_RELIABILITY.md) and
[verification](../validation/m9/README.md). Existing milestone evidence is preserved.

## ConfidenceGuard CG1 verification — 2026-10-17

Full repository suite: 526 passed. Subsequent isolated CG closure additions: 27
focused tests passed; final report-label checks passed. All 24 independent metrics
across pinned German Credit, Wine and Concrete predictions match. JSON Schemas and
synthetic transport examples/results validate. Binary paired, multiclass and
regression browser flows, exact resolution and exports were exercised. Six report
variants (83 pages) received rendered visual inspection. Wheel contents and existing
corpus/historical checksums pass. Shared DataTrust analytical engines were unchanged.
Ordinary/wide probes measured about 10.5/9.6 seconds, with no observed spill; capacity
ceilings and natural production workloads remain unestablished. See the CG1
verification ledger for executed versus reused checks and precise qualifications.

## ConfidenceGuard CG1 first-review corrections — 2026-10-18

Focused corrections bind population provenance to frozen input/intersection lineage
and checked eligibility counts, with explicit class/high-confidence and paired
conditional supports. Conservative exports withhold exact ROC/PR/native-score
details while preserving exact authorized local evidence and scalar ranking.
Safe findings, blockers, method checks and limitations now survive portable output.
Result/API major versions remain unchanged through qualified additive fields.

New verification: 50 CG1/legacy-web tests passed, then all 11 focused regressions
passed including one added interval-remapping case (51 distinct affected tests).
All 24 pinned reference metrics pass; 717 matched historical analytical records
retain scalar values/value states. Updated reports have zero population-ledger
mismatches. JSON Schema and real PDF privacy checks pass; 49 selected PDF pages
were inspected. Ordinary/wide probes took 11.48/9.20s with no observed spill;
concurrent verification load limits timing comparisons. All 93 DataTrust source
files match the correction-start snapshot. The earlier full suite/browser/model
qualification was not rerun or reclassified as new evidence. See
[focused correction handoff](../validation/cg1/REVIEW_CORRECTIONS.md).
Acceptance was pending at that historical handoff. The user's subsequent
authorization accepts CG1 and its closed understanding gate; CG2 implementation
now extends that corrected foundation, as recorded below.

## ConfidenceGuard CG2 implementation — 2026-10-19

CG2 adds probability calibration (identity, monotone Platt, isotonic, monotone beta,
temperature and qualified regularized Dirichlet), deterministic LAC/APS/RAPS,
split/normalized regression and signed CQR. It reuses CG1 snapshots, normalized
relations, reducers, evidence lineage, supervision, disclosure and reports.
No separate analytical engine, auxiliary predictor training or DataTrust migration.

Versioned CG2 contracts keep F/S/C/E explicit, freeze family-wide common selection
inputs and metric-specific comparison populations, and retain application failures.
Exact decimal conformal ranks and tagged unbounded thresholds round-trip safely.
Quantile/sample scoring, qualified calibration diagnostics, coverage/efficiency,
paired/cluster bootstrap and nominal/BCa-adjusted tail/resource admission are added.
Fitted methods, application artifacts and independent assessments remain distinct.
Protected membership sidecars enable later overlap checks; parameter-only imports
disclose unavailable checks. Reapplication remains unvalidated.

Python/CLI/API/browser fit, apply, study and supplied-uncertainty workflows use the
existing local session/CSRF/revision/confirmation/worker-lock boundary. Canonical
JSON/HTML/PDF use one disclosure projection. Historical CG1 evidence remains intact.
CG3 now implements longitudinal reliability within the same product. CG4 is undergoing founder-authorized independent-review corrections; CG5–CG7 retain their future boundaries. CG1/CG2 completion, independent review,
corrections and closed understanding gates are explicitly accepted by the user. Engineering evidence and operating limits
are documented in [CG2 evidence](../validation/cg2/README.md); details and usage in
[CG2 contracts](CG2_CONFIDENCEGUARD.md). Internal qualification does not assert
universal method superiority, production capacity or a new accepted understanding gate.

CG3 is complete, including corrections R1–R3, as confirmed by the user on 2026-10-21. See [correction record](../validation/cg3/review-corrections/README.md).
