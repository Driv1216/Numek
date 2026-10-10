"""Full-population temporal evidence and bounded retained witnesses."""
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import asdict, replace
from datetime import datetime, timedelta, date, timezone
import calendar
import json
import math
import duckdb
from datatrust.contracts import AnalysisError
from datatrust.scalable import fail
from datatrust.temporal_normalization import (DAY,EPOCH,wall_ticks,zone,interval_ticks,literal_tick,normalize_clock,key_sql)


class Evidence:
    def __init__(self,work,config):
        self.work=work;self.config=config;self.records=[];self.checks=[];self.findings=[];self.coverage={};self.omissions={};self.visits=0;self.comparisons=0;self.detailed_series=0
    def add(self,family,source,data,*,measurement=None,entity=None,population='all eligible declared records',exclusions=None,requirement=None,assumptions=None,blocked=None,witnesses=None):
        ident='t'+str(len(self.records)+1)
        record={'id':ident,'check_id':family,'source_ids':[source] if isinstance(source,str) else source,'measurement':measurement,'entity':entity,'clock':data.get('clock'),'population':population,'data':data,'exclusions':exclusions or {},'requirement':requirement,'assumption_dependencies':assumptions or [],'witnesses':(witnesses or [])[:self.config.limits.witnesses]}
        self.records.append(record)
        self.checks.append({'check_id':ident+':'+family,'applicability':'blocked' if blocked else 'applicable','execution':'skipped' if blocked else 'completed','reason':blocked,'evidence_refs':[ident],'version':'temporal_reliability_v1'})
        self.coverage[ident]={'family':family,'status':'blocked' if blocked else 'completed','reason':blocked,'population':population}
        return ident
    def finding(self,ident,title,*,kind='investigation_candidate',detail='',action='Review the declarations and bounded witnesses.',limitations=None):
        r=next(x for x in self.records if x['id']==ident)
        self.findings.append({'id':'f'+str(len(self.findings)+1),'title':title,'evidence_type':kind,'evidence_refs':[ident],'source_ids':r['source_ids'],'measurement':r['measurement'],'finding':detail,'next_action':action,'limitations':limitations or [],'priority':'High' if kind=='declared_violation' else 'Moderate'})
    def query(self,sql,params=()):return self.work.con.execute(sql,params)
    def witnesses(self,sql,params=()):
        cur=self.query(sql+f' LIMIT {self.config.limits.witnesses}',params);names=[c[0] for c in cur.description]
        return [dict(zip(names,row)) for row in cur.fetchall()]
    @contextmanager
    def optional(self,family,source,*,relation=None):
        mark=(len(self.records),len(self.checks),len(self.findings),dict(self.coverage),dict(self.omissions))
        tables={x[0] for x in self.query('SHOW TABLES').fetchall()}
        selected=self.detailed_series;done=set(self.series_sources_done) if hasattr(self,'series_sources_done') else None
        relation_state=deepcopy(vars(relation)) if relation is not None else None
        visits,comparisons=self.visits,self.comparisons
        try:yield
        except (MemoryError,AnalysisError):raise
        except Exception as exc:
            if isinstance(exc,duckdb.Error) and any(s in str(exc).lower() for s in ('out of memory','io error','disk','allocation')):raise
            # Optional algorithms only write newly created intermediates. Preserve previously committed tables.
            try:
                for table in {x[0] for x in self.query('SHOW TABLES').fetchall()}-tables:
                    self.query('DROP TABLE "'+table.replace('"','""')+'"')
            except Exception as cleanup:
                raise AnalysisError('Optional diagnostic intermediates could not be restored.',code='optional_rollback_failed') from cleanup
            self.detailed_series=selected
            if done is None:self.__dict__.pop('series_sources_done',None)
            else:self.series_sources_done=done
            if relation is not None:relation.__dict__.clear();relation.__dict__.update(relation_state)
            self.records=self.records[:mark[0]];self.checks=self.checks[:mark[1]];self.findings=self.findings[:mark[2]];self.coverage=mark[3];self.omissions=mark[4]
            # Attempted work remains charged: rollback must not allow repeated failures to bypass work limits.
            ident=self.add(family,source,{'failure':str(exc),'failed_attempt_observation_visits':self.visits-visits,'failed_attempt_comparisons':self.comparisons-comparisons},blocked='Optional stage failed; earlier committed evidence remains available.')
            self.checks[-1].update(execution='failed');self.coverage[ident]['status']='failed'
    def reserve(self,visits,comparisons=0):
        if self.visits+visits>self.config.limits.observation_visits or self.comparisons+comparisons>self.config.limits.max_comparisons:return False
        self.visits+=visits;self.comparisons+=comparisons;return True


def structural(e,r):
    s=r.temporal;con=e.work.con;cells=r.cells;u=r.unique
    states=dict(con.execute(f'SELECT time_state,count(*) FROM {cells} GROUP BY time_state').fetchall())
    value_states=[{'measurement':m,'state':state,'cells':n} for m,state,n in con.execute(f'SELECT measurement,value_state,count(*) FROM {cells} GROUP BY ALL ORDER BY ALL').fetchall()]
    missing_keys=con.execute(f'SELECT count(*) FILTER(WHERE NOT entity_ok),count(*) FILTER(WHERE NOT observation_key_ok) FROM {cells}').fetchone()
    precision=dict(con.execute(f'SELECT precision,count(*) FROM {cells} GROUP BY precision').fetchall())
    ident=e.add('chronology',r.id,{'rows':r.rows,'cells':r.cell_count,'declared_dense_missing_cells':getattr(r,'dense_missing',0),'clock':asdict(s.clock),'parse_states':states,'precision_counts':{str(k):v for k,v in precision.items()},'value_states':value_states,'missing_entity_cells':missing_keys[0],'incomplete_observation_keys':missing_keys[1],'observation_meaning':s.observation,'clock_units':'civil days' if s.clock.kind=='civil_date' else 'nanoseconds','exact_ticks':True},exclusions={'entity_checks':missing_keys[0]},witnesses=e.witnesses(f"SELECT _row,measurement,time_state FROM {cells} WHERE time_state!='valid' ORDER BY _row,measurement"))
    if states.get('valid',0)==0:e.add('elapsed_chronology',r.id,{},blocked='No usable resolved chronology; temporal conclusions remain unanswered.')
    elif s.clock.kind=='local_datetime':e.add('elapsed_chronology',r.id,{},blocked='Local ordering is available; elapsed-time and cross-zone conclusions require resolved instants.')
    if sum(v for k,v in states.items() if k not in {'valid','missing'}):e.finding(ident,'Some declared clock values remain unresolved',detail='Dependent checks exclude unresolved temporal cells; the report does not treat them as compliant.')
    if not states.get('valid',0):e.add('temporal_scope',r.id,{'eligible_clock_cells':0},blocked='No usable chronology; dependent temporal conclusions are unanswered.')
    order=cells+'_order'
    con.execute(f'''CREATE TABLE {order} AS SELECT *,lag(t) OVER(PARTITION BY entity,measurement ORDER BY _row) previous_t,lag(time_state) OVER(PARTITION BY entity,measurement ORDER BY _row) previous_state FROM {cells} WHERE entity_ok AND cell_origin='supplied' ''' )
    backwards,entities,maxback=con.execute(f"SELECT count(*),count(DISTINCT entity),max(previous_t-t) FROM {order} WHERE time_state='valid' AND previous_state='valid' AND t<previous_t").fetchone()
    backward_rows=con.execute(f"SELECT count(DISTINCT _row) FROM {order} WHERE time_state='valid' AND previous_state='valid' AND t<previous_t").fetchone()[0]
    ident=e.add('ordering',r.id,{'adjacent_backward_cells':backwards,'affected_row_union':backward_rows,'affected_entities':entities,'largest_backward_step_ticks':str(maxback) if maxback is not None else None,'arrival_order_declared':s.source_order_is_arrival},witnesses=e.witnesses(f"SELECT _row,entity,measurement,CAST(t AS VARCHAR) time_tick,CAST(previous_t-t AS VARCHAR) backward_ticks FROM {order} WHERE time_state='valid' AND previous_state='valid' AND t<previous_t ORDER BY _row"))
    if backwards:e.finding(ident,'Source order contains backward temporal steps',detail='This describes file order'+(' under the declared arrival-order interpretation.' if s.source_order_is_arrival else '; arrival order was not declared.'))
    duplicates=con.execute(f'SELECT coalesce(sum(multiplicity-1),0),count(*) FILTER(WHERE multiplicity>1 AND states=1),count(*) FILTER(WHERE states>1),coalesce(sum(multiplicity) FILTER(WHERE states>1),0) FROM {u}').fetchone()
    ident=e.add('repetition',r.id,{'additional_observations':int(duplicates[0]),'identical_repeated_identities':duplicates[1],'conflicting_simultaneous_identities':duplicates[2],'conflicting_cells':int(duplicates[3]),'uniqueness_required':s.unique_observations,'event_identity_declared':bool(s.observation_keys)},requirement='unique_observations' if s.unique_observations else None,witnesses=e.witnesses(f'SELECT entity,measurement,observation_key,CAST(t AS VARCHAR) time_tick,multiplicity,states FROM {u} WHERE multiplicity>1 ORDER BY entity,measurement,t'))
    if duplicates[0] and s.unique_observations:e.finding(ident,'Declared temporal uniqueness is violated',kind='declared_violation')
    elif duplicates[2]:e.finding(ident,'Simultaneous measurements disagree',detail='Conflicts break order-dependent value sequences; duplicate timestamps alone are not a defect.')
    summary=con.execute(f'SELECT min(t),max(t),count(DISTINCT entity) FROM {u}').fetchone()
    histories=u+'_histories';con.execute(f'CREATE TABLE {histories} AS SELECT entity,measurement,count(*) observations,sum(multiplicity) cells,min(t) first_t,max(t) last_t FROM {u} GROUP BY ALL')
    full=con.execute(f'SELECT count(*),min(observations),max(observations),avg(observations),avg(CAST(last_t-first_t AS DOUBLE)),sum(cells) FROM {histories}').fetchone()
    retain=e.config.limits.retained_details
    details=[{'entity':json.loads(entity),'measurement':m,'observations':n,'cells':int(c),'first_tick':str(lo),'last_tick':str(hi),'span_ticks':str(hi-lo)} for entity,m,n,c,lo,hi in con.execute(f'SELECT * FROM {histories} ORDER BY observations,entity,measurement LIMIT {retain}').fetchall()]
    e.omissions[r.id+':entity_histories']=max(0,full[0]-len(details))
    bins=[{'observations':n,'series':c} for n,c in con.execute(f'SELECT CASE WHEN observations=1 THEN 1 WHEN observations<10 THEN 2 WHEN observations<100 THEN 3 ELSE 4 END bucket,count(*) FROM {histories} GROUP BY bucket ORDER BY bucket').fetchall()]
    e.add('panel',r.id,{'distinct_entities':summary[2],'distinct_series':r.series,'history_counts':{'min':full[1],'max':full[2],'entity_weighted_mean':full[3]},'history_length_bins':bins,'retained_histories':details,'observed_first_tick':str(summary[0]) if summary[0] is not None else None,'observed_last_tick':str(summary[1]) if summary[1] is not None else None,'observed_entry_exit_is_lifecycle':False},population='complete entity/observation keys with valid clocks')
    if s.assessment_time:
        if s.clock.kind=='local_datetime':e.add('freshness',r.id,{},blocked='Freshness needs resolved elapsed-time semantics.')
        else:
            assessment=literal_tick(s.assessment_time,s.clock)
            latest=con.execute(f'SELECT max(t) FROM {u} WHERE t<=?',[assessment]).fetchone()[0]
            future=con.execute(f'SELECT count(*) FROM {u} WHERE t>?',[assessment]).fetchone()[0]
            e.add('freshness',r.id,{'observations_after_assessment':future,'assessment_tick':str(assessment),'latest_observation_tick':str(latest) if latest is not None else None,'age_ticks':str(assessment-latest) if latest is not None else None},blocked='No eligible observation.' if latest is None else None)
    r.histories=histories


def ceil_sql(x,d):return f'(({x})//({d})+CASE WHEN ({x})%({d})>0 THEN 1 ELSE 0 END)'
def floor_sql(x,d):return f'(({x})//({d})-CASE WHEN ({x})%({d})<0 THEN 1 ELSE 0 END)'


def active_intervals(e,r):
    s=r.temporal;table=r.cells+'_active';con=e.work.con
    con.execute(f'CREATE TABLE {table}(entity VARCHAR,measurement VARCHAR,start_t HUGEINT,end_t HUGEINT,declared BOOLEAN)')
    if not s.active_intervals:
        con.execute(f'INSERT INTO {table} SELECT entity,measurement,min(t),max(t)+1,false FROM {r.unique} GROUP BY ALL')
    for interval in s.active_intervals:
        start,end=interval_ticks(interval,s.clock)
        if end<=start:raise ValueError('Lifecycle interval end must follow start.')
        if interval.measurement and interval.measurement not in {m.name for m in s.measurements}:raise ValueError('Lifecycle references an unknown measurement.')
        if interval.entity and len(interval.entity)!=len(s.entity_columns):raise ValueError('Lifecycle entity key width is incompatible.')
        ms=[interval.measurement] if interval.measurement else [m.name for m in s.measurements]
        for measurement in ms:
            if interval.entity or not s.entity_columns:
                entity=json.dumps(list(interval.entity),ensure_ascii=False,separators=(',',':'))
                con.execute(f'INSERT INTO {table} VALUES (?,?,?,?,true)',[entity,measurement,start,end])
            else:con.execute(f'INSERT INTO {table} SELECT DISTINCT entity,?,?,?,true FROM {r.cells} WHERE entity_ok',[measurement,start,end])
    overlap=con.execute(f'''SELECT count(*) FROM (SELECT start_t,lag(end_t) OVER(PARTITION BY entity,measurement ORDER BY start_t,end_t) AS prior FROM {table}) WHERE start_t<prior''').fetchone()[0]
    if overlap:raise ValueError('Lifecycle intervals for the same series must be disjoint.')
    count=con.execute(f'SELECT count(*) FROM (SELECT DISTINCT entity,measurement FROM {table})').fetchone()[0]
    if count>e.config.limits.max_series:fail('Expected series exceeds hard limit.','temporal_series_limit')
    r.active=table;return table


def civil_grid(e,r,active):
    s=r.temporal.schedule;clock=r.temporal.clock
    lo,hi=e.query(f'SELECT min(start_t),max(end_t) FROM {active}').fetchone()
    table=r.cells+'_calendar';e.query(f'CREATE TABLE {table}(slot HUGEINT,t HUGEINT)')
    if lo is None:return table
    z=zone(s.timezone);anchor=datetime.fromisoformat(s.anchor)
    if anchor.tzinfo:anchor=anchor.astimezone(z).replace(tzinfo=None)
    # Generate a single civil calendar; series use arithmetic ordinal ranges, never a time Cartesian product.
    lower=date(1970,1,1)+timedelta(days=int(lo)) if clock.kind=='civil_date' else (EPOCH+timedelta(microseconds=int(lo)//1000)).replace(tzinfo=timezone.utc).astimezone(z).date()
    upper=date(1970,1,1)+timedelta(days=int(hi)) if clock.kind=='civil_date' else (EPOCH+timedelta(microseconds=int(hi)//1000)).replace(tzinfo=timezone.utc).astimezone(z).date()
    if clock.kind=='local_datetime':raise ValueError('Civil schedules require a date or resolved instant clock.')
    if s.civil_unit=='monthly':
        idx=(lower.year-anchor.year)*12+lower.month-anchor.month-1
    else:idx=(lower-anchor.date()).days//(1 if s.civil_unit=='daily' else 7)-1
    batch=[];count=0
    while True:
        if s.civil_unit=='monthly':
            month=anchor.year*12+anchor.month-1+idx;y,m=divmod(month,12);m+=1
            if y<1:idx+=1;continue
            if y>9999:break
            last=calendar.monthrange(y,m)[1]
            if anchor.day>last and s.month_end=='skip':idx+=1;continue
            dt=anchor.replace(year=y,month=m,day=min(anchor.day,last))
        else:
            try:dt=anchor+timedelta(days=idx*(1 if s.civil_unit=='daily' else 7))
            except OverflowError:break
        if dt.date()>upper+timedelta(days=1):break
        if dt.date()>=lower-timedelta(days=32):
            if clock.kind=='civil_date':tick=(dt.date()-date(1970,1,1)).days
            else:
                from datatrust.temporal_normalization import parse_clock
                tick,state,_,_=parse_clock(dt.isoformat(),replace(clock,encoding='iso',format=None,epoch_unit=None,timezone=s.timezone,timezone_column=None,fold_column=None,ambiguity='unresolved'))
                if state!='valid':raise ValueError('Civil schedule contains an unresolved/nonexistent instant; supply explicit instants.')
            batch.append((count,tick));count+=1
            if count>e.config.execution.max_rows:fail('Civil calendar exceeds declared job row limit.','schedule_limit')
            if len(batch)>=4096:e.query(f'INSERT INTO {table} VALUES '+','.join('(?,?)' for _ in batch),[v for row in batch for v in row]);batch=[];e.work.check('civil schedule normalization')
        idx+=1
    if batch:e.query(f'INSERT INTO {table} VALUES '+','.join('(?,?)' for _ in batch),[v for row in batch for v in row])
    return table


def continuity(e,r,relations):
    s=r.temporal;con=e.work.con;active=active_intervals(e,r);u=r.unique
    if s.required_lookback_ns:
        if s.clock.kind!='instant':e.add('lookback',r.id,{},blocked='Elapsed lookback requirements need resolved instants.')
        else:
            need=int(s.required_lookback_ns);n,bad=con.execute(f'SELECT count(*),count(*) FILTER(WHERE last_t-first_t<?) FROM {r.histories}',[need]).fetchone()
            ident=e.add('lookback',r.id,{'required_ns':str(need),'series':n,'insufficient_observed_spans':bad,'span_is_continuous_support':False,'support_meaning':'Observed series span only; this does not establish internal continuity or feature-specific point-in-time availability.'},requirement='required_lookback_ns')
            if bad:e.finding(ident,'Observed histories are shorter than the declared lookback',kind='declared_violation')
    if s.schedule.kind=='none':
        intervals=con.execute(f'''SELECT count(*),min(d),max(d) FROM (SELECT t-lag(t) OVER(PARTITION BY entity,measurement ORDER BY t) d FROM (SELECT DISTINCT entity,measurement,t FROM {u})) WHERE d IS NOT NULL''').fetchone()
        e.add('continuity',r.id,{'schedule':'none','inter_observation_distances':{'count':intervals[0],'minimum_ticks':str(intervals[1]) if intervals[1] is not None else None,'maximum_ticks':str(intervals[2]) if intervals[2] is not None else None},'expected_records':None,'leading_trailing_completeness':'unknown','timeline':coverage_timeline(e,r)},blocked='Elapsed distances unresolved for local clock.' if s.clock.kind=='local_datetime' else None)
        return
    schedule=s.schedule;expected=u+'_expected';occupied=u+'_occupied'
    if schedule.kind in {'fixed','civil'}:
        if schedule.kind=='fixed':
            if s.clock.kind!='instant':e.add('continuity',r.id,{},blocked='Fixed elapsed schedules require resolved instant clocks.');return
            anchor=literal_tick(schedule.anchor,s.clock);d=int(schedule.cadence_ns)
            con.execute(f'CREATE TABLE {expected} AS SELECT *,{ceil_sql(f"start_t-({anchor})",str(d))} first_slot,{ceil_sql(f"end_t-({anchor})",str(d))} end_slot FROM {active}')
            con.execute(f'CREATE TABLE {occupied} AS SELECT DISTINCT u.entity,u.measurement,{floor_sql(f"u.t-({anchor})",str(d))} slot,u.t FROM {u} u JOIN {active} a ON u.entity=a.entity AND u.measurement=a.measurement AND u.t>=a.start_t AND u.t<a.end_t WHERE (u.t-({anchor}))%{d}=0')
            r.grid={'kind':'fixed','anchor':anchor,'cadence':d}
        else:
            grid=civil_grid(e,r,active);r.grid={'kind':'civil','table':grid}
            con.execute(f'''CREATE TABLE {expected} AS SELECT a.*,coalesce(g1.slot+1,0) first_slot,coalesce(g2.slot+1,0) end_slot FROM {active} a ASOF LEFT JOIN {grid} g1 ON a.start_t>g1.t ASOF LEFT JOIN {grid} g2 ON a.end_t>g2.t''')
            con.execute(f'''CREATE TABLE {occupied} AS SELECT DISTINCT u.entity,u.measurement,g.slot,u.t FROM {u} u JOIN {grid} g ON u.t=g.t JOIN {active} a ON u.entity=a.entity AND u.measurement=a.measurement AND u.t>=a.start_t AND u.t<a.end_t''')
        gaps=u+'_gaps'
        con.execute(f'''CREATE TABLE {gaps} AS WITH points AS(
            SELECT entity,measurement,start_t,end_t,first_slot,end_slot,first_slot-1 slot FROM {expected}
            UNION ALL SELECT entity,measurement,start_t,end_t,first_slot,end_slot,end_slot FROM {expected}
            UNION ALL SELECT a.entity,a.measurement,a.start_t,a.end_t,a.first_slot,a.end_slot,o.slot FROM {expected} a JOIN {occupied} o ON a.entity=o.entity AND a.measurement=o.measurement AND o.slot>=a.first_slot AND o.slot<a.end_slot),
            steps AS(SELECT *,lead(slot) OVER(PARTITION BY entity,measurement,start_t,end_t ORDER BY slot) next_slot FROM points)
            SELECT entity,measurement,start_t,end_t,slot+1 first_absent_slot,next_slot end_absent_slot,next_slot-slot-1 absent_slots FROM steps WHERE next_slot-slot>1''')
        expected_count=int(con.execute(f'SELECT coalesce(sum(greatest(0,end_slot-first_slot)),0) FROM {expected}').fetchone()[0]);occupied_count=con.execute(f'SELECT count(*) FROM {occupied}').fetchone()[0]
        offgrid=con.execute(f'SELECT count(*) FROM {u} WHERE NOT EXISTS(SELECT 1 FROM {occupied} o WHERE o.entity={u}.entity AND o.measurement={u}.measurement AND o.t={u}.t)').fetchone()[0]
        gapn,longest=con.execute(f'SELECT count(*),max(absent_slots) FROM {gaps}').fetchone()
        detail=e.witnesses(f'SELECT entity,measurement,CAST(first_absent_slot AS VARCHAR) first_absent_slot,CAST(end_absent_slot AS VARCHAR) end_absent_slot,CAST(absent_slots AS VARCHAR) absent_slots FROM {gaps} ORDER BY absent_slots DESC,entity,measurement')
        absent=expected_count-occupied_count
    else:
        sr=relations[schedule.source_id];clock=normalize_clock(e.work,sr,replace(s.clock,column=schedule.time_column));entity,ok=key_sql(sr,schedule.entity_columns)
        if len(schedule.entity_columns)!=len(s.entity_columns):raise ValueError('Supplied schedule entity keys must match the analytical entity key width.')
        if schedule.measurement_column:
            mc=sr.col(schedule.measurement_column)
            if con.execute(f'SELECT count(*) FROM {sr.table} WHERE {mc} IS NULL OR {mc} NOT IN(SELECT unnest(?::VARCHAR[]))',[[m.name for m in s.measurements]]).fetchone()[0]:raise ValueError('Supplied schedule has undeclared measurement identities.')
            measurement=f'CAST({mc} AS VARCHAR)';join='';params=[]
        else:measurement='measurements.measurement';join=' CROSS JOIN (SELECT unnest(?::VARCHAR[]) measurement) measurements';params=[[m.name for m in s.measurements]]
        status='true'
        if schedule.collection_status_column:status=f'{sr.col(schedule.collection_status_column)} IN(SELECT unnest(?::VARCHAR[]))';params.append(list(schedule.collection_active_values))
        con.execute(f'''CREATE TABLE {expected} AS SELECT DISTINCT {entity} entity,{measurement} measurement,t FROM {sr.table} JOIN {clock} USING(_row){join} WHERE state='valid' AND {ok} AND {status}''',params)
        unresolved=con.execute(f"SELECT count(*) FROM {clock} WHERE state!='valid'").fetchone()[0]
        if unresolved:raise ValueError('Required supplied schedule has unresolved clocks; expected population cannot be established.')
        if s.active_intervals:con.execute(f'DELETE FROM {expected} WHERE NOT EXISTS(SELECT 1 FROM {active} a WHERE a.entity={expected}.entity AND a.measurement={expected}.measurement AND {expected}.t>=a.start_t AND {expected}.t<a.end_t)')
        con.execute(f'CREATE TABLE {occupied} AS SELECT DISTINCT a.* FROM {expected} a JOIN {u} u ON a.entity=u.entity AND a.measurement=u.measurement AND a.t=u.t')
        expected_count=con.execute(f'SELECT count(*) FROM {expected}').fetchone()[0];occupied_count=con.execute(f'SELECT count(*) FROM {occupied}').fetchone()[0];absent=expected_count-occupied_count
        offgrid=con.execute(f'SELECT count(*) FROM {u} u WHERE NOT EXISTS(SELECT 1 FROM {expected} a WHERE a.entity=u.entity AND a.measurement=u.measurement AND a.t=u.t)').fetchone()[0]
        missing=expected+'_missing';con.execute(f'CREATE TABLE {missing} AS SELECT * FROM {expected} a WHERE NOT EXISTS(SELECT 1 FROM {occupied} o WHERE a.entity=o.entity AND a.measurement=o.measurement AND a.t=o.t)')
        gapn=None;longest=None;detail=e.witnesses(f'SELECT entity,measurement,CAST(t AS VARCHAR) absent_tick FROM {missing} ORDER BY entity,measurement,t')
        r.grid={'kind':'supplied','table':expected}
    entity_population=expected if schedule.kind=='supplied' else active
    absent_entities=con.execute(f'SELECT count(*) FROM (SELECT DISTINCT entity FROM {entity_population} a WHERE NOT EXISTS(SELECT 1 FROM {u} u WHERE a.entity=u.entity))').fetchone()[0]
    denominator=expected_count
    data={'schedule':schedule.kind,'expectation':schedule.expectation,'expected_records_or_opportunities':expected_count,'occupied_distinct_slots':occupied_count,'absent_expected_records_or_opportunities':absent,'off_grid_or_outside_lifecycle_observations':offgrid,'compressed_gap_intervals':gapn,'longest_gap_slots':str(longest) if longest is not None else None,'absent_expected_entities':absent_entities,'observation_weighted_coverage':occupied_count/denominator if denominator else None,'leading_trailing_scope':'declared lifecycle' if s.active_intervals or schedule.kind=='supplied' else 'observed boundaries only','empty_long_rows_are_missing_cells':s.dense_long,'event_absence_establishes_outage':False,'gap_witnesses':detail}
    if schedule.kind=='supplied':data['gap_reporting']='Missing supplied opportunities and point witnesses only; compressed gap intervals and longest-gap slots are not computed.'
    # Per-series rates preserve the entity-weighted denominator including expected absent entities.
    if schedule.kind in {'fixed','civil'}:
        # Correct disjoint intervals with equal lengths: aggregate expectation independently of occupied slots.
        rates=con.execute(f'''WITH x AS(SELECT entity,measurement,sum(end_slot-first_slot) n FROM {expected} GROUP BY ALL),y AS(SELECT entity,measurement,count(*) n FROM {occupied} GROUP BY ALL) SELECT avg(coalesce(y.n,0)/nullif(x.n,0)::DOUBLE),count(*) FROM x LEFT JOIN y USING(entity,measurement)''').fetchone()
    else:
        rates=con.execute(f'''WITH x AS(SELECT entity,measurement,count(*) n FROM {expected} GROUP BY ALL),y AS(SELECT entity,measurement,count(*) n FROM {occupied} GROUP BY ALL) SELECT avg(coalesce(y.n,0)/nullif(x.n,0)::DOUBLE),count(*) FROM x LEFT JOIN y USING(entity,measurement)''').fetchone()
    data.update(entity_weighted_coverage=rates[0],expected_series=rates[1]);r.expected=expected;r.occupied=occupied
    data['timeline']=coverage_timeline(e,r)
    ident=e.add('continuity',[r.id,schedule.source_id] if schedule.kind=='supplied' else r.id,data,requirement=asdict(schedule),assumptions=['An expected collection opportunity does not require an event occurrence.'] if schedule.expectation=='collection_opportunity' else [],witnesses=detail)
    if absent and schedule.expectation=='required_record':e.finding(ident,'Declared observation schedule has absent records',kind='declared_violation',detail=f'{absent} expected distinct observation slots are absent; supplied null values count as occupied records.')
    elif absent:e.finding(ident,'Some declared collection opportunities have no supplied events',detail='Event absence alone does not establish collection failure or outage.')


def coverage_timeline(e,r):
    """A fixed-size overview; expectation arithmetic never expands absent slots."""
    con=e.work.con;lo,hi=con.execute(f'SELECT min(start_t),max(end_t) FROM {r.active}').fetchone()
    if hasattr(r,'grid') and r.grid['kind']=='supplied':
        first,last=con.execute(f'SELECT min(t),max(t) FROM {r.expected}').fetchone()
        if first is not None:lo=first if lo is None else min(lo,first);hi=last+1 if hi is None else max(hi,last+1)
    if lo is None:return []
    table=r.cells+'_coverage_bins';con.execute(f'CREATE TABLE {table}(bin INTEGER,start_t HUGEINT,end_t HUGEINT)')
    span=hi-lo;bins=min(12,e.config.limits.max_windows)
    con.executemany(f'INSERT INTO {table} VALUES (?,?,?)',[(i,lo+span*i//bins,lo+span*(i+1)//bins) for i in range(bins)])
    counts=con.execute(f"SELECT b.bin,count(x._row),count(x._row) FILTER(WHERE value_state='missing'),count(x._row) FILTER(WHERE value_state IN('invalid','nonfinite')) FROM {table} b LEFT JOIN {r.cells} x ON x.t>=b.start_t AND x.t<b.end_t AND time_state='valid' GROUP BY b.bin ORDER BY b.bin").fetchall()
    expected={};occupied={}
    if hasattr(r,'grid') and hasattr(r,'expected'):
        if r.grid['kind']=='fixed':
            anchor=r.grid['anchor'];d=r.grid['cadence']
            sql=f"SELECT b.bin,coalesce(sum(greatest(0,{ceil_sql(f'least(a.end_t,b.end_t)-({anchor})',str(d))}-{ceil_sql(f'greatest(a.start_t,b.start_t)-({anchor})',str(d))})),0) FROM {table} b LEFT JOIN {r.active} a ON a.start_t<b.end_t AND a.end_t>b.start_t GROUP BY b.bin"
            expected=dict(con.execute(sql).fetchall())
        elif r.grid['kind']=='civil':
            grid=r.grid['table'];clipped=table+'_clipped'
            con.execute(f"CREATE TABLE {clipped} AS SELECT b.bin,greatest(a.start_t,b.start_t) start_t,least(a.end_t,b.end_t) end_t FROM {table} b JOIN {r.active} a ON a.start_t<b.end_t AND a.end_t>b.start_t")
            expected=dict(con.execute(f"SELECT a.bin,sum(coalesce(g2.slot+1,0)-coalesce(g1.slot+1,0)) FROM {clipped} a ASOF LEFT JOIN {grid} g1 ON a.start_t>g1.t ASOF LEFT JOIN {grid} g2 ON a.end_t>g2.t GROUP BY a.bin").fetchall())
        else:expected=dict(con.execute(f'SELECT b.bin,count(x.t) FROM {table} b LEFT JOIN {r.expected} x ON x.t>=b.start_t AND x.t<b.end_t GROUP BY b.bin').fetchall())
        occupied=dict(con.execute(f'SELECT b.bin,count(x.t) FROM {table} b LEFT JOIN {r.occupied} x ON x.t>=b.start_t AND x.t<b.end_t GROUP BY b.bin').fetchall())
    result=[]
    for i,n,missing,invalid in counts:
        start,end=lo+span*i//bins,lo+span*(i+1)//bins;exp=expected.get(i,0) if expected else None;occ=occupied.get(i,0) if occupied else None
        result.append({'bin':i,'start_tick':str(start),'end_tick':str(end),'supplied_cells':n,'supplied_missing_cells':missing,'invalid_or_nonfinite_cells':invalid,'expected_slots_or_opportunities':int(exp) if exp is not None else None,'occupied_slots':occ,'absent_slots_or_opportunities':int(exp)-occ if exp is not None and occ is not None else None,'outside_expectation_period':exp==0 if exp is not None else None})
    return result
