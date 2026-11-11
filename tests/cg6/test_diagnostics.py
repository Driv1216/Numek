import pytest
from confidenceguard.auxiliary.diagnostics import risk_diagnostics


def test_failure_ranking_whole_ties_and_single_class():
    r=risk_diagnostics([0,1,0,1],[.1,.1,.4,.9])
    assert r['auroc']==pytest.approx(.625)
    assert r['average_precision']==pytest.approx(.75)
    assert [(x['accepted'],x['risk']) for x in r['risk_coverage']]==[(2,.5),(3,1/3),(4,.5)]
    assert risk_diagnostics([0,0],[.1,.9])['auroc'] is None


def test_named_raw_gradient_linear_oracle(tmp_path):
    from confidenceguard import RobustnessSpec,ScenarioSpec,TransformationSpec,run_robustness
    from .test_devices import torch_spec
    from .helpers import CFG
    s=torch_spec(tmp_path)
    r=run_robustness(RobustnessSpec(s,(ScenarioSpec('same',(TransformationSpec('same','identity'),)),),
        sensitivity={'gradients':[{'id':'slope','predictor':'model','channel':'point'}],'max_roots':4}),CFG)
    values=[o['gradient_diagnostics']['slope']['values'] for o in r.private['output_rows'] if o.get('gradient_diagnostics')]
    assert values==[[2.]]*4
