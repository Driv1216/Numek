"""Locked matched landmark/fallback comparison; negative evidence is retained.

This campaign can reject promotion. It cannot certify relative efficiency while
other qualification workers compete for the host's resources.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys

import numpy as np
from scipy.stats import binom

import qualify_pipeline as pipeline

FAMILIES=('curved_region','heterogeneous_density')
PROTOCOL={
    'schema_version':'numek.cg4_landmark_comparison/1.0',
    'families':list(FAMILIES),'seeds':[100000,100039],'independent_units':40000,
    'methods':['geometric','landmark'],'selection':'Unchanged native S selection; no H or oracle gate selection.',
    'primary':'Median paired H IoU difference, landmark minus geometric fallback, at least .10 in each predeclared family.',
    'secondary':'Positive paired uncertainty lower bounds in both families; no overall median IoU regression greater than .05.',
    'uncertainty':'20000 paired seed-bootstrap medians, Bonferroni two-sided intervals across two families. Also require a positive conservative distribution-free order-statistic median lower bound under IID seed pairs; ties do not supply a coverage theorem for the bootstrap.',
    'bootstrap_seed':955001,'bootstrap_replicates':20000,'comparison_alpha':.05,
    'futility':'If even replacing every unfinished paired gain with its mathematical maximum 1 leaves the 40-pair median below .10, promotion is impossible on this locked panel. Stop as negative qualification evidence; do not claim a complete panel or compute positive uncertainty claims from the stopped sample.',
    'resources':'Identical two-thread default absolute admission budgets and complete fresh-process workers. Concurrent-host timings/RSS are recorded but cannot establish the required controlled <=2x runtime and <=1.5x memory comparison.',
    'promotion':'Only complete recovery/uncertainty criteria plus separately valid efficiency/absolute-resource, overlap, stability and out-of-sample evidence can promote the original NUMEK method. Failure retains the fallback; neither implementation nor promotion success is presumed.'}


def maximum_possible_median(gains,total=40):
    values=np.asarray(gains,float)
    if values.ndim!=1 or len(values)>total or not np.isfinite(values).all() or (np.abs(values)>1).any():raise ValueError('Invalid bounded paired gains.')
    return float(np.median(np.r_[values,np.ones(total-len(values))]))


def paired_intervals(gains,seed):
    values=np.asarray(gains,float);n=len(values)
    if n!=40 or not np.isfinite(values).all():raise ValueError('Uncertainty requires all 40 fixed pairs.')
    alpha=PROTOCOL['comparison_alpha']/len(FAMILIES);rng=np.random.Generator(np.random.PCG64(seed))
    replicates=np.empty(PROTOCOL['bootstrap_replicates'])
    for start in range(0,len(replicates),256):
        count=min(256,len(replicates)-start);draws=rng.integers(0,n,size=(count,n))
        replicates[start:start+count]=np.median(values[draws],axis=1)
    bootstrap=[float(v) for v in np.quantile(replicates,[alpha/2,1-alpha/2],method='linear')]
    # P{fewer than k observations on either side of a population median} is
    # bounded by 2*BinomialCDF(k-1;n,.5), including conservative treatment of ties.
    indices=[k for k in range(1,n//2+1) if 2*binom.cdf(k-1,n,.5)<=alpha]
    k=max(indices);ordered=np.sort(values)
    return {'paired_bootstrap_median_interval':bootstrap,'bootstrap_replicates':len(replicates),
        'minimum_nominal_tail_draws':len(replicates)*alpha/2,
        'order_statistic_median_interval':[float(ordered[k-1]),float(ordered[n-k])],
        'order_index_k':k,'order_statistic_error_bound':float(2*binom.cdf(k-1,n,.5)),
        'allocated_error':alpha,'positive_lower_bounds':bool(bootstrap[0]>0 and ordered[k-1]>0),
        'scope':'Fixed independent seed pairs under the declared synthetic generator, not arbitrary production regions or a product confirmation interval.'}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--out',required=True);args=parser.parse_args()
    directory=Path(args.out);directory.mkdir(parents=True,exist_ok=True)
    profile={'protocol':PROTOCOL,'source_sha256':pipeline.identity(),'harness_sha256':pipeline.sha(__file__),
        'base_harness_sha256':pipeline.sha(pipeline.__file__),'runtime':pipeline.runtime_versions()}
    path=directory/'profile.json'
    if path.exists() and json.loads(path.read_text())!=profile:raise RuntimeError('Prior comparison has another profile; preserve it.')
    if not path.exists():path.write_text(json.dumps(profile,indent=2,sort_keys=True)+'\n')
    families=[];manifest={};all_gains=[];stopped=False
    for family_index,family in enumerate(FAMILIES):
        pairs=[];gains=[]
        for seed in range(PROTOCOL['seeds'][0],PROTOCOL['seeds'][1]+1):
            methods={}
            order=PROTOCOL['methods'] if seed%2==0 else list(reversed(PROTOCOL['methods']))
            for method in order:
                path=directory/f'{family}-{method}-{seed}.json'
                if not path.exists():
                    pending=path.with_suffix('.pending')
                    command=[sys.executable,'-B',str(Path(pipeline.__file__).resolve()),'--worker','--panel','recovery_qualification',
                        '--archetype',family,'--strategies',method,'--seed',str(seed),'--out',str(pending)]
                    subprocess.run(command,cwd=pipeline.ROOT,check=True);pending.rename(path)
                row=json.loads(path.read_text())
                if row['status']!='completed' or row['seed']!=seed or row['archetype']!=family or row['strategies']!=[method] or row['n']!=40000:raise RuntimeError('Failed/mismatched comparison trial retained; diagnose before continuing.')
                if row['profile']['source_sha256']!=profile['source_sha256'] or row['profile']['harness_sha256']!=profile['base_harness_sha256'] or row['profile']['package_versions']!=profile['runtime']:raise RuntimeError('Comparison source/runtime changed.')
                methods[method]=row;manifest[path.name]=pipeline.sha(path)
            if methods['geometric']['input_sha256']!=methods['landmark']['input_sha256'] or methods['geometric']['profile']['protocol_sha256']!=methods['landmark']['profile']['protocol_sha256']:raise RuntimeError('Methods did not receive identical source evidence/protocol.')
            if methods['geometric']['admitted_limits']!=methods['landmark']['admitted_limits'] or methods['geometric']['admitted_config']!=methods['landmark']['admitted_config']:raise RuntimeError('Matched methods require identical admitted operating budgets.')
            scores={m:r['recovery']['H']['primary_selected_union'] for m,r in methods.items()}
            gain=scores['landmark']['IoU']-scores['geometric']['IoU'];gains.append(gain)
            pair={'seed':seed,'H_recovery':scores,'paired_IoU_gain':gain,
                'execution':{m:r['execution'] for m,r in methods.items()}}
            pairs.append(pair);print(json.dumps({'family':family,'seed':seed,'paired_IoU_gain':gain,'pairs_completed':len(pairs)}),flush=True)
            if maximum_possible_median(gains)<.10:stopped=True;break
        complete=len(pairs)==40;uncertainty=paired_intervals(gains,PROTOCOL['bootstrap_seed']+family_index) if complete else None
        families.append({'family':family,'pairs':pairs,'complete':complete,'median_paired_IoU_gain':float(np.median(gains)),
            'maximum_possible_40_pair_median':maximum_possible_median(gains),'logical_futility':stopped,
            'uncertainty':uncertainty,'recovery_uncertainty_criteria_met':bool(complete and np.median(gains)>=.10 and uncertainty['positive_lower_bounds'])})
        all_gains.extend(gains)
        if stopped:break
    final={'profile':profile,'families':families,'trial_manifest':manifest,
        'status':'promotion_rejected_logical_futility' if stopped else 'complete_recovery_comparison',
        'all_required_pairs_complete':not stopped and len(families)==2 and all(f['complete'] for f in families),
        'overall_median_paired_gain':float(np.median(all_gains)),
        'resource_qualification':'not_established_under_concurrent_load','promoted':False,
        'generated_at':datetime.now(timezone.utc).isoformat(),
        'limitations':'A negative stopping result rejects promotion on the unchanged finite-panel criterion. It does not qualify unseen families, declare fallback universally sufficient or complete the milestone.'}
    path=directory/'summary.json'
    if path.exists():
        previous=json.loads(path.read_text());previous.pop('generated_at',None);comparison=dict(final);comparison.pop('generated_at')
        if previous!=comparison:raise RuntimeError('Completed comparison differs; preserve prior evidence.')
    else:path.write_text(json.dumps(final,indent=2,sort_keys=True,allow_nan=False)+'\n')


if __name__=='__main__':main()
