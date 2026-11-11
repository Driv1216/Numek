"""Audit one complete fixed comparison family; preserve unfavorable results."""
import argparse
import json
import math
from pathlib import Path

import numpy as np

from compare_baselines import PROTOCOL,paired_gain_interval
from run_locked_qualification import ROOT,snapshot,sha


def recovery_audit(value):
    keys=('true_positive','false_positive','false_negative','planned','unavailable','unavailable_oracle_members')
    if any(type(value[k]) is not int or value[k]<0 for k in keys):raise RuntimeError('Invalid recovery counts.')
    tp,fp,fn=(value[k] for k in keys[:3]);n=value['planned']
    if tp+fp+fn>n or value['unavailable']>n-tp-fp or value['unavailable_oracle_members']>min(fn,value['unavailable']):
        raise RuntimeError('Recovery or unavailable-membership counts contradict planned support.')
    reference={'precision':tp/(tp+fp) if tp+fp else 0.,'recall':tp/(tp+fn) if tp+fn else 0.,'IoU':tp/(tp+fp+fn) if tp+fp+fn else 1.}
    if any(not math.isclose(value[k],v,rel_tol=1e-12,abs_tol=1e-15) for k,v in reference.items()):
        raise RuntimeError('Stored recovery differs from independently recomputed counts.')


def summarize(directory):
    directory=Path(directory).resolve();binding_path=directory.with_name(directory.name+'.source-capsule.json')
    binding=json.loads(binding_path.read_text());args=binding['arguments']
    if binding['script']!='compare_baselines.py' or args[args.index('--panel')+1]!='qualification':raise RuntimeError('Only a locked qualification family is admitted.')
    family=args[args.index('--family')+1];capsule,identity=snapshot(binding['source_identity'])
    if family not in PROTOCOL['families'] or sha(capsule/'source-manifest.json')!=binding['source_manifest_sha256']:raise RuntimeError('Family/source binding changed.')
    if sha(capsule/'validation/cg4/compare_baselines.py')!=sha(ROOT/'validation/cg4/compare_baselines.py'):
        raise RuntimeError('Recorded comparison/uncertainty helpers changed; review before aggregation.')
    trials=[];profile=None;methods=PROTOCOL['methods'];measurements={m:[] for m in methods};secondary=[]
    first,last=PROTOCOL['seeds']['qualification']
    for seed in range(first,last+1):
        path=directory/f'{seed}.json';row=json.loads(path.read_text())
        if row['status']!='completed' or row['seed']!=seed or row['family']!=family or row['n']!=PROTOCOL['qualification_units'] or row['formal_confirmation_performed'] is not False:
            raise RuntimeError('Failed, incomplete or mismatched comparison; preserve before diagnosis.')
        if profile is None:profile=row['profile']
        if row['profile']!=profile or profile['protocol']!=PROTOCOL or profile['panel']!='qualification' or profile['full_profile'] is not False:
            raise RuntimeError('Mixed or altered fixed comparison profiles.')
        if profile['harness_sha256']!=sha(capsule/'validation/cg4/compare_baselines.py') or profile['base_harness_sha256']!=sha(capsule/'validation/cg4/qualify_pipeline.py'):
            raise RuntimeError('Recorded harness differs.')
        for name,digest in profile['source_sha256'].items():
            if sha(capsule/name)!=digest:raise RuntimeError('Recorded analytical source differs.')
        comparison=row['comparison']
        if comparison['native_first_S_recomputed_equal'] is not True:raise RuntimeError('Native S reference parity failed.')
        expected=set(methods)|{'native_full_shortlist_secondary'}
        if set(comparison['measurements'])!=expected:raise RuntimeError('Missing or extra method in the fixed comparison.')
        for method in methods:
            roles=comparison['measurements'][method]
            for role in ('D','S','H'):recovery_audit(roles[role]['recovery'])
            measurements[method].append(roles)
        recovery_audit(comparison['measurements']['native_full_shortlist_secondary'])
        secondary.append(comparison['measurements']['native_full_shortlist_secondary'])
        trials.append({'seed':seed,'path':str(path.relative_to(ROOT)),'sha256':sha(path),
            'input_sha256':row['input_sha256'],'baseline_execution':row['baseline_execution'],'native_execution':row['native_execution'],
            'method_times':comparison['method_times'],'frozen_artifact_digests':comparison['frozen_artifact_digests']})
    medians={m:{role:{metric:float(np.median([r[role]['recovery'][metric] for r in measurements[m]]))
        for metric in ('precision','recall','IoU')} for role in ('D','S','H')} for m in methods}
    comparisons=[]
    for method in methods[1:]:
        gains=[native['H']['recovery']['IoU']-baseline['H']['recovery']['IoU'] for native,baseline in zip(measurements['native_unified'],measurements[method])]
        comparisons.append({'baseline':method,'paired_H_IoU_gain':paired_gain_interval(gains),
            'native_higher_IoU_seeds':sum(g>0 for g in gains),'equal_IoU_seeds':sum(g==0 for g in gains),
            'native_lower_IoU_seeds':sum(g<0 for g in gains)})
    return {'schema_version':'numek.cg4_fixed_baseline_family_summary/1.0','family':family,'source_identity':identity,
        'source_binding_sha256':sha(binding_path),'profile':profile,'trials':trials,'completed_pairs':len(trials),
        'primary_one_gate_role_medians':medians,'paired_comparisons':comparisons,
        'H_unavailable':{m:{'total':sum(r['H']['recovery']['unavailable'] for r in measurements[m]),
            'oracle_members':sum(r['H']['recovery']['unavailable_oracle_members'] for r in measurements[m])} for m in methods},
        'native_full_shortlist_secondary_H_medians':{metric:float(np.median([r[metric] for r in secondary])) for metric in ('precision','recall','IoU')},
        'simultaneous_comparison_family':{'planned_families':PROTOCOL['families'],'contrasts_per_family':5,'total_contrasts':20,'error_per_interval':.05/20},
        'scope':'One complete40-pair family, with fixed D proposals and shared native S one-gate selection, independent H measurement and predeclared20-contrast median interval allocation. Native full-shortlist union is secondary, never substituted for the one-gate comparison. Negative differences remain evidence; no presumed superiority, universal recovery or controlled concurrent-host efficiency claim. This does not complete the other three comparison families or the milestone.'}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--directory',required=True);parser.add_argument('--out',required=True);args=parser.parse_args()
    result=summarize(args.directory);result['aggregation_source_sha256']=sha(Path(__file__))
    with Path(args.out).open('x') as stream:json.dump(result,stream,indent=2,sort_keys=True,allow_nan=False);stream.write('\n')
    print(json.dumps({k:v for k,v in result.items() if k not in {'trials','profile'}},sort_keys=True))


if __name__=='__main__':main()
