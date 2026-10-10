import hashlib
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from datatrust import (AnalysisConfig, AnalysisError, CsvParseOptions, DataTrust, DatasetSpec,
                      RegressionOptions, RegressionRelationLimits, TargetExpectations, TaskSpec)
from datatrust.renderer import render_analysis_result
from datatrust.regression import consolidate_relationships


def analyze(tmp_path, values, features=None, options=None, config=None):
    frame=pd.DataFrame(features or {'input':np.arange(len(values))**2})
    frame['outcome']=values
    source=tmp_path/'source.csv';frame.to_csv(source,index=False)
    config=config or AnalysisConfig(regression=options)
    return DataTrust.from_spec(DatasetSpec(source),TaskSpec('regression','outcome'),config).analyze_result()


@pytest.fixture
def frozen_string_storage():
    # Preserve the original storage environment; analytical fixtures remain untouched.
    with pd.option_context('mode.string_storage', 'python'):
        yield

def codes(r):return {f['code'] for f in r.findings}


@pytest.mark.usefixtures('frozen_string_storage')
def test_frozen_unlabeled_evidence_and_report(tmp_path):
    baseline=json.loads(Path('tests/fixtures/m1_unlabeled_baseline.json').read_text())
    for case in baseline.values():
        source=tmp_path/'source.csv';source.write_text(case['raw'])
        r=DataTrust.from_spec(DatasetSpec(source,dataset_name='M1 parity'),TaskSpec('dataset_profile')).analyze_result()
        r.generated_at='2026-10-09T00:00:00+00:00'
        r.execution['elapsed_seconds']=0
        value=r.to_dict()
        assert {k:value[k] for k in case['result']}==case['result']
        assert hashlib.sha256(render_analysis_result(r).encode()).hexdigest()==case['html_sha256']


@pytest.mark.parametrize('raw,message', [('x,outcome\n1,oops\n2,3\n','must be numeric'),('x,outcome\n1,True\n2,False\n','not boolean'),('x,outcome\n1,inf\n2,-inf\n','no finite'),('x,outcome\n1,\n2,\n','no finite')])
def test_rejected_targets(tmp_path,raw,message):
    p=tmp_path/'data.csv';p.write_text(raw)
    with pytest.raises(AnalysisError,match=message):DataTrust(p,'outcome',task='regression').analyze_result()


def test_numeric_override_explicit_and_missing_target(tmp_path):
    p=tmp_path/'data.csv';p.write_text('x,outcome\n1,1\n2,2\n')
    config=AnalysisConfig(parsing=CsvParseOptions(column_types={'outcome':'string'}))
    with pytest.raises(AnalysisError,match='numeric parsing override'):DataTrust.from_spec(DatasetSpec(p),TaskSpec('regression','outcome'),config).analyze_result()
    config=AnalysisConfig(parsing=CsvParseOptions(column_types={'outcome':'numeric'}))
    assert DataTrust.from_spec(DatasetSpec(p),TaskSpec('regression','outcome'),config).analyze_result().profile['regression']['target_statistics']['finite_count']==2
    with pytest.raises(AnalysisError,match='not found'):DataTrust(p,'missing',task='regression').analyze_result()
    with pytest.raises(ValueError,match='requires an explicit'):TaskSpec('regression')


@pytest.mark.parametrize('value',[{'kind':'category'},{'minimum':float('inf')},{'minimum':True},{'minimum':2,'maximum':1},{'kind':'count','nonnegative':False},{'kind':'count','integer_required':False},{'nonnegative':True,'maximum':-1},{'integer_required':True,'minimum':.1,'maximum':.9},{'units':'a'*81},{'nonnegative':1}])
def test_invalid_expectations(value):
    with pytest.raises(ValueError):TargetExpectations(**value)


def test_config_contracts_and_declaration_references(tmp_path):
    config=AnalysisConfig.from_dict({'regression':{'expectations':{'kind':'count'},'relation_limits':{'max_pair_features':2}}})
    assert config.regression.expectations.nonnegative and config.regression.expectations.integer_required
    for cfg in [{'regression':{'unknown':1}},{'regression':{'expectations':{'foo':1}}},{'regression':{'relation_limits':{'max_screen_rows':0}}},{'regression':{'feature_availability':{'x':[]}}}]:
        with pytest.raises(ValueError):AnalysisConfig.from_dict(cfg)
    for name in ['outcome','absent']:
        with pytest.raises(AnalysisError,match='feature columns'):analyze(tmp_path,[1,2],options=RegressionOptions(feature_availability={name:'unknown'}))
    p=tmp_path/'source.csv'
    for task in [TaskSpec('classification','outcome'),TaskSpec('dataset_profile')]:
        with pytest.raises(ValueError,match='Regression options require'):DataTrust.from_spec(DatasetSpec(p),task,config).analyze_result()


def test_quantitative_population_distribution_and_constraints(tmp_path):
    r=analyze(tmp_path,[-1,0,1,2,3,4,100,np.inf,-np.inf,np.nan],options=RegressionOptions(TargetExpectations('count',maximum=4)))
    t=r.profile['regression']['target_statistics'];c=r.profile['regression']['constraints']
    assert (t['finite_count'],t['missing_count'],t['non_missing_count'],t['positive_infinity_count'],t['negative_infinity_count'])==(7,1,9,1,1)
    assert (t['negative_count'],t['zero_count'],t['integer_count'])==(1,1,7)
    assert t['mean']==pytest.approx(109/7)
    assert t['sample_std']==pytest.approx(math.sqrt(sum((v-109/7)**2 for v in [-1,0,1,2,3,4,100])/6))
    assert t['quantiles']['q1']==pytest.approx(.5) and t['quantiles']['q3']==pytest.approx(3.5)
    assert t['bowley_skewness']==pytest.approx(0)
    assert (t['extremes']['lower_count'],t['extremes']['upper_count'])==(0,1)
    assert c['violation_union_count']==2 and c['compliant_finite_count']==5
    assert sum(b['count'] for b in t['histogram']['bins'])==7
    assert r.scoring['values'] is None and r.schema_version=='1.1'
    assert r.methodology_id=='tabular_regression_v1'


def test_constraint_union_inclusive_boundaries_and_fractional(tmp_path):
    r=analyze(tmp_path,[-1,-.5,0,1,1.5,2,3],options=RegressionOptions(TargetExpectations('count',minimum=0,maximum=2)))
    c=r.profile['regression']['constraints']
    assert c['violation_union_count']==4
    assert sum(v['count'] for v in c['rules'])>4
    assert r.profile['regression']['target_statistics']['finite_count']==7


@pytest.mark.parametrize('values,expected', [([5],'regression_constant_target'),([1,2,3],'regression_limited_observations'),([1]*19+[2],'regression_target_concentration')])
def test_small_constant_and_concentrated_targets(tmp_path,values,expected):
    r=analyze(tmp_path,values)
    assert expected in codes(r) and r.execution['status']=='completed'
    if len(values)<4 or values.count(1)>18:assert r.profile['regression']['target_statistics']['extremes'] is None


def test_target_only_and_numeric_precision(tmp_path):
    p=tmp_path/'only.csv';p.write_text('outcome\n1\n2\n3\n4\n')
    r=DataTrust(p,'outcome',task='regression').analyze_result()
    assert r.profile['feature_count']==0 and 'regression_no_features' in codes(r)
    assert r.profile['regression']['repeated_inputs'] is None
    r=analyze(tmp_path,[2**53+1,2**53+2,2**53+3])
    t=r.profile['regression']['target_statistics']
    assert t['distinct_count']==3 and t['min']==2**53+1 and t['quantiles'] is None
    r=analyze(tmp_path,[i*1e-12 for i in range(40)])
    assert r.profile['regression']['target_statistics']['quantiles']['median']==pytest.approx(19.5e-12,abs=1e-25)


@pytest.mark.parametrize('n,coverage,action',[(2,1,False),(29,1,False),(30,1,True),(30,.79,False),(32,.8,True)])
def test_copy_support_gate(tmp_path,n,coverage,action):
    total=round(n/coverage)
    y=np.arange(total,dtype=float);x=y.copy();x[n:]=np.nan
    r=analyze(tmp_path,y,{'input':x})
    copies=[v for v in r.profile['regression']['relationships'] if v['method']=='exact_copy']
    assert copies and copies[0]['action_eligible']==action
    assert ('regression_relationships_unknown' in codes(r))==action
    if not action:assert copies[0]['non_escalation_reasons']
    assert len(r.profile['regression']['relationship_groups'])==1


def test_affine_sum_dedup_and_distinct_relationships(tmp_path):
    y=np.arange(40,dtype=float)
    features={'copy':y,'scaled':y*2+7,'component':y**.5,'remainder':y-y**.5,'zero':np.zeros(40)}
    r=analyze(tmp_path,y,features)
    reg=r.profile['regression']
    assert {'exact_copy','affine_identity','pair_sum'}<={v['method'] for v in reg['relationships']}
    group=next(g for g in reg['relationship_groups'] if g['columns']==['copy'])
    assert len(group['relationship_ids'])==2 # copy + copy/zero sum, one underlying mapping
    assert any(g['columns']==['component','remainder'] for g in reg['relationship_groups'])
    assert len([f for f in r.findings if f['code']=='regression_relationships_unknown'])==1
    assert any(v['reason_category']=='redundant_check' for v in reg['search']['candidates'])


def test_available_and_weak_unavailable_relationships(tmp_path):
    r=analyze(tmp_path,np.arange(40),{'input':np.arange(40)},RegressionOptions(feature_availability={'input':'available_at_prediction'}))
    assert not any(c.startswith('regression_relationships_') for c in codes(r))
    r=analyze(tmp_path,[1,2],{'input':[1,2]},RegressionOptions(feature_availability={'input':'unavailable_at_prediction'}))
    assert 'regression_declared_availability' in codes(r)
    assert 'regression_relationships_unavailable_at_prediction' not in codes(r)


def test_screening_false_match_and_large_offset_nonidentity(tmp_path):
    n=100;y=np.arange(n,dtype=float);a=y**2;b=y-a;b[55]+=.1
    options=RegressionOptions(relation_limits=RegressionRelationLimits(max_screen_rows=4))
    r=analyze(tmp_path,y,{'a':a,'b':b},options)
    assert not any(v['method']=='pair_sum' for v in r.profile['regression']['relationships'])
    r=analyze(tmp_path,1e12+np.arange(100),{'input':1e12+np.arange(100)+np.sin(np.arange(100))})
    assert not r.profile['regression']['relationships']


def test_bounded_search_and_unexpected_failure(tmp_path,monkeypatch):
    r=analyze(tmp_path,np.arange(40),{'x':np.arange(40),'z':np.arange(40)**2},RegressionOptions(relation_limits=RegressionRelationLimits(1,1,1,1)))
    assert r.execution['status']=='completed' and r.coverage['relationship_search']['status']=='bounded'
    assert r.coverage['relationship_search']['pool_exclusions'] and r.coverage['relationship_search']['skipped_count']
    def fail(*args):raise RuntimeError('test failure')
    monkeypatch.setattr('datatrust.core.relationship_evidence',fail)
    r=analyze(tmp_path,np.arange(40))
    assert r.execution['status']=='partial' and r.coverage['relationship_search']['status']=='unavailable'
    assert not r.profile['regression']['relationships']


def test_repeated_inputs_are_context_not_contradictions(tmp_path):
    r=analyze(tmp_path,[1,2,2,3],{'input':[0,0,0,1]})
    e=r.profile['regression']['repeated_inputs']
    assert (e['repeated_group_count'],e['varying_group_count'],e['varying_rows'])==(1,1,3)
    assert 'regression_repeated_input_variation' in codes(r)
    assert not any('conflict' in c for c in codes(r))


@pytest.mark.parametrize('kind',['negative','heavy_tail','skew','mixture','zero_count','bounded','fixed_decimal','integers','repeated_noise'])
def test_legitimate_distributions_no_false_factual_findings(tmp_path,kind):
    rng=np.random.default_rng(20261009)
    values={'negative':rng.normal(-10,2,100),'heavy_tail':rng.standard_t(2,100),'skew':rng.lognormal(0,2,100),
        'mixture':np.r_[rng.normal(-4,1,50),rng.normal(4,1,50)],'zero_count':np.r_[np.zeros(80),np.arange(20)],
        'bounded':np.clip(rng.normal(.5,.3,100),0,1),'fixed_decimal':np.round(rng.normal(0,5,100),2),
        'integers':np.arange(100),'repeated_noise':rng.normal(0,1,100)}[kind]
    r=analyze(tmp_path,values,{'input':rng.normal(0,1,100)})
    assert 'regression_declared_constraints' not in codes(r)
    assert not any('rounding' in c or 'leakage' in c or 'conflict' in c for c in codes(r))
    assert not r.profile['regression']['relationships']


def test_strict_json_reference_resolution(tmp_path):
    r=analyze(tmp_path,np.arange(40),{'input':np.arange(40)},RegressionOptions(TargetExpectations('count',maximum=20)))
    data=json.loads(r.json_text(),parse_constant=lambda s:pytest.fail(s))
    evidence={e['id'] for e in data['evidence']}
    for e in data['evidence']:
        for pointer in e['measurement_refs']:
            node=data
            for key in pointer.split('/')[1:]:node=node[int(key)] if isinstance(node,list) else node[key]
        for ref in e['row_refs']:assert ref['source_sha256']==data['parsing']['source_sha256']
    for f in data['findings']:assert f['evidence_refs'] and set(f['evidence_refs'])<=evidence


def test_translation_constant_sum_consolidation_with_sparse_support(tmp_path):
    y=np.arange(60,dtype=float)+7
    constant=np.full(60,7.);constant[50:]=np.nan
    r=analyze(tmp_path,y,{'input':y-7,'constant':constant})
    reg=r.profile['regression'];group=next(g for g in reg['relationship_groups'] if g['columns']==['input'])
    assert len(group['relationship_ids'])==2
    assert {s['overlap_count'] for s in group['support_scopes']}=={50,60}
    assert len({s['support_sha256'] for s in group['support_scopes']})==2


def test_repeated_null_inputs_keep_row_references_and_large_integer_span(tmp_path):
    r=analyze(tmp_path,[2**53+1,2**53+2,2**53+3],{'a':[np.nan]*3,'b':['same']*3})
    example=r.profile['regression']['repeated_inputs']['examples'][0]
    assert example['span']==2 and example['distinct_count']==3
    assert [ref['parsed_row'] for ref in example['row_refs']]==[1,2,3]


def test_overflow_is_unavailable_not_zero_variation(tmp_path):
    r=analyze(tmp_path,[-1.7e308,1.7e308],{'input':[1,2]})
    t=r.profile['regression']['target_statistics']
    assert t['distinct_count']==2 and t['sample_std'] is None
    assert t['unavailable_statistics']['sample_std']=='statistic_overflow'
    assert 'regression_constant_target' not in codes(r)
    assert sum(b['count'] for b in t['histogram']['bins'])==2


def test_few_distinct_copy_never_becomes_relationship_action(tmp_path):
    y=np.tile([1,2,3,4],10)
    r=analyze(tmp_path,y,{'input':y})
    assert r.profile['regression']['relationships'][0]['non_escalation_reasons']==['few_distinct_targets']
    assert not any(c.startswith('regression_relationships_') for c in codes(r))


def test_interrupted_relationship_search_retains_verified_evidence(tmp_path):
    from datatrust.regression import relationship_evidence
    frame=pd.DataFrame({'first':np.arange(40),'second':np.arange(40)**2,'outcome':np.arange(40)})
    calls=0
    def checkpoint(stage):
        nonlocal calls
        calls+=1
        if calls==2:raise AnalysisError('Deadline reached',code='resource_limit',stage=stage)
    value=relationship_evidence(frame,'outcome',RegressionOptions(),checkpoint)
    assert value['search']['status']=='partial'
    assert len(value['relationships'])==1 and value['relationships'][0]['fully_verified']
    assert value['search']['interrupted_candidate_count']==4
    assert value['search']['skipped_count']==0
    assert value['search']['failure']['reason_category']=='execution_interruption'
