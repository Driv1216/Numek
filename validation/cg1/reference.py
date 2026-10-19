"""Development-only pinned predictors and independent metric/schema references.

Run with the isolated reference target on PYTHONPATH; never imported by runtime.
"""
import csv
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import sys
import time
import os
import uuid

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'validation/cg1'


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    import numpy as np
    from sklearn.datasets import load_wine
    from sklearn.linear_model import LogisticRegression,Ridge
    from sklearn.model_selection import train_test_split
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    from sklearn import metrics
    import jsonschema
    from confidenceguard import (EvaluationSpec,EvaluationConfig,evaluate,DisclosureSpec)
    from confidenceguard.schema import schemas,examples,openapi
    data=BASE/'data';results=BASE/'results';data.mkdir(parents=True,exist_ok=True);results.mkdir(parents=True,exist_ok=True)
    run_label=os.environ.get('CG1_RUN_LABEL',uuid.uuid4().hex[:12]);reports=results/'runs'/run_label;reports.mkdir(parents=True,exist_ok=False)
    definitions=schemas();jsonschema.Draft202012Validator.check_schema(definitions)
    for example in examples()['evaluations'].values():
        check={**definitions,'$ref':'#/$defs/EvaluationRequest'};jsonschema.validate(example,check)
    cases=[];seed=1742
    german=ROOT/'validation/data/prepared/german_credit.csv'
    with german.open() as f:records=list(csv.DictReader(f))
    columns=['duration_months','credit_amount','age','installment_rate','existing_credits','dependents']
    gx=np.array([[float(r[c]) for c in columns] for r in records]);gy=np.array([r['credit_risk'] for r in records]);classes=sorted(set(gy));positive='bad' if 'bad' in classes else classes[-1]
    cases.append(('binary',gx,gy,{'kind':'binary_classification','outcome_definition':'German Credit supplied credit_risk','classes':classes,'positive_class':positive},german,{'source':'Pinned NUMEK UCI German Credit preparation','features':columns}))
    wine=load_wine();wx=wine.data;wy=np.array([str(i) for i in wine.target]);winefile=Path(sys.modules['sklearn'].__file__).parent/'datasets/data/wine_data.csv'
    cases.append(('multiclass',wx,wy,{'kind':'multiclass_classification','outcome_definition':'UCI Wine supplied cultivar class','classes':['0','1','2']},winefile,{'source':'scikit-learn 1.7.2 bundled UCI Wine','publisher':'https://archive.ics.uci.edu/dataset/109/wine','license':'See pinned scikit-learn dataset description and UCI attribution','features':list(wine.feature_names)}))
    concrete=ROOT/'validation/regression/data/prepared/concrete.csv'
    with concrete.open() as f:records=list(csv.DictReader(f))
    cx=np.array([[float(v) for k,v in r.items() if k!='strength_mpa'] for r in records]);cy=np.array([float(r['strength_mpa']) for r in records])
    cases.append(('regression',cx,cy,{'kind':'regression','outcome_definition':'UCI Concrete supplied compressive strength','units':'MPa','material_error':10.},concrete,{'source':'Pinned NUMEK UCI Concrete preparation'}))
    report={'reference_only':True,'seed':seed,'python':platform.python_version(),'packages':{p:importlib.metadata.version(p) for p in ('scikit-learn','numpy','scipy','jsonschema')},'generator_sha256':sha(__file__),'cases':[],'schema_validation':'Draft202012 schemas and all transport examples passed'}
    for name,x,y,task,source,provenance in cases:
        classification=name!='regression';indices=np.arange(len(y));train,test=train_test_split(indices,test_size=.2,random_state=seed,stratify=y if classification else None)
        fit,cal=train_test_split(train,test_size=.2,random_state=seed,stratify=y[train] if classification else None)
        rows=[];predictions=[];probabilities=[];widths=[]
        for i in range(2):
            model=make_pipeline(StandardScaler(),LogisticRegression(C=1. if i==0 else .3,max_iter=2000,random_state=seed) if classification else Ridge(alpha=1. if i==0 else 10.))
            model.fit(x[fit],y[fit]);predictions.append(model.predict(x[test]))
            if classification:probabilities.append(model.predict_proba(x[test]))
            else:widths.append(float(np.quantile(abs(model.predict(x[cal])-y[cal]),.9)))
        for j,index in enumerate(test):
            row={'id':str(index),'outcome':str(y[index]),'cohort':'low' if x[index,0]<=float(np.median(x[fit,0])) else 'high'}
            for i in range(2):
                row[f'prediction{i}']=str(predictions[i][j])
                if classification:
                    for k,c in enumerate(task['classes']):row[f'p{i}_{k}']=format(float(probabilities[i][j,k]),'.17g')
                else:
                    row[f'lower{i}']=str(float(predictions[i][j]-widths[i]));row[f'upper{i}']=str(float(predictions[i][j]+widths[i]))
            rows.append(row)
        path=data/(name+'.csv')
        with path.open('w',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
        runs=[]
        for i in range(2):
            r={'id':f'model{i}','source':'predictions','key_columns':['id'],'model':{'id':name,'version':f'v{i+1}','display_name':f'{name.title()} model {i+1}'},'role':'evaluation','prediction':f'prediction{i}'}
            if classification:r['probabilities']={'columns':{c:f'p{i}_{k}' for k,c in enumerate(task['classes'])}}
            else:r['intervals']=[{'id':'90','lower':f'lower{i}','upper':f'upper{i}','coverage':.9,'provenance':'Empirical 90th percentile residual width on separate calibration split; no conformal guarantee claimed.'}]
            runs.append(r)
        specification={'task':task,'sources':[{'id':'predictions','path':str(path)}],'runs':runs,'outcomes':{'source':'predictions','column':'outcome','key_columns':['id']},'cohorts':[{'id':'stratum','column':'cohort','categories':['low','high']}],'comparison':{'left':'model0','right':'model1'},'policies':([{'id':'threshold','run':'model0','kind':'probability_threshold'}] if name=='binary' else [{'id':'abstention','run':'model0','kind':'confidence_abstention'}] if classification else [{'id':'width','run':'model0','kind':'interval_abstention','interval':'90'}]),'name':name.title()+' pinned prediction evaluation'}
        s=EvaluationSpec.from_dict(specification);jsonschema.validate(s.to_dict(),definitions)
        saved=s.to_dict();saved['sources'][0]['path']=path.name;(data/(name+'.json')).write_text(json.dumps(saved,indent=2)+'\n')
        config=EvaluationConfig(sampling={'mode':'independent_rows'})
        tick=time.monotonic();result=evaluate(s,config);duration=time.monotonic()-tick;checks=[]
        for i in range(2):
            actual={m['metric']:m for m in result.data['measurements'] if m['run']==f'model{i}' and m['scope']=='overall'}
            if classification:
                p=probabilities[i]
                expected={'accuracy':metrics.accuracy_score(y[test],predictions[i]),'log_loss':metrics.log_loss(y[test],p,labels=task['classes']),'brier':float(np.mean(np.sum((p-(y[test,None]==np.array(task['classes'])[None,:]))**2,axis=1)))/(2 if name=='binary' else 1)}
                if name=='binary':
                    py=p[:,task['classes'].index(task['positive_class'])];binary=y[test]==task['positive_class']
                    expected.update(roc_auc=metrics.roc_auc_score(binary,py),average_precision=metrics.average_precision_score(binary,py))
            else:expected={'mae':metrics.mean_absolute_error(y[test],predictions[i]),'rmse':float(np.sqrt(metrics.mean_squared_error(y[test],predictions[i]))),'bias':float(np.mean(predictions[i]-y[test])),'r2':metrics.r2_score(y[test],predictions[i])}
            for metric,value in expected.items():
                observed=actual[metric]['value'];assert np.isclose(observed,value,rtol=1e-10,atol=1e-12),(name,i,metric,observed,value)
                checks.append({'run':f'model{i}','metric':metric,'expected':float(value),'observed':observed})
        jsonschema.validate(result.to_private_dict(),{**definitions,'$ref':'#/$defs/Result'})
        artifacts=result.generate_artifacts(reports/(name+'.html'),json_path=reports/(name+'.json'))
        report['cases'].append({'name':name,'source_sha256':sha(source),'prediction_sha256':sha(path),'provenance':provenance,'source_rows':len(y),'fit_indices_sha256':hashlib.sha256(fit.tobytes()).hexdigest(),'calibration_indices_sha256':hashlib.sha256(cal.tobytes()).hexdigest(),'evaluation_indices_sha256':hashlib.sha256(test.tobytes()).hexdigest(),'fit_rows':len(fit),'calibration_rows':len(cal),'evaluation_rows':len(test),'disjoint_splits':not(set(fit)&set(cal) or set(fit)&set(test) or set(cal)&set(test)),'checks':checks,'whole_evaluation_seconds':duration,'execution':result.execution,'report_sha256':sha(artifacts.html_path)})
    (results/'reference.json').write_text(json.dumps(report,indent=2)+'\n')
    bundle=ROOT/'src/confidenceguard/schemas';bundle.mkdir(exist_ok=True)
    for filename,value in [('contracts.json',definitions),('openapi.json',openapi()),('examples.json',examples())]:(bundle/filename).write_text(json.dumps(value,indent=2)+'\n')
    print(json.dumps({'cases':len(report['cases']),'metric_checks':sum(len(c['checks']) for c in report['cases']),'schema_validation':report['schema_validation']}))


if __name__=='__main__':main()
