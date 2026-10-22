"""Exercise a clean extracted handoff using its installed wheel; no report authoring."""
import argparse
import json
import math
from pathlib import Path
import tarfile
import zipfile


def exercise(root, output, site, resume=False):
    import confidenceguard, datatrust
    from confidenceguard import ReliabilityWorkspace
    root=Path(root).resolve();output=Path(output).resolve();site=Path(site).resolve()
    output.mkdir(parents=True,exist_ok=resume)
    assert site in Path(confidenceguard.__file__).parents
    assert site in Path(datatrust.__file__).parents
    counts={}
    with zipfile.ZipFile(root/'wheel/datatrust-0.1.0-py3-none-any.whl') as wheel:
        for package in ['confidenceguard','datatrust']:
            count=0
            for source in (root/'src'/package).rglob('*'):
                if source.is_file() and '__pycache__' not in source.parts and source.suffix!='.pyc':
                    relative=str(source.relative_to(root/'src'))
                    assert wheel.read(relative)==source.read_bytes(),relative
                    count+=1
            counts[package]=count
    if not resume:
        with tarfile.open(root/'examples/synthetic-backup.tar.gz') as archive:
            assert all(m.name=='backup' or m.name.startswith('backup/') for m in archive.getmembers())
            archive.extractall(output,filter='data')
        workspace=ReliabilityWorkspace.restore(output/'backup',output/'restored')
    else:
        workspace=ReliabilityWorkspace(output/'restored')
    records=json.loads((root/'examples/reproduction.json').read_text());opened=[]
    for record in records:
        result=workspace.open(record['assessment']);assert result.data['analysis_id']==record['assessment'];opened.append(result.data['analysis_id'])
    # Reconstruct from retained facts, without registering original source paths.
    result=workspace.analyze(records[0]['spec'],request_id='packaging-reconstruct')
    expected=json.loads((root/'examples/reports/binary-local.json').read_text())
    def measurements(data):return {(m['scope'],m['metric']):m for m in data['measurements']}
    actual=measurements(result.data);reference=measurements(expected);assert actual.keys()==reference.keys()
    max_difference=0.
    for key,measurement in actual.items():
        old=reference[key];assert measurement['denominator']==old['denominator'] and measurement['value_state']==old['value_state'],key
        value=measurement['value'];previous=old['value']
        if isinstance(value,(float,int)) and isinstance(previous,(float,int)):
            assert math.isclose(value,previous,rel_tol=1e-10,abs_tol=1e-12),(key,value,previous)
            max_difference=max(max_difference,abs(value-previous))
        else:assert value==previous,key
    summary={'wheel_imports':{'confidenceguard':str(Path(confidenceguard.__file__).relative_to(site)),'datatrust':str(Path(datatrust.__file__).relative_to(site))},'wheel_source_asset_files_equal':counts,'restored_assessments':opened,'retained_fact_reconstruction':'binary metric/scopes/denominators/value states identical; numeric values within rel=1e-10, abs=1e-12','max_absolute_numeric_difference':max_difference,'status':'passed'}
    (output/'exercise.json').write_text(json.dumps(summary,indent=2)+'\n')
    return summary


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',default='.');p.add_argument('--out',required=True);p.add_argument('--site',required=True);p.add_argument('--resume',action='store_true');a=p.parse_args()
    print(json.dumps(exercise(a.root,a.out,a.site,a.resume),indent=2))
