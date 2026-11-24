# ConfidenceGuard operations console: research and proposal

This is CG7 plan section J, the "Console" from stage S9. Nothing is built yet, and it needs your approval first.
Everything below is drawn from the real CG7 product as it stands at S8. That product is the operations API in
`src/confidenceguard/operations/api.py` (44 declared routes plus session, OpenAPI, readiness and metrics) and the data it returns for the S6–S8 test scenario.

## 1. What I researched

### 1.1 The real product the console sits on

**There is one API and one source of truth.** The console is a client of `/api/ops/v1`. It adds nothing the API
doesn't have.

- **Authentication.** Server-side sessions (`numek_session`: HttpOnly, SameSite=Strict, Secure under TLS, idle and
  absolute timeouts). Every mutation carries an `X-CSRF-Token`.
- **Authorization.** Every route declares a permission: `read`, `operate`, `analyze`, `intervention:approve`,
  `admin` or `reserve:consume`. The console hides what the principal can't do, and the server enforces it anyway.
  The S9 authorization matrix covers every route for every role.

**What the scenario returns, used for the screens below:**

| Object | Real content |
|---|---|
| Incident #1 | **P1**, rule `formal_tier1` ("Formal sequential alarm on a tier-1 deployment"). The anchor is `detector:brier`, and `detector:matured-error` joined by `population_overlap` (Jaccard ≥ 0.5 on the same windows). |
| Its alarm wording | "The matured observed-label sequence since the detector start is inconsistent (expected false alarms ≤ α per included unit, α = {alpha}) with per-unit conditional {statistic} risk never exceeding {m0}…". It lists "not established": average risk, cause, a probability that degradation occurred, unlabelled units. The figures come from the detector plan; the first build will show the live values. |
| Incident #2 | **P2**, `deterministic_high`, from `health:empty_window` (Mar 22–Apr 5 has no data). Health says "not monitored, not healthy". |
| Differential (S7 scenario) | H-WITHIN supported (✓ within-group change), H-COMP contradicted (✗ composition projection), H-LABEL contradicted, H-MON contested, H-DEPLOY unresolved. The requirement reads "Register the deployment identity (and a CG6 predictor spec…)", and H-UNC is untestable (coverage not monitored). |
| Planner | It considered 8 templates: 5 auto runs planned, 30-minute budget, `cg6_shadow_replay` ineligible ("no registered CG6 predictor spec"), `cg2_recalibration_study` awaiting approval (restricted). |
| Proposal (S8) | "Roll back…": evidence `hypothetical_replay` (validated investigation run), effects error 0.1 [0.08, 0.12], prerequisites ✓✓✓✓. Approval had no side effects, and the handoff digest was verified. |
| After execution | `execution_declared` ✓, `identity_consistent_with_handoff` ✓ (v2 batches), `execution_attested` ✓, then a forged signature ✗. R2 and R3 claims were established from window 9; the resolution is `threshold_recovery_established`. |
| Health / coverage | matured_performance **formal**, behavior descriptive_measures_only, regions not_configured, plus freshness, maturity backlog and detector lag. |

**What the product refuses to show, and the console must not invent:**
- an overall health score;
- "all good" when nothing alarmed;
- a cause;
- any average-risk claim from an alarm.

### 1.2 The approved design system

The design system is concept 22, "Deep water", in `frontend/src/foundation/nk.css`.
- **Paper** `#F3F1EC`, **ink** `#0F1B22`, and ConfidenceGuard **sea glass** `#3F8F86` (light `#D6EAE6`, dark
  `#1F4D47`).
- **Coral** `#E5553B` marks evidence only.
- **Severity** is shown by shape (filled, half-filled or outlined), never by more colours.
- **Type and lines:** Modules tiles, Schibsted Grotesk and IBM Plex Mono, and Markup hairlines and leader lines that
  draw once.
- **Layout:** light, never dark.

The existing DataTrust app (`frontend/src/app`) is a separate Vite build served by its own product. The bundle check
forbids external hosts.

### 1.3 How comparable tools do it (public docs, read 23 Nov)

- **Model-monitoring tools** (Arize, Fiddler, WhyLabs, Evidently) lead with **metric dashboards and threshold
  alerts**: panels grouped in tabs, anomaly counters, drill-down from a chart into events, and RCA scoped to the
  chart's segment and time range.
- **Incident tools** (Datadog, incident.io) centre on an **incident page**: an overview with properties and impact,
  a timeline as the main record, and a remediation area.

**What none of them do.**
- None states what an alarm does *not* establish.
- None separates formal from descriptive evidence.
- None keeps competing explanations in a matrix.
- None keeps verified recovery distinct from "the alert stopped".

**The differentiator is reasoning and standing, not charts.** So the console should make the incident workspace
excellent, and keep fleet charts few and honest.

## 2. Decisions I need from you first

1. **Where it lives.**
   - **A (recommended):** a separate build at `/ops/` (`frontend/src/ops`, `vite.ops.config.ts`), served by
     `confidenceguard ops serve`, exactly as plan section K says.
   - **B:** inside the existing app.
2. **Density.** The Modules tiles are bold, and an operations console needs scannable tables.
   - **A (recommended):** Modules tiles for the fleet and deployment summaries. Calm, dense, mono-figured tables
     inside the incident workspace, where people read evidence.
   - **B:** tiles everywhere.
3. **First build scope.**
   - **A (recommended):** the shell, login, Fleet and the Incident workspace, then stop for your review.
   - **B:** all seven areas at once.
4. **Your notes park ConfidenceGuard pages until the product is done.** CG7 has an S10 closure still to come. Do you
   want the console now (after S9's back end, as planned), or after the S10 gate?

## 3. Proposal

### Shell (every screen)

- **App bar:**
  - the NUMEK mark;
  - "ConfidenceGuard · operations" in sea glass;
  - the installation and the signed-in principal with their roles;
  - a sign-out control.
- **Left rail:** Fleet, Deployments, Incidents, Investigations, Proposals, Sources, Setup, Admin. Areas the principal
  can't act in show read-only.
- **Every figure is mono.** Every claim carries a standing glyph:

  | Glyph | Standing |
  |---|---|
  | ■ | D (deterministic) |
  | ◆ | F (formal) |
  | ◐ | P (practical, descriptive) |
  | ○ | E (estimate) |
  | ◇ | X (experimental) |
  | △ | A (association) |
  | ◌ | H (hypothesis) |

  Shapes carry meaning, and the legend is always one click away.
- **No browser analytics, no external requests.** The bundle check stays in force.

### 1 · Fleet

- **Coverage first.** Each deployment gets a Modules tile showing:
  - its coverage map: dimensions as small cells with formal ◆, descriptive ◐, insufficient power, not configured,
    or stale;
  - freshness ("not monitored since 09:00" in coral when silent);
  - maturity backlog and next maturity date;
  - open incidents by priority.
- **No health score.** The header line is the bound evaluated at observed volume: "expected false alarms per 30
  days across the fleet". Its caption is the API's wording, verbatim.

### 2 · Deployment

- **Tiles.** One tile each for:
  - the identity-standings timeline (declared → registered → spec-compatible → sampled-consistent → signed);
  - definition versions (inspect / confirm history);
  - detectors with standing, power and lag;
  - label maturity;
  - the estimator ledger (bias, exceedances);
  - region exposure.
- **Charts are drawn once, Markup-style.** The window series uses dimension lines for the null level m₀. Alarm
  points are coral, and the onset is a leader line labelled "approximate onset (descriptive)".

### 3 · Incident workspace (the main surface)

Its structure follows the API's `view` and report.

- **Header.**
  - The first line answers what, where, since and how many: "#1 · scorecard-prod · since window 4 (Mar 1) ·
    {affected units} units", with the affected units from the priority impact record.
  - The priority line gives the rule and its why: "P1 · formal sequential alarm on a tier-1 deployment".
  - An "as known at detection ↔ now" toggle switches between the dossier and the latest revision. It shows K for
    each.
- **Evidence ladder.** Conditions are grouped ■ ◆ ◐ ○. Each shows its fixed wording, then "Not established" and
  "Assumptions" folded beneath it. A condition that joined shows its link and rule, for example "population overlap
  · J ≥ 0.5 to the anchor" (the recorded Jaccard value).
- **Differential matrix.** Hypotheses are rows and observations columns. The cells are ✓, ✗ and ?, with standing
  glyphs, and coral is used only on cells that changed since the last revision. A hypothesis expands into its
  supporting and contradicting evidence. "Contested" shows both sides, with the suggested tie-break.
- **Requirements and investigations.**
  - **Requirements:** each shows its ETA (for example "labels mature on {date}") or its action ("register a CG6 predictor spec").
  - **Recommended investigations:** each shows why (movable hypotheses and weights), its cost and its tier.
    "Approve" appears only for `confirm`, and for `restricted` only to a reserve steward.
- **Responses.** The comparison view, side by side:
  - the strongest evidence basis;
  - effects with intervals;
  - prerequisite checks;
  - risks;
  - matched prior mitigations;
  - the required approver.

  "Approve" states its effect in words: "Records your approval. Changes nothing in production."
- **Execution and verification.**
  - The execution standings are shown as five separate rows, each with its evidence kind.
  - The R1, R2 and R3 claims are shown separately, with "R4 · not claimed" always visible.
  - Pending maturity is shown with its date.
- **Timeline.** The H.7 events, newest first, with an "operator" or "system" actor depending on audience.
- **Export.** HTML or PDF, as the shareable or local report (local needs `evidence:protected:read`).

### 4–7 · Investigations, Proposals, Sources, Setup, Admin

- **Investigations and proposals:** lists across incidents, using the same row components as the workspace.
- **Sources:** the ingestion funnel (received = published + duplicate + quarantined), quarantine reasons (never
  values), watermarks and lateness.
- **Setup:**
  - the definition inspect screen. It shows the planner per detector: m₀, α, the expected delay (planner days
    plus the window and follow-up lag, 17 days in the scenario's definition), power, and refusals such as
    "log loss · unbounded statistic".
  - "Confirm" requires the inspection digest that was shown.
- **Admin:** users, roles, tokens (shown once), channels and rules, retention and pins, and audit-chain
  verification.

### Journeys covered

| Journey | Covered by |
|---|---|
| J1 (onboard) | Setup |
| J2 (monitoring gap) | Fleet freshness, then the P2 incident |
| J3 (emerging risk, region) | The workspace: ladder, matrix, requirements, investigations, responses, verification |
| J4 (calibration) | H-CALIB and the restricted study approval |
| J5 (identity drift) | Identity standings, H-DEPLOY, and the shadow-replay approval |

Every journey is driven against the synthetic generator, with real API responses.

### States and accessibility

- **Every list has these states:**
  - empty: what that means, never "healthy";
  - loading;
  - refused: the API's code and message, verbatim;
  - stale revision: reload, then retry.
- **Operator edits** send `expected_revision`.
- **Accessibility:** keyboard-complete; glyphs have text alternatives; the matrix is a real table with headers;
  reduced motion shows every line already drawn.

## 4. Build plan, with a stop after step 1

1. **First build, then a review stop:** the shell, login, Fleet and the Incident workspace on the live API, verified
   with DOM and text checks. No screenshots unless you ask, and the dev server is stopped afterwards.
2. Deployment and Setup (inspect / confirm).
3. Investigations, Proposals and Sources.
4. Admin, and the J1–J5 runs in a real browser (plan M.6).

## 5. Ground rules

- Real figures only. Synthetic scenarios are labelled as such.
- No health score, certification, production-approval or causal claims.
- Wording comes from the API (alarm, recovery, limitation texts) and is never paraphrased into something stronger.
- Coral marks evidence only, and severity is shown by shape.
