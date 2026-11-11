import sys,tempfile,json,csv,hashlib
from pathlib import Path
from dataclasses import replace

ROOT=Path('/Users/drivyaanshyadav/Desktop/Numek')
sys.path.insert(0,str(ROOT/'tests/cg4'))
from helpers import binary
from confidenceguard import investigate,freeze_hypotheses
from confidenceguard.confirmation import _input


def main():
    rows=[]
    with tempfile.TemporaryDirectory(prefix='numek-cg4-frozen-observation-policy-',dir='/private/tmp') as temporary:
        p=Path(temporary);spec=binary(p);source=p/'predictions.csv'
        with source.open() as stream:values=list(csv.DictReader(stream))
        for row in values:row['status']='pending' if row['role']=='H' and row['decision']!=row['y'] else 'final'
        with source.open('w',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=values[0]);writer.writeheader();writer.writerows(values)
        outcome=replace(spec.evaluation.outcomes,status_column='status',status_values={'final':'final','pending':'pending'})
        spec=replace(spec,evaluation=replace(spec.evaluation,outcomes=outcome))
        result=investigate(spec);family=freeze_hypotheses(result)
        cases={'pending_reclassified_final':replace(spec,evaluation=replace(spec.evaluation,outcomes=replace(outcome,status_values={'final':'final','pending':'final'}))),
               'feature_time_view_revised':replace(spec,feature_time_view='retrospective')}
        for case,revised in cases.items():
            try:_input(family,revised);accepted=True;reason=None
            except Exception as exc:accepted=False;reason=getattr(exc,'code',str(exc))
            rows.append({'case':case,'revised_input_accepted':accepted,'reason':reason})
        record={'scope':'Pre-correction frozen-claim admission probe. Discovery used D/S only; no H metrics, H reservation, inference or claim was computed. Source is authored synthetic data; pending H outcomes must not be reclassified after freezing.',
            'cases':rows,'family_observation_policy':family.data['hypotheses'][0]['population_policy']['observation_policy'],
            'source_sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [ROOT/'src/confidenceguard/confirmation.py',ROOT/'src/confidenceguard/investigation.py']},
            'probe_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
        with (ROOT/'validation/cg4/results/frozen-observation-policy-before-correction-v1.json').open('x') as stream:
            json.dump(record,stream,indent=2,sort_keys=True);stream.write('\n')
        print(json.dumps(rows))


if __name__=='__main__':main()
