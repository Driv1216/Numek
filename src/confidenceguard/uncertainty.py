"""Quantile, empirical distribution and conformal-output evidence on shared populations."""
import json
import math
import hashlib
from decimal import Decimal
import numpy as np
from .sources import rows
from .analytics import literal
from .conformal import read_value


def pinball(y,q,tau):
    residual=y-q
    return max(tau*residual,(tau-1)*residual)


def interval_score(y,lo,hi,alpha):
    return hi-lo+2/alpha*max(lo-y,0)+2/alpha*max(y-hi,0)


def empirical_crps(samples,y):
    x=np.sort(np.asarray(samples,dtype=float)); n=len(x)
    if not n or not np.all(np.isfinite(x)) or not math.isfinite(y):return math.nan
    # Equivalent sorted pinball identity sums nonnegative terms instead of
    # subtracting two large expectations; finite samples need no density model.
    scale=max(float(np.max(np.abs(x))),abs(y),1.)
    z=x/scale; yy=y/scale
    terms=(z-yy)*((z>yy).astype(float)-(np.arange(1,n+1)-.5)/n)
    return float(np.sum(terms))*(2/n)*scale


def build_losses(store,run,table,*,root,uncertainty_table=None):
    """Per-event contributions stay in DuckDB, not completed JSON or browser code."""
    rep=store.representations.get(root)
    dest='extra_'+str(list(store.run_tables).index(run.id))
    store.con.execute(f'CREATE TABLE {dest}(ordinal BIGINT,event_key VARCHAR,metric VARCHAR,value DOUBLE,defined BOOLEAN,eligible BOOLEAN)')
    metadata={};pending=[]
    def add(ordinal,event,metric,value,eligible=True,allow_infinity=False):
        defined=value is not None and (math.isfinite(value) or allow_infinity and value==math.inf)
        pending.append((ordinal,event,metric,value if defined else None,defined,eligible))
        if len(pending)>=512:
            store.con.executemany(f'INSERT INTO {dest} VALUES (?,?,?,?,?,?)',pending);pending.clear();store.work.check('uncertainty loss contributions')
    generated_levels=set()
    if uncertainty_table:generated_levels={v[0] for v in store.con.execute(f'SELECT DISTINCT coverage FROM {uncertainty_table}').fetchall()}
    supplied={}
    for i,interval in enumerate(run.intervals):
        nominal=str(Decimal(str(interval.coverage)).normalize())
        if interval.meaning!='prediction' or nominal in generated_levels:continue
        supplied.setdefault(nominal,[]).append((i,interval))
    for nominal,options in supplied.items():
        if len(options)!=1:continue # Ambiguous same-level supplied intervals are not auto-matched.
        i,interval=options[0]
        for ordinal,event,y,lo,hi,width,eligible in rows(store.con,f'SELECT ordinal,event_key,y_num,l{i},u{i},w{i},outcome_valid FROM {table}',batch=512):
            valid=bool(eligible) and width is not None
            metrics={'interval_coverage@'+nominal:float(lo<=y<=hi) if valid else None,
                     'interval_efficiency@'+nominal:width,
                     'interval_empty_rate@'+nominal:0.,'interval_uninformative_rate@'+nominal:0.}
            for metric,value in metrics.items():
                metadata[metric]={'nominal':nominal,'definition':metric.split('@')[0],'supplied_interval':interval.id,'central':interval.central,'availability_conditioned':True}
                add(ordinal,event,metric,value,valid)
    if rep and rep.quantiles:
        levels=[Decimal(q.level) for q in rep.quantiles]; pairs=[]
        for i,t in enumerate(levels):
            if t<Decimal('.5') and 1-t in levels:pairs.append((i,levels.index(1-t),float(2*t)))
        median=levels.index(Decimal('.5')) if Decimal('.5') in levels else None
        for ordinal,event,y,quantiles,eligible in rows(store.con,f'SELECT ordinal,event_key,y_num,quantiles,outcome_valid FROM {table}',batch=512):
            valid=quantiles is not None and bool(eligible)
            for i,t in enumerate(levels):
                metric='pinball@'+str(t);metadata[metric]={'level':str(t),'definition':'pinball_quantile_loss'}
                add(ordinal,event,metric,pinball(y,quantiles[i],float(t)) if valid else None,valid)
                for strict in (False,True):
                    label=('quantile_lt@' if strict else 'quantile_le@')+str(t)
                    metadata[label]={'level':str(t),'ties':'strict' if strict else 'inclusive','interpretation':'Discrete quantile calibration brackets the requested level.'}
                    add(ordinal,event,label,float(y<quantiles[i] if strict else y<=quantiles[i]) if valid else None,valid)
            if median is not None and pairs:
                value=None
                if valid:
                    value=(.5*abs(y-quantiles[median])+math.fsum(a/2*interval_score(y,quantiles[i],quantiles[j],a) for i,j,a in pairs))/(len(pairs)+.5)
                metadata['wis']={'definition':'standard_weighted_interval_score','central_pairs':len(pairs),'median_required':True}
                add(ordinal,event,'wis',value,valid)
            for i,j,a in pairs:
                label='central_interval_score@'+str(Decimal(1)-Decimal(str(a)))
                metadata[label]={'alpha':a,'definition':'central_interval_score'}
                add(ordinal,event,label,interval_score(y,quantiles[i],quantiles[j],a) if valid else None,valid)
    if rep and rep.samples:
        source=store.input_facts[root]['sample_table']
        histogram_metric='sample_rank_histogram' if rep.samples.meaning=='iid_monte_carlo' else 'sample_pit_histogram'
        # Compute sample CRPS entirely in disk reductions. No event-sized sample list.
        store.con.execute(f'''CREATE TABLE sample_crps AS
            WITH ranked AS (SELECT event_key,value,row_number() OVER(PARTITION BY event_key ORDER BY value,draw) i,
                 count(*) OVER(PARTITION BY event_key) n,max(abs(value)) OVER(PARTITION BY event_key) sample_scale FROM {source}),
            contributions AS (SELECT s.*,r.y_num,r.ordinal,r.outcome_valid,r.sample_valid,
                 greatest(coalesce(sample_scale,1),abs(coalesce(r.y_num,0)),1) scale
                 FROM ranked s JOIN {table} r USING(event_key))
            SELECT ordinal,event_key,any_value(outcome_valid AND sample_valid) eligible,
                 (2./max(n))*sum((value/scale-y_num/scale)*((CASE WHEN value>y_num THEN 1. ELSE 0. END)-(i-.5)/n))*max(scale) crps,
                 avg(CASE WHEN value<y_num THEN 1. ELSE 0. END) cdf_left,
                 avg(CASE WHEN value<=y_num THEN 1. ELSE 0. END) cdf_right,max(n) draws
            FROM contributions GROUP BY ordinal,event_key''')
        for ordinal,event,eligible,value,left,right,draws in rows(store.con,'SELECT * FROM sample_crps',batch=512):
            for metric,v in [('empirical_crps',value),('sample_cdf_left',left),('sample_cdf_right',right)]:add(ordinal,event,metric,v,bool(eligible))
            token=json.dumps([store.extension.roles.seed,store.extension.roles.namespace,event],ensure_ascii=True,separators=(',',':')).encode()
            u=int(hashlib.sha256(token).hexdigest()[:13],16)/16**13
            if rep.samples.meaning=='iid_monte_carlo':
                pit=(left*draws+u*((right-left)*draws+1))/(draws+1)
            else:pit=left+u*(right-left)
            add(ordinal,event,histogram_metric,pit,bool(eligible))
        store.con.execute('DROP TABLE sample_crps')
        metadata.update(empirical_crps={'definition':'exact_empirical_distribution_crps','not_unbiased_latent_distribution_crps':True},
                        sample_cdf_left={'sample_meaning':rep.samples.meaning,'uniform_pit_not_automatically_established':True},
                        sample_cdf_right={'sample_meaning':rep.samples.meaning,'uniform_pit_not_automatically_established':True})
        metadata[histogram_metric]={'histogram':True,'sample_meaning':rep.samples.meaning,'randomization':'sha256_namespace_seed_event_v1',
                          'uniform_interpretation_requires':'Conditional IID predictive draws and exchangeable outcome' if rep.samples.meaning=='iid_monte_carlo' else 'The empirical discrete predictive distribution equals the outcome distribution',
                          'finite_samples_do_not_establish_continuous_distribution_calibration':True}
    if uncertainty_table:
        for ordinal,event,coverage,raw,y,yn,eligible,input_valid in rows(store.con,f'SELECT u.ordinal,u.event_key,u.coverage,u.output,r.y,r.y_num,r.outcome_valid,r.cg_input_valid FROM {uncertainty_table} u JOIN {table} r USING(ordinal,event_key)',batch=512):
            output=json.loads(raw); planned=bool(eligible) and bool(input_valid);valid=output['state']!='unavailable' and planned
            prefix='set_' if store.spec.task.classes else 'interval_'
            if store.spec.task.classes:
                included=store.spec.task.classes.index(y) in output.get('members',[]) if valid else None
                width=output.get('size')
            else:
                included=False if output['state']=='empty' else True if output['state']=='unbounded' else read_value(output['lower'])<=yn<=read_value(output['upper']) if valid else None
                width=read_value(output['width']) if output.get('width') else None
            for metric,value in [(prefix+'coverage@'+coverage,float(included) if valid else None),
                                 (prefix+'efficiency@'+coverage,width),
                                 (prefix+'empty_rate@'+coverage,float(output['state']=='empty')),
                                 (prefix+'uninformative_rate@'+coverage,float(output['state'] in {'full','unbounded'}))]:
                metadata[metric]={'nominal':coverage,'definition':metric.split('@')[0],'availability_conditioned':True}
                add(ordinal,event,metric,value if valid else None,planned,allow_infinity='efficiency' in metric)
            metric=prefix+'output_availability@'+coverage
            metadata[metric]={'nominal':coverage,'definition':'output_availability','requires_outcome':False}
            add(ordinal,event,metric,float(output['state']!='unavailable'),True)
    if pending:store.con.executemany(f'INSERT INTO {dest} VALUES (?,?,?,?,?,?)',pending)
    return dest,metadata


def evaluate_losses(e,run,table,loss_table,metadata,where,scope):
    for metric,detail in metadata.items():
        dest='extra_view_'+str(len(e.measurements))
        e.con.execute(f'CREATE TEMP TABLE {dest} AS SELECT r.*,x.value extra_value,x.defined extra_defined FROM {table} r JOIN {loss_table} x USING(ordinal,event_key) WHERE x.metric=? AND x.eligible AND ({where})',[metric])
        e.bind_relation(dest,{'kind':'cg2_extra_metric','input':e.relations[table],'metric':metric,'eligibility':where})
        e.use_relation(dest)
        n,bad,inf,value,median,p95,positives=e.con.execute(f"SELECT count(*),count(*) FILTER(WHERE NOT extra_defined),count(*) FILTER(WHERE extra_value='inf'::DOUBLE),avg(extra_value),median(extra_value),quantile_cont(extra_value,.95),count(*) FILTER(WHERE extra_value=1) FROM {dest}").fetchone()
        data={**detail,'undefined_records':bad}
        if 'coverage@' in metric and detail.get('nominal'):data['empirical_minus_nominal']=value-float(detail['nominal']) if value is not None and not bad else None
        counts=()
        if detail.get('histogram'):
            histogram=e.con.execute(f'SELECT least(9,floor(extra_value*10))::INTEGER,count(*) FROM {dest} WHERE extra_defined GROUP BY 1 ORDER BY 1').fetchall()
            data['bins']=[{'bin':i,'count':count} for i,count in histogram];counts=tuple(v[1] for v in histogram);value=None
        if any(s in metric for s in ('coverage','_rate','quantile_')):counts=(positives,n-positives)
        if 'efficiency' in metric:data.update(median=median,p95=p95,unbounded_records=inf)
        m=e.add(run,scope,'uncertainty' if 'nominal' in detail else 'distribution_quality',metric,value if not bad else None,n,
                data=data,counts=counts,reason='undefined_on_planned_metric_population' if bad else 'zero_denominator' if not n else None)
        e.con.execute(f'DROP TABLE {dest}')
    e.use_relation(table)


def deeper_calibration(e,run,table,where,scope,edges):
    if not run.probabilities:return
    task=e.s.spec.task; valid=f'({where}) AND outcome_valid AND prob_valid';n=e.con.execute(f'SELECT count(*) FROM {table} WHERE {valid}').fetchone()[0]
    if not n:return
    e.use_relation(table)
    targets=[]
    if task.kind=='binary_classification':targets.append(('event',task.classes.index(task.positive_class),f'y={literal(task.positive_class)}'))
    else:targets.extend(('class:'+c,i,f'y={literal(c)}') for i,c in enumerate(task.classes))
    for label,i,event in targets:
        bins=[];sensitive=[];ece=0.
        for j,(lo,hi) in enumerate(zip(edges,edges[1:])):
            pred=f'{valid} AND probs[{i+1}]>={lo!r} AND probs[{i+1}]'+('<=' if j==len(edges)-2 else '<')+repr(hi)
            count,prob,observed=e.con.execute(f'SELECT count(*),avg(probs[{i+1}]),avg(CASE WHEN {event} THEN 1. ELSE 0. END) FROM {table} WHERE {pred}').fetchone()
            positives=round(count*observed) if count else 0;sensitive.extend((positives,count-positives))
            bins.append({'bin':j,'lower':lo,'upper':hi,'count':count,'mean_probability':prob,'observed_frequency':observed})
            if count:ece+=count/n*abs(prob-observed)
        e.add(run,scope,'calibration_diagnostics','frozen_bin_ece',ece,n,data={'target':label,'edges':edges,'bins':bins,'selection_objective':False},counts=sensitive,where=valid)
    # Evaluation-only diagnostic logistic fit; never serialized as a reusable calibrator.
    if task.kind=='binary_classification' and scope=='overall':
        i=task.classes.index(task.positive_class)+1; pred=f'{valid} AND probs[{i}]>0 AND probs[{i}]<1'
        support,positive=e.con.execute(f'SELECT count(*),count(*) FILTER(WHERE y={literal(task.positive_class)}) FROM {table} WHERE {pred}').fetchone()
        reason=None;params=None
        if support and 0<positive<support:
            try:
                from scipy.optimize import minimize
                def objective(theta):
                    total=0.;gradient=np.zeros(2)
                    for p,y in rows(e.con,f'SELECT probs[{i}],y FROM {table} WHERE {pred}',batch=512):
                        z=math.log(p)-math.log1p(-p); eta=theta[0]+theta[1]*z; label=float(y==task.positive_class)
                        total+=float(np.logaddexp(0,eta)-label*eta)/support
                        q=math.exp(-float(np.logaddexp(0,-eta)));gradient+=(q-label)*np.array([1,z])/support
                    e.s.work.check('evaluation calibration slope diagnostic')
                    return total,gradient
                fit=minimize(objective,[0.,1.],jac=True,method='BFGS')
                if fit.success and np.all(np.isfinite(fit.x)):params=fit.x.tolist()
                else:reason='diagnostic_nonconvergence'
            except ImportError:reason='statistics_unavailable'
        else:reason='insufficient_interior_class_support'
        e.add(run,scope,'calibration_diagnostics','calibration_intercept',params[0] if params else None,support,data={'endpoint_exclusions':n-support,'diagnostic_only':True},reason=reason,where=pred)
        e.add(run,scope,'calibration_diagnostics','calibration_slope',params[1] if params else None,support,data={'endpoint_exclusions':n-support,'diagnostic_only':True},reason=reason,where=pred)
