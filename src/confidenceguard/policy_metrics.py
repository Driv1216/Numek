"""Registered CG5 operational/contribution adapters; native metrics retain CG1 semantics."""
from collections import Counter
from decimal import Decimal
import math

from .contracts import EvaluationError,digest
from .policy_runtime import action_key,numeric_loss

RATES={'issued_coverage','abstention_rate','deferral_rate','unavailable_rate','input_unavailable_rate',
       'issued_label_availability','labeled_issued_share',
       'label_availability','correct_issue_rate','issued_accuracy','accuracy','error_rate','selective_risk',
       'precision','opportunity_recall','issued_recall','specificity','false_positive_rate','false_negative_rate',
       'material_error_rate'}
LOSSES={'mae','mse','rmse','bias','absolute_bias','pinball','empirical_cost','utility','operational_charge',
        'resource_mean','model_implied_cost','partial_lower','partial_upper','selective_partial_lower','selective_partial_upper'}
COUNTS={'issued_count','abstention_count','deferral_count','unavailable_count','resource_total','charge_total'}
F1={'opportunity_f1','issued_f1','f1'}
MACRO={'balanced_accuracy','macro_f1_fixed','macro_f1_observed_classes','support_weighted_f1'}
NATIVE={'median_absolute_error','p90_absolute_error','p95_absolute_error','r2','roc_auc','average_precision',
        'brier','log_loss','interval_coverage','interval_width'}
METRICS=RATES|LOSSES|COUNTS|F1|MACRO|NATIVE
FORMAL_UNSUPPORTED={'r2','roc_auc','average_precision','median_absolute_error','p90_absolute_error',
                    'p95_absolute_error','macro_f1_observed_classes','support_weighted_f1'}|COUNTS


def bernoulli_contribution(metric,task):
    """A population-level property of the registered contribution, not its sample."""
    if metric.metric=='selective_risk' and task.kind=='regression':
        return metric.loss=='material'
    return metric.metric in RATES|{'interval_coverage'}


def claim_parameters(metric,task):
    """The controlled parameters needed to identify a completed claim's estimand."""
    result={'units':metric.units}
    if task.kind=='regression':
        result['outcome_units']=task.units
        if metric.metric=='selective_risk': result['loss']=metric.loss
        if metric.metric=='pinball' or metric.metric=='selective_risk' and metric.loss=='pinball':
            result['level']=metric.level
        if metric.metric=='material_error_rate' or metric.metric=='selective_risk' and metric.loss=='material':
            result['material_error']=task.material_error
    return result


def registered(metric,task):
    if metric.metric not in METRICS: raise EvaluationError('Policy metric is not registered.','policy_metric')
    regression={'mae','mse','rmse','bias','absolute_bias','pinball','material_error_rate','median_absolute_error','p90_absolute_error','p95_absolute_error','r2','interval_coverage','interval_width'}
    classification={'precision','opportunity_recall','issued_recall','specificity','false_positive_rate','false_negative_rate','correct_issue_rate','issued_accuracy','accuracy','error_rate'}|F1|MACRO|{'roc_auc','average_precision','brier','log_loss'}
    if task.kind=='regression' and metric.metric in classification or task.kind!='regression' and metric.metric in regression:
        raise EvaluationError('Metric differs from the policy task.','policy_metric_task')
    if metric.metric in {'precision','opportunity_recall','issued_recall','specificity','false_positive_rate','false_negative_rate'}|F1 and (metric.target or task.positive_class) not in task.classes:
        raise EvaluationError('Class-conditional policy metrics need an explicit class.','policy_metric_target')
    if metric.basis in {'model_implied','partial_lower','partial_upper'} and metric.metric not in {'empirical_cost','utility','model_implied_cost','partial_lower','partial_upper','selective_partial_lower','selective_partial_upper'}:
        raise EvaluationError('This metric does not support the requested estimand.','policy_metric_basis')
    if metric.basis=='operational' and metric.metric not in {'issued_coverage','abstention_rate','deferral_rate','unavailable_rate','input_unavailable_rate','issued_count','abstention_count','deferral_count','unavailable_count','resource_mean','resource_total','operational_charge','charge_total'}:
        raise EvaluationError('Outcome metrics cannot be labeled as known operational evidence.','policy_metric_basis')


def scoped(metric,event,record):
    scope=metric.scope
    if scope in {'overall','worst_windows'}: return True
    if scope.startswith('cohort_'):
        try: col,group=scope.split('/',1); i=int(col.removeprefix('cohort_'))
        except (ValueError,TypeError): raise EvaluationError('Invalid cohort scope.','policy_metric_scope')
        return record.get('g'+str(i))==group
    if scope.startswith('window:'): return scope[7:] in record.get('_windows',[])
    if scope.startswith('region:'):
        try: _,region,state=scope.split(':')
        except ValueError: raise EvaluationError('Invalid region scope.','policy_metric_scope')
        if state not in {'member','nonmember','available'}: raise EvaluationError('Invalid region scope state.')
        actual=event.get('regions',{}).get(region,'unavailable')
        return actual!='unavailable' if state=='available' else actual==state
    raise EvaluationError('Metric scope is not registered.','policy_metric_scope')


def cost_value(table,out,task,outcome,metric):
    if table is None: return None
    if task.kind=='regression' and table.get('kind')=='numeric_loss':
        if out['state']!='issued': return table.get('nonissued',{}).get(action_key(out))
        return numeric_loss(out['value'],outcome,table['loss'],table.get('level',.5))
    value=table.get(action_key(out),{}).get(str(outcome))
    return float(value) if value is not None else None


def charge_value(out,charges):
    key=action_key(out)
    if key not in charges: return None
    fixed=float(charges[key])
    price=float(charges.get('resource_price:'+out.get('queue',''),0.))
    return fixed+price*out.get('resource',0.)


def decimal_cost(metric,event,record,out,policy,study):
    row=study.evaluation_costs[metric.cost][action_key(out)]
    if metric.basis=='model_implied':
        probs=event['inputs'][policy.run]['probs']
        value=sum((Decimal(str(p))*Decimal(str(row[c])) for p,c in zip(probs,policy.task.classes)),Decimal(0))
    elif record.get('outcome_valid'): value=Decimal(str(row[record['y']]))
    else:
        lower=(metric.basis=='partial_lower')!=(metric.metric=='utility')
        value=(min if lower else max)(Decimal(str(row[c])) for c in policy.task.classes)
    return -value if metric.metric=='utility' else value


def decimal_operation(metric,out,study):
    if metric.metric in {'resource_mean','resource_total'}:
        if metric.target in out.get('resources_canonical',{}):return Decimal(out['resources_canonical'][metric.target])
        return Decimal(str(out.get('resource_canonical',out.get('resource',0)))) if not metric.target or out.get('queue')==metric.target else Decimal(0)
    fixed=Decimal(str(study.charges[action_key(out)]));price=Decimal(str(study.charges.get('resource_price:'+out.get('queue',''),0)))
    return fixed+price*Decimal(str(out.get('resource_canonical',out.get('resource',0))))


def _economic(metric,event,record,out,policy,study):
    task=policy.task; table=study.evaluation_costs.get(metric.cost) if metric.cost else None
    basis=metric.basis
    if metric.metric=='model_implied_cost': basis='model_implied'
    if metric.metric in {'partial_lower','partial_upper'}: basis=metric.metric
    if metric.metric in {'operational_charge','charge_total'} or basis=='operational':
        return charge_value(out,study.charges),True,None
    y=record.get('y_num') if task.kind=='regression' else record.get('y')
    observed=bool(record.get('outcome_valid'))
    if basis=='model_implied':
        r=event['inputs'].get(policy.run,{})
        if task.kind!='regression':
            probs=r.get('probs') if r.get('prob_valid') else None
            if not probs or table is None: return None,True,None
            costs=[cost_value(table,out,task,c,metric) for c in task.classes]
            if any(c is None for c in costs): return None,True,None
            return math.fsum(p*c for p,c in zip(probs,costs)),True,None
        samples=r.get('_samples')
        if not samples or table is None: return None,True,None
        costs=[cost_value(table,out,task,y,metric) for y in samples]
        return (math.fsum(costs)/len(costs) if all(v is not None for v in costs) else None),True,None
    if basis in {'partial_lower','partial_upper'}:
        if observed: return cost_value(table,out,task,y,metric),True,None
        if task.kind!='regression' and table is not None:
            costs=[cost_value(table,out,task,c,metric) for c in task.classes]
            lower=(basis=='partial_lower')!=(metric.metric=='utility')
            if all(v is not None for v in costs): return (min(costs) if lower else max(costs)),True,None
        # Explicit bounds describe the final statistic's contributions, including
        # utility's sign. atom() applies the cost-to-utility sign exactly once.
        if metric.bounds:
            value=metric.bounds[0 if basis=='partial_lower' else 1]
            return -value if metric.metric=='utility' else value,True,None
        return None,True,None
    return (cost_value(table,out,task,y,metric) if observed else None),observed,None


def atom(metric,event,record,out,policy,study):
    """Return eligibility, contribution, and fixed confusion cells when applicable."""
    task=policy.task; m=metric.metric; labeled=bool(record.get('outcome_valid'))
    issued=out['state']=='issued'; target=metric.target or task.positive_class
    y=record.get('y_num') if task.kind=='regression' else record.get('y')
    value=out.get('value'); positive=issued and value==target
    if m in {'issued_coverage','issued_count'}: return True,float(issued),None
    if m in {'abstention_rate','abstention_count'}: return True,float(out['state']=='abstained'),None
    if m in {'deferral_rate','deferral_count'}: return True,float(out['state']=='deferred'),None
    if m in {'unavailable_rate','unavailable_count'}: return True,float(out['state']=='unavailable'),None
    if m=='input_unavailable_rate': return True,float(out.get('input_unavailable',False)),None
    if m=='label_availability': return True,float(labeled),None
    if m=='issued_label_availability': return issued,float(labeled),None
    if m=='labeled_issued_share': return labeled,float(issued),None
    if m in {'resource_mean','resource_total'}:
        if metric.target:
            if metric.target in out.get('resources_unavailable',[]): return True,None,None
            return True,out.get('resources',{}).get(metric.target,out.get('resource',0.) if out.get('queue')==metric.target else 0.),None
        return True,float(out.get('resource',0.)),None
    if m in {'empirical_cost','utility','model_implied_cost','partial_lower','partial_upper','operational_charge','charge_total'}:
        contribution,eligible,cells=_economic(metric,event,record,out,policy,study)
        return eligible,-contribution if m=='utility' and contribution is not None else contribution,cells
    if m=='correct_issue_rate': return labeled,float(issued and value==y),None
    if m in {'issued_accuracy','accuracy','error_rate','selective_risk'} and task.kind!='regression':
        return labeled and issued,float(value!=y) if m in {'error_rate','selective_risk'} else float(value==y),None
    if m=='precision': return labeled and positive,float(y==target),None
    if m in {'opportunity_recall','issued_recall','false_negative_rate'}:
        eligible=labeled and y==target and (issued or m!='issued_recall')
        return eligible,float(not positive) if m=='false_negative_rate' else float(positive),None
    if m in {'specificity','false_positive_rate'}:
        return labeled and y!=target,float(positive) if m=='false_positive_rate' else float(not positive),None
    if m in F1:
        eligible=labeled and (issued or m=='opportunity_f1')
        cells=(float(positive and y==target),float(positive and y!=target),float(not positive and y==target),float(not positive and y!=target))
        return eligible,None,cells
    if m in {'mae','mse','rmse','bias','absolute_bias','pinball','material_error_rate','selective_risk'}:
        loss='squared' if m in {'mse','rmse'} else 'signed' if m in {'bias','absolute_bias'} else 'pinball' if m=='pinball' else 'material' if m=='material_error_rate' else metric.loss if m=='selective_risk' else 'absolute'
        return labeled and issued,numeric_loss(value,y,loss,metric.level,task.material_error) if labeled and issued else None,None
    if m in {'brier','log_loss'}:
        r=event['inputs'].get(policy.run,{})
        if not labeled or not r.get('prob_valid'): return False,None,None
        probs=r['probs']; index=task.classes.index(y)
        if m=='log_loss': return True,-math.log(probs[index]) if probs[index]>0 else math.inf,None
        return True,(probs[index]-1)**2 if task.kind=='binary_classification' else math.fsum((p-float(i==index))**2 for i,p in enumerate(probs)),None
    if m in {'interval_coverage','interval_width'}:
        interval=event['inputs'].get(policy.run,{}).get('_intervals',{}).get(metric.interval)
        if interval is None: return False,None,None
        return (True,interval['width'],None) if m=='interval_width' else (labeled,float(interval['lower']<=y<=interval['upper']) if labeled else None,None)
    if m in {'median_absolute_error','p90_absolute_error','p95_absolute_error','r2'}:
        return labeled and issued,numeric_loss(value,y,'squared' if m=='r2' else 'absolute') if labeled and issued else None,None
    raise EvaluationError('No registered policy contribution adapter.','policy_metric')


def metric_result(metric,events,records,outputs,policy,study,budget,*,retain_components=False):
    budget.materialize(len(events)*256)
    registered(metric,policy.task)
    m=metric.metric
    if m in {'resource_mean','resource_total'} and metric.target:
        resources={key for key,node in policy.nodes.items() if node['kind']=='capacity'}|{node['action']['queue'] for node in policy.nodes.values() if node['kind']=='action' and node['action']['kind']=='defer'}
        if metric.target not in resources: raise EvaluationError('Resource metric target is not declared by this policy.','policy_metric_target')
    if metric.scope=='worst_windows':
        from dataclasses import replace
        windows=sorted({w for record in records for w in record.get('_windows',[])})
        declared=(study.input.history or {}).get('selection',{}).get('windows',[]) if hasattr(study,'input') else []
        windows=[w['id'] for w in declared] or windows
        children=[metric_result(replace(metric,scope='window:'+w),events,records,outputs,policy,study,budget,retain_components=retain_components) for w in windows]
        defined=bool(children) and all(c['value_state']=='finite' for c in children)
        worst=(max if metric.direction=='minimize' else min)(c['value'] for c in children) if defined else None
        return {'metric':m,'value':worst,'value_state':'finite' if defined else 'undefined','denominator':sum(c['denominator'] for c in children),
                'reason':None if defined else 'unavailable_window','basis':metric.basis,'units':metric.units,'statistic_kind':'worst_window',
                'definition_digest':digest(metric.to_dict()),'windows':windows,'children':children,'sensitive_counts':[n for c in children for n in c['sensitive_counts']]}
    if m in {'selective_partial_lower','selective_partial_upper'}:
        from dataclasses import replace
        lower=m.endswith('lower'); accepted=[]; envelope=[]; identities=[]; invalid=0; canonical=[]
        proxy=replace(metric,metric='partial_lower' if lower else 'partial_upper',basis='partial_lower' if lower else 'partial_upper')
        for event,record,out in zip(events,records,outputs):
            if not scoped(metric,event,record): continue
            budget.charge('contribution_cells'); issued=out['state']=='issued'
            v=_economic(proxy,event,record,out,policy,study)[0] if issued else 0.
            if policy.task.kind!='regression' and v is not None:
                exact=decimal_cost(proxy,event,record,out,policy,study) if issued else Decimal(0)
                canonical.append(exact);v=float(exact)
            accepted.append(float(issued)); identities.append((event['event_key'],event.get('entity_key')))
            if v is None or not math.isfinite(float(v)): invalid+=1
            envelope.append(float(v) if v is not None else 0.)
        n=sum(accepted); total=math.fsum(envelope)
        result={'metric':m,'value':total/n if n and not invalid else None,'value_state':'finite' if n and not invalid else 'undefined',
                'denominator':int(n),'planned':len(accepted),'reason':'unavailable_required_contribution' if invalid else 'zero_denominator' if not n else None,
                'basis':proxy.basis,'units':metric.units,'statistic_kind':'envelope_ratio','numerator':total,
                'definition_digest':digest(metric.to_dict()),'sensitive_counts':[int(n),len(accepted)-int(n)]}
        if n and not invalid and len(canonical)==len(accepted):
            exact_total=sum(canonical,Decimal(0));exact_mean=exact_total/Decimal(int(n))
            result.update(numerator=float(exact_total),value=float(exact_mean),canonical_numerator=str(exact_total),canonical_value=str(exact_mean))
        if retain_components: result.update(_contributions=envelope,_acceptance=accepted,_identities=identities)
        return result
    if m in MACRO:
        from dataclasses import replace
        children=[]; weights=[]
        for c in policy.task.classes:
            child=replace(metric,metric='opportunity_recall' if m=='balanced_accuracy' else 'issued_f1',target=c)
            result=metric_result(child,events,records,outputs,policy,study,budget,retain_components=retain_components)
            support=sum(1 for e,r in zip(events,records) if scoped(metric,e,r) and r.get('outcome_valid') and r.get('y')==c)
            if m in {'macro_f1_observed_classes','support_weighted_f1'} and support==0: continue
            children.append(result); weights.append(support if m=='support_weighted_f1' else 1)
        defined=children and all(c['value_state']=='finite' for c in children) and sum(weights)>0
        value=math.fsum(c['value']*w for c,w in zip(children,weights))/sum(weights) if defined else None
        return {'metric':m,'value':value,'value_state':'finite' if defined else 'undefined','denominator':sum(c['denominator'] for c in children),
                'reason':None if defined else 'undefined_class_summary','basis':metric.basis,'units':metric.units,
                'definition_digest':digest(metric.to_dict()),'statistic_kind':'class_summary','children':children,'weights':weights,
                'sensitive_counts':[v for c in children for v in c.get('sensitive_counts',[c['denominator']])]}
    if m in {'roc_auc','average_precision'}:
        return _ranking(metric,events,records,policy,budget)
    contributions=[]; identities=[]; confusions=[[],[],[],[]]; planned=0; invalid=0; exact=[]
    table=study.evaluation_costs.get(metric.cost)
    categorical_economics=policy.task.kind!='regression' and table is not None and m in {'empirical_cost','utility','partial_lower','partial_upper','model_implied_cost'}
    operational_exact=m in {'resource_mean','resource_total','operational_charge','charge_total'}
    for event,record,out in zip(events,records,outputs):
        if not scoped(metric,event,record): continue
        planned+=1; budget.charge('contribution_cells')
        eligible,value,cells=atom(metric,event,record,out,policy,study)
        if not eligible: continue
        identities.append((event['event_key'],event.get('entity_key')))
        if cells is not None:
            for array,v in zip(confusions,cells): array.append(v)
        elif value is None or type(value) not in (int,float) or math.isnan(value): invalid+=1
        else:
            contributions.append(float(value))
            if categorical_economics:
                exact.append(decimal_cost(metric,event,record,out,policy,study))
            elif operational_exact:exact.append(decimal_operation(metric,out,study))
            if categorical_economics or operational_exact:contributions[-1]=float(exact[-1])
    n=len(identities); cells=[int(sum(v)) for v in confusions]
    value=None; kind='mean'; reason=None
    if not n: reason='zero_denominator'
    elif invalid: reason='unavailable_required_contribution'
    elif m in F1:
        tp,fp,fn,_=cells; den=2*tp+fp+fn
        value=2*tp/den if den else None; kind='f1'
        if den==0: reason='zero_formula_denominator'
    elif m in COUNTS: value=math.fsum(contributions); kind='total'
    elif m in {'median_absolute_error','p90_absolute_error','p95_absolute_error'}:
        import numpy as np
        value=float(np.quantile(contributions,{'median_absolute_error':.5,'p90_absolute_error':.9,'p95_absolute_error':.95}[m])); kind='quantile'
    elif m=='r2':
        ys=[r['y_num'] for e,r,o in zip(events,records,outputs) if scoped(metric,e,r) and r.get('outcome_valid') and o['state']=='issued']
        average=math.fsum(ys)/len(ys); total=math.fsum((y-average)**2 for y in ys)
        value=1-math.fsum(contributions)/total if total else None; kind='r2'
        if value is None: reason='constant_target'
    else:
        value=math.fsum(contributions)/n
        if m=='rmse': value=math.sqrt(value); kind='sqrt_mean'
        elif m=='absolute_bias': value=abs(value); kind='absolute_mean'
    state='undefined' if value is None else 'positive_infinity' if value==math.inf else 'negative_infinity' if value==-math.inf else 'finite'
    result={'metric':m,'value':value if state=='finite' else None,'value_state':state,'denominator':n,'planned':planned,
            'reason':reason,'basis':metric.basis,'units':metric.units,'statistic_kind':kind,
            'numerator':math.fsum(contributions) if contributions and all(math.isfinite(v) for v in contributions) else None,
            'cells':cells if m in F1 else None,'sensitive_counts':cells if m in F1 else [n,planned-n]+([int(sum(contributions)),n-int(sum(contributions))] if m in RATES and all(v in (0.,1.) for v in contributions) else []),
            'definition_digest':digest(metric.to_dict())}
    if (categorical_economics or operational_exact) and exact and not invalid and state=='finite':
        total=sum(exact,Decimal(0)); mean=total if m in COUNTS else total/Decimal(n)
        if not math.isfinite(float(total)) or not math.isfinite(float(mean)):raise EvaluationError('Canonical economic reduction exceeds finite numerical representation.','policy_numeric_range')
        result.update(numerator=float(total),value=float(mean),canonical_numerator=str(total),canonical_value=str(mean),numerical_convention='canonical_decimal_categorical_costs_v1' if categorical_economics else 'canonical_decimal_operational_v1')
    if retain_components:
        result['_contributions']=contributions; result['_identities']=identities; result['_confusions']=confusions
    return result


def _ranking(metric,events,records,policy,budget):
    """Call the authoritative tie-aware CG1 ranking reducer on a bounded relation."""
    from .analytics import Evidence,ranking
    if getattr(budget,'policy_store',None) is None and hasattr(budget,'policy_native_rankings'):
        return dict(budget.policy_native_rankings[(policy.run,metric.id)])
    pstore=getattr(budget,'policy_store',None)
    if pstore is None: raise EvaluationError('Ranking requires an authoritative store.','policy_metric')
    table=pstore.store.run_tables[policy.run]; scope='policy_rank_'+digest(metric.to_dict())[:16]
    # Fixed native ranking is independent of hypothetical action issuance.
    keys=scope+'_keys'
    pstore.con.execute(f'CREATE OR REPLACE TABLE {keys}(event_key VARCHAR)')
    from . import compat
    compat.insert_rows(pstore.con,keys,[(e['event_key'],) for e,r in zip(events,records) if scoped(metric,e,r)])
    where=f'event_key IN (SELECT event_key FROM {keys})'
    e=Evidence(pstore.store); run=pstore.runs[policy.run]
    ranking(e,run,table,where,scope)
    native=next((m for m in e.measurements if m['metric']==metric.metric),None)
    if native is None:return {'metric':metric.metric,'value':None,'value_state':'undefined','denominator':0,'reason':'required_native_ranking_input_unavailable','sensitive_counts':[],
                            'basis':metric.basis,'units':metric.units,'statistic_kind':'ranking','definition_digest':digest(metric.to_dict())}
    return {**{k:native[k] for k in ('metric','value','value_state','denominator','reason','sensitive_counts')},
            'basis':metric.basis,'units':metric.units,'statistic_kind':'ranking','definition_digest':digest(metric.to_dict())}


def constraint_state(constraint,result):
    if result['value_state']!='finite' or result['denominator']<constraint.minimum_support:
        return {'id':constraint.id,'state':'undefined','slack':None,'reason':result.get('reason') or 'insufficient_support'}
    value=Decimal(result['canonical_value']) if result.get('canonical_value') is not None else result['value']
    bound=Decimal(str(constraint.bound)) if isinstance(value,Decimal) else constraint.bound
    slack=bound-value if constraint.operator=='le' else value-bound
    return {'id':constraint.id,'state':'feasible' if slack>=0 else 'violated','slack':float(slack),'reason':None}


def public_stat(result):
    return {k:([public_stat(v) for v in value] if k=='children' else value)
            for k,value in result.items() if not k.startswith('_')}


def native_measurements(pstore,policy,role,outputs=None):
    """Finalist audit/report uses the existing native reducers and population ledger."""
    from dataclasses import replace
    from types import SimpleNamespace
    from .analytics import Evidence,evaluate_scope
    from .contracts import DecisionSpec,SamplingSpec
    from . import compat
    from .policy_runtime import Interpreter
    table='policy_native_'+policy.policy_digest[:16]
    base=pstore.store.run_tables[pstore.anchor]
    pstore.con.execute(f'DROP TABLE IF EXISTS {table}_actions')
    pstore.con.execute(f'CREATE TABLE {table}_actions(event_key VARCHAR,decision VARCHAR,point DOUBLE,state VARCHAR)')
    events,_=pstore.materialize(policy.run,role)
    actions=outputs if outputs is not None else Interpreter(policy,pstore.budget).apply(events,batches=pstore.input.batches)[0]
    for start in range(0,len(events),512):
        chunk=events[start:start+512]; out=actions[start:start+512]
        compat.insert_rows(pstore.con,table+'_actions',[(e['event_key'],a['value'] if a['state']=='issued' and policy.task.kind!='regression' else None,
                      a['value'] if a['state']=='issued' and policy.task.kind=='regression' else None,
                      'hypothetical' if a['state']=='issued' else 'abstained' if a['state'] in {'abstained','deferred'} else 'failed') for e,a in zip(chunk,out)])
    preserve={'ordinal','event_key','entity_key','cg_role','y','y_num','outcome_valid','outcome_reason','history_context'}
    columns=[r[0] for r in pstore.con.execute(f'DESCRIBE {base}').fetchall()]
    input_table=pstore.store.run_tables[policy.run]
    replacements=[f'p.{col} AS {col}' for col in columns if col not in preserve and not col.startswith('g') and col not in {'decision','point','state'}]
    replacements+=['a.decision AS decision','a.point AS point','a.state AS state']
    pstore.con.execute(f'CREATE OR REPLACE TABLE {table} AS SELECT b.* REPLACE('+','.join(replacements)+f') FROM {base} b JOIN {table}_actions a USING(event_key) LEFT JOIN {input_table} p ON p.event_key=b.event_key')
    run=replace(pstore.runs[policy.run],id='policy_'+policy.policy_digest[:16],prediction=None,decision=DecisionSpec())
    store=copy_store(pstore.store,run,table)
    if pstore.history:
        from .history_selection import HistoricalEvidence
        e=HistoricalEvidence(store)
    elif policy.run!=pstore.anchor:
        class SecondaryEvidence(Evidence):
            def witnesses(self,*args,**kwargs): pass
        e=SecondaryEvidence(store)
    else: e=Evidence(store)
    e.bind_relation(table,{'kind':'frozen_policy_replay','policy_digest':policy.policy_digest,'input_fingerprint':pstore.fingerprint,'role':role})
    evaluate_scope(e,run,table,'true','overall')
    for m in e.measurements: m.update(basis='simulated',interpretation='descriptive')
    e.validate_populations()
    # Native witnesses refer to original source rows, never to synthetic policy
    # actions. Secondary runs require a different ordinal projection.
    if policy.run!=pstore.anchor and not pstore.history:
        e.locators={}
        for m in e.measurements: m['evidence_refs']=[]
    return e.measurements,list(e.populations.values()),e.locators


def copy_store(original,run,table):
    from types import SimpleNamespace
    from dataclasses import replace
    from .contracts import SamplingSpec
    store=SimpleNamespace(**vars(original)); spec=SimpleNamespace(**vars(original.spec))
    spec.runs=(run,); store.spec=spec; store.run_tables={run.id:table}
    first=next(iter(original.run_facts.values()))
    store.run_facts={run.id:first}; store.config=replace(original.config,sampling=SamplingSpec('descriptive'))
    return store
