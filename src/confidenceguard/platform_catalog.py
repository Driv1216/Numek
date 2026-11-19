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
        self.governance = None
        self.operation_path = self.root / '.operation.lock'
        self.objects_lock = self.root / '.objects.lock'
        for lock in (self.operation_path, self.objects_lock):
            if not lock.exists():
                with private_file(lock):
                    pass
        private_directory(self.root / 'staging')
        if create and not platform_bound(self.root):
            self._create_binding(config or WorkspaceConfig())
        binding = strict_json((self.root / BINDING).read_bytes())
        if binding.get('format') != BINDING_FORMAT:
            raise EvaluationError('Unsupported platform binding.', 'catalog_version')
        self.binding = binding
        self.db = Database(self._dsn(binding), application_name='confidenceguard')
        self.store = LocalObjectStore(self.root / binding['store'])
        from numek_platform.scope import OrgScope
        self.scope = OrgScope(uuid.UUID(binding['org_id']))
        self.catalog_id = uuid.UUID(binding['catalog_id'])
        self.catalog_version = CATALOG_VERSION
        self._validate()

    @staticmethod
    def _dsn(binding):
        if binding.get('dsn_env'):
            dsn = os.environ.get(binding['dsn_env'])
            if not dsn:
                raise EvaluationError('The platform connection for this workspace is not configured.', 'platform_unavailable')
            return dsn
        from numek_platform.local import LocalCluster
        cluster = LocalCluster(Path(binding['local_cluster']) if Path(binding['local_cluster']).is_absolute()
                               else Path(binding['_root']) / binding['local_cluster'])
        if not cluster.running():
            cluster.start()
        return cluster.dsn()

    def _create_binding(self, config):
        from numek_platform.db import Database
        from numek_platform.db.migrator import migrate
        from numek_platform.evidence.catalogs import create_catalog
        from numek_platform.scope import create_org, get_org
        from numek_platform.errors import PlatformError
        from psycopg.types.json import Jsonb
        binding = {'format': BINDING_FORMAT, 'store': 'platform-objects'}
        if os.environ.get(DSN_ENV):
            binding['dsn_env'] = DSN_ENV          # the connection string itself is never written to disk
            dsn = os.environ[DSN_ENV]
        else:
            from numek_platform.local import LocalCluster
            cluster = LocalCluster(self.root / 'platform')
            cluster.start()
            binding['local_cluster'] = 'platform'
            dsn = cluster.dsn()
        database = Database(dsn)
        migrate(database)
        instance_id = uuid.uuid4().hex
        with database.transaction() as conn:
            conn.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))', ('numek:org:' + ORG_NAME,))
            try:
                scope = get_org(conn, ORG_NAME)
            except PlatformError:
                scope = create_org(conn, ORG_NAME)
            catalog_id = create_catalog(conn, scope, f'workspace:{instance_id}', analytical_instance_id=instance_id,
                                        branch_id=uuid.uuid4().hex, continuity_state='unknown',
                                        continuity_token=uuid.uuid4().hex, config=config.to_dict())
            conn.execute('UPDATE catalogs SET exposure_tracking = false WHERE id = %s', (catalog_id,))
            for key, value in {'instance_id': instance_id, 'config': config.to_dict(), 'retired': False,
                               'schema': CATALOG_VERSION, 'created_at': now()}.items():
                conn.execute('INSERT INTO cg_settings(catalog_id, key, value) VALUES (%s, %s, %s)',
                             (catalog_id, key, Jsonb(value)))
        binding.update(org_id=str(scope.org_id), catalog_id=str(catalog_id))
        with private_file(self.root / BINDING) as stream:
            stream.write(serialized(binding))
            stream.flush()
            os.fsync(stream.fileno())
        fsync_directory(self.root)

    def _setting(self, conn, key):
        row = conn.execute('SELECT value FROM cg_settings WHERE catalog_id = %s AND key = %s', (self.catalog_id, key)).fetchone()
        return None if row is None else row['value']

    def _validate(self):
        with self.db.connect() as conn:
            row = conn.execute('SELECT state FROM catalogs WHERE id = %s', (self.catalog_id,)).fetchone()
            if row is None:
                raise EvaluationError('Workspace catalog is missing from the platform.', 'workspace_missing')
            if row['state'] == 'retired' or self._setting(conn, 'retired'):
                raise EvaluationError('Workspace was retired.', 'workspace_retired')
            if row['state'] != 'active':
                raise EvaluationError('This catalog is not available for use.', 'catalog_unavailable')
            self.instance_id = self._setting(conn, 'instance_id')
            self.config = WorkspaceConfig.from_dict(self._setting(conn, 'config'))

    # Unported SQLite surface ----------------------------------------------------
    def _connect(self):
        raise EvaluationError('This workspace runs on the platform; this operation is not yet ported.', 'platform_unported')

    def deletion_preview(self, **_kwargs):
        return self._connect()

    def delete(self, _plan):
        return self._connect()

    def backup(self, _destination):
        return self._connect()

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
        if codec != codecs.JSONL:
            raise EvaluationError('This evidence codec is not yet readable from the platform.', 'platform_unported')
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
    def commit_capture(self, identifier, *, cancel=None, receipt_extra=None):
        try:
            return self._commit_capture(identifier, cancel=cancel, receipt_extra=receipt_extra)
        except BaseException:
            self._finish_lease(identifier, failed=True)
            raise

    def _commit_capture(self, identifier, *, cancel, receipt_extra):
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

        def before_head(conn, publication_id):
            self._record_relations(conn, publication_id, metadata, rows, dependencies, vector_rows, expected)

        cg_receipt = {'operation_id': identifier, 'new_facts': new, 'duplicate_occurrences': duplicates,
                      'capture_digest': expected, **(receipt_extra or {})}
        try:
            receipt = publish(self.db, self.scope, lease, self.catalog_id, request_id=request_id,
                              request_digest=request_digest, kind='cg_capture', objects=refs, facts=rows,
                              before_head=before_head, publication_id=_uuid(identifier),
                              reservations=getattr(self, '_consumes', {}).pop(identifier, ()),
                              receipt_extra={'cg': {**cg_receipt, 'catalog_sequence': None}},
                              after_head=lambda conn, pid, k: (conn.execute(
                                  "UPDATE publications SET receipt = jsonb_set(receipt, '{cg,catalog_sequence}', to_jsonb(%s::bigint)) "
                                  'WHERE id = %s', (k, pid)), self._fault('before_catalog_commit')))
        except PlatformError as exc:
            raise _translate(exc) from exc
        if receipt.replayed:
            result = self.receipt(request_id, request_digest)
        else:
            result = {'operation_id': identifier, 'catalog_sequence': receipt.sequence, 'new_facts': new,
                      'duplicate_occurrences': duplicates, 'capture_digest': expected, **(receipt_extra or {})}
        self._fault('catalog_committed')
        self._finish_lease(identifier)
        shutil.rmtree(stage)
        fsync_directory(self.root / 'staging')
        return result

    def _row(self, FactRow, entry, fact, claimed, object_id, locator_kind, a, b, entity_of):
        payload = fact.get('payload') or {}
        namespace = payload.get('namespace') if isinstance(payload, dict) else None
        event_hash = entity_hash = target_key = opportunity_key = None
        kind = entry['kind']
        if kind == 'opportunity':
            opportunity_key = entry['key']
            entity_of[opportunity_key] = payload.get('entity')
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
        self.governance = governance
        return self

    def iter_facts(self, kind=None, *, sequence=None, keys=None, fact_digests=(), batch_ids=(), require_complete=True,
                   max_records=30000000, check=None, _logical_order=False):
        from numek_platform.evidence import reader
        from numek_platform.errors import PlatformError
        from numek_platform.governance import reader as governed_reader
        from numek_platform.governance.ledger import Reservation
        try:
            head = self.head()
            k = head if sequence is None else min(int(sequence), head)
            read_pin = reader.pin(self.db, self.scope, self.catalog_id, holder=f'confidenceguard:{os.getpid()}', k=k)
            try:
                filters = {'kinds': None if kind is None else [kind], 'keys': None if keys is None else list(keys),
                           'fact_digests': list(fact_digests) or None, 'require_complete': require_complete,
                           'occurrence_publications': [_uuid(b) for b in batch_ids] or None,
                           'order': 'logical' if _logical_order else 'physical'}
                if self.governance is not None:
                    reservation = Reservation(**{k2: (uuid.UUID(v) if k2 in ('catalog_id', 'job_id') and v else v)
                                                 for k2, v in self.governance['reservation'].items()})
                    locators = governed_reader.resolve(self.db, self.store, reservation, read_pin, **filters).locators
                else:
                    locators = reader.resolve(self.db, read_pin, **filters)
                if len(locators) > max_records:
                    raise EvaluationError('Historical scan record admission exceeded.', 'history_scan_limit')
                count = 0
                for locator, record in reader.read(self.store, locators, max_record_bytes=self.config.max_record_bytes):
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
            payload['depends_on_objects'] = sorted(dependencies)
            from .investigation_storage import write_packet
            write_packet(writer, 'assessment', [aid], payload)
        else:
            writer.add('assessment', [aid], payload)
        writer.finish({'assessment_id': aid})
        return self.commit_capture(identifier, cancel=cancel, receipt_extra={'assessment_id': aid})

    # Governance for historical analysis -----------------------------------------------------------
    def reserve_history(self, *, namespace, k, purpose_label, metadata=None):
        """Reserve every opportunity of ``namespace`` that has an outcome at K, before reading any.

        Membership comes from identity hashes and outcome *existence* only. Returns
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
            read_pin = reader.pin(self.db, self.scope, self.catalog_id, lease=lease, k=k)
            members = governed_reader.membership_from_index(self.db, read_pin, namespace=namespace)
            reservation = ledger.reserve(
                self.db, self.store, self.scope, lease, self.catalog_id, purpose='outcome_disclosure', members=members,
                population_digest=digest(sorted(members)), read_k=k,
                metadata={'purpose': purpose_label, 'namespace': namespace, **(metadata or {})})
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
