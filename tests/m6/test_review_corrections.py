"""Focused independent controls for the M6 source-review correction pass."""
from dataclasses import replace
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from datatrust import (
    AnalysisError, TextAuditSpec, TextInputSpec, TextSourceSpec, TextFieldSpec,
    TextAnalysisConfig, TextWorkLimits, TextEvaluationSpec, TextConversationSpec,
    TextModelOptions,
)
from datatrust.text import _execute
from datatrust.text_models import allocate_windows
from datatrust.text_presentation import executive_summary, report_view


def item(tmp_path,sid,rows,**options):
    path=tmp_path/(sid+'.jsonl')
    path.write_text('\n'.join(json.dumps(x) for x in rows))
    return TextInputSpec(sid,TextSourceSpec(str(path)),(TextFieldSpec('text','text'),),**options)


def config(**changes):
    return TextAnalysisConfig(near_duplicates=False,passages=False,**changes)


def test_selection_reserves_pairs_round_robins_comparisons_and_is_reproducible(tmp_path,monkeypatch):
    from datatrust import text_search
    original=text_search.select_population;trace=[]
    def capture(e,store,*args,**kwargs):
        ledger=original(e,store,*args,**kwargs)
        trace.append(store.con.execute('SELECT uid,sid FROM lexical_selected ORDER BY selection_order').fetchall())
        return ledger
    monkeypatch.setattr(text_search,'select_population',capture)
    sources=[item(tmp_path,sid,[{'text':f'{sid} {n}'} for n in range(20)],role=role)
             for sid,role in [('eval1','evaluation'),('train1','train'),('eval2','test'),('train2','train'),('unrelated','corpus')]]
    spec=TextAuditSpec(tuple(sources),TextEvaluationSpec((('eval1','train1'),('eval2','train2'))))
    cfg=config(limits=replace(TextWorkLimits(),lexical_units=4))
    first=_execute(spec,cfg);_execute(spec,cfg)
    assert trace[0]==trace[1] and {s for _,s in trace[0]}=={'eval1','train1','eval2','train2'}
    ledger=first.coverage['families']['lexical_selection']
    explicit=[x for x in ledger['comparison_allocations'] if x['tier']==0]
    assert len(explicit)==2 and all(x['selected_side_populations']==[1,1] for x in explicit)
    assert ledger['allocation_tier_units']=={'0':4,'1':0,'2':0,'3':0}


def test_split_and_field_strata_receive_round_robin_units(tmp_path):
    source=item(tmp_path,'data',[{'text':f'a {i}','other':f'b {i}','split':s} for s in ['train','evaluation'] for i in range(12)],split_selector='split')
    source=replace(source,fields=source.fields+(TextFieldSpec('other','other'),))
    result=_execute(TextAuditSpec((source,)),config(limits=replace(TextWorkLimits(),lexical_units=4)))
    strata=result.coverage['families']['lexical_selection']['selected_strata']
    assert len(strata)==4 and all(x['units']==1 for x in strata)
    assert len({x['split'] for x in strata})==2 and len({x['field'] for x in strata})==2


def test_disk_queue_batch_boundary_and_seeded_membership(tmp_path,monkeypatch):
    from datatrust import text_search
    original=text_search.select_population;trace=[]
    def capture(e,store,*args,**kwargs):
        ledger=original(e,store,*args,**kwargs)
        trace.append(store.con.execute('SELECT uid FROM lexical_selected ORDER BY selection_order').fetchall())
        return ledger
    monkeypatch.setattr(text_search,'select_population',capture)
    sources=(item(tmp_path,'s',[{'text':f'record {i}','split':str(i%4)} for i in range(640)],split_selector='split'),)
    spec=TextAuditSpec(sources);limits=replace(TextWorkLimits(),lexical_units=257)
    r=_execute(spec,config(limits=limits));_execute(spec,config(limits=limits,seed=17))
    assert len(trace[0])==len(set(trace[0]))==257 and trace[0]!=trace[1]
    assert sorted(x['units'] for x in r.coverage['families']['lexical_selection']['selected_strata'])==[64,64,64,65]


def test_implicit_evaluation_comparison_precedes_other_requested_comparisons(tmp_path):
    sources=tuple(item(tmp_path,sid,[{'text':sid}],role=role) for sid,role in [('e','evaluation'),('t','train'),('t2','train'),('v1','version'),('v2','version')])
    spec=TextAuditSpec(sources,TextEvaluationSpec((('e','t'),('v1','v2'))))
    r=_execute(spec,config(limits=replace(TextWorkLimits(),lexical_units=3)))
    allocation=r.coverage['families']['lexical_selection']
    assert allocation['allocation_tier_units']=={'0':2,'1':1,'2':0,'3':0}
    assert next(x for x in allocation['comparison_allocations'] if x['tier']==1)['selected_side_populations']==[1,1]


@pytest.mark.parametrize('budget,status',[ (1,'budget_insufficient_for_both_sides'),(2,'both_sides_represented') ])
def test_tiny_budget_never_claims_unrepresented_comparison_side(tmp_path,budget,status):
    sources=(item(tmp_path,'e',[{'text':'evaluation'}],role='evaluation'),item(tmp_path,'t',[{'text':'training'}],role='train'))
    r=_execute(TextAuditSpec(sources,TextEvaluationSpec((('e','t'),))),config(limits=replace(TextWorkLimits(),lexical_units=budget)))
    allocation=r.coverage['families']['lexical_selection']['comparison_allocations'][0]
    assert allocation['status']==status
    assert all(allocation['selected_side_populations'])==(budget==2)


def test_unavailable_comparison_side_is_not_fabricated(tmp_path):
    sources=(item(tmp_path,'e',[{'text':None}],role='evaluation'),item(tmp_path,'t',[{'text':'training'}],role='train'))
    r=_execute(TextAuditSpec(sources,TextEvaluationSpec((('e','t'),))),config())
    allocation=r.coverage['families']['lexical_selection']['comparison_allocations'][0]
    assert allocation['status']=='unavailable_side' and allocation['eligible_side_populations']==[0,1]


def test_window_allocation_prioritizes_last_before_interiors_and_qualifies_shortfall():
    assert allocate_windows([9,9],4,16)==[[0,8],[0,8]]
    assert allocate_windows([9,9],3,16)==[[0,8],[0]]
    assert allocate_windows([9,9],2,16)==[[0],[0]]
    assert allocate_windows([9],16,3)==[[0,8,4]]
    assert allocate_windows([0,1,9],3,1)==[[],[0],[0]]


def test_conversation_witnesses_do_not_inherit_prior_violations(tmp_path):
    rows=[{'text':'present','conv':name,'role':role,'turn':0} for name,role in [('a_bad','user'),('b_clean','assistant'),('c_bad','user'),('d_clean','assistant')]]
    declaration=TextConversationSpec(messages_selector=None,conversation_selector='conv',order_selector='turn',content_selector='text',require_completion=True)
    r=_execute(TextAuditSpec((item(tmp_path,'c',rows,conversation=declaration),)),config())
    evidence=next(x for x in r.evidence if x['family']=='conversations')
    assert evidence['data']['violations']=={'missing_completion':2}
    assert {r.private['locators'][ref]['ordinal'] for ref in evidence['references']}=={1,3}


def test_duplicate_actions_are_consolidated_without_summing_evidence(tmp_path):
    r=_execute(TextAuditSpec((item(tmp_path,'c',[{'text':x} for x in ['é','é','e\u0301']]),)),config())
    technical=[x for x in r.evidence if x['family']=='exact_duplicates']
    assert {x['data']['representation'] for x in technical}=={'raw','nfc'}
    summary=executive_summary(r.to_dict());actions=[x for x in summary['actions'] if x['family']=='exact_duplicates']
    assert len(actions)==1 and len(actions[0]['evidence_ids'])==2
    assert summary['technical_findings']==2 and r.profile['executive_action_count']==1
    assert not summary['duplicate_counts_are_additive']


def test_existing_completed_evidence_can_be_synthesized_without_reanalysis():
    value=json.loads(Path('validation/m6/results/reports/5945ed6ff28c4c66bde2c032ae3228a0/controls.json').read_text())
    before=json.dumps(value,sort_keys=True)
    view=report_view(SimpleNamespace(to_dict=lambda:value))
    assert len(view['sections'])==8 and len(view['executive']['actions'])==2
    assert view['executive']['framed_records']==10 and view['executive']['invalid_records']==2
    assert json.dumps(value,sort_keys=True)==before


def test_unexpected_optional_fault_publishes_no_partial_result_and_cleans_workspace(tmp_path,monkeypatch):
    from datatrust import text_search
    original=text_search.investigate
    def fault(e,store):
        e.add('near_duplicates',{'qualifying_pairs':99},violations=99,scope='bounded')
        store.con.execute('CREATE TABLE incomplete_index AS SELECT 1 value')
        raise RuntimeError('PRIVATE_NATIVE_PAYLOAD')
    monkeypatch.setattr(text_search,'investigate',fault)
    spec=TextAuditSpec((item(tmp_path,'s',[{'text':'preserved source'}]),))
    owned=[]
    with pytest.raises(AnalysisError) as error:
        _execute(spec,config(),progress=lambda p:owned.append(p['owned_workspace']) if 'owned_workspace' in p else None)
    assert error.value.code=='text_execution_failed' and 'PRIVATE_NATIVE_PAYLOAD' not in str(error.value)
    assert owned and all(not Path(p).exists() for p in owned)
    monkeypatch.setattr(text_search,'investigate',original)
    fresh=_execute(spec,config())
    assert fresh.execution['publication_policy']=='whole_audit_atomic_fail_closed'
    assert all(x['family']!='near_duplicates' for x in fresh.findings)


class CountingTokenizer:
    is_fast=True
    def __call__(self,text,**options):
        if options.get('return_offsets_mapping'):
            return {'input_ids':list(range(len(text))),'offset_mapping':[(i,i+1) for i in range(len(text))]}
        if options.get('return_tensors')=='pt':
            import torch
            n=len(text)+2
            return {'input_ids':torch.ones((1,n),dtype=torch.long),'attention_mask':torch.ones((1,n),dtype=torch.long)}
        return {'input_ids':list(range(5)) if not options.get('add_special_tokens',True) else list(range(len(text)+2))}


def stub_models(monkeypatch):
    transformers=pytest.importorskip('transformers');torch=pytest.importorskip('torch')
    from datatrust import text, text_models
    provenance={'files':{'tokenizer.json':{'sha256':'authored-test-tokenizer'}},'manifest':{}}
    monkeypatch.setattr(text,'preflight',lambda *args:({'embedding':provenance},[]))
    monkeypatch.setattr(text_models,'verify',lambda *args:None)
    monkeypatch.setattr(transformers.AutoTokenizer,'from_pretrained',lambda *args,**kw:CountingTokenizer())
    class Model:
        def to(self,*args):return self
        def eval(self):return self
        def __call__(self,**encoded):return SimpleNamespace(last_hidden_state=torch.ones((*encoded['input_ids'].shape,2)))
    monkeypatch.setattr(transformers.AutoModel,'from_pretrained',lambda *args,**kw:Model())


def test_tokenizer_vocabulary_charges_final_rejected_output_and_stops(tmp_path,monkeypatch):
    stub_models(monkeypatch)
    spec=TextAuditSpec((item(tmp_path,'s',[{'text':'a'},{'text':'b'},{'text':'c'}]),))
    r=_execute(spec,config(models=TextModelOptions(embedding_directory=str(tmp_path),tokenizer=True,embeddings=False),limits=replace(TextWorkLimits(),tokenizer_tokens=7)))
    ledger=r.coverage['families']['tokenizer_vocabulary']
    assert ledger['examined_units']==1 and ledger['attempted_units']==2
    assert ledger['tokenizer_tokens']==10 and ledger['accepted_token_occurrences']==5
    assert ledger['unattempted_units']==1 and ledger['stop_reason']=='emitted_token_work_budget'


def test_embeddings_expose_selected_sides_endpoint_shortfall_and_unprocessed_parents(tmp_path,monkeypatch):
    stub_models(monkeypatch)
    sources=(item(tmp_path,'eval',[{'text':'e'*1800} for _ in range(3)],role='evaluation'),item(tmp_path,'train',[{'text':'t'*1800} for _ in range(3)],role='train'))
    spec=TextAuditSpec(sources,TextEvaluationSpec((('eval','train'),)))
    r=_execute(spec,config(models=TextModelOptions(embedding_directory=str(tmp_path)),limits=replace(TextWorkLimits(),embedding_windows=2)))
    ledger=r.coverage['families']['semantic_similarity'];record=next(x for x in r.evidence if x['family']=='semantic_similarity')
    assert ledger['selected_population']==2 and ledger['eligible_parents']==6 and ledger['unprocessed_parents']==4
    assert ledger['comparison_allocations'][0]['selected_side_populations']==[1,1]
    assert ledger['partial_parents']==2 and ledger['first_only_long_parents']==2 and ledger['parents_with_first_and_last_windows']==0
    assert all(x['embedded_parents']==1 for x in ledger['parent_populations'])
    assert all(not x['complete_source_coverage'] and not x['first_and_last_eligible_windows_embedded'] for x in record['data']['parent_coverage'])
