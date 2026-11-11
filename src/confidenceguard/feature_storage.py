"""Protected immutable columnar feature and non-object dense-vector codecs.

Logical envelopes remain encoding-independent. Only parent-owned staging may be
written; catalog publication supplies visibility, dependencies and deletion.
"""
import hashlib
import json
import os
from pathlib import Path
import uuid
from .contracts import EvaluationError, digest, strict_json
from .history_storage import private_file, private_directory, file_digest, fsync_directory

CODECS={'utf8_jsonl_v1':'.jsonl','typed_feature_rows_v1':'.parquet','dense_vectors_npy_v1':'.npy',
        'opaque_artifact_bytes_v1':'.cgblob'}
CELL_FIELDS=('kind','state','lexical','canonical','available_ns','effective_ns','availability_state','source_type')


def extension(codec):
    try:return CODECS[codec]
    except KeyError:raise EvaluationError('Unsupported protected evidence codec.','unsupported_codec')


def write_features(directory, envelopes, *, field_ids, check=lambda *args:None, batch_bytes=32*1024**2, shard_bytes=128*1024**2):
    import pyarrow as pa
    import pyarrow.parquet as pq
    directory=private_directory(directory); field_ids=tuple(sorted(field_ids))
    if len(field_ids)>4096:raise EvaluationError('Feature schema exceeds column admission.','feature_schema_limit')
    cell=pa.struct([(key,pa.string()) for key in CELL_FIELDS])
    schema=pa.schema([('envelope',pa.string()),*[(f'f{i}',cell) for i in range(len(field_ids))]],
                     metadata={b'cg_codec':b'typed_feature_rows_v1',b'cg_fields':json.dumps(field_ids).encode()})
    objects=[]; locations=[]; writer=None; stream=None; pending=[]; size=0; shard_size=0; group=0
    def finish():
        nonlocal writer,stream
        if writer is not None:
            writer.close(); stream.flush();os.fsync(stream.fileno());stream.close()
            sha,n=file_digest(path)
            objects.append({'id':oid,'encoding':'typed_feature_rows_v1','kind':'feature','sha256':sha,'bytes':n,'records':records})
            writer=stream=None
    def flush():
        nonlocal writer,stream,pending,size,shard_size,group,path,oid,records
        if not pending:return
        if writer is None:
            oid=uuid.uuid4().hex;path=directory/(oid+'.parquet');stream=private_file(path)
            writer=pq.ParquetWriter(stream,schema,compression='zstd',compression_level=3,version='2.6',use_dictionary=True)
            group=0;records=0;shard_size=0
        table=pa.Table.from_pylist([p[0] for p in pending],schema=schema)
        writer.write_table(table,row_group_size=len(pending))
        for i,(_,envelope) in enumerate(pending):
            locations.append({'kind':envelope['kind'],'key':envelope['key'],'revision':envelope['revision'],
                              'fact_digest':envelope['fact_digest'],'object_id':oid,'offset':group,'length':i+1,
                              'locator_kind':'parquet_row','row_group':group,'row_index':i})
        group+=1;records+=len(pending);shard_size+=table.nbytes
        check('feature shard',table.nbytes);pending=[];size=0
        if shard_size>=shard_bytes:finish()
    path=None;oid=None;records=0
    try:
        for envelope in envelopes:
            envelope=dict(envelope);payload=dict(envelope['payload']);cells=payload.pop('values',{})
            header={**envelope,'payload':payload}
            row={'envelope':json.dumps(header,sort_keys=True,separators=(',',':'),ensure_ascii=True)}
            for i,fid in enumerate(field_ids):row[f'f{i}']={k:cells[fid].get(k) for k in CELL_FIELDS} if fid in cells else None
            cost=len(row['envelope'])+sum(sum(len(str(v)) for v in c.values() if v is not None) for c in cells.values())
            if cost>8*1024**2:raise EvaluationError('Feature row exceeds record admission.','history_record_limit')
            if pending and (size+cost>batch_bytes or len(pending)>=65536):flush()
            pending.append((row,envelope));size+=cost
        flush();finish();fsync_directory(directory)
    finally:
        if writer is not None:writer.close()
        if stream is not None:stream.close()
    return objects,locations


def read_features(path, *, field_ids=None, locations=None, check=lambda *args:None):
    import pyarrow.parquet as pq
    with private_file(path,'rb') as stream:
        reader=pq.ParquetFile(stream,thrift_string_size_limit=16*1024**2,thrift_container_size_limit=100000,arrow_extensions_enabled=False)
        meta=reader.schema_arrow.metadata or {}
        if meta.get(b'cg_codec')!=b'typed_feature_rows_v1':raise EvaluationError('Feature codec differs.','evidence_changed')
        ids=strict_json(meta.get(b'cg_fields',b'[]'))
        if not isinstance(ids,list) or len(ids)>4096 or len(set(ids))!=len(ids):raise EvaluationError('Invalid feature schema.','feature_schema_limit')
        selected=set(ids if field_ids is None else field_ids)
        if selected-set(ids):raise EvaluationError('Feature was not retained.','feature_not_retained')
        columns=['envelope',*[f'f{i}' for i,fid in enumerate(ids) if fid in selected]]
        for group in range(reader.num_row_groups):
            info=reader.metadata.row_group(group)
            if info.num_rows>65536 or info.total_byte_size>256*1024**2:raise EvaluationError('Decoded feature row group exceeds admission.','feature_group_limit')
            if locations is not None and group not in locations:continue
            for index,row in enumerate(reader.read_row_group(group,columns=columns,use_threads=False).to_pylist()):
                if locations is not None and index not in locations[group]:continue
                envelope=strict_json(row.pop('envelope'));envelope['payload']['values']={fid:row[f'f{i}'] for i,fid in enumerate(ids) if fid in selected and row.get(f'f{i}') is not None}
                if field_ids is None:
                    expected=envelope.pop('fact_digest',None)
                    if expected!=digest(envelope) or digest(envelope['identity'])!=envelope['key']:raise EvaluationError('Feature row identity differs.','evidence_changed')
                    envelope['fact_digest']=expected
                envelope['_row_group']=group;envelope['_row_index']=index
                yield envelope
            check('feature reconstruction')


def validate_matrix(path, *, max_dimensions=16384, max_rows=10000000, max_bytes=8*1024**3):
    import numpy as np
    # Parse bounded headers before mmap; never allow NumPy object deserialization.
    with open(path,'rb') as stream:
        version=np.lib.format.read_magic(stream)
        if version not in {(1,0),(2,0)}:raise EvaluationError('Only bounded NPY v1/v2 numeric input is supported.','vector_format')
        header=np.lib.format.read_array_header_1_0 if version==(1,0) else np.lib.format.read_array_header_2_0
        shape,fortran,dtype=header(stream,max_header_size=10000)
        offset=stream.tell()
        if len(shape)!=2 or fortran or dtype.kind!='f' or dtype.itemsize not in (4,8) or dtype.hasobject:
            raise EvaluationError('Vectors require a C-order float32/float64 matrix.','vector_dtype')
        rows,dimensions=shape
        if type(rows) is not int or type(dimensions) is not int or not 0<rows<=max_rows or not 0<dimensions<=max_dimensions:raise EvaluationError('Vector shape exceeds admission.','vector_shape')
        size=rows*dimensions*dtype.itemsize
        if size>max_bytes or os.fstat(stream.fileno()).st_size!=offset+size:raise EvaluationError('Vector byte length differs.','vector_size')
    return {'rows':rows,'dimensions':dimensions,'dtype':dtype.str,'offset':offset,'bytes':size}


def write_vectors(directory, matrix, *, check=lambda *args:None, shard_bytes=64*1024**2):
    import numpy as np
    directory=private_directory(directory);values=np.asarray(matrix)
    if values.ndim!=2 or values.dtype.kind!='f' or values.dtype.itemsize not in (4,8):raise EvaluationError('Invalid dense vectors.')
    dtype=np.dtype('<f'+str(values.dtype.itemsize));step=max(1,shard_bytes//max(1,values.shape[1]*dtype.itemsize));objects=[];locations=[]
    for start in range(0,len(values),step):
        block=np.ascontiguousarray(values[start:start+step],dtype=dtype)
        if not np.isfinite(block).all():raise EvaluationError('Stored vector rows must be finite.','invalid_vector')
        oid=uuid.uuid4().hex;path=directory/(oid+'.npy')
        with private_file(path) as stream:
            np.lib.format.write_array(stream,block,version=(1,0),allow_pickle=False);stream.flush();os.fsync(stream.fileno())
        sha,size=file_digest(path)
        objects.append({'id':oid,'kind':'vector','encoding':'dense_vectors_npy_v1','sha256':sha,'bytes':size,'records':len(block)})
        for i,row in enumerate(block):
            locations.append({'object_id':oid,'row':i,'vector_digest':hashlib.sha256(dtype.str.encode()+row.tobytes()).hexdigest()})
        check('vector shard',block.nbytes)
    fsync_directory(directory);return objects,locations
