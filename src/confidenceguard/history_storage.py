"""Owner-only immutable JSONL objects and an authoritative SQLite catalog.

The catalog commit is the visibility boundary. Pending rows and orphan files never
become evidence merely because they exist. Workers only write parent-owned staging.
"""
from contextlib import contextmanager, closing
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import secrets
import shutil
import sqlite3
import stat
import threading
import time
import uuid

from .contracts import EvaluationError, digest, strict_json
from .history_contracts import WorkspaceConfig, HistoricalEvidenceManifest, now

CATALOG_VERSION = 1
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


class Catalog:
    """Parent-owned durable state; all filesystem entry points are root constrained."""
    def __init__(self, root, *, create=False, config=None):
        self.root = private_directory(root) if create else Path(root).absolute()
        if not self.root.is_dir():
            raise EvaluationError('Initialize the workspace explicitly.', 'workspace_missing')
        info=self.root.stat()
        if info.st_mode & 0o077 or hasattr(os,'getuid') and info.st_uid != os.getuid():raise EvaluationError('Workspace ownership/permissions differ.','unsafe_workspace')
        for path in (self.root, *self.root.parents):
            if path.is_symlink():
                raise EvaluationError('Unsafe workspace path.', 'unsafe_workspace')
        self.db_path = self.root / 'catalog.sqlite3'
        self.operation_path = self.root / '.operation.lock'; self.objects_lock = self.root / '.objects.lock'
        self._verified = {}; self._guard = threading.RLock()
        if create:
            with file_lock(self.operation_path), file_lock(self.objects_lock):
                if self.db_path.exists():
                    raise EvaluationError('Workspace already exists.', 'workspace_exists')
                for part in ('objects', 'staging'):
                    private_directory(self.root / part)
                fd = os.open(self.db_path, os.O_CREAT | os.O_EXCL | os.O_RDWR, 0o600); os.close(fd)
                self._initialize(config or WorkspaceConfig())
        self._resume_retirement()
        self._validate()

    def _connect(self):
        if self.db_path.is_symlink():
            raise EvaluationError('Unsafe catalog.', 'unsafe_workspace')
        with private_file(self.db_path, 'rb'):
            pass
        db = sqlite3.connect(self.db_path, timeout=1, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON'); db.execute('PRAGMA busy_timeout=1000'); db.execute('PRAGMA synchronous=FULL')
        return db

    def _initialize(self, config):
        v = sqlite3.sqlite_version_info
        fixed = v >= (3, 51, 3) or (3, 44, 6) <= v < (3, 45, 0) or (3, 50, 7) <= v < (3, 51, 0)
        with closing(self._connect()) as db:
            db.execute('PRAGMA journal_mode=' + ('WAL' if fixed else 'DELETE'))
            db.executescript('''
                CREATE TABLE settings(key TEXT PRIMARY KEY,value TEXT NOT NULL);
                CREATE TABLE operations(id TEXT PRIMARY KEY,request_id TEXT UNIQUE NOT NULL,request_digest TEXT NOT NULL,
                    state TEXT NOT NULL,sequence INTEGER UNIQUE,created_at TEXT NOT NULL,receipt TEXT,metadata TEXT);
                CREATE TABLE objects(id TEXT PRIMARY KEY,operation_id TEXT NOT NULL REFERENCES operations(id),
                    sha256 TEXT NOT NULL,bytes INTEGER NOT NULL,kind TEXT NOT NULL,records INTEGER NOT NULL,state TEXT NOT NULL);
                CREATE TABLE facts(id INTEGER PRIMARY KEY,kind TEXT NOT NULL,key TEXT NOT NULL,revision TEXT NOT NULL,
                    fact_digest TEXT NOT NULL,object_id TEXT NOT NULL REFERENCES objects(id),offset INTEGER NOT NULL,
                    length INTEGER NOT NULL,operation_id TEXT NOT NULL REFERENCES operations(id));
                CREATE UNIQUE INDEX fact_identity ON facts(kind,key,revision);
                CREATE INDEX fact_kind_key ON facts(kind,key);
                CREATE TABLE occurrences(operation_id TEXT NOT NULL REFERENCES operations(id),fact_id INTEGER NOT NULL REFERENCES facts(id),
                    PRIMARY KEY(operation_id,fact_id));
                CREATE TABLE variants(id TEXT PRIMARY KEY,metadata TEXT NOT NULL,operation_id TEXT NOT NULL REFERENCES operations(id));
                CREATE TABLE assessments(id TEXT PRIMARY KEY,object_id TEXT NOT NULL REFERENCES objects(id),
                    operation_id TEXT NOT NULL REFERENCES operations(id),digest TEXT NOT NULL,predecessor TEXT,state TEXT NOT NULL);
                CREATE TABLE deletions(id TEXT PRIMARY KEY,plan TEXT NOT NULL,state TEXT NOT NULL);
            ''')
            values = {'instance_id': uuid.uuid4().hex, 'config': config.to_dict(), 'retired': False, 'sequence': 0,
                      'schema': CATALOG_VERSION, 'created_at': now()}
            db.execute('BEGIN IMMEDIATE')
            for key, value in values.items():
                db.execute('INSERT INTO settings VALUES (?,?)', (key, json.dumps(value)))
            db.execute(f'PRAGMA user_version={CATALOG_VERSION}'); db.commit()
        fsync_directory(self.root)

    def _resume_retirement(self):
        # A durable full-purge plan authorizes completion even after the process
        # died after tombstones or while removing the catalog itself.
        if not self.db_path.exists():return
        try:
            with closing(self._connect()) as db:
                if db.execute('PRAGMA user_version').fetchone()[0] != CATALOG_VERSION:return
                retire=any(strict_json(row[0]).get('purge') for row in db.execute('SELECT plan FROM deletions'))
            if retire:
                self._retire_files()
                raise EvaluationError('Workspace was retired.','workspace_retired')
        except sqlite3.DatabaseError:return  # _validate supplies the corruption diagnosis.

    def _retire_files(self):
        with file_lock(self.operation_path),file_lock(self.objects_lock):
            for folder in ('objects','staging'):
                for path in (self.root/folder).iterdir():
                    if path.is_dir():self._remove_owned_stage(path)
                    else:
                        with private_file(path,'rb'):pass
                        path.unlink()
            for suffix in ('-wal','-shm',''):
                path=Path(str(self.db_path)+suffix)
                if path.exists():
                    with private_file(path,'rb'):pass
                    path.unlink()
            marker=self.root/'.retired'
            if not marker.exists():
                with private_file(marker) as stream:stream.write(b'workspace retired\n')
            fsync_directory(self.root)

    def _validate(self):
        try:
            with closing(self._connect()) as db:
                if db.execute('PRAGMA user_version').fetchone()[0] != CATALOG_VERSION:
                    raise EvaluationError('Unsupported catalog version; preserve it and use a compatible release.', 'catalog_version')
                settings = {r['key']: strict_json(r['value']) for r in db.execute('SELECT * FROM settings')}
                if settings.get('retired'):
                    raise EvaluationError('Workspace was retired.', 'workspace_retired')
                self.instance_id = settings['instance_id']; self.config = WorkspaceConfig.from_dict(settings['config'])
        except sqlite3.DatabaseError as exc:
            raise EvaluationError('Catalog is corrupt; restore explicitly. It was not rebuilt.', 'catalog_corrupt') from exc

    @contextmanager
    def operation(self, *, exclusive_objects=False):
        with self._guard, file_lock(self.operation_path), file_lock(self.objects_lock, exclusive_objects):
            self._validate()
            yield

    def _fault(self, boundary):
        """Test-only injection point; no environment-driven production fault behavior."""

    def _object_path(self, identifier):
        return self.root / 'objects' / (_safe_name(identifier) + '.jsonl')

    def reserve(self, additional=0):
        total = 0
        for base, dirs, files in os.walk(self.root, followlinks=False):
            if any((Path(base) / d).is_symlink() for d in dirs):
                raise EvaluationError('Unexpected symbolic link in workspace.', 'unsafe_workspace')
            for filename in files:
                path = Path(base) / filename
                info = path.lstat()
                if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                    raise EvaluationError('Unexpected nonregular workspace content.', 'unsafe_workspace')
                total += max(info.st_size, getattr(info, 'st_blocks', 0) * 512)
        if total + additional > self.config.max_bytes:
            raise EvaluationError('Persistent storage quota would be exceeded.', 'history_quota')
        if shutil.disk_usage(self.root).free < self.config.free_disk_bytes + additional:
            raise EvaluationError('Persistent storage reserve unavailable.', 'disk_exhausted')
        return total

    def status(self):
        with closing(self._connect()) as db:
            sequence = json.loads(db.execute("SELECT value FROM settings WHERE key='sequence'").fetchone()[0])
            counts = {kind: n for kind, n in db.execute("SELECT f.kind,count(*) FROM facts f JOIN operations p ON p.id=f.operation_id JOIN objects o ON o.id=f.object_id WHERE p.state='committed' AND o.state='active' GROUP BY f.kind")}
            return {'instance_id': self.instance_id, 'catalog_sequence': sequence, 'config': self.config.to_dict(),
                    'facts': counts, 'bytes': self.reserve(), 'journal_mode': db.execute('PRAGMA journal_mode').fetchone()[0],
                    'sqlite_version': sqlite3.sqlite_version, 'automatic_eviction': False}

    def set_saving(self, enabled):
        if not isinstance(enabled, bool):
            raise EvaluationError('saving must be boolean.')
        with self.operation(), closing(self._connect()) as db:
            values = self.config.to_dict(); values['saving'] = enabled
            db.execute("UPDATE settings SET value=? WHERE key='config'", (json.dumps(values),))
            self.config = WorkspaceConfig.from_dict(values)
        return self.status()

    def receipt(self, request_id, request_digest):
        with closing(self._connect()) as db:
            row = db.execute('SELECT request_digest,state,receipt FROM operations WHERE request_id=?',(request_id,)).fetchone()
            if row is None:return None
            if row['request_digest'] != request_digest:raise EvaluationError('Request ID already has different content.','idempotency_conflict')
            if row['state'] != 'committed':raise EvaluationError('Recover the unfinished operation before retry.','operation_incomplete')
            return strict_json(row['receipt'])

    def begin(self, request_id, request_digest, *, require_saving=True):
        if require_saving and not self.config.saving:
            raise EvaluationError('Historical saving is off; enable it explicitly.', 'persistence_disabled')
        with closing(self._connect()) as db:
            previous = db.execute('SELECT * FROM operations WHERE request_id=?', (request_id,)).fetchone()
            if previous:
                if previous['request_digest'] != request_digest:
                    raise EvaluationError('Request ID already has different content.', 'idempotency_conflict')
                if previous['state'] == 'committed':
                    return None, strict_json(previous['receipt'])
                raise EvaluationError('Recover the unfinished operation before retry.', 'operation_incomplete')
            identifier = uuid.uuid4().hex
            db.execute('INSERT INTO operations(id,request_id,request_digest,state,created_at) VALUES (?,?,?,?,?)',
                       (identifier, request_id, request_digest, 'pending', now()))
        private_directory(self.root / 'staging' / identifier)
        return identifier, None

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

    def commit_capture(self, identifier, *, cancel=None, receipt_extra=None):
        stage = self.root / 'staging' / _safe_name(identifier)
        with private_file(stage / 'capture.json', 'rb') as stream:
            raw = stream.read(64 * 1024**2 + 1)
        if len(raw) > 64 * 1024**2:
            raise EvaluationError('Capture manifest exceeds admission.', 'manifest_limit')
        manifest = strict_json(raw); expected = manifest.pop('content_digest', None)
        if expected != digest(manifest) or manifest.get('operation_id') != identifier:
            raise EvaluationError('Capture identity differs.', 'capture_changed')
        HistoricalEvidenceManifest.from_dict(manifest)
        objects = {v['id']: v for v in manifest['objects']}
        new = duplicates = 0; used = set()
        with closing(self._connect()) as db:
            # Preparatory rows remain hidden through operations.state.
            db.execute('BEGIN IMMEDIATE')
            try:
                for obj in objects.values():
                    _safe_name(obj['id'])
                    sha, size = file_digest(stage / (obj['id'] + '.jsonl'))
                    if sha != obj['sha256'] or size != obj['bytes']:
                        raise EvaluationError('Staged evidence identity differs.', 'capture_changed')
                    db.execute('INSERT INTO objects VALUES (?,?,?,?,?,?,?)', (obj['id'], identifier, sha, size, obj['kind'], obj['records'], 'pending'))
                cached = {}
                with private_file(stage / 'index.jsonl', 'rb') as stream:
                    for raw in stream:
                        if len(raw) > 16384:
                            raise EvaluationError('Invalid capture index.', 'capture_changed')
                        if (new+duplicates)%4096==0:
                            if cancel is not None and cancel.is_set():raise EvaluationError('Cancelled before historical publication.','cancelled')
                            self.reserve()
                        entry = strict_json(raw)
                        obj = objects.get(entry['object_id'])
                        if obj is None or entry['offset'] < 0 or entry['length'] <= 0 or entry['offset'] + entry['length'] > obj['bytes']:
                            raise EvaluationError('Invalid evidence location.', 'capture_changed')
                        oid = entry['object_id']
                        if oid not in cached:
                            if len(cached) >= 16: cached.pop(next(iter(cached))).close()
                            cached[oid] = private_file(stage / (oid + '.jsonl'), 'rb')
                        content = cached[oid]
                        content.seek(entry['offset']); fact = strict_json(content.read(entry['length']))
                        claimed = fact.pop('fact_digest', None)
                        if (claimed != entry['fact_digest'] or digest(fact) != claimed or digest(fact['identity']) != entry['key']
                                or fact['kind'] != entry['kind'] or fact['revision'] != entry['revision']):
                            raise EvaluationError('Record and directory identities differ.', 'capture_changed')
                        same = db.execute('SELECT fact_digest FROM facts WHERE kind=? AND key=? AND revision=?', (entry['kind'], entry['key'], entry['revision'])).fetchone()
                        prior_exists = db.execute('SELECT 1 FROM facts WHERE kind=? AND key=? LIMIT 1', (entry['kind'], entry['key'])).fetchone()
                        is_correction = fact.get('predecessor') is not None or prior_exists and same is None
                        if entry['kind'] in {'prediction', 'context', 'opportunity'} and is_correction:
                            parent = db.execute('SELECT * FROM facts WHERE kind=? AND key=? AND fact_digest=?',
                                                (entry['kind'], entry['key'], fact['predecessor'])).fetchone()
                            if parent is None or not fact.get('reason') or fact.get('available_ns') is None:
                                raise EvaluationError('Correction requires a matching predecessor, reason and availability.', 'correction_predecessor')
                            if fact.get('available_ns') is not None:
                                with private_file(stage/(parent['object_id']+'.jsonl') if parent['operation_id']==identifier else self._object_path(parent['object_id']),'rb') as parent_stream:
                                    parent_stream.seek(parent['offset']);parent_record=strict_json(parent_stream.read(parent['length']))
                                if parent_record.get('available_ns') is not None and int(fact['available_ns'])<int(parent_record['available_ns']):raise EvaluationError('Correction availability precedes its predecessor.','correction_chronology')
                            if entry['kind'] == 'prediction':
                                parent_path = stage/(parent['object_id']+'.jsonl') if parent['operation_id'] == identifier else self._object_path(parent['object_id'])
                                with private_file(parent_path, 'rb') as parent_stream:
                                    parent_stream.seek(parent['offset']); parent_fact = strict_json(parent_stream.read(parent['length']))
                                before = parent_fact['payload']; after = fact['payload']
                                if before['role'] != after['role'] or before['normalized'].get('entity_key') != after['normalized'].get('entity_key'):
                                    raise EvaluationError('Corrections cannot relabel historical role/entity separation.', 'historical_role_reassignment')
                                if parent_fact['authority'] != fact['authority']:
                                    raise EvaluationError('Prediction correction authority differs.', 'correction_authority')
                            # A cycle cannot be introduced: the predecessor must
                            # already exist and a revision ID is immutable.
                            forks = db.execute('SELECT revision FROM facts WHERE kind=? AND key=?', (entry['kind'], entry['key'])).fetchall()
                            if entry['revision'] in {r[0] for r in forks} and not db.execute('SELECT 1 FROM facts WHERE kind=? AND key=? AND revision=? AND fact_digest=?', (entry['kind'], entry['key'], entry['revision'], claimed)).fetchone():
                                raise EvaluationError('Correction revision conflicts.', 'historical_identity_conflict')
                        previous = db.execute('SELECT f.*,p.state FROM facts f JOIN operations p ON p.id=f.operation_id WHERE f.kind=? AND f.key=? AND f.revision=?',
                                              (entry['kind'], entry['key'], entry['revision'])).fetchone()
                        if previous:
                            if previous['fact_digest'] != entry['fact_digest']:
                                raise EvaluationError('Same fact identity/revision has different content.', 'historical_identity_conflict')
                            state = db.execute('SELECT state FROM objects WHERE id=?',(previous['object_id'],)).fetchone()[0]
                            if state != 'active' and previous['operation_id'] != identifier:
                                raise EvaluationError('Previously retained fact was purged or is unavailable; restore a verified backup into a new workspace.','historical_evidence_unavailable')
                            prior_id=previous['object_id'];cache_key='prior:'+prior_id
                            if cache_key not in cached:
                                if len(cached)>=16:cached.pop(next(iter(cached))).close()
                                prior_path=stage/(prior_id+'.jsonl') if previous['operation_id']==identifier else self._object_path(prior_id)
                                cached[cache_key]=private_file(prior_path,'rb')
                            prior_stream=cached[cache_key];prior_stream.seek(previous['offset'])
                            prior_record=strict_json(prior_stream.read(previous['length']));prior_digest=prior_record.pop('fact_digest',None)
                            if prior_digest!=claimed or digest(prior_record)!=claimed or prior_record!=fact:
                                raise EvaluationError('Indexed duplicate differs from retained canonical identity/payload.','historical_identity_conflict')
                            fact_id = previous['id']; duplicates += 1
                        else:
                            cursor = db.execute('INSERT INTO facts(kind,key,revision,fact_digest,object_id,offset,length,operation_id) VALUES (?,?,?,?,?,?,?,?)',
                                                tuple(entry[k] for k in ('kind', 'key', 'revision', 'fact_digest', 'object_id', 'offset', 'length')) + (identifier,))
                            fact_id = cursor.lastrowid; used.add(entry['object_id']); new += 1
                        db.execute('INSERT OR IGNORE INTO occurrences VALUES (?,?)', (identifier, fact_id))
                for stream in cached.values(): stream.close()
                db.commit()
            except BaseException:
                for stream in locals().get('cached', {}).values(): stream.close()
                db.rollback(); raise
            for oid in used:
                src = stage / (oid + '.jsonl'); dest = self._object_path(oid)
                os.link(src, dest); src.unlink()
            fsync_directory(self.root / 'objects'); self._fault('objects_published')
            self.reserve()
            if cancel is not None and cancel.is_set():
                raise EvaluationError('Cancelled before historical commit.', 'cancelled')
            metadata = manifest['metadata']
            db.execute('BEGIN IMMEDIATE')
            try:
                sequence = int(json.loads(db.execute("SELECT value FROM settings WHERE key='sequence'").fetchone()[0])) + 1
                for vid, value in metadata.get('variants', {}).items():
                    previous = db.execute('SELECT metadata FROM variants WHERE id=?', (vid,)).fetchone()
                    for existing in db.execute('SELECT metadata FROM variants').fetchall():
                        old_model = strict_json(existing[0])['signature']['model']; new_model = value['signature']['model']
                        predictor_fields = ('id', 'version', 'artifact_sha256', 'preprocessing')
                        if (old_model['id'], old_model['version']) == (new_model['id'], new_model['version']) and any(old_model.get(k) != new_model.get(k) for k in predictor_fields):
                            raise EvaluationError('Existing predictor version cannot change artifact or preprocessing identity.', 'model_version_conflict')
                    if previous:
                        old = strict_json(previous[0])
                        immutable = ('signature', 'task', 'namespace', 'outcome_definition_version', 'normalized_columns')
                        if any(old.get(k) != value.get(k) for k in immutable):
                            raise EvaluationError('Variant mathematics or normalized representation conflicts.', 'variant_conflict')
                        features = {**old.get('features', {}), **value.get('features', {})}
                        if any(k in old.get('features', {}) and old['features'][k] != v for k,v in value.get('features', {}).items()):
                            raise EvaluationError('Retained feature semantics changed.', 'feature_semantics_conflict')
                        old['features'] = features
                        db.execute('UPDATE variants SET metadata=? WHERE id=?', (serialized(old).decode(), vid))
                    if not previous:
                        db.execute('INSERT INTO variants VALUES (?,?,?)', (vid, serialized(value).decode(), identifier))
                if metadata.get('assessment_id'):
                    aid = metadata['assessment_id']
                    fact = db.execute("SELECT object_id FROM facts WHERE kind='assessment' AND key=?", (digest([aid]),)).fetchone()
                    db.execute('INSERT INTO assessments VALUES (?,?,?,?,?,?)', (aid, fact[0], identifier, expected, None, 'active'))
                receipt = {'operation_id': identifier, 'catalog_sequence': sequence, 'new_facts': new, 'duplicate_occurrences': duplicates,
                           'capture_digest': expected, **(receipt_extra or {})}
                catalog_metadata = {key: metadata[key] for key in ('assessment_id', 'capture_stages') if key in metadata}
                catalog_metadata['variant_ids'] = list(metadata.get('variants', {}))
                db.execute("UPDATE operations SET state='committed',sequence=?,receipt=?,metadata=? WHERE id=?", (sequence, serialized(receipt).decode(), serialized(catalog_metadata).decode(), identifier))
                db.execute("UPDATE objects SET state='active' WHERE operation_id=?", (identifier,))
                for oid in set(objects) - used:
                    db.execute('DELETE FROM objects WHERE id=?', (oid,))
                db.execute("UPDATE settings SET value=? WHERE key='sequence'", (json.dumps(sequence),))
                self._fault('before_catalog_commit'); db.commit()
            except BaseException:
                db.rollback(); raise
        self._fault('catalog_committed')
        shutil.rmtree(stage); fsync_directory(self.root / 'staging')
        return receipt

    def recover(self):
        with self.operation(exclusive_objects=True), closing(self._connect()) as db:
            pending = [r[0] for r in db.execute("SELECT id FROM operations WHERE state='pending'")]
            for identifier in pending:
                objects = [r[0] for r in db.execute('SELECT id FROM objects WHERE operation_id=?', (identifier,))]
                db.execute('BEGIN IMMEDIATE')
                db.execute('DELETE FROM occurrences WHERE operation_id=?', (identifier,))
                db.execute('DELETE FROM facts WHERE operation_id=?', (identifier,))
                db.execute('DELETE FROM objects WHERE operation_id=?', (identifier,))
                db.execute('DELETE FROM operations WHERE id=?', (identifier,)); db.commit()
                for oid in objects:
                    path = self._object_path(oid)
                    if path.exists():
                        with private_file(path, 'rb'): pass
                        path.unlink()
                directory = self.root / 'staging' / identifier
                if directory.exists(): self._remove_owned_stage(directory)
            known = {r[0] for r in db.execute('SELECT id FROM objects')}
            for path in (self.root / 'objects').iterdir():
                if path.suffix != '.jsonl' or not HEX.fullmatch(path.stem):
                    raise EvaluationError('Unrecognized workspace object; left untouched.', 'unsafe_workspace')
                if path.stem not in known:
                    with private_file(path, 'rb'): pass
                    path.unlink()
            for directory in (self.root / 'staging').iterdir():
                if HEX.fullmatch(directory.name): self._remove_owned_stage(directory)
            unavailable = []
            for row in db.execute("SELECT * FROM objects WHERE state='active'").fetchall():
                try: self._verify_object(row['id'], row['sha256'], row['bytes'])
                except (OSError, EvaluationError):
                    db.execute("UPDATE objects SET state='unavailable' WHERE id=?", (row['id'],)); unavailable.append(row['id'])
            for row in db.execute("SELECT * FROM deletions WHERE state='pending'").fetchall():
                self._finish_deletion(db, strict_json(row['plan']))
        return {'pending_operations_removed': len(pending), 'unavailable_objects': unavailable}

    def _remove_owned_stage(self, directory):
        if directory.is_symlink() or not directory.is_dir():
            raise EvaluationError('Unsafe staging directory.', 'unsafe_workspace')
        for path in directory.iterdir():
            with private_file(path, 'rb'): pass
            path.unlink()
        directory.rmdir()

    def iter_facts(self, kind=None, *, sequence=None, keys=None, fact_digests=(), batch_ids=(), require_complete=True, max_records=30000000, check=None):
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
            sql = 'SELECT f.*,o.sha256,o.bytes,p.sequence FROM facts f JOIN objects o ON o.id=f.object_id JOIN operations p ON p.id=f.operation_id WHERE ' + ' AND '.join(where) + ' ORDER BY f.object_id,f.offset'
            count = 0; current = None; stream = None
            try:
                for row in db.execute(sql, args):
                    count += 1
                    if count > max_records:
                        raise EvaluationError('Historical scan record admission exceeded.', 'history_scan_limit')
                    if current != row['object_id']:
                        if stream: stream.close()
                        path = self._verify_object(row['object_id'], row['sha256'], row['bytes'])
                        stream = private_file(path, 'rb'); current = row['object_id']
                    stream.seek(row['offset']); raw = stream.read(row['length'])
                    if len(raw) != row['length'] or len(raw) > self.config.max_record_bytes:
                        raise EvaluationError('Invalid committed record location.', 'evidence_changed')
                    value = strict_json(raw); fd = value.pop('fact_digest', None)
                    if fd != row['fact_digest'] or fd != digest(value) or digest(value['identity']) != row['key']:
                        raise EvaluationError('Historical fact identity differs.', 'evidence_changed')
                    value['fact_digest'] = fd; value['recorded_sequence'] = row['sequence']
                    value['object_id'] = row['object_id']; value['offset'] = row['offset']; value['record_bytes'] = row['length']
                    if check and count % 512 == 0: check('historical evidence scan')
                    yield value
            finally:
                if stream: stream.close()

    def variants(self):
        with closing(self._connect()) as db:
            return {r['id']: strict_json(r['metadata']) for r in db.execute("SELECT v.* FROM variants v JOIN operations p ON p.id=v.operation_id WHERE p.state='committed'")}

    def add_assessment(self, result, *, request_id=None, cancel=None, request_digest=None):
        request_id = request_id or uuid.uuid4().hex
        identifier, previous = self.begin(request_id, request_digest or digest(result.to_private_dict()), require_saving=False)
        if previous: return previous
        writer = EvidenceWriter(self.root / 'staging' / identifier, self.config, identifier)
        aid = result.data['analysis_id']
        writer.add('assessment', [aid], {'result': result.to_private_dict(), 'manifest': result.private})
        writer.finish({'assessment_id': aid})
        receipt = self.commit_capture(identifier, cancel=cancel, receipt_extra={'assessment_id': aid})
        return receipt

    def assessment(self, aid):
        # Fact receipt is authoritative even after a crash before the optional list index.
        values = list(self.iter_facts('assessment', keys=[digest([aid])], max_records=1))
        if not values: raise EvaluationError('Assessment is unavailable.', 'assessment_unavailable')
        packet = values[0]['payload']
        from .history_result import LongitudinalResult
        if packet['result'].get('schema_version') == 'confidenceguard.longitudinal_result/1.0':
            result = LongitudinalResult.from_dict(packet['result'], private=packet['manifest'])
            result._workspace_location = str(self.root)
            return result
        from .result import EvaluationResult
        return EvaluationResult.from_dict(packet['result'], private=packet['manifest'])

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
            if evidence_objects:
                expanded = True
                while expanded:
                    before = len(objects)
                    for oid in tuple(objects):
                        if db.execute('SELECT kind FROM objects WHERE id=?',(oid,)).fetchone()[0] == 'assessment':continue
                        affected.update(r[0] for r in db.execute('SELECT DISTINCT operation_id FROM occurrences WHERE fact_id IN (SELECT id FROM facts WHERE object_id=?)',(oid,)))
                    for operation in affected:
                        objects.update(r[0] for r in db.execute('SELECT id FROM objects WHERE operation_id=?',(operation,)))
                    expanded = len(objects) != before
            impacted = [r[0] for r in db.execute('SELECT id FROM assessments')] if evidence_objects else []
            plan = {'id': uuid.uuid4().hex, 'instance_id': self.instance_id, 'catalog_sequence': status['catalog_sequence'],
                    'object_ids': sorted(objects), 'assessment_ids': list(assessment_ids), 'batch_ids': list(batch_ids),
                    'affected_batches': sorted(affected), 'potentially_impacted_assessments': impacted, 'purge': bool(purge), 'retained_assessments_may_contain_values': True}
            plan['confirmation'] = digest(plan)
            return plan

    def delete(self, plan):
        supplied = dict(plan); confirmation = supplied.pop('confirmation', None)
        if confirmation != digest(supplied) or plan.get('instance_id') != self.instance_id:
            raise EvaluationError('Deletion preview differs.', 'stale_deletion')
        with self.operation(exclusive_objects=True), closing(self._connect()) as db:
            if self.status()['catalog_sequence'] != plan['catalog_sequence']:
                raise EvaluationError('Catalog changed; inspect a new deletion preview.', 'stale_deletion')
            current=self.deletion_preview(object_ids=plan['object_ids'],assessment_ids=plan['assessment_ids'],batch_ids=plan['batch_ids'],purge=plan['purge'])
            for field in ('object_ids','affected_batches','potentially_impacted_assessments'):
                if current[field]!=plan.get(field):raise EvaluationError('Deletion dependencies differ; inspect a new preview.','stale_deletion')
            db.execute('BEGIN IMMEDIATE')
            db.execute('INSERT INTO deletions VALUES (?,?,?)', (plan['id'], serialized(plan).decode(), 'pending'))
            for oid in plan['object_ids']:
                db.execute("UPDATE objects SET state='deleted' WHERE id=?", (oid,))
            for bid in plan['batch_ids']:
                db.execute('DELETE FROM occurrences WHERE operation_id=?', (bid,))
            db.execute("UPDATE settings SET value=? WHERE key='sequence'", (json.dumps(plan['catalog_sequence'] + 1),)); db.commit()
            self._fault('deletion_tombstoned')
            self._finish_deletion(db, plan)
        if plan['purge']:
            self._retire_files()
        return {'deleted_objects': len(plan['object_ids']), 'workspace_retired': plan['purge']}

    def _finish_deletion(self, db, plan):
        for oid in plan['object_ids']:
            path = self._object_path(oid)
            if path.exists():
                with private_file(path, 'rb'): pass
                path.unlink()
            self._verified.pop(oid, None)
        if plan['purge']:
            db.execute("UPDATE settings SET value='true' WHERE key='retired'")
        db.execute("UPDATE deletions SET state='completed' WHERE id=?", (plan['id'],))
        fsync_directory(self.root / 'objects')

    def backup(self, destination):
        destination = Path(destination).absolute()
        if destination == self.root or self.root in destination.parents or destination in self.root.parents or destination.exists():
            raise EvaluationError('Choose a new backup destination outside the workspace.', 'backup_destination')
        with self.operation(), closing(self._connect()) as source:
            private_directory(destination); inventory = {}
            db_path = destination / 'catalog.sqlite3'
            fd = os.open(db_path, os.O_CREAT | os.O_EXCL | os.O_RDWR, 0o600); os.close(fd)
            with closing(sqlite3.connect(db_path)) as target:
                source.backup(target)
                target.execute('PRAGMA journal_mode=DELETE'); target.commit()
            inventory['catalog.sqlite3'] = file_digest(db_path)
            private_directory(destination / 'objects')
            for row in source.execute("SELECT * FROM objects WHERE state='active'"):
                path = self._verify_object(row['id'], row['sha256'], row['bytes'])
                dest = destination / 'objects' / path.name
                with private_file(path, 'rb') as inp, private_file(dest) as out:
                    shutil.copyfileobj(inp, out, 1024**2); out.flush(); os.fsync(out.fileno())
                inventory['objects/' + path.name] = file_digest(dest)
            manifest = {'schema_version': 'confidenceguard.workspace_backup/1.0', 'instance_id': self.instance_id,
                        'catalog_sequence': self.status()['catalog_sequence'], 'files': inventory}
            manifest['content_digest'] = digest(manifest)
            with private_file(destination / 'backup.json') as out:
                out.write(serialized(manifest)); out.flush(); os.fsync(out.fileno())
            fsync_directory(destination / 'objects'); fsync_directory(destination)
            return manifest

    @classmethod
    def restore(cls, backup, destination):
        backup = Path(backup).absolute(); destination = Path(destination).absolute()
        if destination.exists() or destination == backup or backup in destination.parents:
            raise EvaluationError('Restore requires a new destination.', 'restore_destination')
        with private_file(backup / 'backup.json', 'rb') as stream:
            manifest = strict_json(stream.read(64 * 1024**2 + 1))
        expected = manifest.pop('content_digest', None)
        if expected != digest(manifest) or manifest.get('schema_version') != 'confidenceguard.workspace_backup/1.0':
            raise EvaluationError('Backup is incomplete or changed.', 'backup_changed')
        for relative, expected in manifest['files'].items():
            path = Path(relative)
            if path.is_absolute() or '..' in path.parts or str(path) not in {'catalog.sqlite3'} and not (len(path.parts) == 2 and path.parts[0] == 'objects' and HEX.fullmatch(path.stem) and path.suffix == '.jsonl'):
                raise EvaluationError('Unsafe backup inventory.', 'backup_changed')
            if list(file_digest(backup / relative)) != list(expected):
                raise EvaluationError('Backup bytes differ.', 'backup_changed')
        private_directory(destination)
        try:
            for relative in manifest['files']:
                target = destination / relative; private_directory(target.parent)
                with private_file(backup / relative, 'rb') as inp, private_file(target) as out:
                    shutil.copyfileobj(inp, out, 1024**2); out.flush(); os.fsync(out.fileno())
            private_directory(destination / 'objects'); private_directory(destination / 'staging')
            loaded = cls(destination)
            with closing(loaded._connect()) as db:
                db.execute("UPDATE settings SET value=? WHERE key='instance_id'", (json.dumps(uuid.uuid4().hex),))
            loaded._validate(); loaded.recover(); fsync_directory(destination)
            return loaded
        except BaseException:
            # Preserve failed restore for diagnosis; it is never attached implicitly.
            raise
