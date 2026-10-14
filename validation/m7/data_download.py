"""Development-only pinned COCO subset; production analysis never downloads."""
import hashlib
import io
import json
from pathlib import Path
import urllib.request
import zipfile

ROOT=Path(__file__).parent/'data'


def download():
    ROOT.mkdir(parents=True,exist_ok=True)
    manifest_path=ROOT/'natural_manifest.json'
    if manifest_path.exists():
        manifest=json.loads(manifest_path.read_text())
        if len(manifest['images'])>=128 and all((ROOT/x['path']).exists() for x in manifest['images']): return manifest
    archive=ROOT/'annotations_trainval2017.zip'
    if not archive.exists():
        with urllib.request.urlopen('https://s3.amazonaws.com/images.cocodataset.org/annotations/annotations_trainval2017.zip',timeout=60) as r,archive.with_suffix('.part').open('wb') as out:
            while b:=r.read(1024**2): out.write(b)
        archive.with_suffix('.part').rename(archive)
    with zipfile.ZipFile(archive) as z:
        # Read only a fixed known member; do not extract arbitrary archive paths.
        data=json.loads(z.read('annotations/instances_val2017.json'))
    licenses={x['id']:x for x in data['licenses']}
    chosen=sorted(data['images'],key=lambda x:hashlib.sha256(str(x['id']).encode()).hexdigest())[:128]
    images=[]
    for i,item in enumerate(chosen):
        path=ROOT/item['file_name']
        if not path.exists():
            with urllib.request.urlopen(item['coco_url'].replace('http://images.cocodataset.org/','https://s3.amazonaws.com/images.cocodataset.org/'),timeout=60) as response: path.write_bytes(response.read())
        with path.open('rb') as f: sha=hashlib.file_digest(f,'sha256').hexdigest()
        images.append({'id':item['id'],'path':path.name,'sha256':sha,'url':item['coco_url'],'flickr_url':item.get('flickr_url'),'license':licenses[item['license']],'split':'calibration' if i<64 else 'held_out'})
        print('natural',i+1,flush=True)
    manifest={'dataset':'COCO val2017','subset':'SHA256(id) order, first 128; first 64 calibration, next 64 untouched held-out','annotation_archive_sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'images':images,'distribution':'Local validation only; images retain individual Flickr licenses and are not committed.'}
    manifest_path.write_text(json.dumps(manifest,indent=2)+'\n'); return manifest


if __name__=='__main__': download()
