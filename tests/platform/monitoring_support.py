"""Shared CG7 monitoring scenario for the S5 and S6 platform tests: an ingestion contract, synthetic credit
data with a controllable error rate, and the monitoring definition used by both suites."""
import csv
import io
import random
from datetime import datetime, timedelta, timezone

NS = 'credit'
FIELDS = ['id', 'entity', 'when', 'y', 'p', 'available', 'due', 'group', 'model_version']
DAY = 86400 * 10**9
T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)


def tick(dt):
    return int(dt.timestamp()) * 10**9


def contract():
    return {
        'format': 'csv', 'event_time': 'when', 'identity': {'model_version': 'model_version'},
        'fields': {'id': {'type': 'string', 'identity': True}, 'entity': {'type': 'string', 'required': True},
                   'when': {'type': 'timestamp', 'required': True}, 'y': {'type': 'string', 'vocabulary': ['0', '1']},
                   'p': {'type': 'number', 'required': True, 'probability': True}, 'available': {'type': 'timestamp'},
                   'due': {'type': 'timestamp'}, 'group': {'type': 'string', 'vocabulary': ['a', 'b']},
                   'model_version': {'type': 'string'}},
        'batch': {'namespace': NS, 'outcome_definition_version': 'outcome-v1',
                  'bindings': [{'run': 'base', 'features': {'group': 'categorical'}}],
                  'evaluation': {
                      'task': {'kind': 'binary_classification', 'outcome_definition': 'Default', 'classes': ['0', '1'],
                               'positive_class': '1'},
                      'sources': [{'id': 'rows'}],
                      'runs': [{'id': 'base', 'source': 'rows', 'model': {'id': 'scorecard', 'version': '1'},
                                'key_columns': ['id'], 'entity_columns': ['entity'], 'prediction_at': {'column': 'when'},
                                'probabilities': {'positive_column': 'p'},
                                'decision': {'rule': 'probability_threshold', 'threshold': .5}, 'role': 'production'}],
                      'outcomes': {'source': 'rows', 'column': 'y', 'key_columns': ['id'],
                                   'available_at': {'column': 'available'}, 'due_at': {'column': 'due'}}}}}


def generate(start_day, days, per_day, *, error_rate, seed, prefix='u'):
    rng = random.Random(seed)
    rows = []
    for d in range(days):
        day = T0 + timedelta(days=start_day + d)
        for j in range(per_day):
            when = day + timedelta(minutes=17 * j)
            positive = rng.random() < 0.5
            p = 0.8 if positive else 0.2
            correct = rng.random() >= error_rate
            y = ('1' if positive else '0') if correct else ('0' if positive else '1')
            ident = f'{prefix}{start_day + d}-{j}'
            rows.append({'id': ident, 'entity': f'e-{ident}', 'when': when.strftime('%Y-%m-%dT%H:%M:%SZ'), 'y': y, 'p': str(p),
                         'available': (when + timedelta(days=5)).strftime('%Y-%m-%dT%H:%M:%SZ'),
                         'due': (when + timedelta(days=5)).strftime('%Y-%m-%dT%H:%M:%SZ'),
                         'group': 'a' if rng.random() < 0.6 else 'b', 'model_version': 'v1'})
    return rows


def body(rows):
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=FIELDS, lineterminator='\n')
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue().encode()


def send(installation, rows, name):
    from confidenceguard.operations import ingest
    for i in range(0, len(rows), 800):
        ingest.receive(installation, 'scorecard-events', f'{name}-{i}', body(rows[i:i + 800]))
    return ingest.process_pending(installation)


DEFINITION = {
    'start': '2026-02-01T00:00:00Z', 'window_ns': str(7 * DAY), 'allowed_lateness_ns': str(6 * 3600 * 10**9),
    'maturity': {'policy': 'equal_followup', 'followup_ns': str(10 * DAY)},
    'features': {'group': 'categorical'}, 'cohorts': [{'id': 'population', 'column': 'group', 'categories': ['a', 'b']}],
    'reference': {'start': '2026-01-01T00:00:00Z', 'end': '2026-02-01T00:00:00Z', 'alpha': 0.01},
    'detectors': [
        {'id': 'matured-error', 'statistic': 'error', 'delta': 0.01, 'target_false_alarms_per_30_days': 0.1, 'shift': 0.15,
         'max_useful_delay_days': 60},
        {'id': 'brier', 'statistic': 'brier', 'delta': 0.01, 'target_false_alarms_per_30_days': 0.1, 'shift': 0.1,
         'max_useful_delay_days': 60},
        {'id': 'abstention', 'statistic': 'abstention', 'delta': 0.01, 'alpha': 1e-4, 'target': 0.2},
        {'id': 'log-loss', 'statistic': 'log_loss', 'delta': 0.1, 'alpha': 1e-4, 'shift': 0.1},
    ],
    'estimators': ['implied_issued_error', 'implied_brier', 'composition_projection'],
    'rules': [{'id': 'label-availability', 'measure': 'eligible_label_observation_rate', 'op': '<', 'value': 0.5,
               'phase': 'maturity', 'standing': 'P'}],
    'drift_thresholds': {'feature:group': {'total_variation': 0.05}},
}
