"""CG5 role-restricted adapters over the authoritative live/historical stores."""
from contextlib import contextmanager
from dataclasses import replace
import copy
import json
import math
from pathlib import Path
from types import SimpleNamespace

from . import compat
from .contracts import EvaluationError, PredictionRunSpec, digest
from .engine import open_store
from .sources import rows, key, number
from .analytics import literal
from .features import (normalize, missing_cell, apply_availability, outcome_bound_fields,
                       FEATURE_TIME_POLICY)
from .method_contracts import ReliabilitySpec, MethodSpec
from .policy_contracts import PolicyInputSpec
from .policy_runtime import Budget

INPUT_COLUMNS={'state','decision','point','prob_valid','probs','rank_score','selector',
               'scale','quantiles','sample_count','sample_valid','prediction_tick','candidate'}


def _projection(spec):
    evaluation=spec.evaluation; wanted={s.id:set() for s in evaluation.sources}
    runs={r.id:r for r in evaluation.runs}
    for view in spec.features:
        run=runs[view.run or evaluation.runs[0].id]; sid=view.source or run.source
        if sid not in wanted: raise EvaluationError('Feature source is absent.','policy_input')
        wanted[sid].update(view.key_columns or run.key_columns)
        wanted[sid].update(f.column for f in view.fields)
        for clock in (view.available_at,view.information_cutoff,*(f.available_at for f in view.fields),*(f.effective_at for f in view.fields)):
            if clock: wanted[sid].add(clock.column)
    return wanted


class PolicyStore:
    """No discovery sampling and no optimizer access to an assessment relation."""
    def __init__(self, spec, config, limits, work, store, *, phase='selection', history=None):
        self.input=spec; self.config=config; self.limits=limits; self.work=work; self.store=store
        self.con=store.con; self.phase=phase; self.history=history; self.task=store.spec.task
        self.budget=Budget(limits,config,work.check)
        original_runs={r.id:r for r in store.spec.runs}
        for alias,target in spec.run_bindings.items():
            if target not in original_runs or alias in original_runs and alias!=target: raise EvaluationError('Run alias conflicts with a retained variant.','policy_run_binding')
            store.run_tables[alias]=store.run_tables[target]; store.run_facts[alias]=store.run_facts[target]
            original_runs[alias]=replace(original_runs[target],id=alias)
            if target in getattr(store,'representations',{}): store.representations[alias]=replace(store.representations[target],run=alias)
            if target in getattr(store,'input_facts',{}): store.input_facts[alias]=store.input_facts[target]
            if target in getattr(store,'policy_uncertainties',{}): store.policy_uncertainties[alias]=store.policy_uncertainties[target]
        store.spec=SimpleNamespace(**{**vars(store.spec),'runs':tuple(original_runs.values())})
        self.runs=original_runs
        self.anchor=next(iter(self.runs))
        self.files=copy.deepcopy(store.sources); self.feature_tables={}; self.uncertainties=getattr(store,'policy_uncertainties',{})
        self.known_outcome_features=outcome_bound_fields(spec.evaluation,spec.features,store.sources) if spec.evaluation else set()
        self.known_outcome_features.update(v.id+'.'+f.id for v in spec.features for f in v.fields if f.outcome_derived or f.role=='retrospective')
        for run,table in store.run_tables.items():
            n,unique,missing=self.con.execute(f'SELECT count(*),count(DISTINCT event_key),count(*) FILTER(WHERE event_key IS NULL) FROM {table}').fetchone()
            if n!=unique or missing: raise EvaluationError('Policy populations require unique explicit event keys.','policy_identity')
            missing_roles=self.con.execute(f'SELECT count(*) FROM {table} WHERE cg_role IS NULL').fetchone()[0]
            if missing_roles: raise EvaluationError('Every planned opportunity needs a declared role.','policy_unassigned_role')
            overlaps=self.con.execute(f'SELECT count(*) FROM (SELECT entity_key FROM {table} WHERE entity_key IS NOT NULL GROUP BY 1 HAVING count(DISTINCT cg_role)>1)').fetchone()[0]
            if overlaps: raise EvaluationError('An entity crosses development/assessment roles.','entity_role_overlap')
            if run!=self.anchor and (self.runs[run].entity_columns or self.runs[self.anchor].entity_columns):
                anchor=store.run_tables[self.anchor]
                conflicts=self.con.execute(f'SELECT count(*) FROM {anchor} a JOIN {table} b USING(event_key) WHERE a.entity_key IS DISTINCT FROM b.entity_key').fetchone()[0]
                if conflicts: raise EvaluationError('Model outputs disagree on canonical event/entity ownership.','policy_entity_identity_conflict')
        if not history:
            for i,view in enumerate(spec.features):
                run=self.runs[view.run or next(iter(self.runs))]
                source=view.source or run.source; table='policy_feature_'+str(i)
                store.keyed(source,view.key_columns or run.key_columns,table)
                bad=self.con.execute(f'SELECT count(*) FROM {table} WHERE event_key IS NULL OR multiplicity<>1').fetchone()[0]
                if bad: raise EvaluationError('Feature joins require unique explicit keys.','feature_key_conflict')
                self.feature_tables[view.id]=table
        # External frozen vectors are source evidence too. Bind their bytes in
        # the identity/reservation phase, before any analytical materialization.
        for rep in spec.region_representations:
            if rep.kind=='supplied':
                for suffix,path in [('matrix',rep.matrix_path),('keys',rep.keys_source.path)]:
                    info,_,_=compat.capture(path,store.roots,check=lambda:work.check('frozen policy representation identity'))
                    if info['bytes']>config.max_source_bytes: raise EvaluationError('Frozen representation source exceeds admission.','source_limit')
                    self.files[rep.id+':'+suffix]=info
                    work.check('frozen policy representation identity')
        if sum(v.get('bytes',0) for v in self.files.values())>config.max_combined_source_bytes:
            raise EvaluationError('Policy sources and frozen representations exceed combined admission.','source_limit')
        lineage={'input':spec.to_dict(),'files':{k:{n:v.get(n) for n in ('sha256','bytes')} for k,v in self.files.items()},
                 'history':history,'outcome_snapshot':store.outcome_facts.get('snapshot_digest'),'feature_time_policy':FEATURE_TIME_POLICY}
        self.fingerprint=digest(lineage)
        self.cache={}; self.materialized={}
        self.projected_runs=set(self.runs)
        self.budget.policy_store=self

    def project(self,definitions):
        from .policy_contracts import referenced_runs
        if self.materialized:raise AssertionError('Policy projection must precede materialization')
        runs={self.anchor}|{v.run for v in definitions}|{v.run for v in self.input.features if v.run}
        for definition in definitions:runs.update(referenced_runs(definition.to_dict(),[v.to_dict() for v in self.input.features]))
        if runs-self.runs.keys():raise EvaluationError('Referenced policy run is not declared.','policy_run')
        self.projected_runs=runs

    def check_role(self,role):
        if self.phase=='selection' and role!='S':
            raise EvaluationError('Selection services cannot access assessment inputs.','policy_role_sealed')
        if role not in {'F','S','C','E','all'}: raise EvaluationError('Unsupported policy role.')

    def policy_identity(self,run,definition=None):
        if run not in self.runs: raise EvaluationError('Policy run is absent.','policy_run')
        declaration=self.runs[run]
        model=declaration.model.to_dict(); model.pop('display_name',None)
        rep=self.store.representations.get(run) if hasattr(self.store,'representations') else None
        fitted=next((m['artifact_digest'] for m in self.input.fitted_methods if m['id']==run),None)
        if self.history:
            target=self.input.run_bindings.get(run,run)
            chain=self.history.get('method_digests',{}).get(target,[])
            fitted=chain[-1] if chain else None
        identity={'version':'policy_input_semantics_v2','task':self.task.to_dict(),'model':model,
                'decision':declaration.decision.to_dict(),'prediction':declaration.prediction,
                'probability_tolerance':self.config.probability_tolerance,
                'prediction_at':declaration.prediction_at.to_dict() if declaration.prediction_at else None,
                'method_digest':fitted,'representation':rep.to_dict() if rep else None,
                'probability':declaration.probabilities.to_dict() if declaration.probabilities else None,
                'score':declaration.score.to_dict() if declaration.score else None,
                'selection':declaration.selection.to_dict() if declaration.selection else None,
                'intervals':[v.to_dict() for v in declaration.intervals],
                'features':[v.to_dict() for v in self.input.features],
                'regions':[r['artifact']['artifact_digest'] for r in self.input.regions],
                'region_representations':[next((region['representation_contract'] for region in self.input.regions if (region.get('representation_contract') or {}).get('id')==r.id),{k:v for k,v in r.to_dict().items() if k not in {'matrix_path','keys_source','model_directory'}}) for r in self.input.region_representations],
                'feature_time_view':self.input.feature_time_view,'feature_time_policy':FEATURE_TIME_POLICY}
        if definition:
            from .policy_contracts import referenced_runs
            refs=referenced_runs(definition,identity['features'])
            if refs:identity['referenced_runs']={key:self.policy_identity(key) for key in refs}
        return identity

    def bind_policy(self,policy):
        from .policy_contracts import validate_bound_references
        if policy.task!=self.task: raise EvaluationError('Frozen policy task differs from its evidence.','incompatible_policy_input')
        identity=self.policy_identity(policy.run,policy.to_dict())
        validate_bound_references(policy,identity)
        if policy.input_identity and policy.input_identity!=identity:
            raise EvaluationError('Frozen policy input semantics differ.','incompatible_policy_input')
        return replace(policy,input_identity=identity)

    def count(self,run,role):
        self.check_role(role)
        table=self.store.run_tables[self.anchor]; where='true' if role=='all' else 'cg_role='+literal(role)
        return self.con.execute(f'SELECT count(*) FROM {table} WHERE {where}').fetchone()[0]

    def cutpoints(self,run,role,ref):
        self.check_role(role)
        # Simple normalized scalar inputs use DuckDB's grouped sort, with spill.
        table=self.store.run_tables[ref.get('run',run)]; kind=ref['kind']; where='true' if role=='all' else 'cg_role='+literal(role)
        anchor=self.store.run_tables[self.anchor]
        where+=f' AND event_key IN (SELECT event_key FROM {anchor} WHERE '+('true' if role=='all' else 'cg_role='+literal(role))+')'
        expr={'score':'rank_score','selector':'selector','point':'point','scale':'scale','confidence':'confidence'}.get(kind)
        if kind=='probability':
            if ref['target'] not in self.task.classes: raise EvaluationError('Unknown probability class.')
            expr=f'probs[{self.task.classes.index(ref["target"])+1}]'; where+=' AND prob_valid'
        if expr:
            limit=self.limits.max_cutpoints
            result=self.con.execute(f'SELECT DISTINCT {expr} v FROM {table} WHERE {where} AND {expr} IS NOT NULL AND isfinite({expr}) ORDER BY v LIMIT ?',[limit+1]).fetchall()
            if len(result)>limit: raise EvaluationError('Scalar cutpoints exceed admission.','policy_cutpoint_limit')
            self.budget.materialize(len(result)*64)
            return [v for v, in result]
        from .policy_runtime import read_value
        values=set()
        for events,_ in self.batches(run,role):
            for event in events:
                value,state=read_value(ref,event,run,self.budget)
                if state=='observed' and type(value) in (int,float) and math.isfinite(value): values.add(value)
                if len(values)>self.limits.max_cutpoints: raise EvaluationError('Scalar cutpoints exceed admission.','policy_cutpoint_limit')
        return sorted(values)

    def _feature_cells(self,records,run,raw_views):
        asof=None
        if self.input.as_of:
            from .history_contracts import instant
            asof=instant(self.input.as_of)
        result=[{} for _ in records]
        for view in self.input.features:
            for i,record in enumerate(records):
                owner=record.get('_owners',{}).get(view.run or self.anchor)
                raw=raw_views.get(view.id,{}).get(record['event_key'])
                retained=record.get('_typed_features',{}).get(view.id)
                for f in view.fields:
                    if retained is not None:
                        cell=copy.deepcopy(retained.get('values',{}).get(f.id,missing_cell(f.kind)))
                        from .investigation_history import retained_cutoff
                        cutoff,state=retained_cutoff(view,retained)
                        if not view.information_cutoff: cutoff,state=(owner or {}).get('prediction_tick'),None
                    elif raw is not None and f.column in raw:
                        clock=f.available_at or view.available_at
                        available,state=compat.clock(raw.get(clock.column),clock) if clock else (None,'undeclared')
                        effective,_=compat.clock(raw.get(f.effective_at.column),f.effective_at) if f.effective_at else (None,'undeclared')
                        cell=normalize(raw[f.column],f,available_ns=available,effective_ns=effective,availability_state=state)
                        cutoff,state=compat.clock(raw.get(view.information_cutoff.column),view.information_cutoff) if view.information_cutoff else ((owner or {}).get('prediction_tick'),None)
                    else:
                        result[i][view.id+'.'+f.id]=missing_cell(f.kind); continue
                    result[i][view.id+'.'+f.id]=apply_availability(cell,view=self.input.feature_time_view,cutoff_ns=cutoff,cutoff_state=state,as_of_ns=asof,declaration=view.availability)
        return result

    def batches(self,run,role,*,batch_size=512):
        self.check_role(role)
        if run not in self.runs: raise EvaluationError('Policy input run is absent.','policy_run')
        table=self.store.run_tables[self.anchor]; where='true' if role=='all' else 'cg_role='+literal(role)
        cursor=self.con.cursor(); cursor.execute(f'SELECT * FROM {table} WHERE {where} ORDER BY event_key')
        columns=[c[0] for c in cursor.description]
        try:
            while chunk:=cursor.fetchmany(batch_size):
                records=[dict(zip(columns,row)) for row in chunk]; keys=[r['event_key'] for r in records]
                self.budget.materialize(sum(len(json.dumps(r,default=str))+1024 for r in records)*4)
                self.con.execute('CREATE OR REPLACE TABLE policy_batch_keys(event_key VARCHAR)')
                self.con.executemany('INSERT INTO policy_batch_keys VALUES (?)',[(k,) for k in keys])
                for record in records: record['_owners']={}
                positions={r['event_key']:r for r in records}
                for rid,rt in self.store.run_tables.items():
                    if rid not in self.projected_runs:continue
                    for k,tick in rows(self.con,f'SELECT event_key,prediction_tick FROM {rt} JOIN policy_batch_keys USING(event_key)'):
                        positions[k]['_owners'][rid]={'prediction_tick':tick}
                if self.history:
                    windows={}
                    for k,w in rows(self.con,'SELECT event_key,window_id FROM policy_window_members JOIN policy_batch_keys USING(event_key)'):
                        windows.setdefault(k,[]).append(w)
                    for r in records: r['_windows']=windows.get(r['event_key'],[])
                raw_views={}
                for view in self.input.features:
                    if self.history: continue
                    ft=self.feature_tables[view.id]
                    raw_views[view.id]={k:json.loads(p) for k,p in rows(self.con,f'SELECT event_key,payload FROM {ft} JOIN policy_batch_keys USING(event_key)')}
                if self.history:
                    for record in records:
                        record['_typed_features']={}
                        for view in self.input.features:
                            matches=self.con.execute('SELECT payload FROM policy_retained_features WHERE event_key=? AND view_id=?',[record['event_key'],view.id]).fetchall()
                            if len(matches)==1: record['_typed_features'][view.id]=json.loads(matches[0][0])
                features=self._feature_cells(records,run,raw_views)
                inputs=[{} for _ in records]; bykey={k:i for i,k in enumerate(keys)}
                for rid,rt in self.store.run_tables.items():
                    if rid not in self.projected_runs:continue
                    rc=self.con.execute(f'SELECT r.* FROM {rt} r JOIN policy_batch_keys USING(event_key)'); names=[c[0] for c in rc.description]
                    input_rows=rc.fetchall()
                    rep=self.store.representations.get(rid) if hasattr(self.store,'representations') else None
                    original=self.runs[rid]
                    raw_by_key={}
                    if not self.history and original.source in self.store.tables:
                        raw_by_key={k:json.loads(p) for k,p in rows(self.con,f'SELECT b.event_key,s.payload FROM {rt} b JOIN policy_batch_keys USING(event_key) JOIN {self.store.tables[original.source]} s USING(ordinal)')}
                    samples={}
                    source=self.store.input_facts.get(rid,{}) if hasattr(self.store,'input_facts') else {}
                    if source.get('sample_table'):
                        for k,v in rows(self.con,f'SELECT s.event_key,s.value FROM {source["sample_table"]} s JOIN policy_batch_keys USING(event_key) ORDER BY event_key,draw'):
                            samples.setdefault(k,[]).append(v)
                            if sum(len(v) for v in samples.values())*32>self.budget.materialized_limit//4: raise EvaluationError('Predictive samples exceed materialization admission.','policy_memory_admission')
                    uncertainty={}
                    if rid in self.uncertainties:
                        for k,coverage,output in rows(self.con,f'SELECT u.event_key,u.coverage,u.output FROM {self.uncertainties[rid]} u JOIN policy_batch_keys USING(event_key)'):
                            uncertainty.setdefault(k,{})[coverage]=json.loads(output)
                    for row in input_rows:
                        record=dict(zip(names,row)); event=record['event_key']; r={k:v for k,v in record.items() if k in INPUT_COLUMNS}
                        r.update(_classes=list(self.task.classes),_has_selector=original.selection is not None or original.score is not None and original.score.meaning=='selection',
                                 _score_meaning=original.score.meaning if original.score else 'event_ranking',_intervals={},_sets={})
                        if original.selection is None and original.score and original.score.meaning=='selection':r['selector']=record.get('rank_score')
                        raw=raw_by_key.get(event,{})
                        if original.score and original.score.columns:
                            scores=[number(raw.get(original.score.columns[c])) for c in self.task.classes]
                            r['scores']=scores if all(v is not None for v in scores) else None
                        r['_quantiles']={q.level:v for q,v in zip(rep.quantiles,record.get('quantiles') or [])} if rep else {}
                        if record.get('sample_valid') and event in samples: r['_samples']=samples[event]
                        for i,interval in enumerate(original.intervals):
                            lo,hi=record.get('l'+str(i)),record.get('u'+str(i))
                            if lo is not None and hi is not None:
                                r['_intervals'][interval.id]={'lower':lo,'upper':hi,'width':max(0.,hi-lo),'state':'empty' if lo>hi else 'unbounded' if not math.isfinite(hi-lo) else 'finite'}
                        for coverage,output in uncertainty.get(event,{}).items():
                            if 'classes' in output: r['_sets'][coverage]=output
                            else:
                                interval=uncertainty_interval(output)
                                if interval: r['_intervals'][coverage]=interval
                        inputs[bykey[event]][rid]=r
                events=[{'event_key':r['event_key'],'entity_key':r.get('entity_key'),'role':r.get('cg_role'),
                         'inputs':inp,'features':feature,'regions':{}} for r,inp,feature in zip(records,inputs,features)]
                self._regions(events)
                yield events,records
                self.work.check('role-restricted policy batch')
        finally: cursor.close()

    def _regions(self,events):
        if not self.input.regions: return
        import numpy as np
        from .investigation_membership import apply
        features={fid:[e['features'].get(fid,missing_cell('categorical')) for e in events] for fid in {k for e in events for k in e['features']}}
        representations={}
        for rep in self.input.region_representations:
            if rep.kind=='retained':
                loader=getattr(self.store,'policy_retained_representation',None)
                if loader: representations[rep.id]=loader(rep,events)
                continue
            if rep.kind!='supplied':
                raise EvaluationError('CG5 consumes frozen supplied or retained vectors; encode upstream before policy selection.','policy_frozen_representation_required')
            from .representations import supplied,subset
            key='region_rep:'+rep.id
            if key not in self.cache:
                role=" WHERE cg_role='S'" if self.phase=='selection' else " WHERE cg_role='E'" if self.phase=='assessment' else ''
                keys=[r[0] for r in self.con.execute(f'SELECT event_key FROM {self.store.run_tables[self.anchor]}'+role+' ORDER BY event_key').fetchall()]
                self.budget.materialize(len(keys)*max(1,rep.dimensions or 16384)*8*2)
                whole,files=supplied(rep,keys,self.work,self.config,self.store.roots)
                if any(any(self.files[k].get(field)!=info.get(field) for field in ('sha256','bytes')) for k,info in files.items()):
                    raise EvaluationError('Frozen representation changed after policy source reservation.','source_changed')
                self.cache[key]=(whole,{k:i for i,k in enumerate(keys)})
            whole,indices=self.cache[key]
            data=subset(whole,np.asarray([indices[e['event_key']] for e in events],dtype=int))
            for i,e in enumerate(events):
                if not data['available'][i]: continue
                tick,state=data.get('availability',{}).get(e['event_key'],(None,'undeclared'))
                clock=e['inputs'].get(rep.run or next(iter(self.runs)),{}).get('prediction_tick')
                if rep.availability!='at_decision' and (state!='valid' or clock is None or tick>clock): data['available'][i]=False
            representations[rep.id]=data
        for region in self.input.regions:
            artifact=region['artifact']; cache={'_models':region['models'],'_population_size':len(events),
                '_directory':str(self.work.root),'_membership_memory_bytes':self.budget.materialized_limit,
                '_max_distance_ops':self.limits.action_cells-self.budget.counts['action_cells'],'_threads':self.config.threads}
            self.budget.charge('predicate_events',len(events))
            if artifact['kind'] not in {'structured','catboost'} and artifact.get('representation') in representations:
                from .investigation_membership import geometry_document
                parameters=artifact['parameters']
                geometry=geometry_document(region['models'].get(parameters['geometry_digest']),parameters['geometry_digest']) if 'geometry_digest' in parameters else parameters
                centers=geometry['centers']
                work=len(events)*len(centers)*(len(centers[0]) if centers else 0)
                self.budget.charge('action_cells',work)
            mask=apply(artifact,features,representations,cache=cache,check=self.work.check)
            for e,member,available in zip(events,mask['member'],mask['available']):
                e['regions'][artifact['artifact_digest']]='member' if member and available else 'nonmember' if available else 'unavailable'

    def materialize(self,run,role):
        cachekey=(self.anchor,role)
        if cachekey in self.materialized: return self.materialized[cachekey]
        n=self.count(run,role)
        self.budget.materialize(n*(2048+len(self.task.classes)*32*len(self.projected_runs)+sum(len(v.fields) for v in self.input.features)*512))
        events=[]; records=[]; size=0
        for batch,truth in self.batches(run,role):
            size+=sum(len(json.dumps(e,default=str))+len(json.dumps(r,default=str))+1024 for e,r in zip(batch,truth))*3
            self.budget.materialize(size); events.extend(batch); records.extend(truth)
        self.materialized[cachekey]=(events,records)
        self.budget.reserve('frame:'+role,size)
        return events,records

    def identifiers(self,run,role):
        from .evidence_use import source_aliases,source_scope_aliases
        self.check_role(role); table=self.store.run_tables[self.anchor]
        where='true' if role=='all' else 'cg_role='+literal(role)
        events=set(); units=set(); primary=[]; scope_aliases=set()
        for event,entity in rows(self.con,f'SELECT event_key,entity_key FROM {table} WHERE {where} ORDER BY event_key'):
            events.add(digest([self.input.roles.namespace,event])); units.add(digest([self.input.roles.namespace,entity or event])); primary.append(event)
            aliases=self.history.get('source_aliases',{}).get(event,[]) if self.history else [(v,event,entity) for v in self.files.values()]
            for info,eventkey,entitykey in aliases:
                a,b=source_aliases(info,eventkey,entitykey); events.update(a); units.update(b)
                scope_aliases.update(source_scope_aliases(info))
            self.budget.materialize((len(events)+len(units))*192)
        return {'events':sorted(events),'query_events':sorted(events|scope_aliases),'units':sorted(units),'population_digest':digest(primary),
                'planned':len(primary),'identity_scope':'canonical_history_keys_and_retained_original_aliases' if self.history and all(self.history.get('source_aliases',{}).get(k) for k in primary) else 'canonical_history_keys_original_aliases_incomplete' if self.history else 'live_source_keys_and_available_local_aliases'}

    def verify(self):
        if not self.history: self.store.verify()
        for info in self.files.values():
            if info.get('path') and info.get('sha256'): compat.capture(info['path'],self.store.roots,expected=info)


def uncertainty_interval(output):
    def scalar(v):
        if type(v) in (int,float): return float(v)
        if type(v) is dict:
            return v.get('value') if v.get('value_state')=='finite' else math.inf if v.get('value_state')=='positive_infinity' else -math.inf if v.get('value_state')=='negative_infinity' else None
    lo,hi=scalar(output.get('lower')),scalar(output.get('upper'))
    if lo is None or hi is None: return None
    return {'lower':lo,'upper':hi,'width':max(0.,hi-lo),'state':'empty' if lo>hi else 'unbounded' if not math.isfinite(hi-lo) else 'finite'}


@contextmanager
def prepared_policy(spec,config,limits,roots,progress=None,*,phase='selection'):
    if spec.history:
        from .policy_history import prepared_policy_history
        with prepared_policy_history(spec,config,limits,roots,progress,phase=phase) as value: yield value
        return
    extension=ReliabilitySpec(evaluation=spec.evaluation,roles=spec.roles,representations=spec.representations,
        fitted_methods=spec.fitted_methods,membership_sidecars=spec.membership_sidecars,separation=spec.separation)
    work,store,_=open_store(spec.evaluation,config,roots,progress,extension=extension,projection=_projection(spec))
    try:
        store.seal_evaluation_labels()
        if spec.fitted_methods:
            from .methods import _fit_all,_run_objects,_view
            from .membership import inspect_imports
            fitted,_,_,uncertainties=_fit_all(store,extension,[],[])
            store.policy_prior_membership=inspect_imports(store,fitted)
            runs=_run_objects(extension,fitted)
            roots_by_variant={key:v['definition']['run'] for key,v in fitted.items()}
            store.spec=_view(spec.evaluation,runs=tuple(runs))
            store.policy_uncertainties=uncertainties
            if phase!='selection': store.unseal_evaluation_labels(roots_by_variant)
        elif phase!='selection': store.unseal_evaluation_labels({})
        yield PolicyStore(spec,config,limits,work,store,phase=phase)
    finally: work.close()
