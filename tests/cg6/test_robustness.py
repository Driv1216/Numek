from dataclasses import replace
import pytest
from confidenceguard import (RobustnessSpec,ScenarioSpec,TransformationSpec,run_robustness,
    freeze_robustness,RobustnessClaim,EvaluationResult)
from .helpers import execution,CFG


def test_unknown_outcomes_do_not_inherit_labels(tmp_path):
    spec=execution(tmp_path)
    study=RobustnessSpec(spec,(ScenarioSpec('missing',(TransformationSpec('x_missing','missing',('x',),{'rate':1.}),),replicates=2),))
    result=run_robustness(study,CFG)
    variants=[r for r in result.private['output_rows'] if r['scenario']!='original']
    assert len(variants)==120
    assert all(not r['truth']['valid'] for r in variants)
    assert all(m['denominator']==0 for m in result.data['measurements'] if m['metric']=='accuracy' and m['scope']!='overall')
    assert all(m['denominator']<=60 for m in result.data['measurements'] if m['family']=='robustness')
    EvaluationResult.from_dict(result.to_private_dict(),private=result.private)


def test_label_preservation_requires_declaration_and_root_averaging(tmp_path):
    spec=execution(tmp_path,regression=True)
    study=RobustnessSpec(spec,(ScenarioSpec('measurement',(TransformationSpec('identity','identity'),),replicates=3,
        outcome_relation='label_preserving',outcome_reason='Measurement-only controlled fixture'),))
    result=run_robustness(study,CFG)
    delta=next(m for m in result.data['measurements'] if m['metric']=='loss_delta')
    assert delta['value']==0 and delta['denominator']==60
    frozen=freeze_robustness(result,[RobustnessClaim('same','model','measurement','loss_delta','le',.1,bounds=(-1,1))])
    assert frozen.content_digest
