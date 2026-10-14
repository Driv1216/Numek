"""Explicit development provisioning. Runtime never downloads or modifies allowlists."""
import hashlib
import json
from pathlib import Path
import urllib.request
import shutil
import time

ROOT=Path(__file__).parent
REGISTRY=ROOT.parents[1]/'src/datatrust/cross_model_artifacts.json'
MODELS={'nli':('MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli',None,['config.json','model.safetensors','tokenizer_config.json','spm.model']),
        'image_text':('google/siglip-base-patch16-224','7fd15f0689c79d79e38b1c2e2e2370a7bf2761ed',['config.json','preprocessor_config.json','model.safetensors','tokenizer_config.json','special_tokens_map.json','spiece.model'])}


def fetch(url):
    return urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Numek-M9-explicit-development-provisioning'}),timeout=60)


def main():
    registry=json.loads(REGISTRY.read_text()) if REGISTRY.exists() else {'models':{},'qualification':{}}
    for kind,(model,revision,files) in MODELS.items():
        old=registry['models'].get(kind)
        revision=revision or (old or {}).get('revision')
        with fetch(f'https://huggingface.co/api/models/{model}'+(f'/revision/{revision}' if revision else '')+'?blobs=true') as r: publisher=json.load(r)
        revision=publisher['sha'];items={x['rfilename']:x for x in publisher['siblings']}
        root=ROOT/'models'/kind;root.mkdir(parents=True,exist_ok=True)
        expected={};observed={}
        for name in files:
            item=items[name];expected[name]={'algorithm':'sha256' if 'lfs' in item else 'git_blob_sha1','digest':item['lfs']['sha256'] if 'lfs' in item else item['blobId']}
            path=root/name
            if path.exists() and path.stat().st_size!=item['size']: path.rename(path.with_suffix(path.suffix+'.rejected'))
            reused=ROOT.parent/'m7/models/siglip-base-patch16-224'/name
            if not path.exists() and kind=='image_text' and reused.exists(): shutil.copyfile(reused,path)
            if not path.exists():
                with fetch(f'https://huggingface.co/{model}/resolve/{revision}/{name}?download=true&numek_m9={time.time_ns()}') as r,path.with_suffix(path.suffix+'.part').open('wb') as out:
                    while block:=r.read(1024**2): out.write(block)
                part=path.with_suffix(path.suffix+'.part')
                if part.stat().st_size!=item['size']: raise ValueError('Publisher download was incomplete; no artifact admitted.')
                part.rename(path)
            with path.open('rb') as f: observed[name]=hashlib.file_digest(f,'sha256').hexdigest()
            pin=observed[name] if expected[name]['algorithm']=='sha256' else hashlib.sha1(b'blob '+str(path.stat().st_size).encode()+b'\0'+path.read_bytes()).hexdigest()
            if pin!=expected[name]['digest']: raise ValueError('Publisher identity mismatch.')
            print(kind,name,'verified',flush=True)
        registry['models'][kind]={'model':model,'revision':revision,'files':expected,'license':(publisher.get('cardData') or {}).get('license'),'model_card':items['README.md']['blobId']}
        REGISTRY.write_text(json.dumps(registry,indent=2)+'\n')
        (root/'datatrust-model.json').write_text(json.dumps({'model':model,'revision':revision,'files':observed},indent=2)+'\n')


if __name__=='__main__': main()
