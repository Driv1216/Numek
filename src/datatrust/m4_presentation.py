"""Bounded human projection; JSON keeps every retained computed record."""
from dataclasses import asdict


POINTERS={'sources':'/profile','features':'/profile','targets':'/profile','overlap':'/coverage/measurements','schema':'/coverage/measurements',
          'effects':'/coverage/measurements','advanced':'/coverage/measurements','coverage':'/coverage/diagnostics'}
TITLES={'sources':'Sources','features':'Feature populations','targets':'Target populations','overlap':'Overlap','schema':'Schema changes',
        'effects':'Population effects','advanced':'Advanced diagnostics','coverage':'Retained scope and coverage'}
RANK={'High':0,'Moderate':1,'Low':2}


def _signal_findings(value):
    """{(scope, column): finding}: the highest-priority recorded finding whose evidence lists that column, the first in
    recorded order on ties."""
    evidence={e.get('id'):e for e in value.get('evidence',[]) if isinstance(e,dict)}
    out={}
    for finding in value.get('findings',[]):
        rank=RANK.get(finding.get('priority'),3)
        for ref in finding.get('evidence_refs') or []:
            record=evidence.get(ref) or {}
            columns=record.get('affected_columns')
            if not isinstance(columns,list):
                continue
            scopes=list(record.get('source_ids') or [])+([':'.join(record['source_pair'])] if record.get('source_pair') else [])
            for scope in scopes:
                for column in columns:
                    if (scope,column) not in out or rank<RANK.get(out[(scope,column)].get('priority'),3):
                        out[(scope,column)]=finding
    return out


def _signals(value):
    """{(scope, column): rank} from each finding's evidence records whose affected columns are recorded as a list."""
    evidence={e.get('id'):e for e in value.get('evidence',[]) if isinstance(e,dict)}
    out={}
    for finding in value.get('findings',[]):
        rank=RANK.get(finding.get('priority'),3)
        for ref in finding.get('evidence_refs') or []:
            record=evidence.get(ref) or {}
            columns=record.get('affected_columns')
            if not isinstance(columns,list):
                continue
            scopes=list(record.get('source_ids') or [])+([':'.join(record['source_pair'])] if record.get('source_pair') else [])
            for scope in scopes:
                for column in columns:
                    out[(scope,column)]=min(out.get((scope,column),3),rank)
    return out


def report_view(result,profile_name='focused'):
    value=result.to_dict();limits=value['context'].get('presentation',{})
    bound=lambda key,default:limits.get(key,default)
    measurements=value['coverage']['measurements'];comparison=hasattr(result,'inputs')
    sources=value['profile']['sources'] if comparison else {'dataset':value['profile']}
    source_rows=[];features=[];targets=[];overlap=[];schemas=[];effects=[];other=[];coverage=[]
    for scope,p in sources.items():
        source_rows.append({'source':scope,'rows':p['row_count'],'columns':p['column_count'],'sha256':p['source']['sha256'],'task':p['declarations']['task']['kind']})
        for c in p['columns']:
            row={'source':scope,'column':c['name'],'role':c['role'],'storage':c['dtype'],'missing':c['missing_count'],'missing_percent':round(c['missing_rate'],2),'nonfinite':c['nonfinite_count'],'distinct':c['unique_count']}
            (targets if c['role']=='target' else features).append(row)
    for key,m in measurements.items():
        if key.endswith('.split_integrity'):
            for name in ('records','features'):
                d=m[name];overlap.append({'pair':key.rsplit('.',1)[0],'definition':name,'shared_groups':d.get('shared_distinct_groups'),'left_rows':d.get('left_rows'),'right_rows':d.get('right_rows'),'multiset':d.get('multiset_intersection'),'excluded_left':d.get('excluded_left'),'excluded_right':d.get('excluded_right'),'block':d.get('blocked')})
            for d in m['units']:overlap.append({'pair':key.rsplit('.',1)[0],'definition':d['kind']+' '+', '.join(d['columns']),'shared_groups':d.get('shared_distinct_groups'),'left_rows':d.get('left_rows'),'right_rows':d.get('right_rows'),'multiset':d.get('multiset_intersection'),'excluded_left':d.get('excluded_left'),'excluded_right':d.get('excluded_right'),'block':d.get('blocked')})
        elif key.endswith('.schema'):schemas.append({'pair':key.rsplit('.',1)[0],'added':', '.join(m['added']) or 'None','removed':', '.join(m['removed']) or 'None','storage_or_role_changes':len(m['changes'])})
        elif key.endswith('.populations'):
            for d in m['columns']:
                effects.append({'pair':key.rsplit('.',1)[0],'column':d['column'],'left_rows':d['left_rows'],'right_rows':d['right_rows'],'missing_change_pp':round(100*d['missingness_change'],3),'nonfinite_change_pp':round(100*d['nonfinite_change'],3) if 'nonfinite_change' in d else None,'TV':d.get('total_variation'),'CDF':d.get('cdf_distance'),'Wasserstein_1':d.get('wasserstein_1'),'block':d.get('distribution_block')})
        elif key.endswith(('.constraints','.multilabel','.arithmetic_relationships','.missingness_structure','.dependencies','.segments','.segment_mix','.unsupervised_readiness')):
            other.append({'scope':key,'affected_union':m.get('affected_row_union',m.get('constraint_row_union',m.get('review_affected_row_union',m.get('iqr_candidate_row_union')))),'retained_details':len(m.get('declarations',m.get('pairs',m.get('comparisons',m.get('relationships',m.get('patterns',[])))))),'unsearched':m.get('unsearched_pairs',m.get('unsearched_candidates',len(m.get('unsearched',[])))),'stopping_reason':m.get('stopping_reason','complete')})
        excluded=m.get('excluded_columns',m.get('excluded_features',m.get('excluded_targets',[])))
        shown=', '.join(c[:64]+('…' if len(c)>64 else '') for c in excluded[:3])
        if len(excluded)>3:shown+=f'; {len(excluded)-3} more excluded columns in JSON'
        coverage.append({'check':key,'status':value['coverage']['diagnostics'][key]['status'],'population':value['coverage']['diagnostics'][key]['population'],'unsearched':m.get('unsearched_pairs',m.get('unsearched_candidates',len(m.get('unsearched',[])))),'excluded_columns':shown})
    tables={'sources':source_rows,'features':features,'targets':targets,'overlap':overlap,'schema':schemas,'effects':effects,'advanced':other,'coverage':coverage}
    for key,c in value['coverage']['diagnostics'].items():
        if key not in measurements: coverage.append({'check':key,'status':c['status'],'population':c['population'],'unsearched':None,'excluded_columns':c.get('reason','')})
    # Signal-first order within each capped table (plan G.5: the order changes; the limit keeps its meaning).
    signals=_signals(value)
    def rank(row):
        scope=row.get('source',row.get('pair'));column=row.get('column')
        return signals.get((scope,column),3) if column is not None else 3
    for name in ('features','targets','effects'):
        tables[name]=sorted(tables[name],key=rank)
    bounds={'sources':3,'features':bound('feature_details',20),'targets':bound('target_panels',6),'coverage':bound('appendix_rows',100)}
    import copy as _copy
    exact={name:_copy.deepcopy(rows) for name,rows in tables.items()}   # before any display shortening
    projected={name:rows[:bounds.get(name,bound('table_rows',20))] for name,rows in tables.items()}
    omitted={name:len(rows)-len(projected[name]) for name,rows in tables.items()}
    shortened=0
    for rows in projected.values():
        for row in rows:
            for key,cell in row.items():
                if isinstance(cell,str) and key in {'column','definition'} and len(cell)>96:
                    row[key]=cell[:93]+'…';shortened+=1
                elif isinstance(cell,float):row[key]=float(f'{cell:.6g}')
    from datatrust.report_structured import capped_tables, finding_index, finding_signal
    referenced_by=_signal_findings(value)
    def listed(name,rows):
        keys=list(rows[0].keys()) if rows else []
        if 'column' in keys:
            head=[k for k in keys if k not in ('source','pair','column')]
            scope='source' if 'source' in keys else 'pair' if 'pair' in keys else None
            return ['Field'+(' · '+scope if scope else '')]+head,[[str(r['column'])+((' · '+str(r[scope])) if scope else '')]+[r[k] for k in head] for r in rows]
        return keys,[[r[k] for k in keys] for r in rows]
    def signal(row):
        scope=row.get('source',row.get('pair'))
        finding=referenced_by.get((scope,row.get('column'))) if row.get('column') is not None else None
        return finding_signal(finding,scope) if finding else None
    def pointer(name):
        # The exact collection each table lists: per-source column profiles for a comparison, the dataset's otherwise.
        if name in ('features','targets'):return '/profile/sources' if comparison else '/profile/columns'
        if name=='sources':return '/profile/sources' if comparison else '/profile/source'
        return POINTERS.get(name,'/coverage')
    described=[]
    for name,rows in exact.items():
        if rows and len(rows)>len(projected[name]):
            columns,cells=listed(name,rows)
            described.append({'title':TITLES.get(name,name),'columns':columns,'rows':cells[:len(projected[name])],'all_rows':cells,
                              'topic':name,'pointer':pointer(name),'signals':[signal(r) for r in rows]})
    referenced={}
    disclosures,complete=capped_tables(described,profile_name,referenced=referenced)
    return {'tables':projected,'omitted':omitted,'shortened_labels':shortened,'actions':value['findings'][:bound('executive_actions',5)],'omitted_actions':max(0,len(value['findings'])-bound('executive_actions',5)),
            'disclosures':disclosures,'complete_tables':complete,'referenced':referenced,'findings':finding_index(value['findings']),
            'qa':{'schema_version':'1.3','human_omissions':omitted,'shortened_labels':shortened,'computed_records_preserved_in_json':True,'print_profile':profile_name}}
