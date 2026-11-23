"""Outcome-free estimators (standing E) and the matched-population accountability ledger (plan G.5).

**Model-implied estimands follow the decision semantics.**
- ``implied_issued_error``: the mean over *issued* units of 1 − p_d(x), where d is the issued decision
  and the class order is the declared one. Abstentions are excluded. Assumption: ``calibration_transfer``.
- ``implied_brier``: binary p(1 − p) for the positive class; multiclass 1 − Σ p_c². Both match CG1's
  Brier definition. Assumption: ``calibration_transfer``.
- ``composition_projection``: Π = Σ_g ŵ_g^cur · r_g^ref over the first declared cohort. It uses the
  reference's within-group issued-error risks. Assumption: ``unchanged_within_group_risk``. It is
  descriptive unless every group has a finite reference bound.

**The original record is immutable.** When the window's outcomes mature on O ⊆ P_W, a matched
record adds:
- the same formula restricted to O;
- the realized value on O, with a Clopper–Pearson interval for error indicators and a Hoeffding
  interval for the Brier score;
- the coverage |O| / |P_W|;
- exclusions by reason.

A matched comparison tests the assumption on O, not on P_W. Historical accuracy of an estimator does
not establish that its assumptions hold now.
"""
from ...contracts import digest
from . import eprocess

ESTIMATORS = {
    'implied_issued_error': {'assumption': 'calibration_transfer', 'realized': 'error'},
    'implied_brier': {'assumption': 'calibration_transfer', 'realized': 'brier'},
    'composition_projection': {'assumption': 'unchanged_within_group_risk', 'realized': 'error'},
}


def _issued(unit):
    return unit.get('decision') is not None and unit.get('state') in ('issued', 'hypothetical')


def _probs(unit):
    probs = unit.get('probs')
    if probs is None or unit.get('prob_valid') is False:
        return None
    return [float(p) for p in probs]


def _implied(estimator, unit, task):
    classes = task.get('classes') or []
    probs = _probs(unit)
    if probs is None or len(probs) != len(classes):
        return None
    if estimator == 'implied_issued_error':
        if not _issued(unit) or unit['decision'] not in classes:
            return None
        return 1.0 - probs[classes.index(unit['decision'])]
    if estimator == 'implied_brier':
        if task['kind'] == 'binary_classification':
            p = probs[classes.index(task['positive_class'])]
            return p * (1 - p)
        return 1.0 - sum(p * p for p in probs)
    return None


def _realized(kind, unit, task):
    if not unit.get('outcome_valid'):
        return None
    if kind == 'error':
        return None if not _issued(unit) else float(unit['decision'] != unit['y'])
    if kind == 'brier':
        brier = unit.get('brier')
        return None if brier is None else float(brier)
    return None


def population(estimator, units, task):
    if estimator == 'composition_projection':
        return [u for u in units if _issued(u)]
    return [u for u in units if _implied(estimator, u, task) is not None]


def estimate(estimator, units, task, reference=None, namespace=''):
    """The original (immutable) record for window population P_W."""
    members = population(estimator, units, task)
    hashes = sorted(digest([namespace, u['event_key']]) for u in members)
    record = {'estimator': estimator, 'assumption': ESTIMATORS[estimator]['assumption'], 'standing': 'E',
              'population': len(members), 'population_digest': digest(hashes), 'value': None, 'band': None}
    if not members:
        record['reason'] = 'empty_population'
        return record, hashes
    if estimator == 'composition_projection':
        record.update(_projection(members, reference))
        return record, hashes
    values = [_implied(estimator, u, task) for u in members]
    record['value'] = sum(values) / len(values)
    record['formula'] = ('mean over issued units of 1 - p(issued decision)' if estimator == 'implied_issued_error'
                         else 'mean model-implied Brier under calibration')
    return record, hashes


def _projection(members, reference):
    comp = (reference or {}).get('composition')
    if not comp:
        return {'reason': 'no_reference_composition'}
    counts = {}
    for unit in members:
        counts[unit.get('g0')] = counts.get(unit.get('g0'), 0) + 1
    total = sum(counts.values())
    value, lower, upper, formal = 0.0, 0.0, 0.0, True
    unsupported = []
    for group, n in sorted(counts.items(), key=lambda kv: str(kv[0])):
        ref = comp['groups'].get(group)
        if ref is None or ref['risk'] is None:
            unsupported.append(group)
            continue
        w = n / total
        value += w * ref['risk']
        if ref['upper'] is None:
            formal = False
        else:
            lower += w * ref['lower']
            upper += w * ref['upper']
    if unsupported:
        return {'reason': 'groups_without_reference_risk', 'unsupported_groups': unsupported}
    return {'value': value, 'band': [lower, upper] if formal else None, 'formula': 'sum_g w_g(current) * r_g(reference)',
            'band_meaning': 'Bonferroni-split finite reference bounds, under unchanged within-group risk' if formal else None}


def matched(estimator, original_hashes, units, task, reference=None, namespace='', alpha=0.05):
    """Matched record once outcomes have matured: same formula on O, realized on O, coverage and exclusions."""
    wanted = set(original_hashes)
    members = [u for u in units if digest([namespace, u['event_key']]) in wanted]
    kind = ESTIMATORS[estimator]['realized']
    observed, exclusions = [], {}
    for unit in members:
        value = _realized(kind, unit, task)
        if value is None:
            reason = unit.get('outcome_reason') or 'not_applicable'
            exclusions[reason] = exclusions.get(reason, 0) + 1
            continue
        observed.append(unit)
    out = {'coverage': len(observed) / len(wanted) if wanted else None, 'matched_population': len(observed),
           'original_population': len(wanted), 'exclusions': exclusions,
           'selection_note': 'A matched comparison tests the assumption on the labelled subset O, not on P_W.'}
    if not observed:
        out['reason'] = 'no_matured_outcomes'
        return out
    if estimator == 'composition_projection':
        restricted = _projection(observed, reference)
        out['matched_estimate'] = restricted.get('value')
    else:
        values = [_implied(estimator, u, task) for u in observed]
        out['matched_estimate'] = sum(values) / len(values)
    realized = [_realized(kind, u, task) for u in observed]
    n = len(realized)
    out['realized'] = sum(realized) / n
    if kind == 'error':
        k = int(sum(realized))
        out['realized_interval'] = [eprocess.clopper_pearson(k, n, alpha / 2, 'lower'),
                                    eprocess.clopper_pearson(k, n, alpha / 2, 'upper')]
        out['interval_method'] = 'clopper_pearson (requires independent units; entity_first)'
    else:
        bound = 1.0 if task['kind'] == 'binary_classification' else 2.0
        out['realized_interval'] = [eprocess.hoeffding(out['realized'], n, alpha / 2, 'lower', 0, bound),
                                    eprocess.hoeffding(out['realized'], n, alpha / 2, 'upper', 0, bound)]
        out['interval_method'] = 'hoeffding (declared bounds)'
    if out.get('matched_estimate') is not None:
        out['signed_bias'] = out['matched_estimate'] - out['realized']
        lo, hi = out['realized_interval']
        out['exceedance'] = not (lo <= out['matched_estimate'] <= hi)
    return out


def ledger_summary(rows):
    """Descriptive per-estimator accountability: bias, absolute error, exceedances, coverage."""
    done = [r for r in rows if r.get('matched') and r['matched'].get('signed_bias') is not None]
    if not done:
        return {'matched_windows': 0}
    bias = [r['matched']['signed_bias'] for r in done]
    return {'matched_windows': len(done), 'mean_signed_bias': sum(bias) / len(bias),
            'mean_absolute_error': sum(abs(b) for b in bias) / len(bias),
            'exceedances': sum(1 for r in done if r['matched'].get('exceedance')),
            'mean_coverage': sum(r['matched']['coverage'] for r in done) / len(done),
            'qualification': 'Historical accuracy of an estimator does not establish its assumptions hold now.'}
