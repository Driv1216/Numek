"""Finite threat-model searches. Best found never means certified robustness."""
import copy
import itertools
import math

import numpy as np

from ..contracts import EvaluationError,digest
from ..execution.services import predict_batch
from .transformations import feasible


def decision(output,task):
    if output.get('issuance') in {'abstained','missing','failed'}:return None
    if 'decision' in output:return output['decision']
    c=output.get('channels',{})
    if c.get('prediction') is not None:return c['prediction']
    return None


def objective(output,baseline,event,attack,task):
    c=output['channels'];b=baseline['channels'];pred=decision(output,task)
    if output['execution']!='completed' or output['channel_failures']:return None,False
    if attack.objective=='targeted':
        if attack.target_class not in task.classes:raise EvaluationError('Attack target class differs from task.')
        p=c.get('probabilities');value=p[task.classes.index(attack.target_class)] if p else float(pred==attack.target_class)
        return value,pred==attack.target_class
    if attack.objective=='misclassification':
        if not event['truth']['valid']:return None,False
        y=event['truth']['value'];p=c.get('probabilities')
        return (1-p[task.classes.index(y)] if p else float(pred!=y)),pred is not None and pred!=y
    if attack.objective=='loss_increase':
        if not event['truth']['valid'] or 'point' not in c or 'point' not in b:return None,False
        y=event['truth']['value'];base_truth=event.get('baseline_truth',event['truth'])
        if not base_truth['valid']:return None,False
        delta=abs(c['point']-y)-abs(b['point']-base_truth['value'])
        return delta,delta>attack.threshold
    if 'point' in c and 'point' in b:
        delta=abs(c['point']-b['point']);return delta,delta>attack.threshold
    if c.get('probabilities') and b.get('probabilities'):
        delta=float(np.max(np.abs(np.asarray(c['probabilities'])-b['probabilities'])))
        return delta,decision(output,task)!=decision(baseline,task) if attack.threshold==0 else delta>attack.threshold
    return float(pred!=decision(baseline,task)),pred!=decision(baseline,task)


def search(event,baseline,attack,adapter,prepared,seed):
    if adapter.spec.preprocessing.get('kind')=='image' and attack.algorithm in {'fgsm','pgd'}:
        from .image_attacks import search_image
        return search_image(event,baseline,attack,adapter,prepared,seed)
    task=prepared.spec.task;rng=np.random.Generator(np.random.PCG64(seed))
    if attack.objective in {'misclassification','loss_increase'} and not event['truth']['valid']:
        return copy.deepcopy(event),{'eligible':False,'reason':'authoritative_outcome_unavailable','queries':0,'success':None}
    if attack.objective=='misclassification' and (not event.get('baseline_truth',event['truth'])['valid'] or decision(baseline,task)!=event.get('baseline_truth',event['truth'])['value']):
        return copy.deepcopy(event),{'eligible':False,'reason':'baseline_not_correct','queries':0,'success':None}
    if attack.objective=='targeted' and decision(baseline,task)==attack.target_class:
        return copy.deepcopy(event),{'eligible':False,'reason':'baseline_already_target','queries':0,'success':None}
    if attack.queries_per_root<2:raise EvaluationError('Attack budget must reserve final end-to-end verification.','attack_budget')
    best=copy.deepcopy(event);best_score,_=objective(baseline,baseline,event,attack,task)
    if best_score is None:best_score=-float('inf')
    original_score=best_score;random_baseline=None;last_evaluation=None
    queries=0;invalid=0;attempted=0;success=False;coverage='bounded';history=[];gradient_steps=0
    def evaluate(candidate):
        nonlocal queries,invalid,attempted,best,best_score,success,last_evaluation
        if queries>=attack.queries_per_root-1 or attempted>=attack.queries_per_root-1:return False
        attempted+=1
        valid,_,_=feasible(event['record'],candidate['record'],attack.constraints,attack.relations)
        if valid and attack.norm in {'linf','l2'}:
            try:
                difference=np.concatenate([(np.asarray(candidate['record'][f],float)-np.asarray(event['record'][f],float)).reshape(-1) for f in attack.fields])
                valid=np.max(np.abs(difference))<=attack.epsilon+1e-12 if attack.norm=='linf' else np.linalg.norm(difference)<=attack.epsilon+1e-12
            except (ValueError,TypeError):valid=False
        if not valid:invalid+=1;last_evaluation={'state':'infeasible'};return True
        queries+=1
        prepared.attack_queries=getattr(prepared,'attack_queries',0)+1
        if prepared.attack_queries>prepared.spec.limits.max_queries:raise EvaluationError('Global attack query admission exceeded.','attack_budget')
        out=predict_batch(adapter,[candidate],prepared)[0];value,won=objective(out,baseline,event,attack,task)
        last_evaluation={'state':'evaluated','objective':value,'success':bool(won)}
        if value is not None and value>best_score:best=copy.deepcopy(candidate);best_score=value;success=bool(won)
        if len(history)<32:history.append({'queries':queries,'best_objective':best_score if np.isfinite(best_score) else None})
        return True
    if attack.algorithm in {'fgsm','pgd'}:
        tensor_domain=adapter.spec.preprocessing.get('kind')=='tensor'
        if adapter.spec.adapter!='torch' or adapter.spec.preprocessing.get('kind','numeric') not in {'numeric','tabular','tensor'}:
            raise EvaluationError('This gradient attack requires a verified continuous numeric Torch path.','gradient_unavailable')
        if tensor_domain and (attack.stage!='tensor' or len(attack.fields)!=1 or attack.fields[0]!=adapter.spec.inputs[0].column):raise EvaluationError('Prepared-vector attacks require an explicitly declared tensor domain.','gradient_unavailable')
        if not tensor_domain and attack.stage!='raw':raise EvaluationError('Numeric gradients require the declared raw numeric input stage.','gradient_unavailable')
        if any(f.kind in {'categorical','integer','boolean','text','asset'} for f in adapter.spec.inputs if f.column in attack.fields) or adapter.spec.preprocessing.get('categories'):
            raise EvaluationError('Discrete preprocessing cannot inherit a continuous attack.','gradient_unavailable')
        tensor_shape=np.asarray(event['record'][attack.fields[0]]).shape if tensor_domain else None
        original=np.asarray(event['record'][attack.fields[0]],float).reshape(-1) if tensor_domain else np.asarray([float(event['record'][f]) for f in attack.fields],float)
        def assign(candidate,values):
            if tensor_domain:candidate['record'][attack.fields[0]]=values.reshape(tensor_shape).tolist()
            else:
                for f,v in zip(attack.fields,values):candidate['record'][f]=float(v)
        # One seeded random-input control shares the exact feasibility, query
        # and replay accounting of the attack. It is never free hidden work.
        random_delta=rng.uniform(-attack.epsilon,attack.epsilon,len(original))
        if attack.norm=='l2':random_delta*=min(1,attack.epsilon/max(np.linalg.norm(random_delta),1e-30))
        random_candidate=copy.deepcopy(event);assign(random_candidate,original+random_delta)
        if evaluate(random_candidate):random_baseline=last_evaluation
        for restart in range(1 if attack.algorithm=='fgsm' else attack.restarts):
            x=original.copy()
            if restart:x+=rng.uniform(-attack.epsilon,attack.epsilon,len(x))
            for step in range(1 if attack.algorithm=='fgsm' else attack.steps):
                if queries>=attack.queries_per_root-1:break
                candidate=copy.deepcopy(event)
                assign(candidate,x)
                prepared_input=adapter.prepare([{**candidate['record'],'_cg6_event_key':candidate['event_key']}]);raw,tensor=adapter.predict_raw(prepared_input,gradients=True)
                gradient_steps+=1
                prepared.attack_queries=getattr(prepared,'attack_queries',0)+1
                if prepared.attack_queries>prepared.spec.limits.max_queries:raise EvaluationError('Global gradient work admission exceeded.','attack_budget')
                from .gradient_objectives import attack_objective,input_gradient
                objective_tensor=attack_objective(raw,adapter.spec,attack,event,baseline,prepared.config.probability_tolerance)
                gradient=input_gradient(objective_tensor,tensor)
                # Numeric preprocessing is an affine map; chain rule returns raw units.
                scale=np.asarray(adapter.spec.preprocessing.get('scale',np.ones(len(adapter.spec.inputs))))
                indices=[next(i for i,f in enumerate(adapter.spec.inputs) if f.column==field) for field in attack.fields]
                g=gradient.reshape(-1) if tensor_domain else (gradient/scale)[indices]
                if not np.isfinite(g).all():raise EvaluationError('Nonfinite attack gradient.','gradient_unavailable')
                direction=np.sign(g) if attack.norm=='linf' else g/max(np.linalg.norm(g),1e-30)
                x+= (attack.epsilon if attack.algorithm=='fgsm' else attack.step_size)*direction
                delta=x-original
                delta=np.clip(delta,-attack.epsilon,attack.epsilon) if attack.norm=='linf' else delta*min(1,attack.epsilon/max(np.linalg.norm(delta),1e-30))
                x=original+delta
                if tensor_domain:
                    c=attack.constraints.get(attack.fields[0],{});x=np.clip(x,c.get('lower',-np.inf),c.get('upper',np.inf))
                else:
                    for i,f in enumerate(attack.fields):
                        c=attack.constraints.get(f,{})
                        x[i]=min(c.get('upper',float('inf')),max(c.get('lower',-float('inf')),x[i]))
                assign(candidate,x)
                if not evaluate(candidate):break
    else:
        if attack.algorithm=='enumerate':
            domain=itertools.product(*(attack.domains[f] for f in attack.fields));size=math.prod(len(attack.domains[f]) for f in attack.fields)
        else:domain=range(attack.queries_per_root-1);size=None
        completed=0
        for item in domain:
            candidate=copy.deepcopy(best if attack.algorithm=='coordinate' else event)
            if attack.algorithm=='enumerate':
                for f,v in zip(attack.fields,item):candidate['record'][f]=v
            elif attack.algorithm=='text':
                f=attack.fields[int(rng.integers(len(attack.fields)))];text=str(candidate['record'].get(f,''))
                if text:
                    i=int(rng.integers(len(text)));candidate['record'][f]=text[:i]+text[i+1:]
            else:
                selected=[attack.fields[int(rng.integers(len(attack.fields)))]] if attack.algorithm=='coordinate' else attack.fields
                for f in selected:
                    if f in attack.domains:
                        choices=attack.domains[f];candidate['record'][f]=choices[int(rng.integers(len(choices)))]
                    else:candidate['record'][f]=float(event['record'][f])+float(rng.uniform(-attack.epsilon,attack.epsilon))
            if not evaluate(candidate):break
            completed+=1
        if attack.algorithm=='enumerate' and completed==size:coverage='complete_declared_finite_domain'
    final=predict_batch(adapter,[best],prepared)[0];queries+=1
    prepared.attack_queries=getattr(prepared,'attack_queries',0)+1
    if prepared.attack_queries>prepared.spec.limits.max_queries:raise EvaluationError('Global attack query admission exceeded.','attack_budget')
    value,success=objective(final,baseline,event,attack,task)
    return best,{'eligible':True,'queries':queries,'gradient_steps':gradient_steps,
                 'original_baseline_objective':original_score if np.isfinite(original_score) else None,'random_baseline':random_baseline,
                 'attempted_proposals':attempted,'infeasible_proposals':invalid,'success':bool(success),'best_objective':value,
                 'search_coverage':coverage,'termination':'finite_domain_exhausted' if coverage.startswith('complete') else 'bounded_search_completed',
                 'best_so_far':history,'threat_model':attack.to_dict(),'robustness_guarantee':False}
