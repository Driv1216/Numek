"""Render current disclosure from saved synthetic browser evidence, without analytics."""
import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path

from confidenceguard.contracts import DisclosureSpec
from confidenceguard.investigation_result import InvestigationResult
from confidenceguard.result import SharedResult


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--result',required=True);parser.add_argument('--manifest',required=True);parser.add_argument('--out',required=True);args=parser.parse_args()
    p=Path(args.result);m=Path(args.manifest);directory=Path(args.out);directory.mkdir(parents=True,exist_ok=True)
    result=InvestigationResult.from_dict(json.loads(p.read_text()),private=json.loads(m.read_text()))
    before=result.to_private_dict();outputs={}
    for name,policy in [('conservative',None),('exact-aggregates',DisclosureSpec(policy='exact_aggregates_v1'))]:
        projection=result.to_dict(disclosure=policy)
        artifacts=asdict(SharedResult(projection).generate_artifacts(directory/(name+'.html'),json_path=directory/(name+'.json')))
        projected=json.loads(Path(artifacts['json_path']).read_text());html=Path(artifacts['html_path']).read_text()
        assert '/Users/' not in html and '/Users/' not in json.dumps(projected)
        assert not any(artifacts[key] for key in ('private_result_path','private_manifest_path','fitted_methods_path'))
        if name=='conservative':
            assert projected['investigation']['overlap']==[] and projected['investigation']['overlap_disclosure']['state']=='withheld'
            assert 'Protected overlap evidence' in html
        else:
            assert projected['investigation']['overlap']['shortlist_union_support']==120
            assert projected['investigation']['overlap']['total_overlapping_pairs']==0
            assert '120 distinct opportunities' in html
        outputs[name]={'files':{str(Path(artifacts[k])):sha(artifacts[k]) for k in ('html_path','json_path')},
            'overlap':projected['investigation']['overlap'],'overlap_disclosure':projected['investigation']['overlap_disclosure']}
    assert before==result.to_private_dict()
    record={'schema_version':'numek.cg4_report_only_replay/1.0','input_result_sha256':sha(p),'input_manifest_sha256':sha(m),
        'rendering_source_sha256':{name:sha(name) for name in ['src/confidenceguard/investigation_disclosure.py','src/confidenceguard/templates/investigation_sections.html']},
        'replay_source_sha256':sha(__file__),'outputs':outputs,
        'scope':'Current canonical rendering from unchanged synthetic browser evidence; no discovery, selection, H access or numerical recomputation. Exact aggregate authorization does not export learned artifacts.'}
    output=directory.parent/'overlap-report-only-replay-v4.json'
    if output.exists() and json.loads(output.read_text())!=record:raise RuntimeError('Preserve prior replay evidence.')
    if not output.exists():output.write_text(json.dumps(record,indent=2,sort_keys=True)+'\n')
    print(json.dumps(record,indent=2))


if __name__=='__main__':main()
