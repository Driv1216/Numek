"""Deterministic supplied predictions; no predictor fitting/execution."""
import csv
from datetime import datetime, timezone, timedelta
from pathlib import Path
import numpy as np


def create(directory, *, kind='binary_classification', events=1200, classes=5, samples=0, seed=53):
    directory = Path(directory); directory.mkdir(parents=True, exist_ok=True)
    path = directory/'predictions.csv'; rng = np.random.default_rng(seed)
    columns = ['id','entity','when','available','due','outcome','prediction','region','feature','p']
    if kind == 'multiclass_classification': columns += ['p'+str(i) for i in range(classes)]
    if kind == 'regression': columns += ['scale','q05','q50','q95']
    origin = datetime(2026,1,1,tzinfo=timezone.utc)
    sample_path = directory/'samples.csv'
    sf = sample_path.open('w',newline='') if samples else None
    sample_writer = csv.writer(sf) if sf else None
    if sample_writer: sample_writer.writerow(['id','draw','value'])
    with path.open('w',newline='') as stream:
        writer = csv.DictWriter(stream,fieldnames=columns);writer.writeheader()
        for index in range(events):
            tick = origin+timedelta(days=index%365)
            feature=float(rng.normal()+(.4 if index%365>=181 else 0))
            p=float(rng.uniform(.03,.97));label=str(int(rng.random()<p));prediction=str(int(p>=.5))
            row={'id':str(index),'entity':'entity-'+str(index//3),'when':tick.isoformat(),
                 'available':(tick+timedelta(days=8)).isoformat(),'due':(tick+timedelta(days=7)).isoformat(),
                 'outcome':label,'prediction':prediction,'region':'north' if (index%7)<(5 if index%365>=181 else 3) else 'south',
                 'feature':feature,'p':p}
            if kind=='multiclass_classification':
                probabilities=rng.dirichlet(np.ones(classes));row['outcome']='class-'+str(rng.choice(classes,p=probabilities));row['prediction']='class-'+str(np.argmax(probabilities))
                row.update({'p'+str(i):float(v) for i,v in enumerate(probabilities)})
            if kind=='regression':
                point=2+feature;scale=.3+float(rng.random());row.update(outcome=point+scale*float(rng.normal()),prediction=point,scale=scale,q05=point-1.645*scale,q50=point,q95=point+1.645*scale)
                if sample_writer:
                    for draw,value in enumerate(point+scale*rng.normal(size=samples)):sample_writer.writerow([str(index),str(draw),float(value)])
            writer.writerow(row)
    if sf: sf.close()
    task={'kind':kind,'outcome_definition':'Synthetic observed outcome'}
    if kind!='regression': task.update(classes=['0','1'] if kind=='binary_classification' else ['class-'+str(i) for i in range(classes)])
    if kind=='binary_classification':task['positive_class']='1'
    if kind=='regression':task.update(units='synthetic units',material_error=1.)
    run={'id':'supplied','source':'predictions','model':{'id':'synthetic-'+kind,'version':'1','artifact_sha256':'0'*64},
         'key_columns':['id'],'entity_columns':['entity'],'prediction':'prediction','prediction_at':{'column':'when'},'role':'production'}
    if kind=='binary_classification':run['probabilities']={'positive_column':'p'}
    if kind=='multiclass_classification':run['probabilities']={'columns':{'class-'+str(i):'p'+str(i) for i in range(classes)}}
    if kind=='regression':run['intervals']=[{'id':'supplied90','lower':'q05','upper':'q95','coverage':.9}]
    evaluation={'task':task,'sources':[{'id':'predictions','path':str(path)}],'runs':[run],
                'outcomes':{'source':'predictions','column':'outcome','key_columns':['id'],'available_at':{'column':'available'},'due_at':{'column':'due'}}}
    if kind=='regression' and samples:
        evaluation['sources'].append({'id':'samples','path':str(sample_path)})
        evaluation={'schema_version':'confidenceguard.evaluation_spec/1.1','evaluation':evaluation,'roles':{'namespace':'synthetic-events','proportions':{'E':1}},
                    'representations':[{'run':'supplied','scale':'scale','scale_model':{'id':'supplied-scale','version':'1'},
                        'quantile_model':{'id':'supplied-quantiles','version':'1'},'quantiles':[{'level':'0.05','column':'q05'},{'level':'0.5','column':'q50'},{'level':'0.95','column':'q95'}],
                        'samples':{'source':'samples','key_columns':['id'],'draw_column':'draw','value_column':'value','meaning':'iid_monte_carlo'}}]}
    batch={'namespace':'synthetic-events','outcome_definition_version':'synthetic-outcome-v1','evaluation':evaluation,
           'bindings':[{'run':'supplied','features':{'region':'categorical','feature':'numeric'}}]}
    return batch


def specification(variants, *, cohort=True):
    selected=[v['id'] for v in variants]
    return {'namespace':'synthetic-events','variants':selected,'as_of':'2027-02-01T00:00:00Z',
            'windows':[{'id':'reference','start':'2026-01-01T00:00:00Z','end':'2026-07-01T00:00:00Z'},
                       {'id':'current','start':'2026-07-01T00:00:00Z','end':'2027-01-01T00:00:00Z'}],
            'comparisons':[{'id':'time-change','reference_window':'reference','current_window':'current','reference_variant':selected[0],'current_variant':selected[0]}],
            'cohorts':[{'id':'region','column':'region','categories':['north','south']}] if cohort else [],
            'features':{'region':'categorical','feature':'numeric'},'material_thresholds':{'mae':.1,'brier':.01}}
