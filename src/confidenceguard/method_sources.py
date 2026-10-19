"""CG2 projections extend the existing Store; identity/outcome normalization is shared."""
from dataclasses import replace
from decimal import Decimal
import hashlib
import json
import math
import numpy as np
from .sources import Store, rows, number, key
from .contracts import EvaluationError, digest
from .analytics import literal
from .method_contracts import CONFORMAL


class MethodStore(Store):
    def __init__(self,work,spec,config,roots,extension):
        self.extension=extension
        self.representations={r.run:r for r in extension.representations}
        super().__init__(work,spec,config,roots)

    def selected(self,sid):
        selected=super().selected(sid)
        canonical=self.spec.context.source if self.spec.context else self.spec.outcomes.source if self.spec.outcomes else None
        if self.extension.roles.column and sid==canonical: selected.add(self.extension.roles.column)
        if self.extension.roles.column and canonical is None and sid in {r.source for r in self.spec.runs}:selected.add(self.extension.roles.column)
        for partition in (*self.extension.roles.partitions,*self.extension.separation.training_partitions):
            if partition.source==sid: selected.update(partition.key_columns)
        for rep in self.extension.representations:
            run=next(r for r in self.spec.runs if r.id==rep.run)
            if run.source==sid:
                selected.update(rep.logits.values())
                selected.update(v for v in (rep.binary_logit,rep.scale) if v)
                selected.update(q.column for q in rep.quantiles)
            if rep.samples and rep.samples.source==sid:
                selected.update((*rep.samples.key_columns,rep.samples.draw_column,rep.samples.value_column))
        return selected

    def prepare(self):
        super().prepare()
        self.role_facts={}; self.membership_digests={}; self.input_facts={}; self.method_populations={}
        for run in self.spec.runs:
            self.extras(run); self.roles(run)
        # Multiple base models must refer to exactly one canonical event role/entity.
        if len(self.spec.runs)>1:
            a,b=[self.run_tables[r.id] for r in self.spec.runs]
            bad=self.con.execute(f'SELECT count(*) FROM {a} a JOIN {b} b USING(event_key) WHERE a.cg_role IS DISTINCT FROM b.cg_role OR a.entity_key IS DISTINCT FROM b.entity_key').fetchone()[0]
            if bad: raise EvaluationError('Shared event role/entity assertions disagree.','role_conflict')

    def extras(self,run):
        rep=self.representations.get(run.id); table=self.run_tables[run.id]
        self.con.execute(f'ALTER TABLE {table} ADD COLUMN logits DOUBLE[]')
        self.con.execute(f'ALTER TABLE {table} ADD COLUMN scale DOUBLE')
        self.con.execute(f'ALTER TABLE {table} ADD COLUMN quantiles DOUBLE[]')
        self.con.execute(f'ALTER TABLE {table} ADD COLUMN sample_count BIGINT')
        self.con.execute(f'ALTER TABLE {table} ADD COLUMN sample_valid BOOLEAN DEFAULT false')
        self.con.execute(f'ALTER TABLE {table} ADD COLUMN cg_role VARCHAR')
        self.con.execute(f'ALTER TABLE {table} ADD COLUMN input_identity_valid BOOLEAN DEFAULT false')
        self.con.execute(f'ALTER TABLE {table} ADD COLUMN cg_log_probs DOUBLE[]')
        self.con.execute(f'ALTER TABLE {table} ADD COLUMN cg_failure VARCHAR')
        self.con.execute(f'ALTER TABLE {table} ADD COLUMN cg_input_valid BOOLEAN DEFAULT false')
        self.con.execute(f'CREATE TEMP TABLE extras(ordinal BIGINT,logits DOUBLE[],scale DOUBLE,quantiles DOUBLE[])')
        batch=[]; classes=self.spec.task.classes
        for ordinal,payload in rows(self.con,f'SELECT ordinal,payload FROM {self.tables[run.source]}',batch=512):
            record=json.loads(payload); logits=None; scale=None; quantiles=None
            if rep:
                if rep.logits:
                    logits=[number(record.get(rep.logits[c])) for c in classes]
                    if any(v is None for v in logits): logits=None
                elif rep.binary_logit:
                    v=number(record.get(rep.binary_logit))
                    if v is not None: logits=[v if c==self.spec.task.positive_class else 0. for c in classes]
                if rep.scale:
                    v=number(record.get(rep.scale)); scale=v if v is not None and v>0 else None
                if rep.quantiles:
                    quantiles=[number(record.get(q.column)) for q in rep.quantiles]
                    if any(v is None for v in quantiles) or any(a>b for a,b in zip(quantiles,quantiles[1:])): quantiles=None
            batch.append((ordinal,logits,scale,quantiles))
            if len(batch)>=512:
                self.con.executemany('INSERT INTO extras VALUES (?,?,?,?)',batch); batch=[]; self.work.check('CG2 representation normalization')
        if batch:self.con.executemany('INSERT INTO extras VALUES (?,?,?,?)',batch)
        self.con.execute(f'UPDATE {table} r SET logits=e.logits,scale=e.scale,quantiles=e.quantiles FROM extras e WHERE r.ordinal=e.ordinal')
        self.con.execute('DROP TABLE extras')
        self.con.execute(f'UPDATE {table} SET input_identity_valid=event_key IS NOT NULL AND event_key IN (SELECT event_key FROM {table} GROUP BY event_key HAVING count(*)=1)')
        if rep and rep.samples:self.samples(run,rep.samples)

    def samples(self,run,spec):
        table='samples_'+str(list(self.run_tables).index(run.id))
        self.con.execute(f'CREATE TABLE {table}(event_key VARCHAR,draw VARCHAR,value DOUBLE)')
        batch=[]; cells=0
        for ordinal,payload in rows(self.con,f'SELECT ordinal,payload FROM {self.tables[spec.source]}',batch=512):
            record=json.loads(payload); event=key(record,spec.key_columns,None)
            draw=record.get(spec.draw_column); value=number(record.get(spec.value_column))
            batch.append((event,draw if draw else None,value)); cells+=1
            if cells>self.extension.limits.sample_cells: raise EvaluationError('Predictive sample cell admission exceeded.','sample_limit')
            if len(batch)>=512:
                self.con.executemany(f'INSERT INTO {table} VALUES (?,?,?)',batch); batch=[]; self.work.check('predictive sample projection')
        if batch:self.con.executemany(f'INSERT INTO {table} VALUES (?,?,?)',batch)
        self.con.execute(f'CREATE TABLE {table}_groups AS SELECT event_key,count(*) n,count(*)=count(DISTINCT draw) AND count(value)=count(*) AND count(draw)=count(*) AS sample_admitted FROM {table} GROUP BY event_key')
        rt=self.run_tables[run.id]
        self.con.execute(f'UPDATE {rt} r SET sample_count=s.n,sample_valid=s.sample_admitted FROM {table}_groups s WHERE r.event_key=s.event_key')
        self.input_facts[run.id]={'sample_cells':cells,'sample_table':table,'sample_meaning':spec.meaning}

    def roles(self,run):
        spec=self.extension.roles; table=self.run_tables[run.id]
        self.con.execute('CREATE TEMP TABLE role_rows(ordinal BIGINT,event_key VARCHAR,role VARCHAR)')
        if spec.partitions:
            for p in spec.partitions:
                batch=[]
                for _,payload in rows(self.con,f'SELECT ordinal,payload FROM {self.tables[p.source]}',batch=512):
                    event=key(json.loads(payload),p.key_columns,None); batch.append((None,event,p.role))
                    if len(batch)>=512:self.con.executemany('INSERT INTO role_rows VALUES (?,?,?)',batch);batch=[];self.work.check('role partition keys')
                if batch:self.con.executemany('INSERT INTO role_rows VALUES (?,?,?)',batch)
        else:
            query=f'SELECT r.ordinal,r.event_key,r.entity_key,c.payload FROM {table} r LEFT JOIN context_unique c USING(event_key)'
            canonical=self.spec.context.source if self.spec.context else self.spec.outcomes.source if self.spec.outcomes else None
            if spec.column and (canonical is None or canonical==run.source):
                query=f'SELECT r.ordinal,r.event_key,r.entity_key,c.payload FROM {table} r JOIN {self.tables[run.source]} c USING(ordinal)'
            batch=[]
            for ordinal,event,entity,payload in rows(self.con,query,batch=512):
                role=None
                if spec.column: role=spec.values.get(json.loads(payload).get(spec.column)) if payload else None
                else:
                    unit=entity if spec.unit=='entity' else event
                    certain=[r for r,p in spec.proportions.items() if p==1]
                    if certain:role=certain[0]
                    elif unit is not None:
                        token=int(hashlib.sha256(json.dumps([spec.namespace,spec.seed,unit],separators=(',',':')).encode()).hexdigest(),16)/2**256
                        cumulative=0.
                        for r in ('F','S','C','E'):
                            cumulative+=spec.proportions.get(r,0)
                            if token<cumulative:role=r;break
                batch.append((ordinal,event,role))
                if len(batch)>=512:self.con.executemany('INSERT INTO role_rows VALUES (?,?,?)',batch);batch=[];self.work.check('role normalization')
            if batch:self.con.executemany('INSERT INTO role_rows VALUES (?,?,?)',batch)
        conflicts=self.con.execute('SELECT count(*) FROM (SELECT event_key FROM role_rows WHERE event_key IS NOT NULL GROUP BY event_key HAVING count(DISTINCT role)>1)').fetchone()[0]
        if conflicts:raise EvaluationError('One event occurs in prohibited multiple roles.','role_overlap')
        if spec.partitions:self.con.execute(f'UPDATE {table} r SET cg_role=p.cg_assignment FROM (SELECT event_key,min(role) AS cg_assignment FROM role_rows GROUP BY event_key) p WHERE r.event_key=p.event_key')
        else:self.con.execute(f'UPDATE {table} r SET cg_role=p.role FROM role_rows p WHERE r.ordinal=p.ordinal')
        self.con.execute('DROP TABLE role_rows')
        if spec.unit=='entity':
            missing=self.con.execute(f'SELECT count(*) FROM {table} WHERE entity_key IS NULL AND cg_role IS NOT NULL').fetchone()[0]
            overlaps=self.con.execute(f'SELECT count(*) FROM (SELECT entity_key FROM {table} WHERE entity_key IS NOT NULL GROUP BY 1 HAVING count(DISTINCT cg_role)>1)').fetchone()[0]
            if missing or overlaps:raise EvaluationError('Entity separation is missing or violated.','entity_role_overlap')
        entity_role_overlap=self.con.execute(f'SELECT count(*) FROM (SELECT entity_key FROM {table} WHERE entity_key IS NOT NULL GROUP BY 1 HAVING count(DISTINCT cg_role)>1)').fetchone()[0]
        # Training membership is checked against all post-training roles; no label values needed.
        training=[]
        if self.extension.separation.training_partitions:self.con.execute('CREATE TABLE IF NOT EXISTS cg_training(event_key VARCHAR)')
        for p in self.extension.separation.training_partitions:
            for _,payload in rows(self.con,f'SELECT ordinal,payload FROM {self.tables[p.source]}',batch=512):
                event=key(json.loads(payload),p.key_columns,None)
                if event is None:raise EvaluationError('Training membership contains an invalid event key.','invalid_training_membership')
                training.append((event,))
                if len(training)>=512:
                    self._training_keys(training);training=[]
        if training:self._training_keys(training)
        if self.extension.separation.training_partitions:
            overlaps=self.con.execute(f'SELECT count(*) FROM {table} WHERE cg_role IS NOT NULL AND event_key IN (SELECT event_key FROM cg_training)').fetchone()[0]
            if overlaps:raise EvaluationError('Declared training and post-training events overlap.','training_role_overlap')
        counts=dict(self.con.execute(f'SELECT coalesce(cg_role,\'unassigned\'),count(*) FROM {table} GROUP BY 1').fetchall())
        self.role_facts[run.id]={'counts':counts,'namespace':spec.namespace,'unit':spec.unit,'training_membership_checked':bool(self.extension.separation.training_partitions),'cross_role_entity_overlap':entity_role_overlap}
        for role in ('F','S','C','E'):
            h=hashlib.sha256()
            for event,entity in rows(self.con,f'SELECT event_key,entity_key FROM {table} WHERE cg_role=? ORDER BY event_key',[role],batch=512):h.update(json.dumps([spec.namespace,event,entity],separators=(',',':')).encode())
            self.membership_digests[(run.id,role)]=h.hexdigest()

    def _training_keys(self,batch):
        self.con.execute('CREATE TABLE IF NOT EXISTS cg_training(event_key VARCHAR)')
        self.con.executemany('INSERT INTO cg_training VALUES (?)',batch);self.work.check('training membership check')

    def seal_evaluation_labels(self):
        """Training services never see E labels in their normalized run relations."""
        self.sealed_labels={}
        for i,run in enumerate(self.spec.runs):
            table=self.run_tables[run.id]; hidden=f'cg_evaluation_labels_{i}'
            self.con.execute(f'CREATE TABLE {hidden} AS SELECT event_key,y,y_num,outcome_valid,outcome_reason FROM {table} WHERE cg_role=\'E\'')
            self.sealed_labels[run.id]=hidden
            self.con.execute(f'UPDATE {table} SET y=NULL,y_num=NULL,outcome_valid=false,outcome_reason=\'sealed_evaluation\',ptrue=NULL,brier=NULL,log_loss=NULL,log_infinite=false WHERE cg_role=\'E\'')

    def unseal_evaluation_labels(self,roots):
        for rid,table in self.run_tables.items():
            root=roots.get(rid,rid); hidden=self.sealed_labels[root]
            self.con.execute(f'UPDATE {table} r SET y=e.y,y_num=e.y_num,outcome_valid=e.outcome_valid,outcome_reason=e.outcome_reason FROM {hidden} e WHERE r.event_key=e.event_key AND r.cg_role=\'E\'')
            self.refresh_losses(table)

    def refresh_losses(self,table):
        classes=self.spec.task.classes
        if not classes:return
        # Log probabilities from fitted maps distinguish numerical underflow from true zero.
        for i,c in enumerate(classes):
            condition=f'y={literal(c)} AND prob_valid'
            self.con.execute(f'UPDATE {table} SET ptrue=probs[?],log_infinite=CASE WHEN cg_log_probs IS NOT NULL THEN cg_log_probs[?]=\'-inf\'::DOUBLE ELSE probs[?]=0 END,log_loss=CASE WHEN cg_log_probs IS NOT NULL THEN CASE WHEN isfinite(cg_log_probs[?]) THEN -cg_log_probs[?] ELSE NULL END ELSE CASE WHEN probs[?]>0 THEN -ln(probs[?]) ELSE NULL END END WHERE {condition}',[i+1]*7)
        if self.spec.task.kind=='binary_classification':
            i=classes.index(self.spec.task.positive_class)+1
            self.con.execute(f'UPDATE {table} SET brier=pow(probs[{i}]-CASE WHEN y={literal(self.spec.task.positive_class)} THEN 1 ELSE 0 END,2) WHERE prob_valid AND y IS NOT NULL')
        else:
            terms='+'.join(f'pow(probs[{i+1}]-CASE WHEN y={literal(c)} THEN 1 ELSE 0 END,2)' for i,c in enumerate(classes))
            self.con.execute(f'UPDATE {table} SET brier={terms} WHERE prob_valid AND y IS NOT NULL')

    def input_expression(self,method,parent_table=None):
        table=parent_table or self.run_tables[method.run]
        if method.kind in {'split','normalized'}: expression='point IS NOT NULL'+(' AND scale IS NOT NULL' if method.kind=='normalized' else '')
        elif method.kind=='cqr': expression='quantiles IS NOT NULL'
        elif method.input=='logits': expression='logits IS NOT NULL'
        elif method.input=='score': expression='rank_score IS NOT NULL'
        else:expression='prob_valid'
        return table,expression

    def signature(self,method):
        rep=self.representations.get(method.run)
        return {'input':method.input,'scale_model':rep.scale_model if rep and method.kind=='normalized' else None,
                'normalization_version':'cg1_probability_v1','probability_tolerance':self.config.probability_tolerance,
                'quantile_model':rep.quantile_model if rep and method.kind=='cqr' else None,
                'quantile_levels':[q.level for q in rep.quantiles] if rep and method.kind=='cqr' else [],
                'lower_quantile':method.lower_quantile if method.kind=='cqr' else None,
                'upper_quantile':method.upper_quantile if method.kind=='cqr' else None,
                'score_direction':next(r.score.direction for r in self.spec.runs if r.id==method.run) if method.input=='score' and next(r for r in self.spec.runs if r.id==method.run).score else None}

    def batches(self,method,table,where,*,labels=True):
        """Yield bounded matrices from a role-restricted relation, never whole frames."""
        task=self.spec.task
        if method.input=='score':column='rank_score'
        elif method.input=='logits':column='logits'
        else:column='probs'
        query=f'SELECT {column},y FROM {table} WHERE {where} ORDER BY event_key'
        chunk=[]; ys=[]
        for value,y in rows(self.con,query,batch=512):
            if method.input=='score':
                run=next(r for r in self.spec.runs if r.id==method.run); value=[value*(-1 if run.score and run.score.direction=='lower' else 1)]
            chunk.append(value);ys.append(task.classes.index(y) if labels else 0)
            if len(chunk)>=512:
                yield np.asarray(chunk,dtype=float),np.asarray(ys,dtype=int);chunk=[];ys=[];self.work.check('fit input batch')
        if chunk:yield np.asarray(chunk,dtype=float),np.asarray(ys,dtype=int)
