# Read-only: builds src/fixture/relief.generated.json for the Relief concept.
#   adult: counts of rows per (age, hours_per_week), age 17–90 × hours 1–99
#   bike:  mean cnt per (weekday, hour) over all 17,379 rows
# Run from the repository root:  .venv/bin/python frontend-visual-lab-v3/scripts/extract_relief.py
import json, os
import pandas as pd
root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
repo = os.path.dirname(root)
a = pd.read_csv(os.path.join(repo, 'validation/data/prepared/adult.csv'), usecols=['age', 'hours_per_week'])
ages, hours = list(range(17, 91)), list(range(1, 100))
grid = a.groupby(['age', 'hours_per_week']).size()
adult = [[int(grid.get((ag, h), 0)) for h in hours] for ag in ages]
b = pd.read_csv(os.path.join(repo, 'validation/regression/data/prepared/bike_hour.csv'), usecols=['weekday', 'hr', 'cnt'])
bm = b.groupby(['weekday', 'hr'])['cnt'].mean()
bike = [[round(float(bm.get((d, h), 0)), 1) for h in range(24)] for d in range(7)]
out = {'adult': {'ages': [ages[0], ages[-1]], 'hours': [hours[0], hours[-1]], 'rows': int(len(a)), 'grid': adult},
       'bike': {'weekdays': 7, 'hours': 24, 'rows': int(len(b)), 'mean_cnt': bike}}
json.dump(out, open(os.path.join(root, 'src/fixture/relief.generated.json'), 'w'), separators=(',', ':'))
print('adult cells', sum(map(sum, adult)), 'max', max(map(max, adult)), '| bike max mean', max(map(max, bike)))
