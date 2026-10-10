"""Feature-bound timing and exact-observation revision state audits."""
from dataclasses import asdict
import json
from datatrust.temporal_normalization import normalize_clock, literal_tick, key_sql


def effective_bindings(spec):
    active={(a.id,f):True for a in spec.availability for f in a.features}
    for a in spec.availability:
        if a.replaces:
            for f in a.features:active[(a.replaces,f)]=False
    return [(a,tuple(f for f in a.features if active[(a.id,f)])) for a in spec.availability]


def past_observation(e,r,features,cutoff_spec,cutoff):
    past=[m.name for m in r.temporal.measurements if m.name in features and m.past_observation]
    if not past:return
    if r.temporal.clock.kind!=cutoff_spec.kind:
        e.add('past_observation',r.id,{'bound_features':past},blocked='Observation and prediction clocks have incompatible granularity; no intraday past-observation assurance.');return
    bad=e.query(f"SELECT count(*) FROM {r.cells} x JOIN {cutoff} c USING(_row) WHERE x.measurement IN(SELECT unnest(?::VARCHAR[])) AND x.time_state='valid' AND c.state='valid' AND x.t>c.t",[past]).fetchone()[0]
    ident=e.add('past_observation',r.id,{'bound_features':past,'observation_after_prediction_cells':bad},requirement='past_observation')
    if bad:e.finding(ident,'Declared past-observation features have future observation times',kind='declared_violation')


def availability(e,spec,relations):
    con=e.work.con;known={r.id:set() for r in relations.values() if hasattr(r,'cells')};past_checked=set()
    for a,features in effective_bindings(spec):
        if not features:continue
        r=relations[a.source_id];cutoff=normalize_clock(e.work,r,a.cutoff);table=r.cells+'_availability_'+str(len(e.records))
        if a.method=='static':
            expression='c.t' if a.static=='available_at_prediction' else 'NULL::HUGEINT';join='';state="c.state" if a.static=='available_at_prediction' else "'unknown'"
        else:
            clock=normalize_clock(e.work,r,a.availability or a.source_clock);expression='v.t'+('+'+a.delay_ns if a.method=='delay' else '');join=f' JOIN {clock} v USING(_row)';state='v.state'
        con.execute(f'''CREATE TABLE {table} AS SELECT cells._row,cells.measurement,cells.value_state,c.t cutoff,c.state cutoff_state,{expression} available,CASE WHEN cells.cell_origin!='supplied' THEN 'unknown' ELSE {state} END availability_state
            FROM {r.cells} cells JOIN {cutoff} c USING(_row){join} WHERE cells.measurement IN(SELECT unnest(?::VARCHAR[]))''',[list(features)])
        summaries=[]
        for feature in features:
            known[r.id].add(feature)
            n,unresolved,late,rows,unknownvalue=con.execute(f'''SELECT count(*),count(*) FILTER(WHERE cutoff_state!='valid' OR availability_state!='valid'),count(*) FILTER(WHERE cutoff_state='valid' AND availability_state='valid' AND available>cutoff),count(DISTINCT _row) FILTER(WHERE cutoff_state='valid' AND availability_state='valid' AND available>cutoff),count(*) FILTER(WHERE value_state!='valid') FROM {table} WHERE measurement=?''',[feature]).fetchone()
            latest=con.execute(f"SELECT max(available) FROM {table} WHERE measurement=? AND availability_state='valid'",[feature]).fetchone()[0]
            summaries.append({'latest_supplied_availability_tick':str(latest) if latest is not None else None,'feature':feature,'feature_cells':n,'unresolved_cells':unresolved,'available_after_cutoff':late,'affected_row_union':rows,'missing_or_invalid_feature_cells':unknownvalue})
        union=con.execute(f"SELECT count(DISTINCT _row) FROM {table} WHERE cutoff_state='valid' AND availability_state='valid' AND available>cutoff").fetchone()[0]
        ident=e.add('availability',r.id,{'binding':asdict(a),'features':summaries,'affected_row_union':union,'evidence_kind':'measured_timestamp' if a.method=='timestamp' else 'declared_assumption','availability_is_production_consumption_proof':False},requirement=a.id,assumptions=[] if a.method=='timestamp' else [a.id],witnesses=e.witnesses(f"SELECT _row,measurement,CAST(cutoff AS VARCHAR) cutoff_tick,CAST(available AS VARCHAR) availability_tick FROM {table} WHERE cutoff_state='valid' AND availability_state='valid' AND available>cutoff ORDER BY _row,measurement"))
        if union:e.finding(ident,'Bound features become available after their cutoffs',kind='declared_violation',detail='Timing violates the declared use requirement; delay-based availability is conditional on the supplied delay.')
        # Past-observation restriction is independent of feature availability.
        past_observation(e,r,features,a.cutoff,cutoff)
        past_checked.update((r.id,f,a.cutoff) for f in features)
    for h in spec.histories:
        known[h.source_id].update(h.features)
        features=[f for f in h.features if (h.source_id,f,h.cutoff) not in past_checked]
        r=relations[h.source_id]
        if any(m.past_observation and m.name in features for m in r.temporal.measurements):
            past_observation(e,r,features,h.cutoff,normalize_clock(e.work,r,h.cutoff))
        past_checked.update((r.id,f,h.cutoff) for f in features)
    for source,features in known.items():
        undeclared=[m.name for m in relations[source].temporal.measurements if m.name not in features]
        e.add('availability_unknown',source,{'features':undeclared,'meaning':'Undeclared availability remains unknown; no timestamp inheritance.'},blocked='No availability evidence for listed features.' if undeclared else None)


def observation_key(work,r,keys,clock,alias):
    if clock is None:
        key,valid=key_sql(r,keys);return key,valid,''
    table=normalize_clock(work,r,clock);parts=[];valid=[f"{alias}.state='valid'"]
    for name in keys:
        if name==clock.column:parts.append(f'CAST({alias}.t AS VARCHAR)')
        else:
            col=r.col(name);parts.append(f'CAST({col} AS VARCHAR)');valid.append(col+' IS NOT NULL')
    return 'CAST(to_json(list_value('+','.join(parts)+')) AS VARCHAR)',' AND '.join(valid),f' JOIN {table} {alias} USING(_row)'


def histories(e,spec,relations):
    con=e.work.con
    for h in spec.histories:
        r=relations[h.source_id];hr=relations[h.history_source_id];e.work.check(h.id+': revision ordering and selection reservation',hr.rows*(128+len(h.features)*96)+r.rows*len(h.features)*96);available=normalize_clock(e.work,hr,h.availability);cutoff=normalize_clock(e.work,r,h.cutoff)
        sourcekey,sourceok,sourcejoin=observation_key(e.work,r,h.observation_keys,h.source_observation_clock,'source_obs');histkey,histok,histjoin=observation_key(e.work,hr,h.history_keys,h.history_observation_clock,'history_obs')
        raw=r.cells+'_hraw_'+str(len(e.records));selection=raw+'_selected'
        unassignable=con.execute(f'SELECT count(*) FROM {hr.table}{histjoin} WHERE NOT ({histok})').fetchone()[0]
        parts=[];params=[]
        state_expr="CASE "+' '.join(f'WHEN CAST({hr.col(h.state_column)} AS VARCHAR)=? THEN ?' for _ in h.state_values)+" ELSE 'unknown' END" if h.state_column else None
        for feature in h.features:
            col=hr.col(h.value_columns[feature]);val=f'CAST({col} AS VARCHAR)'
            state=state_expr or f"CASE WHEN {col} IS NULL THEN '{h.null_semantics}' ELSE 'valid' END"
            # A 'valid' marker cannot make a null value usable. Unknown states are never skipped.
            state=f"CASE WHEN ({state})='valid' AND {col} IS NULL THEN '{h.null_semantics}' ELSE ({state}) END" if h.state_column else state
            stateparams=[v for pair in h.state_values.items() for v in pair]
            tie=f'CAST({hr.col(h.tie_order_column)} AS VARCHAR)' if h.tie_order_column else 'NULL::VARCHAR'
            rev=f'CAST({hr.col(h.revision_id_column)} AS VARCHAR)' if h.revision_id_column else 'NULL::VARCHAR'
            parts.append(f'SELECT _row,{histkey} obskey,{histok} key_ok,? measurement,clock.t available,clock.state time_state,{val} AS value,{state} revision_state,{tie} tie_order,{rev} revision_id FROM {hr.table} JOIN {available} clock USING(_row){histjoin}')
            params.append(feature)
            if h.state_column:params+=stateparams*2
        con.execute(f'CREATE TABLE {raw} AS '+' UNION ALL '.join(parts),params)
        # Retractions/known-missing states ignore payload values; invalid numerical values retain unknown state.
        con.execute(f"UPDATE {raw} SET value=NULL WHERE revision_state IN('known_missing','retracted')")
        ties=raw+'_ties';eligible=raw+'_eligible'
        if h.tie_order_column:
            # Identical semantic duplicates may collapse; conflicting duplicate ordinals cannot resolve order.
            rank="CASE WHEN regexp_full_match(tie_order,'[+-]?[0-9]+') THEN try_cast(tie_order AS HUGEINT) END"
            con.execute(f'''CREATE TABLE {eligible} AS WITH ranked AS(SELECT *,{rank} tie_rank FROM {raw} WHERE key_ok AND time_state='valid'),
                ranks AS(SELECT obskey,measurement,available,tie_rank,count(DISTINCT list_value(value,revision_state)) semantic_states FROM ranked GROUP BY ALL),
                bad AS(SELECT obskey,measurement,available,count(*) FILTER(WHERE tie_rank IS NULL OR semantic_states>1) invalid_order FROM ranks GROUP BY ALL),
                x AS(SELECT ranked.*,max(tie_rank) OVER(PARTITION BY obskey,measurement,available) last_rank FROM ranked)
                SELECT x.*,bad.invalid_order FROM x JOIN bad USING(obskey,measurement,available) WHERE invalid_order>0 OR tie_rank=last_rank''')
        else:con.execute(f"CREATE TABLE {eligible} AS SELECT *,0 invalid_order FROM {raw} WHERE key_ok AND time_state='valid'")
        con.execute(f'''CREATE TABLE {ties} AS SELECT obskey,measurement,available,count(*) multiplicity,
            count(DISTINCT list_value(value,revision_state)) states,min(value) AS value,min(revision_state) revision_state,
            bool_or(invalid_order>0) invalid_order FROM {eligible} GROUP BY ALL''')
        taint=raw+'_taint';con.execute(f"CREATE TABLE {taint} AS SELECT DISTINCT obskey FROM {raw} WHERE key_ok AND time_state!='valid'")
        if h.baseline_time and not h.initial_creation_included:
            baseline_tick=literal_tick(h.baseline_time,h.cutoff)
            con.execute(f'UPDATE {ties} SET available=? WHERE available<?',[baseline_tick,baseline_tick])
            # Multiple states clamped to a baseline must retain the latest pre-baseline state, so require explicit baseline records.
            if con.execute(f'SELECT count(*) FROM (SELECT obskey,measurement,available,count(*) n FROM {ties} GROUP BY ALL HAVING count(*)>1)').fetchone()[0]:raise ValueError('Supply one explicit initial-state baseline per observation instead of multiple pre-baseline revisions.')
        source=raw+'_source';con.execute(f'''CREATE TABLE {source} AS SELECT x._row,{sourcekey} obskey,{sourceok} key_ok,x.measurement,x.value selected_value,x.value_state selected_state,x.num selected_num,c.t cutoff,c.state cutoff_state FROM {r.cells} x JOIN {r.table} USING(_row) JOIN {cutoff} c USING(_row){sourcejoin} WHERE x.measurement IN(SELECT unnest(?::VARCHAR[]))''',[list(h.features)])
        con.execute(f'''CREATE TABLE {selection} AS SELECT x.*,v.available,v.value history_value,v.revision_state,v.states,v.multiplicity,v.invalid_order,
            EXISTS(SELECT 1 FROM {taint} z WHERE z.obskey=x.obskey) tainted FROM {source} x ASOF LEFT JOIN {ties} v ON x.obskey=v.obskey AND x.measurement=v.measurement AND x.cutoff>=v.available''')
        coverage_start=literal_tick(h.coverage_start,h.cutoff) if h.coverage_start else None;coverage_end=literal_tick(h.coverage_end,h.cutoff) if h.coverage_end else None;baseline=literal_tick(h.baseline_time,h.cutoff) if h.baseline_time else None
        if coverage_start is not None and coverage_end<=coverage_start:raise ValueError('History coverage end must follow start.')
        complete='false' if h.completeness!='complete' or unassignable else f'cutoff>={max(coverage_start,baseline) if baseline is not None else coverage_start} AND cutoff<{coverage_end} AND NOT tainted'
        for feature in h.features:
            measurement=next(m for m in r.temporal.measurements if m.name==feature)
            source_column=measurement.column or measurement.name if r.temporal.layout=='wide' else r.temporal.value_column
            exact_integer=r.types[source_column] in {'BIGINT','UBIGINT'} and hr.types[h.value_columns[feature]] in {'BIGINT','UBIGINT'}
            decimal_scales=[x[1] for x in (getattr(r,'decimals',{}).get(source_column),getattr(hr,'decimals',{}).get(h.value_columns[feature])) if x]
            exact_decimal=bool(decimal_scales) and measurement.representation=='quantitative' and h.absolute_tolerance is None and h.relative_tolerance is None 
            unit_conflict=feature in h.value_units and measurement.unit is not None and h.value_units[feature]!=measurement.unit
            # Exact accepted quantitative representation, with unsafe conversions blocked.
            valid_history="try_cast(history_value AS DOUBLE) IS NOT NULL AND isfinite(try_cast(history_value AS DOUBLE)) AND NOT (regexp_full_match(history_value,'[+-]?[0-9]+') AND abs(try_cast(history_value AS HUGEINT))>9007199254740992)" if measurement.representation=='quantitative' else 'true'
            equal='selected_num=try_cast(history_value AS DOUBLE)' if measurement.representation=='quantitative' else 'selected_value=history_value'
            if measurement.representation=='quantitative' and (h.absolute_tolerance is not None or h.relative_tolerance is not None):equal=f'abs(selected_num-try_cast(history_value AS DOUBLE))<={h.absolute_tolerance or 0}+{h.relative_tolerance or 0}*abs(try_cast(history_value AS DOUBLE))'
            if exact_integer:
                valid_history='true';equal='selected_value=history_value'
                if h.absolute_tolerance is not None or h.relative_tolerance is not None:
                    valid_history='false' # Unsafe tolerance geometry remains blocked, while exact integer equality is supported.
            if exact_decimal and source_column in getattr(r,'decimals',{}) and h.value_columns[feature] in getattr(hr,'decimals',{}):
                valid_history='true';equal='selected_value=history_value'
            elif exact_decimal and max(decimal_scales)<=38:
                scale=max(0,max(decimal_scales));selected_decimal=f'try_cast(selected_value AS DECIMAL(38,{scale}))';history_decimal=f'try_cast(history_value AS DECIMAL(38,{scale}))'
                valid_history=f'{history_decimal} IS NOT NULL AND {selected_decimal} IS NOT NULL';equal=f'{selected_decimal}={history_decimal}'
            elif exact_decimal:valid_history='false'
            compared=selection+'_cmp'+str(len(e.records))
            con.execute(f'''CREATE TABLE {compared} AS SELECT *,({complete}) complete_at_cutoff,CASE
                WHEN {str(unit_conflict).lower()} THEN 'incompatible_units'
                WHEN NOT key_ok OR cutoff_state!='valid' OR tainted THEN 'unresolved'
                WHEN available IS NULL THEN 'no_eligible_revision'
                WHEN states>1 OR invalid_order THEN 'ambiguous'
                WHEN revision_state='unknown' THEN 'unknown_state'
                WHEN revision_state='retracted' THEN CASE WHEN selected_state='missing' THEN 'withdrawn_and_missing' ELSE 'retracted_but_supplied' END
                WHEN revision_state='known_missing' THEN CASE WHEN selected_state='missing' THEN 'agreement_known_missing' ELSE 'mismatch_known_missing' END
                WHEN NOT coalesce(({valid_history}),false) OR selected_num IS NULL AND ? THEN 'unsafe_or_invalid_value_comparison'
                WHEN selected_state!='valid' THEN 'mismatch'
                WHEN ({equal}) THEN 'agreement' ELSE 'mismatch' END comparison FROM {selection} WHERE measurement=?''',[measurement.representation=='quantitative' and not (exact_integer or exact_decimal),feature])
            counts=dict(con.execute(f'SELECT comparison,count(*) FROM {compared} GROUP BY comparison').fetchall())
            mismatch=con.execute(f"SELECT count(*) FILTER(WHERE complete_at_cutoff),count(*) FILTER(WHERE NOT complete_at_cutoff) FROM {compared} WHERE comparison IN('mismatch','mismatch_known_missing','retracted_but_supplied')").fetchone()
            no_eligible=con.execute(f"SELECT count(*) FILTER(WHERE complete_at_cutoff),count(*) FILTER(WHERE NOT complete_at_cutoff) FROM {compared} WHERE comparison='no_eligible_revision'").fetchone()
            future_candidates=con.execute(f'''SELECT count(*) FROM {compared} x WHERE x.comparison IN('mismatch','no_eligible_revision') AND EXISTS(SELECT 1 FROM {ties} v WHERE v.obskey=x.obskey AND v.measurement=x.measurement AND v.available>x.cutoff AND v.states=1 AND v.revision_state='valid' AND v.value=x.selected_value)''').fetchone()[0]
            detail={'observation_key_comparison':'Explicit normalized temporal component and lexical remaining keys' if h.source_observation_clock else 'Exact lexical keys; no inferred clock role','history_binding':asdict(h),'feature':feature,'feature_unit':measurement.unit,'history_unit':h.value_units.get(feature,measurement.unit),'unit_assumption':'Bound history values share the feature unit unless explicitly declared otherwise.','comparison_states':counts,'complete_history_inconsistencies':mismatch[0],'qualified_history_inconsistencies':mismatch[1],'no_eligible_complete':no_eligible[0],'no_eligible_incomplete':no_eligible[1],'later_value_match_candidates':future_candidates,'unassignable_history_rows':unassignable,'agreement_meaning':'Agreement within supplied coverage; not proof of production point-in-time correctness.','tie_order_representation':'exact integer ordinal' if h.tie_order_column else None,'baseline_meaning':'State only from declared baseline; no earlier availability established.' if baseline is not None else None}
            ident=e.add('revision_history',[r.id,hr.id],detail,measurement=feature,requirement=h.id if h.latest_available_required else None,assumptions=[h.id+':coverage'],witnesses=e.witnesses(f"SELECT _row,obskey,CAST(cutoff AS VARCHAR) cutoff_tick,CAST(available AS VARCHAR) revision_available_tick,comparison,complete_at_cutoff FROM {compared} WHERE comparison NOT IN('agreement','agreement_known_missing','withdrawn_and_missing') ORDER BY _row"))
            if mismatch[0] or mismatch[1]:e.finding(ident,'Selected feature state disagrees with supplied revision history',kind='declared_violation' if h.latest_available_required and mismatch[0] else 'qualified_history_inconsistency',detail='Incomplete histories can omit revisions that change this comparison.',limitations=['No claim about what a training pipeline consumed.'])
            if no_eligible[0] and h.latest_available_required:e.finding(ident,'No eligible feature revision in declared complete history',kind='declared_violation',detail='This conclusion is conditional on the applicable completeness declaration.')
            if future_candidates:e.finding(ident,'Selected values resemble later revisions',detail='Equality identifies an investigation candidate; it does not prove revision provenance.')
        if h.selected_revision_id_column:
            selected_id=r.col(h.selected_revision_id_column);ids=raw+'_ids'
            con.execute(f'''CREATE TABLE {ids} AS SELECT obskey,measurement,revision_id,min(available) first_t,max(available) last_t,count(*) FILTER(WHERE time_state!='valid') invalid FROM {raw} WHERE key_ok AND revision_id IS NOT NULL GROUP BY ALL''')
            identified=raw+'_identified';con.execute(f'''CREATE TABLE {identified} AS SELECT x._row,x.measurement,c.t cutoff,i.first_t,i.last_t,i.invalid FROM {r.cells} x JOIN {r.table} USING(_row) JOIN {cutoff} c USING(_row){sourcejoin} LEFT JOIN {ids} i ON {sourcekey}=i.obskey AND x.measurement=i.measurement AND CAST({selected_id} AS VARCHAR)=i.revision_id WHERE x.measurement IN(SELECT unnest(?::VARCHAR[])) AND c.state='valid' ''',[list(h.features)])
            late=con.execute(f'SELECT count(*) FROM {identified} WHERE first_t=last_t AND invalid=0 AND first_t>cutoff').fetchone()[0]
            ident=e.add('selected_revision_timing',[r.id,hr.id],{'late_identified_revision_cells':late,'latest_state_ambiguity_does_not_remove_identified_timing':True,'binding':h.id},requirement=h.id,witnesses=e.witnesses(f'SELECT _row,measurement,CAST(cutoff AS VARCHAR) cutoff_tick,CAST(first_t AS VARCHAR) revision_tick FROM {identified} WHERE first_t=last_t AND invalid=0 AND first_t>cutoff ORDER BY _row'))
            if late:e.finding(ident,'Identified selected revisions were unavailable at cutoff',kind='declared_violation',detail='Revision-ID timing evidence violates the declared selection/use requirement.')


def maturity(e,spec,relations):
    con=e.work.con
    for m in spec.maturity:
        r=relations[m.source_id];clock=normalize_clock(e.work,r,m.availability or m.source_clock);target=r.col(m.target)
        assessment=literal_tick(m.assessment_time,m.availability or m.source_clock);fit=literal_tick(m.fit_cutoff,m.availability or m.source_clock) if m.fit_cutoff else None
        due='v.t'+('+'+m.delay_ns if m.source_clock else '')
        n,due_missing,not_due,unknown,available,fit_late=con.execute(f'''SELECT count(*),count(*) FILTER(WHERE {target} IS NULL AND v.state='valid' AND {due}<=?),count(*) FILTER(WHERE {target} IS NULL AND v.state='valid' AND {due}>?),count(*) FILTER(WHERE v.state!='valid'),count(*) FILTER(WHERE {target} IS NOT NULL AND v.state='valid' AND {due}<=?),count(*) FILTER(WHERE {target} IS NOT NULL AND v.state='valid' AND {due}>?) FROM {r.table} JOIN {clock} v USING(_row)''',[assessment,assessment,assessment,fit if fit is not None else 2**126]).fetchone()
        ident=e.add('outcome_maturity',r.id,{'target':m.target,'rows':n,'missing_already_due':due_missing,'missing_not_yet_due':not_due,'unknown_maturity':unknown,'available_observed_outcomes_at_assessment':available,'observed_outcomes_unavailable_at_fit':fit_late if fit is not None else None,'assessment_tick':str(assessment),'fit_cutoff_tick':str(fit) if fit is not None else None,'rule':asdict(m),'annotation_evidence_overwritten':False},measurement=m.target,assumptions=['Deterministic delay establishes assumed maturation.'] if m.source_clock else [])
        if fit_late and fit is not None:e.finding(ident,'Training outcomes were unavailable at the declared fit cutoff',kind='declared_violation')
        if due_missing:e.finding(ident,'Some missing outcomes are already due under the declared rule',detail='Review release delays and annotation coverage; maturation does not overwrite annotation evidence.')
