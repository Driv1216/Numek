"""Backup cut and restore; legacy v2 migration state machine; lock-order interleavings."""
import os
import random
import sqlite3
import threading
import uuid

import psycopg
import pytest

from helpers import lease_for, publish_records, record
from numek_platform.backup import create_backup, restore_backup
from numek_platform.db import Database
from numek_platform.errors import PlatformError
from numek_platform.evidence import codecs
from numek_platform.evidence.gc import GarbageCollector
from numek_platform.evidence.maintenance import compact, purge_facts
from numek_platform.evidence.publish import publish, stage_object
from numek_platform.evidence.reader import pin, read, resolve
from numek_platform.execution import jobs
from numek_platform.legacy import catalog_v2, migration
from numek_platform.objects import LocalObjectStore
from numek_platform.secrets import DataKeys, FileSecretStore

PASS = 'backup passphrase 1'


def _raw_object(platform, keys, lease, body, *, retained):
    with platform.db.transaction() as conn:
        key_id = keys.create(conn, platform.scope, 'raw_batch')
    envelope = keys.encrypt(platform.scope, key_id, body)
    ref = stage_object(platform.db, platform.store, lease, envelope, catalog_id=platform.catalog_id,
                       codec=codecs.RAW_BATCH, key_id=key_id, retained_for_recovery=retained)
    publish(platform.db, platform.scope, lease, platform.catalog_id, request_id=uuid.uuid4().hex, request_digest='raw',
            kind='raw_batch', objects=[ref])
    return ref, key_id


def test_backup_cut_includes_unprocessed_raw_batches_and_restores_consistently(platform, cluster):
    secrets = FileSecretStore(platform.root / 'secrets')
    keys = DataKeys(secrets)
    facts = [record('opportunity', ['ns', f'e{i}'], {'i': i}) for i in range(4)]
    _, _, lease = publish_records(platform, facts)
    pending_raw, _ = _raw_object(platform, keys, lease, b'acknowledged, not yet processed', retained=True)
    done_raw, _ = _raw_object(platform, keys, lease, b'already processed', retained=False)
    with platform.db.transaction() as conn:
        jobs.enqueue(conn, platform.scope, 'work', idempotency_key='in-flight')
    with platform.db.connect() as conn:
        running, _ = jobs.claim(conn, 'host', ['essential'])

    manifest = create_backup(platform.db, platform.store, secrets, platform.root / 'backup', passphrase=PASS)
    assert manifest['objects'] == 2 and manifest['keys'] == 1        # facts + unprocessed raw; terminal raw excluded

    target_name = 'r_' + uuid.uuid4().hex[:10]
    target = Database(cluster.create_database(target_name))
    try:
        new_store = LocalObjectStore(platform.root / 'restored-store')
        new_secrets = FileSecretStore(platform.root / 'restored-secrets')
        result = restore_backup(platform.root / 'backup', target, new_store, new_secrets, passphrase=PASS)
        assert result['restored_from'] == manifest['installation_id'] != result['installation_id']
        read_pin = pin(target, platform.scope, platform.catalog_id, holder='verify')
        got = sorted(r['identity'][1] for _, r in read(new_store, resolve(target, read_pin)))
        assert got == ['e0', 'e1', 'e2', 'e3']
        with target.connect() as conn:
            states = {r['id']: r['state'] for r in conn.execute('SELECT id, state FROM objects')}
            job = jobs.get(conn, platform.scope, running.job_id)
            continuity = conn.execute('SELECT continuity_state FROM catalogs WHERE id = %s',
                                      (platform.catalog_id,)).fetchone()['continuity_state']
        assert states[pending_raw.id] == 'active' and states[done_raw.id] == 'reclaimed'
        assert job['state'] == 'queued' and job['fence'] > running.fence
        assert continuity == 'restore_unreconciled'
        data = new_store.read_verified(pending_raw.physical_key, pending_raw.sha256, pending_raw.bytes)
        assert DataKeys(new_secrets).decrypt(platform.scope, data) == b'acknowledged, not yet processed'
    finally:
        cluster.drop_database(target_name)


def test_backup_refuses_when_a_required_key_is_missing(platform):
    secrets = FileSecretStore(platform.root / 'secrets')
    keys = DataKeys(secrets)
    lease = lease_for(platform)
    _, key_id = _raw_object(platform, keys, lease, b'body', retained=True)
    with platform.db.transaction() as conn:
        keys.destroy_live(conn, platform.scope, key_id)
    with pytest.raises(PlatformError) as caught:
        create_backup(platform.db, platform.store, secrets, platform.root / 'backup', passphrase=PASS)
    assert caught.value.code == 'backup_key_missing' and not (platform.root / 'backup').exists()


# Legacy migration --------------------------------------------------------------------------

@pytest.fixture
def legacy_root(platform):
    """A frozen catalog v2 fixture workspace (catalog v2 can no longer be created)."""
    from test_v2_migration import fixture
    return fixture('cg3', platform.root)[0]


def _legacy_opens(root):
    """The check every released catalog v2 runtime makes on open (``user_version in (1, 2)``)."""
    if catalog_v2.user_version(root) not in catalog_v2.LIVE_VERSIONS:
        raise PlatformError('Unsupported catalog version.', 'catalog_version')


def test_freeze_locks_out_legacy_runtimes_and_abandon_restores(platform, legacy_root):
    migration_id, catalog_id = migration.plan(platform.db, platform.scope, legacy_root, catalog_name='legacy')
    migration.freeze(platform.db, platform.scope, migration_id)
    with pytest.raises(Exception) as caught:
        _legacy_opens(legacy_root)
    assert getattr(caught.value, 'code', '') == 'catalog_version'
    assert catalog_v2.read_marker(legacy_root)['state'] == 'frozen'
    with pytest.raises(PlatformError):
        pin(platform.db, platform.scope, catalog_id, holder='x')         # partially migrated: inaccessible
    migration.freeze(platform.db, platform.scope, migration_id)          # repeatable after a crash
    migration.abandon(platform.db, platform.scope, migration_id)
    _legacy_opens(legacy_root)
    assert catalog_v2.user_version(legacy_root) == 2 and catalog_v2.read_marker(legacy_root) is None
    migration.abandon(platform.db, platform.scope, migration_id)          # idempotent


def test_resume_aborts_when_the_frozen_source_changed(platform, legacy_root):
    migration_id, _ = migration.plan(platform.db, platform.scope, legacy_root, catalog_name='legacy')
    migration.freeze(platform.db, platform.scope, migration_id)
    with sqlite3.connect(legacy_root / 'catalog.sqlite3') as conn:
        conn.execute("UPDATE settings SET value = '7' WHERE key = 'sequence'")
    with pytest.raises(PlatformError) as caught:
        migration.begin_copy(platform.db, platform.scope, migration_id)
    assert caught.value.code == 'migration_source_changed'


def test_cutover_is_the_point_of_no_return(platform, legacy_root):
    migration_id, catalog_id = migration.plan(platform.db, platform.scope, legacy_root, catalog_name='legacy')
    migration.freeze(platform.db, platform.scope, migration_id)
    migration.begin_copy(platform.db, platform.scope, migration_id)
    with pytest.raises(PlatformError) as caught:                            # nothing copied yet
        migration.begin_validation(platform.db, platform.scope, migration_id)
    assert caught.value.code == 'migration_incomplete'
    from confidenceguard.migration import Legacy, _Replay
    from numek_platform.execution import jobs
    legacy = Legacy(legacy_root)
    with platform.db.connect() as conn:
        lease, _row = jobs.start_inline(conn, platform.scope, 'copy', idempotency_key='copy', owner='test')
    _Replay(platform.db, platform.scope, platform.store, legacy, catalog_id, migration_id, lease).run(1, legacy.events())
    migration.begin_validation(platform.db, platform.scope, migration_id)   # every legacy K copied
    with pytest.raises(PlatformError):
        migration.cutover(platform.db, platform.scope, migration_id, {'passed': False})
    migration.cutover(platform.db, platform.scope, migration_id, {'passed': True, 'checks': ['inventory']})
    assert pin(platform.db, platform.scope, catalog_id, holder='x').k == legacy.settings['sequence']   # now accessible
    assert catalog_v2.read_marker(legacy_root)['state'] == 'cutover_committed'
    assert migration.status(platform.db, platform.scope, migration_id)['complete'] is False
    migration.record_post_cutover_backup(platform.db, platform.scope, migration_id,
                                         {'installation_id': 'x', 'created_at': 'now', 'objects': 0})
    assert migration.status(platform.db, platform.scope, migration_id)['complete'] is True
    with pytest.raises(PlatformError) as caught:
        migration.abandon(platform.db, platform.scope, migration_id)
    assert caught.value.code == 'migration_state'
    with pytest.raises(Exception):
        _legacy_opens(legacy_root)                                         # stays frozen permanently


# Lock-order interleavings ----------------------------------------------------------------------

def test_randomized_interleavings_never_deadlock_and_preserve_evidence(platform):
    rng = random.Random(20261119)
    errors, deadlocks = [], []
    expected = {}
    lock = threading.Lock()
    tolerated = {'compaction_conflict', 'compaction_noop', 'not_compactable', 'object_unavailable'}

    def worker(seed):
        local = random.Random(seed)
        for step in range(int(os.environ.get('NUMEK_INTERLEAVING_STEPS', '12'))):
            op = local.choice(['publish', 'publish', 'publish', 'purge', 'compact', 'gc'])
            try:
                if op == 'publish':
                    recs = [record('opportunity', ['ns', f's{seed}-{step}-{i}'], {'v': i}) for i in range(3)]
                    publish_records(platform, recs)
                    with lock:
                        expected.update({r['key']: r['fact_digest'] for r in recs})
                elif op == 'purge':
                    with lock:
                        if not expected:
                            continue
                        key = local.choice(sorted(expected))
                        expected.pop(key)
                    purge_facts(platform.db, platform.scope, lease_for(platform), platform.catalog_id,
                                [('opportunity', key, 'initial')], request_id=uuid.uuid4().hex, reason='test')
                elif op == 'compact':
                    with platform.db.connect() as conn:
                        ids = [r['id'] for r in conn.execute(
                            "SELECT id FROM objects WHERE catalog_id = %s AND state = 'active' AND codec = %s LIMIT 3",
                            (platform.catalog_id, codecs.OBSERVATIONS))]
                    if len(ids) >= 2:
                        compact(platform.db, platform.store, platform.scope, lease_for(platform), platform.catalog_id, ids)
                else:
                    GarbageCollector(platform.db, platform.store, grace=__import__('datetime').timedelta(0)).run_once()
            except psycopg.errors.DeadlockDetected as exc:
                deadlocks.append(exc)
            except PlatformError as exc:
                if exc.code not in tolerated:
                    errors.append(exc)
            except Exception as exc:  # pragma: no cover - surfaced below
                errors.append(exc)

    threads = [threading.Thread(target=worker, args=(rng.random(),)) for _ in range(6)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert not deadlocks and not errors, (deadlocks, errors)
    read_pin = pin(platform.db, platform.scope, platform.catalog_id, holder='final')
    survivors = {r['key']: r['fact_digest'] for _, r in read(platform.store, resolve(platform.db, read_pin,
                                                                                       require_complete=False))}
    assert survivors == expected
