"""Resume only unmeasured profiles; never overwrite a completed measurement."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parent

def main():
    protocol=json.loads((ROOT/'performance_protocol.json').read_text())
    retained=[]
    for name in protocol['profiles']:
        receipt=ROOT/'results/performance'/name/'receipt.json'
        if receipt.exists():
            value=json.loads(receipt.read_text())
            if not value['passed']:raise RuntimeError('Resolve failed profile before continuing: '+name)
            retained.append({'name':name,'receipt_sha256':hashlib.sha256(receipt.read_bytes()).hexdigest()})
    record={'reason':'Restart before first risk fit to load balanced-role risk fixture; preserve completed profiles',
        'completed_reused':retained,'threshold_or_size_changes':False,
        'fixture_source_sha256':hashlib.sha256((ROOT/'performance.py').read_bytes()).hexdigest(),
        'original_fixture_sha256':hashlib.sha256((ROOT/'performance-before-risk-fixture.py').read_bytes()).hexdigest(),
        'protocol_sha256':hashlib.sha256((ROOT/'performance_protocol.json').read_bytes()).hexdigest(),
        'interrupted_unmeasured':'quantiles-histogram (no completed receipt); restarted with unchanged profile',
        'source_change':'CG6 browser export progress/cancel wiring only; numerical source unchanged'}
    (ROOT/'results/performance-resumption.json').write_text(json.dumps(record,indent=2)+'\n')
    for name in protocol['profiles']:
        if (ROOT/'results/performance'/name/'receipt.json').exists():continue
        print('MEASURING '+name,flush=True)
        subprocess.run([sys.executable,'-B',str(ROOT/'performance.py'),'measure','--name',name],check=True)

if __name__=='__main__':main()
