"""Resume an unchanged objective group after a runner allowlist-only addition.

Keep original group metadata. Record the control-layer transition separately;
analytical source, child arguments, runtime, seeds and budgets remain pinned.
"""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from run_locked_qualification import ROOT,snapshot,sha
from run_objective_campaign import GROUPS


def allowlist_only_transition(before,after):
    def body(source):
        tree=ast.parse(source);removed=[];kept=[]
        for node in tree.body:
            if isinstance(node,ast.Assign) and len(node.targets)==1 and isinstance(node.targets[0],ast.Name) and node.targets[0].id=='SCRIPTS':
                removed.append(ast.literal_eval(node.value))
            else:kept.append(node)
        if len(removed)!=1 or not isinstance(removed[0],tuple) or not all(isinstance(s,str) for s in removed[0]):raise RuntimeError('Runner allowlist is not a fixed tuple.')
        tree.body=kept
        return ast.dump(tree,include_attributes=False),set(removed[0])
    left,old=body(before);right,new=body(after)
    if left!=right or not old<=new:raise RuntimeError('Runner changed beyond an additive benchmark allowlist; inspect before resuming.')
    return sorted(new-old)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--out',required=True);args=parser.parse_args()
    out=Path(args.out).resolve();path=out/'group-profile.json';prior=json.loads(path.read_text())
    if prior['group'] not in GROUPS or prior['objectives']!=list(GROUPS[prior['group']]):raise RuntimeError('Group objectives changed.')
    for objective in prior['objectives']:
        for saved in (out/objective).glob(objective+'-*.json'):
            if json.loads(saved.read_text()).get('status')!='completed':raise RuntimeError('Failed saved trial in pinned legacy campaign; resolve before resuming any objective.')
    capsule,identity=snapshot(prior['source_identity'])
    if prior['source_manifest_sha256']!=sha(capsule/'source-manifest.json') or prior['objective_harness_sha256']!=sha(capsule/'validation/cg4/qualify_objectives.py'):
        raise RuntimeError('Analytical campaign changed.')
    if prior['group_runner_sha256']!=sha(ROOT/'validation/cg4/run_objective_campaign.py'):raise RuntimeError('Original serial group runner changed.')
    original=None
    for manifest in sorted((ROOT/'validation/cg4/source-capsules.nosync').glob('*/source-manifest.json')):
        record=json.loads(manifest.read_text())
        if record['files'].get('validation/cg4/run_locked_qualification.py')==prior['runner_sha256']:
            source,_=snapshot(record['source_identity']);original=source/'validation/cg4/run_locked_qualification.py';break
    if original is None:raise RuntimeError('Original control source is unavailable; preserve prior metadata.')
    current=ROOT/'validation/cg4/run_locked_qualification.py'
    added=allowlist_only_transition(original.read_text(),current.read_text())
    record={'schema_version':'numek.cg4_control_resumption/1.0','original_group_profile_sha256':sha(path),
        'source_identity':identity,'old_runner_sha256':sha(original),'new_runner_sha256':sha(current),
        'original_runner':str(original.relative_to(ROOT)),'added_benchmark_names':added,'resumption_runner_sha256':sha(Path(__file__)),
        'scope':'Control allowlist additions only. Original group metadata and every analytical source/seed/profile/child binding remain unchanged. Completed trials are validated and reused.'}
    token=hashlib.sha256(json.dumps(record,sort_keys=True).encode()).hexdigest()[:16]
    transition=out/f'control-resumption-{token}.json'
    if transition.exists() and json.loads(transition.read_text())!=record:raise RuntimeError('Preserve earlier control transition.')
    if not transition.exists():transition.write_text(json.dumps(record,indent=2,sort_keys=True)+'\n')
    for objective in prior['objectives']:
        print(json.dumps({'objective':objective,'stage':'starting_or_resuming','source_identity':identity}),flush=True)
        with (out/(objective+'.log')).open('ab',buffering=0) as log:
            subprocess.run([sys.executable,'-B',str(current),'--source-identity',identity,'qualify_objectives.py',objective,
                '--panel','qualification','--out',str(out/objective)],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,check=True)
        print(json.dumps({'objective':objective,'stage':'raw_trials_complete','qualification_conclusion':'requires_complete_panel_audit'}),flush=True)


if __name__=='__main__':main()
