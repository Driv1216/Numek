"""numek_monitor: a thin, non-blocking producer SDK for NUMEK CG7 ingestion (standard library only).

    from numek_monitor import Monitor
    monitor = Monitor('https://numek.example/', source='scorecard-prod', token=TOKEN, buffer_dir='/var/lib/app/numek')
    monitor.log({'id': '123', 'entity': 'c-9', 'when': '2026-11-20T10:00:00Z', 'p': 0.18, 'decision': 'approve'})

It is never on the scoring path: ``log`` appends to a local buffer and returns at once; it never raises
and never waits on the network. A background thread seals buffered rows into batches and sends them.

Delivery states (plan H.5), as reported by ``log`` and ``stats``:

``buffered_memory``  in process memory only (``durability='memory'``); lost if the process dies
``buffered_disk``    appended to the on-disk segment; fsync'd by group commit within ``commit_interval``
                     (default 200 ms): survives a process crash, not loss of the disk
``sent``             a batch in flight
``acknowledged``     the installation answered 202: its exact bytes are durable there and will be processed
``dropped``          the buffer was full; the row was discarded and counted. Known loss is reported to
                     the installation in the next batch (``Numek-Dropped-Rows``)

Delivery is at least once. Each batch keeps a stable id (this buffer's id and the batch sequence), so a
batch resent after a crash or a lost response is recognised by the installation and never duplicated.
Batches the installation rejects (authentication, contract, size) are kept under ``rejected/``.
"""
import json
import os
import threading
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

__all__ = ['Monitor']


class Monitor:
    def __init__(self, endpoint, source, token, buffer_dir=None, *, batch_rows=500, flush_interval=2.0,
                 commit_interval=0.2, max_buffer_bytes=64 * 1024**2, durability='disk', timeout=10.0,
                 declared_identity=None, start=True):
        if durability not in ('disk', 'memory'):
            raise ValueError('durability is disk or memory')
        if durability == 'disk' and buffer_dir is None:
            raise ValueError('a buffer_dir is required for disk durability')
        self.url = endpoint.rstrip('/') + f'/api/ops/v1/sources/{source}/batches'
        self.token, self.timeout = token, timeout
        self.batch_rows, self.flush_interval, self.commit_interval = batch_rows, flush_interval, commit_interval
        self.max_buffer_bytes, self.durability = max_buffer_bytes, durability
        self.identity = json.dumps(declared_identity or {}, sort_keys=True)
        self._lock = threading.RLock()
        self._wake = threading.Event()
        self._stop = threading.Event()
        self._stats = {'logged': 0, 'dropped': 0, 'sent': 0, 'acknowledged_batches': 0, 'acknowledged_rows': 0,
                       'rejected_batches': 0, 'retries': 0}
        self._memory, self._memory_bytes, self._sealed_memory = [], 0, []
        self._backoff = 0.0
        if durability == 'disk':
            self.dir = Path(buffer_dir)
            self.dir.mkdir(mode=0o700, parents=True, exist_ok=True)
            (self.dir / 'rejected').mkdir(mode=0o700, exist_ok=True)
            self._state = self._load_state()
            self._active = None
            self._active_rows = 0
            self._active_since = None
            self._dirty = False
            self._recover()
        else:
            self._state = {'buffer_id': uuid.uuid4().hex, 'next_seq': 1, 'dropped_pending': 0}
        self._thread = None
        if start:
            self._thread = threading.Thread(target=self._run, name='numek-monitor', daemon=True)
            self._thread.start()

    # Public API ------------------------------------------------------------------------------------------
    def log(self, row):
        """Buffer one row. Never raises; returns its delivery state (buffered_disk, buffered_memory or dropped)."""
        try:
            line = (json.dumps(row, separators=(',', ':'), sort_keys=True, default=str) + '\n').encode()
        except Exception:
            with self._lock:
                self._drop()
            return 'dropped'
        with self._lock:
            if self._buffered_bytes() + len(line) > self.max_buffer_bytes:
                self._drop()
                return 'dropped'
            self._stats['logged'] += 1
            if self.durability == 'memory':
                self._memory.append(line)
                self._memory_bytes += len(line)
                if len(self._memory) >= self.batch_rows:
                    self._wake.set()
                return 'buffered_memory'
            if self._active is None:
                self._active = open(self.dir / 'active.jsonl', 'ab', buffering=0)
                os.chmod(self.dir / 'active.jsonl', 0o600)
                self._active_since = time.monotonic()
            self._active.write(line)
            self._active_rows += 1
            self._dirty = True
            if self._active_rows >= self.batch_rows:
                self._wake.set()
            return 'buffered_disk'

    def flush(self, timeout=30.0):
        """Seal what is buffered and wait until every batch is acknowledged (or ``timeout``). Returns success."""
        deadline = time.monotonic() + timeout
        with self._lock:
            self._seal()
        while time.monotonic() < deadline:
            self._wake.set()
            if self._thread is None:
                self._send_all()
            if self.pending_batches() == 0:
                return True
            time.sleep(0.05)
        return self.pending_batches() == 0

    def close(self, timeout=30.0):
        ok = self.flush(timeout)
        self._stop.set()
        self._wake.set()
        if self._thread is not None:
            self._thread.join(timeout)
        with self._lock:
            self._commit()
            if self.durability == 'disk' and self._active is not None:
                self._active.close()
                self._active = None
        return ok

    def stats(self):
        with self._lock:
            return {**self._stats, 'pending_batches': self.pending_batches(), 'buffered_bytes': self._buffered_bytes(),
                    'dropped_not_yet_reported': self._state['dropped_pending']}

    def pending_batches(self):
        with self._lock:
            if self.durability == 'memory':
                return len(self._sealed_memory) + (1 if self._memory else 0)
            return len(self._segments()) + (1 if self._active_rows else 0)

    # Buffer ----------------------------------------------------------------------------------------------
    def _load_state(self):
        path = self.dir / 'state.json'
        if path.is_file():
            return json.loads(path.read_text())
        state = {'buffer_id': uuid.uuid4().hex, 'next_seq': 1, 'dropped_pending': 0}
        self._write_state(state)
        return state

    def _write_state(self, state=None):
        state = state or self._state
        path = self.dir / 'state.json'
        tmp = path.with_name('.state.json.tmp')
        with open(tmp, 'wb') as stream:
            stream.write(json.dumps(state).encode())
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)

    def _segments(self):
        return sorted((p for p in self.dir.glob('seg-*.jsonl')), key=lambda p: int(p.stem.split('-')[1]))

    def _buffered_bytes(self):
        if self.durability == 'memory':
            return self._memory_bytes + sum(len(b) for _seq, b, _d in self._sealed_memory)
        total = sum(p.stat().st_size for p in self._segments())
        active = self.dir / 'active.jsonl'
        return total + (active.stat().st_size if active.exists() else 0)

    def _drop(self):
        self._stats['dropped'] += 1
        self._state['dropped_pending'] += 1
        if self.durability == 'disk':
            self._dirty = True

    def _recover(self):
        """A previous process left an active segment: seal it so it is sent (at least once)."""
        active = self.dir / 'active.jsonl'
        if active.exists() and active.stat().st_size:
            self._seal_file(active)
        elif active.exists():
            active.unlink()

    def _commit(self):
        """Group commit: make appended rows and drop counts durable."""
        if self.durability != 'disk' or not self._dirty:
            return
        if self._active is not None:
            os.fsync(self._active.fileno())
        self._write_state()
        self._dirty = False

    def _seal_file(self, path):
        seq = self._state['next_seq']
        meta = {'seq': seq, 'dropped': self._state['dropped_pending']}
        target = self.dir / f'seg-{seq}.jsonl'
        (self.dir / f'seg-{seq}.meta').write_text(json.dumps(meta))
        os.replace(path, target)
        self._state.update(next_seq=seq + 1, dropped_pending=0)
        self._write_state()

    def _seal(self):
        if self.durability == 'memory':
            if self._memory:
                seq = self._state['next_seq']
                self._sealed_memory.append((seq, b''.join(self._memory), self._state['dropped_pending']))
                self._state.update(next_seq=seq + 1, dropped_pending=0)
                self._memory, self._memory_bytes = [], 0
            return
        if self._active is None or not self._active_rows:
            return
        self._active.flush()
        os.fsync(self._active.fileno())
        self._active.close()
        self._active, self._active_rows, self._active_since = None, 0, None
        self._seal_file(self.dir / 'active.jsonl')
        self._dirty = False

    # Sending ---------------------------------------------------------------------------------------------
    def _post(self, seq, body, dropped):
        request = urllib.request.Request(self.url, data=body, method='POST', headers={
            'Authorization': f'Bearer {self.token}', 'Content-Type': 'application/x-ndjson',
            'Numek-Batch-Id': f'sdk:{self._state["buffer_id"]}:{seq}', 'Numek-Dropped-Rows': str(dropped),
            'Numek-Declared-Identity': self.identity})
        self._stats['sent'] += 1
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return response.status
        except urllib.error.HTTPError as exc:
            return exc.code
        except (urllib.error.URLError, OSError, TimeoutError):
            return None

    def _send_all(self):
        if time.monotonic() < self._backoff:
            return
        while True:
            with self._lock:
                if self.durability == 'memory':
                    if not self._sealed_memory:
                        return
                    seq, body, dropped = self._sealed_memory[0]
                    path = None
                else:
                    segments = self._segments()
                    if not segments:
                        return
                    path = segments[0]
                    seq = int(path.stem.split('-')[1])
                    meta = json.loads((self.dir / f'seg-{seq}.meta').read_text())
                    body, dropped = path.read_bytes(), meta['dropped']
            status = self._post(seq, body, dropped)
            with self._lock:
                rows = body.count(b'\n')
                if status in (200, 202):
                    self._stats['acknowledged_batches'] += 1
                    self._stats['acknowledged_rows'] += rows
                    self._backoff = 0.0
                    self._forget(path, seq, rejected=False)
                elif status in (400, 401, 403, 404, 409, 413):
                    self._stats['rejected_batches'] += 1
                    self._forget(path, seq, rejected=True)
                else:                                    # 429, 5xx, network: keep and retry later
                    self._stats['retries'] += 1
                    self._backoff = time.monotonic() + min(30.0, 0.25 * 2 ** min(self._stats['retries'], 7))
                    return

    def _forget(self, path, seq, *, rejected):
        if self.durability == 'memory':
            self._sealed_memory.pop(0)
            return
        meta = self.dir / f'seg-{seq}.meta'
        if rejected:
            os.replace(path, self.dir / 'rejected' / path.name)
            os.replace(meta, self.dir / 'rejected' / meta.name)
        else:
            path.unlink()
            meta.unlink()

    def _run(self):
        while not self._stop.is_set():
            self._wake.wait(self.commit_interval)
            self._wake.clear()
            try:
                with self._lock:
                    self._commit()
                    full = (self._active_rows if self.durability == 'disk' else len(self._memory)) >= self.batch_rows
                    aged = (self.durability == 'disk' and self._active_since is not None
                            and time.monotonic() - self._active_since >= self.flush_interval)
                    if full or aged or (self.durability == 'memory' and self._memory):
                        self._seal()
                self._send_all()
            except Exception:                            # never let the SDK disturb the application
                time.sleep(self.commit_interval)
