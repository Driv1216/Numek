"""Development-only acquisition. Runtime audits never access the network."""
from pathlib import Path
import urllib.request
import hashlib
import json
ROOT=Path(__file__).parent
SOURCES={
 'beijing.zip':'https://archive.ics.uci.edu/static/public/501/beijing+multi+site+air+quality+data.zip',
 'electricity.zip':'https://archive.ics.uci.edu/static/public/321/electricityloaddiagrams20112014.zip',
 'retail.zip':'https://archive.ics.uci.edu/static/public/352/online+retail.zip',
 'alfred.pdf':'https://alfred.stlouisfed.org/docs/alfred_capturing_data.pdf',
}
def digest(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as f:
  for b in iter(lambda:f.read(1024**2),b''):h.update(b)
 return h.hexdigest()
def run():
 catalog=ROOT/'data/raw/manifest.json';previous=json.loads(catalog.read_text()) if catalog.exists() else {};records={}
 for name,url in SOURCES.items():
  p=ROOT/'data/raw'/name
  if not p.exists():
   temp=p.with_suffix(p.suffix+'.part')
   with urllib.request.urlopen(url,timeout=120) as response,temp.open('wb') as f:
    while True:
     b=response.read(1024**2)
     if not b:break
     f.write(b)
   temp.rename(p)
  sha=digest(p)
  if name in previous and sha!=previous[name]['sha256']:raise ValueError('Pinned raw source changed: '+name)
  records[name]={'url':url,'sha256':sha,'bytes':p.stat().st_size};print(name,records[name],flush=True)
 catalog.write_text(json.dumps(records,indent=2)+'\n')
if __name__=='__main__':run()
