"""Controlled wide/long-header presentation case; completed evidence is reusable."""
from pathlib import Path
import csv
import json
from datatrust import *
from datatrust.temporal import execute
from pypdf import PdfReader
ROOT=Path(__file__).parent

def run():
    root=ROOT/'reports/controlled';root.mkdir(exist_ok=True);source=root/'long_headers.csv'
    names=[f'measurement_{i:02d}_'+('long composite name & <display> '*3) for i in range(16)]
    if not source.exists():
        with source.open('w',newline='') as stream:
            writer=csv.writer(stream);writer.writerow(['time','entity',*names])
            writer.writerows([str(i*10**9),'station & <north>',*[i%11+j for j in range(16)]] for i in range(240))
    dest=root/'long_headers_reviewed.pdf'
    if not dest.exists():
        temporal=TemporalSpec(ClockSpec('time',encoding='epoch',epoch_unit='ns'),tuple(MeasurementSpec(x,unit='declared unit & scale') for x in names),entity_columns=('entity',))
        spec=TemporalAuditSpec((TemporalInputSpec('wide',TemporalSourceSpec(str(source.resolve()),'csv'),temporal),),dataset_name='Controlled wide panel — escaped long measurement headers')
        previous=root/'long_headers.json'
        if previous.exists():
            saved=json.loads(previous.read_text());result=TemporalAuditResult(spec=spec,**{k:v for k,v in saved.items() if k!='spec'})
        else:result=execute(spec,TemporalAnalysisConfig())
        assert result.execution['status']=='completed'
        result.generate_artifacts(dest,format='pdf',json_path=root/'long_headers_reviewed.json')
    pdf=PdfReader(dest);pages=len(pdf.pages);assert pages<=12
    assert 'escaped long measurement headers' in ' '.join(pdf.pages[0].extract_text().split())
    (ROOT/'results/presentation.json').write_text(json.dumps({'case':'16 wide measurements with long escaped headers and entity labels','pdf_pages':pages,'artifact':'reports/controlled/long_headers_reviewed.pdf','no_pages_removed':True,'page_target_is_design_budget':True},indent=2)+'\n')
    print(pages,'pages',flush=True)
if __name__=='__main__':run()
