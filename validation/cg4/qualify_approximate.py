"""Frozen-estimand bootstrap operating-envelope simulation; failures are evidence."""
import argparse
from collections import Counter
from dataclasses import replace
from datetime import datetime,timezone
import hashlib
import inspect
import json
from pathlib import Path
import time
import numpy as np
from scipy.stats import binomtest
from threadpoolctl import threadpool_limits
from confidenceguard.confirmation import approximate_interval
from confidenceguard.inference import _replicates,preflight,rank_stat
from confidenceguard.investigation_contracts import ConfirmationSpec,FailureObjectiveSpec

SCENARIOS=('normal_mean','skew_exponential','heavy_lognormal','imbalanced_arms','unequal_complete_clusters','ranking_AUC_ties','ranking_AP_ties')


def sample(seed,scenario):
    rng=np.random.default_rng(seed);n=200;units=np.arange(n);sampling='independent_rows';method='bca';ranked=None
    if scenario=='unequal_complete_clusters':
        sizes=np.minimum(50,rng.geometric(.2,n));units=np.repeat(np.arange(n),sizes)
        value=np.repeat(rng.normal(0,1,n),sizes)+rng.normal(0,.2,len(units));group=units<100;sampling='independent_entities'
    else:
        group=np.arange(n)<(50 if scenario=='imbalanced_arms' else 100)
        value=rng.exponential(1,n) if scenario=='skew_exponential' else rng.lognormal(0,1.5,n) if scenario=='heavy_lognormal' else rng.normal(0,1,n)
    n=len(units);comparison=~group
    values=np.column_stack((np.where(comparison,value,0),comparison.astype(float),np.where(group,value,0),group.astype(float)))
    metric='bias';direction='higher'
    if scenario.startswith('ranking_'):
        y=rng.integers(0,2,n);scores=rng.integers(0,8,n)/7
        metric='roc_auc' if 'AUC' in scenario else 'average_precision';method='percentile';direction='lower'
        # Independent scores and labels imply both groups have population AUC
        # and AP .5 under balanced Bernoulli labels (finite-sample AP is biased).
        ranked=(y,scores,group,comparison)
    objective=FailureObjectiveSpec('contrast',metric,'supplied',direction=direction,practical_threshold=0.)
    protocol=ConfirmationSpec(method=method,sampling=sampling,replicates=20000,replicate_policy='fixed',seed=seed+700000)
    return values,objective,protocol,units,ranked


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--scenario',choices=SCENARIOS,required=True);parser.add_argument('--out',required=True);parser.add_argument('--offset',type=int,default=0);parser.add_argument('--count',type=int,default=1000);args=parser.parse_args()
    if args.offset<0 or args.count<1 or args.offset+args.count>1000:parser.error('Outside the locked 1000-seed panel.')
    directory=Path(args.out);directory.mkdir(parents=True,exist_ok=True)
    functions={f.__name__:hashlib.sha256(inspect.getsource(f).encode()).hexdigest() for f in (approximate_interval,_replicates,preflight,rank_stat,sample)}
    profile={'scenario':args.scenario,'function_sha256':functions,'replicates':20000,'family_size':1,'seed_start':50000,'sampling_units':200,
             'null_effect':0.,'scope':'Frozen independent-unit mean/ratio and ranking contrasts; does not qualify arbitrary distributions or adaptive selection.'}
    path=directory/'profile.json'
    if path.exists() and json.loads(path.read_text())!=profile:raise RuntimeError('Preserve existing simulation evidence under its original profile.')
    path.write_text(json.dumps(profile,sort_keys=True,indent=2)+'\n')
    with threadpool_limits(limits=2):
        for seed in range(50000+args.offset,50000+args.offset+args.count):
            destination=directory/f'{seed}.json'
            if destination.exists():continue
            started=time.monotonic();values,objective,protocol,units,ranked=sample(seed,args.scenario)
            result=approximate_interval(values,objective,protocol,family_size=1,units=units,work_budget=2_000_000_000,check=lambda *args:None,ranked=ranked)
            record={'seed':seed,'result':result,'seconds':time.monotonic()-started,'generated_at':datetime.now(timezone.utc).isoformat(),
                    'input_digest':hashlib.sha256(values.tobytes()+np.asarray(units).tobytes()+(np.asarray(ranked[:2]).tobytes() if ranked else b'')).hexdigest()}
            with destination.open('x') as stream:json.dump(record,stream,sort_keys=True,indent=2,allow_nan=False);stream.write('\n')
            print(json.dumps({'seed':seed,'status':result['status'],'reason':result.get('reason'),'seconds':record['seconds']}),flush=True)
    rows=[json.loads(p.read_text()) for p in sorted(directory.glob('*.json')) if p.name not in {'profile.json','summary.json'}]
    available=[r['result'] for r in rows if r['result']['status']=='available'];failures=sum(not r['lower']<=0<=r['upper'] for r in available);claims=sum(r['lower']>0 for r in available)
    total=len(rows);ci=binomtest(failures,len(available)).proportion_ci(method='exact') if available else None
    summary={'profile':profile,'completed_trials':total,'required_trials':1000,'panel_complete':total==1000,'available':len(available),'noncoverage':failures,
             'false_confirmation':claims,'refusals':dict(Counter(r['result'].get('reason') for r in rows if r['result']['status']!='available')),
             'coverage_bounds_with_refusals':[(len(available)-failures)/total,(total-failures)/total],
             'conditional_noncoverage_MC95':[ci.low,ci.high] if ci else None,
             'excess_noncoverage_diagnostic_p':binomtest(failures,len(available),.05,alternative='greater').pvalue if available else None,
             'diagnostic_multiplicity':'Holm across all seven locked scenarios, evaluated only after completing their panels.',
             'interpretation':'Non-rejection is not a coverage theorem; refusal is not successful interval coverage. Correctly implemented undercoverage is a method-qualification failure.'}
    (directory/'summary.json').write_text(json.dumps(summary,sort_keys=True,indent=2)+'\n')


if __name__=='__main__':main()
