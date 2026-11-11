"""Assemble the explicit CG4 review handoff after implementation closure.

No dependency installation, analytics or qualification runs. Archive verification
is separate from clean installation/reproduction and independent technical review.
Never run against an active qualification output directory.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import zipfile

from review_inventory import check_zip
from run_locked_qualification import ROOT, snapshot


def record(path):
    with path.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    return {'bytes': path.stat().st_size, 'sha256': digest}


def delivery_input(path, label):
    """Refuse links/special files before any archive parsing or hashing."""
    path = Path(path).absolute()
    if not stat.S_ISREG(path.lstat().st_mode):
        raise ValueError(label+' must be a regular file, not a link or special file.')
    return path


def admitted(path):
    return (not any(part in {'__pycache__', '.git', '.pytest_cache', '.venv'} or part.endswith('.nosync') for part in path.parts)
            and path.name != '.DS_Store' and path.suffix not in {'.pyc', '.pending'}
            and not path.name.startswith('.env'))


def referenced_synthetic_state(root):
    """Retain the exact local proof bytes already named by the v59 receipt.

    These two generated fixtures contain synthetic workspace state, not Python
    environments or model caches. All other .nosync exclusions remain in force.
    """
    manifest=root/'validation/cg4/results/verification/selector-correction-v59-manifest.json'
    if not manifest.exists():return set()
    delivery_input(manifest,'Synthetic evidence receipt')
    selected=set();fixtures={'review-reproduction-paired-v53','review-reproduction-paired-v55'}
    for row in json.loads(manifest.read_text())['files']:
        from review_inventory import safe_archive_path
        safe_archive_path(row['path'])
        relative=Path(row['path'])
        if admitted(relative):continue
        parts=relative.parts
        if (relative.is_absolute() or '..' in parts or len(parts)<6
                or parts[:3]!=('validation','cg4','results') or parts[3] not in fixtures
                or parts[4]!='runtime.nosync' or relative.suffix not in {'.json','.jsonl','.parquet','.npy','.sqlite3','.lock'}):
            raise ValueError('Excluded evidence is not a declared synthetic workspace file.')
        source=root/relative;boundary=root.joinpath(*parts[:5])
        if source.is_symlink() or not source.resolve().is_relative_to(boundary.resolve()):
            raise ValueError('Synthetic evidence escaped its fixture boundary.')
        delivery_input(source,'Synthetic evidence')
        if record(source)!={'bytes':row['bytes'],'sha256':row['sha256']}:
            raise ValueError('Referenced synthetic evidence changed after its recorded verification.')
        selected.add(source)
    return selected


def source_inventory(root=ROOT):
    """Fixed product, test, methodology and synthetic qualification boundaries."""
    paths = set()
    for relative in ('src/confidenceguard', 'src/datatrust', 'tests', 'docs', 'constraints', 'validation/cg4/results'):
        for path in (root/relative).rglob('*'):
            if path.is_file() and admitted(path.relative_to(root)):
                paths.add(path)
    for milestone in ('cg1', 'cg2', 'cg3', 'cg4'):
        for path in (root/'validation'/milestone).iterdir():
            if path.is_file() and path.suffix in {'.py', '.md', '.json'}:
                paths.add(path)
    # Delivered legacy tests import these authored validation modules. Keep code
    # and instructions, not their external datasets, environments or model caches.
    for path in (root/'validation').glob('*'):
        if path.is_file() and path.suffix in {'.py','.md','.json'} and admitted(path.relative_to(root)):
            paths.add(path)
    for name in [*('m'+str(i) for i in range(1,10)),'unlabeled','ws3','ws4']:
        for parent, directories, filenames in os.walk(root/'validation'/name):
            parent=Path(parent)
            directories[:]=[n for n in directories if admitted((parent/n).relative_to(root))]
            for filename in filenames:
                path=parent/filename
                if path.suffix in {'.py','.md'} and admitted(path.relative_to(root)):paths.add(path)
    for test, fixture in [('tests/test_m1_analysis.py','validation/unlabeled/known_evidence.csv'),
                          ('tests/cg1/test_review_corrections.py','validation/cg1/results/reports/binary-shareable.json')]:
        if (root/test).is_file():
            path=root/fixture;delivery_input(path,'Required legacy test fixture');paths.add(path)
    for path in (root/'validation/cg1/data').rglob('*'):
        if path.is_file() and admitted(path.relative_to(root)):
            paths.add(path)
    for relative in ('README.md', 'METHODOLOGY.md', 'pyproject.toml', 'setup.py', '.python-version', '.gitignore',
                     'agents/skills/verify/skills.md', 'validation/__init__.py',
                     'validation/cg4/REVIEW_QUICKSTART.md', 'validation/cg4/CG4_IMPLEMENTATION_FINDINGS.md'):
        paths.add(root/relative)
    paths.update(referenced_synthetic_state(root))
    return paths


def verify_wheel(wheel, root=ROOT):
    """Every delivered runtime file must match the final wheel byte-for-byte."""
    root=Path(root).resolve()
    required = {str(p.relative_to(root/'src')): p for prefix in ('confidenceguard', 'datatrust')
                for p in (root/'src'/prefix).rglob('*') if p.is_file() and admitted(p.relative_to(root))}
    for source in required.values():
        if source.is_symlink() or not source.resolve().is_relative_to(root):
            raise ValueError('Runtime source escaped its review root.')
    with zipfile.ZipFile(wheel) as archive:
        names = [entry.filename for entry in archive.infolist()]
        if len(names) != len(set(names)):
            raise ValueError('Duplicate wheel members.')
        for name, source in required.items():
            if name not in names or hashlib.sha256(archive.read(name)).hexdigest() != record(source)['sha256']:
                raise ValueError('Wheel lacks final runtime bytes: '+name)
    return {'runtime_files_verified': len(required), 'wheel': record(wheel)}


def build(stage, output, wheel, synthetic_backup):
    stage = Path(stage).absolute(); output = Path(output).absolute()
    wheel = delivery_input(wheel, 'Wheel'); backup = delivery_input(synthetic_backup, 'Synthetic backup')
    pending = output.with_suffix(output.suffix+'.pending')
    if stage.exists() or output.exists() or pending.exists() or output.with_suffix(output.suffix+'.sha256').exists():
        raise ValueError('Use new staging/output paths; never overwrite delivered evidence.')
    if not backup.is_file() or backup.is_symlink() or not backup.name.endswith('.tar.gz'):
        raise ValueError('Supply the separately verified synthetic backup archive.')
    wheel_check = verify_wheel(wheel)
    delivery = [(wheel, 'wheel/'+wheel.name, wheel_check['wheel']),
                (backup, 'examples/synthetic-backup.tar.gz', record(backup))]
    selected = source_inventory()
    # These are verified source-only snapshots, not environments/model caches.
    capsules = ROOT/'validation/cg4/source-capsules.nosync'
    for directory in capsules.iterdir():
        if not directory.is_dir() or len(directory.name) != 64:
            continue
        capsule, _ = snapshot(directory.name)
        selected.update(p for p in capsule.rglob('*') if p.is_file())
    for source in selected:
        if source.is_symlink() or not source.resolve().is_relative_to(ROOT):
            raise ValueError('Review input escaped its authorized source boundary.')
    before = {str(p.relative_to(ROOT)): record(p) for p in sorted(selected)}
    stage.mkdir(parents=True, mode=0o700)
    for relative, expected in before.items():
        source = ROOT/relative
        if source.is_symlink() or not source.resolve().is_relative_to(ROOT):
            raise ValueError('Review input escaped its authorized source boundary: '+relative)
        target = stage/relative; target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        target.chmod(0o600)
        if record(target) != expected:
            raise ValueError('Review input changed during capture: '+relative)
    for source, relative, expected in delivery:
        delivery_input(source, 'Delivery input')
        target = stage/relative; target.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(source, target); target.chmod(0o600)
        if record(source) != expected or record(target) != expected:
            raise ValueError('Delivery input changed during capture.')
    evidence = stage/'evidence'; evidence.mkdir(exist_ok=True)
    baseline = json.loads((stage/'validation/cg4/baseline.json').read_text())
    if not isinstance(baseline.get('head'),str) or not re.fullmatch('[0-9a-f]{40}',baseline['head']):
        raise ValueError('Review baseline must identify an actual recorded Git commit.')
    with (evidence/'tracked-working-tree.patch').open('xb') as stream:
        subprocess.run(['git', 'diff', '--binary', '--no-ext-diff', '--no-textconv', baseline['head'], '--', 'src', 'tests', 'docs', 'constraints',
                        'README.md', 'METHODOLOGY.md', 'pyproject.toml', 'setup.py', '.python-version', '.gitignore'],
                       cwd=ROOT, stdout=stream, check=True)
    final = {name: value for name, value in before.items() if name.startswith(('src/', 'tests/', 'docs/', 'constraints/'))}
    (evidence/'source-final.json').write_text(json.dumps({'files': final,
        'baseline_head': baseline['head'], 'baseline_comparison': {name: 'unchanged' if baseline['files'].get(name) == value else
            'changed_since_baseline' if name in baseline['files'] else 'new_since_baseline' for name, value in final.items()},
        'patch_scope': 'Tracked diff from recorded CG4 baseline in the listed product paths. Required untracked files are delivered separately; this does not attribute every edit to a particular author.'}, indent=2, sort_keys=True)+'\n')
    (evidence/'wheel-runtime-parity.json').write_text(json.dumps(wheel_check, indent=2, sort_keys=True)+'\n')
    (stage/'REVIEW_START_HERE.md').write_text('# CG4 technical-review handoff\n\nStart with validation/cg4/REVIEW_QUICKSTART.md and CG4_IMPLEMENTATION_FINDINGS.md.\n\nArchive integrity is not independent review, resolution of findings, the understanding gate or founder acceptance.\n')
    after = source_inventory()
    if after != {p for p in selected if 'source-capsules.nosync' not in p.parts} or any(record(ROOT/p) != info for p, info in before.items()):
        raise ValueError('Sources/evidence changed while packaging. Preserve this stage and finish active work first.')
    files = {str(p.relative_to(stage)): record(p) for p in sorted(stage.rglob('*')) if p.is_file()}
    (stage/'MANIFEST.json').write_text(json.dumps({'schema_version': 'numek.cg4_review_inventory/1.0', 'files': files,
        'scope': 'Payload hashes; manifest is covered by the external ZIP checksum. Qualification, extraction/installation reproduction, independent review and acceptance are separate.'}, indent=2, sort_keys=True)+'\n')
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(pending, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path in sorted(stage.rglob('*')):
            if path.is_file():
                archive.write(path, str(path.relative_to(stage)))
    pending.chmod(0o600)
    verified = check_zip(pending)
    with pending.open('rb') as stream:
        os.fsync(stream.fileno())
    os.link(pending, output); pending.unlink()  # atomic, no-replace publication
    checksum = record(output)['sha256']
    with output.with_suffix(output.suffix+'.sha256').open('x') as stream:
        stream.write(checksum+'  '+output.name+'\n')
    return {'zip': str(output), 'sha256': checksum, 'inventory': verified,
            'remaining_delivery_checks': ['safe extraction', 'clean installation', 'representative reproduction'],
            'independent_review_performed': False, 'founder_acceptance': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--stage', required=True); parser.add_argument('--out', required=True)
    parser.add_argument('--wheel', required=True); parser.add_argument('--synthetic-backup', required=True)
    args = parser.parse_args(); print(json.dumps(build(args.stage, args.out, args.wheel, args.synthetic_backup), indent=2))
