"""Deterministic diagnostic truth cases; no mutations to historical inputs."""
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT=Path(__file__).parent


def prepare():
    rng=np.random.default_rng(20261009);n=100;y=np.arange(n,dtype=float)
    cases={
        'copy':(y,{'input':y}, {}, ['regression_relationships_unknown']),
        'affine':(y,{'input':2*y+7}, {}, ['regression_relationships_unknown']),
        'sum':(y,{'a':np.sqrt(y),'b':y-np.sqrt(y)}, {}, ['regression_relationships_unknown']),
        'sparse_copy':(y,{'input':np.r_[y[:20],np.full(80,np.nan)]}, {}, []),
        'missing_nonfinite':(np.r_[y[:97],np.nan,np.inf,-np.inf], {'input':y**2}, {}, ['regression_missing_targets','regression_nonfinite_targets']),
        'constant':(np.ones(n),{'input':y}, {}, ['regression_constant_target']),
        'constraint_union':(np.r_[-1.,-.5,y[2:]],{'input':y**2}, {'kind':'count','maximum':90}, ['regression_declared_constraints']),
        'rounded_legitimate':(np.round(rng.normal(10,2,n),2), {'input':rng.normal(size=n)}, {}, []),
        'heavy_tail_legitimate':(rng.standard_t(2,n),{'input':rng.normal(size=n)}, {}, []),
        'skew_legitimate':(rng.lognormal(0,2,n),{'input':rng.normal(size=n)}, {}, []),
        'bounded_legitimate':(np.clip(rng.normal(.5,.3,n),0,1),{'input':rng.normal(size=n)}, {}, []),
        'zero_inflated_count':(np.r_[np.zeros(80),np.arange(20)],{'input':rng.normal(size=n)}, {'kind':'count'}, []),
        'repeated_measurements':(rng.normal(size=n),{'input':np.repeat(np.arange(20),5)}, {}, ['regression_repeated_input_variation']),
    }
    output=ROOT/'data/mutations';output.mkdir(parents=True,exist_ok=True)
    manifest={}
    for name,(target,features,expectations,expected) in cases.items():
        frame=pd.DataFrame(features);frame['outcome']=target;p=output/(name+'.csv');frame.to_csv(p,index=False)
        manifest[name]={'file':str(p.relative_to(ROOT)),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'target':'outcome','expectations':expectations,
            'expected_findings':expected,'seed':20261009,'recipe':name,'mutation_version':'m2_regression_mutations_v1',
            'mutation_script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), 'rows':len(frame),'columns':len(frame.columns)}
    (ROOT/'mutations.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return manifest


if __name__=='__main__':print(json.dumps(prepare(),indent=2))
