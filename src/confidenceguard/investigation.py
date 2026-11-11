"""Unified CG4 application service. Clients never implement analytical decisions."""
from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime,timezone
import copy
import hashlib
import json
import math
from pathlib import Path
import time
import uuid
import numpy as np
from .contracts import EvaluationConfig,EvaluationError,EvaluationSpec,digest,exact
from .investigation_contracts import InvestigationSpec,INVESTIGATION_METHOD,INVESTIGATION_RESULT,ConfirmationSpec
from .feature_contracts import FeatureViewSpec
from .features import normalize,missing_cell,apply_availability,feature_projection,outcome_bound_fields
from .sources import rows,key
from .analytics import literal
from .engine import open_store
from .history_contracts import instant
from .investigation_result import InvestigationResult
from .result import Inspection
from . import compat


CG4_RESULT_BYTES=256*1024**2


def configuration(config=None):
    """CG4 evidence budget; explicit shared-config instances stay authoritative."""
    if config is None:return EvaluationConfig(result_bytes=CG4_RESULT_BYTES)
    if isinstance(config,dict):return EvaluationConfig.from_dict({'result_bytes':CG4_RESULT_BYTES,**config})
    if not isinstance(config,EvaluationConfig):raise EvaluationError('EvaluationConfig required.')
    return config


def arguments(spec,config,allowed_roots):
    if isinstance(spec,dict):spec=InvestigationSpec.from_dict(spec)
    if not isinstance(spec,InvestigationSpec):raise EvaluationError('InvestigationSpec required.')
    config=configuration(config)
    paths=[s.path for s in spec.evaluation.sources] if spec.evaluation else [spec.history['workspace_path']]
    paths.extend(r.matrix_path for r in spec.representations if r.matrix_path)
    paths.extend(r.keys_source.path for r in spec.representations if r.keys_source)
    roots=set(str(Path(p).absolute().parent) for p in paths)
    roots.update(str(Path(r.model_directory).absolute()) for r in spec.representations if r.model_directory)
    if allowed_roots is not None:roots=set(str(Path(p).absolute()) for p in allowed_roots)
    return spec,config,tuple(sorted(roots))


def historical_workspace(spec,workspace):
    """Bind tracking to the retained source after its worker admission succeeds."""
    if spec.history is None:return workspace
    from .workspace import ReliabilityWorkspace
    root=Path(spec.history['workspace_path']).resolve()
    if workspace is not None:
        supplied=Path(workspace.path if isinstance(workspace,ReliabilityWorkspace) else workspace).resolve()
        if supplied!=root:raise EvaluationError('Exposure tracking must use the admitted historical workspace.','workspace_identity')
    return workspace if isinstance(workspace,ReliabilityWorkspace) else ReliabilityWorkspace(root)


def _roles(spec,records,raw):
    assignments={};entity_roles={};partitions={}
    for role,values in spec.roles.partitions.items():
        for value in values:
            token=json.dumps(value,ensure_ascii=True) if isinstance(value,list) else value
            if token in partitions:raise EvaluationError('CG4 partitions overlap.','role_overlap')
            partitions[token]=role
    for record in records:
        event=record['event_key'];entity=record.get('entity_key')
        unit=entity if spec.roles.unit=='entity' else event
        if unit is None:raise EvaluationError('Entity-level discovery requires explicit entity keys.','entity_keys_required')
        if spec.roles.column:
            role=spec.roles.values.get(raw.get(record['ordinal'],{}).get(spec.roles.column))
        elif partitions:role=partitions.get(unit)
        else:
            fraction=int(digest([spec.roles.namespace,unit,spec.roles.seed]),16)/(2**256)
            a,b,_=spec.roles.proportions;role='D' if fraction<a else 'S' if fraction<a+b else 'H'
        if role not in {'D','S','H'}:raise EvaluationError('Every admitted event requires one CG4 role.','unassigned_role')
        if entity is not None and entity in entity_roles and entity_roles[entity]!=role:raise EvaluationError('An entity crosses D/S/H roles.','role_overlap')
        if entity is not None:entity_roles[entity]=role
        assignments[event]=role
    return assignments


class Prepared:
    def __init__(self,spec,config,roots,work,store,*,history=None,identity_only=False):
        from .investigation_contracts import resolve_objective_units
        spec=replace(spec,objectives=tuple(resolve_objective_units(o,store.spec.task) for o in spec.objectives))
        self.spec=spec;self.config=config;self.roots=roots;self.work=work;self.store=store;self.history=history
        self.files=copy.deepcopy(store.sources);self.models={};self.representations={};self.features={};self.definitions={}
        self.known_outcome_features=outcome_bound_fields(store.spec,spec.features,store.sources) if history is None else set()
        self.diagnostic_fits=0
        run=next(r for r in store.spec.runs if r.id==spec.objectives[0].run);self.primary=run;table=store.run_tables[run.id]
        cursor=store.con.execute(f'SELECT * FROM {table} ORDER BY event_key');columns=[v[0] for v in cursor.description]
        self.records=[dict(zip(columns,row)) for row in cursor.fetchall()];self.keys=[r['event_key'] for r in self.records]
        if None in self.keys or len(set(self.keys))!=len(self.keys):raise EvaluationError('CG4 requires unique explicit event identities.','investigation_identity')
        self.run_records={run.id:{r['event_key']:r for r in self.records}}
        for other in store.spec.runs:
            if other.id==run.id:continue
            cursor=store.con.execute(f'SELECT * FROM {store.run_tables[other.id]} ORDER BY event_key');fields=[v[0] for v in cursor.description]
            records=[dict(zip(fields,row)) for row in cursor.fetchall()]
            if None in [r['event_key'] for r in records] or len({r['event_key'] for r in records})!=len(records):raise EvaluationError('Every admitted model requires unique explicit event identities.','investigation_identity')
            self.run_records[other.id]={r['event_key']:r for r in records}
            for record in records:
                canonical=self.run_records[run.id].get(record['event_key'])
                if canonical is not None and record.get('entity_key') is not None and record['entity_key']!=canonical.get('entity_key'):raise EvaluationError('Shared event entity assertions differ across model runs.','investigation_entity_conflict')
        self.raw={}
        if not history:
            self.raw={int(ordinal):json.loads(payload) for ordinal,payload in rows(store.con,f'SELECT ordinal,payload FROM {store.tables[run.source]}')}
        else:
            self.raw={r['ordinal']:json.loads(r.get('history_context') or '{}') for r in self.records}
        self.roles=_roles(spec,self.records,self.raw);self.index={k:i for i,k in enumerate(self.keys)}
        self.identity_fingerprint=digest({'keys':self.keys,'roles':self.roles,'namespace':spec.roles.namespace,
            'files':{sid:{k:v.get(k) for k in ('sha256','bytes')} for sid,v in self.files.items()}})
        # D sampling is declared and deterministic; S/H are never subsampled.
        discovery=[k for k in self.keys if self.roles[k]=='D']
        admitted=set(sorted(discovery,key=lambda k:digest([spec.roles.seed,k]))[:spec.limits.diagnostic_rows])
        self.selected={role:np.array([self.roles[k]==role and (role!='D' or k in admitted) for k in self.keys]) for role in ('D','S','H')}
        for run in store.spec.runs:
            table=store.run_tables[run.id]
            for col,typ in (('cg4_role','VARCHAR'),('cg4_selected','BOOLEAN'),('cg4_member','BOOLEAN'),('cg4_available','BOOLEAN')):store.con.execute(f'ALTER TABLE {table} ADD COLUMN {col} {typ}')
            store.con.execute('CREATE OR REPLACE TEMP TABLE cg4_roles(event_key VARCHAR,role VARCHAR,selected BOOLEAN)')
            compat.insert_rows(store.con,'cg4_roles',[(k,self.roles[k],self.roles[k]!='D' or k in admitted) for k in self.keys])
            store.con.execute(f'UPDATE {table} SET cg4_role=c.role,cg4_selected=c.selected FROM cg4_roles c WHERE {table}.event_key=c.event_key')
        if identity_only:
            self.fingerprint=self.identity_fingerprint;return
        outcome=getattr(store,'outcomes',None)
        retain_status=not history and outcome is not None and outcome.status_column is not None
        estimated=len(self.keys)*(max(1,sum(len(v.fields) for v in spec.features))*320+(64 if retain_status else 0))
        if estimated>config.max_rss_bytes*.6:raise EvaluationError('Typed feature materialization exceeds admitted memory; select an explicit smaller population or increase the limit.','feature_memory_admission')
        self.outcome_statuses=None
        if retain_status:
            self.outcome_statuses={}
            # Reuse the authoritative unique outcome join. Keep this descriptive
            # sidecar out of normalized rows and population digests: the source
            # fingerprint already binds it, and legacy numerical retries retain
            # their original normalized population identity.
            for event,payload in rows(store.con,'SELECT event_key,payload FROM okeys WHERE multiplicity=1 AND event_key IS NOT NULL'):
                if event not in self.index:continue
                raw=json.loads(payload)
                status=outcome.status_values.get(raw.get(outcome.status_column),'unresolved')
                if store.spec.as_of:
                    tick,state=compat.clock(raw.get(outcome.available_at.column),outcome.available_at) if outcome.available_at else (None,'undeclared')
                    if state!='valid' or tick>store.cutoff:status='unavailable_as_of'
                self.outcome_statuses[event]=status
                if len(self.outcome_statuses)%512==0:work.check('outcome status provenance')
        self.load_features()
        from .representations import supplied,encode
        for representation in spec.representations:
            owner=representation.run or self.primary.id
            if owner not in self.run_records:raise EvaluationError('Representation owner run is absent.','representation_owner')
            if representation.kind=='retained':
                if not history:raise EvaluationError('Retained representations require a historical selection.','representation_not_retained')
                rep=self.retained_representation(representation);files={}
            elif representation.kind=='supplied':rep,files=supplied(representation,self.keys,work,config,roots)
            else:rep,files=encode(representation,self.keys,self.features,work,config,spec.limits,roots,Path(store.spec.sources[0].path).parent)
            if representation.kind=='supplied':
                asof=instant(spec.as_of) if spec.as_of else None
                for i,record in enumerate(self.records):
                    if not rep['available'][i]:continue
                    tick,state=rep['availability'].get(self.keys[i],(None,'undeclared'))
                    owner_record=self.run_records[owner].get(record['event_key'])
                    if owner_record is None:rep['available'][i]=False;rep['reason'][i]='owner_prediction_unavailable';continue
                    clock=asof if spec.feature_time_view=='retrospective' else owner_record.get('prediction_tick')
                    admitted=representation.availability=='at_decision' or state=='valid' and clock is not None and tick<=clock
                    if not admitted:rep['available'][i]=False;rep['reason'][i]='content_availability_unknown' if tick is None else 'content_unavailable_at_cutoff'
            self.representations[representation.id]=rep;self.files.update(files)
        from .features import FEATURE_TIME_POLICY
        self.fingerprint=digest({'spec':spec.to_dict(),'config':config.to_dict(),
            'files':{sid:{k:v.get(k) for k in ('sha256','bytes')} for sid,v in self.files.items()},
            'history':history,'keys':self.keys,'roles':self.roles,'method':INVESTIGATION_METHOD,
            **({'feature_time_policy':FEATURE_TIME_POLICY} if any(v.information_cutoff for v in spec.features) else {})})

    def reserve_diagnostic_fit(self):
        if self.diagnostic_fits>=self.spec.limits.diagnostic_fits:raise EvaluationError('Diagnostic fits, including stability refits, exhausted the explicit budget.','diagnostic_fit_limit')
        self.diagnostic_fits+=1;self.work.check('diagnostic fit reservation')

    def load_features(self):
        evaluation=self.store.spec;run=self.primary;by_run={r.id:r for r in evaluation.runs};asof=instant(self.spec.as_of) if self.spec.as_of else None
        for view in self.spec.features:
            binding=by_run.get(view.run or run.id)
            if binding is None:raise EvaluationError('Unknown feature owner run.')
            source=view.source or binding.source
            if self.history:
                mapping={r['event_key']:json.loads(r.get('history_context') or '{}') for r in self.records}
            else:
                if source not in self.store.tables:raise EvaluationError('Feature source is absent.')
                mapping={};columns=view.key_columns or binding.key_columns
                for ordinal,payload in rows(self.store.con,f'SELECT ordinal,payload FROM {self.store.tables[source]}'):
                    row=json.loads(payload);event=key(row,columns,None)
                    if event is None or event in mapping:raise EvaluationError('Feature joins require unique explicit keys.','feature_key_conflict')
                    mapping[event]=row
            for field in view.fields:
                fid=view.id+'.'+field.id;self.definitions[fid]={'view':view.to_dict(),'field':field.to_dict()};values=[]
                for record in self.records:
                    owner_record=self.run_records[binding.id].get(record['event_key'])
                    if owner_record is None:values.append(missing_cell(field.kind));continue
                    raw=mapping.get(record['event_key'])
                    if raw is None or field.column not in raw:values.append(missing_cell(field.kind));continue
                    clock=field.available_at or view.available_at
                    available,state=compat.clock(raw.get(clock.column),clock) if clock else (None,'undeclared')
                    effective,_=compat.clock(raw.get(field.effective_at.column),field.effective_at) if field.effective_at else (None,'undeclared')
                    cell=normalize(raw.get(field.column),field,available_ns=available,effective_ns=effective,availability_state=state)
                    cutoff,cutoff_state=compat.clock(raw.get(view.information_cutoff.column),view.information_cutoff) if view.information_cutoff else (owner_record.get('prediction_tick'),None)
                    values.append(apply_availability(cell,view=self.spec.feature_time_view,cutoff_ns=cutoff,cutoff_state=cutoff_state,as_of_ns=asof,declaration=view.availability))
                self.features[fid]=values

    def role_data(self,role):
        mask=self.selected[role];indices=np.flatnonzero(mask)
        features={fid:[values[i] for i in indices] for fid,values in self.features.items()}
        from .representations import subset
        representations={rid:subset(rep,indices) for rid,rep in self.representations.items()}
        return indices,features,representations

    def set_membership(self,objective,role,indices,membership,artifact):
        table=objective.table;self.store.con.execute('CREATE OR REPLACE TEMP TABLE cg4_mask(event_key VARCHAR,member BOOLEAN,available BOOLEAN)')
        compat.insert_rows(self.store.con,'cg4_mask',[(self.keys[i],bool(m),bool(a)) for i,m,a in zip(indices,membership['member'],membership['available'])])
        self.store.con.execute(f'UPDATE {table} SET cg4_member=c.member,cg4_available=c.available FROM cg4_mask c WHERE {table}.event_key=c.event_key')
        if objective.reference:
            table=objective.reference.table
            self.store.con.execute(f'UPDATE {table} SET cg4_member=c.member,cg4_available=c.available FROM cg4_mask c WHERE {table}.event_key=c.event_key')
        self.store.cg4_binding={'gate':artifact['artifact_digest'],'role':role,'population':digest([self.keys[i] for i in indices]),'input':self.fingerprint}

    def evaluate(self,objective,role,indices,membership,artifact):
        self.set_membership(objective,role,indices,membership,artifact)
        scope=f"cg4_role={literal(role)} AND cg4_selected";supported=scope+' AND cg4_available'
        member_scope=supported+' AND cg4_member';control_scope=supported+('' if objective.spec.comparator=='overall' else ' AND NOT cg4_member')
        if objective.reference:
            ref=objective.reference
            common=f'event_key IN (SELECT event_key FROM {ref.table} WHERE ({scope}) AND ({ref.pair_eligible_sql}))'
            member_scope+=f' AND ({objective.pair_eligible_sql}) AND ({common})'
            control_scope=supported+f' AND cg4_member AND ({ref.pair_eligible_sql}) AND event_key IN (SELECT event_key FROM {objective.table} WHERE ({scope}) AND ({objective.pair_eligible_sql}))'
            right=ref.evaluate(control_scope,role+'/paired_reference')
        elif objective.spec.comparator=='reference_period':
            member_scope+=' AND cg4_period='+literal(objective.spec.current_period)
            control_scope=supported+' AND cg4_member AND cg4_period='+literal(objective.spec.reference_period)
            right=objective.evaluate(control_scope,role+'/reference_period')
        else:right=objective.evaluate(control_scope,role+'/comparator') if objective.spec.comparator!='ceiling' else None
        left=objective.evaluate(member_scope,role+'/members')
        from .investigation_objectives import adverse
        effect=adverse(objective.spec,left,right)
        n=len(indices);available=int(np.count_nonzero(membership['available']));member=int(np.count_nonzero(membership['member']))
        support=right['support'] if right else 0
        counts=[x for result in (left,right) if result for x in result.get('measurement',{}).get('sensitive_counts',[])]
        from collections import Counter
        unavailable=Counter(str(reason) for reason,a in zip(membership['reason'],membership['available']) if not a)
        outcome_states=Counter('observed_eligible' if self.records[i]['outcome_valid'] else self.records[i].get('outcome_reason') or 'invalid_or_unavailable' for i in indices)
        counts.extend(outcome_states.values())
        status_states=Counter()
        if getattr(self,'outcome_statuses',None) is not None:
            for i in indices:
                record=self.records[i];reason=record.get('outcome_reason')
                state='unavailable_as_of' if reason in {'outcome_not_available_as_of','unresolved_outcome_availability'} else self.outcome_statuses.get(self.keys[i],'no_unique_snapshot')
                status_states[state]+=1
            counts.extend(status_states.values())
        evidence={'planned':n,'available':available,'members':member,'nonmembers':available-member,'unavailable':n-available,
                'conditional_members':left['support'],'conditional_nonmembers':support,'effect':effect if effect is not None and math.isfinite(effect) else None,
                'effect_state':'finite' if effect is not None and math.isfinite(effect) else 'positive_infinity' if effect==math.inf else 'negative_infinity' if effect==-math.inf else 'undefined',
                'member_metric':left,'comparator_metric':right,'sensitive_counts':counts,
                'membership_unavailable_reasons':dict(unavailable),'outcome_observation_states':dict(outcome_states)}
        if status_states:evidence['outcome_status_states']=dict(status_states)
        return evidence

    def verify(self):
        if not self.history:self.store.verify()
        for info in self.files.values():
            if info.get('path') and info.get('sha256'):compat.capture(info['path'],self.roots,expected=info)


@contextmanager
def prepared(spec,config,roots,progress=None,*,identity_only=False):
    from threadpoolctl import threadpool_limits
    with threadpool_limits(limits=config.threads):
        with _prepared(spec,config,roots,progress,identity_only=identity_only) as p:yield p


@contextmanager
def _prepared(spec,config,roots,progress=None,*,identity_only=False):
    if spec.history:
        from .investigation_history import prepare_history
        with prepare_history(spec,config,roots,progress,identity_only=identity_only) as packet:yield packet
        return
    projection=feature_projection(spec,spec.evaluation) if not identity_only else {s.id:({spec.roles.column} if spec.roles.column else set()) for s in spec.evaluation.sources}
    work,store,_=open_store(spec.evaluation,config,roots,progress,projection=projection)
    try:yield Prepared(spec,config,roots,work,store,identity_only=identity_only)
    finally:work.close()


def _inspect(spec,config,roots,*,progress=None):
    with prepared(spec,config,roots,progress) as p:
        from .investigation_objectives import bind
        from .investigation_reconciliation import SELECTION_POLICY,selection_fingerprint
        objectives=[bind(o,p.store).identity for o in spec.objectives]
        data={'schema_version':'confidenceguard.investigation_inspection/1.0','fingerprint':selection_fingerprint(p.fingerprint),
              'selection_policy':SELECTION_POLICY,
              'effective_spec':p.spec.to_dict(),'effective_config':config.to_dict(),'objectives':objectives,
              'population':{'planned':len(p.keys),'roles':{r:int(mask.sum()) for r,mask in p.selected.items()},'D_sampling_limit':spec.limits.diagnostic_rows},
              'features':{fid:{'kind':definition['field']['kind'],'role':definition['field']['role']} for fid,definition in p.definitions.items()},
              'representations':{rid:{'dimensions':rep['vectors'].shape[1],'producer':rep['provenance'].get('producer','supplied')} for rid,rep in p.representations.items()},
              'H_outcomes_disclosed':False,'confirmation_is_separate':True}
        heads=sum((2 if o.direction in {'absolute','nominal_shortfall'} or o.metric in {'bias','calibration_residual','reliability_diagram'} else 1)*
            (3 if o.comparator=='reference_period' else 1) for o in p.spec.objectives)
        stability_targets=sum(sorted((3 if o.comparator=='reference_period' else 1 for o in p.spec.objectives),reverse=True)[:spec.limits.shortlist])
        data['diagnostic_fit_admission']={'maximum_fits':spec.limits.diagnostic_fits,'counts_stability_refits':True,
            'initial_fit_ceiling':2*heads if 'catboost' in spec.strategies else 0,
            'stability_fit_ceiling':4*spec.limits.stability_replicates*stability_targets if 'catboost' in spec.strategies else 0,
            'constant_or_insufficient_targets_do_not_fit':True,'enforcement':'Reserve every actual fit before native training; refuse on exhaustion without silently reducing the profile.'}
        geometry_strategies=len(set(spec.strategies)&{'geometric','landmark'});representations=len(p.representations)
        target_sets=sum(3 if o.comparator=='reference_period' else 1 for o in p.spec.objectives)
        data['geometry_fit_admission']={'initial_fit_ceiling':target_sets*representations*geometry_strategies,
            'stability_fit_ceiling':spec.limits.stability_replicates*stability_targets*representations*geometry_strategies,
            'maximum_distance_coordinate_operations_per_fit':spec.limits.max_distance_operations,
            'distance_budget_scope':'Per strategy/representation/diagnostic-target fit, shared across its admitted geometry spaces; membership application has its own admission. The global operation deadline/RSS/workspace limits still apply.',
            'fit_count_is_an_upper_bound_not_a_capacity_guarantee':True}
        data['population_baseline_admission']={'policy':'declared_ceiling_population_baseline_v1',
            'maximum_candidates':sum(o.comparator=='ceiling' for o in spec.objectives),
            'scope':'One fixed whole-population gate per ceiling objective with adequate D conditional support, independent of chosen discovery strategies. No model fit or search nodes; S uses authoritative metrics.'}
        p.verify();return Inspection(data,{'status':'completed','peak_workspace_bytes':p.work.peak})


def inspect_investigation(spec,config=None,*,allowed_roots=None,progress=None,cancel=None):
    spec,config,roots=arguments(spec,config,allowed_roots)
    return compat.supervise(_inspect,(spec,config,roots),config,progress=progress,cancel=cancel).to_dict()


def propose_diagnostic_targets(strategy,features,representations,objective,targets,limits,*,directory,models,threads,reserve_fit,check,memory_budget):
    """Fixed strategies, separate D targets, one admitted candidate/node budget."""
    from . import discovery_rules,discovery_boosted,discovery_regions
    historical=objective.spec.comparator=='reference_period';pools=[];statuses=[];remaining=limits.max_nodes
    for target_index,target in enumerate(targets):
        eligible=target['eligible'];loss=target['loss'];profile=limits
        binding=copy.deepcopy(target.get('binding',{}))
        binding.update(admitted_D_records=len(eligible),admitted_defined_D_targets=int(eligible.sum()))
        if historical and (int(eligible.sum())<limits.minimum_discovery_support or strategy=='structured' and remaining==0):
            found=[];status={'execution':'not_run','reason':'shared_search_budget_exhausted' if strategy=='structured' and remaining==0 else 'insufficient_D_target_support',
                'search_complete':remaining>0}
        else:
            if historical and strategy=='structured':
                pending=sum(int(t['eligible'].sum())>=limits.minimum_discovery_support for t in targets[target_index:])
                profile=replace(limits,max_nodes=(remaining+pending-1)//pending)
            if strategy=='structured':found,status=discovery_rules.propose(features,eligible,loss,objective,profile,check)
            elif strategy=='catboost':found,status=discovery_boosted.propose(features,eligible,loss,objective,profile,directory,check,models=models,threads=threads,reserve_fit=reserve_fit)
            else:
                found=[];spaces=[]
                for representation in representations.values():
                    proposals,space=discovery_regions.propose(representation,eligible,loss,objective,profile,strategy=strategy,check=check,models=models,memory_budget=memory_budget)
                    found.extend(proposals);spaces.append(space)
                status={'strategy':strategy,'execution':'completed' if representations else 'not_run','reason':None if representations else 'no_representation','representations':spaces,
                    'qualification':'original_NUMEK_failed_promotion_profile' if strategy=='landmark' else 'requires_qualification'}
                if strategy=='landmark':
                    from .investigation_contracts import LANDMARK_PROMOTION_EVIDENCE
                    status['qualification_evidence']=dict(LANDMARK_PROMOTION_EVIDENCE)
        if not historical:return found,status
        remaining-=status.get('nodes',0)
        for proposal in found:proposal['diagnostic_target_binding']={**binding,'diagnostic_head':proposal.get('head')}
        pools.append(found);statuses.append({**status,'diagnostic_target_binding':binding})
    # Do not compare unlike head utilities or multiply the candidate cap.
    proposals=[]
    for position in range(max((len(pool) for pool in pools),default=0)):
        for pool in pools:
            if position<len(pool):proposals.append(pool[position])
            if len(proposals)>=limits.candidates_per_strategy:break
        if len(proposals)>=limits.candidates_per_strategy:break
    status={'strategy':strategy,'execution':'completed','qualification':'requires_historical_objective_family_qualification',
        'diagnostic_target_policy':'historical_period_heads_and_matched_entity_delta_v1','diagnostic_targets':statuses,
        'candidate_budget':limits.candidates_per_strategy,'candidate_admission':'D-only round-robin across declared targets; authoritative S effects select candidates.'}
    if strategy=='structured':status.update(nodes=limits.max_nodes-remaining,search_complete=all(s.get('search_complete',False) for s in statuses),
        node_budget_scope='shared_per_strategy_and_objective',node_allocation='Remaining nodes split across remaining eligible targets; unused nodes pass forward.')
    if strategy=='landmark':
        from .investigation_contracts import LANDMARK_PROMOTION_EVIDENCE
        status.update(qualification='original_NUMEK_failed_promotion_profile',qualification_evidence=dict(LANDMARK_PROMOTION_EVIDENCE))
    return proposals,status


def _discover(spec,config,roots,expected,reserved_identity=None,*,progress=None):
    from .investigation_objectives import bind
    from .investigation_membership import apply
    from .investigation_reconciliation import selection_fingerprint
    from . import discovery_rules,discovery_boosted,discovery_regions
    started=time.monotonic()
    with prepared(spec,config,roots,progress) as p:
        spec=p.spec
        if reserved_identity and reserved_identity!=p.identity_fingerprint:raise EvaluationError('Discovery population changed after exposure reservation.','stale_confirmation')
        if expected and expected!=selection_fingerprint(p.fingerprint):raise EvaluationError('Investigation inspection is stale.','stale_confirmation')
        candidates=[];strategies=[];artifacts={};models={};locators={};memberships={};cache={'_directory':str(p.work.root),'_max_distance_ops':spec.limits.max_distance_operations,'_models':models,'_membership_memory_bytes':config.max_rss_bytes//3,'_threads':config.threads}
        surrogate_predicates={'_structured_masks_enabled':True}
        di,df,dr=p.role_data('D');si,sf,sr=p.role_data('S')
        for objective_spec in spec.objectives:
            objective=bind(objective_spec,p.store);dkeys,target_definitions=objective.discovery_targets()
            # Training query includes all assigned D; use exactly admitted D keys.
            pos={key:i for i,key in enumerate(dkeys)};selection=[pos[p.keys[i]] for i in di]
            target_definitions=[{**target,'eligible':target['eligible'][selection],'loss':target['loss'][selection]} for target in target_definitions]
            proposed=[]
            if objective_spec.comparator=='ceiling':
                # A uniform failure above a fixed ceiling has no excess over
                # its own D mean. Admit the predeclared full population rather
                # than requiring heterogeneous loss to discover this claim.
                from .investigation_membership import seal
                support=int(target_definitions[0]['eligible'].sum())
                admitted=support>=spec.limits.minimum_discovery_support
                if admitted:
                    proposed.append({'artifact':seal('structured',{'clauses':[]},objective=objective.identity),
                        'head':'population','complexity':0,'proposal_source':'declared_ceiling_population_baseline_v1'})
                strategies.append({'strategy':'population_baseline','objective':objective_spec.id,
                    'execution':'completed' if admitted else 'not_run',
                    'reason':None if admitted else 'insufficient_D_target_support',
                    'qualification':'Fixed population definition; authoritative S evaluation, not a learned recovery guarantee.',
                    'D_conditional_support':support,'candidate_budget':1,'uses_native_fit_or_search_nodes':False})
            for strategy in spec.strategies:
                if progress:progress({'stage':'failure_discovery','strategy':strategy,'objective':objective_spec.id})
                result,status=propose_diagnostic_targets(strategy,df,dr,objective,target_definitions,spec.limits,directory=p.work.root,models=models,
                    threads=config.threads,reserve_fit=p.reserve_diagnostic_fit,check=p.work.check,memory_budget=config.max_rss_bytes//3)
                strategies.append({**status,'objective':objective_spec.id,'diagnostic_target_support':{
                    **objective.training_support['D'],'admitted_D_records':len(di),'admitted_defined_targets':int(target_definitions[0]['eligible'].sum())}});proposed.extend(result)
            seen={};dcache={**cache,'_population_size':len(di)};scache={**cache,'_population_size':len(si)}
            # S pointwise targets stay fixed while membership columns change
            # per gate. Read the example target once rather than per gate.
            raw_loss=dict(p.store.con.execute(f'SELECT event_key,({objective.loss_sql}) FROM {objective.table} WHERE cg4_role=\'S\'').fetchall()) if proposed else {}
            losses=np.array([raw_loss.get(p.keys[i]) if raw_loss.get(p.keys[i]) is not None else np.nan for i in si],dtype=float)
            historical=objective.spec.comparator=='reference_period'
            example_periods=dict(p.store.con.execute(f'SELECT event_key,cg4_period FROM {objective.table} WHERE cg4_role=\'S\'').fetchall()) if proposed and historical else {}
            for proposal in proposed:
                artifact=proposal['artifact'];aid=artifact['artifact_digest']
                if aid in seen:
                    binding=proposal.get('diagnostic_target_binding')
                    if binding and binding not in seen[aid]['diagnostic_target_bindings']:seen[aid]['diagnostic_target_bindings'].append(copy.deepcopy(binding))
                    continue
                artifacts[aid]=artifact
                dm=apply(artifact,df,dr,cache=dcache,check=p.work.check);sm=apply(artifact,sf,sr,cache=scache,check=p.work.check)
                memberships[aid]={role:{'member_bits':np.packbits(m['member'],bitorder='little').tobytes().hex(),'available_bits':np.packbits(m['available'],bitorder='little').tobytes().hex(),'records':len(m['member'])} for role,m in (('D',dm),('S',sm))}
                d=p.evaluate(objective,'D',di,dm,artifact);s=p.evaluate(objective,'S',si,sm,artifact)
                cid=digest([objective_spec.id,aid])[:32]
                examples=[]
                adverse_loss=losses if historical else losses*(-1 if proposal.get('head')=='negative' else 1)
                members=np.flatnonzero(sm['member']);outside=np.flatnonzero(sm['available']&~sm['member']);example_indices=[]
                finite=members[~np.isnan(adverse_loss[members])]
                if len(finite):
                    ordered=finite[np.argsort(adverse_loss[finite],kind='stable')]
                    example_indices.extend(((int(ordered[-1]),'higher_base_pointwise_loss_member' if historical else 'higher_diagnostic_loss_member'),
                                            (int(ordered[0]),'lower_base_pointwise_loss_member' if historical else 'lower_diagnostic_loss_member')))
                margin=sm.get('margin')
                if margin is not None:
                    supported=np.flatnonzero(sm['available']&np.isfinite(margin))
                    if len(supported):example_indices.append((int(supported[np.argmin(abs(margin[supported]))]),'boundary_case'))
                if len(outside):example_indices.append((int(outside[0]),'outside_comparison'))
                example_indices.extend((int(i),'representative_member') for i in members)
                seen_examples=set()
                for local_index,selection_reason in example_indices:
                    if local_index in seen_examples:continue
                    seen_examples.add(local_index)
                    if len(examples)>=spec.limits.examples_per_candidate:break
                    index=int(si[local_index]);record=p.records[index];ref='cg4_ref_'+digest([cid,p.keys[index]])[:24]
                    if p.history:locator={'kind':'historical_fact','fact_digest':record['history_fact']}
                    else:
                        source=next(source for source in p.store.spec.sources if source.id==p.primary.source)
                        columns=sorted(p.raw[record['ordinal']]);row=p.raw[record['ordinal']]
                        locator={'source':source.to_dict(),'ordinal':record['ordinal'],'columns':columns,'projection_digest':digest({c:row.get(c) for c in columns})}
                    locators[ref]=locator;example={'reference':ref,'selection':selection_reason,'outcome_values_disclosed':False}
                    if historical:example.update(period=example_periods.get(p.keys[index]),
                        period_state='observed' if p.keys[index] in example_periods else 'unavailable_for_objective_run',
                        diagnostic_context='Base pointwise example, not a per-event historical contrast or paired-proxy explanation.')
                    examples.append(example)
                candidate={'id':cid,'objective':objective_spec.to_dict(),'strategy':artifact['kind'],'membership_artifact':aid,
                    'D':d,'S':s,'head':proposal.get('head'),'complexity':proposal.get('complexity',1),
                    'definition':artifact['parameters'] if artifact['kind']=='structured' else 'Frozen '+artifact['kind']+' membership',
                    'explanation':{'kind':'exact_predicate' if artifact['kind']=='structured' else 'approximate','fidelity':None},
                    'examples':examples,'state':'exploratory','selection_population':'S','H_assessed':False,
                    '_S_mask':np.packbits(sm['member'],bitorder='little').tobytes().hex()}
                if proposal.get('diagnostic_target_binding'):candidate['diagnostic_target_bindings']=[copy.deepcopy(proposal['diagnostic_target_binding'])]
                if proposal.get('proposal_source'):candidate['proposal_source']=proposal['proposal_source']
                from .investigation_reconciliation import explanation
                candidate['explanation']=explanation(candidate,artifact,df,sf,dr,sr,dm,sm,spec.limits,p.work.check,predicate_cache=surrogate_predicates)
                candidates.append(candidate);seen[aid]=candidate
        from .investigation_reconciliation import reconcile,adverse_value,marginal_selection_evidence
        candidates.sort(key=lambda c:(-(adverse_value(c) if adverse_value(c) is not None else -math.inf),-c['S']['conditional_members'],c['complexity'],c['id']))
        by_candidate={c['id']:c for c in candidates};objective_adapters={o.id:bind(o,p.store) for o in spec.objectives}
        def selected_contribution(candidate,previous):
            return marginal_selection_evidence(p,candidate,previous,candidates=by_candidate,memberships=memberships,
                                              indices=si,objective=objective_adapters[candidate['objective']['id']])
        candidates,overlap,selected=reconcile(candidates,spec.limits.shortlist,len(si),selected_contribution)
        from .investigation_reconciliation import stability
        stability(p,candidates,selected,artifacts,models,p.work.check)
        for c in candidates:c.pop('_S_mask',None)
        from .features import FEATURE_TIME_POLICY
        data={'schema_version':INVESTIGATION_RESULT,'methodology_id':INVESTIGATION_METHOD,'analysis_id':uuid.uuid4().hex,
              'generated_at':datetime.now(timezone.utc).isoformat(),'name':spec.name,'task':p.store.spec.task.to_dict(),
              'runs':[{'id':r.id,'display_name':r.model.id,'role':r.role,'version_alias':r.model.version} for r in p.store.spec.runs],
              'outcomes':{'definition':'Authoritative supplied/historical snapshot','H_outcomes_disclosed':False},'comparison':None,
              'measurements':[],'checks':[],'findings':[{'code':'exploratory_discovery','priority':'Review','message':'D/S selection evidence is exploratory. Freeze hypotheses before independent assessment.'}],
              'coverage':{'planned':len(p.keys),'roles':{r:int(mask.sum()) for r,mask in p.selected.items()},'populations':[]},
              'investigation':{'stage':'discovery','feature_time_policy':FEATURE_TIME_POLICY,'fingerprint':selection_fingerprint(p.fingerprint),'candidates':candidates,'shortlist':selected,'overlap':overlap,
                    'selection_policy':overlap['selection_policy'],
                    'strategies':strategies,'assessments':[],'history':[],'notes':[],'qualification':'No discovery recovery guarantee is inferred from predictive accuracy.'}}
        used={c['membership_artifact'] for c in candidates};artifacts={k:v for k,v in artifacts.items() if k in used}
        from .investigation_membership import dependency_digests
        used_models=set().union(*(dependency_digests(a) for a in artifacts.values())) if artifacts else set()
        from .evidence_use import population_identifiers
        ds_events,ds_units=population_identifiers(p,[i for i,k in enumerate(p.keys) if p.roles[k] in {'D','S'}])
        private={'schema':'confidenceguard.investigation_private/1.0','analysis_id':data['analysis_id'],'config':config.to_dict(),
                 'investigation_spec':spec.to_dict(),'spec':spec.evaluation.to_dict() if spec.evaluation else {},'files':p.files,
                 'artifacts':artifacts,'models':{k:v for k,v in models.items() if k in used_models},'locators':locators,
                 'memberships':{k:v for k,v in memberships.items() if k in used},
                 'population_event_hashes':{role:[digest([spec.roles.namespace,p.keys[i]]) for i in np.flatnonzero(p.selected[role])] for role in ('D','S')},
                 'D_S_units':ds_units,'D_S_events':ds_events,
                 'history_binding':p.history,'known_outcome_features':sorted(p.known_outcome_features)}
        if p.history:private['workspace_path']=p.history['workspace_path']
        p.verify();return InvestigationResult(data,private,{'status':'completed','peak_workspace_bytes':p.work.peak,'duration_seconds':time.monotonic()-started,'diagnostic_fits':p.diagnostic_fits}).seal()


def _discovery_population(spec,config,roots,*,progress=None):
    with prepared(spec,config,roots,progress,identity_only=True) as p:
        from .evidence_use import population_identifiers
        events,units=population_identifiers(p,[i for i,k in enumerate(p.keys) if p.roles[k] in {'D','S'}])
        return Inspection({'fingerprint':p.fingerprint,'effective_spec':p.spec.to_dict(),'events':events,'units':units,'population_digest':digest([events,units,p.fingerprint])},{'status':'completed','peak_workspace_bytes':p.work.peak})


def investigate(spec,config=None,*,allowed_roots=None,expected_fingerprint=None,progress=None,cancel=None,workspace=None,request_id=None):
    spec,config,roots=arguments(spec,config,allowed_roots)
    started=time.monotonic();deadline=started+config.max_seconds
    from .evidence_use import record_session
    population=compat.supervise(_discovery_population,(spec,config,roots),config,progress=progress,cancel=cancel,deadline=deadline).data
    spec=InvestigationSpec.from_dict(population['effective_spec'])
    workspace=historical_workspace(spec,workspace)
    tracked=False
    if workspace is not None:
        from .evidence_use import EvidenceUseLedger
        ledger=EvidenceUseLedger(workspace)
        if ledger.status()['enabled']:
            ledger.record('discovery_selection',events=population['events'],units=population['units'],population_digest=population['population_digest'],request_id=request_id,cancel=cancel,deadline=deadline,session_max_bytes=config.max_rss_bytes//8)
            tracked=True
    if not tracked:record_session('discovery_selection',population['events'],population['units'],max_bytes=config.max_rss_bytes//8,workspace=workspace)
    result=compat.supervise(_discover,(spec,config,roots,expected_fingerprint,population['fingerprint']),config,progress=progress,cancel=cancel,deadline=deadline)
    result.execution['end_to_end_seconds']=time.monotonic()-started
    result.execution['requested_operation_deadline_seconds']=config.max_seconds
    return result.seal()


def freeze_hypotheses(result,candidate_ids=None,*,confirmation=None,practical_thresholds=None):
    from .investigation_contracts import FrozenHypothesisSet,FailureObjectiveSpec
    if not isinstance(result,InvestigationResult):raise EvaluationError('Freeze a protected investigation result.')
    InvestigationResult.from_dict(result.to_private_dict(),private=result.private)
    config=confirmation if isinstance(confirmation,ConfirmationSpec) else ConfirmationSpec.from_dict(confirmation or {})
    candidates={c['id']:c for c in result.data['investigation']['candidates']}
    selected=list(result.data['investigation']['shortlist'] if candidate_ids is None else candidate_ids)
    if not selected or len(selected)>32 or len(set(selected))!=len(selected) or set(selected)-set(candidates):raise EvaluationError('Select 1–32 distinct retained hypotheses.')
    if practical_thresholds is not None and (type(practical_thresholds) is not dict or set(practical_thresholds)-set(selected) or
        any(type(v) not in {int,float} or not math.isfinite(v) or v<0 for v in practical_thresholds.values())):raise EvaluationError('Practical thresholds must explicitly bind selected candidates to finite nonnegative effects in their metric units.','practical_threshold_required')
    spec=InvestigationSpec.from_dict(result.private['investigation_spec']);definitions={v.id+'.'+f.id:f for v in spec.features for f in v.fields}
    if len(selected)>spec.limits.max_hypotheses:raise EvaluationError('Selected family exceeds the explicitly admitted hypothesis limit.','hypothesis_limit')
    if config.restatement_schedule:
        from .history_contracts import instant
        if spec.history is None:raise EvaluationError('Scheduled outcome restatements require retained prediction and feature snapshots.','restatement_history_required')
        if any(instant(s.as_of)<=instant(spec.history['selection']['as_of']) for s in config.restatement_schedule):raise EvaluationError('Scheduled outcome cutoffs must follow the initial frozen outcome cutoff.','restatement_schedule')
    representations={r.id:r for r in spec.representations};hypotheses=[]
    for cid in selected:
        candidate=candidates[cid];objective=copy.deepcopy(candidate['objective'])
        objective['metric_identity']=copy.deepcopy(candidate['S']['member_metric'].get('metric_identity',{}))
        if practical_thresholds and cid in practical_thresholds:objective['practical_threshold']=practical_thresholds[cid]
        objective=FailureObjectiveSpec.from_dict(objective)
        if objective.practical_threshold is None:raise EvaluationError('Every hypothesis requires a metric-specific practical threshold.','practical_threshold_required')
        artifact=result.private['artifacts'][candidate['membership_artifact']];fields=set(artifact['features'])
        from .investigation_objectives import legacy_paired_precision
        if legacy_paired_precision(objective,artifact):raise EvaluationError('Earlier paired precision used an unqualified common-positive population. Preserve its record and run a new investigation before freezing.','paired_precision_population_version')
        rep=representations.get(artifact.get('representation'))
        if rep and rep.field:fields.add(rep.field)
        from .features import FEATURE_TIME_POLICY
        cutoff_views=[v for v in spec.features if v.information_cutoff and any(v.id+'.'+f.id in fields for f in v.fields)]
        if cutoff_views and result.data['investigation'].get('feature_time_policy')!=FEATURE_TIME_POLICY:
            raise EvaluationError('This discovery predates corrected declared-cutoff semantics. Preserve it and start a new investigation.','legacy_information_cutoff_interpretation')
        if fields.intersection(result.private.get('known_outcome_features',())) or any(definitions[fid].outcome_derived for fid in fields if fid in definitions):raise EvaluationError('Outcome-derived membership cannot be independently confirmed.','outcome_derived_membership')
        from .investigation_contracts import observation_policy
        hypothesis={'candidate_id':cid,'membership_artifact':candidate['membership_artifact'],'objective':objective.to_dict(),
                    'membership_scope':config.membership_scope,'minimum_membership_coverage':config.minimum_membership_coverage,
                    'sampling':config.sampling,'outcome_scope':config.outcome_scope,'feature_time_view':spec.feature_time_view,
                    'feature_contracts':[v.to_dict() for v in spec.features if any(v.id+'.'+f.id in fields for f in v.fields)],
                    'representation_contract':{k:v for k,v in rep.to_dict().items() if k not in {'matrix_path','keys_source','model_directory'}} if rep else None,
                    'population_policy':{'event_namespace':spec.roles.namespace,'assignment_unit':spec.roles.unit,
                        'weighting':'event_weighted','eligible_denominator':candidate['S']['member_metric'].get('objective_identity',{}).get('conditional_denominator'),
                        'upstream_outputs':[{k:v for k,v in r.to_dict().items() if k!='source'} for r in spec.evaluation.runs] if spec.evaluation else {'historical_variants':spec.history['selection'].get('variants',[]),'selection_policy':{k:v for k,v in spec.history['selection'].items() if k not in {'windows','catalog_sequence','prediction_catalog_sequence','as_of','prediction_as_of','config','name'}}},
                        'observation_policy':observation_policy(spec)},
                    'definition_version':'frozen_failure_hypothesis_v2'}
        if cutoff_views:hypothesis['feature_time_policy']=FEATURE_TIME_POLICY
        hypotheses.append({**hypothesis,'id':digest(hypothesis)})
    used={h['membership_artifact'] for h in hypotheses};artifacts={k:v for k,v in result.private['artifacts'].items() if k in used}
    from .investigation_membership import dependency_digests
    dependencies=set().union(*(dependency_digests(a) for a in artifacts.values()))
    from .investigation_contracts import confirmation_family_digest
    family=confirmation_family_digest(hypotheses,config)
    packet={'schema_version':'confidenceguard.frozen_hypothesis_set/1.1','origin_analysis_id':result.data['analysis_id'],
            'origin_analysis_digest':result.binding['analysis_digest'],'investigation_spec':spec.to_dict(),
            'input_fingerprint':result.data['investigation']['fingerprint'],'files':result.private['files'],
            'hypotheses':hypotheses,'artifacts':artifacts,'models':{k:v for k,v in result.private.get('models',{}).items() if k in dependencies},
            'confirmation_spec':config.to_dict(),'evaluation_config':result.private['config'],'D_S_units':result.private['D_S_units'],'D_S_events':result.private['D_S_events'],'family_digest':family}
    packet['content_digest']=digest(packet);return FrozenHypothesisSet(packet)
