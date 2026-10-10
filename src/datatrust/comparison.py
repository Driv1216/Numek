"""Declared split integrity and exact empirical distribution comparisons."""
from itertools import combinations
import math

from datatrust.scalable import grouped_overlap, quantiles, precision
from datatrust.m4_diagnostics import NUMERIC, ratio


def alignment(spec,r):
    mapping=spec.column_mappings.get(r.id,{})
    if set(mapping)-set(r.names):raise ValueError(f'{r.id}: mapping references absent source columns.')
    resolved={mapping.get(c,c):c for c in r.names}
    if len(resolved)!=len(r.names):raise ValueError('Mapped and unmapped columns collide; mappings must be one-to-one.')
    return resolved


def numeric_compatible(a,b,x,y):
    ta,tb=a.types[x],b.types[y]
    return ta==tb or {ta,tb} <= NUMERIC


def column_role(r,column):
    return 'target' if column in r.task.target_names else 'feature' if column in r.features else 'metadata' if column in r.metadata else 'ignored'


def declared_meaning(r,column):
    semantic='identifier' if column in r.identifiers else r.config.features.semantic_types.get(column)
    units=None;kind=None
    if column in r.task.target_names and r.task.kind=='regression':
        from datatrust.contracts import RegressionOptions,TargetExpectations
        options=r.config.regression or RegressionOptions()
        declaration=options.expectations_by_target.get(column,options.expectations if len(r.task.target_names)==1 else TargetExpectations())
        units=declaration.units;kind=declaration.kind
    return {'semantic':semantic,'units':units,'target_kind':kind}


def distributions(e,a,b,pairs,config,scope,*,conditional=False,inference_allowed=True):
    con=e.work.con;details=[];tests=[]
    if config.inference and not conditional:
        try:from scipy import stats
        except ImportError as exc:raise ValueError('Optional inference requires datatrust[statistics]; install it explicitly.') from exc
    for logical,x,y in pairs:
        ca,cb=a.col(x),b.col(y);na,nb=a.rows,b.rows
        ma=con.execute(f'SELECT count(*) FROM {a.table} WHERE {ca} IS NULL').fetchone()[0];mb=con.execute(f'SELECT count(*) FROM {b.table} WHERE {cb} IS NULL').fetchone()[0]
        change=mb/nb-ma/na
        item={'column':logical,'left_column':x,'right_column':y,'left_rows':na,'right_rows':nb,'left_missing':ma,'right_missing':mb,'missingness_change':change,'missingness_review':min(na,nb)>=config.minimum_population and change>=config.missingness_change}
        left_role,right_role=column_role(a,x),column_role(b,y)
        role_changed=left_role!=right_role
        item.update(left_role=left_role,right_role=right_role,role_changed=role_changed)
        if role_changed:
            item['role_change_qualification']='Comparison of supplied marginal values only; changed feature/target roles do not establish equivalent model use, target meaning or annotation selection. Optional tests retain their existing sampling and method qualifications.'
        if a.types[x] in NUMERIC and b.types[y] in NUMERIC:
            ia=con.execute(f'SELECT count(*) FROM {a.table} WHERE {ca} IS NOT NULL AND NOT isfinite({ca})').fetchone()[0]
            ib=con.execute(f'SELECT count(*) FROM {b.table} WHERE {cb} IS NOT NULL AND NOT isfinite({cb})').fetchone()[0]
            delta=ib/nb-ia/na
            item.update(left_nonfinite=ia,right_nonfinite=ib,nonfinite_change=delta,nonfinite_review=min(na,nb)>=config.minimum_population and delta>=config.missingness_change)
        meanings=declared_meaning(a,x),declared_meaning(b,y)
        conflicting=any(meanings[0][key] is not None and meanings[1][key] is not None and meanings[0][key]!=meanings[1][key] for key in ('semantic','units','target_kind'))
        if conflicting:
            item['distribution_block']='conflicting_declared_meanings_or_units';details.append(item);continue
        if config.inference:
            item['inference_block']=None if inference_allowed and not conditional else 'identical_or_repeated_declared_units_or_conditional_population'
            if inference_allowed and not conditional:
                p=stats.fisher_exact([[ma,na-ma],[mb,nb-mb]]).pvalue
                tests.append({'column':logical,'method':'two_sided_fisher','p_value':float(p)})
        # Semantic declarations take precedence over numeric category storage.
        sa='identifier' if x in a.identifiers else a.config.features.semantic_types.get(x);sb='identifier' if y in b.identifiers else b.config.features.semantic_types.get(y)
        quantitative=a.types[x] in NUMERIC and b.types[y] in NUMERIC and sa not in {'categorical','identifier','unknown'} and sb not in {'categorical','identifier','unknown'}
        if x in a.features and not sa:
            d,integer=con.execute(f'SELECT count(DISTINCT {ca}),bool_and({ca}=trunc({ca})) FROM {a.table} WHERE {a.finite(x)}').fetchone() if a.types[x] in NUMERIC else (None,None)
            if integer and d<=20:quantitative=False
        if y in b.features and not sb:
            d,integer=con.execute(f'SELECT count(DISTINCT {cb}),bool_and({cb}=trunc({cb})) FROM {b.table} WHERE {b.finite(y)}').fetchone() if b.types[y] in NUMERIC else (None,None)
            if integer and d<=20:quantitative=False
        if not numeric_compatible(a,b,x,y):item['distribution_block']='incompatible_representations';details.append(item);continue
        if a.types[x]!=b.types[y] and 'DOUBLE' in {a.types[x],b.types[y]}:
            integer_side,name=(a,x) if a.types[x]!='DOUBLE' else (b,y)
            if precision(con,integer_side,name)=='unsafe_integer_geometry':item['distribution_block']='unsafe_numeric_alignment';details.append(item);continue
        if quantitative:
            pa,pb=a.finite(x),b.finite(y)
            fa=con.execute(f'SELECT count(*) FROM {a.table} WHERE {pa}').fetchone()[0];fb=con.execute(f'SELECT count(*) FROM {b.table} WHERE {pb}').fetchone()[0]
            item.update(left_finite=fa,right_finite=fb,left_nonfinite=na-ma-fa,right_nonfinite=nb-mb-fb)
            if not fa or not fb:item['distribution_block']='empty_finite_population';details.append(item);continue
            block=precision(con,a,x) or precision(con,b,y)
            if block:item['distribution_block']=block;details.append(item);continue
            from datatrust.distribution_effects import numeric_effect
            distance,wasserstein,ties=numeric_effect(con,a.table,ca,pa,b.table,cb,pb,fa,fb)
            if wasserstein is not None and not math.isfinite(wasserstein):item['wasserstein_block']='statistic_overflow';wasserstein=None
            qa=quantiles(con,a.table,ca,pa);qb=quantiles(con,b.table,cb,pb);iqr=qa[4]-qa[2];iqr=iqr if math.isfinite(iqr) else None
            norm=wasserstein/iqr if iqr is not None and iqr>0 and wasserstein is not None and math.isfinite(wasserstein/iqr) else None
            item.update(cdf_distance=distance,wasserstein_1=wasserstein,left_quantiles=qa,right_quantiles=qb,median_shift=qb[3]-qa[3] if math.isfinite(qb[3]-qa[3]) else None,reference_iqr=iqr,normalized_wasserstein=norm,normalization_block=None if norm is not None else 'zero_or_unsafe_reference_iqr')
            exceed=con.execute(f'SELECT count(*) FROM {b.table} WHERE {pb} AND ({cb}<? OR {cb}>?)',[con.execute(f'SELECT min({ca}) FROM {a.table} WHERE {pa}').fetchone()[0],con.execute(f'SELECT max({ca}) FROM {a.table} WHERE {pa}').fetchone()[0]]).fetchone()[0]
            item['reference_range_exceedance']=exceed
            item['distribution_review']=min(fa,fb)>=config.minimum_population and (distance>=config.cdf_distance or norm is not None and norm>=config.normalized_wasserstein)
            if config.inference and inference_allowed and not conditional:
                def continuous(r,name):
                    if logical in config.continuous_columns and r.config.features.semantic_types.get(name)=='quantitative':return True
                    if name in r.task.target_names and r.task.kind=='regression':
                        from datatrust.contracts import RegressionOptions,TargetExpectations
                        opts=r.config.regression or RegressionOptions();return opts.expectations_by_target.get(name,opts.expectations if len(r.task.target_names)==1 else TargetExpectations()).kind=='continuous'
                    return False
                if min(fa,fb)>=100 and not ties and continuous(a,x) and continuous(b,y):
                    en=fa*fb/(fa+fb);p=stats.distributions.kstwo.sf(distance,round(en))
                    tests.append({'column':logical,'method':'asymptotic_two_sample_KS','p_value':float(p)})
                else:item['ks_block']='requires_explicit_continuous_quantitative_fields_100_finite_each_and_no_pooled_ties'
        else:
            pa=a.finite(x) if a.types[x] in NUMERIC else ca+' IS NOT NULL';pb=b.finite(y) if b.types[y] in NUMERIC else cb+' IS NOT NULL'
            oa=con.execute(f'SELECT count(*) FROM {a.table} WHERE {pa}').fetchone()[0];ob=con.execute(f'SELECT count(*) FROM {b.table} WHERE {pb}').fetchone()[0]
            item.update(left_observed=oa,right_observed=ob)
            if not oa or not ob:item['distribution_block']='empty_observed_population';details.append(item);continue
            sql=f'WITH f AS(SELECT {ca} datum,count(*) n,0::BIGINT m FROM {a.table} WHERE {pa} GROUP BY {ca} UNION ALL SELECT {cb},0::BIGINT,count(*) FROM {b.table} WHERE {pb} GROUP BY {cb}),u AS(SELECT datum,sum(n) n,sum(m) m FROM f GROUP BY datum)'
            tv,vocab,newmass,gone=con.execute(sql+' SELECT .5*sum(abs(n/?-m/?)),count(*),sum(m) FILTER(WHERE n=0),sum(n) FILTER(WHERE m=0) FROM u',[oa,ob]).fetchone()
            retained=con.execute(sql+' SELECT datum,n,m FROM u WHERE octet_length(encode(CAST(datum AS VARCHAR)))<=1024 ORDER BY greatest(n,m) DESC,datum LIMIT ?',[min(e.detail_limit(a),e.detail_limit(b))]).fetchall()
            item.update(total_variation=tv,union_vocabulary=vocab,new_category_mass=int(newmass or 0)/ob,disappearing_category_mass=int(gone or 0)/oa,categories=[{'value':v,'left_count':int(n),'right_count':int(m)} for v,n,m in retained],omitted_categories=max(0,vocab-len(retained)),left_residual=oa-sum(n for v,n,m in retained),right_residual=ob-sum(m for v,n,m in retained),distribution_review=min(oa,ob)>=config.minimum_population and tv>=config.categorical_distance)
            # Qualifications are computed over the entire vocabulary, not retained detail.
            newreview,gone_review=con.execute(sql+' SELECT count(*) FILTER(WHERE n=0 AND m>=? AND m/? >=?),count(*) FILTER(WHERE m=0 AND n>=? AND n/? >=?) FROM u',[config.category_count,ob,config.category_share,config.category_count,oa,config.category_share]).fetchone()
            item['new_or_disappearing_review']=min(oa,ob)>=config.minimum_population and bool(newreview or gone_review)
            if config.inference and inference_allowed and not conditional:
                qualified,chi=con.execute(sql+' SELECT bool_and(n>=5 AND m>=5 AND (n+m)*?/(?+?)>=5 AND (n+m)*?/(?+?)>=5),sum(pow(n-(n+m)*?/(?+?),2)/((n+m)*?/(?+?))+pow(m-(n+m)*?/(?+?),2)/((n+m)*?/(?+?))) FROM u',[oa,oa,ob,ob,oa,ob,oa,oa,ob,oa,oa,ob,ob,oa,ob,ob,oa,ob]).fetchone()
                if qualified and vocab>=2:tests.append({'column':logical,'method':'pearson_chi_square','p_value':float(stats.chi2.sf(chi,vocab-1))})
                else:item['chi_square_block']='every_observed_and_expected_cell_must_be_at_least_five'
        details.append(item)
    # One family across successfully calculated marginal tests, including missingness.
    ordered=sorted(tests,key=lambda t:t['p_value']);running=1.
    for i in range(len(ordered)-1,-1,-1):
        running=min(running,ordered[i]['p_value']*len(ordered)/(i+1));ordered[i]['adjusted_p_value']=running;ordered[i]['adjustment']='Benjamini–Hochberg'
    datum={'columns':details,'tests':tests,'inference_requested':config.inference,'sampling':config.sampling,'conditional':conditional,'effect_thresholds':{'missingness':config.missingness_change,'categorical_TV':config.categorical_distance,'CDF':config.cdf_distance,'W1_reference_IQR':config.normalized_wasserstein},'interpretation':'Effects describe parsed populations. Significance alone does not create or raise review priority.'}
    ident=e.add(scope,'populations',datum,columns=[l for l,x,y in pairs],population='observed categorical or finite quantitative values; missing/non-finite counts separately')
    qualifications=[{'column':d['column'],'left_role':d['left_role'],'right_role':d['right_role'],'qualification':d['role_change_qualification']} for d in details if d['role_changed']]
    blocks=[{'column':d['column'],'reason':d['distribution_block']} for d in details if d.get('distribution_block')]
    e.coverage[scope+'.populations'].update(role_change_qualifications=qualifications,distribution_blocks=blocks)
    if any(d.get('missingness_review') or d.get('nonfinite_review') or d.get('distribution_review') or d.get('new_or_disappearing_review') for d in details):e.finding(ident,'Supported input or annotation populations differ','Moderate',scope=scope)
    return datum


def split_pair(e,spec,a,b,aa,bb,annotations):
    con=e.work.con;scope=f'{a.id}:{b.id}';datum={};feature_pairs=[]
    aset,bset=set(aa),set(bb)
    if aset==bset:
        datum['records']=grouped_overlap(con,a,b,[(l and aa[l],bb[l]) for l in aa])
    else:datum['records']={'blocked':'aligned_original_column_sets_differ','left_only':sorted(aset-bset),'right_only':sorted(bset-aset)}
    af={l for l,c in aa.items() if c in a.features};bf={l for l,c in bb.items() if c in b.features}
    if af==bf and af:
        feature_pairs=[(aa[l],bb[l]) for l in aa if l in af];datum['features']=grouped_overlap(con,a,b,feature_pairs)
        if not datum['features'].get('blocked'):
            all_a=' AND '.join(a.col(x)+' IS NULL' for x,y in feature_pairs);all_b=' AND '.join(b.col(y)+' IS NULL' for x,y in feature_pairs)
            na=con.execute(f'SELECT count(*) FROM {a.table} WHERE {all_a}').fetchone()[0];nb=con.execute(f'SELECT count(*) FROM {b.table} WHERE {all_b}').fetchone()[0]
            datum['features']['all_missing_left_matches']=na if nb else 0;datum['features']['all_missing_right_matches']=nb if na else 0
            datum['features']['informative_left_rows']=datum['features']['left_rows']-(na if nb else 0);datum['features']['informative_right_rows']=datum['features']['right_rows']-(nb if na else 0)
    else:datum['features']={'blocked':'declared_feature_sets_differ_or_empty','left_features':sorted(af),'right_features':sorted(bf)}
    units=[]
    for kind,keys in [('entity',spec.identity_keys),('group',spec.group_keys)]:
        for key in keys:
            if not set(key)<=aset&bset:unit={'blocked':'missing_key_columns'}
            else:unit=grouped_overlap(con,a,b,[(aa[l],bb[l]) for l in key],complete=True)
            unit.update(kind=kind,columns=list(key));units.append(unit)
    datum['units']=units
    # Declared complete matched-vector annotation differences; aggregate before joining.
    conflicts=[]
    if feature_pairs and not datum['features'].get('blocked') and annotations.get(a.id) and annotations.get(b.id):
        a_targets={l:c for l,c in aa.items() if c in a.task.target_names};b_targets={l:c for l,c in bb.items() if c in b.task.target_names}
        for l,t in a_targets.items():
            if l not in b_targets:continue
            u=b_targets[l];i=a.task.target_names.index(t);j=b.task.target_names.index(u)
            if not numeric_compatible(a,b,t,u):conflicts.append({'target':l,'blocked':'incompatible_representations'});continue
            fields_a=','.join(a.col(x)+f' k{q}' for q,(x,y) in enumerate(feature_pairs));fields_b=','.join(b.col(y)+f' k{q}' for q,(x,y) in enumerate(feature_pairs));keys=','.join(f'k{q}' for q in range(len(feature_pairs)));join=' AND '.join(f'x.k{q} IS NOT DISTINCT FROM y.k{q}' for q in range(len(feature_pairs)))
            # Different support sets or overlapping numerical ranges are descriptive. Any unequal observed values in a shared vector is contextual disagreement.
            sql=f'WITH x AS(SELECT {fields_a},count(*) n,min(v{i}) lo,max(v{i}) hi FROM {a.table} JOIN {annotations[a.id]["table"]} USING(_row) WHERE o{i} GROUP BY {keys}),y AS(SELECT {fields_b},count(*) n,min(v{j}) lo,max(v{j}) hi FROM {b.table} JOIN {annotations[b.id]["table"]} USING(_row) WHERE o{j} GROUP BY {keys}) SELECT count(*),coalesce(sum(x.n),0),coalesce(sum(y.n),0) FROM x JOIN y ON {join} WHERE x.lo IS DISTINCT FROM y.hi OR x.hi IS DISTINCT FROM y.lo'
            groups,left,right=con.execute(sql).fetchone();conflicts.append({'target':l,'varying_shared_groups':groups,'observed_left_participating_rows':int(left),'observed_right_participating_rows':int(right)})
    datum['annotation_differences']=conflicts
    intent=spec.evaluation_intent if not spec.intent_pairs or any(set(p)=={a.id,b.id} for p in spec.intent_pairs) else 'unknown';datum['evaluation_intent']=intent
    ident=e.add(scope,'split_integrity',datum,columns=[l for l in aa if l in bb],population='parsed records, full declared feature vectors and explicit complete finite keys')
    violated=(intent=='record_disjoint' and datum['records'].get('multiset_intersection',0)>0 or intent=='entity_disjoint' and any(u['kind']=='entity' and u.get('shared_distinct_groups',0) for u in units) or intent=='group_disjoint' and any(u['kind']=='group' and u.get('shared_distinct_groups',0) for u in units))
    if violated:e.finding(ident,'Declared evaluation separation is violated','High',scope=scope,meaning='declared_violation',limitations='Violation applies to the declared equality and separation requirement; it does not establish proven leakage.')
    elif intent=='unknown' and datum['features'].get('informative_right_rows',0):e.finding(ident,'Evaluation sources share informative selected inputs','Moderate',scope=scope,count=datum['features']['informative_right_rows'],denominator=b.rows)
    elif {'validation','test'}=={a.role,b.role} and datum['features'].get('informative_right_rows',0):e.finding(ident,'Validation and test share selected inputs','Moderate',scope=scope)
    return datum


def compare_relations(e,spec,relations,profiles,annotations,config):
    align={r.id:alignment(spec,r) for r in relations};pairs=list(combinations(relations,2));summary=[]
    for a,b in pairs:
        if spec.mode=='versions' and a.role!='reference':a,b=b,a
        aa,bb=align[a.id],align[b.id];scope=a.id+':'+b.id
        added=sorted(set(bb)-set(aa));removed=sorted(set(aa)-set(bb));changes=[]
        for l,x in aa.items():
            if l not in bb:continue
            y=bb[l]
            if a.types[x]!=b.types[y] or column_role(a,x)!=column_role(b,y) or declared_meaning(a,x)!=declared_meaning(b,y):changes.append({'column':l,'left_storage':a.types[x],'right_storage':b.types[y],'left_role':column_role(a,x),'right_role':column_role(b,y),'left_meaning':declared_meaning(a,x),'right_meaning':declared_meaning(b,y)})
        ident=e.add(scope,'schema',{'added':added,'removed':removed,'changes':changes,'left_order':list(aa),'right_order':list(bb),'mappings':{a.id:spec.column_mappings.get(a.id,{}),b.id:spec.column_mappings.get(b.id,{})}},columns=sorted(set(aa)|set(bb)))
        if removed or any(c['left_role']!=c['right_role'] or not numeric_compatible(a,b,aa[c['column']],bb[c['column']]) or c['left_meaning']!=c['right_meaning'] for c in changes):e.finding(ident,'Selected schema or representation changed','Moderate',scope=scope)
        inference_allowed=a.source['sha256']!=b.source['sha256']
        for key in spec.identity_keys+spec.group_keys:
            if set(key)<=set(aa)&set(bb):
                overlap=grouped_overlap(e.work.con,a,b,[(aa[l],bb[l]) for l in key],complete=True)
                if overlap.get('shared_distinct_groups',0) or overlap.get('blocked'):inference_allowed=False
                if config.inference:
                    for r,names in ((a,aa),(b,bb)):
                        columns=[names[l] for l in key];fields=','.join(r.col(c) for c in columns)
                        eligible=' AND '.join(r.finite(c) if r.types[c] in NUMERIC else r.col(c)+' IS NOT NULL' for c in columns)
                        if e.work.con.execute(f'SELECT count(*) FROM (SELECT count(*) n FROM {r.table} WHERE {eligible} GROUP BY {fields} HAVING count(*)>1)').fetchone()[0]:inference_allowed=False
        if a.task.group_columns or b.task.group_columns:
            # Repeated units within a source conflict with independent-row declarations.
            for r in (a,b):
                if r.task.group_columns:
                    cols=','.join(r.col(c) for c in r.task.group_columns)
                    if e.work.con.execute(f'SELECT count(*) FROM (SELECT count(*) n FROM {r.table} GROUP BY {cols} HAVING count(*)>1)').fetchone()[0]:inference_allowed=False
        ga={l for l,x in aa.items() if x in a.task.group_columns};gb={l for l,y in bb.items() if y in b.task.group_columns}
        if ga and ga==gb:
            overlap=grouped_overlap(e.work.con,a,b,[(aa[l],bb[l]) for l in aa if l in ga],complete=True)
            if overlap.get('shared_distinct_groups',0) or overlap.get('blocked'):inference_allowed=False
        if spec.mode=='splits':summary.append(split_pair(e,spec,a,b,aa,bb,annotations))
        populated=[(l,x,bb[l]) for l,x in aa.items() if l in bb and (x in a.features or x in a.task.target_names) and (bb[l] in b.features or bb[l] in b.task.target_names)]
        selected_left={l for l,x in aa.items() if x in a.features or x in a.task.target_names};selected_right={l for l,y in bb.items() if y in b.features or y in b.task.target_names}
        excluded=sorted((selected_left|selected_right)-{l for l,x,y in populated})
        exclusions=[{'column':l,'reason':'missing_aligned_column' if l not in aa or l not in bb else 'not_selected_in_both_sources','left_role':column_role(a,aa[l]) if l in aa else 'absent','right_role':column_role(b,bb[l]) if l in bb else 'absent'} for l in excluded]
        if excluded:e.add(scope,'blocked_alignment',{'columns':excluded,'exclusions':exclusions,'reason':'missing_aligned_column_or_unselected_role','dependent_methods':['population_comparison','full_vector_comparison']},columns=excluded,blocked='Selected fields are absent or unselected in the other source; dependent definitions were not silently intersected. Feature/target transitions remain eligible for qualified marginal comparisons.')
        populations=distributions(e,a,b,populated,config,scope,inference_allowed=inference_allowed)
        populations['excluded_columns']=excluded
        populations['alignment_exclusions']=exclusions
        e.coverage[scope+'.populations'].update(excluded_columns=excluded,alignment_exclusions=exclusions)
        comparative_segments(e,spec,a,b,aa,bb,config,populated)
    tests=[t for key,v in e.measurements.items() if key.endswith('.populations') for t in v.get('tests',[])]
    ordered=sorted(tests,key=lambda t:t['p_value']);running=1.
    for i in range(len(ordered)-1,-1,-1):
        running=min(running,ordered[i]['p_value']*len(ordered)/(i+1));ordered[i]['adjusted_p_value']=running;ordered[i]['adjustment_scope']='all_successful_job_marginal_tests'
    # EXISTS computes each affected-row union explicitly, without adding pair counts.
    unions={};all_unions={}
    if spec.mode=='splits':
        for r in relations:
            ar=align[r.id];by_kind={kind:[] for kind in ('records','features','entity','group')}
            for other in relations:
                if other.id==r.id:continue
                ao=align[other.id]
                pair=next(v for key,v in e.measurements.items() if key in {r.id+':'+other.id+'.split_integrity',other.id+':'+r.id+'.split_integrity'})
                definitions=[('records',tuple(ar),False,pair['records']),('features',tuple(l for l,c in ar.items() if c in r.features),False,pair['features'])]
                definitions.extend((u['kind'],tuple(u['columns']),True,u) for u in pair['units'])
                for kind,names,complete,measurement in definitions:
                    if not names or measurement.get('blocked') or not set(names)<=set(ar)&set(ao):continue
                    cols=[(ar[l],ao[l]) for l in names]
                    join=' AND '.join(f'a.{r.col(x)} IS NOT DISTINCT FROM b.{other.col(y)}' for x,y in cols)
                    eligible=''
                    if complete:
                        eligible=' AND '+ ' AND '.join(f'a.{r.col(x)} IS NOT NULL AND b.{other.col(y)} IS NOT NULL'+(f' AND isfinite(a.{r.col(x)}) AND isfinite(b.{other.col(y)})' if r.types[x] in NUMERIC and other.types[y] in NUMERIC else '') for x,y in cols)
                    by_kind[kind].append(f'EXISTS(SELECT 1 FROM {other.table} b WHERE {join}{eligible})')
            all_unions[r.id]={kind:{'affected_rows':e.work.con.execute(f'SELECT count(*) FROM {r.table} a WHERE '+(' OR '.join(terms) or 'false')).fetchone()[0],'denominator':r.rows,'completed_definitions':len(terms)} for kind,terms in by_kind.items()}
            unions[r.id]=all_unions[r.id]['features']['affected_rows']
        e.add('comparison','overlap_row_unions',all_unions,population='source rows participating in at least one completed definition, separately by record, feature, entity and group equality')
    return {'mode':spec.mode,'source_pairs':len(pairs),'feature_overlap_row_unions':unions,'overlap_row_unions':all_unions}



def comparative_segments(e,spec,a,b,aa,bb,config,pairs):
    from dataclasses import replace
    con=e.work.con;mix=[];scope=a.id+':'+b.id;unsearched=0
    for declaration in config.advanced.segments:
        l=declaration.column
        if l not in aa or l not in bb:
            mix.append({'column':l,'blocked':'missing_aligned_segment_column'});continue
        x,y=aa[l],bb[l];ca,cb=a.col(x),b.col(y);params=[]
        if declaration.bins:
            if a.types[x] not in NUMERIC or b.types[y] not in NUMERIC or precision(con,a,x):
                mix.append({'column':l,'blocked':'unsafe_or_incompatible_reference_geometry'});continue
            edges=sorted(set(quantiles(con,a.table,ca,a.finite(x),tuple(i/declaration.bins for i in range(1,declaration.bins)))))
            def expression(c):return 'CASE '+''.join(f'WHEN {c}<=? THEN {i} ' for i in range(len(edges)))+f'ELSE {len(edges)} END'
            xa,xb=expression(ca),expression(cb);wa,wb=a.finite(x),b.finite(y);params=edges
        else:xa,xb=ca,cb;wa,wb=ca+' IS NOT NULL',cb+' IS NOT NULL';edges=None
        con.execute(f'CREATE OR REPLACE TEMP TABLE _segment_left AS SELECT _row,{xa} segment_value FROM {a.table} WHERE {wa}',params)
        con.execute(f'CREATE OR REPLACE TEMP TABLE _segment_right AS SELECT _row,{xb} segment_value FROM {b.table} WHERE {wb}',params)
        counts='WITH combined AS(SELECT segment_value,count(*) n,0::BIGINT m FROM _segment_left GROUP BY segment_value UNION ALL SELECT segment_value,0::BIGINT,count(*) FROM _segment_right GROUP BY segment_value),u AS(SELECT segment_value,sum(n) n,sum(m) m FROM combined GROUP BY segment_value)'
        na=con.execute('SELECT count(*) FROM _segment_left').fetchone()[0];nb=con.execute('SELECT count(*) FROM _segment_right').fetchone()[0]
        if not na or not nb:mix.append({'column':l,'blocked':'empty_observed_segment_population'});continue
        tv,total=con.execute(counts+' SELECT .5*sum(abs(n/?-m/?)),count(*) FROM u',[na,nb]).fetchone()
        select=counts+' SELECT segment_value,n,m FROM u'+(' WHERE segment_value IN (SELECT unnest(?))' if declaration.categories else '')+' ORDER BY greatest(n,m) DESC,segment_value LIMIT 32'
        levels=con.execute(select,[list(declaration.categories)] if declaration.categories else []).fetchall()
        mix.append({'column':l,'reference_bin_edges':edges,'left_observed':na,'right_observed':nb,'left_excluded':a.rows-na,'right_excluded':b.rows-nb,'total_variation':tv,'levels':[{'level':v,'left_count':int(n),'right_count':int(m)} for v,n,m in levels],'omitted_levels':max(0,total-len(levels)),'left_residual':na-sum(n for v,n,m in levels),'right_residual':nb-sum(m for v,n,m in levels)})
        for segment_value,n,m in levels:
            if not n or not m:continue
            remaining=config.advanced.max_segment_checks-e.segment_checks
            if remaining<=0 or not e.claim(int(n+m)*min(len(pairs),remaining)):
                unsearched+=len(pairs);continue
            selected=pairs[:remaining];unsearched+=max(0,len(pairs)-len(selected));e.segment_checks+=len(selected)
            con.execute(f'CREATE OR REPLACE TEMP TABLE _conditional_left AS SELECT * FROM {a.table} WHERE _row IN (SELECT _row FROM _segment_left WHERE segment_value IS NOT DISTINCT FROM ?)',[segment_value])
            con.execute(f'CREATE OR REPLACE TEMP TABLE _conditional_right AS SELECT * FROM {b.table} WHERE _row IN (SELECT _row FROM _segment_right WHERE segment_value IS NOT DISTINCT FROM ?)',[segment_value])
            ar=replace(a,table='_conditional_left',rows=int(n));br=replace(b,table='_conditional_right',rows=int(m))
            # The scope uses a numbered population, avoiding raw identifier values in findings.
            population_scope=scope+f':segment{len(mix)}:segment_value{levels.index((segment_value,n,m))+1}'
            distributions(e,ar,br,selected,config,population_scope,conditional=True,inference_allowed=False)
    if mix:e.add(scope,'segment_mix',{'declarations':mix,'unsearched_segment_measurements':unsearched,'completed_job_segment_measurements':e.segment_checks,'stopping_reason':'planned_bounds' if unsearched else 'complete'},columns=[d.column for d in config.advanced.segments],population='declared segment mix; within-segment populations remain separate')
