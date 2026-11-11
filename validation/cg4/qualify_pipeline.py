"""Reproducible synthetic discovery-to-confirmation campaign.

Each trial runs in a fresh process with a unique synthetic namespace. Development
seeds never count as locked recovery evidence. Resume only reuses records whose
complete runtime-source, protocol, profile and seed identities match. This is
benchmark tooling, not a product predictor-execution interface.
"""
import argparse
import csv
from dataclasses import replace
from datetime import datetime,timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import traceback
import zipfile
import numpy as np
import qualification_diagnostics as diagnostics
import parallel_qualification as parallel

ROOT=Path(__file__).resolve().parents[2]
PROTOCOL=Path(__file__).with_name('qualification_protocol_v3.json')


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def identity():
    paths=list((ROOT/'src/confidenceguard').glob('*.py'))+[ROOT/'src/datatrust'/n for n in ('worker.py','scalable.py','scalable_engine.py','image_assets.py')]
    return {str(path.relative_to(ROOT)):sha(path) for path in sorted(paths) if path.exists()}


def runtime_versions():
    return {name:importlib.metadata.version(name) for name in ('numpy','scipy','pandas','duckdb','catboost','pyarrow','threadpoolctl')}


def snapshot_sources(destination,profile):
    token=hashlib.sha256(json.dumps(profile,sort_keys=True).encode()).hexdigest();target=destination/('runtime-source-'+token+'.zip')
    if target.exists():return
    with zipfile.ZipFile(target,'x',compression=zipfile.ZIP_DEFLATED) as archive:
        for relative,expected in profile['source_sha256'].items():
            raw=(ROOT/relative).read_bytes()
            if hashlib.sha256(raw).hexdigest()!=expected:raise RuntimeError('Source changed while capturing the qualification runtime.')
            archive.writestr(relative,raw)
        archive.writestr('qualification_profile.json',json.dumps(profile,sort_keys=True,indent=2))
        archive.writestr('qualification_protocol.json',PROTOCOL.read_bytes());archive.writestr('qualify_pipeline.py',Path(__file__).read_bytes())
        raw=Path(diagnostics.__file__).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=profile['diagnostics_harness_sha256']:raise RuntimeError('Diagnostics source changed during capture.')
        archive.writestr('qualification_diagnostics.py',raw)
        archive.writestr('parallel_qualification.py',Path(parallel.__file__).read_bytes())


def generate(directory,seed,n,archetype,*,null=False):
    from confidenceguard import InvestigationSpec
    rng=np.random.default_rng(seed);xy=rng.uniform(-1,1,(n,2));x,y=xy.T;bits=rng.integers(0,2,(n,3));rare=rng.random(n)<.3
    if archetype=='interaction_without_marginals':region=rare&(bits[:,0]!=bits[:,1])
    elif archetype=='parity':region=rare&(bits.sum(axis=1)%2==1)
    elif archetype=='categorical_numeric_conjunction':region=(bits[:,0]==1)&(x>.5)
    elif archetype=='rare_failure':region=x>.9
    elif archetype=='curved_region':region=(x*x+y*y>.5**2)&(x*x+y*y<.65**2)
    elif archetype=='disconnected_regions':region=((x+.5)**2+(y+.5)**2<.3**2)|((x-.5)**2+(y-.5)**2<.3**2)
    elif archetype=='heterogeneous_density':
        sparse=rng.random(n)<.1;xy=rng.normal(0,.1,(n,2));xy[sparse]=rng.normal((1,0),.4,(int(sparse.sum()),2));x,y=xy.T
        radius=(x-1)**2+y*y;region=(radius>.15**2)&(radius<.7**2)
    elif archetype=='overlapping_mechanisms':region=((x+.25)**2+y*y<.33**2)|((x-.25)**2+y*y<.33**2)
    elif archetype=='broad_moderate_and_narrow_severe':region=x>.6
    elif archetype=='high_dimensional_nuisance':region=(x*x+y*y>.5**2)&(x*x+y*y<.65**2)
    else:raise ValueError('Unregistered archetype')
    probabilities=np.where(region,.4,.1)
    if archetype=='broad_moderate_and_narrow_severe':probabilities=np.where((x>.6)&(y>.4),.65,np.where(region,.3,.1))
    if null:probabilities[:]=.1
    outcome=rng.integers(0,2,n);error=rng.random(n)<probabilities;decision=outcome^error
    path=directory/'predictions.csv'
    with path.open('w',newline='') as stream:
        writer=csv.writer(stream);writer.writerow(['id','entity','outcome','prediction','probability','x','y','a','b','c','rare'])
        for i in range(n):writer.writerow([i,i,outcome[i],decision[i],.9 if decision[i] else .1,repr(float(x[i])),repr(float(y[i])),*bits[i],str(bool(rare[i]))])
    vectors=xy.astype('<f4')
    if archetype=='high_dimensional_nuisance':vectors=np.column_stack((vectors,rng.normal(0,.03,(n,382)))).astype('<f4')
    np.save(directory/'vectors.npy',vectors)
    fields=[{'id':f,'column':f,'kind':'float' if f in ('x','y') else 'categorical'} for f in ('x','y','a','b','c','rare')]
    # Geometric panels exclude oracle-coordinate tabular gates, exposing the
    # representation methods' complementary role instead of crediting rules.
    if archetype in {'curved_region','disconnected_regions','heterogeneous_density','overlapping_mechanisms','high_dimensional_nuisance'}:fields=[f for f in fields if f['id'] in {'a','b','c'}]
    spec=InvestigationSpec.from_dict({'name':'Synthetic '+archetype,'evaluation':{'task':{'kind':'binary_classification','outcome_definition':'synthetic_issued_error','classes':['0','1'],'positive_class':'1'},
        'sources':[{'id':'predictions','path':str(path)}],'runs':[{'id':'candidate','source':'predictions','model':{'id':'benchmark_supplied_prediction','version':'v1'},'key_columns':['id'],'entity_columns':['entity'],'prediction':'prediction','probabilities':{'positive_column':'probability'}}],
        'outcomes':{'source':'predictions','column':'outcome','key_columns':['id']}},
        'roles':{'namespace':f'cg4-synthetic-{seed}-{archetype}-{n}-{int(null)}','unit':'entity'},
        'features':[{'id':'context','availability':'at_decision','fields':fields}],
        'representations':[{'id':'geometry','matrix_path':str(directory/'vectors.npy'),'keys_source':{'id':'keys','path':str(path)},'key_columns':['id'],'dimensions':vectors.shape[1],'availability':'at_decision'}],
        'objectives':[{'id':'error','run':'candidate','metric':'error_rate','practical_threshold':.15}]})
    return spec,region,error


def recovery(truth,member,available):
    tp=int(np.count_nonzero(truth&member));fp=int(np.count_nonzero(~truth&member));fn=int(np.count_nonzero(truth&~member))
    return {'precision':tp/(tp+fp) if tp+fp else 0.,'recall':tp/(tp+fn) if tp+fn else 0.,'IoU':tp/(tp+fp+fn) if tp+fp+fn else 1.,
        'true_positive':tp,'false_positive':fp,'false_negative':fn,'planned':len(truth),'unavailable':int((~available).sum()),'unavailable_oracle_members':int((~available&truth).sum())}


def trial(args):
    from confidenceguard import investigate,freeze_hypotheses,confirm_investigation,ConfirmationSpec,EvaluationConfig
    from confidenceguard.investigation import arguments,prepared
    from confidenceguard.investigation_membership import apply
    started=time.monotonic();null=args.panel in {'reduced_full_pipeline_null','default_full_pipeline_null'}
    n=1200 if args.panel=='reduced_full_pipeline_null' else 6000 if args.panel=='development' and not args.full_profile else 40000
    with tempfile.TemporaryDirectory(prefix='numek-cg4-qualification-',dir='/private/tmp') as temporary:
        directory=Path(temporary);spec,oracle,errors=generate(directory,args.seed,n,args.archetype,null=null)
        if null:
            # Complete-null claims sit at their practical boundary. A positive
            # delta against zero true contrast would be an easier error test.
            spec=replace(spec,objectives=tuple(replace(o,practical_threshold=0.) for o in spec.objectives))
        if args.panel=='reduced_full_pipeline_null' or args.panel=='development' and not args.full_profile:
            spec=replace(spec,limits=replace(spec.limits,max_nodes=2000,max_depth=4,candidates_per_strategy=16,shortlist=4,landmarks=32,neighbors=8,stability_replicates=1))
        if args.strategies:spec=replace(spec,strategies=tuple(args.strategies.split(',')))
        from confidenceguard.investigation import configuration
        config=configuration();discovery=investigate(spec,config)
        selected=discovery.data['investigation']['shortlist'];assessment=None
        if selected:
            protocol=ConfirmationSpec(sampling='independent_rows',upstream_independence='declared_independent',external_exposure='declared_unexposed',
                declaration_author='NUMEK synthetic generator',declaration_reason='Independent RNG-generated observations, unique keys and isolated study process; no predictor training or earlier synthetic evidence.')
            frozen=freeze_hypotheses(discovery,confirmation=protocol);assessment=confirm_investigation(frozen,config)
        evidence={};s,c,roots=arguments(spec,config,None)
        with prepared(s,c,roots) as p:
            for role in ('D','S','H'):
                indices,features,reps=p.role_data(role);truth=oracle[np.array([int(json.loads(p.keys[i])[0]) for i in indices])]
                cache={'_models':discovery.private['models'],'_directory':str(p.work.root),'_population_size':len(indices),'_max_distance_ops':spec.limits.max_distance_operations}
                union=np.zeros(len(indices),bool);available=np.ones(len(indices),bool);individual=[]
                for candidate in discovery.data['investigation']['candidates']:
                    if candidate['id'] not in selected:continue
                    mask=apply(discovery.private['artifacts'][candidate['membership_artifact']],features,reps,cache=cache,check=p.work.check)
                    union|=mask['member'];available&=mask['available'];individual.append({'candidate_id':candidate['id'],'strategy':candidate['strategy'],**recovery(truth,mask['member'],mask['available']),
                        'frozen_explanation_fidelity':diagnostics.explanation_fidelity(candidate,discovery.private['artifacts'][candidate['membership_artifact']],mask,features,reps,cache,p.work.check)})
                available|=union
                evidence[role]={'primary_selected_union':recovery(truth,union,available),'selected_candidates':individual}
        assessments=assessment.data['investigation']['assessments'] if assessment else []
        record={'seed':args.seed,'panel':args.panel,'archetype':args.archetype,'null':null,'admitted_limits':spec.limits.to_dict(),'admitted_config':config.to_dict(),'strategies':list(spec.strategies),
            'input_sha256':{'predictions':sha(directory/'predictions.csv'),'vectors':sha(directory/'vectors.npy')},'n':n,'oracle_prevalence':float(oracle.mean()),
            'actual_failure_rate':float(errors.mean()),'recovery':evidence,'shortlist':selected,'assessments':assessments,'false_confirmation_under_complete_null':bool(null and any(a['state']=='confirmed' for a in assessments)),
            'strategy_execution':discovery.data['investigation']['strategies'],'investigation_diagnostics':diagnostics.snapshot(discovery),
            'execution':{'discovery':discovery.execution,'confirmation':assessment.execution if assessment else None},
            'seconds':time.monotonic()-started,'status':'completed','qualification_success_presumed':False}
    return record


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--panel',choices=['development','recovery_qualification','reduced_full_pipeline_null','default_full_pipeline_null'],required=True)
    parser.add_argument('--archetype',default='interaction_without_marginals');parser.add_argument('--strategies');parser.add_argument('--out',required=True)
    parser.add_argument('--offset',type=int,default=0);parser.add_argument('--count',type=int);parser.add_argument('--worker',action='store_true');parser.add_argument('--seed',type=int);parser.add_argument('--full-profile',action='store_true')
    parser.add_argument('--workers',type=int,choices=range(1,5),default=1)
    args=parser.parse_args();protocol=json.loads(PROTOCOL.read_text());sources=identity();profile={'protocol_sha256':sha(PROTOCOL),'source_sha256':sources,'harness_sha256':sha(__file__),
        'parallel_seed_runner_sha256':sha(parallel.__file__),'diagnostics_harness_sha256':sha(diagnostics.__file__),'python':sys.version,'package_versions':runtime_versions(),'strategies':args.strategies,'full_profile':args.full_profile}
    if args.archetype not in protocol['required_archetypes']:parser.error('Archetype is not in the locked protocol.')
    if args.worker:
        try:record=trial(args)
        except Exception as exc:record={'seed':args.seed,'panel':args.panel,'archetype':args.archetype,'status':'execution_failure','error_type':type(exc).__name__,'error_code':getattr(exc,'code',None),'traceback':traceback.format_exc()}
        if identity()!=sources or sha(__file__)!=profile['harness_sha256'] or sha(diagnostics.__file__)!=profile['diagnostics_harness_sha256'] or sha(parallel.__file__)!=profile['parallel_seed_runner_sha256'] or runtime_versions()!=profile['package_versions']:
            record.update(status_before_invalidation=record['status'],status='invalidated_source_change',qualification_usable=False)
        record.update(profile=profile,generated_at=datetime.now(timezone.utc).isoformat())
        with Path(args.out).open('x') as stream:stream.write(json.dumps(record,sort_keys=True,indent=2,allow_nan=False)+'\n')
        return
    panel=protocol['seed_panels'][args.panel];count=panel['count'] if args.count is None else args.count
    if args.offset<0 or count<1 or args.offset+count>panel['count']:parser.error('Requested seed range exceeds its locked panel.')
    destination=Path(args.out);destination.mkdir(parents=True,exist_ok=True)
    snapshot_sources(destination,profile)
    def run_seed(seed):
        if identity()!=sources or sha(__file__)!=profile['harness_sha256'] or sha(diagnostics.__file__)!=profile['diagnostics_harness_sha256'] or sha(parallel.__file__)!=profile['parallel_seed_runner_sha256'] or runtime_versions()!=profile['package_versions']:
            raise RuntimeError('Campaign runtime changed; preserve this panel and start a separately identified campaign.')
        result=destination/f'{args.panel}-{args.archetype}-{seed}.json'
        if result.exists():
            previous=json.loads(result.read_text())
            if (previous.get('profile')!=profile or previous.get('status')!='completed' or previous.get('seed')!=seed or
                previous.get('panel')!=args.panel or previous.get('archetype')!=args.archetype):
                raise RuntimeError('Failed or mismatched saved trial; preserve it and resolve before resuming.')
            parallel.emit({'seed':seed,'reused':True});return
        pending=result.with_suffix('.pending');command=[sys.executable,'-B',str(Path(__file__).resolve()),'--worker','--panel',args.panel,'--archetype',args.archetype,'--seed',str(seed),'--out',str(pending)]
        if pending.exists():raise RuntimeError('Preserve incomplete pending evidence before resuming.')
        if args.strategies:command+=['--strategies',args.strategies]
        if args.full_profile:command+=['--full-profile']
        subprocess.run(command,cwd=ROOT,check=True);pending.rename(result)
        record=json.loads(result.read_text());parallel.emit({'seed':seed,'status':record['status'],'seconds':record.get('seconds'),'H_recovery':record.get('recovery',{}).get('H',{}).get('primary_selected_union')})
        if record['status']!='completed' or record.get('profile')!=profile:raise RuntimeError('Campaign stopped on failed or changed execution; failed evidence is retained for diagnosis.')
    parallel.run_fixed_seeds(range(panel['start']+args.offset,panel['start']+args.offset+count),args.workers,run_seed)


if __name__=='__main__':main()
