"""R1's additional source fields must survive existing completed-evidence reuse."""
import csv
from dataclasses import replace
import pytest

from confidenceguard import (FeatureField, ClockSpec, apply_auxiliary,
    as_reliability_spec, restate_execution, ExecutionRestatementSpec)
from .helpers import execution,CFG
from .test_review_corrections import auxiliary


@pytest.mark.parametrize('consumer',['bridge','restatement'])
def test_r1_additional_fields_and_clocks_survive_completed_reuse(tmp_path,consumer):
    spec=execution(tmp_path,regression=True,n=8)
    with open(spec.sources[0].path) as stream:records=list(csv.DictReader(stream))
    for row in records:row.update(available='2025-12-31T00:00:00Z',cutoff='2026-01-01T00:00:00Z')
    with open(spec.sources[0].path,'w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(records[0]));writer.writeheader();writer.writerows(records)
    spec=replace(spec,information_cutoff=ClockSpec('cutoff'))
    artifact=auxiliary(spec,FeatureField('z','z','float',available_at=ClockSpec('available')))
    result=apply_auxiliary(spec,artifact,CFG)
    if consumer=='bridge':
        linked=as_reliability_spec(result,scope='auxiliary_application',directory=tmp_path/'bridge')
        with open(linked.evaluation.sources[0].path) as stream:rows=list(csv.DictReader(stream))
        assert rows and all(r['z']!='' and r['available']=='2025-12-31T00:00:00Z' for r in rows)
    else:
        revised=restate_execution(result,ExecutionRestatementSpec(spec.sources,spec.outcomes,'R1 frozen-input control'),CFG)
        assert not revised.data['cg6']['execution_repeated']
        assert all('z' in r['input_record'] and 'available' in r['input_record'] for r in revised.private['output_rows'])
        assert [(r['event_key'],r['channels']) for r in revised.private['output_rows']]==[(r['event_key'],r['channels']) for r in result.private['output_rows']]
