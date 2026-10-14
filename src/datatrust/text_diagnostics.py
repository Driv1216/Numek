"""Required population diagnostics. Evidence meaning is independent of execution."""
from collections import Counter
from dataclasses import asdict
import hashlib
import json

from datatrust.text_normalization import MISSING,get,state,lexical,pointer,span_bounds
from datatrust.scalable import fail


class Evidence:
    def __init__(self,work,spec,config,audit_id):
        self.work=work;self.con=work.con;self.spec=spec;self.config=config;self.audit_id=audit_id
        self.records=[];self.checks=[];self.findings=[];self.coverage={};self.locators={};self.definitions={}
        self.sources={x.id:f'source_{i+1}' for i,x in enumerate(spec.inputs)}
        self.definitions.update({ref:{'kind':'source','source_id':sid} for sid,ref in self.sources.items()})
    def ref(self,loc):return hashlib.sha256(json.dumps(loc,sort_keys=True,ensure_ascii=True).encode()).hexdigest()
    def opaque(self,kind,value):
        ref=kind+'_'+hashlib.sha256((self.audit_id+'\0'+kind+'\0'+str(value)).encode()).hexdigest()[:24]
        self.definitions[ref]={'kind':kind,'value':value}
        return ref
    def witness(self,key):
        value=self.con.execute('SELECT payload FROM locators WHERE ref=? LIMIT 1',[key]).fetchone()
        if not value:return None
        ref='evidence_'+hashlib.sha256((self.audit_id+key).encode()).hexdigest()[:24]
        self.locators[ref]=json.loads(value[0]);return ref
    def span_witness(self,key,start,end):
        parent=self.witness(key)
        if not parent:return None
        ref='evidence_'+hashlib.sha256((self.audit_id+key+str(start)+':'+str(end)).encode()).hexdigest()[:24]
        self.locators[ref]=self.locators[parent]|{'span':[start,end]}
        return ref
    def add(self,family,data,*,meaning='deterministic_fact',keys=(),violations=0,scope='full_population',coverage=None):
        refs=[]
        for key in list(keys)[:self.config.limits.witnesses]:
            ref=self.witness(key)
            if ref:refs.append(ref)
        record={'id':f'e{len(self.records)+1}','family':family,'meaning':meaning,'data':data,'references':refs,'scope':scope}
        self.records.append(record)
        self.checks.append({'id':record['id'],'family':family,'applicability':'applicable','execution':'completed','violations':violations,'scope':scope})
        if coverage is not None:self.coverage[family]=coverage
        if violations:
            actions={'invalidity':'Resolve retained invalidity witnesses, repair the applicable record or mapping, and re-audit the original preserved source.','identities':'Resolve duplicate logical identities before using dependent joins.','exact_duplicates':'Review split assignments and legitimate shared content before removing or moving any occurrence.','near_duplicates':'Inspect shared and differing content; template similarity and document families require context.','passages':'Resolve original passage spans and review provenance and evaluation exposure.','annotation_disagreement':'Review repeated-input annotation differences against task semantics; disagreement alone does not identify the correct label.','conversations':'Review explicit order, role, completion and tool-reference requirements.','retrieval':'Repair unresolved references or declared extractive provenance and review judgment conflicts.'}
            self.findings.append({'id':record['id'],'family':family,'meaning':meaning,'count':violations,'references':refs,'action':actions.get(family,'Inspect integrity-verified local evidence and the applicable declaration.')})
        return record


def annotation_tokens(store,item,rid,loc,spec,text,record):
    values=get(record,spec.tokens_selector)
    if not isinstance(values,list):return None,['invalid_token_collection']
    bounds=[];reasons=[];cursor=0
    for i,token in enumerate(values):
        store.tokens+=1
        if store.tokens>store.config.limits.max_supplied_tokens:fail('Supplied-token population exceeds hard limit.','token_limit')
        try:
            if isinstance(token,str):
                if not token:raise ValueError('empty_token')
                # String tokens align only at the next occurrence, without crossing supplied order.
                start=text.find(token,cursor)
                if start<0:raise ValueError('token_not_aligned')
                end=start+len(token)
            elif isinstance(token,dict):
                start,end=span_bounds(text,token.get('start'),token.get('end'),spec.offset_unit if spec.offset_unit!='token' else 'codepoint')
                if 'text' in token and token['text']!=text[start:end]:raise ValueError('token_text_mismatch')
            else:raise ValueError('invalid_token')
            if start<cursor:raise ValueError('token_order_overlap')
            cursor=end;bounds.append({'start':start,'end':end})
        except (ValueError,TypeError):reasons.append('invalid_token_alignment');bounds.append(None)
    return bounds,reasons


def tags_valid(labels,scheme):
    active=None
    for value in labels:
        if value=='O':
            if scheme in {'BIOES','BILOU'} and active is not None:return False
            active=None;continue
        if not isinstance(value,str) or '-' not in value:return False
        tag,entity=value.split('-',1)
        if not entity:return False
        if scheme=='BIO':
            if tag=='B':active=entity
            elif tag=='I' and active==entity:pass
            else:return False
        else:
            end,single=('E','S') if scheme=='BIOES' else ('L','U')
            if tag==single and active is None:pass
            elif tag=='B' and active is None:active=entity
            elif tag=='I' and active==entity:pass
            elif tag==end and active==entity:active=None
            else:return False
    return scheme=='BIO' or active is None


def ingest_annotations(store,item,rid,loc,record,units,*,associated=False):
    for n,spec in enumerate(item.annotations):
        if bool(spec.content_source)!=associated:continue
        uid,text,content_state=units[(spec.content_source,spec.field) if associated else spec.field];value=get(record,spec.selector)
        aid=hashlib.sha256((rid+'\0annotation\0'+str(n)).encode()).hexdigest()
        st='absent' if value is MISSING else 'null' if value is None else 'observed'
        status=get(record,spec.status_selector);expected=spec.expectation;reasons=[]
        if spec.status_selector and status in spec.required_statuses:expected='required'
        metadata_state='not_declared' if not spec.status_selector else state(status)
        if spec.status_selector and metadata_state=='invalid':store.invalid(rid,item.id,{k:v for k,v in loc.items() if k!='_record'}|{'selector':spec.status_selector},'invalid_annotation_status')
        labels=[];tokens=None
        if spec.tokens_selector and (spec.kind=='token' or spec.offset_unit=='token'):
            tokens,token_issues=annotation_tokens(store,item,rid,loc,spec,text or '',record)
            if st=='observed':reasons+=token_issues
            else:
                for reason in set(token_issues):store.invalid(rid,item.id,{k:v for k,v in loc.items() if k!='_record'}|{'selector':spec.tokens_selector},reason)
        if st=='observed':
            if spec.kind=='classification':
                if lexical(value) is None:reasons.append('invalid_classification_label')
                else:labels=[value]
            elif spec.kind=='multilabel':
                if not isinstance(value,list):reasons.append('invalid_multilabel_collection')
                else:
                    labels=[x for x in value if lexical(x) is not None]
                    if len(labels)!=len(value):reasons.append('invalid_multilabel_item')
                    if len(set(labels))!=len(labels):reasons.append('duplicate_multilabel')
            elif text is None:reasons.append('annotation_content_unavailable')
            elif spec.kind=='token':
                if not isinstance(value,list):reasons.append('invalid_token_label_collection')
                else:
                    labels=[x for x in value if lexical(x) is not None]
                    if len(labels)!=len(value):reasons.append('invalid_token_labels')
                    if tokens is not None and len(value)!=len(tokens):reasons.append('token_label_length')
                    if spec.scheme!='none' and not tags_valid(value,spec.scheme):reasons.append('invalid_tag_sequence')
            else:
                if not isinstance(value,list):reasons.append('invalid_span_collection')
                else:
                    intervals=[]
                    for i,span in enumerate(value):
                        store.annotations+=1
                        if store.annotations>store.config.limits.max_annotations:fail('Annotation population exceeds hard limit.','annotation_limit')
                        try:
                            if not isinstance(span,dict):raise ValueError('invalid_span_item')
                            if 'label' in span:
                                if lexical(span['label']) is None:raise ValueError('invalid_span_label')
                                labels.append(span['label'])
                            if tokens is not None and any(t is None for t in tokens):raise ValueError('invalid_token_alignment')
                            start,end=span_bounds(text,span.get('start'),span.get('end'),spec.offset_unit,tokens)
                            if 'text' in span and span['text']!=text[start:end]:raise ValueError('span_text_mismatch')
                            intervals.append((start,end))
                            store.add('annotation_items',(aid,i,'valid',start,end))
                        except (ValueError,TypeError):
                            reasons.append('invalid_span')
                            store.add('annotation_items',(aid,i,'invalid',None,None))
                            store.invalid(rid,item.id,{k:v for k,v in loc.items() if k!='_record'}|{'selector':pointer(spec.selector)+'/'+str(i)},'invalid_span')
                    if not spec.allow_overlap and any(a[1]>b[0] for a,b in zip(sorted(intervals),sorted(intervals)[1:])):reasons.append('forbidden_span_overlap')
                    if spec.kind=='qa' and spec.answerable_selector:
                        answerable=get(record,spec.answerable_selector)
                        if not isinstance(answerable,bool):reasons.append('invalid_answerability')
                        elif not answerable and value:reasons.append('unanswerable_with_answers')
                        elif answerable and not value:reasons.append('answerable_without_answers')
        store.annotations+=1
        if store.annotations>store.config.limits.max_annotations:fail('Annotation population exceeds hard limit.','annotation_limit')
        if st=='observed' or st=='invalid':
            if spec.kind in {'classification','multilabel','token'}:
                members=value if isinstance(value,list) else [value]
                for i,label in enumerate(members):
                    store.annotations+=1
                    if store.annotations>store.config.limits.max_annotations:fail('Annotation population exceeds hard limit.','annotation_limit')
                    store.add('annotation_items',(aid,i,'valid' if lexical(label) is not None else 'invalid',None,None))
        if tokens:
            for i,b in enumerate(tokens):store.add('tokens',(aid,i,b['start'] if b else None,b['end'] if b else None,b is not None))
        if reasons:st='invalid'
        store.add('annotations',(aid,rid,uid,spec.kind,st,expected,lexical(status),json.dumps(labels,ensure_ascii=True),metadata_state))
        store.add('locators',(aid,json.dumps({k:v for k,v in loc.items() if k!='_record'}|{'source_id':item.id,'selector':spec.selector})))
        for reason in set(reasons):store.invalid(rid,item.id,{k:v for k,v in loc.items() if k!='_record'}|{'selector':spec.selector},reason)
        if expected=='required' and st in {'absent','null'}:store.invalid(rid,item.id,{k:v for k,v in loc.items() if k!='_record'}|{'selector':spec.selector},'required_annotation_missing')


def ingest_conversation(store,item,rid,loc,record):
    from datatrust.text_contracts import TextFieldSpec
    c=item.conversation
    values=get(record,c.messages_selector) if c.messages_selector else [record]
    conv=lexical(get(record,c.conversation_selector)) if c.conversation_selector else rid
    if not isinstance(values,list):store.invalid(rid,item.id,{k:v for k,v in loc.items() if k!='_record'},'invalid_message_collection');return
    if conv is None:store.invalid(rid,item.id,{k:v for k,v in loc.items() if k!='_record'},'invalid_conversation_identity')
    if not values and c.require_completion:store.invalid(rid,item.id,{k:v for k,v in loc.items() if k!='_record'},'missing_conversation_completion')
    for i,msg in enumerate(values):
        base=pointer(c.messages_selector)+'/'+str(i) if c.messages_selector else ''
        mloc={k:v for k,v in loc.items() if k!='_record'}|{'selector':base,'nested_ordinal':i,'source_id':item.id}
        mid=hashlib.sha256((rid+'\0message\0'+str(i)).encode()).hexdigest()
        store.add('locators',(mid,json.dumps(mloc)))
        if not isinstance(msg,dict):store.invalid(rid,item.id,mloc,'invalid_message');continue
        role=get(msg,c.role_selector);content=get(msg,c.content_selector);st=state(content)
        position=i if c.messages_selector else get(msg,c.order_selector)
        if isinstance(position,bool) or not isinstance(position,int):position=None;store.invalid(rid,item.id,mloc,'invalid_message_order')
        if role not in c.roles:store.invalid(rid,item.id,mloc,'invalid_message_role')
        calls=get(msg,c.calls_selector)
        if st in {'absent','null'} and role=='assistant' and isinstance(calls,list) and calls:pass
        elif st in {'absent','null','invalid'}:store.invalid(rid,item.id,mloc,'invalid_message_content')
        store.add('messages',(mid,rid,item.id,conv,position,lexical(role),st,json.dumps(msg,ensure_ascii=True)))
        field=TextFieldSpec('message_content',base+pointer(c.content_selector),'completion' if role=='assistant' else 'prompt')
        store.content(item,rid,loc,field,content,field.selector)


def associated_annotations(store):
    store.con.execute('CREATE TABLE annotation_identities AS SELECT sid,lid,count(*) n,min(rid) rid FROM records WHERE valid AND lid IS NOT NULL GROUP BY sid,lid')
    items={x.id:x for x in store.spec.inputs}
    cursor=store.con.cursor().execute('SELECT sid,rid,loc,payload FROM pending_annotations ORDER BY sid,rid')
    while batch:=cursor.fetchmany(64):
        for sid,rid,loc,payload in batch:
            item=items[sid];record=json.loads(payload);location=json.loads(loc);units={}
            for a in item.annotations:
                if not a.content_source:continue
                key=lexical(get(record,a.content_id_selector))
                values=store.con.execute('SELECT c.uid,c.text,c.state FROM annotation_identities i JOIN content c ON i.rid=c.rid WHERE i.sid=? AND i.lid=? AND i.n=1 AND c.field=?',[a.content_source,key,a.field]).fetchall()
                if len(values)==1:units[(a.content_source,a.field)]=values[0]
                else:
                    units[(a.content_source,a.field)]=(None,None,'invalid')
                    store.invalid(rid,sid,location|{'selector':a.content_id_selector},'unresolved_or_ambiguous_annotation_content')
            ingest_annotations(store,item,rid,location|{'_record':record},record,units,associated=True)
    store.flush()


def required(e,store):
    con=store.con
    def rows(sql,args=()):return con.execute(sql,args).fetchall()
    invalid_count=con.execute('SELECT count(*) FROM invalid').fetchone()[0]
    invalid_groups=rows('SELECT reason,count(*) FROM invalid GROUP BY reason ORDER BY reason')
    e.add('invalidity',{'invalid_items':invalid_count,'reasons':dict(invalid_groups),'framing':{e.sources[k]:v for k,v in store.counts.items()}},meaning='deterministic_violation',keys=[x[0] for x in rows('SELECT ref FROM invalid ORDER BY sid,rid,reason LIMIT ?',[e.config.limits.witnesses])],violations=invalid_count)
    states=rows('SELECT state,count(*) FROM content GROUP BY state ORDER BY state')
    totals=con.execute('SELECT count(*),sum(chars),sum(bytes),sum(controls),min(chars),max(chars),avg(chars),quantile_cont(chars,[.25,.5,.75]) FROM content').fetchone()
    scripts=Counter()
    # Stream small histograms rather than retaining the content population.
    cursor=con.execute('SELECT scripts,count(*) FROM content GROUP BY scripts')
    while batch:=cursor.fetchmany(2048):
        for value,n in batch:
            for k,v in json.loads(value).items():scripts[k]+=v*n
    changed=con.execute("SELECT count(*) FROM representations a JOIN representations b USING(uid) WHERE a.representation='raw' AND b.representation='nfc' AND a.text<>b.text").fetchone()[0]
    e.add('corpus',{'content_units':totals[0],'states':dict(states),'characters':totals[1] or 0,'utf8_bytes':totals[2] or 0,'unusual_controls':totals[3] or 0,'minimum_characters':totals[4],'maximum_characters':totals[5],'mean_characters':totals[6],'character_quartiles':totals[7],'script_counts':dict(scripts),'nfc_changed_units':changed,'unicode_version':'16.0.0','script_is_language':False})
    con.execute('CREATE TABLE identities AS SELECT sid,lid,count(*) n,min(rid) rid FROM records WHERE valid AND lid IS NOT NULL GROUP BY sid,lid')
    ambiguous=con.execute('SELECT coalesce(sum(n),0) FROM identities WHERE n>1').fetchone()[0]
    e.add('identities',{'ambiguous_occurrences':ambiguous,'missing_identities':con.execute('SELECT count(*) FROM records WHERE valid AND lid IS NULL').fetchone()[0],'synthetic_logical_ids':False},meaning='deterministic_violation',keys=[x[0] for x in rows('SELECT rid FROM identities WHERE n>1 ORDER BY sid,lid LIMIT ?',[e.config.limits.witnesses])],violations=ambiguous)
    con.execute('CREATE TABLE hash_candidates AS SELECT representation,digest FROM representations GROUP BY representation,digest HAVING count(*)>1')
    con.execute('CREATE TABLE exact_groups AS SELECT r.representation,r.digest,r.text,count(*) n FROM representations r JOIN hash_candidates h USING(representation,digest) GROUP BY r.representation,r.digest,r.text HAVING count(*)>1')
    duplicates=rows('SELECT representation,count(*),sum(n),sum(n-1) FROM exact_groups GROUP BY representation ORDER BY representation')
    for rep,groups,n,excess in duplicates:
        keys=[x[0] for x in rows('SELECT r.uid FROM representations r JOIN exact_groups g USING(representation,digest,text) WHERE representation=? ORDER BY r.uid LIMIT ?',[rep,e.config.limits.witnesses])]
        cross=con.execute('SELECT count(*) FROM (SELECT r.digest,r.text FROM representations r JOIN exact_groups g USING(representation,digest,text) JOIN content c USING(uid) WHERE representation=? GROUP BY r.digest,r.text HAVING count(DISTINCT c.sid||chr(0)||c.split)>1)',[rep]).fetchone()[0]
        e.add('exact_duplicates',{'representation':rep,'groups':groups,'occurrences':n,'excess_occurrences':excess,'cross_source_or_split_groups':cross,'equality_verified':True},meaning='contextual_observation',keys=keys,violations=groups)
    ann=rows('SELECT kind,state,expected,count(*) FROM annotations GROUP BY kind,state,expected ORDER BY kind,state,expected')
    unknown_collections=con.execute("SELECT count(*) FROM invalid WHERE reason IN ('invalid_token_label_collection','invalid_multilabel_collection','invalid_span_collection','invalid_token_collection')").fetchone()[0]
    e.add('annotations',{'states':[{'kind':k,'observation':s,'expectation':x,'count':n} for k,s,x,n in ann],'supplied_tokens':store.tokens,'annotation_collections':sum(n for _,_,_,n in ann),'annotation_items':con.execute('SELECT count(*) FROM annotation_items').fetchone()[0],'unknown_item_cardinality_collections':unknown_collections,'charged_annotation_expansion':store.annotations,'metadata_states':dict(rows('SELECT metadata_state,count(*) FROM annotations GROUP BY metadata_state')),'item_states':dict(rows('SELECT state,count(*) FROM annotation_items GROUP BY state')),'label_correctness_established':False})
    con.execute('CREATE TABLE annotation_categories AS SELECT kind,t.label,count(*) n FROM annotations,unnest(from_json(labels,\'["VARCHAR"]\')) t(label) GROUP BY kind,t.label')
    categories=rows('SELECT kind,label,n FROM annotation_categories ORDER BY n DESC,kind,label LIMIT ?',[e.config.limits.details])
    category_count=con.execute('SELECT count(*) FROM annotation_categories').fetchone()[0]
    e.add('annotation_categories',{'category_count':category_count,'frequencies':[{'kind':k,'label_reference':e.opaque('label',v),'count':n} for k,v,n in categories],'retained_category_omissions':max(0,category_count-len(categories))})
    disagreement=con.execute("SELECT count(*) FROM (SELECT p.digest,p.text,a.kind FROM annotations a JOIN representations p ON a.uid=p.uid WHERE p.representation='raw' AND a.state='observed' AND a.kind IN ('classification','multilabel') GROUP BY p.digest,p.text,a.kind HAVING count(DISTINCT a.labels)>1)").fetchone()[0]
    disagreement_keys=rows("SELECT min(a.aid) FROM annotations a JOIN representations p ON a.uid=p.uid WHERE p.representation='raw' AND a.state='observed' AND a.kind IN ('classification','multilabel') GROUP BY p.digest,p.text,a.kind HAVING count(DISTINCT a.labels)>1 LIMIT ?",[e.config.limits.witnesses])
    e.add('annotation_disagreement',{'repeated_input_groups_with_disagreement':disagreement},meaning='contextual_observation',keys=[x[0] for x in disagreement_keys],violations=disagreement)
    conversations(e,store)
    retrieval(e,store)
    comparisons(e,store)
    empty={'annotations':not ann,'annotation_categories':not ann,'annotation_disagreement':not ann,'conversations':not any(x.conversation for x in store.spec.inputs),'retrieval':not any(x.retrieval for x in store.spec.inputs),'corpus':totals[0]==0}
    for check in e.checks:
        if empty.get(check['family']):check.update(applicability='blocked' if check['family']=='corpus' else 'not_applicable',reason='zero_applicable_population')


def message_groups(cursor,config):
    current=None;messages=[];size=0
    while batch:=cursor.fetchmany(256):
        for conv,mid,position,role,payload in batch:
            if current is not None and conv!=current:
                yield current,messages
                messages=[];size=0
            current=conv;size+=len(payload.encode())
            if len(messages)>=config.limits.max_nested_items or size>config.execution.batch_bytes:
                fail('Conversation expansion exceeds declared retention limit.','conversation_limit')
            messages.append({'mid':mid,'position':position,'role':role,'payload':payload})
    if current is not None:yield current,messages


def conversations(e,store):
    con=store.con
    violations=Counter();witnesses=[];conversation_count=0
    for item in store.spec.inputs:
        if not item.conversation:continue
        c=item.conversation
        # Partition on disk; only one bounded conversation is retained at a time.
        cursor=con.cursor().execute('SELECT conv,mid,position,role,payload FROM messages WHERE sid=? AND conv IS NOT NULL ORDER BY conv,position,mid',[item.id])
        for conv,messages in message_groups(cursor,store.config):
            conversation_count+=1
            before=sum(violations.values())
            if len(messages)>store.config.limits.max_nested_items:fail('Conversation expansion exceeds hard limit.','conversation_limit')
            positions=[m['position'] for m in messages]
            if None in positions or len(set(positions))!=len(positions):violations['ambiguous_order']+=1
            calls={};responses=[]
            for m in messages:
                payload=json.loads(m['payload']);declared=get(payload,c.calls_selector)
                if declared is not MISSING and declared is not None:
                    if not isinstance(declared,list):violations['invalid_tool_calls']+=1
                    else:
                        for call in declared:
                            if not isinstance(call,dict) or lexical(call.get('id')) is None:violations['invalid_call_id']+=1;continue
                            key=call['id']
                            if key in calls:violations['duplicate_call_id']+=1
                            calls.setdefault(key,[]).append(m['position'])
                            function=call.get('function',call)
                            if not isinstance(function,dict) or lexical(function.get('name')) is None:violations['invalid_tool_name']+=1
                            else:
                                args=function.get('arguments',{})
                                if isinstance(args,str):
                                    from datatrust.text_normalization import strict_json,validate_tree
                                    try:args=strict_json(args);validate_tree(args,store.config.limits)
                                    except (ValueError,RecursionError):violations['invalid_tool_arguments']+=1
                                if not isinstance(args,dict):violations['invalid_tool_arguments']+=1
                if m['role']=='tool':responses.append((get(payload,c.call_id_selector),m['position']))
            response_ids=set()
            for key,position in responses:
                if not isinstance(key,str) or key not in calls or len(calls[key])!=1:violations['orphan_or_ambiguous_tool_response']+=1
                elif position is None or calls[key][0] is None or position<=calls[key][0]:violations['response_before_call']+=1
                else:response_ids.add(key)
            if c.require_tool_closure:violations['unclosed_tool_calls']+=len(set(calls)-response_ids)
            if c.require_completion and not (messages and messages[-1]['role']=='assistant' and state(get(json.loads(messages[-1]['payload']),c.content_selector))=='present'):violations['missing_completion']+=1
            if messages and sum(violations.values())>before and len(witnesses)<e.config.limits.witnesses:witnesses.append(messages[0]['mid'])
    roles=store.con.execute('SELECT role,count(*) FROM messages GROUP BY role ORDER BY role').fetchall()
    unknown=con.execute("SELECT count(*) FROM invalid WHERE reason='invalid_message_collection'").fetchone()[0]
    e.add('conversations',{'conversations':conversation_count,'messages':sum(n for _,n in roles),'unknown_message_cardinality_collections':unknown,'role_counts':{role if role in {'system','developer','user','assistant','tool'} else e.opaque('role',role):n for role,n in roles},'violations':dict(violations),'role_alternation_assumed':False,'tools_executed':False},meaning='deterministic_violation',keys=witnesses,violations=sum(violations.values()))


def retrieval(e,store):
    con=store.con;issues=Counter();keys=[];judgments=Counter()
    for item in store.spec.inputs:
        r=item.retrieval
        if not r or r.kind not in {'chunk','judgment','reference'}:continue
        # Join only unique logical identities; missing and ambiguous keys cannot multiply rows.
        con.execute('CREATE OR REPLACE TABLE current_links AS SELECT l.*,t.n tn,t.rid target_rid,q.n qn,q.rid query_rid FROM links l LEFT JOIN identities t ON l.target_sid=t.sid AND l.target_key=t.lid LEFT JOIN identities q ON l.query_sid=q.sid AND l.query_key=q.lid WHERE l.sid=?',[item.id])
        for reason,predicate in [('missing_target','target_key IS NULL'),('unresolved_target','target_key IS NOT NULL AND tn IS NULL'),('ambiguous_target','tn>1')]:
            n=con.execute(f'SELECT count(*) FROM current_links WHERE {predicate}').fetchone()[0];issues[reason]+=n
            if n and len(keys)<e.config.limits.witnesses:keys.extend(x[0] for x in con.execute(f'SELECT rid FROM current_links WHERE {predicate} ORDER BY rid LIMIT ?',[e.config.limits.witnesses-len(keys)]).fetchall())
        if r.kind in {'judgment','reference'}:
            issues['unresolved_or_ambiguous_query']+=con.execute('SELECT count(*) FROM current_links WHERE query_key IS NULL OR qn IS NULL OR qn<>1').fetchone()[0]
        if r.kind=='chunk':
            field=r.field or (item.fields[0].name if item.fields else '')
            parent=next(x for x in store.spec.inputs if x.id==r.parent_source)
            parent_field=r.parent_field or (parent.fields[0].name if parent.fields else '')
            cursor=con.cursor().execute('SELECT l.rid,l.start_value,l.end_value,c.uid,c.text,p.uid,p.text FROM current_links l LEFT JOIN content c ON l.rid=c.rid AND c.field=? LEFT JOIN content p ON l.target_rid=p.rid AND p.field=? WHERE l.tn=1',[field,parent_field])
            while batch:=cursor.fetchmany(512):
                for rid,start,end,uid,text,puid,ptext in batch:
                    if not r.extractive:continue
                    try:
                        if ptext is None or text is None:raise ValueError('content_unavailable')
                        a,b=span_bounds(ptext,json.loads(start) if start else None,json.loads(end) if end else None,r.offset_unit)
                        if ptext[a:b]!=text:raise ValueError('extractive_text_mismatch')
                        # Do not execute on the active cursor connection until the batch is materialized.
                        store.add('intervals',(rid,puid,a,b))
                    except (ValueError,TypeError):
                        issues['invalid_extractive_chunk']+=1
                        if uid and len(keys)<e.config.limits.witnesses:keys.append(uid)
            store.flush()
        else:
            rows=con.execute('SELECT grade,count(*) FROM current_links WHERE tn=1 AND qn=1 GROUP BY grade').fetchall()
            for value,n in rows:
                if value is None:judgments['unknown']+=n
                else:
                    grade=json.loads(value)
                    if grade is None:judgments['unknown']+=n
                    elif isinstance(grade,bool) or not isinstance(grade,(str,int,float)) or isinstance(grade,str) and lexical(grade) is None:issues['invalid_grade']+=n
                    else:judgments['positive' if grade in r.positive_grades else 'other_observed_grade']+=n
            issues['conflicting_judgments']+=con.execute("SELECT count(*) FROM (SELECT target_key,query_key FROM current_links WHERE grade IS NOT NULL AND grade<>'null' GROUP BY target_key,query_key HAVING count(DISTINCT grade)>1)").fetchone()[0]
    covered=0;parents=0
    cursor=con.execute('SELECT parent_uid,start_pos,end_pos FROM intervals ORDER BY parent_uid,start_pos,end_pos');current=None;end=-1
    while batch:=cursor.fetchmany(4096):
        for uid,a,b in batch:
            if uid!=current:parents+=1;current=uid;end=-1
            covered+=max(0,b-max(a,end));end=max(end,b)
    entity_coverage=[]
    for item in store.spec.inputs:
        if not item.retrieval or item.retrieval.kind not in {'document','chunk','query'}:continue
        n=con.execute('SELECT count(*) FROM records WHERE sid=? AND valid',[item.id]).fetchone()[0]
        if item.retrieval.kind=='query':
            linked=con.execute('SELECT count(DISTINCT i.rid) FROM links l JOIN identities i ON l.query_sid=i.sid AND l.query_key=i.lid WHERE i.sid=? AND i.n=1',[item.id]).fetchone()[0]
        else:linked=con.execute('SELECT count(DISTINCT i.rid) FROM links l JOIN identities i ON l.target_sid=i.sid AND l.target_key=i.lid WHERE i.sid=? AND i.n=1',[item.id]).fetchone()[0]
        entity_coverage.append({'source':e.sources[item.id],'kind':item.retrieval.kind,'valid_records':n,'uniquely_referenced_records':linked,'unreferenced_records':max(0,n-linked)})
    parent_bindings={(x.retrieval.parent_source,x.retrieval.parent_field or next(y for y in store.spec.inputs if y.id==x.retrieval.parent_source).fields[0].name) for x in store.spec.inputs if x.retrieval and x.retrieval.kind=='chunk' and x.retrieval.extractive}
    parent_characters=0
    for sid,field in parent_bindings:parent_characters+=con.execute('SELECT coalesce(sum(chars),0) FROM content WHERE sid=? AND field=?',[sid,field]).fetchone()[0]
    e.add('retrieval',{'violations':dict(issues),'judgment_states':dict(judgments),'entity_reference_coverage':entity_coverage,'extractive_parent_count':parents,'covered_source_characters_union':covered,'declared_parent_characters':parent_characters,'extractive_character_coverage':covered/parent_characters if parent_characters else None,'unknown_judgment_is_negative':False,'transformed_chunk_alignment_claimed':False},meaning='deterministic_violation',keys=keys,violations=sum(issues.values()))


def comparisons(e,store):
    from datatrust.distribution_effects import numeric_effect
    con=store.con
    for left,right in store.spec.evaluation.comparisons:
        left_input=next(x for x in store.spec.inputs if x.id==left);right_input=next(x for x in store.spec.inputs if x.id==right)
        fields=con.execute('SELECT DISTINCT a.field FROM content a JOIN content b ON a.field=b.field WHERE a.sid=? AND b.sid=?',[left,right]).fetchall()
        for (name,) in fields:
            con.execute('CREATE OR REPLACE TEMP TABLE cmp_l AS SELECT chars FROM content WHERE sid=? AND field=? AND chars IS NOT NULL',[left,name]);con.execute('CREATE OR REPLACE TEMP TABLE cmp_r AS SELECT chars FROM content WHERE sid=? AND field=? AND chars IS NOT NULL',[right,name])
            n=con.execute('SELECT count(*) FROM cmp_l').fetchone()[0];m=con.execute('SELECT count(*) FROM cmp_r').fetchone()[0]
            if n and m:
                d,w,_=numeric_effect(con,'cmp_l','chars','true','cmp_r','chars','true',n,m,constant_zero=True)
                e.add('comparisons',{'sources':[e.sources[left],e.sources[right]],'field':e.opaque('field',name),'length_cdf_distance':d,'length_wasserstein_characters':w,'populations':[n,m]},meaning='contextual_observation')
            compatible=bool(left_input.id_selector and right_input.id_selector and left_input.namespace and left_input.namespace==right_input.namespace)
            matched=con.execute('SELECT count(*) FROM identities a JOIN identities b ON a.lid=b.lid WHERE a.sid=? AND b.sid=? AND a.n=1 AND b.n=1',[left,right]).fetchone()[0] if compatible else None
            alignment={'sources':[e.sources[left],e.sources[right]],'field':e.opaque('field',name),'unique_lexical_id_matches':matched,'alignment_requires_explicit_id_and_shared_namespace':True}
            if compatible:
                unique=[con.execute('SELECT count(*) FROM identities WHERE sid=? AND n=1',[sid]).fetchone()[0] for sid in (left,right)]
                ambiguous=[con.execute('SELECT count(*) FROM identities WHERE sid=? AND n>1',[sid]).fetchone()[0] for sid in (left,right)]
                changed=con.execute("SELECT count(*) FROM identities a JOIN identities b ON a.lid=b.lid JOIN content x ON a.rid=x.rid AND x.field=? JOIN content y ON b.rid=y.rid AND y.field=? WHERE a.sid=? AND b.sid=? AND a.n=1 AND b.n=1 AND (x.state<>y.state OR x.text IS DISTINCT FROM y.text)",[name,name,left,right]).fetchone()[0]
                alignment.update(unique_identity_populations=unique,unmatched_unique_identities=[x-matched for x in unique],ambiguous_identity_groups=ambiguous,aligned_fields_changed_raw=changed)
            e.add('version_alignment',alignment,meaning='contextual_observation')
