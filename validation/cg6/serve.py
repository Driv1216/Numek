"""Loopback-only synthetic CG6 browser qualification host."""
from pathlib import Path
from datatrust.web import create_app
from confidenceguard import ReliabilityWorkspace,WorkspaceConfig

if __name__=='__main__':
    root=Path(__file__).resolve().parent/'results'/'browser';root.mkdir(parents=True,exist_ok=True)
    retained=root/'retained'
    if not retained.exists():ReliabilityWorkspace.initialize(retained,WorkspaceConfig(saving=True,free_disk_bytes=1))
    create_app(root/'host',data_roots=(root,),confidenceguard_workspace=retained,confidenceguard_launch_token='cg6-synthetic-local-verification').run(host='127.0.0.1',port=8966,threaded=True,use_reloader=False)
