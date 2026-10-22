"""Declared-design simulations with Monte Carlo uncertainty, including misuse controls."""
import argparse
import json
import math
from pathlib import Path
import numpy as np
from confidenceguard import LongitudinalInferenceSpec
from confidenceguard.history_inference import historical_bootstrap


def wilson(success,total):
    z=1.96;p=success/total;den=1+z*z/total
    mid=(p+z*z/(2*total))/den;half=z*math.sqrt(p*(1-p)/total+z*z/(4*total**2))/den
    return [mid-half,mid+half]


def run(trials=100):
    result={};rng=np.random.default_rng(173)
    for design in ('independent_periods','entity_clusters','moving_blocks','invalid_iid_serial'):
        successes=published=refused=0;widths=[];reasons={}
        for trial in range(trials):
            n=300;truth=.2
            if design=='entity_clusters':
                sizes=rng.integers(1,5,120);u=rng.normal(size=120);entities=np.repeat(np.arange(120),sizes)
                left=u[entities]+rng.normal(size=len(entities));right=truth+u[entities]+rng.normal(size=len(entities))
            else:
                entities=np.arange(n);left=rng.normal(size=n);right=truth+rng.normal(size=n)
                if design in ('moving_blocks','invalid_iid_serial'):
                    # Stationary AR(1), independent regimes; burn-in discarded explicitly.
                    def ar():
                        x=np.zeros(n+300)
                        for i in range(1,len(x)):x[i]=.6*x[i-1]+rng.normal()
                        return x[300:]
                    left=ar();right=truth+ar()
            def rows(values,arm):return [(f'{arm}-{i}',str(entities[i]) if design=='entity_clusters' else None,f'{arm}-target-{i}',i+(0 if arm=='a' else 1000),float(value),1.,None) for i,value in enumerate(values)]
            kwargs={'mode':'independent_periods' if design=='invalid_iid_serial' else design,'metrics':['mae'],'replicates':1000,'confidence':.9,'seed':trial,
                    'independent_units':True,'independent_periods':True,'finite_moments':True}
            if design=='moving_blocks':kwargs.update(stationary=True,complete_bins=True,bin_ns='1',block_length=5,known_serial_dependence=True)
            spec=LongitudinalInferenceSpec(**kwargs)
            interval=historical_bootstrap(rows(left,'a'),rows(right,'b'),spec,metric='mae',family_size=1,check=lambda _:None,left_window=(0,n),right_window=(1000,1000+n),available_bytes=256*1024**2)
            if interval['status']=='available':
                published+=1;successes+=interval['lower']<=truth<=interval['upper'];widths.append(interval['upper']-interval['lower'])
            else:refused+=1;reasons[interval['reason']]=reasons.get(interval['reason'],0)+1
        result[design]={'trials':trials,'published':published,'refused':refused,'refusal_rate':refused/trials,'refusal_reasons':reasons,
            'empirical_coverage':successes/published if published else None,'coverage_mc_95_wilson':wilson(successes,published) if published else None,
            'mean_interval_width':float(np.mean(widths)) if widths else None,'nominal_confidence':.9,
            'qualification':'Deliberately misspecified independence control' if design=='invalid_iid_serial' else 'Finite simulated settings; not a general coverage guarantee'}
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--out',required=True);parser.add_argument('--trials',type=int,default=100);args=parser.parse_args()
    result=run(args.trials);Path(args.out).write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
