"""Opt-in public workspace facade. All clients share these application services."""
from dataclasses import replace
from pathlib import Path
import copy
import json
import os
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
        request_digest = digest({'batch': batch.to_dict(), 'config': config.to_dict(), 'sources': identities})
        with self.catalog.operation():
            self.catalog.reserve()
            operation, previous = self.catalog.begin(request_id or uuid.uuid4().hex, request_digest)
            if previous: return previous
            stage = self.path / 'staging' / operation
            descriptor = CaptureDescriptor(str(stage), operation, self.catalog.config.to_dict(), batch.to_dict())
            result = None
            try:
                if batch.operation == 'ingest':
                    compat.supervise(ingest_worker, (batch.to_dict(), config, roots, descriptor), config, progress=progress, cancel=cancel)
                else:
                    from .engine import evaluate
                    from .methods import study, fit_methods, apply_methods
                    operation_service = {'evaluate': evaluate, 'study': study, 'fit': fit_methods, 'apply': apply_methods}[batch.operation]
                    result = operation_service(batch.evaluation, config, allowed_roots=roots, progress=progress, cancel=cancel, _capture=descriptor)
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
                result['population_preview']=compat.supervise(_inspect_history,(str(self.path),frozen,sequence,frozen.as_of or now()),frozen.config).data
        return result

    def analyze(self, spec, *, request_id=None, progress=None, cancel=None, expected_fingerprint=None):
        if isinstance(spec, dict): spec = LongitudinalSpec.from_dict(spec)
        request_digest = digest({'analysis_request': spec.to_dict()})
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
            result = analyze(self.path, spec, progress=progress, cancel=cancel)
            if spec.restates:
                result.data['history']['restatement_changes'] = self._restatement_delta(prior, result)
                result.seal()
            receipt = self.catalog.add_assessment(result, request_id=request_id, cancel=cancel, request_digest=request_digest)
            return result

    def restate(self, assessment_id, *, as_of=None, reason, outcome_only=True, **kwargs):
        prior = self.open(assessment_id)
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
        with self.catalog.operation(): return self.catalog.add_assessment(result, request_id=request_id)

    def backup(self, destination): return self.catalog.backup(destination)
    @classmethod
    def restore(cls, backup, destination):
        Catalog.restore(backup, destination)
        return cls(destination)
    def deletion_preview(self, **kwargs): return self.catalog.deletion_preview(**kwargs)
    def delete(self, preview): return self.catalog.delete(preview)
