"""Fixed two-scenario historical qualification, serial and source locked."""
from pathlib import Path
import json,subprocess,sys
root=Path('/Users/drivyaanshyadav/Desktop/Numek')
identity='cfb739292ae4be4da7c0d219217858c7e4150119aac8898b7449ec7232b5fc88'
out=root/'validation/cg4/results/history-qualification-group-v1';out.mkdir(exist_ok=True)
profile={'source_identity':identity,'scenarios':['current_risk_shift','reference_only_shift'],'seeds':[120000,120039],'qualification_success_presumed':False,'scope':'Serial original locked recovery panels; no formal confirmation or controlled relative-resource claim.'}
p=out/'group-profile.json'
if p.exists() and json.loads(p.read_text())!=profile:raise RuntimeError('Prior campaign differs.')
if not p.exists():p.write_text(json.dumps(profile,indent=2,sort_keys=True)+'\n')
for scenario in profile['scenarios']:
    print(json.dumps({'scenario':scenario,'stage':'starting_or_resuming'}),flush=True)
    with (out/(scenario+'.log')).open('ab',buffering=0) as log:
        subprocess.run([sys.executable,'-B',str(root/'validation/cg4/run_locked_qualification.py'),'--source-identity',identity,'qualify_history.py','--panel','qualification','--scenario',scenario,'--count','40','--out',str(out/scenario)],cwd=root,stdout=log,stderr=subprocess.STDOUT,check=True)
    print(json.dumps({'scenario':scenario,'stage':'raw_trials_complete','qualification_conclusion':'requires_complete_panel_audit'}),flush=True)
