from dataclasses import replace
import json
import numpy as np
import pytest

from confidenceguard import execute_predictor,inspect_predictor,qualify_predictor,EvaluationResult,EvaluationError,DeviceSpec
from confidenceguard.execution.devices import resolve,onnx_options
from .helpers import execution,CFG,file


def test_execution_reuses_native_metrics_and_reopens(tmp_path):
    spec=execution(tmp_path)
    inspected=inspect_predictor(spec,CFG)
    result=execute_predictor(spec,CFG,expected_fingerprint=inspected['fingerprint'])
    accuracy=next(m for m in result.data['measurements'] if m['metric']=='accuracy')
    assert accuracy['value']==.5 and accuracy['denominator']==60
    assert result.data['coverage']['planned_roots']==60
    assert len(result.private['output_rows'])==60
    EvaluationResult.from_dict(result.to_private_dict(),private=result.private)
    exported=result.generate_artifacts(tmp_path/'result.html',json_path=tmp_path/'result.json',audience='shareable')
    assert exported.private_manifest_path is None
    assert 'inputs.csv' not in (tmp_path/'result.html').read_text()
    public=EvaluationResult.from_dict(json.loads((tmp_path/'result.json').read_text()))
    with pytest.raises(EvaluationError):public.to_dict(audience='local')


def test_regression_parity_and_stale_identity(tmp_path):
    spec=execution(tmp_path,regression=True)
    q=qualify_predictor(spec,CFG)
    assert q.data['cg6']['parity']['batch_parity']=='passed'
    assert q.data['cg6']['parity']['reference_parity']=='not_supplied'
    inspected=inspect_predictor(spec,CFG)
    path=tmp_path/'inputs.csv';path.write_text(path.read_text().replace('0.5,','0.6,'))
    with pytest.raises(EvaluationError) as e:execute_predictor(spec,CFG,expected_fingerprint=inspected['fingerprint'])
    assert e.value.code=='stale_confirmation'


def test_cuda_contract_is_not_hardware_qualification():
    device=DeviceSpec(kind='cuda',index=2)
    with pytest.raises(EvaluationError):resolve(device,'torch',{'cpu':True,'cuda':False,'mps':False})
    r=resolve(device,'torch',{'cpu':True,'cuda':True,'mps':False})
    assert r['torch_device']=='cuda:2'
    assert r['qualification']=='runtime_execution_not_yet_established'
    assert onnx_options(device,r)[0][1]['device_id']==2
    assert len(onnx_options(device,r))==1
    assert resolve(replace(device,allow_cpu_fallback=True),'torch',{'cpu':True,'cuda':False})['kind']=='cpu'


def test_sklearn_pipeline_class_mapping(tmp_path):
    from sklearn.pipeline import make_pipeline
    from sklearn.impute import SimpleImputer
    from sklearn.linear_model import LogisticRegression
    import skops.io as sio
    from confidenceguard import OutputBinding
    spec=execution(tmp_path)
    model=make_pipeline(SimpleImputer(),LogisticRegression()).fit(np.array([[0.],[1.],[2.],[3.]]),np.array(['no','no','yes','yes']))
    path=tmp_path/'model.skops';sio.dump(model,path)
    p=replace(spec.predictors[0],adapter='sklearn',architecture={},files=(file(path),),entry=path.name,
              outputs=(OutputBinding('probabilities','predict_proba',classes=tuple(map(str,model.classes_))),OutputBinding('prediction','predict')))
    result=execute_predictor(replace(spec,predictors=(p,)),CFG)
    assert all(r['execution']=='completed' for r in result.private['output_rows'])
    bad=replace(p,outputs=(OutputBinding('probabilities','predict_proba',classes=('yes','no')),))
    with pytest.raises(EvaluationError) as e:execute_predictor(replace(spec,predictors=(bad,)),CFG)
    assert e.value.code=='predictor_class_mapping'
