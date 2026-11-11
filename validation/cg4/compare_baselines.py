"""Locked complementary-value comparisons using shared metric/membership code.

Benchmark models only. No new runtime strategy, predictor executor or analytical
reducer. All models/gates fit D; the shared S frontier chooses one gate per method.
Every method is frozen before H. Full native shortlist recovery is secondary,
explicitly separate from the matched one-gate comparison.
"""
import argparse
from dataclasses import replace
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import traceback

import numpy as np
import qualify_pipeline as pipeline

PROTOCOL={'schema_version':'numek.cg4_baseline_comparison/1.0',
    'families':['interaction_without_marginals','categorical_numeric_conjunction','curved_region','heterogeneous_density'],
    'seeds':{'development':[0,9],'qualification':[180000,180039]},'qualification_units':40000,
    'methods':['native_unified','low_order_rules','shallow_tree','single_diagnostic','error_blind_clusters','simple_balls'],
    'definitions':{'low_order_rules':'Existing predicate search, maximum depth two; same admitted node/candidate budget.',
        'shallow_tree':'One depth-two CPU CatBoost symmetric tree, same diagnostic target and categorical preprocessing.',
        'single_diagnostic':'One depth-four, 256-tree CPU CatBoost diagnostic model; D score quantiles/bands.',
        'error_blind_clusters':'SciPy Lloyd k-means++, 16 centers, 20 iterations, seed zero; geometry only, no outcome input to fitting. One Voronoi cell per proposal.',
        'simple_balls':'Eight D geometry-coverage and eight high-loss observation centers, single balls at fixed D distance quantiles. No annuli, unions, PCA or graph.'},
    'selection':'Shared native adverse-effect/support/complexity frontier on S; one first selected gate per method. No H/oracle choice. Native complete shortlist union is a separately labelled secondary result.',
    'geometry':'Original declared normalized vectors only in simpler baselines. Fit at most 20000 D vectors; shared frozen support radius from 1.5 times the .995 D nearest-center distance quantile. Unavailable H stays in planned recovery denominators.',
    'access':'Tabular baselines use the same admitted typed fields as native rules/CatBoost; geometry baselines use the same supplied vectors as native regions. Geometry panels deliberately exclude oracle-coordinate tabular gates. Benefits are conditional on these input contracts.',
    'inference':'Independent H native effects are descriptive; no product confirmation or causal claim. Paired comparisons use independent fixed seed datasets and must report their uncertainty and comparison multiplicity. No presumed native superiority.',
    'paired_uncertainty':'For all 40 fresh seed pairs, report native-single minus baseline-single H IoU. Use conservative binomial order-statistic intervals for a population median, with .05/(4 families * 5 baselines) error per interval. No normality assumption, adaptive stopping or incomplete-panel interval. Mean/win counts are descriptive. Simultaneous guarantee is conditional on independent seed-pair sampling and fixed method/protocol identities.',
    'resources':'Same product absolute thread/memory/deadline/workspace admission. Record actual fit/evaluation time and shared worker RSS. Concurrent-host time and shared peak RSS cannot establish controlled relative-efficiency ratios.',
    'scope':'Complementary-value evidence for these four error-rate archetypes only. Does not replace required objective-specific, overlap/stability/null/resource qualification or original unified full-shortlist recovery criteria.'}


def paired_gain_interval(gains):
    from scipy.stats import binom
    values=np.asarray(gains,float);n=len(values)
    if values.shape!=(40,) or not np.isfinite(values).all() or (np.abs(values)>1).any():raise ValueError('All 40 bounded, finite paired IoU gains are required.')
    alpha=.05/(len(PROTOCOL['families'])*(len(PROTOCOL['methods'])-1))
    k=max(k for k in range(1,n//2+1) if 2*binom.cdf(k-1,n,.5)<=alpha)
    ordered=np.sort(values)
    return {'median_gain':float(np.median(values)),'lower':float(ordered[k-1]),'upper':float(ordered[n-k]),
        'order_index_k':k,'allocated_error':alpha,'binomial_error_bound':float(2*binom.cdf(k-1,n,.5)),
        'method':'independent_seed_pair_order_statistic_median_Bonferroni_v1'}


def diagnostic_baseline(features,eligible,loss,objective,limits,directory,models,threads,check,*,shallow):
    from catboost import CatBoostClassifier,Pool
    from confidenceguard.contracts import digest,strict_json
    from confidenceguard.investigation_membership import tabular,seal,diagnostic_model
    columns=[{'id':f,'kind':cells[0]['kind']} for f,cells in sorted(features.items()) if cells and cells[0]['kind'] not in {'text','asset'}]
    if not columns:return []
    matrix,categories,available,_=tabular(features,columns);ids=np.flatnonzero(eligible&available)
    if len(ids)<limits.minimum_discovery_support or len(np.unique(loss[ids]))<2:return []
    # This comparison binds binary error; do not imply qualification for other targets.
    if not set(np.unique(loss[ids]))<= {0.,1.}:raise RuntimeError('Benchmark target is not binary error.')
    pool=Pool(matrix[ids],label=loss[ids],cat_features=categories)
    model=CatBoostClassifier(iterations=1 if shallow else 256,depth=2 if shallow else 4,learning_rate=.05,l2_leaf_reg=3,
        random_seed=0,thread_count=threads,task_type='CPU',allow_writing_files=False,verbose=False,loss_function='Logloss',
        bootstrap_type='No',random_strength=0,one_hot_max_size=2,max_ctr_complexity=2)
    check('benchmark diagnostic fit');model.fit(pool);path=Path(directory)/'baseline-model.json';model.save_model(str(path),format='json',pool=pool)
    packet=strict_json(path.read_text());path.unlink()
    for name in ('model_guid','train_finish_time','training'):packet.get('model_info',{}).pop(name,None)
    raw=json.dumps(packet,sort_keys=True,separators=(',',':'),ensure_ascii=True);key=digest(raw);models[key]=raw
    canonical=diagnostic_model(raw);score=np.asarray(canonical.predict(Pool(matrix,cat_features=categories),prediction_type='RawFormulaVal',thread_count=threads),float)
    thresholds=sorted(set(float(np.quantile(score[ids],q,method='linear')) for q in (.2,.4,.6,.8,.9,.95,.975,.99)))
    proposals=[]
    for j,threshold in enumerate(thresholds):
        for upper in ([None,thresholds[j+1]] if j+1<len(thresholds) else [None]):
            mask=(score>=threshold)&eligible&available
            if upper is not None:mask&=score<upper
            if mask.sum()<limits.minimum_discovery_support:continue
            artifact=seal('catboost',{'model_digest':key,'columns':columns,'threshold':threshold,'upper':upper,
                'head_sign':1,'runtime':'catboost/1.2.10-cpu'},features=[c['id'] for c in columns],objective=objective.identity,models=models)
            proposals.append({'artifact':artifact,'complexity':(1 if shallow else 256)*(4 if shallow else 16),'head':'positive'})
    return proposals[:limits.candidates_per_strategy]


def geometric_baseline(representations,eligible,loss,objective,limits,models,check,*,clusters):
    from scipy.cluster.vq import kmeans2
    from confidenceguard.contracts import digest
    from confidenceguard.investigation_membership import seal,transform_vectors
    from confidenceguard.discovery_regions import distances
    proposals=[]
    for rep in representations.values():
        transform={'normalization':rep.get('normalization','none'),'mean':None,'components':None}
        raw=transform_vectors(rep['vectors'],transform);ids=np.flatnonzero(rep['available']&np.isfinite(raw).all(axis=1))
        if len(ids)>limits.geometric_rows:ids=ids[np.linspace(0,len(ids)-1,limits.geometric_rows,dtype=int)]
        if not len(ids):continue
        z=raw[ids];count=min(16,len(z))
        work=len(z)*count*z.shape[1]*(20 if clusters else 1)
        if work>limits.max_distance_operations:raise RuntimeError('Baseline distance admission exceeded.')
        if clusters:
            # Fit geometry before touching eligible/loss; target changes cannot alter centers.
            centers,_=kmeans2(z,count,iter=20,minit='++',seed=0,check_finite=True)
        else:
            cover=np.linspace(0,len(z)-1,min(8,count),dtype=int).tolist()
            risk=np.argsort(-np.where(eligible[ids],loss[ids],-np.inf),kind='stable').tolist()
            centers=z[list(dict.fromkeys(cover+risk))[:count]]
        d2=distances(z,centers);check('benchmark geometry fit')
        support=max(float(np.sqrt(np.quantile(np.min(d2,axis=1),.995,method='linear')))*1.5,float(np.finfo(float).eps))
        document=json.dumps({'schema_version':'confidenceguard.geometry/1.0','transform':transform,'centers':centers.tolist()},sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False)
        key=digest(document);models[key]=document;k=len(centers)
        base={'geometry_digest':key,'radii':[support]*k,'inner':[0.]*k,'components':[],
              'threshold':.5,'neighbors':1,'bandwidth':1.,'support_radius':support}
        choices=[]
        if clusters:
            owner=np.argmin(d2,axis=1)
            for j in range(k):choices.append((owner==j,{**base,'components':[j]}))
        else:
            radii=np.sqrt(np.quantile(d2,[.025,.05,.1,.2,.4,.6,.8],axis=0,method='linear'))
            for j in range(k):
                for radius in radii[:,j]:
                    p={**base,'components':[j],'radii':list(base['radii'])};p['radii'][j]=float(radius)
                    choices.append((d2[:,j]<=radius**2,p))
        for mask,parameters in choices:
            if np.count_nonzero(mask&eligible[ids])<limits.minimum_discovery_support:continue
            # k=1 in the existing kernel decoder is exact nearest-center membership;
            # no NUMEK landmark graph algorithm is fitted or credited here.
            artifact=seal('landmark' if clusters else 'geometric',parameters,representation=rep['id'],objective=objective.identity,models=models)
            proposals.append({'artifact':artifact,'complexity':1,'head':'positive'})
    return proposals[:limits.candidates_per_strategy]


def comparison_worker(spec,native,*,progress=None):
    from confidenceguard import compat
    from confidenceguard.contracts import digest
    from confidenceguard.investigation import arguments,prepared
    from confidenceguard.investigation_objectives import bind
    from confidenceguard.investigation_membership import apply
    from confidenceguard.investigation_reconciliation import reconcile
    from confidenceguard.discovery_rules import propose
    from confidenceguard.result import Inspection
    s,c,roots=arguments(spec,None,None)
    with prepared(s,c,roots,progress) as p:
        objective=bind(spec.objectives[0],p.store);keys,eligible,loss=objective.training('D');position={k:i for i,k in enumerate(keys)}
        di,df,dr=p.role_data('D');si,sf,sr=p.role_data('S');take=np.array([position[p.keys[i]] for i in di]);eligible=eligible[take];loss=loss[take]
        frozen={};timings={};models={}
        # Fit and select every baseline before any H metric is accessed.
        for method in PROTOCOL['methods'][1:]:
            started=time.monotonic()
            if method=='low_order_rules':proposals,_=propose(df,eligible,loss,objective,replace(spec.limits,max_depth=2),p.work.check)
            elif method in {'shallow_tree','single_diagnostic'}:
                p.reserve_diagnostic_fit();proposals=diagnostic_baseline(df,eligible,loss,objective,spec.limits,p.work.root,models,c.threads,p.work.check,shallow=method=='shallow_tree')
            else:proposals=geometric_baseline(dr,eligible,loss,objective,spec.limits,models,p.work.check,clusters=method=='error_blind_clusters')
            fit_seconds=time.monotonic()-started;candidates=[];byid={};cache={'_models':models,'_directory':str(p.work.root),'_population_size':len(si),'_threads':c.threads}
            for proposal in proposals:
                artifact=proposal['artifact'];cid=digest([spec.objectives[0].id,artifact['artifact_digest']])[:32]
                if cid in byid:continue
                mask=apply(artifact,sf,sr,cache=cache,check=p.work.check);evidence=p.evaluate(objective,'S',si,mask,artifact)
                candidate={'id':cid,'objective':objective.spec.to_dict(),'S':evidence,'complexity':proposal['complexity'],'_S_mask':np.packbits(mask['member'],bitorder='little').tobytes().hex()}
                candidates.append(candidate);byid[cid]=artifact
            _,_,selected=reconcile(candidates,1,len(si));frozen[method]=[byid[i] for i in selected]
            timings[method]={'fit_seconds':fit_seconds,'fit_and_S_selection_seconds':time.monotonic()-started,'proposed_candidates':len(candidates)}
        frozen['native_unified']=native['first'];models.update(native['models']);measurements={}
        for role in ('D','S','H'):
            indices,features,reps=p.role_data(role);truth=np.array([native['oracle'][int(json.loads(p.keys[i])[0])] for i in indices],bool)
            cache={'_models':models,'_directory':str(p.work.root),'_population_size':len(indices),'_threads':c.threads}
            for method,gates in frozen.items():
                member=np.zeros(len(indices),bool);available=np.ones(len(indices),bool);effects=[]
                for gate in gates:
                    mask=apply(gate,features,reps,cache=cache,check=p.work.check);member|=mask['member'];available&=mask['available']
                    effects.append(p.evaluate(objective,role,indices,mask,gate))
                measurements.setdefault(method,{})[role]={'recovery':pipeline.recovery(truth,member,available),'native_effects':effects,
                    'frozen_membership_sha256':digest({'member':np.packbits(member,bitorder='little').tobytes().hex(),'available':np.packbits(available,bitorder='little').tobytes().hex(),'planned':len(indices)})}
            if role=='H':
                member=np.zeros(len(indices),bool);available=np.ones(len(indices),bool)
                for gate in native['shortlist']:
                    mask=apply(gate,features,reps,cache=cache,check=p.work.check);member|=mask['member'];available&=mask['available']
                measurements['native_full_shortlist_secondary']=pipeline.recovery(truth,member,available|member)
        p.verify()
        actual_S=measurements['native_unified']['S']['native_effects']
        if actual_S!=native['first_S']:raise RuntimeError('Native first-gate S evidence changed in the common comparison evaluator.')
        return Inspection({'measurements':measurements,'method_times':timings,'frozen_artifact_digests':{m:[a['artifact_digest'] for a in gates] for m,gates in frozen.items()},
            'native_first_S_recomputed_equal':True,'baseline_native_fits':p.diagnostic_fits,'admitted_limits':spec.limits.to_dict(),'admitted_config':c.to_dict()}, {'status':'completed','peak_workspace_bytes':p.work.peak})


def trial(seed,family,panel,full_profile=False):
    from confidenceguard import investigate,compat
    from confidenceguard.investigation import configuration
    from confidenceguard.investigation_membership import dependency_digests
    small=panel=='development' and not full_profile
    n=1200 if small else PROTOCOL['qualification_units']
    with tempfile.TemporaryDirectory(prefix='numek-cg4-baseline-comparison-',dir='/private/tmp') as temporary:
        root=Path(temporary);spec,oracle,_=pipeline.generate(root,seed,n,family)
        if small:spec=replace(spec,limits=replace(spec.limits,max_nodes=2000,max_depth=4,candidates_per_strategy=32,shortlist=4,landmarks=32,neighbors=8,stability_replicates=1))
        native=investigate(spec);ids=native.data['investigation']['shortlist'];candidates={c['id']:c for c in native.data['investigation']['candidates']}
        chosen={cid:native.private['artifacts'][candidates[cid]['membership_artifact']] for cid in ids}
        dependencies=set().union(*(dependency_digests(gate) for gate in chosen.values())) if chosen else set()
        packet={'oracle':oracle.tolist(),'first':[chosen[ids[0]]] if ids else [],'shortlist':[chosen[i] for i in ids],
            'first_S':[candidates[ids[0]]['S']] if ids else [],
            'models':{key:native.private['models'][key] for key in dependencies}}
        measured=compat.supervise(comparison_worker,(spec,packet),configuration())
        return {'status':'completed','seed':seed,'family':family,'n':n,'input_sha256':{'predictions':pipeline.sha(root/'predictions.csv'),'vectors':pipeline.sha(root/'vectors.npy')},
            'comparison':measured.to_dict(),'baseline_execution':measured.execution,'native_execution':native.execution,'formal_confirmation_performed':False}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--panel',choices=PROTOCOL['seeds'],required=True);parser.add_argument('--family',choices=PROTOCOL['families'],required=True)
    parser.add_argument('--out',required=True);parser.add_argument('--count',type=int,default=1);parser.add_argument('--offset',type=int,default=0)
    parser.add_argument('--full-profile',action='store_true',help='Full population/default budgets on development seeds; not qualification evidence.')
    parser.add_argument('--worker',action='store_true');parser.add_argument('--seed',type=int);args=parser.parse_args()
    profile={'protocol':PROTOCOL,'harness_sha256':pipeline.sha(__file__),'base_harness_sha256':pipeline.sha(pipeline.__file__),
        'source_sha256':pipeline.identity(),'packages':pipeline.runtime_versions(),'panel':args.panel,'family':args.family,'full_profile':args.full_profile}
    if args.worker:
        started=time.monotonic()
        try:row=trial(args.seed,args.family,args.panel,args.full_profile)
        except Exception as exc:row={'status':'execution_failure','seed':args.seed,'error_code':getattr(exc,'code',None),'traceback':traceback.format_exc()}
        if profile['source_sha256']!=pipeline.identity() or profile['harness_sha256']!=pipeline.sha(__file__):row.update(status_before_invalidation=row['status'],status='invalidated_source_change')
        row.update(profile=profile,seconds=time.monotonic()-started)
        with Path(args.out).open('x') as stream:json.dump(row,stream,indent=2,sort_keys=True,allow_nan=False);stream.write('\n')
        return
    first,last=PROTOCOL['seeds'][args.panel]
    if args.offset<0 or args.count<1 or first+args.offset+args.count-1>last:parser.error('Outside locked seed panel.')
    out=Path(args.out);out.mkdir(parents=True,exist_ok=True)
    for seed in range(first+args.offset,first+args.offset+args.count):
        path=out/f'{seed}.json'
        if not path.exists():
            pending=path.with_suffix('.pending');command=[sys.executable,'-B',__file__,'--worker','--seed',str(seed),'--panel',args.panel,'--family',args.family,'--out',str(pending)]
            if args.full_profile:command+=['--full-profile']
            subprocess.run(command,check=True);pending.rename(path)
        row=json.loads(path.read_text())
        if row['status']!='completed' or row['seed']!=seed or row['profile']!=profile:raise RuntimeError('Preserve failed/mismatched comparison before diagnosis.')
        print(json.dumps({'seed':seed,'family':args.family,'status':row['status'],'seconds':row['seconds']}),flush=True)


if __name__=='__main__':main()
