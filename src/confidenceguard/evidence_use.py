"""Protected, study-scoped evidence use. Missing history never proves freshness."""
from contextlib import closing,nullcontext
from decimal import Decimal
import json
import uuid
import threading
import hashlib
from .contracts import EvaluationError,digest
from .history_storage import Catalog,EvidenceWriter

# Ephemeral process observations supplement the durable ledger. Process loss is
# unknown history, never evidence of freshness. Only canonical hashed identifiers
# are retained here, never feature values or individual outcomes. These hashes
# are protected identifiers, not anonymization.
_SESSION_USES=[]
_SESSION_LOCK=threading.RLock()
SOURCE_ALIAS_POLICY='canonical_and_original_source_aliases_v1'


def incomplete_replay_use(use):
    metadata=use.get('metadata') or {}
    return (use['kind']=='outcome_disclosure' and metadata.get('purpose') in {'historical_replay','outcome_restatement','policy_historical_replay','policy_outcome_restatement'} and
            (metadata.get('identity_policy')!=SOURCE_ALIAS_POLICY or metadata.get('local_identity_scope')!='canonical_history_keys_and_retained_original_aliases'))


def session_replay_history_incomplete():
    with _SESSION_LOCK:return any(incomplete_replay_use(use) for use in _SESSION_USES)


def source_aliases(info,event,entity=None):
    """Known local file/key reuse survives namespace, label and path changes.

    Paths/inodes are protected provenance anchors, not population identity or
    proof of independence. Independent upstream populations need distinct source
    snapshots. Unobservable copies/forks still require scoped declarations.
    """
    anchors=[]
    if info.get('path'):anchors.append(['path',info['path']])
    if isinstance(info.get('signature'),(list,tuple)) and len(info['signature'])>=2:anchors.append(['file',*info['signature'][:2]])
    return ({digest(['local_source_event_v1',anchor,event]) for anchor in anchors},
            {digest(['local_source_unit_v1',anchor,entity or event]) for anchor in anchors})


def source_scope_aliases(info):
    """Query-only anchors for earlier whole-source disclosure without row keys.

    Keyed D/S/H reservations never store these anchors: shared files do not imply
    shared rows. Only an actual unkeyed outcome assessment records whole-source use.
    """
    anchors=[]
    if info.get('path'):anchors.append(['path',info['path']])
    if isinstance(info.get('signature'),(list,tuple)) and len(info['signature'])>=2:anchors.append(['file',*info['signature'][:2]])
    return {digest(['local_unkeyed_source_exposure_v1',anchor]) for anchor in anchors}


def population_identifiers(prepared,indices,*,source_scope=False):
    """Canonical identifiers plus observable source aliases, never raw outcomes."""
    events=set();units=set();namespace=prepared.spec.roles.namespace
    for i in indices:
        record=prepared.records[int(i)];event=record['event_key'];entity=record.get('entity_key')
        if not source_scope:
            events.add(digest([namespace,event]));units.add(digest([namespace,entity or event]))
        retained=getattr(prepared.store,'cg4_source_identities',{}).get(event)
        if retained is not None:
            sources=retained
        else:
            sources=[]
            for run in prepared.store.spec.runs:
                row=prepared.run_records.get(run.id,{}).get(event)
                if row:sources.append((prepared.files.get(run.source,{}),event,row.get('entity_key')))
            outcomes=getattr(prepared.store,'outcomes',None) or getattr(prepared.store.spec,'outcomes',None)
            if outcomes:sources.append((prepared.files.get(outcomes.source,{}),event,entity))
        for info,key,owner in sources:
            if source_scope:events.update(source_scope_aliases(info))
            else:
                ee,uu=source_aliases(info,key,owner);events.update(ee);units.update(uu)
        if int(i)%512==0:prepared.work.check('protected evidence identity aliases')
    return sorted(events),sorted(units)


def local_identity_scope(prepared,indices):
    """Describe the limits of observable historical cross-source overlap checks.

    Canonical historical keys still support local D/S/H comparison when original
    aliases were not retained. Missing aliases cannot verify separation from a
    differently named live evaluation or source. External declarations remain
    declarations in either case.
    """
    if not prepared.history:return 'live_source_keys_and_available_local_aliases'
    originals=getattr(prepared.store,'cg4_source_identities',{})
    if all(originals.get(prepared.records[int(i)]['event_key']) for i in indices):
        return 'canonical_history_keys_and_retained_original_aliases'
    return 'canonical_history_keys_original_aliases_incomplete'


def evaluation_exposure_worker(spec,config,roots,operation,*,progress=None):
    """Identity scan for live CG1/CG2 outcome use; no history capture or refitting."""
    from .engine import open_store
    from .sources import rows
    from .result import Inspection
    extension=spec if hasattr(spec,'evaluation') else None;base=spec.evaluation if extension else spec
    namespace=spec.roles.namespace if extension else 'cg1_supplied_predictions'
    work=None
    try:
        work,store,_=open_store(base,config,roots,progress,extension=extension)
        events=set();units=set()
        for run in base.runs:
            table=store.run_tables[run.id]
            where=" AND cg_role IN ('F','S','C')" if extension and operation=='fit' else ''
            query=f'SELECT event_key,entity_key FROM {table} WHERE event_key IS NOT NULL'+where
            for event,entity in rows(store.con,query,batch=512):
                events.add(digest([namespace,event]));units.add(digest([namespace,entity or event]))
                outcome_source=store.outcomes.source if store.outcomes else run.source
                for sid in dict.fromkeys((run.source,outcome_source)):
                    info=store.sources[sid];ee,uu=source_aliases(info,event,entity);events.update(ee);units.update(uu)
                    if not run.key_columns:events.update(source_scope_aliases(info))
                if (len(events)+len(units))*192>config.max_rss_bytes//8:raise EvaluationError('Exposure identities exceed the explicit memory budget.','evidence_use_capacity')
                work.check('live outcome exposure identity scan')
        store.verify()
        return Inspection({'events':sorted(events),'units':sorted(units),'population_digest':digest([sorted(events),sorted(units)]),
            'sources':{k:{n:v.get(n) for n in ('sha256','bytes')} for k,v in store.sources.items()}},
            {'status':'completed','peak_workspace_bytes':work.peak})
    finally:
        if work:work.close()


def session_overlap(events,units,family=None,population=None):
    events=set(events);units=set(units)
    with _SESSION_LOCK:
        if any(entry['kind'] in {'confirmation','numerical_recomputation'} and entry['family']==family and entry['population']==population for entry in _SESSION_USES):return False
        return any(events&entry['events'] or units&entry['units'] for entry in _SESSION_USES)


def record_session(kind,events,units,*,family=None,population=None,max_bytes=512*1024**2,numerical_origin=None,numerical_replicates=None,
                   workspace=None,use_id=None,_locked=False,metadata=None):
    catalog=workspace.catalog if hasattr(workspace,'catalog') else workspace if isinstance(workspace,Catalog) else Catalog(workspace) if workspace is not None else None
    if catalog is not None and not _locked:
        with catalog.operation():
            return record_session(kind,events,units,family=family,population=population,max_bytes=max_bytes,
                numerical_origin=numerical_origin,numerical_replicates=numerical_replicates,workspace=catalog,use_id=use_id,_locked=True,metadata=metadata)
    owner=catalog.instance_id if catalog is not None else None
    if use_id is not None:
        # A replayed receipt must not repopulate identifiers erased by deletion.
        with closing(catalog._connect()) as db:
            row=db.execute('SELECT o.state FROM evidence_uses e JOIN objects o ON o.id=e.object_id WHERE e.id=?',(use_id,)).fetchone()
        if row is None or row[0]!='active':return
    events=set(events);units=set(units)
    with _SESSION_LOCK:
        if kind=='numerical_recomputation':
            reserved=next((v for v in _SESSION_USES if v.get('numerical_origin')==numerical_origin),None)
            if reserved and (reserved['numerical_replicates']!=numerical_replicates or reserved['family']!=family or reserved['population']!=population):
                raise EvaluationError('This numerical origin already reserved a different replication budget. Resume that attempt; only its insufficient child can authorize a further extension.','numerical_retry_already_reserved')
        previous=next((v for v in _SESSION_USES if v['kind']==kind and v['family']==family and v['population']==population and
                       v.get('owner')==owner and v.get('use_id')==use_id and v.get('numerical_origin')==numerical_origin),None)
        extra=len(events-(previous['events'] if previous else set()))+len(units-(previous['units'] if previous else set()))
        size=(sum(len(v['events'])+len(v['units']) for v in _SESSION_USES)+extra)*192
        if size>max_bytes:raise EvaluationError('Protected session exposure identifiers exceed the admitted parent-memory budget. Use durable tracking or raise the explicit resource budget.','session_evidence_use_capacity')
        if previous:previous['events'].update(events);previous['units'].update(units)
        else:_SESSION_USES.append({'kind':kind,'events':events,'units':units,'family':family,'population':population,
                                  'numerical_origin':numerical_origin,'numerical_replicates':numerical_replicates,'owner':owner,'use_id':use_id,'metadata':dict(metadata or {})})


def forget_session_uses(owner,*,use_ids=(),purge=False,untracked=False):
    """Release only the deleted workspace's observations; absence is not freshness.

    Called while holding the catalog operation lock, after durable tombstones.
    Python releases retained references; this does not promise physical RAM wiping.
    """
    identifiers=set(use_ids)
    with _SESSION_LOCK:
        _SESSION_USES[:]=[v for v in _SESSION_USES if not (v.get('owner')==owner and
            (purge or v.get('use_id') in identifiers or untracked and v.get('use_id') is None))]


class EvidenceUseLedger:
    def __init__(self,workspace):self.catalog=workspace.catalog if hasattr(workspace,'catalog') else Catalog(workspace)

    def status(self):
        if self.catalog.catalog_version<2:return {'enabled':False,'continuity':'unknown','system_verified_external_independence':False}
        with closing(self.catalog._connect()) as db:
            settings={k:json.loads(v) for k,v in db.execute("SELECT key,value FROM settings WHERE key IN ('exposure_tracking','exposure_continuity','branch_id','exposure_continuity_token')")}
        return {'enabled':settings['exposure_tracking'],'continuity':settings['exposure_continuity'],'branch_id':settings['branch_id'],
                'continuity_token':settings.get('exposure_continuity_token'),
                'system_verified_external_independence':False,'guarantee_scope':'predeclared_study_only'}

    def enable(self,enabled):
        if not isinstance(enabled,bool):raise EvaluationError('Evidence-use consent must be Boolean.')
        if self.catalog.catalog_version<2:raise EvaluationError('Migrate the catalog explicitly before evidence tracking.','migration_required')
        with self.catalog.operation(),closing(self.catalog._connect()) as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute("UPDATE settings SET value=? WHERE key='exposure_tracking'",(json.dumps(enabled),))
            # Starting tracking does not establish anything about earlier use.
            if not enabled:db.execute("UPDATE settings SET value='\"incomplete\"' WHERE key='exposure_continuity'")
            if not enabled or db.execute("SELECT value FROM settings WHERE key='exposure_continuity_token'").fetchone() is None:
                db.execute('INSERT OR REPLACE INTO settings VALUES (?,?)',('exposure_continuity_token',json.dumps(uuid.uuid4().hex)))
            db.commit()
        return self.status()

    def overlap(self,events,units,*,family_digest=None,population_digest=None,check=None):
        events=set(events);units=set(units);uses={};reasons=[]
        try:
            for fact in self.catalog.iter_facts('evidence_use',require_complete=True,check=check):uses[fact['payload']['id']]=fact['payload']
            if any(incomplete_replay_use(use) for use in uses.values()):reasons.append('exposure_history_incomplete')
            with closing(self.catalog._connect()) as db:
                indexed={r[0] for r in db.execute('SELECT id FROM evidence_uses')}
            if indexed!=set(uses):reasons.append('exposure_history_incomplete')
            # The index is a locator, not proof that every protected chunk still
            # exists. Reconstruct the original canonical membership hash using
            # two bounded scans; no whole-history identifier set is materialized.
            hashes={uid:hashlib.sha256(b'{"events":[') for uid in uses}
            for field in ('events','units'):
                counts={uid:0 for uid in uses};chunks={uid:0 for uid in uses};last={uid:None for uid in uses}
                for fact in self.catalog.iter_facts('exposure_members',require_complete=True,check=check,_logical_order=True):
                    packet=fact['payload'];uid=packet['use_id'];use=uses.get(uid)
                    if use is None:reasons.append('exposure_history_incomplete');continue
                    values=packet[field];index=chunks[uid];chunks[uid]+=1
                    expected=max(0,min(512,use[field[:-1]+'_count']-index*512))
                    valid=(fact['identity']==[uid,index] and isinstance(values,list) and len(values)==expected and
                           all(isinstance(v,str) and len(v)==64 and all(c in '0123456789abcdef' for c in v) for v in values) and
                           all(a<b for a,b in zip(values,values[1:])) and (not values or last[uid] is None or last[uid]<values[0]))
                    if not valid:reasons.append('exposure_history_incomplete');continue
                    if values:
                        if counts[uid]:hashes[uid].update(b',')
                        hashes[uid].update(json.dumps(values,separators=(',',':'),ensure_ascii=True).encode()[1:-1])
                        counts[uid]+=len(values);last[uid]=values[-1]
                    same=use['kind'] in {'confirmation','numerical_recomputation'} and use.get('family_digest')==family_digest and use['population_digest']==population_digest
                    if not same and (events if field=='events' else units).intersection(values):reasons.append('previously_exposed_confirmation_population')
                for uid,use in uses.items():
                    if counts[uid]!=use[field[:-1]+'_count'] or chunks[uid]!=(max(use['event_count'],use['unit_count'])+511)//512:reasons.append('exposure_history_incomplete')
                    hashes[uid].update(b'],"units":[' if field=='events' else b']}')
            if any(hashes[uid].hexdigest()!=use['membership_digest'] for uid,use in uses.items()):reasons.append('exposure_history_incomplete')
        except (OSError,EvaluationError,KeyError,TypeError,ValueError) as exc:
            if getattr(exc,'code',None) in {'cancelled','deadline_exceeded'}:raise
            reasons.append('exposure_history_unavailable')
        return sorted(set(reasons))

    def record(self,kind,*,events,units,population_digest,family_digest=None,request_id=None,
               study_id=None,alpha=None,total_alpha=None,metadata=None,cancel=None,locked=False,deadline=None,session_max_bytes=512*1024**2,query_events=None):
        if kind not in {'discovery_selection','confirmation','outcome_disclosure','numerical_recomputation'}:raise EvaluationError('Invalid evidence-use purpose.')
        state=self.status()
        if not state['enabled']:raise EvaluationError('Explicit evidence-use tracking consent required.','exposure_tracking_disabled')
        events=sorted(set(events));units=sorted(set(units));request_id=request_id or uuid.uuid4().hex
        request={'kind':kind,'events':events,'units':units,'population_digest':population_digest,'family_digest':family_digest,
                 'study_id':study_id,'alpha':alpha,'total_alpha':total_alpha,'metadata':metadata or {}}
        request_digest=digest(request)
        def remember(receipt):
            record_session(kind,events,units,family=family_digest,population=population_digest,max_bytes=session_max_bytes,
                numerical_origin=(metadata or {}).get('origin_analysis_digest') if kind=='numerical_recomputation' else None,
                numerical_replicates=(metadata or {}).get('replicates') if kind=='numerical_recomputation' else None,
                workspace=self.catalog,use_id=receipt['evidence_use_id'],_locked=True,metadata=metadata)
            return receipt
        def check(*args):
            import time
            if cancel is not None and cancel.is_set():raise EvaluationError('Evidence reservation cancelled.','cancelled')
            if deadline is not None and time.monotonic()>deadline:raise EvaluationError('Evidence reservation deadline exhausted.','deadline_exceeded')
        with (nullcontext() if locked else self.catalog.operation()):
            check()
            state=self.status()
            if not state['enabled']:raise EvaluationError('Evidence tracking was disabled before reservation.','exposure_tracking_disabled')
            gap=state['continuity'] in {'incomplete','restore_unreconciled'}
            current=(metadata or {}).get('exposure_history_token')
            if kind=='confirmation' and gap and (not current or current!=state.get('continuity_token')):
                raise EvaluationError('This history gap requires a current explicit scoped declaration, not an earlier unexposed assertion.','exposure_history_gap_requires_current_declaration')
            if kind=='numerical_recomputation' and ((metadata or {}).get('continuity_token')!=state.get('continuity_token') or (metadata or {}).get('branch_id')!=state['branch_id'] or gap):
                raise EvaluationError('Numerical-attempt continuity changed before reservation.','numerical_retry_provenance')
            previous=self.catalog.receipt('evidence:'+request_id,request_digest)
            if previous:return remember(previous)
            if kind=='confirmation':
                uses=[fact['payload'] for fact in self.catalog.iter_facts('evidence_use',check=check)]
                declared=(metadata or {}).get('predeclared_look');look_id=(metadata or {}).get('look_id')
                if declared:
                    initial=next((use for use in uses if use['id']==(metadata or {}).get('initial_use_id') and use['kind']=='confirmation' and use.get('family_digest')==family_digest and use.get('metadata',{}).get('look_id') is None),None)
                    membership=digest({'events':events,'units':units})
                    if initial is None or declared not in initial.get('metadata',{}).get('restatement_schedule',[]) or declared.get('id')!=look_id or Decimal(str(declared['alpha']))!=Decimal(str(alpha)) or initial['membership_digest']!=membership:
                        raise EvaluationError('Scheduled reuse lacks the original durable family, schedule or identical planned population.','scheduled_restatement_provenance')
                    if any(use['kind']=='confirmation' and use.get('family_digest')==family_digest and use.get('metadata',{}).get('look_id')==look_id and use['population_digest']!=population_digest for use in uses):
                        raise EvaluationError('This scheduled look was already reserved against a different outcome snapshot. Use descriptive restatement; its allocation cannot be reset.','scheduled_look_already_assessed')
                for prior in uses:
                    if prior['kind']=='confirmation' and prior.get('family_digest')==family_digest and prior['population_digest']==population_digest and prior.get('metadata',{}).get('look_id')==look_id:
                        return remember({'evidence_use_id':prior['id'],'reused_reservation':True,'fresh_independent_evidence':False,
                            'continuity_context':{'enabled':True,'branch_id':prior['branch_id'],'continuity':prior['continuity'],'continuity_token':prior.get('continuity_token')}})
                reasons=self.overlap(query_events if query_events is not None else events,units,family_digest=family_digest,population_digest=population_digest,check=check)
                if current and current==state.get('continuity_token') and (metadata or {}).get('external_exposure')=='declared_unexposed' and (metadata or {}).get('declaration_author') and (metadata or {}).get('declaration_reason'):
                    reasons=[r for r in reasons if r not in {'exposure_history_unavailable','exposure_history_incomplete'}]
                if declared:reasons=[r for r in reasons if r not in {'previously_exposed_confirmation_population','exposure_history_unavailable','exposure_history_incomplete'}]
                if reasons:raise EvaluationError('Confirmation population has conflicting or incomplete exposure history.','confirmation_population_exposed')
            operation,_=self.catalog.begin('evidence:'+request_id,request_digest,require_saving=False)
            uid=digest([kind,population_digest,family_digest,request_id])[:32]
            writer=EvidenceWriter(self.catalog.root/'staging'/operation,self.catalog.config,operation,check)
            membership_digest=digest({'events':events,'units':units})
            for start in range(0,max(len(events),len(units)),512):
                writer.add('exposure_members',[uid,start//512],{'use_id':uid,'events':events[start:start+512],'units':units[start:start+512]})
            use={'id':uid,'kind':kind,'request_id':request_id,'request_digest':request_digest,'population_digest':population_digest,
                 'family_digest':family_digest,'membership_digest':membership_digest,'event_count':len(events),'unit_count':len(units),
                 'study_id':study_id,'alpha':alpha,'total_alpha':total_alpha,'metadata':metadata or {},'branch_id':state['branch_id'],
                 'continuity':state['continuity'],'continuity_token':state.get('continuity_token'),'state':'reserved' if kind in {'confirmation','numerical_recomputation'} else 'exposed'}
            writer.add('evidence_use',[uid],use);writer.finish({'capture_stages':['evidence_use'],'evidence_use':use})
            return remember(self.catalog.commit_capture(operation,cancel=cancel,receipt_extra={'evidence_use_id':uid,'continuity_context':state}))


def commit_use(db,metadata,operation):
    """Called inside the catalog visibility transaction, never after H access."""
    use=metadata.get('evidence_use')
    if not use:return
    object_row=db.execute("SELECT object_id FROM facts WHERE kind='evidence_use' AND key=?",(digest([use['id']]),)).fetchone()
    if object_row is None:raise EvaluationError('Evidence-use protected record is absent.','capture_changed')
    public={k:use[k] for k in ('branch_id','continuity','event_count','unit_count','membership_digest')}
    db.execute('INSERT INTO evidence_uses VALUES (?,?,?,?,?,?,?,?,?,?)',
               (use['id'],use['request_id'],use['request_digest'],use['kind'],use['population_digest'],use.get('family_digest'),use['state'],object_row[0],json.dumps(public),__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat()))
    if use.get('study_id'):
        alpha=Decimal(str(use['alpha']));total=Decimal(str(use['total_alpha']))
        prior=db.execute('SELECT alpha,total_alpha FROM study_allocations WHERE study_id=?',(use['study_id'],)).fetchall()
        if alpha<=0 or any(Decimal(str(row[1]))!=total for row in prior) or sum((Decimal(str(row[0])) for row in prior),Decimal(0))+alpha>total:
            raise EvaluationError('Predeclared study error allocation exhausted or changed.','study_alpha_exhausted')
        db.execute('INSERT INTO study_allocations VALUES (?,?,?,?)',(use['study_id'],use['id'],float(alpha),float(total)))
