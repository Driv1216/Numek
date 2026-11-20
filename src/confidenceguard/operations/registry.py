"""Registration: systems (one evidence catalog each), deployments and versioned ingestion sources.

A system's catalog is a ConfidenceGuard platform catalog bound to the installation
(its database, object store and secrets), so one installation backup covers it and
reserve assignment can run at publication. Its working directory is
``<installation>/catalogs/<catalog id>``.
"""
import base64
import re
import uuid

from psycopg.types.json import Jsonb

from ..contracts import EvaluationError
from ..history_contracts import now
from .contracts import SourceContract

IDENTIFIER = re.compile(r'^[a-z0-9][a-z0-9_.-]{0,63}$')


def _identifier(value, label):
    if not isinstance(value, str) or not IDENTIFIER.fullmatch(value):
        raise EvaluationError(f'Invalid {label} identifier (lowercase letters, digits, . _ -).', 'invalid_identifier')
    return value


def _translate(exc):
    from ..platform_catalog import _translate as translate
    return translate(exc)


def register_system(installation, system_id, name, *, namespace=None):
    """Create a system and its evidence catalog (idempotent for an identical registration)."""
    from numek_platform.evidence.catalogs import create_catalog
    from ..history_storage import CATALOG_VERSION
    from ..history_contracts import WorkspaceConfig
    _identifier(system_id, 'system')
    namespace = namespace or system_id
    scope = installation.scope
    with installation.db.transaction() as conn:
        row = conn.execute('SELECT * FROM ops_systems WHERE org_id = %s AND id = %s', (scope.org_id, system_id)).fetchone()
        if row is not None:
            if (row['name'], row['namespace']) != (name, namespace):
                raise EvaluationError('This system is already registered differently.', 'registration_conflict')
            return dict(row)
        instance_id = uuid.uuid4().hex
        config = WorkspaceConfig(saving=True).to_dict()
        catalog_id = create_catalog(conn, scope, f'system:{system_id}', analytical_instance_id=instance_id,
                                    branch_id=uuid.uuid4().hex, continuity_state='complete', continuity_token=uuid.uuid4().hex,
                                    config=config)
        # Operations catalogs are governed from their first publication.
        conn.execute('UPDATE catalogs SET exposure_tracking = true WHERE id = %s', (catalog_id,))
        for key, value in {'instance_id': instance_id, 'config': config, 'retired': False, 'schema': CATALOG_VERSION,
                           'created_at': now(), 'system_id': system_id}.items():
            conn.execute('INSERT INTO cg_settings(catalog_id, key, value) VALUES (%s, %s, %s)', (catalog_id, key, Jsonb(value)))
        conn.execute('INSERT INTO ops_systems(org_id, id, name, catalog_id, namespace) VALUES (%s, %s, %s, %s, %s)',
                     (scope.org_id, system_id, name, catalog_id, namespace))
    _bind(installation, catalog_id)
    return system(installation, system_id)


def _bind(installation, catalog_id):
    """(Re)write a system catalog's binding: it derives from the database and installation, so a restored
    or relocated installation recreates it."""
    import json
    from ..platform_catalog import BINDING, BINDING_FORMAT, write_binding
    root = installation.catalog_root(catalog_id)
    wanted = {'format': BINDING_FORMAT, 'installation': str(installation.root), 'store': str(installation.store.root),
              'org_id': str(installation.scope.org_id), 'catalog_id': str(catalog_id)}
    path = root / BINDING
    if path.is_file() and json.loads(path.read_bytes()) == wanted:
        return root
    if path.is_file():
        path.unlink()
    write_binding(root, {k: v for k, v in wanted.items() if k not in ('org_id', 'catalog_id')}, installation.scope, catalog_id)
    return root


def system(installation, system_id):
    with installation.db.connect() as conn:
        row = conn.execute('SELECT * FROM ops_systems WHERE org_id = %s AND id = %s',
                           (installation.scope.org_id, system_id)).fetchone()
    if row is None:
        raise EvaluationError('Unknown system.', 'unknown_system')
    return dict(row)


def workspace(installation, system_id):
    """The system's evidence catalog as a ConfidenceGuard workspace (CG3–CG6 analyses run on it)."""
    from ..workspace import ReliabilityWorkspace
    return ReliabilityWorkspace(_bind(installation, system(installation, system_id)['catalog_id']))


def register_deployment(installation, system_id, deployment_id, name, *, tier=2, registered_identity=None,
                        attestation_public_key=None):
    """Register a deployment. ``registered_identity`` may name model id/version, ``artifact_digest`` and
    ``predictor_spec`` (a CG6 PredictorSpec, used for sampled output-consistency audits); the attestation key is
    a raw 32-byte Ed25519 public key (or its base64)."""
    _identifier(deployment_id, 'deployment')
    system(installation, system_id)
    if not isinstance(tier, int) or not 1 <= tier <= 4:
        raise EvaluationError('Tier must be 1 to 4.', 'invalid_registration')
    key = attestation_public_key
    if isinstance(key, str):
        key = base64.b64decode(key)
    if key is not None and len(key) != 32:
        raise EvaluationError('An Ed25519 public key has 32 bytes.', 'invalid_registration')
    scope = installation.scope
    with installation.db.transaction() as conn:
        row = conn.execute('SELECT * FROM ops_deployments WHERE org_id = %s AND id = %s', (scope.org_id, deployment_id)).fetchone()
        if row is not None:
            raise EvaluationError('This deployment is already registered.', 'registration_conflict')
        conn.execute('''INSERT INTO ops_deployments(org_id, id, system_id, name, tier, registered_identity, attestation_public_key)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)''',
                     (scope.org_id, deployment_id, system_id, name, tier, Jsonb(registered_identity or {}), key))
    return deployment(installation, deployment_id)


def deployment(installation, deployment_id):
    with installation.db.connect() as conn:
        row = conn.execute('SELECT * FROM ops_deployments WHERE org_id = %s AND id = %s',
                           (installation.scope.org_id, deployment_id)).fetchone()
    if row is None:
        raise EvaluationError('Unknown deployment.', 'unknown_deployment')
    return dict(row)


def register_source(installation, deployment_id, source_id, contract):
    """Register (or version) a source contract. An identical contract is a no-op; a changed one is a new
    version that applies to batches received from now on (earlier batches keep theirs)."""
    _identifier(source_id, 'source')
    contract = contract if isinstance(contract, SourceContract) else SourceContract.from_dict(contract)
    dep = deployment(installation, deployment_id)
    namespace = system(installation, dep['system_id'])['namespace']
    if contract.batch.get('namespace') != namespace:
        raise EvaluationError(f"The batch template must use the system namespace '{namespace}'.", 'invalid_contract')
    scope = installation.scope
    with installation.db.transaction() as conn:
        conn.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))', (f'ops:source:{scope.org_id}:{source_id}',))
        current = conn.execute("SELECT * FROM ops_sources WHERE org_id = %s AND id = %s AND state = 'active'",
                               (scope.org_id, source_id)).fetchone()
        if current is not None:
            if current['deployment_id'] != deployment_id:
                raise EvaluationError('This source belongs to another deployment.', 'registration_conflict')
            if current['contract_digest'] == contract.digest:
                return dict(current)
            conn.execute("UPDATE ops_sources SET state = 'retired' WHERE org_id = %s AND id = %s AND version = %s",
                         (scope.org_id, source_id, current['version']))
        version = (current['version'] + 1) if current else 1
        conn.execute('''INSERT INTO ops_sources(org_id, id, deployment_id, version, contract, contract_digest, state)
                        VALUES (%s, %s, %s, %s, %s, %s, 'active')''',
                     (scope.org_id, source_id, deployment_id, version, Jsonb(contract.to_dict()), contract.digest))
    if (dep['registered_identity'] or {}).get('predictor_spec'):
        from .identity import check_spec_compatibility
        check_spec_compatibility(installation, deployment_id, source_id)       # recorded with every new contract version
    return source(installation, source_id)


def source(installation, source_id, version=None):
    with installation.db.connect() as conn:
        if version is None:
            row = conn.execute("SELECT * FROM ops_sources WHERE org_id = %s AND id = %s AND state = 'active'",
                               (installation.scope.org_id, source_id)).fetchone()
        else:
            row = conn.execute('SELECT * FROM ops_sources WHERE org_id = %s AND id = %s AND version = %s',
                               (installation.scope.org_id, source_id, version)).fetchone()
    if row is None:
        raise EvaluationError('Unknown or retired source.', 'unknown_source')
    return dict(row)


def issue_ingest_token(installation, source_id, *, expires_in=None):
    """A token for one source, held by a dedicated service principal. Shown once; stored as a hash."""
    from numek_platform import identity
    from numek_platform.errors import PlatformError
    source(installation, source_id)
    scope = installation.scope
    try:
        with installation.db.transaction() as conn:
            name = f'ingest:{source_id}'
            row = conn.execute("SELECT id FROM principals WHERE org_id = %s AND name = %s AND kind = 'service'",
                               (scope.org_id, name)).fetchone()
            principal = (identity.get_principal(conn, scope, row['id']) if row is not None
                         else identity.create_principal(conn, scope, 'service', name))
            token, token_id = identity.issue_token(conn, scope, principal, [f'ingest:source:{source_id}'], expires_in=expires_in)
    except PlatformError as exc:
        raise _translate(exc) from exc
    return {'token': token, 'token_id': str(token_id), 'scope': f'ingest:source:{source_id}'}
