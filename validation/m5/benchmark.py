"""Declared CSV/compressed-Parquet workloads; objectives are hypotheses."""
import argparse
from dataclasses import replace
import json
from pathlib import Path
import platform
import tempfile
import time
import psutil
import pyarrow as pa
import pyarrow.csv as pc
import pyarrow.parquet as pq
from datatrust import *


def run(gib,fmt,output):
    record={'target_combined_gib':gib,'format':fmt,'capacity_guarantee':False,'objective_seconds':300 if gib==1 else 1800,'environment':{'python':platform.python_version(),'platform':platform.platform(),'duckdb':__import__('duckdb').__version__,'pyarrow':pa.__version__,'physical_memory':psutil.virtual_memory().total}}
    with tempfile.TemporaryDirectory(prefix='numek-m5-capacity-') as tmp:
        root=Path(tmp);n=int(gib*1024**3//620);inputs=[]
        for source_id,shift in [('reference',0),('current',20)]:
            csv=root/(source_id+'.csv')
            with csv.open('w') as f:
                f.write('time,entity,x,context\n')
                for start in range(0,n,10000):f.writelines(f'{i*1000000000},{i%128:03d},{i%100000+shift:07d},{"x"*280}\n' for i in range(start,min(n,start+10000)))
            path=csv
            if fmt=='parquet':
                path=csv.with_suffix('.parquet');reader=pc.open_csv(csv,convert_options=pc.ConvertOptions(column_types={'time':pa.int64(),'entity':pa.string(),'x':pa.int64(),'context':pa.string()}));writer=None
                for batch in reader:
                    table=pa.Table.from_batches([batch]);schema=table.schema
                    if writer is None:writer=pq.ParquetWriter(path,schema,compression='zstd')
                    writer.write_table(table)
                writer.close()
            temporal=TemporalSpec(ClockSpec('time',encoding='epoch',epoch_unit='ns'),(MeasurementSpec('x'),),entity_columns=('entity',),max_adjacency_ns='128000000000')
            inputs.append(TemporalInputSpec(source_id,TemporalSourceSpec(str(path),fmt),temporal,role=source_id))
        spec=TemporalAuditSpec(tuple(inputs));cfg=TemporalAnalysisConfig()
        record.update(inputs=[{'source':x.id,'bytes':Path(x.source.path).stat().st_size,'rows':n,'columns':4} for x in inputs],normalized_cells=2*n,scope={'required':'all eligible declared records','behavior':'default 12 windows, both x measurements; bounded series/comparison/work scopes','availability':'unknown; no history or evaluation supplied'},configuration=cfg.to_dict())
        started=time.monotonic()
        try:
            result=DataTrust.audit_temporal(spec,cfg)
            assert all(v['rows']==n for v in result.profile['sources'].values())
            record.update(status=result.execution['status'],execution=result.execution,coverage=result.coverage,result_bytes=len(result.json_text().encode()))
        except Exception as exc:record.update(status='failed',error=str(exc),code=getattr(exc,'code',None),stage=getattr(exc,'stage',None),execution=getattr(exc,'execution',{}))
        record['seconds']=time.monotonic()-started;record['objective_met']=record['status']=='completed' and record['seconds']<=record['objective_seconds']
    output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(record,indent=2)+'\n');print(json.dumps({k:record[k] for k in ('target_combined_gib','format','status','seconds','objective_met')}),flush=True)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--gib',type=float,choices=[1,5],required=True);p.add_argument('--format',choices=['csv','parquet'],default='csv');p.add_argument('--out',type=Path,required=True);a=p.parse_args();run(a.gib,a.format,a.out)
