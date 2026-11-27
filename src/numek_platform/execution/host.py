"""Worker host: claims jobs within its budgets and supervises their processes.

* ``warm`` jobs reuse long-lived processes from pools keyed by
  (organisation, thread cap), so evidence of one organisation never shares
  a process with another. Processes recycle after ``warm_recycle_jobs`` jobs,
  on high resident memory or on an isolation-probe violation.
* ``isolated`` jobs get a fresh process each.

Every running attempt renews its lease about every third of the lease period.
If renewal reports that the fence moved, the host kills the process tree and
writes nothing for that attempt. Job processes write evidence themselves under
their fence; the host only records the terminal state, also under the fence.
"""
import dataclasses
import os
import threading
import time
import uuid
from dataclasses import dataclass, field

import psycopg

from ..errors import FenceLost, PlatformError
from . import jobs as job_store
from .supervision import ChildProcess

GiB = 1024**3


@dataclass(frozen=True)
class JobKind:
    name: str
    function: str                     # 'package.module:function', called as function(ctx, payload)
    lane: str = 'essential'
    job_class: str = 'warm'
    rss_bytes: int = 1 * GiB
    threads: int = 1
    seconds: int = 600
    device: str = 'cpu'

    def resources(self):
        return {'rss_bytes': self.rss_bytes, 'threads': self.threads, 'seconds': self.seconds, 'device': self.device}


class Registry:
    def __init__(self, kinds=()):
        self._kinds = {}
        for kind in kinds:
            self.register(kind)

    def register(self, kind):
        if kind.job_class not in ('warm', 'isolated'):
            raise ValueError(kind.job_class)
        self._kinds[kind.name] = kind
        return kind

    def get(self, name):
        try:
            return self._kinds[name]
        except KeyError:
            raise PlatformError('No worker can run this job kind.', 'unknown_job_kind') from None

    def names(self):
        return list(self._kinds)

    def enqueue(self, conn, scope, name, *, idempotency_key, payload=None, priority=0, max_attempts=3):
        kind = self.get(name)
        return job_store.enqueue(conn, scope, name, idempotency_key=idempotency_key, lane=kind.lane,
                                 job_class=kind.job_class, payload=payload, priority=priority,
                                 resources=kind.resources(), max_attempts=max_attempts)


@dataclass
class HostBudget:
    rss_bytes: int = 8 * GiB
    threads: int = 4
    devices: dict = field(default_factory=lambda: {'cpu': 1_000})
    essential_reserve_rss: int = 1 * GiB      # never lent to investigation or maintenance jobs


@dataclass
class _Usage:
    rss_bytes: int = 0
    threads: int = 0
    devices: dict = field(default_factory=dict)


class WorkerHost:
    def __init__(self, db, store_root, *, registry, budget=None, lanes=('essential', 'investigation', 'maintenance'),
                 name=None, lease_seconds=30, scratch_root=None, warm_recycle_jobs=100, warm_rss_fraction=0.75,
                 poll_seconds=0.5):
        self.db = db
        self.store_root = str(store_root)
        self.registry = registry
        self.budget = budget or HostBudget()
        self.lanes = tuple(lanes)
        self.id = uuid.uuid4()
        self.name = name or f'host-{os.getpid()}'
        self.owner = f'{self.name}:{self.id.hex[:8]}'
        self.lease_seconds = lease_seconds
        self.unavailable = 0              # claim rounds skipped because the database was unavailable
        self.scratch_root = str(scratch_root or os.path.join(self.store_root, 'scratch'))
        os.makedirs(self.scratch_root, mode=0o700, exist_ok=True)
        os.chmod(self.scratch_root, 0o700)
        self.warm_recycle_jobs = warm_recycle_jobs
        self.warm_rss_fraction = warm_rss_fraction
        self.poll_seconds = poll_seconds
        self._lock = threading.Lock()
        self._usage = _Usage()
        self._running = {}
        self._pools = {}
        self.outcomes = []                  # (job_id, fence, outcome) for observability and tests
        self._register()

    # Capacity --------------------------------------------------------------
    def _fits(self, resources, lane):
        rss, threads, device = resources.get('rss_bytes', GiB), resources.get('threads', 1), resources.get('device', 'cpu')
        with self._lock:
            reserve = 0 if lane == 'essential' else self.budget.essential_reserve_rss
            if self._usage.rss_bytes + rss > self.budget.rss_bytes - reserve:
                return False
            if self._usage.threads + threads > self.budget.threads:
                return False
            if self._usage.devices.get(device, 0) + 1 > self.budget.devices.get(device, 0):
                return False
            return True

    def _reserve(self, resources, sign):
        with self._lock:
            self._usage.rss_bytes += sign * resources.get('rss_bytes', GiB)
            self._usage.threads += sign * resources.get('threads', 1)
            device = resources.get('device', 'cpu')
            self._usage.devices[device] = self._usage.devices.get(device, 0) + sign

    def _register(self):
        from psycopg.types.json import Jsonb
        with self.db.transaction() as conn:
            conn.execute('INSERT INTO worker_hosts(id, name, capacity) VALUES (%s, %s, %s)',
                         (self.id, self.name, Jsonb(dataclasses.asdict(self.budget))))

    # Main loop -------------------------------------------------------------
    def step(self):
        """Claim and launch as many jobs as fit. Returns the number launched."""
        launched = 0
        with self.db.connect() as conn:
            conn.execute('UPDATE worker_hosts SET heartbeat_at = now() WHERE id = %s', (self.id,))
            for lane in self.lanes:
                while True:
                    lease, row = job_store.claim(conn, self.owner, [lane], lease_seconds=self.lease_seconds,
                                                 fits=lambda r, lane=lane: self._fits(r, lane),
                                                 kinds=self.registry.names())
                    if lease is None:
                        break
                    resources = dict(row['resources'])
                    self._reserve(resources, +1)
                    thread = threading.Thread(target=self._run, args=(lease, row, resources),
                                              name=f'job-{lease.job_id.hex[:8]}', daemon=True)
                    with self._lock:
                        self._running[(lease.job_id, lease.fence)] = thread
                    thread.start()
                    launched += 1
        return launched

    def run(self, stop):
        """Claim and run jobs until ``stop``. The database being unavailable (down, restarting, a dropped
        connection) is transient: the host keeps its running attempts, waits and claims again. Their leases
        are renewed when the database returns, or expire and the jobs retry under a new fence."""
        while not stop.is_set():
            try:
                self.step()
            except (PlatformError, psycopg.Error):
                self.unavailable += 1
                stop.wait(min(5.0, max(self.poll_seconds, 1.0)))
                continue
            stop.wait(self.poll_seconds)
        self.shutdown()

    def running(self):
        with self._lock:
            return len(self._running)

    def wait_idle(self, timeout=60):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            if not self.running():
                return True
            time.sleep(0.05)
        return False

    def shutdown(self):
        self.wait_idle(timeout=0)
        with self._lock:
            pools, self._pools = self._pools, {}
        for pool in pools.values():
            for child in pool:
                child.close()

    # Processes -------------------------------------------------------------
    def _acquire(self, kind, org_id):
        if kind.job_class == 'isolated':
            return ChildProcess(warm=False, threads=kind.threads)
        key = (org_id, kind.threads)
        with self._lock:
            pool = self._pools.setdefault(key, [])
            while pool:
                child = pool.pop()
                if child.alive():
                    return child
        return ChildProcess(warm=True, threads=kind.threads)

    def _release_process(self, kind, org_id, child, healthy):
        if kind.job_class == 'isolated' or not healthy or not child.alive():
            child.kill()
            return
        child.jobs_run += 1
        if (child.jobs_run >= self.warm_recycle_jobs
                or child.tree_rss() > self.warm_rss_fraction * kind.rss_bytes):
            child.close()
            return
        with self._lock:
            self._pools.setdefault((org_id, kind.threads), []).append(child)

    # One attempt ------------------------------------------------------------
    def _run(self, lease, row, resources):
        outcome = 'unknown'
        try:
            outcome = self._attempt(lease, row, resources)
        except Exception as exc:  # infrastructure failure: let the lease expire and the job retry
            outcome = f'host_error:{type(exc).__name__}'
        finally:
            self._reserve(resources, -1)
            with self._lock:
                self._running.pop((lease.job_id, lease.fence), None)
                self.outcomes.append((lease.job_id, lease.fence, outcome))

    def _attempt(self, lease, row, resources):
        kind = self.registry.get(row['kind'])
        spec = {'function': kind.function, 'payload': row['payload'], 'dsn': self.db.dsn,
                'store_root': self.store_root, 'scratch_root': self.scratch_root, 'threads': kind.threads,
                'seconds': resources.get('seconds', kind.seconds),
                'lease': {'org_id': str(lease.org_id), 'job_id': str(lease.job_id), 'fence': lease.fence,
                          'kind': lease.kind, 'owner': lease.owner}}
        child = self._acquire(kind, lease.org_id)
        healthy = False
        deadline = time.monotonic() + spec['seconds']
        renew_every = max(self.lease_seconds / 3, 0.2)
        next_renew = time.monotonic() + renew_every
        with self.db.connect() as conn:
            try:
                child.send(('job', spec))
                while True:
                    if child.poll(0.1):
                        try:
                            message, body = child.recv()
                        except EOFError:
                            message, body = 'died', None
                        if message == 'result':
                            healthy = body['isolation_clean']
                            return self._finish(conn, lease, lambda: job_store.complete(conn, lease, body['result']),
                                                'succeeded')
                        if message == 'error':
                            healthy = child.warm
                            return self._finish(conn, lease, lambda: job_store.fail(
                                conn, lease, {k: body[k] for k in ('code', 'message', 'type')},
                                retryable=body['retryable']), 'failed')
                    if not child.alive():
                        return self._finish(conn, lease, lambda: job_store.fail(
                            conn, lease, {'code': 'worker_terminated', 'message': 'Job process exited without a result.'},
                            retryable=True), 'terminated')
                    now = time.monotonic()
                    if now > deadline:
                        return self._finish(conn, lease, lambda: job_store.fail(
                            conn, lease, {'code': 'deadline', 'message': 'Whole-job deadline exceeded.'}), 'deadline')
                    if child.tree_rss() > resources.get('rss_bytes', kind.rss_bytes):
                        return self._finish(conn, lease, lambda: job_store.fail(
                            conn, lease, {'code': 'rss_limit', 'message': 'Job memory exceeded its budget.'}), 'rss_limit')
                    if now >= next_renew:
                        next_renew = now + renew_every
                        try:
                            cancel = job_store.renew(conn, lease, self.lease_seconds)
                        except FenceLost:
                            return 'fence_lost'
                        if cancel:
                            return self._finish(conn, lease, lambda: job_store.mark_cancelled(conn, lease), 'cancelled')
            finally:
                self._release_process(kind, lease.org_id, child, healthy)

    @staticmethod
    def _finish(conn, lease, action, outcome):
        try:
            action()
        except FenceLost:
            return 'fence_lost'
        return outcome
