"""Retained execution failures must stop resumption before another seed runs."""
import importlib.util
from pathlib import Path
import sys
import pytest


@pytest.mark.parametrize('name',['qualify_pipeline','qualify_objectives','qualify_history'])
@pytest.mark.parametrize('workers',[1,4])
@pytest.mark.parametrize('pending',[False,True])
def test_saved_worker_failure_is_not_treated_as_completed_evidence(tmp_path,monkeypatch,name,workers,pending):
    directory=Path(__file__).resolve().parents[2]/'validation/cg4';monkeypatch.syspath_prepend(str(directory))
    spec=importlib.util.spec_from_file_location('_cg4_failed_resume_'+name,directory/(name+'.py'))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    pipeline=module if name=='qualify_pipeline' else module.pipeline
    monkeypatch.setattr(pipeline,'identity',lambda:{})
    monkeypatch.setattr(pipeline,'runtime_versions',lambda:{})
    def failed(*args,**kwargs):raise RuntimeError('Synthetic worker failure retained for resumption test')
    monkeypatch.setattr(module,'trial',failed)
    common=['--panel','development']
    if name=='qualify_pipeline':
        common+=['--archetype','interaction_without_marginals'];path=tmp_path/'development-interaction_without_marginals-0.json'
        monkeypatch.setattr(module,'snapshot_sources',lambda *args:None)
    elif name=='qualify_objectives':
        objective=next(iter(module.PANELS));common=[objective]+common;path=tmp_path/(objective+'-0.json')
    else:path=tmp_path/'0.json'
    monkeypatch.setattr(sys,'argv',[name,*common,'--worker','--seed','0','--out',str(path)])
    module.main()
    if pending:
        path=path.rename(path.with_suffix('.pending'))
    before=path.read_bytes()
    def unexpected(*args,**kwargs):raise AssertionError('Another worker launched despite the retained execution failure')
    monkeypatch.setattr(module.subprocess,'run',unexpected)
    monkeypatch.setattr(sys,'argv',[name,*common,'--out',str(tmp_path),'--count','1','--workers',str(workers)])
    with pytest.raises(RuntimeError,match='pending evidence' if pending else 'saved trial'):module.main()
    assert path.read_bytes()==before
