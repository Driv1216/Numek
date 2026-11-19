"""Execution-agnostic services: ``ctx.run`` under the spawned workbench context and the in-process job context."""
import threading
import time

import pytest

from confidenceguard.contracts import EvaluationError
from confidenceguard.execution_context import InProcessContext, SpawnContext, ctx, using


def _double(values, *, progress=None):
    values.append('worker-side')                 # a phase mutating its arguments must not reach the caller
    return {'twice': [v * 2 for v in values[:-1]]}


def _normalized(value):
    volatile = {'analysis_id', 'generated_at', 'execution', 'binding', 'end_to_end_seconds', 'duration_seconds',
                'peak_worker_rss_bytes', 'whole_job_seconds', 'effective_cutoff_ns'}   # 'now'-dependent
    if isinstance(value, dict):
        return {k: _normalized(v) for k, v in value.items() if k not in volatile}
    if isinstance(value, list):
        return [_normalized(v) for v in value]
    return value


def _differences(x, y, path=''):
    if type(x) is not type(y):
        return [path]
    if isinstance(x, dict):
        return [d for k in sorted(set(x) | set(y)) for d in
                ([path + '/' + k] if k not in x or k not in y else _differences(x[k], y[k], path + '/' + k))]
    if isinstance(x, list):
        return [path] if len(x) != len(y) else [d for i, (a, b) in enumerate(zip(x, y)) for d in _differences(a, b, f'{path}[{i}]')]
    if isinstance(x, float):                     # parallel floating-point aggregation: last-bit differences
        return [] if abs(x - y) <= max(1e-12, 1e-9 * max(abs(x), abs(y))) else [path]
    return [] if x == y else [path]


def test_dispatch_defaults_to_spawn_and_scopes_the_active_context():
    assert isinstance(ctx.current, SpawnContext)
    job = InProcessContext()
    with using(job):
        assert ctx.current is job
    assert isinstance(ctx.current, SpawnContext)


def test_in_process_phases_have_spawn_isolation_and_phase_boundary_budgets():
    arguments = [1, 2, 3]
    result = InProcessContext().run(_double, (arguments,), None)
    assert result == {'twice': [2, 4, 6]} and arguments == [1, 2, 3]
    cancelled = threading.Event()
    cancelled.set()
    with pytest.raises(EvaluationError) as caught:
        InProcessContext(cancel=cancelled).run(_double, ([1],), None)
    assert caught.value.code == 'cancelled'
    with pytest.raises(EvaluationError) as caught:
        InProcessContext().run(_double, ([1],), None, deadline=time.monotonic() - 1)
    assert caught.value.code == 'deadline_exceeded'


def test_in_process_phase_isolates_governance_and_closes_its_attempts(platform, monkeypatch, tmp_path):
    from test_cg3_on_platform import _cg3_helpers
    from confidenceguard import platform_catalog
    from confidenceguard.history_storage import Catalog
    monkeypatch.setenv('NUMEK_PLATFORM_DSN', platform.db.dsn)
    helpers = _cg3_helpers()
    ws = helpers.workspace(tmp_path.resolve())
    ws.ingest(helpers.batch(tmp_path.resolve()))
    root = str(ws.catalog.root)
    platform_catalog._WORKER_GOVERNANCE['caller-sentinel'] = {'reservation': {}}
    seen = {}

    def phase(path, *, progress=None):
        assert 'caller-sentinel' not in platform_catalog._WORKER_GOVERNANCE        # fresh state inside the phase
        catalog = Catalog(path).ensure_governance(namespace='events', k=1, purpose_label='historical_selection')
        seen['job'] = catalog.governance['reservation']['job_id']
        return len(list(catalog.iter_facts('outcome')))

    try:
        with using(InProcessContext()):
            assert ctx.run(phase, (root,), None) > 0
        assert root not in platform_catalog._WORKER_GOVERNANCE                     # nothing leaks out
        assert 'caller-sentinel' in platform_catalog._WORKER_GOVERNANCE            # the caller's state is restored
        with platform.db.connect() as conn:
            state = conn.execute('SELECT state FROM jobs WHERE id = %s', (seen['job'],)).fetchone()['state']
        assert state == 'succeeded'                                                # the phase's attempt was closed
    finally:
        platform_catalog._WORKER_GOVERNANCE.pop('caller-sentinel', None)


def test_cg3_platform_analysis_is_identical_in_process_and_spawned(platform, monkeypatch, tmp_path):
    from test_cg3_on_platform import _cg3_helpers
    monkeypatch.setenv('NUMEK_PLATFORM_DSN', platform.db.dsn)
    helpers = _cg3_helpers()
    ws = helpers.workspace(tmp_path.resolve())
    ws.ingest(helpers.batch(tmp_path.resolve()))
    spawned = ws.analyze(helpers.longitudinal(ws, catalog_sequence=1), request_id='spawned')
    with using(InProcessContext()):                       # same snapshot K as the spawned run
        in_process = ws.analyze(helpers.longitudinal(ws, catalog_sequence=1), request_id='in-process')
    assert in_process.data['analysis_id'] != spawned.data['analysis_id']
    assert _differences(_normalized(in_process.to_private_dict()), _normalized(spawned.to_private_dict())) == []


def test_cg1_workbench_evaluation_is_identical_in_process_and_spawned(tmp_path):
    from confidenceguard import evaluate
    from tests.cg4.helpers import binary
    evaluation = binary(tmp_path.resolve(), n=120).evaluation
    spawned = evaluate(evaluation)
    with using(InProcessContext()):
        in_process = evaluate(evaluation)
    assert _differences(_normalized(in_process.to_private_dict()), _normalized(spawned.to_private_dict())) == []
