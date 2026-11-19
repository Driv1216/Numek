"""Purge and compaction.

Purge (logical deletion) records fact tombstones at a new tombstone epoch and
K_del. It takes ``catalog_tombstones`` FOR UPDATE, so it waits for in-flight
publications (which hold it FOR SHARE) and every later publication sees the new
epoch. Purged identities stay in the global index, so they can never be
re-imported silently. Bytes are removed later by compaction plus GC.

Compaction (I-6) rewrites ``observation_facts_parquet_v1`` objects. It verifies
every surviving record's logical digest, moves locators in one transaction at a
new maintenance epoch and tombstones the old objects. K, fact identities,
digests and logical dependencies do not change.
"""
import uuid

from psycopg.types.json import Jsonb

from ..errors import PlatformError
from ..execution.jobs import assert_fence
from . import codecs
from .catalogs import catalog, require_active
from .publish import stage_object
from .reader import pin as pin_catalog, read, release, resolve


def purge_facts(db, scope, lease, catalog_id, identities, *, request_id, reason):
    """Tombstone the given (kind, key_hex, revision) identities at a new K."""
    if not reason:
        raise PlatformError('A purge requires a reason.', 'purge_reason')
    with db.transaction() as conn:
        assert_fence(conn, lease)                                                # 1
        require_active(catalog(conn, scope, catalog_id, lock='share'))           # 3
        prior = conn.execute('SELECT receipt FROM publications WHERE catalog_id = %s AND request_id = %s',
                             (catalog_id, request_id)).fetchone()
        if prior is not None:
            return dict(prior['receipt'])
        epoch = conn.execute('UPDATE catalog_tombstones SET epoch = epoch + 1 WHERE catalog_id = %s RETURNING epoch',
                             (catalog_id,)).fetchone()['epoch']                  # 5 (update)
        publication_id = uuid.uuid4()
        conn.execute(
            '''INSERT INTO publications(org_id, catalog_id, id, request_id, request_digest, kind, job_id, fence)
               VALUES (%s, %s, %s, %s, %s, 'purge', %s, %s)''',
            (scope.org_id, catalog_id, publication_id, request_id, request_id, lease.job_id, lease.fence))
        purged = 0
        for kind, key, revision in identities:
            row = conn.execute(
                '''INSERT INTO fact_tombstones(org_id, catalog_id, kind, key, revision, epoch, publication_id)
                   SELECT %s, %s, %s, %s, %s, %s, %s
                   WHERE EXISTS (SELECT 1 FROM fact_index WHERE catalog_id = %s AND kind = %s AND key = %s AND revision = %s)
                   ON CONFLICT DO NOTHING RETURNING 1''',
                (scope.org_id, catalog_id, kind, bytes.fromhex(key), revision, epoch, publication_id,
                 catalog_id, kind, bytes.fromhex(key), revision)).fetchone()
            purged += row is not None
        head = conn.execute('SELECT head FROM catalog_heads WHERE catalog_id = %s FOR UPDATE',
                            (catalog_id,)).fetchone()['head']                    # 7
        receipt = {'publication_id': str(publication_id), 'sequence': head + 1, 'tombstone_epoch': epoch,
                   'purged': purged, 'reason': reason}
        conn.execute('UPDATE catalog_heads SET head = %s WHERE catalog_id = %s', (head + 1, catalog_id))
        conn.execute('UPDATE publications SET sequence = %s, receipt = %s, committed_at = clock_timestamp() WHERE id = %s',
                     (head + 1, Jsonb(receipt), publication_id))
        return receipt


def compact(db, store, scope, lease, catalog_id, object_ids):
    """Merge observation objects into one, excluding purged facts. Returns the new object id."""
    object_ids = sorted(set(object_ids), key=str)
    read_pin = pin_catalog(db, scope, catalog_id, lease=lease)
    try:
        with db.connect() as conn:
            objects = conn.execute(
                'SELECT id, codec, state FROM objects WHERE org_id = %s AND catalog_id = %s AND id = ANY(%s)',
                (scope.org_id, catalog_id, object_ids)).fetchall()
        if len(objects) != len(object_ids) or any(o['codec'] not in codecs.COMPACTABLE or o['state'] != 'active'
                                                   for o in objects):
            raise PlatformError('Only active columnar observation objects can be compacted.', 'not_compactable')
        locators = resolve(db, read_pin, object_ids=object_ids, require_complete=False, access='maintenance')
        records, moves = [], []
        for locator, record in read(store, locators):
            codecs.verify_record(record, key=locator.key, fact_digest=locator.fact_digest)
            moves.append((locator.kind, locator.key, locator.revision, locator.object_id, len(records)))
            records.append(record)
        data, _rows = codecs.encode_observations(records)
        new = stage_object(db, store, lease, data, catalog_id=catalog_id, codec=codecs.OBSERVATIONS,
                           records=len(records))
        if new.reused:
            raise PlatformError('Compaction produced an existing object; nothing to do.', 'compaction_noop')
        with db.transaction() as conn:
            assert_fence(conn, lease)                                            # 1
            require_active(catalog(conn, scope, catalog_id, lock='share'))       # 3
            locked = conn.execute(                                               # 4 (sorted)
                'SELECT id, state FROM objects WHERE org_id = %s AND id = ANY(%s) ORDER BY id FOR UPDATE',
                (scope.org_id, sorted(object_ids + [new.id], key=str))).fetchall()
            states = {r['id']: r['state'] for r in locked}
            if any(states[o] != 'active' for o in object_ids) or states[new.id] != 'pending':
                raise PlatformError('Objects changed during compaction.', 'compaction_conflict')
            # The full set of live (unpurged) facts on the old objects must be exactly what was read.
            current = conn.execute(
                '''SELECT count(*) AS n FROM fact_index f WHERE f.catalog_id = %s AND f.object_id = ANY(%s)
                   AND NOT EXISTS (SELECT 1 FROM fact_tombstones t WHERE t.catalog_id = f.catalog_id
                                   AND t.kind = f.kind AND t.key = f.key AND t.revision = f.revision)''',
                (catalog_id, object_ids)).fetchone()['n']
            if current != len(moves):
                raise PlatformError('Facts changed during compaction.', 'compaction_conflict')
            mepoch = conn.execute(                                               # 6
                'UPDATE catalog_maintenance SET epoch = epoch + 1 WHERE catalog_id = %s RETURNING epoch',
                (catalog_id,)).fetchone()['epoch']
            conn.execute("UPDATE objects SET state = 'active', activated_at = clock_timestamp() WHERE id = %s", (new.id,))
            conn.execute('CREATE TEMP TABLE _moves (kind text, key bytea, revision text, old uuid, row bigint) ON COMMIT DROP')
            with conn.cursor().copy('COPY _moves (kind, key, revision, old, row) FROM STDIN') as copy:
                for kind, key, revision, old, row in moves:
                    copy.write_row((kind, bytes.fromhex(key), revision, old, row))
            moved = conn.execute(
                '''UPDATE fact_index f SET object_id = %s, locator_kind = 'row', loc_a = m.row, loc_b = 0,
                       compaction_generation = f.compaction_generation + 1
                   FROM _moves m WHERE f.catalog_id = %s AND f.kind = m.kind AND f.key = m.key
                   AND f.revision = m.revision AND f.object_id = m.old''', (new.id, catalog_id)).rowcount
            if moved != len(moves):
                raise PlatformError('Fact locators changed during compaction.', 'compaction_conflict')
            conn.execute(
                '''UPDATE objects SET state = 'tombstoned', tombstoned_at = clock_timestamp(), tombstone_mepoch = %s
                   WHERE org_id = %s AND id = ANY(%s)''', (mepoch, scope.org_id, object_ids))
        return new.id
    finally:
        release(db, read_pin)


def tombstone_objects(db, scope, lease, catalog_id, object_ids):
    """Tombstone objects that no live fact references (for example expired raw batches)."""
    object_ids = sorted(set(object_ids), key=str)
    with db.transaction() as conn:
        assert_fence(conn, lease)
        require_active(catalog(conn, scope, catalog_id, lock='share'))
        rows = conn.execute('SELECT id, state FROM objects WHERE org_id = %s AND id = ANY(%s) ORDER BY id FOR UPDATE',
                            (scope.org_id, object_ids)).fetchall()
        if any(r['state'] != 'active' for r in rows) or len(rows) != len(object_ids):
            raise PlatformError('Only active objects can be tombstoned.', 'object_unavailable')
        referenced = conn.execute(
            '''SELECT 1 FROM fact_index f WHERE f.catalog_id = %s AND f.object_id = ANY(%s)
               AND NOT EXISTS (SELECT 1 FROM fact_tombstones t WHERE t.catalog_id = f.catalog_id AND t.kind = f.kind
                               AND t.key = f.key AND t.revision = f.revision) LIMIT 1''',
            (catalog_id, object_ids)).fetchone()
        if referenced:
            raise PlatformError('Objects still hold live facts; compact them first.', 'object_referenced')
        mepoch = conn.execute('UPDATE catalog_maintenance SET epoch = epoch + 1 WHERE catalog_id = %s RETURNING epoch',
                              (catalog_id,)).fetchone()['epoch']
        conn.execute(
            '''UPDATE objects SET state = 'tombstoned', tombstoned_at = clock_timestamp(), tombstone_mepoch = %s,
                   retained_for_recovery = false WHERE org_id = %s AND id = ANY(%s)''',
            (mepoch, scope.org_id, object_ids))
        return mepoch
