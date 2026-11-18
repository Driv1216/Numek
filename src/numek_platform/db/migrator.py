"""Versioned, transactional schema migrations.

Each ``NNNN_name.sql`` file runs in its own transaction under an advisory lock
and is recorded with its SHA-256. An applied file whose bytes later change is
refused: schema history is append-only, like evidence.
"""
import hashlib
import re
import uuid
from importlib import resources

from .. import PLATFORM_SCHEMA
from ..errors import PlatformError

NAME = re.compile(r'^(\d{4})_[a-z0-9_]+\.sql$')
LOCK_KEY = 0x6E756D656B  # 'numek'


def available_migrations():
    folder = resources.files('numek_platform.db') / 'migrations'
    found = []
    for entry in folder.iterdir():
        match = NAME.match(entry.name)
        if match:
            text = entry.read_text(encoding='utf-8')
            found.append((int(match.group(1)), entry.name, text, hashlib.sha256(text.encode()).hexdigest()))
    found.sort()
    versions = [v for v, *_ in found]
    if versions != list(range(1, len(versions) + 1)):
        raise PlatformError('Migration files are not contiguous.', 'migration_inventory')
    return found


def migrate(database):
    """Apply pending migrations. Returns the list of newly applied versions."""
    applied_now = []
    with database.connect() as conn:
        with conn.transaction():
            conn.execute('SELECT pg_advisory_xact_lock(%s)', (LOCK_KEY,))
            conn.execute(f'CREATE SCHEMA IF NOT EXISTS {PLATFORM_SCHEMA}')
            conn.execute(f'''CREATE TABLE IF NOT EXISTS {PLATFORM_SCHEMA}.schema_migrations (
                version integer PRIMARY KEY, name text NOT NULL, sha256 text NOT NULL,
                applied_at timestamptz NOT NULL DEFAULT now())''')
        for version, name, text, sha in available_migrations():
            with conn.transaction():
                conn.execute('SELECT pg_advisory_xact_lock(%s)', (LOCK_KEY,))
                conn.execute(f'SET LOCAL search_path TO {PLATFORM_SCHEMA}, public')
                row = conn.execute('SELECT name, sha256 FROM schema_migrations WHERE version = %s', (version,)).fetchone()
                if row:
                    if row['sha256'] != sha or row['name'] != name:
                        raise PlatformError(f'Applied migration {version} differs from the shipped file.', 'migration_changed')
                    continue
                conn.execute(text)
                conn.execute('INSERT INTO schema_migrations(version, name, sha256) VALUES (%s, %s, %s)', (version, name, sha))
                if version == 1:
                    conn.execute('INSERT INTO installation(installation_id) VALUES (%s)', (uuid.uuid4(),))
                applied_now.append(version)
    return applied_now


def schema_version(database):
    with database.connect() as conn:
        exists = conn.execute("SELECT to_regclass(%s) AS t", (f'{PLATFORM_SCHEMA}.schema_migrations',)).fetchone()['t']
        if not exists:
            return 0
        return conn.execute('SELECT coalesce(max(version), 0) AS v FROM schema_migrations').fetchone()['v']
