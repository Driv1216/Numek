"""Build from an isolated source copy; never alter old wheels or environments."""
import hashlib
import argparse
import json
import os
from pathlib import Path
import shutil
import tempfile
import zipfile

ROOT=Path(__file__).resolve().parents[3]
HERE=Path(__file__).resolve().parent


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--name',default='package');args=parser.parse_args()
    destination=HERE/(args.name+'-wheel');destination.mkdir(exist_ok=False)
    with tempfile.TemporaryDirectory(prefix='numek-cg6-correction-build-') as temporary:
        source=Path(temporary)
        shutil.copytree(ROOT/'src',source/'src',ignore=shutil.ignore_patterns('__pycache__','*.pyc','*.egg-info'))
        for name in ('pyproject.toml','setup.py','README.md'):shutil.copyfile(ROOT/name,source/name)
        os.chdir(source)
        from setuptools.build_meta import build_wheel
        wheel=destination/build_wheel(str(destination))
    files={str(p.relative_to(ROOT/'src')):hashlib.sha256(p.read_bytes()).hexdigest()
           for p in sorted((ROOT/'src').rglob('*')) if p.is_file() and p.suffix in {'.py','.js','.css','.html','.json'}}
    with zipfile.ZipFile(wheel) as archive:
        mismatch=[name for name,sha in files.items() if hashlib.sha256(archive.read(name)).hexdigest()!=sha]
    if mismatch:raise AssertionError(mismatch)
    value={'passed':True,'wheel':str(wheel.relative_to(ROOT)),
        'wheel_sha256':hashlib.sha256(wheel.read_bytes()).hexdigest(),
        'source_files_verified':len(files),'files':files,
        'new_gradient_module_present':'confidenceguard/robustness/gradient_objectives.py' in files,
        'scope':'Isolated build and exact wheel byte comparison; no installed-wheel or hardware qualification claimed.'}
    (HERE/(args.name+'-receipt.json')).write_text(json.dumps(value,indent=2)+'\n')
    print(json.dumps({k:v for k,v in value.items() if k!='files'},indent=2))


if __name__=='__main__':main()
