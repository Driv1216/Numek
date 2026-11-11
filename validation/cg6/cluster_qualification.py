"""Locked six-design qualification; expected assumption violations are refusals."""
from pathlib import Path
import hashlib
import json
import numpy as np
from scipy.stats import binom
from confidenceguard.robustness.inference import cluster_ratio
from confidenceguard import EvaluationError

ROOT=Path(__file__).resolve().parent
PROTOCOL={'schema':'cg6.cluster_qualification/1.0','trials':2000,'units':80,'seed':20261107,'alpha':.05,
    'acceptance':'For valid designs, covered + unavailable >= binomial .001 lower quantile at p=.95; all invalid-size probes refuse.',
    'designs':['equal_size_shared_Bernoulli','unequal_size_independent_risk','size_dependent_risk','signed_paired_difference','zero_size_clusters','violated_true_size_bound'],
    'standing':'Numerical integration qualification plus written Hoeffding/union-bound derivation; no bootstrap or arbitrary dependence guarantee'}


def main():
    lock=ROOT/'cluster_qualification_protocol.json'
    if lock.exists() and json.loads(lock.read_text())!=PROTOCOL:raise RuntimeError('Cluster protocol changed')
    if not lock.exists():lock.write_text(json.dumps(PROTOCOL,indent=2)+'\n')
    output=ROOT/'results'/'cluster-qualification.json'
    if output.exists():raise RuntimeError('Reuse completed cluster qualification; diagnose defects before any targeted rerun')
    rng=np.random.Generator(np.random.PCG64(PROTOCOL['seed']));records=[];minimum=int(binom.ppf(.001,2000,.95))
    for design in PROTOCOL['designs']:
        covered=unavailable=refused=0;n=PROTOCOL['units']
        for trial in range(PROTOCOL['trials']):
            bounds=(0.,1.);maximum=5
            if design=='equal_size_shared_Bernoulli':d=np.full(n,4);a=d*rng.binomial(1,.2,n);theta=.2
            elif design=='unequal_size_independent_risk':d=rng.choice([1,5],n);a=rng.binomial(d,.6);theta=.6
            elif design=='size_dependent_risk':d=rng.integers(1,6,n);a=rng.binomial(d,d/6);theta=11/18
            elif design=='signed_paired_difference':d=rng.integers(1,6,n);a=rng.binomial(d,.2)-rng.binomial(d,.4);theta=-.2;bounds=(-1.,1.)
            elif design=='zero_size_clusters':d=rng.choice([0,5],n);a=rng.binomial(d,.4);theta=.4
            else:d=np.full(n,5);a=rng.binomial(d,.3);theta=.3;maximum=2
            try:r=cluster_ratio(a,d,max_size=maximum,bounds=bounds,alpha=.05)
            except EvaluationError:
                refused+=1;continue
            if r['state']!='available':unavailable+=1
            else:covered+=r['lower']<=theta<=r['upper']
        passed=refused==2000 if design=='violated_true_size_bound' else refused==0 and covered+unavailable>=minimum
        records.append({'design':design,'trials':2000,'covered_available':int(covered),'unavailable':unavailable,'refused':refused,'passed':passed})
    output.parent.mkdir(parents=True,exist_ok=True)
    kernel=ROOT.parent.parent/'src'/'confidenceguard'/'robustness'/'inference.py'
    receipt={'protocol':PROTOCOL,'minimum_nonfalse_claim_trials':minimum,'records':records,'passed':all(r['passed'] for r in records),'kernel_sha256':hashlib.sha256(kernel.read_bytes()).hexdigest()}
    output.write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt,indent=2))
    if not receipt['passed']:raise SystemExit(1)


if __name__=='__main__':main()
