-- ConfidenceGuard CG7 operations (S6): conditions, incidents, dossiers and knowledge revisions,
-- notifications (outbox, allowlisted egress), retention pins and reproducibility (plan H.7, H.8, R2.7).
--
-- State transitions, events and outbox rows commit together (H.4): histories stay consistent and
-- delivery is at least once with an idempotency key. Events are append-only.

ALTER TABLE ops_signals ADD COLUMN processed_at timestamptz;
CREATE INDEX ops_signals_unprocessed ON ops_signals (org_id, deployment_id, created_at) WHERE processed_at IS NULL;

CREATE TABLE ops_conditions (
    org_id uuid NOT NULL,
    id uuid NOT NULL,
    deployment_id text NOT NULL,
    definition_version integer,
    key text NOT NULL,                       -- source:source_id (health conditions add their source)
    kind text NOT NULL,
    standing text NOT NULL CHECK (standing IN ('D', 'F', 'P', 'E')),
    severity text NOT NULL CHECK (severity IN ('critical', 'high', 'medium', 'low', 'info')),
    state text NOT NULL CHECK (state IN ('emerging', 'active', 'quiescent', 'recovered', 'lapsed', 'suppressed')),
    prior_state text,                        -- state to return to when a suppression expires
    first_window bigint,
    last_window bigint,
    windows bigint[] NOT NULL DEFAULT '{}',  -- windows with signals (persistence k of n)
    signal_count integer NOT NULL DEFAULT 0,
    first_signal_at timestamptz NOT NULL,
    last_signal_at timestamptz NOT NULL,
    suppressed_until timestamptz,
    suppression_reason text,
    recovery jsonb,                          -- R1/R2/R3 evidence when recovered
    revision integer NOT NULL DEFAULT 1,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (org_id, id),
    FOREIGN KEY (org_id, deployment_id) REFERENCES ops_deployments(org_id, id)
);
CREATE UNIQUE INDEX ops_conditions_open ON ops_conditions (org_id, deployment_id, key)
    WHERE state IN ('emerging', 'active', 'quiescent', 'suppressed');

CREATE TABLE ops_condition_signals (
    org_id uuid NOT NULL,
    condition_id uuid NOT NULL,
    signal_id uuid NOT NULL,
    PRIMARY KEY (org_id, condition_id, signal_id),
    FOREIGN KEY (org_id, condition_id) REFERENCES ops_conditions(org_id, id),
    FOREIGN KEY (org_id, signal_id) REFERENCES ops_signals(org_id, id)
);

CREATE TABLE ops_condition_events (
    seq bigserial PRIMARY KEY,
    org_id uuid NOT NULL,
    condition_id uuid NOT NULL,
    from_state text,
    to_state text NOT NULL,
    reason text NOT NULL,
    actor text NOT NULL,
    detail jsonb NOT NULL DEFAULT '{}',
    at timestamptz NOT NULL DEFAULT clock_timestamp(),
    FOREIGN KEY (org_id, condition_id) REFERENCES ops_conditions(org_id, id)
);

CREATE TABLE ops_incidents (
    org_id uuid NOT NULL,
    id uuid NOT NULL,
    number bigint NOT NULL,
    deployment_id text NOT NULL,
    anchor_condition uuid NOT NULL,
    state text NOT NULL CHECK (state IN ('open', 'acknowledged', 'investigating', 'response_proposed', 'response_executing',
                                         'verifying', 'resolved', 'reopened', 'merged')),
    priority text NOT NULL CHECK (priority IN ('P1', 'P2', 'P3', 'P4')),
    priority_basis jsonb NOT NULL,           -- decision-table version, rule and "why"
    owner text,
    resolution text CHECK (resolution IN ('operational_recovery_observed', 'threshold_recovery_established',
                                          'reference_noninferiority_established', 'accepted_risk',
                                          'operator_false_positive', 'monitoring_artifact',
                                          'closed_without_recovery_evidence')),
    resolution_detail jsonb,
    merged_into uuid,
    escalation_level integer NOT NULL DEFAULT 0,
    escalation_due_at timestamptz,
    catalog_sequence bigint NOT NULL,        -- K at open (the detection dossier's knowledge state)
    dossier_object uuid NOT NULL,
    dossier_digest text NOT NULL,
    knowledge_revision integer NOT NULL DEFAULT 0,
    revision integer NOT NULL DEFAULT 1,     -- optimistic concurrency for operator edits
    opened_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    acknowledged_at timestamptz,
    resolved_at timestamptz,
    PRIMARY KEY (org_id, id),
    UNIQUE (org_id, number),
    FOREIGN KEY (org_id, deployment_id) REFERENCES ops_deployments(org_id, id),
    FOREIGN KEY (org_id, anchor_condition) REFERENCES ops_conditions(org_id, id),
    FOREIGN KEY (org_id, dossier_object) REFERENCES objects(org_id, id)
);

CREATE TABLE ops_incident_conditions (
    org_id uuid NOT NULL,
    incident_id uuid NOT NULL,
    condition_id uuid NOT NULL,
    joined_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    rule text NOT NULL,                      -- anchor | direct_link | population_overlap | operator_merge | operator_split
    link jsonb NOT NULL DEFAULT '{}',
    removed_at timestamptz,
    PRIMARY KEY (org_id, incident_id, condition_id, joined_at),
    FOREIGN KEY (org_id, incident_id) REFERENCES ops_incidents(org_id, id),
    FOREIGN KEY (org_id, condition_id) REFERENCES ops_conditions(org_id, id)
);
CREATE UNIQUE INDEX ops_incident_conditions_current ON ops_incident_conditions (org_id, condition_id) WHERE removed_at IS NULL;

CREATE TABLE ops_incident_events (
    seq bigserial PRIMARY KEY,
    org_id uuid NOT NULL,
    incident_id uuid NOT NULL,
    kind text NOT NULL,
    payload jsonb NOT NULL DEFAULT '{}',
    actor text NOT NULL,
    at timestamptz NOT NULL DEFAULT clock_timestamp(),
    FOREIGN KEY (org_id, incident_id) REFERENCES ops_incidents(org_id, id)
);

CREATE TABLE ops_incident_revisions (       -- knowledge revisions: appended, never rewritten
    org_id uuid NOT NULL,
    incident_id uuid NOT NULL,
    revision integer NOT NULL,
    reason text NOT NULL,
    catalog_sequence bigint NOT NULL,
    packet_object uuid NOT NULL,
    packet_digest text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (org_id, incident_id, revision),
    FOREIGN KEY (org_id, incident_id) REFERENCES ops_incidents(org_id, id),
    FOREIGN KEY (org_id, packet_object) REFERENCES objects(org_id, id)
);

CREATE TABLE ops_related_incidents (        -- suggestions only; never automatic merging
    org_id uuid NOT NULL,
    incident_id uuid NOT NULL,
    related_id uuid NOT NULL,
    reason jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (org_id, incident_id, related_id),
    FOREIGN KEY (org_id, incident_id) REFERENCES ops_incidents(org_id, id),
    FOREIGN KEY (org_id, related_id) REFERENCES ops_incidents(org_id, id)
);

CREATE TABLE ops_notification_channels (
    org_id uuid NOT NULL,
    id text NOT NULL CHECK (id ~ '^[a-z0-9][a-z0-9_.-]{0,63}$'),
    kind text NOT NULL CHECK (kind IN ('webhook', 'smtp')),
    destination text NOT NULL,               -- https URL, or smtps://host:port
    secret_name text NOT NULL,               -- HMAC key (webhook) or SMTP credentials, in the secrets store
    config jsonb NOT NULL DEFAULT '{}',      -- smtp: from, to; webhook: none
    enabled boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (org_id, id)
);

CREATE TABLE ops_notification_rules (
    org_id uuid NOT NULL,
    id text NOT NULL,
    channel_id text NOT NULL,
    deployment_id text,                      -- null: every deployment
    min_priority text NOT NULL DEFAULT 'P2' CHECK (min_priority IN ('P1', 'P2', 'P3', 'P4')),
    digest_seconds integer CHECK (digest_seconds IS NULL OR digest_seconds >= 60),
    quiet jsonb NOT NULL DEFAULT '[]',       -- suppression windows [[start_iso, end_iso]]; P1 is never held
    escalation_level integer NOT NULL DEFAULT 0,   -- 0: first notice; n: notified when escalation reaches n
    PRIMARY KEY (org_id, id),
    FOREIGN KEY (org_id, channel_id) REFERENCES ops_notification_channels(org_id, id)
);

CREATE TABLE ops_notification_outbox (
    org_id uuid NOT NULL,
    id uuid NOT NULL,
    channel_id text NOT NULL,
    rule_id text NOT NULL,
    incident_id uuid NOT NULL,
    event_seq bigint NOT NULL,
    idempotency_key text NOT NULL,
    payload jsonb NOT NULL,                  -- ids, priority, state and links only; never evidence values
    state text NOT NULL CHECK (state IN ('queued', 'held', 'digested', 'sent', 'dead')),
    attempts integer NOT NULL DEFAULT 0,
    next_attempt_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    last_error jsonb,
    digest_of uuid[],
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    sent_at timestamptz,
    PRIMARY KEY (org_id, id),
    UNIQUE (org_id, idempotency_key),
    FOREIGN KEY (org_id, channel_id) REFERENCES ops_notification_channels(org_id, id),
    FOREIGN KEY (org_id, incident_id) REFERENCES ops_incidents(org_id, id)
);
CREATE INDEX ops_outbox_due ON ops_notification_outbox (org_id, next_attempt_at) WHERE state IN ('queued', 'held');

CREATE TABLE ops_pins (                     -- explicit retention protection (H.8)
    org_id uuid NOT NULL,
    id uuid NOT NULL,
    catalog_id uuid NOT NULL,
    namespace text NOT NULL,
    start_tick numeric NOT NULL,
    end_tick numeric NOT NULL,
    holder_kind text NOT NULL CHECK (holder_kind IN ('incident', 'proposal', 'study', 'analyst')),
    holder_id text NOT NULL,
    reason text NOT NULL,
    expires_at timestamptz,                  -- null while the holder is open
    released_at timestamptz,
    created_by text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (org_id, id),
    FOREIGN KEY (org_id, catalog_id) REFERENCES catalogs(org_id, id)
);
CREATE INDEX ops_pins_live ON ops_pins (org_id, catalog_id) WHERE released_at IS NULL;

CREATE TABLE ops_retention_policies (
    org_id uuid NOT NULL,
    system_id text NOT NULL,
    observation_days integer NOT NULL DEFAULT 400 CHECK (observation_days >= 30),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (org_id, system_id),
    FOREIGN KEY (org_id, system_id) REFERENCES ops_systems(org_id, id)
);

ALTER TABLE ops_window_evaluations ADD COLUMN reproducibility text NOT NULL DEFAULT 'reproducible'
    CHECK (reproducibility IN ('reproducible', 'summary_only'));
