"""Current canonical PDF/HTML/JSON from unchanged saved synthetic evidence.

No discovery, fitting, selection, confirmation or historical restatement. This
checks rendering/disclosure and protected reopening, not statistical qualification.
"""
import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path

from pypdf import PdfReader
from confidenceguard.contracts import DisclosureSpec
from confidenceguard.investigation_result import InvestigationResult
from confidenceguard.result import SharedResult


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--result',required=True);parser.add_argument('--manifest',required=True);parser.add_argument('--out',required=True);args=parser.parse_args()
    source=Path(args.result).resolve();manifest=Path(args.manifest).resolve();out=Path(args.out).resolve();out.mkdir(parents=True,exist_ok=True)
    if (out/'verification.json').exists():raise RuntimeError('Preserve earlier render verification; use a separately identified replay.')
    original_hashes={'result':sha(source),'manifest':sha(manifest)}
    result=InvestigationResult.from_dict(json.loads(source.read_text()),private=json.loads(manifest.read_text()))
    before=result.to_private_dict();private=result.private
    tokens=set(private.get('artifacts',{}))|set(private.get('models',{}))|set(private.get('locators',{}))
    tokens|={c['id'] for c in before['investigation'].get('candidates',[])}
    tokens|={v['path'] for v in private.get('files',{}).values() if v.get('path')}
    tokens|={n['text'] for n in before['investigation'].get('notes',[]) if n.get('text')}
    tokens={t for t in tokens if isinstance(t,str) and len(t)>=8}
    outputs={}
    for name,audience,policy in [('conservative','shareable',None),('exact-aggregates','shareable',DisclosureSpec(policy='exact_aggregates_v1')),('local','local',None)]:
        directory=out/name;directory.mkdir(exist_ok=True)
        artifacts=result.generate_artifacts(directory/'report.pdf',format='pdf',json_path=directory/'report.json',audience=audience,disclosure=policy)
        html=Path(artifacts.html_path).read_text();packet=json.loads(Path(artifacts.json_path).read_text());reader=PdfReader(artifacts.pdf_path)
        pages=[page.extract_text() for page in reader.pages]
        if not pages or any(not page.strip() for page in pages):raise RuntimeError('Unexpected empty report page.')
        if audience=='shareable':
            SharedResult(packet)  # Protected/private result paths must not be published.
            InvestigationResult.from_dict(packet)
            compact=''.join((html+json.dumps(packet)+''.join(pages)).split())
            leaked=[t for t in tokens if ''.join(t.split()) in compact]
            if leaked:raise RuntimeError('Private evidence token appeared in a shareable report.')
            if any(getattr(artifacts,key) for key in ('private_result_path','private_manifest_path','fitted_methods_path')) or (directory/'.confidenceguard-private').exists():
                raise RuntimeError('Shareable export created a protected reopening bundle.')
        else:
            reopened=InvestigationResult.from_dict(json.loads(Path(artifacts.private_result_path).read_text()),private=json.loads(Path(artifacts.private_manifest_path).read_text()))
            if reopened.to_private_dict()!=before:raise RuntimeError('Protected reopening changed historical bytes/semantics.')
            if any(Path(getattr(artifacts,key)).stat().st_mode&0o077 for key in ('private_result_path','private_manifest_path')):raise RuntimeError('Protected artifact permissions are not owner-only.')
        outputs[name]={'artifacts':asdict(artifacts),'pdf_pages':len(pages),'pdf_page_characters':[len(text) for text in pages],
            'hashes':{Path(path).name:sha(path) for path in (artifacts.html_path,artifacts.pdf_path,artifacts.json_path)}}
    if result.to_private_dict()!=before or {'result':sha(source),'manifest':sha(manifest)}!=original_hashes:raise RuntimeError('Saved analytical input changed during report replay.')
    root=Path(__file__).resolve().parents[2]
    record={'schema_version':'numek.cg4_saved_report_replay/1.0','inputs':{'result':str(source),'manifest':str(manifest),'sha256':original_hashes},
        'source_sha256':{name:sha(root/name) for name in ['src/confidenceguard/artifacts.py','src/confidenceguard/investigation_disclosure.py','src/confidenceguard/templates/report.html','src/confidenceguard/templates/investigation_sections.html']},
        'harness_sha256':sha(__file__),'private_token_count':len(tokens),'private_tokens_absent_from_both_shareable_HTML_JSON_PDF':True,
        'protected_reopening_equal':True,'saved_inputs_unchanged':True,'outputs':outputs,'visual_inspection':'pending',
        'scope':'Current canonical report replay from a saved synthetic investigation. No analytics/H computation, new evidence or statistical qualification; visual verification is separate.'}
    (out/'verification.json').write_text(json.dumps(record,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'outputs':{k:v['pdf_pages'] for k,v in outputs.items()},'private_token_count':len(tokens),'visual_inspection':'pending'}))


if __name__=='__main__':main()
