"""Catalogs: one ordered evidence history (one K sequence) each."""
import uuid

from ..errors import PlatformError

STATES = ('migrating', 'active', 'retired')


def create_catalog(conn, scope, name, *, analytical_instance_id=None, branch_id=None,
                   continuity_state='unknown', continuity_token=None, state='active', config=None):
    if state not in STATES:
        raise ValueError(state)
    catalog_id = uuid.uuid4()
    from psycopg.types.json import Jsonb
    conn.execute(
        '''INSERT INTO catalogs(org_id, id, name, state, analytical_instance_id, branch_id,
                                continuity_state, continuity_token, config)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)''',
        (scope.org_id, catalog_id, name, state, analytical_instance_id or uuid.uuid4().hex,
         branch_id or uuid.uuid4().hex, continuity_state, continuity_token, Jsonb(config or {})))
    for table in ('catalog_heads', 'catalog_tombstones', 'catalog_maintenance'):
        conn.execute(f'INSERT INTO {table}(org_id, catalog_id) VALUES (%s, %s)', (scope.org_id, catalog_id))
    return catalog_id


def catalog(conn, scope, catalog_id, *, lock=None):
    suffix = {None: '', 'share': ' FOR SHARE', 'update': ' FOR UPDATE'}[lock]
    row = conn.execute('SELECT * FROM catalogs WHERE org_id = %s AND id = %s' + suffix,
                       (scope.org_id, catalog_id)).fetchone()
    if row is None:
        raise PlatformError('Unknown catalog.', 'unknown_catalog')
    return row


def require_active(row, *, allow_migrating=False):
    if row['state'] == 'active' or (allow_migrating and row['state'] == 'migrating'):
        return row
    raise PlatformError('This catalog is not available for use.', 'catalog_unavailable')


def head(conn, scope, catalog_id):
    return conn.execute('SELECT head FROM catalog_heads WHERE org_id = %s AND catalog_id = %s',
                        (scope.org_id, catalog_id)).fetchone()['head']
