-- ConfidenceGuard CG7 intelligence (S7): hypothesis states and the differential matrix, information
-- requirements and deferred triggers, the budgeted investigation planner and its runs (plan I).
--
-- Hypothesis states are recomputed with every knowledge revision; each change is an incident event.
-- Investigation runs are deduplicated by logical fingerprint (R2.7) and bound to the incident.

CREATE TABLE ops_hypotheses (
    org_id uuid NOT NULL,
    incident_id uuid NOT NULL,
    hypothesis_id text NOT NULL,
    state text NOT NULL CHECK (state IN ('proposed', 'supported', 'contradicted', 'contested', 'unresolved', 'untestable')),
    reason text,
    evidence jsonb NOT NULL,                 -- supporting and contradicting observations with their standing
    knowledge_revision integer NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (org_id, incident_id, hypothesis_id),
    FOREIGN KEY (org_id, incident_id) REFERENCES ops_incidents(org_id, id)
);

CREATE TABLE ops_requirements (             -- information requirements: missing evidence made explicit
    org_id uuid NOT NULL,
    incident_id uuid NOT NULL,
    observation text NOT NULL,
    status text NOT NULL CHECK (status IN ('open', 'satisfied', 'withdrawn')),
    reason text NOT NULL,
    eta timestamptz,                         -- when the evidence is expected (for example label maturity)
    action text,                             -- what would make it available (for example register a predictor)
    hypotheses text[] NOT NULL,
    template text,                           -- deferred trigger: the discriminating investigation to queue
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    satisfied_at timestamptz,
    triggered_run uuid,
    PRIMARY KEY (org_id, incident_id, observation),
    FOREIGN KEY (org_id, incident_id) REFERENCES ops_incidents(org_id, id)
);
CREATE INDEX ops_requirements_due ON ops_requirements (org_id, eta) WHERE status = 'open' AND template IS NOT NULL;

CREATE TABLE ops_investigation_runs (
    org_id uuid NOT NULL,
    id uuid NOT NULL,
    incident_id uuid NOT NULL,
    deployment_id text NOT NULL,
    template text NOT NULL,
    tier text NOT NULL CHECK (tier IN ('auto', 'confirm', 'restricted')),
    state text NOT NULL CHECK (state IN ('planned', 'awaiting_approval', 'running', 'completed', 'failed', 'refused', 'reused')),
    fingerprint text NOT NULL,               -- template, spec, selection digest and K (R2.7)
    logical_fingerprint text NOT NULL,       -- the fingerprint without K (reuse comparison)
    spec jsonb NOT NULL,
    catalog_sequence bigint NOT NULL,
    value double precision NOT NULL,
    cost_minutes double precision NOT NULL,
    reasoning jsonb NOT NULL,                -- why it was selected: movable hypotheses, weights, budget
    reused_from uuid,
    stale_fraction double precision,
    approved_by text,
    result_object uuid,
    result_digest text,
    result jsonb,                            -- summary: observations it settles, standing
    error jsonb,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    finished_at timestamptz,
    PRIMARY KEY (org_id, id),
    FOREIGN KEY (org_id, incident_id) REFERENCES ops_incidents(org_id, id),
    FOREIGN KEY (org_id, result_object) REFERENCES objects(org_id, id)
);
CREATE INDEX ops_runs_by_incident ON ops_investigation_runs (org_id, incident_id, created_at);
CREATE INDEX ops_runs_by_fingerprint ON ops_investigation_runs (org_id, logical_fingerprint, created_at);
