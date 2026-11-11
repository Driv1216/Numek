"""Audit completed complete-null pipelines without replaying their analytics."""
import argparse
from collections import Counter
import json
import math
from pathlib import Path

from scipy.stats import binomtest
from run_locked_qualification import ROOT,snapshot,sha
from summarize_recovery import captured_protocol,audit_runner

PANELS=('reduced_full_pipeline_null','default_full_pipeline_null')


def assessment_audit(row):
    assessments=row['assessments'];m=len(assessments);noncoverage=False;available=0
    if len({a['hypothesis_id'] for a in assessments})!=m:raise RuntimeError('Repeated hypothesis identity in frozen family.')
    for a in assessments:
        objective=a['objective']
        if objective['metric']!='error_rate' or objective['comparator']!='complement' or objective['direction']!='higher' or a['practical_threshold']!=0.:
            raise RuntimeError('Complete-null claim no longer has the locked zero adverse-effect boundary.')
        interval=a.get('interval')
        if interval is None:
            if a['state'] not in {'statistically_inadmissible','inconclusive'}:raise RuntimeError('A finding lacks an available interval.')
            continue
        lower=interval['lower'];upper=interval['upper']
        if not all(math.isfinite(v) for v in (lower,upper)) or lower>upper:raise RuntimeError('Invalid interval endpoints.')
        if interval['family_size']!=m or interval['confidence']!=.95 or interval['adjustment']!='bonferroni':raise RuntimeError('Frozen family allocation differs.')
        inference=a['inference']
        if inference['elementary_intervals']!=2 or not math.isclose(inference['allocated_alpha'],.05/m,rel_tol=1e-12,abs_tol=0.):raise RuntimeError('Component or hypothesis error allocation changed.')
        state='confirmed' if lower>0. else 'unreproduced' if upper<=0. else 'inconclusive'
        if a['state']!=state:raise RuntimeError('Finding state disagrees with its interval.')
        available+=1;noncoverage|=lower>0. or upper<0.
    false=any(a['state']=='confirmed' for a in assessments)
    if bool(row['false_confirmation_under_complete_null'])!=false:raise RuntimeError('Stored family-error flag disagrees with findings.')
    return {'family_size':m,'available_intervals':available,'false_confirmation':false,'family_noncoverage':bool(noncoverage),
        'states':dict(Counter(a['state'] for a in assessments))}


def summarize(directory):
    directory=Path(directory).resolve();binding_path=directory.with_name(directory.name+'.source-capsule.json')
    binding=json.loads(binding_path.read_text());args=binding['arguments']
    if binding['script']!='qualify_pipeline.py':raise RuntimeError('Not a complete pipeline panel.')
    panel=args[args.index('--panel')+1]
    if panel not in PANELS:raise RuntimeError('Only complete-null panels are admitted.')
    archetype=args[args.index('--archetype')+1] if '--archetype' in args else 'interaction_without_marginals'
    capsule,identity=snapshot(binding['source_identity'])
    first=next(iter(sorted(directory.glob(f'{panel}-{archetype}-*.json'))),None)
    if first is None:raise RuntimeError('No completed null evidence to audit.')
    protocol_path=captured_protocol(capsule,json.loads(first.read_text())['profile']['protocol_sha256'])
    if sha(capsule/'source-manifest.json')!=binding['source_manifest_sha256']:raise RuntimeError('Source binding changed.')
    protocol=json.loads(protocol_path.read_text());seed_spec=protocol['seed_panels'][panel];trials=[];profile=None;states=Counter()
    for seed in range(seed_spec['start'],seed_spec['start']+seed_spec['count']):
        path=directory/f'{panel}-{archetype}-{seed}.json';row=json.loads(path.read_text())
        expected_n=1200 if panel==PANELS[0] else 40000
        if row['status']!='completed' or row['seed']!=seed or row['panel']!=panel or row['archetype']!=archetype or row['null'] is not True or row['n']!=expected_n:
            raise RuntimeError('Failed, incomplete or mismatched trial; preserve before diagnosis.')
        if profile is None:
            profile=row['profile']
            if profile['protocol_sha256']!=sha(protocol_path) or profile['harness_sha256']!=sha(capsule/'validation/cg4/qualify_pipeline.py'):raise RuntimeError('Harness/protocol binding changed.')
            audit_runner(profile,capsule,required=protocol_path.name=='qualification_protocol_v3.json')
            for name,digest in profile['source_sha256'].items():
                if sha(capsule/name)!=digest:raise RuntimeError('Recorded analytical source differs.')
        if row['profile']!=profile:raise RuntimeError('Mixed analytical/runtime profiles.')
        audited=assessment_audit(row);states.update(audited['states'])
        trials.append({'seed':seed,'path':str(path.relative_to(ROOT)),'sha256':sha(path),'input_sha256':row['input_sha256'],**audited})
    failures=sum(t['false_confirmation'] for t in trials);ci=binomtest(failures,len(trials)).proportion_ci(method='exact')
    return {'schema_version':'numek.cg4_complete_null_summary/1.0','panel':panel,'archetype':archetype,
        'source_identity':identity,'source_binding_sha256':sha(binding_path),'profile':profile,'expected_seeds':[seed_spec['start'],seed_spec['start']+seed_spec['count']-1],
        'trials':trials,'completed_trials':len(trials),'false_confirmation_families':failures,'false_confirmation_MC95':[float(ci.low),float(ci.high)],
        'unadjusted_excess_error_p':float(binomtest(failures,len(trials),.05,alternative='greater').pvalue),
        'joint_diagnostic_decision':'Requires both complete reduced/default panels and their predeclared Holm adjustment.',
        'family_noncoverage':sum(t['family_noncoverage'] for t in trials),'no_hypothesis_trials':sum(t['family_size']==0 for t in trials),
        'family_size_distribution':dict(Counter(t['family_size'] for t in trials)),'assessment_states':dict(states),
        'scope':'Adaptive D discovery and S selection, followed by frozen independent H finite Bernoulli component intervals at the true zero practical boundary, under the recorded synthetic IID design. Overlapping claims are not independent experiments. This panel alone does not complete the two-panel error diagnostic, establish universal control, qualify bootstrap/dependence or complete the milestone.'}


def joint_diagnostic(reduced,default):
    """The two predeclared complete-null diagnostics, not pooled trials."""
    rows=[]
    starts=(reduced['expected_seeds'][0],default['expected_seeds'][0])
    if starts not in {(130000,140000),(330000,340000)}:
        raise RuntimeError('Do not mix original and revised selection qualification panels.')
    for summary,panel,count,start in ((reduced,PANELS[0],2000,starts[0]),(default,PANELS[1],200,starts[1])):
        if summary['panel']!=panel or summary['completed_trials']!=count or summary['expected_seeds']!=[start,start+count-1]:
            raise RuntimeError('The joint diagnostic requires both complete locked panels.')
        trials=summary['trials']
        if len(trials)!=count or {t['seed'] for t in trials}!=set(range(start,start+count)):
            raise RuntimeError('Missing or repeated seed in a complete-null diagnostic.')
        failures=sum(t['false_confirmation'] for t in trials)
        if failures!=summary['false_confirmation_families']:
            raise RuntimeError('Aggregate error count disagrees with audited trials.')
        ci=binomtest(failures,count).proportion_ci(method='exact')
        rows.append({'panel':panel,'trials':count,'false_confirmation_families':failures,
            'false_confirmation_MC95':[float(ci.low),float(ci.high)],
            'unadjusted_excess_error_p':float(binomtest(failures,count,.05,alternative='greater').pvalue)})
    running=0.
    for rank,index in enumerate(sorted(range(2),key=lambda i:rows[i]['unadjusted_excess_error_p'])):
        running=max(running,min(1.,rows[index]['unadjusted_excess_error_p']*(2-rank)))
        rows[index]['Holm_adjusted_diagnostic_p']=running
    return {'schema_version':'numek.cg4_complete_null_joint_diagnostic/1.0','diagnostics':rows,
        'diagnostic_rejections':[r['panel'] for r in rows if r['Holm_adjusted_diagnostic_p']<.05],
        'scope':'Two predeclared one-sided excess-family-error diagnostics with Holm adjustment. Different pipeline sizes are not pooled; 200 default-profile runs have limited error-rate resolution. Non-rejection is not proof of nominal control or qualification of other assumptions, methods or the milestone.'}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--directory',required=True);parser.add_argument('--default-directory')
    parser.add_argument('--out',required=True);args=parser.parse_args()
    result=summarize(args.directory)
    if args.default_directory:
        default=summarize(args.default_directory)
        diagnostic=joint_diagnostic(result,default)
        result={'reduced':result,'default':default,'joint_diagnostic':diagnostic}
    result['aggregation_source_sha256']=sha(Path(__file__));path=Path(args.out)
    if path.exists() and json.loads(path.read_text())!=result:raise RuntimeError('Preserve different prior summary.')
    if not path.exists():path.write_text(json.dumps(result,indent=2,sort_keys=True,allow_nan=False)+'\n')
    print(json.dumps(result['joint_diagnostic'] if args.default_directory else {k:v for k,v in result.items() if k not in {'profile','trials'}},sort_keys=True))


if __name__=='__main__':main()
