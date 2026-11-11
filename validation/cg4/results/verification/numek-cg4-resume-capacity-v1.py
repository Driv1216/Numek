"""One-shot resumption of three already-owned benchmark parents at freed slots."""
import json,os,signal,subprocess,time
from pathlib import Path
root=Path('/Users/drivyaanshyadav/Desktop/Numek');results=root/'validation/cg4/results'
plan=json.loads((results/'campaign-capacity-hold-v1.json').read_text())
dependencies=[('objective-fp-qualification-v1/false_positive-110039.json',110039),
              ('history-development-full-v1/0.json',0),
              ('geometric-curved-remainder-v1/recovery_qualification-curved_region-100039.json',100039)]
log=results/'campaign-capacity-resume-v1.jsonl'
def record(value):
    with log.open('a') as stream:stream.write(json.dumps({'at_unix':time.time(),**value},sort_keys=True)+'\n')
pending=list(zip(plan['parents'],dependencies));record({'stage':'waiting_for_existing_trial_boundaries','parents':[p['pid'] for p,_ in pending]})
end=time.monotonic()+6*3600
while pending and time.monotonic()<end:
    for parent,(relative,seed) in list(pending):
        path=results/relative
        if not path.exists():continue
        try:row=json.loads(path.read_text())
        except (json.JSONDecodeError,OSError):continue
        if row.get('seed')!=seed or row.get('status') not in {'completed','execution_failure','invalidated_source_change'}:continue
        pid=parent['pid'];expected=parent['process'].split(None,4)[4]
        actual=subprocess.run(['/bin/ps','-p',pid,'-o','uid=,command='],capture_output=True,text=True)
        fields=actual.stdout.strip().split(None,1)
        if actual.returncode or len(fields)!=2 or fields[0]!=str(os.getuid()) or fields[1]!=expected:
            record({'stage':'attention_parent_identity_changed_or_gone','pid':pid,'dependency':relative});pending.remove((parent,(relative,seed)));continue
        os.kill(int(pid),signal.SIGCONT)
        record({'stage':'resumed_exact_owned_parent','pid':pid,'dependency':relative,'dependency_status':row['status'],
                'scope':'Resumes an existing orchestration parent only; no timed worker was suspended, no new profile or estimator.'})
        pending.remove((parent,(relative,seed)))
    if pending:time.sleep(15)
record({'stage':'finished' if not pending else 'attention_wait_budget_exhausted','remaining_parent_ids':[p['pid'] for p,_ in pending]})
