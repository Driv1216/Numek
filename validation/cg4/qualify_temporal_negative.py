"""Deliberately misuse IID Bernoulli intervals on stationary dependent data.

Validation-only negative evidence. CG4 refuses declared temporal dependence;
this is not an alternative confirmation procedure or a temporal qualification.
"""
import argparse
import hashlib
import inspect
import json
from pathlib import Path
import time

import numpy as np
from scipy.stats import binomtest

from confidenceguard.confirmation import binomial_interval

PROTOCOL={'schema_version':'numek.cg4_temporal_IID_negative_protocol/1.0',
    'trials_per_profile':10000,'observations':200,'stationary_probability':.1,
    'persistence':[0.,.8,.95],'seeds':[190000,190001,190002],'alpha':.05,
    'sampling':'Independent sequences; within each sequence keep previous Bernoulli state with probability rho, otherwise draw fresh Bernoulli(p). Initial state is Bernoulli(p), so every marginal has mean p.',
    'interpretation':'rho=0 is an IID numerical control. Other profiles deliberately violate the interval assumption; excess error is negative evidence, not a defect in IID coverage or a supported temporal method.'}


def counts(rng,trials,n,p,rho):
    state=rng.random(trials)<p;total=state.astype(np.int64)
    for _ in range(1,n):
        state=np.where(rng.random(trials)<rho,state,rng.random(trials)<p)
        total+=state
    return total


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--out',required=True);args=parser.parse_args()
    start=time.monotonic();n=PROTOCOL['observations'];p=PROTOCOL['stationary_probability'];alpha=PROTOCOL['alpha'];trials=PROTOCOL['trials_per_profile']
    endpoints=[binomial_interval(np.r_[np.ones(k),np.zeros(n-k)],alpha) for k in range(n+1)]
    lower,upper=np.asarray(endpoints).T;rows=[]
    for rho,seed in zip(PROTOCOL['persistence'],PROTOCOL['seeds']):
        successes=counts(np.random.Generator(np.random.PCG64(seed)),trials,n,p,rho)
        missed=(lower[successes]>p)|(upper[successes]<p);adverse=lower[successes]>p
        k=int(missed.sum());ci=binomtest(k,trials).proportion_ci(method='exact')
        rows.append({'persistence':rho,'seed':seed,'trials':trials,'noncoverage':k,
            'noncoverage_MC95':[float(ci.low),float(ci.high)],'false_ceiling_failures':int(adverse.sum()),
            'mean_observed_rate':float(successes.mean()/n),
            'count_variance':float(successes.var()),
            'population_count_variance':float(p*(1-p)*(n+2*sum((n-lag)*rho**lag for lag in range(1,n)))),
            'excess_error_diagnostic_p':float(binomtest(k,trials,alpha,alternative='greater').pvalue),
            'count_stream_sha256':hashlib.sha256(successes.astype('<i8').tobytes()).hexdigest()})
    running=0.
    for rank,i in enumerate(sorted(range(len(rows)),key=lambda i:rows[i]['excess_error_diagnostic_p'])):
        running=max(running,min(1.,rows[i]['excess_error_diagnostic_p']*(len(rows)-rank)))
        rows[i]['Holm_adjusted_diagnostic_p']=running
    record={'schema_version':'numek.cg4_temporal_IID_negative_evidence/1.0','protocol':PROTOCOL,'rows':rows,
        'interval_function_sha256':hashlib.sha256(inspect.getsource(binomial_interval).encode()).hexdigest(),
        'harness_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'numpy':np.__version__,'scipy':__import__('scipy').__version__,'seconds':time.monotonic()-start,
        'scope':'Frozen IID kernel and stationary synthetic Markov negative controls only. Product confirmation is not run, no H freshness/declarations are fabricated, and no temporal procedure is enabled. A support floor or bootstrap replication count cannot establish independent sampling.'}
    path=Path(args.out)
    with path.open('x') as stream:json.dump(record,stream,indent=2,sort_keys=True,allow_nan=False);stream.write('\n')
    print(json.dumps({'rows':rows,'seconds':record['seconds']}))


if __name__=='__main__':main()
