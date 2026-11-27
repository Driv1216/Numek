-- Review correction: soft lockout of password sign-in (OWASP ASVS L1 anti-automation).
-- Each failed sign-in for a name is recorded in its own transaction. While a name has LOGIN_FAILURE_LIMIT failures
-- inside LOGIN_FAILURE_WINDOW, further attempts for it are refused (HTTP 429) without checking the password, so a
-- guessing run is bounded by the limit per window rather than by argon2id cost alone. Rows older than the window
-- carry no meaning and are pruned when failures are recorded.
CREATE TABLE login_failures (
    org_id uuid NOT NULL REFERENCES orgs(id),
    name text NOT NULL,
    failed_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE INDEX login_failures_by_name ON login_failures (org_id, name, failed_at);
