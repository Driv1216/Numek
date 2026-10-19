import csv
import copy
import json
import math
import numpy as np
import pytest

from confidenceguard import (EvaluationError, ReliabilitySpec, fit_methods, study, evaluate,
                             FittedMethod, EvaluationResult)
from confidenceguard.contracts import digest
from confidenceguard.conformal import rank, construct, validate_output, value_state, read_value
from confidenceguard.method_contracts import MethodSpec, InferenceSpec
from confidenceguard.inference import preflight, smooth_bootstrap


def binary_spec(tmp_path,methods=None):
    path=tmp_path/'predictions.csv'
    rng=np.random.default_rng(77)
    with path.open('w',newline='') as f:
        w=csv.writer(f);w.writerow(['id','role','y','p','decision','score'])
        for i in range(240):
            p=.05+.9*((i%31)/30);y=int(rng.random()<p)
            w.writerow([str(i),('F','S','C','E')[i//60],y,p,int(p>=.5),math.log(p/(1-p))])
    base={'task':{'kind':'binary_classification','outcome_definition':'event','classes':['0','1'],'positive_class':'1'},
          'sources':[{'id':'predictions','path':str(path)}],
          'runs':[{'id':'original','source':'predictions','model':{'id':'model','version':'v1'},'key_columns':['id'],'prediction':'decision','probabilities':{'positive_column':'p'},'score':{'column':'score'}}],
          'outcomes':{'source':'predictions','column':'y','key_columns':['id']}}
    return {'schema_version':'confidenceguard.study_spec/1.0','evaluation':base,'roles':{'namespace':'events','column':'role'},
            'methods':methods or [{'id':'beta','kind':'beta','run':'original'}],
            'separation':{'base_predictions_independent':True,'evaluation_independent':True,'exchangeable_scores':True,'labels_representative':True}}


def test_safe_infinite_conformal_rank_and_empty_cqr():
    assert rank(9,'0.9')==9
    assert rank(1,'0.95')==2
    split=MethodSpec('split','split','original',input='point')
    output=construct(split,{'threshold':value_state(math.inf)},point=3.)
    validate_output(output)
    assert output['state']=='unbounded'
    cqr=MethodSpec('cqr','cqr','original',input='quantiles')
    empty=construct(cqr,{'threshold':value_state(-2.)},lower=0.,upper=1.)
    validate_output(empty)
    assert empty['state']=='empty' and empty['width']['value']==0


@pytest.mark.parametrize('value',[math.nan,float('-nan'),np.float64('nan')])
def test_nan_numeric_state_is_undefined_not_infinite(value):
    encoded=value_state(value)
    assert encoded=={'value':None,'value_state':'undefined','reason':'not_a_number'}
    assert read_value(json.loads(json.dumps(encoded,allow_nan=False))) is None
    assert value_state(value,state='undefined',reason='numerical_failure')['reason']=='numerical_failure'
    for state in ('finite','positive_infinity','negative_infinity'):
        with pytest.raises(EvaluationError,match='NaN'):value_state(value,state=state)
    with pytest.raises(EvaluationError):read_value(encoded,allowed=('finite','positive_infinity'))
    with pytest.raises(EvaluationError):
        validate_output({'state':'unbounded','lower':encoded,'upper':value_state(math.inf),'width':value_state(math.inf)})
    assert read_value(value_state(-math.inf))==-math.inf
    assert read_value(value_state(math.inf))==math.inf
    assert value_state(-.5)=={'value':-.5,'value_state':'finite'}


def test_fit_study_reopening_and_immutable_originals(tmp_path):
    spec=binary_spec(tmp_path,[{'id':'beta','kind':'beta','run':'original'},
                               {'id':'lac','kind':'lac','run':'original','parent':'beta','levels':['0.9','0.999']}])
    before=(tmp_path/'predictions.csv').read_bytes()
    result=study(spec)
    assert result.data['schema_version']=='confidenceguard.evaluation_result/1.1'
    assert len(result.private['fitted_methods'])==2
    assert len(result.data['cg2']['assessments'])==2
    assert (tmp_path/'predictions.csv').read_bytes()==before
    reopened=EvaluationResult.from_dict(result.to_private_dict(),private=result.private)
    assert reopened.data==result.data
    lac=FittedMethod.from_dict(next(v for v in result.private['fitted_methods'] if v['id']=='lac')).to_dict()
    assert lac['parameters']['thresholds'][1]['threshold']['value_state']=='positive_infinity'
    json.dumps(result.to_dict(),allow_nan=False)
    tampered=copy.deepcopy(lac);tampered['parameters']['thresholds'][0]['threshold']=value_state(math.inf)
    tampered['artifact_digest']=digest({k:v for k,v in tampered.items() if k!='artifact_digest'})
    with pytest.raises(EvaluationError):FittedMethod(tampered)
    undefined=copy.deepcopy(lac);undefined['parameters']['thresholds'][0]['threshold']=value_state(math.nan)
    undefined['artifact_digest']=digest({k:v for k,v in undefined.items() if k!='artifact_digest'})
    with pytest.raises(EvaluationError):FittedMethod(undefined)


def test_all_binary_calibrators_and_common_selection(tmp_path):
    methods=[{'id':kind,'kind':kind,'run':'original','input':'score' if kind=='platt' else 'probabilities'} for kind in ['platt','isotonic','beta','temperature']]
    spec=binary_spec(tmp_path,methods)
    spec['selections']=[{'id':'probability','candidates':['isotonic','beta','temperature']}]
    result=study(spec)
    assert set(result.data['cg2']['methods'])=={'platt','isotonic','beta','temperature','identity:probability'}
    selection=result.data['cg2']['selections'][0]
    assert selection['common_population']['denominator']==60
    assert all(v.get('denominator')==60 for v in selection['candidates'].values())
    assert selection['selected'] is not None


def test_bootstrap_adjusted_admission_and_pairing():
    spec=InferenceSpec(mode='independent_rows',metrics=('log_loss',),adjustment='bonferroni')
    admission=preflight(spec,100,100,10)
    assert admission['status']=='not_admitted'
    assert admission['minimum_nominal_replicates'] in {8000,8001}
    assert 'insufficient_tail_resolution' in admission['reasons']
    rng=np.random.default_rng(4);left=rng.normal(size=200);right=left+.3+rng.normal(0,.05,200)
    result=smooth_bootstrap(np.c_[left,np.ones(200),right,np.ones(200)],
                            InferenceSpec(mode='independent_rows',metrics=('bias',),replicates=3000),family_size=1,check=lambda *a:None)
    assert result['status']=='available' and result['lower']>.25


def test_evaluation_labels_cannot_change_fit(tmp_path):
    spec=binary_spec(tmp_path)
    fitted=fit_methods(spec).private['fitted_methods'][0]
    path=tmp_path/'predictions.csv'
    with path.open(newline='') as f:rows=list(csv.DictReader(f))
    for row in rows:
        if row['role']=='E':row['y']=str(1-int(row['y']))
    with path.open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    changed=fit_methods(spec).private['fitted_methods'][0]
    assert fitted['parameters']==changed['parameters']
    assert fitted['artifact_digest']==changed['artifact_digest']
