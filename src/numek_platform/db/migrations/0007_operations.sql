-- ConfidenceGuard CG7 operations: registration and ingestion (S4).
--
-- A system owns one evidence catalog; its deployments are the model versions
-- that serve it; a source is a versioned ingestion contract feeding one
-- deployment. Received bodies are encrypted platform objects; a batch row is
-- the durable acknowledgement. Quarantine rows carry reasons and locations,
-- never values (minimized rows are kept encrypted, with their own retention).

CREATE TABLE ops_systems (
    org_id uuid NOT NULL,
    id text NOT NULL CHECK (id ~ '^[a-z0-9][a-z0-9_.-]{0,63}$'),
    name text NOT NULL,
    catalog_id uuid NOT NULL,
    namespace text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (org_id, id),
    UNIQUE (catalog_id),
    FOREIGN KEY (org_id, catalog_id) REFERENCES catalogs(org_id, id)
);

CREATE TABLE ops_deployments (
    org_id uuid NOT NULL,
    id text NOT NULL CHECK (id ~ '^[a-z0-9][a-z0-9_.-]{0,63}$'),
    system_id text NOT NULL,
    name text NOT NULL,
    tier integer NOT NULL DEFAULT 2 CHECK (tier BETWEEN 1 AND 4),
    registered_identity jsonb NOT NULL DEFAULT '{}',     -- model id/version, artifact digest, predictor spec digest
    attestation_public_key bytea,                        -- Ed25519 (customer signing key), optional
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (org_id, id),
    FOREIGN KEY (org_id, system_id) REFERENCES ops_systems(org_id, id)
);

CREATE TABLE ops_sources (
    org_id uuid NOT NULL,
    id text NOT NULL CHECK (id ~ '^[a-z0-9][a-z0-9_.-]{0,63}$'),
    deployment_id text NOT NULL,
    version integer NOT NULL CHECK (version >= 1),
    contract jsonb NOT NULL,
    contract_digest text NOT NULL,
    state text NOT NULL CHECK (state IN ('active', 'retired')),
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (org_id, id, version),
    FOREIGN KEY (org_id, deployment_id) REFERENCES ops_deployments(org_id, id)
);
CREATE UNIQUE INDEX ops_sources_active ON ops_sources (org_id, id) WHERE state = 'active';

CREATE TABLE ops_batches (
    org_id uuid NOT NULL,
    source_id text NOT NULL,
    batch_id text NOT NULL CHECK (length(batch_id) BETWEEN 1 AND 128),
    id uuid NOT NULL UNIQUE,
    contract_version integer NOT NULL,
    raw_sha256 bytea NOT NULL CHECK (length(raw_sha256) = 32),   -- plaintext digest: idempotency only
    raw_bytes bigint NOT NULL,
    raw_object uuid NOT NULL,
    state text NOT NULL CHECK (state IN ('received', 'processing', 'published', 'quarantined', 'failed')),
    mode text NOT NULL DEFAULT 'live' CHECK (mode IN ('live', 'backfill')),
    declared_identity jsonb NOT NULL DEFAULT '{}',
    producer_dropped bigint NOT NULL DEFAULT 0 CHECK (producer_dropped >= 0),   -- SDK-reported known loss
    counts jsonb NOT NULL DEFAULT '{}',
    catalog_sequence bigint,
    error jsonb,
    received_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    finished_at timestamptz,
    PRIMARY KEY (org_id, source_id, batch_id),
    FOREIGN KEY (org_id, raw_object) REFERENCES objects(org_id, id)
);
CREATE INDEX ops_batches_state ON ops_batches (org_id, state, received_at);

CREATE TABLE ops_quarantine (
    org_id uuid NOT NULL,
    id uuid NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
    batch uuid NOT NULL REFERENCES ops_batches(id),
    ordinal bigint NOT NULL,                       -- row number in the batch, or -1 for a fact-level conflict
    reasons text[] NOT NULL,
    fields text[] NOT NULL DEFAULT '{}',           -- offending field names (never values)
    fact jsonb,                                    -- kind/key/revision for fact-level conflicts
    rows_object uuid,                              -- encrypted minimized rows of this batch's quarantine
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    FOREIGN KEY (org_id, rows_object) REFERENCES objects(org_id, id)
);
CREATE INDEX ops_quarantine_batch ON ops_quarantine (batch);

CREATE TABLE ops_watermarks (
    org_id uuid NOT NULL,
    source_id text NOT NULL,
    through_tick numeric NOT NULL,                 -- producer-declared completeness, ns since epoch
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (org_id, source_id)
);

CREATE TABLE ops_deployment_events (
    org_id uuid NOT NULL,
    id uuid NOT NULL,
    deployment_id text NOT NULL,
    kind text NOT NULL CHECK (kind IN ('model_change', 'configuration_change', 'data_pipeline_change', 'rollout',
                                       'rollback', 'other')),
    at timestamptz NOT NULL,
    identity jsonb NOT NULL DEFAULT '{}',
    detail jsonb NOT NULL DEFAULT '{}',
    recorded_by text NOT NULL,
    recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (org_id, id),
    FOREIGN KEY (org_id, deployment_id) REFERENCES ops_deployments(org_id, id)
);

CREATE TABLE ops_identity_standings (
    org_id uuid NOT NULL,
    id uuid NOT NULL,
    deployment_id text NOT NULL,
    standing text NOT NULL CHECK (standing IN ('declared', 'registered', 'spec_compatible', 'sampled_output_consistent',
                                               'customer_signed_statement_verified')),
    outcome text NOT NULL CHECK (outcome IN ('established', 'failed', 'not_evaluable')),
    period_start timestamptz,
    period_end timestamptz,
    evidence jsonb NOT NULL DEFAULT '{}',
    recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (org_id, id),
    FOREIGN KEY (org_id, deployment_id) REFERENCES ops_deployments(org_id, id)
);
CREATE INDEX ops_identity_by_deployment ON ops_identity_standings (org_id, deployment_id, standing, recorded_at);

CREATE TABLE ops_directory_files (
    org_id uuid NOT NULL,
    source_id text NOT NULL,
    path text NOT NULL,
    size bigint NOT NULL,
    mtime_ns bigint NOT NULL,
    sha256 bytea NOT NULL,
    batch_id text NOT NULL,
    seen_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (org_id, source_id, path, sha256)
);

CREATE TABLE ops_raw_keys (                        -- one data key per org per UTC day for raw bodies (R2.7)
    org_id uuid NOT NULL,
    day date NOT NULL,
    purpose text NOT NULL CHECK (purpose IN ('raw_batch', 'quarantine_rows')),
    key_id uuid NOT NULL,
    PRIMARY KEY (org_id, day, purpose),
    FOREIGN KEY (org_id, key_id) REFERENCES key_records(org_id, key_id)
);
