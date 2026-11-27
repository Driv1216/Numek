# NUMEK Evidence & Execution Platform (`numek_platform`)

The platform holds all persistent ConfidenceGuard state from CG7 on. The technical authority is the
founder-approved CG7 plan (sections A–Q plus Addendum R2). Stage-by-stage evidence is in
[`validation/cg7/IMPLEMENTATION_STATUS.md`](../validation/cg7/IMPLEMENTATION_STATUS.md). This document describes
what is built, how it behaves, and its limits.

The ephemeral workbench (CG1/CG2 on files) does not use the platform. DataTrust does not use it either.

## Layers

| Layer | Role |
|---|---|
| **PostgreSQL ≥ 16** (17 in use) | The only transactional authority. It holds evidence identity and the fact index, publication order (the catalog sequence K), evidence-use and reserve governance, jobs and leases with fences, operations state, principals, and the audit chain. Schema `numek`; versioned SQL migrations `0001`–`0014`, each applied in a transaction and checksummed. |
| **Immutable object store** | Bulk evidence, content-addressed (`objects/<org>/<sha[:2]>/<sha>.<generation>`). Only the local-filesystem implementation exists (owner-only, `O_EXCL` + fsync + link + directory fsync). An S3-compatible store is a seam only. |
| **DuckDB / Arrow** | Analytical execution inside jobs, over verified in-memory buffers. Never authoritative. |
| **Jobs and worker hosts** | A PostgreSQL job table with fenced leases; worker hosts with warm and isolated job processes under process-tree supervision. |

## Consistency model

- **K-prefix consistency.** A publication writes its rows, then as its last step locks the catalog head row and
  takes `K = head + 1`. K order therefore equals commit order. A reader that sees head = K sees every
  publication ≤ K, and those never change.
- **As-of reads.** Every analytical read names K (and the outcome availability A). Results are reproducible without
  depending on a database snapshot.
- **Deletion.** Purges write tombstones at K_del. Reads that select tombstoned facts refuse with
  `historical_evidence_unavailable`. A publication whose read was overtaken by a purge of facts it read aborts with
  `evidence_deleted_during_analysis`. Purge and publication are linearized through the `catalog_tombstones` row.
- **Global lock order:** job row (fence), exposure advisory lock, object rows sorted by id, `catalog_tombstones`,
  `catalog_heads` (always last). Randomized interleavings are tested for deadlock freedom.

## Fact identity and layout

- **Identity.** The CG3 identity tuple per kind; key = SHA-256 of its canonical form. Identity is
  `(catalog, kind, key, revision)`, and `(catalog, kind, key, predecessor)` forbids correction forks.
  Timestamps are attributes, never identity, so a correction that moves time keeps its identity.
- **Routed layout (migration 0014, S10).** `fact_index` is hash-partitioned (32 partitions) by `route`:
  - predictions and context: their `opportunity_key`;
  - every other kind: their own key.

  A CHECK constraint enforces the rule. A window's opportunities, predictions and context therefore share the
  partitions of its opportunity keys. Outcomes are routed by their key, which equals the opportunity's
  `target_key`. Unique indexes include `route`. Because route is a function of identity, uniqueness stays global.
  A purged fact cannot be re-imported (checked against the global tombstone key).
- **Insertion.** COPY into a temporary table, `INSERT … ON CONFLICT DO NOTHING`, then a digest comparison:
  - an equal digest is a duplicate occurrence;
  - a different digest is a conflict (quarantined by ingestion).

  Joins from a batch-sized set into the index run under `point_lookups` (index probes only) or as LATERAL probes
  with their conditions inside, so their cost follows the batch, not the history.
- **Window selection (H.2).** First, the opportunity keys of a window at K. Then complete revision chains, plus
  predictions, context and outcomes, read by route. Then the unchanged `select_history`. Equivalence with
  full-history selection is a gate (`tests/platform/test_monitoring_windows.py`).

## Objects: lifecycle and integrity

**Write protocol (R2.1).**

| Step | Action |
|---|---|
| W1 | Stage the bytes, fsync, hash. |
| W2 | Insert the row as `pending`, under the job fence. |
| W3 | Promote the file to its permanent key. |
| W4 | Activate the row inside the publication transaction. |

Deduplication only reuses `active` rows; every other state gets a new generation.

**Garbage collection** reclaims:
- pending rows of dead or superseded attempts, after a TTL;
- tombstoned rows after a grace period, when no holds exist and no live read pin predates the tombstone.

Bytes are unlinked only after `reclaiming` has committed.

**Verify on read.** The reader hashes the exact bytes it parses. There is no metadata trust and no gap between
check and use. A rehash primitive exists (`hash_existing`), but no scheduled scrubber runs: rarely read objects are
checked only when read.

**A full disk** (ENOSPC / EDQUOT, S10) leaves no partial staged file. It is reported as `storage_full`: retryable,
HTTP 507 with `Retry-After`. Nothing is acknowledged.

## Governance before access (R2.3)

- **Reservation first.** Protected evidence (outcome values, development rows, reserve rows, protected exports) is
  returned only under a committed reservation. The reservation must match the caller's job fence or session, have
  the right purpose, and cover the requested rows.
- **Membership.** It is materialized from non-outcome fields and stored as an immutable object. A crashed or
  cancelled attempt keeps its reservation, so freshness is never regained.
- **Sealed reserve.** Namespace-level, 10%, `covariate_policy = exclude` by default. Assignment is an HMAC at first
  observation, materialized permanently. Development purposes are refused. Consumption is entity-level and needs
  the `reserve_steward` role.

## Jobs, fencing and worker hosts

- **Leases.** Claims use `SKIP LOCKED`. Every write and renewal checks `fence = mine`. Expired leases are superseded
  by the leader controller (fence + 1), so a stale attempt can neither publish nor complete.
- **The controller** is a single leader through a leadership row with an epoch. Its writes assert the epoch. A
  deposed controller cannot act.
- **Database clock.** Leadership and lease expiry are decided on the database clock (`now()`), so host clock skew
  cannot move them (tested S10).
- **Worker hosts:**
  - warm pools keyed by organisation, recycled after 100 jobs or on RSS;
  - isolated processes for heavy jobs;
  - process-tree RSS, deadline and scratch budgets;
  - native thread caps set before spawn;
  - cancellation;
  - essential-lane slots reserved.
- **Database outages (S10).** The worker host and controller loops treat the database being down, restarting or
  dropping a connection as transient. Attempts that lose their connection are killed and retried under a new
  fence. Both loops resume when the database returns (tested with a real restart).

## Identity, audit, secrets, egress

- **Principals.** Users, services and system principals, scoped by `org_id`; roles bound at org or deployment scope.
  Composite foreign keys make cross-organisation references impossible by constraint.
- **Passwords** are argon2id.
- **Sign-in** is throttled per name: after 10 failed attempts in 15 minutes further attempts get 429 (soft lockout,
  ASVS L1 anti-automation). There is no per-token rate limit beyond ingestion backpressure.
- **Metrics** (`/metrics`, counts only) are open to loopback scrapers; other clients need a signed-in principal or a
  token with read permission.
- **Sessions** are server-side:
  - a new id and secret at every login (no fixation);
  - idle and absolute lifetimes;
  - CSRF on mutations;
  - revocation.
- **Tokens** are scoped. They narrow a principal and never widen it. They are stored only as SHA-256, shown once,
  and support expiry and revocation. Ingest and approval authority are separated for service principals.
- **Audit.** A hash chain in PostgreSQL, anchored to operator-controlled sinks. It is tamper-evident against
  parties without control of both the database and the anchors. It is not tamper-proof against a database
  superuser.
- **Secrets** are held in an owner-only file store:
  - files 0600 and directories 0700;
  - loosened, hard-linked and symlinked files are refused;
  - never written to the database or returned by the API.
- **Raw batches** use AES-256-GCM with per-day data keys.
- **Routed facts.** A prediction or context fact must name its opportunity key, which is its partition route
  (`route_undetermined` otherwise), so one identity can never occupy two partitions. The key must be identity[0]: the
  producer guarantees it (ConfidenceGuard capture refuses a payload that disagrees); the database cannot hash identities.
- **Egress.** An organisation allowlist with resolve-then-connect to the checked address. Private, metadata and
  loopback ranges are denied unless allowlisted. Redirects are never followed. Timeouts and response size are
  bounded.

## Backup, restore and migration

- **Backup** is a cut at the PostgreSQL snapshot S, containing:
  - the dump;
  - every object active at S;
  - the raw objects of every batch not yet terminal at S;
  - the installation configuration and its digest (`confidenceguard ops backup create`);
  - a keyring wrapped with the operator's backup passphrase, holding every data key an included object needs, the
    other live data keys, and every operational secret: sealed-reserve assignment secrets, notification channel
    secrets, and the monitoring unit-order and audit-sampling secrets (review correction B2).

  It refuses if a required key is missing. Batches acknowledged after S are not covered (stated).
- **Restore** creates a new installation identity, requeues running jobs with fence + 1, and sets exposure
  continuity to `restore_unreconciled`. It needs nothing from the old secrets directory, and it refuses a backup that
  lacks any evidence object other than the processed raw batches the cut deliberately leaves out.
- **Catalog v2 → platform migration** is a durable state machine (freeze, copy, validate, cutover) with a single
  point of no return. The v2 writer is retired; a read-only legacy reader remains.

## Deployment profiles

- **P-LOCAL** (macOS/Linux): a managed local PostgreSQL cluster (Unix socket, 0700), sized from the host:
  - `shared_buffers` an eighth of RAM, within 128 MB–2 GB;
  - `max_wal_size` 4 GB;
  - 15-minute checkpoints;
  - WAL compression.

  Existing clusters are not changed.
- **P-SERVER** (Linux x86_64) consists of:
  - an OCI image (digest-pinned base, hash-locked dependencies, non-root);
  - a compose example;
  - hardened systemd units;
  - gunicorn `gthread` serving, with TLS or a declared trusted proxy required off loopback.

  It is **intended, not qualified**: W-REF and Linux runs of the resilience checks have not been measured. See
  [`deploy/README.md`](../deploy/README.md).
- **`ops preflight`** calibrates bytes per fact, WAL and throughput, projects disk, WAL, objects, backup and memory,
  and admits a workload against a 20% reserve, or records it as `not_admitted_on_host` with its identity retained.

## Limits (no claim made)

- **D-1:** shared installations have no supported installation-wide backup, and no production readiness is claimed.
- No HA, no hard multi-tenancy (row-level security deferred, D-2), no compliance claim.
- No S3 store, no OIDC, no remote worker hosts, no scheduled object scrubber.
- About 1,450 database bytes per indexed fact, against the ≤ 150 objective.
- Ingestion writes JSONL objects; the Parquet observation codec exists but is unused.
- P-SERVER and W-REF are unmeasured.
