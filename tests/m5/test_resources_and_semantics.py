from dataclasses import replace
import json
import threading
from pathlib import Path
import pytest
from datatrust import *
from datatrust.temporal import execute
from .test_temporal import family


def run(inputs,**kwargs):return execute(TemporalAuditSpec(tuple(inputs),**kwargs),TemporalAnalysisConfig(behavior=TemporalBehaviorSpec(enabled=False)))
def input_at(p,temporal,role='dataset',id='data',task=None):return TemporalInputSpec(id,TemporalSourceSpec(str(p),'parquet' if p.suffix=='.parquet' else 'csv'),temporal,role,task or TaskSpec('dataset_profile'))


def test_parquet_native_ns_typed_nulls(tmp_path):
    pa=pytest.importorskip('pyarrow');pq=pytest.importorskip('pyarrow.parquet')
    p=tmp_path/'data.parquet';pq.write_table(pa.table({'time':pa.array([1700000000000000001,1700000000000000002],type=pa.timestamp('ns','UTC')),'x':pa.array([1,None],type=pa.int64()),'name':['NA','']}),p,compression='zstd')
    t=TemporalSpec(ClockSpec('time',encoding='native'),(MeasurementSpec('x'),MeasurementSpec('name',representation='categorical')))
    r=run([input_at(p,t)])
    assert family(r,'panel')[0]['observed_last_tick']=='1700000000000000002'
    assert r.parsing['data']['typed_nulls']
    states=family(r,'chronology')[0]['value_states'];assert {'measurement':'name','state':'valid','cells':2} in states
    assert {'measurement':'x','state':'missing','cells':1} in states


def test_parquet_batch_limit_and_nested(tmp_path):
    pa=pytest.importorskip('pyarrow');pq=pytest.importorskip('pyarrow.parquet')
    p=tmp_path/'large.parquet';pq.write_table(pa.table({'time':['2020-01-01T00:00:00Z']*10,'x':['x'*1000]*10}),p)
    t=TemporalSpec(ClockSpec('time'),(MeasurementSpec('x',representation='categorical'),))
    with pytest.raises(AnalysisError,match='decoded-byte'):execute(TemporalAuditSpec((input_at(p,t),)),TemporalAnalysisConfig(limits=TemporalWorkLimits(decoded_batch_bytes=100)))
    pq.write_table(pa.table({'time':['2020-01-01T00:00:00Z'],'x':[[1,2]]}),p)
    with pytest.raises(ValueError,match='Unsupported'):run([input_at(p,t)])


def test_civil_schedule_dst_and_absent_entity(tmp_path):
    p=tmp_path/'data.csv';p.write_text('time,site,x\n2024-03-09T12:00:00-05:00,A,1\n2024-03-10T12:00:00-04:00,A,2\n2024-03-11T12:00:00-04:00,A,3\n')
    t=TemporalSpec(ClockSpec('time'),(MeasurementSpec('x'),),entity_columns=('site',),schedule=ScheduleSpec('civil',anchor='2024-03-09T12:00:00',civil_unit='daily',timezone='America/New_York'),active_intervals=(ActiveInterval('2024-03-09T00:00:00Z','2024-03-12T00:00:00Z'),ActiveInterval('2024-03-09T00:00:00Z','2024-03-12T00:00:00Z',('B',))))
    r=run([input_at(p,t)]);data=family(r,'continuity')[0]
    assert data['expected_records_or_opportunities']==6 and data['absent_expected_entities']==1
    assert data['occupied_distinct_slots']==3 and data['entity_weighted_coverage']==.5


def test_supplied_event_opportunities_not_outages(tmp_path):
    p=tmp_path/'events.csv';p.write_text('time,x\n2020-01-01T00:00:00Z,1\n')
    schedule=tmp_path/'schedule.csv';schedule.write_text('expected\n2020-01-01T00:00:00Z\n2020-01-02T00:00:00Z\n2020-01-03T00:00:00Z\n')
    t=TemporalSpec(ClockSpec('time'),(MeasurementSpec('x'),),observation='event',schedule=ScheduleSpec('supplied',source_id='calendar',time_column='expected',expectation='collection_opportunity'))
    r=run([input_at(p,t),input_at(schedule,None,role='schedule',id='calendar')])
    d=family(r,'continuity')[0]
    assert d['absent_expected_records_or_opportunities']==2
    assert d['compressed_gap_intervals'] is None and d['longest_gap_slots'] is None
    assert 'not computed' in d['gap_reporting']
    assert all('absent_tick' in x and 'first_absent_slot' not in x for x in d['gap_witnesses'])
    assert not any(f['evidence_type']=='declared_violation' for f in r.findings)


def test_evaluation_half_open_membership(tmp_path):
    p=tmp_path/'data.csv';p.write_text('time,id,x\n2020-01-01T00:00:00Z,A,1\n2020-01-02T00:00:00Z,A,2\n2020-01-03T00:00:00Z,B,3\n')
    t=TemporalSpec(ClockSpec('time'),(MeasurementSpec('x'),),entity_columns=('id',))
    f=TemporalFoldSpec('f','data','data',ActiveInterval('2020-01-01T00:00:00Z','2020-01-02T00:00:00Z'),ActiveInterval('2020-01-02T00:00:00Z','2020-01-04T00:00:00Z'),chronology='global',entity_separation='disjoint')
    r=run([input_at(p,t)],evaluation=TemporalEvaluationSpec((f,)))
    d=family(r,'evaluation')[0]
    assert d['train_rows']==1 and d['evaluation_rows']==2
    assert d['violated_requirements']==['entity separation'] and d['evidence_mode']=='window_plan_feasibility'
    assert d['seen_entity_evaluation_rows']==1 and d['unseen_entity_evaluation_rows']==1


def test_conditional_wide_long_equivalence_and_sparse_counterexample(tmp_path):
    wide=tmp_path/'wide.csv';wide.write_text('time,x,y\n0,1,2\n10,,3\n')
    long=tmp_path/'long.csv';long.write_text('time,measurement,v\n0,x,1\n0,y,2\n10,x,\n10,y,3\n')
    clock=ClockSpec('time',encoding='epoch',epoch_unit='ns');m=(MeasurementSpec('x'),MeasurementSpec('y'))
    tw=TemporalSpec(clock,m);tl=TemporalSpec(clock,m,layout='long',measurement_column='measurement',value_column='v')
    a=run([input_at(wide,tw)]);b=run([input_at(long,tl)])
    assert family(a,'chronology')[0]['value_states']==family(b,'chronology')[0]['value_states']
    long.write_text('time,measurement,v\n0,x,1\n0,y,2\n10,y,3\n');c=run([input_at(long,tl)])
    assert family(a,'chronology')[0]['value_states']!=family(c,'chronology')[0]['value_states']


def test_revision_completeness_and_later_restoration(tmp_path):
    p=tmp_path/'data.csv';p.write_text('time,key,x,cutoff\n2020-01-01T00:00:00Z,A,3,2020-01-05T00:00:00Z\n2020-01-01T00:00:00Z,B,4,2020-01-05T00:00:00Z\n')
    hp=tmp_path/'history.csv';hp.write_text('key,value,available,state\nA,1,2020-01-02T00:00:00Z,valid\nA,,2020-01-03T00:00:00Z,retracted\nA,3,2020-01-04T00:00:00Z,valid\n')
    t=TemporalSpec(ClockSpec('time'),(MeasurementSpec('x'),),observation_keys=('key',))
    h=FeatureHistorySpec('h','data','hist',('x',),('key',),('key',),{'x':'value'},ClockSpec('available'),ClockSpec('cutoff'),state_column='state',completeness='complete',coverage_start='2020-01-01T00:00:00Z',coverage_end='2020-02-01T00:00:00Z',initial_creation_included=True,latest_available_required=True)
    r=run([input_at(p,t),input_at(hp,None,role='history',id='hist')],histories=(h,));d=family(r,'revision_history')[0]
    assert d['comparison_states']=={'agreement':1,'no_eligible_revision':1}
    assert d['no_eligible_complete']==1
    assert any(f['title']=='No eligible feature revision in declared complete history' for f in r.findings)


def test_contract_strictness_and_override(tmp_path):
    with pytest.raises(ValueError,match='Unknown'):ClockSpec.from_dict({'column':'time','guess':True})
    p=tmp_path/'data.csv';p.write_text('time,x,y\n0,1,2\n')
    t=TemporalSpec(ClockSpec('time',encoding='epoch',epoch_unit='ns'),(MeasurementSpec('x'),MeasurementSpec('y')))
    a=FeatureAvailabilitySpec('all','data',('x','y'),ClockSpec('time',encoding='epoch',epoch_unit='ns'),method='static',static='unknown')
    with pytest.raises(ValueError,match='Competing'):TemporalAuditSpec((input_at(p,t),),availability=(a,replace(a,id='second',features=('x',))))
    TemporalAuditSpec((input_at(p,t),),availability=(a,replace(a,id='second',features=('x',),replaces='all')))
    with pytest.raises(ValueError,match='CSV'):DatasetSpec(str(p),format='parquet')
    with pytest.raises(ValueError,match='disjoint_labels requires'):
        TemporalFoldSpec.from_dict({'id':'f','train_source_id':'train','evaluation_source_id':'test','disjoint_labels':True})
    with pytest.raises(ValueError,match='both endpoint clocks'):
        TemporalFoldSpec('f','train','test',disjoint_labels=True,label_start=ClockSpec('time'))


def test_combined_observed_and_expected_series_limit(tmp_path):
    p=tmp_path/'data.csv';p.write_text('time,site,x\n0,A,1\n')
    c=ClockSpec('time',encoding='epoch',epoch_unit='ns');t=TemporalSpec(c,(MeasurementSpec('x'),),entity_columns=('site',))
    cfg=TemporalAnalysisConfig(limits=TemporalWorkLimits(max_series=1),behavior=TemporalBehaviorSpec(enabled=False))
    with pytest.raises(AnalysisError,match='Combined temporal series'):
        execute(TemporalAuditSpec((input_at(p,t,id='one'),input_at(p,t,id='two'))),cfg)
    calendar=tmp_path/'calendar.csv';calendar.write_text('expected,site\n0,A\n0,B\n')
    t=replace(t,schedule=ScheduleSpec('supplied',source_id='calendar',time_column='expected',entity_columns=('site',)))
    with pytest.raises(AnalysisError,match='Combined observed/expected temporal series'):
        execute(TemporalAuditSpec((input_at(p,t),input_at(calendar,None,role='schedule',id='calendar'))),cfg)


def test_empty_parquet_and_typed_all_null_target(tmp_path):
    pa=pytest.importorskip('pyarrow');pq=pytest.importorskip('pyarrow.parquet')
    p=tmp_path/'empty.parquet';pq.write_table(pa.table({'time':pa.array([],type=pa.timestamp('ns','UTC')),'x':pa.array([],type=pa.float64())}),p)
    t=TemporalSpec(ClockSpec('time',encoding='native'),(MeasurementSpec('x'),))
    r=run([input_at(p,t)])
    assert family(r,'chronology')[0]['cells']==0
    assert any('No usable chronology' in (x['reason'] or '') for x in r.checks)
    pq.write_table(pa.table({'time':pa.array([0],type=pa.timestamp('ns','UTC')),'x':[1.0],'target':pa.nulls(1)}),p)
    r=run([input_at(p,t,task=TaskSpec('regression','target'))])
    assert family(r,'annotations')[0]['targets'][0]['absent']==1


def test_exact_decimal_revisions_and_boolean_value_states(tmp_path):
    from decimal import Decimal
    pa=pytest.importorskip('pyarrow');pq=pytest.importorskip('pyarrow.parquet')
    p=tmp_path/'d.parquet';hp=tmp_path/'h.parquet'
    typ=pa.decimal128(30,1)
    pq.write_table(pa.table({'time':[0,0],'key':['A','B'],'x':pa.array([Decimal('99999999999999999999.1'),Decimal('99999999999999999999.1')],type=typ),'cutoff':[5,5],'flag':['true','oops']}),p)
    pq.write_table(pa.table({'key':['A','B'],'v':pa.array([Decimal('99999999999999999999.1'),Decimal('99999999999999999999.2')],type=typ),'available':[3,3]}),hp)
    c=ClockSpec('time',encoding='epoch',epoch_unit='ns');t=TemporalSpec(c,(MeasurementSpec('x'),MeasurementSpec('flag',representation='boolean')),observation_keys=('key',))
    h=FeatureHistorySpec('h','data','hist',('x',),('key',),('key',),{'x':'v'},replace(c,column='available'),replace(c,column='cutoff'))
    r=run([input_at(p,t),input_at(hp,None,role='history',id='hist')],histories=(h,))
    assert family(r,'revision_history')[0]['comparison_states']=={'agreement':1,'mismatch':1}
    assert {'measurement':'flag','state':'invalid','cells':1} in family(r,'chronology')[0]['value_states']
