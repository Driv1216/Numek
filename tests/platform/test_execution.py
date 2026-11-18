"""Worker host: warm/isolated classes, thread caps, budgets, lease loss, cancellation, isolation."""
import threading
import time

import pytest

from numek_platform.evidence.reader import pin, resolve
from numek_platform.execution import jobs
from numek_platform.execution.host import HostBudget, JobKind, Registry, WorkerHost
from numek_platform.execution.context import InProcessContext
from numek_platform.errors import PlatformError

MiB = 1024**2


def _registry():
    return Registry([
        JobKind('echo', 'jobs_fixture:echo', job_class='isolated', threads=2, rss_bytes=512 * MiB, seconds=60),
        JobKind('warm_echo', 'jobs_fixture:echo', job_class='warm', threads=1, rss_bytes=512 * MiB, seconds=60),
        JobKind('sleep', 'jobs_fixture:sleep', job_class='isolated', rss_bytes=256 * MiB, seconds=60),
        JobKind('short', 'jobs_fixture:sleep', job_class='isolated', rss_bytes=256 * MiB, seconds=1),
        JobKind('allocate', 'jobs_fixture:allocate', job_class='isolated', rss_bytes=150 * MiB, seconds=60),
        JobKind('leak', 'jobs_fixture:leak', job_class='warm', rss_bytes=512 * MiB, seconds=60),
        JobKind('fail', 'jobs_fixture:fail', job_class='warm', rss_bytes=512 * MiB, seconds=60),
        JobKind('publish', 'jobs_fixture:publish', job_class='isolated', rss_bytes=1024 * MiB, seconds=60),
    ])


@pytest.fixture
def host(platform, job_path):
    instance = WorkerHost(platform.db, platform.root / 'store', registry=_registry(),
                          budget=HostBudget(rss_bytes=8 * 1024 * MiB, threads=8), lease_seconds=3, poll_seconds=0.05)
    yield instance
    instance.shutdown()


def _run(platform, host, kind, payload=None, scope=None, key=None, timeout=60):
    scope = scope or platform.scope
    with platform.db.transaction() as conn:
        row = host.registry.enqueue(conn, scope, kind, idempotency_key=key or f'{kind}-{time.monotonic_ns()}',
                                    payload=payload or {})
    host.step()
    assert host.wait_idle(timeout)
    with platform.db.connect() as conn:
        return jobs.get(conn, scope, row['id'])


def test_isolated_job_runs_with_thread_caps(platform, host):
    job = _run(platform, host, 'echo', {'x': 1})
    assert job['state'] == 'succeeded'
    assert job['result']['omp'] == '2' and job['result']['payload'] == {'x': 1}


def test_warm_processes_are_reused_within_an_org_only(platform, host):
    first = _run(platform, host, 'warm_echo')['result']['pid']
    second = _run(platform, host, 'warm_echo')['result']['pid']
    other_scope, _ = platform.new_org('other')
    third = _run(platform, host, 'warm_echo', scope=other_scope)['result']['pid']
    assert first == second and third != first


def test_isolation_violation_recycles_the_warm_process(platform, host):
    leaked = _run(platform, host, 'leak')
    assert leaked['state'] == 'succeeded'
    after = _run(platform, host, 'leak')
    assert after['result']['pid'] != leaked['result']['pid']


def test_deadline_and_memory_budgets_kill_the_job(platform, host):
    assert _run(platform, host, 'short', {'seconds': 10})['error']['code'] == 'deadline'
    assert _run(platform, host, 'allocate', {'mb': 400})['error']['code'] == 'rss_limit'


def test_failures_report_retry_semantics(platform, host):
    assert _run(platform, host, 'fail', {'retryable': False})['state'] == 'failed'
    assert _run(platform, host, 'fail', {'retryable': True})['state'] == 'queued'


def test_lease_loss_kills_the_attempt_and_writes_nothing(platform, host):
    with platform.db.transaction() as conn:
        row = host.registry.enqueue(conn, platform.scope, 'sleep', idempotency_key='lost', payload={'seconds': 20})
    host.step()
    time.sleep(0.5)
    with platform.db.transaction() as conn:
        conn.execute('UPDATE jobs SET fence = fence + 1 WHERE id = %s', (row['id'],))   # another owner took over
    assert host.wait_idle(15)
    assert [o for j, _f, o in host.outcomes if j == row['id']] == ['fence_lost']
    with platform.db.connect() as conn:
        job = jobs.get(conn, platform.scope, row['id'])
    assert job['state'] == 'running' and job['result'] is None


def test_cancellation_reaches_a_running_job(platform, host):
    with platform.db.transaction() as conn:
        row = host.registry.enqueue(conn, platform.scope, 'sleep', idempotency_key='cancel', payload={'seconds': 20})
    host.step()
    time.sleep(0.3)
    with platform.db.connect() as conn:
        assert jobs.request_cancel(conn, platform.scope, row['id']) == 'cancelling'
    assert host.wait_idle(15)
    with platform.db.connect() as conn:
        assert jobs.get(conn, platform.scope, row['id'])['state'] == 'cancelled'


def test_child_publishes_evidence_under_its_fence(platform, host):
    job = _run(platform, host, 'publish', {'event': 'from-child', 'catalog_id': str(platform.catalog_id)})
    assert job['state'] == 'succeeded' and job['result']['new_facts'] == 1
    read_pin = pin(platform.db, platform.scope, platform.catalog_id, holder='t')
    assert len(resolve(platform.db, read_pin)) == 1


def test_budget_admission_bounds_concurrency(platform, job_path):
    host = WorkerHost(platform.db, platform.root / 'store', registry=_registry(),
                      budget=HostBudget(rss_bytes=600 * MiB, threads=8, essential_reserve_rss=0), lease_seconds=5)
    try:
        with platform.db.transaction() as conn:
            for i in range(3):
                host.registry.enqueue(conn, platform.scope, 'sleep', idempotency_key=f'b{i}', payload={'seconds': 1})
        assert host.step() == 2            # 2 x 256 MiB fit in 600 MiB; the third waits
        assert host.wait_idle(20)
        assert host.step() == 1
        assert host.wait_idle(20)
    finally:
        host.shutdown()


def test_in_process_context_checks_deadline_and_cancellation():
    cancelled = threading.Event()
    ctx = InProcessContext(deadline=time.monotonic() + 60, cancelled=cancelled.is_set)
    assert ctx.run(lambda a, progress: a * 2, (21,)) == 42
    cancelled.set()
    with pytest.raises(PlatformError) as caught:
        ctx.run(lambda a, progress: a, (1,))
    assert caught.value.code == 'cancelled'
