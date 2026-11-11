"""Reproduce the current wheel from a clean temporary source copy.

Run with the locked primary interpreter from any working directory. This builds
only; it does not install dependencies or declare implementation completion.
"""
from pathlib import Path
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'validation/cg4'))
from package_review import admitted, verify_wheel


def main():
    output = ROOT / 'validation/cg4/results/wheel-current-v44'
    if output.exists():
        raise RuntimeError('Preserve earlier build evidence; choose a new identity.')
    output.mkdir(mode=0o700)
    sources = [p for p in (ROOT / 'src').rglob('*')
               if p.is_file() and admitted(p.relative_to(ROOT))]
    sources += [ROOT / name for name in ('pyproject.toml', 'setup.py', 'README.md', 'METHODOLOGY.md')]
    hashes = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in sorted(sources)}
    with tempfile.TemporaryDirectory(prefix='numek-cg4-wheel-v44-', dir='/private/tmp') as temporary:
        source = Path(temporary) / 'source'
        for path in sources:
            target = source / path.relative_to(ROOT)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)
            if hashlib.sha256(target.read_bytes()).hexdigest() != hashes[str(path.relative_to(ROOT))]:
                raise RuntimeError('Source changed while copying.')
        with (output / 'build.txt').open('x') as log:
            subprocess.run([sys.executable, '-B', '-c',
                            'import setuptools.build_meta as backend;backend.build_wheel('+repr(str(output))+')'],
                           cwd=source, env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'},
                           stdout=log, stderr=subprocess.STDOUT, check=True)
    wheels = list(output.glob('*.whl'))
    if len(wheels) != 1:
        raise RuntimeError('Expected exactly one built wheel.')
    verified = verify_wheel(wheels[0])
    if any(hashlib.sha256((ROOT / path).read_bytes()).hexdigest() != digest
           for path, digest in hashes.items()):
        raise RuntimeError('Source changed during build.')
    record = {'schema_version': 'numek.cg4_wheel_build/1.0', 'source_sha256': hashes,
              'python': sys.version, 'wheel': wheels[0].name, 'verification': verified,
              'scope': 'Clean-source current wheel build and runtime/static parity only. Installation, dependency resolution, reproduction and final review delivery remain separate.'}
    with (output / 'verification.json').open('x') as stream:
        json.dump(record, stream, sort_keys=True, indent=2); stream.write('\n')
    print(json.dumps({'wheel': str(wheels[0]), 'verification': verified}, sort_keys=True))


if __name__ == '__main__':
    main()
