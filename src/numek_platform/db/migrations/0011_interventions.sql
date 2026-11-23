-- ConfidenceGuard CG7 interventions (S8): proposals with evidence and verification plans, approvals (no side
-- effects), execution handoffs, execution-evidence standings and recovery verification (plan G.9, G.10, I.9).
--
-- NUMEK never executes a change. A handoff is an immutable packet that the customer acts on; what happened
-- afterwards is recorded as separate execution standings, and actual production evidence is never merged
-- with hypothetical replay.

CREATE TABLE ops_proposals (
    org_id uuid NOT NULL,
    id uuid NOT NULL,
    incident_id uuid NOT NULL,
    deployment_id text NOT NULL,
    kind text NOT NULL CHECK (kind IN ('policy_guard', 'threshold_change', 'recalibration', 'model_rollback', 'model_replacement',
                                       'data_fix', 'monitoring_fix', 'accepted_risk_with_mitigation')),
    title text NOT NULL,
    state text NOT NULL CHECK (state IN ('draft', 'submitted', 'approved', 'rejected', 'handed_off', 'executing', 'verifying',
                                         'verified', 'not_verified', 'withdrawn')),
    author text NOT NULL,
    change jsonb NOT NULL,                   -- what the customer would change (data only)
    expected_identity jsonb NOT NULL DEFAULT '{}',
    evidence jsonb NOT NULL,                 -- [{basis, ref, effects, validated}]
    prerequisites jsonb NOT NULL,            -- declared machine-checked prerequisites and their last results
    risks jsonb NOT NULL DEFAULT '[]',
    required_role text NOT NULL DEFAULT 'approver',
    verification_plan jsonb NOT NULL,
    causal_evidence jsonb,                   -- R4 slot: randomized or staggered rollout evidence (not claimed in CG7)
    revision integer NOT NULL DEFAULT 1,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (org_id, id),
    FOREIGN KEY (org_id, incident_id) REFERENCES ops_incidents(org_id, id),
    FOREIGN KEY (org_id, deployment_id) REFERENCES ops_deployments(org_id, id)
);
CREATE INDEX ops_proposals_by_incident ON ops_proposals (org_id, incident_id, created_at);

CREATE TABLE ops_proposal_events (
    seq bigserial PRIMARY KEY,
    org_id uuid NOT NULL,
    proposal_id uuid NOT NULL,
    kind text NOT NULL,
    payload jsonb NOT NULL DEFAULT '{}',
    actor text NOT NULL,
    at timestamptz NOT NULL DEFAULT clock_timestamp(),
    FOREIGN KEY (org_id, proposal_id) REFERENCES ops_proposals(org_id, id)
);

CREATE TABLE ops_approvals (
    org_id uuid NOT NULL,
    proposal_id uuid NOT NULL,
    approver text NOT NULL,
    decision text NOT NULL CHECK (decision IN ('approved', 'rejected')),
    reason text,
    proposal_revision integer NOT NULL,
    at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (org_id, proposal_id, approver),
    FOREIGN KEY (org_id, proposal_id) REFERENCES ops_proposals(org_id, id)
);

CREATE TABLE ops_handoffs (
    org_id uuid NOT NULL,
    id uuid NOT NULL,
    proposal_id uuid NOT NULL UNIQUE,
    packet_object uuid NOT NULL,
    packet_digest text NOT NULL,
    issued_by text NOT NULL,
    issued_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (org_id, id),
    FOREIGN KEY (org_id, proposal_id) REFERENCES ops_proposals(org_id, id),
    FOREIGN KEY (org_id, packet_object) REFERENCES objects(org_id, id)
);

CREATE TABLE ops_execution_standings (
    org_id uuid NOT NULL,
    id uuid NOT NULL,
    proposal_id uuid NOT NULL,
    standing text NOT NULL CHECK (standing IN ('execution_declared', 'identity_consistent_with_handoff', 'behavior_change_observed',
                                               'sampled_behavior_consistent', 'execution_attested')),
    outcome text NOT NULL CHECK (outcome IN ('established', 'failed', 'not_evaluable')),
    evidence_kind text NOT NULL CHECK (evidence_kind IN ('declaration', 'production', 'signature')),
    evidence jsonb NOT NULL,
    recorded_by text NOT NULL,
    recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (org_id, id),
    FOREIGN KEY (org_id, proposal_id) REFERENCES ops_proposals(org_id, id)
);
CREATE INDEX ops_execution_by_proposal ON ops_execution_standings (org_id, proposal_id, standing, recorded_at);

CREATE TABLE ops_verifications (
    org_id uuid NOT NULL,
    proposal_id uuid NOT NULL,
    claim_id text NOT NULL,
    claim text NOT NULL CHECK (claim IN ('R1', 'R2', 'R3')),
    condition_id uuid,
    detector_id text,                        -- the SM2 recovery test (R2/R3)
    start_window bigint,
    state text NOT NULL CHECK (state IN ('pending', 'running', 'established', 'not_established')),
    result jsonb,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    finished_at timestamptz,
    PRIMARY KEY (org_id, proposal_id, claim_id),
    FOREIGN KEY (org_id, proposal_id) REFERENCES ops_proposals(org_id, id)
);
