"""Canonical synthetic report, disclosure-sentinel and renderer verification."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import sys


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--out',required=True);args=parser.parse_args()
    root=Path(__file__).resolve().parents[2];sys.path.insert(0,str(root/'tests/cg4'))
    from helpers import binary
    from confidenceguard import investigate,annotate_investigation
    from pypdf import PdfReader
    directory=Path(args.out).absolute();directory.mkdir(parents=True,exist_ok=True)
    source=directory/'source';source.mkdir(exist_ok=True)
    discovery=investigate(binary(source));sentinel='CG4_PRIVATE_SENTINEL_27E39F'
    discovery=annotate_investigation(discovery,sentinel+' Synthetic private interpretation; no causal inference.')
    artifacts={};public_text=[];private_text=[]
    for audience in ('shareable','local'):
        report=discovery.generate_artifacts(directory/(audience+'.pdf'),format='pdf',audience=audience,json_path=directory/(audience+'.json'))
        artifacts[audience]=report.__dict__;texts=[]
        for path in (report.html_path,report.json_path):texts.append(Path(path).read_text())
        reader=PdfReader(report.pdf_path);texts.extend(page.extract_text() for page in reader.pages)
        artifacts[audience]['pdf_pages']=len(reader.pages)
        (public_text if audience=='shareable' else private_text).extend(texts)
    passed=not any(sentinel in text for text in public_text) and all(sentinel in text for text in private_text[:2])
    payload={'schema_version':'numek.cg4_report_verification/1.0','generated_at':datetime.now(timezone.utc).isoformat(),
        'artifacts':artifacts,'private_sentinel_absent_from_shareable_HTML_JSON_PDF':not any(sentinel in text for text in public_text),
        'private_note_retained':all(sentinel in text for text in private_text[:2]),'passed':passed,
        'visual_inspection':'required_separately','hashes':{str(p.relative_to(directory)):hashlib.sha256(p.read_bytes()).hexdigest() for p in directory.glob('*') if p.is_file()}}
    (directory/'verification.json').write_text(json.dumps(payload,sort_keys=True,indent=2)+'\n');print(json.dumps(payload))
    return not passed


if __name__=='__main__':raise SystemExit(main())
