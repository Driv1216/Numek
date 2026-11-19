-- ConfidenceGuard object kinds and creating operations (S3b).
--
-- The v2 deletion closure groups objects by their ConfidenceGuard kind
-- (assessment, cg4_packet_part, cg6_artifact, ...) and by the operation that
-- wrote them. Platform objects carry neither, so ConfidenceGuard records both.

CREATE TABLE cg_objects (
    catalog_id uuid NOT NULL REFERENCES catalogs(id),
    object_id uuid PRIMARY KEY REFERENCES objects(id),
    kind text NOT NULL,
    operation_id uuid NOT NULL REFERENCES publications(id)
);
CREATE INDEX cg_objects_operation ON cg_objects (catalog_id, operation_id);
CREATE INDEX cg_objects_kind ON cg_objects (catalog_id, kind);
