"""Exercise the production exact rank primitive above its memory budget."""
from pathlib import Path
import json
import tempfile
import threading
import time
from datatrust import DatasetInput,DatasetSpec,TaskSpec,ExecutionOptions
from datatrust.scalable import Workspace,quantiles,inventory


def run():
    with tempfile.TemporaryDirectory(prefix='numek-external-sort-') as tmp:
        p=Path(tmp)/'seed.csv';p.write_text('x\n1\n');item=DatasetInput('seed','dataset',DatasetSpec(str(p)),TaskSpec('dataset_profile'))
        work=Workspace(ExecutionOptions(memory_bytes=32*1024**2,threads=1),[item]);stop=threading.Event();peak=[0];n=2000000
        def monitor():
            while not stop.wait(.02):
                _,files=inventory(work.root);peak[0]=max(peak[0],sum(f['bytes'] for f in files if f['file'].startswith('spill/')))
        thread=threading.Thread(target=monitor);thread.start()
        try:
            work.con.execute(f'CREATE TABLE ordered_input AS SELECT i+1 _row,((i*104729)%{n})::BIGINT x FROM range({n}) t(i)')
            started=time.monotonic();q=quantiles(work.con,'ordered_input','x','true')
            expected=[(n-1)*v for v in (.01,.05,.25,.5,.75,.95,.99)]
            assert q==expected,(q,expected)
            record={'rows':n,'engine_memory_bytes':32*1024**2,'production_method':'exact externally ordered ranks with linear interpolation','peak_spill_bytes':peak[0],'seconds':time.monotonic()-started,'quantiles':q,'independent_quantiles':expected,'passed':True}
            assert peak[0]>0,'Workload must force external spill.'
            destination=Path(__file__).parent/'results/external-sort.json';destination.write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record,indent=2))
        finally:stop.set();thread.join();work.close()

if __name__=='__main__':run()
