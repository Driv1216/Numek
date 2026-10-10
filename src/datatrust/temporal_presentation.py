"""Presentation of retained M5 evidence; never invokes analytical work."""
import json
from decimal import Decimal
from markupsafe import Markup,escape

TOPICS=[('declarations','Declarations',set()),('chronology','Chronology',{'chronology','elapsed_chronology','ordering','repetition','freshness'}),('continuity','Continuity and history',{'continuity','lookback','panel'}),('behavior','Behavioral investigation',{'behavior','behavior_windows','behavior_series','runs','volatility','seasonality','behavior_panel','behavior_scope','runs_and_volatility','multivariate','annotation_windows'}),('availability','Availability and outcome maturity',{'availability','availability_unknown','past_observation','revision_history','selected_revision_timing','outcome_maturity','annotations'}),('evaluation','Chronological evaluation',{'evaluation'}),('methodology','Methodology and coverage',set())]


def display(v):
    if v is None:return 'Unavailable / unknown'
    if isinstance(v,bool):return 'Yes' if v else 'No'
    if isinstance(v,float):return format(v,'.7g')
    if isinstance(v,(list,dict)):return json.dumps(v,ensure_ascii=False,separators=(',',':'))
    return str(v)


def flattened(data,prefix=''):
    for key,value in data.items():
        name=prefix+key.replace('_',' ')
        if isinstance(value,dict):yield from flattened(value,name+' / ')
        elif isinstance(value,list) and value and isinstance(value[0],dict):
            for index,item in enumerate(value):
                label=str(item.get('feature',item.get('measurement',item.get('window_id',index))))
                yield from flattened(item,name+' ['+label+'] / ')
        else:yield name,display(value)


def bars(labels,counts,title):
    if not counts:return ''
    width=660;height=160;numeric=[Decimal(str(x)) for x in counts];maximum=max(numeric) or Decimal(1);step=width/max(1,len(counts));items=[]
    for i,(label,count) in enumerate(zip(labels,counts)):
        h=float(105*numeric[i]/maximum);x=5+i*step
        items.append(f'<rect x="{x:.2f}" y="{120-h:.2f}" width="{max(1,step-7):.2f}" height="{h:.2f}" fill="#345d9d"/><text x="{x+step/2:.2f}" y="140" text-anchor="middle">{escape(str(label)[:18])}</text><text x="{x+step/2:.2f}" y="{max(12,115-h):.2f}" text-anchor="middle">{escape(display(count))}</text>')
    return Markup(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width+10} {height}" role="img" aria-label="{escape(title)}"><title>{escape(title)}</title>'+''.join(items)+'</svg>')


def report_view(result,*,family=None,measurement=None):
    value=result.to_dict() if hasattr(result,'to_dict') else result
    limits=value['context']['presentation'];records=value['evidence'];topics=[];omissions={};totalrows=0
    for ident,title,families in TOPICS:
        rows=[];charts=[]
        if ident=='declarations':
            for source in value['spec']['inputs']:
                semantics=source['temporal']
                rows.append({'ref':source['id'],'field':'Source and base task','value':display({'format':source['source']['format'],'role':source['role'],'task':source['task']['kind'],'targets':source['task']['targets'] or source['task']['target']})})
                if semantics:
                    for key in ('observation','layout','entity_columns','observation_keys','clock','schedule','active_intervals'):
                        rows.append({'ref':source['id'],'field':key.replace('_',' '),'value':display(semantics[key])})
                    for m in semantics['measurements']:rows.append({'ref':source['id'],'field':m['name'],'value':display(m)})
        elif ident=='methodology':
            data={'schema':value['schema_version'],'methodology':value['methodology_id'],'execution_status':value['execution']['status'],'aggregate_scope':value['coverage']['computed_aggregate_scope'],'search_scope':value['coverage']['unsearched_analytical_scope'],'internal_detail_omissions':value['coverage']['internal_detail_retention_omissions'],'timezone':value['execution']['timezone_data'],'phase_seconds':value['execution']['phase_seconds'],'provisional_limits':value['execution']['temporal_limits'],'decoder_peak_is_bounded':False}
            for key,val in flattened(data):rows.append({'ref':'method','field':key,'value':val})
            for check in value['checks']:
                if check['applicability']=='blocked' or check['execution']=='failed':rows.append({'ref':check['evidence_refs'][0],'field':check['check_id'],'value':check['reason']})
        else:
            topic_records=sorted(records,key=lambda record:record['check_id']!='behavior_series') if ident=='behavior' else records
            for record in topic_records:
                if record['check_id'] not in families or family and record['check_id']!=family or measurement and record['measurement'] is not None and record['measurement']!=measurement:continue
                raw=record['data']
                declarations={'binding','history_binding','fold','declaration','investigation_defaults','clock','windows','retained_histories','details'}
                data={**{k:v for k,v in raw.items() if k not in declarations},**{k:v for k,v in raw.items() if k in declarations}}
                base=','.join(record['source_ids'])+(' / '+record['measurement'] if record['measurement'] else '')
                if record['check_id']=='behavior_windows':
                    ref=raw['windows'][raw['reference_window']]
                    items=[('Reference',f"Window {raw['reference_window']} · {ref['start_tick']} to {ref['end_tick']} · unit {raw['unit'] or 'undeclared'} · support setting {raw['investigation_defaults']['min_support']}")]
                    for x in raw['windows']:
                        missing=display(x['missing_rate'])
                        text=f"{x['cells']} cells · missing rate {missing} · invalid {x['invalid']} · nonfinite {x['nonfinite']} · finite {x['finite']} · {x['entities']} entities"
                        if x['iqr'] is not None:text+=' · IQR '+display(x['iqr'])
                        if x.get('category_proportions'):text+=' · categories '+display(x['category_proportions'])
                        items.append(('Window '+str(x['window_id']),text))
                    for x in raw['comparisons']:
                        text=f"Support {x['reference_support']}/{x['comparison_support']} · Δmissing {display(x.get('missingness_change'))}"
                        for key,label in (('cdf_distance','CDF'),('wasserstein_1','W1'),('normalized_w1','W1/IQR'),('total_variation','TV')):
                            if key in x:text+=' · '+label+' '+display(x[key])
                        if x.get('distribution_block'):text+=' · blocked: '+x['distribution_block']
                        elif x.get('below_support_descriptive_only'):text+=' · below support: descriptive'
                        elif x.get('distribution_review'):text+=' · investigation candidate'
                        items.append(('Comparison '+str(x['reference_window'])+' → '+str(x['comparison_window']),text))
                elif record['check_id']=='behavior_series':items=list(flattened({k:v for k,v in data.items() if k!='details'}))
                elif record['check_id']=='chronology':items=list(flattened({k:v for k,v in data.items() if k!='clock'}))
                else:items=list(flattened(data))
                for field,val in items:rows.append({'ref':record['id']+' '+base,'field':field,'value':val})
                if record['check_id']=='behavior_windows' and len(charts)<2:
                    windows=data['windows'];charts.append({'title':base+' · supplied cells per window', 'svg':bars([x['window_id'] for x in windows],[x['cells'] for x in windows],base+' window support')})
                if record['check_id']=='continuity' and data.get('timeline') and len(charts)<2:
                    charts.append({'title':base+' · missing values and absent slots remain separate', 'svg':timeline(data['timeline'],base)})
                if record['check_id']=='continuity' and 'occupied_distinct_slots' in data and len(charts)<2:charts.append({'title':base+' · expected population', 'svg':bars(['Occupied','Absent'],[data['occupied_distinct_slots'],data['absent_expected_records_or_opportunities']],base+' observation coverage')})
        limit=limits['table_rows'];visible=rows[:limit];omissions[ident]=len(rows)-len(visible);totalrows+=len(visible)
        for row in visible:
            if len(row['value'])>350:row['value']=row['value'][:347]+'… [retained JSON contains full detail]'
        for row in visible:
            for key,size in (('ref',48),('field',64),('value',180)):
                text=row[key];row['print_'+key]=text if len(text)<=size else text[:size-7]+'… [JSON]'
        topics.append({'id':ident,'title':title,'rows':visible,'charts':charts,'omitted_rows':omissions[ident],'total_rows':len(rows)})
    appendix=[]
    for record in records:
        if family and record['check_id']!=family or measurement and record['measurement'] is not None and record['measurement']!=measurement:continue
        for item in record['witnesses']:
            appendix.append({'ref':record['id'],'field':'Witness','value':display(item)})
        for key in ('retained_histories','details'):
            for item in record['data'].get(key,[]):appendix.append({'ref':record['id'],'field':key.replace('_',' '),'value':display(item)})
    appendix_total=len(appendix);appendix=appendix[:limits['appendix_rows']]
    for row in appendix:
        if len(row['value'])>500:row['value']=row['value'][:497]+'… [full detail in JSON]'
        row['print_value']=row['value'] if len(row['value'])<=180 else row['value'][:177]+'… [JSON]'
    return {'appendix':appendix,'appendix_total':appendix_total,'appendix_print_rows':limits['table_rows'],'topics':topics,'actions':value['findings'][:limits['executive_actions']],'omissions':omissions,'qa':{'pdf_abbreviated_metric_cells':sum(row[key]!=row['print_'+key] for topic in topics for row in topic['rows'] for key in ('ref','field','value')),'pdf_omitted_additional_charts':{x['id']:max(0,len(x['charts'])-1) for x in topics},'pdf_appendix_omitted_rows':max(0,appendix_total-min(len(appendix),limits['table_rows'])),'html_appendix_omitted_rows':max(0,appendix_total-len(appendix)),'presentation_omitted_rows':omissions,'retained_evidence_records':len(records),'displayed_metric_rows':totalrows,'page_budget':'One executive page; ordinary target eight pages; wide/long-header target twelve. No PDF pages are removed.'}}


def timeline(rows,title):
    tracks=[('Supplied missing cells','supplied_missing_cells','#9a6fc4'),('Absent slots / opportunities','absent_slots_or_opportunities','#c3893b'),('Outside expectation','outside_expectation_period','#a5afbd')]
    parts=[];step=470/max(1,len(rows))
    for j,(label,key,color) in enumerate(tracks):
        parts.append(f'<text x="0" y="{25+j*38}">{escape(label)}</text>')
        values=[float(x.get(key) or 0) for x in rows];scale=max(values) or 1
        for i,v in enumerate(values):
            parts.append(f'<rect x="{190+i*step:.2f}" y="{9+j*38}" width="{step-3:.2f}" height="22" fill="{color if v else "#e9edf3"}" opacity="{.3+.7*v/scale if v else 1:.3f}"><title>{escape(label)} · bin {i}: {escape(display(rows[i].get(key)))}</title></rect>')
    return Markup(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 665 130" role="img" aria-label="{escape(title)} coverage timeline"><title>{escape(title)} · bounded coverage timeline</title>'+''.join(parts)+'</svg>')
