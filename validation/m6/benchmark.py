"""Measured narrow text workloads; file size is not a capacity guarantee."""
import argparse
from dataclasses import replace
import hashlib,json,time,tempfile
from pathlib import Path
from datatrust import *


def run(mib,out):
    with tempfile.TemporaryDirectory(prefix='numek-m6-capacity-') as root:
        path=Path(root)/'text.jsonl';size=0;n=0
        paragraph=('A preserved source document has explicit provenance, annotations and split membership. '*80)
        started=time.monotonic()
        with path.open('wb') as handle:
            while size<mib*1024**2:
                row=json.dumps({'id':str(n),'text':paragraph+f'Unique local record {n}.'},ensure_ascii=False).encode()+b'\n';handle.write(row);size+=len(row);n+=1
        generation_seconds=time.monotonic()-started
        spec=TextAuditSpec((TextInputSpec('corpus',TextSourceSpec(str(path)),(TextFieldSpec('text','text'),),id_selector='id'),),allowed_roots=(root,))
        # Fully populated structural checks; explicitly bounded investigation settings.
        limits=replace(TextWorkLimits(),lexical_units=128,signature_work=1000000,shingle_positions=100000,verification_visits=1000000,details=10)
        config=TextAnalysisConfig(limits=limits)
        try:
            result=DataTrust.audit_text(spec,config)
            count=next(x for x in result.evidence if x['family']=='corpus')['data']['content_units'];assert count==n
            record={'status':'completed','source_bytes':size,'records':n,'characters_per_record':len(paragraph)+25,'declared_mib':mib,'source_sha256':result.execution['provenance']['source_1']['sha256'],'execution':result.execution,'coverage':result.coverage,'measured_full_content_units':count,'logical_workload':'Narrow JSONL, one lexical ID and one ~6.8K-character ASCII document per row; high shared-template overlap','source_generation_seconds':generation_seconds}
        except Exception as exc:record={'status':'failed','code':getattr(exc,'code',type(exc).__name__),'error':str(exc),'stage':getattr(exc,'stage','unknown'),'source_bytes':size,'records':n,'declared_mib':mib,'execution':getattr(exc,'execution',{}),'completed_result_published':False}
        Path(out).parent.mkdir(parents=True,exist_ok=True);Path(out).write_text(json.dumps(record,indent=2,allow_nan=False)+'\n');print(json.dumps({'mib':mib,'status':record['status'],'records':n,'seconds':record['execution'].get('whole_job_seconds')}))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--mib',type=int,default=100);p.add_argument('--out',required=True);a=p.parse_args();run(a.mib,a.out)
