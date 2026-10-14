"""Optional offline adapters. No downloads, remote code or implicit truncation."""
from collections import Counter
import hashlib
import importlib.metadata
import json
from pathlib import Path

from datatrust.text_normalization import graphemes, capture, verify

REVISION='fd1525a9fd15316a2d503bf26ab031a61d056e98'
RUNTIME={'torch':'2.8.0','transformers':'4.57.1','tokenizers':'0.22.1','safetensors':'0.6.2'}


class TokenizerBudget(Exception):
    pass


class AccountedTokenizer:
    """Charge every original/prefixed slice, including boundary repair attempts."""
    def __init__(self,tokenizer,limits):
        self.tokenizer=tokenizer;self.limits=limits;self.bytes=0;self.tokens=0
    def __call__(self,text,**options):
        size=len(text.encode())
        if self.bytes+size>self.limits.tokenizer_bytes:raise TokenizerBudget('source_input_byte_budget')
        self.bytes+=size
        result=self.tokenizer(text,**options);ids=result['input_ids']
        self.tokens+=int(ids.shape[-1]) if hasattr(ids,'shape') else len(ids)
        if self.tokens>self.limits.tokenizer_tokens:raise TokenizerBudget('emitted_token_work_budget')
        return result


def preflight(options):
    provenance={};protected=[]
    if options.language:
        if importlib.metadata.version('lingua-language-detector')!='2.1.1':raise ValueError('Install the pinned text-language extra.')
        from lingua import Language
        if any(not hasattr(Language,x) for x in options.languages):raise ValueError('Unsupported declared Lingua language.')
        dist=importlib.metadata.distribution('lingua-language-detector')
        files={str(p):capture(dist.locate_file(p)) for p in dist.files if str(p).endswith(('.so','.pyd','.bin'))}
        protected.extend(info['path'] for info in files.values())
        provenance['language']={'package':'lingua-language-detector','version':'2.1.1','files':files,'artifact_hashes':{n:info['sha256'] for n,info in files.items()},'languages':list(options.languages),'calibrated_confidence':False}
    if options.embedding_directory:
        root=Path(options.embedding_directory).resolve()
        for name,version in RUNTIME.items():
            if importlib.metadata.version(name)!=version:raise ValueError('Install the pinned text-embeddings extra.')
        from datatrust.text_normalization import strict_json
        manifest_identity=capture(root/'datatrust-model.json')
        manifest=strict_json((root/'datatrust-model.json').read_text());verify(manifest_identity)
        if manifest.get('revision')!=REVISION or manifest.get('model')!='intfloat/multilingual-e5-small':raise ValueError('Embedding manifest requires the pinned model revision.')
        files=manifest.get('files')
        required={'config.json','model.safetensors','tokenizer.json','tokenizer_config.json','special_tokens_map.json'}
        if not isinstance(files,dict) or not required<=set(files):raise ValueError('Embedding manifest lacks required pinned artifacts.')
        identities={}
        official=json.loads(Path(__file__).with_name('text_model_artifacts.json').read_text())
        for name,digest in files.items():
            path=root/name
            if path.is_symlink() or path.parent!=root or not path.is_file():raise ValueError('Embedding files must be ordinary direct children of the model directory.')
            identity=capture(path)
            if identity['sha256']!=digest:raise ValueError('Embedding artifact integrity mismatch.')
            declared=official['files'].get(name)
            if not declared:raise ValueError('Embedding artifact is outside the pinned publisher manifest.')
            raw=path.read_bytes() if declared['algorithm']!='sha256' else b''
            pinned=identity['sha256'] if declared['algorithm']=='sha256' else hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
            if pinned!=declared['digest']:raise ValueError('Model bytes do not match the pinned publisher revision.')
            identities[name]=identity;protected.append(str(path))
        config=strict_json((root/'config.json').read_text())
        if config.get('hidden_size')!=384 or config.get('max_position_embeddings')!=512 or config.get('model_type')!='bert':raise ValueError('Unsupported embedding architecture.')
        provenance['embedding']={'model':manifest['model'],'revision':REVISION,'files':identities,'manifest':manifest_identity,'runtime':RUNTIME,'device':'cpu','dtype':'float32','pooling':'attention_mask_mean_then_l2','maximum_tokens':512,'window_method':options.long_documents}
        protected.append(str(root/'datatrust-model.json'))
    return provenance,protected


def make_windows(text,tokenizer,*,prefix='query: ',method='token_windows_v1'):
    """Yield source-aligned windows; callers separately bound tokenization and model work."""
    encoded=tokenizer(text,add_special_tokens=False,truncation=False,return_offsets_mapping=True)
    offsets=encoded['offset_mapping'];count=len(encoded['input_ids'])
    if any(not 0<=a<=b<=len(text) for a,b in offsets) or any(offsets[i][0]>offsets[i+1][0] for i in range(len(offsets)-1)):
        return [],count,{'invalid_offsets':1}
    if not offsets:return [],count,{'no_tokens':1}
    if method=='exclude_long':
        whole=tokenizer(prefix+text,add_special_tokens=True,truncation=False)
        if len(whole['input_ids'])>512:return [],count,{'excluded_long':1}
        return [{'start':0,'end':len(text),'token_start':0,'token_end':count,'text':text}],count,{}
    import bisect
    boundaries=[0];n=0
    for g in graphemes(text):n+=len(g);boundaries.append(n)
    windows=[];issues=Counter();i=0
    while i<count:
        j=min(count,i+448);a=0 if i==0 else boundaries[max(0,bisect.bisect_right(boundaries,offsets[i][0])-1)]
        b=len(text) if j==count else boundaries[min(len(boundaries)-1,bisect.bisect_left(boundaries,offsets[j-1][1]))]
        while b>a and len(tokenizer(prefix+text[a:b],add_special_tokens=True,truncation=False)['input_ids'])>512:
            b=boundaries[max(0,bisect.bisect_left(boundaries,b)-1)]
        if b<=a:
            issues['indivisible_or_unalignable_span']+=1;i+=1;continue
        actual_j=j
        while actual_j>i and offsets[actual_j-1][1]>b:actual_j-=1
        if actual_j<=i:issues['alignment_unavailable']+=1;i+=1;continue
        windows.append({'start':a,'end':b,'token_start':i,'token_end':actual_j,'text':text[a:b]})
        if actual_j==count:break
        i=max(i+1,actual_j-64)
    return windows,count,dict(issues)


def evenly_spaced(n,limit):
    if n<=limit:return list(range(n))
    if limit==1:return [0]
    return list(dict.fromkeys(round(i*(n-1)/(limit-1)) for i in range(limit)))


def allocate_windows(counts,budget,per_parent):
    """First across parents, then last, then evenly spaced interiors.

    A global budget below two windows per eligible long parent cannot preserve
    both endpoints for everyone. The caller reports that shortfall explicitly.
    """
    preferences=[]
    for count in counts:
        indices=evenly_spaced(count,per_parent)
        preferences.append(([indices[0],indices[-1]]+indices[1:-1]) if len(indices)>1 else indices)
    allocated=[[] for _ in counts]
    for rank in range(per_parent):
        for i,indices in enumerate(preferences):
            if budget and rank<len(indices):allocated[i].append(indices[rank]);budget-=1
    return allocated


def language(e,store,provenance):
    from lingua import Language,LanguageDetectorBuilder
    options=store.config.models;limit=store.config.limits.language_units
    detector=LanguageDetectorBuilder.from_languages(*(getattr(Language,x) for x in options.languages)).build()
    counts=Counter();details=[];examined=0;ambiguous=0
    from datatrust.text_search import select_population
    selection=select_population(e,store,'language_selected',limit,nonempty=True)
    cursor=store.con.cursor().execute('SELECT s.uid,c.text FROM language_selected s JOIN content c USING(uid) ORDER BY s.selection_order')
    for batch in iter(lambda:cursor.fetchmany(64),[]):
        for uid,text in batch:
            gs=graphemes(text);starts=evenly_spaced(max(1,len(gs)-1024+1),3);predictions=[];margins=[]
            for start in starts:
                confidence=detector.compute_language_confidence_values(''.join(gs[start:start+1024]))
                if confidence:
                    predictions.append(confidence[0].language.name);margins.append(confidence[0].value-(confidence[1].value if len(confidence)>1 else 0))
            examined+=1
            if len(set(predictions))!=1 or not predictions:ambiguous+=1
            else:counts[predictions[0]]+=1
            if len(details)<store.config.limits.details:details.append({'reference':e.witness(uid),'window_predictions':predictions,'separation_margins':margins,'calibrated_probability':False})
        store.work.check('offline language batch')
    total=store.con.execute('SELECT count(*) FROM lexical_catalog WHERE chars>0').fetchone()[0]
    e.add('language',{'predicted_unit_counts':dict(counts),'window_disagreement_or_unresolved':ambiguous,'details':details,'model':{k:v for k,v in provenance.items() if k!='files'}},meaning='model_assisted_candidate',scope='bounded',coverage=selection|{'examined_units':examined,'unexamined_units':total-examined,'full_language_population_claimed':False})
    for info in provenance['files'].values():verify(info)


def embeddings(e,store,provenance):
    import numpy as np
    import torch
    from transformers import AutoTokenizer,AutoModel
    root=store.config.models.embedding_directory;limits=store.config.limits
    torch.set_num_threads(store.config.execution.threads);torch.manual_seed(store.config.seed);torch.use_deterministic_algorithms(True)
    tokenizer=AutoTokenizer.from_pretrained(root,local_files_only=True,trust_remote_code=False,use_fast=True)
    if not tokenizer.is_fast:raise ValueError('A pinned fast tokenizer is required for source offsets.')
    model=AutoModel.from_pretrained(root,local_files_only=True,trust_remote_code=False,use_safetensors=True).to('cpu').eval()
    tokenizer=AccountedTokenizer(tokenizer,limits)
    windows=[];parent_details=[];issues=Counter();tokenized=0;partial=0;embedded_parents=0;complete_parents=0;first_only=0;endpoints=0;covered_characters=0
    # First reserve a fair parent allocation, then distribute remaining windows round-robin.
    parents=[]
    from datatrust.text_search import select_population
    selection=select_population(e,store,'embedding_selected',limits.embedding_windows,nonempty=True)
    cursor=store.con.cursor().execute('SELECT s.uid,c.text,s.kind,s.role,s.sid FROM embedding_selected s JOIN content c USING(uid) ORDER BY s.selection_order')
    tokenized_counts=Counter();embedded_counts=Counter();work_exhausted=False
    for batch in iter(lambda:cursor.fetchmany(32),[]):
        for uid,text,kind,role,sid in batch:
            prefix='passage: ' if role in {'documents','chunks'} or kind=='chunk' else 'query: '
            try:ws,n,problem=make_windows(text,tokenizer,prefix=prefix,method=store.config.models.long_documents)
            except TokenizerBudget as exc:issues[str(exc)]+=1;work_exhausted=True;break
            tokenized+=1;tokenized_counts[sid]+=1;issues.update(problem)
            parents.append((uid,len(text),prefix,ws,n,sid))
        store.work.check('embedding source tokenization')
        if issues.get('source_input_byte_budget') or issues.get('emitted_token_work_budget'):break
    allocated=allocate_windows([len(parent[3]) for parent in parents],limits.embedding_windows,limits.windows_per_parent)
    vectors=[]
    for parent,selected in zip(parents,allocated):
        uid,chars,prefix,ws,n,sid=parent
        intervals=[];embedded_indices=[]
        for index in selected:
            if work_exhausted:break
            window=ws[index]
            try:encoded=tokenizer(prefix+window['text'],return_tensors='pt',truncation=False)
            except TokenizerBudget as exc:issues[str(exc)]+=1;work_exhausted=True;break
            used=encoded['input_ids'].shape[1]
            if used>512:raise ValueError('Source-aligned window exceeded its validated model limit.')
            with torch.inference_mode():
                output=model(**encoded).last_hidden_state;mask=encoded['attention_mask'].unsqueeze(-1)
                pooled=(output*mask).sum(1)/mask.sum(1);pooled=torch.nn.functional.normalize(pooled,p=2,dim=1)
            vector=pooled[0].cpu().numpy()
            if not np.isfinite(vector).all():raise ValueError('Embedding model returned nonfinite evidence.')
            vectors.append(vector)
            ref=e.span_witness(uid,window['start'],window['end'])
            windows.append({'reference':ref,'parent_reference':e.witness(uid),'source_span':[window['start'],window['end']],'token_span':[window['token_start'],window['token_end']],'prefix':prefix,'parent_window_index':index,'model_tokens':used})
            intervals.append((window['start'],window['end']));embedded_indices.append(index)
        covered=0;end=-1
        for a,b in sorted(intervals):covered+=max(0,b-max(a,end));end=max(end,b)
        complete=covered==chars;partial+=bool(intervals) and not complete;complete_parents+=complete;embedded_parents+=bool(intervals);covered_characters+=covered
        if intervals:embedded_counts[sid]+=1
        endpoint_pair=bool(ws) and 0 in embedded_indices and len(ws)-1 in embedded_indices
        endpoints+=endpoint_pair;first_only+=bool(ws) and 0 in embedded_indices and len(ws)>1 and len(ws)-1 not in embedded_indices
        if len(parent_details)<limits.details:parent_details.append({'reference':e.witness(uid),'source':e.sources[sid],'source_characters':chars,'source_characters_covered_union':covered,'eligible_windows':len(ws),'allocated_window_indices':selected,'embedded_window_indices':embedded_indices,'embedded_windows':len(intervals),'complete_source_coverage':complete,'first_and_last_eligible_windows_embedded':endpoint_pair})
        store.work.check('offline embedding parent')
    results=[];pairs=0;best=[[] for _ in vectors]
    if vectors:
        matrix=np.stack(vectors)
        for i in range(len(vectors)):
            remaining_pairs=limits.semantic_pairs-pairs
            if remaining_pairs<=0:break
            end=min(len(vectors),i+1+remaining_pairs)
            for start in range(i+1,end,128):
                stop=min(start+128,end);values=matrix[start:stop]@matrix[i];pairs+=stop-start
                for j,score in zip(range(start,stop),values):
                    if windows[i]['parent_reference']==windows[j]['parent_reference']:continue
                    best[i].append((float(score),j));best[j].append((float(score),i))
                best[i]=sorted(best[i],key=lambda x:(-x[0],x[1]))[:5]
                for j in range(start,stop):best[j]=sorted(best[j],key=lambda x:(-x[0],x[1]))[:5]
            store.work.check('semantic block comparisons')
        for i,neighbors in enumerate(best):
            if len(results)>=limits.details:break
            results.append({'window':windows[i],'neighbors':[{'window':windows[j],'cosine':score} for score,j in neighbors]})
    total=store.con.execute('SELECT count(*) FROM lexical_catalog WHERE chars>0').fetchone()[0]
    roles={item.id:item.role for item in store.spec.inputs}
    populations=[{'source':e.sources[sid],'declared_role':roles[sid],'selected_parents':count,'tokenized_parents':tokenized_counts[sid],'embedded_parents':embedded_counts[sid]} for sid,count in store.con.execute('SELECT sid,count(*) FROM embedding_selected GROUP BY sid ORDER BY sid').fetchall()]
    e.add('semantic_similarity',{'neighbors':results,'parent_coverage':parent_details,'model':{k:v for k,v in provenance.items() if k not in {'files','manifest'}}|{'artifact_hashes':{n:v['sha256'] for n,v in provenance['files'].items()}},'document_equivalence_claimed':False,'global_cosine_threshold':None},meaning='model_assisted_candidate',scope='bounded',coverage=selection|{'eligible_parents':total,'tokenized_parents':tokenized,'embedded_parents':embedded_parents,'unprocessed_parent_window_counts':'unknown','unprocessed_parents':total-tokenized,'selected_but_unprocessed_parents':selection['selected_population']-tokenized,'tokenized_but_unembedded_parents':tokenized-embedded_parents,'parent_detail_omissions':max(0,tokenized-len(parent_details)),'partial_parents':partial,'complete_parents':complete_parents,'parents_with_first_and_last_windows':endpoints,'first_only_long_parents':first_only,'source_characters_covered_union_across_parents':covered_characters,'parent_populations':populations,'window_allocation':'first_then_last_then_evenly_spaced_interiors_round_robin','endpoint_guarantee':'both only if actual allocation and tokenizer work permit; per-parent truth recorded','embedded_windows':len(windows),'tokenizer_bytes':tokenizer.bytes,'tokenizer_tokens':tokenizer.tokens,'token_work_reservation':'input bytes reserved before call; emitted tokens charged on return, including the final rejected whole call','pair_comparisons':pairs,'possible_selected_window_pairs':len(windows)*(len(windows)-1)//2,'exclusions':dict(issues),'window_method':store.config.models.long_documents})
    for info in provenance['files'].values():verify(info)
    verify(provenance['manifest'])


def investigate(e,store,provenance):
    if store.config.models.language:language(e,store,provenance['language'])
    if store.config.models.tokenizer:tokenizer_vocabulary(e,store,provenance['embedding'])
    if store.config.models.embedding_directory and store.config.models.embeddings:embeddings(e,store,provenance['embedding'])


def tokenizer_vocabulary(e,store,provenance):
    from transformers import AutoTokenizer
    tokenizer=AutoTokenizer.from_pretrained(store.config.models.embedding_directory,local_files_only=True,trust_remote_code=False,use_fast=True)
    counts=Counter();lengths=Counter();units=0;accepted_tokens=0;attempted=0;stop='selected_scope_completed'
    limits=store.config.limits
    tokenizer=AccountedTokenizer(tokenizer,limits)
    cursor=store.con.cursor().execute('SELECT s.uid,c.text FROM lexical_selected s JOIN content c USING(uid) ORDER BY s.selection_order')
    for batch in iter(lambda:cursor.fetchmany(64),[]):
        for uid,text in batch:
            attempted+=1
            try:ids=tokenizer(text,add_special_tokens=False,truncation=False)['input_ids']
            except TokenizerBudget as exc:stop=str(exc);break
            accepted_tokens+=len(ids);units+=1;counts.update(ids);lengths[len(ids)]+=1
        store.work.check('offline tokenizer vocabulary batch')
        if stop!='selected_scope_completed':break
    selected=store.con.execute('SELECT count(*) FROM lexical_selected').fetchone()[0]
    e.add('tokenizer_vocabulary',{'examined_units':units,'observed_distinct_token_ids':len(counts),'token_occurrences':accepted_tokens,'tokens_per_unit_distribution':dict(lengths),'top_token_ids':[{'reference':e.opaque('model_token_id',token),'count':n} for token,n in counts.most_common(limits.details)],'tokenizer_artifact_hash':provenance['files']['tokenizer.json']['sha256'],'truncation':False},meaning='contextual_observation',scope='bounded',coverage={'selected_population':selected,'examined_units':units,'attempted_units':attempted,'excluded_units':selected-units,'unattempted_units':selected-attempted,'tokenizer_bytes':tokenizer.bytes,'tokenizer_tokens':tokenizer.tokens,'accepted_token_occurrences':accepted_tokens,'stop_reason':stop,'token_work_reservation':'input bytes reserved before call; all attempted emitted tokens charged on return, including final rejected call','population_estimate':False})
