# CG7 independent technical review: what was wrong and what was fixed

**Review:** 2026-11-27, against the CG7 closure (S1–S10) on branch `cg7/s10-closure` at `e3d6c741` plus the
uncommitted S10 work. **Corrections:** 2026-11-27, same branch, committed together with S10.

**Authority:** the founder-approved CG7 plan (sections A–Q plus Addendum R2). The review verdict was
**CORRECTIONS REQUIRED**: the platform foundation, publication protocol, fencing, governed reader, SM1/SM2 kernels,
qualification and migration were found sound; four bounded problems and a provenance gap had to be fixed before the
understanding gate. This file is the durable record for later sessions: read it before changing monitoring standings,
backups, routed facts or the closure report.

## Summary

| ID | Severity | What was wrong | Fixed by |
|---|---|---|---|
| B1 | Blocking (scientific contract) | SM2 recovery tests were always formal, skipping the R2.5 admission rules | Shared admission function; descriptive claims never recover |
| B2 | Blocking (durability) | Backups carried only object data keys: reserve, channel and order secrets and the config were lost on restore | Keyring carries every live secret; config included; `ops backup create` |
| B3 | Blocking (verification) | The mandatory incrementality gate was established for close-phase windows only | Runner gates both phases; routed maturity phase measured (see B3) |
| B4 | Blocking (documentation) | The closure report said "everything in plan F.1 is implemented" | Report §1/§5 and CG7 doc list what is not implemented |
| P | Provenance | Closure gate ran on an uncommitted tree with no recorded identity | S10 and these corrections committed; gate rerun on that source |
| N2 | Non-blocking | Route integrity of routed facts relied on producers only | `publish` refuses routed facts without an opportunity key |
| N5 | Non-blocking | No sign-in throttling; `/metrics` unauthenticated | Per-name soft lockout (migration 0015); metrics loopback-or-auth |
| N7 | Non-blocking | Restore silently marked any missing object `reclaimed` | Restore refuses unless the object is an excluded processed raw batch |
| N8 | Non-blocking | Two investigation templates ran the same CG3 analysis twice | Shared logical fingerprint (`same_analysis_as`) |
| N9 | Non-blocking | New object-store directories were not fsynced in their parents | Parent directories synced on creation |
| R2.4 | Contract gap (part of B4) | Comparability used label availability only; reference/stream entity overlap not measured | Invalid-outcome and late rates compared; overlap measured and shown |
| Map | Non-blocking | Coverage map always showed regions `not_configured` (stale "S7" note) | Regions coverage from real region detectors; policy note corrected |
| L | Found during verification | A recovery claim made while its condition was active waited a second tick after quiescence; one cycle's outcome depended on the random unit order | Condition transitions chain within one tick |

## B1. SM2 recovery claims skipped admission (R2.5)

**Wrong.** `definitions.start_recovery` inserted every SM2 detector with standing `formal`, and
`runtime._claim_signal` always emitted standing `F`. SM1 on the same definition is downgraded to descriptive for
`mature_as_of` maturity or for `event` units without an independence declaration; SM2 never was, although R2.5
requires "the same predictable-inclusion, comparability, unit and bounds rules as R2.4". A formal
`threshold_recovery_established` / `reference_noninferiority_established` could therefore resolve an incident where the
contract allows only descriptive standing. The confidence-sequence arithmetic itself was valid; the standing was not.

**Fixed.**
- `monitoring/definitions.py`: `design_reasons(definition, phase)` (shared with SM1's `plan_detector`) and
  `recovery_admission(definition, statistic, claim, record)`. `start_recovery` stores the resulting standing and reasons.
- `monitoring/runtime.py`: `_claim_signal` emits `F` only for a formal test; otherwise a `descriptive_recovery_indication`
  (standing P, worded "not recovery evidence"). `recovery_not_established` follows the detector standing.
- `incidents/conditions.py`: a non-F recovery signal records a `descriptive_recovery_indication` event and never changes
  the condition's state or recovery.
- `interventions/verification.py`: a descriptive claim settles as `not_established` (`claim_not_formally_admitted`);
  `feasibility` reports R2/R3 claims that could only be descriptive, so such proposals fail `verification_feasible`.
- Tests: `test_review_corrections.py::test_recovery_admission_follows_the_sm1_rules`,
  `::test_descriptive_recovery_test_never_recovers_its_condition`.

## R2.4 comparability and reference/stream overlap (part of B4)

**Wrong.** Alarms compared only label availability with the reference; R2.4 also names late, invalid and thinning
rates, and requires the reference/stream entity overlap to be measured and shown. It was stated as an assumption only,
while `CG7_SEQUENTIAL_METHODS.md` claimed it was measured.

**Fixed.**
- `runtime._comparability` (per detector and window): label availability and invalid-outcome rate (maturity phase,
  `inclusion_tolerance`, default 0.1) and late-exclusion rate (`late_tolerance`, default 0.01). `shifted` lists the rates
  beyond tolerance and the alarm wording names them. Entity-first thinning is deliberately **not** compared (the stream
  accumulates repeat entities over months; the reference covers one period), and this is documented.
- `references.summarize` stores 64-bit prefixes of the reference's detector entity hashes; `references.entity_overlap`
  measures each window's overlap; alarms, claims and window packets carry it, and the independence assumption shows the
  measured overlap. References built before this change have no digests and report `None` (not measured).
- Test: `::test_alarms_show_comparability_and_reference_entity_overlap`.

## B2. Backups lost operational secrets (R2.2)

**Wrong.** `backup.create_backup` built the keyring from `objects.key_id` only. Not backed up: sealed-reserve HMAC
secrets (`reserves/…`), notification channel secrets (`notify/…`), the per-deployment unit-order secret
(`monitoring-order/…`), the audit-sampling secret (`ops-audit/…`), live data keys no included object referenced
(today's raw-batch key once its batches were processed), and the installation configuration (the CLI never passed it).
After a restore into a fresh secrets store, publishing a new entity in a reserved namespace failed with
`secret_missing` (fail-closed, so the reserve was never compromised, but ingestion stalled), webhooks could not be
signed, and the order secret was silently regenerated. The existing restore tests had no reserve and no channel.

**Fixed.**
- `numek_platform/secrets.py`: `FileSecretStore.names()`; `export_keyring(..., names=...)`.
- `numek_platform/backup.py`: the keyring holds the required data keys (still refusing if one is missing), every other
  live data key still present, and every operational secret. The manifest lists the secret classes and the config digest.
- `confidenceguard ops backup create --installation … --destination …` takes the cut with the installation's config;
  `numek backup create` gained `--config`. `deploy/README.md` and `docs/NUMEK_PLATFORM.md` describe it.
- Test: `::test_backup_carries_every_secret_a_restored_installation_needs` (reserve + channel; after restore a new
  entity publishes, today's key encrypts, the channel and order secrets are identical).

## N7. Restore of an incomplete backup

**Wrong.** Any active object missing from the backup was marked `reclaimed`, relying on the manifest alone.
**Fixed.** `restore_backup` refuses with `backup_invalid` unless the missing object is a processed raw batch the cut
excludes by rule. Test: `::test_restore_refuses_a_backup_that_lacks_an_evidence_object`.

## B3. Incrementality gate measured on one phase

**Wrong.** R2.8 gates "window cost at the largest versus smallest admitted history ≤ 1.3×". The closure reported
"Pass: 1.15", which was the close phase only. The maturity phase (outcome detectors) was last measured at 1.44 on the
unrouted layout and never on the routed one.

**Fixed.** `validation/cg7/workload_run.py` now gates both phases. A fresh routed W-DEV-S1 run on the corrected source
(new preflight, 4 workers, same 1-day reference and conditions as S10) measured:

| Measure (W-DEV-S1, routed layout, corrected source) | Result | Objective |
|---|---|---|
| **Incrementality, close phase** (median of last 7 windows, 90 d ÷ 30 d) | 7.43 ÷ 6.60 s = **1.126** | ≤ 1.3: **passes** |
| **Incrementality, maturity phase** (same rule) | 6.73 ÷ 5.95 s = **1.131** | ≤ 1.3: **passes** |
| Durable ack p95 (10k-row batch, 90 batches) | 0.18 s | < 2 s: met |
| Live publish lag | about 18–19 s | p95 < 5 min: met |
| Daily window p50 / p95 | close 7.3 / 9.7 s; maturity 6.7 / 8.2 s | < 2 min at W-REF size: not measured at that size |
| Restart to ready | 0.91 s | < 60 s: met |
| Database bytes per indexed fact | 1,421.9 | ≤ 150: **not met** (unchanged) |

All windows held 10k units; 0 failed batches; 4.75M facts at the end. Records:
`validation/cg7/results/review_corrections/w-dev-s1-routed.json` and its admitted preflight
`w-dev-s1-preflight.json` (development Mac; P-SERVER, W-DEV and W-REF still not measured). Ack, publish lag and restart
are now measured on the routed layout too (S10 had measured them unrouted).

## B4. Closure report overstated completeness

**Wrong.** §1 said "Everything in plan F.1 is implemented". §5 omitted: policy monitoring (G.2); coverage-miss and
deferral statistics (so uncertainty coverage is not monitored); the R2.4 comparability and overlap gaps (now fixed);
the refusing CG5 policy-replay and CG2 recalibration investigations; the verified v2 backup at freeze (R2.6). It also
said only W-REF-sized windows are blocked by the phase-result budget; W-DEV-sized windows are too.

**Fixed.** `validation/cg7/CG7_IMPLEMENTATION_REPORT.md` §1 and §5 and `docs/CG7_CONFIDENCEGUARD.md` ("Not implemented
in CG7") now list them. Not implemented, by founder scope and still disclosed: policy monitoring, coverage-miss and
deferral statistics, executable CG5/CG2 investigation templates, the pre-freeze v2 backup.

## Non-blocking corrections

- **N2 route integrity** (`evidence/publish.py`). Migration 0014 partitions predictions and context by their
  opportunity key. A routed fact without one would route by its own key, so one identity could occupy two partitions
  and escape the per-partition unique and no-fork indexes. `publish` now refuses such facts (`route_undetermined`),
  except migrated, already purged facts. The key must still equal identity[0]: ConfidenceGuard capture enforces that;
  the database cannot hash identities. Test: `::test_routed_facts_must_name_their_opportunity`.
- **N5 sign-in and metrics** (`identity`, `operations/api.py`, migration `0015_login_failures.sql`). 10 failed sign-ins
  per name in 15 minutes give 429 with `Retry-After` (failures recorded in their own transaction). `/metrics` is open to
  loopback, otherwise needs a principal with read permission. Test:
  `::test_sign_in_is_throttled_after_repeated_failures_and_metrics_need_loopback_or_auth`.
- **N8 duplicate investigation** (`intelligence/templates.py`, `planner.py`). `cg3_cohort_contrast` declares
  `same_analysis_as: cg3_mix_decomposition`; the planner's logical fingerprint uses the analysis, so the second is a
  duplicate or a reuse. Existing installations rerun such analyses once (their earlier fingerprints differ).
- **N9 directory durability** (`objects.py`). Newly created `objects/<org>/<xx>` directories are fsynced in their parents.
- **Condition lifecycle (found while verifying)** (`incidents/conditions.py`). The first full platform run after the
  corrections failed `test_interventions.py::test_verification_resolves_the_incident_with_outcome_evidence` once and passed
  on rerun. Cause: an established claim that arrived while its condition was still active was stored as pending; the tick
  that made the condition quiescent did not apply it, so it stayed quiescent until the next tick. Whether the claim
  arrived before or after quiescence depended on the per-installation random unit-order secret. `tick` now chains
  transitions (each its own event). Test: `::test_a_pending_recovery_is_applied_in_the_same_tick_that_makes_the_condition_quiet`.
  The same run's `test_execution.py::test_child_publishes_evidence_under_its_fence` failed because its fixture published a
  context fact without an opportunity key; the fixture now names one (N2).
- **Coverage map** (`monitoring/health.py`). Regions coverage comes from region-membership and region-restricted
  detectors; only policy is reported as not implemented.

## Not changed (founder decisions or out of scope)

- Storage of about 1,450 database bytes per fact against the ≤ 150 objective.
- The phase-result budget (about 20k units per phase).
- Linux / P-SERVER, W-REF and W-DEV qualification (not admitted on this host; W-DEV is also software-limited).
- Close windows reserve with purpose `monitoring_outcome` (conservative over-recording of exposure).
- D-1 (no installation-wide backup for workspaces bound to a shared installation).

## Verification

Environment: `validation/cg7/py313.nosync` (Python 3.13.17), P-LOCAL PostgreSQL clusters, this development Mac. Each
suite in its own pytest session, on the corrected source (CG4 and CG5 with `--import-mode=importlib`).

| Suite | Result |
|---|---|
| `tests/platform` (final source, after the lifecycle fix) | **224 passed** (215 at S10 closure + 9 in `test_review_corrections.py`) |
| `tests/platform/test_interventions.py` + `test_execution.py` | 18 passed, three consecutive runs (after the race fix) |
| `tests/cg1` | 38 passed |
| `tests/cg2` | 43 passed, 1 skipped (pre-existing) |
| `tests/cg3` | 67 passed |
| `tests/cg4` | 312 passed |
| `tests/cg5` | 109 passed |
| `tests/cg6` | 104 passed, 10 skipped (hardware) |
| Workload gate (B3) | close 1.126, maturity 1.131: passes |

CG1–CG6 ran before the condition-lifecycle fix, which touches only `operations/incidents/conditions.py` (no CG1–CG6
code path), so their results stand. DataTrust was not rerun: no DataTrust file or shared supervision code changed, and the
S10 closure established its failure set is identical to the committed baseline. Qualification (M.2) is unaffected: the
SM1/SM2 kernels in `eprocess.py` are unchanged.

