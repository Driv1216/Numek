# Read-only: builds src/fixture/cg1.generated.json for the Evidence Mark concept from ConfidenceGuard
# CG1's recorded validation evidence (German Credit, model0, 200 held-out predictions).
#   measurements: copied from validation/cg1/results/reports/binary-local.json
#   calibration:  10 equal-width bins of p(bad) vs observed bad rate, from validation/cg1/data/binary.csv
# Run from the repository root:  python3 -I frontend-visual-lab-v3/scripts/extract_cg1.py
import csv, json, os
root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
repo = os.path.dirname(root)
rep = json.load(open(os.path.join(repo, 'validation/cg1/results/reports/binary-local.json')))
want = ['accuracy', 'balanced_accuracy', 'precision', 'recall', 'specificity', 'roc_auc', 'brier', 'issued_errors']
m = {x['metric']: {'value': x['value'], 'denominator': x['denominator']} for x in rep['measurements']
     if x['run'] == 'model0' and x['scope'] == 'overall' and x['metric'] in want}
rows = list(csv.DictReader(open(os.path.join(repo, 'validation/cg1/data/binary.csv'))))
bins = [[0, 0.0, 0] for _ in range(10)]  # n, sum p(bad), observed bad
for r in rows:
    p = float(r['p0_0']); b = bins[min(9, int(p * 10))]
    b[0] += 1; b[1] += p; b[2] += r['outcome'] == 'bad'
wrong = sorted((r for r in rows if r['prediction0'] != r['outcome']), key=lambda r: -max(float(r['p0_0']), float(r['p0_1'])))
w = wrong[0]
out = {
    'dataset': 'German Credit', 'task': rep['task']['kind'], 'positive': rep['task']['positive_class'], 'classes': rep['task']['classes'],
    'generated_at': rep['generated_at'], 'n': len(rows), 'bad': sum(r['outcome'] == 'bad' for r in rows), 'measurements': m,
    'calibration': [{'n': n, 'mean_p': round(s / n, 4) if n else None, 'observed': round(o / n, 4) if n else None} for n, s, o in bins],
    'most_confident_error': {'id': w['id'], 'prediction': w['prediction0'], 'p': round(max(float(w['p0_0']), float(w['p0_1'])), 4), 'outcome': w['outcome']},
}
json.dump(out, open(os.path.join(root, 'src/fixture/cg1.generated.json'), 'w'), indent=1)
print(json.dumps(out)[:900])
