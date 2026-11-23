"""CG7 S8 interventions on a real installation, in simulated time.

The scenario: a March degradation opens incidents. A rollback proposal backed by validated evidence is submitted
and approved, with no side effects, then handed off. Its execution is declared, the identity changes to v2 in
production, and the customer attests. Recovered April data then verifies an R2 claim and an R3 claim through SM2
tests bound to the incident's condition, and the incident resolves with an outcome-supported resolution.

A second proposal, on the health incident, runs out of its horizon and is not verified.
"""
import base64
import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from confidenceguard.contracts import EvaluationError
from monitoring_support import DEFINITION, NS, T0, contract, generate, send, tick  # noqa: E402

DEPLOYMENT = 'scorecard-prod'
APR5 = datetime(2026, 4, 5, tzinfo=timezone.utc)
APR20 = datetime(2026, 4, 20, tzinfo=timezone.utc)
MAY20 = datetime(2026, 5, 20, tzinfo=timezone.utc)
KEY = Ed25519PrivateKey.generate()
SHARED = {}                                  # state handed between ordered tests of this module


@pytest.fixture(scope='module')
def ops(cluster, tmp_path_factory):
    from numek_platform.installation import Installation
    from confidenceguard.operations import registry
    from confidenceguard.operations.intelligence import planner
    from confidenceguard.operations.monitoring import definitions, runtime
    root = Path(tmp_path_factory.mktemp('interventions')).resolve()
    os.environ['NUMEK_OPS_INTERVENTIONS_DSN'] = cluster.create_database('itv_' + uuid.uuid4().hex[:10], template='numek_template')
    installation = Installation.create(root / 'installation', dsn_env='NUMEK_OPS_INTERVENTIONS_DSN')
    registry.register_system(installation, 'credit-default', 'Credit default', namespace=NS)
    public = KEY.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    registry.register_deployment(installation, 'credit-default', DEPLOYMENT, 'Scorecard', tier=1,
                                 registered_identity={'model_version': 'v1'}, attestation_public_key=public)
    registry.register_source(installation, DEPLOYMENT, 'scorecard-events', contract())
    send(installation, generate(0, 31, 40, error_rate=0.1, seed=1, prefix='r') + generate(31, 28, 40, error_rate=0.1, seed=2)
         + generate(59, 21, 40, error_rate=0.4, seed=3), 'initial')
    inspection = definitions.inspect(installation, DEPLOYMENT, DEFINITION, now_tick=tick(T0 + timedelta(days=31)))
    definitions.confirm(installation, DEPLOYMENT, inspection['version'], inspection['inspection_digest'], actor='test',
                        now_tick=tick(T0 + timedelta(days=30)))
    runtime.monitor_once(installation, DEPLOYMENT, now_tick=tick(APR20))
    incidents = _incidents(installation)
    error = next(i for i in incidents if i['anchor_key'] == 'detector:brier')
    run = planner.plan(installation, error['id'], now=APR20, only=('monitoring_health_review',))['selected'][0]
    planner.execute(installation, run['run'], now=APR20)
    return installation, error, next(i for i in incidents if i['anchor_key'].startswith('health:')), run['run']


def _incidents(installation):
    with installation.db.connect() as conn:
        return [dict(r) for r in conn.execute('SELECT i.*, c.key AS anchor_key FROM ops_incidents i JOIN ops_conditions c '
                                              'ON c.id = i.anchor_condition ORDER BY i.number').fetchall()]


def _state(installation, incident_id):
    with installation.db.connect() as conn:
        return conn.execute('SELECT state FROM ops_incidents WHERE id = %s', (incident_id,)).fetchone()['state']


ROLLBACK = {'title': 'Roll back to the January scorecard (v2 retrained on stable data)',
            'change': {'action': 'deploy_model', 'model_version': 'v2', 'positive_class': '1'},
            'expected_identity': {'model_version': 'v2'},
            'effects': [{'metric': 'error_rate', 'expected': 0.1, 'interval': [0.08, 0.12], 'basis': 'hypothetical_replay'},
                        {'metric': 'positive_decision_rate', 'expected': 0.5, 'basis': 'descriptive'}],
            'risks': ['Retrained model not yet seen on April traffic'],
            'verification_plan': {'claims': [{'id': 'threshold', 'claim': 'R2', 'statistic': 'error', 'theta': 0.3, 'alpha': 0.05,
                                              'planned_support': 300},
                                             {'id': 'noninferior', 'claim': 'R3', 'statistic': 'error', 'delta': 0.25, 'alpha': 0.05,
                                              'planned_support': 300}]}}


@pytest.fixture(scope='module')
def proposal(ops):
    from confidenceguard.operations.interventions import proposals
    installation, error, _health, run = ops
    return proposals.create(installation, error['id'], 'model_rollback', author='alice',
                            evidence=[{'basis': 'hypothetical_replay', 'ref': run}, {'basis': 'descriptive', 'summary': 'January baseline'}],
                            prerequisites=['identity_registered', 'attestation_key_registered'], **ROLLBACK)


def test_evidence_bases_are_validated(ops):
    from confidenceguard.operations.interventions import proposals
    installation, error, _health, run = ops
    with pytest.raises(EvaluationError) as caught:
        proposals.create(installation, error['id'], 'model_rollback', author='alice', evidence=[{'basis': 'independent_assessment', 'ref': run}],
                         **ROLLBACK)
    assert caught.value.code == 'evidence_not_independent'                 # an investigation run is not an independent assessment
    with pytest.raises(EvaluationError) as caught:
        proposals.create(installation, error['id'], 'model_rollback', author='alice',
                         evidence=[{'basis': 'hypothetical_replay', 'ref': str(uuid.uuid4())}], **ROLLBACK)
    assert caught.value.code == 'evidence_unavailable'
    with pytest.raises(EvaluationError) as caught:
        proposals.create(installation, error['id'], 'model_rollback', author='alice',
                         **{**ROLLBACK, 'verification_plan': {'claims': [{'id': 'causal', 'claim': 'R4'}]}})
    assert caught.value.code == 'invalid_verification_plan'               # R4 is never claimed


def test_submission_checks_prerequisites_and_moves_the_incident(ops, proposal):
    from confidenceguard.operations.interventions import proposals
    installation, error, _health, _run = ops
    submitted = proposals.submit(installation, proposal['id'], actor='alice', now=APR20 + timedelta(hours=1))
    assert submitted['state'] == 'submitted'
    assert {r['kind']: r['pass'] for r in submitted['prerequisites']['results']} == {
        'identity_registered': True, 'attestation_key_registered': True, 'verification_feasible': True, 'expected_identity_declared': True}
    assert _state(installation, error['id']) == 'response_proposed'
    with installation.db.connect() as conn:
        pins = conn.execute("SELECT expires_at FROM ops_pins WHERE holder_kind = 'proposal' AND holder_id = %s", (str(proposal['id']),)).fetchall()
    assert pins and all(p['expires_at'] is None for p in pins)


def _snapshot(installation):
    with installation.db.connect() as conn:
        return {'deployments': [dict(r) for r in conn.execute('SELECT id, registered_identity, tier FROM ops_deployments ORDER BY id').fetchall()],
                'sources': conn.execute('SELECT count(*) AS n, max(version) AS v FROM ops_sources').fetchone(),
                'jobs': conn.execute('SELECT count(*) AS n FROM jobs').fetchone()['n'],
                'outbox': conn.execute('SELECT count(*) AS n FROM ops_notification_outbox').fetchone()['n'],
                'definitions': conn.execute('SELECT count(*) AS n FROM ops_monitoring_definitions').fetchone()['n'],
                'incident': conn.execute('SELECT state, revision FROM ops_incidents ORDER BY number').fetchall()}


def test_approval_needs_separation_and_permission_and_has_no_side_effect(ops, proposal):
    from confidenceguard.operations.interventions import proposals
    installation, _error, _health, _run = ops
    with pytest.raises(EvaluationError) as caught:
        proposals.decide(installation, proposal['id'], 'approved', actor='alice', permissions={'intervention:approve'})
    assert caught.value.code == 'separation_of_duties'
    with pytest.raises(EvaluationError) as caught:
        proposals.decide(installation, proposal['id'], 'approved', actor='bob', permissions={'read'})
    assert caught.value.code == 'forbidden'
    before = _snapshot(installation)
    approved = proposals.decide(installation, proposal['id'], 'approved', actor='bob', permissions={'intervention:approve'})
    assert approved['state'] == 'approved' and _snapshot(installation) == before
    with installation.db.connect() as conn:
        audit = conn.execute("SELECT count(*) AS n FROM audit_log WHERE action = 'proposal.approve'").fetchone()['n']
    assert audit == 1


def test_handoff_is_immutable_and_never_executes(ops, proposal):
    from confidenceguard.operations.interventions import execution
    installation, _error, _health, _run = ops
    issued = execution.issue_handoff(installation, proposal['id'], actor='bob', now=APR20 + timedelta(hours=2))
    again = execution.handoff(installation, proposal['id'])
    assert again['handoff_digest'] == issued['handoff_digest'] and again['packet']['expected_identity'] == {'model_version': 'v2'}
    assert 'never executes' in again['packet']['executed_by'] and again['packet']['approvals'][0]['approver'] == 'bob'
    with pytest.raises(EvaluationError):
        execution.issue_handoff(installation, proposal['id'], actor='bob', now=APR20)


def test_response_comparison_side_by_side(ops, proposal):
    from confidenceguard.operations.interventions import proposals
    installation, error, _health, _run = ops
    proposals.create(installation, error['id'], 'threshold_change', author='carol', title='Raise the decision threshold to 0.6',
                     change={'action': 'threshold', 'value': 0.6}, expected_identity={'model_version': 'v1'},
                     effects=[{'metric': 'positive_decision_rate', 'expected': 0.4, 'basis': 'descriptive'}],
                     evidence=[{'basis': 'descriptive', 'summary': 'operator judgement'}],
                     verification_plan={'claims': [{'id': 'r2', 'claim': 'R2', 'statistic': 'error', 'theta': 0.3, 'alpha': 0.05,
                                                    'planned_support': 300}]})
    view = proposals.compare(installation, error['id'])
    assert [p['kind'] for p in view['proposals']] == ['model_rollback', 'threshold_change']
    assert [p['strongest_basis'] for p in view['proposals']] == ['hypothetical_replay', 'descriptive']
    assert all('not claimed' in p['causal_claim'] for p in view['proposals']) and 'never merged' in view['qualification']
    assert isinstance(view['prior_mitigations'], list)


def _sign(statement):
    raw = json.dumps(statement, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()
    return base64.b64encode(KEY.sign(raw)).decode()


def test_execution_standings_are_separate(ops, proposal, tmp_path):
    from confidenceguard.operations.interventions import execution
    installation, error, _health, _run = ops
    declared = execution.declare_execution(installation, proposal['id'], executed_at=APR5, actor='customer-ops',
                                           now=APR20 + timedelta(hours=3))
    assert declared['outcome'] == 'established' and declared['evidence_kind'] == 'declaration'
    assert {v['kind'] for v in declared['verification']} == {'R2', 'R3'}
    assert all(v['condition'] is not None for v in declared['verification'])     # bound to the matured-error condition
    assert _state(installation, error['id']) == 'verifying'
    assert execution.identity_consistency(installation, proposal['id'])['outcome'] == 'not_evaluable'   # nothing since execution
    send(installation, generate(94, 21, 40, error_rate=0.1, seed=11, prefix='apr', model_version='v2'), 'april')
    consistent = execution.identity_consistency(installation, proposal['id'])
    assert consistent['outcome'] == 'established' and consistent['evidence_kind'] == 'production'
    handoff = execution.handoff(installation, proposal['id'])
    statement = {'proposal': str(proposal['id']), 'handoff_digest': handoff['handoff_digest'], 'executed_at': APR5.isoformat(),
                 'identity': {'model_version': 'v2'}}
    assert execution.attest(installation, proposal['id'], statement, _sign(statement))['outcome'] == 'established'
    forged = execution.attest(installation, proposal['id'], statement, _sign({**statement, 'executed_at': 'x'}))
    assert forged['outcome'] == 'failed' and forged['reason'] == 'signature_does_not_verify'
    sampled = execution.sampled_behavior(installation, proposal['id'], logged_outputs={'probabilities': ['p']}, scratch=str(tmp_path))
    assert sampled['outcome'] == 'not_evaluable'                                    # no registered predictor: never inferred
    standings = execution.standings(installation, proposal['id'])
    assert standings['execution_attested']['evidence_kind'] == 'signature' and standings['execution_attested']['outcome'] == 'failed'


def test_not_verified_when_the_horizon_passes(ops):
    from confidenceguard.operations.interventions import execution, proposals
    installation, _error, health, _run = ops
    item = proposals.create(installation, health['id'], 'monitoring_fix', author='dana', title='Fix the March feed gap',
                            change={'action': 'restore_feed'}, evidence=[{'basis': 'descriptive', 'summary': 'feed outage'}],
                            verification_plan={'claims': [{'id': 'strict', 'claim': 'R2', 'statistic': 'error', 'theta': 0.01,
                                                           'alpha': 0.05, 'planned_support': 300, 'horizon_units': 60}]})
    proposals.submit(installation, item['id'], actor='dana', now=APR20)
    proposals.decide(installation, item['id'], 'approved', actor='erin', permissions={'intervention:approve'})
    execution.issue_handoff(installation, item['id'], actor='erin', now=APR20)
    execution.declare_execution(installation, item['id'], executed_at=APR5, actor='customer-ops', now=APR20)
    SHARED['health_proposal'] = item['id']


def test_verification_resolves_the_incident_with_outcome_evidence(ops, proposal):
    from confidenceguard.operations.interventions import execution, proposals, verification
    from confidenceguard.operations.monitoring import runtime
    installation, error, health, _run = ops
    runtime.monitor_once(installation, DEPLOYMENT, now_tick=tick(MAY20))
    verified = proposals.get(installation, proposal['id'])
    assert verified['state'] == 'verified'
    with installation.db.connect() as conn:
        claims = {r['claim_id']: dict(r) for r in conn.execute('SELECT * FROM ops_verifications WHERE proposal_id = %s',
                                                               (proposal['id'],)).fetchall()}
        condition = conn.execute('SELECT state, recovery FROM ops_conditions WHERE id = %s', (claims['threshold']['condition_id'],)).fetchone()
    assert {c['state'] for c in claims.values()} == {'established'}
    assert all(c['start_window'] >= 9 for c in claims.values())                   # the first window after April 5
    assert condition['state'] == 'recovered' and condition['recovery']['claim'] in ('R2', 'R3')
    resolved = verification.resolve(installation, proposal['id'], actor='bob', now=MAY20)
    assert resolved['resolution'] in ('threshold_recovery_established', 'reference_noninferiority_established')
    assert _state(installation, error['id']) == 'resolved'
    behavior = execution.behavior_change(installation, proposal['id'])
    assert behavior['evidence_kind'] == 'production' and 'descriptive' in behavior['standing']
    # The health-incident proposal ran out of its horizon without a claim.
    strict = proposals.get(installation, SHARED['health_proposal'])
    assert strict['state'] == 'not_verified' and _state(installation, health['id']) == 'investigating'
    with installation.db.connect() as conn:
        pins = conn.execute("SELECT expires_at FROM ops_pins WHERE holder_kind = 'proposal' AND holder_id = %s", (str(proposal['id']),)).fetchall()
    assert pins and all(p['expires_at'] is not None for p in pins)                 # settled: released after 90 days


def test_illegal_transitions_and_withdrawal(ops):
    from confidenceguard.operations.interventions import proposals
    installation, _error, health, _run = ops
    item = proposals.create(installation, health['id'], 'data_fix', author='dana', title='Backfill', change={'action': 'backfill'},
                            verification_plan={'claims': [{'id': 'ops', 'claim': 'R1'}]})
    with pytest.raises(EvaluationError) as caught:
        proposals.decide(installation, item['id'], 'approved', actor='erin', permissions={'intervention:approve'})
    assert caught.value.code == 'proposal_transition'                             # a draft cannot be approved
    proposals.withdraw(installation, item['id'], actor='dana', reason='superseded')
    assert proposals.get(installation, item['id'])['state'] == 'withdrawn'
    with pytest.raises(EvaluationError):
        proposals.submit(installation, item['id'], actor='dana', now=APR20)
