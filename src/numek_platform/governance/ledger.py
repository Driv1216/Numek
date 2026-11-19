"""Evidence-use reservations: the governance-before-access ledger (R2.3).

A reservation is committed *before* any protected evidence is read:

1. W1-W3 stage an immutable membership object (``exposure_membership_v1``)
   of the event and unit hashes the caller may read.
2. One transaction (lock order: job, exposure lock, catalog, objects,
   governance rows) checks the fence, applies the purpose's reserve mode, runs
   the ported ConfidenceGuard confirmation rules, records the use, activates
   the membership object, enforces study error budgets and updates the
   exposure and entity registries.

A reservation is ``reserved`` until a publication by the same attempt marks it
``consumed`` in the result's own transaction. Failure, cancellation, a crash or
fence loss leave it ``reserved`` forever: it still counts as exposure, and
freshness is never restored.

Ported semantics (``confidenceguard.evidence_use``): legacy use ids and
membership digests; continuity gaps that require a current scoped declaration;
numerical-retry continuity; predeclared scheduled looks; reuse of an identical
confirmation family and population; overlap refusal (excluding the same
confirmation family and population); incomplete replay aliases; and study
alpha budgets. The process-local session ledger is gone: every use is durable.
"""
import io
import uuid
from dataclasses import dataclass
from decimal import Decimal

from psycopg.types.json import Jsonb

from ..canonical import digest
from ..errors import PlatformError
from ..evidence.catalogs import catalog, require_active
from ..evidence.publish import activate_pending, stage_object
from ..execution.jobs import assert_fence
from . import (COMPLETE_IDENTITY_SCOPE, CONFIRMATION_CLASSES, REPLAY_PURPOSES, SOURCE_ALIAS_POLICY,
               purpose_rules)

MEMBERSHIP_CODEC = 'exposure_membership_v1'


@dataclass(frozen=True)
class Reservation:
    id: str
    catalog_id: uuid.UUID
    purpose: str
    kind: str
    read_k: int | None
    job_id: uuid.UUID | None
    fence: int | None
    withheld_reserve_units: int = 0
    reserve_consumed_units: int = 0
    reused: bool = False


def _hexes(values, label):
    out = sorted(set(values))
    for value in out:
        if not isinstance(value, str) or len(value) != 64 or any(c not in '0123456789abcdef' for c in value):
            raise PlatformError(f'Invalid {label} identity hash.', 'invalid_membership')
    return out


def encode_membership(events, units, targets=()):
    import pyarrow as pa
    import pyarrow.parquet as pq
    kinds = ['event'] * len(events) + ['unit'] * len(units) + ['target'] * len(targets)
    table = pa.table({'member_kind': pa.array(kinds, pa.string()),
                      'hash': pa.array(list(events) + list(units) + list(targets), pa.string())})
    sink = io.BytesIO()
    pq.write_table(table, sink, compression='zstd')
    return sink.getvalue()


def decode_membership(data):
    import pyarrow as pa
    import pyarrow.parquet as pq
    table = pq.read_table(pa.BufferReader(data))
    groups = {'event': [], 'unit': [], 'target': []}
    for kind, value in zip(table['member_kind'].to_pylist(), table['hash'].to_pylist()):
        groups[kind].append(value)
    return groups['event'], groups['unit'], groups['target']


def membership_digest(events, units):
    """Identical to the v2 ledger's ``digest({'events': ..., 'units': ...})``."""
    return digest({'events': events, 'units': units})


def tracking_status(db, scope, catalog_id):
    with db.connect() as conn:
        row = catalog(conn, scope, catalog_id)
    return {'enabled': row['exposure_tracking'], 'continuity': row['continuity_state'], 'branch_id': row['branch_id'],
            'continuity_token': row['continuity_token'], 'system_verified_external_independence': False,
            'guarantee_scope': 'predeclared_study_only'}


def set_tracking(db, scope, catalog_id, enabled):
    """v2 semantics: disabling makes continuity incomplete and rotates the token."""
    if not isinstance(enabled, bool):
        raise PlatformError('Evidence-use consent must be Boolean.', 'invalid_request')
    with db.transaction() as conn:
        conn.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))', (f'exposure:{catalog_id}',))
        row = catalog(conn, scope, catalog_id, lock='update')
        token = row['continuity_token']
        continuity = row['continuity_state']
        if not enabled:
            continuity, token = 'incomplete', uuid.uuid4().hex
        elif token is None:
            token = uuid.uuid4().hex
        conn.execute('UPDATE catalogs SET exposure_tracking = %s, continuity_state = %s, continuity_token = %s WHERE id = %s',
                     (enabled, continuity, token, catalog_id))
    return tracking_status(db, scope, catalog_id)


def _reserve_units(conn, catalog_id, units):
    if not units:
        return {}
    rows = conn.execute('SELECT unit_hash, reserve_state, spent_by_use FROM entity_registry WHERE catalog_id = %s '
                        'AND unit_hash = ANY(%s)', (catalog_id, [bytes.fromhex(u) for u in units])).fetchall()
    return {bytes(r['unit_hash']).hex(): r for r in rows if r['reserve_state'] == 'reserve'}


def _covariate_policy(conn, catalog_id):
    rows = conn.execute("SELECT covariate_policy FROM reserves WHERE catalog_id = %s AND state = 'active'", (catalog_id,)).fetchall()
    return 'exclude' if any(r['covariate_policy'] == 'exclude' for r in rows) or not rows else 'inspect'


def _apply_reserve_mode(conn, catalog_id, mode, members, extra_units, consume_reserve):
    """Return (members, extra_units, withheld_units, consumed_units) after the purpose's reserve rule.

    Units already spent are reported by :func:`_spent`; the caller refuses them
    only after the ported same-family reuse rule has had its chance.
    """
    units = sorted({m[1] for m in members} | set(extra_units))
    reserved = _reserve_units(conn, catalog_id, units)
    if not reserved:
        return members, extra_units, [], []
    if mode == 'covariates':
        mode = 'withhold' if _covariate_policy(conn, catalog_id) == 'exclude' else 'admit'
    if mode == 'admit':
        return members, extra_units, [], []
    if mode == 'refuse':
        raise PlatformError('Development roles may not use sealed-reserve entities.', 'reserve_access_refused')
    if mode == 'consume':
        if not consume_reserve:
            raise PlatformError('This population contains sealed-reserve entities; explicit reserve consumption '
                                '(reserve:consume) is required.', 'reserve_access_refused')
        return members, extra_units, [], sorted(reserved)
    kept = [m for m in members if m[1] not in reserved]
    return kept, [u for u in extra_units if u not in reserved], sorted(reserved), []


def _spent(conn, catalog_id, units):
    if not units:
        return []
    rows = conn.execute('SELECT unit_hash FROM entity_registry WHERE catalog_id = %s AND unit_hash = ANY(%s) '
                        'AND spent_by_use IS NOT NULL', (catalog_id, [bytes.fromhex(u) for u in units])).fetchall()
    return [bytes(r['unit_hash']).hex() for r in rows]


def _overlap_reasons(conn, catalog_id, query_events, units, family_digest, population_digest):
    """Ported v2 overlap: any earlier exposure except the same confirmation family and population."""
    reasons = set()
    conn.execute('CREATE TEMP TABLE _req (member_kind text, hash bytea) ON COMMIT DROP')
    with conn.cursor().copy('COPY _req (member_kind, hash) FROM STDIN') as copy:
        for value in query_events:
            copy.write_row(('event', bytes.fromhex(value)))
        for value in units:
            copy.write_row(('unit', bytes.fromhex(value)))
    hit = conn.execute(
        '''SELECT 1 FROM exposure_registry r JOIN _req q ON r.member_kind = q.member_kind AND r.hash = q.hash
           WHERE r.catalog_id = %s AND r.outcome_exposed LIMIT 1''', (catalog_id,)).fetchone()
    if hit is None:
        hit = conn.execute(
            '''SELECT 1 FROM confirmation_members m JOIN _req q ON m.member_kind = q.member_kind AND m.hash = q.hash
               JOIN evidence_uses u ON u.catalog_id = m.catalog_id AND u.id = m.use_id
               WHERE m.catalog_id = %s AND NOT (u.family_digest IS NOT DISTINCT FROM %s AND u.population_digest = %s)
               LIMIT 1''', (catalog_id, family_digest, population_digest)).fetchone()
    if hit is not None:
        reasons.add('previously_exposed_confirmation_population')
    incomplete = conn.execute(
        '''SELECT 1 FROM evidence_uses WHERE catalog_id = %s AND kind = 'outcome_disclosure'
           AND metadata->>'purpose' = ANY(%s)
           AND (metadata->>'identity_policy' IS DISTINCT FROM %s OR metadata->>'local_identity_scope' IS DISTINCT FROM %s)
           LIMIT 1''', (catalog_id, list(REPLAY_PURPOSES), SOURCE_ALIAS_POLICY, COMPLETE_IDENTITY_SCOPE)).fetchone()
    if incomplete is not None:
        reasons.add('exposure_history_incomplete')
    conn.execute('DROP TABLE _req')
    return sorted(reasons)


def _confirmation_rules(conn, catalog_id, kind, row, metadata, family_digest, population_digest, alpha, events, units,
                        query_events):
    """Return an existing reservation id to reuse, or None; raise on refusal (ported semantics)."""
    gap = row['continuity_state'] in ('incomplete', 'restore_unreconciled')
    current = metadata.get('exposure_history_token')
    if not row['exposure_tracking']:
        raise PlatformError('Explicit evidence-use tracking consent required.', 'exposure_tracking_disabled')
    if kind == 'confirmation' and gap and (not current or current != row['continuity_token']):
        raise PlatformError('This history gap requires a current explicit scoped declaration, not an earlier unexposed '
                            'assertion.', 'exposure_history_gap_requires_current_declaration')
    if kind == 'numerical_recomputation' and (metadata.get('continuity_token') != row['continuity_token']
                                              or metadata.get('branch_id') != row['branch_id'] or gap):
        raise PlatformError('Numerical-attempt continuity changed before reservation.', 'numerical_retry_provenance')
    if kind != 'confirmation':
        return None
    declared, look_id = metadata.get('predeclared_look'), metadata.get('look_id')
    if declared:
        initial = conn.execute(
            '''SELECT * FROM evidence_uses WHERE catalog_id = %s AND id = %s AND kind = 'confirmation'
               AND family_digest IS NOT DISTINCT FROM %s AND (metadata->>'look_id') IS NULL''',
            (catalog_id, metadata.get('initial_use_id'), family_digest)).fetchone()
        if (initial is None or declared not in (initial['metadata'] or {}).get('restatement_schedule', [])
                or declared.get('id') != look_id or Decimal(str(declared['alpha'])) != Decimal(str(alpha))
                or initial['membership_digest'] != membership_digest(events, units)):
            raise PlatformError('Scheduled reuse lacks the original durable family, schedule or identical planned '
                                'population.', 'scheduled_restatement_provenance')
        other = conn.execute(
            '''SELECT 1 FROM evidence_uses WHERE catalog_id = %s AND kind = 'confirmation'
               AND family_digest IS NOT DISTINCT FROM %s AND metadata->>'look_id' = %s AND population_digest <> %s''',
            (catalog_id, family_digest, look_id, population_digest)).fetchone()
        if other:
            raise PlatformError('This scheduled look was already reserved against a different outcome snapshot.',
                                'scheduled_look_already_assessed')
    prior = conn.execute(
        '''SELECT id FROM evidence_uses WHERE catalog_id = %s AND kind = 'confirmation'
           AND family_digest IS NOT DISTINCT FROM %s AND population_digest = %s
           AND (metadata->>'look_id') IS NOT DISTINCT FROM %s ORDER BY created_at LIMIT 1''',
        (catalog_id, family_digest, population_digest, look_id)).fetchone()
    if prior:
        return prior['id']
    reasons = _overlap_reasons(conn, catalog_id, query_events, units, family_digest, population_digest)
    if (current and current == row['continuity_token'] and metadata.get('external_exposure') == 'declared_unexposed'
            and metadata.get('declaration_author') and metadata.get('declaration_reason')):
        reasons = [r for r in reasons if r not in ('exposure_history_unavailable', 'exposure_history_incomplete')]
    if declared:
        reasons = [r for r in reasons if r not in ('previously_exposed_confirmation_population',
                                                   'exposure_history_unavailable', 'exposure_history_incomplete')]
    if reasons:
        raise PlatformError('Confirmation population has conflicting or incomplete exposure history.',
                            'confirmation_population_exposed')
    return None


def reserve(db, store, scope, lease, catalog_id, *, purpose, members, population_digest, extra_events=(),
            extra_units=(), read_k=None, as_of=None, selection_digest=None, family_digest=None, request_id=None,
            study_id=None, alpha=None, total_alpha=None, metadata=None, consume_reserve=False, query_events=None):
    """Commit an evidence-use reservation before reading protected evidence.

    ``members`` is [(event_hash, unit_hash)] or [(event_hash, unit_hash, target_key)]
    (platform-native identities; the target key admits the outcome facts of
    that opportunity, which are keyed by target rather than by event);
    ``extra_events`` / ``extra_units`` carry legacy source aliases that have no
    entity pairing. Returns a :class:`Reservation`.
    """
    kind, mode = purpose_rules(purpose)
    metadata = dict(metadata or {}, purpose=metadata.get('purpose', purpose) if metadata else purpose)
    members = sorted({tuple(m) if len(m) == 3 else (m[0], m[1], None) for m in members})
    _hexes([m[0] for m in members] + list(extra_events), 'event')
    _hexes([m[1] for m in members] + list(extra_units), 'unit')
    _hexes([m[2] for m in members if m[2] is not None], 'target')
    request_id = request_id or uuid.uuid4().hex

    # Reserve states change only under the exposure lock; read them now to
    # build the membership object, then re-check inside the transaction.
    with db.connect() as conn:
        kept, kept_extra_units, withheld, consumed = _apply_reserve_mode(conn, catalog_id, mode, members,
                                                                         list(extra_units), consume_reserve)
    events = _hexes([m[0] for m in kept] + list(extra_events), 'event')
    units = _hexes([m[1] for m in kept] + kept_extra_units, 'unit')
    targets = _hexes([m[2] for m in kept if m[2] is not None], 'target')
    request = {'kind': kind, 'purpose': purpose, 'events': events, 'units': units, 'population_digest': population_digest,
               'family_digest': family_digest, 'study_id': study_id, 'alpha': None if alpha is None else str(alpha),
               'total_alpha': None if total_alpha is None else str(total_alpha), 'metadata': metadata,
               'read_k': read_k, 'as_of': as_of, 'selection_digest': selection_digest,
               **({'targets': targets} if targets else {})}
    request_digest = digest(request)
    use_id = digest([kind, population_digest, family_digest, request_id])[:32]
    member_digest = membership_digest(events, units)
    ref = stage_object(db, store, lease, encode_membership(events, units, targets), catalog_id=catalog_id,
                       codec=MEMBERSHIP_CODEC, records=len(events) + len(units) + len(targets))

    with db.transaction() as conn:
        assert_fence(conn, lease)                                                        # 1 job
        conn.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))', (f'exposure:{catalog_id}',))  # 2
        row = require_active(catalog(conn, scope, catalog_id, lock='share'))             # 3 catalog
        existing = conn.execute('SELECT * FROM evidence_uses WHERE catalog_id = %s AND request_id = %s',
                                (catalog_id, request_id)).fetchone()
        if existing is not None:
            if existing['request_digest'] != request_digest:
                raise PlatformError('This request id was already used for different content.', 'idempotency_conflict')
            return _rebind(conn, existing, lease)
        again = _apply_reserve_mode(conn, catalog_id, mode, members, list(extra_units), consume_reserve)
        if (again[0], again[1], again[2], again[3]) != (kept, kept_extra_units, withheld, consumed):
            raise PlatformError('Reserve assignments changed during the reservation; retry.', 'governance_changed',
                                retryable=True)
        if kind in CONFIRMATION_CLASSES:
            reuse = _confirmation_rules(conn, catalog_id, kind, row, metadata, family_digest, population_digest, alpha,
                                        events, units, query_events if query_events is not None else events)
            if reuse is not None:
                prior = conn.execute('SELECT * FROM evidence_uses WHERE catalog_id = %s AND id = %s', (catalog_id, reuse)).fetchone()
                return _rebind(conn, prior, lease)
        if _spent(conn, catalog_id, consumed):
            raise PlatformError('Some sealed-reserve entities were already spent by another study.', 'reserve_access_refused')
        if ref.reused:                                                                   # identical membership bytes
            object_id = ref.id
        else:
            activate_pending(conn, scope, lease, catalog_id, [ref.id])                   # 4 objects
            object_id = ref.id
        conn.execute(
            '''INSERT INTO evidence_uses(org_id, catalog_id, id, request_id, request_digest, kind, purpose, state,
                   population_digest, family_digest, membership_digest, membership_object, event_count, unit_count,
                   withheld_reserve_units, reserve_consumed_units, read_k, as_of, selection_digest, study_id, alpha,
                   total_alpha, branch_id, continuity, continuity_token, metadata, job_id, fence)
               VALUES (%s, %s, %s, %s, %s, %s, %s, 'reserved', %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                       %s, %s, %s, %s, %s, %s, %s)''',
            (scope.org_id, catalog_id, use_id, request_id, request_digest, kind, purpose, population_digest,
             family_digest, member_digest, object_id, len(events), len(units), len(withheld), len(consumed), read_k,
             as_of, selection_digest, study_id, alpha, total_alpha, row['branch_id'], row['continuity_state'],
             row['continuity_token'], Jsonb(metadata), lease.job_id, lease.fence))
        if study_id:
            _allocate(conn, catalog_id, study_id, use_id, alpha, total_alpha)
        _register_exposure(conn, scope, catalog_id, use_id, kind, events, units)
        if consumed:
            conn.execute('UPDATE entity_registry SET spent_by_use = %s, spent_at = now() WHERE catalog_id = %s '
                         'AND unit_hash = ANY(%s) AND spent_by_use IS NULL',
                         (use_id, catalog_id, [bytes.fromhex(u) for u in consumed]))
            reserve_ids = conn.execute(
                "SELECT DISTINCT reserve_id FROM entity_registry WHERE catalog_id = %s AND unit_hash = ANY(%s)",
                (catalog_id, [bytes.fromhex(u) for u in consumed])).fetchall()
            for r in reserve_ids:
                conn.execute("INSERT INTO reserve_events(org_id, reserve_id, event, detail, actor) VALUES (%s, %s, 'consumed', %s, %s)",
                             (scope.org_id, r['reserve_id'], Jsonb({'use_id': use_id, 'units': len(consumed)}), f'job:{lease.job_id}'))
    return Reservation(use_id, catalog_id, purpose, kind, read_k, lease.job_id, lease.fence, len(withheld), len(consumed))


def _rebind(conn, row, lease):
    """Hand an existing reservation to the current attempt; exposure history is unchanged.

    Used for retried attempts (same request id) and for the ported reuse of an
    identical confirmation family and population. The earlier owner is kept.
    """
    if (row['job_id'], row['fence']) != (lease.job_id, lease.fence):
        row = conn.execute(
            '''UPDATE evidence_uses SET job_id = %s, fence = %s,
                   metadata = jsonb_set(metadata, '{rebound_from}', coalesce(metadata->'rebound_from', '[]'::jsonb)
                       || jsonb_build_array(jsonb_build_object('job_id', job_id::text, 'fence', fence)))
               WHERE catalog_id = %s AND id = %s RETURNING *''',
            (lease.job_id, lease.fence, row['catalog_id'], row['id'])).fetchone()
    return _from_row(row, reused=True)


def _from_row(row, *, reused):
    return Reservation(row['id'], row['catalog_id'], row['purpose'], row['kind'], row['read_k'], row['job_id'],
                       row['fence'], row['withheld_reserve_units'], row['reserve_consumed_units'], reused=reused)


def _allocate(conn, catalog_id, study_id, use_id, alpha, total_alpha):
    if alpha is None or total_alpha is None:
        raise PlatformError('Study reservations need alpha and total alpha.', 'study_alpha_exhausted')
    alpha, total = Decimal(str(alpha)), Decimal(str(total_alpha))
    prior = conn.execute('SELECT alpha, total_alpha FROM study_allocations WHERE catalog_id = %s AND study_id = %s FOR UPDATE',
                         (catalog_id, study_id)).fetchall()
    if alpha <= 0 or any(Decimal(r['total_alpha']) != total for r in prior) or sum((Decimal(r['alpha']) for r in prior),
                                                                                   Decimal(0)) + alpha > total:
        raise PlatformError('Predeclared study error allocation exhausted or changed.', 'study_alpha_exhausted')
    conn.execute('INSERT INTO study_allocations(catalog_id, study_id, use_id, alpha, total_alpha) VALUES (%s, %s, %s, %s, %s)',
                 (catalog_id, study_id, use_id, alpha, total))


def _register_exposure(conn, scope, catalog_id, use_id, kind, events, units):
    outcome = kind in ('outcome_disclosure', 'discovery_selection')
    development = kind == 'discovery_selection'
    covariates = kind == 'covariate_inspection'
    conn.execute('CREATE TEMP TABLE _members (member_kind text, hash bytea) ON COMMIT DROP')
    with conn.cursor().copy('COPY _members (member_kind, hash) FROM STDIN') as copy:
        for value in events:
            copy.write_row(('event', bytes.fromhex(value)))
        for value in units:
            copy.write_row(('unit', bytes.fromhex(value)))
    conn.execute(
        '''INSERT INTO exposure_registry(org_id, catalog_id, member_kind, hash, outcome_exposed, development_use,
                                         covariate_inspected, first_use_id, last_use_id)
           SELECT %s, %s, member_kind, hash, %s, %s, %s, %s, %s FROM _members
           ON CONFLICT (catalog_id, member_kind, hash) DO UPDATE SET
               outcome_exposed = exposure_registry.outcome_exposed OR EXCLUDED.outcome_exposed,
               development_use = exposure_registry.development_use OR EXCLUDED.development_use,
               covariate_inspected = exposure_registry.covariate_inspected OR EXCLUDED.covariate_inspected,
               last_use_id = EXCLUDED.last_use_id''',
        (scope.org_id, catalog_id, outcome, development, covariates, use_id, use_id))
    if kind in CONFIRMATION_CLASSES:
        conn.execute('''INSERT INTO confirmation_members(catalog_id, use_id, member_kind, hash)
                        SELECT %s, %s, member_kind, hash FROM _members ON CONFLICT DO NOTHING''', (catalog_id, use_id))
    conn.execute('DROP TABLE _members')


def consume(conn, scope, lease, catalog_id, reservations):
    """Mark this attempt's reservations consumed inside the result's publication transaction."""
    ids = sorted({r.id if isinstance(r, Reservation) else str(r) for r in reservations})
    rows = conn.execute(
        '''SELECT id, state, job_id, fence FROM evidence_uses WHERE org_id = %s AND catalog_id = %s AND id = ANY(%s)
           ORDER BY id FOR UPDATE''', (scope.org_id, catalog_id, ids)).fetchall()
    if len(rows) != len(ids):
        raise PlatformError('A referenced evidence-use reservation is unknown.', 'unknown_reservation')
    for row in rows:
        if row['job_id'] != lease.job_id or row['fence'] != lease.fence:
            raise PlatformError('Reservation belongs to another attempt.', 'reservation_owner')
    conn.execute("UPDATE evidence_uses SET state = 'consumed', consumed_at = clock_timestamp() "
                 "WHERE catalog_id = %s AND id = ANY(%s) AND state = 'reserved'", (catalog_id, ids))
