from dataclasses import replace
import json
from pathlib import Path
import pytest
from datatrust import *
from datatrust.cross import _core,finalize
from datatrust.cross_diagnostics import compare,context
from datatrust.cross_sources import key
from validation.m9.fixtures import financial


def complete(spec,config=None):
    config=config or CrossRepresentationAnalysisConfig()
    return finalize(_core(spec,config),spec,config)


def test_contract_strict_roundtrip(tmp_path):
    s=financial(tmp_path,count=3)
    assert CrossRepresentationAuditSpec.from_dict(s.to_dict())==s
    with pytest.raises(ValueError): CrossRepresentationAnalysisConfig.from_dict({'bogus':True})
    with pytest.raises(ValueError): RelationshipSpec('r','a','b',cardinality='many_to_many')
    with pytest.raises(ValueError): ReconciliationRule('r','x','v',mapping='m',right_field='v')
    with pytest.raises(ValueError): CrossWorkLimits(candidates=True)


@pytest.mark.parametrize('fmt',['pdf','docx'])
def test_financial_reusable_conflicts_and_exact_locations(tmp_path,fmt):
    spec=financial(tmp_path,count=20,format=fmt);r=complete(spec)
    ev=next(e for e in r.evidence if e['population']=='rule_1')
    assert {k:ev['data'].get(k,0) for k in ['satisfied','violated','conflicting_evidence']}=={'satisfied':18,'violated':1,'conflicting_evidence':1}
    conflict=next(d for d in ev['data']['details'] if d['status']=='conflicting_evidence')
    resolved=[r.resolve_evidence(ref,allowed_roots=(str(tmp_path),),reveal_content=True) for ref in conflict['evidence_refs']]
    assert {'12000000','1200000'}<={x['excerpt'] for x in resolved}
    for x in resolved[1:]:
        assert ('page' in x['location']) == (fmt=='pdf')
        assert ('xml_path' in x['location']) == (fmt=='docx')
    assert r.profile['documents']==21
    for marker in ('12000000',str(tmp_path),'Company A001','Revenue'):
        assert marker not in r.json_text()


def test_reviews_roundtrip_and_immutability(tmp_path):
    r=complete(financial(tmp_path,count=3));original=r.json_text();review=r.review_dispositions('local reviewer');target=next(iter(r.profile['review_targets']))
    review.set(target,'confirm','PRIVATE REVIEW NOTE')
    loaded=ReviewDispositionSet.from_dict(review.to_dict(),result=r)
    assert loaded.entries==review.entries and r.json_text()==original
    changed=review.to_dict();changed['result_sha256']='0'*64
    with pytest.raises(ValueError): ReviewDispositionSet.from_dict(changed,result=r)
    with pytest.raises(ValueError): review.set(target,'dismiss','x'*2001)
    with pytest.raises(ValueError): review.set('other','confirm')


def test_declared_precision_keys_and_context():
    assert key({'id':'001'},('id',))!=key({'id':'1'},('id',))
    assert key({'id':1},('id',))!=key({'id':'1'},('id',))
    assert key({'id':'NA'},('id',)) is not None
    rule=ReconciliationRule('r','rel','x',right_field='x',factor='1000000')
    assert compare('12000000','12',rule)
    assert compare('100000000000000000000000000000000000000000000000001','100000000000000000000000000000000000000000000000002',replace(rule,factor='1')) is False
    rel=RelationshipSpec('r','a','b',context={'period':['period','period']},availability=ClockSpec('published'),cutoff=ClockSpec('cutoff'))
    assert context(rel,{'period':'2025','cutoff':'2026-01-01T00:00:00Z'},{'period':'2024','published':'2025-01-01T00:00:00Z'})['excluded']==['period']
    assert not context(rel,{'period':'2025','cutoff':'2026-01-01'},{'period':'2025','published':'2025-01-01T00:00:00Z'})['eligible']


def test_changed_source_no_repair(tmp_path):
    r=complete(financial(tmp_path,count=3));ref=next(iter(r.private['locators']));Path(r.private['locators'][ref]['source']).write_text('changed')
    with pytest.raises((AnalysisError,ValueError)): r.resolve_evidence(ref,allowed_roots=(str(tmp_path),),reveal_content=True)


def test_bounded_mapping_cannot_agree(tmp_path):
    spec=financial(tmp_path,count=3)
    spec=replace(spec,mappings=(replace(spec.mappings[0],layout='wrong'),spec.mappings[1]))
    r=complete(spec)
    assert next(e for e in r.evidence if e['population']=='rule_1')['data']['inconclusive']==3


def test_supervision_exports_reload_and_disclosure(tmp_path):
    spec=financial(tmp_path,count=3);r=DataTrust.audit_cross_representation(spec)
    a=r.generate_artifacts(tmp_path/'report.html',json_path=tmp_path/'analysis.json')
    restored=CrossRepresentationAuditResult.from_dict(json.loads(Path(a.json_path).read_text()),private=a.private_manifest_path)
    assert restored.json_text()==r.json_text()
    review=r.review_dispositions();target=next(iter(review.targets));review.set(target,'unresolved','sensitive note')
    ReviewDispositionSet.from_dict(review.to_dict(),result=restored)
    assert 'sensitive note' not in Path(a.html_path).read_text()
    ref=next(iter(r.private['locators']));variant=r.generate_artifacts(tmp_path/'disclosed.html',disclosure=CrossDisclosureOptions((ref,)),allowed_roots=(str(tmp_path),))
    assert variant.html_path!=a.html_path
