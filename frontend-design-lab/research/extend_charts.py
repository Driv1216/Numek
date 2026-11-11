from pathlib import Path
import csv,json
ROOT=Path(__file__).resolve().parents[2]
LAB=ROOT/'frontend-design-lab'
p=LAB/'src/fixtures/classification.json'
data=json.loads(p.read_text())
with (ROOT/'validation/data/prepared/adult.csv').open() as f: rows=list(csv.DictReader(f))
bins=[]
for low,high in [(0,9),(10,19),(20,29),(30,39),(40,49),(50,59),(60,69),(70,79),(80,89),(90,99)]:
    group=[r for r in rows if low<=int(r['hours_per_week'])<=high]
    counts={label:sum(r['annual_income_over_50k']==label for r in group) for label in ['<=50K','>50K']}
    examples={label:[{k:r[k] for k in ['age','education','hours_per_week','annual_income_over_50k']} for r in group if r['annual_income_over_50k']==label][:5] for label in counts}
    bins.append({'label':f'{low}–{high}','lower':low,'upper':high,'counts':counts,'examples':examples})
data['hour_bins']=bins
p.write_text(json.dumps(data,indent=2))
(LAB/'public/fixtures/adult-summary.json').write_text(json.dumps(data,indent=2))
print('Histogram rows',sum(sum(b['counts'].values()) for b in bins))
