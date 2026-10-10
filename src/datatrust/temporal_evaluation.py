"""Audit supplied memberships or window feasibility, without generating splits."""
from dataclasses import asdict
from datatrust.temporal_normalization import normalize_clock, interval_ticks, literal_tick, key_sql
from datatrust.scalable import fail


def interval_union(e,table,start,end,by_entity=False):
    name=table+'_interval_union'
    partition='PARTITION BY entity ' if by_entity else '';entity='entity,' if by_entity else '';group='entity,g' if by_entity else 'g'
    eligible=' AND entity_ok' if by_entity else ''
    e.query(f'''CREATE TABLE {name} AS WITH x AS(SELECT {entity} {start} s,{end} e,max({end}) OVER({partition}ORDER BY {start},{end} ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING) AS prior FROM {table} WHERE {start} IS NOT NULL AND {end}>{start}{eligible}),
        y AS(SELECT *,sum(CASE WHEN prior IS NULL OR s>prior THEN 1 ELSE 0 END) OVER({partition}ORDER BY s,e ROWS UNBOUNDED PRECEDING) g FROM x)
        SELECT {entity}min(s) s,max(e) e FROM y GROUP BY {group}''')
    return name


def evaluation(e,spec,relations):
    con=e.work.con
    if len(spec.evaluation.folds)>e.config.limits.max_folds:fail('Supplied fold limit exceeded.','temporal_fold_limit')
    for fold in spec.evaluation.folds:
        train=relations[fold.train_source_id];ev=relations[fold.evaluation_source_id];tables=[];exclusions={}
        if train.temporal.clock.kind!=ev.temporal.clock.kind:
            e.add('evaluation', [train.id,ev.id], {'fold':asdict(fold)},blocked='Fold clock interpretations differ.');continue
        for r,interval,tag in ((train,fold.train_interval,'train'),(ev,fold.evaluation_interval,'evaluation')):
            clock=normalize_clock(e.work,r,fold.origin or r.temporal.clock);entity,ok=key_sql(r,r.temporal.entity_columns)
            group,gok=key_sql(r,fold.group_columns)
            where='';params=[]
            if interval:
                start,end=interval_ticks(interval,fold.origin or r.temporal.clock)
                if end<=start:raise ValueError('Fold window end must follow start.')
                where=' WHERE c.t>=? AND c.t<?';params=[start,end]
            table=r.table+'_fold_'+str(len(e.records))+'_'+tag
            con.execute(f'CREATE TABLE {table} AS SELECT _row,{entity} entity,{ok} entity_ok,{group} group_key,{gok} group_ok,c.t origin,c.state origin_state FROM {r.table} JOIN {clock} c USING(_row){where}',params)
            exclusions[tag]={'unresolved_origins':con.execute(f"SELECT count(*) FROM {clock} WHERE state!='valid'").fetchone()[0],'missing_entity_rows':con.execute(f'SELECT count(*) FROM {table} WHERE NOT entity_ok').fetchone()[0]}
            if fold.label_start:
                ls=normalize_clock(e.work,r,fold.label_start);le=normalize_clock(e.work,r,fold.label_end)
                con.execute(f'ALTER TABLE {table} ADD COLUMN label_start HUGEINT');con.execute(f'ALTER TABLE {table} ADD COLUMN label_end HUGEINT')
                con.execute(f"UPDATE {table} SET label_start=x.t FROM {ls} x WHERE {table}._row=x._row AND x.state='valid'");con.execute(f"UPDATE {table} SET label_end=x.t FROM {le} x WHERE {table}._row=x._row AND x.state='valid'")
            tables.append(table)
        a,b=tables;ntrain=con.execute(f'SELECT count(*) FROM {a}').fetchone()[0];neval=con.execute(f'SELECT count(*) FROM {b}').fetchone()[0]
        mode='window_plan_feasibility' if train.id==ev.id or fold.train_interval or fold.evaluation_interval else 'supplied_membership_evidence'
        data={'fold':asdict(fold),'evidence_mode':mode,'train_rows':ntrain,'evaluation_rows':neval,'model_fitting_performed':False,'shared_lookbacks_are_not_automatically_violations':True}
        chronology_block=None;violations=[];blocked_requirements={};gap=None
        origin_gap_required=bool(fold.purge_ns and fold.gap_basis=='origin')
        if fold.chronology!='none' or origin_gap_required:
            if (fold.origin or train.temporal.clock).kind=='local_datetime':chronology_block='Chronological separation across unresolved local clocks cannot establish elapsed/cross-zone guarantees.'
            elif fold.chronology!='within_entity':
                last=con.execute(f"SELECT max(origin) FROM {a} WHERE origin_state='valid'").fetchone()[0];first=con.execute(f"SELECT min(origin) FROM {b} WHERE origin_state='valid'").fetchone()[0]
                if last is None or first is None:chronology_block='One fold population has no usable chronology.'
                else:
                    gap=first-last;data.update(train_latest_tick=str(last),evaluation_first_tick=str(first),chronological_gap_ticks=str(gap))
                    if fold.chronology=='global' and gap<=0:violations.append('global chronology')
            else:
                if len(train.temporal.entity_columns)!=len(ev.temporal.entity_columns):raise ValueError('Within-entity fold keys have incompatible widths.')
                shared,bad,gap=con.execute(f'''WITH x AS(SELECT entity,max(origin) t FROM {a} WHERE entity_ok AND origin_state='valid' GROUP BY entity),y AS(SELECT entity,min(origin) t FROM {b} WHERE entity_ok AND origin_state='valid' GROUP BY entity) SELECT count(*),count(*) FILTER(WHERE y.t<=x.t),min(y.t-x.t) FROM x JOIN y USING(entity)''').fetchone()
                data.update(shared_chronological_entities=shared,within_entity_violations=bad,minimum_entity_gap_ticks=str(gap) if gap is not None else None)
                if bad:violations.append('within-entity chronology')
                if not shared:chronology_block='No shared entities have resolvable chronology; within-entity separation is unanswered.'
        if origin_gap_required:
            data['origin_gap_scope']='within_entity' if fold.chronology=='within_entity' else 'global'
            if (fold.origin or train.temporal.clock).kind!='instant':blocked_requirements['origin_gap']='Nanosecond gaps require resolved instant origins.'
            elif gap is None:blocked_requirements['origin_gap']=chronology_block or 'No usable origin boundary pair; declared gap is unassessable.'
            elif gap<int(fold.purge_ns):violations.append('declared within-entity gap' if fold.chronology=='within_entity' else 'declared gap')
        shared_entities=con.execute(f'SELECT count(*) FROM (SELECT DISTINCT entity FROM {a} WHERE entity_ok) x JOIN (SELECT DISTINCT entity FROM {b} WHERE entity_ok) y USING(entity)').fetchone()[0]
        seen_rows,unseen_rows=con.execute(f'''SELECT count(*) FILTER(WHERE entity_ok AND EXISTS(SELECT 1 FROM {a} x WHERE x.entity={b}.entity AND x.entity_ok)),count(*) FILTER(WHERE entity_ok AND NOT EXISTS(SELECT 1 FROM {a} x WHERE x.entity={b}.entity AND x.entity_ok)) FROM {b}''').fetchone()
        data.update(shared_entities=shared_entities,seen_entity_evaluation_rows=seen_rows,unseen_entity_evaluation_rows=unseen_rows)
        if fold.entity_separation=='disjoint' and shared_entities:violations.append('entity separation')
        if fold.group_columns:
            groups=con.execute(f'SELECT count(*) FROM (SELECT DISTINCT group_key FROM {a} WHERE group_ok) x JOIN (SELECT DISTINCT group_key FROM {b} WHERE group_ok) y USING(group_key)').fetchone()[0];data['shared_groups']=groups
            if fold.entity_separation=='disjoint' and groups:violations.append('group separation')
        overlap=con.execute(f'''SELECT count(*) FROM {b} y WHERE origin_state='valid' AND EXISTS(SELECT 1 FROM {a} x WHERE x.origin_state='valid' AND x.origin=y.origin AND x.entity=y.entity)''').fetchone()[0]
        data['overlapping_origin_rows']=overlap
        if overlap and fold.disjoint_origins:violations.append('prediction-origin separation')
        if fold.label_start:
            invalid=con.execute(f'SELECT count(*) FROM {b} WHERE label_start IS NULL OR label_end IS NULL OR label_end<label_start').fetchone()[0];data['unresolved_or_reversed_label_intervals']=invalid
            per_entity=fold.label_separation_scope=='within_entity'
            if per_entity and len(train.temporal.entity_columns)!=len(ev.temporal.entity_columns):raise ValueError('Within-entity label keys have incompatible widths.')
            for tag,table in (('train',a),('evaluation',b)):
                exclusions[tag]['unresolved_or_reversed_label_intervals']=con.execute(f'SELECT count(*) FROM {table} WHERE label_start IS NULL OR label_end IS NULL OR label_end<label_start').fetchone()[0]
            union=interval_union(e,a,'label_start','label_end',per_entity)
            points=a+'_label_points';entity='entity,' if per_entity else '';eligible=' AND entity_ok' if per_entity else ''
            con.execute(f'CREATE TABLE {points} AS SELECT DISTINCT {entity}label_start t FROM {a} WHERE label_start=label_end{eligible}')
            match='y.entity=x.entity AND ' if per_entity else ''
            point_match='y.entity=p.entity AND ' if per_entity else ''
            # A half-open interval intersects a point at its start, but never at its end.
            label_overlap=con.execute(f'''SELECT count(*) FROM {b} y ASOF LEFT JOIN {union} x ON {match}y.label_end>x.s ASOF LEFT JOIN {points} p ON {point_match}y.label_end>p.t WHERE y.label_start<y.label_end AND (x.e>y.label_start OR p.t>=y.label_start){' AND y.entity_ok' if per_entity else ''}''').fetchone()[0]
            # Point labels are independent of half-open interval endpoints.
            point_overlap=con.execute(f'''SELECT count(*) FROM {b} y WHERE y.label_start=y.label_end AND (EXISTS(SELECT 1 FROM {points} x WHERE {match}x.t=y.label_start) OR EXISTS(SELECT 1 FROM {union} x WHERE {match}x.s<=y.label_start AND x.e>y.label_start)){' AND y.entity_ok' if per_entity else ''}''').fetchone()[0]
            data.update(evaluation_overlapping_label_intervals=label_overlap,evaluation_overlapping_point_labels=point_overlap)
            if fold.disjoint_labels and (label_overlap or point_overlap):violations.append('label separation')
            if fold.purge_ns and fold.gap_basis=='label':
                if fold.label_end.kind!='instant':
                    gap=None;blocked_requirements['label_gap']='Nanosecond label gaps require resolved instant endpoints.'
                elif fold.chronology=='within_entity':
                    gap=con.execute(f"WITH x AS(SELECT entity,max(label_end) t FROM {a} WHERE entity_ok GROUP BY entity),y AS(SELECT entity,min(label_start) t FROM {b} WHERE entity_ok GROUP BY entity) SELECT min(y.t-x.t) FROM x JOIN y USING(entity)").fetchone()[0]
                else:
                    last=con.execute(f'SELECT max(label_end) FROM {a}').fetchone()[0];first=con.execute(f'SELECT min(label_start) FROM {b}').fetchone()[0];gap=first-last if first is not None and last is not None else None
                data['label_gap_ticks']=str(gap) if gap is not None else None
                if gap is None:blocked_requirements.setdefault('label_gap','No usable label boundary pair; declared gap is unassessable.')
                if gap is not None and gap<int(fold.purge_ns):violations.append('declared label purge/gap')
            if fold.horizon_ns:
                bad=con.execute(f'SELECT count(*) FROM {b} WHERE label_end IS NOT NULL AND origin IS NOT NULL AND label_end-origin!=?', [int(fold.horizon_ns)]).fetchone()[0];data['horizon_mismatches']=bad
                if bad:violations.append('target horizon')
            if fold.fit_cutoff:
                fit=literal_tick(fold.fit_cutoff,fold.label_end);late=con.execute(f'SELECT count(*) FROM {a} WHERE label_end>?',[fit]).fetchone()[0];data['training_label_end_after_fit']=late
                # Label interval end is an outcome time, not measured availability.
                data['label_end_establishes_label_availability']=False
        if fold.lookback_ns:
            if (fold.origin or ev.temporal.clock).kind!='instant':data['lookback_support']='blocked: resolved instants required'
            else:
                lookback=int(fold.lookback_ns)
                first=con.execute(f'''SELECT count(*) FROM {b} y LEFT JOIN (SELECT entity,min(first_t) first_t FROM {train.histories} GROUP BY entity) h USING(entity) WHERE y.origin IS NULL OR h.first_t IS NULL OR y.origin-h.first_t<?''',[lookback]).fetchone()[0]
                data.update(lookback_insufficient_observed_boundaries=first,lookback_support_meaning='Observed earliest training boundary per entity, pooled across measurements. This does not establish internal continuity or feature-specific point-in-time availability; consult separate continuity and availability evidence.')
                if first:violations.append('lookback boundary support')
        if fold.fit_cutoff:
            training_maturity=[]
            for m in spec.maturity:
                if m.source_id!=train.id:continue
                clock=normalize_clock(e.work,train,m.availability or m.source_clock);fit=literal_tick(fold.fit_cutoff,m.availability or m.source_clock);available='c.t'+('+'+m.delay_ns if m.source_clock else '')
                late,unknown=con.execute(f"SELECT count(*) FILTER(WHERE c.state='valid' AND {available}>?),count(*) FILTER(WHERE c.state!='valid') FROM {a} x JOIN {clock} c USING(_row) JOIN {train.table} USING(_row) WHERE {train.col(m.target)} IS NOT NULL",[fit]).fetchone();training_maturity.append({'target':m.target,'unavailable_at_fit':late,'unknown_at_fit':unknown})
                if late:violations.append('training outcome availability')
            data['training_maturity']=training_maturity
        details=e.witnesses(f'SELECT entity,count(*) evaluation_rows,min(CAST(origin AS VARCHAR)) first_origin,max(CAST(origin AS VARCHAR)) last_origin FROM {b} WHERE entity_ok GROUP BY entity ORDER BY count(*) DESC,entity')
        data.update(violated_requirements=sorted(set(violations)),blocked_requirements=blocked_requirements,entity_coverage_witnesses=details)
        blocked='; '.join(dict.fromkeys(([chronology_block] if chronology_block else [])+list(blocked_requirements.values()))) or None
        ident=e.add('evaluation',[train.id,ev.id],data,requirement=fold.id,exclusions=exclusions,blocked=blocked)
        if violations:e.finding(ident,'Supplied fold violates declared temporal requirements',kind='declared_violation',detail=', '.join(sorted(set(violations)))+'. Evidence describes '+mode+'.')
