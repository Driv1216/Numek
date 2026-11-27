"""CG7 S6: conditions, incidents, dossiers and knowledge revisions, notifications, controller tasks, retention pins,
and backup and restore of operations state. Runs on a real installation fed by S4 ingestion and S5 monitoring,
in simulated time."""
import hashlib
import hmac
import json
import os
import socketserver
import threading
import uuid
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

from confidenceguard.contracts import EvaluationError
from monitoring_support import DEFINITION, NS, T0, contract, generate, send, tick  # noqa: E402

DEPLOYMENT = 'scorecard-prod'
APR20 = datetime(2026, 4, 20, tzinfo=timezone.utc)


class Hook(BaseHTTPRequestHandler):
    received = []
    status = 200

    def do_POST(self):
        body = self.rfile.read(int(self.headers['Content-Length']))
        Hook.received.append({'headers': dict(self.headers), 'body': body})
        self.send_response(Hook.status)
        self.end_headers()

    def log_message(self, *args):
        pass


class Mail(socketserver.StreamRequestHandler):
    messages = []

    def handle(self):
        self.wfile.write(b'220 test\r\n')
        data = False
        lines = []
        while True:
            line = self.rfile.readline()
            if not line:
                return
            if data:
                if line == b'.\r\n':
                    Mail.messages.append(b''.join(lines))
                    data = False
                    self.wfile.write(b'250 ok\r\n')
                else:
                    lines.append(line)
                continue
            verb = line[:4].upper()
            if verb in (b'EHLO', b'HELO'):
                self.wfile.write(b'250 test\r\n')
            elif verb == b'DATA':
                data = True
                self.wfile.write(b'354 go\r\n')
            elif verb == b'QUIT':
                self.wfile.write(b'221 bye\r\n')
                return
            else:
                self.wfile.write(b'250 ok\r\n')


def _allow(installation, scheme, port):
    with installation.db.transaction() as conn:
        conn.execute("INSERT INTO egress_allowlist(org_id, id, scheme, host, port, cidr) VALUES (%s, %s, %s, '127.0.0.1', %s, '127.0.0.1/32')",
                     (installation.scope.org_id, uuid.uuid4(), scheme, port))


@pytest.fixture(scope='module')
def ops(cluster, tmp_path_factory):
    from numek_platform.installation import Installation
    from confidenceguard.operations import registry
    from confidenceguard.operations.incidents import notify
    from confidenceguard.operations.monitoring import definitions
    root = Path(tmp_path_factory.mktemp('incidents')).resolve()
    os.environ['NUMEK_OPS_INCIDENTS_DSN'] = cluster.create_database('ops_' + uuid.uuid4().hex[:10], template='numek_template')
    installation = Installation.create(root / 'installation', dsn_env='NUMEK_OPS_INCIDENTS_DSN')
    registry.register_system(installation, 'credit-default', 'Credit default', namespace=NS)
    registry.register_deployment(installation, 'credit-default', DEPLOYMENT, 'Scorecard', tier=1)
    registry.register_source(installation, DEPLOYMENT, 'scorecard-events', contract())
    send(installation, generate(0, 31, 40, error_rate=0.1, seed=1, prefix='r') + generate(31, 28, 40, error_rate=0.1, seed=2)
         + generate(59, 21, 40, error_rate=0.4, seed=3), 'initial')
    inspection = definitions.inspect(installation, DEPLOYMENT, DEFINITION, now_tick=tick(T0 + timedelta(days=31)))
    definitions.confirm(installation, DEPLOYMENT, inspection['version'], inspection['inspection_digest'], actor='test',
                        now_tick=tick(T0 + timedelta(days=30)))
    server = HTTPServer(('127.0.0.1', 0), Hook)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    _allow(installation, 'http', server.server_port)
    hook = notify.configure_channel(installation, 'oncall', 'webhook', f'http://127.0.0.1:{server.server_port}/hook', actor='admin')
    notify.add_rule(installation, 'oncall-p2', 'oncall', min_priority='P2')
    notify.add_rule(installation, 'oncall-escalation', 'oncall', min_priority='P1', escalation_level=1)
    yield installation, hook['signing_key']
    server.shutdown()


@pytest.fixture(scope='module')
def detected(ops):
    from confidenceguard.operations.incidents import notify
    from confidenceguard.operations.monitoring import runtime
    installation, _key = ops
    summary = runtime.monitor_once(installation, DEPLOYMENT, now_tick=tick(APR20))
    notify.send_due(installation, now=APR20)
    return summary


def _incidents(installation):
    with installation.db.connect() as conn:
        return [dict(r) for r in conn.execute('SELECT i.*, c.key AS anchor_key FROM ops_incidents i JOIN ops_conditions c '
                                              'ON c.org_id = i.org_id AND c.id = i.anchor_condition ORDER BY i.number').fetchall()]


def _error_condition(installation):
    with installation.db.connect() as conn:
        return dict(conn.execute("SELECT * FROM ops_conditions WHERE key = 'detector:matured-error' ORDER BY created_at LIMIT 1").fetchone())


def _error_incident(installation):
    """The incident whose members include the matured-error condition (or its recurrence)."""
    with installation.db.connect() as conn:
        row = conn.execute('''SELECT ic.incident_id FROM ops_incident_conditions ic JOIN ops_conditions c ON c.id = ic.condition_id
                              WHERE c.key = 'detector:matured-error' AND ic.removed_at IS NULL ORDER BY ic.joined_at LIMIT 1''').fetchone()
    return next(i for i in _incidents(installation) if i['id'] == row['incident_id'])


def test_formal_alarm_opens_a_p1_incident_with_an_immutable_dossier(ops, detected):
    from confidenceguard.operations.incidents import incidents
    installation, _key = ops
    incident = _error_incident(installation)
    # The first formal condition processed is the anchor (detectors are folded in id order: brier, then matured-error);
    # matured-error joined it by population overlap on the same windows.
    assert incident['anchor_key'] == 'detector:brier'
    assert incident['priority'] == 'P1' and incident['priority_basis']['rule'] == 'formal_tier1'
    assert incident['state'] == 'open' and incident['escalation_due_at'] == APR20 + timedelta(minutes=15)
    view = incidents.view(installation, incident['id'], as_known='detection')
    dossier = view['knowledge']
    assert dossier['kind'] == 'detection_dossier' and dossier['catalog_sequence'] == incident['catalog_sequence']
    assert dossier['signals'] and all(s['standing'] == 'F' for s in dossier['signals'])
    assert dossier['window_evaluations'] and dossier['reference']['id'] and dossier['health']['coverage']
    assert {d['detector_id'] for d in dossier['detectors']} >= {'matured-error', 'brier'}
    assert view['events'][0]['kind'] == 'opened'
    # Pins protect the incident's windows.
    with installation.db.connect() as conn:
        pin = conn.execute("SELECT * FROM ops_pins WHERE holder_kind = 'incident' AND holder_id = %s", (str(incident['id']),)).fetchone()
    assert pin is not None and pin['expires_at'] is None


def test_grouping_is_anchor_compatible_and_never_transitive(ops, detected):
    from confidenceguard.operations.incidents import incidents
    installation, _key = ops
    with installation.db.connect() as conn:
        memberships = conn.execute('SELECT ic.incident_id, ic.condition_id, ic.rule, ic.link FROM ops_incident_conditions ic '
                                   'WHERE ic.removed_at IS NULL').fetchall()
        anchors = {r['id']: r['anchor_condition'] for r in conn.execute('SELECT id, anchor_condition FROM ops_incidents').fetchall()}
        conditions = {r['id']: dict(r) for r in conn.execute('SELECT * FROM ops_conditions').fetchall()}
        for member in memberships:
            if member['rule'] == 'anchor':
                assert anchors[member['incident_id']] == member['condition_id']
                continue
            assert member['rule'] in ('population_overlap', 'direct_link')
            assert member['link']['anchor'] == str(anchors[member['incident_id']])          # linked to the anchor itself
            found, compatible = incidents.link(installation, conn, conditions[anchors[member['incident_id']]],
                                               conditions[member['condition_id']])
            assert compatible and found['strength'] in ('population_overlap', 'exact')
    # Non-transitivity: a condition linked only to a non-anchor member must not join.
    with installation.db.connect() as conn:
        anchor = conditions[_error_incident(installation)['anchor_condition']]
        empty = next(c for c in conditions.values() if c['key'].startswith('health:empty_window'))
        found, _compatible = incidents.link(installation, conn, anchor, empty)
    assert found is None or found['strength'] == 'related_only'
    assert not any(m['condition_id'] == empty['id'] and anchors[m['incident_id']] == anchor['id'] for m in memberships)


def test_empty_windows_open_their_own_deterministic_incident(ops, detected):
    installation, _key = ops
    health = [i for i in _incidents(installation) if i['anchor_key'].startswith('health:empty_window')]
    assert len(health) == 1 and health[0]['priority'] == 'P2' and health[0]['priority_basis']['rule'] == 'deterministic_high'


def test_notifications_are_signed_minimal_and_idempotent(ops, detected):
    installation, key = ops
    opened = [json.loads(r['body']) for r in Hook.received if json.loads(r['body']).get('event') == 'opened']
    assert {o['priority'] for o in opened} >= {'P1', 'P2'}
    request = next(r for r in Hook.received if json.loads(r['body']).get('event') == 'opened')
    headers = {k.lower(): v for k, v in request['headers'].items()}
    expected = hmac.new(bytes.fromhex(key), headers['numek-timestamp'].encode() + b'.' + request['body'], hashlib.sha256).hexdigest()
    assert headers['numek-signature'] == f'sha256={expected}' and headers['numek-idempotency-key']
    payload = json.loads(request['body'])
    assert set(payload) == {'incident', 'number', 'deployment', 'priority', 'state', 'event', 'event_seq', 'escalation_level', 'link', 'at'}
    with installation.db.connect() as conn:
        states = {r['state'] for r in conn.execute('SELECT state FROM ops_notification_outbox').fetchall()}
        secret = conn.execute("SELECT count(*) AS n FROM ops_notification_channels WHERE secret_name LIKE 'notify/%%'").fetchone()['n']
        leaked = conn.execute('SELECT count(*) AS n FROM ops_notification_channels WHERE config::text LIKE %s', (f'%{key}%',)).fetchone()['n']
    assert states == {'sent'} and secret == 1 and leaked == 0
    before = len(Hook.received)
    from confidenceguard.operations.incidents import notify
    assert notify.send_due(installation, now=APR20)['sent'] == 0 and len(Hook.received) == before


def test_escalation_notifies_the_next_level(ops, detected):
    from confidenceguard.operations.incidents import incidents, notify
    installation, _key = ops
    incident = _error_incident(installation)
    assert incidents.escalate_due(installation, now=APR20 + timedelta(minutes=5)) == []
    escalated = incidents.escalate_due(installation, now=APR20 + timedelta(minutes=16))
    assert {'incident': str(incident['id']), 'level': 1} in escalated
    notify.send_due(installation, now=APR20 + timedelta(minutes=16))
    assert any(json.loads(r['body']).get('event') == 'escalated' and json.loads(r['body'])['escalation_level'] == 1 for r in Hook.received)


def test_lifecycle_rules_and_resolution_evidence(ops, detected):
    from confidenceguard.operations.incidents import incidents
    installation, _key = ops
    incident = _error_incident(installation)
    with pytest.raises(EvaluationError) as caught:
        incidents.transition(installation, incident['id'], 'verifying', actor='alice', expected_revision=incident['revision'])
    assert caught.value.code == 'incident_transition'
    with pytest.raises(EvaluationError) as caught:
        incidents.transition(installation, incident['id'], 'acknowledged', actor='alice', expected_revision=incident['revision'] - 1)
    assert caught.value.code == 'stale_revision'
    incidents.transition(installation, incident['id'], 'acknowledged', actor='alice', expected_revision=incident['revision'],
                         now=APR20 + timedelta(minutes=20))
    incidents.assign(installation, incident['id'], 'alice', actor='lead')
    incidents.transition(installation, incident['id'], 'investigating', actor='alice', now=APR20 + timedelta(minutes=30))
    with pytest.raises(EvaluationError) as caught:
        incidents.transition(installation, incident['id'], 'resolved', actor='alice', resolution='threshold_recovery_established')
    assert caught.value.code == 'recovery_evidence_required'                  # an absent alarm is never recovery
    with pytest.raises(EvaluationError) as caught:
        incidents.transition(installation, incident['id'], 'resolved', actor='alice', resolution='accepted_risk')
    assert caught.value.code == 'resolution_reason_required'
    assert _error_incident(installation)['escalation_due_at'] is None


def test_recovery_claim_resolves_the_incident_and_knowledge_is_revised(ops, detected):
    from confidenceguard.operations.incidents import incidents
    from confidenceguard.operations.monitoring import definitions, runtime
    installation, _key = ops
    incident = _error_incident(installation)
    definitions.start_recovery(installation, DEPLOYMENT, 'verify-error', claim='R2', alpha=0.05, planned_support=300,
                               statistic='error', theta=0.3, condition_id=_error_condition(installation)['id'])
    send(installation, generate(94, 21, 40, error_rate=0.1, seed=11, prefix='apr'), 'april')
    may20 = datetime(2026, 5, 20, tzinfo=timezone.utc)
    runtime.monitor_once(installation, DEPLOYMENT, now_tick=tick(may20))
    error = _error_condition(installation)
    with installation.db.connect() as conn:
        condition = conn.execute('SELECT state, recovery FROM ops_conditions WHERE id = %s', (error['id'],)).fetchone()
    assert condition['state'] == 'recovered' and condition['recovery']['claim'] == 'R2'
    assert 'not current risk' in condition['recovery']['interpretation']
    incidents.transition(installation, incident['id'], 'resolved', actor='alice', resolution='threshold_recovery_established',
                         now=may20)
    resolved = _error_incident(installation)
    assert resolved['state'] == 'resolved' and resolved['resolution_detail']['claim'] == 'R2'
    now_view = incidents.view(installation, incident['id'])
    detection = incidents.view(installation, incident['id'], as_known='detection')
    assert now_view['as_known'].startswith('revision') and detection['as_known'] == 'detection'
    recovered = [c for c in now_view['knowledge']['conditions'] if c['id'] == str(error['id'])]
    assert recovered[0]['state'] == 'recovered'
    assert str(error['id']) not in {c['id'] for c in detection['knowledge']['conditions']}   # joined after detection
    with installation.db.connect() as conn:
        pin = conn.execute("SELECT expires_at FROM ops_pins WHERE holder_kind = 'incident' AND holder_id = %s", (str(incident['id']),)).fetchone()
    assert pin['expires_at'] == may20 + timedelta(days=90)


def _signal(installation, source, source_id, standing, severity, *, window=None, payload=None, version=1):
    with installation.db.transaction() as conn:
        conn.execute('''INSERT INTO ops_signals(org_id, id, deployment_id, definition_version, source, source_id, window_index, standing,
                            severity, payload, dedupe_key) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)''',
                     (installation.scope.org_id, uuid.uuid4(), DEPLOYMENT, version, source, source_id, window, standing, severity,
                      json.dumps(payload or {'kind': 'synthetic'}), uuid.uuid4().hex))


def test_recurrence_reopens_a_recently_resolved_incident(ops, detected):
    from confidenceguard.operations.incidents import engine
    installation, _key = ops
    incident = _error_incident(installation)
    assert incident['state'] == 'resolved'
    _signal(installation, 'detector', 'matured-error', 'F', 'high', window=16, payload={'kind': 'sequential_alarm'})
    engine.operate(installation, DEPLOYMENT, now=datetime(2026, 5, 25, tzinfo=timezone.utc))
    reopened = _error_incident(installation)
    assert reopened['id'] == incident['id'] and reopened['state'] == 'reopened' and reopened['resolution'] is None
    with installation.db.connect() as conn:
        rules = [r['rule'] for r in conn.execute('SELECT rule FROM ops_incident_conditions WHERE incident_id = %s AND removed_at IS NULL',
                                                 (incident['id'],)).fetchall()]
        pin = conn.execute("SELECT expires_at FROM ops_pins WHERE holder_kind = 'incident' AND holder_id = %s", (str(incident['id']),)).fetchone()
    assert 'recurrence' in rules and pin['expires_at'] is None


def test_condition_lifecycle_persistence_lapse_suppression_and_r1(ops, detected):
    from confidenceguard.operations.incidents import conditions, engine
    installation, _key = ops
    base = datetime(2026, 6, 1, tzinfo=timezone.utc)
    with installation.db.connect() as conn:
        current = conditions.current_window(conn, installation.scope, DEPLOYMENT)
    # Persistence: a descriptive rule signal in 2 of the last 3 windows becomes active.
    _signal(installation, 'rule', 'synthetic-drift', 'P', 'medium', window=current - 1)
    engine.operate(installation, DEPLOYMENT, now=base)
    _signal(installation, 'rule', 'synthetic-drift', 'P', 'medium', window=current)
    engine.operate(installation, DEPLOYMENT, now=base)
    # Lapse: a windowless emerging condition with no repeat within 3 days.
    _signal(installation, 'rule', 'one-off', 'P', 'low')
    engine.operate(installation, DEPLOYMENT, now=base)
    # R1: a deterministic health condition recovers operationally after hold + further hold with no signal.
    _signal(installation, 'health', 'source_silent', 'D', 'high', payload={'kind': 'source_silent', 'source': 'scorecard-events'})
    engine.operate(installation, DEPLOYMENT, now=base)
    with installation.db.connect() as conn:
        state = {r['key']: r for r in conn.execute("SELECT * FROM ops_conditions WHERE key IN ('rule:synthetic-drift', 'rule:one-off', "
                                                   "'health:source_silent:scorecard-events')").fetchall()}
    assert state['rule:synthetic-drift']['state'] == 'active' and state['rule:one-off']['state'] == 'emerging'
    assert state['health:source_silent:scorecard-events']['state'] == 'active'
    conditions.suppress(installation, state['rule:synthetic-drift']['id'], reason='known upstream change', until=base + timedelta(days=1),
                        actor='alice')
    engine.operate(installation, DEPLOYMENT, now=base + timedelta(days=2))
    engine.operate(installation, DEPLOYMENT, now=base + timedelta(days=5))
    with installation.db.connect() as conn:
        state = {r['key']: r for r in conn.execute("SELECT * FROM ops_conditions WHERE key IN ('rule:synthetic-drift', 'rule:one-off', "
                                                   "'health:source_silent:scorecard-events')").fetchall()}
        events = [r['reason'] for r in conn.execute('SELECT reason FROM ops_condition_events WHERE condition_id = %s ORDER BY seq',
                                                    (state['health:source_silent:scorecard-events']['id'],)).fetchall()]
        audit = conn.execute("SELECT count(*) AS n FROM audit_log WHERE action = 'condition.suppress'").fetchone()['n']
    assert state['rule:one-off']['state'] == 'lapsed'
    assert state['rule:synthetic-drift']['state'] == 'active'                        # suppression expired back to active
    silent = state['health:source_silent:scorecard-events']
    assert silent['state'] == 'recovered' and silent['recovery']['claim'] == 'R1'
    assert events == ['created', 'no_signals_for_hold_period', 'R1'] and audit == 1


def test_split_and_merge_are_audited_and_reversible(ops, detected):
    from confidenceguard.operations.incidents import incidents
    from numek_platform.audit import verify_chain
    installation, _key = ops
    target = _error_incident(installation)
    source = next(i for i in _incidents(installation) if i['anchor_key'].startswith('health:empty_window'))
    moved = incidents.merge(installation, target['id'], source['id'], reason='one upstream outage', actor='alice')
    with installation.db.connect() as conn:
        merged = conn.execute('SELECT state, merged_into FROM ops_incidents WHERE id = %s', (source['id'],)).fetchone()
    assert merged['state'] == 'merged' and merged['merged_into'] == target['id']
    created = incidents.split(installation, target['id'], [uuid.UUID(c) for c in moved['moved']], reason='separate cause', actor='alice')
    with installation.db.connect() as conn:
        members = [r['condition_id'] for r in conn.execute('SELECT condition_id FROM ops_incident_conditions WHERE incident_id = %s '
                                                           'AND removed_at IS NULL', (created['incident'],)).fetchall()]
        kinds = [r['kind'] for r in conn.execute('SELECT kind FROM ops_incident_events WHERE incident_id = %s ORDER BY seq',
                                                 (target['id'],)).fetchall()]
        assert verify_chain(conn, installation.scope) == (True, None)
    assert sorted(str(m) for m in members) == sorted(moved['moved'])
    assert 'merged_in' in kinds and 'split_out' in kinds
    with pytest.raises(EvaluationError):
        incidents.split(installation, target['id'], [target['anchor_condition']], reason='no', actor='alice')


def test_dead_letters_digests_quiet_windows_and_smtp(ops, detected):
    from confidenceguard.operations.incidents import incidents, notify
    installation, _key = ops
    notify.configure_channel(installation, 'nowhere', 'webhook', 'https://hooks.invalid.example/x', actor='admin')
    notify.add_rule(installation, 'nowhere-all', 'nowhere', min_priority='P4')
    mail = socketserver.ThreadingTCPServer(('127.0.0.1', 0), Mail)
    threading.Thread(target=mail.serve_forever, daemon=True).start()
    _allow(installation, 'smtp', mail.server_address[1])
    notify.configure_channel(installation, 'mail', 'smtp', f'smtp://127.0.0.1:{mail.server_address[1]}',
                             config={'from': 'numek@example.test', 'to': 'oncall@example.test', 'allow_plaintext': True})
    notify.add_rule(installation, 'mail-digest', 'mail', min_priority='P4', digest_seconds=600)
    target = _error_incident(installation)
    at = datetime(2026, 6, 10, tzinfo=timezone.utc)
    incidents.set_priority(installation, target['id'], 'P2', reason='customer impact limited', actor='lead', now=at)
    incidents.set_priority(installation, target['id'], 'P3', reason='further limited', actor='lead', now=at)
    assert notify.send_due(installation, now=at)['sent'] >= 1                         # webhook rule sends at once
    assert not Mail.messages                                                         # digest is held
    notify.send_due(installation, now=at + timedelta(minutes=11))
    assert len(Mail.messages) == 1 and b'2 incident updates' in Mail.messages[0]
    later = at
    for _ in range(notify.MAX_ATTEMPTS + 1):
        later += timedelta(hours=2)
        notify.send_due(installation, now=later)
    with installation.db.connect() as conn:
        dead = conn.execute("SELECT state, attempts, last_error FROM ops_notification_outbox WHERE channel_id = 'nowhere'").fetchall()
        signal = conn.execute("SELECT standing, severity FROM ops_signals WHERE source_id = 'notification_dead_letter'").fetchone()
    assert dead and all(r['state'] == 'dead' and r['attempts'] == notify.MAX_ATTEMPTS for r in dead)
    assert dead[0]['last_error']['code'] == 'egress_denied' and (signal['standing'], signal['severity']) == ('D', 'high')
    mail.shutdown()


def test_controller_tasks_enqueue_under_leadership(ops, detected):
    from numek_platform.errors import PlatformError
    from confidenceguard.operations.scheduler import OperationsTasks, controller
    installation, _key = ops
    fixed = datetime(2026, 6, 20, tzinfo=timezone.utc).timestamp()
    leader = controller(installation, clock=lambda: fixed)
    report = leader.run_once()
    assert report['leader'] and report['tasks'][0]['cycles_enqueued'] == [DEPLOYMENT]
    again = leader.run_once()
    assert again['tasks'][0]['cycles_enqueued'] == []                                # already queued for the slot
    with installation.db.connect() as conn:
        jobs = conn.execute("SELECT kind, count(*) AS n FROM jobs WHERE kind IN ('ops_monitoring_cycle', 'ops_retention') GROUP BY kind").fetchall()
    assert {r['kind']: r['n'] for r in jobs} == {'ops_monitoring_cycle': 1, 'ops_retention': 1}
    with pytest.raises(PlatformError):                                              # a deposed controller cannot enqueue
        OperationsTasks(installation, clock=lambda: fixed).enqueue_cycles('impostor', leader.epoch + 7, datetime.now(timezone.utc))


def test_backup_and_restore_keep_operations_state(ops, detected, cluster, tmp_path):
    from numek_platform.backup import create_backup, restore_backup
    from numek_platform.db import Database
    from numek_platform.installation import Installation
    from confidenceguard.operations.incidents import incidents
    installation, _key = ops
    destination = Path(tmp_path).resolve() / 'backup'
    create_backup(installation.db, installation.store, installation.secrets, destination, passphrase='backup secret')
    os.environ['NUMEK_OPS_RESTORED_INCIDENTS_DSN'] = cluster.create_database('rs_' + uuid.uuid4().hex[:10])
    root = Path(tmp_path).resolve() / 'restored'
    root.mkdir(mode=0o700)
    (root / 'installation.json').write_text(json.dumps({**installation.config, 'dsn_env': 'NUMEK_OPS_RESTORED_INCIDENTS_DSN'}))
    for part in ('objects', 'secrets', 'catalogs'):
        (root / part).mkdir(mode=0o700)
    restored = Installation(root)
    restore_backup(destination, Database(restored.dsn()), restored.store, restored.secrets, passphrase='backup secret')
    incident = _error_incident(installation)
    original, copy = incidents.view(installation, incident['id']), incidents.view(restored, incident['id'])
    assert copy['knowledge'] == original['knowledge'] and copy['incident']['state'] == original['incident']['state']
    with restored.db.connect() as conn:
        detectors = conn.execute("SELECT detector_id, state_version, cursor_window FROM ops_detectors ORDER BY detector_id").fetchall()
    with installation.db.connect() as conn:
        expected = conn.execute("SELECT detector_id, state_version, cursor_window FROM ops_detectors ORDER BY detector_id").fetchall()
    assert detectors == expected


def test_retention_skips_pins_and_marks_windows_summary_only(ops, detected):
    from confidenceguard.operations.incidents import pins
    installation, _key = ops
    pins.set_policy(installation, 'credit-default', 30)
    pins.pin(installation, 'credit-default', '2026-01-01T00:00:00Z', '2026-01-15T00:00:00Z', reason='audit sample', actor='analyst',
             expires_at=datetime(2026, 12, 31, tzinfo=timezone.utc))
    report = pins.observation_sweep(installation, now=datetime(2026, 7, 1, tzinfo=timezone.utc))[0]
    assert report['facts_purged'] > 0 and report['pinned_opportunities_skipped'] >= 14 * 40
    assert report['windows_summary_only'] > 0
    with installation.db.connect() as conn:
        kept = conn.execute('''SELECT count(*) AS n FROM fact_index f WHERE f.kind = 'opportunity' AND f.event_tick < %s
                               AND NOT EXISTS (SELECT 1 FROM fact_tombstones t WHERE t.catalog_id = f.catalog_id AND t.kind = f.kind
                                               AND t.key = f.key AND t.revision = f.revision)''',
                            (tick(datetime(2026, 1, 15, tzinfo=timezone.utc)),)).fetchone()['n']
        summary = conn.execute("SELECT count(*) AS n FROM ops_window_evaluations WHERE reproducibility = 'summary_only'").fetchone()['n']
    assert kept == 14 * 40 and summary == report['windows_summary_only']


class _Flaky(BaseHTTPRequestHandler):
    mode, keys = '500', []

    def do_POST(self):
        _Flaky.keys.append(self.headers.get('Numek-Idempotency-Key'))
        self.rfile.read(int(self.headers.get('Content-Length', 0)))
        if _Flaky.mode == 'hang':
            import time
            time.sleep(15)
            return
        self.send_response(500)
        self.end_headers()

    def log_message(self, *args):
        pass


def test_failing_and_hanging_webhooks_retry_with_backoff_then_dead_letter(ops, detected):
    """M.3: an endpoint answering 500, then one that never answers (bounded by the egress timeout), then 500 until the
    last attempt. Retries back off exponentially, are never early, keep one idempotency key, and end as a dead letter
    with a D health signal."""
    import time
    from http.server import ThreadingHTTPServer
    from confidenceguard.operations.incidents import incidents, notify
    installation, _key = ops
    server = ThreadingHTTPServer(('127.0.0.1', 0), _Flaky)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    port = server.server_address[1]
    _allow(installation, 'http', port)
    notify.configure_channel(installation, 'flaky', 'webhook', f'http://127.0.0.1:{port}/hook', actor='admin')
    notify.add_rule(installation, 'flaky-all', 'flaky', min_priority='P4')
    target = _error_incident(installation)
    at = datetime(2026, 8, 1, tzinfo=timezone.utc)
    incidents.set_priority(installation, target['id'], 'P2', reason='flaky endpoint check', actor='lead', now=at)

    def row():
        with installation.db.connect() as conn:
            return dict(conn.execute("SELECT state, attempts, next_attempt_at, last_error FROM ops_notification_outbox "
                                     "WHERE channel_id = 'flaky'").fetchone())
    try:
        notify.send_due(installation, now=at)
        first = row()
        assert first['state'] == 'queued' and first['attempts'] == 1
        assert first['last_error'] == {'code': 'http_status', 'status': 500}
        assert first['next_attempt_at'] == at + timedelta(seconds=30)
        notify.send_due(installation, now=at + timedelta(seconds=10))                 # not due yet: no early retry
        assert row()['attempts'] == 1
        _Flaky.mode = 'hang'
        started = time.monotonic()
        notify.send_due(installation, now=first['next_attempt_at'])
        assert time.monotonic() - started < 14                                       # the egress timeout bounds it
        second = row()
        assert second['attempts'] == 2 and second['last_error']['code'] == 'egress_failed'          # the timeout
        assert second['next_attempt_at'] == first['next_attempt_at'] + timedelta(seconds=60)   # backoff doubles
        _Flaky.mode = '500'
        while row()['state'] != 'dead':
            notify.send_due(installation, now=row()['next_attempt_at'])
        assert row()['attempts'] == notify.MAX_ATTEMPTS
        assert len(_Flaky.keys) == notify.MAX_ATTEMPTS and len(set(_Flaky.keys)) == 1   # one idempotency key throughout
        with installation.db.connect() as conn:
            signal = conn.execute("SELECT standing FROM ops_signals WHERE source_id = 'notification_dead_letter' "
                                  "ORDER BY created_at DESC LIMIT 1").fetchone()
        assert signal['standing'] == 'D'
    finally:
        server.shutdown()
