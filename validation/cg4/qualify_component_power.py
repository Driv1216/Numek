"""Locked power/availability panel for the separate component-BCa candidate.

The candidate remains disabled. This panel cannot qualify unseen distributions,
32-hypothesis tails, other objectives, or the complete discovery pipeline.
"""
import argparse
from collections import Counter
from dataclasses import replace
from datetime import datetime,timezone
import hashlib
import importlib.metadata
import inspect
import json
from pathlib import Path
import time

import numpy as np
from scipy.stats import binomtest
from threadpoolctl import threadpool_limits

from confidenceguard.confirmation import approximate_interval
from confidenceguard.inference import _replicates,preflight
from qualify_approximate import sample
from qualify_composed_approximate import composed

SCENARIOS=('normal_mean','skew_exponential','unequal_complete_clusters')
PROTOCOL={
    'schema_version':'numek.cg4_component_BCa_power/1.0',
    'method':'component_BCa_contrast_candidate_v1','scenarios':list(SCENARIOS),
    'qualification_seed_range':[200000,200999],'development_seed_range':[0,9],
    'independent_units':200,'replicates':20000,'family_size':1,'elementary_intervals':2,
    'confidence':.95,'true_adverse_effect':1.,'practical_threshold':.15,
    'population':'Same locked null generators plus a fixed +1 contribution for every member event. Unequal independent clusters retain event weighting.',
    'acceptance':'At all 1000 trials per scenario, Bonferroni-simultaneous exact lower Monte Carlo bounds must exceed .80 for confirmation probability and .90 for interval availability. Refusals count as nonconfirmations. Coverage diagnostics and all limitations remain separate.',
    'diagnostic_allocation':'.05 / (3 scenarios * 2 endpoints); two-sided exact binomial intervals are conservative for these lower-bound diagnostics.',
    'rationale':'Useful power for a predeclared large unit-standard-deviation contrast; this does not impose a universal product effect threshold or promise power at smaller effects.',
    'product_status':'Experimental candidate; not enabled. Extreme tails, multiple hypotheses, transformations, support envelopes and complete product qualification remain required.'}


def power_sample(seed,scenario):
    values,objective,spec,units,_=sample(seed,scenario)
    values=values.copy()
    values[:,2]+=PROTOCOL['true_adverse_effect']*values[:,3]
    return values,replace(objective,practical_threshold=PROTOCOL['practical_threshold']),spec,units


def support(values,units):
    result=[]
    for column in (3,1):
        selected=values[:,column]>0;_,index=np.unique(units[selected],return_inverse=True)
        weights=np.bincount(index).astype(float)
        result.append({'events':int(selected.sum()),'independent_units':len(weights),
            'effective_units':float(weights.sum()**2/(weights@weights)) if len(weights) else 0.})
    return result


def summary(rows,panel):
    output=[];allocation=.05/(len(SCENARIOS)*2)
    for scenario in SCENARIOS:
        selected=[r for r in rows if r['scenario']==scenario];n=len(selected)
        if not n:continue
        available=[r['result'] for r in selected if r['result']['status']=='available']
        confirmations=sum(r['lower']>PROTOCOL['practical_threshold'] for r in available)
        ci=lambda count:binomtest(count,n).proportion_ci(confidence_level=1-allocation,method='exact')
        power=ci(confirmations);availability=ci(len(available));complete=panel=='qualification' and n==1000
        output.append({'scenario':scenario,'trials':n,'available':len(available),'confirmations':confirmations,
            'confirmation_probability_MC_interval':[float(power.low),float(power.high)],
            'availability_MC_interval':[float(availability.low),float(availability.high)],
            'refusals':dict(Counter(r['result'].get('reason') for r in selected if r['result']['status']!='available')),
            'criterion_met':bool(complete and power.low>.80 and availability.low>.90),
            'coverage_failures':sum(not r['lower']<=PROTOCOL['true_adverse_effect']<=r['upper'] for r in available)})
    return {'rows':output,'panel_complete':panel=='qualification' and len(rows)==3000,
        'scope':'Power and availability only; does not supersede the retained null/coverage diagnostics or qualify the disabled candidate generally.'}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--panel',choices=('development','qualification'),required=True)
    parser.add_argument('--out',required=True);args=parser.parse_args()
    directory=Path(args.out);directory.mkdir(parents=True,exist_ok=True)
    functions=(composed,approximate_interval,_replicates,preflight,sample,power_sample,support,summary)
    profile={'protocol':PROTOCOL,'panel':args.panel,'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'function_sha256':{f.__name__:hashlib.sha256(inspect.getsource(f).encode()).hexdigest() for f in functions},
        'runtime':{name:importlib.metadata.version(name) for name in ('numpy','scipy','threadpoolctl')}}
    profile_path=directory/'profile.json'
    if profile_path.exists() and json.loads(profile_path.read_text())!=profile:raise RuntimeError('Preserve the prior panel and use another output directory.')
    if not profile_path.exists():profile_path.write_text(json.dumps(profile,sort_keys=True,indent=2)+'\n')
    start,stop=PROTOCOL[args.panel+'_seed_range'];rows=[]
    with threadpool_limits(limits=2):
        for scenario in SCENARIOS:
            for seed in range(start,stop+1):
                destination=directory/f'{scenario}-{seed}.json'
                if destination.exists():
                    row=json.loads(destination.read_text())
                    if row['seed']!=seed or row['scenario']!=scenario or row['profile_digest']!=hashlib.sha256(json.dumps(profile,sort_keys=True).encode()).hexdigest():raise RuntimeError('Existing trial identity differs.')
                else:
                    started=time.monotonic();values,objective,spec,units=power_sample(seed,scenario);arms=support(values,units)
                    if any(a['independent_units']<spec.minimum_units or a['effective_units']<spec.minimum_units for a in arms):
                        result={'status':'unavailable','reason':'insufficient_conditional_independent_support'}
                    else:result=composed(values,objective,spec,units)
                    row={'scenario':scenario,'seed':seed,'result':result,'support':arms,
                        'profile_digest':hashlib.sha256(json.dumps(profile,sort_keys=True).encode()).hexdigest(),
                        'input_sha256':hashlib.sha256(values.tobytes()+units.tobytes()).hexdigest(),
                        'seconds':time.monotonic()-started,'generated_at':datetime.now(timezone.utc).isoformat()}
                    pending=destination.with_suffix('.pending')
                    with pending.open('w') as stream:json.dump(row,stream,sort_keys=True,indent=2,allow_nan=False);stream.write('\n')
                    pending.rename(destination)
                    print(json.dumps({'scenario':scenario,'seed':seed,'status':result['status'],'seconds':row['seconds']}),flush=True)
                rows.append(row)
    final={'profile':profile,**summary(rows,args.panel)};path=directory/'summary.json'
    if path.exists() and json.loads(path.read_text())!=final:raise RuntimeError('Existing completed summary differs.')
    if not path.exists():path.write_text(json.dumps(final,sort_keys=True,indent=2)+'\n')


if __name__=='__main__':main()
