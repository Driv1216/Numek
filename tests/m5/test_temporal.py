from dataclasses import replace
from datetime import datetime,timezone
from pathlib import Path
import json
import pytest
from datatrust import *
from datatrust.temporal import execute
from datatrust.temporal_normalization import parse_clock,DAY


def audit(tmp_path,text,*,temporal=None,**kwargs):
    p=tmp_path/'source.csv';p.write_text(text)
    t=temporal or TemporalSpec(ClockSpec('time',timezone='UTC'),(MeasurementSpec('x'),))
    spec=TemporalAuditSpec((TemporalInputSpec('data',TemporalSourceSpec(str(p)),t),),**kwargs)
    return execute(spec,TemporalAnalysisConfig(behavior=TemporalBehaviorSpec(enabled=False)))


def family(result,name):return [r['data'] for r in result.evidence if r['check_id']==name]


def test_exact_clocks_and_dst():
    c=ClockSpec('t',timezone='America/New_York')
    assert parse_clock('2024-11-03T01:30:00.123456789',c)[1]=='ambiguous_local_time'
    lo=parse_clock('2024-11-03T01:30:00.123456789',replace(c,ambiguity='earlier'))[0]
    hi=parse_clock('2024-11-03T01:30:00.123456789',replace(c,ambiguity='later'))[0]
    assert hi-lo==3600*10**9 and lo%10**9==123456789
    assert parse_clock('2024-03-10T02:30:00',c)[1]=='nonexistent_local_time'
    assert parse_clock('2020-01-01T00:00:00.0000000001Z',c)[1]=='unsupported_precision'
    assert parse_clock('2020-01-01T00:00:60Z',c)[1]=='leap_second'
    assert parse_clock('2020-01-01',c)[1]=='date_interval'
    assert parse_clock('9007199254740993',ClockSpec('t',encoding='epoch',epoch_unit='ns'))[0]==9007199254740993
    assert parse_clock('1969-12-31T23:59:59.999999999Z',c)[0]==-1


def test_fixed_gaps_duplicates_and_missing(tmp_path):
    t=TemporalSpec(ClockSpec('time',encoding='epoch',epoch_unit='ns'),(MeasurementSpec('x'),),schedule=ScheduleSpec('fixed',cadence_ns='10',anchor='0'),active_intervals=(ActiveInterval('0','100000000000'),))
    result=audit(tmp_path,'time,x\n0,1\n0,1\n20,\n30,2\n25,5\n',temporal=t)
    c=family(result,'continuity')[0]
    assert c['expected_records_or_opportunities']==10_000_000_000
    assert c['occupied_distinct_slots']==3 and c['absent_expected_records_or_opportunities']==9_999_999_997
    assert c['compressed_gap_intervals']==2
    assert family(result,'repetition')[0]['additional_observations']==1
    assert family(result,'chronology')[0]['value_states'][0]['cells']>=1
    assert result.schema_version=='1.4' and result.methodology_id=='temporal_reliability_v1'
    assert not list(tmp_path.glob('datatrust-m4-*'))


def test_bound_timing_and_unknown(tmp_path):
    p=tmp_path/'data.csv';p.write_text('time,x,y,cutoff,available\n2020-01-01T00:00:00Z,1,2,2020-01-02T00:00:00Z,2020-01-03T00:00:00Z\n')
    t=TemporalSpec(ClockSpec('time'),(MeasurementSpec('x'),MeasurementSpec('y')))
    a=FeatureAvailabilitySpec('x-time','data',('x',),ClockSpec('cutoff'),availability=ClockSpec('available'))
    result=execute(TemporalAuditSpec((TemporalInputSpec('data',TemporalSourceSpec(str(p)),t),),availability=(a,)),TemporalAnalysisConfig(behavior=TemporalBehaviorSpec(enabled=False)))
    assert family(result,'availability')[0]['affected_row_union']==1
    assert family(result,'availability_unknown')[0]['features']==['y']


def test_history_state_truth_table(tmp_path):
    p=tmp_path/'data.csv';p.write_text('time,key,x,cutoff\n2020-01-01T00:00:00Z,A,1,2020-01-04T00:00:00Z\n2020-01-01T00:00:00Z,B,2,2020-01-04T00:00:00Z\n2020-01-01T00:00:00Z,C,3,2020-01-04T00:00:00Z\n')
    hp=tmp_path/'history.csv';hp.write_text('key,value,available,state\nA,1,2020-01-02T00:00:00Z,valid\nA,2,2020-01-03T00:00:00Z,valid\nA,3,2020-01-03T00:00:00Z,valid\nB,2,2020-01-02T00:00:00Z,valid\nB,,2020-01-03T00:00:00Z,retracted\nC,3,2020-01-02T00:00:00Z,valid\nC,,2020-01-03T00:00:00Z,unknown\n')
    t=TemporalSpec(ClockSpec('time'),(MeasurementSpec('x'),),observation_keys=('key',))
    h=FeatureHistorySpec('h','data','hist',('x',),('key',),('key',),{'x':'value'},ClockSpec('available'),ClockSpec('cutoff'),state_column='state')
    result=execute(TemporalAuditSpec((TemporalInputSpec('data',TemporalSourceSpec(str(p)),t),TemporalInputSpec('hist',TemporalSourceSpec(str(hp)),role='history')),histories=(h,)),TemporalAnalysisConfig(behavior=TemporalBehaviorSpec(enabled=False)))
    states=family(result,'revision_history')[0]['comparison_states']
    assert states=={'ambiguous':1,'retracted_but_supplied':1,'unknown_state':1}


def test_windows_empty_reference_is_not_replaced(tmp_path):
    p=tmp_path/'data.csv';p.write_text('time,x\n2020-01-02T00:00:00Z,1\n2020-01-03T00:00:00Z,2\n')
    spec=TemporalAuditSpec((TemporalInputSpec('data',TemporalSourceSpec(str(p)),TemporalSpec(ClockSpec('time'),(MeasurementSpec('x'),))),))
    cfg=TemporalAnalysisConfig(behavior=TemporalBehaviorSpec(explicit_windows=(ActiveInterval('2020-01-01T00:00:00Z','2020-01-02T00:00:00Z'),ActiveInterval('2020-01-02T00:00:00Z','2020-01-04T00:00:00Z'))))
    result=execute(spec,cfg)
    assert result.execution['status']=='completed', str([c['data'] for c in result.evidence if 'failure' in c['data']])
    data=family(result,'behavior_windows')[0]
    assert data['windows'][0]['cells']==0 and data['windows'][0]['missing_rate'] is None
    assert data['reference_window']==0 and not data['reference_was_replaced']
    assert not any(f['title']=='Window effects meet configured investigation settings' for f in result.findings)
