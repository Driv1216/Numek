"""Supplementary fixed block-length experiments; retain the earlier short-block failure."""
import argparse,json,math
from pathlib import Path
import numpy as np
from confidenceguard import LongitudinalInferenceSpec
from confidenceguard.history_inference import historical_bootstrap
from .statistics import wilson

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',required=True);p.add_argument('--trials',type=int,default=100);a=p.parse_args()
    rng=np.random.default_rng(937);counts={length:{'covered':0,'published':0,'refused':0,'widths':[]} for length in (10,20,40)}
    n=1200
    for trial in range(a.trials):
        def ar():
            values=np.zeros(n+600)
            for i in range(1,len(values)):values[i]=.6*values[i-1]+rng.normal()
            return values[600:]
        def records(values,arm):return [(f'{arm}-{i}',None,f'{arm}-t-{i}',i+(0 if arm=='a' else 10000),float(v),1.,None) for i,v in enumerate(values)]
        left=records(ar(),'a');right=records(.2+ar(),'b')
        spec=LongitudinalInferenceSpec(mode='moving_blocks',metrics=('bias',),confidence=.9,replicates=1000,seed=trial,
            stationary=True,complete_bins=True,independent_periods=True,finite_moments=True,known_serial_dependence=True,
            bin_ns='1',block_length=20,sensitivity_lengths=(10,40))
        result=historical_bootstrap(left,right,spec,metric='bias',family_size=1,check=lambda _:None,left_window=(0,n),right_window=(10000,10000+n),available_bytes=256*1024**2)
        for item in [result,*result['sensitivity']]:
            record=counts[item['block_length']]
            if item['status']=='available':
                record['published']+=1;record['covered']+=item['lower']<=.2<=item['upper'];record['widths'].append(item['upper']-item['lower'])
            else:record['refused']+=1
    output={'trials':a.trials,'bins_per_period':n,'phi':.6,'nominal_confidence':.9,'primary_length':20,'declared_sensitivities':[10,40],
        'qualification':'Supplementary finite settings. Does not replace earlier n=300/L=5 undercoverage or select an analysis block length.'}
    output['lengths']={length:{'published':v['published'],'refused':v['refused'],'coverage':v['covered']/v['published'] if v['published'] else None,
        'coverage_mc_95_wilson':wilson(v['covered'],v['published']) if v['published'] else None,'mean_width':float(np.mean(v['widths'])) if v['widths'] else None} for length,v in counts.items()}
    Path(a.out).write_text(json.dumps(output,indent=2)+'\n');print(json.dumps(output,indent=2))
