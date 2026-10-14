"""Reuse completed public analytics while exporting a new canonical projection."""
import hashlib,json
from pathlib import Path
from pypdf import PdfReader
from datatrust import TextAuditResult
ROOT=Path(__file__).parent

def run():
    file=ROOT/'results/verification.json';ledger=json.loads(file.read_text())
    version=hashlib.sha256((Path('src/datatrust/templates/text_report.html').read_bytes()+Path('src/datatrust/text_presentation.py').read_bytes())).hexdigest()[:12]
    for name,entry in ledger['new_evidence'].items():
        if 'pdf' not in entry:continue
        parent=ROOT/entry['artifact_directory'];public=json.loads((parent/(name+'.json')).read_text());audit=public['profile']['audit_id']
        private=json.loads((parent/'.datatrust-private'/audit/'manifest.json').read_text())
        for key in ['export_fingerprint','export_identity','excerpts','disclosure']:public['profile'].pop(key,None)
        r=TextAuditResult(*(public[k] for k in ['profile','checks','evidence','findings','coverage','execution','generated_at']),private)
        out=parent/('render-'+version);out.mkdir(mode=0o700,exist_ok=True)
        a=r.generate_artifacts(out/(name+'.pdf'),format='pdf',json_path=out/(name+'.json'))
        pages=len(PdfReader(a.pdf_path).pages)
        entry['pdf']={'path':str(Path(a.pdf_path).relative_to(ROOT)),'pages':pages,'sha256':hashlib.sha256(Path(a.pdf_path).read_bytes()).hexdigest(),'qa':a.qa_metadata,'reused_completed_analytics':True,'new_projection_sha256':version}
        file.write_text(json.dumps(ledger,indent=2,allow_nan=False)+'\n');print(name,pages,'pages',flush=True)
if __name__=='__main__':run()
