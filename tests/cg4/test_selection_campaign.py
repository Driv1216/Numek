import importlib.util
import json
from pathlib import Path
import sys

import pytest


def tool(monkeypatch):
    directory=Path(__file__).resolve().parents[2]/'validation/cg4';monkeypatch.syspath_prepend(str(directory))
    spec=importlib.util.spec_from_file_location('_cg4_selection_campaign',directory/'run_selection_campaign.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def test_sequence_uses_fresh_locked_panels_and_does_not_repeat_existing_broad(tmp_path,monkeypatch):
    module=tool(monkeypatch);protocol,jobs=module.panels(module.ROOT,tmp_path)
    assert protocol['seed_panels']['recovery_qualification']['start']==300000
    assert not any(kind=='recovery' and name==module.BROAD for kind,name,*_ in jobs)
    objectives=[name for kind,name,*_ in jobs if kind=='objective']
    # The live generator adds the separate R2 protocol 1.2 anchor. The running
    # old-source campaign keeps its immutable fourteen-objective profile.
    assert len(objectives)==15 and {'paired_precision','regression_r2'} <= set(objectives)
    assert len(jobs)==len({job[-1] for job in jobs})
    assert jobs[-2][1]=='reduced_full_pipeline_null' and jobs[-1][1]=='default_full_pipeline_null'
    assert all(destination.is_relative_to(tmp_path) for *_,destination in jobs)


def test_missing_or_failed_dependency_never_becomes_completed_or_fresh(tmp_path,monkeypatch):
    module=tool(monkeypatch);paths=[tmp_path/'first.json',tmp_path/'second.json']
    paths[0].write_text(json.dumps({'status':'completed'}))
    with pytest.raises(RuntimeError,match='incomplete'):module.wait_for_completed(paths,timeout=0)
    paths[1].write_text(json.dumps({'status':'execution_failure'}))
    with pytest.raises(RuntimeError,match='Failed dependency'):module.wait_for_completed(paths,timeout=0)
    paths[1].write_text(json.dumps({'status':'completed'}));module.wait_for_completed(paths,timeout=0)
    with pytest.raises(RuntimeError,match='target failed'):module.require_recovery({'source_identity':'current','anchor_criterion_met':False},'current')
    with pytest.raises(RuntimeError,match='target failed'):module.require_recovery({'source_identity':'current'},'current')
    with pytest.raises(RuntimeError,match='different source'):module.require_recovery({'source_identity':'old','anchor_criterion_met':True},'current')
    module.require_recovery({'source_identity':'current','anchor_criterion_met':True},'current')


def test_campaign_refuses_different_saved_evidence(tmp_path,monkeypatch):
    module=tool(monkeypatch);path=tmp_path/'record.json';original={'method_failure':True}
    module.save(path,original);raw=path.read_bytes();module.save(path,original)
    with pytest.raises(RuntimeError,match='different prior'):module.save(path,{'method_failure':False})
    assert path.read_bytes()==raw


def test_duplicate_driver_refuses_before_waiting_or_launching_trials(tmp_path,monkeypatch):
    from confidenceguard.contracts import EvaluationError
    module=tool(monkeypatch)
    monkeypatch.setattr(module,'snapshot',lambda identity:(module.ROOT,identity))
    monkeypatch.setattr(sys,'argv',['campaign','--source-identity','fixture','--broad-directory',str(tmp_path/'broad'),'--out',str(tmp_path)])
    with module.file_lock(tmp_path/'.campaign.lock'):
        with pytest.raises(EvaluationError,match='busy'):module.main()


def test_driver_forwards_its_actual_interpreter_to_locked_trials(tmp_path,monkeypatch):
    module=tool(monkeypatch);broad=tmp_path/'broad';broad.mkdir();out=tmp_path/'out'
    (broad/f'recovery_qualification-{module.BROAD}-0.json').write_text('{"status":"completed"}')
    monkeypatch.setattr(module,'snapshot',lambda identity:(module.ROOT,identity))
    monkeypatch.setattr(module,'sha',lambda path:'fixture-hash')
    monkeypatch.setattr(module,'panels',lambda capsule,out:({'seed_panels':{'recovery_qualification':{'start':0,'count':1}}},
        [('recovery','fixture','qualify_pipeline.py',['--panel','recovery_qualification'],out/'fixture')]))
    monkeypatch.setattr(module,'recover_panel',lambda path:{'source_identity':'fixture','anchor_criterion_met':True})
    captured=[]
    def intercept(command,**kwargs):
        captured.append(command);raise RuntimeError('Captured before analytical execution')
    monkeypatch.setattr(module.subprocess,'run',intercept)
    monkeypatch.setattr(sys,'argv',['campaign','--source-identity','fixture','--broad-directory',str(broad),'--out',str(out)])
    with pytest.raises(RuntimeError,match='Captured'):module.main()
    command,=captured
    assert command[command.index('--python')+1]==sys.executable
    assert command[command.index('--workers')+1]=='4'
    assert command[command.index('--source-identity')+1]=='fixture'
