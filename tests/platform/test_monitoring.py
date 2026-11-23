"""CG7 S5 end to end, on a real installation.

The pipeline under test:
- ingestion (S4);
- a frozen reference;
- inspect, then confirm, a versioned definition;
- monitoring cycles in simulated time.

The tests cover:
- window evaluations under window-scoped reservations;
- SM1 alarms on a real shift;
- contiguous, unique detector segments;
- idempotent replay;
- estimator records and matched accountability;
- rules;
- late revisions;
- SM2 recovery;
- health and coverage.
"""
import csv
import io
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from confidenceguard.contracts import EvaluationError

NS = 'credit'
FIELDS = ['id', 'entity', 'when', 'y', 'p', 'available', 'due', 'group', 'model_version']
DAY = 86400 * 10**9
T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)


def tick(dt):
    return int(dt.timestamp()) * 10**9


def contract():
    return {
        'format': 'csv', 'event_time': 'when', 'identity': {'model_version': 'model_version'},
        'fields': {'id': {'type': 'string', 'identity': True}, 'entity': {'type': 'string', 'required': True},
                   'when': {'type': 'timestamp', 'required': True}, 'y': {'type': 'string', 'vocabulary': ['0', '1']},
                   'p': {'type': 'number', 'required': True, 'probability': True}, 'available': {'type': 'timestamp'},
                   'due': {'type': 'timestamp'}, 'group': {'type': 'string', 'vocabulary': ['a', 'b']},
                   'model_version': {'type': 'string'}},
        'batch': {'namespace': NS, 'outcome_definition_version': 'outcome-v1',
                  'bindings': [{'run': 'base', 'features': {'group': 'categorical'}}],
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


def generate(start_day, days, per_day, *, error_rate, seed, prefix='u'):
    rng = random.Random(seed)
    rows = []
    for d in range(days):
        day = T0 + timedelta(days=start_day + d)
        for j in range(per_day):
            when = day + timedelta(minutes=17 * j)
            positive = rng.random() < 0.5
            p = 0.8 if positive else 0.2
            correct = rng.random() >= error_rate
            y = ('1' if positive else '0') if correct else ('0' if positive else '1')
            ident = f'{prefix}{start_day + d}-{j}'
            rows.append({'id': ident, 'entity': f'e-{ident}', 'when': when.strftime('%Y-%m-%dT%H:%M:%SZ'), 'y': y, 'p': str(p),
                         'available': (when + timedelta(days=5)).strftime('%Y-%m-%dT%H:%M:%SZ'),
                         'due': (when + timedelta(days=5)).strftime('%Y-%m-%dT%H:%M:%SZ'),
                         'group': 'a' if rng.random() < 0.6 else 'b', 'model_version': 'v1'})
    return rows


def body(rows):
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=FIELDS, lineterminator='\n')
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue().encode()


def send(installation, rows, name):
    from confidenceguard.operations import ingest
    for i in range(0, len(rows), 800):
        ingest.receive(installation, 'scorecard-events', f'{name}-{i}', body(rows[i:i + 800]))
    return ingest.process_pending(installation)


DEFINITION = {
    'start': '2026-02-01T00:00:00Z', 'window_ns': str(7 * DAY), 'allowed_lateness_ns': str(6 * 3600 * 10**9),
    'maturity': {'policy': 'equal_followup', 'followup_ns': str(10 * DAY)},
    'features': {'group': 'categorical'}, 'cohorts': [{'id': 'population', 'column': 'group', 'categories': ['a', 'b']}],
    'reference': {'start': '2026-01-01T00:00:00Z', 'end': '2026-02-01T00:00:00Z', 'alpha': 0.01},
    'detectors': [
        {'id': 'matured-error', 'statistic': 'error', 'delta': 0.01, 'target_false_alarms_per_30_days': 0.1, 'shift': 0.15,
         'max_useful_delay_days': 60},
        {'id': 'brier', 'statistic': 'brier', 'delta': 0.01, 'target_false_alarms_per_30_days': 0.1, 'shift': 0.1,
         'max_useful_delay_days': 60},
        {'id': 'abstention', 'statistic': 'abstention', 'delta': 0.01, 'alpha': 1e-4, 'target': 0.2},
        {'id': 'log-loss', 'statistic': 'log_loss', 'delta': 0.1, 'alpha': 1e-4, 'shift': 0.1},
    ],
    'estimators': ['implied_issued_error', 'implied_brier', 'composition_projection'],
    'rules': [{'id': 'label-availability', 'measure': 'eligible_label_observation_rate', 'op': '<', 'value': 0.5,
               'phase': 'maturity', 'standing': 'P'}],
    'drift_thresholds': {'feature:group': {'total_variation': 0.05}},
}


@pytest.fixture(scope='module')
def monitored(tmp_path_factory):
    import os
    from numek_platform.installation import Installation
    from confidenceguard.operations import registry
    root = Path(tmp_path_factory.mktemp('monitoring')).resolve()
    os.environ.setdefault('NUMEK_OPS_MONITORING_DSN', os.environ['NUMEK_PLATFORM_DSN'])
    installation = Installation.create(root / 'installation', dsn_env='NUMEK_OPS_MONITORING_DSN',
                                       org='monitoring-' + root.name[-8:].replace('_', '-'))
    registry.register_system(installation, 'credit-default', 'Credit default', namespace=NS)
    registry.register_deployment(installation, 'credit-default', 'scorecard-prod', 'Scorecard', tier=1)
    registry.register_source(installation, 'scorecard-prod', 'scorecard-events', contract())
    reference = generate(0, 31, 40, error_rate=0.1, seed=1, prefix='r')                     # January
    stable = generate(31, 28, 40, error_rate=0.1, seed=2)                                   # February
    shifted = generate(59, 21, 40, error_rate=0.4, seed=3)                                  # March 1-21: degraded
    send(installation, reference + stable + shifted, 'initial')
    return installation


@pytest.fixture(scope='module')
def confirmed(monitored):
    from confidenceguard.operations.monitoring import definitions
    inspection = definitions.inspect(monitored, 'scorecard-prod', DEFINITION, now_tick=tick(T0 + timedelta(days=31)))
    result = definitions.confirm(monitored, 'scorecard-prod', inspection['version'], inspection['inspection_digest'],
                                 actor='test', now_tick=tick(T0 + timedelta(days=30)))
    return inspection, result


def test_inspection_plans_refuses_and_freezes_the_reference(monitored, confirmed):
    inspection, result = confirmed
    plans = {p['id']: p for p in inspection['detectors']}
    assert plans['log-loss']['admitted'] is False and plans['log-loss']['refusal'] == 'unbounded_statistic'
    error = plans['matured-error']
    assert error['admitted'] and error['standing'] == 'formal' and error['reference_design'] == 'clopper_pearson'
    # Inspected on Feb 1: January's last 10 days have not completed their equal follow-up, so they are excluded.
    assert 800 < error['reference_n'] < 1240 and error['m0'] == pytest.approx(error['reference_upper'] + 0.01)
    assert 0.08 < error['reference_mean'] < 0.12 and error['power'] == 'adequate'
    assert error['alpha'] == pytest.approx(0.1 / (30 * error['included_units_per_day']))
    assert error['expected_total_delay_days'] == pytest.approx(
        error['planner']['expected_delay_days'] + 17, rel=1e-9)                     # + window (7 d) + follow-up (10 d)
    assert plans['brier']['reference_design'] == 'hoeffding'
    assert inspection['refusals'] == [{'id': 'log-loss', 'reason': 'unbounded_statistic'}]
    assert result['state'] == 'confirmed' and result['added_after_observation'] is False
    with monitored.db.connect() as conn:
        use = conn.execute('SELECT purpose, state FROM evidence_uses WHERE id = %s',
                           (inspection['reference']['evidence_use'],)).fetchone()
    assert (use['purpose'], use['state']) == ('reference', 'consumed')
    # Stale confirmations refuse; the reference is computed once per rule and K.
    from confidenceguard.operations.monitoring import definitions
    again = definitions.inspect(monitored, 'scorecard-prod', DEFINITION, now_tick=tick(T0 + timedelta(days=31)))
    assert again['reference']['id'] == inspection['reference']['id']
    with pytest.raises(EvaluationError) as caught:
        definitions.confirm(monitored, 'scorecard-prod', again['version'], 'x' * 64)
    assert caught.value.code == 'stale_confirmation'


def test_adaptive_reference_is_refused(monitored):
    from confidenceguard.operations.monitoring import definitions
    bad = {**DEFINITION, 'reference': {'start': '2026-01-15T00:00:00Z', 'end': '2026-02-15T00:00:00Z'}}
    with pytest.raises(EvaluationError) as caught:
        definitions.inspect(monitored, 'scorecard-prod', bad)
    assert caught.value.code == 'adaptive_reference'


def _segments(installation, detector):
    with installation.db.connect() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT window_index, first_unit, units, alarms, state_version FROM ops_detector_segments "
            "WHERE detector_id = %s ORDER BY window_index", (detector,)).fetchall()]


def test_cycle_detects_the_shift_with_contiguous_segments_and_is_idempotent(monitored, confirmed):
    from confidenceguard.operations.monitoring import runtime
    now = tick(datetime(2026, 4, 20, tzinfo=timezone.utc))
    summary = runtime.cycle(monitored, 'scorecard-prod', now_tick=now)
    close = [e for e in summary['evaluated'] if e['phase'] == 'close']
    maturity = [e for e in summary['evaluated'] if e['phase'] == 'maturity']
    assert [e['window'] for e in close] == list(range(len(close))) and len(close) >= 10
    assert [e['window'] for e in maturity] == list(range(len(maturity))) and len(maturity) >= 8
    segments = _segments(monitored, 'matured-error')
    assert [s['window_index'] for s in segments] == list(range(len(segments)))
    assert [s['state_version'] for s in segments] == list(range(1, len(segments) + 1))
    for a, b in zip(segments, segments[1:]):                                  # unit indices are contiguous
        assert b['first_unit'] == a['first_unit'] + a['units']
    alarms = [a for s in segments for a in s['alarms']]
    assert alarms, 'the March degradation must be detected'
    alarm_window = next(s['window_index'] for s in segments if s['alarms'])
    assert alarm_window >= 4                                                 # not before the shift (window 4 = Mar 1)
    assert not any(s['alarms'] for s in segments[:4])
    with monitored.db.connect() as conn:
        signal = conn.execute("SELECT standing, payload FROM ops_signals WHERE source = 'detector' AND source_id = 'matured-error' "
                              "ORDER BY created_at LIMIT 1").fetchone()
        uses = conn.execute('SELECT u.purpose, u.state FROM ops_window_evaluations e JOIN evidence_uses u ON u.id = e.evidence_use_id '
                            'WHERE e.deployment_id = %s', ('scorecard-prod',)).fetchall()
    assert signal['standing'] == 'F' and 'inconsistent' in signal['payload']['wording']
    assert 'cause' in signal['payload']['not_established']
    assert {(u['purpose'], u['state']) for u in uses} == {('monitoring_outcome', 'consumed'), ('detector', 'consumed')}
    # Replay at the same time applies nothing; a forced re-application of an applied window refuses.
    again = runtime.cycle(monitored, 'scorecard-prod', now_tick=now)
    assert again['evaluated'] == [] and _segments(monitored, 'matured-error') == segments


def test_double_application_refuses(monitored, confirmed):
    from confidenceguard.operations.monitoring import definitions, references, runtime
    from confidenceguard.operations.monitoring import context
    current = definitions.confirmed(monitored, 'scorecard-prod')
    ctx = context.deployment(monitored, 'scorecard-prod')
    reference = references.load(monitored, current['reference_id'])
    before = _segments(monitored, 'matured-error')
    with pytest.raises(Exception):
        runtime.evaluate(monitored, ctx, current, reference, 'maturity', 2, closure='assumed_complete_after_lateness',
                         as_of_tick=tick(datetime(2026, 4, 1, tzinfo=timezone.utc)))
    assert _segments(monitored, 'matured-error') == before


def test_estimators_are_recorded_then_matched(monitored, confirmed):
    with monitored.db.connect() as conn:
        rows = [dict(r) for r in conn.execute("SELECT estimator, window_index, value, record, matched FROM ops_estimates "
                                              "ORDER BY estimator, window_index").fetchall()]
    implied = [r for r in rows if r['estimator'] == 'implied_issued_error']
    assert implied and all(r['value'] == pytest.approx(0.2) for r in implied if r['record']['population'])
    matched = [r for r in implied if r['matched'] and r['record']['population']]     # no data after Mar 21
    assert matched and all(0 < r['matched']['coverage'] <= 1 for r in matched)
    early = [r for r in matched if r['window_index'] < 4]
    late = [r for r in matched if 5 <= r['window_index'] <= 6]
    assert all(r['matched']['realized'] < 0.2 for r in early)               # calibration held (implied 0.2 >= realized 0.1)
    assert all(r['matched']['realized'] > 0.3 and r['matched']['exceedance'] for r in late)   # assumption failed after shift
    projection = next(r for r in rows if r['estimator'] == 'composition_projection' and r['record']['population'])
    assert projection['record']['band'] is not None and projection['record']['assumption'] == 'unchanged_within_group_risk'
    from confidenceguard.operations.monitoring import estimators
    assert estimators.ledger_summary(implied)['exceedances'] >= 2


def test_late_batch_creates_a_revision_and_is_excluded_from_detectors(monitored, confirmed):
    from confidenceguard.operations.monitoring import runtime
    with monitored.db.connect() as conn:
        before = conn.execute("SELECT late_excluded, units FROM ops_detectors WHERE detector_id = 'matured-error'").fetchone()
    send(monitored, generate(40, 2, 15, error_rate=0.1, seed=9, prefix='late'), 'late')        # Feb 10-11 (window 1)
    summary = runtime.cycle(monitored, 'scorecard-prod', now_tick=tick(datetime(2026, 4, 21, tzinfo=timezone.utc)))
    revised = [r for r in summary['revisions'] if r['window'] == 1]
    assert {r['phase'] for r in revised} == {'close', 'maturity'}
    with monitored.db.connect() as conn:
        after = conn.execute("SELECT late_excluded, units FROM ops_detectors WHERE detector_id = 'matured-error'").fetchone()
        versions = conn.execute("SELECT revision FROM ops_window_evaluations WHERE window_index = 1 AND phase = 'maturity' "
                                "ORDER BY revision").fetchall()
    assert after['late_excluded'] - before['late_excluded'] == 30 and after['units'] == before['units']
    assert [v['revision'] for v in versions] == [1, 2]


def test_recovery_claim_with_sm2(monitored, confirmed):
    from confidenceguard.operations.monitoring import definitions, runtime
    with pytest.raises(EvaluationError) as caught:                     # verification cannot start in evaluated windows
        definitions.start_recovery(monitored, 'scorecard-prod', 'too-early', claim='R2', alpha=0.05, planned_support=300,
                                   statistic='error', theta=0.3, start_window=0)
    assert caught.value.code == 'invalid_recovery'
    plan = definitions.start_recovery(monitored, 'scorecard-prod', 'recovery-r2', claim='R2', alpha=0.05,
                                      planned_support=300, statistic='error', theta=0.3)
    send(monitored, generate(94, 21, 40, error_rate=0.1, seed=11, prefix='apr'), 'april')     # Apr 5-25: recovered
    runtime.cycle(monitored, 'scorecard-prod', now_tick=tick(datetime(2026, 5, 20, tzinfo=timezone.utc)))
    with monitored.db.connect() as conn:
        det = conn.execute("SELECT state, cursor_window FROM ops_detectors WHERE detector_id = 'recovery-r2'").fetchone()
        claim = conn.execute("SELECT payload FROM ops_signals WHERE source = 'recovery' AND source_id = 'recovery-r2'").fetchone()
    assert det['cursor_window'] is not None and det['cursor_window'] >= plan['first_window']
    assert det['state']['claimed_at'] is not None and det['state']['claimed_at'] >= 30
    assert claim['payload']['kind'] == 'threshold_recovery_established' and claim['payload']['upper'] < 0.3
    assert 'not current risk' in claim['payload']['interpretation']


def test_health_and_coverage(monitored, confirmed):
    from confidenceguard.operations.monitoring import health
    report = health.report(monitored, 'scorecard-prod', now_tick=tick(datetime(2026, 4, 21, tzinfo=timezone.utc)))
    assert report['coverage']['matured_performance']['status'] == 'formal'
    assert report['coverage']['regions']['status'] == 'not_configured'
    assert report['statement'].startswith('Absence of conditions is not evidence of health')
    assert report['untimed_opportunities'] == 0
    assert not [c for c in report['conditions'] if c['kind'] == 'monitoring_stale']
    later = health.report(monitored, 'scorecard-prod', now_tick=tick(datetime(2026, 6, 1, tzinfo=timezone.utc)))
    kinds = {c['kind'] for c in later['conditions']}
    assert 'monitoring_stale' in kinds


def test_drift_and_rules_reuse_cg3_reducers(monitored, confirmed):
    from confidenceguard.operations.monitoring import packets
    with monitored.db.connect() as conn:
        close = conn.execute("SELECT packet_object FROM ops_window_evaluations WHERE phase = 'close' AND window_index = 5 "
                             "AND revision = 1").fetchone()
    packet = packets.read(monitored, close['packet_object'])
    group = next(d for d in packet['drift'] if d['field'] == 'feature:group')
    assert group['status'] == 'completed' and group['kind'] == 'categorical' and 'total_variation' in group
    decision = next(d for d in packet['drift'] if d['field'] == 'decision')
    assert decision['status'] == 'completed'
    assert {m['metric'] for m in packet['measurements']} >= {'eligible_label_observation_rate', 'error_rate'}
    with monitored.db.connect() as conn:
        empty = {r['window_index'] for r in conn.execute(
            "SELECT window_index FROM ops_signals WHERE payload->>'kind' = 'empty_window'").fetchall()}
        unevaluable_windows = {r['window_index'] for r in conn.execute(
            "SELECT window_index FROM ops_signals WHERE payload->>'kind' = 'rule_unevaluable'").fetchall()}
    assert {7, 8} <= empty and unevaluable_windows <= empty                  # Mar 22 - Apr 5 has no data: a D condition
    assert all(len(u['entity']) == 64 and 'e-' not in u['entity'] for u in packet['units'])   # packets carry hashes only
