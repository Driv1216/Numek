"""Data-only frozen membership. Unknown application is distinct from nonmembership."""
from dataclasses import dataclass,field
from functools import lru_cache
import copy
import json
import math
import tempfile
from pathlib import Path
import numpy as np
from .contracts import EvaluationError,digest,strict_json
from .features import value,learner_number,predicate_masks
from .execution_context import ctx

SCHEMA='confidenceguard.membership_artifact/1.0'


def seal(kind,parameters,*,features=(),representation=None,objective=None,models=None):
    packet={'schema_version':SCHEMA,'algorithm_version':kind+'_v1','kind':kind,'parameters':parameters,
            'features':list(features),'representation':representation,'objective_identity':objective}
    packet['artifact_digest']=digest(packet)
    return validate(packet,models=models)


def dependency_digests(artifact):
    p=artifact['parameters']
    return {p[k] for k in ('model_digest','geometry_digest') if k in p}


@lru_cache(maxsize=4)
def geometry_document(raw,expected):
    if not isinstance(raw,str) or len(raw)>64*1024**2 or digest(raw)!=expected:raise EvaluationError('Frozen geometry dependency differs.','membership_artifact_changed')
    geometry=strict_json(raw)
    if not isinstance(geometry,dict) or set(geometry)!={'schema_version','transform','centers'} or geometry['schema_version']!='confidenceguard.geometry/1.0':raise EvaluationError('Unsupported frozen geometry dependency.','membership_artifact')
    validate_geometry(geometry)
    return geometry


def validate_geometry(p):
    centers=np.asarray(p['centers'],dtype=float)
    if centers.ndim!=2 or not 0<len(centers)<=16384 or not 1<=centers.shape[1]<=16384 or not np.isfinite(centers).all():raise EvaluationError('Invalid landmarks.')
    transform=p['transform']
    if set(transform)!={'normalization','mean','components'} or transform['normalization'] not in {'none','l2'}:raise EvaluationError('Invalid frozen geometry transform.')
    if (transform['mean'] is None)!=(transform['components'] is None):raise EvaluationError('Incomplete frozen PCA transform.')
    if transform['mean'] is not None:
        mean=np.asarray(transform['mean'],float);components=np.asarray(transform['components'],float)
        if mean.ndim!=1 or not 1<=len(mean)<=16384 or components.shape!=(centers.shape[1],len(mean)) or not np.isfinite(mean).all() or not np.isfinite(components).all():raise EvaluationError('Invalid frozen PCA dimensions.')
    return centers


def validate(packet,max_bytes=64*1024**2,models=None):
    if not isinstance(packet,dict) or set(packet)!={'schema_version','algorithm_version','kind','parameters','features','representation','objective_identity','artifact_digest'}:
        raise EvaluationError('Invalid frozen membership structure.','membership_artifact')
    if packet['schema_version']!=SCHEMA or packet['kind'] not in {'structured','catboost','geometric','landmark'} or packet['algorithm_version']!=packet['kind']+'_v1':
        raise EvaluationError('Unsupported frozen membership.','membership_artifact')
    try:raw=json.dumps(packet,ensure_ascii=True,allow_nan=False)
    except (TypeError,ValueError):raise EvaluationError('Membership parameters must be finite JSON data.','membership_artifact') from None
    if len(raw)>max_bytes:raise EvaluationError('Membership artifact exceeds admission.','membership_artifact_limit')
    stack=[(packet,0)];elements=0
    while stack:
        item,depth=stack.pop();elements+=1
        if depth>32 or elements>4000000:raise EvaluationError('Membership artifact shape exceeds admission.','membership_artifact_limit')
        if isinstance(item,dict):stack.extend((v,depth+1) for v in item.values())
        elif isinstance(item,list):stack.extend((v,depth+1) for v in item)
        elif isinstance(item,float) and not math.isfinite(item):raise EvaluationError('Nonfinite membership parameter.')
    if packet['artifact_digest']!=digest({k:v for k,v in packet.items() if k!='artifact_digest'}):raise EvaluationError('Membership digest differs.','membership_artifact_changed')
    from .contracts import name
    p=packet['parameters'];kind=packet['kind'];fields=packet['features']
    if type(p) is not dict or type(fields) is not list or len(fields)>8192 or any(type(v) is not str for v in fields) or len(set(fields))!=len(fields):raise EvaluationError('Invalid membership feature declarations.','membership_artifact')
    for field in fields:name(field)
    if packet['objective_identity'] is not None and type(packet['objective_identity']) is not dict:raise EvaluationError('Invalid objective identity.','membership_artifact')
    if kind in {'geometric','landmark'}:
        name(packet['representation'])
        if fields:raise EvaluationError('Geometric artifacts use their declared representation.','membership_artifact')
    elif packet['representation'] is not None:raise EvaluationError('Tabular artifacts cannot imply an undeclared representation.','membership_artifact')
    if kind=='structured':
        if set(p)=={'clauses'}:groups=[p['clauses']]
        elif set(p)=={'any_of'} and isinstance(p['any_of'],list) and 1<=len(p['any_of'])<=3:groups=p['any_of']
        else:raise EvaluationError('Invalid structured gate.')
        # The direct empty conjunction is the total population gate. Empty
        # disjuncts remain invalid, preventing ambiguous redundant OR imports.
        if any(not isinstance(group,list) or not (0 if set(p)=={'clauses'} else 1)<=len(group)<=16 for group in groups):raise EvaluationError('Invalid structured conjunction.')
        for clause in (c for group in groups for c in group):
            if type(clause) is not dict:raise EvaluationError('Invalid structured predicate.')
            if set(clause)!={'field','op','value','kind'} or clause['op'] not in {'eq','le','gt','state','interval','not_in'} or clause['field'] not in packet['features']:raise EvaluationError('Invalid structured predicate.')
            if clause['kind'] not in {'categorical','boolean','integer','decimal','float','timestamp'}:raise EvaluationError('Unsupported structured feature kind.')
            if clause['op'] in {'interval','not_in'} and (not isinstance(clause['value'],list) or not 1<=len(clause['value'])<=128):raise EvaluationError('Invalid predicate set.')
            if clause['op']=='interval' and len(clause['value'])!=2:raise EvaluationError('Invalid predicate interval.')
            if clause['op']=='state':
                if clause['value'] not in {'missing','invalid'}:raise EvaluationError('Unsupported state predicate.')
            else:
                values=clause['value'] if clause['op'] in {'interval','not_in'} else [clause['value']]
                if any(type(v) is not str for v in values):raise EvaluationError('Exact lexical predicate bounds required.')
                try:decoded=[value({'state':'observed','kind':clause['kind'],'canonical':v}) for v in values]
                except (ArithmeticError,ValueError,TypeError):raise EvaluationError('Invalid canonical predicate bound.') from None
                if any(isinstance(v,float) and not math.isfinite(v) or hasattr(v,'is_finite') and not v.is_finite() for v in decoded):raise EvaluationError('Nonfinite predicate bound.')
                if clause['kind']=='boolean' and any(v not in {'true','false'} for v in values):raise EvaluationError('Invalid Boolean predicate bound.')
                if clause['op']=='interval' and not decoded[0]<decoded[1]:raise EvaluationError('Predicate interval must increase.')
        if set(fields)!={c['field'] for group in groups for c in group}:raise EvaluationError('Structured feature dependencies differ.')
    elif kind=='catboost':
        import re
        if set(p)!={'model_digest','columns','threshold','upper','head_sign','runtime'} or not isinstance(p['model_digest'],str) or not re.fullmatch('[0-9a-f]{64}',p['model_digest']):raise EvaluationError('Invalid diagnostic gate.')
        if models is not None:validate_model(models.get(p['model_digest']),p['model_digest'],max_bytes)
        if p['runtime']!='catboost/1.2.10-cpu' or not isinstance(p['columns'],list) or not 1<=len(p['columns'])<=8192:raise EvaluationError('Unsupported diagnostic runtime.')
        if any(set(c)!={'id','kind'} or c['id'] not in packet['features'] or c['kind'] not in {'categorical','boolean','integer','decimal','float','timestamp'} for c in p['columns']) or len({c['id'] for c in p['columns']})!=len(p['columns']):raise EvaluationError('Diagnostic feature order differs.')
        if p['head_sign'] not in {-1,1} or type(p['head_sign']) is not int or type(p['threshold']) not in {int,float} or not math.isfinite(p['threshold']) or p['upper'] is not None and (type(p['upper']) not in {int,float} or not math.isfinite(p['upper']) or p['upper']<=p['threshold']):raise EvaluationError('Invalid diagnostic score boundary.')
    else:
        required={'transform','centers','radii','inner','components','threshold','neighbors','bandwidth','support_radius'}
        if set(p)==required-{'transform','centers'}|{'geometry_digest'}:
            import re
            if not isinstance(p['geometry_digest'],str) or not re.fullmatch('[0-9a-f]{64}',p['geometry_digest']):raise EvaluationError('Invalid geometry dependency.')
            if models is not None:
                geometry=geometry_document(models.get(p['geometry_digest']),p['geometry_digest']);count=len(geometry['centers'])
            else:count=len(p['radii'])
        elif set(p)==required:count=len(validate_geometry(p))
        else:raise EvaluationError('Invalid geometric gate.')
        if not 0<count<=16384 or not isinstance(p['components'],list) or any(type(i) is not int or i<0 or i>=count for i in p['components']):raise EvaluationError('Invalid landmark component.')
        if type(p['neighbors']) is not int or not 0<p['neighbors']<=count:raise EvaluationError('Invalid neighbor count.')
        if any(type(p[k]) not in {int,float} or not math.isfinite(p[k]) for k in ('threshold','bandwidth','support_radius')) or not 0<=p['threshold']<=1 or p['bandwidth']<=0 or p['support_radius']<0:raise EvaluationError('Invalid geometric parameters.')
        if type(p['radii']) is not list or type(p['inner']) is not list or len(p['radii'])!=count or len(p['inner'])!=count or any(type(v) not in {int,float} or not math.isfinite(v) or v<0 for v in p['radii']+p['inner']):raise EvaluationError('Invalid geometric radii.')
        if any(not math.isfinite(float(v)*float(v)) for v in p['radii']+p['inner']+[p['support_radius']]) or not math.isfinite(2.*p['bandwidth']*p['bandwidth']):raise EvaluationError('Squared geometric parameters exceed the finite range.','geometry_numeric_range')
        if any(a>b for a,b in zip(p['inner'],p['radii'])):raise EvaluationError('Invalid geometric annulus.')
    return copy.deepcopy(packet)


@dataclass(frozen=True)
class MembershipArtifact:
    data: dict
    models: dict = field(default_factory=dict,repr=False)
    def __post_init__(self):
        if type(self.models) is not dict:raise EvaluationError('Data-only membership dependencies required.','membership_artifact')
        packet=validate(self.data)
        models={key:self.models[key] for key in dependency_digests(packet) if key in self.models}
        if any(type(v) is not str or len(v)>64*1024**2 for v in models.values()):raise EvaluationError('Membership dependency exceeds admission.','membership_artifact_limit')
        object.__setattr__(self,'data',validate(packet,models=models if models else None))
        object.__setattr__(self,'models',models)
    def to_dict(self):return copy.deepcopy(self.data)
    @property
    def artifact_digest(self):return self.data['artifact_digest']
    def apply(self,features,representations=None,*,config=None,limits=None,progress=None,cancel=None):
        """Apply an immutable gate in the same bounded worker as investigations."""
        from .investigation import configuration
        from .investigation_contracts import InvestigationLimits
        from . import compat
        config=configuration(config);limits=InvestigationLimits.from_dict(limits) if isinstance(limits,dict) else limits or InvestigationLimits()
        if not isinstance(limits,InvestigationLimits):raise EvaluationError('InvestigationLimits required.')
        packet=validate(self.data,models=self.models if self.models else None)
        features,representations,n=_application_inputs(packet,features,representations or {},config,limits)
        result=ctx.run(_membership_application,(packet,self.models,features,representations,n,config,limits),config,progress=progress,cancel=cancel)
        data=result.to_dict()
        return {'member':np.asarray(data['member'],bool),'available':np.asarray(data['available'],bool),
                'reason':np.asarray(data['reason'],object),
                'margin':np.asarray([np.nan if v is None else v for v in data['margin']],float) if data['margin'] is not None else None,
                'execution':result.execution}


def _application_inputs(packet,features,representations,config,limits):
    """Validate data before sending it to a native-operation worker."""
    if type(features) is not dict or type(representations) is not dict or len(features)>8192:raise EvaluationError('Bounded typed feature/representation dictionaries required.','membership_input')
    n=None;size=0;wanted={};represented={}
    params=packet['parameters']
    descriptions=(params.get('columns',[]) if packet['kind']=='catboost' else
        [clause for group in params.get('any_of',[params.get('clauses',[])]) for clause in group] if packet['kind']=='structured' else [])
    expected={d.get('field',d.get('id')):d['kind'] for d in descriptions}
    from .features import STATES
    kinds={'categorical','boolean','integer','decimal','float','timestamp','text','asset'}
    fields={'kind','state','lexical','canonical','available_ns','effective_ns','availability_state','source_type'}
    for name,cells in features.items():
        if not isinstance(name,str) or type(cells) not in {list,tuple}:raise EvaluationError('Typed feature rows required.','membership_input')
        if n is None:n=len(cells)
        if len(cells)!=n or n>config.max_rows:raise EvaluationError('Membership feature alignment or row limit differs.','membership_input')
        for cell in cells:
            if (type(cell) is not dict or set(cell)-fields or any(type(v) is not str and v is not None for v in cell.values()) or
                cell.get('kind') not in kinds or cell.get('state') not in STATES):raise EvaluationError('Invalid typed membership cell.','membership_input')
            if name in expected and cell['kind']!=expected[name]:raise EvaluationError('Typed application feature kind differs from its frozen gate.','membership_feature_contract')
            if any(len(v)>config.max_record_bytes for v in cell.values() if v is not None):raise EvaluationError('Membership cell exceeds record admission.','membership_input_memory')
            size+=512+sum(len(v.encode('utf-8',errors='surrogatepass')) for v in cell.values() if v is not None)
            if size>config.max_rss_bytes//4:raise EvaluationError('Typed membership input exceeds parent/worker memory admission.','membership_input_memory')
            if cell['state']=='observed':
                try:
                    observed=value(cell)
                    if cell['canonical'] is None or isinstance(observed,float) and not math.isfinite(observed) or hasattr(observed,'is_finite') and not observed.is_finite():raise ValueError('Nonfinite observed value')
                    if cell['kind']=='boolean' and cell['canonical'] not in {'true','false'}:raise ValueError('Invalid Boolean')
                except (ArithmeticError,ValueError,TypeError,KeyError):raise EvaluationError('Invalid observed membership value.','membership_input') from None
        if name in packet['features']:wanted[name]=cells
    for name,rep in representations.items():
        if not isinstance(name,str) or type(rep) is not dict:raise EvaluationError('Invalid membership representation.','membership_input')
        matrix=rep.get('vectors');known=rep.get('available')
        if type(matrix) not in {np.ndarray,np.memmap} or matrix.ndim!=2 or matrix.dtype.kind!='f' or matrix.dtype.itemsize not in (4,8) or not 1<=matrix.shape[1]<=limits.max_vector_dimensions:
            raise EvaluationError('Finite-dimension non-object vector matrix required.','membership_input')
        if n is None:n=len(matrix)
        if len(matrix)!=n or n>config.max_rows or type(known) is not np.ndarray or known.dtype!=np.dtype(bool) or known.shape!=(n,):raise EvaluationError('Membership representation alignment differs.','membership_input')
        reasons=rep.get('reason')
        if reasons is not None and (type(reasons) not in {list,tuple} or len(reasons)!=n or any(type(v) is not str or len(v)>512 for v in reasons)):raise EvaluationError('Invalid representation states.','membership_input')
        size+=matrix.nbytes*4+n*128
        if size>config.max_rss_bytes//2:raise EvaluationError('Membership representation exceeds parent/worker memory admission.','membership_input_memory')
        if name==packet['representation']:represented[name]={k:rep[k] for k in ('vectors','available','reason') if k in rep}
    # Even when a required field is absent, an admitted unrelated field can
    # establish row count; absence remains unavailable for every such row.
    return wanted,represented,n or 0


def _membership_application(packet,models,features,representations,n,config,limits,*,progress=None):
    from . import compat
    from .result import Inspection
    from threadpoolctl import threadpool_limits
    work=compat.workspace(config,128*1024**2,progress)
    try:
        with threadpool_limits(limits=config.threads):
            work.check('frozen membership application')
            measured=apply(packet,features,representations,cache={'_models':models,'_population_size':n,'_directory':str(work.root),
                '_max_distance_ops':limits.max_distance_operations,'_membership_memory_bytes':config.max_rss_bytes//3,'_threads':config.threads},check=work.check)
            margin=measured.get('margin')
            output={k:measured[k].tolist() for k in ('member','available','reason')}
            output['margin']=[float(v) if math.isfinite(v) else None for v in margin] if margin is not None else None
            work.check('frozen membership completed')
            return Inspection(output,{'status':'completed','peak_workspace_bytes':work.peak})
    finally:work.close()


def validate_model(model_json,expected,max_bytes=64*1024**2):
    if not isinstance(model_json,str) or len(model_json)>max_bytes or digest(model_json)!=expected:raise EvaluationError('Diagnostic model dependency differs.','membership_artifact_changed')
    model=strict_json(model_json);trees=model.get('oblivious_trees')
    if not isinstance(trees,list) or not 0<len(trees)<=4096:raise EvaluationError('Unsupported diagnostic tree shape.')
    if set(model)-{'features_info','model_info','oblivious_trees','scale_and_bias','ctr_data'}:raise EvaluationError('Unsupported diagnostic model fields.')
    def finite(values):return isinstance(values,list) and all(type(v) in {int,float} and math.isfinite(v) for v in values)
    for tree in trees:
        if not isinstance(tree,dict) or set(tree)-{'splits','leaf_values','leaf_weights'}:raise EvaluationError('Unsupported diagnostic tree fields.')
        splits=tree.get('splits') or [];leaves=tree.get('leaf_values');weights=tree.get('leaf_weights')
        if not isinstance(splits,list) or len(splits)>16 or not finite(leaves) or len(leaves)!=2**len(splits) or weights is not None and (not finite(weights) or len(weights)!=len(leaves) or any(v<0 for v in weights)):raise EvaluationError('Unsupported diagnostic tree shape.')
        for split in splits:
            if not isinstance(split,dict) or split.get('split_type') not in {'FloatFeature','OneHotFeature','OnlineCtr'}:raise EvaluationError('Unsupported diagnostic split.')
            for key,value in split.items():
                if key=='split_type':continue
                if type(value) not in {int,float} or not math.isfinite(value) or key.endswith('index') and (type(value) is not int or not 0<=value<4000000):raise EvaluationError('Invalid diagnostic split parameter.')
    features=model.get('features_info')
    if not isinstance(features,dict) or set(features)-{'float_features','categorical_features','ctrs','cat_features_hash'}:raise EvaluationError('Unsupported diagnostic feature metadata.')
    if any(not isinstance(v,list) or len(v)>4000000 for v in features.values()):raise EvaluationError('Diagnostic feature metadata exceeds admission.')
    flat=[]
    for key in ('float_features','categorical_features'):
        for feature in features.get(key,[]):
            index=feature.get('flat_feature_index');inner=feature.get('feature_index')
            if type(index) is not int or not 0<=index<16384 or type(inner) is not int or not 0<=inner<16384:raise EvaluationError('Invalid diagnostic feature index.')
            if key=='float_features' and (not finite(feature.get('borders')) or len(feature['borders'])>65536):raise EvaluationError('Invalid diagnostic numeric borders.')
            flat.append(index)
    if len(set(flat))!=len(flat):raise EvaluationError('Duplicate diagnostic feature index.')
    counts={'float_feature_index':len(features.get('float_features',[])),'cat_feature_index':len(features.get('categorical_features',[]))}
    def indices(element):
        for key,limit in counts.items():
            if key in element and (type(element[key]) is not int or not 0<=element[key]<limit):raise EvaluationError('Diagnostic feature reference is absent.')
    for tree in trees:
        for split in tree.get('splits') or []:indices(split)
    for ctr in features.get('ctrs',[]):
        if not isinstance(ctr,dict) or not finite(ctr.get('borders')) or len(ctr['borders'])>65536 or not isinstance(ctr.get('elements'),list) or not 1<=len(ctr['elements'])<=64:raise EvaluationError('Invalid diagnostic CTR description.')
        for element in ctr['elements']:indices(element)
    ctrs=model.get('ctr_data',{})
    if not isinstance(ctrs,dict) or len(ctrs)>65536:raise EvaluationError('Diagnostic CTR metadata exceeds admission.')
    cells=0
    for identifier,table in ctrs.items():
        if len(identifier)>65536 or not isinstance(table,dict) or set(table)!={'counter_denominator','hash_map','hash_stride'}:raise EvaluationError('Invalid diagnostic CTR table.')
        description=strict_json(identifier)
        if not isinstance(description,dict) or set(description)!={'identifier','type'} or not isinstance(description['identifier'],list) or not 1<=len(description['identifier'])<=64:raise EvaluationError('Invalid diagnostic CTR identifier.')
        for element in description['identifier']:indices(element)
        stride=table['hash_stride'];values=table['hash_map'];denominator=table['counter_denominator']
        if type(stride) is not int or not 2<=stride<=256 or not isinstance(values,list) or len(values)%stride or type(denominator) is not int or not 0<=denominator<=2**63-1:raise EvaluationError('Invalid diagnostic CTR shape.')
        cells+=len(values)
        if cells>4000000:raise EvaluationError('Diagnostic CTR cells exceed admission.')
        for offset,value in enumerate(values):
            if offset%stride==0:
                if not isinstance(value,str) or not value.isascii() or not value.isdecimal() or len(value)>20 or int(value)>2**64-1:raise EvaluationError('Invalid diagnostic categorical hash.')
            elif type(value) is not int or not 0<=value<=2**63-1:raise EvaluationError('Invalid diagnostic CTR count.')
    scale=model.get('scale_and_bias')
    if not isinstance(scale,list) or len(scale)!=2 or type(scale[0]) not in {int,float} or not math.isfinite(scale[0]) or not finite(scale[1]) or len(scale[1])!=1:raise EvaluationError('Unsupported diagnostic output shape.')
    return model_json


def tabular(features,columns):
    n=len(next(iter(features.values()))) if features else 0;matrix=[];available=np.ones(n,dtype=bool);categorical=[];conversion={}
    for descriptor in columns:
        fid=descriptor['id'];cells=features.get(fid)
        if cells is None:raise EvaluationError('Required diagnostic feature was not retained.','feature_not_retained')
        available&=np.array([c['state'] not in {'unavailable','not_retained'} for c in cells])
        if descriptor['kind'] in {'integer','decimal','float','timestamp'}:
            numbers=[];states=[]
            for cell in cells:
                number,state=learner_number(cell);numbers.append(float('nan') if number is None else number)
                states.append(json.dumps(['state',cell['state'],state],ensure_ascii=True,separators=(',',':')))
                conversion[state]=conversion.get(state,0)+1
            matrix.extend((numbers,states));categorical.append(len(matrix)-1)
        else:
            matrix.append([json.dumps(['value',c['lexical']] if c['state']=='observed' else ['state',c['state']],ensure_ascii=True,separators=(',',':')) for c in cells]);categorical.append(len(matrix)-1)
    return np.array(matrix,dtype=object).T,categorical,available,conversion


@lru_cache(maxsize=4)
def diagnostic_model(model_json):
    return load_diagnostic_model(model_json)


def load_diagnostic_model(model_json):
    import importlib.metadata
    if importlib.metadata.version('catboost')!='1.2.10':raise EvaluationError('Frozen diagnostics require CatBoost 1.2.10.','diagnostic_runtime')
    from catboost import CatBoost
    model=CatBoost()
    with tempfile.TemporaryDirectory(prefix='numek-cg4-model-') as directory:
        path=Path(directory)/'model.json';path.write_text(model_json,encoding='utf-8');model.load_model(str(path),format='json')
    return model


def transform_vectors(matrix,transform):
    z=np.asarray(matrix,dtype=np.float64)
    if transform['normalization']=='l2':
        # Scaling first avoids overflow/underflow for otherwise finite vectors.
        scale=np.max(np.abs(z),axis=1)
        with np.errstate(invalid='ignore',divide='ignore'):
            scaled=np.divide(z,scale[:,None],out=np.full_like(z,np.nan),where=scale[:,None]>0)
            norm=np.sqrt(np.sum(scaled*scaled,axis=1))
            z=np.divide(scaled,norm[:,None],out=np.full_like(z,np.nan),where=norm[:,None]>0)
    if transform.get('mean') is not None:z=(z-np.asarray(transform['mean']))@np.asarray(transform['components']).T
    return z


def distances(z,centers):
    # Direct blocked subtraction avoids cancellation on near-identical vectors.
    return np.sum((z[:,None,:]-centers[None,:,:])**2,axis=2)


def distance_block_rows(centers,dimensions,memory_budget=2*1024**3):
    # Subtraction and squaring can coexist; keep the temporary coordinate tensor
    # inside the admitted working-memory share even for a very wide vector.
    per_row=max(1,int(centers)*int(dimensions)*8*2)
    if per_row>memory_budget:raise EvaluationError('A distance row exceeds geometric working-memory admission.','membership_memory_limit')
    return max(1,min(128,memory_budget//per_row))


def distance_cache(z,centers,key,cache,check):
    if key in cache:return cache[key]
    work=len(z)*len(centers)*z.shape[1]
    if work>cache.get('_max_distance_ops',2000000000):raise EvaluationError('Membership distance work exceeds admission.','distance_work_limit')
    size=len(z)*len(centers)*8
    memory=cache.get('_membership_memory_bytes',2*1024**3)
    block=distance_block_rows(len(centers),z.shape[1],memory//2)
    if size>min(128*1024**2,memory//2):
        directory=cache.get('_directory')
        if directory is None:raise EvaluationError('Large geometric application requires owned bounded scratch.','membership_memory_limit')
        check('membership distance reservation',size)
        fd,path=tempfile.mkstemp(prefix='cg4-distances-',dir=directory)
        import os
        os.close(fd);out=np.memmap(path,dtype='<f8',mode='w+',shape=(len(z),len(centers)))
    else:out=np.empty((len(z),len(centers)),dtype=float)
    for start in range(0,len(z),block):
        out[start:start+block]=distances(z[start:start+block],centers);check('membership distances')
    cache[key]=out;return out


def apply(packet,features,representations,*,cache=None,check=lambda *args:None):
    p=packet['parameters'];kind=packet['kind'];cache=cache if cache is not None else {}
    n=len(next(iter(features.values()))) if features else len(next(iter(representations.values()))['vectors']) if representations else 0
    n=cache.get('_population_size',n);reasons=np.full(n,'',dtype=object);margin=None
    if kind=='structured':
        if 'any_of' in p:
            outcomes=[apply({**packet,'parameters':{'clauses':group}},features,representations,cache=cache,check=check) for group in p['any_of']]
            member=np.logical_or.reduce([o['member'] for o in outcomes]);available=member|np.logical_and.reduce([o['available'] for o in outcomes])
            return {'member':member,'available':available,'reason':np.where(available,'','required_feature_unavailable')}
        member=np.ones(n,dtype=bool);available=np.ones(n,dtype=bool)
        for clause in p['clauses']:
            cells=features.get(clause['field'])
            if cells is None:available[:]=False;reasons[:]='feature_not_retained';continue
            valid,mask=predicate_masks(cells,clause,cache if cache.get('_structured_masks_enabled') else None);available&=valid
            member&=mask
    elif kind=='catboost':
        if any(c['id'] not in features for c in p['columns']):return {'member':np.zeros(n,bool),'available':np.zeros(n,bool),'reason':np.full(n,'required_feature_not_retained',object),'margin':None}
        key='diagnostic:'+digest([p['model_digest'],p['columns']])
        if key not in cache:
            from catboost import Pool
            matrix,cats,available,_=tabular(features,p['columns'])
            model_json=validate_model(cache.get('_models',{}).get(p['model_digest']),p['model_digest'])
            score=np.asarray(diagnostic_model(model_json).predict(Pool(matrix,cat_features=cats),prediction_type='RawFormulaVal',thread_count=cache.get('_threads',2)),dtype=float).reshape(-1)
            cache[key]=(score,available)
        score,available=cache[key];member=score>=p['threshold']
        margin=score-p['threshold']
        if p['upper'] is not None:member&=score<p['upper']
        if p['upper'] is not None:margin=np.minimum(margin,p['upper']-score)
    else:
        rep=representations.get(packet['representation'])
        if rep is None:return {'member':np.zeros(n,bool),'available':np.zeros(n,bool),'reason':np.full(n,'representation_not_retained',object)}
        geometry=geometry_document(cache.get('_models',{}).get(p['geometry_digest']),p['geometry_digest']) if 'geometry_digest' in p else p
        if n*rep['vectors'].shape[1]*8*4>cache.get('_membership_memory_bytes',2*1024**3):raise EvaluationError('Representation transform exceeds geometric working-memory admission.','membership_transform_memory_limit')
        z=transform_vectors(rep['vectors'],geometry['transform']);available=np.array(rep['available'],dtype=bool)&np.isfinite(z).all(axis=1);member=np.zeros(n,bool);margin=np.full(n,np.nan)
        centers=np.asarray(geometry['centers'],dtype=float)
        key='distances:'+digest([packet['representation'],p.get('geometry_digest') or digest([geometry['transform'],geometry['centers']])])
        all_distances=distance_cache(z,centers,key,cache,check)
        for start in range(0,n,128):
            end=min(n,start+128);d2=all_distances[start:end];nearest=np.min(d2,axis=1)
            available[start:end]&=nearest<=p['support_radius']**2
            if kind=='geometric':
                mask=np.zeros(end-start,bool);local_margin=np.full(end-start,-np.inf)
                for j in p['components']:
                    mask|=(d2[:,j]<=p['radii'][j]**2)&(d2[:,j]>=p['inner'][j]**2)
                    distance=np.sqrt(d2[:,j]);part=p['radii'][j]-distance
                    if p['inner'][j]>0:part=np.minimum(part,distance-p['inner'][j])
                    local_margin=np.maximum(local_margin,part)
                margin[start:end]=local_margin
                member[start:end]=mask
            else:
                # Stable sorting supplies a reproducible landmark-index tie rule.
                ix=np.argsort(d2,axis=1,kind='stable')[:,:p['neighbors']]
                chosen=np.take_along_axis(d2,ix,axis=1);weights=np.exp(-(chosen-chosen[:,0,None])/(2*p['bandwidth']**2))
                local=np.isin(ix,p['components']);score=(weights*local).sum(axis=1)/weights.sum(axis=1)
                member[start:end]=score>=p['threshold']
                margin[start:end]=score-p['threshold']
            check('frozen geometric membership')
        known=np.asarray(rep['available'],bool)
        original=rep.get('reason',['representation_unavailable']*n)
        reasons[~known]=np.asarray(original,dtype=object)[~known]
        reasons[known&~np.isfinite(z).all(axis=1)]='invalid_representation_transform'
        reasons[known&np.isfinite(z).all(axis=1)&~available]='outside_frozen_geometric_support'
    reasons[(~available)&(reasons=='')]='required_feature_unavailable'
    return {'member':member&available,'available':available,'reason':reasons,'margin':margin}
