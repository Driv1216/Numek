"""Verified, pinned evidence reads.

Protocol:

1. ``pin`` commits a read pin recording K (the visible prefix), the tombstone
   epoch (deletion serialization) and the maintenance epoch floor (object
   reclamation safety). It commits *before* any locator is resolved.
2. ``resolve`` returns locators for facts with publication sequence <= K in a
   single REPEATABLE READ transaction, so a concurrent compaction is seen
   entirely or not at all. Selected purged facts refuse (v2 semantics) unless
   the caller explicitly accepts an incomplete selection.
3. ``read`` loads each object, hashes exactly the consumed bytes, then decodes.
4. ``release`` ends protection.

Garbage collection never reclaims an object tombstoned at maintenance epoch m
while a live pin on that catalog has floor < m, so every locator a reader can
hold stays readable.
"""
import uuid
from dataclasses import dataclass

from ..errors import PlatformError
from . import codecs
from .catalogs import catalog, require_active

# Outcome-bearing kinds: readable only through an evidence-use reservation
# (``numek_platform.governance.reader``). Raw projected rows carry outcome columns.
PROTECTED_KINDS = ('outcome', 'raw')
ACCESS = ('plain', 'governed', 'maintenance')
_RESERVE_ROW = '''EXISTS (SELECT 1 FROM entity_registry e WHERE e.catalog_id = f.catalog_id
                  AND e.unit_hash = f.entity_hash AND e.reserve_state = 'reserve')'''


@dataclass(frozen=True)
class ReadPin:
    id: uuid.UUID
    org_id: uuid.UUID
    catalog_id: uuid.UUID
    k: int
    tombstone_epoch: int
    maintenance_epoch: int


@dataclass(frozen=True)
class Locator:
    kind: str
    key: str
    revision: str
    fact_digest: str
    predecessor: str | None
    sequence: int
    object_id: uuid.UUID
    physical_key: str
    sha256: str
    bytes: int
    codec: str
    locator_kind: str
    loc_a: int
    loc_b: int
    event_hash: str | None = None
    entity_hash: str | None = None
    protected: bool = False


def pin(db, scope, catalog_id, *, lease=None, holder=None, ttl_seconds=3600, k=None, allow_migrating=False):
    """Commit a read pin. Job readers bind to their fence; others to a holder + expiry."""
    if (lease is None) == (holder is None):
        raise ValueError('Exactly one of lease or holder is required.')
    with db.transaction() as conn:
        require_active(catalog(conn, scope, catalog_id), allow_migrating=allow_migrating)
        head = conn.execute('SELECT head FROM catalog_heads WHERE catalog_id = %s', (catalog_id,)).fetchone()['head']
        if k is None:
            k = head
        elif not 0 <= k <= head:
            raise PlatformError('Future catalog snapshot is unavailable.', 'catalog_snapshot')
        tombstone = conn.execute('SELECT epoch FROM catalog_tombstones WHERE catalog_id = %s', (catalog_id,)).fetchone()['epoch']
        maintenance = conn.execute('SELECT epoch FROM catalog_maintenance WHERE catalog_id = %s', (catalog_id,)).fetchone()['epoch']
        pin_id = uuid.uuid4()
        if lease is not None:
            if lease.org_id != scope.org_id:
                raise PlatformError('Job and scope belong to different organisations.', 'scope_mismatch')
            conn.execute(
                '''INSERT INTO read_pins(org_id, id, catalog_id, job_id, fence, k, tombstone_epoch, maintenance_epoch)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s)''',
                (scope.org_id, pin_id, catalog_id, lease.job_id, lease.fence, k, tombstone, maintenance))
        else:
            conn.execute(
                '''INSERT INTO read_pins(org_id, id, catalog_id, holder, expires_at, k, tombstone_epoch, maintenance_epoch)
                   VALUES (%s, %s, %s, %s, now() + make_interval(secs => %s), %s, %s, %s)''',
                (scope.org_id, pin_id, catalog_id, holder, ttl_seconds, k, tombstone, maintenance))
    return ReadPin(pin_id, scope.org_id, catalog_id, k, tombstone, maintenance)


def release(db, read_pin):
    with db.transaction() as conn:
        conn.execute('UPDATE read_pins SET released_at = clock_timestamp() WHERE id = %s AND released_at IS NULL',
                     (read_pin.id,))


def resolve(db, read_pin, *, kinds=None, keys=None, opportunity_keys=None, target_keys=None, object_ids=None,
            event_tick_range=None, require_complete=True, limit=None, access='plain', _governance=None,
            fact_digests=None, occurrence_publications=None, namespace=None, order='physical', _count=False, routes=None):
    """Resolve visible fact locators at the pin's K (one REPEATABLE READ snapshot).

    ``routes`` selects facts by partition route (migration 0014): predictions and context by their opportunity's
    key, every other kind by its own key. It is read as one index probe per route within that route's partition,
    so its cost follows the routes asked for, not the history held.

    ``_count=True`` (maintenance only) returns how many locators the same call would return, applying the
    same completeness and availability refusals, without building them.

    ``access='plain'`` never returns protected (outcome-bearing) facts: an
    explicit kind request that would include one refuses with
    ``reservation_required``; listing mode (no kinds) leaves them out. It also
    leaves out rows of sealed-reserve entities. Governed access is reached only through
    ``numek_platform.governance.reader.resolve``. ``access='maintenance'``
    (compaction) moves bytes without exposing values to analysis.
    """
    if access not in ACCESS or (access == 'governed') != (_governance is not None) or (_count and access != 'maintenance'):
        raise PlatformError('Invalid evidence access mode.', 'invalid_access')
    where = ['f.catalog_id = %s', 'p.sequence IS NOT NULL', 'p.sequence <= %s']
    params = [read_pin.catalog_id, read_pin.k]
    if kinds is not None:
        if access == 'plain' and set(kinds) & set(PROTECTED_KINDS):
            raise PlatformError('Outcome-bearing evidence requires an evidence-use reservation.', 'reservation_required')
        where.append('f.kind = ANY(%s)')
        params.append(list(kinds))
    if access == 'plain':
        # Listing mode (no kinds) leaves protected facts out. An explicit kind
        # request that would include protected facts refuses below instead of
        # silently handing an analysis a partial population.
        if kinds is None:
            where.append('NOT f.protected')
        where.append(f'NOT {_RESERVE_ROW}')
    if fact_digests is not None:
        where.append('f.fact_digest = ANY(%s)')
        params.append([bytes.fromhex(v) for v in fact_digests])
    if namespace is not None:
        where.append('f.namespace = %s')
        params.append(namespace)
    if occurrence_publications is not None:
        where.append('''EXISTS (SELECT 1 FROM fact_occurrences oc JOIN publications op ON op.id = oc.publication_id
                        WHERE oc.catalog_id = f.catalog_id AND oc.kind = f.kind AND oc.key = f.key
                        AND oc.revision = f.revision AND oc.publication_id = ANY(%s) AND op.sequence <= %s)''')
        params.extend([list(occurrence_publications), read_pin.k])
    for column, values in (('key', keys), ('opportunity_key', opportunity_keys), ('target_key', target_keys)):
        if values is not None:
            where.append(f'f.{column} = ANY(%s)')
            params.append([bytes.fromhex(v) for v in values])
    if object_ids is not None:
        where.append('f.object_id = ANY(%s)')
        params.append(list(object_ids))
    if event_tick_range is not None:
        lower, upper = event_tick_range
        where.append('f.event_tick >= %s AND f.event_tick < %s')
        params.extend([lower, upper])
    source, source_params = 'fact_index f', []
    if routes is not None:
        # A LATERAL probe per route: the plan must start from the routes, each probe an index scan on
        # (catalog_id, kind, route) pruned at run time to its route's partition. OFFSET 0 keeps the subquery from
        # being flattened into a join the planner could drive from the whole index, so the probe's own
        # conditions are written inside it. Distinct routes: the probe never repeats a fact.
        if kinds is None:
            raise PlatformError('A read by route names its kinds.', 'invalid_access')
        source = ('unnest(%s::bytea[]) AS rq(route) CROSS JOIN LATERAL '
                  '(SELECT f0.* FROM fact_index f0 WHERE f0.catalog_id = %s AND f0.kind = ANY(%s) '
                  'AND f0.route = rq.route OFFSET 0) f')
        source_params = [sorted({bytes.fromhex(v) for v in routes}), read_pin.catalog_id, list(kinds)]
    with db.transaction('repeatable_read', read_only=access != 'governed') as conn:
        if _governance is not None:
            extra, extra_params = _governance(conn)
            where.append(extra)
            params.extend(extra_params)
        clause = ' AND '.join(where)
        params = source_params + params
        # Total, deterministic orders. Physical order equals catalog v2's (object id, offset,
        # length): platform object ids are the v2 ids, and UUID order is their hex order.
        tail = (' ORDER BY o.id, f.loc_a, f.loc_b, f.kind, f.key, f.revision' if order == 'physical' else
                ' ORDER BY p.sequence, o.created_at, o.id, f.loc_a, f.loc_b, f.kind, f.key, f.revision') \
            + (' LIMIT %s' if limit else '')
        if limit:
            params.append(limit)
        if require_complete:
            purged = conn.execute(
                f'''SELECT 1 FROM {source} JOIN publications p ON p.id = f.publication_id
                    JOIN fact_tombstones t ON t.catalog_id = f.catalog_id AND t.kind = f.kind AND t.key = f.key
                         AND t.revision = f.revision
                    WHERE {clause} LIMIT 1''', params[:len(params) - (1 if limit else 0)]).fetchone()
            if purged:
                raise PlatformError('Selected historical evidence was deleted or is unavailable; choose an intact '
                                    'explicit population.', 'historical_evidence_unavailable')
        if _count:
            # Same visibility and availability rules as the row query, without materializing locators.
            total = conn.execute(
                f'''SELECT count(*) AS n, coalesce(bool_or(o.state NOT IN ('active', 'tombstoned')), false) AS unavailable
                    FROM {source} JOIN publications p ON p.id = f.publication_id
                    JOIN objects o ON o.id = f.object_id
                    WHERE {clause} AND NOT EXISTS (SELECT 1 FROM fact_tombstones t WHERE t.catalog_id = f.catalog_id
                          AND t.kind = f.kind AND t.key = f.key AND t.revision = f.revision)''',
                params[:len(params) - (1 if limit else 0)]).fetchone()
            if total['unavailable']:
                raise PlatformError('Selected evidence object is unavailable.', 'historical_evidence_unavailable')
            return min(total['n'], limit) if limit else total['n']
        rows = conn.execute(
            f'''SELECT f.kind, f.key, f.revision, f.fact_digest, f.predecessor, p.sequence, f.object_id,
                       o.physical_key, o.sha256, o.bytes, o.codec, o.state AS object_state,
                       f.locator_kind, f.loc_a, f.loc_b, f.event_hash, f.entity_hash, f.protected
                FROM {source} JOIN publications p ON p.id = f.publication_id
                JOIN objects o ON o.id = f.object_id
                WHERE {clause} AND NOT EXISTS (SELECT 1 FROM fact_tombstones t WHERE t.catalog_id = f.catalog_id
                      AND t.kind = f.kind AND t.key = f.key AND t.revision = f.revision){tail}''', params).fetchall()
    if access == 'plain' and any(r['protected'] for r in rows):
        raise PlatformError('This selection includes outcome-bearing evidence; reserve it first.', 'reservation_required')
    out = []
    for r in rows:
        if r['object_state'] not in ('active', 'tombstoned'):
            raise PlatformError('Selected evidence object is unavailable.', 'historical_evidence_unavailable')
        out.append(Locator(r['kind'], bytes(r['key']).hex(), r['revision'], bytes(r['fact_digest']).hex(),
                           None if r['predecessor'] is None else bytes(r['predecessor']).hex(), r['sequence'],
                           r['object_id'], r['physical_key'], bytes(r['sha256']).hex(), r['bytes'], r['codec'],
                           r['locator_kind'], r['loc_a'], r['loc_b'],
                           None if r['event_hash'] is None else bytes(r['event_hash']).hex(),
                           None if r['entity_hash'] is None else bytes(r['entity_hash']).hex(), r['protected']))
    return out


def keys_in_event_range(db, read_pin, *, kind, lower, upper, namespace=None):
    """Keys with *any* revision of ``kind`` whose event tick lies in ``[lower, upper)`` at the pin's K.

    Index-only (no fact values are read). Event time is a non-identity attribute, so a correction that
    moves an opportunity in or out of the window keeps its key: taking every key with any revision in
    range, then loading complete revision chains, is a superset of the window's selection (plan H.2).
    """
    where = ['f.catalog_id = %s', 'f.kind = %s', 'p.sequence IS NOT NULL', 'p.sequence <= %s',
             'f.event_tick >= %s', 'f.event_tick < %s']
    params = [read_pin.catalog_id, kind, read_pin.k, lower, upper]
    if namespace is not None:
        where.append('f.namespace = %s')
        params.append(namespace)
    with db.transaction('repeatable_read', read_only=True) as conn:
        rows = conn.execute(f'''SELECT DISTINCT f.key FROM fact_index f JOIN publications p ON p.id = f.publication_id
                                WHERE {' AND '.join(where)} ORDER BY f.key''', params).fetchall()
    return [bytes(r['key']).hex() for r in rows]


def read(store, locators, *, max_record_bytes=8 * 1024**2):
    """Yield (locator, record) pairs, verifying each object over the bytes consumed."""
    by_object = {}
    for locator in locators:
        by_object.setdefault(locator.object_id, []).append(locator)
    for group in by_object.values():
        first = group[0]
        data = store.read_verified(first.physical_key, first.sha256, first.bytes)
        records = codecs.decode(first.codec, data,
                                [(l.locator_kind, l.loc_a, l.loc_b, l.key, l.fact_digest) for l in group],
                                max_record_bytes=max_record_bytes)
        yield from zip(group, records)
