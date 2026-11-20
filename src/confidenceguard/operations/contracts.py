"""Source contracts: what a producer may send, how each row is checked, and how it maps to CG3 evidence.

A contract (versioned per source) declares:

``format``      ``csv`` or ``jsonl``
``fields``      the permitted fields. Anything else is dropped at parse time and only
                counted (minimization); values of undeclared fields never reach storage.
                Each field: ``type`` (string, number, integer, boolean, timestamp),
                ``required``, and optional ``vocabulary``, ``minimum``/``maximum``,
                ``probability`` (a value in [0, 1]), ``identity`` (never empty: keys).
``batch``       a CG3 ``PredictionBatchSpec`` template whose single source is the batch
                itself (its ``path`` is filled per batch). It maps rows to CG3 identities,
                so publication reuses CG3's identity, correction and dedup rules unchanged.
``event_time``  the opportunity-time field (watermarks and lateness).
``identity``    optional fields carrying the serving model's declared identity
                (``model_id``, ``model_version``, ``artifact_digest``).
``probability_sums``  optional groups of probability fields that must sum to 1.

Row checks are deterministic violations (standing D). A failing row is quarantined
with its reasons and offending field names, never its values.
"""
import json
import math
from dataclasses import dataclass

from ..contracts import EvaluationError, digest

TYPES = ('string', 'number', 'integer', 'boolean', 'timestamp')
FORMATS = ('csv', 'jsonl')
SOURCE_ID = 'rows'
MAX_FIELDS = 512


@dataclass(frozen=True)
class SourceContract:
    format: str
    fields: dict
    batch: dict
    event_time: str | None = None
    identity: dict | None = None
    probability_sums: tuple = ()

    @classmethod
    def from_dict(cls, value):
        if not isinstance(value, dict) or set(value) - {'format', 'fields', 'batch', 'event_time', 'identity', 'probability_sums'}:
            raise EvaluationError('Unknown source contract fields.', 'invalid_contract')
        contract = cls(value.get('format', 'csv'), value.get('fields') or {}, value.get('batch') or {}, value.get('event_time'),
                       value.get('identity'), tuple(tuple(g) for g in value.get('probability_sums', ())))
        contract.validate()
        return contract

    def to_dict(self):
        return {'format': self.format, 'fields': self.fields, 'batch': self.batch, 'event_time': self.event_time,
                'identity': self.identity, 'probability_sums': [list(g) for g in self.probability_sums]}

    @property
    def digest(self):
        return digest(self.to_dict())

    def validate(self):
        if self.format not in FORMATS:
            raise EvaluationError('Source format must be csv or jsonl.', 'invalid_contract')
        if not self.fields or len(self.fields) > MAX_FIELDS:
            raise EvaluationError('Declare between one and 512 permitted fields.', 'invalid_contract')
        for name, rule in self.fields.items():
            if not isinstance(name, str) or not name or not isinstance(rule, dict):
                raise EvaluationError('Invalid field declaration.', 'invalid_contract')
            if rule.get('type', 'string') not in TYPES:
                raise EvaluationError(f'Unsupported field type for {name}.', 'invalid_contract')
            unknown = set(rule) - {'type', 'required', 'vocabulary', 'minimum', 'maximum', 'probability', 'identity'}
            if unknown:
                raise EvaluationError(f'Unknown rule for {name}.', 'invalid_contract')
        for field in [self.event_time, *((self.identity or {}).values()), *(f for g in self.probability_sums for f in g)]:
            if field is not None and field not in self.fields:
                raise EvaluationError(f'Contract references undeclared field {field}.', 'invalid_contract')
        self.batch_spec('/contract/validation.csv')               # the CG3 mapping must parse

    def batch_spec(self, path):
        """The CG3 batch for one received batch whose minimized rows are at ``path``."""
        from ..history_contracts import PredictionBatchSpec
        value = json.loads(json.dumps(self.batch))
        evaluation = value.get('evaluation') or {}
        sources = evaluation.get('sources') or []
        if len(sources) != 1 or sources[0].get('id') != SOURCE_ID:
            raise EvaluationError(f"The batch template must have exactly one source with id '{SOURCE_ID}'.", 'invalid_contract')
        sources[0].update(path=str(path), format='csv')
        try:
            return PredictionBatchSpec.from_dict(value)
        except EvaluationError as exc:
            raise EvaluationError('The batch template is not a valid CG3 prediction batch: ' + str(exc), 'invalid_contract') from exc


def _number(value):
    if isinstance(value, bool):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _check(rule, value):
    """Return a reason code, or None if the value satisfies the field rule."""
    kind = rule.get('type', 'string')
    if kind in ('number', 'integer'):
        number = _number(value)
        if number is None or (kind == 'integer' and not float(number).is_integer()):
            return 'invalid_type'
        if rule.get('probability') and not 0 <= number <= 1:
            return 'invalid_probability'
        if rule.get('minimum') is not None and number < rule['minimum'] or rule.get('maximum') is not None and number > rule['maximum']:
            return 'out_of_range'
    elif kind == 'boolean':
        if str(value).strip().lower() not in ('true', 'false', '1', '0'):
            return 'invalid_type'
    elif kind == 'timestamp':
        from ..compat import clock
        from ..contracts import ClockSpec
        _tick, state = clock(value, ClockSpec('value'))
        if state != 'valid':
            return 'invalid_timestamp'
    if rule.get('vocabulary') is not None and str(value) not in {str(v) for v in rule['vocabulary']}:
        return 'outside_vocabulary'
    return None


def check_rows(contract, rows):
    """Minimize and check rows. Returns (accepted, quarantined, dropped_field_counts).

    ``accepted`` rows keep only declared fields; ``quarantined`` is
    [(ordinal, reasons, fields, minimized_row)]; dropped counts are per undeclared
    field name (values are never kept).
    """
    accepted, quarantined, dropped = [], [], {}
    declared = contract.fields
    for ordinal, row in enumerate(rows):
        for name in row:
            if name not in declared:
                dropped[name] = dropped.get(name, 0) + 1
        minimized = {name: row.get(name) for name in declared if name in row}
        reasons, fields = [], []
        for name, rule in declared.items():
            value = minimized.get(name)
            empty = value is None or (isinstance(value, str) and value.strip() == '')
            if empty:
                if rule.get('required') or rule.get('identity'):
                    reasons.append('missing_identity' if rule.get('identity') else 'missing_required')
                    fields.append(name)
                continue
            reason = _check(rule, value)
            if reason:
                reasons.append(reason)
                fields.append(name)
        for group in contract.probability_sums:
            values = [_number(minimized.get(f)) for f in group]
            if all(v is not None for v in values) and abs(sum(values) - 1) > 1e-6:
                reasons.append('invalid_probability_sum')
                fields.extend(group)
        if reasons:
            quarantined.append((ordinal, sorted(set(reasons)), sorted(set(fields)), minimized))
        else:
            accepted.append(minimized)
    return accepted, quarantined, dropped


def parse(contract, body, max_rows=5_000_000):
    """Parse a received body into row dicts (values as received; no type coercion)."""
    import csv
    import io
    try:
        text = body.decode('utf-8-sig')
    except UnicodeDecodeError as exc:
        raise EvaluationError('Batch is not UTF-8 text.', 'invalid_batch') from exc
    rows = []
    if contract.format == 'csv':
        reader = csv.DictReader(io.StringIO(text))
        if reader.fieldnames is None:
            raise EvaluationError('Batch has no header.', 'invalid_batch')
        if len(set(reader.fieldnames)) != len(reader.fieldnames):
            raise EvaluationError('Batch header repeats a field.', 'invalid_batch')
        for row in reader:
            if None in row:
                raise EvaluationError('Batch row has more values than its header.', 'invalid_batch')
            rows.append(row)
            if len(rows) > max_rows:
                raise EvaluationError('Batch exceeds the row admission.', 'batch_too_large')
    else:
        for number, line in enumerate(text.splitlines(), 1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise EvaluationError(f'Batch line {number} is not JSON.', 'invalid_batch') from exc
            if not isinstance(value, dict):
                raise EvaluationError(f'Batch line {number} is not an object.', 'invalid_batch')
            rows.append({k: (json.dumps(v) if isinstance(v, (dict, list)) else v) for k, v in value.items()})
            if len(rows) > max_rows:
                raise EvaluationError('Batch exceeds the row admission.', 'batch_too_large')
    return rows


def to_csv(contract, rows):
    """Minimized accepted rows as CSV (declared field order) for the CG3 capture path."""
    import csv
    import io
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=list(contract.fields), lineterminator='\n')
    writer.writeheader()
    for row in rows:
        writer.writerow({k: ('' if row.get(k) is None else ('true' if row.get(k) is True else 'false' if row.get(k) is False else row.get(k)))
                         for k in contract.fields})
    return out.getvalue().encode()
