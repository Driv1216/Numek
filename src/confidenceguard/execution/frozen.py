"""Apply imported CG2 artifacts to CG6 views without fitting or label access."""
from dataclasses import replace
import copy
import json

from ..contracts import EvaluationSpec,DecisionSpec
from ..method_contracts import ReliabilitySpec,RoleSpec,CALIBRATORS
from ..methods import _fit_all
from ..membership import inspect_imports
from ..sources import rows
from .contracts import OutputBinding


def apply_frozen(prepared,view):
    artifacts=tuple(m for m in prepared.spec.fitted_methods if m['definition']['run']==view['predictor'].id)
    if not artifacts:return
    store=prepared.store
    names=('spec','extension','run_tables','run_facts','representations','input_facts')
    saved={k:getattr(store,k) for k in names};root=view['predictor'].id
    declaration=replace(view['run'],id=root)
    evaluation=replace(saved['spec'],runs=(declaration,),comparison=None) if isinstance(saved['spec'],EvaluationSpec) else None
    if evaluation is None:
        from dataclasses import fields
        original={f.name:getattr(saved['spec'],f.name) for f in fields(EvaluationSpec)}
        evaluation=EvaluationSpec(**{**original,'runs':(declaration,),'comparison':None})
    reps=(replace(saved['representations'][view['id']],run=root),) if view['id'] in saved['representations'] else ()
    extension=ReliabilitySpec(evaluation=evaluation,roles=prepared.spec.roles or RoleSpec(namespace=prepared.spec.namespace,proportions={'E':1}),representations=reps,
        fitted_methods=artifacts,membership_sidecars=tuple(v for v in prepared.spec.membership_sidecars if set(v['method_digests'])&{m['artifact_digest'] for m in artifacts}))
    try:
        store.spec=evaluation;store.extension=extension
        store.run_tables={root:saved['run_tables'][view['id']]};store.run_facts={root:saved['run_facts'][view['id']]}
        store.representations={root:r for r in reps};store.input_facts={root:saved['input_facts'].get(view['id'],{})}
        fitted,_,_,uncertainties=_fit_all(store,extension,[],[])
        checked=inspect_imports(store,fitted)
        applications={m['id']:{'artifact':m,'table':store.run_tables[m['id']],'uncertainty':uncertainties.get(m['id'])} for m in artifacts}
        if not hasattr(prepared,'method_membership'):prepared.method_membership={}
        if view['scope']=='original':prepared.method_membership.update(checked)
    finally:
        for key,value in saved.items():setattr(store,key,value)
    for mid,application in applications.items():
        artifact=application['artifact'];definition=artifact['definition'];base=view['predictor']
        outputs=tuple(b for b in base.outputs if b.channel!='prediction')
        if prepared.spec.task.kind!='regression':outputs+=(OutputBinding('prediction'),)
        if definition['kind'] in CALIBRATORS and not any(b.channel=='probabilities' for b in outputs):outputs+=(OutputBinding('probabilities',classes=prepared.spec.task.classes),)
        virtual=replace(base,id=mid,outputs=outputs,decision=DecisionSpec(rule='none'),execution_view_only=True,provenance={**base.provenance,'frozen_method':artifact['artifact_digest']})
        derived=prepared.start_view(virtual,view['scope']);table=application['table'];pending=[];values=[]
        query=f'SELECT o.payload,r.probs,r.decision,r.cg_failure FROM {table} r JOIN cg6_outputs o ON o.view=? AND o.event_key=r.event_key ORDER BY r.event_key'
        for payload,probabilities,decision,failure in rows(prepared.con,query,[view['id']],batch=512):
            parent=json.loads(payload);out={k:copy.deepcopy(parent[k]) for k in ('channels','channel_failures','execution')}
            out['issuance']=parent.get('issuance')
            if definition['kind'] in CALIBRATORS:
                out['channels'].pop('probabilities',None)
                if probabilities is not None:out['channels']['probabilities']=probabilities
            if prepared.spec.task.kind!='regression':out['channels']['prediction']=decision
            if failure:out['channel_failures']['frozen_method']=failure
            event={'event_key':parent['event_key'],'entity_key':parent['entity_key'],'role':parent['role'],'truth':parent['truth'],'record':parent['input_record'],'unavailable_fields':parent.get('unavailable_fields',[])}
            if parent.get('variant'):event['variant']=parent['variant']
            if application['uncertainty']:
                out['uncertainty']=[{'coverage':coverage,'output':json.loads(value)} for coverage,value in prepared.con.execute(f"SELECT coverage,output FROM {application['uncertainty']} WHERE event_key=? ORDER BY coverage",[parent['event_key']]).fetchall()]
            pending.append(event);values.append(out)
            if len(pending)>=512:prepared.append(derived,pending,values);pending=[];values=[]
        if pending:prepared.append(derived,pending,values)
        prepared.finish_view(derived)
        native=store.run_tables[derived['id']]
        prepared.con.execute(f'UPDATE {native} d SET cg_input_valid=s.cg_input_valid,cg_failure=s.cg_failure,cg_log_probs=s.cg_log_probs,rank_score=s.rank_score FROM {table} s WHERE d.event_key=s.event_key')
        store.refresh_losses(native)
        if application['uncertainty']:
            destination='cg6_uncertainty_'+str(derived['index']);prepared.con.execute(f"ALTER TABLE {application['uncertainty']} RENAME TO {destination}")
            if not hasattr(prepared,'uncertainties'):prepared.uncertainties={}
            prepared.uncertainties[derived['id']]=destination
        prepared.con.execute(f'DROP TABLE {table}')
