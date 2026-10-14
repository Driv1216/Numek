"""Reproducible bounded lexical, MinHash and verified passage investigations."""
from collections import Counter, defaultdict, deque
import hashlib
import itertools
import json
from pathlib import Path

from datatrust.text_normalization import graphemes
from datatrust.scalable import fail

PROFILES=((32,4),(16,8),(16,6),(20,7),(26,8),(32,8))
HASH_VERSION='blake2b64_independent_keys_v1'


def shingles(text):
    gs=graphemes(text)
    return {''.join(gs[i:i+5]) for i in range(max(0,len(gs)-4))}


def signature(values,bands,rows,seed=0):
    keys=[hashlib.sha256(seed.to_bytes(8,'big')+i.to_bytes(4,'big')).digest()[:16] for i in range(bands*rows)]
    minima=[2**64-1]*len(keys)
    for value in sorted(values):
        raw=value.encode('utf8')
        for i,key in enumerate(keys):
            h=int.from_bytes(hashlib.blake2b(raw,key=key,digest_size=8).digest(),'big')
            if h<minima[i]:minima[i]=h
    return tuple(minima)


def round_pairs(members,cap):
    """Diagonal enumeration touches both bucket ends before exhausting large buckets."""
    members=sorted(members);n=len(members);used=0
    for distance in range(1,n):
        for i in range(n-distance):
            if used>=cap:return
            used+=1;yield members[i],members[i+distance]


def cross_pairs(left,right):
    # Diagonals touch both sides without materializing a Cartesian product.
    for diagonal in range(len(left)+len(right)-1):
        for i in range(max(0,diagonal-len(right)+1),min(len(left),diagonal+1)):
            a,b=left[i],right[diagonal-i]
            if a!=b:yield min(a,b),max(a,b)


def candidate_pairs(signatures,bands,rows,bucket_cap,total_cap,seed=0,pair_groups=()):
    buckets=defaultdict(list)
    for i,sig in enumerate(signatures):
        for b in range(bands):buckets[(b,sig[b*rows:(b+1)*rows])].append(i)
    buckets={k:v for k,v in buckets.items() if len(v)>1}
    order=sorted(buckets,key=lambda k:hashlib.sha256((str(seed)+repr(k)).encode()).digest())
    def stream(members):
        emitted=0;seen=set();member_set=set(members)
        for left,right in pair_groups:
            a=sorted(member_set.intersection(left));b=sorted(member_set.intersection(right))
            for pair in cross_pairs(a,b):
                if pair in seen:continue
                if emitted>=bucket_cap:return
                seen.add(pair);emitted+=1;yield pair
        for pair in round_pairs(members,bucket_cap):
            if pair in seen:continue
            if emitted>=bucket_cap:return
            emitted+=1;yield pair
    streams=[iter(stream(buckets[k])) for k in order]
    seen=set();emissions=0;potential=sum(len(v)*(len(v)-1)//2 for v in buckets.values())
    if pair_groups:
        import heapq
        def tier(pair):
            a,b=pair
            return next((n for n,(left,right) in enumerate(pair_groups) if (a in left and b in right) or (b in left and a in right)),len(pair_groups))
        heap=[];turn=0
        for i,s in enumerate(streams):
            pair=next(s,None)
            if pair is not None:heapq.heappush(heap,(tier(pair),turn,i,pair));turn+=1
        while heap and len(seen)<total_cap:
            _,_,i,pair=heapq.heappop(heap);emissions+=1;seen.add(pair)
            pair=next(streams[i],None)
            if pair is not None:heapq.heappush(heap,(tier(pair),turn,i,pair));turn+=1
        return sorted(seen),{'candidate_emissions':emissions,'unique_candidates':len(seen),'potential_bucket_emissions':potential,'bucket_count':len(buckets),'bucket_emission_cap':bucket_cap,'omitted_bucket_emissions':max(0,potential-emissions),'unique_unseen_pairs':'unknown','candidate_search':'approximate'}
    active=list(range(len(streams)))
    while active and len(seen)<total_cap:
        remaining=[]
        for i in active:
            try:pair=next(streams[i])
            except StopIteration:continue
            emissions+=1;seen.add(pair);remaining.append(i)
            if len(seen)>=total_cap:break
        active=remaining
    return sorted(seen),{'candidate_emissions':emissions,'unique_candidates':len(seen),'potential_bucket_emissions':potential,'bucket_count':len(buckets),'bucket_emission_cap':bucket_cap,'omitted_bucket_emissions':max(0,potential-emissions),'unique_unseen_pairs':'unknown','candidate_search':'approximate'}


def shipping_profile():
    path=Path(__file__).with_name('text_search_profile.json')
    value=json.loads(path.read_text())
    if value['hash_version']!=HASH_VERSION:raise ValueError('Search calibration does not match hash implementation.')
    return value


SELECTION_VERSION='comparison_side_reserved_split_stratified_v2'


def comparison_tiers(spec):
    evaluation={x.id for x in spec.inputs if x.role in {'evaluation','test','validation'}}
    training={x.id for x in spec.inputs if x.role in {'train','documents','chunks'}}
    requested={tuple(sorted(pair)) for pair in spec.evaluation.comparisons}
    explicit=sorted(pair for pair in requested if set(pair)&evaluation)
    implicit=sorted({tuple(sorted((a,b))) for a in evaluation for b in training if a!=b}-requested)
    other=sorted(pair for pair in requested if not set(pair)&evaluation)
    return (explicit,implicit,other)


def select_population(e,store,table,budget,*,nonempty=False,length_limit=None):
    """Disk-backed strata queues; reserve missing sides atomically before allocation.

    Queue prefixes are bounded in Python. A single remaining unit may extend an
    already represented comparison, but cannot start a two-sided comparison.
    Sources with an unavailable side fall back to within-source investigation.
    """
    con=store.con;cfg=store.config
    # Internal table names and predicates are fixed by callers, never user SQL.
    assert table in {'lexical_selected','language_selected','embedding_selected'}
    predicates=['chars>0'] if nonempty else ['TRUE'];parameters=[]
    if length_limit is not None:predicates.append('graphemes<=?');parameters.append(length_limit)
    predicate=' AND '.join(predicates);queue=table+'_queue'
    con.execute(f'''CREATE TABLE {queue} AS SELECT uid,sid,
        row_number() OVER(PARTITION BY sid ORDER BY stratum_rank,stratum_key,member_key,uid) source_rank
        FROM (SELECT *,row_number() OVER(PARTITION BY sid,split,field,kind,length_stratum
        ORDER BY member_key,uid) stratum_rank FROM lexical_catalog WHERE {predicate})
        ORDER BY sid,source_rank''',parameters)
    eligible=dict(con.execute(f'SELECT sid,count(*) FROM {queue} GROUP BY sid').fetchall())
    pools={};offsets=Counter();selected_counts=Counter();chosen=[];allocated=Counter();checked_at=0
    def check_selection(phase):
        nonlocal checked_at
        if len(chosen)-checked_at>=128 or len(chosen)==budget:
            store.work.check(phase);checked_at=len(chosen)
    def peek(sid):
        pool=pools.setdefault(sid,deque())
        if not pool and offsets[sid]<eligible.get(sid,0):
            rows=con.execute(f'SELECT uid FROM {queue} WHERE sid=? AND source_rank>? ORDER BY source_rank LIMIT 128',[sid,offsets[sid]]).fetchall()
            pool.extend(x[0] for x in rows);offsets[sid]+=len(rows)
        return pool[0] if pool else None
    def take(sid,tier,target):
        uid=peek(sid)
        if uid is None:return False
        pools[sid].popleft();selected_counts[sid]+=1
        chosen.append((uid,len(chosen),tier));allocated[(tier,target,sid)]+=1
        return True
    seeded=lambda value:hashlib.sha256((str(cfg.seed)+'\0'+json.dumps(value,ensure_ascii=True)).encode()).digest()
    tiers=[sorted(pairs,key=seeded) for pairs in comparison_tiers(store.spec)]
    for tier,pairs in enumerate(tiers):
        active=pairs
        while active and len(chosen)<budget:
            remaining=[];progress=False
            for pair in active:
                if len(chosen)>=budget:break
                if any(not eligible.get(sid) for sid in pair):continue
                missing=[sid for sid in pair if not selected_counts[sid]]
                if len(missing)>budget-len(chosen):continue
                # Establish both sides first, then advance source strata in rounds.
                sides=missing+[sid for sid in sorted(pair,key=lambda s:(selected_counts[s],seeded(s))) if sid not in missing]
                for sid in sides:
                    if len(chosen)<budget:progress=take(sid,tier,pair) or progress
                if any(peek(sid) is not None for sid in pair):remaining.append(pair)
            if not progress:break
            active=remaining;check_selection('text comparison-side selection')
    sources=sorted(eligible,key=seeded)
    while sources and len(chosen)<budget:
        remaining=[]
        for sid in sources:
            if len(chosen)>=budget:break
            if take(sid,3,(sid,)):remaining.append(sid)
        sources=remaining;check_selection('text within-source selection')
    selection=table+'_allocation'
    con.execute(f'CREATE TABLE {selection}(uid VARCHAR,selection_order BIGINT,allocation_tier INT)')
    if chosen:con.executemany(f'INSERT INTO {selection} VALUES (?,?,?)',chosen)
    con.execute(f'CREATE TABLE {table} AS SELECT c.*,a.selection_order,a.allocation_tier FROM lexical_catalog c JOIN {selection} a USING(uid)')
    con.execute(f'DROP TABLE {queue}');con.execute(f'DROP TABLE {selection}')
    store.work.check('text population selection completed')
    strata=con.execute(f'SELECT sid,field,kind,split,length_stratum,count(*),sum(graphemes),sum(bytes) FROM {table} GROUP BY ALL ORDER BY sid,field,kind,split,length_stratum').fetchall()
    comparisons=[]
    for tier,pairs in enumerate(tiers):
        for pair in pairs:
            sides=[selected_counts[sid] for sid in pair];available=[eligible.get(sid,0) for sid in pair]
            comparisons.append({'tier':tier,'sources':[e.sources[sid] for sid in pair],
                'eligible_side_populations':available,'selected_side_populations':sides,
                'units_allocated_in_this_comparison':[allocated[(tier,pair,sid)] for sid in pair],
                'status':'both_sides_represented' if all(sides) else 'unavailable_side' if not all(available) else 'budget_insufficient_for_both_sides'})
    applicable=con.execute('SELECT count(*) FROM lexical_catalog'+(' WHERE chars>0' if nonempty else '')).fetchone()[0]
    return {'framed_records':sum(x['records'] for x in store.counts.values()),'invalid_records':sum(x['invalid_records'] for x in store.counts.values()),
        'content_population':con.execute('SELECT count(*) FROM content').fetchone()[0],'valid_applicable_population':applicable,
        'eligible_population':sum(eligible.values()),'selected_population':len(chosen),'selection':SELECTION_VERSION,'seed':cfg.seed,
        'representation':store.selection_representation,'selected_graphemes':sum(x[6] or 0 for x in strata),'selected_bytes':sum(x[7] or 0 for x in strata),
        'selected_strata':[{'source':e.sources[s],'field':e.opaque('field',f),'kind':k,'split':e.opaque('split',split) if split is not None else None,'length_stratum':length,'units':n,'graphemes':g,'bytes':b} for s,f,k,split,length,n,g,b in strata],
        'comparison_allocations':comparisons,'allocation_tier_units':{str(tier):sum(v for (t,_,_),v in allocated.items() if t==tier) for tier in range(4)},
        'excluded_for_length':applicable-sum(eligible.values()),'excluded_for_unit_budget':sum(eligible.values())-len(chosen),
        'stop_reason':'unit_budget' if len(chosen)<sum(eligible.values()) else 'eligible_scope_completed','population_estimate':False}


def select(e,store):
    cfg=store.config;rep='nfc' if 'nfc' in cfg.representations else 'raw'
    store.selection_representation=rep
    store.con.execute('''CREATE TABLE lexical_catalog AS SELECT c.uid,c.sid,c.field,c.kind,c.role,c.split,c.state,c.chars,c.graphemes,c.bytes,p.representation,p.digest,
        CASE WHEN c.graphemes<=100 THEN '0-100' WHEN c.graphemes<=1000 THEN '101-1000' ELSE '1001+' END length_stratum,
        sha256(?||c.uid) member_key,sha256(?||to_json(struct_pack(sid:=c.sid,split:=c.split,field:=c.field,kind:=c.kind,length:=length_stratum))) stratum_key
        FROM content c JOIN representations p USING(uid) WHERE p.representation=? AND c.state IN ('present','empty','whitespace')''',[str(cfg.seed),str(cfg.seed),rep])
    ledger=select_population(e,store,'lexical_selected',cfg.limits.lexical_units,length_limit=cfg.limits.lexical_graphemes)
    if cfg.lexical_complete and ledger['selected_population']!=ledger['valid_applicable_population']:fail('Complete lexical scope does not fit the declared unit/length limits.','lexical_complete_limit')
    e.add('lexical_selection',ledger,scope='bounded',coverage=ledger)
    return ledger


def lexical(e,store,ledger):
    import regex
    from datatrust.distribution_effects import categorical_effect
    con=store.con;cfg=store.config;used=0;units=0;buffer=[];buffer_bytes=0
    con.execute('CREATE TABLE vocabulary(sid VARCHAR,token VARCHAR,n BIGINT)')
    def flush():
        nonlocal buffer_bytes
        if buffer:
            import pandas as pd
            con.register('_vocab',pd.DataFrame(buffer,columns=['sid','token','n']));con.execute('INSERT INTO vocabulary SELECT * FROM _vocab');con.unregister('_vocab');buffer.clear();buffer_bytes=0
    cursor=con.cursor().execute('SELECT s.uid,s.sid,p.text FROM lexical_selected s JOIN representations p ON s.uid=p.uid AND s.representation=p.representation ORDER BY s.selection_order')
    while batch:=cursor.fetchmany(128):
        for uid,sid,text in batch:
            words=regex.findall(r'\p{L}[\p{L}\p{M}]*|\p{N}+|[^\s]',text)
            if used+len(words)>cfg.limits.vocabulary_tokens:
                if cfg.lexical_complete:fail('Complete vocabulary work exceeds explicit budget.','lexical_complete_limit')
                continue
            used+=len(words);units+=1
            for token,n in Counter(words).items():buffer.append((sid,token,n));buffer_bytes+=len(token.encode())+32
            if buffer_bytes>=cfg.execution.batch_bytes:flush();store.work.check('vocabulary batch')
    flush()
    con.execute('CREATE TABLE vocabulary_counts AS SELECT sid,token,sum(n)::BIGINT n FROM vocabulary GROUP BY sid,token')
    distinct=con.execute('SELECT count(DISTINCT token) FROM vocabulary_counts').fetchone()[0]
    top=con.execute('SELECT token,sum(n) n FROM vocabulary_counts GROUP BY token ORDER BY n DESC,token LIMIT ?',[cfg.limits.details]).fetchall()
    coverage=ledger|{'examined_units':units,'token_occurrences':used,'stop_reason':'vocabulary_work_limit' if units<ledger['selected_population'] else 'selected_scope_completed','vocabulary_is_lower_bound':units<ledger['valid_applicable_population']}
    e.add('vocabulary',{'observed_distinct_tokens':distinct,'token_occurrences':used,'unit_count':units,'top_tokens':[{'reference':e.opaque('token',w),'occurrences':n} for w,n in top],'tokenization':'unicode_letters_numbers_punctuation_v1','language_independent_words_claimed':False},scope='bounded',coverage=coverage)
    for left,right in store.spec.evaluation.comparisons:
        # Materialize counts as categorical weights, avoiding expansion of tokens.
        n=con.execute('SELECT sum(n) FROM vocabulary_counts WHERE sid=?',[left]).fetchone()[0];m=con.execute('SELECT sum(n) FROM vocabulary_counts WHERE sid=?',[right]).fetchone()[0]
        if n and m:
            tv=con.execute('SELECT .5*sum(abs(coalesce(a.n,0)/?-coalesce(b.n,0)/?)) FROM (SELECT token,n FROM vocabulary_counts WHERE sid=?) a FULL JOIN (SELECT token,n FROM vocabulary_counts WHERE sid=?) b USING(token)',[n,m,left,right]).fetchone()[0]
            e.add('lexical_comparison',{'sources':[e.sources[left],e.sources[right]],'selected_token_total_variation':tv,'token_populations':[n,m],'population_estimate':False},meaning='contextual_observation',scope='bounded')


def near(e,store,ledger):
    cfg=store.config;profile=shipping_profile();b=profile['bands'];r=profile['rows'];cap=profile['bucket_cap']
    units=[];sets=[];signatures=[];position_work=0;signature_work=0;excluded=0;memberships=[]
    # Collapse exact content, retaining representatives; multiplicities are restored below.
    cursor=store.con.cursor().execute('SELECT min(s.uid),p.digest,p.text,count(*),list(DISTINCT s.sid) FROM lexical_selected s JOIN representations p ON s.uid=p.uid AND s.representation=p.representation GROUP BY p.digest,p.text ORDER BY min(s.selection_order),min(s.uid)')
    while batch:=cursor.fetchmany(64):
        for uid,digest,text,multiplicity,sources in batch:
            positions=max(0,len(graphemes(text))-4)
            if not positions:excluded+=1;continue
            values=shingles(text);cost=len(values)*b*r
            if position_work+positions>cfg.limits.shingle_positions or signature_work+cost>cfg.limits.signature_work:excluded+=1;continue
            position_work+=positions;signature_work+=cost
            units.append((uid,digest,text,multiplicity));memberships.append(sources);sets.append(values);signatures.append(signature(values,b,r,cfg.seed))
        store.work.check('MinHash signature batch')
    source_indices={x.id:{i for i,sids in enumerate(memberships) if x.id in sids} for x in store.spec.inputs}
    comparisons=[pair for tier in comparison_tiers(store.spec) for pair in tier]
    pair_groups=[(source_indices[a],source_indices[b]) for a,b in comparisons]
    def pair_priority(pair):
        i,j=pair
        return next((n for n,(a,b) in enumerate(pair_groups) if (i in a and j in b) or (j in a and i in b)),len(pair_groups))
    pair_cost=sum(len(s) for s in sets)*max(0,len(sets)-1)
    if len(sets)<=200 and pair_cost<=cfg.limits.verification_visits:
        pairs=list(itertools.combinations(range(len(sets)),2));stats={'candidate_search':'exhaustive_selected_unique_units','unique_candidates':len(pairs),'candidate_emissions':len(pairs),'omitted_bucket_emissions':0}
    else:pairs,stats=candidate_pairs(signatures,b,r,cap,cfg.limits.candidates,cfg.seed,pair_groups)
    pairs.sort(key=lambda pair:(pair_priority(pair),pair))
    visits=0;verified=0;accepted=0;false_candidates=0;details=[];omitted=0
    for i,j in pairs:
        cost=len(sets[i])+len(sets[j])
        if visits+cost>cfg.limits.verification_visits:omitted+=1;continue
        visits+=cost;verified+=1
        common=len(sets[i]&sets[j]);union=len(sets[i]|sets[j]);similarity=common/union
        if similarity>=cfg.near_threshold:
            accepted+=1
            if len(details)<cfg.limits.details:
                refs=[e.witness(units[k][0]) for k in (i,j)]
                provenance=[]
                for k in (i,j):
                    rows=store.con.execute('SELECT c.sid,c.split,count(*) n FROM representations p JOIN content c USING(uid) WHERE p.representation=? AND p.digest=? AND p.text=? GROUP BY c.sid,c.split ORDER BY n DESC,c.sid,c.split LIMIT ?',[ledger['representation'],units[k][1],units[k][2],cfg.limits.details]).fetchall()
                    total=store.con.execute('SELECT count(*) FROM representations WHERE representation=? AND digest=? AND text=?',[ledger['representation'],units[k][1],units[k][2]]).fetchone()[0]
                    provenance.append({'population_occurrences':total,'retained_source_split_counts':[{'source':e.sources[sid],'split':e.opaque('split',split),'occurrences':n} for sid,split,n in rows],'retained_counts_cover_population':sum(n for _,_,n in rows)==total})
                raw=[store.con.execute('SELECT text FROM content WHERE uid=?',[units[k][0]]).fetchone()[0] for k in (i,j)]
                difference=next((n for n,(a,c) in enumerate(zip(*raw)) if a!=c),min(map(len,raw)))
                context=[e.span_witness(units[k][0],max(0,difference-40),min(len(raw[n]),difference+120)) for n,k in enumerate((i,j))]
                shared=[e.span_witness(units[k][0],0,min(difference,160)) for k in (i,j)] if difference else []
                details.append({'references':[x for x in refs if x],'shared_literal_prefix_references':shared,'first_raw_difference_context_references':context,'raw_context_does_not_remap_normalized_similarity':True,'jaccard':similarity,'intersection':common,'union':union,'selected_occurrence_multiplicities':[units[i][3],units[j][3]],'population_occurrence_provenance':provenance,'template_interpretation_required':True})
        else:false_candidates+=1
    indexed_comparisons=[{'sources':[e.sources[a],e.sources[b]],'indexed_unique_side_units':[len(source_indices[a]),len(source_indices[b])],'both_sides_indexed':bool(source_indices[a] and source_indices[b])} for a,b in comparisons]
    coverage=ledger|stats|{'pair_selection':'requested_evaluation_then_evaluation_training_then_other_requested_then_remaining_v1','indexed_comparison_sides':indexed_comparisons,'indexed_unique_units':len(units),'excluded_unique_units':excluded,'shingle_positions':position_work,'signature_hash_evaluations':signature_work,'verified_pairs':verified,'unverified_candidates':omitted,'verification_visits':visits,'candidate_recall_on_this_corpus':'unknown' if stats['candidate_search'].startswith('approximate') else 'complete_over_indexed_units','global_absence_claim':False,'profile':profile}
    e.add('near_duplicates',{'qualifying_pairs':accepted,'subthreshold_candidates':false_candidates,'threshold':cfg.near_threshold,'details':details,'detail_omissions':max(0,accepted-len(details)),'not_transitive':True,'containment_recall_claimed':False},meaning='heuristic_candidate',violations=accepted,scope='bounded',coverage=coverage)


def fingerprints(text,minimum):
    from collections import deque
    gs=graphemes(text);n=len(gs)-4
    if len(gs)<minimum:return gs,[]
    hashes=[int.from_bytes(hashlib.blake2b(''.join(gs[i:i+5]).encode(),digest_size=8).digest(),'big') for i in range(n)]
    w=max(1,minimum-5+1);out=[];previous=None;queue=deque()
    for i,h in enumerate(hashes):
        while queue and hashes[queue[-1]]>=h:queue.pop()
        queue.append(i)
        while queue and queue[0]<=i-w:queue.popleft()
        if i>=w-1 and queue[0]!=previous:
            previous=queue[0];out.append((hashes[previous],previous))
    return gs,out


def passages(e,store,ledger):
    cfg=store.config;index=defaultdict(list);units=[];work=0;excluded=0;pairs=0;matches=0;details=[]
    cursor=store.con.cursor().execute('SELECT s.uid,c.text FROM lexical_selected s JOIN content c USING(uid) ORDER BY s.selection_order')
    for batch in iter(lambda:cursor.fetchmany(64),[]):
        for uid,text in batch:
            cost=max(0,len(graphemes(text))-4)
            if work+cost>cfg.limits.shingle_positions:excluded+=1;continue
            work+=cost;gs,prints=fingerprints(text,cfg.minimum_passage);unit=len(units);units.append((uid,gs,text))
            for h,pos in prints:index[h].append((unit,pos))
        store.work.check('passage fingerprint batch')
    visits=0;seen=set();candidate_emissions=0;potential=0
    potential=sum(len(m)*(len(m)-1)//2 for m in index.values());stopped=False
    for h in sorted(index):
        members=index[h]
        for i,j in round_pairs(list(range(len(members))),shipping_profile()['bucket_cap']):
            a,p=members[i];b,q=members[j]
            if a==b:continue
            key=(min(a,b),max(a,b),p,q)
            if key in seen:continue
            if pairs>=cfg.limits.candidates or visits+cfg.minimum_passage>cfg.limits.verification_visits:stopped=True;break
            seen.add(key);pairs+=1;candidate_emissions+=1
            left=units[a][1];right=units[b][1];start=0
            while start<min(p,q) and visits<cfg.limits.verification_visits and left[p-start-1]==right[q-start-1]:start+=1;visits+=1
            length=0
            while p+length<len(left) and q+length<len(right) and visits<cfg.limits.verification_visits:
                visits+=1
                if left[p+length]!=right[q+length]:break
                length+=1
            if start+length>=cfg.minimum_passage:
                matches+=1
                if len(details)<cfg.limits.details:
                    refs=[]
                    for k,begin,end in ((a,p-start,p+length),(b,q-start,q+length)):
                        cp_start=sum(len(g) for g in units[k][1][:begin]);cp_end=sum(len(g) for g in units[k][1][:end])
                        refs.append({'reference':e.span_witness(units[k][0],cp_start,cp_end),'source_grapheme_span':[begin,end],'source_codepoint_span':[cp_start,cp_end]})
                    details.append({'matches':refs,'graphemes':start+length})
        if stopped:break
    e.add('passages',{'verified_passage_matches':matches,'minimum_graphemes':cfg.minimum_passage,'details':details,'detail_omissions':max(0,matches-len(details)),'template_interpretation_required':True},meaning='heuristic_candidate',violations=matches,scope='bounded',coverage=ledger|{'representation':'raw','indexed_units':len(units),'excluded_units':excluded,'fingerprint_work':work,'candidate_emissions':candidate_emissions,'potential_bucket_emissions':potential,'verified_candidates':pairs,'verification_visits':visits,'stop_reason':'work_budget' if stopped else 'examined_fingerprints_completed','candidate_recall_on_this_corpus':'unknown','global_absence_claim':False})


def investigate(e,store):
    ledger=select(e,store)
    repetition(e,store,ledger)
    if store.config.vocabulary:lexical(e,store,ledger)
    if store.config.near_duplicates:near(e,store,ledger)
    if store.config.passages:passages(e,store,ledger)
    return ledger


def repetition(e,store,ledger):
    """Literal nonblank-line repetition, without declaring content low quality."""
    used=0;examined=0;repeated=0;details=[];limit=store.config.limits.shingle_positions
    cursor=store.con.cursor().execute('SELECT s.uid,c.text,c.graphemes FROM lexical_selected s JOIN content c USING(uid) ORDER BY s.selection_order')
    for batch in iter(lambda:cursor.fetchmany(64),[]):
        for uid,text,size in batch:
            if used+size>limit:continue
            used+=size;examined+=1
            lines=Counter(line for line in text.splitlines() if line.strip())
            extra=sum(n-1 for n in lines.values());repeated+=bool(extra)
            if extra and len(details)<store.config.limits.details:
                line=next(line for line,n in lines.items() if n>1);start=text.find(line)
                details.append({'reference':e.span_witness(uid,start,start+len(line)),'excess_repeated_nonblank_lines':extra})
        store.work.check('literal line repetition batch')
    e.add('repetition',{'units_with_repeated_nonblank_lines':repeated,'details':details,'quality_violation_claimed':False},meaning='contextual_observation',scope='bounded',coverage=ledger|{'examined_units':examined,'grapheme_visits':used,'stop_reason':'work_budget' if examined<ledger['selected_population'] else 'selected_scope_completed'})
