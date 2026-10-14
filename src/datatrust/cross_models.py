"""Pinned local paired adapters. Qualification is for the complete measured pipeline."""
from dataclasses import asdict
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import time

from datatrust.cross_private_base import digest
from datatrust.cross_contracts import CrossRepresentationAuditResult
from datatrust.image_assets import capture,decode
from datatrust.image_contracts import ImageWorkLimits
from datatrust.text_models import preflight as text_preflight,make_windows,RUNTIME
from datatrust.text_models import TokenizerBudget
from datatrust.text_contracts import TextModelOptions
from datatrust.scalable import Workspace,fail


def registry(): return json.loads(Path(__file__).with_name('cross_model_artifacts.json').read_text())


def algorithm_identity():
    return digest({n:hashlib.sha256(Path(__file__).with_name(n).read_bytes()).hexdigest() for n in ('cross.py','cross_models.py','cross_documents.py','cross_diagnostics.py','cross_sources.py','cross_contracts.py')})


def preflight(options):
    result={};allow=registry()
    for kind,directory in [('nli',options.nli_directory),('image_text',options.image_text_directory)]:
        if not directory: continue
        official=allow['models'].get(kind)
        if not official: raise ValueError('No publisher-pinned M9 artifacts for requested method.')
        root=Path(directory).absolute();manifest,raw,_=capture(root/'datatrust-model.json',(root,),max_bytes=1024**2)
        allowed=set(official['files'])|{'datatrust-model.json','publisher.json','README.md','LICENSE'}
        if any(p.is_symlink() or not p.is_file() or p.name not in allowed and not p.name.endswith('.rejected') for p in root.iterdir()): raise ValueError('Model directory contains unverified auxiliary artifacts.')
        declaration=json.loads(raw)
        if declaration.get('model')!=official['model'] or declaration.get('revision')!=official['revision'] or set(declaration.get('files',{}))!=set(official['files']): raise ValueError('Model identity differs from publisher allowlist.')
        files={}
        for name,pin in official['files'].items():
            if Path(name).name!=name: raise ValueError('Unsafe model artifact name.')
            info,raw,_=capture(root/name,(root,),max_bytes=16*1024**2 if pin['algorithm']!='sha256' else None)
            observed=info['sha256'] if pin['algorithm']=='sha256' else hashlib.sha1(b'blob '+str(info['bytes']).encode()+b'\0'+raw).hexdigest()
            if observed!=pin['digest'] or info['sha256']!=declaration['files'][name]: raise ValueError('Publisher model bytes differ.')
            files[name]=info
        files['datatrust-model.json']=manifest
        import importlib.metadata
        for name,version in {**RUNTIME,'sentencepiece':'0.2.1'}.items():
            if importlib.metadata.version(name)!=version: raise ValueError('Install pinned cross-models extra.')
        q=allow['qualification'].get(kind,{})
        qualified=q.get('status')=='passed' and q.get('algorithm_identity')==algorithm_identity() and q.get('revision')==official['revision']
        result[kind]={'directory':str(root),'model':official['model'],'revision':official['revision'],'files':files,'runtime':RUNTIME,'device':'cpu','dtype':'float32','license':official.get('license'),'qualified':qualified,'qualification':q if qualified else {'status':'unqualified'},'algorithm_identity':algorithm_identity()}
    if options.retrieval_directory:
        p,_=text_preflight(TextModelOptions(embedding_directory=options.retrieval_directory))
        root=Path(options.retrieval_directory)
        allowed=set(p['embedding']['files'])|{'datatrust-model.json','README.md','LICENSE'}
        if any(f.is_symlink() or not f.is_file() or f.name not in allowed for f in root.iterdir()): raise ValueError('Retrieval directory contains unverified auxiliary artifacts.')
        result['retrieval']=p['embedding']|{'directory':str(Path(options.retrieval_directory).absolute())}
    return result


class CountedTokenizer:
    def __init__(self,tokenizer,owner): self.tokenizer=tokenizer;self.owner=owner
    def __getattr__(self,n): return getattr(self.tokenizer,n)
    def __call__(self,*texts,**options):
        work=self.owner.tokenizer_work;limit=self.owner.limits
        values=[]
        for text in texts: values.extend(text if isinstance(text,(list,tuple)) else [text])
        for n in ('text','text_pair'):
            if n in options: values.extend(options[n] if isinstance(options[n],(list,tuple)) else [options[n]])
        size=sum(len(t.encode()) for t in values if isinstance(t,str))
        if work['bytes']+size>limit.tokenizer_bytes: raise TokenizerBudget('source_input_byte_budget')
        work['bytes']+=size;work['calls']+=1
        result=self.tokenizer(*texts,**options);ids=result['input_ids']
        if hasattr(ids,'numel'): tokens=int(ids.numel())
        elif ids and isinstance(ids[0],list): tokens=sum(len(x) for x in ids)
        else: tokens=len(ids)
        work['tokens']+=tokens
        if work['tokens']>limit.tokenizer_tokens: raise TokenizerBudget('emitted_token_work_budget')
        return result


class Adapters:
    def __init__(self,provenance,threads,limits=None):
        import torch
        torch.set_num_threads(threads);torch.manual_seed(0);torch.use_deterministic_algorithms(True)
        self.p=provenance;self.loaded={};self.tokenizer_calls=0;self.encoded_tokens=0;self.inference_pairs=0
        from datatrust.cross_contracts import CrossWorkLimits
        self.limits=limits or CrossWorkLimits();self.tokenizer_work={'calls':0,'bytes':0,'tokens':0}

    def load(self,kind):
        if kind in self.loaded: return self.loaded[kind]
        from transformers import AutoTokenizer,AutoModel,AutoModelForSequenceClassification,AutoProcessor
        root=self.p[kind]['directory']
        if kind=='image_text':
            tokenizer=AutoProcessor.from_pretrained(root,local_files_only=True,trust_remote_code=False,use_fast=False)
            model=AutoModel.from_pretrained(root,local_files_only=True,trust_remote_code=False,use_safetensors=True)
        else:
            tokenizer=AutoTokenizer.from_pretrained(root,local_files_only=True,trust_remote_code=False,use_fast=True)
            cls=AutoModelForSequenceClassification if kind=='nli' else AutoModel
            model=cls.from_pretrained(root,local_files_only=True,trust_remote_code=False,use_safetensors=True)
        if kind=='image_text': tokenizer.tokenizer=CountedTokenizer(tokenizer.tokenizer,self)
        else: tokenizer=CountedTokenizer(tokenizer,self)
        self.loaded[kind]=(tokenizer,model.to('cpu').float().eval());return self.loaded[kind]

    def embed(self,texts,prefix):
        import torch
        tokenizer,model=self.load('retrieval')
        inp=tokenizer([prefix+t for t in texts],padding=True,truncation=False,return_tensors='pt');self.tokenizer_calls+=len(texts);self.encoded_tokens+=int(inp['attention_mask'].sum())
        if inp['input_ids'].shape[1]>512: raise ValueError('Retrieval input exceeds declared window.')
        with torch.inference_mode():
            output=model(**inp).last_hidden_state;mask=inp['attention_mask'].unsqueeze(-1);vector=(output*mask).sum(1)/mask.sum(1)
            return torch.nn.functional.normalize(vector,p=2,dim=1).numpy()

    def text(self,item,limit,check):
        import numpy as np
        import torch
        if item['language']!='en' or any(e['language']!='en' for e in item['evidence']): return {'status':'abstained','reason':'english_scope_unresolved'}
        claim=item['claim']
        if any(any(0xd800<=ord(c)<=0xdfff for c in str(t)) for t in [claim,*[e['text'] for e in item['evidence']]]): return {'status':'abstained','reason':'invalid_unicode'}
        if not isinstance(claim,str) or len(claim.strip())<8 or not item['evidence']: return {'status':'abstained','reason':'claim_or_evidence_unusable'}
        rt,_=self.load('retrieval');nt,nm=self.load('nli');claim_tokens=nt(claim,add_special_tokens=False)['input_ids'];self.tokenizer_calls+=1
        if len(claim_tokens)>128: return {'status':'abstained','reason':'claim_token_bound'}
        windows=[]
        for e in item['evidence']:
            check()
            if not isinstance(e['text'],str) or not e['text'].strip(): continue
            proposed,_,issues=make_windows(e['text'],rt,prefix='passage: ')
            if not proposed: continue
            # Reserve first/last across parents. Bound interiors without claiming full coverage.
            selected=[proposed[0],proposed[-1]] if len(proposed)>1 else proposed
            for w in selected:
                # M6 source-aligned windows are dictionaries with original slices.
                a,b=w['start'],w['end'];text=e['text'][a:b]
                pair=nt(text,claim,add_special_tokens=True,truncation=False)['input_ids'];self.tokenizer_calls+=1
                if len(pair)>512: continue
                windows.append({'text':text,'reference':e['reference'],'span':[a,b],'partial_parent':len(selected)<len(proposed)})
        if not windows: return {'status':'abstained','reason':'no_eligible_source_window'}
        query=self.embed([claim],'query: ');scores=[]
        for i in range(0,len(windows),4):
            check();vectors=self.embed([w['text'] for w in windows[i:i+4]],'passage: ');scores.extend((vectors@query[0]).tolist())
        ordered=sorted(range(len(windows)),key=lambda i:(-scores[i],windows[i]['reference'],windows[i]['span']))
        # One candidate per distinct evidence occurrence before additional windows.
        selected=[];seen=set()
        for i in ordered:
            ref=windows[i]['reference']
            if ref not in seen and len(selected)<limit: selected.append(i);seen.add(ref)
        for i in ordered:
            if len(selected)>=limit: break
            if i not in selected: selected.append(i)
        predictions=[];q=self.p['nli']['qualification'];threshold=q.get('threshold',.9);margin=q.get('margin',.2)
        labels=nm.config.id2label
        for i in selected:
            check();w=windows[i];inp=nt(w['text'],claim,return_tensors='pt',truncation=False)
            if inp['input_ids'].shape[1]>512: continue
            self.inference_pairs+=1;self.encoded_tokens+=int(inp['attention_mask'].sum())
            with torch.inference_mode(): p=torch.softmax(nm(**inp).logits[0],dim=-1).numpy()
            named={str(labels[j]).lower():float(v) for j,v in enumerate(p)}
            # This publisher's explicit class order is checked, never guessed from LABEL_n.
            if set(named)!={'entailment','neutral','contradiction'}: raise ValueError('Publisher NLI label semantics differ.')
            ordered_scores=sorted(named.items(),key=lambda x:-x[1]);winner=ordered_scores[0]
            candidate=winner[0] if winner[1]>=threshold and winner[1]-ordered_scores[1][1]>=margin and winner[0]!='neutral' else 'abstained'
            predictions.append({'reference':w['reference'],'span':w['span'],'scores':named,'retrieval_score':scores[i],'judgment':candidate,'partial_parent':w['partial_parent']})
        judgments={p['judgment'] for p in predictions};status='mixed_evidence' if {'entailment','contradiction'}<=judgments else 'contradiction_candidate' if 'contradiction' in judgments else 'support_candidate' if 'entailment' in judgments else 'abstained'
        return {'status':status,'reason':'insufficient_examined_evidence' if status=='abstained' else None,'predictions':predictions,'reference_pool_complete':len(seen)==len({e['reference'] for e in item['evidence']}),'extraction_complete':item['complete'],'window_pool':len(windows),'evaluated_pairs':len(predictions),'scores_are_probabilities':False}

    def image_text(self,item,check,roots):
        import torch
        if item['language']!='en' or not isinstance(item['claim'],str) or not item['claim'].strip(): return {'status':'abstained','reason':'english_claim_scope_unresolved'}
        processor,model=self.load('image_text');images=[];refs=[];alternatives=[]
        for e in item['evidence']:
            if not e.get('asset') or not e.get('source_identity'): continue
            check();_,raw,_=capture(e['asset'],roots,expected=e['source_identity'],max_bytes=128*1024**2);facts,image=decode(raw,ImageWorkLimits())
            if image is not None: images.append(image);refs.append(e['reference']);alternatives.append(e.get('alternative',False))
        if not images: return {'status':'abstained','reason':'no_eligible_image'}
        tokens=processor.tokenizer(item['claim'],truncation=False)['input_ids'];self.tokenizer_calls+=1
        if len(tokens)>64: return {'status':'abstained','reason':'caption_token_bound'}
        scores=[]
        for i in range(0,len(images),2):
            check();inp=processor(text=[item['claim']],images=images[i:i+2],padding='max_length',max_length=64,truncation=False,return_tensors='pt')
            with torch.inference_mode(): scores.extend(model(**inp).logits_per_image[:,0].numpy().tolist())
        threshold=self.p['image_text']['qualification'].get('threshold',-2.0);self.inference_pairs+=len(images)
        primary=[float(v) for v,a in zip(scores,alternatives) if not a]
        return {'status':'abstained' if not primary else 'misassociation_candidate' if any(v<threshold for v in primary) else 'compatibility_candidate','predictions':[{'reference':r,'score':float(v),'alternative':a,'judgment':'alternative_review_candidate' if a else 'misassociation_candidate' if float(v)<threshold else 'compatibility_candidate'} for r,v,a in zip(refs,scores,alternatives)],'alternative_candidates':[{'reference':refs[i],'score':float(scores[i])} for i in sorted(range(len(scores)),key=lambda i:-scores[i]) if alternatives[i]][:3],'scores_are_probabilities':False}


def execute(items,provenance,config,allocation,*,progress=None,_benchmark=False):
    start=time.monotonic();work=Workspace(config.execution,[],progress,phase_plan={'estimated_peak_workspace_bytes':512*1024**2,'kind':'bounded_cross_models'})
    if progress: progress({'owned_workspace':str(work.root),'stage':'M9 optional models'})
    examined=[];omitted=0;loaded_seconds=0;adapter=None
    def check():
        if time.monotonic()-start>=allocation: raise TimeoutError('model_allocation')
        work.check('cross model unit')
    try:
        for item in items:
            p=provenance.get(item['kind'])
            if not p or not p['qualified'] and not _benchmark:
                examined.append({'target_id':item['target_id'],'rule':item['rule'],'status':'abstained','reason':'model_not_enabled_or_unqualified','evidence_refs':[item['claim_reference']]});continue
            if not _benchmark and (item.get('layout') not in p['qualification'].get('eligible_layouts',[]) or item.get('mapping_kind') not in p['qualification'].get('eligible_mapping_kinds',[]) or item['kind']=='nli' and any(e.get('format') not in {'pdf','docx'} for e in item['evidence'])):
                examined.append({'target_id':item['target_id'],'rule':item['rule'],'status':'abstained','reason':'outside_qualified_declaration_profile','evidence_refs':[item['claim_reference']]});continue
            try:
                check()
                if adapter is None: adapter=Adapters(provenance,config.execution.threads,config.limits)
                before=time.monotonic();adapter.load(item['kind']);loaded_seconds+=time.monotonic()-before
                answer=adapter.text(item,config.limits.evidence_candidates,check) if item['kind']=='nli' else adapter.image_text(item,check,tuple(config.execution.__dict__.get('allowed_roots',())) or tuple(str(Path(e['asset']).parent) for e in item['evidence'] if e.get('asset')))
                examined.append({'target_id':item['target_id'],'rule':item['rule'],**answer,'evidence_refs':[item['claim_reference'],*[e['reference'] for e in item['evidence'][:config.limits.evidence_candidates]]]})
            except (TimeoutError,TokenizerBudget):
                omitted=len(items)-len(examined);break
        execution={'status':'completed','effective_limits':asdict(config.execution),'peak_workspace_bytes':work.peak,'duration_seconds':time.monotonic()-start,'model_load_seconds':loaded_seconds,'tokenizer_calls':adapter.tokenizer_calls if adapter else 0,'encoded_tokens':adapter.encoded_tokens if adapter else 0,'inference_pairs':adapter.inference_pairs if adapter else 0}
        execution['tokenizer_work']=adapter.tokenizer_work if adapter else {'calls':0,'bytes':0,'tokens':0}
        execution['attempted_unit_charged']=bool(omitted)
        execution['effective_limits'].pop('scratch_directory',None)
        execution['methods']={k:{'model':p['model'],'revision':p['revision'],'license':p.get('license'),'qualified':p.get('qualified',False),'scope':p.get('qualification',{}).get('scope'),'threshold':p.get('qualification',{}).get('threshold'),'margin':p.get('qualification',{}).get('margin'),'device':'cpu','dtype':'float32'} for k,p in provenance.items() if k!='retrieval'}
        return CrossRepresentationAuditResult({'answers':examined},[],[],[],{'selected':len(items),'examined':len(examined),'unexamined':omitted,'stop_reason':'allocation' if omitted else None},execution,datetime.now(timezone.utc).isoformat(),{})
    finally: work.close()


def merge(result,stage):
    result.execution['model_execution']=stage.execution;result.coverage['models']=stage.coverage
    from collections import Counter
    counts=Counter(x['status'] for x in stage.profile['answers']);details=[]
    priorities={'mixed_evidence':0,'contradiction_candidate':1,'misassociation_candidate':1,'abstained':2,'support_candidate':3,'compatibility_candidate':3}
    for answer in sorted(stage.profile['answers'],key=lambda x:(priorities.get(x['status'],2),x['target_id'])):
        target=answer['target_id']
        if len(details)>=result.execution['cross_limits']['details']: continue
        answer=dict(answer);details.append(answer)
        existing=result.profile['review_targets'].get(target)
        if existing: existing['semantic']=answer
        else: result.profile['review_targets'][target]={'kind':'record_investigation','evidence_refs':answer['evidence_refs'],'semantic':answer,'population':answer['rule']}
    eid='measurement_models';result.evidence.append({'id':eid,'family':'models','population':'selected_claims_and_pairs','data':{**counts,'details':details},'references':[],'scope':'bounded'})
    result.checks.append({'id':eid,'family':'models','execution':'completed','scope':'bounded','applicability':'applicable','evidence_refs':[eid]})
    for status in ('contradiction_candidate','mixed_evidence','misassociation_candidate'):
        if counts[status]:
            fid='finding_'+status
            result.findings.append({'id':fid,'family':'models','title':'Review '+status.replace('_',' '),'priority':'Moderate','evidence_refs':[eid],'references':[],'population':'selected_claims_and_pairs','counts':{status:counts[status]}})
            result.profile['review_targets'][fid]={'kind':'aggregate_finding','evidence_refs':[eid],'population':'selected_claims_and_pairs','counts':{status:counts[status]},'inspection_scope':'Aggregate disposition does not establish individual record inspection.'}
