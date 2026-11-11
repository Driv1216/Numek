"""First-class supplied vectors and two publisher-pinned offline CG4 encoders."""
import hashlib
import importlib.metadata
import io
import json
from pathlib import Path
import shutil
import numpy as np
from .contracts import EvaluationError,digest,strict_json
from .sources import records,key
from .feature_storage import validate_matrix
from .feature_contracts import ENCODER_DIMENSIONS
from . import compat

E5='fd1525a9fd15316a2d503bf26ab031a61d056e98'
DINO='f9e44c814b77203eaa57a6bdbbd535f21ede1415'
RUNTIMES={'encoders_cpu_v1':{'torch':'2.8.0','transformers':'4.57.1','tokenizers':'0.22.1','safetensors':'0.6.2'},
          'encoders_cpu_py314_v1':{'torch':'2.10.0','transformers':'4.57.1','tokenizers':'0.22.1','safetensors':'0.6.2'}}


def admit_aligned_matrix(rows,dimensions,dtype,config):
    """Bound the aligned output before allocating, including mostly absent keys."""
    dtype=np.dtype(dtype)
    if dtype.kind!='f' or dtype.itemsize not in (4,8) or dtype.hasobject:raise EvaluationError('Invalid vector dtype.','vector_dtype')
    required=int(rows)*int(dimensions)*dtype.itemsize
    if required>config.max_rss_bytes//3:raise EvaluationError('Aligned representation exceeds its share of the worker memory budget.','representation_memory_admission')
    return required


def subset(representation,indices):
    """Preserve alignment of every observation-level representation field."""
    result={**representation,'vectors':representation['vectors'][indices],
            'available':representation['available'][indices]}
    for field in ('reason','coverage'):
        if field in representation:result[field]=[representation[field][int(i)] for i in indices]
    return result


def supplied(spec,keys,work,config,roots):
    info,_,_=compat.capture(spec.matrix_path,roots);path=work.root/('vectors-'+digest(spec.id)[:20]+'.npy')
    work.check('vector snapshot reservation',info['bytes'])
    with compat.secure_open(spec.matrix_path,roots) as (source,_),path.open('xb') as output:shutil.copyfileobj(source,output,1024**2)
    compat.capture(spec.matrix_path,roots,expected=info)
    with path.open('rb') as stream:captured=hashlib.file_digest(stream,'sha256').hexdigest()
    if captured!=info['sha256']:raise EvaluationError('Vector source changed during capture.','source_changed')
    shape=validate_matrix(path,max_dimensions=spec.dimensions or 16384,max_rows=config.max_rows,max_bytes=config.max_combined_source_bytes)
    if spec.dimensions and shape['dimensions']!=spec.dimensions:raise EvaluationError('Declared vector dimensions differ.','vector_shape')
    admit_aligned_matrix(len(keys),shape['dimensions'],shape['dtype'],config)
    meta_info,_,_=compat.capture(spec.keys_source.path,roots);snapshot=work.root/('vector-keys-'+digest(spec.id)[:20]+'.'+spec.keys_source.format)
    with compat.secure_open(spec.keys_source.path,roots) as (source,_),snapshot.open('xb') as output:shutil.copyfileobj(source,output,1024**2)
    mapping={};availability={};count=0;required=set(spec.key_columns)
    if spec.available_at:required.add(spec.available_at.column)
    if spec.content_available_at:required.add(spec.content_available_at.column)
    for location,row in records(snapshot,spec.keys_source,config,required):
        if row is None:
            if required-set(location['header']):raise EvaluationError('Representation key columns are absent.')
            continue
        event=key(row,spec.key_columns,None)
        if event is None or event in mapping:raise EvaluationError('Representation keys must be present and unique.','representation_key_conflict')
        mapping[event]=count;count+=1
        clock=spec.content_available_at or spec.available_at
        if clock:
            tick,state=compat.clock(row.get(clock.column),clock);availability[event]=(tick,state)
    if count!=shape['rows']:raise EvaluationError('Representation keys and matrix rows differ.','vector_alignment')
    compat.capture(spec.keys_source.path,roots,expected=meta_info)
    matrix=np.load(path,mmap_mode='r',allow_pickle=False,max_header_size=10000)
    output=np.full((len(keys),shape['dimensions']),np.nan,dtype=matrix.dtype);valid=np.zeros(len(keys),bool);reasons=[]
    for i,event in enumerate(keys):
        position=mapping.get(event)
        if position is None:reasons.append('representation_not_retained');continue
        vector=matrix[position]
        if not np.isfinite(vector).all():reasons.append('invalid_representation');continue
        output[i]=vector;valid[i]=True;reasons.append('')
        if i%512==0:work.check('vector alignment')
    if spec.normalization=='l2':
        bad=valid&np.all(output==0,axis=1);valid[bad]=False
        for i in np.flatnonzero(bad):reasons[i]='zero_norm_representation'
    return {'id':spec.id,'vectors':output,'available':valid,'reason':reasons,'normalization':spec.normalization,
            'availability':availability,'provenance':{'spec':spec.to_dict(),'matrix':info,'keys':meta_info,'shape':shape,
              'identity_qualification':'producer-declared model hash; publisher authenticity not independently established' if spec.model_digest else 'producer declared; model bytes unknown'}}, {spec.id+':matrix':info,spec.id+':keys':meta_info}


def verified_encoder(spec,roots,work):
    import datatrust
    expected_runtime=RUNTIMES[spec.runtime_profile]
    for package,version in expected_runtime.items():
        try:observed=importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:observed=None
        if observed!=version and not (package=='torch' and observed==version+'+cpu'):raise EvaluationError('Install the explicitly pinned offline encoder runtime.','encoder_runtime')
    root=Path(spec.model_directory).absolute();manifest_info,raw,_=compat.capture(root/'datatrust-model.json',roots,max_bytes=1024**2)
    manifest=strict_json(raw);image=spec.kind=='dinov2_image'
    model='facebook/dinov2-base' if image else 'intfloat/multilingual-e5-small';revision=DINO if image else E5
    if manifest.get('model')!=model or manifest.get('revision')!=revision:raise EvaluationError('Encoder is outside the pinned CG4 profiles.','encoder_identity')
    package=Path(datatrust.__file__).parent
    official=strict_json((package/('image_model_artifacts.json' if image else 'text_model_artifacts.json')).read_text())
    declared=official['models'][model]['files'] if image else official['files']
    required={'config.json','preprocessor_config.json','model.safetensors'} if image else {'config.json','model.safetensors','tokenizer.json','tokenizer_config.json','special_tokens_map.json'}
    if not required<=set(manifest.get('files',{})):raise EvaluationError('Encoder lacks required pinned files.','encoder_identity')
    files={}
    for name,sha in manifest['files'].items():
        if Path(name).name!=name or name not in declared:raise EvaluationError('Unapproved encoder file.','encoder_identity')
        info,data,_=compat.capture(root/name,roots,max_bytes=None if name.endswith('.safetensors') else 16*1024**2)
        if info['sha256']!=sha:raise EvaluationError('Encoder bytes changed.','encoder_identity')
        pin=declared[name]
        if pin['algorithm']=='sha256':actual=info['sha256']
        else:
            if data is None:
                with compat.secure_open(root/name,roots) as (stream,_):data=stream.read()
            actual=hashlib.sha1(b'blob '+str(info['bytes']).encode()+b'\0'+data).hexdigest()
        if actual!=pin['digest']:raise EvaluationError('Encoder publisher bytes differ.','encoder_identity')
        files[name]=info;work.check('offline encoder verification')
    if spec.model_digest is not None and spec.model_digest!=files['model.safetensors']['sha256']:raise EvaluationError('Declared encoder weight identity differs from the verified pinned file.','encoder_identity')
    return {'model':model,'revision':revision,'runtime':{name:importlib.metadata.version(name) for name in expected_runtime},'profile':spec.runtime_profile,'files':files,'manifest':manifest_info,
            'device':'cpu','dtype':'float32','producer':'publisher_pinned_offline_encoder_v1','training_on_investigation_data':False}


def encode(spec,keys,features,work,config,limits,roots,asset_base):
    admit_aligned_matrix(len(keys),ENCODER_DIMENSIONS[spec.kind],'<f4',config)
    provenance=verified_encoder(spec,roots,work)
    import torch
    from transformers import AutoModel,AutoTokenizer,AutoImageProcessor
    torch.set_num_threads(config.threads);torch.use_deterministic_algorithms(True);torch.manual_seed(0)
    model=AutoModel.from_pretrained(spec.model_directory,local_files_only=True,trust_remote_code=False,use_safetensors=True).to('cpu').eval()
    image=spec.kind=='dinov2_image';dimensions=ENCODER_DIMENSIONS[spec.kind]
    matrix=np.full((len(keys),dimensions),np.nan,dtype='<f4');valid=np.zeros(len(keys),bool);reasons=[];coverage=[];files={}
    cells=features.get(spec.field)
    if cells is None:raise EvaluationError('Encoder content field is absent.','feature_not_retained')
    tokens=windows=pixels=0
    if image:processor=AutoImageProcessor.from_pretrained(spec.model_directory,local_files_only=True,trust_remote_code=False,use_fast=False)
    else:
        tokenizer=AutoTokenizer.from_pretrained(spec.model_directory,local_files_only=True,trust_remote_code=False,use_fast=True)
        from datatrust.text_models import make_windows
    for i,cell in enumerate(cells):
        if cell['state']!='observed':reasons.append('content_'+cell['state']);coverage.append({'complete':False});continue
        work.check('offline representation encoding')
        if image:
            from PIL import Image,ImageOps
            path=Path(cell['lexical']);path=path if path.is_absolute() else Path(asset_base)/path
            info,raw,_=compat.capture(path,roots,max_bytes=config.max_record_bytes)
            if raw is None:reasons.append('image_byte_limit');coverage.append({'complete':False});continue
            with Image.open(io.BytesIO(raw)) as raster:
                count=raster.width*raster.height
                if pixels+count>limits.max_encoder_pixels:reasons.append('image_pixel_budget');coverage.append({'complete':False});continue
                pixels+=count;rgb=ImageOps.exif_transpose(raster).convert('RGB')
                with torch.inference_mode():
                    output=model(**processor(images=rgb,return_tensors='pt')).last_hidden_state[:,0]
                    vector=torch.nn.functional.normalize(output,p=2,dim=1)[0].cpu().numpy()
            files['asset:'+digest(keys[i])]=info;coverage.append({'complete':True,'pixels':count,'source_sha256':info['sha256']})
        else:
            text=cell['lexical']
            if tokens+len(text.encode())>limits.max_encoder_tokens:reasons.append('text_token_work_admission');coverage.append({'complete':False});continue
            admitted,total,issues=make_windows(text,tokenizer,prefix='passage: ',method='token_windows_v1');tokens+=total
            if tokens>limits.max_encoder_tokens:raise EvaluationError('Tokenizer work exceeded admission.','encoder_token_limit')
            remaining=min(spec.max_windows_per_event,limits.max_encoder_windows-windows)
            indices=np.linspace(0,len(admitted)-1,min(len(admitted),max(0,remaining)),dtype=int) if admitted else []
            pooled=[];weights=[];end=0;covered=0
            for index in indices:
                window=admitted[int(index)];batch=tokenizer('passage: '+window['text'],return_tensors='pt',truncation=False)
                amount=int(batch['input_ids'].numel());tokens+=amount
                if amount>512 or tokens>limits.max_encoder_tokens:raise EvaluationError('Frozen text token budget exceeded.','encoder_token_limit')
                with torch.inference_mode():
                    output=model(**batch).last_hidden_state;mask=batch['attention_mask'].unsqueeze(-1)
                    average=(output*mask).sum(1)/mask.sum(1);embedding=torch.nn.functional.normalize(average,p=2,dim=1)[0].cpu().numpy()
                new=max(0,window['token_end']-max(end,window['token_start']));end=max(end,window['token_end']);covered+=new
                pooled.append(embedding);weights.append(max(1,new));windows+=1
            if not pooled:reasons.append('text_window_unavailable');coverage.append({'complete':False,'tokens':total});continue
            vector=np.average(pooled,axis=0,weights=weights);norm=np.linalg.norm(vector);vector=vector/norm if norm>0 else vector*np.nan
            coverage.append({'complete':len(indices)==len(admitted),'source_tokens':total,'covered_tokens_union':covered,'windows':len(indices),'issues':issues})
        if np.isfinite(vector).all():matrix[i]=vector;valid[i]=True;reasons.append('')
        else:reasons.append('nonfinite_encoder_output')
    for info in provenance['files'].values():compat.capture(info['path'],roots,expected=info)
    provenance.update(prefix=None if image else 'passage: ',pooling='l2_cls' if image else 'unique_token_weighted_window_mean_then_l2',windows=windows,token_work=tokens,pixels=pixels)
    availability={event:(int(cell['available_ns']) if cell.get('available_ns') is not None else None,cell.get('availability_state','undeclared')) for event,cell in zip(keys,cells)}
    return {'id':spec.id,'vectors':matrix,'available':valid,'reason':reasons,'normalization':'none','availability':availability,'provenance':provenance,'coverage':coverage},files
