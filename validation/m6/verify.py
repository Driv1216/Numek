"""M6 closure: pinned public populations, independent supplied-data truth and exports."""
from dataclasses import replace
import csv,hashlib,importlib.metadata,json,platform,time
from pathlib import Path
from datatrust import *
from datatrust.text_normalization import strict_json

ROOT=Path(__file__).parent

def sha(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def run(selected=None):
    manifest=json.loads((ROOT/'data/prepared_manifest.json').read_text());out=ROOT/'results';out.mkdir(exist_ok=True)
    for item in manifest['prepared'].values():assert sha(ROOT/item['path'])==item['sha256']
    ledger={'status':'running','python':platform.python_version(),'platform':platform.platform(),'new_evidence':{},'reused_evidence':['Pinned LSH grid calibration; 1 GiB full-population supervised workload (structural methods unchanged)','Historical M1–M5 artifacts are verified by the repository suite, never regenerated.']}
    if selected and (out/'verification.json').exists():ledger['new_evidence']=json.loads((out/'verification.json').read_text())['new_evidence']
    def data(r,family):return next(x['data'] for x in r.evidence if x['family']==family)
    def rows(name):return [json.loads(x) for x in (ROOT/manifest['prepared'][name]['path']).read_text().splitlines()]
    for name,case in manifest['cases'].items():
        if selected and name not in selected:continue
        spec=TextAuditSpec.from_dict(case['spec'],base_directory=ROOT);config=TextAnalysisConfig.from_dict(case['config']);tick=time.monotonic();r=DataTrust.audit_text(spec,config)
        population=sum(manifest['prepared'][Path(x.source.path).stem]['rows'] for x in spec.inputs)
        assert sum(x['records'] for x in r.profile['source_populations'].values())==population
        if name=='sms':
            with (ROOT/manifest['prepared']['sms']['path']).open() as f:raw=list(csv.DictReader(f))
            assert data(r,'corpus')['characters']==sum(len(x['text']) for x in raw)
            assert data(r,'annotation_categories')['category_count']==2
        elif name.startswith('ud_'):
            assert data(r,'annotations')['supplied_tokens']==sum(len(x['tokens']) for x in rows(name))
        elif name=='squad':
            raw=rows(name);assert data(r,'corpus')['content_units']==2*len(raw)
            assert data(r,'annotations')['annotation_items']==sum(len(x['answers']) for x in raw)
        elif name=='oasst':
            assert data(r,'conversations')['messages']==sum(len(x['messages']) for x in rows(name))
        elif name=='scifact':
            assert not any(data(r,'retrieval')['violations'].values())
            expected=sum(x['end']-x['start'] for x in rows('scifact_chunks'))
            assert data(r,'retrieval')['covered_source_characters_union']==expected
            assert data(r,'retrieval')['judgment_states']['positive']==72
        elif name=='pairing':assert data(r,'invalidity')['invalid_items']==2 and r.profile['asset_references']==16
        run_dir=out/'reports'/r.profile['audit_id'];run_dir.mkdir(parents=True,mode=0o700)
        artifacts=r.generate_artifacts(run_dir/f'{name}.html',json_path=run_dir/f'{name}.json')
        public=(run_dir/f'{name}.json').read_text();assert str(ROOT.resolve()) not in public
        strict_json(public)
        for reference in list(r.private['locators'])[:10]:assert r.resolve_evidence(reference,allowed_roots=spec.allowed_roots)['status']=='resolved'
        entry={'records':population,'seconds':time.monotonic()-tick,'execution':r.execution,'coverage':r.coverage,'source_hashes':r.execution['provenance'],'artifact_directory':str(run_dir.relative_to(ROOT)),'artifact_hashes':{'html':sha(artifacts.html_path),'json':sha(artifacts.json_path)},'transformation':case['transformation']}
        if name in {'squad','ud_hindi','scifact'}:
            pdf=r.generate_artifacts(run_dir/f'{name}.pdf',format='pdf');from pypdf import PdfReader
            reader=PdfReader(pdf.pdf_path);text='\n'.join(p.extract_text() for p in reader.pages)
            assert 'Methods and coverage' in text and 'Corpus integrity' in text
            entry['pdf']={'pages':len(reader.pages),'sha256':sha(pdf.pdf_path),'qa':pdf.qa_metadata}
        ledger['new_evidence'][name]=entry;(out/'verification.json').write_text(json.dumps(ledger,indent=2,allow_nan=False)+'\n');print(name,'passed',round(entry['seconds'],2),flush=True)
    ledger['status']='passed';(out/'verification.json').write_text(json.dumps(ledger,indent=2,allow_nan=False)+'\n')

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--cases');a=p.parse_args();run(a.cases.split(',') if a.cases else None)
