"""Durable jobs with fenced leases.

Every claim increments ``fence``. An attempt may act only while its fence is
current; every consequential write locks the job row first (lock-order step
1) and checks the fence inside the same transaction. A paused or partitioned
worker whose lease was reassigned therefore cannot publish, complete or
renew: its writes match zero rows and abort.
"""
import uuid
from dataclasses import dataclass

from psycopg.types.json import Jsonb

from ..errors import FenceLost, PlatformError

LANES = ('essential', 'investigation', 'maintenance')
CLASSES = ('warm', 'isolated', 'inline')
TERMINAL = ('succeeded', 'failed', 'cancelled', 'dead')


@dataclass(frozen=True)
class JobLease:
    org_id: uuid.UUID
    job_id: uuid.UUID
    fence: int
    kind: str = ''
    owner: str = ''


def _event(conn, org_id, job_id, fence, event, detail=None):
    conn.execute('INSERT INTO job_events(org_id, job_id, fence, event, detail) VALUES (%s, %s, %s, %s, %s)',
                 (org_id, job_id, fence, event, Jsonb(detail or {})))


def enqueue(conn, scope, kind, *, idempotency_key, lane='essential', job_class='warm', payload=None,
            priority=0, resources=None, max_attempts=3, delay_seconds=0):
    """Insert a job or return the existing one with the same idempotency key."""
    if lane not in LANES or job_class not in CLASSES:
        raise ValueError((lane, job_class))
    job_id = uuid.uuid4()
    row = conn.execute(
        '''INSERT INTO jobs(org_id, id, kind, lane, job_class, priority, idempotency_key, state,
                            max_attempts, resources, payload, not_before)
           VALUES (%s, %s, %s, %s, %s, %s, %s, 'queued', %s, %s, %s, now() + make_interval(secs => %s))
           ON CONFLICT (org_id, idempotency_key) DO NOTHING
           RETURNING *''',
        (scope.org_id, job_id, kind, lane, job_class, priority, idempotency_key, max_attempts,
         Jsonb(resources or {}), Jsonb(payload or {}), delay_seconds)).fetchone()
    if row is None:
        row = conn.execute('SELECT * FROM jobs WHERE org_id = %s AND idempotency_key = %s',
                           (scope.org_id, idempotency_key)).fetchone()
        if row['kind'] != kind:
            raise PlatformError('Idempotency key is bound to a different job kind.', 'idempotency_conflict')
    else:
        _event(conn, scope.org_id, job_id, 0, 'enqueued')
    return row


def claim(conn, owner, lanes, *, lease_seconds=60, fits=None, kinds=None, candidates=8):
    """Claim one queued job (SKIP LOCKED). ``fits(resources) -> bool`` admits by budget."""
    with conn.transaction():
        params = [list(lanes)]
        kind_clause = ''
        if kinds is not None:
            kind_clause = ' AND kind = ANY(%s)'
            params.append(list(kinds))
        params.append(candidates)
        rows = conn.execute(
            f'''SELECT org_id, id, resources FROM jobs
                WHERE state = 'queued' AND lane = ANY(%s) AND not_before <= now(){kind_clause}
                ORDER BY priority DESC, created_at
                FOR UPDATE SKIP LOCKED LIMIT %s''', params).fetchall()
        for row in rows:
            if fits is None or fits(row['resources']):
                job = conn.execute(
                    '''UPDATE jobs SET state = 'running', fence = fence + 1, attempts = attempts + 1,
                           lease_owner = %s, lease_expires_at = now() + make_interval(secs => %s),
                           started_at = coalesce(started_at, now()), cancel_requested = false
                       WHERE org_id = %s AND id = %s RETURNING *''',
                    (owner, lease_seconds, row['org_id'], row['id'])).fetchone()
                _event(conn, job['org_id'], job['id'], job['fence'], 'claimed', {'owner': owner})
                return JobLease(job['org_id'], job['id'], job['fence'], job['kind'], owner), job
    return None, None


def start_inline(conn, scope, kind, *, idempotency_key, owner, payload=None, lease_seconds=3600, lane='essential'):
    """Create and immediately own a job for a synchronous caller (CLI, Python API)."""
    with conn.transaction():
        row = enqueue(conn, scope, kind, idempotency_key=idempotency_key, lane=lane, job_class='inline', payload=payload)
        if row['state'] in TERMINAL:
            return None, row
        job = conn.execute(
            '''UPDATE jobs SET state = 'running', fence = fence + 1, attempts = attempts + 1, lease_owner = %s,
                   lease_expires_at = now() + make_interval(secs => %s), started_at = coalesce(started_at, now())
               WHERE org_id = %s AND id = %s AND state IN ('queued', 'running') RETURNING *''',
            (owner, lease_seconds, scope.org_id, row['id'])).fetchone()
        if job is None:
            raise PlatformError('The job is not available to run.', 'job_unavailable')
        _event(conn, job['org_id'], job['id'], job['fence'], 'claimed', {'owner': owner, 'inline': True})
        return JobLease(job['org_id'], job['id'], job['fence'], kind, owner), job


def assert_fence(conn, lease):
    """Lock the job row and verify this attempt still owns it (lock-order step 1)."""
    row = conn.execute('SELECT state, fence FROM jobs WHERE org_id = %s AND id = %s FOR UPDATE',
                       (lease.org_id, lease.job_id)).fetchone()
    if row is None or row['state'] != 'running' or row['fence'] != lease.fence:
        raise FenceLost()
    return row


def renew(conn, lease, lease_seconds=60):
    """Extend the lease. Returns ``cancel_requested``; raises FenceLost if superseded."""
    row = conn.execute(
        '''UPDATE jobs SET lease_expires_at = now() + make_interval(secs => %s)
           WHERE org_id = %s AND id = %s AND fence = %s AND state = 'running'
           RETURNING cancel_requested''', (lease_seconds, lease.org_id, lease.job_id, lease.fence)).fetchone()
    if row is None:
        raise FenceLost()
    return row['cancel_requested']


def complete(conn, lease, result=None):
    with conn.transaction():
        row = conn.execute(
            '''UPDATE jobs SET state = 'succeeded', result = %s, finished_at = now(), lease_owner = NULL,
                   lease_expires_at = NULL
               WHERE org_id = %s AND id = %s AND fence = %s AND state = 'running' RETURNING id''',
            (Jsonb(result or {}), lease.org_id, lease.job_id, lease.fence)).fetchone()
        if row is None:
            raise FenceLost()
        _event(conn, lease.org_id, lease.job_id, lease.fence, 'succeeded')


def fail(conn, lease, error, *, retryable=False, backoff_seconds=5):
    """Record a failure. Retryable failures requeue until ``max_attempts``."""
    with conn.transaction():
        row = conn.execute(
            '''UPDATE jobs SET
                   state = CASE WHEN %s AND attempts < max_attempts THEN 'queued' ELSE 'failed' END,
                   error = %s, lease_owner = NULL, lease_expires_at = NULL,
                   not_before = now() + make_interval(secs => %s * power(2, greatest(attempts - 1, 0))),
                   finished_at = CASE WHEN %s AND attempts < max_attempts THEN NULL ELSE now() END
               WHERE org_id = %s AND id = %s AND fence = %s AND state = 'running' RETURNING state''',
            (retryable, Jsonb(error), backoff_seconds, retryable, lease.org_id, lease.job_id, lease.fence)).fetchone()
        if row is None:
            raise FenceLost()
        _event(conn, lease.org_id, lease.job_id, lease.fence, 'failed', {'retryable': retryable, 'state': row['state']})
        return row['state']


def mark_cancelled(conn, lease):
    with conn.transaction():
        row = conn.execute(
            '''UPDATE jobs SET state = 'cancelled', finished_at = now(), lease_owner = NULL, lease_expires_at = NULL
               WHERE org_id = %s AND id = %s AND fence = %s AND state = 'running' RETURNING id''',
            (lease.org_id, lease.job_id, lease.fence)).fetchone()
        if row is None:
            raise FenceLost()
        _event(conn, lease.org_id, lease.job_id, lease.fence, 'cancelled')


def request_cancel(conn, scope, job_id):
    """Queued jobs cancel immediately; running jobs are signalled through renewal."""
    with conn.transaction():
        row = conn.execute('SELECT state, fence FROM jobs WHERE org_id = %s AND id = %s FOR UPDATE',
                           (scope.org_id, job_id)).fetchone()
        if row is None:
            raise PlatformError('Unknown job.', 'unknown_job')
        if row['state'] == 'queued':
            conn.execute("UPDATE jobs SET state = 'cancelled', finished_at = now() WHERE org_id = %s AND id = %s",
                         (scope.org_id, job_id))
            _event(conn, scope.org_id, job_id, row['fence'], 'cancelled')
            return 'cancelled'
        if row['state'] == 'running':
            conn.execute('UPDATE jobs SET cancel_requested = true WHERE org_id = %s AND id = %s', (scope.org_id, job_id))
            return 'cancelling'
        return row['state']


def expire_leases(conn):
    """Supersede every expired running attempt (fence + 1). Returns affected ids.

    Called by the controller inside a transaction that asserts its leadership
    epoch, so a deposed controller cannot expire leases.
    """
    rows = conn.execute(
        '''UPDATE jobs SET fence = fence + 1,
               state = CASE WHEN attempts >= max_attempts THEN 'dead' ELSE 'queued' END,
               finished_at = CASE WHEN attempts >= max_attempts THEN now() ELSE NULL END,
               lease_owner = NULL, lease_expires_at = NULL
           WHERE state = 'running' AND job_class <> 'inline' AND lease_expires_at < now()
           RETURNING org_id, id, fence, state''').fetchall()
    for row in rows:
        _event(conn, row['org_id'], row['id'], row['fence'], 'lease_expired', {'state': row['state']})
    return rows


def expire_inline(conn):
    """Inline attempts whose owner vanished become dead (never silently rerun)."""
    rows = conn.execute(
        '''UPDATE jobs SET fence = fence + 1, state = 'dead', finished_at = now(), lease_owner = NULL,
               lease_expires_at = NULL
           WHERE state = 'running' AND job_class = 'inline' AND lease_expires_at < now()
           RETURNING org_id, id, fence''').fetchall()
    for row in rows:
        _event(conn, row['org_id'], row['id'], row['fence'], 'lease_expired', {'state': 'dead'})
    return rows


def get(conn, scope, job_id):
    row = conn.execute('SELECT * FROM jobs WHERE org_id = %s AND id = %s', (scope.org_id, job_id)).fetchone()
    if row is None:
        raise PlatformError('Unknown job.', 'unknown_job')
    return row
