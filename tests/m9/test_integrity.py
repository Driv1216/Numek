from dataclasses import replace
import io
import json
import zipfile
import pytest
from datatrust import *
from datatrust.cross import _core,finalize
from datatrust.cross_sources import key
from datatrust.cross_documents import extract
from validation.m9.fixtures import financial


def table_spec(tmp_path,left,right,rel=None,separation=()):
    for name,records in [('left',left),('right',right)]: (tmp_path/(name+'.jsonl')).write_text('\n'.join(json.dumps(x) for x in records)+'\n')
    return CrossRepresentationAuditSpec((CrossRepresentationInputSpec('left',str(tmp_path/'left.jsonl'),format='jsonl'),CrossRepresentationInputSpec('right',str(tmp_path/'right.jsonl'),format='jsonl')),relationships=(rel or RelationshipSpec('rel','left','right',cardinality='one_to_one'),),rules=(ReconciliationRule('value','rel','value',right_field='value'),),separation=separation,allowed_roots=(str(tmp_path),))


def core(spec,cfg=None):
    cfg=cfg or CrossRepresentationAnalysisConfig();return finalize(_core(spec,cfg),spec,cfg)


def test_duplicate_unique_keys_block_no_cartesian(tmp_path):
    s=table_spec(tmp_path,[{'id':'a','value':1}],[{'id':'a','value':1},{'id':'a','value':2}]);r=core(s)
    assert next(e for e in r.evidence if e['family']=='relationships')['data']['associations']==0
    assert next(e for e in r.evidence if e['family']=='relationships')['data']['cardinality_violations']==1
    assert next(e for e in r.evidence if e['population']=='rule_1')['data']['inconclusive']==1


def test_explicit_associations_dedup_and_orphans(tmp_path):
    s=table_spec(tmp_path,[{'id':'a','value':1},{'id':'b','value':2}],[{'id':'x','value':1},{'id':'y','value':2}])
    p=tmp_path/'links.jsonl';p.write_text('\n'.join(json.dumps(x) for x in [{'left_id':'a','right_id':'x'},{'left_id':'a','right_id':'x'},{'left_id':'b','right_id':'y'},{'left_id':'missing','right_id':'x'}]))
    s=replace(s,inputs=(*s.inputs,CrossRepresentationInputSpec('links',str(p),format='jsonl')),relationships=(replace(s.relationships[0],cardinality='many_to_many',association_source='links'),))
    r=core(s);assert next(e for e in r.evidence if e['family']=='relationships')['data']['associations']==2
    assert next(e for e in r.evidence if e['family']=='relationships')['data']['duplicate_association_rows']==1 and next(e for e in r.evidence if e['family']=='relationships')['data']['invalid_association_rows']==1


def test_json_decimal_lexemes_and_large_numeric_keys(tmp_path):
    s=table_spec(tmp_path,[{'id':'a','value':0}],[{'id':'a','value':0}])
    (tmp_path/'left.jsonl').write_text('{"id":"a","value":1.00000000000000000001}\n')
    (tmp_path/'right.jsonl').write_text('{"id":"a","value":1.00000000000000000002}\n')
    r=core(s);assert next(e for e in r.evidence if e['population']=='rule_1')['data']['violated']==1
    assert key({'id':'100000000000000000000000000000001'},('id',),'numeric')!=key({'id':'100000000000000000000000000000002'},('id',),'numeric')


def test_numeric_normalization_collision_not_merge(tmp_path):
    rel=RelationshipSpec('rel','left','right',key_representation='numeric',cardinality='many_to_one')
    r=core(table_spec(tmp_path,[{'id':'001','value':1},{'id':'1','value':1}],[{'id':'1','value':1}],rel))
    assert next(e for e in r.evidence if e['family']=='relationships')['data']['normalization_collisions']==1 and next(e for e in r.evidence if e['family']=='relationships')['data']['associations']==0


def test_context_mismatch_asof_and_authority(tmp_path):
    s=financial(tmp_path,count=3)
    r=core(replace(s,rules=(replace(s.rules[0],authority_role='not_present'),)))
    assert next(e for e in r.evidence if e['population']=='rule_1')['data']['inconclusive']==3
    r=core(replace(s,relationships=(replace(s.relationships[0],version_mode='latest_as_of'),)))
    # Equal publication clocks cannot choose a winner for the conflicting entity.
    assert any('ambiguous_as_of_tie' in d['reasons'] for d in next(e for e in r.evidence if e['population']=='rule_1')['data']['details'])


def test_separation_and_bounded_ancestry(tmp_path):
    sep=CrossSeparationSpec('separate','left','right')
    r=core(table_spec(tmp_path,[{'id':'a','value':1}],[{'id':'a','value':1}],separation=(sep,)))
    assert r.evidence[-1]['data']['left_affected_records']==1 and r.evidence[-1]['data']['violated']==1
    with pytest.raises(ValueError): CrossSeparationSpec('x','a','b',left_path=('r',)*4)


def test_discovery_budget_and_required_admission(tmp_path):
    s=financial(tmp_path,count=3)
    cfg=CrossRepresentationAnalysisConfig(limits=CrossWorkLimits(discovery_visits=1))
    r=core(s,cfg);assert next(e for e in r.evidence if e['population']=='rule_1')['data']['inconclusive']==3
    cfg=CrossRepresentationAnalysisConfig(limits=CrossWorkLimits(documents=1))
    with pytest.raises(AnalysisError): core(s,cfg)


def test_declared_two_hop_ancestry_deduplicates_endpoints(tmp_path):
    populations={'left':[{'id':'l1','mid':'m1'},{'id':'l2','mid':'m1'},{'id':'l3','mid':'m3'}],
        'right':[{'id':'q1','mid':'m2'},{'id':'q2','mid':'m2'},{'id':'q3','mid':'m3'}],
        'middle':[{'id':'m1','parent':'p1'},{'id':'m2','parent':'p1'},{'id':'m3','parent':'p2'}],
        'parents':[{'id':'p1'},{'id':'p2'}]}
    inputs=[]
    for name,rows in populations.items():
        path=tmp_path/(name+'.jsonl');path.write_text('\n'.join(json.dumps(x) for x in rows)+'\n')
        inputs.append(CrossRepresentationInputSpec(name,str(path),format='jsonl'))
    relationships=(RelationshipSpec('lm','left','middle',left_keys=('mid',),cardinality='many_to_one',meaning='derivation'),RelationshipSpec('rm','right','middle',left_keys=('mid',),cardinality='many_to_one',meaning='derivation'),RelationshipSpec('mp','middle','parents',left_keys=('parent',),cardinality='many_to_one',meaning='derivation'))
    separation=CrossSeparationSpec('ancestor','left','right',mode='ancestry',left_path=('lm','mp'),right_path=('rm','mp'))
    spec=CrossRepresentationAuditSpec(tuple(inputs),relationships=relationships,separation=(separation,),allowed_roots=(str(tmp_path),))
    result=core(spec);e=next(x['data'] for x in result.evidence if x['family']=='separation')
    assert e['shared_units']==2 and e['left_affected_records']==3 and e['right_affected_records']==3
    assert e['populations']==[3,3] and e['unqualified_records']==[0,0]
    assert e['status']=='violated'
    permitted=core(replace(spec,separation=(replace(separation,required=False),)))
    assert permitted.evidence[-1]['data']['violated']==0 and permitted.evidence[-1]['data']['shared_units']==2


def test_docx_revision_merged_and_bomb_coverage(tmp_path):
    from docx import Document
    from docx.oxml import OxmlElement
    doc=Document();p=doc.add_paragraph('SECRET revision');ins=OxmlElement('w:ins');p._p.append(ins)
    table=doc.add_table(rows=2,cols=2);table.cell(0,0).merge(table.cell(0,1));f=io.BytesIO();doc.save(f)
    units=list(extract(f.getvalue(),'docx',CrossWorkLimits()))
    assert any(u['kind']=='unsupported' for u in units) and any(u['kind']=='table' and not u['complete'] for u in units)
    with pytest.raises(AnalysisError): list(extract(f.getvalue(),'docx',CrossWorkLimits(expanded_docx_bytes=10)))


def test_missing_and_symlink_evidence(tmp_path):
    s=financial(tmp_path,count=3);(tmp_path/'A001-0.pdf').unlink();r=core(s)
    assert next(e for e in r.evidence if e['population']=='rule_1')['data']['inconclusive']==1
    (tmp_path/'A001-0.pdf').symlink_to(tmp_path/'A002-0.pdf')
    with pytest.raises(AnalysisError): core(s)


def test_parquet_scalar_decimal_and_txt(tmp_path):
    import pyarrow as pa
    import pyarrow.parquet as pq
    from decimal import Decimal
    p=tmp_path/'records.parquet';pq.write_table(pa.table({'id':['a'],'value':pa.array([Decimal('1.01')],type=pa.decimal128(8,2))}),p)
    t=tmp_path/'evidence.txt';t.write_text('Amount: 1.01\n')
    s=CrossRepresentationAuditSpec((CrossRepresentationInputSpec('records',str(p),format='parquet'),CrossRepresentationInputSpec('txt',str(t),kind='text',format='txt',metadata={'id':'a'})),relationships=(RelationshipSpec('rel','records','txt'),),mappings=(DocumentMappingSpec('amount',labels=('Amount',),pattern=r'\s*:\s*(?P<value>[^\n]+)'),),rules=(ReconciliationRule('r','rel','value',mapping='amount'),),allowed_roots=(str(tmp_path),))
    r=core(s);assert next(e for e in r.evidence if e['population']=='rule_1')['data']['satisfied']==1
