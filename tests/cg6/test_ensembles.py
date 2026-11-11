from dataclasses import replace
import numpy as np
import pytest
from confidenceguard import (execute_predictor,RobustnessSpec,ScenarioSpec,TransformationSpec,run_robustness,
    AuxiliaryCandidate,AuxiliaryStudySpec,fit_auxiliary,apply_auxiliary,ExecutionSpec,EvaluationError)
from .helpers import execution,CFG


def test_supplied_ensemble_common_support_and_variability(tmp_path):
    s=execution(tmp_path);other=replace(s.predictors[0],id='other',architecture={'values':{'output':[.75,.25]}})
    s=replace(s,predictors=(*s.predictors,other),ensembles=({'id':'mean','members':['model','other'],'decision':{'rule':'probability_argmax'}},))
    result=execute_predictor(s,CFG)
    ensemble=[r for r in result.private['output_rows'] if r['predictor']=='mean']
    assert ensemble and all(r['channels']['probabilities']==[.5,.5] for r in ensemble)
    assert all(r['ensemble']['probability_argmax_disagreement']==.5 and r.get('decision') is None for r in ensemble)
    assert set(result.private['predictors'])=={'model','other'}
    with pytest.raises(EvaluationError):ExecutionSpec((result.private['view_predictors']['mean'],),s.sources,s.input_source,s.key_columns,s.namespace)
    scenario=ScenarioSpec('invalid',(TransformationSpec('missing','missing',('x',),parameters={'rate':1.}),))
    stressed=run_robustness(RobustnessSpec(s,(scenario,)),CFG)
    assert all(r['execution']=='ensemble_member_unavailable' for r in stressed.private['output_rows'] if r['predictor']=='mean' and r['scenario']!='original')


def test_bounded_independent_auxiliary_initializations(tmp_path):
    s=execution(tmp_path,regression=True,n=120)
    candidate=AuxiliaryCandidate('ensemble','mlp_ensemble',parameters={'epochs':2,'hidden':[4,4],'batch_rows':16,'patience':2})
    assert candidate.ensemble_members==5
    result=fit_auxiliary(AuxiliaryStudySpec(s,'scale','model',candidates=(candidate,)),CFG)
    artifact=result.private['auxiliary_artifacts'][0]
    assert len(artifact['predictors'])==5
    assert len({p['files'][0]['sha256'] for p in artifact['predictors']})==5
    applied=apply_auxiliary(s,artifact,CFG,role='E')
    assert all(o['ensemble']['members']==5 and o['ensemble']['variance']>=0 for o in applied.private['output_rows'])
