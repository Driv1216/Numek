"""One robustness orchestrator over generated views and existing native reducers."""
from dataclasses import replace
import copy
import hashlib
import json
from pathlib import Path
import time
from types import SimpleNamespace

import numpy as np

from ..contracts import EvaluationError,ComparisonSpec,digest,strict_json
from ..sources import rows
from ..analytics import compare
from ..execution.adapters import Adapter
from ..execution.services import service,apply_events,make_result,measurement
from .contracts import RobustnessSpec,FrozenRobustnessProtocol,RobustnessAssessmentSpec,RobustnessClaim,PolicyStressSpec
from .transformations import variant,condition,materialized_content
from .attacks import search
from .inference import assess


def _output(prepared,view,event):
    value=prepared.con.execute('SELECT payload FROM cg6_outputs WHERE view=? AND event_key=?',[view,event]).fetchone()
    return json.loads(value[0]) if value else None


def _loss(output,task):
    if not output['truth']['valid'] or output['execution']!='completed':return None
    c=output['channels'];y=output['truth']['value']
    if task.kind=='regression':return abs(c['point']-y) if 'point' in c and output.get('issuance') in {'issued','hypothetical'} else None
    return float(output['decision']!=y) if output.get('decision') is not None and output.get('issuance') in {'issued','hypothetical'} else None


def _metamorphic(left,right,relation):
    channel=relation['channel'];a=left['channels'].get(channel);b=right['channels'].get(channel)
    if a is None or b is None:return None
    a=np.asarray(a);b=np.asarray(b)
    if a.shape!=b.shape:return None
    if a.dtype.kind in 'OUS' or b.dtype.kind in 'OUS':return float(not np.array_equal(a,b)) if relation['relation']=='invariant' else None
    atol=relation.get('atol',0.);rtol=relation.get('rtol',0.)
    if relation['relation']=='monotone':
        direction=1 if relation.get('direction','increasing')=='increasing' else -1
        return float(np.any(direction*(b-a)<-(atol+rtol*np.abs(a))))
    if relation['relation']=='equivariant':
        if 'permutation' in relation:a=a[np.asarray(relation['permutation'],int)]
        else:a=a*relation.get('factor',1)+relation.get('offset',0)
    return float(not np.allclose(a,b,atol=atol,rtol=rtol))


def _contributions(prepared,view,scenario,replicate,attacker=None):
    pending=[]
    query='SELECT v.payload,b.payload FROM cg6_outputs v LEFT JOIN cg6_outputs b ON b.view=? AND b.event_key=v.event_key WHERE v.view=? ORDER BY v.event_key'
    # Match once as a disk relation; per-root SQL preparation would multiply
    # orchestration cost across every model/scenario/replicate.
    for payload,base_payload in rows(prepared.con,query,[view['predictor'].id,view['id']],batch=512):
        out=json.loads(payload);root=out['event_key'];original=json.loads(base_payload) if base_payload else None
        if original is None:raise EvaluationError('Original/variant matching failed.','variant_alignment')
        channels=out['channels'];left=original['channels'];loss=_loss(out,prepared.spec.task);base_loss=_loss(original,prepared.spec.task)
        confidence=max(channels['probabilities'])-max(left['probabilities']) if channels.get('probabilities') and left.get('probabilities') else None
        flip=float(out['decision']!=original['decision']) if out.get('decision') is not None and original.get('decision') is not None and out.get('issuance') in {'issued','hypothetical'} and original.get('issuance') in {'issued','hypothetical'} else None
        metrics={'loss_delta':loss-base_loss if loss is not None and base_loss is not None else None,'confidence_delta':confidence,'flip_rate':flip,
                 'output_failure_rate':float(out['execution']!='completed' or bool(out['channel_failures']) or out.get('issuance')=='failed')}
        if 'point' in channels and 'point' in left:
            metrics['point_delta']=channels['point']-left['point']
            if len(scenario.transformations)==1 and scenario.transformations[0].operation=='finite_difference':
                t=scenario.transformations[0];step=t.parameters.get('step',.01)*t.parameters.get('direction',1)
                metrics['directional_finite_difference']=metrics['point_delta']/step if step else None
        if channels.get('probabilities') and left.get('probabilities'):metrics['probability_max_change']=float(np.max(np.abs(np.asarray(channels['probabilities'])-left['probabilities'])))
        if out.get('uncertainty') or original.get('uncertainty'):
            from ..conformal import read_value
            def uncertainty(row):
                values={}
                for item in row.get('uncertainty',[]):
                    o=item['output'];level=item['coverage'];available=o['state']!='unavailable'
                    covered=None;width=None
                    if available:
                        if prepared.spec.task.classes:
                            width=o.get('size')
                            if row['truth']['valid']:covered=float(prepared.spec.task.classes.index(row['truth']['value']) in o.get('members',[]))
                        else:
                            width=read_value(o['width']) if o.get('width') else None
                            if row['truth']['valid']:covered=float(False if o['state']=='empty' else True if o['state']=='unbounded' else read_value(o['lower'])<=row['truth']['value']<=read_value(o['upper']))
                    values[level]={'coverage_delta':covered,'efficiency_delta':width,'uncertainty_availability_delta':float(available)}
                return values
            before=uncertainty(original);after=uncertainty(out)
            for level in before.keys()|after.keys():
                for metric in ('coverage_delta','efficiency_delta','uncertainty_availability_delta'):
                    a=before.get(level,{}).get(metric);b=after.get(level,{}).get(metric)
                    metrics[metric+'@'+level]=float(b-a) if a is not None and b is not None and np.isfinite(a) and np.isfinite(b) else None
        if scenario.outcome_relation=='reference_label_diagnostic':
            diagnostic=_loss({**out,'truth':original['truth']},prepared.spec.task)
            metrics['original_label_reference_loss_delta']=diagnostic-base_loss if diagnostic is not None and base_loss is not None else None
        if prepared.spec.task.kind!='regression' and loss is not None and base_loss is not None and channels.get('probabilities') and left.get('probabilities'):
            metrics['confidently_wrong_transition']=float(loss==1 and max(channels['probabilities'])>=.9)-float(base_loss==1 and max(left['probabilities'])>=.9)
            y=prepared.spec.task.classes.index(out['truth']['value']);by=prepared.spec.task.classes.index(original['truth']['value'])
            p=np.asarray(channels['probabilities']);q=np.asarray(left['probabilities'])
            if prepared.spec.task.kind=='binary_classification':
                pos=prepared.spec.task.classes.index(prepared.spec.task.positive_class)
                metrics['brier_delta']=float((p[pos]-float(y==pos))**2-(q[pos]-float(by==pos))**2)
            else:metrics['brier_delta']=float(np.sum((p-np.eye(len(p))[y])**2)-np.sum((q-np.eye(len(q))[by])**2))
            if p[y]>0 and q[by]>0:metrics['log_loss_delta']=float(np.log(q[by])-np.log(p[y]))
        if scenario.metamorphic:metrics['metamorphic_violation']=_metamorphic(original,out,scenario.metamorphic)
        attack=out.get('variant',{}).get('attack')
        if attack:
            valid_outcome=scenario.outcome_relation in {'label_preserving','authoritative_variant','registered_transform'} or scenario.attack.objective in {'output_change','targeted'}
            if view['predictor'].id==attacker:
                # Frozen baseline-ineligible roots remain in operational search
                # accounting, but are outside this conditional success estimand.
                if attack.get('eligible'):metrics['attack_success']=float(attack['success']) if valid_outcome else None
            else:
                from .attacks import objective,decision
                eligible=bool(original['truth']['valid']) if scenario.attack.objective in {'misclassification','loss_increase'} else True
                if scenario.attack.objective=='misclassification':eligible &= decision(original,prepared.spec.task)==original['truth']['value']
                if scenario.attack.objective=='targeted':eligible &= decision(original,prepared.spec.task)!=scenario.attack.target_class
                if eligible:
                    _,success=objective(out,original,{'truth':out['truth'],'baseline_truth':original['truth']},scenario.attack,prepared.spec.task)
                    metrics['transfer_attack_success']=float(success) if valid_outcome else None
        for metric,value in metrics.items():
            pending.append((view['predictor'].id,scenario.id,root,out['entity_key'] or root,replicate,metric,value,attacker or ''))
        if len(pending)>=512:
            prepared.con.executemany('INSERT INTO cg6_contributions VALUES (?,?,?,?,?,?,?,?)',pending);pending=[]
    if pending:prepared.con.executemany('INSERT INTO cg6_contributions VALUES (?,?,?,?,?,?,?,?)',pending)


def run_worker(prepared,operation,staging,registrations,options,started):
    protocol=FrozenRobustnessProtocol.from_dict(options['protocol']) if options.get('protocol') else None
    study=RobustnessSpec.from_dict(options['robustness'])
    role='E' if operation=='robustness_assess' else study.role
    prepared.con.execute('CREATE TABLE cg6_contributions(predictor VARCHAR,scenario VARCHAR,event_key VARCHAR,entity_key VARCHAR,replicate INTEGER,metric VARCHAR,value DOUBLE,attacker VARCHAR)')
    prepared.con.execute('CREATE TABLE cg6_variants(scope VARCHAR,event_key VARCHAR,payload VARCHAR,applicable BOOLEAN)')
    adapters={};originals={};devices={};scenario_records=[]
    for p in prepared.spec.predictors:
        a=Adapter(p,prepared.spec.device,prepared.config,prepared.spec.limits,prepared.work,prepared.roots,registrations);prepared.attach(a);adapters[p.id]=a
        originals[p.id]=apply_events(prepared,a,prepared.events(role),'original')
    if prepared.spec.auxiliaries:
        from ..auxiliary.composite import attach_auxiliaries
        attach_auxiliaries(prepared,adapters,registrations)
        for pid,a in adapters.items():
            if pid not in originals:originals[pid]=apply_events(prepared,a,prepared.events(role),'original')
    if prepared.spec.ensembles:
        from ..execution.ensembles import attach_ensembles
        attach_ensembles(prepared,adapters)
        for group in prepared.spec.ensembles:originals[group['id']]=apply_events(prepared,adapters[group['id']],prepared.events(role),'original')
    total_variants=0
    for scenario in study.scenarios:
        actors=([pid for pid,a in adapters.items() if a.spec.adapter=='torch' and hasattr(a,'model')] if scenario.attack and scenario.attack.algorithm in {'fgsm','pgd'} else list(adapters)) if scenario.attack else [None]
        if not actors:raise EvaluationError('No admitted model has the requested gradient path.','gradient_unavailable')
        for attacker in actors:
            for replicate in range(scenario.replicates):
                scope=scenario.id+'/replicate_'+str(replicate)+(('/attacker_'+attacker) if attacker else '')
                permutation={}
                fields=sorted({f for t in scenario.transformations if t.operation=='permutation' for f in t.fields})
                if fields:
                    inputs=[e for e in prepared.events(role) if condition(e['record'],scenario.filter,e.get('unavailable_fields',())) is True]
                    if len(inputs)*max(256,len(fields)*128)>prepared.config.max_rss_bytes//3:raise EvaluationError('Permutation memory admission exceeded.','permutation_memory')
                    for transformation in scenario.transformations:
                        if transformation.operation!='permutation':continue
                        rng=np.random.Generator(np.random.PCG64(int(digest([study.seed,scenario.id,replicate,transformation.id])[:16],16)));indices=rng.permutation(len(inputs))
                        for e,j in zip(inputs,indices):permutation.setdefault(e['event_key'],{})[transformation.id]={f:inputs[j]['record'].get(f) for f in transformation.fields}
                planned=applicable=0;validity={};attacks=[];pending=[]
                for e in prepared.events(role):
                    selected=condition(e['record'],scenario.filter,e.get('unavailable_fields',())) is True
                    if not selected and operation!='policy_stress':continue
                    transformed=variant(e,scenario,replicate,study.seed,prepared,permutation.get(e['event_key'])) if selected else copy.deepcopy(e)
                    if not selected:transformed['variant']={'id':digest([e['event_key'],scenario.id,replicate,'unchanged']),'root_event':e['event_key'],'scenario':scenario.id,'replicate':replicate,'outcome_relation':'unchanged','validity':[],'applicable':True,'input_record':e['record']}
                    if scenario.attack and selected and transformed['variant']['applicable']:
                        baseline=_output(prepared,attacker,e['event_key'])
                        transformed['baseline_truth']=e['truth']
                        if scenario.outcome_relation=='authoritative_variant':
                            # A label for the pre-search input cannot label every
                            # candidate. Exact final labels are rebound below.
                            transformed['truth']={'value':None,'valid':False,'reason':'candidate_specific_authoritative_outcome_required'}
                        attacked,record=search(transformed if transformed['variant']['applicable'] else e,baseline,scenario.attack,adapters[attacker],prepared,int(digest([study.seed,e['event_key'],scenario.id,replicate,attacker])[:16],16))
                        transformed['record']=attacked['record'];transformed['variant']['input_record']=attacked['record'];transformed['variant']['attack']=record
                        transformed['variant']['id']=digest([e['event_key'],scenario.id,replicate,attacker,materialized_content(attacked['record'],prepared)])
                        if scenario.outcome_relation=='authoritative_variant':
                            from .transformations import transformed_truth
                            transformed['truth']=transformed_truth(e['truth'],scenario.outcome_relation,scenario.outcome_rule,scenario.variant_outcomes,transformed['variant']['id'],prepared.spec.task)
                        attacks.append(record)
                    total_variants+=1;planned+=1;applicable+=transformed['variant']['applicable']
                    if total_variants>prepared.spec.limits.max_variants:raise EvaluationError('Variant admission exceeded.','variant_limit')
                    for v in transformed['variant']['validity']:
                        k='valid_feasible' if v['structural_valid'] and v['domain_feasible'] else 'invalid_or_infeasible';validity[k]=validity.get(k,0)+1
                    payload=json.dumps(transformed,allow_nan=False,separators=(',',':'))
                    pending.append((scope,e['event_key'],payload,transformed['variant']['applicable']))
                    if len(pending)>=512:prepared.con.executemany('INSERT INTO cg6_variants VALUES (?,?,?,?)',pending);pending=[];prepared.work.check('variant materialization')
                if pending:prepared.con.executemany('INSERT INTO cg6_variants VALUES (?,?,?,?)',pending)
                if not planned:
                    scenario_records.append({'id':scenario.id,'replicate':replicate,'planned':0,'applicable':0,'state':'empty_scope'});continue
                def event_rows():
                    for payload, in rows(prepared.con,'SELECT payload FROM cg6_variants WHERE scope=? ORDER BY event_key',[scope],batch=512):yield json.loads(payload)
                for pid,a in adapters.items():
                    start=len(prepared.views);apply_events(prepared,a,event_rows(),scope)
                    for view in prepared.views[start:]:_contributions(prepared,view,scenario,replicate,attacker)
                scenario_records.append({'id':scenario.id,'replicate':replicate,'attacker':attacker,'planned':planned,'applicable':applicable,'validity':validity,
                    'own_attack_unsupported_models':[pid for pid in adapters if pid not in actors] if scenario.attack else [],
                    'outcome_relation':scenario.outcome_relation,'attack_queries':sum(a.get('queries',0) for a in attacks),'attack_eligible':sum(a.get('eligible',False) for a in attacks),
                    'attack_successes':sum(a.get('success') is True for a in attacks),'search_guarantee':False})
    from .sensitivity import diagnose
    gradients=diagnose(prepared,adapters,study) if study.sensitivity else []
    evidence=prepared.metrics();comparisons=[]
    original_spec=prepared.store.spec
    for edge in study.comparisons:
        scopes=sorted({v['scope'] for v in prepared.views})
        for scope in scopes:
            a=next((v for v in prepared.views if v['predictor'].id==edge['left'] and v['scope']==scope),None)
            b=next((v for v in prepared.views if v['predictor'].id==edge['right'] and v['scope']==scope),None)
            if a and b:
                prepared.store.spec=SimpleNamespace(**{**vars(original_spec),'runs':(a['run'],b['run']),'comparison':ComparisonSpec(a['id'],b['id'])})
                before=len(evidence.measurements);comparison=compare(evidence)
                for m in evidence.measurements[before:]:m['data']['experiment_scope']=scope
                comparisons.append({'scope':scope,**comparison})
    prepared.store.spec=original_spec
    execution_root=Path(__file__).parents[1]
    implementation_files=[*Path(__file__).parent.glob('*.py'),*(execution_root/'execution'/name for name in ('services.py','store.py','frozen.py','provenance.py','ensembles.py','batch_admission.py')),*(execution_root/'auxiliary'/name for name in ('services.py','composite.py','contracts.py'))]
    implementation={str(p.relative_to(execution_root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(implementation_files)}
    for pid,a in adapters.items():
        devices[pid]=a.finish()
        devices[pid].setdefault('runtime',{})['experiment_implementation_sha256']=implementation
    result=make_result(prepared,'assessment' if protocol else 'policy_stress' if operation=='policy_stress' else 'robustness',
        {'devices':devices,'scenarios':scenario_records,'comparisons':comparisons,'sensitivity':gradients,'design_digest':digest(study.to_dict()),
         'reservation':options.get('reservation'),'exposure_checks':options.get('exposure_checks')},
        started=started,evidence=evidence,staging=staging,private_extra={'robustness_spec':study.to_dict(),**({'frozen_protocol':protocol.to_dict()} if protocol else {})})
    if study.regions:
        from .regions import transitions
        result.data['cg6']['region_transitions']=transitions(prepared,study)
    roots={};summaries={};planned_units=[];potential={};batch_units={};mixture_groups={};mixture_totals={};weighted={}
    for e in prepared.events(role):
        planned_units.append(e['entity_key'] or e['event_key'])
        potential[e['event_key']]=e['entity_key'] or e['event_key']
        for s in study.scenarios:
            if s.mixture_weights and condition(e['record'],s.filter,e.get('unavailable_fields',())) is True:
                group=str(e['record'].get(s.mixture_field));mixture_groups[(s.id,e['event_key'])]=group
                key=(s.id,group);mixture_totals[key]=mixture_totals.get(key,0)+1
        if protocol and protocol.sampling=='independent_batches':
            b=e['record'].get(protocol.batch_field)
            if b is None:raise EvaluationError('Independent-batch membership is missing.','batch_membership')
            batch_units[e['event_key']]=str(b)
    query='SELECT predictor,scenario,event_key,entity_key,metric,attacker,count(*) planned,count(value) available,avg(value) FROM cg6_contributions GROUP BY ALL ORDER BY predictor,scenario,metric,event_key'
    required={(c.predictor,c.scenario,c.metric,c.predictor if c.metric=='attack_success' else '') for c in protocol.claims} if protocol else set()
    contribution_path=Path(staging)/'root-contributions.jsonl';ch=hashlib.sha256();contribution_bytes=0
    with contribution_path.open('xb') as stream:
        for pid,sid,event,entity,metric,attacker,planned,available,value in rows(prepared.con,query,batch=512):
            k=(pid,sid,metric,attacker);summary=summaries.setdefault(k,{'planned':0,'incomplete':0,'support':0,'sum':0.,'positive':0,'negative':0})
            summary['planned']+=1
            if planned==available:
                summary['support']+=1;summary['sum']+=value;summary['positive']+=value>0;summary['negative']+=value<0
            else:summary['incomplete']+=1
            scenario=next(s for s in study.scenarios if s.id==sid)
            if scenario.mixture_weights:
                group=mixture_groups.get((sid,event));mass=scenario.mixture_weights.get(group,0.)
                w=mass/max(1,mixture_totals.get((sid,group),0))
                item=weighted.setdefault(k,{'numerator':0.,'denominator':0.,'support':0,'planned':0})
                item['planned']+=1
                if planned==available:item['numerator']+=w*value;item['denominator']+=w;item['support']+=1
            raw=(json.dumps({'predictor':pid,'scenario':sid,'event_key':event,'entity_key':entity,'metric':metric,'attacker':attacker,'value':value if planned==available else None},allow_nan=False)+'\n').encode()
            stream.write(raw);ch.update(raw);contribution_bytes+=len(raw)
            if contribution_bytes>prepared.config.workspace_bytes:raise EvaluationError('Contribution artifact exceeds storage admission.','execution_output_limit')
            if k in required:
                r=roots.setdefault(k,{'values':[],'entities':[],'events':[],'planned':0,'incomplete':0});r['planned']+=1
                if planned==available:r['values'].append(value);r['entities'].append(entity);r['events'].append(event)
                else:r['incomplete']+=1
                if sum(len(v['values']) for v in roots.values())*192>prepared.config.max_rss_bytes//3:raise EvaluationError('Assessment contribution memory exceeds admission.','inference_memory')
    contribution_path.chmod(0o600)
    result.private['contribution_artifact']={'path':str(contribution_path),'sha256':ch.hexdigest(),'bytes':contribution_bytes}
    for (pid,sid,metric,attacker),r in summaries.items():
        measurement(result,pid,metric,r['sum']/r['support'] if r['support'] else None,r['support'],scope=sid,family='robustness',
                    data={'planned_roots':r['planned'],'incomplete_roots':r['incomplete'],'sampling_unit':'original_event','replicates_averaged_within_root':True,
                          'attacker':attacker or None,'successful_complete_root_conditioning':bool(r['incomplete'])},reason=None if r['support'] else 'no_eligible_root_contributions')
        result.data['measurements'][-1]['sensitive_counts']=[r['positive'],r['negative'],r['support']-r['positive']-r['negative'],r['incomplete']]
    result.private['root_contributions']=[{'predictor':p,'scenario':s,'metric':m,'attacker':a,**r} for (p,s,m,a),r in summaries.items()]
    for (pid,sid,metric,attacker),r in weighted.items():
        scenario=next(s for s in study.scenarios if s.id==sid)
        absent=[g for g,mass in scenario.mixture_weights.items() if mass>0 and not mixture_totals.get((sid,g))]
        reason='positive_mass_cohort_without_planned_support' if absent else 'no_eligible_weighted_contributions' if r['denominator']==0 else None
        measurement(result,pid,'mixture_'+metric,r['numerator']/r['denominator'] if reason is None else None,r['support'],scope=sid,family='robustness_mixture',
            data={'frozen_masses':scenario.mixture_weights,'weighted_numerator':r['numerator'],'weighted_denominator':r['denominator'],'root_weights':'mass / planned original events in cohort',
                  'planned_roots':r['planned'],'complete_output_conditioning':r['support']<r['planned'],'attacker':attacker or None,'interval':'unavailable; descriptive fixed mixture'},reason=reason)
    events=[e['event_key'] for e in prepared.events(role)]
    result.private['experiment_membership']={'namespace':prepared.spec.namespace,'events':[digest([prepared.spec.namespace,e]) for e in events],
                                          'units':[digest([prepared.spec.namespace,u]) for u in planned_units]}
    if protocol:
        result.data['cg6']['protocol_digest']=protocol.content_digest
        overlap=bool(set(result.private['experiment_membership']['events'])&set(protocol.development_events) or set(result.private['experiment_membership']['units'])&set(protocol.development_units))
        upstream=protocol.upstream_independence=='declared_independent' and protocol.external_exposure=='declared_unexposed'
        checks=options.get('exposure_checks',{})
        reason='development_overlap' if overlap else 'upstream_or_external_independence_unknown' if not upstream else 'known_prior_exposure' if checks.get('overlap') else None
        observed_profiles={pid:value.get('runtime') for pid,value in devices.items()}
        if protocol.runtime_profiles!=observed_profiles:reason=reason or 'frozen_runtime_profile_changed_or_unestablished'
        claims=[]
        from ..execution.provenance import assessment_reasons
        known_reasons=assessment_reasons(prepared)
        for c in protocol.claims:
            r=roots.get((c.predictor,c.scenario,c.metric,c.predictor if c.metric=='attack_success' else ''))
            claim_reason=reason or known_reasons.get(c.predictor)
            if r is None or claim_reason:
                claims.append({'id':c.id,'state':'refused','reason':claim_reason or 'claim_contributions_unavailable','allocated_alpha':(1-protocol.confidence)/len(protocol.claims)})
            elif r['incomplete']:
                claims.append({'id':c.id,'state':'refused','reason':'incomplete_planned_outputs_or_outcomes','allocated_alpha':(1-protocol.confidence)/len(protocol.claims)})
            else:
                entities=[batch_units[e] for e in r['events']] if protocol.sampling=='independent_batches' else r['entities']
                potential_units=list(batch_units.values()) if protocol.sampling=='independent_batches' else planned_units
                entity_batches={}
                if protocol.sampling=='independent_batches':
                    for e,u in potential.items():entity_batches.setdefault(u,set()).add(batch_units[e])
                crossed=any(len(v)>1 for v in entity_batches.values())
                claims.append({'id':c.id,'state':'refused','reason':'entity_crosses_batches','allocated_alpha':(1-protocol.confidence)/len(protocol.claims)} if crossed else assess(r['values'],entities,c,protocol,len(protocol.claims),potential_entities=potential_units))
        result.data['cg6']['claims']=claims
    if operation=='policy_stress':
        from .policy import run_policy_stress
        run_policy_stress(prepared,result,PolicyStressSpec.from_dict(options['policy_stress']))
    for (pid,sid,metric,attacker),r in summaries.items():
        if metric=='output_failure_rate' and r['sum']>0:
            result.data['findings'].append({'priority':'Review','code':'scenario_output_failures','message':f'{pid} has unavailable outputs in scenario {sid}; planned and successful-output populations remain distinct.','count':r['positive']})
    if any(s.outcome_relation in {'unknown','reference_label_diagnostic'} for s in study.scenarios):result.data['findings'].append({'priority':'Interpretation','code':'unknown_variant_outcomes','message':'Some scenarios have unknown transformed outcomes. Interpret behavior and confidence diagnostics without calling them transformed predictive performance.'})
    prepared.verify();return result


def inspect_robustness(spec,config=None,**kwargs):
    study=RobustnessSpec.from_dict(spec) if isinstance(spec,dict) else spec
    return service(study.execution,config,operation='inspect',options={'robustness':study.to_dict()},**kwargs)


def run_robustness(spec,config=None,**kwargs):
    study=RobustnessSpec.from_dict(spec) if isinstance(spec,dict) else spec
    return service(study.execution,config,operation='robustness',options={'robustness':study.to_dict()},**kwargs)


def freeze_robustness(result,claims,*,confidence=.95,sampling='independent_roots',max_cluster_size=None,upstream_independence='unknown',external_exposure='unknown',batch_field=None):
    if not isinstance(result, __import__('confidenceguard.execution.result',fromlist=['ExecutionResult']).ExecutionResult):raise EvaluationError('Protected completed experiment required.')
    member=result.private['experiment_membership']
    return FrozenRobustnessProtocol.create(study=RobustnessSpec.from_dict(result.private['robustness_spec']),claims=claims,
        development_events=member['events'],development_units=member['units'],confidence=confidence,sampling=sampling,max_cluster_size=max_cluster_size,
        upstream_independence=upstream_independence,external_exposure=external_exposure,batch_field=batch_field,
        runtime_profiles={pid:profile.get('runtime') for pid,profile in result.data['cg6'].get('devices',{}).items()})


def assess_robustness(spec,config=None,**kwargs):
    assessment=RobustnessAssessmentSpec.from_dict(spec) if isinstance(spec,dict) else spec
    study=replace(assessment.protocol.study,execution=assessment.execution,role='E')
    return service(assessment.execution,config,operation='robustness_assess',options={'robustness':study.to_dict(),'protocol':assessment.protocol.to_dict()},**kwargs)


def stress_policy(spec,config=None,**kwargs):
    stress=PolicyStressSpec.from_dict(spec) if isinstance(spec,dict) else spec
    return service(stress.robustness.execution,config,operation='policy_stress',options={'robustness':stress.robustness.to_dict(),'policy_stress':stress.to_dict()},**kwargs)
