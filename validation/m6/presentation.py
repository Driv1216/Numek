"""Authored invalid/Unicode/model report and explicit disclosure variant."""
from dataclasses import replace
import hashlib,json
from pathlib import Path
from datatrust import *
ROOT=Path(__file__).parent

def run():
    data=ROOT/'data/authored';data.mkdir(exist_ok=True);source=data/'controls.jsonl'
    text='हिन्दी पाठ e\u0301 😀 <b>literal markup</b> \u202e bidi control'
    long=('Preserved local source content and source-aligned annotations. '*140)+'A closing हिन्दी sentence.'
    rows=[{'id':str(i),'text':t,'label':'SECRET_LABEL','spans':spans,'messages':messages} for i,(t,spans,messages) in enumerate([
        (text,[],[{'role':'user','content':text},{'role':'assistant','content':'Completion'}]),
        (text,[{'start':0,'end':2},{'start':9000,'end':9001}],[]),
        (long,[],[{'role':'assistant','content':None,'tool_calls':[{'id':'call','function':{'name':'local','arguments':'{"x":1}'}}]},{'role':'tool','tool_call_id':'call','content':'Done'}]),
        ('NA',[],[{'role':'user','content':'NA'},{'role':'user','content':'Valid nonalternating roles'}]),
        ('',[],[]),(None,[],[]),(17,[],[]),('bad\ud800',[],[]),
    ])]
    raw=('\n'.join(json.dumps(x,ensure_ascii=True) for x in rows)+'\n{"duplicate":1,"duplicate":2}\n\nnot json\n').encode()
    if source.exists():assert source.read_bytes()==raw
    else:source.write_bytes(raw)
    spec=TextAuditSpec((TextInputSpec('controls',TextSourceSpec(str(source.resolve())),(TextFieldSpec('text','text'),),id_selector='id',annotations=(TextAnnotationSpec('text','label'),TextAnnotationSpec('text','spans',kind='span')),conversation=TextConversationSpec()),),allowed_roots=(str(data.resolve()),))
    cfg=TextAnalysisConfig(limits=replace(TextWorkLimits(),lexical_units=32,signature_work=100000,shingle_positions=100000,verification_visits=100000,details=5,language_units=16,embedding_windows=32),models=TextModelOptions(language=True,embedding_directory=str((ROOT/'models/multilingual-e5-small').resolve()),tokenizer=True))
    r=DataTrust.audit_text(spec,cfg);out=ROOT/'results/reports'/r.profile['audit_id'];out.mkdir(parents=True,mode=0o700)
    default=r.generate_artifacts(out/'controls.pdf',format='pdf',json_path=out/'controls.json')
    refs=next(x['references'] for x in r.evidence if x['family']=='exact_duplicates')[:2]
    excerpt=r.generate_artifacts(out/'excerpts.pdf',format='pdf',excerpt_refs=tuple(refs),allowed_roots=spec.allowed_roots,json_path=out/'excerpts.json')
    from pypdf import PdfReader
    ledger={'source_sha256':hashlib.sha256(raw).hexdigest(),'execution':r.execution,'coverage':r.coverage,'default':{'path':str(Path(default.pdf_path).relative_to(ROOT)),'pages':len(PdfReader(default.pdf_path).pages)},'excerpt':{'path':str(Path(excerpt.pdf_path).relative_to(ROOT)),'pages':len(PdfReader(excerpt.pdf_path).pages)},'public_default_private':True}
    assert 'SECRET_LABEL' not in Path(default.json_path).read_text() and text not in Path(default.html_path).read_text()
    assert '&lt;b&gt;' in Path(excerpt.html_path).read_text() and '[U+202E]' in Path(excerpt.html_path).read_text()
    (ROOT/'results/presentation.json').write_text(json.dumps(ledger,indent=2,allow_nan=False)+'\n');print(json.dumps({k:v for k,v in ledger.items() if k in {'default','excerpt'}}))
if __name__=='__main__':run()
