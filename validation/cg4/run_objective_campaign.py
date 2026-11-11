"""One-shot, serial benchmark groups using the existing locked-source runner.

Validation only: no product queue, scheduler, new learner or method selection.
Each fixed group runs one child at a time and stops on any execution defect.
Completed trial files are verified/reused by the original objective harness.
"""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
import subprocess
import sys

from run_locked_qualification import ROOT,snapshot,sha

GROUPS={'classification':('precision','probability_quality','calibration_bins'),
        'continuous_uncertainty':('regression_bias','regression_tail','uncertainty_coverage','uncertainty_efficiency','paired_degradation'),
        'ranking':('ranking_auc','ranking_ap')}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--group',choices=GROUPS,required=True)
    parser.add_argument('--source-identity',required=True);parser.add_argument('--out',required=True);args=parser.parse_args()
    capsule,identity=snapshot(args.source_identity);directory=Path(args.out).resolve();directory.mkdir(parents=True,exist_ok=True)
    profile={'schema_version':'numek.cg4_objective_serial_group/1.0','group':args.group,
        'objectives':list(GROUPS[args.group]),'source_identity':identity,'source_manifest_sha256':sha(capsule/'source-manifest.json'),
        'objective_harness_sha256':sha(capsule/'validation/cg4/qualify_objectives.py'),
        'runner_sha256':sha(ROOT/'validation/cg4/run_locked_qualification.py'),'group_runner_sha256':sha(Path(__file__)),
        'scope':'Original 40 qualification seeds per objective, unchanged criterion and default profile. Serial fresh child processes; failures stop the group. No automatic promotion or qualification-success assumption.'}
    path=directory/'group-profile.json'
    if path.exists() and json.loads(path.read_text())!=profile:raise RuntimeError('Preserve prior group/source evidence.')
    if not path.exists():path.write_text(json.dumps(profile,indent=2,sort_keys=True)+'\n')
    for objective in GROUPS[args.group]:
        print(json.dumps({'objective':objective,'stage':'starting_or_resuming','at':datetime.now(timezone.utc).isoformat()}),flush=True)
        with (directory/(objective+'.log')).open('ab',buffering=0) as log:
            subprocess.run([sys.executable,'-B',str(ROOT/'validation/cg4/run_locked_qualification.py'),
                '--source-identity',identity,'qualify_objectives.py',objective,'--panel','qualification',
                '--out',str(directory/objective)],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,check=True)
        print(json.dumps({'objective':objective,'stage':'raw_trials_complete','at':datetime.now(timezone.utc).isoformat(),
            'scope':'Source-checked raw completion only; complete-panel aggregation and qualification conclusions remain separate.'}),flush=True)


if __name__=='__main__':main()
