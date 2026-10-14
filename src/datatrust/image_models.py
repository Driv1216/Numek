"""Verified offline visual encoders; optional execution is a separate worker."""
from dataclasses import asdict
from datetime import datetime,timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path
import time

from datatrust.image_assets import capture,decode,error
from datatrust.image_contracts import ImageAuditResult
from datatrust.text_models import RUNTIME
from datatrust.text_normalization import strict_json

MODELS={'facebook/dinov2-small':'ed25f3a31f01632728cabb09d1542f84ab7b0056','facebook/dinov2-base':'f9e44c814b77203eaa57a6bdbbd535f21ede1415','google/siglip-base-patch16-224':'7fd15f0689c79d79e38b1c2e2e2370a7bf2761ed'}


def registry(): return json.loads(Path(__file__).with_name('image_model_artifacts.json').read_text())


def preflight(options,*,benchmark=False):
    if options.directory is None: return None
    for package,version in RUNTIME.items():
        try:
            if importlib.metadata.version(package)!=version: raise ValueError('Install the pinned image-embeddings extra.')
        except importlib.metadata.PackageNotFoundError as exc: raise ValueError('Install the pinned image-embeddings extra.') from exc
    root=Path(options.directory).absolute()
    manifest,raw,_=capture(root/'datatrust-model.json',(root,),max_bytes=1024**2)
    if raw is None: raise ValueError('Model manifest exceeds its limit.')
    declaration=strict_json(raw.decode()); model=declaration.get('model'); official=registry()
    if model not in MODELS or declaration.get('revision')!=MODELS[model]: raise ValueError('Unsupported image model identity.')
    if not benchmark:
        selection=official.get('selection',{})
        chosen=selection.get(options.mode)
        if selection.get('status')!='passed' or not chosen or chosen['model']!=model: raise ValueError('Model does not match the measured shipping profile.')
    files={}
    declared=official['models'][model]['files']
    required={'config.json','preprocessor_config.json','model.safetensors'}
    if not isinstance(declaration.get('files'),dict) or set(declaration['files'])!=required: raise ValueError('Model requires exactly the pinned config, processor and safetensors files.')
    for name in required:
        info,raw,_=capture(root/name,(root,),max_bytes=1024**2 if name!='model.safetensors' else None)
        if info['sha256']!=declaration['files'][name]: raise ValueError('Local image model integrity mismatch.')
        pinned=declared[name]
        observed=info['sha256'] if pinned['algorithm']=='sha256' else hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
        if observed!=pinned['digest']: raise ValueError('Image model bytes differ from the pinned publisher artifacts.')
        files[name]=info
    return {'model':model,'revision':MODELS[model],'files':files,'manifest':manifest,'runtime':RUNTIME,'license':'Apache-2.0','license_identity':official['models'][model].get('license_identity'),'device':'cpu','dtype':'float32','pooling':'l2_normalized_cls' if 'dinov2' in model else 'l2_normalized_vision_pooler','operating_point':official.get('selection',{}).get(options.mode,{}).get('threshold'),'review_evidence':official.get('review_evidence',{}) if model==official.get('selection',{}).get('default',{}).get('model') else {}}


def selection(store,e):
    con=store.con; limit=store.config.limits.embedding_images
    if not con.execute("SELECT 1 FROM information_schema.tables WHERE table_name='signatures'").fetchone():
        from datatrust.image_search import build_index
        build_index(store)
    catalog={}
    rows=con.execute('SELECT s.aid,s.path,min(o.oid),list(DISTINCT m.split),list(DISTINCT m.sid),list(DISTINCT struct_pack(sid := m.sid, split := m.split)) FROM signatures s JOIN signature_membership m USING(aid) JOIN occurrences o ON o.path=s.path GROUP BY s.aid,s.path').fetchall()
    for aid,path,oid,splits,sources,memberships in rows:
        catalog[aid]={'aid':aid,'path':path,'identity':store.files[path],'oid':oid,'splits':sorted(splits),'sources':sorted(store.sources[v] for v in sources),'memberships':[[store.sources[v['sid']],v['split']] for v in memberships]}
    focused=[]; chosen=set()
    for a,b,_ in con.execute('SELECT * FROM image_candidates ORDER BY distance,hash(left_aid,right_aid,?) LIMIT ?',[store.config.seed,limit]).fetchall():
        if len(focused)+sum(x not in chosen for x in (a,b))>limit//2: continue
        for aid in (a,b):
            if aid not in chosen: focused.append(dict(catalog[aid],purpose='candidate_focused')); chosen.add(aid)
    # Independent selection reserves evaluation and reference sides, then round-robins split strata.
    groups={}
    for aid in con.execute('SELECT aid FROM signatures ORDER BY hash(aid,?),aid',[store.config.seed]).fetchall():
        value=catalog[aid[0]]
        for split in value['splits']: groups.setdefault(split,[]).append(aid[0])
    evaluation={'validation','test','evaluation'}
    query=[k for k in groups if k in evaluation]; refs=[k for k in groups if k not in evaluation]
    def take(keys,count,purpose):
        result=[]; cursors={k:0 for k in keys}
        while len(result)<count:
            progressed=False
            for k in keys:
                while cursors[k]<len(groups[k]) and groups[k][cursors[k]] in chosen: cursors[k]+=1
                if cursors[k]<len(groups[k]):
                    aid=groups[k][cursors[k]]; cursors[k]+=1; chosen.add(aid); result.append(dict(catalog[aid],purpose=purpose)); progressed=True
                    if len(result)>=count: break
            if not progressed: break
        return result
    available=limit-len(focused); independent=take(query,available//4,'discovery_query')+take(refs,available-available//4,'discovery_reference')
    independent+=take(list(groups),limit-len(focused)-len(independent),'discovery')
    # Interleave purposes so a CPU time bound does not leave discovery entirely untouched.
    output=[]
    for i in range(max(len(focused),len(independent))):
        if i<len(focused): output.append(focused[i])
        if i<len(independent): output.append(independent[i])
    store.model_populations=[{'source':store.sources[sid],'split':split,'split_reference':e.opaque('split',split),'eligible_rasters':n} for sid,split,n in con.execute('SELECT sid,split,count(DISTINCT aid) FROM signature_membership GROUP BY sid,split ORDER BY sid,split').fetchall()]
    for value in output: value['reference']=store.witness(value.pop('oid'))
    return output


def load_encoder(provenance,threads):
    import torch
    from transformers import AutoImageProcessor,AutoModel,SiglipVisionModel
    torch.set_num_threads(threads); torch.use_deterministic_algorithms(True); torch.manual_seed(0)
    root=str(Path(provenance['manifest']['path']).parent)
    processor=AutoImageProcessor.from_pretrained(root,local_files_only=True,trust_remote_code=False,use_fast=False)
    cls=AutoModel if 'dinov2' in provenance['model'] else SiglipVisionModel
    model=cls.from_pretrained(root,local_files_only=True,trust_remote_code=False,use_safetensors=True).to('cpu').eval()
    return processor,model


def encode(processor,model,images,provenance):
    import torch
    with torch.inference_mode():
        output=model(**processor(images=images,return_tensors='pt'))
        values=output.last_hidden_state[:,0] if 'dinov2' in provenance['model'] else output.pooler_output
        values=torch.nn.functional.normalize(values,p=2,dim=1).cpu().numpy()
    import numpy as np
    if not np.isfinite(values).all(): error('nonfinite_image_embedding','image model')
    return values


def review_pairs(suggestions,limit=3):
    """Bound the exported undirected graph, not just its directed proposals.

    Cross-split proposals precede within-split proposals, then higher cosine and
    stable endpoint order win. This deterministic greedy cap is not a maximum
    matching or a matching-quality guarantee.
    """
    union={}
    for i,rows in enumerate(suggestions):
        for score,j,cross in rows:
            key=(min(i,j),max(i,j))
            union[key]=(score,cross)
    selected=[]; degrees=[0]*len(suggestions)
    for (i,j),(score,cross) in sorted(union.items(),key=lambda x:(not x[1][1],-x[1][0],x[0])):
        if degrees[i]>=limit or degrees[j]>=limit: continue
        selected.append((i,j,score,cross)); degrees[i]+=1; degrees[j]+=1
    return selected,len(union)


def execute_model(selected,provenance,spec,config,allocation,audit_id,populations=(),*,progress=None):
    import numpy as np
    from datatrust.image_sources import roots_for
    started=time.monotonic(); processor,model=load_encoder(provenance,config.execution.threads)
    vectors=[]; accepted=[]; read_bytes=0; excluded=0; inference_seconds=0; batch_size=4; stop='selected_population_completed'
    for start in range(0,len(selected),batch_size):
        remaining=allocation-(time.monotonic()-started)
        predicted=inference_seconds/max(1,len(accepted))*batch_size
        if remaining<=max(.1,predicted*1.5): stop='model_time_allocation'; break
        batch=selected[start:start+batch_size]; images=[]; valid=[]
        for item in batch:
            info,raw,_=capture(item['path'],roots_for(spec),max_bytes=config.source_limits.asset_capture_bytes,expected=item['identity'])
            read_bytes+=info['bytes']; facts,preview=decode(raw,config.limits)
            if preview is None: excluded+=1; continue
            images.append(preview); valid.append(item)
        if images:
            tick=time.monotonic(); vectors.extend(encode(processor,model,images,provenance)); inference_seconds+=time.monotonic()-tick; accepted.extend(valid)
        if progress: progress({'stage':'offline visual embeddings','embedded':len(accepted),'selected':len(selected)})
    matrix=np.stack(vectors) if vectors else np.empty((0,0),dtype=np.float32)
    pairs=0; candidates=[]; threshold=provenance.get('operating_point'); threshold=1.0 if threshold is None else threshold
    suggestions=[[] for _ in accepted]; examined=np.zeros(len(accepted),dtype=np.int64)
    # Every charged unordered comparison updates both endpoints' top-three lists.
    # Cross-split work runs first; one common cap applies across both search phases.
    for cross in (True,False):
        stopped=False
        for i,item in enumerate(accepted):
            for start in range(i+1,len(accepted),512):
                if time.monotonic()-started>=allocation: stop='model_time_allocation'; stopped=True; break
                if pairs>=config.limits.cosine_pairs: stop='cosine_pair_budget'; stopped=True; break
                indices=[j for j in range(start,min(start+512,len(accepted))) if any(a!=b for a in item['splits'] for b in accepted[j]['splits'])==cross]
                indices=indices[:config.limits.cosine_pairs-pairs]
                if not indices: continue
                scores=matrix[indices]@matrix[i]; pairs+=len(indices); examined[i]+=len(indices); examined[indices]+=1
                for j,score in zip(indices,scores):
                    if float(score)>=threshold:
                        suggestions[i]=sorted(suggestions[i]+[(float(score),j,cross)],key=lambda x:(-x[0],x[1]))[:3]
                        suggestions[j]=sorted(suggestions[j]+[(float(score),i,cross)],key=lambda x:(-x[0],x[1]))[:3]
            if stopped: break
        if stopped: break
    bounded_pairs,qualifying=review_pairs(suggestions)
    for i,j,score,cross in bounded_pairs[:config.limits.details]:
        candidates.append({'left':accepted[i]['reference'],'right':accepted[j]['reference'],'cosine':score,'cross_split':cross,'selection_purposes':[accepted[i]['purpose'],accepted[j]['purpose']]})
    public_model={k:v for k,v in provenance.items() if k not in {'files','manifest'}}
    public_model['artifact_hashes']={k:v['sha256'] for k,v in provenance['files'].items()}
    record={'id':'image_embeddings','family':'embeddings','meaning':'model_assisted_candidate','scope':'bounded','references':[],'data':{'candidates':candidates,'model':public_model,'correct_labels_identified':False,'similarity_proves_leakage':False}}
    coverage={'selected':len(selected),'embedded':len(accepted),'excluded':excluded,'unattempted':len(selected)-len(accepted)-excluded,'selection_purposes':{p:sum(x['purpose']==p for x in accepted) for p in {x['purpose'] for x in selected}},'cosine_comparisons':pairs,'encoded_query_population':len(accepted),'queries_started':int((examined>0).sum()),'queries_completed':int((examined==max(0,len(accepted)-1)).sum()),'qualifying_review_pairs':qualifying,'retained_review_pairs':len(candidates),'suggestions_per_query':3,'stop_reason':stop,'reference_pool_complete':False,'absence_claim':'selected encoded reference pool only'}
    coverage['populations']=[{'source':v['source'],'split':v['split_reference'],'eligible_rasters':v['eligible_rasters'],'selected_rasters':sum([v['source'],v['split']] in x['memberships'] for x in selected),'encoded_rasters':sum([v['source'],v['split']] in x['memberships'] for x in accepted)} for v in populations]
    coverage.update(review_pairs_after_endpoint_cap=len(bounded_pairs),endpoint_cap_omissions=qualifying-len(bounded_pairs),detail_omissions=len(bounded_pairs)-len(candidates),suggestion_limit_scope='Both endpoints of every exported undirected pair',pair_selection='Directed top-three union; greedy cross-split first, cosine descending, stable endpoints; degree at most three',matching_quality_claim=False,benchmark_scope='Recorded query-wise top-three benchmark precedes this exported degree cap; post-cap retrieval quality is unmeasured.')
    coverage['reference_pool_complete']=bool(populations) and all(v['encoded_rasters']==v['eligible_rasters'] for v in coverage['populations'])
    execution={'status':'completed','backend':'offline_cpu','effective_limits':asdict(config.execution),'peak_workspace_bytes':0,'duration_seconds':time.monotonic()-started,'read_bytes':read_bytes,'inference_seconds':inference_seconds,'allocated_seconds':allocation}
    return ImageAuditResult({'audit_id':audit_id},[{'id':'image_embeddings','family':'embeddings','applicability':'applicable','execution':'completed','scope':'bounded'}],[record],[],{'families':{'embeddings':coverage}},execution,datetime.now(timezone.utc).isoformat(),{'locators':{}})
