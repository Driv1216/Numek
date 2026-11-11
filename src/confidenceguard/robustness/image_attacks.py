"""Pixel-domain PGD with exact decoded-candidate replay and bounded work."""
import copy
import hashlib
import io
import numpy as np

from ..contracts import EvaluationError
from ..execution.services import predict_batch
from .transformations import canonical_image


def search_image(event,baseline,attack,adapter,prepared,seed):
    from .attacks import objective,decision
    from PIL import Image
    if attack.stage!='canonical_image' or len(attack.fields)!=1 or attack.fields[0]!=adapter.spec.inputs[0].column:
        raise EvaluationError('Image gradients require the declared canonical RGB pixel domain.','gradient_unavailable')
    if attack.algorithm not in {'fgsm','pgd'} or attack.norm not in {'linf','l2'}:raise EvaluationError('Unsupported continuous image threat model.')
    if attack.constraints or attack.relations:raise EvaluationError('Image constraints use the declared [0,1] pixel box and radius; scalar field constraints do not describe pixels.')
    task=prepared.spec.task;field=attack.fields[0];image=canonical_image(event['record'][field],prepared,prepared.spec.limits)
    if 'image_size' in adapter.spec.preprocessing:image=image.resize(tuple(adapter.spec.preprocessing['image_size']))
    original=np.asarray(image,dtype=np.float32)/255.;rng=np.random.Generator(np.random.PCG64(seed))
    mean=np.asarray(adapter.spec.preprocessing.get('image_mean',[0.,0.,0.]),np.float32)
    scale=np.asarray(adapter.spec.preprocessing.get('image_scale',[1.,1.,1.]),np.float32)
    if scale.shape!=(3,) or np.any(scale<=0):raise EvaluationError('Image normalization must have three positive scale values.')
    queries=0;gradients=0;invalid=0;history=[];created=set();best=copy.deepcopy(event)
    best_score,_=objective(baseline,baseline,event,attack,task);best_score=-float('inf') if best_score is None else best_score
    def charge():
        nonlocal queries
        queries+=1;prepared.attack_queries=getattr(prepared,'attack_queries',0)+1
        if queries>attack.queries_per_root or prepared.attack_queries>prepared.spec.limits.max_queries:raise EvaluationError('Image attack query budget exceeded.','attack_budget')
        prepared.work.check('image attack work')
    def candidate_pixels(x):
        nonlocal invalid,best,best_score
        # Project onto the exact 8-bit lattice before distance admission. No
        # relaxed float candidate can be reported as an end-to-end image attack.
        pixels=np.rint(np.clip(x,0,1)*255).astype(np.uint8);actual=pixels.astype(np.float32)/255.;delta=actual-original
        distance=float(np.max(np.abs(delta))) if attack.norm=='linf' else float(np.linalg.norm(delta))
        if distance>attack.epsilon+1e-7:invalid+=1;return
        stream=io.BytesIO();Image.fromarray(pixels).save(stream,format='PNG');raw=stream.getvalue();sha=hashlib.sha256(raw).hexdigest()
        path=prepared.work.root/('attack-'+sha+'.png');value=str(path)
        if not path.exists():prepared.work.check('attack image reservation',len(raw));path.write_bytes(raw);created.add(value)
        prepared.assets[value]=value
        if not hasattr(prepared,'generated_assets'):prepared.generated_assets={}
        prepared.generated_assets[value]={'path':value,'sha256':sha,'bytes':len(raw)}
        candidate=copy.deepcopy(event);candidate['record'][field]=value
        charge();output=predict_batch(adapter,[candidate],prepared)[0];score,_=objective(output,baseline,event,attack,task)
        if score is not None and score>best_score:best=candidate;best_score=score
        if len(history)<32:history.append({'queries':queries,'best_objective':best_score,'distance':distance})
    if attack.objective in {'misclassification','loss_increase'} and not event['truth']['valid']:return best,{'eligible':False,'reason':'authoritative_outcome_unavailable','queries':0,'success':None}
    if attack.objective=='misclassification' and (not event.get('baseline_truth',event['truth'])['valid'] or decision(baseline,task)!=event.get('baseline_truth',event['truth'])['value']):return best,{'eligible':False,'reason':'baseline_not_correct','queries':0,'success':None}
    if attack.objective=='targeted' and decision(baseline,task)==attack.target_class:return best,{'eligible':False,'reason':'baseline_already_target','queries':0,'success':None}
    random_baseline=None
    if attack.queries_per_root>=4:
        candidate_pixels(np.clip(original+rng.uniform(-attack.epsilon,attack.epsilon,original.shape),0,1));random_baseline=best_score
    for restart in range(1 if attack.algorithm=='fgsm' else attack.restarts):
        x=original.copy()
        if restart:x=np.clip(x+rng.uniform(-attack.epsilon,attack.epsilon,x.shape),0,1)
        for step in range(1 if attack.algorithm=='fgsm' else attack.steps):
            if queries>=attack.queries_per_root-2:break
            normalized=((x-mean)/scale).transpose(2,0,1)[None].astype(np.float32)
            charge();raw,tensor=adapter.predict_raw(normalized,gradients=True);gradients+=1
            from .gradient_objectives import attack_objective,input_gradient
            obj=attack_objective(raw,adapter.spec,attack,event,baseline,prepared.config.probability_tolerance)
            gradient=input_gradient(obj,tensor).transpose(1,2,0)/scale
            if not np.isfinite(gradient).all():raise EvaluationError('Nonfinite image gradient.','gradient_unavailable')
            direction=np.sign(gradient) if attack.norm=='linf' else gradient/max(np.linalg.norm(gradient),1e-30)
            x=x+(attack.epsilon if attack.algorithm=='fgsm' else attack.step_size)*direction
            delta=x-original
            delta=np.clip(delta,-attack.epsilon,attack.epsilon) if attack.norm=='linf' else delta*min(1.,attack.epsilon/max(np.linalg.norm(delta),1e-30))
            x=np.clip(original+delta,0,1);candidate_pixels(x)
    charge();final=predict_batch(adapter,[best],prepared)[0];value,success=objective(final,baseline,event,attack,task)
    best_path=best['record'][field]
    for path in created-{best_path}:
        from pathlib import Path
        Path(path).unlink(missing_ok=True);prepared.assets.pop(path,None);prepared.generated_assets.pop(path,None)
    return best,{'eligible':True,'queries':queries,'gradient_steps':gradients,'infeasible_proposals':invalid,'success':bool(success),
        'best_objective':value,'best_so_far':history,'random_baseline_objective':random_baseline,'search_coverage':'bounded',
        'domain':'declared resized canonical RGB pixels in [0,1]; exact 8-bit replay','threat_model':attack.to_dict(),'robustness_guarantee':False}
