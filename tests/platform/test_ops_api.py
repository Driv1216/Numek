"""CG7 S9: the operations API, its security, OpenAPI, reports, the CLI, the Python client and investigation jobs.

The authorization matrix walks every declared route for every role. A role is refused (403) exactly when it
lacks the route's permission. Other checks:
- sessions: HttpOnly, SameSite=Strict, CSRF on mutation, revocation;
- tokens: they narrow and never widen their principal's roles;
- principals of another organisation are refused;
- the incident report: a shareable projection without identities, a local audience gated by
  ``evidence:protected:read``, HTML and PDF;
- health, readiness and metrics;
- the serving guard;
- worker-host investigation jobs;
- the CLI;
- ``OpsClient`` against a live server.
"""
import json
import os
import subprocess
import sys
import threading
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from monitoring_support import DEFINITION, NS, T0, contract, generate, send, tick  # noqa: E402

DEPLOYMENT = 'scorecard-prod'
APR20 = datetime(2026, 4, 20, tzinfo=timezone.utc)
ROLES = ('viewer', 'operator', 'analyst', 'approver', 'admin', 'reserve_steward')
PASSWORD = 'correct horse battery staple'


@pytest.fixture(scope='module')
def ops(cluster, tmp_path_factory):
    from numek_platform import identity
    from numek_platform.installation import Installation
    from confidenceguard.operations import registry
    from confidenceguard.operations.monitoring import definitions, runtime
    root = Path(tmp_path_factory.mktemp('opsapi')).resolve()
    os.environ['NUMEK_OPS_API_DSN'] = cluster.create_database('api_' + uuid.uuid4().hex[:10], template='numek_template')
    installation = Installation.create(root / 'installation', dsn_env='NUMEK_OPS_API_DSN')
    registry.register_system(installation, 'credit-default', 'Credit default', namespace=NS)
    registry.register_deployment(installation, 'credit-default', DEPLOYMENT, 'Scorecard', tier=1)
    registry.register_source(installation, DEPLOYMENT, 'scorecard-events', contract())
    send(installation, generate(0, 31, 40, error_rate=0.1, seed=1, prefix='r') + generate(31, 28, 40, error_rate=0.1, seed=2)
         + generate(59, 21, 40, error_rate=0.4, seed=3), 'initial')
    inspection = definitions.inspect(installation, DEPLOYMENT, DEFINITION, now_tick=tick(T0 + timedelta(days=31)))
    definitions.confirm(installation, DEPLOYMENT, inspection['version'], inspection['inspection_digest'], actor='test',
                        now_tick=tick(T0 + timedelta(days=30)))
    runtime.monitor_once(installation, DEPLOYMENT, now_tick=tick(APR20))
    with installation.db.transaction() as conn:
        for role in ROLES:
            principal = identity.create_principal(conn, installation.scope, 'user', role)
            identity.set_password(conn, installation.scope, principal, PASSWORD)
            identity.bind_role(conn, installation.scope, principal, role)
    return installation


@pytest.fixture(scope='module')
def app(ops):
    from confidenceguard.operations import api
    application = api.create_app(ops)
    application.testing = True
    return application


def login(app, name):
    client = app.test_client()
    response = client.post('/api/ops/v1/session', json={'name': name, 'password': PASSWORD})
    assert response.status_code == 200, response.get_json()
    return client, response.get_json()['data']['csrf'], response


def _ids(ops):
    with ops.db.connect() as conn:
        incident = conn.execute('SELECT id FROM ops_incidents ORDER BY number LIMIT 1').fetchone()['id']
        condition = conn.execute('SELECT id FROM ops_conditions LIMIT 1').fetchone()['id']
    return incident, condition


def test_sessions_cookies_csrf_and_revocation(app, ops):
    anonymous = app.test_client()
    assert anonymous.get('/api/ops/v1/incidents').status_code == 401
    client, csrf, response = login(app, 'operator')
    cookie = response.headers['Set-Cookie']
    assert 'HttpOnly' in cookie and 'SameSite=Strict' in cookie
    who = client.get('/api/ops/v1/session').get_json()['data']
    assert who['principal']['name'] == 'operator' and 'operate' in who['permissions']
    incident, _condition = _ids(ops)
    refused = client.post(f'/api/ops/v1/incidents/{incident}/assign', json={'owner': 'operator'})
    assert refused.status_code == 403 and refused.get_json()['error']['code'] == 'csrf_failed'
    accepted = client.post(f'/api/ops/v1/incidents/{incident}/assign', json={'owner': 'operator'}, headers={'X-CSRF-Token': csrf})
    assert accepted.status_code == 200
    assert app.test_client().post('/api/ops/v1/session', json={'name': 'operator', 'password': 'wrong'}).status_code == 401
    client.delete('/api/ops/v1/session')
    assert client.get('/api/ops/v1/session').status_code == 401


def test_tokens_narrow_and_other_orgs_are_refused(app, ops):
    from numek_platform import identity
    from numek_platform.scope import create_org
    with ops.db.transaction() as conn:
        analyst = identity.get_principal(conn, ops.scope, conn.execute("SELECT id FROM principals WHERE name = 'analyst' AND org_id = %s",
                                                                       (ops.scope.org_id,)).fetchone()['id'])
        narrow, _ = identity.issue_token(conn, ops.scope, analyst, ['role:viewer'])
        other = create_org(conn, 'other-' + uuid.uuid4().hex[:6])
        stranger = identity.create_principal(conn, other, 'user', 'stranger')
        identity.bind_role(conn, other, stranger, 'admin')
        foreign, _ = identity.issue_token(conn, other, stranger, ['role:admin'])
    client = app.test_client()
    headers = {'Authorization': f'Bearer {narrow}'}
    assert client.get('/api/ops/v1/incidents', headers=headers).status_code == 200
    incident, _ = _ids(ops)
    assert client.post(f'/api/ops/v1/incidents/{incident}/investigations', json={}, headers=headers).status_code == 403
    assert client.get('/api/ops/v1/incidents', headers={'Authorization': f'Bearer {foreign}'}).status_code == 403


def test_openapi_declares_every_route_with_its_permission(app):
    from confidenceguard.operations import api
    spec = app.test_client().get('/api/ops/v1/openapi.json').get_json()
    operations = [(path, method, op['x-permission']) for path, item in spec['paths'].items() for method, op in item.items()]
    assert len(operations) == len(api.ROUTES) >= 40
    assert all(permission in ('read', 'operate', 'analyze', 'intervention:approve', 'admin') for _p, _m, permission in operations)
    assert {'session', 'token'} == set(spec['components']['securitySchemes'])


def test_incident_report_audiences_and_html(app, ops):
    incident, _ = _ids(ops)
    viewer, _csrf, _ = login(app, 'viewer')
    shared = viewer.get(f'/api/ops/v1/incidents/{incident}/report').get_json()['data']
    text = json.dumps(shared)
    assert shared['audience'] == 'shareable' and 'principal:' not in text and str(incident) not in text
    assert shared['ladder'] and shared['recovery']['R4_causal'] == 'not claimed' and shared['report_digest']
    assert viewer.get(f'/api/ops/v1/incidents/{incident}/report?audience=local').status_code == 403
    analyst, _csrf, _ = login(app, 'analyst')
    local = analyst.get(f'/api/ops/v1/incidents/{incident}/report?audience=local').get_json()['data']
    assert local['audience'] == 'local' and local['incident']['id'] == str(incident)
    html = analyst.get(f'/api/ops/v1/incidents/{incident}/report?format=html').get_data(as_text=True)
    assert html.startswith('<!doctype html>') and 'Differential diagnosis' in html and 'No overall reliability score' in html


def test_health_readiness_metrics_and_serving_guard(app):
    from confidenceguard.contracts import EvaluationError
    from confidenceguard.operations import api
    client = app.test_client()
    assert client.get('/healthz').status_code == 200
    ready = client.get('/readyz').get_json()['data']
    assert ready['checks']['database'] == 'ok' and 'controller' in ready['checks']
    metrics = client.get('/metrics').get_data(as_text=True)
    assert 'numek_incidents{state=' in metrics and 'numek_catalog_head_max' in metrics
    with pytest.raises(EvaluationError):
        api.serve_guard('0.0.0.0')
    assert api.serve_guard('0.0.0.0', tls=True) and api.serve_guard('127.0.0.1')


def test_worker_host_runs_investigation_jobs(ops):
    from numek_platform.execution.host import WorkerHost
    from confidenceguard.operations.intelligence import planner
    from confidenceguard.operations.jobs import REGISTRY
    incident, _ = _ids(ops)
    result = planner.plan(ops, incident, now=APR20, only=('monitoring_health_review',))
    run = next(s for s in result['selected'] if s['state'] == 'planned')
    queued = planner.enqueue(ops, uuid.UUID(run['run']))
    host = WorkerHost(ops.db, ops.store.root, registry=REGISTRY, lanes=('investigation',))
    try:
        assert host.step() == 1 and host.wait_idle(300)
    finally:
        host.shutdown()
    with ops.db.connect() as conn:
        state = conn.execute('SELECT state FROM ops_investigation_runs WHERE id = %s', (uuid.UUID(run['run']),)).fetchone()['state']
        job = conn.execute('SELECT state, lane FROM jobs WHERE id = %s', (uuid.UUID(queued['job']),)).fetchone()
    assert state == 'completed' and job['state'] == 'succeeded' and job['lane'] == 'investigation'


def test_cli_administration_and_reports(ops, tmp_path):
    from click.testing import CliRunner
    from confidenceguard.cli import main
    runner = CliRunner()
    root = str(ops.root)
    created = runner.invoke(main, ['ops', 'user', 'create', 'cli-analyst', '--role', 'analyst', '--installation', root], input='a long enough passphrase\n')
    assert created.exit_code == 0, created.output
    service = runner.invoke(main, ['ops', 'user', 'create', 'producer', '--role', 'viewer', '--service', '--installation', root])
    assert service.exit_code == 0
    token = runner.invoke(main, ['ops', 'token', 'issue', 'producer', '--scope', 'ingest:source:scorecard-events', '--installation', root])
    assert token.exit_code == 0 and json.loads(token.output)['token'].startswith('nmk_')
    listed = json.loads(runner.invoke(main, ['ops', 'incidents', '--installation', root]).output)
    assert listed and listed[-1]['number'] == 1
    out = tmp_path / 'incident-1.html'
    written = runner.invoke(main, ['ops', 'report', '1', '--out', str(out), '--json-out', str(tmp_path / 'incident-1.json'),
                                   '--installation', root])
    assert written.exit_code == 0, written.output
    assert out.read_text().startswith('<!doctype html>') and json.loads((tmp_path / 'incident-1.json').read_text())['audience'] == 'shareable'


def test_pdf_report(ops, tmp_path):
    env = {**os.environ, 'DYLD_FALLBACK_LIBRARY_PATH': '/opt/homebrew/lib', 'NUMEK_OPS_API_DSN': os.environ['NUMEK_OPS_API_DSN']}
    probe = subprocess.run([sys.executable, '-c', 'import weasyprint'], env=env, capture_output=True)
    if probe.returncode:
        pytest.skip('WeasyPrint system libraries are not available in this environment')
    out = tmp_path / 'incident-1.pdf'
    done = subprocess.run([sys.executable, '-m', 'confidenceguard.cli', 'ops', 'report', '1', '--out', str(out), '--format', 'pdf',
                           '--installation', str(ops.root)], env=env, capture_output=True, text=True)
    assert done.returncode == 0, done.stderr[-2000:]
    assert out.read_bytes().startswith(b'%PDF') and out.with_suffix('.html').exists()


def test_ops_client_against_a_live_server(app, ops):
    from werkzeug.serving import make_server
    from confidenceguard.operations.client import OpsClient, OpsError
    server = make_server('127.0.0.1', 0, app, threaded=True)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        url = f'http://127.0.0.1:{server.server_port}'
        client = OpsClient(url).login('operator', PASSWORD)
        incidents = client.get('/incidents')['items']
        assert incidents and client.get(f"/incidents/{incidents[0]['id']}")['incident']['number'] == incidents[0]['number']
        assert client.post(f"/incidents/{incidents[0]['id']}/assign", {'owner': 'operator'})['owner'] == 'operator'
        with pytest.raises(OpsError) as caught:
            client.post(f"/incidents/{incidents[0]['id']}/investigations", {})
        assert caught.value.code == 'forbidden' and caught.value.status == 403
        assert '<!doctype html>' in client.report_html(incidents[0]['id'])
    finally:
        server.shutdown()


def _fill(path, ids):
    for name, value in ids.items():
        path = path.replace(f'<{name}>', str(value))
    return path


def test_authorization_matrix_over_every_route(app, ops):
    """For every route and role: 403 exactly when the role lacks the route's permission (empty bodies)."""
    from numek_platform.identity import ROLE_PERMISSIONS
    from confidenceguard.operations import api
    incident, condition = _ids(ops)
    from confidenceguard.operations.intelligence import planner
    with ops.db.connect() as conn:
        row = conn.execute('SELECT id FROM ops_investigation_runs LIMIT 1').fetchone()
    run = row['id'] if row else planner.plan(ops, incident, now=APR20)['selected'][0]['run']
    from confidenceguard.operations.interventions import proposals
    draft = proposals.create(ops, incident, 'monitoring_fix', author='principal:analyst', title='matrix', change={'action': 'x'},
                             verification_plan={'claims': [{'id': 'ops', 'claim': 'R1'}]})
    from numek_platform import identity
    with ops.db.transaction() as conn:                 # throwaway targets: admin calls with empty bodies must not touch fixtures
        spare = identity.create_principal(conn, ops.scope, 'user', 'matrix-spare-' + uuid.uuid4().hex[:6])
        _secret, spare_token = identity.issue_token(conn, ops.scope, spare, ['role:viewer'])
    ids = {'deployment': DEPLOYMENT, 'system': 'credit-default', 'incident': incident, 'condition': condition, 'run': run,
           'proposal': draft['id'], 'version': 1, 'principal': spare.id, 'token': spare_token, 'entry': uuid.uuid4()}
    clients = {role: login(app, role) for role in ROLES}
    mismatches, checked = [], 0
    for route in api.ROUTES:
        path = '/api/ops/v1' + _fill(route['path'], ids)
        for role, (client, csrf, _) in clients.items():
            if route['method'] == 'GET':
                response = client.get(path)
            else:
                response = client.post(path, json={}, headers={'X-CSRF-Token': csrf})
            allowed = route['permission'] in ROLE_PERMISSIONS[role]
            body = response.get_json(silent=True, force=True) or {}
            code = (body.get('error') or {}).get('code')
            if not allowed and not (response.status_code == 403 and code == 'forbidden'):
                mismatches.append(('should refuse', route['method'], route['path'], role, response.status_code, code))
            if allowed and code == 'forbidden':
                mismatches.append(('should allow', route['method'], route['path'], role, response.status_code, code))
            checked += 1
    assert mismatches == [] and checked == len(api.ROUTES) * len(ROLES)


def test_sources_funnel_and_cross_incident_lists(app, ops):
    """Console step 3 reads: the source funnel reconciles, quarantine shows reasons and field names but never values, and
    investigations and proposals are listed across incidents."""
    from confidenceguard.operations import ingest
    from monitoring_support import body
    rows = generate(80, 1, 6, error_rate=0.1, seed=9, prefix='q')
    rows[0] = {**rows[0], 'p': '1.7', 'entity': 'SENTINEL-ENTITY-VALUE'}
    rows[1] = {**rows[1], 'y': '2'}
    ingest.receive(ops, 'scorecard-events', 'step3-invalid', body(rows))
    ingest.receive(ops, 'scorecard-events', 'step3-resend', body(rows[2:]))
    ingest.process_pending(ops)
    viewer, _csrf, _ = login(app, 'viewer')
    view = viewer.get(f'/api/ops/v1/deployments/{DEPLOYMENT}/sources').get_json()['data']
    assert 'SENTINEL-ENTITY-VALUE' not in json.dumps(view) and '1.7' not in json.dumps(view['sources'][0]['quarantine_reasons'])
    source = view['sources'][0]
    funnel = source['funnel']
    assert source['source'] == 'scorecard-events' and funnel['reconciled']
    assert funnel['rows_received'] == funnel['rows_accepted'] + funnel['rows_quarantined'] and funnel['rows_quarantined'] >= 2
    assert funnel['facts_duplicate'] > 0                                      # the resend's facts were already held
    reasons = {q['reason']: q for q in source['quarantine_reasons']}
    assert reasons and all(q['rows'] >= 1 for q in reasons.values())
    assert {'p', 'y'} <= {f for q in reasons.values() for f in (q['fields'] or [])}
    assert {b['batch_id'] for b in source['batches']} >= {'step3-invalid', 'step3-resend'}
    assert all('watermark_at_receipt' not in b['counts'] for b in source['batches'])
    assert set(source['fields']['p']) <= {'type', 'required', 'identity', 'probability'}
    runs = viewer.get('/api/ops/v1/investigations').get_json()['data']['items']
    props = viewer.get('/api/ops/v1/proposals').get_json()['data']['items']
    assert runs and all(r['incident_number'] >= 1 and r['deployment_id'] == DEPLOYMENT for r in runs)
    assert props and all('evidence' not in p and isinstance(p['evidence_basis'], list) for p in props)


def test_admin_principals_tokens_egress_retention_and_audit(app, ops, tmp_path):
    """Console step 4 administration: secrets are shown once and never listed; every change is audited; the last
    administrator cannot be removed; disabling revokes sessions and tokens; the audit chain verifies against anchors."""
    from numek_platform import audit
    admin, csrf, _ = login(app, 'admin')
    post = lambda path, body: admin.post('/api/ops/v1' + path, json=body, headers={'X-CSRF-Token': csrf})
    created = post('/principals', {'kind': 'user', 'name': 'carol', 'roles': ['viewer']}).get_json()['data']
    assert created['initial_password'] and len(created['initial_password']) >= 12
    carol = app.test_client()
    assert carol.post('/api/ops/v1/session', json={'name': 'carol', 'password': created['initial_password']}).status_code == 200
    listing = admin.get('/api/ops/v1/principals').get_json()['data']
    assert created['initial_password'] not in json.dumps(listing)
    row = next(p for p in listing['items'] if p['name'] == 'carol')
    assert row['has_password'] and row['roles'] == [{'role': 'viewer', 'scope_kind': 'org', 'scope_id': ''}]
    assert post(f"/principals/{created['principal']}/roles", {'action': 'bind', 'role': 'operator', 'scope_kind': 'deployment',
                                                              'scope_id': DEPLOYMENT}).status_code == 200
    service = post('/principals', {'kind': 'service', 'name': 'feeder', 'roles': []}).get_json()['data']
    assert service['initial_password'] is None
    refused = post(f"/principals/{service['principal']}/roles", {'action': 'bind', 'role': 'approver'})
    assert refused.status_code == 403 and refused.get_json()['error']['code'] == 'separation_of_duties'
    issued = post('/tokens', {'principal': service['principal'], 'scopes': ['ingest:source:scorecard-events'], 'expires_in_days': 30}).get_json()['data']
    assert issued['token'].startswith('nmk_') and issued['token'] not in json.dumps(admin.get('/api/ops/v1/tokens').get_json())
    assert post(f"/tokens/{issued['id']}/revoke", {}).get_json()['data']['revoked']
    assert next(t for t in admin.get('/api/ops/v1/tokens').get_json()['data']['items'] if t['id'] == issued['id'])['revoked_at']
    # Disabling revokes the live session; the only administrator cannot remove itself.
    assert post(f"/principals/{created['principal']}/disable", {'disabled': True}).status_code == 200
    assert carol.get('/api/ops/v1/session').status_code == 401
    me = next(p for p in admin.get('/api/ops/v1/principals').get_json()['data']['items'] if p['name'] == 'admin')
    assert post(f"/principals/{me['id']}/disable", {'disabled': True}).get_json()['error']['code'] == 'self_lockout'
    assert post(f"/principals/{me['id']}/roles", {'action': 'unbind', 'role': 'admin'}).get_json()['error']['code'] == 'self_lockout'
    # Egress entries validate; retention lists pins; channels never expose credentials.
    assert post('/egress', {'scheme': 'https', 'host': 'hooks.example.test', 'cidr': '203.0.113.0/24'}).get_json()['data']['port'] == 443
    assert post('/egress', {'scheme': 'ftp', 'host': 'x'}).get_json()['error']['code'] == 'invalid_egress'
    assert post('/egress', {'scheme': 'https', 'host': 'x.test', 'cidr': '10.0.0.1/8'}).get_json()['error']['code'] == 'invalid_egress'
    entries = admin.get('/api/ops/v1/egress').get_json()['data']['items']
    assert post(f"/egress/{entries[0]['id']}/remove", {}).get_json()['data']['removed']
    retention = admin.get('/api/ops/v1/systems/credit-default/retention').get_json()['data']
    assert retention['observation_days'] >= 30 and isinstance(retention['pins'], list)
    channels = admin.get('/api/ops/v1/channels').get_json()['data']
    assert all('secret_name' not in c for c in channels['channels'])
    # Own password change: wrong current refused; success revokes other sessions only.
    viewer, vcsrf, _ = login(app, 'viewer')
    other, _ocsrf, _ = login(app, 'viewer')
    change = lambda current, new: viewer.post('/api/ops/v1/session/password', json={'current': current, 'new': new}, headers={'X-CSRF-Token': vcsrf})
    assert change('wrong password value', 'another long password').status_code == 403
    assert change(PASSWORD, 'another long password').status_code == 200
    assert viewer.get('/api/ops/v1/session').status_code == 200 and other.get('/api/ops/v1/session').status_code == 401
    assert change('another long password', PASSWORD).status_code == 200
    # Every change above is in the chain, and the chain verifies against an exported anchor.
    actions = {e['action'] for e in admin.get('/api/ops/v1/audit?limit=200').get_json()['data']['items']}
    assert {'principal.create', 'principal.role.bind', 'token.issue', 'token.revoke', 'principal.disable', 'egress.allow',
            'egress.remove', 'principal.password.change'} <= actions
    sink = tmp_path / 'anchors.jsonl'
    with ops.db.transaction() as conn:
        audit.export_anchor(conn, ops.scope, str(sink))
    verified = post('/audit/verify', {}).get_json()['data']
    assert verified['chain_ok'] and verified['anchors_ok'] and verified['anchors'] and verified['entries'] >= 8
    from click.testing import CliRunner
    from confidenceguard.operations.cli import ops as ops_cli
    result = CliRunner().invoke(ops_cli, ['audit', 'verify', '--installation', str(ops.root), '--sink', str(sink)])
    assert result.exit_code == 0 and '"ok": true' in result.output
