from dataclasses import replace
import pytest
from confidenceguard import (AuxiliaryStudySpec,AuxiliaryCandidate,fit_auxiliary,apply_auxiliary,assess_auxiliary,EvaluationResult)
from .helpers import execution,CFG


@pytest.mark.parametrize('kind',['scale','quantiles'])
def test_fit_apply_separation_and_artifact(tmp_path,kind):
    spec=execution(tmp_path,regression=True,n=120)
    study=AuxiliaryStudySpec(spec,kind,'model',candidates=(AuxiliaryCandidate('constant','constant'),AuxiliaryCandidate('hist','histogram',parameters={'iterations':8,'min_samples_leaf':3})),quantile_rearrange=True)
    fitted=fit_auxiliary(study,CFG)
    artifact=fitted.private['auxiliary_artifacts'][0]
    assert not fitted.data['cg6']['separation']['E_accessed']
    assert {r['role'] for r in fitted.private['output_rows']}=={'F','S'}
    applied=apply_auxiliary(spec,artifact,CFG,role='E')
    assert len(applied.private['output_rows'])==30
    assessed=assess_auxiliary(spec,artifact,CFG)
    assert assessed.data['measurements']
    EvaluationResult.from_dict(assessed.to_private_dict(),private=assessed.private)


def test_c_and_e_feature_label_mutation_cannot_change_fit(tmp_path):
    import csv
    s=execution(tmp_path,regression=True,n=120)
    study=AuxiliaryStudySpec(s,'scale','model',candidates=(AuxiliaryCandidate('mlp','mlp',parameters={'epochs':3,'patience':2,'hidden':[8,8]}),))
    first=fit_auxiliary(study,CFG).private['auxiliary_artifacts'][0]
    path=s.sources[0].path
    with open(path) as stream:records=list(csv.DictReader(stream))
    for row in records:
        if row['role'] in {'C','E'}:row.update(x='987654',y='-123456')
    with open(path,'w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(records[0]));writer.writeheader();writer.writerows(records)
    second=fit_auxiliary(study,CFG).private['auxiliary_artifacts'][0]
    assert first['selection']==second['selection']
    assert first['membership']==second['membership']
    assert [p['files'][0]['sha256'] for p in first['predictors']]==[p['files'][0]['sha256'] for p in second['predictors']]


def test_mlp_scale_selection_matches_deployed_floor(tmp_path):
    import hashlib
    import numpy as np
    spec=execution(tmp_path,regression=True,n=120)
    study=AuxiliaryStudySpec(spec,'scale','model',scale_floor=100.,candidates=(
        AuxiliaryCandidate('mlp','mlp',parameters={'epochs':3,'patience':2,'hidden':[8,8]}),))
    fitted=fit_auxiliary(study,CFG)
    artifact=fitted.private['auxiliary_artifacts'][0]
    applied=apply_auxiliary(spec,artifact,{**CFG,'max_details':120},role='S')
    rows=applied.private['output_rows']
    # S nomination must evaluate the deployed, explicitly floored predictor.
    selected=[r for r in rows if int(hashlib.sha256(str(r['entity_key'] or r['event_key']).encode()).hexdigest(),16)/2**256>=study.s_tuning_fraction]
    assert selected
    assert len(rows)==30
    assert all(r['channels']['scale']==100. for r in rows)
    expected=np.mean([(100.-abs(float(r['truth']['value'])-.5))**2 for r in selected])
    assert artifact['selection']['S_objective']==pytest.approx(expected)
