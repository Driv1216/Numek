"""Consequential semantic and lifecycle controls added at M6 closure."""
from dataclasses import replace
import json
from pathlib import Path
import pytest
from datatrust import *
from datatrust.text import _execute
from datatrust.text_search import candidate_pairs
from datatrust.text_models import AccountedTokenizer,TokenizerBudget
from tests.m6.test_search_models import CharacterTokenizer


def audit(tmp_path,rows,**kwargs):
    path=tmp_path/'input.jsonl';path.write_text('\n'.join(json.dumps(x,ensure_ascii=True) for x in rows))
    item=TextInputSpec('s',TextSourceSpec(str(path)),(TextFieldSpec('text','text'),),**kwargs)
    return _execute(TextAuditSpec((item,)),TextAnalysisConfig(near_duplicates=False,passages=False))


def test_relative_roots_bind_to_spec_directory(tmp_path):
    d={'inputs':[{'id':'s','source':{'path':'input.jsonl'},'fields':[{'name':'text','selector':'text'}]}],'allowed_roots':['.']}
    s=TextAuditSpec.from_dict(d,base_directory=tmp_path)
    assert s.allowed_roots==(str(tmp_path.resolve()),) and Path(s.inputs[0].source.path).parent==tmp_path


def test_supplied_tokens_survive_missing_labels(tmp_path):
    r=audit(tmp_path,[{'text':'one two','tokens':['one','two']}],annotations=(TextAnnotationSpec('text','labels',kind='token',tokens_selector='tokens'),))
    a=next(x['data'] for x in r.evidence if x['family']=='annotations')
    assert a['supplied_tokens']==2 and a['states'][0]['observation']=='absent'


def test_invalid_span_neighbor_and_surrogate_metadata(tmp_path):
    r=audit(tmp_path,[{'text':'abc','status':'\ud800','spans':[{'start':0,'end':1,'label':'entity'},{'start':8,'end':9}]}],annotations=(TextAnnotationSpec('text','spans',kind='span',status_selector='status'),))
    a=next(x['data'] for x in r.evidence if x['family']=='annotations')
    assert a['item_states']=={'valid':1,'invalid':1} and a['metadata_states']=={'invalid':1}


def test_flat_missing_identity_never_merges_messages(tmp_path):
    r=audit(tmp_path,[{'text':'a','role':'user','content':'a','order':0},{'text':'b','role':'assistant','content':'b','order':0}],conversation=TextConversationSpec(messages_selector=None,conversation_selector='conv',order_selector='order'))
    c=next(x['data'] for x in r.evidence if x['family']=='conversations')
    assert c['messages']==2 and c['conversations']==0 and not c['violations']


def test_prioritized_candidates_reserve_comparison_sides():
    pairs,coverage=candidate_pairs([(1,)*140]*20,20,7,5,3,pair_groups=[({0,1},{18,19})])
    assert pairs and all(a in {0,1} and b in {18,19} for a,b in pairs)
    assert coverage['unique_unseen_pairs']=='unknown'


def test_tokenizer_repair_calls_are_charged():
    tokenizer=AccountedTokenizer(CharacterTokenizer(),replace(TextWorkLimits(),tokenizer_bytes=10,tokenizer_tokens=10))
    tokenizer('abcd',add_special_tokens=False);tokenizer('abcd',add_special_tokens=False)
    with pytest.raises(TokenizerBudget):tokenizer('abcd')
    assert tokenizer.bytes==8 and tokenizer.tokens==8


def test_strict_scalar_arrays():
    for cls,value in [(TextConversationSpec,{'roles':'user'}),(TextModelOptions,{'languages':'ENGLISH'}),(TextRetrievalSpec,{'positive_grades':'1'}),(TextEvaluationSpec,{'comparisons':['ab']})]:
        with pytest.raises(ValueError):cls.from_dict(value)


def test_judgment_null_conflict_and_ambiguity(tmp_path):
    def source(name,rows):
        p=tmp_path/(name+'.jsonl');p.write_text('\n'.join(json.dumps(x) for x in rows));return TextSourceSpec(str(p))
    docs=TextInputSpec('docs',source('docs',[{'id':'d','text':'abc'},{'id':'a','text':'first'},{'id':'a','text':'second'}]),(TextFieldSpec('text','text'),),id_selector='id',retrieval=TextRetrievalSpec('document'))
    qs=TextInputSpec('qs',source('qs',[{'id':'q','text':'query'}]),(TextFieldSpec('text','text',kind='query'),),id_selector='id',retrieval=TextRetrievalSpec('query'))
    js=TextInputSpec('js',source('js',[{'query_id':'q','document_id':'d','relevance':v} for v in [None,0,1]]+[{'query_id':'q','document_id':'a','relevance':1}]),retrieval=TextRetrievalSpec('judgment',query_source='qs',target_source='docs'))
    r=_execute(TextAuditSpec((docs,qs,js)),TextAnalysisConfig(near_duplicates=False,passages=False))
    d=next(x['data'] for x in r.evidence if x['family']=='retrieval')
    assert d['judgment_states']['unknown']==1 and d['violations']['conflicting_judgments']==1 and d['violations']['ambiguous_target']==1


def test_resource_failure_has_no_completed_result(tmp_path):
    p=tmp_path/'data.jsonl';p.write_text(json.dumps({'text':'safe'}));spec=TextAuditSpec((TextInputSpec('s',TextSourceSpec(str(p)),(TextFieldSpec('text','text'),)),))
    for execution,code in [(replace(ExecutionOptions(),max_rss_bytes=1024),'rss_limit'),(replace(ExecutionOptions(),max_seconds=.001),'deadline')]:
        with pytest.raises(AnalysisError) as error:DataTrust.audit_text(spec,TextAnalysisConfig(execution=execution))
        assert error.value.code==code and not error.value.execution['completed_result_published']


def test_version_alignment_retains_changes_unmatched_and_ambiguity(tmp_path):
    def item(sid,rows):
        p=tmp_path/(sid+'.jsonl');p.write_text('\n'.join(json.dumps(x) for x in rows));return TextInputSpec(sid,TextSourceSpec(str(p)),(TextFieldSpec('text','text'),),namespace='version',id_selector='id')
    left=item('left',[{'id':'same','text':'before'},{'id':'removed','text':'old'},{'id':'ambiguous','text':'a'},{'id':'ambiguous','text':'b'}])
    right=item('right',[{'id':'same','text':'after'},{'id':'added','text':'new'},{'id':'ambiguous','text':'c'}])
    r=_execute(TextAuditSpec((left,right),TextEvaluationSpec((('left','right'),))),TextAnalysisConfig(near_duplicates=False,passages=False))
    a=next(x['data'] for x in r.evidence if x['family']=='version_alignment')
    assert a['aligned_fields_changed_raw']==1 and a['unique_lexical_id_matches']==1
    assert a['unmatched_unique_identities']==[1,2] and a['ambiguous_identity_groups']==[1,0]
