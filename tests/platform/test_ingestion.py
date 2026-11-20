"""CG7 S4 ingestion: durable encrypted receipt, processing, quarantine, reserve assignment, watermarks,
directory pull, the HTTP surface, the SDK, identity standings, retention and recovery."""
import base64
import csv
import io
import json
import threading
from pathlib import Path

import pytest

from confidenceguard.contracts import EvaluationError, digest

NS = 'credit'
FIELDS = ['id', 'entity', 'when', 'y', 'p', 'available', 'due', 'group', 'model_version']


def contract(fmt='csv'):
    return {
        'format': fmt,
        'event_time': 'when',
        'identity': {'model_version': 'model_version'},
        'fields': {
            'id': {'type': 'string', 'identity': True},
            'entity': {'type': 'string', 'required': True},
            'when': {'type': 'timestamp', 'required': True},
            'y': {'type': 'string', 'vocabulary': ['0', '1']},
            'p': {'type': 'number', 'required': True, 'probability': True},
            'available': {'type': 'timestamp'},
            'due': {'type': 'timestamp'},
            'group': {'type': 'string', 'vocabulary': ['a', 'b']},
            'model_version': {'type': 'string'},
        },
        'batch': {
            'namespace': NS, 'outcome_definition_version': 'outcome-v1', 'bindings': [{'run': 'base'}],
            'evaluation': {
                'task': {'kind': 'binary_classification', 'outcome_definition': 'Default', 'classes': ['0', '1'],
                         'positive_class': '1'},
                'sources': [{'id': 'rows'}],
                'runs': [{'id': 'base', 'source': 'rows', 'model': {'id': 'scorecard', 'version': '1'}, 'key_columns': ['id'],
                          'entity_columns': ['entity'], 'prediction_at': {'column': 'when'},
                          'probabilities': {'positive_column': 'p'},
                          'decision': {'rule': 'probability_threshold', 'threshold': .5}, 'role': 'production'}],
                'outcomes': {'source': 'rows', 'column': 'y', 'key_columns': ['id'], 'available_at': {'column': 'available'},
                             'due_at': {'column': 'due'}}}},
    }


def rows(start=0, count=12, *, version='v1', month='01', p=None):
    out = []
    for i in range(start, start + count):
        out.append({'id': str(i), 'entity': f'entity-{i}', 'when': f'2026-{month}-10T00:00:00Z', 'y': str(i % 2),
                    'p': p if p is not None else ('.8' if i % 2 else '.2'), 'available': '2026-03-01T00:00:00Z',
                    'due': '2026-02-28T00:00:00Z', 'group': 'a' if i % 3 else 'b', 'model_version': version})
    return out


def body(values, extra=None):
    out = io.StringIO()
    fields = FIELDS + list(extra or ())
    writer = csv.DictWriter(out, fieldnames=fields, lineterminator='\n')
    writer.writeheader()
    for value in values:
        writer.writerow({k: value.get(k, '') for k in fields})
    return out.getvalue().encode()


@pytest.fixture
def ops(platform, monkeypatch, tmp_path):
    from confidenceguard.operations import registry
    from numek_platform.installation import Installation
    monkeypatch.setenv('NUMEK_OPS_TEST_DSN', platform.db.dsn)
    installation = Installation.create(Path(tmp_path).resolve() / 'installation', dsn_env='NUMEK_OPS_TEST_DSN')
    registry.register_system(installation, 'credit-default', 'Credit default 90d', namespace=NS)
    registry.register_deployment(installation, 'credit-default', 'scorecard-prod', 'Scorecard (production)', tier=1,
                                 registered_identity={'model_version': 'v1'})
    registry.register_source(installation, 'scorecard-prod', 'scorecard-events', contract())
    return installation


def test_receive_is_durable_encrypted_and_idempotent(ops):
    from confidenceguard.operations import ingest
    data = body(rows())
    receipt = ingest.receive(ops, 'scorecard-events', 'b-1', data)
    assert receipt['state'] == 'received' and receipt['acknowledged'] and receipt['raw_sha256'] == __import__('hashlib').sha256(data).hexdigest()
    assert ingest.receive(ops, 'scorecard-events', 'b-1', data) == receipt                  # identical retry
    with pytest.raises(EvaluationError) as caught:
        ingest.receive(ops, 'scorecard-events', 'b-1', data + b'\n')
    assert caught.value.code == 'batch_conflict'
    with ops.db.connect() as conn:
        obj = conn.execute("SELECT o.* FROM objects o JOIN ops_batches b ON b.raw_object = o.id WHERE b.batch_id = 'b-1'").fetchone()
        job = conn.execute("SELECT state FROM jobs WHERE idempotency_key = %s", (f"ops-batch:{receipt['batch']}",)).fetchone()
    assert obj['codec'] == 'encrypted_raw_batch_v1' and obj['key_id'] is not None and obj['retained_for_recovery']
    stored = (ops.store.root / obj['physical_key']).read_bytes()
    assert b'entity-3' not in stored and bytes(obj['sha256']) != bytes.fromhex(receipt['raw_sha256'])   # names reveal nothing
    assert job['state'] == 'queued'                                                          # acknowledged => will be processed


def test_processing_publishes_minimizes_and_quarantines_with_a_reconciled_funnel(ops):
    from confidenceguard.operations import ingest, registry
    good = rows(count=12)
    bad = [dict(good[0], id='90', p='1.7'), dict(good[1], id='91', entity=''), dict(good[2], id='92', group='z')]
    data = body([dict(r, ssn=f'SSN-{i:04d}') for i, r in enumerate(good + bad)], extra=['ssn'])
    ingest.receive(ops, 'scorecard-events', 'b-1', data)
    result = ingest.process_pending(ops)[0]
    assert result['state'] == 'published' and result['catalog_sequence'] == 1
    counts = result['counts']
    assert (counts['rows_received'], counts['rows_accepted'], counts['rows_quarantined']) == (15, 12, 3)
    assert counts['fields_dropped'] == {'ssn': 15} and counts['facts_new'] > 0
    assert result['quarantine_reasons'] == {'invalid_probability': 1, 'missing_required': 1, 'outside_vocabulary': 1}
    assert ingest.funnel(ops, 'scorecard-events')['reconciled']
    ws = registry.workspace(ops, 'credit-default')
    assert ws.status()['facts']['prediction'] == 12
    retained = json.dumps([f for kind in ('opportunity', 'prediction', 'context') for f in ws.catalog.iter_facts(kind)])
    assert 'SSN-' not in retained                                                             # minimized before storage
    with ops.db.connect() as conn:
        quarantine = conn.execute('SELECT ordinal, reasons, fields, rows_object FROM ops_quarantine ORDER BY ordinal').fetchall()
        obj = conn.execute('SELECT physical_key, sha256, bytes FROM objects WHERE id = %s', (quarantine[0]['rows_object'],)).fetchone()
    assert [q['ordinal'] for q in quarantine] == [12, 13, 14] and quarantine[0]['fields'] == ['p']
    envelope = ops.store.read_verified(obj['physical_key'], bytes(obj['sha256']).hex(), obj['bytes'])
    assert b'1.7' not in envelope                                                             # quarantined rows are encrypted
    kept = [json.loads(l) for l in ops.data_keys.decrypt(ops.scope, envelope, ingest._aad('scorecard-events', 'b-1')).splitlines()]
    assert kept[0]['row']['p'] == '1.7' and 'ssn' not in kept[0]['row']                       # minimized there too
    analysis = ws.analyze({'namespace': NS, 'variants': [ws.models()[0]['id']], 'as_of': '2026-03-02T00:00:00Z',
                           'windows': [{'id': 'jan', 'start': '2026-01-01T00:00:00Z', 'end': '2026-02-01T00:00:00Z'}]})
    assert analysis.data['history']['window_coverage'][0]['selected_predictions'] == 12      # CG3 runs on ingested evidence


def test_conflicting_resend_is_quarantined_per_fact_not_per_batch(ops):
    from confidenceguard.operations import ingest
    ingest.receive(ops, 'scorecard-events', 'b-1', body(rows(count=6)))
    ingest.process_pending(ops)
    changed = rows(count=6)
    changed[0]['p'] = '.55'                                                     # same identity, different prediction
    ingest.receive(ops, 'scorecard-events', 'b-2', body(changed + rows(start=6, count=4)))
    result = ingest.process_pending(ops)[0]
    assert result['state'] == 'published' and result['counts']['facts_quarantined'] >= 1
    assert result['quarantine_reasons'].get('historical_identity_conflict', 0) >= 1
    assert result['counts']['facts_new'] > 0                                    # the new rows still published


def test_processing_and_receipt_are_crash_safe_and_idempotent(ops, monkeypatch):
    from confidenceguard.operations import ingest, registry
    from numek_platform.evidence.gc import GarbageCollector
    import datetime as dt
    monkeypatch.setattr(ingest, 'fault', lambda name: (_ for _ in ()).throw(RuntimeError(name)) if name == 'raw_durable' else None)
    with pytest.raises(RuntimeError):
        ingest.receive(ops, 'scorecard-events', 'lost', body(rows()))
    with ops.db.connect() as conn:
        assert conn.execute("SELECT count(*) AS n FROM ops_batches WHERE batch_id = 'lost'").fetchone()['n'] == 0
    with ops.db.transaction() as conn:                                          # the dead attempt's job is over
        conn.execute("UPDATE jobs SET state = 'failed' WHERE kind = 'ops_receive' AND state = 'running'")
    report = GarbageCollector(ops.db, ops.store, pending_ttl=dt.timedelta(0)).run_once()
    assert report['reclaimed'] >= 1                                             # the orphan raw object is reclaimed
    monkeypatch.setattr(ingest, 'fault', lambda name: (_ for _ in ()).throw(RuntimeError(name)) if name == 'published' else None)
    ingest.receive(ops, 'scorecard-events', 'b-1', body(rows()))
    with pytest.raises(RuntimeError):
        ingest.process_pending(ops)
    monkeypatch.setattr(ingest, 'fault', lambda name: None)
    result = ingest.process_pending(ops)[0]                                     # the retry finds the publication
    ws = registry.workspace(ops, 'credit-default')
    assert result['state'] == 'published' and result['catalog_sequence'] == 1 and ws.status()['catalog_sequence'] == 1


def test_entities_are_assigned_to_the_reserve_at_publication(ops):
    from confidenceguard.operations import ingest, registry
    from numek_platform.governance import reserve as reserves
    ingest.receive(ops, 'scorecard-events', 'b-1', body(rows(count=6)))
    ingest.process_pending(ops)
    catalog_id = registry.system(ops, 'credit-default')['catalog_id']
    reserves.create_reserve(ops.db, ops.secrets, ops.scope, catalog_id, NS, actor='test', fraction='0.5')
    ingest.receive(ops, 'scorecard-events', 'b-2', body(rows(start=0, count=40, month='02')))
    ingest.process_pending(ops)
    with ops.db.connect() as conn:
        states = {bytes(r['unit_hash']).hex(): r['reserve_state'] for r in conn.execute(
            'SELECT unit_hash, reserve_state FROM entity_registry WHERE catalog_id = %s', (catalog_id,))}
    unit = lambda i: digest([NS, json.dumps([f'entity-{i}'], separators=(',', ':'))])     # normalized entity key tuple
    early = {unit(i) for i in range(6)}
    late = {unit(i) for i in range(6, 40)}
    assert {states[u] for u in early} == {'pre_reserve'}                         # first seen before the reserve
    assert {states[u] for u in late} == {'reserve', 'non_reserve'}               # assigned at first sight


def test_watermarks_lateness_and_window_closure(ops):
    from confidenceguard.operations import ingest
    assert ingest.declare_watermark(ops, 'scorecard-events', '2026-01-31T00:00:00Z')['through_tick'] > 0
    assert ingest.declare_watermark(ops, 'scorecard-events', '2026-01-01T00:00:00Z')['regression_ignored']
    ingest.receive(ops, 'scorecard-events', 'late', body(rows(count=4, month='01') + rows(start=4, count=2, month='02')))
    assert ingest.process_pending(ops)[0]['counts']['late_rows'] == 4
    jan = ingest.window_closure(ops, 'scorecard-events', '2026-01-01T00:00:00Z', '2026-01-31T00:00:00Z', allowed_lateness_ns=0,
                                now_tick='2026-01-31T00:00:00Z')
    feb = ingest.window_closure(ops, 'scorecard-events', '2026-02-01T00:00:00Z', '2026-03-01T00:00:00Z',
                                allowed_lateness_ns=86400 * 10**9, now_tick='2026-03-01T12:00:00Z')
    later = ingest.window_closure(ops, 'scorecard-events', '2026-02-01T00:00:00Z', '2026-03-01T00:00:00Z',
                                  allowed_lateness_ns=86400 * 10**9, now_tick='2026-03-03T00:00:00Z')
    assert (jan['standing'], feb['standing'], later['standing']) == ('producer_declared_complete', 'open',
                                                                     'assumed_complete_after_lateness')


def test_directory_pull_receives_new_and_changed_files_and_never_deletes(ops, tmp_path):
    from confidenceguard.operations import ingest
    drop = Path(tmp_path).resolve() / 'drop'
    drop.mkdir()
    (drop / 'one.csv').write_bytes(body(rows(count=3)))
    (drop / 'notes.txt').write_text('ignored')
    assert len(ingest.pull_directory(ops, 'scorecard-events', drop)) == 1
    assert ingest.pull_directory(ops, 'scorecard-events', drop) == []                        # unchanged: nothing new
    (drop / 'one.csv').write_bytes(body(rows(count=4)))                                     # changed content: a new batch
    (drop / 'two.csv').write_bytes(body(rows(start=10, count=2)))
    assert len(ingest.pull_directory(ops, 'scorecard-events', drop)) == 2
    assert sorted(p.name for p in drop.iterdir()) == ['notes.txt', 'one.csv', 'two.csv']   # never deletes
    processed = Path(tmp_path).resolve() / 'processed'
    (drop / 'three.csv').write_bytes(body(rows(start=20, count=2)))
    ingest.pull_directory(ops, 'scorecard-events', drop, processed=processed)
    assert (processed / 'three.csv').exists() and not (drop / 'three.csv').exists()       # moved, never deleted


def test_http_surface_authenticates_scopes_and_maps_errors(ops, monkeypatch):
    from confidenceguard.operations import ingest, registry
    from confidenceguard.operations.web import create_app
    registry.register_source(ops, 'scorecard-prod', 'other-events', contract())
    token = registry.issue_ingest_token(ops, 'scorecard-events')['token']
    other = registry.issue_ingest_token(ops, 'other-events')['token']
    client = create_app(ops).test_client()
    url = '/api/ops/v1/sources/scorecard-events/batches'
    data = body(rows(count=3))
    assert client.post(url, data=data, headers={'Numek-Batch-Id': 'x'}).status_code == 401
    assert client.post(url, data=data, headers={'Authorization': f'Bearer {other}', 'Numek-Batch-Id': 'x'}).status_code == 403
    headers = {'Authorization': f'Bearer {token}', 'Numek-Batch-Id': 'h-1', 'Numek-Declared-Identity': json.dumps({'model_version': 'v1'})}
    accepted = client.post(url, data=data, headers=headers)
    assert accepted.status_code == 202 and accepted.json['data']['state'] == 'received'
    assert client.post(url, data=data + b'\n', headers=headers).status_code == 409
    ingest.process_pending(ops)
    status = client.get(url + '/h-1', headers={'Authorization': f'Bearer {token}'})
    assert status.status_code == 200 and status.json['data']['state'] == 'published'
    assert client.post('/api/ops/v1/sources/scorecard-events/watermark', json={'through': '2026-01-31T00:00:00Z'},
                       headers={'Authorization': f'Bearer {token}'}).status_code == 200
    events = '/api/ops/v1/deployments/scorecard-prod/events'
    assert client.post(events, json={'kind': 'model_change', 'at': '2026-01-15T00:00:00Z'},
                       headers={'Authorization': f'Bearer {token}'}).status_code == 403                # source token: no
    from numek_platform import identity
    with ops.db.transaction() as conn:
        principal = identity.create_principal(conn, ops.scope, 'service', 'serving-system')
        deployment_token, _ = identity.issue_token(conn, ops.scope, principal, ['ingest:deployment:scorecard-prod'])
    assert client.post(events, json={'kind': 'model_change', 'at': '2026-01-15T00:00:00Z', 'identity': {'model_version': 'v2'}},
                       headers={'Authorization': f'Bearer {deployment_token}'}).status_code == 200
    monkeypatch.setattr(ingest, 'MAX_PENDING_BATCHES', 0)
    busy = client.post(url, data=data, headers=dict(headers, **{'Numek-Batch-Id': 'h-2'}))
    assert busy.status_code == 429 and busy.headers['Retry-After']


def _serve(app):
    from werkzeug.serving import make_server
    server = make_server('127.0.0.1', 0, app, threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, f'http://127.0.0.1:{server.server_port}'


def test_sdk_buffers_durably_delivers_at_least_once_and_reports_known_loss(ops, tmp_path):
    from confidenceguard.operations import ingest, registry
    from confidenceguard.operations.web import create_app
    from numek_monitor import Monitor
    registry.register_source(ops, 'scorecard-prod', 'sdk-events', contract('jsonl'))
    token = registry.issue_ingest_token(ops, 'sdk-events')['token']
    server, url = _serve(create_app(ops))
    buffer_dir = Path(tmp_path).resolve() / 'sdk-buffer'
    try:
        crashed = Monitor(url, 'sdk-events', token, buffer_dir, batch_rows=1000, start=False, max_buffer_bytes=4096)
        states = [crashed.log(r) for r in rows(count=40)]
        assert set(states) == {'buffered_disk', 'dropped'} and states.count('dropped') > 0
        dropped = states.count('dropped')
        crashed._commit()                                       # group commit; then the process "dies" without flushing
        monitor = Monitor(url, 'sdk-events', token, buffer_dir, max_buffer_bytes=4096)      # a new process recovers
        assert monitor.flush(30) and monitor.stats()['acknowledged_rows'] == 40 - dropped
        monitor.log(rows(start=100, count=1)[0])
        assert monitor.close(30)
        buffer_id = json.loads((buffer_dir / 'state.json').read_text())['buffer_id']
        first = ingest.status(ops, 'sdk-events', f'sdk:{buffer_id}:1')                  # the recovered batch kept its id
        kept = rows(count=40)[:40 - dropped]
        original = b''.join((json.dumps(r, separators=(',', ':'), sort_keys=True) + '\n').encode() for r in kept)
        assert monitor._post(1, original, dropped) == 202                               # a lost response, resent:
        assert ingest.status(ops, 'sdk-events', f'sdk:{buffer_id}:1')['batch'] == first['batch']   # recognised, not duplicated
        with ops.db.connect() as conn:
            reported = conn.execute("SELECT sum(producer_dropped) AS n FROM ops_batches WHERE source_id = 'sdk-events'").fetchone()['n']
        assert reported == dropped                                                       # known loss is recorded
        results = ingest.process_pending(ops)
        assert {r['state'] for r in results} == {'published'}
        assert ingest.funnel(ops, 'sdk-events')['rows_received'] == 40 - dropped + 1
    finally:
        server.shutdown()


def test_identity_standings_and_customer_signed_statements(ops, tmp_path):
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
    from confidenceguard.operations import identity, ingest, registry
    from tests.cg6.helpers import execution
    (Path(tmp_path) / 'cg6').mkdir()
    predictor = execution(Path(tmp_path).resolve() / 'cg6', n=12).predictors[0].to_dict()
    signing = Ed25519PrivateKey.generate()
    public = signing.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    registry.register_deployment(ops, 'credit-default', 'scorecard-canary', 'Canary', registered_identity={
        'model_version': 'v1', 'predictor_spec': predictor}, attestation_public_key=base64.b64encode(public).decode())
    registry.register_source(ops, 'scorecard-canary', 'canary-events', contract())
    ingest.receive(ops, 'canary-events', 'b-1', body(rows(count=4, version='v1')))
    ingest.receive(ops, 'canary-events', 'b-2', body(rows(start=4, count=4, version='v2')))
    ingest.process_pending(ops)
    with ops.db.connect() as conn:
        outcomes = [(r['standing'], r['outcome']) for r in conn.execute(
            "SELECT standing, outcome FROM ops_identity_standings WHERE deployment_id = 'scorecard-canary' ORDER BY recorded_at")]
    assert ('registered', 'established') in outcomes and ('registered', 'failed') in outcomes
    compatible = identity.check_spec_compatibility(ops, 'scorecard-canary', 'canary-events')
    assert compatible['outcome'] == 'failed' and compatible['differing']     # classes ['0','1'] vs the predictor's ['no','yes']
    statement = {'deployment': 'scorecard-canary', 'artifact_digest': 'sha256:abc', 'period_start': '2026-01-01T00:00:00Z',
                 'period_end': '2026-02-01T00:00:00Z'}
    signature = signing.sign(identity._canonical(statement))
    assert identity.verify_signed_statement(ops, 'scorecard-canary', statement, signature)['outcome'] == 'established'
    forged = dict(statement, artifact_digest='sha256:other')
    assert identity.verify_signed_statement(ops, 'scorecard-canary', forged, signature)['outcome'] == 'failed'
    logged = [{'id': str(i), 'x': str(i / 300), 'p_no': '0.25', 'p_yes': '0.75'} for i in range(300)]
    consistent = identity.audit_outputs(ops, 'scorecard-canary', logged, key_columns=['id'],
                                        logged_outputs={'probabilities': ['p_no', 'p_yes']}, sample_size=200,
                                        max_mismatch_rate=0.02, scratch=Path(tmp_path) / 'audit-1')
    assert consistent['outcome'] == 'established' and consistent['compared'] == 200 and consistent['mismatches'] == 0
    assert consistent['mismatch_rate_upper_bound'] < 0.02 and 'not attestation' in consistent['qualification']
    logged[3]['p_yes'] = '0.9'
    drifted = identity.audit_outputs(ops, 'scorecard-canary', logged, key_columns=['id'], logged_outputs={'probabilities': ['p_no', 'p_yes']},
                                     sample_size=300, scratch=Path(tmp_path) / 'audit-2')
    assert drifted['outcome'] == 'failed' and drifted['mismatches'] == 1
    latest = identity.standings(ops, 'scorecard-canary')
    assert latest['sampled_output_consistent']['outcome'] == 'failed'
    assert latest['customer_signed_statement_verified']['outcome'] == 'failed'          # the latest statement was forged


def test_retention_tombstones_old_bodies_and_destroys_spent_day_keys(ops):
    from confidenceguard.operations import ingest, retention
    ingest.receive(ops, 'scorecard-events', 'b-1', body(rows(count=3) + [dict(rows(count=1)[0], id='99', p='9')]))
    ingest.receive(ops, 'scorecard-events', 'unprocessed', body(rows(start=50, count=2)))
    ingest.process_batch(ops, ingest.status(ops, 'scorecard-events', 'b-1')['batch'])
    with ops.db.transaction() as conn:
        conn.execute("UPDATE ops_batches SET received_at = now() - interval '8 days'")
        conn.execute("UPDATE objects SET created_at = now() - interval '31 days' WHERE codec = 'encrypted_quarantine_rows_v1'")
        conn.execute("UPDATE ops_raw_keys SET day = day - 40")
    report = retention.sweep(ops)
    assert report['raw_tombstoned'] == 1 and report['quarantine_tombstoned'] == 1         # the unprocessed body is kept
    destroyed = {k['purpose'] for k in report['keys_destroyed_live']}
    assert destroyed == {'quarantine_rows'}                                                # the raw key still protects a live body
    assert 'complete only after every backup' in report['deletion_status']


def test_backup_restores_unprocessed_acknowledged_batches_which_then_process(ops, platform, tmp_path, monkeypatch):
    from confidenceguard.operations import ingest
    from numek_platform.backup import create_backup, restore_backup
    from numek_platform.db import Database
    from numek_platform.installation import Installation
    ingest.receive(ops, 'scorecard-events', 'in-flight', body(rows(count=5)))             # acknowledged, not processed
    destination = Path(tmp_path).resolve() / 'backup'
    manifest = create_backup(ops.db, ops.store, ops.secrets, destination, passphrase='backup secret')
    assert manifest['keys'] >= 1
    name = 'r_' + __import__('uuid').uuid4().hex[:12]
    restored_dsn = platform.cluster.create_database(name)
    monkeypatch.setenv('NUMEK_OPS_RESTORED_DSN', restored_dsn)
    root = Path(tmp_path).resolve() / 'restored'
    root.mkdir(mode=0o700)
    (root / 'installation.json').write_text(json.dumps({**ops.config, 'dsn_env': 'NUMEK_OPS_RESTORED_DSN'}))
    for part in ('objects', 'secrets', 'catalogs'):
        (root / part).mkdir(mode=0o700)
    restored = Installation(root)
    restore_backup(destination, Database(restored_dsn), restored.store, restored.secrets, passphrase='backup secret')
    result = ingest.process_pending(restored)[0]
    assert result['batch_id'] == 'in-flight' and result['state'] == 'published' and result['counts']['rows_accepted'] == 5


def test_worker_host_processes_ingestion_jobs(ops):
    from confidenceguard.operations import ingest
    from confidenceguard.operations.jobs import REGISTRY
    from numek_platform.execution.host import WorkerHost
    ingest.receive(ops, 'scorecard-events', 'b-1', body(rows(count=4)))
    host = WorkerHost(ops.db, ops.store.root, registry=REGISTRY, lanes=('essential',))
    try:
        assert host.step() == 1 and host.wait_idle(120)
    finally:
        host.shutdown()
    assert ingest.status(ops, 'scorecard-events', 'b-1')['state'] == 'published'


def test_raw_values_never_reach_logs(ops, caplog):
    """Log scanner (M.4): received rows, quarantined rows and undeclared fields never appear in any log record."""
    import logging
    from confidenceguard.operations import ingest
    from confidenceguard.operations.web import create_app
    from confidenceguard.operations import registry
    caplog.set_level(logging.DEBUG)
    secret_rows = [dict(r, ssn=f'SENSITIVE-{i:05d}') for i, r in enumerate(rows(count=5) + [dict(rows(count=1)[0], id='77', p='4.2')])]
    token = registry.issue_ingest_token(ops, 'scorecard-events')['token']
    client = create_app(ops).test_client()
    client.post('/api/ops/v1/sources/scorecard-events/batches', data=body(secret_rows, extra=['ssn']),
                headers={'Authorization': f'Bearer {token}', 'Numek-Batch-Id': 'logged'})
    client.post('/api/ops/v1/sources/scorecard-events/batches', data=b'not,a,valid\nbatch',
                headers={'Authorization': f'Bearer {token}', 'Numek-Batch-Id': 'logged'})        # an error path too
    ingest.process_pending(ops)
    text = '\n'.join(r.getMessage() for r in caplog.records)
    assert 'SENSITIVE-' not in text and 'entity-3' not in text and '4.2' not in text
