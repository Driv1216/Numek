"""Four fixed trusted adapters; model files never select Python imports."""
import copy
import hashlib
import importlib
import inspect
import json
from pathlib import Path
import shutil
import time

import numpy as np

from .. import compat
from ..contracts import EvaluationError, digest
from .contracts import bounded, shape
from . import devices

_HOST = {}


def register_host_predictor(identifier, factory, *, code_files, gradients=False, batch_independent=True):
    """OS-operator Python API only. Registrations are not accepted from model JSON."""
    from ..contracts import name
    name(identifier)
    if not callable(factory) or '<locals>' in factory.__qualname__ or factory.__module__=='__main__':
        raise EvaluationError('Host factories must be importable installed functions.','host_registration')
    files={str(Path(p).absolute()):hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in code_files}
    if not files or not any(Path(p).resolve()==Path(inspect.getsourcefile(factory)).resolve() for p in files):
        raise EvaluationError('Host registration must bind its factory source file.','host_registration')
    value={'module':factory.__module__,'qualname':factory.__qualname__,'files':files,
           'gradients':bool(gradients),'batch_independent':bool(batch_independent)}
    value['code_digest']=digest(value);_HOST[identifier]=value
    return copy.deepcopy(value)


def host_bindings(): return copy.deepcopy(_HOST)


def host_factory(identifier, registrations):
    value=registrations.get(identifier)
    if value is None: raise EvaluationError('Host registration is unavailable.','host_registration')
    for path,sha in value['files'].items():
        if hashlib.sha256(Path(path).read_bytes()).hexdigest()!=sha: raise EvaluationError('Host code changed.','source_changed')
    obj=importlib.import_module(value['module'])
    for part in value['qualname'].split('.'):obj=getattr(obj,part)
    return obj,value


def capture_artifacts(spec, roots, work, limits):
    if len(spec.files)>limits.max_artifact_files: raise EvaluationError('Model file count exceeded.','model_limit')
    directory=work.root/('model-'+spec.predictor_digest)
    directory.mkdir(exist_ok=True)
    identities={};total=0
    for f in spec.files:
        info,_,_=compat.capture(f.path,roots,check=lambda:work.check('model verification'))
        total+=info['bytes']
        if total>limits.max_artifact_bytes: raise EvaluationError('Model artifact bytes exceeded.','model_limit')
        if info['sha256']!=f.sha256: raise EvaluationError('Model bytes differ from manifest.','model_changed')
        target=directory/f.name;target.parent.mkdir(parents=True,exist_ok=True)
        work.check('model snapshot reservation',info['bytes'])
        if not target.exists():
            with compat.secure_open(f.path,roots) as (source,_),target.open('xb') as out:shutil.copyfileobj(source,out,1024**2)
        with target.open('rb') as captured:actual=hashlib.file_digest(captured,'sha256').hexdigest()
        if actual!=f.sha256: raise EvaluationError('Model changed during capture.','source_changed')
        compat.capture(f.path,roots,expected=info)
        identities[f.name]=info
    return directory,identities


def torch_architecture(spec, registrations,allocation_bytes=2*1024**3):
    import torch
    from torch import nn
    a=spec.architecture
    kind=a.get('kind','mlp')
    if kind=='host':
        if not spec.registration: raise EvaluationError('Host architecture registration required.')
        factory,_=host_factory(spec.registration,registrations)
        return factory(copy.deepcopy(a))
    shape(a,{'kind','input_dim','hidden','output_dim','head','levels','channels','vocabulary','embedding_dim'})
    head=a.get('head','linear')
    if head not in {'linear','positive','quantiles','sigmoid'}: raise EvaluationError('Unknown Torch output head.')
    output_dim=a.get('output_dim',len(spec.task.classes) if spec.task.classes else 1)
    hidden=a.get('hidden',[128,128])
    if type(output_dim) is not int or not 1<=output_dim<=10000 or not isinstance(hidden,list) or len(hidden)>8 or any(type(h) is not int or not 1<=h<=4096 for h in hidden): raise EvaluationError('Torch architecture allocation exceeded.','model_limit')
    if kind=='mlp':
        dims=[a.get('input_dim',len(spec.inputs)),*hidden,output_dim]
        if any(type(v) is not int or v<1 for v in dims) or sum((x+1)*y for x,y in zip(dims,dims[1:]))*8>allocation_bytes:raise EvaluationError('Decoded architecture exceeds preallocation admission.','model_limit')
    elif kind=='text':
        n=a.get('vocabulary',10000);d=a.get('embedding_dim',64)
        if type(n) is not int or type(d) is not int or not 1<=n<=1000000 or not 1<=d<=1024 or (n*d+(d+1)*output_dim)*8>allocation_bytes:raise EvaluationError('Text architecture exceeds preallocation admission.','model_limit')
    elif kind=='cnn':
        channels=a.get('channels',3)
        if type(channels) is not int or not 1<=channels<=64 or ((channels*9+1)*16+17*output_dim)*8>allocation_bytes:raise EvaluationError('Image architecture exceeds preallocation admission.','model_limit')
    class Network(nn.Module):
        def __init__(self):
            super().__init__()
            if kind=='mlp':
                dim=a.get('input_dim',len(spec.inputs))
                if type(dim) is not int or not 1<=dim<=100000: raise EvaluationError('Invalid model input dimension.')
                layers=[]
                for h in hidden:layers.extend([nn.Linear(dim,h),nn.ReLU()]);dim=h
                layers.append(nn.Linear(dim,output_dim));self.net=nn.Sequential(*layers)
            elif kind=='cnn':
                self.net=nn.Sequential(nn.Conv2d(a.get('channels',3),16,3,padding=1),nn.ReLU(),nn.AdaptiveAvgPool2d((1,1)),nn.Flatten(),nn.Linear(16,output_dim))
            elif kind=='text':
                n=a.get('vocabulary',10000);d=a.get('embedding_dim',64)
                if type(n) is not int or not 1<=n<=1000000 or type(d) is not int or not 1<=d<=1024:raise EvaluationError('Text model allocation exceeded.')
                self.embedding=nn.Embedding(n,d);self.net=nn.Linear(d,output_dim)
            else:raise EvaluationError('Unsupported built-in architecture.')
        def forward(self,x=None,attention_mask=None,input_ids=None):
            if kind=='text':
                if input_ids is not None:x=input_ids
                e=self.embedding(x);mask=(x!=spec.preprocessing.get('padding_id',0)).unsqueeze(-1) if attention_mask is None else attention_mask.unsqueeze(-1)
                v=(e*mask).sum(1)/mask.sum(1).clamp_min(1);v=self.net(v)
            else:v=self.net(x)
            if head=='positive':return torch.nn.functional.softplus(v)
            if head=='sigmoid':return torch.sigmoid(v)
            if head=='quantiles':return torch.cat((v[:,:1],v[:,:1]+torch.cumsum(torch.nn.functional.softplus(v[:,1:]),dim=1)),dim=1)
            return v
    return Network()


class Adapter:
    def __init__(self,spec,device,config,limits,work,roots,registrations):
        if spec.execution_view_only:raise EvaluationError('A derived evidence view is not a standalone executable predictor.','derived_view_not_executable')
        self.spec=spec;self.device_spec=device;self.config=config;self.limits=limits;self.work=work
        self.directory,self.files=capture_artifacts(spec,roots,work,limits)
        self.realization=devices.resolve(device,spec.adapter)
        self.realization.update(loads=1,batches=0,rows=0,retries=[],allocator_peaks={})
        observed=devices.capabilities()
        self.realization['runtime']={k:observed[k] for k in ('versions','python','platform')}
        runtime_files=[Path(__file__),Path(__file__).with_name('devices.py'),Path(__file__).with_name('contracts.py'),Path(__file__).parents[1]/'calibration.py',Path(__file__).parents[1]/'conformal.py']
        self.realization['runtime']['implementation_sha256']={str(p.relative_to(Path(__file__).parents[1])):hashlib.sha256(p.read_bytes()).hexdigest() for p in runtime_files}
        if observed['versions'].get('onnxruntime') and observed['versions'].get('onnxruntime-gpu'):raise EvaluationError('CPU and GPU ONNX distributions cannot coexist ambiguously.','predictor_dependency')
        self.registrations=registrations;self.profile=None;self.model=None
        for package,version in spec.runtime.items():
            import importlib.metadata
            try:observed=importlib.metadata.version(package)
            except importlib.metadata.PackageNotFoundError:observed=None
            if observed!=version:raise EvaluationError('Predictor runtime version differs.','predictor_runtime')
        try:self._load()
        except (ImportError,ModuleNotFoundError) as exc:raise EvaluationError('Install the explicitly declared optional model runtime.','predictor_dependency') from exc

    def _load(self):
        s=self.spec
        if s.adapter=='sklearn':
            import skops.io as sio
            unknown=sio.get_untrusted_types(file=self.directory/s.entry)
            # Standard estimators/pipelines are skops defaults. Never automatically
            # turn an untrusted-type inventory into an executable trust list.
            reviewed_types={'numpy.dtype','sklearn.ensemble._hist_gradient_boosting.predictor.TreePredictor'}
            if set(unknown)-reviewed_types:raise EvaluationError('Model contains types outside the standard skops trust policy.','untrusted_model_types')
            self.model=sio.load(self.directory/s.entry,trusted=sorted(set(unknown)&reviewed_types))
            if not type(self.model).__module__.startswith('sklearn.'):raise EvaluationError('Expected standard scikit-learn pipeline/estimator.','predictor_compatibility')
            final=getattr(self.model,'_final_estimator',self.model)
            admitted={'LinearRegression','Ridge','Lasso','ElasticNet','LogisticRegression','SVC','LinearSVC','SVR','LinearSVR',
                'DecisionTreeClassifier','DecisionTreeRegressor','RandomForestClassifier','RandomForestRegressor',
                'ExtraTreesClassifier','ExtraTreesRegressor','HistGradientBoostingClassifier','HistGradientBoostingRegressor'}
            from sklearn.base import is_classifier,is_regressor
            if type(final).__name__ not in admitted or not (is_regressor(final) if s.task.kind=='regression' else is_classifier(final)):raise EvaluationError('Estimator is outside the admitted task/model families.','predictor_compatibility')
            if hasattr(self.model,'feature_names_in_') and list(self.model.feature_names_in_)!=[f.column for f in s.inputs]:raise EvaluationError('Model feature order differs.','predictor_input_schema')
            self.realization['classes']=list(map(str,getattr(self.model,'classes_',[])))
            for b in s.outputs:
                if b.source not in {'predict','predict_proba','decision_function'} or not callable(getattr(self.model,b.source,None)):raise EvaluationError('Estimator output method is unavailable.','predictor_output_schema')
                if b.source=='predict_proba' and b.channel=='probabilities' and list(b.classes)!=self.realization['classes']:raise EvaluationError('Probability binding differs from estimator class order.','predictor_class_mapping')
                if b.source=='decision_function' and b.classes and list(b.classes)!=self.realization['classes']:raise EvaluationError('Score binding differs from estimator class order.','predictor_class_mapping')
                if b.source=='decision_function' and b.channel=='score' and not b.classes and b.meaning=='event_ranking' and len(self.realization['classes'])==2:
                    direction='higher' if self.realization['classes'][1]==s.task.positive_class else 'lower'
                    if b.direction!=direction:raise EvaluationError('Binary score orientation differs from producer semantics.','predictor_class_mapping')
        elif s.adapter=='torch':
            import torch
            from safetensors.torch import load_file
            dtype=devices.configure_torch(self.device_spec,self.config,self.realization)
            self.model=torch_architecture(s,self.registrations,allocation_bytes=min(self.limits.max_artifact_bytes,self.config.max_rss_bytes//3))
            parameters=sum(p.numel()*p.element_size() for p in self.model.parameters())
            if parameters>min(self.limits.max_artifact_bytes,self.config.max_rss_bytes//2):raise EvaluationError('Decoded model allocation exceeded.','model_limit')
            self.model.load_state_dict(load_file(str(self.directory/s.entry),device='cpu'),strict=True)
            self.model=self.model.to(device=self.realization['torch_device'],dtype=dtype).eval()
        elif s.adapter=='onnx':
            import onnx
            import onnxruntime as ort
            graph=onnx.load_model(str(self.directory/s.entry),load_external_data=False)
            if any(o.domain not in {'','ai.onnx','ai.onnx.ml'} for o in graph.opset_import):raise EvaluationError('Custom ONNX domains are not admitted.','onnx_operator')
            # Inspect tensors and nodes throughout nested graphs/functions, not
            # only top-level initializers, before native session construction.
            stack=[graph]
            while stack:
                message=stack.pop()
                if isinstance(message,onnx.NodeProto) and message.domain not in {'','ai.onnx','ai.onnx.ml'}:raise EvaluationError('Custom ONNX nodes are not admitted.','onnx_operator')
                if isinstance(message,onnx.TensorProto) and message.data_location==onnx.TensorProto.EXTERNAL:
                    external={item.key:item.value for item in message.external_data}
                    if set(external)-{'location','offset','length','checksum'} or not external.get('location'):raise EvaluationError('Unsupported ONNX external reference.','artifact_path')
                    location=external['location'];relative=Path(location)
                    if relative.is_absolute() or '..' in relative.parts or '\\' in location:raise EvaluationError('ONNX external references must be safe relative paths.','artifact_path')
                    identity=self.files.get(str(Path(s.entry).parent/relative))
                    if identity is None:raise EvaluationError('ONNX external data must be enumerated.','artifact_path')
                    try:offset=int(external.get('offset','0'));length=int(external.get('length',str(identity['bytes']-offset)))
                    except ValueError:raise EvaluationError('Invalid ONNX external byte range.','artifact_path') from None
                    if offset<0 or length<0 or offset+length>identity['bytes']:raise EvaluationError('ONNX external range exceeds captured bytes.','artifact_path')
                for descriptor,value in message.ListFields():
                    if descriptor.type==descriptor.TYPE_MESSAGE:
                        stack.extend(value if descriptor.is_repeated else [value])
            options=ort.SessionOptions();options.intra_op_num_threads=self.config.threads;options.inter_op_num_threads=1
            options.enable_profiling=True;options.profile_file_prefix=str(self.work.root/('onnx-profile-'+s.id))
            if self.realization['kind']=='cuda' and self.device_spec.onnx_mode=='strict':options.add_session_config_entry('session.disable_cpu_ep_fallback','1')
            ort.disable_telemetry_events()
            providers=devices.onnx_options(self.device_spec,self.realization)
            if any(p not in ort.get_available_providers() for p,_ in providers):raise EvaluationError('Requested ONNX provider is unavailable.','device_unavailable')
            self.model=ort.InferenceSession(str(self.directory/s.entry),sess_options=options,providers=providers)
            self.model.disable_fallback()
            if self.realization['kind']=='cuda' and 'CUDAExecutionProvider' not in self.model.get_providers():raise EvaluationError('CUDA provider did not initialize.','device_unavailable')
            self.realization['providers']=self.model.get_providers()
        elif s.adapter=='custom':
            factory,registration=host_factory(s.registration,self.registrations)
            self.model=factory(s.to_dict(),str(self.directory),copy.deepcopy(self.realization))
            self.realization['host_registration']=registration
        else:
            shape(s.architecture,{'values'})
            if 'values' not in s.architecture:raise EvaluationError('Constant predictor values are required.')

    def numeric(self,records):
        s=self.spec;p=s.preprocessing
        values=[]
        for record in records:
            row=[]
            for f in s.inputs:
                v=record.get(f.column)
                if v in f.missing_values or v is None:v=np.nan
                vocabulary=p.get('categories',{}).get(f.id)
                if vocabulary is not None:
                    row.extend([float(v==c) for c in vocabulary]+[float(v not in vocabulary)])
                else:
                    try:row.append(float(v))
                    except (ValueError,TypeError):raise EvaluationError('Input cannot be converted by frozen numeric preprocessing.','predictor_input_rejected')
            values.append(row)
        dtype=np.dtype(p.get('dtype',self.device_spec.precision))
        a=np.asarray(values,dtype=dtype)
        if 'fill' in p:a=np.where(np.isnan(a),np.asarray(p['fill'],dtype=dtype),a)
        if 'mean' in p:a=a-np.asarray(p['mean'],dtype=dtype)
        if 'scale' in p:
            scale=np.asarray(p['scale'],dtype=dtype)
            if np.any(scale<=0) or not np.isfinite(scale).all():raise EvaluationError('Invalid frozen preprocessing scale.')
            a=a/scale
        if not np.isfinite(a).all():raise EvaluationError('Numeric model inputs are nonfinite.','predictor_input_rejected')
        return a

    def prepare(self,records):
        s=self.spec;p=s.preprocessing;kind=p.get('kind','tabular')
        if kind=='tabular' and s.adapter=='sklearn':
            import pandas as pd
            values=[]
            for r in records:
                row={}
                for f in s.inputs:
                    v=r.get(f.column)
                    if v is None or v in f.missing_values:v=np.nan
                    elif f.kind in {'float','decimal','integer'}:
                        try:v=float(v)
                        except (ValueError,TypeError):raise EvaluationError('Invalid numerical model input.','predictor_input_rejected')
                    row[f.column]=v
                values.append(row)
            return pd.DataFrame(values,columns=[f.column for f in s.inputs])
        if kind=='text':
            if s.adapter=='sklearn':return [r.get(s.inputs[0].column,'') for r in records]
            from tokenizers import Tokenizer
            path=p.get('tokenizer')
            if path not in self.files:raise EvaluationError('Tokenizer must be an admitted artifact.')
            if not hasattr(self,'tokenizer'):self.tokenizer=Tokenizer.from_file(str(self.directory/path))
            encoded=self.tokenizer.encode_batch([str(r.get(s.inputs[0].column) or '') for r in records])
            self.token_work=getattr(self,'token_work',0)+sum(len(t.ids) for t in encoded)
            if self.token_work>self.limits.max_tokens_work:raise EvaluationError('Tokenizer work admission exceeded.','tokenizer_limit')
            ids=np.full((len(records),self.limits.max_tokens),p.get('padding_id',0),dtype=np.int64);mask=np.zeros_like(ids)
            coverage=[]
            for i,t in enumerate(encoded):
                n=min(len(t.ids),self.limits.max_tokens);ids[i,:n]=t.ids[:n];mask[i,:n]=1
                coverage.append({'original_tokens':len(t.ids),'retained_tokens':n,'truncated':n<len(t.ids)})
            self.realization.setdefault('text_coverage',{'tokens':0,'retained_tokens':0,'truncated_events':0})
            for c in coverage:
                self.realization['text_coverage']['tokens']+=c['original_tokens'];self.realization['text_coverage']['retained_tokens']+=c['retained_tokens'];self.realization['text_coverage']['truncated_events']+=c['truncated']
            return {'input_ids':ids,'attention_mask':mask}
        if kind=='image':
            from PIL import Image,ImageOps
            values=[]
            for r in records:
                v=r.get(s.inputs[0].column)
                if isinstance(v,np.ndarray):a=v
                else:
                    # Assets were captured by PreparedExecution, never opened from
                    # an unchecked browser/model-provided absolute path.
                    if not isinstance(v,str) or v not in getattr(self,'asset_snapshots',{}):raise EvaluationError('Image asset was not captured.','predictor_input_rejected')
                    with Image.open(self.asset_snapshots[v]) as image:
                        if image.width*image.height>self.limits.max_image_pixels:raise EvaluationError('Image pixel admission exceeded.','image_limit')
                        decoded=image.width*image.height
                        image=ImageOps.exif_transpose(image).convert('RGB')
                        if 'image_size' in p:
                            size=p['image_size']
                            if not isinstance(size,list) or len(size)!=2 or any(type(d) is not int or d<1 for d in size) or size[0]*size[1]>self.limits.max_image_pixels:raise EvaluationError('Resized image allocation exceeded.','image_limit')
                            image=image.resize(tuple(size))
                        a=np.asarray(image,dtype=np.float32)/255.
                        coverage=self.realization.setdefault('image_coverage',{'decoded_pixels':0,'model_pixels':0,'items':0,'color':'EXIF-oriented RGB [0,1] before declared normalization'})
                        coverage['decoded_pixels']+=decoded;coverage['model_pixels']+=image.width*image.height;coverage['items']+=1
                if a.ndim!=3 or a.shape[-1]!=3 or a.size>3*self.limits.max_image_pixels:raise EvaluationError('Invalid canonical image tensor.','predictor_input_rejected')
                a=(a-np.asarray(p.get('image_mean',[0,0,0])))/np.asarray(p.get('image_scale',[1,1,1]))
                values.append(a.transpose(2,0,1))
            return np.stack(values).astype(np.float32)
        if kind=='tensor':
            if not hasattr(self,'tensor_rows'):raise EvaluationError('Keyed tensor input was not aligned.','tensor_alignment')
            values=[]
            for r in records:
                original=self.tensor_rows.get(r.get('_cg6_event_key'))
                if original is None:raise EvaluationError('Tensor event is outside captured alignment.','tensor_alignment')
                supplied=r.get(s.inputs[0].column)
                if not isinstance(supplied,list):raise EvaluationError('Prepared tensor input is missing or malformed.','predictor_input_rejected')
                value=np.asarray(supplied,dtype=original.dtype)
                if value.shape!=original.shape or not np.isfinite(value).all():raise EvaluationError('Transformed tensor shape or values differ.','predictor_input_rejected')
                values.append(value)
            return np.stack(values)
        return self.numeric(records)

    def predict_raw(self,prepared,*,gradients=False):
        s=self.spec
        if s.adapter=='sklearn':
            from threadpoolctl import threadpool_limits
            with threadpool_limits(limits=self.config.threads):return {b.source:getattr(self.model,b.source)(prepared) for b in s.outputs}
        if s.adapter=='torch':
            import torch
            dtype=getattr(torch,self.device_spec.precision);device=self.realization['torch_device']
            def tensor(a):return torch.as_tensor(a,device=device,dtype=torch.long if np.asarray(a).dtype.kind in 'iu' else dtype)
            data={k:tensor(v) for k,v in prepared.items()} if isinstance(prepared,dict) else tensor(prepared)
            if gradients:
                if s.architecture.get('kind')=='host' and not self.realization.get('host_registration',self.registrations.get(s.registration,{})).get('gradients'):raise EvaluationError('Host architecture has no admitted gradient contract.','gradient_unavailable')
                if isinstance(data,dict) or not data.dtype.is_floating_point:raise EvaluationError('Full input path is not differentiable.','gradient_unavailable')
                data=data.detach().requires_grad_(True)
                return self.model(data),data
            with torch.inference_mode():value=self.model(**data) if isinstance(data,dict) else self.model(data)
            return {k:v.detach().cpu().numpy() for k,v in value.items()} if isinstance(value,dict) else {'output':value.detach().cpu().numpy()}
        if s.adapter=='onnx':
            names=[v.name for v in self.model.get_inputs()]
            data=prepared if isinstance(prepared,dict) else {s.preprocessing.get('tensor_name',names[0]):prepared}
            if set(data)!=set(names):raise EvaluationError('ONNX tensor bindings differ.','predictor_input_schema')
            return dict(zip([v.name for v in self.model.get_outputs()],self.model.run(None,data)))
        if s.adapter=='custom':return self.model.predict(prepared)
        n=len(next(iter(prepared.values()))) if isinstance(prepared,dict) else len(prepared)
        return {k:np.asarray([v]*n) for k,v in s.architecture['values'].items()}

    def predict(self,records):
        prepared=self.prepare(records)
        total=sum(v.nbytes for v in prepared.values()) if isinstance(prepared,dict) else getattr(prepared,'nbytes',0)
        if total>self.limits.batch_tensor_bytes:raise EvaluationError('Batch tensor allocation exceeded.','batch_tensor_limit')
        self.work.check('predictor inference',total)
        value=self.predict_raw(prepared)
        devices.synchronize(self.realization['kind'])
        self.realization['batches']+=1;self.realization['rows']+=len(records)
        evidence=devices.check_memory(self.realization,self.device_spec)
        for k,v in evidence.items():
            if type(v) is int:self.realization['allocator_peaks'][k]=max(v,self.realization['allocator_peaks'].get(k,0))
        return value

    def finish(self):
        if self.spec.adapter=='onnx':
            profile=Path(self.model.end_profiling())
            nodes=[v for v in json.loads(profile.read_text()) if v.get('cat')=='Node']
            counts={}
            for v in nodes:
                provider=v.get('args',{}).get('provider')
                if provider:counts[provider]=counts.get(provider,0)+1
            self.realization['observed_node_execution']=counts
            if self.realization['kind']=='cuda' and self.device_spec.onnx_mode=='strict' and counts.get('CPUExecutionProvider'):
                raise EvaluationError('Strict CUDA application executed CPU graph nodes.','onnx_placement')
            self.realization['cuda_nodes_observed']=bool(counts.get('CUDAExecutionProvider'))
        return copy.deepcopy(self.realization)


def normalize_outputs(raw,spec,n,tolerance):
    if not isinstance(raw,dict):raise EvaluationError('Predictor must return named outputs.','predictor_output_schema')
    result=[{'channels':{},'channel_failures':{},'execution':'completed'} for _ in range(n)]
    def original(value):
        if isinstance(value,np.ndarray):return [original(v) for v in value] if value.ndim else original(value.item())
        if isinstance(value,np.generic):return original(value.item())
        if isinstance(value,(list,tuple)):return [original(v) for v in value]
        if type(value) is float and not np.isfinite(value):return {'value':None,'value_state':'nan' if np.isnan(value) else 'positive_infinity' if value>0 else 'negative_infinity'}
        if value is None or type(value) in (str,bool,int,float):return value
        raise EvaluationError('Bound model outputs require numeric, label or state arrays.','predictor_output_schema')
    for source in {b.source for b in spec.outputs}:
        if source not in raw:raise EvaluationError('Bound model output is absent.','predictor_output_schema')
        values=np.asarray(raw[source])
        if values.ndim==0 or len(values)!=n:raise EvaluationError('Model output batch alignment differs.','predictor_output_schema')
        for i,value in enumerate(values):result[i].setdefault('original_outputs',{})[source]=original(value)
    for b in spec.outputs:
        if b.source not in raw:raise EvaluationError('Bound model output is absent.','predictor_output_schema')
        a=np.asarray(raw[b.source])
        if a.ndim==0 or len(a)!=n:raise EvaluationError('Model output batch alignment differs.','predictor_output_schema')
        if b.indices:
            if a.ndim!=2 or max(b.indices)>=a.shape[1]:raise EvaluationError('Model output indices differ.','predictor_output_schema')
            a=a[:,b.indices]
        if b.activation!='none':
            a=a.astype(float)
            if b.activation=='softmax':
                z=a-a.max(axis=1,keepdims=True);a=np.exp(z);a/=a.sum(axis=1,keepdims=True)
            else:a=np.exp(-np.logaddexp(0,-a))
        for i,v in enumerate(a):
            reason=None;value=None
            if b.channel in {'prediction','issuance'}:
                value=str(np.asarray(v).item())
                value=b.mapping.get(value,value)
                if value not in (spec.task.classes if b.channel=='prediction' else {'issued','abstained','failed','missing'}):reason='invalid_class_prediction' if b.channel=='prediction' else 'invalid_issuance_state'
            else:
                try:
                    values=np.asarray(v,dtype=float).reshape(-1)
                    if not np.isfinite(values).all():reason='nonfinite_output'
                    elif b.channel in {'probabilities','logits'} or b.channel=='score' and b.classes:
                        if len(values)!=len(b.classes):reason='class_output_shape'
                        elif len(b.classes)==1 and b.channel=='probabilities':
                            p=float(values[0]);value=[p if c==b.classes[0] else 1-p for c in spec.task.classes]
                        elif set(b.classes)!=set(spec.task.classes):reason='incomplete_class_mapping'
                        else:value=[float(values[b.classes.index(c)]) for c in spec.task.classes]
                        if value is not None and b.channel=='probabilities' and (min(value)<0 or max(value)>1 or abs(sum(value)-1)>tolerance):reason='invalid_probabilities'
                    elif b.channel in {'quantiles','samples'}:
                        value=values.tolist()
                        if b.channel=='quantiles':
                            if len(value)!=len(b.levels):reason='quantile_output_shape'
                            elif any(x>y for x,y in zip(value,value[1:])):
                                if spec.preprocessing.get('quantile_rearrange'):
                                    result[i].setdefault('postprocessing',[]).append({'channel':'quantiles','operation':'declared_quantile_rearrangement','original':list(value)})
                                    value=sorted(value)
                                else:reason='crossed_quantiles'
                    elif len(values)!=1:reason='scalar_output_shape'
                    else:value=float(values[0])
                    if b.channel=='scale' and value is not None:
                        floor=spec.preprocessing.get('scale_floor')
                        if floor is not None:
                            if value<float(floor):result[i].setdefault('postprocessing',[]).append({'channel':'scale','operation':'declared_scale_floor','original':value,'floor':floor})
                            value=max(value,float(floor))
                        if value<=0:reason='nonpositive_scale'
                    if b.channel=='risk' and value is not None and not 0<=value<=1:reason='invalid_risk_probability'
                except (ValueError,TypeError):reason='invalid_numeric_output'
            if reason:result[i]['channel_failures'][b.channel]=reason
            else:result[i]['channels'][b.channel]=value
    for output in result:
        c=output['channels'];decision=c.get('prediction')
        if c.get('issuance') in {'abstained','missing'}:output['channel_failures'].pop('prediction',None)
        if decision is None and spec.decision.rule=='probability_argmax' and c.get('probabilities'):
            p=c['probabilities'];winners=[i for i,v in enumerate(p) if v==max(p)]
            if len(winners)==1 or spec.decision.tie_policy=='class_order':decision=spec.task.classes[winners[0]]
        elif decision is None and spec.decision.rule=='probability_threshold' and c.get('probabilities'):
            decision=spec.task.positive_class if c['probabilities'][spec.task.classes.index(spec.task.positive_class)]>=spec.decision.threshold else next(c for c in spec.task.classes if c!=spec.task.positive_class)
        elif decision is None and spec.decision.rule=='score_threshold' and isinstance(c.get('score'),(int,float)):
            binding=next(b for b in spec.outputs if b.channel=='score');positive=c['score']>=spec.decision.threshold if binding.direction=='higher' else c['score']<=spec.decision.threshold
            decision=spec.task.positive_class if positive else next(c for c in spec.task.classes if c!=spec.task.positive_class)
        elif decision is None and spec.decision.rule=='score_argmax' and isinstance(c.get('score'),list):
            p=c['score'];winners=[i for i,v in enumerate(p) if v==max(p)]
            if len(winners)==1 or spec.decision.tie_policy=='class_order':decision=spec.task.classes[winners[0]]
        output['decision']=decision
        output['issuance']=c.get('issuance') or ('issued' if c.get('point') is not None or decision is not None else 'abstained' if spec.decision.rule!='none' and not output['channel_failures'] else 'missing')
    return result
