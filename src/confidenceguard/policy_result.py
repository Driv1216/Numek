"""Immutable CG5 evidence, conservative projections and protected reopening."""
import copy

from .contracts import EvaluationError,DisclosureSpec,TaskDefinition,digest,strict_json
from .result import EvaluationResult,SharedResult,completed_shape
from .policy_contracts import RESULT,METHOD,PolicySpec,PolicyMetricSpec,PolicyStudySpec,FrozenPolicyFamily
from .policy_metrics import claim_parameters

LIMITATIONS=[
    'Policy decisions are hypothetical offline replay; no deployment approval or causal business-value guarantee.',
    'Observed-outcome, model-implied, operational and missing-label bounds are different estimands.',
    'Conditional selective risk, full-opportunity behavior and deferral workload have different denominators.',
    'Independent support conditions on frozen policies and declared sampling, observation, bounds and exposure assumptions.',
    'Historical stability does not establish future effectiveness. Conformal marginal coverage is not conditional policy coverage.',
    'Sampled resource controls can overshoot; admission defaults are not capacity guarantees.',
]


def public_claim_parameters(definition,task,disclosure):
    """Share controlled semantics, or withhold the claim when units are private.

    Arbitrary native unit strings are protected text. A caller can explicitly
    approve a public label through display_labels['units:'+original_unit].
    """
    metric=PolicyMetricSpec.from_dict(definition); task=TaskDefinition.from_dict(task)
    parameters=claim_parameters(metric,task)
    safe_units={'fraction','count','items','squared_items','dimensionless',
                'native_loss_units','native_squared_units'}
    def unit(value):
        if not isinstance(value,str): return None
        return disclosure.display_labels.get('units:'+value,value if value in safe_units else None)
    parameters['units']=unit(parameters['units'])
    if parameters['units'] is None: return None
    needs_outcome_units=task.kind=='regression' and metric.metric in {
        'mae','mse','rmse','bias','absolute_bias','pinball','selective_risk',
        'material_error_rate','median_absolute_error','p90_absolute_error','p95_absolute_error'}
    if needs_outcome_units:
        parameters['outcome_units']=unit(task.units)
        if parameters['outcome_units'] is None: return None
    else: parameters.pop('outcome_units',None)
    if 'material_error' in parameters and parameters['material_error'] is None: return None
    return parameters


class PolicyResult(EvaluationResult):
    @classmethod
    def from_dict(cls,value,*,private=None):
        if isinstance(value,str): value=strict_json(value)
        if not isinstance(value,dict) or value.get('schema_version')!=RESULT or value.get('methodology_id')!=METHOD:
            raise EvaluationError('Unsupported policy result.','policy_result')
        if value.get('audience')=='shareable':
            if private is not None or digest({k:v for k,v in value.items() if k!='projection_digest'})!=value.get('projection_digest'):
                raise EvaluationError('Policy projection binding differs.','policy_changed')
            return PolicyShared(copy.deepcopy(value))
        completed_shape(value)
        payload={k:v for k,v in value.items() if k!='binding'}; binding=value.get('binding',{})
        if not isinstance(private,dict) or private.get('schema')!='confidenceguard.policy_private/1.0' or binding!={'analysis_digest':digest(payload),'private_manifest_digest':digest(private)} or private.get('analysis_digest')!=digest(payload) or private.get('analysis_id')!=value.get('analysis_id'):
            raise EvaluationError('Protected policy evidence binding differs.','policy_changed')
        PolicyStudySpec.from_dict(private['study'])
        policies={k:PolicySpec.from_dict(v) for k,v in private['policies'].items()}
        if any(p.policy_digest!=key for key,p in policies.items()): raise EvaluationError('Policy definition differs.','policy_changed')
        panel=value.get('policy')
        if not isinstance(panel,dict) or panel.get('stage') not in {'selection','replay','assessment','historical','preview'}:
            raise EvaluationError('Invalid policy result stage.')
        if panel.get('stage')=='assessment':
            frozen=FrozenPolicyFamily.from_dict(private['frozen_family'])
            if frozen.family_digest!=panel.get('assessment_family_digest'): raise EvaluationError('Assessment family differs.','policy_changed')
        return cls({k:copy.deepcopy(v) for k,v in value.items() if k not in {'binding','execution'}},
                   copy.deepcopy(private),copy.deepcopy(value.get('execution',{})),copy.deepcopy(binding))

    @property
    def source_paths(self):
        paths=[v['path'] for v in self.private.get('files',{}).values() if v.get('path')]
        root=getattr(self,'_workspace_location',self.private.get('workspace_path'))
        if root: paths.append(root)
        return tuple(paths)

    def to_dict(self,audience='shareable',disclosure=None):
        if audience=='local': return self.to_private_dict()
        if audience!='shareable': raise EvaluationError('Unsupported policy audience.')
        policy=disclosure or self.private['config']['disclosure']
        if isinstance(policy,dict): policy=DisclosureSpec.from_dict(policy)
        raw=self.to_private_dict(); panel=raw['policy']; conservative=policy.policy=='conservative_aggregates_v1'
        counts=[]
        for row in panel.get('candidates',[]):
            for m in row.get('metrics',{}).values(): counts.extend(m.get('sensitive_counts',[]))
        for m in raw['measurements']: counts.extend(m.get('sensitive_counts',[])); counts.append(m['denominator'])
        for claim in panel.get('assessments',[]): counts.extend(claim.get('support_counts',[]))
        private_economics=bool(self.private['study'].get('evaluation_costs') or self.private['study'].get('charges') or any(p.get('decision_costs') for p in self.private['policies'].values()))
        withheld=conservative and (private_economics or any(v is not None and 0<float(v)<max(policy.minimum_component,policy.minimum_denominator) for v in counts))
        aliases={r['id']:'policy_'+str(i+1) for i,r in enumerate(raw['runs'])}
        public={'schema_version':RESULT,'methodology_id':METHOD,'analysis_id':raw['analysis_id'],
                'generated_at':raw['generated_at'],'name':'ConfidenceGuard decision policies','audience':'shareable',
                'task':{'kind':raw['task']['kind']},'runs':[{'id':aliases[r['id']],'display_name':'Policy '+str(i+1),'role':'hypothetical'} for i,r in enumerate(raw['runs'])],
                'outcomes':{'scope':raw['outcomes'].get('scope','observed_labels'),'interpretation':'Supplied authoritative outcomes; observation and causal limitations apply.'},
                'comparison':None,'measurements':[],'checks':[],'findings':[],
                'coverage':{'populations':[],'analytical_scope':'Frozen admitted policy populations; exact definitions and lineage retained locally.',
                            'limitations':LIMITATIONS,'joint_policy_withholding':withheld,'not_anonymity_guarantee':True},
                'policy':{'stage':panel['stage'],'interpretation':'Offline policy evidence; no deployment recommendation.',
                          'executable_definitions_exported':False,'joint_withholding':withheld},
                'disclosure':{**policy.to_dict(),'display_labels':{}},'origin_binding':raw['binding'],
                'execution':{'status':self.execution.get('status','completed'),'backend':'duckdb_local'}}
        if not withheld:
            for i,m in enumerate(raw['measurements']):
                if m['run'] not in aliases: continue
                # Free text, units, targets, names, formulas and exact predicates
                # are not portable metadata merely because the scalar is safe.
                visible={k:copy.deepcopy(m[k]) for k in ('value','value_state','denominator','denominator_kind','basis','interpretation','applicability','execution') if k in m}
                visible['evidence_basis']=m.get('evidence_basis','native_supplied_prediction_diagnostic')
                visible.update(id='measurement_'+str(i+1),run=aliases[m['run']],scope='scope_'+str(i+1),family='policy',metric=m['metric'],population_id=m['population_id'],data={})
                if m.get('uncertainty'): visible['uncertainty']={k:v for k,v in m['uncertainty'].items() if k in {'lower','upper','level','method','strength','family_size','adjustment'}}
                public['measurements'].append(visible)
                public['coverage']['populations'].append({'id':m['population_id'],'run':visible['run'],'scope':visible['scope'],'denominator':m['denominator'],'denominator_kind':m['denominator_kind']})
            claims=[]; omitted=0
            definitions={c['id']:c['metric'] for c in (self.private.get('frozen_family') or {}).get('protocol',{}).get('claims',[])}
            classes={value:'class_'+str(i+1) for i,value in enumerate(raw['task'].get('classes',[]))}
            class_metrics={'precision','opportunity_recall','issued_recall','specificity','false_positive_rate','false_negative_rate','f1','issued_f1','opportunity_f1'}
            for i,c in enumerate(panel.get('assessments',[])):
                definition=c.get('metric_definition') or definitions.get(c['id'],{})
                # An opaque scope label does not identify a protected cohort's
                # estimand. Withhold its conclusion and interval together.
                if c.get('scope')!='overall' or not definition or definition.get('cost') or definition.get('interval') or definition.get('target') is not None and definition.get('metric') not in class_metrics:
                    omitted+=1; continue
                parameters=public_claim_parameters(definition,raw['task'],policy)
                if parameters is None:
                    omitted+=1; continue
                shown={k:c[k] for k in ('metric','operator','bound','basis','scope','direction','estimate','estimate_state','support','comparator_support','minimum_support','state','method','strength','lower','upper','reason','family_size','allocated_alpha','required') if k in c}
                shown.update(parameters)
                shown.update(id='claim_'+str(i+1),policy_digest=aliases.get('policy_'+c['policy_digest'][:16]),
                             comparator=aliases.get('policy_'+c['comparator'][:16]) if c.get('comparator') else None)
                target=definition.get('target') or (raw['task'].get('positive_class') if definition.get('metric') in class_metrics else None)
                if target is not None: shown['target']=classes.get(target,'protected_class')
                claims.append(shown)
            public['policy'].update(assessments=claims,withheld_assessments=omitted,
                assessment_disclosure='Only identified overall claims are shown; protected scopes, economics and uninterpretable unit definitions are withheld with their intervals.')
            public['policy']['searches']=[{k:s[k] for k in ('backend','search_coverage','solution_standing','termination') if k in s} for s in panel.get('searches',[])]
        public['findings']=[{'code':'joint_policy_withholding' if withheld else 'policy_qualification','priority':'Information',
                             'message':'Related policy evidence and nomination are withheld jointly.' if withheld else 'Policy conclusions retain the displayed evidence and population qualifications.'}]
        public['projection_digest']=digest(public)
        return public

    def resolve_evidence(self,reference,*,allowed_roots,reveal_values=False,max_characters=240):
        if reference not in self.private.get('locators',{}): raise EvaluationError('Unknown policy evidence reference.','unknown_reference')
        if self.private['locators'][reference].get('kind')=='historical_fact':
            PolicyResult.from_dict(self.to_private_dict(),private=self.private)
            from types import SimpleNamespace
            from .history_result import LongitudinalResult
            proxy=SimpleNamespace(data={'history':{'catalog_sequence':self.private['history_binding']['catalog_sequence']}},
                private={'locators':self.private['locators'],'workspace_root':getattr(self,'_workspace_location',self.private['workspace_path'])})
            return LongitudinalResult.resolve_evidence(proxy,reference,allowed_roots=allowed_roots,reveal_values=reveal_values,max_characters=max_characters)
        from .private import resolve_evidence
        return resolve_evidence(self,reference,allowed_roots=allowed_roots,reveal_values=reveal_values,max_characters=max_characters)


class PolicyShared(SharedResult):
    def to_dict(self,audience='shareable',**kwargs):
        if audience!='shareable': raise EvaluationError('Portable policy evidence cannot recover private definitions.')
        return copy.deepcopy(self.data)
