"""Supervised historical orchestration over shared prediction/uncertainty reducers."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json
import math
import time
import uuid
import numpy as np
from .contracts import EvaluationError, digest, EvaluationConfig
from .analytics import evaluate_scope, distributions, literal
from .uncertainty import build_losses, evaluate_losses, deeper_calibration
from .history_contracts import LongitudinalSpec, HistoricalWindow, HISTORY_METHOD, HISTORY_RESULT, instant, now
from .history_result import LongitudinalResult
from .history_selection import HistoryStore, load_history, select_history, context_links
from .history_inference import metric_expression, contributions, historical_bootstrap
from .history_metrics import metric_fields, metric_key, materiality, prioritize_drift
from . import compat


LIMITATIONS = [
    'Supplied outcomes and history completeness are declarations, not independently verified truth.',
    'Observed labels may be selective; no missing-outcome correction or full-population performance claim.',
    'Unknown maturity, timing, model identity or upstream independence limits dependent conclusions.',
    'Historical comparisons and mix decomposition are associational, not causal attribution.',
    'Inference conditions on frozen artifacts and declared dependence; it excludes fitting/selection and missing-label uncertainty.',
    'Empirical conformal coverage does not establish future coverage under distribution shift.',
    'Repeated interactive investigation and change-point candidates have no sequential or post-selection guarantee.',
    'No universal score, automated policy, model execution, incident or deployment approval is defined.',
]


def make_windows(start, end, *, cadence_ns=None, rolling_ns=None, calendar=None, timezone_name=None):
    """Freeze exact fixed/rolling or timezone-declared civil day/week/month windows."""
    from zoneinfo import ZoneInfo
    from calendar import monthrange
    if bool(cadence_ns) == bool(calendar): raise EvaluationError('Choose fixed cadence or a civil calendar.')
    lo, hi = instant(start), instant(end)
    result = []
    if cadence_ns:
        step = int(cadence_ns); width = int(rolling_ns or cadence_ns)
        if step <= 0 or width <= 0: raise EvaluationError('Window durations must be positive.')
        def iso(tick):
            seconds, ns = divmod(tick, 1000000000)
            return datetime.fromtimestamp(seconds, timezone.utc).strftime('%Y-%m-%dT%H:%M:%S') + f'.{ns:09d}Z'
        current = lo
        while current < hi:
            if len(result) >= 120: raise EvaluationError('Generated windows exceed admission.')
            result.append(HistoricalWindow('window_' + str(len(result)+1), iso(current), iso(min(current+width, hi))))
            current += step
    else:
        if rolling_ns or calendar not in {'day', 'week', 'month'} or not timezone_name:
            raise EvaluationError('Civil windows require an explicit timezone and day/week/month cadence.')
        current = datetime.fromisoformat(start.replace('Z', '+00:00')).astimezone(ZoneInfo(timezone_name))
        finish = datetime.fromisoformat(end.replace('Z', '+00:00')).astimezone(ZoneInfo(timezone_name))
        while current < finish:
            if len(result) >= 120: raise EvaluationError('Generated windows exceed admission.')
            if calendar == 'month':
                month = current.month % 12 + 1; year = current.year + (current.month == 12)
                following = current.replace(year=year, month=month, day=min(current.day, monthrange(year, month)[1]))
            else: following = current + timedelta(days=1 if calendar == 'day' else 7)
            result.append(HistoricalWindow('window_' + str(len(result)+1), current.isoformat(), min(following, finish).isoformat()))
            current = following
    return tuple(result)


def _evaluate(store, scope='overall', where='true', *, distributions_enabled=False):
    e = store.evidence; table = store.table
    if distributions_enabled: distributions(e, store.run, table)
    e.use_relation(table)
    total, labeled = store.con.execute(f'SELECT count(*),count(*) FILTER(WHERE outcome_valid) FROM {table} WHERE {where}').fetchone()
    e.ratio(store.run, scope, 'outcome_availability', 'eligible_label_observation_rate', labeled, total, where=where,
            data={'interpretation': 'Eligible observed/mature outcomes under this policy; not proof of label representativeness.'})
    evaluate_scope(e, store.run, table, where, scope)
    cost=metric_expression(store,'empirical_cost')
    if cost:
        expression,_,valid=cost;valid=f'({where}) AND ({valid})'
        n,value=store.con.execute(f'SELECT count(*),avg({expression}) FROM {table} WHERE {valid}').fetchone()
        e.use_relation(table);e.add(store.run,scope,'performance','empirical_cost',value,n,where=valid,data={'estimand':'Observed event mean under the frozen supplied action/outcome cost mapping; unmapped outcomes are excluded.'},reason=None if n else 'zero_denominator')
    if store.spec.task.kind == 'regression':
        valid = f"({where}) AND outcome_valid AND point IS NOT NULL AND state IN ('issued','hypothetical') AND isfinite(point-y_num)"
        n, value = store.con.execute(f'SELECT count(*),avg(pow(point-y_num,2)) FROM {table} WHERE {valid}').fetchone()
        e.use_relation(table)
        e.add(store.run, scope, 'performance', 'mse', value, n, where=valid, reason=None if n else 'zero_denominator')
    else:
        valid = f"({where}) AND outcome_valid AND decision IS NOT NULL AND state IN ('issued','hypothetical')"
        n, errors = store.con.execute(f'SELECT count(*),count(*) FILTER(WHERE decision<>y) FROM {table} WHERE {valid}').fetchone()
        e.use_relation(table); e.ratio(store.run, scope, 'performance', 'error_rate', errors, n, where=valid)
    if store.metadata.get('has_cg2'):
        if not hasattr(store, 'loss_table'):
            loss, metadata = build_losses(store, store.run, table, root=store.variant,
                                          uncertainty_table=store.uncertainty_table)
            dest = 'history_losses_' + digest(table)[:12]
            store.con.execute(f'ALTER TABLE {loss} RENAME TO {dest}')
            store.loss_table = dest; store.extra_metadata = metadata
        evaluate_losses(e, store.run, table, store.loss_table, store.extra_metadata, where, scope)
    deeper_calibration(e, store.run, table, where, scope, store.calibration_edges)


def _lookup(store, scope='overall'):
    result = {}
    for m in store.evidence.measurements:
        if m['scope'] != scope:
            continue
        interval_id = m.get('data', {}).get('interval')
        if interval_id:
            interval = next((v for v in store.run.intervals if v.id == interval_id), None)
            if interval:
                m['data']['interval_definition'] = {'nominal': interval.coverage, 'meaning': interval.meaning, 'central': interval.central}
        m.update(metric_fields(m))
        if m['value'] is not None or m['value_state'] in {'positive_infinity', 'negative_infinity'}:
            key = m['metric_key']
            if key in result:
                raise EvaluationError('Duplicate equivalent historical measurement identity.', 'historical_metric_identity_conflict')
            result[key] = m
    return result


def qualification(edge, left, right):
    a = left.metadata; b = right.metadata; reasons = []; status = 'compatible'
    if a['task'] != b['task'] or a['outcome_definition_version'] != b['outcome_definition_version']:
        reasons.append('different_task_outcome_horizon_units_or_classes'); status = 'blocked'
    if edge.kind == 'temporal' and edge.reference_variant != edge.current_variant:
        reasons.append('variant_changed_requires_combined_comparison'); status = 'blocked'
    if edge.kind == 'matched' and edge.reference_window != edge.current_window:
        reasons.append('matched_comparison_requires_one_window'); status = 'blocked'
    if edge.kind in {'matched', 'contrast_change'} and (left.coverage['inline_assertion_conflicts'] or right.coverage['inline_assertion_conflicts']):
        reasons.append('conflicting_asserted_outcome_copy'); status = 'blocked'
    if a['signature']['model'] != b['signature']['model']: reasons.append('model_changed')
    if a['method_digests'] != b['method_digests']: reasons.append('calibration_or_conformal_artifact_changed')
    if a.get('base_model_identity_declared_only') or b.get('base_model_identity_declared_only'): reasons.append('artifact_identity_unestablished')
    if left.coverage['unknown_information_cutoff'] or right.coverage['unknown_information_cutoff']:reasons.append('information_cutoff_unestablished')
    if left.coverage['information_after_opportunity'] or right.coverage['information_after_opportunity']:reasons.append('known_lookahead_excluded')
    if left.coverage['incomplete_outcome_history'] or right.coverage['incomplete_outcome_history']:reasons.append('supplied_revision_history_incomplete')
    if left.coverage['undated_outcomes'] or right.coverage['undated_outcomes']:reasons.append('source_availability_unestablished')
    if left.coverage['unknown_maturity'] or right.coverage['unknown_maturity']: reasons.append('maturity_unestablished')
    reasons.append('observed_label_estimand_selective_labels_not_corrected')
    if left.coverage['ambiguous_predictions'] or right.coverage['ambiguous_predictions']: reasons.append('ambiguous_predictions_excluded')
    if left.coverage['unqualified_method_outputs'] or right.coverage['unqualified_method_outputs']: reasons.append('prior_method_membership_unavailable')
    if left.coverage.get('application_failures') or right.coverage.get('application_failures'): reasons.append('planned_output_failures_successful_subset_only')
    if status != 'blocked' and reasons: status = 'qualified'
    return status, reasons


def _delta(a, b):
    if a['value_state'] == b['value_state'] == 'finite':
        value=b['value']-a['value']
        return (value,'finite') if math.isfinite(value) else (None,'positive_infinity' if value>0 else 'negative_infinity')
    if a['value_state'] == b['value_state']: return None, 'undefined'
    if b['value_state'] == 'positive_infinity' or a['value_state'] == 'negative_infinity': return None, 'positive_infinity'
    if b['value_state'] == 'negative_infinity' or a['value_state'] == 'positive_infinity': return None, 'negative_infinity'
    return None, 'undefined'


def _metric_compatible(left, right, metric, a, b):
    if a.get('data', {}).get('nominal') != b.get('data', {}).get('nominal'):
        return False
    if a.get('data', {}).get('target') != b.get('data', {}).get('target'):
        return False
    if 'interval' in metric:
        def signatures(store):
            return [(v.id, v.coverage, v.meaning, v.central) for v in store.run.intervals]
        if '@' not in metric and a.get('data', {}).get('interval_definition') is not None:
            if a['data']['interval_definition'] != b.get('data', {}).get('interval_definition'):
                return False
        elif signatures(left) != signatures(right) and '@' not in metric:
            return False
    if metric in {'ranking_score', 'selection_score', 'class_score_maximum'} and left.metadata['signature']['score'] != right.metadata['signature']['score']:
        return False
    return True


def _contrast_records(a, b):
    if not isinstance(a, list) or not isinstance(b, list): return None
    right = {row[0]: row for row in b}; result = []
    for row in a:
        other = right.get(row[0])
        if other is None or row[5] != 1 or other[5] != 1: return None
        result.append((*row[:4], other[4]-row[4], 1., None))
    return result if len(result) == len(b) else None


def _paired_scopes(left, right, scope):
    """Recompute both variants on metric-family common bases, including conditional denominators."""
    con = left.con; result_l = {}; result_r = {}; bases = {}
    families = {'decision': "decision IS NOT NULL AND state IN ('issued','hypothetical')", 'point': "point IS NOT NULL AND state IN ('issued','hypothetical')",
                'probability': 'prob_valid', 'ranking': 'rank_score IS NOT NULL'}
    for family, valid in families.items():
        suffix = digest([scope, family])[:12]; base = 'history_common_' + suffix
        con.execute(f'''CREATE TABLE {base} AS SELECT a.event_key FROM {left.table} a JOIN {right.table} b USING(event_key)
            WHERE a.outcome_valid AND b.outcome_valid AND a.y IS NOT DISTINCT FROM b.y
              AND ({'a.' + valid.replace(' AND ', ' AND a.').replace("state IN", "state IN")})
              AND ({'b.' + valid.replace(' AND ', ' AND b.').replace("state IN", "state IN")})''')
        for store, dest in ((left, result_l), (right, result_r)):
            local_scope = scope + '/' + family
            _evaluate(store, local_scope, f'event_key IN (SELECT event_key FROM {base})')
            measured = _lookup(store, local_scope)
            for key, m in measured.items():
                metric = m['metric']
                if m.get('data', {}).get('interval'):
                    continue  # Supplied intervals need their own paired availability base.
                kind = 'probability' if m['family'] in {'calibration', 'calibration_diagnostics', 'probability_quality', 'high_confidence'} else 'ranking' if m['family'] in {'ranking', 'ranking_curve'} else 'point' if metric in {'mae', 'mse', 'rmse', 'bias', 'r_squared', 'median_absolute_error', 'p90_absolute_error', 'p95_absolute_error', 'material_error_rate'} else 'decision'
                if kind == family:
                    dest[key] = m; bases[key] = base
    for interval in left.run.intervals:
        other = next((v for v in right.run.intervals if (v.id,v.coverage,v.meaning,v.central)==(interval.id,interval.coverage,interval.meaning,interval.central)), None)
        if other is None or interval.meaning != 'prediction': continue
        i = list(left.run.intervals).index(interval); j = list(right.run.intervals).index(other)
        base = 'history_interval_common_' + digest([scope,interval.id])[:12]
        con.execute(f'''CREATE TABLE {base} AS SELECT a.event_key FROM {left.table} a JOIN {right.table} b USING(event_key)
            WHERE a.outcome_valid AND b.outcome_valid AND a.y IS NOT DISTINCT FROM b.y
            AND a.w{i} IS NOT NULL AND b.w{j} IS NOT NULL''')
        for store,dest in ((left,result_l),(right,result_r)):
            local_scope = scope + '/interval/' + digest(interval.id)[:12]
            _evaluate(store,local_scope,f'event_key IN (SELECT event_key FROM {base})')
            for key,m in _lookup(store,local_scope).items():
                if m.get('data',{}).get('interval') == interval.id:
                    dest[key]=m; bases[key]=base
    if metric_expression(left,'empirical_cost') and metric_expression(right,'empirical_cost'):
        base='history_cost_common_'+digest(scope)[:12]
        left_valid=metric_expression(left,'empirical_cost')[2];right_valid=metric_expression(right,'empirical_cost')[2]
        con.execute(f'CREATE TABLE {base} AS SELECT event_key FROM (SELECT event_key FROM {left.table} WHERE {left_valid}) a JOIN (SELECT event_key FROM {right.table} WHERE {right_valid}) b USING(event_key)')
        for store,dest in ((left,result_l),(right,result_r)):
            local_scope=scope+'/cost';_evaluate(store,local_scope,f'event_key IN (SELECT event_key FROM {base})')
            for key, measured in _lookup(store,local_scope).items():
                if measured['metric']=='empirical_cost':dest[key]=measured;bases[key]=base
    for metric in sorted(set(getattr(left,'extra_metadata',{})) & set(getattr(right,'extra_metadata',{}))):
        base = 'history_common_extra_' + digest([scope,metric])[:12]
        con.execute(f"""CREATE TABLE {base} AS SELECT a.event_key FROM {left.table} a JOIN {right.table} b USING(event_key)
            JOIN {left.loss_table} x ON x.event_key=a.event_key JOIN {right.loss_table} y ON y.event_key=b.event_key
            WHERE a.outcome_valid AND b.outcome_valid AND a.y IS NOT DISTINCT FROM b.y
            AND x.metric=? AND y.metric=? AND x.eligible AND y.eligible AND x.defined AND y.defined""",[metric,metric])
        for store,dest in ((left,result_l),(right,result_r)):
            local_scope=scope+'/extra/'+digest(metric)[:12]
            _evaluate(store,local_scope,f'event_key IN (SELECT event_key FROM {base})')
            for key, m in _lookup(store,local_scope).items():
                if m['metric']==metric:dest[key]=m;bases[key]=base
    return result_l, result_r, bases


def _joint_records(a, b):
    if not isinstance(a, list) or not isinstance(b, list): return a, b
    left = {r[0]: r for r in a}; right = {r[0]: r for r in b}; union = sorted(left.keys() | right.keys())
    # Missing conditional-denominator contributions are zeros on the paired base,
    # not intersections of both positive decisions (which would redefine precision).
    def side(own, other):
        result = []
        for key in union:
            if key in own: result.append(own[key])
            else:
                r = other[key]; result.append((*r[:4], 0., 0., None))
        return result
    return side(left, right), side(right, left)


def _scoped_store(store, scope, predicate):
    import copy
    clone = copy.copy(store)
    clone.table = 'scoped_' + digest([store.table, scope])[:16]
    store.con.execute(f'CREATE TEMP TABLE IF NOT EXISTS {clone.table} AS SELECT * FROM {store.table} WHERE {predicate}')
    clone.run_tables = {store.variant: clone.table}
    store.evidence.bind_relation(clone.table, {'kind': 'declared_cohort_projection', 'input': store.evidence.relations[store.table], 'predicate': predicate})
    return clone


def _cohort_contrasts(left, right, edge, spec, family_size, work, reference_second=None, current_second=None):
    result = []
    for index, cohort in enumerate(spec.cohorts):
        groups = sorted({v[0] for store in (left,right) for v in store.con.execute(f'SELECT DISTINCT g{index} FROM {store.table}').fetchall()} - {'unretained','unresolved'})
        for group in groups:
            scope = f'cohort_{index}/{group}'; predicate = f'g{index}={literal(group)}'
            a_store = _scoped_store(left, scope, predicate); b_store = _scoped_store(right, scope, predicate)
            paired = edge.kind == 'matched'; bases = {}
            if paired:
                a,b,bases = _paired_scopes(a_store,b_store,'matched/'+edge.id+'/'+scope)
            elif edge.kind == 'contrast_change':
                a_second_store = _scoped_store(reference_second,scope,predicate);b_second_store = _scoped_store(current_second,scope,predicate)
                a,a_second,reference_bases = _paired_scopes(a_store,a_second_store,'contrast_reference/'+edge.id+'/'+scope)
                b,b_second,current_bases = _paired_scopes(b_store,b_second_store,'contrast_current/'+edge.id+'/'+scope)
            else:
                a,b = _lookup(left,scope),_lookup(right,scope)
            for key in sorted(a.keys() & b.keys()):
                l,r = a[key],b[key]; metric=l['metric']
                if not _metric_compatible(left,right,metric,l,r):continue
                value,state = _delta(l,r);extra={}
                if edge.kind == 'contrast_change':
                    if key not in a_second or key not in b_second:continue
                    old,old_state=_delta(l,a_second[key]);new,new_state=_delta(r,b_second[key])
                    value=new-old if old_state==new_state=='finite' else None;state='finite' if value is not None else 'undefined'
                    extra={'reference_second_population_id':a_second[key]['population_id'],'current_second_population_id':b_second[key]['population_id']}
                contrast={'scope':scope,'metric':metric,**metric_fields(l),'value':value,'value_state':state,'reference_population_id':l['population_id'],
                          'current_population_id':r['population_id'],'reference_support':l['denominator'],'current_support':r['denominator'],
                          'estimand':'Declared-cohort eligible observed outcomes','inference':{'status':'not_requested'},**extra}
                materiality(contrast,l,r,spec.material_thresholds,kind=edge.kind)
                if metric in spec.inference.metrics:
                    lc=contributions(a_store,metric,allowed_events=bases.get(key));rc=contributions(b_store,metric,allowed_events=bases.get(key))
                    if paired and metric not in {'roc_auc','average_precision'}:lc,rc=_joint_records(lc,rc)
                    if edge.kind == 'contrast_change':
                        additive=metric in {'accuracy','error_rate','mae','mse','bias','brier','log_loss','material_error_rate','empirical_cost'} or metric.startswith(('interval_coverage@','interval_efficiency@','set_coverage@','set_efficiency@'))
                        lc=_contrast_records(contributions(a_store,metric,allowed_events=reference_bases.get(key)),contributions(a_second_store,metric,allowed_events=reference_bases.get(key))) if additive else None
                        rc=_contrast_records(contributions(b_store,metric,allowed_events=current_bases.get(key)),contributions(b_second_store,metric,allowed_events=current_bases.get(key))) if additive else None
                    if any(s is not None and s.coverage['unqualified_method_outputs'] for s in (left,right,reference_second,current_second)):
                        contrast['inference']={'status':'unavailable','reason':'prior_method_membership_unavailable'}
                        if spec.inference.inference_required:raise EvaluationError('Required cohort inference lacks method membership checks.','historical_inference_unavailable')
                    else:
                        lw=next(w for w in spec.windows if w.id==edge.reference_window);rw=next(w for w in spec.windows if w.id==edge.current_window)
                        contrast['inference']=historical_bootstrap(lc,rc,spec.inference,metric=metric,family_size=family_size,
                            check=work.check,left_window=(instant(lw.start),instant(lw.end)),right_window=(instant(rw.start),instant(rw.end)),
                            available_bytes=spec.config.memory_bytes//2,paired=paired)
                result.append(contrast)
    return result


def _mix(left, right, metric, cohorts):
    expression_l = metric_expression(left, metric); expression_r = metric_expression(right, metric)
    decomposable = {'accuracy', 'error_rate', 'mae', 'mse', 'bias', 'brier', 'log_loss', 'material_error_rate','empirical_cost'}
    extra = metric in getattr(left, 'extra_metadata', {}) and metric in getattr(right, 'extra_metadata', {})
    if not extra and (metric not in decomposable or not expression_l or not expression_r): return []
    result = []
    for index, cohort in enumerate(cohorts):
        groups = []
        for store, expression in ((left, expression_l), (right, expression_r)):
            if extra:
                data = store.con.execute(f'SELECT g{index},count(*),avg(x.value) FROM {store.table} r JOIN {store.loss_table} x USING(ordinal,event_key) WHERE x.metric=? AND x.eligible AND x.defined GROUP BY 1 ORDER BY 1', [metric]).fetchall()
            else:
                numerator, denominator, valid = expression
                data = store.con.execute(f'SELECT g{index},count(*),avg({numerator}) FROM {store.table} WHERE {valid} GROUP BY 1 ORDER BY 1').fetchall()
            groups.append({g: (n, mean) for g, n, mean in data})
        a, b = groups; total_a = sum(n for n, m in a.values()); total_b = sum(n for n, m in b.values())
        record = {'metric': metric, 'cohort': cohort.id, 'prediction_derived': cohort.prediction_derived,
                  'reference_support': total_a, 'current_support': total_b, 'status': 'unavailable', 'groups': []}
        if {'unretained','unresolved'} & (a.keys() | b.keys()):
            record['reason'] = 'cohort_context_unretained_or_conflicting'; result.append(record); continue
        if not total_a or not total_b: record['reason'] = 'zero_denominator'; result.append(record); continue
        common = a.keys() & b.keys()
        record['common_reference_mass'] = sum(a[g][0] for g in common)/total_a
        record['common_current_mass'] = sum(b[g][0] for g in common)/total_b
        finite_common = [g for g in common if all(math.isfinite(v) for v in (a[g][1],b[g][1]))]
        if finite_common:
            mass = sum(a[g][0] for g in finite_common)
            record['common_support_standardization'] = {'reference_weighted_reference':sum(a[g][0]*a[g][1] for g in finite_common)/mass,
                'reference_weighted_current':sum(a[g][0]*b[g][1] for g in finite_common)/mass,
                'excluded_reference_mass':1-sum(a[g][0] for g in finite_common)/total_a,
                'excluded_current_mass':1-sum(b[g][0] for g in finite_common)/total_b,
                'interpretation':'Common-support observed-population standardization; excluded groups are not imputed.'}
        if a.keys() != b.keys(): record['reason'] = 'new_or_disappearing_groups'; result.append(record); continue
        if any(m is None or not math.isfinite(m) for groups in (a, b) for n, m in groups.values()):
            record['reason'] = 'nonfinite_group_mean'; result.append(record); continue
        mix = within = standardized = delta = 0.
        for group in sorted(a):
            na, ma = a[group]; nb, mb = b[group]; wa, wb = na/total_a, nb/total_b
            cmix = (wb-wa)*(mb+ma)/2; cwithin = (mb-ma)*(wb+wa)/2
            mix += cmix; within += cwithin; standardized += wa*mb; delta += wb*mb-wa*ma
            record['groups'].append({'group': group, 'reference_weight': wa, 'current_weight': wb,
                                    'reference_mean': ma, 'current_mean': mb, 'mix': cmix, 'within': cwithin,
                                    'reference_support': na, 'current_support': nb})
        if not math.isclose(mix+within, delta, rel_tol=1e-10, abs_tol=1e-12): raise AssertionError('Mix decomposition failed reconciliation')
        record.update(status='completed', mix=mix, within=within, aggregate_delta=delta,
                      reference_weight_standardized_current=standardized, causal_attribution=False)
        result.append(record)
    return result


def _drift(left, right, spec, edge):
    from datatrust.distribution_effects import numeric_effect, categorical_effect, numeric_geometry
    target_compatible=left.metadata['task']==right.metadata['task'] and left.metadata['outcome_definition_version']==right.metadata['outcome_definition_version']
    con = left.con; numeric = {'point_prediction': ('point', 'point'), 'ranking_score': ('rank_score', 'rank_score')}
    if left.run.probabilities and right.run.probabilities and left.spec.task.classes == right.spec.task.classes:
        for index in range(len(left.spec.task.classes)): numeric['probability_class_' + str(index)] = (f'probs[{index+1}]', f'probs[{index+1}]')
    for feature, meaning in spec.features.items():
        expression = 'json_extract_string(history_context,' + literal('$.' + json.dumps(feature)) + ')'
        if meaning == 'numeric': numeric['feature:' + feature] = (f'try_cast({expression} AS DOUBLE)', f'try_cast({expression} AS DOUBLE)')
    if left.run.probabilities and right.run.probabilities:
        numeric['observed_brier_loss']=('CASE WHEN outcome_valid AND prob_valid THEN brier END',)*2
        numeric['observed_log_loss']=("CASE WHEN outcome_valid AND prob_valid THEN CASE WHEN log_infinite THEN 'inf'::DOUBLE ELSE log_loss END END",)*2
    for metric in sorted(set(getattr(left,'extra_metadata',{})) & set(getattr(right,'extra_metadata',{}))):
        if any(token in metric for token in ('efficiency','crps','pinball','wis')):
            numeric['output:'+metric]=tuple(f'(SELECT x.value FROM {store.loss_table} x WHERE x.ordinal={store.table}.ordinal AND x.metric={literal(metric)} AND x.eligible AND x.defined)' for store in (left,right))
    if left.spec.task.kind == right.spec.task.kind == 'regression':
        numeric['observed_absolute_error']=('CASE WHEN outcome_valid THEN abs(point-y_num) END',)*2
        numeric['observed_residual'] = ('CASE WHEN outcome_valid THEN point-y_num END',)*2
    for index, interval in enumerate(left.run.intervals):
        if index < len(right.run.intervals) and interval.coverage == right.run.intervals[index].coverage and interval.meaning == right.run.intervals[index].meaning:
            numeric['interval_width_' + str(index)] = (f'w{index}', f'w{index}')
    result = []
    for field, (a, b) in numeric.items():
        record = {'comparison': edge.id, 'field': field, 'kind': 'numeric', 'status': 'unavailable'}
        if field.startswith('feature:') and any(store.coverage['feature_retention'].get(field[8:],0)<store.coverage['selected_predictions'] for store in (left,right)):
            record['reason']='partial_feature_retention';result.append(record);continue
        if not target_compatible and not field.startswith('feature:'):
            record['reason']='incompatible_target_semantics';result.append(record);continue
        if field == 'ranking_score' and left.metadata['signature']['score'] != right.metadata['signature']['score']:
            record['reason'] = 'score_semantics_changed'; result.append(record); continue
        temporary = 'drift_' + digest([edge.id, field])[:14]
        con.execute(f'CREATE TEMP TABLE {temporary}_a AS SELECT {a} v FROM {left.table}')
        con.execute(f'CREATE TEMP TABLE {temporary}_b AS SELECT {b} v FROM {right.table}')
        counts = [con.execute(f'SELECT count(*),count(*) FILTER(WHERE v IS NULL),count(*) FILTER(WHERE v IS NOT NULL AND NOT isfinite(v)),count(*) FILTER(WHERE v IS NOT NULL AND isfinite(v)) FROM {temporary}_{side}').fetchone() for side in ('a', 'b')]
        record.update(reference_counts=counts[0], current_counts=counts[1])
        if counts[0][3] and counts[1][3]:
            if any(numeric_geometry(con, temporary+'_'+side, 'v', 'v IS NOT NULL AND isfinite(v)') for side in ('a', 'b')):
                record['reason'] = 'unsafe_floating_resolution'
            else:
                ks, w1, ties = numeric_effect(con, temporary+'_a', 'v', 'v IS NOT NULL AND isfinite(v)', temporary+'_b', 'v', 'v IS NOT NULL AND isfinite(v)', counts[0][3], counts[1][3], constant_zero=True)
                quartiles = con.execute(f'SELECT quantile_cont(v,.25),quantile_cont(v,.75) FROM {temporary}_a WHERE isfinite(v)').fetchone()
                scale = quartiles[1]-quartiles[0]
                if not math.isfinite(w1):
                    record.update(reason='nonfinite_distribution_geometry');result.append(record)
                    for side in ('a','b'):con.execute(f'DROP TABLE {temporary}_{side}')
                    continue
                record.update(status='completed', ks_distance=ks, wasserstein_1=w1, reference_iqr_scaled_w1=w1/scale if math.isfinite(scale) and scale > 0 else None, tied_groups=ties, p_value=None)
                edges=sorted(set(con.execute(f'SELECT quantile_cont(v,?) FROM {temporary}_a WHERE isfinite(v)',[i/10]).fetchone()[0] for i in range(11)))
                if any(not math.isfinite(v) for v in edges):
                    record['histogram_reason']='unsafe_interpolation_geometry';result.append(record)
                    for side in ('a','b'):con.execute(f'DROP TABLE {temporary}_{side}')
                    continue
                def histogram(side):
                    expressions=[f'count(*) FILTER(WHERE v<{edges[0]!r})']
                    expressions += [f'count(*) FILTER(WHERE v>={lo!r} AND v<{hi!r})' for lo,hi in zip(edges,edges[1:])]
                    expressions += [f'count(*) FILTER(WHERE v={edges[-1]!r})',f'count(*) FILTER(WHERE v>{edges[-1]!r})']
                    return list(con.execute('SELECT '+','.join(expressions)+f' FROM {temporary}_{side} WHERE isfinite(v)').fetchone())
                record['frozen_reference_histogram']={'edges':edges,'reference':histogram('a'),'current':histogram('b'),
                    'convention':'below, half-open interior bins, exact maximum, above; repeated quantiles retain one boundary'}
        else: record['reason'] = 'empty_finite_population'
        result.append(record)
        con.execute(f'DROP TABLE {temporary}_a'); con.execute(f'DROP TABLE {temporary}_b'); left.work.check('historical numeric drift')
    categorical = {'issuance': 'state', 'decision': 'decision'}
    for feature, meaning in spec.features.items():
        if meaning == 'categorical': categorical['feature:' + feature] = 'json_extract_string(history_context,' + literal('$.'+json.dumps(feature)) + ')'
    for field, expression in categorical.items():
        if field.startswith('feature:') and any(store.coverage['feature_retention'].get(field[8:],0)<store.coverage['selected_predictions'] for store in (left,right)):
            result.append({'comparison':edge.id,'field':field,'kind':'categorical','status':'unavailable','reason':'partial_feature_retention'});continue
        if field=='decision' and not target_compatible:
            result.append({'comparison':edge.id,'field':field,'kind':'categorical','status':'unavailable','reason':'incompatible_target_semantics'});continue
        temporary = 'category_' + digest([edge.id, field])[:14]
        for side, store in (('a', left), ('b', right)):
            con.execute(f'CREATE TEMP TABLE {temporary}_{side} AS SELECT {expression} v FROM {store.table}')
        na, nb = [con.execute(f'SELECT count(*) FROM {temporary}_{side}').fetchone()[0] for side in ('a', 'b')]
        record = {'comparison': edge.id, 'field': field, 'kind': 'categorical', 'status': 'unavailable', 'reference_support': na, 'current_support': nb}
        if na and nb:
            record.update(categorical_effect(con, temporary+'_a', 'v', 'true', temporary+'_b', 'v', 'true', na, nb))
            counts = con.execute(f'''WITH x AS(SELECT v,count(*) a,0::BIGINT b FROM {temporary}_a GROUP BY v UNION ALL SELECT v,0::BIGINT,count(*) FROM {temporary}_b GROUP BY v)
                SELECT v,sum(a),sum(b) FROM x GROUP BY v''').fetchall()
            js = 0.
            for category, a, b in counts:
                p, q = a/na, b/nb; m = (p+q)/2
                if p: js += p*math.log(p/m)/2
                if q: js += q*math.log(q/m)/2
            record.update(status='completed', jensen_shannon_divergence_nats=js, counts=[{'category': c, 'reference': a, 'current': b} for c, a, b in counts])
        else: record['reason'] = 'zero_denominator'
        result.append(record)
        for side in ('a', 'b'): con.execute(f'DROP TABLE {temporary}_{side}')
    return result


def _temporal(stores, spec):
    result = []; windows = sorted(spec.windows, key=lambda w: instant(w.start))
    for variant in sorted({v for v, w in stores}):
        lookups = {w.id: _lookup(stores[(variant, w.id)]) for w in windows}
        exemplars = {key: m for lookup in lookups.values() for key, m in lookup.items()}
        metrics = sorted(exemplars, key=lambda key: exemplars[key]['metric_label'])
        for key in metrics:
            points = []; exemplar = exemplars[key]
            metric = exemplar['metric']
            for window in windows:
                m = lookups[window.id].get(key)
                points.append({'window': window.id, 'tick': str(instant(window.start)), 'value': m['value'] if m and m['value_state'] == 'finite' else None,
                               'support': m['denominator'] if m else 0})
            record = {'variant': variant, 'metric': metric, **metric_fields(exemplar), 'points': points, 'interpretation': 'exploratory', 'change_candidates': []}
            good = [p for p in points if p['value'] is not None and p['support']]
            if len(good) >= 3:
                magnitude=max(abs(p['value']) for p in good)
                support=sum(p['support'] for p in good)
                if magnitude and (magnitude>math.sqrt(np.finfo(float).max/(16*support)) or magnitude<math.sqrt(np.finfo(float).tiny*16*support)):
                    record['statistics_reason']='unsafe_temporal_float_geometry';result.append(record);continue
                times = np.array([(int(p['tick'])-int(good[0]['tick']))/1e9 for p in good]); values = np.array([p['value'] for p in good]); weights = np.array([p['support'] for p in good], dtype=float)
                center = np.average(times, weights=weights); denom = np.sum(weights*(times-center)**2)
                record['support_weighted_slope_per_second'] = float(np.sum(weights*(times-center)*(values-np.average(values, weights=weights)))/denom) if denom else None
                contiguous = len(good) == len(points) and len({int(points[i+1]['tick'])-int(points[i]['tick']) for i in range(len(points)-1)}) == 1 and all(instant(a.end) == instant(b.start) for a, b in zip(windows, windows[1:]))
                if contiguous and np.std(values[:-1]) and np.std(values[1:]): record['lag_one_correlation'] = float(np.corrcoef(values[:-1], values[1:])[0, 1])
                if contiguous:
                    total_cost = np.sum(weights*(values-np.average(values, weights=weights))**2)
                    candidates = []
                    for split in range(spec.min_segment_bins, len(points)-spec.min_segment_bins+1):
                        if min(weights[:split].sum(),weights[split:].sum())<spec.min_segment_support:continue
                        costs = sum(np.sum(ww*(vv-np.average(vv, weights=ww))**2) for vv, ww in ((values[:split], weights[:split]), (values[split:], weights[split:])))
                        if total_cost-costs<=0:continue
                        candidates.append({'window': points[split]['window'], 'weighted_squared_error_reduction': float(max(0., total_cost-costs)),
                                           'reference_support': int(weights[:split].sum()), 'current_support': int(weights[split:].sum()), 'p_value': None})
                    record['change_candidates'] = sorted(candidates, key=lambda c: (-c['weighted_squared_error_reduction'], c['window']))[:spec.change_candidates]
                    if spec.seasonal_period:
                        record['seasonal_phases'] = [{'phase': phase, 'mean': float(np.average(values[phase::spec.seasonal_period], weights=weights[phase::spec.seasonal_period]))} for phase in range(min(spec.seasonal_period, len(values)))]
                else: record['sequence_reason'] = 'gapped_or_overlapping_window_sequence'
            result.append(record)
    return result


def _execute_history(root, spec, sequence, effective_as_of, *, progress=None):
    started = time.monotonic(); work = compat.workspace(spec.config, 512*1024**2, progress)
    try:
        if progress: progress({'owned_workspace': str(work.root), 'stage': 'historical_evidence_materialization'})
        variants, scan = load_history(work, root, spec, sequence)
        cutoff = select_history(work, spec, effective_as_of)
        context_links(work, root, sequence, spec.max_scan_records)
        stores = {}; runs = []; measurements = []; populations = {}; locators = {}; checks = []; coverage = []
        for variant, metadata in variants.items():
            for feature, meaning in spec.features.items():
                if metadata['features'].get(feature) != meaning:
                    raise EvaluationError('Requested feature was not retained with matching semantics.', 'feature_not_retained')
            runs.append({'id': variant, 'display_name': metadata['run']['model'].get('display_name') or variant,
                         'model': metadata['run']['model'], 'role': 'historical', 'representations': metadata['signature']})
            for window in spec.windows:
                store = HistoryStore(work, spec, variant, metadata, window, cutoff); store.metadata = metadata
                store.calibration_edges = spec.calibration_edges
                stores[(variant, window.id)] = store
                store.coverage['label_observation_by_feature'] = []
                for feature,meaning in spec.features.items():
                    expr='json_extract_string(history_context,'+literal('$.'+json.dumps(feature))+')'
                    if meaning=='numeric':
                        numeric=f'try_cast({expr} AS DOUBLE)'
                        profile=store.con.execute(f'SELECT outcome_valid,count(*),count({numeric}),avg({numeric}) FILTER(WHERE isfinite({numeric})),min({numeric}) FILTER(WHERE isfinite({numeric})),max({numeric}) FILTER(WHERE isfinite({numeric})) FROM {store.table} GROUP BY outcome_valid').fetchall()
                        store.coverage['label_observation_by_feature'].append({'feature':feature,'kind':meaning,'rows':[{'observed_eligible':v[0],'support':v[1],'nonmissing':v[2],'mean':v[3],'minimum':v[4],'maximum':v[5]} for v in profile]})
                    else:
                        cardinality=store.con.execute(f'SELECT count(DISTINCT {expr}) FROM {store.table}').fetchone()[0]
                        if cardinality>spec.config.max_groups:raise EvaluationError('Observation profile category admission exceeded.','history_category_limit')
                        profile=store.con.execute(f'SELECT outcome_valid,{expr},count(*) FROM {store.table} GROUP BY 1,2').fetchall()
                        store.coverage['label_observation_by_feature'].append({'feature':feature,'kind':meaning,'rows':[{'observed_eligible':v[0],'category':v[1],'support':v[2]} for v in profile]})
                _evaluate(store, distributions_enabled=True)
                for index, cohort in enumerate(spec.cohorts):
                    for group, in work.con.execute(f'SELECT DISTINCT g{index} FROM {store.table} ORDER BY 1').fetchall():
                        if group in {'unretained', 'unresolved'}:
                            store.evidence.checks.append({'id': 'historical_cohort_'+cohort.id, 'applicability': 'blocked', 'execution': 'not_run', 'reason': 'cohort_context_unretained_or_conflicting'})
                            continue
                        _evaluate(store, f'cohort_{index}/{group}', f'g{index}={literal(group)}')
                coverage.append({'variant': variant, 'window': window.id, **store.coverage})
                work.check('historical native window metrics')
        comparisons = []; drift = []; mix = []
        planned_scopes = 1+sum(len(c.categories)+2 if c.categories else len(c.edges)+2 for c in spec.cohorts)
        # Keep unavailable requests in the family, expanding any dimensioned metrics.
        family_size = max(1, planned_scopes * sum(
            max(1, len({metric_key(m) for variant, window in (
                (edge.reference_variant, edge.reference_window), (edge.current_variant, edge.current_window))
                if (variant, window) in stores for m in stores[(variant, window)].evidence.measurements
                if m['scope']=='overall' and m['metric']==metric}))
            for edge in spec.comparisons for metric in spec.inference.metrics))
        for edge in spec.comparisons:
            if (edge.reference_variant, edge.reference_window) not in stores or (edge.current_variant, edge.current_window) not in stores:
                raise EvaluationError('Unknown compared variant/window.', 'comparison_reference')
            left = stores[(edge.reference_variant, edge.reference_window)]; right = stores[(edge.current_variant, edge.current_window)]
            status, reasons = qualification(edge, left, right)
            record = {**edge.to_dict(), 'status': status, 'reasons': reasons, 'metrics': []}
            comparisons.append(record)
            drift.extend(_drift(left, right, spec, edge))
            if status == 'blocked': continue
            paired = edge.kind == 'matched'
            reference_second = current_second = None
            if edge.kind == 'contrast_change':
                reference_second = stores.get((edge.second_reference_variant, edge.reference_window))
                current_second = stores.get((edge.second_current_variant, edge.current_window))
                if reference_second is None or current_second is None:
                    raise EvaluationError('Contrast change references unknown secondary variants.')
                if any(a.metadata['task'] != b.metadata['task'] or a.metadata['outcome_definition_version'] != b.metadata['outcome_definition_version'] or a.coverage['inline_assertion_conflicts'] or b.coverage['inline_assertion_conflicts'] for a,b in ((left,reference_second),(right,current_second))):
                    record.update(status='blocked', reasons=record['reasons']+['secondary_variant_task_incompatible']); continue
                a, a_second, reference_bases = _paired_scopes(left, reference_second, 'contrast_reference/' + edge.id)
                b, b_second, current_bases = _paired_scopes(right, current_second, 'contrast_current/' + edge.id)
                bases = {}
            elif paired: a, b, bases = _paired_scopes(left, right, 'matched/' + edge.id)
            else: a, b, bases = _lookup(left), _lookup(right), {}
            for key in sorted(a.keys() & b.keys()):
                l, r = a[key], b[key]; metric=l['metric']
                # Same metric ID is insufficient for non-equivalent interval/calibration meanings.
                if not _metric_compatible(left, right, metric, l, r):
                    continue
                value, value_state = _delta(l, r)
                second_populations = {}
                if edge.kind == 'contrast_change':
                    if key not in a_second or key not in b_second: continue
                    reference_effect, reference_state = _delta(l, a_second[key])
                    current_effect, current_state = _delta(r, b_second[key])
                    value = current_effect-reference_effect if reference_state == current_state == 'finite' else None
                    value_state = 'finite' if value is not None else 'undefined'
                    second_populations = {'reference_second_population_id': a_second[key]['population_id'],
                                          'current_second_population_id': b_second[key]['population_id'],
                                          'reference_matched_contrast': reference_effect, 'current_matched_contrast': current_effect}
                contrast = {'scope': 'overall', 'metric': metric, **metric_fields(l), 'value': value, 'value_state': value_state,
                            'reference_population_id': l['population_id'], 'current_population_id': r['population_id'],
                            'reference_support': l['denominator'], 'current_support': r['denominator'],
                            'estimand': 'matched-opportunity conditionals' if paired else 'period-specific eligible observed outcomes',
                            'inference': {'status': 'not_requested'}, **second_populations}
                materiality(contrast, l, r, spec.material_thresholds, kind=edge.kind)
                if 'practical_assessment' in contrast:
                    contrast['practical_assessment']['full_planned_population_established'] = not bool(left.coverage.get('application_failures') or right.coverage.get('application_failures'))
                if metric in spec.inference.metrics:
                    lc = contributions(left, metric, allowed_events=bases.get(key)); rc = contributions(right, metric, allowed_events=bases.get(key))
                    if paired and metric not in {'roc_auc', 'average_precision'}: lc, rc = _joint_records(lc, rc)
                    if any(s is not None and s.coverage['unqualified_method_outputs'] for s in (left,right,reference_second,current_second)):
                        contrast['inference'] = {'status': 'unavailable', 'reason': 'prior_method_membership_unavailable'}
                        if spec.inference.inference_required: raise EvaluationError('Required inference lacks prior method membership checks.', 'historical_inference_unavailable')
                    elif edge.kind == 'contrast_change':
                        additive = metric in {'accuracy', 'error_rate', 'mae', 'mse', 'bias', 'brier', 'log_loss', 'material_error_rate','empirical_cost'} or metric.startswith(('interval_coverage@', 'interval_efficiency@','set_coverage@','set_efficiency@'))
                        reference_records = _contrast_records(contributions(left, metric, allowed_events=reference_bases.get(key)), contributions(reference_second, metric, allowed_events=reference_bases.get(key))) if additive else None
                        current_records = _contrast_records(contributions(right, metric, allowed_events=current_bases.get(key)), contributions(current_second, metric, allowed_events=current_bases.get(key))) if additive else None
                        contrast['inference'] = historical_bootstrap(reference_records, current_records, spec.inference, metric=metric, family_size=family_size,
                            check=work.check, left_window=(instant(next(w.start for w in spec.windows if w.id == edge.reference_window)), instant(next(w.end for w in spec.windows if w.id == edge.reference_window))),
                            right_window=(instant(next(w.start for w in spec.windows if w.id == edge.current_window)), instant(next(w.end for w in spec.windows if w.id == edge.current_window))),
                            available_bytes=spec.config.memory_bytes//2)
                    else:
                        contrast['inference'] = historical_bootstrap(lc, rc, spec.inference, metric=metric, family_size=family_size,
                            check=work.check, left_window=(instant(next(w.start for w in spec.windows if w.id == edge.reference_window)), instant(next(w.end for w in spec.windows if w.id == edge.reference_window))),
                            right_window=(instant(next(w.start for w in spec.windows if w.id == edge.current_window)), instant(next(w.end for w in spec.windows if w.id == edge.current_window))),
                            available_bytes=spec.config.memory_bytes//2, paired=paired)
                record['metrics'].append(contrast)
                if not paired and edge.kind != 'contrast_change': mix.extend({'comparison': edge.id, **item, **metric_fields(l)} for item in _mix(left, right, metric, spec.cohorts))
            record['metrics'].extend(_cohort_contrasts(left,right,edge,spec,family_size,work,reference_second,current_second))
            absent = set(spec.inference.metrics) - {v['metric'] for v in record['metrics']}
            record['unavailable_requested_metrics'] = sorted(absent)
            if absent and spec.inference.inference_required:
                raise EvaluationError('Required inferential metric unavailable.', 'historical_inference_unavailable')
        temporal = _temporal(stores, spec)
        for (variant, window), store in stores.items():
            e = store.evidence; e.validate_populations()
            prefix = digest([variant, window])[:12]
            for p in e.populations.values():
                p['scope'] = window + '/' + p['scope']; populations[p['id']] = p
            for m in e.measurements:
                m.update(metric_fields(m))
                m['id'] = prefix + '_' + m['id']; m['scope'] = window + '/' + m['scope']; measurements.append(m)
            locators.update(e.locators); checks.extend(e.checks)
        aid = uuid.uuid4().hex
        history = {'catalog_sequence': sequence, 'as_of': effective_as_of, 'windows': [w.to_dict() for w in spec.windows],
                   'maturity': spec.maturity, 'followup_ns': spec.followup_ns, 'comparisons': comparisons, 'drift': drift,
                   'mix': mix, 'temporal': temporal, 'window_coverage': coverage,
                   'interpretation_version': 'historical_interpretation_v2',
                   'restates': spec.restates, 'restatement_reason': spec.restatement_reason, 'outcome_only': spec.outcome_only,
                   'materialization': scan, 'family_size': family_size, 'prediction_selection': {'slots': spec.slots, 'attempts': spec.attempts,'catalog_sequence':spec.prediction_catalog_sequence or sequence,'as_of':spec.prediction_as_of or effective_as_of},
                   'as_of_interpretation': 'Workspace facts committed by K; source availability evaluated at A. Unknown source availability remains qualified.'}
        data = {'schema_version': HISTORY_RESULT, 'methodology_id': HISTORY_METHOD, 'analysis_id': aid, 'generated_at': now(),
                'name': spec.name, 'task': next(iter(variants.values()))['task'], 'runs': runs,
                'outcomes': {'authority': spec.authority, 'as_of': effective_as_of}, 'comparison': None,
                'measurements': measurements, 'checks': checks, 'findings': [],
                'coverage': {'population_provenance_version': '1.1', 'populations': list(populations.values()),
                             'retention_limits': {'maximum_investigation_details': spec.config.max_details},
                             'analytical_scope': 'All selected unique admitted historical opportunities and metric-specific populations.',
                             'limitations': LIMITATIONS, 'sampling': {'requested': spec.inference.mode}}, 'history': history}
        for edge in comparisons:
            if edge['status'] != 'compatible': data['findings'].append({'code': 'comparison_qualified', 'priority': 'Review',
                'message': 'Inspect comparison identity, maturity, output and observed-label scope.', 'comparison': edge['id'], 'reasons': edge['reasons']})
        for item in drift:
            if prioritize_drift(item, spec.drift_thresholds):
                data['findings'].append({'code': 'distribution_change', 'priority': 'Investigation', 'message': 'A declared distribution-effect threshold was exceeded; this is descriptive materiality, not statistical confirmation or degradation.', 'comparison': item['comparison'], 'field': item['field'], 'prioritization': item['prioritization']})
        missing_threshold_fields = sorted(set(spec.drift_thresholds)-{item['field'] for item in drift})
        history['unavailable_drift_threshold_fields'] = missing_threshold_fields
        private = {'schema': 'confidenceguard.history_private_manifest/1.0', 'analysis_id': aid, 'history_spec': spec.to_dict(),
                   'config': spec.config.to_dict(), 'workspace_root': str(root), 'files': {}, 'locators': locators,
                   'reproduction': {'methodology': HISTORY_METHOD, 'normalization': 'historical_facts_v1', 'numpy': np.__version__,
                                    'duckdb': __import__('duckdb').__version__, 'seed': spec.inference.seed}}
        result = LongitudinalResult(data, private, {'status': 'completed', 'backend': 'duckdb_local',
                    'duration_seconds': time.monotonic()-started, 'peak_workspace_bytes': work.peak,
                    'resource_qualification': 'Sampled controls may overshoot; measured workloads are not capacity guarantees.'})
        work.check('historical completed evidence publication')
        if len(result.json_text().encode()) > spec.config.private_bytes: raise EvaluationError('Historical result exceeds private budget.', 'private_result_limit')
        return result
    finally:
        work.close()


def _inspect_history(root,spec,sequence,effective_as_of,*,progress=None):
    work=compat.workspace(spec.config,512*1024**2,progress)
    try:
        variants,scan=load_history(work,root,spec,sequence)
        cutoff=select_history(work,spec,effective_as_of);context_links(work,root,sequence,spec.max_scan_records)
        stores={};coverage=[]
        for variant,metadata in variants.items():
            for window in spec.windows:
                store=HistoryStore(work,spec,variant,metadata,window,cutoff);store.metadata=metadata
                stores[(variant,window.id)]=store;coverage.append({'variant':variant,'window':window.id,**store.coverage})
        edges=[]
        for edge in spec.comparisons:
            a=stores.get((edge.reference_variant,edge.reference_window));b=stores.get((edge.current_variant,edge.current_window))
            if a is None or b is None:raise EvaluationError('Comparison references an unselected variant.','variant_unavailable')
            status,reasons=qualification(edge,a,b)
            edges.append({'id':edge.id,'status':status,'reasons':reasons})
        from .engine import Inspection
        return Inspection({'window_coverage':coverage,'comparisons':edges,'materialization':scan,
                'estimated_inference_work_ceiling':spec.inference.work_units,
                'cutoff':effective_as_of,'qualification':'Population preview; metric-specific denominators and statistical eligibility are validated by the assessment.'},{'status':'completed','peak_workspace_bytes':work.peak})
    finally:work.close()


def analyze(root, spec, *, progress=None, cancel=None):
    if isinstance(spec, dict): spec = LongitudinalSpec.from_dict(spec)
    sequence = spec.catalog_sequence
    if sequence is None: raise EvaluationError('Parent must freeze the catalog snapshot before execution.')
    result = compat.supervise(_execute_history, (str(root), spec, sequence, spec.as_of or now()),
                              replace(spec.config, result_bytes=spec.config.private_bytes+spec.config.result_bytes), progress=progress, cancel=cancel)
    if cancel is not None and cancel.is_set(): raise EvaluationError('Cancelled before assessment commit.', 'cancelled')
    result.seal(); LongitudinalResult.from_dict(result.to_private_dict(), private=result.private)
    if len(json.dumps(result.to_dict()).encode()) > spec.config.result_bytes: raise EvaluationError('Shareable historical result exceeds budget.', 'result_limit')
    return result
