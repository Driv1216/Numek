"""Development-only public corpus acquisition; fixed raw hashes are sealed on first run."""
import hashlib,json,urllib.request
from pathlib import Path

SOURCES={
 'sms':('https://archive.ics.uci.edu/static/public/228/sms+spam+collection.zip','CC BY 4.0'),
 'ud_english':('https://raw.githubusercontent.com/UniversalDependencies/UD_English-EWT/r2.16/en_ewt-ud-dev.conllu','CC BY-SA 4.0'),
 'ud_hindi':('https://raw.githubusercontent.com/UniversalDependencies/UD_Hindi-HDTB/r2.16/hi_hdtb-ud-dev.conllu','CC BY-NC-SA 4.0'),
 'squad':('https://rajpurkar.github.io/SQuAD-explorer/dataset/dev-v2.0.json','CC BY-SA 4.0'),
 'oasst':('https://huggingface.co/datasets/OpenAssistant/oasst1/resolve/main/2023-04-12_oasst_ready.trees.jsonl.gz','Apache 2.0'),
 'scifact':('https://scifact.s3-us-west-2.amazonaws.com/release/latest/data.tar.gz','Claims/evidence: CC BY 4.0; abstracts: ODC-By 1.0 (publisher LICENSE.md)'),
}
root=Path(__file__).parent;raw=root/'data/raw';raw.mkdir(parents=True,exist_ok=True);manifest_path=root/'data/manifest.json'
previous=json.loads(manifest_path.read_text()) if manifest_path.exists() else {};manifest={}
for name,(url,license) in SOURCES.items():
    path=raw/name
    if not path.exists():
        req=urllib.request.Request(url,headers={'User-Agent':'Numek-M6-development-validation'})
        with urllib.request.urlopen(req,timeout=60) as response,path.with_suffix('.part').open('wb') as out:
            resolved=response.geturl().split('?')[0]
            while data:=response.read(1024**2):out.write(data)
        path.with_suffix('.part').rename(path)
    else:resolved=previous.get(name,{}).get('resolved_url',url)
    digest=hashlib.sha256(path.read_bytes()).hexdigest()
    if name in previous and previous[name]['sha256']!=digest:raise ValueError('Pinned raw corpus changed; no silent repinning.')
    manifest[name]={'url':url,'resolved_url':resolved,'sha256':digest,'bytes':path.stat().st_size,'license':license}
    manifest_path.write_text(json.dumps(manifest,indent=2)+'\n');print(name,digest,flush=True)
