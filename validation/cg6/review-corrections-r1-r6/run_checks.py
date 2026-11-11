"""Source-bound receipts for the bounded R1–R6 correction checks."""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[3]
HERE=Path(__file__).resolve().parent


def source_map(folder, suffixes):
    return {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted((ROOT/folder).rglob('*')) if p.is_file() and p.suffix in suffixes}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--name',required=True)
    parser.add_argument('tests',nargs='+')
    args=parser.parse_args()
    log=HERE/(args.name+'.log');receipt=HERE/(args.name+'.json')
    if log.exists() or receipt.exists():raise RuntimeError('Preserve existing receipts; use a new check name.')
    runtime=source_map('src',{'.py','.js','.css','.html','.json'})
    tests=source_map('tests',{'.py'})
    command=[sys.executable,'-B','-m','pytest',*args.tests,'-v','-ra','--tb=short','-p','no:cacheprovider']
    env={**os.environ,'PYTHONPATH':str(ROOT/'src'),'PYTHONDONTWRITEBYTECODE':'1'}
    started=datetime.now(timezone.utc).isoformat();clock=time.monotonic()
    with log.open('x') as stream:
        result=subprocess.run(command,cwd=ROOT,env=env,stdout=stream,stderr=subprocess.STDOUT)
    unchanged=runtime==source_map('src',{'.py','.js','.css','.html','.json'}) and tests==source_map('tests',{'.py'})
    versions={}
    for package in ('torch','numpy','scikit-learn','skops','onnxruntime','safetensors','pytest'):
        try:versions[package]=importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:versions[package]=None
    value={'command':command,'started_at':started,'elapsed_seconds':time.monotonic()-clock,
           'exit_code':result.returncode,'passed':result.returncode==0 and unchanged,
           'source_unchanged_during_check':unchanged,'python':sys.version,'versions':versions,
           'runtime_source_sha256':runtime,'test_source_sha256':tests,
           'runtime_source_digest':hashlib.sha256(json.dumps(runtime,sort_keys=True,separators=(',',':')).encode()).hexdigest(),
           'log_sha256':hashlib.sha256(log.read_bytes()).hexdigest(),
           'cuda_runtime_qualification':'not_claimed_by_this_receipt'}
    receipt.write_text(json.dumps(value,indent=2)+'\n')
    print(json.dumps({k:value[k] for k in ('passed','exit_code','elapsed_seconds','runtime_source_digest')}))
    print('\n'.join(log.read_text().splitlines()[-22:]))
    raise SystemExit(0 if value['passed'] else 1)


if __name__=='__main__':main()
