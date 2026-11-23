"""Machine-checkable observations over an incident's evidence (plan I.3–I.5).

Each observation is ``True``, ``False`` or ``None`` (not evaluable) and carries:
- a standing (D, F, P, E or H);
- the evidence it used;
- when it is ``None``, a reason, plus an ETA or an action that would make it evaluable. These become the
  incident's information requirements.

Observations read the deployment's evidence over the incident's span: open conditions, window packets,
estimates and accountability records, identity standings and deployment events. They also read the results of
completed investigations, which may settle an observation that monitoring alone cannot. The rules are
deterministic and documented here, and they never read new outcome values.
"""
from datetime import datetime, timedelta, timezone

from ..monitoring import definitions, eprocess, packets, windows as window_math

COMPOSITION_TRUE, COMPOSITION_FALSE = 0.005, 0.002
WITHIN_ALPHA = 0.05
MIN_GROUP_UNITS = 30


def _ns(dt):
    return int(dt.timestamp() * 1e9)


def context(installation, incident_id):
    """The incident's deployment, definition, member and open conditions, and its window span."""
    scope = installation.scope
    with installation.db.connect() as conn:
        incident = dict(conn.execute('SELECT * FROM ops_incidents WHERE org_id = %s AND id = %s', (scope.org_id, incident_id)).fetchone())
        members = [dict(r) for r in conn.execute(
            '''SELECT c.* FROM ops_incident_conditions ic JOIN ops_conditions c ON c.org_id = ic.org_id AND c.id = ic.condition_id
               WHERE ic.org_id = %s AND ic.incident_id = %s AND ic.removed_at IS NULL''', (scope.org_id, incident_id)).fetchall()]
        conditions = [dict(r) for r in conn.execute(
            "SELECT * FROM ops_conditions WHERE org_id = %s AND deployment_id = %s AND state IN ('emerging', 'active', 'quiescent', 'recovered')",
            (scope.org_id, incident['deployment_id'])).fetchall()]
        current = conn.execute("SELECT * FROM ops_monitoring_definitions WHERE org_id = %s AND deployment_id = %s AND state = 'confirmed'",
                               (scope.org_id, incident['deployment_id'])).fetchone()
        reference = None
        if current is not None:
            from ..monitoring import references
            reference = references.load(installation, current['reference_id'])
    windows = sorted({w for c in members for w in (c['windows'] or [])})
    spec = current['spec'] if current else None
    span = None
    if spec and windows:
        span = (window_math.window_ticks(spec['start'], spec['window_ns'], windows[0])[0],
                window_math.window_ticks(spec['start'], spec['window_ns'], windows[-1])[1])
    elif members:
        first = min(c['first_signal_at'] for c in members)
        last = max(c['last_signal_at'] for c in members)
        span = (_ns(first - timedelta(days=1)), _ns(last + timedelta(days=1)))
    return {'incident': incident, 'members': members, 'conditions': conditions, 'definition': spec,
            'version': None if current is None else current['version'], 'reference': reference, 'windows': windows, 'span': span}


def _packets(installation, ctx, phase):
    if not ctx['windows'] or ctx['version'] is None:
        return []
    with installation.db.connect() as conn:
        rows = conn.execute('''SELECT DISTINCT ON (window_index) window_index, packet_object FROM ops_window_evaluations
                               WHERE org_id = %s AND deployment_id = %s AND definition_version = %s AND phase = %s
                                     AND window_index = ANY(%s) ORDER BY window_index, revision DESC''',
                            (installation.scope.org_id, ctx['incident']['deployment_id'], ctx['version'], phase,
                             ctx['windows'])).fetchall()
    return [(r['window_index'], packets.read(installation, r['packet_object'])) for r in rows]


def _maturity_eta(ctx):
    spec = ctx['definition']
    if not spec or not ctx['windows']:
        return None
    _start, end = window_math.window_ticks(spec['start'], spec['window_ns'], ctx['windows'][-1])
    due = end + definitions.maturity_ns(spec) + int(spec['allowed_lateness_ns'])
    return datetime.fromtimestamp(due / 1e9, tz=timezone.utc)


def _open(ctx, prefix):
    return [c for c in ctx['conditions'] if c['key'].startswith(prefix) and c['state'] in ('emerging', 'active', 'quiescent')]


def _statistic(ctx, condition):
    source, _, ident = condition['key'].partition(':')
    if source != 'detector' or not ctx['definition']:
        return None
    detector = next((d for d in ctx['definition'].get('detectors', []) if d['id'] == ident), None)
    return None if detector is None else detector['statistic']


def _result(value, standing, evidence=None, *, reason=None, eta=None, action=None):
    out = {'value': value, 'standing': standing, 'evidence': evidence or {}}
    if value is None:
        out.update(reason=reason or 'not_evaluable', eta=None if eta is None else eta.isoformat(), action=action)
    return out


# Observations ------------------------------------------------------------------------------------------------
def deployment_event(installation, ctx):
    if ctx['span'] is None:
        return _result(None, 'D', reason='no_incident_span')
    start = ctx['span'][0]
    with installation.db.connect() as conn:
        rows = conn.execute('''SELECT id, kind, at FROM ops_deployment_events WHERE org_id = %s AND deployment_id = %s
                               AND at <= to_timestamp(%s / 1e9) AND at >= to_timestamp(%s / 1e9) - interval '7 days' ORDER BY at''',
                            (installation.scope.org_id, ctx['incident']['deployment_id'], ctx['span'][1], start)).fetchall()
    return _result(bool(rows), 'D', {'events': [{'id': str(r['id']), 'kind': r['kind'], 'at': r['at'].isoformat()} for r in rows]})


def identity_change(installation, ctx):
    with installation.db.connect() as conn:
        rows = conn.execute('''SELECT DISTINCT ON (standing) standing, outcome FROM ops_identity_standings WHERE org_id = %s
                               AND deployment_id = %s ORDER BY standing, recorded_at DESC''',
                            (installation.scope.org_id, ctx['incident']['deployment_id'])).fetchall()
    outcomes = {r['standing']: r['outcome'] for r in rows}
    if any(v == 'failed' for v in outcomes.values()):
        return _result(True, 'D', {'standings': outcomes})
    if any(outcomes.get(k) == 'established' for k in ('registered', 'sampled_output_consistent', 'customer_signed_statement_verified')):
        return _result(False, 'D', {'standings': outcomes})
    return _result(None, 'D', {'standings': outcomes}, reason='identity_not_established',
                   action='Register the deployment identity (and a CG6 predictor spec for sampled output audits).')


def integrity(installation, ctx):
    found = [c['key'] for c in _open(ctx, 'health:batches_failed') + _open(ctx, 'rule:drift:feature:')]
    found += [c['key'] for c in _open(ctx, 'detector:') if _statistic(ctx, c) == 'missing_field']
    if found:
        return _result(True, 'D' if any(k.startswith('health') for k in found) else 'P', {'conditions': found})
    # No open integrity condition is not evidence of integrity: the contract diff settles it.
    return _result(None, 'D', reason='integrity_not_checked', action='Run the contract_diff investigation.')


def drift_feature(installation, ctx):
    if not (ctx['definition'] or {}).get('drift_thresholds'):
        return _result(None, 'P', reason='no_drift_thresholds_declared', action='Declare drift thresholds for retained features.')
    found = [c['key'] for c in _open(ctx, 'rule:drift:feature:')]
    return _result(bool(found), 'P', {'conditions': found})


def composition_shift(installation, ctx):
    reference = ctx['reference']
    comp = (reference or {}).get('packet', {}).get('composition') if reference else None
    if not comp:
        return _result(None, 'E', reason='no_reference_composition', action='Declare cohorts in the monitoring definition.')
    base = sum(g['share'] * g['risk'] for g in comp['groups'].values() if g['risk'] is not None)
    with installation.db.connect() as conn:
        rows = conn.execute('''SELECT window_index, value FROM ops_estimates WHERE org_id = %s AND deployment_id = %s AND definition_version = %s
                               AND estimator = 'composition_projection' AND window_index = ANY(%s) AND value IS NOT NULL''',
                            (installation.scope.org_id, ctx['incident']['deployment_id'], ctx['version'], ctx['windows'] or [])).fetchall()
    if not rows:
        return _result(None, 'E', reason='no_composition_projection',
                       action="Add the 'composition_projection' estimator to the monitoring definition.")
    delta = max(r['value'] for r in rows) - base
    value = True if delta >= COMPOSITION_TRUE else False if delta < COMPOSITION_FALSE else None
    return _result(value, 'E', {'projected_minus_reference': delta, 'assumption': 'unchanged_within_group_risk'},
                   reason='ambiguous_projection_change')


def within_group_change(installation, ctx):
    reference = ctx['reference']
    comp = (reference or {}).get('packet', {}).get('composition') if reference else None
    if not comp:
        return _result(None, 'P', reason='no_reference_composition', action='Declare cohorts in the monitoring definition.')
    matured = _packets(installation, ctx, 'maturity')
    if not matured:
        return _result(None, 'P', reason='outcomes_not_matured', eta=_maturity_eta(ctx))
    counts = {}
    for _w, packet in matured:
        for u in packet['units']:
            if u['outcome_valid'] and u['decision'] is not None and u['state'] in ('issued', 'hypothetical'):
                n, k = counts.get(u['group'], (0, 0))
                counts[u['group']] = (n + 1, k + (u['decision'] != u['y']))
    split = WITHIN_ALPHA / max(1, len(comp['groups']))
    groups, evaluable = {}, False
    for group, ref in comp['groups'].items():
        n, k = counts.get(group, (0, 0))
        if n < MIN_GROUP_UNITS or ref['upper'] is None:
            continue
        evaluable = True
        lower = eprocess.clopper_pearson(k, n, split, 'lower')
        groups[group] = {'n': n, 'rate': k / n, 'lower': lower, 'reference_upper': ref['upper'], 'exceeds': lower > ref['upper']}
    if not evaluable:
        return _result(None, 'P', {'groups': groups}, reason='insufficient_matured_group_support', eta=_maturity_eta(ctx))
    return _result(any(g['exceeds'] for g in groups.values()), 'P',
                   {'groups': groups, 'note': 'Descriptive comparison chosen after detection (no formal standing).'})


def calibration(installation, ctx):
    with installation.db.connect() as conn:
        rows = conn.execute('''SELECT estimator, window_index, matched FROM ops_estimates WHERE org_id = %s AND deployment_id = %s
                               AND definition_version = %s AND estimator IN ('implied_issued_error', 'implied_brier')
                               AND window_index = ANY(%s) AND matched IS NOT NULL''',
                            (installation.scope.org_id, ctx['incident']['deployment_id'], ctx['version'], ctx['windows'] or [])).fetchall()
    checked = [r for r in rows if r['matched'].get('exceedance') is not None]
    if not checked:
        return _result(None, 'E', reason='no_matched_accountability', eta=_maturity_eta(ctx))
    exceed = [r['window_index'] for r in checked if r['matched']['exceedance']]
    return _result(bool(exceed), 'E', {'exceeding_windows': exceed, 'checked': len(checked),
                                       'assumption': 'calibration_transfer'})


def error_alarm(installation, ctx):
    outcome = [c for c in ctx['conditions'] if _statistic(ctx, c) in ('error', 'high_confidence_error', 'brier')]
    if not outcome:
        has_detector = any(d['statistic'] in ('error', 'high_confidence_error', 'brier') for d in (ctx['definition'] or {}).get('detectors', []))
        if not has_detector:
            return _result(None, 'F', reason='no_outcome_detector', action='Add a matured-error or Brier detector.')
        if not _packets(installation, ctx, 'maturity'):
            return _result(None, 'F', reason='outcomes_not_matured', eta=_maturity_eta(ctx))
        return _result(False, 'F', {'conditions': []})
    return _result(True, max((c['standing'] for c in outcome), key='EPDF'.index), {'conditions': [c['key'] for c in outcome]})


def label_availability_shift(installation, ctx):
    matured = _packets(installation, ctx, 'maturity')
    if not matured:
        return _result(None, 'D', reason='outcomes_not_matured', eta=_maturity_eta(ctx))
    tolerance = float((ctx['definition'] or {}).get('inclusion_tolerance', 0.1))
    gaps = {w: (p['label_availability_rate'], p['reference_label_availability_rate']) for w, p in matured
            if p.get('label_availability_rate') is not None and p.get('reference_label_availability_rate') is not None}
    if not gaps:
        return _result(None, 'D', reason='no_label_availability_rate')
    shifted = {w: v for w, v in gaps.items() if abs(v[0] - v[1]) > tolerance}
    return _result(bool(shifted), 'D', {'windows': {str(w): v for w, v in gaps.items()}, 'tolerance': tolerance})


def monitoring_health(installation, ctx):
    found = [c['key'] for c in _open(ctx, 'health:')]
    return _result(bool(found), 'D', {'conditions': found})


def region_exposure(installation, ctx):
    detectors = [d for d in (ctx['definition'] or {}).get('detectors', []) if d['statistic'] == 'region_membership']
    if not detectors:
        return _result(None, 'F', reason='no_region_exposure_detector', action='Declare frozen CG4 regions and exposure detectors.')
    found = [c['key'] for c in ctx['conditions'] if _statistic(ctx, c) == 'region_membership']
    return _result(bool(found), 'F', {'conditions': found})


def multiple_deployments(installation, ctx):
    keys = {c['key'] for c in ctx['members']}
    with installation.db.connect() as conn:
        rows = conn.execute('''SELECT DISTINCT c.deployment_id FROM ops_conditions c JOIN ops_deployments d ON d.org_id = c.org_id AND d.id = c.deployment_id
                               JOIN ops_deployments me ON me.org_id = d.org_id AND me.system_id = d.system_id AND me.id = %s
                               WHERE c.org_id = %s AND c.deployment_id <> %s AND c.key = ANY(%s)
                                     AND c.state IN ('emerging', 'active', 'quiescent')''',
                            (ctx['incident']['deployment_id'], installation.scope.org_id, ctx['incident']['deployment_id'], list(keys))).fetchall()
    return _result(bool(rows), 'D', {'deployments': [r['deployment_id'] for r in rows]})


def policy_change(installation, ctx):
    if not (ctx['definition'] or {}).get('policy'):
        return _result(None, 'D', reason='no_policy_declared', action='Declare the frozen CG5 policy in the monitoring definition.')
    event = deployment_event(installation, ctx)
    changes = [e for e in event['evidence'].get('events', []) if e['kind'] == 'configuration_change']
    return _result(bool(changes), 'D', {'events': changes})


def domain_shift(installation, ctx):
    return _result(None, 'P', reason='requires_domain_classifier_investigation',
                   action='Run the domain_classifier investigation (covariates only).')


def uncertainty(installation, ctx):
    return _result(None, 'P', reason='coverage_statistics_not_monitored',
                   action='Coverage-miss statistics for interval and set outputs are not yet monitored.')


OBSERVATIONS = {
    'O-deploy-event': deployment_event, 'O-identity-change': identity_change, 'O-integrity': integrity,
    'O-drift-feature': drift_feature, 'O-composition-shift': composition_shift, 'O-within-group-change': within_group_change,
    'O-calibration': calibration, 'O-error-alarm': error_alarm, 'O-label-availability-shift': label_availability_shift,
    'O-monitoring-health': monitoring_health, 'O-region-exposure': region_exposure,
    'O-multiple-deployments': multiple_deployments, 'O-policy-change': policy_change, 'O-uncertainty': uncertainty,
    'O-domain-shift': domain_shift,
}


def evaluate(installation, incident_id):
    """All observations for an incident, with completed investigation results applied on top."""
    ctx = context(installation, incident_id)
    out = {name: fn(installation, ctx) for name, fn in OBSERVATIONS.items()}
    with installation.db.connect() as conn:
        runs = conn.execute('''SELECT DISTINCT ON (template) template, id, result FROM ops_investigation_runs WHERE org_id = %s
                               AND incident_id = %s AND state IN ('completed', 'reused') ORDER BY template, created_at DESC''',
                            (installation.scope.org_id, incident_id)).fetchall()
    for run in runs:
        for name, value in ((run['result'] or {}).get('observations') or {}).items():
            if name in out and value.get('value') is not None:
                out[name] = {**value, 'evidence': {**value.get('evidence', {}), 'investigation': str(run['id']), 'template': run['template']}}
    return ctx, out

