"""Evidence codecs.

``utf8_jsonl_v1`` is the legacy CG3 format: one serialized record per byte
range, with per-record digest checks kept exactly as v2 performs them.

``observation_facts_parquet_v1`` stores the *same logical records*: each row
holds the legacy serialization of one record, so decoding returns exactly the
dictionary the JSONL reader would. Logical digests are verified when the
object is written (publication and compaction); on read, the object's SHA-256
over the consumed bytes establishes integrity.
"""
import io

from ..canonical import digest, fact_digest_of, serialized, strict_json
from ..errors import IntegrityFailure, PlatformError

JSONL = 'utf8_jsonl_v1'
OBSERVATIONS = 'observation_facts_parquet_v1'
BLOB = 'opaque_artifact_bytes_v1'
RAW_BATCH = 'encrypted_raw_batch_v1'
FACT_CODECS = (JSONL, OBSERVATIONS)
COMPACTABLE = (OBSERVATIONS,)
ROW_GROUP = 65536


def verify_record(record, *, key=None, fact_digest=None):
    """The v2 per-record checks: digest of the body, and the key of the identity."""
    computed = fact_digest_of(record)
    if record.get('fact_digest') != computed or (fact_digest is not None and fact_digest != computed):
        raise IntegrityFailure('Historical fact identity differs.')
    if key is not None and 'identity' in record and digest(record['identity']) != key:
        raise IntegrityFailure('Historical fact identity differs.')
    return computed


# Legacy JSONL -------------------------------------------------------------

def decode_jsonl_range(data, offset, length, *, max_record_bytes, key=None, fact_digest=None):
    raw = data[offset:offset + length]
    if len(raw) != length or length > max_record_bytes:
        raise IntegrityFailure('Invalid retained record location.')
    record = strict_json(raw)
    verify_record(record, key=key, fact_digest=fact_digest)
    return record


def encode_jsonl(records):
    """Encode records as legacy JSONL; returns (bytes, [(offset, length)])."""
    out, locations, offset = io.BytesIO(), [], 0
    for record in records:
        verify_record(record)
        line = serialized(record) + b'\n'
        out.write(line)
        locations.append((offset, len(line) - 1))
        offset += len(line)
    return out.getvalue(), locations


# Observation Parquet -------------------------------------------------------

def encode_observations(records):
    """Encode fact records into one Parquet object; returns (bytes, row indexes)."""
    import pyarrow as pa
    import pyarrow.parquet as pq

    kinds, keys, revisions, digests, bodies = [], [], [], [], []
    for record in records:
        computed = verify_record(record)
        kinds.append(record['kind'])
        keys.append(record['key'])
        revisions.append(str(record['revision']))
        digests.append(computed)
        bodies.append(serialized(record).decode('ascii'))
    table = pa.table({
        'kind': pa.array(kinds, pa.string()),
        'key': pa.array(keys, pa.string()),
        'revision': pa.array(revisions, pa.string()),
        'fact_digest': pa.array(digests, pa.string()),
        'record': pa.array(bodies, pa.large_string()),
    })
    sink = io.BytesIO()
    pq.write_table(table, sink, compression='zstd', row_group_size=ROW_GROUP)
    return sink.getvalue(), list(range(len(records)))


def decode_observations(data):
    """Decode a verified Parquet buffer into its records (row order preserved)."""
    import pyarrow as pa
    import pyarrow.parquet as pq

    try:
        table = pq.read_table(pa.BufferReader(data))
    except Exception as exc:  # malformed bytes that nevertheless matched a hash
        raise IntegrityFailure('Stored evidence could not be decoded.') from exc
    records = []
    for body, kind, key, revision, fact_digest in zip(table['record'].to_pylist(), table['kind'].to_pylist(),
                                                     table['key'].to_pylist(), table['revision'].to_pylist(),
                                                     table['fact_digest'].to_pylist()):
        record = strict_json(body)
        if (record.get('kind') != kind or record.get('key') != key or str(record.get('revision')) != revision
                or record.get('fact_digest') != fact_digest):
            raise IntegrityFailure('Columnar fact metadata differs from its record.')
        records.append(record)
    return records


def decode(codec, data, locators, *, max_record_bytes=8 * 1024**2):
    """Decode the records at ``locators`` [(locator_kind, a, b, key, fact_digest)] from one object."""
    if codec == JSONL:
        return [decode_jsonl_range(data, a, b, max_record_bytes=max_record_bytes, key=key, fact_digest=fd)
                for kind, a, b, key, fd in locators]
    if codec == OBSERVATIONS:
        rows = decode_observations(data)
        out = []
        for kind, a, _b, key, fd in locators:
            if kind != 'row' or not 0 <= a < len(rows):
                raise IntegrityFailure('Invalid columnar row location.')
            record = rows[a]
            if record['key'] != key or record['fact_digest'] != fd:
                raise IntegrityFailure('Historical fact identity differs.')
            out.append(record)
        return out
    raise PlatformError('Objects of this codec do not contain facts.', 'unsupported_codec')
