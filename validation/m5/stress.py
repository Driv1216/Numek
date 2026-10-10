"""Adversarial temporal shapes and intentional supervised failures."""
from dataclasses import replace
from pathlib import Path
import json
import platform
import tempfile
import time
import pyarrow as pa
import pyarrow.parquet as pq
from datatrust import *


def run(output):
    results=[]
    with tempfile.TemporaryDirectory(prefix='numek-m5-stress-') as tmp:
        root=Path(tmp)
        for kind in ('short_histories','skew','wide','large_gap','revision_heavy','oversized_dictionary','decoded_failure','rss_failure','workspace_failure'):
            p=root/(kind+'.csv');history=None;histories=()
            if kind=='wide':
                names=[f'x{i}' for i in range(96)];p.write_text('time,'+','.join(names)+'\n'+''.join(str(i)+','+','.join(str(i%97+j) for j in range(96))+'\n' for i in range(10000)))
                temporal=TemporalSpec(ClockSpec('time',encoding='epoch',epoch_unit='ns'),tuple(MeasurementSpec(x) for x in names))
            elif kind=='large_gap':
                p.write_text('time,x\n0,1\n1000000000000000000,2\n');temporal=TemporalSpec(ClockSpec('time',encoding='epoch',epoch_unit='ns'),(MeasurementSpec('x'),),schedule=ScheduleSpec('fixed',cadence_ns='1',anchor='0'))
            elif kind in {'oversized_dictionary','decoded_failure'}:
                p=root/(kind+'.parquet');pq.write_table(pa.table({'time':[0]*128,'x':['a'*100000]*128}),p,use_dictionary=True,compression='zstd');temporal=TemporalSpec(ClockSpec('time',encoding='epoch',epoch_unit='ns'),(MeasurementSpec('x',representation='categorical'),))
            else:
                p.write_text('time,id,x,cutoff\n'+''.join(f'{i},{i if kind=="short_histories" else 0 if i<95000 else i},{i%101},200000\n' for i in range(100000)))
                temporal=TemporalSpec(ClockSpec('time',encoding='epoch',epoch_unit='ns'),(MeasurementSpec('x'),),entity_columns=('id',),observation_keys=('id','time'))
                if kind=='revision_heavy':
                    hp=root/'history.csv';hp.write_text('id,time,value,available\n'+''.join(f'{i%10},0,{i%101},{i}\n' for i in range(100000)))
                    history=TemporalInputSpec('history',TemporalSourceSpec(str(hp)),role='history')
                    histories=(FeatureHistorySpec('h','data','history',('x',),('id','time'),('id','time'),{'x':'value'},ClockSpec('available',encoding='epoch',epoch_unit='ns'),ClockSpec('cutoff',encoding='epoch',epoch_unit='ns')),)
            item=TemporalInputSpec('data',TemporalSourceSpec(str(p),'parquet' if p.suffix=='.parquet' else 'csv'),temporal)
            cfg=TemporalAnalysisConfig(behavior=TemporalBehaviorSpec(windows=4),limits=TemporalWorkLimits(behavior_measurements=4))
            if kind=='decoded_failure':cfg=replace(cfg,limits=replace(cfg.limits,decoded_batch_bytes=1000))
            if kind=='rss_failure':cfg=replace(cfg,execution=replace(cfg.execution,max_rss_bytes=64*1024**2))
            if kind=='workspace_failure':cfg=replace(cfg,execution=replace(cfg.execution,workspace_bytes=32*1024**2))
            spec=TemporalAuditSpec((item,history) if history else (item,),histories=histories);started=time.monotonic()
            record={'kind':kind,'configuration':cfg.to_dict(),'source_bytes':p.stat().st_size}
            try:
                result=DataTrust.audit_temporal(spec,cfg);record.update(status=result.execution['status'],execution=result.execution,result_bytes=len(result.json_text().encode()),coverage=result.coverage)
                if kind=='large_gap':assert next(x['data'] for x in result.evidence if x['check_id']=='continuity')['absent_expected_records_or_opportunities']==999999999999999999
                if kind in {'decoded_failure','rss_failure','workspace_failure'}:raise AssertionError('Intended failure published a result.')
            except Exception as exc:
                if isinstance(exc,AssertionError):raise
                record.update(status='failed',error=str(exc),code=getattr(exc,'code',None),execution=getattr(exc,'execution',None))
                if kind not in {'decoded_failure','rss_failure','workspace_failure'}:raise
            record['seconds']=time.monotonic()-started;results.append(record);print(kind,record['status'],record['seconds'],flush=True)
    output.write_text(json.dumps({'python':platform.python_version(),'capacity_guarantee':False,'cases':results},indent=2)+'\n')
if __name__=='__main__':run(Path(__file__).parent/'results/stress.json')
