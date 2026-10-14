"""One bounded projection for canonical HTML and PDF. No analytics at render time."""
TOPICS=(
 ('Summary and actionability',()),
 ('Corpus integrity',('invalidity','identities','corpus')),
 ('Duplication and passages',('exact_duplicates','near_duplicates','passages','repetition')),
 ('Tokens and annotations',('annotations','annotation_categories','annotation_disagreement','vocabulary','tokenizer_vocabulary')),
 ('Conversations',('conversations',)),
 ('Retrieval and provenance',('retrieval',)),
 ('Comparisons and model evidence',('comparisons','version_alignment','lexical_comparison','language','semantic_similarity')),
 ('Methods and coverage',()),
)


def display(value):
    if value is None:return 'Unavailable'
    if isinstance(value,bool):return 'Yes' if value else 'No'
    if isinstance(value,float):return f'{value:,.6g}'
    if isinstance(value,int):return f'{value:,}'
    if isinstance(value,str):return value
    if isinstance(value,dict):
        entries=list(value.items())
        return '; '.join(f'{str(k).replace("_"," ")}: {display(v)}' for k,v in entries[:5])+(f'; {len(entries)-5} further entries in JSON' if len(entries)>5 else '')
    return '; '.join(display(x) for x in value[:5])+(f'; {len(value)-5} further entries in JSON' if len(value)>5 else '')


def executive_summary(value):
    """Synthesize completed evidence; never sum overlapping representation findings."""
    evidence={x['id']:x for x in value['evidence']};groups={}
    order={'deterministic_violation':0,'contextual_observation':1,'heuristic_candidate':2,'model_assisted_candidate':3}
    for finding in value['findings']:
        key=(finding['family'],finding['meaning'],finding['action'])
        group=groups.setdefault(key,{'family':key[0],'meaning':key[1],'action':key[2],'evidence_ids':[],'observations':[],'scopes':[]})
        record=evidence[finding['id']];data=record['data'];group['evidence_ids'].append(record['id'])
        label=data.get('representation') or record['scope'].replace('_',' ')
        unit='groups' if finding['family']=='exact_duplicates' else 'pairs' if finding['family']=='near_duplicates' else 'items' if finding['family']=='invalidity' else 'observations'
        group['observations'].append(f"{label}: {finding['count']:,} {unit}")
        if record['scope'] not in group['scopes']:group['scopes'].append(record['scope'])
    actions=sorted(groups.values(),key=lambda x:(order.get(x['meaning'],4),x['family']))
    populations=value['profile'].get('source_populations',{})
    framed=sum(x['records'] for x in populations.values());invalid=sum(x['invalid_records'] for x in populations.values())
    corpus=next((x['data'] for x in value['evidence'] if x['family']=='corpus'),{})
    invalidity=next((x['data'] for x in value['evidence'] if x['family']=='invalidity'),{})
    families=value['coverage'].get('families',{});lexical=families.get('lexical_selection',{});semantic=families.get('semantic_similarity')
    scope=[f"Required checks accounted for {framed:,} framed records; {invalid:,} invalid records remain in the population."]
    if lexical:scope.append(f"Lexical selection examined {lexical['selected_population']:,} of {lexical['eligible_population']:,} eligible units; each investigation has its own additional work limits.")
    if semantic:scope.append(f"Semantic investigation embedded {semantic['embedded_parents']:,} of {semantic['eligible_parents']:,} eligible parents in {semantic['embedded_windows']:,} windows; segment similarity does not establish document equivalence.")
    blocked=[x['family'] for x in value['checks'] if x['applicability']=='blocked']
    if blocked:scope.append('Blocked checks: '+', '.join(dict.fromkeys(blocked))+'.')
    summary=f"{len(actions)} review actions across {len(value['findings'])} technical findings. Required checks retain invalidity; bounded searches disclose their examined scope."
    return {'summary':summary,'actions':actions,'technical_findings':len(value['findings']),'framed_records':framed,'invalid_records':invalid,
        'invalid_items':invalidity.get('invalid_items',0),'content_units':corpus.get('content_units',0),'content_states':display(corpus.get('states',{})),
        'scope':scope,'action_omissions':max(0,len(actions)-5),'duplicate_counts_are_additive':False}


def report_view(result):
    value=result.to_dict();sections=[];checks={x['id']:x for x in value['checks']}
    for title,families in TOPICS:
        records=[]
        for record in value['evidence']:
            if record['family'] not in families:continue
            hidden={'details','neighbors','parent_coverage'}
            rows=[(k.replace('_',' ').capitalize(),display(v)) for k,v in record['data'].items() if k not in hidden]
            details=[]
            for key in ('details','neighbors','parent_coverage'):
                items=record['data'].get(key,[])
                if key=='neighbors' and items:
                    examples=[]
                    for item in items[:2]:
                        window=item['window'];neighbors=item['neighbors'][:2]
                        examples.append(f"{window['reference']} characters {window['source_span']} → "+'; '.join(f"{n['window']['reference']} characters {n['window']['source_span']}, cosine {n['cosine']:.6g}" for n in neighbors))
                    details.append(('Examined segment neighbors','; '.join(examples)))
                elif items:details.append((key.replace('_',' ').capitalize(),display(items[:2])))
            records.append(record|{'rows':rows,'visible_details':details,'applicability':checks[record['id']]['applicability']})
        compact=bool(records) and all(x['applicability']=='not_applicable' for x in records)
        sections.append({'title':title,'records':records,'compact':compact})
    coverage=[]
    base=value['coverage']['families'].get('lexical_selection',{})
    for family,data in value['coverage']['families'].items():
        entries={k:v for k,v in data.items() if k not in {'selected_strata','profile'} and (family=='lexical_selection' or k not in base or v!=base[k])}
        if 'selected_strata' in data and family=='lexical_selection':entries['retained_selected_strata']=len(data['selected_strata'])
        if 'selected_strata' in data and family!='lexical_selection':
            entries['population_and_selection']='Same selected strata as lexical selection; additional method exclusions are listed here' if data['selected_strata']==base.get('selected_strata') else f"This family selected {len(data['selected_strata'])} strata independently; exact allocations remain in JSON"
        if 'profile' in data:entries['candidate_profile']=f"{data['profile']['bands']} bands × {data['profile']['rows']} rows; bucket cap {data['profile']['bucket_cap']}; calibration applies only to recorded fixtures"
        coverage.append({'family':family,'rows':[(k.replace('_',' ').capitalize(),display(v)) for k,v in entries.items()]})
    execution={k:v for k,v in value['execution'].items() if k not in {'effective_limits','text_limits','provenance','warnings'}}
    return {'sections':sections,'executive':executive_summary(value),'coverage':coverage,'execution':[(k.replace('_',' ').capitalize(),display(v)) for k,v in execution.items()],'qa':{'analytical_topics':8,'pages_cut_to_budget':False,'target_executive_pages':2,'target_total_pages':12,'raw_content_default':False,'coverage_separate_from_invalidity':True}}
