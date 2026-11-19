"""Frozen-gate historical investigation and descriptive immutable restatements."""
from dataclasses import replace
from datetime import datetime,timezone
import copy
import time
import uuid
import numpy as np
from .contracts import EvaluationError,digest
from .investigation_contracts import InvestigationSpec,FailureObjectiveSpec,INVESTIGATION_METHOD,INVESTIGATION_RESULT
from .investigation_result import InvestigationResult
from .investigation import arguments,prepared
from .investigation_membership import apply
from . import compat
from .execution_context import ctx


def _population(spec,config,roots,H_only,*,progress=None):
    from .result import Inspection
    with prepared(spec,config,roots,progress,identity_only=True) as p:
        indices=[i for i,k in enumerate(p.keys) if not H_only or p.roles[k]=='H']
        from .evidence_use import population_identifiers,local_identity_scope,SOURCE_ALIAS_POLICY
        events,units=population_identifiers(p,indices)
        return Inspection({'identity':p.identity_fingerprint,'effective_spec':p.spec.to_dict(),'events':events,'units':units,
            'planned_records':len(indices),'identity_policy':SOURCE_ALIAS_POLICY,'local_identity_scope':local_identity_scope(p,indices),
            'population_digest':digest([events,units,p.identity_fingerprint])},{'status':'completed','peak_workspace_bytes':p.work.peak})


def _replay(origin,spec,config,roots,population,reason,restatement,H_only,*,progress=None):
    from .investigation_objectives import bind
    original=InvestigationSpec.from_dict(origin.private['investigation_spec'])
    if original.roles.namespace!=spec.roles.namespace:raise EvaluationError('Historical replay cannot silently rename the original namespace.','investigation_identity')
    with prepared(spec,config,roots,progress) as p:
        if population['identity']!=p.identity_fingerprint:raise EvaluationError('Historical replay changed after exposure reservation.','stale_confirmation')
        p.store.cg4_confirmation=True
        spec=p.spec;mapping={o.id:o for o in spec.objectives};frozen=origin.private.get('frozen_hypotheses')
        if frozen:
            claims=[{'id':h['candidate_id'],'membership_artifact':h['membership_artifact'],'objective':h['objective'],'hypothesis_id':h['id']} for h in frozen['hypotheses']]
        else:claims=origin.private.get('replay_claims') or [c for c in origin.data['investigation']['candidates'] if c['id'] in origin.data['investigation']['shortlist']]
        history=[];memberships={};event_hashes={};locators={}
        if not claims:raise EvaluationError('Historical replay requires retained selected regions.','no_frozen_regions')
        for claim in claims:
            objective=FailureObjectiveSpec.from_dict(claim['objective']);replacement=mapping.get(objective.id)
            if replacement is None:raise EvaluationError('Bind each original objective to an explicit historical run.','objective_run')
            comparisons=lambda o:{k:v for k,v in o.to_dict().items() if k not in {'run','reference_run','metric_identity','practical_threshold'}}
            if comparisons(objective)!=comparisons(replacement):raise EvaluationError('Historical replay changed the original objective definition.','objective_identity')
            objective=replace(objective,run=replacement.run,reference_run=replacement.reference_run)
            adapter=bind(objective,p.store);artifact=origin.private['artifacts'][claim['membership_artifact']]
            roles=['H'] if H_only else list(p.store.cg4_periods) if p.history and objective.comparator!='reference_period' else ['historical_replay']
            if not H_only:
                for table in p.store.run_tables.values():
                    p.store.con.execute(f'UPDATE {table} SET cg4_role='+('cg4_period' if p.history and objective.comparator!='reference_period' else "'historical_replay'")+',cg4_selected=true')
            memberships[claim['membership_artifact']]={}
            for role in roles:
                indices=np.array([i for i,r in enumerate(p.records) if (p.roles[p.keys[i]]=='H' if H_only else r['cg4_period']==role if p.history and role!='historical_replay' else True)],dtype=int)
                fields={k:[v[i] for i in indices] for k,v in p.features.items()}
                from .representations import subset
                representations={k:subset(v,indices) for k,v in p.representations.items()}
                mask=apply(artifact,fields,representations,cache={'_models':origin.private.get('models',{}),'_population_size':len(indices),'_directory':str(p.work.root),'_max_distance_ops':spec.limits.max_distance_operations,'_membership_memory_bytes':config.max_rss_bytes//3,'_threads':config.threads},check=p.work.check)
                packed={'member_bits':np.packbits(mask['member'],bitorder='little').tobytes().hex(),'available_bits':np.packbits(mask['available'],bitorder='little').tobytes().hex(),'records':len(indices)}
                hashes=[digest([spec.roles.namespace,p.keys[i]]) for i in indices];event_hashes[role]=hashes
                if restatement:
                    before=origin.private.get('memberships',{}).get(claim['membership_artifact'],{}).get(role)
                    before_keys=origin.private.get('population_event_hashes',{}).get(role)
                    if before is None or before_keys is None:raise EvaluationError('Original immutable membership is unavailable; this restatement cannot establish unchanged membership.','restatement_membership_unavailable')
                    if before!=packed or before_keys!=hashes:raise EvaluationError('Outcome-only restatement changed the original planned population or membership.','restatement_membership_changed')
                memberships[claim['membership_artifact']][role]=packed
                evaluated=p.evaluate(adapter,role,indices,mask,artifact)
                history.append({'candidate_id':claim['id'],'hypothesis_id':claim.get('hypothesis_id'),'period':role,
                    'objective':objective.to_dict(),'evidence':evaluated,'state':'exploratory','statistical_confirmation':False,
                    'interpretation':'Descriptive frozen-region restatement; no fresh independent evidence.' if restatement else 'Historical application of a frozen gate; no independent temporal confirmation.'})
                for index in indices[np.flatnonzero(mask['member'])[:spec.limits.examples_per_candidate]]:
                    record=p.records[index]
                    if p.history:
                        ref='cg4_history_'+digest([claim['id'],record['history_fact']])[:24];locators[ref]={'kind':'historical_fact','fact_digest':record['history_fact']}
        from .features import FEATURE_TIME_POLICY
        aid=uuid.uuid4().hex
        data={'schema_version':INVESTIGATION_RESULT,'methodology_id':INVESTIGATION_METHOD,'analysis_id':aid,'generated_at':datetime.now(timezone.utc).isoformat(),
            'name':spec.name+(' — outcome restatement' if restatement else ' — historical replay'),'task':p.store.spec.task.to_dict(),'runs':[],
            'outcomes':{'scope':'Frozen historical selection; observed/mature outcomes only'},'comparison':None,'measurements':[],'checks':[],
            'findings':[{'code':'descriptive_historical_application','priority':'Review','message':'Historical replay and default restatements are descriptive. Original assessments remain immutable.'}],
            'coverage':{'planned':population['planned_records'],'populations':[]},'investigation':{'stage':'restatement' if restatement else 'historical_replay',
                'origin_analysis_id':origin.data['analysis_id'],'origin_analysis_digest':origin.binding['analysis_digest'],'reason':reason,'feature_time_policy':FEATURE_TIME_POLICY,
                'candidates':[],'assessments':[],'strategies':[],'overlap':[],'history':history,'notes':[],
                'family_digest':frozen.get('family_digest') if frozen else None,'inference':'descriptive_only','no_new_independence_claim':True}}
        private={'schema':'confidenceguard.investigation_private/1.0','analysis_id':aid,'config':config.to_dict(),'investigation_spec':spec.to_dict(),
            'spec':spec.evaluation.to_dict() if spec.evaluation else {},'files':p.files,'artifacts':origin.private['artifacts'],'models':origin.private.get('models',{}),
            'locators':locators,'history_binding':p.history,'memberships':memberships,'population_event_hashes':event_hashes,
            'origin_analysis_id':origin.data['analysis_id'],'frozen_hypotheses':frozen}
        private['replay_claims']=[{k:c.get(k) for k in ('id','membership_artifact','objective','hypothesis_id')} for c in claims]
        private['replay_H_only']=H_only
        if p.history:private['workspace_path']=p.history['workspace_path']
        p.verify();return InvestigationResult(data,private,{'status':'completed','peak_workspace_bytes':p.work.peak}).seal()


def replay_investigation(origin,spec,config=None,*,reason,workspace=None,allowed_roots=None,progress=None,cancel=None,restatement=False,H_only=False):
    from .contracts import name
    from .evidence_use import EvidenceUseLedger,record_session
    name(reason)
    if not isinstance(origin,InvestigationResult):raise EvaluationError('Historical replay requires protected original evidence.')
    InvestigationResult.from_dict(origin.to_private_dict(),private=origin.private)
    from .investigation_objectives import legacy_paired_precision
    frozen=origin.private.get('frozen_hypotheses')
    claims=frozen['hypotheses'] if frozen else origin.private.get('replay_claims') or [c for c in origin.data['investigation'].get('candidates',[]) if c['id'] in origin.data['investigation']['shortlist']]
    for claim in claims:
        objective=FailureObjectiveSpec.from_dict(claim['objective'])
        if legacy_paired_precision(objective,origin.private['artifacts'][claim['membership_artifact']]):raise EvaluationError('Earlier paired precision population semantics cannot be silently reinterpreted by historical replay. Preserve the original and start a new investigation.','paired_precision_population_version')
    spec,config,roots=arguments(spec,config or origin.private['config'],allowed_roots)
    if spec.history is None:raise EvaluationError('Historical replay requires an explicit retained historical selection.')
    started=time.monotonic();deadline=started+config.max_seconds
    population=ctx.run(_population,(spec,config,roots,H_only),config,progress=progress,cancel=cancel,deadline=deadline).data
    spec=InvestigationSpec.from_dict(population['effective_spec'])
    from .investigation import historical_workspace
    workspace=historical_workspace(spec,workspace)
    metadata={'purpose':'outcome_restatement' if restatement else 'historical_replay','origin':origin.data['analysis_id'],
              'identity_policy':population['identity_policy'],'local_identity_scope':population['local_identity_scope']}
    if workspace is not None and EvidenceUseLedger(workspace).status()['enabled']:
        EvidenceUseLedger(workspace).record('outcome_disclosure',events=population['events'],units=population['units'],population_digest=population['population_digest'],metadata=metadata,cancel=cancel,deadline=deadline,session_max_bytes=config.max_rss_bytes//8)
    else:record_session('outcome_disclosure',population['events'],population['units'],max_bytes=config.max_rss_bytes//8,workspace=workspace,metadata=metadata)
    result=ctx.run(_replay,(origin,spec,config,roots,population,reason,restatement,H_only),config,progress=progress,cancel=cancel,deadline=deadline)
    result.execution['end_to_end_seconds']=time.monotonic()-started;return result.seal()


def restatement_spec(prior,as_of,reason):
    original=InvestigationSpec.from_dict(prior.private['investigation_spec'])
    if original.history is None:raise EvaluationError('Outcome-only historical restatements require retained prediction and feature snapshots.','restatement_history_required')
    selection=copy.deepcopy(original.history['selection']);prediction_sequence=selection.get('prediction_catalog_sequence') or selection['catalog_sequence']
    original_cutoff=selection.get('prediction_as_of') or selection['as_of']
    selection.update(catalog_sequence=None,as_of=as_of,prediction_catalog_sequence=prediction_sequence,prediction_as_of=original_cutoff)
    return replace(original,history={**original.history,'selection':selection},as_of=original.as_of or original_cutoff)


def annotate_investigation(result,text,*,references=()):
    if not isinstance(text,str) or not text.strip() or len(text)>8192 or any(ord(c)<32 and c not in '\n\t' or 0xd800<=ord(c)<=0xdfff for c in text):raise EvaluationError('Notes require nonempty bounded plain text.')
    InvestigationResult.from_dict(result.to_private_dict(),private=result.private)
    if len(text)>8192 or not isinstance(references,(list,tuple)) or set(references)-result.private.get('locators',{}).keys():raise EvaluationError('Notes require bounded text and retained evidence references.')
    data=copy.deepcopy(result.data);private=copy.deepcopy(result.private);aid=uuid.uuid4().hex;timestamp=datetime.now(timezone.utc).isoformat()
    data.update(analysis_id=aid,generated_at=timestamp);data['investigation']['annotation_parent']={'analysis_id':result.data['analysis_id'],'analysis_digest':result.binding['analysis_digest']}
    data['investigation'].setdefault('notes',[]).append({'id':uuid.uuid4().hex,'text':text,'references':list(references),'recorded_at':timestamp,'visibility':'private','statistical_claim':False})
    private.update(analysis_id=aid)
    return InvestigationResult(data,private,copy.deepcopy(result.execution)).seal()
