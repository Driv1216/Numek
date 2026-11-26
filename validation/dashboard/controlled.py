"""Small controlled cases for the dashboard redesign corpus (cases.json, "controlled").

Each builder runs the real DataTrust engine on a small deterministic input written under `root` and returns the completed
result. They exist only to give the results dashboard a case that no retained milestone result covers. They are not
validation claims, are never committed, and change no analytical code.

- classification_partial: German Credit with declared context. The one optional classification stage (contextual
  evidence) is made to raise, so the engine records it as failed and publishes an honest partial result. This is an
  injected fault for presentation testing only.
- annotation_regression_single: one numerical target with optional annotations (tabular_annotation_regression_v1).
- m4_before_after: the German Credit before/after fixture of tests/test_before_after.py (M4 versions, before_after preset).
- m6_clean: a framed corpus of distinct generated sentences.
- m9_clean: records that all agree with their PDF evidence under one decimal rule (no model rule).
- unlabeled_wide: the WS4 wide generator (5,000 x 1,000), profiled without a target.
- generic_unknown_methodology: german_credit's JSON relabelled with an unknown methodology and schema. Test-only.
"""
import csv
import json
import random
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[2]
GERMAN = REPO / 'validation/data/prepared/german_credit.csv'
GERMAN_CONTEXT = {'prediction': {'objective': 'decide whether to approve a credit application', 'point': 'at application'},
                  'columns': {'duration_months': {'availability': 'available_at_prediction', 'unit': 'months'}}}
BEFORE_AFTER = [{'kind': 'filter', 'description': 'credit_amount < 10000'}, {'kind': 'drop_columns', 'columns': ['telephone']},
                {'kind': 'impute', 'columns': ['age']}]


def classification_partial(root):
    from datatrust import AnalysisConfig, DataTrust, DatasetSpec, TaskSpec

    def fail(*args, **kwargs):
        raise RuntimeError('injected for presentation testing')
    with mock.patch('datatrust.contextual.build', fail):
        result = DataTrust.from_spec(DatasetSpec(str(GERMAN)), TaskSpec('classification', target='credit_risk'),
                                     AnalysisConfig(context=GERMAN_CONTEXT)).analyze_result()
    assert result.execution['status'] == 'partial', 'the injected optional failure must produce a partial result'
    return result


def annotation_regression_single(root):
    from datatrust import AnalysisConfig, AnnotationOptions, AnnotationSpec, DataTrust, DatasetSpec, RegressionOptions, TaskSpec
    rng = random.Random(11)
    path = Path(root) / 'annotation_regression.csv'
    with path.open('w', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(['site', 'temperature', 'humidity', 'yield_kg'])
        for i in range(400):
            temperature, humidity = round(rng.uniform(5, 35), 1), round(rng.uniform(20, 90), 1)
            value = round(2.5 * temperature - 0.4 * humidity + rng.gauss(0, 4), 2)
            if i % 9 == 0:
                value = ''          # not yet measured: optional annotation
            elif i % 97 == 0:
                value = -abs(value)  # violates the declared nonnegative expectation
            writer.writerow([f's{i % 25:02d}', temperature, humidity, value])
    config = AnalysisConfig(annotations=AnnotationOptions(AnnotationSpec('optional')),
                            regression=RegressionOptions.from_dict({'expectations': {'kind': 'continuous', 'nonnegative': True, 'units': 'kg'}}))
    result = DataTrust.from_spec(DatasetSpec(str(path)), TaskSpec('regression', target='yield_kg'), config).analyze_result()
    assert result.methodology_id == 'tabular_annotation_regression_v1'
    return result


def m4_before_after(root):
    import pandas as pd
    from datatrust import ComparisonSpec, DatasetInput, DatasetSpec, TaskSpec
    from datatrust.m4_worker import compare
    before = pd.read_csv(GERMAN)
    before.insert(0, 'id', range(len(before)))
    before.loc[before.index % 50 == 0, 'age'] = None
    after = before[before.credit_amount < 10000].drop(columns=['telephone']).copy()
    after['age'] = after['age'].fillna(after['age'].median())
    paths = Path(root) / 'before.csv', Path(root) / 'after.csv'
    before.to_csv(paths[0], index=False)
    after.to_csv(paths[1], index=False)
    task = TaskSpec('classification', 'credit_risk')
    spec = ComparisonSpec('versions', (DatasetInput('source1', 'reference', DatasetSpec(str(paths[0])), task),
                                       DatasetInput('source2', 'current', DatasetSpec(str(paths[1])), task)),
                          identity_keys=(('id',),), preset='before_after', transformations=tuple(BEFORE_AFTER),
                          dataset_name='German Credit before and after preprocessing')
    return compare(spec)


WORDS = ('river stone harbour lantern meadow copper violet signal orbit canyon ember glacier quiet ledger compass willow '
         'thunder marble saffron beacon tundra prism cedar falcon hollow juniper kelp lattice mosaic nectar opal pepper '
         'quartz rustic summit tidal umber vessel wharf yarrow zephyr almond basalt cobalt dune estuary fjord grove').split()


def m6_clean(root):
    from datatrust import DataTrust, TextAnalysisConfig, TextAuditSpec, TextFieldSpec, TextInputSpec, TextSourceSpec
    rng = random.Random(5)
    path = Path(root) / 'corpus.jsonl'
    lines = []
    for i in range(80):
        words = rng.sample(WORDS, 9)
        lines.append(json.dumps({'id': f'doc{i:03d}', 'text': f"Record {i}: " + ' '.join(words) + f" near marker {rng.randint(1000, 9999)}."}))
    path.write_text('\n'.join(lines) + '\n')
    spec = TextAuditSpec((TextInputSpec('corpus', TextSourceSpec(str(path), format='jsonl'), (TextFieldSpec('text', 'text'),)),),
                         allowed_roots=(str(root),))
    return DataTrust.audit_text(spec, TextAnalysisConfig())


def m9_clean(root):
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    from datatrust import (ClockSpec, CrossRepresentationAuditSpec, CrossRepresentationInputSpec, DataTrust, DocumentMappingSpec,
                           ReconciliationRule, RelationshipSpec)
    root = Path(root)
    records, docs = [], []
    styles = getSampleStyleSheet()
    for i in range(1, 9):
        entity = f'B{i:03d}'
        revenue = str(1_000_000 * i)
        records.append({'id': entity, 'entity': entity, 'period': 'FY2025', 'revenue': revenue, 'cutoff': '2026-01-01T00:00:00Z'})
        path = root / f'{entity}.pdf'
        table = Table([['Metric', 'Period', 'Value'], ['Revenue', 'FY2025', revenue]], colWidths=[150, 100, 150])
        table.setStyle(TableStyle([('GRID', (0, 0), (-1, -1), 1, 'black')]))
        SimpleDocTemplate(str(path)).build([Paragraph(f'Company {entity} financial evidence', styles['Title']), Spacer(1, 20), table])
        docs.append({'id': entity, 'entity': entity, 'period': 'FY2025', 'path': path.name, 'available': '2025-12-01T00:00:00Z',
                     'role': 'evidence', 'layout': 'finance'})
    for name, rows in (('records', records), ('documents', docs)):
        with (root / f'{name}.csv').open('w', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=rows[0])
            writer.writeheader()
            writer.writerows(rows)
    spec = CrossRepresentationAuditSpec(
        inputs=(CrossRepresentationInputSpec('records', str(root / 'records.csv'), language='en'),
                CrossRepresentationInputSpec('documents', str(root / 'documents.csv'), kind='document', asset_root=str(root), layout='finance', language='en')),
        relationships=(RelationshipSpec('support', 'records', 'documents', left_keys=('entity',), right_keys=('entity',),
                                        context={'entity': ['entity', 'entity'], 'period': ['period', 'period']},
                                        availability=ClockSpec('available'), cutoff=ClockSpec('cutoff')),),
        mappings=(DocumentMappingSpec('revenue', layout='finance', kind='table_field', headers={'label': ['Metric'], 'period': ['Period'], 'value': ['Value']},
                                      row_column='label', row_label='Revenue', context_columns={'period': 'period'}, unit='INR', currency='INR'),),
        rules=(ReconciliationRule('revenue', 'support', 'revenue', mapping='revenue', unit='INR', currency='INR'),),
        allowed_roots=(str(root),), dataset_name='Clean financial reconciliation (controlled)')
    return DataTrust.audit_cross_representation(spec)


def unlabeled_wide(root):
    from datatrust import DataTrust, DatasetSpec, TaskSpec
    from validation.ws4.run_scalability import wide_csv
    path = wide_csv(Path(root) / 'wide_1000.csv', 5000, 1000)
    return DataTrust.from_spec(DatasetSpec(str(path)), TaskSpec('dataset_profile')).analyze_result()


def generic_unknown_methodology(root, base):
    """Test-only: a completed german_credit result relabelled as an unknown future methodology and schema."""
    value = json.loads(Path(base).read_text())
    value['methodology_id'] = 'future_method_v9'
    value['schema_version'] = '9.9'
    return value


BUILDERS = {'classification_partial': classification_partial, 'annotation_regression_single': annotation_regression_single,
            'm4_before_after': m4_before_after, 'm6_clean': m6_clean, 'm9_clean': m9_clean, 'unlabeled_wide': unlabeled_wide}
