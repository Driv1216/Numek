"""Validation orchestration cannot duplicate seeds or conceal failed trials."""
import importlib.util
from pathlib import Path
import threading
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest


def tool():
    path=Path(__file__).resolve().parents[2]/'validation/cg4/parallel_qualification.py'
    spec=importlib.util.spec_from_file_location('_cg4_parallel',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def test_bounded_parallel_seeds_each_run_once_without_changing_their_identity():
    module=tool();lock=threading.Lock();active=0;maximum=0;seen=[]
    barrier=threading.Barrier(4)
    def run(seed):
        nonlocal active,maximum
        with lock:active+=1;maximum=max(maximum,active);seen.append(seed)
        barrier.wait(timeout=10)
        with lock:active-=1
    module.run_fixed_seeds(range(8),4,run)
    assert maximum==4 and sorted(seen)==list(range(8)) and active==0
    for workers in [0,5,True,1.5]:
        with pytest.raises(ValueError):module.run_fixed_seeds([1,2],workers,run)
    with pytest.raises(ValueError):module.run_fixed_seeds([1,1],1,run)


def test_failure_keeps_running_trials_and_stops_queued_trials(monkeypatch):
    module=tool();started=threading.Event();release=threading.Event();stopped=threading.Event();seen=[]
    monkeypatch.setattr(module,'threading',SimpleNamespace(Event=lambda:stopped))
    def run(seed):
        if seed==0:
            started.set();assert release.wait(timeout=10);seen.append(0)
        elif seed==1:
            assert started.wait(timeout=10)
            raise RuntimeError('preserved failed seed')
        else:
            pytest.fail('Queued seed started after failure.')
    with ThreadPoolExecutor(max_workers=1) as pool:
        future=pool.submit(module.run_fixed_seeds,range(20),2,run)
        assert stopped.wait(timeout=10)
        release.set()
        with pytest.raises(RuntimeError,match='preserved failed seed'):future.result(timeout=10)
    assert seen==[0]


def test_serial_execution_stops_at_first_failure_and_output_remains_json(capsys):
    module=tool();seen=[]
    def run(seed):
        seen.append(seed)
        module.emit({'seed':seed})
        if seed==2:raise RuntimeError('failed')
    with pytest.raises(RuntimeError):module.run_fixed_seeds(range(5),1,run)
    assert seen==[0,1,2]
    assert capsys.readouterr().out.splitlines()==['{"seed": 0}','{"seed": 1}','{"seed": 2}']


def test_current_helper_identity_is_required_and_verified(tmp_path,monkeypatch):
    directory=Path(__file__).resolve().parents[2]/'validation/cg4'
    monkeypatch.syspath_prepend(str(directory))
    from summarize_recovery import audit_runner,sha
    target=tmp_path/'validation/cg4';target.mkdir(parents=True)
    files={'diagnostics_harness_sha256':'qualification_diagnostics.py','parallel_seed_runner_sha256':'parallel_qualification.py'}
    for name in files.values():(target/name).write_text(name)
    profile={field:sha(target/name) for field,name in files.items()}
    audit_runner(profile,tmp_path,required=True)
    audit_runner({},tmp_path)  # legacy source profiles predate these fields
    with pytest.raises(RuntimeError,match='required'):audit_runner({},tmp_path,required=True)
    (target/'parallel_qualification.py').write_text('changed')
    with pytest.raises(RuntimeError,match='differs'):audit_runner(profile,tmp_path,required=True)
