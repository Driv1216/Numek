"""Independent byte correspondence audit, without using package/build verification helpers."""
from pathlib import Path
import argparse, hashlib, json, zipfile

ROOT=Path(__file__).resolve().parents[4]
EVIDENCE=Path(__file__).resolve().parent

def sha(path):
 with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()

def main():
 p=argparse.ArgumentParser();p.add_argument('--wheel',required=True);p.add_argument('--installed-site',required=True);p.add_argument('--out',required=True);args=p.parse_args()
 freeze=json.loads((EVIDENCE/'source-freeze.json').read_text());identity=freeze['source_identity']
 capsule=ROOT/'validation/cg4/source-capsules.nosync'/identity
 manifest=json.loads((capsule/'source-manifest.json').read_text());hashes=manifest['files']
 assert hashlib.sha256(json.dumps(hashes,sort_keys=True).encode()).hexdigest()==identity==manifest['source_identity']
 assert all(sha(ROOT/relative)==expected==sha(capsule/relative) for relative,expected in hashes.items())
 runtime={n.removeprefix('src/'):h for n,h in hashes.items() if n.startswith(('src/confidenceguard/','src/datatrust/'))}
 wheel=Path(args.wheel).resolve();site=Path(args.installed_site)
 with zipfile.ZipFile(wheel) as archive:
  names=archive.namelist();assert len(names)==len(set(names))
  for name,expected in runtime.items():assert hashlib.sha256(archive.read(name)).hexdigest()==expected==sha(site/name),name
 old=ROOT/'validation/cg4/source-capsules.nosync'/freeze['previous_reviewed_source'];before=json.loads((old/'source-manifest.json').read_text())['files']
 changed=[n for n,h in hashes.items() if n.startswith('src/') and before.get(n)!=h]
 allowed={'src/confidenceguard/'+n for n in ('features.py','investigation.py','investigation_history.py','investigation_replay.py','evidence_use.py','confirmation.py','transport.py','discovery_rules.py','static/investigation-client.js','static/client.css')}
 assert set(changed)==allowed,(changed,allowed)
 docs=(ROOT/'docs/CG4_CONFIDENCEGUARD.md').read_text();current=(ROOT/'docs/CURRENT_STATE.md').read_text()
 assert 'General AUC/AP percentile confirmation is refused before H metrics' in docs
 assert 'Independent review, findings review, founder-authorized corrections, focused\ncorrection verification, the understanding gate and founder acceptance follow later.' not in docs
 assert 'Targeted independent re-review' in docs and identity in current and 'founder acceptance remain pending' in current
 result={'source_identity':identity,'wheel_sha256':sha(wheel),'runtime_files_verified_source_capsule_wheel_installed':len(runtime),'all_capsule_sources_match_current':True,'changed_runtime_files':sorted(changed),'documentation_current_scope_checks':True,'scientific_reuse_receipt':'reuse-audit.json','scope':'Independent implementation of SHA-256 comparisons; no package builder/helper reused. Byte correspondence and bounded file scope are not independent scientific review or founder acceptance.','acceptance':False}
 target=Path(args.out);assert not target.exists();target.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n');print(json.dumps(result,sort_keys=True))

if __name__=='__main__':main()
