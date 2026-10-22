"""Synthetic-only local browser qualification host; never opens real workspaces."""
import argparse
from pathlib import Path
import secrets
from datatrust.web import create_app
from confidenceguard import ReliabilityWorkspace,WorkspaceConfig
from .fixtures import create

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--root',required=True);parser.add_argument('--port',type=int,default=8033);parser.add_argument('--existing',action='store_true');args=parser.parse_args()
    root=Path(args.root)
    if args.existing:workspace=ReliabilityWorkspace(root/'workspace')
    else:
        root.mkdir(exist_ok=False,parents=True)
        workspace=ReliabilityWorkspace.initialize(root/'workspace',WorkspaceConfig());create(root/'inputs',events=365)
    token=secrets.token_urlsafe(32)
    app=create_app(root/('host-'+secrets.token_hex(6)),data_roots=(root/'inputs',),confidenceguard_workspace=workspace.path,confidenceguard_launch_token=token)
    print(f'http://127.0.0.1:{args.port}/confidenceguard?launch={token}',flush=True)
    try:app.run(host='127.0.0.1',port=args.port,threaded=True,debug=False,use_reloader=False)
    finally:app.extensions['confidenceguard_store'].cleanup()
