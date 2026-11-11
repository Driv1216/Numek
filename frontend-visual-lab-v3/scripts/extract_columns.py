"""Real per-column distributions for the tabular runs (read-only), used to shape the Collection site's objects.
Writes src/fixture/adult-columns.generated.json (Adult) and src/fixture/columns.generated.json (all four)."""
import json
from pathlib import Path
import numpy as np
import pandas as pd

repo = Path(__file__).resolve().parents[2]
RUNS = {'adult': ('validation/data/prepared/adult.csv', 'annual_income_over_50k'), 'german': ('validation/data/prepared/german_credit.csv', 'credit_risk'),
        'bank': ('validation/data/prepared/bank_marketing.csv', 'subscribed_term_deposit'), 'bike': ('validation/regression/data/prepared/bike_hour.csv', 'cnt')}

def profile(df, target):
  cols = []
  for c in df.columns:
    s = df[c]
    item = dict(name=c, target=c == target, missing=int(s.isna().sum()), unique=int(s.nunique()))
    if pd.api.types.is_numeric_dtype(s):
        v = s.dropna().to_numpy()
        lo, hi = float(v.min()), float(v.max())
        counts, edges = np.histogram(v, bins=32, range=(lo, hi))
        item.update(kind='numeric', min=lo, max=hi, median=float(np.median(v)), mean=round(float(v.mean()), 2),
                    q1=float(np.quantile(v, .25)), q3=float(np.quantile(v, .75)), bins=counts.tolist(), zero_share=round(float((v == 0).mean() * 100), 2))
    else:
        vc = s.value_counts(dropna=True)
        top = [[str(k), int(n)] for k, n in vc.head(10).items()]
        rest = int(vc.iloc[10:].sum())
        if rest: top.append(['other', rest])
        item.update(kind='categorical', values=top)
    cols.append(item)
  return cols

allruns = {}
for rid, (path, target) in RUNS.items():
    d = pd.read_csv(repo / path, na_values=['?'])
    allruns[rid] = dict(rows=len(d), columns=profile(d, target))
base = repo / 'frontend-visual-lab-v3/src/fixture'
(base / 'adult-columns.generated.json').write_text(json.dumps(allruns['adult']['columns'], indent=1))
(base / 'columns.generated.json').write_text(json.dumps(allruns))
print({k: (v['rows'], len(v['columns'])) for k, v in allruns.items()})
