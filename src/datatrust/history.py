"""Local-first analysis history for the DataTrust app.

Only canonical artifacts are kept: analysis JSON, report HTML, and a PDF generated during the live session
or later from the saved, verified HTML. Datasets, source snapshots, private manifests, excerpts and local paths are never stored.
Canonical artifacts can still contain values from the data (names, top values, distributions, quoted
rows), which is why saving starts only after an informed first-use choice.

Layout under the history root (0o700 directories, 0o600 files):
  entries/<id>/   owner marker, manifest.json (the source of truth) and the artifacts
  staging/<id>/   a record being written; renamed into entries/ atomically once verified
  history.sqlite3 the index, rebuildable from the manifests
"""
from contextlib import closing
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import sqlite3
import sys
import threading
import time
import uuid

import psutil

SCHEMA = 1
DEFAULT_MAX_AGE_DAYS = 90
DEFAULT_MAX_TOTAL_BYTES = 2 * 1024 ** 3
ARTIFACT_NAMES = {'json': 'analysis.json', 'html': 'report.html', 'pdf': 'report.pdf'}
STAGING_STALE_SECONDS = 600
PDF_LOCK = '.pdf-lock'
PDF_LOCK_STALE_SECONDS = 900  # A conversion lock older than this, or whose process is gone, was abandoned.


class HistoryError(Exception):
    """A history operation was refused; nothing partial was left behind."""


def default_history_dir() -> Path:
    home = Path.home()
    if sys.platform == 'darwin':
        return home / 'Library' / 'Application Support' / 'NUMEK' / 'DataTrust' / 'history'
    if os.name == 'nt':
        return Path(os.environ.get('LOCALAPPDATA') or home / 'AppData' / 'Local') / 'NUMEK' / 'DataTrust' / 'history'
    return Path(os.environ.get('XDG_DATA_HOME') or home / '.local' / 'share') / 'numek' / 'datatrust' / 'history'


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def _digest(path: Path) -> tuple[str, int]:
    h, size = hashlib.sha256(), 0
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block); size += len(block)
    return h.hexdigest(), size


def _fsync_dir(path: Path) -> None:
    if os.name == 'nt':
        return
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _private_dir(path: Path) -> Path:
    if path.is_symlink():
        raise HistoryError(f'{path.name} is a symbolic link; history directories must be real directories.')
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(path, 0o700)
    return path


def _write_private(path: Path, data: bytes) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'wb') as f:
        f.write(data); f.flush(); os.fsync(f.fileno())


def _copy_verified(source: Path, dest: Path, expected_sha256: str) -> dict:
    """Copy into a new private file, hash the copy, and require it to equal the verified original."""
    h, size = hashlib.sha256(), 0
    fd = os.open(dest, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with open(source, 'rb') as src, os.fdopen(fd, 'wb') as out:
        for block in iter(lambda: src.read(1 << 20), b''):
            out.write(block); h.update(block); size += len(block)
        out.flush(); os.fsync(out.fileno())
    if h.hexdigest() != expected_sha256 or _digest(dest)[0] != expected_sha256:
        raise HistoryError('An artifact changed while it was being saved; nothing was recorded.')
    return {'sha256': expected_sha256, 'bytes': size}


class History:
    def __init__(self, root):
        self.root = _private_dir(Path(root).expanduser()).resolve()
        self.entries = _private_dir(self.root / 'entries')
        self.staging = _private_dir(self.root / 'staging')
        self.db_path = self.root / 'history.sqlite3'
        self.process = uuid.uuid4().hex
        self.lock = threading.RLock()
        self._open_index()
        self.recover()
        self.apply_retention()

    # ——— Index ———
    def _db(self):
        db = sqlite3.connect(self.db_path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA busy_timeout = 10000')
        return db

    def _open_index(self):
        try:
            with closing(self._db()) as db, db:
                self._migrate(db)
        except sqlite3.DatabaseError:
            # A corrupt index is set aside and rebuilt from the manifests during recovery.
            self.db_path.rename(self.root / f'history.sqlite3.corrupt-{int(time.time())}')
            with closing(self._db()) as db, db:
                self._migrate(db)
        os.chmod(self.db_path, 0o600)

    def _migrate(self, db):
        if db.execute('PRAGMA user_version').fetchone()[0] >= SCHEMA:
            return
        db.executescript('''
            CREATE TABLE IF NOT EXISTS entries (
                id TEXT PRIMARY KEY, created_at TEXT NOT NULL, workflow TEXT NOT NULL, mode TEXT NOT NULL,
                dataset_name TEXT, source_filename TEXT, source_sha256 TEXT, methodology_id TEXT, schema_version TEXT,
                generated_at TEXT, score REAL, risk_level TEXT, summary_json TEXT NOT NULL, search_text TEXT NOT NULL,
                analysis_sha256 TEXT NOT NULL, owner TEXT NOT NULL, artifacts_json TEXT NOT NULL,
                total_bytes INTEGER NOT NULL, state TEXT NOT NULL DEFAULT 'ok', UNIQUE (workflow, analysis_sha256));
            CREATE TABLE IF NOT EXISTS pending (
                id TEXT PRIMARY KEY, workflow TEXT NOT NULL, display_name TEXT, started_at TEXT NOT NULL,
                process TEXT NOT NULL, pid INTEGER NOT NULL, state TEXT NOT NULL DEFAULT 'running');
            CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);
        ''')
        db.execute(f'PRAGMA user_version = {SCHEMA}')

    # ——— Settings: the first-use choice and retention ———
    def settings(self) -> dict:
        with closing(self._db()) as db:
            raw = {r['key']: r['value'] for r in db.execute('SELECT key, value FROM settings')}
        age, size = raw.get('max_age_days', str(DEFAULT_MAX_AGE_DAYS)), raw.get('max_total_bytes', str(DEFAULT_MAX_TOTAL_BYTES))
        return {'saving': raw.get('saving', 'unset'), 'max_age_days': int(age) if age else None, 'max_total_bytes': int(size) if size else None}

    def set_settings(self, *, saving=None, max_age_days=..., max_total_bytes=...):
        values = {}
        if saving is not None:
            if saving not in {'on', 'off'}:
                raise HistoryError('Choose whether to save completed analyses.')
            values['saving'] = saving
        for key, value in (('max_age_days', max_age_days), ('max_total_bytes', max_total_bytes)):
            if value is ...:
                continue
            if value is not None and (isinstance(value, bool) or not isinstance(value, int) or value < 1):
                raise HistoryError('Retention limits must be positive whole numbers, or none.')
            values[key] = '' if value is None else str(value)
        with self.lock, closing(self._db()) as db, db:
            for key, value in values.items():
                db.execute('INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value', (key, value))
        self.apply_retention()
        return self.settings()

    @property
    def saving(self) -> bool:
        return self.settings()['saving'] == 'on'

    # ——— Intent journal ———
    def begin(self, workflow: str, display_name: str) -> str:
        pid = uuid.uuid4().hex
        with self.lock, closing(self._db()) as db, db:
            db.execute('INSERT INTO pending (id, workflow, display_name, started_at, process, pid) VALUES (?, ?, ?, ?, ?, ?)',
                       (pid, workflow, display_name, _now(), self.process, os.getpid()))
        return pid

    def end(self, pending_id: str) -> None:
        with self.lock, closing(self._db()) as db, db:
            db.execute('DELETE FROM pending WHERE id = ?', (pending_id,))

    def interrupted(self) -> list[dict]:
        with closing(self._db()) as db:
            return [dict(r) for r in db.execute("SELECT id, workflow, display_name, started_at FROM pending WHERE state = 'interrupted' ORDER BY started_at DESC")]

    def dismiss(self, pending_id: str) -> None:
        with self.lock, closing(self._db()) as db, db:
            db.execute("DELETE FROM pending WHERE id = ? AND state = 'interrupted'", (pending_id,))

    # ——— Recording ———
    def record(self, *, workflow: str, mode: str, artifacts: dict, meta: dict, pending_id: str | None = None) -> str:
        """Copy verified canonical artifacts ({kind: (path, sha256)}) into a new entry, atomically."""
        if 'json' not in artifacts or set(artifacts) - set(ARTIFACT_NAMES):
            raise HistoryError('Only canonical analysis JSON, report HTML and PDF artifacts can be saved.')
        analysis_sha = artifacts['json'][1]
        with self.lock:
            with closing(self._db()) as db:
                row = db.execute('SELECT id FROM entries WHERE workflow = ? AND analysis_sha256 = ?', (workflow, analysis_sha)).fetchone()
            if row:
                for kind, (path, sha) in artifacts.items():
                    self.attach(row['id'], kind, path, sha)
                if pending_id:
                    self.end(pending_id)
                return row['id']
            eid, owner = uuid.uuid4().hex, secrets.token_hex(16)
            stage = self.staging / eid
            try:
                _private_dir(stage)
                _write_private(stage / 'owner', owner.encode())
                files = []
                for kind in ('json', 'html', 'pdf'):
                    if kind in artifacts:
                        path, sha = artifacts[kind]
                        files.append({'kind': kind, 'name': ARTIFACT_NAMES[kind], **_copy_verified(Path(path), stage / ARTIFACT_NAMES[kind], sha)})
                manifest = {'history_schema': SCHEMA, 'id': eid, 'owner': owner, 'created_at': _now(), 'workflow': workflow, 'mode': mode, **meta, 'artifacts': files}
                _write_private(stage / 'manifest.json', json.dumps(manifest, sort_keys=True, indent=2).encode())
                _fsync_dir(stage)
                os.rename(stage, self.entries / eid)
                _fsync_dir(self.entries)
            except Exception:
                if stage.is_dir() and not stage.is_symlink():
                    shutil.rmtree(stage, ignore_errors=True)
                raise
            with closing(self._db()) as db, db:
                self._index(db, manifest)
                if pending_id:
                    db.execute('DELETE FROM pending WHERE id = ?', (pending_id,))
        self.apply_retention()
        return eid

    def attach(self, eid: str, kind: str, path, sha256: str, html_sha256: str | None = None) -> None:
        """Add an artifact generated later in the live session (a PDF). Existing files are never replaced.
        html_sha256 binds a PDF to the canonical HTML it was rendered from; it is recorded only when it is the
        saved HTML's digest."""
        with self.lock:
            entry = self._entry_dir(eid)
            manifest = self._manifest(entry)
            if any(a['kind'] == kind for a in manifest['artifacts']):
                return
            temp = entry / f'.{ARTIFACT_NAMES[kind]}.{uuid.uuid4().hex}'
            try:
                info = _copy_verified(Path(path), temp, sha256)
                os.rename(temp, entry / ARTIFACT_NAMES[kind])
            finally:
                temp.unlink(missing_ok=True)
            html = next((a['sha256'] for a in manifest['artifacts'] if a['kind'] == 'html'), None)
            bound = {'html_sha256': html_sha256} if kind == 'pdf' and html_sha256 and html_sha256 == html else {}
            manifest['artifacts'].append({'kind': kind, 'name': ARTIFACT_NAMES[kind], **info, **bound})
            self._write_manifest(eid, entry, manifest)

    def _write_manifest(self, eid: str, entry: Path, manifest: dict) -> None:
        staged = entry / f'.manifest.{uuid.uuid4().hex}'
        _write_private(staged, json.dumps(manifest, sort_keys=True, indent=2).encode())
        os.replace(staged, entry / 'manifest.json')
        _fsync_dir(entry)
        with closing(self._db()) as db, db:
            db.execute('UPDATE entries SET artifacts_json = ?, total_bytes = ? WHERE id = ?',
                       (json.dumps(manifest['artifacts']), sum(a['bytes'] for a in manifest['artifacts']), eid))

    # ——— Saved PDFs ———
    def generate_pdf(self, eid: str, converter) -> dict:
        """Render the saved canonical HTML to a PDF and attach it, bound to that HTML's digest. Needs no dataset.

        The HTML is verified first and again after conversion (the converter also refuses HTML that changes
        while it reads). One conversion per entry at a time, across processes, through an exclusive lock file;
        a lock whose process is gone, or that is older than PDF_LOCK_STALE_SECONDS, was abandoned and is
        replaced. If the entry is deleted or altered meanwhile, nothing is kept. Returns the entry view."""
        view = self.verify(eid)
        if view['state'] != 'ok':
            raise HistoryError('This saved analysis changed on disk or is missing; no PDF was generated.')
        entry = self._entry_dir(eid)
        manifest = self._manifest(entry)
        html = next((a for a in manifest['artifacts'] if a['kind'] == 'html'), None)
        if html is None:
            raise HistoryError('This saved analysis has no canonical HTML report to convert.')
        if any(a['kind'] == 'pdf' for a in manifest['artifacts']):
            return view
        token = self._lock_pdf(entry)
        work = self.staging / f'.pdf-{eid}-{uuid.uuid4().hex}.pdf'  # never inside the entry, so a deletion stays complete
        try:
            try:
                converter(entry / ARTIFACT_NAMES['html'], work, expected_html_sha256=html['sha256'])
            except OSError as exc:
                if not (entry / ARTIFACT_NAMES['html']).is_file():
                    raise HistoryError('This saved analysis was deleted while its PDF was generated; nothing was kept.') from exc
                raise
            with self.lock:
                try:
                    self._row(eid)
                    entry = self._entry_dir(eid)
                    current = self._manifest(entry)
                except (KeyError, OSError, ValueError) as exc:
                    raise HistoryError('This saved analysis was deleted while its PDF was generated; nothing was kept.') from exc
                saved = next((a for a in current['artifacts'] if a['kind'] == 'html'), None)
                if saved is None or saved['sha256'] != html['sha256'] or _digest(entry / ARTIFACT_NAMES['html'])[0] != html['sha256']:
                    raise HistoryError('The saved report changed while its PDF was generated; nothing was kept.')
                if not any(a['kind'] == 'pdf' for a in current['artifacts']):
                    sha, size = _digest(work)
                    os.chmod(work, 0o600)
                    os.rename(work, entry / ARTIFACT_NAMES['pdf'])
                    current['artifacts'].append({'kind': 'pdf', 'name': ARTIFACT_NAMES['pdf'], 'sha256': sha, 'bytes': size,
                                                 'html_sha256': html['sha256'], 'origin': 'saved_html'})
                    self._write_manifest(eid, entry, current)
        finally:
            work.unlink(missing_ok=True)
            self._unlock_pdf(entry, token)
        self.apply_retention()
        return self.verify(eid)

    def _lock_pdf(self, entry: Path) -> str:
        token = secrets.token_hex(16)
        record = json.dumps({'token': token, 'pid': os.getpid(), 'process': self.process, 'started': time.time()}).encode()
        lock = entry / PDF_LOCK
        for _ in range(2):
            try:
                _write_private(lock, record)
                return token
            except FileExistsError:
                if not self._pdf_lock_abandoned(lock):
                    raise HistoryError('A PDF of this saved analysis is already being generated. Try again shortly.')
                lock.unlink(missing_ok=True)
        raise HistoryError('A PDF of this saved analysis is already being generated. Try again shortly.')

    @staticmethod
    def _pdf_lock_abandoned(lock: Path) -> bool:
        try:
            held = json.loads(lock.read_text())
            started, pid = float(held['started']), int(held['pid'])
        except (OSError, ValueError, KeyError, TypeError):
            try:  # unreadable: judge by age alone
                return time.time() - lock.stat().st_mtime > PDF_LOCK_STALE_SECONDS
            except OSError:
                return True
        return time.time() - started > PDF_LOCK_STALE_SECONDS or not psutil.pid_exists(pid)

    @staticmethod
    def _unlock_pdf(entry: Path, token: str) -> None:
        lock = entry / PDF_LOCK
        try:
            if json.loads(lock.read_text()).get('token') == token:
                lock.unlink(missing_ok=True)
        except (OSError, ValueError):
            pass

    def _index(self, db, manifest: dict, state: str = 'ok') -> None:
        summary = manifest.get('summary', {})
        search = ' '.join(str(x) for x in [manifest.get('dataset_name'), manifest.get('source_filename'), manifest['workflow'], manifest['mode'],
                                            manifest.get('target'), manifest.get('risk_level'), *[f.get('title', '') for f in summary.get('findings', [])]] if x).lower()
        db.execute('''INSERT OR REPLACE INTO entries (id, created_at, workflow, mode, dataset_name, source_filename, source_sha256, methodology_id,
                      schema_version, generated_at, score, risk_level, summary_json, search_text, analysis_sha256, owner, artifacts_json, total_bytes, state)
                      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                   (manifest['id'], manifest['created_at'], manifest['workflow'], manifest['mode'], manifest.get('dataset_name'), manifest.get('source_filename'),
                    manifest.get('source_sha256'), manifest.get('methodology_id'), manifest.get('schema_version'), manifest.get('generated_at'),
                    manifest.get('score'), manifest.get('risk_level'), json.dumps(summary), search,
                    next(a['sha256'] for a in manifest['artifacts'] if a['kind'] == 'json'), manifest['owner'],
                    json.dumps(manifest['artifacts']), sum(a['bytes'] for a in manifest['artifacts']), state))

    # ——— Reading ———
    def _entry_dir(self, eid: str) -> Path:
        if not isinstance(eid, str) or len(eid) != 32 or any(c not in '0123456789abcdef' for c in eid):
            raise KeyError(eid)
        path = self.entries / eid
        if path.is_symlink() or not path.is_dir() or path.resolve().parent != self.entries.resolve():
            raise KeyError(eid)
        return path

    def _manifest(self, entry: Path) -> dict:
        return json.loads((entry / 'manifest.json').read_text())

    def _row(self, eid: str):
        with closing(self._db()) as db:
            row = db.execute('SELECT * FROM entries WHERE id = ?', (eid,)).fetchone()
        if row is None:
            raise KeyError(eid)
        return row

    @staticmethod
    def _view(row) -> dict:
        artifacts = json.loads(row['artifacts_json'])
        return {'id': row['id'], 'created_at': row['created_at'], 'workflow': row['workflow'], 'mode': row['mode'], 'dataset_name': row['dataset_name'],
                'source_filename': row['source_filename'], 'generated_at': row['generated_at'], 'score': row['score'], 'risk_level': row['risk_level'],
                'summary': json.loads(row['summary_json']), 'artifacts': [a['kind'] for a in artifacts], 'bytes': row['total_bytes'], 'state': row['state']}

    def _set_state(self, eid: str, state: str) -> None:
        with self.lock, closing(self._db()) as db, db:
            db.execute('UPDATE entries SET state = ? WHERE id = ?', (state, eid))

    def verify(self, eid: str) -> dict:
        """Check every artifact against the manifest before anything is shown or served."""
        row = self._row(eid)
        try:
            entry = self._entry_dir(eid)
        except KeyError:
            self._set_state(eid, 'missing')
            return {**self._view(self._row(eid))}
        ok = True
        try:
            manifest = self._manifest(entry)
            ok = manifest.get('owner') == row['owner'] and (entry / 'owner').read_text() == row['owner']
            for a in manifest['artifacts']:
                f = entry / a['name']
                ok = ok and not f.is_symlink() and f.is_file() and _digest(f) == (a['sha256'], a['bytes'])
        except (OSError, ValueError, KeyError):
            ok = False
        state = 'ok' if ok else 'altered'
        if state != row['state']:
            self._set_state(eid, state)
        # How the saved report was rendered, when this entry recorded it; older entries did not.
        return {**self._view(self._row(eid)), 'presentation': manifest.get('presentation') if ok else None}

    def file(self, eid: str, kind: str) -> Path:
        view = self.verify(eid)
        if view['state'] != 'ok':
            raise HistoryError('This saved analysis changed on disk or is missing; it was not opened.')
        if kind not in view['artifacts']:
            raise KeyError(kind)
        entry = self._entry_dir(eid)
        if kind == 'pdf':
            artifacts = {a['kind']: a for a in self._manifest(entry)['artifacts']}
            if artifacts['pdf'].get('html_sha256') not in (None, artifacts.get('html', {}).get('sha256')):
                raise HistoryError('This saved PDF was rendered from a different report; it was not opened.')
        return entry / ARTIFACT_NAMES[kind]

    def search(self, q='', workflow=None, risk=None, date_from=None, date_to=None, cursor=0, limit=50) -> dict:
        where, args = [], []
        if q:
            escaped = q.lower().replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
            where.append("search_text LIKE ? ESCAPE '\\'"); args.append(f'%{escaped}%')
        for column, value in (('workflow', workflow), ('risk_level', risk)):
            if value:
                where.append(f'{column} = ?'); args.append(value)
        if date_from:
            where.append('created_at >= ?'); args.append(date_from)
        if date_to:
            where.append('created_at < ?'); args.append(date_to)
        clause = f"WHERE {' AND '.join(where)}" if where else ''
        with closing(self._db()) as db:
            total = db.execute(f'SELECT COUNT(*) FROM entries {clause}', args).fetchone()[0]
            rows = db.execute(f'SELECT * FROM entries {clause} ORDER BY created_at DESC, id LIMIT ? OFFSET ?', [*args, limit, cursor]).fetchall()
        return {'items': [self._view(r) for r in rows], 'total': total, 'next_cursor': cursor + limit if cursor + limit < total else None}

    def usage(self) -> dict:
        with closing(self._db()) as db:
            count, size = db.execute('SELECT COUNT(*), COALESCE(SUM(total_bytes), 0) FROM entries').fetchone()
        return {'count': count, 'bytes': size}

    # ——— Deletion and retention ———
    def delete(self, eid: str) -> None:
        with self.lock:
            row = self._row(eid)
            path = self.entries / eid
            if path.exists() or path.is_symlink():
                if path.is_symlink() or not path.is_dir() or path.resolve().parent != self.entries.resolve():
                    raise HistoryError('That saved analysis is not a regular history folder; it was left untouched.')
                marker = path / 'owner'
                if marker.is_symlink() or not marker.is_file() or marker.read_text() != row['owner']:
                    raise HistoryError('That history folder is not owned by this index; it was left untouched.')
                shutil.rmtree(path)
            with closing(self._db()) as db, db:
                db.execute('DELETE FROM entries WHERE id = ?', (eid,))

    def clear(self) -> int:
        with closing(self._db()) as db:
            ids = [r['id'] for r in db.execute('SELECT id FROM entries')]
        for eid in ids:
            self.delete(eid)
        return len(ids)

    def apply_retention(self) -> list[str]:
        settings, removed = self.settings(), []
        with closing(self._db()) as db:
            rows = db.execute('SELECT id, created_at, total_bytes FROM entries ORDER BY created_at ASC, id').fetchall()
        if settings['max_age_days']:
            cutoff = (datetime.now(timezone.utc) - timedelta(days=settings['max_age_days'])).isoformat(timespec='seconds')
            removed += [r['id'] for r in rows if r['created_at'] < cutoff]
        if settings['max_total_bytes']:
            kept = [r for r in rows if r['id'] not in removed]
            total = sum(r['total_bytes'] for r in kept)
            for r in kept:
                if total <= settings['max_total_bytes']:
                    break
                removed.append(r['id']); total -= r['total_bytes']
        for eid in removed:
            try:
                self.delete(eid)
            except (HistoryError, KeyError):
                pass
        return removed

    # ——— Recovery ———
    def recover(self) -> dict:
        report = {'staging_removed': 0, 'reindexed': 0, 'missing': 0, 'interrupted': 0}
        with self.lock:
            for stage in self.staging.iterdir():
                if stage.is_dir() and not stage.is_symlink() and (stage / 'owner').is_file() and time.time() - stage.stat().st_mtime > STAGING_STALE_SECONDS:
                    shutil.rmtree(stage, ignore_errors=True); report['staging_removed'] += 1
            for entry in self.entries.iterdir():
                if entry.is_dir() and not entry.is_symlink() and (entry / PDF_LOCK).exists() and self._pdf_lock_abandoned(entry / PDF_LOCK):
                    (entry / PDF_LOCK).unlink(missing_ok=True)
            for leftover in self.staging.glob('.pdf-*'):  # conversions that never finished
                if leftover.is_file() and not leftover.is_symlink() and time.time() - leftover.stat().st_mtime > STAGING_STALE_SECONDS:
                    leftover.unlink(missing_ok=True)
            with closing(self._db()) as db:
                indexed = {r['id'] for r in db.execute('SELECT id FROM entries')}
            for entry in self.entries.iterdir():
                if entry.name in indexed or entry.is_symlink() or not entry.is_dir():
                    continue
                try:
                    manifest = self._manifest(entry)
                    valid = (manifest.get('id') == entry.name and (entry / 'owner').read_text() == manifest.get('owner')
                             and all(_digest(entry / a['name']) == (a['sha256'], a['bytes']) for a in manifest['artifacts']))
                except (OSError, ValueError, KeyError):
                    continue
                with closing(self._db()) as db, db:
                    self._index(db, manifest, 'ok' if valid else 'altered')
                report['reindexed'] += 1
            with closing(self._db()) as db, db:
                for r in db.execute("SELECT id FROM entries WHERE state != 'missing'").fetchall():
                    if not (self.entries / r['id']).is_dir():
                        db.execute("UPDATE entries SET state = 'missing' WHERE id = ?", (r['id'],)); report['missing'] += 1
                for r in db.execute("SELECT id, process, pid FROM pending WHERE state = 'running'").fetchall():
                    # Another store's intent is stale once its process is gone (or was an earlier store in this one).
                    if r['process'] != self.process and (r['pid'] == os.getpid() or not psutil.pid_exists(r['pid'])):
                        db.execute("UPDATE pending SET state = 'interrupted' WHERE id = ?", (r['id'],)); report['interrupted'] += 1
        return report
