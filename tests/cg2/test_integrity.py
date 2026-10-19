import copy
import csv
import json
import math
from pathlib import Path
import threading
import numpy as np
import pytest

from confidenceguard import EvaluationError,EvaluationResult,FittedMethod,study,fit_methods,apply_methods,inspect
from confidenceguard.contracts import digest
from confidenceguard.calibration import MethodUnavailable,transform
from confidenceguard.conformal import rank,value_state
from confidenceguard.method_contracts import MethodSpec,InferenceSpec,MethodLimits
from confidenceguard.fitted import bounded_json
from confidenceguard.methods import _execute2,_arguments2
from confidenceguard.inference import smooth_bootstrap
from .test_methods import binary_spec


def rewrite(path,fn):
    with path.open(newline='') as f:items=list(csv.DictReader(f))
    fn(items)
    with path.open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(items[0]));writer.writeheader();writer.writerows(items)


def test_exact_rank_does_not_round_near_integer():
    assert rank(1,'0.5000000000000000000000000000001')==2
    assert rank(1,'0.4999999999999999999999999999999')==1
    with pytest.raises(EvaluationError):MethodSpec('m','lac','r',levels=['1e-999999999'])


def test_selection_freezes_differing_inputs_and_failed_candidate(tmp_path,monkeypatch):
    spec=binary_spec(tmp_path,[{'id':'platt','kind':'platt','run':'original','input':'score'},
                               {'id':'beta','kind':'beta','run':'original'}])
    spec['selections']=[{'id':'choose','candidates':['platt','beta']}]
    rewrite(tmp_path/'predictions.csv',lambda rows:rows[61].update(p=''))
    import confidenceguard.methods as services
    original=services.transform
    def failure(definition,params,x,classes,positive):
        if definition.id=='beta':raise MethodUnavailable('Injected candidate failure.','numerical_transformation')
        return original(definition,params,x,classes,positive)
    monkeypatch.setattr(services,'transform',failure)
    s,c,roots=_arguments2(spec,None,None);result=_execute2(s,c,roots,'study',None)
    selection=result.data['cg2']['selections'][0];population=selection['common_population']
    assert population['denominator']==59
    assert population['candidate_native_input_support']['platt']==60
    assert population['candidate_native_input_support']['beta']==59
    assert selection['candidates']['beta']['status']=='disqualified'
    assert selection['candidates']['platt']['denominator']==59
    assert selection['candidates']['identity:choose']['denominator']==59
    assert selection['selected']!='beta'
    deltas=[m for m in result.data['measurements'] if m['metric']=='brier_right_minus_left']
    assert deltas and all(not m['data']['primary_comparison_allowed'] for m in deltas)
    assert all(m['denominator']==0 for m in deltas)


def test_fitting_populations_bind_inputs_and_reopen_counts(tmp_path):
    spec=binary_spec(tmp_path);first=fit_methods(spec)
    population=first.data['cg2']['fit_status']['beta']['fit_population']
    rewrite(tmp_path/'predictions.csv',lambda rows:rows[0].update(p='.21'))
    second=fit_methods(spec)
    assert population['id']!=second.data['cg2']['fit_status']['beta']['fit_population']['id']
    exact=second.to_private_dict();private=copy.deepcopy(second.private)
    exact['cg2']['fit_status']['beta']['fit_population']['denominator']+=1
    from confidenceguard.methods import assessment_basis
    exact['cg2']['assessment_basis_digest']=assessment_basis({k:v for k,v in exact.items() if k not in {'execution','binding'}})
    exact['binding']['analysis_digest']=digest({k:v for k,v in exact.items() if k!='binding'})
    private['analysis_digest']=exact['binding']['analysis_digest'];exact['binding']['private_manifest_digest']=digest(private)
    with pytest.raises(EvaluationError):EvaluationResult.from_dict(exact,private=private)


def test_safe_loader_rejects_literal_nonfinite_depth_and_parameters(tmp_path):
    with pytest.raises(EvaluationError):bounded_json('{"a":NaN}')
    with pytest.raises(EvaluationError):bounded_json('['*40+'0'+']'*40)
    with pytest.raises(EvaluationError):bounded_json('{"a":0,"a":1}')
    artifact=fit_methods(binary_spec(tmp_path)).private['fitted_methods'][0]
    bad=copy.deepcopy(artifact);bad['parameters']['coefficients'][0]=math.inf
    with pytest.raises(EvaluationError):FittedMethod(bad)
    saved=FittedMethod(artifact).save(tmp_path/'method.json')
    with pytest.raises(EvaluationError):FittedMethod.load(saved,allowed_roots=[])


def test_unknown_or_overlapping_roles_do_not_become_independent(tmp_path):
    spec=binary_spec(tmp_path);spec['roles']={'namespace':'events','partitions':[{'source':'predictions','role':'F','key_columns':['id']},{'source':'predictions','role':'E','key_columns':['id']}]}
    with pytest.raises(EvaluationError) as error:study(spec)
    assert error.value.code=='role_overlap'


def test_applied_missing_keys_stay_in_event_export(tmp_path):
    spec=binary_spec(tmp_path);fitted=fit_methods(spec)
    rewrite(tmp_path/'predictions.csv',lambda rows:rows[0].update(id=''))
    spec['methods']=[];spec['fitted_methods']=fitted.private['fitted_methods'];spec['roles']={'namespace':'new','column':'role'}
    rewrite(tmp_path/'predictions.csv',lambda rows:[row.update(role='E') for row in rows])
    spec['output_path']=str(tmp_path/'applied.jsonl')
    result=apply_methods(spec)
    lines=[json.loads(line) for line in (tmp_path/'applied.jsonl').read_text().splitlines()]
    assert len(lines)==241
    missing=next(line for line in lines[1:] if line['event_key'] is None)
    assert missing['probabilities'] is None and missing['reason']=='unavailable_input'
    assert result.data['cg2']['applications']['beta']['unavailable_records']==1


def test_cancelled_application_has_no_committed_file(tmp_path):
    spec=binary_spec(tmp_path);fitted=fit_methods(spec)
    spec['methods']=[];spec['fitted_methods']=fitted.private['fitted_methods'];spec['output_path']=str(tmp_path/'cancelled.jsonl')
    cancel=threading.Event();cancel.set()
    with pytest.raises(EvaluationError):apply_methods(spec,cancel=cancel)
    assert not (tmp_path/'cancelled.jsonl').exists()
    assert not list(tmp_path.glob('.cg2-stage-*'))


def test_bootstrap_no_degenerate_false_certainty_or_budget_fallback():
    values=np.tile([1.,1.,2.,1.],(100,1));request=InferenceSpec(mode='independent_rows',metrics=('bias',))
    degenerate=smooth_bootstrap(values,request,family_size=1,check=lambda *a:None)
    assert degenerate['status']=='unavailable' and degenerate['reason']=='degenerate_bootstrap_distribution'
    budget=InferenceSpec(mode='independent_rows',metrics=('bias',),work_units=1)
    blocked=smooth_bootstrap(values,budget,family_size=1,check=lambda *a:None)
    assert blocked['status']=='not_admitted' and 'inference_work_limit' in blocked['reasons']


def test_log_domain_preserves_loss_and_probability_ranking():
    method=MethodSpec('platt','platt','original',input='score')
    params={'coefficients':[1.,0.],'scalar_scale':1.,'mean':0.,'sd':1.}
    p,logs=transform(method,params,np.array([[800.],[900.]]),['0','1'],'1')
    assert p[0,0]==0 and logs[0,0]==-800
    assert logs[0,1]!=logs[1,1] or logs[0,0]!=logs[1,0]
    with pytest.raises(MethodUnavailable):transform(method,{**params,'coefficients':[1e308,0.]},np.array([[1e308]]),['0','1'],'1')
