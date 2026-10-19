"""Immutable local snapshots and projected disk relations; no whole-frame loading."""
from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import json
import math
import os
from pathlib import Path
from . import compat
from .contracts import ClockSpec, EvaluationError, OutcomeSnapshotSpec, digest


def scalar(value):
    if value is None:return None
    if hasattr(value,'isoformat'):return value.isoformat()
    return str(value)


def number(value):
    """Reject underflow and integer geometry loss instead of inventing zeros/errors."""
    if value is None or value=='' or len(str(value))>1024:return None
    try:
        d=Decimal(str(value));v=float(d)
        if not math.isfinite(v) or d!=0 and v==0:return None
        if d==d.to_integral_value() and Decimal.from_float(v)!=d:return None
        return v
    except (InvalidOperation,ValueError,OverflowError):return None


def probability(value):
    v=number(value)
    if v is None:return None
    d=Decimal(str(value))
    if not 0<=d<=1:return None
    # Interior decimal values rounding to an endpoint must not manufacture a
    # zero complementary probability or turn an out-of-range value into one.
    if v in (0.,1.) and d!=Decimal.from_float(v):return None
    return v


def key(record,columns,fallback):
    values=[record.get(c) for c in columns]
    if not columns:return fallback
    if any(v is None or v=='' for v in values):return None
    return json.dumps(values,ensure_ascii=True,separators=(',',':'))


def rows(con,sql,args=(),batch=1):
    cursor=con.cursor()
    try:
        cursor.execute(sql,args)
        while True:
            chunk=cursor.fetchmany(batch)
            if not chunk:break
            yield from chunk
    finally:cursor.close()


def records(path,source,config,columns=None):
    if source.format=='csv':
        for loc,record,reason in compat.frames(path,source,config):
            if 'header' in loc:yield loc,None;continue
            if reason:raise EvaluationError('Invalid source framing.','source_structure','ingestion')
            if record is not None:yield loc,record
    else:
        reader,meta=compat.parquet(path)
        try:
            if meta['columns']>config.max_columns:raise EvaluationError('Parquet column limit exceeded.','column_limit')
            yield {'header':reader.schema_arrow.names},None
            ordinal=0
            # Native decoder allocation remains under parent RSS supervision.
            for batch in reader.iter_batches(batch_size=max(1,min(1024,config.batch_bytes//max(1024,len(columns or reader.schema_arrow.names)*128))),columns=sorted(columns) if columns else None,use_threads=False):
                if batch.nbytes>config.batch_bytes*2:raise EvaluationError('Decoded batch exceeds admitted ceiling.','batch_limit')
                for record in batch.to_pylist():
                    ordinal+=1
                    if len(json.dumps({k:scalar(v) for k,v in record.items()}).encode())>config.max_record_bytes:raise EvaluationError('Scalar record exceeds byte limit.','record_limit')
                    yield {'ordinal':ordinal},{k:scalar(v) for k,v in record.items()}
        finally:reader.close()


class Store:
    def __init__(self,work,spec,config,roots):
        self.work,self.con,self.spec,self.config,self.roots=work,work.con,spec,config,roots
        self.sources={};self.tables={};self.headers={};self.counts={};self.snapshots={};self.total=0;self.warnings=[]
        self.outcomes=spec.outcomes
        if not self.outcomes and len(spec.runs)==1 and spec.runs[0].inline_outcome:
            r=spec.runs[0];self.outcomes=OutcomeSnapshotSpec(r.source,r.inline_outcome,r.key_columns)
        self.context=spec.context
        self.cohort_columns=[c.column for c in spec.cohorts]

    def selected(self,sid):
        selected=set()
        def clock(c):
            if c:selected.add(c.column)
        for r in self.spec.runs:
            if r.source!=sid:continue
            selected.update(r.key_columns);selected.update(r.entity_columns)
            selected.update(v for v in (r.prediction,r.decision.column,r.decision.state_column,r.inline_outcome) if v)
            for p in (r.probabilities,r.score,r.selection):
                if p:selected.update(p.columns.values());selected.update(v for v in (getattr(p,'positive_column',None),getattr(p,'column',None)) if v)
            for interval in r.intervals:selected.update((interval.lower,interval.upper))
            clock(r.prediction_at)
            if self.context:
                selected.update(self.context.assertions.get(r.id,{}).values())
        if self.outcomes and self.outcomes.source==sid:
            o=self.outcomes;selected.add(o.column);selected.update(o.key_columns)
            if o.status_column:selected.add(o.status_column)
            for c in (o.available_at,o.due_at,o.target_at):clock(c)
        context_sid=self.context.source if self.context else self.outcomes.source if self.outcomes else None
        if context_sid==sid:
            selected.update(self.cohort_columns);selected.update(self.context.key_columns if self.context else self.outcomes.key_columns)
        return selected

    def ingest(self):
        combined=0
        for i,s in enumerate(self.spec.sources):
            info,_,_=compat.capture(s.path,self.roots,check=lambda:self.work.check('source verification'))
            combined+=info['bytes']
            if info['bytes']>self.config.max_source_bytes or combined>self.config.max_combined_source_bytes:raise EvaluationError('Source bytes exceed admission limits.','source_limit')
            snap=self.work.root/f'cg-source-{i}.{s.format}';self.work.check('snapshot reservation',info['bytes'])
            h=hashlib.sha256()
            with compat.secure_open(s.path,self.roots) as (original,_),snap.open('xb') as output:
                while True:
                    block=original.read(1024**2)
                    if not block:break
                    output.write(block);h.update(block)
            if h.hexdigest()!=info['sha256']:raise EvaluationError('Source changed during capture.','source_changed')
            compat.capture(s.path,self.roots,expected=info)
            self.sources[s.id]=info;self.snapshots[s.id]=snap
            table=f'src{i}';self.tables[s.id]=table;self.con.execute(f'CREATE TABLE {table}(ordinal BIGINT,payload VARCHAR)')
            required=self.selected(s.id);pending=[];pending_bytes=0;n=0
            for loc,record in records(snap,s,self.config,required):
                if record is None:
                    self.headers[s.id]=loc['header']
                    if required-set(loc['header']):raise EvaluationError('Mapped columns are absent; inspect source headers.','missing_columns')
                    continue
                n+=1;self.total+=1
                if n>self.config.max_rows or self.total>self.config.max_combined_rows:raise EvaluationError('Row admission exceeded.','row_limit')
                payload=json.dumps({k:scalar(record.get(k)) for k in sorted(required)},ensure_ascii=True,separators=(',',':'))
                pending.append((loc['ordinal'],payload));pending_bytes+=len(payload)+64
                if pending_bytes>=min(self.config.batch_bytes,1024**2) or len(pending)>=1024:
                    self.con.executemany(f'INSERT INTO {table} VALUES (?,?)',pending);pending=[];pending_bytes=0;self.work.check('projected ingestion')
            if pending:self.con.executemany(f'INSERT INTO {table} VALUES (?,?)',pending)
            self.counts[s.id]=n
            if n==0:raise EvaluationError('Prediction sources require framed records.','empty_source')

    def keyed(self,sid,columns,table):
        self.con.execute(f'CREATE TABLE {table}_raw(ordinal BIGINT,event_key VARCHAR,payload VARCHAR)')
        batch=[];retained=0
        for ordinal,payload in rows(self.con,f'SELECT ordinal,payload FROM {self.tables[sid]}'):
            record=json.loads(payload);batch.append((ordinal,key(record,columns,f'{sid}:{ordinal}'),payload));retained+=len(payload)
            if len(batch)>=512 or retained>=min(self.config.batch_bytes,1024**2):self.con.executemany(f'INSERT INTO {table}_raw VALUES (?,?,?)',batch);batch=[];retained=0;self.work.check('identity normalization')
        if batch:self.con.executemany(f'INSERT INTO {table}_raw VALUES (?,?,?)',batch)
        self.con.execute(f'CREATE TABLE {table} AS SELECT *,count(*) OVER(PARTITION BY event_key) multiplicity FROM {table}_raw')
        self.con.execute(f'DROP TABLE {table}_raw')

    def prepare(self):
        cutoff_spec=ClockSpec('cutoff')
        self.cutoff=compat.clock(self.spec.as_of or datetime.now(timezone.utc).isoformat(),cutoff_spec)[0]
        if self.cutoff is None:raise EvaluationError('Evaluation cutoff requires an unambiguous instant.','invalid_cutoff')
        self.con.execute('CREATE TABLE outcome(event_key VARCHAR,ordinal BIGINT,y VARCHAR,y_num DOUBLE,eligible BOOLEAN,reason VARCHAR,available HUGEINT,due HUGEINT,target HUGEINT)')
        self.outcome_facts={'authority':'none','timing':'unestablished','duplicate_rows':0,'invalid_keys':0}
        if self.outcomes:
            o=self.outcomes
            if any(r.source!=o.source and not (r.key_columns and o.key_columns) for r in self.spec.runs):raise EvaluationError('Cross-source outcomes require explicit keys.')
            self.keyed(o.source,o.key_columns,'okeys')
            self.outcome_facts.update(authority=o.source,duplicate_rows=self.con.execute('SELECT count(*) FROM okeys WHERE multiplicity>1 AND event_key IS NOT NULL').fetchone()[0],invalid_keys=self.con.execute('SELECT count(*) FROM okeys WHERE event_key IS NULL').fetchone()[0])
            pending=[]
            for ordinal,k,payload,n in rows(self.con,'SELECT * FROM okeys'):
                record=json.loads(payload);v=record.get(o.column);yn=number(v) if self.spec.task.kind=='regression' else None
                reason=None if (yn is not None if self.spec.task.kind=='regression' else v in self.spec.task.classes) else 'missing_or_invalid_outcome'
                if k is None:reason='missing_outcome_key'
                if n>1:reason='duplicate_outcome_key'
                if o.status_column and o.status_values.get(record.get(o.status_column)) not in {'observed','final'}:reason='provisional_invalid_or_unresolved_status'
                available,a_state=compat.clock(record.get(o.available_at.column),o.available_at) if o.available_at else (None,'undeclared')
                due,d_state=compat.clock(record.get(o.due_at.column),o.due_at) if o.due_at else (None,'undeclared')
                target,_=compat.clock(record.get(o.target_at.column),o.target_at) if o.target_at else (None,'undeclared')
                if self.spec.as_of and a_state!='valid':reason='unresolved_outcome_availability'
                elif self.spec.as_of and available>self.cutoff:reason='outcome_not_available_as_of'
                if o.due_at and (d_state!='valid' or due>self.cutoff):reason='unresolved_or_immature_outcome'
                retained_value=v if yn is not None or v in self.spec.task.classes else None
                pending.append((k,ordinal,retained_value,yn,reason is None,reason,available,due,target))
                if len(pending)>=512:self.con.executemany('INSERT INTO outcome VALUES (?,?,?,?,?,?,?,?,?)',pending);pending=[]
            if pending:self.con.executemany('INSERT INTO outcome VALUES (?,?,?,?,?,?,?,?,?)',pending)
            # Only unique identities may participate in a join, including invalid values.
            self.con.execute('CREATE TABLE outcome_unique AS SELECT * FROM outcome WHERE event_key IN (SELECT event_key FROM okeys WHERE multiplicity=1 AND event_key IS NOT NULL)')
            h=hashlib.sha256()
            for row in rows(self.con,'SELECT event_key,y,y_num,eligible,reason,available,due,target FROM outcome ORDER BY event_key,y,reason'):
                h.update(json.dumps([scalar(v) for v in row],ensure_ascii=True).encode())
            self.outcome_facts['canonical_content_digest']=h.hexdigest()
            self.outcome_facts['snapshot_digest']=digest({'content':h.hexdigest(),'source_sha256':self.sources[o.source]['sha256'],'task':self.spec.task.to_dict(),'binding':o.to_dict(),'as_of':self.spec.as_of})
            self.outcome_facts['timing']='as_of_qualified' if self.spec.as_of else 'supplied_snapshot_maturity_declared' if o.due_at else 'supplied_snapshot_maturity_unestablished'
            self.outcome_facts['effective_cutoff_ns']=str(self.cutoff)
        else:self.con.execute('CREATE TABLE outcome_unique AS SELECT * FROM outcome')
        cs=self.context.source if self.context else self.outcomes.source if self.outcomes else None
        if cs:
            keys=self.context.key_columns if self.context else self.outcomes.key_columns
            if any(r.source!=cs and not (r.key_columns and keys) for r in self.spec.runs):raise EvaluationError('Cross-source context requires explicit keys.')
            self.keyed(cs,keys,'context_keys')
            self.con.execute('CREATE TABLE context_unique AS SELECT event_key,payload FROM context_keys WHERE event_key IS NOT NULL AND multiplicity=1')
        else:self.con.execute('CREATE TABLE context_unique(event_key VARCHAR,payload VARCHAR)')
        ch=hashlib.sha256()
        for event,payload in rows(self.con,'SELECT event_key,payload FROM context_unique ORDER BY event_key'):
            projected={c.column:json.loads(payload).get(c.column) for c in self.spec.cohorts}
            ch.update(json.dumps([event,projected],sort_keys=True,ensure_ascii=True).encode())
        self.context_facts={'authority':cs,'canonical_content_digest':ch.hexdigest(),'snapshot_digest':digest({'content':ch.hexdigest(),'source_sha256':self.sources[cs]['sha256'] if cs else None,'binding':self.context.to_dict() if self.context else None,'cohorts':[c.to_dict() for c in self.spec.cohorts]}),'membership':'one canonical context for all runs'}
        self.run_tables={};self.run_facts={}
        for i,r in enumerate(self.spec.runs):self.normalize(r,i)

    def group(self,record,c):
        v=record.get(c.column)
        if v is None or v=='':return 'missing'
        if c.categories:
            try:return 'category_'+str(c.categories.index(v))
            except ValueError:return 'other'
        n=number(v)
        if n is None:return 'invalid'
        for i,(lo,hi) in enumerate(zip(c.edges,c.edges[1:])):
            if lo<=n<hi or i==len(c.edges)-2 and n==hi:return 'bin_'+str(i)
        return 'out_of_range'

    def normalize(self,r,index):
        task=self.spec.task;config=self.config;table=f'run{index}';self.run_tables[r.id]=table
        self.keyed(r.source,r.key_columns,f'rkeys{index}')
        cols='ordinal BIGINT,event_key VARCHAR,entity_key VARCHAR,y VARCHAR,y_num DOUBLE,outcome_valid BOOLEAN,outcome_reason VARCHAR,decision VARCHAR,point DOUBLE,state VARCHAR,origin VARCHAR,prob_valid BOOLEAN,probs DOUBLE[],top_label VARCHAR,confidence DOUBLE,ptrue DOUBLE,brier DOUBLE,log_loss DOUBLE,log_infinite BOOLEAN,rank_score DOUBLE,score_valid BOOLEAN,score_max DOUBLE,selector DOUBLE,candidate VARCHAR,prediction_tick HUGEINT'
        cols+=''.join(f',g{i} VARCHAR' for i,_ in enumerate(self.spec.cohorts))+''.join(f',l{i} DOUBLE,u{i} DOUBLE,w{i} DOUBLE' for i,_ in enumerate(r.intervals))
        self.con.execute(f'CREATE TABLE {table}({cols})')
        facts={'records':self.counts[r.source],'duplicate_keys':0,'missing_keys':0,'invalid_probabilities':0,'probability_sum_roundoff':0,'inline_conflicts':0,'inline_comparable':0,'inline_missing':0,'inline_invalid':0,'context_conflicts':{},'decision_rule_mismatches':0,'unresolved_issuance':0,'invalid_intervals':{},'role':r.role}
        query=f'SELECT r.ordinal,r.event_key,r.payload,r.multiplicity,o.y,o.y_num,o.eligible,o.reason,c.payload FROM rkeys{index} r LEFT JOIN outcome_unique o USING(event_key) LEFT JOIN context_unique c USING(event_key)'
        pending=[]
        for ordinal,k,payload,multiplicity,y,yn,eligible,reason,cpayload in rows(self.con,query):
            record=json.loads(payload);context=json.loads(cpayload) if cpayload else {}
            if k is None:facts['missing_keys']+=1;eligible=False;reason='missing_prediction_key'
            if multiplicity>1 and k is not None:facts['duplicate_keys']+=1;eligible=False;reason='duplicate_prediction_key'
            if r.inline_outcome and y is not None:
                copied=record.get(r.inline_outcome)
                facts['inline_comparable']+=1
                if copied in (None,''):facts['inline_missing']+=1
                elif (number(copied) is None if task.kind=='regression' else copied not in task.classes):facts['inline_invalid']+=1
                same=number(copied)==yn if task.kind=='regression' and number(copied) is not None else copied==y
                if copied not in (None,'') and not same:facts['inline_conflicts']+=1
            if self.context:
                for canonical,col in self.context.assertions.get(r.id,{}).items():
                    if record.get(col)!=context.get(canonical):facts['context_conflicts'][canonical]=facts['context_conflicts'].get(canonical,0)+1
            p=None
            if r.probabilities:
                if r.probabilities.positive_column:
                    v=probability(record.get(r.probabilities.positive_column))
                    if v is not None and 0<=v<=1:p=[v if c==task.positive_class else 1-v for c in task.classes]
                else:
                    values=[probability(record.get(r.probabilities.columns[c])) for c in task.classes]
                    if all(v is not None and 0<=v<=1 for v in values) and abs(math.fsum(values)-1)<=config.probability_tolerance:
                        p=values
                        if math.fsum(values)!=1:facts['probability_sum_roundoff']+=1
                if p is None:facts['invalid_probabilities']+=1
            top=None;maxp=max(p) if p else None
            if p:
                winners=[i for i,v in enumerate(p) if v==maxp]
                if len(winners)==1 or r.decision.tie_policy=='class_order':top=task.classes[winners[0]]
            rank=number(record.get(r.score.column)) if r.score and r.score.column else (p[task.classes.index(task.positive_class)] if p and task.kind=='binary_classification' else None)
            score_vector=[number(record.get(r.score.columns[c])) for c in task.classes] if r.score and r.score.columns else None
            score_valid=all(v is not None for v in score_vector) if score_vector else rank is not None if r.score else False
            score_max=max(score_vector) if score_vector and score_valid else rank if score_valid else None
            selector=number(record.get(r.selection.column)) if r.selection else None
            supplied=record.get(r.decision.column or r.prediction) if r.decision.column or r.prediction else None
            candidate=supplied if supplied in task.classes else None
            point=number(supplied) if task.kind=='regression' else None
            derived=None
            if r.decision.rule=='probability_threshold' and p:
                v=p[task.classes.index(task.positive_class)];derived=task.positive_class if v>=r.decision.threshold else next(c for c in task.classes if c!=task.positive_class)
            elif r.decision.rule=='score_threshold' and rank is not None:
                positive=rank>=r.decision.threshold if r.score.direction=='higher' else rank<=r.decision.threshold
                derived=task.positive_class if positive else next(c for c in task.classes if c!=task.positive_class)
            elif r.decision.rule=='probability_argmax':derived=top
            elif r.decision.rule=='score_argmax':
                vector=score_vector
                if all(v is not None for v in vector):
                    best=max(vector);winners=[i for i,v in enumerate(vector) if v==best]
                    if len(winners)==1 or r.decision.tie_policy=='class_order':derived=task.classes[winners[0]]
            origin='supplied' if r.decision.column or r.prediction else 'derived' if r.decision.rule!='none' else 'none'
            decision=candidate if origin=='supplied' else derived
            if origin=='supplied' and r.decision.rule!='none' and candidate!=derived:facts['decision_rule_mismatches']+=1
            if r.decision.state_column:
                state=r.decision.state_values.get(record.get(r.decision.state_column),'unresolved')
                if state=='unresolved':facts['unresolved_issuance']+=1
            elif origin=='supplied':state='issued' if (point is not None if task.kind=='regression' else decision is not None) else 'missing'
            elif origin=='derived':state='hypothetical' if decision is not None else 'abstained'
            else:state='unknown'
            ptrue=p[task.classes.index(y)] if p and y in task.classes else None
            brier=(p[task.classes.index(task.positive_class)]-(y==task.positive_class))**2 if ptrue is not None and task.kind=='binary_classification' else math.fsum((v-(c==y))**2 for c,v in zip(task.classes,p)) if ptrue is not None else None
            tick,_=compat.clock(record.get(r.prediction_at.column),r.prediction_at) if r.prediction_at else (None,'undeclared')
            row=[ordinal,k,key(record,r.entity_columns,None) if r.entity_columns else None,y,yn,bool(eligible),reason or ('no_matched_outcome' if not eligible else None),decision,point,state,origin,p is not None,p,top,p[task.classes.index(decision)] if p and decision in task.classes else None,ptrue,brier,-math.log(ptrue) if ptrue is not None and ptrue>0 else None,ptrue==0 if ptrue is not None else False,rank,score_valid,score_max,selector,candidate,tick]
            row.extend(self.group(context,c) if cpayload else 'unresolved' for c in self.spec.cohorts)
            for j,interval in enumerate(r.intervals):
                lo,hi=number(record.get(interval.lower)),number(record.get(interval.upper));width=hi-lo if lo is not None and hi is not None else None
                if width is None or not math.isfinite(width) or width<0:
                    facts['invalid_intervals'][interval.id]=facts['invalid_intervals'].get(interval.id,0)+1;lo=hi=width=None
                row.extend((lo,hi,width))
            pending.append(tuple(row))
            if len(pending)>=512:self.con.executemany(f'INSERT INTO {table} VALUES ({",".join("?" for _ in row)})',pending);pending=[];self.work.check('prediction normalization')
        if pending:self.con.executemany(f'INSERT INTO {table} VALUES ({",".join("?" for _ in pending[0])})',pending)
        facts['repeated_entities']=self.con.execute(f'SELECT coalesce(sum(n),0) FROM (SELECT count(*) n FROM {table} WHERE entity_key IS NOT NULL GROUP BY entity_key HAVING count(*)>1)').fetchone()[0]
        self.run_facts[r.id]=facts

    def verify(self):
        for info in self.sources.values():compat.capture(info['path'],self.roots,expected=info,check=lambda:self.work.check('final source verification'))
