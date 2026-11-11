"""Post-hoc D/S-only diagnosis of the first failed broad/narrow trial.

No H membership, effects, refitting, selection or confirmation is requested.
This cannot qualify a revised selector or establish fresh independent evidence.
"""
from pathlib import Path
import hashlib
import json
import sys
import tempfile
import numpy as np

ROOT=Path('/Users/drivyaanshyadav/Desktop/Numek')
CAPSULE=ROOT/'validation/cg4/source-capsules.nosync/d8f73aaacf3d835d4323561e94336fccef453cdc6db5c985af2357b4084dcc46'
sys.path.insert(0,str(CAPSULE/'validation/cg4'))
from qualify_pipeline import generate
from confidenceguard import investigate
from confidenceguard.investigation import arguments,prepared


def main():
    summary=json.loads((ROOT/'validation/cg4/results/recovery-broad-narrow-summary-v1.json').read_text())
    original=next(row for row in summary['trials'] if not row['success'])
    out=ROOT/'validation/cg4/results/broad-narrow-DS-diagnostic-v54';out.mkdir(mode=0o700)
    with tempfile.TemporaryDirectory(prefix='numek-cg4-broad-DS-',dir='/private/tmp') as temporary:
        spec,oracle,_=generate(Path(temporary),original['seed'],40000,'broad_moderate_and_narrow_severe')
        result=investigate(spec)
        raw=json.loads((ROOT/original['path']).read_text())
        if result.data['investigation']['shortlist']!=raw['shortlist']:
            raise RuntimeError('D/S diagnosis did not reproduce original shortlist; do not attribute results to it.')
        result.generate_artifacts(out/'discovery.html',format='html',audience='local',json_path=out/'discovery.json')
        rows=result.data['investigation']['candidates'];shortlist=set(result.data['investigation']['shortlist'])
        s,c,roots=arguments(spec,None,None);roles={}
        with prepared(s,c,roots) as p:
            for role in ('D','S'):
                indices,_,_=p.role_data(role)
                truth=oracle[np.array([int(json.loads(p.keys[i])[0]) for i in indices])]
                measured=[];selected_union=np.zeros(len(indices),bool)
                for candidate in rows:
                    stored=result.private['memberships'][candidate['membership_artifact']][role]
                    mask=np.unpackbits(np.frombuffer(bytes.fromhex(stored['member_bits']),dtype=np.uint8),bitorder='little')[:len(indices)].astype(bool)
                    tp=int(np.count_nonzero(mask&truth));fp=int(np.count_nonzero(mask&~truth))
                    if candidate['id'] in shortlist:selected_union|=mask
                    measured.append({'candidate':candidate['id'],'strategy':candidate['strategy'],'selected':candidate['id'] in shortlist,
                        'effect':candidate[role]['effect'],'conditional_members':candidate[role]['conditional_members'],
                        'precision':tp/(tp+fp) if tp+fp else 0.,'recall':tp/int(truth.sum()),
                        'definition':candidate['definition'],'complexity':candidate['complexity'],'frontier':candidate['frontier']})
                roles[role]={'candidates':measured,'selected_union_precision':float(np.count_nonzero(selected_union&truth)/selected_union.sum()),
                             'selected_union_recall':float(np.count_nonzero(selected_union&truth)/truth.sum())}
        record={'schema_version':'numek.cg4_posthoc_DS_selection_diagnosis/1.0','original_trial':original['path'],
                'original_trial_sha256':original['sha256'],'source_identity':CAPSULE.name,
                'seed':original['seed'],'original_shortlist_reproduced':True,'roles':roles,
                'scope':'Post-hoc first failed trial diagnosis using original source/profile and D/S only. Oracle comparisons diagnose proposal versus selection coverage; they are not selection rules or qualification. No H membership/effect calculation or original finding alteration.'}
        (out/'diagnostic.json').write_text(json.dumps(record,indent=2,sort_keys=True)+'\n')
        print(json.dumps({'seed':original['seed'],'original_shortlist_reproduced':True,
            'roles':{role:{key:value for key,value in data.items() if key!='candidates'} for role,data in roles.items()}}),flush=True)


if __name__=='__main__':main()
