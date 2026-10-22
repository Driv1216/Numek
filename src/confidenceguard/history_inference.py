"""Fixed-artifact historical bootstrap designs with explicit refusal semantics."""
import math
from decimal import Decimal, ROUND_CEILING
import numpy as np
from .contracts import EvaluationError
from .analytics import literal


def metric_expression(store, metric):
    """Shared normalized fields; conditional denominators remain explicit."""
    run = store.run; task = store.spec.task
    point = "outcome_valid AND point IS NOT NULL AND state IN ('issued','hypothetical') AND isfinite(point-y_num)"
    decision = "outcome_valid AND decision IS NOT NULL AND state IN ('issued','hypothetical')"
    probability = 'outcome_valid AND prob_valid'
    if metric=='empirical_cost' and task.kind!='regression' and getattr(store,'event_costs',None):
        action="CASE WHEN state='abstained' THEN 'abstained' ELSE decision END"
        expression='CASE '+' '.join(f'WHEN ({action})={literal(a)} AND y={literal(y)} THEN {cost!r}::DOUBLE' for a,values in store.event_costs.items() for y,cost in values.items())+' ELSE NULL::DOUBLE END'
        return expression,'1.',f'outcome_valid AND ({expression}) IS NOT NULL'
    if metric in {'mae', 'mse', 'rmse', 'bias'}:
        return {'mae': 'abs(point-y_num)', 'mse': 'pow(point-y_num,2)', 'rmse': 'pow(point-y_num,2)', 'bias': 'point-y_num'}[metric], '1.', point
    if metric in {'accuracy', 'error_rate'}:
        return ('CASE WHEN decision=y THEN 1. ELSE 0. END' if metric == 'accuracy' else 'CASE WHEN decision<>y THEN 1. ELSE 0. END'), '1.', decision
    if metric == 'brier': return 'brier', '1.', probability
    if metric == 'log_loss': return "CASE WHEN log_infinite THEN 'inf'::DOUBLE ELSE log_loss END", '1.', probability
    if metric in {'precision', 'recall', 'specificity', 'f1'} and task.kind == 'binary_classification':
        positive = literal(task.positive_class)
        tp = f'CASE WHEN decision={positive} AND y={positive} THEN 1. ELSE 0. END'
        if metric == 'precision': return tp, '1.', decision + f' AND decision={positive}'
        if metric == 'recall': return tp, '1.', decision + f' AND y={positive}'
        if metric == 'specificity': return f'CASE WHEN decision<>{positive} THEN 1. ELSE 0. END', '1.', decision + f' AND y<>{positive}'
        return '2*(' + tp + ')', f'CASE WHEN decision={positive} THEN 1. ELSE 0. END + CASE WHEN y={positive} THEN 1. ELSE 0. END', decision
    if metric == 'material_error_rate' and task.material_error is not None:
        return f'CASE WHEN abs(point-y_num)>{task.material_error!r} THEN 1. ELSE 0. END', '1.', point
    if metric in {'roc_auc', 'average_precision'} and task.kind == 'binary_classification':
        return f'CASE WHEN y={literal(task.positive_class)} THEN 1. ELSE 0. END', '1.', 'outcome_valid AND rank_score IS NOT NULL'
    return None


def contributions(store, metric, *, allowed_events=None):
    expression = metric_expression(store, metric)
    extra_join = ''
    if expression is None and metric in getattr(store, 'extra_metadata', {}):
        expression = ('x.value', '1.', 'x.eligible AND x.defined')
        extra_join = f' JOIN {store.loss_table} x USING(ordinal,event_key) '
    if expression is None:
        return None
    numerator, denominator, valid = expression
    if extra_join: valid += ' AND x.metric=' + literal(metric)
    predicate = valid + (f' AND r.event_key IN (SELECT event_key FROM {allowed_events})' if allowed_events else '')
    count = store.con.execute(f'SELECT count(*) FROM {store.table} r {extra_join} WHERE {predicate}').fetchone()[0]
    if count * 320 > store.config.memory_bytes // 2:
        return {'refusal': 'inference_memory_admission'}
    score = 'rank_score' if metric in {'roc_auc', 'average_precision'} else 'NULL::DOUBLE'
    result = store.con.execute(f'''SELECT r.event_key,entity_key,history_target,history_tick,({numerator})::DOUBLE,
        ({denominator})::DOUBLE,{score} FROM {store.table} r {extra_join} WHERE {predicate} ORDER BY r.event_key''').fetchall()
    if not result: return []
    return result


def _support(weights):
    values = np.asarray(weights, dtype=float)
    positive = values[values > 0]
    return {'participating_units': len(positive), 'effective_units': float(positive.sum()**2 / (positive @ positive)) if len(positive) else 0.,
            'maximum_denominator_share': float(positive.max() / positive.sum()) if len(positive) else None}


def _rank_stat(rows, weights, metric):
    y = np.array([r[4] for r in rows]); scores = np.array([r[6] for r in rows])
    _, groups = np.unique(scores, return_inverse=True)
    if metric == 'average_precision': groups = int(groups.max()) - groups
    positive = np.bincount(groups, weights=weights*y)
    total = np.bincount(groups, weights=weights)
    p = positive.sum(); negatives = total.sum() - p
    if p <= 0 or negatives <= 0: return math.nan
    if metric == 'roc_auc':
        neg = total-positive
        return float(np.sum(positive*(np.cumsum(neg)-neg+.5*neg))/(p*negatives))
    cumulative = np.cumsum(total)
    return float(np.sum(np.divide(positive*np.cumsum(positive), cumulative, out=np.zeros_like(cumulative), where=cumulative > 0))/p)


def _historical_bootstrap(left, right, spec, *, metric, family_size, check, left_window, right_window,
                         available_bytes, effect=None, paired=False):
    base = {'status': 'unavailable', 'method': 'historical_percentile_v1', 'design': spec.mode,
            'conditioning': 'Frozen artifacts and declared observation/maturity process; no fit/selection or missing-label uncertainty.',
            'family_size': family_size, 'adjustment': spec.adjustment, 'level': spec.confidence,
            'exploratory': spec.exploratory, 'support_floor_is_engineering_rule': True}

    def refuse(reason, **detail):
        result = {**base, 'reason': reason, **detail}
        if spec.inference_required:
            raise EvaluationError('Required historical inference is unavailable: ' + reason, 'historical_inference_unavailable')
        return result

    if spec.mode == 'descriptive': return refuse('descriptive_requested')
    if left is None or right is None: return refuse('unsupported_inferential_estimand')
    if isinstance(left, dict) or isinstance(right, dict): return refuse('inference_memory_admission')
    if not left or not right: return refuse('zero_denominator')
    if spec.known_common_shocks and spec.mode != 'moving_blocks': return refuse('uncorrected_common_shock_dependence')
    if not spec.finite_moments: return refuse('finite_moment_assumption_required')
    ranked = metric in {'roc_auc', 'average_precision'}
    if any(not math.isfinite(r[4]) or not math.isfinite(r[5]) or ranked and (r[6] is None or not math.isfinite(r[6])) for r in (*left, *right)):
        return refuse('nonfinite_statistic')
    factor = max(1, family_size) if spec.adjustment == 'bonferroni' else 1
    tail_decimal = (Decimal(1)-Decimal(str(spec.confidence)))/(2*factor)
    tail = float(tail_decimal)
    minimum = int((Decimal(spec.minimum_tail)/tail_decimal).to_integral_value(rounding=ROUND_CEILING))
    base.update(minimum_replicates=minimum, nominal_tail_probability=tail, requested_replicates=spec.replicates)
    if spec.replicates < minimum: return refuse('insufficient_tail_resolution')
    n = len(left)+len(right)
    if n * 320 + spec.replicates*8 > available_bytes: return refuse('inference_memory_admission')
    left_events = {r[0] for r in left}; right_events = {r[0] for r in right}
    left_targets = {r[2] for r in left}; right_targets = {r[2] for r in right}
    if paired:
        if left_events != right_events: return refuse('paired_populations_differ')
    elif spec.mode in {'independent_periods', 'moving_blocks'} and (left_events & right_events or left_targets & right_targets):
        return refuse('shared_opportunities_or_outcome_targets')
    if spec.mode == 'independent_periods':
        if not spec.independent_units or not spec.independent_periods: return refuse('independence_declarations_required')
        if spec.known_serial_dependence: return refuse('uncorrected_serial_dependence')
        entities = [r[1] for r in (*left, *right) if r[1] is not None]
        targets = [r[2] for r in (*left, *right)]
        if len(entities) != len(set(entities)) or len(targets) != len(set(targets)):
            return refuse('known_repeated_unit_requires_clustering')
        values_l = np.array([[r[4], r[5]] for r in left]); values_r = np.array([[r[4], r[5]] for r in right])
        groups_l = np.arange(len(left)); groups_r = np.arange(len(right))
        unit_count = len(left)+len(right)
        draw = lambda rng: (rng.multinomial(len(left), np.full(len(left), 1/len(left))), rng.multinomial(len(right), np.full(len(right), 1/len(right))))
    elif spec.mode in {'entity_clusters', 'paired_clusters', 'paired_rows'}:
        if not spec.independent_units: return refuse('independent_units_declaration_required')
        if spec.mode == 'paired_rows':
            if not paired: return refuse('paired_design_requires_matched_comparison')
            if spec.known_serial_dependence: return refuse('uncorrected_serial_dependence')
            keys_l = [r[0] for r in left]; keys_r = [r[0] for r in right]
            entity_values = [r[1] for r in left if r[1] is not None]
            if len(entity_values) != len(set(entity_values)) or len(left_targets) != len(left): return refuse('known_repeated_unit_requires_clustering')
        else:
            if any(r[1] is None for r in (*left, *right)): return refuse('missing_entity_key')
            keys_l = [r[1] for r in left]; keys_r = [r[1] for r in right]
            assignment = {}
            for r in (*left, *right):
                if r[2] in assignment and assignment[r[2]] != r[1]: return refuse('outcome_dependence_crosses_entities')
                assignment[r[2]] = r[1]
        units = {key: i for i, key in enumerate(sorted(set(keys_l) | set(keys_r)))}
        groups_l = np.array([units[key] for key in keys_l]); groups_r = np.array([units[key] for key in keys_r]); unit_count = len(units)
        values_l = np.zeros((unit_count, 2)); values_r = np.zeros((unit_count, 2))
        for c in (0, 1):
            values_l[:, c] = np.bincount(groups_l, weights=[r[4+c] for r in left], minlength=unit_count)
            values_r[:, c] = np.bincount(groups_r, weights=[r[4+c] for r in right], minlength=unit_count)
        draw = lambda rng: (lambda weights: (weights, weights))(rng.multinomial(unit_count, np.full(unit_count, 1/unit_count)))
    elif spec.mode == 'moving_blocks':
        if ranked: return refuse('moving_blocks_requires_mean_or_ratio')
        if not (spec.stationary and spec.complete_bins and spec.bin_ns and spec.block_length): return refuse('moving_block_declarations_required')
        if spec.known_nonstationarity: return refuse('nonstationary_regime')
        if not paired and not spec.independent_periods: return refuse('cross_period_independence_required')
        if spec.block_length < 2: return refuse('block_length_one_is_not_dependence_correction')
        cadence = int(spec.bin_ns); length = spec.block_length
        def bins(records, window):
            start, end = window
            if (end-start) % cadence: return None
            count = (end-start)//cadence
            if count > 1000000: return None
            values = np.zeros((count, 2))
            for row in records:
                index = (row[3]-start)//cadence
                if index < 0 or index >= count: return None
                values[index] += row[4:6]
            return values
        values_l = bins(left, left_window); values_r = bins(right, right_window)
        if values_l is None or values_r is None: return refuse('incomplete_regular_bin_grid')
        if min(len(values_l), len(values_r))//length < 30: return refuse('insufficient_block_equivalents')
        def support_blocks(values):
            complete = len(values)//length
            return _support(values[:complete*length, 1].reshape(complete, length).sum(axis=1))
        supports = [support_blocks(values_l), support_blocks(values_r)]
        if any(v['effective_units'] < 30-1e-10 for v in supports): return refuse('insufficient_effective_block_support', support=supports)
        def block_weights(rng, size):
            starts = rng.integers(0, size-length+1, size=math.ceil(size/length))
            indices = (starts[:, None]+np.arange(length)).ravel()[:size]
            return np.bincount(indices, minlength=size)
        def draw(rng):
            a = block_weights(rng, len(values_l))
            return (a, a) if paired else (a, block_weights(rng, len(values_r)))
        groups_l = groups_r = None; unit_count = len(values_l)+len(values_r)
        base.update(block_length=length, bin_ns=spec.bin_ns, block_support=supports, block_scheme='noncircular_overlapping_blocks_truncated_v1')
    else: return refuse('unsupported_design')
    supports = [_support(values_l[:, 1]), _support(values_r[:, 1])]
    base['support'] = supports
    if any(v['participating_units'] < 30 or v['effective_units'] < 30-1e-10 for v in supports): return refuse('insufficient_independent_support')
    if ranked:
        for records, groups, values in ((left, groups_l, values_l), (right, groups_r, values_r)):
            for label in (0, 1):
                counts = np.bincount(groups, weights=[float(r[4] == label) for r in records], minlength=len(values))
                support = _support(counts)
                if support['participating_units'] < 30 or support['effective_units'] < 30-1e-10:
                    return refuse('insufficient_class_support')
    work = spec.replicates * (n*4 if ranked else unit_count*4)
    if work > spec.work_units: return refuse('inference_work_limit', estimated_work_units=work)
    base['estimated_work_units'] = work
    def statistic(a, b):
        if ranked:
            return _rank_stat(right, b[groups_r], metric)-_rank_stat(left, a[groups_l], metric)
        x = a @ values_l; y = b @ values_r
        if x[1] <= 0 or y[1] <= 0: return math.nan
        l, r = x[0]/x[1], y[0]/y[1]
        if metric == 'rmse':
            if l <= 0 or r <= 0: return math.nan
            l, r = math.sqrt(l), math.sqrt(r)
        return r-l
    estimate = statistic(np.ones(len(values_l)), np.ones(len(values_r)))
    if not math.isfinite(estimate): return refuse('undefined_original_statistic')
    rng = np.random.Generator(np.random.PCG64(spec.seed)); draws = np.empty(spec.replicates)
    for index in range(spec.replicates):
        if index % 16 == 0: check('historical bootstrap replicate batch')
        a, b = draw(rng); draws[index] = statistic(a, b)
    invalid = int(np.count_nonzero(~np.isfinite(draws)))
    if invalid: return refuse('undefined_bootstrap_replicates', invalid_replicates=invalid)
    if np.all(draws == draws[0]): return refuse('degenerate_bootstrap_distribution')
    lower, upper = np.quantile(draws, [tail, 1-tail], method='linear')
    return {**base, 'status': 'available', 'lower': float(lower), 'upper': float(upper), 'estimate': estimate,
            'completed_replicates': spec.replicates, 'invalid_replicates': 0, 'rng': 'numpy.PCG64', 'seed': spec.seed,
            'quantile_convention': 'numpy_linear', 'tail_resolution_validated': True,
            'scope': 'Approximate fixed-artifact interval under declared sampling/dependence assumptions.'}


def historical_bootstrap(left, right, spec, **kwargs):
    """Primary procedure and declared exploratory block-length sensitivity."""
    from dataclasses import replace
    family = max(1, kwargs['family_size'])
    budget = spec.work_units // (family * (1+len(spec.sensitivity_lengths)))
    admitted = replace(spec, work_units=max(1,budget), sensitivity_lengths=())
    result = _historical_bootstrap(left,right,admitted,**kwargs)
    if spec.mode == 'moving_blocks':
        result['sensitivity_proposals'] = sorted({max(2,(spec.block_length or 2)//2),2*(spec.block_length or 2)} - {spec.block_length})
        result['sensitivity'] = []
        for length in spec.sensitivity_lengths:
            alternative = replace(admitted,block_length=length,inference_required=False,exploratory=True)
            item = _historical_bootstrap(left,right,alternative,**kwargs)
            item['interpretation'] = 'Exploratory sensitivity; never replaces the frozen primary procedure.'
            result['sensitivity'].append(item)
    return result
