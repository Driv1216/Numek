# ConfidenceGuard CG7: evidence-driven reliability operations

CG7 turns ConfidenceGuard from analyses a user runs into a service that watches deployed models continuously. It:
- ingests production predictions and outcomes;
- monitors them with formally admitted sequential methods;
- opens and reasons about incidents;
- prepares responses that a human approves and the customer executes;
- verifies recovery.

**NUMEK never changes production.**

- **Authority:** the founder-approved CG7 plan (A–Q plus Addendum R2).
- **Evidence:** [`validation/cg7/IMPLEMENTATION_STATUS.md`](../validation/cg7/IMPLEMENTATION_STATUS.md).
- **Closure report:** [`validation/cg7/CG7_IMPLEMENTATION_REPORT.md`](../validation/cg7/CG7_IMPLEMENTATION_REPORT.md).
- **Foundation:** [`docs/NUMEK_PLATFORM.md`](NUMEK_PLATFORM.md).
- **Formal methods and proofs:** [`docs/CG7_SEQUENTIAL_METHODS.md`](CG7_SEQUENTIAL_METHODS.md).

## What CG7 rests on

CG1–CG6 analytical kernels, contracts, method identities and refusals are unchanged. CG7 moved their persistence
onto the platform:
- The catalog v2 writer is retired; a read-only legacy reader remains, and the migration is validated.
- Execution is behind `ctx.run`.
- CG7 operations are built on top.

## Capabilities

**Registration (S4).**
- Systems, deployments with a registered identity, and sources with versioned contracts.
- Monitoring definitions are inspected first. Inspection shows the population, the false-alarm plan, the detection
  planner and the refusals. Only the inspected digest can then be confirmed.

**Ingestion (S4).**
- HTTP batches, a scheduled directory pull, and a thin SDK with a durable disk buffer.
- The acknowledgment (202) means the exact bytes are durable and encrypted.
- Processing publishes facts with CG3's identity, correction and deduplication rules. Rows that fail the contract are
  quarantined per row with the reason, and the funnel (received = published + duplicate + quarantined) reconciles.
- Watermarks and lateness decide window closure.
- Backfills run in the maintenance lane.
- Identity standings run from declared to registered, spec-compatible, sampled-output-consistent and
  customer-signed (Ed25519).
- Raw bodies are retained 7 days.

**Monitoring (S5).**
- Half-open event-time windows. A close phase (outcome-free measures) and a maturity phase (matured outcomes under
  `equal_followup`).
- Late publications create window revisions. Detector inputs are frozen at maturity.
- Detectors:
  - **SM1**, a bounded-mean e-CUSUM with resets. Formal statement: E[false alarms] ≤ α·E[units].
  - **SM2**, a normal-mixture confidence sequence for recovery claims.
  - Finite reference bounds.
  - A power planner that marks useless detectors `insufficient_power`.
- Outcome-free estimators (decision-specific implied error, composition projection) with matched-population
  accountability.
- Health and a coverage map: freshness, volume, lateness, maturity backlog, power.

**Operations (S6).**
- **Conditions:** emerging, active, quiescent, recovered, lapsed, suppressed.
- **Incidents:**
  - anchor-compatible, non-transitive grouping;
  - an immutable detection dossier, with append-only knowledge revisions;
  - a versioned priority table.
- **Notifications:** signed webhooks and SMTP through an allowlisted egress, with retries and backoff, a dead
  letter, and digests.
- **Retention and pins.** Measurements whose facts were purged become `summary_only`.
- **Backup and restore.**

**Intelligence (S7).**
- Frozen CG4 regions in monitoring, and structural links.
- A hypothesis catalog (H-COMP … H-MON) with machine-checkable observations.
- A differential matrix, information requirements with ETAs, and deferred triggers.
- A budgeted deterministic investigation planner with tiers `auto` / `confirm` / `restricted`.
- Recurring-pattern matching and a domain-classifier investigation (descriptive, with an optional exploratory
  permutation test).

**Interventions (S8).**
- Proposals carry machine-checked prerequisites and a validated evidence basis (`hypothetical_replay`,
  `independent_assessment`, `descriptive`).
- Approval has no side effect. The handoff is to the customer.
- Execution-evidence standings are kept separate.
- Recovery claims: R1 operational (outcome-free), R2 threshold, R3 non-inferiority to reference; R4 causal is never
  claimed. `accepted_risk` is never recovery. R2/R3 are formal only under the same admission as SM1 (maturity, unit
  design, reference design); otherwise a crossing is a descriptive indication, never recovery.

**Product (S9).**
- An API (`/api/ops/v1`, 66 routes, each with a declared permission; OpenAPI).
- Server-side sessions with CSRF, or scoped tokens.
- The `confidenceguard ops` CLI, a standard-library `OpsClient`, and the operations console at `/ops/`.
- Incident reports in HTML, PDF and JSON, for local and shareable audiences.

**Closure (S10).**
- gunicorn serving with the TLS / trusted-proxy guard.
- An OCI image, a compose example and systemd units.
- `ops preflight` workload admission and the workload runner.
- The routed fact layout (migration 0014).
- Resilience hardening: database outages, a full object store, process kills.

## Standings shown everywhere

| Code | Standing |
|---|---|
| D | deterministic violation |
| F | formally admitted sequential or finite claim |
| P | practical effect beyond a declared threshold (descriptive) |
| E | estimated (named assumption) |
| X | experimental (CG6) |
| A | association |
| H | hypothesis |

The absence of conditions is never shown as health. Coverage, freshness, maturity backlog and detector power are
shown beside it.

## Running it

```bash
confidenceguard ops init --root /path/to/installation
```

```bash
confidenceguard ops preflight --workload W-DEV-S1 --scratch /path/to/scratch --out preflight.json
```

```bash
confidenceguard ops serve --installation /path/to/installation --port 8443 --tls-cert cert.pem --tls-key key.pem
```

```bash
confidenceguard ops controller --installation /path/to/installation
```

```bash
confidenceguard ops worker --installation /path/to/installation
```

- The `operations` extra installs the service dependencies.
- P-LOCAL needs PostgreSQL ≥ 16 binaries.
- Server packaging and profiles are described in [`deploy/README.md`](../deploy/README.md).

## Measured performance (this development Mac; P-SERVER not qualified)

W-DEV-S1 is a separately named smaller workload: 10k predictions a day, 30 features, 30- and 90-day histories.
W-REF and W-DEV keep their identities and are `not_admitted_on_host` (disk).

| Measure | Result |
|---|---|
| Incrementality gate (90 d ÷ 30 d, ≤ 1.3 required) | close **1.126**, maturity **1.131** |
| Daily window, p50 / p95 | close 7.3 / 9.7 s; maturity 6.7 / 8.2 s |
| Durable acknowledgment p95 (10k rows) | 0.18 s |
| Live publish lag | 18–19 s |
| Restart to ready | 0.91 s in the workload; within the 60 s bound after SIGKILL of the API and after a database restart (tested) |

All from one complete routed run after the review corrections. Storage is about 1,420 database bytes per fact,
against the ≤ 150 objective (**missed**).

## Not implemented in CG7

- Policy monitoring (supplied actions against a frozen CG5 replay); the coverage map shows it `not_configured`.
- Coverage-miss and deferral detector statistics (uncertainty coverage is not monitored).
- Executable CG5 policy-replay and CG2 recalibration investigations (both refuse with a reason).

The independent review's corrections are in [`CG7_REVIEW_CORRECTIONS.md`](CG7_REVIEW_CORRECTIONS.md).

## What CG7 does not establish

- Causal explanations, or the effect of an intervention.
- Performance for unlabelled, immature, late-excluded or reserve-withheld units.
- Average-risk statements from alarms.
- Attestation without customer signatures.
- Independence from external evidence use.
- HA, multi-tenancy, compliance.
- Capacity beyond the measured profiles.
- Linux qualification.

D-1 remains: no production-readiness claim is made for shared installations.
