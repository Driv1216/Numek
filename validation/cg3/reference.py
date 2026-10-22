"""Independent standard-library arithmetic over pinned supplied predictions.

No ConfidenceGuard imports, reducer calls, fitting, or report regeneration.
"""
import argparse
import csv
import json
import math
from pathlib import Path


def verify(inputs, reports):
    checked = []
    for label in ('binary', 'multiclass', 'regression'):
        rows = list(csv.DictReader((Path(inputs)/label/'predictions.csv').open()))
        data = json.loads((Path(reports)/(label+'-local.json')).read_text())
        samples = {}
        sample_path = Path(inputs)/label/'samples.csv'
        if sample_path.exists():
            for row in csv.DictReader(sample_path.open()):
                samples.setdefault(row['id'], []).append(float(row['value']))
        for window, selected in [('reference', [r for r in rows if r['when'] < '2026-07-01']),
                                 ('current', [r for r in rows if r['when'] >= '2026-07-01'])]:
            if not selected:
                continue
            expected = {}
            if label == 'regression':
                errors = [float(r['prediction'])-float(r['outcome']) for r in selected]
                expected.update(mae=sum(abs(x) for x in errors)/len(errors),
                                mse=sum(x*x for x in errors)/len(errors),
                                bias=sum(errors)/len(errors),
                                interval_coverage=sum(float(r['q05']) <= float(r['outcome']) <= float(r['q95']) for r in selected)/len(selected))
                if samples:
                    scores = []
                    for row in selected:
                        draws = samples[row['id']]; y = float(row['outcome']); n = len(draws)
                        scores.append(sum(abs(x-y) for x in draws)/n - sum(abs(x-z) for x in draws for z in draws)/(2*n*n))
                    expected['empirical_crps'] = sum(scores)/len(scores)
            else:
                expected['accuracy'] = sum(r['prediction'] == r['outcome'] for r in selected)/len(selected)
                if label == 'binary':
                    expected['brier'] = sum((float(r['p'])-int(r['outcome']))**2 for r in selected)/len(selected)
                    expected['log_loss'] = -sum(math.log(float(r['p']) if r['outcome']=='1' else 1-float(r['p'])) for r in selected)/len(selected)
            for metric, value in expected.items():
                measurement = next(m for m in data['measurements'] if m['metric']==metric and m['scope']==window+'/overall')
                assert measurement['denominator']==len(selected), (label, window, metric, measurement)
                assert math.isclose(measurement['value'], value, rel_tol=1e-10, abs_tol=1e-12), (label, window, metric, value, measurement['value'])
                checked.append({'task':label,'window':window,'metric':metric,'support':len(selected),'expected':value})
    return {'schema':'cg3.independent_arithmetic/1.0','checked':checked,'status':'passed'}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--inputs',type=Path,required=True);p.add_argument('--reports',type=Path,required=True);p.add_argument('--out',type=Path)
    a=p.parse_args();result=verify(a.inputs,a.reports);text=json.dumps(result,indent=2)+'\n'
    if a.out:a.out.write_text(text)
    print(text)
