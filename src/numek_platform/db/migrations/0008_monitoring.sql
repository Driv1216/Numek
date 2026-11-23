-- ConfidenceGuard CG7 monitoring (S5): versioned definitions, frozen references, window evaluations,
-- sequential detectors (SM1/SM2), signals and the estimator accountability ledger.
--
-- Every result row names the evidence-use reservation it was read under (governance before access) and
-- the immutable packet object that holds its content; rows are never rewritten except detector state,
-- which advances only by contiguous, unique segments (H.4: never applied twice, never skipped).

CREATE TABLE ops_monitoring_definitions (
    org_id uuid NOT NULL,
    deployment_id text NOT NULL,
    version integer NOT NULL CHECK (version >= 1),
    state text NOT NULL CHECK (state IN ('inspected', 'confirmed', 'superseded')),
    spec jsonb NOT NULL,
    spec_digest text NOT NULL,
    inspection jsonb NOT NULL,
    inspection_digest text NOT NULL,
    reference_id uuid,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    confirmed_at timestamptz,
    confirmed_by text,
    superseded_at timestamptz,
    PRIMARY KEY (org_id, deployment_id, version),
    FOREIGN KEY (org_id, deployment_id) REFERENCES ops_deployments(org_id, id)
);
CREATE UNIQUE INDEX ops_definitions_confirmed ON ops_monitoring_definitions (org_id, deployment_id) WHERE state = 'confirmed';

CREATE TABLE ops_references (
    org_id uuid NOT NULL,
    id uuid NOT NULL,
    deployment_id text NOT NULL,
    rule jsonb NOT NULL,                     -- the predeclared rule: period, statistics, design, alpha_ref
    rule_digest text NOT NULL,
    catalog_sequence bigint NOT NULL,
    as_of text NOT NULL,
    packet_object uuid NOT NULL,             -- immutable JSON packet (rates, finite bounds, within-group risks)
    packet_digest text NOT NULL,
    relation_object uuid,                    -- immutable Parquet relation of the selected reference rows (drift)
    evidence_use_id text NOT NULL,           -- purpose 'reference'
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (org_id, id),
    UNIQUE (org_id, deployment_id, rule_digest, catalog_sequence),
    FOREIGN KEY (org_id, deployment_id) REFERENCES ops_deployments(org_id, id),
    FOREIGN KEY (org_id, packet_object) REFERENCES objects(org_id, id),
    FOREIGN KEY (org_id, relation_object) REFERENCES objects(org_id, id)
);

CREATE TABLE ops_window_evaluations (
    org_id uuid NOT NULL,
    id uuid NOT NULL,
    deployment_id text NOT NULL,
    definition_version integer NOT NULL,
    window_index bigint NOT NULL,
    revision integer NOT NULL CHECK (revision >= 1),     -- late publications create a new revision (G.1)
    phase text NOT NULL CHECK (phase IN ('close', 'maturity')),
    start_tick numeric NOT NULL,
    end_tick numeric NOT NULL,
    closure text NOT NULL,
    catalog_sequence bigint NOT NULL,
    as_of text NOT NULL,
    selection_digest text NOT NULL,
    units integer NOT NULL,
    packet_object uuid NOT NULL,
    packet_digest text NOT NULL,
    evidence_use_id text NOT NULL,           -- purpose 'monitoring_outcome'
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (org_id, id),
    UNIQUE (org_id, deployment_id, definition_version, window_index, phase, revision),
    FOREIGN KEY (org_id, deployment_id, definition_version) REFERENCES ops_monitoring_definitions(org_id, deployment_id, version),
    FOREIGN KEY (org_id, packet_object) REFERENCES objects(org_id, id)
);

CREATE TABLE ops_detectors (
    org_id uuid NOT NULL,
    deployment_id text NOT NULL,
    definition_version integer NOT NULL,
    detector_id text NOT NULL,
    kind text NOT NULL CHECK (kind IN ('sm1', 'sm2')),
    phase text NOT NULL CHECK (phase IN ('close', 'maturity')),
    standing text NOT NULL CHECK (standing IN ('formal', 'descriptive', 'insufficient_power')),
    plan jsonb NOT NULL,
    state jsonb NOT NULL,                    -- exact kernel checkpoint
    state_version bigint NOT NULL DEFAULT 0,
    cursor_window bigint,                    -- last applied window index (contiguity)
    units bigint NOT NULL DEFAULT 0,
    alarms bigint NOT NULL DEFAULT 0,
    late_excluded bigint NOT NULL DEFAULT 0,
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (org_id, deployment_id, definition_version, detector_id),
    FOREIGN KEY (org_id, deployment_id, definition_version) REFERENCES ops_monitoring_definitions(org_id, deployment_id, version)
);

CREATE TABLE ops_detector_segments (
    org_id uuid NOT NULL,
    deployment_id text NOT NULL,
    definition_version integer NOT NULL,
    detector_id text NOT NULL,
    window_index bigint NOT NULL,
    evaluation_id uuid NOT NULL,
    state_version bigint NOT NULL,           -- version produced by this segment
    first_unit bigint NOT NULL,              -- detector unit index of this segment's first unit (1-based)
    units integer NOT NULL,
    excluded jsonb NOT NULL DEFAULT '{}',    -- counts by reason (late, invalid outcome, thinned, reserve-withheld)
    alarms jsonb NOT NULL DEFAULT '[]',
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (org_id, deployment_id, definition_version, detector_id, window_index),
    FOREIGN KEY (org_id, deployment_id, definition_version, detector_id)
        REFERENCES ops_detectors(org_id, deployment_id, definition_version, detector_id),
    FOREIGN KEY (org_id, evaluation_id) REFERENCES ops_window_evaluations(org_id, id)
);

-- Units already admitted to a detector (entity_first thinning is per statistic; late exclusion).
CREATE TABLE ops_detector_units (
    org_id uuid NOT NULL,
    deployment_id text NOT NULL,
    definition_version integer NOT NULL,
    detector_id text NOT NULL,
    kind text NOT NULL CHECK (kind IN ('entity', 'event')),
    hash bytea NOT NULL,
    window_index bigint NOT NULL,
    PRIMARY KEY (org_id, deployment_id, definition_version, detector_id, kind, hash),
    FOREIGN KEY (org_id, deployment_id, definition_version, detector_id)
        REFERENCES ops_detectors(org_id, deployment_id, definition_version, detector_id)
);

CREATE TABLE ops_signals (
    org_id uuid NOT NULL,
    id uuid NOT NULL,
    deployment_id text NOT NULL,
    definition_version integer NOT NULL,
    source text NOT NULL CHECK (source IN ('detector', 'recovery', 'rule', 'health')),
    source_id text NOT NULL,
    window_index bigint,
    standing text NOT NULL CHECK (standing IN ('D', 'F', 'P', 'E')),
    severity text NOT NULL CHECK (severity IN ('critical', 'high', 'medium', 'low', 'info')),
    payload jsonb NOT NULL,
    dedupe_key text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (org_id, id),
    UNIQUE (org_id, dedupe_key)
);
CREATE INDEX ops_signals_by_deployment ON ops_signals (org_id, deployment_id, created_at);

CREATE TABLE ops_estimates (                 -- G.5 matched-population accountability ledger
    org_id uuid NOT NULL,
    id uuid NOT NULL,
    deployment_id text NOT NULL,
    definition_version integer NOT NULL,
    estimator text NOT NULL,
    window_index bigint NOT NULL,
    evaluation_id uuid NOT NULL,
    population_digest text NOT NULL,         -- P_W (event hashes)
    population bigint NOT NULL,
    value double precision,
    record jsonb NOT NULL,                   -- formula, assumptions, artifacts, K (immutable original record)
    matched jsonb,                           -- matched estimate on O, realized value and bound, coverage, exclusions
    matched_evaluation_id uuid,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    matched_at timestamptz,
    PRIMARY KEY (org_id, id),
    UNIQUE (org_id, deployment_id, definition_version, estimator, window_index),
    FOREIGN KEY (org_id, evaluation_id) REFERENCES ops_window_evaluations(org_id, id)
);

-- Monitoring health counts untimed opportunities (they belong to no window) without scanning history.
CREATE INDEX fact_untimed_opportunities ON fact_index (catalog_id, namespace) WHERE kind = 'opportunity' AND event_tick IS NULL;
