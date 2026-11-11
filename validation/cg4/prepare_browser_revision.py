"""Add clocked synthetic outcomes without rewriting the unclocked fixture."""
from datetime import datetime,timezone
from pathlib import Path
import csv
import json
from confidenceguard import ReliabilityWorkspace


def main():
    root=Path(__file__).with_name('browser_inputs_v2.nosync').absolute()
    path=root/'clocked-labels-v1.csv'
    if not path.exists():
        now=datetime.now(timezone.utc).isoformat()
        with (root/'predictions.csv').open() as stream:rows=list(csv.DictReader(stream))
        with path.open('x',newline='') as stream:
            writer=csv.writer(stream);writer.writerow(['id','y','revision','order','available','status'])
            writer.writerows((r['id'],r['y'],'clocked-labels-v1','1',now,'final') for r in rows)
    ws=ReliabilityWorkspace(root/'workspace')
    # The original supplied authority has unknown availability. Keep its facts
    # and conservative interpretation. This explicitly named synthetic authority
    # contains only newly acquired, fully clocked revisions.
    spec={'source':{'id':'outcomes','path':str(path)},'namespace':'fixture-browser_inputs_v2.nosync',
        'outcome_definition_version':'v1','authority':'cg4_synthetic_clocked_labels','event_columns':['id'],'column':'y',
        'revision_column':'revision','order_column':'order','available_at':{'column':'available'},'status_column':'status'}
    print(json.dumps(ws.update_outcomes(spec,request_id='browser-clocked-authority-v1')))
    print(json.dumps({'as_of':datetime.now(timezone.utc).isoformat(),'source':'clocked-labels-v1.csv',
                      'authority':spec['authority'],'synthetic':True}))


if __name__=='__main__':main()
