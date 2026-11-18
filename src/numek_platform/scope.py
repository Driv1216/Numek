"""Organisation scoping.

Every repository function takes an :class:`OrgScope`. There is deliberately
no unscoped query API; hosted multi-tenancy (RLS, per-org databases) is a
later decision, but ownership boundaries exist from the first row.
"""
import uuid
from dataclasses import dataclass

from .errors import PlatformError


@dataclass(frozen=True)
class OrgScope:
    org_id: uuid.UUID

    def __post_init__(self):
        if not isinstance(self.org_id, uuid.UUID):
            object.__setattr__(self, 'org_id', uuid.UUID(str(self.org_id)))


def create_org(conn, name):
    org_id = uuid.uuid4()
    conn.execute('INSERT INTO orgs(id, name) VALUES (%s, %s)', (org_id, name))
    return OrgScope(org_id)


def get_org(conn, name):
    row = conn.execute('SELECT id FROM orgs WHERE name = %s', (name,)).fetchone()
    if row is None:
        raise PlatformError('Unknown organisation.', 'unknown_org')
    return OrgScope(row['id'])


def installation_id(conn):
    return conn.execute('SELECT installation_id FROM installation').fetchone()['installation_id']
