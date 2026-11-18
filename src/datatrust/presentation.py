"""Bounded human report projection; analytical evidence is never mutated."""
from datatrust.contracts import PresentationLimits
from datatrust.report_layout import group_checks
from collections import defaultdict


# Where each table's records live in the completed result, for disclosures (Report Experience, plan I5).
POINTERS={'annotation target details':'/profile/annotations/targets','annotation state details':'/profile/annotations/targets',
          'class distribution':'/profile/classification/distribution','label distributions':'/profile/multilabel/labels',
          'partial positive bounds':'/profile/multilabel/partial_positive_count_bounds','cardinality distribution':'/profile/multilabel/cardinality_distribution',
          'label pairs':'/profile/multilabel/pairs','label combinations':'/profile/multilabel/combinations/records',
          'label constraints':'/profile/multilabel/constraints','numerical output summaries':'/profile/multioutput_regression/outputs',
          'output distribution details':'/profile/multioutput_regression/outputs','output quantile details':'/profile/multioutput_regression/outputs',
          'output declarations':'/profile/multioutput_regression/outputs','input-target relationships':'/profile/multioutput_regression/outputs',
          'output dependencies':'/profile/multioutput_regression/output_dependencies','input coverage histogram':'/profile/readiness/observed_feature_count_histogram',
          'binary sparsity':'/profile/readiness/binary_sparsity','categorical frequencies':'/profile/readiness/categorical_frequency',
          'scale ratios':'/profile/readiness/scale_ratios','quantitative feature details':'/profile/readiness/quantitative_features',
          'feature structure':'/profile/columns','nonempty cohort contrasts':'/profile/annotation_cohorts/records','technical check groups':'/checks'}


def report_view(result,profile_name='focused'):
    p=result.profile; limits=PresentationLimits(**p.get('presentation_limits',{})); omitted=[]
    def take(records,cap,topic):
        records=list(records)
        if len(records)>cap:omitted.append({'topic':topic,'computed':len(records),'displayed':cap,'omitted':len(records)-cap})
        return records[:cap]
    def table(title,columns,rows,topic,cap=None):
        # Rows have already been formatted into short scalar cells. The historical display limit keeps its meaning;
        # every computed row is also kept so the complete table and its disclosure can be laid out.
        rows=list(rows);cap=limits.table_rows if cap is None else cap
        pointer=POINTERS.get(topic,'/profile/multioutput_regression/outputs' if topic.endswith('search ledger') else '/profile')
        return {'title':title,'columns':columns,'rows':take(rows,cap,topic),'topic':topic,'all_rows':rows,'cap':cap,'pointer':pointer}
    fmt=lambda x:'Unavailable' if x is None else format(x,'.6g') if isinstance(x,float) else str(x)
    declaration=lambda x:'Undeclared' if x is None else fmt(x)
    pct=lambda x:'Unavailable' if x is None else f'{100*x:.1f}%'
    actions=take(result.findings,limits.executive_actions,'prioritized actions')
    actions=[{'title':f['title'],'severity':f['severity'],'recommendation':f['recommendation'],'scope':str(f.get('population','selected inputs')),
              'affected_count':f.get('affected_count'), 'evidence_refs':f.get('evidence_refs',[])} for f in actions]
    priorities={}; names=set(p['roles']['columns'])
    def mentions(value):
        if isinstance(value,str):
            if value in names:yield value
        elif isinstance(value,dict):
            for key in ('target','feature','columns','targets','declaration'):
                if key in value:yield from mentions(value[key])
        elif isinstance(value,(list,tuple)):
            for item in value:yield from mentions(item)
    referenced_by={}   # name -> the highest-priority finding that mentions it (first in recorded order on ties)
    for finding in result.findings:
        rank={'High':0,'Moderate':1,'Low':2}[finding['severity']]
        for name in mentions([finding.get('affected_columns',[]),finding.get('evidence',[])]):
            if rank<priorities.get(name,3):referenced_by[name]=finding
            priorities[name]=min(priorities.get(name,3),rank)
    def ordered(records,key):return sorted(records,key=lambda record:priorities.get(record[key],3))
    annotation=[]; task_tables=[]; feature_tables=[]; appendix=[]
    a=p.get('annotations')
    if a:
        annotation.append(table('Per-target annotation coverage',['Target','Observed / rows','Supplied / expected','Unknown expectation','Invalid / conflicts','Uncertain observed'],
                                [[c['target'],f"{c['observed']} / {c['total_rows']} ({pct(c['observed_coverage'])})",f"{c['supplied_expected']} / {c['expected']} ({pct(c['expected_coverage'])})",
                                  f"{c['unknown_expectation_population']} / {c['total_rows']}",f"{c['invalid']} / {c['declaration_inconsistencies']}",str(c['uncertain_observed'])] for c in ordered(a['targets'],'target')],'annotation target details'))
        annotation.append(table('Annotation state counts',['Target','Absent','Expected gaps','Intentional absence','Unresolved metadata'],[[c['target'],c['absent'],c['unavailable_expected'],c['intentional_absence'],c['unresolved_metadata']] for c in ordered(a['targets'],'target')],'annotation state details',limits.target_panels))
    classification=p.get('classification')
    if classification:
        task_tables.append(table('Observed class distribution',['Class','Count','Share of observed'],[[r['label'],r['count'],pct(r['share'])] for r in classification['distribution']],'class distribution'))
    m=p.get('multilabel')
    if m:
        task_tables.append(table('Observed binary assignments',['Label','Positive','Negative','Unknown (absent)','Invalid','Positive / known'],[[r['target'],r['positive'],r['negative'],r['absent'],r['invalid'],pct(r['positive_share_known'])] for r in ordered(m['labels'],'target')],'label distributions'))
        task_tables.append(table('Partial-vector positive-count bounds (invalid vectors excluded)',['Lower positive count','Upper positive count','Partial vectors'],[[r['lower'],r['upper'],r['count']] for r in m['partial_positive_count_bounds']],'partial positive bounds'))
        task_tables.append(table('Complete-vector cardinality',['Positive labels','Complete vectors'],[[key,count] for key,count in m['cardinality_distribution'].items()],'cardinality distribution'))
        task_tables.append(table('Label pairs on jointly observed rows',['Labels','Jointly observed / rows','00 / 01 / 10 / 11','Jaccard','P(second + | first +)'],
                                [[' / '.join(r['targets']),f"{r['jointly_observed']} / {p['row_count']}",f"{r['n00']} / {r['n01']} / {r['n10']} / {r['n11']}",fmt(r['jaccard']),pct(r['b_positive_given_a_positive'])] for r in m['pairs']],'label pairs'))
        task_tables.append(table('Recorded complete-vector combinations ('+m['combinations']['scope']+')',['Assignments in target order','Count'],[[' '.join(map(str,r['vector'])),r['count']] for r in m['combinations']['records']],'label combinations'))
        if m['combinations']['records']:
            legend=take(p['roles']['targets'],limits.target_panels,'combination position legend')
            task_tables[-1]['note']='Binary positions follow declared target order, independently of prioritized label tables: '+', '.join(f'{i+1} = {name}' for i,name in enumerate(legend))+('. Remaining positions are mapped in JSON.' if len(legend)<len(p['roles']['targets']) else '.')
        if m['constraints']:
            task_tables.append(table('Declared label constraints',['Rule','Labels / bound','Violated','Satisfied','Inconclusive'],[[r['rule'],str(r['declaration']),r['violated'],r['satisfied'],r['inconclusive']] for r in m['constraints']],'label constraints'))
    r=p.get('multioutput_regression')
    if r:
        selected=take(ordered(r['outputs'],'target'),limits.target_panels,'detailed output panels')
        task_tables.append(table('Finite outputs (units remain separate)',['Output','Finite / rows','Distinct','Median','IQR','Constraint violations'],
                                [[o['target'],f"{o['finite_count']} / {p['row_count']}",fmt(o['statistics']['distinct_count']) if o['statistics'] else 'Unavailable',
                                  fmt(o['statistics']['quantiles']['median']) if o['statistics'] and o['statistics']['quantiles'] else 'Unavailable',fmt(o['statistics']['iqr']) if o['statistics'] else 'Unavailable',
                                  str(o['constraints']['violation_union_count']) if o['constraints'] else 'Unavailable'] for o in selected],'numerical output summaries'))
        def statistic(output,key):
            return fmt(output['statistics'][key]) if output['statistics'] else 'Unavailable'
        def quantile(output,key):
            values=output['statistics']['quantiles'] if output['statistics'] else None
            return fmt(values[key]) if values else 'Unavailable'
        task_tables.append(table('Output distributions (finite populations, separate units)',
            ['Output','Minimum / maximum','Mean','Sample standard deviation','Central 90% span','Bowley skewness'],
            [[o['target'],statistic(o,'min')+' / '+statistic(o,'max'),statistic(o,'mean'),statistic(o,'sample_std'),statistic(o,'central_90_span'),statistic(o,'bowley_skewness')] for o in selected],'output distribution details'))
        task_tables.append(table('Output quantiles and arithmetic applicability',
            ['Output','p1 / p5','q1 / median / q3','p95 / p99','Blocked evidence'],
            [[o['target'],quantile(o,'p1')+' / '+quantile(o,'p5'),quantile(o,'q1')+' / '+quantile(o,'median')+' / '+quantile(o,'q3'),quantile(o,'p95')+' / '+quantile(o,'p99'),
              o['blocked_reason'] or '; '.join(dict.fromkeys(o['statistics']['unavailable_statistics'].values())) or 'Supported within scope'] for o in selected],'output quantile details'))
        task_tables.append(table('Declared output expectations',['Output','Meaning','Units','Minimum / maximum','Integer / nonnegative'],[[o['target'],o['expectations']['kind'],o['expectations']['units'] or 'Undeclared',declaration(o['expectations']['minimum'])+' / '+declaration(o['expectations']['maximum']),declaration(o['expectations']['integer_required'])+' / '+declaration(o['expectations']['nonnegative'])] for o in selected],'output declarations'))
        task_tables.append(table('Verified input-target witnesses',['Output','Expression','Observed overlap','Observed-target coverage','Availability'],
                                [[o['target'],v['expression'],v['overlap_count'],pct(v['target_coverage']/100),v['availability']] for o in r['outputs'] for v in o['relationships']],'input-target relationships'))
        task_tables.append(table('Output dependencies (separate from inputs)',['Outputs','Finite overlap / rows','Pearson','Identities','Unavailable reason'],
                                [[' / '.join(v['targets']),f"{v['finite_overlap']} / {p['row_count']}",fmt(v['pearson']),'; '.join(i['expression'] for i in v['identities']) or 'None verified',v['pearson_unavailable_reason'] or 'Applicable'] for v in r['output_dependencies']],'output dependencies'))
    ready=p.get('readiness')
    if ready:
        task_tables.append(table('Observed input coverage',['Observed selected features','Rows'],[[key,count] for key,count in ready['observed_feature_count_histogram'].items()],'input coverage histogram'))
        task_tables.append(table('Boolean / binary sparsity',['Feature','Zero','One','Observed','Missing'],[[r['feature'],r['zero_count'],r['one_count'],r['observed_count'],r['missing_count']] for r in ready['binary_sparsity']],'binary sparsity'))
        task_tables.append(table('Low-frequency non-geometry observations',['Feature','Observed values','Distinct values','Singleton categories','Rows in categories < 5'],[[r['feature'],r['observed_count'],r['category_count'],r['singleton_category_count'],r['rows_in_categories_with_fewer_than_five']] for r in ready['categorical_frequency']],'categorical frequencies'))
        task_tables.append(table('Scale evidence by representation',['Population','Eligible fields','IQR ratio','Applicability'],[[r['population'],len(r['eligible_features']),fmt(r['ratio']),r['unavailable_reason'] or 'Conditional on representation and units'] for r in ready['scale_ratios']],'scale ratios'))
        task_tables.append(table('Quantitative feature evidence',['Feature','Meaning','Finite / rows','IQR','Central 90% span','Scale exclusion'],[[r['feature'],r['population'],f"{r['finite_count']} / {p['row_count']}",fmt(r['iqr']),fmt(r['central_90_span']),r['scale_ineligible_reason'] or 'Eligible'] for r in ordered(ready['quantitative_features'],'feature')],'quantitative feature details',limits.feature_details))
    feature_tables.append(table('Selected feature structure',['Feature','Meaning','Storage','Observed distinct','Missing / rows'],
                                [[c['name'],next((s['semantic_type'].replace('_',' ') for s in p['feature_semantics'] if s['column']==c['name']),'unknown'),c['dtype'],c['unique_count'],f"{c['missing_count']} / {p['row_count']}"] for c in ordered(p['columns'],'name') if c['role']=='feature'],'feature structure',limits.feature_details))
    cohorts=p.get('annotation_cohorts')
    cohort_availability = None
    if cohorts:
        nonempty=[c for c in cohorts['records'] if min(c['sizes'])>0]
        unavailable=len(cohorts['records'])-len(nonempty)
        if unavailable:
            omitted.append({'topic':'cohort details with an empty population','computed':unavailable,'displayed':0,'omitted':unavailable})
        cohort_availability=f"{len(cohorts['records'])} feature/cohort records computed; {unavailable} have an empty comparison population. Empty populations support no shape contrast; their counts and reasons remain in JSON."
        feature_tables.append(table('Annotation population contrasts',['Cohort','Feature','Cohort sizes','Missing counts','Supported shape evidence'],
                                    [[c['cohort'],c['feature'],' / '.join(map(str,c['sizes'])),' / '.join(map(str,c['missing_counts'])),
                                      'TV = '+fmt(c['categorical']['total_variation_distance']) if c['categorical'] else '; '.join(f"median {fmt(v['median'])}, IQR {fmt(v['iqr'])}" for v in c['numerical']) if c['numerical'] else c['reason'] or 'Counts only'] for c in nonempty],'nonempty cohort contrasts'))
    technical=group_checks(result.checks)
    appendix.append(table('Check applicability and execution (repeated checks aggregated)',['Check','Count and scope examples','Applicability','Execution','Reason'],technical,'technical check groups',min(limits.table_rows,limits.appendix_rows)))
    remaining=limits.appendix_rows-len(appendix[0]['rows'])
    for o in (r or {}).get('outputs',[]):
        if o['search']:
            candidates=o['search']['candidates']
            if remaining<=0:
                take(candidates,0,o['target']+' search ledger')
                continue
            appendix.append(table('Relationship search: '+o['target'],['Method','Inputs','Status','Reason','Verified rows'],[[v['method'],', '.join(v['columns']),v['status'],v['reason_category'] or 'Applicable',v['verified_rows']] for v in candidates],o['target']+' search ledger',max(0,min(limits.table_rows,remaining))))
            remaining-=len(appendix[-1]['rows'])
    bounds=[]
    for name,obj in [('annotation cohorts',cohorts),('label pairs',(m or {}).get('pair_search')),('combinations',(m or {}).get('combinations')),('output dependencies',(r or {}).get('dependency_search'))]:
        if obj:bounds.append({'diagnostic':name,'status':obj['status'],'meaning':obj.get('scope') or ('Some declared candidate scope was not computed.' if obj['status']=='bounded' else 'Completed within the declared diagnostic scope.')})
    relationship_scopes=defaultdict(list)
    for output in (r or {}).get('outputs',[]):
        if output['search']:relationship_scopes[output['search']['status']].append(output['target'])
    for status,targets in relationship_scopes.items():
        bounds.append({'diagnostic':'input relationships across outputs','status':status,
                       'meaning':f"{len(targets)} output searches; scope examples: {', '.join(targets[:3])}"+(' ...' if len(targets)>3 else '')+'. No observed relationship means only none verified in the searched scope; full per-output coverage is in JSON.'})
    qa={'limits':limits.__dict__,'presentation_omissions':omitted,'appendix_detail_rows':sum(len(t['rows']) for t in appendix),
        'executive_actions_displayed':len(actions),'analytical_bounds':bounds,'meaning':'Presentation omissions do not remove computed JSON evidence. Analytical bounds identify uncomputed scope. Execution failures are separate.'}
    from datatrust.report_structured import capped_tables, finding_index, finding_signal
    every=annotation+task_tables+feature_tables+appendix
    for t in every:
        t['signals']=[finding_signal(referenced_by[str(row[0])]) if row and str(row[0]) in referenced_by else None for row in t['all_rows']]
    referenced={}
    disclosures,complete=capped_tables(every,profile_name,referenced=referenced)
    qa['print_profile']=profile_name
    return {'actions':actions,'annotation_tables':annotation,'task_tables':task_tables,'feature_tables':feature_tables,'appendix':appendix,'qa':qa,'bounds':bounds,
            'disclosures':disclosures,'complete_tables':complete,'referenced':referenced,'findings':finding_index(result.to_dict()['findings'] if hasattr(result,'to_dict') else result.findings),
            'cohort_availability':cohort_availability, 'annotation_rows':(a or {}).get('rows'),'groups':(a or {}).get('groups'), 'multilabel_summary':m,'regression_summary':r,'readiness_summary':ready,'repetition':p.get('repeated_inputs') or (r or {}).get('repeated_inputs')}
