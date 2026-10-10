"""Offline regression evidence/parity verification against pinned inputs."""
import argparse
import hashlib
import json
import math
import platform
import statistics
import time
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

from datatrust import DataTrust,DatasetSpec,TaskSpec,AnalysisConfig,RegressionOptions,TargetExpectations

ROOT=Path(__file__).parent


def verify_all(write_artifacts=False):
    manifest=json.loads((ROOT/'manifest.json').read_text())
    mutations=json.loads((ROOT/'mutations.json').read_text())
    sources=json.loads((ROOT/'sources.json').read_text())
    for name,source in sources.items():
        archive=ROOT/'data/raw'/f'{name}.zip'
        assert hashlib.sha256(archive.read_bytes()).hexdigest()==source['archive_sha256'],name
        with zipfile.ZipFile(archive) as bundle:
            for member,expected in manifest['sources'][name]['member_sha256'].items():
                assert hashlib.sha256(bundle.read(member)).hexdigest()==expected,member
    old_summary=ROOT/'results/verification.json'
    old=json.loads(old_summary.read_text()) if old_summary.exists() else {'cases':[]}
    owned={p:sha for item in old['cases'] for p,sha in item.get('artifacts',{}).items()}
    for relative,expected in owned.items():
        assert hashlib.sha256((ROOT/relative).read_bytes()).hexdigest()==expected,relative
    presentation=ROOT/'results/presentation/manifest.json'
    if presentation.exists():
        for case in json.loads(presentation.read_text())['cases']:
            hashes={**case['artifacts'],**case.get('contact_sheets',{})}
            if 'source_snapshot' in case:
                hashes[case['source_snapshot']]=case['source_sha256']
            for relative,expected in hashes.items():
                assert hashlib.sha256((ROOT/relative).read_bytes()).hexdigest()==expected,relative
    browser=ROOT/'results/browser/manifest.json'
    if browser.exists():
        for relative,expected in json.loads(browser.read_text())['artifacts'].items():
            assert hashlib.sha256((ROOT/relative).read_bytes()).hexdigest()==expected,relative
    summary={'validation_type':'internal','external_method_validity':'not_established','python':platform.python_version(),
             'pandas':pd.__version__,'numpy':np.__version__,'platform':platform.platform(),'cases':[]}
    for name,case in {**manifest['datasets'],**mutations}.items():
        source=ROOT/case['file']
        assert hashlib.sha256(source.read_bytes()).hexdigest()==case['sha256'],name
        availability={'casual':'unavailable_at_prediction','registered':'unavailable_at_prediction'} if name in {'bike_hour','bike_day'} else {}
        options=RegressionOptions(TargetExpectations(**case['expectations']),availability)
        started=time.monotonic()
        r=DataTrust.from_spec(DatasetSpec(source,dataset_name=name.replace('_',' ').title(),purpose='Forecast interval total before its outcomes are known.' if name.startswith('bike_') else 'Internal regression dataset reliability validation.'),TaskSpec('regression',case['target']),AnalysisConfig(regression=options)).analyze_result()
        elapsed=time.monotonic()-started
        assert (r.profile['row_count'],r.profile['column_count'])==(case['rows'],case['columns'])
        assert r.execution['status']=='completed' and r.scoring['values'] is None
        reg=r.profile['regression'];t=reg['target_statistics']
        frame=pd.read_csv(source)
        finite=sorted(v for v in frame[case['target']].tolist() if pd.notna(v) and math.isfinite(v))
        assert len(finite)==t['finite_count'] and len(set(finite))==t['distinct_count'],name
        assert math.isclose(t['mean'],statistics.mean(finite),rel_tol=1e-12,abs_tol=1e-12),name
        if len(finite)>1:assert math.isclose(t['sample_std'],statistics.stdev(finite),rel_tol=1e-12,abs_tol=1e-12),name
        for key,probability in [('p1',.01),('p5',.05),('q1',.25),('median',.5),('q3',.75),('p95',.95),('p99',.99)]:
            position=(len(finite)-1)*probability;lower=math.floor(position);upper=math.ceil(position)
            expected=finite[lower]+(finite[upper]-finite[lower])*(position-lower)
            assert math.isclose(t['quantiles'][key],expected,rel_tol=1e-12,abs_tol=1e-12),(name,key)
        expected_union=sum((options.expectations.minimum is not None and v<options.expectations.minimum) or
            (options.expectations.maximum is not None and v>options.expectations.maximum) or
            (options.expectations.nonnegative and v<0) or
            (options.expectations.integer_required and not float(v).is_integer()) or False for v in finite)
        assert reg['constraints']['violation_union_count']==expected_union,name
        assert sum(v['count'] for v in t['histogram']['bins'])==t['finite_count'] if t['histogram'] else t['precision_reason']
        codes={f['code'] for f in r.findings}
        assert set(case.get('expected_findings',[]))<=codes,name
        if name.startswith('bike_') and not name.endswith('removed'):
            assert any(v['columns']==['casual','registered'] and v['method']=='pair_sum' and v['action_eligible'] for v in reg['relationships']),name
            assert 'regression_relationships_unavailable_at_prediction' in codes
        if name.endswith('removed'):
            assert not any('casual' in v['columns'] or 'registered' in v['columns'] for v in reg['relationships'])
        if name=='sparse_copy':
            assert reg['relationships'] and not any(c.startswith('regression_relationships_') for c in codes)
        if 'legitimate' in name or name=='zero_inflated_count':
            assert not reg['relationships'] and 'regression_declared_constraints' not in codes
        assert not any('rounding' in code or 'conflicting_label' in code for code in codes)
        data=json.loads(r.json_text(),parse_constant=lambda value:(_ for _ in ()).throw(AssertionError(value)))
        ids={e['id'] for e in data['evidence']}
        for finding in data['findings']:assert finding['evidence_refs'] and set(finding['evidence_refs'])<=ids
        for e in data['evidence']:
            for pointer in e['measurement_refs']:
                node=data
                for key in pointer.split('/')[1:]:node=node[int(key)] if isinstance(node,list) else node[key]
        artifacts={}
        if write_artifacts:
            destination=ROOT/'reports';destination.mkdir(exist_ok=True)
            # Only replace outputs named and hashed by our previous regression manifest.
            for suffix in ['html','json']:
                path=destination/(name+'.'+suffix)
                if path.exists():
                    key=str(path.relative_to(ROOT))
                    if owned.get(key)!=hashlib.sha256(path.read_bytes()).hexdigest():raise ValueError(f'Unrecognized regression artifact {path}')
                    path.unlink()
            bundle=r.generate_artifacts(destination/(name+'.html'),json_path=destination/(name+'.json'))
            artifacts={str(Path(path).relative_to(ROOT)):hashlib.sha256(Path(path).read_bytes()).hexdigest() for path in [bundle.html_path,bundle.json_path]}
        summary['cases'].append({'name':name,'passed':True,'rows':case['rows'],'columns':case['columns'],'source_sha256':case['sha256'],
            'elapsed_seconds':elapsed,'runtime_target_met':elapsed<30,'frame_bytes':r.execution['frame_bytes'],
            'search_status':reg['search']['status'],'comparisons':reg['search']['comparisons'],'finding_codes':sorted(codes),'artifacts':artifacts})
    if write_artifacts:
        (ROOT/'results').mkdir(exist_ok=True)
        (ROOT/'results/verification.json').write_text(json.dumps(summary,indent=2)+'\n')
    return summary


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--write-artifacts',action='store_true');args=parser.parse_args()
    print(json.dumps(verify_all(args.write_artifacts),indent=2))
