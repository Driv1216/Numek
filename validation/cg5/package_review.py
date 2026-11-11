"""CG5 review packaging only: no analytics, installation, acceptance or source edits."""
import argparse,hashlib,io,json,os,posixpath,re,shutil,stat,tempfile,zipfile
from collections import Counter
from pathlib import Path,PurePosixPath,PureWindowsPath
from urllib.parse import unquote
ROOT=Path(__file__).resolve().parents[2]
WORK=ROOT/'validation/cg5/review-packaging-20261104'
FINAL='validation/cg5/results/final-source.json'
ENTRY='REVIEW_START_HERE.md'
SKIP_DIRS={'__pycache__','.git','.pytest_cache','.venv','venv','node_modules','site-packages','.confidenceguard-session'}
SUPERSEDED={'final-20261104','closure-20261104','closure-20261104-v2'}

def sha(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
def info(path):return {'bytes':path.stat().st_size,'sha256':sha(path)}
def safe(name):
    if not name or '\\' in name or ':' in name or name.startswith('/') or PureWindowsPath(name).drive or '..' in PurePosixPath(name).parts or PurePosixPath(name).as_posix()!=name or any(ord(c)<32 for c in name):raise ValueError('Unsafe archive member: '+name)
def regular(path):
    if not stat.S_ISREG(path.lstat().st_mode) or not path.resolve().is_relative_to(ROOT):raise ValueError('Not an owned regular input: '+str(path))
def excluded(relative):
    parts=Path(relative).parts;p=Path(relative)
    if any(n in SKIP_DIRS for n in parts) or p.name=='.DS_Store' or p.suffix in {'.pyc','.pyo','.pending'}:return 'cache_or_environment'
    if any(n.endswith('.nosync') for n in parts):return 'environment_or_local_dependency; source-only capsule exception handled separately'
    if p.name.startswith('.env') or p.suffix.lower() in {'.pem','.key','.p12','.pfx'}:return 'potential_secret_material'
    if p.name.startswith('NUMEK_ConfidenceGuard_') and p.suffix=='.zip':return 'superseded_independent_review_delivery; current source/evidence supplied directly'
    if relative.startswith('validation/cg5/results/') and len(parts)>3:
        if parts[3] in SUPERSEDED:return 'superseded_CG5_scratch_run; governing qualified/final records retained'
        if parts[3]=='browser-host':return 'transient_browser_host_state'
    if relative.startswith('validation/cg5/review-packaging-'):return 'packaging_work_area; explicit generated records handled separately'
    if relative.startswith('src/datatrust.egg-info/'):return 'generated_build_metadata'
    return None

def walk(directory,selected,omitted):
    for base,dirs,files in os.walk(ROOT/directory,followlinks=False):
        base=Path(base);keep=[]
        for name in dirs:
            p=base/name;rel=p.relative_to(ROOT).as_posix();reason=excluded(rel)
            if p.is_symlink():omitted.append({'path':rel,'kind':'directory','reason':'symlink_not_followed'})
            elif reason:omitted.append({'path':rel+'/','kind':'directory','reason':reason})
            else:keep.append(name)
        dirs[:]=keep
        for name in files:
            p=base/name;rel=p.relative_to(ROOT).as_posix();reason=excluded(rel)
            if reason:omitted.append({'path':rel,'kind':'file','reason':reason});continue
            regular(p);selected.add(rel)

def collect():
    selected=set();omitted=[]
    for folder in ('src/confidenceguard','src/datatrust','tests','docs','constraints','validation/cg1','validation/cg2','validation/cg3','validation/cg4','validation/cg5','agents/skills/verify'):walk(folder,selected,omitted)
    for name in ('README.md','METHODOLOGY.md','pyproject.toml','setup.py','.python-version','.gitignore'):
        regular(ROOT/name);selected.add(name)
    # Authored helpers imported by retained host/legacy tests, not their datasets.
    for p in (ROOT/'validation').iterdir():
        if p.is_file() and p.suffix in {'.py','.md','.json'} and not excluded(p.relative_to(ROOT).as_posix()):selected.add(p.relative_to(ROOT).as_posix())
    for folder in [*('m'+str(i) for i in range(1,10)),'unlabeled','ws3','ws4']:
        for base,dirs,files in os.walk(ROOT/'validation'/folder):
            dirs[:]=[n for n in dirs if not excluded((Path(base)/n).relative_to(ROOT).as_posix())]
            for name in files:
                p=Path(base)/name;rel=p.relative_to(ROOT).as_posix()
                if p.suffix in {'.py','.md'} and not excluded(rel):regular(p);selected.add(rel)
    if (ROOT/'validation/unlabeled/known_evidence.csv').is_file():selected.add('validation/unlabeled/known_evidence.csv')
    # Explicit exception: immutable source-only qualification snapshots, never envs.
    capsules=[]
    directory=ROOT/'validation/cg4/source-capsules.nosync'
    for capsule in sorted(directory.iterdir()):
        if not capsule.is_dir() or not re.fullmatch('[0-9a-f]{64}',capsule.name):continue
        manifest=json.loads((capsule/'source-manifest.json').read_text());files=manifest['files']
        if hashlib.sha256(json.dumps(files,sort_keys=True).encode()).hexdigest()!=capsule.name or manifest['source_identity']!=capsule.name:raise ValueError('Historical capsule identity mismatch')
        for name,digest in files.items():
            safe(name);p=capsule/name;regular(p)
            if sha(p)!=digest:raise ValueError('Historical capsule bytes changed: '+str(p))
        for p in capsule.rglob('*'):
            if p.is_file():regular(p);selected.add(p.relative_to(ROOT).as_posix())
        capsules.append(capsule.name)
    # Two synthetic protected fixtures explicitly referenced by prior CG4 receipts.
    import sys
    sys.path.insert(0,str(ROOT/'validation/cg4'))
    from package_review import referenced_synthetic_state
    for p in referenced_synthetic_state(ROOT):regular(p);selected.add(p.relative_to(ROOT).as_posix())
    # Close local Markdown references where the input is admitted. Historical
    # external datasets/old delivery archives remain explicitly classified.
    scanned=set();missing=[]
    while True:
        pending=[n for n in selected if n.endswith('.md') and n not in scanned]
        if not pending:break
        for name in pending:
            scanned.add(name)
            for target in re.findall(r'\]\(([^)]+)\)',(ROOT/name).read_text(errors='replace')):
                target=target.strip('<>').split('#')[0]
                if not target or re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*:',target):continue
                rel=posixpath.normpath(posixpath.join(posixpath.dirname(name),unquote(target)))
                if rel.startswith('../') or rel.startswith('/'):
                    missing.append({'from':name,'target':target,'reason':'historical_nonportable_reference'});continue
                p=ROOT/rel
                if p.is_file() and not excluded(rel):regular(p);selected.add(rel)
    source=json.loads((ROOT/FINAL).read_text());expected=source['final_source_files']
    if hashlib.sha256(json.dumps(expected,sort_keys=True,separators=(',',':')).encode()).hexdigest()!=source['tree_digest']:raise ValueError('Recorded source map digest differs')
    if not set(expected)<=selected:raise ValueError('Verified source file omitted')
    for name,digest in expected.items():
        if sha(ROOT/name)!=digest:raise ValueError('Verified implementation changed: '+name)
    return selected,omitted,capsules

def references(records,read):
    rows=[]
    directories={parent.as_posix() for name in records for parent in PurePosixPath(name).parents}
    attachment_name='review/HISTORICAL_REFERENCE_ATTACHMENTS.json'
    aliases={v['original_reference']:v['archive_path'] for v in json.loads(read(attachment_name)).get('attachments',[])} if attachment_name in records else {}
    for name in sorted(n for n in records if n.endswith('.md')):
        for target in re.findall(r'\]\(([^)]+)\)',read(name).decode(errors='replace')):
            target=target.strip('<>').split('#')[0]
            if not target or re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*:',target):continue
            rel=posixpath.normpath(posixpath.join(posixpath.dirname(name),unquote(target)))
            present=rel in records or rel.rstrip('/') in directories
            mapping=None
            if not present:
                mapped=aliases.get(target)
                if not mapped and target.startswith(str(ROOT)+'/'):mapped=re.sub(r':\d+$','',target[len(str(ROOT))+1:])
                if not mapped and '/verification/' in name and name.endswith('.md'):
                    if target=='CG4_CONFIDENCEGUARD.md':mapped='docs/CG4_CONFIDENCEGUARD.md'
                    elif target.startswith('../validation/'):mapped=target[3:]
                if mapped in records:rel=mapped;present=True;mapping='historical path mapped to included member; historical line annotations are retained, not revalidated'
            rows.append({'from':name,'target':target,'resolved_path':rel,'status':'included' if present else 'historical_reference_outside_payload','mapping':mapping,'reason':None if present else excluded(rel) or ('not_present_in_starting_repository' if not (ROOT/rel).exists() else 'legacy_non_CG5_context_not_redistributed')})
    return rows

def validate_zip(path,extract=True):
    with zipfile.ZipFile(path) as z:
        entries=z.infolist();names=[i.filename for i in entries]
        if len(names)!=len(set(names)):raise ValueError('Duplicate archive entries')
        for e in entries:
            safe(e.filename)
            if e.is_dir() or stat.S_IFMT(e.external_attr>>16) not in {0,stat.S_IFREG}:raise ValueError('Non-regular archive entry')
        manifest=json.loads(z.read('MANIFEST.json'));records=manifest['files']
        if set(names)!=set(records)|{'MANIFEST.json'}:raise ValueError('Manifest coverage mismatch')
        for name,expected in records.items():
            raw=z.read(name)
            if len(raw)!=expected['bytes'] or hashlib.sha256(raw).hexdigest()!=expected['sha256']:raise ValueError('Payload mismatch: '+name)
        if z.testzip() is not None:raise ValueError('CRC failure')
        source=json.loads(z.read(FINAL))
        if hashlib.sha256(json.dumps(source['final_source_files'],sort_keys=True,separators=(',',':')).encode()).hexdigest()!=source['tree_digest']:raise ValueError('Source map digest mismatch')
        for name,digest in source['final_source_files'].items():
            if records[name]['sha256']!=digest:raise ValueError('Verified source mismatch')
        runtime={n:rec for n,rec in records.items() if n.startswith(('src/confidenceguard/','src/datatrust/'))}
        wheel_name='wheel/datatrust-0.1.0-py3-none-any.whl'
        build=json.loads(z.read('wheel/verification.json'))
        if records[wheel_name]['sha256']!=build['verification']['wheel']['sha256']:raise ValueError('Wheel build hash differs')
        with zipfile.ZipFile(io.BytesIO(z.read(wheel_name))) as wheel:
            for name,expected in runtime.items():
                if hashlib.sha256(wheel.read(name[4:])).hexdigest()!=expected['sha256']:raise ValueError('Wheel runtime mismatch: '+name)
        refs=references(set(records)|{'MANIFEST.json'},z.read)
        required_docs={'REVIEW_START_HERE.md','review/ARCHITECTURE_AND_SCRUTINY.md','review/EVIDENCE_GUIDE.md','review/REPRODUCTION.md','review/PACKAGING_SCOPE.md'}
        broken=[r for r in refs if r['from'] in required_docs and r['status']!='included']
        if broken:raise ValueError('Broken review instruction references: '+str(broken[:3]))
        safe_extract=False
        if extract:
            with tempfile.TemporaryDirectory(prefix='numek-cg5-extract-') as tmp:
                root=Path(tmp)
                for name in names:
                    p=root/name;p.parent.mkdir(parents=True,exist_ok=True)
                    with p.open('xb') as f:f.write(z.read(name))
                if {p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()}!=set(names):raise ValueError('Extraction inventory differs')
                for name,expected in records.items():
                    if info(root/name)!=expected:raise ValueError('Extraction hash differs')
                safe_extract=True
        return {'status':'passed','payload_files':len(records),'zip_members':len(names),'uncompressed_bytes':sum(e.file_size for e in entries),'crc':'passed','manifest_coverage':'every payload file; MANIFEST.json covered by external ZIP checksum','verified_source_files':len(source['final_source_files']),'source_tree_digest':source['tree_digest'],'wheel_runtime_files_verified':len(runtime),'review_instruction_references':'all included','historical_reference_exceptions':sum(r['status']!='included' for r in refs),'safe_extraction_verified':safe_extract}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--inventory',action='store_true');parser.add_argument('--stage',type=Path);parser.add_argument('--out',type=Path);parser.add_argument('--verify',type=Path);args=parser.parse_args()
    if args.verify:print(json.dumps(validate_zip(args.verify),indent=2));return
    selected,omitted,capsules=collect()
    if args.inventory:
        WORK.mkdir(exist_ok=True,parents=True)
        inventory={n:info(ROOT/n) for n in sorted(selected)}
        (WORK/'selection.json').write_text(json.dumps({'files':inventory,'excluded':omitted,'historical_source_capsules':capsules},indent=2,sort_keys=True)+'\n')
        print(json.dumps({'files':len(selected),'bytes':sum(v['bytes'] for v in inventory.values()),'capsules':len(capsules),'excluded_boundaries':len(omitted)}));return
    if not args.stage or not args.out:parser.error('Supply --inventory or both --stage and --out')
    stage=args.stage.absolute();output=args.out.absolute();pending=output.with_suffix('.zip.pending')
    if stage.exists() or output.exists() or pending.exists() or output.with_suffix('.zip.sha256').exists():raise ValueError('Use fresh staging/output paths')
    before={n:info(ROOT/n) for n in sorted(selected)};stage.mkdir(mode=0o700,parents=True)
    for name,expected in before.items():
        dest=stage/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,dest);dest.chmod(0o600)
        if info(dest)!=expected:raise ValueError('Input changed during copy: '+name)
    for p in (WORK/'instructions').rglob('*'):
        if p.is_file():
            dest=stage/p.relative_to(WORK/'instructions');dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dest);dest.chmod(0o600)
    for p in (WORK/'wheel').iterdir():
        dest=stage/'wheel'/p.name;dest.parent.mkdir(exist_ok=True);shutil.copyfile(p,dest);dest.chmod(0o600)
    review=stage/'review';review.mkdir(exist_ok=True)
    (review/'PACKAGING_INVENTORY.json').write_text(json.dumps({'schema_version':'numek.cg5_packaging_selection/1.0','captured_repository_files':before,'excluded_boundaries':omitted,'historical_source_capsules':capsules,'source_change_policy':'Packaging only. Production source and completed analytical bytes unchanged.'},indent=2,sort_keys=True)+'\n')
    payload={p.relative_to(stage).as_posix():p for p in stage.rglob('*') if p.is_file()}
    refs=references(set(payload)|{'MANIFEST.json','review/REFERENCES.json'},lambda n:payload[n].read_bytes())
    (review/'REFERENCES.json').write_text(json.dumps({'scope':'All included Markdown local path references; archived historical context may reference excluded old deliveries, model/dataset inputs or pre-existing absent files. Current review instructions must resolve.','references':refs},indent=2)+'\n')
    # Recheck the original capture after all packaging copies and bookkeeping.
    for name,expected in before.items():
        if info(ROOT/name)!=expected:raise ValueError('Repository input changed during capture: '+name)
    records={p.relative_to(stage).as_posix():info(p) for p in sorted(stage.rglob('*')) if p.is_file()}
    (stage/'MANIFEST.json').write_text(json.dumps({'schema_version':'numek.cg5_review_inventory/1.0','files':records,'scope':'Payload bytes and hashes only; external ZIP checksum covers this manifest. No independent acceptance or deployment readiness.'},indent=2,sort_keys=True)+'\n')
    with zipfile.ZipFile(pending,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in sorted(stage.rglob('*')):
            if p.is_file():
                e=zipfile.ZipInfo(p.relative_to(stage).as_posix(),(2026,11,4,0,0,0));e.compress_type=zipfile.ZIP_DEFLATED;e.external_attr=(stat.S_IFREG|0o600)<<16;z.writestr(e,p.read_bytes())
    pending.chmod(0o600);receipt=validate_zip(pending)
    os.link(pending,output);pending.unlink()
    value={'archive':str(output),'filename':output.name,**info(output),'verification':receipt,'analytical_tests_rerun':False,'completed_results_regenerated':False,'production_code_modified':False,'independent_review_performed':False,'independent_acceptance':False}
    output.with_suffix('.zip.sha256').write_text(value['sha256']+'  '+output.name+'\n')
    output.with_suffix('.integrity.json').write_text(json.dumps(value,indent=2,sort_keys=True)+'\n')
    print(json.dumps(value,indent=2))
if __name__=='__main__':main()
