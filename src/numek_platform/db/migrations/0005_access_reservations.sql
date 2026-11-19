-- Access-only reservations (S3b).
--
-- Class ``access`` authorizes a governed read without recording outcome
-- exposure. ConfidenceGuard workers use it where v2 read outcomes without a
-- ledger entry; their exposure, if any, is the caller's own evidence-use record.

ALTER TABLE evidence_uses DROP CONSTRAINT evidence_uses_kind_check;
ALTER TABLE evidence_uses ADD CONSTRAINT evidence_uses_kind_check
    CHECK (kind IN ('discovery_selection', 'confirmation', 'outcome_disclosure', 'numerical_recomputation',
                    'covariate_inspection', 'access'));
