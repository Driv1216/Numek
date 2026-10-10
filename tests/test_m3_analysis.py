"""Independent counts/formulas and compatibility tests for M3 semantics."""
import hashlib
import json
import math
import statistics
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from datatrust import *
from datatrust.annotations import normalize_target, effective_policy
from datatrust.multilabel import multilabel_evidence
from datatrust.presentation import report_view
from datatrust.renderer import render_analysis_result


def analyze(tmp_path,text,task,config=None):
    path=tmp_path/'data.csv';path.write_text(text)
    return DataTrust.from_spec(DatasetSpec(path),task,config).analyze_result()


def annotation_config(expectation='unknown',status_column=None,status_values=None):
    return AnalysisConfig(annotations=AnnotationOptions(AnnotationSpec(expectation,status_column,status_values)))


@pytest.mark.parametrize('expectation,value,status,expected',[
 ('expected','a',None,{'observed':1,'supplied_expected':1}),('optional','a',None,{'observed':1,'expected':0}),
 ('unknown','a','unknown',{'observed':1,'unknown':1}),('expected',None,None,{'unavailable_expected':1}),
 ('optional',None,None,{'unavailable_expected':0,'intentional_absence':0}),('unknown',None,'unknown',{'unavailable_expected':0,'unknown':1}),
 ('optional',None,'intentionally_unlabeled',{'intentional_absence':1,'unavailable_expected':0}),
 ('unknown','a','intentionally_unlabeled',{'observed':1,'declaration_inconsistencies':1}),
 ('unknown',None,'observed',{'observed':0,'declaration_inconsistencies':1}),
 ('unknown','a','uncertain',{'observed':1,'uncertain_observed':1}),('unknown',None,'uncertain',{'uncertain_absent':1,'observed':0}),
 ('unknown','a','oops',{'observed':1,'unresolved_metadata':1,'unknown_expectation_population':1}),
 ('expected',None,'oops',{'expected':1,'unavailable_expected':1,'unresolved_metadata':1}),
 ('optional','a',None,{'observed':1,'unresolved_metadata':1}),
])
def test_annotation_truth_table(expectation,value,status,expected):
    data=pd.DataFrame({'y':[value],'state':[status]})
    c=normalize_target(data,'y','classification',AnnotationSpec(expectation,'state' if status is not None or expectation=='optional' and value=='a' else None))['coverage']
    for key,value in expected.items():assert c[key]==value,(key,c)


@pytest.mark.parametrize('expectation',['expected','optional','unknown'])
@pytest.mark.parametrize('status',['observed','uncertain','unknown','intentionally_unlabeled',None,'unmapped'])
def test_invalid_never_becomes_observed(expectation,status):
    state=normalize_target(pd.DataFrame({'y':[2],'s':[status]}),'y','multilabel_classification',AnnotationSpec(expectation,'s'))
    assert state['coverage']['invalid']==1 and state['coverage']['observed']==0
    assert not state['valid'][0]


def test_unknown_and_uncertain_retain_values_and_distinct_missing_reasons(tmp_path):
    text='x,y,s\n1,a,unknown\n2,b,uncertain\n3,,unknown\n4,,oops\n5,,observed\n6,a,intentionally_unlabeled\n'
    r=analyze(tmp_path,text,TaskSpec('classification','y'),annotation_config('expected','s'))
    c=r.profile['annotations']['targets'][0]
    assert c['observed']==3 and c['uncertain_observed']==1 and c['declaration_inconsistencies']==2
    assert c['expected']==3 and c['supplied_expected']==1 and c['unavailable_expected_by_reason']=={'invalid':0,'unresolved_status':1,'missing':1}
    assert r.profile['classification']['observed_count']==3
    assert r.schema_version=='1.2' and r.scoring['values'] is None
    assert r.profile['roles']['features']==['x'] and r.profile['roles']['metadata']==['s']


def test_six_row_multilabel_independent_reference(tmp_path):
    r=analyze(tmp_path,'x,a,b,c\n1,1,0,1\n2,0,0,0\n3,1,,0\n4,,,\n5,0,1,0\n6,1,1,\n',TaskSpec('multilabel_classification',targets=('a','b','c')))
    m=r.profile['multilabel'];assert r.execution['status']=='completed'
    assert (m['complete_vector_count'],m['partial_vector_count'],m['empty_vector_count'])==(3,2,1)
    assert m['cardinality']==1 and m['density']==1/3 and m['observed_cells']==13 and m['observed_positives']==6
    pair=next(p for p in m['pairs'] if p['targets']==['a','b'])
    assert [pair[k] for k in ('n00','n01','n10','n11')]==[1,1,1,1]
    assert pair['jaccard']==1/3 and pair['jointly_observed']==4 and pair['b_positive_given_a_positive']==.5
    assert m['cardinality_distribution']=={'0':1,'1':1,'2':1}
    assert sum(p['count'] for p in m['combinations']['records'])==3
    assert not any('gaps' in f['code'] for f in r.findings)


def test_indicator_exact_encodings_and_partial_constraints(tmp_path):
    config=AnalysisConfig(parsing=CsvParseOptions(column_types={'a':'string','b':'string'}),multilabel=MultilabelOptions(minimum_positive=1,maximum_positive=1,mutually_exclusive=(('a','b'),),requires=(('a','b'),)))
    r=analyze(tmp_path,'x,a,b\n1,1,0\n2,1,\n3,0,0\n4,1,1\n5,2,1\n6,True,0\n7, 1,0\n',TaskSpec('multilabel_classification',targets=('a','b')),config)
    m=r.profile['multilabel'];assert m['labels'][0]['invalid']==3
    rules={c['rule']:c for c in m['constraints']}
    assert rules['requires']['violated']==1 and rules['requires']['inconclusive']==3
    assert rules['minimum_positive']['violated']==1 and rules['maximum_positive']['violated']==1
    assert rules['mutually_exclusive']['violated']==1
    assert m['constraint_violation_row_union']==3


def test_complementary_partial_repeated_inputs_are_compatible(tmp_path):
    r=analyze(tmp_path,'x,a,b,state\nsame,1,,unknown\nsame,,0,observed\nsame,1,0,uncertain\nother,0,0,unknown\nother,1,0,unknown\n',TaskSpec('multilabel_classification',targets=('a','b')),annotation_config('unknown','state'))
    rep=r.profile['repeated_inputs']
    assert rep['varying_row_union']==2
    assert rep['targets'][0]['varying_group_count']==1 and rep['targets'][1]['varying_group_count']==0
    assert r.profile['roles']['features']==['x']


def test_group_coverage_distinguishes_vectors_spread_over_rows(tmp_path):
    r=analyze(tmp_path,'g,x,a,b\none,1,1,\none,2,,1\ntwo,3,1,1\n,4,1,1\n',TaskSpec('multilabel_classification',targets=('a','b'),group_columns=('g',)),annotation_config('expected'))
    g=r.profile['annotations']['groups']
    assert g['excluded_incomplete_key_rows']==1 and g['group_count']==2
    assert g['complete_vector_on_one_row_groups']==1 and g['all_targets_somewhere_groups']==2
    assert g['pooled_expected_cell_coverage']==4/6 and g['equally_weighted_expected_group_coverage']==.75
    assert r.profile['annotations']['rows']['complete_observed_vector']==2


def test_empty_supervision_and_feature_free_inputs(tmp_path):
    for task in (TaskSpec('classification','y'),TaskSpec('regression','y'),TaskSpec('multilabel_classification','y')):
        r=analyze(tmp_path,'y\n""\n""\n',replace(task,feature_columns=()),annotation_config())
        assert r.profile['annotations']['rows']['no_observed']==2 and r.execution['status']=='completed'
        assert r.profile['annotations']['targets'][0]['expected_coverage'] is None
        assert r.scoring['values'] is None and r.profile['feature_count']==0
        assert 'Unavailable' in render_analysis_result(r) or 'No observed' in render_analysis_result(r)
    with pytest.raises(ValueError,match='no usable labels'):analyze(tmp_path,'x,y\n1,\n2,\n',TaskSpec('classification','y'))
    with pytest.raises(AnalysisError,match='no finite'):analyze(tmp_path,'x,y\n1,\n2,\n',TaskSpec('regression','y'))


@pytest.mark.parametrize('kind',['classification','regression'])
def test_semantic_compatibility_matrix_full_payload_and_html(tmp_path,kind):
    text='x,z,y\n'+''.join(f'{i},{i%3},{i%2 if kind=="classification" else i*2+1}\n' for i in range(40))
    base=analyze(tmp_path,text,TaskSpec(kind,'y'))
    base.generated_at='2026-10-09T00:00:00+00:00';base.execution['elapsed_seconds']=0
    variants=[(TaskSpec(kind,targets=('y',)),AnalysisConfig()),(TaskSpec(kind,'y',feature_columns=('z','x')),AnalysisConfig()),
              (TaskSpec(kind,'y'),annotation_config('expected'))]
    if kind=='regression':variants.append((TaskSpec(kind,targets=('y',)),AnalysisConfig(regression=RegressionOptions(expectations_by_target={'y':TargetExpectations()}))))
    for task,config in variants:
        r=analyze(tmp_path,text,task,config);r.generated_at=base.generated_at;r.execution['elapsed_seconds']=0
        assert r.to_dict()==base.to_dict()
        assert render_analysis_result(r)==render_analysis_result(base)
    unknown=analyze(tmp_path,text,TaskSpec(kind,'y'),annotation_config())
    assert unknown.schema_version=='1.2' and unknown.scoring['values'] is None
    assert unknown.methodology_id!=base.methodology_id


def test_multioutput_no_target_contamination_and_independent_pearson(tmp_path):
    text='x,code,y,z,empty\n'+''.join(f'{i},{i%4},{3*i+2},{7*i-3},\n' for i in range(40))
    config=AnalysisConfig(features=FeatureOptions({'x':'quantitative','code':'categorical'}),regression=RegressionOptions(expectations_by_target={'y':TargetExpectations(minimum=5)}))
    r=analyze(tmp_path,text,TaskSpec('regression',targets=('y','z','empty')),config)
    m=r.profile['multioutput_regression']
    assert r.profile['roles']['features']==['x','code']
    assert (m['complete_vector_count'],m['partial_vector_count'],m['empty_vector_count'])==(0,40,0)
    assert m['outputs'][2]['blocked_reason']=='no_finite_observed_targets'
    assert m['constraint_violation_row_union']==1
    assert all(set(candidate['columns'])<=set(['x','code']) for o in m['outputs'] if o['search'] for candidate in o['search']['candidates'])
    pair=m['output_dependencies'][0]
    x=list(range(2,120,3));y=list(range(-3,271,7));xm=statistics.mean(x);ym=statistics.mean(y)
    expected=sum((a-xm)*(b-ym) for a,b in zip(x,y))/math.sqrt(sum((a-xm)**2 for a in x)*sum((b-ym)**2 for b in y))
    assert math.isclose(pair['pearson'],expected,abs_tol=1e-14)
    assert pair['scope']=='output_dependencies' and pair['identities']


def test_shared_relationship_budget_and_round_robin(tmp_path):
    config=AnalysisConfig(regression=RegressionOptions(relation_limits=RegressionRelationLimits(max_single_comparisons=60,max_pair_comparisons=10)))
    r=analyze(tmp_path,'x,y,z\n'+''.join(f'{i},{i},{i}\n' for i in range(30)),TaskSpec('regression',targets=('y','z')),config)
    m=r.profile['multioutput_regression'];assert m['relationship_work']['single']==60
    assert all(o['relationships'] and o['relationships'][0]['method']=='exact_copy' for o in m['outputs'])
    assert all(o['search']['comparisons']['single']<=60 for o in m['outputs'])


def test_unsupervised_semantic_recoding_and_legitimate_extremes(tmp_path):
    text='q,scale,code,id,flag\n'+''.join(f'{i if i<39 else 1000},{i*1000},{i%3},{100000+i},{i%2}\n' for i in range(40))
    config=AnalysisConfig(features=FeatureOptions({'q':'quantitative','scale':'quantitative','code':'categorical','id':'identifier'}))
    r=analyze(tmp_path,text,TaskSpec('anomaly_detection'),config);e=r.profile['readiness']
    assert [s['feature'] for s in e['quantitative_features']]==['q','scale']
    assert e['marginal_extreme_candidate_rows']==1 and e['scale_ratios'][0]['conditional_review']
    assert all('anomal' not in f['code'] for f in r.findings)
    config=replace(config,features=replace(config.features,scale_sensitive=False))
    r2=analyze(tmp_path,text,TaskSpec('clustering'),config)
    assert not r2.profile['readiness']['scale_ratios'][0]['conditional_review']
    assert r2.profile['readiness']['scale_ratios'][0]['ratio']==e['scale_ratios'][0]['ratio']
    recoded=text.replace(',0,100',',900,100').replace(',1,100',',1000,100').replace(',2,100',',7000,100')
    r3=analyze(tmp_path,recoded,TaskSpec('clustering'),config)
    assert r3.profile['readiness']['scale_ratios']==r2.profile['readiness']['scale_ratios']


def test_categorical_only_readiness_and_no_fake_geometry(tmp_path):
    r=analyze(tmp_path,'kind,id\na,1\nb,2\na,3\n',TaskSpec('clustering'),AnalysisConfig(features=FeatureOptions({'id':'identifier'})))
    e=r.profile['readiness'];assert e['complete_finite_quantitative_rows'] is None
    assert e['distinct_feature_vectors']==3 and e['categorical_frequency']
    assert all(v['ratio'] is None for v in e['scale_ratios'])


def test_pattern_and_pair_limits_are_complete_bounded_not_partial(tmp_path):
    config=AnalysisConfig(diagnostics=DiagnosticLimits(max_patterns=1,max_multilabel_pair_targets=2,max_multilabel_comparisons=1,max_cohort_comparisons=1))
    r=analyze(tmp_path,'x,a,b,c\n1,0,0,0\n2,1,1,1\n3,0,0,0\n',TaskSpec('multilabel_classification',targets=('a','b','c')),config)
    m=r.profile['multilabel'];assert m['combinations']['processed_complete_vectors']==1 and m['combinations']['status']=='bounded'
    assert m['pair_search']['status']=='bounded' and not m['pairs']
    assert r.profile['annotation_cohorts']['status']=='bounded' and r.execution['status']=='completed'
    assert 'source prefix' in render_analysis_result(r)


def test_strict_json_references_and_presentation_does_not_mutate(tmp_path):
    r=analyze(tmp_path,'x,a,b\n1,1,0\n2,0,1\n3,,\n',TaskSpec('multilabel_classification',targets=('a','b')))
    before=r.json_text();view=report_view(r);html=render_analysis_result(r)
    assert r.json_text()==before and 'Composite scoring: not defined' in html
    data=json.loads(before,parse_constant=lambda v:pytest.fail(v));ids={e['id'] for e in data['evidence']}
    for e in data['evidence']:
        for pointer in e['measurement_refs']:
            node=data
            for key in pointer.split('/')[1:]:node=node[int(key)] if isinstance(node,list) else node[key]
    for f in data['findings']:assert f['evidence_refs'] and set(f['evidence_refs'])<=ids
    assert view['qa']['appendix_detail_rows']<=100


@pytest.mark.parametrize('spec',[{'kind':'classification','targets':['a','b']},{'kind':'regression','target':'a','targets':['b']},{'kind':'clustering','target':'a'},
                                   {'kind':'regression','targets':['a','a']},{'kind':'dataset_profile','backend':'x'},{'kind':'classification','target':'a','feature_columns':['a']}])
def test_strict_invalid_tasks(spec):
    with pytest.raises(ValueError):TaskSpec.from_dict(spec)


def test_status_mapping_contradictions_and_feature_references(tmp_path):
    with pytest.raises(ValueError):AnnotationState('expected','intentionally_unlabeled')
    with pytest.raises(ValueError):AnnotationSpec('expected','s',{'absent':AnnotationState(annotation_status='intentionally_unlabeled')})
    for task,config in [(TaskSpec('multilabel_classification',targets=('a','b'),feature_columns=('s',)),annotation_config('unknown','s')),
                         (TaskSpec('regression',targets=('a','b')),AnalysisConfig(regression=RegressionOptions(feature_availability={'b':'unknown'}))),
                         (TaskSpec('clustering',metadata_columns=('s',)),AnalysisConfig(features=FeatureOptions({'s':'quantitative'}))),
                         (TaskSpec('clustering'),annotation_config('unknown','s'))]:
        with pytest.raises(ValueError):analyze(tmp_path,'s,a,b\nx,1,0\ny,0,1\n',task,config)


def test_tv_distance_and_shape_gates_independent(tmp_path):
    text='code,value,label\n'+''.join(f'{"a" if i<30 else "b"},{i},{"yes" if i<40 else ""}\n' for i in range(80))
    r=analyze(tmp_path,text,TaskSpec('classification','label'),AnalysisConfig(annotations=AnnotationOptions(),features=FeatureOptions({'value':'quantitative','code':'categorical'})))
    records=r.profile['annotation_cohorts']['records']
    code=next(c for c in records if c['cohort']=='any_observed_vs_none' and c['feature']=='code')
    assert code['categorical']['total_variation_distance']==.5*(abs(30/40-0)+abs(10/40-40/40))
    value=next(c for c in records if c['cohort']=='any_observed_vs_none' and c['feature']=='value')
    assert [c['median'] for c in value['numerical']]==[19.5,59.5]
    assert [c['iqr'] for c in value['numerical']]==[19.5,19.5]
    assert not any('cohort' in f['code'] for f in r.findings)


def test_definite_constraint_violation_survives_unrelated_invalid_assignment(tmp_path):
    r=analyze(tmp_path,'x,a,b,c\n1,1,1,2\n2,0,,0\n',TaskSpec('multilabel_classification',targets=('a','b','c')),AnalysisConfig(multilabel=MultilabelOptions(mutually_exclusive=(('a','b'),))))
    assert r.profile['multilabel']['constraints'][0]['violated']==1
    assert r.profile['multilabel']['labels'][2]['invalid']==1


def test_contradictory_overlapping_constraint_groups_rejected(tmp_path):
    config=AnalysisConfig(multilabel=MultilabelOptions(minimum_positive=2,mutually_exclusive=(('a','b'),('b','c'),('a','c'))))
    with pytest.raises(ValueError,match='Contradictory'):
        analyze(tmp_path,'x,a,b,c\n1,0,0,0\n',TaskSpec('multilabel_classification',targets=('a','b','c')),config)


def test_identifier_cue_is_conditional_and_declaration_can_resolve_it(tmp_path):
    text='observation_id,value\n'+''.join(f'{i},{i*.5}\n' for i in range(30))
    r=analyze(tmp_path,text,TaskSpec('clustering'))
    assert r.profile['feature_semantics'][0]['semantic_type']=='ambiguous_identifier'
    assert r.profile['roles']['features']==['observation_id','value']
    r=analyze(tmp_path,text,TaskSpec('clustering'),AnalysisConfig(features=FeatureOptions({'observation_id':'quantitative'})))
    assert r.profile['feature_semantics'][0]['quantitative_geometry']


def test_large_integer_tiny_spread_overflow_and_constant_outputs(tmp_path):
    text='x,large,tiny,overflow,constant\n'+''.join(f'{i},{2**60+i},{1e-20+i*1e-24},{1e308 if i%2 else -1e308},7\n' for i in range(40))
    r=analyze(tmp_path,text,TaskSpec('regression',targets=('large','tiny','overflow','constant')))
    outputs={o['target']:o for o in r.profile['multioutput_regression']['outputs']}
    assert outputs['large']['statistics']['precision_reason']=='integer_precision_beyond_float64'
    assert outputs['large']['statistics']['mean'] is None and outputs['large']['statistics']['histogram'] is None
    assert outputs['tiny']['statistics']['iqr']>0 and outputs['tiny']['statistics']['iqr']<1e-22
    assert outputs['overflow']['statistics']['iqr'] is None
    assert outputs['constant']['statistics']['mean']==7 and outputs['constant']['statistics']['extremes'] is None
    assert not any(p['pearson'] is not None and 'large' in p['targets'] for p in r.profile['multioutput_regression']['output_dependencies'])


def test_confirmation_fingerprint_compares_effective_semantics():
    from datatrust.annotations import specification_fingerprint
    columns=['a','b','y']
    old=TaskSpec('classification','y');default=AnalysisConfig()
    fp=specification_fingerprint(old,default,columns)
    for task,config in [(TaskSpec('classification',targets=('y',)),default),
                        (TaskSpec('classification','y',feature_columns=('b','a')),default),
                        (old,annotation_config('expected')),
                        (old,AnalysisConfig(annotations=AnnotationOptions(per_target={'y':AnnotationSpec('expected')})))]:
        assert specification_fingerprint(task,config,columns)==fp
    assert specification_fingerprint(old,annotation_config('unknown'),columns)!=fp
    assert specification_fingerprint(old,annotation_config('optional'),columns)!=fp


def test_unbounded_multilabel_and_joint_regression_permutation_invariance(tmp_path):
    import random
    rows=[f'{i},{i%2},{int(i%3==0)},{i*3+.25}' for i in range(45)]
    shuffled=rows.copy();random.Random(12).shuffle(shuffled)
    for task,config in [(TaskSpec('multilabel_classification',targets=('a','b')),AnalysisConfig()),
                        (TaskSpec('regression',targets=('a','y')),AnalysisConfig(features=FeatureOptions({'x':'quantitative'})))]:
        first=analyze(tmp_path,'x,a,b,y\n'+'\n'.join(rows)+'\n',task,config)
        second=analyze(tmp_path,'x,a,b,y\n'+'\n'.join(shuffled)+'\n',task,config)
        assert first.profile['annotations']['rows']==second.profile['annotations']['rows']
        if task.kind=='multilabel_classification':
            assert first.profile['multilabel']['pairs']==second.profile['multilabel']['pairs']
            assert first.profile['multilabel']['cardinality']==second.profile['multilabel']['cardinality']
            assert {tuple(c['vector']):c['count'] for c in first.profile['multilabel']['combinations']['records']}=={tuple(c['vector']):c['count'] for c in second.profile['multilabel']['combinations']['records']}
        else:
            for a,b in zip(first.profile['multioutput_regression']['output_dependencies'],second.profile['multioutput_regression']['output_dependencies']):
                assert math.isclose(a['pearson'],b['pearson'],abs_tol=1e-12) if a['pearson'] is not None else b['pearson'] is None


def test_unresolved_status_does_not_erase_known_expected_requirement(tmp_path):
    r=analyze(tmp_path,'x,y,state\n1,a,unmapped\n2,,unmapped\n3,,unmapped\n',TaskSpec('classification','y'),AnalysisConfig(annotations=AnnotationOptions(AnnotationSpec('expected','state')),diagnostics=DiagnosticLimits(max_examples=1)))
    c=r.profile['annotations']['targets'][0]
    assert c['expected']==3 and c['supplied_expected']==1 and c['expected_coverage']==1/3
    assert c['unresolved_metadata']==3 and c['unknown_expectation_population']==0
    assert c['unavailable_expected_by_reason']['unresolved_status']==2
    assert all(len(refs)<=1 for refs in c['row_refs_by_reason'].values())


def test_repeated_input_metadata_variation_is_separate_from_observed_disagreement(tmp_path):
    r=analyze(tmp_path,'x,y,state\nsame,a,observed\nsame,a,uncertain\nsame,,intentionally_unlabeled\nother,b,unknown\n',TaskSpec('classification','y'),annotation_config('unknown','state'))
    repeated=r.profile['repeated_inputs']
    assert repeated['varying_row_union']==0
    assert repeated['mixed_metadata_group_union']==1
    assert repeated['targets'][0]['mixed_expectation_group_count']==1
    assert repeated['targets'][0]['mixed_status_group_count']==1
    assert not any(f['code']=='observed_annotation_disagreement' for f in r.findings)
