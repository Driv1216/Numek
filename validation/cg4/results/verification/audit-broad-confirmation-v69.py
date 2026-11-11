"""Read-only native-count/public-SciPy reference for the completed fresh panel."""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import sys

import numpy as np
from scipy.stats import binomtest

ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT/'validation/cg4'))
from summarize_baselines import recovery_audit


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--directory',required=True);parser.add_argument('--out',required=True)
    args=parser.parse_args();directory=Path(args.directory).resolve();rows=[];states=Counter();errors=[]
    for seed in range(300000,300040):
        path=directory/f'recovery_qualification-broad_moderate_and_narrow_severe-{seed}.json'
        trial=json.loads(path.read_text());assert trial['status']=='completed' and trial['seed']==seed
        for role in ('D','S','H'):recovery_audit(trial['recovery'][role]['primary_selected_union'])
        family=trial['assessments'];m=len(family);effects=[]
        assert {a['candidate_id'] for a in family}==set(trial['shortlist'])
        for claim in family:
            objective=claim['objective']
            assert objective['metric']=='error_rate' and objective['comparator']=='complement' and objective['direction']=='higher'
            assert claim['practical_threshold']==.15 and claim['strength']=='finite_sample'
            arms=[];points=[]
            for key in ('member_metric','comparator_metric'):
                metric=claim[key];measurement=metric['measurement'];correct,wrong=measurement['sensitive_counts'];n=correct+wrong
                assert measurement['metric']=='accuracy' and n==metric['support']==measurement['denominator'] and n>0
                assert math.isclose(metric['value'],wrong/n,abs_tol=1e-14)
                points.append(wrong/n)
                interval=binomtest(wrong,n).proportion_ci(confidence_level=1-.05/(m*2),method='exact')
                arms.append((float(interval.low),float(interval.high)))
            effect=points[0]-points[1];assert math.isclose(claim['effect'],effect,abs_tol=1e-14)
            lo=arms[0][0]-arms[1][1];hi=arms[0][1]-arms[1][0];stored=claim['interval']
            assert stored['confidence']==.95 and stored['family_size']==m and stored['adjustment']=='bonferroni'
            error=max(abs(stored['lower']-lo),abs(stored['upper']-hi));errors.append(error)
            assert error<=5e-11
            state='confirmed' if lo>.15 else 'unreproduced' if hi<=.15 else 'inconclusive'
            assert state==claim['state'];states[state]+=1;effects.append(effect)
        rows.append({'seed':seed,'path':str(path.relative_to(ROOT)),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                     'family_size':m,'H_native_effects':effects})
    result={'schema_version':'numek.cg4_native_confirmation_reference/1.0','trials':rows,'claims':sum(states.values()),
            'states':dict(states),'maximum_interval_reference_difference':max(errors),'reference_tolerance':5e-11,
            'H_effect_median':float(np.median([e for row in rows for e in row['H_native_effects']])),
            'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'scope':'Existing 40 fresh broad/narrow trials only. Native error counts and independent public SciPy Clopper–Pearson component composition agree with stored effects, family allocation, intervals and finding states. No new observations, discovery, selection or qualification simulation; no general bootstrap/strategy guarantee.'}
    with Path(args.out).open('x') as stream:json.dump(result,stream,indent=2,sort_keys=True);stream.write('\n')
    print(json.dumps({k:v for k,v in result.items() if k!='trials'},sort_keys=True))


if __name__=='__main__':main()
