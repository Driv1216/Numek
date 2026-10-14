"""Decision-led projections of completed M7 evidence, never reanalysis."""

TOPICS=[('inventory','Inventory'),('decode','Decode and representations'),('visual','Visual evidence'),('annotations','Annotation integrity'),('composition','Dataset composition'),('duplicates','Duplication candidates'),('comparison','Split and version comparisons'),('coverage','Methods and coverage')]


def display(value):
    if value is None: return 'Unavailable'
    if isinstance(value,bool): return 'Yes' if value else 'No'
    if isinstance(value,float): return format(value,'.5g')
    return str(value)


def detail_lines(value,limit=10,*,scalars_first=False):
    """Flatten nested technical fields into bounded, separately readable lines."""
    lines=[]
    def visit(item,prefix=''):
        if isinstance(item,dict):
            if not item: lines.append((prefix,'None observed'))
            pairs=item.items()
            if scalars_first: pairs=sorted(pairs,key=lambda kv:isinstance(kv[1],(list,dict)))
            for k,v in pairs: visit(v,(prefix+' / ' if prefix else '')+str(k).replace('_',' '))
        elif isinstance(item,list):
            if not item: lines.append((prefix,'None retained'))
            for n,v in enumerate(item): visit(v,(prefix+' / ' if prefix else '')+str(n+1))
        else: lines.append((prefix,display(item)))
    visit(value)
    retained=[{'label':k,'value':v[:240]+(' ...' if len(v)>240 else '')} for k,v in lines[:limit]]
    return retained,max(0,len(lines)-limit)+sum(len(v)>240 for k,v in lines[:limit])


def executive_actions(data):
    """Group decisions by consequence, without scoring dataset reliability.

    Counts retain their original units; reason/rule counts are not presented as
    unique images. Repeated raster representations do not crowd out blockers.
    """
    families={}
    for record in data['evidence']: families.setdefault(record['family'],[]).append(record['data'])
    actions=[]
    def add(title,facts,action,meaning):
        if facts: actions.append({'title':title,'facts':facts,'action':action,'meaning':meaning})
    def values(family): return families.get(family,[])
    facts=[]
    for d in values('decode'):
        n=sum(d.get('asset_states',{}).get(k,0) for k in ('corrupt_or_truncated','unreadable'))
        if n: facts.append(f'{n} image locations could not be decoded.')
    for d in values('logical_identity'):
        if d.get('occurrences_with_duplicate_source_keys'): facts.append(f"{d['occurrences_with_duplicate_source_keys']} occurrences have ambiguous logical keys.")
    source_reasons={'source_unavailable','unsafe_or_unavailable_source','out_of_root','unsafe_path','not_regular_file','invalid_asset_reference','invalid_split','supplied_checksum_mismatch'}
    reasons={}
    for d in values('annotations'):
        for k,v in d.get('invalidity_reasons',{}).items():
            if k in source_reasons: reasons[k]=reasons.get(k,0)+v
    if reasons: facts.append(f"{sum(reasons.values())} source/reference diagnostic reasons need resolution.")
    add('Resolve source and identity problems',facts,'Inspect the retained local references, repair the declared sources or keys, then re-audit. Dependent comparisons cannot establish a clean result.','deterministic facts')
    facts=[]
    for d in values('split_requirements'):
        if d.get('asset_separation_required') and d.get('exact_asset_overlap_occurrences'): facts.append(f"{d['exact_asset_overlap_occurrences']} left-side occurrences repeat exact bytes across a declared separation.")
        if d.get('group_separation_required'):
            n=d.get('declared_group_overlap_occurrences',d.get('complete_declared_group_overlap_occurrences',0))
            if n: facts.append(f"{n} left-side occurrences share declared groups ({d.get('group_mode','composite')} matching).")
            if d.get('group_separation_applicability')!='applicable': facts.append('Group separation has missing values or unresolved key/namespace populations; inspect its disclosed scope.')
    add('Resolve declared split separation',facts,'Review the overlapping asset/group membership and revise the split assignment or declaration. This evidence does not prove training exposure or evaluation inflation.','declared requirements')
    facts=[]
    for d in values('annotations'):
        v=d.get('validity',{}); n=v.get('invalid',0)+v.get('partial',0)
        if n: facts.append(f'{n} occurrences have invalid or partially valid annotations; reason counts can overlap.')
        if d.get('blocked_geometric_checks'): facts.append('Some geometric checks are blocked; source views do not establish aligned annotation agreement.')
    for d in values('annotation_disagreement'):
        if d.get('compatible_exact_raster_groups_with_differences'): facts.append(f"{d['compatible_exact_raster_groups_with_differences']} exact-raster groups have compatible normalized annotation differences.")
        if d.get('payload_difference_groups_blocked'): facts.append(f"{d['payload_difference_groups_blocked']} differing annotation groups cannot be geometrically compared.")
    add('Review annotation integrity',facts,'Inspect supplied states, taxonomy and coordinate frames. Correct declared violations; adjudicate compatible differences locally. The audit does not identify the correct label.','facts and compatible differences')
    facts=[]
    for d in values('versions'):
        if d.get('alignment')=='blocked': facts.append('Version alignment is blocked; only population and exact-content overlap are available.')
        c=d.get('changes',{})
        if c.get('annotation_payload_changes_blocked'): facts.append(f"{c['annotation_payload_changes_blocked']} changed annotation comparisons are blocked by compatibility.")
        if c.get('compatible_annotation_changes'): facts.append(f"{c['compatible_annotation_changes']} aligned occurrences have compatible annotation changes.")
        if c.get('byte_changes'): facts.append(f"{c['byte_changes']} aligned occurrences have changed image bytes.")
        if d.get('added') or d.get('removed'): facts.append(f"{d.get('added',0)} occurrences added; {d.get('removed',0)} removed under explicit logical alignment.")
    if data['execution'].get('status')=='partial': facts.append('Optional model evidence failed; only verified core evidence is available.')
    near=data.get('coverage',{}).get('families',{}).get('near_duplicates',{})
    if near.get('stop_reason') and near['stop_reason']!='examined_scope_completed': facts.append('Similarity search reached a planned bound; unexamined search is not a negative result.')
    add('Resolve comparison and coverage limits',facts,'Review the aligned changes and blocked populations. Supply compatible declarations where possible, or explicitly accept the bounded scope before making a dataset decision.','changes and coverage boundaries')
    facts=[]
    for d in values('quality_expectations'):
        if d.get('declared_violations'): facts.append(f"{sum(d['declared_violations'].values())} explicit visual-quality rule violations (not unique-image counts).")
    for name,key,wording in [('near_duplicates','qualifying_raster_pairs','perceptual raster pairs'),('embeddings',None,'retained model pairs'),('exact_duplicates_bytes','cross_split_occurrences','cross-split occurrences with exact byte repetition')]:
        for d in values(name):
            n=len(d.get('candidates',[])) if key is None else d.get(key,0)
            if n: facts.append(f'{n} {wording} are available for investigation.')
    add('Investigate visual and repetition evidence',facts,'Apply explicit quality expectations separately from similarity candidates. Inspect examples locally; similarity alone proves neither leakage nor an incorrect label.','declared quality rules and review candidates')
    return actions


def report_view(result):
    data=result.to_dict(); sections=[]; omitted=0
    checks={c['id']:c for c in data['checks']}
    for key,title in TOPICS:
        def matches(family):
            if key=='duplicates': return family.startswith(('exact_duplicates','near_duplicates','embeddings','annotation_disagreement'))
            if key=='comparison': return family.startswith(('split','versions','logical'))
            if key=='visual': return family in {'visual_quality','visual_extremes','quality_expectations'}
            if key=='composition': return family in {'composition','multilabel_composition'}
            return key!='coverage' and family.startswith(key)
        blocks=[]
        for record in [r for r in data['evidence'] if matches(r['family'])]:
            rows=[]; hidden=0
            for name,value in record['data'].items():
                if name in {'quality_score','examples','details','candidates'}: continue
                if name=='metrics' and isinstance(value,dict):
                    for metric,summary in value.items():
                        lines,n=detail_lines(summary); hidden+=n; rows.append({'label':metric.replace('_',' '),'lines':lines})
                else:
                    lines,n=detail_lines(value,20 if name=='group_keys' else 10); hidden+=n; rows.append({'label':name.replace('_',' '),'lines':lines})
            hidden+=max(0,len(rows)-20); omitted+=hidden
            c=checks.get(record['id'],{}); d=record['data']
            state='Blocked' if c.get('applicability')=='blocked' or d.get('group_separation_applicability')=='blocked' or d.get('blocked_geometric_checks') else 'Review' if c.get('violations') else 'Bounded' if record.get('scope')=='bounded' else 'Examined'
            blocks.append({'title':record['family'].replace('_',' '),'meaning':record['meaning'].replace('_',' '),'state':state,'rows':rows[:20],'omitted':hidden})
        if key=='coverage':
            rows=[]
            boundaries={'execution':data['execution']['status'],'source integrity':'Verified per-file bytes and membership; no atomic filesystem snapshot.','search interpretation':'Bounded candidates do not establish global absence, leakage or annotation correctness.'}
            for family,cov in [*boundaries.items(),*data['coverage']['families'].items()]:
                # Keep stop reasons, query counts and scope claims ahead of nested
                # witnesses; a presentation cap must not hide search semantics.
                lines,n=detail_lines(cov,24,scalars_first=True); omitted+=n
                rows.append({'label':family.replace('_',' '),'lines':lines,'omitted':n})
            blocks=[{'title':'Population and search coverage','meaning':'method and execution boundaries','state':'Partial' if data['execution']['status']=='partial' else 'Bounded','rows':rows,'omitted':0}]
            for record in data['evidence']:
                if record['family']=='embeddings':
                    model=record['data'].get('model',{})
                    benchmark=model.get('review_evidence',{})
                    if not benchmark:
                        # Older completed audits carry the same pinned encoder but
                        # precede interpretation metadata. Project its recorded
                        # benchmark without changing or re-running their evidence.
                        from datatrust.image_models import registry,MODELS
                        pinned=registry()
                        if model.get('model')==pinned['selection']['default']['model'] and model.get('revision')==MODELS.get(model.get('model')):
                            benchmark=pinned.get('review_evidence',{})
                    if benchmark:
                        blocks.append({'title':'Model benchmark interpretation','meaning':'fixed-fixture evidence, not universal matching quality','state':'Review','rows':[{'label':'Encoder versus pipeline','lines':[{'label':'Encoder calibration precision','value':format(benchmark['encoder_calibration']['precision'],'.2%')},{'label':'Encoder held-out precision','value':format(benchmark['encoder_held_out']['precision'],'.2%')},{'label':'Combined pipeline held-out precision','value':format(benchmark['combined_pipeline_held_out']['precision'],'.2%')},{'label':'90% combined precision target','value':'Not met'},{'label':'Scope','value':benchmark['scope']}]}],'omitted':0})
        sections.append({'title':title,'blocks':blocks})
    return {'sections':sections,'actions':executive_actions(data),'examples':data['profile'].get('examples',[]),'qa':{'presentation_rows_omitted':omitted,'presentation_rows_or_details_omitted':omitted,'topics':8,'maximum_actions':5,'retained_evidence_not_recomputed':True}}
