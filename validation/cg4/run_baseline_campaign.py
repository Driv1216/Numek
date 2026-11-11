"""One fixed serial comparison panel; child source/profile bindings are authoritative."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

from run_locked_qualification import ROOT,snapshot,sha
from compare_baselines import PROTOCOL


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--source-identity',required=True);parser.add_argument('--out',required=True);args=parser.parse_args()
    capsule,identity=snapshot(args.source_identity);out=Path(args.out).resolve();out.mkdir(parents=True,exist_ok=True)
    profile={'schema_version':'numek.cg4_baseline_serial_group/1.0','source_identity':identity,
        'source_manifest_sha256':sha(capsule/'source-manifest.json'),'comparison_harness_sha256':sha(capsule/'validation/cg4/compare_baselines.py'),
        'families':PROTOCOL['families'],'seeds':PROTOCOL['seeds']['qualification'],
        'scope':'160 fresh full-size comparisons, one child at a time; fixed one-gate S selection, no H/oracle tuning or presumed superiority. Completion requires separate complete-panel/source/uncertainty audits.'}
    path=out/'group-profile.json'
    if path.exists() and json.loads(path.read_text())!=profile:raise RuntimeError('Preserve prior group/profile.')
    if not path.exists():path.write_text(json.dumps(profile,indent=2,sort_keys=True)+'\n')
    # Record control bytes separately from immutable analytical identities.
    control={'controller_sha256':sha(Path(__file__)),'runner_sha256':sha(ROOT/'validation/cg4/run_locked_qualification.py'),'source_identity':identity}
    import hashlib
    token=hashlib.sha256(json.dumps(control,sort_keys=True).encode()).hexdigest()[:16]
    record=out/f'control-{token}.json'
    if not record.exists():record.write_text(json.dumps(control,indent=2,sort_keys=True)+'\n')
    for family in profile['families']:
        print(json.dumps({'family':family,'stage':'starting_or_resuming'}),flush=True)
        with (out/(family+'.log')).open('ab',buffering=0) as log:
            subprocess.run([sys.executable,'-B',str(ROOT/'validation/cg4/run_locked_qualification.py'),'--source-identity',identity,
                'compare_baselines.py','--panel','qualification','--family',family,'--count','40','--out',str(out/family)],cwd=ROOT,
                stdout=log,stderr=subprocess.STDOUT,check=True)
        print(json.dumps({'family':family,'stage':'raw_trials_complete','qualification_conclusion':'requires_complete_panel_audit'}),flush=True)


if __name__=='__main__':main()
