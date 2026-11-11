"""Record a qualification environment without exposing machine environment variables.

Use --fetch-metadata only with network authorization. PyPI metadata establishes
declared compatibility and candidate wheels, not successful product execution.
"""
import argparse
from datetime import datetime,timezone
import hashlib
import importlib.metadata as metadata
import json
from pathlib import Path
import platform
import re
import sys
import urllib.request


def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--lock',required=True);parser.add_argument('--out',required=True)
    parser.add_argument('--fetch-metadata',action='store_true');args=parser.parse_args()
    from packaging.tags import sys_tags
    from packaging.utils import parse_wheel_filename,canonicalize_name
    from packaging.requirements import Requirement
    text=Path(args.lock).read_text();pins={canonicalize_name(k):v for k,v in re.findall(r'^([A-Za-z0-9_.-]+)==([^\s\\]+)',text,re.M)}
    supported=set(sys_tags());packages={};failures=[]
    for name,version in sorted(pins.items()):
        try:distribution=metadata.distribution(name)
        except metadata.PackageNotFoundError:failures.append({'package':name,'reason':'not_installed'});continue
        observed=distribution.version
        if observed!=version:failures.append({'package':name,'reason':'version_mismatch','installed':observed,'lock':version})
        files={p.name:sha(distribution.locate_file(p)) for p in distribution.files or () if str(p).endswith(('.dist-info/METADATA','.dist-info/RECORD','.dist-info/WHEEL'))}
        item={'installed_version':observed,'locked_version':version,'distribution_manifest_hashes':files}
        if args.fetch_metadata:
            url=f'https://pypi.org/pypi/{name}/{version}/json'
            with urllib.request.urlopen(url,timeout=60) as response:raw=response.read(16*1024**2)
            release=json.loads(raw);wheels=[]
            for entry in release['urls']:
                if not entry['filename'].endswith('.whl'):continue
                try:_,_,_,tags=parse_wheel_filename(entry['filename'])
                except ValueError:continue
                if supported&tags:wheels.append({k:entry[k] for k in ('filename','url','size','digests','requires_python','yanked')})
            info=release['info'];item['official_metadata']={'url':url,'response_sha256':hashlib.sha256(raw).hexdigest(),
                'requires_python':info['requires_python'],'requires_dist':info['requires_dist'],'matching_runtime_wheels':wheels,
                'source_distributions':[{k:e[k] for k in ('filename','url','size','digests')} for e in release['urls'] if e['packagetype']=='sdist']}
        packages[name]=item
    import numpy as np
    from threadpoolctl import threadpool_info
    import sqlite3
    payload={'schema_version':'numek.cg4_runtime_audit/1.0','generated_at':datetime.now(timezone.utc).isoformat(),
        'python':{'version':sys.version,'executable_sha256':sha(sys.executable),'implementation':platform.python_implementation(),'GIL_build':not bool(__import__('sysconfig').get_config_var('Py_GIL_DISABLED'))},
        'platform':{'system':platform.system(),'machine':platform.machine(),'release':platform.release()},'sqlite':sqlite3.sqlite_version,
        'lock':{'path':args.lock,'sha256':sha(args.lock)},'packages':packages,'failures':failures,'native_threadpools':threadpool_info(),
        'scope':'Executed package inventory and metadata/wheel audit; this alone does not establish analytical, encoder or platform qualification.'}
    path=Path(args.out);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(payload,sort_keys=True,indent=2)+'\n')
    print(json.dumps({'packages':len(packages),'mismatches':failures,'out':str(path)}))
    return bool(failures)


if __name__=='__main__':raise SystemExit(main())
