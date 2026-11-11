"""CG6 source preparation and generated-output views over the CG1/CG2 store."""
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import shutil
from types import SimpleNamespace

import numpy as np

from .. import compat
from ..contracts import (EvaluationSpec,ModelIdentity,PredictionRunSpec,DecisionSpec,
                        ProbabilitySpec,ScoreSpec,SourceSpec,EvaluationError,digest,ContextSnapshotSpec)
from ..engine import open_store
from ..method_contracts import ReliabilitySpec,RoleSpec
from ..sources import rows,key
from ..analytics import Evidence,distributions,evaluate_scope,literal
from ..feature_contracts import FeatureField


class PreparedExecution:
    def __init__(self,spec,config,roots,progress=None,*,capture_external=True):
        self.spec=spec;self.config=config;self.roots=roots;self.progress=progress
        self.work=None;self.assets={};self.files={};self.views=[];self.cell_count=0;self.tensor_snapshots={};self.tensor_inputs={}
        auxiliary_fields=[FeatureField.from_dict(f) for a in spec.auxiliaries for p in a['predictors'] for f in p['inputs']]
        self.bound_fields=(*spec.context_fields,*(f for p in spec.predictors for f in p.inputs),*auxiliary_fields)
        primary=spec.predictors[0]
        base=EvaluationSpec(task=primary.task,sources=spec.sources,
            runs=(PredictionRunSpec('execution_population',spec.input_source,ModelIdentity(primary.id,'cg6',artifact_sha256=primary.predictor_digest),key_columns=spec.key_columns,entity_columns=spec.entity_columns),),
            outcomes=spec.outcomes,context=ContextSnapshotSpec(spec.input_source,spec.key_columns),cohorts=spec.cohorts,name=spec.name,as_of=spec.as_of)
        role=spec.roles or RoleSpec(namespace=spec.namespace,proportions={'E':1})
        extension=ReliabilitySpec(evaluation=base,roles=role)
        projected={s.id:set() for s in spec.sources}
        projected[spec.input_source].update(f.column for f in spec.context_fields)
        projected[spec.input_source].update(spec.batch_columns)
        if spec.information_cutoff:projected[spec.input_source].add(spec.information_cutoff.column)
        for f in spec.context_fields:
            for c in (f.available_at,f.effective_at):
                if c:projected[spec.input_source].add(c.column)
        for p in spec.predictors:
            projected[spec.input_source].update(f.column for f in p.inputs)
            for f in p.inputs:
                for c in (f.available_at,f.effective_at):
                    if c:projected[spec.input_source].add(c.column)
        for a in spec.auxiliaries:
            for p in a['predictors']:
                for f in p['inputs']:
                    if not f['column'].startswith(('_cg6_parent_','_cg6_vector_')):projected[spec.input_source].add(f['column'])
                    for clock in ('available_at','effective_at'):
                        if f.get(clock):projected[spec.input_source].add(f[clock]['column'])
        try:
            self.work,self.store,_=open_store(base,config,roots,progress,extension=extension,projection=projected)
            self.con=self.store.con;self.original_table=self.store.run_tables['execution_population']
            n,unique,missing=self.con.execute(f'SELECT count(*),count(DISTINCT event_key),count(*) FILTER(WHERE event_key IS NULL) FROM {self.original_table}').fetchone()
            if n!=unique or missing:raise EvaluationError('Execution requires unique explicit nonmissing event keys; no observations were dropped.','execution_identity')
            if spec.roles and spec.entity_columns:
                crossed=self.con.execute(f'SELECT count(*) FROM (SELECT entity_key FROM {self.original_table} GROUP BY entity_key HAVING count(DISTINCT cg_role)>1)').fetchone()[0]
                if crossed:raise EvaluationError('Whole entities must stay within CG6 roles.','entity_role_overlap')
            self.count=n;self.files=dict(self.store.sources)
            self.validate_model_fields([f for p in spec.predictors for f in p.inputs]+auxiliary_fields)
            if capture_external:self.capture_external()
            self.fingerprint=digest({'spec':spec.to_dict(),'config':config.to_dict(),
                'files':{k:{x:v.get(x) for x in ('sha256','bytes')} for k,v in self.files.items()},
                'outcomes':self.store.outcome_facts.get('snapshot_digest'),'normalization':'cg1_probability_v1'})
            self.con.execute('CREATE TABLE cg6_outputs(view VARCHAR,event_key VARCHAR,payload VARCHAR,status VARCHAR)')
            self.con.execute('CREATE UNIQUE INDEX cg6_output_identity ON cg6_outputs(view,event_key)')
        except BaseException:
            if self.work:self.work.close()
            raise

    def capture_external(self):
        for p in self.spec.predictors:
            for f in p.files:
                info,_,_=compat.capture(f.path,self.roots,check=lambda:self.work.check('model identity'))
                if info['sha256']!=f.sha256:raise EvaluationError('Model manifest differs from source.','model_changed')
                self.files['model:'+p.id+':'+f.name]=info
            kind=p.preprocessing.get('kind','tabular')
            if kind=='image':
                for event in self.events():
                    raw=event['record'].get(p.inputs[0].column)
                    if not raw:continue
                    path=Path(raw)
                    if not path.is_absolute():path=Path(next(s.path for s in self.spec.sources if s.id==self.spec.input_source)).parent/path
                    info,_,_=compat.capture(path,self.roots,max_bytes=self.config.max_source_bytes)
                    if sum(v['bytes'] for v in self.files.values())+info['bytes']>self.config.max_combined_source_bytes:raise EvaluationError('Combined source/media admission exceeded.','source_limit')
                    target=self.work.root/('asset-'+info['sha256'])
                    if not target.exists():
                        self.work.check('image capture reservation',info['bytes'])
                        with compat.secure_open(path,self.roots) as (source,_),target.open('xb') as out:shutil.copyfileobj(source,out,1024**2)
                    compat.capture(path,self.roots,expected=info)
                    self.assets[raw]=str(target);self.files['asset:'+info['sha256']]=info
            if kind=='tensor':
                for k in ('tensor_file','keys_source'):
                    path=p.preprocessing.get(k)
                    if not isinstance(path,str):raise EvaluationError('Tensor input requires a matrix and keyed source.','tensor_alignment')
                    info,_,_=compat.capture(path,self.roots)
                    if info['bytes']>self.config.max_source_bytes:raise EvaluationError('Tensor input bytes exceeded.','source_limit')
                    self.files['tensor:'+p.id+':'+k]=info
                    target=self.work.root/('tensor-'+info['sha256'])
                    if not target.exists():
                        self.work.check('tensor capture reservation',info['bytes'])
                        with compat.secure_open(path,self.roots) as (source,_),target.open('xb') as out:shutil.copyfileobj(source,out,1024**2)
                    with target.open('rb') as source:actual=hashlib.file_digest(source,'sha256').hexdigest()
                    if actual!=info['sha256']:raise EvaluationError('Tensor source changed during capture.','source_changed')
                    self.tensor_snapshots[path]=str(target)
        if sum(v['bytes'] for v in self.files.values())>self.config.max_combined_source_bytes:raise EvaluationError('Combined input/model source bytes exceeded.','source_limit')

    def events(self,role=None):
        source=self.store.tables[self.spec.input_source]
        where='true' if role is None else 'r.cg_role='+literal(role)
        q=f'SELECT r.event_key,r.entity_key,r.ordinal,r.cg_role,r.y,r.y_num,r.outcome_valid,r.outcome_reason,s.payload FROM {self.original_table} r JOIN {source} s USING(ordinal) WHERE {where} ORDER BY r.event_key'
        for k,entity,ordinal,assignment,y,yn,valid,reason,payload in rows(self.con,q,batch=512):
            record=json.loads(payload);unavailable=[]
            for field,matrix in self.tensor_inputs.values():
                if k in matrix:record[field]=matrix[k].tolist()
            cutoff,state=compat.clock(record.get(self.spec.information_cutoff.column),self.spec.information_cutoff) if self.spec.information_cutoff else (None,None)
            for f in self.bound_fields:
                for clock in (f.available_at,f.effective_at):
                    if clock:
                        tick,status=compat.clock(record.get(clock.column),clock)
                        if tick is None or cutoff is None or state!='valid' or status!='valid' or tick>cutoff:unavailable.append(f.column)
            yield {'event_key':k,'entity_key':entity,'ordinal':ordinal,'role':assignment if self.spec.roles else None,
                   'truth':{'value':yn if self.spec.task.kind=='regression' else y,'valid':bool(valid),'reason':reason},
                   'record':record,'unavailable_fields':sorted(set(unavailable))}

    def validate_model_fields(self,fields):
        forbidden=set(self.spec.key_columns)|set(self.spec.entity_columns)|set(self.spec.batch_columns)
        if self.spec.roles and self.spec.roles.column:forbidden.add(self.spec.roles.column)
        outcome=self.spec.outcomes
        if outcome:
            left=self.files[self.spec.input_source];right=self.files[outcome.source]
            if left['sha256']==right['sha256']:forbidden.update({outcome.column,outcome.status_column})
        if any(f.column in forbidden for f in fields):raise EvaluationError('Known identifiers, roles or authoritative outcome aliases cannot be model inputs.','outcome_input')
        if any(f.available_at or f.effective_at for f in fields) and self.spec.information_cutoff is None:raise EvaluationError('Dated auxiliary/model inputs require an information cutoff.','input_availability')

    def attach(self,adapter):
        adapter.asset_snapshots=self.assets
        p=adapter.spec
        for name,info in adapter.files.items():self.files['model:'+p.id+':'+name]=info
        if p.preprocessing.get('kind')=='tensor':
            from ..feature_storage import validate_matrix
            from ..sources import records
            from ..contracts import SourceSpec
            matrix_path=self.tensor_snapshots[p.preprocessing['tensor_file']];keys_path=self.tensor_snapshots[p.preprocessing['keys_source']]
            validate_matrix(matrix_path,max_bytes=self.config.max_source_bytes,max_rows=self.config.max_rows)
            matrix=np.load(matrix_path,mmap_mode='r',allow_pickle=False,max_header_size=10000)
            keys=[]
            for loc,r in records(keys_path,SourceSpec('tensor_keys',keys_path),self.config,set(p.preprocessing.get('key_columns',self.spec.key_columns))):
                if r is not None:keys.append(key(r,p.preprocessing.get('key_columns',self.spec.key_columns),None))
            if len(keys)!=len(matrix) or None in keys or len(set(keys))!=len(keys):raise EvaluationError('Tensor key alignment differs.','tensor_alignment')
            adapter.tensor_rows={k:matrix[i] for i,k in enumerate(keys)}
            field=p.inputs[0].column;sha=self.files['tensor:'+p.id+':tensor_file']['sha256']
            if not hasattr(self,'tensor_binding_digests'):self.tensor_binding_digests={}
            if field in self.tensor_binding_digests and self.tensor_binding_digests[field]!=sha:raise EvaluationError('One tensor input field cannot refer to differing materialized matrices.','tensor_input_binding')
            self.tensor_binding_digests[field]=sha
            self.tensor_inputs[p.id]=(p.inputs[0].column,adapter.tensor_rows)

    def start_view(self,predictor,scope):
        index=len(self.views)+1;sid=f'cg6_generated_{index}';table=f'cg6_generated_raw_{index}'
        rid=predictor.id if scope=='original' else predictor.id+'@'+scope
        self.con.execute(f'CREATE TABLE {table}(ordinal BIGINT,payload VARCHAR)')
        self.store.tables[sid]=table;self.store.counts[sid]=0
        self.store.sources[sid]={'sha256':digest([self.fingerprint,predictor.predictor_digest,scope]),'bytes':0}
        source=SourceSpec(sid,str(self.work.root/(sid+'.csv')))
        outputs={b.channel:b for b in predictor.outputs};pred='cg6_prediction' if 'prediction' in outputs or 'point' in outputs else None
        probabilities=ProbabilitySpec(columns={c:'cg6_p_'+str(i) for i,c in enumerate(self.spec.task.classes)}) if 'probabilities' in outputs else None
        score=(ScoreSpec(columns={c:'cg6_s_'+str(i) for i,c in enumerate(self.spec.task.classes)},direction=outputs['score'].direction,meaning=outputs['score'].meaning) if outputs['score'].classes else ScoreSpec(column='cg6_score',direction=outputs['score'].direction,meaning=outputs['score'].meaning)) if 'score' in outputs else None
        selection=ScoreSpec(column='cg6_risk',direction='lower',meaning='selection') if 'risk' in outputs else None
        decision=replace(predictor.decision,column=pred,state_column='cg6_state',state_values={'issued':'issued','abstained':'abstained','failed':'failed','missing':'missing'})
        run=PredictionRunSpec(rid,sid,ModelIdentity(predictor.id,'cg6',artifact_sha256=predictor.predictor_digest,preprocessing=digest(predictor.preprocessing)),key_columns=self.spec.key_columns,
            entity_columns=self.spec.entity_columns,prediction=pred,decision=decision,probabilities=probabilities,score=score,selection=selection)
        view={'id':rid,'scope':scope,'predictor':predictor,'run':run,'source':source,'table':table,'index':index,'rows':0,'hash':hashlib.sha256()}
        if 'samples' in outputs:
            self.con.execute(f'CREATE TABLE {table}_draws(ordinal BIGINT,payload VARCHAR)')
            self.store.tables[sid+'_draws']=table+'_draws';view['sample_rows']=0
        self.views.append(view);return view

    def append(self,view,events,outputs):
        raw=[];ledger=[];draws=[]
        for event,out in zip(events,outputs):
            record=dict(event['record'])
            channels=out['channels'];record['cg6_prediction']=channels.get('point',channels.get('prediction'))
            # The CG1 normalizer owns derived decisions. Latent probabilities
            # remain available even if a supplied hard-output channel is invalid.
            record['cg6_state']='failed' if out['execution']!='completed' else out.get('issuance') or channels.get('issuance') or ('issued' if record['cg6_prediction'] is not None else 'abstained' if view['predictor'].decision.rule!='none' else 'missing')
            for i,v in enumerate(channels.get('probabilities',[])):record['cg6_p_'+str(i)]=v
            for i,v in enumerate(channels.get('logits',[])):record['cg6_l_'+str(i)]=v
            record['cg6_score']=channels.get('score')
            record['cg6_risk']=channels.get('risk')
            if isinstance(record['cg6_score'],list):
                for j,v in enumerate(record['cg6_score']):record['cg6_s_'+str(j)]=v
                record['cg6_score']=None
            record['cg6_scale']=channels.get('scale')
            for j,v in enumerate(channels.get('quantiles',[])):record['cg6_quantile_'+str(j)]=v
            record['cg6_outcome']=event['truth']['value'] if event['truth']['valid'] else None
            record['cg6_outcome_status']='observed' if event['truth']['valid'] else 'invalid'
            record['cg6_role']=event.get('role')
            for draw,value in enumerate(channels.get('samples',[])):
                view['sample_rows']+=1
                draws.append((view['sample_rows'],json.dumps({**{k:record[k] for k in self.spec.key_columns},'cg6_draw':str(draw),'cg6_sample':value})))
            view['rows']+=1
            text=json.dumps(record,ensure_ascii=True,allow_nan=False,separators=(',',':'))
            raw.append((view['rows'],text));view['hash'].update(text.encode())
            payload={**out,'event_key':event['event_key'],'entity_key':event['entity_key'],'role':event['role'],'truth':event['truth'],
                     'predictor':view['predictor'].id,'scenario':view['scope'],'input_record':event['record'],'unavailable_fields':event.get('unavailable_fields',[])}
            if event.get('variant'):payload['variant']=event['variant']
            ledger.append((view['id'],event['event_key'],json.dumps(payload,allow_nan=False,separators=(',',':')),out['execution']))
            self.cell_count+=sum(len(v) if isinstance(v,list) else 1 for v in channels.values())
            def cells(v):return sum(cells(x) for x in v) if isinstance(v,list) else 1
            self.cell_count+=sum(cells(v) for v in out.get('original_outputs',{}).values())
        if self.cell_count>min(self.spec.limits.max_output_cells,self.config.probability_cells):raise EvaluationError('Output cell admission exceeded.','output_cell_limit')
        compat.insert_rows(self.con,view['table'],raw);compat.insert_rows(self.con,'cg6_outputs',ledger)
        if draws:compat.insert_rows(self.con,view['table']+'_draws',draws)
        self.store.counts[view['source'].id]=view['rows']

    def finish_view(self,view):
        self.store.sources[view['source'].id]['sha256']=view['hash'].hexdigest()
        self.store.spec=SimpleNamespace(**{**vars(self.store.spec),'sources':(*self.store.spec.sources,view['source'])})
        self.store.normalize(view['run'],view['index'])
        rt=self.store.run_tables[view['id']]
        from ..method_contracts import RepresentationSpec,QuantileField,SampleSpec
        outputs={b.channel:b for b in view['predictor'].outputs}
        if set(outputs)&{'scale','quantiles','logits','samples'}:
            params={}
            if 'logits' in outputs:params['logits']={c:'cg6_l_'+str(i) for i,c in enumerate(self.spec.task.classes)}
            if 'samples' in outputs:params['samples']=SampleSpec(view['source'].id+'_draws',self.spec.key_columns,'cg6_draw','cg6_sample')
            if 'scale' in outputs:params.update(scale='cg6_scale',scale_model=view['run'].model.to_dict())
            if 'quantiles' in outputs:params.update(quantiles=tuple(QuantileField(str(q),'cg6_quantile_'+str(j)) for j,q in enumerate(outputs['quantiles'].levels)),quantile_model=view['run'].model.to_dict())
            self.store.representations[view['id']]=RepresentationSpec(view['id'],**params)
        self.store.extras(view['run']);self.store.roles(view['run'])
        # Outcome relations are explicit variant evidence. Original labels must
        # not leak through the normalizer's root-key join into an unknown world.
        valid="json_extract_string(o.payload,'$.truth.valid')='true'"
        y="NULL" if self.spec.task.kind=='regression' else f"CASE WHEN {valid} THEN json_extract_string(o.payload,'$.truth.value') END"
        yn=f"CASE WHEN {valid} THEN TRY_CAST(json_extract_string(o.payload,'$.truth.value') AS DOUBLE) END" if self.spec.task.kind=='regression' else "NULL"
        self.con.execute(f"UPDATE {rt} r SET outcome_valid={valid},y={y},y_num={yn},outcome_reason=json_extract_string(o.payload,'$.truth.reason'),ptrue=NULL,brier=NULL,log_loss=NULL,log_infinite=false FROM cg6_outputs o WHERE o.view=? AND o.event_key=r.event_key",[view['id']])
        self.store.refresh_losses(rt)
        self.con.execute(f"UPDATE cg6_outputs o SET payload=json_merge_patch(o.payload,json_object('decision',r.decision,'issuance',r.state)) FROM {rt} r WHERE o.view=? AND o.event_key=r.event_key",[view['id']])

    def metrics(self):
        runs=tuple(v['run'] for v in self.views)
        self.store.spec=SimpleNamespace(**{**vars(self.store.spec),'runs':runs})
        self.store.run_tables={r.id:self.store.run_tables[r.id] for r in runs}
        self.store.run_facts={r.id:self.store.run_facts[r.id] for r in runs}
        e=Evidence(self.store)
        for v in self.views:
            r=v['run'];table=self.store.run_tables[r.id]
            distributions(e,r,table);evaluate_scope(e,r,table,'true','overall' if v['scope']=='original' else v['scope'])
            if r.id in getattr(self,'uncertainties',{}) or r.id in self.store.representations:
                from ..uncertainty import build_losses,evaluate_losses
                loss_table,metadata=build_losses(self.store,r,table,root=r.id,uncertainty_table=getattr(self,'uncertainties',{}).get(r.id))
                evaluate_losses(e,r,table,loss_table,metadata,'true','overall' if v['scope']=='original' else v['scope'])
            for i,c in enumerate(self.spec.cohorts):
                for group, in self.con.execute(f'SELECT DISTINCT g{i} FROM {table} ORDER BY 1').fetchall():
                    if group!='unresolved':evaluate_scope(e,r,table,f'g{i}={literal(group)}',v['scope']+f'/cohort_{i}/'+group)
        e.validate_populations();return e

    def output_rows(self,view=None):
        where=' WHERE view='+literal(view) if view is not None else ''
        for payload, in rows(self.con,'SELECT payload FROM cg6_outputs'+where+' ORDER BY view,event_key',batch=512):yield json.loads(payload)

    def verify(self):
        for info in self.files.values():compat.capture(info['path'],self.roots,expected=info,check=lambda:self.work.check('final CG6 source verification'))

    def close(self):
        if self.work:self.work.close()
