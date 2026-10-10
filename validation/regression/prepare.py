"""Prepare pinned UCI tables without cleaning, deduplicating, or historical writes."""
import argparse
import hashlib
import io
import json
import platform
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT=Path(__file__).parent
CONCRETE_COLUMNS=['cement','blast_furnace_slag','fly_ash','water','superplasticizer','coarse_aggregate','fine_aggregate','age_days','strength_mpa']


def digest(content):return hashlib.sha256(content).hexdigest()


def prepare(download=False):
    import xlrd  # only preparation requires the XLS reader
    sources=json.loads((ROOT/'sources.json').read_text())
    output=ROOT/'data/prepared';output.mkdir(parents=True,exist_ok=True)
    raw=ROOT/'data/raw';raw.mkdir(parents=True,exist_ok=True)
    manifest={'preparation_version':'m2_regression_prepare_v1', 'preparation_script_sha256':digest(Path(__file__).read_bytes()),
              'prepared_at':datetime.now(timezone.utc).isoformat(),'retrieval_date':'2026-10-09',
              'python':platform.python_version(),'pandas':pd.__version__,'xlrd':xlrd.__version__,'sources':{},'datasets':{}}
    for name,source in sources.items():
        archive=raw/(name+'.zip')
        if not archive.exists():
            if not download:raise FileNotFoundError(f'Missing pinned archive {archive}; use --download.')
            with urllib.request.urlopen(source['url'],timeout=30) as response:archive.write_bytes(response.read())
        content=archive.read_bytes()
        if digest(content)!=source['archive_sha256']:raise ValueError(f'Archive checksum mismatch: {name}')
        with zipfile.ZipFile(io.BytesIO(content)) as bundle:
            members={member:bundle.read(member) for member in source['source_files']}
        manifest['sources'][name]={**source,'member_sha256':{member:digest(value) for member,value in members.items()}}
        if name=='concrete':
            frame=pd.read_excel(io.BytesIO(members['Concrete_Data.xls']),engine='xlrd')
            mapping=dict(zip(map(str,frame.columns),CONCRETE_COLUMNS));frame=frame.rename(columns=mapping)
            tables={'concrete':(frame,'strength_mpa',mapping,{'kind':'continuous','units':'MPa'})}
        else:
            tables={f'bike_{period}':(pd.read_csv(io.BytesIO(members[period+'.csv'])),'cnt',{}, {'kind':'count','units':'rental bikes per interval'}) for period in ['hour','day']}
        for key,(frame,target,mapping,expectations) in tables.items():
            path=output/(key+'.csv');frame.to_csv(path,index=False)
            manifest['datasets'][key]={'file':str(path.relative_to(ROOT)),'sha256':digest(path.read_bytes()),'rows':len(frame),'columns':len(frame.columns),
                'target':target,'header_mapping':mapping,'source':name,'expectations':expectations,
                'preparation':'No row filtering, filling, scaling, or deduplication; Concrete headers renamed and XLS converted to CSV.'}
            if name=='bike':
                if not frame['cnt'].eq(frame['casual']+frame['registered']).all():raise AssertionError('Bike derived total does not match components')
                clean=frame.drop(columns=['casual','registered']);cleanpath=output/(key+'_components_removed.csv');clean.to_csv(cleanpath,index=False)
                manifest['datasets'][key+'_components_removed']={**manifest['datasets'][key],'file':str(cleanpath.relative_to(ROOT)),
                    'sha256':digest(cleanpath.read_bytes()),'columns':len(clean.columns),'derivation':'Remove casual and registered only; negative control for component-sum checks.'}
    (ROOT/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return manifest


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--download',action='store_true')
    print(json.dumps(prepare(parser.parse_args().download),indent=2))
