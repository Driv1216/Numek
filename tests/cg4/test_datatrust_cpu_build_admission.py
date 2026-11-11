"""CPU local tags require distinct provenance, without accepting newer runtimes."""
from types import SimpleNamespace
import pytest
from datatrust import text_models,image_models


@pytest.mark.parametrize('torch_version',['2.8.0','2.8.0+cpu'])
def test_exact_supported_versions_and_actual_build_identity(monkeypatch,torch_version,tmp_path):
    versions={**text_models.RUNTIME,'torch':torch_version}
    monkeypatch.setattr(text_models.importlib.metadata,'version',versions.__getitem__)
    assert text_models.pinned_runtime('text-embeddings')==versions
    assert text_models.RUNTIME['torch']=='2.8.0'  # existing profile is not relabeled
    class FileAdmissionReached(Exception):pass
    def marker(*args,**kwargs):raise FileAdmissionReached()
    monkeypatch.setattr(text_models,'capture',marker);monkeypatch.setattr(image_models,'capture',marker)
    with pytest.raises(FileAdmissionReached):text_models.preflight(SimpleNamespace(language=False,embedding_directory=str(tmp_path)))
    with pytest.raises(FileAdmissionReached):image_models.preflight(SimpleNamespace(directory=str(tmp_path)))


@pytest.mark.parametrize('package,version',[
    ('torch','2.10.0'),('torch','2.8.0+cu128'),('torch','2.8.0+cpu.local'),
    ('torch','2.8.0.dev1'),('transformers','4.57.2'),('safetensors','0.6.2+local')])
def test_other_builds_and_versions_remain_rejected(monkeypatch,package,version):
    versions={**text_models.RUNTIME,package:version}
    monkeypatch.setattr(text_models.importlib.metadata,'version',versions.__getitem__)
    with pytest.raises(ValueError,match='pinned text-embeddings'):text_models.pinned_runtime('text-embeddings')


def test_missing_optional_runtime_is_a_named_admission_failure(monkeypatch):
    def missing(package):raise text_models.importlib.metadata.PackageNotFoundError(package)
    monkeypatch.setattr(text_models.importlib.metadata,'version',missing)
    with pytest.raises(ValueError,match='pinned image-embeddings'):text_models.pinned_runtime('image-embeddings')
