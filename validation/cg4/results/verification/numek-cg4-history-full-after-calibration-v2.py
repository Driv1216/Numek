"""One fixed benchmark dependency; no product scheduler or new method selection."""
import json,subprocess,time
from pathlib import Path
root=Path('/Users/drivyaanshyadav/Desktop/Numek')
dependency=root/'validation/cg4/results/objective-calibration-residual-qualification-v1/calibration_residual-110039.json'
print(json.dumps({'stage':'waiting_for_existing_calibration_campaign_slot','dependency':str(dependency)}),flush=True)
end=time.monotonic()+6*3600
while time.monotonic()<end:
    if dependency.exists():
        try:row=json.loads(dependency.read_text())
        except (OSError,json.JSONDecodeError):row={}
        if row.get('seed')==110039 and row.get('objective_panel')=='calibration_residual' and row.get('status')=='completed':break
    time.sleep(15)
else:raise RuntimeError('Capacity dependency did not complete within the one-shot wait budget; inspect existing evidence before resuming.')
command=[str(root/'validation/cg4/py313q.nosync/bin/python'),'-B',str(root/'validation/cg4/run_locked_qualification.py'),
    '--source-identity','e8b8f8ebbf654d8c43f3075f9b26574e42a44126999d252e0a20e7d05e1c3f23','qualify_history.py',
    '--panel','development','--scenario','reference_only_shift','--full-profile','--offset','1','--count','1',
    '--out',str(root/'validation/cg4/results/history-reference-only-development-full-v1')]
print(json.dumps({'stage':'starting_fixed_full_size_historical_development','source_identity':command[4],'qualification_success_presumed':False}),flush=True)
subprocess.run(command,cwd=root,check=True)
