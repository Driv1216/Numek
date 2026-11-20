"""ConfidenceGuard catalog on the NUMEK evidence platform (CG7 S3).

``PlatformCatalog`` is a :class:`history_storage.Catalog` whose durable state
lives in PostgreSQL and the platform object store instead of a workspace
SQLite file. ``Catalog(root)`` returns one automatically when ``root`` holds a
``platform.json`` binding, so every existing call site (including supervised
worker children) opens the right implementation.

Preserved exactly:

* the worker-side capture protocol (``EvidenceWriter`` staging, index and
  manifest) and every ``commit_capture`` validation: record and directory
  identities; correction predecessor, reason, availability and chronology;
  prediction role, entity and authority immutability; revision conflicts;
  duplicate content equality; purged re-import refusal; vector-digest
  deduplication without resurrection; fact, object and vector dependencies;
  blob descriptors; variant and predictor-version immutability; assessments;
* identities: v2 object ids (32 hex) are the platform object UUIDs, operation
  ids are publication UUIDs, and K is the platform catalog sequence (one
  publication per operation);
* receipts, request-id idempotency and error codes.

Changed deliberately:

* no whole-operation file lock: concurrency is the platform's (fenced
  publication, global identity constraints, K assigned at commit);
* outcome-bearing facts are readable only under an evidence-use reservation
  (``governance``), recorded before access;
* integrity is verified on every read over the exact bytes consumed.

Not yet ported (raise ``platform_unported``): raw SQLite access, deletion,
backup/restore through this class, and typed-feature/vector object reads.
Those land in later S3 steps.
"""
import contextlib
import hashlib
import os
import shutil
import threading
import uuid
from dataclasses import asdict
from pathlib import Path

from .contracts import EvaluationError, digest, strict_json
from .history_contracts import HistoricalEvidenceManifest, WorkspaceConfig, now
from .history_storage import (CATALOG_VERSION, Catalog, _safe_name, file_digest, fsync_directory, private_directory,
                              private_file, serialized)

BINDING = 'platform.json'
BINDING_FORMAT = 'numek_platform_binding/1'
DSN_ENV = 'NUMEK_PLATFORM_DSN'
ORG_NAME = 'local'
FACT_KINDS_WITH_EVENTS = ('opportunity', 'prediction', 'context', 'sample')
# Reservations adopted by worker processes, keyed by workspace root. A supervised
# worker is a fresh process per job, so this never outlives the attempt it serves.
_WORKER_GOVERNANCE = {}
# Scoped study authority inherited by this process's access reservations: the id
# of a confirmation-class evidence use (see ``study_authority``).
_STUDY_AUTHORITY = {'use_id': None}


# Admission refusals that ingestion quarantines per fact instead of refusing a whole capture.
QUARANTINABLE = ('historical_identity_conflict', 'historical_evidence_unavailable', 'historical_role_reassignment',
                 'correction_authority', 'correction_chronology', 'correction_predecessor')
_ATTEMPT_SCOPES = []      # stack of in-process phase scopes (lists of open worker attempts)
# Catalogs a v2 -> platform migration is validating in this process. Only the migration
# job reads a ``migrating`` catalog (in process); every other reader is refused.
_MIGRATION_VALIDATION = set()


@contextlib.contextmanager
def process_scope():
    """Isolate process-local governance for one in-process phase (see ``execution_context``).

    A spawned phase starts with no worker reservation or study authority and its
    access-reservation attempts close when the process exits. An in-process
    phase gets the same: fresh state on entry, its own attempts completed on
    exit, and the caller's state restored afterwards.
    """
    saved_governance = dict(_WORKER_GOVERNANCE)
    saved_authority = _STUDY_AUTHORITY['use_id']
    _WORKER_GOVERNANCE.clear()
    _STUDY_AUTHORITY['use_id'] = None
    attempts = []
    _ATTEMPT_SCOPES.append(attempts)
    try:
        yield
    finally:
        _ATTEMPT_SCOPES.remove(attempts)
        for dsn, lease in attempts:
            PlatformCatalog._close_attempt(dsn, lease)
        _WORKER_GOVERNANCE.clear()
        _WORKER_GOVERNANCE.update(saved_governance)
        _STUDY_AUTHORITY['use_id'] = saved_authority


def governed_call(authority, operation, *arguments, progress=None):
    """Run a supervised worker operation under a study's authority (picklable entry point)."""
    with study_authority(authority):
        return operation(*arguments, progress=progress)


@contextlib.contextmanager
def study_authority(reservation):
    """Let worker reads inside this block see the sealed-reserve units consumed by ``reservation``.

    ``reservation`` is a confirmation-class evidence-use receipt (CG4
    confirmation, numerical recomputation and scheduled looks; CG5 policy
    assessment and scheduled looks). The ledger bounds what the authority
    admits (same study family, the reservation's own membership, its
    snapshot); other receipts and v2 workspaces grant nothing.
    """
    # Only confirmation-class receipts confer authority (other receipts grant nothing).
    use_id = (reservation.get('evidence_use_id') if isinstance(reservation, dict)
              and reservation.get('evidence_kind') in ('confirmation', 'numerical_recomputation') else None)
    previous = _STUDY_AUTHORITY['use_id']
    _STUDY_AUTHORITY['use_id'] = use_id
    try:
        yield use_id
    finally:
        _STUDY_AUTHORITY['use_id'] = previous


def platform_bound(root):
    return (Path(root) / BINDING).is_file()


def _uuid(oid):
    return uuid.UUID(hex=_safe_name(oid))


def _translate(exc):
    """Map platform errors onto ConfidenceGuard's error type, keeping their codes."""
    from numek_platform.errors import PlatformError
    if isinstance(exc, PlatformError):
        error = EvaluationError(str(exc), exc.code)
        error.retryable = exc.retryable
        return error
    return exc


def installation(root):
    """The platform installation a workspace at ``root`` uses: (database, org scope, binding base).

    ``NUMEK_PLATFORM_DSN`` names a shared installation (the binding stores the
    variable name, never the connection string); otherwise the workspace gets its
    own P-LOCAL cluster under ``root/platform``. The schema is migrated and the
    ConfidenceGuard organisation is created on first use.
    """
    from numek_platform.db import Database
    from numek_platform.db.migrator import migrate
    from numek_platform.errors import PlatformError
    from numek_platform.scope import create_org, get_org
    root = Path(root)
    binding = {'format': BINDING_FORMAT, 'store': 'platform-objects'}
    if os.environ.get(DSN_ENV):
        binding['dsn_env'] = DSN_ENV
        dsn = os.environ[DSN_ENV]
    else:
        from numek_platform.local import LocalCluster
        cluster = LocalCluster(root / 'platform')
        cluster.start()
        binding['local_cluster'] = 'platform'
        dsn = cluster.dsn()
    database = Database(dsn)
    migrate(database)
    with database.transaction() as conn:
        conn.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))', ('numek:org:' + ORG_NAME,))
        try:
            scope = get_org(conn, ORG_NAME)
        except PlatformError:
            scope = create_org(conn, ORG_NAME)
    return database, scope, binding


def write_binding(root, binding, scope, catalog_id):
    """Durably bind ``root`` to its platform catalog (``platform.json``)."""
    value = dict(binding, org_id=str(scope.org_id), catalog_id=str(catalog_id))
    with private_file(Path(root) / BINDING) as stream:
        stream.write(serialized(value))
        stream.flush()
        os.fsync(stream.fileno())
    fsync_directory(Path(root))
    return value


class PlatformCatalog(Catalog):
    """Platform-backed ConfidenceGuard catalog (see module docstring)."""

    # Construction --------------------------------------------------------------
    def __init__(self, root, *, create=False, config=None):
        from numek_platform.db import Database
        from numek_platform.objects import LocalObjectStore
        self.root = private_directory(Path(root).absolute())
        self._guard = threading.RLock()
        self._verified = {}
        self._leases = {}
        self._governance = None
        self._lexical_entity = {}
        self.operation_path = self.root / '.operation.lock'
        self.objects_lock = self.root / '.objects.lock'
        for lock in (self.operation_path, self.objects_lock):
            if not lock.exists():
                with private_file(lock):
                    pass
        private_directory(self.root / 'staging')
        private_directory(self.root / 'objects')        # materialized verified copies (v2 layout)
        if create and not platform_bound(self.root):
            if (self.root / 'catalog.sqlite3').exists():
                raise EvaluationError('A catalog v2 workspace already exists here; migrate it instead.', 'workspace_exists')
            self._create_binding(config or WorkspaceConfig())
        binding = strict_json((self.root / BINDING).read_bytes())
        if binding.get('format') != BINDING_FORMAT:
            raise EvaluationError('Unsupported platform binding.', 'catalog_version')
        self.binding = binding
        self.installation = None
        if binding.get('installation'):
            from numek_platform.installation import Installation
            self.installation = Installation(binding['installation'])
        self.db = Database(self._dsn(binding, self.root), application_name='confidenceguard')
        self.store = (self.installation.store if self.installation is not None
                      else LocalObjectStore(self.root / binding['store']))
        # Reserve assignment needs the installation's secrets; standalone workspaces have none.
        self.secrets = self.installation.secrets if self.installation is not None else None
        from numek_platform.scope import OrgScope
        self.scope = OrgScope(uuid.UUID(binding['org_id']))
        self.catalog_id = uuid.UUID(binding['catalog_id'])
        self.catalog_version = CATALOG_VERSION
        self._validate()

    @staticmethod
    def _dsn(binding, root):
        if binding.get('installation'):
            from numek_platform.installation import Installation
            return Installation(binding['installation']).dsn()
        if binding.get('dsn_env'):
            dsn = os.environ.get(binding['dsn_env'])
            if not dsn:
                raise EvaluationError('The platform connection for this workspace is not configured.', 'platform_unavailable')
            return dsn
        from numek_platform.local import LocalCluster
        relative = Path(binding['local_cluster'])
        if relative.is_absolute() or '..' in relative.parts:
            raise EvaluationError('Unsafe platform binding.', 'unsafe_workspace')
        cluster = LocalCluster(Path(root) / relative)
        if not cluster.running():
            cluster.start()
        return cluster.dsn()

    def _create_binding(self, config):
        database, scope, binding = installation(self.root)
        instance_id = uuid.uuid4().hex
        from numek_platform.evidence.catalogs import create_catalog
        from psycopg.types.json import Jsonb
        with database.transaction() as conn:
            catalog_id = create_catalog(conn, scope, f'workspace:{instance_id}', analytical_instance_id=instance_id,
                                        branch_id=uuid.uuid4().hex, continuity_state='unknown',
                                        continuity_token=uuid.uuid4().hex, config=config.to_dict())
            conn.execute('UPDATE catalogs SET exposure_tracking = false WHERE id = %s', (catalog_id,))
            for key, value in {'instance_id': instance_id, 'config': config.to_dict(), 'retired': False,
                               'schema': CATALOG_VERSION, 'created_at': now()}.items():
                conn.execute('INSERT INTO cg_settings(catalog_id, key, value) VALUES (%s, %s, %s)',
                             (catalog_id, key, Jsonb(value)))
        write_binding(self.root, binding, scope, catalog_id)

    def _setting(self, conn, key):
        row = conn.execute('SELECT value FROM cg_settings WHERE catalog_id = %s AND key = %s', (self.catalog_id, key)).fetchone()
        return None if row is None else row['value']

    def _validate(self):
        with self.db.connect() as conn:
            row = conn.execute('SELECT state FROM catalogs WHERE id = %s', (self.catalog_id,)).fetchone()
            if row is None:
                raise EvaluationError('Workspace catalog is missing from the platform.', 'workspace_missing')
            # Only a ConfidenceGuard purge (which sets the retired setting) may finish physical removal;
            # a catalog retired for another reason (an abandoned migration) is simply unavailable.
            retired = bool(self._setting(conn, 'retired'))
            if row['state'] == 'retired' and not retired:
                raise EvaluationError('This catalog is not available for use.', 'catalog_unavailable')
        if retired:
            # The purge committed atomically; finish physical removal if the process died before it.
            self._retire_files()
            raise EvaluationError('Workspace was retired.', 'workspace_retired')
        with self.db.connect() as conn:
            self._migrating = row['state'] == 'migrating' and self.catalog_id in _MIGRATION_VALIDATION
            if row['state'] != 'active' and not self._migrating:
                raise EvaluationError('This catalog is not available for use.', 'catalog_unavailable')
            self.instance_id = self._setting(conn, 'instance_id')
            self.config = WorkspaceConfig.from_dict(self._setting(conn, 'config'))

    # Unported SQLite surface ----------------------------------------------------
    def _connect(self):
        raise EvaluationError('This workspace runs on the platform; this operation is not yet ported.', 'platform_unported')


    # Deletion (port of v2 deletion_preview / delete) ----------------------------------------------------
    def _object_kind(self, conn, object_hex):
        row = conn.execute('SELECT kind, operation_id FROM cg_objects WHERE catalog_id = %s AND object_id = %s',
                           (self.catalog_id, _uuid(object_hex))).fetchone()
        return (row['kind'], row['operation_id'].hex) if row else (None, None)

    def _operation_objects(self, conn, operation_hex, kinds=None):
        sql = 'SELECT object_id FROM cg_objects WHERE catalog_id = %s AND operation_id = %s'
        params = [self.catalog_id, _uuid(operation_hex)]
        if kinds:
            sql += ' AND kind = ANY(%s)'
            params.append(list(kinds))
        return {r['object_id'].hex for r in conn.execute(sql, params)}

    def _occurring_operations(self, conn, object_hexes):
        if not object_hexes:
            return set()
        return {r['publication_id'].hex for r in conn.execute(
            '''SELECT DISTINCT oc.publication_id FROM fact_index f JOIN fact_occurrences oc ON oc.catalog_id = f.catalog_id
               AND oc.kind = f.kind AND oc.key = f.key AND oc.revision = f.revision
               WHERE f.catalog_id = %s AND f.object_id = ANY(%s)''', (self.catalog_id, [_uuid(o) for o in object_hexes]))}

    def deletion_preview(self, *, object_ids=(), assessment_ids=(), batch_ids=(), purge=False):
        if not isinstance(purge, bool):
            raise EvaluationError('purge must be boolean.')
        status = self.status()
        owned = ('cg4_packet_part', 'cg6_artifact', 'cg6_artifact_descriptor')
        with self.db.connect() as conn:
            objects = {_safe_name(o) for o in object_ids}
            for bid in batch_ids:
                if not conn.execute('SELECT 1 FROM publications WHERE catalog_id = %s AND id = %s',
                                    (self.catalog_id, _uuid(bid))).fetchone():
                    raise EvaluationError('Unknown batch association.', 'unknown_batch')
            for aid in assessment_ids:
                if not conn.execute('SELECT 1 FROM cg_assessments WHERE catalog_id = %s AND id = %s', (self.catalog_id, aid)).fetchone():
                    raise EvaluationError('Unknown assessment.', 'assessment_unavailable')
                objects |= self.object_ids_for_key('assessment', digest([aid]))
            for oid in tuple(objects):
                kind, operation = self._object_kind(conn, oid)
                if kind == 'assessment':
                    objects |= self._operation_objects(conn, operation, owned)
            if purge:
                objects = {r['id'].hex for r in conn.execute(
                    "SELECT id FROM objects WHERE catalog_id = %s AND state IN ('active', 'pending')", (self.catalog_id,))}
            for oid in objects:
                if not conn.execute('SELECT 1 FROM objects WHERE catalog_id = %s AND id = %s', (self.catalog_id, _uuid(oid))).fetchone():
                    raise EvaluationError('Unknown deletion object.', 'unknown_object')
            if not purge and conn.execute('SELECT 1 FROM evidence_uses WHERE catalog_id = %s AND membership_object = ANY(%s) LIMIT 1',
                                          (self.catalog_id, [_uuid(o) for o in objects])).fetchone():
                # Exposure records are durable governance: deleting one would break its
                # reservation and could suggest regained freshness. A purge retires them
                # with the catalog; exposure history survives it.
                raise EvaluationError('Evidence-use records are durable governance and cannot be deleted.',
                                      'governance_record')
            evidence_objects = [o for o in objects if self._object_kind(conn, o)[0] != 'assessment']
            if objects:
                expanded = True
                while expanded:
                    before = len(objects)
                    for oid in tuple(objects):
                        kind, operation = self._object_kind(conn, oid)
                        if kind == 'assessment':
                            objects |= self._operation_objects(conn, operation, owned)
                    captures = self._occurring_operations(conn, [o for o in objects if self._object_kind(conn, o)[0] != 'assessment'])
                    for operation in captures:
                        objects |= self._operation_objects(conn, operation)
                    for row in conn.execute('SELECT object_id, depends_on FROM cg_artifact_dependencies WHERE catalog_id = %s',
                                            (self.catalog_id,)):
                        if row['depends_on'].hex in objects:
                            objects.add(row['object_id'].hex)
                    expanded = len(objects) != before
            affected = self._occurring_operations(conn, objects)
            impacted = [r['id'] for r in conn.execute("SELECT id FROM cg_assessments WHERE catalog_id = %s AND state = 'active' ORDER BY id",
                                                      (self.catalog_id,))] if evidence_objects else []
        plan = {'id': uuid.uuid4().hex, 'instance_id': self.instance_id, 'catalog_sequence': status['catalog_sequence'],
                'object_ids': sorted(objects), 'assessment_ids': list(assessment_ids), 'batch_ids': list(batch_ids),
                'affected_batches': sorted(affected), 'potentially_impacted_assessments': impacted, 'purge': bool(purge),
                'retained_assessments_may_contain_values': True}
        plan['confirmation'] = digest(plan)
        return plan

    def delete(self, plan):
        from psycopg.types.json import Jsonb
        from numek_platform.execution import jobs
        from numek_platform.execution.jobs import assert_fence
        supplied = dict(plan)
        confirmation = supplied.pop('confirmation', None)
        if confirmation != digest(supplied) or plan.get('instance_id') != self.instance_id:
            raise EvaluationError('Deletion preview differs.', 'stale_deletion')
        with self.operation():
            if self.head() != plan['catalog_sequence']:
                raise EvaluationError('Catalog changed; inspect a new deletion preview.', 'stale_deletion')
            current = self.deletion_preview(object_ids=plan['object_ids'], assessment_ids=plan['assessment_ids'],
                                            batch_ids=plan['batch_ids'], purge=plan['purge'])
            for field in ('object_ids', 'affected_batches', 'potentially_impacted_assessments'):
                if current[field] != plan.get(field):
                    raise EvaluationError('Deletion dependencies differ; inspect a new preview.', 'stale_deletion')
            with self.db.connect() as conn:
                lease, _row = jobs.start_inline(conn, self.scope, 'cg_deletion', idempotency_key='cg-deletion:' + plan['id'],
                                                owner=f'confidenceguard:{os.getpid()}')
            object_uuids = sorted((_uuid(o) for o in plan['object_ids']), key=str)
            with self.db.transaction() as conn:                                     # global lock order
                assert_fence(conn, lease)                                           # 1 job
                conn.execute('SELECT id FROM catalogs WHERE id = %s ' + ('FOR UPDATE' if plan['purge'] else 'FOR SHARE'),
                             (self.catalog_id,))                                    # 3 catalog
                if object_uuids:
                    conn.execute('SELECT id FROM objects WHERE id = ANY(%s) ORDER BY id FOR UPDATE', (object_uuids,))  # 4
                conn.execute("INSERT INTO cg_deletions(catalog_id, id, plan, state) VALUES (%s, %s, %s, 'pending')",
                             (self.catalog_id, plan['id'], Jsonb(plan)))
                epoch = conn.execute('UPDATE catalog_tombstones SET epoch = epoch + 1 WHERE catalog_id = %s RETURNING epoch',
                                     (self.catalog_id,)).fetchone()['epoch']        # 5
                mepoch = conn.execute('UPDATE catalog_maintenance SET epoch = epoch + 1 WHERE catalog_id = %s RETURNING epoch',
                                      (self.catalog_id,)).fetchone()['epoch']       # 6
                head = conn.execute('SELECT head FROM catalog_heads WHERE catalog_id = %s FOR UPDATE',
                                    (self.catalog_id,)).fetchone()['head']          # 7
                publication = uuid.uuid4()
                conn.execute('''INSERT INTO publications(org_id, catalog_id, id, request_id, request_digest, kind, job_id, fence,
                                                         sequence, receipt, committed_at)
                                VALUES (%s, %s, %s, %s, %s, 'cg_deletion', %s, %s, %s, %s, clock_timestamp())''',
                             (self.scope.org_id, self.catalog_id, publication, 'deletion:' + plan['id'], confirmation,
                              lease.job_id, lease.fence, head + 1, Jsonb({'cg': {'deletion_id': plan['id']}})))
                if object_uuids:
                    conn.execute('''INSERT INTO fact_tombstones(org_id, catalog_id, kind, key, revision, epoch, publication_id)
                                    SELECT %s, catalog_id, kind, key, revision, %s, %s FROM fact_index
                                    WHERE catalog_id = %s AND object_id = ANY(%s) ON CONFLICT DO NOTHING''',
                                 (self.scope.org_id, epoch, publication, self.catalog_id, object_uuids))
                    conn.execute("UPDATE objects SET state = 'tombstoned', tombstoned_at = clock_timestamp(), tombstone_mepoch = %s "
                                 "WHERE id = ANY(%s) AND state IN ('active', 'pending')", (mepoch, object_uuids))
                    conn.execute("UPDATE cg_assessments SET state = 'deleted' WHERE catalog_id = %s AND object_id = ANY(%s)",
                                 (self.catalog_id, object_uuids))
                    # v2 semantics: removing evidence leaves exposure continuity incomplete.
                    conn.execute("UPDATE catalogs SET continuity_state = 'incomplete', continuity_token = %s WHERE id = %s",
                                 (uuid.uuid4().hex, self.catalog_id))
                if plan['batch_ids']:
                    conn.execute('DELETE FROM fact_occurrences WHERE catalog_id = %s AND publication_id = ANY(%s)',
                                 (self.catalog_id, [_uuid(b) for b in plan['batch_ids']]))
                if plan['purge']:
                    conn.execute("UPDATE cg_settings SET value = 'true'::jsonb WHERE catalog_id = %s AND key = 'retired'",
                                 (self.catalog_id,))
                    conn.execute("UPDATE catalogs SET state = 'retired' WHERE id = %s", (self.catalog_id,))
                conn.execute('UPDATE catalog_heads SET head = %s WHERE catalog_id = %s', (head + 1, self.catalog_id))
                conn.execute("UPDATE cg_deletions SET state = 'completed' WHERE catalog_id = %s AND id = %s",
                             (self.catalog_id, plan['id']))
            with self.db.connect() as conn:
                jobs.complete(conn, lease, {'deleted_objects': len(object_uuids)})
        from .evidence_use import forget_session_uses
        # v2 parity: release this workspace's process-local untracked observations
        # (durable platform uses stay recorded; absence is never freshness).
        forget_session_uses(self.instance_id, purge=plan['purge'], untracked=bool(plan['object_ids']))
        self._fault('deletion_tombstoned')
        if plan['purge']:
            self._retire_files()
        else:
            self._reclaim_deleted(plan['object_ids'])
        return {'deleted_objects': len(plan['object_ids']), 'workspace_retired': plan['purge']}

    def _reclaim_deleted(self, object_ids):
        """Physical removal: platform GC (pins and holds still protect live readers), then local copies."""
        from numek_platform.evidence.gc import GarbageCollector
        import datetime as dt
        GarbageCollector(self.db, self.store, grace=dt.timedelta(0), catalog_id=self.catalog_id).run_once()
        for oid in object_ids:      # materialized copies, and frozen catalog v2 bytes of a migrated workspace
            for suffix in ('.cgblob', '.parquet', '.jsonl', '.npy'):
                path = self.root / 'objects' / (oid + suffix)
                if path.is_file() and not path.is_symlink():
                    path.unlink()

    def _retire_files(self):
        """Complete a committed full purge (idempotent): reclaim bytes, empty local folders, mark retired."""
        from .evidence_use import forget_session_uses
        with self.db.connect() as conn:
            owner = self._setting(conn, 'instance_id')
        forget_session_uses(owner, purge=True)
        self._reclaim_deleted(())
        for folder in ('objects', 'staging'):
            target = self.root / folder
            if target.is_dir() and not target.is_symlink():
                for path in target.iterdir():
                    if path.is_dir() and not path.is_symlink():
                        shutil.rmtree(path)
                    else:
                        path.unlink()
                fsync_directory(target)
        # A migrated workspace's frozen catalog v2 goes with it: a purge leaves no copy behind.
        for name in ('catalog.sqlite3', 'catalog.sqlite3-wal', 'catalog.sqlite3-shm', '.numek-migration.json'):
            path = self.root / name
            if path.is_file() and not path.is_symlink():
                path.unlink()
        marker = self.root / '.retired'
        if not marker.exists():
            marker.write_bytes(b'workspace retired\n')
            os.chmod(marker, 0o600)
        fsync_directory(self.root)

    # Backup and restore (workspaces with their own P-LOCAL cluster) ------------------------------------------
    def backup(self, destination):
        from numek_platform.backup import create_backup
        destination = Path(destination).absolute()
        if self.binding.get('dsn_env'):
            # A shared installation's backup is the installation's own procedure; it does not
            # yet cover the object stores of ConfidenceGuard workspaces bound to it.
            raise EvaluationError('Workspace backup is available only for workspaces with their own platform cluster; '
                                  'this workspace shares a platform installation.', 'backup_scope')
        if destination == self.root or self.root in destination.parents or destination in self.root.parents or destination.exists():
            raise EvaluationError('Choose a new backup destination outside the workspace.', 'backup_destination')
        private_directory(destination)
        manifest = create_backup(self.db, self.store, None, destination / 'platform', passphrase=None)
        with private_file(destination / BINDING) as stream:
            stream.write(serialized(self.binding))
        summary = {'schema_version': 'confidenceguard.workspace_backup/2.0', 'instance_id': self.instance_id,
                   'catalog_sequence': self.head(), 'platform_manifest': digest(manifest), 'storage': 'numek_platform',
                   'files': sorted(manifest['files'])}   # v2 manifest parity: what the backup holds
        summary['content_digest'] = digest(summary)
        with private_file(destination / 'backup.json') as stream:
            stream.write(serialized(summary))
            stream.flush()
            os.fsync(stream.fileno())
        fsync_directory(destination)
        return summary

    @classmethod
    def restore(cls, backup, destination):
        from numek_platform.backup import restore_backup, verify_backup
        from numek_platform.db import Database
        from numek_platform.local import LocalCluster
        from numek_platform.objects import LocalObjectStore
        backup = Path(backup).absolute()
        destination = Path(destination).absolute()
        if destination.exists() or destination == backup or backup in destination.parents:
            raise EvaluationError('Restore requires a new destination.', 'restore_destination')
        summary = strict_json((backup / 'backup.json').read_bytes())
        expected = summary.pop('content_digest', None)
        if expected != digest(summary) or summary.get('schema_version') != 'confidenceguard.workspace_backup/2.0':
            raise EvaluationError('Backup is incomplete or changed.', 'backup_changed')
        try:
            manifest = verify_backup(backup / 'platform')
        except Exception as exc:
            raise EvaluationError('Backup is incomplete or changed.', 'backup_changed') from exc
        if digest(manifest) != summary['platform_manifest']:
            raise EvaluationError('Backup is incomplete or changed.', 'backup_changed')
        binding = strict_json((backup / BINDING).read_bytes())
        private_directory(destination)
        cluster = LocalCluster(destination / 'platform')
        cluster.start()
        database = Database(cluster.dsn())
        restore_backup(backup / 'platform', database, LocalObjectStore(destination / binding['store']), None, passphrase=None)
        binding = {k: v for k, v in binding.items() if k != 'dsn_env'}
        binding['local_cluster'] = 'platform'
        with private_file(destination / BINDING) as stream:
            stream.write(serialized(binding))
        from psycopg.types.json import Jsonb
        with database.transaction() as conn:                         # a restore is a new instance (v2 semantics)
            catalog_id = uuid.UUID(binding['catalog_id'])
            conn.execute("UPDATE cg_settings SET value = %s WHERE catalog_id = %s AND key = 'instance_id'",
                         (Jsonb(uuid.uuid4().hex), catalog_id))
            conn.execute('UPDATE catalogs SET branch_id = %s, continuity_token = %s WHERE id = %s',
                         (uuid.uuid4().hex, uuid.uuid4().hex, catalog_id))
        fsync_directory(destination)
        return cls(destination)

    def migrate(self, _backup_destination):
        return {'catalog_version': CATALOG_VERSION, 'changed': False}

    def _object_path(self, identifier):
        raise EvaluationError('Platform objects are read through verified streams, not paths.', 'platform_unported')

    # Locks and status -------------------------------------------------------------
    @contextlib.contextmanager
    def operation(self, *, exclusive_objects=False):
        # Publication is fenced and serialized by the platform; this only keeps
        # one in-process caller per catalog object and refreshes settings.
        with self._guard:
            self._validate()
            yield

    def _lease(self, identifier):
        from numek_platform.execution import jobs
        lease = self._leases.get(identifier)
        if lease is None:
            with self.db.connect() as conn:
                lease, _row = jobs.start_inline(conn, self.scope, 'cg_operation', idempotency_key=f'cg-op:{identifier}',
                                                owner=f'confidenceguard:{os.getpid()}')
            if lease is None:
                raise EvaluationError('This operation already finished.', 'operation_incomplete')
            self._leases[identifier] = lease
        return lease

    def _finish_lease(self, identifier, *, failed=False):
        from numek_platform.execution import jobs
        from numek_platform.errors import FenceLost
        lease = self._leases.pop(identifier, None)
        if lease is None:
            return
        try:
            with self.db.connect() as conn:
                if failed:
                    jobs.fail(conn, lease, {'code': 'operation_failed'})
                else:
                    jobs.complete(conn, lease, {'operation_id': identifier})
        except FenceLost:
            pass

    def adopt_lease(self, identifier, lease):
        """Run an operation under an existing attempt (for example one holding a reservation)."""
        self._leases[identifier] = lease

    def head(self):
        with self.db.connect() as conn:
            return conn.execute('SELECT head FROM catalog_heads WHERE catalog_id = %s', (self.catalog_id,)).fetchone()['head']

    def reserve(self, additional=0):
        with self.db.connect() as conn:
            stored = conn.execute("SELECT coalesce(sum(bytes), 0) AS b FROM objects WHERE catalog_id = %s "
                                  "AND state IN ('pending', 'active', 'tombstoned')", (self.catalog_id,)).fetchone()['b']
        staging = sum(p.stat().st_size for p in (self.root / 'staging').rglob('*') if p.is_file() and not p.is_symlink())
        total = int(stored) + staging
        if total + additional > self.config.max_bytes:
            raise EvaluationError('Persistent storage quota would be exceeded.', 'history_quota')
        if shutil.disk_usage(self.store.root).free < self.config.free_disk_bytes + additional:
            raise EvaluationError('Persistent storage reserve unavailable.', 'disk_exhausted')
        return total

    def status(self):
        with self.db.connect() as conn:
            counts = {r['kind']: r['n'] for r in conn.execute(
                '''SELECT f.kind, count(*) AS n FROM fact_index f JOIN objects o ON o.id = f.object_id
                   WHERE f.catalog_id = %s AND o.state IN ('active', 'tombstoned')
                   AND NOT EXISTS (SELECT 1 FROM fact_tombstones t WHERE t.catalog_id = f.catalog_id AND t.kind = f.kind
                                   AND t.key = f.key AND t.revision = f.revision)
                   GROUP BY f.kind''', (self.catalog_id,))}
            row = conn.execute('SELECT continuity_state FROM catalogs WHERE id = %s', (self.catalog_id,)).fetchone()
        return {'instance_id': self.instance_id, 'catalog_sequence': self.head(), 'config': self.config.to_dict(),
                'facts': counts, 'bytes': self.reserve(), 'journal_mode': 'postgresql', 'sqlite_version': None,
                'automatic_eviction': False, 'catalog_version': self.catalog_version,
                'exposure_continuity': row['continuity_state'], 'storage': 'numek_platform'}

    def set_saving(self, enabled):
        from psycopg.types.json import Jsonb
        if not isinstance(enabled, bool):
            raise EvaluationError('saving must be boolean.')
        with self.operation(), self.db.transaction() as conn:
            values = self.config.to_dict()
            values['saving'] = enabled
            conn.execute("UPDATE cg_settings SET value = %s WHERE catalog_id = %s AND key = 'config'",
                         (Jsonb(values), self.catalog_id))
        self.config = WorkspaceConfig.from_dict(values)
        return self.status()

    def recover(self):
        """Platform publication is atomic; only local staging can be left behind."""
        removed = 0
        for directory in (self.root / 'staging').iterdir():
            if directory.is_dir() and not directory.is_symlink():
                shutil.rmtree(directory)
                removed += 1
        return {'pending_operations_removed': removed, 'unavailable_objects': []}

    # Operations -------------------------------------------------------------------------
    def receipt(self, request_id, request_digest):
        with self.db.connect() as conn:
            row = conn.execute('SELECT request_digest, receipt FROM publications WHERE catalog_id = %s AND request_id = %s',
                               (self.catalog_id, request_id)).fetchone()
        if row is None:
            return None
        if row['request_digest'] != request_digest:
            raise EvaluationError('Request ID already has different content.', 'idempotency_conflict')
        return dict(row['receipt'].get('cg') or {})

    def begin(self, request_id, request_digest, *, require_saving=True):
        if require_saving and not self.config.saving:
            raise EvaluationError('Historical saving is off; enable it explicitly.', 'persistence_disabled')
        previous = self.receipt(request_id, request_digest)
        if previous is not None:
            return None, previous
        identifier = uuid.uuid4().hex
        self._requests = getattr(self, '_requests', {})
        self._requests[identifier] = (request_id, request_digest)
        private_directory(self.root / 'staging' / identifier)
        return identifier, None

    # Stored records ------------------------------------------------------------------------
    def _stored_record(self, object_id, codec, offset, length, cache):
        """Read one committed record through verify-on-read (maintenance access)."""
        from numek_platform.evidence import codecs
        key = ('object', object_id)
        if key not in cache:
            with self.db.connect() as conn:
                row = conn.execute('SELECT physical_key, sha256, bytes, state FROM objects WHERE id = %s', (object_id,)).fetchone()
            if row is None or row['state'] not in ('active', 'tombstoned'):
                raise EvaluationError('Previously retained fact was purged or is unavailable; restore a verified backup '
                                      'into a new workspace.', 'historical_evidence_unavailable')
            try:
                cache[key] = self.store.read_verified(row['physical_key'], bytes(row['sha256']).hex(), row['bytes'])
            except Exception as exc:
                raise _translate(exc) from exc
        data = cache[key]
        if codec == 'typed_feature_rows_v1':
            return self._read_record(self._materialize(object_id.hex, '.parquet'), codec, offset, length, cache)
        if codec != codecs.JSONL:
            raise EvaluationError('Objects of this codec do not contain facts.', 'unsupported_codec')
        raw = data[offset:offset + length]
        if len(raw) != length or length > self.config.max_record_bytes:
            raise EvaluationError('Invalid retained record location.', 'evidence_changed')
        return strict_json(raw)

    def _fact_row(self, conn, kind, key, *, revision=None, fact_digest=None):
        where, params = ['f.catalog_id = %s', 'f.kind = %s', 'f.key = %s'], [self.catalog_id, kind, bytes.fromhex(key)]
        if revision is not None:
            where.append('f.revision = %s')
            params.append(revision)
        if fact_digest is not None:
            where.append('f.fact_digest = %s')
            params.append(bytes.fromhex(fact_digest))
        return conn.execute(
            f'''SELECT f.*, o.codec, o.state AS object_state,
                       EXISTS (SELECT 1 FROM fact_tombstones t WHERE t.catalog_id = f.catalog_id AND t.kind = f.kind
                               AND t.key = f.key AND t.revision = f.revision) AS purged
                FROM fact_index f JOIN objects o ON o.id = f.object_id WHERE {' AND '.join(where)} LIMIT 1''', params).fetchone()

    # Publication (port of v2 commit_capture) ------------------------------------------------------
    def commit_capture(self, identifier, *, cancel=None, receipt_extra=None, conflicts='refuse'):
        """Publish a staged capture. ``conflicts='quarantine'`` (CG7 ingestion) leaves facts that conflict with
        retained evidence (or correct it inadmissibly) out of the publication and reports them, instead of
        refusing the whole capture."""
        if conflicts not in ('refuse', 'quarantine'):
            raise ValueError(conflicts)
        try:
            return self._commit_capture(identifier, cancel=cancel, receipt_extra=receipt_extra, conflicts=conflicts)
        except BaseException:
            self._finish_lease(identifier, failed=True)
            raise

    def _commit_capture(self, identifier, *, cancel, receipt_extra, conflicts='refuse'):
        from .feature_storage import extension, validate_matrix
        from numek_platform.evidence.publish import FactRow, publish, stage_object
        from numek_platform.errors import PlatformError
        stage = self.root / 'staging' / _safe_name(identifier)
        with private_file(stage / 'capture.json', 'rb') as stream:
            raw = stream.read(64 * 1024**2 + 1)
        if len(raw) > 64 * 1024**2:
            raise EvaluationError('Capture manifest exceeds admission.', 'manifest_limit')
        manifest = strict_json(raw)
        expected = manifest.pop('content_digest', None)
        if expected != digest(manifest) or manifest.get('operation_id') != identifier:
            raise EvaluationError('Capture identity differs.', 'capture_changed')
        HistoricalEvidenceManifest.from_dict(manifest)
        if manifest['metadata'].get('evidence_use'):
            raise EvaluationError('Evidence uses are recorded by the platform ledger, not captures.', 'platform_unported')
        objects = {v['id']: v for v in manifest['objects']}
        for obj in objects.values():
            _safe_name(obj['id'])
            sha, size = file_digest(stage / (obj['id'] + extension(obj.get('encoding', 'utf8_jsonl_v1'))))
            if sha != obj['sha256'] or size != obj['bytes']:
                raise EvaluationError('Staged evidence identity differs.', 'capture_changed')

        lease = self._lease(identifier)
        new = duplicates = 0
        used, rows, seen = set(), [], {}
        dependencies, vector_rows = set(), []
        staged_cache, stored_cache = {}, {}
        entity_of = {}
        quarantined = []
        with self.db.connect() as conn, contextlib.ExitStack() as cleanup:
            cleanup.callback(lambda: [s.close() for s in staged_cache.values() if hasattr(s, 'close')])
            with private_file(stage / 'index.jsonl', 'rb') as stream:
                entries = []
                for line in stream:
                    if len(line) > 16384:
                        raise EvaluationError('Invalid capture index.', 'capture_changed')
                    entries.append(strict_json(line))
            for count, entry in enumerate(entries):
                if count % 4096 == 0:
                    if cancel is not None and cancel.is_set():
                        raise EvaluationError('Cancelled before historical publication.', 'cancelled')
                    self.reserve()
                if entry.get('kind') == 'vector_location':
                    vector_rows.append(self._validate_vector(conn, stage, objects, entry, staged_cache, validate_matrix, used))
                    continue
                obj = objects.get(entry['object_id'])
                codec = obj.get('encoding', 'utf8_jsonl_v1') if obj else None
                if (obj is None or entry['offset'] < 0 or entry['length'] <= 0
                        or (codec == 'utf8_jsonl_v1' and entry['offset'] + entry['length'] > obj['bytes'])):
                    raise EvaluationError('Invalid evidence location.', 'capture_changed')
                fact = self._read_record(stage / (entry['object_id'] + extension(codec)), codec, entry['offset'],
                                         entry['length'], staged_cache)
                claimed = fact.pop('fact_digest', None)
                if (claimed != entry['fact_digest'] or digest(fact) != claimed or digest(fact['identity']) != entry['key']
                        or fact['kind'] != entry['kind'] or fact['revision'] != entry['revision']):
                    raise EvaluationError('Record and directory identities differ.', 'capture_changed')
                identity = (entry['kind'], entry['key'], entry['revision'])
                same = seen.get(identity) or self._fact_row(conn, entry['kind'], entry['key'], revision=entry['revision'])
                prior_exists = (any(k == entry['kind'] and key == entry['key'] for k, key, _r in seen)
                                or self._fact_row(conn, entry['kind'], entry['key']) is not None)
                is_correction = fact.get('predecessor') is not None or (prior_exists and same is None)
                try:
                    if entry['kind'] in {'prediction', 'context', 'opportunity', 'feature', 'representation'} and is_correction:
                        self._validate_correction(conn, entry, fact, claimed, seen, stage, staged_cache, stored_cache)
                    if same is not None:
                        if isinstance(same, dict) and same.get('_staged'):
                            if same['fact_digest'] != claimed:
                                raise EvaluationError('Same fact identity/revision has different content.', 'historical_identity_conflict')
                            duplicates += 1
                            continue
                        if bytes(same['fact_digest']).hex() != claimed:
                            raise EvaluationError('Same fact identity/revision has different content.', 'historical_identity_conflict')
                        if same['purged'] or same['object_state'] not in ('active', 'tombstoned'):
                            raise EvaluationError('Previously retained fact was purged or is unavailable; restore a verified '
                                                  'backup into a new workspace.', 'historical_evidence_unavailable')
                        prior_record = self._stored_record(same['object_id'], same['codec'], same['loc_a'], same['loc_b'], stored_cache)
                        prior_digest = prior_record.pop('fact_digest', None)
                        if prior_digest != claimed or digest(prior_record) != claimed or prior_record != fact:
                            raise EvaluationError('Indexed duplicate differs from retained canonical identity/payload.',
                                                  'historical_identity_conflict')
                        duplicates += 1
                        target_object = same['object_id']
                        rows.append(self._row(FactRow, entry, fact, claimed, target_object, same['locator_kind'], same['loc_a'],
                                              same['loc_b'], entity_of))
                    else:
                        new += 1
                        used.add(entry['object_id'])
                        target_object = _uuid(entry['object_id'])
                        seen[identity] = {'_staged': True, 'fact_digest': claimed, 'object_id': entry['object_id'],
                                          'offset': entry['offset'], 'length': entry['length'], 'codec': codec}
                        rows.append(self._row(FactRow, entry, fact, claimed, target_object,
                                              entry.get('locator_kind', 'byte_range'), entry['offset'], entry['length'], entity_of))
                except EvaluationError as exc:
                    if conflicts != 'quarantine' or exc.code not in QUARANTINABLE:
                        raise
                    # Ingestion: this fact conflicts with retained evidence (or corrects it
                    # inadmissibly); it is reported and left out, the rest is published.
                    quarantined.append({'kind': entry['kind'], 'key': entry['key'], 'revision': entry['revision'],
                                        'reason': exc.code})
                    continue
                self._collect_dependencies(conn, fact, target_object, objects, used, dependencies)
        if cancel is not None and cancel.is_set():
            raise EvaluationError('Cancelled before historical commit.', 'cancelled')

        refs = []
        for oid in sorted(used):  # W1-W3 per object (pending until the publication commits)
            obj = objects[oid]
            path = stage / (oid + extension(obj.get('encoding', 'utf8_jsonl_v1')))
            with private_file(path, 'rb') as stream:
                data = stream.read()
            try:
                refs.append(stage_object(self.db, self.store, lease, data, catalog_id=self.catalog_id,
                                         codec=obj.get('encoding', 'utf8_jsonl_v1'), records=obj.get('records', 0),
                                         object_id=_uuid(oid)))
            except PlatformError as exc:
                raise _translate(exc) from exc
        self._fault('objects_published')
        metadata = manifest['metadata']
        request_id, request_digest = getattr(self, '_requests', {}).get(identifier, (f'operation:{identifier}', expected))

        object_kinds = [(_uuid(oid), objects[oid]['kind']) for oid in sorted(used)]

        def before_head(conn, publication_id):
            self._record_relations(conn, publication_id, metadata, rows, dependencies, vector_rows, expected)
            for object_uuid, kind in object_kinds:
                conn.execute('INSERT INTO cg_objects(catalog_id, object_id, kind, operation_id) VALUES (%s, %s, %s, %s)',
                             (self.catalog_id, object_uuid, kind, publication_id))

        cg_receipt = {'operation_id': identifier, 'new_facts': new, 'duplicate_occurrences': duplicates,
                      'capture_digest': expected, **(receipt_extra or {})}
        if conflicts == 'quarantine':
            cg_receipt['quarantined_facts'] = quarantined
        entities = self._first_seen_entities(rows)

        def after_head(conn, pid, k):
            conn.execute("UPDATE publications SET receipt = jsonb_set(receipt, '{cg,catalog_sequence}', to_jsonb(%s::bigint)) "
                         'WHERE id = %s', (k, pid))
            self._register_entities(conn, entities, k)
            self._fault('before_catalog_commit')

        try:
            receipt = publish(self.db, self.scope, lease, self.catalog_id, request_id=request_id,
                              request_digest=request_digest, kind='cg_capture', objects=refs, facts=rows,
                              before_head=before_head, publication_id=_uuid(identifier),
                              reservations=getattr(self, '_consumes', {}).pop(identifier, ()),
                              receipt_extra={'cg': {**cg_receipt, 'catalog_sequence': None}},
                              exposure_lock=bool(entities), after_head=after_head)
        except PlatformError as exc:
            raise _translate(exc) from exc
        if receipt.replayed:
            result = self.receipt(request_id, request_digest)
        else:
            result = {**cg_receipt, 'catalog_sequence': receipt.sequence}
        self._fault('catalog_committed')
        self._finish_lease(identifier)
        shutil.rmtree(stage)
        fsync_directory(self.root / 'staging')
        return result

    def _first_seen_entities(self, rows):
        """{namespace: [(unit_hash, lexical entity)]} of the opportunities a capture publishes.

        Registered with the namespace's sealed reserve in the publication transaction, at its K
        (G.8: assignment at first sight; an entity first seen before a reserve existed stays
        ``pre_reserve``). Needs the installation's secrets; standalone workspaces have none.
        """
        if self.secrets is None:
            return {}
        out = {}
        for row in rows:
            if row.kind == 'opportunity' and row.namespace and row.entity_hash:
                out.setdefault(row.namespace, {})[row.entity_hash] = self._lexical_entity.get(row.key) or row.opportunity_key
        return {ns: sorted(values.items()) for ns, values in out.items()}

    def _register_entities(self, conn, entities, k):
        if not entities:
            return
        from numek_platform.governance.reserve import register_entities
        for namespace, values in entities.items():
            register_entities(conn, self.secrets, self.scope, self.catalog_id, namespace, values, k)

    def _row(self, FactRow, entry, fact, claimed, object_id, locator_kind, a, b, entity_of):
        payload = fact.get('payload') or {}
        namespace = payload.get('namespace') if isinstance(payload, dict) else None
        event_hash = entity_hash = target_key = opportunity_key = None
        kind = entry['kind']
        if kind == 'opportunity':
            opportunity_key = entry['key']
            entity_of[opportunity_key] = payload.get('entity')
            if self is not None:
                self._lexical_entity[entry['key']] = payload.get('entity')
            target_key = payload.get('target_key')
        elif kind in ('prediction', 'sample'):
            opportunity_key = payload.get('opportunity_key')
            target_key = payload.get('target_key')
        elif kind == 'context':
            opportunity_key = fact['identity'][0] if fact.get('identity') else None
        elif kind == 'outcome':
            target_key = entry['key']
        if namespace is not None and opportunity_key is not None:
            event_hash = digest([namespace, opportunity_key])
            entity = (payload.get('normalized') or {}).get('entity_key') if kind == 'prediction' else entity_of.get(opportunity_key)
            entity_hash = digest([namespace, entity or opportunity_key])
        protected = kind in ('outcome', 'raw') or (kind == 'prediction' and payload.get('inline_assertion') is not None)
        tick = None
        clock = payload.get('time') if isinstance(payload, dict) else None
        if isinstance(clock, dict) and clock.get('state') == 'valid' and clock.get('tick') is not None:
            tick = int(clock['tick'])
        return FactRow(kind, entry['key'], entry['revision'], claimed, object_id, locator_kind if locator_kind in
                       ('byte_range', 'row', 'object') else 'byte_range', a, b, predecessor=fact.get('predecessor'),
                       opportunity_key=opportunity_key if opportunity_key and len(opportunity_key) == 64 else None,
                       target_key=target_key if target_key and len(target_key) == 64 else None,
                       entity_hash=entity_hash, event_hash=event_hash, event_tick=tick,
                       available_tick=int(fact['available_ns']) if fact.get('available_ns') is not None else None,
                       namespace=namespace, protected=protected)

    def _validate_correction(self, conn, entry, fact, claimed, seen, stage, staged_cache, stored_cache):
        from .feature_storage import extension
        staged_parent = next((v for (k, key, _r), v in seen.items() if k == entry['kind'] and key == entry['key']
                              and v['fact_digest'] == fact.get('predecessor')), None)
        parent = staged_parent or (self._fact_row(conn, entry['kind'], entry['key'], fact_digest=fact['predecessor'])
                                   if fact.get('predecessor') else None)
        if parent is None or not fact.get('reason') or fact.get('available_ns') is None:
            raise EvaluationError('Correction requires a matching predecessor, reason and availability.', 'correction_predecessor')
        if staged_parent:
            parent_record = self._read_record(stage / (staged_parent['object_id'] + extension(staged_parent['codec'])),
                                              staged_parent['codec'], staged_parent['offset'], staged_parent['length'], staged_cache)
        else:
            parent_record = self._stored_record(parent['object_id'], parent['codec'], parent['loc_a'], parent['loc_b'], stored_cache)
        if parent_record.get('available_ns') is not None and int(fact['available_ns']) < int(parent_record['available_ns']):
            raise EvaluationError('Correction availability precedes its predecessor.', 'correction_chronology')
        if entry['kind'] == 'prediction':
            before, after = parent_record['payload'], fact['payload']
            if before['role'] != after['role'] or before['normalized'].get('entity_key') != after['normalized'].get('entity_key'):
                raise EvaluationError('Corrections cannot relabel historical role/entity separation.', 'historical_role_reassignment')
            if parent_record['authority'] != fact['authority']:
                raise EvaluationError('Prediction correction authority differs.', 'correction_authority')
        existing = self._fact_row(conn, entry['kind'], entry['key'], revision=entry['revision'])
        if existing is not None and bytes(existing['fact_digest']).hex() != claimed:
            raise EvaluationError('Correction revision conflicts.', 'historical_identity_conflict')

    def _validate_vector(self, conn, stage, objects, entry, cache, validate_matrix, used):
        import numpy as np
        obj = objects.get(entry['object_id'])
        if obj is None or obj.get('encoding') != 'dense_vectors_npy_v1':
            raise EvaluationError('Vector index codec differs.', 'capture_changed')
        path = stage / (obj['id'] + '.npy')
        key = ('vector', obj['id'])
        if key not in cache:
            cache[key] = (validate_matrix(path, max_bytes=self.config.max_bytes),
                          np.load(path, mmap_mode='r', allow_pickle=False, max_header_size=10000))
        info, matrix = cache[key]
        if not isinstance(entry.get('row'), int) or not 0 <= entry['row'] < info['rows']:
            raise EvaluationError('Vector row index differs.', 'capture_changed')
        vector = matrix[entry['row']]
        actual = hashlib.sha256(matrix.dtype.str.encode() + vector.tobytes()).hexdigest()
        if not np.isfinite(vector).all() or actual != entry['vector_digest']:
            raise EvaluationError('Vector logical digest differs.', 'capture_changed')
        previous = conn.execute('''SELECT o.state FROM cg_vector_locations v JOIN objects o ON o.id = v.object_id
                                   WHERE v.catalog_id = %s AND v.digest = %s''', (self.catalog_id, actual)).fetchone()
        if previous is not None:
            if previous['state'] not in ('active', 'pending'):
                raise EvaluationError('Previously deleted vectors cannot be resurrected.', 'historical_evidence_unavailable')
            return None
        used.add(obj['id'])
        return (actual, _uuid(obj['id']), entry['row'], info['dtype'], info['dimensions'])

    def _collect_dependencies(self, conn, fact, target_object, objects, used, dependencies):
        payload = fact.get('payload') or {}
        if not isinstance(payload, dict):
            return
        vector_digest = payload.get('vector_digest')
        if vector_digest:
            row = conn.execute('SELECT object_id FROM cg_vector_locations WHERE catalog_id = %s AND digest = %s',
                               (self.catalog_id, vector_digest)).fetchone()
            staged = [oid for oid in used if objects.get(oid, {}).get('encoding') == 'dense_vectors_npy_v1']
            if row is None and not staged:
                raise EvaluationError('Representation vector dependency is absent.', 'capture_changed')
            dependencies.add((target_object, row['object_id'] if row else ('vector', vector_digest)))
        for dependency in payload.get('depends_on_facts', []):
            row = conn.execute('''SELECT f.object_id, o.state FROM fact_index f JOIN objects o ON o.id = f.object_id
                                  WHERE f.catalog_id = %s AND f.fact_digest = %s LIMIT 1''',
                               (self.catalog_id, bytes.fromhex(dependency))).fetchone()
            if row is None or row['state'] != 'active':
                raise EvaluationError('Required fact dependency is absent or deleted.', 'capture_changed')
            if row['object_id'] != target_object:
                dependencies.add((target_object, row['object_id']))
        for dependency in payload.get('depends_on_objects', []):
            _safe_name(dependency)
            if dependency in objects:
                blob = objects[dependency]
                if blob.get('encoding') == 'opaque_artifact_bytes_v1':
                    if (fact['kind'] != 'cg6_artifact_descriptor' or payload.get('object_id') != dependency
                            or payload.get('sha256') != blob['sha256'] or payload.get('bytes') != blob['bytes']):
                        if dependency not in used:
                            raise EvaluationError('Binary artifact descriptor differs.', 'capture_changed')
                    else:
                        used.add(dependency)
                elif dependency not in used:
                    used.add(dependency)
            else:
                row = conn.execute('SELECT state FROM objects WHERE id = %s AND catalog_id = %s',
                                   (_uuid(dependency), self.catalog_id)).fetchone()
                if row is None or row['state'] != 'active':
                    raise EvaluationError('Required protected object is absent or deleted.', 'dependency_unavailable')
            if _uuid(dependency) != target_object:
                dependencies.add((target_object, _uuid(dependency)))

    def _record_relations(self, conn, publication_id, metadata, rows, dependencies, vector_rows, capture_digest):
        from psycopg.types.json import Jsonb
        conn.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))', (f'cg-variants:{self.catalog_id}',))
        for vid, value in metadata.get('variants', {}).items():
            previous = conn.execute('SELECT metadata FROM cg_variants WHERE catalog_id = %s AND id = %s',
                                    (self.catalog_id, vid)).fetchone()
            new_model = value['signature']['model']
            for existing in conn.execute('SELECT metadata FROM cg_variants WHERE catalog_id = %s', (self.catalog_id,)):
                old_model = existing['metadata']['signature']['model']
                fields = ('id', 'version', 'artifact_sha256', 'preprocessing')
                if ((old_model['id'], old_model['version']) == (new_model['id'], new_model['version'])
                        and any(old_model.get(k) != new_model.get(k) for k in fields)):
                    raise EvaluationError('Existing predictor version cannot change artifact or preprocessing identity.',
                                          'model_version_conflict')
            if previous:
                old = previous['metadata']
                immutable = ('signature', 'task', 'namespace', 'outcome_definition_version', 'normalized_columns')
                if any(old.get(k) != value.get(k) for k in immutable):
                    raise EvaluationError('Variant mathematics or normalized representation conflicts.', 'variant_conflict')
                if any(k in old.get('features', {}) and old['features'][k] != v for k, v in value.get('features', {}).items()):
                    raise EvaluationError('Retained feature semantics changed.', 'feature_semantics_conflict')
                old['features'] = {**old.get('features', {}), **value.get('features', {})}
                conn.execute('UPDATE cg_variants SET metadata = %s WHERE catalog_id = %s AND id = %s',
                             (Jsonb(old), self.catalog_id, vid))
            else:
                conn.execute('INSERT INTO cg_variants(catalog_id, id, metadata, publication_id) VALUES (%s, %s, %s, %s)',
                             (self.catalog_id, vid, Jsonb(value), publication_id))
        for row in vector_rows:
            if row is not None:
                conn.execute('''INSERT INTO cg_vector_locations(catalog_id, digest, object_id, row_index, dtype, dimensions)
                                VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT DO NOTHING''', (self.catalog_id, *row))
        for child, parent in dependencies:
            if isinstance(parent, tuple):
                found = conn.execute('SELECT object_id FROM cg_vector_locations WHERE catalog_id = %s AND digest = %s',
                                     (self.catalog_id, parent[1])).fetchone()
                if found is None:
                    raise EvaluationError('Representation vector dependency is absent.', 'capture_changed')
                parent = found['object_id']
            if parent != child:
                conn.execute('''INSERT INTO cg_artifact_dependencies(catalog_id, object_id, depends_on) VALUES (%s, %s, %s)
                                ON CONFLICT DO NOTHING''', (self.catalog_id, child, parent))
        if metadata.get('assessment_id'):
            aid = metadata['assessment_id']
            key = digest([aid])
            fact = next((r for r in rows if r.kind == 'assessment' and r.key == key), None)
            if fact is None:
                raise EvaluationError('Assessment record is absent from its capture.', 'capture_changed')
            conn.execute('''INSERT INTO cg_assessments(catalog_id, id, object_id, publication_id, digest, predecessor, state)
                            VALUES (%s, %s, %s, %s, %s, NULL, 'active')''',
                         (self.catalog_id, aid, fact.object_id, publication_id, capture_digest))

    # Reading ------------------------------------------------------------------------------------
    def governed(self, governance):
        """Attach an evidence-use reservation for outcome-bearing reads (see ``reserve_history``)."""
        self._governance = governance
        return self

    @property
    def governance(self):
        """This instance's reservation, else the one this worker process holds for the root.

        Looked up on every read, so catalog instances opened before the worker
        reserved (or renewed) read under the same reservation.
        """
        return self._governance if self._governance is not None else _WORKER_GOVERNANCE.get(str(self.root))

    def ensure_governance(self, *, namespace, k, purpose_label):
        """Reserve before the first outcome read in a process that was not handed a reservation.

        Used by CG4/CG5 history workers. The reservation is committed before any
        protected read; its attempt is completed when the process exits (a crash
        leaves it reserved, so the exposure stays recorded).
        """
        held = self.governance
        authority = _STUDY_AUTHORITY['use_id']
        if held is not None and not held.get('auto'):
            return self                   # handed-in reservations are never widened (later K refuses on read)
        if (held is not None and held.get('authority') == authority and held['namespace'] == namespace
                and held['reservation']['read_k'] >= k):
            return self
        self._auto_reserve(namespace=namespace, k=k, purpose_label=purpose_label, authority=authority)
        return self

    def _auto_reserve(self, *, namespace, k, purpose_label, authority, install=True):
        lease, governance = self.reserve_history(namespace=namespace, k=k, purpose_label=purpose_label, exposure=False,
                                                 authority=authority)
        governance.update(auto=True, namespace=namespace, purpose_label=purpose_label, authority=authority)
        if _ATTEMPT_SCOPES:                       # in-process phase: closed when the phase ends
            _ATTEMPT_SCOPES[-1].append((self.db.dsn, lease))
        else:                                     # spawned phase: closed when the process exits
            from multiprocessing import util
            util.Finalize(None, PlatformCatalog._close_attempt, args=(self.db.dsn, lease), exitpriority=10)
        if not install:
            return governance
        _WORKER_GOVERNANCE[str(self.root)] = governance
        self.governed(governance)
        return governance

    @staticmethod
    def _close_attempt(dsn, lease):
        from numek_platform.db import Database
        from numek_platform.errors import FenceLost
        from numek_platform.execution import jobs
        try:
            with Database(dsn).connect() as conn:
                jobs.complete(conn, lease, {})
        except (FenceLost, Exception):
            pass

    def iter_facts(self, kind=None, *, sequence=None, keys=None, fact_digests=(), batch_ids=(), require_complete=True,
                   max_records=30000000, check=None, _logical_order=False):
        from numek_platform.evidence import reader
        from numek_platform.errors import PlatformError
        from numek_platform.governance import reader as governed_reader
        from numek_platform.governance.ledger import Reservation
        try:
            head = self.head()
            k = head if sequence is None else min(int(sequence), head)
            read_pin = reader.pin(self.db, self.scope, self.catalog_id, holder=f'confidenceguard:{os.getpid()}', k=k,
                                  allow_migrating=self._migrating)
            try:
                filters = {'kinds': None if kind is None else [kind], 'keys': None if keys is None else list(keys),
                           'fact_digests': list(fact_digests) or None, 'require_complete': require_complete,
                           'occurrence_publications': [_uuid(b) for b in batch_ids] or None,
                           'order': 'logical' if _logical_order else 'physical'}
                held = self.governance
                if held is not None and held.get('auto') and k > held['reservation']['read_k']:
                    # Worker access reservations follow the snapshot a worker reads,
                    # with the same study authority. Past the study's own snapshot the
                    # authority grants nothing: that one read is made without it (sealed
                    # reserve rows withheld) and the in-snapshot reservation is kept.
                    try:
                        held = self._auto_reserve(namespace=held['namespace'], k=k, purpose_label=held['purpose_label'],
                                                  authority=held.get('authority'))
                    except EvaluationError as exc:
                        if exc.code != 'authority_snapshot':
                            raise
                        held = self._auto_reserve(namespace=held['namespace'], k=k, purpose_label=held['purpose_label'],
                                                  authority=None, install=False)
                if held is not None:
                    reservation = Reservation(**{k2: (uuid.UUID(v) if k2 in ('catalog_id', 'job_id') and v else v)
                                                 for k2, v in held['reservation'].items()})
                    locators = governed_reader.resolve(self.db, self.store, reservation, read_pin, **filters).locators
                else:
                    locators = reader.resolve(self.db, read_pin, **filters)
                if len(locators) > max_records:
                    raise EvaluationError('Historical scan record admission exceeded.', 'history_scan_limit')
                count = 0
                for locator, record in self._read_locators(locators):
                    count += 1
                    if check and count % 512 == 0:
                        check('historical evidence scan')
                    value = dict(record)
                    fd = value.pop('fact_digest', None)
                    if fd != locator.fact_digest or fd != digest(value) or digest(value['identity']) != locator.key:
                        raise EvaluationError('Historical fact identity differs.', 'evidence_changed')
                    value['fact_digest'] = fd
                    value['recorded_sequence'] = locator.sequence
                    value['object_id'] = locator.object_id.hex
                    value['offset'] = locator.loc_a
                    value['record_bytes'] = locator.loc_b if locator.codec == 'utf8_jsonl_v1' else len(serialized(value))
                    self._verified[locator.object_id.hex] = (0, 0, locator.bytes)
                    yield value
            finally:
                reader.release(self.db, read_pin)
        except PlatformError as exc:
            raise _translate(exc) from exc

    def _read_locators(self, locators):
        """Decode locators: platform codecs via verify-on-read, legacy typed features via the v2 row reader."""
        from numek_platform.evidence import reader
        native = [l for l in locators if l.codec in ('utf8_jsonl_v1', 'observation_facts_parquet_v1')]
        other = [l for l in locators if l not in native]
        yield from reader.read(self.store, native, max_record_bytes=self.config.max_record_bytes)
        cache = {}
        try:
            for locator in other:
                if locator.codec != 'typed_feature_rows_v1':
                    raise EvaluationError('Objects of this codec do not contain facts.', 'unsupported_codec')
                path = self._materialize(locator.object_id.hex, '.parquet')
                yield locator, self._read_record(path, locator.codec, locator.loc_a, locator.loc_b, cache)
        finally:
            for value in cache.values():
                if hasattr(value, 'close'):
                    value.close()

    def variants(self):
        with self.db.connect() as conn:
            return {r['id']: r['metadata'] for r in conn.execute('SELECT id, metadata FROM cg_variants WHERE catalog_id = %s',
                                                                (self.catalog_id,))}

    def _assessment_objects(self, conn, kind, identity_values):
        found = set()
        for value in identity_values:
            if value:
                found.update(r['object_id'].hex for r in conn.execute(
                    'SELECT object_id FROM fact_index WHERE catalog_id = %s AND kind = %s AND key = %s',
                    (self.catalog_id, kind, bytes.fromhex(digest([value])))))
        return found

    def add_assessment(self, result, *, request_id=None, cancel=None, request_digest=None, lease=None, reservations=()):
        from .history_storage import EvidenceWriter
        cg4 = result.data.get('methodology_id') == 'failure_investigation_v1'
        cg5 = result.data.get('methodology_id') == 'policy_selection_v1'
        request_id = request_id or uuid.uuid4().hex
        identifier, previous = self.begin(request_id, request_digest or digest(result.to_private_dict()), require_saving=False)
        if previous:
            return previous
        if lease is not None:
            self.adopt_lease(identifier, lease)
        self._consumes = getattr(self, '_consumes', {})
        self._consumes[identifier] = list(reservations)
        writer = EvidenceWriter(self.root / 'staging' / identifier, self.config, identifier)
        aid = result.data['analysis_id']
        payload = {'result': result.to_private_dict(), 'manifest': result.private}
        if cg4 or cg5:
            binding = result.private.get('history_binding') or {}
            dependencies = set(binding.get('source_objects', ())) if binding.get('instance_id') == self.instance_id else set()
            panel = result.data.get('investigation') or result.data.get('policy', {})
            parents = [panel.get('origin_analysis_id'), result.private.get('origin_analysis_id'),
                       (panel.get('annotation_parent') or {}).get('analysis_id'),
                       (panel.get('numerical_recomputation') or {}).get('origin_analysis_id')]
            with self.db.connect() as conn:
                dependencies |= self._assessment_objects(conn, 'assessment', parents)
                if cg5:
                    frozen = result.private.get('frozen_family') or {}
                    dependencies |= self._assessment_objects(conn, 'policy_family', [frozen.get('content_digest')])
                # (v2 also linked the CG5 evidence-use fact; platform uses are durable governance rows,
                # not deletable objects, so there is nothing to link.)
            # A standalone run can reuse the exact bytes already retained here (v2 parity).
            # Link those known copies for deletion without inferring statistical
            # independence or identity from different files with similar values.
            hashes = {v.get('sha256') for v in result.private.get('files', {}).values() if isinstance(v, dict)} - {None}
            if hashes:
                for fact in self.iter_facts('capture_metadata', require_complete=False):
                    metadata = fact['payload']
                    inputs = list(metadata.get('sources', {}).values())
                    inputs.extend(v for k, v in metadata.get('external_inputs', {}).items()
                                  if ':model:' not in k and not k.endswith(':manifest'))
                    if hashes.intersection(v.get('sha256') for v in inputs if isinstance(v, dict)):
                        with self.db.connect() as conn:
                            dependencies |= {r['id'].hex for r in conn.execute(
                                '''SELECT o.id FROM cg_objects c JOIN objects o ON o.id = c.object_id
                                   WHERE c.catalog_id = %s AND c.operation_id = %s AND o.state = 'active' ''',
                                (self.catalog_id, _uuid(fact['identity'][0])))}
            payload['depends_on_objects'] = sorted(dependencies)
            from .investigation_storage import write_packet
            write_packet(writer, 'assessment', [aid], payload)
        else:
            writer.add('assessment', [aid], payload)
        writer.finish({'assessment_id': aid})
        return self.commit_capture(identifier, cancel=cancel, receipt_extra={'assessment_id': aid})

    # Backend-neutral queries (same API as the v2 Catalog) ---------------------------------------------
    @property
    def authority_file(self):
        return self.root / BINDING

    def object_ids_for_key(self, kind, key):
        with self.db.connect() as conn:
            return {r['object_id'].hex for r in conn.execute(
                'SELECT object_id FROM fact_index WHERE catalog_id = %s AND kind = %s AND key = %s',
                (self.catalog_id, kind, bytes.fromhex(key)))}

    def object_ids_for_fact_digests(self, digests):
        digests = [bytes.fromhex(d) for d in digests]
        found = set()
        with self.db.connect() as conn:
            for start in range(0, len(digests), 4096):
                found.update(r['object_id'].hex for r in conn.execute(
                    'SELECT DISTINCT object_id FROM fact_index WHERE catalog_id = %s AND fact_digest = ANY(%s)',
                    (self.catalog_id, digests[start:start + 4096])))
        return found

    def prediction_digests_in_operation(self, operation_id):
        with self.db.connect() as conn:
            return {bytes(r['fact_digest']).hex() for r in conn.execute(
                '''SELECT f.fact_digest FROM fact_occurrences c JOIN fact_index f ON f.catalog_id = c.catalog_id
                      AND f.kind = c.kind AND f.key = c.key AND f.revision = c.revision
                   WHERE c.catalog_id = %s AND c.publication_id = %s AND c.kind = %s''',
                (self.catalog_id, _uuid(operation_id), 'prediction'))}

    def object_operations(self, object_ids):
        ids = [_uuid(o) for o in object_ids]
        with self.db.connect() as conn:
            return {r['object_id'].hex: r['publication_id'].hex for r in conn.execute(
                '''SELECT DISTINCT ON (object_id) object_id, publication_id FROM fact_index
                   WHERE catalog_id = %s AND object_id = ANY(%s) ORDER BY object_id, publication_id''',
                (self.catalog_id, ids))}

    def vector_location(self, vector_digest):
        with self.db.connect() as conn:
            row = conn.execute(
                '''SELECT v.object_id, v.row_index, o.sha256, o.bytes, o.state FROM cg_vector_locations v
                   JOIN objects o ON o.id = v.object_id WHERE v.catalog_id = %s AND v.digest = %s''',
                (self.catalog_id, vector_digest)).fetchone()
        if row is None:
            return None
        if row['state'] != 'active':
            raise EvaluationError('Retained vector is unavailable.', 'historical_evidence_unavailable')
        return {'object_id': row['object_id'].hex, 'row_index': row['row_index'], 'sha256': bytes(row['sha256']).hex(),
                'bytes': row['bytes']}

    def vector_matrix(self, location):
        import io
        import numpy as np
        data = self._verified_bytes(_uuid(location['object_id']))
        return np.load(io.BytesIO(data), allow_pickle=False, max_header_size=10000)

    def sealed_reserve_units(self, units):
        """The subset of ``units`` (hex hashes) registered as sealed-reserve entities."""
        units = sorted(set(units))
        if not units:
            return set()
        with self.db.connect() as conn:
            rows = conn.execute("SELECT unit_hash FROM entity_registry WHERE catalog_id = %s AND reserve_state = 'reserve' "
                                'AND unit_hash = ANY(%s)', (self.catalog_id, [bytes.fromhex(u) for u in units])).fetchall()
        return {bytes(r['unit_hash']).hex() for r in rows}

    def assessment(self, aid):
        """v2 parity: retained binaries a result names exist at their v2 paths (verified copies)."""
        result = super().assessment(aid)
        for oid in sorted(set((getattr(result, 'private', None) or {}).get('retained_binary_paths', {}).values())):
            self.blob_path(oid)
        return result

    def blob_path(self, object_id):
        """Verified local copy of a retained opaque object at its v2 path (objects/<oid>.cgblob)."""
        return self._materialize(object_id, '.cgblob')

    def _object_row(self, object_uuid):
        with self.db.connect() as conn:
            row = conn.execute('SELECT physical_key, sha256, bytes, state, codec FROM objects WHERE id = %s AND catalog_id = %s',
                               (object_uuid, self.catalog_id)).fetchone()
        if row is None or row['state'] not in ('active', 'tombstoned'):
            raise EvaluationError('Retained evidence is unavailable.', 'historical_evidence_unavailable')
        return row

    def _verified_bytes(self, object_uuid):
        row = self._object_row(object_uuid)
        try:
            return self.store.read_verified(row['physical_key'], bytes(row['sha256']).hex(), row['bytes'])
        except Exception as exc:
            raise _translate(exc) from exc

    def _materialize(self, object_id, suffix):
        """Write verified bytes once to objects/<oid><suffix> (0600); consumers re-verify on use."""
        target = private_directory(self.root / 'objects') / (_safe_name(object_id) + suffix)
        row = self._object_row(_uuid(object_id))
        expected = bytes(row['sha256']).hex()
        if target.is_file() and not target.is_symlink():
            sha, size = file_digest(target)
            if sha == expected and size == row['bytes']:
                return target
            target.unlink()
        data = self._verified_bytes(_uuid(object_id))
        temporary = target.with_name('.' + target.name + '.' + uuid.uuid4().hex)
        with private_file(temporary) as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
        fsync_directory(target.parent)
        return target

    # Sealed-reserve study claims (G.8) -----------------------------------------------------------------
    def family_claim(self, family_digest):
        """The study family's reserve claim receipt, or None."""
        with self.db.connect() as conn:
            row = conn.execute('''SELECT id, reserve_consumed_units, read_k FROM evidence_uses WHERE catalog_id = %s
                                  AND purpose = 'reserve_claim' AND family_digest = %s ORDER BY created_at LIMIT 1''',
                               (self.catalog_id, family_digest)).fetchone()
        return None if row is None else {'evidence_use_id': row['id'], 'evidence_kind': 'confirmation',
                                         'reserve_units': row['reserve_consumed_units'],
                                         'catalog_sequence': row['read_k'], 'reserve_claim': True}

    def claim_reserve(self, *, family_digest, namespace, k, tick_ranges, eligible, purpose_label, metadata=None):
        """Reserve and consume the sealed-reserve entities a frozen family's assessment role may use.

        G.8 ordering: the family is frozen; eligible reserve membership is found
        from identities only (``reserve_identities``: keys, clocks, outcome
        existence; ``eligible`` applies the family's identity-only role rule);
        one transaction reserves and consumes it; inspection and assessment then
        read under that authority. Idempotent per family: a retry, a scheduled
        look or a numerical recomputation reuses the original claim, so the
        authorized population never grows. Returns None (ordinary workflow) when
        tracking is off, no active reserve exists, or nothing is eligible.
        """
        from numek_platform.errors import PlatformError
        from numek_platform.evidence import reader
        from numek_platform.execution import jobs
        from numek_platform.governance import ledger, reader as governed_reader
        existing = self.family_claim(family_digest)
        if existing is not None:
            return existing
        try:
            if not ledger.tracking_status(self.db, self.scope, self.catalog_id)['enabled']:
                return None
            with self.db.connect() as conn:
                active = conn.execute("SELECT 1 FROM reserves WHERE catalog_id = %s AND namespace = %s AND state = 'active'",
                                      (self.catalog_id, namespace)).fetchone()
            if active is None:
                return None
            with self.db.connect() as conn:
                lease, _row = jobs.start_inline(conn, self.scope, 'cg_reserve_claim', idempotency_key=uuid.uuid4().hex,
                                                owner=f'confidenceguard:{os.getpid()}')
            try:
                read_pin = reader.pin(self.db, self.scope, self.catalog_id, lease=lease, k=k, allow_migrating=self._migrating)
                identities = governed_reader.reserve_identities(self.db, self.store, read_pin, namespace=namespace,
                                                                tick_ranges=tick_ranges, family_digest=family_digest)
                members = sorted({(i['event_hash'], i['entity_hash'], i['target_key']) for i in identities if eligible(i)})
                reader.release(self.db, read_pin)
                if not members:
                    return None
                reservation = ledger.reserve(
                    self.db, self.store, self.scope, lease, self.catalog_id, purpose='reserve_claim', members=members,
                    population_digest='reserve-claim:' + digest(members), family_digest=family_digest, read_k=k,
                    request_id='reserve-claim:' + family_digest, consume_reserve=True,
                    metadata={'purpose': purpose_label, 'namespace': namespace, **(metadata or {})})
            finally:
                self.finish_attempt(lease)
        except PlatformError as exc:
            raise _translate(exc) from exc
        return {'evidence_use_id': reservation.id, 'evidence_kind': 'confirmation',
                'reserve_units': reservation.reserve_consumed_units, 'catalog_sequence': k, 'reserve_claim': True}

    # Governance for historical analysis -----------------------------------------------------------
    def reserve_history(self, *, namespace, k, purpose_label, metadata=None, exposure=True, authority=None):
        """Reserve every opportunity of ``namespace`` that has an outcome at K, before reading any.

        Membership comes from identity hashes and outcome *existence* only. As in
        v2, the read is recorded as outcome exposure only when it is a disclosure
        (``exposure``) and evidence-use tracking is enabled; otherwise the
        reservation is access-only (``selection_access``). Returns
        (lease, governance) for the analysis attempt; the caller publishes its
        result under the same lease (consuming the reservation) or abandons it
        (the exposure remains recorded).
        """
        from numek_platform.errors import PlatformError
        from numek_platform.evidence import reader
        from numek_platform.execution import jobs
        from numek_platform.governance import ledger, reader as governed_reader
        try:
            with self.db.connect() as conn:
                lease, _row = jobs.start_inline(conn, self.scope, 'cg_history_analysis', idempotency_key=uuid.uuid4().hex,
                                                owner=f'confidenceguard:{os.getpid()}')
            read_pin = reader.pin(self.db, self.scope, self.catalog_id, lease=lease, k=k, allow_migrating=self._migrating)
            members = governed_reader.membership_from_index(self.db, read_pin, namespace=namespace)
            disclosed = exposure and ledger.tracking_status(self.db, self.scope, self.catalog_id)['enabled']
            reservation = ledger.reserve(
                self.db, self.store, self.scope, lease, self.catalog_id,
                purpose='outcome_disclosure' if disclosed else 'selection_access', members=members,
                allow_migrating=self._migrating,
                population_digest=digest(sorted(members)), read_k=k,
                metadata={'purpose': purpose_label, 'namespace': namespace, **(metadata or {})},
                authority=None if disclosed else authority)
            reader.release(self.db, read_pin)
        except PlatformError as exc:
            raise _translate(exc) from exc
        governance = {'reservation': {key: (str(value) if isinstance(value, uuid.UUID) else value)
                                      for key, value in asdict(reservation).items()}}
        return lease, governance

    def finish_attempt(self, lease, *, failed=False):
        from numek_platform.execution import jobs
        from numek_platform.errors import FenceLost
        try:
            with self.db.connect() as conn:
                if failed:
                    jobs.fail(conn, lease, {'code': 'analysis_failed'})
                else:
                    jobs.complete(conn, lease, {})
        except FenceLost:
            pass
