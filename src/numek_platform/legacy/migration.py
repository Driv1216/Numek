"""Catalog v2 -> platform migration state machine (R2.6).

planned -> frozen -> copying -> validating -> cutover_committed
                         \\________________/-> abandoned (only before cutover)

* PostgreSQL ``legacy_migrations`` is authoritative; the marker file in the
  v2 root mirrors it and is repaired from PostgreSQL on restart.
* The platform catalog stays ``migrating`` (refused by every reader, writer
  and API) until the cutover transaction.
* Resume recomputes the v2 inventory and aborts on any difference.
* The point of no return is the single cutover transaction, and it requires
  a passing validation report. There is no reverse migration afterwards; the
  migration is reported complete only after a post-cutover platform backup
  has been recorded.

Copying (publication replay in K order) and equivalence validation are
implemented in S3 together with the ConfidenceGuard storage port.
"""
import uuid

from psycopg.types.json import Jsonb

from ..errors import PlatformError
from ..evidence.catalogs import create_catalog
from . import catalog_v2

ORDER = ('planned', 'frozen', 'copying', 'validating', 'cutover_committed')


def _row(conn, scope, migration_id, lock=True):
    row = conn.execute('SELECT * FROM legacy_migrations WHERE org_id = %s AND id = %s' + (' FOR UPDATE' if lock else ''),
                       (scope.org_id, migration_id)).fetchone()
    if row is None:
        raise PlatformError('Unknown migration.', 'unknown_migration')
    return row


def _advance(conn, scope, migration_id, expected, new, **fields):
    row = _row(conn, scope, migration_id)
    if row['state'] not in expected:
        raise PlatformError(f"Migration is {row['state']}, not {'/'.join(expected)}.", 'migration_state')
    sets = ', '.join(f'{k} = %s' for k in fields)
    conn.execute(f"UPDATE legacy_migrations SET state = %s, updated_at = now(){', ' + sets if sets else ''} "
                 'WHERE org_id = %s AND id = %s',
                 (new, *[Jsonb(v) if isinstance(v, (dict, list)) else v for v in fields.values()], scope.org_id, migration_id))
    return row


def plan(db, scope, legacy_root, *, catalog_name):
    """Register a migration and its (still inaccessible) platform catalog."""
    stored = catalog_v2.settings(legacy_root)
    migration_id = uuid.uuid4()
    with db.transaction() as conn:
        catalog_id = create_catalog(
            conn, scope, catalog_name, state='migrating', analytical_instance_id=stored['instance_id'],
            branch_id=stored.get('branch_id') or stored['instance_id'],
            continuity_state=stored.get('exposure_continuity', 'unknown'),
            continuity_token=stored.get('exposure_continuity_token'), config=stored.get('config') or {})
        conn.execute(
            '''INSERT INTO legacy_migrations(org_id, id, catalog_id, legacy_root, legacy_instance_id, state)
               VALUES (%s, %s, %s, %s, %s, 'planned')''',
            (scope.org_id, migration_id, catalog_id, str(legacy_root), stored['instance_id']))
    return migration_id, catalog_id


def freeze(db, scope, migration_id):
    """Lock out legacy runtimes and record the inventory. Safe to repeat after a crash."""
    with db.connect() as conn:
        row = _row(conn, scope, migration_id, lock=False)
    if row['state'] not in ('planned', 'frozen'):
        raise PlatformError('Migration cannot be frozen in its current state.', 'migration_state')
    original = catalog_v2.freeze(row['legacy_root'], migration_id)          # durable lockout first
    body, inventory_digest = catalog_v2.inventory(row['legacy_root'])
    with db.transaction() as conn:
        _advance(conn, scope, migration_id, ('planned', 'frozen'), 'frozen', original_user_version=original,
                 inventory=body, inventory_digest=inventory_digest)
    catalog_v2.write_marker(row['legacy_root'], {'migration_id': str(migration_id), 'state': 'frozen',
                                                 'inventory_digest': inventory_digest})
    return inventory_digest


def check_source(db, scope, migration_id):
    """Resume guard: the frozen source must still match its recorded inventory."""
    with db.connect() as conn:
        row = _row(conn, scope, migration_id, lock=False)
    if catalog_v2.user_version(row['legacy_root']) != catalog_v2.FROZEN_VERSION:
        raise PlatformError('Legacy catalog is no longer frozen.', 'migration_source_changed')
    _body, current = catalog_v2.inventory(row['legacy_root'])
    if current != row['inventory_digest']:
        raise PlatformError('Legacy catalog changed after it was frozen.', 'migration_source_changed')
    return row


def begin_copy(db, scope, migration_id):
    check_source(db, scope, migration_id)
    with db.transaction() as conn:
        _advance(conn, scope, migration_id, ('frozen', 'copying'), 'copying')


def begin_validation(db, scope, migration_id):
    row = check_source(db, scope, migration_id)
    if row['last_migrated_k'] != (row['inventory'] or {}).get('head'):
        raise PlatformError('Not every legacy publication has been copied.', 'migration_incomplete')
    with db.transaction() as conn:
        _advance(conn, scope, migration_id, ('copying', 'validating'), 'validating')


def cutover(db, scope, migration_id, validation):
    """Point of no return: one transaction activates the catalog."""
    if not isinstance(validation, dict) or validation.get('passed') is not True:
        raise PlatformError('Cutover requires a passing validation report.', 'migration_validation')
    row = check_source(db, scope, migration_id)
    with db.transaction() as conn:
        _advance(conn, scope, migration_id, ('validating',), 'cutover_committed', validation=validation)
        updated = conn.execute("UPDATE catalogs SET state = 'active' WHERE org_id = %s AND id = %s AND state = 'migrating'",
                               (scope.org_id, row['catalog_id'])).rowcount
        if updated != 1:
            raise PlatformError('Platform catalog is not awaiting cutover.', 'migration_state')
    catalog_v2.write_marker(row['legacy_root'], {'migration_id': str(migration_id), 'state': 'cutover_committed',
                                                 'inventory_digest': row['inventory_digest']})


def record_post_cutover_backup(db, scope, migration_id, manifest):
    with db.transaction() as conn:
        row = _row(conn, scope, migration_id)
        if row['state'] != 'cutover_committed':
            raise PlatformError('Backup can only be recorded after cutover.', 'migration_state')
        conn.execute('UPDATE legacy_migrations SET post_cutover_backup = %s, updated_at = now() WHERE id = %s',
                     (Jsonb({'installation_id': manifest['installation_id'], 'created_at': manifest['created_at'],
                             'objects': manifest['objects']}), migration_id))


def status(db, scope, migration_id):
    with db.connect() as conn:
        row = _row(conn, scope, migration_id, lock=False)
    complete = row['state'] == 'cutover_committed' and row['post_cutover_backup'] is not None
    return {'state': row['state'], 'complete': complete, 'last_migrated_k': row['last_migrated_k'],
            'catalog_id': str(row['catalog_id'])}


def abandon(db, scope, migration_id):
    """Before cutover only: drop the platform copy, then restore the legacy catalog. Idempotent."""
    with db.transaction() as conn:
        row = _row(conn, scope, migration_id)
        if row['state'] == 'cutover_committed':
            raise PlatformError('Cutover is final; recover through platform backups.', 'migration_state')
        if row['state'] != 'abandoned':
            catalog_id = row['catalog_id']
            for table in ('fact_tombstones', 'fact_occurrences'):
                conn.execute(f'DELETE FROM {table} WHERE catalog_id = %s', (catalog_id,))
            conn.execute('DELETE FROM fact_index WHERE catalog_id = %s', (catalog_id,))
            conn.execute('DELETE FROM read_pins WHERE catalog_id = %s', (catalog_id,))
            conn.execute('DELETE FROM publications WHERE catalog_id = %s', (catalog_id,))
            mepoch = conn.execute('UPDATE catalog_maintenance SET epoch = epoch + 1 WHERE catalog_id = %s RETURNING epoch',
                                  (catalog_id,)).fetchone()['epoch']
            conn.execute(
                """UPDATE objects SET state = 'tombstoned', tombstoned_at = clock_timestamp(), tombstone_mepoch = %s
                   WHERE catalog_id = %s AND state IN ('active', 'pending')""", (mepoch, catalog_id))
            conn.execute("UPDATE catalogs SET state = 'retired', name = name || ':abandoned:' || id::text WHERE id = %s",
                         (catalog_id,))
            conn.execute("UPDATE legacy_migrations SET state = 'abandoned', updated_at = now() WHERE id = %s", (migration_id,))
    catalog_v2.unfreeze(row['legacy_root'], migration_id)
    catalog_v2.remove_marker(row['legacy_root'])
