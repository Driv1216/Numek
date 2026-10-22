"""Measured storage/scan probes. Always write new evidence directories."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time
import psutil
from confidenceguard import ReliabilityWorkspace,WorkspaceConfig
from .fixtures import create,specification


def run(output,events,kind,classes,samples):
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    batch=create(output/'inputs',kind=kind,events=events,classes=classes,samples=samples)
    workspace=ReliabilityWorkspace.initialize(output/'workspace',WorkspaceConfig(saving=True))
    process=psutil.Process();started=time.monotonic()
    receipt=workspace.ingest(batch)
    recorded=time.monotonic()-started
    settings=specification(workspace.models(),cohort=False)
    started=time.monotonic();result=workspace.analyze(settings);analysis=time.monotonic()-started
    started=time.monotonic();duplicate=workspace.ingest(batch);overlap=time.monotonic()-started
    source_bytes=sum(p.stat().st_size for p in (output/'inputs').iterdir())
    probes={'record_seconds':recorded,'analysis_seconds':analysis,'overlapping_import_seconds':overlap,
            'events':events,'kind':kind,'classes':classes,'samples_per_event':samples,'source_bytes':source_bytes,
            'workspace':workspace.status(),'scan':result.data['history']['materialization'],
            'analysis_execution':result.execution,'record_receipt':receipt,'duplicate_receipt':duplicate,
            'parent_rss_after_bytes':process.memory_info().rss,'timestamp':datetime.now(timezone.utc).isoformat(),
            'qualification':'Local measured workload; sampled resources and concurrent load do not establish capacity or isolated speed guarantees.'}
    (output/'resources.json').write_text(json.dumps(probes,indent=2)+'\n')
    print(json.dumps({k:probes[k] for k in ('events','record_seconds','analysis_seconds','overlapping_import_seconds')},indent=2),flush=True)
    return probes


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--out',required=True);parser.add_argument('--events',type=int,default=10000)
    parser.add_argument('--kind',default='binary_classification');parser.add_argument('--classes',type=int,default=24);parser.add_argument('--samples',type=int,default=0)
    args=parser.parse_args();run(args.out,args.events,args.kind,args.classes,args.samples)
