"""CG6 artifacts inside the existing v2 immutable catalog, without SQL migration."""
import copy
from pathlib import Path
import uuid

from ..contracts import EvaluationError,digest
from ..history_storage import EvidenceWriter
from ..investigation_storage import write_packet


def save_result(workspace,result,*,request_id=None,cancel=None,request_digest=None):
    from ..workspace import ReliabilityWorkspace
    ws=ReliabilityWorkspace(workspace) if isinstance(workspace,(str,Path)) else workspace
    cat=ws.catalog
    if cat.catalog_version<2:raise EvaluationError('Use the established backed-up migration to catalog v2.','migration_required')
    request_id=request_id or uuid.uuid4().hex
    request_digest=request_digest or digest(result.to_private_dict())
    with cat.operation():
        operation,previous=cat.begin(request_id,request_digest,require_saving=False)
        if previous:return previous
        writer=EvidenceWriter(cat.root/'staging'/operation,cat.config,operation)
        dependencies=set();old_private=copy.deepcopy(result.private)
        from contextlib import closing
        with closing(cat._connect()) as db:
            parent=result.data['cg6'].get('parent_analysis_id')
            if parent:dependencies.update(r[0] for r in db.execute("SELECT object_id FROM facts WHERE kind='assessment' AND key=?",(digest([parent]),)))
            reservation=result.private.get('evidence_use_reservation') or {}
            if reservation.get('evidence_use_id'):dependencies.update(r[0] for r in db.execute("SELECT object_id FROM facts WHERE kind='evidence_use' AND key=?",(digest([reservation['evidence_use_id']]),)))
        locations=result.private.setdefault('retained_binary_paths',{})
        try:
            artifact=result.private.get('output_artifact')
            if artifact:
                descriptor=writer.add_blob(artifact['path'],format='cg6_predictions_jsonl_v1',identity=[result.data['analysis_id'],'predictions'])
                if descriptor['sha256']!=artifact['sha256'] or descriptor['bytes']!=artifact['bytes']:raise EvaluationError('Output changed before retention.','source_changed')
                result.private['output_artifact']={**artifact,'path':str(cat.root/'objects'/(descriptor['object_id']+'.cgblob')),'object_id':descriptor['object_id']}
                dependencies.add(descriptor['object_id'])
                locations[result.private['output_artifact']['path']]=descriptor['object_id']
            retained={}
            contribution=result.private.get('contribution_artifact')
            if contribution:
                descriptor=writer.add_blob(contribution['path'],format='cg6_root_contributions_jsonl_v1',identity=[result.data['analysis_id'],'root_contributions'])
                if descriptor['sha256']!=contribution['sha256']:raise EvaluationError('Contributions changed before retention.','source_changed')
                dependencies.add(descriptor['object_id']);result.private['contribution_artifact']={**contribution,'path':str(cat.root/'objects'/(descriptor['object_id']+'.cgblob')),'object_id':descriptor['object_id']}
                locations[result.private['contribution_artifact']['path']]=descriptor['object_id']
            media={}
            for path,info in result.private.get('variant_assets',{}).items():
                descriptor=writer.add_blob(path,format='cg6_variant_media',identity=[result.data['analysis_id'],'media',info['sha256']])
                dependencies.add(descriptor['object_id']);media[path]={**info,'path':str(cat.root/'objects'/(descriptor['object_id']+'.cgblob'))}
                locations[media[path]['path']]=descriptor['object_id']
            result.private['variant_assets']=media
            for pid,p in result.private.get('predictors',{}).items():
                retained[pid]=[]
                if p.get('retention')=='reference':
                    result.private.setdefault('external_model_dependencies',{})[pid]={'files':p['files'],'unchanged_external_files_required_for_execution':True}
                    continue
                for f in p['files']:
                    descriptor=writer.add_blob(f['path'],format='predictor_artifact',identity=[result.data['analysis_id'],pid,f['name']],source_roots=(str(Path(f['path']).parent),))
                    if descriptor['sha256']!=f['sha256']:raise EvaluationError('Model changed before retention.','model_changed')
                    dependencies.add(descriptor['object_id'])
                    retained[pid].append({**f,'path':str(cat.root/'objects'/(descriptor['object_id']+'.cgblob')),'object_id':descriptor['object_id']})
                    locations[retained[pid][-1]['path']]=descriptor['object_id']
            result.private['retained_predictor_files']=retained
            # Preserve auxiliary binaries as well as their data-only descriptors.
            for a in result.private.get('auxiliary_artifacts',[]):
                for p in a.get('predictors',[]):
                    files=[]
                    for f in p['files']:
                        d=writer.add_blob(f['path'],format='auxiliary_model',identity=[result.data['analysis_id'],a['artifact_digest'],p['id'],f['name']],source_roots=(str(Path(f['path']).parent),))
                        dependencies.add(d['object_id']);files.append({**f,'path':str(cat.root/'objects'/(d['object_id']+'.cgblob'))})
                        locations[files[-1]['path']]=d['object_id']
                    p['files']=files
            result.seal()
            payload={'result':result.to_private_dict(),'manifest':result.private,'depends_on_objects':sorted(dependencies)}
            write_packet(writer,'assessment',[result.data['analysis_id']],payload)
            writer.finish({'assessment_id':result.data['analysis_id']})
            receipt=cat.commit_capture(operation,cancel=cancel,receipt_extra={'assessment_id':result.data['analysis_id']})
            result._workspace_location=str(cat.root)
            return receipt
        except BaseException:
            result.private=old_private;result.seal();raise


def retained_predictor(workspace,assessment_id,predictor_id):
    result=workspace.open(assessment_id)
    p=copy.deepcopy(result.private['predictors'][predictor_id])
    retained=result.private.get('retained_predictor_files',{}).get(predictor_id)
    if retained is None:raise EvaluationError('Model bytes were not retained.','model_unavailable')
    if p.get('retention')=='reference':
        from .contracts import PredictorSpec
        return PredictorSpec.from_dict(p)
    p['files']=[{**{k:v for k,v in f.items() if k!='object_id'},'path':result.retained_path(f['path'])} for f in retained]
    from .contracts import PredictorSpec
    return PredictorSpec.from_dict(p)
