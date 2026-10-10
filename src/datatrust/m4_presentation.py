"""Bounded human projection; JSON keeps every retained computed record."""
from dataclasses import asdict


def report_view(result):
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
    bounds={'sources':3,'features':bound('feature_details',20),'targets':bound('target_panels',6),'coverage':bound('appendix_rows',100)}
    projected={name:rows[:bounds.get(name,bound('table_rows',20))] for name,rows in tables.items()}
    omitted={name:len(rows)-len(projected[name]) for name,rows in tables.items()}
    shortened=0
    for rows in projected.values():
        for row in rows:
            for key,cell in row.items():
                if isinstance(cell,str) and key in {'column','definition'} and len(cell)>96:
                    row[key]=cell[:93]+'…';shortened+=1
                elif isinstance(cell,float):row[key]=float(f'{cell:.6g}')
    return {'tables':projected,'omitted':omitted,'shortened_labels':shortened,'actions':value['findings'][:bound('executive_actions',5)],'omitted_actions':max(0,len(value['findings'])-bound('executive_actions',5)),'qa':{'schema_version':'1.3','human_omissions':omitted,'shortened_labels':shortened,'computed_records_preserved_in_json':True}}
