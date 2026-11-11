"""Frozen CG5 replay on isolated, complete scenario worlds."""
from dataclasses import replace
from types import SimpleNamespace
import copy

from ..contracts import EvaluationError
from ..policy_contracts import PolicyApplicationSpec
from ..policy_store import PolicyStore
from ..policy_runtime import Interpreter
from ..policies import _application_study
from ..policy_optimization import all_metrics
from ..policy_metrics import metric_result,public_stat,constraint_state


def run_policy_stress(prepared,result,spec):
    application=PolicyApplicationSpec.from_dict(spec.application)
    if not application.policy.input_identity:raise EvaluationError('Policy stress requires an already bound frozen policy.','policy_frozen_required')
    if application.input.history:raise EvaluationError('Materialize the authorized historical selection before scenario execution.','policy_stress_history')
    store=prepared.store
    saved={key:copy.copy(getattr(store,key)) for key in ('spec','run_tables','run_facts','tables','counts','sources','representations','input_facts')}
    worlds=[];original_actions={}
    try:
        for scope in sorted({v['scope'] for v in prepared.views},key=lambda v:(v!='original',v)):
            bindings=[]
            for r in application.input.evaluation.runs:
                matches=[v for v in prepared.views if v['scope']==scope and v['predictor'].id==r.id]
                if len(matches)!=1:raise EvaluationError('Frozen policy input run is absent from this scenario.','policy_run_binding')
                v=matches[0];bindings.append((r,v))
            store.run_tables={};store.run_facts={};store.representations={};store.input_facts={}
            declarations=[]
            for target,v in bindings:
                actual=v['run'];declarations.append(replace(actual,id=target.id,source=target.source))
                store.run_tables[target.id]=saved['run_tables'][actual.id];store.run_facts[target.id]=saved['run_facts'][actual.id]
                store.tables[target.source]=v['table'];store.counts[target.source]=v['rows'];store.sources[target.source]=saved['sources'][actual.source]
                if actual.id in saved['representations']:store.representations[target.id]=replace(saved['representations'][actual.id],run=target.id)
                if actual.id in saved['input_facts']:store.input_facts[target.id]=saved['input_facts'][actual.id]
            if application.input.fitted_methods:
                from ..methods import _run_objects
                from ..method_contracts import ReliabilitySpec
                extension=ReliabilitySpec(evaluation=application.input.evaluation,roles=application.input.roles,representations=application.input.representations,fitted_methods=application.input.fitted_methods)
                derived_runs=_run_objects(extension,{m['id']:m for m in application.input.fitted_methods})[len(application.input.evaluation.runs):]
                store.policy_uncertainties={}
                for run in derived_runs:
                    matches=[v for v in prepared.views if v['scope']==scope and v['predictor'].id==run.id]
                    if len(matches)!=1:raise EvaluationError('Frozen uncertainty method was not applied to this complete scenario world.','policy_method_binding')
                    v=matches[0];declarations.append(run);store.run_tables[run.id]=saved['run_tables'][v['id']];store.run_facts[run.id]=saved['run_facts'][v['id']]
                    root=next(m['definition']['run'] for m in application.input.fitted_methods if m['id']==run.id)
                    if root in store.representations:store.representations[run.id]=replace(store.representations[root],run=run.id)
                    if v['id'] in getattr(prepared,'uncertainties',{}):store.policy_uncertainties[run.id]=prepared.uncertainties[v['id']]
            store.spec=SimpleNamespace(**{**vars(saved['spec']),'runs':tuple(declarations)})
            for i in range(len(application.input.features)):prepared.con.execute(f'DROP TABLE IF EXISTS policy_feature_{i}')
            p=PolicyStore(application.input,prepared.config,application.limits,prepared.work,store,phase='replay')
            policy=p.bind_policy(application.policy)
            p.project((policy,));events,records=p.materialize(policy.run,application.role)
            # The unchanged CG5 interpreter checks full batch count and key digest.
            # A filtered/partial scenario therefore stays capacity-unavailable.
            outputs,trace=Interpreter(policy,p.budget).apply(events,batches=application.input.batches)
            study=_application_study(replace(application,policy=policy))
            values={m.id:public_stat(metric_result(m,events,records,outputs,policy,study,p.budget)) for m in all_metrics(study).values()}
            constraints=[constraint_state(c,values[c.metric.id]) for c in application.constraints]
            changes=0
            for event,out in zip(events,outputs):
                action=(out['state'],out.get('value'),out.get('queue'))
                if scope=='original':original_actions[event['event_key']]=action
                else:changes+=action!=original_actions.get(event['event_key'])
            worlds.append({'scope':scope,'policy_digest':policy.policy_digest,'planned':len(events),'action_changes':changes,
                'metrics':values,'constraints':constraints,'capacity':trace['capacity'],'trace':trace,
                'application_state':'capacity_unavailable' if any(not c['complete'] for c in trace['capacity']) else 'completed'})
        result.data['cg6']['policy_stress']={'policy_digest':application.policy.policy_digest,'worlds':worlds,
            'batch_field':spec.batch_field,
            'interpretation':'Frozen hypothetical policy replay; no causal value or reviewer effectiveness claim.'}
        result.private['policy_stress_spec']=spec.to_dict()
    finally:
        for key,value in saved.items():setattr(store,key,value)
