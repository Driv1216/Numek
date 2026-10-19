import json
from dataclasses import replace
import math
import pytest
from confidenceguard import *
from confidenceguard.engine import _execute


def spec(tmp_path,text,kind='binary_classification',**run):
    p=tmp_path/'input.csv';p.write_text(text)
    task=TaskDefinition(kind,'supplied outcome',classes=('0','1') if kind=='binary_classification' else ('a','b','c') if kind=='multiclass_classification' else (),positive_class='1' if kind=='binary_classification' else None)
    r=PredictionRunSpec('model','data',ModelIdentity('model','v1'),key_columns=('id',),**run)
    return EvaluationSpec(task,(SourceSpec('data',str(p)),),(r,),OutcomeSpec('data','y',('id',)))


def core(s,c=None):
    c=c or EvaluationConfig();return _execute(s,c,(str(__import__('pathlib').Path(s.sources[0].path).parent),),False,None).seal()


def measurement(r,metric,scope='overall',run='model'):
    return next(m for m in r.data['measurements'] if m['metric']==metric and m['scope']==scope and m['run']==run)


def test_binary_probability_only_and_explicit_derivation(tmp_path):
    s=spec(tmp_path,'id,y,p\na,0,0.1\nb,1,0.8\nc,0,0.7\nd,1,0.8\n',probabilities=ProbabilitySpec('p'))
    r=core(s)
    assert measurement(r,'accuracy')['value'] is None
    assert measurement(r,'brier')['value']==pytest.approx((.01+.04+.49+.04)/4)
    assert measurement(r,'roc_auc')['value']==1
    assert measurement(r,'average_precision')['value']==1
    d=replace(s.runs[0],decision=DecisionSpec(rule='probability_threshold',threshold=.5))
    hypothetical=core(replace(s,runs=(d,)))
    assert measurement(hypothetical,'accuracy')['value']==.75
    assert measurement(hypothetical,'accuracy')['basis']=='simulated'
    assert hypothetical.data['runs'][0]['decision_provenance']['origin']=='derived'


def test_score_native_thresholds_and_ties(tmp_path):
    s=spec(tmp_path,'id,y,s\na,1,10\nb,0,10\nc,1,20\nd,0,0\n',score=ScoreSpec('s'))
    s=replace(s,policies=(DecisionPolicySpec('native','model','score_threshold'),))
    r=core(s)
    assert measurement(r,'roc_auc')['value']==.875
    assert measurement(r,'average_precision')['value']==pytest.approx(5/6)
    points=measurement(r,'policy_curve')['data']['points']
    assert {p['threshold'] for p in points if p['state']=='finite'}=={0,10,20}
    assert next(p for p in points if p['threshold']==10)['accepted']==3


def test_multiclass_ties_and_zero_probability(tmp_path):
    s=spec(tmp_path,'id,y,pa,pb,pc\n1,a,.5,.5,0\n2,b,1,0,0\n3,c,0,0,1\n','multiclass_classification',probabilities=ProbabilitySpec(columns={'a':'pa','b':'pb','c':'pc'}),decision=DecisionSpec(rule='probability_argmax'))
    r=core(s)
    assert measurement(r,'accuracy')['denominator']==2
    assert measurement(r,'log_loss')['value_state']=='positive_infinity'
    assert measurement(r,'brier')['value']==pytest.approx(2.5/3)
    assert 'Infinity' not in json.dumps(r.to_dict())


def test_regression_intervals_and_scale(tmp_path):
    s=spec(tmp_path,'id,y,p,l,u\n1,1,2,0,2\n2,3,1,2,4\n3,5,5,6,8\n','regression',prediction='p',intervals=(PredictionIntervalSpec('90','l','u',.9),))
    r=core(s)
    assert measurement(r,'mae')['value']==1
    assert measurement(r,'rmse')['value']==pytest.approx(math.sqrt(5/3))
    assert measurement(r,'bias')['value']==pytest.approx(-1/3)
    assert measurement(r,'r2')['value']==pytest.approx(.375)
    assert measurement(r,'interval_coverage')['value']==pytest.approx(2/3)
    assert measurement(r,'central_interval_score')['value']==pytest.approx(26/3)


def test_abstained_candidates_and_native_issuance(tmp_path):
    s=spec(tmp_path,'id,y,p,state,prob\n1,1,1,issued,.9\n2,0,1,abstained,.8\n3,0,,failed,.7\n',prediction='p',probabilities=ProbabilitySpec('prob'),decision=DecisionSpec(state_column='state',candidate_evaluation=True))
    r=core(s)
    assert measurement(r,'accuracy')['value']==1
    assert measurement(r,'candidate_accuracy')['value']==.5
    assert measurement(r,'brier')['denominator']==3


def test_paired_inline_authority_context_and_shuffle(tmp_path):
    a=spec(tmp_path,'id,y,p,g\na,1,1,A\nb,0,1,B\n',prediction='p',inline_outcome='y')
    p=tmp_path/'other.csv';p.write_text('id,y,p,g\nb,1,0,B\na,1,1,A\n')
    b=PredictionRunSpec('other','other',ModelIdentity('other','v2'),key_columns=('id',),prediction='p',inline_outcome='y')
    s=replace(a,sources=(*a.sources,SourceSpec('other',str(p))),runs=(*a.runs,b),comparison=ComparisonSpec('model','other'))
    assert 'conflicting_asserted_outcome_copy' in core(s).data['comparison']['blocked_reasons']
    b=replace(b,inline_outcome_role='non_authoritative_copy')
    r=core(replace(s,runs=(s.runs[0],b)))
    assert not r.data['comparison']['blocked_reasons']
    assert measurement(r,'accuracy_right_minus_left','paired','other')['value']==.5


def test_cohort_privacy_and_reopening(tmp_path):
    s=spec(tmp_path,'id,y,p,g\n'+''.join(f'{i},{i%2},{i%2},{"SECRET" if i==0 else "COMMON"}\n' for i in range(30)),prediction='p')
    s=replace(s,cohorts=(CohortSpec('segment','g',categories=('SECRET','COMMON')),))
    r=core(s);shared=r.to_dict()
    assert not any(m['scope'].startswith('cohort_0') for m in shared['measurements'])
    assert 'SECRET' not in json.dumps(shared)
    reopened=EvaluationResult.from_dict(r.to_private_dict(),private=r.private)
    assert reopened.to_dict()==shared
    with pytest.raises(EvaluationError):EvaluationResult.from_dict(shared,private=r.private)


def test_supervised_api_and_source_confirmation(tmp_path):
    s=spec(tmp_path,'id,y,p\na,0,0\nb,1,1\n',prediction='p')
    inspection=inspect(s)
    r=evaluate(s,expected_fingerprint=inspection['fingerprint'])
    assert measurement(r,'accuracy')['value']==1
    assert r.execution['peak_worker_rss_bytes']>0
    __import__('pathlib').Path(s.sources[0].path).write_text('id,y,p\na,1,0\n')
    with pytest.raises(EvaluationError):evaluate(s,expected_fingerprint=inspection['fingerprint'])
