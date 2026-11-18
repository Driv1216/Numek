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


def one(conn, sql, params=()):
    return conn.execute(sql, params).fetchone()


def all_rows(conn, sql, params=()):
    return conn.execute(sql, params).fetchall()
