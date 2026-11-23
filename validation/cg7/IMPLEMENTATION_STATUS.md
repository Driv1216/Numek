# CG7 implementation status

The technical authority is the founder-approved CG7 plan: revised plan sections A–Q plus Addendum R2. This file
records what is implemented and what evidence exists, stage by stage. Several kinds of standing are kept separate:
engineering correctness, statistical qualification, resilience, measured performance, product completeness,
independent review and founder acceptance.

## S7: intelligence (2026-11-23). Implemented; closure gate passing.

### Implemented (plan I.1–I.9 except response comparison, G.5–G.7, R2.7)

**S7a: regions, structural links, priority v2.**
- **Frozen CG4 regions.** A definition declares regions (an id, a frozen membership artifact, and a source standing:
  `H-confirmed`, `S-selected` or `exploratory`).
  - **Application:** structured gates are applied to each unit's declared context with CG4's own `apply`, giving
    member, nonmember or unavailable. This uses covariates only, so a region restriction is predictable inclusion.
    Diagnostic and geometric gates are refused (`region_kind_unsupported_in_monitoring`).
  - **What they enable:** a new outcome-free `region_membership` (exposure) statistic; a `params.region`
    restriction on any statistic, with its own region-scoped reference (`statistic@region`); region shares in
    packets.
- **Structural links.** Field dependencies come from:
  - CG4 gate features;
  - CG5 policy predicate inputs (from a declared frozen `PolicySpec`);
  - CG6 predictor-spec inputs;
  - missing-field detectors, drift rules and cohort rules.

  A structural link joins conditions alongside `exact` and `population_overlap`, recording the shared inputs and
  "not a common cause".
- **Priority table `cg7_priority_v2`** adds impact axes: affected units, region share and region source standing.
  A formal alarm scoped to an S-selected or exploratory region is capped at P2. A region with under 1% of traffic
  is capped at P2. The impact is recorded with its basis.

**S7b: hypotheses, differential matrix, requirements, triggers.**
- **The catalog** (H-COMP, H-WITHIN, H-INTEG, H-DEPLOY, H-CALIB, H-UNC, H-POLICY, H-LABEL, H-MULTI, H-MON) is data.
  Each entry has machine-checkable supporting and contradicting observations, required observations, and
  executable discriminating templates; a consistency check is tested.
- **15 deterministic observations** cover identity, integrity, composition projection, within-group change,
  calibration accountability, label availability, health, regions, other deployments, policy and domain shift.
  - Each is `True`, `False` or `None` with a standing, its evidence, and, when `None`, a reason, an ETA or an action.
  - Completed investigations settle observations, keeping their id.
  - Absence of alarms is not evidence: with no open integrity condition, integrity stays unknown until the
    contract diff checks it.
- **States:** supported, contradicted, contested, unresolved, proposed, untestable. They are recomputed with every
  knowledge revision, and each change is an incident event.
- **The differential matrix** (✓ / ✗ / ? with standing) is in every revision packet.
- **Information requirements** carry an ETA (label maturity) or an action. **Deferred triggers** queue the
  template when the ETA passes. When the evidence arrives and has already decided the hypothesis, the requirement
  is marked satisfied without a run.

**S7c: planner, templates, recurring patterns.**
- **The planner:**
  - candidates come from templates' `discriminates` over movable hypotheses;
  - value is Σ weight, with weight 2 for F or D support;
  - selection is greedy by value per minute, with deterministic ties;
  - tiers: `auto`, `confirm`, and `restricted` (which needs `reserve:consume`);
  - budgets: 30 auto minutes per deployment per day, counting planned runs; 5 auto runs per incident; a 24 h
    cooldown;
  - fingerprint dedup;
  - the R2.7 reuse rule: only additional units, no corrections, outcome revisions or tombstones, and under 20% new
    support, gives a reuse marked stale; otherwise it reruns;
  - every candidate's reasoning is recorded.
- **Executors:**
  - `contract_diff`: contract versions, quarantine rate, feature retention;
  - `label_availability_audit`;
  - `monitoring_health_review`;
  - `cg3_mix_decomposition` / `cg3_cohort_contrast`: a CG3 longitudinal analysis with the mix/within split;
  - `domain_classifier`;
  - `label_acquisition_guidance`;
  - `cg6_shadow_replay`: retained raw rows in the span replayed through the registered predictor via the S4 audit,
    on approval with `logged_outputs`.

  `cg5_policy_replay`, `cg2_recalibration_study` and `cg2_uncertainty_study` refuse explicitly (operator spec
  required; restricted, S8; not monitored).
- **Results** are immutable packets. Each completion appends a knowledge revision.
- **Recurring patterns:** deterministic typed signatures (deployment, condition keys, structural inputs, supported
  hypotheses, deployment-event kinds), matched at Jaccard ≥ 0.6, shown with each resolution and its verification.

**S7d: domain classifier, label guidance, calibration-transfer diagnostic.**
- **The G.7 domain classifier:**
  - one row per entity per arm, in keyed order; entities in both arms are excluded and counted;
  - declared features only, with outcome and identifier names refused;
  - a keyed 50/50 split; HistGradientBoosting (CG6 pin) fit on half A;
  - descriptive held-out AUC with no interval, permutation importance, and domain-probability calibration;
  - an exploratory exact permutation test (10,000 permutations, average-rank ties), refused below 300 entities per
    arm in half B;
  - reads covariates only under `covariate_inspection` reservations, which are consumed.
- **G.6 Neyman allocation** (n_g ∝ w_g√(r_g(1 − r_g))), with the random-within-strata requirement and expected
  half-widths. The exposure × excess list is labelled a heuristic.
- **G.5 / R2.7 Poisson-binomial calibration-transfer diagnostic** on matched implied-error records: an exact
  two-sided tail, both assumptions listed, standing diagnostic.

**Comparability fix (S5 code).** Reference and window label-availability rates now count only units whose
follow-up has elapsed (tick + horizon ≤ cutoff). Before, a reference built before full maturity faked a
label-availability shift against matured windows. The fix was found through the S7 differential, and the S5 and
S6 suites still pass.

**Schema** `0010_intelligence.sql`: hypotheses, requirements and triggers, investigation runs.

### Evidence

**Q-DC** (locked `validation/cg7/domain_protocol.json`, run once): 500 null runs with 700 entities per arm and
10,000 permutations each. **21 rejections at 0.05 (4.2%)**, with an exact binomial p of 0.82 against 5%, and no
refused tests: **pass.** Results are in `validation/cg7/results/domain_qualification.json`.

`tests/platform/test_intelligence.py` (13 tests) runs on a real installation. The scenario: group b degrades
within the group and its share rises.
- **Regions and links:** the region reference and exposure alarm start no earlier than the March share rise;
  diagnostic gates are refused; the structural link between the region conditions shares `group`.
- **Priority v2:** S-selected cap, impact recorded, low-exposure and exploratory rules.
- **The differential:**
  - all ten hypotheses are judged;
  - H-WITHIN is supported and H-COMP contradicted (equal reference risks: composition explains nothing);
  - H-LABEL is contradicted after the comparability fix;
  - H-UNC is untestable;
  - the identity requirement carries its action;
  - matrix cells are as expected.
- **The planner:** ineligibility reasons, greedy order, duplicate suppression on replan, restricted approval refused
  without `reserve:consume` and refused explicitly with it.
- **Executions:** the contract diff settles integrity (H-INTEG contradicted); the domain classifier reads
  covariates under two consumed reservations.
- **Reuse** after additional units, with zero material changes and a stale fraction under 20%.
- **Triggers** fire for a movable hypothesis and mark a decided one satisfied.
- **Patterns, guidance, diagnostic, catalog:** deterministic signatures and thresholds; Neyman allocation and
  half-widths; the exact Poisson-binomial diagnostic against brute force; the domain-classifier core (AUC equals
  sklearn with ties, shift detected, overlap exclusion); catalog consistency.

| Check | Result |
|---|---|
| `tests/platform` | **171 passed** (one run; 158 earlier + 13 new S7 tests) |
| `tests/cg1`–`tests/cg6` | Not rerun: S7 changes no CG1–CG6 code path. The last full run was the S5 gate (673 passed, 0 failed). |

### Limitations and deferred (no claim made)

- **Response comparison (I.9) and proposals** are S8. "Previous mitigations" lists resolutions and verification
  evidence only.
- **Templates that don't execute yet:**
  - The CG5 replay needs an operator spec.
  - The recalibration and uncertainty studies are restricted or unmonitored.
  - The shadow replay needs retained raw rows and declared logged outputs.
- **Regions:** only structured CG4 gates are applied in monitoring.
- **Observation rules** (thresholds such as projection deltas of 0.005/0.002 and AUC of 0.6/0.55) are documented
  constants, not qualified decision rules. The matrix is association reasoning.
- **Not covered:** worker-host execution of investigations (the executor is ready; job wiring comes with S9); the
  API, CLI and console (S9).
- D-1 remains tracked; there is no production-readiness claim.

## S6: operations (2026-11-23). Implemented; closure gate passing.

### Implemented (plan H.4, H.7, H.8, C.4–C.6, G.10)

**Conditions** (`operations/incidents/conditions.py`) fold monitoring signals into persistent states.
- `emerging → active`: persistence (2 of the last 3 windows), a formal alarm, or a high or critical deterministic
  violation.
- `emerging → lapsed`: no repeat within 3 windows.
- `active → quiescent`: 2 quiet windows.
- `quiescent → active`: the condition recurs.
- `quiescent → recovered`, only by declared criteria:
  - R1 for deterministic and descriptive health or rule conditions, after a further hold;
  - R2/R3 when an SM2 recovery test bound to the condition (`start_recovery(condition_id=)`) establishes its claim.
    A claim made while the condition is active waits for quiescence.
- **An absent alarm is never recovery.** Detector conditions stay quiescent without an SM2 claim.
- **Suppression** needs a reason and an expiry, returns to the prior state when it expires, and is audited.
- Every transition is an append-only event in the same transaction.

**Incidents** (`incidents.py`, priority table `priority.py`).
- **Priority.** A versioned decision table (`cg7_priority_v1`) records the rule and the "why". Operator overrides
  need a reason and are audited and notified.
- **Opening.** P1 and P2 conditions open or join incidents; P3 and P4 remain visible conditions.
- **Grouping is anchor-compatible and non-transitive.** A condition joins only through a *direct* link to the anchor
  (`exact`: a shared prior deployment event; or `population_overlap`: Jaccard ≥ 0.5 of evaluated window
  populations) when it is compatible in deployment and time. Otherwise it opens its own incident, with
  `related_incident` suggestions; nothing is merged automatically. Every decision is an event with its rule, link
  and rationale.
- **Detection dossier.** An immutable packet at K_open holds:
  - signals;
  - window evaluations with digests and evidence uses;
  - detector plans and states;
  - the reference;
  - health;
  - identity standings;
  - deployment events.
- **Knowledge revisions** are appended and never rewritten. `view(as_known='detection'|'now')` verifies digests.
- **Lifecycle** follows the H.7 transition table, with optimistic revisions for operator edits.
- **Resolution.** Outcome-supported resolutions require a member condition recovered with the matching evidence
  (R1, R2 or R3). Operator resolutions (`accepted_risk` and the rest) require a reason and are never recovery.
  A recurrence of the same condition key within 30 days of resolution reopens the incident.
- **Acknowledgement SLAs** (P1 15 min, P2 1 h, P3 24 h) escalate an unacknowledged incident by level.
- **Split and merge** are audited, reversible operator actions (each records its inverse). The anchor cannot be
  split out.

**Notifications** (`notify.py`).
- An outbox row is written in the incident event's transaction, only for state and priority changes.
- Payloads carry ids, priority, state and a link only.
- Webhooks are HMAC-SHA256 signed over `timestamp.body`. The key is generated, shown once and kept in the secrets
  store.
- SMTP uses implicit TLS or STARTTLS; plaintext needs an explicit channel flag.
- Every destination goes through `numek_platform.egress`: the allowlist, the checked-address pin, no redirects.
  The egress check now also accepts `smtp`/`smtps` destinations.
- Delivery is at least once, with idempotency keys. Rows are claimed before sending.
- A failure backs off exponentially (30 s doubling, capped at 1 h). After 8 attempts the row is a dead letter and
  raises a D health condition (`notification_dead_letter`).
- Rules set the minimum priority, digests and quiet windows (P1 is never held), and escalation levels.

**Controller and scheduling** (`operations/scheduler.py`; platform `Controller(tasks=)`).
- While leading, the controller enqueues one idempotent `ops_monitoring_cycle` job per deployment and slot, plus
  the daily retention job. Both enqueues are guarded by `assert_leader`, so a deposed controller cannot enqueue.
- It also fires escalation timers and delivers the outbox.
- The cycle job now runs `monitor_once`: the S5 cycle, then signals → conditions → incidents.

**Retention and pins** (`pins.py`; H.8).
- Explicit pins (incident, analyst with expiry, study, proposal) protect event-tick ranges. Incident pins stay live
  while the incident is open and until 90 days after resolution; reopening clears the expiry.
- The observation sweep purges, through the platform purge at a new K, opportunities past `observation_days`
  (default 400, per system, minimum 30). It purges the whole revision chain with predictions, context, samples
  and outcomes, and skips pinned ranges, reporting how many it skipped.
- Window evaluations that lost facts become `summary_only`.

**Backup and restore.** Operations state (conditions, incidents, events, revisions, outbox, pins, detectors) lives in
the installation database and its packets in the installation store, so the R2.2 installation backup covers it. The
restore test verifies this.

**Schema** `0009_incidents.sql`: conditions with signal links and events; incidents with members, events, revisions
and related suggestions; channels, rules and outbox; pins; retention policies; signal processing marks;
evaluation reproducibility.

### Evidence

`tests/platform/test_incidents.py` (14 tests) runs on a real installation fed by S4 ingestion and S5 monitoring, in
simulated time. It covers:
- **Opening:** a formal alarm opens a P1 incident (rule `formal_tier1`) with a verified dossier at K_open and a live
  pin; a second formal condition on the same windows joins by population overlap.
- **Grouping:** every member is linked to the anchor itself (re-verified). The empty-window health condition, which
  has no link to the anchor, is not grouped and opens its own P2 incident.
- **Notifications:** webhooks are signed (verified), payloads minimal, the key is absent from the database, and a
  repeat send sends nothing.
- **Escalation** past the SLA notifies the level-1 rule.
- **Lifecycle:** an illegal transition and a stale revision are refused; resolving with R2 before evidence exists
  is refused; an operator resolution without a reason is refused.
- **Recovery:** an SM2 R2 claim bound to the condition recovers it, and the outcome-supported resolution succeeds.
  The "now" revision shows the recovery while the detection dossier stays unchanged, and the pin expires 90 days
  after resolution.
- **Recurrence** reopens the incident and clears the pin expiry.
- **Condition lifecycle:** persistence, lapse, suppression expiry and R1 recovery with the exact event sequence;
  suppression is audited.
- **Merge and split:** moved conditions are restored; the audit chain verifies; splitting out the anchor is refused.
- **Delivery:** a non-allowlisted channel dead-letters after 8 attempts with `egress_denied` and raises a D health
  signal; an SMTP digest of two updates is delivered as one message; P2/P3 digests are held.
- **Controller:** it enqueues cycle and retention jobs once per slot under leadership; an impostor epoch is refused.
- **Backup and restore:** incident knowledge, state and detector checkpoints are identical after restore.
- **Retention:** an analyst pin keeps exactly its 560 opportunities; other facts are purged and the affected
  evaluations become `summary_only`.

| Check | Result |
|---|---|
| `tests/platform` (includes the S5 suites after the shared-helper move) | **158 passed** (one run; 144 earlier + 14 new S6 tests) |
| `tests/cg1`–`tests/cg6` | Not rerun: S6 changes no CG1–CG6 code path (selection, catalog, kernels and capture are untouched). The platform suite applies the new migration from scratch. The last full run was the S5 gate (673 passed, 0 failed). |

### Limitations and deferred (no claim made)

- **Links:** only `exact` (shared deployment event) and `population_overlap`. Structural links (CG4 gate features,
  CG5 predicate inputs, CG6 spec inputs) and the leading-hypothesis contradiction check arrive with S7 intelligence.
- **The priority table has no impact axis yet** (volume, traffic share, constraint violations, costs), and no region
  rule. These are S7.
- **Escalation** notifies further rule levels. On-call schedules and acknowledgement through the notification
  channel are not implemented.
- **Retention:** reserve-study pins are created explicitly; there is no automatic pin from CG4 studies. Proposal
  pins arrive with S8.
- **Not covered:** PITR and multi-host controller qualification; the API, CLI and console for incidents (S9).
- D-1 remains tracked; there is no production-readiness claim.

## S5: monitoring (2026-11-20). Implemented; closure gate passing.

### Implemented (plan G.1–G.5, H.2, H.4, H.6; Addendum R2.3–R2.5)

**S5a: sequential kernels** (`operations/monitoring/eprocess.py`; proofs in `docs/CG7_SEQUENTIAL_METHODS.md`).

*SM1: bounded-mean e-CUSUM with resets (R2.4).*
- Grid λ_k = (0.5/m₀)·2^-k, K = 12, equal weights; alarm when the mixture reaches 1/α; every component then resets.
- Computed in log space. The checkpoint is exact and chunking-invariant.
- Refuses m₀ outside (0, 1) and units outside [0, 1]. No epochs.
- The written proof gives E[N_U] ≤ α·E[U] for any stopping-time horizon U, with resets.

*SM2: one-sided Hoeffding normal-mixture confidence sequence (R2.5).*
- Bounds the running average of conditional means.
- Supports R2 (fixed θ) and R3 (θ = L_ref + Δ) claims, valid under any checking schedule.
- Minimum support 30. ρ is fixed before verification (default: planned support / 4).

*Finite bounds and the planner.*
- Bounds: one-sided Clopper–Pearson and Hoeffding, plus reuse of the CG6 bounded-cluster ratio.
- The detection planner uses the grid's Bernoulli growth rate (the worst case for a bounded statistic with a given
  mean). It reports the expected delay in units and days, and flags `insufficient_power`.

**S5b: definitions and exact incremental windows.**
- **Window pruning** (`load_history(..., window_ticks=)`, H.2). The pruned load reads:
  - the opportunities with *any* revision in the window, located by a key-only index lookup;
  - their complete revision chains;
  - their predictions, context and samples (by opportunity key) and outcomes (by target key).

  The unchanged CG3 `select_history` / `HistoryStore` then run on that load. Cost scales with the window, not
  history.
- **Window-scoped reservations.** Membership comes from identity hashes and clocks only, and is committed before
  any read. The purposes are `monitoring_outcome`, `detector` and `reference`; each is always recorded as exposure.
- **Versioned definitions** (`definitions.py`). Inspect records a version together with:
  - the frozen reference;
  - per-detector admission or refusal: unbounded statistics (log loss, MSE, absolute error) are refused, and so is
    m₀ ≥ 1;
  - m₀ = U_ref + δ;
  - α, from a target number of false alarms per 30 days at the included-unit rate;
  - planner delay including window and maturity lag;
  - power, and formal or descriptive standing with reasons.

  A reference that does not end before monitoring starts is refused (`adaptive_reference`). Confirm requires the
  inspection digest the operator saw (`stale_confirmation` otherwise), supersedes the previous version and creates
  its detectors. Detectors never carry state across versions. A version confirmed after its start is
  `added_after_observation`, and its detectors consume only windows that start after confirmation.

**S5c: references, measures, estimators and the ledger.**
- **References** are immutable and computed once per rule and K, under purpose `reference`. Each holds:
  - per-statistic included counts and means;
  - finite bounds under the registered design (Clopper–Pearson / Hoeffding / bounded-cluster), or `None` with
    reasons;
  - inclusion rates and the included-unit rate per day;
  - cohort composition with Bonferroni-split within-group risks;
  - the frozen selected relation (Parquet).
- **Window measures** reuse CG1/CG2/CG3 reducers through `longitudinal._evaluate`. Drift uses CG3's own `_drift`
  against the frozen reference relation (KS, W1, TV, JS, with CG3's refusals).
- **Rules** are deterministic thresholds (D/P) plus CG3 drift prioritization (P).
- **Outcome-free estimators** (G.5): implied issued error (1 − p of the issued decision), implied Brier (CG1's
  definition), and composition projection. Each carries an assumption label and standing E.
- **Matched accountability ledger.** The original record is immutable. At maturity a matched record is added: the
  same formula on O ⊆ P_W, the realized value with Clopper–Pearson or Hoeffding intervals, coverage, exclusions,
  signed bias and exceedance. `ledger_summary` gives descriptive accountability.

**S5d: detector runtime** (`runtime.py`, `units.py`, `health.py`; job kind `ops_monitoring_cycle`, essential lane).
- **Phases.** Close: outcome-free measures, drift, estimator records, rules and outcome-free detectors. Maturity:
  matured measures, matched accountability, rules and outcome detectors.
- **Units.** Inclusion is predictable: selected state, availability and maturity, `entity_first` per detector.
  Invalid outcome values are excluded and counted. Units are ordered by window, then HMAC(per-deployment secret,
  event key), so the order is independent of X.
- **One transaction per window phase.** It holds, in order:
  1. the fence;
  2. the exposure lock;
  3. the packet;
  4. reservation consumption;
  5. the evaluation row;
  6. per detector, a unique segment (`first_unit` contiguous) and a state update guarded by the previous version
     and window contiguity;
  7. the admitted units;
  8. estimates and signals (dedupe keys).

  A replay applies nothing, and a forced re-application refuses.
- **Late publications** are detected incrementally from facts published since the earliest latest-evaluation K.
  Outcome arrival is not lateness for the close phase. A late publication creates a new evaluation *revision*; its
  units never enter running detectors and are counted as late exclusions.
- **Alarms** carry the fixed R2.4 wording, what is not established, the assumptions, and a comparability
  annotation. That annotation flags a population-definition shift when label availability differs from the
  reference beyond tolerance. Descriptive detectors produce P signals with no probability statement.
- **SM2 recovery tests** start only at a window not yet evaluated, and emit `threshold_recovery_established`,
  `reference_noninferiority_established` or `recovery_not_established`.
- **Health** (D) covers:
  - source silence, failed batches, backlog and known producer loss;
  - failed ops jobs;
  - untimed opportunities (new partial index);
  - closure and maturity backlog, staleness, empty closed windows;
  - detector standing, power, lag and late exclusions.

  **Coverage map:** formal / insufficient_power / descriptive / not_configured / stale per dimension. "Absence of
  conditions is not evidence of health."
- **Schema** `0008_monitoring.sql`: definitions, references, window evaluations (phase, revision), detectors,
  segments, admitted units, signals, estimates.

### Evidence

**Statistical qualification (M.2).** The locked protocol `validation/cg7/sequential_protocol.json` was run once by
`sequential_qualification.py`; results are in `validation/cg7/results/sequential_qualification.json`.

| Panel | Result |
|---|---|
| Q-E1a exact enumeration, all 2^20 paths, resets, 3 m₀ × 2 α | pass. E[N_t] and P(N_t ≥ 1) ≤ tα at every t; the worst ratio to the bound is 0.02 |
| Q-E1b recursion = brute-force definition; CUSUM ≤ Shiryaev–Roberts | pass (300 paths, 362 alarms compared, 0 mismatches) |
| Q-E1c log-space stability over 10^8 units | pass (state finite; prefix equal to `EDetector`; 0 alarms against α·U = 1) |
| Q-E1d SM2 exact false-claim probability; closed form against numerical integration | pass (exact ≤ 3.7e-4 against 0.05; integration to 1e-6) |
| Q-E2 SM1 null with resets: 6 generators × 2,000 trials, nα = 0.05 | pass. First alarms 0–4 per panel against an allowance of 100 (the bound is conservative) |
| Q-E3 SM2 null: constant, alternating and drifting running averages | pass (0 false claims in each panel) |
| Q-E4 violation controls (documented limits) | Unthinned repeated entities 99%, common shock 99%, and an unrepresentative reference (true mean 1.1·m₀) 33% of trials alarm. This inflation is expected, and the `entity_first` default and the declared assumptions exist for it. |
| Q-E5 planner validity, 4 scenarios × 400 trials | pass (median delay 0.87–0.93× the prediction) |

The run had one harness defect: Q-E2's outcome was computed but not saved, because of numpy-bool JSON
serialization. Under the stopping rule, Q-E2 was rerun with the same seed and code path, and the rerun and its
reason are recorded in the results file. Q-E3 to Q-E5 then ran for the first time (`--resume`). No threshold,
seed or panel changed.

**Engineering correctness.**
- `tests/platform/test_sequential_kernels.py` (15 tests): the recursion against its definition, the checkpoint,
  refusals, log-space stability, the SM2 boundary against numerical integration, support, bounds and the planner.
- `tests/platform/test_monitoring_windows.py` (7 tests) is the **H.2 equivalence gate**. Pruned and full selection
  are compared for every window, at two snapshots and two maturity policies, on a history with:
  - corrections that move opportunities forward and backward between windows;
  - late, out-of-order, withdrawn and final outcome revisions;
  - outcomes before predictions;
  - malformed clocks, retries and repeated entities.

  The two selections are equal in rows, selected digest, every measurement and coverage. The one exclusion is the
  whole-history `unlocated_opportunities`, which health reports from the index. A mutation check confirms that
  naive in-window-only pruning is caught. The window reservation is smaller than the namespace's.
- `tests/platform/test_monitoring.py` (9 tests) runs on a real installation, through S4 ingestion, in simulated
  time. It covers:
  - inspection: planner, refusals, a reference computed once and its purpose consumed, stale confirmation, an
    adaptive reference refused;
  - the cycle: contiguous and unique segments, contiguous unit indices, the March shift detected with no alarm
    before it, F signals with fixed wording, evaluations consumed under `monitoring_outcome` / `detector`, an
    idempotent replay, and a forced double application refused;
  - estimators: recorded, then matched. Calibration holds before the shift; after it, exceedances are recorded;
  - a late batch: close and maturity revisions, 30 late units excluded, detector units unchanged;
  - an SM2 R2 claim on recovered data, and its start-window refusal;
  - health and coverage: formal matured performance, regions not configured, staleness detected;
  - drift and rules through CG3 reducers; empty closed windows as D conditions; packets carry hashes, not lexical
    entities.

| Check | Result |
|---|---|
| `tests/platform` | **144 passed** (one run; 113 earlier + 31 new S5 tests) |
| `tests/cg1`–`tests/cg6` (selection path, reader, reservation and schema changed) | **673 passed, 0 failed, 11 skipped** (one run; the same pre-existing skips) |

### Limitations and deferred (no claim made)

- **Statistics not yet admitted:** coverage miss (interval and set outputs), region membership (frozen CG4 regions)
  and deferral indicators. They are refused as unknown statistics. Region and policy dimensions show
  `not_configured` in the coverage map (S7).
- **Not implemented in S5:**
  - the G.5 Poisson-binomial calibration-transfer diagnostic;
  - G.6 Neyman label-allocation guidance;
  - the G.7 domain classifier and Q-DC (S7);
  - measurement of reference/stream entity overlap. R2.4 asks for it to be shown; it is stated as an assumption on
    every alarm instead.
- **Health:** volume against expected volume is not modelled beyond empty closed windows.
- **Pending later stages:**
  - controller scheduling of `ops_monitoring_cycle` (S6 with the controller);
  - conditions, incidents and notifications built from signals (S6);
  - retention pins for references and packets (S6);
  - the API, CLI and console for definitions (S9).
- **Comparability** is checked through label availability only. Late and thinning rates are recorded but not
  compared.
- **Performance:** not measured. The incrementality ratio and M.5 tiers are S10.
- D-1 remains tracked (shared-installation workspace stores); there is no production-readiness claim.

## S4: ingestion (2026-11-20). Implemented; closure gate passing.

### Implemented (plan H.4, H.5, C.6, G.9, R2.7)

**Installation and registration.**
- **`numek_platform.installation`.** An installation is one database (named by an environment variable, or a P-LOCAL
  cluster), one object store, one secrets store and a catalogs directory.
- **Systems.** Each system owns one ConfidenceGuard platform catalog bound to the installation: its database, object
  store and secrets. One installation backup therefore covers every system catalog. The binding is derived from the
  database, so a restored or relocated installation recreates it.
- **Deployments** carry a registered identity (model id and version, artifact digest, optional CG6 predictor spec) and
  an optional Ed25519 customer key.
- **Sources** are versioned contracts (`operations.contracts`):
  - the format (CSV or JSONL);
  - the permitted fields, each with type, required/identity, vocabulary, range or probability rules;
  - probability-sum groups;
  - an event-time field;
  - identity fields;
  - a CG3 `PredictionBatchSpec` template, so publication reuses CG3's identity, correction and dedup rules unchanged.

  A changed contract becomes a new version, and earlier batches keep theirs.
- **Ingest tokens** are scoped to one source (`ingest:source:<id>`) or deployment (`ingest:deployment:<id>`). They are
  issued only to service principals, shown once and stored as a hash.

**Receive (the durable acknowledgement).**
1. The raw body is encrypted with that UTC day's data key (AES-256-GCM, authenticated by source and batch id), under a
   random object id. Object names reveal nothing about the plaintext.
2. The body is written durably (W1–W3).
3. One transaction activates it, records the batch and enqueues its processing job. Only after that commit is the
   batch acknowledged (HTTP 202).

How retries and failures behave:
- **Same id, same bytes:** returns the same receipt.
- **Same id, different bytes:** refused with `batch_conflict` (409).
- **Crash before commit:** leaves only a pending object, which GC reclaims.
- **Backpressure:** 429 with `Retry-After` when pending batches or pending raw bytes exceed the admission.
- **Backfill batches** run in the maintenance lane, never competing with live monitoring.

**Process.**
1. Decrypt and verify the plaintext digest, then parse.
2. **Minimization.** Undeclared fields are dropped at parse time and only counted. Their values never reach storage,
   the quarantine or logs.
3. **Row checks** (deterministic, standing D): missing identity or required field, type, timestamp, vocabulary, range,
   probability, probability sums. A failing row is quarantined with its reasons and field names, never its values. The
   minimized rows are kept encrypted under the day's quarantine key.
4. **Publication.** Accepted rows publish through the CG3 capture path at one K. A fact that conflicts with retained
   evidence, or corrects it inadmissibly, is quarantined per fact (`commit_capture(conflicts='quarantine')`) instead
   of refusing the batch.
5. **Reserve assignment.** Entities are registered with the namespace's sealed reserve in the publication transaction,
   at its K: assignment at first sight, and an entity first seen before a reserve existed stays `pre_reserve`. This
   closes the S3d gap: reserve-backed studies now work end to end on ingested evidence.
6. One final transaction records the batch state, counts, quarantine and identity standings, and releases the raw body
   from recovery retention.
7. Retries are idempotent (the publication's request id is the batch id). Jobs run on worker hosts with
   `InProcessContext` (`operations.jobs:REGISTRY`), or through `process_pending` on a single host.
8. **Funnel.** Rows received = accepted + quarantined; facts published = new + duplicate, with conflicting facts
   quarantined; `funnel()` reports the reconciliation.

**Watermarks and closure.**
- Producer watermarks are monotonic (a regression is ignored and reported).
- Rows at or before the watermark that was current at receipt are counted as late.
- Closure standing of a window `[a, b)` is `producer_declared_complete`, `assumed_complete_after_lateness`, or `open`
  (plan G.1). Window revisions and detector inputs are S5.

**Directory pull** (`SourceConnector` seam). New or changed files are fingerprinted (path, size, mtime, SHA-256) and
received. Customer files are never deleted; they are optionally moved to a `processed` directory. Database and S3
connectors are prepared only, as planned.

**SDK `numek_monitor`** (standard library only).
- `log()` is non-blocking and never raises.
- Rows go to an on-disk segment, fsynced by group commit within 200 ms.
- Sealed batches keep a stable id (buffer id plus sequence), so a resend after a crash or a lost response is
  recognised.
- A full buffer drops and counts rows; the known loss is reported in the next batch (`Numek-Dropped-Rows`).
- Rejected batches are kept aside.
- Delivery states follow H.5: `buffered_memory`, `buffered_disk`, `sent`, `acknowledged`, `dropped`.

**Deployment identity standings** (each recorded separately with evidence; G.9 and R2.7):
- `declared` per batch, from a header and/or identity fields; inconsistency fails it.
- `registered`: the declared identity equals the registered one.
- `spec_compatible`: the contract's task against the registered predictor's task, recorded with every contract
  version.
- `sampled_output_consistent`: a keyed-random sample (HMAC, independent of outputs) replayed through the registered
  CG6 predictor in-process. It reports mismatches, rows that can't be replayed, and a one-sided Clopper–Pearson upper
  bound on the mismatch rate. Agreement on samples is stated not to be attestation.
- `customer_signed_statement_verified`: Ed25519 over a canonical statement (deployment, artifact digest, period).
  Trust rests on the customer's signing process. Runtime (hardware or TEE) attestation is not implemented and never
  inferred.

**Deployment events** (model, configuration and data-pipeline changes, rollout, rollback) are recorded with their
identity and actor.

**Retention and crypto-shredding** (R2.7).
- Raw bodies of terminal batches are tombstoned after 7 days; unprocessed bodies are kept.
- Encrypted quarantine rows are tombstoned after 30 days, under each catalog's own maintenance epoch.
- A day key whose objects are all gone and whose day is past retention is destroyed live. That is reported as
  `destroyed_live` with "complete only after every backup holding these keys expires (not tracked)", never as
  deleted.

**HTTP surface** (`operations.web`; ingestion only, the full API and console are S9): batches, batch status,
watermarks, deployment events and signed statements. It uses bearer tokens, the ConfidenceGuard envelope and
401/403/404/409/413/429 mapping, and never logs bodies.

**Backups.** Received bodies of unprocessed batches (`retained_for_recovery`) and their day keys are in the
installation backup (R2.2). A restored installation processes them.

### Evidence

`tests/platform/test_ingestion.py` (14 tests) covers:
- encrypted, durable, idempotent receipt (identical retry, conflict, enqueued job, opaque object names);
- minimization (undeclared values absent from every stored fact);
- row quarantine with reasons and encrypted minimized rows;
- a reconciled funnel, with a CG3 analysis on the ingested evidence;
- per-fact conflict quarantine;
- crash before acknowledgement (orphan raw object reclaimed) and crash after publication (idempotent retry, one K);
- reserve assignment at publication (`pre_reserve` before the reserve, `reserve`/`non_reserve` after);
- watermarks, lateness and closure standings;
- directory pull (new and changed files only; never deletes);
- the HTTP surface (authentication, per-source and per-deployment scopes, 409 and 429);
- the SDK: crash recovery from the disk buffer, known loss recorded, a lost-response resend recognised;
- identity standings: registered pass and fail, spec incompatibility, a valid and a forged signed statement, the
  sampled output audit consistent and drifted;
- retention and key shredding (live keys kept);
- backup and restore of an acknowledged unprocessed batch, which then processes;
- the worker host processing an ingestion job;
- a log scanner showing no row or undeclared value in any log record.

| Check | Result |
|---|---|
| `tests/platform` | **113 passed** (one run) |
| `tests/cg1`–`tests/cg6` (capture path changed: conflict mode, reserve registration, receipt shape) | **673 passed, 0 failed, 11 skipped** (one run; the same pre-existing skips) |

### Limitations and deferred (no claim made)

- **Shared-installation workspaces still keep per-workspace stores (D-1).** Installation-bound system catalogs (all
  ingested evidence) use the installation store and are covered by one installation backup.
- **Not in S4** (all S9): the operations API beyond ingestion, user sessions, the console, CLI commands for
  operations, TLS/proxy enforcement for non-loopback serving, and gunicorn packaging. Window evaluation, detectors and
  references are S5.
- **Contract checks.** Registration validates that the CG3 batch template parses. It does not prove the template uses
  only declared fields; a template naming an undeclared column fails processing with an explicit error.
- **Sampled audits** need the logged inputs and outputs as rows; the caller supplies them (recent raw batches stay
  readable during retention).
- **Performance:** not measured in S4. The M.5 tiers (W-DEV) belong to the S10 closure.

## S3 closure: v2 -> platform migration (S3c), execution contexts, catalog v2 writer retirement (2026-11-20). Implemented; closure gate passing.

S3 is complete with this record: S3a (CG3), S3b (CG4–CG6 storage), S3c (migration and equivalence), S3d (G.8 reserve
and test port), and the remaining S3 items, the `ctx.run` refactor and v2 writer retirement.

### S3c: catalog v2 -> platform migration

`confidenceguard.migration.migrate_workspace(path)` migrates one workspace in place. It is also available as
`ReliabilityWorkspace.migrate(path, backup)` and through the CLI: `confidenceguard workspace migrate`, `migrate-status`
and `migrate-abandon`. It drives the R2.6 state machine in `numek_platform.legacy`:

1. **Plan.** Create a `migrating` catalog carrying the v2 analytical identity (instance id, branch, continuity state and
   token, tracking, configuration, creation time), and bind the root to it. The catalog is inaccessible to every reader,
   writer and API, except the migration's own in-process validation (see "Analytical equivalence" below).
2. **Freeze.** Set `user_version = 9002`, which every released runtime refuses, and record the inventory. A v2
   deletion consumes a K without an operation row; the inventory now accounts for those Ks.
3. **Replay in K order.** One platform transaction per K, resumable from the last committed K (recorded in that same
   transaction).
   - Each v2 operation becomes the publication with the same K, id, request id, request digest and receipt.
   - Its objects keep their ids and bytes, re-verified on copy. Its facts keep kind, key, revision, digest and locator.
   - Its occurrences, variants, assessments, artifact dependencies, vector locations and object kinds are written in
     the same transaction.
   - A v2 deletion becomes a deletion publication at its K that tombstones its facts. Its bytes were already gone, so
     those objects are recorded as reclaimed placeholders.
   - Each v2 evidence use becomes a durable legacy governance record inside its K's transaction. It keeps its v2 id,
     kind, digests and counts, and its membership is rebuilt from the v2 ledger's own membership facts. The exposure
     registry, confirmation members and study allocation are rebuilt with it.
4. **Validate** (`validate`; the report gates cutover). Structural checks:
   - K sequence and every publication;
   - fact identity, digest and locator;
   - occurrences and deletion tombstones;
   - object identity, plus full verify-on-read of every copied byte;
   - every ConfidenceGuard relation;
   - identity and settings;
   - evidence governance, use for use: fields, decoded membership against the v2 digest, registry flags, confirmation
     members, study allocations.

   Then analytical checks (run by the migration job in-process, under `InProcessContext`):
   - **Historical reconstruction:** every retained logical fact decodes byte-equal.
   - **Retained assessments:** every retained assessment reopens identically.
   - **Deletion previews:** equal for every retained assessment and for one object of every evidence kind.
   - **Evidence-use overlap:** equal answers on every recorded population (sampled) and an unrelated one.
   - **CG3 re-execution:** every retained CG3 analysis (including restatements) re-executes at its own K and equals the
     stored v2 result. Numbers are compared with a 1e-12 absolute / 1e-9 relative tolerance. The only exclusions are the
     result's own id, time and execution metadata, read accounting, and population labels that v2 derived from an
     unordered selection stream (see "Defects found"). An analysis that v2's conservative "potentially impacted" list
     covers after an evidence deletion must either re-execute equal or refuse exactly as v2 does.
5. **Cutover.** A single transaction, allowed only with a passing report; it is the point of no return. v2 stays frozen
   read-only. Purging the migrated workspace also removes the frozen v2 catalog and its bytes.
6. **Completion.** Reported only after a post-cutover backup. A workspace with its own P-LOCAL cluster takes it
   automatically when given a destination. A shared installation reports
   `post_cutover_backup_required_on_shared_installation` (tracked item D-1).

Interruption and recovery:
- A crash at any boundary (planned, frozen, any K, copied, cutover) resumes from durable state.
- A source changed after freezing refuses with `migration_source_changed`, including on a resumed freeze. Tampered
  evidence bytes refuse with `evidence_changed`.
- `abandon_workspace` (before cutover only) removes the platform copy, including governance and ConfidenceGuard rows
  and the never-readable object copies, and restores v2 exactly (same inventory digest). The workspace can then be
  migrated again.
- A catalog v2 backup (`workspace_backup/1.0`) still restores: it becomes a new instance and is then migrated
  (`restore_legacy_backup`).

Frozen test sources:
- `tests/fixtures/catalog_v2/` holds three catalog v2 workspaces (about 3.8 MB):
  - CG3 with a restatement, evidence uses and an assessment deletion;
  - CG3 with an evidence deletion;
  - CG4/CG5/CG6 with typed features, discovery and confirmation uses with a study budget, a policy family and CG6
    binary artifacts.
- They were generated by the last runtime with the v2 writer (`validation/cg7/generate_catalog_v2_fixtures.py`). Its
  identity (commit `c94feb90` plus the S3 working tree) and the archive digests are in `manifest.json`.

### Execution-agnostic services (`ctx.run`)

- **Call sites.** All 36 `compat.supervise` call sites in 16 modules now call `ctx.run(operation, arguments, config,
  progress=, cancel=, deadline=)` from `confidenceguard.execution_context`. (The plan counted 35; the count at
  migration was 36.)
- **No parallel path remains.** `compat.supervise` and the S1 placeholder `numek_platform/execution/context.py` are
  removed.
- **`SpawnContext`** is the default (the ephemeral workbench and every caller that sets nothing). It keeps the
  previous behaviour exactly: a fresh supervised interpreter per phase, with DataTrust's process-tree limits.
- **`InProcessContext`** is for persistent platform jobs, whose process the worker host already isolates and budgets,
  and for migration validation. It runs phases directly, with:
  - spawn-equivalent data isolation (arguments and results are pickled across the boundary);
  - cancellation and deadline checks at phase boundaries;
  - `platform_catalog.process_scope()`: each phase starts with no worker reservation or study authority, its own
    access-reservation attempts are closed when it ends, and the caller's state is restored.
- **Activation** is through `execution_context.using(context)`.
- **Equivalence (tested).** A CG3 platform analysis and a CG1 workbench evaluation are identical in-process and
  spawned. The only difference is the time-dependent `effective_cutoff_ns`.

### Catalog v2 writer retirement (after the migration and execution-context checks)

- **v2 roots.** `Catalog(root)` on an unmigrated v2 root refuses with `migration_required`, naming the migration
  command.
- **New workspaces.** `Catalog(root, create=True)` and `ReliabilityWorkspace.initialize` always create platform
  workspaces: a shared installation when `NUMEK_PLATFORM_DSN` is set, otherwise the workspace's own P-LOCAL cluster.
- **v2 writer code removed** from `history_storage`:
  - creation, open and retirement handling;
  - v1 -> v2 migration;
  - capture commit and recovery;
  - assessment writing;
  - deletion and backup.

  `history_storage.py` went from 1,109 to 591 lines.
- **v2 branches removed** from the workspace (history exposure, analysis, inspection), the evidence-use ledger
  (v2 tracking writes, `commit_use`) and CG6 retained paths.
- **What remains for v2 is read-only tooling.**
  - `LegacyCatalog` is the read-only view of live or frozen catalog v2 (read-only SQLite; every mutating method
    refuses). It keeps the v2 read paths that migration validation compares against: fact iteration, assessments,
    deletion preview, ledger overlap and status.
  - `numek_platform.legacy` holds the read-only reader, freeze/unfreeze and the state machine.
  - `confidenceguard.migration` holds replay, validation and v2 backup restore.
- **No dual-write and no dual-backend runtime remains.**
- **Tests.**
  - The suites run on one session-scoped P-LOCAL cluster that `tests/conftest.py` starts unless a DSN is given; plan
    E.4 specified this test migration.
  - Tests that needed v2 workspaces use the frozen fixtures.
  - The S3d-era v2 branches of ported tests are removed, so their platform invariants are now unconditional.

### Defects found and fixed in this step

- **CG3 history selection was not reproducible.** The query streaming the selected predictions had no `ORDER BY`, and
  DuckDB's parallel joins return rows in varying order. The selected-fact digest, the record ordinals and population
  labels therefore varied between identical runs on either backend: 2 of 3 repeated runs differed. The stream is now
  ordered.
- **Abandon left the catalog unusable.** The generic abandon did not remove a catalog's governance and ConfidenceGuard
  rows (a foreign-key violation) and kept its object rows, which blocked a second migration.
- **A resumed freeze accepted a changed source.** It re-recorded the inventory instead of comparing against the
  recorded one.
- **Migration-abandoned catalogs could trigger purge completion.** An abandoned catalog is `retired`. With a binding
  file present, opening it ran the purge-completion path (emptying `objects/`). File retirement now requires
  ConfidenceGuard's own purge marker.
- **Initialization over an existing v2 root.** It is now refused (`workspace_exists`).

### Tracked deferred items (not part of S3, no claim made)

- **D-1: shared-installation object store and backup.**
  - *Current state.* ConfidenceGuard workspaces on a shared installation keep a per-workspace object store
    (`platform-objects/`). `numek backup create` reads exactly one object store, so it does not cover them; workspace
    backup refuses with `backup_scope`. Such workspaces therefore have no supported installation-wide backup, and
    their migration is reported `cutover_committed` but not `complete`.
  - *Acceptance.* An installation object store configured once per installation (deployment configuration, S9/S10)
    and used by every bound workspace. One installation backup covering all their objects, with a restore test. The
    post-cutover migration backup recorded through it.
  - *No production-readiness claim is made* for shared installations until D-1 is done.
- **D-2: PostgreSQL row-level security and multi-tenant isolation.** Deferred by the plan; unchanged.

### Evidence

| Check | Result |
|---|---|
| `tests/cg1`–`tests/cg6` (session P-LOCAL cluster; catalog v2 retired) | 671 passed, 2 failed, 11 skipped (one run). Both failures were tests still patching the removed `compat.supervise` (missed in the port); they now patch `ctx.run` and pass on rerun (3 passed, 2 hardware skips). No product failure. |
| `tests/platform` (migration, execution context, authority, reserve-backed studies, governance, publication, GC, backup) | **99 passed** |
| DataTrust suites (root, `m4`–`m9`; workbench transport now uses `ctx.run`) | Failure set identical to the same suites run at the S3d commit (`c94feb90`) in a clean worktree with the same environment. Every failure is environmental: the CG7 environment does not include DataTrust's optional extras (`reportlab`, `docx`, `ijson`, `pycocotools`, the pinned text-embeddings `transformers`). One test shows as new only because the baseline worktree lacked the locally downloaded model and skipped it; here it runs and fails for missing `transformers`. **No DataTrust regression.** |

### Remaining limitations

- D-1 above. Shared installations have no supported installation-wide backup, and no production readiness is claimed.
- Analytical migration validation re-executes retained CG3 analyses. CG4, CG5 and CG6 results are validated by
  byte-equal reconstruction of their inputs, identical reopening and the deletion closure, and a CG4 re-execution is
  checked in the tests. CG5 and CG6 re-execution is not part of the validation report.
- Population labels in v2 CG3 results came from an unordered stream, so they are excluded from re-execution equality;
  every measured value, count and state is compared. Results sealed before the ordering fix keep the labels they were
  sealed with.
- A catalog v2 runtime cannot be used again after cutover (no reverse migration); recovery is through platform backups.
- The frozen v2 fixtures are generated inputs: regenerating them needs the pre-retirement runtime recorded in their
  manifest.

## S3d: reserve-backed assessments (G.8) and the v2-specific test port (2026-11-19). Implemented; closure gate passing.

### Implemented

**Reserve-backed CG4 confirmation and CG5 policy assessment (G.8 ordering).**
1. *Freeze.* The study family and its selection rules are frozen (`freeze_hypotheses`, `freeze_policy_family`); freezing claims nothing.
2. *Identify eligible reserve membership without protected inspection.*
   - Platform `governance.reader.reserve_identities` returns, for fresh sealed-reserve entities (or ones already spent by the same family), each opportunity with an outcome fact at K in the selection's windows.
   - It returns only identity hashes, the opportunity key and tick, and the identity fields of the opportunity payload (`entity`, `opportunity`, `event`, `target`). It never returns covariates, predictions or outcome values.
   - The family's assessment role (CG4 `H`, CG5 `E`) is then decided by `investigation.identity_role` / `policy_history.identity_role`. These are the same functions role assignment now uses, so the claim and the analysis cannot disagree.
3. *Reserve and consume atomically.* `PlatformCatalog.claim_reserve` makes one `reserve_claim` reservation (class `confirmation`, consume). It has no error budget, exactly one claim exists per family, and its snapshot is fixed.
4. *Authorized inspection and assessment.*
   - `inspect_confirmation` / `inspect_policy_assessment` make or reuse the claim before any worker runs, then run the inspection worker through `governed_call(claim, …)`.
   - The assessment worker runs under its own confirmation reservation, which consumes the same units: the spent-by-family rule allows it.

**Rules the claim must respect.**
- **Ordinary workflows are unchanged.** There is no claim, and sealed entities stay withheld, for v2 workspaces, tracking off, no active reserve, roles taken from a data column (not decidable from identities), or nothing eligible.
- **Retries, scheduled looks and numerical recomputations reuse the original claim.** The authorized population never grows. A family with predeclared looks may read its own units at the later look snapshot; the membership bound still applies.
- **Interrupted studies keep their claim and spending.** Freshness is never restored, and the retry resumes the same claim.
- **Another family cannot claim or read those units.**
- **A claim is not exposure.** It is left out of overlap checks: it reads nothing, and its units are already protected by the reserve rules.
- **Only confirmation-class receipts confer authority.** Receipts now carry `evidence_kind`. This also prevents a CG5 descriptive `outcome_disclosure` receipt from being passed as authority, which the ledger refuses.

**Frozen input identity under authority.**
- CG4's frozen-input digest (`cg4_canonical_selected_history_v1`) still covers the selection as discovery saw it.
- Claimed reserve rows get a separate digest (`sealed_reserve_sha256`, `sealed_reserve_rows`). Digests of v2 and reserve-free catalogs are unchanged.
- Catalog instances in a worker now read under the worker's current reservation even if they were opened before it was made.

**Product corrections found by the test port.**
- **Session identifiers.** Platform deletion and purge now release the workspace's process-local untracked session identifiers, as v2 does. This includes completion of an interrupted purge on reopen.
- **Evidence-use records.** A targeted deletion of an evidence-use membership object now refuses (`governance_record`). Exposure records are durable governance; a purge still retires them, and exposure history survives it.
- **Repeated evidence-use requests.** A repeated request returns the original receipt, as in v2. Different content refuses.
- **Standalone runs on retained bytes.** A standalone CG4/CG5 run over bytes already retained in the workspace now depends on those capture objects for deletion (v2 parity; the port had dropped it).
- **Deterministic fact order.** Typed-feature rows of one object shared a sort key, so their order was undefined. The physical order is now `(object id, loc_a, loc_b, …)`, which is v2's order, and the logical order has full tie-breakers.
- **Missing backups.** A restore from a missing backup now refuses with `backup_changed` on both backends (it used to raise `FileNotFoundError`).
- **Backup refusal message.** It was misleading, now corrected. `numek backup create` reads one object store, so it does not cover the per-workspace object stores of ConfidenceGuard workspaces on a shared installation (see Limitations). Platform backup summaries also list their files, matching the v2 manifest.

**v2-specific test port (all 30 S3b failures).** No assertion was removed. Each was replaced by the platform form of the same invariant, through `tests/backend_support.py`. On v2 the tests run unchanged.

| S3b category | Count | Replacement |
|---|---|---|
| Workspace backup on a shared installation | 7 | Marked `workspace_backup`, as is the CG6 raw-SQL test below, which also backs up. `tests/conftest.py` runs them, unchanged, on P-LOCAL platform workspaces (own cluster each, stopped afterwards) when the shared DSN is set. The intentional shared-installation behavior is verified by `test_shared_installation_workspace_refuses_workspace_backup_without_side_effects`: `backup_scope` refusal, nothing partial written, workspace unchanged. |
| Raw v2 SQL | 5 | Storage helper API (`object_ids_for_key`, same query on v2) and `codec_counts` |
| v2 `evidence_use` facts | 8 | `evidence_uses(ws)` (`EvidenceUseLedger.records()`, the v2 payload shape on both backends). The membership-chunk test checks, on the platform, that every member (across the old 512-member chunk boundaries) is in the durable registry and that the use's immutable membership object holds exactly its digested membership. |
| Process-local session ledger | 3 | Platform contract: uses are durable governance (nothing held in process memory, every member stays exposed, targeted deletion of a use refuses). Untracked process-local values are released on deletion and purge, also when a purge dies after its tombstones. Another workspace's purge does not affect this workspace. |
| v2 `objects/` layout | 6 | `stored_evidence(ws)`: the authoritative evidence bytes (the platform store, excluding governance membership objects and materialized copies). `object_file(ws, oid)`: the tamper target. |
| v2 lock contention (`workspace_busy`) | 1 | Platform contract (plan E.2): the v2 file locks gate nothing. Two concurrent ingests from separate workspace handles both publish, K stays gap-free (2, 3), no fact is lost, and deletion proceeds while the old objects lock is held. |

**New end-to-end tests** (`tests/platform/test_reserve_backed_studies.py`). They use controlled entity registration: every entity whose id is a multiple of 10 is sealed reserve. They cover:
- CG4 confirmation:
  - D/S never touch a sealed entity;
  - freezing claims nothing;
  - exactly one claim, for the family's H reserve units;
  - the confirmation consumes exactly those;
  - its H population contains them and no other sealed entity;
  - `spent_by` points at the claim;
  - idempotent retry;
  - the predeclared look reuses the claim with identical membership.
- An unrelated family sees none of those units and cannot claim them.
- A column-role study claims nothing.
- An interrupted study keeps its claim, and the retry resumes it.
- CG5 policy assessment:
  - one claim for the family's E reserve units;
  - the assessment consumes exactly those;
  - selection (S) never touched a sealed entity.

### Evidence

| Check | Result |
|---|---|
| `tests/cg3`–`tests/cg6` with every workspace on the platform (one closure run) | **592 passed, 0 failed, 10 skipped** (shared DSN; the backup tests run on P-LOCAL through the marker) |
| `tests/cg3`–`tests/cg6` on catalog v2 (one closure run) | **592 passed, 0 failed, 10 skipped** (the same 10 skips on both backends; they predate CG7) |
| `tests/platform` | 84 passed, 1 failed. The new shared-installation refusal test caught a real gap: restoring from a missing backup raised a bare `FileNotFoundError` on both backends. `restore` now refuses with `backup_changed`; the file was rerun (5 passed), as were the affected v2 CG3 backup and lifecycle files (21 passed). |

### Not done in S3d (plan items outside this authorization)

- **`ctx.run` refactor** of the 35 `compat.supervise` sites. It was not part of the S3d requirements given. CG workers still spawn per phase; S4+ platform job workers need it.
- **Retirement of the v2 writer.** It requires S3c (v2 → platform replay and equivalence validation), which has not been run. Retiring the writer first would strand existing v2 workspaces.

### Limitations

- Platform ConfidenceGuard workspaces do not register entities with a reserve at publication; that arrives with S4 ingestion. The end-to-end tests use controlled registration.
- A reserve claim is a conservative superset: entities later found ineligible (for example, immature outcomes) are still spent. Claims bind the snapshot at which they are made; a selection without a fixed catalog sequence claims at the current head.
- Roles taken from a data column cannot be decided from identities, so such studies cannot use the sealed reserve.
- Shared-installation ConfidenceGuard workspaces keep per-workspace object stores, which `numek backup create` does not cover. Workspace backup is available on P-LOCAL. An installation object store for server deployments belongs to S9/S10.

## S3b: CG4/CG5/CG6 storage, deletion, backup and scoped study authority (2026-11-19). Implemented; gate classified.

### Implemented

- **Storage helpers instead of v2 internals.**
  - The v2 `Catalog` and `PlatformCatalog` share one helper API: `authority_file`, `object_ids_for_key`, `object_ids_for_fact_digests`, `prediction_digests_in_operation`, `object_operations`, `vector_location`, `vector_matrix`, `blob_path`.
  - `policy_history`, `investigation_history`, `investigation_result`, `confirmation`, `execution/storage`, `execution/result` and `workspace` no longer open SQLite, verify objects or build `catalog.sqlite3` paths themselves.
- **Platform reads of v2 object kinds.**
  - Typed feature rows (`typed_feature_rows_v1`) are read through a verified, materialized copy.
  - Retained CG6 blobs are recreated at their v2 paths (`objects/<oid>.cgblob`) when a result is opened.
  - Migration `0004_cg_objects.sql` records each object's ConfidenceGuard kind and creating operation (needed by the deletion closure).
- **Deletion and purge** (port of v2 semantics).
  - Preview and closure work as in v2. A deletion writes tombstones, advances K by one and makes continuity incomplete.
  - Garbage collection is scoped to the catalog.
  - A full purge retires the catalog. If the process dies after the purge committed, reopening the workspace finishes the physical removal (empties `objects/` and `staging/`, writes `.retired`), as v2 does.
- **Backup and restore** for workspaces with their own P-LOCAL cluster: a snapshot-consistent platform backup, and a restore into a new cluster that is a new instance (new instance id, branch and continuity token; continuity `restore_unreconciled`). Workspaces on a shared installation refuse with `backup_scope`; the installation backup (`numek backup create`) covers them. The platform backup no longer requires a keyring when no encrypted objects exist.
- **Access-only reservations.**
  - Migration `0005_access_reservations.sql` adds `selection_access` (class `access`). It authorizes a governed read and records **no** exposure. It is not an evidence use: it is absent from `EvidenceUseLedger.records()`, from overlap checks and from the exposure registry, and it can never grant study authority.
  - CG4/CG5 history workers reserve with it before their first protected read. As in v2, CG3 analyses record `outcome_disclosure` only when evidence-use tracking is enabled.
  - Without this, a worker's automatic reservation marked the whole namespace as outcome-exposed and refused every later confirmation.
- **Scoped study authority for the sealed reserve.**
  - A confirmation-class reservation (CG4 confirmation, numerical recomputation and scheduled looks; CG5 policy assessment and scheduled looks) now records its snapshot (`read_k`).
  - The assessment worker runs inside `study_authority(reservation)`. Its access reservation inherits that authority and admits only the sealed-reserve units that:
    - are in the authority's own membership;
    - were spent by a confirmation-class use of the **same study family**;
    - lie within the authority's snapshot (`authority_snapshot` otherwise).
  - Any other purpose that names an authority refuses with `authority_scope`. Unrelated studies, monitoring, exploratory and development reads keep those units withheld or refused.
  - A predeclared scheduled look or numerical recomputation of the same family may reuse units its family already spent. Units spent by another family still refuse.
  - Retries rebind the original reservation (unchanged authorization). Interrupted studies keep their units spent; freshness is never restored.
- **Snapshot rules for governed reads.**
  - There is no plain-reader fallback.
  - A reservation handed to an analysis is never widened: a read beyond its K refuses with `reservation_snapshot`.
  - Only a worker's own access reservation is renewed at a later K, with the same authority, which itself refuses beyond the study's snapshot.
- **Smaller fixes.**
  - `EvidenceUseLedger.records()` gives v2-shaped evidence-use records on both backends. Scheduled-look provenance in CG4 and CG5 uses it.
  - A repeated evidence-use request no longer crashes on the platform: each call is its own attempt, and the ledger's request id provides idempotency.

**Defect found by the gate and fixed (pre-existing, both backends).**
- CG3 built `label_observation_by_feature` with an unordered DuckDB `GROUP BY`, and the categorical Jensen–Shannon sum iterated another unordered `GROUP BY`.
- Parallel hash aggregation returns groups in varying order. Sealed CG3 results were therefore not byte-reproducible: the platform backup/restore test failed in 2 of about 8 full-suite runs under load.
- Both queries are now ordered. Results sealed before this fix keep the order they were sealed with.

### Evidence

Shared gate cluster (`NUMEK_PLATFORM_DSN`), `validation/cg7/py313.nosync`.

| Check | Result |
|---|---|
| `tests/cg3`–`tests/cg6` with every workspace on the platform (one run on the final code) | **562 passed, 30 failed, 10 skipped.** Every failure is classified below. One was a genuine defect, fixed after the run and rechecked in its own file and in `tests/platform` (80 passed). |
| `tests/platform` (now including `test_study_authority.py`) | 80 passed, 4 consecutive runs under concurrent gate load |
| `tests/cg3` on v2 (regression) | 67 passed |
| Touched CG4/CG5 files on v2, after the authority change (scheduled looks, entity-arm confirmation, history, exposure, policy history) | 26 passed |
| CG6 integration and CG3 lifecycle on v2, earlier in S3b (the authority change does not touch them) | 20 passed |

`test_study_authority.py` covers:
- authorized access to exactly the consumed units;
- population boundaries;
- refusal for unrelated studies and every non-access purpose;
- the authority snapshot;
- retries, reuse and scheduled looks;
- interrupted studies;
- worker inheritance through `PlatformCatalog`;
- non-widening of handed-in reservations.

**Genuine defect found by the gate (fixed).**
- `evidence_uses` had primary key `(org_id, id)`. ConfidenceGuard use ids are the v2 per-catalog `digest([kind, population, family, request])[:32]`, and every ConfidenceGuard workspace of an installation shares one organization. Two workspaces recording the same request therefore collided (`UniqueViolation`, `test_deleted_exposure_releases_only_its_owned_session_identifiers`).
- Migration `0006_evidence_use_identity.sql` makes the key `(org_id, catalog_id, id)`.
- After the fix, the test runs until it reaches its session-ledger assertion (third row of the table below).

**Final disposition of all 30 failures** (corrected in S3d; the earlier wording said "the other 29" while the table below counts 30).
- 1 failure had a genuine defect *and* an obsolete v2 assertion: `test_deleted_exposure_releases_only_its_owned_session_identifiers`. The defect is the evidence-use key collision above; the assertion is the session-ledger row below, where this test is counted.
- 29 failures had only obsolete v2-specific assertions.
- Total: 30 failures, all ported in S3d. The table assigns each test exactly once, by its post-fix disposition (7 + 5 + 8 + 3 + 6 + 1 = 30). S3d also found product gaps behind some of these rows; they are listed in the S3d record.

Each was checked against its failing line:

| Category | Count | Tests | S3d handling |
|---|---|---|---|
| Backup of a workspace on a shared installation (`backup_scope`, by design) | 7 | cg3 `test_backup_preserves_assessment…`, `test_saving_and_backup`, `test_inspection_effective_populations_and_backup_refusal`; cg4 `test_mixed_codec_commit…`, `test_large_sealed_packet…`, `test_restore_and_later_consent_gaps…`; cg5 `test_policy_family_packet_backup…` | Run them on P-LOCAL workspaces |
| Raw v2 SQL (`ws.catalog._connect()`) | 5 | cg4 `test_implicit_inline_outcomes…`, `test_deleting_historical_features…`, `test_standalone_byte_identical…`, `test_capture_metadata_used…`; cg6 `test_binary_codec_catalog_v2_backup_reopen` | Assert through the storage helpers and platform tables |
| v2 `evidence_use` facts (`iter_facts('evidence_use')`) | 8 | cg4 `test_exposure.py` ×3, `test_historical_API_infers_tracking…`, `test_live_CG4_tracks…`, `test_live_CG1_records…`, `test_scheduled_look…`; cg5 `test_policy_scheduled_look…` | Use `EvidenceUseLedger.records()`. In both scheduled-look tests, every product step before that assertion passes. |
| Process-local session ledger (`session_overlap`); platform workspaces record every use durably | 3 | cg4 `test_exposure_deletion.py` ×3 | Assert durable ledger state instead |
| v2 `objects/` layout: byte snapshots of the folder, or tampering with `objects/<oid>.jsonl` (no longer the authority; platform verify-on-read and tamper refusal are tested in `tests/platform`) | 6 | cg4 `test_old_or_invalid_retained_cutoff…` ×5; cg3 `test_fault_recovery_deletion_and_tamper` | Snapshot or tamper the platform store. Possible S3d improvement: read typed features from verified in-memory bytes instead of a materialized copy. |
| v2 lock-contention assertion (`workspace_busy`) | 1 | `test_operation_and_download_locks_are_bounded` | Replace with platform concurrency tests (plan E.2) |

**Limitation, for the founder.**
- CG4/CG5 confirmation inspection runs before the study's reservation and reads under `selection_access`, so sealed-reserve entities are withheld from the inspected population.
- Platform ConfidenceGuard workspaces also do not register entities with a reserve yet; entity registration at publication arrives with ingestion in S4.
- Today a CG population therefore never contains reserve units, and the authority path is verified at the platform level and through the worker plumbing, not end to end through CG4.
- Making reserve-backed confirmations reachable end to end needs the G.8 ordering: freeze the family, reserve and consume reserve entities from identity-only membership, then inspect and assess under that authority. That changes CG4/CG5 inspection semantics and is not done here.

## S3a: ConfidenceGuard CG3 on the platform (2026-11-19). Implemented; gate passing for the ported scope.

S3 is executed in four gated steps:

| Step | Scope | Status |
|---|---|---|
| S3a | CG3 catalog on the platform | implemented |
| S3b | CG4/CG5/CG6 storage, raw-SQL and object-path sites, deletion and backup | implemented |
| S3c | v2 → platform replay and equivalence validation | **implemented (S3 closure record)** |
| S3d | reserve-backed assessments (G.8) and the v2-specific test port | implemented; `ctx.run` refactor and v2 writer retirement completed in the S3 closure record |

### Implemented

- **Migration `0003_confidenceguard.sql`.**
  - Per-fact `protected` flag (outcomes, raw rows, and predictions carrying an inline outcome assertion) and a `namespace` column.
  - `cg_*` relations: settings, variants, assessments, artifact dependencies, vector locations, deletions.
- **Platform changes.**
  - Protection is now a property of each fact. Plain reads refuse an explicit kind request that would include a protected fact (no silent partial populations), and list mode leaves protected facts out.
  - Governed membership carries target keys, because outcome facts are keyed by target.
  - A reservation covers knowledge up to its K, so reading an earlier frozen snapshot is allowed.
  - `publish` accepts a fixed publication id; `stage_object` accepts a fixed object id without content dedupe.
- **`confidenceguard/platform_catalog.py` (`PlatformCatalog(Catalog)`).**
  - `Catalog(root)` opens it automatically for a root holding `platform.json`, or for a new workspace created with `NUMEK_PLATFORM_DSN` set. Worker children reach it unchanged. The binding stores the variable name, never the connection string.
  - Full port of v2 `commit_capture`: record and directory identities; correction predecessor, reason, availability and chronology; prediction role, entity and authority immutability; revision conflicts; duplicate content equality; purged re-import refusal; vector dedup without resurrection; fact, object and vector dependencies; blob descriptors; variant and predictor-version immutability; assessments. v2 receipt counting and the v2 fault-injection boundaries are kept.
  - Identities kept: v2 object ids (32-hex) are the platform object UUIDs, operation ids are publication UUIDs, and K is the platform sequence.
- **Governance before access in CG3.**
  - `inspect` (population preview), `analyze` and `restate` reserve the namespace's outcome-bearing population at K before reading. Membership comes from identity hashes and outcome *existence* only.
  - The reservation is passed explicitly through `longitudinal.analyze → _execute_history → load_history`.
  - The saved assessment consumes it in its own publication.
  - `EvidenceUseLedger` (status, enable, overlap, record) delegates to platform governance with the v2 receipt shape. The session ledger is not used for platform workspaces.

### Evidence

Fresh P-LOCAL cluster, `validation/cg7/py313.nosync`.

| Check | Result |
|---|---|
| `tests/cg3` on the v2 backend (regression) | 67 passed |
| `tests/cg3` with every workspace on the platform (`NUMEK_PLATFORM_DSN`) | **59 passed, 8 expected failures**: 7 `platform_unported` (deletion and backup, which are S3b) and 1 v2 lock-contention assertion (`workspace_busy`), which the plan replaces with platform concurrency tests |
| `tests/cg4/test_history.py`, `test_exposure.py`, `tests/cg5/test_interfaces_history.py`, `tests/cg6/test_integration.py` on v2 | 21 passed (CG4 needs `--import-mode=importlib`: `tests/cg4` has relative imports but no `__init__.py`, which predates CG7) |
| `tests/platform`, including the new `test_cg3_on_platform.py` | 71 passed |

The new test runs CG3 ingest, analyze and restate on the platform, and checks:
- duplicate receipts and idempotency;
- the reservation is consumed with the saved assessment;
- plain outcome reads are refused;
- v2 object identities are kept;
- outcome-only restatement keeps the prediction snapshot.

**Defects found and fixed in S3a:**
- Governed reads forced every kind to the reservation K, which broke outcome-only restatements (13 vs 6 selected predictions).
- The crash-hook boundaries were missing.

## S2: governance before access (2026-11-19). Implemented; focused checks pass.

Migration `0002_governance.sql` and the package `numek_platform/governance/`. Governance identities use the
ConfidenceGuard v2 hash space (`digest([namespace, event])`, `digest([namespace, entity or event])`). Facts now carry
`event_hash`, so migrated v2 uses and platform-native uses overlap-check against each other.

| Area | What it does |
|---|---|
| Purposes | Each purpose maps to a legacy evidence-use class (`outcome_disclosure`, `discovery_selection`, `confirmation`, `numerical_recomputation`) plus a reserve mode. The new `covariate_inspection` class is not outcome exposure. Monitoring, detector, reference and outcome-disclosure purposes withhold reserve entities. Every fitting, selection and discovery role refuses them. Confirmation, assessment, numerical retries and exports admit reserve entities only with explicit consumption. Covariate inspection follows the reserve's covariate policy. |
| Reservation (`ledger.reserve`) | Committed **before** any protected read. The membership object (`exposure_membership_v1`) is staged through W1–W3 and activated in the reservation transaction. Lock order: job, exposure lock, catalog, objects, governance rows. Ported from `confidenceguard.evidence_use`: legacy use ids and membership digests, tracking consent, continuity gaps requiring a current declaration, numerical-retry continuity, predeclared scheduled looks, reuse of an identical confirmation family and population, overlap refusal (excluding the same confirmation family and population), incomplete replay aliases, study alpha budgets. Idempotent by request id; a retried attempt *rebinds* the reservation and the earlier owner is kept. |
| Exposure records | `exposure_registry` (one row per exposed identity, with flags: outcome, development, covariate) plus `confirmation_members` (per use, confirmation classes only). Overlap checks cost is proportional to the request, not the history. **Exposure history is never deleted**: purging facts does not erase it, so fact deletion no longer forces continuity to "incomplete" (stronger than v2). The process-local session ledger is gone; every use is durable. |
| Consumption | `publish(..., reservations=[...])` marks the attempt's reservations `consumed` in the result's own transaction. A result cannot exist without its evidence-use records. Failure, cancellation or fence loss leave the reservation `reserved` permanently, so it still counts as exposure. |
| Sealed reserve (`reserve.py`) | Namespace-level reserve. Founder defaults: 10%, covariate policy `exclude`. Assignment is materialized at first observation (HMAC-SHA256 against the version effective at first-seen K). `pre_reserve` applies before creation. Rotation and fraction changes are new versions for new entities only. Explicit reallocation covers only unexposed, undeveloped entities (and uninspected ones under `exclude`). Explicit release keeps history. Consumption is entity level (`spent_by_use`). Every event is ledgered in `reserve_events`. |
| Governed reader (`reader.py`) | The only path to outcome-bearing kinds (`outcome`, `raw`). Results are restricted in-snapshot to the reservation's membership events and admitted reserve units. The reservation must belong to the live attempt and to the same K. Withheld rows are counted; `strict` refuses instead. Covariate reservations never open outcomes. `membership_from_index` builds membership from identity hashes, clocks and outcome *existence* only. |
| Plain reader | Refuses outcome-bearing kinds (`reservation_required`) and leaves out reserve entities' rows. Only compaction uses `maintenance` access. |

### Evidence (S2 focused checks)

| Check | Result |
|---|---|
| `tests/platform` | 69 passed, 24.9 s (56 from S1 + 13 governance) |
| `tests/platform/test_governance.py` repeated 12 times, each with fresh random reserve secrets | 12 of 12 passed |
| pyflakes over `numek_platform` and `tests/platform` | clean apart from one intentional re-export |

The governance tests cover:

- plain reads never exposing outcomes or reserve rows;
- reservation before access, consumption with the result, and the window measurement published under it;
- a crashed attempt keeping its exposure and losing access;
- monitoring exposure refusing a later confirmation while the reserve stays fresh;
- explicit consumption required, with entity-level spending;
- ported same-family reuse with rebinding, and a different family refused;
- development roles refused on reserve entities;
- covariate policy `exclude` vs `inspect`;
- reserve assignment stable across rotation and fraction changes, with `pre_reserve` before creation and about 10% of 2,000 entities assigned;
- reallocation refusing exposed entities, and release;
- tracking consent and continuity-gap declarations;
- study alpha exhaustion;
- exposure surviving purge;
- request-id idempotency, rebinding and reservation ownership at publication.

**Defects found and fixed during S2 verification:**
- An already-spent reserve check ran before the ported same-family reuse rule. It now runs after it, inside the transaction.
- One test assumed a fixed random assignment.

**Not yet done:**
- ConfidenceGuard read paths still use catalog v2. Porting them onto the governed reader is S3.
- Ingestion-time entity registration is wired in S4.

## S1 — Platform core (2026-11-19): implemented, focused checks passing

New top-level package `src/numek_platform/`. Nothing in ConfidenceGuard or DataTrust was changed. `pyproject.toml`
gains:

- the `platform` extra;
- the `numek` console script;
- packaging of the SQL migrations.

| Area | Module | What it does |
|---|---|---|
| Schema | `db/migrations/0001_core.sql`, `db/migrator.py` | Organisation-scoped tables with composite `(org_id, id)` foreign keys. Global `fact_index`, hash-partitioned by identity key (32 partitions): `UNIQUE(catalog, kind, key, revision)` plus a partial unique index that forbids correction forks. Checksummed, append-only migrations. |
| Canonical identity | `canonical.py` | Byte-compatible restatement of `confidenceguard.contracts.digest` and `history_storage.serialized`, pinned by a test. |
| Object store | `objects.py` | Content-addressed physical keys with generations. Staging per job attempt. **Verify-on-read hashes exactly the consumed bytes** (no metadata trust, no time-of-check/time-of-use window). |
| Publication | `evidence/publish.py` | W1–W4. Fence first. Global lock order. Pending objects activated only for the owning attempt. `ON CONFLICT` identity insert classifying duplicate, conflict, ambiguous-batch and purged re-import. K assigned last, under the head-row lock. Idempotent request ids. |
| Reading | `evidence/reader.py` | Committed read pins (K, tombstone epoch, maintenance floor). Locator resolution in one REPEATABLE READ snapshot. Purged selections refuse (v2 semantics). |
| Maintenance | `evidence/maintenance.py`, `evidence/gc.py` | Purge at a new tombstone epoch and K. Compaction with per-row digest checks and locator moves at a new maintenance epoch. GC invariants I-1 to I-3 (pending vs live attempt, pins, holds, grace). Interrupted reclamation completes. Staging cleanup. |
| Jobs | `execution/jobs.py` | Enqueue (idempotent), `SKIP LOCKED` claim with admission callback, fence on every claim/expiry, renew/complete/fail/cancel all `WHERE fence`. Inline jobs die rather than rerun. |
| Controller | `execution/controller.py` | Leadership row with an epoch. Deposed leaders cannot act. Lease expiry. Periodic GC. |
| Worker host | `execution/host.py`, `supervision.py`, `_child.py`, `probes.py` | Warm pools keyed by (org, thread cap) and isolated processes. Native thread caps set in the child environment before import. Process-group kill. Process-tree RSS. Deadline, cancellation and lease-loss kill with no write. Isolation probes recycle a warm process that leaked state. Host RSS/thread/device budgets with an essential-lane reserve. |
| Execution context | `execution/context.py` | `SpawnContext` (today's supervision) and `InProcessContext` (platform jobs), ready for the S3 port of the 35 `compat.supervise` sites. |
| Identity | `identity/__init__.py` | Principals (user/service/system). argon2id passwords. Server-side sessions with CSRF, idle and absolute expiry. SHA-256-stored scoped tokens that only narrow authority; `ingest` exists only as a per-source service-token scope. Role bindings by scope. Service principals cannot hold approval. No permission executes production changes. |
| Audit | `audit.py` | Per-organisation hash chain, appended inside the audited transaction, with anchors exported to an external file sink. Tamper-evident within the stated threat model, not tamper-proof. |
| Secrets | `secrets.py` | Owner-only secret store. AES-256-GCM data keys. `destroy_live` is recorded as live destruction only. Scrypt-wrapped backup keyrings refuse missing keys. |
| Egress | `egress.py` | Allowlist on (scheme, host, port). One DNS resolution with every address checked; protected ranges are refused unless an entry's CIDR covers them. Connects to the checked IP with SNI. No redirects. Bounded response. |
| Backup | `backup.py` | Recovery point is one exported snapshot S. Includes active objects and raw batches still needed for recovery, plus a wrapped keyring. Restore: new installation id, fence + 1 requeue, pending objects reclaimed, continuity `restore_unreconciled`. |
| P-LOCAL | `local/__init__.py` | Managed PostgreSQL ≥ 16 cluster. Unix socket only, inside a 0700 directory. `LC_ALL` pinned (the macOS postmaster otherwise aborts with "became multithreaded during startup"). |
| Migration skeleton | `legacy/catalog_v2.py`, `legacy/migration.py` | Read-only v2 reader. Freeze sets `user_version = 9002`, which every released runtime refuses (`history_storage.py:358-363`). Inventory and resume check. Inaccessible `migrating` catalog. Single-transaction cutover. Abandon before cutover only. Completion requires a recorded post-cutover backup. **Publication replay and equivalence validation are S3 work.** |
| CLI | `cli.py` | `numek local init/start/stop/status`, `db migrate`, `gc`, `backup create/verify`, `worker`, `controller`. |

### Evidence (S1 focused checks)

Environment: `validation/cg7/py313.nosync`, which is git-ignored.

- **Python:** CPython 3.13.17, from the accepted CG6 runtime lock `constraints/cg6-runtime-macos-arm64-py313.lock`.
- **Added packages** (resolved before 2026-11-01): psycopg 3.3.6, argon2-cffi 25.1.0, cryptography 50.0.2, pytest 9.2.0, pypdf 6.21.4, gunicorn 23.0.0. gunicorn is not yet used.
- **Server:** PostgreSQL 17.12 (Homebrew).
- **Host:** macOS 27.0.1 arm64, 10 CPUs, 16 GiB.

| Check | Result |
|---|---|
| `tests/platform` (56 tests, real PostgreSQL via P-LOCAL) | 56 passed, 21.9 s |
| CLI lifecycle smoke (init, status, migrate, stop) | passed |
| Large randomized interleaving (`NUMEK_INTERLEAVING_STEPS=1700`: 6 threads × 1,700 = 10,200 operations of publish, purge, compact and GC) | passed in 243.9 s: no deadlock, no unexpected error, surviving evidence exactly equals expected |

The suite covers:
- **Identity and publication:** canonical identity equivalence; checksummed migrations; JSONL and Parquet round trips; idempotent replay and conflicting reuse; duplicates, conflicts, quarantine and ambiguous batches; same-key timestamp corrections; fork and missing-predecessor refusal; purged re-import refusal; **K order = commit order under 6 concurrent writers**; concurrent identical identities published once; cross-organisation references refused by constraint; migrating catalogs inaccessible.
- **Fencing and GC:** stale attempts cannot publish, renew or complete; retries, dead letters and cancellation; deposed controllers; verify-on-read against changed and missing bytes; generation dedupe; GC against live and stale pending objects, pins, holds and grace; interrupted reclamation.
- **Compaction and purge:** compaction digests; purge during analysis aborts publication.
- **Execution:** thread caps, warm reuse per organisation, isolation recycling, deadline and RSS kills, retry semantics, lease-loss kill without write, cancellation, child publication under its fence, budget admission.
- **Security:** sessions and CSRF, token narrowing, separation of duties, cross-organisation bindings, audit tampering against anchors, keyrings and live destruction, egress protected ranges, allowlist and no-redirect.
- **Backup and migration:** backup cut and restore, refusal on a missing key, migration freeze/abandon/resume/cutover, randomized interleavings.

**Defects found and fixed during S1 verification:**
1. Concurrent staging of identical bytes raced on generation allocation. Fixed with a per-(org, sha) transaction advisory lock.
2. Staging into another organisation's catalog surfaced a raw foreign-key error. Fixed: catalog ownership is now checked in W2.
3. The warm isolation probe registry was duplicated because the child runs as `__main__`. Moved to `execution/probes.py`.
4. The PostgreSQL version parse failed on Homebrew's suffix.

**Not established by S1:**
- PostgreSQL RLS and hosted tenancy (deferred by plan).
- The S3 object store and remote worker hosts.
- Any performance or capacity claim; no M.5 workload has run.
- Linux qualification.
- Independent review.

ConfidenceGuard persistence still runs on catalog v2 until S3.
