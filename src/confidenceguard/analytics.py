"""Full-population SQL reductions and bounded evidence retention."""
import json
import math
from dataclasses import replace
from .contracts import digest


def literal(value):return "'"+str(value).replace("'","''")+"'"


def wilson(k,n):
    if not n:return None
    z=1.959963984540054;p=k/n;d=1+z*z/n
    center=(p+z*z/(2*n))/d;half=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/d
    return {'lower':max(0.,center-half),'upper':min(1.,center+half),'level':.95,'method':'wilson','scope':'pointwise_independent_Bernoulli'}


def finite_data(value):
    if isinstance(value,float) and not math.isfinite(value):return {'value':None,'value_state':'positive_infinity' if value>0 else 'negative_infinity' if value<0 else 'undefined'}
    if isinstance(value,list):return [finite_data(v) for v in value]
    if isinstance(value,dict):return {k:finite_data(v) for k,v in value.items()}
    return value


class Evidence:
    def __init__(self,store):
        self.s=store;self.con=store.con;self.config=store.config;self.measurements=[];self.populations={};self.locators={};self.checks=[]
        self.inference=self.config.sampling.mode=='independent_rows' and not any(f['repeated_entities'] for f in store.run_facts.values())
        self.relations={};self.population_counts={};self.table=None
        for run in store.spec.runs:
            source=next(s for s in store.spec.sources if s.id==run.source).to_dict();source.pop('path')
            self.bind_relation(store.run_tables[run.id],{'kind':'normalized_run','run':run.id,'declaration_digest':digest(run.to_dict()),'source_sha256':store.sources[run.source]['sha256'],'source_interpretation':source,'task_digest':digest(store.spec.task.to_dict()),'normalization_version':'1','probability_tolerance':store.config.probability_tolerance,'outcome_snapshot':store.outcome_facts.get('snapshot_digest'),'context_snapshot':store.context_facts['snapshot_digest']})

    def bind_relation(self,table,lineage):
        self.relations[table]=lineage

    def use_relation(self,table):
        if table not in self.relations:raise AssertionError('Unbound analytical relation')
        self.table=table

    def grouped_count(self,where,n):
        """Reuse an exact SQL GROUP BY count; avoid a full scan per declared class."""
        key=digest([self.relations[self.table],where])
        if key in self.population_counts and self.population_counts[key]!=n:raise AssertionError('Conflicting grouped population count')
        self.population_counts[key]=n

    def population(self,run,scope,where,n,denominator_kind='eligible_records'):
        """Identity binds frozen relation lineage AND eligibility, never a transient table name.

        Denominator is record support, not an F1 formula or a number of macro classes.
        Check each distinct reduction against SQL while its relation still exists.
        """
        lineage=self.relations[self.table]
        definition={'run':run.id,'scope':scope,'definition':where,'lineage':lineage,'denominator_kind':denominator_kind}
        pid='pop_'+digest(definition)[:32]
        key=digest([lineage,where])
        if key not in self.population_counts:
            self.population_counts[key]=self.con.execute(f'SELECT count(*) FROM {self.table} WHERE {where}').fetchone()[0]
        if self.population_counts[key]!=n:raise AssertionError('Analytical population denominator differs from eligibility count')
        record={'id':pid,**definition,'denominator':n}
        if pid in self.populations and self.populations[pid]!=record:raise AssertionError('Conflicting population identity')
        self.populations[pid]=record
        return pid

    def validate_populations(self):
        for m in self.measurements:
            p=self.populations[m['population_id']]
            if (p['run'],p['scope'],p['denominator'],p['denominator_kind'])!=(m['run'],m['scope'],m['denominator'],m['denominator_kind']):raise AssertionError('Inconsistent measurement population')

    def add(self,run,scope,family,metric,value=None,n=0,*,data=None,counts=(),where='true',reason=None,units=None,basis='measured',state=None,denominator_kind='eligible_records'):
        if family in {'performance','confusion','failures','candidate','high_confidence_decision'} and run.decision.rule!='none' and not (run.prediction or run.decision.column):basis='simulated'
        if reason:basis='unavailable'
        pid=self.population(run,scope,where,n,denominator_kind)
        m={'id':f'm{len(self.measurements)+1}','run':run.id,'scope':scope,'family':family,'metric':metric,'method_version':'1','population_id':pid,'denominator':n,'value':value,'value_state':state or ('finite' if value is not None else 'undefined'),'applicability':'blocked' if reason else 'applicable','execution':'completed' if not reason else 'not_run','reason':reason,'units':units,'basis':basis,'interpretation':'descriptive','method_standing':'established_method','sensitive_counts':list(counts),'data':data or {},'disclosure_group':scope.split('/')[0] if scope!='overall' else family,'support_warning':n<self.config.support_warning,'evidence_refs':[]}
        if isinstance(value,float) and not math.isfinite(value):m['value']=None;m['value_state']='positive_infinity' if value>0 else 'negative_infinity'
        m['data']=finite_data(m['data'])
        m['denominator_kind']=denominator_kind
        self.measurements.append(m)
        return m

    def ratio(self,run,scope,family,metric,k,n,**kw):
        m=self.add(run,scope,family,metric,k/n if n else None,n,counts=(k,n-k),reason=None if n else 'zero_denominator',**kw)
        if self.inference and n:m['uncertainty']=wilson(k,n);m['interpretation']='inferential'
        return m

    def witnesses(self,m,run,table,where,columns):
        if len(self.locators)>=self.config.max_details:return
        for ordinal, in self.con.execute(f'SELECT ordinal FROM {table} WHERE {where} ORDER BY ordinal LIMIT ?',[min(self.config.witnesses,self.config.max_details-len(self.locators))]).fetchall():
            ref='ref_'+digest([run.id,ordinal,m['metric'],m['scope']])[:24]
            payload=self.con.execute(f'SELECT payload FROM {self.s.tables[run.source]} WHERE ordinal=?',[ordinal]).fetchone()[0]
            self.locators[ref]={'source':run.source,'ordinal':ordinal,'projection_columns':sorted(json.loads(payload)),'projection_digest':digest(json.loads(payload)),'columns':[c for c in columns if c]}
            outcome=self.s.outcomes
            if outcome:
                event=self.con.execute(f'SELECT event_key FROM {table} WHERE ordinal=? LIMIT 1',[ordinal]).fetchone()[0]
                found=self.con.execute('SELECT ordinal FROM outcome_unique WHERE event_key=?',[event]).fetchone()
                if found:
                    op=self.con.execute(f'SELECT payload FROM {self.s.tables[outcome.source]} WHERE ordinal=?',[found[0]]).fetchone()[0]
                    related={'source':outcome.source,'ordinal':found[0],'projection_columns':sorted(json.loads(op)),'projection_digest':digest(json.loads(op)),'columns':[outcome.column]}
                    self.locators[ref]['related']=[related]
            m['evidence_refs'].append(ref)

    def paired_witnesses(self,m,left,right,ta,tb,where):
        table='pair_witnesses'
        self.con.execute(f'CREATE TEMP TABLE {table} AS SELECT b.* FROM {ta} a JOIN {tb} b USING(event_key) WHERE {where}')
        self.witnesses(m,right,table,'true',[right.decision.column or right.prediction])
        for ref in m['evidence_refs']:
            loc=self.locators[ref]
            event=self.con.execute(f'SELECT event_key FROM {table} WHERE ordinal=?',[loc['ordinal']]).fetchone()[0]
            ordinal=self.con.execute(f'SELECT ordinal FROM {ta} WHERE event_key=?',[event]).fetchone()[0]
            payload=json.loads(self.con.execute(f'SELECT payload FROM {self.s.tables[left.source]} WHERE ordinal=?',[ordinal]).fetchone()[0])
            loc.setdefault('related',[]).append({'source':left.source,'ordinal':ordinal,'projection_columns':sorted(payload),'projection_digest':digest(payload),'columns':[c for c in [left.decision.column or left.prediction] if c]})
        self.con.execute(f'DROP TABLE {table}')


def distributions(e,r,table):
    e.use_relation(table)
    """Descriptive predictive artifacts do not require observed labels or issuance."""
    con=e.con;n=con.execute(f'SELECT count(*) FROM {table}').fetchone()[0]
    values=con.execute(f'SELECT state,count(*) FROM {table} GROUP BY state ORDER BY state').fetchall()
    e.add(r,'overall','prediction_distributions','recorded_decision_states',n=n,data={'states':[{'state':s,'count':v} for s,v in values]},counts=[v for _,v in values])
    if r.probabilities:
        nn,mean,entropy,margin=con.execute(f'SELECT count(*),avg(list_max(probs)),avg(list_sum(list_transform(probs,x->CASE WHEN x>0 THEN -x*ln(x) ELSE 0 END))),avg(list_sort(probs)[-1]-list_sort(probs)[-2]) FROM {table} WHERE prob_valid').fetchone()
        hist=con.execute(f'SELECT least(9,floor(list_max(probs)*10))::INTEGER,count(*) FROM {table} WHERE prob_valid GROUP BY 1 ORDER BY 1').fetchall()
        e.add(r,'overall','prediction_distributions','probability_concentration',mean,nn,data={'mean_entropy_nats':entropy,'mean_top_two_margin':margin,'maximum_probability_histogram':[{'bin':b,'count':v} for b,v in hist],'interpretation':'Descriptive supplied probability concentration; no epistemic/aleatoric decomposition or correctness assurance.'},counts=[v for _,v in hist],where='prob_valid',reason=None if nn else 'no_valid_probability_vectors')
    for column,label,predicate in [('rank_score','ranking_score','rank_score IS NOT NULL'),('score_max','class_score_maximum','score_valid') if r.score and r.score.columns else ('selector','selection_score','selector IS NOT NULL'),('point','point_prediction','point IS NOT NULL')]:
        nn,lo,hi,q1,q2,q3=con.execute(f'SELECT count(*),min({column}),max({column}),quantile_cont({column},.25),quantile_cont({column},.5),quantile_cont({column},.75) FROM {table} WHERE {predicate}').fetchone()
        if nn:e.add(r,'overall','prediction_distributions',label,n=nn,data={'minimum':lo,'maximum':hi,'q25':q1,'median':q2,'q75':q3,'interpretation':'Supplied native units; no probability interpretation inferred.'},where=predicate)


def classification(e,r,table,where,scope):
    e.use_relation(table)
    con=e.con;classes=e.s.spec.task.classes
    valid=f'({where}) AND outcome_valid AND decision IS NOT NULL AND state IN (\'issued\',\'hypothetical\')'
    n,correct=con.execute(f'SELECT count(*),count(*) FILTER(WHERE decision=y) FROM {table} WHERE {valid}').fetchone()
    e.ratio(r,scope,'performance','accuracy',correct,n,where=valid)
    counts=con.execute(f'SELECT y,decision,count(*) FROM {table} WHERE {valid} GROUP BY y,decision ORDER BY y,decision').fetchall()
    e.add(r,scope,'confusion','confusion',n=n,data={'cells':[{'actual':a,'predicted':b,'count':v} for a,b,v in counts]},counts=[v for _,_,v in counts],where=valid,reason=None if n else 'no_eligible_issued_decisions')
    per=[]
    for c in classes:
        tp=sum(v for a,b,v in counts if a==b==c);fn=sum(v for a,b,v in counts if a==c and b!=c);fp=sum(v for a,b,v in counts if b==c and a!=c);tn=n-tp-fn-fp
        item={'class':c,'support':tp+fn,'predicted':tp+fp,'tp':tp,'fn':fn,'fp':fp,'tn':tn,'precision':tp/(tp+fp) if tp+fp else None,'recall':tp/(tp+fn) if tp+fn else None,'f1':2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else None}
        e.grouped_count(f'{valid} AND y={literal(c)}',tp+fn)
        e.grouped_count(f'{valid} AND decision={literal(c)}',tp+fp)
        e.grouped_count(f'{valid} AND y<>{literal(c)}',tn+fp)
        item['recall_population_id']=e.population(r,scope,f'{valid} AND y={literal(c)}',tp+fn,'class_conditional_records')
        item['precision_population_id']=e.population(r,scope,f'{valid} AND decision={literal(c)}',tp+fp,'class_conditional_records')
        item['f1_formula_denominator']=2*tp+fp+fn
        if e.inference:item['recall_interval']=wilson(tp,tp+fn);item['precision_interval']=wilson(tp,tp+fp)
        per.append(item)
    e.add(r,scope,'confusion','per_class',n=n,data={'classes':per,'macro_population':'classes with observed outcome support'},counts=[v for x in per for v in (x['tp'],x['fn'],x['fp'],x['tn'])],where=valid)
    supported=[x for x in per if x['support']]
    for metric,key in [('balanced_accuracy','recall'),('macro_f1_observed_classes','f1')]:
        value=sum(x[key] for x in supported)/len(supported) if supported else None
        m=e.add(r,scope,'performance',metric,value,n,data={'supported_classes':len(supported),'declared_classes':len(classes),'aggregation_denominator':'observed_support_classes'},where=valid,denominator_kind='evaluation_support',reason=None if value is not None else 'no_observed_class_support')
        if scope=='overall':m['disclosure_group']='confusion'
    weighted=sum((x['f1'] or 0)*x['support'] for x in per)/n if n else None
    m=e.add(r,scope,'performance','support_weighted_f1',weighted,n,where=valid,denominator_kind='evaluation_support')
    if scope=='overall':m['disclosure_group']='confusion'
    if e.s.spec.task.kind=='binary_classification':
        x=next(x for x in per if x['class']==e.s.spec.task.positive_class)
        for metric,k,d,predicate in [('precision',x['tp'],x['tp']+x['fp'],f'decision={literal(x["class"])}'),('recall',x['tp'],x['support'],f'y={literal(x["class"])}'),('specificity',x['tn'],x['tn']+x['fp'],f'y<>{literal(x["class"])}')]:e.ratio(r,scope,'performance',metric,k,d,where=f'{valid} AND {predicate}',denominator_kind='class_conditional_records')
        m=e.add(r,scope,'performance','f1',x['f1'],n,where=valid,denominator_kind='evaluation_support',data={'formula_denominator':2*x['tp']+x['fp']+x['fn']},counts=(x['tp'],x['fp'],x['fn'],x['tn']),reason=None if x['f1'] is not None else 'zero_denominator')
        if scope=='overall':m['disclosure_group']='confusion'
    if scope=='overall':
        m=e.add(r,scope,'failures','issued_errors',n-correct,n,counts=(n-correct,correct),where=valid)
        e.witnesses(m,r,table,f'{valid} AND decision<>y',[r.decision.column or r.prediction,r.inline_outcome])
    if r.decision.candidate_evaluation:
        cn,cc=con.execute(f'SELECT count(*),count(*) FILTER(WHERE candidate=y) FROM {table} WHERE ({where}) AND outcome_valid AND candidate IS NOT NULL').fetchone()
        e.ratio(r,scope,'candidate','candidate_accuracy',cc,cn,where=f'({where}) AND outcome_valid AND candidate IS NOT NULL')


def regression(e,r,table,where,scope):
    e.use_relation(table)
    valid=f'({where}) AND outcome_valid AND point IS NOT NULL AND state IN (\'issued\',\'hypothetical\')'
    con=e.con;n=con.execute(f'SELECT count(*) FROM {table} WHERE {valid}').fetchone()[0]
    if not n:
        for metric in ('mae','rmse','bias','median_absolute_error','p90_absolute_error','p95_absolute_error','r2'):e.add(r,scope,'performance',metric,n=0,reason='no_eligible_point_predictions',where=valid)
        return
    # Scaling avoids overflow in sums of squares. An unrepresentable residual blocks statistics.
    view=f'(SELECT *,point-y_num err FROM {table} WHERE {valid})'
    unsafe,scale=con.execute(f'SELECT count(*) FILTER(WHERE NOT isfinite(err)),max(abs(err)) FROM {view}').fetchone()
    if unsafe:
        e.add(r,scope,'performance','regression_losses',n=n,reason='unrepresentable_residual',counts=(unsafe,),where=valid);return
    scale=scale or 1.
    mae,rmse,bias,median,p90,p95=con.execute(f'SELECT avg(abs(err)/?),sqrt(avg(pow(err/?,2))),avg(err/?),quantile_cont(abs(err),.5),quantile_cont(abs(err),.9),quantile_cont(abs(err),.95) FROM {view}',[scale,scale,scale]).fetchone()
    for metric,value in [('mae',mae*scale),('rmse',rmse*scale),('bias',bias*scale),('median_absolute_error',median),('p90_absolute_error',p90),('p95_absolute_error',p95)]:
        e.add(r,scope,'performance',metric,value,n,units=e.s.spec.task.units,where=valid)
    yscale=con.execute(f'SELECT max(abs(y_num)) FROM {view}').fetchone()[0] or 1.
    variance,mse=con.execute(f'SELECT var_pop(y_num/?),avg(pow(err/?,2)) FROM {view}',[yscale,scale]).fetchone()
    ratio=scale/yscale
    r2=1-(mse/variance)*ratio**2 if variance and n>1 and ratio<1e150 else None
    e.add(r,scope,'performance','r2',r2,n,where=valid,reason=None if r2 is not None else 'constant_target_or_unsafe_arithmetic')
    if e.s.spec.task.material_error is not None:
        k=con.execute(f'SELECT count(*) FROM {view} WHERE abs(err)>?',[e.s.spec.task.material_error]).fetchone()[0]
        m=e.ratio(r,scope,'failures','material_error_rate',k,n,where=valid)
        if scope=='overall':e.witnesses(m,r,table,f'{valid} AND abs(point-y_num)>{e.s.spec.task.material_error!r}',[r.prediction])
    if scope=='overall':
        histogram=[]
        for value,count in con.execute(f'SELECT CASE WHEN err<0 THEN \'negative\' WHEN err>0 THEN \'positive\' ELSE \'zero\' END,count(*) FROM {view} GROUP BY 1').fetchall():histogram.append({'sign':value,'count':count})
        e.add(r,scope,'residuals','residual_distribution',n=n,data={'signs':histogram,'absolute_quantiles':{'p50':median,'p90':p90,'p95':p95}},counts=[x['count'] for x in histogram],where=valid)


def ranking(e,r,table,where,scope):
    e.use_relation(table)
    valid=f'({where}) AND outcome_valid AND rank_score IS NOT NULL'
    positive=literal(e.s.spec.task.positive_class);direction=-1 if r.score and r.score.direction=='lower' else 1
    n,p=e.con.execute(f'SELECT count(*),count(*) FILTER(WHERE y={positive}) FROM {table} WHERE {valid}').fetchone();neg=n-p
    if not n or not p or not neg:
        for m in ('roc_auc','average_precision'):e.add(r,scope,'ranking',m,n=n,reason='requires_positive_and_negative_outcomes',counts=(p,neg),where=valid)
        return
    grouped=f'(SELECT rank_score*{direction} score,count(*) n,count(*) FILTER(WHERE y={positive}) p FROM {table} WHERE {valid} GROUP BY 1)'
    auc=e.con.execute(f'SELECT sum(p*(before_neg+.5*(n-p)))/?/? FROM (SELECT *,coalesce(sum(n-p) OVER(ORDER BY score ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING),0) before_neg FROM {grouped})',[p,neg]).fetchone()[0]
    ap=e.con.execute(f'SELECT sum((p/?)*(cp/cn)) FROM (SELECT *,sum(p) OVER(ORDER BY score DESC) cp,sum(n) OVER(ORDER BY score DESC) cn FROM {grouped})',[p]).fetchone()[0]
    e.add(r,scope,'ranking','roc_auc',auc,n,counts=(p,neg),where=valid)
    e.add(r,scope,'ranking','average_precision',ap,n,counts=(p,neg),data={'prevalence':p/n,'definition':'non_interpolated_recall_increment'},where=valid)
    if scope=='overall':
        groups=e.con.execute(f'SELECT count(*) FROM {grouped}').fetchone()[0];stride=max(1,math.ceil(groups/max(1,e.config.curve_points-2)))
        curve=e.con.execute(f'SELECT score,cp,cn FROM (SELECT *,row_number() OVER(ORDER BY score DESC) i,sum(p) OVER(ORDER BY score DESC) cp,sum(n) OVER(ORDER BY score DESC) cn FROM {grouped}) WHERE (i-1)%?=0 OR i=? ORDER BY score DESC',[stride,groups]).fetchall()
        points=[{'threshold':None,'state':'none','tpr':0.,'fpr':0.,'precision':None,'recall':0.}]+[{'threshold':s*direction,'state':'finite','tpr':a/p,'fpr':(b-a)/neg,'precision':a/b,'recall':a/p} for s,a,b in curve]
        e.add(r,scope,'ranking_curve','roc_pr_curve',n=n,data={'points':points,'full_score_groups':groups,'retained_points':len(points),'selection':'label_independent_score_group_order','scalar_metrics_use_all_groups':True},counts=(p,neg),where=valid)


def calibration(e,r,table,where,scope):
    e.use_relation(table)
    valid=f'({where}) AND outcome_valid AND prob_valid';con=e.con
    n,mean,loss,infinite=con.execute(f'SELECT count(*),avg(brier),avg(log_loss),count(*) FILTER(WHERE log_infinite) FROM {table} WHERE {valid}').fetchone()
    e.add(r,scope,'probability_quality','brier',mean,n,data={'definition':'binary_event_squared_error' if e.s.spec.task.kind=='binary_classification' else 'unhalved_multiclass_sum'},where=valid,reason=None if n else 'no_eligible_probabilities')
    e.add(r,scope,'probability_quality','log_loss',None if infinite else loss,n,state='positive_infinity' if infinite else None,counts=(infinite,n-infinite),data={'zero_true_class_probability':infinite,'logarithm':'natural'},where=valid,reason=None if n else 'no_eligible_probabilities')
    if not n:return
    diagrams=[]
    if e.s.spec.task.kind=='binary_classification':
        idx=e.s.spec.task.classes.index(e.s.spec.task.positive_class)+1;diagrams.append(('event',f'probs[{idx}]',f'y={literal(e.s.spec.task.positive_class)}','true'))
    else:
        for i,c in enumerate(e.s.spec.task.classes):diagrams.append(('class:'+c,f'probs[{i+1}]',f'y={literal(c)}','true'))
    diagrams.extend([('top_label','list_max(probs)','top_label=y','top_label IS NOT NULL'),('supplied_or_derived_decision','confidence','decision=y','confidence IS NOT NULL AND state IN (\'issued\',\'hypothetical\')')])
    for label,prob,event,extra in diagrams:
        bins=e.config.calibration_bins
        data=con.execute(f'SELECT least({bins-1},floor(({prob})*{bins}))::INTEGER bin,count(*) n,avg({prob}),count(*) FILTER(WHERE {event}) FROM {table} WHERE {valid} AND ({extra}) GROUP BY 1 ORDER BY 1').fetchall()
        dn=sum(row[1] for row in data);bybin={b:(nn,mp,k) for b,nn,mp,k in data};out=[];ece=0
        for b in range(bins):
            nn,mp,k=bybin.get(b,(0,None,0));freq=k/nn if nn else None
            out.append({'bin':b,'lower':b/bins,'upper':(b+1)/bins,'upper_inclusive':b==bins-1,'count':nn,'mean_probability':mp,'observed_frequency':freq,'interval':wilson(k,nn) if e.inference else None,'limited_bin_support':nn<e.config.bin_support_warning})
            if nn:ece+=nn/dn*abs(freq-mp)
        e.add(r,scope,'calibration','reliability_diagram',ece if dn else None,dn,data={'target':label,'bins':out,'ece_definition':'sum_bin_mass_absolute_frequency_gap','binning':'fixed_equal_width'},counts=[v for _,nn,_,k in data for v in (k,nn-k)],where=f'{valid} AND ({extra})',basis='simulated' if label=='supplied_or_derived_decision' and not (r.prediction or r.decision.column) and r.decision.rule!='none' else 'measured',reason=None if dn else 'no_eligible_calibration_target')
        if label=='top_label':
            hw=f'{valid} AND top_label IS NOT NULL AND list_max(probs)>={e.config.high_confidence!r}'
            hn,errors=con.execute(f'SELECT count(*),count(*) FILTER(WHERE top_label<>y) FROM {table} WHERE {hw}').fetchone()
            m=e.ratio(r,scope,'high_confidence','high_confidence_top_class_error_rate',errors,hn,where=hw,data={'threshold':e.config.high_confidence,'meaning':'unique_top_probability_class_mismatch_not_issued_decision'})
            all_errors=con.execute(f'SELECT count(*) FROM {table} WHERE {valid} AND top_label IS NOT NULL AND top_label<>y').fetchone()[0]
            e.ratio(r,scope,'high_confidence','share_of_top_class_errors_high_confidence',errors,all_errors,where=f'{valid} AND top_label IS NOT NULL AND top_label<>y')
            if scope=='overall':e.witnesses(m,r,table,f'{hw} AND top_label<>y',list(r.probabilities.columns.values()) if r.probabilities.columns else [r.probabilities.positive_column])
    hw=f'{valid} AND confidence>={e.config.high_confidence!r} AND state IN (\'issued\',\'hypothetical\')'
    hn,errors=con.execute(f'SELECT count(*),count(*) FILTER(WHERE decision<>y) FROM {table} WHERE {hw}').fetchone()
    e.ratio(r,scope,'high_confidence_decision','high_confidence_decision_error_rate',errors,hn,where=hw,data={'confidence':'probability_assigned_to_chosen_class'})


def intervals(e,r,table,where,scope):
    e.use_relation(table)
    for i,interval in enumerate(r.intervals):
        valid=f'({where}) AND outcome_valid AND w{i} IS NOT NULL'
        if interval.meaning!='prediction':
            e.add(r,scope,'intervals','interval_coverage',reason='interval_is_not_a_prediction_interval',data={'interval':interval.id},where='false',denominator_kind='not_evaluated');continue
        n,k,lower,upper,mean,median,p95=e.con.execute(f'SELECT count(*),count(*) FILTER(WHERE y_num BETWEEN l{i} AND u{i}),count(*) FILTER(WHERE y_num<l{i}),count(*) FILTER(WHERE y_num>u{i}),avg(w{i}),quantile_cont(w{i},.5),quantile_cont(w{i},.95) FROM {table} WHERE {valid}').fetchone()
        e.ratio(r,scope,'intervals','interval_coverage',k,n,data={'interval':interval.id,'nominal':interval.coverage,'lower_misses':lower,'upper_misses':upper,'maturity':'supplied_outcome_eligibility'},where=valid)
        e.add(r,scope,'intervals','interval_width',mean,n,data={'interval':interval.id,'median':median,'p95':p95},counts=(lower,upper,k),units=e.s.spec.task.units,where=valid)
        if interval.central:
            alpha=1-interval.coverage
            score=e.con.execute(f'SELECT avg(w{i}+2/?*greatest(l{i}-y_num,0)+2/?*greatest(y_num-u{i},0)) FROM {table} WHERE {valid}',[alpha,alpha]).fetchone()[0]
            e.add(r,scope,'intervals','central_interval_score',score,n,data={'interval':interval.id,'alpha':alpha},where=valid,units=e.s.spec.task.units)


def evaluate_scope(e,r,table,where,scope):
    e.use_relation(table)
    e.s.work.check('analytical population reductions')
    n,labeled,issued=e.con.execute(f'SELECT count(*),count(*) FILTER(WHERE outcome_valid),count(*) FILTER(WHERE state=\'issued\') FROM {table} WHERE {where}').fetchone()
    e.add(r,scope,'availability','population_coverage',labeled/n if n else None,n,data={'records':n,'eligible_outcomes':labeled,'issued':issued,'issuance_meaning':'recorded' if r.prediction or r.decision.column or r.decision.state_column else 'unestablished'},counts=(labeled,n-labeled,issued,n-issued),where=where)
    if e.s.spec.task.kind=='regression':regression(e,r,table,where,scope);intervals(e,r,table,where,scope)
    else:
        classification(e,r,table,where,scope)
        if e.s.spec.task.kind=='binary_classification':ranking(e,r,table,where,scope)
        if r.probabilities:calibration(e,r,table,where,scope)


def policies(e,r,table):
    e.use_relation(table)
    for pi,policy in enumerate(p for p in e.s.spec.policies if p.run==r.id):
        family='policy:'+policy.id;scope='overall';config=e.config;task=e.s.spec.task
        if policy.kind=='supplied_cost':
            if task.kind=='regression':e.add(r,scope,family,'empirical_cost',reason='categorical_action_outcome_costs_require_classification',where='false',denominator_kind='not_evaluated');continue
            clauses=[]
            for action,costs in policy.costs.items():
                for outcome,cost in costs.items():clauses.append(f'WHEN (CASE WHEN state=\'abstained\' THEN \'abstained\' ELSE decision END)={literal(action)} AND y={literal(outcome)} THEN {cost!r}')
            if not clauses:e.add(r,scope,family,'empirical_cost',reason='cost_table_required',where='false',denominator_kind='not_evaluated');continue
            n,covered,cost=e.con.execute(f'SELECT count(*),count(cost),avg(cost) FROM (SELECT CASE {" ".join(clauses)} END cost FROM {table} WHERE outcome_valid AND state IN (\'issued\',\'abstained\'))').fetchone()
            e.add(r,scope,family,'empirical_cost',cost if covered==n else None,n,reason=None if covered==n and n else 'incomplete_cost_table_or_empty_population',basis='simulated',data={'covered':covered,'unchanged_outcome_assumption':True},where="outcome_valid AND state IN ('issued','abstained')");continue
        binary=policy.kind in {'probability_threshold','score_threshold'}
        if policy.kind=='probability_threshold' and task.kind=='binary_classification' and r.probabilities:score=f'probs[{task.classes.index(task.positive_class)+1}]';direction=1
        elif policy.kind=='score_threshold' and task.kind=='binary_classification' and r.score and r.score.column:score='rank_score';direction=1 if r.score.direction=='higher' else -1
        elif policy.kind=='confidence_abstention' and task.kind!='regression' and (r.prediction or r.decision.column or r.decision.rule!='none'):score='confidence';direction=1
        elif policy.kind=='selection_abstention' and r.selection:score='selector';direction=1 if r.selection.direction=='higher' else -1
        elif policy.kind=='interval_abstention' and task.kind=='regression' and policy.interval in [v.id for v in r.intervals]:score=f'w{[v.id for v in r.intervals].index(policy.interval)}';direction=-1
        else:e.add(r,scope,family,'policy_curve',reason='required_score_decision_or_interval_unavailable',basis='simulated',where='false',denominator_kind='not_evaluated');continue
        valid=f'{score} IS NOT NULL'
        if not binary:valid+=' AND '+('point IS NOT NULL AND (NOT outcome_valid OR isfinite(point-y_num))' if task.kind=='regression' else 'decision IS NOT NULL')
        if task.kind=='regression':loss='abs(point-y_num)';positive='false'
        else:loss='CASE WHEN decision=y THEN 0.::DOUBLE ELSE 1.::DOUBLE END';positive=f'y={literal(task.positive_class)}' if binary else 'false'
        bad=f'abs(point-y_num)>{task.material_error!r}' if task.kind=='regression' and task.material_error is not None else 'false'
        cost_ready=bool(policy.costs) and not binary and task.kind!='regression' and all(c in policy.costs and all(y in policy.costs[c] for y in task.classes) for c in (*task.classes,'abstained'))
        acost=rcost='0.::DOUBLE'
        if cost_ready:
            acost='CASE '+ ' '.join(f'WHEN decision={literal(c)} AND y={literal(y)} THEN {policy.costs[c][y]!r}::DOUBLE' for c in task.classes for y in task.classes)+' ELSE 0.::DOUBLE END'
            rcost='CASE '+ ' '.join(f'WHEN y={literal(y)} THEN {policy.costs["abstained"][y]!r}::DOUBLE' for y in task.classes)+' ELSE 0.::DOUBLE END'
        g=f'pol{len(e.measurements)}'
        e.con.execute(f'CREATE TABLE {g} AS SELECT ({score})*{direction} score,count(*) n,count(*) FILTER(WHERE outcome_valid) ln,count(*) FILTER(WHERE outcome_valid AND {positive}) pos,sum(CASE WHEN outcome_valid THEN {loss} ELSE 0 END) loss,count(*) FILTER(WHERE outcome_valid AND {bad}) bad,sum(CASE WHEN outcome_valid THEN {acost} ELSE 0 END) acost,sum(CASE WHEN outcome_valid THEN {rcost} ELSE 0 END) rcost FROM {table} WHERE {valid} GROUP BY 1')
        columns=('n','ln','pos','loss','bad','acost','rcost')
        e.con.execute(f'CREATE TABLE {g}p AS SELECT score,'+','.join(f'sum({c}) OVER(ORDER BY score DESC) {c}' for c in columns)+f' FROM {g}')
        totals=e.con.execute('SELECT '+','.join(f'coalesce(sum({c}),0)' for c in columns)+f' FROM {g}').fetchone();alln,alll,allp,allloss,allbad,allacost,allrcost=totals
        cuts=list(policy.thresholds)
        if not cuts:
            if policy.kind in {'probability_threshold','confidence_abstention'}:cuts=[i/100 for i in range(101)]
            else:
                ng=e.con.execute(f'SELECT count(*) FROM {g}').fetchone()[0];stride=max(1,math.ceil(ng/max(1,min(config.max_thresholds,config.curve_points)-2)))
                cuts=[s*direction for s, in e.con.execute(f'SELECT score FROM (SELECT score,row_number() OVER(ORDER BY score) i FROM {g}) WHERE (i-1)%?=0 OR i=? ORDER BY score',[stride,ng]).fetchall()]
        e.con.execute(f'CREATE TABLE {g}cuts(idx INTEGER,threshold DOUBLE)')
        if cuts:e.con.executemany(f'INSERT INTO {g}cuts VALUES (?,?)',[(i,v*direction) for i,v in enumerate(cuts)])
        selected=e.con.execute(f'SELECT c.idx,'+','.join('p.'+c for c in columns)+f' FROM {g}cuts c ASOF LEFT JOIN {g}p p ON c.threshold<=p.score ORDER BY c.idx').fetchall()
        selected=[(-1,0,0,0,0,0,0,0),*selected,(-2,*totals)]
        points=[];sensitive=[]
        for idx,n,ln,pos,loss_sum,bad_sum,accept_cost,reject_cost in selected:
            n,ln,pos,loss_sum,bad_sum,accept_cost,reject_cost=(v or 0 for v in (n,ln,pos,loss_sum,bad_sum,accept_cost,reject_cost));sensitive.extend((n,alln-n,ln,n-ln))
            point={'state':'none' if idx==-1 else 'all' if idx==-2 else 'finite','threshold':None if idx<0 else cuts[idx],'accepted':int(n),'accepted_labeled':int(ln),'coverage':n/alln if alln else None,'observed_label_coverage':ln/n if n else None,'labeled_population_coverage':ln/alll if alll else None}
            if binary:
                tp=pos;fp=ln-pos;fn=allp-pos;tn=alll-allp-fp;sensitive.extend((tp,fp,fn,tn))
                point.update(tp=int(tp),fp=int(fp),fn=int(fn),tn=int(tn),accuracy=(tp+tn)/alll if alll else None,precision=tp/ln if ln else None,recall=tp/allp if allp else None)
                if policy.costs:
                    neg=next(c for c in task.classes if c!=task.positive_class)
                    try:point['empirical_cost']=(tp*policy.costs[task.positive_class][task.positive_class]+fp*policy.costs[task.positive_class][neg]+fn*policy.costs[neg][task.positive_class]+tn*policy.costs[neg][neg])/alll if alll else None
                    except KeyError:point['cost_unavailable']='incomplete_cost_table'
            else:
                point['accepted_mae' if task.kind=='regression' else 'accepted_error_rate']=loss_sum/ln if ln else None
                if task.kind=='regression' and task.material_error is not None:
                    point['accepted_material_error_rate']=bad_sum/ln if ln else None;sensitive.extend((bad_sum,ln-bad_sum))
                if policy.costs:
                    if cost_ready:point['empirical_cost']=(accept_cost+allrcost-reject_cost)/alll if alll else None
                    else:point['cost_unavailable']='complete_categorical_accept_and_abstain_costs_required'
                if task.kind!='regression':sensitive.extend((loss_sum,ln-loss_sum))
            points.append(point)
        e.add(r,scope,family,'policy_curve',n=alln,data={'kind':policy.kind,'points':points,'selection_population':'valid selector and applicable candidate outputs','decision_provenance':'simulated','threshold_units':'probability' if policy.kind.startswith('probability') or policy.kind=='confidence_abstention' else 'native_selector_units','direction':'higher' if direction==1 else 'lower','ties':'whole_equal_score_groups','unchanged_outcome_assumption':bool(policy.costs)},counts=sensitive,basis='simulated',where=valid,reason=None if alln else 'no_selector_population')
        e.con.execute(f'DROP TABLE {g}');e.con.execute(f'DROP TABLE {g}p');e.con.execute(f'DROP TABLE {g}cuts');e.s.work.check('policy replay')


def compare(e,*,predicates=None):
    spec=e.s.spec
    if not spec.comparison:return None
    a=next(r for r in spec.runs if r.id==spec.comparison.left);b=next(r for r in spec.runs if r.id==spec.comparison.right)
    ta,tb=e.s.run_tables[a.id],e.s.run_tables[b.id];reasons=[]
    if not e.s.outcomes:reasons.append('authoritative_outcomes_required')
    for r in (a,b):
        facts=e.s.run_facts[r.id]
        if facts['duplicate_keys'] or facts['missing_keys']:reasons.append('ambiguous_prediction_identities')
        if facts['inline_conflicts'] and r.inline_outcome_role=='agreement_assertion':reasons.append('conflicting_asserted_outcome_copy')
    if e.s.outcome_facts['duplicate_rows']:reasons.append('ambiguous_outcome_identities')
    if (a.horizon or spec.task.horizon)!=(b.horizon or spec.task.horizon):reasons.append('different_horizons')
    # Group before joining so duplicate identities cannot create Cartesian evidence.
    n,missing_left,missing_right=e.con.execute(f'SELECT count(*) FILTER(WHERE a.event_key IS NOT NULL AND b.event_key IS NOT NULL),count(*) FILTER(WHERE a.event_key IS NULL),count(*) FILTER(WHERE b.event_key IS NULL) FROM (SELECT DISTINCT event_key FROM {ta} WHERE event_key IS NOT NULL) a FULL JOIN (SELECT DISTINCT event_key FROM {tb} WHERE event_key IS NOT NULL) b USING(event_key)').fetchone()
    timing=e.con.execute(f'SELECT count(*) FILTER(WHERE a.prediction_tick IS NOT NULL AND b.prediction_tick IS NOT NULL AND a.prediction_tick<>b.prediction_tick),count(*) FILTER(WHERE a.prediction_tick IS NULL OR b.prediction_tick IS NULL) FROM (SELECT * FROM {ta} QUALIFY count(*) OVER(PARTITION BY event_key)=1) a JOIN (SELECT * FROM {tb} QUALIFY count(*) OVER(PARTITION BY event_key)=1) b USING(event_key)').fetchone()
    if timing[0]:reasons.append('different_information_cutoffs')
    ledger={'left':a.id,'right':b.id,'shared':n,'left_only':missing_right,'right_only':missing_left,'different_cutoffs':timing[0],'unknown_cutoffs':timing[1],'blocked_reasons':sorted(set(reasons)),'timing_qualification':'unestablished' if timing[1] else 'known_equal_on_shared_events','outcome_snapshot':e.s.outcome_facts.get('snapshot_digest'),'scope':'matched supplied predictions; no isolated causal model or generalization claim'}
    if reasons:return ledger
    conditions={'decision':"a.outcome_valid AND b.outcome_valid AND a.decision IS NOT NULL AND b.decision IS NOT NULL AND a.state IN ('issued','hypothetical') AND b.state IN ('issued','hypothetical')",'probability':'a.outcome_valid AND b.outcome_valid AND a.prob_valid AND b.prob_valid','ranking':'a.outcome_valid AND b.outcome_valid AND a.rank_score IS NOT NULL AND b.rank_score IS NOT NULL','point':"a.outcome_valid AND b.outcome_valid AND a.point IS NOT NULL AND b.point IS NOT NULL AND a.state IN ('issued','hypothetical') AND b.state IN ('issued','hypothetical')"}
    if predicates:
        for kind,predicate in predicates.items():
            if kind in conditions:conditions[kind]+=' AND ('+predicate+')'
    metrics=['point'] if spec.task.kind=='regression' else ['decision','probability']
    if spec.task.kind=='binary_classification':metrics.append('ranking')
    interval_pairs={}
    for ai,iv in enumerate(a.intervals):
        for bi,jv in enumerate(b.intervals):
            if iv.id!=jv.id:continue
            if (iv.coverage,iv.meaning,iv.central)!=(jv.coverage,jv.meaning,jv.central):
                e.checks.append({'id':'paired_interval:'+iv.id,'applicability':'blocked','execution':'not_run','reason':'interval_meaning_nominal_coverage_or_centrality_differs'});continue
            kind='interval:'+iv.id;interval_pairs[kind]=(ai,bi,iv,jv);metrics.append(kind)
            conditions[kind]=f'a.outcome_valid AND b.outcome_valid AND a.w{ai} IS NOT NULL AND b.w{bi} IS NOT NULL'
    populations={}
    scopes=[('paired',None)]
    for i,c in enumerate(spec.cohorts):
        if any(e.s.run_facts[r.id]['context_conflicts'].get(c.column) for r in (a,b)):continue
        groups=e.con.execute(f'SELECT DISTINCT g{i} FROM {ta} ORDER BY 1').fetchall()
        scopes.extend((f'cohort_{i}/{g}/paired',(i,g)) for g, in groups)
    for scope,group in scopes:
        for kind in metrics:
            condition=conditions[kind]
            if group:condition+=f' AND a.g{group[0]}={literal(group[1])} AND b.g{group[0]}={literal(group[1])}'
            for r,t,other in ((a,ta,tb),(b,tb,ta)):
                # Alias correspondence remains fixed even when selecting the right side.
                dest=f'paired{len(e.measurements)}';alias='a' if r.id==a.id else 'b'
                projection=f'{alias}.*'
                effective_run=r
                if kind in interval_pairs:
                    ai,bi,iv,jv=interval_pairs[kind];index=ai if alias=='a' else bi;effective_run=replace(r,intervals=(iv if alias=='a' else jv,))
                    excluded=','.join(f'{c}{i}' for i in range(len(r.intervals)) for c in ('l','u','w'))
                    projection+=f' EXCLUDE ({excluded}),'+','.join(f'{alias}.{c}{index} {c}0' for c in ('l','u','w'))
                e.con.execute(f'CREATE TABLE {dest} AS SELECT {projection} FROM {ta} a JOIN {tb} b USING(event_key) WHERE {condition}')
                e.bind_relation(dest,{'kind':'paired_projection','left':e.relations[ta],'right':e.relations[tb],'selected_run':r.id,'intersection':kind,'eligibility':condition,'interval_projection':effective_run.to_dict()['intervals'] if kind in interval_pairs else None})
                before=len(e.measurements)
                if kind=='point':regression(e,r,dest,'true',scope)
                elif kind=='decision':classification(e,r,dest,'true',scope)
                elif kind=='ranking':ranking(e,r,dest,'true',scope)
                elif kind in interval_pairs:intervals(e,effective_run,dest,'true',scope)
                else:calibration(e,r,dest,'true',scope)
                current=e.measurements[before:]
                populations[(scope,kind,r.id)]={m['metric']:m for m in current if m['value_state'] in {'finite','positive_infinity','negative_infinity'} and m['metric']!='reliability_diagram'}
                e.con.execute(f'DROP TABLE {dest}')
            joined=f'{ta} a JOIN {tb} b USING(event_key)'
            e.bind_relation(joined,{'kind':'paired_base','left':e.relations[ta],'right':e.relations[tb],'intersection':kind})
            e.use_relation(joined)
            base_n=e.con.execute(f'SELECT count(*) FROM {joined} WHERE {condition}').fetchone()[0]
            left,right=populations[(scope,kind,a.id)],populations[(scope,kind,b.id)]
            for metric in sorted(left.keys()&right.keys()):
                l,rr=left[metric],right[metric]
                lv=l['value'] if l['value_state']=='finite' else math.inf if l['value_state']=='positive_infinity' else -math.inf
                rv=rr['value'] if rr['value_state']=='finite' else math.inf if rr['value_state']=='positive_infinity' else -math.inf
                difference=rv-lv;undefined=math.isnan(difference)
                delta=e.add(b,scope,'comparison',metric+'_right_minus_left',None if undefined else difference,base_n,denominator_kind='paired_base_support',data={'left_run':a.id,'right_run':b.id,'left':l['value'],'right':rr['value'],'left_value_state':l['value_state'],'right_value_state':rr['value_state'],'metric_population':kind,'left_population_id':l['population_id'],'right_population_id':rr['population_id'],'left_denominator':l['denominator'],'right_denominator':rr['denominator'],'interpretation':'Both metrics use the common paired base; class/high-confidence conditionals may select different subsets. No automatic winner.'},reason='indeterminate_infinite_difference' if undefined else None,where=condition)
                delta['disclosure_group']=l['disclosure_group']
            if kind=='decision':
                cells=e.con.execute(f'SELECT a.decision=a.y,b.decision=b.y,count(*) FROM {ta} a JOIN {tb} b USING(event_key) WHERE {condition} GROUP BY 1,2').fetchall()
                m=e.add(b,scope,'comparison','error_transitions',n=sum(x[2] for x in cells),data={'cells':[{'left_correct':l,'right_correct':rr,'count':nn} for l,rr,nn in cells]},counts=[x[2] for x in cells],where=condition)
                if scope=='paired':e.paired_witnesses(m,a,b,ta,tb,condition+' AND (a.decision=a.y)<>(b.decision=b.y)')
            if kind=='point':
                view=f'(SELECT abs(a.point-a.y_num) le,abs(b.point-b.y_num) re FROM {ta} a JOIN {tb} b USING(event_key) WHERE {condition})'
                nn,unsafe,improved,worse,same=e.con.execute(f'SELECT count(*),count(*) FILTER(WHERE NOT isfinite(le) OR NOT isfinite(re)),count(*) FILTER(WHERE re<le),count(*) FILTER(WHERE re>le),count(*) FILTER(WHERE re=le) FROM {view}').fetchone()
                m=e.add(b,scope,'comparison','absolute_error_transitions',n=nn,data={} if unsafe else {'right_smaller_error':improved,'right_larger_error':worse,'equal_error':same},counts=() if unsafe else (improved,worse,same),where=condition,reason='unrepresentable_residual' if unsafe else None)
                if scope=='paired' and not unsafe:e.paired_witnesses(m,a,b,ta,tb,condition+' AND abs(a.point-a.y_num)<>abs(b.point-b.y_num)')
    return ledger
