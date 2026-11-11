from dataclasses import replace
import json
import pytest

from confidenceguard import (AuxiliaryStudySpec,AuxiliaryCandidate,fit_auxiliary,apply_auxiliary,as_reliability_spec,
    MethodSpec,fit_methods,apply_methods,execute_predictor,ReliabilityWorkspace,WorkspaceConfig,EvaluationError,
    RobustnessSpec,ScenarioSpec,TransformationSpec,FeatureField,ClockSpec)
from confidenceguard.execution.storage import retained_predictor
from confidenceguard import schema
from .helpers import execution,CFG


@pytest.mark.parametrize('kind,method,input',[('scale','normalized','normalized'),('quantiles','cqr','quantiles')])
def test_fitted_auxiliary_into_unchanged_cg2(tmp_path,kind,method,input):
    s=execution(tmp_path,regression=True,n=120)
    fitted=fit_auxiliary(AuxiliaryStudySpec(s,kind,'model',candidates=(AuxiliaryCandidate('constant','constant'),)),CFG)
    applied=apply_auxiliary(s,fitted.private['auxiliary_artifacts'][0],CFG)
    linked=as_reliability_spec(applied,scope='auxiliary_application',directory=tmp_path/'bridge')
    assert linked.evaluation.runs[0].prediction=='cg6_prediction'
    assert linked.representations
    m=MethodSpec('uncertainty',method,'constant',input=input,lower_quantile='.1',upper_quantile='.9')
    fitted_methods=fit_methods(replace(linked,methods=(m,)),CFG)
    assert fitted_methods.private['fitted_methods']
    artifact=fitted_methods.private['fitted_methods'][0]
    assessed=apply_methods(replace(linked,fitted_methods=(artifact,),membership_sidecars=tuple(fitted_methods.private['membership_sidecars']),output_path=str(tmp_path/'uncertainty.csv')),CFG)
    assert assessed.execution['status']=='completed'
    from confidenceguard import run_robustness
    frozen=replace(s,auxiliaries=(fitted.private['auxiliary_artifacts'][0],),fitted_methods=(artifact,),membership_sidecars=tuple(fitted_methods.private['membership_sidecars']))
    scenario=ScenarioSpec('identity',(TransformationSpec('same','identity'),),outcome_relation='label_preserving',outcome_reason='Identity oracle')
    stressed=run_robustness(RobustnessSpec(frozen,(scenario,),role='E'),CFG)
    uncertainty=[m for m in stressed.data['measurements'] if m['run'].startswith('uncertainty') and 'coverage@' in m['metric']]
    assert uncertainty and all(m['denominator']==30 and m['value_state']=='finite' for m in uncertainty)


def test_binary_codec_catalog_v2_backup_reopen(tmp_path):
    from .test_devices import torch_spec
    s=torch_spec(tmp_path);ws=ReliabilityWorkspace.initialize(tmp_path/'workspace',config=WorkspaceConfig(saving=True))
    result=execute_predictor(s,CFG,workspace=ws)
    aid=result.data['analysis_id'];reopened=ws.open(aid)
    assert ws.catalog.catalog_version==2
    assert reopened.data==result.data
    assert retained_predictor(ws,aid,'model').predictor_digest==s.predictors[0].predictor_digest
    output=reopened.private['output_artifact']
    assert output['path'].endswith('.cgblob')
    from contextlib import closing
    with closing(ws.catalog._connect()) as db:
        assert db.execute("SELECT count(*) FROM objects WHERE encoding='opaque_artifact_bytes_v1'").fetchone()[0]>=2
    # Reopening and report rendering must not construct an adapter.
    import unittest.mock
    with unittest.mock.patch('confidenceguard.execution.adapters.Adapter',side_effect=AssertionError('unexpected model load')):
        ws.open(aid).generate_artifacts(tmp_path/'reopened.html',format='html',json_path=tmp_path/'reopened.json',audience='local')
    ws.backup(tmp_path/'backup')
    restored=ReliabilityWorkspace.restore(tmp_path/'backup',tmp_path/'restored')
    rebound=restored.open(aid)
    assert str(restored.path) in rebound.retained_path(rebound.private['output_artifact']['path'])
    ref=next(iter(rebound.private['locators']))
    assert rebound.resolve_evidence(ref,allowed_roots=(restored.path,),reveal_values=True)['verified']
    from confidenceguard import ExecutionRestatementSpec
    for f in s.predictors[0].files:__import__('pathlib').Path(f.path).unlink()
    # Frozen outputs and copied immutable bytes suffice after relocation. No
    # executable model or original model path is needed for outcome restatement.
    declaration=ExecutionRestatementSpec(s.sources,s.outcomes,'Restored evidence outcome refresh')
    revised=restored.restate_execution(aid,declaration,CFG,request_id='restatement-after-restore')
    assert restored.restate_execution(aid,declaration,CFG,request_id='restatement-after-restore').data['analysis_id']==revised.data['analysis_id']
    assert revised.data['cg6']['execution_repeated'] is False
    plan=restored.deletion_preview(assessment_ids=(aid,))
    restored.delete(plan)
    with pytest.raises(EvaluationError):restored.open(aid)
    with pytest.raises(EvaluationError):restored.open(revised.data['analysis_id'])


def test_schema_contains_strict_execution_surface():
    import subprocess
    document=schema.schemas()
    subprocess.run(['python3','-c','import jsonschema,json,sys;jsonschema.Draft202012Validator.check_schema(json.load(sys.stdin))'],input=json.dumps(document),text=True,check=True)
    for name in ('PredictorSpec','ExecutionSpec','AuxiliaryStudySpec','FrozenRobustnessProtocol','ExecutionJobRequest'):
        assert document['$defs'][name]['additionalProperties'] is False
    assert '/execution/drafts' in schema.openapi()['paths']


def test_retained_robustness_contributions_and_frozen_protocol(tmp_path):
    from confidenceguard import run_robustness,RobustnessClaim
    from confidenceguard.execution.artifact_bytes import verify_artifact
    s=execution(tmp_path,n=24);ws=ReliabilityWorkspace.initialize(tmp_path/'workspace',config=WorkspaceConfig(saving=True))
    scenario=ScenarioSpec('same',(TransformationSpec('identity','identity'),),outcome_relation='label_preserving',outcome_reason='Identity oracle')
    result=run_robustness(RobustnessSpec(s,(scenario,),role='S'),CFG,workspace=ws)
    frozen=ws.freeze_robustness(result,[{'id':'failures','predictor':'model','scenario':'same','metric':'output_failure_rate','operator':'le','threshold':.5,'minimum_support':2}])
    assert ws.open_robustness_protocol(frozen.content_digest).content_digest==frozen.content_digest
    reopened=ws.open(result.data['analysis_id'])
    info=reopened.private['contribution_artifact'];verify_artifact(info,(ws.path,))
    assert __import__('pathlib').Path(info['path']).stat().st_mode&0o077==0


def test_late_features_refuse_execution(tmp_path):
    import csv
    s=execution(tmp_path,regression=True,n=8);path=tmp_path/'inputs.csv'
    with path.open() as f:records=list(csv.DictReader(f))
    for r in records:r.update(cutoff='2026-01-01T00:00:00Z',available='2026-01-02T00:00:00Z')
    with path.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(records[0]));w.writeheader();w.writerows(records)
    f=replace(s.predictors[0].inputs[0],available_at=ClockSpec('available'))
    s=replace(s,predictors=(replace(s.predictors[0],inputs=(f,)),),information_cutoff=ClockSpec('cutoff'))
    result=execute_predictor(s,CFG)
    assert all(o['execution']=='feature_unavailable' for o in result.private['output_rows'])


def test_outcome_restatement_preserves_predictions_and_unknown_variants(tmp_path):
    import csv
    from confidenceguard import (run_robustness,restate_execution,ExecutionRestatementSpec,OutcomeSnapshotSpec,SourceSpec)
    s=execution(tmp_path,n=12)
    scenario=ScenarioSpec('unknown',(TransformationSpec('same','identity'),))
    parent=run_robustness(RobustnessSpec(s,(scenario,)),CFG)
    path=tmp_path/'new-outcomes.csv'
    with path.open('w',newline='') as out:
        writer=csv.writer(out);writer.writerow(['id','truth']);writer.writerows((i,'yes') for i in range(12))
    restated=restate_execution(parent,ExecutionRestatementSpec((SourceSpec('later',str(path)),),OutcomeSnapshotSpec('later','truth',('id',)),'Synthetic later labels'),CFG)
    assert restated.data['cg6']['execution_repeated'] is False
    assert all(r['truth']['value']=='yes' for r in restated.private['output_rows'] if r['scenario']=='original')
    assert all(not r['truth']['valid'] for r in restated.private['output_rows'] if r['scenario']!='original')
    assert [(r['event_key'],r['channels']) for r in restated.private['output_rows']]==[(r['event_key'],r['channels']) for r in parent.private['output_rows']]
