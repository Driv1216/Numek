"""Immutable CG4 assessments using the common report and artifact coordinator."""
import copy
import json
from .contracts import EvaluationError,digest,strict_json
from .result import EvaluationResult,SharedResult
from .investigation_contracts import INVESTIGATION_RESULT,CONFIRMATION_RESULT,INVESTIGATION_METHOD


class InvestigationResult(EvaluationResult):
    @property
    def source_paths(self):
        paths=[v['path'] for v in self.private['files'].values() if v.get('path')]
        root=getattr(self,'_workspace_location',self.private.get('workspace_path') or self.private.get('evidence_workspace_path'))
        if root:paths.append(root)
        return tuple(paths)

    @classmethod
    def from_dict(cls,value,*,private=None):
        if isinstance(value,str):value=strict_json(value)
        if not isinstance(value,dict) or value.get('schema_version') not in {INVESTIGATION_RESULT,CONFIRMATION_RESULT} or value.get('methodology_id')!=INVESTIGATION_METHOD:
            raise EvaluationError('Unsupported CG4 completed evidence.')
        if value.get('audience')=='shareable':
            if private is not None or value.get('projection_digest')!=digest({k:v for k,v in value.items() if k!='projection_digest'}):raise EvaluationError('CG4 projection binding differs.')
            return SharedResult(copy.deepcopy(value))
        if not isinstance(private,dict) or private.get('schema')!='confidenceguard.investigation_private/1.0':raise EvaluationError('Protected CG4 manifest required.')
        binding=value.get('binding',{});payload={k:v for k,v in value.items() if k!='binding'}
        if binding!={'analysis_digest':digest(payload),'private_manifest_digest':digest(private)} or private.get('analysis_digest')!=digest(payload) or private.get('analysis_id')!=value.get('analysis_id'):
            raise EvaluationError('CG4 result and protected evidence differ.','evidence_changed')
        if not isinstance(value.get('investigation'),dict) or not isinstance(value.get('coverage'),dict):raise EvaluationError('Invalid CG4 result shape.')
        from .investigation_membership import validate
        for artifact in private.get('artifacts',{}).values():validate(artifact,models=private.get('models',{}))
        return cls({k:copy.deepcopy(v) for k,v in value.items() if k not in {'binding','execution'}},copy.deepcopy(private),copy.deepcopy(value.get('execution',{})),copy.deepcopy(binding))

    def to_dict(self,audience='shareable',disclosure=None):
        if audience=='local':return self.to_private_dict()
        if audience!='shareable':raise EvaluationError('Unknown investigation audience.')
        from .investigation_disclosure import project
        return project(self,disclosure)

    def resolve_evidence(self,reference,*,allowed_roots,reveal_values=False,max_characters=240):
        if not allowed_roots:raise EvaluationError('Current authorized roots required.','roots_required')
        if not isinstance(reveal_values,bool) or not isinstance(max_characters,int) or not 1<=max_characters<=240:raise EvaluationError('Invalid bounded evidence resolution.')
        self.from_dict(self.to_private_dict(),private=self.private)
        locator=self.private.get('locators',{}).get(reference)
        if locator is None:raise EvaluationError('Unknown retained evidence reference.','unknown_reference')
        from . import compat
        if locator.get('kind')=='historical_fact':
            from .history_storage import Catalog,file_lock
            from pathlib import Path
            root=getattr(self,'_workspace_location',self.private['workspace_path'])
            from .history_storage import authority_file
            with compat.secure_open(authority_file(root),allowed_roots):pass
            catalog=Catalog(root)
            with file_lock(catalog.objects_lock,False):
                matches=list(catalog.iter_facts(fact_digests=[locator['fact_digest']],max_records=1))
            if not matches:raise EvaluationError('Historical evidence is unavailable.','historical_evidence_unavailable')
            payload=matches[0]['payload']
        else:
            from .sources import records
            from .contracts import SourceSpec,EvaluationConfig
            source=SourceSpec.from_dict(locator['source']);info=self.private['files'][source.id]
            compat.capture(source.path,allowed_roots,expected=info);payload=None
            for coordinate,row in records(source.path,source,EvaluationConfig.from_dict(self.private['config'])):
                if row is not None and coordinate['ordinal']==locator['ordinal']:payload=row;break
            if payload is None or digest({c:payload.get(c) for c in locator['columns']})!=locator['projection_digest']:raise EvaluationError('Exact source evidence differs.','evidence_changed')
            compat.capture(source.path,allowed_roots,expected=info)
            payload={c:payload.get(c) for c in locator['columns']}
        out={'reference':reference,'status':'resolved','values_disclosed':reveal_values}
        if reveal_values:
            raw=json.dumps(payload,ensure_ascii=True,default=str);out.update(excerpt=raw[:max_characters],excerpt_truncated=len(raw)>max_characters)
        return out


ConfirmationAssessment=InvestigationResult
