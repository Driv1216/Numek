from dataclasses import replace
import json
from pathlib import Path
import pytest
from datatrust import *
from datatrust.text import _execute
from datatrust.text_search import signature,candidate_pairs,shingles,shipping_profile,fingerprints
from datatrust.text_models import make_windows,evenly_spaced


def test_search_profile_calibration_binding():
    profile=shipping_profile();ledger=json.loads(Path('validation/m6/results/calibration.json').read_text())
    assert profile==ledger['profile']
    winner=next(x for x in ledger['grid'] if all(x[k]==profile[k] for k in ('bands','rows','bucket_cap')))
    assert winner['eligible'] and all(x['budgeted_recall']>=.99 for x in winner['scopes'])
    assert ledger['saturation']['observed_recall']<.1


def test_lsh_false_candidates_require_exact_verification():
    # Equal signatures can intentionally collide; only source shingle sets establish equality.
    candidates,coverage=candidate_pairs([(1,)*140]*20,20,7,10,15)
    assert len(candidates)<=15 and coverage['omitted_bucket_emissions']>0
    assert signature(shingles('original long enough text'),20,7)==signature(shingles('original long enough text'),20,7)


def test_budgeted_units_and_full_population_are_distinct(tmp_path):
    p=tmp_path/'data.jsonl';p.write_text('\n'.join(json.dumps({'text':f'item {i} language evidence and a unique ending {i}'}) for i in range(12)))
    spec=TextAuditSpec((TextInputSpec('s',TextSourceSpec(str(p)),(TextFieldSpec('text','text'),)),))
    config=TextAnalysisConfig(limits=replace(TextWorkLimits(),lexical_units=3,signature_work=1000,verification_visits=100),passages=False)
    r=_execute(spec,config)
    assert next(x for x in r.evidence if x['family']=='corpus')['data']['content_units']==12
    assert r.coverage['families']['lexical_selection']['selected_population']==3
    assert r.coverage['families']['near_duplicates']['global_absence_claim'] is False
    with pytest.raises(AnalysisError):_execute(spec,replace(config,lexical_complete=True))


def test_passage_winnowing_preserves_original_span(tmp_path):
    common='A shared source-aligned passage with enough graphemes to inspect carefully.'
    p=tmp_path/'data.jsonl';p.write_text('\n'.join(json.dumps({'text':t}) for t in ['left '+common+' first','unrelated '+common+' last']))
    spec=TextAuditSpec((TextInputSpec('s',TextSourceSpec(str(p)),(TextFieldSpec('text','text'),)),),allowed_roots=(str(tmp_path),))
    r=_execute(spec,TextAnalysisConfig(near_duplicates=False))
    passages=next(x for x in r.evidence if x['family']=='passages')['data']
    assert passages['verified_passage_matches']>0
    match=passages['details'][0]['matches'][0]
    resolved=r.resolve_evidence(match['reference'],allowed_roots=(tmp_path,),reveal_content=True)
    assert len(resolved['excerpt'])>=50 and 'shared' in resolved['excerpt']


class CharacterTokenizer:
    def __call__(self,text,add_special_tokens=True,truncation=False,return_offsets_mapping=False,**kwargs):
        assert truncation is False
        result={'input_ids':[ord(x) for x in text]+([0,0] if add_special_tokens else [])}
        if return_offsets_mapping:result['offset_mapping']=[(i,i+1) for i in range(len(text))]
        return result


def test_windows_tail_unicode_no_prefix_truncation():
    text='a😀e\u0301 '+('long content '*160)+'TAIL'
    windows,n,issues=make_windows(text,CharacterTokenizer())
    assert n==len(text) and not issues and windows[0]['start']==0 and windows[-1]['end']==len(text)
    assert all(w['text']==text[w['start']:w['end']] for w in windows)
    assert all(len('query: '+w['text'])+2<=512 for w in windows)
    assert windows[-1]['text'].endswith('TAIL')
    assert evenly_spaced(100,3)==[0,50,99]
    excluded,n,issues=make_windows(text,CharacterTokenizer(),method='exclude_long')
    assert excluded==[] and issues['excluded_long']==1


def test_indivisible_grapheme_exclusion_not_truncation():
    text='e'+'\u0301'*600
    windows,n,issues=make_windows(text,CharacterTokenizer())
    assert windows==[] and issues


def test_offline_language_adapter(tmp_path,monkeypatch):
    # Deny Python network calls while the actual optional detector runs.
    import socket
    monkeypatch.setattr(socket,'create_connection',lambda *args,**kwargs:(_ for _ in ()).throw(AssertionError('network prohibited')))
    p=tmp_path/'data.jsonl';p.write_text(json.dumps({'text':'This is a complete English sentence about source integrity and useful local evidence.'}))
    spec=TextAuditSpec((TextInputSpec('s',TextSourceSpec(str(p)),(TextFieldSpec('text','text'),)),))
    r=_execute(spec,TextAnalysisConfig(near_duplicates=False,passages=False,models=TextModelOptions(language=True,languages=('ENGLISH','HINDI'))))
    assert next(x for x in r.evidence if x['family']=='language')['data']['predicted_unit_counts']['ENGLISH']==1


def test_actual_pinned_offline_embeddings(tmp_path,monkeypatch):
    root=Path('validation/m6/models/multilingual-e5-small')
    if not (root/'datatrust-model.json').exists():pytest.skip('Pinned development model not downloaded yet.')
    import socket
    monkeypatch.setattr(socket,'create_connection',lambda *args,**kwargs:(_ for _ in ()).throw(AssertionError('network prohibited')))
    text=('The dataset preserves original text and source-aligned annotations. '*130)+'A unique closing sentence at the tail.'
    p=tmp_path/'data.jsonl';p.write_text('\n'.join(json.dumps({'text':t}) for t in [text,'Original source text is retained with annotations.']))
    spec=TextAuditSpec((TextInputSpec('s',TextSourceSpec(str(p)),(TextFieldSpec('text','text'),)),))
    r=_execute(spec,TextAnalysisConfig(near_duplicates=False,passages=False,models=TextModelOptions(embedding_directory=str(root.resolve()),tokenizer=True)))
    model=next(x for x in r.evidence if x['family']=='semantic_similarity')
    assert model['data']['neighbors'] and model['data']['parent_coverage'][0]['embedded_windows']>1
    assert model['data']['model']['revision']==TextModelOptions().embedding_revision
    assert all(x['window']['model_tokens']<=512 for x in model['data']['neighbors'])
    long_parent=next(x for x in model['data']['parent_coverage'] if x['source_characters']==len(text))
    assert long_parent['complete_source_coverage']
    artifacts=r.generate_artifacts(tmp_path/'model.html')
    assert root.as_posix() not in Path(artifacts.html_path).read_text()

