"""Bounded typed policy interpretation; never reads outcome values."""
from collections import Counter
from decimal import Decimal
import math
import operator
import statistics
import time

from .contracts import EvaluationError, digest
from .features import value as feature_value
from .policy_contracts import PolicySpec

COUNTER_VERSION='policy_countable_operations_v1'


class Budget:
    def __init__(self, limits, config, check=lambda *args:None):
        self.limits=limits; self.config=config; self.check=check; self.counts=Counter()
        self.started=time.monotonic(); self.materialized_limit=min(limits.materialized_bytes,config.max_rss_bytes//4)
        self.allocations={}

    def charge(self, kind, count=1):
        if type(count) is not int or count<0: raise AssertionError('Invalid policy accounting')
        ceiling=getattr(self.limits,kind)
        if self.counts[kind]+count>ceiling:
            raise EvaluationError('Policy operation admission exceeded.','policy_'+kind+'_limit','policy')
        self.counts[kind]+=count
        self.check('policy '+kind)

    def admit(self,kind,upper):
        if self.counts[kind]+upper>getattr(self.limits,kind): raise EvaluationError('Policy upper-bound admission exceeded.','policy_'+kind+'_limit','policy')

    def materialize(self, size):
        if size+sum(self.allocations.values())>self.materialized_limit: raise EvaluationError('Policy materialization exceeds the explicit allocation limit.','policy_memory_admission')
        self.check('policy materialization',size)

    def reserve(self,name,size):
        previous=self.allocations.pop(name,0)
        try: self.materialize(size)
        except Exception:
            self.allocations[name]=previous
            raise
        self.allocations[name]=size

    def to_dict(self):
        return {'version':COUNTER_VERSION,'counts':dict(self.counts),
                'limits':self.limits.to_dict(),'materialized_limit_bytes':self.materialized_limit,'retained_allocation_bytes':sum(self.allocations.values())}


def action_key(action):
    if action['state']=='issued':
        return str(action['value'])
    return 'deferred:'+action['queue'] if action['state']=='deferred' else action['state']


def numeric_loss(prediction, outcome, kind='absolute', level=.5, material=None):
    residual=prediction-outcome
    if not math.isfinite(residual): return None
    if kind=='squared': result=residual*residual
    elif kind=='signed': result=residual
    elif kind=='pinball': result=(1-level)*residual if residual>=0 else -level*residual
    elif kind=='material': result=float(abs(residual)>material) if material is not None else None
    else: result=abs(residual)
    return result if result is None or math.isfinite(result) else None


def read_value(ref, event, default_run, budget=None):
    """Only explicitly projected decision inputs are present in event['inputs']."""
    kind=ref['kind']; run=ref.get('run',default_run)
    r=event.get('inputs',{}).get(run,{})
    if kind=='constant': return ref['value'],'observed'
    if budget: budget.charge('action_cells')
    if kind=='field':
        cell=event.get('features',{}).get(ref['target'])
        if cell is None: return None,'not_retained'
        return feature_value(cell),cell['state']
    if kind=='region':
        region=event.get('regions',{}).get(ref['target'])
        return (region,'observed') if region in {'member','nonmember'} else (None,'unavailable')
    if kind=='output_state': return r.get('state','missing'),'observed'
    if kind=='supplied_decision': value=r.get('decision') if r.get('state') in {'issued','hypothetical'} else None
    elif kind in {'argmax_class','argmax_score_class'}:
        values=r.get('probs') if kind=='argmax_class' and r.get('prob_valid') else r.get('scores') if kind=='argmax_score_class' else None
        if not values: return None,'unavailable'
        if budget: budget.charge('action_cells',max(0,len(values)-1))
        maximum=max(values);indices=[i for i,v in enumerate(values) if v==maximum]
        value=r['_classes'][indices[0]] if len(indices)==1 or ref.get('tie_policy')=='action_order' else None
    elif kind in {'score','selector','point','scale'}:
        value=r.get({'score':'rank_score','selector':'selector','point':'point','scale':'scale'}[kind])
        if kind=='score' and r.get('_score_meaning')!='event_ranking': value=None
        if kind=='selector' and not r.get('_has_selector'): value=None
    elif kind in {'probability','confidence','margin'}:
        probs=r.get('probs') if r.get('prob_valid') else None
        if not probs: return None,'unavailable'
        if budget and kind!='probability': budget.charge('action_cells',max(0,len(probs)-1))
        if kind=='probability':
            classes=r.get('_classes',[])
            if ref['target'] not in classes: return None,'unavailable'
            value=probs[classes.index(ref['target'])]
        elif kind=='confidence': value=max(probs)
        else:
            ordered=sorted(probs,reverse=True); value=ordered[0]-ordered[1]
    elif kind=='class_score':
        scores=r.get('scores'); classes=r.get('_classes',[])
        value=scores[classes.index(ref['target'])] if scores and ref['target'] in classes else None
    elif kind=='quantile': value=r.get('_quantiles',{}).get(ref['target'])
    elif kind.startswith('sample_'):
        values=r.get('_samples')
        if not values: return None,'unavailable'
        if budget: budget.charge('action_cells',max(0,len(values)-1))
        value=math.fsum(values)/len(values) if kind=='sample_mean' else statistics.median(values)
    elif kind.startswith('interval_'):
        interval=r.get('_intervals',{}).get(ref['target'])
        if interval is None: return None,'unavailable'
        if kind=='interval_state': value=interval['state']
        else: value=interval['width']
    elif kind.startswith('set_'):
        output=r.get('_sets',{}).get(ref['target'])
        if output is None: return None,'unavailable'
        value=output['state'] if kind=='set_state' else len(output['classes'])
    else: return None,'unavailable'
    return (value,'observed') if value is not None else (None,'unavailable')


def evaluate_predicate(p, event, run, budget=None):
    kind=p['kind']
    if kind in {'all','any'}:
        unknown=False
        for item in p['items']:
            result=evaluate_predicate(item,event,run,budget)
            if kind=='all' and result is False: return False
            if kind=='any' and result is True: return True
            unknown |= result is None
        return None if unknown else kind=='all'
    if kind=='not':
        result=evaluate_predicate(p['item'],event,run,budget)
        return None if result is None else not result
    if budget: budget.charge('predicate_events')
    if kind=='region':
        if budget: budget.charge('action_cells')
        state=event.get('regions',{}).get(p['digest'],'unavailable')
        if p['state']=='unavailable': return state=='unavailable'
        return None if state=='unavailable' else state==p['state']
    value,state=read_value(p['value'],event,run,budget)
    if kind=='state': return state==p['state']
    if state!='observed': return None
    if kind=='in':
        if isinstance(value,Decimal):
            try: return value in [Decimal(str(v)) for v in p['values']]
            except ArithmeticError: return None
        return value in p['values']
    constant=p['constant']
    if type(constant) is dict: return constant['cut']=='all'
    # Exact typed feature numerics do not round through float to define a gate.
    if isinstance(value,Decimal):
        try: constant=Decimal(str(constant))
        except Exception: return None
    if isinstance(value,bool)!=(isinstance(constant,bool)): return None
    op={'eq':operator.eq,'ne':operator.ne,'lt':operator.lt,'le':operator.le,'gt':operator.gt,'ge':operator.ge}[p['op']]
    try: return bool(op(value,constant))
    except (TypeError,ValueError,ArithmeticError): return None


class Interpreter:
    def __init__(self, policy, budget=None):
        self.policy=PolicySpec.from_dict(policy) if isinstance(policy,dict) else policy
        self.budget=budget; self.routes=Counter(); self.unknown=Counter(); self.overlaps=Counter(); self.unresolved=Counter(); self.fallbacks=Counter(); self.capacity_resources={}

    def unavailable(self, reason):
        result=self.act(self.policy.unavailable,{})
        result.update(input_unavailable=True,reason=reason)
        return result

    def act(self,a,event):
        kind=a['kind']; task=self.policy.task
        def emitted(value): return {'state':'issued','value':value,'resource':0.}
        if kind=='abstain': return {'state':'abstained','value':None,'resource':0.}
        if kind=='defer': return {'state':'deferred','value':None,'queue':a['queue'],'resource':float(a.get('resource',1)),'resource_canonical':str(a.get('resource',1))}
        if kind=='unavailable': return {'state':'unavailable','value':None,'resource':0.,'reason':a.get('reason','declared_unavailable')}
        if kind=='label': return emitted(a['label'])
        if kind=='numeric':
            value,state=(a['value'],'observed') if 'value' in a else read_value(a['source'],event,self.policy.run,self.budget)
            return emitted(float(value)) if state=='observed' and type(value) in (int,float,Decimal) and math.isfinite(float(value)) else self.unavailable('numeric_input_unavailable')
        r=event.get('inputs',{}).get(self.policy.run,{})
        if kind=='supplied':
            if r.get('state')=='abstained': return {'state':'abstained','value':None,'resource':0.}
            v=r.get('point') if task.kind=='regression' else r.get('decision')
            return emitted(v) if v is not None and r.get('state') in {'issued','hypothetical'} else self.unavailable('supplied_action_unavailable')
        if kind=='threshold':
            v,state=read_value(a['source'],event,self.policy.run,self.budget)
            if state!='observed': return self.unavailable('threshold_input_unavailable')
            yes=v>=a['threshold'] if a.get('direction','higher')=='higher' else v<=a['threshold']
            return emitted(a.get('positive',task.positive_class) if yes else a.get('negative',next(c for c in task.classes if c!=task.positive_class)))
        if kind=='argmax':
            values=r.get('probs') if a.get('source','probabilities')=='probabilities' and r.get('prob_valid') else r.get('scores') if a.get('source')=='class_scores' else None
            if not values or len(values)!=len(task.classes): return self.unavailable('argmax_input_unavailable')
            if self.budget: self.budget.charge('action_cells',len(values))
            maximum=max(values);indices=[i for i,v in enumerate(values) if v==maximum]
            if len(indices)>1 and a.get('tie_policy','abstain')=='abstain': return self.act({'kind':'abstain'},event)
            return emitted(task.classes[indices[0]])
        if kind=='expected_cost':
            table=self.policy.decision_costs[a['costs']]; actions=[self.act(v,event) for v in a['actions']]
            if a.get('source','probabilities')=='probabilities':
                probs=r.get('probs') if r.get('prob_valid') else None
                if not probs: return self.unavailable('expected_cost_inputs_unavailable')
                totals=[]
                for alt in actions:
                    row=table.get(action_key(alt))
                    if row is None or any(c not in row for c in task.classes): return self.unavailable('incomplete_decision_costs')
                    if self.budget: self.budget.charge('action_cells',len(probs))
                    totals.append(math.fsum(p*float(row[c]) for p,c in zip(probs,task.classes)))
            else:
                samples=r.get('_samples')
                if not samples or table.get('kind')!='numeric_loss': return self.unavailable('expected_cost_inputs_unavailable')
                totals=[]
                for alt in actions:
                    if self.budget: self.budget.charge('action_cells',len(samples))
                    if alt['state']!='issued':
                        charge=table.get('nonissued',{}).get(action_key(alt))
                        if charge is None: return self.unavailable('incomplete_decision_costs')
                        totals.append(float(charge)); continue
                    losses=[numeric_loss(alt['value'],y,table['loss'],table.get('level',.5)) for y in samples]
                    if any(v is None for v in losses): return self.unavailable('nonfinite_decision_cost')
                    totals.append(math.fsum(losses)/len(losses))
            if not all(math.isfinite(v) for v in totals): return self.unavailable('nonfinite_decision_cost')
            minimum=min(totals);indices=[i for i,v in enumerate(totals) if v==minimum]
            if len(indices)>1 and a.get('tie_policy','abstain')=='abstain': return self.act({'kind':'abstain'},event)
            result=actions[indices[0]].copy(); result['model_implied_decision_cost']=totals[indices[0]]
            return result
        raise AssertionError('Unvalidated action')

    def node(self,key,event,capacity=None):
        node=self.policy.nodes[key]; kind=node['kind']; self.routes[key]+=1
        if kind=='action': result=self.act(node['action'],event)
        elif kind=='rules':
            conditions=[evaluate_predicate(rule['when'],event,self.policy.run,self.budget) for rule in node['rules']]
            self.overlaps[key]+=int(sum(v is True for v in conditions)>1)
            self.unresolved[key]+=sum(v is None for v in conditions)
            for rule,condition in zip(node['rules'],conditions):
                if condition is None:
                    self.unknown[key]+=1; result=self.unavailable('unresolved_prior_rule'); break
                if condition:
                    result=self.node(rule['then'],event,capacity); break
            else:
                if not node.get('otherwise'): self.fallbacks[key]+=1
                result=self.node(node['otherwise'],event,capacity) if node.get('otherwise') else self.act(self.policy.fallback,event)
        elif kind=='accept':
            condition=evaluate_predicate(node['when'],event,self.policy.run,self.budget)
            if condition is None:
                self.unknown[key]+=1; result=self.unavailable('acceptance_input_unavailable')
            else: result=self.node(node['accepted'] if condition else node['rejected'],event,capacity)
        else:
            state=(capacity or {}).get((key,event['event_key']))
            if state is None:
                result=self.unavailable('incomplete_batch_or_resource'); result.setdefault('resources_unavailable',[]).append(key)
            else:
                result=self.node(node['admitted'] if state else node['overflow'],event,capacity)
                if state:
                    quantity=self.capacity_resources[(key,event['event_key'])]
                    result.setdefault('resources',{})[key]=float(quantity)
                    result.setdefault('resources_canonical',{})[key]=str(quantity)
        result=dict(result); result.setdefault('route',key); result.setdefault('input_unavailable',False)
        return result

    def apply(self, events, *, batches=()):
        if self.budget: self.budget.materialize(len(events)*512)
        capacity={}; declarations={b['id']:b for b in batches}; capacity_checks=[]
        # Visit guards in DAG order. A guard ranks only the events routed to it,
        # while completeness is checked against the entire declared batch.
        order=[]; visited=set()
        def visit(key):
            if key in visited: return
            visited.add(key); n=self.policy.nodes[key]
            children=([r['then'] for r in n['rules']]+([n['otherwise']] if n.get('otherwise') else [])) if n['kind']=='rules' else [n['accepted'],n['rejected']] if n['kind']=='accept' else [n['admitted'],n['overflow']] if n['kind']=='capacity' else []
            for child in children: visit(child)
            order.append(key)
        visit(self.policy.root)
        def waiting(key,event):
            n=self.policy.nodes[key]
            if n['kind']=='action': return None
            if n['kind']=='capacity':
                state=capacity.get((key,event['event_key']))
                return key if state is None else waiting(n['admitted'] if state else n['overflow'],event)
            if n['kind']=='accept':
                state=evaluate_predicate(n['when'],event,self.policy.run,self.budget)
                return None if state is None else waiting(n['accepted'] if state else n['rejected'],event)
            for rule in n['rules']:
                state=evaluate_predicate(rule['when'],event,self.policy.run,self.budget)
                if state is None: return None
                if state: return waiting(rule['then'],event)
            return waiting(n['otherwise'],event) if n.get('otherwise') else None
        for key in reversed(order):
            node=self.policy.nodes[key]
            if node['kind']!='capacity': continue
            declaration=declarations.get(node['batch'])
            if declaration is None: raise EvaluationError('Capacity batch declaration is absent.','policy_batch_contract')
            groups={}
            for event in events:
                v,state=read_value({'kind':'field','target':declaration['field']},event,self.policy.run,self.budget)
                groups.setdefault(str(v) if state=='observed' else None,[]).append(event)
            for group,items in groups.items():
                expected=declaration['members'].get(group,{})
                complete=(len(items)==expected.get('count') and digest(sorted(e['event_key'] for e in items))==expected.get('digest'))
                ranked=[]; routed=[e for e in items if waiting(self.policy.root,e)==key]
                for event in routed:
                    score,state=read_value(node['ranking'],event,self.policy.run,self.budget)
                    resource,rs=read_value(node['resource'],event,self.policy.run,self.budget) if 'resource' in node else (1.,'observed')
                    if state!='observed' or rs!='observed' or type(score) not in (float,int,Decimal) or not math.isfinite(float(score)) or type(resource) not in (float,int,Decimal) or not math.isfinite(float(resource)) or resource<0:
                        complete=False; continue
                    ranked.append((score,Decimal(str(resource)),event['event_key']))
                    self.capacity_resources[(key,event['event_key'])]=Decimal(str(resource))
                status={'node':key,'batch':group,'complete':complete,'planned':len(items),'routed':len(routed),'budget':node['budget']}
                if complete:
                    ranked.sort(key=lambda t:(-t[0] if node.get('direction','higher')=='higher' else t[0],t[2]))
                    used=Decimal(0); stopped=False; i=0
                    while i<len(ranked):
                        j=i+1
                        while j<len(ranked) and ranked[j][0]==ranked[i][0]: j+=1
                        resource=sum((r[1] for r in ranked[i:j]),Decimal(0)); accepted=not stopped and used+resource<=Decimal(str(node['budget']))
                        stopped |= not accepted
                        for _,_,event in ranked[i:j]: capacity[key,event]=accepted
                        if accepted: used+=resource
                        i=j
                    status['used_resource']=float(used);status['used_resource_canonical']=str(used)
                capacity_checks.append(status)
        outputs=[self.node(self.policy.root,event,capacity) for event in events]
        return outputs,{'routes':dict(self.routes),'unknown_routes':dict(self.unknown),'overlap_events':dict(self.overlaps),'unresolved_predicates':dict(self.unresolved),'fallback_events':dict(self.fallbacks),'capacity':capacity_checks}


def complexity(policy):
    return (len(policy.nodes),sum(len(n.get('rules',[])) for n in policy.nodes.values()),policy.policy_digest)
