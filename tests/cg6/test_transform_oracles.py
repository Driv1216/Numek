from types import SimpleNamespace
from dataclasses import replace
import numpy as np
import pytest
from confidenceguard import TransformationSpec,ScenarioSpec,RobustnessSpec,AttackSpec,run_robustness,EvaluationError
from confidenceguard.robustness.transformations import transform,variant,feasible,transformed_truth
from .helpers import execution,CFG


def test_block_conditional_missingness_and_exact_repair():
    rng=np.random.default_rng(1)
    t=TransformationSpec('block','missing',('a','b'),parameters={'rate':1.,'mode':'block','condition':{'field':'group','op':'eq','value':'chosen'}})
    for group in ('chosen','other'):
        record={'a':1.,'b':2.,'group':group};changed,v=transform(record,t,rng,None)
        assert (changed['a']=='' and changed['b']=='')==(group=='chosen')
        assert record['a']==1. and v['structural_valid']
    record={'a':'1.4','b':3};valid,reason,repairs=feasible({'a':1,'b':3},record,{'a':{'lower':0,'upper':2,'integer':True,'repair':True}},({'coefficients':{'a':1,'b':1},'operator':'le','bound':4},))
    assert valid and repairs==['a'] and record['a']=='1'
    assert not feasible({'a':1},{'a':2},{'a':{'mutable':False}},())[0]


def test_registered_outcome_rule_and_unavailable_condition(tmp_path):
    s=execution(tmp_path,regression=True)
    scenario=ScenarioSpec('units',(TransformationSpec('scale','set',('x',),parameters={'values':{'x':5.}}),),
        outcome_relation='registered_transform',outcome_reason='Synthetic affine-unit oracle',outcome_rule={'operation':'affine_regression_v1','factor':2.,'offset':3.})
    RobustnessSpec(s,(scenario,))
    assert transformed_truth({'value':4.,'valid':True,'reason':None},scenario.outcome_relation,scenario.outcome_rule,{},'id',s.task)['value']==11.
    event={'event_key':'root','record':{'x':1.,'z':2.},'truth':{'value':4.,'valid':True,'reason':None},'unavailable_fields':['z']}
    t=TransformationSpec('conditional','missing',('x',),parameters={'rate':1.,'condition':{'field':'z','op':'gt','value':0}})
    out=variant(event,ScenarioSpec('conditional',(t,)),0,0,SimpleNamespace(spec=s))
    assert out['record']['x']==1. and not out['variant']['applicable']
    assert not out['truth']['valid']


def test_complete_finite_attack_matches_linear_domain_oracle(tmp_path):
    from .test_devices import torch_spec
    s=torch_spec(tmp_path);domain=[0.,.25,.5,1.]
    attack=AttackSpec('enumerate',('x',),norm='discrete',domains={'x':domain},queries_per_root=5)
    r=run_robustness(RobustnessSpec(s,(ScenarioSpec('finite',attack=attack),),role='E'),CFG)
    for row in r.private['output_rows']:
        if not row.get('variant'):continue
        witness=row['variant']['attack'];x=float(next(o for o in r.private['output_rows'] if o['scenario']=='original' and o['event_key']==row['event_key'])['input_record']['x'])
        assert witness['search_coverage']=='complete_declared_finite_domain' and witness['queries']==5
        assert witness['best_objective']==pytest.approx(max(abs(2*v-2*x) for v in domain),abs=1e-6)
