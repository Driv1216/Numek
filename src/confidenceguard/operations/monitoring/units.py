"""Detector units (plan G.1, G.3 as corrected by R2.4).

A **statistic** maps a selected window row to X in [0, 1], rescaled by its declared true bounds.

**Inclusion is predictable.** It uses only information available before the outcome value:
- the selected state;
- outcome availability and maturity;
- the unit design.

Units whose outcome value is invalid are excluded and counted; they are never filtered by value.

**Unit design.**
- ``entity_first`` (the default): the first eligible unit of each entity in a definition version.
- ``event``: every unit. Requires a declaration that units are independent.

**Unit order.** Units enter in window order, then in HMAC(secret, event key) order. This order is
deterministic and independent of X.
"""
import hashlib
import hmac

from ...contracts import EvaluationError, digest

OUTCOME = 'maturity'      # outcome-bearing: evaluated when the window's outcomes have matured
OUTCOME_FREE = 'close'    # outcome-free: evaluated when the window closes

STATISTICS = {
    'error': {'phase': OUTCOME, 'tasks': ('binary_classification', 'multiclass_classification'),
              'meaning': 'issued decision differs from the matured observed label'},
    'high_confidence_error': {'phase': OUTCOME, 'tasks': ('binary_classification', 'multiclass_classification'),
                              'meaning': 'error among issued decisions with confidence at or above the declared level'},
    'brier': {'phase': OUTCOME, 'tasks': ('binary_classification', 'multiclass_classification'),
              'meaning': 'Brier score rescaled by its true bound (1 binary, 2 multiclass)'},
    'abstention': {'phase': OUTCOME_FREE, 'tasks': None, 'meaning': 'output state is abstained'},
    'failure': {'phase': OUTCOME_FREE, 'tasks': None, 'meaning': 'output state is failed or missing'},
    'missing_field': {'phase': OUTCOME_FREE, 'tasks': None, 'meaning': 'a declared context field is missing'},
    'region_membership': {'phase': OUTCOME_FREE, 'tasks': None,
                          'meaning': 'the unit is a member of a frozen CG4 region (exposure; covariates only)'},
}
REFUSED = {'log_loss': 'unbounded_statistic', 'mse': 'unbounded_statistic', 'squared_error': 'unbounded_statistic',
           'absolute_error': 'unbounded_statistic'}
INVALID_OUTCOME_REASONS = ('missing_or_invalid_outcome',)


def admit(statistic, task_kind):
    """Return (admitted, reason)."""
    if statistic in REFUSED:
        return False, REFUSED[statistic]
    spec = STATISTICS.get(statistic)
    if spec is None:
        return False, 'unknown_statistic'
    if spec['tasks'] is not None and task_kind not in spec['tasks']:
        return False, 'statistic_task_mismatch'
    return True, None


def value(statistic, unit, *, classes=2, params=None):
    """X in [0, 1] for an included unit, else None (excluded; ``exclusion`` gives the reason)."""
    params = params or {}
    state = unit.get('state')
    if statistic in ('error', 'high_confidence_error'):
        if unit.get('decision') is None or state not in ('issued', 'hypothetical'):
            return None
        if statistic == 'high_confidence_error':
            confidence = unit.get('confidence')
            if confidence is None or confidence < params.get('confidence_at_least', 0.9):
                return None
        return 1.0 if unit['decision'] != unit['y'] else 0.0
    if statistic == 'brier':
        brier = unit.get('brier')
        if brier is None:
            return None
        bound = 1.0 if classes == 2 else 2.0
        x = float(brier) / bound
        if not 0 <= x <= 1:
            raise EvaluationError('A Brier score lies outside its declared true bound.', 'statistic_out_of_bounds')
        return x
    if statistic == 'abstention':
        return None if state is None else float(state == 'abstained')
    if statistic == 'failure':
        return None if state is None else float(state in ('failed', 'missing'))
    if statistic == 'missing_field':
        features = unit.get('features') or {}
        return float(features.get(params['field']) in (None, ''))
    if statistic == 'region_membership':
        member = (unit.get('regions') or {}).get(params['region'])
        return None if member is None else float(member)
    raise EvaluationError('Unknown statistic.', 'unknown_statistic')


def eligible(statistic, unit):
    """Predictable eligibility (no outcome value). Returns (eligible, exclusion reason or None)."""
    if STATISTICS[statistic]['phase'] == OUTCOME_FREE:
        return True, None
    if unit.get('outcome_valid'):
        return True, None
    reason = unit.get('outcome_reason') or 'no_matched_outcome'
    return False, 'invalid_outcome' if reason in INVALID_OUTCOME_REASONS else 'not_matured_or_unlabelled'


def order_key(secret, event_key):
    return hmac.new(secret, str(event_key).encode(), hashlib.sha256).digest()


def entity_hash(namespace, unit):
    entity = unit.get('entity_key') or unit.get('event_key')
    return bytes.fromhex(digest([namespace, entity]))


def event_hash(namespace, unit):
    return bytes.fromhex(digest([namespace, unit.get('event_key')]))


def stream(units, *, statistic, design, namespace, secret, seen_entities=frozenset(), seen_events=frozenset(),
           classes=2, params=None):
    """Ordered detector inputs for one window.

    Returns ``(values, admitted_entities, admitted_events, excluded)``:
    - ``values``: the X values in unit order;
    - ``admitted_entities`` / ``admitted_events``: the hashes these units add to the definition's
      admitted sets;
    - ``excluded``: counts by reason.
    """
    excluded = {}
    ordered = sorted(units, key=lambda u: order_key(secret, u['event_key']))
    values, entities, events = [], [], []
    seen_e, seen_v = set(seen_entities), set(seen_events)
    for unit in ordered:
        ev = event_hash(namespace, unit)
        if ev in seen_v:
            excluded['already_admitted'] = excluded.get('already_admitted', 0) + 1
            continue
        ok, reason = eligible(statistic, unit)
        if not ok:
            excluded[reason] = excluded.get(reason, 0) + 1
            continue
        region = (params or {}).get('region')
        if region is not None and statistic != 'region_membership':
            member = (unit.get('regions') or {}).get(region)        # restriction by covariates only (predictable)
            if member is not True:
                key = 'region_unavailable' if member is None else 'outside_region'
                excluded[key] = excluded.get(key, 0) + 1
                continue
        ent = entity_hash(namespace, unit)
        if design == 'entity_first' and ent in seen_e:
            excluded['entity_thinned'] = excluded.get('entity_thinned', 0) + 1
            continue
        x = value(statistic, unit, classes=classes, params=params)
        if x is None:
            excluded['not_applicable'] = excluded.get('not_applicable', 0) + 1
            continue
        values.append(x)
        seen_e.add(ent)
        seen_v.add(ev)
        entities.append(ent)
        events.append(ev)
    return values, entities, events, excluded


def summarize(values):
    n = len(values)
    return {'n': n, 'sum': float(sum(values)), 'mean': float(sum(values) / n) if n else None}
