"""Complete native-document pipeline qualification with family-disjoint authored controls."""
from collections import Counter
from dataclasses import replace
import copy
import csv
import hashlib
import json
from pathlib import Path
import time

from datatrust import *
from datatrust.cross import _core
from datatrust.cross_models import preflight,execute,algorithm_identity
from datatrust.worker import run_supervised

ROOT=Path(__file__).parent.absolute();RESULTS=ROOT/'results';REGISTRY=ROOT.parents[1]/'src/datatrust/cross_model_artifacts.json'


def population(split,n):
    root=ROOT/'data'/split;root.mkdir(parents=True,exist_ok=True);records=[];docs=[];truth={}
    for label in ('support','contradiction','insufficient'):
        for i in range(n):
            entity=f'{split}-{label}-{i:03d}';fmt='pdf' if i%2==0 else 'docx';path=root/(entity+'.'+fmt)
            period='FY2025';claim=f'Company {entity} was profitable in FY2025.'
            if label=='support': sentence=[f'Company {entity} earned a profit in FY2025.',f'The FY2025 financial result for company {entity} was profitable.',claim][i%3]
            elif label=='contradiction': sentence=[f'Company {entity} was not profitable in FY2025.',f'Company {entity} incurred a loss in FY2025.',f'Company {entity} was loss-making in FY2025.'][i%3]
            else: sentence=f'Company {entity} submitted its FY2025 report.'
            if split=='held_out':
                if label=='support': sentence=[f'In FY2025 company {entity} operated profitably.',f'A profit was recorded for company {entity} during FY2025.',f'The FY2025 accounts of company {entity} showed a profit.'][i%3]
                elif label=='contradiction': sentence=[f'Company {entity} recorded a financial loss during FY2025.',f'The FY2025 accounts of company {entity} showed a loss rather than a profit.',f'Company {entity} did not make a profit in FY2025.'][i%3]
                else: sentence=f'The FY2025 filing for company {entity} was received.'
            doc_period='FY2024' if label=='insufficient' and i%3==0 else period
            no_text=label=='insufficient' and i%3==1
            heading='Management performance' if split=='calibration' else 'Statement of financial performance'
            text_label='Business status' if split=='calibration' else 'Financial condition'
            if fmt=='pdf':
                from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle
                from reportlab.lib.styles import getSampleStyleSheet
                from reportlab.pdfgen import canvas
                if no_text:
                    c=canvas.Canvas(str(path));c.rect(50,50,100,100);c.showPage();c.save()
                else:
                    styles=getSampleStyleSheet();t=Table([['Metric','Period','Value'],['Revenue',doc_period,'12000000']]);t.setStyle(TableStyle([('GRID',(0,0),(-1,-1),1,'black')]))
                    blocks=[Paragraph(heading,styles['Heading1']),Spacer(1,20),t,Spacer(1,20),Paragraph(text_label+': '+sentence,styles['Normal'])]
                    if split=='held_out': blocks=[Paragraph('Supplied annual evidence',styles['Normal']),blocks[0],blocks[-1],Spacer(1,30),t]
                    SimpleDocTemplate(str(path)).build(blocks)
            else:
                from docx import Document
                d=Document()
                if not no_text:
                    d.add_heading(heading,1)
                    if split=='calibration': d.add_paragraph(text_label+': '+sentence)
                    t=d.add_table(rows=2,cols=3)
                    for row,vals in zip(t.rows,[['Metric','Period','Value'],['Revenue',doc_period,'12000000']]):
                        for c,v in zip(row.cells,vals): c.text=v
                    if split=='held_out': d.add_paragraph(text_label+': '+sentence)
                d.save(path)
            records.append({'id':entity,'period':period,'claim':claim,'revenue':'12000000'})
            docs.append({'id':entity,'period':doc_period,'path':path.name,'layout':'financial_evidence_v1'})
            truth[entity]=label
    for name,rows in [('records',records),('documents',docs)]:
        with (root/(name+'.csv')).open('w',newline='') as f:
            w=csv.DictWriter(f,fieldnames=rows[0]);w.writeheader();w.writerows(rows)
    spec=CrossRepresentationAuditSpec((CrossRepresentationInputSpec('records',str(root/'records.csv'),language='en'),CrossRepresentationInputSpec('documents',str(root/'documents.csv'),kind='document',asset_root=str(root),layout='financial_evidence_v1',language='en')),relationships=(RelationshipSpec('support','records','documents',cardinality='one_to_one',context={'period':['period','period']}),),mappings=(DocumentMappingSpec('text',layout='financial_evidence_v1',labels=('Business status','Financial condition'),pattern=r'\s*:\s*(?P<value>[^\n]+)'),DocumentMappingSpec('revenue',layout='financial_evidence_v1',kind='table_field',headers={'label':['Metric'],'period':['Period'],'value':['Value']},row_column='label',row_label='Revenue',context_columns={'period':'period'})),rules=(ReconciliationRule('status','support','claim',mapping='text',method='nli',claim_language='en'),ReconciliationRule('revenue','support','revenue',mapping='revenue')),allowed_roots=(str(root),))
    return spec,truth


def benchmark_stage(items,p,c,allocation,*,progress=None):
    import socket
    def blocked(*args,**kwargs): raise RuntimeError('Network forbidden in qualification worker.')
    socket.socket.connect=blocked;socket.socket.connect_ex=blocked;socket.create_connection=blocked
    result=execute(items,p,c,allocation,progress=progress,_benchmark=True)
    result.execution['network_socket_operations']='blocked_inside_spawned_worker'
    return result


def classify(answer,threshold,margin):
    judgments=set()
    for p in answer.get('predictions',[]):
        scores=sorted(p['scores'].items(),key=lambda x:-x[1])
        if scores[0][0]!='neutral' and scores[0][1]>=threshold and scores[0][1]-scores[1][1]>=margin: judgments.add(scores[0][0])
    return 'mixed' if {'entailment','contradiction'}<=judgments else 'support' if 'entailment' in judgments else 'contradiction' if 'contradiction' in judgments else 'abstained'


def metrics(answers,truth,threshold,margin):
    tally=Counter();total=len(truth)
    for target,label in truth.items():
        answer=answers.get(target,{})
        predicted=classify(answer,threshold,margin)
        tally[label+'_'+predicted]+=1
    out={'counts':dict(tally),'total':total,'assessed':len(answers),'unexamined':total-len(answers),'threshold':threshold,'margin':margin}
    for label in ('support','contradiction'):
        correct=tally[label+'_'+label];emitted=sum(v for k,v in tally.items() if k.endswith('_'+label));eligible=sum(v for k,v in tally.items() if k.startswith(label+'_'))
        out[label]={'correct':correct,'emitted':emitted,'eligible':eligible,'precision':correct/emitted if emitted else 0,'recall':correct/eligible if eligible else 0}
    out['abstention']=sum(v for k,v in tally.items() if k.endswith('_abstained'))/total
    out['false_findings_on_insufficient']=sum(v for k,v in tally.items() if k.startswith('insufficient_') and not k.endswith('_abstained'))
    return out


def run():
    RESULTS.mkdir(parents=True,exist_ok=True)
    cfg=CrossRepresentationAnalysisConfig(models=CrossModelOptions(str(ROOT/'models/nli'),str(ROOT.parent/'m6/models/multilingual-e5-small')))
    provenance=preflight(cfg.models);provenance['nli']['qualification']={'threshold':0,'margin':0}
    runs={};cases={};frozen=[]
    for split,n in [('calibration',100),('held_out',200)]:
        started=time.monotonic();spec,source_truth=population(split,n);r=run_supervised(_core,(spec,cfg,provenance),cfg.execution)
        truth={}
        for item in r.private['model_inputs']:
            loc=r.private['locators'][item['claim_reference']];ordinal=loc['record']['ordinal'];entity=list(source_truth)[ordinal-1];truth[item['target_id']]=source_truth[entity]
        stage=run_supervised(benchmark_stage,(r.private['model_inputs'],provenance,cfg,cfg.limits.model_seconds),cfg.execution)
        answers={x['target_id']:x for x in stage.profile['answers']};runs[split]={'answers':answers,'truth':truth,'execution':stage.execution,'coverage':stage.coverage,'core_execution':r.execution,'core_coverage':r.coverage,'source_truth_sha256':hashlib.sha256(json.dumps(source_truth,sort_keys=True).encode()).hexdigest(),'seconds':time.monotonic()-started}
        if split=='calibration':
            grid=[metrics(answers,truth,t,m) for t in (.8,.85,.9,.95,.98) for m in (.1,.2)]
            viable=[x for x in grid if all(x[k]['precision']>=.95 for k in ('support','contradiction'))]
            chosen=max(viable or grid,key=lambda x:(min(x[k]['precision'] for k in ('support','contradiction')),min(x[k]['recall'] for k in ('support','contradiction')),-x['threshold']))
            frozen=[chosen['threshold'],chosen['margin']];print('Frozen calibration',frozen,flush=True)
            runs[split]['grid']=grid
        runs[split]['metrics']=metrics(answers,truth,*frozen);print(split,runs[split]['metrics'],flush=True)
        # No raw text, document paths or private manifests are retained in the public ledger.
        runs[split].pop('answers');runs[split].pop('truth')
    held=runs['held_out']['metrics'];passed=all(held[k]['precision']>=.9 and held[k]['recall']>=.7 and held[k]['eligible']>=200 for k in ('support','contradiction')) and held['false_findings_on_insufficient']==0
    reg=json.loads(REGISTRY.read_text());reg['qualification']['nli']={'status':'passed' if passed else 'failed','algorithm_identity':algorithm_identity(),'revision':reg['models']['nli']['revision'],'threshold':frozen[0],'margin':frozen[1],'scope':'Authored native PDF/DOCX English financial declarations; not external methodology validation.','ledger':'validation/m9/results/text_qualification.json','held_out':held,'limits':cfg.limits.to_dict(),'eligible_layouts':['finance','financial_evidence_v1'],'eligible_mapping_kinds':['label_value','text']}
    REGISTRY.write_text(json.dumps(reg,indent=2)+'\n');(RESULTS/'text_qualification.json').write_text(json.dumps({'pipeline':'native extraction -> declared mapping/context -> E5 retrieval -> NLI -> emitted candidate','split':'Disjoint entities, document bytes, authored layout families and sentence variants; common labels are declared recipe aliases.','network':'Blocked inside model worker by offline validation runner when used.','algorithm_identity':algorithm_identity(),'runs':runs,'qualification':reg['qualification']['nli']},indent=2)+'\n')


if __name__=='__main__': run()
