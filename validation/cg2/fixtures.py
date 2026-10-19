"""Deterministic supplied-prediction fixtures; no predictor runs in the product."""
import csv
from pathlib import Path
import numpy as np


def prepare(directory,kind,*,rows=1200,classes=3,seed=20261019,samples=15):
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    rng=np.random.default_rng(seed);path=directory/(kind+'.csv');fields=['id','role','entity','cohort','outcome','prediction']
    roles=np.array(['F','S','C','E'])[np.minimum(np.arange(rows)*4//rows,3)]
    if kind=='binary':
        z=rng.normal(size=rows);truth=1/(1+np.exp(-z));outcome=rng.binomial(1,truth)
        logit=2.2*z+.5;p=1/(1+np.exp(-logit));pred=(p>=.5).astype(int)
        fields+=['probability','score','logit'];extra=np.c_[p,logit,logit]
        task={'kind':'binary_classification','outcome_definition':'Synthetic event','classes':['0','1'],'positive_class':'1'}
    elif kind=='multiclass':
        truth_logits=rng.normal(size=(rows,classes));truth=np.exp(truth_logits-truth_logits.max(axis=1,keepdims=True));truth/=truth.sum(axis=1,keepdims=True)
        outcome=np.array([rng.choice(classes,p=p) for p in truth])
        logits=1.8*truth_logits+np.linspace(-.4,.4,classes)
        p=np.exp(logits-logits.max(axis=1,keepdims=True));p/=p.sum(axis=1,keepdims=True);pred=p.argmax(axis=1)
        fields += [f'p{i}' for i in range(classes)]+[f'z{i}' for i in range(classes)];extra=np.c_[p,logits]
        task={'kind':'multiclass_classification','outcome_definition':'Synthetic class','classes':list(map(str,range(classes)))}
    else:
        pred=rng.normal(3,2,rows);scale=rng.uniform(.2,2.,rows);outcome=pred+scale*rng.normal(size=rows)
        quantiles=np.c_[pred-1.6448536269514722*scale,pred,pred+1.6448536269514722*scale]
        fields+=['scale','q05','q50','q95'];extra=np.c_[scale,quantiles]
        task={'kind':'regression','outcome_definition':'Synthetic heteroscedastic response','units':'response units'}
    with path.open('w',newline='') as f:
        writer=csv.writer(f);writer.writerow(fields)
        for i in range(rows):writer.writerow([str(i),roles[i],f'entity-{i}','A' if i%2 else 'B',str(outcome[i]),str(pred[i]),*extra[i]])
    run={'id':'original','source':'predictions','key_columns':['id'],'entity_columns':['entity'],'model':{'id':kind+'-supplied','version':'fixture-1','display_name':kind.title()+' supplied model'},'prediction':'prediction'}
    evaluation={'task':task,'sources':[{'id':'predictions','path':str(path.absolute())}],'runs':[run],
                'outcomes':{'source':'predictions','column':'outcome','key_columns':['id']},
                'cohorts':[{'id':'cohort','column':'cohort','categories':['A','B']}],'name':kind.title()+' CG2 qualification'}
    spec={'schema_version':'confidenceguard.study_spec/1.0','evaluation':evaluation,'roles':{'namespace':'synthetic-'+kind,'column':'role','unit':'entity'},
          'separation':{'base_predictions_independent':True,'evaluation_independent':True,'exchangeable_scores':True,'labels_representative':True}}
    if kind=='binary':
        run['probabilities']={'positive_column':'probability'};run['score']={'column':'score'}
        spec['methods']=[{'id':'platt','kind':'platt','run':'original','input':'score'},
                         {'id':'isotonic','kind':'isotonic','run':'original'},
                         {'id':'beta','kind':'beta','run':'original'},
                         {'id':'temperature','kind':'temperature','run':'original'},
                         {'id':'lac','kind':'lac','run':'original','parent':'selected:calibration','levels':['0.9','0.9999']}]
        spec['selections']=[{'id':'calibration','candidates':['platt','isotonic','beta','temperature']}]
        spec['representations']=[{'run':'original','binary_logit':'logit'}]
    elif kind=='multiclass':
        run['probabilities']={'columns':{str(i):f'p{i}' for i in range(classes)}}
        spec['representations']=[{'run':'original','logits':{str(i):f'z{i}' for i in range(classes)}}]
        spec['methods']=[{'id':'temperature','kind':'temperature','run':'original','input':'logits'},
                         {'id':'dirichlet','kind':'dirichlet','run':'original','regularization':.01},
                         {'id':'aps','kind':'aps','run':'original','parent':'temperature'},
                         {'id':'raps','kind':'raps','run':'original','parent':'temperature','penalty':.02,'k_reg':1}]
    else:
        sample_path=directory/'regression-samples.csv'
        with sample_path.open('w',newline='') as f:
            writer=csv.writer(f);writer.writerow(['id','draw','sample'])
            for i in range(rows):
                for j,v in enumerate(pred[i]+scale[i]*rng.normal(size=samples)):writer.writerow([i,j,v])
        evaluation['sources'].append({'id':'samples','path':str(sample_path.absolute())})
        run['intervals']=[{'id':'native90','lower':'q05','upper':'q95','coverage':.9}]
        spec['representations']=[{'run':'original','scale':'scale','scale_model':{'id':'supplied-scale','version':'1'},
                                 'quantiles':[{'level':'.05','column':'q05'},{'level':'.5','column':'q50'},{'level':'.95','column':'q95'}],
                                 'quantile_model':{'id':'supplied-quantiles','version':'1'},
                                 'samples':{'source':'samples','key_columns':['id'],'draw_column':'draw','value_column':'sample'}}]
        spec['methods']=[{'id':'split','kind':'split','run':'original','input':'point','levels':['0.9','0.9999']},
                         {'id':'normalized','kind':'normalized','run':'original','input':'normalized'},
                         {'id':'cqr','kind':'cqr','run':'original','input':'quantiles'}]
    return spec
