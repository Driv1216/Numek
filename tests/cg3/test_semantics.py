import copy
import csv
import json
from pathlib import Path
import pytest
from confidenceguard import EvaluationError, LongitudinalSpec, HistoricalCorrectionSpec
from .test_history import workspace, batch, longitudinal


def rewrite(path, function):
    with path.open() as stream: records = list(csv.DictReader(stream)); fields = records[0].keys()
    function(records)
    with path.open('w') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields); writer.writeheader(); writer.writerows(records)


def test_equal_followup_and_workspace_known_asof(tmp_path):
    ws = workspace(tmp_path); source = batch(tmp_path); receipt = ws.ingest(source)
    result = ws.analyze(longitudinal(ws, maturity='equal_followup', followup_ns=str(10*86400*10**9)))
    assert all(m['denominator'] == 0 for m in result.data['measurements'] if m['metric'] == 'accuracy')
    old = ws.analyze(longitudinal(ws, catalog_sequence=receipt['catalog_sequence']))
    p = tmp_path/'updates.csv'; p.write_text('id,y,rev,ord,available,status\n1,0,r1,1,2026-03-01T00:00:00Z,withdrawn\n')
    ws.update_outcomes({'source': {'id': 'o', 'path': str(p)}, 'namespace': 'events', 'outcome_definition_version': 'outcome-v1', 'event_columns': ['id'],
        'column': 'y', 'revision_column': 'rev', 'order_column': 'ord', 'available_at': {'column': 'available'}, 'status_column': 'status'})
    latest = ws.analyze(longitudinal(ws))
    assert any(c['outcome_states'].get('outcome_withdrawn') == 1 for c in latest.data['history']['window_coverage'])
    prior_again = ws.analyze(longitudinal(ws, catalog_sequence=receipt['catalog_sequence']))
    values = lambda r: [(m['scope'], m['metric'], m['value'], m['denominator']) for m in r.data['measurements']]
    for a,b in zip(values(prior_again),values(old)):
        assert a[:2] == b[:2] and a[3] == b[3]
        assert a[2] == pytest.approx(b[2], abs=1e-12) if a[2] is not None else b[2] is None


def test_attempt_selection_and_overlapping_subset(tmp_path):
    ws = workspace(tmp_path); source = batch(tmp_path); ws.ingest(source)
    path = Path(source['evaluation']['sources'][0]['path'])
    with path.open() as stream: records = list(csv.DictReader(stream)); fields = list(records[0])+['attempt']
    for row in records: row['attempt'] = 'retry'
    with path.open('w') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields); writer.writeheader(); writer.writerows(records[:4])
    source['bindings'][0]['attempt_column'] = 'attempt'; ws.ingest(source)
    selected = ws.analyze(longitudinal(ws))
    assert selected.data['history']['window_coverage'][0]['ambiguous_predictions'] == 8
    variant = ws.models()[0]['id']
    exact = ws.analyze(longitudinal(ws, attempts={variant: 'single'}))
    assert exact.data['history']['window_coverage'][0]['selected_predictions'] == 6


def test_opportunity_and_context_corrections(tmp_path):
    ws = workspace(tmp_path); ws.ingest(batch(tmp_path))
    opportunity = next(f for f in ws.catalog.iter_facts('opportunity') if f['payload']['time']['tick'] == '1768003200000000000')
    result = ws.correct({'kind': 'opportunity', 'key': opportunity['key'], 'revision': 'corrected',
        'predecessor': opportunity['fact_digest'], 'authority': 'supplied', 'available_at': '2026-03-03T00:00:00Z',
        'reason': 'Correct event timestamp', 'changes': {'time': {'state': 'valid', 'tick': str(1769904000*10**9)}}})
    assert result['new_facts'] >= 1
    before = ws.analyze(longitudinal(ws))
    after = ws.analyze(longitudinal(ws, as_of='2026-03-04T00:00:00Z'))
    assert before.data['history']['window_coverage'] != after.data['history']['window_coverage']


def test_matched_comparison_and_task_blocker(tmp_path):
    ws = workspace(tmp_path); source = batch(tmp_path); ws.ingest(source)
    candidate = copy.deepcopy(source); candidate['evaluation']['runs'][0]['model']['version'] = '2'
    path = Path(source['evaluation']['sources'][0]['path'])
    rewrite(path, lambda rows: [r.update(p=str(1-float(r['p']))) for r in rows])
    ws.ingest(candidate)
    a, b = [m['id'] for m in ws.models()]
    specification = longitudinal(ws, variants=[a,b], comparisons=[{'id':'matched', 'reference_window':'jan','current_window':'jan','reference_variant':a,'current_variant':b,'kind':'matched'}])
    result = ws.analyze(specification)
    contrast = next(m for m in result.data['history']['comparisons'][0]['metrics'] if m['metric']=='accuracy')
    assert abs(contrast['value']) == 1
    candidate['outcome_definition_version'] = 'different-target'
    candidate['evaluation']['task']['outcome_definition'] = 'Different outcome'
    candidate['evaluation']['runs'][0]['model']['version'] = '3'; ws.ingest(candidate)
    c = next(m['id'] for m in ws.models() if m['outcome_definition_version']=='different-target')
    specification['variants'] = [a,c]; specification['comparisons'][0]['current_variant'] = c
    blocked = ws.analyze(specification)
    assert blocked.data['history']['comparisons'][0]['status'] == 'blocked'
    assert blocked.data['history']['comparisons'][0]['metrics'] == []


def test_mix_reconciles_and_regression_mse(tmp_path):
    ws = workspace(tmp_path); source = batch(tmp_path, count=40)
    path = Path(source['evaluation']['sources'][0]['path'])
    rewrite(path, lambda rows: [r.update(p='0.9' if r['group']=='a' else '0.1') for r in rows])
    ws.ingest(source)
    result = ws.analyze(longitudinal(ws, cohorts=[{'id':'population','column':'group','categories':['a','b']}]))
    mix = next(m for m in result.data['history']['mix'] if m['metric']=='accuracy')
    assert mix['status'] == 'completed'
    assert mix['mix']+mix['within'] == pytest.approx(mix['aggregate_delta'])
    regression = copy.deepcopy(source); regression['evaluation']['task'] = {'kind':'regression','outcome_definition':'Numeric observed value'}
    regression['evaluation']['runs'][0].pop('probabilities'); regression['evaluation']['runs'][0]['decision'] = {}; regression['evaluation']['runs'][0]['prediction'] = 'p'
    regression['evaluation']['runs'][0]['model']['id'] = 'regression'; regression['outcome_definition_version'] = 'numeric-v1'
    ws.ingest(regression)
    variant = next(v['id'] for v in ws.models() if v['task']['kind']=='regression')
    result = ws.analyze(longitudinal(ws, variants=[variant], comparisons=[]))
    assert any(m['metric']=='mse' and m['denominator']==20 for m in result.data['measurements'])


def test_recorded_cg2_outputs_reconstruct_without_refitting(tmp_path):
    from tests.cg2.test_methods import binary_spec
    spec = binary_spec(tmp_path, [{'id':'lac','kind':'lac','run':'original','levels':['0.9','0.999']}])
    path = tmp_path/'predictions.csv'
    with path.open() as stream: records = list(csv.DictReader(stream)); fields=list(records[0])+['when']
    for row in records: row['when']='2026-01-10T00:00:00Z'
    with path.open('w') as stream:
        writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader();writer.writerows(records)
    spec['evaluation']['runs'][0]['prediction_at']={'column':'when'}
    ws=workspace(tmp_path)
    receipt=ws.ingest({'namespace':'events','outcome_definition_version':'outcome-v1','operation':'study','evaluation':spec,'bindings':[{'run':'original'}]})
    original=ws.open(receipt['assessment_id'])
    assert original.private['fitted_methods']
    path.unlink()
    variant=next(m['id'] for m in ws.models() if m['method_digests'])
    result=ws.analyze(longitudinal(ws,variants=[variant],as_of=None,features={},maturity='observed',comparisons=[]))
    assert any(m['metric'].startswith('set_coverage@') and m['denominator']==60 for m in result.data['measurements'])


def test_fault_recovery_deletion_and_tamper(tmp_path,monkeypatch):
    ws=workspace(tmp_path);source=batch(tmp_path)
    def fail(boundary):
        if boundary=='objects_published':raise RuntimeError('simulated crash')
    monkeypatch.setattr(ws.catalog,'_fault',fail)
    with pytest.raises(RuntimeError):ws.ingest(source)
    assert ws.status()['facts']=={}
    monkeypatch.setattr(ws.catalog,'_fault',lambda boundary:None)
    ws.recover();ws.ingest(source)
    result=ws.analyze(longitudinal(ws));before=ws.status()['facts']['prediction']
    plan=ws.deletion_preview(assessment_ids=[result.data['analysis_id']]);ws.delete(plan)
    assert ws.status()['facts']['prediction']==before
    with pytest.raises(EvaluationError):ws.open(result.data['analysis_id'])
    obj=next(ws.catalog.iter_facts('prediction'))['object_id'];path=ws.path/'objects'/(obj+'.jsonl')
    with path.open('ab') as stream:stream.write(b'changed')
    with pytest.raises(EvaluationError):list(ws.catalog.iter_facts('prediction'))
