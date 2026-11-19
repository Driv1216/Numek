"""Namespace-level sealed confirmation reserves and the entity registry (G.8 + R2).

* A reserve belongs to one (catalog, namespace). Founder defaults: 10% of
  entities, covariate policy ``exclude``.
* Assignment is materialized when an entity is first seen:
  HMAC-SHA256(secret, namespace || 0x00 || entity) read as a 64-bit fraction,
  compared with the reserve version effective at that first-seen K. The result
  is stored permanently. Entities first seen before the reserve existed are
  ``pre_reserve`` and never reserved.
* Rotation and fraction changes add versions for *new* entities only. Existing
  assignments never change except through two ledgered, explicit operations:
  ``reallocate_into_reserve`` (only unexposed, undeveloped entities, and
  uninspected ones under ``exclude``) and ``release`` (released entities keep
  their exposure history).
* Changing a monitoring definition, version or deployment cannot touch any of
  this: independence is never regained by reconfiguration.
"""
import hashlib
import hmac
import secrets as _secrets
import uuid
from decimal import Decimal

from psycopg.types.json import Jsonb

from ..errors import PlatformError

DEFAULT_FRACTION = Decimal('0.10')
DEFAULT_COVARIATE_POLICY = 'exclude'
STRICT = 'exclude'


def _lock(conn, catalog_id):
    conn.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))', (f'exposure:{catalog_id}',))


def _secret_name(org_id, reserve_id, version):
    return f'reserves/{uuid.UUID(str(org_id)).hex}/{uuid.UUID(str(reserve_id)).hex}/v{version}'


def _event(conn, scope, reserve_id, event, actor, detail=None):
    conn.execute('INSERT INTO reserve_events(org_id, reserve_id, event, detail, actor) VALUES (%s, %s, %s, %s, %s)',
                 (scope.org_id, reserve_id, event, Jsonb(detail or {}), actor))


def _head(conn, catalog_id):
    return conn.execute('SELECT head FROM catalog_heads WHERE catalog_id = %s', (catalog_id,)).fetchone()['head']


def create_reserve(db, secret_store, scope, catalog_id, namespace, *, actor, fraction=DEFAULT_FRACTION,
                   covariate_policy=DEFAULT_COVARIATE_POLICY):
    fraction = Decimal(str(fraction))
    if not Decimal(0) < fraction <= Decimal('0.5'):
        raise PlatformError('Reserve fraction must be in (0, 0.5].', 'invalid_reserve')
    if covariate_policy not in ('exclude', 'inspect'):
        raise PlatformError('Unknown covariate policy.', 'invalid_reserve')
    reserve_id = uuid.uuid4()
    name = _secret_name(scope.org_id, reserve_id, 1)
    secret_store.put(name, _secrets.token_bytes(32))
    with db.transaction() as conn:
        _lock(conn, catalog_id)
        conn.execute('''INSERT INTO reserves(org_id, catalog_id, id, namespace, covariate_policy, state)
                        VALUES (%s, %s, %s, %s, %s, 'active')''', (scope.org_id, catalog_id, reserve_id, namespace, covariate_policy))
        effective = _head(conn, catalog_id) + 1
        conn.execute('INSERT INTO reserve_versions(reserve_id, version, fraction, secret_name, effective_from_k) '
                     'VALUES (%s, 1, %s, %s, %s)', (reserve_id, fraction, name, effective))
        _event(conn, scope, reserve_id, 'created', actor, {'fraction': str(fraction), 'covariate_policy': covariate_policy,
                                                          'effective_from_k': effective})
    return reserve_id


def _add_version(db, secret_store, scope, reserve_id, *, actor, fraction=None, rotate=False, event):
    with db.transaction() as conn:
        reserve = conn.execute('SELECT * FROM reserves WHERE org_id = %s AND id = %s AND state = %s',
                               (scope.org_id, reserve_id, 'active')).fetchone()
        if reserve is None:
            raise PlatformError('Unknown or retired reserve.', 'unknown_reserve')
        _lock(conn, reserve['catalog_id'])
        last = conn.execute('SELECT * FROM reserve_versions WHERE reserve_id = %s ORDER BY version DESC LIMIT 1',
                            (reserve_id,)).fetchone()
        version = last['version'] + 1
        name = last['secret_name']
        if rotate:
            name = _secret_name(scope.org_id, reserve_id, version)
            secret_store.put(name, _secrets.token_bytes(32))
        new_fraction = Decimal(str(fraction)) if fraction is not None else last['fraction']
        if not Decimal(0) <= new_fraction <= Decimal('0.5'):
            raise PlatformError('Reserve fraction must be in [0, 0.5].', 'invalid_reserve')
        effective = _head(conn, reserve['catalog_id']) + 1
        conn.execute('INSERT INTO reserve_versions(reserve_id, version, fraction, secret_name, effective_from_k) '
                     'VALUES (%s, %s, %s, %s, %s)', (reserve_id, version, new_fraction, name, effective))
        _event(conn, scope, reserve_id, event, actor, {'version': version, 'fraction': str(new_fraction),
                                                      'effective_from_k': effective})
    return version


def rotate_secret(db, secret_store, scope, reserve_id, *, actor):
    """New secret for entities first seen from now on; existing assignments are untouched."""
    return _add_version(db, secret_store, scope, reserve_id, actor=actor, rotate=True, event='rotated')


def change_fraction(db, secret_store, scope, reserve_id, fraction, *, actor):
    """New fraction for entities first seen from now on (never re-exposes or re-reserves anyone)."""
    return _add_version(db, secret_store, scope, reserve_id, actor=actor, fraction=fraction, event='fraction_changed')


def _draw(secret, namespace, entity):
    mac = hmac.new(secret, namespace.encode() + b'\x00' + entity.encode(), hashlib.sha256).digest()
    return Decimal(int.from_bytes(mac[:8], 'big')) / Decimal(2**64)


def register_entities(conn, secret_store, scope, catalog_id, namespace, entities, first_seen_k):
    """Materialize reserve assignment for newly seen entities. Idempotent; never reassigns.

    ``entities`` is [(unit_hash_hex, entity_lexical)]. Call inside the publication
    transaction that first records them (holding the exposure lock), with its K.
    """
    reserve = conn.execute("SELECT id FROM reserves WHERE catalog_id = %s AND namespace = %s AND state = 'active'",
                           (catalog_id, namespace)).fetchone()
    versions = []
    if reserve is not None:
        versions = conn.execute('SELECT * FROM reserve_versions WHERE reserve_id = %s ORDER BY effective_from_k, version',
                                (reserve['id'],)).fetchall()
    applicable = [v for v in versions if v['effective_from_k'] <= first_seen_k]
    version = applicable[-1] if applicable else None
    secret = secret_store.get(version['secret_name']) if version else None
    rows = []
    for unit_hash, lexical in entities:
        if version is None:
            state = 'pre_reserve'
        else:
            state = 'reserve' if _draw(secret, namespace, lexical) < version['fraction'] else 'non_reserve'
        rows.append((scope.org_id, catalog_id, bytes.fromhex(unit_hash), namespace, first_seen_k, state,
                     reserve['id'] if version else None, version['version'] if version else None))
    with conn.cursor() as cur:
        cur.executemany(
            '''INSERT INTO entity_registry(org_id, catalog_id, unit_hash, namespace, first_seen_k, reserve_state,
                                           reserve_id, reserve_version)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT (catalog_id, unit_hash) DO NOTHING''', rows)
    return {state: sum(1 for r in rows if r[5] == state) for state in ('reserve', 'non_reserve', 'pre_reserve')}


def reallocate_into_reserve(db, scope, reserve_id, unit_hashes, *, reason, actor):
    """Move eligible existing entities into the reserve. Returns (moved, refused)."""
    if not reason:
        raise PlatformError('Reallocation requires a reason.', 'invalid_reserve')
    with db.transaction() as conn:
        reserve = conn.execute("SELECT * FROM reserves WHERE org_id = %s AND id = %s AND state = 'active'",
                               (scope.org_id, reserve_id)).fetchone()
        if reserve is None:
            raise PlatformError('Unknown or retired reserve.', 'unknown_reserve')
        _lock(conn, reserve['catalog_id'])
        moved, refused = [], []
        for unit in sorted(set(unit_hashes)):
            h = bytes.fromhex(unit)
            entity = conn.execute('SELECT reserve_state FROM entity_registry WHERE catalog_id = %s AND unit_hash = %s FOR UPDATE',
                                  (reserve['catalog_id'], h)).fetchone()
            exposure = conn.execute(
                '''SELECT bool_or(outcome_exposed) AS o, bool_or(development_use) AS d, bool_or(covariate_inspected) AS c
                   FROM exposure_registry WHERE catalog_id = %s AND member_kind = 'unit' AND hash = %s''',
                (reserve['catalog_id'], h)).fetchone()
            confirmed = conn.execute(
                "SELECT 1 FROM confirmation_members WHERE catalog_id = %s AND member_kind = 'unit' AND hash = %s LIMIT 1",
                (reserve['catalog_id'], h)).fetchone()
            eligible = (entity is not None and entity['reserve_state'] in ('non_reserve', 'pre_reserve')
                        and not exposure['o'] and not exposure['d'] and confirmed is None
                        and not (reserve['covariate_policy'] == STRICT and exposure['c']))
            if eligible:
                conn.execute("UPDATE entity_registry SET reserve_state = 'reserve', reserve_id = %s WHERE catalog_id = %s AND unit_hash = %s",
                             (reserve_id, reserve['catalog_id'], h))
                moved.append(unit)
            else:
                refused.append(unit)
        _event(conn, scope, reserve_id, 'reallocated', actor, {'moved': len(moved), 'refused': len(refused), 'reason': reason})
    return moved, refused


def release(db, scope, reserve_id, unit_hashes, *, reason, actor):
    """Release reserve entities explicitly. They keep their history; nothing is re-exposed silently."""
    if not reason:
        raise PlatformError('Release requires a reason.', 'invalid_reserve')
    with db.transaction() as conn:
        reserve = conn.execute('SELECT * FROM reserves WHERE org_id = %s AND id = %s', (scope.org_id, reserve_id)).fetchone()
        if reserve is None:
            raise PlatformError('Unknown reserve.', 'unknown_reserve')
        _lock(conn, reserve['catalog_id'])
        count = conn.execute(
            "UPDATE entity_registry SET reserve_state = 'released' WHERE catalog_id = %s AND unit_hash = ANY(%s) "
            "AND reserve_state = 'reserve'", (reserve['catalog_id'], [bytes.fromhex(u) for u in unit_hashes])).rowcount
        _event(conn, scope, reserve_id, 'released', actor, {'released': count, 'reason': reason})
    return count


def status(db, scope, reserve_id):
    with db.connect() as conn:
        reserve = conn.execute('SELECT * FROM reserves WHERE org_id = %s AND id = %s', (scope.org_id, reserve_id)).fetchone()
        if reserve is None:
            raise PlatformError('Unknown reserve.', 'unknown_reserve')
        counts = {r['reserve_state']: r['n'] for r in conn.execute(
            'SELECT reserve_state, count(*) AS n FROM entity_registry WHERE catalog_id = %s AND namespace = %s GROUP BY 1',
            (reserve['catalog_id'], reserve['namespace']))}
        spent = conn.execute(
            "SELECT count(*) AS n FROM entity_registry WHERE catalog_id = %s AND namespace = %s AND reserve_state = 'reserve' "
            'AND spent_by_use IS NOT NULL', (reserve['catalog_id'], reserve['namespace'])).fetchone()['n']
        versions = conn.execute('SELECT version, fraction, effective_from_k FROM reserve_versions WHERE reserve_id = %s '
                                'ORDER BY version', (reserve_id,)).fetchall()
    return {'reserve_id': str(reserve_id), 'namespace': reserve['namespace'], 'covariate_policy': reserve['covariate_policy'],
            'state': reserve['state'], 'counts': counts, 'spent': spent,
            'fresh_reserve': counts.get('reserve', 0) - spent,
            'versions': [{'version': v['version'], 'fraction': str(v['fraction']), 'effective_from_k': v['effective_from_k']}
                         for v in versions]}
