"""PostgreSQL access.

Connections are autocommit; every unit of work opens an explicit transaction
with :meth:`Database.transaction`. Isolation is set per transaction, never per
connection, so a pooled connection cannot leak a stronger level into the next
caller.
"""
from contextlib import contextmanager

import psycopg
from psycopg.rows import dict_row

from .. import PLATFORM_SCHEMA
from ..errors import PlatformError

ISOLATION = {
    'read_committed': 'READ COMMITTED',
    'repeatable_read': 'REPEATABLE READ',
    'serializable': 'SERIALIZABLE',
}


class Database:
    def __init__(self, dsn, *, application_name='numek', connect_timeout=10):
        if not isinstance(dsn, str) or not dsn:
            raise PlatformError('A database connection string is required.', 'platform_unavailable')
        self.dsn = dsn
        self.application_name = application_name
        self.connect_timeout = connect_timeout

    def connect(self):
        try:
            conn = psycopg.connect(
                self.dsn, autocommit=True, row_factory=dict_row,
                application_name=self.application_name, connect_timeout=self.connect_timeout,
                options=f'-c search_path={PLATFORM_SCHEMA},public')
        except psycopg.OperationalError as exc:
            raise PlatformError('The platform database is unavailable.', 'platform_unavailable', retryable=True) from exc
        return conn

    @contextmanager
    def transaction(self, isolation='read_committed', *, read_only=False, conn=None):
        """Yield a connection inside one transaction; commit on success."""
        owned = conn is None
        conn = conn or self.connect()
        try:
            with conn.transaction():
                mode = ISOLATION[isolation] + (' READ ONLY' if read_only else '')
                conn.execute(f'SET TRANSACTION ISOLATION LEVEL {mode}')
                yield conn
        finally:
            if owned:
                conn.close()


@contextmanager
def point_lookups(conn):
    """Plan the enclosed statements as nested loops of index probes (no hash or merge joins).

    For joins from a batch-sized set (a capture's identities, a publication's staged facts) into
    ``fact_index``: each probe is pruned at run time to the one hash partition of its route, so the cost
    follows the batch, not the history. The planner otherwise often scans the whole index (its cost grows
    with every publication). Must run inside a transaction; the previous settings are restored on exit,
    so the rest of that transaction plans as usual. These settings do not fix which side of a join drives it:
    a statement whose plan must start from the set (for example under an ORDER BY on another table) uses a
    LATERAL probe instead, as ``evidence.reader.resolve`` does for routes.
    """
    if conn.info.transaction_status == psycopg.pq.TransactionStatus.IDLE:
        raise PlatformError('point_lookups requires an open transaction.', 'invalid_access')
    previous = conn.execute("SELECT current_setting('enable_hashjoin') AS h, current_setting('enable_mergejoin') AS m").fetchone()
    conn.execute("SELECT set_config('enable_hashjoin', 'off', true), set_config('enable_mergejoin', 'off', true)")
    try:
        yield conn
    finally:
        if conn.info.transaction_status == psycopg.pq.TransactionStatus.INTRANS:
            conn.execute("SELECT set_config('enable_hashjoin', %s, true), set_config('enable_mergejoin', %s, true)",
                         (previous['h'], previous['m']))


def one(conn, sql, params=()):
    return conn.execute(sql, params).fetchone()


def all_rows(conn, sql, params=()):
    return conn.execute(sql, params).fetchall()
