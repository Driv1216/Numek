"""Locked finite-procedure diagnostics, with independent interval references.

This campaign exercises frozen inference kernels. It is deliberately distinct
from the separately required selection-to-confirmation full-pipeline null runs.
"""
import argparse
from datetime import datetime,timezone
from functools import lru_cache
import hashlib
import inspect
import json
from pathlib import Path
import time
import numpy as np
from scipy.stats import beta,binomtest
from confidenceguard.confirmation import binomial_interval,bounded_interval,finite_interval,classify,orient
from confidenceguard.investigation_contracts import FailureObjectiveSpec


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--out',required=True);args=parser.parse_args()
    protocol=Path(__file__).with_name('qualification_protocol.json').read_bytes();locked=json.loads(protocol)
    panel=locked['seed_panels']['finite_statistics'];start=time.monotonic();rng=np.random.default_rng(panel['start'])
    rows=[];parity=[];n=100;trials=panel['count']
    @lru_cache(None)
    def implemented(k,n,alpha):return binomial_interval(np.r_[np.ones(k),np.zeros(n-k)],alpha)
    for m in (1,10,32):
        alpha=.05/m
        for k in range(n+1):
            actual=implemented(k,n,alpha);reference=(0. if k==0 else beta.ppf(alpha/2,k,n-k+1),1. if k==n else beta.ppf(1-alpha/2,k+1,n-k))
            parity.append(max(abs(actual[0]-reference[0]),abs(actual[1]-reference[1])))
        for probability in (.01,.1,.5,.99):
            successes=rng.binomial(n,probability,size=(trials,m));lower=np.array([implemented(k,n,alpha)[0] for k in range(n+1)]);upper=np.array([implemented(k,n,alpha)[1] for k in range(n+1)])
            failed=np.any((lower[successes]>probability)|(upper[successes]<probability),axis=1);count=int(failed.sum())
            interval=binomtest(count,trials).proportion_ci(method='exact')
            rows.append({'kind':'simultaneous_Clopper_Pearson_coverage','family_size':m,'probability':probability,'n_per_hypothesis':n,
                'trials':trials,'family_noncoverage':count,'empirical_noncoverage':count/trials,'MC_95_interval':[float(interval.low),float(interval.high)],
                'diagnostic_p':float(binomtest(count,trials,.05,alternative='greater').pvalue),'nominal_error':.05})
    # Actual component composition and adverse-effect orientation, including an
    # absolute-bias null. No simulated H is used to select a hypothesis.
    for direction in ('higher','lower','absolute'):
        objective=FailureObjectiveSpec('contrast','error_rate','model',direction=direction,practical_threshold=.0)
        count=0
        for _ in range(trials):
            a=rng.binomial(n,.1);b=rng.binomial(n,.1)
            left=implemented(int(a),n,.025);right=implemented(int(b),n,.025);left=orient(left,objective);right=orient(right,objective)
            interval=(left[0]-right[1],left[1]-right[0]);count+=classify(interval,0.)=='confirmed'
        ci=binomtest(count,trials).proportion_ci(method='exact')
        rows.append({'kind':'component_contrast_null','direction':direction,'trials':trials,'false_confirmations':count,'empirical_error':count/trials,
            'MC_95_interval':[float(ci.low),float(ci.high)],'diagnostic_p':float(binomtest(count,trials,.05,alternative='greater').pvalue),'nominal_error':.05})
    # Predeclared Holm diagnostics control the chance of spuriously rejecting a
    # valid simulation panel; a non-rejection does not establish nominal control.
    ordered=sorted(range(len(rows)),key=lambda i:rows[i]['diagnostic_p']);running=0.
    for rank,i in enumerate(ordered):
        running=max(running,min(1.,rows[i]['diagnostic_p']*(len(rows)-rank)));rows[i]['Holm_adjusted_diagnostic_p']=running
    functions={f.__name__:hashlib.sha256(inspect.getsource(f).encode()).hexdigest() for f in (binomial_interval,bounded_interval,finite_interval,classify,orient)}
    data={'schema_version':'numek.cg4_statistical_qualification/1.0','status':'completed','generated_at':datetime.now(timezone.utc).isoformat(),
        'protocol_sha256':hashlib.sha256(protocol).hexdigest(),'function_sha256':functions,'seed':panel['start'],
        'trials_per_scenario':trials,'total_frozen_hypothesis_experiments':len(rows)*trials,'rows':rows,
        'reference_parity_max_abs':float(max(parity)),'reference_parity_tolerance':1e-10,'parity_pass':bool(max(parity)<=1e-10),
        'excess_error_diagnostic_rejections':[i for i,r in enumerate(rows) if r['Holm_adjusted_diagnostic_p']<.05],
        'seconds':time.monotonic()-start,'scope':'IID frozen Bernoulli procedures only; does not qualify bootstrap, discovery, dependence, full-pipeline selection, or external independence.'}
    path=Path(args.out);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x') as stream:json.dump(data,stream,sort_keys=True,indent=2);stream.write('\n')
    print(json.dumps({k:data[k] for k in ('parity_pass','excess_error_diagnostic_rejections','total_frozen_hypothesis_experiments','seconds')}))


if __name__=='__main__':main()
