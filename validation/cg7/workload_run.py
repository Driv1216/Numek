"""Run an admitted CG7 workload and record its M.5 measurements (plan M.5, R2.8).

    python validation/cg7/workload_run.py --workload W-DEV-S1 --root <scratch dir> --workers 3 --out <result.json>

It refuses a workload whose preflight record (``--preflight``) is not ``admitted``.

**How it runs.** On a fresh P-LOCAL installation:
1. Load the reference days and confirm the workload's monitoring definition (daily windows).
2. Start ``--workers`` worker hosts (``confidenceguard ops worker --lanes essential``) as separate processes; they
   process the received batches exactly as in operation.
3. For each history milestone (for W-DEV-S1: 30, then 90 days):
   - receive one 10k-row batch per day (timing each durable acknowledgement), declare the producer watermark,
     and wait until every batch is terminal;
   - run the monitoring cycle at the end of the milestone day, in ``InProcessContext`` as a worker job does,
     timing every window evaluation by phase.
4. **Live phase:** five more days, one batch at a time, measuring publish lag (received → published) with an idle
   queue, and the day's cycle.
5. Stop the workers. Measure restart-to-ready of ``ops serve`` on the loaded installation, and the storage per fact.

**The incrementality ratio** (the mandatory R2.8 gate) is, for each phase, the median window evaluation time over the
last seven windows at the longest history, divided by the same median at the shortest history. The windows have the
same volume (10k predictions a day), so the ratio isolates history growth. Both the close and the maturity ratio must
be at most 1.3.
"""
import argparse
import json
import os
import signal
import statistics
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))

PY = sys.executable
DAY_NS = 86_400 * 10**9
REFERENCE_DAYS = 1          # 1 x 10k reference units: a phase result carries ~1.6 KB per unit against a 32 MiB budget (S10 finding)
GATE = 1.3


def tick(dt):
    return int(dt.timestamp()) * 10**9


def percentile(values, q):
    ordered = sorted(values)
    return ordered[max(0, min(len(ordered) - 1, int(round(q * (len(ordered) - 1)))))] if ordered else None


def wait_terminal(installation, timeout=7200):
    started = time.monotonic()
    while time.monotonic() - started < timeout:
        with installation.db.connect() as conn:
            row = conn.execute("SELECT count(*) FILTER (WHERE state IN ('received', 'processing')) AS pending, "
                               "count(*) FILTER (WHERE state = 'failed') AS failed FROM ops_batches").fetchone()
        if row['pending'] == 0:
            return row['failed']
        time.sleep(0.5)
    raise TimeoutError('batches did not finish')


def receive_days(installation, workload, days, *, seed):
    from confidenceguard.operations import ingest, workloads
    acks = []
    for day in days:
        body = workloads.csv_body(workloads.rows_for_day(day, workload.per_deployment_predictions, workload.features, seed=seed))
        started = time.perf_counter()
        ingest.receive(installation, 'events', f'day-{day}', body)
        acks.append(time.perf_counter() - started)
    last = workloads.T0 + timedelta(days=days[-1] + 1) - timedelta(seconds=1)
    ingest.declare_watermark(installation, 'events', last.strftime('%Y-%m-%dT%H:%M:%SZ'))
    return acks


class Progress:
    """Append-only JSON lines in the run directory, flushed per record: timings survive a stopped or failed run,
    and progress can be followed without querying the installation."""

    def __init__(self, path):
        self.path = Path(path)
        self.stream = open(self.path, 'w', encoding='utf-8')          # one run per directory

    def __call__(self, event, **fields):
        self.stream.write(json.dumps({'at': time.time(), 'event': event, **fields}, default=str) + '\n')
        self.stream.flush()


class Timings(list):
    def __init__(self, progress):
        super().__init__()
        self.progress = progress

    def append(self, item):
        super().append(item)
        self.progress('window', **item)


def timed_cycle(installation, now_tick, label, timings):
    """Run cycles at ``now_tick`` until no window advances; time each window evaluation by phase."""
    from confidenceguard.execution_context import InProcessContext, using
    from confidenceguard.operations.monitoring import runtime
    original = runtime.evaluate

    def timed(installation_, ctx, current, reference, phase, index, **kwargs):
        started = time.perf_counter()
        out = original(installation_, ctx, current, reference, phase, index, **kwargs)
        timings.append({'milestone': label, 'phase': phase, 'window': index, 'seconds': time.perf_counter() - started,
                        'units': out['units']})
        return out

    runtime.evaluate = timed
    try:
        started = time.perf_counter()
        with using(InProcessContext(deadline=None)):
            while runtime.cycle(installation, 'd1', now_tick=now_tick)['evaluated']:
                pass
        return time.perf_counter() - started
    finally:
        runtime.evaluate = original


def storage_rates(installation):
    from confidenceguard.operations import workloads
    s = workloads.storage(installation)
    with installation.db.connect() as conn:
        rows = conn.execute("SELECT coalesce(sum((counts->>'rows_accepted')::bigint), 0) AS n FROM ops_batches").fetchone()['n']
    objects = s['object_bytes_by_codec']
    raw = sum(v for k, v in objects.items() if k.startswith('encrypted_raw'))
    return {'facts': s['facts'], 'rows': int(rows), 'db_bytes': s['db_bytes'], 'db_bytes_per_fact': round(s['db_bytes'] / s['facts'], 1),
            'evidence_object_bytes_per_row': round((sum(objects.values()) - raw) / rows, 1) if rows else None,
            'object_bytes_by_codec': objects}


def restart_to_ready(installation_root, port=8479):
    env = {**os.environ, 'PYTHONDONTWRITEBYTECODE': '1', 'PYTHONPATH': str(ROOT / 'src')}
    started = time.monotonic()
    proc = subprocess.Popen([PY, '-B', '-m', 'confidenceguard.cli', 'ops', 'serve', '--installation', str(installation_root),
                             '--port', str(port)], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    ready = None
    try:
        while time.monotonic() - started < 120:
            try:
                with urllib.request.urlopen(f'http://127.0.0.1:{port}/readyz', timeout=2) as r:
                    if r.status == 200:
                        ready = time.monotonic() - started
                        break
            except (urllib.error.URLError, OSError):
                pass
            time.sleep(0.1)
    finally:
        proc.send_signal(signal.SIGTERM)
        proc.wait(timeout=60)
    return ready


def main():
    from numek_platform.installation import Installation
    from confidenceguard.operations import workloads
    from confidenceguard.operations.monitoring import definitions
    parser = argparse.ArgumentParser()
    parser.add_argument('--workload', required=True)
    parser.add_argument('--root', required=True)
    parser.add_argument('--workers', type=int, default=3)
    parser.add_argument('--preflight', required=True, help='The admitted preflight record for this workload.')
    parser.add_argument('--out', required=True)
    parser.add_argument('--seed', type=int, default=11)
    parser.add_argument('--override-history', help='Smoke runs only: comma-separated history days (recorded as an override).')
    parser.add_argument('--override-per-day', type=int, help='Smoke runs only: predictions per day (recorded as an override).')
    args = parser.parse_args()

    workload = workloads.WORKLOADS[args.workload]
    overrides = {}
    if args.override_history or args.override_per_day:
        import dataclasses
        changes = {}
        if args.override_history:
            changes['history_days'] = tuple(int(v) for v in args.override_history.split(','))
        if args.override_per_day:
            changes['predictions_per_day'] = args.override_per_day * workload.deployments
        overrides = {k: list(v) if isinstance(v, tuple) else v for k, v in changes.items()}
        workload = dataclasses.replace(workload, **changes)
    preflight = json.loads(Path(args.preflight).read_text())
    if preflight.get('workload') != workload.id or preflight.get('decision') != 'admitted':
        raise SystemExit(f'{workload.id} has no admitted preflight record; refusing to run it.')
    root = Path(args.root)
    installation = workloads.setup_installation(root / 'installation', workload)
    result = {'schema': 'numek.workload_run/1', 'workload': workload.id, 'preflight_digest': preflight['digest'],
              'overrides': overrides or None, 'counts_as_workload_run': not overrides,
              'host': workloads.host_capacity(root), 'workers': args.workers, 'milestones': [], 'gate': GATE}
    env = {**os.environ, 'PYTHONDONTWRITEBYTECODE': '1', 'PYTHONPATH': str(ROOT / 'src')}
    workers = [subprocess.Popen([PY, '-B', '-m', 'confidenceguard.cli', 'ops', 'worker', '--installation',
                                 str(installation.root), '--lanes', 'essential'], env=env, stdout=subprocess.DEVNULL,
                                stderr=open(root / f'worker-{i}.log', 'w')) for i in range(args.workers)]
    progress = Progress(root / 'progress.jsonl')
    progress('start', workload=workload.id, workers=args.workers, overrides=overrides or None)
    timings = Timings(progress)
    try:
        # Reference days, then inspect and confirm the definition (as an analyst does in Setup).
        started = time.perf_counter()
        acks = receive_days(installation, workload, list(range(REFERENCE_DAYS)), seed=args.seed)
        failed = wait_terminal(installation)
        confirm_at = tick(workloads.T0 + timedelta(days=REFERENCE_DAYS, hours=2))
        inspection = definitions.inspect(installation, 'd1', workloads.definition(workload.features, reference_days=REFERENCE_DAYS),
                                         now_tick=confirm_at)
        definitions.confirm(installation, 'd1', inspection['version'], inspection['inspection_digest'], actor='workload',
                            now_tick=confirm_at)
        result['reference'] = {'days': REFERENCE_DAYS, 'seconds': round(time.perf_counter() - started, 1), 'failed_batches': failed,
                               'detectors': [(d['id'], d.get('standing'), d.get('power')) for d in inspection['detectors']]}
        progress('reference', **result['reference'])
        loaded = REFERENCE_DAYS
        for milestone in workload.history_days:
            days = list(range(loaded, milestone))
            started = time.perf_counter()
            acks += receive_days(installation, workload, days, seed=args.seed)
            failed = wait_terminal(installation)
            load_seconds = time.perf_counter() - started
            progress('loaded', history_days=milestone, days=len(days), seconds=round(load_seconds, 1), failed_batches=failed)
            loaded = milestone
            cycle_seconds = timed_cycle(installation, tick(workloads.T0 + timedelta(days=milestone, hours=2)), milestone, timings)
            result['milestones'].append({'history_days': milestone, 'days_loaded': len(days), 'load_seconds': round(load_seconds, 1),
                                         'rows_per_second': round(len(days) * workload.per_deployment_predictions / load_seconds, 1),
                                         'failed_batches': failed, 'cycle_seconds': round(cycle_seconds, 1),
                                         'storage': storage_rates(installation)})
            progress('milestone', **result['milestones'][-1])
            print(json.dumps(result['milestones'][-1], default=str), flush=True)
        # Live phase: one batch at a time with an idle queue.
        live = []
        for day in range(loaded, loaded + 5):
            receive_days(installation, workload, [day], seed=args.seed)
            wait_terminal(installation)
            with installation.db.connect() as conn:
                row = conn.execute("SELECT extract(epoch FROM finished_at - received_at) AS lag FROM ops_batches "
                                   'WHERE batch_id = %s', (f'day-{day}',)).fetchone()
            seconds = timed_cycle(installation, tick(workloads.T0 + timedelta(days=day + 1, hours=2)), 'live', timings)
            live.append({'day': day, 'publish_lag_seconds': float(row['lag']), 'cycle_seconds': round(seconds, 1)})
            progress('live', **live[-1])
        result['live'] = live
    finally:
        for proc in workers:
            proc.send_signal(signal.SIGTERM)
        for proc in workers:
            try:
                proc.wait(timeout=90)
            except subprocess.TimeoutExpired:
                proc.kill()
    result['restart_to_ready_seconds'] = restart_to_ready(installation.root)
    result['storage'] = storage_rates(installation)
    result['window_timings'] = timings

    def median_last(label, phase, n=7):
        rows = sorted((t for t in timings if t['milestone'] == label and t['phase'] == phase), key=lambda t: t['window'])[-n:]
        return (statistics.median(t['seconds'] for t in rows), [t['window'] for t in rows], [t['units'] for t in rows]) if rows else (None, [], [])

    shortest, longest = min(workload.history_days), max(workload.history_days)
    ratios = {}
    for phase in ('close', 'maturity'):
        short, short_windows, short_units = median_last(shortest, phase)
        long, long_windows, long_units = median_last(longest, phase)
        ratios[phase] = {'median_seconds_short': short, 'median_seconds_long': long, 'windows_short': short_windows,
                         'windows_long': long_windows, 'units_short': short_units, 'units_long': long_units,
                         'ratio': round(long / short, 3) if short and long else None}
    # R2.8 gates window cost: both phases (the review found the maturity phase, which carries the outcome detectors,
    # had been reported but not gated).
    result['incrementality'] = {**ratios, 'histories': [shortest, longest], 'gate_phase': ['close', 'maturity'],
                                'passes': all(ratios[p]['ratio'] is not None and ratios[p]['ratio'] <= GATE
                                              for p in ('close', 'maturity'))}
    result['ack_seconds'] = {'p50': percentile(acks, 0.5), 'p95': percentile(acks, 0.95), 'max': max(acks), 'n': len(acks)}
    result['daily_window_seconds'] = {phase: {'p50': percentile([t['seconds'] for t in timings if t['phase'] == phase], 0.5),
                                              'p95': percentile([t['seconds'] for t in timings if t['phase'] == phase], 0.95),
                                              'max': max((t['seconds'] for t in timings if t['phase'] == phase), default=None)}
                                      for phase in ('close', 'maturity')}
    installation.stop()
    progress('done', incrementality=result['incrementality'])
    Path(args.out).write_text(json.dumps(result, indent=1, default=str) + '\n')
    print(json.dumps({k: result[k] for k in ('incrementality', 'ack_seconds', 'daily_window_seconds', 'restart_to_ready_seconds',
                                             'live', 'storage')}, indent=1, default=str))


if __name__ == '__main__':
    try:
        main()
    finally:                                   # never leave a P-LOCAL cluster running after a failed run
        import glob
        from numek_platform.installation import Installation
        for flag in ('--root',):
            if flag in sys.argv:
                candidate = Path(sys.argv[sys.argv.index(flag) + 1]) / 'installation'
                if (candidate / 'installation.json').is_file():
                    Installation(candidate).stop()
