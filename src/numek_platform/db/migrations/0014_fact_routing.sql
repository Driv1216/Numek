-- S10: route window-linked facts to their opportunity's partition (the M.5 incrementality gate).
--
-- fact_index was hash-partitioned by key. A window reads its opportunities by key, but their predictions and
-- context by opportunity_key, which is not the partition key, so every window read scanned all partitions and its
-- cost grew with the whole history. The table is now partitioned by route:
--   prediction and context: route = opportunity_key, which is identity[0] (their opportunity's key);
--   every other kind:        route = key.
-- route is a function of the fact's identity (never of its payload), so one logical identity always lands in one
-- partition and the per-partition unique indexes, which include route, stay globally unique (plan H.2, 6.1).
-- Facts whose bytes were deleted before migration carry no opportunity_key and route by key; they are all
-- tombstoned, and publication refuses re-importing a tombstoned identity through the global fact_tombstones key.
--
-- This rewrites the table: an offline step, proportional to the facts held.

CREATE TABLE fact_index_routed (
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
    event_hash bytea,
    protected boolean NOT NULL DEFAULT false,
    namespace text,
    route bytea NOT NULL CHECK (length(route) = 32),
    CHECK (route = CASE WHEN kind IN ('prediction', 'context') AND opportunity_key IS NOT NULL THEN opportunity_key ELSE key END),
    FOREIGN KEY (org_id, catalog_id) REFERENCES catalogs(org_id, id),
    FOREIGN KEY (org_id, object_id) REFERENCES objects(org_id, id),
    FOREIGN KEY (org_id, publication_id) REFERENCES publications(org_id, id)
) PARTITION BY HASH (route);

DO $$
BEGIN
    FOR i IN 0..31 LOOP
        EXECUTE format('CREATE TABLE fact_index_routed_p%s PARTITION OF fact_index_routed FOR VALUES WITH (MODULUS 32, REMAINDER %s)', i, i);
    END LOOP;
END $$;

INSERT INTO fact_index_routed (org_id, catalog_id, kind, key, revision, fact_digest, predecessor, object_id, locator_kind,
                               loc_a, loc_b, publication_id, opportunity_key, target_key, entity_hash, event_tick,
                               available_tick, compaction_generation, event_hash, protected, namespace, route)
SELECT org_id, catalog_id, kind, key, revision, fact_digest, predecessor, object_id, locator_kind, loc_a, loc_b,
       publication_id, opportunity_key, target_key, entity_hash, event_tick, available_tick, compaction_generation,
       event_hash, protected, namespace,
       CASE WHEN kind IN ('prediction', 'context') AND opportunity_key IS NOT NULL THEN opportunity_key ELSE key END
FROM fact_index;

DROP TABLE fact_index;
ALTER TABLE fact_index_routed RENAME TO fact_index;
DO $$
BEGIN
    FOR i IN 0..31 LOOP
        EXECUTE format('ALTER TABLE fact_index_routed_p%s RENAME TO fact_index_p%s', i, i);
    END LOOP;
END $$;

CREATE UNIQUE INDEX fact_identity ON fact_index (catalog_id, kind, route, key, revision);
CREATE UNIQUE INDEX fact_no_fork ON fact_index (catalog_id, kind, route, key, predecessor) WHERE predecessor IS NOT NULL;
CREATE INDEX fact_by_digest ON fact_index (fact_digest);
CREATE INDEX fact_by_object ON fact_index (object_id);
CREATE INDEX fact_by_publication ON fact_index (publication_id);
CREATE INDEX fact_by_opportunity ON fact_index (catalog_id, opportunity_key) WHERE opportunity_key IS NOT NULL;
CREATE INDEX fact_by_target ON fact_index (catalog_id, target_key) WHERE target_key IS NOT NULL;
CREATE INDEX fact_by_entity ON fact_index (catalog_id, entity_hash) WHERE entity_hash IS NOT NULL;
CREATE INDEX fact_by_event ON fact_index (catalog_id, kind, event_tick) WHERE event_tick IS NOT NULL;
CREATE INDEX fact_by_event_hash ON fact_index (catalog_id, event_hash) WHERE event_hash IS NOT NULL;
CREATE INDEX fact_by_namespace ON fact_index (catalog_id, namespace, kind) WHERE namespace IS NOT NULL;
CREATE INDEX fact_untimed_opportunities ON fact_index (catalog_id, namespace) WHERE kind = 'opportunity' AND event_tick IS NULL;

ANALYZE fact_index;
