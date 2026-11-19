"""Outcome-only restatement of sealed execution evidence; no adapter loading."""
from dataclasses import dataclass,replace
import copy
import csv
import json
from pathlib import Path
import shutil
import tempfile
import time

from .. import compat
from ..contracts import Contract,EvaluationError,SourceSpec,OutcomeSnapshotSpec,nested,sequence,name,digest,EvaluationConfig
from ..method_contracts import RoleSpec
from ..result import EvaluationResult
from .contracts import ExecutionSpec
from .artifact_bytes import verify_artifact
from .store import PreparedExecution
from .services import make_result
from ..execution_context import ctx


@dataclass(frozen=True)
class ExecutionRestatementSpec(Contract):
    sources: tuple
    outcomes: OutcomeSnapshotSpec
    reason: str
    as_of: str | None = None
    schema_version: str = 'confidenceguard.execution_restatement_spec/1.0'

    def __post_init__(self):
        sequence(self,'sources',SourceSpec);nested(self,'outcomes',OutcomeSnapshotSpec);name(self.reason)
        if self.outcomes.source not in {s.id for s in self.sources}:raise EvaluationError('Restatement outcome source is absent.')
        if self.as_of:
            from ..history_contracts import instant
            instant(self.as_of)
            if self.outcomes.available_at is None:raise EvaluationError('Restatement as-of requires outcome availability.')
        if self.schema_version!='confidenceguard.execution_restatement_spec/1.0':raise EvaluationError('Unsupported execution restatement.')


def inspect_restatement(parent,spec,*,allowed_roots):
    spec=ExecutionRestatementSpec.from_dict(spec) if isinstance(spec,dict) else spec
    files=[]
    for source in spec.sources:
        identity,_,_=compat.capture(source.path,allowed_roots)
        files.append({'id':source.id,'sha256':identity['sha256'],'bytes':identity['bytes']})
    return {'fingerprint':digest({'parent':parent.binding,'spec':spec.to_dict(),'files':files}),
            'parent_analysis_id':parent.data['analysis_id'],'outcome_sources':files,'execution_repeated':False}


def _worker(parent,spec,config,roots,staging,expected_fingerprint,*,progress=None):
    if inspect_restatement(parent,spec,allowed_roots=roots)['fingerprint']!=expected_fingerprint:raise EvaluationError('Restatement sources changed.','stale_confirmation')
    started=time.monotonic();artifact=copy.deepcopy(parent.private['output_artifact']);artifact['path']=parent.retained_path(artifact['path'])
    verify_artifact(artifact,roots)
    original=ExecutionSpec.from_dict(parent.private['execution_spec'])
    # Relocation changes storage locations, never predictor mathematics. Reuse
    # copied immutable bytes when the original model files no longer exist.
    predictors=[]
    for p in original.predictors:
        retained=parent.private.get('retained_predictor_files',{}).get(p.id)
        if retained:
            p=replace(p,files=tuple(replace(f,path=parent.retained_path(next(v['path'] for v in retained if v['name']==f.name))) for f in p.files))
        predictors.append(p)
    auxiliary=copy.deepcopy(parent.private.get('auxiliary_artifacts',[]))
    for a in auxiliary:
        for p in a['predictors']:
            for f in p['files']:f['path']=parent.retained_path(f['path'])
    original=replace(original,predictors=tuple(predictors),auxiliaries=tuple(auxiliary) if original.auxiliaries else ())
    views=parent.private['view_specs'];root_view=next((v for v in views if v['scope']=='original'),views[0])
    root_path=Path(staging)/'frozen-inputs.csv';fields=set(original.key_columns)|set(original.entity_columns)|{'cg6_role'}
    from ..feature_contracts import FeatureField
    model_fields=[f for p in original.predictors for f in p.inputs]
    model_fields.extend(FeatureField.from_dict(f) for a in original.auxiliaries for p in a['predictors'] for f in p['inputs']
                        if not f['column'].startswith(('_cg6_parent_','_cg6_vector_')))
    for f in model_fields:
        fields.add(f.column)
        fields.update(c.column for c in (f.available_at,f.effective_at) if c)
    for f in original.context_fields:
        fields.add(f.column);fields.update(c.column for c in (f.available_at,f.effective_at) if c)
    fields.update(original.batch_columns)
    if original.information_cutoff:fields.add(original.information_cutoff.column)
    with root_path.open('x',newline='') as out:
        writer=csv.DictWriter(out,fieldnames=sorted(fields));writer.writeheader()
        with compat.secure_open(artifact['path'],roots) as (stream,_):
            for line in stream:
                row=json.loads(line)
                if row['predictor']!=root_view['predictor'] or row['scenario']!=root_view['scope']:continue
                writer.writerow({**{k:row['input_record'].get(k) for k in fields},'cg6_role':row.get('role') or 'E'})
    root_path.chmod(0o600)
    sid='cg6_frozen_inputs'
    if sid in {s.id for s in spec.sources}:raise EvaluationError('Reserved restatement source ID.')
    execution=replace(original,sources=(SourceSpec(sid,str(root_path)),*spec.sources),input_source=sid,outcomes=spec.outcomes,as_of=spec.as_of,
        roles=RoleSpec(namespace=(original.roles.namespace if original.roles else original.namespace),column='cg6_role',unit='entity' if original.entity_columns else 'event'))
    prepared=PreparedExecution(execution,config,(*roots,str(staging)),progress,capture_external=False)
    try:
        prepared.fingerprint=digest({'parent_binding':parent.binding,'outcomes':prepared.fingerprint,'restatement':spec.to_dict()})
        lookup={p.id:p for p in original.predictors}
        from .contracts import PredictorSpec
        lookup.update({k:PredictorSpec.from_dict(v) for k,v in parent.private.get('view_predictors',{}).items()})
        lookup.update({p.id:p for p in original.predictors})
        for declaration in views:
            predictor=lookup.get(declaration['predictor'])
            if predictor is None:raise EvaluationError('Frozen predictor descriptor is unavailable.','restatement_binding')
            view=prepared.start_view(predictor,declaration['scope']);events=[];outputs=[];uncertainty=None
            with compat.secure_open(artifact['path'],roots) as (stream,_):
                for line in stream:
                    row=parent.resolve_retained_assets(json.loads(line))
                    if row['predictor']!=declaration['predictor'] or row['scenario']!=declaration['scope']:continue
                    relation=row.get('variant',{}).get('outcome_relation','unchanged')
                    truth=row['truth']
                    if relation in {'unchanged','label_preserving','registered_transform'}:
                        value=prepared.con.execute(f'SELECT y,y_num,outcome_valid,outcome_reason FROM {prepared.original_table} WHERE event_key=?',[row['event_key']]).fetchone()
                        if value is None:raise EvaluationError('Frozen root population changed.','restatement_binding')
                        y,yn,valid,reason=value;truth={'value':yn if original.task.kind=='regression' else y,'valid':bool(valid),'reason':reason}
                        if relation=='registered_transform':
                            from ..robustness.transformations import transformed_truth
                            truth=transformed_truth(truth,relation,row['variant']['outcome_rule'],{},row['variant']['id'],original.task)
                    event={'event_key':row['event_key'],'entity_key':row['entity_key'],'role':row.get('role') or 'E','truth':truth,'record':row['input_record'],'unavailable_fields':row.get('unavailable_fields',[])}
                    if row.get('variant'):event['variant']=row['variant']
                    output={k:v for k,v in row.items() if k not in {'event_key','entity_key','truth','role','predictor','scenario','input_record','variant','unavailable_fields'}}
                    if output.get('uncertainty'):
                        if uncertainty is None:
                            uncertainty='cg6_restate_uncertainty_'+str(view['index'])
                            prepared.con.execute(f'CREATE TABLE {uncertainty}(ordinal BIGINT,event_key VARCHAR,coverage VARCHAR,output VARCHAR)')
                        ordinal=prepared.con.execute(f'SELECT ordinal FROM {prepared.original_table} WHERE event_key=?',[row['event_key']]).fetchone()[0]
                        prepared.con.executemany(f'INSERT INTO {uncertainty} VALUES (?,?,?,?)',[(ordinal,row['event_key'],v['coverage'],json.dumps(v['output'],allow_nan=False)) for v in output['uncertainty']])
                    events.append(event);outputs.append(output)
                    if len(events)>=512:prepared.append(view,events,outputs);events=[];outputs=[]
            if events:prepared.append(view,events,outputs)
            prepared.finish_view(view)
            if uncertainty:
                if not hasattr(prepared,'uncertainties'):prepared.uncertainties={}
                prepared.uncertainties[view['id']]=uncertainty
        for old,info in parent.private.get('variant_assets',{}).items():
            info={**info,'path':parent.retained_path(info['path'])};verify_artifact(info,roots);prepared.assets[info['path']]=info['path']
        evidence=prepared.metrics()
        result=make_result(prepared,'restatement',{'parent_analysis_id':parent.data['analysis_id'],'parent_binding':parent.binding,
            'reason':spec.reason,'as_of':spec.as_of,'execution_repeated':False,'transformations_repeated':False,
            'claims':[],'scientific_qualification':'descriptive outcome-only restatement; prior inferential claims are not reissued'},
            started=started,evidence=evidence,staging=staging,private_extra={'restatement_spec':spec.to_dict(),'parent_output_digest':artifact['sha256'],
                'auxiliary_artifacts':auxiliary,'execution_membership':parent.private.get('execution_membership')})
        verify_artifact(artifact,roots);prepared.verify();return result
    finally:prepared.close()


def restate_execution(parent,spec,config=None,*,allowed_roots=None,workspace=None,tracking_workspace=None,request_id=None,expected_fingerprint=None,progress=None,cancel=None,_artifact_root=None):
    if isinstance(parent,str):raise EvaluationError('Open protected retained evidence before outcome restatement.')
    parent=copy.deepcopy(parent);EvaluationResult.from_dict(parent.to_private_dict(),private=parent.private)
    if parent.private['execution_spec'].get('evidence_retention','materialized_inputs')!='materialized_inputs':raise EvaluationError('Outcome restatement needs retained frozen inputs.','execution_input_not_retained')
    if not parent.private.get('output_artifact'):raise EvaluationError('Completed exact output evidence is required.')
    spec=ExecutionRestatementSpec.from_dict(spec) if isinstance(spec,dict) else spec
    config=EvaluationConfig.from_dict(config) if isinstance(config,dict) else config or EvaluationConfig.from_dict(parent.private['config'])
    paths=[s.path for s in spec.sources]+[parent.retained_path(parent.private['output_artifact']['path'])]+[parent.retained_path(v['path']) for v in parent.private.get('variant_assets',{}).values()]
    roots=tuple(str(Path(r).absolute()) for r in (allowed_roots if allowed_roots is not None else {str(Path(p).absolute().parent) for p in paths}))
    inspected=inspect_restatement(parent,spec,allowed_roots=roots)
    if expected_fingerprint and expected_fingerprint!=inspected['fingerprint']:raise EvaluationError('Restatement sources changed.','stale_confirmation')
    request_digest=digest({'parent':parent.binding,'restatement':spec.to_dict(),'fingerprint':inspected['fingerprint'],'config':config.to_dict()})
    if workspace is not None and request_id is not None:
        from ..workspace import ReliabilityWorkspace
        ws=ReliabilityWorkspace(workspace) if isinstance(workspace,(str,Path)) else workspace
        with ws.catalog.operation():previous=ws.catalog.receipt(request_id,request_digest)
        if previous:return ws.open(previous['assessment_id'])
    staging=compat.protected_directory(tempfile.mkdtemp(prefix='numek-cg6-restate-',dir=_artifact_root or config.scratch_directory))
    try:
        identity=parent.private.get('execution_membership')
        reservation=checks=None
        if identity:
            from .exposure import reserve
            inherited={**identity,'query_events':identity['events'],'fingerprint':digest({'parent':parent.binding,'restatement':spec.to_dict()})}
            reservation,checks=reserve(inherited,'restatement',{},tracking_workspace or workspace,request_id,config)
        result=ctx.run(_worker,(parent,spec,config,roots,str(staging),inspected['fingerprint']),replace(config,result_bytes=config.private_bytes+config.result_bytes),progress=progress,cancel=cancel)
        if cancel is not None and cancel.is_set():raise EvaluationError('Cancelled before restatement publication.','cancelled')
        if reservation:
            result.private['evidence_use_reservation']=reservation
            result.data['cg6']['exposure_checks']={**checks,'inherited_root_identity':True}
        result.seal()
        if len(result.json_text().encode())>config.private_bytes:raise EvaluationError('Restatement exceeds protected result admission.','private_result_limit')
        if len(json.dumps(result.to_dict()).encode())>config.result_bytes:raise EvaluationError('Restatement exceeds public result admission.','result_limit')
        if workspace:
            from .storage import save_result
            save_result(workspace,result,request_id=request_id,cancel=cancel,request_digest=request_digest)
        return result
    except BaseException:shutil.rmtree(staging,ignore_errors=True);raise
