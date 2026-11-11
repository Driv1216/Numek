"""Opt-in public workspace facade. All clients share these application services."""
from dataclasses import replace
from pathlib import Path
import copy
import json
import os
import time
import uuid
from .contracts import EvaluationConfig, EvaluationError, digest, strict_json
from .history_contracts import (WorkspaceConfig, PredictionBatchSpec, OutcomeRevisionSpec,
    HistoricalCorrectionSpec, LongitudinalSpec, instant)
from .history_storage import Catalog, EvidenceWriter, serialized, private_file, file_lock
from .history_capture import CaptureDescriptor, ingest_worker, outcomes_worker
from . import compat


def _append_assessment(stage, result, config):
    """Parent adds the sealed assessment to the same atomic capture operation."""
    with private_file(stage / 'capture.json', 'rb') as stream:
        manifest = strict_json(stream.read(64*1024**2+1))
    manifest.pop('content_digest')
    aid = result.data['analysis_id']; identity = [aid]
    record = {'kind': 'assessment', 'key': digest(identity), 'identity': identity, 'revision': 'initial',
              'payload': {'result': result.to_private_dict(), 'manifest': result.private},
              'predecessor': None, 'available_ns': None, 'authority': None, 'reason': None}
    record['fact_digest'] = digest(record); raw = serialized(record)+b'\n'
    if len(raw) > config.max_record_bytes:
        raise EvaluationError('Assessment record exceeds recording admission.', 'history_record_limit')
    oid = uuid.uuid4().hex
    with private_file(stage / (oid+'.jsonl')) as stream:
        stream.write(raw); stream.flush(); os.fsync(stream.fileno())
    entry = {'kind': 'assessment', 'key': record['key'], 'revision': 'initial', 'fact_digest': record['fact_digest'],
             'object_id': oid, 'offset': 0, 'length': len(raw)}
    fd = os.open(stage / 'index.jsonl', os.O_WRONLY | os.O_APPEND | getattr(os, 'O_NOFOLLOW', 0))
    with os.fdopen(fd, 'ab') as stream:
        stream.write(serialized(entry)+b'\n'); stream.flush(); os.fsync(stream.fileno())
    import hashlib
    manifest['objects'].append({'id': oid, 'kind': 'assessment', 'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw),
                                'records': 1, 'encoding': 'utf8_jsonl_v1', 'normalization_version': 'historical_facts_v1'})
    manifest['metadata']['assessment_id'] = aid
    manifest['content_digest'] = digest(manifest)
    # The manifest is still private staging, never a completed immutable object.
    fd = os.open(stage / 'capture.json', os.O_WRONLY | os.O_TRUNC | getattr(os, 'O_NOFOLLOW', 0))
    with os.fdopen(fd, 'wb') as stream:
        stream.write(serialized(manifest)); stream.flush(); os.fsync(stream.fileno())


class ReliabilityWorkspace:
    def __init__(self, path):
        self.catalog = Catalog(path)
        self.path = self.catalog.root

    @classmethod
    def initialize(cls, path, config=None):
        if isinstance(config, dict): config = WorkspaceConfig.from_dict(config)
        Catalog(path, create=True, config=config or WorkspaceConfig())
        return cls(path)

    @property
    def instance_id(self): return self.catalog.instance_id

    def status(self): return self.catalog.status()
    def models(self):
        return list(self.catalog.variants().values())
    def set_saving(self, enabled): return self.catalog.set_saving(enabled)
    def recover(self): return self.catalog.recover()

    def ingest(self, batch, config=None, *, request_id=None, progress=None, cancel=None, allowed_roots=None):
        if isinstance(batch, dict): batch = PredictionBatchSpec.from_dict(batch)
        if not isinstance(batch, PredictionBatchSpec): raise EvaluationError('PredictionBatchSpec required.')
        if isinstance(config, dict): config = EvaluationConfig.from_dict(config)
        config = config or EvaluationConfig()
        sources = batch.base.sources
        roots = tuple(str(Path(p).absolute()) for p in (allowed_roots if allowed_roots is not None else {Path(s.path).absolute().parent for s in sources}))
        if not roots: raise EvaluationError('Current authorized roots required.', 'roots_required')
        # Source bytes bind idempotency; filename alone is not an import identity.
        identities = {s.id: compat.capture(s.path, roots)[0]['sha256'] for s in sources}
        deadline=time.monotonic()+config.max_seconds
        from .evidence_use import EvidenceUseLedger
        ledger=EvidenceUseLedger(self);tracking=ledger.status()['enabled']
        inputs=None
        if batch.feature_views or batch.discovery_representations or tracking:
            from .history_capture import capture_inputs_worker
            inputs=compat.supervise(capture_inputs_worker,(batch.to_dict(),config,roots),config,progress=progress,cancel=cancel,deadline=deadline).data
            if identities!={k:v['sha256'] for k,v in inputs['sources'].items()}:raise EvaluationError('Sources changed during capture admission.','source_changed')
        request_digest = digest({'batch': batch.to_dict(), 'config': config.to_dict(), 'sources': identities,
                                 **({'external':inputs['external']} if inputs is not None and inputs['external'] else {})})
        with self.catalog.operation():
            self.catalog.reserve()
            if request_id:
                previous=self.catalog.receipt(request_id,request_digest)
                if previous:return previous
            if tracking and batch.operation!='ingest':
                population=digest([inputs['events'],inputs['units']])
                ledger.record('outcome_disclosure',events=inputs['events'],units=inputs['units'],population_digest=population,
                    request_id=('capture:'+request_id) if request_id else None,metadata={'operation':batch.operation,'namespace':batch.namespace},
                    cancel=cancel,deadline=deadline,locked=True,session_max_bytes=config.max_rss_bytes//8)
            operation, previous = self.catalog.begin(request_id or uuid.uuid4().hex, request_digest)
            if previous: return previous
            stage = self.path / 'staging' / operation
            descriptor = CaptureDescriptor(str(stage), operation, self.catalog.config.to_dict(), batch.to_dict(),inputs)
            result = None
            try:
                if batch.operation == 'ingest':
                    compat.supervise(ingest_worker, (batch.to_dict(), config, roots, descriptor), config, progress=progress, cancel=cancel,deadline=deadline)
                else:
                    from .engine import evaluate
                    from .methods import study, fit_methods, apply_methods
                    operation_service = {'evaluate': evaluate, 'study': study, 'fit': fit_methods, 'apply': apply_methods}[batch.operation]
                    result = operation_service(batch.evaluation, config, allowed_roots=roots, progress=progress, cancel=cancel, _capture=descriptor,_deadline=deadline)
                    _append_assessment(stage, result, self.catalog.config)
                receipt = self.catalog.commit_capture(operation, cancel=cancel, receipt_extra={'assessment_id': result.data['analysis_id']} if result else None)
                return receipt
            except BaseException as exc:
                # A completed ephemeral evaluation is explicitly distinct from an
                # uncommitted recording. Do not attach it as historical evidence.
                if result is not None: exc.completed_evaluation = result
                raise

    def evaluate(self, batch, config=None, **kwargs):
        if isinstance(batch, dict): batch = PredictionBatchSpec.from_dict(batch)
        return self.ingest(replace(batch, operation='evaluate'), config, **kwargs)

    def update_outcomes(self, specification, config=None, *, request_id=None, progress=None, cancel=None, allowed_roots=None):
        if isinstance(specification, dict): specification = OutcomeRevisionSpec.from_dict(specification)
        if isinstance(config, dict): config = EvaluationConfig.from_dict(config)
        config = config or EvaluationConfig()
        roots = tuple(str(Path(p).absolute()) for p in (allowed_roots if allowed_roots is not None else (Path(specification.source.path).absolute().parent,)))
        identity = compat.capture(specification.source.path, roots)[0]['sha256']
        with self.catalog.operation():
            self.catalog.reserve()
            operation, previous = self.catalog.begin(request_id or uuid.uuid4().hex, digest([specification.to_dict(), identity, config.to_dict()]))
            if previous: return previous
            compat.supervise(outcomes_worker, (specification.to_dict(), config, roots, str(self.path/'staging'/operation), operation, self.catalog.config.to_dict()),
                             config, progress=progress, cancel=cancel)
            return self.catalog.commit_capture(operation, cancel=cancel)

    def correct(self, specification, *, request_id=None):
        if isinstance(specification, dict): specification = HistoricalCorrectionSpec.from_dict(specification)
        with self.catalog.operation():
            facts = list(self.catalog.iter_facts(specification.kind, keys=[specification.key]))
            parent = next((f for f in facts if f['fact_digest'] == specification.predecessor), None)
            if parent is None: raise EvaluationError('Correction predecessor is unavailable.', 'correction_predecessor')
            if specification.authority != parent.get('authority') and parent.get('authority') is not None:
                raise EvaluationError('Correction authority differs.', 'correction_authority')
            if any(f['predecessor'] == specification.predecessor for f in facts):
                raise EvaluationError('A competing correction head already exists.', 'correction_fork')
            if specification.kind == 'prediction':
                raise EvaluationError('Prediction corrections require a PredictionBatchSpec with revision/predecessor/reason bindings so the shared normalizer validates new outputs.', 'prediction_correction_requires_ingestion')
            allowed = {'values'} if specification.kind == 'context' else {'time', 'information_cutoff'}
            if set(specification.changes)-allowed: raise EvaluationError('Correction cannot reassign immutable identity.', 'identity_reassignment')
            payload = copy.deepcopy(parent['payload']); payload.update(specification.changes)
            if specification.kind == 'opportunity':
                for field in specification.changes:
                    clock = payload[field]
                    if not isinstance(clock, dict) or set(clock) != {'tick', 'state'} or clock['state'] != 'valid' or not isinstance(clock['tick'], str) or not clock['tick'].lstrip('-').isdigit():
                        raise EvaluationError('Corrected opportunity clocks require exact valid tick/state pairs.')
            operation, previous = self.catalog.begin(request_id or uuid.uuid4().hex, digest(specification.to_dict()))
            if previous: return previous
            writer = EvidenceWriter(self.path/'staging'/operation, self.catalog.config, operation)
            writer.add(specification.kind, parent['identity'], payload, revision=specification.revision,
                       predecessor=parent['fact_digest'], available_ns=instant(specification.available_at),
                       authority=specification.authority, reason=specification.reason)
            writer.finish({'correction': specification.to_dict()})
            return self.catalog.commit_capture(operation)

    def inspect(self, spec, *, populations=True):
        if isinstance(spec, dict): spec = LongitudinalSpec.from_dict(spec)
        status = self.status(); sequence = spec.catalog_sequence or status['catalog_sequence']
        if sequence > status['catalog_sequence']: raise EvaluationError('Future catalog snapshot is unavailable.', 'catalog_snapshot')
        frozen = replace(spec, catalog_sequence=sequence)
        fingerprint = digest({'spec': frozen.to_dict(), 'instance': self.instance_id, 'catalog_sequence': status['catalog_sequence']})
        result = {'schema_version': 'confidenceguard.longitudinal_inspection/1.0', 'spec': frozen.to_dict(), 'fingerprint': fingerprint,
                'catalog_sequence': status['catalog_sequence'], 'variants': self.models(),
                'qualifications': ['Observed-label populations and declared dependence only.', 'Detailed eligibility is computed under supervised analysis.']}
        if populations:
            from .longitudinal import _inspect_history
            from .history_contracts import now
            with self.catalog.operation():
                self._reserve_history_exposure(frozen,purpose='historical_population_preview',locked=True)
                result['population_preview']=compat.supervise(_inspect_history,(str(self.path),frozen,sequence,frozen.as_of or now()),frozen.config).data
        return result

    def _reserve_history_exposure(self,spec,*,purpose,locked=False,progress=None,cancel=None,deadline=None):
        from .evidence_use import EvidenceUseLedger
        from .longitudinal import exposure_population
        ledger=EvidenceUseLedger(self)
        if not ledger.status()['enabled']:return
        population=compat.supervise(exposure_population,(str(self.path),spec,spec.catalog_sequence,spec.as_of or __import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat()),spec.config,progress=progress,cancel=cancel,deadline=deadline).data
        ledger.record('outcome_disclosure',**population,metadata={'purpose':purpose,'namespace':spec.namespace},locked=locked,cancel=cancel,deadline=deadline,session_max_bytes=spec.config.max_rss_bytes//8)

    def _reserve_live_exposure(self,spec,config,roots,*,operation,request_id,progress=None,cancel=None,deadline=None):
        from .evidence_use import EvidenceUseLedger,evaluation_exposure_worker
        base=spec.evaluation if hasattr(spec,'evaluation') else spec
        ledger=EvidenceUseLedger(self)
        if base.effective_outcomes is None or not ledger.status()['enabled']:return None
        packet=compat.supervise(evaluation_exposure_worker,(spec,config,roots,operation),config,progress=progress,cancel=cancel,deadline=deadline).data
        sources=packet.pop('sources')
        return ledger.record('outcome_disclosure',**packet,request_id=request_id,metadata={'purpose':'live_browser_outcome_assessment','operation':operation,'sources':sources},
            cancel=cancel,deadline=deadline,session_max_bytes=config.max_rss_bytes//8)

    def analyze(self, spec, *, request_id=None, progress=None, cancel=None, expected_fingerprint=None):
        if isinstance(spec, dict): spec = LongitudinalSpec.from_dict(spec)
        request_digest = digest({'analysis_request': spec.to_dict()});deadline=time.monotonic()+spec.config.max_seconds
        with self.catalog.operation():
            if request_id:
                previous = self.catalog.receipt(request_id, request_digest)
                if previous:return self.catalog.assessment(previous['assessment_id'])
            inspected = self.inspect(spec,populations=False)
            if expected_fingerprint is not None and expected_fingerprint != inspected['fingerprint']:
                raise EvaluationError('Historical confirmation is stale.', 'stale_confirmation')
            spec = LongitudinalSpec.from_dict(inspected['spec'])
            if spec.restates:
                prior = self.catalog.assessment(spec.restates)
                if not hasattr(prior, 'private') or 'history_spec' not in prior.private: raise EvaluationError('Restate a protected historical assessment.')
                if spec.outcome_only:
                    spec = replace(spec, prediction_catalog_sequence=prior.private['history_spec'].get('prediction_catalog_sequence') or prior.private['history_spec']['catalog_sequence'],prediction_as_of=prior.private['history_spec'].get('prediction_as_of') or prior.data['history']['as_of'])
                    left = LongitudinalSpec.from_dict(prior.private['history_spec']).to_dict(); right = spec.to_dict().copy()
                    for field in ('catalog_sequence', 'prediction_catalog_sequence','prediction_as_of', 'as_of', 'restates', 'restatement_reason', 'outcome_only', 'name'):
                        left.pop(field, None); right.pop(field, None)
                    if left != right: raise EvaluationError('Outcome-only restatement changed frozen analysis declarations.', 'restatement_scope')
            from .longitudinal import analyze
            self._reserve_history_exposure(spec,purpose='historical_analysis',locked=True,progress=progress,cancel=cancel,deadline=deadline)
            result = analyze(self.path, spec, progress=progress, cancel=cancel,_deadline=deadline)
            if spec.restates:
                result.data['history']['restatement_changes'] = self._restatement_delta(prior, result)
                result.seal()
            receipt = self.catalog.add_assessment(result, request_id=request_id, cancel=cancel, request_digest=request_digest)
            return result

    def restate(self, assessment_id, *, as_of=None, reason, outcome_only=True, **kwargs):
        prior = self.open(assessment_id)
        if prior.data.get('methodology_id')=='failure_investigation_v1':
            if not outcome_only:raise EvaluationError('Use an explicit historical replay for changed prediction/feature snapshots.','restatement_scope')
            return self.restate_investigation(assessment_id,as_of=as_of,reason=reason,**kwargs)
        values = prior.private['history_spec'].copy()
        values.update(catalog_sequence=None, as_of=as_of, restates=assessment_id, restatement_reason=reason, outcome_only=outcome_only)
        return self.analyze(LongitudinalSpec.from_dict(values), **kwargs)

    @staticmethod
    def _restatement_delta(prior, result):
        a = {(m['run'], m['scope'], m['metric'], m.get('data', {}).get('target')): m for m in prior.data['measurements']}
        changed = []
        for m in result.data['measurements']:
            key = (m['run'], m['scope'], m['metric'], m.get('data', {}).get('target')); old = a.get(key)
            if old and any(old[k] != m[k] for k in ('value', 'value_state', 'denominator', 'population_id')):
                changed.append({'metric': m['metric'], 'run': m['run'], 'scope': m['scope'], 'reference_support': old['denominator'],
                                'current_support': m['denominator'], 'reference_value': old['value'], 'current_value': m['value'],
                                'reference_state': old['value_state'], 'current_state': m['value_state'], 'population_changed': old['population_id'] != m['population_id']})
        return changed

    def open(self, assessment_id):
        with file_lock(self.catalog.objects_lock, False): return self.catalog.assessment(assessment_id)

    def assessments(self):
        result = []
        with file_lock(self.catalog.objects_lock, False):
            for fact in self.catalog.iter_facts('assessment',require_complete=False):
                value = fact['payload']['result']
                result.append({'id': value['analysis_id'], 'name': value['name'], 'generated_at': value['generated_at'],
                               'methodology_id': value['methodology_id'], 'catalog_sequence': fact['recorded_sequence']})
        return result

    def save_assessment(self, result, *, request_id=None):
        # Existing exact bundles stay immutable. They do not gain reconstructable
        # event evidence merely by being added to this catalog.
        type(result).from_dict(result.to_private_dict(), private=result.private)
        if result.data.get('methodology_id')=='predictor_robustness_v1':
            from .execution.storage import save_result
            return save_result(self,result,request_id=request_id)
        with self.catalog.operation(): return self.catalog.add_assessment(result, request_id=request_id)

    def _cg6_service(self,operation,spec,config=None,**kwargs):
        from .execution.services import service
        return service(spec,config,operation=operation,workspace=None if operation=='inspect' else self,tracking_workspace=self,**kwargs)

    def inspect_predictor(self,spec,config=None,**kwargs):return self._cg6_service('inspect',spec,config,**kwargs)
    def register_predictor(self,spec,config=None,**kwargs):return self._cg6_service('register',spec,config,**kwargs)
    def execute_predictor(self,spec,config=None,**kwargs):return self._cg6_service('execute',spec,config,**kwargs)
    def qualify_predictor(self,spec,config=None,*,reference=None,atol=1e-6,rtol=1e-5,**kwargs):
        return self._cg6_service('qualify',spec,config,options={'reference':reference,'atol':atol,'rtol':rtol},**kwargs)
    def fit_auxiliary(self,spec,config=None,**kwargs):
        from .auxiliary.services import fit_auxiliary
        return fit_auxiliary(spec,config,workspace=self,**kwargs)
    def apply_auxiliary(self,spec,artifact,config=None,**kwargs):
        from .auxiliary.services import apply_auxiliary
        return apply_auxiliary(spec,artifact,config,workspace=self,**kwargs)
    def assess_auxiliary(self,spec,artifact,config=None,**kwargs):
        from .auxiliary.services import assess_auxiliary
        return assess_auxiliary(spec,artifact,config,workspace=self,**kwargs)
    def inspect_robustness(self,spec,config=None,**kwargs):
        from .robustness.services import inspect_robustness
        return inspect_robustness(spec,config,tracking_workspace=self,**kwargs)
    def run_robustness(self,spec,config=None,**kwargs):
        from .robustness.services import run_robustness
        return run_robustness(spec,config,workspace=self,**kwargs)
    def assess_robustness(self,spec,config=None,**kwargs):
        from .robustness.services import assess_robustness
        return assess_robustness(spec,config,workspace=self,**kwargs)
    def stress_policy(self,spec,config=None,**kwargs):
        from .robustness.services import stress_policy
        return stress_policy(spec,config,workspace=self,**kwargs)
    def restate_execution(self,result,spec,config=None,**kwargs):
        from .execution.restatement import restate_execution
        return restate_execution(self.open(result) if isinstance(result,str) else result,spec,config,workspace=self,**kwargs)

    def freeze_robustness(self,result,claims,*,request_id=None,**kwargs):
        from .robustness.services import freeze_robustness
        from .investigation_storage import write_packet
        from contextlib import closing
        result=self.open(result) if isinstance(result,str) else result
        frozen=freeze_robustness(result,claims,**kwargs)
        with self.catalog.operation():
            operation,previous=self.catalog.begin(request_id or uuid.uuid4().hex,frozen.content_digest,require_saving=False)
            if previous:return self.open_robustness_protocol(frozen.content_digest)
            with closing(self.catalog._connect()) as db:
                parents=[r[0] for r in db.execute("SELECT object_id FROM facts WHERE kind='assessment' AND key=?",(digest([result.data['analysis_id']]),))]
            writer=EvidenceWriter(self.path/'staging'/operation,self.catalog.config,operation)
            write_packet(writer,'robustness_protocol',[frozen.content_digest],{'protocol':frozen.to_dict(),'depends_on_objects':parents})
            writer.finish({'capture_stages':['frozen_robustness_protocol']});self.catalog.commit_capture(operation)
        return frozen

    def open_robustness_protocol(self,content_digest):
        from .robustness.contracts import FrozenRobustnessProtocol
        from .investigation_storage import read_packet
        with file_lock(self.catalog.objects_lock,False):
            facts=list(self.catalog.iter_facts('robustness_protocol',keys=[digest([content_digest])]))
            if len(facts)!=1:raise EvaluationError('Frozen robustness protocol is unavailable.','robustness_protocol_unavailable')
            return FrozenRobustnessProtocol.from_dict(read_packet(self.catalog,facts[0])['protocol'])

    def backup(self, destination): return self.catalog.backup(destination)
    @classmethod
    def restore(cls, backup, destination):
        Catalog.restore(backup, destination)
        return cls(destination)
    def deletion_preview(self, **kwargs): return self.catalog.deletion_preview(**kwargs)
    def delete(self, preview): return self.catalog.delete(preview)

    def migrate(self, backup_destination):
        return self.catalog.migrate(backup_destination)

    def evidence_tracking(self,enabled=None):
        from .evidence_use import EvidenceUseLedger
        ledger=EvidenceUseLedger(self)
        return ledger.status() if enabled is None else ledger.enable(enabled)

    def enrich_features(self,specification,config=None,*,allowed_roots=None,request_id=None,progress=None,cancel=None):
        from .feature_contracts import FeatureEnrichmentSpec
        from .investigation_history import enrich_worker
        if isinstance(specification,dict):specification=FeatureEnrichmentSpec.from_dict(specification)
        if isinstance(config,dict):config=EvaluationConfig.from_dict(config)
        config=config or EvaluationConfig()
        if self.catalog.catalog_version<2:raise EvaluationError('Explicit catalog migration with a verified backup is required.','migration_required')
        roots=tuple(str(Path(p).absolute()) for p in (allowed_roots or (Path(specification.source.path).absolute().parent,)))
        identity=compat.capture(specification.source.path,roots)[0]['sha256']
        with self.catalog.operation():
            self.catalog.reserve();operation,previous=self.catalog.begin(request_id or uuid.uuid4().hex,digest([specification.to_dict(),config.to_dict(),identity]))
            if previous:return previous
            compat.supervise(enrich_worker,(specification.to_dict(),config,roots,str(self.path),str(self.path/'staging'/operation),operation,self.catalog.config.to_dict()),config,progress=progress,cancel=cancel)
            return self.catalog.commit_capture(operation,cancel=cancel)

    def prepare_representations(self,batch,config=None,**kwargs):
        if isinstance(batch,dict):batch=PredictionBatchSpec.from_dict(batch)
        if batch.schema_version!='confidenceguard.prediction_batch_spec/2.0' or not batch.discovery_representations:raise EvaluationError('Representation preparation requires an explicit v2 prediction batch and representation declarations.')
        return self.ingest(replace(batch,operation='ingest'),config,**kwargs)

    def _cg4_previous(self,request_id,request):
        """A retry reopens immutable evidence; it does not repeat analytics."""
        def canonical(value):
            if hasattr(value,'to_dict'):return canonical(value.to_dict())
            if isinstance(value,dict):return {k:canonical(v) for k,v in value.items() if k not in {'progress','cancel','allowed_roots'}}
            if isinstance(value,(tuple,list)):return [canonical(v) for v in value]
            return value
        request_digest=digest(canonical(request))
        if request_id:
            with self.catalog.operation():previous=self.catalog.receipt(request_id,request_digest)
            if previous:return self.open(previous['assessment_id']),request_digest
        return None,request_digest

    def _cg4_save(self,result,request_id,request_digest):
        with self.catalog.operation():receipt=self.catalog.add_assessment(result,request_id=request_id,request_digest=request_digest)
        return self.open(receipt['assessment_id']) if receipt['assessment_id']!=result.data['analysis_id'] else result

    def investigate(self,spec,config=None,*,request_id=None,**kwargs):
        from .investigation import investigate
        previous,request_digest=self._cg4_previous(request_id,{'operation':'investigate','spec':spec,'config':config,'options':kwargs})
        if previous:return previous
        result=investigate(spec,config,workspace=self,request_id=('discovery:'+request_id) if request_id else None,**kwargs)
        return self._cg4_save(result,request_id,request_digest)

    def investigations(self):
        return [row for row in self.assessments() if row['methodology_id']=='failure_investigation_v1']

    def freeze_hypotheses(self,result,candidate_ids=None,*,request_id=None,**kwargs):
        from .investigation import freeze_hypotheses
        if self.catalog.catalog_version<2:raise EvaluationError('Explicit backed-up catalog migration required before retaining CG4 hypotheses.','migration_required')
        frozen=freeze_hypotheses(result,candidate_ids,**kwargs)
        with self.catalog.operation():
            operation,previous=self.catalog.begin(request_id or uuid.uuid4().hex,frozen.data['content_digest'])
            if previous:return frozen
            writer=EvidenceWriter(self.path/'staging'/operation,self.catalog.config,operation)
            from contextlib import closing
            with closing(self.catalog._connect()) as db:
                parents=[r[0] for r in db.execute("SELECT object_id FROM facts WHERE kind='assessment' AND key=?",(digest([result.data['analysis_id']]),))]
            binding=result.private.get('history_binding') or {}
            if binding.get('instance_id')==self.instance_id:parents.extend(binding.get('source_objects',()))
            from .investigation_storage import write_packet
            write_packet(writer,'hypothesis_set',[frozen.data['content_digest']],{'frozen_hypotheses':frozen.to_dict(),'depends_on_objects':sorted(set(parents))})
            writer.finish({'capture_stages':['frozen_hypothesis_set']});self.catalog.commit_capture(operation)
        return frozen

    def open_hypotheses(self,content_digest):
        from .investigation_contracts import FrozenHypothesisSet
        with file_lock(self.catalog.objects_lock,False):
            facts=list(self.catalog.iter_facts('hypothesis_set',keys=[digest([content_digest])]))
        if len(facts)!=1:raise EvaluationError('Frozen hypothesis set is unavailable.','hypothesis_unavailable')
        from .investigation_storage import read_packet
        return FrozenHypothesisSet.from_dict(read_packet(self.catalog,facts[0])['frozen_hypotheses'])

    def confirm_investigation(self,frozen,config=None,*,request_id=None,**kwargs):
        from .confirmation import confirm_investigation
        previous,request_digest=self._cg4_previous(request_id,{'operation':'confirm','frozen':frozen,'config':config,'options':kwargs})
        if previous:return previous
        result=confirm_investigation(frozen,config,workspace=self,request_id=('confirmation:'+request_id) if request_id else None,**kwargs)
        return self._cg4_save(result,request_id,request_digest)

    def retry_confirmation(self,assessment_id,*,request_id=None,**kwargs):
        from .confirmation import retry_confirmation
        previous,request_digest=self._cg4_previous(request_id,{'operation':'numerical_retry','origin':assessment_id,'options':kwargs})
        if previous:return previous
        result=retry_confirmation(self.open(assessment_id),workspace=self,request_id=('numerical:'+request_id) if request_id else None,**kwargs)
        return self._cg4_save(result,request_id,request_digest)

    def inspect_restatement_confirmation(self,assessment_id,look_id,config=None,**kwargs):
        from .confirmation import inspect_restatement_confirmation
        return inspect_restatement_confirmation(self.open(assessment_id),look_id,config,workspace=self,**kwargs)

    def restate_confirmation(self,assessment_id,look_id,config=None,*,request_id=None,**kwargs):
        from .confirmation import restate_confirmation
        previous,request_digest=self._cg4_previous(request_id,{'operation':'predeclared_confirmation_look','origin':assessment_id,'look_id':look_id,'config':config,'options':kwargs})
        if previous:return previous
        result=restate_confirmation(self.open(assessment_id),look_id,config,workspace=self,request_id=('look:'+request_id) if request_id else None,**kwargs)
        return self._cg4_save(result,request_id,request_digest)

    def replay_investigation(self,origin,spec,config=None,*,request_id=None,**kwargs):
        from .investigation_replay import replay_investigation
        previous,request_digest=self._cg4_previous(request_id,{'operation':'historical_replay','origin':origin if isinstance(origin,str) else origin.binding['analysis_digest'],'spec':spec,'config':config,'options':kwargs})
        if previous:return previous
        if isinstance(origin,str):origin=self.open(origin)
        result=replay_investigation(origin,spec,config,workspace=self,**kwargs)
        return self._cg4_save(result,request_id,request_digest)

    def restate_investigation(self,assessment_id,*,as_of,reason,request_id=None,**kwargs):
        from .investigation_replay import restatement_spec
        from .investigation_contracts import InvestigationSpec
        prior=self.open(assessment_id);spec=restatement_spec(prior,as_of,reason)
        spec=replace(spec,history={**spec.history,'workspace_path':str(self.path)})
        H_only=prior.private.get('replay_H_only',prior.data['investigation']['stage']=='confirmation')
        return self.replay_investigation(prior,spec,reason=reason,restatement=True,H_only=H_only,request_id=request_id,**kwargs)

    def annotate_investigation(self,assessment_id,text,*,references=(),request_id=None):
        from .investigation_replay import annotate_investigation
        previous,request_digest=self._cg4_previous(request_id,{'operation':'annotation','origin':assessment_id,'text':text,'references':references})
        if previous:return previous
        result=annotate_investigation(self.open(assessment_id),text,references=references)
        return self._cg4_save(result,request_id,request_digest)

    def inspect_policy_study(self,spec,config=None,**kwargs):
        from .policies import inspect_policy_study
        return inspect_policy_study(spec,config,**kwargs)

    def optimize_policies(self,spec,config=None,*,request_id=None,**kwargs):
        from .policies import optimize_policies
        previous,request_digest=self._cg4_previous(request_id,{'operation':'policy_optimize','spec':spec,'config':config,'options':kwargs})
        if previous:return previous
        result=optimize_policies(spec,config,workspace=self,request_id=('policy-selection:'+request_id) if request_id else None,**kwargs)
        return self._cg4_save(result,request_id,request_digest)

    def replay_policy(self,spec,config=None,*,request_id=None,**kwargs):
        from .policies import replay_policy
        previous,request_digest=self._cg4_previous(request_id,{'operation':'policy_replay','spec':spec,'config':config,'options':kwargs})
        if previous:return previous
        result=replay_policy(spec,config,workspace=self,request_id=('policy-replay:'+request_id) if request_id else None,**kwargs)
        return self._cg4_save(result,request_id,request_digest)

    def freeze_policy_family(self,result,policy_digests=None,*,request_id=None,**kwargs):
        from .policy_assessment import freeze_policy_family
        from .investigation_storage import write_packet
        from contextlib import closing
        if self.catalog.catalog_version<2:raise EvaluationError('Migrate explicitly before retaining policy families.','migration_required')
        frozen=freeze_policy_family(result,policy_digests,**kwargs)
        with self.catalog.operation():
            operation,previous=self.catalog.begin(request_id or uuid.uuid4().hex,frozen.data['content_digest'])
            if previous:return frozen
            parents=set((result.private.get('history_binding') or {}).get('source_objects',[]))
            with closing(self.catalog._connect()) as db:
                parents.update(row[0] for row in db.execute("SELECT object_id FROM facts WHERE kind='assessment' AND key=?",(digest([result.data['analysis_id']]),)))
            writer=EvidenceWriter(self.path/'staging'/operation,self.catalog.config,operation)
            write_packet(writer,'policy_family',[frozen.data['content_digest']],{'frozen_policy_family':frozen.to_dict(),'depends_on_objects':sorted(parents)})
            writer.finish({'capture_stages':['frozen_policy_family']});self.catalog.commit_capture(operation)
        return frozen

    def open_policy_family(self,content_digest):
        from .policy_contracts import FrozenPolicyFamily
        from .investigation_storage import read_packet
        with file_lock(self.catalog.objects_lock,False):
            facts=list(self.catalog.iter_facts('policy_family',keys=[digest([content_digest])]))
            if len(facts)!=1:raise EvaluationError('Frozen policy family is unavailable.','policy_unavailable')
            return FrozenPolicyFamily.from_dict(read_packet(self.catalog,facts[0])['frozen_policy_family'])

    def assess_policies(self,frozen,config=None,*,request_id=None,**kwargs):
        from .policy_assessment import assess_policies
        previous,request_digest=self._cg4_previous(request_id,{'operation':'policy_assess','frozen':frozen,'config':config,'options':kwargs})
        if previous:return previous
        result=assess_policies(frozen,config,workspace=self,request_id=('policy-assessment:'+request_id) if request_id else None,**kwargs)
        return self._cg4_save(result,request_id,request_digest)

    def analyze_policy_history(self,spec,config=None,*,request_id=None,**kwargs):
        from .policy_history import analyze_policy_history
        previous,request_digest=self._cg4_previous(request_id,{'operation':'policy_history','spec':spec,'config':config,'options':kwargs})
        if previous:return previous
        result=analyze_policy_history(spec,config,workspace=self,request_id=('policy-history:'+request_id) if request_id else None,**kwargs)
        return self._cg4_save(result,request_id,request_digest)

    def restate_policy_history(self,assessment_id,*,as_of,reason,request_id=None,**kwargs):
        from .policy_history import policy_restatement
        spec=policy_restatement(self.open(assessment_id),as_of,reason)
        return self.analyze_policy_history(spec,request_id=request_id,**kwargs)

    def policy_assessments(self):
        return [row for row in self.assessments() if row['methodology_id']=='policy_selection_v1']

    def preview_policy_assessment(self,result,assessment,**kwargs):
        from .policy_assessment import preview_policy_assessment
        return preview_policy_assessment(self.open(result) if isinstance(result,str) else result,assessment,**kwargs)

    def inspect_policy_assessment(self,frozen,config=None,**kwargs):
        from .policy_assessment import inspect_policy_assessment
        return inspect_policy_assessment(frozen,config,workspace=self,**kwargs)

    def inspect_policy_restatement(self,assessment_id,look_id,config=None,**kwargs):
        from .policy_assessment import inspect_policy_restatement
        return inspect_policy_restatement(self.open(assessment_id),look_id,config,workspace=self,**kwargs)

    def restate_policy_assessment(self,assessment_id,look_id,config=None,*,request_id=None,**kwargs):
        from .policy_assessment import restate_policy_assessment
        previous,request_digest=self._cg4_previous(request_id,{'operation':'policy_scheduled_look','assessment':assessment_id,'look':look_id,'config':config,'options':kwargs})
        if previous:return previous
        result=restate_policy_assessment(self.open(assessment_id),look_id,config,workspace=self,request_id=request_id,**kwargs)
        return self._cg4_save(result,request_id,request_digest)
