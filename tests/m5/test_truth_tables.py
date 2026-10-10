from dataclasses import replace
import json
import math
from pathlib import Path
import threading
import pytest
from datatrust import *
from datatrust.temporal import execute
from .test_temporal import family
from .test_resources_and_semantics import input_at,run


def test_dense_long_missing_and_chunk_invariance(tmp_path):
    p=tmp_path/'data.csv';p.write_text('time,m,v\n0,x,1\n0,y,2\n10,y,3\n')
    t=TemporalSpec(ClockSpec('time',encoding='epoch',epoch_unit='ns'),(MeasurementSpec('x'),MeasurementSpec('y')),layout='long',measurement_column='m',value_column='v',dense_long=True)
    spec=TemporalAuditSpec((input_at(p,t),));cfg=TemporalAnalysisConfig(behavior=TemporalBehaviorSpec(enabled=False))
    a=execute(spec,replace(cfg,execution=replace(cfg.execution,batch_bytes=1024)));b=execute(spec,replace(cfg,execution=replace(cfg.execution,batch_bytes=10**6)))
    assert [x['data'] for x in a.evidence]==[x['data'] for x in b.evidence]
    assert family(a,'chronology')[0]['declared_dense_missing_cells']==1
    assert {'measurement':'x','state':'missing','cells':1} in family(a,'chronology')[0]['value_states']


def test_history_selected_id_and_malformed_rows(tmp_path):
    p=tmp_path/'data.csv';p.write_text('time,key,x,cutoff,chosen\n0,A,2,5,r2\n0,B,2,5,r2\n')
    hp=tmp_path/'hist.csv';hp.write_text('key,value,available,id\nA,1,3,r1\nA,2,8,r2\nB,1,3,r1\nB,2,bad,r2\n')
    c=ClockSpec('time',encoding='epoch',epoch_unit='ns');t=TemporalSpec(c,(MeasurementSpec('x'),),observation_keys=('key',))
    h=FeatureHistorySpec('h','data','hist',('x',),('key',),('key',),{'x':'value'},replace(c,column='available'),replace(c,column='cutoff'),revision_id_column='id',selected_revision_id_column='chosen')
    r=run([input_at(p,t),input_at(hp,None,role='history',id='hist')],histories=(h,))
    assert family(r,'selected_revision_timing')[0]['late_identified_revision_cells']==1
    assert family(r,'revision_history')[0]['comparison_states']=={'mismatch':1,'unresolved':1}
    record=next(x for x in r.evidence if x['check_id']=='revision_history');assert {x['source_id'] for x in record['source_references']}=={'data','hist'}


def test_integer_revision_equality_and_units(tmp_path):
    p=tmp_path/'data.csv';p.write_text('time,key,x,cutoff\n0,A,9007199254740993,5\n')
    hp=tmp_path/'hist.csv';hp.write_text('key,value,available\nA,9007199254740993,3\n')
    c=ClockSpec('time',encoding='epoch',epoch_unit='ns');t=TemporalSpec(c,(MeasurementSpec('x',unit='kg'),),observation_keys=('key',))
    h=FeatureHistorySpec('h','data','hist',('x',),('key',),('key',),{'x':'value'},replace(c,column='available'),replace(c,column='cutoff'))
    inputs=[input_at(p,t),input_at(hp,None,role='history',id='hist')]
    assert family(run(inputs,histories=(h,)),'revision_history')[0]['comparison_states']=={'agreement':1}
    assert family(run(inputs,histories=(replace(h,value_units={'x':'m'}),)),'revision_history')[0]['comparison_states']=={'incompatible_units':1}


def test_tie_order_known_missing_and_baseline(tmp_path):
    p=tmp_path/'data.csv';p.write_text('time,key,x,cutoff\n0,A,,5\n0,B,2,5\n')
    hp=tmp_path/'hist.csv';hp.write_text('key,value,available,ordinal,state\nA,1,3,1,valid\nA,,3,2,known_missing\nB,2,3,1,valid\n')
    c=ClockSpec('time',encoding='epoch',epoch_unit='ns');t=TemporalSpec(c,(MeasurementSpec('x'),),observation_keys=('key',))
    h=FeatureHistorySpec('h','data','hist',('x',),('key',),('key',),{'x':'value'},replace(c,column='available'),replace(c,column='cutoff'),tie_order_column='ordinal',tie_order_meaning='monotone revision sequence',state_column='state',baseline_time='4')
    r=run([input_at(p,t),input_at(hp,None,role='history',id='hist')],histories=(h,))
    assert family(r,'revision_history')[0]['comparison_states']=={'agreement':1,'agreement_known_missing':1}
    p.write_text('time,key,x,cutoff\n0,A,,2\n0,B,2,2\n')
    r=run([input_at(p,t),input_at(hp,None,role='history',id='hist')],histories=(h,))
    assert family(r,'revision_history')[0]['comparison_states']=={'no_eligible_revision':2}


def test_maturity_and_signed_delay_known_future(tmp_path):
    p=tmp_path/'data.csv';p.write_text('time,x,y,cutoff\n10,1,,5\n20,2,,25\n30,3,1,25\n')
    c=ClockSpec('time',encoding='epoch',epoch_unit='ns');t=TemporalSpec(c,(MeasurementSpec('x'),))
    a=FeatureAvailabilitySpec('a','data',('x',),replace(c,column='cutoff'),method='delay',source_clock=c,delay_ns='-10')
    m=OutcomeMaturitySpec('data','y','25',source_clock=c,delay_ns='10',fit_cutoff='35')
    r=run([input_at(p,t,task=TaskSpec('regression','y'))],availability=(a,),maturity=(m,))
    assert family(r,'availability')[0]['affected_row_union']==0
    assert not family(r,'past_observation')
    d=family(r,'outcome_maturity')[0]
    assert d['missing_already_due']==1 and d['missing_not_yet_due']==1 and d['observed_outcomes_unavailable_at_fit']==1
    assert family(r,'annotations')[0]['targets'][0]['observed']==1


def test_interval_label_purge_and_point_boundaries(tmp_path):
    a=tmp_path/'train.csv';a.write_text('time,x,ls,le\n0,1,0,10\n')
    b=tmp_path/'test.csv';b.write_text('time,x,ls,le\n10,2,10,20\n')
    c=ClockSpec('time',encoding='epoch',epoch_unit='ns');t=TemporalSpec(c,(MeasurementSpec('x'),))
    f=TemporalFoldSpec('f','train','test',chronology='global',label_start=replace(c,column='ls'),label_end=replace(c,column='le'),purge_ns='1',gap_basis='label',disjoint_labels=True)
    r=run([input_at(a,t,id='train'),input_at(b,t,id='test')],evaluation=TemporalEvaluationSpec((f,)))
    d=family(r,'evaluation')[0];assert d['evaluation_overlapping_label_intervals']==0 and d['violated_requirements']==['declared label purge/gap']
    f=replace(f,purge_ns=None);b.write_text('time,x,ls,le\n10,2,9,9\n');r=run([input_at(a,t,id='train'),input_at(b,t,id='test')],evaluation=TemporalEvaluationSpec((f,)))
    assert family(r,'evaluation')[0]['evaluation_overlapping_point_labels']==1


def test_origin_gap_without_chronology(tmp_path):
    a=tmp_path/'train.csv';a.write_text('time,x\n0,1\n')
    b=tmp_path/'test.csv';b.write_text('time,x\n5,2\n')
    c=ClockSpec('time',encoding='epoch',epoch_unit='ns');t=TemporalSpec(c,(MeasurementSpec('x'),))
    inputs=[input_at(a,t,id='train'),input_at(b,t,id='test')]
    f=TemporalFoldSpec('f','train','test',purge_ns='10')
    d=family(run(inputs,evaluation=TemporalEvaluationSpec((f,))),'evaluation')[0]
    assert d['origin_gap_scope']=='global' and d['chronological_gap_ticks']=='5'
    assert d['violated_requirements']==['declared gap']
    d=family(run(inputs,evaluation=TemporalEvaluationSpec((replace(f,purge_ns='5'),))),'evaluation')[0]
    assert d['violated_requirements']==[] and d['blocked_requirements']=={}
    b.write_text('time,x\nbad,2\n')
    result=run(inputs,evaluation=TemporalEvaluationSpec((f,)))
    assert 'origin_gap' in family(result,'evaluation')[0]['blocked_requirements']
    record=next(x for x in result.evidence if x['check_id']=='evaluation')
    assert next(x for x in result.checks if record['id'] in x['evidence_refs'])['applicability']=='blocked'


@pytest.mark.parametrize('train_point',[True,False])
@pytest.mark.parametrize('scope',['global','within_entity'])
def test_symmetric_point_interval_labels(tmp_path,train_point,scope):
    a=tmp_path/'train.csv';b=tmp_path/'test.csv'
    a.write_text('time,site,x,ls,le\n0,A,1,'+('15,15' if train_point else '10,20')+'\n')
    labels=[(10,15),(15,20),(10,20),(20,25)] if train_point else [(9,9),(10,10),(15,15),(20,20)]
    b.write_text('time,site,x,ls,le\n'+''.join(f'30,{site},2,{start},{end}\n' for site in ('A','B') for start,end in labels))
    c=ClockSpec('time',encoding='epoch',epoch_unit='ns');t=TemporalSpec(c,(MeasurementSpec('x'),),entity_columns=('site',))
    f=TemporalFoldSpec('f','train','test',label_start=replace(c,column='ls'),label_end=replace(c,column='le'),disjoint_labels=True,label_separation_scope=scope)
    d=family(run([input_at(a,t,id='train'),input_at(b,t,id='test')],evaluation=TemporalEvaluationSpec((f,))),'evaluation')[0]
    key='evaluation_overlapping_label_intervals' if train_point else 'evaluation_overlapping_point_labels'
    assert d[key]==(4 if scope=='global' else 2)
    assert d['violated_requirements']==['label separation']


def test_history_only_past_observation(tmp_path):
    p=tmp_path/'data.csv';p.write_text('time,key,x,cutoff\n10,A,1,5\n')
    hp=tmp_path/'history.csv';hp.write_text('key,v,available\nA,1,3\n')
    c=ClockSpec('time',encoding='epoch',epoch_unit='ns');t=TemporalSpec(c,(MeasurementSpec('x',past_observation=True),),observation_keys=('key',))
    h=FeatureHistorySpec('h','data','hist',('x',),('key',),('key',),{'x':'v'},replace(c,column='available'),replace(c,column='cutoff'))
    r=run([input_at(p,t),input_at(hp,None,role='history',id='hist')],histories=(h,))
    assert family(r,'revision_history')[0]['comparison_states']=={'agreement':1}
    assert family(r,'past_observation')[0]['observation_after_prediction_cells']==1
    assert family(r,'availability_unknown')[0]['features']==[]
    assert any(x['title']=='Declared past-observation features have future observation times' for x in r.findings)


def test_optional_atomic_rollback_and_required_failure(tmp_path,monkeypatch):
    import datatrust.temporal as module
    p=tmp_path/'data.csv';p.write_text('time,x\n0,1\n');spec=TemporalAuditSpec((input_at(p,TemporalSpec(ClockSpec('time',encoding='epoch',epoch_unit='ns'),(MeasurementSpec('x'),))),))
    def broken(e,r):
        if e.behavior_phase=='requested':
            e.add('uncommitted',r.id,{'bad':True});assert e.reserve(3,1)
            e.detailed_series+=1;e.series_sources_done={r.id}
            e.query('CREATE TABLE optional_leftover(x INTEGER)')
            r.behavior_windows=('optional_leftover',[]);r.behavior_cell_table='optional_leftover';r.requested_series_table='optional_leftover';r.clocks['uncommitted']='optional_leftover'
            raise RuntimeError('optional failure')
        assert e.detailed_series==0 and not hasattr(e,'series_sources_done')
        assert e.visits==3 and e.comparisons==1
        assert not any(hasattr(r,key) for key in ('behavior_windows','behavior_cell_table','requested_series_table')) and 'uncommitted' not in r.clocks
        e.query('CREATE TABLE optional_leftover(x INTEGER)')
        e.add('continued',r.id,{'restored':True})
    monkeypatch.setattr(module,'behavior',broken)
    cfg=TemporalAnalysisConfig(behavior=TemporalBehaviorSpec(requested_measurements=('x',)))
    r=execute(spec,cfg)
    assert r.execution['status']=='partial' and not family(r,'uncommitted') and family(r,'chronology') and family(r,'continued')
    failed=family(r,'behavior')[0]
    assert failed['failed_attempt_observation_visits']==3 and failed['failed_attempt_comparisons']==1
    def allocation(e,r):raise MemoryError('decoder allocation failed')
    monkeypatch.setattr(module,'behavior',allocation)
    with pytest.raises(MemoryError):execute(spec,TemporalAnalysisConfig())


def test_parent_termination_and_result_budget(tmp_path):
    p=tmp_path/'data.csv';p.write_text('time,x\n0,1\n');spec=TemporalAuditSpec((input_at(p,TemporalSpec(ClockSpec('time',encoding='epoch',epoch_unit='ns'),(MeasurementSpec('x'),))),))
    event=threading.Event();event.set()
    with pytest.raises(AnalysisError,match='cancelled'):DataTrust.audit_temporal(spec,TemporalAnalysisConfig(execution=ExecutionOptions(scratch_directory=str(tmp_path))),cancel=event)
    with pytest.raises(AnalysisError,match='deadline'):DataTrust.audit_temporal(spec,TemporalAnalysisConfig(execution=ExecutionOptions(max_seconds=.001,scratch_directory=str(tmp_path))))
    with pytest.raises(AnalysisError,match='JSON budget'):execute(spec,TemporalAnalysisConfig(execution=ExecutionOptions(result_bytes=100)))
    assert not list(tmp_path.glob('datatrust-m4-*'))


def test_missing_runs_break_and_seasonal_support(tmp_path):
    p=tmp_path/'data.csv';p.write_text('time,x\n'+''.join(f'{i},{"" if 12<=i<15 else i%4}\n' for i in range(40)))
    c=ClockSpec('time',encoding='epoch',epoch_unit='ns');t=TemporalSpec(c,(MeasurementSpec('x'),),schedule=ScheduleSpec('fixed',cadence_ns='1',anchor='0'))
    cfg=TemporalAnalysisConfig(behavior=TemporalBehaviorSpec(windows=2,min_phase_support=2,min_support=2,seasonality=(SeasonalSpec('data','x',period_ns='4',anchor='0',phases=4),)))
    r=execute(TemporalAuditSpec((input_at(p,t),)),cfg)
    assert r.execution['status']=='completed',str([x['data'] for x in r.evidence if 'failure' in x['data']])
    assert family(r,'runs')[0]['longest_missing_state_run']==3
    assert family(r,'seasonality')[0]['overall_cycles']==10
    assert family(r,'seasonality')[0]['comparisons'][0]['phase_matched_cdf']==0


def test_base_annotations_and_lexical_evaluation_groups(tmp_path):
    a=tmp_path/'train.csv';a.write_text('time,x,y,state,group\n0,1,,intentionally_unlabeled,001\n')
    b=tmp_path/'test.csv';b.write_text('time,x,y,state,group\n10,2,1,observed,1\n')
    c=ClockSpec('time',encoding='epoch',epoch_unit='ns');t=TemporalSpec(c,(MeasurementSpec('x'),))
    cfg=AnalysisConfig(annotations=AnnotationOptions(per_target={'y':AnnotationSpec('unknown','state')}),features=FeatureOptions({'x':'quantitative'}))
    inputs=[replace(input_at(a,t,id='train',task=TaskSpec('regression','y',feature_columns=('x',))),config=cfg),replace(input_at(b,t,id='test',task=TaskSpec('regression','y',feature_columns=('x',))),config=cfg)]
    f=TemporalFoldSpec('f','train','test',entity_separation='disjoint',group_columns=('group',))
    r=run(inputs,evaluation=TemporalEvaluationSpec((f,)))
    assert family(r,'annotations')[0]['targets'][0]['intentionally_unlabeled']==1
    assert family(r,'evaluation')[0]['shared_groups']==0


def test_civil_categorical_phase_matching(tmp_path):
    p=tmp_path/'phases.csv'
    from datetime import datetime,timedelta,timezone
    rows=['time,x']
    for day in range(56):
        stamp=datetime(2020,1,1,tzinfo=timezone.utc)+timedelta(days=day)
        rows.append(stamp.isoformat()+','+('weekend' if stamp.weekday()>4 else 'weekday'))
    p.write_text('\n'.join(rows)+'\n')
    t=TemporalSpec(ClockSpec('time'),(MeasurementSpec('x',representation='categorical'),))
    cfg=TemporalAnalysisConfig(behavior=TemporalBehaviorSpec(windows=2,min_phase_support=2,min_cycles=8,min_window_cycles=2,seasonality=(SeasonalSpec('data','x',kind='civil',civil_phase='weekday',timezone='UTC'),)))
    r=execute(TemporalAuditSpec((input_at(p,t),)),cfg)
    d=family(r,'seasonality')[0]
    assert d['comparisons'][0]['phase_matched_tv']==0
    assert d['comparisons'][0]['full_seasonal_explanation_claimed'] is False
    assert r.execution['status']=='completed'


def test_multivariate_and_annotation_windows(tmp_path):
    p=tmp_path/'pairs.csv';p.write_text('time,x,y,target\n0,1,2,1\n1,2,4,\n2,3,6,2\n3,4,8,3\n')
    c=ClockSpec('time',encoding='epoch',epoch_unit='ns');t=TemporalSpec(c,(MeasurementSpec('x'),MeasurementSpec('y')))
    item=input_at(p,t,task=TaskSpec('regression','target'))
    cfg=TemporalAnalysisConfig(behavior=TemporalBehaviorSpec(windows=2,multivariate_pairs=(('x','y'),)))
    r=execute(TemporalAuditSpec((item,)),cfg)
    assert [x['pearson'] for x in family(r,'multivariate')[0]['window_pairs']]==pytest.approx([1,1])
    windows=family(r,'annotation_windows')[0]['windows']
    assert [x['expected_coverage'] for x in windows]==[.5,1]
    assert [x['expected'] for x in windows]==[2,2]
    assert r.execution['status']=='completed'


def test_event_multiplicity_and_as_of_freshness(tmp_path):
    p=tmp_path/'events.csv';p.write_text('time,x\n0,1\n0,1\n10,2\n')
    c=ClockSpec('time',encoding='epoch',epoch_unit='ns')
    t=TemporalSpec(c,(MeasurementSpec('x'),),observation='event',assessment_time='5')
    r=execute(TemporalAuditSpec((input_at(p,t),)),TemporalAnalysisConfig())
    assert family(r,'runs')[0]['valid_observations']==3
    assert family(r,'repetition')[0]['additional_observations']==0
    d=family(r,'freshness')[0];assert d['latest_observation_tick']=='0' and d['age_ticks']=='5' and d['observations_after_assessment']==1


def test_conflicting_duplicate_ordinals_and_later_supersession(tmp_path):
    p=tmp_path/'d.csv';p.write_text('time,key,x,cutoff\n0,A,3,5\n0,A,4,9\n')
    hp=tmp_path/'h.csv';hp.write_text('key,v,available,ordinal\nA,1,3,1\nA,2,3,1\nA,3,3,2\nA,4,8,1\n')
    c=ClockSpec('time',encoding='epoch',epoch_unit='ns');t=TemporalSpec(c,(MeasurementSpec('x'),),observation_keys=('key',))
    h=FeatureHistorySpec('h','data','hist',('x',),('key',),('key',),{'x':'v'},replace(c,column='available'),replace(c,column='cutoff'),tie_order_column='ordinal',tie_order_meaning='ordinal within publication')
    r=run([input_at(p,t),input_at(hp,None,role='history',id='hist')],histories=(h,))
    assert family(r,'revision_history')[0]['comparison_states']=={'agreement':1,'ambiguous':1}


def test_window_rates_and_categorical_proportions(tmp_path):
    p=tmp_path/'states.csv';p.write_text('time,x,category\n0,1,a\n1,oops,a\n2,inf,b\n3,,b\n4,2,b\n')
    parsing=CsvParseOptions(column_types={'x':'string','category':'string'},missing_policy='empty_only')
    t=TemporalSpec(ClockSpec('time',encoding='epoch',epoch_unit='ns'),(MeasurementSpec('x'),MeasurementSpec('category',representation='categorical')))
    item=TemporalInputSpec('data',TemporalSourceSpec(str(p),parsing=parsing),t)
    r=execute(TemporalAuditSpec((item,)),TemporalAnalysisConfig(behavior=TemporalBehaviorSpec(windows=2)))
    numeric=next(x for x in family(r,'behavior_windows') if x['measurement']=='x')['windows']
    assert numeric[0]['invalid_rate']==.5
    assert numeric[1]['finite']==1
    assert numeric[1]['missing_rate']==pytest.approx(1/3) and numeric[1]['nonfinite_rate']==pytest.approx(1/3)
    categorical=next(x for x in family(r,'behavior_windows') if x['measurement']=='category')['windows']
    assert categorical[0]['category_proportions']==[{'value':'a','count':2,'proportion':1.0}]
    assert categorical[1]['category_proportions']==[{'value':'b','count':3,'proportion':1.0}]
    assert not any(f['title']=='Window effects meet configured investigation settings' for f in r.findings)


def test_large_exact_counts_render_without_javascript_rounding(tmp_path):
    p=tmp_path/'huge.csv';p.write_text('time,x\n0,1\n1000000000000000000,2\n')
    t=TemporalSpec(ClockSpec('time',encoding='epoch',epoch_unit='ns'),(MeasurementSpec('x'),),schedule=ScheduleSpec('fixed',cadence_ns='1',anchor='0'))
    r=run([input_at(p,t)])
    html=Path(r.generate_report(tmp_path/'large.html')).read_text()
    assert '999999999999999999' in html
    serialized=r.to_dict();d=next(x['data'] for x in serialized['evidence'] if x['check_id']=='continuity')
    assert d['absent_expected_records_or_opportunities']=='999999999999999999'


def test_civil_date_seasonality_without_instant_claim(tmp_path):
    from datetime import date,timedelta
    p=tmp_path/'dates.csv';p.write_text('day,x\n'+'\n'.join(f'{date(2020,1,1)+timedelta(days=i)},{i%7}' for i in range(56))+'\n')
    t=TemporalSpec(ClockSpec('day',kind='civil_date'),(MeasurementSpec('x'),))
    cfg=TemporalAnalysisConfig(behavior=TemporalBehaviorSpec(windows=2,min_phase_support=2,min_window_cycles=2,seasonality=(SeasonalSpec('data','x',kind='civil',civil_phase='weekday',timezone='UTC'),)))
    r=execute(TemporalAuditSpec((input_at(p,t),)),cfg)
    d=family(r,'seasonality')[0]
    assert len(d['comparisons'][0]['common_supported_phases'])==7
    assert 'no elapsed-time' in d['phase_clock_meaning']


def test_declared_observation_key_clocks_across_formats(tmp_path):
    pa=pytest.importorskip('pyarrow');pq=pytest.importorskip('pyarrow.parquet')
    p=tmp_path/'data.csv';p.write_text('time,id,x,cutoff,selected\n2023-11-14T17:13:20.000000001-05:00,001,2,2023-11-14T22:13:20.000000005Z,r2\n')
    hp=tmp_path/'history.parquet';pq.write_table(pa.table({'observed':pa.array([1700000000000000001,1700000000000000001],type=pa.timestamp('ns','UTC')),'id':['001','001'],'value':[2,3],'available':pa.array([1700000000000000003,1700000000000000008],type=pa.timestamp('ns','UTC')),'revision':['r1','r2']}),hp)
    c=ClockSpec('time');t=TemporalSpec(c,(MeasurementSpec('x'),),entity_columns=('id',),observation_keys=('id','time'))
    h=FeatureHistorySpec('h','data','hist',('x',),('id','time'),('id','observed'),{'x':'value'},ClockSpec('available',encoding='native'),replace(c,column='cutoff'),source_observation_clock=c,history_observation_clock=ClockSpec('observed',encoding='native'),revision_id_column='revision',selected_revision_id_column='selected')
    r=run([input_at(p,t),input_at(hp,None,role='history',id='hist')],histories=(h,))
    assert family(r,'revision_history')[0]['comparison_states']=={'agreement':1}
    assert family(r,'selected_revision_timing')[0]['late_identified_revision_cells']==1
    assert family(r,'revision_history')[0]['observation_key_comparison'].startswith('Explicit normalized')
    with pytest.raises(ValueError,match='both sides'):replace(h,history_observation_clock=None)


def test_supplied_calendar_absent_entity_and_timeline_domain(tmp_path):
    p=tmp_path/'data.csv';p.write_text('time,id,x\n2020-01-02T00:00:00Z,A,1\n')
    q=tmp_path/'calendar.csv';q.write_text('expected,id\n2020-01-01T00:00:00Z,B\n2020-01-02T00:00:00Z,A\n2020-01-03T00:00:00Z,B\n')
    t=TemporalSpec(ClockSpec('time'),(MeasurementSpec('x'),),entity_columns=('id',),schedule=ScheduleSpec('supplied',source_id='calendar',time_column='expected',entity_columns=('id',)))
    r=run([input_at(p,t),input_at(q,None,role='schedule',id='calendar')]);d=family(r,'continuity')[0]
    assert d['absent_expected_entities']==1 and d['expected_records_or_opportunities']==3
    assert d['entity_weighted_coverage']==.5
    assert sum(x['expected_slots_or_opportunities'] for x in d['timeline'])==3


def test_requested_series_precedes_automatic_search_across_sources(tmp_path):
    a=tmp_path/'first.csv';a.write_text('time,site,x\n'+''.join(f'{i},A,{i}\n' for i in range(100)))
    b=tmp_path/'requested.csv';b.write_text('time,site,x\n'+''.join(f'{i},B,{i}\n' for i in range(10)))
    t=TemporalSpec(ClockSpec('time',encoding='epoch',epoch_unit='ns'),(MeasurementSpec('x'),),entity_columns=('site',))
    spec=TemporalAuditSpec((input_at(a,t,id='first'),input_at(b,t,id='requested')))
    cfg=TemporalAnalysisConfig(limits=TemporalWorkLimits(detailed_series=1,observation_visits=40),behavior=TemporalBehaviorSpec(windows=2,requested_series=(TemporalSeriesSpec('requested','x',('B',)),)))
    r=execute(spec,cfg)
    records=[x for x in r.evidence if x['check_id']=='behavior_series']
    assert records[0]['source_ids']==['requested'] and records[0]['data']['details'][0]['selection']=='explicit request'
    scope=r.coverage['unsearched_analytical_scope']
    assert any(x['source_ids']==['first'] and x['scope'].get('unsearched_scope') for x in scope)
    assert all('details' not in x['scope'] for x in scope)
    assert r.execution['status']=='completed' and r.coverage['work_observation_visits']<=40
