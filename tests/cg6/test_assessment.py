from dataclasses import replace
from confidenceguard import (RobustnessSpec,ScenarioSpec,TransformationSpec,RobustnessClaim,run_robustness,
    freeze_robustness,assess_robustness,RobustnessAssessmentSpec)
from confidenceguard.contracts import digest
from confidenceguard.sources import key
from .helpers import execution,CFG


def test_replicate_average_uses_bounded_root_inference(tmp_path):
    s=execution(tmp_path,n=120)
    scenario=ScenarioSpec('identity',(TransformationSpec('same','identity'),),replicates=3,outcome_relation='label_preserving',outcome_reason='Identity oracle')
    development=run_robustness(RobustnessSpec(s,(scenario,),role='S'),CFG)
    protocol=freeze_robustness(development,[RobustnessClaim('flips','model','identity','flip_rate','le',.4)],
        upstream_independence='declared_independent',external_exposure='declared_unexposed')
    result=assess_robustness(RobustnessAssessmentSpec(protocol,s),CFG)
    claim=result.data['cg6']['claims'][0]
    assert claim['state']=='supported',claim
    assert claim['support']==30 and claim['method']=='paired_bounded_mean_hoeffding'


def test_known_primary_overlap_cannot_be_overridden(tmp_path):
    s=execution(tmp_path,n=120)
    events=[digest([s.namespace,key({'id':str(i)},('id',),None)]) for i in range(120) if i%4==3]
    p=replace(s.predictors[0],provenance={'training_membership':{'namespace':s.namespace,'events':events,'units':[]}})
    s=replace(s,predictors=(p,))
    scenario=ScenarioSpec('identity',(TransformationSpec('same','identity'),),outcome_relation='label_preserving',outcome_reason='Identity oracle')
    development=run_robustness(RobustnessSpec(s,(scenario,),role='S'),CFG)
    protocol=freeze_robustness(development,[RobustnessClaim('flips','model','identity','flip_rate','le',.4)],
        upstream_independence='declared_independent',external_exposure='declared_unexposed')
    result=assess_robustness(RobustnessAssessmentSpec(protocol,s),CFG)
    assert result.data['cg6']['claims'][0]['reason']=='known_primary_training_assessment_overlap'
