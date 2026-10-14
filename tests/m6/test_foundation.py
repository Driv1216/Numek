from dataclasses import replace
import json
from pathlib import Path
import pytest
from datatrust import *
from datatrust.text import _execute
from datatrust.text_normalization import frames,span_bounds,state,MISSING,strict_json


def spec_for(path,**kwargs):
    return TextAuditSpec((TextInputSpec('data',TextSourceSpec(str(path),format='csv' if path.suffix=='.csv' else 'jsonl'),(TextFieldSpec('text','text'),),**kwargs),),allowed_roots=(str(path.parent),))


def cfg(**kwargs):
    return TextAnalysisConfig(near_duplicates=False,passages=False,**kwargs)


def audit(path,records,**kwargs):
    path.write_text('\n'.join(json.dumps(x,ensure_ascii=False) for x in records))
    return _execute(spec_for(path,**kwargs),cfg())


def test_contract_roundtrip_and_strict_unknown(tmp_path):
    spec=spec_for(tmp_path/'a.jsonl')
    assert TextAuditSpec.from_dict(spec.to_dict())==spec
    with pytest.raises(ValueError):TextAnalysisConfig.from_dict({'bogus':1})
    with pytest.raises(ValueError):TextAuditSpec((spec.inputs[0],spec.inputs[0]))
    with pytest.raises(ValueError):TextSourceSpec('a','jsonl',encoding='utf-16')
    with pytest.raises(ValueError):TextAnnotationSpec('x','x',offset_unit='guess')


@pytest.mark.parametrize('unit,start,end,expected',[('codepoint',1,3,(1,3)),('utf8',1,5,(1,2)),('utf16',1,3,(1,2))])
def test_original_offset_units(unit,start,end,expected):
    assert span_bounds('a😀e\u0301',start,end,unit)==expected


@pytest.mark.parametrize('unit,start,end',[('utf8',2,5),('utf16',2,3),('codepoint',True,2),('codepoint',3,2)])
def test_invalid_boundaries(unit,start,end):
    with pytest.raises(ValueError):span_bounds('a😀e\u0301',start,end,unit)


def test_states_preserve_na_and_surrogates():
    assert [state(x) for x in [MISSING,None,'',' ','NA',8,'\ud800']]==['absent','null','empty','whitespace','present','invalid','invalid']
    for value in ['{"a":1,"a":2}','{"a":NaN}']:
        with pytest.raises(ValueError):strict_json(value)


def test_jsonl_invalid_records_and_separator_accounting(tmp_path):
    p=tmp_path/'a.jsonl';p.write_bytes(b'{"text":"valid"}\n\n{"text":NaN}\n\xff\n[]\n{"text":"last"}\n')
    result=_execute(spec_for(p),cfg())
    assert result.profile['source_populations']['source_1']=={'records':5,'valid_records':2,'invalid_records':3,'separators':1}
    assert result.evidence[0]['data']['invalid_items']==3
    assert '"valid"' not in result.json_text() # corpus values must stay private


def test_csv_broken_framing_is_fatal(tmp_path):
    p=tmp_path/'a.csv';p.write_text('text,id\nhello\n')
    with pytest.raises(AnalysisError,match='width'):_execute(spec_for(p),cfg())
    p.write_text('text\n"unfinished\n')
    with pytest.raises(AnalysisError,match='framing'):_execute(spec_for(p),cfg())


def test_csv_json_cell_invalid_siblings(tmp_path):
    p=tmp_path/'a.csv';p.write_text('text,labels\nhello,invalid-json\n')
    source=TextSourceSpec(str(p),'csv',json_columns=('labels',))
    spec=TextAuditSpec((TextInputSpec('d',source,(TextFieldSpec('text','text'),),annotations=(TextAnnotationSpec('text','labels',kind='multilabel'),)),))
    result=_execute(spec,cfg())
    assert next(r for r in result.evidence if r['family']=='corpus')['data']['content_units']==1
    assert next(r for r in result.evidence if r['family']=='invalidity')['data']['invalid_items']==2


def test_annotation_partial_and_valid_no_entity(tmp_path):
    r=audit(tmp_path/'a.jsonl',[{'text':'😀a','spans':[{'start':0,'end':2,'text':'😀'},{'start':True,'end':3}]},{'text':'ok','spans':[]}],annotations=(TextAnnotationSpec('text','spans',kind='span',offset_unit='utf16'),))
    evidence=next(x for x in r.evidence if x['family']=='annotations')['data']['states']
    assert {x['observation'] for x in evidence}=={'invalid','observed'}


def test_all_invalid_dataset_completed_integrity(tmp_path):
    p=tmp_path/'a.jsonl';p.write_text('[]\ninvalid\n')
    r=_execute(spec_for(p),cfg())
    assert r.execution['status']=='completed'
    assert next(x for x in r.evidence if x['family']=='corpus')['data']['content_units']==0


def test_exact_normalized_duplicates_are_separate(tmp_path):
    r=audit(tmp_path/'a.jsonl',[{'text':'é'},{'text':'e\u0301'}])
    duplicate=[x for x in r.evidence if x['family']=='exact_duplicates']
    assert len(duplicate)==1 and duplicate[0]['data']['representation']=='nfc'


def test_token_tags_and_missing_expectation(tmp_path):
    r=audit(tmp_path/'a.jsonl',[{'text':'hello world','tokens':['hello','world'],'tags':['I-X','O']},{'text':'plain'}],annotations=(TextAnnotationSpec('text','tags',kind='token',tokens_selector='tokens',scheme='BIO',expectation='required'),))
    reasons=next(x for x in r.evidence if x['family']=='invalidity')['data']['reasons']
    assert reasons['invalid_tag_sequence']==1 and reasons['required_annotation_missing']==1


def test_conversation_parallel_tools_allowed(tmp_path):
    r=audit(tmp_path/'a.jsonl',[{'messages':[{'role':'assistant','content':None,'tool_calls':[{'id':'1','function':{'name':'f','arguments':'{}'}},{'id':'2','function':{'name':'g','arguments':{}}}]},{'role':'tool','content':'a','tool_call_id':'2'},{'role':'tool','content':'b','tool_call_id':'1'}]}],conversation=TextConversationSpec(require_tool_closure=True))
    assert next(x for x in r.evidence if x['family']=='conversations')['data']['violations'].get('orphan_or_ambiguous_tool_response',0)==0


def test_private_manifest_resolution_integrity(tmp_path):
    p=tmp_path/'a.jsonl';r=audit(p,[{'text':'SECRET_MARKER'},{'text':'SECRET_MARKER'}])
    ref=next(x for x in r.evidence if x['family']=='exact_duplicates')['references'][0]
    assert r.resolve_evidence(ref,allowed_roots=(tmp_path,),reveal_content=True)['excerpt']=='SECRET_MARKER'
    assert 'SECRET_MARKER' not in r.json_text() and str(tmp_path) not in r.json_text()
    with pytest.raises(ValueError):r.resolve_evidence(ref,allowed_roots=())
    p.write_text('{"text":"changed"}\n')
    with pytest.raises(AnalysisError):r.resolve_evidence(ref,allowed_roots=(tmp_path,),reveal_content=True)


def test_hard_expansion_not_silent_exclusion(tmp_path):
    p=tmp_path/'a.jsonl';p.write_text(json.dumps({'text':'ok','items':list(range(20))}))
    limits=replace(TextWorkLimits(),max_nested_items=10)
    with pytest.raises(AnalysisError):_execute(spec_for(p),replace(cfg(),limits=limits))
