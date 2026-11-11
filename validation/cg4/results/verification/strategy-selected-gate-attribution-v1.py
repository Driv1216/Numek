"""Post-hoc read-only attribution; no new recovery acceptance/promotion rule.

Use the first gate of each strategy in the *recorded S shortlist order*. Never
choose an oracle-best H gate. Other strategies still influence reconciliation,
so this cannot substitute for isolated-method or matched-baseline qualification.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

import numpy as np

ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT/'validation/cg4'))
from summarize_baselines import recovery_audit

PANELS=('recovery-interaction-summary-v1.json','recovery-parity-summary-v1.json',
        'recovery-categorical-numeric-summary-v1.json','recovery-high-dim-summary-v1.json')


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--out',required=True);args=parser.parse_args()
    results=[]
    for name in PANELS:
        path=ROOT/'validation/cg4/results'/name;panel=json.loads(path.read_text());trials=[]
        if len(panel['trials'])!=40:raise ValueError('Only a previously audited complete panel is admitted.')
        for trial in panel['trials']:
            raw_path=ROOT/trial['path']
            if sha(raw_path)!=trial['sha256']:raise ValueError('A previously audited trial changed.')
            row=json.loads(raw_path.read_text());ordered=row['shortlist'];roles={}
            if len(set(ordered))!=len(ordered):raise ValueError('Duplicated selected identity.')
            for role in ('D','S','H'):
                gates=row['recovery'][role]['selected_candidates']
                if len(gates)!=len(ordered) or {g['candidate_id'] for g in gates}!=set(ordered):raise ValueError('Incomplete selected gates.')
                roles[role]={g['candidate_id']:g for g in gates}
                for gate in gates:recovery_audit(gate)
            choices={}
            for cid in ordered:
                strategy=roles['S'][cid]['strategy']
                if any(roles[role][cid]['strategy']!=strategy for role in ('D','H')):raise ValueError('Strategy attribution changed.')
                if strategy not in choices:
                    choices[strategy]={'candidate_id':cid,'recovery':{role:{k:roles[role][cid][k] for k in
                        ('precision','recall','IoU','planned','unavailable','unavailable_oracle_members')} for role in ('D','S','H')}}
            trials.append({'seed':row['seed'],'path':trial['path'],'sha256':trial['sha256'],'first_S_selected_per_strategy':choices})
        strategies=sorted({s for t in trials for s in t['first_S_selected_per_strategy']})
        summaries={}
        for strategy in strategies:
            selected=[t['first_S_selected_per_strategy'][strategy] for t in trials if strategy in t['first_S_selected_per_strategy']]
            summaries[strategy]={'selected_in_trials':len(selected),'all_trial_denominator':40,
                'no_selected_gate_seeds':[t['seed'] for t in trials if strategy not in t['first_S_selected_per_strategy']],
                'conditional_on_selected_role_medians':{role:{k:float(np.median([r['recovery'][role][k] for r in selected]))
                    for k in ('precision','recall','IoU')} for role in ('D','S','H')},
                'H_unavailable_gate_occurrences':sum(r['recovery']['H']['unavailable'] for r in selected),
                'H_unavailable_oracle_member_occurrences':sum(r['recovery']['H']['unavailable_oracle_members'] for r in selected)}
        results.append({'archetype':panel['archetype'],'accepted_panel_summary':str(path.relative_to(ROOT)),
            'summary_sha256':sha(path),'trials':trials,'strategy_descriptive_summaries':summaries})
    result={'schema_version':'numek.cg4_posthoc_strategy_attribution/1.0','panels':results,'audit_source_sha256':sha(Path(__file__)),
        'scope':'Post-hoc attribution of previously S-selected gates, using all 40 locked trials per accepted panel. No refitting, H-guided choice, mask-union reconstruction, backfilled diagnostics or new pass criterion. Selection absence remains explicit; medians are conditional on selection. Competing strategies affect shortlist inclusion. This is not isolated-method qualification, a complementary-value test, a recovery theorem or a replacement for matched comparisons.'}
    with Path(args.out).open('x') as stream:json.dump(result,stream,indent=2,sort_keys=True);stream.write('\n')
    print(json.dumps([{k:v for k,v in p.items() if k!='trials'} for p in results],sort_keys=True))


if __name__=='__main__':main()
