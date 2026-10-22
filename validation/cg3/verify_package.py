"""Verify the non-circular review inventory without third-party dependencies."""
import argparse
import hashlib
import json
from pathlib import Path


def verify(root):
    root=Path(root).resolve(); manifest=json.loads((root/'MANIFEST.json').read_text())
    expected=manifest['files']; actual={str(p.relative_to(root)) for p in root.rglob('*') if p.is_file() and p.name!='MANIFEST.json' and '__pycache__' not in p.parts}
    assert actual==set(expected), {'missing':sorted(set(expected)-actual),'extra':sorted(actual-set(expected))}
    for relative,record in expected.items():
        path=root/relative
        assert path.is_file() and not path.is_symlink(),relative
        assert path.stat().st_size==record['bytes'],relative
        assert hashlib.sha256(path.read_bytes()).hexdigest()==record['sha256'],relative
    return {'status':'passed','files':len(expected),'bytes':sum(r['bytes'] for r in expected.values()),'manifest_excludes_itself':True}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',default='.');a=p.parse_args();print(json.dumps(verify(a.root),indent=2))
