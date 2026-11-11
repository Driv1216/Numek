# Read-only: runs DataTrust's own browser-UI inspection on the prepared Adult CSV and writes what
# the Upload → Configure → Confirm screens would show into src/fixture/inspect.generated.json.
#   inspect_csv_dataset: rows, columns, first-10-row preview, grouped target options
#   inspect_classification_target: per small-set candidate, detected subtype, class split, suitability
# Run from the repository root:
#   PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src .venv/bin/python -B frontend-visual-lab-v3/scripts/extract_inspect.py
import json, os
from datatrust.profiler import inspect_classification_target, inspect_csv_dataset

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
repo = os.path.dirname(root)
path = os.path.join(repo, 'validation/data/prepared/adult.csv')
i = inspect_csv_dataset(path, preview_rows=10)
opts = [{k: o.get(k) for k in ('name', 'group', 'observed_distinct_count', 'missing_count', 'selector_explanation')} for o in i['target_options']]
targets = {}
for o in i['target_options']:
    try:
        t = inspect_classification_target(path, o['name'])
        s = t['suitability']
        targets[o['name']] = {
            'subtype': t['classification_subtype'], 'class_count': t['class_count'], 'labeled': t['labeled_row_count'], 'missing': t['target_missing_count'],
            'distribution': t['target_distribution'][:8], 'more_classes': max(0, len(t['target_distribution']) - 8),
            'explanation': s['explanation'], 'requires_override': s['requires_override'], 'disabled': s['disabled'],
        }
    except Exception as exc:  # recorded as the UI would see it, not hidden
        targets[o['name']] = {'error': str(exc)}
out = {
    'file': 'adult.csv', 'file_size': os.path.getsize(path), 'row_count': i['row_count'], 'column_count': i['column_count'],
    'columns': i['columns'], 'preview': [[str(r.get(c, '')) for c in i['columns']] for r in i['preview']],
    'target_options': opts, 'targets': targets,
}
json.dump(out, open(os.path.join(root, 'src/fixture/inspect.generated.json'), 'w'), indent=1, default=str)
print('options', len(opts), 'targets', len(targets), 'errors', sum('error' in v for v in targets.values()), 'size', out['file_size'])
for k, v in targets.items(): print(k, v.get('subtype'), v.get('class_count'), v.get('requires_override'), (v.get('explanation') or v.get('error', ''))[:90])
