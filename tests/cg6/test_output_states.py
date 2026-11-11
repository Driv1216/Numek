from dataclasses import replace
import numpy as np
from confidenceguard import OutputBinding,DecisionSpec,execute_predictor,qualify_predictor
from confidenceguard.execution.adapters import normalize_outputs
from .helpers import execution,CFG


def test_declared_abstention_preserves_latent_probabilities(tmp_path):
    s=execution(tmp_path)
    p=replace(s.predictors[0],outputs=(OutputBinding('probabilities',classes=('no','yes')),OutputBinding('issuance','state',mapping={'0':'abstained'})),architecture={'values':{'output':[.25,.75],'state':0}})
    r=execute_predictor(replace(s,predictors=(p,)),CFG)
    assert all(o['issuance']=='abstained' and o['channels']['probabilities']==[.25,.75] for o in r.private['output_rows'])
    assert not any(m['metric']=='accuracy' and m['value_state']=='finite' for m in r.data['measurements'])
    q=qualify_predictor(replace(s,predictors=(p,)),CFG)
    assert q.data['cg6']['parity']['batch_parity']=='passed'


def test_hard_label_mapping_and_exact_tie_abstention(tmp_path):
    s=execution(tmp_path)
    p=replace(s.predictors[0],outputs=(OutputBinding('prediction','label',mapping={'0':'no','1':'yes'}),),decision=DecisionSpec())
    outputs=normalize_outputs({'label':np.array([0,1])},p,2,1e-6)
    assert [o['channels']['prediction'] for o in outputs]==['no','yes']
    p=replace(s.predictors[0],architecture={'values':{'output':[.5,.5]}})
    r=execute_predictor(replace(s,predictors=(p,)),CFG)
    assert all(o['issuance']=='abstained' for o in r.private['output_rows'])
