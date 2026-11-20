"""Deployment identity standings (plan G.9, R2.7). Each standing is recorded separately, with its evidence.

``declared``                 what the producer says it served (batch header and/or identity fields)
``registered``               the declared identity equals the deployment's registered identity
``spec_compatible``          the source contract's task (kind, classes, positive class) matches the
                             registered predictor's
``sampled_output_consistent`` a keyed-random sample of logged inputs, replayed through the registered
                             CG6 predictor, reproduces the logged outputs within tolerance; the mismatch
                             rate carries a one-sided Clopper-Pearson upper bound, and rows that cannot
                             be replayed are counted, never assumed consistent
``customer_signed_statement_verified``  an Ed25519 signature over a canonical statement verifies against
                             the deployment's registered customer key. Trust rests on the customer's
                             signing process; hardware/TEE runtime attestation is not implemented and
                             never inferred.

Agreement on samples is never attestation: other predictors may agree on them.
"""
import base64
import hashlib
import hmac
import json
import uuid

from psycopg.types.json import Jsonb

from ..contracts import EvaluationError, digest
from . import registry

IDENTITY_KEYS = ('model_id', 'model_version', 'artifact_digest')


def _record(conn, scope, deployment_id, standing, outcome, evidence, *, period=(None, None)):
    conn.execute('''INSERT INTO ops_identity_standings(org_id, id, deployment_id, standing, outcome, period_start, period_end, evidence)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)''',
                 (scope.org_id, uuid.uuid4(), deployment_id, standing, outcome, period[0], period[1], Jsonb(evidence)))


def record_batch_identity(conn, scope, deployment, declared, problem, batch_row):
    """``declared`` and ``registered`` standings for one processed batch (in its final transaction)."""
    period = (batch_row['received_at'], batch_row['received_at'])
    evidence = {'batch': str(batch_row['id']), 'source': batch_row['source_id']}
    if problem is not None:
        _record(conn, scope, deployment['id'], 'declared', 'failed', {**evidence, 'reason': problem}, period=period)
        return
    declared = {k: v for k, v in (declared or {}).items() if k in IDENTITY_KEYS and v not in (None, '')}
    if not declared:
        _record(conn, scope, deployment['id'], 'declared', 'not_evaluable', {**evidence, 'reason': 'no_identity_declared'}, period=period)
        return
    _record(conn, scope, deployment['id'], 'declared', 'established', {**evidence, 'identity': declared}, period=period)
    registered = {k: v for k, v in (deployment['registered_identity'] or {}).items() if k in IDENTITY_KEYS}
    shared = sorted(set(declared) & set(registered))
    if not shared:
        _record(conn, scope, deployment['id'], 'registered', 'not_evaluable', {**evidence, 'reason': 'nothing_comparable'}, period=period)
    else:
        differing = [k for k in shared if str(declared[k]) != str(registered[k])]
        _record(conn, scope, deployment['id'], 'registered', 'failed' if differing else 'established',
                {**evidence, 'compared': shared, 'differing': differing}, period=period)


def check_spec_compatibility(installation, deployment_id, source_id):
    """Compare a source contract's CG3 task with the registered predictor's task; records the standing."""
    from .contracts import SourceContract
    dep = registry.deployment(installation, deployment_id)
    src = registry.source(installation, source_id)
    task = SourceContract.from_dict(src['contract']).batch_spec('/contract/check.csv').base.task.to_dict()
    predictor = (dep['registered_identity'] or {}).get('predictor_spec')
    if not predictor:
        outcome, evidence = 'not_evaluable', {'reason': 'no_registered_predictor'}
    else:
        registered = predictor.get('task') or {}
        fields = ('kind', 'classes', 'positive_class')
        differing = [f for f in fields if (task.get(f) or None) != (registered.get(f) or None)]
        outcome = 'failed' if differing else 'established'
        evidence = {'source': source_id, 'contract_version': src['version'], 'compared': list(fields), 'differing': differing}
    with installation.db.transaction() as conn:
        _record(conn, installation.scope, deployment_id, 'spec_compatible', outcome, evidence)
    return {'standing': 'spec_compatible', 'outcome': outcome, **evidence}


def _canonical(statement):
    return json.dumps(statement, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()


def verify_signed_statement(installation, deployment_id, statement, signature):
    """Verify a customer-signed statement ``{deployment, artifact_digest, period_start, period_end}``."""
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    dep = registry.deployment(installation, deployment_id)
    required = {'deployment', 'artifact_digest', 'period_start', 'period_end'}
    if not isinstance(statement, dict) or set(statement) != required:
        raise EvaluationError('A signed statement names exactly deployment, artifact_digest, period_start, period_end.',
                              'invalid_statement')
    if statement['deployment'] != deployment_id:
        raise EvaluationError('The statement names another deployment.', 'invalid_statement')
    signature = base64.b64decode(signature) if isinstance(signature, str) else signature
    key = dep['attestation_public_key']
    evidence = {'statement_digest': hashlib.sha256(_canonical(statement)).hexdigest(), 'statement': statement,
                'trust': 'customer_signing_process', 'runtime_attestation': 'not_implemented'}
    if key is None:
        outcome, evidence['reason'] = 'not_evaluable', 'no_registered_customer_key'
    else:
        evidence['key_fingerprint'] = hashlib.sha256(bytes(key)).hexdigest()
        try:
            Ed25519PublicKey.from_public_bytes(bytes(key)).verify(signature, _canonical(statement))
            outcome = 'established'
        except (InvalidSignature, ValueError):
            outcome, evidence['reason'] = 'failed', 'signature_does_not_verify'
    from ..history_contracts import instant
    from datetime import datetime, timezone
    period = tuple(datetime.fromtimestamp(instant(statement[k]) / 1e9, tz=timezone.utc) for k in ('period_start', 'period_end'))
    with installation.db.transaction() as conn:
        _record(conn, installation.scope, deployment_id, 'customer_signed_statement_verified', outcome, evidence, period=period)
    return {'standing': 'customer_signed_statement_verified', 'outcome': outcome, **evidence}


def clopper_pearson_upper(failures, n, confidence=0.95):
    from scipy.stats import beta
    if n == 0:
        return 1.0
    return 1.0 if failures >= n else float(beta.ppf(confidence, failures + 1, n - failures))


def audit_outputs(installation, deployment_id, rows, *, key_columns, logged_outputs, sample_size=200, tolerance=1e-6,
                  max_mismatch_rate=0.01, confidence=0.95, scratch, config=None):
    """Sampled output-consistency audit of logged rows against the registered CG6 predictor.

    ``rows`` are logged rows (inputs, keys and logged outputs); ``logged_outputs`` maps an output channel
    to the logged field(s) (``{'probabilities': ['p_no', 'p_yes']}``). The sample is keyed-random
    (HMAC of the event key under a per-deployment secret), independent of outputs.
    """
    from pathlib import Path
    from .. import ExecutionSpec, PredictorSpec, SourceSpec, execute_predictor
    from ..execution_context import InProcessContext, using
    dep = registry.deployment(installation, deployment_id)
    spec = (dep['registered_identity'] or {}).get('predictor_spec')
    if not spec:
        raise EvaluationError('No registered predictor to replay.', 'no_registered_predictor')
    predictor = PredictorSpec.from_dict(spec)
    secret_name = f'ops-audit/{installation.scope.org_id.hex}/{deployment_id}'
    if not installation.secrets.exists(secret_name):
        import secrets as _secrets
        installation.secrets.put(secret_name, _secrets.token_bytes(32))
    secret = installation.secrets.get(secret_name)
    keyed = sorted(rows, key=lambda r: hmac.new(secret, json.dumps([r.get(c) for c in key_columns]).encode(), 'sha256').digest())
    sample = keyed[:sample_size]
    inputs = [f.column for f in predictor.inputs]
    replayable = [r for r in sample if all(r.get(c) not in (None, '') for c in [*inputs, *key_columns])]
    not_replayable = len(sample) - len(replayable)
    mismatches, compared = 0, 0
    if replayable:
        import csv
        directory = Path(scratch)
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        path = directory / 'audit-inputs.csv'
        with path.open('w', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=sorted({*inputs, *key_columns}))
            writer.writeheader()
            for r in replayable:
                writer.writerow({c: r.get(c) for c in writer.fieldnames})
        execution = ExecutionSpec((predictor,), (SourceSpec('input', str(path)),), 'input', tuple(key_columns),
                                  f'audit-{deployment_id}')
        with using(InProcessContext()):
            result = execute_predictor(execution, config or {'free_disk_bytes': 1}, allowed_roots=(str(directory),))
        replayed = {}
        for line in Path(result.private['output_artifact']['path']).read_text().splitlines():
            record = json.loads(line)
            replayed[record['event_key']] = record if record['execution'] == 'completed' else None
        for r in replayable:
            record = replayed.get(json.dumps([str(r.get(c)) for c in key_columns], separators=(',', ':')))
            if record is None:
                not_replayable += 1
                continue
            compared += 1
            for channel, fields in logged_outputs.items():
                fields = [fields] if isinstance(fields, str) else list(fields)
                values = record['channels'].get(channel)
                values = values if isinstance(values, list) else [values]
                logged = [float(r[f]) for f in fields]
                if len(values) != len(logged) or any(abs(a - float(b)) > tolerance for a, b in zip(logged, values)):
                    mismatches += 1
                    break
    upper = clopper_pearson_upper(mismatches, compared, confidence)
    outcome = ('failed' if mismatches else 'established' if compared and upper <= max_mismatch_rate else 'not_evaluable')
    evidence = {'sample_size': len(sample), 'compared': compared, 'mismatches': mismatches, 'not_replayable': not_replayable,
                'mismatch_rate_upper_bound': upper, 'confidence': confidence, 'tolerance': tolerance,
                'max_mismatch_rate': max_mismatch_rate, 'sampling': 'keyed_random_independent_of_outputs',
                'predictor_spec_digest': digest(spec),
                'qualification': 'Agreement on sampled inputs is not attestation; other predictors may agree on them.'}
    if outcome == 'not_evaluable':
        evidence['reason'] = 'insufficient_sample_for_the_declared_rate'
    with installation.db.transaction() as conn:
        _record(conn, installation.scope, deployment_id, 'sampled_output_consistent', outcome, evidence)
    return {'standing': 'sampled_output_consistent', 'outcome': outcome, **evidence}


def standings(installation, deployment_id):
    """Latest outcome of every standing (each with its evidence and time)."""
    with installation.db.connect() as conn:
        rows = conn.execute('''SELECT DISTINCT ON (standing) standing, outcome, evidence, recorded_at, period_start, period_end
                               FROM ops_identity_standings WHERE org_id = %s AND deployment_id = %s
                               ORDER BY standing, recorded_at DESC''', (installation.scope.org_id, deployment_id)).fetchall()
    return {r['standing']: {'outcome': r['outcome'], 'evidence': r['evidence'], 'recorded_at': r['recorded_at'].isoformat()}
            for r in rows}
