"""Read-only projection of pinned public/synthetic evidence. Writes only to the lab."""
from pathlib import Path
import json, csv, collections, shutil, hashlib, subprocess
import pdfplumber
ROOT=Path(__file__).resolve().parents[2]
LAB=ROOT/'frontend-design-lab'
assets=LAB/'public/fixtures'
assets.mkdir(parents=True,exist_ok=True)
summary=json.loads((ROOT/'validation/results/validation_summary.json').read_text())['results']['adult']
with (ROOT/'validation/data/prepared/adult.csv').open() as f:
    rows=list(csv.DictReader(f))
counts=collections.Counter(r['annual_income_over_50k'] for r in rows)
missing=[{'field':col,'count':sum(not r[col] for r in rows)} for col in rows[0] if col!='annual_income_over_50k']
# Actual conflicting rows, identical features, differing labels; limited to one group.
features=[c for c in rows[0] if c!='annual_income_over_50k']
groups=collections.defaultdict(list)
for i,row in enumerate(rows): groups[tuple(row[c] for c in features)].append({'row':i+2,**row})
conflicts=[g for g in groups.values() if len({r['annual_income_over_50k'] for r in g})>1]
summary.update(class_counts=dict(counts),missingness=sorted(missing,key=lambda r:-r['count']),preview=[{k:r[k] for k in ['age','education','hours_per_week','annual_income_over_50k']} for r in rows[:5]],conflict_example=[{k:r[k] for k in ['row','age','education','hours_per_week','annual_income_over_50k']} for r in conflicts[0]])
summary['risks'].append({'code':'leakage_review_prompts','title':'Prediction-time availability needs review','severity':'Low','finding':'The marital_status field has a generic status-like name.','evidence':'Name-based review prompt only; no strong leakage candidate.','modeling_impact':'Availability cannot be established from a column name.','recommendation':'Confirm collection timing with the source owner.','score_effect':'Review only; does not affect scoring.'})
(LAB/'src/fixtures/classification.json').write_text(json.dumps(summary,indent=2))
(assets/'adult-summary.json').write_text(json.dumps(summary,indent=2))
shutil.copyfile(ROOT/'validation/reports/adult.html',assets/'adult-report.html')
bounded=ROOT/'validation/m9/data/bounded'
records=[]
with (bounded/'records.csv').open() as f:
    for row in csv.DictReader(f):
        docs=[]
        for path in sorted(bounded.glob(row['id']+'-*.pdf')):
            with pdfplumber.open(path) as pdf: text=pdf.pages[0].extract_text()
            docs.append({'file':path.name,'text':text,'page':1})
            shutil.copyfile(path,assets/path.name)
        status='conflicting_evidence' if row['id']=='A020' else 'violated' if row['id']=='A019' else 'satisfied'
        records.append({**row,'status':status,'documents':docs})
(LAB/'src/fixtures/connected.json').write_text(json.dumps(records,indent=2))
for kind in ['json','html','pdf']:
    shutil.copyfile(ROOT/f'validation/m9/results/reports/final/bounded.{kind}',assets/f'm9-report.{kind}')
shutil.copyfile(bounded/'records.csv',assets/'records.csv')
shutil.copyfile(bounded/'documents.csv',assets/'documents.csv')
files=subprocess.check_output(['git','ls-files','-co','--exclude-standard'],cwd=ROOT,text=True).splitlines()
state={}
for name in files:
    path=ROOT/name
    if name.startswith('frontend-design-lab/') or not path.is_file(): continue
    state[name]={'size':path.stat().st_size,'mtime_ns':path.stat().st_mtime_ns}
    if path.suffix in ['.py','.md','.html','.json','.toml','.csv'] and path.stat().st_size<2_000_000:
        state[name]['sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
(LAB/'research/production-baseline.json').write_text(json.dumps(state,indent=2))
print('Fixture projection: Adult',counts,'conflicting groups',len(conflicts))
print('M9 exact PDF excerpts:',[(r['id'],r['documents']) for r in records[-2:]])
print('Production baseline files:',len(state))
