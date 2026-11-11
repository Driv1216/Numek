"""Historical deterioration: independent entities, paired dated observations.

Synthetic predictor outputs are supplied evidence. This tool is not a product
predictor executor. Repeated observations stay together in D/S/H and resampling.
"""
import argparse
import csv
from datetime import datetime,timezone
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import traceback
import numpy as np
import qualify_pipeline as pipeline
import parallel_qualification as parallel

PROTOCOL={'schema_version':'numek.cg4_historical_recovery_protocol/1.2',
    'selection_policy':'severity_material_excess_support_frontier_v2',
    'independent_entities':40000,'events_per_entity':2,'region':'a=1 AND x>.5; expected prevalence .125',
    'reference_error':.1,'current_background_error':.1,'current_region_error':.4,'practical_threshold':.15,
    'seeds':{'development':[0,39],'qualification':[320000,320039]},
    'criterion':{'H_precision':.7,'H_recall':.7,'minimum_successes_of_40':32},
    'population_recovery':'Event-weighted region recovery; both period observations share truth and entity role.',
    'effect':'Current minus reference error within the frozen region, recomputed by shared reducers.',
    'confirmation':'Complete-entity approximate inference must be qualified independently. Repeated events cannot use IID-row inference.',
    'scenarios':{'current_risk_shift':'Reference error .10 everywhere; current region .40, background .10.',
                 'reference_only_shift':'Current error .40 everywhere; reference region .10, background .40. Current-only diagnostic risk has no population signal for the region.'},
    'diagnostic_target_policy':'historical_period_heads_and_matched_entity_delta_v1',
    'qualification_success_presumed':False}


def generate(root,seed,n,scenario='current_risk_shift'):
    if scenario not in PROTOCOL['scenarios']:raise ValueError('Unregistered historical scenario.')
    rng=np.random.default_rng(seed);x=rng.uniform(-1,1,n);a=rng.integers(0,2,n)
    region=(a==1)&(x>.5);path=root/'predictions.csv';truth={};records=[]
    for period,when in [('reference','2026-01-01T00:00:00Z'),('current','2026-02-01T00:00:00Z')]:
        y=rng.integers(0,2,n);rate=np.where(region,.4,.1) if period=='current' else np.full(n,.1)
        if scenario=='reference_only_shift':rate=np.full(n,.4) if period=='current' else np.where(region,.1,.4)
        error=rng.random(n)<rate
        for i in range(n):
            event=period+'-'+str(i);truth[event]=bool(region[i])
            records.append([event,i,int(y[i]),int(y[i]^error[i]),repr(float(x[i])),int(a[i]),when,'2026-03-01T00:00:00Z'])
    with path.open('w',newline='') as stream:
        writer=csv.writer(stream);writer.writerow(['id','entity','y','decision','x','a','when','available']);writer.writerows(records)
    namespace=f'cg4-history-{seed}-{n}'
    if scenario!='current_risk_shift':namespace+='-'+scenario
    evaluation={'task':{'kind':'binary_classification','classes':['0','1'],'positive_class':'1','outcome_definition':'Independent synthetic dated label'},
        'sources':[{'id':'data','path':str(path)}],
        'runs':[{'id':'model','source':'data','model':{'id':'synthetic-fixed-predictor','version':'v1'},'key_columns':['id'],'entity_columns':['entity'],'prediction':'decision','prediction_at':{'column':'when'}}],
        'outcomes':{'source':'data','column':'y','key_columns':['id'],'available_at':{'column':'available'}}}
    view={'id':'context','availability':'at_decision','fields':[{'id':'x','column':'x','kind':'float'},{'id':'a','column':'a','kind':'categorical'}]}
    batch={'schema_version':'confidenceguard.prediction_batch_spec/2.0','evaluation':evaluation,'namespace':namespace,
           'outcome_definition_version':'v1','bindings':[{'run':'model'}],'feature_views':[view]}
    return batch,view,truth


def trial(seed,development,strategies,full_profile=False,scenario='current_risk_shift'):
    from confidenceguard import ReliabilityWorkspace,WorkspaceConfig,InvestigationSpec
    from confidenceguard.investigation import prepared,arguments
    from confidenceguard.investigation_objectives import bind
    from confidenceguard.investigation_membership import apply
    with tempfile.TemporaryDirectory(prefix='numek-cg4-history-qualification-',dir='/private/tmp') as temporary:
        root=Path(temporary);small_development=development and not full_profile
        n=1200 if small_development else PROTOCOL['independent_entities'];batch,view,truth=generate(root,seed,n,scenario)
        workspace=ReliabilityWorkspace.initialize(root/'workspace',WorkspaceConfig(saving=True,free_disk_bytes=1))
        capture=workspace.ingest(batch);variant=workspace.models()[0]['id']
        spec=InvestigationSpec.from_dict({'name':'Synthetic historical deterioration','history':{'workspace_path':str(workspace.path),
            'selection':{'namespace':batch['namespace'],'variants':[variant],'as_of':'2026-04-01T00:00:00Z',
            'windows':[{'id':'reference','start':'2026-01-01T00:00:00Z','end':'2026-02-01T00:00:00Z'},
                       {'id':'current','start':'2026-02-01T00:00:00Z','end':'2026-03-01T00:00:00Z'}]}},
            'roles':{'namespace':batch['namespace'],'unit':'entity'},'features':[view],
            'objectives':[{'id':'deterioration','metric':'error_rate','run':variant,'comparator':'reference_period',
                'reference_period':'reference','current_period':'current','practical_threshold':.15}],
            'strategies':strategies.split(',') if strategies else ['structured','catboost'],
            **({'limits':{'max_nodes':10000,'candidates_per_strategy':32,'stability_replicates':1}} if small_development else {})})
        result=workspace.investigate(spec);selected=result.data['investigation']['shortlist'];recovered={}
        effective=InvestigationSpec.from_dict(result.private['investigation_spec']);s,c,roots=arguments(effective,None,None)
        with prepared(s,c,roots) as p:
            # Original key is retained as provenance; it is not inferred from a
            # fact hash or from the observed errors after selection.
            originals=getattr(p.store,'cg4_original_keys',{})
            truth_by_key={key:truth[json.loads(raw)[0]] for key,raw in originals.items()}
            objective=bind(p.spec.objectives[0],p.store)
            for role in ('D','S','H'):
                indices,features,reps=p.role_data(role);oracle=np.array([truth_by_key[p.keys[i]] for i in indices])
                union=np.zeros(len(indices),bool);available=np.ones(len(indices),bool);effects=[]
                cache={'_models':result.private['models'],'_population_size':len(indices)}
                for candidate in result.data['investigation']['candidates']:
                    if candidate['id'] not in selected:continue
                    artifact=result.private['artifacts'][candidate['membership_artifact']];mask=apply(artifact,features,reps,cache=cache)
                    union|=mask['member'];available&=mask['available']
                    effects.append({'id':candidate['id'],'native_evidence':p.evaluate(objective,role,indices,mask,artifact),
                        'frozen_explanation_fidelity':pipeline.diagnostics.explanation_fidelity(candidate,artifact,mask,features,reps,cache,p.work.check)})
                recovered[role]={'primary_selected_union':pipeline.recovery(oracle,union,available|union),'selected_native_effects':effects}
        h=recovered['H']['primary_selected_union']
        return {'status':'completed','seed':seed,'scenario':scenario,'independent_entities':n,'events':2*n,'input_sha256':pipeline.sha(root/'predictions.csv'),
            'capture_digest':capture['capture_digest'],'recovery':recovered,'shortlist':selected,'strategy_execution':result.data['investigation']['strategies'],
            'admitted_limits':spec.limits.to_dict(),'admitted_config':result.private['config'],
            'execution':result.execution,'investigation_diagnostics':pipeline.diagnostics.snapshot(result),'anchor_success':h['precision']>=.7 and h['recall']>=.7,
            'formal_confirmation_performed':False,'confirmation_limitation':PROTOCOL['confirmation']}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--panel',choices=('development','qualification'),required=True)
    parser.add_argument('--out',required=True);parser.add_argument('--offset',type=int,default=0);parser.add_argument('--count',type=int,default=40)
    parser.add_argument('--strategies');parser.add_argument('--worker',action='store_true');parser.add_argument('--seed',type=int)
    parser.add_argument('--full-profile',action='store_true',help='Use the complete population and default budgets for development, without counting it as qualification.')
    parser.add_argument('--scenario',choices=PROTOCOL['scenarios'],default='current_risk_shift')
    parser.add_argument('--workers',type=int,choices=range(1,5),default=1)
    args=parser.parse_args();profile={'protocol':PROTOCOL,'harness_sha256':pipeline.sha(__file__),'source_sha256':pipeline.identity(),
        'parallel_seed_runner_sha256':pipeline.sha(parallel.__file__),'diagnostics_harness_sha256':pipeline.sha(pipeline.diagnostics.__file__),
        'packages':pipeline.runtime_versions(),'panel':args.panel,'strategies':args.strategies,'full_profile':args.full_profile,'scenario':args.scenario}
    if args.worker:
        started=time.monotonic()
        try:record=trial(args.seed,args.panel=='development',args.strategies,args.full_profile,args.scenario)
        except Exception as exc:record={'status':'execution_failure','seed':args.seed,'error_code':getattr(exc,'code',None),'traceback':traceback.format_exc()}
        if pipeline.identity()!=profile['source_sha256'] or pipeline.sha(__file__)!=profile['harness_sha256'] or pipeline.sha(pipeline.diagnostics.__file__)!=profile['diagnostics_harness_sha256'] or pipeline.sha(parallel.__file__)!=profile['parallel_seed_runner_sha256']:record.update(status_before_invalidation=record['status'],status='invalidated_source_change')
        record.update(profile=profile,seconds=time.monotonic()-started,generated_at=datetime.now(timezone.utc).isoformat())
        with Path(args.out).open('x') as stream:json.dump(record,stream,sort_keys=True,indent=2,allow_nan=False);stream.write('\n')
        return
    if args.offset<0 or args.count<1 or args.offset+args.count>40:parser.error('Outside locked 40-seed panel.')
    out=Path(args.out);out.mkdir(parents=True,exist_ok=True);start=PROTOCOL['seeds'][args.panel][0]
    def run_seed(seed):
        path=out/f'{seed}.json'
        if path.exists():
            previous=json.loads(path.read_text())
            if previous.get('profile')!=profile or previous.get('status')!='completed' or previous.get('seed')!=seed or previous.get('scenario')!=args.scenario:
                raise RuntimeError('Failed or mismatched saved trial; preserve it and resolve before resuming.')
            return
        pending=path.with_suffix('.pending');command=[sys.executable,'-B',__file__,'--worker','--seed',str(seed),'--panel',args.panel,'--out',str(pending)]
        if pending.exists():raise RuntimeError('Preserve incomplete pending evidence before resuming.')
        if args.strategies:command+=['--strategies',args.strategies]
        if args.full_profile:command+=['--full-profile']
        command+=['--scenario',args.scenario]
        subprocess.run(command,check=True);pending.rename(path);record=json.loads(path.read_text());parallel.emit({'seed':seed,'status':record['status'],'seconds':record['seconds']})
        if record['status']!='completed' or record.get('profile')!=profile:raise RuntimeError('Retain failed evidence; diagnose before continuing.')
    parallel.run_fixed_seeds(range(start+args.offset,start+args.offset+args.count),args.workers,run_seed)


if __name__=='__main__':main()
