-- S10: the late-revision check (operations monitoring, plan H.6) remembers the last catalog sequence it scanned,
-- per deployment, definition version and phase. Each cycle then scans only facts published after it, so its cost
-- follows new publications instead of growing with the whole history (the M.5 incrementality gate).
CREATE TABLE ops_revision_cursors (
    org_id uuid NOT NULL,
    deployment_id text NOT NULL,
    definition_version integer NOT NULL,
    phase text NOT NULL CHECK (phase IN ('close', 'maturity')),
    checked_sequence bigint NOT NULL CHECK (checked_sequence >= 0),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (org_id, deployment_id, definition_version, phase),
    FOREIGN KEY (org_id, deployment_id) REFERENCES ops_deployments(org_id, id)
);
