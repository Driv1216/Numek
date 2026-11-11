"""Fixed fresh-selector qualification sequence; no product execution API.

One panel at a time, at most four independent seed subprocesses per panel.
Acceptance failures stop the sequence and retain the failed panel and audit.
"""
import argparse
import ast
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
import time

from confidenceguard.history_storage import file_lock
from run_locked_qualification import ROOT, snapshot, sha
from summarize_recovery import recover_panel
from summarize_objective import summarize as objective_summary
from summarize_history import summarize as history_summary, recorded_protocol
from summarize_null import summarize as null_summary, joint_diagnostic

BROAD='broad_moderate_and_narrow_severe'


def save(path, value):
    if path.exists():
        if json.loads(path.read_text())!=value:
            raise RuntimeError('Preserve a different prior campaign record: '+str(path))
    else:
        with path.open('x') as stream:
            json.dump(value,stream,indent=2,sort_keys=True,allow_nan=False);stream.write('\n')


def wait_for_completed(paths, timeout=8*3600):
    deadline=time.monotonic()+timeout
    while True:
        present=[p for p in paths if p.is_file()]
        for path in present:
            if json.loads(path.read_text()).get('status')!='completed':
                raise RuntimeError('Failed dependency trial retained: '+str(path))
        if len(present)==len(paths):return
        if time.monotonic()>=deadline:
            raise RuntimeError('Dependency remains incomplete; do not infer untouched evidence or launch replacement trials.')
        time.sleep(15)


def panels(capsule, out):
    protocol=json.loads((capsule/'validation/cg4/qualification_protocol_v3.json').read_text())
    if protocol.get('selection_policy')!='severity_material_excess_support_frontier_v2':
        raise RuntimeError('This sequence is exclusively for the revised selector.')
    tree=ast.parse((capsule/'validation/cg4/qualify_objectives.py').read_text())
    declarations=[node.value for node in tree.body if isinstance(node,ast.Assign)
                  and any(isinstance(t,ast.Name) and t.id=='PANELS' for t in node.targets)]
    if len(declarations)!=1:raise RuntimeError('Missing explicit objective panel declaration.')
    objectives=list(ast.literal_eval(declarations[0]))
    history=recorded_protocol(capsule)
    if history['schema_version']!='numek.cg4_historical_recovery_protocol/1.2':
        raise RuntimeError('Historical selection qualification requires its fresh panel.')
    jobs=[]
    for family in protocol['required_archetypes']:
        if family!=BROAD:
            jobs.append(('recovery',family,'qualify_pipeline.py',['--panel','recovery_qualification','--archetype',family],out/('recovery-'+family)))
    for name in objectives:
        jobs.append(('objective',name,'qualify_objectives.py',[name,'--panel','qualification'],out/('objective-'+name)))
    for name in history['scenarios']:
        jobs.append(('history',name,'qualify_history.py',['--panel','qualification','--scenario',name],out/('history-'+name)))
    for name in ('reduced_full_pipeline_null','default_full_pipeline_null'):
        jobs.append(('null',name,'qualify_pipeline.py',['--panel',name,'--archetype','interaction_without_marginals'],out/name))
    return protocol,jobs


def require_recovery(summary, identity):
    if summary.get('source_identity')!=identity:
        raise RuntimeError('A different source profile cannot qualify the current selector.')
    if summary.get('anchor_criterion_met') is not True:
        raise RuntimeError('Locked recovery target failed. Preserve negative evidence; do not lower the criterion or continue as qualified.')


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--source-identity',required=True)
    parser.add_argument('--broad-directory',required=True);parser.add_argument('--out',required=True);args=parser.parse_args()
    capsule,identity=snapshot(args.source_identity);out=Path(args.out).resolve();out.mkdir(parents=True,exist_ok=True)
    with file_lock(out/'.campaign.lock'):
        broad=Path(args.broad_directory).resolve();protocol,jobs=panels(capsule,out)
        tools=['run_selection_campaign.py','run_locked_qualification.py','summarize_recovery.py','summarize_objective.py','summarize_history.py','summarize_null.py']
        helpers={name:sha(ROOT/'validation/cg4'/name) for name in tools}
        profile={'schema_version':'numek.cg4_fresh_selection_campaign/1.0','source_identity':identity,
                 'source_manifest_sha256':sha(capsule/'source-manifest.json'),'orchestration_sha256':helpers,
                 'broad_directory':str(broad),'jobs':[[kind,name,script,options,str(destination)] for kind,name,script,options,destination in jobs],
                 'workers_per_panel':4,'acceptance':'Original locked targets; stop on an execution, recovery or statistical diagnostic failure. No presumed qualification. Existing broad panel must be completely audited before subsequent work.'}
        save(out/'campaign-profile.json',profile)
        seeds=protocol['seed_panels']['recovery_qualification']
        print(json.dumps({'stage':'waiting_for_existing_broad_panel','source_identity':identity}),flush=True)
        wait_for_completed([broad/f'recovery_qualification-{BROAD}-{seed}.json' for seed in range(seeds['start'],seeds['start']+seeds['count'])])
        summary=recover_panel(broad);save(out/'broad-summary.json',summary);require_recovery(summary,identity)
        completed=[];nulls={}
        for kind,name,script,options,destination in jobs:
            if any(sha(ROOT/'validation/cg4'/n)!=h for n,h in helpers.items()):
                raise RuntimeError('Orchestration changed; preserve the recorded campaign before resuming.')
            print(json.dumps({'stage':'starting_or_resuming','kind':kind,'panel':name,'at':datetime.now(timezone.utc).isoformat()}),flush=True)
            with (out/(destination.name+'.log')).open('ab',buffering=0) as log:
                subprocess.run([sys.executable,'-B',str(ROOT/'validation/cg4/run_locked_qualification.py'),'--source-identity',identity,script,
                                *options,'--workers','4','--out',str(destination)],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,check=True)
            summary={'recovery':recover_panel,'objective':objective_summary,'history':history_summary,'null':null_summary}[kind](destination)
            save(out/(destination.name+'-summary.json'),summary)
            if kind=='null':nulls[name]=summary
            else:require_recovery(summary,identity)
            completed.append(destination.name)
            print(json.dumps({'stage':'panel_audited','panel':name,'scope':'Recorded synthetic profile only; not complete milestone acceptance.'}),flush=True)
        diagnostic=joint_diagnostic(nulls['reduced_full_pipeline_null'],nulls['default_full_pipeline_null'])
        save(out/'joint-null-diagnostic.json',diagnostic)
        if diagnostic['diagnostic_rejections']:raise RuntimeError('Excess-error diagnostic rejected; retain evidence and investigate.')
        save(out/'completion.json',{'panels':completed,'scope':'Fresh automatic-selection recovery/null sequence only. Per-strategy qualification, unresolved approximate inference, controlled resources, final delivery and independent review remain separate.'})


if __name__=='__main__':main()
