from dataclasses import replace
import pytest
from confidenceguard import FeatureField,SourceSpec,OutcomeSnapshotSpec,AuxiliaryStudySpec,AuxiliaryCandidate,fit_auxiliary,execute_predictor,EvaluationError
from .helpers import execution,CFG


def test_known_source_alias_cannot_hide_outcome_input(tmp_path):
    s=execution(tmp_path,regression=True)
    p=replace(s.predictors[0],inputs=(FeatureField('target_alias','y','float',role='model_input'),))
    s=replace(s,predictors=(p,),outcomes=OutcomeSnapshotSpec('labels','y',('id',)),sources=(*s.sources,SourceSpec('labels',s.sources[0].path)))
    with pytest.raises(EvaluationError) as e:execute_predictor(s,CFG)
    assert e.value.code=='outcome_input'


def test_auxiliary_identifier_input_refused(tmp_path):
    s=execution(tmp_path,regression=True)
    study=AuxiliaryStudySpec(s,'scale','model',inputs=(FeatureField('identity','entity','float'),),candidates=(AuxiliaryCandidate('constant','constant'),))
    with pytest.raises(EvaluationError) as e:fit_auxiliary(study,CFG)
    assert e.value.code=='outcome_input'
