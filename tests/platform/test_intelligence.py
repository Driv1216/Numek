"""CG7 S7 intelligence on a real installation.

The scenario: group b degrades *within* the group in March, while its traffic share also rises (0.4 to 0.6). That
gives a composition change with no composition-explained risk, so the differential has something real to
separate.

The tests cover:
- frozen CG4 regions (exposure and region-scoped error);
- structural links;
- priority table v2;
- hypotheses, the differential matrix and requirements;
- the planner (tiers, budgets, reuse, approvals, refusals) and the template executors;
- deferred triggers;
- recurring patterns;
- label guidance;
- the Poisson-binomial diagnostic;
- the domain classifier.
"""
import os
import uuid
from datetime import datetime, timedelta, timezone
from itertools import product
from pathlib import Path

import numpy as np
import pytest

from confidenceguard.contracts import EvaluationError
from monitoring_support import DEFINITION, NS, T0, contract, generate, send, tick  # noqa: E402

DEPLOYMENT = 'scorecard-prod'
APR20 = datetime(2026, 4, 20, tzinfo=timezone.utc)


def region_b():
    from confidenceguard.investigation_membership import seal
    return seal('structured', {'clauses': [{'field': 'group', 'op': 'eq', 'value': 'b', 'kind': 'categorical'}]}, features=['group'])


def definition():
    detectors = [d for d in DEFINITION['detectors'] if d['id'] in ('matured-error', 'brier')]
    detectors += [
        {'id': 'region-b-error', 'statistic': 'error', 'params': {'region': 'group-b'}, 'delta': 0.01,
         'target_false_alarms_per_30_days': 0.1, 'shift': 0.15, 'max_useful_delay_days': 60},
        {'id': 'region-b-exposure', 'statistic': 'region_membership', 'params': {'region': 'group-b'}, 'delta': 0.02,
         'target_false_alarms_per_30_days': 0.1, 'shift': 0.15, 'max_useful_delay_days': 60}]
    return {**DEFINITION, 'detectors': detectors,
            'regions': [{'id': 'group-b', 'artifact': region_b(), 'source_standing': 'S-selected'}]}


@pytest.fixture(scope='module')
def ops(cluster, tmp_path_factory):
    from numek_platform.installation import Installation
    from confidenceguard.operations import registry
    from confidenceguard.operations.monitoring import definitions, runtime
    root = Path(tmp_path_factory.mktemp('intelligence')).resolve()
    os.environ['NUMEK_OPS_INTELLIGENCE_DSN'] = cluster.create_database('int_' + uuid.uuid4().hex[:10], template='numek_template')
    installation = Installation.create(root / 'installation', dsn_env='NUMEK_OPS_INTELLIGENCE_DSN')
    registry.register_system(installation, 'credit-default', 'Credit default', namespace=NS)
    registry.register_deployment(installation, 'credit-default', DEPLOYMENT, 'Scorecard', tier=1)
    registry.register_source(installation, DEPLOYMENT, 'scorecard-events', contract())
    send(installation, generate(0, 31, 40, error_rate=0.1, seed=1, prefix='r') + generate(31, 28, 40, error_rate=0.1, seed=2)
         + generate(59, 21, 40, error_rate=0.1, error_rate_b=0.5, b_share=0.6, seed=3), 'initial')
    inspection = definitions.inspect(installation, DEPLOYMENT, definition(), now_tick=tick(T0 + timedelta(days=31)))
    definitions.confirm(installation, DEPLOYMENT, inspection['version'], inspection['inspection_digest'], actor='test',
                        now_tick=tick(T0 + timedelta(days=30)))
    runtime.monitor_once(installation, DEPLOYMENT, now_tick=tick(APR20))
    return installation, inspection


def _conditions(installation):
    with installation.db.connect() as conn:
        return {r['key']: dict(r) for r in conn.execute('SELECT * FROM ops_conditions ORDER BY created_at').fetchall()}


def _incident_of(installation, key):
    with installation.db.connect() as conn:
        row = conn.execute('''SELECT i.* FROM ops_incident_conditions ic JOIN ops_conditions c ON c.id = ic.condition_id
                              JOIN ops_incidents i ON i.id = ic.incident_id WHERE c.key = %s AND ic.removed_at IS NULL
                              ORDER BY ic.joined_at LIMIT 1''', (key,)).fetchone()
    return None if row is None else dict(row)


def test_regions_are_monitored_with_cg4_membership(ops):
    from confidenceguard.operations.monitoring import references
    installation, inspection = ops
    reference = references.load(installation, inspection['reference']['id'])
    stats = reference['packet']['statistics']
    assert 0.35 < stats['region_membership@group-b']['mean'] < 0.45            # January share of group b
    assert stats['error@group-b']['n'] < stats['error']['n']                    # region-scoped reference is its own
    assert reference['packet']['region_shares']['group-b']['source_standing'] == 'S-selected'
    plans = {p['id']: p for p in inspection['detectors']}
    assert plans['region-b-exposure']['region_source_standing'] == 'S-selected' and plans['region-b-exposure']['phase'] == 'close'
    conditions = _conditions(installation)
    assert 'detector:region-b-exposure' in conditions and 'detector:region-b-error' in conditions
    assert min(conditions['detector:region-b-exposure']['windows']) >= 4          # the March share rise, not before
    with pytest.raises(EvaluationError) as caught:                               # diagnostic gates are refused in monitoring
        from confidenceguard.operations.intelligence import regions
        bad = {**region_b(), 'kind': 'catboost'}
        regions.validate([{'id': 'x', 'artifact': bad, 'source_standing': 'H-confirmed'}], {'group': 'categorical'})
    assert caught.value.code in ('membership_artifact', 'membership_artifact_changed', 'region_kind_unsupported_in_monitoring')


def test_structural_links_join_region_conditions(ops):
    from confidenceguard.operations.incidents import incidents
    from confidenceguard.operations.intelligence import association
    installation, _inspection = ops
    conditions = _conditions(installation)
    exposure, error = conditions['detector:region-b-exposure'], conditions['detector:region-b-error']
    with installation.db.connect() as conn:
        a = incidents._dependencies(conn, installation.scope, exposure)
        b = incidents._dependencies(conn, installation.scope, error)
        found, compatible = incidents.link(installation, conn, exposure, error)
    assert a['inputs'] == b['inputs'] == {'group'} and a['artifacts'][0]['kind'] == 'cg4_region'
    assert found['strength'] in ('structural', 'exact') and compatible
    structural = association.structural(a, b)
    assert structural['shared_inputs'] == ['group'] and 'not a common cause' in structural['qualification']
    assert _incident_of(installation, 'detector:region-b-exposure')['id'] == _incident_of(installation, 'detector:region-b-error')['id']


def test_priority_v2_caps_selected_regions_and_records_impact(ops):
    from confidenceguard.operations.incidents import priority
    installation, _inspection = ops
    incident = _incident_of(installation, 'detector:region-b-exposure')
    basis = incident['priority_basis']
    assert basis['table'] == 'cg7_priority_v2'
    assert basis['impact']['region'] == 'group-b'                               # anchored on the region exposure alarm
    assert incident['priority'] == 'P2' and basis['rule'] == 'formal_region_not_confirmed'
    assert basis['impact']['affected_units'] > 0 and 0.5 < basis['impact']['region_share'] < 0.7
    formal = {'standing': 'F', 'severity': 'high'}
    assert priority.decide(formal, 1, {'region_source_standing': 'H-confirmed', 'region_share': 0.004})[1]['rule'] == 'formal_region_low_exposure'
    assert priority.decide(formal, 1, {'region_source_standing': 'H-confirmed', 'region_share': 0.3})[0] == 'P1'
    assert priority.decide(formal, 1, {'region_source_standing': 'exploratory', 'region_share': 0.3})[0] == 'P2'
    assert priority.decide({'standing': 'E', 'severity': 'high'}, 1)[0] == 'P4'


def test_hypotheses_matrix_and_requirements(ops):
    from confidenceguard.operations.incidents import incidents
    installation, _inspection = ops
    incident = _incident_of(installation, 'detector:region-b-error')
    with installation.db.connect() as conn:
        states = {r['hypothesis_id']: dict(r) for r in conn.execute('SELECT * FROM ops_hypotheses WHERE incident_id = %s',
                                                                     (incident['id'],)).fetchall()}
        requirements = {r['observation']: dict(r) for r in conn.execute('SELECT * FROM ops_requirements WHERE incident_id = %s',
                                                                          (incident['id'],)).fetchall()}
        transitions = conn.execute("SELECT count(*) AS n FROM ops_incident_events WHERE incident_id = %s AND kind = 'hypothesis_state'",
                                   (incident['id'],)).fetchone()['n']
    assert len(states) == 10 and transitions >= 10
    assert states['H-UNC']['state'] == 'untestable' and states['H-UNC']['reason'] == 'coverage_statistics_not_monitored'
    assert states['H-WITHIN']['state'] == 'supported'                              # group b degraded within the group
    assert states['H-COMP']['state'] == 'contradicted'                             # equal reference risks: mix explains nothing
    assert states['H-DEPLOY']['state'] == 'unresolved'
    identity = requirements['O-identity-change']
    assert identity['status'] == 'open' and 'predictor spec' in identity['action'] and 'H-DEPLOY' in identity['hypotheses']
    view = incidents.view(installation, incident['id'])
    matrix = view['knowledge']['differential']
    within = next(r for r in matrix['rows'] if r['hypothesis'] == 'H-WITHIN')
    assert within['cells']['O-within-group-change'] == '✓' and 'not an established cause' in matrix['qualification']
    comp = next(r for r in matrix['rows'] if r['hypothesis'] == 'H-COMP')
    assert comp['cells']['O-composition-shift'] == '✗'


def test_planner_tiers_budgets_and_refusals(ops):
    from confidenceguard.operations.intelligence import planner
    installation, _inspection = ops
    incident = _incident_of(installation, 'detector:region-b-error')
    result = planner.plan(installation, incident['id'], now=APR20 + timedelta(hours=1))
    decisions = {c['template']: c for c in result['considered']}
    assert decisions['cg6_shadow_replay']['decision'] == 'ineligible' and 'predictor' in decisions['cg6_shadow_replay']['reason']
    restricted = [c for c in result['considered'] if c['tier'] == 'restricted' and c['decision'] == 'awaiting_approval']
    auto = [c for c in result['considered'] if c['decision'] == 'planned']
    assert auto and all(c['tier'] == 'auto' for c in auto) and result['budget']['auto_minutes_used_today'] <= 30
    assert all(c['value_per_minute'] >= d['value_per_minute'] for c, d in zip(auto, auto[1:]))     # greedy order
    again = planner.plan(installation, incident['id'], now=APR20 + timedelta(hours=1))
    assert all(c['decision'] in ('duplicate', 'ineligible', 'budget', 'cooldown') for c in again['considered'])
    assert restricted, 'H-CALIB is movable, so its restricted recalibration study awaits approval'
    with pytest.raises(EvaluationError) as caught:
        planner.approve(installation, restricted[0]['run'], actor='alice', now=APR20 + timedelta(hours=2))
    assert caught.value.code == 'forbidden'
    refused = planner.approve(installation, restricted[0]['run'], actor='alice', permissions=('reserve:consume',),
                              now=APR20 + timedelta(hours=2))
    assert refused['state'] == 'refused' and refused['code'] == 'restricted_study'


def test_auto_investigations_settle_observations(ops):
    from confidenceguard.operations.incidents import incidents
    from confidenceguard.operations.intelligence import planner
    installation, _inspection = ops
    incident = _incident_of(installation, 'detector:region-b-error')
    with installation.db.connect() as conn:
        planned = [r['id'] for r in conn.execute("SELECT id FROM ops_investigation_runs WHERE incident_id = %s AND state = 'planned' "
                                                 'ORDER BY value DESC', (incident['id'],)).fetchall()]
    results = [planner.execute(installation, run, now=APR20 + timedelta(hours=2)) for run in planned]
    by_state = {r['state'] for r in results}
    assert 'completed' in by_state
    with installation.db.connect() as conn:
        runs = {r['template']: dict(r) for r in conn.execute('SELECT * FROM ops_investigation_runs WHERE incident_id = %s',
                                                             (incident['id'],)).fetchall()}
        uses = conn.execute("SELECT purpose, state FROM evidence_uses WHERE purpose = 'covariate_inspection'").fetchall()
    assert runs['contract_diff']['state'] == 'completed'
    assert runs['contract_diff']['result']['observations']['O-integrity']['value'] is False
    assert runs['domain_classifier']['state'] == 'completed'
    assert len(uses) == 2 and all(u['state'] == 'consumed' for u in uses)          # covariates only, both arms, consumed
    view = incidents.view(installation, incident['id'])
    assert view['knowledge']['reason'].startswith('investigation')
    with installation.db.connect() as conn:
        integ = conn.execute("SELECT state FROM ops_hypotheses WHERE incident_id = %s AND hypothesis_id = 'H-INTEG'",
                             (incident['id'],)).fetchone()['state']
    assert integ == 'contradicted'


def test_reuse_only_when_the_change_is_additional_units(ops):
    from confidenceguard.operations.intelligence import planner
    installation, _inspection = ops
    incident = _incident_of(installation, 'detector:region-b-error')
    send(installation, generate(63, 1, 10, error_rate=0.1, seed=21, prefix='extra'), 'extra')     # a few more units in March
    with installation.db.connect() as conn:
        completed = [r['template'] for r in conn.execute("SELECT template FROM ops_investigation_runs WHERE incident_id = %s "
                                                         "AND state = 'completed' ORDER BY created_at", (incident['id'],)).fetchall()]
    decision = None
    for template in completed:                     # a template whose hypothesis is still movable (terminal ones drop out)
        result = planner.plan(installation, incident['id'], now=APR20 + timedelta(hours=3), only=(template,))
        decision = next((c for c in result['considered'] if c['template'] == template), None)
        if decision is not None:
            break
    assert decision is not None, completed
    assert decision['decision'] == 'reused' and decision['reuse_check']['material_changes'] == 0
    with installation.db.connect() as conn:
        reused = conn.execute("SELECT reused_from, stale_fraction, result FROM ops_investigation_runs WHERE id = %s",
                              (uuid.UUID(decision['run']),)).fetchone()
    assert reused['reused_from'] is not None and 0 < reused['stale_fraction'] < 0.2 and reused['result'] is not None


def test_deferred_trigger_queues_its_template(ops):
    from confidenceguard.operations.intelligence import planner
    installation, _inspection = ops
    incident = _incident_of(installation, 'detector:region-b-error')

    def require(observation, template, hypothesis):
        with installation.db.transaction() as conn:
            conn.execute('''INSERT INTO ops_requirements(org_id, incident_id, observation, status, reason, eta, hypotheses, template)
                            VALUES (%s, %s, %s, 'open', 'awaiting evidence', %s, %s, %s)
                            ON CONFLICT (org_id, incident_id, observation) DO UPDATE SET status = 'open', eta = EXCLUDED.eta,
                            template = EXCLUDED.template, triggered_run = NULL, hypotheses = EXCLUDED.hypotheses''',
                         (installation.scope.org_id, incident['id'], observation, APR20, [hypothesis], template))
    require('O-monitoring-health', 'monitoring_health_review', 'H-MON')             # H-MON is contested: still movable
    require('O-label-availability-shift', 'label_availability_audit', 'H-LABEL')    # already decided by monitoring evidence
    send(installation, generate(64, 1, 5, error_rate=0.1, seed=22, prefix='later'), 'later')      # the evidence moves on (new K)
    fired = planner.fire_triggers(installation, now=APR20 + timedelta(days=2))
    assert [f['observation'] for f in fired] == ['O-monitoring-health']
    with installation.db.connect() as conn:
        rows = {r['observation']: r for r in conn.execute("SELECT observation, status, triggered_run, reason FROM ops_requirements "
                                                          "WHERE incident_id = %s", (incident['id'],)).fetchall()}
    assert rows['O-monitoring-health']['triggered_run'] is not None
    assert rows['O-label-availability-shift']['status'] == 'satisfied' and 'decided' in rows['O-label-availability-shift']['reason']


def test_recurring_patterns_are_deterministic(ops):
    from confidenceguard.operations.incidents import incidents
    from confidenceguard.operations.intelligence import patterns
    installation, _inspection = ops
    with installation.db.connect() as conn:
        ids = [r['id'] for r in conn.execute("SELECT id FROM ops_incidents WHERE state <> 'merged' ORDER BY number").fetchall()]
    assert len(ids) >= 2
    first, second = ids[0], ids[1]
    incidents.transition(installation, first, 'resolved', actor='alice', resolution='monitoring_artifact', reason='test pattern')
    signature = patterns.signature(installation, second)
    assert f'deployment:{DEPLOYMENT}' in signature and signature == patterns.signature(installation, second)
    everything = patterns.similar(installation, second, threshold=0.0)
    assert [s['incident'] for s in everything['similar']] == [str(first)] and everything['similar'][0]['resolution'] == 'monitoring_artifact'
    assert patterns.similar(installation, second, threshold=1.01)['similar'] == []


def test_catalog_is_complete_and_consistent():
    from confidenceguard.operations.intelligence import hypotheses, observations, templates
    assert hypotheses._consistent()
    assert len(hypotheses.CATALOG) == 10 and all(h['templates'] for h in hypotheses.CATALOG)
    named = {o for h in hypotheses.CATALOG for o in (*h['supports'], *h['contradicts'], *h['requires'])}
    assert named <= set(observations.OBSERVATIONS)
    assert all(set(t['discriminates']) <= set(hypotheses.BY_ID) for t in templates.TEMPLATES.values())


def test_neyman_allocation_and_label_guidance():
    from confidenceguard.operations.intelligence import guidance
    shares, risks = {'a': 0.6, 'b': 0.4}, {'a': 0.1, 'b': 0.5}
    allocation = guidance.neyman(shares, risks, 100)
    assert sum(allocation.values()) == 100
    expected_b = 100 * 0.4 * 0.5 / (0.6 * 0.3 + 0.4 * 0.5)
    assert abs(allocation['b'] - expected_b) <= 1
    proportional = {'a': 60, 'b': 40}
    assert guidance.half_width(shares, risks, allocation) <= guidance.half_width(shares, risks, proportional)


def test_poisson_binomial_diagnostic_is_exact():
    from confidenceguard.operations.monitoring.estimators import poisson_binomial_diagnostic
    p = [0.1, 0.3, 0.25, 0.6, 0.05]
    dist = np.zeros(len(p) + 1)
    for bits in product([0, 1], repeat=len(p)):
        prob = np.prod([q if b else 1 - q for q, b in zip(p, bits)])
        dist[sum(bits)] += prob
    for observed in range(len(p) + 1):
        result = poisson_binomial_diagnostic(p, observed)
        assert result['two_sided_p'] == pytest.approx(dist[dist <= dist[observed] * (1 + 1e-12)].sum(), abs=1e-12)
    assert result['standing'] == 'diagnostic' and len(result['assumptions']) == 2


def test_domain_classifier_core():
    import hashlib
    from sklearn.metrics import roc_auc_score
    from confidenceguard.operations.intelligence import domain
    rng = np.random.default_rng(3)
    scores, labels = rng.integers(0, 5, 400).astype(float), rng.random(400) < 0.5
    assert domain.auc(scores, labels) == pytest.approx(roc_auc_score(labels, scores))           # ties by average rank

    def arm(n, prefix, share):
        return [(hashlib.sha256(f'{prefix}{i}'.encode()).digest(), {'group': 'b' if rng.random() < share else 'a',
                                                                     'income': f'{rng.normal(50, 10):.1f}'}) for i in range(n)]
    shared = arm(20, 'both', 0.5)
    shifted = domain.core(arm(700, 'r', 0.3) + shared, arm(700, 'c', 0.7) + shared, {'group': 'categorical', 'income': 'numeric'},
                          b'k' * 32, permutations=2000)
    assert shifted['counts']['excluded_in_both_arms'] == 20 and shifted['held_out_auc'] > 0.65
    assert shifted['exploratory_test']['p_value'] < 0.01 and shifted['permutation_importance'][0]['feature'] == 'group'
    assert shifted['auc_interval'] is None and shifted['standing'] == 'descriptive'
    with pytest.raises(EvaluationError):
        domain.core(arm(100, 'x', 0.5), arm(100, 'y', 0.5), {'y': 'categorical'}, b'k' * 32)
