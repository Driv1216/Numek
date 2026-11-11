"""One fixed capacity dependency, not a product scheduler."""
from pathlib import Path
import json,subprocess,sys,time
root=Path('/Users/drivyaanshyadav/Desktop/Numek')
dependency=root/'validation/cg4/results/null-reduced-capsule-v7/131999.json'
print(json.dumps({'stage':'waiting_for_reduced_complete_null_slot','dependency':str(dependency)}),flush=True)
end=time.monotonic()+6*3600
while time.monotonic()<end:
    if dependency.exists():
        try:row=json.loads(dependency.read_text())
        except (OSError,json.JSONDecodeError):row={}
        if row.get('seed')==131999 and row.get('status')=='completed':break
    time.sleep(15)
else:raise RuntimeError('Capacity dependency did not complete; inspect retained campaign before resuming.')
command=[sys.executable,'-B',str(root/'validation/cg4/run_locked_qualification.py'),'--source-identity','cfb739292ae4be4da7c0d219217858c7e4150119aac8898b7449ec7232b5fc88','qualify_partial_null.py','--panel','qualification','--count','1000','--out',str(root/'validation/cg4/results/partial-null-qualification-v1')]
print(json.dumps({'stage':'starting_locked_partial_null','seeds':[170000,170999],'qualification_success_presumed':False}),flush=True)
subprocess.run(command,cwd=root,check=True)
