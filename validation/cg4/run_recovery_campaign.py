"""The four remaining original recovery anchors, serial and source locked."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time

from run_locked_qualification import ROOT,snapshot,sha

FAMILIES=('categorical_numeric_conjunction','rare_failure','overlapping_mechanisms','broad_moderate_and_narrow_severe')


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--source-identity',required=True);parser.add_argument('--out',required=True)
    parser.add_argument('--after-partial-null',action='store_true');args=parser.parse_args()
    capsule,identity=snapshot(args.source_identity);out=Path(args.out).resolve();out.mkdir(parents=True,exist_ok=True)
    profile={'schema_version':'numek.cg4_remaining_recovery_group/1.0','source_identity':identity,
        'source_manifest_sha256':sha(capsule/'source-manifest.json'),'families':list(FAMILIES),'seeds':[100000,100039],
        'scope':'Original 40-seed/default-profile anchors; no threshold/budget changes or presumed qualification. Serial children, failures stop execution, completed evidence is reused.'}
    path=out/'group-profile.json'
    if path.exists() and json.loads(path.read_text())!=profile:raise RuntimeError('Preserve prior group/profile.')
    if not path.exists():path.write_text(json.dumps(profile,indent=2,sort_keys=True)+'\n')
    if args.after_partial_null:
        directory=ROOT/'validation/cg4/results/partial-null-qualification-v1';last=directory/'170999.json'
        print(json.dumps({'stage':'waiting_for_existing_partial_null_slot','dependency':str(last)}),flush=True)
        deadline=time.monotonic()+12*3600
        while time.monotonic()<deadline:
            if last.is_file():
                row=json.loads(last.read_text())
                if row.get('seed')!=170999 or row.get('status')!='completed':raise RuntimeError('Dependency ended in a failed/mismatched trial.')
                for seed in range(170000,171000):
                    prior=json.loads((directory/f'{seed}.json').read_text())
                    if prior.get('seed')!=seed or prior.get('status')!='completed':raise RuntimeError('Dependency is not complete; preserve before continuing.')
                break
            time.sleep(15)
        else:raise RuntimeError('Capacity dependency did not complete; inspect retained evidence before resuming.')
    for family in FAMILIES:
        destination=out/family
        for saved in destination.glob(f'recovery_qualification-{family}-*.json'):
            if json.loads(saved.read_text()).get('status')!='completed':raise RuntimeError('Failed saved trial in archived source; resolve before resuming.')
        print(json.dumps({'family':family,'stage':'starting_or_resuming'}),flush=True)
        with (out/(family+'.log')).open('ab',buffering=0) as log:
            subprocess.run([sys.executable,'-B',str(ROOT/'validation/cg4/run_locked_qualification.py'),'--source-identity',identity,
                'qualify_pipeline.py','--panel','recovery_qualification','--archetype',family,'--out',str(destination)],cwd=ROOT,
                stdout=log,stderr=subprocess.STDOUT,check=True)
        print(json.dumps({'family':family,'stage':'raw_trials_complete','qualification_conclusion':'requires_complete_panel_audit'}),flush=True)


if __name__=='__main__':main()
