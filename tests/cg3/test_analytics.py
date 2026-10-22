import copy
import json
from pathlib import Path
import pytest
from confidenceguard import ReliabilityWorkspace, WorkspaceConfig, EvaluationError, make_windows
from validation.cg3.fixtures import create, specification


@pytest.mark.parametrize('kind', ['binary_classification','multiclass_classification','regression'])
def test_all_task_families_have_longitudinal_metrics_and_private_exports(tmp_path,kind):
    batch=create(tmp_path/'inputs',kind=kind,events=300)
    ws=ReliabilityWorkspace.initialize(tmp_path/'workspace',WorkspaceConfig(saving=True,free_disk_bytes=1))
    ws.ingest(batch)
    spec=specification(ws.models())
    result=ws.analyze(spec)
    expected='mae' if kind=='regression' else 'accuracy'
    assert any(m['metric']==expected and m['denominator']>0 for m in result.data['measurements'])
    assert result.data['history']['temporal']
    artifacts=result.generate_artifacts(tmp_path/'local.html',audience='local',json_path=tmp_path/'local.json')
    assert Path(artifacts.private_result_path).stat().st_mode & 0o077 == 0
    assert 'How strong is the evidence?' in Path(artifacts.html_path).read_text()
    assert any(d['status']=='completed' for d in result.data['history']['drift'])
    # Distances are independently checked against scalar SciPy references.
    try:
        import scipy.stats
    except ImportError:
        return
    import csv
    with Path(batch['evaluation']['sources'][0]['path']).open() as stream: rows=list(csv.DictReader(stream))
    a=[float(r['feature']) for r in rows if r['when']<'2026-07-01'];b=[float(r['feature']) for r in rows if r['when']>='2026-07-01']
    drift=next(d for d in result.data['history']['drift'] if d['field']=='feature:feature')
    assert drift['wasserstein_1']==pytest.approx(scipy.stats.wasserstein_distance(a,b))
    assert drift['ks_distance']==pytest.approx(scipy.stats.ks_2samp(a,b).statistic)


def test_regression_quantiles_samples_reconstruct_from_frozen_evidence(tmp_path):
    batch=create(tmp_path/'inputs',kind='regression',events=80,samples=7)
    ws=ReliabilityWorkspace.initialize(tmp_path/'workspace',WorkspaceConfig(saving=True,free_disk_bytes=1));ws.ingest(batch)
    for source in batch['evaluation']['evaluation']['sources']:Path(source['path']).unlink()
    spec=specification(ws.models());spec['comparisons']=[]
    result=ws.analyze(spec)
    assert any(m['metric']=='empirical_crps' and m['denominator']>0 for m in result.data['measurements'])
    assert any(m['metric'].startswith('pinball@') for m in result.data['measurements'])


def test_changed_contrast_uses_two_matched_pairs(tmp_path):
    batch=create(tmp_path/'inputs',events=400)
    ws=ReliabilityWorkspace.initialize(tmp_path/'workspace',WorkspaceConfig(saving=True,free_disk_bytes=1));ws.ingest(batch)
    candidate=copy.deepcopy(batch);candidate['evaluation']['runs'][0]['model']['version']='2'
    import csv
    path=Path(candidate['evaluation']['sources'][0]['path'])
    with path.open() as stream:rows=list(csv.DictReader(stream));fields=rows[0].keys()
    for row in rows:row['p']=str(1-float(row['p']))
    with path.open('w') as stream:
        writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader();writer.writerows(rows)
    ws.ingest(candidate);a,b=[v['id'] for v in ws.models()]
    spec=specification(ws.models());spec['comparisons']=[{'id':'paired-change','kind':'contrast_change',
        'reference_window':'reference','current_window':'current','reference_variant':a,'current_variant':a,
        'second_reference_variant':b,'second_current_variant':b}]
    result=ws.analyze(spec);edge=result.data['history']['comparisons'][0]
    m=next(m for m in edge['metrics'] if m['metric']=='brier')
    assert m['value']==pytest.approx(m['current_matched_contrast']-m['reference_matched_contrast'])
    assert m['reference_second_population_id']


def test_calendar_and_exact_fixed_windows():
    civil=make_windows('2026-03-07T00:00:00-05:00','2026-03-10T00:00:00-04:00',calendar='day',timezone_name='America/New_York')
    assert len(civil)==3
    from confidenceguard.history_contracts import instant
    assert instant(civil[1].end)-instant(civil[1].start)==23*3600*10**9
    exact=make_windows('2026-01-01T00:00:00.000000001Z','2026-01-01T00:00:00.000000006Z',cadence_ns='2',rolling_ns='3')
    assert len(exact)==3 and exact[0].start.endswith('000000001Z')


def test_backup_preserves_assessment_and_current_resolver_location(tmp_path):
    batch=create(tmp_path/'inputs',events=80)
    ws=ReliabilityWorkspace.initialize(tmp_path/'workspace',WorkspaceConfig(saving=True,free_disk_bytes=1));ws.ingest(batch)
    result=ws.analyze(specification(ws.models()));before=result.to_private_dict()
    ws.backup(tmp_path/'backup');clone=ReliabilityWorkspace.restore(tmp_path/'backup',tmp_path/'clone')
    restored=clone.open(result.data['analysis_id']);assert restored.to_private_dict()==before
    if restored.private['locators']:
        ref=next(iter(restored.private['locators']))
        assert restored.resolve_evidence(ref,allowed_roots=(clone.path,))['status']=='resolved'
