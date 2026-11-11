"""Explicit hardware contracts. Availability is never runtime qualification."""
import importlib.metadata
import platform
import sys
import time

from ..contracts import EvaluationError
from .contracts import DeviceSpec


def capabilities():
    versions={}
    for p in ('torch','scikit-learn','skops','onnxruntime','onnxruntime-gpu','numpy','safetensors'):
        try: versions[p]=importlib.metadata.version(p)
        except importlib.metadata.PackageNotFoundError: versions[p]=None
    availability={'cpu':True,'mps':False,'cuda':False}
    if versions['torch']:
        import torch
        availability.update(mps=torch.backends.mps.is_available(),cuda=torch.cuda.is_available())
    return {'implementation':{k:'implemented' for k in availability},'availability':availability,
            'qualification':{k:'not_established_by_capability_probe' if v else 'not_run_hardware_unavailable' for k,v in availability.items()},
            'versions':versions,'python':sys.version,'platform':platform.platform(),
            'scientific_method_standing':'Independent of availability and device execution; use the scoped source-bound method qualification receipts and dataset assessment.',
            'interpretation':'Availability probes and contract tests do not establish runtime or scientific qualification.'}


def resolve(spec, adapter, observed=None):
    if isinstance(spec,dict): spec=DeviceSpec.from_dict(spec)
    availability=observed if observed is not None else capabilities()['availability']
    kind=spec.kind
    if kind=='auto': kind=next((k for k in ('cuda','mps','cpu') if availability.get(k) and (adapter not in {'sklearn','constant'} or k=='cpu') and (adapter!='onnx' or k!='mps')),'cpu')
    reason=None
    supported=kind=='cpu' or adapter in {'torch','custom'} or adapter=='onnx' and kind=='cuda'
    if not supported or not availability.get(kind,False):
        if not spec.allow_cpu_fallback: raise EvaluationError('Requested execution device is unavailable or incompatible.','device_unavailable')
        reason='device_unavailable_or_incompatible';kind='cpu'
    if kind=='mps' and spec.precision=='float64': raise EvaluationError('MPS float64 is unsupported.','device_precision')
    return {'requested':spec.to_dict(),'kind':kind,'index':spec.index if kind=='cuda' else 0,
            'torch_device':f'cuda:{spec.index}' if kind=='cuda' else kind,
            'fallback_reason':reason,'qualification':'runtime_execution_not_yet_established'}


def configure_torch(spec, config, realization):
    import os
    # Validate the operator's startup setting before seeding, device selection,
    # allocation or any other CUDA initialization here. Never silently change
    # it after a caller may already have initialized cuBLAS.
    if realization['kind']=='cuda' and spec.deterministic:
        setting=os.environ.get('CUBLAS_WORKSPACE_CONFIG')
        if setting not in {':4096:8',':16:8'}:
            raise EvaluationError('Deterministic CUDA requires CUBLAS_WORKSPACE_CONFIG=:4096:8 or :16:8 before process startup.','device_profile')
        realization['cublas_workspace_config']=setting
    import torch
    if realization['kind']=='mps' and os.environ.get('PYTORCH_ENABLE_MPS_FALLBACK')=='1':
        raise EvaluationError('Implicit MPS CPU fallback is enabled; use an explicit admitted execution profile.','device_profile')
    torch.set_num_threads(config.threads)
    torch.manual_seed(0)
    torch.use_deterministic_algorithms(spec.deterministic)
    if realization['kind']=='cuda':
        if realization['index']>=torch.cuda.device_count(): raise EvaluationError('CUDA index is unavailable.','device_unavailable')
        torch.cuda.set_device(realization['index'])
        torch.cuda.manual_seed_all(0)
        torch.backends.cudnn.benchmark=False
        torch.backends.cudnn.deterministic=spec.deterministic
        torch.backends.cuda.matmul.allow_tf32=False
        torch.backends.cudnn.allow_tf32=False
        torch.cuda.set_per_process_memory_fraction(min(1.,spec.memory_bytes/torch.cuda.get_device_properties(realization['index']).total_memory),realization['index'])
    if realization['kind']=='mps':
        # This allocator fraction is a safeguard, not a hard OS quota.
        available=getattr(torch.mps,'recommended_max_memory',lambda:spec.memory_bytes)()
        torch.mps.set_per_process_memory_fraction(min(1.,spec.memory_bytes/max(1,available)))
    return getattr(torch,spec.precision)


def synchronize(kind):
    if kind=='cuda':
        import torch
        torch.cuda.synchronize()
    elif kind=='mps':
        import torch
        torch.mps.synchronize()


def memory(realization):
    kind=realization['kind']
    if kind=='cuda':
        import torch
        d=realization['index']
        return {'allocated_bytes':torch.cuda.memory_allocated(d),'reserved_bytes':torch.cuda.memory_reserved(d),
                'peak_allocated_bytes':torch.cuda.max_memory_allocated(d),'device_wide_telemetry':'not_observed'}
    if kind=='mps':
        import torch
        return {'allocated_bytes':torch.mps.current_allocated_memory(),'driver_allocated_bytes':torch.mps.driver_allocated_memory(),
                'physical_memory_addition_to_rss':'not_valid_unified_memory_overlap'}
    return {'allocated_bytes':None,'reason':'cpu_device_allocator_not_available'}


def check_memory(realization, spec):
    evidence=memory(realization)
    if (evidence.get('allocated_bytes') or 0)>spec.memory_bytes:
        raise EvaluationError('Device allocation exceeded its configured budget.','device_memory_limit')
    return evidence


def onnx_options(spec, realization):
    if realization['kind']=='cpu': return [('CPUExecutionProvider',{})]
    if realization['kind']!='cuda': raise EvaluationError('ONNX MPS is not a supported provider.','device_unavailable')
    result=[('CUDAExecutionProvider',{'device_id':realization['index'],'gpu_mem_limit':spec.memory_bytes,
                                   'do_copy_in_default_stream':True,'use_tf32':False})]
    if spec.onnx_mode=='hybrid':result.append(('CPUExecutionProvider',{}))
    return result
