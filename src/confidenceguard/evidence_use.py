"""Protected, study-scoped evidence use. Missing history never proves freshness."""
from contextlib import closing
import json
import uuid
import threading
import hashlib
from .contracts import EvaluationError,digest
from .history_storage import Catalog

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
    def __init__(self,workspace):
        self.catalog=workspace.catalog if hasattr(workspace,'catalog') else Catalog(workspace)
        from .platform_catalog import PlatformCatalog
        self.platform=isinstance(self.catalog,PlatformCatalog)

    def status(self):
        if self.platform:
            from numek_platform.governance.ledger import tracking_status
            return tracking_status(self.catalog.db,self.catalog.scope,self.catalog.catalog_id)
        # Read-only legacy catalog v2 (migration validation and historical reproduction).
        if self.catalog.catalog_version<2:return {'enabled':False,'continuity':'unknown','system_verified_external_independence':False}
        with closing(self.catalog._connect()) as db:
            settings={k:json.loads(v) for k,v in db.execute("SELECT key,value FROM settings WHERE key IN ('exposure_tracking','exposure_continuity','branch_id','exposure_continuity_token')")}
        return {'enabled':settings['exposure_tracking'],'continuity':settings['exposure_continuity'],'branch_id':settings['branch_id'],
                'continuity_token':settings.get('exposure_continuity_token'),
                'system_verified_external_independence':False,'guarantee_scope':'predeclared_study_only'}

    def enable(self,enabled):
        if not isinstance(enabled,bool):raise EvaluationError('Evidence-use consent must be Boolean.')
        if not self.platform:raise EvaluationError('Catalog v2 is read-only; migrate the workspace to the NUMEK platform.','migration_required')
        from numek_platform.governance.ledger import set_tracking
        return set_tracking(self.catalog.db,self.catalog.scope,self.catalog.catalog_id,enabled)

    def overlap(self,events,units,*,family_digest=None,population_digest=None,check=None):
        if self.platform:
            from numek_platform.governance.ledger import _overlap_reasons
            with self.catalog.db.transaction() as conn:
                return _overlap_reasons(conn,self.catalog.catalog_id,sorted(set(events)),sorted(set(units)),family_digest,population_digest)
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
        if not self.platform:raise EvaluationError('Catalog v2 is read-only; migrate the workspace to the NUMEK platform.','migration_required')
        return self._record_platform(kind,events=events,units=units,population_digest=population_digest,family_digest=family_digest,
            request_id=request_id,study_id=study_id,alpha=alpha,total_alpha=total_alpha,metadata=metadata,query_events=query_events)


def _record_platform(self,kind,*,events,units,population_digest,family_digest,request_id,study_id,alpha,total_alpha,metadata,query_events):
    """Durable platform reservation with the v2 receipt shape (exposure is recorded, never session-only)."""
    from numek_platform.errors import PlatformError
    from numek_platform.execution import jobs
    from numek_platform.governance import ledger
    from .platform_catalog import _translate
    state=self.status()
    if not state['enabled']:raise EvaluationError('Explicit evidence-use tracking consent required.','exposure_tracking_disabled')
    catalog=self.catalog;request_id=request_id or uuid.uuid4().hex
    with catalog.db.connect() as conn:
        prior=conn.execute('SELECT * FROM evidence_uses WHERE catalog_id=%s AND request_id=%s',(catalog.catalog_id,request_id)).fetchone()
    if prior is not None and 'receipt_catalog_sequence' in (prior['metadata'] or {}):
        # A repeated request returns the original receipt (v2 parity); different content still
        # refuses in the ledger.
        expected=dict(metadata or {},purpose=(metadata or {}).get('purpose',kind))
        if (prior['kind']!=kind or prior['population_digest']!=population_digest or prior['family_digest']!=family_digest
                or {k:v for k,v in prior['metadata'].items() if k!='receipt_catalog_sequence'}!=expected):
            raise EvaluationError('This request id was already used for different content.','idempotency_conflict')
        return {'evidence_use_id':prior['id'],'evidence_kind':prior['kind'],'catalog_sequence':prior['metadata']['receipt_catalog_sequence'],
                'continuity_context':{'enabled':True,'continuity':prior['continuity'],'branch_id':prior['branch_id'],
                    'continuity_token':prior['continuity_token'],'system_verified_external_independence':False,
                    'guarantee_scope':'predeclared_study_only'}}
    head=catalog.head();metadata=dict(metadata or {},receipt_catalog_sequence=head)
    try:
        with catalog.db.connect() as conn:
            # One attempt per call; a repeated request id is idempotent in the ledger itself.
            lease,_row=jobs.start_inline(conn,catalog.scope,'cg_evidence_use',idempotency_key=uuid.uuid4().hex,owner='confidenceguard')
        try:
            reservation=ledger.reserve(catalog.db,catalog.store,catalog.scope,lease,catalog.catalog_id,purpose=kind,members=[],
                extra_events=sorted(set(events)),extra_units=sorted(set(units)),population_digest=population_digest,family_digest=family_digest,
                request_id=request_id,study_id=study_id,alpha=alpha,total_alpha=total_alpha,metadata=metadata,query_events=query_events,
                consume_reserve=kind in {'confirmation','numerical_recomputation'},
                read_k=catalog.head())   # the study's snapshot: inherited worker authority never reads beyond it
        finally:
            with catalog.db.connect() as conn:jobs.complete(conn,lease,{})
    except PlatformError as exc:
        raise _translate(exc) from exc
    if reservation.reused:
        return {'evidence_use_id':reservation.id,'evidence_kind':reservation.kind,'reused_reservation':True,'fresh_independent_evidence':False,'continuity_context':state}
    return {'evidence_use_id':reservation.id,'evidence_kind':reservation.kind,'catalog_sequence':head,'continuity_context':state}


EvidenceUseLedger._record_platform=_record_platform


def _records(self):
    """Every durable evidence-use record in the v2 payload shape (access-only platform reads are not uses)."""
    if not self.platform:
        return [fact['payload'] for fact in self.catalog.iter_facts('evidence_use')]
    with self.catalog.db.connect() as conn:
        rows=conn.execute("SELECT * FROM evidence_uses WHERE catalog_id=%s AND kind<>'access' ORDER BY created_at,id",(self.catalog.catalog_id,)).fetchall()
    def number(value):
        return None if value is None else (int(value) if value==int(value) else float(value))
    # A G.8 reserve claim consumes sealed-reserve units but is not an assessment use.
    return [{'id':r['id'],'kind':'reserve_claim' if r['purpose']=='reserve_claim' else r['kind'],'request_id':r['request_id'],'request_digest':r['request_digest'],'population_digest':r['population_digest'],
             'family_digest':r['family_digest'],'membership_digest':r['membership_digest'],'event_count':r['event_count'],'unit_count':r['unit_count'],
             'study_id':r['study_id'],'alpha':number(r['alpha']),'total_alpha':number(r['total_alpha']),'metadata':r['metadata'] or {},'branch_id':r['branch_id'],
             'continuity':r['continuity'],'continuity_token':r['continuity_token'],
             'state':'reserved' if r['kind'] in {'confirmation','numerical_recomputation'} else 'exposed'} for r in rows]


EvidenceUseLedger.records=_records


