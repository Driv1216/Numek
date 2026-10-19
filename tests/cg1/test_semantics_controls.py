from dataclasses import replace
import io
import json
from pathlib import Path
import pytest
from confidenceguard import *
from confidenceguard.contracts import strict_json,digest
from .test_analysis import spec,core,measurement
from .test_interfaces import BASE,terminal
from datatrust.web import create_app


def paired(tmp_path,left,right,**kwargs):
    kind=kwargs.pop('kind','binary_classification')
    s=spec(tmp_path,left,kind,prediction='p',**kwargs)
    p=tmp_path/'right.csv';p.write_text(right)
    r=PredictionRunSpec('right','right',ModelIdentity('right','v2'),key_columns=('id',),prediction='p',**kwargs)
    return replace(s,sources=(*s.sources,SourceSpec('right',str(p))),runs=(*s.runs,r),comparison=ComparisonSpec('model','right'))


def test_duplicate_joins_are_not_cartesian(tmp_path):
    s=paired(tmp_path,'id,y,p\nx,1,1\nx,1,0\n','id,y,p\nx,1,1\nx,1,0\n')
    r=core(s)
    assert r.data['comparison']['shared']==1
    assert 'ambiguous_prediction_identities' in r.data['comparison']['blocked_reasons']
    assert measurement(r,'accuracy')['denominator']==0


def test_temporal_and_horizon_compatibility(tmp_path):
    s=paired(tmp_path,'id,y,p,t\nx,1,1,2025-01-01T00:00:00Z\n','id,y,p,t\nx,1,1,2025-01-02T00:00:00Z\n',prediction_at=ClockSpec('t'))
    assert 'different_information_cutoffs' in core(s).data['comparison']['blocked_reasons']
    r=replace(s.runs[1],horizon='30 days')
    assert 'different_horizons' in core(replace(s,runs=(s.runs[0],r))).data['comparison']['blocked_reasons']


def test_context_conflicts_block_only_affected_cohort(tmp_path):
    s=paired(tmp_path,'id,y,p,g\nx,1,1,A\ny,0,0,B\n','id,y,p,g\nx,1,1,B\ny,0,0,B\n')
    s=replace(s,context=ContextSnapshotSpec('data',('id',),assertions={'right':{'g':'g'}}),cohorts=(CohortSpec('group','g',categories=('A','B')),))
    r=core(s)
    assert not r.data['comparison']['blocked_reasons']
    assert any(c.get('reason')=='conflicting_canonical_context_assertion' for c in r.data['checks'])
    assert not any(m['scope'].endswith('/paired') and m['scope'].startswith('cohort_0') for m in r.data['measurements'])
    assert r.data['coverage']['context_snapshot']['snapshot_digest']


def test_paired_failure_witnesses_bind_both_predictions_and_outcome(tmp_path):
    s=paired(tmp_path,'id,y,p\nx,1,0\ny,0,0\n','id,y,p\nx,1,1\ny,0,1\n')
    r=core(s);m=next(m for m in r.data['measurements'] if m['scope']=='paired' and m['metric']=='error_transitions')
    ref=m['evidence_refs'][0]
    assert len(r.private['locators'][ref]['related'])==2
    assert r.resolve_evidence(ref,allowed_roots=(str(tmp_path),))['status']=='resolved'
    with pytest.raises(EvaluationError):r.resolve_evidence(ref,allowed_roots=(str(tmp_path),),reveal_values='false')
    s=paired(tmp_path,'id,y,p\nx,1,3\ny,2,2\n','id,y,p\nx,1,1\ny,2,3\n',kind='regression')
    r=core(s);m=next(m for m in r.data['measurements'] if m['scope']=='paired' and m['metric']=='absolute_error_transitions')
    assert m['data']['right_smaller_error']==1 and m['data']['right_larger_error']==1
    assert m['evidence_refs']


def test_paired_native_scores_and_matched_intervals(tmp_path):
    s=paired(tmp_path,'id,y,p\nx,1,20\ny,0,-4\nz,1,5\n','id,y,p\nx,1,2\ny,0,9\nz,1,5\n')
    runs=tuple(replace(r,prediction=None,score=ScoreSpec('p')) for r in s.runs)
    r=core(replace(s,runs=runs))
    m=next(m for m in r.data['measurements'] if m['scope']=='paired' and m['metric']=='roc_auc_right_minus_left')
    assert m['denominator']==3 and m['value']==-1
    s=paired(tmp_path,'id,y,p,lo,hi\nx,1,1,0,2\ny,3,3,2,4\n','id,y,p,lo,hi\nx,1,1,0,2\ny,3,3,,\n',kind='regression')
    iv=PredictionIntervalSpec('90','lo','hi',.9)
    s=replace(s,runs=tuple(replace(run,intervals=(iv,)) for run in s.runs))
    r=core(s)
    m=next(m for m in r.data['measurements'] if m['scope']=='paired' and m['metric']=='interval_coverage_right_minus_left')
    assert m['denominator']==1 and m['value']==0


def test_paired_infinite_loss_difference_is_not_zero(tmp_path):
    s=paired(tmp_path,'id,y,p\nx,1,0\ny,0,1\n','id,y,p\nx,1,.8\ny,0,.2\n')
    s=replace(s,runs=tuple(replace(r,prediction=None,probabilities=ProbabilitySpec('p')) for r in s.runs))
    r=core(s)
    m=next(m for m in r.data['measurements'] if m['scope']=='paired' and m['metric']=='log_loss_right_minus_left')
    assert m['value_state']=='negative_infinity' and m['value'] is None


def test_asof_maturity_and_label_states(tmp_path):
    s=spec(tmp_path,'id,y,p,status,available,due\n1,1,1,final,2025-01-01T00:00:00Z,2025-01-01T00:00:00Z\n2,0,0,final,2025-01-03T00:00:00Z,2025-01-01T00:00:00Z\n3,1,1,provisional,2025-01-01T00:00:00Z,2025-01-01T00:00:00Z\n4,0,0,final,2025-01-01T00:00:00Z,2025-01-03T00:00:00Z\n',prediction='p')
    o=replace(s.outcomes,status_column='status',available_at=ClockSpec('available'),due_at=ClockSpec('due'))
    r=core(replace(s,outcomes=o,as_of='2025-01-02T00:00:00Z'))
    assert measurement(r,'accuracy')['denominator']==1
    states=r.data['coverage']['run_populations']['model']['outcome_states']
    assert states['outcome_not_available_as_of']==1 and states['unresolved_or_immature_outcome']==1


def test_independent_intervals_and_repeated_entities(tmp_path):
    s=spec(tmp_path,'id,y,p,entity\n1,1,1,A\n2,1,0,A\n',prediction='p')
    c=EvaluationConfig(sampling=SamplingSpec('independent_rows'))
    interval=measurement(core(s,c),'accuracy')['uncertainty']
    assert interval['lower']==pytest.approx(.09453120573423074)
    repeated=replace(s.runs[0],entity_columns=('entity',))
    assert 'uncertainty' not in measurement(core(replace(s,runs=(repeated,)),c),'accuracy')


def test_score_direction_and_multiclass_score_only(tmp_path):
    s=spec(tmp_path,'id,y,s\n1,1,-20\n2,0,30\n',score=ScoreSpec('s',direction='lower'),decision=DecisionSpec(rule='score_threshold',threshold=0))
    r=core(s);assert measurement(r,'accuracy')['value']==1 and measurement(r,'roc_auc')['value']==1
    s=spec(tmp_path,'id,y,sa,sb,sc\n1,a,10,10,0\n2,c,0,0,8\n','multiclass_classification',score=ScoreSpec(columns={'a':'sa','b':'sb','c':'sc'},meaning='class_scores'),decision=DecisionSpec(rule='score_argmax',tie_policy='class_order'))
    r=core(s);assert measurement(r,'accuracy')['value']==1
    assert not any(m['metric']=='brier' for m in r.data['measurements'])


def test_regression_selector_keeps_unlabeled_coverage(tmp_path):
    s=spec(tmp_path,'id,y,p,u\n1,1,1,1\n2,,5,2\n','regression',prediction='p',selection=ScoreSpec('u',meaning='selection',direction='lower'))
    s=replace(s,policies=(DecisionPolicySpec('selection','model','selection_abstention',thresholds=(2,)),))
    curve=measurement(core(s),'policy_curve')
    assert curve['denominator']==2
    p=next(p for p in curve['data']['points'] if p['state']=='finite')
    assert p['coverage']==1 and p['observed_label_coverage']==.5 and p['accepted_mae']==0


def test_multiclass_abstention_and_costs_are_finite_json(tmp_path):
    s=spec(tmp_path,'id,y,p,pa,pb,pc\n1,a,a,.9,.1,0\n2,b,a,.6,.4,0\n3,c,c,0,.1,.9\n','multiclass_classification',prediction='p',probabilities=ProbabilitySpec(columns={'a':'pa','b':'pb','c':'pc'}))
    costs={c:{y:0 if c==y else 4 for y in s.task.classes} for c in s.task.classes};costs['abstained']={c:1 for c in s.task.classes}
    s=replace(s,policies=(DecisionPolicySpec('abstain','model','confidence_abstention',thresholds=(.8,),costs=costs),))
    r=core(s);p=next(p for p in measurement(r,'policy_curve')['data']['points'] if p['state']=='finite')
    assert p['accepted']==2 and p['accepted_error_rate']==0 and p['empirical_cost']==pytest.approx(1/3)
    json.dumps(r.to_private_dict(),allow_nan=False)


def test_unlabeled_invalid_probabilities_and_finite_json(tmp_path):
    s=spec(tmp_path,'id,y,p\n1,,.9\n2,,1e-400\n3,,1.1\n',probabilities=ProbabilitySpec('p'))
    r=core(replace(s,outcomes=None));assert measurement(r,'brier')['value'] is None
    assert r.data['runs'][0]['facts']['invalid_probabilities']==2
    with pytest.raises(ValueError):strict_json('{"x": 1e999}')
    with pytest.raises(ValueError):strict_json('{"x":1,"x":2}')
    with pytest.raises(ValueError):EvaluationSpec.from_dict({**s.to_dict(),'typo':True})


def test_probability_decimal_conversion_cannot_create_zero_complement(tmp_path):
    s=spec(tmp_path,'id,y,p\n1,0,0.9999999999999999999999\n2,0,1.0000000000000000000001\n3,0,0.9999999999999999\n',probabilities=ProbabilitySpec('p'))
    r=core(s)
    assert r.data['runs'][0]['facts']['invalid_probabilities']==2
    m=measurement(r,'log_loss')
    assert m['denominator']==1 and m['value_state']=='finite' and m['value']>30


def test_native_parquet_and_exact_large_keys(tmp_path):
    import pyarrow as pa
    import pyarrow.parquet as pq
    p=tmp_path/'native.parquet'
    pq.write_table(pa.table({'id':pa.array([9007199254740992,9007199254740993],type=pa.int64()),'y':['0','1'],'p':['0','1']}),p)
    s=spec(tmp_path,'id,y,p\n1,0,0\n',prediction='p')
    s=replace(s,sources=(SourceSpec('data',str(p),'parquet'),))
    r=core(s);assert measurement(r,'accuracy')['denominator']==2
    assert not r.data['runs'][0]['facts']['duplicate_keys']


def test_cohort_limits_and_joint_comparison_disclosure(tmp_path):
    s=paired(tmp_path,'id,y,p,g\n'+''.join(f'{i},{i%2},{1-i%2 if i==0 else i%2},A\n' for i in range(30)),'id,y,p,g\n'+''.join(f'{i},{i%2},{i%2},A\n' for i in range(30)))
    r=core(s);shared=r.to_dict()
    assert not any(m['metric'] in {'accuracy','accuracy_right_minus_left'} for m in shared['measurements'])
    cohort=replace(s,cohorts=(CohortSpec('g','g',categories=('A',)),))
    with pytest.raises(EvaluationError):core(cohort,EvaluationConfig(max_groups=2))
    assert core(cohort,EvaluationConfig(max_groups=5)).data['measurements']


def test_job_idempotency_busy_stale_and_cancellation(tmp_path):
    s=spec(tmp_path,'id,y,p\n1,0,0\n2,1,1\n',prediction='p')
    app=create_app(tmp_path/'app',data_roots=(tmp_path,));client=app.test_client()
    try:
        token=client.get(BASE+'/session').json['data']['csrf_token'];headers={'X-CSRF-Token':token}
        source=client.post(BASE+'/sources',json={'root_id':'root_0','relative_path':'input.csv'},headers=headers).json['data']
        value=s.to_dict();value['sources']=[{'id':'data','handle':source['handle']}]
        draft=client.post(BASE+'/evaluations',json={'spec':value},headers=headers).json['data']
        payload={'kind':'inspect','client_request_id':'same','evaluation_id':draft['id'],'revision':1}
        lock=app.extensions['datatrust_worker_lock'];lock.acquire()
        assert client.post(BASE+'/jobs',json=payload,headers=headers).status_code==409
        lock.release()
        first=client.post(BASE+'/jobs',json=payload,headers=headers).json['data']
        assert client.post(BASE+'/jobs',json=payload,headers=headers).json['data']['id']==first['id']
        cancelled=client.post(BASE+'/jobs/'+first['id']+'/cancel',headers=headers).json['data']
        end=terminal(client,cancelled);assert end['state'] in {'cancelled','succeeded'}
        changed=client.put(BASE+'/evaluations/'+draft['id'],json={'spec':value,'expected_revision':1},headers=headers)
        assert changed.status_code==200
        assert client.post(BASE+'/jobs',json={**payload,'client_request_id':'new'},headers=headers).status_code==409
        forged={'schema_version':'confidenceguard.evaluation_result/1.0','methodology_id':'prediction_evaluation_v1','analysis_id':'../../escape','audience':'shareable'};forged['projection_digest']=digest(forged)
        assert client.post(BASE+'/results/import',data={'result':(io.BytesIO(json.dumps(forged).encode()),'r.json')},headers=headers).status_code==422
    finally:app.extensions['confidenceguard_store'].cleanup()
