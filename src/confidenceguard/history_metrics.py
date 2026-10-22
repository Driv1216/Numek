"""Historical measurement semantics and explicit descriptive materiality policies."""
from decimal import Decimal
import math
from .contracts import digest


def metric_identity(measurement):
    """Exclude observed bins/counts/fit estimates; retain the mathematical definition.

    Predictor/method-chain artifacts are bound by the surrounding variant/edge.
    Measurement-specific artifacts, when present, belong to this identity too.
    """
    data = measurement.get('data', {})
    dimensions = {key: data[key] for key in (
        'target', 'interval', 'supplied_interval', 'nominal', 'level', 'alpha',
        'central', 'interval_definition', 'definition', 'ties', 'edges', 'binning', 'ece_definition',
        'sample_meaning', 'threshold', 'high_confidence_threshold', 'method', 'method_id', 'artifact_digest', 'artifact_sha256',
    ) if key in data}
    if measurement['metric'] == 'reliability_diagram' and data.get('bins'):
        dimensions['calibration_partition'] = [[b.get('lower'), b.get('upper'), b.get('upper_inclusive')] for b in data['bins']]
    for key in ('nominal', 'level', 'alpha'):
        if key in dimensions and dimensions[key] is not None:
            dimensions[key] = str(Decimal(str(dimensions[key])).normalize())
    return {'metric': measurement['metric'], 'family': measurement.get('family'),
            'method_version': measurement.get('method_version'),
            'units': measurement.get('units'), 'dimensions': dimensions}


def metric_key(measurement):
    return 'metric_' + digest(metric_identity(measurement))


def metric_fields(measurement):
    identity = metric_identity(measurement)
    parts = [measurement['metric']]
    parts.extend(f'{key}={value}' for key, value in identity['dimensions'].items()
                 if key not in {'edges', 'calibration_partition', 'artifact_digest', 'artifact_sha256', 'interval_definition'})
    # The short key disambiguates definitions differing only in bins/artifacts/units.
    key = metric_key(measurement)
    return {'metric_identity': identity, 'metric_key': key,
            'metric_label': ' · '.join(parts) + ' [' + key[-10:] + ']'}


HIGHER_BETTER = frozenset({
    'accuracy', 'balanced_accuracy', 'macro_f1_observed_classes',
    'support_weighted_f1', 'precision', 'recall', 'specificity', 'f1',
    'roc_auc', 'average_precision', 'r2', 'r_squared',
})
LOWER_BETTER = frozenset({
    'error_rate', 'mae', 'mse', 'rmse', 'median_absolute_error',
    'p90_absolute_error', 'p95_absolute_error', 'material_error_rate',
    'brier', 'log_loss', 'frozen_bin_ece', 'reliability_diagram',
    'empirical_crps', 'wis', 'central_interval_score', 'empirical_cost',
})


def materiality(contrast, left, right, thresholds, *, kind):
    """Attach a qualified observed effect; never invent a default adverse direction."""
    metric = contrast['metric']
    if metric not in thresholds:
        return
    assessment = {'threshold': thresholds[metric], 'statistical_confirmation': False,
                  'status': 'unavailable'}
    contrast['practical_assessment'] = assessment
    if contrast['value_state'] != 'finite':
        assessment['reason'] = 'nonfinite_materiality_contrast'
        return
    target = None
    if metric in HIGHER_BETTER:
        policy = 'higher_is_better'
    elif metric in LOWER_BETTER or metric.startswith(('pinball@', 'central_interval_score@')):
        policy = 'lower_is_better'
    elif metric in {'bias', 'calibration_intercept', 'calibration_slope'}:
        policy = 'distance_from_target'; target = 1. if metric == 'calibration_slope' else 0.
    elif metric in {'interval_coverage', 'set_coverage'} or metric.startswith(('interval_coverage@', 'set_coverage@')):
        policy = 'nominal_shortfall'
        try:
            target = float(left.get('data', {})['nominal'])
            other = float(right.get('data', {})['nominal'])
            if not math.isfinite(target) or not 0 < target < 1 or target != other:
                raise ValueError
        except (KeyError, TypeError, ValueError):
            assessment['reason'] = 'compatible_nominal_level_required'
            return
    elif metric in {'eligible_label_observation_rate', 'population_coverage'}:
        policy = 'absolute_change'
    else:
        assessment['reason'] = 'materiality_interpretation_unspecified'
        return
    assessment['interpretation'] = policy
    if target is not None:
        assessment['target'] = target
    if kind == 'contrast_change' and policy not in {'higher_is_better', 'lower_is_better'}:
        assessment['reason'] = 'unsupported_materiality_for_contrast_change'
        return
    if policy == 'absolute_change':
        effect = abs(contrast['value'])
        assessment['observed_absolute_difference'] = effect
    else:
        if policy == 'higher_is_better': effect = -contrast['value']
        elif policy == 'lower_is_better': effect = contrast['value']
        elif policy == 'distance_from_target': effect = abs(right['value']-target)-abs(left['value']-target)
        else: effect = max(0., target-right['value'])-max(0., target-left['value'])
        assessment['observed_adverse_difference'] = effect
    assessment.update(status='available', material_observed_change=effect > thresholds[metric])


DRIFT_MEASURES = frozenset({'ks_distance', 'wasserstein_1', 'total_variation',
                            'jensen_shannon_divergence_nats'})


def prioritize_drift(item, thresholds):
    """All distances survive; only declared field/effect thresholds confer priority."""
    declared = thresholds.get(item['field'], {})
    priority = {'status': 'no_threshold_declared', 'statistical_confirmation': False}
    item['prioritization'] = priority
    if not declared:
        return False
    priority['thresholds'] = dict(declared)
    if item['status'] != 'completed' or any(key not in item for key in declared):
        priority.update(status='unavailable', reason='declared_drift_measure_unavailable')
        return False
    exceeded = [key for key, threshold in declared.items() if item[key] > threshold]
    priority.update(status='threshold_exceeded' if exceeded else 'within_declared_thresholds',
                    exceeded_measures=exceeded, interpretation='Descriptive materiality; no p-value or degradation conclusion.')
    return bool(exceeded)
