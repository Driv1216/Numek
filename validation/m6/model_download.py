"""Development-only download of the approved fixed E5-small revision."""
import hashlib
import json
from pathlib import Path
import urllib.request
from datatrust.text_models import REVISION

root=Path(__file__).parent/'models'/'multilingual-e5-small';root.mkdir(parents=True,exist_ok=True)
files=['config.json','model.safetensors','tokenizer.json','tokenizer_config.json','special_tokens_map.json','sentencepiece.bpe.model']
hashes={}
publisher=json.loads((Path(__file__).parent/'results/model_publisher_identity.json').read_text())
identities={x['rfilename']:x for x in publisher['siblings']}
for name in files:
    path=root/name
    if not path.exists():
        request=urllib.request.Request(f'https://huggingface.co/intfloat/multilingual-e5-small/resolve/{REVISION}/{name}',headers={'User-Agent':'Numek-M6-development-validation'})
        with urllib.request.urlopen(request,timeout=60) as response,path.with_suffix(path.suffix+'.part').open('wb') as out:
            while chunk:=response.read(1024**2):out.write(chunk)
        path.with_suffix(path.suffix+'.part').rename(path)
    raw=path.read_bytes();hashes[name]=hashlib.sha256(raw).hexdigest()
    identity=identities[name]
    observed=hashes[name] if 'lfs' in identity else hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
    expected=identity['lfs']['sha256'] if 'lfs' in identity else identity['blobId']
    if observed!=expected:raise ValueError('Downloaded artifact does not match publisher commit identity.')
(root/'datatrust-model.json').write_text(json.dumps({'model':'intfloat/multilingual-e5-small','revision':REVISION,'files':hashes},indent=2)+'\n')
print(json.dumps({'revision':REVISION,'files':hashes,'directory':str(root)}))
