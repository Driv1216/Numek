"""Shared native-operation supervision for local M4/M5 jobs."""
import json
import multiprocessing
from pathlib import Path
import shutil
import time
import psutil
from datatrust.contracts import AnalysisError
from datatrust.scalable import fail, available, owned_inventory

def _entry(pipe,operation,arguments):
    latest = {}
    def progress(value):
        latest.update(value)
        pipe.send(('progress',value))
    try:
        result=operation(*arguments,progress=progress)
        pipe.send(('result',result))
    except Exception as exc:
        pipe.send(('error',{'message':str(exc),'code':getattr(exc,'code','analysis_failed'),'stage':getattr(exc,'stage',latest.get('stage','worker')),'type':type(exc).__name__}))
    finally:pipe.close()


def run_supervised(operation, arguments, options, *, progress=None, cancel=None, owned_snapshots=()):
    context=multiprocessing.get_context('spawn');receiver,sender=context.Pipe(duplex=False)
    process=context.Process(target=_entry,args=(sender,operation,arguments),daemon=True)
    started=time.monotonic();process.start();sender.close();root=None;peak_rss=0;peak_workspace=0;peak_spill=0;result=None
    try:
        monitor=psutil.Process(process.pid)
        while True:
            if cancel is not None and cancel.is_set():fail('Analysis cancelled; no completed result was published.','cancelled')
            if time.monotonic()-started>options.max_seconds:fail('Whole-job deadline exceeded; worker terminated.','deadline')
            try:rss=monitor.memory_info().rss;peak_rss=max(peak_rss,rss)
            except psutil.NoSuchProcess:rss=0
            if rss>options.max_rss_bytes:fail(f'Worker RSS {rss} bytes exceeded configured termination threshold {options.max_rss_bytes}.','rss_limit')
            if root and root.exists():
                owned,files=owned_inventory(root,owned_snapshots)
                peak_workspace=max(peak_workspace,owned)
                peak_spill=max(peak_spill,sum(f['bytes'] for f in files if f['file'].startswith('spill/')))
                if owned>options.workspace_bytes:fail(f'Workspace {owned} bytes exceeds budget {options.workspace_bytes}.')
                if available(root)<options.free_disk_bytes:fail('Scratch free-space reserve was breached during execution.','disk_exhausted')
                if any(available(path)<options.free_disk_bytes for path in owned_snapshots):fail('Owned-upload free-space reserve was breached.','disk_exhausted')
            if receiver.poll(.1):
                try:kind,value=receiver.recv()
                except EOFError:break
                if kind=='progress':
                    if 'owned_workspace' in value:root=Path(value.pop('owned_workspace'))
                    if progress:progress(value)
                elif kind=='error':raise AnalysisError(value['message'],code=value['code'],stage=value['stage'])
                elif kind=='result':result=value;break
            if not process.is_alive() and not receiver.poll():break
        process.join(2)
        if result is None:fail(f'Worker exited without completed evidence (exit {process.exitcode}).','worker_terminated')
        result.execution.update(peak_worker_rss_bytes=peak_rss,whole_job_seconds=time.monotonic()-started,peak_spill_bytes=peak_spill)
        result.execution['peak_workspace_bytes']=max(result.execution['peak_workspace_bytes'],peak_workspace)
        # Parent-added supervision metadata belongs to the serialized-result budget too.
        for _ in range(2):result.execution['serialized_bytes']=len(result.json_text().encode('utf-8'))
        if len(result.json_text().encode('utf-8'))>options.result_bytes:fail('Final serialized result exceeds its job budget after supervision metadata. Reduce detail bounds.','result_limit')
        return result
    except BaseException as exc:
        exc.execution={'status':'failed','peak_worker_rss_bytes':peak_rss,'peak_workspace_bytes':peak_workspace,'peak_spill_bytes':peak_spill,'whole_job_seconds':time.monotonic()-started,'max_rss_bytes':options.max_rss_bytes,'sampled_rss_overshoot_bytes':max(0,peak_rss-options.max_rss_bytes),'completed_result_published':False}
        raise
    finally:
        if process.is_alive():process.terminate();process.join(3)
        if process.is_alive():process.kill();process.join()
        receiver.close()
        if root and root.exists():
            marker=root/'owner.json'
            if marker.is_file() and not marker.is_symlink() and json.loads(marker.read_text()).get('pid')==process.pid:shutil.rmtree(root)

