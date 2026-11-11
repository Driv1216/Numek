"""Verify relocated immutable artifacts by bytes, separately from live files."""
from .. import compat
from ..contracts import EvaluationError


def verify_artifact(info,roots,*,check=None):
    observed,_,_=compat.capture(info['path'],roots,check=check)
    # Retention changes the inode and signature. Content-addressed evidence binds
    # its digest and size; live source capture separately binds its signature.
    if observed['sha256']!=info['sha256'] or observed['bytes']!=info['bytes']:
        raise EvaluationError('Retained artifact bytes changed.','evidence_changed')
    return observed
