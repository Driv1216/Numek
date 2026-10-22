import copy
import csv
import json
from pathlib import Path
import pytest
from confidenceguard import (ReliabilityWorkspace, WorkspaceConfig, PredictionBatchSpec, LongitudinalSpec,
    HistoricalWindow, HistoricalComparison, OutcomeRevisionSpec, EvaluationError, LongitudinalResult)


def batch(tmp_path, name='predictions', count=12):
    path = tmp_path / (name + '.csv')
    with path.open('w') as stream:
        stream.write('id,entity,when,y,p,available,due,group\n')
        for i in range(count):
            month = '01' if i < count//2 else '02'
            stream.write(f'{i},entity-{i},2026-{month}-10T00:00:00Z,{i%2},{.8 if i%2 else .2},2026-03-01T00:00:00Z,2026-02-28T00:00:00Z,{"a" if i%3 else "b"}\n')
    return {'namespace': 'events', 'outcome_definition_version': 'outcome-v1', 'bindings': [{'run': 'base', 'features': {'group': 'categorical'}}],
        'evaluation': {'task': {'kind': 'binary_classification', 'outcome_definition': 'Observed event', 'classes': ['0', '1'], 'positive_class': '1'},
        'sources': [{'id': 'p', 'path': str(path)}], 'runs': [{'id': 'base', 'source': 'p', 'model': {'id': 'risk', 'version': '1'},
            'key_columns': ['id'], 'entity_columns': ['entity'], 'prediction_at': {'column': 'when'}, 'probabilities': {'positive_column': 'p'},
            'decision': {'rule': 'probability_threshold', 'threshold': .5}, 'role': 'production'}],
        'outcomes': {'source': 'p', 'column': 'y', 'key_columns': ['id'], 'available_at': {'column': 'available'}, 'due_at': {'column': 'due'}}}}


def workspace(tmp_path):
    return ReliabilityWorkspace.initialize(tmp_path/'workspace', WorkspaceConfig(saving=True, free_disk_bytes=1))


def longitudinal(ws, **changes):
    variant = ws.models()[0]['id']
    value = {'namespace': 'events', 'variants': [variant], 'as_of': '2026-03-02T00:00:00Z',
             'windows': [{'id': 'jan', 'start': '2026-01-01T00:00:00Z', 'end': '2026-02-01T00:00:00Z'},
                         {'id': 'feb', 'start': '2026-02-01T00:00:00Z', 'end': '2026-03-01T00:00:00Z'}],
             'comparisons': [{'id': 'change', 'reference_window': 'jan', 'current_window': 'feb', 'reference_variant': variant, 'current_variant': variant}],
             'features': {'group': 'categorical'}}
    value.update(changes)
    return value


def test_capture_dedup_reconstruct_and_restart(tmp_path):
    ws = workspace(tmp_path); specification = batch(tmp_path)
    first = ws.ingest(specification, request_id='first')
    assert ws.ingest(specification, request_id='first') == first
    before = ws.status()['facts']['prediction']
    again = ws.ingest(specification)
    assert again['duplicate_occurrences'] > 0
    assert ws.status()['facts']['prediction'] == before == 12
    Path(specification['evaluation']['sources'][0]['path']).unlink()
    ws = ReliabilityWorkspace(ws.path)
    result = ws.analyze(longitudinal(ws))
    assert len(result.data['history']['comparisons'][0]['metrics']) > 0
    accuracy = [m for m in result.data['measurements'] if m['metric'] == 'accuracy' and m['scope'].endswith('/overall')]
    assert [(m['value'], m['denominator']) for m in accuracy] == [(1, 6), (1, 6)]
    reopened = ws.open(result.data['analysis_id'])
    assert reopened.to_private_dict() == result.to_private_dict()
    LongitudinalResult.from_dict(result.to_private_dict(), private=result.private)


def test_pre_cutoff_capture_and_outcome_revision(tmp_path):
    ws = workspace(tmp_path); specification = batch(tmp_path)
    specification['evaluation']['as_of'] = '2026-01-01T00:00:00Z'
    ws.ingest(specification)
    old = ws.analyze(longitudinal(ws, as_of='2026-02-01T00:00:00Z'))
    assert all(m['denominator'] == 0 for m in old.data['measurements'] if m['metric'] == 'accuracy')
    later = ws.analyze(longitudinal(ws))
    assert any(m['value'] == 1 for m in later.data['measurements'] if m['metric'] == 'accuracy')
    path = tmp_path/'updates.csv'; path.write_text('id,y,revision,order,available,status\n1,0,correction,1,2026-03-04T00:00:00Z,final\n')
    revision = {'source': {'id': 'updates', 'path': str(path)}, 'namespace': 'events', 'outcome_definition_version': 'outcome-v1',
                'event_columns': ['id'], 'column': 'y', 'revision_column': 'revision', 'order_column': 'order',
                'available_at': {'column': 'available'}, 'status_column': 'status'}
    ws.update_outcomes(revision)
    newer = ws.restate(later.data['analysis_id'], as_of='2026-03-05T00:00:00Z', reason='Outcome correction')
    assert any(m['value'] < 1 for m in newer.data['measurements'] if m['metric'] == 'accuracy' and m['value'] is not None)
    assert ws.open(later.data['analysis_id']).to_private_dict() == later.to_private_dict()
    assert newer.data['history']['restatement_changes']


def test_conflict_is_not_double_counting_and_recovery(tmp_path):
    ws = workspace(tmp_path); specification = batch(tmp_path)
    ws.ingest(specification)
    path = Path(specification['evaluation']['sources'][0]['path'])
    path.write_text(path.read_text().replace(',0.8,', ',0.7,'))
    with pytest.raises(EvaluationError) as error: ws.ingest(specification)
    assert error.value.code == 'historical_identity_conflict'
    ws.recover()
    assert ws.status()['facts']['prediction'] == 12


def test_saving_and_backup(tmp_path):
    ws = ReliabilityWorkspace.initialize(tmp_path/'workspace', WorkspaceConfig(free_disk_bytes=1))
    specification = batch(tmp_path)
    with pytest.raises(EvaluationError, match='saving is off'): ws.ingest(specification)
    ws.set_saving(True); ws.ingest(specification)
    manifest = ws.backup(tmp_path/'backup')
    assert manifest['files']
    clone = ReliabilityWorkspace.restore(tmp_path/'backup', tmp_path/'restored')
    assert clone.instance_id != ws.instance_id
    assert clone.status()['facts'] == ws.status()['facts']
