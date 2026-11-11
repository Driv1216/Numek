"""Partial-null D/S selection-to-confirmation with exactly enumerable gate truth.

Eight equiprobable feature cells avoid estimating null status from H labels or
an approximate oracle sample. This is a reduced-profile benchmark, not predictor
execution or a replacement for default-profile/continuous-feature experiments.
"""
import argparse
import csv
from datetime import datetime,timezone
from fractions import Fraction
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import traceback

import numpy as np
import qualify_pipeline as pipeline

PROTOCOL={'schema_version':'numek.cg4_partial_null_protocol/1.1',
    'seeds':{'development':[0,9],'qualification':[170000,170999]},'independent_rows':1200,
    'population':'Eight equiprobable Boolean feature cells; error .40 when a XOR b, otherwise .10. Labels are independent fair Bernoulli variables; supplied decisions flip on error.',
    'strategies':['structured','catboost','geometric'],'requested_families':[1,10,32],
    'family_selection':'Cycle requested size by seed offset modulo three. Freeze equally spaced ranks across the native S reconciliation order, including nonshortlisted candidates; size one uses the first rank. This stresses both adverse and nonadverse retained gates instead of taking only the strongest alternatives. If fewer exist, retain/report the actual family; never call it the requested size. No H or oracle selection.',
    'truth':'Exact rational member-minus-complement population risk, enumerating all eight cells with frozen gates. Null iff defined effect <= zero. Undefined truth or incomplete applicability is not silently called a true null.',
    'alpha':.05,'delta':0.,'diagnostics':'One-sided exact binomial excess false-confirmation test at .05, Holm across requested sizes 1/10/32. Also report exact Monte Carlo intervals, null/alternative/undefined counts and simultaneous interval noncoverage. Non-rejection is not proof of control.',
    'scope':'Reduced-profile partial-null families with correlated/overlapping gates; finite IID Bernoulli inference and explicit declared synthetic independence. No bootstrap, temporal/entity dependence, default-capacity or universal learner qualification.'}


def exact_effect(member,available):
    if len(member)!=8 or len(available)!=8 or not all(available):return None
    inside=[i for i,v in enumerate(member) if v];outside=[i for i,v in enumerate(member) if not v]
    if not inside or not outside:return None
    def rate(ids):return sum((Fraction(4 if bool(i&1)!=bool(i&2) else 1,10) for i in ids),Fraction())/len(ids)
    return rate(inside)-rate(outside)


def trial(seed,panel):
    from confidenceguard import InvestigationSpec,investigate,freeze_hypotheses,confirm_investigation,ConfirmationSpec
    from confidenceguard.features import normalize
    from confidenceguard.feature_contracts import FeatureField
    from confidenceguard.investigation_membership import apply
    start=PROTOCOL['seeds'][panel][0];requested=PROTOCOL['requested_families'][(seed-start)%3]
    rng=np.random.Generator(np.random.PCG64(seed));n=PROTOCOL['independent_rows']
    cells=rng.integers(0,8,n);labels=rng.integers(0,2,n)
    probability=np.where(((cells&1)>0)!=((cells&2)>0),.4,.1);errors=rng.random(n)<probability
    with tempfile.TemporaryDirectory(prefix='numek-cg4-partial-null-',dir='/private/tmp') as temporary:
        root=Path(temporary);path=root/'predictions.csv'
        with path.open('w',newline='') as stream:
            writer=csv.writer(stream);writer.writerow(['id','y','decision','a','b','c'])
            writer.writerows([i,int(labels[i]),int(labels[i]^errors[i]),*[str((int(cell)>>j)&1) for j in range(3)]] for i,cell in enumerate(cells))
        vectors=np.column_stack([((cells>>j)&1).astype(float) for j in range(3)]).astype('<f4');np.save(root/'vectors.npy',vectors)
        spec=InvestigationSpec.from_dict({'name':'Exactly enumerable partial-null investigation',
            'evaluation':{'task':{'kind':'binary_classification','classes':['0','1'],'positive_class':'1','outcome_definition':'Independent synthetic label'},
            'sources':[{'id':'data','path':str(path)}],
            'runs':[{'id':'model','source':'data','model':{'id':'synthetic-fixed','version':'1'},'key_columns':['id'],'prediction':'decision'}],
            'outcomes':{'source':'data','column':'y','key_columns':['id']}},
            'roles':{'namespace':f'cg4-partial-null-{seed}-{n}','unit':'independent_rows'},
            'features':[{'id':'context','availability':'at_decision','fields':[{'id':f,'column':f,'kind':'categorical'} for f in 'abc']}],
            'representations':[{'id':'geometry','matrix_path':str(root/'vectors.npy'),'keys_source':{'id':'keys','path':str(path)},'key_columns':['id'],'dimensions':3,'availability':'at_decision'}],
            'objectives':[{'id':'error','metric':'error_rate','run':'model','practical_threshold':0.}],
            'strategies':PROTOCOL['strategies'],'limits':{'max_nodes':2000,'max_depth':4,'candidates_per_strategy':64,'shortlist':4,'landmarks':32,'neighbors':8,'stability_replicates':1}})
        result=investigate(spec);ordered=result.data['investigation']['candidates']
        selected_candidates=[ordered[i] for i in np.linspace(0,len(ordered)-1,min(requested,len(ordered)),dtype=int)] if ordered else []
        selected=[c['id'] for c in selected_candidates]
        if not selected:return {'status':'completed','seed':seed,'requested_family':requested,'actual_family':0,'claims':[],
            'false_confirmation':False,'family_noncoverage':False,'no_candidates':True,'input_sha256':{'predictions':pipeline.sha(path),'vectors':pipeline.sha(root/'vectors.npy')}}
        protocol=ConfirmationSpec(sampling='independent_rows',upstream_independence='declared_independent',external_exposure='declared_unexposed',
            declaration_author='NUMEK finite-cell synthetic generator',declaration_reason='Independent RNG observations in an isolated study process; no predictor training or previous exposure.')
        frozen=freeze_hypotheses(result,selected,confirmation=protocol)
        # All identities are frozen before H. Mathematical truth is evaluated on
        # a separate exhaustive feature grid and cannot change candidate choice.
        fields={f'context.{f}':[normalize(str((i>>j)&1),FeatureField(f,f)) for i in range(8)] for j,f in enumerate('abc')}
        representations={'geometry':{'vectors':np.array([[(i>>j)&1 for j in range(3)] for i in range(8)],float),'available':np.ones(8,bool)}}
        cache={'_models':result.private['models'],'_directory':str(root),'_population_size':8,'_threads':2}
        effects={}
        for candidate in selected_candidates:
            gate=result.private['artifacts'][candidate['membership_artifact']];mask=apply(gate,fields,representations,cache=cache)
            effects[candidate['id']]=(exact_effect(mask['member'],mask['available']),int(mask['available'].sum()))
        assessed=confirm_investigation(frozen);claims=[]
        for row in assessed.data['investigation']['assessments']:
            effect,available=effects[row['candidate_id']];interval=row.get('interval')
            false=effect is not None and effect<=0 and row['state']=='confirmed'
            noncoverage=bool(effect is not None and interval and not Fraction.from_float(interval['lower'])<=effect<=Fraction.from_float(interval['upper']))
            claims.append({'candidate_id':row['candidate_id'],'hypothesis_id':row['hypothesis_id'],'state':row['state'],
                'truth':None if effect is None else {'numerator':effect.numerator,'denominator':effect.denominator,'effect':float(effect),'null':effect<=0},
                'applicable_population_cells':available,'interval':interval,'false_confirmation':bool(false),'noncoverage':noncoverage,'reason':row.get('reason')})
        return {'status':'completed','seed':seed,'requested_family':requested,'actual_family':len(selected),'claims':claims,
            'false_confirmation':any(c['false_confirmation'] for c in claims),'family_noncoverage':any(c['noncoverage'] for c in claims),
            'no_candidates':False,'input_sha256':{'predictions':pipeline.sha(path),'vectors':pipeline.sha(root/'vectors.npy')},
            'frozen_family_digest':frozen.family_digest,'admitted_limits':spec.limits.to_dict(),'admitted_config':result.private['config'],
            'discovery_execution':result.execution,'confirmation_execution':assessed.execution}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--panel',choices=PROTOCOL['seeds'],required=True);parser.add_argument('--out',required=True)
    parser.add_argument('--count',type=int,default=1);parser.add_argument('--offset',type=int,default=0);parser.add_argument('--worker',action='store_true');parser.add_argument('--seed',type=int)
    args=parser.parse_args();profile={'protocol':PROTOCOL,'harness_sha256':pipeline.sha(__file__),'source_sha256':pipeline.identity(),
        'packages':pipeline.runtime_versions(),'panel':args.panel}
    if args.worker:
        started=time.monotonic()
        try:record=trial(args.seed,args.panel)
        except Exception as exc:record={'status':'execution_failure','seed':args.seed,'error_code':getattr(exc,'code',None),'traceback':traceback.format_exc()}
        if pipeline.identity()!=profile['source_sha256'] or pipeline.sha(__file__)!=profile['harness_sha256']:record.update(status_before_invalidation=record['status'],status='invalidated_source_change')
        record.update(profile=profile,seconds=time.monotonic()-started,generated_at=datetime.now(timezone.utc).isoformat())
        with Path(args.out).open('x') as stream:json.dump(record,stream,sort_keys=True,indent=2,allow_nan=False);stream.write('\n')
        return
    first,last=PROTOCOL['seeds'][args.panel]
    if args.offset<0 or args.count<1 or first+args.offset+args.count-1>last:parser.error('Outside the fixed seed panel.')
    out=Path(args.out);out.mkdir(parents=True,exist_ok=True)
    for seed in range(first+args.offset,first+args.offset+args.count):
        path=out/f'{seed}.json'
        if not path.exists():
            pending=path.with_suffix('.pending');subprocess.run([sys.executable,'-B',__file__,'--worker','--seed',str(seed),'--panel',args.panel,'--out',str(pending)],check=True);pending.rename(path)
        row=json.loads(path.read_text())
        if row['profile']!=profile or row['seed']!=seed or row['status']!='completed':raise RuntimeError('Preserve mismatched/failed evidence before diagnosis.')
        print(json.dumps({k:row[k] for k in ('seed','status','requested_family','actual_family','false_confirmation','seconds')}),flush=True)


if __name__=='__main__':main()
