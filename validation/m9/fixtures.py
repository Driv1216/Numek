"""Independent authored financial expectations; no model-derived ground truth."""
import csv
import json
from pathlib import Path
from datatrust import *


def financial(root,count=20,format='pdf'):
    root=Path(root);root.mkdir(parents=True,exist_ok=True);docs=[];records=[]
    for i in range(1,count+1):
        entity=f'A{i:03d}';records.append({'id':entity,'entity':entity,'period':'FY2025','revenue':'12000000','cutoff':'2026-01-01T00:00:00Z','claim':f'Company {entity} was profitable in FY2025.'})
        copies=2 if i==count else 1
        for j in range(copies):
            revenue='1200000' if i==count-1 or i==count and j==1 else '12000000'
            status=f'Company {entity} was '+('loss-making' if i==count and j==1 else 'profitable')+' in FY2025.'
            path=root/f'{entity}-{j}.{format}'
            if format=='pdf':
                from reportlab.platypus import SimpleDocTemplate,Paragraph,Table,TableStyle,Spacer
                from reportlab.lib.styles import getSampleStyleSheet
                styles=getSampleStyleSheet();table=Table([['Metric','Period','Value'],['Revenue','FY2025',revenue]],colWidths=[150,100,150]);table.setStyle(TableStyle([('GRID',(0,0),(-1,-1),1,'black')]))
                SimpleDocTemplate(str(path)).build([Paragraph(f'Company {entity} financial evidence',styles['Title']),Spacer(1,20),table,Spacer(1,20),Paragraph('Business status: '+status,styles['Normal'])])
            else:
                from docx import Document
                doc=Document();doc.add_heading(f'Company {entity} financial evidence',0);t=doc.add_table(rows=2,cols=3)
                for row,values in zip(t.rows,[['Metric','Period','Value'],['Revenue','FY2025',revenue]]):
                    for cell,v in zip(row.cells,values): cell.text=v
                doc.add_paragraph('Business status: '+status);doc.save(path)
            docs.append({'id':entity+f'-{j}','entity':entity,'period':'FY2025','path':path.name,'available':'2025-12-01T00:00:00Z','role':'evidence','layout':'finance'})
    for name,rows in [('records',records),('documents',docs)]:
        with (root/(name+'.csv')).open('w',newline='') as f:
            w=csv.DictWriter(f,fieldnames=rows[0]);w.writeheader();w.writerows(rows)
    spec=CrossRepresentationAuditSpec(inputs=(CrossRepresentationInputSpec('records',str(root/'records.csv'),language='en'),CrossRepresentationInputSpec('documents',str(root/'documents.csv'),kind='document',asset_root=str(root),layout='finance',language='en')),relationships=(RelationshipSpec('support','records','documents',left_keys=('entity',),right_keys=('entity',),context={'entity':['entity','entity'],'period':['period','period']},availability=ClockSpec('available'),cutoff=ClockSpec('cutoff')),),mappings=(DocumentMappingSpec('revenue',layout='finance',kind='table_field',headers={'label':['Metric'],'period':['Period'],'value':['Value']},row_column='label',row_label='Revenue',context_columns={'period':'period'},unit='INR',currency='INR'),DocumentMappingSpec('status',layout='finance',labels=('Business status',),pattern=r'\s*:\s*(?P<value>[^\n]+)')),rules=(ReconciliationRule('revenue','support','revenue',mapping='revenue',unit='INR',currency='INR'),ReconciliationRule('status','support','claim',mapping='status',method='nli',claim_language='en')),allowed_roots=(str(root),),dataset_name='Financial evidence reconciliation')
    (root/'audit.json').write_text(json.dumps(spec.to_dict(),indent=2)+'\n')
    return spec
