"""Build a source-only review wheel with installed locked build tools.

No dependency installation, generated egg-info reuse, analytics or acceptance.
"""
import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from package_review import ROOT, admitted, delivery_input, verify_wheel


def sha(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--out',required=True);args=parser.parse_args()
    output=Path(args.out).absolute()
    if output.exists():raise RuntimeError('Preserve prior build evidence; choose a new output.')
    sources=[p for prefix in ('confidenceguard','datatrust') for p in (ROOT/'src'/prefix).rglob('*')
             if p.is_file() and admitted(p.relative_to(ROOT))]
    sources += [ROOT/name for name in ('pyproject.toml','setup.py','README.md','METHODOLOGY.md')]
    for path in sources:
        delivery_input(path,'Build source')
        if not path.resolve().is_relative_to(ROOT):raise RuntimeError('Build source escaped the source root.')
    hashes={str(p.relative_to(ROOT)):sha(p) for p in sorted(sources)}
    output.mkdir(parents=True,mode=0o700)
    with tempfile.TemporaryDirectory(prefix='numek-cg4-review-wheel-',dir='/private/tmp') as temporary:
        source=Path(temporary)/'source'
        for path in sources:
            target=source/path.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(path,target)
            if sha(target)!=hashes[str(path.relative_to(ROOT))]:raise RuntimeError('Build input changed during capture.')
        environment={k:v for k,v in os.environ.items() if k!='PYTHONPATH'}
        with (output/'build.txt').open('x') as stream:
            subprocess.run([sys.executable,'-B','-c','import setuptools.build_meta as backend;backend.build_wheel('+repr(str(output))+')'],
                           cwd=source,env=environment,stdout=stream,stderr=subprocess.STDOUT,check=True)
    wheels=list(output.glob('*.whl'))
    if len(wheels)!=1:raise RuntimeError('Expected one wheel.')
    verified=verify_wheel(wheels[0])
    if any(sha(ROOT/name)!=h for name,h in hashes.items()):raise RuntimeError('Build source changed during execution.')
    record={'schema_version':'numek.cg4_wheel_build/1.0','source_sha256':hashes,'python':sys.version,
            'build_tools':{name:importlib.metadata.version(name) for name in ('setuptools','wheel')},
            'wheel':wheels[0].name,'verification':verified,
            'scope':'Clean-source build excluding generated metadata/cache. Exact runtime/static parity; installation, reproduction and final delivery remain separate.'}
    with (output/'verification.json').open('x') as stream:json.dump(record,stream,indent=2,sort_keys=True);stream.write('\n')
    print(json.dumps({'wheel':str(wheels[0]),'verification':verified},sort_keys=True))


if __name__=='__main__':main()
