"""Enforce network denial inside the spawned optional model worker itself."""
from dataclasses import replace
import json
import os
from pathlib import Path
import socket
from datatrust import *

ROOT=Path(__file__).parent


def offline_model(*args,**kwargs):
    def blocked(*args,**kwargs): raise RuntimeError('Network forbidden in model validation worker.')
    socket.socket.connect=blocked
    socket.socket.connect_ex=blocked
    socket.create_connection=blocked
    from datatrust.image_models import execute_model
    result=execute_model(*args,**kwargs)
    result.execution['network_socket_operations']='blocked_inside_spawned_worker'
    return result


def run():
    import datatrust.images as images
    from datatrust.image_models import registry
    original=images.run_supervised
    def supervise(operation,args,options,**kwargs):
        return original(offline_model if operation.__name__=='execute_model' else operation,args,options,**kwargs)
    images.run_supervised=supervise
    data=ROOT/'data'; model=registry()['selection']['default']['model']
    spec=ImageAuditSpec((ImageInputSpec('data',ImageSourceSpec(str(data/'public_unlabeled.jsonl'),'jsonl',str(data))),),allowed_roots=(str(data.absolute()),))
    config=replace(ImageAnalysisConfig(),models=ImageModelOptions(str(ROOT/'models'/model.split('/')[-1])),limits=replace(ImageWorkLimits(),embedding_images=32))
    try: result=images.audit_images(spec,config)
    finally: images.run_supervised=original
    assert result.execution['status']=='completed'
    assert result.coverage['families']['embeddings']['embedded']==32
    assert result.execution['model_execution']['network_socket_operations']=='blocked_inside_spawned_worker'
    output=ROOT/os.environ.get('M7_RESULT_DIR','results/release'); output.mkdir(parents=True,exist_ok=True)
    (output/'offline_worker.json').write_text(json.dumps({'status':'passed','model':model,'execution':result.execution,'coverage':result.coverage},indent=2,allow_nan=False)+'\n')
    print('Offline execution enforced inside spawned worker: passed',flush=True)


if __name__=='__main__': run()
