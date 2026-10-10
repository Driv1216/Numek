"""Full-population SQL diagnostics with bounded search and detail retention."""
from dataclasses import asdict
from itertools import combinations
import hashlib
import math

from datatrust.contracts import (AnnotationOptions, AnnotationSpec, CheckOutcome,
    EvidenceRecord, Applicability, ExecutionStatus, RegressionOptions, TargetExpectations)
from datatrust.scalable import quantiles, precision, grouped_overlap

NUMERIC = {'BIGINT','UBIGINT','DOUBLE'}


def ratio(n,d): return n/d if d else None


class Evidence:
    def __init__(self, work, limits):
        self.work=work; self.limits=limits; self.checks=[]; self.records=[]; self.findings=[]; self.coverage={}; self.measurements={}; self.work_units=0; self.segment_checks=0

    def claim(self, units):
        if self.work_units + units > self.limits.max_pair_work: return False
        self.work_units += units
        return True

    def optional(self, scope, family, operation):
        import duckdb
        before = (len(self.checks),len(self.records),len(self.findings),dict(self.coverage),dict(self.measurements))
        try: return operation()
        except (MemoryError, duckdb.OutOfMemoryException, duckdb.IOException): raise
        except (RuntimeError, duckdb.Error) as exc:
            self.checks = self.checks[:before[0]]; self.records = self.records[:before[1]]; self.findings = self.findings[:before[2]]
            self.coverage = before[3]; self.measurements = before[4]
            key = f'{scope}.{family}'
            self.checks.append(CheckOutcome(key,execution=ExecutionStatus.FAILED,scope=scope,reason=f'{type(exc).__name__}: {exc}',version='m4.1'))
            self.coverage[key]={'status':'failed','population':'applicable declared population','reason':str(exc),'planned_bounds':False,'stopping_reason':'unexpected_failure'}

    def detail_limit(self, relation):
        return min(self.limits.max_details,max(1,self.work.options.result_bytes//(self.work.input_count*len(relation.names)*16384)))

    def add(self, scope, family, value, *, columns=(), population='all eligible records', denominator=None, affected=None, blocked=None):
        key=f'{scope}.{family}'; ident=f'e{len(self.records)+1}'
        self.measurements[key]=value
        self.checks.append(CheckOutcome(key,Applicability.BLOCKED if blocked else Applicability.APPLICABLE,
            ExecutionStatus.SKIPPED if blocked else ExecutionStatus.COMPLETED,scope=scope,reason=blocked,evidence_refs=[ident],version='m4.1'))
        ids = tuple(scope.split(':')[:2]) if scope != 'comparison' else ()
        pointer = '/coverage/measurements/' + key.replace('~','~0').replace('/','~1')
        self.records.append(EvidenceRecord(ident,key,[pointer],population,denominator,affected,list(columns),method='exact disk relations / bounded deterministic search',source_ids=ids,source_pair=ids if len(ids)==2 else (),population_id=key+'.population'))
        self.coverage[key]={'population':population,'denominator':denominator,'columns':list(columns),'status':'blocked' if blocked else 'completed','reason':blocked,'detail_retention':self.limits.max_details}
        if isinstance(value, dict):
            self.coverage[key].update(
                selected_columns=value.get('selected_columns',value.get('selected_features',list(columns))),
                excluded_columns=value.get('excluded_columns',value.get('excluded_features',value.get('excluded_targets',[]))),
                completed_work=value.get('work',value.get('pair_work',value.get('completed_checks'))),
                unsearched_scope=value.get('unsearched_pairs',value.get('unsearched_candidates',len(value.get('unsearched',[])))),
                stopping_reason=value.get('stopping_reason','complete'),
                planned_bounds=value.get('stopping_reason','complete').startswith('planned'),
                support_precision_exclusions=[{'scope':d.get('columns',d.get('target',d.get('column'))),'reason':d.get('precision_block',d.get('reason'))} for d in value.get('pairs',value.get('ledger',value.get('columns',[]))) if isinstance(d,dict) and (d.get('precision_block') or d.get('status')=='excluded')],
                detail_omissions=value.get('detail_omissions',value.get('omitted_categories',value.get('distinct_patterns',0)-value.get('retained_patterns',value.get('distinct_patterns',0))))
            )
        self.work.check(key)
        return ident

    def finding(self, ident, title, priority, *, scope, count=None, denominator=None, meaning='observation', action='Review source provenance and the declared use.', limitations='Evidence does not establish a defect, causality, or leakage.'):
        self.findings.append({'id':f'f{len(self.findings)+1}','title':title,'priority':priority,'severity':priority.lower(),'scope':scope,'affected_count':count,'denominator':denominator,'evidence_refs':[ident],'evidence_type':meaning,'next_action':action,'limitations':limitations})


def numeric_summary(con, r, name):
    c=r.col(name); pred=r.finite(name)
    n,lo,hi,zero,negative,integer=con.execute(f'SELECT count(*),min({c}),max({c}),count(*) FILTER(WHERE {c}=0),count(*) FILTER(WHERE {c}<0),count(*) FILTER(WHERE {c}=trunc({c})) FROM {r.table} WHERE {pred}').fetchone()
    distinct=con.execute(f'SELECT count(*) FROM (SELECT {c} FROM {r.table} WHERE {pred} GROUP BY {c})').fetchone()[0]
    result={'finite_count':n,'minimum':lo,'maximum':hi,'zero_count':zero,'negative_count':negative,'integer_count':integer,'distinct_count':distinct,'precision_block':precision(con,r,name),'unavailable_statistics':{}}
    if not n:return result
    mode,modal=con.execute(f'SELECT {c},count(*) n FROM {r.table} WHERE {pred} GROUP BY {c} ORDER BY n DESC,min(_row) LIMIT 1').fetchone()
    result.update(modal_value=mode,modal_count=modal,modal_share=100*modal/n)
    if distinct<=20:
        result['histogram']={'method':'exact_value_counts','denominator':n,'bins':[{'lower':v,'upper':v,'count':cnt} for v,cnt in con.execute(f'SELECT {c},count(*) FROM {r.table} WHERE {pred} GROUP BY {c} ORDER BY {c}').fetchall()]}
    expectations=(r.config.regression or RegressionOptions()) if name in r.task.target_names and r.task.kind=='regression' else None
    expectation=expectations.expectations_by_target.get(name,expectations.expectations if len(r.task.target_names)==1 else TargetExpectations()) if expectations else TargetExpectations()
    endpoints=[('observed_minimum',lo),('observed_maximum',hi),('declared_minimum',expectation.minimum),('declared_maximum',expectation.maximum)]
    result['boundary_concentration']=[{'boundary':label,'value':v,'count':con.execute(f'SELECT count(*) FROM {r.table} WHERE {pred} AND {c}=?',[v]).fetchone()[0]} for label,v in endpoints if v is not None]
    for item in result['boundary_concentration']:item.update(share=100*item['count']/n,review_candidate=n>=20 and distinct>1 and item['count']/n>=.1)
    if result['precision_block']:
        result['unavailable_statistics']={key:result['precision_block'] for key in ('mean','standard_deviation','quantiles','iqr','outliers','rounding')};return result
    scale=max(abs(float(lo)),abs(float(hi))) or 1.;nc=f'({c}/{scale!r})'
    normalized_distinct=con.execute(f'SELECT count(*) FROM (SELECT {nc} FROM {r.table} WHERE {pred} GROUP BY {nc})').fetchone()[0]
    if normalized_distinct<distinct:
        result['precision_block']='scaled_variation_resolution_loss';result['unavailable_statistics']={'geometry':result['precision_block']};return result
    nq=quantiles(con,r.table,nc,pred);qs=[v*scale for v in nq];result['quantiles']=dict(zip(('p1','p5','q1','median','q3','p95','p99'),qs))
    center=float(lo)/scale;m,std=con.execute(f'SELECT avg({nc}-?),stddev_samp({nc}-?) FROM {r.table} WHERE {pred}',[center,center]).fetchone()
    for key,v in [('mean',(m+center)*scale),('standard_deviation',std*scale if std is not None else None),('iqr',(nq[4]-nq[2])*scale),('central_90_span',(nq[5]-nq[1])*scale)]:
        result[key]=v if v is None or math.isfinite(v) else None
        if v is not None and not math.isfinite(v):result['unavailable_statistics'][key]='statistic_overflow'
    niqr=nq[4]-nq[2];fences=(nq[2]-1.5*niqr,nq[4]+1.5*niqr)
    if n>=4 and niqr>0:
        low,high=con.execute(f'SELECT count(*) FILTER(WHERE {nc}<?),count(*) FILTER(WHERE {nc}>?) FROM {r.table} WHERE {pred}',list(fences)).fetchone()
        result.update(outlier_count=low+high,outlier_lower_count=low,outlier_upper_count=high,outlier_share=(low+high)/n,normalized_iqr_fences=list(fences),scale=scale,iqr_fences=[v*scale if math.isfinite(v*scale) else None for v in fences],bowley=((nq[4]-nq[3])-(nq[3]-nq[2]))/niqr)
    else:result['unavailable_statistics']['outliers']='insufficient_observations' if n<4 else 'zero_iqr'
    grids=[]
    if n>=20 and distinct>=5:
        for step in (1.,.1,.01,.001):
            if max(abs(float(lo)),abs(float(hi)))/step>=2**52 or max(math.ulp(float(lo)),math.ulp(float(hi)))>step*1e-8:grids.append({'step':step,'status':'blocked','reason':'floating_resolution'});continue
            hits=con.execute(f'SELECT count(*) FROM {r.table} WHERE {pred} AND abs({c}/?-round({c}/?))<=1e-8',[step,step]).fetchone()[0]
            grids.append({'step':step,'status':'completed','aligned_count':hits,'share':100*hits/n})
    result['rounding']={'status':'completed' if any(g['status']=='completed' for g in grids) else 'blocked','grids':grids,'coarsest_aligned_step':next((g['step'] for g in grids if g.get('share',0)>=95),None),'reason':'insufficient_support' if n<20 or distinct<5 else None}
    if distinct>20:
        span=float(hi)/scale-float(lo)/scale;width=2*niqr/(n**(1/3))
        bins=min(40,max(1,math.ceil(span/width))) if width>0 else min(40,math.ceil(math.log2(n)+1))
        edges=[float(lo)/scale+span*i/bins for i in range(bins+1)]
        idx=f'least({bins-1},greatest(0,CAST(floor(({nc}-?)/?) AS INT)))'
        counts=dict(con.execute(f'SELECT {idx} bin,count(*) FROM {r.table} WHERE {pred} GROUP BY bin ORDER BY bin',[edges[0],span/bins]).fetchall())
        result['histogram']={'method':'freedman_diaconis_capped_40' if width>0 else 'sturges_zero_iqr','denominator':n,'bins':[{'lower':edges[i]*scale,'upper':edges[i+1]*scale,'count':counts.get(i,0)} for i in range(bins)],'interval_policy':'left closed, right open; final bin includes maximum'}
    return result


def profiles(e,r):
    con=e.work.con; columns=[]; semantics=[]; targetset=set(r.task.target_names)
    for name in r.names:
        c=r.col(name); typ=r.types[name]; numeric=typ in NUMERIC
        missing=con.execute(f'SELECT count(*) FROM {r.table} WHERE {c} IS NULL').fetchone()[0]
        distinct,top=con.execute(f'SELECT count(*),coalesce(max(n),0) FROM (SELECT count(*) n FROM {r.table} WHERE {c} IS NOT NULL GROUP BY {c})').fetchone()
        nonfinite=con.execute(f'SELECT count(*) FROM {r.table} WHERE {c} IS NOT NULL AND NOT isfinite({c})').fetchone()[0] if numeric else 0
        role='target' if name in targetset else 'metadata' if name in r.metadata else 'feature' if name in r.features else 'ignored'
        item={'name':name,'column':name,'dtype':typ,'role':role,'missing_count':missing,'missing_rate':100*missing/r.rows,'unique_count':distinct,'constant':distinct<=1,'near_constant':distinct>1 and max(top,missing)/r.rows>=.95,'high_cardinality':typ not in NUMERIC|{'BOOLEAN'} and distinct>=20 and distinct/r.rows>=.8,'is_numeric':numeric,'nonfinite_count':nonfinite,'outlier_rate':0.,'top_value_is_missing':missing>top,'top_value_count':max(top,missing),'non_null_count':r.rows-missing,'top_value_rate':100*max(top,missing)/r.rows}
        if numeric:
            item['numerical']=numeric_summary(con,r,name); item['outlier_count']=item['numerical'].get('outlier_count'); item['outlier_denominator']=item['numerical']['finite_count'];item['outlier_rate']=100*item['numerical'].get('outlier_count',0)/r.rows if r.parsing['base_task_policy']=='classification_legacy_2026_08_13' else 100*item['numerical'].get('outlier_share',0);item['numeric_summary']={'non_finite_count':nonfinite}
        counts=con.execute(f'SELECT {c},count(*) n FROM {r.table} WHERE {c} IS NOT NULL AND octet_length(encode(CAST({c} AS VARCHAR)))<=1024 GROUP BY {c} ORDER BY n DESC,{c} LIMIT ?', [e.detail_limit(r)]).fetchall()
        item['values']=[{'value':v,'count':n} for v,n in counts]; item['omitted_distinct_values']=max(0,distinct-len(counts)); item['residual_count']=r.rows-missing-sum(n for v,n in counts)
        columns.append(item)
        if name in r.features:
            declared='identifier' if name in r.identifiers else r.config.features.semantic_types.get(name)
            if declared=='quantitative' and not numeric: raise ValueError(f'{name}: quantitative declarations require numeric nonboolean storage.')
            ambiguous=typ=='BOOLEAN' or numeric and distinct<=20 and item['numerical']['integer_count']==item['numerical']['finite_count']
            name_id=any(t in name.lower().replace('-','_').split('_') for t in ('id','identifier','index')) and distinct/r.rows>=.98
            semantic=declared or ('ambiguous_identifier' if numeric and name_id else 'ambiguous_code' if ambiguous else 'assumed_quantitative' if numeric else 'categorical')
            semantics.append({'column':name,'declaration':declared,'semantic_type':semantic,'quantitative_geometry':semantic in {'quantitative','assumed_quantitative'}})
    keys=','.join(r.col(n) for n in r.names)
    distinct,extra,participating,largest,duplicate_groups=con.execute(f'SELECT count(*),sum(n-1),sum(CASE WHEN n>1 THEN n ELSE 0 END),max(n),count(*) FILTER(WHERE n>1) FROM (SELECT count(*) n FROM {r.table} GROUP BY {keys})').fetchone()
    feature_missing=' OR '.join(r.col(n)+' IS NULL' for n in r.features) or 'false'
    allmissing=' AND '.join(r.col(n)+' IS NULL' for n in r.features) or 'false'
    incomplete,allnull=con.execute(f'SELECT count(*) FILTER(WHERE {feature_missing}),count(*) FILTER(WHERE {allmissing}) FROM {r.table}').fetchone()
    profile={'row_count':r.rows,'column_count':len(r.names),'columns':columns,'feature_semantics':semantics,'duplicate_count':int(extra),'duplicate_rows':int(extra),'duplicate_group_count':duplicate_groups,'rows_in_duplicate_groups':int(participating),'largest_duplicate_group_size':largest,'missing_cells':sum(c['missing_count'] for c in columns),'missing_feature_cells':sum(c['missing_count'] for c in columns if c['role']=='feature'),'missing_feature_row_count':incomplete,'missing_feature_row_rate':100*incomplete/r.rows,'feature_count':len(r.features),'duplicate_rate':100*extra/r.rows,'duplicate_participating_rows':int(participating),'largest_duplicate_group':largest,'distinct_records':distinct,'incomplete_feature_vectors':incomplete,'all_missing_feature_vectors':allnull,'source':{k:v for k,v in r.source.items() if k!='signature'},'declarations':{'task':asdict(r.task),'base_policy':r.parsing['base_task_policy'],'configuration':asdict(r.config)},'missing_rate':100*sum(c['missing_count'] for c in columns)/(r.rows*len(columns))}
    ident=e.add(r.id,'structure',profile,columns=r.names,denominator=r.rows,affected=int(extra))
    from datatrust.risks import build_unlabeled_findings
    structural=dict(profile,columns=[c for c in columns if c['role']=='feature'],missing_cells=profile['missing_feature_cells'],missing_rate=100*profile['missing_feature_cells']/(r.rows*max(1,len(r.features))))
    for finding in build_unlabeled_findings(structural):
        if finding['code']=='numeric_outlier_concentration' and r.parsing['base_task_policy'].startswith('tabular_'):continue
        e.finding(ident,finding['title'],finding['severity'],scope=r.id,action=finding['recommendation'])
    return profile


def annotation_relations(e,r):
    con=e.work.con; targets=r.task.target_names
    if not targets: return None
    options=r.config.annotations or AnnotationOptions(AnnotationSpec('expected'))
    expressions=['_row']; descriptors=[]
    for i,t in enumerate(targets):
        c=r.col(t); typ=r.types[t]; spec=options.per_target.get(t,options.default)
        if r.task.kind=='regression':
            if typ not in NUMERIC: raise ValueError(f'{t}: regression requires numeric nonboolean target storage.')
            valid=r.finite(t); value=c
        elif r.task.kind=='multilabel_classification':
            valid=f'{c} IN (0,1)' if typ in NUMERIC|{'BOOLEAN'} else f"{c} IN ('0','1')"
            value=f'CASE WHEN {valid} THEN CAST({c} AS INTEGER) END'
        else: valid=f'{c} IS NOT NULL'; value=c
        expectation='?'; status="'unspecified'"; params=[spec.expectation]
        if spec.status_column:
            sc=r.col(spec.status_column)
            mapping=spec.status_values
            if mapping is None:
                from datatrust.contracts import canonical_status_values
                mapping=canonical_status_values()
            # Effective state is exact literal token mapping; invalid/unmapped remain unknown.
            expectation='CASE '+''.join(f'WHEN {str(r.types[spec.status_column]=="VARCHAR").lower()} AND CAST({sc} AS VARCHAR)=? THEN ? ' for _ in mapping)+f"ELSE '{'expected' if spec.expectation=='expected' else 'unknown'}' END"
            ep=[]
            for token,state in mapping.items(): ep.extend([token,state.expectation or spec.expectation])
            status='CASE '+''.join(f'WHEN {str(r.types[spec.status_column]=="VARCHAR").lower()} AND CAST({sc} AS VARCHAR)=? THEN ? ' for _ in mapping)+"ELSE 'unresolved' END"
            sp=[]
            for token,state in mapping.items(): sp.extend([token,state.annotation_status])
            params=ep+sp
        # Small per-target state relations avoid dense Python row arrays.
        state=r.table+f'_a{i}'
        con.execute(f'CREATE TEMP TABLE {state} AS SELECT _row,{value} v,coalesce({valid},false) observed,({c} IS NULL) absent,({c} IS NOT NULL AND NOT coalesce({valid},false)) invalid,{expectation} expectation,{status} status FROM {r.table}',params)
        counts=con.execute(f"SELECT count(*) FILTER(WHERE observed),count(*) FILTER(WHERE absent),count(*) FILTER(WHERE invalid),count(*) FILTER(WHERE expectation='expected'),count(*) FILTER(WHERE expectation='expected' AND observed),count(*) FILTER(WHERE expectation='expected' AND NOT observed),count(*) FILTER(WHERE status='intentionally_unlabeled' AND absent),count(*) FILTER(WHERE expectation='unknown'),count(*) FILTER(WHERE status='uncertain' AND observed),count(*) FILTER(WHERE status='observed' AND absent OR status='intentionally_unlabeled' AND NOT absent) FROM {state}").fetchone()
        keys=('observed','absent','invalid','expected','supplied_expected','unavailable_expected','intentionally_unlabeled','unknown_expectation','uncertain_observed','contradictions')
        d=dict(zip(keys,counts)); d.update(target=t,table=state,expected_coverage=ratio(d['supplied_expected'],d['expected']))
        descriptors.append(d)
        expressions.extend([f'a{i}.observed AS o{i}',f'a{i}.invalid AS i{i}',f'a{i}.v AS v{i}',f"a{i}.expectation='expected' AS e{i}",f"a{i}.expectation='expected' AND a{i}.observed AS s{i}",f"a{i}.expectation='unknown' AS u{i}",f"a{i}.expectation AS ex{i}",f"a{i}.status AS st{i}"])
    table=r.table+'_annotation'
    joins=' '.join(f'JOIN {d["table"]} a{i} USING(_row)' for i,d in enumerate(descriptors))
    con.execute(f'CREATE TEMP TABLE {table} AS SELECT '+','.join(expressions)+f' FROM {r.table} {joins}')
    observed='+'.join(f'CAST(o{i} AS INT)' for i in range(len(targets))); expected='+'.join(f'CAST(e{i} AS INT)' for i in range(len(targets))); supplied='+'.join(f'CAST(s{i} AS INT)' for i in range(len(targets)))
    n=len(targets)
    values=con.execute(f'SELECT count(*) FILTER(WHERE ({observed})>0),count(*) FILTER(WHERE ({observed})={n}),count(*) FILTER(WHERE ({observed}) BETWEEN 1 AND {n-1}),count(*) FILTER(WHERE ({observed})=0),count(*) FILTER(WHERE ({expected})>({supplied})),count(*) FILTER(WHERE ({expected})>0),count(*) FILTER(WHERE ({expected})>0 AND ({expected})=({supplied})) FROM {table}').fetchone()
    rows=dict(zip(('any_observed','complete_observed_vector','partial_observed_vector','no_observed','expected_gaps','rows_with_expected','every_expected_supplied'),values))
    groups=None
    if r.task.group_columns:
        cols=','.join(r.col(c) for c in r.task.group_columns); complete=' AND '.join(r.col(c)+' IS NOT NULL' for c in r.task.group_columns)
        group=r.table+'_agroups'
        con.execute(f'CREATE TEMP TABLE {group} AS SELECT {cols},count(*) row_count,sum({observed}) observed_cells,sum({expected}) expected_cells,sum({supplied}) supplied_cells,bool_or(({observed})={n}) complete_vector,'+','.join(f'bool_or(o{i}) any{i},count(DISTINCT (ex{i},st{i},o{i}))>1 mixed{i}' for i in range(n))+f' FROM {r.table} JOIN {table} USING(_row) WHERE {complete} GROUP BY {cols}')
        alltargets=' AND '.join(f'any{i}' for i in range(n)); mixed=' OR '.join(f'mixed{i}' for i in range(n))
        g=con.execute(f'SELECT count(*),sum(row_count),count(*) FILTER(WHERE observed_cells>0),count(*) FILTER(WHERE complete_vector),count(*) FILTER(WHERE {alltargets}),count(*) FILTER(WHERE expected_cells>supplied_cells),count(*) FILTER(WHERE {mixed}),sum(supplied_cells)/nullif(sum(expected_cells),0),avg(supplied_cells/nullif(expected_cells,0)),sum(observed_cells)/(nullif(sum(row_count),0)*{n}),avg(observed_cells/(row_count*{n})) FROM {group}').fetchone()
        groups=dict(zip(('group_count','eligible_rows','any_annotation_groups','complete_vector_on_one_row_groups','all_targets_somewhere_groups','expected_gap_groups','mixed_state_groups','pooled_expected_cell_coverage','equally_weighted_expected_group_coverage','pooled_observed_cell_coverage','equally_weighted_observed_group_coverage'),g)); groups.update(keys=r.task.group_columns,excluded_incomplete_key_rows=r.rows-(g[1] or 0))
    value={'targets':[{k:v for k,v in d.items() if k!='table'} for d in descriptors],'rows':rows,'groups':groups,'meaning':'Well-formed observations remain observed; expectation, status and validity are independent.'}
    ident=e.add(r.id,'annotations',value,columns=targets,denominator=r.rows,affected=rows['expected_gaps'])
    if rows['expected_gaps']: e.finding(ident,'Declared expected annotations are unavailable','High' if rows['expected_gaps']/rows['rows_with_expected']>=.25 else 'Moderate',scope=r.id,count=rows['expected_gaps'],denominator=rows['rows_with_expected'],meaning='declared_violation')
    for title,predicate,priority in (
        ('Supplied annotations have invalid values',' OR '.join(f'i{i}' for i in range(n)),'High'),
        ('Annotation status contradicts supplied values',' OR '.join(f"(st{i}='observed' AND NOT o{i} AND NOT i{i} OR st{i}='intentionally_unlabeled' AND (o{i} OR i{i}))" for i in range(n)),'Moderate'),
    ):
        count=con.execute(f'SELECT count(*) FROM {table} WHERE {predicate}').fetchone()[0]
        if count:e.finding(ident,title,priority,scope=r.id,count=count,denominator=r.rows)
    return {'table':table,'targets':descriptors,'rows':rows}


def repeated_inputs(e,r,annotations):
    if not r.features: return
    con=e.work.con; cols=','.join(r.col(c) for c in r.features); allnull=' AND '.join(r.col(c)+' IS NULL' for c in r.features)
    group=r.table+'_repeated'; targets=r.task.target_names
    extra=','.join(f'count(DISTINCT v{i}) FILTER(WHERE o{i}) d{i}' for i in range(len(targets)))
    con.execute(f'CREATE TEMP TABLE {group} AS SELECT {cols},count(*) n,min(_row) first_row'+(','+extra if extra else '')+f' FROM {r.table}'+(f' JOIN {annotations["table"]} USING(_row)' if annotations else '')+f' GROUP BY {cols}')
    rows=con.execute(f'SELECT count(*),count(*) FILTER(WHERE n>1),coalesce(sum(n) FILTER(WHERE n>1),0),max(n),coalesce(sum(n) FILTER(WHERE n>1 AND ({allnull})),0) FROM {group}').fetchone()
    vary=' OR '.join(f'd{i}>1' for i in range(len(targets))) or 'false'
    union=con.execute(f'SELECT coalesce(sum(n),0) FROM {group} WHERE n>1 AND ({vary})').fetchone()[0]
    details=[]
    for i,t in enumerate(targets):
        groups,participating=con.execute(f'SELECT count(*),coalesce(sum(n),0) FROM {group} WHERE n>1 AND d{i}>1').fetchone()
        details.append({'target':t,'varying_groups':groups,'participating_rows':int(participating)})
    v=dict(zip(('distinct_input_vectors','repeated_group_count','participating_rows','largest_group','all_missing_participating_rows'),rows));v.update(varying_row_union=int(union),targets=details,interpretation='Observed differences are contextual disagreement; partial complementary annotations are compatible.')
    ident=e.add(r.id,'repeated_inputs',v,columns=r.features,denominator=r.rows,affected=int(union))
    if union: e.finding(ident,'Repeated inputs have different observed annotations','Moderate',scope=r.id,count=int(union),denominator=r.rows)


def missingness(e,r):
    con=e.work.con; features=r.features
    if not features: return
    bits=','.join(f'CAST({r.col(c)} IS NULL AS INTEGER)' for c in features)
    signature=f'list_value({bits})'; group=r.table+'_missing'
    con.execute(f'CREATE TEMP TABLE {group} AS SELECT {signature} signature,count(*) n FROM {r.table} GROUP BY signature')
    patterns=con.execute(f'SELECT signature,n FROM {group} ORDER BY n DESC,signature LIMIT ?', [min(e.limits.max_patterns,e.limits.max_details)]).fetchall()
    total=con.execute(f'SELECT count(*) FROM {group}').fetchone()[0]
    review_count=con.execute(f'SELECT coalesce(sum(n),0) FROM {group} WHERE list_sum(signature)>=2 AND n>=20 AND n>=?', [r.rows*.05]).fetchone()[0]
    value={'patterns':[{'missing_columns':[c for c,b in zip(features,s) if b],'count':n,'share':n/r.rows} for s,n in patterns[:e.limits.max_details]],'distinct_patterns':total,'retained_patterns':min(total,e.limits.max_details),'residual_mass':r.rows-sum(n for s,n in patterns[:e.limits.max_details]),'review_affected_row_union':int(review_count),'selected_columns':list(features),'unsearched_patterns':0,'detail_omissions':max(0,total-e.limits.max_details)}
    pairs=[]; pool=selected_pool(features,e.limits); possible=len(pool)*(len(pool)-1)//2; used=0
    for a,b in selected_pairs(pool,e.limits):
        if not e.claim(r.rows): break
        used+=r.rows; x=r.col(a)+' IS NULL'; y=r.col(b)+' IS NULL'
        counts=con.execute(f'SELECT count(*) FILTER(WHERE NOT ({x}) AND NOT ({y})),count(*) FILTER(WHERE NOT ({x}) AND ({y})),count(*) FILTER(WHERE ({x}) AND NOT ({y})),count(*) FILTER(WHERE ({x}) AND ({y})) FROM {r.table}').fetchone()
        n00,n01,n10,n11=counts; den=math.sqrt((n10+n11)*(n00+n01)*(n01+n11)*(n00+n10))
        phi=(n11*n00-n10*n01)/den if den else None
        qualifies=r.rows>=100 and min(n10+n11,n00+n01,n01+n11,n00+n10)>=20 and phi is not None and abs(phi)>=.5
        pairs.append({'columns':[a,b],'n00':n00,'n01':n01,'n10':n10,'n11':n11,'phi':phi,'missing_b_given_missing_a':ratio(n11,n10+n11),'missing_b_given_observed_a':ratio(n01,n00+n01),'review':qualifies})
    value.update(pairs=pairs,pair_work=used,unsearched_pairs=possible-len(pairs),excluded_columns=[c for c in features if c not in pool],stopping_reason='planned_bounds' if possible>len(pairs) or len(features)>len(pool) else 'complete')
    ident=e.add(r.id,'missingness_structure',value,columns=features,denominator=r.rows,affected=int(review_count))
    if review_count or any(p['review'] for p in pairs): e.finding(ident,'Selected features have concentrated or associated missingness','Moderate',scope=r.id,count=int(review_count),denominator=r.rows,limitations='Missingness patterns do not identify MCAR, MAR or MNAR and do not prescribe imputation.')


def selected_pool(features,limits):
    requested={c for pair in limits.requested_pairs+limits.spearman_pairs for c in pair}
    if requested-set(features):raise ValueError('Requested pairs require selected feature columns.')
    if len(requested)>limits.max_features:raise ValueError('Requested pair columns exceed the configured feature pool.')
    ordered=[c for c in features if c in requested]+[c for c in features if c not in requested]
    return tuple(ordered[:limits.max_features])


def selected_pairs(pool,limits):
    seen=set(); out=[]
    for pair in limits.requested_pairs+limits.spearman_pairs:
        if not set(pair)<=set(pool): raise ValueError('Requested pairs must be within the eligible declared feature pool.')
        key=frozenset(pair)
        if key not in seen: out.append(pair);seen.add(key)
    for offset in range(1,len(pool)):
        for i in range(len(pool)-offset):
            pair=(pool[i],pool[i+offset]); key=frozenset(pair)
            if key not in seen: out.append(pair);seen.add(key)
            if len(out)>=limits.max_pairs: return out[:limits.max_pairs]
    return out[:limits.max_pairs]


def constraints(e,r,extra=()):
    con=e.work.con; details=[]; predicates=[]
    declarations=list(e.limits.constraints)+list(extra)
    if r.task.kind=='regression':
        from datatrust.m4_contracts import ValueConstraint
        options=r.config.regression or RegressionOptions()
        for target in r.task.target_names:
            expectation=options.expectations_by_target.get(target,options.expectations if len(r.task.target_names)==1 else TargetExpectations())
            for rule,value in [('minimum',expectation.minimum),('maximum',expectation.maximum),('nonnegative',expectation.nonnegative),('integer',expectation.integer_required)]:
                if value is not None and value is not False:
                    declarations.append(ValueConstraint((target,),rule,value if rule in {'minimum','maximum'} else None))
        unique=[]
        for declaration in declarations:
            if declaration not in unique:unique.append(declaration)
        declarations=unique
    for constraint in declarations:
        cols=constraint.columns; rule=constraint.rule; value=constraint.value; missing=set(cols)-set(r.names)
        params=[]; pred='false'; inconclusive=0; blocked=None
        if rule=='required': count=len(missing)
        elif rule=='forbidden': count=len(set(cols)&set(r.names))
        elif missing: count=None;blocked='missing_required_columns'
        elif rule=='type':
            typ=r.types[cols[0]]
            if r.representations[cols[0]]['representation']=='unknown':count=None;blocked='unknown_logical_type';inconclusive=r.rows
            else:count=0 if typ in ({'VARCHAR'} if value=='string' else NUMERIC if value=='numeric' else {'BIGINT','UBIGINT'} if value=='integer' else {'BOOLEAN'}) else 1
        else:
            c=r.col(cols[0]); numeric=r.types[cols[0]] in NUMERIC
            if rule=='non_null': pred=c+' IS NULL'
            elif rule=='allowed_values': pred=f'{c} IS NOT NULL AND NOT ({c} IN (SELECT unnest(?)))'; params=[list(value)]
            elif rule=='unique':
                keys=','.join(r.col(n) for n in cols); eligible=' AND '.join(r.finite(n) if r.types[n] in NUMERIC else r.col(n)+' IS NOT NULL' for n in cols)
                count=con.execute(f'SELECT coalesce(sum(n),0) FROM (SELECT count(*) n FROM {r.table} WHERE {eligible} GROUP BY {keys} HAVING count(*)>1)').fetchone()[0]
                inconclusive=r.rows-con.execute(f'SELECT count(*) FROM {r.table} WHERE {eligible}').fetchone()[0]
                pred=f'({keys}) IN (SELECT {keys} FROM {r.table} WHERE {eligible} GROUP BY {keys} HAVING count(*)>1)' if len(cols)>1 else f'{keys} IN (SELECT {keys} FROM {r.table} WHERE {eligible} GROUP BY {keys} HAVING count(*)>1)'
            elif not numeric: count=None;blocked='incompatible_numeric_storage'
            elif rule=='finite': pred=f'{c} IS NOT NULL AND NOT isfinite({c})'
            elif rule in {'minimum','maximum'}: pred=f'{r.finite(cols[0])} AND {c}'+(' < ?' if rule=='minimum' else ' > ?');params=[value]
            elif rule=='nonnegative': pred=f'{r.finite(cols[0])} AND {c}<0'
            elif rule=='integer': pred=f'{r.finite(cols[0])} AND {c}!=trunc({c})'
            elif rule=='less_equal':
                if r.types[cols[1]] not in NUMERIC: count=None;blocked='incompatible_numeric_storage'
                else: pred=f'{r.finite(cols[0])} AND {r.finite(cols[1])} AND {c}>{r.col(cols[1])}'
            if rule!='unique' and not blocked:
                count=con.execute(f'SELECT count(*) FROM {r.table} WHERE {pred}',params).fetchone()[0]
            if not blocked and rule not in {'non_null','unique'}:
                elig=' AND '.join(r.finite(n) if rule in {'minimum','maximum','nonnegative','integer','less_equal'} else r.col(n)+' IS NOT NULL' for n in cols)
                inconclusive=r.rows-con.execute(f'SELECT count(*) FROM {r.table} WHERE {elig}').fetchone()[0]
        examples=[]
        if count and rule not in {'required','forbidden','type'}:
            examples=[{'source_sha256':r.source['sha256'],'parsing_fingerprint':r.parsing['fingerprint'],'logical_row':x[0]} for x in con.execute(f'SELECT _row FROM {r.table} WHERE {pred} ORDER BY _row LIMIT ?',params+[e.limits.max_examples]).fetchall()]
        if rule not in {'required','forbidden','type'} and not blocked: predicates.append((pred,params))
        details.append({'declaration':asdict(constraint),'violations':int(count) if count is not None else None,'violation_unit':'fields' if rule in {'required','forbidden','type'} else 'rows','inconclusive_rows':inconclusive,'blocked':blocked,'row_refs':examples})
    if not details: return
    parameters=[p for pred,ps in predicates for p in ps]
    union=con.execute(f'SELECT count(*) FROM {r.table} WHERE '+(' OR '.join('('+p+')' for p,ps in predicates) or 'false'),parameters).fetchone()[0]
    ident=e.add(r.id,'constraints',{'declarations':details,'affected_row_union':union},columns=sorted({c for d in details for c in d['declaration']['columns']}),denominator=r.rows,affected=union)
    if any(d['violations'] for d in details): e.finding(ident,'A declared dataset requirement is violated','High',scope=r.id,count=union or None,denominator=r.rows if union else None,meaning='declared_violation',action='Reconcile the source with the explicit requirement before relying on it.',limitations='Violation is established only for the declared requirement and completed applicable checks; schema violations count fields, not affected rows.')


def dependence(e,r,profile):
    con=e.work.con; geometry={s['column'] for s in profile['feature_semantics'] if s['quantitative_geometry']}
    pool=selected_pool(r.features,e.limits); pairs=[]; used=0; total=len(pool)*(len(pool)-1)//2
    for a,b in selected_pairs(pool,e.limits):
        if not e.claim(r.rows): break
        used+=r.rows; x,y=r.col(a),r.col(b)
        duplicate=con.execute(f'SELECT count(*) FROM {r.table} WHERE {x} IS DISTINCT FROM {y}').fetchone()[0]==0 if r.types[a]==r.types[b] else False
        item={'columns':[a,b],'exact_duplicate':duplicate}
        if a in geometry and b in geometry:
            pred=f'{r.finite(a)} AND {r.finite(b)}'; n,dx,dy=con.execute(f'SELECT count(*),count(DISTINCT {x}),count(DISTINCT {y}) FROM {r.table} WHERE {pred}').fetchone()
            block=precision(con,r,a,pred) or precision(con,r,b,pred)
            item.update(matched=n,coverage=n/r.rows,distinct=[dx,dy],precision_block=block)
            if not block and n>=2:
                lo,hi,ly,hy=con.execute(f'SELECT min({x}),max({x}),min({y}),max({y}) FROM {r.table} WHERE {pred}').fetchone();sx=max(abs(float(lo)),abs(float(hi))) or 1.;sy=max(abs(float(ly)),abs(float(hy)),1.)
                corr=con.execute(f'SELECT corr({x}/?-?,{y}/?-?) FROM {r.table} WHERE {pred}',[sx,float(lo)/sx,sy,float(ly)/sy]).fetchone()[0]
                item['pearson']=corr if corr is not None and math.isfinite(corr) else None
                item['review']=n>=100 and min(dx,dy)>=10 and n/r.rows>=.8 and corr is not None and math.isfinite(corr) and abs(corr)>=.98
            if (a,b) in e.limits.spearman_pairs or (b,a) in e.limits.spearman_pairs:
                if block: item['spearman_block']=block
                else:
                    rank=f'SELECT rank() OVER(ORDER BY {x})+(count(*) OVER(PARTITION BY {x})-1)/2.0 rx,rank() OVER(ORDER BY {y})+(count(*) OVER(PARTITION BY {y})-1)/2.0 ry FROM {r.table} WHERE {pred}'
                    item['spearman']=con.execute(f'SELECT corr(rx,ry) FROM ({rank})').fetchone()[0]
        elif a not in geometry and b not in geometry:
            pred=f'{x} IS NOT NULL AND {y} IS NOT NULL'
            grouped=f'SELECT {x} x,{y} y,count(*) n FROM {r.table} WHERE {pred} GROUP BY {x},{y}'
            n,dx,dy=con.execute(f'SELECT sum(n),count(DISTINCT x),count(DISTINCT y) FROM ({grouped})').fetchone();n=n or 0
            def fd(source,target):
                groups,minimum,violations=con.execute(f'SELECT count(*),min(n),count(*) FILTER(WHERE distinct_targets>1) FROM (SELECT {source},sum(n) n,count(*) distinct_targets FROM ({grouped}) GROUP BY {source})').fetchone()
                return {'source':a if source=='x' else b,'target':b if target=='y' else a,'violating_groups':violations,'minimum_support':minimum,'review':groups>=2 and (minimum or 0)>=5 and n>=100 and n/r.rows>=.8 and violations==0}
            item.update(matched=n,coverage=n/r.rows,functional_dependencies=[fd('x','y'),fd('y','x')])
            if n>1 and dx>1 and dy>1:
                chi=con.execute(f'WITH cells AS({grouped}),tot AS(SELECT *,sum(n) OVER(PARTITION BY x) nx,sum(n) OVER(PARTITION BY y) ny FROM cells) SELECT sum(n*n*?/(nx*ny))-? FROM tot',[n,n]).fetchone()[0]
                phi=max(0,chi/n-(dx-1)*(dy-1)/(n-1));rc=dx-(dx-1)**2/(n-1);kc=dy-(dy-1)**2/(n-1)
                item['corrected_cramers_v']=math.sqrt(phi/min(rc-1,kc-1)) if min(rc-1,kc-1)>0 else None
        pairs.append(item)
    proxies=[];categorical=[c for c in pool if c not in geometry];proxy_targets=r.task.target_names if r.task.kind in {'classification','multilabel_classification'} else ();proxy_total=len(categorical)*len(proxy_targets)
    for f in categorical:
        for t in proxy_targets:
            if len(pairs)+len(proxies)>=e.limits.max_pairs or not e.claim(r.rows):continue
            used+=r.rows;x=r.col(f);y=r.col(t)
            valid=f'{y} IS NOT NULL' if r.task.kind=='classification' else f"{y} IN (0,1)" if r.types[t] in NUMERIC|{'BOOLEAN'} else f"{y} IN ('0','1')"
            grouped=f'SELECT {x} x,{y} y,count(*) n FROM {r.table} WHERE {x} IS NOT NULL AND {valid} GROUP BY {x},{y}'
            matched,groups,minimum,violations=con.execute(f'SELECT coalesce(sum(n),0),count(*),min(n),count(*) FILTER(WHERE distinct_targets>1) FROM (SELECT x,sum(n) n,count(*) distinct_targets FROM ({grouped}) GROUP BY x)').fetchone()
            proxies.append({'feature':f,'target':t,'matched':int(matched),'coverage':float(matched)/r.rows,'source_categories':groups,'minimum_category_support':minimum,'violating_source_categories':violations,'review':groups>=2 and (minimum or 0)>=5 and matched>=100 and matched/r.rows>=.8 and violations==0,'availability':e.limits.feature_availability.get(f,(r.config.regression.feature_availability if r.config.regression else {}).get(f,'unknown')),'interpretation':'Qualified categorical functional dependence requires a provenance/model-use review; unique-value memorization is excluded.'})
    missing_spearman=[list(p) for p in e.limits.spearman_pairs if not any(set(x['columns'])==set(p) and 'spearman' in x for x in pairs)]
    value={'pairs':pairs,'categorical_input_target_proxies':proxies,'unsearched_proxy_pairs':proxy_total-len(proxies),'selected_features':list(pool),'excluded_features':[c for c in r.features if c not in pool],'unsearched_pairs':total-len(pairs),'work':used,'blocked_spearman':missing_spearman,'stopping_reason':'planned_bounds' if total>len(pairs) or len(r.features)>len(pool) else 'complete'}
    ident=e.add(r.id,'dependencies',value,columns=pool,denominator=r.rows)
    if any(p['review'] for p in proxies) or any(p.get('review') or any(d['review'] for d in p.get('functional_dependencies',[])) for p in pairs): e.finding(ident,'Strong dependence between selected inputs warrants review','Moderate',scope=r.id,limitations='Dependence does not establish redundancy, causality or leakage; unique-value memorization is excluded.')


def cohort_populations(e,r,annotations,profile):
    if not annotations: return
    con=e.work.con; ds=r.config.diagnostics; work=0; details=[]; unsearched=[]
    tables=annotations['targets']; populations=[]
    for i,d in enumerate(tables):
        populations.extend([(d['target'],'expected_missing',d['table'],"expectation='expected' AND NOT observed"),(d['target'],'intentionally_absent',d['table'],"status='intentionally_unlabeled' AND absent"),(d['target'],'unresolved_absence',d['table'],"NOT observed AND expectation!='expected' AND status!='intentionally_unlabeled'")])
    populations.append(('all','no_annotation',annotations['table'],'NOT ('+' OR '.join('o'+str(i) for i in range(len(tables)))+')'))
    geometries={s['column'] for s in profile['feature_semantics'] if s['quantitative_geometry']}
    for target,label,table,condition in populations:
        reference='observed' if target!='all' else '('+' OR '.join('o'+str(i) for i in range(len(tables)))+')'
        n_a,n_b=con.execute(f'SELECT count(*) FILTER(WHERE {reference}),count(*) FILTER(WHERE {condition}) FROM {table}').fetchone()
        for f in r.features:
            if work+2*r.rows>ds.max_cohort_comparisons: unsearched.append({'target':target,'cohort':label,'feature':f});continue
            work+=2*r.rows; c=r.col(f)
            a=f'_row IN (SELECT _row FROM {table} WHERE {reference})';b=f'_row IN (SELECT _row FROM {table} WHERE {condition})'
            ma,mb=con.execute(f'SELECT count(*) FILTER(WHERE {a} AND {c} IS NULL),count(*) FILTER(WHERE {b} AND {c} IS NULL) FROM {r.table}').fetchone()
            item={'target':target,'cohort':label,'feature':f,'observed_rows':n_a,'cohort_rows':n_b,'observed_missing':ma,'cohort_missing':mb,'missingness_difference':(mb/n_b-ma/n_a) if n_a and n_b else None}
            if f in geometries:
                qa=quantiles(con,r.table,c,a+' AND '+r.finite(f),(.25,.5,.75));qb=quantiles(con,r.table,c,b+' AND '+r.finite(f),(.25,.5,.75))
                item.update(observed_quantiles=qa,cohort_quantiles=qb,precision_block=precision(con,r,f,a+' AND '+r.finite(f)) or precision(con,r,f,b+' AND '+r.finite(f)))
            else:
                distinct=con.execute(f'SELECT count(DISTINCT {c}) FROM {r.table} WHERE ({a} OR {b}) AND {c} IS NOT NULL').fetchone()[0]
                if distinct<=100 and n_a and n_b:
                    dist=con.execute(f'SELECT count(*) FILTER(WHERE {a}) na,count(*) FILTER(WHERE {b}) nb FROM {r.table} WHERE {c} IS NOT NULL GROUP BY {c}').fetchall()
                    da=sum(x for x,y in dist);db=sum(y for x,y in dist)
                    item['total_variation']=.5*sum(abs(x/da-y/db) for x,y in dist) if da and db else None
                else:item['category_shape_block']='more_than_100_categories_or_empty_population'
            details.append(item)
    value={'comparisons':details,'unsearched':unsearched,'work':work,'budget':ds.max_cohort_comparisons,'stopping_reason':'planned_work_limit' if unsearched else 'complete','interpretation':'Annotation selection and observed feature populations may differ; this is not label correctness evidence.'}
    e.add(r.id,'annotation_cohorts',value,columns=r.features,denominator=r.rows)


def multilabel(e,r,annotations):
    if r.task.kind!='multilabel_classification': return
    from datatrust.multilabel import validate_options
    options=validate_options(r.task.target_names,r.config.multilabel); con=e.work.con; table=annotations['table'];k=len(r.task.target_names);ds=r.config.diagnostics
    known='+'.join(f'CAST(o{i} AS INT)' for i in range(k));positive='+'.join(f'CAST(coalesce(v{i}=1,false) AS INT)' for i in range(k));invalid=' OR '.join(f'i{i}' for i in range(k));complete=f'({known})={k}'
    n,allzero,positive_total,known_total,invalidrows=con.execute(f'SELECT count(*) FILTER(WHERE {complete}),count(*) FILTER(WHERE {complete} AND ({positive})=0),sum({positive}),sum({known}),count(*) FILTER(WHERE {invalid}) FROM {table}').fetchone()
    patterns=con.execute(f'SELECT list_value('+','.join(f'v{i}' for i in range(k))+f') pattern,count(*) n FROM {table} WHERE {complete} GROUP BY pattern ORDER BY n DESC,pattern LIMIT ?',[min(ds.max_patterns,e.limits.max_details)]).fetchall()
    totalpatterns=con.execute(f'SELECT count(*) FROM (SELECT '+','.join(f'v{i}' for i in range(k))+f' FROM {table} WHERE {complete} GROUP BY ALL)').fetchone()[0]
    cardinality=con.execute(f'SELECT ({positive}) positives,count(*) n FROM {table} WHERE {complete} GROUP BY positives ORDER BY positives').fetchall()
    pairs=[];work=0;pool=range(min(k,ds.max_multilabel_pair_targets));possible=len(pool)*(len(pool)-1)//2
    for a,b in combinations(pool,2):
        if work+r.rows>ds.max_multilabel_comparisons: break
        work+=r.rows
        counts=con.execute(f'SELECT count(*) FILTER(WHERE v{a}=0 AND v{b}=0),count(*) FILTER(WHERE v{a}=0 AND v{b}=1),count(*) FILTER(WHERE v{a}=1 AND v{b}=0),count(*) FILTER(WHERE v{a}=1 AND v{b}=1) FROM {table} WHERE o{a} AND o{b}').fetchone();n00,n01,n10,n11=counts
        pairs.append({'targets':[r.task.target_names[a],r.task.target_names[b]],'n00':n00,'n01':n01,'n10':n10,'n11':n11,'matched':sum(counts),'jaccard':ratio(n11,n11+n01+n10),'p_b_given_a':ratio(n11,n11+n10),'p_a_given_b':ratio(n11,n11+n01)})
    violations=[];preds=[]
    for label,bound,relation in [('minimum_positive',options.minimum_positive,'<'),('maximum_positive',options.maximum_positive,'>')]:
        if bound is None:continue
        # Partial vectors may prove a bound violation; unresolved vectors remain inconclusive.
        expression=f'({positive}+{k}-({known}))<{bound}' if relation=='<' else f'({positive})>{bound}'
        satisfied=f'({positive})>={bound}' if relation=='<' else f'({positive}+{k}-({known}))<={bound}'
        count,ok=con.execute(f'SELECT count(*) FILTER(WHERE NOT ({invalid}) AND {expression}),count(*) FILTER(WHERE NOT ({invalid}) AND {satisfied}) FROM {table}').fetchone()
        violations.append({'rule':label,'bound':bound,'violations':count,'satisfied':ok,'inconclusive':r.rows-count-ok});preds.append('NOT ('+invalid+') AND '+expression)
    for group in options.mutually_exclusive:
        indices=[r.task.target_names.index(t) for t in group]; pos='+'.join(f'CAST(coalesce(v{i}=1,false) AS INT)' for i in indices);unknown='+'.join(f'CAST(NOT o{i} AS INT)' for i in indices)
        pred=f'({pos})>1';count,ok=con.execute(f'SELECT count(*) FILTER(WHERE {pred}),count(*) FILTER(WHERE ({pos}+{unknown})<=1) FROM {table}').fetchone()
        violations.append({'rule':'mutually_exclusive','targets':group,'violations':count,'satisfied':ok,'inconclusive':r.rows-count-ok});preds.append(pred)
    for a,b in options.requires:
        i,j=r.task.target_names.index(a),r.task.target_names.index(b);pred=f'v{i}=1 AND v{j}=0'
        count,ok=con.execute(f'SELECT count(*) FILTER(WHERE {pred}),count(*) FILTER(WHERE v{i}=0 OR v{j}=1) FROM {table}').fetchone();violations.append({'rule':'requires','targets':[a,b],'violations':count,'satisfied':ok,'inconclusive':r.rows-count-ok});preds.append(pred)
    union=con.execute(f'SELECT count(*) FROM {table} WHERE '+(' OR '.join('('+p+')' for p in preds) or 'false')).fetchone()[0]
    value={'complete_vectors':n,'all_zero_vectors':allzero,'known_cells':int(known_total),'known_cell_share':known_total/(r.rows*k),'positive_assignments':int(positive_total),'density_known':ratio(positive_total,known_total),'invalid_rows':invalidrows,'cardinality':[{'positives':p,'count':c} for p,c in cardinality],'patterns':[{'vector':p,'count':c} for p,c in patterns],'distinct_patterns':totalpatterns,'residual_complete_mass':n-sum(c for p,c in patterns),'pairs':pairs,'unsearched_pairs':possible-len(pairs),'excluded_targets':list(r.task.target_names[ds.max_multilabel_pair_targets:]),'work':work,'constraints':violations,'constraint_row_union':union,'stopping_reason':'planned_bounds' if possible>len(pairs) or totalpatterns>len(patterns) or k>ds.max_multilabel_pair_targets else 'complete'}
    ident=e.add(r.id,'multilabel',value,columns=r.task.target_names,denominator=r.rows,affected=union)
    if union:e.finding(ident,'A declared label-vector requirement is violated','High',scope=r.id,count=union,denominator=r.rows,meaning='declared_violation')


def relationships(e,r,profile):
    if r.task.kind!='regression': return
    con=e.work.con;options=r.config.regression or RegressionOptions();bounds=options.relation_limits
    eligible=[s['column'] for s in profile['feature_semantics'] if s['quantitative_geometry']]
    targets=r.task.target_names
    from datatrust.regression import name_candidates
    cues={c['column'] for target in targets for c in name_candidates(eligible,target) if not c['historical_qualifier']}
    ordered=sorted(eligible,key=lambda c:c not in cues);pool=ordered[:bounds.max_pair_features]
    ledger=[];verified=[];singlework=0;pairwork=0;omitted_candidates=0;retention_budget=max(1,e.work.options.result_bytes//8192)
    for method in ('exact_copy','affine_identity','pair_sum'):
        candidates=[(c,) for c in eligible] if method!='pair_sum' else list(combinations(pool,2))
        for cols in candidates:
            for target in targets:
                if len(ledger)>=retention_budget:omitted_candidates+=1;continue
                entry={'target':target,'method':method,'columns':list(cols),'status':'unsearched','reason':'planned_work_limit'};ledger.append(entry)
                if method=='affine_identity' and any(v['target']==target and v['columns']==list(cols) and v['method']=='exact_copy' for v in verified):entry.update(status='excluded',reason='redundant_check');continue
                # Full verification, bounded work shared across every output.
                charge=r.rows*(2 if method=='affine_identity' else 1)
                if method=='pair_sum':
                    if pairwork+charge>bounds.max_pair_comparisons:continue
                    pairwork+=charge
                else:
                    if singlework+charge>bounds.max_single_comparisons:continue
                    singlework+=charge
                pred=' AND '.join(r.finite(c) for c in (*cols,target));y=r.col(target);xs=[r.col(c) for c in cols]
                n,distinct=con.execute(f'SELECT count(*),count(DISTINCT {y}) FROM {r.table} WHERE {pred}').fetchone()
                entry.update(status='completed',reason=None,matched=n)
                if n<(2 if method=='exact_copy' else 20) or distinct<(2 if method=='exact_copy' else 5):entry.update(status='excluded',reason='insufficient_support');continue
                block=next((precision(con,r,c,pred) for c in (*cols,target) if precision(con,r,c,pred)),None)
                if block and method!='exact_copy':entry.update(status='excluded',reason=block);continue
                coefficient=1.;intercept=0.;tolerance=0.
                if method=='exact_copy': bad=con.execute(f'SELECT count(*) FROM {r.table} WHERE {pred} AND {xs[0]}!={y}').fetchone()[0]
                else:
                    lo,hi=con.execute(f'SELECT min({y}),max({y}) FROM {r.table} WHERE {pred}').fetchone();sy=max(abs(float(lo)),abs(float(hi))) or 1.;yn=f'{y}/?';params=[]
                    if method=='affine_identity':
                        lx,hx=con.execute(f'SELECT min({xs[0]}),max({xs[0]}) FROM {r.table} WHERE {pred}').fetchone();sx=max(abs(float(lx)),abs(float(hx))) or 1.
                        if lx==hx:entry.update(status='excluded',reason='constant_feature');continue
                        # Two deterministic min/max anchors; verify every matched row.
                        anchors=con.execute(f'SELECT {xs[0]},{y} FROM {r.table} WHERE {pred} ORDER BY {xs[0]},_row LIMIT 1').fetchone(),con.execute(f'SELECT {xs[0]},{y} FROM {r.table} WHERE {pred} ORDER BY {xs[0]} DESC,_row LIMIT 1').fetchone()
                        x0,y0=anchors[0][0]/sx,anchors[0][1]/sy;x1,y1=anchors[1][0]/sx,anchors[1][1]/sy
                        coef=(y1-y0)/(x1-x0);offset=y0-coef*x0;spread=float(hi)/sy-float(lo)/sy;allowance=32*2.220446049250313e-16*(abs(coef)+abs(offset)+1);tolerance=1e-10*spread+allowance
                        if allowance>1e-6*spread:entry.update(status='excluded',reason='unsafe_identity_resolution');continue
                        bad=con.execute(f'SELECT count(*) FROM {r.table} WHERE {pred} AND abs({y}/?-(?*({xs[0]}/?)+?))>?',[sy,coef,sx,offset,tolerance]).fetchone()[0]
                        coefficient=coef*sy/sx;intercept=offset*sy
                    else:
                        limits_xy=con.execute(f'SELECT max(abs({xs[0]})),max(abs({xs[1]})) FROM {r.table} WHERE {pred}').fetchone();sy=max(sy,*map(float,limits_xy));spread=float(hi)/sy-float(lo)/sy;allowance=32*2.220446049250313e-16
                        if allowance>spread*1e-6:entry.update(status='excluded',reason='unsafe_identity_resolution');continue
                        tolerance=1e-10*spread+allowance
                        bad=con.execute(f'SELECT count(*) FROM {r.table} WHERE {pred} AND abs({y}/?-({xs[0]}/?+{xs[1]}/?))>?',[sy,sy,sy,tolerance]).fetchone()[0]
                if bad:entry['reason']='not_identity';continue
                support=hashlib.sha256();cursor=con.execute(f'SELECT _row-1 FROM {r.table} WHERE {pred} ORDER BY _row');examples=[]
                while True:
                    batch=cursor.fetchmany(4096)
                    if not batch:break
                    for (row,) in batch:
                        support.update(int(row).to_bytes(8,'little',signed=True))
                        if len(examples)<e.limits.max_examples:examples.append(row+1)
                finite_target=next(c['numerical']['finite_count'] for c in profile['columns'] if c['name']==target)
                context=[options.feature_availability.get(c,e.limits.feature_availability.get(c,'unknown')) for c in cols]
                item={'target':target,'method':method,'columns':list(cols),'coefficient':coefficient,'intercept':intercept,'normalized_tolerance':tolerance/(float(hi)/sy-float(lo)/sy) if method!='exact_copy' else 0.,'matched':n,'target_coverage':n/finite_target,'fully_verified':True,'support_sha256':support.hexdigest(),'row_ordinals':examples,'availability':context,'action_eligible':n>=30 and distinct>=5 and n/finite_target>=.8}
                verified.append(item);entry.update(status='verified_relationship',reason=None)
    value={'relationships':verified,'ledger':ledger,'single_work':singlework,'pair_work':pairwork,'eligible_features':eligible,'pair_pool':pool,'result_retention_budget':max(1,e.work.options.result_bytes//8192),'candidate_count':len(targets)*(2*len(eligible)+len(pool)*(len(pool)-1)//2),'excluded_pair_features':[c for c in eligible if c not in pool],'unsearched_candidates':sum(x['status']=='unsearched' for x in ledger)+omitted_candidates,'unsearched_compact_scope':{'candidate_records_not_created':omitted_candidates,'targets':list(targets),'eligible_features':eligible,'pair_pool':pool},'stopping_reason':'planned_bounds' if omitted_candidates or any(x['status']=='unsearched' for x in ledger) or len(pool)<len(eligible) else 'complete'}
    ident=e.add(r.id,'arithmetic_relationships',value,columns=eligible,denominator=r.rows)
    if any(v['action_eligible'] for v in verified):e.finding(ident,'An output is reproducible from selected inputs','Moderate',scope=r.id,limitations='A verified arithmetic relationship requires a provenance and prediction-time availability review; it does not prove leakage.')
    pairs=[];ds=r.config.diagnostics;work=0;outputpool=targets[:ds.max_output_pair_targets]
    for a,b in combinations(outputpool,2):
        if work+3*r.rows>ds.max_output_comparisons:break
        work+=3*r.rows;x,y=r.col(a),r.col(b);pred=r.finite(a)+' AND '+r.finite(b)
        n,dx,dy=con.execute(f'SELECT count(*),count(DISTINCT {x}),count(DISTINCT {y}) FROM {r.table} WHERE {pred}').fetchone();block=precision(con,r,a,pred) or precision(con,r,b,pred)
        item={'targets':[a,b],'matched':n,'distinct':[dx,dy],'precision_block':block}
        if not block and n>=20 and min(dx,dy)>=5:
            copy=con.execute(f'SELECT bool_and({x}={y}) FROM {r.table} WHERE {pred}').fetchone()[0]
            lx,hx,ly,hy=con.execute(f'SELECT min({x}),max({x}),min({y}),max({y}) FROM {r.table} WHERE {pred}').fetchone();sx=max(abs(float(lx)),abs(float(hx))) or 1.;sy=max(abs(float(ly)),abs(float(hy)),1.)
            corr=con.execute(f'SELECT corr({x}/?-?,{y}/?-?) FROM {r.table} WHERE {pred}',[sx,float(lx)/sx,sy,float(ly)/sy]).fetchone()[0]
            item.update(exact_copy=copy,pearson=corr)
            if not copy and lx != hx:
                anchors=con.execute(f'SELECT {x},{y} FROM {r.table} WHERE {pred} ORDER BY {x},_row LIMIT 1').fetchone(),con.execute(f'SELECT {x},{y} FROM {r.table} WHERE {pred} ORDER BY {x} DESC,_row LIMIT 1').fetchone()
                x0,y0=anchors[0][0]/sx,anchors[0][1]/sy;x1,y1=anchors[1][0]/sx,anchors[1][1]/sy
                coef=(y1-y0)/(x1-x0);offset=y0-coef*x0;spread=float(hy)/sy-float(ly)/sy;allowance=32*2.220446049250313e-16*(1+abs(coef)+abs(offset))
                if allowance<=spread*1e-6:
                    tolerance=1e-10*spread+allowance
                    bad=con.execute(f'SELECT count(*) FROM {r.table} WHERE {pred} AND abs({y}/?-(?*({x}/?)+?))>?',[sy,coef,sx,offset,tolerance]).fetchone()[0]
                    item['affine_identity']={'fully_verified':True,'coefficient':coef*sy/sx,'intercept':offset*sy,'normalized_tolerance':tolerance/spread} if not bad else None
                else:item['identity_block']='unsafe_arithmetic'
        pairs.append(item)
    e.add(r.id,'output_dependencies',{'pairs':pairs,'excluded_targets':list(targets[len(outputpool):]),'unsearched_pairs':len(outputpool)*(len(outputpool)-1)//2-len(pairs),'work':work},columns=outputpool,denominator=r.rows)


def readiness(e,r,profile):
    if r.task.kind not in {'clustering','anomaly_detection'}:return
    con=e.work.con;semantics=profile['feature_semantics'];geometry=[s['column'] for s in semantics if s['quantitative_geometry']]
    complete=' AND '.join(r.finite(c) for c in geometry) or 'false';n=con.execute(f'SELECT count(*) FROM {r.table} WHERE {complete}').fetchone()[0]
    details=[];fences=[];categories=[];binary=[];zero_cells=0;finite_cells=0
    for c in r.features:
        item=next(x for x in profile['columns'] if x['name']==c);col=r.col(c)
        if c in geometry:
            num=item['numerical'];zero_cells+=num['zero_count'];finite_cells+=num['finite_count']
            reason=num['precision_block'] or ('fewer_than_20_finite' if num['finite_count']<20 else 'zero_or_unsafe_iqr' if not num.get('iqr') else None)
            record={'column':c,'population':next(s['semantic_type'] for s in semantics if s['column']==c),'iqr':num.get('iqr'),'central_90_span':num.get('central_90_span'),'precision_block':num['precision_block'],'scale_ineligible_reason':reason}
            if r.task.kind=='anomaly_detection' and num.get('normalized_iqr_fences'):
                lo,hi=num['normalized_iqr_fences'];scale=num['scale'];pred=f'({r.finite(c)} AND ({col}/{scale!r}<{lo!r} OR {col}/{scale!r}>{hi!r}))';fences.append(pred)
                values=con.execute(f'SELECT {col},count(*) n FROM {r.table} WHERE {pred} GROUP BY {col} ORDER BY n DESC,{col} LIMIT ?',[e.limits.max_details]).fetchall()
                total=con.execute(f'SELECT count(DISTINCT {col}) FROM {r.table} WHERE {pred}').fetchone()[0]
                record.update(extreme_candidate_value_multiplicities=[{'value':v,'count':count} for v,count in values],omitted_distinct_candidates=total-len(values),residual_candidate_count=num['outlier_count']-sum(count for v,count in values))
            details.append(record)
        else:
            sql=f'SELECT {col} v,count(*) n FROM {r.table} WHERE {col} IS NOT NULL GROUP BY {col}'
            total,single,rare=con.execute(f'SELECT count(*),count(*) FILTER(WHERE n=1),coalesce(sum(n) FILTER(WHERE n<5),0) FROM ({sql})').fetchone()
            examples=con.execute(f'SELECT v,n FROM ({sql}) WHERE n<5 ORDER BY n DESC,v LIMIT ?',[e.limits.max_examples]).fetchall()
            categories.append({'feature':c,'category_count':total,'singleton_category_count':single,'rows_in_categories_with_fewer_than_five':int(rare),'rare_category_examples':[{'value':v,'count':count} for v,count in examples]})
        if r.types[c]=='BOOLEAN' or r.types[c] in NUMERIC and con.execute(f'SELECT count(*) FROM {r.table} WHERE {col} IS NOT NULL AND {col} NOT IN (0,1)').fetchone()[0]==0:
            z,o=con.execute(f'SELECT count(*) FILTER(WHERE {col}=0),count(*) FILTER(WHERE {col}=1) FROM {r.table}').fetchone();binary.append({'feature':c,'zero_count':z,'one_count':o,'observed_count':z+o,'missing_count':item['missing_count']})
    ratios=[]
    for label,pop in [('declared_quantitative','quantitative'),('assumed_quantitative','assumed_quantitative')]:
        eligible=[d for d in details if d['population']==pop and not d['scale_ineligible_reason']]
        spans=[d['iqr'] for d in eligible];scale=max(spans)/min(spans) if len(spans)>=2 else None
        ratios.append({'population':label,'eligible_features':[d['column'] for d in eligible],'ratio':scale if scale is None or math.isfinite(scale) else None,'conditional_review':scale is not None and math.isfinite(scale) and scale>=10 and r.config.features.scale_sensitive is not False})
    def hist(expression):return {str(k):cnt for k,cnt in con.execute(f'SELECT ({expression}) k,count(*) FROM {r.table} GROUP BY k ORDER BY k').fetchall()}
    observed='+'.join(f'CAST({r.col(c)} IS NOT NULL AS INT)' for c in r.features) or '0';finite='+'.join(f'CAST({r.finite(c)} AS INT)' for c in geometry) or '0';nonzero='+'.join(f'CAST(({r.finite(c)}) AND {r.col(c)}!=0 AS INT)' for c in geometry) or '0';touches='+'.join(f'CAST({p} AS INT)' for p in fences) or '0'
    union=con.execute(f'SELECT count(*) FROM {r.table} WHERE ({touches})>0').fetchone()[0]
    allzero=con.execute(f'SELECT count(*) FROM {r.table} WHERE {complete} AND ({nonzero})=0').fetchone()[0] if geometry else None
    value={'quantitative_columns':geometry,'excluded_from_geometry':[s['column'] for s in semantics if not s['quantitative_geometry']],'complete_quantitative_vectors':n if geometry else None,'scales':details,'scale_ratios':ratios,'zero_density_known_quantitative_cells':ratio(zero_cells,finite_cells),'finite_quantitative_cells':finite_cells,'complete_all_zero_quantitative_vectors':allzero,'observed_feature_count_histogram':hist(observed),'finite_quantitative_count_histogram':hist(finite),'nonzero_quantitative_count_histogram':hist(nonzero),'extreme_candidate_feature_count_histogram':hist(touches) if r.task.kind=='anomaly_detection' else None,'iqr_candidate_row_union':union if r.task.kind=='anomaly_detection' else None,'categorical_frequency':categories,'binary_sparsity':binary,'interpretation':'Readiness and IQR candidates are representation-dependent observations, not verified anomalies or removal recommendations.'}
    ident=e.add(r.id,'unsupervised_readiness',value,columns=r.features,denominator=r.rows,affected=union)
    if any(x['conditional_review'] for x in ratios):e.finding(ident,'Quantitative feature scales differ substantially','Low',scope=r.id)


def segments(e,r,profile,reference=None):
    con=e.work.con;details=[];used=0;unsearched=[]
    for declaration in e.limits.segments:
        if declaration.column not in r.names:raise ValueError('Unknown segment column.')
        c=r.col(declaration.column);params=[]
        if declaration.bins:
            ref=reference or r
            logical=next((l for l,c in getattr(r,'alignment',{}).items() if c==declaration.column),declaration.column)
            reference_column=getattr(ref,'alignment',{}).get(logical,declaration.column)
            if ref.types.get(reference_column) not in NUMERIC or r.types[declaration.column] not in NUMERIC:raise ValueError('Numeric bins require compatible quantitative storage.')
            if precision(con,ref,reference_column):raise ValueError('Segment bins require safe reference geometry.')
            edges=sorted(set(quantiles(con,ref.table,ref.col(reference_column),ref.finite(reference_column),tuple(i/declaration.bins for i in range(1,declaration.bins)))))
            expression='CASE '+''.join(f'WHEN {c}<=? THEN {i} ' for i,_ in enumerate(edges))+f'ELSE {len(edges)} END';params=edges
        else:expression=c
        table=r.table+'_segment';con.execute(f'CREATE OR REPLACE TEMP TABLE {table} AS SELECT _row,{expression} segment FROM {r.table} WHERE '+(r.finite(declaration.column) if declaration.bins else c+' IS NOT NULL'),params)
        levels=con.execute(f'SELECT segment,count(*) n FROM {table}'+(' WHERE segment IN (SELECT unnest(?))' if declaration.categories else '')+' GROUP BY segment ORDER BY n DESC,segment LIMIT 32',[list(declaration.categories)] if declaration.categories else []).fetchall()
        totallevels=con.execute(f'SELECT count(DISTINCT segment) FROM {table}').fetchone()[0]
        excluded=r.rows-con.execute(f'SELECT count(*) FROM {table}').fetchone()[0]
        for level,n in levels:
            for f in r.features:
                if e.segment_checks>=e.limits.max_segment_checks or not e.claim(r.rows):unsearched.append({'segment':declaration.column,'level':level,'feature':f});continue
                used+=1;e.segment_checks+=1;x=r.col(f);rest=r.rows-n
                missing,complement=con.execute(f'SELECT count(*) FILTER(WHERE segment IS NOT DISTINCT FROM ? AND {x} IS NULL),count(*) FILTER(WHERE segment IS DISTINCT FROM ? AND {x} IS NULL) FROM {r.table} LEFT JOIN {table} USING(_row)',[level,level]).fetchone()
                diff=missing/n-complement/rest if n and rest else None
                item={'segment_column':declaration.column,'level':level,'feature':f,'rows':n,'complement_rows':rest,'missing':missing,'complement_missing':complement,'missingness_difference':diff,'review':n>=100 and rest>=100 and diff is not None and abs(diff)>=.10,'omitted_levels':max(0,totallevels-len(levels)),'excluded_segment_rows':excluded}
                num=next(p.get('numerical') for p in profile['columns'] if p['name']==f)
                if num and num.get('iqr_fences'):
                    lo,hi=num['iqr_fences'];cnt,finite,other,otherfinite=con.execute(f'SELECT count(*) FILTER(WHERE segment IS NOT DISTINCT FROM ? AND {r.finite(f)} AND ({x}<? OR {x}>?)),count(*) FILTER(WHERE segment IS NOT DISTINCT FROM ? AND {r.finite(f)}),count(*) FILTER(WHERE segment IS DISTINCT FROM ? AND {r.finite(f)} AND ({x}<? OR {x}>?)),count(*) FILTER(WHERE segment IS DISTINCT FROM ? AND {r.finite(f)}) FROM {r.table} LEFT JOIN {table} USING(_row)',[level,lo,hi,level,level,lo,hi,level]).fetchone()
                    delta=cnt/finite-other/otherfinite if finite and otherfinite else None
                    item.update(iqr_candidates=cnt,finite=finite,complement_iqr_candidates=other,complement_finite=otherfinite,candidate_concentration_difference=delta,candidate_review=finite>=100 and cnt/finite>=.05 and delta is not None and delta>=.05)
                details.append(item)
    if details or unsearched:e.add(r.id,'segments',{'comparisons':details,'unsearched':unsearched,'completed_checks':used,'budget':e.limits.max_segment_checks,'stopping_reason':'planned_bounds' if unsearched else 'complete'},columns=tuple(s.column for s in e.limits.segments),denominator=r.rows)


def analyze_input(e,r,*,advanced=True,reference=None):
    if set(e.limits.feature_availability)-set(r.features):raise ValueError('Feature availability must reference selected feature columns.')
    profile=profiles(e,r);a=annotation_relations(e,r)
    e.optional(r.id,'repeated_inputs',lambda:repeated_inputs(e,r,a))
    e.optional(r.id,'annotation_cohorts',lambda:cohort_populations(e,r,a,profile))
    e.optional(r.id,'multilabel',lambda:multilabel(e,r,a))
    if r.task.kind=='regression':
        e.optional(r.id,'constraints',lambda:constraints(e,r))
    e.optional(r.id,'arithmetic_relationships',lambda:relationships(e,r,profile))
    e.optional(r.id,'unsupervised_readiness',lambda:readiness(e,r,profile))
    if advanced:
        if e.limits.missingness: e.optional(r.id,'missingness_structure',lambda:missingness(e,r))
        if e.limits.dependencies: e.optional(r.id,'dependencies',lambda:dependence(e,r,profile))
        if r.task.kind!='regression': e.optional(r.id,'constraints',lambda:constraints(e,r))
        e.optional(r.id,'segments',lambda:segments(e,r,profile,reference))
    return profile,a
