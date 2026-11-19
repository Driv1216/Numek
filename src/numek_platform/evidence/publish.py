"""Evidence publication: the platform's commit protocol.

Write protocol for one job attempt (lease = job id + fence):

W1  bytes -> ``staging/<job>.<fence>/`` (fsync, hash)          ``stage_object``
W2  short txn: fence check, ``INSERT objects(state='pending')``
W3  rename into the permanent physical key (fsync dir)
W4  ``publish``: one transaction, locks in the global order
      job (fence) -> [exposure lock] -> catalog (share) -> objects (sorted)
      -> catalog_tombstones (share) -> catalog_heads (update, last)
    activates this attempt's pending objects, inserts global fact identities,
    checks the reader's deletion epoch, and assigns K = head + 1 last.

Because K is assigned under the head-row lock held until commit, K order is
commit order: a reader that sees head = K sees every publication <= K.
"""
import hashlib
import uuid
from dataclasses import dataclass, field

import psycopg
from psycopg.types.json import Jsonb

from ..errors import PlatformError
from ..execution.jobs import assert_fence
from .catalogs import catalog, require_active

ON_CONFLICT = ('refuse', 'quarantine')


@dataclass(frozen=True)
class ObjectRef:
    id: uuid.UUID
    sha256: str
    generation: int
    physical_key: str
    codec: str
    bytes: int
    reused: bool = False


@dataclass
class FactRow:
    kind: str
    key: str                      # hex sha256 of the canonical identity
    revision: str
    fact_digest: str              # hex
    object_id: uuid.UUID
    locator_kind: str             # 'byte_range' | 'row' | 'object'
    loc_a: int
    loc_b: int
    predecessor: str | None = None
    opportunity_key: str | None = None
    target_key: str | None = None
    entity_hash: str | None = None    # governance unit hash: digest([namespace, entity or event])
    event_hash: str | None = None     # governance event hash: digest([namespace, event])
    event_tick: int | None = None
    available_tick: int | None = None


@dataclass
class Receipt:
    publication_id: uuid.UUID
    catalog_id: uuid.UUID
    sequence: int
    new_facts: int
    duplicate_occurrences: int
    conflicts: list = field(default_factory=list)
    replayed: bool = False

    def to_dict(self):
        return {'publication_id': str(self.publication_id), 'catalog_id': str(self.catalog_id),
                'sequence': self.sequence, 'new_facts': self.new_facts,
                'duplicate_occurrences': self.duplicate_occurrences, 'conflicts': self.conflicts}


def _b(hex_value):
    return None if hex_value is None else bytes.fromhex(hex_value)


# W1-W3 ------------------------------------------------------------------------

def stage_object(db, store, lease, data, *, catalog_id, codec, records=0, key_id=None,
                 retained_for_recovery=False):
    """Stage one immutable object for this attempt; dedupe against active objects."""
    staged = store.write_staged(lease.job_id, lease.fence, data)
    sha = bytes.fromhex(staged.sha256)
    from ..scope import OrgScope
    with db.transaction() as conn:
        assert_fence(conn, lease)
        require_active(catalog(conn, OrgScope(lease.org_id), catalog_id, lock='share'), allow_migrating=True)
        # Serialize generation allocation for identical bytes.
        conn.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))', (f'object:{lease.org_id}:{staged.sha256}',))
        existing = conn.execute(
            '''SELECT id, generation, physical_key, codec, bytes FROM objects
               WHERE org_id = %s AND sha256 = %s AND state = 'active' AND catalog_id = %s
                     AND codec = %s AND key_id IS NOT DISTINCT FROM %s
               ORDER BY generation DESC LIMIT 1''',
            (lease.org_id, sha, catalog_id, codec, key_id)).fetchone()
        if existing is not None:
            staged.path.unlink()
            return ObjectRef(existing['id'], staged.sha256, existing['generation'], existing['physical_key'],
                             existing['codec'], existing['bytes'], reused=True)
        generation = conn.execute('SELECT coalesce(max(generation) + 1, 0) AS g FROM objects WHERE org_id = %s AND sha256 = %s',
                                  (lease.org_id, sha)).fetchone()['g']
        object_id = uuid.uuid4()
        key = store.physical_key(lease.org_id, staged.sha256, generation)
        conn.execute(
            '''INSERT INTO objects(org_id, id, catalog_id, sha256, generation, physical_key, codec, bytes, records,
                                   key_id, retained_for_recovery, state, job_id, fence)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'pending', %s, %s)''',
            (lease.org_id, object_id, catalog_id, sha, generation, key, codec, staged.bytes, records, key_id,
             retained_for_recovery, lease.job_id, lease.fence))
    store.promote(staged, key)
    return ObjectRef(object_id, staged.sha256, generation, key, codec, staged.bytes)


# W4 ---------------------------------------------------------------------------

def _existing_receipt(conn, catalog_id, request_id, request_digest):
    row = conn.execute('SELECT request_digest, receipt FROM publications WHERE catalog_id = %s AND request_id = %s',
                       (catalog_id, request_id)).fetchone()
    if row is None:
        return None
    if row['request_digest'] != request_digest:
        raise PlatformError('This request id was already used for different content.', 'idempotency_conflict')
    receipt = dict(row['receipt'])
    return Receipt(uuid.UUID(receipt['publication_id']), uuid.UUID(receipt['catalog_id']), receipt['sequence'],
                   receipt['new_facts'], receipt['duplicate_occurrences'], receipt.get('conflicts', []), replayed=True)


def publish(db, scope, lease, catalog_id, *, request_id, request_digest, kind, objects=(), facts=(),
            pin=None, on_conflict='refuse', allow_migrating=False, exposure_lock=False,
            before_head=None, after_head=None, receipt_extra=None, reservations=()):
    """Atomically publish facts and objects as one catalog sequence step.

    ``before_head(conn, publication_id)`` and ``after_head(conn, publication_id, K)``
    let callers add rows (measurements, incident updates) inside the same
    transaction. ``reservations`` are evidence-use reservations this attempt
    made before reading; they become ``consumed`` atomically with the result,
    so a result can never exist without its evidence-use records. Raises on
    stale fences, conflicts (when refusing), forks, purged identities or
    deletion of evidence the caller read.
    """
    if on_conflict not in ON_CONFLICT:
        raise ValueError(on_conflict)
    if lease.org_id != scope.org_id:
        raise PlatformError('Job and scope belong to different organisations.', 'scope_mismatch')
    for attempt in range(3):
        try:
            return _publish_once(db, scope, lease, catalog_id, request_id, request_digest, kind, list(objects),
                                 list(facts), pin, on_conflict, allow_migrating, exposure_lock or bool(reservations),
                                 before_head, after_head, receipt_extra, list(reservations))
        except psycopg.errors.UniqueViolation as exc:
            constraint = getattr(exc.diag, 'constraint_name', '') or ''
            if 'request_id' in constraint and attempt < 2:
                continue  # a concurrent duplicate committed first; re-read its receipt
            if 'no_fork' in constraint or 'predecessor' in constraint:
                raise PlatformError('A competing correction head already exists.', 'correction_fork') from exc
            raise


def _publish_once(db, scope, lease, catalog_id, request_id, request_digest, kind, objects, facts, pin,
                  on_conflict, allow_migrating, exposure_lock, before_head, after_head, receipt_extra, reservations):
    with db.transaction() as conn:
        assert_fence(conn, lease)                                           # 1 job
        previous = _existing_receipt(conn, catalog_id, request_id, request_digest)
        if previous is not None:
            return previous
        if exposure_lock:                                                    # 2 exposure
            conn.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))", (f'exposure:{catalog_id}',))
        require_active(catalog(conn, scope, catalog_id, lock='share'), allow_migrating=allow_migrating)  # 3

        object_ids = sorted({o.id for o in objects} | {f.object_id for f in facts}, key=str)
        if object_ids:                                                       # 4 objects, sorted
            rows = {r['id']: r for r in conn.execute(
                '''SELECT id, state, job_id, fence, catalog_id FROM objects
                   WHERE org_id = %s AND id = ANY(%s) ORDER BY id FOR UPDATE''',
                (scope.org_id, object_ids)).fetchall()}
            pending = []
            for oid in object_ids:
                row = rows.get(oid)
                if row is None or row['catalog_id'] != catalog_id:
                    raise PlatformError('Referenced evidence object is unknown.', 'unknown_object')
                if row['state'] == 'pending':
                    if row['job_id'] != lease.job_id or row['fence'] != lease.fence:
                        raise PlatformError('Staged object belongs to another attempt.', 'object_owner')
                    pending.append(oid)
                elif row['state'] != 'active':
                    raise PlatformError('Referenced evidence object is no longer available.', 'object_unavailable')
            if pending:
                conn.execute("UPDATE objects SET state = 'active', activated_at = clock_timestamp() WHERE org_id = %s AND id = ANY(%s)",
                             (scope.org_id, pending))
        if reservations:                                                     # governance rows (exposure lock held)
            from ..governance.ledger import consume
            consume(conn, scope, lease, catalog_id, reservations)

        tombstone_epoch = conn.execute(                                       # 5 tombstones (share)
            'SELECT epoch FROM catalog_tombstones WHERE catalog_id = %s FOR SHARE', (catalog_id,)).fetchone()['epoch']
        if pin is not None:
            _check_deletion_since_pin(conn, catalog_id, pin, tombstone_epoch)

        publication_id = uuid.uuid4()
        conn.execute(
            '''INSERT INTO publications(org_id, catalog_id, id, request_id, request_digest, kind, job_id, fence)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s)''',
            (scope.org_id, catalog_id, publication_id, request_id, request_digest, kind, lease.job_id, lease.fence))
        new, duplicates, conflicts = _insert_facts(conn, scope, catalog_id, publication_id, facts)
        if conflicts and on_conflict == 'refuse':
            raise PlatformError('Conflicting evidence for an existing identity was refused.', 'fact_conflict')
        if before_head:
            before_head(conn, publication_id)

        head = conn.execute(                                                  # 7 head (last)
            'SELECT head FROM catalog_heads WHERE catalog_id = %s FOR UPDATE', (catalog_id,)).fetchone()['head']
        sequence = head + 1
        conn.execute('UPDATE catalog_heads SET head = %s WHERE catalog_id = %s', (sequence, catalog_id))
        receipt = Receipt(publication_id, catalog_id, sequence, new, duplicates, conflicts)
        stored = receipt.to_dict() | (receipt_extra or {})
        conn.execute('UPDATE publications SET sequence = %s, receipt = %s, committed_at = clock_timestamp() WHERE id = %s',
                     (sequence, Jsonb(stored), publication_id))
        if after_head:
            after_head(conn, publication_id, sequence)
        return receipt


def _check_deletion_since_pin(conn, catalog_id, pin, tombstone_epoch):
    """Abort when evidence visible to the reader was purged after it pinned."""
    if pin.catalog_id != catalog_id:
        raise PlatformError('Read pin belongs to another catalog.', 'pin_mismatch')
    if tombstone_epoch == pin.tombstone_epoch:
        return
    purged = conn.execute(
        '''SELECT 1 FROM fact_tombstones t
           JOIN fact_index f ON f.catalog_id = t.catalog_id AND f.kind = t.kind AND f.key = t.key AND f.revision = t.revision
           JOIN publications p ON p.id = f.publication_id
           WHERE t.catalog_id = %s AND t.epoch > %s AND p.sequence <= %s LIMIT 1''',
        (catalog_id, pin.tombstone_epoch, pin.k)).fetchone()
    if purged:
        raise PlatformError('Evidence used by this analysis was deleted before publication.',
                            'evidence_deleted_during_analysis')


_COLUMNS = ('kind', 'key', 'revision', 'fact_digest', 'predecessor', 'object_id', 'locator_kind', 'loc_a', 'loc_b',
            'opportunity_key', 'target_key', 'entity_hash', 'event_hash', 'event_tick', 'available_tick')


def _insert_facts(conn, scope, catalog_id, publication_id, facts):
    if not facts:
        return 0, 0, []
    # Within-batch identity: identical repeats count once. Differing digests for
    # one identity are ambiguous, so neither variant is published.
    conflicts, seen, ambiguous = [], {}, set()
    for fact in facts:
        identity = (fact.kind, fact.key, fact.revision)
        prior = seen.setdefault(identity, fact)
        if prior.fact_digest != fact.fact_digest:
            ambiguous.add(identity)
    for kind, key, revision in sorted(ambiguous):
        conflicts.append({'kind': kind, 'key': key, 'revision': revision, 'reason': 'batch_conflict'})
    unique = [f for identity, f in seen.items() if identity not in ambiguous]
    if not unique:
        return 0, 0, conflicts
    conn.execute(
        '''CREATE TEMP TABLE _facts (kind text, key bytea, revision text, fact_digest bytea, predecessor bytea,
               object_id uuid, locator_kind text, loc_a bigint, loc_b bigint, opportunity_key bytea, target_key bytea,
               entity_hash bytea, event_hash bytea, event_tick numeric, available_tick numeric) ON COMMIT DROP''')
    with conn.cursor().copy(f'COPY _facts ({", ".join(_COLUMNS)}) FROM STDIN') as copy:
        for f in unique:
            copy.write_row((f.kind, _b(f.key), f.revision, _b(f.fact_digest), _b(f.predecessor), f.object_id,
                            f.locator_kind, f.loc_a, f.loc_b, _b(f.opportunity_key), _b(f.target_key),
                            _b(f.entity_hash), _b(f.event_hash), f.event_tick, f.available_tick))

    # Predecessors must already exist on the same identity chain (or in this batch) and not be purged.
    missing = conn.execute(
        '''SELECT n.kind, n.key, n.revision FROM _facts n
           WHERE n.predecessor IS NOT NULL
             AND NOT EXISTS (SELECT 1 FROM _facts b WHERE b.kind = n.kind AND b.key = n.key AND b.fact_digest = n.predecessor)
             AND NOT EXISTS (SELECT 1 FROM fact_index f WHERE f.catalog_id = %s AND f.kind = n.kind AND f.key = n.key
                             AND f.fact_digest = n.predecessor
                             AND NOT EXISTS (SELECT 1 FROM fact_tombstones t WHERE t.catalog_id = f.catalog_id
                                             AND t.kind = f.kind AND t.key = f.key AND t.revision = f.revision))
           LIMIT 1''', (catalog_id,)).fetchone()
    if missing:
        raise PlatformError('Correction predecessor is unavailable.', 'correction_predecessor')

    inserted = conn.execute(
        f'''INSERT INTO fact_index(org_id, catalog_id, publication_id, {", ".join(_COLUMNS)})
            SELECT %s, %s, %s, {", ".join(_COLUMNS)} FROM _facts
            ON CONFLICT (catalog_id, kind, key, revision) DO NOTHING
            RETURNING kind, key, revision''', (scope.org_id, catalog_id, publication_id)).fetchall()
    inserted_ids = {(r['kind'], bytes(r['key']), r['revision']) for r in inserted}

    existing = conn.execute(
        '''SELECT n.kind, n.key, n.revision, n.fact_digest = f.fact_digest AS same,
                  EXISTS (SELECT 1 FROM fact_tombstones t WHERE t.catalog_id = f.catalog_id AND t.kind = f.kind
                          AND t.key = f.key AND t.revision = f.revision) AS purged
           FROM _facts n JOIN fact_index f ON f.catalog_id = %s AND f.kind = n.kind AND f.key = n.key
                AND f.revision = n.revision AND f.publication_id <> %s''', (catalog_id, publication_id)).fetchall()
    duplicates = 0
    for row in existing:
        identity = (row['kind'], bytes(row['key']), row['revision'])
        if identity in inserted_ids:
            continue
        if row['purged']:
            raise PlatformError('Purged evidence cannot be re-imported under its old identity.', 'historical_evidence_unavailable')
        if row['same']:
            duplicates += 1
        else:
            conflicts.append({'kind': row['kind'], 'key': bytes(row['key']).hex(), 'revision': row['revision'],
                              'reason': 'fact_conflict'})
    conflict_ids = {(c['kind'], c['key'], c['revision']) for c in conflicts}
    conn.execute(
        '''INSERT INTO fact_occurrences(org_id, catalog_id, publication_id, kind, key, revision)
           SELECT %s, %s, %s, kind, key, revision FROM _facts''', (scope.org_id, catalog_id, publication_id))
    if conflict_ids:
        conn.execute(
            'DELETE FROM fact_occurrences WHERE publication_id = %s AND (kind, encode(key, %s), revision) IN (SELECT * FROM unnest(%s::text[], %s::text[], %s::text[]))',
            (publication_id, 'hex', [c[0] for c in conflict_ids], [c[1] for c in conflict_ids], [c[2] for c in conflict_ids]))
    return len(inserted_ids), duplicates, conflicts


def activate_pending(conn, scope, lease, catalog_id, object_ids):
    """Activate this attempt's pending objects outside a K publication (governance records).

    Caller holds the job row (fence) and the exposure lock; locks objects sorted (step 4).
    """
    object_ids = sorted(set(object_ids), key=str)
    rows = conn.execute('SELECT id, state, job_id, fence, catalog_id FROM objects WHERE org_id = %s AND id = ANY(%s) '
                        'ORDER BY id FOR UPDATE', (scope.org_id, object_ids)).fetchall()
    if len(rows) != len(object_ids) or any(r['state'] != 'pending' or r['job_id'] != lease.job_id or r['fence'] != lease.fence
                                           or r['catalog_id'] != catalog_id for r in rows):
        raise PlatformError('Staged object belongs to another attempt.', 'object_owner')
    conn.execute("UPDATE objects SET state = 'active', activated_at = clock_timestamp() WHERE org_id = %s AND id = ANY(%s)",
                 (scope.org_id, object_ids))


def request_digest_of(value):
    """Stable digest for idempotent request bodies."""
    from ..canonical import digest
    return digest(value)


def sha256_hex(data):
    return hashlib.sha256(data).hexdigest()
