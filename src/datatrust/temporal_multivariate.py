"""Declared contemporaneous pairs and window-qualified annotation coverage."""
import math
from datatrust.distribution_effects import numeric_geometry
from datatrust.temporal_normalization import normalize_clock


def annotation_windows(e,r,wins):
    annotations=getattr(r,'annotations',None)
    if not annotations:return
    clock=normalize_clock(e.work,r,r.temporal.clock);rows=[]
    for descriptor in annotations['targets']:
        states=descriptor['table']
        for window,n,observed,expected,supplied,invalid,unknown in e.query(f'''SELECT w.window_id,count(a._row),count(a._row) FILTER(WHERE observed),count(a._row) FILTER(WHERE expectation='expected'),count(a._row) FILTER(WHERE expectation='expected' AND observed),count(a._row) FILTER(WHERE invalid),count(a._row) FILTER(WHERE expectation='unknown') FROM {wins} w LEFT JOIN {clock} c ON c.state='valid' AND c.t>=w.start_t AND c.t<w.end_t LEFT JOIN {states} a USING(_row) GROUP BY w.window_id ORDER BY w.window_id''').fetchall():
            rows.append({'target':descriptor['target'],'window_id':window,'rows':n,'observed':observed,'expected':expected,'supplied_expected':supplied,'invalid':invalid,'unknown_expectation':unknown,'expected_coverage':supplied/expected if expected else None})
    e.add('annotation_windows',r.id,{'windows':rows,'meaning':'Original M3 observation and expectation states; outcome maturity is a separate declaration.'})


def multivariate(e,r,table,wins):
    """Exact observation matching; duplicate/conflicting cells never create pair products."""
    declarations=e.config.behavior.multivariate_pairs
    selected={m.name:m for m in getattr(r,'behavior_measurements',())}
    candidates=[p for p in declarations if p[0] in selected and p[1] in selected]
    details=[];unsearched=[];con=e.work.con
    for index,(a,b) in enumerate(candidates):
        escaped=lambda name:"'"+name.replace("'","''")+"'"
        n=con.execute(f'SELECT count(*) FROM {table} WHERE measurement IN (?,?)',[a,b]).fetchone()[0]
        if not e.reserve(n*2,con.execute(f'SELECT count(*) FROM {wins}').fetchone()[0]):unsearched.append([a,b]);continue
        narrow=table+'_pair_'+str(index)
        # One semantic state at an observation may retain identical multiplicity.
        con.execute(f'''CREATE TABLE {narrow} AS WITH x AS(SELECT entity,observation_key,t,window_id,measurement,min(value) AS value,min(num) num,min(value_state) state,count(DISTINCT list_value(value,value_state)) states,count(*) multiplicity FROM {table} WHERE entity_ok AND observation_key_ok AND measurement IN (?,?) GROUP BY entity,observation_key,t,window_id,measurement),
            a AS(SELECT * FROM x WHERE measurement={escaped(a)}),b AS(SELECT * FROM x WHERE measurement={escaped(b)})
            SELECT coalesce(a.window_id,b.window_id) window_id,a.value av,b.value bv,a.num x,b.num y,a.state ast,b.state bst,a.states ac,b.states bc,a.multiplicity am,b.multiplicity bm FROM a FULL OUTER JOIN b USING(entity,observation_key,t,window_id)''',[a,b])
        for window,n,matched,absent,ambiguous in con.execute(f'''SELECT w.window_id,count(p.window_id),count(p.window_id) FILTER(WHERE ac=1 AND bc=1 AND ast='valid' AND bst='valid'),count(p.window_id) FILTER(WHERE ac IS NULL OR bc IS NULL),count(p.window_id) FILTER(WHERE ac>1 OR bc>1) FROM {wins} w LEFT JOIN {narrow} p USING(window_id) GROUP BY w.window_id ORDER BY w.window_id''').fetchall():
            item={'measurements':[a,b],'window_id':window,'observation_identities':n,'matched_valid':matched,'absent_measurement_identities':absent,'ambiguous_identities':ambiguous,'matched_coverage':matched/n if n else None,'below_support_descriptive_only':matched<e.config.behavior.min_support,'pearson':None,'units':[selected[a].unit,selected[b].unit]}
            pred=f"window_id={window} AND ac=1 AND bc=1 AND ast='valid' AND bst='valid'"
            if selected[a].representation=='quantitative' and selected[b].representation=='quantitative' and matched:
                unsafe=con.execute(f'SELECT count(*) FROM {narrow} WHERE {pred} AND (x IS NULL OR y IS NULL)').fetchone()[0]
                block='unsafe_numeric_geometry' if unsafe else numeric_geometry(con,narrow,'x',pred) or numeric_geometry(con,narrow,'y',pred)
                if block:item['block']=block
                else:
                    lo,hi,ly,hy=con.execute(f'SELECT min(x),max(x),min(y),max(y) FROM {narrow} WHERE {pred}').fetchone()
                    sx=max(abs(lo),abs(hi)) or 1.;sy=max(abs(ly),abs(hy)) or 1.
                    if lo==hi or ly==hy:item['block']='constant_or_sparse_matched_population'
                    elif matched>=2:
                        corr=con.execute(f'SELECT corr(x/?-?,y/?-?) FROM {narrow} WHERE {pred}',[sx,lo/sx,sy,ly/sy]).fetchone()[0]
                        item['pearson']=corr if corr is not None and math.isfinite(corr) else None
            else:item['block']='quantitative_geometry_not_declared'
            details.append(item)
        con.execute(f'DROP TABLE {narrow}')
    if candidates or declarations:
        e.add('multivariate',r.id,{'declared_pairs':[list(x) for x in candidates],'window_pairs':details,'unsearched_pairs':unsearched,'meaning':'Contemporaneous matched observations only. Window composition, temporal dependence and sparse support qualify associations; no cross-lag, causality, independent-row inference or defect threshold.'})
