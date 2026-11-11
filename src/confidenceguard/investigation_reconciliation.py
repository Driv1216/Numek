"""Transparent effect/support/complexity frontiers and overlapping evidence."""
from collections import defaultdict
from dataclasses import replace
from types import SimpleNamespace
import numpy as np
from .contracts import digest
from .investigation_membership import apply

SELECTION_POLICY='severity_material_excess_support_frontier_v2'


def selection_fingerprint(prepared_input):
    return digest({'prepared_input':prepared_input,'selection_policy':SELECTION_POLICY})


def adverse_value(candidate):
    measured=candidate['S']
    if measured.get('effect_state')=='positive_infinity':return float('inf')
    if measured.get('effect_state')=='negative_infinity':return -float('inf')
    return measured['effect']


def marginal_selection_evidence(p,candidate,previous,*,candidates,memberships,indices,objective):
    """Shared S-only uncovered-population calculation; no gate is changed."""
    def membership(cid):
        packet=memberships[candidates[cid]['membership_artifact']]['S']
        return {k:np.unpackbits(np.frombuffer(bytes.fromhex(packet[k+'_bits']),dtype=np.uint8),bitorder='little')[:len(indices)].astype(bool) for k in ('member','available')}
    original=membership(candidate['id']);covered=np.zeros(len(indices),bool);known=np.ones(len(indices),bool)
    for prior in previous:
        mask=membership(prior);covered|=mask['member'];known&=mask['available']
    available=original['available']&known&~covered;member=original['member']&available
    reason=np.where(covered,'already_covered_by_selected_candidates',np.where(~known,'previous_membership_unavailable','candidate_membership_unavailable'))
    mask={'member':member,'available':available,'reason':np.where(available,'',reason)}
    binding={'artifact_digest':digest({'selection_only_uncovered_gate':candidate['membership_artifact'],'previous':previous})}
    measured=p.evaluate(objective,'S',indices,mask,binding)
    declared=candidate['objective'].get('practical_threshold');threshold=declared if declared is not None else 0.
    value=adverse_value({'S':measured})
    return {'admitted':value is not None and value>threshold and measured['conditional_members']>=p.spec.limits.minimum_discovery_support,
        'population':'S excluding already covered members, requiring all preceding memberships applicable',
        'previous_candidates':list(previous),'practical_threshold':declared,'admission_threshold':threshold,
        'threshold_basis':'declared_material_effect' if declared is not None else 'positive_effect_only_no_material_threshold_declared',
        'minimum_conditional_support':p.spec.limits.minimum_discovery_support,
        'evidence':measured,'interpretation':'Exploratory selection only; the original candidate gate and its original population remain unchanged.'}


def reconcile(candidates,shortlist,n,novelty=None):
    groups=defaultdict(list);masks={};overlap=[]
    for c in candidates:
        masks[c['id']]=int.from_bytes(bytes.fromhex(c['_S_mask']),'little')
        groups[c['objective']['id']].append(c)
    ordered=[]
    for objective,items in sorted(groups.items()):
        # Compute the same transitive Pareto order once. Repeated all-pairs
        # scans at every front made large candidate families needlessly cubic.
        valid=np.array([adverse_value(c) is not None for c in items]);active=valid.copy()
        effect=np.array([adverse_value(c) if valid[i] else -float('inf') for i,c in enumerate(items)])
        support=np.array([c['S']['conditional_members'] for c in items]);complexity=np.array([c['complexity'] for c in items])
        dominates=(effect[:,None]>=effect[None,:])&(support[:,None]>=support[None,:])&(complexity[:,None]<=complexity[None,:])
        dominates&=(effect[:,None]>effect[None,:])|(support[:,None]>support[None,:])|(complexity[:,None]<complexity[None,:])
        dominates&=valid[:,None]&valid[None,:];indegree=dominates.sum(axis=0);level=0;fronts=[]
        while np.any(active):
            indices=np.flatnonzero(active&(indegree==0))
            if not len(indices):raise RuntimeError('Strict Pareto dominance unexpectedly contains a cycle.')
            frontier=[items[i] for i in indices]
            for c in frontier:c['frontier']=level
            fronts.extend(sorted(frontier,key=lambda c:(-adverse_value(c),-c['S']['conditional_members'],c['complexity'],c['id'])))
            indegree-=dominates[indices].sum(axis=0);active[indices]=False;level+=1
        for i,c in enumerate(items):
            if not valid[i]:c['frontier']=None;fronts.append(c)
        groups[objective]=fronts
    # Round-robin objectives, preserving units rather than comparing unlike effects.
    selected=[];queues={k:list(v) for k,v in groups.items()};impact_queues={};impact_attempted=set()
    for key,items in groups.items():
        # Preserve the severity extreme, then reserve a different frontier
        # direction. The declared material threshold penalizes broad dilution;
        # a missing threshold does not silently become a material zero.
        scored=[c for c in items if c['objective'].get('practical_threshold') is not None
                and adverse_value(c) is not None and adverse_value(c)>c['objective']['practical_threshold']
                and c['S']['conditional_members']>0]
        impact_queues[key]=sorted(scored,key=lambda c:(
            -(adverse_value(c)-c['objective']['practical_threshold'])*c['S']['conditional_members'],
            -adverse_value(c),-c['S']['conditional_members'],c['complexity'],c['id']))
    while len(selected)<shortlist and any(queues.values()):
        for key in sorted(queues):
            if len(selected)>=shortlist:break
            previous=[cid for cid in selected if next(c for c in candidates if c['id']==cid)['objective']['id']==key]
            choices=[]
            if len(previous)==1 and key not in impact_attempted:
                impact_attempted.add(key);choices.append(('material_excess_support_anchor',impact_queues[key]))
            choices.append(('severity_anchor' if not previous else 'pareto_severity_diversity',queues[key]))
            chosen=False
            for reason,queue in choices:
                while queue:
                    candidate=queue.pop(0);effect=adverse_value(candidate)
                    if candidate['id'] in selected or effect is None or effect<=0:continue
                    bit=masks[candidate['id']]
                    near=False
                    for prior in previous:
                        union=(bit|masks[prior]).bit_count();iou=(bit&masks[prior]).bit_count()/union if union else 1.
                        if iou>.95:near=True;break
                    if not near:
                        if novelty is not None and previous:
                            contribution=novelty(candidate,previous);candidate['selection_contribution']=contribution
                            if not contribution['admitted']:continue
                        candidate['selection_reason']=reason
                        selected.append(candidate['id']);chosen=True;break
                if chosen:break
    for key in sorted(groups):ordered.extend(groups[key])
    selected_ids=set(selected);priority=[];other=[];total_pairs=selected_pairs=0;pair_limit=1000
    for i,left in enumerate(ordered):
        for right in ordered[i+1:]:
            a=masks[left['id']];b=masks[right['id']];intersection=(a&b).bit_count()
            if not intersection:continue
            union=(a|b).bit_count()
            total_pairs+=1;important=left['id'] in selected_ids and right['id'] in selected_ids
            selected_pairs+=int(important);bucket=priority if important else other
            if len(bucket)<pair_limit:bucket.append({'left':left['id'],'right':right['id'],'intersection':intersection,'union':union,'jaccard':intersection/union,'left_contained':intersection==a.bit_count(),'right_contained':intersection==b.bit_count()})
    overlap=priority+other[:pair_limit-len(priority)]
    union=0
    for cid in selected:union|=masks[cid]
    for c in ordered:c['shortlisted']=c['id'] in selected
    return ordered,{'selection_policy':SELECTION_POLICY,
        'pairs':overlap,'retained_pairs':len(overlap),'pair_limit':pair_limit,
        'total_overlapping_pairs':total_pairs,'omitted_pairs':total_pairs-len(overlap),'pair_coverage_complete':total_pairs==len(overlap),
        'shortlist_pairs_complete':len(priority)==selected_pairs,'shortlist_pairs_prioritized':True,
        'shortlist_union_support':union.bit_count(),'selection_population':n,'counts_are_not_summed':True},selected


def fidelity_counts(gate,prediction,*,basis):
    """Feature-only fidelity with both sources of unavailable membership visible.

    Precision/recall describe the joint applicable population. Gate members with
    no applicable explanation are counted separately, never made nonmembers.
    ``available`` remains the legacy alias for ``jointly_available``.
    """
    known=np.asarray(gate['available'],bool);surrogate_known=np.asarray(prediction['available'],bool)
    joint=known&surrogate_known;truth=np.asarray(gate['member'],bool)&joint;pred=np.asarray(prediction['member'],bool)&joint
    tp=int(np.count_nonzero(truth&pred));fp=int(np.count_nonzero(pred&~truth));fn=int(np.count_nonzero(truth&~pred))
    return {'basis':basis,'planned':len(known),'gate_available':int(known.sum()),'surrogate_available':int(surrogate_known.sum()),
        'jointly_available':int(joint.sum()),'available':int(joint.sum()),'unavailable':len(known)-int(joint.sum()),
        'gate_members_without_surrogate':int(np.count_nonzero(np.asarray(gate['member'],bool)&known&~surrogate_known)),
        'true_positive':tp,'false_positive':fp,'false_negative':fn,'true_negative':int(np.count_nonzero(joint&~truth&~pred)),
        'precision':tp/(tp+fp) if tp+fp else None,'recall':tp/(tp+fn) if tp+fn else None,
        'disagreement_rate':(fp+fn)/int(joint.sum()) if joint.any() else None,
        'scope':'Fidelity is conditional on joint applicability. Unavailable membership remains visible against planned support; these counts do not establish future fidelity.'}


def explanation(candidate,artifact,df,sf,dr,sr,dm,sm,limits,check,predicate_cache=None):
    if artifact['kind']=='structured':
        return {'kind':'exact_predicate','evaluation_population':'S',
            'fidelity':fidelity_counts(sm,sm,basis='exact_definition_identity'),
            'defines_membership':True,'causal_interpretation':False,
            'scope':'The predicate is the gate itself; these identity counts are not an empirical surrogate accuracy estimate.'}
    if not df:return {'kind':'approximate','reason':'no_tabular_surrogate_features','fidelity':None}
    from .discovery_rules import propose
    surrogate=SimpleNamespace(spec=SimpleNamespace(direction='higher',metric='membership'),identity={'definition':'D_fitted_membership_surrogate_v1'})
    admitted=replace(limits,max_depth=min(3,limits.max_depth),max_nodes=min(10000,limits.max_nodes),candidates_per_strategy=16)
    proposals,_=propose(df,dm['available'],dm['member'].astype(float),surrogate,admitted,check,predicate_cache=predicate_cache)
    best=None
    for proposal in proposals:
        mask=apply(proposal['artifact'],df,{},cache=predicate_cache)['member'];target=dm['member'];tp=int(np.count_nonzero(mask&target));den=int(mask.sum()+target.sum())
        f1=2*tp/den if den else 0
        if best is None or f1>best[0]:best=(f1,proposal['artifact'])
    if best is None:return {'kind':'approximate','reason':'no_supported_surrogate_rule','fidelity':None}
    surrogate_artifact=best[1];prediction=apply(surrogate_artifact,sf,{},cache=predicate_cache)
    return {'kind':'approximate','definition':surrogate_artifact['parameters'],'fit_population':'D','evaluation_population':'S',
            'fidelity':fidelity_counts(sm,prediction,basis='frozen_D_fitted_surrogate'),
            'causal_interpretation':False,'defines_membership':False}


def stability(prepared,candidates,selected,artifacts,models,check):
    """Bounded D-only refits; membership matching on S never reads S outcomes."""
    from .investigation_objectives import bind
    p=prepared;di,df,dr=p.role_data('D');si,sf,sr=p.role_data('S');limits=p.spec.limits
    chosen=[]
    for candidate in candidates:
        if candidate['id'] not in selected:continue
        if candidate.get('proposal_source')=='declared_ceiling_population_baseline_v1':
            candidate['stability']={'method':'fixed_population_definition_v1','refit_required':False,
                'scope':'The empty conjunction applies to every admitted observation without fitting. This definition identity is not empirical discovery stability or future effect stability.'}
        else:chosen.append(candidate)
    if not chosen:return
    # This is a product diagnostic profile, not a substitute for locked full
    # method-qualification stability campaigns.
    profile=replace(limits,max_nodes=min(limits.max_nodes,100000),candidates_per_strategy=min(limits.candidates_per_strategy,32))
    seed=0;row_limit=min(limits.diagnostic_rows,limits.geometric_rows)
    for objective_id in sorted({c['objective']['id'] for c in chosen}):
        targets=[c for c in chosen if c['objective']['id']==objective_id];objective=bind(next(o for o in p.spec.objectives if o.id==objective_id),p.store)
        dkeys,diagnostics=objective.discovery_targets();position={k:i for i,k in enumerate(dkeys)};take=np.array([position[p.keys[i]] for i in di])
        diagnostics=[{**t,'eligible':t['eligible'][take],'loss':t['loss'][take]} for t in diagnostics]
        reference_cache={'_models':models,'_directory':str(p.work.root),'_max_distance_ops':limits.max_distance_operations,'_population_size':len(si),'_membership_memory_bytes':p.config.max_rss_bytes//3,'_threads':p.config.threads}
        reference={c['id']:apply(artifacts[c['membership_artifact']],sf,sr,cache=reference_cache,check=check) for c in targets}
        units=[p.records[i].get('entity_key') if p.spec.roles.unit=='entity' else p.keys[i] for i in di]
        groups={}
        for i,unit in enumerate(units):groups.setdefault(unit,[]).append(i)
        names=sorted(groups);rng=np.random.Generator(np.random.PCG64(seed));outcomes={c['id']:[] for c in targets}
        for repeat in range(limits.stability_replicates):
            sample=np.array([i for unit in rng.choice(names,len(names),replace=True) for i in groups[unit]],dtype=int)
            if len(sample)>row_limit:sample=sample[np.linspace(0,len(sample)-1,row_limit,dtype=int)]
            features={k:[v[i] for i in sample] for k,v in df.items()}
            from .representations import subset
            representations={k:subset(v,sample) for k,v in dr.items()}
            for kind in sorted({c['strategy'] for c in targets}):
                temporary_models={}
                from .investigation import propose_diagnostic_targets
                sampled=[{**t,'eligible':t['eligible'][sample],'loss':t['loss'][sample]} for t in diagnostics]
                proposals,_=propose_diagnostic_targets(kind,features,representations,objective,sampled,profile,directory=p.work.root,models=temporary_models,
                    threads=p.config.threads,reserve_fit=p.reserve_diagnostic_fit,check=check,memory_budget=p.config.max_rss_bytes//3)
                cache={'_models':temporary_models,'_directory':str(p.work.root),'_max_distance_ops':limits.max_distance_operations,'_population_size':len(si),'_membership_memory_bytes':p.config.max_rss_bytes//3,'_threads':p.config.threads}
                matches={c['id']:(0.,None) for c in targets if c['strategy']==kind}
                for proposal in proposals:
                    mask=apply(proposal['artifact'],sf,sr,cache=cache,check=check)
                    for candidate in targets:
                        if candidate['strategy']!=kind:continue
                        original_artifact=artifacts[candidate['membership_artifact']]
                        if proposal['artifact'].get('representation')!=original_artifact.get('representation'):continue
                        bindings=candidate.get('diagnostic_target_bindings')
                        if bindings:
                            if not any(b['name']==proposal.get('diagnostic_target_binding',{}).get('name') and b.get('diagnostic_head')==proposal.get('head') for b in bindings):continue
                        elif candidate.get('head')!=proposal.get('head'):continue
                        original=reference[candidate['id']];union=np.count_nonzero(mask['member']|original['member']);iou=np.count_nonzero(mask['member']&original['member'])/union if union else 1.
                        if iou>matches[candidate['id']][0] or matches[candidate['id']][1] is None:matches[candidate['id']]=(float(iou),float(np.mean(mask['available'])) if len(si) else 0.)
                for cid,(iou,coverage) in matches.items():outcomes[cid].append({'replicate':repeat,'membership_IoU':iou,'applicable_fraction':coverage,'refit_D_records':len(sample)})
                check('D perturbation refit stability')
        for candidate in targets:
            values=outcomes[candidate['id']]
            candidate['stability']={'method':'bounded_D_unit_bootstrap_refits_v2','seed':seed,'replicates':limits.stability_replicates,
                'profile':{'maximum_nodes':profile.max_nodes,'retained_candidates':profile.candidates_per_strategy,'D_row_limit':row_limit},
                'diagnostic_references':'Original D-only diagnostic targets fixed; refits resample whole admitted D units before the disclosed D cap.',
                'matching':'Largest frozen membership IoU on S features, within strategy, representation and diagnostic head; no S outcome selection.',
                'median_membership_IoU':float(np.median([v['membership_IoU'] for v in values])) if values else None,
                'results':values,'coverage_guarantee':False,'scope':'Product perturbation diagnostic; full-method qualification is separate.'}
            if candidate.get('diagnostic_target_bindings'):
                candidate['stability'].update(diagnostic_target_policy='historical_period_heads_and_matched_entity_delta_v1',
                    matching='Largest frozen membership IoU on S features within strategy, representation and a recorded D diagnostic target/head; no S outcome selection.')
