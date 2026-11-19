-- ConfidenceGuard on the platform (S3).
--
-- * Protection is a per-fact property set by the producer at publication
--   (outcomes, raw projected rows, and predictions carrying an inline outcome
--   assertion), not something inferred from the kind at read time.
-- * namespace scopes governance membership to the analysed history.
-- * cg_* tables hold the ConfidenceGuard catalog relations that v2 kept in
--   SQLite (variants, assessments, dependencies, vector locations, deletions,
--   settings). Object ids are the v2 32-hex ids read as UUIDs, so every stored
--   reference (depends_on_objects, descriptors, bindings) keeps its meaning.

ALTER TABLE fact_index ADD COLUMN protected boolean NOT NULL DEFAULT false;
ALTER TABLE fact_index ADD COLUMN namespace text;
CREATE INDEX fact_by_namespace ON fact_index (catalog_id, namespace, kind) WHERE namespace IS NOT NULL;
UPDATE fact_index SET protected = true WHERE kind IN ('outcome', 'raw');

CREATE TABLE cg_settings (
    catalog_id uuid NOT NULL REFERENCES catalogs(id),
    key text NOT NULL,
    value jsonb NOT NULL,
    PRIMARY KEY (catalog_id, key)
);

CREATE TABLE cg_variants (
    catalog_id uuid NOT NULL REFERENCES catalogs(id),
    id text NOT NULL,
    metadata jsonb NOT NULL,
    publication_id uuid NOT NULL REFERENCES publications(id),
    PRIMARY KEY (catalog_id, id)
);

CREATE TABLE cg_assessments (
    catalog_id uuid NOT NULL REFERENCES catalogs(id),
    id text NOT NULL,
    object_id uuid NOT NULL REFERENCES objects(id),
    publication_id uuid NOT NULL REFERENCES publications(id),
    digest text NOT NULL,
    predecessor text,
    state text NOT NULL CHECK (state IN ('active', 'deleted')),
    PRIMARY KEY (catalog_id, id)
);

CREATE TABLE cg_artifact_dependencies (
    catalog_id uuid NOT NULL REFERENCES catalogs(id),
    object_id uuid NOT NULL REFERENCES objects(id),
    depends_on uuid NOT NULL REFERENCES objects(id),
    PRIMARY KEY (object_id, depends_on)
);
CREATE INDEX cg_dependencies_parent ON cg_artifact_dependencies (depends_on);

CREATE TABLE cg_vector_locations (
    catalog_id uuid NOT NULL REFERENCES catalogs(id),
    digest text NOT NULL,
    object_id uuid NOT NULL REFERENCES objects(id),
    row_index bigint NOT NULL,
    dtype text NOT NULL,
    dimensions integer NOT NULL,
    PRIMARY KEY (catalog_id, digest)
);

CREATE TABLE cg_deletions (
    catalog_id uuid NOT NULL REFERENCES catalogs(id),
    id text NOT NULL,
    plan jsonb NOT NULL,
    state text NOT NULL CHECK (state IN ('pending', 'completed')),
    PRIMARY KEY (catalog_id, id)
);
