"""CG7 S10 packaging and workload preflight.

Covers:
- the gunicorn serving options (guard, TLS, trusted proxy, logs without query strings), and a real start, ready and
  graceful stop of ``ops serve``;
- the deployment files: the image installs from a hashed lock and a digest-pinned base, the compose and systemd
  files keep the database password out of the repository;
- the workload registry (W-REF and W-DEV keep their identities; smaller workloads name their parent and deviations)
  and the admission arithmetic, including the 20% disk reserve.
"""
import os
import re
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def test_serving_options_guard_tls_proxy_and_logs():
    from confidenceguard.contracts import EvaluationError
    from confidenceguard.operations import serving
    local = serving.options('127.0.0.1', 8443)
    assert local['worker_class'] == 'gthread' and local['preload_app'] is False and local['bind'] == ['127.0.0.1:8443']
    assert local['forwarded_allow_ips'] == '' and local['secure_scheme_headers'] == {}     # nobody may claim https
    with pytest.raises(EvaluationError) as refused:
        serving.options('0.0.0.0', 8443)
    assert refused.value.code == 'tls_required'
    tls = serving.options('0.0.0.0', 8443, tls_cert='/c.crt', tls_key='/c.key')
    assert tls['certfile'] == '/c.crt' and tls['keyfile'] == '/c.key'
    proxied = serving.options('0.0.0.0', 8443, trusted_proxy=True, proxy_ips='10.0.0.5')
    assert proxied['forwarded_allow_ips'] == '10.0.0.5' and proxied['secure_scheme_headers'] == {'X-FORWARDED-PROTO': 'https'}
    assert serving.options('::1', 9000)['bind'] == ['[::1]:9000']
    assert '%(U)s' in serving.ACCESS_LOG_FORMAT and '%(r)s' not in serving.ACCESS_LOG_FORMAT and '%(q)s' not in serving.ACCESS_LOG_FORMAT
    with pytest.raises(ValueError):
        serving.options('127.0.0.1', 8443, workers=0)


def test_ops_serve_runs_gunicorn_until_sigterm(cluster, tmp_path):
    from numek_platform.installation import Installation
    env_name = 'NUMEK_S10_SERVE_DSN'
    env = {**os.environ, env_name: cluster.create_database('serve_' + uuid.uuid4().hex[:10], template='numek_template'),
           'PYTHONPATH': str(ROOT / 'src'), 'PYTHONDONTWRITEBYTECODE': '1'}
    os.environ[env_name] = env[env_name]
    Installation.create(tmp_path / 'installation', dsn_env=env_name)
    port = 8400 + os.getpid() % 500
    log = tmp_path / 'serve.log'
    proc = subprocess.Popen([sys.executable, '-B', '-m', 'confidenceguard.cli', 'ops', 'serve', '--installation',
                             str(tmp_path / 'installation'), '--port', str(port), '--workers', '2', '--threads', '2'],
                            env=env, stdout=open(log, 'w'), stderr=subprocess.STDOUT)
    try:
        status, started = None, time.monotonic()
        while time.monotonic() - started < 60 and status != 200:
            try:
                with urllib.request.urlopen(f'http://127.0.0.1:{port}/readyz', timeout=2) as r:
                    status = r.status
            except (urllib.error.URLError, OSError):
                time.sleep(0.2)
        assert status == 200
        with pytest.raises(urllib.error.HTTPError) as unauth:
            urllib.request.urlopen(f'http://127.0.0.1:{port}/api/ops/v1/session?token=planted-secret', timeout=2)
        assert unauth.value.code == 401
        workers = subprocess.run(['pgrep', '-P', str(proc.pid)], capture_output=True, text=True).stdout.split()
        assert len(workers) == 2
    finally:
        proc.send_signal(signal.SIGTERM)
        assert proc.wait(timeout=60) == 0
    text = log.read_text()
    assert 'Using worker: gthread' in text and '"path":"/api/ops/v1/session"' in text and 'planted-secret' not in text


def test_deployment_files_pin_inputs_and_keep_secrets_out():
    containerfile = (ROOT / 'deploy/oci/Containerfile').read_text()
    assert re.search(r'ARG PYTHON_IMAGE=python:3\.13\.\d+-slim-\w+@sha256:[0-9a-f]{64}', containerfile)
    assert '--require-hashes -r /tmp/ops.lock' in containerfile and '--no-deps /tmp/wheels/*.whl' in containerfile
    assert 'USER numek' in containerfile and 'NUMEK_DSN' in containerfile
    lock = (ROOT / 'constraints/cg7-ops-linux-x86_64-py313.lock').read_text()
    pins = re.findall(r'^([A-Za-z0-9_.-]+)==([^ \\\n]+)', lock, re.M)
    blocks = re.split(r'\n(?=[A-Za-z0-9_.-]+==)', lock.split('\n', 2)[2])
    assert pins and all('--hash=sha256:' in b for b in blocks if '==' in b)              # every pin is hashed
    assert {'gunicorn', 'psycopg-binary', 'scikit-learn', 'scipy'} <= {name for name, _ in pins}
    assert '--exclude-newer' in lock.split('\n', 2)[1]
    ignore = [line for line in (ROOT / 'deploy/oci/Containerfile.dockerignore').read_text().splitlines()
              if line and not line.startswith('#')]
    assert ignore[0] == '*' and '!src/' in ignore and not any('.env' in line for line in ignore)   # an allowlist
    compose = (ROOT / 'deploy/compose/compose.yaml').read_text()
    assert '${POSTGRES_PASSWORD:?' in compose and 'read_only: true' in compose and '127.0.0.1:8443:8443' in compose
    gitignore = (ROOT / '.gitignore').read_text()
    assert 'deploy/compose/.env' in gitignore and 'deploy/compose/tls/' in gitignore
    for unit in ('numek-ops-api.service', 'numek-ops-controller.service', 'numek-ops-worker@.service'):
        text = (ROOT / 'deploy/systemd' / unit).read_text()
        assert 'EnvironmentFile=/etc/numek/ops.env' in text and 'NoNewPrivileges=yes' in text and 'ReadWritePaths=/var/lib/numek' in text
        assert 'NUMEK_DSN=' not in text                                                    # the DSN lives only in ops.env


def test_workload_identities_and_admission():
    from confidenceguard.operations import workloads
    ref, dev, small = (workloads.WORKLOADS[k] for k in ('W-REF', 'W-DEV', 'W-DEV-S1'))
    assert (ref.systems, ref.deployments, ref.predictions_per_day, ref.revisions_per_day, ref.features, ref.regions,
            ref.policies, ref.history_days) == (3, 20, 2_000_000, 1_000_000, 30, 10, 1, (90,))
    assert (dev.predictions_per_day, dev.revisions_per_day, dev.history_days) == (200_000, 100_000, (30, 60, 90))
    assert dev.parent is None and ref.parent is None
    assert small.parent == 'W-DEV' and small.deviations and small.per_deployment_predictions == dev.per_deployment_predictions
    calibration = {'facts_per_row': 5.0, 'db_bytes_per_fact': 1000.0, 'wal_bytes_per_fact': 2000.0,
                   'evidence_object_bytes_per_row': 4000.0, 'raw_object_bytes_per_row': 300.0,
                   'ingest_rows_per_second_single_process': 100.0}
    host = {'free_bytes': 100 * 2**30, 'memory_bytes': 16 * 2**30}
    projected = workloads.project(small, calibration)
    assert projected['rows'] == 900_000 and projected['facts'] == 4_500_000
    assert projected['database_bytes'] == 4_500_000_000 and projected['single_process_load_hours'] == 2.5
    assert workloads.admit(small, projected, host)['decision'] == 'admitted'
    big = workloads.admit(dev, workloads.project(dev, calibration), host)
    assert big['decision'] == 'not_admitted_on_host' and big['reasons'][0].startswith('disk') and big['identity'] == 'retained'
    # The reserve: a workload needing between 80% and 100% of the free space is refused.
    just_over = dict(host, free_bytes=int(projected['disk_bytes'] / 0.9))
    assert workloads.admit(small, projected, just_over)['decision'] == 'not_admitted_on_host'
    assert workloads.admit(small, projected, dict(host, memory_bytes=2 * 2**30))['reasons'][0].startswith('memory')


def test_synthetic_rows_are_deterministic_and_inside_their_day():
    from confidenceguard.operations import workloads
    a = workloads.rows_for_day(40, 100, 30, seed=3)
    assert a == workloads.rows_for_day(40, 100, 30, seed=3) and a != workloads.rows_for_day(40, 100, 30, seed=4)
    assert len(a) == 100 and all(r['when'].startswith('2026-02-10') for r in a) and len([k for k in a[0] if k.startswith('f')]) == 30
    body = workloads.csv_body(a).decode().splitlines()
    assert len(body) == 101 and body[0].split(',')[:3] == ['id', 'entity', 'when']


def test_local_cluster_tuning_is_bounded_and_preflight_reserves_its_wal():
    from numek_platform.local import MAX_WAL_BYTES, WAL_PEAK_BYTES, tuning
    from confidenceguard.operations import workloads
    assert tuning(4 * 2**30)['shared_buffers'] == '512MB'                       # an eighth of RAM ...
    assert tuning(512 * 2**20)['shared_buffers'] == '128MB'                     # ... never below the default
    assert tuning(256 * 2**30)['shared_buffers'] == '2048MB'                    # ... nor above 2 GB
    assert tuning()['max_wal_size'] == f'{MAX_WAL_BYTES // 2**20}MB' and tuning()['checkpoint_timeout'] == '15min'
    calibration = {'facts_per_row': 5, 'db_bytes_per_fact': 1400, 'wal_bytes_per_fact': 2000,
                   'evidence_object_bytes_per_row': 5800, 'raw_object_bytes_per_row': 320,
                   'ingest_rows_per_second_single_process': 1000}
    projection = workloads.project(workloads.WORKLOADS['W-DEV-S1'], calibration)
    assert projection['wal_peak_bytes'] == WAL_PEAK_BYTES > MAX_WAL_BYTES


def test_point_lookups_is_scoped_to_its_block(cluster):
    from numek_platform.db import Database, point_lookups
    from numek_platform.errors import PlatformError
    db = Database(cluster.dsn())
    with db.connect() as conn:
        with pytest.raises(PlatformError):                                       # outside a transaction: refused
            with point_lookups(conn):
                pass
        with conn.transaction():
            with point_lookups(conn):
                assert conn.execute("SELECT current_setting('enable_hashjoin') AS h").fetchone()['h'] == 'off'
                assert conn.execute("SELECT current_setting('enable_mergejoin') AS m").fetchone()['m'] == 'off'
            # the rest of the transaction plans as usual
            assert conn.execute("SELECT current_setting('enable_hashjoin') AS h").fetchone()['h'] == 'on'
        assert conn.execute("SELECT current_setting('enable_mergejoin') AS m").fetchone()['m'] == 'on'
