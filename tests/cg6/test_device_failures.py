from dataclasses import replace
from pathlib import Path
import threading
import pytest
from confidenceguard import (DeviceSpec,EvaluationError,EvaluationConfig,execute_predictor,register_host_predictor)
from confidenceguard import compat
from tests.cg6.host_fixtures import slow_torch_factory,allocator_oom_worker
from .helpers import execution,CFG


@pytest.mark.parametrize('device',['mps','cuda'])
def test_native_allocator_oom(device):
    import torch
    available=torch.backends.mps.is_available() if device=='mps' else torch.cuda.is_available()
    if not available:pytest.skip('not_run_hardware_unavailable: '+device+' allocator qualification requires compatible hardware')
    r=compat.supervise(allocator_oom_worker,(device,),EvaluationConfig(max_seconds=30,free_disk_bytes=1)).to_dict()
    assert r['native_oom_observed'],r


@pytest.mark.parametrize('device',['mps','cuda'])
def test_cancel_after_real_device_batch(tmp_path,device):
    import torch
    available=torch.backends.mps.is_available() if device=='mps' else torch.cuda.is_available()
    if not available:pytest.skip('not_run_hardware_unavailable: '+device+' cancellation qualification requires compatible hardware')
    source=Path(__file__).with_name('host_fixtures.py')
    register_host_predictor('cg6_slow_device',slow_torch_factory,code_files=(source,))
    s=execution(tmp_path,regression=True,n=200)
    p=replace(s.predictors[0],adapter='custom',registration='cg6_slow_device',architecture={})
    s=replace(s,predictors=(p,),device=DeviceSpec(device),limits=replace(s.limits,batch_rows=8))
    cancel=threading.Event();calls=[]
    def progress(value):
        if value.get('stage')=='predictor inference':
            calls.append(value)
            if len(calls)==2:cancel.set()
    with pytest.raises(EvaluationError) as error:execute_predictor(s,CFG,cancel=cancel,progress=progress)
    assert len(calls)>=2 and error.value.code=='cancelled'
