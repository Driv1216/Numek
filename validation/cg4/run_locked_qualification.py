"""Run fixed CG4 benchmark tools against a verified immutable source snapshot.

This validation-only helper isolates long campaigns from ongoing workspace edits.
It is not imported by NUMEK and exposes no product predictor-execution interface.
"""
import argparse
import hashlib
import json
import os
import re
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ('qualify_pipeline.py', 'qualify_objectives.py', 'qualify_composed_approximate.py',
           'qualify_component_power.py','qualify_studentized.py','qualify_moment.py','qualify_landmark_comparison.py','qualify_history.py','qualify_partial_null.py','compare_baselines.py','replay_default_profile.py','replay_geometric_reference.py', 'profile_discovery.py')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def snapshot(source_identity=None):
    if source_identity is not None:
        if not re.fullmatch('[0-9a-f]{64}',source_identity):raise RuntimeError('Invalid source identity.')
        target=ROOT/'validation/cg4/source-capsules.nosync'/source_identity
        if target.is_symlink():raise RuntimeError('Qualification source directory cannot be a symlink.')
        manifest=json.loads((target/'source-manifest.json').read_text());hashes=manifest['files']
        expected=hashlib.sha256(json.dumps(hashes,sort_keys=True).encode()).hexdigest()
        if expected!=source_identity or manifest['source_identity']!=source_identity:raise RuntimeError('Source manifest identity differs.')
        for relative,expected in hashes.items():
            path=target/relative
            if not path.resolve().is_relative_to(target.resolve()) or path.is_symlink() or sha(path)!=expected:raise RuntimeError('Qualification source snapshot differs.')
        return target,source_identity
    admitted = {'.py', '.json', '.html', '.js', '.css', '.svg', '.woff', '.woff2', '.ttf'}
    files = [p for p in (ROOT/'src').rglob('*') if p.is_file() and p.suffix in admitted and '__pycache__' not in p.parts]
    files += list((ROOT/'validation/cg4').glob('*.py')) + list((ROOT/'validation/cg4').glob('qualification_protocol*.json'))
    files += [ROOT/'pyproject.toml', ROOT/'setup.py', ROOT/'.python-version']
    if any(p.is_symlink() for p in files): raise RuntimeError('Source snapshot refuses symlinked files.')
    hashes = {str(p.relative_to(ROOT)): sha(p) for p in sorted(files)}
    key = hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest()
    parent = ROOT/'validation/cg4/source-capsules.nosync'; parent.mkdir(exist_ok=True)
    target = parent/key
    if not target.exists():
        with tempfile.TemporaryDirectory(prefix='pending-', dir=parent) as temporary:
            staging = Path(temporary)/'source'; staging.mkdir()
            for relative, expected in hashes.items():
                raw = (ROOT/relative).read_bytes()
                if hashlib.sha256(raw).hexdigest() != expected: raise RuntimeError('Workspace source changed during snapshot capture.')
                destination = staging/relative; destination.parent.mkdir(parents=True, exist_ok=True); destination.write_bytes(raw)
            (staging/'source-manifest.json').write_text(json.dumps({'source_identity': key, 'files': hashes}, sort_keys=True, indent=2)+'\n')
            staging.rename(target)
    manifest = json.loads((target/'source-manifest.json').read_text())
    if manifest != {'source_identity': key, 'files': hashes} or any(sha(target/p) != h for p, h in hashes.items()):
        raise RuntimeError('Existing qualification source snapshot changed; refuse reuse.')
    return target, key


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--python', default=str(ROOT/'validation/cg4/py313q.nosync/bin/python'))
    parser.add_argument('--source-identity',help='Resume the exact captured source rather than capturing live edits.')
    parser.add_argument('script', choices=SCRIPTS); parser.add_argument('arguments', nargs=argparse.REMAINDER)
    args = parser.parse_args(); capsule, identity = snapshot(args.source_identity); forwarded = list(args.arguments)
    if forwarded[:1] == ['--']: forwarded.pop(0)
    for name in ('--out', '--prior'):
        if name in forwarded:
            index = forwarded.index(name)+1; forwarded[index] = str(Path(forwarded[index]).absolute())
    interpreter = str(Path(args.python).absolute()); environment = {**os.environ, 'PYTHONPATH': str(capsule/'src')}
    # Verify import origins before any long computation; editable installs must
    # not redirect this campaign to the live workspace.
    probe = subprocess.check_output([interpreter, '-B', '-c',
        'import confidenceguard,datatrust,json;print(json.dumps([confidenceguard.__file__,datatrust.__file__]))'],
        cwd=capsule, env=environment, text=True)
    if any(not Path(path).is_relative_to(capsule) for path in json.loads(probe)):
        raise RuntimeError('Qualification imports escaped the captured source tree.')
    binding = {'schema_version': 'numek.cg4_locked_source_run/1.0', 'source_identity': identity,
               'source_manifest': str(capsule/'source-manifest.json'), 'source_manifest_sha256': sha(capsule/'source-manifest.json'),
               'interpreter': interpreter, 'interpreter_sha256': sha(Path(interpreter)), 'script': args.script, 'arguments': forwarded,
               'scope': 'Source and installed qualification environment only. Qualification success is determined by the recorded protocol and results.'}
    if '--out' in forwarded:
        out = Path(forwarded[forwarded.index('--out')+1]); binding_path = out.with_name(out.name+'.source-capsule.json')
        binding_path.parent.mkdir(parents=True, exist_ok=True)
        if binding_path.exists() and json.loads(binding_path.read_text()) != binding: raise RuntimeError('Output belongs to another source snapshot.')
        if not binding_path.exists(): binding_path.write_text(json.dumps(binding, sort_keys=True, indent=2)+'\n')
    print(json.dumps({'locked_source': identity, 'script': args.script}), flush=True)
    subprocess.run([interpreter, '-B', str(capsule/'validation/cg4'/args.script), *forwarded],
                   cwd=capsule, env=environment, check=True)


if __name__ == '__main__':
    main()
