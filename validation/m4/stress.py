"""Forced spill, grouping-before-join and exact external ordering evidence."""
from dataclasses import replace
import json
from pathlib import Path
import tempfile
import time
from datatrust import *


def run():
    with tempfile.TemporaryDirectory(prefix='numek-m4-spill-') as tmp:
        root=Path(tmp);n=1000000;inputs=[]
        for role in ('train','test'):
            p=root/(role+'.csv')
            with p.open('w') as f:
                f.write('id,measurement,context\n')
                for start in range(0,n,10000):f.writelines(f'{i:08d},{i%100000},{"x"*300}{i:08d}\n' for i in range(start,min(start+10000,n)))
            inputs.append(DatasetInput(role,role,DatasetSpec(str(p)),TaskSpec('dataset_profile'),AnalysisConfig(features=FeatureOptions({'id':'identifier','measurement':'quantitative','context':'identifier'}))))
        options=ExecutionOptions(memory_bytes=512*1024**2,batch_bytes=4*1024**2,max_seconds=600)
        started=time.monotonic();result=DataTrust.compare(ComparisonSpec('splits',tuple(inputs),identity_keys=(('id',),),evaluation_intent='overlap_permitted'),ComparisonConfig(execution=options))
        integrity=result.coverage['measurements']['train:test.split_integrity']
        assert integrity['records']['multiset_intersection']==n
        assert integrity['features']['left_rows']==n and integrity['units'][0]['shared_distinct_groups']==n
        assert result.coverage['measurements']['train:test.populations']['columns'][1]['cdf_distance']==0
        record={'status':result.execution['status'],'source_rows_each':n,'combined_source_bytes':sum(Path(i.dataset.path).stat().st_size for i in inputs),'engine_memory_bytes':options.memory_bytes,'execution':result.execution,'elapsed_seconds':time.monotonic()-started,'full_equality_verified':True,'external_ordering_method':'row_number over ordered finite values; full empirical CDF ordered frequencies','peak_spill_bytes':result.execution['peak_spill_bytes']}
        destination=Path(__file__).parent/'results/spill-join-sort.json';destination.write_text(json.dumps(record,indent=2)+'\n');print(json.dumps({k:v for k,v in record.items() if k!='execution'},indent=2))

if __name__=='__main__':run()
