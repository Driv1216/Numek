"""Replay S-only reconciliation from retained synthetic D/S candidate masks.

No predictor fit, gate change, H membership or H effect calculation. This is a
post-hoc diagnosis, not independent qualification of the revised selector.
"""
import argparse
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile

import numpy as np

from confidenceguard.contracts import digest
from confidenceguard.investigation import arguments, prepared
from confidenceguard.investigation_objectives import bind
from confidenceguard.investigation_reconciliation import reconcile,marginal_selection_evidence
from confidenceguard.investigation_result import InvestigationResult
from run_locked_qualification import ROOT,snapshot


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--diagnostic',required=True);parser.add_argument('--out',required=True)
    args=parser.parse_args();folder=Path(args.diagnostic).absolute();output=Path(args.out).absolute()
    if output.exists():raise RuntimeError('Preserve previous diagnostic evidence.')
    diagnostic=json.loads((folder/'diagnostic.json').read_text())
    identity='d8f73aaacf3d835d4323561e94336fccef453cdc6db5c985af2357b4084dcc46'
    if diagnostic['source_identity']!=identity or not diagnostic['original_shortlist_reproduced']:
        raise RuntimeError('This replay only admits the source-checked original broad/narrow diagnosis.')
    capsule,_=snapshot(identity);sys.path.insert(0,str(capsule/'validation/cg4'))
    try:
        specifier=importlib.util.spec_from_file_location('cg4_original_broad_generator',capsule/'validation/cg4/qualify_pipeline.py')
        generator=importlib.util.module_from_spec(specifier);specifier.loader.exec_module(generator)
    finally:sys.path.pop(0)
    record_path=folder/'discovery.json';raw=json.loads(record_path.read_text())
    manifest_path=folder/'.confidenceguard-private'/raw['analysis_id']/'manifest.json'
    original=InvestigationResult.from_dict(raw,private=json.loads(manifest_path.read_text()))
    rows=copy.deepcopy(original.data['investigation']['candidates']);by_id={r['id']:r for r in rows}
    for candidate in rows:
        candidate['_S_mask']=original.private['memberships'][candidate['membership_artifact']]['S']['member_bits']
    with tempfile.TemporaryDirectory(prefix='numek-cg4-S-replay-',dir='/private/tmp') as temporary:
        spec,oracle,_=generator.generate(Path(temporary),diagnostic['seed'],40000,'broad_moderate_and_narrow_severe')
        original_trial=json.loads((ROOT/diagnostic['original_trial']).read_text())
        inputs={'predictions':sha(Path(temporary)/'predictions.csv'),'vectors':sha(Path(temporary)/'vectors.npy')}
        if inputs!=original_trial['input_sha256']:raise RuntimeError('Regenerated synthetic bytes differ.')
        s,c,roots=arguments(spec,original.private['config'],None)
        with prepared(s,c,roots) as p:
            si,_,_=p.role_data('S')
            if original.private['population_event_hashes']['S']!=[digest([s.roles.namespace,p.keys[i]]) for i in si]:
                raise RuntimeError('Original S masks do not align with regenerated evidence.')
            objective=bind(s.objectives[0],p.store)
            def marginal(candidate,previous):
                return marginal_selection_evidence(p,candidate,previous,candidates=by_id,
                    memberships=original.private['memberships'],indices=si,objective=objective)
            ordered,overlap,selected=reconcile(rows,s.limits.shortlist,len(si),marginal)
            roles={}
            for role in ('D','S'):
                indices,_,_=p.role_data(role)
                truth=oracle[np.array([int(json.loads(p.keys[i])[0]) for i in indices])]
                values={}
                for name,choices in [('original',original.data['investigation']['shortlist']),('revised',selected)]:
                    union=np.zeros(len(indices),bool)
                    for cid in choices:
                        stored=original.private['memberships'][by_id[cid]['membership_artifact']][role]
                        union|=np.unpackbits(np.frombuffer(bytes.fromhex(stored['member_bits']),dtype=np.uint8),bitorder='little')[:len(indices)].astype(bool)
                    tp=int(np.count_nonzero(union&truth));fp=int(np.count_nonzero(union&~truth))
                    values[name]={'planned':len(indices),'members':int(union.sum()),'oracle_precision':tp/(tp+fp) if tp+fp else 0.,
                                  'oracle_recall':tp/int(truth.sum()),'oracle_IoU':tp/int(np.count_nonzero(union|truth))}
                roles[role]=values
    record={'schema_version':'numek.cg4_S_selection_replay/1.0','seed':diagnostic['seed'],
        'original_source_identity':identity,'original_diagnostic_sha256':sha(folder/'diagnostic.json'),
        'protected_result_sha256':sha(record_path),'protected_manifest_sha256':sha(manifest_path),
        'selection_policy':overlap['selection_policy'],'original_shortlist':original.data['investigation']['shortlist'],
        'revised_shortlist':selected,'first_severity_gate_preserved':selected[0]==original.data['investigation']['shortlist'][0],
        'roles':roles,'selected_S_evidence':[{'id':r['id'],'reason':r.get('selection_reason'),
            'effect':r['S']['effect'],'conditional_members':r['S']['conditional_members'],
            'marginal':r.get('selection_contribution')} for r in ordered if r['id'] in selected],
        'sources':{name:sha(ROOT/name) for name in ('src/confidenceguard/investigation_reconciliation.py','src/confidenceguard/investigation.py')},
        'harness_sha256':sha(Path(__file__)),
        'scope':'Post-hoc D/S-only development comparison from original frozen candidate masks. Uses current shared marginal reducers; all original masks, effects and models remain unchanged. No model fit, H membership/effect evaluation, new independent claim or qualification conclusion.'}
    with output.open('x') as stream:json.dump(record,stream,indent=2,sort_keys=True);stream.write('\n')
    print(json.dumps({k:v for k,v in record.items() if k not in ('selected_S_evidence','sources')},sort_keys=True))


if __name__=='__main__':main()
