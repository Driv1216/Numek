"""Final bounded canonical-equality overlap workload against supplied synthetic facts."""
import argparse,json,time
from pathlib import Path
from confidenceguard import ReliabilityWorkspace
from .fixtures import create

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',required=True);p.add_argument('--out',required=True);p.add_argument('--events',type=int,default=100000);a=p.parse_args()
    root=Path(a.root);out=Path(a.out);out.mkdir(exist_ok=False,parents=True)
    # Reproduce the pinned deterministic source bytes into a new source location.
    batch=create(out/'inputs',events=a.events);ws=ReliabilityWorkspace(root/'workspace');before=ws.status()
    started=time.monotonic();receipt=ws.ingest(batch);duration=time.monotonic()-started;after=ws.status()
    assert before['facts']['prediction']==after['facts']['prediction']
    result={'events':a.events,'seconds':duration,'before':before,'after':after,'receipt':receipt,'canonical_payload_checks':True,'hidden_sampling':False}
    (out/'reimport.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
