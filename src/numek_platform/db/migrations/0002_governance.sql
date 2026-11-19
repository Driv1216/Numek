-- NUMEK platform governance (S2): evidence use before access, exposure
-- registry, entity registry and namespace-level sealed reserves.
--
-- Governance identity space is the ConfidenceGuard v2 one:
--   event_hash  = digest([namespace, event])
--   entity_hash = digest([namespace, entity or event])     ("unit")
-- so migrated v2 uses and platform-native uses overlap-check against each other.
--
-- Exposure history is never deleted. Purging facts does not erase what was
-- exposed, so fact deletion alone does not make continuity incomplete.
--
-- Lock order extension: governance rows (evidence_uses, exposure_*, entity_*,
-- reserves) are written only while holding the per-catalog exposure advisory
-- lock (step 2), and are locked after objects (step 4) and before
-- catalog_tombstones (step 5):
--   job -> exposure -> catalog -> objects -> governance rows -> tombstones
--       -> maintenance -> heads

ALTER TABLE fact_index ADD COLUMN event_hash bytea;
CREATE INDEX fact_by_event_hash ON fact_index (catalog_id, event_hash) WHERE event_hash IS NOT NULL;

ALTER TABLE catalogs ADD COLUMN exposure_tracking boolean NOT NULL DEFAULT true;

CREATE TABLE evidence_uses (
    org_id uuid NOT NULL,
    catalog_id uuid NOT NULL,
    id text NOT NULL CHECK (id ~ '^[0-9a-f]{32}$'),
    request_id text NOT NULL,
    request_digest text NOT NULL,
    kind text NOT NULL CHECK (kind IN ('discovery_selection', 'confirmation', 'outcome_disclosure',
                                       'numerical_recomputation', 'covariate_inspection')),
    purpose text NOT NULL,
    state text NOT NULL CHECK (state IN ('reserved', 'consumed')),
    population_digest text NOT NULL,
    family_digest text,
    membership_digest text NOT NULL,
    membership_object uuid,
    event_count bigint NOT NULL,
    unit_count bigint NOT NULL,
    withheld_reserve_units bigint NOT NULL DEFAULT 0,
    reserve_consumed_units bigint NOT NULL DEFAULT 0,
    read_k bigint,
    as_of text,
    selection_digest text,
    study_id text,
    alpha numeric,
    total_alpha numeric,
    branch_id text NOT NULL,
    continuity text NOT NULL,
    continuity_token text,
    metadata jsonb NOT NULL DEFAULT '{}',
    job_id uuid,
    fence bigint,
    legacy boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    consumed_at timestamptz,
    PRIMARY KEY (org_id, id),
    UNIQUE (catalog_id, id),
    UNIQUE (catalog_id, request_id),
    FOREIGN KEY (org_id, catalog_id) REFERENCES catalogs(org_id, id),
    FOREIGN KEY (org_id, membership_object) REFERENCES objects(org_id, id)
);
CREATE INDEX evidence_uses_family ON evidence_uses (catalog_id, kind, family_digest, population_digest);

CREATE TABLE study_allocations (
    catalog_id uuid NOT NULL,
    study_id text NOT NULL,
    use_id text NOT NULL,
    alpha numeric NOT NULL CHECK (alpha > 0),
    total_alpha numeric NOT NULL CHECK (total_alpha > 0),
    PRIMARY KEY (catalog_id, use_id),
    FOREIGN KEY (catalog_id, use_id) REFERENCES evidence_uses(catalog_id, id)
);
CREATE INDEX study_allocations_study ON study_allocations (catalog_id, study_id);

-- One row per identity ever exposed (any purpose). Flags say how.
CREATE TABLE exposure_registry (
    org_id uuid NOT NULL,
    catalog_id uuid NOT NULL,
    member_kind text NOT NULL CHECK (member_kind IN ('event', 'unit')),
    hash bytea NOT NULL CHECK (length(hash) = 32),
    outcome_exposed boolean NOT NULL DEFAULT false,      -- by a non-confirmation outcome-bearing use
    development_use boolean NOT NULL DEFAULT false,      -- fit / selection / discovery roles
    covariate_inspected boolean NOT NULL DEFAULT false,
    first_use_id text NOT NULL,
    last_use_id text NOT NULL,
    PRIMARY KEY (catalog_id, member_kind, hash),
    FOREIGN KEY (org_id, catalog_id) REFERENCES catalogs(org_id, id)
);

-- Per-use membership, kept only for confirmation and numerical uses, so the
-- v2 rule "the same family and population is not a conflict" stays exact.
CREATE TABLE confirmation_members (
    catalog_id uuid NOT NULL,
    use_id text NOT NULL,
    member_kind text NOT NULL CHECK (member_kind IN ('event', 'unit')),
    hash bytea NOT NULL,
    PRIMARY KEY (catalog_id, member_kind, hash, use_id),
    FOREIGN KEY (catalog_id, use_id) REFERENCES evidence_uses(catalog_id, id)
);

CREATE TABLE reserves (
    org_id uuid NOT NULL,
    catalog_id uuid NOT NULL,
    id uuid NOT NULL UNIQUE,
    namespace text NOT NULL,
    covariate_policy text NOT NULL CHECK (covariate_policy IN ('exclude', 'inspect')),
    state text NOT NULL CHECK (state IN ('active', 'retired')),
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (org_id, id),
    FOREIGN KEY (org_id, catalog_id) REFERENCES catalogs(org_id, id)
);
CREATE UNIQUE INDEX reserves_one_active ON reserves (catalog_id, namespace) WHERE state = 'active';

-- A version applies to entities first seen at or after effective_from_k.
-- Rotation or a fraction change adds a version; assignments never change.
CREATE TABLE reserve_versions (
    reserve_id uuid NOT NULL REFERENCES reserves(id),
    version integer NOT NULL CHECK (version >= 1),
    fraction numeric NOT NULL CHECK (fraction >= 0 AND fraction <= 0.5),
    secret_name text NOT NULL,
    effective_from_k bigint NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (reserve_id, version)
);

CREATE TABLE entity_registry (
    org_id uuid NOT NULL,
    catalog_id uuid NOT NULL,
    unit_hash bytea NOT NULL CHECK (length(unit_hash) = 32),
    namespace text NOT NULL,
    first_seen_k bigint NOT NULL,
    reserve_state text NOT NULL CHECK (reserve_state IN ('reserve', 'non_reserve', 'pre_reserve', 'released')),
    reserve_id uuid REFERENCES reserves(id),
    reserve_version integer,
    spent_by_use text,
    spent_at timestamptz,
    assigned_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (catalog_id, unit_hash),
    FOREIGN KEY (org_id, catalog_id) REFERENCES catalogs(org_id, id)
);
CREATE INDEX entity_registry_reserve ON entity_registry (catalog_id) WHERE reserve_state = 'reserve';

CREATE TABLE reserve_events (
    seq bigserial PRIMARY KEY,
    org_id uuid NOT NULL,
    reserve_id uuid NOT NULL REFERENCES reserves(id),
    event text NOT NULL CHECK (event IN ('created', 'rotated', 'fraction_changed', 'reallocated', 'released',
                                         'consumed', 'retired')),
    detail jsonb NOT NULL DEFAULT '{}',
    actor text NOT NULL,
    at timestamptz NOT NULL DEFAULT clock_timestamp()
);
