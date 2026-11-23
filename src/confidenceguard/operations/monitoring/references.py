"""Frozen monitoring references (plan G.3, H.6, R2.4).

A reference is computed **once per reference version** and is immutable from then on.

**Rule.** It is fixed by a predeclared rule: a period ``[start, end)`` that ends no later than the
monitoring start, the definition's inclusion rule, and ``alpha_ref``. A reference chosen after
observing current data would be ``adaptive``. The rule's end therefore precedes the monitoring start.

**Governance.** It is read under its own reservation, with purpose ``reference``. Reference
outcomes become exposed, and the sealed reserve is never drawn from, because monitoring purposes
withhold reserve units.

**Packet contents.**
- Per detector statistic, the included-unit count and mean, and finite one-sided bounds under the
  registered design:
  - Clopper–Pearson for Bernoulli statistics with independent units;
  - Hoeffding for bounded means;
  - the CG6 bounded-cluster ratio when entities repeat under the ``event`` design and a true maximum
    per entity is declared.
- Inclusion rates (for comparability).
- The included-unit rate per day (for the planner).
- Per-cohort composition and within-group risks (for the composition projection).
- The frozen selected relation (Parquet), so that drift is computed with CG3's own distances.

Outside a registered design, a statistic's bounds are ``None`` and its detectors are descriptive.
"""
import base64
import math
import uuid

from psycopg.types.json import Jsonb

from ...contracts import EvaluationError, digest
from ...history_contracts import instant
from . import eprocess, packets, units as unit_rules, windows

MIN_REFERENCE_UNITS = 30


def order_secret(installation, deployment_id):
    """Per-deployment secret for the keyed unit order (created once; never stored in the database)."""
    import secrets as _secrets
    name = f'monitoring-order/{installation.scope.org_id}/{deployment_id}'
    if not installation.secrets.exists(name):
        installation.secrets.put(name, _secrets.token_bytes(32))
    return installation.secrets.get(name)


def rule_of(definition):
    reference = definition['reference']
    return {'period': [reference['start'], reference['end']], 'alpha': reference.get('alpha', 0.01),
            'variant': definition['variant'], 'maturity': definition['maturity'], 'unit_design': definition['unit_design'],
            'max_units_per_entity': definition.get('max_units_per_entity'), 'authority': definition.get('authority', 'supplied'),
            'cohorts': definition.get('cohorts', []), 'features': definition.get('features', {}),
            'statistics': sorted({(d['statistic'], digest(d.get('params') or {})) for d in definition['detectors']}),
            'params': {d['statistic']: d.get('params') or {} for d in definition['detectors']}}


def longitudinal_spec(definition, namespace, start, end, k, as_of, window_id='window'):
    from ...history_contracts import LongitudinalSpec
    maturity = definition['maturity']
    value = {'namespace': namespace, 'variants': [definition['variant']], 'as_of': as_of, 'catalog_sequence': k,
             'windows': [{'id': window_id, 'start': start, 'end': end}], 'features': definition.get('features', {}),
             'cohorts': definition.get('cohorts', []), 'authority': definition.get('authority', 'supplied'),
             'maturity': maturity['policy']}
    if maturity['policy'] == 'equal_followup':
        value['followup_ns'] = str(maturity['followup_ns'])
    return LongitudinalSpec.from_dict(value)


def build(installation, deployment_id, definition, *, now_tick=None):
    """Return the reference for this rule at the current K, computing it once (idempotent per rule and K)."""
    import time
    from ...execution_context import ctx
    from . import context
    deployment = context.deployment(installation, deployment_id)
    rule = rule_of(definition)
    start, end = rule['period']
    if instant(start) >= instant(end):
        raise EvaluationError('A reference period is a nonempty half-open interval.', 'invalid_reference')
    if instant(end) > instant(definition['start']):
        raise EvaluationError('The reference must end before monitoring starts (a rule fixed in advance).', 'adaptive_reference')
    ws = deployment['workspace']
    k = ws.status()['catalog_sequence']
    rule_digest = digest(rule)
    with installation.db.connect() as conn:
        row = conn.execute('SELECT * FROM ops_references WHERE org_id = %s AND deployment_id = %s AND rule_digest = %s '
                           'AND catalog_sequence = %s', (installation.scope.org_id, deployment_id, rule_digest, k)).fetchone()
    if row is not None:
        return load(installation, row['id'])
    now_tick = time.time_ns() if now_tick is None else int(now_tick)
    as_of = windows.iso(now_tick)
    spec = longitudinal_spec(definition, deployment['namespace'], start, end, k, as_of, window_id='reference')
    ticks = (instant(start), instant(end))
    lease, governance = windows.reserve_window(ws.catalog, namespace=deployment['namespace'], k=k, ticks=ticks,
                                               purpose='reference', metadata={'deployment': deployment_id})
    try:
        result = ctx.run(_evaluate_reference, (str(ws.path), spec, k, as_of, governance), spec.config).data
        if definition['variant'] not in result['variants']:
            raise EvaluationError('The reference period has no predictions of the monitored variant.', 'reference_empty')
        selected = result['variants'][definition['variant']]
        packet = summarize(installation, deployment_id, definition, deployment['namespace'], selected, rule, ticks)
        packet.update(rule=rule, rule_digest=rule_digest, catalog_sequence=k, as_of=as_of,
                      selection_digest=selected['selected_digest'], coverage=selected['coverage'],
                      metadata=_metadata(ws, definition['variant']))
        relation = base64.b64decode(selected.pop('relation'))
        packet_ref = packets.stage(installation, lease, deployment['catalog_id'], packets.encode(packet))
        relation_ref = packets.stage(installation, lease, deployment['catalog_id'], relation, packets.RELATION_CODEC)
        reference_id = uuid.uuid4()

        def write(conn):
            conn.execute('''INSERT INTO ops_references(org_id, id, deployment_id, rule, rule_digest, catalog_sequence, as_of,
                                packet_object, packet_digest, relation_object, evidence_use_id)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)''',
                         (installation.scope.org_id, reference_id, deployment_id, Jsonb(rule), rule_digest, k, as_of,
                          packet_ref.id, packets.packet_digest(packet), relation_ref.id, governance['reservation']['id']))
        packets.publish(installation, lease, deployment['catalog_id'], [packet_ref, relation_ref],
                        [governance['reservation']['id']], write)
    except BaseException:
        ws.catalog.finish_attempt(lease, failed=True)
        raise
    return load(installation, reference_id)


def _metadata(ws, variant):
    for model in ws.catalog.variants().items():
        if model[0] == variant:
            return {k: model[1][k] for k in ('task', 'run', 'signature', 'outcome_definition_version') if k in model[1]}
    raise EvaluationError('Unknown variant.', 'variant_unavailable')


def _evaluate_reference(root, spec, k, as_of, governance, progress=None):
    from ...result import Inspection
    return Inspection(windows.evaluate_window(root, spec, k, as_of, governance, cohort_scopes=False, export_relation=True,
                                              progress=progress), {'status': 'completed', 'peak_workspace_bytes': 0})


def summarize(installation, deployment_id, definition, namespace, selected, rule, ticks):
    """Finite bounds and rates for every declared statistic (deterministic in the keyed unit order)."""
    secret = order_secret(installation, deployment_id)
    rows = selected['units']
    classes = len(selected['task'].get('classes') or [0, 1])
    alpha_ref = float(rule['alpha'])
    days = (ticks[1] - ticks[0]) / 86400e9
    out = {'statistics': {}, 'selected_units': len(rows), 'period_days': days}
    labelled = sum(1 for u in rows if u.get('outcome_valid'))
    out['inclusion'] = {'label_availability_rate': labelled / len(rows) if rows else None,
                        'invalid_outcome_rate': (sum(1 for u in rows if u.get('outcome_reason') in unit_rules.INVALID_OUTCOME_REASONS)
                                                 / len(rows)) if rows else None}
    for statistic, params in rule['params'].items():
        if statistic not in unit_rules.STATISTICS:          # refused statistics are reported at inspection
            continue
        values, entities, _events, excluded = unit_rules.stream(rows, statistic=statistic, design=rule['unit_design'],
                                                                namespace=namespace, secret=secret, classes=classes,
                                                                params=params)
        out['statistics'][statistic] = bounds(values, entities, rule, alpha_ref, excluded=excluded, days=days,
                                              selected=len(rows))
    out['composition'] = composition(rows, definition, namespace, secret, classes, alpha_ref)
    return out


def bounds(values, entities, rule, alpha_ref, *, excluded, days, selected):
    n = len(values)
    record = {'n': n, 'mean': (sum(values) / n) if n else None, 'excluded': excluded, 'units_per_day': n / days if days else None,
              'inclusion_rate': n / selected if selected else None, 'alpha_ref': alpha_ref, 'upper': None, 'lower': None,
              'design': None, 'reasons': []}
    repeated = len(entities) - len(set(entities))
    record['repeated_entity_units'] = repeated
    if n < MIN_REFERENCE_UNITS:
        record['reasons'].append('insufficient_reference_support')
        return record
    bernoulli = all(v in (0.0, 1.0) for v in values)
    if rule['unit_design'] == 'event' and repeated:
        cap = rule.get('max_units_per_entity')
        if not cap:
            record['reasons'].append('repeated_entities_without_declared_maximum')
            return record
        from ...robustness.inference import cluster_ratio
        groups = {}
        for entity, value in zip(entities, values):
            numerator, denominator = groups.get(entity, (0.0, 0))
            groups[entity] = (numerator + value, denominator + 1)
        if max(d for _n, d in groups.values()) > cap:
            record['reasons'].append('declared_entity_maximum_exceeded')
            return record
        num = [g[0] for g in groups.values()]
        den = [g[1] for g in groups.values()]
        interval = cluster_ratio(num, den, max_size=int(cap), bounds=(0.0, 1.0), alpha=alpha_ref)
        if interval['state'] != 'available':
            record['reasons'].append(interval.get('reason', 'insufficient_reference_support'))
            return record
        record.update(design='bounded_cluster_ratio_hoeffding_v1', upper=float(interval['upper']),
                      lower=float(interval['lower']))
        return record
    if bernoulli:
        k = int(sum(values))
        record.update(design='clopper_pearson', upper=eprocess.clopper_pearson(k, n, alpha_ref, 'upper'),
                      lower=eprocess.clopper_pearson(k, n, alpha_ref, 'lower'))
    else:
        mean = sum(values) / n
        record.update(design='hoeffding', upper=eprocess.hoeffding(mean, n, alpha_ref, 'upper'),
                      lower=eprocess.hoeffding(mean, n, alpha_ref, 'lower'))
    return record


def composition(rows, definition, namespace, secret, classes, alpha_ref):
    """Reference shares and within-group issued-error risks for the first declared cohort (G.5 projection)."""
    cohorts = definition.get('cohorts') or []
    if not cohorts:
        return None
    groups = {}
    for unit in rows:
        groups.setdefault(unit.get('g0'), []).append(unit)
    labels = sorted(g for g in groups if g not in ('unretained', 'unresolved', None))
    split = alpha_ref / max(1, len(labels))                         # Bonferroni across groups
    out = {'cohort': cohorts[0]['id'], 'groups': {}, 'alpha_per_group': split}
    for label in labels:
        values, _e, _v, _x = unit_rules.stream(groups[label], statistic='error', design=definition['unit_design'],
                                               namespace=namespace, secret=secret, classes=classes)
        n = len(values)
        k = int(sum(values))
        out['groups'][label] = {'share': len(groups[label]) / len(rows), 'n': n, 'risk': k / n if n else None,
                                'upper': eprocess.clopper_pearson(k, n, split, 'upper') if n >= MIN_REFERENCE_UNITS else None,
                                'lower': eprocess.clopper_pearson(k, n, split, 'lower') if n >= MIN_REFERENCE_UNITS else None}
    return out


def load(installation, reference_id):
    with installation.db.connect() as conn:
        row = conn.execute('SELECT * FROM ops_references WHERE org_id = %s AND id = %s',
                           (installation.scope.org_id, reference_id)).fetchone()
    if row is None:
        raise EvaluationError('Unknown reference.', 'reference_unknown')
    packet = packets.read(installation, row['packet_object'])
    if packets.packet_digest(packet) != row['packet_digest']:
        raise EvaluationError('Reference packet differs from its record.', 'evidence_changed')
    return {'id': str(row['id']), 'rule_digest': row['rule_digest'], 'catalog_sequence': row['catalog_sequence'],
            'packet': packet, 'relation_object': row['relation_object'], 'evidence_use_id': row['evidence_use_id']}


def relation(installation, reference):
    """Frozen reference relation and its metadata for drift (``windows.evaluate_window(reference=...)``)."""
    data = packets.read(installation, reference['relation_object'])
    packet = reference['packet']
    return {'relation': data, 'metadata': packet['metadata'], 'coverage': packet['coverage']}


def null_level(statistic_record, delta):
    """m0 = U_ref + delta under a registered design (formal), else mean + delta (descriptive)."""
    if statistic_record['upper'] is not None:
        return statistic_record['upper'] + delta, 'formal'
    if statistic_record['mean'] is None:
        return None, 'descriptive'
    return statistic_record['mean'] + delta, 'descriptive'


def recovery_threshold(statistic_record, delta):
    """R3: theta = L_ref + Delta (a wide reference makes the claim harder)."""
    if statistic_record['lower'] is None:
        return None
    return min(1.0, statistic_record['lower'] + delta)


def finite(x):
    return x is not None and math.isfinite(x)
