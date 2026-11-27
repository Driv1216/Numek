"""Corrections from the CG7 independent technical review (2026-11-27). See docs/CG7_REVIEW_CORRECTIONS.md.

- B1: SM2 recovery tests follow the SM1 admission rules (R2.5); a descriptive claim is never recovery evidence.
- R2.4 comparability: alarms compare label availability, invalid-outcome and late-exclusion rates with the reference
  and show the measured reference/stream entity overlap.
- B2: a backup carries every secret the installation needs (R2.2), so a restored installation keeps ingesting into a
  sealed-reserve namespace and keeps signing notifications; a restore refuses a backup that lacks an evidence object.
- Route integrity, sign-in throttling and metrics access.
"""
import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from confidenceguard.contracts import EvaluationError
from numek_platform.errors import PlatformError
from monitoring_support import DEFINITION, NS, T0, contract, generate, send, tick  # noqa: E402

DEPLOYMENT = 'scorecard-prod'
APR20 = datetime(2026, 4, 20, tzinfo=timezone.utc)
PASSPHRASE = 'backup secret phrase'


@pytest.fixture(scope='module')
def ops(cluster, tmp_path_factory):
    from numek_platform.governance import reserve as reserves
    from numek_platform.installation import Installation
    from confidenceguard.operations import registry
    from confidenceguard.operations.incidents import notify
    from confidenceguard.operations.monitoring import definitions, runtime
    root = Path(tmp_path_factory.mktemp('corrections')).resolve()
    os.environ['NUMEK_OPS_CORRECTIONS_DSN'] = cluster.create_database('rc_' + uuid.uuid4().hex[:10], template='numek_template')
    installation = Installation.create(root / 'installation', dsn_env='NUMEK_OPS_CORRECTIONS_DSN')
    registry.register_system(installation, 'credit-default', 'Credit default', namespace=NS)
    registry.register_deployment(installation, 'credit-default', DEPLOYMENT, 'Scorecard', tier=1)
    registry.register_source(installation, DEPLOYMENT, 'scorecard-events', contract())
    send(installation, generate(0, 31, 40, error_rate=0.1, seed=1, prefix='r') + generate(31, 28, 40, error_rate=0.1, seed=2)
         + generate(59, 21, 40, error_rate=0.4, seed=3), 'initial')
    catalog_id = registry.system(installation, 'credit-default')['catalog_id']
    reserves.create_reserve(installation.db, installation.secrets, installation.scope, catalog_id, NS, actor='test',
                            fraction='0.3')
    notify.configure_channel(installation, 'oncall', 'webhook', 'https://hooks.example.test/numek', actor='admin')
    inspection = definitions.inspect(installation, DEPLOYMENT, DEFINITION, now_tick=tick(T0 + timedelta(days=31)))
    definitions.confirm(installation, DEPLOYMENT, inspection['version'], inspection['inspection_digest'], actor='test',
                        now_tick=tick(T0 + timedelta(days=30)))
    runtime.monitor_once(installation, DEPLOYMENT, now_tick=tick(APR20))
    return installation


def _error_condition(installation):
    with installation.db.connect() as conn:
        return dict(conn.execute("SELECT * FROM ops_conditions WHERE key = 'detector:matured-error' ORDER BY created_at "
                                 'LIMIT 1').fetchone())


# B1 -------------------------------------------------------------------------------------------------------------
def test_recovery_admission_follows_the_sm1_rules():
    from confidenceguard.operations.monitoring import definitions
    base = {'maturity': {'policy': 'equal_followup', 'followup_ns': '1'}, 'unit_design': 'entity_first'}
    record = {'design': 'clopper_pearson', 'lower': 0.05}
    assert definitions.recovery_admission(base, 'error', 'R2', record) == ('formal', [])
    assert definitions.recovery_admission(base, 'error', 'R3', record) == ('formal', [])
    as_of = {**base, 'maturity': {'policy': 'mature_as_of', 'horizon_ns': '1'}}
    assert definitions.recovery_admission(as_of, 'error', 'R2', record) == ('descriptive', ['maturity_not_equal_followup'])
    assert definitions.recovery_admission(as_of, 'abstention', 'R2', record) == ('formal', [])     # outcome-free statistic
    event = {**base, 'unit_design': 'event'}
    assert definitions.recovery_admission(event, 'error', 'R2', record) == (
        'descriptive', ['event_units_without_independence_declaration'])
    assert definitions.recovery_admission({**event, 'independent_units': True}, 'error', 'R2', record) == ('formal', [])
    assert definitions.recovery_admission(base, 'error', 'R3', {'design': None, 'lower': None}) == (
        'descriptive', ['reference_design_not_registered'])


def test_descriptive_recovery_test_never_recovers_its_condition(ops):
    from confidenceguard.operations.monitoring import definitions, runtime
    condition = _error_condition(ops)
    # A definition whose units are events without an independence declaration: SM1 is descriptive there, and so is SM2.
    with ops.db.transaction() as conn:
        conn.execute("""UPDATE ops_monitoring_definitions SET spec = jsonb_set(spec, '{unit_design}', '"event"')
                        WHERE deployment_id = %s AND state = 'confirmed'""", (DEPLOYMENT,))
    try:
        plan = definitions.start_recovery(ops, DEPLOYMENT, 'verify-event', claim='R2', alpha=0.05, planned_support=300,
                                          statistic='error', theta=0.3, condition_id=condition['id'])
    finally:
        with ops.db.transaction() as conn:
            conn.execute("""UPDATE ops_monitoring_definitions SET spec = jsonb_set(spec, '{unit_design}', '"entity_first"')
                            WHERE deployment_id = %s AND state = 'confirmed'""", (DEPLOYMENT,))
    assert plan['standing'] == 'descriptive' and plan['reasons'] == ['event_units_without_independence_declaration']
    send(ops, generate(94, 21, 40, error_rate=0.1, seed=11, prefix='apr'), 'april')           # recovered data
    runtime.monitor_once(ops, DEPLOYMENT, now_tick=tick(datetime(2026, 5, 20, tzinfo=timezone.utc)))
    with ops.db.connect() as conn:
        det = conn.execute("SELECT standing, state FROM ops_detectors WHERE detector_id = 'verify-event'").fetchone()
        signal = conn.execute("SELECT standing, payload FROM ops_signals WHERE source = 'recovery' AND source_id = 'verify-event'"
                              ).fetchone()
        row = conn.execute('SELECT state, recovery FROM ops_conditions WHERE id = %s', (condition['id'],)).fetchone()
        events = [r['reason'] for r in conn.execute('SELECT reason FROM ops_condition_events WHERE condition_id = %s',
                                                  (condition['id'],)).fetchall()]
    assert det['standing'] == 'descriptive' and det['state']['claimed_at'] is not None       # the kernel did cross theta
    assert signal['standing'] == 'P' and signal['payload']['kind'] == 'descriptive_recovery_indication'
    assert 'not recovery evidence' in signal['payload']['wording']
    assert row['state'] != 'recovered' and not (row['recovery'] or {}).get('claim')
    assert 'descriptive_recovery_indication' in events


def test_alarms_show_comparability_and_reference_entity_overlap(ops):
    with ops.db.connect() as conn:
        alarm = conn.execute("""SELECT payload FROM ops_signals WHERE source = 'detector' AND payload->>'kind' = 'sequential_alarm'
                                AND payload->>'statistic' = 'error' ORDER BY created_at LIMIT 1""").fetchone()['payload']
    comparability = alarm['comparability']
    assert {'label_availability', 'invalid_outcome', 'late_exclusion'} <= set(comparability['rates'])
    overlap = comparability['reference_entity_overlap']
    assert overlap['entities'] > 0 and overlap['shared'] == 0          # synthetic entities never repeat across periods
    assert 'measured entity overlap with the reference: 0 of' in alarm['assumptions'][2]
    assert alarm['population'] == 'included population comparable to reference'


# B2 -------------------------------------------------------------------------------------------------------------
def _restore(ops, cluster, tmp_path, destination, env):
    from numek_platform.backup import restore_backup
    from numek_platform.db import Database
    from numek_platform.installation import Installation
    os.environ[env] = cluster.create_database('rr_' + uuid.uuid4().hex[:10])
    root = Path(tmp_path).resolve() / ('restored-' + env.lower())
    root.mkdir(mode=0o700)
    (root / 'installation.json').write_text(json.dumps({**ops.config, 'dsn_env': env}))
    for part in ('objects', 'secrets', 'catalogs'):
        (root / part).mkdir(mode=0o700)
    restored = Installation(root)
    restore_backup(destination, Database(restored.dsn()), restored.store, restored.secrets, passphrase=PASSPHRASE)
    return restored


def test_backup_carries_every_secret_a_restored_installation_needs(ops, cluster, tmp_path):
    from numek_platform.backup import create_backup
    from numek_platform.installation import CONFIG
    from confidenceguard.operations import ingest, registry
    from confidenceguard.operations.monitoring import references
    destination = Path(tmp_path).resolve() / 'backup'
    config = (ops.root / CONFIG).read_bytes()
    manifest = create_backup(ops.db, ops.store, ops.secrets, destination, passphrase=PASSPHRASE, config_bytes=config)
    assert {'datakeys', 'reserves', 'notify', 'monitoring-order'} <= set(manifest['secrets'])
    assert manifest['config_sha256'] and (destination / 'config.bin').read_bytes() == config
    restored = _restore(ops, cluster, tmp_path, destination, 'NUMEK_RC_RESTORED_DSN')
    # Every secret of the old installation is present after the restore (nothing is needed from the old directory).
    assert set(ops.secrets.names()) <= set(restored.secrets.names())
    order = f'monitoring-order/{ops.scope.org_id}/{DEPLOYMENT}'
    assert restored.secrets.get(order) == references.order_secret(ops, DEPLOYMENT)
    # New entities in the reserved namespace need the reserve secret, and today's raw batches need today's data key
    # (whose batches were all processed, so no object in the cut referenced it).
    ingest.receive(restored, 'scorecard-events', 'after-restore', __import__('monitoring_support').body(
        generate(200, 1, 30, error_rate=0.1, seed=21, prefix='z')))
    result = ingest.process_pending(restored)[0]
    assert result['state'] == 'published' and result['counts']['rows_accepted'] == 30
    catalog_id = registry.system(restored, 'credit-default')['catalog_id']
    with restored.db.connect() as conn:
        states = {r['reserve_state'] for r in conn.execute('SELECT reserve_state FROM entity_registry WHERE catalog_id = %s '
                                                            'AND first_seen_k = (SELECT max(first_seen_k) FROM entity_registry '
                                                            'WHERE catalog_id = %s)', (catalog_id, catalog_id)).fetchall()}
    assert states <= {'reserve', 'non_reserve'} and states
    with restored.db.connect() as conn:
        channel = conn.execute("SELECT secret_name FROM ops_notification_channels WHERE id = 'oncall'").fetchone()
    assert restored.secrets.get(channel['secret_name']) == ops.secrets.get(channel['secret_name'])


def test_restore_refuses_a_backup_that_lacks_an_evidence_object(ops, cluster, tmp_path):
    from numek_platform.backup import MANIFEST, create_backup, restore_backup
    from numek_platform.db import Database
    destination = Path(tmp_path).resolve() / 'backup-damaged'
    manifest = create_backup(ops.db, ops.store, ops.secrets, destination, passphrase=PASSPHRASE)
    with ops.db.connect() as conn:
        victim = conn.execute("SELECT physical_key FROM objects WHERE state = 'active' AND codec <> 'encrypted_raw_batch_v1' "
                              'ORDER BY id LIMIT 1').fetchone()['physical_key']
    name = 'objects/' + victim.replace('/', '__')
    (destination / name).unlink()
    del manifest['files'][name]                                  # a consistent-looking but incomplete backup
    (destination / MANIFEST).write_text(json.dumps(manifest, sort_keys=True, indent=1))
    os.environ['NUMEK_RC_DAMAGED_DSN'] = cluster.create_database('rd_' + uuid.uuid4().hex[:10])
    from numek_platform.objects import LocalObjectStore
    from numek_platform.secrets import FileSecretStore
    root = Path(tmp_path).resolve() / 'damaged-target'
    with pytest.raises(PlatformError) as caught:
        restore_backup(destination, Database(os.environ['NUMEK_RC_DAMAGED_DSN']), LocalObjectStore(root / 'objects'),
                       FileSecretStore(root / 'secrets'), passphrase=PASSPHRASE)
    assert caught.value.code == 'backup_invalid'


# Route integrity, sign-in throttling, metrics -----------------------------------------------------------------
def test_routed_facts_must_name_their_opportunity(platform):
    from helpers import publish_records, record
    fact = record('prediction', ['a' * 64, 'v1', 'slot', 1], {'p': 0.2})
    with pytest.raises(PlatformError) as caught:
        publish_records(platform, [fact], opportunity_keys=[None])
    assert caught.value.code == 'route_undetermined'
    receipt, _ref, _lease = publish_records(platform, [fact])          # identity[0] is the opportunity key
    assert receipt.new_facts == 1


def test_sign_in_is_throttled_after_repeated_failures_and_metrics_need_loopback_or_auth(ops):
    from numek_platform import identity
    from confidenceguard.operations import api
    with ops.db.transaction() as conn:
        principal = identity.create_principal(conn, ops.scope, 'user', 'throttled')
        identity.set_password(conn, ops.scope, principal, 'correct horse battery staple')
        identity.bind_role(conn, ops.scope, principal, 'viewer')
    app = api.create_app(ops)
    app.testing = True
    client = app.test_client()
    for _ in range(identity.LOGIN_FAILURE_LIMIT):
        assert client.post('/api/ops/v1/session', json={'name': 'throttled', 'password': 'wrong guess'}).status_code == 401
    blocked = client.post('/api/ops/v1/session', json={'name': 'throttled', 'password': 'correct horse battery staple'})
    assert blocked.status_code == 429 and blocked.get_json()['error']['code'] == 'login_throttled'
    assert int(blocked.headers['Retry-After']) == int(identity.LOGIN_FAILURE_WINDOW.total_seconds())
    with ops.db.transaction() as conn:                          # the window passes
        conn.execute("UPDATE login_failures SET failed_at = failed_at - interval '1 hour' WHERE name = 'throttled'")
    signed_in = client.post('/api/ops/v1/session', json={'name': 'throttled', 'password': 'correct horse battery staple'})
    assert signed_in.status_code == 200
    assert app.test_client().get('/metrics').status_code == 200                                  # loopback scraper
    remote = app.test_client()
    assert remote.get('/metrics', environ_base={'REMOTE_ADDR': '10.0.0.5'}).status_code == 401
    assert client.get('/metrics', environ_base={'REMOTE_ADDR': '10.0.0.5'}).status_code == 200    # signed-in viewer


def test_templates_running_the_same_analysis_share_one_fingerprint():
    from confidenceguard.operations.intelligence import templates
    assert templates.TEMPLATES['cg3_cohort_contrast']['run'] is templates.TEMPLATES['cg3_mix_decomposition']['run']
    assert templates.TEMPLATES['cg3_cohort_contrast']['same_analysis_as'] == 'cg3_mix_decomposition'


def test_a_pending_recovery_is_applied_in_the_same_tick_that_makes_the_condition_quiet(ops):
    """Found while verifying the corrections: a claim recorded while the condition was active waited for a second tick
    after quiescence, so the outcome of one cycle depended on the (randomly keyed) unit order. Transitions now chain."""
    from psycopg.types.json import Jsonb
    from confidenceguard.operations.incidents import conditions
    condition = _error_condition(ops)
    evidence = {'claim': 'R2', 'signal': str(uuid.uuid4()), 'wording': 'synthetic', 'theta': 0.3, 'units': 300,
                'interpretation': 'synthetic', 'pending_quiescence': True}
    with ops.db.transaction() as conn:
        conn.execute("UPDATE ops_conditions SET state = 'active', recovery = %s, last_window = 0 WHERE id = %s",
                     (Jsonb(evidence), condition['id']))
    conditions.tick(ops, DEPLOYMENT, now=datetime(2026, 6, 1, tzinfo=timezone.utc))
    with ops.db.connect() as conn:
        row = conn.execute('SELECT state, recovery FROM ops_conditions WHERE id = %s', (condition['id'],)).fetchone()
        reasons = [r['reason'] for r in conn.execute('SELECT reason FROM ops_condition_events WHERE condition_id = %s '
                                                     'ORDER BY seq DESC LIMIT 2', (condition['id'],)).fetchall()]
    assert row['state'] == 'recovered' and row['recovery']['claim'] == 'R2' and 'pending_quiescence' not in row['recovery']
    assert reasons == ['R2', 'no_signals_for_hold_period']
