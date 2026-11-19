# CG7 implementation status

The technical authority is the founder-approved CG7 plan: revised plan sections A–Q plus Addendum R2. This file
records what is implemented and what evidence exists, stage by stage. Several kinds of standing are kept separate:
engineering correctness, statistical qualification, resilience, measured performance, product completeness,
independent review and founder acceptance.

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

**The other 29 failures are obsolete v2-specific assertions** (they are the S3d test port). Each was checked against its failing line:

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
| S3b | CG4/CG5/CG6 storage, raw-SQL and object-path sites, deletion and backup | **implemented (record above)** |
| S3c | v2 → platform replay and equivalence validation | pending |
| S3d | `ctx.run` refactor, remaining test port, v2 writer retirement | pending |

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
