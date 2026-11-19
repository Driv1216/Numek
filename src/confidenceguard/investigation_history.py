"""CG4 immutable enrichment and historical adapters; CG3 selection stays authoritative."""
from contextlib import contextmanager
from dataclasses import replace
import copy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import numpy as np
from .contracts import EvaluationError,EvaluationConfig,digest,PredictionRunSpec
from .feature_contracts import FeatureEnrichmentSpec
from .features import normalize,missing_cell,apply_availability,outcome_bound_fields,information_cutoff,FEATURE_TIME_POLICY
from .history_contracts import LongitudinalSpec,instant,now
from .history_storage import Catalog,EvidenceWriter,file_lock
from .sources import rows,key,records
from . import compat


def envelope(kind,identity,payload,*,revision='initial',predecessor=None,available_ns=None,authority='supplied',reason=None):
    result={'kind':kind,'key':digest(identity),'identity':identity,'revision':revision,'predecessor':predecessor,
            'available_ns':str(available_ns) if available_ns is not None else None,'authority':authority,'reason':reason,'payload':payload}
    return {**result,'fact_digest':digest(result)}


def captured_outcome_columns(metadata,variant):
    """Positive origin evidence from retained metadata, including old captures.

    An absent marker is not proof of independence. Match original variant and
    immutable source bytes, rather than reusing a source ID from another batch.
    """
    if variant not in metadata.get('variants',{}):return set()
    evaluation=metadata.get('batch',{}).get('evaluation',{})
    evaluation=evaluation.get('evaluation',evaluation)
    outcome=evaluation.get('outcomes');runs=evaluation.get('runs',[])
    if not outcome and len(runs)==1 and runs[0].get('inline_outcome'):
        outcome={'source':runs[0]['source'],'column':runs[0]['inline_outcome']}
    if not outcome:return set()
    source=metadata.get('sources',{}).get(outcome['source'],{})
    if not source.get('sha256') or type(source.get('bytes')) is not int:return set()
    return {(source['sha256'],source['bytes'],column) for column in (outcome.get('column'),outcome.get('status_column')) if column}


def captured_context_outcome_columns(metadata,variant):
    """Legacy context fallback is positive only when every possible source agrees."""
    origins=captured_outcome_columns(metadata,variant)
    if not origins:return set()
    evaluation=metadata['batch']['evaluation'];evaluation=evaluation.get('evaluation',evaluation)
    sources=metadata.get('sources',{});runs=evaluation.get('runs',[])
    outcome=evaluation.get('outcomes') or {'source':runs[0]['source']}
    context_source=(evaluation.get('context') or {}).get('source',outcome['source'])
    identities={(sha,size) for sha,size,_ in origins}
    # Capture used canonical context first, then prediction-row fallback. Old
    # metadata does not identify every fallback per cell; do not infer an origin
    # from a matching column name or an unrelated run/source ID alone.
    possible=[sources.get(context_source,{})]+[sources.get(run['source'],{}) for run in runs]
    if not runs or any((source.get('sha256'),source.get('bytes')) not in identities for source in possible):return set()
    return {column for _,_,column in origins}


def legacy_source_origin(metadata,variant,target,prediction):
    """Recover only unambiguous single-run identities actually retained by CG3."""
    if variant not in metadata.get('variants',{}):return None
    batch=metadata.get('batch',{});evaluation=batch.get('evaluation',{});evaluation=evaluation.get('evaluation',evaluation)
    runs=evaluation.get('runs',[])
    if len(runs)!=1 or not runs[0].get('key_columns'):return None
    run=runs[0];bindings=[b for b in batch.get('bindings',[]) if b.get('run')==run['id']]
    if len(bindings)!=1:return None
    binding=bindings[0]
    if tuple(binding.get('event_columns') or run['key_columns'])!=tuple(run['key_columns']):return None
    if not isinstance(target,list) or len(target)!=4 or target[0]!=batch.get('namespace') or target[2]!=batch.get('outcome_definition_version') or not isinstance(target[1],list) or len(target[1])!=len(run['key_columns']) or any(type(v) is not str or not v for v in target[1]):return None
    event=json.dumps(target[1],ensure_ascii=True,separators=(',',':'));entity=prediction.get('normalized',{}).get('entity_key')
    if entity is not None and binding.get('entity_namespace') is not None:
        try:wrapped=json.loads(entity)
        except (TypeError,ValueError):return None
        if not isinstance(wrapped,list) or len(wrapped)!=2 or wrapped[0]!=binding['entity_namespace'] or type(wrapped[1]) is not str:return None
        entity=wrapped[1]
    sources=[];outcome=evaluation.get('outcomes')
    for sid in dict.fromkeys([run['source']]+([outcome['source']] if outcome else [])):
        info=metadata.get('sources',{}).get(sid,{})
        if not info.get('path') or not isinstance(info.get('signature'),list) or len(info['signature'])<2:return None
        sources.append(({'path':info['path'],'signature':info['signature'][:2]},event,entity))
    return {'event':event,'entity':entity,'sources':sources}


def cells_from_row(view,row):
    values={}
    for field in view.fields:
        clock=field.available_at or view.available_at
        available,state=compat.clock(row.get(clock.column),clock) if clock else (None,'undeclared')
        effective,_=compat.clock(row.get(field.effective_at.column),field.effective_at) if field.effective_at else (None,'undeclared')
        values[field.id]=normalize(row.get(field.column),field,available_ns=available,effective_ns=effective,availability_state=state)
    return values


def retained_cutoff(view,payload,raw=None):
    """A distinct declared cutoff is never replaced by prediction time."""
    if view.information_cutoff is None:return None,None
    packet=information_cutoff(view,raw) if payload is None else payload.get('information_cutoff')
    if not isinstance(packet,dict) or packet.get('policy')!=FEATURE_TIME_POLICY or packet.get('clock')!=view.information_cutoff.to_dict():
        return None,'not_retained'
    if packet.get('state')!='valid':return None,packet.get('state') or 'invalid'
    tick=packet.get('tick_ns')
    if not isinstance(tick,str):return None,'invalid'
    try:
        parsed=int(tick)
        return (parsed,'valid') if str(parsed)==tick else (None,'invalid')
    except (ValueError,TypeError):return None,'invalid'


def capture_typed(capture,store,run,base,variant,mapping):
    """Called only for explicit v2 retention, before the existing atomic commit."""
    from .representations import supplied,encode
    writer=capture.writer;batch=capture.batch
    owner_rows=store.con.execute(f'SELECT event_key,opportunity_key,prediction_key,prediction_revision FROM {mapping} ORDER BY event_key').fetchall()
    keys=[r[0] for r in owner_rows];owners={r[0]:r for r in owner_rows}
    entities=dict(rows(store.con,f'SELECT event_key,entity_key FROM {store.run_tables[run.id]}',batch=512))
    for event,opportunity,prediction,revision in owner_rows:
        writer.add('prediction_origin',[prediction,revision],{'namespace':batch.namespace,'variant':variant,'opportunity_key':opportunity,
            'original_event_key':event,'original_entity_key':entities.get(event),'prediction_key':prediction,'prediction_revision':revision})
        for sid in dict.fromkeys((base.source,store.spec.outcomes.source if store.spec.outcomes else base.source)):
            source=store.sources[sid];anchor={'path':source['path'],'signature':source['signature'][:2]}
            writer.add('prediction_source_identity',[prediction,revision,digest(anchor)],{'namespace':batch.namespace,'variant':variant,
                'opportunity_key':opportunity,'original_event_key':event,'original_entity_key':entities.get(event),'source':anchor})
    views=[v for v in batch.feature_views if (v.run or batch.base.runs[0].id)==base.id]
    known_outcomes=outcome_bound_fields(batch.base,views,store.sources)
    feature_cells={};source_maps={}
    for view in views:
        source=view.source or base.source;columns=view.key_columns or base.key_columns
        source_id=(source,columns)
        if source_id not in source_maps:
            source_maps[source_id]={}
            for _,raw in rows(store.con,f'SELECT ordinal,payload FROM {store.tables[source]}'):
                raw=json.loads(raw);event=key(raw,columns,None)
                if event is None or event in source_maps[source_id]:raise EvaluationError('Typed retention requires unique explicit join keys.','feature_key_conflict')
                source_maps[source_id][event]=raw
        by_key=source_maps[source_id]
        def feature_envelopes():
            for event in keys:
                _,opportunity,prediction,revision=owners[event]
                row=by_key.get(event);values=cells_from_row(view,row) if row else {f.id:missing_cell(f.kind) for f in view.fields}
                for f in view.fields:feature_cells.setdefault(view.id+'.'+f.id,[]).append(values[f.id])
                owner=opportunity if view.owner=='opportunity' else digest([prediction,revision])
                yield envelope('feature',[batch.namespace,view.id,owner],
                    {'namespace':batch.namespace,'view':view.to_dict(),'owner':view.owner,'owner_key':owner,
                     'opportunity_key':opportunity,'variant':variant if view.owner=='prediction_revision' else None,
                     'values':values,'source':{k:store.sources[source].get(k) for k in ('sha256','bytes')},
                     'normalization':FEATURE_TIME_POLICY if view.information_cutoff else 'typed_feature_v1',
                     **({'information_cutoff':information_cutoff(view,row)} if view.information_cutoff else {}),
                     **({'known_outcome_fields':sorted(known_outcomes.intersection(view.id+'.'+f.id for f in view.fields))} if known_outcomes.intersection(view.id+'.'+f.id for f in view.fields) else {})},
                    revision=view.revision,predecessor=view.predecessor,authority=view.authority,reason=view.reason)
        writer.add_features(feature_envelopes(),tuple(f.id for f in view.fields))
    for spec in batch.discovery_representations:
        if (spec.run or batch.base.runs[0].id)!=base.id:continue
        if spec.kind=='retained':raise EvaluationError('An ingestion batch cannot import an unbound retained representation.')
        if spec.kind=='supplied':rep,files=supplied(spec,keys,store.work,store.config,store.roots)
        else:
            from .investigation_contracts import InvestigationLimits
            rep,files=encode(spec,keys,feature_cells,store.work,store.config,InvestigationLimits(),store.roots,Path(store.spec.sources[0].path).parent)
        for info in files.values():compat.capture(info['path'],store.roots,expected=info)
        available=np.flatnonzero(rep['available']);locations=writer.add_vectors(rep['vectors'][available]);by_index=dict(zip(available,locations))
        values=[]
        for i,event in enumerate(keys):
            _,opportunity,prediction,revision=owners[event];owner=digest([prediction,revision])
            payload={'namespace':batch.namespace,'representation':spec.id,'owner':'prediction_revision','owner_key':owner,
                     'opportunity_key':opportunity,'variant':variant,'values':{},'state':'observed' if i in by_index else 'unavailable',
                     'reason':rep['reason'][i],'spec':spec.to_dict(),'provenance':rep['provenance'],
                     'content_available':rep['availability'].get(event),'dimensions':rep['vectors'].shape[1],
                     'vector_digest':by_index[i]['vector_digest'] if i in by_index else None}
            if spec.kind in {'e5_text','dinov2_image'}:
                view_id=spec.field.split('.',1)[0]
                content_view=next(v for v in views if v.id==view_id)
                payload['content_availability_declaration']=content_view.availability
                if content_view.information_cutoff:
                    source=content_view.source or base.source;columns=content_view.key_columns or base.key_columns
                    payload['content_information_cutoff']=information_cutoff(content_view,source_maps[(source,columns)].get(event))
            # Large publisher manifests are retained once, not once per vector.
            payload['provenance']={'identity':digest(rep['provenance'])}
            values.append(envelope('representation',[batch.namespace,spec.id,owner],payload))
        writer.add('representation_metadata',[batch.namespace,spec.id,variant,digest(rep['provenance'])],
                   {'namespace':batch.namespace,'representation':spec.id,'variant':variant,'provenance':rep['provenance']})
        writer.add_features(values,())


def enrich_worker(specification,config,roots,root,stage,operation,workspace_config,*,progress=None):
    from .result import Inspection
    specification=FeatureEnrichmentSpec.from_dict(specification);view=specification.view
    work=compat.workspace(config,128*1024**2,progress)
    try:
        catalog=Catalog(root);source=specification.source;info,_,_=compat.capture(source.path,roots)
        # The source reader owns a secure immutable snapshot, as for predictions.
        import shutil
        snapshot=work.root/('enrichment.'+source.format)
        with compat.secure_open(source.path,roots) as (stream,_),snapshot.open('xb') as output:shutil.copyfileobj(stream,output,1024**2)
        compat.capture(source.path,roots,expected=info)
        with snapshot.open('rb') as stream:
            if hashlib.file_digest(stream,'sha256').hexdigest()!=info['sha256']:raise EvaluationError('Enrichment changed during capture.','source_changed')
        opportunities={f['key']:f for f in catalog.iter_facts('opportunity',check=work.check) if f['payload'].get('namespace')==specification.namespace}
        predictions={f['fact_digest']:f for f in catalog.iter_facts('prediction',check=work.check) if f['payload'].get('namespace')==specification.namespace}
        writer=EvidenceWriter(stage,workspace_config,operation,work.check);seen=set();count=0
        def incoming():
            nonlocal count
            for location,row in records(snapshot,source,config):
                if row is None:continue
                opportunity=row.get(specification.opportunity_column);fact=opportunities.get(opportunity)
                if fact is None:raise EvaluationError('Enrichment references an unknown opportunity in the declared namespace.','feature_owner_unknown')
                variant=None;owner=opportunity;dependencies=[fact['fact_digest']]
                if view.owner=='prediction_revision':
                    prediction=predictions.get(row.get(specification.prediction_revision_column))
                    if prediction is None or prediction['payload']['opportunity_key']!=opportunity or prediction['payload']['variant']!=view.run:raise EvaluationError('Enrichment prediction ownership differs.','feature_owner_unknown')
                    variant=prediction['payload']['variant'];owner=digest([prediction['key'],prediction['revision']]);dependencies.append(prediction['fact_digest'])
                if owner in seen:raise EvaluationError('Enrichment owner occurs more than once.','feature_key_conflict')
                seen.add(owner);count+=1
                predecessor=row.get(specification.predecessor_column) if specification.predecessor_column else view.predecessor
                yield envelope('feature',[specification.namespace,view.id,owner],
                    {'namespace':specification.namespace,'view':view.to_dict(),'owner':view.owner,'owner_key':owner,'opportunity_key':opportunity,
                     'variant':variant,'values':cells_from_row(view,row),'source':{k:info.get(k) for k in ('sha256','bytes')},
                     'normalization':FEATURE_TIME_POLICY if view.information_cutoff else 'typed_feature_v1',
                     **({'information_cutoff':information_cutoff(view,row)} if view.information_cutoff else {}),
                     'depends_on_facts':dependencies,'acquired_at':specification.acquired_at},
                    revision=view.revision,predecessor=predecessor,available_ns=instant(specification.acquired_at),authority=view.authority,reason=view.reason)
                if count%512==0:work.check('typed enrichment')
        writer.add_features(incoming(),tuple(f.id for f in view.fields));writer.finish({'capture_stages':['typed_enrichment'],'source':info,'enrichment':specification.to_dict()})
        compat.capture(source.path,roots,expected=info)
        return Inspection({'prepared':count},{'status':'completed','peak_workspace_bytes':work.peak})
    finally:work.close()


def frozen_selection(spec):
    if set(spec.history)-{'workspace_path','selection'} or not {'workspace_path','selection'}<=set(spec.history):raise EvaluationError('History requires workspace_path and a LongitudinalSpec selection.')
    root=Path(spec.history['workspace_path']).absolute();catalog=Catalog(root)
    selection=LongitudinalSpec.from_dict(spec.history['selection'])
    if selection.namespace!=spec.roles.namespace:raise EvaluationError('Historical and CG4 namespaces differ.','investigation_identity')
    if selection.as_of is None and spec.as_of is None:raise EvaluationError('An explicit historical as_of is required.','history_cutoff_required')
    sequence=selection.catalog_sequence or catalog.status()['catalog_sequence']
    if sequence>catalog.status()['catalog_sequence']:raise EvaluationError('Historical catalog snapshot is unavailable.','catalog_snapshot')
    return root,replace(selection,catalog_sequence=sequence,as_of=selection.as_of or spec.as_of)


def visible_heads(catalog,kind,sequence,asof,namespace,check):
    facts={}
    for fact in catalog.iter_facts(kind,sequence=sequence,check=check):
        if fact['payload'].get('namespace')!=namespace or fact['available_ns'] is not None and int(fact['available_ns'])>asof:continue
        facts.setdefault(fact['key'],[]).append(fact)
    heads=[]
    for revisions in facts.values():
        parents={f['predecessor'] for f in revisions if f['predecessor']}
        current=[f for f in revisions if f['fact_digest'] not in parents]
        if len(current)!=1:raise EvaluationError('Historical typed evidence has competing revision heads.','feature_revision_ambiguous')
        heads.extend(current)
    return heads


@contextmanager
def prepare_history(spec,config,roots,progress,*,identity_only=False):
    from .history_selection import load_history,select_history,context_links,HistoryStore
    from .investigation import Prepared
    root,selection=frozen_selection(spec)
    from .history_storage import authority_file
    with compat.secure_open(authority_file(root),roots):pass
    selection=replace(selection,config=config)
    catalog=Catalog(root);work=compat.workspace(config,512*1024**2,progress)
    try:
        with file_lock(catalog.objects_lock,False):
            variants,scan=load_history(work,root,selection,selection.catalog_sequence)
            cutoff=select_history(work,selection,selection.as_of);context_links(work,root,selection.catalog_sequence,selection.max_scan_records)
            tables={};stores=[]
            for variant,metadata in variants.items():
                parts=[]
                for window in selection.windows:
                    store=HistoryStore(work,selection,variant,metadata,window,cutoff);stores.append(store)
                    store.con.execute(f'ALTER TABLE {store.table} ADD COLUMN cg4_period VARCHAR')
                    store.con.execute(f'UPDATE {store.table} SET cg4_period=?',[window.id]);parts.append(store.table)
                table='cg4_history_'+digest(variant)[:12]
                work.con.execute(f'CREATE TABLE {table} AS '+ ' UNION ALL '.join('SELECT * FROM '+p for p in parts))
                duplicate=work.con.execute(f'SELECT count(*)-count(DISTINCT event_key) FROM {table}').fetchone()[0]
                if duplicate:raise EvaluationError('CG4 historical periods must not duplicate opportunities.','history_period_overlap')
                work.con.execute(f'UPDATE {table} SET ordinal=ordered.n FROM (SELECT event_key,row_number() OVER(ORDER BY event_key) n FROM {table}) ordered WHERE {table}.event_key=ordered.event_key')
                tables[variant]=table
            retained_inputs={id(s):copy.deepcopy(s.input_facts) for s in stores}
            base=stores[0];base.run_tables=tables;base.spec=SimpleNamespace(task=base.spec.task,runs=tuple(PredictionRunSpec.from_dict(m['run']) for m in variants.values()),cohorts=selection.cohorts,sources=base.spec.sources)
            base.representations={k:v for s in stores for k,v in s.representations.items()}
            base.cg4_uncertainty_by_run={};base.input_facts={}
            for variant in variants:
                parts=[s for s in stores if s.variant==variant]
                uncertainty='cg4_u_'+digest(variant)[:12]
                union=' UNION ALL '.join(f'SELECT event_key,coverage,output FROM {s.uncertainty_table}' for s in parts)
                work.con.execute(f'CREATE TABLE {uncertainty} AS SELECT r.ordinal,u.event_key,u.coverage,u.output FROM ({union}) u JOIN {tables[variant]} r USING(event_key)')
                base.cg4_uncertainty_by_run[variant]=uncertainty
                sample_tables=[retained_inputs[id(s)][variant]['sample_table'] for s in parts if variant in retained_inputs[id(s)] and retained_inputs[id(s)][variant].get('sample_table')]
                if sample_tables:
                    combined='cg4_samples_'+digest(variant)[:12];work.con.execute(f'CREATE TABLE {combined} AS '+ ' UNION '.join('SELECT * FROM '+t for t in sample_tables))
                    base.input_facts[variant]={'sample_table':combined,'sample_meaning':next(retained_inputs[id(s)][variant]['sample_meaning'] for s in parts if variant in retained_inputs[id(s)])}
            base.cg4_periods=[w.id for w in selection.windows];base.run_facts={vid:{'repeated_entities':0,'context_conflicts':{},'duplicate_keys':0,'missing_keys':0,'inline_conflicts':0} for vid in variants}
            source_selection={k:v for k,v in selection.to_dict().items() if k!='config'}
            canonical=hashlib.sha256();sealed_rows=hashlib.sha256();sealed_count=0
            from .history_storage import serialized
            # Rows of sealed-reserve entities are present only under a study's G.8
            # authority. The frozen input identity is the selection as discovery saw
            # it (without them); the claimed reserve rows get their own digest.
            unit_of=lambda row:digest([selection.namespace,row.get('entity_key') or row['event_key']])
            sealed=set()
            for table in tables.values():
                units={unit_of({'entity_key':e,'event_key':k}) for k,e in rows(work.con,f'SELECT event_key,entity_key FROM {table}')}
                sealed|=catalog.sealed_reserve_units(units)
            for variant,table in sorted(tables.items()):
                cursor=work.con.cursor()
                try:
                    cursor.execute(f'SELECT * FROM {table} ORDER BY event_key');columns=[c[0] for c in cursor.description]
                    while True:
                        chunk=cursor.fetchmany(512)
                        if not chunk:break
                        for row in chunk:
                            value={k:v for k,v in zip(columns,row) if k!='ordinal'}
                            if sealed and unit_of(value) in sealed:sealed_rows.update(serialized([variant,value]));sealed_count+=1
                            else:canonical.update(serialized([variant,value]))
                        work.check('canonical historical identity')
                finally:cursor.close()
            # CG3's historical reducer lineage remains unchanged. CG4's immutable
            # admission identity cannot depend on a SQL join's physical row order.
            base.sources={'historical':{'sha256':digest({'normalization':'cg4_canonical_selected_history_v1','selection':source_selection,'selected':canonical.hexdigest()})}}
            if sealed_count:base.sources['historical'].update(sealed_reserve_sha256=sealed_rows.hexdigest(),sealed_reserve_rows=sealed_count)
            feature_sequence=selection.prediction_catalog_sequence or selection.catalog_sequence
            feature_asof=instant(selection.prediction_as_of or selection.as_of)
            feature_facts=visible_heads(catalog,'feature',feature_sequence,feature_asof,selection.namespace,work.check)
            representation_facts=visible_heads(catalog,'representation',feature_sequence,feature_asof,selection.namespace,work.check)
            source_objects={f['object_id'] for f in feature_facts if f['payload']['view']['id'] in {v.id for v in spec.features}}
            source_objects.update(f['object_id'] for f in representation_facts if f['payload']['representation'] in {r.id for r in spec.representations})
            source_objects.update(catalog.object_ids_for_fact_digests([row[0] for row in rows(work.con,'SELECT DISTINCT fact_digest FROM hf',batch=512)]))
            predictions={f['fact_digest']:f for f in catalog.iter_facts('prediction',sequence=feature_sequence,check=work.check)}
            # Exposure knowledge is current knowledge, even when analytical values
            # are reconstructed from an older K. An old snapshot cannot reset use.
            exposed_operations=[];sidecars=[];outcome_origins={variant:set() for variant in variants};context_outcomes={variant:set() for variant in variants};capture_metadata={}
            for metadata in catalog.iter_facts('capture_metadata',check=work.check,require_complete=False):
                payload=metadata['payload']
                if payload.get('batch',{}).get('namespace')!=selection.namespace:continue
                capture_metadata[metadata['identity'][0]]=payload
                if set(variants).intersection(payload.get('variants',{})):source_objects.add(metadata['object_id'])
                for variant in variants:
                    outcome_origins[variant].update(captured_outcome_columns(payload,variant))
                    context_outcomes[variant].update(captured_context_outcome_columns(payload,variant))
                if payload.get('batch',{}).get('operation') in {'evaluate','study'}:exposed_operations.append(metadata['identity'][0])
                sidecars.extend(payload.get('membership_sidecars',[]))
            exposed_facts=set()
            for operation in exposed_operations:
                exposed_facts.update(catalog.prediction_digests_in_operation(operation))
            origin_facts=[f['payload'] for f in catalog.iter_facts('prediction_origin',sequence=feature_sequence,check=work.check) if f['payload'].get('namespace')==selection.namespace]
            origins={f['opportunity_key']:f['original_event_key'] for f in origin_facts}
            base.cg4_known_exposed_facts=exposed_facts;base.cg4_sidecars=sidecars;base.cg4_original_keys=origins
            base.cg4_original_entities={f['opportunity_key']:f.get('original_entity_key') for f in origin_facts}
            base.cg4_source_identities={}
            for f in origin_facts:
                base.cg4_source_identities.setdefault(f['opportunity_key'],[]).extend((info,f['original_event_key'],f.get('original_entity_key')) for info in f.get('source_identities',[]))
            for fact in catalog.iter_facts('prediction_source_identity',sequence=feature_sequence,check=work.check):
                f=fact['payload']
                if f['namespace']==selection.namespace:base.cg4_source_identities.setdefault(f['opportunity_key'],[]).append((f['source'],f['original_event_key'],f.get('original_entity_key')))
            missing=[]
            for table in tables.values():
                for (fact_digest,) in rows(work.con,f'SELECT DISTINCT history_fact FROM {table}'):
                    fact=predictions[fact_digest]
                    if fact['payload']['opportunity_key'] not in base.cg4_source_identities:missing.append(fact)
            if missing:
                object_operations=catalog.object_operations(sorted({f['object_id'] for f in missing}))
                legacy_opportunities={digest(f['identity']):f for f in catalog.iter_facts('opportunity',sequence=feature_sequence,
                    keys={f['payload']['opportunity_key'] for f in missing},require_complete=False,max_records=selection.max_scan_records,check=work.check)}
                for fact in missing:
                    p=fact['payload'];opportunity=legacy_opportunities.get(p['opportunity_key']);metadata=capture_metadata.get(object_operations.get(fact['object_id']))
                    if not opportunity or not metadata:continue
                    origin=legacy_source_origin(metadata,p['variant'],opportunity['identity'][0],p)
                    if origin is None:continue
                    base.cg4_original_keys.setdefault(p['opportunity_key'],origin['event'])
                    base.cg4_original_entities.setdefault(p['opportunity_key'],origin['entity'])
                    base.cg4_source_identities[p['opportunity_key']]=origin['sources'];source_objects.add(opportunity['object_id'])
                    work.check('legacy source identity reconstruction')
            class HistoricalPrepared(Prepared):
                def load_features(self):
                    asof=instant(self.spec.as_of or selection.as_of)
                    lookup={(f['payload']['view']['id'],f['payload']['owner_key']):f for f in feature_facts}
                    for view in self.spec.features:
                        for field in view.fields:
                            fid=view.id+'.'+field.id;self.definitions[fid]={'view':view.to_dict(),'field':field.to_dict()};cells=[]
                            for record in self.records:
                                owner_record=self.run_records.get(view.run or self.primary.id,{}).get(record['event_key'])
                                if owner_record is None:cells.append(missing_cell(field.kind));continue
                                prediction=predictions[owner_record['history_fact']]
                                owner=record['history_opportunity'] if view.owner=='opportunity' else digest([prediction['key'],prediction['revision']])
                                fact=lookup.get((view.id,owner));cell=missing_cell(field.kind)
                                cutoff,cutoff_state=owner_record.get('prediction_tick'),None
                                if fact:
                                    retained=fact['payload'];definition=next((f for f in retained['view']['fields'] if f['id']==field.id),None)
                                    if fid in retained.get('known_outcome_fields',()):self.known_outcome_features.add(fid)
                                    source=retained.get('source',{})
                                    if (source.get('sha256'),source.get('bytes'),field.column) in outcome_origins[view.run or self.primary.id]:self.known_outcome_features.add(fid)
                                    if definition!=field.to_dict():raise EvaluationError('Requested typed field differs from its retained semantics.','feature_semantics_changed')
                                    if retained['view'].get('information_cutoff')!=view.to_dict()['information_cutoff']:raise EvaluationError('Requested information cutoff differs from retained semantics.','feature_semantics_changed')
                                    if view.owner=='prediction_revision' and retained['variant']!=(view.run or self.primary.id):raise EvaluationError('Typed prediction ownership differs.','feature_owner_unknown')
                                    cell=retained['values'].get(field.id,cell)
                                    if view.information_cutoff:cutoff,cutoff_state=retained_cutoff(view,retained)
                                else:
                                    raw=json.loads(record.get('history_context') or '{}')
                                    if field.column in raw:
                                        cell=cells_from_row(view,raw)[field.id]
                                        if field.column in context_outcomes[view.run or self.primary.id]:self.known_outcome_features.add(fid)
                                    if view.information_cutoff:cutoff,cutoff_state=retained_cutoff(view,None,raw)
                                cells.append(apply_availability(cell,view=self.spec.feature_time_view,cutoff_ns=cutoff,cutoff_state=cutoff_state,as_of_ns=asof,declaration=view.availability))
                            self.features[fid]=cells
                def retained_representation(self,representation):
                    wanted=[f for f in representation_facts if f['payload']['representation']==representation.id and f['payload']['variant']==(representation.run or self.primary.id)]
                    mapping={f['payload']['owner_key']:f['payload'] for f in wanted};dimension=representation.dimensions or (wanted[0]['payload']['dimensions'] if wanted else None)
                    if not dimension:raise EvaluationError('Representation dimensions were not retained.','representation_not_retained')
                    from .representations import admit_aligned_matrix
                    admit_aligned_matrix(len(self.keys),dimension,'<f8',self.config)
                    matrix=np.full((len(self.keys),dimension),np.nan,dtype='<f8');available=np.zeros(len(self.keys),bool);reasons=['representation_not_retained']*len(self.keys);opened={}
                    content_views={(f['payload']['view']['id'],f['payload']['owner_key']):f['payload']['view'] for f in feature_facts}
                    if True:
                        for i,record in enumerate(self.records):
                            owner_record=self.run_records.get(representation.run or self.primary.id,{}).get(record['event_key'])
                            if owner_record is None:reasons[i]='owner_prediction_unavailable';continue
                            pred=predictions[owner_record['history_fact']];payload=mapping.get(digest([pred['key'],pred['revision']]))
                            if not payload or payload['state']!='observed':continue
                            original=payload['spec']
                            if representation.model_digest and representation.model_digest!=original.get('model_digest'):raise EvaluationError('Retained representation identity differs.','representation_changed')
                            location=catalog.vector_location(payload['vector_digest'])
                            if location is None:raise EvaluationError('Retained vector location is absent.','historical_evidence_unavailable')
                            oid=location['object_id']
                            if oid not in opened:opened[oid]=catalog.vector_matrix(location)
                            vector=opened[oid][location['row_index']]
                            if vector.shape!=(dimension,) or hashlib.sha256(opened[oid].dtype.str.encode()+vector.tobytes()).hexdigest()!=payload['vector_digest']:raise EvaluationError('Retained vector changed.','historical_evidence_changed')
                            tick,state=payload.get('content_available') or (None,'undeclared');limit=instant(self.spec.as_of or selection.as_of) if self.spec.feature_time_view=='retrospective' else owner_record.get('prediction_tick')
                            admitted=original.get('availability')=='at_decision' or payload.get('content_availability_declaration')=='at_decision' or tick is not None and state=='valid' and limit is not None and int(tick)<=limit
                            if original.get('kind') in {'e5_text','dinov2_image'}:
                                view_id=original['field'].split('.',1)[0]
                                content_view=content_views.get((view_id,digest([pred['key'],pred['revision']]))) or content_views.get((view_id,record['history_opportunity']))
                                if not content_view and self.spec.feature_time_view=='available_at_decision':
                                    admitted=False
                                elif content_view and content_view.get('information_cutoff'):
                                    from .feature_contracts import FeatureViewSpec
                                    view=FeatureViewSpec.from_dict(content_view)
                                    cutoff,cutoff_state=retained_cutoff(view,{'information_cutoff':payload.get('content_information_cutoff')})
                                    cell={'state':'observed','canonical':'content','available_ns':tick}
                                    admitted=apply_availability(cell,view=self.spec.feature_time_view,cutoff_ns=cutoff,cutoff_state=cutoff_state,
                                        as_of_ns=limit,declaration=payload.get('content_availability_declaration','unknown'))['state']=='observed'
                            if not admitted:reasons[i]='content_unavailable_at_cutoff';continue
                            matrix[i]=vector;available[i]=True;reasons[i]=''
                    return {'id':representation.id,'vectors':matrix,'available':available,'reason':reasons,'normalization':representation.normalization,
                            'provenance':{'producer':'retained','selection':selection.to_dict(),'facts_digest':digest([f['fact_digest'] for f in wanted])}}
            effective=replace(spec,history={'workspace_path':str(root),'selection':selection.to_dict()})
            binding={'workspace_path':str(root),'instance_id':catalog.instance_id,'selection':selection.to_dict(),'scan':scan,
                     'source_objects':sorted(source_objects),
                     'typed_snapshot':digest([f['fact_digest'] for f in feature_facts+representation_facts]),
                     'exposure_knowledge':digest([sorted(exposed_facts),sidecars])}
            prepared=HistoricalPrepared(effective,config,roots,work,base,history=binding,identity_only=identity_only)
            yield prepared
    finally:work.close()
