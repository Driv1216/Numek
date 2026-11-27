# CG7 implementation report (S1–S10)

**Date:** 2026-11-26.
**Authority:** the founder-approved CG7 plan (sections A–Q plus Addendum R2).
**Detailed evidence:** [`IMPLEMENTATION_STATUS.md`](IMPLEMENTATION_STATUS.md).

This report closes the implementation. Standings are kept separate:

| Standing | State |
|---|---|
| Engineering correctness | Below |
| Migration equivalence | Below |
| Statistical qualification | Below |
| Resilience | Below |
| Measured performance | Below, by profile and host |
| Product completeness | Below |
| Independent review | **done** (2026-11-27): corrections required and applied; see [`docs/CG7_REVIEW_CORRECTIONS.md`](../../docs/CG7_REVIEW_CORRECTIONS.md) |
| Understanding gate | **not done** |
| Founder acceptance | **not given** |

No production-readiness claim is made (D-1).

## 1. What was built

| Stage | Delivered |
|---|---|
| S1 platform core | Schema and migrator; object store and codecs; K publication protocol; verified reader; jobs, fencing and worker hosts; `ExecutionContext`; P-LOCAL; identity, RBAC, sessions and tokens; audit; secrets; egress |
| S2 governance | Reservation-gated reader; evidence-use port; entity registry; sealed reserve |
| S3 port and migration | CG3–CG6 persistence on the platform; `ctx.run` at every supervised site; v2 → platform migration state machine with validation; v2 writer retired |
| S4 ingestion | Encrypted durable receipt; contract processing with quarantine; watermarks; directory pull; SDK; identity standings; attestations |
| S5 monitoring | H.2 incremental windows; references; measures; SM1/SM2; estimators and ledger; power planner; health and coverage |
| S6 operations | Conditions; incidents with non-transitive grouping; dossiers; notifications; retention and pins; backup and restore |
| S7 intelligence | Regions and structural links; hypothesis catalog; differential matrix; requirements and triggers; planner; patterns; domain classifier |
| S8 interventions | Proposals; approvals; handoff; execution standings; verification R1–R3 (R4 never) |
| S9 product | API (66 routes); CLI; client; reports; investigation jobs; operations console |
| S10 closure | gunicorn serving; OCI, compose and systemd; preflight and workloads; routed fact layout; resilience hardening; this closure |

Plan F.1 is implemented except for the items listed in §5 under "Not implemented". The independent technical review
(2026-11-27) found that an earlier version of this sentence overstated completeness; its corrections are recorded in
[`docs/CG7_REVIEW_CORRECTIONS.md`](../../docs/CG7_REVIEW_CORRECTIONS.md).

## 2. Gates (plan M, Addendum R2.8)

| Gate | Result |
|---|---|
| **M.1 correctness and migration** | **Pass.** K-prefix under concurrency; fencing; global uniqueness and forks; verify-on-read and TOCTOU; deletion during analysis; GC invariants and randomized interleavings (no deadlocks); H.2 window equivalence (including the routed filters); the migration validation gate, resume and point of no return; funnel reconciliation; detector contiguity; lifecycle tables; non-transitive grouping; planner; reserve rules. |
| **M.2 statistical qualification** | **Pass**, run once under the locked protocols:<br>• Q-E1 exact enumeration: worst ratio to the bound 0.02.<br>• Q-E2 SM1 null: 0–4 first alarms per panel against an allowance of 100.<br>• Q-E3 SM2 null: 0 false claims.<br>• Q-E5 planner: median delay 0.87–0.93× the prediction.<br>• Q-DC: 4.2% rejections, p = 0.82.<br>• Q-E4: the violation controls inflate as expected, and this is documented as a limit. |
| **M.3 resilience** | **Pass** (S10, `tests/platform/test_resilience.py` plus earlier focused tests):<br>• a crash at each of 5 processing boundaries;<br>• a full object store;<br>• SIGKILL of a worker host mid-job (twice);<br>• SIGKILL of an API worker, then of the whole server;<br>• SIGKILL of the controller;<br>• host clock skew of ±1 h;<br>• a database restart under the worker and controller loops;<br>• webhooks that return 500 or hang, through to the dead letter.<br>Also covered: no acknowledged batch lost, no duplicate fact, K contiguous, ready within 60 s. Covered earlier: raw durability, detector double application, stale and deposed writers, lease loss, backup with unprocessed batches, migration crash points. |
| **M.4 security** | **Pass.** The S9 authorization matrix over every route × role; CSRF; tokens narrow and never widen; organisation scoping by constraint; egress (protected ranges, no redirects); log scanner; audit tamper detection; approval without side effects; warm-worker leakage. Added in S10: session rotation, absolute expiry and revocation; token expiry with hash-only storage; secret files 0600 / 0700, with loosened, hard-linked and symlinked files refused. This was a focused ASVS L1-area review; **no compliance claim**. |
| **M.5 performance** | Engineering objectives on the admitted workload; see §3. |
| **Incrementality (mandatory, R2.8)** | **Pass, both phases** (W-DEV-S1, routed layout, after the review corrections): close **1.126**, maturity **1.131**, against ≤ 1.3. The S10 closure had measured the close phase only (1.15); the review required the maturity phase too. |
| **M.6 product and compatibility** | **Pass with recorded partial journeys.** J1–J5 were run in a real browser. R2/R3 claims and sampled-replay standings are not reachable in the demo (see the status file). Installed wheel: the `operations` extra in a fresh environment outside the source tree runs `ops init` (schema 14), publishes a batch, and serves `readyz` and the console under gunicorn. |
| **Closure gate (all affected suites, once)** | **Pass.** After the review corrections: platform 224 (S10: 215); CG1–CG6 unchanged counts below. S10: Platform 215; CG1 38; CG2 43 (1 skip); CG3 67; CG4 312; CG5 109; CG6 104 (10 hardware skips). DataTrust: every failure set is identical to the committed HEAD (missing optional extras and pre-existing frozen-result checks), so there is no regression. See the status file. |

## 3. Measured performance (development Mac, labelled as such)

| Measure | Result | Objective |
|---|---|---|
| Incrementality, close windows (90 d ÷ 30 d) | 1.126 | ≤ 1.3: met |
| Incrementality, maturity windows (90 d ÷ 30 d) | 1.131 | ≤ 1.3: met |
| Durable ack p95 (10k rows) | 0.18 s | < 2 s: met |
| Live publish lag | 18–19 s | < 5 min: met |
| Daily window p50 / p95 (10k units) | close 7.3 / 9.7 s; maturity 6.7 / 8.2 s | < 2 min at W-REF size: not measured at that size |
| Restart to ready | 0.91 s | < 60 s: met |
| Database bytes per indexed fact | ~1,420 | ≤ 150: **not met** |
| Parquet vs JSONL (codec) | 20.5% | ≤ 40%: met by the codec; ingestion still writes JSONL |
| Essential-lane latency during backfill plus a CG6 job | not measured | ≤ 2× idle |

- **All values are from one complete routed W-DEV-S1 run** on the corrected source (2026-11-27,
  `results/review_corrections/w-dev-s1-routed.json`). The S10 routed run had been stopped after its close windows
  (defect 10), so its ack, lag and restart values were unrouted.
- **Workloads not admitted:** W-REF and W-DEV are `not_admitted_on_host` (disk), with their identities retained.
  W-DEV-S1 is a separately named smaller workload.
- **Not qualified:** P-SERVER is intended, not qualified.

## 4. Defects found in S10 and fixed

The workload and the resilience tests found defects that the CI-sized tests could not:

1. A non-incremental late-revision scan (cursor table, migration 0013).
2. The revision catch-up, three times:
   - an OR of IN lists;
   - a hash join over the whole index;
   - a quadratic plan on the routed layout, now LATERAL probes.
3. Quadratic duplicate and locator scans in capture.
4. Whole-index merge and hash joins in prefetch and publication (`point_lookups`).
5. Double population resolution in governed reads.
6. A full fact count per window to read K.
7. P-LOCAL running PostgreSQL defaults (host tuning).
8. **Window reads scanning every partition.** Fixed by the routed layout, migration 0014, founder approved.
9. **A full disk** surfaced as a raw OS error and left a partial file. Now `storage_full`, retryable, 507.
10. **The worker host and controller loops died when the database restarted.** Now transient.
11. **Ingestion API** database errors returned 500. Now 503 with `Retry-After`.

## 5. Not done, deferred or limited (no claim made)

- **Deferred by the plan, seams only:**
  - the S3 object store;
  - OIDC;
  - remote worker hosts;
  - row-level security and per-org keys (D-2);
  - database and S3 connectors;
  - intervention executors;
  - Iceberg export.
- **D-1:** no supported installation-wide backup for shared installations; no production readiness.
- **Not implemented** (plan F.1 items and contract details without an implementation; no claim made):
  - **policy monitoring** (G.2 Policy: supplied actions against a frozen CG5 replay, constraint ledger). The coverage map
    reports the policy dimension `not_configured`;
  - **coverage-miss and deferral statistics** (G.3). Interval and set outputs are therefore not monitored for coverage,
    and the uncertainty investigation (`cg2_uncertainty_study`) is never eligible;
  - **executable CG5 policy-replay and CG2 recalibration investigations.** Both templates refuse with an explicit reason
    (an operator-authored replay specification; a restricted reserve study). H-POLICY, H-CALIB and H-UNC therefore have no
    automatic discriminating investigation;
  - **a verified catalog v2 backup at freeze** (R2.6). The freeze changes only the v2 `user_version` and one settings
    row, and abandon restores them, so the v2 bytes remain the pre-migration copy; operators who want an independent
    copy take a v2 workspace backup first;
  - a scheduled object scrubber (only the rehash primitive exists);
  - per-token rate limits beyond ingestion backpressure. (Password sign-in is throttled per name since the review.)
- **Implemented since the review** (previously missing, see the corrections document): R2.4 comparability of invalid-
  outcome and late-exclusion rates alongside label availability; the measured reference/stream entity overlap; R2.5
  admission of SM2 recovery tests; backup of every operational secret and of the installation configuration.
- **Phase-result budget.** About 20k units per phase through the JSON result, so no window larger than about 20k units
  can be evaluated: W-REF-sized **and W-DEV-sized** windows (2M and 200k predictions a day) cannot run until per-unit
  rows stop passing through the result, whatever the hardware. Needs a founder decision.
- **Storage objective missed** (~10×). Parquet ingestion is unused.
- **systemd units** unverified. **P-SERVER, W-REF and tier C** unmeasured.
- **Journey gaps** where the demo cannot supply evidence:
  - matured post-change outcomes (R2/R3);
  - a registered predictor (sampled consistency);
  - recalibration studies outside the planner.
- **Remaining growth in close windows** is about 0.9 s across 60 more days, mostly the exposure-registry upsert.
  Within the gate.

## 6. Decisions for the founder

1. **Accept or reject CG7** after independent review and the understanding gate.
2. **Phase-result budget:** stop returning per-unit rows through job results, which enables W-REF-sized windows.
3. **Storage per fact:**
   - narrower index rows;
   - fewer secondary indexes;
   - moving `fact_occurrences` into objects;
   - or accept the measured size.
4. **Parquet observation objects** for ingestion.
5. **Linux qualification hardware** for W-REF and P-SERVER, if and when P-SERVER is to be claimed.
