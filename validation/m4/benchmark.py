"""Measured combined-input objectives. No guaranteed capacity claim."""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import platform
import tempfile
import time
import psutil
from datatrust import *


def run(gib,output):
    record={'combined_input_target_gib':gib,'environment':{'python':platform.python_version(),'platform':platform.platform(),'physical_memory':psutil.virtual_memory().total,'duckdb':__import__('duckdb').__version__,'pandas':__import__('pandas').__version__},'objectives':{'seconds':300 if gib==1 else 1800,'rss_bytes':6*1024**3},'capacity_guarantee':False}
    with tempfile.TemporaryDirectory(prefix='numek-m4-capacity-') as temp:
        root=Path(temp);count=int(gib*1024**3//602);sources=[]
        for role,shift in [('reference',0),('current',20)]:
            p=root/(role+'.csv')
            with p.open('w') as f:
                f.write('id,measurement,category,context\n')
                for start in range(0,count,10000):
                    f.writelines(f'{i:08d},{i%100000+shift:07d},{"A" if i%2 else "B"},{"x"*280}\n' for i in range(start,min(start+10000,count)))
            sources.append(DatasetInput(role,role,DatasetSpec(str(p)),TaskSpec('dataset_profile',group_columns=('id',)),AnalysisConfig(features=FeatureOptions({'measurement':'quantitative','category':'categorical','context':'categorical'}))))
        record['inputs']=[{'role':i.role,'bytes':Path(i.dataset.path).stat().st_size,'rows':count,'columns':4} for i in sources]
        record['combined_source_bytes']=sum(v['bytes'] for v in record['inputs'])
        options=ExecutionOptions()
        started=time.monotonic()
        try:
            result=DataTrust.compare(ComparisonSpec('versions',tuple(sources)),ComparisonConfig(execution=options))
            record.update(status=result.execution['status'],execution=result.execution,coverage={k:{'status':v['status'],'population':v['population']} for k,v in result.coverage['diagnostics'].items()},result_bytes=len(result.json_text().encode()))
            assert result.profile['sources']['reference']['row_count']==count
            measurement=result.coverage['measurements']['reference:current.populations']['columns'][0]
            assert measurement['column']=='measurement' and measurement['wasserstein_1']>0
        except Exception as exc:record.update(status='failed',failure=str(exc),code=getattr(exc,'code',None))
        record['elapsed_seconds']=time.monotonic()-started
        record['runtime_objective_met']=record['status']=='completed' and record['elapsed_seconds']<=record['objectives']['seconds']
        record['rss_objective_met']=record.get('execution',{}).get('peak_worker_rss_bytes',float('inf'))<record['objectives']['rss_bytes']
    output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(record,indent=2)+'\n');print(json.dumps({k:v for k,v in record.items() if k!='execution'},indent=2),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--gib',type=float,choices=[1,5],required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();run(a.gib,a.out)
