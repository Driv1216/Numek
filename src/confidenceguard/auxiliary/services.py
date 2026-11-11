"""Fit, select, apply and independently assess executable auxiliary models."""
from dataclasses import replace
import copy
import hashlib
import json
from pathlib import Path
import time

import numpy as np

from ..contracts import EvaluationError,digest
from ..feature_contracts import FeatureField
from ..execution.contracts import ExecutionSpec,DeviceSpec,OutputBinding
from ..execution.adapters import Adapter,normalize_outputs
from ..execution.services import service,apply_events,make_result,measurement,predict_batch
from .contracts import AuxiliaryStudySpec,AuxiliaryArtifact
from .fitting import preprocessing,fit,loss


def target(study,event,output):
    truth=event['truth'];c=output['channels']
    if study.kind=='failure_risk' and study.failure=='execution_failure':return float(output['execution']!='completed')
    if not truth['valid']:return None
    y=truth['value']
    if study.kind=='quantiles':return y
    if study.kind=='scale':return abs(y-c['point']) if 'point' in c else None
    if study.execution.task.kind=='regression':
        return float(abs(y-c['point'])>study.material_error) if 'point' in c and study.material_error is not None else None
    pred=output.get('decision',c.get('prediction'))
    base=next(p for p in study.execution.predictors if p.id==study.base_predictor)
    if pred is None and base.decision.rule=='probability_argmax' and c.get('probabilities'):
        values=c['probabilities'];best=max(values);ids=[i for i,v in enumerate(values) if v==best]
        if len(ids)==1:pred=study.execution.task.classes[ids[0]]
    if pred is None:return None
    error=float(pred!=y)
    if study.failure=='high_confidence_error':return error*float(max(c.get('probabilities',[0]))>=study.high_confidence_threshold)
    return error


def augment(event,output,prediction_features,vector_field=None):
    event=copy.deepcopy(event);c=output['channels']
    for f in prediction_features:
        value=c.get(f)
        if f=='confidence':value=max(c['probabilities']) if c.get('probabilities') else None
        if f=='entropy':value=-sum(p*np.log(p) for p in c['probabilities'] if p>0) if c.get('probabilities') else None
        event['record']['_cg6_parent_'+f]=value
    if vector_field:
        values=np.asarray(event['record'][vector_field],float).reshape(-1)
        for i,v in enumerate(values):event['record']['_cg6_vector_'+str(i)]=float(v)
    return event


def membership(events,namespace):
    return [digest([namespace,e['event_key']]) for e in events],[digest([namespace,e['entity_key'] or e['event_key']]) for e in events]


def run_worker(prepared,operation,staging,registrations,options,started):
    if operation=='auxiliary_fit':return fit_worker(prepared,staging,registrations,options,started)
    return application_worker(prepared,staging,registrations,options,started,assess=operation=='auxiliary_assess')


def fit_worker(prepared,staging,registrations,options,started):
    study=AuxiliaryStudySpec.from_dict(options['study']);base=next(p for p in prepared.spec.predictors if p.id==study.base_predictor)
    prepared.validate_model_fields(study.inputs or base.inputs)
    adapter=Adapter(base,prepared.spec.device,prepared.config,prepared.spec.limits,prepared.work,prepared.roots,registrations);prepared.attach(adapter)
    frames={};targets={};excluded={};frame_bytes=0
    for role in ('F','S'):
        frame=[];ys=[];missing=0
        def sink(events,outputs):
            nonlocal missing,frame_bytes
            for e,o in zip(events,outputs):
                if {f.column for f in (study.inputs or base.inputs)}&set(e.get('unavailable_fields',())):missing+=1;continue
                y=target(study,e,o)
                if y is None:missing+=1;continue
                frame.append(augment(e,o,study.prediction_features));ys.append(y)
                frame_bytes+=len(json.dumps(frame[-1]))*4+128
                if frame_bytes>prepared.config.max_rss_bytes//3:raise EvaluationError('Auxiliary role-frame memory admission exceeded.','auxiliary_memory')
        apply_events(prepared,adapter,prepared.events(role),'fit_'+role,sink=sink)
        frames[role]=frame;targets[role]=np.asarray(ys,float);excluded[role]=missing
    if not frames['F'] or not frames['S']:raise EvaluationError('Eligible F and S support is required.','auxiliary_target_support')
    fields=study.inputs or base.inputs
    vector_field=None
    if not study.inputs and base.preprocessing.get('kind')=='tensor':
        vector_field=base.inputs[0].column;dimensions=np.asarray(frames['F'][0]['record'][vector_field]).size
        fields=tuple(FeatureField('vector_'+str(i),'_cg6_vector_'+str(i),'float',role='model_input') for i in range(dimensions))
        frames={role:[augment(e,{'channels':{}},(),vector_field) for e in values] for role,values in frames.items()}
    fields=(*fields,*(FeatureField('parent_'+f,'_cg6_parent_'+f,'float',role='prediction_derived') for f in study.prediction_features))
    pre=preprocessing(frames['F'],fields)
    pre.update(**({'scale_floor':study.scale_floor} if study.kind=='scale' else {}))
    candidates=[];fitted={}
    for candidate in study.candidates:
        prepared.work.check('auxiliary candidate fitting')
        try:
            models,objective,record=fit(candidate,study,fields,pre,frames['F'],frames['S'],targets['F'],targets['S'],base,prepared.config,prepared.spec.device,staging,prepared.work.check)
            fitted[candidate.id]=(models,record)
            candidates.append({'id':candidate.id,'family':candidate.family,'objective':objective,'state':'fitted','parameters':candidate.parameters,
                               'seed':candidate.seed,'ensemble_members':candidate.ensemble_members,
                               'training':record['training'],'nomination_support':record['nomination_support']})
        except EvaluationError as exc:
            if exc.code not in {'auxiliary_target_support','crossed_quantiles','auxiliary_selection_support'}:raise
            candidates.append({'id':candidate.id,'family':candidate.family,'objective':None,'state':'disqualified','reason':exc.code})
    eligible=[c for c in candidates if c['state']=='fitted' and np.isfinite(c['objective'])]
    if not eligible:raise EvaluationError('No auxiliary candidate has a defined frozen-S objective.','auxiliary_selection_failed')
    winner=min(eligible,key=lambda c:(c['objective'],len(fitted[c['id']][0]),[x.id for x in study.candidates].index(c['id'])))
    models,record=fitted[winner['id']]
    fe,fu=membership(frames['F'],prepared.spec.namespace);se,su=membership(frames['S'],prepared.spec.namespace)
    member={'namespace':prepared.spec.namespace,'F_events':fe,'S_events':se,'F_units':fu,'S_units':su,
            'fit_data_digest':digest([[e['event_key'],e['record'],float(y)] for e,y in zip(frames['F'],targets['F'])]),
            'selection_data_digest':digest([[e['event_key'],e['record'],float(y)] for e,y in zip(frames['S'],targets['S'])]),
            'upstream_provenance':base.provenance}
    from ..execution.devices import capabilities
    runtime=capabilities()
    fitting_identity={'python':runtime['python'],'platform':runtime['platform'],'packages':runtime['versions'],
        'source_sha256':{path.name:hashlib.sha256(path.read_bytes()).hexdigest() for path in (Path(__file__),Path(__file__).with_name('fitting.py'),Path(__file__).with_name('contracts.py'))}}
    artifact=AuxiliaryArtifact.create(id=winner['id'],kind=study.kind,predictors=tuple(models),parent_digest=base.predictor_digest,
        target={'kind':study.kind,'failure':study.failure,'material_error':study.material_error,'high_confidence_threshold':study.high_confidence_threshold,'levels':list(study.levels),'scale_floor':study.scale_floor,
                'prediction_features':list(study.prediction_features),'vector_field':vector_field,'quantile_rearrange':study.quantile_rearrange,'base_predictor':base.id,'members':record['members']},
        membership=member,selection={'candidate':winner['id'],'objective':'pinball' if study.kind=='quantiles' else 'brier' if study.kind=='failure_risk' else 'squared_residual_scale',
            'S_objective':winner['objective'],'s_tuning_fraction':study.s_tuning_fraction,'refit_F_plus_S':False,'fitting_runtime':fitting_identity,'selected_training':record['training'],
            'candidate_family':[{k:v for k,v in c.items() if k!='training'} for c in candidates]})
    result=make_result(prepared,'auxiliary_fit',{'candidates':candidates,'nomination':winner['id'],'artifact_digest':artifact.artifact_digest,
        'separation':{'F':len(frames['F']),'S':len(frames['S']),'C_accessed':False,'E_accessed':False,'excluded_targets':excluded},
        'scientific_qualification':'fit_and_selection_only; independent assessment is separate'},started=started,staging=staging,
        private_extra={'auxiliary_artifacts':[artifact.to_dict()],'auxiliary_study':study.to_dict()})
    result.data['cg6']['devices']={base.id:adapter.finish()}
    prepared.verify();return result


def apply_artifact(prepared,artifact,events,parent,registrations):
    """Yield aligned events and aggregate auxiliary outputs, with no fitting."""
    adapters=[]
    for p in artifact.predictors:
        device=prepared.spec.device if p.adapter in {'torch','custom'} else DeviceSpec()
        a=Adapter(p,device,prepared.config,prepared.spec.limits,prepared.work,prepared.roots,registrations);prepared.attach(a);adapters.append(a)
    batch=[]
    def invoke(batch):
        primary=predict_batch(parent,batch,prepared)
        enriched=[augment(e,o,artifact.target.get('prediction_features',()),artifact.target.get('vector_field')) for e,o in zip(batch,primary)]
        parts=[predict_batch(a,enriched,prepared) for a in adapters]
        for i,e in enumerate(enriched):
            member_outputs=[];reason=None;repairs=[]
            for member in artifact.target['members']:
                selected=[parts[j][i] for j in range(member['start'],member['start']+member['count'])]
                if any(o['execution']!='completed' or o['channel_failures'] for o in selected):reason='auxiliary_output_unavailable';break
                if artifact.kind=='quantiles':
                    values=selected[0]['channels'].get('quantiles') if len(selected)==1 else [o['channels']['point'] for o in selected]
                    if artifact.target.get('quantile_rearrange'):
                        if any(x>y for x,y in zip(values,values[1:])):repairs.append({'operation':'declared_quantile_rearrangement','original':values})
                        values=sorted(values)
                    if any(x>y for x,y in zip(values,values[1:])):reason='crossed_quantiles';break
                else:values=selected[0]['channels']['scale' if artifact.kind=='scale' else 'score']
                member_outputs.append(values)
            if reason:out={'channels':{},'channel_failures':{artifact.kind:reason},'execution':'completed'}
            else:
                values=np.asarray(member_outputs,float);average=np.mean(values,axis=0)
                channel={'scale':'scale','quantiles':'quantiles','failure_risk':'risk'}[artifact.kind]
                out={'channels':{channel:average.tolist() if average.ndim else float(average)},'channel_failures':{},'execution':'completed',
                     'ensemble':{'members':len(member_outputs),'variance':np.var(values,axis=0).tolist(),'interpretation':'predictive variability; not a calibrated uncertainty distribution'}}
                out['postprocessing']=repairs+[item for part in parts for item in part[i].get('postprocessing',[])]
            yield e,out,primary[i]
    coupled=parent.spec.adapter=='custom' and not parent.realization['host_registration']['batch_independent']
    if coupled:
        def key(e):return tuple(e['record'].get(c) for c in prepared.spec.batch_columns) if prepared.spec.batch_columns else ('application',)
        counts={};roles={};groups={};used=0
        for e in prepared.events():
            k=key(e);counts[k]=counts.get(k,0)+1;roles.setdefault(k,set()).add(e['role'])
        for e in events:
            k=key(e);groups.setdefault(k,[]).append(e);used+=len(json.dumps(e))+256
            if used>prepared.config.max_rss_bytes//3 or len(groups[k])>prepared.spec.limits.batch_rows:raise EvaluationError('Complete auxiliary parent batches exceed admission.','execution_batch')
        for k,batch in groups.items():
            if len(batch)!=counts[k] or len(roles[k])>1:raise EvaluationError('Auxiliary application requires complete role-separated parent batches.','execution_batch_incomplete')
            from ..execution.batch_admission import tensor_bytes
            if max(sum(tensor_bytes(a,e,prepared) for e in batch) for a in [parent,*adapters])>prepared.spec.limits.batch_tensor_bytes:raise EvaluationError('Complete auxiliary batch exceeds tensor admission.','batch_tensor_limit')
            yield from invoke(batch)
    else:
        for e in events:
            batch.append(e)
            if len(batch)>=prepared.spec.limits.batch_rows:
                yield from invoke(batch);batch=[]
        if batch:yield from invoke(batch)
    prepared.auxiliary_realizations={a.spec.id:a.finish() for a in adapters}


def application_worker(prepared,staging,registrations,options,started,assess=False):
    artifact=AuxiliaryArtifact.from_dict(options['artifact']);role=options.get('role','E' if assess else None)
    base=next((p for p in prepared.spec.predictors if p.predictor_digest==artifact.parent_digest),None)
    if base is None:raise EvaluationError('Auxiliary parent model differs.','auxiliary_parent')
    parent=Adapter(base,prepared.spec.device,prepared.config,prepared.spec.limits,prepared.work,prepared.roots,registrations);prepared.attach(parent)
    # One complete, immutable application view carries the frozen primary
    # prediction and the fitted auxiliary representation into unchanged CG2.
    channel={'scale':'scale','quantiles':'quantiles','failure_risk':'risk'}[artifact.kind]
    binding=OutputBinding(channel,levels=tuple(artifact.target['levels']) if channel=='quantiles' else (),direction='lower',meaning='selection')
    outputs=tuple(o for o in base.outputs if o.channel!=channel)+(binding,)
    p=replace(base,id=artifact.id,outputs=outputs,execution_view_only=True,provenance={**base.provenance,'auxiliary_artifact':artifact.artifact_digest,'primary_predictor':base.predictor_digest})
    view=prepared.start_view(p,'auxiliary_application')
    observations=[];overlap=False;namespace_match=artifact.membership.get('namespace')==prepared.spec.namespace
    used=set(artifact.membership.get('F_events',()))|set(artifact.membership.get('S_events',()))
    units=set(artifact.membership.get('F_units',()))|set(artifact.membership.get('S_units',()))
    target_spec=AuxiliaryStudySpec(execution=prepared.spec,kind=artifact.kind,base_predictor=base.id,
        failure=artifact.target['failure'],material_error=artifact.target.get('material_error'),high_confidence_threshold=artifact.target.get('high_confidence_threshold',.9),levels=tuple(artifact.target['levels']))
    for e,o,primary in apply_artifact(prepared,artifact,prepared.events(role),parent,registrations):
        combined={**o,'channels':{**primary['channels'],**o['channels']},'channel_failures':{**primary['channel_failures'],**o['channel_failures']},
                  'issuance':primary.get('issuance'),'decision':primary.get('decision'),'original_outputs':primary.get('original_outputs',{})}
        if primary['execution']!='completed':combined['execution']=primary['execution']
        prepared.append(view,[e],[combined])
        overlap |= digest([prepared.spec.namespace,e['event_key']]) in used or digest([prepared.spec.namespace,e['entity_key'] or e['event_key']]) in units
        y=target(target_spec,e,primary)
        c=o['channels'];channel={'scale':'scale','quantiles':'quantiles','failure_risk':'risk'}[artifact.kind]
        if y is not None and channel in c:observations.append((e,y,c[channel]))
    prepared.finish_view(view)
    from ..execution.provenance import assessment_reasons
    upstream_reasons=assessment_reasons(prepared)
    contradicted=overlap or base.id in upstream_reasons
    result=make_result(prepared,'auxiliary_assessment' if assess else 'auxiliary_application',
        {'artifact_digest':artifact.artifact_digest,'application_state':'applied_unvalidated','membership_check':'contradicted' if overlap else 'passed' if namespace_match else 'unavailable',
         'planned_role':role,'independent_assessment':'not_requested' if not assess else 'refused' if contradicted or not namespace_match else 'observed_nonoverlap_only'},
        started=started,staging=staging,private_extra={'auxiliary_artifacts':[artifact.to_dict()],'applied_predictor':p.to_dict()})
    if observations:
        ys=np.asarray([o[1] for o in observations]);pred=np.asarray([o[2] for o in observations]);n=len(ys)
        objective=loss(artifact.kind,pred,ys,artifact.target['levels'])
        measurement(result,view['id'],'pinball_loss' if artifact.kind=='quantiles' else 'brier' if artifact.kind=='failure_risk' else 'scale_squared_error',objective,n,family='auxiliary_diagnostics')
        if artifact.kind=='quantiles':
            for j,q in enumerate(artifact.target['levels']):measurement(result,view['id'],'quantile_calibration',float(np.mean(ys<=pred[:,j])),n,family='auxiliary_diagnostics',data={'level':q,'inclusive':True})
        if artifact.kind=='failure_risk':
            measurement(result,view['id'],'failure_prevalence',float(np.mean(ys)),n,family='auxiliary_diagnostics')
            with np.errstate(divide='ignore'):
                logs=-np.log(np.where(ys==1,pred,1-pred))
            measurement(result,view['id'],'failure_log_loss',float(np.mean(logs)),n,family='auxiliary_diagnostics',data={'zero_probability_is_infinite_loss':True})
            bins=[]
            for lo in np.linspace(0,.9,10):
                mask=(pred>=lo)&(pred<lo+.1 if lo<.9 else pred<=1)
                bins.append({'lower':float(lo),'support':int(mask.sum()),'predicted':float(pred[mask].mean()) if mask.any() else None,'observed':float(ys[mask].mean()) if mask.any() else None})
            result.data['cg6']['calibration_bins']=bins
            from .diagnostics import risk_diagnostics
            ranking=risk_diagnostics(ys,pred)
            result.data['cg6']['risk_diagnostics']=ranking
            for metric in ('auroc','average_precision'):
                if ranking[metric] is not None:measurement(result,view['id'],'failure_'+metric,ranking[metric],n,family='auxiliary_diagnostics',data={'prevalence':ranking['prevalence'],'tie_policy':ranking['tie_policy']})
    result.data['cg6']['assessment_qualifications']={'upstream_independence':options.get('upstream_independence','unknown'),
        'observable_upstream_contradictions':upstream_reasons,
        'membership_checks_establish_only_supplied_nonoverlap':True,'no_future_coverage_guarantee':True}
    result.data['cg6']['devices']={base.id:parent.finish(),**getattr(prepared,'auxiliary_realizations',{})}
    prepared.verify();return result


def fit_auxiliary(spec,config=None,**kwargs):
    study=AuxiliaryStudySpec.from_dict(spec) if isinstance(spec,dict) else spec
    fields={f.id:f for f in (*study.execution.context_fields,*study.inputs)}
    execution=replace(study.execution,context_fields=tuple(fields.values()))
    return service(execution,config,operation='auxiliary_fit',options={'study':study.to_dict()},**kwargs)


def apply_auxiliary(spec,artifact,config=None,*,role=None,**kwargs):
    if isinstance(artifact,AuxiliaryArtifact):artifact=artifact.to_dict()
    return service(spec,config,operation='auxiliary_apply',options={'artifact':artifact,'role':role},**kwargs)


def assess_auxiliary(spec,artifact,config=None,*,upstream_independence='unknown',**kwargs):
    if isinstance(artifact,AuxiliaryArtifact):artifact=artifact.to_dict()
    return service(spec,config,operation='auxiliary_assess',options={'artifact':artifact,'role':'E','upstream_independence':upstream_independence},**kwargs)
