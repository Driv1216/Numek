"""CG2 application services over CG1 ingestion, supervision and evidence reducers."""
import copy
from dataclasses import fields, replace
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import time
from types import SimpleNamespace
import uuid
import numpy as np

from .contracts import (EvaluationConfig, EvaluationError, ProbabilitySpec, SamplingSpec,
                        ComparisonSpec, digest, exact)
from .method_contracts import (ReliabilitySpec, MethodSpec, CALIBRATORS, CONFORMAL,
                               CG2_RESULT, CG2_METHOD, parse_spec)
from .calibration import fit_calibrator, transform, MethodUnavailable
from .conformal import thresholds, score, construct, value_state, validate_output
from .fitted import FittedMethod, make_method, compatible, assessment
from .engine import open_store, _arguments
from .sources import rows
from .analytics import Evidence, evaluate_scope, distributions, policies, compare, literal
from .result import EvaluationResult, Inspection
from . import compat


def _view(spec,**changes):
    return SimpleNamespace(**{**{f.name:getattr(spec,f.name) for f in fields(spec)},**changes})


def _arguments2(spec,config,allowed_roots):
    spec=parse_spec(spec)
    if not isinstance(spec,ReliabilitySpec):raise EvaluationError('CG2 needs a versioned reliability/study specification.')
    config=EvaluationConfig.from_dict(config) if isinstance(config,dict) else config or EvaluationConfig()
    base,config,roots=_arguments(spec.evaluation,config,allowed_roots)
    spec=replace(spec,evaluation=base)
    if spec.inference.mode=='independent_rows':config=replace(config,sampling=SamplingSpec('independent_rows'))
    elif spec.inference.mode=='independent_clusters':config=replace(config,sampling=SamplingSpec('descriptive'))
    for raw in spec.fitted_methods:FittedMethod.from_dict(raw,limits=spec.limits)
    _validate_methods(spec)
    effective,_=_effective_methods(spec)
    known={r.id for r in base.runs}|{m.id for m in effective}|{m['id'] for m in spec.fitted_methods}
    if any(edge.left not in known or edge.right not in known for edge in spec.comparisons):raise EvaluationError('Comparison refers to an undeclared run or variant.')
    if len(base.policies)+len(spec.variant_policies)>config.max_policies or any(len(p.thresholds)>config.max_thresholds for p in spec.variant_policies):raise EvaluationError('Combined fixed-policy admission exceeded.','policy_limit')
    return spec,config,roots


def _validate_methods(spec):
    task=spec.evaluation.task;reps={r.run:r for r in spec.representations};runs={r.id:r for r in spec.evaluation.runs}
    methods=[*spec.methods,*[MethodSpec.from_dict(v['definition']) for v in spec.fitted_methods]]
    if len(methods)>spec.limits.variants:raise EvaluationError('Derived variant admission exceeded.','variant_limit')
    ids={m.id for m in methods}
    if ids & set(runs):raise EvaluationError('Method IDs must be distinct from base run IDs.')
    for m in methods:
        if m.run not in runs:raise EvaluationError('Method binding needs the same declared logical base run.','incompatible_method')
        rep=reps.get(m.run);run=runs[m.run]
        if m.kind in {'platt','isotonic','beta'} and task.kind!='binary_classification':raise EvaluationError('This calibration family requires binary outcomes.')
        if m.kind=='dirichlet' and task.kind!='multiclass_classification':raise EvaluationError('Dirichlet requires a multiclass task.')
        if m.kind in {'lac','aps','raps'} and task.kind=='regression' or m.kind in {'split','normalized','cqr'} and task.kind!='regression':raise EvaluationError('Conformal method/task mismatch.')
        if m.kind in {'identity','beta','dirichlet','lac','aps','raps'} and m.input!='probabilities':raise EvaluationError('This method requires an explicit probability input.')
        if m.kind in {'platt','isotonic'} and m.input not in {'probabilities','probability_logit','score'}:raise EvaluationError('Invalid scalar calibration input.')
        if m.kind=='temperature' and m.input not in {'probabilities','logits'}:raise EvaluationError('Temperature needs declared logits or probability-power input.')
        if m.kind in CALIBRATORS and m.parent:raise EvaluationError('CG2 calibration maps bind original inputs; only conformal construction chains from a calibrator.')
        if m.kind=='split' and m.input!='point' or m.kind=='normalized' and m.input!='normalized' or m.kind=='cqr' and m.input!='quantiles':raise EvaluationError('Declare the regression method input explicitly.')
        if m.input in {'probabilities','probability_logit'} and not run.probabilities and not m.parent:raise EvaluationError('Probability input is absent.')
        if m.input=='score' and (not run.score or not run.score.column):raise EvaluationError('Native scalar score input is absent.')
        if m.input=='logits' and (not rep or not (rep.logits or rep.binary_logit)):raise EvaluationError('Explicit logits are absent.')
        if m.kind=='normalized' and (not rep or not rep.scale):raise EvaluationError('A positive-scale binding is required.')
        if m.kind=='cqr' and (not rep or {m.lower_quantile,m.upper_quantile}-{q.level for q in rep.quantiles}):raise EvaluationError('CQR quantile bindings are absent.')
        if m.kind=='raps' and m.k_reg>len(task.classes):raise EvaluationError('RAPS cutoff exceeds the class universe.')
        if m.kind=='raps' and not math.isfinite(m.penalty*max(0,len(task.classes)-m.k_reg)):raise EvaluationError('RAPS penalty/rank arithmetic exceeds the supported numeric range.')
        if m.kind=='dirichlet' and len(task.classes)**2+len(task.classes)>spec.limits.parameter_elements:raise EvaluationError('Dirichlet parameter admission exceeded.','parameter_limit')
    by_id={m.id:m for m in methods}
    for m in methods:
        if m.parent and not m.parent.startswith('selected:'):
            p=by_id.get(m.parent)
            if p is None or p.kind not in CALIBRATORS or p.run!=m.run or m.kind not in {'lac','aps','raps'}:raise EvaluationError('Conformal parents must be compatible probability calibrators.')


def _effective_methods(spec):
    methods=list(spec.methods);families=[]
    for family in spec.selections:
        members=[m for m in methods if m.id in family.candidates]
        ids=list(family.candidates)
        # Identity competes on the same population when original probabilities exist.
        if family.objective!='efficiency' and next(r for r in spec.evaluation.runs if r.id==members[0].run).probabilities and not any(m.kind=='identity' for m in members):
            identity=MethodSpec('identity:'+family.id,'identity',members[0].run)
            if any(m.id==identity.id for m in methods):raise EvaluationError('Reserved identity candidate ID collision.')
            methods.append(identity);ids.append(identity.id)
        families.append(replace(family,candidates=tuple(ids)))
    if len(methods)>spec.limits.candidates or len(methods)+len(spec.fitted_methods)>spec.limits.variants:raise EvaluationError('Effective candidate/variant admission exceeded, including identity.','candidate_limit')
    ids=[m.id for m in methods]+[m['id'] for m in spec.fitted_methods]
    if len(ids)!=len(set(ids)):raise EvaluationError('Effective method/identity IDs collide with imported methods.')
    return methods,families


def _comparison_edges(spec,methods):
    return list(spec.comparisons) or ([spec.evaluation.comparison] if spec.evaluation.comparison else [])+[ComparisonSpec(m.run,m.id) for m in methods]+[ComparisonSpec(v['definition']['run'],v['id']) for v in spec.fitted_methods]


def _pool(store,method,members,role,*,fraction=None,pilot=None):
    base=store.run_tables[method.run]
    predicates=[store.input_expression(m)[1] for m in members]
    where=f'cg_role={literal(role)} AND outcome_valid AND input_identity_valid AND '+ ' AND '.join('('+p+')' for p in predicates)
    if fraction is not None:
        # Pilot splitting is label-independent and follows the declared independent unit.
        unit='entity_key' if store.extension.roles.unit=='entity' else 'event_key'
        cutoff=int(fraction*1000000)
        token=f"CAST('0x'||substr(sha256(to_json(list_value({unit},{literal(store.extension.roles.namespace)},{literal(str(store.extension.roles.seed))}))),1,13) AS UBIGINT)"
        where+=f' AND {token}%1000000'+('<' if pilot=='calibration' else '>=')+str(cutoff)
    table='cg_pool_'+uuid.uuid4().hex
    store.con.execute(f'CREATE TABLE {table} AS SELECT * FROM {base} WHERE {where}')
    count=store.con.execute(f'SELECT count(*) FROM {table}').fetchone()[0]
    native={m.id:store.con.execute(f'SELECT count(*) FROM {base} WHERE cg_role=? AND outcome_valid AND input_identity_valid AND ({store.input_expression(m)[1]})',[role]).fetchone()[0] for m in members}
    total=store.con.execute(f'SELECT count(*) FROM {base} WHERE cg_role=?',[role]).fetchone()[0]
    h=hashlib.sha256()
    for row in rows(store.con,f'SELECT event_key,y,y_num,probs,rank_score,logits,point,scale,quantiles FROM {table} ORDER BY event_key',batch=512):h.update(json.dumps(row,separators=(',',':'),allow_nan=False).encode())
    lineage={'role':role,'namespace':store.extension.roles.namespace,'members':sorted(m.id for m in members),
             'input_requirements':[m.to_dict() for m in members],'role_membership_digest':store.membership_digests[(method.run,role)],
             'task_digest':digest(store.spec.task.to_dict()),'normalization_version':'cg1_extended_v1','probability_tolerance':store.config.probability_tolerance,
             'eligible_content_digest':h.hexdigest(),'denominator_kind':'eligible_records'}
    population={'id':'fitpop_'+digest(lineage)[:32],'run':method.run,'scope':'role/'+role,'definition':where,'denominator_kind':'eligible_records','lineage':lineage,'denominator':count,'role_records':total,
                  'candidate_native_input_support':native,'excluded_from_role':total-count,
                  'frozen_before_fitting':True,'failures_do_not_renegotiate_membership':True}
    store.method_populations[population['id']]=population
    return table,population


def _clone(store,method,parent=None):
    source=store.run_tables[parent] if parent else store.run_tables[method.run]
    table='cg_variant_'+str(len(store.run_tables))
    store.con.execute(f'CREATE TABLE {table} AS SELECT * FROM {source}')
    store.run_tables[method.id]=table
    store.run_facts[method.id]=copy.deepcopy(store.run_facts[method.run])
    store.run_facts[method.id].update(derived=True,method=method.id)
    return table


def _apply_calibrator(store,method,fitted):
    table=_clone(store,method); original=store.run_tables[method.run]
    expression=store.input_expression(method)[1]
    store.con.execute(f'UPDATE {table} SET cg_input_valid=input_identity_valid AND ({expression}),prob_valid=false,probs=NULL,cg_log_probs=NULL,top_label=NULL,confidence=NULL,ptrue=NULL,brier=NULL,log_loss=NULL,log_infinite=false,rank_score=NULL,cg_failure=\'unavailable_input\'')
    store.con.execute('CREATE TEMP TABLE probability_updates(ordinal BIGINT,probs DOUBLE[],logs DOUBLE[],top_label VARCHAR,confidence DOUBLE,ranking DOUBLE,failure VARCHAR)')
    task=store.spec.task;pos=task.classes.index(task.positive_class) if task.positive_class else None
    source_column='rank_score' if method.input=='score' else 'logits' if method.input=='logits' else 'probs'
    query=f'SELECT ordinal,{source_column},decision FROM {original} WHERE input_identity_valid AND ({expression}) ORDER BY event_key'
    pending=[]
    for ordinal,value,decision in rows(store.con,query,batch=512):
        if method.input=='score':
            run=next(r for r in store.spec.runs if r.id==method.run);value=[value*(-1 if run.score.direction=='lower' else 1)]
        try:
            p,lp=transform(method,fitted['parameters'],np.asarray([value]),task.classes,task.positive_class);p=p[0];lp=lp[0]
            if not np.all(np.isfinite(p)) or np.any(p<0) or abs(float(p.sum())-1)>store.config.probability_tolerance:raise MethodUnavailable('Invalid normalized probability output.','numerical_transformation')
            top=float(p.max()); winners=np.flatnonzero(p==top)
            base_run=next(r for r in store.spec.runs if r.id==method.run)
            label=task.classes[int(winners[0])] if len(winners)==1 or base_run.decision.tie_policy=='class_order' else None
            confidence=float(p[task.classes.index(decision)]) if decision in task.classes else None
            pending.append((ordinal,p.tolist(),lp.tolist(),label,confidence,float(lp[pos]-lp[1-pos]) if pos is not None else None,None))
        except MethodUnavailable as exc:pending.append((ordinal,None,None,None,None,None,exc.code))
        if len(pending)>=512:
            store.con.executemany('INSERT INTO probability_updates VALUES (?,?,?,?,?,?,?)',pending);pending=[];store.work.check('fitted probability application')
    if pending:store.con.executemany('INSERT INTO probability_updates VALUES (?,?,?,?,?,?,?)',pending)
    store.con.execute(f'UPDATE {table} r SET probs=u.probs,cg_log_probs=u.logs,prob_valid=u.failure IS NULL,top_label=u.top_label,confidence=u.confidence,rank_score=u.ranking,cg_failure=u.failure FROM probability_updates u WHERE r.ordinal=u.ordinal')
    store.con.execute('DROP TABLE probability_updates');store.refresh_losses(table)
    store.run_facts[method.id]['ranking_representation']='log_odds_preserving_underflow_order' if pos is not None else 'not_applicable'
    return table


def _conformal_data(store,method,row):
    p,y,yn,point,scale,quantiles=row
    if method.kind in {'lac','aps','raps'}:return {'p':np.asarray([p]),'y':np.asarray([store.spec.task.classes.index(y)])}
    result={'y':np.asarray([yn]),'point':np.asarray([point]),'scale':np.asarray([scale])}
    if method.kind=='cqr':
        levels=[q.level for q in store.representations[method.run].quantiles]
        result.update(lower=np.asarray([quantiles[levels.index(method.lower_quantile)]]),upper=np.asarray([quantiles[levels.index(method.upper_quantile)]]))
    return result


def _fit_conformal(store,method,pool,parent=None):
    table=store.run_tables[parent] if parent else store.run_tables[method.run]
    dest='scores_'+uuid.uuid4().hex;store.con.execute(f'CREATE TABLE {dest}(score DOUBLE)')
    query=f'SELECT r.probs,p.y,p.y_num,r.point,r.scale,r.quantiles,r.prob_valid,r.cg_failure FROM {pool} p JOIN {table} r USING(ordinal,event_key)'
    pending=[]
    for *values,prob_valid,failure in rows(store.con,query,batch=512):
        if method.kind in {'lac','aps','raps'} and (not prob_valid or failure):raise MethodUnavailable('A parent failed on planned calibration inputs.','parent_failure_on_common_population')
        v=float(score(method,**_conformal_data(store,method,values))[0]);pending.append((v,))
        if len(pending)>=512:
            store.con.executemany(f'INSERT INTO {dest} VALUES (?)',pending);pending=[];store.work.check('conformal score contributions')
    if pending:store.con.executemany(f'INSERT INTO {dest} VALUES (?)',pending)
    result={'thresholds':thresholds(store.con,dest,method.levels,store.work.check)}
    store.con.execute(f'DROP TABLE {dest}');return result


def _apply_conformal(store,method,fitted,parent=None):
    table=_clone(store,method,parent);raw=store.run_tables[method.run]
    expression=store.input_expression(method)[1]
    if parent:
        store.con.execute(f'UPDATE {table} SET cg_input_valid=cg_input_valid AND input_identity_valid')
    else:store.con.execute(f'UPDATE {table} SET cg_input_valid=input_identity_valid AND ({expression})')
    output='uncertainty_'+str(len(store.run_tables));store.con.execute(f'CREATE TABLE {output}(ordinal BIGINT,event_key VARCHAR,coverage VARCHAR,output VARCHAR)')
    pending=[];failed=[]
    query=f'SELECT ordinal,event_key,probs,point,scale,quantiles,cg_input_valid,prob_valid,cg_failure FROM {table} ORDER BY event_key'
    for ordinal,event,p,point,scale,quantiles,eligible,prob_valid,parent_failure in rows(store.con,query,batch=512):
        for threshold in fitted['parameters']['thresholds']:
            if not eligible or parent_failure or method.kind in {'lac','aps','raps'} and not prob_valid:
                result={'state':'unavailable','members':None,'width':None,'reason':parent_failure or 'unavailable_input'}
            else:
                args={'p':p,'point':point,'scale':scale}
                if method.kind=='cqr':
                    levels=[q.level for q in store.representations[method.run].quantiles]
                    args.update(lower=quantiles[levels.index(method.lower_quantile)],upper=quantiles[levels.index(method.upper_quantile)])
                try:result=construct(method,threshold,**args)
                except MethodUnavailable as exc:
                    result={'state':'unavailable','members':None,'width':None,'reason':exc.code};failed.append((exc.code,ordinal))
            validate_output(result,len(store.spec.task.classes) if store.spec.task.classes else None)
            pending.append((ordinal,event,threshold['coverage'],json.dumps(result,allow_nan=False)))
        if len(pending)>=512:
            store.con.executemany(f'INSERT INTO {output} VALUES (?,?,?,?)',pending);pending=[];store.work.check('conformal application')
            if failed:store.con.executemany(f'UPDATE {table} SET cg_failure=? WHERE ordinal=?',failed);failed=[]
    if pending:store.con.executemany(f'INSERT INTO {output} VALUES (?,?,?,?)',pending)
    if failed:store.con.executemany(f'UPDATE {table} SET cg_failure=? WHERE ordinal=?',failed)
    return table,output


def _objective(store,method,table,pool,objective):
    n=store.con.execute(f'SELECT count(*) FROM {pool}').fetchone()[0]
    count,invalid,infinite,loss=store.con.execute(f'SELECT count(*),count(*) FILTER(WHERE NOT r.prob_valid OR r.cg_failure IS NOT NULL),count(*) FILTER(WHERE r.log_infinite),avg(r.brier)' .replace('avg(r.brier)','avg(r.brier)' if objective=='brier' else 'avg(r.log_loss)')+f' FROM {pool} p JOIN {table} r USING(ordinal,event_key)').fetchone()
    if not n:return {'status':'unavailable','reason':'empty_common_selection_population','denominator':n}
    if invalid or count!=n:return {'status':'disqualified','reason':'candidate_failure_on_common_selection_population','denominator':n,'failed_records':invalid}
    value=math.inf if objective=='log_loss' and infinite else loss
    if value is None or math.isnan(value):return {'status':'unavailable','reason':'undefined_selection_objective','denominator':n}
    return {'status':'eligible','denominator':n,**value_state(value)}


def _choose(records,members):
    candidates=[m for m in members if records.get(m.id,{}).get('status')=='eligible' and records[m.id].get('value_state')=='finite']
    if not candidates:return None
    best=min(records[m.id]['value'] for m in candidates)
    tied=[m for m in candidates if math.isclose(records[m.id]['value'],best,rel_tol=1e-8,abs_tol=1e-10)]
    complexity={'identity':0,'temperature':1,'platt':2,'beta':3,'isotonic':4,'dirichlet':5,'lac':0,'aps':0,'raps':0,'split':0,'normalized':0,'cqr':0}
    return min(tied,key=lambda m:(records[m.id].get('free_parameters',complexity[m.kind]),members.index(m))).id


def _dependency_exclusions(methods):
    import importlib.util
    available=importlib.util.find_spec('scipy') is not None
    return {m.id:'statistics_unavailable' for m in methods if m.kind in {'platt','beta','temperature','dirichlet'} and not available}


def _reproducibility(store):
    import importlib.metadata
    import platform
    packages={}
    for package in ('numpy','duckdb','scipy'):
        try:packages[package]=importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:packages[package]=None
    return {'python':platform.python_version(),'packages':packages,'numeric_type':'IEEE754_float64','threads':store.config.threads,
            'role_assignment':'sha256_namespace_seed_unit_v1','role_seed':store.extension.roles.seed,'namespace':store.extension.roles.namespace,
            'role_unit':store.extension.roles.unit,'ordering':'canonical_event_key',
            'implementation_sha256':{name:hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest() for name in ('calibration.py','conformal.py','method_sources.py','method_contracts.py')},
            'promise':'Documented numerical reproducibility; no universal cross-platform bitwise identity.'}


def _imported_methods(store,spec):
    roots={r.id:r for r in spec.evaluation.runs};fitted={}
    for raw in spec.fitted_methods:
        artifact=FittedMethod(raw,limits=spec.limits).to_dict();definition=MethodSpec.from_dict(artifact['definition'])
        parent_digest=next((v['artifact_digest'] for v in spec.fitted_methods if v['id']==definition.parent),None)
        compatible(artifact,spec.evaluation.task,roots[definition.run].model,store.signature(definition),parent_digest)
        fitted[definition.id]=artifact
    return fitted


def _fit_all(store,spec,methods,families):
    task=spec.evaluation.task;roots={r.id:r for r in spec.evaluation.runs}
    fitted=_imported_methods(store,spec);status={};pools={};selections=[];uncertainties={};selected={}
    excluded=_dependency_exclusions(methods)
    status.update({mid:{'status':'unavailable','reason':reason,'admission':'dependency_excluded_before_population_freeze'} for mid,reason in excluded.items()})
    # Calibrators first, preserving declaration order and frozen family membership.
    family_for={mid:f for f in families for mid in f.candidates}
    for family in families:
        members=[m for m in methods if m.id in family.candidates and m.id not in excluded]
        if family.objective=='efficiency':continue
        if not members:continue
        for role in ('F','S'):pools[(family.id,role)]=_pool(store,members[0],members,role)
    for method in methods:
        if method.kind not in CALIBRATORS:continue
        if method.id in excluded:continue
        family=family_for.get(method.id)
        pool,pop=pools[(family.id,'F')] if family else _pool(store,method,[method],'F')
        try:
            if method.kind=='identity':params,metadata={}, {'fit_records':pop['denominator'],'algorithm_version':'identity_v1','converged':True}
            else:
                params,metadata=fit_calibrator(method,task,lambda:store.batches(method,pool,'true'),directory=store.work.root,check=store.work.check,connection=store.con,parameter_elements=spec.limits.parameter_elements)
            provenance={**metadata,'fit_population':pop,'separation':spec.separation.to_dict(),'reproducibility':_reproducibility(store),'source_role_digests':{'F':store.membership_digests[(method.run,'F')]}}
            artifact=make_method(method,task,roots[method.run].model,params,provenance,store.signature(method),limits=spec.limits).to_dict()
            fitted[method.id]=FittedMethod(artifact,limits=spec.limits).to_dict();status[method.id]={'status':'fitted','fit_population':pop}
        except MethodUnavailable as exc:status[method.id]={'status':'unavailable','reason':exc.code,'fit_population':pop}
    for key,artifact in list(fitted.items()):
        method=MethodSpec.from_dict(artifact['definition'])
        if method.kind in CALIBRATORS:_apply_calibrator(store,method,artifact)
    for family in families:
        if family.objective=='efficiency':continue
        members=[m for m in methods if m.id in family.candidates]
        if (family.id,'S') not in pools:
            selections.append({'id':family.id,'objective':family.objective,'common_population':None,'candidates':{m.id:{'status':'disqualified','reason':status[m.id]['reason']} for m in members},'selected':None,'reason':'no_admitted_candidates'});continue
        pool,pop=pools[(family.id,'S')]
        records={m.id:_objective(store,m,store.run_tables[m.id],pool,family.objective) if m.id in fitted else {'status':'disqualified','reason':status[m.id]['reason']} for m in members}
        for m in members:
            if m.id in fitted:
                p=fitted[m.id]['parameters']
                records[m.id]['free_parameters']=len(set(p['values'])) if m.kind=='isotonic' else len(task.classes)**2-1 if m.kind=='dirichlet' else {'identity':0,'platt':2,'beta':3,'temperature':1}[m.kind]
        winner=_choose(records,members);selected[family.id]=winner
        selections.append({'id':family.id,'objective':family.objective,'common_population':pop,'candidates':records,'selected':winner,
                           'tie_rule':'rtol=1e-8,atol=1e-10; fewer parameters; declared order','refitted_on_selection':False})
        for member in members:
            if member.id not in fitted:continue
            artifact=fitted[member.id]
            artifact['provenance']['selection_history']=[copy.deepcopy(selections[-1])]
            artifact['provenance']['source_role_digests']['S']=store.membership_digests[(member.run,'S')]
            artifact['artifact_digest']=digest({k:v for k,v in artifact.items() if k!='artifact_digest'})
            fitted[member.id]=FittedMethod(artifact,limits=spec.limits).to_dict()
    # Resolve conformal parents only after calibration selection is immutable.
    conformal=[]
    for method in methods:
        if method.kind not in CONFORMAL:continue
        if method.parent and method.parent.startswith('selected:'):
            parent=selected.get(method.parent.split(':',1)[1])
            if not parent:status[method.id]={'status':'unavailable','reason':'upstream_selection_unavailable'};continue
            method=replace(method,parent=parent)
        if method.parent and method.parent not in fitted:status[method.id]={'status':'unavailable','reason':'upstream_fit_unavailable'};continue
        conformal.append(method)
    # Pilot conformal selection never touches C; common pilot inputs remain fixed.
    conformal_selected=set();candidate_membership={mid for f in families if f.objective=='efficiency' for mid in f.candidates}
    for family in families:
        if family.objective!='efficiency':continue
        members=[m for m in conformal if m.id in family.candidates]
        declared=[m for m in methods if m.id in family.candidates]
        # Parent probability maps may have been fitted from native scores. Planned
        # inputs then follow the upstream map, not absent original probabilities.
        planning=[_planning_method(next((v for v in members if v.id==m.id),m),methods,fitted) for m in declared]
        pool,pop=_pool(store,planning[0],planning,'S',fraction=family.pilot_fraction,pilot='calibration')
        val,vpop=_pool(store,planning[0],planning,'S',fraction=family.pilot_fraction,pilot='evaluation')
        records={}
        for m in members:
            try:
                params=_fit_conformal(store,m,pool,m.parent)
                rec=_pilot_efficiency(store,m,params,val,m.parent)
                if family.coverage_tolerance is None:rec.update(status='unavailable',reason='coverage_tolerance_required_for_selection')
                elif any(v['coverage']<float(level)-family.coverage_tolerance for level,v in rec.get('levels',{}).items()):rec.update(status='disqualified',reason='pilot_coverage_constraint')
                records[m.id]=rec
            except MethodUnavailable as exc:records[m.id]={'status':'disqualified','reason':exc.code}
        for m in declared:
            if m.id not in records:records[m.id]={'status':'disqualified','reason':status.get(m.id,{}).get('reason','upstream_unavailable')}
        winner=_choose(records,members);selected[family.id]=winner
        if winner:conformal_selected.add(winner)
        selections.append({'id':family.id,'objective':'efficiency','pilot_calibration':pop,'common_population':vpop,'candidates':records,'selected':winner,'pilot_thresholds_discarded':True})
    for method in conformal:
        if method.id in candidate_membership and method.id not in conformal_selected:
            status[method.id]={'status':'not_selected','reason':'pilot_selection'};continue
        planning=_planning_method(method,methods,fitted);pool,pop=_pool(store,planning,[planning],'C')
        try:
            params=_fit_conformal(store,method,pool,method.parent)
            parent_digest=fitted[method.parent]['artifact_digest'] if method.parent else None
            provenance={'calibration_population':pop,'separation':spec.separation.to_dict(),'score_version':'1','reproducibility':_reproducibility(store),'source_role_digests':{'C':store.membership_digests[(method.run,'C')]}}
            selection=next((s for s in selections if s['objective']=='efficiency' and method.id in s['candidates']),None)
            if selection:provenance['selection_history']=[copy.deepcopy(selection)];provenance['source_role_digests']['S']=store.membership_digests[(method.run,'S')]
            artifact=make_method(method,task,roots[method.run].model,params,provenance,store.signature(method),parent_digest,limits=spec.limits).to_dict()
            fitted[method.id]=FittedMethod(artifact,limits=spec.limits).to_dict();status[method.id]={'status':'fitted','calibration_population':pop}
        except MethodUnavailable as exc:status[method.id]={'status':'unavailable','reason':exc.code,'calibration_population':pop}
    for key,artifact in fitted.items():
        method=MethodSpec.from_dict(artifact['definition'])
        if method.kind in CONFORMAL:
            _,output=_apply_conformal(store,method,artifact,method.parent);uncertainties[key]=output
    return fitted,status,selections,uncertainties


def _planning_method(method,methods,fitted):
    if method.parent:
        parent=next((m for m in methods if m.id==method.parent),None)
        if parent is None and method.parent in fitted:parent=MethodSpec.from_dict(fitted[method.parent]['definition'])
        if parent is not None:return replace(parent,id=method.id)
    return method


def _pilot_efficiency(store,method,params,pool,parent):
    table=store.run_tables[parent] if parent else store.run_tables[method.run]
    n=0;total=0.;covered=0;by_level={t['coverage']:{'records':0,'covered':0,'efficiency':0.} for t in params['thresholds']}
    for p,y,yn,point,scale,quantiles,prob_valid,failure in rows(store.con,f'SELECT r.probs,p.y,p.y_num,r.point,r.scale,r.quantiles,r.prob_valid,r.cg_failure FROM {pool} p JOIN {table} r USING(ordinal,event_key)',batch=512):
        if failure or method.kind in {'lac','aps','raps'} and not prob_valid:raise MethodUnavailable('Pilot parent output failed.','candidate_failure_on_common_selection_population')
        for threshold in params['thresholds']:
            args={'p':p,'point':point,'scale':scale}
            if method.kind=='cqr':
                levels=[q.level for q in store.representations[method.run].quantiles];args.update(lower=quantiles[levels.index(method.lower_quantile)],upper=quantiles[levels.index(method.upper_quantile)])
            output=construct(method,threshold,**args);n+=1
            item=by_level[threshold['coverage']];item['records']+=1
            if store.spec.task.classes:
                total+=output['size'];covered+=int(store.spec.task.classes.index(y) in output['members'])
                item['efficiency']+=output['size'];item['covered']+=int(store.spec.task.classes.index(y) in output['members'])
            else:
                from .conformal import read_value
                total+=read_value(output['width']);covered+=int(output['state']=='unbounded' or output['state']=='finite' and read_value(output['lower'])<=yn<=read_value(output['upper']))
                item['efficiency']+=read_value(output['width']);item['covered']+=int(output['state']=='unbounded' or output['state']=='finite' and read_value(output['lower'])<=yn<=read_value(output['upper']))
        store.work.check('common pilot evaluation')
    if not n:return {'status':'unavailable','reason':'empty_common_selection_population'}
    for item in by_level.values():
        item['coverage']=item['covered']/item['records'];item['efficiency']=value_state(item['efficiency']/item['records'])
    return {'status':'eligible','denominator':n//len(params['thresholds']),'levels':by_level,'objective_aggregation':'mean efficiency over the identical declared levels',**value_state(total/n)}


def _calibration_edges(store,spec):
    if spec.calibration_strategy=='fixed':return list(spec.calibration_edges or [i/store.config.calibration_bins for i in range(store.config.calibration_bins+1)])
    tables=[store.run_tables[r.id] for r in spec.evaluation.runs if r.probabilities]
    if not tables:raise EvaluationError('Fit-derived calibration bins require probabilities.')
    union=' UNION ALL '.join(f'SELECT unnest(probs) value FROM {t} WHERE cg_role=\'F\' AND prob_valid AND input_identity_valid' for t in tables)
    count=store.con.execute(f'SELECT count(*) FROM ({union}) q').fetchone()[0]
    if not count:raise EvaluationError('Fit-derived calibration bins need an eligible F population.','empty_fit_bins')
    values=store.con.execute(f'SELECT quantile_disc(value,?) FROM ({union}) q',[[i/store.config.calibration_bins for i in range(1,store.config.calibration_bins)]]).fetchone()[0]
    return sorted({0.,1.,*values})


def _run_objects(spec,fitted):
    result=list(spec.evaluation.runs); roots={r.id:r for r in result}
    for key,artifact in fitted.items():
        definition=MethodSpec.from_dict(artifact['definition']);base=roots[definition.run]
        probability=definition.kind in CALIBRATORS or definition.parent is not None
        result.append(replace(base,id=key,probabilities=base.probabilities or ProbabilitySpec(columns={c:'derived_'+str(i) for i,c in enumerate(spec.evaluation.task.classes)}) if probability else base.probabilities,
                              score=None if probability else base.score,role='evaluation'))
    return result


def _evaluation_relations(store,runs):
    full=dict(store.run_tables)
    for i,run in enumerate(runs):
        table=f'cg_eval_{i}'
        store.con.execute(f'CREATE TABLE {table} AS SELECT * FROM {full[run.id]} WHERE cg_role=\'E\'')
        store.run_tables[run.id]=table
        store.run_facts[run.id]['repeated_entities']=store.con.execute(f'SELECT coalesce(sum(n),0) FROM (SELECT count(*) n FROM {table} WHERE entity_key IS NOT NULL GROUP BY entity_key HAVING count(*)>1)').fetchone()[0]
    return full


def _comparison_plans(store,runs,edges):
    by_id={r.id:r for r in runs};nodes=sorted({v for edge in edges for v in (edge.left,edge.right)})
    for node in nodes:
        if node not in by_id:raise EvaluationError('Unknown comparison variant.')
    result={}
    for kind in ('decision','probability','ranking','point'):
        predicates=[];outputs=[];eligible=[]
        for node in nodes:
            run=by_id[node]
            supported=(kind=='probability' and run.probabilities or kind=='ranking' and store.spec.task.kind=='binary_classification' and (run.probabilities or run.score) or kind=='point' and store.spec.task.kind=='regression' or kind=='decision' and store.spec.task.kind!='regression')
            if not supported:continue
            table=store.run_tables[node]
            if node in {r.id for r in store.extension.evaluation.runs}:
                pred={'probability':'prob_valid','ranking':'rank_score IS NOT NULL','point':"point IS NOT NULL AND state IN ('issued','hypothetical')",'decision':"decision IS NOT NULL AND state IN ('issued','hypothetical')"}[kind]
            else:
                pred='cg_input_valid'
                if kind=='point':pred+=" AND point IS NOT NULL AND state IN ('issued','hypothetical')"
                if kind=='decision':pred+=" AND decision IS NOT NULL AND state IN ('issued','hypothetical')"
            predicates.append(f'SELECT event_key FROM {table} WHERE input_identity_valid AND outcome_valid AND ({pred})');eligible.append(node)
            output_pred={'probability':'prob_valid','ranking':'rank_score IS NOT NULL','point':"point IS NOT NULL AND state IN ('issued','hypothetical')",'decision':"decision IS NOT NULL AND state IN ('issued','hypothetical')"}[kind]
            outputs.append(f'SELECT event_key FROM {table} WHERE input_identity_valid AND outcome_valid AND ({pred}) AND ({output_pred}) AND cg_failure IS NULL')
        if len(predicates)<2:continue
        table='cg_common_'+kind;store.con.execute(f'CREATE TABLE {table} AS '+' INTERSECT '.join(predicates))
        actual=table+'_outputs';store.con.execute(f'CREATE TABLE {actual} AS '+' INTERSECT '.join(outputs))
        h=hashlib.sha256()
        for event, in rows(store.con,f'SELECT event_key FROM {table} ORDER BY event_key',batch=512):h.update(event.encode());h.update(b'\n')
        result[kind]={'table':table,'actual_table':actual,'nodes':eligible,'planned_membership_digest':h.hexdigest(),'actual_support':store.con.execute(f'SELECT count(*) FROM {actual}').fetchone()[0],
                      'planned_support':store.con.execute(f'SELECT count(*) FROM {table}').fetchone()[0],
                      'basis':'family_wide_common_inputs','count_checked':True}
    return result


def _core_comparisons(e,store,runs,edges,plans):
    ledgers=[];old=store.spec
    lineage_plans={k:{key:v for key,v in p.items() if key not in {'table','actual_table'}} for k,p in plans.items()}
    for run in runs:
        table=store.run_tables[run.id]
        e.bind_relation(table,{**e.relations[table],'comparison_population_plan':lineage_plans})
    for edge in edges:
        store.spec=_view(store.extension.evaluation,runs=tuple(runs),comparison=edge)
        predicates={k:f'a.event_key IN (SELECT event_key FROM {p["actual_table"]})' for k,p in plans.items()}
        before=len(e.measurements);ledger=compare(e,predicates=predicates)
        if ledger is None:continue
        if not ledger['blocked_reasons']:
            expected={'probability':['brier','log_loss'],'ranking':['roc_auc','average_precision'],'point':['mae','rmse','bias'],'decision':['accuracy']}
            by_id={r.id:r for r in runs}
            for kind,plan in plans.items():
                if plan['actual_support'] or not plan['planned_support'] or edge.left not in plan['nodes'] or edge.right not in plan['nodes']:continue
                joined=f'{store.run_tables[edge.left]} a JOIN {store.run_tables[edge.right]} b USING(event_key)'
                e.bind_relation(joined,{'kind':'unavailable_cg2_paired_base','left':e.relations[store.run_tables[edge.left]],'right':e.relations[store.run_tables[edge.right]],'population_plan':lineage_plans[kind]})
                e.use_relation(joined)
                for metric in expected[kind]:
                    e.add(by_id[edge.right],'paired','comparison',metric+'_right_minus_left',n=0,where='false',reason='no_successful_common_outputs',denominator_kind='paired_base_support',
                          data={'left_run':edge.left,'right_run':edge.right,'metric_population':kind})
        for m in e.measurements[before:]:
            if m['family']!='comparison':continue
            kind=m['data'].get('metric_population')
            if kind not in plans:continue
            plan=plans[kind];failed={};scope_filter='true'
            if m['scope'].startswith('cohort_'):
                head,group,_=m['scope'].split('/',2);scope_filter=f'g{int(head.removeprefix("cohort_"))}={literal(group)}'
            left_table=store.run_tables[edge.left]
            planned_support=store.con.execute(f'SELECT count(*) FROM {left_table} WHERE ({scope_filter}) AND event_key IN (SELECT event_key FROM {plan["table"]})').fetchone()[0]
            actual_support=store.con.execute(f'SELECT count(*) FROM {left_table} WHERE ({scope_filter}) AND event_key IN (SELECT event_key FROM {plan["actual_table"]})').fetchone()[0]
            for node in plan['nodes']:
                table=store.run_tables[node]
                failed[node]=store.con.execute(f'SELECT count(*) FROM {table} WHERE ({scope_filter}) AND cg_input_valid AND cg_failure IS NOT NULL AND event_key IN (SELECT event_key FROM {plan["table"]})').fetchone()[0]
            m['data'].update(planned_common_input_support=planned_support,candidate_failures=failed,
                             population_basis='family_wide_common_inputs_then_paired_outputs',
                             primary_comparison_allowed=not any(failed.values()) and actual_support==planned_support,
                             comparison_qualification='success_conditional_descriptive' if any(failed.values()) else 'common_input_population_only')
        ledger['population_plans']=lineage_plans
        ledgers.append(ledger)
    store.spec=old
    return ledgers


def _extra_comparisons(e,store,runs,edges,extra):
    by_id={r.id:r for r in runs};ledgers=[]
    # A common input population for every participating node supporting a metric.
    all_nodes={node for edge in edges for node in (edge.left,edge.right)}
    all_metrics={metric for node,(table,metadata) in extra.items() if node in all_nodes for metric in metadata}
    common={}
    for metric in all_metrics:
        nodes=[node for node in sorted(all_nodes) if node in extra and metric in extra[node][1]]
        if len(nodes)<2:continue
        if any(extra[node][1][metric].get('histogram') for node in nodes):continue
        statements=[f'SELECT x.event_key FROM {extra[node][0]} x JOIN {store.run_tables[node]} r USING(ordinal,event_key) WHERE x.metric={literal(metric)} AND x.eligible AND r.outcome_valid AND r.input_identity_valid' for node in nodes]
        dest='cg_extra_common_'+str(len(common));store.con.execute(f'CREATE TABLE {dest} AS '+' INTERSECT '.join(statements))
        failures={node:store.con.execute(f'SELECT count(*) FROM {extra[node][0]} WHERE metric=? AND event_key IN (SELECT event_key FROM {dest}) AND NOT defined',[metric]).fetchone()[0] for node in nodes}
        common[metric]=(dest,failures)
    for edge in edges:
        if edge.left not in extra or edge.right not in extra:continue
        lt,lm=extra[edge.left];rt,rm=extra[edge.right]
        for metric in sorted(lm.keys()&rm.keys()):
            if lm[metric].get('nominal')!=rm[metric].get('nominal'):continue
            if metric not in common:continue
            planned,failures=common[metric]
            dest='cg_extra_pair_'+str(len(e.measurements))
            store.con.execute(f'CREATE TABLE {dest} AS SELECT a.*,l.value left_extra,r.value right_extra,l.defined left_defined,r.defined right_defined FROM {store.run_tables[edge.left]} a JOIN {lt} l USING(ordinal,event_key) JOIN {store.run_tables[edge.right]} b USING(event_key) JOIN {rt} r ON b.ordinal=r.ordinal AND b.event_key=r.event_key WHERE l.metric=? AND r.metric=? AND a.event_key IN (SELECT event_key FROM {planned})',[metric,metric])
            e.bind_relation(dest,{'kind':'cg2_extra_paired_base','left':e.relations[store.run_tables[edge.left]],'right':e.relations[store.run_tables[edge.right]],'metric':metric,'common_nodes':sorted(all_nodes)})
            e.use_relation(dest)
            n,bad,left,right=store.con.execute(f'SELECT count(*),count(*) FILTER(WHERE NOT left_defined OR NOT right_defined),avg(left_extra),avg(right_extra) FROM {dest}').fetchone()
            family_bad=any(failures.values())
            delta=right-left if not family_bad and left is not None and right is not None else math.nan
            m=e.add(by_id[edge.right],'paired','comparison',metric+'_right_minus_left',None if math.isnan(delta) else delta,n,
                    data={'left_run':edge.left,'right_run':edge.right,'metric_population':'extra:'+metric,
                          'left':value_state(left),'right':value_state(right),'planned_common_input_support':store.con.execute(f'SELECT count(*) FROM {planned}').fetchone()[0],
                          'candidate_undefined_records':failures,'paired_defined_support':n-bad,
                          'primary_comparison_allowed':bool(n) and not family_bad,'comparison_qualification':'common_input_population_only' if not family_bad else 'undefined_on_family_population'},
                    reason='undefined_on_planned_metric_population' if family_bad or math.isnan(delta) else None,denominator_kind='paired_base_support')
            m['cg2_contribution_table']=dest
            ledgers.append({'metric':metric,'left':edge.left,'right':edge.right,'planned':m['data']['planned_common_input_support'],'actual':n})
    return ledgers


def _contribution_query(store,m):
    data=m['data'];metric=m['metric'].removesuffix('_right_minus_left')
    left,right=data.get('left_run'),data.get('right_run')
    if not left or not right:return None
    if m.get('cg2_contribution_table'):
        table=m['cg2_contribution_table'];return f'SELECT left_extra,1.,right_extra,1.,entity_key FROM {table}',False
    a=store.run_tables[left];b=store.run_tables[right]
    population=next(p for p in store._evidence.populations.values() if p['id']==m['population_id'])
    where=population['definition'];task=store.spec.task
    positive=literal(task.positive_class) if task.positive_class else "''"
    means={'log_loss':"CASE WHEN {s}.log_infinite THEN 'inf'::DOUBLE ELSE {s}.log_loss END",'brier':'{s}.brier',
           'mae':'abs({s}.point-{s}.y_num)','rmse':'pow({s}.point-{s}.y_num,2)','bias':'{s}.point-{s}.y_num',
           'accuracy':'CASE WHEN {s}.decision={s}.y THEN 1. ELSE 0. END'}
    if metric in {'roc_auc','average_precision'}:
        return f'SELECT CASE WHEN a.y={positive} THEN 1. ELSE 0. END,dense_rank() OVER(ORDER BY a.rank_score),dense_rank() OVER(ORDER BY b.rank_score),a.entity_key FROM {a} a JOIN {b} b USING(event_key) WHERE {where}',metric
    if metric in means:
        expression=means[metric];parts=[expression.format(s='a'),'1.',expression.format(s='b'),'1.']
    elif metric in {'precision','recall','specificity'}:
        parts=[]
        for s in ('a','b'):
            if metric=='precision':num=f'{s}.decision={positive} AND {s}.y={positive}';den=f'{s}.decision={positive}'
            elif metric=='recall':num=f'{s}.decision={positive} AND {s}.y={positive}';den=f'{s}.y={positive}'
            else:num=f'{s}.decision<>{positive} AND {s}.y<>{positive}';den=f'{s}.y<>{positive}'
            parts.extend([f'CASE WHEN {num} THEN 1. ELSE 0. END',f'CASE WHEN {den} THEN 1. ELSE 0. END'])
    else:return None
    return 'SELECT '+','.join(parts)+f',a.entity_key FROM {a} a JOIN {b} b USING(event_key) WHERE {where}',False


def _infer(e,store,spec,edges,started):
    from .inference import preflight,smooth_bootstrap,bootstrap
    request=spec.inference
    if request.mode=='descriptive':return {'status':'descriptive','contrasts':[]}
    family_size=len(edges)*len(request.metrics)*len(request.scopes)
    plans=[];matches=set();work_total=0
    for m in e.measurements:
        metric=m['metric'].removesuffix('_right_minus_left')
        if m['family']!='comparison' or metric not in request.metrics or m['scope'] not in request.scopes:continue
        matches.add((m['data'].get('left_run'),m['data'].get('right_run'),metric,m['scope']))
        reason=None;query=None
        if m['value_state']!='finite':reason='nonfinite_comparison'
        elif not m['data'].get('primary_comparison_allowed',True):reason='failure_conditioned_comparison'
        elif not spec.separation.base_predictions_independent or not spec.separation.evaluation_independent:reason='evaluation_independence_unestablished'
        elif any(f['cross_role_entity_overlap'] for f in store.role_facts.values()):reason='cross_role_entity_dependence'
        elif any(v['status']=='contradicted' for v in getattr(store,'prior_membership',{}).values()):reason='prior_membership_overlap'
        elif any(not store.assessment_membership.get(node,True) for node in (m['data']['left_run'],m['data']['right_run'])):reason='prior_membership_unavailable'
        elif request.mode=='independent_rows' and any(store.run_facts[node]['repeated_entities'] for node in (m['data']['left_run'],m['data']['right_run'])):reason='known_repeated_entities'
        else:query=_contribution_query(store,m)
        if query and not query[1]:
            import importlib.util
            if importlib.util.find_spec('scipy') is None:reason='statistics_unavailable'
        if not query and not reason:reason='interval_procedure_not_supported'
        if reason:plans.append((m,None,None,{'status':'not_admitted','reasons':[reason],'execution':'not_run','family_size':family_size}));continue
        sql,ranked=query
        n,units,missing=store.con.execute(f'SELECT count(*),count(DISTINCT entity_key),count(*) FILTER(WHERE entity_key IS NULL) FROM ({sql}) q').fetchone()
        concentration=None
        if request.mode=='independent_clusters':
            if missing:plans.append((m,None,None,{'status':'not_admitted','reasons':['missing_cluster_identity'],'execution':'not_run','family_size':family_size}));continue
            maximum,squared,total=store.con.execute(f'SELECT max(n),sum(n*n),sum(n) FROM (SELECT count(*) n FROM ({sql}) q GROUP BY entity_key) c').fetchone()
            concentration={'largest_cluster_fraction':maximum/total if total else None,'size_concentration_effective_units':total*total/squared if squared else 0,
                           'interpretation':'Size concentration diagnostic; not a replacement for independent-cluster count or proof of asymptotic accuracy.'}
            if not ranked:
                sql='SELECT '+','.join(f'sum(c{i}) c{i}' for i in range(4))+',entity_key FROM ('+sql.replace('SELECT ','SELECT ',1)+') q(c0,c1,c2,c3,entity_key) GROUP BY entity_key ORDER BY entity_key'
        else:units=n
        remaining=store.config.max_seconds-(time.monotonic()-started)
        admission=preflight(request,n if ranked else units,units,family_size,ranked=bool(ranked),available_bytes=min(store.config.memory_bytes,store.config.max_rss_bytes//2),remaining_seconds=remaining)
        admission.update(evaluation_records=n,cluster_preaggregation=request.mode=='independent_clusters' and not ranked)
        if concentration:admission['cluster_concentration']=concentration
        work_total+=admission['estimated_work_units']
        plans.append((m,sql,ranked,admission))
    missing=[{'left':edge.left,'right':edge.right,'metric':metric,'scope':scope,'status':'not_admitted','reasons':['comparison_unavailable'],'family_size':family_size} for edge in edges for metric in request.metrics for scope in request.scopes if (edge.left,edge.right,metric,scope) not in matches]
    exceeded=work_total>request.work_units
    if request.inference_required and (missing or exceeded or any(p[3]['status']!='admitted' for p in plans)):
        raise EvaluationError('Required inference failed statistical/computational admission.','inference_not_admitted')
    records=[]
    for m,sql,ranked,admission in plans:
        if exceeded:admission.update(status='not_admitted',reasons=list(admission.get('reasons',[]))+['job_inference_work_limit'],execution='not_run')
        if admission['status']!='admitted':m['uncertainty_status']=admission;records.append({'measurement':m['id'],**admission});continue
        count=store.con.execute(f'SELECT count(*) FROM ({sql}) q').fetchone()[0]
        columns=3 if ranked else 4
        path=store.work.root/('bootstrap-'+m['id'])
        store.work.check('bootstrap contribution reservation',count*columns*8)
        values=np.memmap(path,mode='w+',dtype='float64',shape=(count,columns));clusters=[]
        for i,row in enumerate(rows(store.con,sql,batch=512)):
            values[i]=row[:columns]
            if ranked and request.mode=='independent_clusters':clusters.append(row[-1])
            if i%512==0:store.work.check('paired inference contributions')
        if ranked:
            result=bootstrap(values,request,family_size=family_size,check=store.work.check,clusters=clusters or None,ranked=ranked,available_bytes=store.config.memory_bytes)
        else:result=smooth_bootstrap(values,request,family_size=family_size,check=store.work.check,root=m['metric']=='rmse_right_minus_left',available_bytes=store.config.memory_bytes)
        del values;path.unlink()
        result.update(evaluation_records=admission['evaluation_records'],sampling_unit='cluster' if request.mode=='independent_clusters' else 'event')
        if 'cluster_concentration' in admission:result['cluster_concentration']=admission['cluster_concentration']
        if request.mode=='independent_clusters':m['sensitive_counts'].append(admission['independent_units'])
        m['uncertainty_status']=result
        if result['status']=='available':
            m['uncertainty']=result;m['interpretation']='inferential'
            margin=request.material_difference or 0.
            m['data']['directional_evidence']='right_lower' if result['upper'] < -margin else 'right_higher' if result['lower']>margin else 'inconclusive'
            m['data']['practical_difference_declared']=request.material_difference is not None
        elif request.inference_required:raise EvaluationError('Required interval failed final statistical checks.','inference_unavailable')
        records.append({'measurement':m['id'],**result})
    return {'status':'completed','family_size':family_size,'estimated_job_work_units':work_total,'work_budget':request.work_units,'contrasts':records+missing,
            'conditioning':'Fixed fitted artifacts; no fitting/selection variability; adjustment family never shrinks after failures.'}


def assessment_basis(data):
    value=copy.deepcopy(data);cg=value.get('cg2',{})
    cg.pop('assessments',None);cg.pop('assessment_basis_digest',None)
    return digest(value)


def _application_record(store,artifact,table,uncertainty_table):
    h=hashlib.sha256();n=0;failures=0
    for ordinal,event,p,logs,point,decision,state,failure in rows(store.con,f'SELECT ordinal,event_key,probs,cg_log_probs,point,decision,state,cg_failure FROM {table} ORDER BY event_key,ordinal',batch=512):
        safe_logs=[value_state(v) for v in logs] if logs is not None else None
        h.update(json.dumps([ordinal,event,p,safe_logs,point,decision,state,failure],allow_nan=False,separators=(',',':')).encode());n+=1;failures+=int(failure is not None)
    if uncertainty_table:
        for ordinal,event,coverage,output in rows(store.con,f'SELECT ordinal,event_key,coverage,output FROM {uncertainty_table} WHERE ordinal IN (SELECT ordinal FROM {table}) ORDER BY event_key,ordinal,coverage',batch=512):h.update(json.dumps([ordinal,event,coverage,output],separators=(',',':')).encode())
    result={'method_digest':artifact['artifact_digest'],'namespace':store.extension.roles.namespace,'prediction_content_digest':h.hexdigest(),'records':n,'unavailable_records':failures,
            'evidence_state':'applied_unvalidated','historical_assessments_do_not_validate_this_application':True,
            'coverage_assumptions':store.extension.separation.to_dict()}
    result['application_digest']=digest(result);return result


def _execute2(spec,config,roots,operation,expected,staging=None,capture=None,*,progress=None):
    started=time.monotonic();work=None
    try:
        work,store,cells=open_store(spec.evaluation,config,roots,progress,extension=spec,capture=capture)
        methods,families=_effective_methods(spec)
        declared_edges=_comparison_edges(spec,methods)
        fingerprint=digest({'sources':{k:{'sha256':v['sha256'],'bytes':v['bytes']} for k,v in store.sources.items()},'spec':spec.to_dict(),'config':config.to_dict(),'methodology':CG2_METHOD,
                            'outcomes':store.outcome_facts.get('snapshot_digest'),'context':store.context_facts['snapshot_digest'],'effective_methods':[m.to_dict() for m in methods]})
        if expected and fingerprint!=expected:raise EvaluationError('Confirmed CG2 input/method/population/inference settings changed.','stale_confirmation')
        if operation=='inspect':
            from .inference import preflight
            from .membership import inspect_imports
            imported=_imported_methods(store,spec)
            prior_membership=inspect_imports(store,imported)
            plans=[]
            dependency_exclusions=_dependency_exclusions(methods)
            for family in families:
                members=[m for m in methods if m.id in family.candidates and m.id not in dependency_exclusions]
                if not members:plans.append({'family':family.id,'status':'unavailable','reason':'no_admitted_candidates'});continue
                for role in ('F','S'):
                    _,pop=_pool(store,members[0],members,role);plans.append({'family':family.id,**pop})
            eval_n=sum(store.role_facts[r.id]['counts'].get('E',0) for r in spec.evaluation.runs)
            edge_count=len(declared_edges)
            family_size=edge_count*len(spec.inference.metrics)*len(spec.inference.scopes)
            inference=preflight(spec.inference,eval_n,eval_n,family_size,available_bytes=min(config.memory_bytes,config.max_rss_bytes//2),remaining_seconds=config.max_seconds-(time.monotonic()-started))
            store.verify()
            return Inspection({'schema_version':'confidenceguard.inspection/1.1','fingerprint':fingerprint,'effective_spec':spec.to_dict(),'effective_config':config.to_dict(),
                               'sources':[{'id':s.id,'columns':store.headers[s.id],'records':store.counts[s.id],'bytes':store.sources[s.id]['bytes']} for s in spec.evaluation.sources],
                               'runs':store.run_facts,'outcomes':store.outcome_facts,'roles':store.role_facts,'selection_populations':plans,
                               'dependency_exclusions':dependency_exclusions,
                               'method_compatibility':[{'id':key,'status':'compatible','artifact_digest':v['artifact_digest']} for key,v in imported.items()],
                               'prior_membership_checks':prior_membership,
                               'inference_admission':inference,'inference_exact_support_rechecked_after_freezing':True,'methodology_id':CG2_METHOD},
                              {'status':'completed','duration_seconds':time.monotonic()-started,'peak_workspace_bytes':work.peak})
        if operation in {'evaluate','apply'} and methods:raise EvaluationError('Fitting declarations require fit/study; evaluation/application consume fitted artifacts.')
        if operation=='apply' and not spec.output_path:raise EvaluationError('Application needs an explicit protected output_path.')
        store.seal_evaluation_labels()
        diagnostic_edges=_calibration_edges(store,spec) if spec.evaluation.task.classes else []
        if progress:progress({'stage':'method_fitting_and_selection' if operation in {'fit','study'} else 'fitted_method_application'})
        fitted,status,selections,uncertainties=_fit_all(store,spec,methods,families)
        from .membership import preserve,inspect_imports,assessment_membership_passed
        prior_membership=inspect_imports(store,fitted)
        store.prior_membership=prior_membership
        imported_ids={v['id'] for v in spec.fitted_methods}
        store.assessment_membership={key:assessment_membership_passed(key,fitted,imported_ids,prior_membership) for key in fitted}
        membership_sidecars=list(spec.membership_sidecars)+preserve(store,fitted)
        roots_by_variant={key:v['definition']['run'] for key,v in fitted.items()}
        runs=_run_objects(spec,fitted)
        if operation in {'study','evaluate'}:store.unseal_evaluation_labels(roots_by_variant)
        if capture is not None:
            store.history_capture.outputs(store,fitted=fitted,uncertainties=uncertainties,runs=runs,membership=membership_sidecars,calibration_edges=diagnostic_edges)
        full_tables=_evaluation_relations(store,runs)
        store.spec=_view(spec.evaluation,runs=tuple(runs),comparison=None,policies=tuple((*spec.evaluation.policies,*spec.variant_policies)))
        e=Evidence(store);store._evidence=e
        for run in runs:
            table=store.run_tables[run.id]
            e.bind_relation(table,{'kind':'cg2_evaluation_projection','normalized':e.relations[table],'role':'E','role_membership_digest':store.membership_digests[(roots_by_variant.get(run.id,run.id),'E')],
                                   'representation':store.representations[roots_by_variant.get(run.id,run.id)].to_dict() if roots_by_variant.get(run.id,run.id) in store.representations else None,
                                   'auxiliary_source_digests':{sid:v['sha256'] for sid,v in store.sources.items()},
                                   'method_digest':fitted[run.id]['artifact_digest'] if run.id in fitted else None})
        extra={}
        from .uncertainty import build_losses,evaluate_losses,deeper_calibration
        present={r.id for r in runs}
        edges=[edge for edge in declared_edges if edge.left in present and edge.right in present]
        if operation in {'study','evaluate'}:
            if progress:progress({'stage':'independent_prediction_evaluation'})
            for run in runs:
                table=store.run_tables[run.id];distributions(e,run,table);evaluate_scope(e,run,table,'true','overall');policies(e,run,table)
                loss_table,metadata=build_losses(store,run,table,root=roots_by_variant.get(run.id,run.id),uncertainty_table=uncertainties.get(run.id));extra[run.id]=(loss_table,metadata)
                evaluate_losses(e,run,table,loss_table,metadata,'true','overall')
                deeper_calibration(e,run,table,'true','overall',diagnostic_edges)
                for i,cohort in enumerate(spec.evaluation.cohorts):
                    if store.run_facts[run.id]['context_conflicts'].get(cohort.column):
                        e.checks.append({'id':f'cohort_{i}:{run.id}','applicability':'blocked','execution':'not_run','reason':'conflicting_canonical_context_assertion'});continue
                    for group, in store.con.execute(f'SELECT DISTINCT g{i} FROM {table} ORDER BY 1').fetchall():
                        if group=='unresolved':continue
                        where=f'g{i}={literal(group)}';scope=f'cohort_{i}/{group}'
                        evaluate_scope(e,run,table,where,scope);evaluate_losses(e,run,table,loss_table,metadata,where,scope)
                        deeper_calibration(e,run,table,where,scope,diagnostic_edges)
            plans=_comparison_plans(store,runs,edges)
            comparisons=_core_comparisons(e,store,runs,edges,plans)
            extra_comparisons=_extra_comparisons(e,store,runs,edges,extra)
            inference=_infer(e,store,spec,declared_edges,started)
        else:comparisons=[];extra_comparisons=[];inference={'status':'not_run','reason':'no_independent_evaluation_requested'}
        for m in e.measurements:m.pop('cg2_contribution_table',None)
        e.validate_populations()
        aid=uuid.uuid4().hex
        applications={key:_application_record(store,v,store.run_tables[key],uncertainties.get(key)) for key,v in fitted.items()}
        qualifies=operation in {'study','evaluate'} and spec.separation.base_predictions_independent and spec.separation.evaluation_independent and not any(f['cross_role_entity_overlap'] for f in store.role_facts.values())
        for key,app in applications.items():
            n=store.con.execute(f'SELECT count(*) FROM {store.run_tables[key]} WHERE outcome_valid AND input_identity_valid AND cg_input_valid AND cg_failure IS NULL').fetchone()[0]
            if qualifies and n and store.assessment_membership[key]:app['assessment_eligible']=True
            else:app['assessment_eligible']=False
            # Application identity never changes when an assessment is attached.
        limitations=['Independent evaluation is evidence presence, not proof of improvement or future coverage.',
                     'Reapplication is applied-but-unvalidated until this application receives a qualifying independent assessment.',
                     'Conformal coverage is marginal under exchangeable scores and independent fixed upstream choices.',
                     'Cluster inference does not establish conformal validity. Selective labels limit population claims.',
                     'Fixed-artifact intervals exclude training, fitting and selection variability.',
                     'Observed separation checks apply only to supplied identities; external provenance remains declared.',
                     'Sampled resource controls can overshoot and are not capacity guarantees.']
        if not all((spec.separation.exchangeable_scores,spec.separation.labels_representative)):limitations.append('Ordinary future-population conformal coverage assumptions are unestablished for this application.')
        run_records=[]
        for i,run in enumerate(runs):
            root=roots_by_variant.get(run.id,run.id)
            run_records.append({'id':run.id,'display_name':run.model.display_name or f'Model {i+1}','version_alias':f'Variant {i+1}','model':run.model.to_dict(),'role':'evaluation' if operation in {'study','evaluate'} else 'calibration',
                                'decision_provenance':{**run.decision.to_dict(),'origin':'supplied' if run.prediction or run.decision.column else 'derived' if run.decision.rule!='none' else 'none'},
                                'representations':{'hard_prediction':bool(run.prediction or run.decision.column),'probabilities':bool(run.probabilities),'scores':bool(run.score),'intervals':len(run.intervals)},
                                'facts':store.run_facts[run.id],'root_run':root,'method_digest':fitted[run.id]['artifact_digest'] if run.id in fitted else None})
        findings=[]
        for run in runs:
            facts=store.run_facts[run.id]
            for field in ('duplicate_keys','missing_keys','invalid_probabilities','inline_conflicts','decision_rule_mismatches','unresolved_issuance'):
                if facts[field]:findings.append({'code':field,'run':run.id,'priority':'Review','message':'Review the declared input interpretation and affected evidence.','count':facts[field]})
        for comparison in comparisons:
            if comparison['blocked_reasons']:findings.append({'code':'paired_comparison_blocked','priority':'Review','message':'Paired performance is unavailable under the current outcome, identity or timing declarations.','reasons':comparison['blocked_reasons']})
        if any(m['metric']=='log_loss' and m['value_state']=='positive_infinity' for m in e.measurements):findings.append({'code':'zero_probability_observed_outcome','priority':'Review','message':'An observed reference outcome received zero supplied probability.'})
        for key,state in status.items():
            if state['status']=='unavailable':findings.append({'code':'method_unavailable','priority':'Review','run':key,'message':'A requested method could not be fitted on its frozen population.','reason':state['reason']})
        if any(app['unavailable_records'] for app in applications.values()):findings.append({'code':'application_unavailable_outputs','priority':'Review','message':'Some planned application inputs did not produce usable transformed outputs; primary improvement claims are limited.'})
        observed_e=any(store.con.execute(f'SELECT count(*) FROM {store.run_tables[r.id]} WHERE outcome_valid AND input_identity_valid').fetchone()[0] for r in runs)
        if not qualifies or not observed_e or applications and not any(app['assessment_eligible'] for app in applications.values()):findings.append({'code':'independent_evaluation_unestablished','priority':'Review','message':'No qualifying independent evaluation is established; fitted/application evidence does not prove improvement.'})
        if any(v['status']!='passed' for v in prior_membership.values()):findings.append({'code':'prior_membership_qualification','priority':'Review','message':'Prior fitting/selection/calibration membership checks are unavailable or contradicted; inspect exact method-specific qualifications.'})
        if not spec.separation.exchangeable_scores or not spec.separation.labels_representative:findings.append({'code':'coverage_assumptions_unestablished','priority':'Review','message':'Ordinary future-population conformal coverage assumptions are not established.'})
        cg={'operation':operation,'methods':{key:{'method':v['definition']['kind'],'artifact_digest':v['artifact_digest'],'evidence_state':'fitted_only','algorithm_version':v['algorithm_version']} for key,v in fitted.items()},
            'fit_status':status,'selections':selections,'applications':applications,'comparisons':comparisons,'extra_comparisons':extra_comparisons,'inference':inference,'assessments':[],
            'roles':store.role_facts,'separation':spec.separation.to_dict(),'prior_membership_checks':prior_membership,'assessments_do_not_change_method_or_application_digests':True}
        cg['comparison_requests']=[{**edge.to_dict(),'execution':'completed' if edge in edges else 'not_run','reason':None if edge in edges else 'variant_unavailable_before_evaluation'} for edge in declared_edges]
        cg['evidence_views']={key:{'id':key,'method_state':'independently_evaluated' if app['assessment_eligible'] else 'fitted_only',
                                  'application_state':'independently_evaluated' if app['assessment_eligible'] else 'applied_unvalidated',
                                  'method_digest':app['method_digest'],'application_digest':app['application_digest'],
                                  'meaning':'Evidence presence for this exact application, not proof of improvement or future coverage.'} for key,app in applications.items()}
        coverage={'population_provenance_version':'1.1','populations':list(e.populations.values())+list(store.method_populations.values()),'sources':store.counts,'outcome_snapshot':store.outcome_facts,'context_snapshot':store.context_facts,
                  'cohort_definitions':[c.to_dict() for c in spec.evaluation.cohorts],
                  'retention_limits':{'witnesses_per_group':config.witnesses,'maximum_investigation_details':config.max_details,'retained_witnesses':len(e.locators),'curve_points':config.curve_points},
                  'analytical_scope':'Frozen role populations; common selection inputs and metric-specific paired evaluation. No silent sampling or population renegotiation.',
                  'sampling':{'requested':spec.inference.mode,'inference_enabled':any(m.get('interpretation')=='inferential' for m in e.measurements)},'limitations':limitations}
        data={'schema_version':CG2_RESULT,'methodology_id':CG2_METHOD,'analysis_id':aid,'generated_at':datetime.now(timezone.utc).isoformat(),'name':spec.evaluation.name,
              'task':spec.evaluation.task.to_dict(),'runs':run_records,'outcomes':store.outcome_facts,'comparison':comparisons[0] if comparisons else None,
              'measurements':e.measurements,'checks':e.checks,'findings':findings,'coverage':coverage,'cg2':cg}
        basis=assessment_basis(data);cg['assessment_basis_digest']=basis
        for key,app in applications.items():
            if app['assessment_eligible']:
                populations=[p['id'] for p in e.populations.values() if p['run']==key and p['denominator']>0]
                cg['assessments'].append(assessment(fitted[key]['artifact_digest'],app['application_digest'],aid,store.outcome_facts.get('snapshot_digest'),populations,
                                                    {'observable_role_checks':'passed','prior_membership':prior_membership.get(key,{'status':'current_study_roles_checked'}),'base_prediction_independence':'declared','evaluation_independence':'declared','future_coverage_established':False},basis))
        private={'schema':'confidenceguard.private_manifest/1.0','analysis_id':aid,'spec':spec.evaluation.to_dict(),'cg2_spec':spec.to_dict(),'config':config.to_dict(),
                 'files':store.sources,'locators':e.locators,'methodology':CG2_METHOD,'fitted_methods':list(fitted.values()),'membership_sidecars':membership_sidecars}
        execution={'status':'completed','backend':'duckdb_local','engine_version':__import__('duckdb').__version__,'effective_limits':config.to_dict(),
                   'duration_seconds':time.monotonic()-started,'peak_workspace_bytes':work.peak,'estimated_peak_workspace_bytes':work.estimate,
                   'planning_estimate_is_upper_bound':False,'publication_policy':'whole_evaluation_atomic','resource_qualification':'Sampled controls can overshoot; no capacity guarantee.'}
        execution['effective_limits'].pop('scratch_directory',None)
        result=EvaluationResult(data,private,execution)
        store.verify();work.check('CG2 completed evidence publication',config.private_bytes)
        if len(result.json_text().encode())+len(json.dumps(private,allow_nan=False).encode())>config.private_bytes:raise EvaluationError('CG2 protected result and manifest exceed budget.','private_result_limit')
        if operation=='apply':_publish_application(store,spec,fitted,uncertainties,result,staging)
        return result
    except EvaluationError:raise
    except Exception as exc:
        from datatrust.contracts import AnalysisError
        if isinstance(exc,AnalysisError):raise EvaluationError('CG2 stopped; inspect source/resources.',exc.code,exc.stage) from exc
        raise EvaluationError('CG2 failed; no completed analytical evidence published.','evaluation_failed','methods') from exc
    finally:
        if work:work.close()


def _publish_application(store,spec,fitted,uncertainties,result,staging):
    if staging is None:raise EvaluationError('Application publication requires a parent-owned staging transaction.')
    destination=Path(staging['path']);temporary=Path(staging['writing'])
    compat.protect(tuple(s.path for s in spec.evaluation.sources),[destination,temporary,Path(spec.output_path)])
    compat.destination(destination)
    st=os.statvfs(destination.parent)
    if st.f_bavail*st.f_frsize<store.config.free_disk_bytes+256*1024**2:raise EvaluationError('Application output reserve unavailable.','disk_exhausted')
    published=False
    try:
        with temporary.open('r+b') as output:
            stat=os.fstat(output.fileno())
            if temporary.is_symlink() or (stat.st_dev,stat.st_ino)!=(staging['device'],staging['inode']) or stat.st_size!=0 or stat.st_mode&0o077:raise EvaluationError('Application staging ownership differs.','artifact_collision')
            header={'schema_version':'confidenceguard.prediction_application/1.0','evidence_state':'applied_unvalidated',
                    'methods':{k:v['artifact_digest'] for k,v in fitted.items()},'applications':result.data['cg2']['applications'],
                    'task':spec.evaluation.task.to_dict(),'models':{r.id:r.model.to_dict() for r in spec.evaluation.runs},
                    'meaning':'Historical evaluations do not prove improvement or future coverage for these inputs.'}
            output.write((json.dumps(header,allow_nan=False)+'\n').encode());size=0;h=hashlib.sha256()
            for key in fitted:
                table=store.run_tables[key]
                original=store.run_tables[fitted[key]['definition']['run']]
                query=f'SELECT r.ordinal,r.event_key,r.probs,r.cg_log_probs,r.point,r.cg_failure,o.probs,o.rank_score,o.decision,o.state FROM {table} r JOIN {original} o ON r.ordinal=o.ordinal ORDER BY r.event_key,r.ordinal'
                for ordinal,event,p,logs,point,failure,original_probabilities,original_score,decision,state in rows(store.con,query,batch=512):
                    value={'method':key,'source_ordinal':ordinal,'event_key':event,'probabilities':p,'log_probabilities':[value_state(v) for v in logs] if logs is not None else None,'point':point,
                           'original_probabilities':original_probabilities,'original_score':original_score,'original_decision':decision,'issuance_state':state,
                           'reason':failure,'evidence_state':'applied_unvalidated'}
                    if key in uncertainties:value['uncertainty']=[{'coverage':c,'output':json.loads(raw)} for c,raw in store.con.execute(f'SELECT coverage,output FROM {uncertainties[key]} WHERE ordinal=? ORDER BY coverage',[ordinal]).fetchall()]
                    raw=(json.dumps(exact(value),allow_nan=False,separators=(',',':'))+'\n').encode();output.write(raw);size+=len(raw);h.update(raw)
                    if size>store.config.workspace_bytes:raise EvaluationError('Application output budget exceeded.','workspace_limit')
                    if size%(1024**2)<len(raw):
                        store.work.check('application export',size);st=os.statvfs(destination.parent)
                        if st.f_bavail*st.f_frsize<store.config.free_disk_bytes:raise EvaluationError('Application filesystem reserve exhausted.','disk_exhausted')
            output.flush();os.fsync(output.fileno())
        store.verify();store.work.check('application publication',temporary.stat().st_size)
        os.link(temporary,destination);published=True
        info,_,_=compat.capture(destination,(str(destination.parent),),check=lambda:store.work.check('application identity',destination.stat().st_size))
        result.private['application_export']={'path':str(Path(spec.output_path).absolute()),'bytes':info['bytes'],'sha256':info['sha256'],'evidence_state':'applied_unvalidated'}
    except BaseException:
        raise
    finally:pass # Parent owns cleanup, including worker termination during a native call.


def _service(spec,config,operation,*,progress=None,cancel=None,allowed_roots=None,expected_fingerprint=None,_capture=None):
    spec,config,roots=_arguments2(spec,config,allowed_roots)
    worker_config=replace(config,result_bytes=config.private_bytes+config.result_bytes)
    staging=None
    if operation=='apply':
        if not spec.output_path:raise EvaluationError('Application requires output_path.')
        final=Path(spec.output_path).absolute();compat.protect(tuple(s.path for s in spec.evaluation.sources),[final]);compat.destination(final)
        final.parent.mkdir(parents=True,exist_ok=True)
        stage=final.parent/('.cg2-stage-'+uuid.uuid4().hex);writing=stage.with_suffix('.writing')
        fd=os.open(writing,os.O_CREAT|os.O_EXCL|os.O_RDWR,0o600)
        stat=os.fstat(fd);os.close(fd)
        staging={'path':str(stage),'writing':str(writing),'device':stat.st_dev,'inode':stat.st_ino}
    try:
        result=compat.supervise(_execute2,(spec,config,roots,operation,expected_fingerprint,staging,_capture),worker_config,progress=progress,cancel=cancel)
        if operation=='inspect':return result.to_dict()
        if cancel is not None and cancel.is_set():raise EvaluationError('CG2 cancelled before commit.','cancelled')
        if staging:result.execution['application_committed']=True
        result.seal()
        if len(result.json_text().encode())>config.private_bytes or len(json.dumps(result.to_dict()).encode())>config.result_bytes:raise EvaluationError('Final CG2 result budget exceeded.','result_limit')
        if staging:
            info,_,_=compat.capture(staging['path'],(str(Path(staging['path']).parent),))
            expected=result.private['application_export']
            if info['sha256']!=expected['sha256'] or info['bytes']!=expected['bytes']:raise EvaluationError('Staged application changed before commit.','artifact_changed')
            for source in result.private['files'].values():compat.capture(source['path'],roots,expected=source)
            if cancel is not None and cancel.is_set():raise EvaluationError('CG2 cancelled before application commit.','cancelled')
            os.link(staging['path'],spec.output_path) # Commit wins subsequent cancellation races.
        return result
    finally:
        if staging:
            for path in (staging['path'],staging['writing']):
                try:
                    stat=os.lstat(path)
                    if (stat.st_dev,stat.st_ino)==(staging['device'],staging['inode']):Path(path).unlink()
                except FileNotFoundError:pass


def fit_methods(spec,config=None,**kwargs):return _service(spec,config,'fit',**kwargs)
def apply_methods(spec,config=None,**kwargs):return _service(spec,config,'apply',**kwargs)
def evaluate_methods(spec,config=None,**kwargs):return _service(spec,config,'evaluate',**kwargs)
def study(spec,config=None,**kwargs):return _service(spec,config,'study',**kwargs)
def inspect_methods(spec,config=None,**kwargs):return _service(spec,config,'inspect',**kwargs)
