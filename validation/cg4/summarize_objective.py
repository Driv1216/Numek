"""Verify and aggregate a complete locked objective panel without resimulation."""
import argparse
from collections import Counter
import json
from pathlib import Path

import numpy as np
from scipy.stats import binomtest

from run_locked_qualification import ROOT, snapshot, sha
from summarize_recovery import audit_runner


def summarize(directory):
    directory=Path(directory).resolve();binding_path=directory.with_name(directory.name+'.source-capsule.json')
    binding=json.loads(binding_path.read_text());args=binding['arguments']
    if binding['script']!='qualify_objectives.py' or args[args.index('--panel')+1]!='qualification':
        raise RuntimeError('Only the complete locked objective qualification panel is admitted.')
    capsule,identity=snapshot(binding['source_identity'])
    if sha(capsule/'source-manifest.json')!=binding['source_manifest_sha256']:raise RuntimeError('Source binding changed.')
    objective=args[0];rows=[];profile=None;native_effects=[];states=Counter();strengths=Counter()
    # The approved objective panel fixes these seeds; development and partial
    # campaigns cannot be combined into a new favorable recovery panel.
    first=next(iter(sorted(directory.glob(f'{objective}-*.json'))),None)
    if first is None:raise RuntimeError('No completed objective evidence to audit.')
    version=json.loads(first.read_text())['profile']['protocol']['schema_version']
    if version=='numek.cg4_objective_recovery_protocol/1.0':
        expected_seeds=[280000,280039] if objective=='paired_precision' else [110000,110039]
    elif version=='numek.cg4_objective_recovery_protocol/1.1':
        expected_seeds=[380000,380039] if objective=='paired_precision' else [310000,310039]
    else:raise RuntimeError('Unknown objective qualification protocol.')
    for seed in range(expected_seeds[0],expected_seeds[1]+1):
        path=directory/f'{objective}-{seed}.json';row=json.loads(path.read_text())
        if row['status']!='completed' or row['seed']!=seed or row['objective_panel']!=objective:
            raise RuntimeError('Incomplete or mismatched trial; preserve it before diagnosis.')
        if profile is None:profile=row['profile']
        if row['profile']!=profile or profile['panel']!='qualification':raise RuntimeError('Mixed qualification profiles.')
        if profile['harness_sha256']!=sha(capsule/'validation/cg4/qualify_objectives.py') or profile['base_harness_sha256']!=sha(capsule/'validation/cg4/qualify_pipeline.py'):
            raise RuntimeError('Recorded harness changed.')
        audit_runner(profile,capsule,required=version=='numek.cg4_objective_recovery_protocol/1.1')
        for name,digest in profile['source_sha256'].items():
            if sha(capsule/name)!=digest:raise RuntimeError('Recorded analytical source differs.')
        protocol=profile['protocol'];criterion=protocol['criterion']
        seeds=protocol.get('panel_specific_seed_ranges',{}).get(objective,protocol['qualification_seed_range'])
        if seeds!=expected_seeds or protocol['units']!=40000:raise RuntimeError('Unrecognized locked seed/population panel.')
        if row['objective']['metric']!=protocol['panels'][objective]['metric']:raise RuntimeError('Objective differs from panel.')
        recovery={role:row['recovery'][role]['primary_selected_union'] for role in ('D','S','H')}
        h=recovery['H'];success=h['precision']>=criterion['H_precision'] and h['recall']>=criterion['H_recall']
        if bool(row['anchor_success'])!=bool(success):raise RuntimeError('Stored anchor result contradicts recovery.')
        effects=[]
        for selected in row['recovery']['H']['selected_native_effects']:
            evidence=selected['native_evidence'];value=evidence.get('effect')
            if value is not None:
                if not np.isfinite(value):raise RuntimeError('Nonfinite native effect must retain its value-state semantics.')
                effects.append(float(value));native_effects.append(float(value))
        assessment_states=[a['state'] for a in row['assessments']];states.update(assessment_states)
        strengths.update(a.get('strength','unspecified') for a in row['assessments'])
        rows.append({'seed':seed,'path':str(path.relative_to(ROOT)),'sha256':sha(path),'input_sha256':row['input_sha256'],
                     'recovery':recovery,'success':bool(success),'H_selected_native_effects':effects,
                     'assessment_states':assessment_states,'seconds':row['seconds']})
    successes=sum(r['success'] for r in rows);interval=binomtest(successes,len(rows)).proportion_ci(method='exact')
    return {'schema_version':'numek.cg4_objective_anchor_summary/1.0','objective':objective,
        'source_identity':identity,'source_binding_sha256':sha(binding_path),'protocol':protocol,
        'successes':successes,'success_fraction_MC95':[float(interval.low),float(interval.high)],
        'anchor_criterion_met':successes>=criterion['minimum_successes_of_40'],'trials':rows,
        'role_medians':{role:{metric:float(np.median([r['recovery'][role][metric] for r in rows]))
                            for metric in ('precision','recall','IoU')} for role in ('D','S','H')},
        'H_unavailable':{'total':sum(r['recovery']['H']['unavailable'] for r in rows),
                         'oracle_members':sum(r['recovery']['H']['unavailable_oracle_members'] for r in rows)},
        'H_selected_effect_summary':{'count':len(native_effects),'minimum':min(native_effects) if native_effects else None,
                                     'median':float(np.median(native_effects)) if native_effects else None,
                                     'maximum':max(native_effects) if native_effects else None},
        'assessment_states':dict(states),'assessment_strengths':dict(strengths),
        'scope':'The declared synthetic objective and unified-strategy operating profile only. H measures independently selected frozen gates. Planned membership stays in recovery denominators. Candidate effects overlap and are not independent replicates. No claim for other objectives, individual strategy superiority, external independence verification or milestone completion.'}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--directory',required=True);parser.add_argument('--out',required=True);args=parser.parse_args()
    result=summarize(args.directory);result['aggregation_source_sha256']=sha(Path(__file__))
    path=Path(args.out)
    if path.exists() and json.loads(path.read_text())!=result:raise RuntimeError('Preserve different prior summary.')
    if not path.exists():path.write_text(json.dumps(result,indent=2,sort_keys=True,allow_nan=False)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in {'trials','protocol'}},sort_keys=True))


if __name__=='__main__':main()
