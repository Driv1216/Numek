"""Canonical JSON identity, byte-compatible with ConfidenceGuard.

``digest`` reproduces ``confidenceguard.contracts.digest`` exactly and
``serialized`` reproduces ``confidenceguard.history_storage.serialized``. The
platform must not import ConfidenceGuard, so both are restated here and a test
pins their equivalence. Changing either breaks every historical fact identity.
"""
import hashlib
import json
import math
from pathlib import Path


def exact(value):
    if isinstance(value, dict):
        return {str(k): exact(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [exact(v) for v in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, int) and not isinstance(value, bool) and abs(value) > 2**53 - 1:
        return str(value)
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError('Nonfinite JSON requires a value_state.')
    return value


def canonical_bytes(value):
    return json.dumps(exact(value), sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def encode_numbers(value):
    if isinstance(value, float) and not math.isfinite(value):
        return {'__cg_number__': 'positive_infinity' if value > 0 else 'negative_infinity' if value < 0 else 'undefined'}
    if isinstance(value, dict):
        return {k: encode_numbers(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [encode_numbers(v) for v in value]
    return value


def serialized(value):
    return json.dumps(encode_numbers(value), sort_keys=True, ensure_ascii=True, separators=(',', ':'), allow_nan=False).encode()


def strict_json(text):
    """Parse JSON rejecting duplicate keys and nonfinite numbers."""
    def pairs(items):
        result = {}
        for k, v in items:
            if k in result:
                raise ValueError('Duplicate JSON object key.')
            result[k] = v
        return result

    def reject(_value):
        raise ValueError('Nonfinite JSON is unsupported.')

    if isinstance(text, (bytes, bytearray, memoryview)):
        text = bytes(text).decode('utf-8')
    return json.loads(text, object_pairs_hook=pairs, parse_constant=reject)


def fact_digest_of(record):
    """Logical digest of a fact record (the record without its own digest)."""
    body = {k: v for k, v in record.items() if k != 'fact_digest'}
    return digest(body)
