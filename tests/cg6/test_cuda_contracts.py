"""Contract evidence only: these tests do not execute or qualify CUDA."""
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from confidenceguard import DeviceSpec,EvaluationConfig,EvaluationError
from confidenceguard.execution.devices import resolve,onnx_options,configure_torch,memory


def test_cuda_request_provider_options_and_explicit_failure():
    device=DeviceSpec('cuda',index=2,memory_bytes=128*1024**2)
    realized=resolve(device,'onnx',{'cpu':True,'mps':False,'cuda':True})
    providers=onnx_options(device,realized)
    assert providers==[('CUDAExecutionProvider',{'device_id':2,'gpu_mem_limit':128*1024**2,'do_copy_in_default_stream':True,'use_tf32':False})]
    assert onnx_options(replace(device,onnx_mode='hybrid'),realized)[1]==('CPUExecutionProvider',{})
    with pytest.raises(EvaluationError) as e:resolve(device,'torch',{'cpu':True,'cuda':False})
    assert e.value.code=='device_unavailable'
    assert resolve(replace(device,allow_cpu_fallback=True),'torch',{'cpu':True,'cuda':False})['kind']=='cpu'


def test_cuda_training_configuration_and_accounting_interfaces(monkeypatch):
    import torch
    monkeypatch.setenv('CUBLAS_WORKSPACE_CONFIG',':4096:8')
    cuda=SimpleNamespace(**{k:Mock(return_value=v) for k,v in {'device_count':3,'set_device':None,'manual_seed_all':None,
        'set_per_process_memory_fraction':None,'get_device_properties':SimpleNamespace(total_memory=1024**3),
        'memory_allocated':41,'memory_reserved':73,'max_memory_allocated':59}.items()})
    monkeypatch.setattr(torch,'cuda',cuda)
    monkeypatch.setattr(torch,'manual_seed',Mock())
    monkeypatch.setattr(torch,'use_deterministic_algorithms',Mock())
    monkeypatch.setattr(torch,'set_num_threads',Mock())
    device=DeviceSpec('cuda',index=2,memory_bytes=128*1024**2,deterministic=True)
    realization={'kind':'cuda','index':2}
    assert configure_torch(device,EvaluationConfig(),realization)==torch.float32
    cuda.set_device.assert_called_once_with(2)
    cuda.set_per_process_memory_fraction.assert_called_once_with(.125,2)
    assert memory(realization)['allocated_bytes']==41
    with pytest.raises(EvaluationError):configure_torch(replace(device,index=3),EvaluationConfig(),{'kind':'cuda','index':3})
