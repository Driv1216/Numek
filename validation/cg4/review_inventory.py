"""Check findings references now, and their inclusion in the final ZIP later.

This does not build a review bundle, run qualification, or confer acceptance.
"""
import argparse
import hashlib
import json
from pathlib import Path,PurePosixPath,PureWindowsPath
import posixpath
import re
import stat
import zipfile

ROOT=Path(__file__).resolve().parents[2]
FINDINGS='validation/cg4/CG4_IMPLEMENTATION_FINDINGS.md'


def references(text):
    result=[]
    for target in re.findall(r'\]\(([^)]+)\)',text):
        if '://' in target or target.startswith('#'):continue
        target=target.strip('<>').split('#',1)[0]
        if target.startswith('/'):raise ValueError('Findings must use portable relative references.')
        normalized=posixpath.normpath(posixpath.join(str(PurePosixPath(FINDINGS).parent),target))
        if normalized=='..' or normalized.startswith('../'):raise ValueError('Findings reference escapes the review root.')
        result.append(normalized)
    return sorted(set(result))


def check_workspace():
    doc=ROOT/FINDINGS;links=references(doc.read_text());missing=[]
    for relative in links:
        path=ROOT/relative
        if not path.exists() or path.is_symlink():missing.append(relative)
    if missing:raise ValueError('Missing findings evidence: '+', '.join(missing))
    return {'findings':FINDINGS,'sha256':hashlib.sha256(doc.read_bytes()).hexdigest(),
        'referenced_paths':links,'status':'workspace_references_present',
        'scope':'Reference presence only. Final ZIP inclusion, manifest hashes, reproduction and qualification require their own recorded checks.'}


def safe_archive_path(name,*,directory=False):
    canonical=name[:-1] if directory and name.endswith('/') else name
    if (not canonical or name.startswith('/') or PureWindowsPath(name).drive or ':' in name or '\\' in name
            or '..' in PurePosixPath(name).parts or PurePosixPath(canonical).as_posix()!=canonical
            or any(ord(character)<32 for character in name)):
        raise ValueError('Unsafe or noncanonical review archive path.')


def check_zip(path):
    with zipfile.ZipFile(path) as archive:
        all_entries=archive.infolist()
        for entry in all_entries:
            safe_archive_path(entry.filename,directory=entry.is_dir())
            mode=entry.external_attr>>16;kind=stat.S_IFMT(mode)
            allowed={0,stat.S_IFDIR} if entry.is_dir() else {0,stat.S_IFREG}
            if kind not in allowed or mode&0o7000:raise ValueError('Unsafe review ZIP member type or permissions.')
        entries=[entry for entry in all_entries if not entry.is_dir()];names=[e.filename for e in entries]
        if len(all_entries)!=len({e.filename for e in all_entries}):raise ValueError('Unsafe or duplicate review ZIP paths.')
        file_names=set(names)
        if any(any(str(parent) in file_names for parent in PurePosixPath(name).parents if str(parent)!='.') for name in names):raise ValueError('Archive file is also a parent directory.')
        if sum(e.file_size for e in entries)>64*1024**3:raise ValueError('Review ZIP exceeds the inventory admission ceiling.')
        if 'MANIFEST.json' not in names or FINDINGS not in names:raise ValueError('Review ZIP lacks its manifest or implementation findings.')
        if archive.getinfo('MANIFEST.json').file_size>20*1024**2 or archive.getinfo(FINDINGS).file_size>256*1024:raise ValueError('Review manifest/findings exceed admission.')
        manifest=json.loads(archive.read('MANIFEST.json'));records=manifest['files']
        if set(records)!=set(names)-{'MANIFEST.json'}:raise ValueError('Manifest must cover every review file, including implementation findings.')
        for relative,record in records.items():
            sha=hashlib.sha256();size=0
            with archive.open(relative) as stream:
                while block:=stream.read(1024**2):sha.update(block);size+=len(block)
            if record['bytes']!=size or record['sha256']!=sha.hexdigest():raise ValueError('Review inventory mismatch: '+relative)
        links=references(archive.read(FINDINGS).decode())
        for relative in links:
            if relative not in records and not any(name.startswith(relative.rstrip('/')+'/') for name in records):raise ValueError('Referenced findings evidence absent from ZIP: '+relative)
    return {'status':'zip_inventory_and_findings_references_verified','files':len(records),'findings':FINDINGS,
        'scope':'ZIP contents and hashes only; independent technical review and founder acceptance are separate.'}


def check_extracted(root):
    root=Path(root).resolve();manifest=root/'MANIFEST.json'
    if manifest.is_symlink() or manifest.stat().st_size>20*1024**2:raise ValueError('Invalid extracted manifest.')
    records=json.loads(manifest.read_text())['files']
    names={str(p.relative_to(root)) for p in root.rglob('*') if p.is_file() and p!=manifest}
    if names!=set(records):raise ValueError('Extracted file set differs from the review manifest.')
    for relative,expected in records.items():
        safe_archive_path(relative)
        path=root/relative
        if path.is_symlink() or not path.resolve().is_relative_to(root):raise ValueError('Extracted evidence escaped the review root.')
        with path.open('rb') as stream:actual=hashlib.file_digest(stream,'sha256').hexdigest()
        if path.stat().st_size!=expected['bytes'] or actual!=expected['sha256']:raise ValueError('Extracted inventory mismatch: '+relative)
    if FINDINGS not in records:raise ValueError('Implementation findings are absent.')
    for relative in references((root/FINDINGS).read_text()):
        if relative not in records and not any(name.startswith(relative.rstrip('/')+'/') for name in records):raise ValueError('Referenced findings evidence absent: '+relative)
    return {'status':'extracted_inventory_and_findings_references_verified','files':len(records),
        'scope':'Extracted bytes only. Installation, reproduction, independent review and acceptance are separate.'}


def main():
    parser=argparse.ArgumentParser();group=parser.add_mutually_exclusive_group();group.add_argument('--zip');group.add_argument('--root');args=parser.parse_args()
    print(json.dumps(check_zip(args.zip) if args.zip else check_extracted(args.root) if args.root else check_workspace(),sort_keys=True,indent=2))


if __name__=='__main__':main()
