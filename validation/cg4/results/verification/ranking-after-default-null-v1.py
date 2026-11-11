"""Fixed validation-only capacity handoff; no product scheduler or analytics changes."""
import json
from pathlib import Path
import subprocess
import sys
import time
ROOT=Path('/Users/drivyaanshyadav/Desktop/Numek')
sys.path.insert(0,str(ROOT/'validation/cg4'))
from summarize_null import summarize,joint_diagnostic
from run_locked_qualification import sha
result_root=ROOT/'validation/cg4/results'
last=result_root/'null-default-capsule-v3/default_full_pipeline_null-interaction_without_marginals-140199.json'
source='d8f73aaacf3d835d4323561e94336fccef453cdc6db5c985af2357b4084dcc46'
print(json.dumps({'stage':'waiting_for_existing_default_null_slot','dependency':str(last),'next':'fixed original ranking objective group','source_identity':source}),flush=True)
end=time.monotonic()+24*3600
while not last.is_file():
    if time.monotonic()>end:raise RuntimeError('Dependency deadline reached; inspect preserved evidence.')
    time.sleep(15)
default=summarize(result_root/'null-default-capsule-v3')
reduced=summarize(result_root/'null-reduced-capsule-v7')
for filename,record in [('null-default-summary-v1.json',default),('null-complete-joint-summary-v1.json',{'reduced':reduced,'default':default,'joint_diagnostic':joint_diagnostic(reduced,default)})]:
    record['aggregation_source_sha256']=sha(ROOT/'validation/cg4/summarize_null.py')
    path=result_root/filename
    if path.exists() and json.loads(path.read_text())!=record:raise RuntimeError('Different prior completed-null summary; preserve before continuing.')
    if not path.exists():path.write_text(json.dumps(record,sort_keys=True,indent=2,allow_nan=False)+'\n')
print(json.dumps({'stage':'complete_null_audited','joint_diagnostic':joint_diagnostic(reduced,default)}),flush=True)
subprocess.run([sys.executable,'-B',str(ROOT/'validation/cg4/run_objective_campaign.py'),'--group','ranking','--source-identity',source,'--out',str(result_root/'objective-ranking-group-v1')],cwd=ROOT,check=True)
