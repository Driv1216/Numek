"""Objective-specific proposals; authoritative evaluation stays in shared reducers."""
from dataclasses import dataclass,replace
import math
import numpy as np
from .contracts import EvaluationError
from .analytics import Evidence,literal,classification,regression,calibration,ranking,intervals,diagnostic_mean
from .history_metrics import metric_identity

PAIRED_PRECISION_POPULATION='common_issued_base_distinct_positive_denominators_v2'


def legacy_paired_precision(spec,artifact):
    return (spec.comparator=='paired' and spec.metric=='precision' and
            (artifact.get('objective_identity') or {}).get('paired_population_version')!=PAIRED_PRECISION_POPULATION)


@dataclass
class Objective:
    spec: object
    store: object
    run: object
    table: str
    eligible_sql: str
    loss_sql: str
    reducer: str
    native_metric: str
    native_transform: str = 'identity'
    target_label: str | None = None
    bounded: tuple = ()
    binary: bool = False
    proxy: str = 'exact_additive_loss'
    reference: object = None
    loss_table: str | None = None
    extra_metadata: dict | None = None

    @property
    def identity(self):
        identity={'definition_version':'failure_objective_v1',**self.spec.to_dict(),
                'eligible_population':self.eligible_sql,'conditional_denominator':self.denominator_kind,
                'learning_target':('D-only target-specific ranking performance surrogate: one minus discordance / positive precision staircase' if self.reducer=='ranking' else self.loss_sql),'proxy':self.proxy,'authoritative_metric':self.native_metric,
                'authoritative_transform':self.native_transform,'task':self.store.spec.task.to_dict(),
                'paired_reference':self.reference.identity if self.reference else None}
        if self.reference and self.spec.metric=='precision':
            identity.update(definition_version='failure_objective_v2',
                paired_population_version=PAIRED_PRECISION_POPULATION,
                paired_eligible_population=self.pair_eligible_sql,
                learning_target='D-only difference of precision ratio influence proxies on the common issued base, with each model\'s own positive denominator; proposal proxy, not a subgroup precision estimator.')
        if self.spec.metric=='r2':
            identity.update(definition_version='failure_objective_v2',
                diagnostic_target_policy='negative_squared_residual_for_r2_v2',
                learning_target='-('+self.loss_sql+')',
                learning_target_interpretation='Larger negative squared-residual targets are better, matching the native R2 direction. Proposal only: subgroup target variance still requires the authoritative R2 reducer.')
        if self.spec.comparator=='reference_period':
            identity.update(diagnostic_target_policy='historical_period_heads_and_matched_entity_delta_v1',
                learning_target_scope='Base pointwise target; historical proposal heads use the current period, negated reference period, and finite within-entity period-mean differences. Each actual proposal binding is retained separately. Native historical reducers and denominators are unchanged.')
        return identity

    @property
    def denominator_kind(self):
        return 'class_conditional_records' if self.spec.metric in {'false_negative_rate','false_positive_rate','precision','recall','specificity'} else 'eligible_records'

    @property
    def pair_eligible_sql(self):
        # Predicted-positive membership is a metric denominator, not common
        # predictor availability. Intersecting it makes paired precision equal.
        return "outcome_valid AND decision IS NOT NULL AND state IN ('issued','hypothetical')" if self.spec.metric=='precision' else self.eligible_sql

    def _paired_precision_training(self,keys,eligible,loss,role):
        ref=self.reference
        current_base=dict(self.store.con.execute(f'SELECT event_key,({self.pair_eligible_sql}) FROM {self.table} WHERE cg4_role=?',[role]).fetchall())
        other=self.store.con.execute(f'SELECT event_key,({ref.pair_eligible_sql}),({ref.eligible_sql}),({ref.loss_sql}) FROM {ref.table} WHERE cg4_role=?',[role]).fetchall()
        other={r[0]:(bool(r[1]),bool(r[2]),float(r[3]) if r[3] is not None else np.nan) for r in other}
        common=np.array([bool(current_base[k]) and other.get(k,(False,False,np.nan))[0] for k in keys])
        current=common&eligible
        reference=common&np.array([other.get(k,(False,False,np.nan))[1] for k in keys])
        reference_loss=np.array([other.get(k,(False,False,np.nan))[2] for k in keys])
        n=int(common.sum());counts=[int(current.sum()),int(reference.sum())]
        values=[float(np.mean(v[g])) if np.any(g) else None for v,g in ((loss,current),(reference_loss,reference))]
        proxy=np.full(len(keys),np.nan)
        if n and all(counts):
            a=np.zeros(len(keys));b=np.zeros(len(keys))
            a[current]=(loss[current]-values[0])/(counts[0]/n)
            b[reference]=(reference_loss[reference]-values[1])/(counts[1]/n)
            proxy[common]=(a-b)[common]
        defined=common&np.isfinite(proxy)
        if not hasattr(self,'training_support'):self.training_support={}
        self.training_support[role]={'assigned_records':len(keys),
            'native_eligible_before_proxy_and_pair_requirements':n,
            'learning_target_defined_records':int(defined.sum()),
            'excluded_after_proxy_pair_and_period_requirements':n-int(defined.sum()),
            'paired_population_version':PAIRED_PRECISION_POPULATION,
            'conditional_metric_support':{'current':counts[0],'reference':counts[1]},
            'D_reference_precision':dict(zip(('current','reference'),values)),
            'diagnostic_contribution_units':'dimensionless_ratio_influence',
            'inference_bounds':list(self.bounded),
            'bounds_scope':'Bounds concern the authoritative Bernoulli contributions, not this influence proxy.',
            'interpretation':'D-only frozen reference ratios propose regions. Native subgroup precision is recomputed with distinct conditional denominators; undefined reference ratios refuse the proxy.'}
        return keys,defined,proxy

    def training(self,role='D',*,period=None):
        if period is not None and (self.spec.comparator!='reference_period' or period not in {self.spec.reference_period,self.spec.current_period}):
            raise EvaluationError('Diagnostic period is not part of the declared historical contrast.','objective_period')
        rows=self.store.con.execute(f'SELECT event_key,({self.eligible_sql}),({self.loss_sql}) FROM {self.table} WHERE cg4_role=? ORDER BY event_key',[role]).fetchall()
        keys=[r[0] for r in rows];eligible=np.array([bool(r[1]) for r in rows]);loss=np.array([float(r[2]) if r[2] is not None else np.nan for r in rows])
        if self.reference and self.spec.metric=='precision':return self._paired_precision_training(keys,eligible,loss,role)
        if self.reducer=='ranking':
            records=self.store.con.execute(f'SELECT y={literal(self.store.spec.task.positive_class)},rank_score FROM {self.table} WHERE cg4_role=? ORDER BY event_key',[role]).fetchall()
            y=np.array([r[0] for r in records],dtype=bool);scores=np.array([r[1] if r[1] is not None else np.nan for r in records],dtype=float)
            scores*= -1 if self.run.score and self.run.score.direction=='lower' else 1
            pos=np.sort(scores[eligible&y]);neg=np.sort(scores[eligible&~y]);loss[:]=np.nan
            if len(pos) and len(neg):
                for flag,reference in ((True,neg),(False,pos)):
                    ids=np.flatnonzero(eligible&(y==flag));values=scores[ids]
                    lo=np.searchsorted(reference,values,'left');hi=np.searchsorted(reference,values,'right')
                    loss[ids]=(len(reference)-hi+.5*(hi-lo))/len(reference) if flag else (lo+.5*(hi-lo))/len(reference)
                if self.native_metric=='average_precision':
                    all_scores=np.sort(scores[eligible]);ids=np.flatnonzero(eligible&y)
                    loss[ids]=1-(len(pos)-np.searchsorted(pos,scores[ids],'left'))/(len(all_scores)-np.searchsorted(all_scores,scores[ids],'left'))
                loss=1-loss
        if self.native_metric=='log_loss':loss=np.minimum(loss,self.spec.training_clip)
        # Native R2 is better when larger, whereas its raw squared-residual
        # proxy is worse when larger. Align the target before shared heads and
        # paired/historical proxy contrasts; never change native metric SQL.
        if self.spec.metric=='r2':loss=-loss
        native_eligible=int(eligible.sum())
        eligible&=np.isfinite(loss)
        if self.reference:
            ref_keys,ref_eligible,ref_loss=self.reference.training(role)
            aligned={key:(e,v) for key,e,v in zip(ref_keys,ref_eligible,ref_loss)}
            for i,key in enumerate(keys):
                e,v=aligned.get(key,(False,np.nan));eligible[i]&=e
                loss[i]-=v
        if self.spec.comparator=='reference_period':
            periods=dict(self.store.con.execute(f'SELECT event_key,cg4_period FROM {self.table} WHERE cg4_role=?',[role]).fetchall())
            # A proposal head requests one frozen period; the authoritative
            # evaluator still recomputes both periods using the frozen gate.
            eligible&=np.array([periods[k]==(period or self.spec.current_period) for k in keys])
        if not hasattr(self,'training_support'):self.training_support={}
        self.training_support[role]={'assigned_records':len(keys),'native_eligible_before_proxy_and_pair_requirements':native_eligible,
            'learning_target_defined_records':int(eligible.sum()),'excluded_after_proxy_pair_and_period_requirements':native_eligible-int(eligible.sum()),
            'log_loss_training_clip':self.spec.training_clip if self.native_metric=='log_loss' else None,
            'diagnostic_contribution_units':(self.store.spec.task.units or 'target_units')+'^2' if self.spec.metric in {'rmse','r2'} else self.spec.units,
            'inference_bounds':list(self.bounded),'bounds_scope':'Predeclared pointwise contributions before any root/absolute interval transform; never H extrema.',
            'interpretation':'Diagnostic proposal support only. Final metric denominators are recomputed by the authoritative reducers.'}
        if self.spec.metric=='r2':self.training_support[role].update(
            diagnostic_target_policy='negative_squared_residual_for_r2_v2',
            bounds_scope='Declared bounds concern raw squared residuals, not their negated proposal target. A native nonadditive R2 interval remains unregistered.')
        return keys,eligible,loss

    def discovery_targets(self):
        """D-only proposal targets; never substitute these for native metrics.

        Historical difference can hide in favorable reference performance even
        when current risk is flat. Keep period targets separate, and add an
        entity-paired proxy where both conditional targets are observed. The
        paired proxy is a within-entity mean difference, not a replacement for
        the final event-weighted or nonadditive historical metric.
        """
        keys,current,loss=self.training('D');primary=dict(self.training_support['D'])
        def target(name,eligible,values,meaning,**extra):
            return {'name':name,'eligible':eligible,'loss':values,'binding':{
                'name':name,'definition_version':'historical_proposal_targets_v1' if self.spec.comparator=='reference_period' else 'objective_proposal_target_v1',
                'learning_target':meaning,'base_proxy':self.proxy,'conditional_denominator':self.denominator_kind,
                'assigned_D_records':len(keys),'defined_D_targets':int(eligible.sum()),
                'authoritative_metric_unchanged':True,**extra}}
        if self.spec.comparator!='reference_period':
            return keys,[target('objective',current,loss,self.identity['learning_target'])]
        reference_keys,reference,reference_loss=self.training('D',period=self.spec.reference_period)
        self.training_support['D']=primary
        if reference_keys!=keys:raise EvaluationError('Historical diagnostic rows changed during preparation.','source_changed')
        common={'reference_period':self.spec.reference_period,'current_period':self.spec.current_period,
                'diagnostic_contribution_units':primary['diagnostic_contribution_units'],
                'target_reference_population':'Eligible D-only observations before the diagnostic fit-row cap; S/H outcomes are not used.',
                'base_proxy_reference':'Pooled eligible D scores before period masking' if self.reducer=='ranking' else 'Declared base pointwise diagnostic target'}
        targets=[target('current_period',current,loss,'Current-period '+self.identity['learning_target'],
                        eligible_population=f"({self.eligible_sql}) AND cg4_role='D' AND cg4_period={literal(self.spec.current_period)}",**common),
                 target('reference_favorable',reference,-reference_loss,'Negated reference-period '+self.identity['learning_target'],
                        eligible_population=f"({self.eligible_sql}) AND cg4_role='D' AND cg4_period={literal(self.spec.reference_period)}",**common)]
        rows=self.store.con.execute(f'SELECT event_key,entity_key FROM {self.table} WHERE cg4_role=? ORDER BY event_key',['D']).fetchall()
        if [r[0] for r in rows]!=keys:raise EvaluationError('Historical diagnostic entity rows changed.','source_changed')
        means={}
        for i,(_,entity) in enumerate(rows):
            if entity is None:continue
            if not current[i] and not reference[i]:continue
            values=means.setdefault(entity,[0.,0,0.,0])
            for active,value,offset in ((current[i],loss[i],0),(reference[i],reference_loss[i],2)):
                if active:
                    count=values[offset+1];values[offset]=values[offset]*(count/(count+1))+float(value)/(count+1);values[offset+1]=count+1
        paired=np.zeros(len(keys),bool);delta=np.full(len(keys),np.nan);entities=set();nonfinite_delta_rows=0
        for i,(_,entity) in enumerate(rows):
            values=means.get(entity)
            if current[i] and values is not None and values[1] and values[3]:
                difference=values[0]-values[2]
                if math.isfinite(difference):paired[i]=True;delta[i]=difference;entities.add(entity)
                else:nonfinite_delta_rows+=1
        targets.append(target('entity_paired_period_delta',paired,delta,
            'D-only within-entity current mean base diagnostic target minus reference mean base diagnostic target; attached to eligible current rows.',
            eligible_population='D current-period conditional target rows belonging to an explicit entity with finite eligible targets in both frozen periods.',
            paired_entities=len(entities),current_eligible_rows=int(current.sum()),reference_eligible_rows=int(reference.sum()),
            entity_mean_numerics='incremental_weighted_mean_v1',nonfinite_delta_rows=nonfinite_delta_rows,
            sampling_interpretation='Diagnostic proxy only. Multiple current rows repeat their entity delta; final event-weighted estimands and all planned S/H rows remain authoritative. No paired-only confirmation population is inferred.',**common))
        return keys,targets

    def evaluate(self,where,scope):
        e=Evidence(self.store)
        if getattr(self.store,'cg4_binding',None):e.bind_relation(self.table,{**e.relations[self.table],'cg4':self.store.cg4_binding})
        reducer={'classification':classification,'regression':regression,'calibration':calibration,'ranking':ranking,'intervals':intervals}.get(self.reducer)
        if self.reducer=='uncertainty':
            from .uncertainty import evaluate_losses
            evaluate_losses(e,self.run,self.table,self.loss_table,{self.native_metric:self.extra_metadata[self.native_metric]},where,scope)
            m=next((m for m in e.measurements if m['metric']==self.native_metric),None)
        elif reducer:
            reducer(e,self.run,self.table,where,scope)
            matches=[m for m in e.measurements if m['metric']==self.native_metric and (self.target_label is None or m.get('data',{}).get('target')==self.target_label) and (not self.spec.interval or m.get('data',{}).get('interval')==self.spec.interval)]
            if self.target_label and self.native_metric in {'precision','recall','f1'} and self.store.spec.task.kind=='multiclass_classification':
                per=next((m for m in e.measurements if m['metric']=='per_class'),None)
                item=next((c for c in per['data']['classes'] if c['class']==self.target_label),None) if per else None
                if item:
                    key=self.native_metric;n=item['support'] if key=='recall' else item['predicted'] if key=='precision' else sum(item[k] for k in ('tp','fp','fn','tn'))
                    matches=[{'metric':key,'family':'performance','method_version':'1','value':item[key],'value_state':'finite' if item[key] is not None else 'undefined','denominator':n,'population_id':item[key+'_population_id'] if key in {'precision','recall'} else per['population_id'],'data':{'target':self.target_label},'sensitive_counts':[item[k] for k in ('tp','fp','fn','tn')]}]
            m=matches[0] if matches else None
        else:m=diagnostic_mean(e,self.run,self.table,where,scope,self.spec.metric,self.loss_sql,self.eligible_sql,units=self.spec.units)
        if m is None:return {'value':None,'value_state':'undefined','support':0,'reason':'metric_not_available','objective_identity':self.identity}
        if self.spec.metric_identity and metric_identity(m)!=self.spec.metric_identity:raise EvaluationError('The authoritative metric definition differs from the frozen hypothesis.','confirmation_metric_identity')
        value=m['value']
        if value is not None and self.native_transform=='one_minus':value=1-value
        if value is not None and self.native_transform=='square':value=value*value
        state=m['value_state']
        if value is not None and not math.isfinite(value):state='positive_infinity' if value>0 else 'negative_infinity' if value<0 else 'undefined';value=None
        return {'value':value,'value_state':state,'support':int(m['denominator']),
                'population_id':m['population_id'],'metric_identity':metric_identity(m),
                'objective_identity':self.identity,'reason':m.get('reason'),'measurement':m}


def uncertainty_contribution_contract(spec,task):
    """Frozen contribution semantics, independent of observed loss-table rows.

    Discovery/assessment still validate the exact metric against retained output
    metadata. Confirmation inspection can apply its registration checks when a
    future source contains H only, without computing H losses or needing D/S.
    """
    metric=spec.metric
    if not (metric.startswith(('pinball@','quantile_lt@','quantile_le@','central_interval_score@','interval_coverage@','interval_efficiency@','interval_empty_rate@','interval_uninformative_rate@','interval_output_availability@','set_coverage@','set_efficiency@','set_empty_rate@','set_uninformative_rate@','set_output_availability@')) or metric in {'wis','empirical_crps','sample_cdf_left','sample_cdf_right'}):return None
    binary=any(v in metric for v in ('coverage@','_rate@','quantile_lt@','quantile_le@','output_availability@'))
    bounds=(0.,1.) if binary or metric.startswith('sample_cdf_') else (0.,float(len(task.classes))) if metric.startswith('set_efficiency@') else ()
    return {'binary':binary,'bounded':spec.bounds or bounds}


def bind(spec,store):
    from .investigation_contracts import resolve_objective_units
    spec=resolve_objective_units(spec,store.spec.task)
    runs={r.id:r for r in store.spec.runs}
    if spec.run not in runs:raise EvaluationError('Objective run is absent.','objective_run')
    run=runs[spec.run];task=store.spec.task;metric=spec.metric
    valid='outcome_valid';loss='NULL::DOUBLE';reducer='diagnostic';native=metric;transform='identity';target=None;bounds=();binary=False;proxy='exact_additive_loss'
    issued="decision IS NOT NULL AND state IN ('issued','hypothetical')"
    point="point IS NOT NULL AND state IN ('issued','hypothetical') AND isfinite(point-y_num)"
    if metric in {'accuracy','error_rate','false_negative_rate','false_positive_rate','precision','recall','specificity','f1'}:
        if task.kind=='regression':raise EvaluationError('Classification objective on regression task.','objective_task')
        c=spec.target or task.positive_class
        if metric not in {'accuracy','error_rate'} and c not in task.classes:raise EvaluationError('Class-conditional objective requires a target.','objective_target')
        valid+=f' AND {issued}';loss='(decision<>y)::DOUBLE';reducer='classification';native='accuracy';bounds=(0.,1.);binary=True
        if metric=='error_rate':transform='one_minus'
        elif metric=='accuracy':loss='(decision=y)::DOUBLE'
        elif metric in {'false_negative_rate','recall'}:
            valid+=f' AND y={literal(c)}';loss=f'(decision<>{literal(c)})::DOUBLE' if metric=='false_negative_rate' else f'(decision={literal(c)})::DOUBLE';native='recall';transform='one_minus' if metric=='false_negative_rate' else 'identity'
        elif metric in {'false_positive_rate','specificity'}:
            valid+=f' AND y<>{literal(c)}';loss=f'(decision={literal(c)})::DOUBLE' if metric=='false_positive_rate' else f'(decision<>{literal(c)})::DOUBLE';native='specificity';transform='one_minus' if metric=='false_positive_rate' else 'identity'
        elif metric=='precision':valid+=f' AND decision={literal(c)}';loss=f'(y={literal(c)})::DOUBLE';native='precision'
        else:native='f1';loss='(decision=y)::DOUBLE';binary=False;bounds=();proxy='issued_accuracy_proxy_for_f1'
        if task.kind=='multiclass_classification' and native in {'precision','recall','f1'}:target=c
        if task.kind=='multiclass_classification' and native=='specificity':reducer='diagnostic';native=metric;transform='identity';target=c
    elif metric in {'brier','log_loss','reliability_diagram','calibration_residual'}:
        if task.kind=='regression' or not run.probabilities:raise EvaluationError('Probability objective requires probabilities.','objective_representation')
        valid+=' AND prob_valid';reducer='calibration'
        if metric=='brier':loss='brier';bounds=(0.,1. if task.kind=='binary_classification' else 2.)
        elif metric=='log_loss':loss="CASE WHEN log_infinite THEN 'Infinity'::DOUBLE ELSE log_loss END";proxy='finite_clipped_log_loss_for_proposals'
        else:
            c=spec.target or task.positive_class
            if c not in task.classes:raise EvaluationError('Calibration discovery requires a target class.','objective_target')
            loss=f'(y={literal(c)})::DOUBLE-probs[{task.classes.index(c)+1}]';bounds=(-1.,1.)
            if metric=='calibration_residual':reducer='diagnostic';target=c
            else:target='event' if task.kind=='binary_classification' else 'class:'+c;proxy='signed_calibration_residual_heads'
    elif metric in {'mae','mse','rmse','bias','material_error_rate','median_absolute_error','p90_absolute_error','p95_absolute_error','r2'}:
        if task.kind!='regression':raise EvaluationError('Regression objective requires regression.','objective_task')
        valid+=' AND '+point;reducer='regression'
        loss='point-y_num' if metric=='bias' else 'pow(point-y_num,2)' if metric in {'mse','rmse','r2'} else 'abs(point-y_num)'
        if metric=='mse':native='rmse';transform='square'
        if metric=='material_error_rate':
            threshold=task.material_error
            if threshold is None or spec.material_error is not None and spec.material_error!=threshold:raise EvaluationError('Bind the authoritative task material-error threshold.','objective_threshold')
            loss=f'(abs(point-y_num)>{threshold!r})::DOUBLE';bounds=(0.,1.);binary=True
        if metric in {'median_absolute_error','p90_absolute_error','p95_absolute_error','r2'}:proxy='point_loss_proxy_for_nonadditive_metric'
    elif metric in {'interval_coverage','interval_miscoverage','interval_width','central_interval_score'}:
        ids=[x.id for x in run.intervals]
        if task.kind!='regression' or spec.interval not in ids:raise EvaluationError('A declared regression interval is required.','objective_interval')
        i=ids.index(spec.interval);valid+=f' AND l{i} IS NOT NULL AND u{i} IS NOT NULL';reducer='intervals'
        if run.intervals[i].meaning!='prediction':raise EvaluationError('Uncertainty failure requires a prediction interval.','objective_interval')
        native='interval_coverage' if metric in {'interval_coverage','interval_miscoverage'} else metric
        loss=f'(y_num<l{i} OR y_num>u{i})::DOUBLE' if metric=='interval_miscoverage' else f'(y_num>=l{i} AND y_num<=u{i})::DOUBLE' if metric=='interval_coverage' else f'w{i}'
        if metric in {'interval_coverage','interval_miscoverage'}:bounds=(0.,1.);binary=True
        if metric=='interval_miscoverage':transform='one_minus'
        if metric=='central_interval_score':
            nominal=run.intervals[i].coverage
            if nominal is None or not run.intervals[i].central:raise EvaluationError('Central interval score requires a declared central interval.','objective_nominal')
            loss=f'w{i}+{2/(1-nominal)!r}*greatest(l{i}-y_num,0)+{2/(1-nominal)!r}*greatest(y_num-u{i},0)'
    elif metric in {'roc_auc','average_precision'}:
        if task.kind!='binary_classification':raise EvaluationError('Binary event ranking required.','objective_task')
        valid+=' AND rank_score IS NOT NULL';reducer='ranking';proxy='fixed_D_discordance' if metric=='roc_auc' else 'D_precision_staircase_and_discordance_proxy'
    elif (contribution_contract:=uncertainty_contribution_contract(spec,task)) is not None:
        table,metadata=extra_losses(store,run)
        if metric not in metadata or metadata[metric].get('histogram'):raise EvaluationError('The requested uncertainty objective was not retained.','objective_representation')
        outer=store.run_tables[spec.run];condition=f'x.event_key={outer}.event_key AND x.metric={literal(metric)}'
        valid=f'EXISTS(SELECT 1 FROM {table} x WHERE {condition} AND x.eligible)'
        loss=f'(SELECT CASE WHEN x.defined THEN x.value ELSE NULL END FROM {table} x WHERE {condition})'
        reducer='uncertainty'
        result=Objective(spec,store,run,outer,valid,loss,reducer,metric,**contribution_contract,loss_table=table,extra_metadata=metadata)
        if spec.comparator=='paired':result.reference=bind(replace(spec,run=spec.reference_run,reference_run=None,comparator='complement'),store)
        return result
    else:raise EvaluationError('No authoritative adapter for this failure objective.','objective_not_supported')
    result=Objective(spec,store,run,store.run_tables[spec.run],valid,loss,reducer,native,transform,target,spec.bounds or bounds,binary,proxy)
    if spec.comparator=='paired':
        if spec.reference_run==spec.run:raise EvaluationError('A paired comparison requires distinct runs.','objective_comparator')
        result.reference=bind(replace(spec,run=spec.reference_run,reference_run=None,comparator='complement'),store)
        result.proxy='paired_precision_ratio_influence_v2' if spec.metric=='precision' else 'paired_metric_specific_proposal_difference:'+proxy
    if spec.comparator=='reference_period':
        if not getattr(store,'cg4_periods',None) or {spec.reference_period,spec.current_period}-set(store.cg4_periods):raise EvaluationError('Historical objective periods are absent.','objective_period')
    return result


def extra_losses(store,run):
    cache=getattr(store,'cg4_extra_losses',{})
    if run.id in cache:return cache[run.id]
    if not hasattr(store,'representations'):store.representations={}
    from .uncertainty import build_losses
    from .contracts import digest
    uncertainty=getattr(store,'cg4_uncertainty_by_run',{}).get(run.id)
    table=store.run_tables[run.id]
    if not getattr(store,'cg4_confirmation',False):
        # No H outcome contributes even to intermediate uncertainty reductions
        # during discovery or its inspection.
        admitted='cg4_extra_input_'+digest(run.id)[:12]
        # rows() uses a separate DuckDB cursor/connection. Connection-local
        # temporary tables are invisible there; this relation belongs to the
        # job's disposable protected database and retains the H exclusion.
        store.con.execute(f'CREATE TABLE {admitted} AS SELECT * FROM {table} WHERE cg4_role<>\'H\'');table=admitted
    loss,metadata=build_losses(store,run,table,root=run.id,uncertainty_table=uncertainty)
    destination='cg4_losses_'+digest(run.id)[:12];store.con.execute(f'ALTER TABLE {loss} RENAME TO {destination}')
    cache[run.id]=(destination,metadata);store.cg4_extra_losses=cache
    return cache[run.id]


def adverse(spec,left,right=None):
    a=left.get('value');b=(right or {}).get('value')
    if left.get('value_state')=='positive_infinity':a=math.inf
    if left.get('value_state')=='negative_infinity':a=-math.inf
    if right and right.get('value_state')=='positive_infinity':b=math.inf
    if right and right.get('value_state')=='negative_infinity':b=-math.inf
    if a is None:return None
    def orient(v):
        if v is None:return None
        return abs(v) if spec.direction=='absolute' else spec.nominal-v if spec.direction=='nominal_shortfall' else -v if spec.direction=='lower' else v
    a=orient(a);b=orient(spec.ceiling) if spec.comparator=='ceiling' else orient(b)
    effect=a-b if b is not None else None
    return None if effect is not None and math.isnan(effect) else effect
