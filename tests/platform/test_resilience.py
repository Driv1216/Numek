"""CG7 S10 operational resilience (plan M.3): deterministic fault injection at named boundaries, real SIGKILL of the
worker, API and controller processes, a database restart, a full object store, failing notification endpoints and
host clock skew.

Acceptance (M.3): no acknowledged batch is lost; no logical fact is duplicated; K stays contiguous; the ingestion
funnel reconciles; services are ready within 60 s of a restart; refusals are retryable and leave nothing partial.
Fault points already covered elsewhere and not repeated here: raw durability and acknowledgment
(test_ingestion), detector double application (test_monitoring), stale fences and deposed controllers
(test_fencing_gc), lease loss (test_execution), backup with active jobs and migration crash points
(test_backup_migration), notification redirects and egress denial (test_security, test_incidents).
"""
import errno
import http.server
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from confidenceguard.contracts import EvaluationError
from test_ingestion import body, contract, rows

ROOT = Path(__file__).resolve().parents[2]
NS = 'credit'


def _installation(dsn, root, env_name):
    from confidenceguard.operations import registry
    from numek_platform.installation import Installation
    os.environ[env_name] = dsn
    installation = Installation.create(Path(root).resolve() / 'installation', dsn_env=env_name)
    registry.register_system(installation, 'credit-default', 'Credit default 90d', namespace=NS)
    registry.register_deployment(installation, 'credit-default', 'scorecard-prod', 'Scorecard', tier=1,
                                 registered_identity={'model_version': 'v1'})
    registry.register_source(installation, 'scorecard-prod', 'scorecard-events', contract())
    return installation


@pytest.fixture
def ops(cluster, tmp_path):
    name = 'NUMEK_RES_' + uuid.uuid4().hex[:8].upper()
    installation = _installation(cluster.create_database('res_' + uuid.uuid4().hex[:10], template='numek_template'),
                                 tmp_path, name)
    yield installation
    os.environ.pop(name, None)


def _env():
    return {**os.environ, 'PYTHONPATH': os.pathsep.join([str(ROOT / 'src'), str(Path(__file__).parent)]),
            'PYTHONDONTWRITEBYTECODE': '1'}


def _invariants(installation, batches):
    """Every batch published exactly once, K contiguous, facts unique, the funnel reconciled."""
    from confidenceguard.operations import ingest
    with installation.db.connect() as conn:
        pubs = [r['sequence'] for r in conn.execute("SELECT sequence FROM publications WHERE sequence IS NOT NULL "
                                                    'ORDER BY sequence').fetchall()]
        head = conn.execute('SELECT max(head) AS h FROM catalog_heads').fetchone()['h']
        dupes = conn.execute('SELECT count(*) - count(DISTINCT (catalog_id, kind, key, revision)) AS d FROM fact_index').fetchone()['d']
        published = conn.execute("SELECT batch_id, catalog_sequence FROM ops_batches WHERE state = 'published'").fetchall()
    assert pubs == list(range(1, len(pubs) + 1)) and head == len(pubs)
    assert dupes == 0
    assert sorted(r['batch_id'] for r in published) == sorted(batches)
    assert len({r['catalog_sequence'] for r in published}) == len(published)        # one publication per batch
    assert ingest.funnel(installation, 'scorecard-events')['reconciled']


# 1. Named boundaries inside processing ------------------------------------------------------------------------------
BOUNDARIES = [('ingest', 'checked'), ('catalog', 'objects_published'), ('catalog', 'before_catalog_commit'),
              ('catalog', 'catalog_committed'), ('ingest', 'published')]


def test_crash_at_every_processing_boundary_then_retry_publishes_exactly_once(ops, monkeypatch):
    from confidenceguard import platform_catalog
    from confidenceguard.operations import ingest
    names = []
    for n, (where, boundary) in enumerate(BOUNDARIES):
        name = f'b-{boundary}'
        names.append(name)
        ingest.receive(ops, 'scorecard-events', name, body(rows(start=100 * n, count=20)))

        def crash(point, wanted=boundary):
            if point == wanted:
                raise RuntimeError(f'crash at {point}')
        if where == 'ingest':
            monkeypatch.setattr(ingest, 'fault', crash)
        else:
            monkeypatch.setattr(platform_catalog.PlatformCatalog, '_fault', lambda self, point: crash(point), raising=False)
        with pytest.raises(RuntimeError, match=boundary):
            ingest.process_pending(ops)
        monkeypatch.setattr(ingest, 'fault', lambda point: None)
        monkeypatch.setattr(platform_catalog.PlatformCatalog, '_fault', lambda self, point: None, raising=False)
        results = ingest.process_pending(ops)
        assert [r['state'] for r in results] == ['published'], boundary
    _invariants(ops, names)


# 2. A full object store ------------------------------------------------------------------------------------------------
def test_full_object_store_refuses_retryably_and_leaves_nothing_partial(ops, monkeypatch):
    from confidenceguard.operations import ingest, registry
    from confidenceguard.operations.web import create_app
    from numek_platform import objects
    real_open = objects.open_private

    class Full:
        def __init__(self, stream):
            self.stream = stream

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            self.stream.close()

        def write(self, chunk):
            raise OSError(errno.ENOSPC, 'No space left on device')

        def __getattr__(self, name):
            return getattr(self.stream, name)

    monkeypatch.setattr(objects, 'open_private', lambda path, mode: Full(real_open(path, mode)))
    with pytest.raises(EvaluationError) as refused:
        ingest.receive(ops, 'scorecard-events', 'full', body(rows(count=5)))
    assert refused.value.code == 'storage_full' and refused.value.retryable
    token = registry.issue_ingest_token(ops, 'scorecard-events')['token']
    response = create_app(ops).test_client().post('/api/ops/v1/sources/scorecard-events/batches', data=body(rows(count=5)),
                                                  headers={'Authorization': f'Bearer {token}', 'Numek-Batch-Id': 'full'})
    assert response.status_code == 507 and response.headers['Retry-After'] == '30'
    assert response.get_json()['error']['code'] == 'storage_full'
    staged = [p for p in (ops.store.root / 'staging').rglob('*') if p.is_file()]
    assert staged == []                                                          # no partial object left behind
    with ops.db.connect() as conn:
        assert conn.execute("SELECT count(*) AS n FROM ops_batches").fetchone()['n'] == 0      # nothing acknowledged
    monkeypatch.setattr(objects, 'open_private', real_open)                      # space freed: the same batch succeeds
    ingest.receive(ops, 'scorecard-events', 'full', body(rows(count=5)))
    assert ingest.process_pending(ops)[0]['state'] == 'published'
    _invariants(ops, ['full'])


# 3. SIGKILL of a worker host in the middle of a job ---------------------------------------------------------------
def _wait(predicate, timeout, step=0.1):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        value = predicate()
        if value:
            return value
        time.sleep(step)
    return None


def _job_states(installation, kind='ops_ingest_batch'):
    with installation.db.connect() as conn:
        return [dict(r) for r in conn.execute('SELECT id, state, fence FROM jobs WHERE kind = %s ORDER BY created_at',
                                              (kind,)).fetchall()]


def test_sigkilled_worker_host_mid_job_loses_nothing_and_duplicates_nothing(ops):
    from confidenceguard.operations import ingest
    from confidenceguard.operations.jobs import REGISTRY
    from numek_platform.evidence.gc import GarbageCollector
    from numek_platform.execution.controller import Controller
    from numek_platform.execution.host import WorkerHost
    names = []
    controller = Controller(ops.db)
    for delay in (0.2, 1.5):                                     # two arbitrary points while the job is running
        name = f'killed-{delay}'
        names.append(name)
        ingest.receive(ops, 'scorecard-events', name, body(rows(start=int(delay * 10000), count=3000)))
        worker = subprocess.Popen([sys.executable, '-B', '-m', 'confidenceguard.cli', 'ops', 'worker', '--installation',
                                   str(ops.root), '--lanes', 'essential'], env=_env(), start_new_session=True,
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            assert _wait(lambda: any(j['state'] == 'running' for j in _job_states(ops)), 60)
            time.sleep(delay)
        finally:
            os.killpg(worker.pid, signal.SIGKILL)                # the host and its job processes, no cleanup
            worker.wait(timeout=30)
        with ops.db.transaction() as conn:                       # let the lease period pass (database time)
            conn.execute("UPDATE jobs SET lease_expires_at = now() - interval '1 second' WHERE state = 'running'")
        assert controller.run_once()['expired'] == 1             # supersedes the dead attempt (fence + 1)
        host = WorkerHost(ops.db, ops.store.root, registry=REGISTRY, lanes=('essential',))
        try:
            assert host.step() == 1 and host.wait_idle(180)
        finally:
            host.shutdown()
        assert ingest.status(ops, 'scorecard-events', name)['state'] == 'published'
    assert all(j['state'] == 'succeeded' and j['fence'] >= 2 for j in _job_states(ops))
    GarbageCollector(ops.db, ops.store, pending_ttl=timedelta(0)).run_once()   # the dead attempts' objects are reclaimed
    with ops.db.connect() as conn:
        assert conn.execute("SELECT count(*) AS n FROM objects WHERE state = 'pending'").fetchone()['n'] == 0
    _invariants(ops, names)


# 4. SIGKILL of the API: a worker, then the whole server ------------------------------------------------------------
def _ready(port, timeout=60):
    def probe():
        try:
            with urllib.request.urlopen(f'http://127.0.0.1:{port}/readyz', timeout=2) as r:
                return r.status == 200
        except (urllib.error.URLError, OSError):
            return False
    return _wait(probe, timeout, 0.2)


def _serve(installation, port, log):
    return subprocess.Popen([sys.executable, '-B', '-m', 'confidenceguard.cli', 'ops', 'serve', '--installation',
                             str(installation.root), '--port', str(port), '--workers', '2', '--threads', '2'],
                            env=_env(), start_new_session=True, stdout=open(log, 'w'), stderr=subprocess.STDOUT)


def test_sigkilled_api_keeps_acknowledged_batches_and_is_ready_within_60_seconds(ops, tmp_path):
    from confidenceguard.operations import ingest, registry
    token = registry.issue_ingest_token(ops, 'scorecard-events')['token']
    port = 8900 + os.getpid() % 300

    def post(batch_id, start):
        request = urllib.request.Request(f'http://127.0.0.1:{port}/api/ops/v1/sources/scorecard-events/batches',
                                         data=body(rows(start=start, count=10)), method='POST',
                                         headers={'Authorization': f'Bearer {token}', 'Numek-Batch-Id': batch_id})
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.status

    server = _serve(ops, port, tmp_path / 'serve-1.log')
    try:
        assert _ready(port)
        assert post('before-kill', 0) == 202
        workers = subprocess.run(['pgrep', '-P', str(server.pid)], capture_output=True, text=True).stdout.split()
        os.kill(int(workers[0]), signal.SIGKILL)                 # one request worker dies; the master replaces it
        assert _wait(lambda: len(subprocess.run(['pgrep', '-P', str(server.pid)], capture_output=True,
                                                text=True).stdout.split()) == 2
                     and int(workers[0]) not in map(int, subprocess.run(['pgrep', '-P', str(server.pid)],
                                                                        capture_output=True, text=True).stdout.split()), 30)
        assert _ready(port, 30) and post('after-worker-kill', 100) == 202
    finally:
        os.killpg(server.pid, signal.SIGKILL)                    # the whole server, no graceful stop
        server.wait(timeout=30)
    started = time.monotonic()
    server = _serve(ops, port, tmp_path / 'serve-2.log')
    try:
        assert _ready(port)
        restart_to_ready = time.monotonic() - started
        assert restart_to_ready < 60
        assert post('after-restart', 200) == 202
    finally:
        server.send_signal(signal.SIGTERM)
        server.wait(timeout=60)
    for name in ('before-kill', 'after-worker-kill', 'after-restart'):            # every acknowledged batch survived
        assert ingest.status(ops, 'scorecard-events', name)['state'] == 'received'
    ingest.process_pending(ops)
    _invariants(ops, ['before-kill', 'after-worker-kill', 'after-restart'])


# 5. SIGKILL of the controller, and host clock skew -----------------------------------------------------------------
def _leader(installation):
    with installation.db.connect() as conn:
        row = conn.execute('SELECT holder, epoch, expires_at > now() AS live FROM controller_leadership').fetchone()
    return None if row is None else dict(row)


def test_sigkilled_controller_is_replaced_under_a_new_epoch(ops):
    from numek_platform.errors import PlatformError
    from numek_platform.execution.controller import Controller, assert_leader
    controller = subprocess.Popen([sys.executable, '-B', '-m', 'confidenceguard.cli', 'ops', 'controller', '--installation',
                                   str(ops.root)], env=_env(), start_new_session=True,
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        first = _wait(lambda: (_leader(ops) or {}).get('live') and _leader(ops), 60)
        assert first
    finally:
        os.killpg(controller.pid, signal.SIGKILL)
        controller.wait(timeout=30)
    successor = Controller(ops.db)
    assert successor.run_once() == {'leader': False}             # the dead leader's lease still runs (database time)
    with ops.db.transaction() as conn:
        conn.execute("UPDATE controller_leadership SET expires_at = now() - interval '1 second'")
    report = successor.run_once()
    assert report['leader'] and report['epoch'] == first['epoch'] + 1
    with ops.db.connect() as conn, pytest.raises(PlatformError) as deposed:
        with conn.transaction():
            assert_leader(conn, first['holder'], first['epoch'])   # anything the old leader still tried is refused
    assert deposed.value.code == 'not_leader'


def test_host_clock_skew_cannot_move_leadership_or_leases(ops):
    """Leadership and job leases are decided on the database clock, so a host whose clock runs an hour ahead (or
    behind) can neither take over a live leader nor expire a live lease."""
    from numek_platform.execution import jobs
    from numek_platform.execution.controller import Controller
    leader = Controller(ops.db, holder='leader')
    assert leader.run_once()['leader']
    with ops.db.transaction() as conn:
        jobs.enqueue(conn, ops.scope, 'ops_ingest_batch', idempotency_key='skew', lane='essential', job_class='warm',
                     payload={}, resources={'rss_bytes': 1, 'threads': 1, 'seconds': 60, 'device': 'cpu'})
    with ops.db.connect() as conn:
        lease, _row = jobs.claim(conn, 'worker-a', ['essential'], lease_seconds=60)
    assert lease is not None
    real = time.time
    try:
        for offset in (3600, -3600):
            time.time = lambda offset=offset: real() + offset    # this host's clock is wrong
            skewed = Controller(ops.db, holder=f'skewed{offset}')
            assert skewed.run_once() == {'leader': False}
            assert leader.run_once()['expired'] == 0              # the claimed lease is still live
    finally:
        time.time = real
    assert [j['state'] for j in _job_states(ops)] == ['running']


# 6. A database restart --------------------------------------------------------------------------------------------
def test_database_restart_is_survived_by_ingestion_worker_and_controller(tmp_path):
    from confidenceguard.operations import ingest
    from confidenceguard.operations.api import create_app
    from confidenceguard.operations.jobs import REGISTRY
    from numek_platform.db import Database
    from numek_platform.db.migrator import migrate
    from numek_platform.errors import PlatformError
    from numek_platform.execution.controller import Controller
    from numek_platform.execution.host import WorkerHost
    from numek_platform.local import LocalCluster
    root = Path(tempfile.mkdtemp(prefix='nmk-restart-')).resolve()
    try:
        cluster = LocalCluster(root / 'cluster')
    except PlatformError as exc:
        shutil.rmtree(root, ignore_errors=True)
        pytest.skip(str(exc))
    stop = threading.Event()
    try:
        cluster.start()
        dsn = cluster.create_database('restart')
        migrate(Database(dsn))
        installation = _installation(dsn, tmp_path, 'NUMEK_RES_RESTART')
        ingest.receive(installation, 'scorecard-events', 'before', body(rows(count=10)))
        host = WorkerHost(installation.db, installation.store.root, registry=REGISTRY, lanes=('essential',), poll_seconds=0.2)
        controller = Controller(installation.db, ttl_seconds=5)
        threads = [threading.Thread(target=host.run, args=(stop,), daemon=True),
                   threading.Thread(target=controller.run, args=(stop, 0.5), daemon=True)]
        for t in threads:
            t.start()
        assert _wait(lambda: ingest.status(installation, 'scorecard-events', 'before')['state'] == 'published', 120)
        client = create_app(installation).test_client()
        cluster.stop()                                            # the database goes away under both loops
        time.sleep(2)
        with pytest.raises((EvaluationError, PlatformError)) as down:
            ingest.receive(installation, 'scorecard-events', 'during', body(rows(start=50, count=10)))
        assert down.value.code == 'platform_unavailable' and down.value.retryable
        assert client.get('/readyz').status_code == 503
        started = time.monotonic()
        cluster.start()
        assert _wait(lambda: client.get('/readyz').status_code == 200, 60)
        assert time.monotonic() - started < 60
        assert all(t.is_alive() for t in threads)                 # neither loop died with the database
        assert host.unavailable >= 1
        ingest.receive(installation, 'scorecard-events', 'during', body(rows(start=50, count=10)))
        assert _wait(lambda: ingest.status(installation, 'scorecard-events', 'during')['state'] == 'published', 120)
        assert (_leader(installation) or {}).get('live')          # the controller leads again
        _invariants(installation, ['before', 'during'])
    finally:
        stop.set()
        time.sleep(1)
        cluster.stop()
        shutil.rmtree(root, ignore_errors=True)
        os.environ.pop('NUMEK_RES_RESTART', None)
