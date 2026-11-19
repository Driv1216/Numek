"""Policy reconstruction reuses CG3 selection, revisions and typed CG4 evidence."""
from contextlib import contextmanager
from dataclasses import replace
import hashlib
import copy
import json
from pathlib import Path
from types import SimpleNamespace

from . import compat
from .contracts import EvaluationError,PredictionRunSpec,digest
from .history_contracts import LongitudinalSpec,instant
from .history_storage import Catalog,file_lock,serialized
from .sources import rows


def identity_role(roles,unit):
    """CG5 retained role of a unit from identity alone (seeded whole-unit hash); None for column roles.

    Shared by role assignment and the G.8 reserve claim, so both always agree.
    """
    if roles.column or roles.partitions:return None
    token=int(hashlib.sha256(json.dumps([roles.namespace,roles.seed,unit],separators=(',',':')).encode()).hexdigest(),16)/2**256
    cumulative=0.
    for r in ('F','S','C','E'):
        cumulative+=roles.proportions.get(r,0)
        if token<cumulative:return r
    return None


def _roles(store,spec):
    """Use CG2's role interpretation and hash convention on immutable keys."""
    con=store.con
    for run,table in store.run_tables.items():
        con.execute('CREATE OR REPLACE TEMP TABLE policy_role_assignment(event_key VARCHAR,role VARCHAR)')
        assignment=[]; partitions={}
        if spec.roles.partitions:
            raise EvaluationError('Retained policy roles use a retained role field or seeded whole-unit proportions; live partition sources are unavailable.','policy_history_partition')
        for event,entity,context in rows(con,f'SELECT event_key,entity_key,history_context FROM {table} ORDER BY event_key'):
            if spec.roles.column: role=spec.roles.values.get(json.loads(context or '{}').get(spec.roles.column))
            else:
                unit=entity if spec.roles.unit=='entity' else event
                if unit is None: raise EvaluationError('Retained entity separation requires entity keys.','entity_keys_required')
                role=identity_role(spec.roles,unit)
            assignment.append((event,role))
            if len(assignment)>=512: con.executemany('INSERT INTO policy_role_assignment VALUES (?,?)',assignment); assignment=[]
        if assignment: con.executemany('INSERT INTO policy_role_assignment VALUES (?,?)',assignment)
        con.execute(f'UPDATE {table} b SET cg_role=a.role FROM policy_role_assignment a WHERE a.event_key=b.event_key')


@contextmanager
def prepared_policy_history(spec,config,limits,roots,progress=None,*,phase='selection'):
    from .history_selection import load_history,select_history,context_links,HistoryStore
    from .investigation_history import visible_heads,captured_outcome_columns,captured_context_outcome_columns
    from .policy_store import PolicyStore
    root=Path(spec.history['workspace_path']).absolute(); catalog=Catalog(root)
    from .history_storage import authority_file
    with compat.secure_open(authority_file(root),roots): pass
    selection=LongitudinalSpec.from_dict(spec.history['selection'])
    if selection.catalog_sequence is None: selection=replace(selection,catalog_sequence=catalog.status()['catalog_sequence'])
    selection=replace(selection,config=config)
    work=compat.workspace(config,512*1024**2,progress)
    try:
        with file_lock(catalog.objects_lock,False):
            variants,scan=load_history(work,root,selection,selection.catalog_sequence)
            cutoff=select_history(work,selection,selection.as_of)
            context_links(work,root,selection.catalog_sequence,selection.max_scan_records)
            con=work.con; tables={}; native=[]; uncertainty={}
            con.execute('CREATE TABLE policy_window_members(event_key VARCHAR,window_id VARCHAR)')
            source_objects=set()
            for variant,metadata in variants.items():
                parts=[]; uncertainty_parts=[]
                for window in selection.windows:
                    current=HistoryStore(work,selection,variant,metadata,window,cutoff); native.append(current)
                    parts.append(current.table); uncertainty_parts.append(current.uncertainty_table)
                    con.execute(f'INSERT INTO policy_window_members SELECT event_key,? FROM {current.table}',[window.id])
                table='policy_history_'+digest(variant)[:12]
                # Overlapping windows are scopes, never duplicated observations.
                con.execute(f'CREATE TABLE {table} AS SELECT * FROM ('+' UNION ALL '.join('SELECT * FROM '+t for t in parts)+') QUALIFY row_number() OVER(PARTITION BY event_key ORDER BY ordinal)=1')
                tables[variant]=table
                u='policy_history_uncertainty_'+digest(variant)[:12]
                con.execute(f'CREATE TABLE {u} AS '+' UNION '.join('SELECT * FROM '+t for t in uncertainty_parts)); uncertainty[variant]=u
            base=native[0]; base.run_tables=tables; base.policy_metadata=variants
            base.spec=SimpleNamespace(task=base.spec.task,runs=tuple(PredictionRunSpec.from_dict(m['run']) for m in variants.values()),cohorts=selection.cohorts,sources=base.spec.sources)
            base.roots=roots; base.policy_uncertainties=uncertainty
            base.representations={k:v for s in native for k,v in s.representations.items()}
            base.input_facts={k:v for s in native for k,v in s.input_facts.items()}
            base.run_facts={k:next(s.run_facts[k] for s in native if k in s.run_facts) for k in tables}
            _roles(base,spec)
            con.execute('CREATE TABLE policy_retained_features(event_key VARCHAR,view_id VARCHAR,payload VARCHAR)')
            feature_sequence=selection.prediction_catalog_sequence or selection.catalog_sequence
            feature_asof=instant(selection.prediction_as_of or selection.as_of)
            needed={v.id:v for v in spec.features}; known=set(); aliases={}; exposed=set()
            needed_predictions={r[0] for table in tables.values() for r in con.execute(f'SELECT DISTINCT history_fact FROM {table}').fetchall()}
            if len(needed_predictions)*4096>min(limits.materialized_bytes,config.max_rss_bytes//4): raise EvaluationError('Retained policy metadata exceeds materialization admission.','policy_memory_admission')
            predictions={f['fact_digest']:f for f in catalog.iter_facts('prediction',sequence=feature_sequence,fact_digests=needed_predictions,max_records=selection.max_scan_records,check=work.check)}
            owners={}; owners_by_run={}
            for run_id,table in tables.items():
                owners_by_run[run_id]={}
                for event,fact in rows(con,f'SELECT event_key,history_fact FROM {table}'):
                    prediction=predictions.get(fact)
                    if prediction:
                        owners[event]=prediction
                        owners_by_run[run_id][event]=prediction
                        source_objects.add(prediction['object_id'])
            metadata=[]; outcome_origins=set(); context_origins=set()
            for fact in catalog.iter_facts('capture_metadata',check=work.check,max_records=selection.max_scan_records):
                packet=fact['payload']
                if not set(variants).intersection(packet.get('variants',{})): continue
                metadata.append(fact); source_objects.add(fact['object_id'])
                for variant in variants:
                    outcome_origins.update(captured_outcome_columns(packet,variant))
                    context_origins.update(captured_context_outcome_columns(packet,variant))
                if packet.get('batch',{}).get('operation') in {'evaluate','study'}:
                    exposed.update(catalog.prediction_digests_in_operation(fact['identity'][0]))
            heads=visible_heads(catalog,'feature',feature_sequence,feature_asof,selection.namespace,work.check)
            by_owner={}
            for fact in heads:
                payload=fact['payload']; view=payload['view']['id']
                if view in needed: by_owner.setdefault((view,payload['owner_key']),[]).append(fact)
            for event,prediction in owners.items():
                for viewid,view in needed.items():
                    target=spec.run_bindings.get(view.run or next(iter(tables)),view.run or next(iter(tables)))
                    prediction=owners_by_run.get(target,{}).get(event)
                    if prediction is None: continue
                    owner=event if view.owner=='opportunity' else digest([prediction['key'],prediction['revision']])
                    matches=by_owner.get((viewid,owner),[])
                    if len(matches)!=1: continue
                    fact=matches[0]; payload=fact['payload']; retained=payload['view']
                    if retained.get('information_cutoff')!=view.to_dict().get('information_cutoff'): raise EvaluationError('Retained cutoff semantics differ.','feature_semantics_changed')
                    for field in view.fields:
                        declaration=next((f for f in retained['fields'] if f['id']==field.id),None)
                        if declaration!=field.to_dict(): raise EvaluationError('Typed retained field semantics differ.','feature_semantics_changed')
                        source=payload.get('source',{})
                        if (source.get('sha256'),source.get('bytes'),field.column) in outcome_origins or field.column in context_origins:
                            known.add(viewid+'.'+field.id)
                    known.update(payload.get('known_outcome_fields',[])); source_objects.add(fact['object_id'])
                    con.execute('INSERT INTO policy_retained_features VALUES (?,?,?)',[event,viewid,json.dumps(payload)])
            for fact in catalog.iter_facts('prediction_source_identity',sequence=feature_sequence,check=work.check,max_records=selection.max_scan_records):
                p=fact['payload']; event=p.get('opportunity_key')
                if event in owners:
                    aliases.setdefault(event,[]).append((p['source'],p['original_event_key'],p.get('original_entity_key'))); source_objects.add(fact['object_id'])
            # Every reconstructed input and authority record participates in deletion.
            source_objects.update(catalog.object_ids_for_fact_digests([d for d, in rows(con,'SELECT DISTINCT fact_digest FROM hf')]))
            history={'instance_id':catalog.instance_id,'workspace_path':str(root),'catalog_sequence':selection.catalog_sequence,
                     'method_digests':{k:v.get('method_digests',[]) for k,v in variants.items()},
                     'selection':selection.to_dict(),'source_objects':sorted(source_objects),'source_aliases':aliases,
                     'known_exposed_events':[event for event,p in owners.items() if p['fact_digest'] in exposed],
                     'scan':scan,'windows':[w.to_dict() for w in selection.windows]}
            representation_heads=visible_heads(catalog,'representation',feature_sequence,feature_asof,selection.namespace,work.check) if spec.region_representations else []
            def retained_representation(rep,events):
                import numpy as np
                target=spec.run_bindings.get(rep.run or next(iter(tables)),rep.run or next(iter(tables)))
                wanted=[f for f in representation_heads if f['payload']['representation']==rep.id and f['payload']['variant']==target]
                mapping={f['payload']['owner_key']:f for f in wanted}; dimensions=rep.dimensions or (wanted[0]['payload']['dimensions'] if wanted else None)
                if not dimensions: raise EvaluationError('Representation dimensions were not retained.','representation_not_retained')
                policy.budget.materialize(len(events)*dimensions*8*2)
                matrix=np.full((len(events),dimensions),np.nan); available=np.zeros(len(events),bool); reasons=['representation_not_retained']*len(events)
                matrices={}
                if True:
                    for i,event in enumerate(events):
                        pred=owners_by_run.get(target,{}).get(event['event_key']); fact=mapping.get(digest([pred['key'],pred['revision']])) if pred else None
                        if not fact or fact['payload']['state']!='observed': continue
                        payload=fact['payload']; original=payload['spec']
                        if rep.model_digest and original.get('model_digest')!=rep.model_digest or original.get('normalization','none')!=rep.normalization: raise EvaluationError('Retained representation contract differs.','representation_changed')
                        location=catalog.vector_location(payload['vector_digest'])
                        if location is None: raise EvaluationError('Retained vector unavailable.','historical_evidence_unavailable')
                        if location['object_id'] not in matrices: matrices[location['object_id']]=catalog.vector_matrix(location)
                        vectors=matrices[location['object_id']]; vector=vectors[location['row_index']]
                        if vector.shape!=(dimensions,) or hashlib.sha256(vectors.dtype.str.encode()+vector.tobytes()).hexdigest()!=payload['vector_digest']: raise EvaluationError('Retained vector changed.','historical_evidence_changed')
                        clock=event['inputs'].get(rep.run or policy.anchor,{}).get('prediction_tick'); tick,state=payload.get('content_available') or (None,'undeclared')
                        admitted=original.get('availability')=='at_decision' or payload.get('content_availability_declaration')=='at_decision' or state=='valid' and tick is not None and clock is not None and tick<=clock
                        if original.get('kind') in {'e5_text','dinov2_image'}:
                            cell=event['features'].get(original['field']); admitted=admitted and cell is not None and cell['state']=='observed'
                        if not admitted: reasons[i]='content_unavailable_at_cutoff'; continue
                        matrix[i]=vector; available[i]=True; reasons[i]=''
                        source_objects.update((fact['object_id'],location['object_id']))
                history['source_objects']=sorted(source_objects)
                return {'id':rep.id,'vectors':matrix,'available':available,'reason':reasons,'normalization':rep.normalization}
            base.policy_retained_representation=retained_representation
            policy=PolicyStore(spec,config,limits,work,base,phase=phase,history=history)
            policy.budget.reserve('historical_metadata',len(needed_predictions)*4096)
            policy.known_outcome_features.update(known)
            yield policy
    finally: work.close()


def _policy_history_worker(application,study,config,roots,reservation,expected,*,progress=None):
    from .policy_runtime import Interpreter
    from .policy_metrics import metric_result,public_stat,atom,constraint_state,scoped as metric_scoped
    from .policies import make_result
    with prepared_policy_history(application.input,config,application.limits,roots,progress,phase='history') as p:
        if p.fingerprint!=expected: raise EvaluationError('Historical policy snapshot changed after reservation.','stale_confirmation')
        policy=p.bind_policy(application.policy); study=replace(study,candidates=(policy,))
        p.project((policy,))
        events,records=p.materialize(policy.run,application.role)
        actions,trace=Interpreter(policy,p.budget).apply(events,batches=p.input.batches)
        windows=p.history['windows']; metrics={}; summaries=[]; constraint_ledger=[]; worst=[]
        definitions={m.id:m for m in study.objectives}
        for constraint in study.constraints:
            if constraint.metric.id in definitions and definitions[constraint.metric.id]!=constraint.metric:
                raise EvaluationError('A historical metric identity has inconsistent definitions.','policy_metric_identity')
            definitions[constraint.metric.id]=constraint.metric
        for window in windows:
            for metric in definitions.values():
                # Windowing intersects the declared cohort/region restriction.
                # Filter once; the shared reducer still owns all eligibility.
                indices=[i for i,r in enumerate(records) if window['id'] in r.get('_windows',[]) and metric_scoped(metric,events[i],r)]
                scoped=replace(metric,scope='window:'+window['id'],id=metric.id+'@'+window['id'])
                result=public_stat(metric_result(scoped,[events[i] for i in indices],[records[i] for i in indices],[actions[i] for i in indices],policy,study,p.budget))
                result['population_definition']={'window':window['id'],'restriction':metric.scope}
                result['definition_digest']=digest({'metric':metric.to_dict(),'window':window['id']})
                metrics[scoped.id]=result
                if metric in study.objectives:
                    summaries.append({'window':window['id'],'metric_id':metric.id,'metric':metric.metric,'scope':metric.scope,'evidence':result})
            for constraint in study.constraints:
                value=metrics[constraint.metric.id+'@'+window['id']]
                constraint_ledger.append({**constraint_state(constraint,value),'id':constraint.id+'@'+window['id'],
                    'constraint_id':constraint.id,'window':window['id'],'metric_id':constraint.metric.id,
                    'metric':constraint.metric.metric,'scope':constraint.metric.scope,'operator':constraint.operator,
                    'bound':constraint.bound,'support':value['denominator'],'minimum_support':constraint.minimum_support,
                    'evidence_basis':constraint.metric.basis,'definition_digest':value['definition_digest']})
        for metric in definitions.values():
            values=[metrics[metric.id+'@'+w['id']] for w in windows]
            defined=bool(values) and all(v['value_state']=='finite' for v in values)
            value=(max if metric.direction=='minimize' else min)(v['value'] for v in values) if defined else None
            worst.append({'metric_id':metric.id,'metric':metric.metric,'scope':metric.scope,'basis':metric.basis,
                'value':value,'value_state':'finite' if defined else 'undefined',
                'windows':[w['id'] for w,v in zip(windows,values) if defined and v['value']==value],
                'window_supports':{w['id']:v['denominator'] for w,v in zip(windows,values)}})
        comparisons=[]
        for left,right in zip(windows,windows[1:]):
            for metric in study.objectives:
                a=metrics[metric.id+'@'+left['id']]; b=metrics[metric.id+'@'+right['id']]
                value=b['value']-a['value'] if a['value_state']==b['value_state']=='finite' else None
                comparisons.append({'reference':left['id'],'current':right['id'],'metric_id':metric.id,'metric':metric.metric,
                                    'value':value,'value_state':'finite' if value is not None else 'undefined',
                                    'reference_support':a['denominator'],'current_support':b['denominator'],
                                    'interpretation':'Retrospective change under one frozen policy; no prospective or causal effectiveness claim.'})
        applicability=[]
        for window in windows:
            indices=[i for i,r in enumerate(records) if window['id'] in r.get('_windows',[])]
            applicability.append({'window':window['id'],'planned':len(indices),'observed_outcomes':sum(bool(records[i].get('outcome_valid')) for i in indices),
                                  'issued':sum(actions[i]['state']=='issued' for i in indices),'deferred':sum(actions[i]['state']=='deferred' for i in indices),
                                  'unavailable':sum(actions[i]['state']=='unavailable' for i in indices),
                                  'region_unavailable':{r['artifact']['artifact_digest']:sum(events[i]['regions'].get(r['artifact']['artifact_digest'])=='unavailable' for i in indices) for r in p.input.regions}})
        # Feed the existing CG3 drift and compatible mix decompositions policy
        # action relations and registered additive contributions.
        from .longitudinal import _mix,_drift
        from .analytics import literal
        views={}; mix=[]; drift=[]
        con=p.con; base=p.store.run_tables[p.anchor]
        con.execute('CREATE TABLE policy_history_actions(event_key VARCHAR,decision VARCHAR,point DOUBLE)')
        compat.insert_rows(con,'policy_history_actions',[(e['event_key'],a.get('value') if policy.task.kind!='regression' and a['state']=='issued' else None,a.get('value') if policy.task.kind=='regression' and a['state']=='issued' else None) for e,a in zip(events,actions)])
        con.execute('CREATE TABLE policy_history_losses(ordinal BIGINT,event_key VARCHAR,metric VARCHAR,eligible BOOLEAN,defined BOOLEAN,value DOUBLE)')
        additive={m.id:m for m in study.objectives if all(metrics[m.id+'@'+w['id']]['statistic_kind']=='mean' for w in windows)}
        for metric in additive.values():
            data=[]
            for event,record,action in zip(events,records,actions):
                p.budget.charge('contribution_cells')
                eligible,value,_=atom(metric,event,record,action,policy,study)
                eligible=eligible and metric_scoped(metric,event,record)
                data.append((record['ordinal'],event['event_key'],metric.id,eligible,value is not None,value))
                if len(data)>=512: compat.insert_rows(con,'policy_history_losses',data);data=[]
            if data: compat.insert_rows(con,'policy_history_losses',data)
        for window in windows:
            table='policy_stress_'+digest(window['id'])[:16]
            con.execute(f'CREATE TABLE {table} AS SELECT b.* REPLACE(a.decision AS decision,a.point AS point) FROM {base} b JOIN policy_history_actions a USING(event_key) WHERE b.event_key IN (SELECT event_key FROM policy_window_members WHERE window_id=?)',[window['id']])
            view=SimpleNamespace(**vars(p.store));view.table=table;view.run=p.runs[policy.run]
            target=p.input.run_bindings.get(policy.run,policy.run);view.metadata=p.store.policy_metadata[target]
            view.loss_table='policy_history_losses';view.extra_metadata=additive
            views[window['id']]=view
        selection=LongitudinalSpec.from_dict(p.history['selection'])
        for left,right in zip(windows,windows[1:]):
            a,b=views[left['id']],views[right['id']];edge=SimpleNamespace(id='policy_'+left['id']+'_'+right['id'])
            for metric in additive:
                mix.extend({'reference':left['id'],'current':right['id'],**record} for record in _mix(a,b,metric,selection.cohorts))
            drift.extend(_drift(a,b,selection,edge))
        disagreement=sum(a['state']=='issued' and a.get('value')!=e['inputs'].get(policy.run,{}).get('point' if policy.task.kind=='regression' else 'decision') for e,a in zip(events,actions))
        row={'policy_digest':policy.policy_digest,'metrics':metrics,'constraints':constraint_ledger,'observed_feasibility':'historical_descriptive','baseline':False,'trace':trace}
        panel={'stage':'historical','candidates':[row],'windows':windows,'timeline':summaries,'comparisons':comparisons,
               'constraint_ledger':constraint_ledger,'worst_window_evidence':worst,
               'applicability':applicability,'reservation':reservation,'frozen_policy_across_windows':True,
               'mix_decompositions':mix,'drift':drift,'issued_action_disagreement_with_supplied':disagreement,
               'interpretation':'One immutable policy replayed on retained historical evidence. Reselection is a separate development study.'}
        result=make_result(study,config,p,panel,{policy.policy_digest:policy.to_dict()},private_extra={'application_spec':application.to_dict()})
        p.verify(); return result


def analyze_policy_history(spec,config=None,*,allowed_roots=None,workspace=None,request_id=None,progress=None,cancel=None,_deadline=None):
    from .policy_contracts import PolicyApplicationSpec
    from .policies import arguments,workspace_for,_application_study,_identity_worker,_reserve,_finish
    import time
    spec,config,roots=arguments(spec,config,allowed_roots,PolicyApplicationSpec)
    if spec.input.history is None: raise EvaluationError('Policy history needs retained immutable evidence.','policy_history_required')
    workspace=workspace_for(spec.input,workspace); study=_application_study(spec); deadline=_deadline or time.monotonic()+config.max_seconds
    identity=compat.supervise(_identity_worker,(spec.input,config,spec.limits,roots,spec.role,'history'),config,progress=progress,cancel=cancel,deadline=deadline).to_dict()
    reservation=_reserve('outcome_disclosure',identity['population'],spec.input,workspace,config,request_id=request_id,cancel=cancel,deadline=deadline,
                         metadata={'purpose':'policy_historical_replay','identity_policy':'canonical_and_original_source_aliases_v1','local_identity_scope':identity['population']['identity_scope']})
    result=compat.supervise(_policy_history_worker,(spec,study,config,roots,reservation,identity['fingerprint']),replace(config,result_bytes=config.private_bytes+config.result_bytes),progress=progress,cancel=cancel,deadline=deadline)
    return _finish(result,config)


def policy_restatement(prior,as_of,reason):
    from .policy_result import PolicyResult
    from .policy_contracts import PolicyApplicationSpec
    PolicyResult.from_dict(prior.to_private_dict(),private=prior.private)
    if not reason or prior.data['policy']['stage']!='historical': raise EvaluationError('Outcome restatement requires a retained historical policy and reason.')
    spec=PolicyApplicationSpec.from_dict(prior.private['application_spec'])
    history=copy.deepcopy(spec.input.history); selection=history['selection']; binding=prior.private['history_binding']
    selection.update(prediction_catalog_sequence=selection.get('prediction_catalog_sequence') or binding['catalog_sequence'],
                     prediction_as_of=selection.get('prediction_as_of') or selection.get('as_of'),
                     catalog_sequence=Catalog(history['workspace_path']).status()['catalog_sequence'],as_of=as_of,outcome_only=True)
    return replace(spec,input=replace(spec.input,history=history),name='Outcome-only policy restatement: '+reason)
