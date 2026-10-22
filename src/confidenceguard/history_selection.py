"""Frozen historical selection and adapters for the existing CG1/CG2 reducers."""
from dataclasses import replace
import json
from types import SimpleNamespace
from . import compat
from .contracts import (EvaluationError, SourceSpec, PredictionRunSpec, TaskDefinition, digest)
from .analytics import Evidence, literal
from .sources import number, rows, Store
from .method_sources import MethodStore
from .history_contracts import instant
from .history_storage import Catalog, decode_numbers, serialized


class HistoricalEvidence(Evidence):
    def witnesses(self, measurement, run, table, where, columns):
        room = min(self.config.witnesses, self.config.max_details - len(self.locators))
        if room <= 0:
            return
        for fact, opportunity in self.con.execute(f'SELECT history_fact,history_opportunity FROM {table} WHERE {where} ORDER BY history_opportunity LIMIT ?', [room]).fetchall():
            ref = 'history_ref_' + digest([fact, measurement['metric'], measurement['scope']])[:24]
            self.locators[ref] = {'kind': 'historical_fact', 'fact_digest': fact, 'opportunity_key': opportunity,
                                  'columns': columns, 'variant': run.id}
            measurement['evidence_refs'].append(ref)


def load_history(work, root, spec, sequence):
    catalog = Catalog(root)
    con = work.con
    con.execute('CREATE TABLE hf(kind VARCHAR,key VARCHAR,revision VARCHAR,fact_digest VARCHAR,predecessor VARCHAR,available HUGEINT,authority VARCHAR,sequence BIGINT,payload VARCHAR,identity VARCHAR)')
    scanned = 0; parsed_bytes = 0; record_bytes = 0; objects = set(); pending = []
    for kind in ('opportunity', 'prediction', 'outcome', 'context', 'sample'):
        for fact in catalog.iter_facts(kind, sequence=(spec.prediction_catalog_sequence or sequence) if kind != 'outcome' else sequence, batch_ids=spec.batch_ids, max_records=spec.max_scan_records, check=work.check):
            record_bytes += fact['record_bytes']
            data = fact['payload']
            if data.get('namespace') != spec.namespace:
                continue
            scanned += 1
            if scanned > spec.max_scan_records:
                raise EvaluationError('Combined historical scan exceeded admission.', 'history_scan_limit')
            payload = serialized(data).decode(); parsed_bytes += len(payload); objects.add(fact['object_id'])
            pending.append((kind, fact['key'], fact['revision'], fact['fact_digest'], fact['predecessor'],
                            int(fact['available_ns']) if fact['available_ns'] is not None else None,
                            fact['authority'], fact['recorded_sequence'], payload, json.dumps(fact['identity'])))
            if len(pending) >= 512:
                compat.insert_rows(con,'hf',pending); pending = []; work.check('historical materialization')
    if pending: compat.insert_rows(con,'hf',pending)
    # Immutable capture descriptors provide the metadata that existed at K.
    # The convenience current-model index may have learned additional retention
    # bindings later and must never leak those declarations into earlier views.
    variants={};first_sequence={}
    for fact in catalog.iter_facts('capture_metadata',sequence=spec.prediction_catalog_sequence or sequence,batch_ids=spec.batch_ids,max_records=spec.max_scan_records,check=work.check):
        record_bytes+=fact['record_bytes'];parsed_bytes+=len(serialized(fact['payload']));objects.add(fact['object_id'])
        for vid,value in fact['payload'].get('variants',{}).items():
            if value['namespace']!=spec.namespace or spec.variants and vid not in spec.variants:continue
            if vid not in variants:
                variants[vid]=value;first_sequence[vid]=fact['recorded_sequence']
            else:
                features={**variants[vid]['features'],**value['features']}
                if fact['recorded_sequence']<first_sequence[vid]:variants[vid]=value;first_sequence[vid]=fact['recorded_sequence']
                variants[vid]['features']=features
    if set(spec.variants) - variants.keys():
        raise EvaluationError('Selected variant is unknown at the requested snapshot.', 'variant_unavailable')
    if not variants or len(variants) > spec.max_variants:
        raise EvaluationError('Select admitted variants present in this snapshot.', 'history_variant_limit')
    return variants, {'materialized_records': scanned, 'parsed_payload_bytes': parsed_bytes, 'objects_read': len(objects),
                      'record_bytes_read':record_bytes,'verified_object_bytes':sum(v[2] for v in catalog._verified.values()),'event_corpus_passes': 1, 'raw_projection_scan_required': False}


def select_history(work, spec, effective_as_of):
    con = work.con; cutoff = instant(effective_as_of)
    con.execute('CREATE TABLE h_visible AS SELECT * FROM hf WHERE available IS NULL OR available<=?', [instant(spec.prediction_as_of) if spec.prediction_as_of else cutoff])
    # Correction heads are resolved before any window or eligibility filter.
    for kind in ('opportunity', 'prediction', 'context'):
        condition = "AND revision='initial'" if kind == 'context' and spec.context_view == 'original' else ''
        con.execute(f'''CREATE TABLE hs_{kind} AS SELECT h.*,
            count(*) OVER(PARTITION BY key) head_count FROM h_visible h
            WHERE kind=? {condition} AND NOT EXISTS(SELECT 1 FROM h_visible child WHERE child.kind=h.kind AND child.key=h.key AND child.predecessor=h.fact_digest {"AND child.revision='initial'" if condition else ''})''', [kind])
    con.execute('CREATE TABLE h_opportunities AS SELECT *,json_extract_string(payload,\'$.target_key\') target_key,try_cast(json_extract_string(payload,\'$.time.tick\') AS HUGEINT) tick FROM hs_opportunity')
    con.execute('CREATE TABLE h_predictions AS SELECT *,json_extract_string(payload,\'$.variant\') variant,json_extract_string(payload,\'$.opportunity_key\') opportunity_key,json_extract_string(payload,\'$.logical_prediction\') logical_prediction,json_extract_string(payload,\'$.slot\') slot,json_extract_string(payload,\'$.attempt\') attempt,json_extract_string(payload,\'$.role\') history_role FROM hs_prediction')
    con.execute('CREATE TABLE h_outcomes AS SELECT *,try_cast(json_extract_string(payload,\'$.order\') AS HUGEINT) revision_order FROM hf WHERE kind=\'outcome\'')
    return cutoff


class HistoryStore:
    """One variant's frozen outputs, with labels/context selected anew per window."""
    group = Store.group
    refresh_losses = MethodStore.refresh_losses

    def __init__(self, work, spec, variant, metadata, window, cutoff):
        self.work = work; self.con = work.con; self.config = spec.config; self.variant = variant
        task = TaskDefinition.from_dict(metadata['task'])
        run = PredictionRunSpec.from_dict(metadata['run'])
        self.spec = SimpleNamespace(task=task, runs=(run,), cohorts=spec.cohorts,
                                    sources=(SourceSpec('historical', '/historical-evidence'),))
        self.event_costs=spec.event_costs
        self.run = run; self.outcomes = None; self.roots = ()
        self.representations = {}; self.input_facts = {}; self.run_tables = {}; self.run_facts = {}
        self.extension = SimpleNamespace(roles=SimpleNamespace(seed=spec.inference.seed, namespace=spec.namespace))
        self.sources = {'historical': {'sha256': digest([variant, window.to_dict(), cutoff, spec.catalog_sequence])}}
        self.outcome_facts = {'snapshot_digest': digest([spec.catalog_sequence, cutoff, spec.maturity, spec.followup_ns, spec.authority])}
        self.context_facts = {'snapshot_digest': digest([spec.context_view, [c.to_dict() for c in spec.cohorts]])}
        suffix = digest([variant, window.id])[:14]; table = 'history_run_' + suffix
        self.table = table; self.run_tables[variant] = table
        columns = dict(metadata['normalized_columns'])
        columns.update({'ordinal': 'BIGINT', 'event_key': 'VARCHAR', 'y': 'VARCHAR', 'y_num': 'DOUBLE',
                        'outcome_valid': 'BOOLEAN', 'outcome_reason': 'VARCHAR', 'ptrue': 'DOUBLE', 'brier': 'DOUBLE',
                        'log_loss': 'DOUBLE', 'log_infinite': 'BOOLEAN', 'cg_log_probs': 'DOUBLE[]', 'cg_role': 'VARCHAR',
                        'history_fact': 'VARCHAR', 'history_opportunity': 'VARCHAR', 'history_target': 'VARCHAR',
                        'history_tick': 'HUGEINT', 'history_context': 'VARCHAR'})
        for index, _ in enumerate(spec.cohorts): columns['g' + str(index)] = 'VARCHAR'
        # Column names/types come only from validated local normalized schemas.
        allowed = {'BIGINT', 'VARCHAR', 'DOUBLE', 'BOOLEAN', 'HUGEINT', 'DOUBLE[]', 'BIGINT[]', 'INTEGER', 'INTEGER[]'}
        if any(not c.replace('_', '').isalnum() or t not in allowed for c, t in columns.items()):
            raise EvaluationError('Unsupported normalized relation schema.', 'history_normalization_version')
        self.con.execute(f'CREATE TABLE {table}(' + ','.join('"' + c + '" ' + t for c, t in columns.items()) + ')')
        self.con.execute(f'CREATE TABLE history_uncertainty_{suffix}(ordinal BIGINT,event_key VARCHAR,coverage VARCHAR,output VARCHAR)')
        self.uncertainty_table = 'history_uncertainty_' + suffix
        self.coverage = {'opportunities': 0, 'selected_predictions': 0, 'ambiguous_predictions': 0,
                         'outcome_states': {}, 'observation_scope': 'eligible observed reference outcomes',
                         'selective_labels_not_corrected': True, 'unknown_maturity': 0, 'corrected_records': 0,
                         'unknown_information_cutoff':0,'information_after_opportunity':0,'unqualified_method_outputs': 0,'incomplete_outcome_history':0,'undated_outcomes':0}
        self.coverage['unlocated_opportunities'] = self.con.execute("SELECT count(*) FROM h_predictions p JOIN h_opportunities o ON p.opportunity_key=o.key WHERE p.variant=? AND o.tick IS NULL",[variant]).fetchone()[0]
        self.coverage['inline_assertion_conflicts'] = 0
        self.features = {}; self.raw_rows = []
        self._populate(spec, metadata, window, cutoff, columns)
        self.refresh_losses(table)
        self.coverage['feature_retention']={feature:self.con.execute(f"SELECT count(*) FILTER(WHERE json_exists(history_context,{literal('$.'+json.dumps(feature))})) FROM {table}").fetchone()[0] for feature in spec.features}
        self.coverage['output_states'] = dict(self.con.execute(f'SELECT state,count(*) FROM {table} GROUP BY state').fetchall())
        failure = 'cg_failure IS NOT NULL' if 'cg_failure' in columns else "state IN ('failed','missing')"
        self.coverage['application_failures'] = self.con.execute(f'SELECT count(*) FROM {table} WHERE {failure}').fetchone()[0]
        repeated = self.con.execute(f'SELECT coalesce(sum(n),0) FROM (SELECT count(*) n FROM {table} WHERE entity_key IS NOT NULL GROUP BY entity_key HAVING count(*)>1)').fetchone()[0]
        self.run_facts[variant] = {'repeated_entities': repeated, 'context_conflicts': {}, 'duplicate_keys': 0,
                                 'missing_keys': 0, 'inline_conflicts': 0}
        self.evidence = HistoricalEvidence(self)
        self.evidence.bind_relation(table, {'kind': 'historical_selected_predictions', 'variant': variant,
            'window': window.to_dict(), 'catalog_sequence': spec.catalog_sequence, 'outcome_snapshot': self.outcome_facts['snapshot_digest'],
            'context_snapshot': self.context_facts['snapshot_digest'], 'normalization_version': 'historical_facts_v1',
            'selected_fact_digest': self.selected_digest})

    def _populate(self, spec, metadata, window, cutoff, columns):
        con = self.con; variant = self.variant
        start, end = instant(window.start), instant(window.end)
        # Target revisions are selected per event/follow-up, prior to testing label validity.
        desired = spec.attempts.get(variant)
        if desired is not None and not isinstance(desired, str):
            raise EvaluationError('Attempt selection maps variants to explicit attempt IDs.')
        slot_predicate = ' OR '.join('p.slot=' + literal(v) for v in spec.slots) or 'false'
        role_predicate = ' OR '.join('p.history_role=' + literal(v) for v in spec.roles) or 'false'
        attempt_predicate = ' AND p.attempt=' + literal(desired) if desired else ''
        query = f'''SELECT p.payload,p.fact_digest,p.predecessor,p.head_count,o.payload,o.head_count,c.payload,c.head_count,
                    count(*) OVER(PARTITION BY p.logical_prediction) attempts
             FROM h_predictions p JOIN h_opportunities o ON p.opportunity_key=o.key
             LEFT JOIN hs_context c ON c.key=sha256(to_json(list_value(p.opportunity_key)))
             WHERE p.variant=? AND ({slot_predicate}) AND ({role_predicate}) {attempt_predicate}
                   AND o.tick>=? AND o.tick<?'''
        # Canonical SHA uses ASCII JSON. Context keys are joined through an explicit
        # key column rather than relying on DuckDB's JSON escaping conventions.
        context_map = 'ctx_' + digest([variant, window.id])[:12]
        con.execute(f'CREATE TABLE {context_map}(opportunity_key VARCHAR,payload VARCHAR,head_count BIGINT)')
        con.execute(f'INSERT INTO {context_map} SELECT l.opportunity_key,c.payload,c.head_count FROM hs_context c JOIN h_context_links l USING(key)')
        query = query.replace("hs_context c ON c.key=sha256(to_json(list_value(p.opportunity_key)))", f'{context_map} c ON c.opportunity_key=p.opportunity_key')
        eligible_unknown = spec.as_of is None and spec.maturity != 'equal_followup'
        revision_cutoff = f'least({cutoff},o.tick+{int(spec.followup_ns)})' if spec.maturity == 'equal_followup' else str(cutoff)
        unknown = "json_extract_string(h.payload,'$.available.state')<>'valid'"
        allow_unknown = f"({unknown} AND json_extract_string(h.payload,'$.order')='0')" if eligible_unknown else 'false'
        outcome_plan = 'outcome_plan_' + digest([variant, window.id])[:12]
        con.execute(f"""CREATE TABLE {outcome_plan} AS WITH candidates AS (
            SELECT o.key opportunity_key,h.payload,h.fact_digest,h.revision_order,h.available,
               ({unknown} AND NOT ({allow_unknown})) unknown_availability,
               (h.available<={revision_cutoff} OR ({allow_unknown})) eligible
            FROM h_opportunities o JOIN h_outcomes h ON h.key=o.target_key
            WHERE o.tick>=? AND o.tick<? AND h.authority=?), eligible AS (
            SELECT *,max(revision_order) OVER(PARTITION BY opportunity_key) max_order,
               lag(available) OVER(PARTITION BY opportunity_key ORDER BY revision_order) previous_available
            FROM candidates WHERE eligible), heads AS (
            SELECT *,count(*) OVER(PARTITION BY opportunity_key) head_count FROM eligible WHERE revision_order=max_order),
            invalid AS (SELECT opportunity_key,bool_or(unknown_availability) availability_unknown FROM candidates GROUP BY opportunity_key),
            chronology AS (SELECT opportunity_key,bool_or(available<previous_available) bad FROM eligible GROUP BY opportunity_key)
            SELECT i.opportunity_key,min(h.payload) outcome_payload,min(h.fact_digest) outcome_digest,
               CASE WHEN i.availability_unknown THEN 'unresolved_outcome_availability'
                    WHEN coalesce(max(h.head_count),0)>1 THEN 'ambiguous_outcome_revision'
                    WHEN bool_or(c.bad) THEN 'inconsistent_revision_chronology'
                    WHEN count(h.fact_digest)=0 THEN 'no_outcome_available_as_of' ELSE NULL END reason
            FROM invalid i LEFT JOIN heads h USING(opportunity_key) LEFT JOIN chronology c USING(opportunity_key)
            GROUP BY i.opportunity_key,i.availability_unknown""", [start,end,spec.authority])
        selected_outcomes = {}
        # Metadata is small for ordinary jobs; the SQL join below streams records
        # for large histories instead of materializing event dictionaries.
        query = query.replace('SELECT p.payload,p.fact_digest', 'SELECT p.payload,p.fact_digest')
        query = query.replace('count(*) OVER(PARTITION BY p.logical_prediction) attempts',
            'count(*) OVER(PARTITION BY p.logical_prediction) attempts,sel.outcome_payload,sel.outcome_digest,sel.reason')
        query = query.replace(f'WHERE p.variant=?', f'LEFT JOIN {outcome_plan} sel ON sel.opportunity_key=p.opportunity_key WHERE p.variant=?')
        import hashlib
        h = hashlib.sha256(); ordinal = 0; pending = []; uncertainty = []
        for raw, fact_digest, revision, heads, opp_raw, opp_heads, ctx_raw, ctx_heads, attempts, selected_raw, selected_digest, selected_reason in rows(con, query, [variant, start, end], batch=512):
            self.coverage['opportunities'] += 1
            if heads != 1 or opp_heads != 1 or attempts != 1 or ctx_heads not in (None, 1):
                self.coverage['ambiguous_predictions'] += 1; continue
            pred = decode_numbers(json.loads(raw)); opp = json.loads(opp_raw)
            if not pred.get('method_membership_qualified', True): self.coverage['unqualified_method_outputs'] += 1
            context = json.loads(ctx_raw)['values'] if ctx_raw else {}
            normalized = pred['normalized']; ordinal += 1
            info=opp['information_cutoff']
            self.coverage['unknown_information_cutoff']+=info['state']!='valid'
            lookahead=info['tick'] is not None and int(info['tick'])>int(opp['time']['tick'])
            self.coverage['information_after_opportunity']+=lookahead
            selected_cutoff = cutoff
            age = cutoff - int(opp['time']['tick'])
            if spec.maturity == 'equal_followup': selected_cutoff = min(cutoff, int(opp['time']['tick']) + int(spec.followup_ns))
            outcome_data = (selected_raw, selected_digest, selected_reason)
            selected = json.loads(outcome_data[0]) if outcome_data and outcome_data[0] else None
            outcome_digest = outcome_data[1] if outcome_data else None
            reason = (outcome_data[2] or ('no_matched_outcome' if not selected else None)) if outcome_data else 'no_matched_outcome'
            if reason: selected = None
            y = yn = None; valid = False
            if selected:
                self.coverage['incomplete_outcome_history'] += not selected.get('history_complete',False)
                self.coverage['undated_outcomes'] += selected['available']['state'] != 'valid'
                y = selected['value']; yn = number(y) if self.spec.task.kind == 'regression' else None
                valid = yn is not None if self.spec.task.kind == 'regression' else y in self.spec.task.classes
                reason = None if valid else 'missing_or_invalid_outcome'
                if selected['status'] not in {'observed', 'final'}: valid = False; reason = 'outcome_' + str(selected['status'])
                if selected['order'] == '0' and pred.get('inline_assertion_role') == 'agreement_assertion' and pred.get('inline_assertion') is not None:
                    same = number(pred['inline_assertion']) == yn if self.spec.task.kind == 'regression' else pred['inline_assertion'] == y
                    if not same: self.coverage['inline_assertion_conflicts'] += 1
                due = selected.get('due', {'tick': None, 'state': 'undeclared'})
                if due['state'] == 'undeclared': self.coverage['unknown_maturity'] += 1
                if spec.maturity != 'observed' and due['state'] not in {'valid', 'undeclared'}:
                    valid = False; reason = 'unresolved_maturity'
                elif spec.maturity != 'observed' and due['tick'] is not None and int(due['tick']) > selected_cutoff:
                    valid = False; reason = 'immature_outcome'
                if spec.maturity == 'equal_followup' and age < int(spec.followup_ns):
                    valid = False; reason = 'insufficient_followup'
            if lookahead:valid=False;reason='information_after_opportunity'
            state = reason or 'eligible'
            self.coverage['outcome_states'][state] = self.coverage['outcome_states'].get(state, 0) + 1
            normalized.update(ordinal=ordinal, event_key=pred['opportunity_key'], y=y, y_num=yn, outcome_valid=valid,
                              outcome_reason=reason, ptrue=None, brier=None, log_loss=None, log_infinite=False,
                              history_fact=fact_digest, history_opportunity=pred['opportunity_key'], history_target=pred['target_key'],
                              history_tick=int(opp['time']['tick']), history_context=json.dumps(context), cg_role=pred['role'])
            normalized.setdefault('cg_log_probs', None)
            for index, cohort in enumerate(spec.cohorts):
                normalized['g' + str(index)] = ('unretained' if cohort.column not in context else 'unresolved' if cohort.column in pred.get('context_conflicts', []) else self.group(context, cohort))
            pending.append(tuple(normalized.get(c) for c in columns))
            for item in pred['uncertainty']: uncertainty.append((ordinal, pred['opportunity_key'], item['coverage'], json.dumps(item['output'])))
            h.update(serialized([fact_digest, outcome_digest if selected else None, normalized['outcome_valid'], reason, context]))
            self.coverage['selected_predictions'] += 1
            self.coverage['corrected_records'] += revision is not None
            if len(pending) >= 512:
                compat.insert_rows(con,self.table,pending); pending = []; self.work.check('historical selected outputs')
            if len(uncertainty) >= 512:
                compat.insert_rows(con,self.uncertainty_table,uncertainty); uncertainty = []
        if pending: compat.insert_rows(con,self.table,pending)
        if uncertainty: compat.insert_rows(con,self.uncertainty_table,uncertainty)
        self.selected_digest = h.hexdigest()
        if metadata.get('representation'):
            from .method_contracts import RepresentationSpec
            rep = dict(metadata['representation']); rep['run'] = variant
            self.representations[variant] = RepresentationSpec.from_dict(rep)
            if rep.get('samples'):
                sample_table = 'samples_' + digest([variant, window.id])[:12]
                con.execute(f'''CREATE TABLE {sample_table} AS SELECT json_extract_string(s.payload,'$.opportunity_key') event_key,
                    json_extract_string(s.payload,'$.draw') draw,try_cast(json_extract_string(s.payload,'$.value') AS DOUBLE) "value"
                    FROM hf s JOIN hs_prediction p ON p.key=json_extract_string(s.payload,'$.prediction_key') AND p.revision=json_extract_string(s.payload,'$.prediction_revision')
                    JOIN {self.table} r ON r.history_fact=p.fact_digest
                    WHERE s.kind='sample' AND json_extract_string(s.payload,'$.variant')=?
                    AND json_extract_string(s.payload,'$.opportunity_key') IN (SELECT event_key FROM {self.table})''', [variant])
                self.input_facts[variant] = {'sample_table': sample_table, 'sample_meaning': rep['samples']['meaning']}


def context_links(work, root, sequence, max_records):
    """Opaque canonical identity links; never infer equality through JSON formatting."""
    con = work.con
    con.execute('CREATE TABLE h_context_links(key VARCHAR PRIMARY KEY,opportunity_key VARCHAR)')
    con.execute("INSERT INTO h_context_links SELECT key,min(json_extract_string(identity,'$[0]')) FROM hf WHERE kind='context' GROUP BY key")
