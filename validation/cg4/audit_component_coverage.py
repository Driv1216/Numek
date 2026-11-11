"""Exploratory component-mean audit of retained simulations, not new qualification."""
import argparse
import hashlib
import inspect
import json
import math
from pathlib import Path

from scipy.stats import binomtest
from qualify_approximate import sample


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--input',required=True);parser.add_argument('--out',required=True);args=parser.parse_args()
    folder=Path(args.input);profile=json.loads((folder/'profile.json').read_text())
    expected={'normal_mean':0.,'skew_exponential':1.,'heavy_lognormal':math.exp(1.5**2/2),
        'imbalanced_arms':0.,'unequal_complete_clusters':0.}
    if set(profile['scenarios'])!=set(expected) or profile['seed_range']!=[60000,60999] or profile['components']!=2 or profile['confidence']!=.95:raise RuntimeError('Original component protocol differs.')
    if profile['functions_sha256']['sample']!=hashlib.sha256(inspect.getsource(sample).encode()).hexdigest():raise RuntimeError('Original generator definition differs; do not guess population means.')
    rows=[];manifest={}
    for scenario,truth in expected.items():
        counters=[{'available':0,'noncoverage':0,'lower_above_truth':0,'upper_below_truth':0} for _ in range(2)]
        for seed in range(60000,61000):
            path=folder/f'{scenario}-{seed}.json';raw=path.read_bytes();record=json.loads(raw)
            if record['scenario']!=scenario or record['seed']!=seed or len(record['result']['components'])!=2:raise RuntimeError('Retained trial identity differs.')
            manifest[path.name]=hashlib.sha256(raw).hexdigest()
            for target,component in zip(counters,record['result']['components']):
                if component['status']!='available':continue
                target['available']+=1
                target['noncoverage']+=int(not component['lower']<=truth<=component['upper'])
                target['lower_above_truth']+=int(component['lower']>truth)
                target['upper_below_truth']+=int(component['upper']<truth)
        for index,counter in enumerate(counters):
            n=counter['available'];failed=counter['noncoverage']
            ci=binomtest(failed,n).proportion_ci(method='exact') if n else None
            rows.append({'scenario':scenario,'component':'member' if index==0 else 'comparator','trials':1000,
                'population_mean':truth,'nominal_two_sided_error':.025,**counter,'unavailable':1000-n,
                'conditional_noncoverage_MC95':[float(ci.low),float(ci.high)] if ci else None,
                'coverage_bounds_with_refusals':[(n-failed)/1000,(1000-failed)/1000]})
    result={'scope':'Post-hoc diagnostic of individual component means. Original qualification tested contrasts, not these claims; no new locked qualification or ceiling-objective support is inferred.',
        'simulation_rerun':False,'changed_original_acceptance_criteria':False,
        'input_profile_sha256':hashlib.sha256((folder/'profile.json').read_bytes()).hexdigest(),'trial_manifest':manifest,'rows':rows}
    with Path(args.out).open('x') as stream:json.dump(result,stream,sort_keys=True,indent=2,allow_nan=False);stream.write('\n')
    print(json.dumps({'scope':result['scope'],'rows':rows},indent=2))


if __name__=='__main__':main()
