import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import stat
import tarfile
import zipfile

import pytest


def tool(name):
    directory=Path(__file__).resolve().parents[2]/'validation/cg4';sys.path.insert(0,str(directory))
    try:
        spec=importlib.util.spec_from_file_location('_cg4_review_'+name,directory/(name+'.py'))
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
    finally:sys.path.pop(0)


def test_wheel_check_detects_missing_or_stale_untracked_runtime(tmp_path):
    module=tool('package_review');package=tmp_path/'src/confidenceguard';package.mkdir(parents=True)
    (tmp_path/'src/datatrust').mkdir();(package/'__init__.py').write_bytes(b'# final\n')
    required=package/'investigation.py';required.write_bytes(b'# required untracked module\n')
    wheel=tmp_path/'delivery.whl'
    with zipfile.ZipFile(wheel,'w') as z:z.writestr('confidenceguard/__init__.py',b'# final\n')
    with pytest.raises(ValueError,match='investigation.py'):module.verify_wheel(wheel,tmp_path)
    with zipfile.ZipFile(wheel,'a') as z:z.writestr('confidenceguard/investigation.py',b'# stale\n')
    with pytest.raises(ValueError,match='investigation.py'):module.verify_wheel(wheel,tmp_path)
    with zipfile.ZipFile(wheel,'w') as z:
        z.writestr('confidenceguard/__init__.py',b'# final\n');z.writestr('confidenceguard/investigation.py',required.read_bytes())
    assert module.verify_wheel(wheel,tmp_path)['runtime_files_verified']==2
    assert not module.admitted(Path('validation/cg4/model-cache.nosync/weights.bin'))
    assert not module.admitted(Path('src/.env'))


def test_review_retains_hash_verified_referenced_synthetic_state_without_admitting_environments(tmp_path):
    module=tool('package_review');relative=Path('validation/cg4/results/review-reproduction-paired-v55/runtime.nosync/backup/objects/fact.jsonl')
    evidence=tmp_path/relative;evidence.parent.mkdir(parents=True);evidence.write_bytes(b'{"synthetic":true}\n')
    receipt=tmp_path/'validation/cg4/results/verification/selector-correction-v59-manifest.json';receipt.parent.mkdir()
    row={'path':str(relative),**module.record(evidence)}
    receipt.write_text(json.dumps({'files':[row]}))
    assert not module.admitted(relative) and module.referenced_synthetic_state(tmp_path)=={evidence}
    evidence.write_bytes(b'changed')
    with pytest.raises(ValueError,match='changed'):module.referenced_synthetic_state(tmp_path)
    for path in ['validation/cg4/py313q.nosync/pyvenv.cfg',
                 'validation/cg4/results/review-reproduction-paired-v55/runtime.nosync/environment/pyvenv.cfg',
                 '../outside.jsonl']:
        receipt.write_text(json.dumps({'files':[{**row,'path':path}]}))
        with pytest.raises(ValueError,match='not a declared|Unsafe'):module.referenced_synthetic_state(tmp_path)


def test_referenced_synthetic_link_is_refused_before_reading_outside_bytes(tmp_path,monkeypatch):
    module=tool('package_review');relative=Path('validation/cg4/results/review-reproduction-paired-v55/runtime.nosync/backup/objects/fact.jsonl')
    evidence=tmp_path/relative;evidence.parent.mkdir(parents=True);outside=tmp_path/'outside.jsonl';outside.write_bytes(b'outside')
    evidence.symlink_to(outside)
    receipt=tmp_path/'validation/cg4/results/verification/selector-correction-v59-manifest.json';receipt.parent.mkdir()
    receipt.write_text(json.dumps({'files':[{'path':str(relative),'bytes':7,'sha256':'fixture'}]}))
    def forbidden_read(path):raise AssertionError('Escaped evidence was read.')
    monkeypatch.setattr(module,'record',forbidden_read)
    with pytest.raises(ValueError,match='escaped'):module.referenced_synthetic_state(tmp_path)


def test_delivered_legacy_test_dependencies_are_included_without_model_cache(tmp_path):
    module=tool('package_review')
    for name in ['cg1','cg2','cg3','cg4']:(tmp_path/'validation'/name).mkdir(parents=True)
    required=['validation/config.py','validation/m9/fixtures.py','validation/m7/review_corrections.py',
              'validation/unlabeled/verify.py','validation/unlabeled/known_evidence.csv',
              'validation/cg1/results/reports/binary-shareable.json']
    for name in required+['tests/test_m1_analysis.py','tests/cg1/test_review_corrections.py',
                           'validation/m7/model-cache.nosync/untrusted_remote_code.py']:
        path=tmp_path/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text('fixture')
    inventory=module.source_inventory(tmp_path)
    assert all(tmp_path/name in inventory for name in required)
    assert tmp_path/'validation/m7/model-cache.nosync/untrusted_remote_code.py' not in inventory
    (tmp_path/'validation/unlabeled/known_evidence.csv').unlink()
    with pytest.raises(FileNotFoundError):module.source_inventory(tmp_path)


def bundle(root):
    module=tool('review_inventory');files={module.FINDINGS:b'[Evidence](results/negative.json)\n',
        'validation/cg4/results/negative.json':b'{"method_failed":true}\n'}
    records={name:{'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()} for name,raw in files.items()}
    for name,raw in {**files,'MANIFEST.json':json.dumps({'files':records}).encode()}.items():
        p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw)
    return module,files


def test_extracted_and_zip_checks_cover_findings_negative_evidence_and_tampering(tmp_path):
    root=tmp_path/'payload';module,files=bundle(root);archive=tmp_path/'review.zip'
    with zipfile.ZipFile(archive,'w') as z:
        for p in root.rglob('*'):
            if p.is_file():z.write(p,str(p.relative_to(root)))
    assert module.check_zip(archive)['files']==2
    assert module.check_extracted(root)['files']==2
    (root/'validation/cg4/results/negative.json').write_bytes(b'{"method_failed":false}\n')
    with pytest.raises(ValueError,match='mismatch'):module.check_extracted(root)
    with zipfile.ZipFile(archive,'a') as z:z.writestr('../outside',b'escape')
    with pytest.raises(ValueError,match='Unsafe'):module.check_zip(archive)


def test_findings_reference_cannot_be_removed_even_with_a_rewritten_manifest(tmp_path):
    root=tmp_path/'payload';module,_=bundle(root)
    path=root/'validation/cg4/results/negative.json';path.unlink()
    manifest=json.loads((root/'MANIFEST.json').read_text());del manifest['files']['validation/cg4/results/negative.json']
    (root/'MANIFEST.json').write_text(json.dumps(manifest))
    with pytest.raises(ValueError,match='Referenced findings evidence absent'):module.check_extracted(root)


@pytest.mark.parametrize('change_during_capture',[False,True,'wheel','backup'])
def test_packaging_refuses_mixed_source_and_verifies_published_fixture(tmp_path,monkeypatch,change_during_capture):
    module=tool('package_review');root=tmp_path/'repo';root.mkdir();inventory,files=bundle(root)
    for name in ('src/confidenceguard','src/datatrust','tests','docs','constraints','validation/cg1/data',
                 'validation/cg2','validation/cg3','validation/cg4/source-capsules.nosync'):
        (root/name).mkdir(parents=True,exist_ok=True)
    source=root/'src/confidenceguard/required.py';source.write_text('# frozen runtime\n')
    for name in ('README.md','METHODOLOGY.md','pyproject.toml','setup.py','.python-version','.gitignore',
                 'agents/skills/verify/skills.md','validation/__init__.py','validation/cg4/REVIEW_QUICKSTART.md'):
        p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('# fixture\n')
    (root/'validation/cg4/baseline.json').write_text(json.dumps({'head':'0'*40,'files':{}}))
    wheel=tmp_path/'runtime.whl'
    with zipfile.ZipFile(wheel,'w') as archive:archive.writestr('confidenceguard/required.py',source.read_bytes())
    backup=tmp_path/'synthetic.tar.gz'
    with tarfile.open(backup,'w:gz'):pass
    original_inventory=module.source_inventory;original_wheel=module.verify_wheel
    monkeypatch.setattr(module,'ROOT',root)
    captured=False
    def inventory_with_concurrent_delivery_change():
        nonlocal captured
        if not captured and change_during_capture in ('wheel','backup'):
            (wheel if change_during_capture=='wheel' else backup).write_bytes(b'changed after initial validation\n')
        captured=True
        return original_inventory(root)
    monkeypatch.setattr(module,'source_inventory',inventory_with_concurrent_delivery_change)
    monkeypatch.setattr(module,'verify_wheel',lambda value:original_wheel(value,root))
    def tracked_diff(command,*,cwd,stdout,check):
        assert command[:6]==['git','diff','--binary','--no-ext-diff','--no-textconv','0'*40]
        stdout.write(b'# tracked fixture patch\n')
        if change_during_capture is True:source.write_text('# concurrent change\n')
    monkeypatch.setattr(module.subprocess,'run',tracked_diff)
    output=tmp_path/'review.zip';stage=tmp_path/'stage'
    if change_during_capture:
        reason='changed while packaging' if change_during_capture is True else 'Delivery input changed during capture'
        with pytest.raises(ValueError,match=reason):module.build(stage,output,wheel,backup)
        assert not output.exists() and not output.with_suffix('.zip.sha256').exists()
    else:
        result=module.build(stage,output,wheel,backup)
        assert not result['independent_review_performed'] and not result['founder_acceptance']
        assert inventory.check_extracted(stage)['files']==result['inventory']['files']
        assert output.stat().st_mode&0o077==0
        assert result['sha256']==hashlib.sha256(output.read_bytes()).hexdigest()
        with pytest.raises(ValueError,match='never overwrite'):module.build(stage,output,wheel,backup)


@pytest.mark.parametrize('name',['C:/outside','drive:alternate-stream','./alias','a//b','a/../outside'])
def test_portable_zip_names_refuse_drive_stream_and_normalization_aliases(name):
    with pytest.raises(ValueError,match='Unsafe'):tool('review_inventory').safe_archive_path(name)


def test_zip_refuses_link_metadata_including_directory_shaped_links(tmp_path):
    module=tool('review_inventory');root=tmp_path/'payload';bundle(root)
    for name in ('link','link/'):
        archive=tmp_path/('directory-link.zip' if name.endswith('/') else 'link.zip')
        with zipfile.ZipFile(archive,'w') as z:
            for p in root.rglob('*'):
                if p.is_file():z.write(p,str(p.relative_to(root)))
            info=zipfile.ZipInfo(name);info.create_system=3;info.external_attr=(stat.S_IFLNK|0o777)<<16
            z.writestr(info,b'../outside')
        with pytest.raises(ValueError,match='member type'):module.check_zip(archive)


def test_wheel_source_symlink_is_refused_before_content_hashing(tmp_path,monkeypatch):
    module=tool('package_review');root=tmp_path/'repo';p=root/'src/confidenceguard';p.mkdir(parents=True)
    (root/'src/datatrust').mkdir();outside=tmp_path/'outside.py';outside.write_text('# authored synthetic outside source\n')
    (p/'linked.py').symlink_to(outside)
    def never_read_source(*args):raise AssertionError('Unadmitted source bytes were read')
    monkeypatch.setattr(module,'record',never_read_source)
    with pytest.raises(ValueError,match='escaped'):module.verify_wheel(tmp_path/'not-opened.whl',root)


@pytest.mark.parametrize('special',['symlink','fifo'])
def test_delivery_links_and_special_files_refuse_before_hashing_or_loading(tmp_path,special):
    import os
    module=tool('package_review');path=tmp_path/'delivery.tar.gz'
    if special=='symlink':
        target=tmp_path/'authored-synthetic-target';target.write_bytes(b'not admitted')
        path.symlink_to(target)
    else:os.mkfifo(path)
    with pytest.raises(ValueError,match='regular file'):module.delivery_input(path,'Fixture')
