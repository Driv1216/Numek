"""Read the publisher's commit-specific LFS/blob identities for offline pinning."""
import json,urllib.request
from pathlib import Path
from datatrust.text_models import REVISION
req=urllib.request.Request(f'https://huggingface.co/api/models/intfloat/multilingual-e5-small/revision/{REVISION}?blobs=true',headers={'User-Agent':'Numek-M6-validation'})
with urllib.request.urlopen(req,timeout=60) as r:info=json.load(r)
root=Path(__file__).parent/'results';root.mkdir(exist_ok=True)
(root/'model_publisher_identity.json').write_text(json.dumps(info,indent=2)+'\n')
print(json.dumps({x['rfilename']:x.get('lfs',{}).get('sha256',x.get('blobId')) for x in info['siblings']}))
