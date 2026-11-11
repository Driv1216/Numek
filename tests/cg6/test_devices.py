from dataclasses import replace
import json
import numpy as np
import pytest

from confidenceguard import (PredictorSpec,OutputBinding,DeviceSpec,execute_predictor,qualify_predictor,
    AuxiliaryStudySpec,AuxiliaryCandidate,fit_auxiliary,RobustnessSpec,ScenarioSpec,AttackSpec,run_robustness)
from confidenceguard.execution.adapters import torch_architecture
from .helpers import execution,file,CFG


def torch_spec(tmp_path):
    import torch
    from safetensors.torch import save_file
    s=execution(tmp_path,regression=True)
    p=replace(s.predictors[0],architecture={'kind':'mlp','hidden':[],'input_dim':1,'output_dim':1})
    model=torch_architecture(p,{})
    with torch.no_grad():model.net[0].weight.fill_(2);model.net[0].bias.fill_(1)
    path=tmp_path/'linear.safetensors';save_file(model.state_dict(),str(path))
    return replace(s,predictors=(replace(p,adapter='torch',entry=path.name,files=(file(path),)),))


def test_torch_complete_reference_and_pgd_oracle(tmp_path):
    s=torch_spec(tmp_path)
    result=execute_predictor(s,CFG)
    expected=[{**row,'channels':{'point':1+2*float(row['input_record']['x'])}} for row in result.private['output_rows']]
    q=qualify_predictor(s,CFG,reference=expected)
    assert q.data['cg6']['parity']['reference_parity']=='passed'
    attack=AttackSpec('pgd',('x',),access='white_box',epsilon=.1,steps=3,restarts=1,queries_per_root=10,step_size=.05)
    r=run_robustness(RobustnessSpec(s,(ScenarioSpec('attack',attack=attack),)),CFG)
    witnesses=[o['variant']['attack'] for o in r.private['output_rows'] if 'variant' in o]
    assert witnesses and all(w['gradient_steps']==3 and abs(w['best_objective']-.2)<1e-5 for w in witnesses)


@pytest.mark.parametrize('device',['cpu','cuda'])
def test_onnx_local_graph_reference(tmp_path,device):
    import onnx
    if device=='cuda':
        import torch,onnxruntime
        if not torch.cuda.is_available():pytest.skip('not_run_hardware_unavailable: ONNX CUDA qualification requires compatible NVIDIA hardware')
        if 'CUDAExecutionProvider' not in onnxruntime.get_available_providers():pytest.fail('NVIDIA hardware is available but the admitted ONNX CUDA provider is missing')
    from onnx import helper,TensorProto,numpy_helper
    s=execution(tmp_path,regression=True)
    graph=helper.make_graph([helper.make_node('MatMul',['x','w'],['z']),helper.make_node('Add',['z','b'],['point'])],
        'linear',[helper.make_tensor_value_info('x',TensorProto.FLOAT,[None,1])],[helper.make_tensor_value_info('point',TensorProto.FLOAT,[None,1])],
        [numpy_helper.from_array(np.asarray([[2]],np.float32),'w'),numpy_helper.from_array(np.asarray([1],np.float32),'b')])
    model=helper.make_model(graph,opset_imports=[helper.make_opsetid('',17)]);model.ir_version=10
    path=tmp_path/'linear.onnx';onnx.save(model,path)
    p=replace(s.predictors[0],adapter='onnx',entry=path.name,files=(file(path),),preprocessing={'kind':'numeric','dtype':'float32'},outputs=(OutputBinding('point','point'),),architecture={})
    r=qualify_predictor(replace(s,predictors=(p,),device=DeviceSpec(device)),CFG)
    assert r.data['cg6']['parity']['batch_parity']=='passed'
    assert all(abs(o['channels']['point']-(1+2*float(o['input_record']['x'])))<1e-5 for o in r.private['output_rows'])
    observed=r.data['cg6']['devices']['model']['observed_node_execution']
    assert observed['CUDAExecutionProvider' if device=='cuda' else 'CPUExecutionProvider']>0
    if device=='cuda':assert not observed.get('CPUExecutionProvider')


@pytest.mark.parametrize('device',['mps','cuda'])
def test_real_device_execution_fit_and_backward(tmp_path,device):
    import torch
    if not (torch.backends.mps.is_available() if device=='mps' else torch.cuda.is_available()):pytest.skip('not_run_hardware_unavailable: compatible '+device+' runtime not exposed to this process')
    s=torch_spec(tmp_path);cpu=execute_predictor(s,CFG)
    mps=replace(s,device=DeviceSpec(device))
    q=qualify_predictor(mps,CFG,reference=cpu.private['output_rows'],atol=1e-5,rtol=1e-4)
    assert q.data['cg6']['parity']['reference_parity']=='passed'
    assert q.data['cg6']['devices']['model']['kind']==device
    study=AuxiliaryStudySpec(mps,'scale','model',candidates=(AuxiliaryCandidate('mlp','mlp',parameters={'epochs':3,'patience':2,'hidden':[8,8],'batch_rows':8}),))
    fitted=fit_auxiliary(study,CFG)
    assert fitted.private['auxiliary_artifacts'][0]['predictors'][0]['adapter']=='torch'
    from confidenceguard import apply_auxiliary
    applied=apply_auxiliary(mps,fitted.private['auxiliary_artifacts'][0],CFG,role='E')
    assert all(o['channels']['scale']>0 for o in applied.private['output_rows'])
    assert all(d['kind']==device for d in applied.data['cg6']['devices'].values())
    scenario=ScenarioSpec('mps_gradient',attack=AttackSpec('fgsm',('x',),access='white_box',epsilon=.1,queries_per_root=4))
    r=run_robustness(RobustnessSpec(mps,(scenario,),role='E'),CFG)
    assert all(w['variant']['attack']['gradient_steps']==1 for w in r.private['output_rows'] if 'variant' in w)


def test_cuda_runtime_pending_without_hardware(tmp_path):
    import torch
    if not torch.cuda.is_available():pytest.skip('not_run_hardware_unavailable: CUDA runtime qualification requires NVIDIA hardware')
    s=replace(torch_spec(tmp_path),device=DeviceSpec('cuda'))
    r=qualify_predictor(s,CFG,atol=1e-5,rtol=1e-4)
    assert r.data['cg6']['devices']['model']['kind']=='cuda'
    assert r.data['cg6']['parity']['batch_parity']=='passed'
