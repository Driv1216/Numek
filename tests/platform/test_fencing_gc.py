"""Fencing, leadership, verify-on-read, garbage collection, compaction and purge serialization."""
import datetime as dt
import uuid

import pytest

from helpers import lease_for, publish_records, record
from numek_platform.errors import FenceLost, IntegrityFailure, PlatformError
from numek_platform.evidence import codecs
from numek_platform.evidence.gc import GarbageCollector, add_hold, release_hold
from numek_platform.evidence.maintenance import compact, purge_facts, tombstone_objects
from numek_platform.evidence.publish import stage_object
from numek_platform.evidence.reader import pin, read, release, resolve
from numek_platform.execution import jobs
from numek_platform.execution.controller import Controller, acquire_leadership, assert_leader

NOW = dt.timedelta(0)


def _expire(platform, job_id):
    with platform.db.transaction() as conn:
        conn.execute("UPDATE jobs SET lease_expires_at = now() - interval '1 second' WHERE id = %s", (job_id,))


def _claimable(platform, key):
    with platform.db.transaction() as conn:
        return jobs.enqueue(conn, platform.scope, 'work', idempotency_key=key)


# Fencing ---------------------------------------------------------------------------

def test_stale_attempt_cannot_publish_renew_or_complete(platform):
    _claimable(platform, 'k1')
    with platform.db.connect() as conn:
        stale, _ = jobs.claim(conn, 'host-a', ['essential'])
    _expire(platform, stale.job_id)
    assert Controller(platform.db).run_once()['expired'] == 1
    with platform.db.connect() as conn:
        fresh, _ = jobs.claim(conn, 'host-b', ['essential'])
    assert fresh.job_id == stale.job_id and fresh.fence > stale.fence   # expiry and reclaim each advance it
    with pytest.raises(FenceLost):
        publish_records(platform, [record('context', ['ns', 'e'], {})], lease=stale)
    with platform.db.connect() as conn:
        with pytest.raises(FenceLost):
            jobs.renew(conn, stale)
        with pytest.raises(FenceLost):
            jobs.complete(conn, stale, {})
    receipt, _, _ = publish_records(platform, [record('context', ['ns', 'e'], {})], lease=fresh)
    assert receipt.new_facts == 1
    with platform.db.connect() as conn:
        jobs.complete(conn, fresh, {'ok': True})
        assert jobs.get(conn, platform.scope, fresh.job_id)['state'] == 'succeeded'


def test_retry_backoff_dead_letter_and_cancel(platform):
    with platform.db.transaction() as conn:
        jobs.enqueue(conn, platform.scope, 'work', idempotency_key='retry', max_attempts=2)
    with platform.db.connect() as conn:
        lease, _ = jobs.claim(conn, 'h', ['essential'])
        assert jobs.fail(conn, lease, {'code': 'io'}, retryable=True, backoff_seconds=0) == 'queued'
        lease, _ = jobs.claim(conn, 'h', ['essential'])
        assert jobs.fail(conn, lease, {'code': 'io'}, retryable=True, backoff_seconds=0) == 'failed'
    with platform.db.transaction() as conn:
        queued = jobs.enqueue(conn, platform.scope, 'work', idempotency_key='cancel-q')
    with platform.db.connect() as conn:
        assert jobs.request_cancel(conn, platform.scope, queued['id']) == 'cancelled'
        _claimable(platform, 'cancel-r')
        running, _ = jobs.claim(conn, 'h', ['essential'])
        assert jobs.request_cancel(conn, platform.scope, running.job_id) == 'cancelling'
        assert jobs.renew(conn, running) is True


def test_enqueue_is_idempotent(platform):
    first = _claimable(platform, 'same')
    second = _claimable(platform, 'same')
    assert first['id'] == second['id']


def test_deposed_controller_cannot_act(platform):
    with platform.db.connect() as conn:
        epoch_a = acquire_leadership(conn, 'a', ttl_seconds=30)
        assert acquire_leadership(conn, 'b', ttl_seconds=30) is None
        conn.execute("UPDATE controller_leadership SET expires_at = now() - interval '1 second'")
        epoch_b = acquire_leadership(conn, 'b', ttl_seconds=30)
        assert epoch_b == epoch_a + 1
        with pytest.raises(PlatformError) as caught, conn.transaction():
            assert_leader(conn, 'a', epoch_a)
        assert caught.value.code == 'not_leader'


def test_inline_attempts_die_rather_than_rerun(platform):
    lease = lease_for(platform)
    _expire(platform, lease.job_id)
    Controller(platform.db).run_once()
    with platform.db.connect() as conn:
        assert jobs.get(conn, platform.scope, lease.job_id)['state'] == 'dead'


# Objects and verification -------------------------------------------------------------

def test_verify_on_read_refuses_changed_or_missing_bytes(platform):
    _, ref, _ = publish_records(platform, [record('context', ['ns', 'e'], {'x': 1})])
    path = platform.store._path(ref.physical_key)
    original = path.read_bytes()
    read_pin = pin(platform.db, platform.scope, platform.catalog_id, holder='t')
    locators = resolve(platform.db, read_pin)
    path.write_bytes(original[:-1] + bytes([original[-1] ^ 1]))
    with pytest.raises(IntegrityFailure):
        list(read(platform.store, locators))
    path.unlink()
    with pytest.raises(IntegrityFailure):
        list(read(platform.store, locators))


def test_identical_bytes_dedupe_only_against_active_objects(platform):
    lease = lease_for(platform)
    data = b'opaque artifact'
    first = stage_object(platform.db, platform.store, lease, data, catalog_id=platform.catalog_id, codec=codecs.BLOB)
    second = stage_object(platform.db, platform.store, lease, data, catalog_id=platform.catalog_id, codec=codecs.BLOB)
    assert not first.reused and not second.reused and second.generation == first.generation + 1  # pending: no dedupe
    from numek_platform.evidence.publish import publish
    publish(platform.db, platform.scope, lease, platform.catalog_id, request_id='r', request_digest='d', kind='blob',
            objects=[first])
    third = stage_object(platform.db, platform.store, lease, data, catalog_id=platform.catalog_id, codec=codecs.BLOB)
    assert third.reused and third.id == first.id
    tombstone_objects(platform.db, platform.scope, lease, platform.catalog_id, [first.id])
    fourth = stage_object(platform.db, platform.store, lease, data, catalog_id=platform.catalog_id, codec=codecs.BLOB)
    assert not fourth.reused and fourth.generation > second.generation


# Garbage collection -------------------------------------------------------------------------

def test_gc_never_reclaims_live_pending_and_reclaims_stale_pending(platform):
    lease = lease_for(platform)
    ref = stage_object(platform.db, platform.store, lease, b'pending bytes', catalog_id=platform.catalog_id,
                       codec=codecs.BLOB)
    gc = GarbageCollector(platform.db, platform.store, grace=NOW, pending_ttl=NOW)
    gc.run_once()
    assert platform.store.exists(ref.physical_key)                       # attempt still live
    _expire(platform, lease.job_id)
    Controller(platform.db).run_once()                                   # inline attempt -> dead
    report = gc.run_once()
    assert report['reclaimed'] == 1 and not platform.store.exists(ref.physical_key)
    with platform.db.connect() as conn:
        assert conn.execute('SELECT state FROM objects WHERE id = %s', (ref.id,)).fetchone()['state'] == 'reclaimed'


def test_gc_respects_pins_holds_and_grace(platform):
    _, ref, lease = publish_records(platform, [record('context', ['ns', 'e1'], {'x': 1})])
    _, other, _ = publish_records(platform, [record('context', ['ns', 'e2'], {'x': 2})])
    read_pin = pin(platform.db, platform.scope, platform.catalog_id, holder='reader')
    old_locators = resolve(platform.db, read_pin, keys=[record('context', ['ns', 'e1'], {'x': 1})['key']])
    new_id = compact(platform.db, platform.store, platform.scope, lease, platform.catalog_id, [ref.id, other.id])
    gc = GarbageCollector(platform.db, platform.store, grace=NOW, pending_ttl=NOW)
    gc.run_once()
    assert platform.store.exists(ref.physical_key)                       # pin floor < tombstone epoch
    assert [r['identity'] for _, r in read(platform.store, old_locators)] == [['ns', 'e1']]
    release(platform.db, read_pin)
    hold = add_hold(platform.db, 'test')
    gc.run_once()
    assert platform.store.exists(ref.physical_key)                       # held
    release_hold(platform.db, hold)
    assert GarbageCollector(platform.db, platform.store, grace=dt.timedelta(hours=1)).run_once()['reclaimed'] == 0
    assert gc.run_once()['reclaimed'] == 2 and not platform.store.exists(ref.physical_key)
    fresh = pin(platform.db, platform.scope, platform.catalog_id, holder='after')
    got = list(read(platform.store, resolve(platform.db, fresh)))
    assert {l.object_id for l, _ in got} == {new_id}
    assert sorted(r['identity'][1] for _, r in got) == ['e1', 'e2']


def test_gc_finishes_interrupted_reclamation_and_cleans_staging(platform):
    _, ref, lease = publish_records(platform, [record('context', ['ns', 'e'], {})])
    with platform.db.transaction() as conn:
        conn.execute("UPDATE objects SET state = 'reclaiming' WHERE id = %s", (ref.id,))
    leftover = platform.store.staging_dir(uuid.uuid4(), 3)
    leftover.mkdir(parents=True)
    report = GarbageCollector(platform.db, platform.store, pending_ttl=NOW).run_once()
    assert report['reclaimed'] == 1 and report['staging_removed'] >= 1 and not leftover.exists()


# Compaction and purge ------------------------------------------------------------------------

def test_compaction_preserves_identity_and_excludes_purged_rows(platform):
    first = [record('opportunity', ['ns', f'a{i}'], {'i': i}) for i in range(3)]
    second = [record('opportunity', ['ns', f'b{i}'], {'i': i}) for i in range(3)]
    _, ref1, lease = publish_records(platform, first)
    _, ref2, _ = publish_records(platform, second)
    purge_facts(platform.db, platform.scope, lease, platform.catalog_id, [('opportunity', first[0]['key'], 'initial')],
                request_id='p', reason='test')
    before_digests = {r['fact_digest'] for r in first[1:] + second}
    new_id = compact(platform.db, platform.store, platform.scope, lease, platform.catalog_id, [ref1.id, ref2.id])
    read_pin = pin(platform.db, platform.scope, platform.catalog_id, holder='t')
    got = list(read(platform.store, resolve(platform.db, read_pin, require_complete=False)))
    assert {r['fact_digest'] for _, r in got} == before_digests and {l.object_id for l, _ in got} == {new_id}
    with platform.db.connect() as conn:
        assert conn.execute('SELECT records FROM objects WHERE id = %s', (new_id,)).fetchone()['records'] == 5


def test_purge_during_analysis_aborts_publication_and_refuses_reads(platform):
    fact = record('context', ['ns', 'e1'], {'value': 1})
    _, _, lease = publish_records(platform, [fact])
    analysis = lease_for(platform, kind='analysis')
    read_pin = pin(platform.db, platform.scope, platform.catalog_id, lease=analysis)
    assert len(resolve(platform.db, read_pin)) == 1
    purge_facts(platform.db, platform.scope, lease, platform.catalog_id, [('context', fact['key'], 'initial')],
                request_id='purge', reason='withdrawn')
    with pytest.raises(PlatformError) as caught:
        publish_records(platform, [record('context', ['ns', 'derived'], {})], lease=analysis, pin=read_pin)
    assert caught.value.code == 'evidence_deleted_during_analysis'
    with pytest.raises(PlatformError) as caught:
        resolve(platform.db, read_pin)
    assert caught.value.code == 'historical_evidence_unavailable'
    assert resolve(platform.db, read_pin, require_complete=False) == []


def test_publication_with_pin_succeeds_when_unrelated_purge_happened(platform):
    a = record('outcome', ['ns', 'a', 'v', 't'], {'value': 1})
    _, _, lease = publish_records(platform, [a])
    analysis = lease_for(platform, kind='analysis')
    read_pin = pin(platform.db, platform.scope, platform.catalog_id, lease=analysis)
    later = record('outcome', ['ns', 'later', 'v', 't'], {'value': 0})
    publish_records(platform, [later])                                   # sequence > pin.k
    purge_facts(platform.db, platform.scope, lease, platform.catalog_id, [('outcome', later['key'], 'initial')],
                request_id='purge-later', reason='withdrawn')
    receipt, _, _ = publish_records(platform, [record('context', ['ns', 'derived'], {})], lease=analysis, pin=read_pin)
    assert receipt.new_facts == 1
