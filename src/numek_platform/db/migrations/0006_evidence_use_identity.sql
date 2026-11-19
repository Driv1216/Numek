-- Evidence-use ids are per catalog (S3b).
--
-- ConfidenceGuard use ids are the v2 ``digest([kind, population, family,
-- request])[:32]``, unique within one catalog's ledger. Every ConfidenceGuard
-- workspace of an installation shares one organization, so two workspaces that
-- record the same request must not collide. The key keeps ``org_id`` (R2.7
-- composite organization keys) and adds the catalog.

ALTER TABLE evidence_uses DROP CONSTRAINT evidence_uses_pkey;
ALTER TABLE evidence_uses ADD PRIMARY KEY (org_id, catalog_id, id);
