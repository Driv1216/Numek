"""Bounded predicate lattice; no marginal-effect pruning of interactions."""
from collections import Counter
import heapq
import math
import numpy as np
from .features import value,predicate_masks
from .contracts import digest
from .investigation_membership import seal


def bits(mask):return int.from_bytes(np.packbits(mask,bitorder='little').tobytes(),'little')


def heads(objective,loss):
    if objective.spec.direction in {'absolute','nominal_shortfall'} or objective.spec.metric in {'bias','calibration_residual','reliability_diagram'}:
        return [('positive',loss),('negative',-loss)]
    return [('negative',-loss)] if objective.spec.direction=='lower' else [('positive',loss)]


def numeric_cuts(observed,bins):
    """D observation quantiles, preserving exact values and empirical ties."""
    ordered=sorted(observed)
    return sorted({ordered[int(i*(len(ordered)-1)/bins)] for i in range(1,bins)}) if ordered else []


def propose(features,eligible,loss,objective,limits,check=lambda *args:None,*,predicate_cache=None):
    atoms=[];full=(1<<len(eligible))-1;eligible_bits=bits(eligible)
    for fid,cells in sorted(features.items()):
        observed=[value(c) for c in cells if c['state']=='observed']
        if not cells:continue
        kind=cells[0]['kind']
        if kind in {'text','asset'}:continue
        if kind in {'categorical','boolean'}:
            common=Counter(c['canonical'] for c in cells if c['state']=='observed').most_common(limits.categorical_values)
            choices=[('eq',v) for v,_ in common]
            if len(common)<len(set(observed)):choices.append(('not_in',[v for v,_ in common]))
        else:
            cuts=numeric_cuts(observed,limits.numeric_bins)
            by_value={value(c):c['canonical'] for c in cells if c['state']=='observed'}
            choices=[(op,by_value[cut]) for cut in cuts for op in ('le','gt')]
            choices.extend(('interval',[by_value[left],by_value[right]]) for position,left in enumerate(cuts) for right in cuts[position+1:])
        choices.extend(('state',state) for state in ('missing','invalid') if any(c['state']==state for c in cells))
        for op,bound in choices:
            clause={'field':fid,'op':op,'value':bound,'kind':kind}
            _,mask=predicate_masks(cells,clause,predicate_cache)
            bit=bits(mask)
            if (bit&eligible_bits).bit_count()>=limits.minimum_discovery_support:atoms.append((clause,bit))
    best=[];nodes=0;truncated=False;counter=0;seen=set();head_data=[]
    for label,target in heads(objective,loss):
        finite=target[eligible];base=float(np.mean(finite)) if len(finite) else 0
        binary=bool(len(finite) and set(np.unique(finite)).issubset({0.,1.}))
        head_data.append((label,target,base,bits(eligible&(target==1)) if binary else None))
    # Breadth by depth prevents input ordering from spending all work on one deep path.
    def walk(start,remaining,mask,clauses,fields):
        nonlocal nodes,truncated,counter
        for j in range(start,len(atoms)):
            if nodes>=limits.max_nodes:truncated=True;return
            clause,atom=atoms[j]
            if clause['field'] in fields:continue
            combined=mask&atom;support=(combined&eligible_bits).bit_count();nodes+=1
            if nodes%256==0:check('structured predicate lattice')
            if support<limits.minimum_discovery_support:continue
            path=clauses+[clause]
            if remaining>1:
                walk(j+1,remaining-1,combined,path,fields|{clause['field']})
                if truncated:return
                continue
            signature=digest(path)
            if signature in seen:continue
            seen.add(signature)
            for label,target,base,positive in head_data:
                if positive is not None:mean=(combined&positive).bit_count()/support
                else:
                    selected=np.unpackbits(np.frombuffer(combined.to_bytes((len(eligible)+7)//8,'little'),dtype=np.uint8),bitorder='little')[:len(eligible)].astype(bool)&eligible
                    mean=float(np.mean(target[selected]))
                utility=(mean-base)*math.sqrt(support)
                if utility<=0:continue
                counter+=1;entry=(utility,counter,path,label,support)
                if len(best)<limits.candidates_per_strategy:heapq.heappush(best,entry)
                elif entry[:2]>best[0][:2]:heapq.heapreplace(best,entry)
    for depth in range(1,min(limits.max_depth,len(features))+1):
        walk(0,depth,full,[],set())
        if truncated:break
    candidates=[]
    best=sorted(best,reverse=True)
    atom_masks={digest(c):mask for c,mask in atoms}
    singles=[]
    for utility,_,clauses,head,support in sorted(best,reverse=True):
        artifact=seal('structured',{'clauses':clauses},features=sorted({c['field'] for c in clauses}),objective=objective.identity)
        candidates.append({'artifact':artifact,'D_proxy_utility':utility,'D_conditional_support':support,'head':head,'complexity':len(clauses)})
        mask=full
        for clause in clauses:mask&=atom_masks[digest(clause)]
        singles.append((clauses,head,mask))
    # Small D-only disjunctions recover disconnected interaction mechanisms such
    # as XOR without inventing an opaque nonlinear gate.
    for i,(left,head,a) in enumerate(singles[:16]):
        for right,other,b in singles[i+1:16]:
            if head!=other:continue
            union=(a|b)&eligible_bits;support=union.bit_count()
            if support<limits.minimum_discovery_support:continue
            target=next(t for label,t,_,_ in head_data if label==head);base=next(base for label,_,base,_ in head_data if label==head)
            selected=np.unpackbits(np.frombuffer(union.to_bytes((len(eligible)+7)//8,'little'),np.uint8),bitorder='little')[:len(eligible)].astype(bool)
            utility=(float(np.mean(target[selected]))-base)*math.sqrt(support)
            artifact=seal('structured',{'any_of':[left,right]},features=sorted({c['field'] for c in left+right}),objective=objective.identity)
            candidates.append({'artifact':artifact,'D_proxy_utility':utility,'D_conditional_support':support,'head':head,'complexity':len(left)+len(right)})
    candidates=sorted(candidates,key=lambda c:(-c['D_proxy_utility'],c['artifact']['artifact_digest']))[:limits.candidates_per_strategy]
    return candidates,{'strategy':'structured','nodes':nodes,'atoms':len(atoms),'search_complete':not truncated,
                       'proposal_vocabulary':'D_observation_quantiles_and_independent_state_predicates_v3',
                       'search_class':'Conjunctions across distinct fields; top-16 D-only disjunction proposals are additional heuristics.',
                       'max_depth':limits.max_depth,'search_objective':'D diagnostic proxy excess times sqrt conditional support',
                       'global_authoritative_optimum_claimed':False,'marginal_effect_pruning':False}
