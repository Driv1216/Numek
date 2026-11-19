"""Sealed CG6 evidence and conservative relational disclosure."""
import copy
import hashlib
from pathlib import Path

from ..contracts import EvaluationError,DisclosureSpec,digest,strict_json
from ..result import EvaluationResult,SharedResult,completed_shape
from .contracts import METHOD,RESULT,bounded

LIMITATIONS=[
    'Experimental behavior concerns only identified scenarios, inputs and execution budgets; bounded search is not a robustness guarantee.',
    'Variants of an original event are dependent observations. Unknown transformed outcomes cannot establish transformed accuracy.',
    'Statistical claims require frozen populations, valid outcome relations, sampling, bounds and independent evidence.',
    'Availability and contract tests do not establish device runtime qualification. NVIDIA qualification may remain pending hardware.',
    'Trusted execution is not a security sandbox. Sampled resource limits can overshoot.',
    'No universal robustness score, causal policy value, certification or production approval is established.',
]


class ExecutionResult(EvaluationResult):
    @classmethod
    def from_dict(cls,value,*,private=None):
        if isinstance(value,str):value=strict_json(value)
        if not isinstance(value,dict) or value.get('schema_version')!=RESULT or value.get('methodology_id')!=METHOD:raise EvaluationError('Unsupported CG6 result.')
        if value.get('audience')=='shareable':
            if private is not None or digest({k:v for k,v in value.items() if k!='projection_digest'})!=value.get('projection_digest'):raise EvaluationError('CG6 projection differs.','execution_changed')
            return ExecutionShared(copy.deepcopy(value))
        completed_shape(value)
        payload={k:v for k,v in value.items() if k!='binding'}
        if not isinstance(private,dict) or private.get('schema')!='confidenceguard.execution_private/1.0' or value.get('binding')!={'analysis_digest':digest(payload),'private_manifest_digest':digest(private)} or private.get('analysis_digest')!=digest(payload) or private.get('analysis_id')!=value.get('analysis_id'):
            raise EvaluationError('Protected CG6 binding differs.','execution_changed')
        from .contracts import ExecutionSpec
        if private.get('execution_spec'):ExecutionSpec.from_dict(private['execution_spec'])
        panel=value.get('cg6')
        if not isinstance(panel,dict) or panel.get('stage') not in {'registration','qualification','execution','auxiliary_fit','auxiliary_application','auxiliary_assessment','robustness','assessment','policy_stress','restatement'}:raise EvaluationError('Invalid CG6 result stage.')
        for artifact in private.get('auxiliary_artifacts',[]):
            from ..auxiliary.contracts import AuxiliaryArtifact
            AuxiliaryArtifact.from_dict(artifact)
        if private.get('frozen_protocol'):
            from ..robustness.contracts import FrozenRobustnessProtocol
            protocol=FrozenRobustnessProtocol.from_dict(private['frozen_protocol'])
            if panel.get('protocol_digest')!=protocol.content_digest:raise EvaluationError('CG6 assessment protocol differs.')
        bounded(panel,max_bytes=256*1024**2)
        return cls({k:copy.deepcopy(v) for k,v in value.items() if k not in {'binding','execution'}},copy.deepcopy(private),copy.deepcopy(value['execution']),copy.deepcopy(value['binding']))

    @property
    def source_paths(self):
        return tuple(v['path'] for v in self.private.get('files',{}).values() if isinstance(v,dict) and v.get('path'))

    def to_dict(self,audience='shareable',disclosure=None):
        if audience=='local':return self.to_private_dict()
        if audience!='shareable':raise EvaluationError('Unsupported CG6 audience.')
        d=disclosure or self.private['config']['disclosure']
        if isinstance(d,dict):d=DisclosureSpec.from_dict(d)
        raw=self.to_private_dict();aliases={r['id']:'predictor_'+str(i+1) for i,r in enumerate(raw['runs'])}
        counts=[m['denominator'] for m in raw['measurements']]
        counts.extend(x for m in raw['measurements'] for x in m.get('sensitive_counts',[]))
        counts.extend(s.get(k) for s in raw['cg6'].get('scenarios',[]) for k in ('planned','applicable','attack_eligible','attack_successes') if s.get(k) is not None)
        withheld=d.policy=='conservative_aggregates_v1' and any(0<float(n)<max(d.minimum_component,d.minimum_denominator) for n in counts if n is not None)
        panel=raw['cg6'];public={'schema_version':RESULT,'methodology_id':METHOD,'analysis_id':raw['analysis_id'],'generated_at':raw['generated_at'],
            'name':'ConfidenceGuard execution and robustness','audience':'shareable','task':{'kind':raw['task']['kind']},
            'runs':[{'id':aliases[r['id']],'display_name':'Predictor '+str(i+1)} for i,r in enumerate(raw['runs'])],
            'outcomes':{'scope':raw['outcomes'].get('scope','observed_labels')},'comparison':None,'measurements':[],'checks':[],
            'findings':[],'coverage':{'limitations':LIMITATIONS,'joint_withholding':withheld,'populations':[]},
            'cg6':{'stage':panel['stage'],'evidence_level':'verified_experimental_behavior','joint_withholding':withheld,
                   'qualification':copy.deepcopy(panel.get('qualification',{}))},
            'execution':{'status':raw['execution'].get('status'),'duration_seconds':raw['execution'].get('duration_seconds')},
            'disclosure':d.to_dict(),'origin_binding':copy.deepcopy(self.binding)}
        if raw['task']['kind']=='regression':public['task']['units']=d.display_labels.get('units','declared outcome units') if raw['task'].get('units') else None
        if not withheld:
            scope_alias={s:'scenario_'+str(i+1) for i,s in enumerate(sorted({m['scope'] for m in raw['measurements'] if m['scope']!='overall'}))}
            for m in raw['measurements']:
                # Scenario names, units, output targets, cutoffs, vectors and
                # learned definitions are private; only interpretable overall scalars.
                if m['family'] not in {'performance','proper_scores','robustness_operational','robustness'} or m.get('data',{}).get('target'):continue
                if m['family']!='robustness' and m['scope']!='overall':continue
                if m['run'] not in aliases:continue
                safe={k:copy.deepcopy(m.get(k)) for k in ('id','metric','family','value','value_state','denominator','denominator_kind','basis','interpretation','reason')}
                safe.update(run=aliases[m['run']],scope='overall' if m['scope']=='overall' else scope_alias[m['scope']],population_id=m['population_id'],data={'sampling_unit':'original_event','replicates_averaged_within_root':True} if m['family']=='robustness' else {})
                public['measurements'].append(safe)
            public['cg6']['scenarios']=[{'id':scope_alias.get(s['id'],'scenario'),'replicate':s['replicate'],'planned':s['planned'],'applicable':s['applicable'],'outcome_relation':s.get('outcome_relation','unknown')} for s in panel.get('scenarios',[])]
            public['cg6']['claims']=[{'id':'claim_'+str(i+1),'state':'withheld','allocated_alpha':c.get('allocated_alpha')} for i,c in enumerate(panel.get('claims',[]))]
        public['projection_digest']=digest(public);return public

    def resolve_evidence(self,reference,*,allowed_roots,reveal_values=False):
        if reference not in self.private.get('locators',{}):raise EvaluationError('Unknown CG6 evidence reference.')
        from .. import compat
        locator=self.private['locators'][reference];info=copy.deepcopy(self.private.get('output_artifact'))
        if not info:raise EvaluationError('Exact output artifact was not retained.','evidence_unavailable')
        info['path']=self.retained_path(info['path'])
        from .artifact_bytes import verify_artifact
        verify_artifact(info,allowed_roots)
        with compat.secure_open(info['path'],allowed_roots) as (stream,_):
            for line in stream:
                row=strict_json(line)
                if digest([row['predictor'],row['scenario'],row['event_key']])==locator['key']:
                    return {'reference':reference,'verified':True,'values':self.resolve_retained_assets(row) if reveal_values else None,'values_withheld':not reveal_values}
        raise EvaluationError('Retained witness is absent.','evidence_changed')

    def resolve_retained_assets(self,row):
        row=copy.deepcopy(row)
        mapping=self.private.get('variant_assets',{})
        for record in (row.get('input_record',{}),row.get('variant',{}).get('input_record',{})):
            for k,v in record.items():
                if isinstance(v,str) and v in mapping:record[k]=self.retained_path(mapping[v]['path'])
        return row

    def retained_path(self,path):
        oid=self.private.get('retained_binary_paths',{}).get(path)
        location=getattr(self,'_workspace_location',None)
        if oid and location:
            from ..platform_catalog import platform_bound
            if platform_bound(location):
                from ..history_storage import Catalog
                return str(Catalog(location).blob_path(oid))   # verified materialization at the v2 path
            return str(Path(location)/'objects'/(oid+'.cgblob'))
        return path


class ExecutionShared(SharedResult):
    def to_dict(self,audience='shareable',**kwargs):
        if audience!='shareable':raise EvaluationError('Shareable CG6 evidence cannot become protected evidence.')
        return copy.deepcopy(self.data)
