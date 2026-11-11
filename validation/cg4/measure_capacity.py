"""Bounded synthetic codec/lifecycle capacity evidence, outside product APIs."""
import argparse
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import time


def measure(n,kind,dimensions,*,progress=None):
    from confidenceguard import EvaluationConfig,ReliabilityWorkspace,WorkspaceConfig
    from confidenceguard.contracts import digest
    from confidenceguard.feature_contracts import FeatureField
    from confidenceguard.features import normalize
    from confidenceguard.feature_storage import write_features,read_features,write_vectors,validate_matrix
    from confidenceguard.history_storage import EvidenceWriter
    from confidenceguard.investigation_history import envelope
    from confidenceguard.result import Inspection
    import numpy as np
    import pyarrow as pa
    import pyarrow.parquet as pq
    import pyarrow.ipc as ipc
    root=Path(tempfile.mkdtemp(prefix='numek-cg4-capacity-',dir='/private/tmp'))
    (root/'owner.json').write_text(json.dumps({'pid':os.getpid()}))
    if progress:progress({'owned_workspace':str(root),'stage':'synthetic capacity'})
    started=time.monotonic();timings={};out={'n':n,'kind':kind,'dimensions':dimensions,'limits':EvaluationConfig().to_dict()}
    def timed(label,operation):
        wall=time.monotonic();cpu=time.process_time();value=operation();timings[label]={'seconds':time.monotonic()-wall,'CPU_seconds':time.process_time()-cpu};return value
    def check(*args):
        if progress:progress({'stage':str(args[0]) if args else 'capacity'})
    kinds=('categorical','boolean','integer','decimal','float','timestamp','text','categorical')*2
    fields=[FeatureField('f'+str(i),'f'+str(i),k) for i,k in enumerate(kinds)]
    def records():
        for i in range(n):
            tokens=(f'category-{i%100003}',str(bool(i%2)),str(2**60+i),str(i)+'.000000000000000001',repr(i/13),'2026-01-01T00:00:00Z','Synthetic lexical field '+str(i%307),'é' if i%2 else 'e\u0301')*2
            values={f.id:normalize(v if i%997 else None,f) for f,v in zip(fields,tokens)}
            yield envelope('feature',['capacity',str(i)],{'namespace':'synthetic-capacity','values':values})
    try:
        if kind=='vectors':
            source=root/'input.npy';matrix=np.lib.format.open_memmap(source,mode='w+',dtype='<f4',shape=(n,dimensions))
            rng=np.random.default_rng(20261024)
            for start in range(0,n,4096):matrix[start:start+4096]=rng.standard_normal((min(4096,n-start),dimensions),dtype=np.float32)
            matrix.flush();out['input_header']=validate_matrix(source)
            objects,locations=timed('NPY_shard_write',lambda:write_vectors(root/'vectors',matrix,check=check))
            out.update(shards=len(objects),persistent_bytes=sum(o['bytes'] for o in objects),logical_vectors=len(locations),
                       first_vector_digest=locations[0]['vector_digest'],last_vector_digest=locations[-1]['vector_digest'])
            def verify():
                count=0
                for obj in objects:
                    block=np.load(root/'vectors'/(obj['id']+'.npy'),mmap_mode='r',allow_pickle=False)
                    for start in range(0,len(block),4096):
                        length=min(4096,len(block)-start)
                        if not np.array_equal(matrix[count:count+length],block[start:start+length]):raise AssertionError('Vector reconstruction differs')
                        count+=length
                assert count==n
            timed('NPY_exact_reconstruction',verify);out['exact_reconstruction']=True
        elif kind=='lifecycle':
            ws=ReliabilityWorkspace.initialize(root/'workspace',WorkspaceConfig(saving=True,free_disk_bytes=2*1024**3))
            with ws.catalog.operation():
                operation,_=ws.catalog.begin('capacity',digest(['capacity',n]));writer=EvidenceWriter(ws.path/'staging'/operation,ws.catalog.config,operation,check)
                timed('staged_columnar_write',lambda:writer.add_features(records(),tuple(f.id for f in fields)))
                writer.finish({'synthetic_capacity_only':True});receipt=timed('verified_catalog_commit',lambda:ws.catalog.commit_capture(operation))
            timed('verified_backup',lambda:ws.backup(root/'backup'))
            restored=timed('verified_restore',lambda:ReliabilityWorkspace.restore(root/'backup',root/'restored'))
            with closing(restored.catalog._connect()) as db:out['restored_feature_facts']=db.execute("SELECT count(*) FROM facts WHERE kind='feature'").fetchone()[0]
            assert out['restored_feature_facts']==n
            preview=timed('deletion_preview',lambda:ws.deletion_preview(batch_ids=[receipt['operation_id']]))
            timed('transitive_delete',lambda:ws.delete(preview));out['lifecycle_pass']=True
        else:
            objects,locations=timed('Parquet_write',lambda:write_features(root/'parquet',records(),field_ids=[f.id for f in fields],check=check))
            del locations
            out['Parquet_bytes']=sum(v['bytes'] for v in objects)
            def reconstruct():
                h=hashlib.sha256();count=0
                for obj in objects:
                    for row in read_features(root/'parquet'/(obj['id']+'.parquet'),check=check):h.update(row['fact_digest'].encode());count+=1
                assert count==n
                return h.hexdigest()
            full=timed('Parquet_full_reconstruction',reconstruct)
            expected=hashlib.sha256()
            for row in records():expected.update(row['fact_digest'].encode())
            assert expected.hexdigest()==full;out['logical_rows_digest']=full
            def projected():
                h=hashlib.sha256();count=0
                for obj in objects:
                    for row in read_features(root/'parquet'/(obj['id']+'.parquet'),field_ids=['f0'],check=check):
                        h.update(json.dumps(row['payload']['values']['f0'],sort_keys=True).encode());count+=1
                assert count==n
                return h.hexdigest()
            projection=timed('Parquet_projected_read',projected)
            def jsonl_write():
                with (root/'rows.jsonl').open('w') as stream:
                    for row in records():stream.write(json.dumps(row,sort_keys=True,separators=(',',':'),ensure_ascii=True)+'\n')
            timed('JSONL_write',jsonl_write);out['JSONL_bytes']=(root/'rows.jsonl').stat().st_size
            def jsonl_read():
                h=hashlib.sha256()
                with (root/'rows.jsonl').open() as stream:
                    for line in stream:h.update(json.dumps(json.loads(line)['payload']['values']['f0'],sort_keys=True).encode())
                return h.hexdigest()
            assert timed('JSONL_projected_read',jsonl_read)==projection
            def arrow_write():
                sink=None
                try:
                    for obj in objects:
                        reader=pq.ParquetFile(root/'parquet'/(obj['id']+'.parquet'))
                        if sink is None:sink=ipc.new_file(str(root/'rows.arrow'),reader.schema_arrow,options=ipc.IpcWriteOptions(compression='zstd'))
                        for batch in reader.iter_batches(batch_size=8192,use_threads=False):sink.write_batch(batch)
                finally:
                    if sink:sink.close()
            timed('Arrow_IPC_zstd_write',arrow_write);out['Arrow_IPC_zstd_bytes']=(root/'rows.arrow').stat().st_size
            def arrow_read():
                h=hashlib.sha256()
                with pa.memory_map(str(root/'rows.arrow'),'r') as source:
                    reader=ipc.open_file(source)
                    for i in range(reader.num_record_batches):
                        for cell in reader.get_batch(i).select(['f0']).column(0).to_pylist():h.update(json.dumps(cell,sort_keys=True).encode())
                return h.hexdigest()
            assert timed('Arrow_IPC_zstd_projected_read',arrow_read)==projection
            out.update(exact_reconstruction=True,projected_value_parity=True,fields=len(fields),high_cardinality_values=min(n,100003))
        out['physical_peak_final_bytes']=sum(p.stat().st_size for p in root.rglob('*') if p.is_file());out['timings']=timings
        return Inspection(out,{'status':'completed','peak_workspace_bytes':out['physical_peak_final_bytes'],'seconds':time.monotonic()-started})
    finally:shutil.rmtree(root)


def main():
    from confidenceguard import EvaluationConfig
    from confidenceguard import compat
    parser=argparse.ArgumentParser();parser.add_argument('--rows',type=int,choices=(100000,1000000),required=True);parser.add_argument('--kind',choices=('features','vectors','lifecycle'),required=True);parser.add_argument('--dimensions',type=int,choices=(384,768),default=384);parser.add_argument('--out',required=True);args=parser.parse_args()
    record={'schema_version':'numek.cg4_capacity_measurement/1.0','harness_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'rows':args.rows,'kind':args.kind,'scope':'Synthetic codecs/lifecycle only, not capacity of complete discovery on these populations.'}
    try:record.update(status='completed',result=compat.supervise(measure,(args.rows,args.kind,args.dimensions),EvaluationConfig()).to_dict())
    except Exception as exc:record.update(status='refused_or_failed',error_type=type(exc).__name__,error_code=getattr(exc,'code',None),execution=getattr(exc,'execution',None),error=str(exc))
    path=Path(args.out);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x') as stream:json.dump(record,stream,sort_keys=True,indent=2);stream.write('\n')
    print(json.dumps(record))


if __name__=='__main__':main()
