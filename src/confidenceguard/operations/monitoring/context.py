"""Resolve a deployment to its system catalog, namespace, workspace and sources."""
from .. import registry


def deployment(installation, deployment_id):
    row = registry.deployment(installation, deployment_id)
    system = registry.system(installation, row['system_id'])
    with installation.db.connect() as conn:
        sources = [r['id'] for r in conn.execute(
            "SELECT id FROM ops_sources WHERE org_id = %s AND deployment_id = %s AND state = 'active' ORDER BY id",
            (installation.scope.org_id, deployment_id)).fetchall()]
    return {'deployment': row, 'system': system, 'catalog_id': system['catalog_id'], 'namespace': system['namespace'],
            'workspace': registry.workspace(installation, row['system_id']), 'sources': sources}
