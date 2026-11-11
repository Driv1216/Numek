"""Explicit benchmark-only acquisition. The product never downloads models/data.

Only acquisition manifests and aggregate findings belong in the review bundle;
AG News/CIFAR assets are not redistributed through NUMEK.
"""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import re
import urllib.request

SOURCES={
    'bank':{'url':'https://archive.ics.uci.edu/static/public/222/bank+marketing.zip','page':'https://archive.ics.uci.edu/dataset/222/bank+marketing',
            'attribution':'Moro, Rita and Cortez (2014), UCI Bank Marketing, DOI 10.24432/C5K306','license':'CC BY 4.0, as stated by UCI','filename':'bank-marketing.zip'},
    'wine':{'url':'https://archive.ics.uci.edu/static/public/186/wine+quality.zip','page':'https://archive.ics.uci.edu/dataset/186/wine+quality',
            'attribution':'Cortez et al. (2009), UCI Wine Quality, DOI 10.24432/C56S3T','license':'CC BY 4.0, as stated by UCI','filename':'wine-quality.zip'},
    'cifar10':{'url':'https://cave.cs.toronto.edu/kriz/cifar-10-binary.tar.gz','page':'https://cave.cs.toronto.edu/kriz/cifar.html',
               'attribution':'Krizhevsky, Nair and Hinton; Learning Multiple Layers of Features from Tiny Images (2009)',
               'license':'Publisher requests citation; no explicit license grant found on the dataset page. No dataset redistribution in the NUMEK review bundle.',
               'publisher_md5':'c32a1d4ab5d03f1284b67883e8d87530','filename':'cifar-10-binary.tar.gz'}}


def get(url,max_bytes):
    with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'NUMEK-CG4-internal-benchmark/1.0'}),timeout=120) as stream:
        raw=stream.read(max_bytes+1)
        if len(raw)>max_bytes:raise RuntimeError('Publisher response exceeds benchmark acquisition budget.')
        return raw,{'resolved_url':stream.url,'content_type':stream.headers.get('Content-Type'),'ETag':stream.headers.get('ETag')}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('dataset',choices=tuple(SOURCES)+('ag_news',));parser.add_argument('--cache',default=str(Path(__file__).with_name('datasets.nosync')));args=parser.parse_args()
    directory=Path(args.cache)/args.dataset;directory.mkdir(parents=True,exist_ok=True)
    manifest=directory/'acquisition.json'
    if manifest.exists():
        previous=json.loads(manifest.read_text())
        for entry in previous['files']:
            if hashlib.sha256((directory/entry['filename']).read_bytes()).hexdigest()!=entry['sha256']:raise RuntimeError('Acquired dataset changed; preserve the manifest and diagnose the bytes.')
        print(json.dumps({'manifest':str(manifest),'reused':True}));return
    files=[];provenance={}
    if args.dataset=='ag_news':
        endpoint='https://huggingface.co/api/datasets/fancyzhx/ag_news/revision/main';raw,info=get(endpoint,1024**2);repo=json.loads(raw);revision=repo['sha']
        if not re.fullmatch('[0-9a-f]{40}',revision):raise RuntimeError('Invalid publisher repository revision.')
        provenance={'metadata_url':endpoint,'metadata_sha256':hashlib.sha256(raw).hexdigest(),'resolved_revision':revision,
            'page':'https://huggingface.co/datasets/fancyzhx/ag_news/blob/'+revision+'/README.md',
            'attribution':'Zhang, Zhao and LeCun (2015); AG corpus by Antonio Gulli; fancyzhx/ag_news publisher mirror',
            'license':'Dataset card declares license unknown and describes research/non-commercial provision. This acquisition does not establish broader rights. No dataset content is redistributed in the review bundle.'}
        names=[entry['rfilename'] for entry in repo['siblings'] if re.fullmatch(r'data/(train|test)-[0-9]+-of-[0-9]+\.parquet',entry['rfilename'])]
        if len(names)!=2:raise RuntimeError('Unexpected AG News split layout; do not silently substitute data.')
        requests=[(name.rsplit('/',1)[-1],'https://huggingface.co/datasets/fancyzhx/ag_news/resolve/'+revision+'/'+name,64*1024**2) for name in names]
    else:
        provenance=SOURCES[args.dataset].copy();requests=[(provenance['filename'],provenance['url'],256*1024**2)]
    for filename,url,limit in requests:
        data,headers=get(url,limit)
        if provenance.get('publisher_md5') and hashlib.md5(data).hexdigest()!=provenance['publisher_md5']:raise RuntimeError('Publisher CIFAR checksum differs.')
        with (directory/filename).open('xb') as stream:stream.write(data)
        files.append({'filename':filename,'url':url,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),**headers})
    record={'schema_version':'numek.cg4_dataset_acquisition/1.0','dataset':args.dataset,'acquired_at':datetime.now(timezone.utc).isoformat(),
            'provenance':provenance,'files':files,'customer_evidence':False,'review_bundle_policy':'manifests, code and aggregates only; exclude raw and derived dataset content'}
    manifest.write_text(json.dumps(record,sort_keys=True,indent=2)+'\n')
    evidence=Path(__file__).with_name('results')/'datasets';evidence.mkdir(exist_ok=True)
    with (evidence/(args.dataset+'-acquisition.json')).open('x') as stream:json.dump(record,stream,sort_keys=True,indent=2);stream.write('\n')
    print(json.dumps({'manifest':str(manifest),'files':len(files),'bytes':sum(f['bytes'] for f in files)}))


if __name__=='__main__':main()
