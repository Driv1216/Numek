"""Recorded narrow workloads; no extrapolated arbitrary-document capacity claims."""
import csv
import json
from pathlib import Path
import time
from datatrust import *

ROOT=Path(__file__).parent.absolute()


def prepare(name,rows,documents,fanout):
    root=ROOT/'data'/name;root.mkdir(parents=True,exist_ok=True)
    from reportlab.pdfgen import canvas
    for i in range(documents):
        p=root/f'doc-{i}.pdf';c=canvas.Canvas(str(p));c.drawString(50,750,f'Supplied financial evidence {i}');c.drawString(50,720,'Revenue: 12000000');c.showPage();c.save()
    with (root/'records.csv').open('w',newline='') as f:
        w=csv.writer(f);w.writerow(['id','doc_id','revenue','period'])
        for i in range(rows): w.writerow([f'r{i}',f'd{i%documents}','12000000','FY2025'])
    with (root/'documents.csv').open('w',newline='') as f:
        w=csv.writer(f);w.writerow(['id','record_id','path','period'])
        if fanout:
            for i in range(rows):
                for j in range(fanout): w.writerow([f'a{i}-{j}',f'r{i}',f'doc-{(i+j)%documents}.pdf','FY2025'])
        else:
            for i in range(documents): w.writerow([f'd{i}','',f'doc-{i}.pdf','FY2025'])
    rel=RelationshipSpec('support','records','documents',left_keys=('id' if fanout else 'doc_id',),right_keys=('record_id' if fanout else 'id',),cardinality='one_to_many' if fanout else 'many_to_one',context={'period':['period','period']})
    maps=() if fanout else (DocumentMappingSpec('revenue',layout='finance',labels=('Revenue',),pattern=r'\s*:\s*(?P<value>[^\n]+)'),)
    rules=() if fanout else (ReconciliationRule('revenue','support','revenue',mapping='revenue'),)
    return CrossRepresentationAuditSpec((CrossRepresentationInputSpec('records',str(root/'records.csv')),CrossRepresentationInputSpec('documents',str(root/'documents.csv'),kind='document',asset_root=str(root),layout='finance')),relationships=(rel,),mappings=maps,rules=rules,allowed_roots=(str(root),)),root


def run(large=False):
    name='large' if large else 'small';rows,documents,fanout=(1000000,1000,5) if large else (10000,50,0)
    spec,root=prepare(name,rows,documents,fanout);start=time.monotonic();out=ROOT/'results';out.mkdir(exist_ok=True)
    from datatrust.cross_models import algorithm_identity
    identity=algorithm_identity()
    try:
        r=DataTrust.audit_cross_representation(spec)
        associations=next(e['data']['associations'] for e in r.evidence if e['family']=='relationships')
        assert associations==rows*(fanout or 1)
        if not large: assert next(e['data']['satisfied'] for e in r.evidence if e['population']=='rule_1')==rows
        payload={'status':'completed','execution':r.execution,'coverage':r.coverage,'records':rows,'associations':associations,'native_pdf_pages':documents,'scope':'Full record/association integrity and native extraction; large workload does not claim million-record field reconciliation throughput.' if large else 'Full native extraction, associations and 10000 field reconciliations.','source_bytes':sum(p.stat().st_size for p in root.glob('*.csv')),'seconds':time.monotonic()-start}
    except Exception as exc:
        payload={'status':'failed','code':getattr(exc,'code',type(exc).__name__),'execution':getattr(exc,'execution',{}),'seconds':time.monotonic()-start,'records':rows,'associations':rows*(fanout or 1),'native_pdf_pages':documents,'scope':'Recorded admission/integrity workload, not a capacity guarantee.'}
    payload['algorithm_identity']=identity
    target=out/(name+'_resources.json')
    if target.exists() and not (out/('initial_'+name+'_resources.json')).exists():
        (out/('initial_'+name+'_resources.json')).write_bytes(target.read_bytes())
    target.write_text(json.dumps(payload,indent=2,allow_nan=False)+'\n');print(json.dumps({k:payload[k] for k in ('status','records','associations','seconds')}),flush=True)


if __name__=='__main__':
    import sys
    run('--large' in sys.argv)
