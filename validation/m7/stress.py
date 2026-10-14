"""Measured disk-backed 100k signature population and actual minimal-copy image workload."""
from dataclasses import replace
import json
import os
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace

import duckdb
import numpy as np
import pandas as pd
import psutil
from PIL import Image
from datatrust import *
from datatrust.scalable import Workspace
from datatrust.image_sources import ValidatedImageSourcePlan
from datatrust.image_search import build_index,investigate
from datatrust.image_diagnostics import Evidence
from datatrust.images import audit_images

ROOT=Path(__file__).parent


def run():
    out=ROOT/os.environ.get('M7_RESULT_DIR','results'); out.mkdir(exist_ok=True)
    process=psutil.Process(); results={}
    options=ExecutionOptions() if os.environ.get('M7_FULL_SEARCH') else replace(ExecutionOptions(),memory_bytes=64*1024**2)
    config=replace(ImageAnalysisConfig(),execution=options,limits=replace(ImageWorkLimits(),posting_visits=100000000 if os.environ.get('M7_FULL_SEARCH') else 2000000,hamming_comparisons=50000000 if os.environ.get('M7_FULL_SEARCH') else 1000000,details=5))
    work=Workspace(options,[],phase_plan={'estimated_peak_workspace_bytes':512*1024**2},image_source_plan=ValidatedImageSourcePlan([],512*1024**2))
    try:
        n=100000; rng=np.random.default_rng(901); signatures=rng.integers(0,2**63,n,dtype=np.uint64)
        # Controlled cross-split low-distance witnesses in the 100k catalog.
        signatures[80000:80100]=signatures[:100]^np.uint64(1<<23)
        facts=[json.dumps({'oriented_sha256':f'{i:064x}','visual_eligible':True,'phash':int(v)}) for i,v in enumerate(signatures)]
        assets=pd.DataFrame({'path':[f'asset-{i}' for i in range(n)],'payload':facts})
        occurrences=pd.DataFrame({'oid':np.arange(n),'sid':['dataset']*n,'split':['train']*80000+['validation']*10000+['test']*10000,'path':assets['path']})
        work.con.register('input_assets',assets); work.con.execute('CREATE TABLE assets AS SELECT * FROM input_assets')
        work.con.register('input_occurrences',occurrences); work.con.execute('CREATE TABLE occurrences AS SELECT * FROM input_occurrences')
        spec=ImageAuditSpec((ImageInputSpec('dataset',ImageSourceSpec('.')),))
        store=SimpleNamespace(con=work.con,config=config,spec=spec,work=work,audit_id='stress',sources={'dataset':'source_1'})
        store.witness=lambda oid:f'controlled_{oid}'
        evidence=Evidence(store); started=time.monotonic(); investigate(evidence,store); work.check('100k signature ledger')
        coverage=evidence.coverage['near_duplicates']; count=work.con.execute('SELECT count(*) FROM image_candidates WHERE left_aid<>right_aid').fetchone()[0]
        results['signature_100k']={'seconds':time.monotonic()-started,'population':n,'partition_entries':n*7,'candidates':count,'coverage':coverage,'peak_workspace_bytes':work.peak,'rss_bytes_at_end':process.memory_info().rss,'configured_engine_memory':options.memory_bytes,'claim':'Signature/index/search workload only; not 100k full-resolution image decoding.'}
    finally: work.close()
    if not os.environ.get('M7_SIGNATURE_ONLY'):
        with tempfile.TemporaryDirectory(prefix='numek-m7-media-') as tmp:
            p=Path(tmp); rng=np.random.default_rng(8)
            # 1000 real image locations, 10k occurrences, varying annotation roles.
            for i in range(1000): Image.fromarray(rng.integers(0,256,(96,128,3),dtype=np.uint8)).save(p/f'{i}.jpg',quality=90)
            rows=[{'path':f'{i%1000}.jpg','id':str(i),'split':'train' if i<8000 else 'test'} for i in range(10000)]
            manifest=p/'manifest.jsonl'; manifest.write_text(''.join(json.dumps(x)+'\n' for x in rows))
            item=ImageInputSpec('s',ImageSourceSpec(str(manifest),'jsonl',str(p)),mapping=ImageMappingSpec(logical_id='id',split='split'))
            started=time.monotonic(); result=audit_images(ImageAuditSpec((item,),allowed_roots=(str(p),)),replace(ImageAnalysisConfig(),limits=replace(ImageWorkLimits(),details=10)))
            results['actual_media']={'seconds':time.monotonic()-started,'occurrences':10000,'image_locations':1000,'source_media_bytes':sum(x.stat().st_size for x in p.glob('*.jpg')),'execution':result.execution,'coverage':result.coverage,'private_bytes':len(json.dumps(result.private).encode()),'public_bytes':len(result.json_text().encode()),'corpus_copied':result.execution['corpus_copied'],'claim':'Measured narrow 96x128 JPEG workload; not general capacity.'}
    (out/'stress.json').write_text(json.dumps(results,indent=2,allow_nan=False,default=lambda x:x.item() if hasattr(x,'item') else str(x))+'\n'); print(json.dumps({k:{'seconds':v['seconds']} for k,v in results.items()}),flush=True)


if __name__=='__main__': run()
