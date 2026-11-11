"""Two-stage historical capture: pre-eligibility facts and frozen outputs.

Nothing in this module supplies archived labels to a fitting query. Capture is
opt-in and its descriptor is created only by the parent workspace service.
"""
from dataclasses import dataclass
import json
from pathlib import Path
from .contracts import digest, EvaluationError, ClockSpec
from .history_contracts import PredictionBatchSpec, OutcomeRevisionSpec
from .history_storage import EvidenceWriter, encode_numbers
from .sources import rows, key
from . import compat


def values(record, columns):
    result = [record.get(c) for c in columns]
    return result if result and all(v is not None and v != '' for v in result) else None


def clock_value(record, clock):
    if clock is None:
        return {'tick': None, 'state': 'undeclared'}
    tick, state = compat.clock(record.get(clock.column), clock)
    return {'tick': str(tick) if tick is not None else None, 'state': state}


def target_identity(namespace, event, definition, target):
    return [namespace, event, definition, target]


def variant_identity(run, task, representation=None, methods=(), policies=()):
    from .fitted import model_identity, task_identity
    signature = {'model': model_identity(run.model), 'task': task_identity(task),
                 'probabilities': bool(run.probabilities),
                 'score': {'direction': run.score.direction, 'meaning': run.score.meaning, 'vector': bool(run.score.columns)} if run.score else None,
                 'decision': {k: v for k, v in run.decision.to_dict().items() if k not in {'column', 'state_column', 'state_values'}},
                 'supplied_decision': bool(run.prediction or run.decision.column),
                 'intervals': [{k: v for k, v in x.to_dict().items() if k not in {'id', 'lower', 'upper'}} for x in run.intervals],
                 'methods': list(methods), 'policies': list(policies),
                 'representation': {k: v for k, v in (representation or {}).items() if k in {'scale_model', 'quantile_model'}},
                 'quantile_levels': [q['level'] for q in (representation or {}).get('quantiles', [])],
                 'sample_meaning': ((representation or {}).get('samples') or {}).get('meaning')}
    return 'variant_' + digest(signature), signature


@dataclass(frozen=True)
class CaptureDescriptor:
    directory: str
    operation_id: str
    workspace_config: dict
    batch: dict
    inputs: dict | None = None


def batch_projection(batch):
    """Fixed historical projections, shared by admission and actual capture."""
    projection={source.id:set() for source in batch.base.sources}
    bindings={b.run:b for b in batch.bindings}
    for run in batch.base.runs:
        binding=bindings[run.id];columns=projection[run.source]
        for attr in ('event_columns','opportunity_columns','target_columns'):columns.update(getattr(binding,attr))
        columns.update(binding.features)
        columns.update(v for v in (binding.attempt_column,binding.slot_column,binding.revision_column,binding.predecessor_column,binding.correction_reason_column) if v)
        for clock in (binding.opportunity_at,binding.information_cutoff,binding.available_at):
            if clock:columns.add(clock.column)
        if batch.base.context:projection[batch.base.context.source].update(binding.features)
    if batch.feature_views:
        from .features import feature_projection
        from types import SimpleNamespace
        extra=feature_projection(SimpleNamespace(features=batch.feature_views,objectives=(SimpleNamespace(run=batch.base.runs[0].id),),roles=SimpleNamespace(column=None)),batch.base)
        for sid,columns in extra.items():projection[sid].update(columns)
    return projection


def capture_inputs_worker(batch,config,roots,*,progress=None):
    """Bind external bytes and observable exposure identities without fitting."""
    from .engine import open_store
    from .result import Inspection
    from .representations import verified_encoder
    from .investigation_history import cells_from_row
    batch=PredictionBatchSpec.from_dict(batch);work=None
    try:
        extension=batch.evaluation if hasattr(batch.evaluation,'evaluation') else None
        work,store,_=open_store(batch.base,config,roots,progress,extension=extension,projection=batch_projection(batch))
        external={};events=set();units=set();bindings={b.run:b for b in batch.bindings}
        for spec in batch.discovery_representations:
            if spec.kind=='supplied':
                external[spec.id+':matrix']=compat.capture(spec.matrix_path,roots)[0]
                external[spec.id+':keys']=compat.capture(spec.keys_source.path,roots)[0]
            else:
                provenance=verified_encoder(spec,roots,work)
                external[spec.id+':manifest']=provenance['manifest']
                for filename,info in provenance['files'].items():external[spec.id+':model:'+filename]=info
                if spec.kind=='dinov2_image':
                    view_id,field_id=spec.field.split('.',1)
                    view=next((v for v in batch.feature_views if v.id==view_id),None)
                    if view is None:raise EvaluationError('Encoder field is absent from retained features.','feature_not_retained')
                    base=next(r for r in batch.base.runs if r.id==(view.run or batch.base.runs[0].id))
                    for _,payload in rows(store.con,f'SELECT ordinal,payload FROM {store.tables[view.source or base.source]}',batch=512):
                        cell=cells_from_row(view,json.loads(payload))[field_id]
                        if cell['state']!='observed':continue
                        path=Path(cell['lexical']);path=path if path.is_absolute() else Path(batch.base.sources[0].path).parent/path
                        info=compat.capture(path,roots,max_bytes=config.max_record_bytes)[0]
                        external[spec.id+':asset:'+digest(str(path))]=info;work.check('capture asset identities')
        if batch.operation!='ingest':
            for run in batch.base.runs:
                binding=bindings[run.id];table=store.run_tables[run.id]
                columns={r[0] for r in store.con.execute(f'DESCRIBE {table}').fetchall()}
                where=" AND r.cg_role IN ('F','S','C')" if batch.operation=='fit' and 'cg_role' in columns else ''
                query=f'SELECT r.event_key,r.entity_key,s.payload FROM {table} r JOIN {store.tables[run.source]} s USING(ordinal) WHERE r.event_key IS NOT NULL'+where
                for event,entity,payload in rows(store.con,query,batch=512):
                    raw=json.loads(payload);identity=values(raw,binding.event_columns or run.key_columns)
                    opportunity=values(raw,binding.opportunity_columns or run.key_columns)
                    target=values(raw,binding.target_columns) if binding.target_columns else [binding.target_instance]
                    events.add(digest([batch.namespace,event]));units.add(digest([batch.namespace,entity or event]))
                    from .evidence_use import source_aliases
                    for source in (run.source,batch.base.outcomes.source if batch.base.outcomes else run.source):
                        ee,uu=source_aliases(store.sources[source],event,entity);events.update(ee);units.update(uu)
                    if identity is not None and opportunity is not None and target is not None:
                        opp=digest([target_identity(batch.namespace,identity,batch.outcome_definition_version,target),opportunity])
                        events.add(digest([batch.namespace,opp]));units.add(digest([batch.namespace,opp]))
                    if entity is not None and binding.entity_namespace:
                        namespaced=json.dumps([binding.entity_namespace,entity],ensure_ascii=True,separators=(',',':'))
                        units.add(digest([batch.namespace,namespaced]))
                    if (len(events)+len(units))*192>config.max_rss_bytes//8:raise EvaluationError('Capture exposure identities exceed explicit memory admission.','evidence_use_capacity')
        for info in external.values():compat.capture(info['path'],roots,expected=info)
        store.verify()
        return Inspection({'sources':store.sources,'external':external,'events':sorted(events),'units':sorted(units)},
                          {'status':'completed','peak_workspace_bytes':work.peak})
    finally:
        if work:work.close()


class Capture:
    def __init__(self, descriptor, store):
        self.descriptor = descriptor
        self.batch = PredictionBatchSpec.from_dict(descriptor.batch)
        self.bindings = {b.run: b for b in self.batch.bindings}
        self.writer = EvidenceWriter(descriptor.directory, descriptor.workspace_config, descriptor.operation_id, store.work.check)
        self.metadata = {'batch': self.batch.to_dict(), 'variants': {}, 'capture_stages': ['before_prepare'],
                         'identity_qualification': 'Supplied explicit namespace/keys; hashes are identifiers, not anonymization.'}

    def extend_projection(self, store):
        store.add_projection(batch_projection(self.batch))

    def raw(self, store):
        """Called immediately after ingest and before prepare, including invalid facts."""
        if self.descriptor.inputs is not None:
            expected=self.descriptor.inputs['sources']
            if {k:v['sha256'] for k,v in expected.items()}!={k:v['sha256'] for k,v in store.sources.items()}:raise EvaluationError('Sources changed after capture admission.','source_changed')
        self.metadata['sources'] = store.sources
        self.metadata['headers'] = store.headers
        self.metadata['counts'] = store.counts
        self.metadata['source_interpretations']={}
        for source in store.spec.sources:
            interpretation={'format':source.format,'encoding':source.encoding,'delimiter':source.delimiter,'projection':sorted(store.selected(source.id))}
            if source.format=='parquet':
                reader,_=compat.parquet(store.snapshots[source.id])
                try:interpretation['native_types']={field.name:str(field.type) for field in reader.schema_arrow if field.name in store.selected(source.id)}
                finally:reader.close()
            self.metadata['source_interpretations'][source.id]=interpretation
        self.metadata['config'] = store.config.to_dict()
        for source in store.spec.sources:
            columns = sorted(store.selected(source.id))
            projection = digest({'sha256': store.sources[source.id]['sha256'], 'columns': columns,
                                 'interpretation': {k: v for k, v in source.to_dict().items() if k not in {'path', 'id'}}})
            for ordinal, payload in rows(store.con, f'SELECT ordinal,payload FROM {store.tables[source.id]}', batch=512):
                self.writer.add('raw', [projection, ordinal], {'record': json.loads(payload), 'ordinal': ordinal,
                                'projection': projection, 'source_sha256': store.sources[source.id]['sha256']})
        self._outcomes(store)

    def _outcomes(self, store):
        outcome = store.outcomes
        if not outcome:
            return
        # Initial snapshots use their declared outcome keys as event keys. More
        # complex target layouts use the explicit outcome-revision importer.
        b = next(iter(self.bindings.values()))
        for ordinal, payload in rows(store.con, f'SELECT ordinal,payload FROM {store.tables[outcome.source]}', batch=512):
            record = json.loads(payload); event = values(record, outcome.key_columns)
            if event is None:
                continue  # The original invalid row is retained in Stage A raw.
            target = values(record, b.target_columns) if b.target_columns else [b.target_instance]
            if target is None: continue
            identity = target_identity(self.batch.namespace, event, self.batch.outcome_definition_version, target)
            status = outcome.status_values.get(record.get(outcome.status_column), 'unresolved') if outcome.status_column else 'observed'
            data = {'value': record.get(outcome.column), 'status': status, 'order': '0',
                    'available': clock_value(record, outcome.available_at), 'due': clock_value(record, outcome.due_at),
                    'target_at': clock_value(record, outcome.target_at), 'history_complete': self.batch.history_complete,
                    'outcome_definition_version': self.batch.outcome_definition_version, 'namespace': self.batch.namespace}
            self.writer.add('outcome', identity, data, authority=self.batch.authority,
                            available_ns=data['available']['tick'])

    def outputs(self, store, *, fitted=None, uncertainties=None, runs=None, membership=None, calibration_edges=None):
        fitted = fitted or {}; uncertainties = uncertainties or {}; runs = runs or store.spec.runs
        roots = {key: method['definition']['run'] for key, method in fitted.items()}
        base_runs = {r.id: r for r in self.batch.base.runs}
        self.metadata['fitted_methods'] = list(fitted.values())
        self.metadata['membership_sidecars'] = membership or []
        self.metadata['calibration_edges'] = calibration_edges or []
        self.metadata['capture_stages'].append('frozen_outputs_before_E_projection')
        context_columns = {c.column for c in self.batch.base.cohorts} | {column for binding in self.bindings.values() for column in binding.features}
        for run in runs:
            root_id = roots.get(run.id, run.id); base = base_runs[root_id]; binding = self.bindings[root_id]
            representation = getattr(store, 'representations', {}).get(root_id)
            rep = representation.to_dict() if representation else {}
            chain = []; current = run.id
            while current in fitted:
                method = fitted[current]; chain.insert(0, method['artifact_digest']); current = method['definition'].get('parent')
            policies = [{k: v for k, v in p.to_dict().items() if k not in {'id', 'run'}} for p in self.batch.base.policies if p.run == root_id]
            vid, signature = variant_identity(run, store.spec.task, rep, chain, ())
            columns = [(r[0], r[1]) for r in store.con.execute(f'DESCRIBE {store.run_tables[run.id]}').fetchall()]
            retained = [(c, t) for c, t in columns if c not in {'ordinal', 'event_key', 'y', 'y_num', 'outcome_valid', 'outcome_reason', 'ptrue', 'brier', 'log_loss', 'log_infinite', 'input_identity_valid'} and not (c.startswith('g') and c[1:].isdigit())]
            meta = {'id': vid, 'signature': signature, 'run': run.to_dict(), 'task': store.spec.task.to_dict(),
                    'namespace': self.batch.namespace, 'outcome_definition_version': self.batch.outcome_definition_version,
                    'authority': self.batch.authority, 'normalized_columns': retained,
                    'representation': rep, 'has_cg2': bool(getattr(store, 'extension', None)),
                    'method_digests': chain, 'probability_tolerance': store.config.probability_tolerance,
                    'features': binding.features,'replay_policies':policies, 'base_model_identity_declared_only': not bool(run.model.artifact_sha256)}
            # File paths and source/run aliases do not define variant mathematics.
            meta['run']['source'] = 'historical'; meta['run']['id'] = vid
            self.metadata['variants'][vid] = meta
            table = store.run_tables[run.id]
            selection = ','.join('r."' + c.replace('"', '""') + '"' for c, _ in columns)
            uncertainty_join = ''; uncertainty_column = 'NULL::VARCHAR'
            if run.id in uncertainties:
                uncertainty_join = f" LEFT JOIN (SELECT ordinal,to_json(list(struct_pack(coverage:=coverage,output:=output) ORDER BY coverage)) u FROM {uncertainties[run.id]} GROUP BY ordinal) uncertainty USING(ordinal) "
                uncertainty_column = 'uncertainty.u'
            mapping = 'capture_map_' + digest(run.id)[:12]
            store.con.execute(f'CREATE TABLE {mapping}(event_key VARCHAR,opportunity_key VARCHAR,prediction_key VARCHAR,prediction_revision VARCHAR)')
            map_batch = []
            query = f'SELECT {selection},src.payload,ctx.payload,{uncertainty_column} FROM {table} r JOIN {store.tables[base.source]} src USING(ordinal) LEFT JOIN context_unique ctx USING(event_key) {uncertainty_join} ORDER BY r.ordinal'
            for row in rows(store.con, query, batch=512):
                normalized = dict(zip((c for c, _ in columns), row[:-3])); ordinal = normalized['ordinal']
                raw = json.loads(row[-3])
                if normalized.get('entity_key') is not None and binding.entity_namespace is not None:normalized['entity_key']=json.dumps([binding.entity_namespace,normalized['entity_key']],ensure_ascii=True,separators=(',',':'))
                event = values(raw, binding.event_columns or base.key_columns)
                opportunity = values(raw, binding.opportunity_columns or base.key_columns)
                target = values(raw, binding.target_columns) if binding.target_columns else [binding.target_instance]
                if event is None or opportunity is None or target is None:
                    continue
                tid = target_identity(self.batch.namespace, event, self.batch.outcome_definition_version, target)
                opp_identity = [tid, opportunity]; opp_key = digest(opp_identity)
                opportunity_time = clock_value(raw, binding.opportunity_at or base.prediction_at)
                information = clock_value(raw, binding.information_cutoff or base.prediction_at)
                self.writer.add('opportunity', opp_identity, {'namespace': self.batch.namespace, 'target_key': digest(tid),
                    'event': event, 'target': target, 'opportunity': opportunity, 'time': opportunity_time, 'information_cutoff': information,
                    'entity': normalized.get('entity_key')})
                old_event = normalized['event_key']
                context = {}
                if row[-2]: context = json.loads(row[-2])
                context = {c: context.get(c, raw.get(c)) for c in context_columns}
                self.writer.add('context', [opp_key], {'values': context, 'namespace': self.batch.namespace,
                                'prediction_derived': any(c.prediction_derived for c in self.batch.base.cohorts)})
                slot = raw.get(binding.slot_column) if binding.slot_column else binding.slot
                attempt = raw.get(binding.attempt_column) if binding.attempt_column else 'single'
                revision = raw.get(binding.revision_column) if binding.revision_column else 'initial'
                if not slot or not attempt or not revision: continue
                predecessor = raw.get(binding.predecessor_column) if binding.predecessor_column else None
                reason = raw.get(binding.correction_reason_column) if binding.correction_reason_column else None
                available = clock_value(raw, binding.available_at)
                payload = {'namespace': self.batch.namespace, 'variant': vid, 'opportunity_key': opp_key,
                           'target_key': digest(tid), 'logical_prediction': digest([opp_key, vid, slot]), 'slot': slot, 'attempt': attempt,
                           'normalized': {c: normalized[c] for c, _ in retained},
                           'role': normalized.get('cg_role') or base.role, 'uncertainty': []}
                if run.generated_at is not None:payload['generated_at']=run.generated_at
                payload['method_membership_qualified'] = run.id not in fitted or bool(getattr(store, 'assessment_membership', {}).get(run.id, False))
                payload['separation'] = getattr(getattr(store, 'extension', None), 'separation', None).to_dict() if getattr(getattr(store, 'extension', None), 'separation', None) else None
                payload['context_conflicts'] = [canonical for canonical, column in (store.context.assertions.get(root_id, {}) if store.context else {}).items() if raw.get(column) != context.get(canonical)]
                payload['inline_assertion'] = raw.get(base.inline_outcome) if base.inline_outcome else None
                payload['inline_assertion_role'] = base.inline_outcome_role if base.inline_outcome else None
                if row[-1]:
                    payload['uncertainty'] = [{'coverage': item['coverage'], 'output': json.loads(item['output'])} for item in json.loads(row[-1])]
                self.writer.add('prediction', [opp_key, vid, slot, attempt], payload, revision=revision,
                                predecessor=predecessor, available_ns=available['tick'], authority=self.batch.authority, reason=reason)
                map_batch.append((old_event,opp_key,digest([opp_key,vid,slot,attempt]),revision))
                if len(map_batch)>=512:
                    compat.insert_rows(store.con,mapping,map_batch);map_batch=[]
            if map_batch:compat.insert_rows(store.con,mapping,map_batch)
            if representation and representation.samples:
                sample_table=store.input_facts[root_id]['sample_table']
                for opp_key,prediction_key,prediction_revision,draw,value in rows(store.con,f'SELECT DISTINCT m.opportunity_key,m.prediction_key,m.prediction_revision,s.draw,s.value FROM {sample_table} s JOIN {mapping} m USING(event_key) ORDER BY m.opportunity_key,s.draw',batch=512):
                    self.writer.add('sample',[prediction_key,prediction_revision,draw],{'namespace':self.batch.namespace,'opportunity_key':opp_key,'variant':vid,'prediction_key':prediction_key,'prediction_revision':prediction_revision,'draw':draw,'value':value})
            if self.batch.feature_views or self.batch.discovery_representations:
                from .investigation_history import capture_typed
                capture_typed(self,store,run,base,vid,mapping)
            store.con.execute(f'DROP TABLE {mapping}')
        if self.descriptor.inputs is not None:
            for info in self.descriptor.inputs['external'].values():compat.capture(info['path'],store.roots,expected=info)
            self.metadata['external_inputs']=self.descriptor.inputs['external']
        return self.writer.finish(self.metadata)


def ingest_worker(batch, config, roots, descriptor, *, progress=None):
    """Capture supplied facts/outputs only. No fitting or E-only restriction."""
    from .engine import open_store
    from .result import Inspection
    batch = PredictionBatchSpec.from_dict(batch)
    extension = batch.evaluation if hasattr(batch.evaluation, 'evaluation') else None
    work = None
    try:
        work, store, _ = open_store(batch.base, config, roots, progress, extension=extension, capture=descriptor)
        store.history_capture.outputs(store)
        store.verify(); work.check('historical capture final verification')
        return Inspection({'capture_ready': True}, {'status': 'completed', 'peak_workspace_bytes': work.peak})
    finally:
        if work: work.close()


def outcomes_worker(spec, config, roots, directory, operation_id, workspace_config, *, progress=None):
    """Import raw revisions even when no prediction has arrived yet."""
    from .sources import Store
    from .contracts import EvaluationSpec, TaskDefinition, PredictionRunSpec, ModelIdentity
    from .result import Inspection
    spec = OutcomeRevisionSpec.from_dict(spec)
    # Shared secure Store ingestion; projection is extended before parsing.
    evaluation = EvaluationSpec(TaskDefinition('regression', spec.outcome_definition_version), (spec.source,),
                                (PredictionRunSpec('revision_source', spec.source.id, ModelIdentity('revision_source', '1'), key_columns=spec.event_columns),))
    work = compat.workspace(config, max(512 * 1024**2, Path(spec.source.path).stat().st_size * 6), progress)
    try:
        if progress: progress({'owned_workspace': str(work.root), 'stage': 'outcome_revision_ingestion'})
        store = Store(work, evaluation, config, roots)
        required = set(spec.event_columns) | set(spec.target_columns) | {spec.column, spec.revision_column, spec.order_column}
        for clock in (spec.available_at, spec.due_at, spec.target_at):
            if clock: required.add(clock.column)
        if spec.status_column: required.add(spec.status_column)
        store.selected = lambda sid: required
        store.ingest()
        writer = EvidenceWriter(directory, workspace_config, operation_id, work.check)
        for ordinal, payload in rows(store.con, f'SELECT ordinal,payload FROM {store.tables[spec.source.id]}', batch=512):
            record = json.loads(payload)
            writer.add('raw', [store.sources[spec.source.id]['sha256'], sorted(required), ordinal], {'record': record, 'ordinal': ordinal})
            event = values(record, spec.event_columns)
            target = values(record, spec.target_columns) if spec.target_columns else [spec.target_instance]
            if event is None or target is None: continue
            order = record.get(spec.order_column); revision = record.get(spec.revision_column)
            if not revision or order is None or not str(order).isascii() or not str(order).isdigit():
                raise EvaluationError('Revisions require stable IDs and nonnegative exact integer order.', 'revision_order')
            data = {'value': record.get(spec.column), 'status': record.get(spec.status_column) if spec.status_column else 'observed',
                    'order': str(int(order)), 'available': clock_value(record, spec.available_at),
                    'due': clock_value(record, spec.due_at), 'target_at': clock_value(record, spec.target_at),
                    'history_complete': spec.history_complete, 'namespace': spec.namespace,
                    'outcome_definition_version': spec.outcome_definition_version}
            writer.add('outcome', target_identity(spec.namespace, event, spec.outcome_definition_version, target), data,
                       revision=revision, authority=spec.authority, available_ns=data['available']['tick'])
        store.verify(); writer.finish({'outcome_revision': spec.to_dict(), 'sources': store.sources})
        return Inspection({'capture_ready': True}, {'status': 'completed', 'peak_workspace_bytes': work.peak})
    finally:
        work.close()
