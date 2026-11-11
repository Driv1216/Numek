"""Explicit local trust operation; never exposed as a browser/API job."""
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import tempfile
import shutil
import time

from .. import compat
from ..contracts import EvaluationError
from .contracts import ArtifactFile
from .adapters import capture_artifacts,Adapter,host_bindings
from .services import arguments,make_result
from .store import PreparedExecution


def _convert(spec,config,roots,staging,trusted_sha256,registrations,*,progress=None):
    started=time.monotonic();prepared=PreparedExecution(spec,config,roots,progress)
    try:
        if len(spec.predictors)!=1:raise EvaluationError('Convert exactly one trusted legacy model at a time.')
        p=spec.predictors[0]
        if p.adapter!='sklearn' or next(f for f in p.files if f.name==p.entry).sha256!=trusted_sha256:raise EvaluationError('Exact legacy bytes must be explicitly trusted.','legacy_trust_required')
        directory,_=capture_artifacts(p,roots,prepared.work,spec.limits)
        # joblib also reads ordinary pickle. This call may execute trusted code;
        # supervision is not a security sandbox and does not make it safe.
        import joblib
        import skops.io as sio
        model=joblib.load(directory/p.entry)
        path=Path(staging)/'converted.skops';sio.dump(model,path);path.chmod(0o600)
        with path.open('rb') as source:sha=hashlib.file_digest(source,'sha256').hexdigest()
        converted=replace(p,entry=path.name,files=(ArtifactFile(path.name,str(path),sha),),provenance={**p.provenance,'legacy_conversion':{'source_sha256':trusted_sha256,'explicit_operator_trust':True,'safety_or_scientific_validity_established':False}})
        prepared.spec=replace(spec,predictors=(converted,))
        adapter=Adapter(converted,spec.device,config,spec.limits,prepared.work,(*roots,str(staging)),registrations)
        prepared.attach(adapter)
        result=make_result(prepared,'registration',{'conversion':converted.provenance['legacy_conversion'],'devices':{converted.id:adapter.finish()}},started=started,staging=staging)
        prepared.verify();return result
    finally:prepared.close()


def convert_legacy_predictor(spec,*,trusted_sha256,config=None,allowed_roots=None,progress=None,cancel=None,workspace=None,request_id=None):
    spec,config,roots=arguments(spec,config,allowed_roots)
    staging=compat.protected_directory(tempfile.mkdtemp(prefix='numek-cg6-conversion-',dir=config.scratch_directory))
    try:
        result=compat.supervise(_convert,(spec,config,roots,str(staging),trusted_sha256,host_bindings()),replace(config,result_bytes=config.private_bytes+config.result_bytes),progress=progress,cancel=cancel)
        if cancel is not None and cancel.is_set():raise EvaluationError('Cancelled before legacy conversion publication.','cancelled')
        result.seal()
        if len(result.json_text().encode())>config.private_bytes or len(json.dumps(result.to_dict()).encode())>config.result_bytes:raise EvaluationError('Converted predictor metadata exceeds result admission.','result_limit')
        if workspace:
            from .storage import save_result
            save_result(workspace,result,request_id=request_id,cancel=cancel)
        return result
    except BaseException:shutil.rmtree(staging,ignore_errors=True);raise
