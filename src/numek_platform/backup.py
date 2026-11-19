"""Consistent installation backups (R2.2).

Recovery point: one PostgreSQL snapshot S. A backup contains

* a logical dump taken at exactly S (``pg_dump --snapshot``);
* every object that is active at S, except raw ingestion batches that are no
  longer needed for recovery (``retained_for_recovery = false``) unless asked;
  raw objects of acknowledged-but-unprocessed batches are therefore always in;
* a keyring, wrapped with the operator's passphrase, holding every data key
  that any included object needs; the backup refuses if one is missing;
* a manifest with the SHA-256 of every file.

A ``gc_holds`` row keeps every object present at S on disk while it is copied.
Batches acknowledged after S are not covered; producers may resend (unknown
batch ids are accepted as new after a restore).

Restore is offline and produces a new installation identity. Running attempts
at S are requeued with fence + 1, pending objects (bytes not in the cut) are
marked reclaimed, read pins are cleared and evidence continuity becomes
``restore_unreconciled``.
"""
import datetime as dt
import hashlib
import json
import os
import shutil
import subprocess
import uuid
from pathlib import Path

from .errors import PlatformError
from .evidence.gc import add_hold, release_hold
from .fsutil import fsync_directory, open_private, private_directory, write_atomic
from .local import find_binaries, server_env
from .secrets import export_keyring, import_keyring

MANIFEST = 'manifest.json'


def _sha_file(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as stream:
        for block in iter(lambda: stream.read(1024**2), b''):
            digest.update(block)
    return digest.hexdigest()


def create_backup(db, store, secret_store, destination, *, passphrase, include_terminal_raw=False, config_bytes=None):
    destination = Path(destination).absolute()
    if destination.exists():
        raise PlatformError('Backup destination must be new.', 'backup_destination')
    if str(destination).startswith(str(store.root) + os.sep):
        raise PlatformError('Backups must be outside the live platform root.', 'backup_destination')
    private_directory(destination)
    hold = add_hold(db, 'backup')
    files = {}
    try:
        with db.transaction('repeatable_read', read_only=True) as conn:
            snapshot = conn.execute('SELECT pg_export_snapshot() AS s').fetchone()['s']
            installation = conn.execute('SELECT installation_id FROM installation').fetchone()['installation_id']
            objects = conn.execute(
                '''SELECT org_id, id, physical_key, sha256, bytes, key_id, codec FROM objects
                   WHERE state = 'active' AND (codec <> 'encrypted_raw_batch_v1' OR retained_for_recovery OR %s)
                   ORDER BY id''', (include_terminal_raw,)).fetchall()
            keys = sorted({(r['org_id'], r['key_id']) for r in objects if r['key_id'] is not None}, key=str)
            dump = destination / 'database.dump'
            result = subprocess.run([str(find_binaries() / 'pg_dump'), '--snapshot', snapshot, '-Fc', '--no-owner',
                                     '-f', str(dump), '-d', db.dsn], capture_output=True, text=True, env=server_env())
            if result.returncode != 0:
                raise PlatformError('Database dump failed: ' + result.stderr.strip()[-300:], 'backup_failed')
        os.chmod(dump, 0o600)
        files['database.dump'] = _sha_file(dump)
        if keys or passphrase is not None:
            if passphrase is None:
                raise PlatformError('This backup includes encrypted objects; a backup passphrase is required.',
                                    'backup_passphrase')
            keyring = export_keyring(secret_store, keys, passphrase)
            write_atomic(destination / 'keyring.bin', keyring)
            files['keyring.bin'] = hashlib.sha256(keyring).hexdigest()
        object_root = private_directory(destination / 'objects')
        for row in objects:
            data = store.read_verified(row['physical_key'], bytes(row['sha256']).hex(), row['bytes'])
            target = object_root / row['physical_key'].replace('/', '__')
            with open_private(target, 'xb') as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            files['objects/' + target.name] = bytes(row['sha256']).hex()
        fsync_directory(object_root)
        if config_bytes is not None:
            write_atomic(destination / 'config.bin', config_bytes)
            files['config.bin'] = hashlib.sha256(config_bytes).hexdigest()
        manifest = {'format': 'numek_platform_backup/1', 'installation_id': str(installation), 'snapshot': snapshot,
                    'created_at': dt.datetime.now(dt.timezone.utc).isoformat(), 'objects': len(objects),
                    'keys': len(keys), 'include_terminal_raw': include_terminal_raw,
                    'recovery_point': 'database snapshot; batches acknowledged after it are not covered',
                    'files': files}
        write_atomic(destination / MANIFEST, json.dumps(manifest, sort_keys=True, indent=1).encode())
        return manifest
    except BaseException:
        shutil.rmtree(destination, ignore_errors=True)
        raise
    finally:
        release_hold(db, hold)


def verify_backup(source):
    source = Path(source)
    manifest = json.loads((source / MANIFEST).read_bytes())
    for name, expected in manifest['files'].items():
        if _sha_file(source / name) != expected:
            raise PlatformError('Backup content does not match its manifest.', 'backup_invalid')
    return manifest


def restore_backup(source, db, store, secret_store, *, passphrase):
    """Restore into an empty database and empty object store; returns the new installation id."""
    source = Path(source)
    manifest = verify_backup(source)
    with db.connect() as conn:
        if conn.execute("SELECT to_regclass('numek.installation') AS t").fetchone()['t']:
            raise PlatformError('Restore requires an empty database.', 'restore_target')
    result = subprocess.run([str(find_binaries() / 'pg_restore'), '--no-owner', '--exit-on-error', '-d', db.dsn,
                             str(source / 'database.dump')], capture_output=True, text=True, env=server_env())
    if result.returncode != 0:
        raise PlatformError('Database restore failed: ' + result.stderr.strip()[-300:], 'restore_failed')
    if (source / 'keyring.bin').exists():
        import_keyring(secret_store, (source / 'keyring.bin').read_bytes(), passphrase)
    with db.connect() as conn:
        rows = conn.execute("SELECT id, physical_key, sha256, bytes FROM objects WHERE state = 'active'").fetchall()
    restored = 0
    for row in rows:
        backup_file = source / 'objects' / row['physical_key'].replace('/', '__')
        if not backup_file.exists():
            continue  # terminal raw batch excluded from the cut; handled below
        data = backup_file.read_bytes()
        if hashlib.sha256(data).hexdigest() != bytes(row['sha256']).hex() or len(data) != row['bytes']:
            raise PlatformError('Backup object failed verification.', 'backup_invalid')
        staged = store.write_staged(uuid.UUID(int=0), 0, data)
        store.promote(staged, row['physical_key'])
        restored += 1
    store.remove_staging(store.staging_dir(uuid.UUID(int=0), 0))
    new_installation = uuid.uuid4()
    with db.transaction() as conn:
        conn.execute('UPDATE installation SET installation_id = %s, restored_from = %s',
                     (new_installation, manifest['installation_id']))
        conn.execute('''UPDATE jobs SET fence = fence + 1, state = 'queued', lease_owner = NULL, lease_expires_at = NULL
                        WHERE state = 'running' ''')
        conn.execute("UPDATE objects SET state = 'reclaimed' WHERE state IN ('pending', 'reclaiming')")
        # Active objects deliberately left out of the cut (terminal raw batches) no longer exist here.
        missing = [r['id'] for r in rows if not (source / 'objects' / r['physical_key'].replace('/', '__')).exists()]
        if missing:
            conn.execute("UPDATE objects SET state = 'reclaimed', retained_for_recovery = false WHERE id = ANY(%s)", (missing,))
        conn.execute('UPDATE read_pins SET released_at = now() WHERE released_at IS NULL')
        conn.execute('UPDATE gc_holds SET released_at = now() WHERE released_at IS NULL')
        conn.execute("UPDATE catalogs SET continuity_state = 'restore_unreconciled'")
    return {'installation_id': str(new_installation), 'objects_restored': restored, 'restored_from': manifest['installation_id']}
