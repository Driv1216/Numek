"""Free-space polling tolerates a completed worker removing its scratch root."""
import errno
from types import SimpleNamespace
import pytest
from datatrust import scalable


def test_free_space_poll_falls_back_when_scratch_disappears_between_exists_and_stat(tmp_path,monkeypatch):
    scratch=tmp_path/'scratch';scratch.mkdir();actual=scalable.os.statvfs;calls=[]
    def raced(path):
        calls.append(path)
        if path==scratch:
            scratch.rmdir()
            return actual(path)
        return SimpleNamespace(f_bavail=12345,f_frsize=4096)
    monkeypatch.setattr(scalable.os,'statvfs',raced)
    assert scalable.available(scratch)==12345*4096
    assert calls==[scratch,tmp_path]


def test_free_space_poll_does_not_hide_permission_or_io_failures(tmp_path,monkeypatch):
    def broken(path):raise PermissionError(errno.EACCES,'Synthetic denied statvfs')
    monkeypatch.setattr(scalable.os,'statvfs',broken)
    with pytest.raises(PermissionError):scalable.available(tmp_path)
