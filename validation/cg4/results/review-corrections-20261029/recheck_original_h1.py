from pathlib import Path
import tempfile,runpy,json,hashlib

def main():
 root=Path.cwd();evidence=root/'validation/cg4/results/review-corrections-20261029';script=evidence/'reviewer-original/temporal_probe.py'
 module=runpy.run_path(str(script));mkdtemp=tempfile.mkdtemp
 def redirected(*args,**kwargs):
  kwargs['dir']='/private/tmp/numek-cg4-corrections';return mkdtemp(*args,**kwargs)
 tempfile.mkdtemp=redirected
 try:
  try:module['main']()
  except Exception as error:
   tb=error.__traceback__;frame=None
   while tb:
    if tb.tb_frame.f_code.co_name=='main' and tb.tb_frame.f_code.co_filename==str(script):frame=tb.tb_frame
    tb=tb.tb_next
   assert frame is not None
   values=frame.f_locals
   from confidenceguard import investigate,EvaluationError
   assert isinstance(error,EvaluationError)
   historical=values['historical_result'];live=investigate(values['live'])
   states={'live':module['states'](values['live']),'retained':module['states'](values['history_spec'])}
   assert states['live']==states['retained'] and all(set(v)=={'unavailable'} for v in states['live'].values())
   assert live.data['investigation']['candidates']==historical.data['investigation']['candidates']==[]
   record={'reviewer_script_sha256':hashlib.sha256(script.read_bytes()).hexdigest(),'execution':'Original reviewer script under installed corrected wheel; only disposable tempfile output root redirected','states':states,'live_candidates':0,'retained_candidates':0,'freeze_refused':True,'refusal':str(error),'H_metrics_disclosed':False}
   (evidence/'H1-after.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record))
  else:raise AssertionError('Original counterexample unexpectedly completed confirmation')
 finally:tempfile.mkdtemp=mkdtemp

if __name__=='__main__':main()
