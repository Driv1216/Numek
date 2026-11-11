"""Complete the original geometric-only panel using every valid prefix trial."""
import json
from pathlib import Path
import numpy as np
from scipy.stats import binomtest

from run_locked_qualification import ROOT,snapshot,sha


def main():
    root=ROOT/'validation/cg4/results';plan_path=root/'geometric-curved-reuse-plan-v1.json';plan=json.loads(plan_path.read_text())
    capsule,identity=snapshot(plan['source_identity']);protocol_path=capsule/'validation/cg4/qualification_protocol_v2.json'
    protocol=json.loads(protocol_path.read_text());anchor=protocol['strong_signal_anchor']
    assert plan['expected_seeds']==[100000,100039]
    assert plan['unchanged_criterion']=={'H_precision':anchor['required_precision'],'H_recall':anchor['required_recall'],'required_successes':anchor['required_successes_of_40']}
    bindings=[]
    for name in ('landmark-matched-comparison-v1','geometric-curved-remainder-v1'):
        path=root/(name+'.source-capsule.json');binding=json.loads(path.read_text())
        if binding['source_identity']!=identity or binding['source_manifest_sha256']!=sha(capsule/'source-manifest.json'):raise RuntimeError('Source reuse boundary differs.')
        bindings.append({'path':str(path.relative_to(ROOT)),'sha256':sha(path)})
    comparison=json.loads((root/'landmark-matched-comparison-v1/summary.json').read_text())
    if comparison['status']!='promotion_rejected_logical_futility' or len(comparison['families'][0]['pairs'])!=21:raise RuntimeError('The original deterministic prefix differs.')
    rows=[];profile=None;limits=config=None
    for seed in range(100000,100040):
        part=plan['existing_trials'] if seed<=100020 else plan['remaining_trials']
        path=ROOT/part['directory']/part['filename'].format(seed=seed);row=json.loads(path.read_text())
        if seed<=100020 and sha(path)!=comparison['trial_manifest'][path.name]:raise RuntimeError('Existing prefix trial changed.')
        if row['status']!='completed' or row['seed']!=seed or row['panel']!='recovery_qualification' or row['archetype']!='curved_region' or row['null'] or row['strategies']!=['geometric'] or row['n']!=anchor['independent_units']:raise RuntimeError('Incomplete or incompatible original geometric trial.')
        if profile is None:profile=row['profile'];limits=row['admitted_limits'];config=row['admitted_config']
        if row['profile']!=profile or row['admitted_limits']!=limits or row['admitted_config']!=config:raise RuntimeError('Mixed analytical/runtime/admission profiles cannot be silently combined.')
        if profile['protocol_sha256']!=sha(protocol_path) or profile['harness_sha256']!=sha(capsule/'validation/cg4/qualify_pipeline.py'):raise RuntimeError('Recorded protocol/harness differs.')
        for name,digest in profile['source_sha256'].items():
            if sha(capsule/name)!=digest:raise RuntimeError('Recorded analytical source changed.')
        recovery={role:row['recovery'][role]['primary_selected_union'] for role in ('D','S','H')};h=recovery['H']
        rows.append({'seed':seed,'path':str(path.relative_to(ROOT)),'sha256':sha(path),'input_sha256':row['input_sha256'],
            'recovery':recovery,'success':bool(h['precision']>=anchor['required_precision'] and h['recall']>=anchor['required_recall']),
            'seconds':row['seconds'],'assessment_states':[a['state'] for a in row['assessments']]})
    successes=sum(r['success'] for r in rows);ci=binomtest(successes,len(rows)).proportion_ci(method='exact')
    result={'schema_version':'numek.cg4_geometric_recovery_reuse_summary/1.0','source_identity':identity,'source_bindings':bindings,
        'reuse_plan_sha256':sha(plan_path),'aggregation_source_sha256':sha(Path(__file__)),'protocol_sha256':sha(protocol_path),
        'strategy':'geometric','archetype':'curved_region','expected_seeds':[100000,100039],'trials':rows,
        'successes':successes,'required_successes':anchor['required_successes_of_40'],
        'success_fraction_MC95':[float(ci.low),float(ci.high)],'anchor_criterion_met':bool(successes>=anchor['required_successes_of_40']),
        'role_medians':{role:{metric:float(np.median([r['recovery'][role][metric] for r in rows])) for metric in ('precision','recall','IoU')} for role in ('D','S','H')},
        'H_unavailable':{'total':sum(r['recovery']['H']['unavailable'] for r in rows),'oracle_members':sum(r['recovery']['H']['unavailable_oracle_members'] for r in rows)},
        'admitted_limits':limits,'admitted_config':config,
        'scope':'All 40 original seeds, geometric-only D proposals and unchanged native S selection; every first-21 fallback trial retained after landmark logical futility, only 19 missing trials executed. This is one objective/archetype operating envelope, not a complete method/milestone, landmark promotion, controlled efficiency comparison or universal recovery guarantee.'}
    path=root/'geometric-curved-summary-v1.json'
    if path.exists() and json.loads(path.read_text())!=result:raise RuntimeError('Preserve prior summary.')
    if not path.exists():path.write_text(json.dumps(result,indent=2,sort_keys=True,allow_nan=False)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in {'trials','admitted_limits','admitted_config'}},sort_keys=True))


if __name__=='__main__':main()
