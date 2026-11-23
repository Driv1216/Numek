"""Window measures (plan G.2, H.6).

Window measures reuse the CG1, CG2 and CG3 reducers unchanged:
- ``longitudinal._evaluate`` on the window's ``HistoryStore``, which gives distributions, availability,
  performance, calibration and CG2 losses;
- CG3 ``_drift`` against the frozen reference relation, which gives KS, W1, TV and JS distances with
  CG3's own refusals.

Rules over these measures are descriptive (P) or deterministic (D), never formal.
"""
import io
from types import SimpleNamespace


def drift_against_reference(work, spec, store, reference):
    """CG3 distribution effects of this window against the frozen reference relation (same DuckDB work)."""
    import pyarrow.parquet as pq
    from ...contracts import PredictionRunSpec, TaskDefinition
    from ...history_contracts import HistoricalComparison
    from ...longitudinal import _drift
    table = 'monitoring_reference_relation'
    arrow = pq.read_table(io.BytesIO(reference['relation']))
    work.con.register('monitoring_reference_arrow', arrow)
    try:
        work.con.execute(f'CREATE OR REPLACE TABLE {table} AS SELECT * FROM monitoring_reference_arrow')
    finally:
        work.con.unregister('monitoring_reference_arrow')
    metadata = reference['metadata']
    left = SimpleNamespace(con=work.con, work=work, table=table, metadata=metadata,
                           run=PredictionRunSpec.from_dict(metadata['run']),
                           spec=SimpleNamespace(task=TaskDefinition.from_dict(metadata['task'])),
                           coverage=reference['coverage'])
    edge = HistoricalComparison('reference_drift', 'reference', spec.windows[0].id, store.variant, store.variant)
    return _drift(left, store, spec, edge)


def flat(measurements):
    """{'scope/metric': {'value', 'denominator'}} for overall and cohort scopes (rules and the console)."""
    out = {}
    for m in measurements:
        if m.get('value') is None and m.get('denominator') is None:
            continue
        key = f"{m.get('scope')}/{m.get('metric')}"
        out.setdefault(key, {'value': m.get('value'), 'denominator': m.get('denominator')})
    return out


OPERATORS = {'>': lambda a, b: a > b, '>=': lambda a, b: a >= b, '<': lambda a, b: a < b, '<=': lambda a, b: a <= b}


def evaluate_rules(rules, measures, drift, *, drift_thresholds=None):
    """Deterministic threshold rules (standing D or P) and CG3 drift prioritization (P). Returns signals."""
    from ...history_metrics import prioritize_drift
    signals = []
    for rule in rules or ():
        found = measures.get(f"{rule.get('scope', 'overall')}/{rule['measure']}")
        if found is None or found['value'] is None:
            signals.append({'source_id': rule['id'], 'standing': 'D', 'severity': 'info', 'kind': 'rule_unevaluable',
                            'payload': {'rule': rule, 'reason': 'measure_unavailable'}})
            continue
        if found['denominator'] is not None and found['denominator'] < rule.get('min_denominator', 1):
            continue
        if OPERATORS[rule['op']](float(found['value']), float(rule['value'])):
            signals.append({'source_id': rule['id'], 'standing': rule.get('standing', 'P'),
                            'severity': rule.get('severity', 'medium'), 'kind': 'threshold_exceeded',
                            'payload': {'rule': rule, 'observed': found}})
    for item in drift or ():
        if drift_thresholds and item.get('status') == 'completed' and prioritize_drift(item, drift_thresholds):
            signals.append({'source_id': f"drift:{item['field']}", 'standing': 'P', 'severity': 'medium',
                            'kind': 'distribution_change',
                            'payload': {'field': item['field'], 'prioritization': item.get('prioritization'),
                                        'interpretation': 'Declared distribution-effect threshold exceeded; descriptive '
                                                          'materiality, not statistical confirmation or degradation.'}})
    return signals
