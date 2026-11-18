-- NUMEK platform core schema (S1).
--
-- Ownership: every tenant-visible row carries org_id. Children reference parents
-- through composite (org_id, id) keys, so a cross-organisation reference is
-- impossible by constraint, not only by query discipline.
--
-- Lock order (every transaction acquires only the locks it needs, in this order):
--   1 jobs row (fence)  2 exposure advisory lock  3 catalogs row (share)
--   4 objects rows (sorted by id)  5 catalog_tombstones  6 catalog_maintenance
--   7 catalog_heads (always last)

CREATE TABLE installation (
    singleton boolean PRIMARY KEY DEFAULT true CHECK (singleton),
    installation_id uuid NOT NULL,
    restored_from uuid,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE orgs (
    id uuid PRIMARY KEY,
    name text NOT NULL UNIQUE,
    created_at timestamptz NOT NULL DEFAULT now()
);

-- Identity -------------------------------------------------------------------

CREATE TABLE principals (
    org_id uuid NOT NULL REFERENCES orgs(id),
    id uuid NOT NULL UNIQUE,
    kind text NOT NULL CHECK (kind IN ('user', 'service', 'system')),
    name text NOT NULL,
    disabled boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (org_id, id),
    UNIQUE (org_id, kind, name)
);

CREATE TABLE password_credentials (
    org_id uuid NOT NULL,
    principal_id uuid NOT NULL,
    hash text NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (org_id, principal_id),
    FOREIGN KEY (org_id, principal_id) REFERENCES principals(org_id, id)
);

CREATE TABLE role_bindings (
    org_id uuid NOT NULL,
    principal_id uuid NOT NULL,
    role text NOT NULL CHECK (role IN ('viewer', 'operator', 'analyst', 'approver', 'admin')),
    scope_kind text NOT NULL CHECK (scope_kind IN ('org', 'system', 'deployment', 'catalog', 'source')),
    scope_id text NOT NULL DEFAULT '',
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (org_id, principal_id, role, scope_kind, scope_id),
    FOREIGN KEY (org_id, principal_id) REFERENCES principals(org_id, id)
);

CREATE TABLE sessions (
    org_id uuid NOT NULL,
    id uuid NOT NULL UNIQUE,
    principal_id uuid NOT NULL,
    secret_hash bytea NOT NULL,
    csrf_hash bytea NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    last_seen_at timestamptz NOT NULL DEFAULT now(),
    absolute_expires_at timestamptz NOT NULL,
    revoked_at timestamptz,
    PRIMARY KEY (org_id, id),
    FOREIGN KEY (org_id, principal_id) REFERENCES principals(org_id, id)
);

CREATE TABLE api_tokens (
    org_id uuid NOT NULL,
    id uuid NOT NULL UNIQUE,
    principal_id uuid NOT NULL,
    secret_hash bytea NOT NULL,
    scopes text[] NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz,
    revoked_at timestamptz,
    last_used_at timestamptz,
    PRIMARY KEY (org_id, id),
    FOREIGN KEY (org_id, principal_id) REFERENCES principals(org_id, id)
);

CREATE TABLE audit_log (
    org_id uuid NOT NULL REFERENCES orgs(id),
    seq bigint NOT NULL,
    prev_hash bytea NOT NULL,
    hash bytea NOT NULL,
    at timestamptz NOT NULL DEFAULT clock_timestamp(),
    actor text NOT NULL,
    action text NOT NULL,
    target text NOT NULL,
    payload jsonb NOT NULL DEFAULT '{}',
    PRIMARY KEY (org_id, seq)
);

CREATE TABLE audit_anchors (
    org_id uuid NOT NULL REFERENCES orgs(id),
    seq bigint NOT NULL,
    hash bytea NOT NULL,
    sink text NOT NULL,
    exported_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (org_id, seq, sink)
);

CREATE TABLE key_records (
    org_id uuid NOT NULL REFERENCES orgs(id),
    key_id uuid NOT NULL UNIQUE,
    purpose text NOT NULL,
    state text NOT NULL CHECK (state IN ('active', 'retired', 'destroyed_live')),
    created_at timestamptz NOT NULL DEFAULT now(),
    destroyed_at timestamptz,
    PRIMARY KEY (org_id, key_id)
);

CREATE TABLE egress_allowlist (
    org_id uuid NOT NULL REFERENCES orgs(id),
    id uuid NOT NULL,
    scheme text NOT NULL CHECK (scheme IN ('https', 'http', 'smtp', 'smtps')),
    host text NOT NULL,
    port integer NOT NULL CHECK (port BETWEEN 1 AND 65535),
    cidr cidr,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (org_id, id)
);

-- Execution ------------------------------------------------------------------

CREATE TABLE jobs (
    org_id uuid NOT NULL REFERENCES orgs(id),
    id uuid NOT NULL UNIQUE,
    kind text NOT NULL,
    lane text NOT NULL CHECK (lane IN ('essential', 'investigation', 'maintenance')),
    job_class text NOT NULL CHECK (job_class IN ('warm', 'isolated', 'inline')),
    priority integer NOT NULL DEFAULT 0,
    idempotency_key text NOT NULL,
    state text NOT NULL CHECK (state IN ('queued', 'running', 'succeeded', 'failed', 'cancelled', 'dead')),
    fence bigint NOT NULL DEFAULT 0,
    attempts integer NOT NULL DEFAULT 0,
    max_attempts integer NOT NULL DEFAULT 3 CHECK (max_attempts >= 1),
    lease_owner text,
    lease_expires_at timestamptz,
    not_before timestamptz NOT NULL DEFAULT now(),
    cancel_requested boolean NOT NULL DEFAULT false,
    resources jsonb NOT NULL DEFAULT '{}',
    payload jsonb NOT NULL DEFAULT '{}',
    result jsonb,
    error jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    started_at timestamptz,
    finished_at timestamptz,
    PRIMARY KEY (org_id, id),
    UNIQUE (org_id, idempotency_key)
);
CREATE INDEX jobs_claim ON jobs (lane, priority DESC, created_at) WHERE state = 'queued';
CREATE INDEX jobs_running_lease ON jobs (lease_expires_at) WHERE state = 'running';

CREATE TABLE job_events (
    seq bigserial PRIMARY KEY,
    org_id uuid NOT NULL,
    job_id uuid NOT NULL,
    fence bigint NOT NULL,
    event text NOT NULL,
    detail jsonb NOT NULL DEFAULT '{}',
    at timestamptz NOT NULL DEFAULT clock_timestamp(),
    FOREIGN KEY (org_id, job_id) REFERENCES jobs(org_id, id)
);

CREATE TABLE worker_hosts (
    id uuid PRIMARY KEY,
    name text NOT NULL,
    capacity jsonb NOT NULL,
    started_at timestamptz NOT NULL DEFAULT now(),
    heartbeat_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE controller_leadership (
    singleton boolean PRIMARY KEY DEFAULT true CHECK (singleton),
    holder text NOT NULL,
    epoch bigint NOT NULL,
    expires_at timestamptz NOT NULL
);

-- Evidence -------------------------------------------------------------------

CREATE TABLE catalogs (
    org_id uuid NOT NULL REFERENCES orgs(id),
    id uuid NOT NULL UNIQUE,
    name text NOT NULL,
    state text NOT NULL CHECK (state IN ('migrating', 'active', 'retired')),
    -- Preserved analytical identity (the v2 instance_id for migrated catalogs).
    analytical_instance_id text NOT NULL,
    branch_id text NOT NULL,
    continuity_state text NOT NULL,
    continuity_token text,
    config jsonb NOT NULL DEFAULT '{}',
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (org_id, id),
    UNIQUE (org_id, name)
);

CREATE TABLE catalog_heads (
    org_id uuid NOT NULL,
    catalog_id uuid PRIMARY KEY,
    head bigint NOT NULL DEFAULT 0,
    FOREIGN KEY (org_id, catalog_id) REFERENCES catalogs(org_id, id)
);

CREATE TABLE catalog_tombstones (
    org_id uuid NOT NULL,
    catalog_id uuid PRIMARY KEY,
    epoch bigint NOT NULL DEFAULT 0,
    FOREIGN KEY (org_id, catalog_id) REFERENCES catalogs(org_id, id)
);

CREATE TABLE catalog_maintenance (
    org_id uuid NOT NULL,
    catalog_id uuid PRIMARY KEY,
    epoch bigint NOT NULL DEFAULT 0,
    FOREIGN KEY (org_id, catalog_id) REFERENCES catalogs(org_id, id)
);

CREATE TABLE objects (
    org_id uuid NOT NULL,
    id uuid NOT NULL UNIQUE,
    catalog_id uuid NOT NULL,
    sha256 bytea NOT NULL CHECK (length(sha256) = 32),
    generation integer NOT NULL CHECK (generation >= 0),
    physical_key text NOT NULL UNIQUE,
    codec text NOT NULL,
    bytes bigint NOT NULL CHECK (bytes >= 0),
    records bigint NOT NULL DEFAULT 0,
    key_id uuid,
    retained_for_recovery boolean NOT NULL DEFAULT false,
    state text NOT NULL CHECK (state IN ('pending', 'active', 'tombstoned', 'reclaiming', 'reclaimed', 'corrupt')),
    job_id uuid,
    fence bigint,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    activated_at timestamptz,
    tombstoned_at timestamptz,
    tombstone_mepoch bigint,
    PRIMARY KEY (org_id, id),
    UNIQUE (org_id, sha256, generation),
    FOREIGN KEY (org_id, catalog_id) REFERENCES catalogs(org_id, id),
    FOREIGN KEY (org_id, key_id) REFERENCES key_records(org_id, key_id),
    CHECK (state <> 'tombstoned' OR (tombstoned_at IS NOT NULL AND tombstone_mepoch IS NOT NULL))
);
CREATE INDEX objects_active_sha ON objects (org_id, sha256) WHERE state = 'active';
CREATE INDEX objects_gc ON objects (state) WHERE state IN ('pending', 'tombstoned', 'reclaiming');

CREATE TABLE publications (
    org_id uuid NOT NULL,
    catalog_id uuid NOT NULL,
    id uuid NOT NULL UNIQUE,
    request_id text NOT NULL,
    request_digest text NOT NULL,
    kind text NOT NULL,
    -- Assigned last, under the catalog_heads row lock: K order == commit order.
    sequence bigint,
    job_id uuid,
    fence bigint,
    receipt jsonb,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    committed_at timestamptz,
    PRIMARY KEY (org_id, id),
    UNIQUE (catalog_id, request_id),
    UNIQUE (catalog_id, sequence),
    FOREIGN KEY (org_id, catalog_id) REFERENCES catalogs(org_id, id)
);

-- Global fact identity. Hash-partitioned by key: the key fixes the partition,
-- so per-partition unique indexes are globally unique. Timestamps are
-- non-identity attributes and can never move a logical fact.
CREATE TABLE fact_index (
    org_id uuid NOT NULL,
    catalog_id uuid NOT NULL,
    kind text NOT NULL,
    key bytea NOT NULL CHECK (length(key) = 32),
    revision text NOT NULL,
    fact_digest bytea NOT NULL CHECK (length(fact_digest) = 32),
    predecessor bytea,
    object_id uuid NOT NULL,
    locator_kind text NOT NULL CHECK (locator_kind IN ('byte_range', 'row', 'object')),
    loc_a bigint NOT NULL,
    loc_b bigint NOT NULL,
    publication_id uuid NOT NULL,
    opportunity_key bytea,
    target_key bytea,
    entity_hash bytea,
    event_tick numeric,
    available_tick numeric,
    compaction_generation integer NOT NULL DEFAULT 0,
    FOREIGN KEY (org_id, catalog_id) REFERENCES catalogs(org_id, id),
    FOREIGN KEY (org_id, object_id) REFERENCES objects(org_id, id),
    FOREIGN KEY (org_id, publication_id) REFERENCES publications(org_id, id)
) PARTITION BY HASH (key);

DO $$
BEGIN
    FOR i IN 0..31 LOOP
        EXECUTE format('CREATE TABLE fact_index_p%s PARTITION OF fact_index FOR VALUES WITH (MODULUS 32, REMAINDER %s)', i, i);
    END LOOP;
END $$;

CREATE UNIQUE INDEX fact_identity ON fact_index (catalog_id, kind, key, revision);
CREATE UNIQUE INDEX fact_no_fork ON fact_index (catalog_id, kind, key, predecessor) WHERE predecessor IS NOT NULL;
CREATE INDEX fact_by_digest ON fact_index (fact_digest);
CREATE INDEX fact_by_object ON fact_index (object_id);
CREATE INDEX fact_by_publication ON fact_index (publication_id);
CREATE INDEX fact_by_opportunity ON fact_index (catalog_id, opportunity_key) WHERE opportunity_key IS NOT NULL;
CREATE INDEX fact_by_target ON fact_index (catalog_id, target_key) WHERE target_key IS NOT NULL;
CREATE INDEX fact_by_entity ON fact_index (catalog_id, entity_hash) WHERE entity_hash IS NOT NULL;
CREATE INDEX fact_by_event ON fact_index (catalog_id, kind, event_tick) WHERE event_tick IS NOT NULL;

CREATE TABLE fact_occurrences (
    org_id uuid NOT NULL,
    catalog_id uuid NOT NULL,
    publication_id uuid NOT NULL,
    kind text NOT NULL,
    key bytea NOT NULL,
    revision text NOT NULL,
    PRIMARY KEY (publication_id, kind, key, revision),
    FOREIGN KEY (org_id, publication_id) REFERENCES publications(org_id, id)
);
CREATE INDEX occurrences_by_fact ON fact_occurrences (catalog_id, kind, key, revision);

CREATE TABLE fact_tombstones (
    org_id uuid NOT NULL,
    catalog_id uuid NOT NULL,
    kind text NOT NULL,
    key bytea NOT NULL,
    revision text NOT NULL,
    epoch bigint NOT NULL,
    publication_id uuid NOT NULL,
    PRIMARY KEY (catalog_id, kind, key, revision),
    FOREIGN KEY (org_id, publication_id) REFERENCES publications(org_id, id)
);
CREATE INDEX tombstones_by_epoch ON fact_tombstones (catalog_id, epoch);

-- A reader registers (and commits) a pin before resolving locators. The
-- maintenance-epoch floor protects every object the reader can still hold a
-- locator to; the tombstone epoch serializes deletion against publication.
CREATE TABLE read_pins (
    org_id uuid NOT NULL,
    id uuid NOT NULL UNIQUE,
    catalog_id uuid NOT NULL,
    job_id uuid,
    fence bigint,
    holder text,
    expires_at timestamptz,
    k bigint NOT NULL,
    tombstone_epoch bigint NOT NULL,
    maintenance_epoch bigint NOT NULL,
    started_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    released_at timestamptz,
    PRIMARY KEY (org_id, id),
    FOREIGN KEY (org_id, catalog_id) REFERENCES catalogs(org_id, id),
    CHECK ((job_id IS NOT NULL AND fence IS NOT NULL) OR (holder IS NOT NULL AND expires_at IS NOT NULL))
);
CREATE INDEX read_pins_live ON read_pins (catalog_id) WHERE released_at IS NULL;

CREATE TABLE gc_holds (
    id uuid PRIMARY KEY,
    reason text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    released_at timestamptz
);

-- Legacy catalog v2 migration state machine (authoritative here; mirrored in a
-- marker file inside the frozen v2 root).
CREATE TABLE legacy_migrations (
    org_id uuid NOT NULL,
    id uuid NOT NULL UNIQUE,
    catalog_id uuid NOT NULL,
    legacy_root text NOT NULL,
    legacy_instance_id text NOT NULL,
    state text NOT NULL CHECK (state IN ('planned', 'frozen', 'copying', 'validating', 'cutover_committed', 'abandoned')),
    original_user_version integer,
    inventory jsonb,
    inventory_digest text,
    last_migrated_k bigint NOT NULL DEFAULT 0,
    validation jsonb,
    post_cutover_backup jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (org_id, id),
    FOREIGN KEY (org_id, catalog_id) REFERENCES catalogs(org_id, id)
);
CREATE UNIQUE INDEX legacy_migration_live ON legacy_migrations (legacy_instance_id)
    WHERE state NOT IN ('abandoned');
