"""Evidence association (plan I.1): typed links between conditions, each with an explicit strength.

| Strength | Meaning |
|---|---|
| ``exact`` | Both conditions follow the same recorded deployment event (identity or event precedes onset). |
| ``structural`` | The conditions depend on a shared frozen input. |
| ``population_overlap`` | The Jaccard similarity of their evaluated window populations. |
| ``temporal`` | Overlapping time only; a suggestion, never a join. |

Structural inputs come from:
- CG4 gate features (region-restricted statistics);
- CG5 policy predicate inputs (decision-based statistics, when the definition declares the frozen policy);
- CG6 predictor-spec inputs (overall performance statistics, when the deployment registers a predictor spec);
- the fields of missing-field detectors, drift rules and cohort rules.

**A structural dependency is not a common cause.** It says only that two conditions read the same input, and
every link records the inputs it shares.
"""
from ..monitoring import units as unit_rules

DECISION_STATISTICS = ('error', 'high_confidence_error', 'abstention')
MODEL_STATISTICS = ('error', 'high_confidence_error', 'brier', 'abstention', 'failure')


def policy_inputs(policy):
    """Field inputs and region digests a frozen CG5 policy reads (walks every predicate and value reference)."""
    fields, regions = set(), set()

    def visit(value):
        if isinstance(value, dict):
            if value.get('kind') == 'field' and isinstance(value.get('target'), str):
                fields.add(value['target'])
            if value.get('kind') == 'region' and isinstance(value.get('digest'), str):
                regions.add(value['digest'])
            for item in value.values():
                visit(item)
        elif isinstance(value, list):
            for item in value:
                visit(item)
    visit(policy.get('nodes') if policy else None)
    return fields, regions


def predictor_inputs(registered_identity):
    spec = (registered_identity or {}).get('predictor_spec')
    if not spec:
        return set()
    return {i['column'] if isinstance(i, dict) and 'column' in i else i['id'] for i in spec.get('inputs', []) if isinstance(i, dict)}


def dependencies(condition, definition, registered_identity):
    """{'inputs': set of field names, 'artifacts': [...]} that a condition structurally depends on."""
    source, _, ident = condition['key'].partition(':')
    out, artifacts = set(), []
    if not definition:
        return {'inputs': out, 'artifacts': artifacts}
    regions = {r['id']: r for r in definition.get('regions') or []}
    if source == 'detector':
        detector = next((d for d in definition.get('detectors', []) if d['id'] == ident), None)
        if detector is not None:
            params = detector.get('params') or {}
            statistic = detector['statistic']
            if statistic == 'missing_field':
                out.add(params['field'])
            region = params.get('region')
            if region in regions:
                out |= set(regions[region]['artifact']['features'])
                artifacts.append({'kind': 'cg4_region', 'digest': regions[region]['artifact']['artifact_digest'],
                                  'source_standing': regions[region]['source_standing']})
            elif statistic in MODEL_STATISTICS and statistic in unit_rules.STATISTICS:
                inputs = predictor_inputs(registered_identity)
                if inputs:
                    out |= inputs
                    artifacts.append({'kind': 'cg6_predictor_spec', 'inputs': sorted(inputs)})
            if statistic in DECISION_STATISTICS and definition.get('policy'):
                fields, region_digests = policy_inputs(definition['policy'])
                out |= fields
                artifacts.append({'kind': 'cg5_policy', 'inputs': sorted(fields), 'regions': sorted(region_digests)})
    elif source == 'rule':
        if ident.startswith('drift:feature:'):
            out.add(ident[len('drift:feature:'):])
        rule = next((r for r in definition.get('rules', []) if r['id'] == ident), None)
        if rule and str(rule.get('scope', '')).startswith('cohort_'):
            index = int(rule['scope'].split('/')[0].split('_')[1])
            cohorts = definition.get('cohorts') or []
            if index < len(cohorts):
                out.add(cohorts[index]['column'])
    return {'inputs': out, 'artifacts': artifacts}


def structural(a, b):
    shared = sorted(a['inputs'] & b['inputs'])
    if not shared:
        return None
    return {'strength': 'structural', 'shared_inputs': shared,
            'artifacts': [x for x in a['artifacts'] + b['artifacts']],
            'qualification': 'A structural dependency is not a common cause.'}
