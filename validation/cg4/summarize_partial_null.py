"""Audit the complete fixed partial-null panel; never fill or discard trials."""
import argparse
from collections import Counter
from fractions import Fraction
import json
import math
from pathlib import Path

from scipy.stats import binomtest
from run_locked_qualification import ROOT,snapshot,sha


def claim_audit(row):
    """Recompute truth, interval coverage and findings from stored primitives."""
    claims=row['claims'];m=row['actual_family']
    if m!=len(claims) or len({c['hypothesis_id'] for c in claims})!=m:
        raise RuntimeError('Repeated or miscounted frozen hypotheses.')
    family_false=False;family_miss=False
    for claim in claims:
        truth=claim['truth'];effect=None
        if truth is not None:
            if type(truth['numerator']) is not int or type(truth['denominator']) is not int or truth['denominator']<=0:
                raise RuntimeError('Invalid exact population effect.')
            effect=Fraction(truth['numerator'],truth['denominator'])
            if truth['null']!=(effect<=0) or truth['effect']!=float(effect):
                raise RuntimeError('Rational truth status/value disagrees.')
        interval=claim['interval'];miss=False
        if interval is not None:
            lo,hi=interval['lower'],interval['upper']
            if not all(type(v) in {int,float} and math.isfinite(v) for v in (lo,hi)) or lo>hi:
                raise RuntimeError('Invalid interval endpoints.')
            if interval['family_size']!=m or interval['confidence']!=.95 or interval['adjustment']!='bonferroni':
                raise RuntimeError('Frozen family confidence allocation changed.')
            state='confirmed' if lo>0 else 'unreproduced' if hi<=0 else 'inconclusive'
            if state!=claim['state']:raise RuntimeError('Finding state disagrees with interval.')
            miss=effect is not None and not Fraction(lo)<=effect<=Fraction(hi)
        elif claim['state'] not in {'statistically_inadmissible','inconclusive'}:
            raise RuntimeError('A finding lacks an available interval.')
        false=effect is not None and effect<=0 and claim['state']=='confirmed'
        if claim['false_confirmation']!=false or claim['noncoverage']!=miss:
            raise RuntimeError('Claim error/coverage flags disagree with exact truth and interval.')
        family_false|=false;family_miss|=miss
    if row['false_confirmation']!=family_false or row['family_noncoverage']!=family_miss:
        raise RuntimeError('Family error/coverage flags disagree with audited claims.')
    return {'false_confirmation':family_false,'family_noncoverage':family_miss}


def summarize(directory):
    directory=Path(directory).resolve();binding_path=directory.with_name(directory.name+'.source-capsule.json')
    binding=json.loads(binding_path.read_text());args=binding['arguments']
    if binding['script']!='qualify_partial_null.py' or args[args.index('--panel')+1]!='qualification':raise RuntimeError('Only the locked qualification panel is admitted.')
    capsule,identity=snapshot(binding['source_identity'])
    if sha(capsule/'source-manifest.json')!=binding['source_manifest_sha256']:raise RuntimeError('Source binding changed.')
    trials=[];profile=None;groups={1:[],10:[],32:[]}
    for seed in range(170000,171000):
        path=directory/f'{seed}.json';row=json.loads(path.read_text())
        if row['seed']!=seed or row['status']!='completed':raise RuntimeError('Missing or failed trial; preserve it before diagnosis.')
        if profile is None:profile=row['profile']
        if row['profile']!=profile or profile['panel']!='qualification':raise RuntimeError('Mixed qualification profiles.')
        if sha(capsule/'validation/cg4/qualify_partial_null.py')!=profile['harness_sha256']:raise RuntimeError('Harness changed.')
        for name,digest in profile['source_sha256'].items():
            if sha(capsule/name)!=digest:raise RuntimeError('Recorded analytical source differs.')
        expected=(1,10,32)[(seed-170000)%3]
        if row['requested_family']!=expected or row['actual_family']!=len(row['claims']) or row['actual_family']>expected:raise RuntimeError('Family allocation changed.')
        audited=claim_audit(row);false=audited['false_confirmation']
        trial={'seed':seed,'path':str(path.relative_to(ROOT)),'sha256':sha(path),'actual_family':row['actual_family'],
            'false_confirmation':false,'family_noncoverage':audited['family_noncoverage'],
            'null_hypotheses':sum(c['truth'] is not None and c['truth']['null'] for c in row['claims']),
            'alternative_hypotheses':sum(c['truth'] is not None and not c['truth']['null'] for c in row['claims']),
            'undefined_truth':sum(c['truth'] is None for c in row['claims']),
            'assessment_states':dict(Counter(c['state'] for c in row['claims']))}
        groups[expected].append(trial);trials.append(trial)
    diagnostics=[]
    for requested,rows in groups.items():
        failures=sum(r['false_confirmation'] for r in rows);ci=binomtest(failures,len(rows)).proportion_ci(method='exact')
        diagnostics.append({'requested_family':requested,'trials':len(rows),'false_confirmation_families':failures,
            'MC_95_interval':[float(ci.low),float(ci.high)],'diagnostic_p':float(binomtest(failures,len(rows),.05,alternative='greater').pvalue),
            'actual_family_distribution':dict(Counter(r['actual_family'] for r in rows)),
            'all_requested_families_available':all(r['actual_family']==requested for r in rows),
            'null_hypotheses':sum(r['null_hypotheses'] for r in rows),'alternative_hypotheses':sum(r['alternative_hypotheses'] for r in rows),
            'families_with_null_claims':sum(r['null_hypotheses']>0 for r in rows),
            'null_opportunity_qualification':'no_observed_null_claims; this subset does not demonstrate null-claim error control' if not any(r['null_hypotheses'] for r in rows) else 'contains_null_and_alternative_claims',
            'undefined_truth':sum(r['undefined_truth'] for r in rows),'family_noncoverage':sum(r['family_noncoverage'] for r in rows)})
    running=0.
    for rank,index in enumerate(sorted(range(3),key=lambda i:diagnostics[i]['diagnostic_p'])):
        running=max(running,min(1.,diagnostics[index]['diagnostic_p']*(3-rank)));diagnostics[index]['Holm_adjusted_diagnostic_p']=running
    return {'schema_version':'numek.cg4_partial_null_summary/1.0','source_identity':identity,'source_binding_sha256':sha(binding_path),
        'profile':profile,'trials':trials,'diagnostics':diagnostics,
        'diagnostic_rejections':[d['requested_family'] for d in diagnostics if d['Holm_adjusted_diagnostic_p']<.05],
        'scope':'Reduced-profile partial-null D/S/H investigations on the eight-cell population only. Actual frozen families govern inference; smaller actual families do not qualify requested-size operation. Subsets without observed null claims do not demonstrate null-claim error control; their zero family-error count is retained with that limitation, and the diagnostic multiplicity family is not reduced. Overlapping claims are not independent Monte Carlo trials. Non-rejection does not prove control or complete full-product/default-profile qualification.'}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--directory',required=True);parser.add_argument('--out',required=True);args=parser.parse_args()
    result=summarize(args.directory);result['aggregation_source_sha256']=sha(Path(__file__));path=Path(args.out)
    if path.exists() and json.loads(path.read_text())!=result:raise RuntimeError('Preserve different prior summary.')
    if not path.exists():path.write_text(json.dumps(result,indent=2,sort_keys=True,allow_nan=False)+'\n')
    print(json.dumps({k:result[k] for k in ('source_identity','diagnostics','diagnostic_rejections')},sort_keys=True))


if __name__=='__main__':main()
