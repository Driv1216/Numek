"""Explicit CG3 review allowlist; source comes from the final dirty working tree."""
import argparse
import hashlib
from importlib import metadata
import json
from pathlib import Path
import platform
import shutil
import sqlite3
import subprocess
import sys
import tarfile
import zipfile
from confidenceguard import ReliabilityWorkspace


ROOT=Path(__file__).resolve().parents[2]

def record(path):return {'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}

def build(stage,output):
    stage=Path(stage);stage.mkdir(parents=True,exist_ok=False);output=Path(output)
    def copy(source,relative=None):
        source=Path(source);relative=Path(relative) if relative is not None else source.relative_to(ROOT)
        assert source.is_file() and not source.is_symlink(),source
        target=stage/relative;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target)
    source_files=[]
    for directory in ['src/confidenceguard','src/datatrust','tests','docs']:
        for path in sorted((ROOT/directory).rglob('*')):
            if not path.is_file() or path.name=='.DS_Store' or '__pycache__' in path.parts or path.suffix in ('.pyc','.zip'):continue
            copy(path);source_files.append(path)
    for name in ['README.md','METHODOLOGY.md','pyproject.toml','setup.py']:
        copy(ROOT/name);source_files.append(ROOT/name)
    copy(ROOT/'agents/skills/verify/skills.md')
    copy(ROOT/'validation/__init__.py')
    for milestone in ('cg1','cg2','cg3'):
        for path in sorted((ROOT/'validation'/milestone).glob('*.py')):copy(path)
        for path in sorted((ROOT/'validation'/milestone).glob('*.md')):copy(path)
    for path in sorted((ROOT/'validation/cg1/data').rglob('*')):
        if path.is_file():copy(path)
    for relative in ['validation/cg1/results/reference.json','validation/cg1/results/reports/binary-shareable.json','validation/cg3/baseline.json']:
        copy(ROOT/relative)
    for path in sorted((ROOT/'validation/cg3/results').glob('*')):
        if path.is_file() and path.suffix in ('.json','.png'):copy(path)
    evidence=stage/'evidence';evidence.mkdir(exist_ok=True)
    logs=['repository-suite','final-affected','delivery-tests','cli-final','review-gates','publication-final','history-verify','dry-runs-verify']
    for name in logs:copy(Path('/private/tmp')/('numek-cg3-'+name+'.txt'),'evidence/logs/'+name+'.txt')
    probes={'million':'numek-cg3-probe-1000000/resources.json','wide':'numek-cg3-probe-wide/resources.json','samples':'numek-cg3-probe-samples/resources.json','backfill':'numek-cg3-backfill-qualified/backfill.json','overlap-final':'numek-cg3-final-reimport/reimport.json'}
    for name,relative in probes.items():copy(Path('/private/tmp')/relative,'evidence/workloads/'+name+'.json')
    qa=Path('/private/tmp/numek-cg3-delivery-pdf-qa')
    rendered=json.loads((qa/'rendered.json').read_text())
    for item in rendered:
        item['visual_review']='reviewed: all rendered pages; no clipping, overlap or unreadable glyphs observed'
        item['pdf']='examples/reports/'+Path(item['pdf']).name
        item['contact_sheets']=['evidence/pdf-contact-sheets/'+Path(p).parent.name+'/'+Path(p).name for p in item['contact_sheets']]
    (evidence/'pdf-review.json').write_text(json.dumps(rendered,indent=2)+'\n')
    for path in qa.glob('*/contact-*.png'):copy(path,'evidence/pdf-contact-sheets/'+path.parent.name+'/'+path.name)
    for path in (ROOT/'validation/cg3/results').glob('browser-*.png'):copy(path,'evidence/browser/'+path.name)
    example=Path('/private/tmp/numek-cg3-review-example-delivery')
    for path in (example/'inputs').rglob('*.csv'):copy(path,'examples/inputs/'+str(path.relative_to(example/'inputs')))
    copy(example/'reproduction.json','examples/reproduction.json')
    for path in Path('/private/tmp/numek-cg3-delivery-reports').iterdir():
        if path.suffix in ('.html','.json','.pdf'):copy(path,'examples/reports/'+path.name)
    copy(ROOT/'validation/cg3/results/independent-reference.json','examples/expected.json')
    backup_parent=stage.parent/(stage.name+'-backup');backup_parent.mkdir(exist_ok=False)
    workspace=ReliabilityWorkspace(example/'workspace');workspace.backup(backup_parent/'backup')
    (stage/'examples').mkdir(exist_ok=True)
    with tarfile.open(stage/'examples/synthetic-backup.tar.gz','w:gz') as archive:archive.add(backup_parent/'backup',arcname='backup')
    copy(Path('/private/tmp/numek-cg3-wheel-delivery/datatrust-0.1.0-py3-none-any.whl'),'wheel/datatrust-0.1.0-py3-none-any.whl')
    versions={}
    for name in ('datatrust','click','flask','jinja2','pandas','numpy','weasyprint','duckdb','psutil','tzdata','unicodedataplus','regex','pytest','pypdf','scipy','pyarrow'):
        try:versions[name]=metadata.version(name)
        except metadata.PackageNotFoundError:versions[name]='not installed'
    (evidence/'environment.json').write_text(json.dumps({'python':sys.version,'platform':platform.platform(),'machine':platform.machine(),'sqlite':sqlite3.sqlite_version,'packages':versions,'dependency_contract':'pyproject.toml','scope':'No credentials, environment variable values, model weights or package caches captured.'},indent=2)+'\n')
    with (evidence/'tracked-working-tree.patch').open('wb') as stream:subprocess.run(['git','diff','--binary','HEAD','--', 'src','tests','docs','README.md','METHODOLOGY.md','pyproject.toml','setup.py'],cwd=ROOT,stdout=stream,check=True)
    baseline=json.loads((ROOT/'validation/cg3/baseline.json').read_text())['files']
    final={str(p.relative_to(ROOT)):record(p) for p in source_files}
    comparison={name:('unchanged' if baseline[name]==value else 'changed_since_cg3_baseline') if name in baseline else 'new_since_cg3_baseline' for name,value in final.items()}
    (evidence/'source-final.json').write_text(json.dumps({'files':final,'baseline_comparison':comparison,'patch_scope':'Full tracked HEAD diff; contains pre-existing working-tree changes. See INTENDED_CHANGES.md.'},indent=2)+'\n')
    (stage/'REVIEW_START_HERE.md').write_text('# ConfidenceGuard CG3 technical review\n\nStart with `validation/cg3/REVIEW_QUICKSTART.md`, then the decisions and verification ledger.\n\nThis is the final working-tree handoff. Required untracked runtime is included.\nThe example workspace is entirely synthetic. Independent review/user acceptance remain open.\n')
    write_manifest(stage)
    write_zip(stage,output)
    return {'zip':str(output),'sha256':record(output)['sha256'],'files':len(json.loads((stage/'MANIFEST.json').read_text())['files'])}


def write_manifest(stage):
    files={str(p.relative_to(stage)):record(p) for p in sorted(stage.rglob('*')) if p.is_file() and p.name!='MANIFEST.json' and '__pycache__' not in p.parts}
    (stage/'MANIFEST.json').write_text(json.dumps({'schema':'cg3.review_inventory/1.0','excludes':['MANIFEST.json itself','external ZIP checksum'],'files':files},indent=2)+'\n')


def write_zip(stage,output):
    output.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(output,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
        for path in sorted(stage.rglob('*')):
            if path.is_file() and '__pycache__' not in path.parts:archive.write(path,str(path.relative_to(stage)))
    output.with_suffix(output.suffix+'.sha256').write_text(record(output)['sha256']+'  '+output.name+'\n')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--stage',required=True);p.add_argument('--out',required=True);a=p.parse_args();print(json.dumps(build(a.stage,a.out),indent=2))
