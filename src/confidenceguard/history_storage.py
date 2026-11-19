"""Evidence staging, record decoding and catalog entry points for ConfidenceGuard workspaces.

Workers write parent-owned staging (``EvidenceWriter``); the platform publication
is the visibility boundary (``platform_catalog``). The retired catalog v2 is read
only through :class:`LegacyCatalog` (migration and historical reproduction).
"""
from contextlib import contextmanager, closing
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import sqlite3
import stat
import threading
import uuid

from .contracts import EvaluationError, digest, strict_json
from .history_contracts import WorkspaceConfig, HistoricalEvidenceManifest

CATALOG_VERSION = 2
HEX = re.compile(r'^[0-9a-f]{32}$')


def encode_numbers(value):
    if isinstance(value, float) and not math.isfinite(value):
        return {'__cg_number__': 'positive_infinity' if value > 0 else 'negative_infinity' if value < 0 else 'undefined'}
    if isinstance(value, dict):
        return {k: encode_numbers(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [encode_numbers(v) for v in value]
    return value


def decode_numbers(value):
    if isinstance(value, dict):
        if set(value) == {'__cg_number__'}:
            return {'positive_infinity': math.inf, 'negative_infinity': -math.inf, 'undefined': None}[value['__cg_number__']]
        return {k: decode_numbers(v) for k, v in value.items()}
    if isinstance(value, list):
        return [decode_numbers(v) for v in value]
    return value


def serialized(value):
    return json.dumps(encode_numbers(value), sort_keys=True, ensure_ascii=True, separators=(',', ':'), allow_nan=False).encode()


def fsync_directory(path):
    if os.name != 'nt':
        fd = os.open(path, os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0))
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


def private_directory(path):
    path = Path(path).absolute()
    # Check every existing component before mkdir or chmod; never follow a link.
    for part in (path, *path.parents):
        if part.is_symlink():
            raise EvaluationError('Workspace paths must not contain symbolic links.', 'unsafe_workspace')
    path.mkdir(parents=True, mode=0o700, exist_ok=True)
    if not path.is_dir() or hasattr(os, 'getuid') and path.stat().st_uid != os.getuid():
        raise EvaluationError('Workspace ownership differs.', 'unsafe_workspace')
    os.chmod(path, 0o700)
    return path


def private_file(path, mode='xb'):
    flags = os.O_NOFOLLOW if hasattr(os, 'O_NOFOLLOW') else 0
    flags |= os.O_WRONLY | os.O_CREAT | os.O_EXCL if mode == 'xb' else os.O_RDONLY
    fd = os.open(path, flags, 0o600)
    info = os.fstat(fd)
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_mode & 0o077 or hasattr(os,'getuid') and info.st_uid != os.getuid():
        os.close(fd)
        raise EvaluationError('Protected file ownership or permissions differ.', 'unsafe_permissions')
    return os.fdopen(fd, mode)


def file_digest(path):
    h = hashlib.sha256(); size = 0
    with private_file(path, 'rb') as stream:
        for block in iter(lambda: stream.read(1024**2), b''):
            h.update(block); size += len(block)
    return h.hexdigest(), size


def _safe_name(identifier):
    if not isinstance(identifier, str) or not HEX.fullmatch(identifier):
        raise EvaluationError('Invalid opaque object identity.', 'unknown_object')
    return identifier


@contextmanager
def file_lock(path, exclusive=True):
    flags = os.O_RDWR | os.O_CREAT | getattr(os, 'O_NOFOLLOW', 0)
    fd = os.open(path, flags, 0o600)
    info = os.fstat(fd)
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_mode & 0o077 or hasattr(os,'getuid') and info.st_uid != os.getuid():
        os.close(fd)
        raise EvaluationError('Unsafe workspace lock.', 'unsafe_workspace')
    try:
        try:
            if os.name == 'nt':
                import msvcrt
                # Windows byte-range locks serialize access conservatively.
                if info.st_size == 0:
                    os.write(fd, b'0')
                os.lseek(fd, 0, 0); msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(fd, (fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH) | fcntl.LOCK_NB)
        except (BlockingIOError, OSError) as exc:
            raise EvaluationError('Workspace is busy; retry after the current operation.', 'workspace_busy') from exc
        yield
    finally:
        if os.name != 'nt':
            import fcntl
            fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


class EvidenceWriter:
    """Bounded worker writer. Index entries contain locations, never event values."""
    def __init__(self, directory, config, operation_id, check=None):
        self.directory = Path(directory)
        self.config = WorkspaceConfig.from_dict(config) if isinstance(config, dict) else config
        self.operation_id = operation_id
        self.check = check or (lambda *args: None)
        self.objects = []; self.stream = None; self.kind = None; self.bytes = 0; self.records = 0
        self.total_bytes = 0; self.total_records = 0; self.metadata = {}
        self.chunks = {}; self.bounds = {}
        self.index = private_file(self.directory / 'index.jsonl')

    def _finish_chunk(self):
        if self.stream is None:
            return
        self.stream.flush(); os.fsync(self.stream.fileno()); self.stream.close()
        self.objects.append({'id': self.object_id, 'kind': self.kind, 'sha256': self.h.hexdigest(), 'bytes': self.bytes,
                             'records': self.records, 'encoding': 'utf8_jsonl_v1', 'normalization_version': 'historical_facts_v1', 'pruning': self.bounds.pop(self.object_id,{})})
        self.stream = None

    def add(self, kind, identity, payload, *, revision='initial', predecessor=None, available_ns=None, authority=None, reason=None):
        key = digest(identity)
        record = {'kind': kind, 'key': key, 'identity': identity, 'revision': revision, 'payload': encode_numbers(payload),
                  'predecessor': predecessor, 'available_ns': str(available_ns) if available_ns is not None else None,
                  'authority': authority, 'reason': reason}
        record['fact_digest'] = digest(record)
        raw = serialized(record) + b'\n'
        if len(raw) > self.config.max_record_bytes:
            raise EvaluationError('Historical record exceeds the configured bound.', 'history_record_limit')
        if self.kind != kind:
            if self.stream is not None:
                self.chunks[self.kind] = (self.stream, self.object_id, self.bytes, self.records, self.h)
            previous = self.chunks.pop(kind, None)
            if previous:
                self.stream, self.object_id, self.bytes, self.records, self.h = previous
            else:
                self.stream = None
            self.kind = kind
        if self.stream is None or self.bytes + len(raw) > self.config.chunk_bytes:
            self._finish_chunk(); self.object_id = uuid.uuid4().hex; self.kind = kind
            self.stream = private_file(self.directory / (self.object_id + '.jsonl'))
            self.bytes = 0; self.records = 0; self.h = hashlib.sha256()
        bounds = self.bounds.setdefault(self.object_id,{'namespace':payload.get('namespace'),'variant':payload.get('variant'),'minimum_clock_ns':None,'maximum_clock_ns':None,'unresolved_clock_records':0,'maximum_record_bytes':0})
        tick = (payload.get('time') or payload.get('available') or {}).get('tick')
        bounds['maximum_record_bytes']=max(bounds['maximum_record_bytes'],len(raw))
        if tick is None:bounds['unresolved_clock_records']+=1
        else:
            bounds['minimum_clock_ns']=str(min(int(tick),int(bounds['minimum_clock_ns']))) if bounds['minimum_clock_ns'] is not None else str(tick)
            bounds['maximum_clock_ns']=str(max(int(tick),int(bounds['maximum_clock_ns']))) if bounds['maximum_clock_ns'] is not None else str(tick)
        if bounds['namespace'] != payload.get('namespace'):bounds['namespace']=None
        if bounds['variant'] != payload.get('variant'):bounds['variant']=None
        entry = {'kind': kind, 'key': key, 'revision': revision, 'fact_digest': record['fact_digest'],
                 'object_id': self.object_id, 'offset': self.bytes, 'length': len(raw)}
        self.stream.write(raw); self.h.update(raw); self.index.write(serialized(entry) + b'\n')
        self.bytes += len(raw); self.records += 1; self.total_bytes += len(raw); self.total_records += 1
        if self.total_bytes > self.config.max_bytes:
            raise EvaluationError('Historical capture exceeds persistent storage admission.', 'history_quota')
        if self.total_records % 512 == 0:
            self.check('historical capture', self.bytes)
            disk = shutil.disk_usage(self.directory)
            if disk.free < self.config.free_disk_bytes:
                raise EvaluationError('Historical capture exhausted free-space reserve.', 'disk_exhausted')
        return key

    def finish(self, metadata):
        self.add('capture_metadata', [self.operation_id], metadata)
        self._finish_chunk()
        while self.chunks:
            self.kind, previous = self.chunks.popitem()
            self.stream, self.object_id, self.bytes, self.records, self.h = previous
            self._finish_chunk()
        self.index.flush(); os.fsync(self.index.fileno()); self.index.close()
        manifest = HistoricalEvidenceManifest(self.operation_id, tuple(self.objects), encode_numbers(metadata)).to_dict()
        manifest['content_digest'] = digest(manifest)
        with private_file(self.directory / 'capture.json') as stream:
            stream.write(serialized(manifest)); stream.flush(); os.fsync(stream.fileno())
        fsync_directory(self.directory)
        return manifest

    def add_features(self,envelopes,field_ids):
        from .feature_storage import write_features
        objects,locations=write_features(self.directory,envelopes,field_ids=field_ids,check=self.check)
        self.objects.extend(objects)
        for entry in locations:self.index.write(serialized(entry)+b'\n')
        self.total_bytes+=sum(o['bytes'] for o in objects);self.total_records+=len(locations)
        if self.total_bytes>self.config.max_bytes:raise EvaluationError('Feature capture exceeds storage admission.','history_quota')

    def add_vectors(self,matrix):
        from .feature_storage import write_vectors
        objects,locations=write_vectors(self.directory,matrix,check=self.check)
        self.objects.extend(objects)
        for entry in locations:self.index.write(serialized({'kind':'vector_location',**entry})+b'\n')
        self.total_bytes+=sum(o['bytes'] for o in objects)
        if self.total_bytes>self.config.max_bytes:raise EvaluationError('Vector capture exceeds storage admission.','history_quota')
        return locations

    def add_blob(self,path,*,format,identity,source_roots=None):
        """Stream CG6 model/media/output bytes; descriptors remain ordinary facts.

        Reopening, backup and publication verify opaque bytes, never execute them.
        The v2 encoding/dependency columns require no catalog schema migration.
        """
        oid=uuid.uuid4().hex;target=self.directory/(oid+'.cgblob')
        h=hashlib.sha256();size=0
        from contextlib import ExitStack
        with ExitStack() as contexts:
            if source_roots is None:inp=contexts.enter_context(private_file(path,'rb'))
            else:
                from . import compat
                inp,_=contexts.enter_context(compat.secure_open(path,source_roots))
            out=contexts.enter_context(private_file(target));before=os.fstat(inp.fileno())
            while block:=inp.read(1024**2):
                size+=len(block)
                if self.total_bytes+size>self.config.max_bytes:raise EvaluationError('Binary artifact exceeds storage admission.','history_quota')
                self.check('binary artifact capture',len(block));out.write(block);h.update(block)
            after=os.fstat(inp.fileno())
            if (before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)!=(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns):raise EvaluationError('Binary source changed during retention.','source_changed')
            out.flush();os.fsync(out.fileno())
        obj={'id':oid,'kind':'cg6_artifact','encoding':'opaque_artifact_bytes_v1','sha256':h.hexdigest(),'bytes':size,'records':0}
        self.objects.append(obj);self.total_bytes+=size
        descriptor={'object_id':oid,'format':format,'sha256':obj['sha256'],'bytes':size,'depends_on_objects':[oid]}
        self.add('cg6_artifact_descriptor',identity,descriptor)
        return descriptor


def authority_file(root):
    """The file that proves a workspace root: the platform binding or the v2 catalog."""
    root = Path(root)
    return root / 'platform.json' if (root / 'platform.json').is_file() else root / 'catalog.sqlite3'


class Catalog:
    """ConfidenceGuard evidence catalog: every workspace is stored on the NUMEK platform.

    ``Catalog(root)`` opens the platform-backed implementation for a root bound
    to the platform (``platform.json``), and ``Catalog(root, create=True)``
    creates one. Catalog v2 has been retired as a writer (CG7 S3): a v2 root is
    refused with ``migration_required`` until ``confidenceguard.migration``
    migrates it, and :class:`LegacyCatalog` remains as its read-only view for
    migration and historical reproduction. This base holds only behaviour both
    share.
    """

    def __new__(cls, root=None, *args, create=False, config=None, **kwargs):
        if cls is Catalog and root is not None:
            from .platform_catalog import PlatformCatalog, platform_bound
            if platform_bound(root) or create:
                return super().__new__(PlatformCatalog)
            if (Path(root) / 'catalog.sqlite3').exists():
                raise EvaluationError('This workspace uses the retired catalog v2. Migrate it to the NUMEK platform '
                                      '(confidenceguard workspace migrate --path ...).', 'migration_required')
            raise EvaluationError('Initialize the workspace explicitly.', 'workspace_missing')
        return super().__new__(cls)


    def _fault(self, boundary):
        """Test-only injection point; no environment-driven production fault behavior."""

    def _read_record(self,path,codec,offset,length,cache):
        if codec=='utf8_jsonl_v1':
            key=('json',str(path))
            if key not in cache:
                if len(cache)>=8:
                    old=cache.pop(next(iter(cache)))
                    if hasattr(old,'close'):old.close()
                cache[key]=private_file(path,'rb')
            stream=cache[key];stream.seek(offset);raw=stream.read(length)
            if len(raw)!=length or length>self.config.max_record_bytes:raise EvaluationError('Invalid retained record location.','evidence_changed')
            return strict_json(raw)
        if codec=='typed_feature_rows_v1':
            from .feature_storage import read_features
            key=('parquet',str(path),offset)
            if key not in cache:
                if len(cache)>=2:
                    old=cache.pop(next(iter(cache)))
                    if hasattr(old,'close'):old.close()
                # One bounded row group, never one scan per feature row.
                group={v.pop('_row_index'):v for v in read_features(path,locations={offset:set(range(65536))})}
                for value in group.values():value.pop('_row_group',None)
                cache[key]=group
            value=cache[key].get(length-1)
            if value is None:raise EvaluationError('Invalid columnar row location.','evidence_changed')
            return json.loads(json.dumps(value))
        raise EvaluationError('Objects of this codec do not contain facts.','unsupported_codec')

    def sealed_reserve_units(self, units):
        """Units that are sealed-reserve entities (v2 catalogs have no reserve)."""
        return set()

    def assessment(self, aid):
        # Fact receipt is authoritative even after a crash before the optional list index.
        values = list(self.iter_facts('assessment', keys=[digest([aid])], max_records=1))
        if not values: raise EvaluationError('Assessment is unavailable.', 'assessment_unavailable')
        from .investigation_storage import read_packet
        packet = read_packet(self,values[0])
        from .history_result import LongitudinalResult
        if packet['result'].get('schema_version') == 'confidenceguard.longitudinal_result/1.0':
            result = LongitudinalResult.from_dict(packet['result'], private=packet['manifest'])
            result._workspace_location = str(self.root)
            return result
        from .result import EvaluationResult
        result=EvaluationResult.from_dict(packet['result'], private=packet['manifest'])
        if result.data.get('methodology_id') in {'failure_investigation_v1','policy_selection_v1','predictor_robustness_v1'}:result._workspace_location=str(self.root)
        return result

    @classmethod
    def restore(cls, backup, destination):
        """Restore a workspace backup as a new platform workspace (a catalog v2 backup is restored, then migrated)."""
        from .platform_catalog import PlatformCatalog
        if (Path(backup) / 'platform').is_dir():
            return PlatformCatalog.restore(backup, destination)
        from .migration import restore_legacy_backup
        return restore_legacy_backup(backup, destination)


class LegacyCatalog(Catalog):
    """Read-only view of a catalog v1/v2 workspace, including one frozen for platform migration.

    Used by the v2 -> platform migration to read the source and to compute the
    reference answers its validation compares against (fact reconstruction,
    assessments, deletion previews, evidence-use overlap). It never writes: the
    SQLite connection is opened read-only and every mutating method refuses.
    """
    FROZEN_VERSION = 9002

    def __new__(cls, root=None, *args, **kwargs):
        return object.__new__(cls)

    def __init__(self, root):
        self.root = Path(root).absolute()
        if not self.root.is_dir() or not (self.root / 'catalog.sqlite3').is_file():
            raise EvaluationError('Legacy catalog not found.', 'workspace_missing')
        self.db_path = self.root / 'catalog.sqlite3'
        self.operation_path = self.root / '.operation.lock'; self.objects_lock = self.root / '.objects.lock'
        self._verified = {}; self._guard = threading.RLock()
        self._validate()

    def _connect(self):
        if self.db_path.is_symlink():
            raise EvaluationError('Unsafe catalog.', 'unsafe_workspace')
        db = sqlite3.connect(f'file:{self.db_path}?mode=ro', uri=True, timeout=1, isolation_level=None)
        db.row_factory = sqlite3.Row
        return db

    def _validate(self):
        with closing(self._connect()) as db:
            version = db.execute('PRAGMA user_version').fetchone()[0]
            settings = {r['key']: strict_json(r['value']) for r in db.execute('SELECT * FROM settings')}
        if version == self.FROZEN_VERSION:
            version = (settings.get('numek_migration') or {}).get('original_user_version')
        if version not in (1, CATALOG_VERSION):
            raise EvaluationError('Unsupported legacy catalog version.', 'catalog_version')
        self.catalog_version = version
        self.settings = settings
        self.instance_id = settings['instance_id']; self.config = WorkspaceConfig.from_dict(settings['config'])

    @contextmanager
    def operation(self, *, exclusive_objects=False):
        yield

    # v2 read paths (moved from the retired v2 catalog) -------------------------------------
    def _object_path(self, identifier):
        identifier=_safe_name(identifier);codec='utf8_jsonl_v1'
        if self.catalog_version>=2:
            with closing(self._connect()) as db:
                row=db.execute('SELECT encoding FROM objects WHERE id=?',(identifier,)).fetchone()
                if row:codec=row[0]
        from .feature_storage import extension
        return self.root / 'objects' / (identifier+extension(codec))

    def status(self):
        with closing(self._connect()) as db:
            sequence = json.loads(db.execute("SELECT value FROM settings WHERE key='sequence'").fetchone()[0])
            counts = {kind: n for kind, n in db.execute("SELECT f.kind,count(*) FROM facts f JOIN operations p ON p.id=f.operation_id JOIN objects o ON o.id=f.object_id WHERE p.state='committed' AND o.state='active' GROUP BY f.kind")}
            return {'instance_id': self.instance_id, 'catalog_sequence': sequence, 'config': self.config.to_dict(),
                    'facts': counts, 'bytes': self.reserve(), 'journal_mode': db.execute('PRAGMA journal_mode').fetchone()[0],
                    'sqlite_version': sqlite3.sqlite_version, 'automatic_eviction': False,'catalog_version':self.catalog_version,
                    'exposure_continuity':json.loads(db.execute("SELECT value FROM settings WHERE key='exposure_continuity'").fetchone()[0]) if self.catalog_version>=2 else 'unknown'}

    def receipt(self, request_id, request_digest):
        with closing(self._connect()) as db:
            row = db.execute('SELECT request_digest,state,receipt FROM operations WHERE request_id=?',(request_id,)).fetchone()
            if row is None:return None
            if row['request_digest'] != request_digest:raise EvaluationError('Request ID already has different content.','idempotency_conflict')
            if row['state'] != 'committed':raise EvaluationError('Recover the unfinished operation before retry.','operation_incomplete')
            return strict_json(row['receipt'])

    def _verify_object(self, identifier, sha, size):
        path = self._object_path(identifier)
        with private_file(path, 'rb') as stream:
            info = os.fstat(stream.fileno())
        token = (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns, sha)
        if self._verified.get(identifier) != token:
            actual, count = file_digest(path)
            if actual != sha or count != size:
                raise EvaluationError('Committed evidence changed; no substitute was used.', 'evidence_changed')
            self._verified[identifier] = token
        return path

    def iter_facts(self, kind=None, *, sequence=None, keys=None, fact_digests=(), batch_ids=(), require_complete=True, max_records=30000000, check=None, _logical_order=False):
        where = ["p.state='committed'", "o.state='active'"]; args = []
        if kind: where.append('f.kind=?'); args.append(kind)
        if sequence is not None: where.append('p.sequence<=?'); args.append(sequence)
        if fact_digests:
            where.append('f.fact_digest IN ('+','.join('?' for _ in fact_digests)+')');args.extend(fact_digests)
        with closing(self._connect()) as db:
            if batch_ids:
                placeholders = ','.join('?' for _ in batch_ids)
                where.append(f"EXISTS(SELECT 1 FROM occurrences oc JOIN operations op ON op.id=oc.operation_id WHERE oc.fact_id=f.id AND op.state='committed' AND oc.operation_id IN ({placeholders})" + (' AND op.sequence<=?' if sequence is not None else '') + ')')
                args.extend(batch_ids)
                if sequence is not None: args.append(sequence)
            if keys is not None:
                db.execute('CREATE TEMP TABLE selected_keys(key TEXT PRIMARY KEY)')
                db.executemany('INSERT OR IGNORE INTO selected_keys VALUES (?)', ((k,) for k in keys))
                where.append('f.key IN (SELECT key FROM selected_keys)')
            missing_where = [w for w in where if w != "o.state='active'"] + ["o.state!='active'"]
            missing = db.execute('SELECT count(*) FROM facts f JOIN objects o ON o.id=f.object_id JOIN operations p ON p.id=f.operation_id WHERE ' + ' AND '.join(missing_where),args).fetchone()[0]
            if missing and require_complete:
                raise EvaluationError('Selected historical evidence was deleted or is unavailable; choose an intact explicit batch population.', 'historical_evidence_unavailable')
            codec_column='o.encoding' if self.catalog_version>=2 else "'utf8_jsonl_v1' AS encoding"
            sql = 'SELECT f.*,o.sha256,o.bytes,'+codec_column+',p.sequence FROM facts f JOIN objects o ON o.id=f.object_id JOIN operations p ON p.id=f.operation_id WHERE ' + ' AND '.join(where) + (' ORDER BY f.id' if _logical_order else ' ORDER BY f.object_id,f.offset,f.length')
            count = 0; current = None; cache={}
            try:
                for row in db.execute(sql, args):
                    count += 1
                    if count > max_records:
                        raise EvaluationError('Historical scan record admission exceeded.', 'history_scan_limit')
                    if current != row['object_id']:
                        path = self._verify_object(row['object_id'], row['sha256'], row['bytes'])
                        current = row['object_id']
                    value=self._read_record(path,row['encoding'],row['offset'],row['length'],cache);fd=value.pop('fact_digest',None)
                    if fd != row['fact_digest'] or fd != digest(value) or digest(value['identity']) != row['key']:
                        raise EvaluationError('Historical fact identity differs.', 'evidence_changed')
                    value['fact_digest'] = fd; value['recorded_sequence'] = row['sequence']
                    value['object_id'] = row['object_id']; value['offset'] = row['offset']; value['record_bytes'] = row['length'] if row['encoding']=='utf8_jsonl_v1' else len(serialized(value))
                    if check and count % 512 == 0: check('historical evidence scan')
                    yield value
            finally:
                for stream in cache.values():
                    if hasattr(stream,'close'):stream.close()

    def variants(self):
        with closing(self._connect()) as db:
            return {r['id']: strict_json(r['metadata']) for r in db.execute("SELECT v.* FROM variants v JOIN operations p ON p.id=v.operation_id WHERE p.state='committed'")}

    # Backend-neutral queries used by CG4-CG6 (the platform catalog implements the same API).

    @property
    def authority_file(self):
        return self.root / 'catalog.sqlite3'

    def object_ids_for_key(self, kind, key):
        with closing(self._connect()) as db:
            return {r[0] for r in db.execute('SELECT object_id FROM facts WHERE kind=? AND key=?', (kind, key))}

    def object_ids_for_fact_digests(self, digests):
        found, digests = set(), list(digests)
        with closing(self._connect()) as db:
            for start in range(0, len(digests), 512):
                chunk = digests[start:start+512]
                found.update(r[0] for r in db.execute('SELECT DISTINCT object_id FROM facts WHERE fact_digest IN ('+','.join('?' for _ in chunk)+')', chunk))
        return found

    def prediction_digests_in_operation(self, operation_id):
        with closing(self._connect()) as db:
            return {r[0] for r in db.execute("SELECT f.fact_digest FROM facts f JOIN occurrences c ON c.fact_id=f.id WHERE f.kind='prediction' AND c.operation_id=?", (operation_id,))}

    def object_operations(self, object_ids):
        found, object_ids = {}, list(object_ids)
        with closing(self._connect()) as db:
            for start in range(0, len(object_ids), 512):
                chunk = object_ids[start:start+512]
                found.update(db.execute('SELECT id,operation_id FROM objects WHERE id IN ('+','.join('?' for _ in chunk)+')', chunk))
        return found

    def vector_location(self, vector_digest):
        """Location of a retained vector, or None. Raises when its object is no longer active."""
        with closing(self._connect()) as db:
            location = db.execute('SELECT * FROM vector_locations WHERE digest=?', (vector_digest,)).fetchone()
            if location is None:
                return None
            obj = db.execute('SELECT * FROM objects WHERE id=?', (location['object_id'],)).fetchone()
        if obj is None or obj['state'] != 'active':
            raise EvaluationError('Retained vector is unavailable.', 'historical_evidence_unavailable')
        return {'object_id': location['object_id'], 'row_index': location['row_index'], 'sha256': obj['sha256'], 'bytes': obj['bytes']}

    def vector_matrix(self, location):
        import numpy as np
        path = self._verify_object(location['object_id'], location['sha256'], location['bytes'])
        return np.load(path, mmap_mode='r', allow_pickle=False, max_header_size=10000)

    def blob_path(self, object_id):
        """Path of a verified retained opaque object (CG6 models, outputs, media)."""
        return self._object_path(_safe_name(object_id))

    def deletion_preview(self, *, object_ids=(), assessment_ids=(), batch_ids=(), purge=False):
        if not isinstance(purge,bool):raise EvaluationError('purge must be boolean.')
        status = self.status()
        with closing(self._connect()) as db:
            objects = set(object_ids)
            for bid in batch_ids:
                if not db.execute("SELECT 1 FROM operations WHERE id=? AND state='committed'",(bid,)).fetchone():raise EvaluationError('Unknown batch association.','unknown_batch')
            for aid in assessment_ids:
                if not db.execute('SELECT 1 FROM assessments WHERE id=?',(aid,)).fetchone():raise EvaluationError('Unknown assessment.','assessment_unavailable')
                for row in db.execute("SELECT object_id FROM facts WHERE kind='assessment' AND key=?", (digest([aid]),)): objects.add(row[0])
            # Large CG4 assessment parts are private copies, not orphanable
            # auxiliary objects. Deleting their header deletes the entire bundle.
            for oid in tuple(objects):
                source=db.execute("SELECT operation_id FROM objects WHERE id=? AND kind='assessment'",(oid,)).fetchone()
                if source:objects.update(r[0] for r in db.execute("SELECT id FROM objects WHERE operation_id=? AND kind='cg4_packet_part'",(source[0],)))
                if source:objects.update(r[0] for r in db.execute("SELECT id FROM objects WHERE operation_id=? AND kind IN ('cg6_artifact','cg6_artifact_descriptor')",(source[0],)))
            if purge: objects = {r[0] for r in db.execute('SELECT id FROM objects')}
            for oid in objects:
                if not db.execute('SELECT 1 FROM objects WHERE id=?', (_safe_name(oid),)).fetchone():
                    raise EvaluationError('Unknown deletion object.', 'unknown_object')
            affected = set()
            for oid in objects:
                affected.update(r[0] for r in db.execute('SELECT DISTINCT operation_id FROM occurrences WHERE fact_id IN (SELECT id FROM facts WHERE object_id=?)', (oid,)))
            evidence_objects = [oid for oid in objects if db.execute('SELECT kind FROM objects WHERE id=?', (oid,)).fetchone()[0] != 'assessment']
            # Derived and raw copies can contain the same event values. The safe purge
            # unit is the complete affected capture, never a misleading single row.
            if evidence_objects or self.catalog_version>=2 and objects:
                expanded = True
                while expanded:
                    before = len(objects)
                    # Dependency closure can discover a derived assessment
                    # header after the initial seed expansion. Its owned packet
                    # parts and binary copies belong to that same deletion unit.
                    # Expand them on every pass so preview and revalidation use
                    # the same fixed point, including restatement descendants.
                    for oid in tuple(objects):
                        source=db.execute("SELECT operation_id FROM objects WHERE id=? AND kind='assessment'",(oid,)).fetchone()
                        if source:objects.update(r[0] for r in db.execute("SELECT id FROM objects WHERE operation_id=? AND kind IN ('cg4_packet_part','cg6_artifact','cg6_artifact_descriptor')",(source[0],)))
                    captures=set()
                    for oid in tuple(objects):
                        if db.execute('SELECT kind FROM objects WHERE id=?',(oid,)).fetchone()[0] == 'assessment':continue
                        captures.update(r[0] for r in db.execute('SELECT DISTINCT operation_id FROM occurrences WHERE fact_id IN (SELECT id FROM facts WHERE object_id=?)',(oid,)))
                    for operation in captures:
                        objects.update(r[0] for r in db.execute('SELECT id FROM objects WHERE operation_id=?',(operation,)))
                    if self.catalog_version>=2 and objects:
                        for child,parent in db.execute('SELECT object_id,depends_on FROM artifact_dependencies'):
                            if parent in objects:objects.add(child)
                    expanded = len(objects) != before
            # Compute receipts after closure. Including derived assessment roots
            # in a subsequent preview must not change its dependency fixed point.
            affected=set()
            for oid in objects:affected.update(r[0] for r in db.execute('SELECT DISTINCT operation_id FROM occurrences WHERE fact_id IN (SELECT id FROM facts WHERE object_id=?)',(oid,)))
            impacted = [r[0] for r in db.execute('SELECT id FROM assessments')] if evidence_objects else []
            plan = {'id': uuid.uuid4().hex, 'instance_id': self.instance_id, 'catalog_sequence': status['catalog_sequence'],
                    'object_ids': sorted(objects), 'assessment_ids': list(assessment_ids), 'batch_ids': list(batch_ids),
                    'affected_batches': sorted(affected), 'potentially_impacted_assessments': impacted, 'purge': bool(purge), 'retained_assessments_may_contain_values': True}
            plan['confirmation'] = digest(plan)
            return plan

    def _refuse(self, *args, **kwargs):
        raise EvaluationError('Catalog v2 is read-only; migrate the workspace to the NUMEK platform.', 'migration_required')

    def reserve(self, additional=0):
        if additional:
            self._refuse()
        return 0                                   # no write admission is ever needed

    begin = commit_capture = add_assessment = delete = set_saving = recover = backup = migrate = _refuse
