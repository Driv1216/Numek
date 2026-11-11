"""Independent SciPy BCa interval composition on identical bootstrap draws."""
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import numpy as np
from scipy.stats import bootstrap
from qualify_approximate import sample
from confidenceguard.confirmation import approximate_interval


def main():
    rows=[]
    for scenario in ('normal_mean','skew_exponential','heavy_lognormal','unequal_complete_clusters'):
        for seed in (50000,50013,50101):
            values,objective,protocol,units,_=sample(seed,scenario)
            labels=np.unique(units);matrix=np.stack([values[units==label].sum(axis=0) for label in labels])
            n=len(matrix);rng=np.random.Generator(np.random.PCG64(protocol.seed));draws=np.empty(protocol.replicates)
            for i in range(len(draws)):
                total=rng.multinomial(n,np.full(n,1/n))@matrix
                draws[i]=total[2]/total[3]-total[0]/total[1]
            def statistic(data,axis=-1):
                totals=data.sum(axis=axis)
                return totals[2]/totals[3]-totals[0]/totals[1]
            previous=bootstrap((matrix.T,),statistic,axis=-1,paired=True,n_resamples=2,method='percentile',rng=np.random.default_rng(0))
            previous.bootstrap_distribution=draws
            reference=bootstrap((matrix.T,),statistic,axis=-1,paired=True,n_resamples=0,batch=64,method='BCa',bootstrap_result=previous)
            measured=approximate_interval(values,objective,protocol,family_size=1,units=units,work_budget=2_000_000_000,check=lambda *args:None)
            difference=max(abs(measured['lower']-reference.confidence_interval.low),abs(measured['upper']-reference.confidence_interval.high)) if measured['status']=='available' else None
            tolerance=1e-10*max(1.,abs(reference.confidence_interval.low),abs(reference.confidence_interval.high))
            rows.append({'scenario':scenario,'seed':seed,'NUMEK_status':measured['status'],'NUMEK_interval':[measured.get('lower'),measured.get('upper')],
                'SciPy_interval':list(reference.confidence_interval),'max_abs_difference':difference,'tolerance':tolerance,'parity':bool(difference is not None and difference<=tolerance),
                'draw_digest':hashlib.sha256(draws.tobytes()).hexdigest()})
    destination=Path(__file__).with_name('results')/'BCa-SciPy-reference-v1.json'
    record={'schema_version':'numek.cg4_BCa_reference/1.0','rows':rows,'all_available_cases_match':all(r['parity'] for r in rows),
        'reference':'https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.bootstrap.html',
        'scope':'Independent SciPy bias/acceleration/interval calculation using identical recorded draws. Parity does not establish frequentist coverage.'}
    with destination.open('x') as stream:json.dump(record,stream,sort_keys=True,indent=2);stream.write('\n')
    print(json.dumps(record))


if __name__=='__main__':main()
