"""Stakeholder prose over immutable counts; detailed evidence remains in JSON."""
LABELS={'satisfied':'Agreements','violated':'Discrepancies','conflicting_evidence':'Conflicting supplied evidence','inconclusive':'Unresolved comparisons','unassessed':'Assigned to optional investigation','support_candidate':'Possible support','contradiction_candidate':'Possible contradiction','mixed_evidence':'Competing support and contradiction','misassociation_candidate':'Possible image misassociation','compatibility_candidate':'Possible image–text compatibility','abstained':'No model judgment','missing_logical_identity':'Missing logical identity','duplicate_logical_identity':'Repeated logical identity','invalid_source_record':'Unreadable or invalid source record','exact_literal_containment':'Exact text repeated within supplied evidence','perceptual_image_similarity':'Images look similar; inspect before deciding'}


def label(value):
    return LABELS.get(value,value.replace('_',' ').capitalize())


def population_label(value):
    prefix,_,number=value.rpartition('_')
    return {'source':'Source','relationship':'Relationship','context':'Context check','rule':'Reconciliation','separation':'Separation requirement'}.get(prefix,'Optional investigations')+((' '+number) if number.isdecimal() else '')


def summary(result):
    n=len(result.findings)
    return f'This review identified {n:,} topics for investigation across the supplied sources.' if n else 'No concerns were identified in the completed checks. Unexamined and unresolved evidence still require attention.'


def explanation(family,c):
    n=lambda k:f'{c.get(k,0):,}'
    if family=='identities':
        text=f"Reviewed {n('records')} source records: {n('invalid_keys_total')} have no usable logical identity and {n('cardinality_violations')} identity groups repeat."
        if c.get('invalid_records'): text+=f" {n('invalid_records')} records could not be read reliably."
    elif family=='relationships':
        text=f"Resolved {n('associations')} declared associations. {n('required_gap')} left-side records lack required evidence; {n('inverse_gap')} right-side records lack a required counterpart."
        if c.get('cardinality_violations') or c.get('normalization_collisions'): text+=f" {n('cardinality_violations')} key groups violate the declared uniqueness rules and {n('normalization_collisions')} normalized groups combine distinct original identities."
        if c.get('invalid_keys_total') or c.get('invalid_association_rows'): text+=f" {n('invalid_keys_total')} endpoint records have unusable keys; {n('invalid_association_rows')} association rows contain unusable or unresolved endpoints."
        if c.get('duplicate_association_rows'): text+=f" {n('duplicate_association_rows')} repeated association rows were deduplicated."
    elif family=='context':
        text=f"Checked {n('associations')} associations against declared entity, period and timing context. {n('violated')} were excluded and {n('inconclusive')} have unresolved context; these counts can overlap."
    elif family=='reconciliation':
        text=f"Of {n('records')} records, {n('satisfied')} agree, {n('violated')} disagree, {n('conflicting_evidence')} have competing document values, and {n('inconclusive')} cannot be resolved."
        if c.get('unassessed'): text+=f" {n('unassessed')} records are assigned to optional model investigation."
        if c.get('incomplete_records'): text+=f" Evidence discovery is incomplete for {n('incomplete_records')} records."
    elif family=='separation':
        text=f"Found {n('shared_units')} distinct exact overlap keys, affecting {n('left_affected_records')} left-side and {n('right_affected_records')} right-side records. Each record is counted once per side."
        text+=' The declared separation requirement is violated.' if c.get('status')=='violated' else ' The declared requirement remains unresolved.' if c.get('status')=='inconclusive' else 'Permitted overlap is descriptive; no required separation violation was observed.'
        if c.get('investigation_candidates'): text+=f" {n('investigation_candidates')} visually similar image pairs require review and do not establish a violation."
        if c.get('candidate_coverage',{}).get('bounded'): text+=' The additional passage or image investigation reached its bounded scope; it cannot establish absence across all sources.'
    else:
        text=' '.join(f'{label(k)}: {v:,}.' for k,v in c.items() if isinstance(v,int) and not isinstance(v,bool) and k in LABELS)
        text+=' Model findings concern examined evidence and require human interpretation.'
    return text


SECTION_IDS={'identities':'identities','relationships':'associations','context':'cross_context','reconciliation':'reconciliation','separation':'separation','models':'models'}


def report_view(result,profile_name='focused'):
    import copy
    from datatrust.report_structured import capped_tables,has_references,labelled
    r=copy.deepcopy(result.to_dict());sections=[];described=[];index={e['id']:i for i,e in enumerate(r['evidence'])}
    for family,title in [('identities','Source logical identities'),('relationships','Identity and association integrity'),('context','Declared entity, version and timing context'),('reconciliation','Reconciliation and conflicting evidence'),('separation','Cross-source contamination'),('models','Optional semantic investigations')]:
        blocks=[]
        for e in r['evidence']:
            if e['family']!=family: continue
            counts={k:v for k,v in e['data'].items() if k not in {'details','candidates'} and not isinstance(v,(dict,list))}
            details=e['data'].get('details',[])[:5]
            for d in details: d['description']=label(d.get('reason') or d.get('status','Retained source example'))
            i=index[e['id']]
            block={'population':e['population'],'title':population_label(e['population']),'explanation':explanation(family,e['data']),'counts':{label(k):v for k,v in counts.items()},'details':details,'omitted':max(0,len(e['data'].get('details',[]))-len(details)),
                   'anchor':f'ev-{i}','disclosures':[]}
            for key in ('details','candidates'):
                items=e['data'].get(key) or []
                if len(items)>(5 if key=='details' else 0):
                    rows=[[str(d.get('target_id') or d.get('reference') or n+1),label(d.get('reason') or d.get('status') or 'retained example'),labelled({k:v for k,v in d.items() if k not in {'target_id','description'}})] for n,d in enumerate(items)]
                    described.append({'title':f"{block['title']} · {title} · retained {key}",'columns':['Review reference','Outcome','Recorded detail'],'rows':rows[:5 if key=='details' else 0],'all_rows':rows,
                                      'topic':f"{e['id']}-{key}",'noun':'retained examples','pointer':f'/evidence/{i}/data/{key}','protected':True,'block':block})
            nested=[[k.replace('_',' '),labelled(v)] for k,v in e['data'].items() if k not in {'details','candidates'} and isinstance(v,(dict,list))]
            if nested:
                described.append({'title':f"{block['title']} · {title} · nested measurements",'columns':['Field','Recorded value'],'rows':[],'all_rows':nested,
                                  'topic':f"{e['id']}-nested",'noun':'fields','pointer':f'/evidence/{i}/data','protected':has_references(nested),'block':block})
            blocks.append(block)
        sections.append({'id':SECTION_IDS[family],'title':title,'blocks':blocks})
    ordered=sorted(enumerate(r['findings']),key=lambda x:{'High':0,'Moderate':1}.get(x[1]['priority'],2))
    actions=[{**f,'anchor':f'finding-{n}','explanation':explanation(f['family'],f['counts']),'population_title':population_label(f['population'])} for n,f in ordered[:5]]
    carded={a['anchor'] for a in actions}
    findings=[{'anchor':f'finding-{n}' if f'finding-{n}' in carded else None,'index':n,'title':f['title'],'severity':f['priority'],
               'effect':population_label(f['population'])+' · '+str(f['family']).replace('_',' ')} for n,f in enumerate(r['findings'])]
    coverage={k:v for k,v in r['coverage'].items() if k!='document_extraction'}
    docs=r['coverage'].get('document_extraction',[])
    from collections import Counter
    coverage['document_extraction']={'documents':len(docs),'states':dict(Counter(x['state'] for x in docs)),'processed_units':sum(x.get('processed',0) for x in docs),'text_free_pages':sum(x.get('text_free',0) for x in docs),'detail':'Per-document coverage remains in strict JSON.'}
    scope=[f"The audit admitted {r['profile']['source_count']:,} sources and {r['profile']['records']:,} source records, including manifest rows.",f"Document and text extraction covered {len(docs):,} document/settings entries and {coverage['document_extraction']['processed_units']:,} pages or document blocks; {coverage['document_extraction']['text_free_pages']:,} pages contained no usable native text."]
    for pop,c in r['coverage'].get('model_selection',{}).items(): scope.append(f"{population_label(pop)}: selected {c['selected']:,} of {c['population']:,} records for optional investigation; {c['not_selected']:,} were not selected.")
    for state,count in coverage['document_extraction']['states'].items():
        if state!='processed': scope.append(f"{count:,} extraction entries require attention ({label(state).lower()}).")
    model_state=r['coverage'].get('models',{}).get('status')
    if model_state in {'bounded','failed'}: scope.append('Optional model work stopped at its allocation.' if model_state=='bounded' else 'Optional model work failed; only the verified deterministic evidence was retained.')
    limitations={'disclosures':[]}
    rest=[[k.replace('_',' '),labelled(v)] for k,v in r['coverage'].items() if k!='document_extraction']
    if rest:
        described.append({'title':'Coverage','columns':['Coverage family','Recorded coverage'],'rows':[],'all_rows':rest,'topic':'coverage','noun':'coverage families',
                          'pointer':'/coverage','protected':has_references(rest),'block':limitations})
    if docs:
        rows=[[str(n+1),label(x.get('state','')),labelled({k:v for k,v in x.items() if k!='state'})] for n,x in enumerate(docs)]
        described.append({'title':'Document extraction coverage','columns':['Entry','State','Recorded coverage'],'rows':[],'all_rows':rows,'topic':'document-extraction',
                          'noun':'document entries','pointer':'/coverage/document_extraction','protected':True,'block':limitations})
    disclosures,complete=capped_tables(described,profile_name,limit_label='summary selection',section_label='Complete retained evidence')
    for table in described:
        if table['topic'] in disclosures:table['block']['disclosures'].append(disclosures[table['topic']])
    execution=[('Completion',label(r['execution']['status'])),('Elapsed time',f"{r['execution'].get('whole_job_seconds',r['execution'].get('duration_seconds',0)):.1f} seconds"),('Peak sampled worker memory',f"{r['execution'].get('peak_worker_rss_bytes',0)/1024**2:.1f} MiB"),('Peak temporary workspace',f"{r['execution'].get('peak_workspace_bytes',0)/1024**2:.1f} MiB")]
    return {'findings':findings,'disclosures':disclosures,'complete_tables':complete,'profile':profile_name,'limitation_disclosures':limitations['disclosures'],
            'qa':{'schema_version':'1.7','print_profile':profile_name,'retained_evidence_not_recomputed':True},
            'summary':summary(result),'actions':actions,'omitted_actions':max(0,len(r['findings'])-5),'sections':sections,'scope':scope,'execution':execution,'coverage':coverage,'examples':r['profile'].get('examples',[]),'target_labels':{id:label(t.get('semantic',{}).get('status') or t.get('detail',{}).get('reason') or t.get('detail',{}).get('status') or t['kind']) for id,t in r['profile']['review_targets'].items()}}
