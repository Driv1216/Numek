"""Fixed learners receive only admitted F/S arrays; no store or E accessor."""
from dataclasses import replace
import copy
import hashlib
from pathlib import Path

import numpy as np

from ..contracts import EvaluationError,digest,DecisionSpec
from ..execution.contracts import PredictorSpec,OutputBinding,ArtifactFile
from ..execution.adapters import Adapter,torch_architecture
from ..execution import devices


def preprocessing(events,fields):
    categories={};fill=[];mean=[];scale=[]
    for f in fields:
        values=[e['record'].get(f.column) for e in events]
        if f.kind in {'categorical','boolean','text'}:
            vocab=sorted({str(v) for v in values if v is not None and v not in f.missing_values})
            if len(vocab)>256:raise EvaluationError('Auxiliary category vocabulary exceeds its fixed profile.','auxiliary_features')
            categories[f.id]=vocab;fill.extend([0.]*(len(vocab)+1));mean.extend([0.]*(len(vocab)+1));scale.extend([1.]*(len(vocab)+1))
        else:
            clean=[]
            for v in values:
                if v is None or v in f.missing_values:continue
                try:x=float(v)
                except (TypeError,ValueError):continue
                if np.isfinite(x):clean.append(x)
            if not clean:raise EvaluationError('Auxiliary numerical feature has no finite fit values.','auxiliary_features')
            median=float(np.median(clean));fill.append(median);mean.append(float(np.mean(clean)));scale.append(max(float(np.std(clean)),1e-12))
    return {'kind':'numeric','dtype':'float32','categories':categories,'fill':fill,'mean':mean,'scale':scale}


def matrix(events,predictor):
    # Reuse the exact inference transform rather than a fitting-only encoding.
    stub=object.__new__(Adapter);stub.spec=predictor;stub.device_spec=type('Precision',(),{'precision':'float32'})()
    return stub.numeric([e['record'] for e in events])


def loss(kind,pred,target,levels):
    pred=np.asarray(pred,float);target=np.asarray(target,float)
    if kind=='quantiles':
        r=target.reshape(-1,1)-pred
        return float(np.mean(np.maximum(np.asarray(levels)*r,(np.asarray(levels)-1)*r)))
    pred=pred.reshape(-1)
    if kind=='failure_risk':return float(np.mean((pred-target)**2))
    return float(np.mean((pred-target)**2))


def fit(candidate,study,fields,pre,F,S,yF,yS,base,config,device,staging,check):
    """Return immutable model specs and S objective; E is absent by construction."""
    kind=study.kind;p=candidate.parameters;levels=study.levels
    models=[];members=[];history=[]
    if candidate.family=='logistic' and kind!='failure_risk':raise EvaluationError('Logistic fitting is restricted to binary failure risk.')
    for member in range(candidate.ensemble_members):
        seed=candidate.seed+member
        artifact_path=Path(staging)/(candidate.id+'-'+str(member)+('.safetensors' if candidate.family=='mlp' else '.skops'))
        head='positive' if kind=='scale' else 'quantiles' if kind=='quantiles' else 'sigmoid'
        channel='scale' if kind=='scale' else 'quantiles' if kind=='quantiles' else 'score'
        source='output';indices=()
        architecture={'kind':'mlp','input_dim':len(pre['fill']),'hidden':p.get('hidden',[128,128]),'output_dim':len(levels) if kind=='quantiles' else 1,'head':head}
        from ..contracts import TaskDefinition
        output_task=TaskDefinition('binary_classification','Declared primary prediction failure',classes=('0','1'),positive_class='1') if kind=='failure_risk' else base.task
        template=PredictorSpec(candidate.id+'_'+str(member),output_task,'constant',fields,
            (OutputBinding(channel,levels=levels if kind=='quantiles' else (),direction='lower',meaning='selection'),),
            preprocessing={**pre,**({'scale_floor':study.scale_floor} if kind=='scale' else {})},architecture={'values':{'output':0.}})
        xF=matrix(F,template);xS=matrix(S,template)
        if (xF.nbytes+xS.nbytes)*4>config.max_rss_bytes//2:raise EvaluationError('Auxiliary arrays exceed memory admission.','auxiliary_memory')
        if candidate.family=='constant':
            constant=np.quantile(yF,levels).tolist() if kind=='quantiles' else max(float(np.mean(yF)),study.scale_floor) if kind=='scale' else float(np.mean(yF))
            model=replace(template,architecture={'values':{'output':constant}})
            prediction=np.tile(constant,(len(S),1)) if kind=='quantiles' else np.full(len(S),constant)
        elif candidate.family in {'histogram','logistic'}:
            from sklearn.ensemble import HistGradientBoostingRegressor,HistGradientBoostingClassifier
            from sklearn.linear_model import LogisticRegression
            import skops.io as sio
            from threadpoolctl import threadpool_limits
            params={'max_iter':p.get('iterations',200),'learning_rate':p.get('learning_rate',.1),
                    'max_leaf_nodes':p.get('max_leaf_nodes',31),'min_samples_leaf':p.get('min_samples_leaf',20),'early_stopping':False,'random_state':seed}
            with threadpool_limits(limits=config.threads):
                if kind=='quantiles':
                    # Each quantile is an independently serialized admitted model.
                    fitted=[HistGradientBoostingRegressor(loss='quantile',quantile=q,**params).fit(xF,yF) for q in levels]
                    prediction=np.column_stack([m.predict(xS) for m in fitted])
                    crossing_count=int(np.any(np.diff(prediction,axis=1)<0,axis=1).sum())
                    # The bundle's explicit ordered rearrangement is fixed before C.
                    if study.quantile_rearrange:prediction=np.sort(prediction,axis=1)
                elif kind=='failure_risk':
                    if len(np.unique(yF))<2:raise EvaluationError('Failure-risk fit needs both outcomes.','auxiliary_target_support')
                    fitted=[(LogisticRegression(C=p.get('C',1.),random_state=seed,max_iter=p.get('iterations',200)) if candidate.family=='logistic' else HistGradientBoostingClassifier(**params)).fit(xF,yF)]
                    prediction=fitted[0].predict_proba(xS)[:,list(fitted[0].classes_).index(1.)]
                else:
                    fitted=[HistGradientBoostingRegressor(loss='squared_error',**params).fit(xF,yF)]
                    prediction=np.maximum(fitted[0].predict(xS),study.scale_floor)
            for j,learner in enumerate(fitted):
                path=artifact_path.with_name(artifact_path.stem+'-'+str(j)+'.skops');sio.dump(learner,path);path.chmod(0o600)
                binding=OutputBinding('score' if kind=='failure_risk' else 'scale' if kind=='scale' else 'point',
                                      source='predict_proba' if kind=='failure_risk' else 'predict',indices=(1,) if kind=='failure_risk' else (),direction='lower',meaning='selection')
                part=replace(template,id=template.id+'q'+str(j),adapter='sklearn',files=(ArtifactFile(path.name,str(path),hashlib.sha256(path.read_bytes()).hexdigest()),),entry=path.name,outputs=(binding,))
                if kind=='quantiles':part=replace(part,provenance={'quantile_level':levels[j]})
                models.append(part)
            members.append({'start':len(models)-len(fitted),'count':len(fitted)})
            history.append({'device':'cpu','family':candidate.family,'iterations':p.get('iterations',200),
                **({'crossed_S_outputs_before_rearrangement':crossing_count,'rearrangement_frozen_before_C':study.quantile_rearrange} if kind=='quantiles' else {})})
        else:
            import torch
            from safetensors.torch import save_file
            realization=devices.resolve(device,'torch');dtype=devices.configure_torch(device,config,realization)
            torch.manual_seed(seed)
            model_spec=replace(template,architecture=architecture)
            learner=torch_architecture(model_spec,{},allocation_bytes=min(config.max_rss_bytes//8,device.memory_bytes//4))
            learner.to(device=realization['torch_device'],dtype=dtype)
            optimizer=torch.optim.AdamW(learner.parameters(),lr=p.get('learning_rate',1e-3),weight_decay=p.get('weight_decay',1e-4))
            rng=np.random.Generator(np.random.PCG64(seed));best=None;best_loss=float('inf');wait=0;epochs=0
            batch=p.get('batch_rows',1024);maximum=p.get('epochs',200);patience=p.get('patience',15)
            if batch>study.execution.limits.batch_rows or batch*xF.shape[1]*np.dtype(device.precision).itemsize>study.execution.limits.batch_tensor_bytes:raise EvaluationError('Declared training batch exceeds admission; choose an explicit smaller training batch.','auxiliary_batch_admission')
            if len(S)*max(1,len(levels) if kind=='quantiles' else 1)*candidate.ensemble_members*8>config.max_rss_bytes//4:raise EvaluationError('Auxiliary selection outputs exceed memory admission.','auxiliary_memory')
            if maximum>10000:raise EvaluationError('Epoch admission exceeded.','auxiliary_fit_limit')
            # S tuning and nomination use separate stable unit partitions.
            tuning=np.asarray([int(hashlib.sha256(str(e['entity_key'] or e['event_key']).encode()).hexdigest(),16)/2**256<study.s_tuning_fraction for e in S])
            if not tuning.any() or tuning.all():raise EvaluationError('Both S tuning and nomination need support.','auxiliary_selection_support')
            tensor=lambda a:torch.as_tensor(a,device=realization['torch_device'],dtype=dtype)
            def infer(array):
                parts=[]
                with torch.inference_mode():
                    for start in range(0,len(array),batch):
                        parts.append(learner(tensor(array[start:start+batch])).cpu().numpy());devices.check_memory(realization,device);check('auxiliary selection inference')
                result=np.concatenate(parts)
                return np.maximum(result,study.scale_floor) if kind=='scale' else result
            for epoch in range(maximum):
                learner.train()
                permutation=rng.permutation(len(xF))
                for start in range(0,len(xF),batch):
                    check('auxiliary Torch fitting');idx=permutation[start:start+batch];x=tensor(xF[idx]);target=tensor(yF[idx])
                    optimizer.zero_grad(set_to_none=True);v=learner(x)
                    if kind=='quantiles':
                        residual=target[:,None]-v;qs=tensor(np.asarray(levels));objective=torch.maximum(qs*residual,(qs-1)*residual).mean()
                    else:objective=((v.reshape(-1)-target)**2).mean()
                    if not torch.isfinite(objective):raise EvaluationError('Auxiliary objective became nonfinite.','auxiliary_fit_failed')
                    objective.backward();optimizer.step();devices.check_memory(realization,device)
                learner.eval()
                pred=infer(xS[tuning])
                score=loss(kind,pred,yS[tuning],levels);epochs=epoch+1
                if score<best_loss:
                    best_loss=score;best={k:v.detach().cpu().clone() for k,v in learner.state_dict().items()};wait=0
                else:wait+=1
                if wait>=patience:break
            learner.load_state_dict(best);learner.eval()
            prediction=infer(xS)
            save_file(best,str(artifact_path))
            artifact_path.chmod(0o600)
            model=replace(model_spec,adapter='torch',files=(ArtifactFile(artifact_path.name,str(artifact_path),hashlib.sha256(artifact_path.read_bytes()).hexdigest()),),entry=artifact_path.name)
            devices.synchronize(realization['kind'])
            history.append({'device':realization['kind'],'epochs':epochs,'best_tuning_loss':best_loss,'allocator':devices.memory(realization)})
        if candidate.family not in {'histogram','logistic'}:
            models.append(model);members.append({'start':len(models)-1,'count':1})
        # Keep every member's S prediction for the finite ensemble objective.
        if kind!='quantiles':prediction=np.asarray(prediction).reshape(-1)
        # Local accumulator deliberately excludes any E inputs.
        if member==0:predictions=[]
        predictions.append(prediction)
    prediction=np.mean(predictions,axis=0)
    if kind=='quantiles' and np.any(np.diff(prediction,axis=1)<0):raise EvaluationError('Candidate crossed quantiles on frozen S.','crossed_quantiles')
    tuning=np.asarray([int(hashlib.sha256(str(e['entity_key'] or e['event_key']).encode()).hexdigest(),16)/2**256<study.s_tuning_fraction for e in S])
    if not (~tuning).any():raise EvaluationError('S nomination has no support.','auxiliary_selection_support')
    objective=loss(kind,prediction[~tuning],np.asarray(yS)[~tuning],levels)
    return models,objective,{'members':members,'training':history,'nomination_support':int((~tuning).sum()),'s_predictions':prediction.tolist()}
