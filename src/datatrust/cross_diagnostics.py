"""Relationship populations and bounded, answer-independent reconciliation."""
from collections import Counter
from datetime import datetime
from decimal import Decimal, InvalidOperation, localcontext
import json
import regex
import unicodedataplus as unicode

from datatrust.cross_sources import key,value,decode_record
from datatrust.cross_private_base import digest
from datatrust.temporal_normalization import parse_clock
from datatrust.scalable import fail


def stream(con,query,params=()):
    cur=con.cursor();cur.execute(query,params)
    try:
        while rows:=cur.fetchmany(128):
            yield from rows
    finally: cur.close()


def relationships(store):
    evidence=[]
    for rel in store.spec.relationships:
        examples=[]
        def retain(reason,rows,selectors):
            for group in rows:
                if len(examples)>=store.config.limits.details: break
                refs=[store.witness(rid,sel) for rid in group for sel in selectors[:store.config.limits.witnesses]]
                examples.append({'reason':reason,'evidence_refs':refs,'key_component_omissions':max(0,len(selectors)-store.config.limits.witnesses)})
        for side,sid,selectors in [('left',rel.left_source,rel.left_keys),('right',rel.right_source,rel.right_keys)]:
            batch=[]
            for rid,payload in stream(store.con,'SELECT rid,payload FROM records WHERE sid=? AND state!=?',(sid,'invalid')):
                record=decode_record(payload);batch.append((rel.id,side,rid,key(record,selectors,rel.key_representation),key(record,selectors)))
                if len(batch)>=256: store.insert('bindings',batch);batch=[];store.work.check('identity projections')
            if batch: store.insert('bindings',batch)
            bad=store.con.execute('SELECT rid FROM bindings WHERE rel=? AND side=? AND k IS NULL ORDER BY rid LIMIT ?',[rel.id,side,store.config.limits.witnesses]).fetchall()
            retain(side+'_invalid_key',bad,selectors)
            for label,condition in [('normalization_collision','count(DISTINCT rawk)>1'),('duplicate_key','count(*)>1')]:
                groups=store.con.execute(f'SELECT k FROM bindings WHERE rel=? AND side=? AND k IS NOT NULL GROUP BY k HAVING {condition} ORDER BY k LIMIT ?',[rel.id,side,store.config.limits.witnesses]).fetchall()
                for k, in groups:
                    order='rawk,rid' if label=='normalization_collision' else 'rid'
                    # One member of each distinct raw identity makes a collision inspectable.
                    query='SELECT min(rid) FROM bindings WHERE rel=? AND side=? AND k=? GROUP BY rawk ORDER BY rawk LIMIT 2' if label=='normalization_collision' else f'SELECT rid FROM bindings WHERE rel=? AND side=? AND k=? ORDER BY {order} LIMIT 2'
                    retain(side+'_'+label,[[x[0] for x in store.con.execute(query,[rel.id,side,k]).fetchall()]],selectors)
        collisions=store.con.execute('SELECT count(*) FROM (SELECT side,k FROM bindings WHERE rel=? AND k IS NOT NULL GROUP BY side,k HAVING count(DISTINCT rawk)>1)',[rel.id]).fetchone()[0]
        # Normalization collisions block equality, rather than silently merging identities.
        store.con.execute('UPDATE bindings SET k=NULL WHERE rel=? AND (side,k) IN (SELECT side,k FROM bindings WHERE rel=? AND k IS NOT NULL GROUP BY side,k HAVING count(DISTINCT rawk)>1)',[rel.id,rel.id])
        unique_left=rel.cardinality in {'one_to_one','one_to_many'} or bool(rel.association_source)
        unique_right=rel.cardinality in {'one_to_one','many_to_one'} or bool(rel.association_source)
        duplicate={};invalid={}
        for side,unique in [('left',unique_left),('right',unique_right)]:
            duplicate[side]=store.con.execute('SELECT count(*) FROM (SELECT k FROM bindings WHERE rel=? AND side=? AND k IS NOT NULL GROUP BY k HAVING count(*)>1)',[rel.id,side]).fetchone()[0]
            invalid[side]=store.con.execute('SELECT count(*) FROM bindings WHERE rel=? AND side=? AND k IS NULL',[rel.id,side]).fetchone()[0]
            if unique: store.con.execute('UPDATE bindings SET k=NULL WHERE rel=? AND side=? AND k IN (SELECT k FROM bindings WHERE rel=? AND side=? GROUP BY k HAVING count(*)>1)',[rel.id,side,rel.id,side])
        assoc_invalid=assoc_duplicates=0
        if rel.association_source:
            store.con.execute('CREATE OR REPLACE TEMP TABLE declared_pairs(lk VARCHAR,rk VARCHAR,rid VARCHAR)')
            association_selectors=(* (rel.association_left_keys or (rel.association_left,)),* (rel.association_right_keys or (rel.association_right,)))
            bad_examples=0
            for rid,payload in stream(store.con,'SELECT rid,payload FROM records WHERE sid=? AND state!=?',(rel.association_source,'invalid')):
                record=decode_record(payload);a=key(record,rel.association_left_keys or (rel.association_left,),rel.key_representation);b=key(record,rel.association_right_keys or (rel.association_right,),rel.key_representation)
                if a is None or b is None:
                    assoc_invalid+=1
                    if bad_examples<store.config.limits.witnesses: retain('invalid_association_key',[(rid,)],association_selectors);bad_examples+=1
                    continue
                store.con.execute('INSERT INTO declared_pairs VALUES (?,?,?)',[a,b,rid])
            assoc_duplicates=store.con.execute('SELECT count(*)-count(DISTINCT (lk,rk)) FROM declared_pairs').fetchone()[0]
            assoc_invalid+=store.con.execute("SELECT count(*) FROM declared_pairs p WHERE NOT EXISTS(SELECT 1 FROM bindings WHERE rel=? AND side='left' AND k=p.lk) OR NOT EXISTS(SELECT 1 FROM bindings WHERE rel=? AND side='right' AND k=p.rk)",[rel.id,rel.id]).fetchone()[0]
            retain('association_endpoint_unresolved',store.con.execute("SELECT rid FROM declared_pairs p WHERE NOT EXISTS(SELECT 1 FROM bindings WHERE rel=? AND side='left' AND k=p.lk) OR NOT EXISTS(SELECT 1 FROM bindings WHERE rel=? AND side='right' AND k=p.rk) ORDER BY rid LIMIT ?",[rel.id,rel.id,store.config.limits.witnesses]).fetchall(),association_selectors)
            for a,b in store.con.execute('SELECT lk,rk FROM declared_pairs GROUP BY lk,rk HAVING count(*)>1 ORDER BY lk,rk LIMIT ?',[store.config.limits.witnesses]).fetchall():
                retain('duplicate_association_row',[[x[0] for x in store.con.execute('SELECT rid FROM declared_pairs WHERE lk=? AND rk=? ORDER BY rid LIMIT 2',[a,b]).fetchall()]],association_selectors)
            join="FROM bindings l JOIN (SELECT DISTINCT lk,rk FROM declared_pairs) p ON p.lk=l.k JOIN bindings r ON r.k=p.rk WHERE l.rel=? AND r.rel=? AND l.side='left' AND r.side='right'"
        else: join="FROM bindings l JOIN bindings r ON l.k=r.k WHERE l.rel=? AND r.rel=? AND l.side='left' AND r.side='right' AND l.k IS NOT NULL"
        count=store.con.execute('SELECT count(*) '+join,[rel.id,rel.id]).fetchone()[0]
        current=store.con.execute('SELECT count(*) FROM edges').fetchone()[0]
        if count+current>store.config.limits.associations: fail('Declared association population exceeds admission.','association_limit')
        store.work.check('association materialization',count*160)
        store.con.execute('INSERT INTO edges SELECT ?,l.rid,r.rid '+join,[rel.id,rel.id,rel.id])
        missing={}
        for side,col in [('left','l'),('right','r')]:
            missing[side]=store.con.execute(f'SELECT count(*) FROM bindings b WHERE rel=? AND side=? AND NOT EXISTS(SELECT 1 FROM edges e WHERE e.rel=b.rel AND e.{col}=b.rid)',[rel.id,side]).fetchone()[0]
            if (side=='left' and rel.required=='required') or (side=='right' and rel.inverse_required):
                retain(side+'_required_endpoint_missing',store.con.execute(f'SELECT rid FROM bindings b WHERE rel=? AND side=? AND NOT EXISTS(SELECT 1 FROM edges e WHERE e.rel=b.rel AND e.{col}=b.rid) ORDER BY rid LIMIT ?',[rel.id,side,store.config.limits.witnesses]).fetchall(),rel.left_keys if side=='left' else rel.right_keys)
        evidence.append({'relationship':rel.id,'associations':count,'unmatched':missing,'invalid_keys':invalid,'duplicate_keys':duplicate,'normalization_collisions':collisions,'invalid_association_rows':assoc_invalid,'duplicate_association_rows':assoc_duplicates,'required_gap':missing['left'] if rel.required=='required' else 0,'inverse_gap':missing['right'] if rel.inverse_required else 0,'cardinality_violations':(duplicate['left'] if unique_left else 0)+(duplicate['right'] if unique_right else 0),'examples':examples})
    return evidence


def clock(record,spec):
    if not spec: return None
    v=value(record,spec.column)
    return parse_clock(v,spec,value(record,spec.timezone_column) if spec.timezone_column else None,value(record,spec.fold_column) if spec.fold_column else None)


def context(rel,left,right):
    reasons=[];unknown=[]
    for name,(a,b) in rel.context.items():
        x,y=value(left,a),value(right,b)
        if x is None or y is None or x=='' or y=='': unknown.append(name)
        elif type(x)!=type(y) or x!=y: reasons.append(name)
    cutoff=clock(left,rel.cutoff);availability=clock(right,rel.availability)
    if cutoff:
        if cutoff[1]!='valid' or availability[1]!='valid' or rel.cutoff.kind!=rel.availability.kind: unknown.append('availability_clock')
        elif availability[0]>cutoff[0]: reasons.append('available_after_cutoff')
        for spec,bound in ((rel.valid_from,'not_yet_valid'),(rel.valid_to,'expired')):
            if spec:
                t=clock(right,spec)
                if t[1]!='valid' or cutoff[1]!='valid' or spec.kind!=rel.cutoff.kind: unknown.append('validity_clock')
                elif (t[0]>cutoff[0] if bound=='not_yet_valid' else t[0]<=cutoff[0]): reasons.append(bound)
    return {'eligible':not reasons and not unknown,'excluded':reasons,'unknown':unknown,'availability':str(availability[0]) if availability and availability[1]=='valid' else None}


def relationship_contexts(store):
    results=[]
    for rel in store.spec.relationships:
        if not rel.context and not rel.cutoff: continue
        batch=[];excluded=Counter();unknown=Counter()
        query='SELECT e.l,e.r,l.payload,r.payload FROM edges e JOIN records l ON l.rid=e.l JOIN records r ON r.rid=e.r WHERE e.rel=?'
        for left,right,lp,rp in stream(store.con,query,(rel.id,)):
            ctx=context(rel,decode_record(lp),decode_record(rp));excluded.update(ctx['excluded']);unknown.update(ctx['unknown'])
            batch.append((rel.id,left,right,json.dumps(ctx),bool(ctx['excluded']),bool(ctx['unknown'])))
            if len(batch)>=256: store.insert('contexts',batch);batch=[];store.work.check('declared context populations')
        if batch: store.insert('contexts',batch)
        n,v,u,affected=store.con.execute('SELECT count(*),count(*) FILTER(WHERE excluded),count(*) FILTER(WHERE unresolved),count(DISTINCT l) FILTER(WHERE excluded OR unresolved) FROM contexts WHERE rel=?',[rel.id]).fetchone()
        results.append({'relationship':rel.id,'associations':n,'violated':v,'inconclusive':u,'affected_records':affected,'context_exclusions':dict(excluded),'unknown_context':dict(unknown)})
    store.con.execute('CREATE INDEX edge_lookup ON edges(rel,l)')
    store.con.execute('CREATE INDEX context_lookup ON contexts(rel,l)')
    return results


def transform(text,representation):
    if representation=='nfc': return unicode.normalize('NFC',text)
    if representation=='casefold': return text.casefold()
    if representation=='whitespace': return ' '.join(text.split())
    return text


def canonical(v,rule,*,evidence=False):
    if v is None or isinstance(v,(list,dict)) or isinstance(v,bool) and rule.method in {'decimal','date'} or str(v)=='': raise ValueError('Unusable value.')
    if any(0xd800<=ord(c)<=0xdfff for c in str(v)): raise ValueError('Invalid Unicode value.')
    if rule.method=='decimal':
        text=str(v).strip()
        decimal=rule.evidence_decimal_separator if evidence and rule.evidence_decimal_separator else rule.decimal_separator
        thousands=rule.evidence_thousands_separator if evidence and rule.evidence_decimal_separator else rule.thousands_separator
        if isinstance(v,(int,float,Decimal)): decimal='.';thousands=None
        if thousands:
            integer=text.split(decimal)[0].lstrip('+-')
            if thousands in integer:
                groups=integer.split(thousands)
                western=len(groups[0])<=3 and all(len(g)==3 for g in groups[1:])
                indian=len(groups[0])<=2 and len(groups[-1])==3 and all(len(g)==2 for g in groups[1:-1])
                if not all(g.isdecimal() for g in groups) or not (western or indian): raise ValueError('Malformed numeric grouping.')
            if decimal in text and thousands in text.split(decimal,1)[1]: raise ValueError('Grouping in fractional value.')
            text=text.replace(thousands,'')
        text=text.replace(decimal,'.')
        if '_' in text: raise ValueError('Undeclared numeric separator.')
        number=Decimal(text)
        if not number.is_finite(): raise ValueError('Non-finite decimal.')
        return number
    if rule.method=='date': return datetime.strptime(str(v),rule.evidence_date_format if evidence and rule.evidence_date_format else rule.date_format).date()
    text=transform(str(v),rule.representation)
    return rule.aliases.get(text,text) if rule.method=='category' else text


def compare(expected,observed,rule):
    try:
        a,b=canonical(expected,rule),canonical(observed,rule,evidence=True)
        if rule.method=='decimal':
            # Decimal defaults must not round long source values during conversion/subtraction.
            with localcontext() as ctx:
                ctx.prec=max(50,len(str(a))+len(str(b))+len(rule.factor)+len(rule.tolerance)+10)
                return abs(a-b*Decimal(rule.factor))<=Decimal(rule.tolerance)
        return a==b
    except (ValueError,ArithmeticError,TypeError): return None


def discover(store,r,mapping,left,left_source):
    candidates=[];reasons=[];complete=True
    source=store.sources[r['sid']];layout=value(r['record'],source.layout_selector) if source.layout_selector else source.layout or value(r['record'],'layout') or 'default'
    if layout!=mapping.layout: return [],False,['layout_mismatch']
    info=store.asset_units.get((source.kind,r['asset'],mapping.strategy)) if r['asset'] else None
    if info:
        cov=info['coverage']
        if cov.get('tables_bounded') and mapping.kind=='table_field' and (not mapping.pages or not cov.get('table_bound_pages') or set(mapping.pages)&set(cov['table_bound_pages'])): complete=False;reasons.append('table_discovery_bound')
        if cov.get('state') in {'unreadable_or_unsupported','unsupported_encrypted','unsupported'} or mapping.pages and any(p>cov.get('total',0) for p in mapping.pages): complete=False;reasons.append('extraction_incomplete')
    if r['asset'] and not info:
        return [],False,['evidence_unavailable']
    substitutions={k:value(left,sel) for k,sel in mapping.substitutions.items()}
    if any(v is None for v in substitutions.values()): return [],False,['substitution_missing']
    def substitute(text,escape=False):
        for name,v in substitutions.items(): text=text.replace('{'+name+'}',regex.escape(str(v)) if escape else str(v))
        return text
    lid=str(value(left,store.sources[left_source].id_selector))
    override=mapping.overrides.get(left_source+':'+lid,mapping.overrides.get(lid))
    if override:
        complete=False;reasons.append('manual_override_selected_scope')
        if 'document_id' in override and str(value(r['record'],source.id_selector))!=str(override['document_id']): return [],False,reasons
    for unit in store.units(r,mapping):
        if mapping.pages and unit.get('page') not in mapping.pages: continue
        if unit.get('part') and unit['part'] not in mapping.parts and not (unit['part'].startswith('word/header') and 'headers' in mapping.parts) and not (unit['part'].startswith('word/footer') and 'footers' in mapping.parts): continue
        if unit.get('state')=='text_free': complete=False;reasons.append('text_free_selected_page');continue
        if override and any(unit.get(k)!=v for k,v in override.items() if k not in {'span','row','column','document_id'}): continue
        store.discovery_visits+=len(unit.get('text',''))+sum(len(x) for x in unit.get('rows',[]))
        if store.discovery_visits>store.config.limits.discovery_visits: complete=False;reasons.append('job_discovery_work_bound');break
        if not unit.get('complete',False): complete=False;reasons.append(unit.get('reason','unsupported_unit'));continue
        if mapping.kind=='table_field' and unit['kind']=='table':
            rows=unit['rows'];header_matches=[]
            for hi,row in enumerate(rows):
                matched={name:[i for i,c in enumerate(row) if c is not None and c in aliases] for name,aliases in mapping.headers.items()}
                if all(len(v)==1 for v in matched.values()): header_matches.append((hi,{k:v[0] for k,v in matched.items()}))
            if len(header_matches)!=1:
                if header_matches: complete=False;reasons.append('ambiguous_headers')
                continue
            hi,columns=header_matches[0];label=value(left,mapping.row_selector) if mapping.row_selector else substitute(mapping.row_label)
            for ri,row in enumerate(rows[hi+1:],hi+1):
                if override and 'row' in override and override['row']!=ri: continue
                if len(row)<=max(columns.values()): complete=False;reasons.append('table_width');continue
                if row[columns[mapping.row_column]]!=str(label): continue
                unknown_context=False;excluded_context=False
                for name,sel in mapping.context_columns.items():
                    v=value(left,sel);cell=row[columns[name]]
                    if v is None or cell in {None,''}: unknown_context=True
                    elif cell!=str(v): excluded_context=True
                if excluded_context: reasons.append('table_context_excluded');continue
                if unknown_context: complete=False;reasons.append('table_context_unknown');continue
                ci=override.get('column',columns[mapping.value_column]) if override else columns[mapping.value_column]
                if ci>=len(row): reasons.append('override_cell_unavailable');continue
                candidate={k:v for k,v in unit.items() if k not in {'rows','cells','geometry','text'}}
                candidate.update(row=ri,column=ci,value=row[ci],cell_location=unit.get('cells',[[]]*len(rows))[ri][ci],mapping=mapping.id)
                candidates.append(candidate)
                if len(candidates)>store.config.limits.candidates: break
        elif mapping.kind in {'label_value','text'} and unit['kind']=='text':
            text=unit['text'];start=0;end=len(text)
            if mapping.section:
                occurrences=[]
                for match in regex.finditer(regex.escape(substitute(mapping.section)),text):
                    occurrences.append(match)
                    if len(occurrences)>1: break
                if len(occurrences)!=1:
                    if occurrences: complete=False;reasons.append('ambiguous_section')
                    continue
                start=occurrences[0].end();end=min(len(text),start+store.config.limits.region_chars)
                if end<len(text): complete=False;reasons.append('section_region_bound')
            if override and 'span' in override: start,end=override['span']
            if not 0<=start<=end<=len(text): reasons.append('override_span_unavailable');continue
            if mapping.kind=='text' or override and 'span' in override:
                candidates.append({**{k:v for k,v in unit.items() if k not in {'geometry','text'}},'value':text[start:end],'span':[start,end],'mapping':mapping.id})
            else:
                for label in mapping.labels:
                    for match in regex.finditer(regex.escape(substitute(label)),text[start:end]):
                        a=start+match.end();b=min(end,a+store.config.limits.region_chars)
                        try:
                            m=regex.match(substitute(mapping.pattern,True),text[a:b],timeout=store.config.limits.pattern_seconds)
                        except TimeoutError: complete=False;reasons.append('pattern_timeout');continue
                        if not m: continue
                        lo,hi=m.span('value');lo+=a;hi+=a
                        if hi==b and b<end: complete=False;reasons.append('region_bound')
                        geometry=unit.get('geometry')
                        candidate={k:v for k,v in unit.items() if k not in {'geometry','text'}}
                        candidate.update(value=text[lo:hi],span=[lo,hi],mapping=mapping.id,label=label,geometry_digest=digest(geometry) if geometry else None)
                        # Source glyph geometry is retained once per extracted unit in scratch;
                        # published text witnesses use its digest and unit location for exact re-extraction.
                        candidates.append(candidate)
                        if len(candidates)>store.config.limits.candidates: break
        if len(candidates)>store.config.limits.candidates:
            candidates=candidates[:store.config.limits.candidates];complete=False;reasons.append('candidate_bound');break
    return candidates,complete,sorted(set(reasons))


def reconcile(store,rule,left_id):
    rel=next(x for x in store.spec.relationships if x.id==rule.relationship);left=store.record(left_id);expected=value(left['record'],rule.field)
    mapping=next((x for x in store.spec.mappings if x.id==rule.mapping),None)
    eligible=[];reasons=[];contexts=[];complete=True
    for rid,payload in stream(store.con,'SELECT e.r,c.payload FROM edges e LEFT JOIN contexts c ON e.rel=c.rel AND e.l=c.l AND e.r=c.r WHERE e.rel=? AND e.l=? ORDER BY e.r',(rel.id,left_id)):
        right=store.record(rid);ctx=json.loads(payload) if payload else context(rel,left['record'],right['record']);contexts.append({'record':rid,**ctx})
        if ctx['unknown']: complete=False;reasons+=ctx['unknown']
        if ctx['eligible']: eligible.append((right,ctx))
    if rel.version_mode=='latest_as_of' and eligible:
        newest=max(int(ctx['availability']) for _,ctx in eligible);eligible=[(r,c) for r,c in eligible if int(c['availability'])==newest]
        if len(eligible)>1: complete=False;reasons.append('ambiguous_as_of_tie')
    all_candidates=[];semantic_docs=[]
    for right,ctx in eligible:
        if mapping:
            candidates,done,why=discover(store,right,mapping,left['record'],left['sid']);complete &= done;reasons+=why
        else: candidates=[{'kind':'field','value':value(right['record'],rule.right_field),'selector':rule.right_field,'complete':True}]
        for candidate in candidates: all_candidates.append({'right':right['rid'],'unit':candidate,'authority':rule.authority_source==right['sid'] or bool(rule.authority_role and (value(right['record'],'role') or store.sources[right['sid']].role)==rule.authority_role)})
        if rule.method in {'nli','image_text'}: semantic_docs.append(right['rid'])
    if not eligible: complete=False;reasons.append('no_eligible_evidence')
    if rule.method in {'nli','image_text'}:
        return {'status':'unassessed','complete':complete,'reasons':sorted(set(reasons)),'contexts':contexts,'candidates':all_candidates,'semantic_documents':semantic_docs,'expected':expected}
    comparisons=[];valid=[]
    for c in all_candidates:
        v=c['unit']['value'];evidence_unit=mapping.unit if mapping else value(store.record(c['right'])['record'],'unit')
        unit_ok=not rule.unit or evidence_unit==rule.unit or evidence_unit is not None and Decimal(rule.factor)!=1
        currency_ok=not rule.currency or mapping and mapping.currency==rule.currency or not mapping and value(store.record(c['right'])['record'],'currency')==rule.currency
        match=compare(expected,v,rule) if unit_ok and currency_ok else None
        comparisons.append(match)
        try: valid.append((canonical(v,rule,evidence=True),c))
        except (ValueError,InvalidOperation,TypeError): complete=False;reasons.append('invalid_value')
        if match is None: complete=False;reasons.append('comparison_unresolved')
    if not all_candidates: complete=False;reasons.append('mapping_not_found')
    # Conflict means evidence values differ beyond the declared tolerance.
    distinct=[]
    evidence_rule=__import__('dataclasses').replace(rule,factor='1',date_format=rule.evidence_date_format or rule.date_format,decimal_separator=rule.evidence_decimal_separator or rule.decimal_separator,thousands_separator=rule.evidence_thousands_separator if rule.evidence_decimal_separator else rule.thousands_separator)
    for v,c in valid:
        if not any(compare(c['unit']['value'],old['unit']['value'],evidence_rule) is True for old in distinct): distinct.append(c)
    conflict=len(distinct)>1
    selected=[c for c in all_candidates if c['authority']] if rule.authority_role or rule.authority_source else all_candidates
    selected_matches=[compare(expected,c['unit']['value'],rule) for c in selected]
    selected_conflict=any(compare(a['unit']['value'],b['unit']['value'],evidence_rule) is False for a in selected for b in selected)
    if not complete or not selected or any(x is None for x in selected_matches): status='inconclusive'
    elif selected_conflict: status='conflicting_evidence'
    elif all(selected_matches): status='satisfied'
    else: status='violated'
    if conflict and not (rule.authority_role or rule.authority_source): status='conflicting_evidence'
    return {'status':status,'complete':complete,'reasons':sorted(set(reasons)),'contexts':contexts,'candidates':all_candidates,'comparisons':comparisons,'conflict':conflict,'expected':expected}


def required(store):
    structural=relationships(store)
    store.context_evidence=relationship_contexts(store)
    for rule in store.spec.rules:
        rel=next(r for r in store.spec.relationships if r.id==rule.relationship)
        for rid, in stream(store.con,'SELECT rid FROM records WHERE sid=? ORDER BY ordinal',(rel.left_source,)):
            result=reconcile(store,rule,rid)
            store.con.execute('INSERT INTO outcomes VALUES (?,?,?,?)',[rule.id,rid,result['status'],json.dumps(result,ensure_ascii=True,default=str)])
            store.work.check('reconciliation')
    return structural


def content_units(store,rid,selectors):
    """Raw source-aligned text/cells, independent of reconciliation recipes."""
    r=store.record(rid);source=store.sources[r['sid']]
    if not r['asset']:
        text=value(r['record'],selectors[0])
        if isinstance(text,str) and text.strip(): yield text,{'kind':'field','selector':selectors[0],'value':text},True
        return
    settings=next((v for (kind,asset,strategy),v in sorted(store.asset_units.items()) if kind==source.kind and asset==r['asset']),None)
    if not settings: return
    cov=settings['coverage'];complete=cov.get('state')=='processed' and not cov.get('text_free',0) and not cov.get('tables_bounded',False) and not cov.get('unsupported_blocks',0)
    for payload, in stream(store.con,'SELECT payload FROM units WHERE asset=? AND settings=? ORDER BY ordinal',(r['asset'],settings['settings'])):
        u=json.loads(payload);base={k:v for k,v in u.items() if k not in {'text','geometry','rows','cells'}}
        base['extraction_settings']=settings['settings']
        if u['kind']=='text':
            if u.get('text','').strip():
                if 'geometry' in u: base['geometry_digest']=digest(u['geometry'])
                yield u['text'],base|{'value':u['text'],'span':[0,len(u['text'])]},complete and u.get('complete',True)
        elif u['kind']=='table':
            for row,values in enumerate(u['rows']):
                for col,text in enumerate(values):
                    if isinstance(text,str) and text.strip(): yield text,base|{'value':text,'row':row,'column':col,'cell_location':u['cells'][row][col]},complete and u.get('complete',True)


def separation(store):
    results=[]
    for s in store.spec.separation:
        document_content=s.mode=='content' and any(store.sources[sid].kind=='document' for sid in (s.left_source,s.right_source))
        populations=[];selected={'left':[],'right':[]};excluded_units=0;incomplete=False;examples=[];work_start=store.discovery_visits
        for side,sid,selectors,path,splits in [('left',s.left_source,s.left_keys,s.left_path,s.left_splits),('right',s.right_source,s.right_keys,s.right_path,s.right_splits)]:
            table='separation_'+side;store.con.execute(f'CREATE OR REPLACE TEMP TABLE {table}(rid VARCHAR,k VARCHAR)')
            scope='sid=?'+(' AND split IN (SELECT unnest(?))' if splits else '');params=[sid,*([list(splits)] if splits else [])]
            populations.append(store.con.execute('SELECT count(*) FROM records WHERE '+scope,params).fetchone()[0])
            if s.mode=='ancestry':
                store.con.execute(f'INSERT INTO {table} SELECT rid,rid FROM records WHERE '+scope,params)
                for rel in path:
                    store.con.execute(f'CREATE OR REPLACE TEMP TABLE step AS SELECT DISTINCT p.rid,e.r k FROM {table} p JOIN edges e ON p.k=e.l WHERE e.rel=?',[rel])
                    store.con.execute(f'DELETE FROM {table}');store.con.execute(f'INSERT INTO {table} SELECT * FROM step')
            else:
                for rid,payload,asset in stream(store.con,'SELECT rid,payload,asset FROM records WHERE '+scope+' ORDER BY hash(rid,?),rid',(*params,store.config.seed)):
                    r=decode_record(payload)
                    if s.mode=='keys': k=key(r,selectors)
                    elif s.mode=='content':
                        for text,unit,complete in content_units(store,rid,selectors):
                            store.work.check('cross-source text unit indexing')
                            store.con.execute(f'INSERT INTO {table} VALUES (?,?)',[rid,digest(text)])
                            incomplete|=not complete
                            if not document_content or len(text)<50: continue
                            if len(selected[side])<store.config.limits.candidates and len(text)<=store.config.limits.region_chars:
                                selected[side].append((rid,text,unit))
                            else: excluded_units+=1
                        store.work.check('cross-source extracted text equality')
                        continue
                    else:
                        # M7 representations include dimensions, mode and relevant color/alpha metadata.
                        k=store.files.get(asset,{}).get('sha256')
                        facts=store.asset_facts.get(('image',asset),{})
                        for name in ('native_sha256','oriented_sha256'):
                            if facts.get(name): store.con.execute(f'INSERT INTO {table} VALUES (?,?)',[rid,name+':'+facts[name]])
                        if facts.get('visual_eligible') and len(selected[side])<store.config.limits.candidates: selected[side].append((rid,facts,asset))
                        elif facts.get('visual_eligible'): excluded_units+=1
                    store.con.execute(f'INSERT INTO {table} VALUES (?,?)',[rid,k])
                    store.work.check('cross-source exact representation')
        supplemental=0;similarity=0;pair_visits=0;bounded=False
        # Raw literal containment uses M6's winnowing fingerprints; it never uses normalized similarity as equality.
        if document_content or s.mode=='assets':
            if document_content:
                from datatrust.text_search import fingerprints
                prepared={'left':[],'right':[]}
                for side,units in selected.items():
                    for u in units:
                        if store.discovery_visits+len(u[1])>store.config.limits.discovery_visits: excluded_units+=1;continue
                        store.discovery_visits+=len(u[1]);store.work.check('bounded passage fingerprints')
                        prepared[side].append((*u,{h for h,pos in fingerprints(u[1],50)[1]}))
            else: prepared=selected
            from datatrust.text_search import cross_pairs
            nleft=len(prepared['left'])
            for li,ri in cross_pairs(list(range(nleft)),list(range(nleft,nleft+len(prepared['right'])))):
                a,b=prepared['left'][li],prepared['right'][ri-nleft]
                if pair_visits>=store.config.limits.candidates: bounded=True;break
                cost=len(a[1])+len(b[1]) if document_content else 1
                if store.discovery_visits+cost>store.config.limits.discovery_visits: bounded=True;break
                store.discovery_visits+=cost;pair_visits+=1
                store.work.check('bounded cross-representation overlap candidates')
                if document_content:
                    if a[1]==b[1] or not a[3]&b[3]: continue
                    short,long=(a,b) if len(a[1])<=len(b[1]) else (b,a)
                    if len(short[1])<50: continue
                    start=long[1].find(short[1])
                    if start<0: continue
                    token=digest(short[1]);supplemental+=1
                    for side,u in [('left',a),('right',b)]: store.con.execute(f'INSERT INTO separation_{side} VALUES (?,?)',[u[0],token])
                    if len(examples)<store.config.limits.witnesses:
                        refs=[]
                        for u in (a,b):
                            unit=dict(u[2]);unit['value']=short[1]
                            unit['span']=[start,start+len(short[1])] if u is long else [0,len(short[1])]
                            refs.append(store.witness(u[0],unit=unit))
                        examples.append({'reason':'exact_literal_containment','evidence_refs':refs,'match_kind':'exact'})
                else:
                    af,bf=a[1],b[1]
                    if af.get('oriented_sha256')==bf.get('oriented_sha256') or af.get('native_sha256')==bf.get('native_sha256'): continue
                    distance=(af['phash']^bf['phash']).bit_count()
                    if distance<=6:
                        similarity+=1
                        if len(examples)<store.config.limits.witnesses:
                            refs=[store.witness(u[0],store.sources[store.record(u[0])['sid']].path_selector) for u in (a,b)]
                            examples.append({'reason':'perceptual_image_similarity','evidence_refs':refs,'match_kind':'investigation_candidate','hamming_distance':distance})
            bounded|=bool(excluded_units)
        shared=store.con.execute('SELECT count(*) FROM (SELECT k FROM separation_left WHERE k IS NOT NULL INTERSECT SELECT k FROM separation_right WHERE k IS NOT NULL)').fetchone()[0]
        left=store.con.execute('SELECT count(DISTINCT rid) FROM separation_left l WHERE k IS NOT NULL AND EXISTS(SELECT 1 FROM separation_right r WHERE l.k=r.k)').fetchone()[0]
        right=store.con.execute('SELECT count(DISTINCT rid) FROM separation_right r WHERE k IS NOT NULL AND EXISTS(SELECT 1 FROM separation_left l WHERE l.k=r.k)').fetchone()[0]
        # Group exact representations rather than exploding all occurrence pairs.
        for k,l,r in store.con.execute('SELECT l.k,l.rid,r.rid FROM (SELECT k,min(rid) rid FROM separation_left WHERE k IS NOT NULL GROUP BY k) l JOIN (SELECT k,min(rid) rid FROM separation_right WHERE k IS NOT NULL GROUP BY k) r ON l.k=r.k ORDER BY l.k LIMIT ?',[store.config.limits.witnesses]).fetchall():
            representation=k.split(':',1)[0] if ':' in k else 'declared_exact'
            if len(examples)<store.config.limits.details:
                refs=[]
                for rid,selectors in [(l,s.left_keys),(r,s.right_keys)]:
                    if s.mode=='content':
                        for text,unit,complete in content_units(store,rid,selectors):
                            if digest(text)==k: refs.append(store.witness(rid,unit=unit));break
                    else:
                        src=store.sources[store.record(rid)['sid']]
                        refs.extend(store.witness(rid,sel) for sel in ((src.path_selector,) if s.mode=='assets' else selectors[:store.config.limits.witnesses]))
                if s.mode=='ancestry':
                    ancestor=store.record(k);refs.append(store.witness(k,store.sources[ancestor['sid']].id_selector))
                if len(refs)>=2: examples.append({'reason':'exact_'+representation,'evidence_refs':refs,'match_kind':'exact'})
        unqualified=[]
        for side,sid,splits in [('left',s.left_source,s.left_splits),('right',s.right_source,s.right_splits)]:
            scope='sid=?'+(' AND split IN (SELECT unnest(?))' if splits else '');params=[sid,*([list(splits)] if splits else [])]
            n=store.con.execute(f'SELECT count(*) FROM records r WHERE '+scope+f' AND NOT EXISTS(SELECT 1 FROM separation_{side} p WHERE p.rid=r.rid AND p.k IS NOT NULL)',params).fetchone()[0];unqualified.append(n)
        results.append({'requirement':s.id,'shared_units':shared,'left_affected_records':left,'right_affected_records':right,'populations':populations,'unqualified_records':unqualified,'required':s.required,'status':'violated' if shared and s.required else 'inconclusive' if any(unqualified) or not all(populations) or document_content and (incomplete or bounded) else 'satisfied','examples':examples,'exact_containment_pairs':supplemental,'investigation_candidates':similarity,'candidate_coverage':{'examined_pairs':pair_visits,'work_visits':store.discovery_visits-work_start,'pair_limit':store.config.limits.candidates,'excluded_units':excluded_units,'bounded':bounded,'extraction_incomplete':incomplete,'minimum_literal_graphemes':50,'image_hamming_radius':6,'similarity_establishes_violation':False,'absence_claim':'examined scope only'},'exact_representations':['declared_raw_content'] if s.mode=='content' else ['file_sha256','native_raster_v1','oriented_rgba8_v1'] if s.mode=='assets' else [s.mode]})
    return results
