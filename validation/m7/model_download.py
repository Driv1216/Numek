"""Explicit development download of three fixed publisher revisions; never runtime code."""
import hashlib
import json
from pathlib import Path
import urllib.request
from datatrust.image_models import MODELS

ROOT=Path(__file__).parent
REGISTRY=Path(__file__).parents[2]/'src/datatrust/image_model_artifacts.json'


def download():
    registry=json.loads(REGISTRY.read_text()); registry.setdefault('models',{})
    for model,revision in MODELS.items():
        root=ROOT/'models'/model.split('/')[-1]; root.mkdir(parents=True,exist_ok=True)
        request=urllib.request.Request(f'https://huggingface.co/api/models/{model}/revision/{revision}?blobs=true',headers={'User-Agent':'Numek-M7-development-validation'})
        with urllib.request.urlopen(request,timeout=60) as response: publisher=json.load(response)
        if publisher['sha']!=revision: raise ValueError('Publisher revision mismatch.')
        identity={x['rfilename']:x for x in publisher['siblings']}
        (root/'publisher.json').write_text(json.dumps(publisher,indent=2)+'\n')
        expected={}; observed={}
        for name in ['config.json','preprocessor_config.json','model.safetensors']:
            item=identity[name]
            expected[name]={'algorithm':'sha256' if 'lfs' in item else 'git_blob_sha1','digest':item['lfs']['sha256'] if 'lfs' in item else item['blobId']}
            path=root/name
            if not path.exists():
                request=urllib.request.Request(f'https://huggingface.co/{model}/resolve/{revision}/{name}',headers={'User-Agent':'Numek-M7-development-validation'})
                with urllib.request.urlopen(request,timeout=60) as response,path.with_suffix(path.suffix+'.part').open('wb') as out:
                    while block:=response.read(1024**2): out.write(block)
                path.with_suffix(path.suffix+'.part').rename(path)
            with path.open('rb') as f: observed[name]=hashlib.file_digest(f,'sha256').hexdigest()
            pin=observed[name] if expected[name]['algorithm']=='sha256' else hashlib.sha1(b'blob '+str(path.stat().st_size).encode()+b'\0'+path.read_bytes()).hexdigest()
            if pin!=expected[name]['digest']: raise ValueError('Downloaded bytes differ from publisher.')
        registry['models'][model]={'revision':revision,'files':expected,'license':'Apache-2.0','publisher_url':f'https://huggingface.co/{model}/tree/{revision}','license_identity':{'spdx':'Apache-2.0','publisher_revision':revision,'model_card_git_blob_sha1':identity['README.md']['blobId'],'model_card_url':f'https://huggingface.co/{model}/blob/{revision}/README.md'}}
        REGISTRY.write_text(json.dumps(registry,indent=2)+'\n')
        (root/'datatrust-model.json').write_text(json.dumps({'model':model,'revision':revision,'files':observed},indent=2)+'\n')
        print(model,'publisher artifacts verified',flush=True)


if __name__=='__main__': download()
