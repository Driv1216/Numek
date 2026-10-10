"""Bounded behavioral investigation. Defaults are review settings, not defect tests."""
from dataclasses import asdict
from datetime import timedelta, timezone
import math
import pandas as pd
from datatrust.scalable import quantiles
from datatrust.distribution_effects import numeric_effect,categorical_effect,numeric_geometry
from datatrust.temporal_normalization import EPOCH,zone,interval_ticks,literal_tick


def windows(e,r):
    b=e.config.behavior;table=r.cells+'_windows';con=e.work.con
    con.execute(f'CREATE TABLE {table}(window_id INTEGER,start_t HUGEINT,end_t HUGEINT)')
    endpoints=[]
    if b.explicit_windows:
        for x in b.explicit_windows:
            lo,hi=interval_ticks(x,r.temporal.clock)
            if hi<=lo:raise ValueError('Behavior window_id end must follow start.')
            endpoints.append((lo,hi))
        if any(endpoints[i][0]<endpoints[i-1][1] for i in range(1,len(endpoints))):raise ValueError('Behavior windows must be ordered and disjoint.')
    else:
        lo,hi=con.execute(f"SELECT min(t),max(t) FROM {r.cells} WHERE time_state='valid'").fetchone()
        if lo is None:return table,[]
        width=hi-lo+1
        endpoints=[(lo+width*i//b.windows,lo+width*(i+1)//b.windows) for i in range(b.windows)]
    con.executemany(f'INSERT INTO {table} VALUES (?,?,?)',[(i,lo,hi) for i,(lo,hi) in enumerate(endpoints)])
    return table,endpoints


def window_summary(e,r,table,wins,measurement,cohort=None):
    con=e.work.con;condition='measurement=?'
    params=[measurement]
    if cohort:condition+=f' AND entity IN(SELECT entity FROM {cohort})'
    rows=con.execute(f'''SELECT w.window_id,w.start_t,w.end_t,count(x._row),count(x._row) FILTER(WHERE value_state='missing'),count(x._row) FILTER(WHERE value_state='invalid'),count(x._row) FILTER(WHERE value_state='nonfinite'),count(x.num),count(DISTINCT entity) FROM {wins} w LEFT JOIN {table} x ON w.window_id=x.window_id AND {condition} GROUP BY w.window_id,w.start_t,w.end_t ORDER BY w.window_id''',params).fetchall()
    result=[]
    for i,start,end,n,missing,invalid,nonfinite,finite,entities in rows:
        # Quantiles use exact ranks; unsafe numeric geometry blocks effect comparisons.
        q=None
        if finite:
            escaped="'"+measurement.replace("'","''")+"'"
            q=quantiles(con,table,'num',f"window_id={i} AND measurement={escaped} AND num IS NOT NULL"+(f' AND entity IN(SELECT entity FROM {cohort})' if cohort else ''))
        result.append({'window_id':i,'start_tick':str(start),'end_tick':str(end),'cells':n,'missing':missing,'invalid':invalid,'nonfinite':nonfinite,'finite':finite,'entities':entities,'missing_rate':missing/n if n else None,'invalid_rate':invalid/n if n else None,'nonfinite_rate':nonfinite/n if n else None,'quantiles':q,'iqr':q[4]-q[2] if q and math.isfinite(q[4]-q[2]) else None})
    declaration=next(m for m in r.temporal.measurements if m.name==measurement)
    if declaration.representation!='quantitative':
        escaped="'"+measurement.replace("'","''")+"'"
        omitted=0
        for window in result:
            predicate=f"window_id={window['window_id']} AND measurement={escaped} AND value_state='valid'"+(f' AND entity IN(SELECT entity FROM {cohort})' if cohort else '')
            groups=f'SELECT value,count(*) n FROM {table} WHERE {predicate} GROUP BY value'
            levels,total=con.execute(f'SELECT count(*),coalesce(sum(n),0) FROM ({groups})').fetchone()
            retained=con.execute(f'SELECT * FROM ({groups}) ORDER BY n DESC,value LIMIT ?',[e.config.limits.witnesses]).fetchall()
            window.update(category_levels=levels,category_population=int(total),category_proportions=[{'value':v,'count':count,'proportion':count/total} for v,count in retained],unretained_category_mass=(int(total)-sum(x[1] for x in retained))/total if total else None)
            omitted+=levels-len(retained)
        e.omissions[r.id+':'+measurement+':window categories'+(':stable cohort' if cohort else '')]=omitted
    return result


def compare_windows(e,r,table,measurement,summaries,pairs,*,cohort=None):
    con=e.work.con;b=e.config.behavior;details=[]
    escaped="'"+measurement.name.replace("'","''")+"'";cohort_filter=f' AND entity IN(SELECT entity FROM {cohort})' if cohort else ''
    for left,right in pairs:
        a,c=summaries[left],summaries[right]
        if not e.reserve(a['cells']+c['cells'],1):return details,True
        item={'reference_window':left,'comparison_window':right,'reference_support':a['cells'],'comparison_support':c['cells'],'reference_iqr':a['iqr'],'reference_span':[a['start_tick'],a['end_tick']],'reference_entities':a['entities'],'comparison_entities':c['entities'],'unit':measurement.unit,'thresholds_are_investigation_defaults':True}
        change=c['missing_rate']-a['missing_rate'] if a['missing_rate'] is not None and c['missing_rate'] is not None else None
        item.update(missingness_change=change,missingness_review=change is not None and min(a['cells'],c['cells'])>=b.min_support and change>=b.missingness_increase)
        pa=f"window_id={left} AND measurement={escaped} AND value_state='valid'"+cohort_filter;pb=f"window_id={right} AND measurement={escaped} AND value_state='valid'"+cohort_filter
        if measurement.representation=='quantitative':
            unsafe=con.execute(f'SELECT count(*) FROM {table} WHERE (window_id=? OR window_id=?) AND measurement=? AND value_state=\'valid\' AND num IS NULL',[left,right,measurement.name]).fetchone()[0]
            if unsafe:item['distribution_block']='unsafe_numeric_geometry';details.append(item);continue
            na,nb=a['finite'],c['finite'];pa+=' AND num IS NOT NULL';pb+=' AND num IS NOT NULL'
            if not na or not nb:item['distribution_block']='empty_finite_population';details.append(item);continue
            block=numeric_geometry(con,table,'num',pa) or numeric_geometry(con,table,'num',pb)
            if block:item['distribution_block']=block;details.append(item);continue
            distance,w1,_=numeric_effect(con,table,'num',pa,table,'num',pb,na,nb,constant_zero=True)
            if w1 is not None and not math.isfinite(w1):w1=None;item['wasserstein_block']='statistic_overflow'
            iqr=a['iqr'];norm=w1/iqr if w1 is not None and iqr is not None and iqr>0 and math.isfinite(w1/iqr) else None
            item.update(cdf_distance=distance,wasserstein_1=w1,normalized_w1=norm,normalization_block=None if norm is not None else 'zero_or_unsafe_reference_iqr',distribution_review=min(na,nb)>=b.min_support and (distance>=b.distribution_effect or norm is not None and norm>=b.normalized_w1))
        else:
            na=con.execute(f'SELECT count(*) FROM {table} WHERE {pa}').fetchone()[0];nb=con.execute(f'SELECT count(*) FROM {table} WHERE {pb}').fetchone()[0]
            if not na or not nb:item['distribution_block']='empty_observed_population';details.append(item);continue
            item.update(categorical_effect(con,table,'value',pa,table,'value',pb,na,nb));item['distribution_review']=min(na,nb)>=b.min_support and item['total_variation']>=b.distribution_effect
        item['below_support_descriptive_only']=min(na,nb)<b.min_support
        details.append(item)
    return details,False


def sequence(e,r,measurement,wins):
    con=e.work.con;s=r.temporal;table=r.cells+'_sequence_'+str(len(e.records));escaped="'"+measurement.name.replace("'","''")+"'"
    # Conflicting simultaneous measurements and unresolved clocks cannot establish a value path.
    identity='observation_key,' if s.observation=='event' else ''
    con.execute(f'''CREATE TABLE {table}_points AS SELECT entity,measurement,{identity}t,min(_row) _row,count(DISTINCT list_value(value,value_state)) states,min(value) AS value,min(num) num,min(value_state) value_state,sum(multiplicity) multiplicity FROM {r.unique} WHERE measurement={escaped} GROUP BY ALL''')
    if s.observation=='event':
        con.execute(f'ALTER TABLE {table}_points ADD COLUMN simultaneous BIGINT')
        con.execute(f'UPDATE {table}_points SET simultaneous=x.n FROM (SELECT entity,t,count(*) n FROM {table}_points GROUP BY entity,t) x WHERE {table}_points.entity=x.entity AND {table}_points.t=x.t')
    maxgap=int(s.max_adjacency_ns) if s.max_adjacency_ns else None
    continuity='true';proven=s.schedule.kind!='none' or maxgap is not None
    if getattr(r,'grid',{}).get('kind')=='fixed':continuity=f't-previous_t={r.grid["cadence"]}'
    elif getattr(r,'grid',{}).get('kind')=='civil':
        grid=r.grid['table'];con.execute(f'ALTER TABLE {table}_points ADD COLUMN slot HUGEINT');con.execute(f'UPDATE {table}_points SET slot=g.slot FROM {grid} g WHERE {table}_points.t=g.t');continuity='slot=previous_slot+1'
    elif getattr(r,'grid',{}).get('kind')=='supplied':
        grid=r.grid['table'];seq=table+'_grid';con.execute(f'CREATE TABLE {seq} AS SELECT *,row_number() OVER(PARTITION BY entity,measurement ORDER BY t) slot FROM {grid}')
        con.execute(f'ALTER TABLE {table}_points ADD COLUMN slot HUGEINT');con.execute(f'UPDATE {table}_points SET slot=g.slot FROM {seq} g WHERE {table}_points.t=g.t AND {table}_points.entity=g.entity AND {table}_points.measurement=g.measurement');continuity='slot=previous_slot+1'
    if maxgap is not None:continuity=f'({continuity}) AND t-previous_t<={maxgap}'
    slot='slot' if r.temporal.schedule.kind in {'civil','supplied'} and hasattr(r,'grid') else 'NULL::HUGEINT'
    simult='simultaneous' if s.observation=='event' else '1'
    con.execute(f'''CREATE TABLE {table}_lag AS SELECT *,lag({simult}) OVER q previous_simultaneous,lag(t) OVER q previous_t,lag(value) OVER q previous_value,lag(num) OVER q previous_num,lag(value_state) OVER q previous_state,lag(states) OVER q previous_states,lag({slot}) OVER q previous_slot FROM {table}_points WINDOW q AS(PARTITION BY entity ORDER BY t,_row)''')
    same_lifecycle=f"EXISTS(SELECT 1 FROM {r.active} a WHERE a.entity=x.entity AND a.measurement=x.measurement AND a.start_t<=x.previous_t AND a.end_t>x.t)" if s.active_intervals else 'true'
    taint=f"EXISTS(SELECT 1 FROM {r.cells} bad WHERE bad.entity=x.entity AND bad.measurement=x.measurement AND bad.time_state!='valid')"
    eligible=f"{simult}=1 AND previous_simultaneous=1 AND states=1 AND previous_states=1 AND t>previous_t AND ({continuity}) AND ({same_lifecycle}) AND NOT ({taint})"
    rate=e.config.behavior.rate_differences
    difference='num-previous_num'
    rate_block=rate and (s.clock.kind!='instant' or not maxgap)
    if rate and not rate_block:difference='(num-previous_num)/(CAST(t-previous_t AS DOUBLE)/1000000000)'
    con.execute(f'''CREATE TABLE {table} AS SELECT x.*,({eligible}) adjacent,
        CASE WHEN {eligible} AND value_state='valid' AND previous_state='valid' AND num IS NOT NULL AND previous_num IS NOT NULL THEN {difference} ELSE NULL END difference,
        w.window_id FROM {table}_lag x LEFT JOIN {wins} w ON t>=w.start_t AND t<w.end_t''')
    runs=table+'_runs';con.execute(f'''CREATE TABLE {runs} AS WITH x AS(SELECT *,sum(CASE WHEN adjacent AND value_state='valid' AND previous_state='valid' AND value=previous_value OR adjacent AND value_state='missing' AND previous_state='missing' THEN 0 ELSE 1 END) OVER(PARTITION BY entity ORDER BY t,_row ROWS UNBOUNDED PRECEDING) run FROM {table}) SELECT entity,run,min(value) AS value,min(value_state) state,min(t) first_t,max(t) last_t,count(*) observations,min(states) min_states,max(states) max_states FROM x GROUP BY entity,run''')
    valid,vary=con.execute(f"SELECT count(*) FILTER(WHERE value_state='valid' AND states=1),count(DISTINCT value) FILTER(WHERE value_state='valid' AND states=1) FROM {table}").fetchone()
    candidates=con.execute(f"SELECT count(*),coalesce(sum(observations),0),max(observations) FROM {runs} WHERE state='valid' AND min_states=1 AND max_states=1 AND observations>=?",[e.config.behavior.flatline_observations]).fetchone()
    missing=con.execute(f"SELECT count(*),max(observations) FROM {runs} WHERE state='missing'").fetchone()
    ident=e.add('runs',r.id,{'measurement':measurement.name,'exact_repetition_runs':candidates[0],'participating_observations':int(candidates[1]),'longest_repetition':candidates[2],'missing_state_runs':missing[0],'longest_missing_state_run':missing[1],'continuity_established':proven,'valid_observations':valid,'distinct_valid_values':vary,'candidate_threshold':e.config.behavior.flatline_observations,'scope':'consecutive observations' if not proven else 'declared adjacency','globally_constant_descriptive':vary<=1},measurement=measurement.name,witnesses=e.witnesses(f'SELECT entity,CAST(first_t AS VARCHAR) first_tick,CAST(last_t AS VARCHAR) last_tick,observations,state FROM {runs} ORDER BY observations DESC,entity,first_t'))
    supported_candidates=con.execute(f"SELECT count(*) FROM {runs} x JOIN (SELECT entity,count(*) FILTER(WHERE value_state='valid' AND states=1) n,count(DISTINCT value) FILTER(WHERE value_state='valid' AND states=1) d FROM {table} GROUP BY entity) y USING(entity) WHERE x.state='valid' AND x.min_states=1 AND x.max_states=1 AND x.observations>=? AND y.n>=? AND y.d>1",[e.config.behavior.flatline_observations,e.config.behavior.min_support]).fetchone()[0]
    if proven and measurement.representation=='quantitative' and supported_candidates:e.finding(ident,'Contiguous equal-value runs merit investigation',detail='Configured candidate threshold met. Legitimate plateaus, zeros, and operating regimes remain plausible.')
    if measurement.representation!='quantitative':return
    if rate_block:e.add('volatility',r.id,{'measurement':measurement.name},measurement=measurement.name,blocked='Rate differences require resolved instants and an explicit maximum adjacency gap.');return
    # Each difference belongs only to windows containing both endpoints.
    con.execute(f'UPDATE {table} SET difference=NULL WHERE difference IS NOT NULL AND NOT isfinite(difference)')
    con.execute(f'''UPDATE {table} SET difference=NULL WHERE NOT EXISTS(SELECT 1 FROM {wins} w WHERE w.window_id={table}.window_id AND {table}.previous_t>=w.start_t AND {table}.previous_t<w.end_t)''')
    summaries=[]
    for i in range(len(e.query(f'SELECT * FROM {wins}').fetchall())):
        n=con.execute(f'SELECT count(difference) FROM {table} WHERE window_id=?',[i]).fetchone()[0];q=quantiles(con,table,'difference',f'window_id={i} AND difference IS NOT NULL AND isfinite(difference)') if n else None
        summaries.append({'window_id':i,'differences':n,'dispersion':q[4]-q[2] if q and math.isfinite(q[4]-q[2]) else None})
    ref=summaries[e.config.behavior.reference_window] if summaries else None;comparisons=[]
    if ref:
        for x in summaries:
            d=ref['dispersion'];ratio=x['dispersion']/d if d is not None and d>0 and x['dispersion'] is not None and math.isfinite(x['dispersion']/d) else None
            comparisons.append({**x,'reference_window':ref['window_id'],'ratio':ratio,'review':ratio is not None and min(x['differences'],ref['differences'])>=e.config.behavior.volatility_support and (ratio>=e.config.behavior.volatility_ratio or ratio<=1/e.config.behavior.volatility_ratio),'block':None if ratio is not None else 'zero_or_unsafe_reference_dispersion'})
    ident=e.add('volatility',r.id,{'measurement':measurement.name,'definition':'IQR of eligible consecutive '+('elapsed-rate ' if rate else '')+'differences','windows':comparisons,'continuity_established':proven},measurement=measurement.name)
    if any(x['review'] for x in comparisons):e.finding(ident,'Consecutive-difference dispersion changed',detail='Configured support and ratio settings met; this does not establish a sensor defect or performance change.')


def seasonality(e,r,measurement,table,endpoints,declaration):
    b=e.config.behavior;con=e.work.con;phase=table+'_phase_'+str(len(e.records));escaped="'"+measurement.name.replace("'","''")+"'"
    if declaration.kind=='elapsed' and r.temporal.clock.kind!='instant' or declaration.civil_phase=='hour' and r.temporal.clock.kind=='civil_date':e.add('seasonality',r.id,{},measurement=measurement.name,blocked='Elapsed phases need resolved instants; civil-hour phases need intraday labels.');return
    n=con.execute(f'SELECT count(*) FROM {table} WHERE measurement={escaped}').fetchone()[0]
    if not e.reserve(n*2):e.add('seasonality',r.id,{'unsearched_scope':'Phase assignment exceeds declared observation visits.'},measurement=measurement.name);return
    con.execute(f'CREATE TABLE {phase} AS SELECT *,NULL::INTEGER phase,NULL::VARCHAR AS cycle FROM {table} WHERE measurement={escaped}')
    assign_phase(e,r,phase,declaration)
    support=[{'window_id':w,'phase':p,'observations':n,'eligible':eligible,'cycles':c} for w,p,n,eligible,c in con.execute(f"SELECT window_id,phase,count(*),count(*) FILTER(WHERE value_state='valid' AND (num IS NOT NULL OR ?)),count(DISTINCT cycle) FILTER(WHERE value_state='valid' AND (num IS NOT NULL OR ?)) FROM {phase} GROUP BY ALL ORDER BY ALL",[measurement.representation!='quantitative']*2).fetchall()]
    cycles=con.execute(f'SELECT count(DISTINCT cycle) FROM {phase}').fetchone()[0];ref=b.reference_window;effects=[]
    for current in range(len(endpoints)):
        if current==ref:continue
        supported=[p for p in {x['phase'] for x in support} if all(any(x['window_id']==w and x['phase']==p and x['eligible']>=b.min_phase_support and x['cycles']>=b.min_window_cycles for x in support) for w in (ref,current))]
        nref=con.execute(f'SELECT count(*) FROM {phase} WHERE window_id=?',[ref]).fetchone()[0];ncur=con.execute(f'SELECT count(*) FROM {phase} WHERE window_id=?',[current]).fetchone()[0]
        refincluded=sum(x['eligible'] for x in support if x['window_id']==ref and x['phase'] in supported);curincluded=sum(x['eligible'] for x in support if x['window_id']==current and x['phase'] in supported)
        item={'reference_window':ref,'comparison_window':current,'common_supported_phases':supported,'excluded_reference_mass':(nref-refincluded)/nref if nref else None,'excluded_comparison_mass':(ncur-curincluded)/ncur if ncur else None,'phase_effects':[],'phase_matched_cdf':None,'phase_matched_w1':None,'phase_matched_tv':None,'full_seasonal_explanation_claimed':False}
        if cycles<b.min_cycles or not supported:item['block']='insufficient_cycles_or_common_phase_support';effects.append(item);continue
        weighted=0.;weighted_w=0.;valid=0
        for p in supported:
            left=f'window_id={ref} AND phase={p} AND value_state=\'valid\'';right=f'window_id={current} AND phase={p} AND value_state=\'valid\''
            nl=con.execute(f'SELECT count(*) FROM {phase} WHERE {left}').fetchone()[0];nr=con.execute(f'SELECT count(*) FROM {phase} WHERE {right}').fetchone()[0]
            if not nl or not nr:continue
            if not e.reserve(nl+nr,1):item['block']='declared_work_bound';break
            weight=next(x['eligible'] for x in support if x['window_id']==ref and x['phase']==p)/refincluded
            if measurement.representation=='quantitative':
                if con.execute(f'SELECT count(*) FROM {phase} WHERE ({left} OR {right}) AND num IS NULL').fetchone()[0]:continue
                block=numeric_geometry(con,phase,'num',left) or numeric_geometry(con,phase,'num',right)
                if block:item['block']=block;break
                distance,w1,_=numeric_effect(con,phase,'num',left,phase,'num',right,nl,nr,constant_zero=True)
                if w1 is None or not math.isfinite(w1):item['block']='statistic_overflow';break
                weighted+=weight*distance;weighted_w+=weight*w1
                item['phase_effects'].append({'phase':p,'reference_weight':weight,'cdf':distance,'w1':w1})
            else:
                effect=categorical_effect(con,phase,'value',left,phase,'value',right,nl,nr);weighted+=weight*effect['total_variation'];item['phase_effects'].append({'phase':p,'reference_weight':weight,**effect})
            valid+=1
        if valid==len(supported) and not item.get('block'):
            item['phase_matched_cdf' if measurement.representation=='quantitative' else 'phase_matched_tv']=weighted
            if measurement.representation=='quantitative':item['phase_matched_w1']=weighted_w
        effects.append(item)
    expected_support,expected_block=expected_phase_support(e,r,declaration,endpoints)
    e.add('seasonality',r.id,{'unsearched_phase_comparisons':sum(x.get('block')=='declared_work_bound' for x in effects),'unsearched_expected_phase_scope':expected_block if expected_block and ('budget' in expected_block or 'unsearched' in expected_block) else None,'expected_phase_opportunities':expected_support,'expected_phase_block':expected_block,'effect_definition':'Reference-weighted average of supported phasewise empirical effects; not the distance of pooled mixtures or proof of a seasonal explanation.','declaration':asdict(declaration),'phase_clock_meaning':'Resolved instants mapped to declared timezone' if r.temporal.clock.kind=='instant' else 'Source civil labels; no elapsed-time or cross-zone guarantee','overall_cycles':cycles,'phase_support':support,'comparisons':effects,'expected_opportunities_available':hasattr(r,'expected'),'population':'common supported phases weighted by the explicitly identified reference window_id'},measurement=measurement.name)


def behavior(e,r):
    b=e.config.behavior
    if not b.enabled:e.add('behavior',r.id,{'unsearched_scope':'Behavior disabled by declaration.'});return
    con=e.work.con;phase=getattr(e,'behavior_phase','complete');requested=getattr(r,'requested_behavior_names',set())
    if phase=='requested' and not requested:return
    if not hasattr(r,'behavior_windows'):r.behavior_windows=windows(e,r)
    wins,endpoints=r.behavior_windows
    if not endpoints:e.add('behavior',r.id,{},blocked='No usable chronology for window_id investigation.');return
    selected=[m for name in b.requested_measurements for m in r.temporal.measurements if name==m.name]
    selected += [m for m in r.temporal.measurements if m not in selected]
    selected=getattr(r,'behavior_measurements',selected[:e.config.limits.behavior_measurements])
    all_selected=selected
    selected=[m for m in selected if (m.name in requested)==(phase=='requested')] if phase!='complete' else selected
    if not all_selected:
        e.add('behavior_scope',r.id,{'selected_measurements':[],'unsearched_scope':[m.name for m in r.temporal.measurements],'reason':'Job-level declared measurement-search bound.'});return
    table=r.cells+'_window_cells'
    if not hasattr(r,'behavior_cell_table'):con.execute(f"CREATE TABLE {table} AS SELECT x.*,w.window_id FROM {r.cells} x JOIN {wins} w ON x.t>=w.start_t AND x.t<w.end_t WHERE time_state='valid' AND x.measurement IN(SELECT unnest(?::VARCHAR[]))",[[m.name for m in all_selected]])
    r.behavior_cell_table=table
    pairs=list(dict.fromkeys([(i-1,i) for i in range(1,len(endpoints))]+[(b.reference_window,i) for i in range(len(endpoints)) if i!=b.reference_window]))
    from datatrust.temporal_multivariate import annotation_windows,multivariate
    if phase!='remaining':
        with e.optional('multivariate',r.id,relation=r):multivariate(e,r,table,wins)
    if phase=='requested':detailed_series(e,r,table,wins,pairs,requested_only=True)
    unsearched=[m.name for m in r.temporal.measurements if m not in all_selected] if phase!='requested' else []
    for m in selected:
        cells=con.execute(f'SELECT count(*) FROM {table} WHERE measurement=?',[m.name]).fetchone()[0]
        if not e.reserve(cells*2):unsearched.append(m.name);continue
        summaries=window_summary(e,r,table,wins,m.name)
        effects,bounded=compare_windows(e,r,table,m,summaries,pairs)
        ident=e.add('behavior_windows',r.id,{'measurement':m.name,'unit':m.unit,'windows':summaries,'comparisons':effects,'reference_window':b.reference_window,'reference_was_replaced':False,'investigation_defaults':asdict(b),'comparison_search_bounded':bounded,'empty_denominators_are_unavailable':True,'interpretation':'Observed effects are descriptive investigation evidence, not validated universal defects, changepoints, concept drift, or model performance.'},measurement=m.name)
        if any(x.get('missingness_review') or x.get('distribution_review') for x in effects):e.finding(ident,'Window effects meet configured investigation settings',detail='Review reference support, dispersion, seasonality, and entity composition before interpreting the change.')
        if bounded:unsearched.append(m.name+':remaining comparisons')
        # Population mix and stable-cohort behavior remain distinct.
        cohort=table+'_cohort_'+str(len(e.records));con.execute(f'''CREATE TABLE {cohort} AS SELECT entity FROM {table} WHERE measurement=? AND entity_ok GROUP BY entity HAVING count(DISTINCT window_id)=?''',[m.name,len(endpoints)])
        cohorts=con.execute(f'SELECT count(*) FROM {cohort}').fetchone()[0]
        mix=[];mix_unsearched=[]
        for left,right in pairs:
            nl=con.execute(f'SELECT count(*) FROM {table} WHERE window_id=? AND measurement=? AND entity_ok',[left,m.name]).fetchone()[0];nr=con.execute(f'SELECT count(*) FROM {table} WHERE window_id=? AND measurement=? AND entity_ok',[right,m.name]).fetchone()[0]
            if nl and nr and not e.reserve(nl+nr,1):mix_unsearched.append([left,right]);continue
            if nl and nr:mix.append({'reference_window':left,'comparison_window':right,**categorical_effect(con,table,'entity',f"window_id={left} AND measurement='{m.name.replace(chr(39),chr(39)*2)}' AND entity_ok",table,'entity',f"window_id={right} AND measurement='{m.name.replace(chr(39),chr(39)*2)}' AND entity_ok",nl,nr)})
        stable=[];stable_unsearched=False
        if b.stable_cohort and cohorts:
            stable_unsearched=not e.reserve(cells*2)
        if b.stable_cohort and cohorts and not stable_unsearched:
            cs=window_summary(e,r,table,wins,m.name,cohort);stable,_=compare_windows(e,r,table,m,cs,pairs,cohort=cohort)
            stable_unsearched=stable_unsearched or _
        e.add('behavior_panel',r.id,{'measurement':m.name,'population_mix':mix,'unsearched_population_mix_pairs':mix_unsearched,'unsearched_stable_cohort':stable_unsearched,'stable_entities':cohorts,'stable_cohort_effects':stable,'qualification':'Stable cohort conditions on survival across every declared window_id; it can omit entrants, exits and behavior-only problems. Pooled stable-cohort effects are not per-entity causal effects.'},measurement=m.name)
        if e.reserve(cells*4):
            with e.optional('runs_and_volatility',r.id,relation=r):sequence(e,r,m,wins)
        else:e.add('runs_and_volatility',r.id,{'unsearched_scope':'Run/volatility work exceeds declared observation visits.'},measurement=m.name)
        for declaration in b.seasonality:
            if declaration.source_id==r.id and declaration.measurement==m.name:
                with e.optional('seasonality',r.id,relation=r):seasonality(e,r,m,table,endpoints,declaration)
        e.work.check(r.id+': bounded behavioral investigation')
    if phase!='requested':
        with e.optional('annotation_windows',r.id,relation=r):annotation_windows(e,r,wins)
        detailed_series(e,r,table,wins,pairs,automatic_only=phase=='remaining')
    e.add('behavior_scope',r.id,{'selected_measurements':[m.name for m in selected],'unsearched_scope':unsearched,'work_observation_visits':e.visits,'comparisons':e.comparisons,'selection':'Requested measurements first, then declaration order. Detail retention can miss behavior-only exceptions.','defaults_validated_universal_defect_criteria':False})


def detailed_series(e,r,table,wins,pairs,requested_only=False,automatic_only=False):
    """Grouped per-series effects: a bounded relation, rather than one query per entity."""
    import json
    con=e.work.con;b=e.config.behavior
    if not hasattr(e,'series_sources_done'):e.series_sources_done=set()
    reserved=sum(x.source_id!=r.id and x.source_id not in e.series_sources_done for x in b.requested_series)
    limit=max(0,e.config.limits.detailed_series-e.detailed_series-reserved)
    requested=[] if automatic_only else [x for x in b.requested_series if x.source_id==r.id]
    if requested_only and not requested:return
    e.series_sources_done.add(r.id)
    if not limit and not requested:return
    chosen=table+'_detailed_series_'+('requested' if requested_only else 'remaining' if automatic_only else 'complete');con.execute(f'CREATE TABLE {chosen}(entity VARCHAR,measurement VARCHAR,selection VARCHAR)')
    for x in requested:
        entity=json.dumps(list(x.entity),ensure_ascii=False,separators=(',',':'))
        con.execute(f'INSERT INTO {chosen} VALUES (?,?,?)',[entity,x.measurement,'explicit request'])
    if requested_only:r.requested_series_table=chosen
    previous=getattr(r,'requested_series_table',None) if automatic_only else None
    excluded=f' AND NOT EXISTS(SELECT 1 FROM {previous} p WHERE p.entity=x.entity AND p.measurement=x.measurement)' if previous else ''
    remain=0 if requested_only else limit-len(requested)
    if remain>0:con.execute(f'''INSERT INTO {chosen} SELECT entity,measurement,'coverage concerns, support, canonical identity' FROM {table} x WHERE entity_ok AND NOT EXISTS(SELECT 1 FROM {chosen} c WHERE c.entity=x.entity AND c.measurement=x.measurement){excluded} GROUP BY entity,measurement ORDER BY count(DISTINCT window_id),count(*) DESC,entity,measurement LIMIT {remain}''')
    count=con.execute(f'SELECT count(*) FROM {chosen}').fetchone()[0];e.detailed_series+=count
    if not count:return
    narrow=chosen+'_cells';con.execute(f'CREATE TABLE {narrow} AS SELECT x.entity,x.measurement,x.window_id,x.num,x.value,x.value_state FROM {table} x JOIN {chosen} c USING(entity,measurement)')
    visits=con.execute(f'SELECT count(*) FROM {narrow}').fetchone()[0]
    allowed=min(len(pairs),max(0,(e.config.limits.max_comparisons-e.comparisons)//max(1,count)))
    allowed=min(allowed,max(0,(e.config.limits.observation_visits-e.visits)//max(1,visits*2)))
    if not allowed:e.add('behavior_series',r.id,{'selected_series':count,'unsearched_scope':'Per-series comparisons exceeded declared work budget.'});return
    selected_pairs=pairs[:allowed];e.reserve(visits*2*allowed,count*allowed)
    comparisons=chosen+'_pairs';con.execute(f'CREATE TABLE {comparisons}(a INTEGER,b INTEGER)');con.executemany(f'INSERT INTO {comparisons} VALUES (?,?)',selected_pairs)
    # Window support and exact order-statistic interpolation over bounded selected series.
    support=chosen+'_support';con.execute(f'''CREATE TABLE {support} AS SELECT c.entity,c.measurement,w.window_id,count(x.window_id) n,count(x.window_id) FILTER(WHERE x.value_state='missing') missing,count(x.num) finite,count(x.window_id) FILTER(WHERE x.value_state='valid') AS valid_count,min(x.num) lo,max(x.num) hi,count(x.window_id) FILTER(WHERE x.value_state='valid' AND x.num IS NULL) unsafe FROM {chosen} c CROSS JOIN {wins} w LEFT JOIN {narrow} x ON c.entity=x.entity AND c.measurement=x.measurement AND w.window_id=x.window_id GROUP BY ALL''')
    ranks=chosen+'_ranks';con.execute(f'''CREATE TABLE {ranks} AS SELECT *,row_number() OVER(PARTITION BY entity,measurement,window_id ORDER BY num) rank,count(*) OVER(PARTITION BY entity,measurement,window_id) n FROM {narrow} WHERE num IS NOT NULL''')
    iqrs=chosen+'_iqr';con.execute(f'''CREATE TABLE {iqrs} AS WITH q AS(SELECT entity,measurement,window_id,p,
        max(num) FILTER(WHERE rank=floor((n-1)*p)+1) lo,max(num) FILTER(WHERE rank=ceil((n-1)*p)+1) hi,max((n-1)*p-floor((n-1)*p)) fraction
        FROM {ranks} CROSS JOIN (SELECT unnest([.25,.75]) p) p GROUP BY ALL), v AS(SELECT *,lo*(1-fraction)+hi*fraction AS value FROM q)
        SELECT entity,measurement,window_id,max(value) FILTER(WHERE p=.75)-max(value) FILTER(WHERE p=.25) iqr FROM v GROUP BY ALL''')
    frequencies=chosen+'_freq';con.execute(f'''CREATE TABLE {frequencies} AS SELECT entity,measurement,window_id,num,count(*) n FROM {narrow} WHERE num IS NOT NULL GROUP BY ALL''')
    numeric=chosen+'_numeric';con.execute(f'''CREATE TABLE {numeric} AS WITH f AS(SELECT entity,measurement,a,b,num datum,n,0::BIGINT m FROM {frequencies} f JOIN {comparisons} p ON f.window_id=p.a UNION ALL SELECT entity,measurement,a,b,num,0::BIGINT,n FROM {frequencies} f JOIN {comparisons} p ON f.window_id=p.b),u AS(SELECT entity,measurement,a,b,datum,sum(n) n,sum(m) m FROM f GROUP BY ALL),cdf AS(SELECT *,sum(n) OVER q/sum(n) OVER g fa,sum(m) OVER q/sum(m) OVER g fb,lead(datum) OVER q next_datum,coalesce(nullif(max(abs(datum)) OVER g,0),1) scale FROM u WINDOW q AS(PARTITION BY entity,measurement,a,b ORDER BY datum ROWS UNBOUNDED PRECEDING),g AS(PARTITION BY entity,measurement,a,b)) SELECT entity,measurement,a,b,max(abs(fa-fb)) cdf,sum(abs(fa-fb)*(CASE WHEN sign(next_datum)=sign(datum) THEN (next_datum-datum)/scale ELSE next_datum/scale-datum/scale END))*max(scale) w1 FROM cdf GROUP BY ALL''')
    categories=chosen+'_categories';con.execute(f'''CREATE TABLE {categories} AS WITH f AS(SELECT entity,measurement,a,b,value datum,count(*) n,0::BIGINT m FROM {narrow} x JOIN {comparisons} p ON x.window_id=p.a WHERE value_state='valid' GROUP BY ALL UNION ALL SELECT entity,measurement,a,b,value,0::BIGINT,count(*) FROM {narrow} x JOIN {comparisons} p ON x.window_id=p.b WHERE value_state='valid' GROUP BY ALL),u AS(SELECT entity,measurement,a,b,datum,sum(n) n,sum(m) m FROM f GROUP BY ALL),s AS(SELECT *,sum(n) OVER(PARTITION BY entity,measurement,a,b) na,sum(m) OVER(PARTITION BY entity,measurement,a,b) nb FROM u) SELECT entity,measurement,a,b,.5*sum(abs(n/nullif(na,0)-m/nullif(nb,0))) tv FROM s GROUP BY ALL''')
    sql=f'''SELECT c.entity,c.measurement,p.a,p.b,x.n,y.n,x.missing,y.missing,x.finite,y.finite,x.valid_count,y.valid_count,x.lo,x.hi,y.lo,y.hi,x.unsafe+y.unsafe unsafe,q.iqr,z.cdf,z.w1,v.tv,c.selection FROM {chosen} c CROSS JOIN {comparisons} p JOIN {support} x ON x.entity=c.entity AND x.measurement=c.measurement AND x.window_id=p.a JOIN {support} y ON y.entity=c.entity AND y.measurement=c.measurement AND y.window_id=p.b LEFT JOIN {iqrs} q ON q.entity=c.entity AND q.measurement=c.measurement AND q.window_id=p.a LEFT JOIN {numeric} z ON z.entity=c.entity AND z.measurement=c.measurement AND z.a=p.a AND z.b=p.b LEFT JOIN {categories} v ON v.entity=c.entity AND v.measurement=c.measurement AND v.a=p.a AND v.b=p.b ORDER BY (c.selection='explicit request') DESC,c.entity,c.measurement,p.a,p.b'''
    details=[];candidates=0;total=count*allowed
    measurements={m.name:m for m in r.temporal.measurements}
    cursor=con.execute(sql)
    for row in cursor.fetchall():
        entity,m,a,current,na,nb,ma,mb,fa,fb,va,vb,lo,hi,ly,hy,unsafe,iqr,cdf,w1,tv,selection=row
        geometry=any(low is not None and high is not None and low!=high and high-low<=128*max(math.ulp(low),math.ulp(high)) for low,high in ((lo,hi),(ly,hy)))
        unsafe=unsafe or geometry
        overflow=w1 is not None and not math.isfinite(w1)
        if overflow:w1=None
        if cdf is not None and not math.isfinite(cdf):cdf=None
        if iqr is not None and not math.isfinite(iqr):iqr=None
        quantitative=measurements[m].representation=='quantitative';change=mb/nb-ma/na if na and nb else None;normal=w1/iqr if w1 is not None and iqr is not None and iqr>0 and math.isfinite(w1/iqr) else None
        review=bool(min(na,nb)>=b.min_support and change is not None and change>=b.missingness_increase or quantitative and not unsafe and min(fa,fb)>=b.min_support and (cdf is not None and cdf>=b.distribution_effect or normal is not None and normal>=b.normalized_w1) or not quantitative and min(va,vb)>=b.min_support and tv is not None and tv>=b.distribution_effect)
        candidates+=review
        if len(details)<e.config.limits.retained_details:details.append({'entity':json.loads(entity),'measurement':m,'reference_window':a,'comparison_window':current,'reference_cells':na,'comparison_cells':nb,'missingness_change':change,'cdf':cdf if quantitative and not unsafe else None,'w1':w1 if quantitative and not unsafe else None,'reference_iqr':iqr if quantitative else None,'normalized_w1':normal if quantitative and not unsafe else None,'tv':tv if not quantitative else None,'investigation_candidate':review,'selection':selection,'unsafe_numeric_comparison':bool(unsafe) if quantitative else False,'wasserstein_block':'statistic_overflow' if quantitative and overflow else None,'normalization_block':'zero_or_unsafe_reference_iqr' if quantitative and normal is None else None})
    ident=e.add('behavior_series',r.id,{'selected_series':count,'compared_series_windows':total,'investigation_candidates':candidates,'details':details,'retention_omissions':max(0,total-len(details)),'unsearched_window_pairs':len(pairs)-allowed,'selection_bias':'Requested scope first; other series chosen by coverage concerns/support/canonical identity. Other behavior-only issues may be missed.'})
    e.omissions[r.id+':series_effects']=max(0,total-len(details))
    if candidates:e.finding(ident,'Within-series window effects merit investigation',detail='Configured investigation settings met in selected series. Aggregate population mix is reported separately.')


def assign_phase(e,r,phase,declaration):
    con=e.work.con
    if declaration.kind=='elapsed':
        period=int(declaration.period_ns);anchor=literal_tick(declaration.anchor,r.temporal.clock)
        from datatrust.temporal_diagnostics import floor_sql
        con.execute(f'UPDATE {phase} SET phase=CAST(((t-({anchor}))%{period}+{period})%{period}*{declaration.phases}//{period} AS INTEGER),cycle=CAST({floor_sql(f"t-({anchor})",str(period))} AS VARCHAR)')
    else:
        z=zone(declaration.timezone);cursor=con.cursor();cursor.execute(f'SELECT _row,t FROM {phase} ORDER BY _row')
        try:
            while True:
                rows=cursor.fetchmany(4096)
                if not rows:break
                updates=[]
                for ordinal,tick in rows:
                    dt=EPOCH+timedelta(days=tick) if r.temporal.clock.kind=='civil_date' else EPOCH+timedelta(microseconds=tick//1000)
                    if r.temporal.clock.kind=='instant':dt=dt.replace(tzinfo=timezone.utc).astimezone(z)
                    ph=dt.hour if declaration.civil_phase=='hour' else dt.weekday() if declaration.civil_phase=='weekday' else dt.month-1
                    cycle=dt.date().isoformat() if declaration.civil_phase=='hour' else str(dt.isocalendar()[:2]) if declaration.civil_phase=='weekday' else str(dt.year)
                    updates.append((ordinal,ph,cycle))
                frame=pd.DataFrame(updates,columns=['_row','phase','cycle']);con.register('_phase_batch',frame)
                try:con.execute(f'UPDATE {phase} SET phase=b.phase,cycle=b.cycle FROM _phase_batch b WHERE {phase}._row=b._row')
                finally:con.unregister('_phase_batch')
        finally:cursor.close()


def expected_phase_support(e,r,declaration,endpoints):
    """Expected phase counts from arithmetic or existing calendars; never expand fixed gaps."""
    con=e.work.con
    if not hasattr(r,'expected'):return [],'No declared expected observation population.'
    if getattr(r,'grid',{}).get('kind')=='fixed':
        if declaration.kind!='elapsed':return [],'Civil-phase expectation for a fixed elapsed grid remains unsearched; no implicit DST mapping.'
        period=int(declaration.period_ns);cadence=r.grid['cadence'];anchor=literal_tick(declaration.anchor,r.temporal.clock);shift=(r.grid['anchor']-anchor)%period
        if period%cadence or shift%cadence:return [],'Noncommensurate phase-grid counting exceeds this arithmetic method; expectation phase scope remains unanswered.'
        cycle=period//cadence;offset=shift//cadence;result=[]
        from datatrust.temporal_diagnostics import ceil_sql,floor_sql
        def prefix(x,low,high):
            whole=floor_sql(x,str(cycle));rem=f'(({x})-({whole})*{cycle})'
            return f'({whole})*{high-low}+greatest(0,least({high-low},{rem}-{low}))'
        for w,(lo,hi) in enumerate(endpoints):
            first=ceil_sql(f'greatest(start_t,{lo})-({r.grid["anchor"]})',str(cadence));end=ceil_sql(f'least(end_t,{hi})-({r.grid["anchor"]})',str(cadence))
            for phase in range(declaration.phases):
                low=(cycle*phase+declaration.phases-1)//declaration.phases;high=(cycle*(phase+1)+declaration.phases-1)//declaration.phases
                n=con.execute(f'SELECT coalesce(sum(({prefix(f"({end})+{offset}",low,high)})-({prefix(f"({first})+{offset}",low,high)})),0) FROM {r.active} WHERE measurement=? AND start_t<? AND end_t>?',[declaration.measurement,hi,lo]).fetchone()[0]
                result.append({'window_id':w,'phase':phase,'expected_opportunities':int(n)})
        return result,None
    base=r.cells+'_expected_phase_'+str(len(e.records));wins=r.cells+'_windows'
    if r.grid['kind']=='supplied':
        n=con.execute(f'SELECT count(*) FROM {r.expected} WHERE measurement=?',[declaration.measurement]).fetchone()[0]
        if not e.reserve(n*2):return [],'Expected phase search stopped at the declared observation-visit budget.'
        con.execute(f'''CREATE TABLE {base} AS SELECT row_number() OVER() _row,x.t,w.window_id,NULL::INTEGER phase,NULL::VARCHAR AS cycle FROM {r.expected} x JOIN {wins} w ON x.t>=w.start_t AND x.t<w.end_t WHERE measurement=?''',[declaration.measurement])
        assign_phase(e,r,base,declaration)
        return [{'window_id':w,'phase':p,'expected_opportunities':n} for w,p,n in con.execute(f'SELECT window_id,phase,count(*) FROM {base} GROUP BY ALL ORDER BY ALL').fetchall()],None
    # Calendar exists once globally. Count selected lifecycle ranges using phase prefixes.
    grid=r.grid['table'];n=con.execute(f'SELECT count(*) FROM {grid}').fetchone()[0]
    if not e.reserve(n*2):return [],'Calendar phase search stopped at the declared observation-visit budget.'
    con.execute(f'CREATE TABLE {base} AS SELECT slot _row,t,NULL::INTEGER phase,NULL::VARCHAR AS cycle FROM {grid}')
    assign_phase(e,r,base,declaration);result=[]
    for phase in [x[0] for x in con.execute(f'SELECT DISTINCT phase FROM {base}').fetchall()]:
        prefix_table=base+'_prefix_'+str(phase);con.execute(f'CREATE TABLE {prefix_table} AS SELECT t,count(*) OVER(ORDER BY t ROWS UNBOUNDED PRECEDING) n FROM {base} WHERE phase=?',[phase])
        for w,(lo,hi) in enumerate(endpoints):
            n=con.execute(f'''SELECT coalesce(sum(coalesce(g2.n,0)-coalesce(g1.n,0)),0) FROM (SELECT greatest(start_t,?) start_t,least(end_t,?) end_t FROM {r.active} WHERE measurement=? AND start_t<? AND end_t>?) a ASOF LEFT JOIN {prefix_table} g1 ON a.start_t>g1.t ASOF LEFT JOIN {prefix_table} g2 ON a.end_t>g2.t''',[lo,hi,declaration.measurement,hi,lo]).fetchone()[0]
            result.append({'window_id':w,'phase':phase,'expected_opportunities':int(n)})
    return result,None
