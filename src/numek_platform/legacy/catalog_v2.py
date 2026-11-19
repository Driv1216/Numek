"""Catalog v2: read-only reader, freeze/unfreeze and inventory.

Freezing sets ``PRAGMA user_version = 9002``. Every released ConfidenceGuard
runtime validates ``user_version in (1, 2)`` (``history_storage.Catalog._validate``)
and therefore refuses a frozen catalog with ``catalog_version``. The lockout is
stored in the source itself, so it survives crashes and interrupted migrations.
Only this reader accepts 9002.
"""
import contextlib
import json
import os
import sqlite3
from pathlib import Path

from ..canonical import digest
from ..errors import PlatformError
from ..fsutil import write_atomic

FROZEN_VERSION = 9002
LIVE_VERSIONS = (1, 2)
MARKER = '.numek-migration.json'
SETTINGS_KEY = 'numek_migration'


@contextlib.contextmanager
def _flock(path):
    """Exclusive non-blocking lock on a v2 lock file (same semantics as the v2 writer)."""
    import fcntl
    fd = os.open(path, os.O_RDWR | os.O_CREAT | getattr(os, 'O_NOFOLLOW', 0), 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise PlatformError('The legacy workspace is busy; retry after the current operation.', 'workspace_busy') from None
        yield
    finally:
        os.close(fd)


def _readonly(root):
    path = Path(root) / 'catalog.sqlite3'
    if not path.is_file() or path.is_symlink():
        raise PlatformError('Legacy catalog not found.', 'workspace_missing')
    conn = sqlite3.connect(f'file:{path}?mode=ro', uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def user_version(root):
    with contextlib.closing(_readonly(root)) as conn:
        return conn.execute('PRAGMA user_version').fetchone()[0]


def settings(root):
    with contextlib.closing(_readonly(root)) as conn:
        return {r['key']: json.loads(r['value']) for r in conn.execute('SELECT key, value FROM settings')}


def inventory(root):
    """Deterministic description of everything a migration must preserve."""
    with contextlib.closing(_readonly(root)) as conn:
        version = conn.execute('PRAGMA user_version').fetchone()[0]
        if version not in (*LIVE_VERSIONS, FROZEN_VERSION):
            raise PlatformError('Unsupported legacy catalog version.', 'catalog_version')
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        stored = {r['key']: json.loads(r['value']) for r in conn.execute('SELECT key, value FROM settings')}
        operations = [dict(r) for r in conn.execute(
            "SELECT id, sequence, state, request_digest FROM operations WHERE state = 'committed' ORDER BY sequence")]
        objects = [dict(r) for r in conn.execute(
            'SELECT id, sha256, bytes, kind, records, state' + (', encoding' if 'artifact_dependencies' in tables else '')
            + ' FROM objects ORDER BY id')]
        fact_counts = {r[0]: r[1] for r in conn.execute('SELECT kind, count(*) FROM facts GROUP BY kind ORDER BY kind')}
        uses = [dict(r) for r in conn.execute('SELECT id, kind, population_digest, state FROM evidence_uses ORDER BY id')] \
            if 'evidence_uses' in tables else []
        deletions = [dict(r) for r in conn.execute('SELECT id, state, plan FROM deletions ORDER BY id')]
    # Every K is either one committed operation or one deletion (a v2 deletion advances K
    # without an operation row; its plan records the K it was planned at).
    deletion_ks = [json.loads(d.pop('plan'))['catalog_sequence'] + 1 for d in deletions]
    for d, k in zip(deletions, deletion_ks):
        d['k'] = k
    sequences = sorted([o['sequence'] for o in operations] + deletion_ks)
    if sequences != list(range(1, len(sequences) + 1)) or len(sequences) != (stored.get('sequence') or 0):
        raise PlatformError('Legacy catalog sequence is not contiguous.', 'migration_inventory')
    stored.pop(SETTINGS_KEY, None)
    body = {'instance_id': stored.get('instance_id'), 'catalog_version': stored.get('schema'),
            'head': stored.get('sequence'), 'operations': operations, 'objects': objects,
            'fact_counts': fact_counts, 'evidence_uses': uses, 'deletions': deletions}
    return body, digest(body)


def freeze(root, migration_id):
    """Durably lock out every legacy runtime. Returns the original user_version (idempotent)."""
    root = Path(root)
    with _flock(root / '.operation.lock'), _flock(root / '.objects.lock'):
        conn = sqlite3.connect(root / 'catalog.sqlite3', isolation_level=None)
        try:
            conn.execute('PRAGMA busy_timeout=1000')
            conn.execute('PRAGMA synchronous=FULL')
            conn.execute('BEGIN IMMEDIATE')
            version = conn.execute('PRAGMA user_version').fetchone()[0]
            row = conn.execute('SELECT value FROM settings WHERE key = ?', (SETTINGS_KEY,)).fetchone()
            if version == FROZEN_VERSION:
                state = json.loads(row[0]) if row else None
                if not state or state.get('migration_id') != str(migration_id):
                    raise PlatformError('Legacy catalog is frozen by another migration.', 'migration_conflict')
                conn.execute('ROLLBACK')
                return state['original_user_version']
            if version not in LIVE_VERSIONS:
                raise PlatformError('Unsupported legacy catalog version.', 'catalog_version')
            conn.execute('INSERT OR REPLACE INTO settings(key, value) VALUES (?, ?)',
                         (SETTINGS_KEY, json.dumps({'migration_id': str(migration_id), 'original_user_version': version})))
            conn.execute(f'PRAGMA user_version={FROZEN_VERSION}')
            conn.execute('COMMIT')
            return version
        except BaseException:
            if conn.in_transaction:
                conn.execute('ROLLBACK')
            raise
        finally:
            conn.close()


def unfreeze(root, migration_id):
    """Restore the original version (abandon before cutover only). Idempotent."""
    root = Path(root)
    with _flock(root / '.operation.lock'), _flock(root / '.objects.lock'):
        conn = sqlite3.connect(root / 'catalog.sqlite3', isolation_level=None)
        try:
            conn.execute('PRAGMA synchronous=FULL')
            conn.execute('BEGIN IMMEDIATE')
            version = conn.execute('PRAGMA user_version').fetchone()[0]
            row = conn.execute('SELECT value FROM settings WHERE key = ?', (SETTINGS_KEY,)).fetchone()
            if version != FROZEN_VERSION:
                conn.execute('ROLLBACK')
                return version
            state = json.loads(row[0]) if row else None
            if not state or state.get('migration_id') != str(migration_id):
                raise PlatformError('Legacy catalog is frozen by another migration.', 'migration_conflict')
            conn.execute('DELETE FROM settings WHERE key = ?', (SETTINGS_KEY,))
            conn.execute(f"PRAGMA user_version={int(state['original_user_version'])}")
            conn.execute('COMMIT')
            return state['original_user_version']
        except BaseException:
            if conn.in_transaction:
                conn.execute('ROLLBACK')
            raise
        finally:
            conn.close()


def write_marker(root, state):
    write_atomic(Path(root) / MARKER, json.dumps(state, sort_keys=True).encode())


def read_marker(root):
    path = Path(root) / MARKER
    return json.loads(path.read_bytes()) if path.is_file() else None


def remove_marker(root):
    try:
        (Path(root) / MARKER).unlink()
    except FileNotFoundError:
        pass
