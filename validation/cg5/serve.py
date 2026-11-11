"""Local synthetic UI verification host; never production or external data."""
from pathlib import Path
from datatrust.web import create_app
from confidenceguard import ReliabilityWorkspace,WorkspaceConfig
if __name__=='__main__':
    root=Path(__file__).resolve().parent/'results'
    root.mkdir(exist_ok=True)
    retained=root/'browser-retained'
    if not retained.exists():
        try:ReliabilityWorkspace.initialize(retained,WorkspaceConfig(saving=True,free_disk_bytes=1))
        except FileExistsError:pass
    create_app(root/'browser-host',data_roots=(root,),confidenceguard_workspace=retained,confidenceguard_launch_token='cg5-synthetic-local-verification').run(host='127.0.0.1',port=8965,threaded=True,use_reloader=False)
