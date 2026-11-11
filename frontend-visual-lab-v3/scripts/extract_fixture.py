"""Builds the lab's shared fixture from preserved repository evidence (read-only).

Inputs: validation/data/prepared/adult.csv and validation/reports/adult.html.
Output: src/fixture/adult.generated.json and src/fixture/adult-rows.generated.json.
Nothing outside frontend-visual-lab-v3 is written.
"""
import base64, html, json, re
from pathlib import Path
import numpy as np
import pandas as pd

repo = Path(__file__).resolve().parents[2]
out = Path(__file__).resolve().parents[1] / 'src' / 'fixture'
df = pd.read_csv(repo / 'validation/data/prepared/adult.csv', keep_default_na=True, na_values=['?'])
target = 'annual_income_over_50k'
feats = [c for c in df.columns if c != target]

# Per-column appendix values are taken from the canonical report, not recomputed.
t = (repo / 'validation/reports/adult.html').read_text()
t = re.sub(r'<(script|style)[\s\S]*?</\1>', '', t)
lines = [html.unescape(l).strip() for l in re.sub(r'<[^>]+>', '\n', t).split('\n')]
lines = [l for l in lines if l]
cols = []
i = lines.index('Outliers') + 1
while len(cols) < len(df.columns):
    name = lines[i].replace('_\n', '_')
    # wrapped names like "final_" "weight" appear on consecutive lines
    while name.endswith('_'):
        i += 1; name += lines[i]
    rec = lines[i + 1:i + 11]
    cols.append(dict(name=name, role=rec[0], type=rec[1], non_null=rec[2], missing=rec[3], unique=rec[4],
                     top_share=rec[5], constant=rec[6], near_constant=rec[7], high_cardinality=rec[8], outliers=rec[9]))
    i += 11

missing_per_row = df[feats].isna().sum(axis=1).clip(upper=3).to_numpy()
cls = (df[target] == '>50K').astype(int).to_numpy()

# Exact duplicate groups over all columns; "repeated" counts rows beyond the first.
key_all = pd.util.hash_pandas_object(df.fillna('<NA>'), index=False)
dup_sizes = key_all.value_counts()
dup_keys = set(dup_sizes[dup_sizes > 1].index)
is_dup = key_all.isin(dup_keys).to_numpy()
dup_id = np.zeros(len(df), dtype=int)
for n, k in enumerate(sorted(dup_keys, key=lambda k: np.where(key_all.values == k)[0][0]), 1):
    dup_id[key_all.values == k] = n

# Feature-identical groups with more than one non-missing label.
key_f = pd.util.hash_pandas_object(df[feats].fillna('<NA>'), index=False)
g = df.assign(_k=key_f.values).groupby('_k')[target].nunique()
conf_keys = list(g[g > 1].index)
conflict_id = np.zeros(len(df), dtype=int)
groups = []
for n, k in enumerate(conf_keys, 1):
    idx = np.where(key_f.values == k)[0]
    conflict_id[idx] = n
    rows = df.iloc[idx]
    groups.append(dict(id=n, rows=[int(x) + 1 for x in idx],
                       features={c: (None if pd.isna(rows.iloc[0][c]) else (rows.iloc[0][c].item() if hasattr(rows.iloc[0][c], 'item') else rows.iloc[0][c])) for c in feats},
                       labels=list(rows[target])))

def iqr(col):
    s = df[col].dropna(); q1, q3 = s.quantile(.25), s.quantile(.75); r = q3 - q1
    lo, hi = q1 - 1.5 * r, q3 + 1.5 * r
    return float(q1), float(q3), float(lo), float(hi), ((s < lo) | (s > hi))

h_q1, h_q3, h_lo, h_hi, h_out = iqr('hours_per_week')
a_q1, a_q3, a_lo, a_hi, a_out = iqr('age')
hours = df['hours_per_week'].to_numpy()
hours_out = ((hours < h_lo) | (hours > h_hi))

def hist(col, lo, hi, step=1):
    v = df[col].to_numpy(); edges = np.arange(lo, hi + step, step)
    c, _ = np.histogram(v, bins=edges); return dict(start=lo, step=step, counts=c.tolist())

flags = (cls | (missing_per_row << 1) | (is_dup.astype(int) << 3) | (hours_out.astype(int) << 4)).astype(np.uint8)
packed = np.stack([flags, df['age'].clip(0, 255).to_numpy().astype(np.uint8), np.clip(hours, 0, 255).astype(np.uint8), conflict_id.astype(np.uint8), dup_id.astype(np.uint8)], axis=1).ravel()

summary = dict(
    rows=len(df), columns=len(df.columns), target=target,
    classes=dict(le50k=int((cls == 0).sum()), gt50k=int(cls.sum())),
    missing_rows=dict(one=int((missing_per_row == 1).sum()), two=int((missing_per_row == 2).sum()), three_plus=int((missing_per_row >= 3).sum())),
    missing_by_col={c: int(df[c].isna().sum()) for c in feats if df[c].isna().any()},
    duplicates=dict(groups=int((dup_sizes > 1).sum()), repeated_rows=int((dup_sizes[dup_sizes > 1] - 1).sum()), rows_in_groups=int(is_dup.sum()), largest=int(dup_sizes.max())),
    conflicts=groups,
    hours=dict(q1=h_q1, q3=h_q3, lower=h_lo, upper=h_hi, outliers=int(h_out.sum()), below=int((df['hours_per_week'] < h_lo).sum()), above=int((df['hours_per_week'] > h_hi).sum()), hist=hist('hours_per_week', 1, 99)),
    age=dict(q1=a_q1, q3=a_q3, lower=a_lo, upper=a_hi, outliers=int(a_out.sum()), hist=hist('age', 17, 90)),
    column_evidence=cols,
    sample_rows=df.head(14).fillna('?').astype(str).values.tolist(),
)
(out / 'adult.generated.json').write_text(json.dumps(summary, indent=1))
(out / 'adult-rows.generated.json').write_text(json.dumps(dict(stride=5, layout='flags(class|miss<<1|dup<<3|hoursOut<<4), age, hours, conflictGroup, dupGroup', data=base64.b64encode(packed.tobytes()).decode())))
print(json.dumps({k: summary[k] for k in ['rows', 'classes', 'missing_rows', 'duplicates']}), 'conflict groups', len(groups), 'hours', summary['hours']['outliers'], h_lo, h_hi, 'cols', [c['name'] for c in cols])
