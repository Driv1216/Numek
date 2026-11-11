"""Pinned diagnostic serialization on lexical/state/OOS/threshold boundaries.

Train once, then reload and apply in separately invoked interpreter processes.
This verifies application parity, not failure-recovery qualification.
"""
import argparse
from dataclasses import replace
import hashlib
import importlib.metadata
import json
from pathlib import Path
import sys
import numpy as np
from confidenceguard.contracts import digest
from confidenceguard.feature_contracts import FeatureField
from confidenceguard.features import normalize,missing_cell
from confidenceguard.investigation_membership import tabular,validate_model,diagnostic_model,seal,apply


def inputs():
    categories=['1','1.0','01',' 1','1 ','é','e\u0301','True','true','["state","missing"]']+[f'group-{i}' for i in range(30)]
    fields=(FeatureField('category','category','categorical'),FeatureField('number','number','decimal'))
    train={'category':[],'number':[]};target=[]
    for i in range(1200):
        category=categories[i%len(categories)];number=str(i%17)
        train['category'].append(normalize(category,fields[0]));train['number'].append(normalize(number,fields[1]))
        target.append(int(i%len(categories) in {0,2,5,8,12,17,25,31} or i%17>13))
    extra=['never seen','１','\t1','é','e\u0301',None,'1.0','01']
    numeric=['9007199254740993','1e1000','1e-1000','-0','NaN',None,'.1','1.00000000000000000001']
    test={'category':[normalize(v,fields[0]) for v in extra],'number':[normalize(v,fields[1]) for v in numeric]}
    for state in ('missing','invalid','unavailable','not_retained'):
        test['category'].append(missing_cell('categorical',state));test['number'].append(missing_cell('decimal',state))
    columns=[{'id':f.id,'kind':f.kind} for f in fields]
    return train,np.array(target),test,columns


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--directory',required=True);parser.add_argument('--train',action='store_true');args=parser.parse_args()
    directory=Path(args.directory);directory.mkdir(parents=True,exist_ok=True)
    train,target,test,columns=inputs();matrix,cats,available,conversion=tabular(test,columns)
    if args.train:
        from catboost import CatBoostClassifier,Pool
        x,cat,_,_=tabular(train,columns);pool=Pool(x,label=target,cat_features=cat)
        model=CatBoostClassifier(iterations=256,depth=8,learning_rate=.05,l2_leaf_reg=3,random_seed=0,thread_count=2,task_type='CPU',allow_writing_files=False,verbose=False,loss_function='Logloss',bootstrap_type='No',random_strength=0,one_hot_max_size=2,max_ctr_complexity=2)
        model.fit(pool);original=np.asarray(model.predict(Pool(matrix,cat_features=cats),prediction_type='RawFormulaVal',thread_count=2)).reshape(-1)
        path=directory/'model.json';model.save_model(str(path),format='json',pool=pool)
        raw=path.read_text();validate_model(raw,digest(raw))
        (directory/'original.json').write_text(json.dumps({'scores':original.tolist(),'features':test,'columns':columns,'conversion':conversion},ensure_ascii=True,indent=2)+'\n')
    raw=(directory/'model.json').read_text();validate_model(raw,digest(raw));reference=json.loads((directory/'original.json').read_text())
    from catboost import Pool
    score=np.asarray(diagnostic_model(raw).predict(Pool(matrix,cat_features=cats),prediction_type='RawFormulaVal',thread_count=2)).reshape(-1)
    expected=np.array(reference['scores']);difference=float(np.max(np.abs(expected-score)));boundary=[]
    for threshold in sorted(set(float(v) for v in expected)):
        for point in (np.nextafter(threshold,-np.inf),threshold,np.nextafter(threshold,np.inf)):
            for upper in (None,float(np.nextafter(point,np.inf))):
                gate=seal('catboost',{'model_digest':digest(raw),'columns':columns,'threshold':float(point),'upper':upper,'head_sign':1,'runtime':'catboost/1.2.10-cpu'},features=list(test),models={digest(raw):raw})
                output=apply(gate,test,{},cache={'_models':{digest(raw):raw}})
                mask=(expected>=point)&available
                if upper is not None:mask&=expected<upper
                boundary.append(bool(np.array_equal(mask,output['member']) and np.array_equal(available,output['available'])))
    result={'schema_version':'numek.cg4_catboost_application_parity/1.0','python':sys.version,'catboost':importlib.metadata.version('catboost'),
        'model_sha256':hashlib.sha256(raw.encode()).hexdigest(),'score_max_abs_difference':difference,'score_tolerance':1e-12,
        'threshold_boundary_cases':len(boundary),'all_membership_boundaries_equal':all(boundary),'available':available.tolist(),
        'lexical_identity_tags_distinct':len(set(tabular({'category':train['category'][:40]},columns[:1])[0][:,0]))==40,
        'scope':'Data-only application/serialization, including categorical CTRs, missing/invalid/unseen/precision-loss states; not recovery or coverage qualification.'}
    result['passed']=difference<=1e-12 and all(boundary) and result['lexical_identity_tags_distinct']
    path=directory/('parity-py'+str(sys.version_info.major)+str(sys.version_info.minor)+'.json');path.write_text(json.dumps(result,sort_keys=True,indent=2)+'\n');print(json.dumps(result))
    return not result['passed']


if __name__=='__main__':raise SystemExit(main())
