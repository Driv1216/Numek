"""Numerical replay of a completed synthetic trial; no new confirmation claim."""
import argparse
from dataclasses import replace
import json
from pathlib import Path
import tempfile
import numpy as np
import qualify_pipeline as pipeline


def main():
    from confidenceguard import investigate
    from confidenceguard.investigation import arguments,prepared
    from confidenceguard.investigation_membership import apply
    from confidenceguard.investigation_objectives import bind
    from confidenceguard.confirmation import finite_interval
    parser=argparse.ArgumentParser();parser.add_argument('--prior',required=True);parser.add_argument('--out',required=True);args=parser.parse_args()
    prior=json.loads(Path(args.prior).read_text());source=pipeline.identity()
    if prior['status']!='completed' or prior['panel'] not in {'recovery_qualification','default_full_pipeline_null','reduced_full_pipeline_null'}:raise RuntimeError('Completed locked synthetic evidence required.')
    with tempfile.TemporaryDirectory(prefix='numek-cg4-numerical-replay-',dir='/private/tmp') as temporary:
        spec,oracle,_=pipeline.generate(Path(temporary),prior['seed'],prior['n'],prior['archetype'],null=prior['null'])
        if prior['null']:spec=replace(spec,objectives=tuple(replace(o,practical_threshold=0.) for o in spec.objectives))
        if prior['panel']=='reduced_full_pipeline_null':spec=replace(spec,limits=replace(spec.limits,max_nodes=2000,max_depth=4,candidates_per_strategy=16,shortlist=4,landmarks=32,neighbors=8,stability_replicates=1))
        spec=replace(spec,strategies=tuple(prior['strategies']));result=investigate(spec);selected=result.data['investigation']['shortlist']
        recovered={};effects=[];intervals=[];s,c,roots=arguments(spec,None,None)
        originals={a['candidate_id']:a for a in prior['assessments']};m=len(originals)
        with prepared(s,c,roots) as p:
            adapter=bind(p.spec.objectives[0],p.store)
            for role in ('D','S','H'):
                indices,features,reps=p.role_data(role);truth=oracle[np.array([int(json.loads(p.keys[i])[0]) for i in indices])]
                union=np.zeros(len(indices),bool);available=np.ones(len(indices),bool);individual=[]
                cache={'_models':result.private['models'],'_population_size':len(indices),'_directory':str(p.work.root),
                    '_max_distance_ops':spec.limits.max_distance_operations,'_membership_memory_bytes':c.max_rss_bytes//3,'_threads':c.threads}
                for candidate in result.data['investigation']['candidates']:
                    if candidate['id'] not in selected:continue
                    artifact=result.private['artifacts'][candidate['membership_artifact']];mask=apply(artifact,features,reps,cache=cache,check=p.work.check)
                    union|=mask['member'];available&=mask['available']
                    individual.append({'candidate_id':candidate['id'],'strategy':candidate['strategy'],**pipeline.recovery(truth,mask['member'],mask['available'])})
                    old=originals.get(candidate['id'],{})
                    if role=='H' and old.get('H_outcomes_disclosed'):
                        measured=p.evaluate(adapter,role,indices,mask,artifact)
                        effects.append({'candidate_id':candidate['id'],'matches':old['effect']==measured['effect'] and old['effect_state']==measured['effect_state']})
                        if old.get('inference',{}).get('status')=='available':
                            if adapter.spec.metric!='error_rate' or not adapter.binary:raise RuntimeError('Only the registered Bernoulli error contrast is admitted for this numerical reference.')
                            values=np.array([float(p.records[i]['decision']!=p.records[i]['y']) for i in indices])
                            eligible=np.array([r['outcome_valid'] and r['decision'] is not None for r in (p.records[i] for i in indices)])
                            member=mask['member']&eligible;control=mask['available']&~mask['member']&eligible
                            interval=finite_interval(adapter.spec,values[member],values[control],.05/m,binary=True,bounds=(0.,1.))
                            intervals.append({'candidate_id':candidate['id'],'matches':all(interval[k]==old['interval'][k] for k in ('lower','upper'))})
                recovered[role]={'primary_selected_union':pipeline.recovery(truth,union,available|union),'selected_candidates':individual}
        checks={'candidate_ids_equal':selected==prior['shortlist'],'D_S_H_recovery_equal':recovered==prior['recovery'],
            'available_native_H_effects_equal':all(v['matches'] for v in effects),'available_finite_intervals_equal':all(v['matches'] for v in intervals),
            'source_unchanged':source==pipeline.identity()}
    record={'schema_version':'numek.cg4_default_profile_computational_replay/1.0','reference':str(Path(args.prior).absolute()),
        'reference_sha256':pipeline.sha(args.prior),'source_sha256':source,'harness_sha256':pipeline.sha(__file__),
        'checks':checks,'native_effects':effects,'finite_intervals':intervals,'status':'matched' if all(checks.values()) else 'mismatch',
        'replay_only':True,'counts_as_new_qualification_trial':False,'fresh_independent_evidence':False,
        'scope':'Reproduce selected masks, native effects and finite numerical intervals. No confirmation operation or new independent assessment is performed.'}
    with Path(args.out).open('x') as stream:json.dump(record,stream,sort_keys=True,indent=2);stream.write('\n')
    print(json.dumps({'status':record['status'],'checks':checks}))


if __name__=='__main__':main()
