"""Discriminating investigation templates (plan I.6): CG2–CG6 adapters and operational checks.

**Each template declares:**
- the hypotheses it discriminates;
- its tier:
  - ``auto``: descriptive, small, and no new outcome exposure beyond what monitoring already recorded;
  - ``confirm``: execution, fitting or large; needs an operator approval;
  - ``restricted``: reserve or E/H consumption; never automatic, needs ``reserve:consume``;
- a cost in compute minutes;
- an eligibility check that returns a reason;
- an executor.

**Executors** return a summary and the observations they settle. Settled observations override monitoring-only
observations in the differential matrix, keeping the investigation's id and standing.

**Templates that cannot execute here** refuse with an explicit reason, never silently:
- the CG5 replay needs an operator-authored replay specification;
- the recalibration and uncertainty studies are restricted and arrive with S8.
"""
from ...contracts import EvaluationError, digest
from ..monitoring import windows as window_math
from . import observations as observation_rules


def _iso(tick):
    return window_math.iso(int(tick))


# Executors -----------------------------------------------------------------------------------------------------
def contract_diff(installation, ctx, spec):
    """Contract versions, quarantine reasons and feature retention: incident span against the reference period."""
    scope = installation.scope
    from ...history_contracts import instant
    reference = ctx['reference']['packet']
    start, end = ctx['span']
    ref_start, ref_end = instant(ctx['definition']['reference']['start']), instant(ctx['definition']['reference']['end'])
    with installation.db.connect() as conn:
        sources = [r['id'] for r in conn.execute("SELECT id FROM ops_sources WHERE org_id = %s AND deployment_id = %s GROUP BY id",
                                                 (scope.org_id, ctx['incident']['deployment_id'])).fetchall()]

        def batches(a, b):
            return conn.execute('''SELECT contract_version, counts FROM ops_batches WHERE org_id = %s AND source_id = ANY(%s)
                                   AND received_at >= to_timestamp(%s / 1e9) AND received_at < to_timestamp(%s / 1e9)''',
                                (scope.org_id, sources, a, b)).fetchall()
        now_rows, ref_rows = batches(start, end), batches(ref_start, ref_end)
    versions_now = sorted({r['contract_version'] for r in now_rows})
    versions_ref = sorted({r['contract_version'] for r in ref_rows})

    def rate(rows):
        received = sum(int((r['counts'] or {}).get('rows_received', 0)) for r in rows)
        quarantined = sum(int((r['counts'] or {}).get('rows_quarantined', 0)) for r in rows)
        return (quarantined / received) if received else None
    retention = {}
    for _w, packet in observation_rules._packets(installation, ctx, 'close'):
        cov = packet.get('coverage') or {}
        total = cov.get('selected_predictions') or 0
        for feature, kept in (cov.get('feature_retention') or {}).items():
            a, b = retention.get(feature, (0, 0))
            retention[feature] = (a + kept, b + total)
    ref_cov = reference.get('coverage') or {}
    ref_total = ref_cov.get('selected_predictions') or 0
    drops = {}
    for feature, (kept, total) in retention.items():
        ref_rate = (ref_cov.get('feature_retention', {}).get(feature, 0) / ref_total) if ref_total else None
        now_rate = kept / total if total else None
        if ref_rate is not None and now_rate is not None:
            drops[feature] = {'reference': ref_rate, 'incident': now_rate, 'drop': ref_rate - now_rate}
    q_now, q_ref = rate(now_rows), rate(ref_rows)
    changed_contract = bool(set(versions_now) - set(versions_ref)) and bool(versions_ref)
    quarantine_rose = q_now is not None and q_now >= 0.01 and (q_ref is None or q_now > 2 * q_ref)
    retention_fell = any(d['drop'] > 0.05 for d in drops.values())
    finding = changed_contract or quarantine_rose or retention_fell
    summary = {'contract_versions': {'incident': versions_now, 'reference': versions_ref}, 'quarantine_rate': {'incident': q_now, 'reference': q_ref},
               'feature_retention': drops, 'contract_changed': changed_contract, 'quarantine_rose': quarantine_rose,
               'retention_fell': retention_fell}
    return {'summary': summary, 'observations': {'O-integrity': {'value': finding, 'standing': 'D', 'evidence': summary}}}


def label_availability_audit(installation, ctx, spec):
    matured = observation_rules._packets(installation, ctx, 'maturity')
    tolerance = float(ctx['definition'].get('inclusion_tolerance', 0.1))
    by_group = {}
    rows = []
    for window, packet in matured:
        units = packet['units']
        rate = sum(1 for u in units if u['outcome_valid']) / len(units) if units else None
        rows.append({'window': window, 'rate': rate, 'reference': packet.get('reference_label_availability_rate')})
        for u in units:
            a, b = by_group.get(u['group'], (0, 0))
            by_group[u['group']] = (a + bool(u['outcome_valid']), b + 1)
    shifted = [r for r in rows if r['rate'] is not None and r['reference'] is not None and abs(r['rate'] - r['reference']) > tolerance]
    value = None if not rows else bool(shifted)
    summary = {'windows': rows, 'by_group': {str(g): a / b for g, (a, b) in by_group.items() if b}, 'tolerance': tolerance}
    out = {'summary': summary, 'observations': {}}
    if value is not None:
        out['observations']['O-label-availability-shift'] = {'value': value, 'standing': 'D', 'evidence': summary}
    return out


def monitoring_health_review(installation, ctx, spec):
    from ..monitoring import health
    report = health.report(installation, ctx['incident']['deployment_id'])
    multi = observation_rules.multiple_deployments(installation, ctx)
    return {'summary': {'health': report, 'other_deployments': multi['evidence']},
            'observations': {'O-monitoring-health': {'value': bool(report['conditions']), 'standing': 'D',
                                                     'evidence': {'conditions': report['conditions']}},
                             'O-multiple-deployments': multi}}


def cg3_mix(installation, ctx, spec):
    """CG3 longitudinal analysis: the reference period against the incident span, with the definition's cohorts.

    The mix/within decomposition separates composition from within-group change (descriptive, P)."""
    from ..monitoring import context as deployment_context
    from ...history_contracts import LongitudinalSpec
    definition = ctx['definition']
    if not definition.get('cohorts'):
        raise EvaluationError('The mix decomposition needs declared cohorts.', 'template_ineligible')
    deployment = deployment_context.deployment(installation, ctx['incident']['deployment_id'])
    ws = deployment['workspace']
    start, end = ctx['span']
    value = {'namespace': deployment['namespace'], 'variants': [definition['variant']], 'as_of': spec['as_of'],
             'windows': [{'id': 'reference', 'start': definition['reference']['start'], 'end': definition['reference']['end']},
                         {'id': 'incident', 'start': _iso(start), 'end': _iso(end)}],
             'comparisons': [{'id': 'incident_change', 'reference_window': 'reference', 'current_window': 'incident',
                              'reference_variant': definition['variant'], 'current_variant': definition['variant']}],
             'features': definition.get('features', {}), 'cohorts': definition['cohorts'],
             'maturity': definition['maturity']['policy'], 'authority': definition.get('authority', 'supplied')}
    if definition['maturity']['policy'] == 'equal_followup':
        value['followup_ns'] = str(definition['maturity']['followup_ns'])
    result = ws.analyze(LongitudinalSpec.from_dict(value), request_id=spec['request_id'])
    mix = next((m for m in result.data['history']['mix'] if m['metric'] in ('error_rate', 'accuracy')), None)
    summary = {'analysis_id': result.data['analysis_id'], 'mix': mix}
    observations = {}
    if mix and mix.get('status') == 'completed' and mix.get('aggregate_delta'):
        sign = 1 if mix['metric'] == 'error_rate' else -1                 # accuracy falls when risk rises
        aggregate, composition, within = sign * mix['aggregate_delta'], sign * mix['mix'], sign * mix['within']
        if aggregate > 0:
            observations['O-composition-shift'] = {'value': composition >= 0.5 * aggregate, 'standing': 'P', 'evidence': summary}
            observations['O-within-group-change'] = {'value': within >= 0.5 * aggregate, 'standing': 'P', 'evidence': summary}
    return {'summary': summary, 'observations': observations}


def cg6_shadow_replay(installation, ctx, spec):
    """Sampled output-consistency audit of logged rows in the incident span against the registered CG6 predictor."""
    from .. import identity, ingest, registry
    from ..contracts import SourceContract, parse
    scope = installation.scope
    if not spec.get('logged_outputs'):
        raise EvaluationError('Name the logged output fields (logged_outputs) when approving the replay.', 'template_spec_required')
    start, end = ctx['span']
    rows = []
    with installation.db.connect() as conn:
        batches = conn.execute('''SELECT b.* FROM ops_batches b JOIN ops_sources s ON s.org_id = b.org_id AND s.id = b.source_id
                                  AND s.version = b.contract_version WHERE b.org_id = %s AND s.deployment_id = %s
                                  AND b.state = 'published' ORDER BY b.received_at''',
                               (scope.org_id, ctx['incident']['deployment_id'])).fetchall()
    key_columns = None
    for batch in batches:
        source = registry.source(installation, batch['source_id'], batch['contract_version'])
        contract = SourceContract.from_dict(source['contract'])
        try:
            body = ingest._decrypt(installation, scope, batch)
        except Exception:
            continue                                                     # raw body past retention
        parsed = parse(contract, body)
        ticks = ingest._ticks(contract, parsed)
        rows += [r for r, t in zip(parsed, ticks) if t is not None and start <= t < end]
        key_columns = [name for name, field in contract.fields.items() if field.get('identity')]
    if not rows:
        raise EvaluationError('No retained raw rows in the incident span to replay.', 'template_data_unavailable')
    audit = identity.audit_outputs(installation, ctx['incident']['deployment_id'], rows, key_columns=key_columns,
                                   logged_outputs=spec['logged_outputs'], scratch=spec['scratch'])
    failed = audit.get('outcome') == 'failed'
    return {'summary': audit, 'observations': {'O-identity-change': {'value': failed, 'standing': 'D', 'evidence': audit}}}


def domain_classifier(installation, ctx, spec):
    from . import domain
    return domain.investigate(installation, ctx, spec)


def label_acquisition_guidance(installation, ctx, spec):
    from . import guidance
    return {'summary': guidance.label_guidance(installation, ctx, spec), 'observations': {}}


def _refuse(code, message):
    def run(installation, ctx, spec):
        raise EvaluationError(message, code)
    return run


# Eligibility ---------------------------------------------------------------------------------------------------
def _eligible_always(installation, ctx):
    return (ctx['definition'] is not None and ctx['span'] is not None), 'no confirmed definition or incident span'


def _eligible_cohorts(installation, ctx):
    ok, reason = _eligible_always(installation, ctx)
    if not ok:
        return ok, reason
    return bool(ctx['definition'].get('cohorts')), 'no cohorts declared'


def _eligible_matured(installation, ctx):
    ok, reason = _eligible_always(installation, ctx)
    if not ok:
        return ok, reason
    return bool(observation_rules._packets(installation, ctx, 'maturity')), 'incident windows have not matured'


def _eligible_predictor(installation, ctx):
    from .. import registry
    dep = registry.deployment(installation, ctx['incident']['deployment_id'])
    return bool((dep['registered_identity'] or {}).get('predictor_spec')), 'no registered CG6 predictor spec'


def _eligible_policy(installation, ctx):
    return bool((ctx['definition'] or {}).get('policy')), 'no frozen CG5 policy declared'


def _never(installation, ctx):
    return False, 'restricted or not monitored'


TEMPLATES = {
    'contract_diff': {'tier': 'auto', 'cost': 1.0, 'cost_class': 'small', 'discriminates': ('H-INTEG',),
                      'eligible': _eligible_always, 'run': contract_diff},
    'label_availability_audit': {'tier': 'auto', 'cost': 1.0, 'cost_class': 'small', 'discriminates': ('H-LABEL',),
                                 'eligible': _eligible_matured, 'run': label_availability_audit},
    'monitoring_health_review': {'tier': 'auto', 'cost': 0.5, 'cost_class': 'small', 'discriminates': ('H-MON', 'H-MULTI'),
                                 'eligible': _eligible_always, 'run': monitoring_health_review},
    'cg3_mix_decomposition': {'tier': 'auto', 'cost': 5.0, 'cost_class': 'medium', 'discriminates': ('H-COMP', 'H-WITHIN'),
                              'eligible': _eligible_cohorts, 'run': cg3_mix},
    'cg3_cohort_contrast': {'tier': 'auto', 'cost': 5.0, 'cost_class': 'medium', 'discriminates': ('H-WITHIN', 'H-COMP'),
                            'eligible': _eligible_cohorts, 'run': cg3_mix, 'same_analysis_as': 'cg3_mix_decomposition'},
    'domain_classifier': {'tier': 'auto', 'cost': 5.0, 'cost_class': 'medium', 'discriminates': ('H-COMP', 'H-INTEG'),
                          'eligible': _eligible_always, 'run': domain_classifier},
    'label_acquisition_guidance': {'tier': 'auto', 'cost': 0.5, 'cost_class': 'small', 'discriminates': (),
                                   'supports_requirements': ('O-within-group-change', 'O-calibration'),
                                   'eligible': _eligible_cohorts, 'run': label_acquisition_guidance},
    'cg6_shadow_replay': {'tier': 'confirm', 'cost': 10.0, 'cost_class': 'large', 'discriminates': ('H-DEPLOY',),
                          'eligible': _eligible_predictor, 'run': cg6_shadow_replay},
    'cg5_policy_replay': {'tier': 'confirm', 'cost': 10.0, 'cost_class': 'large', 'discriminates': ('H-POLICY',),
                          'eligible': _eligible_policy,
                          'run': _refuse('operator_specification_required',
                                         'A CG5 replay needs an operator-authored replay specification (ReliabilityWorkspace.replay_policy).')},
    'cg2_recalibration_study': {'tier': 'restricted', 'cost': 30.0, 'cost_class': 'large', 'discriminates': ('H-CALIB',),
                                'eligible': _eligible_matured,
                                'run': _refuse('restricted_study', 'A recalibration study fits on development windows and is '
                                                                   'assessed through a restricted reserve study (S8).')},
    'cg2_uncertainty_study': {'tier': 'restricted', 'cost': 30.0, 'cost_class': 'large', 'discriminates': ('H-UNC',),
                              'eligible': _never,
                              'run': _refuse('not_monitored', 'Coverage statistics are not yet monitored.')},
}
COST_ORDER = {'small': 0, 'medium': 1, 'large': 2}


def spec_for(template, ctx, now):
    """The deterministic template spec and its selection digest (incident windows, reference, definition)."""
    selection = digest({'deployment': ctx['incident']['deployment_id'], 'windows': ctx['windows'], 'span': list(ctx['span'] or []),
                        'reference': (ctx['reference'] or {}).get('id'), 'version': ctx['version']})
    return {'template': template, 'incident': str(ctx['incident']['id']), 'as_of': now.isoformat(),
            'selection_digest': selection}

