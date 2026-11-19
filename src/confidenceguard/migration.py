"""Catalog v2 -> NUMEK platform migration of a ConfidenceGuard workspace (CG7 S3c; plan E.3-E.4, R2.6).

``migrate_workspace(path)`` moves one v1/v2 workspace onto the platform in place:

1. **Plan.** A ``migrating`` platform catalog is created with the v2 analytical
   identity (instance id, branch, continuity, tracking, configuration) and the
   workspace root is bound to it (``platform.json``). Every reader and writer
   refuses a ``migrating`` catalog, and every released v2 runtime refuses the
   source once it is frozen, so nothing can use either side until cutover.
2. **Freeze** (``numek_platform.legacy``): the v2 catalog is locked out durably
   (``user_version = 9002``) and its inventory recorded.
3. **Replay in K order**, one platform transaction per K, resumable from the last
   committed K. Each v2 operation becomes the publication with the *same*
   sequence K, publication id, request id, request digest and receipt; its
   objects keep their ids and bytes (re-verified); its facts keep their kind,
   key, revision, digest and locator; its occurrences, variants, assessments,
   artifact dependencies and vector locations are written in the same
   transaction. A v2 deletion (which consumed a K without an operation row)
   becomes a deletion publication at that K that tombstones its facts. Each v2
   evidence use becomes a durable governance record (legacy) with its v2 id,
   membership (from the v2 ledger's own membership facts), exposure registry,
   confirmation members and study allocation, inside its K's transaction.
4. **Validate** (see :func:`validate`): structural equality of everything above,
   full verify-on-read of every migrated object, byte-equal logical reconstruction
   of every retained fact, equal assessments, deletion previews and evidence-use
   overlap answers, and deterministic re-execution of every retained CG3 analysis.
5. **Cutover**: one transaction (the point of no return) activates the catalog,
   only with a passing report. v2 stays frozen read-only; there is no reverse
   migration.
6. **Post-cutover backup**: required before the migration is reported complete.
   It is available for workspaces with their own P-LOCAL cluster; for a shared
   installation it is the operator's installation procedure (tracked limitation).

Before cutover, ``abandon_workspace`` drops the platform copy and restores v2.
"""
import contextlib
import json
import math
import uuid
from pathlib import Path

from .contracts import EvaluationError, digest, strict_json
import re

MAX_OVERLAP_SAMPLE = 64


def fault(boundary):
    """Test-only crash injection point (monkeypatched by tests)."""


def _translate(exc):
    from .platform_catalog import _translate as translate
    return translate(exc)


# Read-only v2 source ---------------------------------------------------------------------------------------
class Legacy:
    """The frozen v2 source, read through ``LegacyCatalog`` (read-only SQLite) and verified object bytes."""

    def __init__(self, root):
        from .history_storage import LegacyCatalog
        self.root = Path(root)
        self.catalog = LegacyCatalog(root)
        self.settings = self.catalog.settings
        self._bytes_verified = set()

    def query(self, sql, params=()):
        with contextlib.closing(self.catalog._connect()) as db:
            return [dict(r) for r in db.execute(sql, params)]

    @property
    def v2(self):
        return self.catalog.catalog_version >= 2

    def objects(self):
        encoding = 'encoding' if self.v2 else "'utf8_jsonl_v1' AS encoding"
        return self.query(f'SELECT id, operation_id, sha256, bytes, kind, records, state, {encoding} FROM objects ORDER BY id')

    def path(self, obj):
        from .feature_storage import extension
        return self.root / 'objects' / (obj['id'] + extension(obj['encoding']))

    def verified_bytes(self, obj):
        import hashlib
        data = self.path(obj).read_bytes()
        if hashlib.sha256(data).hexdigest() != obj['sha256'] or len(data) != obj['bytes']:
            raise EvaluationError('Legacy evidence changed; migration stopped.', 'evidence_changed')
        self._bytes_verified.add(obj['id'])
        return data

    def record(self, fact, obj, cache):
        if obj['id'] not in self._bytes_verified:
            self.verified_bytes(obj)
        return self.catalog._read_record(self.path(obj), obj['encoding'], fact['offset'], fact['length'], cache)

    def facts(self):
        locator = 'locator_kind' if self.v2 else "'byte_range' AS locator_kind"
        return self.query(f'SELECT id, kind, key, revision, fact_digest, object_id, offset, length, operation_id, {locator} '
                          'FROM facts ORDER BY id')

    def events(self):
        """{K: ('operation', row) | ('deletion', plan)} for K = 1..head."""
        events = {}
        for op in self.query("SELECT * FROM operations WHERE state = 'committed' ORDER BY sequence"):
            events[op['sequence']] = ('operation', op)
        for row in self.query('SELECT id, plan, state FROM deletions'):
            plan = strict_json(row['plan'].encode())
            events[plan['catalog_sequence'] + 1] = ('deletion', plan)
        head = self.settings.get('sequence') or 0
        if sorted(events) != list(range(1, head + 1)):
            raise EvaluationError('Legacy catalog sequence is not contiguous.', 'migration_inventory')
        return events


# Platform side ------------------------------------------------------------------------------------------------
def _platform(root):
    from .platform_catalog import installation
    database, scope, binding = installation(root)
    from numek_platform.objects import LocalObjectStore
    return database, scope, binding, LocalObjectStore(Path(root) / binding['store'])


def _live_migration(db, instance_id):
    with db.connect() as conn:
        return conn.execute("SELECT * FROM legacy_migrations WHERE legacy_instance_id = %s AND state <> 'abandoned'",
                            (instance_id,)).fetchone()


def _prepare_catalog(db, catalog_id, legacy):
    """CG identity on the migrating catalog (idempotent)."""
    from psycopg.types.json import Jsonb
    from .history_storage import CATALOG_VERSION
    s = legacy.settings
    values = {'instance_id': s['instance_id'], 'config': s['config'], 'retired': False, 'schema': CATALOG_VERSION,
              'created_at': s.get('created_at'), 'legacy_catalog_version': legacy.catalog.catalog_version}
    with db.transaction() as conn:
        for key, value in values.items():
            conn.execute('INSERT INTO cg_settings(catalog_id, key, value) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING',
                         (catalog_id, key, Jsonb(value)))
        conn.execute('UPDATE catalogs SET exposure_tracking = %s WHERE id = %s', (bool(s.get('exposure_tracking')), catalog_id))


def _placeholder(db, scope, lease, catalog_id, obj):
    """Object row for v2 bytes a later deletion removed: no bytes exist to copy (reclaimed at that deletion's K)."""
    from numek_platform.evidence.publish import ObjectRef
    from numek_platform.execution.jobs import assert_fence
    object_id = uuid.UUID(obj['id'])
    with db.transaction() as conn:
        assert_fence(conn, lease)
        sha = bytes.fromhex(obj['sha256'])
        conn.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))', (f"object:{scope.org_id}:{obj['sha256']}",))
        generation = conn.execute('SELECT coalesce(max(generation) + 1, 0) AS g FROM objects WHERE org_id = %s AND sha256 = %s',
                                  (scope.org_id, sha)).fetchone()['g']
        key = f"legacy-deleted/{scope.org_id}/{obj['id']}"
        conn.execute('''INSERT INTO objects(org_id, id, catalog_id, sha256, generation, physical_key, codec, bytes, records,
                                            state, job_id, fence)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'pending', %s, %s)''',
                     (scope.org_id, object_id, catalog_id, sha, generation, key, obj['encoding'], obj['bytes'],
                      obj['records'], lease.job_id, lease.fence))
    return ObjectRef(object_id, obj['sha256'], generation, key, obj['encoding'], obj['bytes'])


class _Replay:
    def __init__(self, db, scope, store, legacy, catalog_id, migration_id, lease):
        self.db, self.scope, self.store, self.legacy = db, scope, store, legacy
        self.catalog_id, self.migration_id, self.lease = catalog_id, migration_id, lease
        self.objects = {o['id']: o for o in legacy.objects()}
        self.facts = legacy.facts()
        self.by_id = {f['id']: f for f in self.facts}
        self.stored_in = {}
        for f in self.facts:
            self.stored_in.setdefault(f['operation_id'], []).append(f)
        self.occurrences = {}
        for r in legacy.query('SELECT operation_id, fact_id FROM occurrences'):
            self.occurrences.setdefault(r['operation_id'], []).append(r['fact_id'])
        self.entity_of = {}
        self.rows = {}
        self.cache = {}

    def fact_row(self, fact):
        from numek_platform.evidence.publish import FactRow
        from .platform_catalog import PlatformCatalog
        if fact['id'] in self.rows:
            return self.rows[fact['id']]
        obj = self.objects[fact['object_id']]
        entry = {'kind': fact['kind'], 'key': fact['key'], 'revision': fact['revision']}
        if obj['state'] == 'active':
            record = self.legacy.record(fact, obj, self.cache)
            claimed = record.pop('fact_digest', None)
            if claimed != fact['fact_digest'] or digest(record) != claimed or digest(record['identity']) != fact['key']:
                raise EvaluationError('Legacy record and index identities differ.', 'evidence_changed')
            row = PlatformCatalog._row(None, FactRow, entry, record, claimed, uuid.UUID(obj['id']), fact['locator_kind'],
                                       fact['offset'], fact['length'], self.entity_of)
        else:     # bytes deleted in v2: identity and locator only (never readable again)
            row = FactRow(fact['kind'], fact['key'], fact['revision'], fact['fact_digest'], uuid.UUID(obj['id']),
                          fact['locator_kind'] if fact['locator_kind'] in ('byte_range', 'row', 'object') else 'byte_range',
                          fact['offset'], fact['length'])
        self.rows[fact['id']] = row
        return row

    def uses_of(self, op_id):
        """v2 evidence uses recorded by this operation, with their full membership."""
        if not self.legacy.v2:
            return []
        uses = []
        stored = [f for f in self.stored_in.get(op_id, ()) if f['kind'] == 'evidence_use']
        chunks = sorted((f for f in self.stored_in.get(op_id, ()) if f['kind'] == 'exposure_members'),
                        key=lambda f: f['id'])
        for fact in stored:
            payload = self.legacy.record(fact, self.objects[fact['object_id']], self.cache)['payload']
            events, units = [], []
            for chunk in chunks:
                part = self.legacy.record(chunk, self.objects[chunk['object_id']], self.cache)['payload']
                if part['use_id'] == payload['id']:
                    events.extend(part['events'])
                    units.extend(part['units'])
            uses.append((payload, sorted(set(events)), sorted(set(units))))
        return uses

    def run(self, start, events):
        for k in range(start, max(events, default=0) + 1):
            kind, value = events[k]
            if kind == 'operation':
                self.operation(k, value)
            else:
                self.deletion(k, value)
            fault(f'after_k:{k}')

    def _after_head(self, expected):
        def after_head(conn, _publication_id, k):
            if k != expected:
                raise EvaluationError('Replayed catalog sequence differs from the legacy sequence.', 'migration_sequence')
            conn.execute('UPDATE legacy_migrations SET last_migrated_k = %s, updated_at = now() WHERE id = %s',
                         (k, self.migration_id))
        return after_head

    def operation(self, k, op):
        from psycopg.types.json import Jsonb
        from numek_platform.evidence.publish import publish, stage_object
        from numek_platform.governance.ledger import encode_membership, _register_exposure
        from numek_platform.governance import CONFIRMATION_CLASSES
        legacy = self.legacy
        own = [o for o in self.objects.values() if o['operation_id'] == op['id']]
        refs = []
        for obj in sorted(own, key=lambda o: o['id']):
            if obj['state'] == 'active':
                refs.append(stage_object(self.db, self.store, self.lease, legacy.verified_bytes(obj), catalog_id=self.catalog_id,
                                         codec=obj['encoding'], records=obj['records'], object_id=uuid.UUID(obj['id'])))
            else:
                refs.append(_placeholder(self.db, self.scope, self.lease, self.catalog_id, obj))
        fact_ids = list(dict.fromkeys(self.occurrences.get(op['id'], []) + [f['id'] for f in self.stored_in.get(op['id'], ())]))
        rows = [self.fact_row(self.by_id[i]) for i in fact_ids]
        uses = self.uses_of(op['id'])
        memberships = []
        for payload, events, units in uses:
            memberships.append(stage_object(self.db, self.store, self.lease, encode_membership(events, units),
                                            catalog_id=self.catalog_id, codec='exposure_membership_v1',
                                            records=len(events) + len(units)))
        refs.extend(memberships)
        own_ids = {o['id'] for o in own}
        variants = legacy.query('SELECT id, metadata FROM variants WHERE operation_id = ?', (op['id'],))
        assessments = legacy.query('SELECT * FROM assessments WHERE operation_id = ?', (op['id'],))
        deps = [d for d in legacy.query('SELECT object_id, depends_on FROM artifact_dependencies')
                if d['object_id'] in own_ids] if legacy.v2 else []
        vectors = [v for v in legacy.query('SELECT * FROM vector_locations') if v['object_id'] in own_ids] if legacy.v2 else []
        allocations = {a['reservation_id']: a for a in legacy.query('SELECT * FROM study_allocations')} if legacy.v2 and uses else {}

        def before_head(conn, publication_id):
            for obj in own:
                conn.execute('INSERT INTO cg_objects(catalog_id, object_id, kind, operation_id) VALUES (%s, %s, %s, %s)',
                             (self.catalog_id, uuid.UUID(obj['id']), obj['kind'], publication_id))
            for v in variants:
                conn.execute('INSERT INTO cg_variants(catalog_id, id, metadata, publication_id) VALUES (%s, %s, %s, %s)',
                             (self.catalog_id, v['id'], Jsonb(json.loads(v['metadata'])), publication_id))
            for a in assessments:
                conn.execute('''INSERT INTO cg_assessments(catalog_id, id, object_id, publication_id, digest, predecessor, state)
                                VALUES (%s, %s, %s, %s, %s, %s, %s)''',
                             (self.catalog_id, a['id'], uuid.UUID(a['object_id']), publication_id, a['digest'], a['predecessor'],
                              'deleted' if a['state'] == 'deleted' else 'active'))
            for d in deps:
                conn.execute('INSERT INTO cg_artifact_dependencies(catalog_id, object_id, depends_on) VALUES (%s, %s, %s)',
                             (self.catalog_id, uuid.UUID(d['object_id']), uuid.UUID(d['depends_on'])))
            for v in vectors:
                conn.execute('''INSERT INTO cg_vector_locations(catalog_id, digest, object_id, row_index, dtype, dimensions)
                                VALUES (%s, %s, %s, %s, %s, %s)''',
                             (self.catalog_id, v['digest'], uuid.UUID(v['object_id']), v['row_index'], v['dtype'], v['dimensions']))
            for (payload, events, units), membership in zip(uses, memberships):
                kind = payload['kind']
                metadata = dict(payload.get('metadata') or {})
                metadata.setdefault('purpose', kind)
                metadata['receipt_catalog_sequence'] = k
                conn.execute(
                    '''INSERT INTO evidence_uses(org_id, catalog_id, id, request_id, request_digest, kind, purpose, state,
                           population_digest, family_digest, membership_digest, membership_object, event_count, unit_count,
                           study_id, alpha, total_alpha, branch_id, continuity, continuity_token, metadata, legacy)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, true)''',
                    (self.scope.org_id, self.catalog_id, payload['id'], payload['request_id'], payload['request_digest'], kind,
                     kind, 'reserved' if kind in CONFIRMATION_CLASSES else 'consumed', payload['population_digest'],
                     payload.get('family_digest'), payload['membership_digest'], membership.id, payload['event_count'],
                     payload['unit_count'], payload.get('study_id'), payload.get('alpha'), payload.get('total_alpha'),
                     payload['branch_id'], payload['continuity'], payload.get('continuity_token'), Jsonb(metadata)))
                _register_exposure(conn, self.scope, self.catalog_id, payload['id'], kind, events, units)
                allocation = allocations.get(payload['id'])
                if allocation:
                    conn.execute('INSERT INTO study_allocations(catalog_id, study_id, use_id, alpha, total_alpha) VALUES (%s, %s, %s, %s, %s)',
                                 (self.catalog_id, allocation['study_id'], payload['id'], allocation['alpha'], allocation['total_alpha']))

        receipt = strict_json(op['receipt'].encode()) if op.get('receipt') else {}
        try:
            publish(self.db, self.scope, self.lease, self.catalog_id, request_id=op['request_id'],
                    request_digest=op['request_digest'], kind='cg_capture', objects=refs, facts=rows,
                    before_head=before_head, after_head=self._after_head(k), receipt_extra={'cg': receipt},
                    publication_id=uuid.UUID(op['id']), allow_migrating=True, exposure_lock=bool(uses))
        except Exception as exc:
            raise _translate(exc) from exc

    def deletion(self, k, plan):
        from psycopg.types.json import Jsonb
        from numek_platform.evidence.publish import publish
        objects = [uuid.UUID(o) for o in plan['object_ids']]

        def before_head(conn, publication_id):
            epoch = conn.execute('UPDATE catalog_tombstones SET epoch = epoch + 1 WHERE catalog_id = %s RETURNING epoch',
                                 (self.catalog_id,)).fetchone()['epoch']
            mepoch = conn.execute('UPDATE catalog_maintenance SET epoch = epoch + 1 WHERE catalog_id = %s RETURNING epoch',
                                  (self.catalog_id,)).fetchone()['epoch']
            if objects:
                conn.execute('''INSERT INTO fact_tombstones(org_id, catalog_id, kind, key, revision, epoch, publication_id)
                                SELECT %s, catalog_id, kind, key, revision, %s, %s FROM fact_index
                                WHERE catalog_id = %s AND object_id = ANY(%s) ON CONFLICT DO NOTHING''',
                             (self.scope.org_id, epoch, publication_id, self.catalog_id, objects))
                # v2 already removed these bytes: the rows are reclaimed directly.
                conn.execute('''UPDATE objects SET state = 'reclaimed', tombstoned_at = clock_timestamp(), tombstone_mepoch = %s
                                WHERE catalog_id = %s AND id = ANY(%s)''', (mepoch, self.catalog_id, objects))
            conn.execute("INSERT INTO cg_deletions(catalog_id, id, plan, state) VALUES (%s, %s, %s, 'completed')",
                         (self.catalog_id, plan['id'], Jsonb(plan)))

        try:
            publish(self.db, self.scope, self.lease, self.catalog_id, request_id='deletion:' + plan['id'],
                    request_digest=plan.get('confirmation') or digest(plan), kind='cg_deletion', before_head=before_head,
                    after_head=self._after_head(k), receipt_extra={'cg': {'deletion_id': plan['id']}},
                    publication_id=uuid.uuid5(uuid.NAMESPACE_URL, 'numek:cg-deletion:' + plan['id']), allow_migrating=True)
        except Exception as exc:
            raise _translate(exc) from exc


def _drop_stale_pending(db, store, catalog_id):
    """Objects staged by a migration attempt that died before its K committed."""
    with db.transaction() as conn:
        rows = conn.execute("DELETE FROM objects WHERE catalog_id = %s AND state = 'pending' RETURNING physical_key",
                            (catalog_id,)).fetchall()
    for row in rows:
        if not row['physical_key'].startswith('legacy-deleted/'):
            store.unlink(row['physical_key'])


# Validation ---------------------------------------------------------------------------------------------------
def numbers_equal(a, b):
    """Equality with a tight tolerance for floats (parallel aggregation changes last bits only)."""
    if isinstance(a, bool) or isinstance(b, bool) or not isinstance(a, float) and not isinstance(b, float):
        return a == b
    if not isinstance(a, (int, float)) or not isinstance(b, (int, float)):
        return False
    if math.isnan(a) or math.isnan(b):
        return math.isnan(a) and math.isnan(b)
    return abs(a - b) <= max(1e-12, 1e-9 * max(abs(a), abs(b)))


def differences(a, b, path='', ignore=()):
    """Paths where ``a`` and ``b`` differ (floats with :func:`numbers_equal`), skipping paths matching ``ignore``."""
    if any(pattern.search(path) for pattern in ignore):
        return []
    if isinstance(a, dict) and isinstance(b, dict):
        out = []
        for key in sorted(set(a) | set(b)):
            sub = f'{path}/{key}'
            if any(pattern.search(sub) for pattern in ignore):
                continue
            out.extend([sub] if key not in a or key not in b else differences(a[key], b[key], sub, ignore))
        return out
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            return [path]
        return [d for i, (x, y) in enumerate(zip(a, b)) for d in differences(x, y, f'{path}[{i}]', ignore)]
    return [] if numbers_equal(a, b) else [path]


# Fields a re-execution legitimately recomputes: the result's own identity and timing, the
# platform's read accounting, and population labels v2 derived from an unordered selection
# stream (fixed in CG7 S3). None of them is a measured value, count or eligibility state.
ORDER_DEPENDENT = tuple(re.compile(p) for p in (
    r'^/(analysis_id|generated_at|execution|binding)$',
    r'^/history/materialization$',
    r'^/coverage/populations\[\d+\]/(id|lineage/selected_fact_digest)$',
    r'(^|/)(population_id|precision_population_id|recall_population_id|current_population_id|reference_population_id)$',
    r'effective_cutoff_ns$'))


def validate(root, *, db, scope, catalog_id, legacy):
    """Equivalence report for a fully replayed (still ``migrating``) catalog. ``passed`` gates cutover."""
    checks = {}

    def check(name, failures, detail=None):
        checks[name] = {'passed': not failures, 'failures': failures[:20], 'count': len(failures), **(detail or {})}

    events = legacy.events()
    with db.connect() as conn:
        head = conn.execute('SELECT head FROM catalog_heads WHERE catalog_id = %s', (catalog_id,)).fetchone()['head']
        pubs = {r['sequence']: r for r in conn.execute(
            'SELECT id, sequence, request_id, request_digest, kind, receipt FROM publications WHERE catalog_id = %s', (catalog_id,))}
        facts = {(r['kind'], bytes(r['key']).hex(), r['revision']): r for r in conn.execute(
            'SELECT kind, key, revision, fact_digest, object_id, locator_kind, loc_a, loc_b, publication_id FROM fact_index '
            'WHERE catalog_id = %s', (catalog_id,))}
        occurrences = {(r['publication_id'].hex, r['kind'], bytes(r['key']).hex(), r['revision']) for r in conn.execute(
            'SELECT publication_id, kind, key, revision FROM fact_occurrences WHERE catalog_id = %s', (catalog_id,))}
        tombstones = {(r['kind'], bytes(r['key']).hex(), r['revision']) for r in conn.execute(
            'SELECT kind, key, revision FROM fact_tombstones WHERE catalog_id = %s', (catalog_id,))}
        objects = {r['id'].hex: r for r in conn.execute(
            '''SELECT o.id, o.sha256, o.bytes, o.codec, o.state, o.physical_key, c.kind, c.operation_id FROM objects o
               LEFT JOIN cg_objects c ON c.object_id = o.id WHERE o.catalog_id = %s''', (catalog_id,))}
        catalog_row = conn.execute('SELECT * FROM catalogs WHERE id = %s', (catalog_id,)).fetchone()
        settings = {r['key']: r['value'] for r in conn.execute('SELECT key, value FROM cg_settings WHERE catalog_id = %s',
                                                               (catalog_id,))}
        relations = {
            'variants': {(r['id'], json.dumps(r['metadata'], sort_keys=True), r['publication_id'].hex) for r in conn.execute(
                'SELECT id, metadata, publication_id FROM cg_variants WHERE catalog_id = %s', (catalog_id,))},
            'assessments': {(r['id'], r['object_id'].hex, r['publication_id'].hex, r['digest'], r['predecessor'], r['state'])
                            for r in conn.execute('SELECT * FROM cg_assessments WHERE catalog_id = %s', (catalog_id,))},
            'dependencies': {(r['object_id'].hex, r['depends_on'].hex) for r in conn.execute(
                'SELECT object_id, depends_on FROM cg_artifact_dependencies WHERE catalog_id = %s', (catalog_id,))},
            'vectors': {(r['digest'], r['object_id'].hex, r['row_index'], r['dtype'], r['dimensions']) for r in conn.execute(
                'SELECT * FROM cg_vector_locations WHERE catalog_id = %s', (catalog_id,))},
            'deletions': {(r['id'], json.dumps(r['plan'], sort_keys=True)) for r in conn.execute(
                'SELECT id, plan FROM cg_deletions WHERE catalog_id = %s', (catalog_id,))}}
        uses = {r['id']: r for r in conn.execute('SELECT * FROM evidence_uses WHERE catalog_id = %s', (catalog_id,))}
        registry = {(r['member_kind'], bytes(r['hash']).hex(), r['outcome_exposed'], r['development_use'], r['covariate_inspected'])
                    for r in conn.execute('SELECT * FROM exposure_registry WHERE catalog_id = %s', (catalog_id,))}
        members = {(r['use_id'], r['member_kind'], bytes(r['hash']).hex()) for r in conn.execute(
            'SELECT use_id, member_kind, hash FROM confirmation_members WHERE catalog_id = %s', (catalog_id,))}
        allocations = {(r['study_id'], r['use_id'], float(r['alpha']), float(r['total_alpha'])) for r in conn.execute(
            'SELECT * FROM study_allocations WHERE catalog_id = %s', (catalog_id,))}

    # K sequence and publications
    failures = [] if head == (legacy.settings.get('sequence') or 0) else [f'head {head}']
    for k, (kind, value) in events.items():
        pub = pubs.get(k)
        if pub is None:
            failures.append(f'K={k} missing')
        elif kind == 'operation':
            if (pub['id'].hex, pub['request_id'], pub['request_digest']) != (value['id'], value['request_id'], value['request_digest']) \
                    or pub['receipt'].get('cg') != (strict_json(value['receipt'].encode()) if value.get('receipt') else {}):
                failures.append(f'K={k} operation')
        elif pub['request_id'] != 'deletion:' + value['id'] or pub['kind'] != 'cg_deletion':
            failures.append(f'K={k} deletion')
    check('k_sequence_and_publications', failures, {'head': head})

    # Facts, occurrences, tombstones
    legacy_facts = legacy.facts()
    legacy_objects = {o['id']: o for o in legacy.objects()}
    failures = []
    expected = {}
    for f in legacy_facts:
        expected[(f['kind'], f['key'], f['revision'])] = (f['fact_digest'], f['object_id'], f['offset'], f['length'])
    if set(expected) != set(facts):
        failures.append(f'identity sets differ ({len(expected)} legacy, {len(facts)} platform)')
    for identity, (fd, oid, a, b) in expected.items():
        row = facts.get(identity)
        if row is not None and (bytes(row['fact_digest']).hex(), row['object_id'].hex, row['loc_a'], row['loc_b']) != (fd, oid, a, b):
            failures.append('fact ' + '/'.join(identity))
    check('fact_identity_digest_and_locator', failures, {'facts': len(expected)})
    by_id = {f['id']: f for f in legacy_facts}
    legacy_occurrences = {(r['operation_id'], by_id[r['fact_id']]['kind'], by_id[r['fact_id']]['key'], by_id[r['fact_id']]['revision'])
                          for r in legacy.query('SELECT operation_id, fact_id FROM occurrences')}
    check('occurrences', [] if legacy_occurrences == occurrences else ['occurrence sets differ'],
          {'occurrences': len(legacy_occurrences)})
    deleted = {(f['kind'], f['key'], f['revision']) for f in legacy_facts if legacy_objects[f['object_id']]['state'] != 'active'}
    check('deletion_tombstones', [] if deleted == tombstones else ['tombstone sets differ'], {'tombstoned': len(deleted)})

    # Objects: identity, bytes (full verify-on-read), kind, operation, state
    from numek_platform.objects import LocalObjectStore
    from .platform_catalog import BINDING
    store = LocalObjectStore(Path(root) / strict_json((Path(root) / BINDING).read_bytes())['store'])
    failures = []
    for oid, obj in legacy_objects.items():
        row = objects.get(oid)
        if row is None:
            failures.append(f'object {oid} missing')
            continue
        same = (bytes(row['sha256']).hex(), row['bytes'], row['codec'], row['kind'], row['operation_id'].hex if row['operation_id'] else None) \
            == (obj['sha256'], obj['bytes'], obj['encoding'], obj['kind'], obj['operation_id'])
        if not same:
            failures.append(f'object {oid} identity')
        elif obj['state'] == 'active':
            if row['state'] != 'active':
                failures.append(f'object {oid} state {row["state"]}')
            else:
                try:
                    store.read_verified(row['physical_key'], obj['sha256'], obj['bytes'])
                except Exception:
                    failures.append(f'object {oid} bytes')
        elif row['state'] != 'reclaimed':
            failures.append(f'object {oid} deleted state {row["state"]}')
    check('objects_identity_and_bytes', failures, {'objects': len(legacy_objects),
                                                   'verified_bytes': sum(1 for o in legacy_objects.values() if o['state'] == 'active')})

    # ConfidenceGuard relations
    lr = {
        'variants': {(r['id'], json.dumps(json.loads(r['metadata']), sort_keys=True), r['operation_id'])
                     for r in legacy.query('SELECT * FROM variants')},
        'assessments': {(r['id'], r['object_id'], r['operation_id'], r['digest'], r['predecessor'],
                         'deleted' if r['state'] == 'deleted' else 'active') for r in legacy.query('SELECT * FROM assessments')},
        'dependencies': {(r['object_id'], r['depends_on']) for r in legacy.query('SELECT * FROM artifact_dependencies')} if legacy.v2 else set(),
        'vectors': {(r['digest'], r['object_id'], r['row_index'], r['dtype'], r['dimensions'])
                    for r in legacy.query('SELECT * FROM vector_locations')} if legacy.v2 else set(),
        'deletions': {(r['id'], json.dumps(strict_json(r['plan'].encode()), sort_keys=True)) for r in legacy.query('SELECT * FROM deletions')}}
    check('cg_relations', [name for name in lr if lr[name] != relations[name]], {name: len(v) for name, v in lr.items()})

    # Identity and settings
    s = legacy.settings
    expected_identity = {'instance_id': s['instance_id'], 'config': s['config'], 'created_at': s.get('created_at'),
                         'branch_id': s.get('branch_id') or s['instance_id'], 'continuity': s.get('exposure_continuity', 'unknown'),
                         'continuity_token': s.get('exposure_continuity_token'), 'tracking': bool(s.get('exposure_tracking'))}
    actual_identity = {'instance_id': settings.get('instance_id'), 'config': settings.get('config'),
                       'created_at': settings.get('created_at'), 'branch_id': catalog_row['branch_id'],
                       'continuity': catalog_row['continuity_state'], 'continuity_token': catalog_row['continuity_token'],
                       'tracking': catalog_row['exposure_tracking']}
    check('identity_and_settings', [k for k in expected_identity if expected_identity[k] != actual_identity[k]])

    # Evidence governance
    failures = []
    expected_registry, expected_members, expected_allocations = {}, set(), set()
    if legacy.v2:
        from numek_platform.governance import CONFIRMATION_CLASSES
        from numek_platform.governance.ledger import decode_membership, membership_digest
        replay = _Replay(db, scope, None, legacy, catalog_id, None, None)
        allocation_rows = {a['reservation_id']: a for a in legacy.query('SELECT * FROM study_allocations')}
        legacy_uses = legacy.query('SELECT * FROM evidence_uses')
        for v2use in legacy_uses:
            payloads = [u for op in {o['operation_id'] for o in legacy_objects.values() if o['id'] == v2use['object_id']}
                        for u in replay.uses_of(op) if u[0]['id'] == v2use['id']]
            if len(payloads) != 1:
                failures.append(f"use {v2use['id']} source")
                continue
            payload, events, units = payloads[0]
            row = uses.get(v2use['id'])
            if row is None:
                failures.append(f"use {v2use['id']} missing")
                continue
            if (row['kind'], row['request_id'], row['population_digest'], row['family_digest'], row['membership_digest'],
                    row['event_count'], row['unit_count'], row['branch_id'], row['continuity']) != (
                    payload['kind'], payload['request_id'], payload['population_digest'], payload.get('family_digest'),
                    payload['membership_digest'], payload['event_count'], payload['unit_count'], payload['branch_id'],
                    payload['continuity']):
                failures.append(f"use {v2use['id']} fields")
            obj = objects[row['membership_object'].hex]
            stored_events, stored_units, _targets = decode_membership(
                store.read_verified(obj['physical_key'], bytes(obj['sha256']).hex(), obj['bytes']))
            if (stored_events, stored_units) != (events, units) or membership_digest(events, units) != payload['membership_digest']:
                failures.append(f"use {v2use['id']} membership")
            kind = payload['kind']
            for member_kind, values in (('event', events), ('unit', units)):
                for value in values:
                    flags = expected_registry.setdefault((member_kind, value), [False, False, False])
                    flags[0] |= kind in ('outcome_disclosure', 'discovery_selection')
                    flags[1] |= kind == 'discovery_selection'
                    flags[2] |= kind == 'covariate_inspection'
                    if kind in CONFIRMATION_CLASSES:
                        expected_members.add((payload['id'], member_kind, value))
            allocation = allocation_rows.get(v2use['id'])
            if allocation:
                expected_allocations.add((allocation['study_id'], v2use['id'], float(allocation['alpha']), float(allocation['total_alpha'])))
        if {u for u in uses if not uses[u]['legacy']} or len(uses) != len(legacy_uses):
            failures.append('use sets differ')
    registry_expected = {(k, h, *flags) for (k, h), flags in expected_registry.items()}
    if registry_expected != registry:
        failures.append('exposure registry differs')
    if expected_members != members:
        failures.append('confirmation members differ')
    if expected_allocations != allocations:
        failures.append('study allocations differ')
    check('evidence_governance', failures, {'uses': len(uses), 'registry_rows': len(registry)})

    if all(c['passed'] for c in checks.values()):
        checks.update(_analytical(root, catalog_id, legacy))
    return {'schema_version': 'confidenceguard.platform_migration_validation/1.0', 'passed': all(c['passed'] for c in checks.values()),
            'checks': checks}


def _analytical(root, catalog_id, legacy):
    """Reconstruction, assessments, deletion previews, overlap and CG3 re-execution (migration job, in process)."""
    from types import SimpleNamespace
    from .evidence_use import EvidenceUseLedger
    from .execution_context import InProcessContext, using
    from .platform_catalog import PlatformCatalog, _MIGRATION_VALIDATION
    from .workspace import ReliabilityWorkspace
    checks = {}

    def check(name, failures, detail=None):
        checks[name] = {'passed': not failures, 'failures': failures[:20], 'count': len(failures), **(detail or {})}

    _MIGRATION_VALIDATION.add(catalog_id)
    try:
        platform = PlatformCatalog(root)
        ws = ReliabilityWorkspace.__new__(ReliabilityWorkspace)
        ws.path, ws.catalog = Path(root), platform
        old = legacy.catalog

        # Historical reconstruction: every retained logical fact, byte-equal after decoding.
        from numek_platform.evidence import reader
        pin = reader.pin(platform.db, platform.scope, catalog_id, holder='migration-validation', allow_migrating=True)
        try:
            locators = reader.resolve(platform.db, pin, access='maintenance', require_complete=False)
            migrated = {}
            for locator, record in platform._read_locators([l for l in locators if l.codec in
                                                            ('utf8_jsonl_v1', 'typed_feature_rows_v1')]):
                migrated[(locator.kind, locator.key, locator.revision)] = record
        finally:
            reader.release(platform.db, pin)
        reference = {}
        for fact in old.iter_facts(None, require_complete=False):
            value = {k: v for k, v in fact.items() if k not in ('recorded_sequence', 'object_id', 'offset', 'record_bytes')}
            reference[(fact['kind'], fact['key'], fact['revision'])] = value
        failures = [] if set(reference) == set(migrated) else ['retained fact sets differ']
        failures += ['/'.join(i) for i in reference if i in migrated and reference[i] != migrated[i]]
        check('historical_reconstruction', failures, {'facts': len(reference)})

        # Retained assessments reopen identically.
        # Retained = its object is still stored (a v2 deletion removes the object, not the row).
        aids = [a['id'] for a in legacy.query("SELECT a.id FROM assessments a JOIN objects o ON o.id = a.object_id "
                                              "WHERE o.state = 'active' ORDER BY a.id")]
        failures = []
        for aid in aids:
            try:
                same = platform.assessment(aid).to_private_dict() == old.assessment(aid).to_private_dict()
            except EvaluationError as exc:
                same = False
                failures.append(f'{aid}: {exc.code}')
                continue
            if not same:
                failures.append(aid)
        check('retained_assessments', failures, {'assessments': len(aids)})

        # Deletion previews: every retained assessment and one object of every evidence kind.
        failures = []
        selections = [{'assessment_ids': [aid]} for aid in aids]
        seen_kinds = set()
        for o in legacy.query("SELECT id, kind FROM objects WHERE state = 'active' ORDER BY id"):
            if o['kind'] not in seen_kinds and o['kind'] not in ('assessment',):
                seen_kinds.add(o['kind'])
                selections.append({'object_ids': [o['id']]})
        for selection in selections:
            a, b = old.deletion_preview(**selection), platform.deletion_preview(**selection)
            if any(a[f] != b[f] for f in ('object_ids', 'affected_batches', 'potentially_impacted_assessments')):
                failures.append(json.dumps(selection))
        check('deletion_previews', failures, {'selections': len(selections)})

        # Evidence-use overlap answers on every recorded population (sampled) and an unrelated one.
        failures = []
        if legacy.v2:
            old_ledger = EvidenceUseLedger(SimpleNamespace(catalog=old, path=Path(root)))
            new_ledger = EvidenceUseLedger(ws)
            replay = _Replay(None, None, None, legacy, catalog_id, None, None)
            samples = [([digest(['migration-validation', 'unrelated'])], [])]
            for op in {o['operation_id'] for o in legacy.objects() if o['kind'] == 'evidence_use'}:
                for payload, events, units in replay.uses_of(op):
                    samples.append((events[:MAX_OVERLAP_SAMPLE], units[:MAX_OVERLAP_SAMPLE]))
            for events, units in samples:
                if sorted(old_ledger.overlap(events, units)) != sorted(new_ledger.overlap(events, units)):
                    failures.append(f'{len(events)} events/{len(units)} units')
        check('evidence_use_overlap', failures)

        # Deterministic re-execution of every retained CG3 analysis at its own K.
        failures, executed, refused = [], 0, 0
        from .history_contracts import LongitudinalSpec
        from .longitudinal import analyze
        # v2 lists every active assessment as potentially impacted by an evidence deletion (a
        # superset). Such an analysis either re-executes equal (it never read the deleted
        # evidence) or refuses as v2 does; a refusal is accepted only for those.
        impacted = {aid for row in legacy.query('SELECT plan FROM deletions')
                    for plan in [strict_json(row['plan'].encode())] if plan['object_ids']
                    for aid in plan.get('potentially_impacted_assessments', ())}
        for aid in aids:
            stored = old.assessment(aid)
            spec_dict = (getattr(stored, 'private', None) or {}).get('history_spec')
            if not spec_dict:
                continue
            spec = LongitudinalSpec.from_dict(spec_dict)
            lease, governance = platform.reserve_history(namespace=spec.namespace, k=spec.catalog_sequence,
                                                         purpose_label='migration_validation', exposure=False)
            try:
                with using(InProcessContext()):
                    result = analyze(Path(root), spec, governance=governance)
            except EvaluationError as exc:
                if aid in impacted and exc.code == 'historical_evidence_unavailable':
                    refused += 1
                    continue
                failures.append(f'{aid}: {exc.code}')
                continue
            finally:
                platform.finish_attempt(lease)
            if stored.data.get('history', {}).get('restatement_changes') is not None:
                result.data['history']['restatement_changes'] = stored.data['history']['restatement_changes']
            diff = differences(stored.to_private_dict(), result.to_private_dict(), ignore=ORDER_DEPENDENT)
            executed += 1
            if diff:
                failures.append(f'{aid}: {diff[:5]}')
        check('cg3_reexecution', failures, {'analyses': executed, 'refused_after_deletion_as_in_v2': refused,
                                            'ignored_fields': [p.pattern for p in ORDER_DEPENDENT]})
    finally:
        _MIGRATION_VALIDATION.discard(catalog_id)
    return checks


# Orchestration ------------------------------------------------------------------------------------------------
def migrate_workspace(path, *, backup_destination=None):
    """Migrate (or resume migrating) the v1/v2 workspace at ``path``. Returns the migration status and report."""
    from numek_platform.errors import PlatformError
    from numek_platform.execution import jobs
    from numek_platform.legacy import migration as M
    from .platform_catalog import BINDING, platform_bound, write_binding
    root = Path(path).absolute()
    if not (root / 'catalog.sqlite3').is_file():
        raise EvaluationError('No catalog v2 workspace exists at this path.', 'workspace_missing')
    try:
        legacy = Legacy(root)
        if legacy.settings.get('retired'):
            raise EvaluationError('Workspace was retired; nothing to migrate.', 'workspace_retired')
        db, scope, binding, store = _platform(root)
        row = _live_migration(db, legacy.settings['instance_id'])
        if row is None:
            if platform_bound(root):
                raise EvaluationError('This workspace is already bound to the platform.', 'migration_state')
            migration_id, catalog_id = M.plan(db, scope, root, catalog_name=f"workspace:{legacy.settings['instance_id']}")
            _prepare_catalog(db, catalog_id, legacy)
            write_binding(root, binding, scope, catalog_id)          # inaccessible until cutover (catalog is migrating)
            row = _live_migration(db, legacy.settings['instance_id'])
        migration_id, catalog_id = row['id'], row['catalog_id']
        if not platform_bound(root):
            write_binding(root, binding, scope, catalog_id)          # repair after a crash between plan and binding
        fault('planned')
        if row['state'] in ('planned', 'frozen'):
            M.freeze(db, scope, migration_id)
            fault('frozen')
        if row['state'] in ('planned', 'frozen', 'copying'):
            M.begin_copy(db, scope, migration_id)
            legacy = Legacy(root)
            status = M.status(db, scope, migration_id)
            _drop_stale_pending(db, store, catalog_id)
            with db.connect() as conn:
                lease, _ = jobs.start_inline(conn, scope, 'cg_v2_migration', idempotency_key=uuid.uuid4().hex,
                                             owner='confidenceguard-migration')
            try:
                _Replay(db, scope, store, legacy, catalog_id, migration_id, lease).run(status['last_migrated_k'] + 1, legacy.events())
            finally:
                with contextlib.suppress(Exception), db.connect() as conn:
                    jobs.complete(conn, lease, {})
            M.begin_validation(db, scope, migration_id)
            fault('copied')
        report = None
        state = M.status(db, scope, migration_id)['state']
        if state == 'validating':
            report = validate(root, db=db, scope=scope, catalog_id=catalog_id, legacy=Legacy(root))
            if not report['passed']:
                with db.transaction() as conn:
                    conn.execute('UPDATE legacy_migrations SET validation = %s WHERE id = %s',
                                 (__import__('psycopg').types.json.Jsonb(report), migration_id))
                failed = sorted(k for k, v in report['checks'].items() if not v['passed'])
                error = EvaluationError('Migration validation failed: ' + ', '.join(failed) + '. The workspace stays '
                                        'frozen and unmigrated; abandon to restore catalog v2.', 'migration_validation')
                error.report = report
                raise error
            M.cutover(db, scope, migration_id, report)
            fault('cutover')
        with db.connect() as conn:
            row = conn.execute('SELECT * FROM legacy_migrations WHERE id = %s', (migration_id,)).fetchone()
        report = report or row['validation']
        backup = None
        if row['post_cutover_backup'] is None and backup_destination is not None:
            if binding.get('dsn_env'):
                raise EvaluationError('Workspace backup is available only for workspaces with their own platform cluster; '
                                      'back up the shared installation with its operator procedure.', 'backup_scope')
            from .workspace import ReliabilityWorkspace
            summary = ReliabilityWorkspace(root).backup(backup_destination)
            manifest = json.loads((Path(backup_destination) / 'platform' / 'manifest.json').read_bytes())
            M.record_post_cutover_backup(db, scope, migration_id, manifest)
            backup = {'path': str(Path(backup_destination).absolute()), 'content_digest': summary['content_digest']}
        status = M.status(db, scope, migration_id)
    except PlatformError as exc:
        raise _translate(exc) from exc
    if not status['complete']:
        status['incomplete_reason'] = ('post_cutover_backup_required_on_shared_installation' if binding.get('dsn_env')
                                       else 'post_cutover_backup_required')
    return {**status, 'migration_id': str(migration_id), 'validation': report, 'backup': backup,
            'binding': str(root / BINDING)}


def abandon_workspace(path):
    """Before cutover only: drop the platform copy and restore catalog v2 (idempotent)."""
    from numek_platform.errors import PlatformError
    from numek_platform.legacy import migration as M
    from .platform_catalog import BINDING
    root = Path(path).absolute()
    legacy = Legacy(root)
    db, scope, _binding, store = _platform(root)
    row = _live_migration(db, legacy.settings['instance_id'])
    if row is None:
        raise EvaluationError('No migration is in progress for this workspace.', 'unknown_migration')
    if row['state'] == 'cutover_committed':
        raise EvaluationError('Cutover is final; recover through platform backups.', 'migration_state')
    with contextlib.suppress(FileNotFoundError):
        (root / BINDING).unlink()                                   # never open the abandoned copy again
    def cleanup(conn, catalog_id):
        for table in ('cg_vector_locations', 'cg_artifact_dependencies', 'cg_assessments', 'cg_variants', 'cg_deletions',
                      'cg_objects', 'cg_settings'):
            conn.execute(f'DELETE FROM {table} WHERE catalog_id = %s', (catalog_id,))

    try:
        M.abandon(db, scope, row['id'], cleanup=cleanup, store=store)
    except PlatformError as exc:
        raise _translate(exc) from exc
    return {'state': 'abandoned', 'migration_id': str(row['id'])}


def migration_status(path):
    from numek_platform.legacy import catalog_v2, migration as M
    root = Path(path).absolute()
    marker = catalog_v2.read_marker(root)
    if marker is None:
        return {'state': 'not_started'}
    db, scope, _binding, _store = _platform(root)
    return M.status(db, scope, uuid.UUID(marker['migration_id']))


def restore_legacy_backup(backup, destination):
    """Restore a catalog v2 workspace backup (``workspace_backup/1.0``) as a new platform workspace.

    The verified backup files are copied into a new v2 workspace that becomes a new instance
    (new instance id, branch and continuity token; continuity ``restore_unreconciled``), as a
    v2 restore did; that copy is then migrated (validated) onto the platform.
    """
    import os
    import shutil
    import sqlite3
    from .feature_storage import CODECS
    from .history_storage import HEX, file_digest, fsync_directory, private_directory, private_file
    from .platform_catalog import PlatformCatalog
    backup = Path(backup).absolute()
    destination = Path(destination).absolute()
    if destination.exists() or destination == backup or backup in destination.parents:
        raise EvaluationError('Restore requires a new destination.', 'restore_destination')
    if not (backup / 'backup.json').is_file():
        raise EvaluationError('Backup is incomplete or changed.', 'backup_changed')
    with private_file(backup / 'backup.json', 'rb') as stream:
        manifest = strict_json(stream.read(64 * 1024**2 + 1))
    expected = manifest.pop('content_digest', None)
    if expected != digest(manifest) or manifest.get('schema_version') != 'confidenceguard.workspace_backup/1.0':
        raise EvaluationError('Backup is incomplete or changed.', 'backup_changed')
    for relative, identity in manifest['files'].items():
        path = Path(relative)
        if path.is_absolute() or '..' in path.parts or str(path) != 'catalog.sqlite3' and not (
                len(path.parts) == 2 and path.parts[0] == 'objects' and HEX.fullmatch(path.stem) and path.suffix in CODECS.values()):
            raise EvaluationError('Unsafe backup inventory.', 'backup_changed')
        if list(file_digest(backup / relative)) != list(identity):
            raise EvaluationError('Backup bytes differ.', 'backup_changed')
    private_directory(destination)
    for relative in manifest['files']:
        target = destination / relative
        private_directory(target.parent)
        with private_file(backup / relative, 'rb') as source, private_file(target) as out:
            shutil.copyfileobj(source, out, 1024**2)
            out.flush()
            os.fsync(out.fileno())
    for part in ('objects', 'staging'):
        private_directory(destination / part)
    for lock in ('.operation.lock', '.objects.lock'):
        with private_file(destination / lock):
            pass
    with contextlib.closing(sqlite3.connect(destination / 'catalog.sqlite3', isolation_level=None)) as db:
        db.execute('BEGIN IMMEDIATE')
        version = db.execute('PRAGMA user_version').fetchone()[0]
        db.execute("UPDATE settings SET value = ? WHERE key = 'instance_id'", (json.dumps(uuid.uuid4().hex),))
        if version >= 2:
            db.execute("UPDATE settings SET value = '\"restore_unreconciled\"' WHERE key = 'exposure_continuity'")
            db.execute("UPDATE settings SET value = ? WHERE key = 'branch_id'", (json.dumps(uuid.uuid4().hex),))
            db.execute('INSERT OR REPLACE INTO settings VALUES (?, ?)', ('exposure_continuity_token', json.dumps(uuid.uuid4().hex)))
        db.execute('COMMIT')
    fsync_directory(destination)
    migrate_workspace(destination)
    return PlatformCatalog(destination)
