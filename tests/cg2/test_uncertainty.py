import csv
import math
import json
import numpy as np
import pytest
from confidenceguard import study,fit_methods,apply_methods,evaluate,EvaluationError,EvaluationResult
from confidenceguard.uncertainty import empirical_crps,pinball,interval_score


def regression_spec(tmp_path):
    rng=np.random.default_rng(11);path=tmp_path/'regression.csv';sample=tmp_path/'samples.csv'
    with path.open('w',newline='') as f,sample.open('w',newline='') as sf:
        w=csv.writer(f);s=csv.writer(sf);w.writerow(['id','role','y','point','scale','q05','q50','q95']);s.writerow(['id','draw','value'])
        for i in range(240):
            point=float(i%17)/3;scale=.2+(i%7)/5;y=point+scale*rng.normal()
            w.writerow([i,('F','S','C','E')[i//60],y,point,scale,point-1.64*scale,point,point+1.64*scale])
            for draw,v in enumerate(point+scale*rng.normal(size=9)):s.writerow([i,draw,v])
    evaluation={'task':{'kind':'regression','outcome_definition':'continuous outcome','units':'units'},'sources':[{'id':'p','path':str(path)},{'id':'samples','path':str(sample)}],
                'runs':[{'id':'original','source':'p','model':{'id':'model','version':'1'},'key_columns':['id'],'prediction':'point','intervals':[{'id':'native','lower':'q05','upper':'q95','coverage':.9}]}],
                'outcomes':{'source':'p','column':'y','key_columns':['id']}}
    return {'schema_version':'confidenceguard.study_spec/1.0','evaluation':evaluation,'roles':{'namespace':'events','column':'role'},
            'representations':[{'run':'original','scale':'scale','scale_model':{'id':'scale','version':'1'},'quantile_model':{'id':'quantiles','version':'1'},
                                'quantiles':[{'level':'.05','column':'q05'},{'level':'.5','column':'q50'},{'level':'.95','column':'q95'}],
                                'samples':{'source':'samples','key_columns':['id'],'draw_column':'draw','value_column':'value'}}],
            'methods':[{'id':'split','kind':'split','run':'original','input':'point','levels':['0.9','0.999']},
                       {'id':'normalized','kind':'normalized','run':'original','input':'normalized','levels':['0.9']},
                       {'id':'cqr','kind':'cqr','run':'original','input':'quantiles','levels':['0.9']}],
            'separation':{'base_predictions_independent':True,'evaluation_independent':True,'exchangeable_scores':True,'labels_representative':True}}


def test_regression_distributions_and_unbounded_efficiency(tmp_path):
    result=study(regression_spec(tmp_path))
    assert set(result.data['cg2']['methods'])=={'split','normalized','cqr'}
    metrics=result.data['measurements']
    assert any(m['metric']=='empirical_crps' and m['value_state']=='finite' for m in metrics)
    infinite=next(m for m in metrics if m['run']=='split' and m['scope']=='overall' and m['metric']=='interval_efficiency@0.999')
    assert infinite['value_state']=='positive_infinity' and infinite['denominator']==60
    paired=next(m for m in metrics if m['run']=='cqr' and m['metric']=='interval_coverage@0.9_right_minus_left')
    assert paired['denominator']==60
    EvaluationResult.from_dict(result.to_private_dict(),private=result.private)


def test_empirical_crps_matches_independent_pairwise_oracle():
    x=np.array([-2.,-1.,.5,4.]);y=1.3
    reference=np.abs(x-y).mean()-.5*np.abs(x[:,None]-x).mean()
    assert empirical_crps(x,y)==pytest.approx(reference)
    assert pinball(2,1,.9)==pytest.approx(.9)
    assert interval_score(3,0,2,.1)==pytest.approx(22)


def test_multiclass_temperature_dirichlet_and_sets(tmp_path):
    path=tmp_path/'multi.csv';rng=np.random.default_rng(22)
    with path.open('w',newline='') as f:
        w=csv.writer(f);w.writerow(['id','role','y','decision','p0','p1','p2','z0','z1','z2'])
        for i in range(360):
            z=rng.normal(size=3);p=np.exp(z-z.max());p/=p.sum();y=rng.choice(3,p=p)
            w.writerow([i,('F','S','C','E')[i//90],str(y),str(p.argmax()),*p,*z])
    evaluation={'task':{'kind':'multiclass_classification','outcome_definition':'class','classes':['0','1','2']},'sources':[{'id':'p','path':str(path)}],
                'runs':[{'id':'original','source':'p','model':{'id':'model','version':'1'},'key_columns':['id'],'prediction':'decision','probabilities':{'columns':{'0':'p0','1':'p1','2':'p2'}}}],
                'outcomes':{'source':'p','column':'y','key_columns':['id']}}
    spec={'schema_version':'confidenceguard.study_spec/1.0','evaluation':evaluation,'roles':{'namespace':'events','column':'role'},
          'representations':[{'run':'original','logits':{'0':'z0','1':'z1','2':'z2'}}],
          'methods':[{'id':'temperature','kind':'temperature','run':'original','input':'logits'},
                     {'id':'dirichlet','kind':'dirichlet','run':'original','regularization':.01},
                     {'id':'aps','kind':'aps','run':'original'},
                     {'id':'raps','kind':'raps','run':'original','parent':'temperature','penalty':.02,'k_reg':1}]}
    result=study(spec)
    assert set(result.data['cg2']['methods'])=={'temperature','dirichlet','aps','raps'}
    assert any(m['metric']=='set_coverage@0.9' and m['denominator']==90 for m in result.data['measurements'])


def test_reapplication_is_unvalidated_and_collision_safe(tmp_path):
    from .test_methods import binary_spec
    spec=binary_spec(tmp_path)
    fitted=study(spec)
    application=dict(spec);application['methods']=[];application['fitted_methods']=fitted.private['fitted_methods']
    application['roles']={'namespace':'new-events','proportions':{'E':1}}
    application['evaluation']=dict(spec['evaluation']);application['evaluation'].pop('outcomes')
    application['output_path']=str(tmp_path/'predictions.jsonl')
    result=apply_methods(application)
    assert result.data['cg2']['assessments']==[]
    assert all(v['application_state']=='applied_unvalidated' for v in result.data['cg2']['evidence_views'].values())
    assert len((tmp_path/'predictions.jsonl').read_text().splitlines())==241
    assert (tmp_path/'predictions.jsonl').stat().st_mode&0o077==0
    assert not list(tmp_path.glob('.cg2-stage-*'))
    with pytest.raises(Exception):apply_methods(application)
