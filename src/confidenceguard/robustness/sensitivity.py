"""Bounded, named-output Torch gradients in declared input coordinates."""
import json
import numpy as np

from ..contracts import EvaluationError
from ..execution.contracts import shape,positive


def validate(raw,execution):
    shape(raw,{'gradients','max_roots'})
    maximum=raw.get('max_roots',100);positive(maximum,'gradient root budget')
    if maximum>execution.limits.max_queries:raise EvaluationError('Gradient work exceeds execution admission.')
    seen=set()
    for entry in raw.get('gradients',[]):
        shape(entry,{'id','predictor','channel','class','retain_raw'},{'id','predictor','channel'})
        if entry['predictor'] not in execution.predictor_ids or entry['channel'] not in {'point','logits','probabilities'}:raise EvaluationError('Invalid named gradient target.')
        if entry.get('class') is not None and entry['class'] not in execution.task.classes:raise EvaluationError('Gradient target class differs.')
        if type(entry.get('retain_raw',True)) is not bool:raise EvaluationError('Gradient retention requires a Boolean.')
        from ..contracts import name
        name(entry['id'])
        if entry['id'] in seen:raise EvaluationError('Gradient target identities must be unique.')
        seen.add(entry['id'])


def diagnose(prepared,adapters,study):
    import torch
    results=[]
    for descriptor in study.sensitivity.get('gradients',[]):
        adapter=adapters[descriptor['predictor']];p=adapter.spec;kind=p.preprocessing.get('kind','numeric')
        if p.adapter!='torch' or kind=='text' or p.preprocessing.get('categories') or any(f.kind in {'categorical','integer','boolean'} for f in p.inputs):
            results.append({'id':descriptor['id'],'state':'refused','reason':'complete_continuous_torch_path_required'});continue
        binding=next((b for b in p.outputs if b.channel==descriptor['channel']),None)
        if binding is None:results.append({'id':descriptor['id'],'state':'refused','reason':'named_output_unavailable'});continue
        count=0;skipped=0;norms=[]
        for event in prepared.events(study.role):
            if count+skipped>=study.sensitivity.get('max_roots',100):break
            if set(event.get('unavailable_fields',()))&{f.column for f in p.inputs}:skipped+=1;continue
            prepared_input=adapter.prepare([{**event['record'],'_cg6_event_key':event['event_key']}])
            prepared.attack_queries=getattr(prepared,'attack_queries',0)+1
            if prepared.attack_queries>prepared.spec.limits.max_queries:raise EvaluationError('Gradient work admission exceeded.','attack_budget')
            raw,tensor=adapter.predict_raw(prepared_input,gradients=True)
            if isinstance(raw,dict):raw=raw[binding.source]
            if raw.ndim==1:raw=raw[:,None]
            if binding.indices:raw=raw[:,list(binding.indices)]
            if binding.activation=='softmax':raw=torch.softmax(raw,dim=1)
            elif binding.activation=='sigmoid':raw=torch.sigmoid(raw)
            target=descriptor.get('class')
            index=binding.classes.index(target) if target is not None else 0
            if raw.shape[1]>1 and target is None:raise EvaluationError('Vector gradient outputs require an explicit class.','gradient_unavailable')
            gradient=torch.autograd.grad(raw[0,index],tensor)[0].detach().cpu().numpy()[0]
            basis='prepared_tensor'
            if kind in {'numeric','tabular'}:
                gradient=gradient/np.asarray(p.preprocessing.get('scale',np.ones(len(p.inputs))))
                basis='raw_numeric_features'
            elif kind=='image':
                gradient=gradient/np.asarray(p.preprocessing.get('image_scale',[1,1,1]))[:,None,None];basis='canonical_RGB_pixels_before_normalization'
            if not np.isfinite(gradient).all():raise EvaluationError('Nonfinite named-output gradient.','gradient_unavailable')
            if descriptor.get('retain_raw',True) and gradient.size>4096:raise EvaluationError('Large gradients require an explicit summary-only retention declaration.','gradient_retention')
            norm=float(np.linalg.norm(gradient));norms.append(norm);count+=1
            packet={'id':descriptor['id'],'basis':basis,'shape':list(gradient.shape),'norm_l2':norm,'mean_absolute':float(np.mean(np.abs(gradient))),
                'values':gradient.tolist() if descriptor.get('retain_raw',True) else None,'raw_retained':descriptor.get('retain_raw',True),'target':descriptor}
            prepared.cell_count+=gradient.size if descriptor.get('retain_raw',True) else 7
            if prepared.cell_count>min(prepared.spec.limits.max_output_cells,prepared.config.probability_cells):raise EvaluationError('Gradient evidence cell admission exceeded.','output_cell_limit')
            prepared.con.execute("UPDATE cg6_outputs SET payload=json_merge_patch(payload,json_object('gradient_diagnostics',CAST(? AS JSON))) WHERE view=? AND event_key=?",[json.dumps({descriptor['id']:packet}),p.id,event['event_key']])
            prepared.work.check('named-output gradient diagnostics')
        results.append({'id':descriptor['id'],'state':'completed','evaluated_roots':count,'unavailable_roots':skipped,'mean_norm_l2':float(np.mean(norms)) if norms else None,
            'scope':'first admitted canonical roots; local derivative of the named complete pipeline; no causal or global robustness claim'})
    return results
