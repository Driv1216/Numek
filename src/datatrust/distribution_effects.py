"""Empirical effect mathematics, independent of M4/M5 interpretation."""
import math


def numeric_effect(con,left,value_left,where_left,right,value_right,where_right,n_left,n_right,*,constant_zero=False):
    sql=f'''WITH frequencies AS(SELECT {value_left} datum,count(*) n,0::BIGINT m FROM {left} WHERE {where_left} GROUP BY {value_left} UNION ALL SELECT {value_right},0::BIGINT,count(*) FROM {right} WHERE {where_right} GROUP BY {value_right}),combined AS(SELECT datum,sum(n) n,sum(m) m FROM frequencies GROUP BY datum),cdf AS(SELECT datum,sum(n) OVER(ORDER BY datum ROWS UNBOUNDED PRECEDING)/? fa,sum(m) OVER(ORDER BY datum ROWS UNBOUNDED PRECEDING)/? fb,lead(datum) OVER(ORDER BY datum) next_value,n+m pooled FROM combined) SELECT max(abs(fa-fb)),sum(abs(fa-fb)*(CAST(next_value AS DOUBLE)-CAST(datum AS DOUBLE))),count(*) FILTER(WHERE pooled>1) FROM cdf'''
    lo,hi=con.execute(f'SELECT min(v),max(v) FROM (SELECT {value_left} v FROM {left} WHERE {where_left} UNION ALL SELECT {value_right} FROM {right} WHERE {where_right})').fetchone()
    scale=max(abs(float(lo)),abs(float(hi))) or 1.
    sql=sql.replace('sum(abs(fa-fb)*(CAST(next_value AS DOUBLE)-CAST(datum AS DOUBLE)))',f'sum(abs(fa-fb)*(CASE WHEN sign(next_value)=sign(datum) THEN (CAST(next_value AS DOUBLE)-CAST(datum AS DOUBLE))/{scale!r} ELSE next_value/{scale!r}-datum/{scale!r} END))')
    distance,scaled,ties=con.execute(sql,[n_left,n_right]).fetchone();w1=scaled*scale if scaled is not None else 0. if constant_zero else None
    return distance,w1,ties


def categorical_effect(con,left,value_left,where_left,right,value_right,where_right,n_left,n_right):
    sql=f'''WITH f AS(SELECT {value_left} datum,count(*) n,0::BIGINT m FROM {left} WHERE {where_left} GROUP BY {value_left} UNION ALL SELECT {value_right},0::BIGINT,count(*) FROM {right} WHERE {where_right} GROUP BY {value_right}),u AS(SELECT datum,sum(n) n,sum(m) m FROM f GROUP BY datum) SELECT .5*sum(abs(n/?-m/?)),count(*),sum(m) FILTER(WHERE n=0),sum(n) FILTER(WHERE m=0) FROM u'''
    tv,vocab,new,gone=con.execute(sql,[n_left,n_right]).fetchone()
    return {'total_variation':tv,'union_vocabulary':vocab,'new_category_mass':int(new or 0)/n_right,'disappearing_category_mass':int(gone or 0)/n_left}


def numeric_geometry(con,table,column,predicate):
    n,lo,hi=con.execute(f'SELECT count({column}),min({column}),max({column}) FROM {table} WHERE {predicate}').fetchone()
    if not n:return 'empty_finite_population'
    if lo!=hi and float(hi)-float(lo)<=128*max(math.ulp(float(lo)),math.ulp(float(hi))):return 'unsafe_floating_resolution'
    return None
