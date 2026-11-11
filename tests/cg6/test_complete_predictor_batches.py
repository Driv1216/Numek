from dataclasses import replace
from pathlib import Path
import pytest
from confidenceguard import (register_host_predictor,execute_predictor,qualify_predictor,RobustnessSpec,ScenarioSpec,TransformationSpec,run_robustness,EvaluationError)
from tests.cg6.host_fixtures import centered_batch_factory
from .helpers import execution,CFG


def coupled(tmp_path):
    register_host_predictor('centered_batches',centered_batch_factory,code_files=(Path(__file__).with_name('host_fixtures.py'),),batch_independent=False)
    s=execution(tmp_path,regression=True,n=20)
    p=replace(s.predictors[0],adapter='custom',registration='centered_batches',architecture={})
    return replace(s,predictors=(p,),batch_columns=('batch',),roles=None)


def test_coupled_parity_replays_complete_declared_batches(tmp_path):
    s=coupled(tmp_path);original=execute_predictor(s,CFG)
    q=qualify_predictor(s,CFG,reference=original.private['output_rows'])
    assert q.data['cg6']['parity']['batch_parity']=='passed'
    assert q.data['cg6']['parity']['reference_parity']=='passed'
    assert q.data['cg6']['parity']['runtime_evidence']['model']['batch_test']=='complete_declared_batch_replay'
    assert q.data['cg6']['devices']['model']['batches']==4


def test_coupled_scenario_cannot_silently_execute_partial_batch(tmp_path):
    s=coupled(tmp_path)
    scenario=ScenarioSpec('partial',(TransformationSpec('same','identity'),),filter={'field':'x','op':'lt','value':.1})
    with pytest.raises(EvaluationError) as e:run_robustness(RobustnessSpec(s,(scenario,)),CFG)
    assert e.value.code=='execution_batch_incomplete'
