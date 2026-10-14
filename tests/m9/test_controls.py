from dataclasses import replace
from decimal import Decimal
import json
import threading
import pytest
from datatrust import *
from datatrust.cross import _core,finalize
from datatrust.cross_diagnostics import compare
from datatrust.cross_sources import key
from validation.m9.fixtures import financial


def test_context_checks_without_comparison_rules(tmp_path):
    s=financial(tmp_path,count=3)
    p=tmp_path/'documents.csv';p.write_text(p.read_text().replace('2025-12-01T00:00:00Z','2027-12-01T00:00:00Z'))
    s=replace(s,rules=());r=finalize(_core(s,CrossRepresentationAnalysisConfig()),s,CrossRepresentationAnalysisConfig())
    e=next(e for e in r.evidence if e['family']=='context')
    assert e['data']['violated']==4 and e['data']['affected_records']==3
    assert e['references']
    assert any('2027' in r.resolve_evidence(ref,allowed_roots=(str(tmp_path),),reveal_content=True)['excerpt'] for ref in e['references'])


def test_private_manifest_has_locations_not_corpus_text(tmp_path):
    s=financial(tmp_path,count=3);r=finalize(_core(s,CrossRepresentationAnalysisConfig()),s,CrossRepresentationAnalysisConfig())
    raw=json.dumps(r.private)
    assert 'Company A001 was profitable' not in raw
    assert all('value' not in loc.get('unit',{}) for loc in r.private['locators'].values())


def test_value_conventions_and_grouping():
    r=ReconciliationRule('r','x','value',right_field='value',evidence_decimal_separator=',',evidence_thousands_separator='.')
    assert compare('1000.10','1.000,10',r)
    assert compare(Decimal('1000.10'),'1.000,10',r)
    assert compare('1000','1..000',r) is None
    d=ReconciliationRule('r','x','date',right_field='date',method='date',evidence_date_format='%d/%m/%Y')
    assert compare('2025-01-31','31/01/2025',d)
    assert compare('2025-01-31','01/31/2025',d) is None


def test_same_source_split_scopes(tmp_path):
    p=tmp_path/'data.jsonl';p.write_text('\n'.join(json.dumps(x) for x in [{'id':'a','subject':'s','split':'train'},{'id':'b','subject':'s','split':'test'},{'id':'c','subject':'other','split':'train'}]))
    s=CrossRepresentationAuditSpec((CrossRepresentationInputSpec('data',str(p),format='jsonl',split_selector='split'),),separation=(CrossSeparationSpec('separate','data','data',left_keys=('subject',),right_keys=('subject',),left_splits=('train',),right_splits=('test',)),),allowed_roots=(str(tmp_path),))
    r=_core(s,CrossRepresentationAnalysisConfig());e=next(e for e in r.evidence if e['family']=='separation')
    assert e['data']['left_affected_records']==1 and e['data']['right_affected_records']==1 and e['data']['populations']==[2,1]


def test_native_key_types_not_silently_coerced():
    from datatrust.cross_sources import NativeDate
    assert key({'id':NativeDate('2025-01-01')},('id',))!=key({'id':'2025-01-01'},('id',))
    assert key({'id':NativeDate('2025-01-01')},('id',),'lexical')==key({'id':'2025-01-01'},('id',),'lexical')


def test_manual_override_is_explicit_narrow_scope(tmp_path):
    s=financial(tmp_path,count=3)
    m=replace(s.mappings[0],overrides={'A001':{'page':1,'row':1,'column':2}})
    s=replace(s,mappings=(m,s.mappings[1]));r=_core(s,CrossRepresentationAnalysisConfig())
    e=next(e for e in r.evidence if e['population']=='rule_1')
    assert any('manual_override_selected_scope' in d['reasons'] and d['status']=='inconclusive' for d in e['data']['details'])


def test_cancel_and_pdf_failure_surviving_artifacts(tmp_path):
    s=financial(tmp_path,count=3);cancel=threading.Event();cancel.set()
    with pytest.raises(AnalysisError): DataTrust.audit_cross_representation(s,cancel=cancel)
    r=DataTrust.audit_cross_representation(s)
    def broken(*args,**kwargs): raise RuntimeError('PDF failure')
    with pytest.raises(RuntimeError) as info: r.generate_artifacts(tmp_path/'report.pdf',format='pdf',json_path=tmp_path/'report.json',pdf_converter=broken)
    assert info.value.artifacts.html_path and info.value.artifacts.json_path and info.value.artifacts.private_manifest_path
    assert r.execution['peak_worker_rss_bytes']>=r.execution['phase_resources']['core']['peak_worker_rss_bytes']


def test_isolated_optional_fault_preserves_verified_core(tmp_path,monkeypatch):
    import datatrust.cross as cross
    s=financial(tmp_path,count=3);cfg=CrossRepresentationAnalysisConfig(models=CrossModelOptions('unused','unused'))
    monkeypatch.setattr(cross,'preflight',lambda *a:{})
    original=cross.run_supervised
    def supervise(operation,args,options,**kwargs):
        if operation.__name__=='execute': raise AnalysisError('Injected isolated native fault.',code='model_fault',stage='models')
        return original(operation,args,options,**kwargs)
    monkeypatch.setattr(cross,'run_supervised',supervise)
    r=cross.audit_cross_representation(s,cfg)
    assert r.execution['status']=='partial' and r.coverage['models']['committed']==0
    assert r.profile['private_manifest_sha256']


def test_tokenizer_work_boundary_charges_rejected_call():
    from datatrust.cross_models import CountedTokenizer
    from datatrust.text_models import TokenizerBudget
    class Owner:
        limits=CrossWorkLimits(tokenizer_tokens=1)
        tokenizer_work={'calls':0,'bytes':0,'tokens':0}
    t=CountedTokenizer(lambda *a,**k:{'input_ids':[1,2]},Owner)
    with pytest.raises(TokenizerBudget): t('hello')
    assert Owner.tokenizer_work=={'calls':1,'bytes':5,'tokens':2}


def test_context_dst_fold_changes_cutoff_eligibility():
    from datatrust.cross_diagnostics import context
    rel=RelationshipSpec('r','left','right',cutoff=ClockSpec('cutoff'),availability=ClockSpec('published',timezone='America/New_York',fold_column='fold'))
    left={'cutoff':'2024-11-03T06:00:00Z'}
    assert context(rel,left,{'published':'2024-11-03T01:30:00','fold':0})['eligible']
    assert context(rel,left,{'published':'2024-11-03T01:30:00','fold':1})['excluded']==['available_after_cutoff']
    assert context(rel,left,{'published':'2024-03-10T02:30:00','fold':0})['unknown']==['availability_clock']


def test_mutation_prevents_final_publication(tmp_path):
    spec=financial(tmp_path,count=3);cfg=CrossRepresentationAnalysisConfig();result=_core(spec,cfg)
    with (tmp_path/'A003-1.pdf').open('ab') as handle: handle.write(b'changed after core')
    with pytest.raises(AnalysisError) as caught: finalize(result,spec,cfg)
    assert caught.value.code=='source_changed'
    assert 'private_manifest_sha256' not in result.profile
