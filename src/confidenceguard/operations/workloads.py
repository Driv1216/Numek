"""Workloads and the resource preflight (plan M.5, Addendum R2.8).

**Workloads keep their identities.** W-REF and W-DEV are the plan's workloads, defined here as data and never
shrunk. A workload that does not fit a host is recorded ``not_admitted_on_host``, and a separately named smaller
workload is defined instead, with every way it differs from its parent listed in ``deviations``.

**Preflight** (``confidenceguard ops preflight --workload W``) runs before any substantial workload:

1. **Calibration.** A scratch P-LOCAL installation ingests synthetic rows of the workload's shape through the real
   receive / process / publish path until about ``calibration_facts`` facts exist. It measures:
   - PostgreSQL bytes per fact and WAL bytes per fact;
   - object bytes per row, split into raw batches (retained 7 days) and evidence objects;
   - single-process ingestion throughput;
   - verify-on-read throughput (the exact bytes are hashed before use).
2. **Projection** for the workload: database, WAL generated, objects, backup, staging, memory and load time.
3. **Admission:** the projected disk must fit within 80% of the free space (a 20% reserve), and memory within 80%
   of physical memory. Otherwise the result is ``not_admitted_on_host``.

Load time is projected and reported, but it is not an admission criterion (R2.8 admits on capacity).
"""
import hashlib
import io
import json
import math
import os
import random
import shutil
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

RAW_RETENTION_DAYS = 7
DISK_RESERVE = 0.20
MEMORY_RESERVE = 0.20
T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
NAMESPACE = 'workload'


@dataclass(frozen=True)
class Workload:
    id: str
    description: str
    systems: int
    deployments: int
    predictions_per_day: int              # across all deployments
    revisions_per_day: int                # corrections and restatements, across all deployments
    features: int
    regions: int
    policies: int
    history_days: tuple                   # the history lengths the workload is measured at
    concurrent: tuple = ()                # load that runs alongside (backfill, a CG6 job)
    parent: str | None = None
    deviations: tuple = ()
    status: str = 'engineering_objective'

    @property
    def per_deployment_predictions(self):
        return self.predictions_per_day // self.deployments


WORKLOADS = {w.id: w for w in (
    Workload('W-REF', 'Reference workload (identity retained).', systems=3, deployments=20, predictions_per_day=2_000_000,
             revisions_per_day=1_000_000, features=30, regions=10, policies=1, history_days=(90,),
             concurrent=('7-day backfill', 'one CG6 robustness job'), status='hardware_dependent_qualification'),
    Workload('W-DEV', 'Development workload: W-REF shape at 10% volume.', systems=3, deployments=20,
             predictions_per_day=200_000, revisions_per_day=100_000, features=30, regions=10, policies=1,
             history_days=(30, 60, 90), concurrent=('7-day backfill', 'one CG6 robustness job')),
    Workload('W-DEV-S1', "One W-DEV deployment's prediction stream (10k predictions a day, 30 numeric features and one "
             'categorical), measured at 30 and 90 days of history.', systems=1, deployments=1, predictions_per_day=10_000,
             revisions_per_day=0, features=30, regions=0, policies=0, history_days=(30, 90), parent='W-DEV',
             deviations=('one system and one deployment instead of 3 and 20 (per-deployment volume equals W-DEV)',
                         'no revisions: corrections enter through the workspace API, not producer batches, and are not generated',
                         'no frozen regions and no policy',
                         'no concurrent backfill or CG6 job')),
)}


# Synthetic source -------------------------------------------------------------------------------------------------
def feature_names(n):
    return [f'f{i:02d}' for i in range(1, n + 1)]


def contract(features):
    fields = {'id': {'type': 'string', 'identity': True}, 'entity': {'type': 'string', 'required': True},
              'when': {'type': 'timestamp', 'required': True}, 'y': {'type': 'string', 'vocabulary': ['0', '1']},
              'p': {'type': 'number', 'required': True, 'probability': True}, 'available': {'type': 'timestamp'},
              'due': {'type': 'timestamp'}, 'group': {'type': 'string', 'vocabulary': ['a', 'b']},
              'model_version': {'type': 'string'}}
    fields.update({name: {'type': 'number'} for name in feature_names(features)})
    bindings = {'group': 'categorical', **{name: 'numeric' for name in feature_names(features)}}
    return {
        'format': 'csv', 'event_time': 'when', 'identity': {'model_version': 'model_version'}, 'fields': fields,
        'batch': {'namespace': NAMESPACE, 'outcome_definition_version': 'outcome-v1',
                  'bindings': [{'run': 'base', 'features': bindings}],
                  'evaluation': {
                      'task': {'kind': 'binary_classification', 'outcome_definition': 'Default', 'classes': ['0', '1'],
                               'positive_class': '1'},
                      'sources': [{'id': 'rows'}],
                      'runs': [{'id': 'base', 'source': 'rows', 'model': {'id': 'scorecard', 'version': '1'},
                                'key_columns': ['id'], 'entity_columns': ['entity'], 'prediction_at': {'column': 'when'},
                                'probabilities': {'positive_column': 'p'},
                                'decision': {'rule': 'probability_threshold', 'threshold': .5}, 'role': 'production'}],
                      'outcomes': {'source': 'rows', 'column': 'y', 'key_columns': ['id'],
                                   'available_at': {'column': 'available'}, 'due_at': {'column': 'due'}}}}}


def definition(features, *, reference_days=7, followup_days=7):
    """Daily windows from day ``reference_days``; the reference is the days before it."""
    day = 86_400 * 10**9
    start = T0 + timedelta(days=reference_days)
    return {
        'start': start.strftime('%Y-%m-%dT%H:%M:%SZ'), 'window_ns': str(day), 'allowed_lateness_ns': str(3600 * 10**9),
        'maturity': {'policy': 'equal_followup', 'followup_ns': str(followup_days * day)},
        'features': {'group': 'categorical', **{name: 'numeric' for name in feature_names(features)}},
        'cohorts': [{'id': 'population', 'column': 'group', 'categories': ['a', 'b']}],
        'reference': {'start': T0.strftime('%Y-%m-%dT%H:%M:%SZ'), 'end': start.strftime('%Y-%m-%dT%H:%M:%SZ'), 'alpha': 0.01},
        'detectors': [
            {'id': 'matured-error', 'statistic': 'error', 'delta': 0.01, 'target_false_alarms_per_30_days': 0.1, 'shift': 0.05,
             'max_useful_delay_days': 30},
            {'id': 'brier', 'statistic': 'brier', 'delta': 0.01, 'target_false_alarms_per_30_days': 0.1, 'shift': 0.05,
             'max_useful_delay_days': 30},
            {'id': 'abstention', 'statistic': 'abstention', 'delta': 0.01, 'alpha': 1e-4, 'target': 0.2},
        ],
        'estimators': ['implied_issued_error', 'implied_brier', 'composition_projection'],
    }


def rows_for_day(day, count, features, *, seed, error_rate=0.1, availability_days=3):
    """``count`` deterministic rows whose event times fall inside day ``day`` (UTC)."""
    rng = random.Random(f'{seed}:{day}')
    base = T0 + timedelta(days=day)
    names = feature_names(features)
    step = 86_400 / count
    out = []
    for j in range(count):
        when = base + timedelta(seconds=int(j * step))
        positive = rng.random() < 0.5
        correct = rng.random() >= error_rate
        y = ('1' if positive else '0') if correct else ('0' if positive else '1')
        ident = f'd{day}-{j}'
        avail = (when + timedelta(days=availability_days)).strftime('%Y-%m-%dT%H:%M:%SZ')
        row = {'id': ident, 'entity': f'e-{ident}', 'when': when.strftime('%Y-%m-%dT%H:%M:%SZ'), 'y': y,
               'p': f'{0.5 + (0.35 if positive else -0.35) + rng.uniform(-0.1, 0.1):.4f}', 'available': avail, 'due': avail,
               'group': 'a' if rng.random() < 0.6 else 'b', 'model_version': 'v1'}
        row.update({name: f'{rng.gauss(0, 1):.4f}' for name in names})
        out.append(row)
    return out


def csv_body(rows):
    import csv
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(rows[0]), lineterminator='\n')
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue().encode()


def setup_installation(root, workload, *, deployment='d1', system='s1', source='events'):
    """A fresh P-LOCAL installation registered for ``workload`` (one system, deployment and source)."""
    from numek_platform.installation import Installation
    from . import registry
    root = Path(root)
    if root.exists():
        if (root / 'installation.json').is_file():
            Installation(root).stop()                  # never delete a running cluster's directory
        shutil.rmtree(root)
    installation = Installation.create(root)
    registry.register_system(installation, system, system, namespace=NAMESPACE)
    registry.register_deployment(installation, system, deployment, deployment, tier=1, registered_identity={'model_version': 'v1'})
    registry.register_source(installation, deployment, source, contract(workload.features))
    return installation


# Measurements -----------------------------------------------------------------------------------------------------
def storage(installation):
    """Database, WAL position, fact count, and active object bytes by codec."""
    with installation.db.connect() as conn:
        db = conn.execute('SELECT pg_database_size(current_database()) AS b').fetchone()['b']
        wal = conn.execute("SELECT (pg_current_wal_lsn() - '0/0'::pg_lsn)::bigint AS w").fetchone()['w']
        facts = conn.execute('SELECT count(*) AS n FROM fact_index').fetchone()['n']
        codecs = {r['codec']: int(r['b']) for r in conn.execute(
            "SELECT codec, coalesce(sum(bytes), 0) AS b FROM objects WHERE state = 'active' GROUP BY codec").fetchall()}
    return {'db_bytes': int(db), 'wal_lsn': int(wal), 'facts': int(facts), 'object_bytes_by_codec': codecs}


def verify_throughput(installation, *, budget_bytes=512 * 2**20):
    """Hash-verified reads of active evidence objects (bytes per second over at most ``budget_bytes``)."""
    store = installation.store
    with installation.db.connect() as conn:
        rows = conn.execute("SELECT physical_key, sha256, bytes FROM objects WHERE state = 'active' ORDER BY bytes DESC").fetchall()
    read, started = 0, time.perf_counter()
    for row in rows:
        store.read_verified(row['physical_key'], bytes(row['sha256']).hex(), row['bytes'])
        read += row['bytes']
        if read >= budget_bytes:
            break
    elapsed = time.perf_counter() - started
    return {'bytes': read, 'seconds': round(elapsed, 3), 'bytes_per_second': round(read / elapsed) if elapsed else None}


def parquet_ratio(installation, *, sample_objects=40):
    """Size of the same logical records in ``observation_facts_parquet_v1`` relative to ``utf8_jsonl_v1``.

    The CG3 capture path (and so operations ingestion) publishes JSONL; this re-encodes a sample of published JSONL
    objects with the Parquet codec to report the codec's ratio. It is a property of the codec, not of what the
    product currently stores.
    """
    import json as _json
    from numek_platform.evidence import codecs
    store = installation.store
    with installation.db.connect() as conn:
        rows = conn.execute("SELECT physical_key, sha256, bytes, records FROM objects WHERE state = 'active' AND codec = %s "
                            'ORDER BY bytes DESC LIMIT %s', (codecs.JSONL, sample_objects)).fetchall()
    jsonl = parquet = records = 0
    for row in rows:
        data = store.read_verified(row['physical_key'], bytes(row['sha256']).hex(), row['bytes'])
        decoded = [_json.loads(line) for line in data.splitlines() if line.strip()]
        jsonl += len(data)
        encoded, _rows = codecs.encode_observations(decoded)
        parquet += len(encoded)
        records += len(decoded)
    return {'objects': len(rows), 'records': records, 'jsonl_bytes': jsonl, 'parquet_bytes': parquet,
            'ratio': round(parquet / jsonl, 3) if jsonl else None}


def calibrate(scratch, workload, *, facts=1_000_000, batch_rows=10_000, seed=7, keep=False):
    """Ingest rows of ``workload``'s shape until about ``facts`` facts exist; return per-fact and per-row rates."""
    from . import ingest
    installation = setup_installation(Path(scratch) / 'calibration', workload)
    try:
        before = storage(installation)
        rows_sent, day, ingest_seconds, receive_seconds = 0, 0, 0.0, []
        target_rows = None
        while True:
            count = batch_rows
            rows = rows_for_day(day, count, workload.features, seed=seed)
            started = time.perf_counter()
            ingest.receive(installation, 'events', f'cal-{day}', csv_body(rows))
            receive_seconds.append(time.perf_counter() - started)
            ingest.process_pending(installation)
            ingest_seconds += time.perf_counter() - started
            rows_sent += count
            day += 1
            current = storage(installation)['facts'] - before['facts']
            if target_rows is None and current:
                target_rows = math.ceil(facts / (current / rows_sent))
            if current >= facts or (target_rows and rows_sent >= target_rows):
                break
        after = storage(installation)
        new_facts = after['facts'] - before['facts']
        objects = {c: after['object_bytes_by_codec'].get(c, 0) - before['object_bytes_by_codec'].get(c, 0)
                   for c in after['object_bytes_by_codec']}
        raw = sum(v for c, v in objects.items() if c.startswith('encrypted_raw'))
        result = {
            'rows': rows_sent, 'facts': new_facts, 'facts_per_row': round(new_facts / rows_sent, 4),
            'db_bytes_per_fact': round((after['db_bytes'] - before['db_bytes']) / new_facts, 1),
            'wal_bytes_per_fact': round((after['wal_lsn'] - before['wal_lsn']) / new_facts, 1),
            'raw_object_bytes_per_row': round(raw / rows_sent, 1),
            'evidence_object_bytes_per_row': round((sum(objects.values()) - raw) / rows_sent, 1),
            'object_bytes_by_codec': objects,
            'ingest_rows_per_second_single_process': round(rows_sent / ingest_seconds, 1),
            'receive_seconds_per_batch_p95': round(sorted(receive_seconds)[max(0, math.ceil(0.95 * len(receive_seconds)) - 1)], 3),
            'batch_rows': batch_rows, 'verify_on_read': verify_throughput(installation),
        }
        return result
    finally:
        installation.stop()
        if not keep:
            shutil.rmtree(Path(scratch) / 'calibration', ignore_errors=True)


def host_capacity(path):
    import platform
    import psutil
    path = Path(path)
    probe = path if path.exists() else path.parent
    while not probe.exists():
        probe = probe.parent
    usage = shutil.disk_usage(probe)
    return {'path': str(path), 'free_bytes': usage.free, 'total_bytes': usage.total,
            'memory_bytes': psutil.virtual_memory().total, 'cpus': os.cpu_count(),
            'platform': f'{platform.system()} {platform.release()} {platform.machine()}'}


def project(workload, calibration, *, max_history_days=None, worker_memory_bytes=2 * 2**30, api_memory_bytes=512 * 2**20,
            shared_buffers_bytes=None, workers=2):
    """Projected resources for ``workload`` at its longest history (or ``max_history_days``)."""
    if shared_buffers_bytes is None:                           # the P-LOCAL cluster's own sizing on this host
        from numek_platform.local import tuning
        shared_buffers_bytes = int(tuning()['shared_buffers'].removesuffix('MB')) * 2**20
    days = max_history_days or max(workload.history_days)
    rows = workload.predictions_per_day * days
    # A revision is counted as one new fact (a lower bound; corrections can add occurrences too).
    facts = rows * calibration['facts_per_row'] + workload.revisions_per_day * days
    db = facts * calibration['db_bytes_per_fact']
    wal = facts * calibration['wal_bytes_per_fact']
    evidence = rows * calibration['evidence_object_bytes_per_row']
    raw = workload.predictions_per_day * min(days, RAW_RETENTION_DAYS) * calibration['raw_object_bytes_per_row']
    staging = workload.predictions_per_day * calibration['raw_object_bytes_per_row'] * 2      # one day's batches, twice
    backup = db + evidence                                                                   # raw excluded by default
    from numek_platform.local import WAL_PEAK_BYTES
    wal_peak = WAL_PEAK_BYTES                                  # max_wal_size (P-LOCAL tuning) plus overrun; no archiving
    disk = db + wal_peak + evidence + raw + staging + backup
    memory = shared_buffers_bytes + workers * worker_memory_bytes + 2 * api_memory_bytes
    load_seconds = (rows + workload.revisions_per_day * days) / calibration['ingest_rows_per_second_single_process']
    return {'history_days': days, 'rows': rows, 'facts': round(facts), 'database_bytes': round(db),
            'wal_generated_bytes': round(wal), 'wal_peak_bytes': wal_peak, 'evidence_object_bytes': round(evidence),
            'raw_object_bytes': round(raw), 'staging_bytes': round(staging), 'backup_bytes': round(backup),
            'disk_bytes': round(disk), 'memory_bytes': memory,
            'single_process_load_hours': round(load_seconds / 3600, 2),
            'assumptions': ['a revision adds one fact', 'backups are written to the same disk',
                            f'raw batches are retained {RAW_RETENTION_DAYS} days',
                            f'{workers} worker hosts at {worker_memory_bytes // 2**30} GiB each, two API workers']}


def admit(workload, projection, host):
    reasons = []
    disk_limit = (1 - DISK_RESERVE) * host['free_bytes']
    if projection['disk_bytes'] > disk_limit:
        reasons.append(f"disk: needs {projection['disk_bytes'] / 2**30:.1f} GiB, {disk_limit / 2**30:.1f} GiB usable "
                       f"({host['free_bytes'] / 2**30:.1f} GiB free less a {int(DISK_RESERVE * 100)}% reserve)")
    memory_limit = (1 - MEMORY_RESERVE) * host['memory_bytes']
    if projection['memory_bytes'] > memory_limit:
        reasons.append(f"memory: needs {projection['memory_bytes'] / 2**30:.1f} GiB, {memory_limit / 2**30:.1f} GiB usable")
    return {'workload': workload.id, 'decision': 'admitted' if not reasons else 'not_admitted_on_host', 'reasons': reasons,
            'identity': 'retained' if workload.parent is None else f'smaller named workload of {workload.parent}'}


def preflight(workload_id, scratch, *, calibration=None, calibration_facts=1_000_000):
    workload = WORKLOADS[workload_id]
    started = datetime.now(timezone.utc)
    if calibration is None:
        calibration = calibrate(scratch, workload, facts=calibration_facts)
    host = host_capacity(scratch)
    projection = project(workload, calibration)
    decision = admit(workload, projection, host)
    out = {'schema': 'numek.workload_preflight/1', 'at': started.isoformat(), 'workload_definition': asdict(workload),
           'calibration': calibration, 'host': host, 'projection': projection, **decision}
    out['digest'] = hashlib.sha256(json.dumps(out, sort_keys=True, default=str).encode()).hexdigest()
    return out
