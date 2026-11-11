"""Separate safe extraction, inventory and source/wheel correspondence check."""
from pathlib import Path, PurePosixPath, PureWindowsPath
import argparse,hashlib,json,stat,zipfile

ROOT=Path(__file__).resolve().parents[4]

def sha(path):
 with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--zip',required=True);parser.add_argument('--extract',required=True);parser.add_argument('--out',required=True);args=parser.parse_args()
 archive=Path(args.zip).absolute();extract=Path(args.extract).absolute();receipt=Path(args.out).absolute()
 assert not extract.exists() and not receipt.exists()
 with zipfile.ZipFile(archive) as z:
  entries=z.infolist();names=[e.filename for e in entries];name_set=set(names);assert len(names)==len(name_set)
  assert sum(e.file_size for e in entries)<64*1024**3
  for e in entries:
   name=e.filename;path=PurePosixPath(name)
   assert name and path.as_posix()==name and not path.is_absolute() and '..' not in path.parts
   assert not PureWindowsPath(name).drive and ':' not in name and '\\' not in name and not any(ord(c)<32 for c in name)
   mode=e.external_attr>>16;assert stat.S_IFMT(mode) in {0,stat.S_IFREG} and not mode&0o7000
   assert not any(str(parent) in name_set for parent in path.parents if str(parent)!='.')
  records=json.loads(z.read('MANIFEST.json'))['files'];assert set(records)==set(names)-{'MANIFEST.json'}
  extract.mkdir(mode=0o700)
  compared=0
  for e in entries:
   path=extract/e.filename;path.parent.mkdir(parents=True,exist_ok=True)
   digest=hashlib.sha256();size=0
   with z.open(e) as source,path.open('xb') as dest:
    while chunk:=source.read(1024**2):dest.write(chunk);digest.update(chunk);size+=len(chunk)
   path.chmod(0o600)
   if e.filename=='MANIFEST.json':continue
   assert records[e.filename]=={'bytes':size,'sha256':digest.hexdigest()},e.filename
   current=ROOT/e.filename
   if current.is_file():assert sha(current)==digest.hexdigest(),e.filename;compared+=1
 freeze=json.loads((extract/'validation/cg4/results/review-corrections-20261029/source-freeze.json').read_text());identity=freeze['source_identity']
 manifest=json.loads((extract/'validation/cg4/source-capsules.nosync'/identity/'source-manifest.json').read_text());hashes=manifest['files']
 assert hashlib.sha256(json.dumps(hashes,sort_keys=True).encode()).hexdigest()==identity
 assert all(sha(extract/relative)==h for relative,h in hashes.items())
 runtime={n.removeprefix('src/'):h for n,h in hashes.items() if n.startswith(('src/confidenceguard/','src/datatrust/'))}
 wheel=extract/'wheel/datatrust-0.1.0-py3-none-any.whl'
 with zipfile.ZipFile(wheel) as z:
  assert all(hashlib.sha256(z.read(n)).hexdigest()==h for n,h in runtime.items())
 result={'schema_version':'numek.cg4_corrections_independent_delivery_integrity/1.0','zip':str(archive),'zip_sha256':sha(archive),'zip_bytes':archive.stat().st_size,'manifest_sha256':sha(extract/'MANIFEST.json'),'payloads_verified_and_safely_extracted':len(records),'payloads_compared_with_current_repository':compared,'source_identity':identity,'wheel_sha256':sha(wheel),'runtime_files_matched_zip_source_capsule_and_wheel':len(runtime),'extracted_root':str(extract),'all_passed':True,'independent_technical_rereview':'pending','understanding_gate':'pending','founder_acceptance':False,'scope':'Separate implementation of safe path/type checks, all payload hashes, current repository comparison, source identity and nested wheel parity. Does not confer independent technical review or acceptance.'}
 receipt.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n');print(json.dumps(result,sort_keys=True))

if __name__=='__main__':main()
