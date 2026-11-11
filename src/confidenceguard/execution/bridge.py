"""Completed prediction export into unchanged CG1/CG2 public contracts."""
from dataclasses import replace
import csv
import hashlib
import json
import os
from pathlib import Path
import uuid

from .. import compat
from ..contracts import EvaluationSpec,PredictionRunSpec,SourceSpec,OutcomeSnapshotSpec,EvaluationError,digest
from ..method_contracts import ReliabilitySpec,RoleSpec,RepresentationSpec


def as_evaluation_spec(result,*,predictors=None,scope='original',directory=None):
    """Serialize completed evidence only; never execute or normalize a model."""
    if result.private['execution_spec'].get('evidence_retention','materialized_inputs')!='materialized_inputs':raise EvaluationError('This result retained outputs and recipes; exact input bridging is unavailable.','execution_input_not_retained')
    artifact=__import__('copy').deepcopy(result.private.get('output_artifact'))
    if not artifact:raise EvaluationError('Completed predictions are unavailable.','execution_output_unavailable')
    artifact['path']=result.retained_path(artifact['path'])
    from .artifact_bytes import verify_artifact
    verify_artifact(artifact,(str(Path(artifact['path']).parent),))
    views=[v for v in result.private['view_specs'] if v['scope']==scope and (predictors is None or v['predictor'] in predictors)]
    if not 1<=len(views)<=2:raise EvaluationError('Choose one or two completed views for a CG1/CG2 bridge.')
    root=compat.protected_directory(directory or Path(artifact['path']).parent/('evaluation-'+uuid.uuid4().hex))
    base=result.private['execution_spec'];runs=[];sources=[]
    memberships=[]
    for a in result.private.get('auxiliary_artifacts',[]):
        m=a['membership'];memberships.append((set(m.get('F_events',[])+m.get('S_events',[])),set(m.get('F_units',[])+m.get('S_units',[]))))
    for i,view in enumerate(views):
        original=PredictionRunSpec.from_dict(view['run']);sid='cg6_generated_'+str(i+1)
        path=root/(sid+'.csv');compat.destination(path)
        model_fields=[f for p in base['predictors'] for f in p['inputs']]
        model_fields.extend(f for a in base.get('auxiliaries',[]) for p in a['predictors'] for f in p['inputs']
                            if not f['column'].startswith(('_cg6_parent_','_cg6_vector_')))
        input_fields={f['column'] for f in (*model_fields,*base.get('context_fields',[]))}|set(base.get('batch_columns',[]))
        for f in [*model_fields,*base.get('context_fields',[])]:
            input_fields.update(f[k]['column'] for k in ('available_at','effective_at') if f.get(k))
        if base.get('information_cutoff'):input_fields.add(base['information_cutoff']['column'])
        columns=sorted(input_fields|set(base['key_columns'])|set(base['entity_columns'])|{'cg6_prediction','cg6_state','cg6_score','cg6_risk','cg6_scale','cg6_role','cg6_outcome','cg6_outcome_status'}|
                       {f'cg6_p_{j}' for j in range(len(result.data['task'].get('classes',[])))}|
                       {f'cg6_l_{j}' for j in range(len(result.data['task'].get('classes',[])))}|
                       {f'cg6_s_{j}' for j in range(len(result.data['task'].get('classes',[])))}|
                       {f'cg6_quantile_{j}' for j in range(256) if any(len(r.get('quantiles',[]))>j for r in [view.get('representation') or {}])})
        if base.get('roles',{}):
            rolecol=base['roles'].get('column')
            if rolecol:columns=sorted(set(columns)|{rolecol})
        stage=root/('.'+path.name+'.pending')
        with stage.open('x',newline='') as out:
            writer=csv.DictWriter(out,fieldnames=columns);writer.writeheader()
            with open(artifact['path'],'rb') as inp:
                for line in inp:
                    row=result.resolve_retained_assets(json.loads(line))
                    if row['predictor']!=view['predictor'] or row['scenario']!=scope:continue
                    values={k:v for k,v in row.get('input_record',{}).items() if k in columns};c=row['channels']
                    values.update(cg6_prediction=c.get('point',c.get('prediction')),cg6_state='failed' if row['execution']!='completed' else row.get('issuance','missing'),
                                  cg6_score=c.get('score'),cg6_risk=c.get('risk'),cg6_scale=c.get('scale'),cg6_role=row.get('role'),
                                  cg6_outcome=row['truth']['value'] if row['truth']['valid'] else None,cg6_outcome_status='observed' if row['truth']['valid'] else 'invalid')
                    for j,v in enumerate(c.get('probabilities',[])):values[f'cg6_p_{j}']=v
                    for j,v in enumerate(c.get('logits',[])):values[f'cg6_l_{j}']=v
                    if isinstance(c.get('score'),list):
                        values['cg6_score']=None
                        for j,v in enumerate(c['score']):values[f'cg6_s_{j}']=v
                    for j,v in enumerate(c.get('quantiles',[])):values[f'cg6_quantile_{j}']=v
                    for used_events,used_units in memberships:
                        namespace=base['namespace']
                        used=digest([namespace,row['event_key']]) in used_events or digest([namespace,row['entity_key'] or row['event_key']]) in used_units
                        if used and row.get('role') in {'C','E'}:raise EvaluationError('Known auxiliary training/selection contamination blocks the downstream bridge.','auxiliary_role_overlap')
                        if used:values['cg6_role']=''
                    writer.writerow(values)
            out.flush();os.fsync(out.fileno())
        os.chmod(stage,0o600);os.link(stage,path);stage.unlink()
        runs.append(replace(original,id=view['predictor'],source=sid))
        sources.append(SourceSpec(sid,str(path)))
        if (view.get('representation') or {}).get('samples'):
            sample_path=root/(sid+'_draws.csv');compat.destination(sample_path)
            fields=[*base['key_columns'],'cg6_draw','cg6_sample'];sample_stage=root/('.'+sample_path.name+'.pending')
            with sample_stage.open('x',newline='') as out:
                writer=csv.DictWriter(out,fieldnames=fields);writer.writeheader()
                with open(artifact['path'],'rb') as inp:
                    for line in inp:
                        row=json.loads(line)
                        if row['predictor']!=view['predictor'] or row['scenario']!=scope:continue
                        for j,v in enumerate(row['channels'].get('samples',[])):writer.writerow({**{k:row['input_record'][k] for k in base['key_columns']},'cg6_draw':j,'cg6_sample':v})
                out.flush();os.fsync(out.fileno())
            os.chmod(sample_stage,0o600);os.link(sample_stage,sample_path);sample_stage.unlink()
            sources.append(SourceSpec(sid+'_draws',str(sample_path)))
    return EvaluationSpec(task=result.data['task'],sources=tuple(sources),runs=tuple(runs),
        outcomes=OutcomeSnapshotSpec(sources[0].id,'cg6_outcome',tuple(base['key_columns']),status_column='cg6_outcome_status',status_values={'observed':'observed','invalid':'invalid'}),
        cohorts=tuple(base.get('cohorts',())),name=result.data['name'])


def as_reliability_spec(result,*,predictors=None,scope='original',directory=None):
    evaluation=as_evaluation_spec(result,predictors=predictors,scope=scope,directory=directory)
    original=result.private['execution_spec'];declared=original.get('roles') or {}
    roles=RoleSpec(namespace=declared.get('namespace',original['namespace']),column='cg6_role',unit=declared.get('unit','event'))
    reps=[]
    for run in evaluation.runs:
        view=next(v for v in result.private['view_specs'] if v['scope']==scope and v['predictor']==run.id)
        if view['representation']:
            r=RepresentationSpec.from_dict(view['representation']);reps.append(replace(r,run=run.id,samples=replace(r.samples,source=run.source+'_draws') if r.samples else None))
    return ReliabilitySpec(evaluation=evaluation,roles=roles,representations=tuple(reps))
