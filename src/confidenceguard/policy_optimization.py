"""Registered finite policy search. Every backend uses the same interpreter/metrics."""
from dataclasses import replace
from decimal import Decimal
from itertools import product
import copy
import math
import json

from .contracts import EvaluationError,digest
from .policy_contracts import PolicySpec,PolicyConstraint,PolicyMetricSpec
from .policy_runtime import Interpreter,read_value,evaluate_predicate,complexity
from .policy_metrics import metric_result,constraint_state,public_stat,registered,scoped,RATES,decimal_cost,decimal_operation

BOUNDED_CODES={'policy_max_search_states_limit','policy_max_candidates_limit','policy_solver_calls_limit',
               'policy_predicate_events_limit','policy_action_cells_limit','policy_contribution_cells_limit',
               'policy_metric_records_limit','policy_dominance_pairs_limit','policy_max_cutpoints_limit','policy_selection_state_limit'}


def substitute(value,bindings):
    if type(value) is dict:
        if set(value)=={'parameter'}: return copy.deepcopy(bindings[value['parameter']])
        return {k:substitute(v,bindings) for k,v in value.items()}
    if isinstance(value,(list,tuple)): return [substitute(v,bindings) for v in value]
    return value


def bind(template,bindings):
    result=substitute(template,bindings)
    # Alternative subgraphs may have unused nodes after binding. Keep identities
    # mathematical: remove only nodes unreachable from the single entry point.
    nodes=result.get('nodes',{}); seen=set()
    def visit(key):
        if key in seen or key not in nodes: return
        seen.add(key); node=nodes[key]; kind=node.get('kind')
        children=[r['then'] for r in node.get('rules',[])]+([node['otherwise']] if node.get('otherwise') else []) if kind=='rules' else [node['accepted'],node['rejected']] if kind=='accept' else [node['admitted'],node['overflow']] if kind=='capacity' else []
        for child in children: visit(child)
    visit(result.get('root'))
    result['nodes']={k:v for k,v in nodes.items() if k in seen}
    return PolicySpec.from_dict(result)


def domains(family,pstore):
    result={}
    for p in family.parameters:
        if p.kind in {'finite','node'}: values=list(p.values)
        elif p.kind=='grid':
            a,b=Decimal(str(p.lower)),Decimal(str(p.upper)); step=(b-a)/(p.count-1)
            values=[str(a+i*step) if p.value and p.value['kind']=='field' else float(a+i*step) for i in range(p.count)]
            if not p.endpoints: values=values[1:-1]
        else: values=pstore.cutpoints(family.template['run'],'S',p.value)
        if p.kind=='cutpoints' and p.endpoints: values=[{'cut':'none'},*values,{'cut':'all'}]
        if not values: raise EvaluationError('Policy parameter has no available development choices.','policy_parameter_unavailable')
        if len(values)>pstore.limits.max_cutpoints: raise EvaluationError('Parameter domain exceeds admission.','policy_cutpoint_limit')
        result[p.id]=values
    return result


def all_metrics(study):
    values={m.id:m for m in study.objectives}
    for constraint in study.constraints:
        if constraint.metric.id in values and values[constraint.metric.id]!=constraint.metric:
            raise EvaluationError('A metric identity has inconsistent definitions.','policy_metric_identity')
        values[constraint.metric.id]=constraint.metric
    kind=study.input.evaluation.task.kind if study.input.evaluation else study.candidates[0].task.kind if study.candidates else study.families[0].template['task']['kind']
    names=['issued_coverage','abstention_rate','deferral_rate','unavailable_rate','input_unavailable_rate','issued_label_availability','labeled_issued_share','selective_risk']
    if kind!='regression':names.append('correct_issue_rate')
    for name in names:
        metric=PolicyMetricSpec('accounting:'+name,name,units='native_loss_units' if name=='selective_risk' and kind=='regression' else 'fraction')
        if metric.id in values and values[metric.id]!=metric:raise EvaluationError('Reserved action-accounting metric identity differs.','policy_metric_identity')
        values[metric.id]=metric
    return values


def evaluate_candidate(policy,study,pstore,*,baseline=False,retain_components=False,count=True):
    policy=pstore.bind_policy(policy)
    if count and not baseline: pstore.budget.charge('max_candidates')
    events,records=pstore.materialize(policy.run,'S' if pstore.phase=='selection' else 'E')
    actions,trace=Interpreter(policy,pstore.budget).apply(events,batches=pstore.input.batches)
    values={key:metric_result(m,events,records,actions,policy,study,pstore.budget,retain_components=retain_components) for key,m in all_metrics(study).items()}
    constraints=[constraint_state(c,values[c.metric.id]) for c in study.constraints]
    objectives_defined=all(values[m.id]['value_state']=='finite' for m in study.objectives)
    capacity_available=all(v['complete'] for v in trace['capacity'])
    feasible=objectives_defined and capacity_available and all(c['state']=='feasible' for c in constraints)
    return {'policy_digest':policy.policy_digest,'metrics':{k:public_stat(v) for k,v in values.items()},
            'constraints':constraints,'observed_feasibility':'feasible' if feasible else 'undefined' if not capacity_available or not objectives_defined or any(c['state']=='undefined' for c in constraints) else 'violated',
            'baseline':baseline,'complexity':list(complexity(policy)[:2]),'trace':trace},values


def objective_vector(record,study):
    return tuple(record['metrics'][m.id]['value']*(1 if m.direction=='minimize' else -1) for m in study.objectives)


def selection_key(record,study):
    values=objective_vector(record,study)
    return (math.fsum(m.weight*v for m,v in zip(study.objectives,values)),) if study.search.mode=='weighted' else values


def within_tolerance(values,reference,study):
    return all(abs(v-o)<=study.search.absolute_tolerance+study.search.relative_tolerance*abs(o) for v,o in zip(values,reference))


def encoded_tie_bounds(metric,lo,hi,weight=1.):
    """Map signed, weighted RMSE endpoints into signed, weighted MSE units."""
    if metric is None or metric.metric!='rmse' or weight==0: return lo,hi
    try:
        transform=(lambda v: weight*max(0.,v/weight)**2) if metric.direction=='minimize' else (lambda v: -weight*max(0.,-v/weight)**2)
        bounds=transform(lo),transform(hi)
    except OverflowError as exc:
        raise EvaluationError('RMSE tolerance transformation exceeds finite admission.','policy_solver_scaling') from exc
    if not all(math.isfinite(v) for v in bounds):
        raise EvaluationError('RMSE tolerance transformation exceeds finite admission.','policy_solver_scaling')
    return bounds


def choose(records,study):
    eligible=[r for r in records if (not r['baseline'] or r.get('candidate')) and r['observed_feasibility']=='feasible']
    if not eligible: return None
    def key(r): return selection_key(r,study)
    optimum=min(tuple(r.get('empirical_objective_reference',key(r))) for r in eligible)
    tied=[r for r in eligible if within_tolerance(key(r),optimum,study)]
    selected=min(tied,key=lambda r:(r['complexity'],r['policy_digest']))
    return {'policy_digest':selected['policy_digest'],'empirical_optimum':list(optimum),
            'nominated_objective':list(key(selected)),
            'within_selection_tolerance':key(selected)!=optimum,
            'rationale':'Feasible development objectives, then declared numerical tie tolerance, structural complexity and canonical definition order.'}


def frontier(records,study,budget):
    eligible=[r for r in records if r['observed_feasibility']=='feasible']; result=[]; complete=True
    for row in eligible:
        values=objective_vector(row,study); dominated=False
        for other in eligible:
            if other is row: continue
            try: budget.charge('dominance_pairs')
            except EvaluationError as exc:
                if exc.code!='policy_dominance_pairs_limit':raise
                complete=False; break
            comparison=objective_vector(other,study)
            if all(a<=b for a,b in zip(comparison,values)) and any(a<b for a,b in zip(comparison,values)):
                dominated=True; break
        if not complete: break
        if not dominated: result.append(row['policy_digest'])
    plot=None
    if len(study.objectives)>=2 and eligible:
        x,y=study.objectives[:2];xs=[Decimal(str(r['metrics'][x.id]['value'])) for r in eligible];ys=[Decimal(str(r['metrics'][y.id]['value'])) for r in eligible]
        xmin,xmax=min(xs),max(xs);ymin,ymax=min(ys),max(ys)
        nominee=(choose(records,study) or {}).get('policy_digest');shown=eligible[:255]
        primary=next((r for r in eligible if r['policy_digest']==nominee),None)
        if primary and primary not in shown:shown.append(primary)
        points=[]
        for row in shown:
            a=Decimal(str(row['metrics'][x.id]['value']));b=Decimal(str(row['metrics'][y.id]['value']))
            points.append({'policy_digest':row['policy_digest'],'x':40+float((a-xmin)/(xmax-xmin))*320 if xmax!=xmin else 200,
                'y':180-float((b-ymin)/(ymax-ymin))*140 if ymax!=ymin else 110,'nominated':row['policy_digest']==nominee,'nondominated':row['policy_digest'] in result})
        plot={'points':points,'x_metric':x.metric,'y_metric':y.metric,'x_range':[str(xmin),str(xmax)],'y_range':[str(ymin),str(ymax)],
              'omitted_display_points':len(eligible)-len(points),'interpretation':'Backend display coordinates only; discrete empirical points, without interpolation or statistical distinguishability.'}
    return {'policies':result,'dominance_complete_for_retained_pool':complete,'plot':plot,
            'axes':[m.to_dict() for m in study.objectives],
            'interpretation':'Empirical trade-offs; conditional risk, full-opportunity behavior and workload retain distinct denominators. No statistical distinguishability claim.'}


def _sweep_admission(family,study):
    if len(family.parameters)!=1: return None
    p=family.parameters[0]; nodes=family.template.get('nodes',{}); root=nodes.get(family.template.get('root'),{})
    if root.get('kind')!='accept': return None
    predicate=root['when'];guards=[]
    if predicate.get('kind')=='all':
        varying=[v for v in predicate['items'] if v.get('kind')=='compare' and v.get('constant')=={'parameter':p.id}]
        if len(varying)!=1:return None
        guards=[v for v in predicate['items'] if v is not varying[0]];predicate=varying[0]
    if predicate.get('kind')!='compare' or predicate.get('op') not in {'ge','le'} or predicate.get('constant')!={'parameter':p.id}: return None
    if p.kind=='cutpoints' and p.value!=predicate['value']: return None
    if any(m.scope=='worst_windows' for m in all_metrics(study).values()): return None
    if any(n.get('kind')!='action' for key,n in nodes.items() if key!=family.template['root']): return None
    if any(m.metric in {'r2','roc_auc','average_precision','median_absolute_error','p90_absolute_error','p95_absolute_error',
                        'balanced_accuracy','macro_f1_fixed','macro_f1_observed_classes','support_weighted_f1','selective_partial_lower','selective_partial_upper'} for m in all_metrics(study).values()): return None
    return p,predicate,root,guards


def sweep(family,domain,study,pstore):
    """Exact whole-score-group sweep of registered additive/confusion statistics."""
    admission=_sweep_admission(family,study)
    if admission is None: raise EvaluationError('This composition/metric is not admitted for grouped sweep.','policy_backend_incompatible')
    from .policy_metrics import atom
    p,predicate,root,guards=admission; first=pstore.bind_policy(bind(family.template,{p.id:domain[p.id][0]}))
    events,records=pstore.materialize(first.run,'S'); metrics=all_metrics(study)
    pstore.budget.admit('contribution_cells',len(events)*len(metrics)*2)
    pstore.budget.materialize(len(events)*len(metrics)*256)
    interpreter=Interpreter(first,pstore.budget)
    exact={k for k,m in metrics.items() if first.task.kind!='regression' and m.cost in study.evaluation_costs and m.metric in {'empirical_cost','utility','partial_lower','partial_upper','model_implied_cost'}}
    exact_operations={k for k,m in metrics.items() if m.metric in {'resource_mean','resource_total','operational_charge','charge_total'}}
    exact|=exact_operations
    def blank(): return {k:[Decimal(0) if k in exact else 0.,0.,[0.,0.,0.,0.],0] for k in metrics}
    groups={}; base=blank()
    def contribution(m,e,r,a):
        if not scoped(m,e,r): return [0.,0.,[0.,0.,0.,0.],0]
        pstore.budget.charge('contribution_cells')
        eligible,v,cells=atom(m,e,r,a,first,study)
        if not eligible: return [0.,0.,[0.,0.,0.,0.],0]
        invalid=int(cells is None and (v is None or not math.isfinite(v)))
        if m.id in exact and not invalid: v=decimal_operation(m,a,study) if m.id in exact_operations else decimal_cost(m,e,r,a,first,study)
        return [v if v is not None and math.isfinite(v) else 0.,1.,list(cells) if cells is not None else [0.,0.,0.,0.],invalid]
    def add(target,values,factor=1):
        target[0]+=factor*(Decimal(str(values[0])) if isinstance(target[0],Decimal) else values[0]); target[1]+=factor*values[1]
        for i in range(4): target[2][i]+=factor*values[2][i]
        target[3]+=factor*values[3]
    for e,r in zip(events,records):
        score,state=read_value(predicate['value'],e,first.run,pstore.budget)
        guard=evaluate_predicate({'kind':'all','items':guards},e,first.run,pstore.budget) if guards else True
        if guard is False:left=right=interpreter.node(root['rejected'],e)
        elif state!='observed':left=right=interpreter.unavailable('acceptance_input_unavailable')
        else:
            left=interpreter.node(root['accepted'],e) if guard is True else interpreter.unavailable('acceptance_input_unavailable')
            right=interpreter.node(root['rejected'],e)
        group=groups.setdefault(score,blank()) if state=='observed' else None
        for key,m in metrics.items():
            a=contribution(m,e,r,left); b=contribution(m,e,r,right); add(base[key],b)
            if group is not None: add(group[key],a); add(group[key],b,-1)
    scores=sorted(groups,reverse=predicate['op']=='ge'); position=0; totals=copy.deepcopy(base)
    number=lambda v:Decimal(v) if isinstance(v,str) else v
    ordered=sorted(domain[p.id],key=lambda v:math.inf if type(v) is dict and v['cut']=='all' else -math.inf if type(v) is dict else -number(v) if predicate['op']=='ge' else number(v))
    # Explicit endpoint order: none -> finite thresholds admitting ranked groups -> all.
    ordered=[v for v in ordered if type(v) is dict and v['cut']=='none']+[v for v in ordered if type(v) is not dict]+[v for v in ordered if type(v) is dict and v['cut']=='all']
    from .policy_metrics import F1,COUNTS
    for cut in ordered:
        pstore.budget.charge('max_cutpoints')
        while position<len(scores) and (type(cut) is dict and cut['cut']=='all' or type(cut) is not dict and (scores[position]>=number(cut) if predicate['op']=='ge' else scores[position]<=number(cut))):
            for key in metrics: add(totals[key],groups[scores[position]][key])
            position+=1
            pstore.budget.counts['sweep_group_updates']+=len(metrics)
        policy=pstore.bind_policy(bind(family.template,{p.id:cut})); values={}
        for key,m in metrics.items():
            numerator,n,cells,invalid=totals[key]; kind='mean'; value=None
            if n and not invalid:
                if m.metric in F1:
                    tp,fp,fn,_=cells; den=2*tp+fp+fn; value=2*tp/den if den else None; kind='f1'
                elif m.metric in COUNTS: value=numerator; kind='total'
                else:
                    value=numerator/Decimal(int(n)) if isinstance(numerator,Decimal) else numerator/n
                    if m.metric=='rmse': value=math.sqrt(max(0.,value)); kind='sqrt_mean'
                    elif m.metric=='absolute_bias': value=abs(value); kind='absolute_mean'
            values[key]={'metric':m.metric,'value':float(value) if value is not None else None,'value_state':'finite' if value is not None else 'undefined',
                         'denominator':int(n),'planned':len(events),'reason':None if value is not None else 'unavailable_required_contribution' if invalid else 'zero_denominator',
                         'basis':m.basis,'units':m.units,'statistic_kind':kind,'numerator':float(numerator),'cells':list(map(int,cells)) if m.metric in F1 else None,
                         'definition_digest':digest(m.to_dict()),'sensitive_counts':list(map(int,cells)) if m.metric in F1 else [int(n),len(events)-int(n)]+([int(round(numerator)),int(n-round(numerator))] if m.metric in RATES and 0<=numerator<=n else [])}
            if key in exact and value is not None: values[key].update(canonical_value=str(value),canonical_numerator=str(numerator),numerical_convention='canonical_decimal_categorical_costs_v1')
        constraints=[constraint_state(c,values[c.metric.id]) for c in study.constraints]
        feasible=all(v['value_state']=='finite' for v in (values[m.id] for m in study.objectives)) and all(c['state']=='feasible' for c in constraints)
        yield policy,{'policy_digest':policy.policy_digest,'metrics':values,'constraints':constraints,
                      'observed_feasibility':'feasible' if feasible else 'undefined' if any(v['value_state']!='finite' for v in values.values()) else 'violated',
                      'baseline':False,'complexity':list(complexity(policy)[:2]),'trace':{'sweep':'whole_equal_score_groups','ties':'inclusive'},'parameters':{p.id:cut}}


def _fixed_cells(family,domain):
    if any(p.kind!='node' for p in family.parameters): raise EvaluationError('MILP requires finite node choices in fixed residual cells.','policy_backend_incompatible')
    template=family.template; root=template['nodes'].get(template['root'],{})
    if root.get('kind')!='rules' or not root.get('otherwise'): raise EvaluationError('MILP requires fixed ordered routing and an otherwise cell.','policy_backend_incompatible')
    cells=[r['then'] for r in root['rules']]+[root['otherwise']]
    if len(set(cells))!=len(cells): raise EvaluationError('MILP cells must be distinct residual routes.','policy_backend_incompatible')
    mapping={}
    for cell in cells:
        node=template['nodes'].get(cell)
        if type(node) is not dict or set(node)!={'parameter'} or node['parameter'] not in domain: raise EvaluationError('Each MILP cell needs one finite leaf parameter.','policy_backend_incompatible')
        mapping[cell]=node['parameter']
    if set(mapping.values())!=domain.keys() or len(set(mapping.values()))!=len(cells): raise EvaluationError('MILP parameters must map one-to-one to cells.','policy_backend_incompatible')
    def references(value,path=()):
        if type(value) is dict:
            if set(value)=={'parameter'}: yield path
            else:
                for key,item in value.items(): yield from references(item,path+(key,))
        elif isinstance(value,(list,tuple)):
            for i,item in enumerate(value): yield from references(item,path+(i,))
    if any(path not in {('nodes',cell) for cell in cells} for path in references(template)):
        raise EvaluationError('Separable MILP parameters may occur only at their own cell entry.','policy_backend_incompatible')
    # A cell option may reuse fixed nodes, but never another variable cell (or
    # a route returning to it). Otherwise its statistics depend on other choices.
    def visit(key,node,cell,active):
        if key in active or key!=cell and key in mapping:
            raise EvaluationError('MILP cell subgraphs must be independent of other parameters.','policy_backend_incompatible')
        if node.get('kind')=='capacity': raise EvaluationError('Batch coupling cannot use a separable MILP.','policy_backend_incompatible')
        active=active|{key}
        for child in _children(node):
            if child not in template['nodes']: raise EvaluationError('MILP subgraph refers to an absent node.','policy_backend_incompatible')
            visit(child,template['nodes'][child],cell,active)
    for cell in cells:
        for option in domain[mapping[cell]]:
            visit(cell,option,cell,set())
    return root,cells,mapping


def _children(node):
    kind=node.get('kind')
    if kind=='rules': return [r['then'] for r in node['rules']]+([node['otherwise']] if node.get('otherwise') else [])
    if kind=='accept': return [node['accepted'],node['rejected']]
    if kind=='capacity': return [node['admitted'],node['overflow']]
    return []


def ordered_band(family,bindings):
    predicates=[]
    def scan(v):
        if isinstance(v,dict):
            if v.get('kind')=='compare' and isinstance(v.get('constant'),dict) and set(v['constant'])=={'parameter'}: predicates.append(v)
            for x in v.values(): scan(x)
        elif isinstance(v,(list,tuple)):
            for x in v: scan(x)
    scan(family.template)
    if len(predicates)!=2 or {p['op'] for p in predicates}!={'lt','ge'} or predicates[0]['value']!=predicates[1]['value']:
        raise EvaluationError('Two-cut bands require negative below a lower cut and positive at or above an upper cut on one input.','policy_backend_incompatible')
    cuts={}
    for p in predicates:
        v=bindings[p['constant']['parameter']]
        cuts[p['op']]=(math.inf if p['op']=='lt' else -math.inf) if isinstance(v,dict) and v['cut']=='all' else (-math.inf if p['op']=='lt' else math.inf) if isinstance(v,dict) else Decimal(str(v))
    return cuts['lt']<=cuts['ge']


def milp_family(family,domain,study,pstore,*,inspect_only=False,on_candidate=None,global_nomination=False):
    from .policy_solver import solve
    from .policy_metrics import F1,COUNTS,MACRO,NATIVE,scoped
    authoritative_study=study; objective_groups={}; expanded=[]; constraints=[]
    def windows(m):
        declarations=(study.input.history or {}).get('selection',{}).get('windows',[])
        if not declarations: raise EvaluationError('Worst-window metrics require frozen historical windows.','policy_backend_incompatible')
        return [replace(m,id=m.id+'@window:'+w['id'],scope='window:'+w['id']) for w in declarations]
    for m in study.objectives:
        group=windows(m) if m.scope=='worst_windows' else [m];objective_groups[m.id]=group;expanded.extend(group)
    for c in study.constraints:
        if c.metric.scope=='worst_windows':
            if (c.metric.direction=='minimize')!=(c.operator=='le'): raise EvaluationError('This worst-window constraint is disjunctive.','policy_backend_incompatible')
            constraints.extend(replace(c,id=c.id+'@'+m.scope,metric=m) for m in windows(c.metric))
        else: constraints.append(c)
    study=replace(study,objectives=tuple(expanded),constraints=tuple(constraints))
    root,cells,mapping=_fixed_cells(family,domain)
    if len(cells)>pstore.limits.max_cells or any(len(v)>pstore.limits.max_options for v in domain.values()): raise EvaluationError('Fixed-cell choices exceed admission.','policy_cell_limit')
    metrics=all_metrics(study)
    if any(m.metric in (MACRO-{'balanced_accuracy'})|NATIVE for m in metrics.values()): raise EvaluationError('Metric has no registered linear fixed-cell encoding.','policy_backend_incompatible')
    first={k:v[0] for k,v in domain.items()}; prototype=pstore.bind_policy(bind(family.template,first))
    events,records=pstore.materialize(prototype.run,'S'); partitions={c:[] for c in cells}; partitions[None]=[]
    class_denominators={key:[sum(1 for e,r in zip(events,records) if scoped(m,e,r) and r.get('outcome_valid') and r.get('y')==c) for c in prototype.task.classes]
                        for key,m in metrics.items() if m.metric=='balanced_accuracy'}
    if any(not all(values) for values in class_denominators.values()): raise EvaluationError('Fixed-class objective has absent development support.','policy_backend_incompatible')
    def terms(key,result):
        if key in class_denominators:
            den=class_denominators[key]
            return sum(float(child.get('numerator') or 0.)/(len(den)*n) for child,n in zip(result['children'],den)),0.
        return _terms(result,metrics[key])
    for i,event in enumerate(events):
        cell=root['otherwise']
        for rule in root['rules']:
            condition=evaluate_predicate(rule['when'],event,prototype.run,pstore.budget)
            if condition is None: cell=None; break
            if condition: cell=rule['then']; break
        partitions[cell].append(i)
    options=sum(len(domain[mapping[cell]]) for cell in cells)
    pstore.budget.materialize(options*(len(metrics)*96+1024))
    pstore.budget.admit('contribution_cells',len(metrics)*(len(partitions[None])+sum(len(partitions[cell])*len(domain[mapping[cell]]) for cell in cells)))
    coefficients={k:[] for k in metrics}; support={k:[] for k in metrics}; denominators={k:[] for k in metrics}; groups=[]; bindings=[]; valid=[]
    constants={}
    constant_events=[events[i] for i in partitions[None]]; constant_records=[records[i] for i in partitions[None]]
    constant_outputs=Interpreter(prototype,pstore.budget).apply(constant_events,batches=pstore.input.batches)[0]
    for key,m in metrics.items():
        constants[key]=metric_result(m,constant_events,constant_records,constant_outputs,prototype,study,pstore.budget)
        if constants[key].get('reason')=='unavailable_required_contribution' or constants[key]['value_state'] in {'positive_infinity','negative_infinity'}:
            raise EvaluationError('Fixed unavailable routes require complete finite contributions.','policy_backend_incompatible')
    for cell in cells:
        parameter=mapping[cell]; indices=partitions[cell]; group=[]
        for option in domain[parameter]:
            policy=pstore.bind_policy(bind(family.template,{**first,parameter:option}))
            if any(n['kind']=='capacity' for n in policy.nodes.values()): raise EvaluationError('Batch coupling cannot use a separable MILP.','policy_backend_incompatible')
            subset=[events[i] for i in indices]; truth=[records[i] for i in indices]
            actions=Interpreter(policy,pstore.budget).apply(subset,batches=pstore.input.batches)[0]
            group.append(len(bindings)); bindings.append((parameter,option)); option_valid=True
            for key,m in metrics.items():
                r=metric_result(m,subset,truth,actions,policy,study,pstore.budget)
                if key not in class_denominators and r['denominator'] and (r.get('numerator') is None and m.metric not in F1 or r['reason']=='unavailable_required_contribution'): option_valid=False
                a,b=terms(key,r); coefficients[key].append(a); denominators[key].append(b); support[key].append(r['denominator'])
            valid.append(option_valid)
        groups.append(group)
    n=len(bindings); rows=[]; lower=[]; upper=[]
    for group in groups: rows.append({i:1. for i in group}); lower.append(1.); upper.append(1.)
    const={key:terms(key,r) for key,r in constants.items()}
    for key,m in metrics.items():
        if m.metric in COUNTS or key in class_denominators: const[key]=(const[key][0],1.)
    def append(values,lo,hi): rows.append({i:v for i,v in enumerate(values) if v}); lower.append(lo); upper.append(hi)
    for constraint in study.constraints:
        key=constraint.metric.id; cN,cD=const[key]; N=coefficients[key]; D=denominators[key]
        append(support[key],constraint.minimum_support-constants[key]['denominator'],math.inf)
        append(D,1.-cD,math.inf)
        bound=constraint.bound
        if constraint.metric.metric=='rmse':
            if bound<0: raise EvaluationError('RMSE bounds cannot be negative.','policy_backend_incompatible')
            bound*=bound
        if constraint.metric.metric=='absolute_bias':
            if constraint.operator!='le' or bound<0: raise EvaluationError('Absolute-bias lower bounds are nonconvex.','policy_backend_incompatible')
            append([a-bound*b for a,b in zip(N,D)],-math.inf,bound*cD-cN)
            append([-a-bound*b for a,b in zip(N,D)],-math.inf,bound*cD+cN)
        else:
            values=[a-bound*b for a,b in zip(N,D)]; rhs=bound*cD-cN
            if not math.isfinite(rhs) or not all(math.isfinite(v) for v in values): raise EvaluationError('Finite constraint algebra overflowed.','policy_solver_scaling')
            append(values,-math.inf if constraint.operator=='le' else rhs,rhs if constraint.operator=='le' else math.inf)
    objectives=[]; variable_lower=[0.]*n; variable_upper=[1. if v else 0. for v in valid]; integrality=[1]*n
    for m in authoritative_study.objectives:
        if m.scope=='worst_windows':
            if m.metric=='absolute_bias' and m.direction!='minimize' or authoritative_study.search.mode=='weighted' and len(authoritative_study.objectives)>1 and m.metric=='rmse': raise EvaluationError('Worst-window objective has no admitted convex linear encoding.','policy_backend_incompatible')
            terms_by_window=[]; magnitude=0.
            for child in objective_groups[m.id]:
                cN,cD=const[child.id];N=coefficients[child.id];D=denominators[child.id]
                if any(len({D[i] for i in group})!=1 for group in groups): raise EvaluationError('Worst-window objective requires fixed denominators.','policy_backend_incompatible')
                total=cD+sum(D[group[0]] for group in groups)
                if total<=0: raise EvaluationError('A required window has no support.','policy_backend_incompatible')
                magnitude=max(magnitude,(abs(cN)+sum(max(abs(N[i]) for i in group) for group in groups))/total)
                terms_by_window.append((N,cN,total))
            aux=len(variable_lower)
            for vector,_ in objectives: vector.append(0.)
            variable_lower.append(-magnitude);variable_upper.append(magnitude);integrality.append(0)
            sign=1 if m.direction=='minimize' else -1
            if m.metric=='absolute_bias': variable_lower[-1]=0.
            for N,cN,total in terms_by_window:
                rows.append({**{i:sign*a for i,a in enumerate(N) if a},aux:-sign*total});lower.append(-math.inf);upper.append(-sign*cN)
                if m.metric=='absolute_bias': rows.append({**{i:-a for i,a in enumerate(N) if a},aux:-total});lower.append(-math.inf);upper.append(cN)
            objectives.append(([0.]*aux+[float(sign)],0.));continue
        key=m.id; cN,cD=const[key]; D=denominators[key]; N=coefficients[key]
        if any(len({D[i] for i in group})!=1 for group in groups): raise EvaluationError('Variable-denominator objectives cannot use a linear MILP.','policy_backend_incompatible')
        total=cD+sum(D[group[0]] for group in groups)
        if total<=0: raise EvaluationError('Objective denominator is undefined.','policy_backend_incompatible')
        if study.search.mode=='weighted' and len(study.objectives)>1 and m.metric=='rmse': raise EvaluationError('A weighted sum containing RMSE is not linear in MSE.','policy_backend_incompatible')
        sign=1 if m.direction=='minimize' else -1
        if m.metric=='absolute_bias':
            if m.direction!='minimize': raise EvaluationError('Maximizing absolute bias requires a nonconvex objective.','policy_backend_incompatible')
            aux=len(variable_lower)
            for vector,_ in objectives: vector.append(0.)
            variable_lower.append(0.); variable_upper.append(abs(cN)+sum(max(abs(N[i]) for i in group) for group in groups)); integrality.append(0)
            rows.append({**{i:a for i,a in enumerate(N) if a},aux:-total}); lower.append(-math.inf); upper.append(-cN)
            rows.append({**{i:-a for i,a in enumerate(N) if a},aux:-total}); lower.append(-math.inf); upper.append(cN)
            objectives.append(([0.]*aux+[1.],0.))
        else: objectives.append(([sign*a/total for a in N]+[0.]*(len(variable_lower)-n),sign*cN/total))
    if study.search.mode=='weighted': targets=[([sum(m.weight*objectives[j][0][i] for j,m in enumerate(authoritative_study.objectives)) for i in range(len(variable_lower))],sum(m.weight*objectives[j][1] for j,m in enumerate(authoritative_study.objectives)))]
    else: targets=objectives
    sizes={'solver_variables':len(variable_lower),'solver_rows':len(rows),'solver_nonzeros':sum(len(row) for row in rows)}
    for key,value in sizes.items():
        if value>getattr(pstore.limits,key): raise EvaluationError('MILP declaration exceeds admission.','policy_'+key+'_limit')
    if inspect_only:
        numerical=[solve(c,rows,lower,upper,variable_lower,variable_upper,integrality,pstore.budget,inspect_only=True) for c,_ in targets]
        return {**sizes,'objective_solves':len(targets),'tie_refinement':'bounded_one_hot_enumeration','numerical_admission':numerical},[]
    results=[]; best=None; objective_complete=True; reference=None
    def expected_objective(record,index):
        values=[(record['metrics'][m.id]['value']**2 if m.metric=='rmse' else record['metrics'][m.id]['value'])*(1 if m.direction=='minimize' else -1) for m in authoritative_study.objectives]
        return math.fsum(m.weight*v for m,v in zip(authoritative_study.objectives,values)) if authoritative_study.search.mode=='weighted' else values[index]
    def decode(result,c,constant,index):
        nonlocal best
        x=result.get('candidate')
        if x is None: return None
        if len(x)!=len(variable_lower) or any(sum(x[i] for i in group)!=1 for group in groups) or any(x[i] not in (0,1) or x[i]>variable_upper[i] for i in range(n)):
            raise EvaluationError('Solver one-hot decoding failed.','policy_solver_decode')
        chosen={bindings[i][0]:bindings[i][1] for i,v in enumerate(x[:n]) if v==1}
        policy=pstore.bind_policy(bind(family.template,chosen)); record,_=evaluate_candidate(policy,authoritative_study,pstore)
        result['certificate_transferred']=False
        if record['observed_feasibility']!='feasible':
            result['authoritative_re_evaluation']='rejected'; return None
        if index is not None:
            encoded=math.fsum(v*w for v,w in zip(c,x))+constant
            actual=expected_objective(record,index)
            result['objective_equivalence']={'encoded':encoded,'replayed':actual}
            result['objective_equivalence'].update(absolute_tolerance=1e-9,relative_tolerance=1e-9)
            close=lambda value: math.isclose(value,actual,abs_tol=1e-9,rel_tol=1e-9)
            if not close(encoded) or result.get('encoded_objective') is not None and not close(result['encoded_objective']+constant):
                result['authoritative_re_evaluation']='objective_mismatch'
                best=(policy,record); return None
        result['authoritative_re_evaluation']='feasible'; result['certificate_transferred']=True
        return policy,record
    for index,(c,constant) in enumerate(targets):
        try: result=solve(c,rows,lower,upper,variable_lower,variable_upper,integrality,pstore.budget)
        except EvaluationError as exc:
            if exc.code not in BOUNDED_CODES: raise
            objective_complete=False
            results.append({'state':'limit','candidate':None,'reason':exc.code,'purpose':'objective'})
            break
        result['purpose']='objective'; results.append(result)
        candidate=decode(result,c,constant,index)
        if candidate is None:
            objective_complete=False; break
        best=candidate
        if on_candidate:
            try: on_candidate(*candidate)
            except EvaluationError as exc:
                if exc.code not in BOUNDED_CODES: raise
                objective_complete=False;result['nomination_termination']=exc.code;break
        if result['state']!='solver_optimal_encoded_model': objective_complete=False; break
        # Lock the literal optimum for subsequent priorities, rather than
        # optimizing a secondary objective over a relaxed business requirement.
        objective=math.fsum(v*w for v,w in zip(c,result['candidate']))
        append(c,-math.inf,objective)
    results[0]['objective_plan_count']=len(targets)
    if not best or not objective_complete:
        if results: results[-1]['tie_refinement']={'complete':False,'termination':'objective_not_certified'}
        return best,results
    reference=best[1]; reference_key=selection_key(reference,authoritative_study)
    # Replace priority locks with the declared tie band in original metric units.
    del rows[-len(targets):]; del lower[-len(targets):]; del upper[-len(targets):]
    # Across families/outer routes, the final reference is not known yet. For
    # r<=1, U(x)=x+abs_tol+r*abs(x) is nondecreasing. Every future global
    # reference has first component <= this family's literal first optimum;
    # hence all global ties are inside this first-component upper envelope.
    # Later lexicographic components must stay unrestricted. For r>1 there is
    # no such monotonic guarantee, so enumerate the whole admitted one-hot space.
    global_envelope=global_nomination and authoritative_study.search.relative_tolerance<=1
    for index,(c,constant) in enumerate(targets):
        if global_nomination and (not global_envelope or index>0): continue
        weighted=authoritative_study.search.mode=='weighted'
        metric=authoritative_study.objectives[index] if not weighted or len(authoritative_study.objectives)==1 else None
        weight=metric.weight if weighted and metric is not None else 1.
        value=reference_key[index]
        tolerance=authoritative_study.search.absolute_tolerance+authoritative_study.search.relative_tolerance*abs(value)
        lo,hi=value-tolerance,value+tolerance
        # A single weighted RMSE has a monotone inverse; mixed sums are refused.
        lo,hi=encoded_tie_bounds(metric,lo,hi,weight)
        if global_nomination: lo=-math.inf
        append(c,lo-constant,hi-constant)
    tie_count=1; complete=False; termination='solver_limit'
    current=results[-1]['candidate']
    while True:
        # Enumerate tied one-hot assignments; hashes are not linear objectives.
        selected=[i for i in range(n) if current[i]==1]
        rows.append({i:1. for i in selected}); lower.append(-math.inf); upper.append(len(groups)-1.)
        try:
            result=solve([0.]*len(variable_lower),rows,lower,upper,variable_lower,variable_upper,integrality,pstore.budget)
        except EvaluationError as exc:
            if exc.code not in BOUNDED_CODES and exc.code not in {'policy_solver_rows_limit','policy_solver_nonzeros_limit'}: raise
            termination=exc.code; break
        result['purpose']='tie_refinement'; results.append(result)
        if result['state']=='solver_infeasible_encoded_model': complete=True; termination='tied_space_exhausted'; break
        try: candidate=decode(result,[],0.,None)
        except EvaluationError as exc:
            if exc.code not in BOUNDED_CODES: raise
            termination=exc.code; break
        if candidate is None: termination='no_validated_tie_candidate'; break
        current=result['candidate']; tie_count+=1
        key=selection_key(candidate[1],authoritative_study)
        if global_nomination:
            envelope_upper=reference_key[0]+authoritative_study.search.absolute_tolerance+authoritative_study.search.relative_tolerance*abs(reference_key[0])
            in_band=not global_envelope or key[0]<=envelope_upper
        else: in_band=within_tolerance(key,reference_key,authoritative_study)
        if not in_band:
            result['certificate_transferred']=False; result['authoritative_re_evaluation']='tie_band_mismatch';termination='tie_band_mismatch';break
        if on_candidate:
            try: on_candidate(*candidate)
            except EvaluationError as exc:
                if exc.code not in BOUNDED_CODES: raise
                termination=exc.code;break
        if within_tolerance(key,reference_key,authoritative_study) and (candidate[1]['complexity'],candidate[1]['policy_digest'])<(best[1]['complexity'],best[1]['policy_digest']): best=candidate
        if result['state']!='solver_optimal_encoded_model': termination='solver_limit';break
    results[-1]['tie_refinement']={'complete':complete,'evaluated':tie_count,'termination':termination,
                                  'reference_objective':list(reference_key),'order':'structural_complexity_then_policy_digest',
                                  'scope':'global_nomination_envelope' if global_envelope else 'whole_finite_family' if global_nomination else 'local_tolerance_band'}
    best[1]['empirical_objective_reference']=list(reference_key)
    return best,results


def _terms(result,metric):
    if metric.metric in {'opportunity_f1','issued_f1','f1'}:
        tp,fp,fn,_=result['cells'] or (0,0,0,0); return float(2*tp),float(2*tp+fp+fn)
    return float(result.get('numerator') or 0.),0. if metric.metric in __import__('confidenceguard.policy_metrics',fromlist=['COUNTS']).COUNTS else float(result['denominator'])


def bounded_family(family,domain,study,pstore):
    """Deterministic beam search over adjacent finite parameter choices."""
    keys=list(domain); dimensions=[len(domain[k]) for k in keys]
    starts={tuple(0 for _ in keys),tuple(n-1 for n in dimensions),tuple(n//2 for n in dimensions)}
    beam=sorted(starts); seen=set(); evaluated=0
    def ranking(row):
        if row['observed_feasibility']=='feasible': return (0,selection_key(row,study),row['policy_digest'])
        violations=tuple((0 if c['state']=='feasible' else 1, max(0.,-(c['slack'] or 0.))) for c in row['constraints'])
        return (1,violations,row['policy_digest'])
    while beam and evaluated<study.limits.max_candidates:
        layer=[]
        for state in beam:
            if state in seen: continue
            seen.add(state); pstore.budget.charge('max_search_states')
            bindings={key:domain[key][index] for key,index in zip(keys,state)}
            if family.kind=='two_cut' and not ordered_band(family,bindings):
                layer.append(((2,),state)); continue
            policy=pstore.bind_policy(bind(family.template,bindings)); row,_=evaluate_candidate(policy,study,pstore); row['parameters']=bindings
            evaluated+=1; layer.append((ranking(row),state)); yield policy,row
            if evaluated>=study.limits.max_candidates: break
        layer.sort(key=lambda pair:pair[0]); neighbors=set()
        for _,state in layer[:study.limits.beam_width]:
            for dimension,n in enumerate(dimensions):
                for step in (-1,1):
                    value=state[dimension]+step
                    if 0<=value<n:
                        nextstate=state[:dimension]+(value,)+state[dimension+1:]
                        if nextstate not in seen: neighbors.add(nextstate)
        beam=sorted(neighbors)


def pareto_milp(family,domain,study,pstore):
    """Bounded epsilon-constraint solves; never a complete-frontier certificate."""
    all_runs=[]; candidates=[]; objectives={m.id:m for m in study.objectives}
    schedules=list(study.search.epsilon_constraints)
    if not schedules:
        extrema={}
        for m in study.objectives:
            for direction in ('minimize','maximize'):
                target=replace(m,direction=direction)
                sub=replace(study,objectives=(target,),search=replace(study.search,mode='lexicographic'))
                result,runs=milp_family(family,domain,sub,pstore); all_runs.extend(runs)
                if result:
                    policy,_=result; row,_=evaluate_candidate(policy,study,pstore); candidates.append((policy,row))
                    extrema.setdefault(m.id,[]).append(row['metrics'][m.id]['value'])
        for m in study.objectives[1:]:
            values=extrema.get(m.id,[])
            if len(values)<2: continue
            lo,hi=min(values),max(values)
            for j in range(5): schedules.append([{'metric_id':m.id,'operator':'le' if m.direction=='minimize' else 'ge','bound':lo+(hi-lo)*j/4}])
    for schedule in schedules:
        extra=[]
        for i,bound in enumerate(schedule):
            if bound['metric_id'] not in objectives: raise EvaluationError('Epsilon bound references an absent objective.','policy_backend_incompatible')
            extra.append(PolicyConstraint('epsilon_'+str(i),objectives[bound['metric_id']],bound['operator'],bound['bound']))
        sub=replace(study,objectives=(study.objectives[0],),constraints=tuple((*study.constraints,*extra)),search=replace(study.search,mode='lexicographic'))
        result,runs=milp_family(family,domain,sub,pstore); all_runs.extend(runs)
        if result:
            policy,_=result; row,_=evaluate_candidate(policy,study,pstore); candidates.append((policy,row))
    return candidates,all_runs,schedules


def select_backend(family,study,space):
    if family.backend!='auto': return family.backend
    if family.routing_parameters: return 'hybrid'
    if _sweep_admission(family,study) and family.kind in {'threshold','acceptance'}: return 'sweep'
    if family.kind=='fixed_cells': return 'milp'
    return 'enumerate' if space<=study.limits.max_candidates else 'bounded'


def milp_standing(runs,result):
    objectives=[r for r in runs if r.get('purpose','objective')=='objective']
    infeasible=bool(objectives) and result is None and objectives[0]['state']=='solver_infeasible_encoded_model'
    certified=bool(objectives) and len(objectives)==objectives[0].get('objective_plan_count',1) and all(
        r['state']=='solver_optimal_encoded_model' and r.get('certificate_transferred') is True
        and r.get('authoritative_re_evaluation')=='feasible' for r in objectives)
    tie=next((r['tie_refinement'] for r in reversed(runs) if 'tie_refinement' in r),{'complete':False,'termination':'not_run'})
    complete=infeasible or certified and tie['complete']
    standing='solver_optimal_encoded_model' if certified and tie['complete'] else 'solver_optimal_objectives_tie_incomplete' if certified else 'solver_infeasible_encoded_model' if infeasible else 'validated_incumbent' if result else 'no_validated_incumbent'
    return {'solution_standing':standing,'search_coverage':'complete' if complete else 'incomplete',
            'objective_certificate_transferred':certified,'tie_refinement':tie}


def hybrid_family(family,domain,study,pstore,*,inspect_only=False,on_candidate=None):
    """Finite outer routing enumeration; every inner solve shares one budget."""
    keys=list(family.routing_parameters); leaves=tuple(p for p in family.parameters if p.id not in keys)
    if not keys or not leaves: raise EvaluationError('Hybrid search requires outer routes and inner leaf parameters.','policy_backend_incompatible')
    candidates=[]; branches=[]; complete=True; retained={}
    # Returned candidates remain live in the caller. Keep their reservation
    # through the request, including prior direct calls sharing this budget.
    retained_bytes=pstore.budget.allocations.get('hybrid_candidates',0)//4
    def collect(policy,row):
        nonlocal retained_bytes
        if on_candidate:
            on_candidate(policy,row); return
        if policy.policy_digest in retained: return
        size=len(json.dumps([policy.to_dict(),row],sort_keys=True,allow_nan=False).encode())
        try: pstore.budget.reserve('hybrid_candidates',4*(retained_bytes+size))
        except EvaluationError as exc:
            if exc.code!='policy_memory_admission': raise
            raise EvaluationError('Hybrid nomination state exceeds admission.','policy_selection_state_limit') from exc
        retained_bytes+=size;retained[policy.policy_digest]=True;candidates.append((policy,row))
    for choices in product(*(domain[k] for k in keys)):
        try:
            pstore.budget.charge('max_search_states')
            route=dict(zip(keys,choices))
            # Substitute only outer choices. Inner placeholders stay typed.
            def partial(v):
                if isinstance(v,dict):
                    if set(v)=={'parameter'}: return copy.deepcopy(route.get(v['parameter'],v))
                    return {k:partial(x) for k,x in v.items()}
                if isinstance(v,(list,tuple)): return [partial(x) for x in v]
                return v
            inner=replace(family,template=partial(family.template),parameters=leaves,routing_parameters=(),kind='fixed_cells',backend='milp')
            leaf_domain={p.id:domain[p.id] for p in leaves}
            if inspect_only:
                admission,_=milp_family(inner,leaf_domain,study,pstore,inspect_only=True)
                branches.append({'routing_digest':digest(route),'admission':admission})
                if len(branches)>=pstore.limits.solver_calls and len(branches)<math.prod(len(domain[k]) for k in keys): complete=False;break
                continue
            if study.search.mode=='pareto':
                found,runs,schedules=pareto_milp(inner,leaf_domain,study,pstore)
                for candidate in found: collect(*candidate)
                standing={'search_coverage':'incomplete','solution_standing':'sampled_epsilon_tradeoff_set'}
            else:
                result,runs=milp_family(inner,leaf_domain,study,pstore,on_candidate=collect,global_nomination=True)
                standing=milp_standing(runs,result)
            branches.append({'routing_digest':digest(route),'routing_choices':route,'solver_runs':runs,**standing})
            complete=complete and standing['search_coverage']=='complete'
            if pstore.budget.counts['solver_calls']>=pstore.limits.solver_calls:
                if len(branches)<math.prod(len(domain[k]) for k in keys): complete=False
                break
        except EvaluationError as exc:
            if exc.code not in BOUNDED_CODES: raise
            branches.append({'termination':exc.code,'search_coverage':'incomplete'});complete=False;break
    return candidates,branches,complete


def family_guidance(study,pstore):
    """S-only encoding preflight, shared with execution; never solves or reads E."""
    from .policy_solver import availability
    result=[]
    for family in study.families:
        row={'family':family.id,'requested_backend':family.backend,'status':'refused'}
        try:
            domain=domains(family,pstore);space=math.prod(len(v) for v in domain.values())
            backend=select_backend(family,study,space)
            row.update(backend=backend,declared_parameter_space=space,domain_sizes={k:len(v) for k,v in domain.items()})
            if backend=='sweep' and _sweep_admission(family,study) is None: raise EvaluationError('Grouped sweep is incompatible.','policy_backend_incompatible')
            if backend=='enumerate' and space>study.limits.max_candidates: raise EvaluationError('Finite family exceeds exhaustive admission.','policy_candidate_admission')
            if backend=='enumerate':
                keys=list(domain);checked=0
                for values in product(*(domain[k] for k in keys)):
                    pstore.budget.charge('max_search_states');bindings=dict(zip(keys,values))
                    if family.kind!='two_cut' or ordered_band(family,bindings): pstore.bind_policy(bind(family.template,bindings))
                    checked+=1
                row['typed_bindings_checked']=checked
            if backend=='milp': row['encoding'],_=milp_family(family,domain,study,pstore,inspect_only=True)
            if backend=='hybrid':
                _,branches,complete=hybrid_family(family,domain,study,pstore,inspect_only=True)
                row.update(outer_branches=branches,outer_preflight_complete=complete)
                if not complete: row.update(status='partial_guidance',reason='outer_preflight_limit');result.append(row);continue
            profile=availability() if backend in {'milp','hybrid'} else None
            row.update(status='unavailable' if profile and not profile['available'] else 'admitted',
                       reason='policy_solver_dependency' if profile and not profile['available'] else None,
                       standing='bounded_best_found' if backend=='bounded' else 'encoded_model_with_recorded_tolerances' if profile else 'declared_finite_family')
            if backend=='bounded': row.update(status='partial_guidance',reason='bounded_composition_requires_per_candidate_validation')
        except EvaluationError as exc: row.update(reason=exc.code)
        result.append(row)
    return result


def search(study,pstore):
    policies={}; records=[]; searches=[]; evaluated=0; retained_omissions=0; retained_bytes=0; sizes={}
    contenders={}; contender_sizes={}; contender_bytes=0; reference=None
    def track(policy,row):
        nonlocal contender_bytes,reference
        if row['baseline'] or row['observed_feasibility']!='feasible': return
        key=selection_key(row,study)
        actual_reference=tuple(row.get('empirical_objective_reference',key))
        previous=reference; reference=min(reference,actual_reference) if reference is not None else actual_reference
        # Any future lexicographic optimum has a no-larger first component.
        # Keep every potentially eligible tolerance tie, including all later
        # components, independently of the displayed candidate pool. Very large
        # relative tolerances need the entire evaluated pool; do not prune them.
        if study.search.relative_tolerance<=1:
            if previous is None or previous[0]!=reference[0]:
                for digest_ in list(contenders):
                    if not within_tolerance((selection_key(contenders[digest_][1],study)[0],),(reference[0],),study):
                        contenders.pop(digest_);contender_bytes-=contender_sizes.pop(digest_)
            if not within_tolerance((key[0],),(reference[0],),study): return
        size=len(json.dumps([policy.to_dict(),row],sort_keys=True,allow_nan=False).encode())
        new_size=contender_bytes-contender_sizes.get(policy.policy_digest,0)+size
        try: pstore.budget.reserve('selection_contenders',new_size*4)
        except EvaluationError as exc:
            if exc.code!='policy_memory_admission': raise
            raise EvaluationError('Analytical nomination state exceeds admission; search is incomplete.','policy_selection_state_limit') from exc
        contender_bytes=new_size;contender_sizes[policy.policy_digest]=size
        contenders[policy.policy_digest]=(policy.to_dict(),row)
    actions=[{'kind':'supplied'},{'kind':'abstain'}]
    if pstore.task.kind!='regression':actions.extend({'kind':'label','label':c} for c in pstore.task.classes)
    def deferred(value):
        if isinstance(value,dict):
            if value.get('kind')=='defer' and value not in actions:actions.append(value)
            for v in value.values():deferred(v)
        elif isinstance(value,(tuple,list)):
            for v in value:deferred(v)
    for definition in (*study.candidates,*study.baselines):deferred(definition.to_dict())
    for family in study.families:
        deferred(family.template)
        for parameter in family.parameters:deferred(parameter.values)
    baselines=list(study.baselines)
    for action in actions:
        policy=pstore.bind_policy(PolicySpec(pstore.task,pstore.anchor,{'root':{'kind':'action','action':action}},'root',{'kind':'abstain'},{'kind':'unavailable'}))
        if all(policy.policy_digest!=p.policy_digest for p in baselines):baselines.append(policy)
    width=len(all_metrics(study));pool_limit=min(study.limits.max_candidates+len(baselines),study.limits.metric_records//width)
    if pool_limit<=len(baselines):raise EvaluationError('Retained detail must include the mandatory baselines and a nominated candidate.','policy_metric_records_limit')
    def keep(policy,row):
        nonlocal evaluated,retained_omissions,retained_bytes
        evaluated+=1
        track(policy,row)
        if policy.policy_digest in policies:
            if not row['baseline']:
                next(r for r in records if r['policy_digest']==policy.policy_digest)['candidate']=True
            return
        replaced=False
        size=len(json.dumps([policy.to_dict(),row],sort_keys=True,allow_nan=False).encode())
        other_memory=sum(v for k,v in pstore.budget.allocations.items() if k!='candidate_records')
        ceiling=min(pstore.budget.config.private_bytes//2,max(0,pstore.budget.materialized_limit-other_memory)//4)
        while len(records)>=pool_limit or retained_bytes+size>ceiling:
            # Exact scalar analysis continues; retain the best development rows.
            candidates=[r for r in records if not r['baseline']]
            if not candidates: raise EvaluationError('Baseline retention exceeds admission.','policy_max_candidates_limit')
            def order(r):
                return (0,tuple(r.get('empirical_objective_reference',selection_key(r,study))),r['complexity'],r['policy_digest']) if r['observed_feasibility']=='feasible' else (1,(),r['complexity'],r['policy_digest'])
            # Display retention uses the same objective ordering. Analytical
            # nomination and tolerance ties live in their separately bounded set.
            worst=max(candidates,key=order)
            if order(row)>=order(worst):
                retained_omissions+=1; return
            records.remove(worst); policies.pop(worst['policy_digest']); retained_bytes-=sizes.pop(worst['policy_digest']); retained_omissions+=1
            replaced=True
        if not replaced: pstore.budget.charge('metric_records',len(row['metrics']))
        retained_bytes+=size;sizes[policy.policy_digest]=size
        pstore.budget.reserve('candidate_records',retained_bytes*4)
        policies[policy.policy_digest]=policy.to_dict(); records.append(row)
    for policy in baselines:
        row,_=evaluate_candidate(policy,study,pstore,baseline=True)
        row['comparison_role']='supplied_trace_only' if policy.nodes[policy.root].get('action',{}).get('kind')=='supplied' else 'declared_or_conventional_task_baseline'
        keep(policy,row)
    for policy in study.candidates:
        row,_=evaluate_candidate(policy,study,pstore); keep(policy,row)
    for family in study.families:
        domain=domains(family,pstore); space=math.prod(len(v) for v in domain.values())
        admission=_sweep_admission(family,study)
        backend=select_backend(family,study,space)
        record={'family':family.id,'backend':backend,'declared_parameter_space':space,'domain_digest':digest(domain),'search_coverage':'complete','evaluated':0,'certificate_scope':'Declared finite development family only.'}
        before=evaluated
        try:
            if backend=='sweep':
                for policy,row in sweep(family,domain,study,pstore): keep(policy,row)
                record['solution_standing']='exact_grouped_empirical_search'
            elif backend=='milp':
                if study.search.mode=='pareto':
                    results,solvers,schedules=pareto_milp(family,domain,study,pstore)
                    for policy,row in results: keep(policy,row)
                    record.update(solver_runs=solvers,epsilon_schedule=schedules,search_coverage='incomplete',solution_standing='sampled_epsilon_tradeoff_set')
                    record['evaluated']=evaluated-before; searches.append(record); continue
                result,solvers=milp_family(family,domain,study,pstore,on_candidate=keep,global_nomination=True); record['solver_runs']=solvers
                standing=milp_standing(solvers,result)
                record.update(standing)
                if result and solvers[0].get('authoritative_re_evaluation')=='objective_mismatch': keep(*result)
            elif backend=='hybrid':
                candidates,branches,complete=hybrid_family(family,domain,study,pstore,on_candidate=keep)
                record.update(branches=branches,search_coverage='complete' if complete else 'incomplete',
                              solution_standing='complete_outer_routing_with_encoded_inner_optima' if complete else 'bounded_hybrid_best_found',
                              termination='outer_space_exhausted' if complete else 'inner_or_outer_limit')
            else:
                if backend=='bounded':
                    for policy,row in bounded_family(family,domain,study,pstore): keep(policy,row)
                    record.update(search_coverage='incomplete',solution_standing='bounded_best_found',search_strategy='deterministic_adjacent_choice_beam',termination='candidate_or_neighborhood_limit')
                    record['evaluated']=evaluated-before; searches.append(record); continue
                if backend=='enumerate' and space>study.limits.max_candidates: raise EvaluationError('Explicit exhaustive family exceeds candidate admission.','policy_candidate_admission')
                keys=list(domain); states=0
                for values in product(*(domain[k] for k in keys)):
                    if states>=study.limits.max_candidates:
                        record.update(search_coverage='incomplete',termination='candidate_limit'); break
                    pstore.budget.charge('max_search_states'); states+=1
                    bindings=dict(zip(keys,values))
                    if family.kind=='two_cut' and not ordered_band(family,bindings): continue
                    policy=pstore.bind_policy(bind(family.template,bindings)); row,_=evaluate_candidate(policy,study,pstore); row['parameters']=bindings; keep(policy,row)
                record['solution_standing']='exact_finite_enumeration' if record['search_coverage']=='complete' and backend=='enumerate' else 'bounded_best_found'
                if backend=='bounded': record['search_coverage']='incomplete'; record['search_strategy']='canonical_bounded_product_neighborhood'
        except EvaluationError as exc:
            if exc.code not in BOUNDED_CODES: raise
            record.update(search_coverage='incomplete',termination=exc.code,solution_standing='bounded_best_found')
        record['evaluated']=evaluated-before; searches.append(record)
    nomination=choose([row for _,row in contenders.values()],study)
    chosen=contenders[nomination['policy_digest']] if nomination else None
    pstore.budget.allocations.pop('selection_contenders',None)
    contenders.clear();contender_sizes.clear()
    if nomination:
        definition,row=chosen;key=nomination['policy_digest']
        row['empirical_objective_reference']=nomination['empirical_optimum']
        if key not in policies:
            size=len(json.dumps([definition,row],sort_keys=True,allow_nan=False).encode())
            ceiling=min(pstore.budget.config.private_bytes//2,max(0,pstore.budget.materialized_limit-sum(v for k,v in pstore.budget.allocations.items() if k!='candidate_records'))//4)
            removed=0
            while len(records)>=pool_limit or retained_bytes+size>ceiling:
                expendable=[r for r in records if not r['baseline']]
                if not expendable: raise EvaluationError('Nomination and mandatory baselines exceed retention admission.','policy_metric_records_limit')
                discarded=expendable[-1];records.remove(discarded);policies.pop(discarded['policy_digest']);retained_bytes-=sizes.pop(discarded['policy_digest'])
                removed+=1
            policies[key]=definition;records.append(row);sizes[key]=size;retained_bytes+=size
            pstore.budget.reserve('candidate_records',retained_bytes*4)
            retained_omissions+=max(0,removed-1)
        else:
            next(r for r in records if r['policy_digest']==key)['empirical_objective_reference']=nomination['empirical_optimum']
        nomination['tie_coverage']='complete_for_declared_families' if all(s['search_coverage']=='complete' for s in searches) else 'incomplete_best_found'
    return records,policies,searches,nomination,{'evaluated_candidates':evaluated,'retained_candidates':len(records),'omitted_candidate_detail':retained_omissions,
        'objective_optimum_preserved':True,'selection_tie_coverage':nomination['tie_coverage'] if nomination else 'no_feasible_nominee'}
