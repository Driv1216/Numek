"""Governed evidence access: the only path to outcome-bearing facts.

``resolve`` accepts a reservation and returns locators restricted, inside the
same REPEATABLE READ snapshot, to:

* outcome-bearing kinds only for events in the reservation's membership
  (never for covariate-inspection reservations);
* rows of sealed-reserve entities only when the reservation admitted those
  units (explicit consumption, or covariate policy ``inspect``).

The reservation must still belong to a live attempt (job fence) and was made
for the same catalog sequence K as the read pin. Withheld rows are counted, so
reports can disclose them. ``strict=True`` refuses instead of filtering.
"""
from dataclasses import dataclass

from ..errors import PlatformError
from ..evidence import reader as evidence_reader
from ..evidence.reader import _RESERVE_ROW
from .ledger import decode_membership


@dataclass(frozen=True)
class GovernedResult:
    locators: list
    withheld: int


def _reservation(db, reservation):
    with db.connect() as conn:
        row = conn.execute(
            '''SELECT u.*, o.physical_key, o.sha256, o.bytes,
                      (u.job_id IS NULL OR EXISTS (SELECT 1 FROM jobs j WHERE j.id = u.job_id AND j.fence = u.fence
                                                   AND j.state = 'running')) AS live
               FROM evidence_uses u JOIN objects o ON o.id = u.membership_object
               WHERE u.catalog_id = %s AND u.id = %s''', (reservation.catalog_id, reservation.id)).fetchone()
    if row is None:
        raise PlatformError('Unknown evidence-use reservation.', 'unknown_reservation')
    if not row['live'] or (row['job_id'], row['fence']) != (reservation.job_id, reservation.fence):
        raise PlatformError('Reservation no longer belongs to a live attempt.', 'reservation_owner')
    return row


def membership_from_index(db, read_pin, *, kinds=('opportunity',), event_tick_range=None, require_outcome=True,
                          namespace=None):
    """Membership pairs (event_hash, unit_hash) from non-outcome fields only.

    Uses identity hashes, clocks and the *existence* of an outcome fact at K;
    never outcome values or statuses. A conservative superset of what a reader
    may then open.
    """
    where = ['f.catalog_id = %s', 'p.sequence <= %s', 'f.kind = ANY(%s)', 'f.event_hash IS NOT NULL',
             'f.entity_hash IS NOT NULL']
    params = [read_pin.catalog_id, read_pin.k, list(kinds)]
    if namespace is not None:
        where.append('f.namespace = %s')
        params.append(namespace)
    if event_tick_range is not None:
        where.append('f.event_tick >= %s AND f.event_tick < %s')
        params.extend(event_tick_range)
    if require_outcome:
        where.append('''EXISTS (SELECT 1 FROM fact_index o JOIN publications op ON op.id = o.publication_id
                                WHERE o.catalog_id = f.catalog_id AND o.kind = 'outcome'
                                AND (o.event_hash = f.event_hash OR (f.target_key IS NOT NULL AND o.target_key = f.target_key))
                                AND op.sequence <= %s)''')
        params.append(read_pin.k)
    with db.transaction('repeatable_read', read_only=True) as conn:
        rows = conn.execute(
            f'''SELECT DISTINCT f.event_hash, f.entity_hash, f.target_key FROM fact_index f
                JOIN publications p ON p.id = f.publication_id WHERE {' AND '.join(where)}''', params).fetchall()
    return sorted((bytes(r['event_hash']).hex(), bytes(r['entity_hash']).hex(),
                   None if r['target_key'] is None else bytes(r['target_key']).hex()) for r in rows)


def resolve(db, store, reservation, read_pin, *, strict=False, **filters):
    row = _reservation(db, reservation)
    # A reservation covers knowledge up to its K; reading an earlier snapshot
    # (for example a frozen prediction snapshot) is within it, a later one is not.
    if row['read_k'] is not None and read_pin.k > row['read_k']:
        raise PlatformError('Reservation was made for an earlier catalog snapshot.', 'reservation_snapshot')
    if read_pin.catalog_id != reservation.catalog_id:
        raise PlatformError('Read pin belongs to another catalog.', 'pin_mismatch')
    events, units, targets = decode_membership(store.read_verified(row['physical_key'], bytes(row['sha256']).hex(),
                                                                   row['bytes']))
    covariates_only = row['kind'] == 'covariate_inspection'

    def governance(conn):
        conn.execute('CREATE TEMP TABLE _gov_events (hash bytea PRIMARY KEY) ON COMMIT DROP')
        conn.execute('CREATE TEMP TABLE _gov_units (hash bytea PRIMARY KEY) ON COMMIT DROP')
        conn.execute('CREATE TEMP TABLE _gov_targets (hash bytea PRIMARY KEY) ON COMMIT DROP')
        with conn.cursor().copy('COPY _gov_targets (hash) FROM STDIN') as copy:
            for value in targets:
                copy.write_row((bytes.fromhex(value),))
        with conn.cursor().copy('COPY _gov_events (hash) FROM STDIN') as copy:
            for value in events:
                copy.write_row((bytes.fromhex(value),))
        with conn.cursor().copy('COPY _gov_units (hash) FROM STDIN') as copy:
            for value in units:
                copy.write_row((bytes.fromhex(value),))
        if covariates_only:
            protected = 'NOT f.protected'
        else:
            protected = ('(NOT f.protected OR f.event_hash IN (SELECT hash FROM _gov_events) '
                         'OR f.target_key IN (SELECT hash FROM _gov_targets))')
        reserve = f'(NOT {_RESERVE_ROW} OR f.entity_hash IN (SELECT hash FROM _gov_units))'
        return f'{protected} AND {reserve}', []

    allowed = evidence_reader.resolve(db, read_pin, access='governed', _governance=governance, **filters)
    everything = evidence_reader.resolve(db, read_pin, access='maintenance', **filters)
    withheld = len(everything) - len(allowed)
    if strict and withheld:
        raise PlatformError('The selection includes evidence outside this reservation.', 'reservation_membership')
    return GovernedResult(allowed, withheld)
