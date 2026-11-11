"""Explicitly operator-installed test fixtures; never model-upload imports."""
import time
import numpy as np


def slow_torch_factory(spec,directory,realization):
    import torch
    class Predictor:
        def predict(self,values):
            tensor=torch.as_tensor(values,device=realization['torch_device'],dtype=torch.float32)
            output=tensor.sum(dim=1).detach().cpu().numpy()
            time.sleep(.05)
            return {'output':output}
    return Predictor()


def allocator_oom_worker(kind,*,progress=None):
    import torch
    from confidenceguard.result import Inspection
    if kind=='mps':
        torch.mps.set_per_process_memory_fraction(64*1024**2/torch.mps.recommended_max_memory())
    else:
        torch.cuda.set_per_process_memory_fraction(64*1024**2/torch.cuda.get_device_properties(0).total_memory)
    observed=False;message=None
    try:
        tensor=torch.ones(32*1024**2,dtype=torch.float32,device=kind)
        tensor.sum().cpu().item()
    except RuntimeError as exc:
        observed='out of memory' in str(exc).lower();message=str(exc)
    return Inspection({'device':kind,'native_oom_observed':observed,'allocator_limit_bytes':64*1024**2,
        'probe_request_bytes':128*1024**2,'failure':message,'interpretation':'allocator-limited native OOM; physical memory exhaustion was not attempted'}, {'status':'completed','peak_workspace_bytes':0})


def centered_batch_factory(spec,directory,realization):
    import numpy as np
    class Predictor:
        def predict(self,values):
            x=np.asarray(values,float)[:,0]
            return {'output':(x-x.mean())[:,None]}
    return Predictor()
