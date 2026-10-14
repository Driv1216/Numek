"""Independent, exact-result-bound review snapshots, never analytical mutations."""
from dataclasses import dataclass, field
from datetime import datetime, timezone
import copy
import json
from datatrust.cross_private_base import digest
from datatrust.text_normalization import strict_json


def data(result): return result.to_dict() if hasattr(result,'to_dict') else result


@dataclass
class ReviewDispositionSet:
    audit_id: str
    result_sha256: str
    private_manifest_sha256: str
    targets: dict
    reviewer: str | None = None
    entries: dict = field(default_factory=dict)

    @classmethod
    def for_result(cls,result,*,reviewer=None):
        r=data(result)
        if r.get('schema_version')!='1.7': raise ValueError('Reviews require an M9 result.')
        if reviewer is not None and (not isinstance(reviewer,str) or len(reviewer)>200): raise ValueError('Invalid reviewer label.')
        return cls(r['profile']['audit_id'],digest(r),r['profile']['private_manifest_sha256'],copy.deepcopy(r['profile']['review_targets']),reviewer)

    def set(self,target,disposition,note=''):
        if target not in self.targets: raise ValueError('Unknown review target.')
        if disposition not in {'confirm','dismiss','unresolved'}: raise ValueError('Invalid disposition.')
        if not isinstance(note,str) or len(note)>2000 or any(0xd800<=ord(c)<=0xdfff for c in note): raise ValueError('Notes are limited to 2000 characters.')
        self.entries[target]={'target_id':target,'target_sha256':digest(self.targets[target]),'evidence_refs':list(self.targets[target]['evidence_refs']),'disposition':disposition,'note':note,'updated_at':datetime.now(timezone.utc).isoformat()}

    def to_dict(self):
        return {'schema':'m9_review_v1','audit_id':self.audit_id,'result_sha256':self.result_sha256,'private_manifest_sha256':self.private_manifest_sha256,'reviewer':self.reviewer,'reviewer_authenticated':False,'entries':copy.deepcopy(list(self.entries.values()))}

    def json_text(self): return json.dumps(self.to_dict(),ensure_ascii=False,indent=2,allow_nan=False)

    def export(self,path,*,result):
        r=data(result)
        self.from_dict(self.to_dict(),result=r)
        from datatrust.renderer import publish_bytes,protect_source
        if hasattr(result,'source_paths'): protect_source(result.source_paths,[path])
        return publish_bytes(path,self.json_text().encode())

    @classmethod
    def from_dict(cls,value,*,result):
        if isinstance(value,str): value=strict_json(value)
        keys={'schema','audit_id','result_sha256','private_manifest_sha256','reviewer','reviewer_authenticated','entries'}
        if not isinstance(value,dict) or set(value)!=keys or value['schema']!='m9_review_v1' or value['reviewer_authenticated'] is not False: raise ValueError('Invalid review snapshot.')
        review=cls.for_result(result,reviewer=value['reviewer'])
        for key in ('audit_id','result_sha256','private_manifest_sha256'):
            if getattr(review,key)!=value[key]: raise ValueError('Review is bound to another original result.')
        if not isinstance(value['entries'],list) or len(value['entries'])>len(review.targets): raise ValueError('Invalid review entries.')
        for entry in value['entries']:
            if not isinstance(entry,dict) or set(entry)!={'target_id','target_sha256','evidence_refs','disposition','note','updated_at'}: raise ValueError('Invalid disposition entry.')
            target=entry['target_id']
            if target in review.entries or target not in review.targets or entry['target_sha256']!=digest(review.targets[target]) or entry['evidence_refs']!=review.targets[target]['evidence_refs']: raise ValueError('Review target binding differs.')
            review.set(target,entry['disposition'],entry['note'])
            stamp=datetime.fromisoformat(entry['updated_at'])
            if stamp.tzinfo is None: raise ValueError('Review timestamps need an offset.')
            review.entries[target]['updated_at']=entry['updated_at']
        return review
