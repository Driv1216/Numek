"""Disk-backed seven-partition candidate search, with fair cross-split work ledgers."""
from collections import deque,OrderedDict
import itertools
import json

WIDTHS=(10,9,9,9,9,9,9)
SHIFTS=(0,10,19,28,37,46,55)


def parts(value): return [(value>>s)&((1<<w)-1) for s,w in zip(SHIFTS,WIDTHS)]


def build_index(store):
    con=store.con; seed=store.config.seed
    con.execute("CREATE TABLE signatures AS SELECT row_number() OVER (ORDER BY raster)::BIGINT aid,raster,min(path) path,min(phash)::UBIGINT signature FROM (SELECT path,json_extract_string(payload,'$.oriented_sha256') raster,json_extract(payload,'$.phash')::UBIGINT phash FROM assets WHERE json_extract(payload,'$.visual_eligible')::BOOLEAN) GROUP BY raster")
    con.execute("CREATE TABLE signature_membership AS SELECT DISTINCT s.aid,o.sid,o.split FROM signatures s JOIN assets a ON json_extract_string(a.payload,'$.oriented_sha256')=s.raster JOIN occurrences o ON o.path=a.path")
    queries=[]
    for band,(shift,width) in enumerate(zip(SHIFTS,WIDTHS)):
        queries.append(f'SELECT {band} band,(signature >> {shift}) & {(1<<width)-1} bucket,aid,signature FROM signatures')
    con.execute('CREATE TABLE partition_entries AS '+' UNION ALL '.join(queries))
    con.execute(f'CREATE TABLE partition_ranked AS SELECT *,row_number() OVER (PARTITION BY band,bucket ORDER BY hash(aid,{seed}),aid) rank,count(*) OVER (PARTITION BY band,bucket) population FROM partition_entries')
    con.execute('CREATE TABLE postings AS SELECT * FROM partition_ranked WHERE rank<=?',[store.config.limits.bucket_entries])
    con.execute('CREATE INDEX posting_key ON postings(band,bucket)')
    con.execute('CREATE TABLE image_candidates(left_aid BIGINT,right_aid BIGINT,distance INTEGER, PRIMARY KEY(left_aid,right_aid))')
    return con.execute('SELECT count(*) FROM signatures').fetchone()[0]


def investigate(e,store):
    if not store.config.near_duplicates:
        e.add('near_duplicates',{'reason':'disabled'},applicability='not_applicable',coverage={'examined':0}); return
    import numpy as np
    total=build_index(store); con=store.con; limits=store.config.limits
    lookup=np.array([i.bit_count() for i in range(256)],dtype=np.uint8)
    declared=[(r.left,r.right) for r in store.spec.split_requirements]
    splits=[r[0] for r in con.execute('SELECT DISTINCT split FROM occurrences ORDER BY split').fetchall()]
    pairs=list(dict.fromkeys(declared+list(itertools.combinations(splits,2))))
    ledgers=[]; jobs=[]
    con.execute("CREATE TEMP TABLE search_references(pair_id INTEGER,aid BIGINT)")
    def population(value):
        return con.execute('SELECT DISTINCT s.aid,s.signature FROM signatures s JOIN signature_membership m USING(aid) WHERE m.sid=? OR m.split=? ORDER BY hash(s.aid,?),s.aid',[value,value,store.config.seed]).fetchall()
    for left,right in pairs:
        a,b=population(left),population(right)
        if len(a)>len(b): left,right,a,b=right,left,b,a
        con.execute('CREATE TEMP TABLE IF NOT EXISTS search_references(pair_id INTEGER,aid BIGINT)')
        pid=len(jobs)
        if b: con.executemany('INSERT INTO search_references VALUES (?,?)',[(pid,int(x[0])) for x in b])
        ledger={'left':e.opaque('split',left),'right':e.opaque('split',right),'query_population':len(a),'reference_population':len(b),'queries_started':0,'queries_completed':0,'posting_visits':0,'hamming_comparisons':0,'qualifying_emissions':0,'posting_saturation_visits':0,'scope':'cross_split'}
        ledgers.append(ledger); jobs.append({'id':pid,'queries':a,'ledger':ledger,'done':set()})
    remaining_visits=limits.posting_visits; remaining_comparisons=limits.hamming_comparisons; candidate_count=0
    exhausted=None
    posting_cache=OrderedDict(); cache_bytes=0; rows_loaded=0
    def search(jobs,comparison_budget,visit_budget):
        nonlocal remaining_visits,remaining_comparisons,candidate_count,exhausted,cache_bytes,rows_loaded
        used=visits=0; offset=0; take=1
        active=list(jobs)
        while active and used<comparison_budget and visits<visit_budget and candidate_count<limits.candidate_pairs:
            max_queries=max((len(j['queries']) for j in active),default=0)
            for ordinal in range(max_queries):
                for job in active:
                    if ordinal>=len(job['queries']) or ordinal in job['done']: continue
                    aid,sig=job['queries'][ordinal]; buckets=parts(int(sig)); all_finished=True; ledger=job['ledger']
                    if offset==0: ledger['queries_started']+=1
                    for band,bucket in enumerate(buckets):
                        quota=min(take,visit_budget-visits,remaining_visits)
                        if quota<=0: exhausted='posting_visit_budget'; return used,visits
                        cache_key=(job['id'],band,bucket)
                        cached=posting_cache.get(cache_key)
                        if cached is None:
                            fetch_limit=min(limits.bucket_entries,remaining_visits,visit_budget-visits)
                            fetched=con.execute('SELECT p.aid,p.signature,p.population FROM postings p JOIN search_references r ON p.aid=r.aid WHERE r.pair_id=? AND p.band=? AND p.bucket=? ORDER BY p.rank LIMIT ?',[job['id'],band,bucket,fetch_limit]).fetchall()
                            cached=np.array(fetched,dtype=np.uint64).reshape(-1,3)
                            remaining_visits-=len(fetched); visits+=len(fetched); ledger['posting_visits']+=len(fetched); rows_loaded+=len(fetched)
                            if fetch_limit<limits.bucket_entries and len(fetched)==fetch_limit:
                                exhausted='posting_visit_budget'; return used,visits
                            while posting_cache and cache_bytes+cached.nbytes>32*1024**2:
                                _,old=posting_cache.popitem(last=False); cache_bytes-=old.nbytes
                            posting_cache[cache_key]=cached; cache_bytes+=cached.nbytes
                        else: posting_cache.move_to_end(cache_key)
                        quota=min(quota,remaining_visits,visit_budget-visits)
                        if quota<=0: exhausted='posting_visit_budget'; return used,visits
                        rows=cached[offset:offset+quota]
                        visits+=len(rows); remaining_visits-=len(rows); ledger['posting_visits']+=len(rows)
                        if len(rows)==quota: all_finished=False
                        if len(rows):
                            ledger['posting_saturation_visits']+=int(sum(r[2]>limits.bucket_entries for r in rows))
                            ids=np.array([r[0] for r in rows],dtype=np.int64); signatures=np.array([r[1] for r in rows],dtype=np.uint64)
                            keep=ids!=aid
                            # A pair is verified in its first shared partition only.
                            for previous in range(band): keep &= ((signatures>>SHIFTS[previous])&((1<<WIDTHS[previous])-1))!=buckets[previous]
                            ids=ids[keep]; signatures=signatures[keep]
                            allowance=min(comparison_budget-used,remaining_comparisons)
                            if len(ids)>allowance:
                                ids=ids[:allowance]; signatures=signatures[:allowance]; exhausted='hamming_work_budget'
                            if len(ids):
                                x=(signatures^np.uint64(sig)).view(np.uint8).reshape(-1,8); distances=lookup[x].sum(axis=1)
                                used+=len(ids); remaining_comparisons-=len(ids); ledger['hamming_comparisons']+=len(ids)
                                good=distances<=store.config.hamming_radius
                                for other,distance in zip(ids[good],distances[good]):
                                    if candidate_count>=limits.candidate_pairs: exhausted='qualifying_pair_budget'; break
                                    a,b=sorted((int(aid),int(other)))
                                    inserted=con.execute('INSERT INTO image_candidates VALUES (?,?,?) ON CONFLICT DO NOTHING RETURNING left_aid',[a,b,int(distance)]).fetchone()
                                    candidate_count+=bool(inserted); ledger['qualifying_emissions']+=1
                            if exhausted: return used,visits
                    if all_finished: job['done'].add(ordinal); ledger['queries_completed']+=1
                    if used>=comparison_budget or visits>=visit_budget: return used,visits
                if ordinal%128==0: store.work.check('perceptual cross-split candidates')
            active=[j for j in active if len(j['done'])<len(j['queries'])]
            offset+=take; take=min(128,take*4)
        return used,visits
    cross_budget=max(1,int(limits.hamming_comparisons*.8)); cross_visits=max(1,int(limits.posting_visits*.8))
    used,visits=search(jobs,cross_budget,cross_visits)
    cross_finished=all(len(j['done'])==len(j['queries']) for j in jobs)
    # Within-population queries use remaining reserved work; exact rasters are collapsed.
    within=[]
    for split in splits:
        a=population(split); pid=len(jobs)+len(within)
        if a: con.executemany('INSERT INTO search_references VALUES (?,?)',[(pid,int(x[0])) for x in a])
        ledger={'split':e.opaque('split',split),'query_population':len(a),'reference_population':len(a),'queries_started':0,'queries_completed':0,'posting_visits':0,'hamming_comparisons':0,'qualifying_emissions':0,'posting_saturation_visits':0,'scope':'within_split'}
        ledgers.append(ledger); within.append({'id':pid,'queries':a,'ledger':ledger,'done':set()})
    cross_stop=exhausted
    if remaining_visits>0 and remaining_comparisons>0 and candidate_count<limits.candidate_pairs:
        exhausted=None
        search(within,remaining_comparisons if cross_finished else max(0,limits.hamming_comparisons-cross_budget),remaining_visits if cross_finished else max(0,limits.posting_visits-cross_visits))
    examples=[]
    for a,b,d in con.execute('SELECT * FROM image_candidates ORDER BY distance,left_aid,right_aid LIMIT ?',[limits.details]).fetchall():
        oids=[]
        for aid in (a,b):
            oid=con.execute("SELECT min(o.oid) FROM signatures s JOIN assets a ON json_extract_string(a.payload,'$.oriented_sha256')=s.raster JOIN occurrences o ON o.path=a.path WHERE s.aid=?",[aid]).fetchone()[0]
            oids.append(oid)
        examples.append({'left':store.witness(oids[0]),'right':store.witness(oids[1]),'hamming_distance':d})
    saturated=con.execute('SELECT count(*) FROM (SELECT DISTINCT band,bucket FROM partition_ranked WHERE population>?)',[limits.bucket_entries]).fetchone()[0]
    e.add('near_duplicates',{'qualifying_raster_pairs':candidate_count,'examples':examples,'radius':store.config.hamming_radius,'representation':'DCT64 opaque RGB preview; seven disjoint partitions','approximate_groups_are_equivalence_classes':False},meaning='investigation_candidate',violations=candidate_count,scope='bounded',coverage={'indexed_rasters':total,'partition_entries':total*7,'saturated_buckets':saturated,'posting_visits':limits.posting_visits-remaining_visits,'posting_rows_loaded':rows_loaded,'posting_cache_limit_bytes':32*1024**2,'hamming_comparisons':limits.hamming_comparisons-remaining_comparisons,'pair_populations':ledgers,'cross_split_queries_complete':cross_finished,'cross_split_stop_reason':cross_stop,'stop_reason':exhausted or ('examined_scope_completed' if all(l['queries_started']==l['queries_completed'] for l in ledgers) else 'reserved_work_bound'),'detail_omissions':max(0,candidate_count-len(examples)),'absence_claim':'examined scope only; capped postings do not establish global absence'})
