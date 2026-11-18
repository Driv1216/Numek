"""Publication protocol: identity, K-prefix order, idempotency, corrections, conflicts."""
import threading
import uuid

import psycopg
import pytest

from helpers import lease_for, publish_records, record
from numek_platform.canonical import canonical_bytes, digest, serialized
from numek_platform.db.migrator import migrate
from numek_platform.errors import PlatformError
from numek_platform.evidence import codecs
from numek_platform.evidence.maintenance import purge_facts
from numek_platform.evidence.reader import pin, read, release, resolve


def test_canonical_identity_matches_confidenceguard():
    from confidenceguard.contracts import digest as cg_digest
    from confidenceguard.history_storage import serialized as cg_serialized
    values = [{'b': 1, 'a': [1.5, None, True, 'x']}, {'big': 2**60, 'nested': {'z': -0.0}},
              {'inf': float('inf')}, ['ü', {'k': (1, 2)}]]
    for value in values:
        assert serialized(value) == cg_serialized(value)
        if 'inf' not in value:
            assert digest(value) == cg_digest(value)
    assert canonical_bytes({'b': 1, 'a': 2}) == b'{"a":2,"b":1}'


def test_migrations_are_idempotent_and_checksummed(platform):
    assert migrate(platform.db) == []
    with platform.db.transaction() as conn:
        conn.execute("UPDATE schema_migrations SET sha256 = 'tampered' WHERE version = 1")
    with pytest.raises(PlatformError) as caught:
        migrate(platform.db)
    assert caught.value.code == 'migration_changed'


@pytest.mark.parametrize('codec', [codecs.OBSERVATIONS, codecs.JSONL])
def test_publish_and_read_roundtrip(platform, codec):
    records = [record('opportunity', ['ns', f'event-{i}'], {'tick': str(i)}) for i in range(5)]
    receipt, ref, _ = publish_records(platform, records, codec=codec, event_ticks=list(range(5)))
    assert (receipt.sequence, receipt.new_facts, receipt.duplicate_occurrences) == (1, 5, 0)
    read_pin = pin(platform.db, platform.scope, platform.catalog_id, holder='test')
    locators = resolve(platform.db, read_pin, event_tick_range=(1, 4))
    got = sorted(r['identity'][1] for _, r in read(platform.store, locators))
    assert got == ['event-1', 'event-2', 'event-3']
    assert all(rec == original for (_, rec), original in zip(read(platform.store, resolve(platform.db, read_pin)), records))
    release(platform.db, read_pin)


def test_idempotent_replay_and_conflicting_reuse(platform):
    records = [record('opportunity', ['ns', 'e1'], {'v': 1})]
    first, _, lease = publish_records(platform, records, request_id='req-1')
    again, _, _ = publish_records(platform, records, request_id='req-1', lease=lease)
    assert again.replayed and again.sequence == first.sequence
    other = [record('opportunity', ['ns', 'e2'], {'v': 2})]
    with pytest.raises(PlatformError) as caught:
        publish_records(platform, other, request_id='req-1', lease=lease)
    assert caught.value.code == 'idempotency_conflict'


def test_duplicates_count_once_and_conflicts_are_refused_or_quarantined(platform):
    base = record('outcome', ['ns', 'e1', 'v1', 't'], {'value': 1})
    publish_records(platform, [base])
    receipt, _, _ = publish_records(platform, [base, record('outcome', ['ns', 'e2', 'v1', 't'], {'value': 0})])
    assert (receipt.new_facts, receipt.duplicate_occurrences) == (1, 1)
    changed = record('outcome', ['ns', 'e1', 'v1', 't'], {'value': 0})       # same identity+revision, new payload
    with pytest.raises(PlatformError) as caught:
        publish_records(platform, [changed])
    assert caught.value.code == 'fact_conflict'
    receipt, _, _ = publish_records(platform, [changed, record('outcome', ['ns', 'e3', 'v1', 't'], {'value': 1})],
                                    on_conflict='quarantine')
    assert receipt.new_facts == 1 and [c['reason'] for c in receipt.conflicts] == ['fact_conflict']


def test_ambiguous_batch_publishes_neither_variant(platform):
    a = record('outcome', ['ns', 'x', 'v1', 't'], {'value': 1})
    b = record('outcome', ['ns', 'x', 'v1', 't'], {'value': 0})
    receipt, _, _ = publish_records(platform, [a, b], on_conflict='quarantine')
    assert receipt.new_facts == 0 and receipt.conflicts[0]['reason'] == 'batch_conflict'


def test_timestamp_correction_keeps_identity_and_forks_are_refused(platform):
    original = record('opportunity', ['ns', 'e1'], {'time': '100'})
    publish_records(platform, [original], event_ticks=[100])
    corrected = record('opportunity', ['ns', 'e1'], {'time': '900'}, revision='r2', predecessor=original['fact_digest'])
    receipt, _, _ = publish_records(platform, [corrected], event_ticks=[900])
    assert receipt.new_facts == 1
    with platform.db.connect() as conn:
        rows = conn.execute('SELECT DISTINCT key FROM fact_index WHERE catalog_id = %s', (platform.catalog_id,)).fetchall()
    assert len(rows) == 1                     # one logical identity despite a different event day
    fork = record('opportunity', ['ns', 'e1'], {'time': '901'}, revision='r3', predecessor=original['fact_digest'])
    with pytest.raises(PlatformError) as caught:
        publish_records(platform, [fork])
    assert caught.value.code == 'correction_fork'
    orphan = record('opportunity', ['ns', 'e9'], {'time': '1'}, revision='r2', predecessor='0' * 64)
    with pytest.raises(PlatformError) as caught:
        publish_records(platform, [orphan])
    assert caught.value.code == 'correction_predecessor'


def test_purged_identity_cannot_be_reimported(platform):
    fact = record('context', ['ns', 'e1'], {'x': 1})
    _, _, lease = publish_records(platform, [fact])
    purge_facts(platform.db, platform.scope, lease, platform.catalog_id, [('context', fact['key'], 'initial')],
                request_id='purge-1', reason='subject request')
    with pytest.raises(PlatformError) as caught:
        publish_records(platform, [fact])
    assert caught.value.code == 'historical_evidence_unavailable'


def test_k_order_equals_commit_order_under_concurrency(platform):
    errors, stop = [], threading.Event()
    observations = []

    def writer(n):
        try:
            for i in range(8):
                publish_records(platform, [record('opportunity', ['ns', f'w{n}-{i}'], {'i': i})])
        except Exception as exc:  # pragma: no cover - surfaced below
            errors.append(exc)

    def reader():
        with platform.db.connect() as conn:
            while not stop.is_set():
                with conn.transaction():
                    conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ')
                    head = conn.execute('SELECT head FROM catalog_heads WHERE catalog_id = %s', (platform.catalog_id,)).fetchone()['head']
                    seqs = [r['sequence'] for r in conn.execute(
                        'SELECT sequence FROM publications WHERE catalog_id = %s AND sequence <= %s ORDER BY sequence',
                        (platform.catalog_id, head))]
                observations.append((head, seqs))

    threads = [threading.Thread(target=writer, args=(n,)) for n in range(6)]
    watcher = threading.Thread(target=reader)
    watcher.start()
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    stop.set()
    watcher.join()
    assert not errors
    assert observations and all(seqs == list(range(1, head + 1)) for head, seqs in observations)
    with platform.db.connect() as conn:
        assert conn.execute('SELECT head FROM catalog_heads WHERE catalog_id = %s', (platform.catalog_id,)).fetchone()['head'] == 48


def test_concurrent_identical_identity_publishes_once(platform):
    fact = record('outcome', ['ns', 'same', 'v1', 't'], {'value': 1})
    barrier, receipts, errors = threading.Barrier(4), [], []

    def go():
        try:
            barrier.wait()
            receipts.append(publish_records(platform, [fact])[0])
        except Exception as exc:  # pragma: no cover
            errors.append(exc)

    threads = [threading.Thread(target=go) for _ in range(4)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert not errors
    assert sorted(r.new_facts for r in receipts) == [0, 0, 0, 1]
    assert sum(r.duplicate_occurrences for r in receipts) == 3


def test_cross_organisation_references_are_impossible(platform):
    other_scope, other_catalog = platform.new_org('other')
    fact = record('context', ['ns', 'e1'], {'x': 1})
    _, ref, _ = publish_records(platform, [fact])
    with platform.db.transaction() as conn, pytest.raises(psycopg.errors.ForeignKeyViolation):
        conn.execute(
            '''INSERT INTO fact_index(org_id, catalog_id, kind, key, revision, fact_digest, object_id, locator_kind,
                                      loc_a, loc_b, publication_id)
               SELECT %s, %s, 'context', %s, 'x', %s, %s, 'row', 0, 0, id FROM publications LIMIT 1''',
            (other_scope.org_id, other_catalog, bytes(32), bytes(32), ref.id))
    with pytest.raises(PlatformError) as caught:
        publish_records(platform, [record('context', ['ns', 'e2'], {'x': 2})], scope=other_scope,
                        catalog_id=platform.catalog_id, lease=lease_for(platform, scope=other_scope))
    assert caught.value.code in ('unknown_catalog', 'unknown_object')


def test_migrating_catalog_is_inaccessible(platform):
    from numek_platform.evidence.catalogs import create_catalog
    with platform.db.transaction() as conn:
        hidden = create_catalog(conn, platform.scope, 'migrating', state='migrating')
    with pytest.raises(PlatformError) as caught:
        pin(platform.db, platform.scope, hidden, holder='x')
    assert caught.value.code == 'catalog_unavailable'
    with pytest.raises(PlatformError) as caught:
        publish_records(platform, [record('context', ['ns', 'e'], {})], catalog_id=hidden)
    assert caught.value.code == 'catalog_unavailable'


def test_payload_with_nonfinite_numbers_roundtrips(platform):
    fact = record('prediction', ['ns', 'e1', 'v', 0, 0], {'log_loss': {'__cg_number__': 'positive_infinity'}})
    publish_records(platform, [fact])
    read_pin = pin(platform.db, platform.scope, platform.catalog_id, holder='t')
    [(_, got)] = list(read(platform.store, resolve(platform.db, read_pin)))
    assert got == fact and uuid.UUID(str(read_pin.id))
