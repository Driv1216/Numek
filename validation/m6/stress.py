"""Declared nested, asset-heavy and model-enabled measurements; no extrapolation."""
from dataclasses import replace
import hashlib,json,tempfile,time
from pathlib import Path
from datatrust import *
ROOT=Path(__file__).parent

def run():
    results={}
    with tempfile.TemporaryDirectory(prefix='numek-m6-stress-') as temp:
        root=Path(temp)
        def source(name,rows):
            p=root/(name+'.jsonl')
            with p.open('w') as f:
                for row in rows:f.write(json.dumps(row,ensure_ascii=False)+'\n')
            return TextSourceSpec(str(p))
        common=TextAnalysisConfig(limits=replace(TextWorkLimits(),lexical_units=64,shingle_positions=100000,signature_work=500000,verification_visits=500000,details=5))
        tokens=['token'+str(i) for i in range(100)];text=' '.join(tokens)
        nested=TextInputSpec('nested',source('nested',({'id':str(i),'text':text,'tokens':tokens,'labels':['O']*100} for i in range(2000))),(TextFieldSpec('text','text'),),id_selector='id',annotations=(TextAnnotationSpec('text','labels',kind='token',tokens_selector='tokens',scheme='BIO'),))
        for i in range(100):(root/f'asset-{i}.txt').write_text(('Source aligned content '+str(i)+'\n')*40)
        assets=TextInputSpec('assets',source('assets',({'id':str(i),'text':'asset-'+str(i%100)+'.txt'} for i in range(10000))),(TextFieldSpec('text','text',asset=AssetSpec('text')),),id_selector='id')
        long_text=('Source identity, original offsets, multilingual text and verified annotations. '*150)+'Tail provenance sentence.'
        models=TextInputSpec('model',source('model',({'id':str(i),'text':long_text+str(i)} for i in range(16))),(TextFieldSpec('text','text'),),id_selector='id')
        model_config=replace(common,models=TextModelOptions(language=True,embedding_directory=str((ROOT/'models/multilingual-e5-small').resolve()),tokenizer=True),limits=replace(common.limits,embedding_windows=64,windows_per_parent=4,language_units=16))
        for name,item,config in [('nested',nested,common),('asset_heavy',assets,common),('model_enabled',models,model_config)]:
            tick=time.monotonic();r=DataTrust.audit_text(TextAuditSpec((item,),allowed_roots=(str(root),)),config)
            results[name]={'status':r.execution['status'],'seconds':time.monotonic()-tick,'profile':r.profile,'execution':r.execution,'coverage':r.coverage,'source_sha256':r.execution['provenance']['source_1']['sha256'],'model_artifact_hashes':{n:x['sha256'] for n,x in r.private['models'].get('embedding',{}).get('files',{}).items()}}
            if name=='nested':assert next(x['data'] for x in r.evidence if x['family']=='annotations')['supplied_tokens']==200000
            if name=='asset_heavy':assert r.profile['asset_references']==10000 and len(r.private['assets'])==100
            if name=='model_enabled':assert r.coverage['families']['semantic_similarity']['embedded_windows']==64
            print(name,'completed',round(results[name]['seconds'],2),flush=True)
            (ROOT/'results/stress.json').write_text(json.dumps(results,indent=2,allow_nan=False)+'\n')
if __name__=='__main__':run()
