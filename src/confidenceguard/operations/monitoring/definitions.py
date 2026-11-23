"""Versioned monitoring definitions: inspect, then confirm (plan J1, G.3, R2.4).

Inspecting a definition records a new version in state ``inspected``. The inspection shows:
- the window plan;
- the frozen reference, which inspection computes once per rule and K;
- per detector:
  - admission or refusal;
  - the null level m₀ = U_ref + δ;
  - α, taken from the declared target of false alarms per 30 days;
  - the planner's expected delay in units and days, including maturity;
  - power status;
  - formal or descriptive standing, with reasons;
- estimators and rules.

Confirming requires the inspection digest the operator saw. Confirmation supersedes the previously
confirmed version and creates that version's detectors. Detectors never carry state across versions:
a definition or reference change starts new detectors (R2.4).

A definition confirmed after its monitoring start is flagged ``added_after_observation``. Its
detectors consume only windows that start at or after confirmation, because they are valid
prospectively.
"""
import math
import time

from psycopg.types.json import Jsonb

from ...contracts import EvaluationError, digest
from ...history_contracts import instant
from . import eprocess, estimators, references, units as unit_rules

SCHEMA = 'confidenceguard.monitoring_definition/1.0'
DAY_NS = 86400 * 10**9
DEFAULTS = {'allowed_lateness_ns': str(6 * 3600 * 10**9), 'unit_design': 'entity_first', 'authority': 'supplied',
            'estimators': [], 'rules': [], 'drift_thresholds': {}, 'features': {}, 'cohorts': [], 'inclusion_tolerance': 0.1,
            'health': {}}


def _positive_ns(value, label):
    if not isinstance(value, (str, int)) or isinstance(value, bool) or not str(value).isdigit() or int(value) <= 0:
        raise EvaluationError(f'{label} must be a positive integer number of nanoseconds.', 'invalid_definition')
    return str(int(value))


def normalize(spec, models):
    """Validate a definition and fill defaults. ``models`` are the workspace variants (for resolution)."""
    if not isinstance(spec, dict):
        raise EvaluationError('A monitoring definition is a mapping.', 'invalid_definition')
    out = {**DEFAULTS, **spec, 'schema_version': spec.get('schema_version', SCHEMA)}
    if out['schema_version'] != SCHEMA:
        raise EvaluationError('Unsupported monitoring definition schema.', 'invalid_definition')
    instant(out.get('start') or '')
    out['window_ns'] = _positive_ns(out.get('window_ns'), 'window_ns')
    out['allowed_lateness_ns'] = str(int(out['allowed_lateness_ns']))
    maturity = out.get('maturity') or {}
    if maturity.get('policy') == 'equal_followup':
        maturity = {'policy': 'equal_followup', 'followup_ns': _positive_ns(maturity.get('followup_ns'), 'followup_ns')}
    elif maturity.get('policy') == 'mature_as_of':
        maturity = {'policy': 'mature_as_of', 'horizon_ns': _positive_ns(maturity.get('horizon_ns'), 'horizon_ns')}
    else:
        raise EvaluationError('Declare maturity: equal_followup (followup_ns) or mature_as_of (horizon_ns).',
                              'invalid_definition')
    out['maturity'] = maturity
    if out['unit_design'] not in ('entity_first', 'event'):
        raise EvaluationError('Unit design is entity_first or event.', 'invalid_definition')
    variants = [m['id'] for m in models]
    if out.get('variant') is None:
        if len(variants) != 1:
            raise EvaluationError('Name the monitored variant (the namespace has several).', 'variant_required')
        out['variant'] = variants[0]
    elif out['variant'] not in variants:
        raise EvaluationError('Unknown variant.', 'variant_unavailable')
    if not isinstance(out.get('reference'), dict):
        raise EvaluationError('Declare a reference rule (period ending before monitoring starts).', 'invalid_definition')
    detectors = out.get('detectors') or []
    if len({d.get('id') for d in detectors}) != len(detectors) or any(not d.get('id') for d in detectors):
        raise EvaluationError('Detectors need unique ids.', 'invalid_definition')
    for d in detectors:
        if 'delta' not in d or not isinstance(d['delta'], (int, float)) or d['delta'] < 0:
            raise EvaluationError('Every detector declares a nonnegative practical tolerance delta.', 'invalid_definition')
        if ('alpha' in d) == ('target_false_alarms_per_30_days' in d):
            raise EvaluationError('Declare exactly one of alpha or target_false_alarms_per_30_days.', 'invalid_definition')
        if ('target' in d) == ('shift' in d):
            raise EvaluationError('Declare the planned alternative: target (mean) or shift (above m0).', 'invalid_definition')
    for name in out['estimators']:
        if name not in estimators.ESTIMATORS:
            raise EvaluationError('Unknown estimator.', 'invalid_definition')
    for rule in out['rules']:
        if rule.get('op') not in ('>', '>=', '<', '<=') or 'measure' not in rule or 'id' not in rule:
            raise EvaluationError('Rules declare id, measure, op and value.', 'invalid_definition')
    from ..intelligence import regions as region_rules
    out['regions'] = region_rules.validate(out.get('regions'), out['features'])
    known = {r['id'] for r in out['regions']}
    for d in detectors:
        region = (d.get('params') or {}).get('region')
        if d['statistic'] == 'region_membership' and region is None:
            raise EvaluationError('region_membership names its region in params.', 'invalid_definition')
        if region is not None and region not in known:
            raise EvaluationError('A detector names an undeclared region.', 'invalid_definition')
    if out.get('policy') is not None:
        from ...policy_contracts import PolicySpec
        PolicySpec.from_dict(out['policy'])                     # frozen CG5 policy (its inputs are structural links)
    out['detectors'] = detectors
    return out


def maturity_ns(definition):
    m = definition['maturity']
    return int(m.get('followup_ns') or m.get('horizon_ns'))


def plan_detector(definition, detector, reference, task_kind, *, units_per_day_declared=None):
    """Admission, null level, alpha and the planner for one detector."""
    statistic = detector['statistic']
    plan = {'id': detector['id'], 'statistic': statistic, 'kind': 'sm1', 'reasons': []}
    admitted, reason = unit_rules.admit(statistic, task_kind)
    if not admitted:
        return {**plan, 'admitted': False, 'refusal': reason}
    plan['phase'] = unit_rules.STATISTICS[statistic]['phase']
    record = reference['packet']['statistics'].get(references.statistic_key(detector))
    if record is None or record['n'] == 0:
        return {**plan, 'admitted': False, 'refusal': 'reference_empty'}
    m0, standing = references.null_level(record, float(detector['delta']))
    if m0 is None or m0 >= 1:
        return {**plan, 'admitted': False, 'refusal': 'null_level_at_or_above_one'}
    if standing == 'descriptive':
        plan['reasons'].extend(record['reasons'] or ['reference_design_not_registered'])
    region = (detector.get('params') or {}).get('region')
    if region is not None:
        plan['region'] = region
        plan['region_source_standing'] = next(r['source_standing'] for r in definition['regions'] if r['id'] == region)
    if plan['phase'] == unit_rules.OUTCOME and definition['maturity']['policy'] != 'equal_followup':
        standing = 'descriptive'
        plan['reasons'].append('maturity_not_equal_followup')
    if definition['unit_design'] == 'event' and not definition.get('independent_units'):
        standing = 'descriptive'
        plan['reasons'].append('event_units_without_independence_declaration')
    included_per_day = record['units_per_day']
    if units_per_day_declared:
        included_per_day = float(units_per_day_declared) * (record['inclusion_rate'] or 0)
    if 'alpha' in detector:
        alpha = float(detector['alpha'])
    else:
        if not included_per_day:
            return {**plan, 'admitted': False, 'refusal': 'unknown_unit_rate'}
        alpha = float(detector['target_false_alarms_per_30_days']) / (30 * included_per_day)
    if not 0 < alpha < 1:
        return {**plan, 'admitted': False, 'refusal': 'invalid_alpha'}
    m1 = float(detector['target']) if 'target' in detector else m0 + float(detector['shift'])
    m1 = min(m1, 1.0)
    planner = eprocess.plan_detection(m0, m1, alpha, units_per_day=included_per_day or None)
    delay_days = planner.get('expected_delay_days')
    lag_days = (maturity_ns(definition) / DAY_NS) if plan['phase'] == unit_rules.OUTCOME else 0.0
    lag_days += int(definition['window_ns']) / DAY_NS
    total = None if delay_days is None or not math.isfinite(delay_days) else delay_days + lag_days
    max_days = float(detector.get('max_useful_delay_days', 30))
    power = 'adequate' if total is not None and total <= max_days else 'insufficient_power'
    if power == 'insufficient_power':
        standing = 'insufficient_power'
    return {**plan, 'admitted': True, 'standing': standing, 'm0': m0, 'm1': m1, 'alpha': alpha, 'delta': detector['delta'],
            'reference_upper': record['upper'], 'reference_mean': record['mean'], 'reference_n': record['n'],
            'reference_design': record['design'], 'alpha_ref': record['alpha_ref'],
            'included_units_per_day': included_per_day, 'planner': planner, 'maturity_and_window_lag_days': lag_days,
            'expected_total_delay_days': total, 'max_useful_delay_days': max_days, 'power': power,
            'expected_false_alarms_per_30_days': alpha * 30 * included_per_day if included_per_day else None,
            'false_alarm_statement': 'E[false alarms] <= alpha x included units; evaluated at observed volume it is an '
                                     'estimate of the right-hand side, not a realized-period guarantee.',
            'conditional_on_reference': f"Holds with probability >= 1 - {record['alpha_ref']} that the reference bound "
                                        'covers the reference mean, and assumes the reference is independent of the stream.',
            'params': detector.get('params') or {}}


def inspect(installation, deployment_id, spec, *, now_tick=None):
    """Record a new inspected version and return its inspection (with ``inspection_digest``)."""
    from . import context
    deployment = context.deployment(installation, deployment_id)
    ws = deployment['workspace']
    definition = normalize(spec, ws.models())
    reference = references.build(installation, deployment_id, definition, now_tick=now_tick)
    task = reference['packet']['metadata']['task']
    plans = [plan_detector(definition, d, reference, task['kind'],
                           units_per_day_declared=definition.get('expected_units_per_day')) for d in definition['detectors']]
    inspection = {'schema_version': 'confidenceguard.monitoring_inspection/1.0', 'deployment': deployment_id,
                  'variant': definition['variant'], 'catalog_sequence': reference['catalog_sequence'],
                  'reference': {'id': reference['id'], 'rule_digest': reference['rule_digest'],
                                'units': reference['packet']['selected_units'],
                                'inclusion': reference['packet']['inclusion'], 'evidence_use': reference['evidence_use_id']},
                  'windows': {'start': definition['start'], 'length_ns': definition['window_ns'],
                              'allowed_lateness_ns': definition['allowed_lateness_ns'],
                              'maturity': definition['maturity']},
                  'detectors': plans, 'estimators': definition['estimators'], 'rules': definition['rules'],
                  'family': {'expected_false_alarms_per_30_days': sum(p.get('expected_false_alarms_per_30_days') or 0
                                                                      for p in plans if p.get('admitted'))},
                  'refusals': [{'id': p['id'], 'reason': p['refusal']} for p in plans if not p.get('admitted')],
                  'qualifications': ['Absence of alarms is not evidence of health; see coverage and power status.',
                                     'Formal alarms concern the included matured observed-label population only.']}
    inspection_digest = digest({'definition': definition, 'inspection': inspection})
    scope = installation.scope
    with installation.db.transaction() as conn:
        conn.execute('SELECT 1 FROM ops_deployments WHERE org_id = %s AND id = %s FOR UPDATE', (scope.org_id, deployment_id))
        version = conn.execute('SELECT coalesce(max(version), 0) + 1 AS v FROM ops_monitoring_definitions '
                               'WHERE org_id = %s AND deployment_id = %s', (scope.org_id, deployment_id)).fetchone()['v']
        conn.execute('''INSERT INTO ops_monitoring_definitions(org_id, deployment_id, version, state, spec, spec_digest,
                            inspection, inspection_digest, reference_id)
                        VALUES (%s, %s, %s, 'inspected', %s, %s, %s, %s, %s)''',
                     (scope.org_id, deployment_id, version, Jsonb(definition), digest(definition), Jsonb(inspection),
                      inspection_digest, reference['id']))
    return {**inspection, 'version': version, 'inspection_digest': inspection_digest}


def confirm(installation, deployment_id, version, inspection_digest, *, actor='system', now_tick=None):
    """Confirm an inspected version exactly as inspected; supersede the previous one; create its detectors."""
    from . import windows
    now_tick = time.time_ns() if now_tick is None else int(now_tick)
    scope = installation.scope
    with installation.db.transaction() as conn:
        row = conn.execute('SELECT * FROM ops_monitoring_definitions WHERE org_id = %s AND deployment_id = %s AND version = %s '
                           'FOR UPDATE', (scope.org_id, deployment_id, version)).fetchone()
        if row is None:
            raise EvaluationError('Unknown definition version.', 'definition_unknown')
        if row['state'] != 'inspected':
            raise EvaluationError('Only an inspected version can be confirmed.', 'definition_state')
        if row['inspection_digest'] != inspection_digest:
            raise EvaluationError('The inspection changed since it was shown; inspect again.', 'stale_confirmation')
        definition, inspection = row['spec'], row['inspection']
        start = instant(definition['start'])
        length = int(definition['window_ns'])
        first = 0
        after = now_tick > start
        if after:                                           # prospective only: first window starting at/after now
            first = -(-(now_tick - start) // length)
        conn.execute("UPDATE ops_monitoring_definitions SET state = 'superseded', superseded_at = clock_timestamp() "
                     "WHERE org_id = %s AND deployment_id = %s AND state = 'confirmed'", (scope.org_id, deployment_id))
        conn.execute("UPDATE ops_monitoring_definitions SET state = 'confirmed', confirmed_at = clock_timestamp(), "
                     "confirmed_by = %s WHERE org_id = %s AND deployment_id = %s AND version = %s",
                     (actor, scope.org_id, deployment_id, version))
        for plan in inspection['detectors']:
            if not plan.get('admitted'):
                continue
            state = eprocess.EDetector(plan['m0'], plan['alpha']).state()
            plan = {**plan, 'first_window': first, 'added_after_observation': after,
                    'first_window_start': windows.iso(start + first * length)}
            conn.execute('''INSERT INTO ops_detectors(org_id, deployment_id, definition_version, detector_id, kind, phase,
                                standing, plan, state)
                            VALUES (%s, %s, %s, %s, 'sm1', %s, %s, %s, %s)''',
                         (scope.org_id, deployment_id, version, plan['id'], plan['phase'], plan['standing'], Jsonb(plan),
                          Jsonb(state)))
    references.order_secret(installation, deployment_id)
    return {'deployment': deployment_id, 'version': version, 'state': 'confirmed', 'first_window': first,
            'added_after_observation': after}


def start_recovery(installation, deployment_id, detector_id, *, claim, alpha, planned_support, statistic, delta=None,
                   theta=None, start_window=None, horizon_units=None, params=None, condition_id=None):
    """Start an SM2 recovery test (R2: fixed theta; R3: theta = L_ref + Delta) on the confirmed version.

    Verification uses only windows not yet evaluated in the statistic's phase (default: the next one), so the
    verification start is fixed before any of its units are seen.
    """
    current = confirmed(installation, deployment_id)
    if current is None:
        raise EvaluationError('No confirmed monitoring definition.', 'definition_unknown')
    phase = unit_rules.STATISTICS[statistic]['phase']
    with installation.db.connect() as conn:
        last = conn.execute('SELECT max(window_index) AS m FROM ops_window_evaluations WHERE org_id = %s AND deployment_id = %s '
                            'AND definition_version = %s AND phase = %s',
                            (installation.scope.org_id, deployment_id, current['version'], phase)).fetchone()['m']
    following = 0 if last is None else last + 1
    if start_window is None:
        start_window = following
    elif int(start_window) < following:
        raise EvaluationError('Recovery verification starts at a window not yet evaluated.', 'invalid_recovery')
    reference = references.load(installation, current['reference_id'])
    record = reference['packet']['statistics'].get(statistic)
    if claim == 'R2':
        if theta is None:
            raise EvaluationError('R2 declares the acceptable risk theta.', 'invalid_recovery')
        threshold = float(theta)
    elif claim == 'R3':
        if record is None or delta is None:
            raise EvaluationError('R3 needs the statistic in the reference and a margin Delta.', 'invalid_recovery')
        threshold = references.recovery_threshold(record, float(delta))
        if threshold is None:
            raise EvaluationError('The reference has no finite lower bound for this statistic (R3 unavailable).',
                                  'reference_design_not_registered')
    else:
        raise EvaluationError('Recovery claims are R2 or R3.', 'invalid_recovery')
    test = eprocess.RecoveryTest.planned(threshold, float(alpha), int(planned_support))
    plan = {'id': detector_id, 'kind': 'sm2', 'claim': claim, 'statistic': statistic, 'theta': threshold, 'alpha': alpha,
            'rho': test.rho, 'planned_support': planned_support, 'first_window': int(start_window), 'params': params or {},
            'phase': phase, 'delta': delta, 'horizon_units': horizon_units,
            'condition_id': None if condition_id is None else str(condition_id),
            'error_bound': alpha if claim == 'R2' else alpha + (record or {}).get('alpha_ref', 0),
            'interpretation': 'Average conditional risk of included units since the verification start, not current risk.'}
    with installation.db.transaction() as conn:
        conn.execute('''INSERT INTO ops_detectors(org_id, deployment_id, definition_version, detector_id, kind, phase, standing,
                            plan, state)
                        VALUES (%s, %s, %s, %s, 'sm2', %s, 'formal', %s, %s)''',
                     (installation.scope.org_id, deployment_id, current['version'], detector_id, plan['phase'], Jsonb(plan),
                      Jsonb(test.state())))
    return plan


def confirmed(installation, deployment_id):
    with installation.db.connect() as conn:
        row = conn.execute("SELECT * FROM ops_monitoring_definitions WHERE org_id = %s AND deployment_id = %s "
                           "AND state = 'confirmed'", (installation.scope.org_id, deployment_id)).fetchone()
    return None if row is None else dict(row)
