"""Apply CG4 frozen membership without rediscovering region boundaries."""
import json
from collections import Counter
import numpy as np

from .. import compat
from ..contracts import EvaluationError
from ..feature_contracts import FeatureField
from ..features import normalize
from ..investigation_membership import MembershipArtifact,apply


def validate_region(raw,columns):
    from ..execution.contracts import shape
    shape(raw,{'id','artifact','fields','models','representation'},{'id','artifact','fields'})
    from ..contracts import name
    name(raw['id']);artifact=MembershipArtifact(raw['artifact'],raw.get('models',{}))
    for descriptor in raw['fields'].values():
        field=FeatureField.from_dict(descriptor)
        if field.column not in columns or field.outcome_derived or field.role=='retrospective':raise EvaluationError('Frozen region requires declared decision-time feature bindings.','region_features')
    if set(artifact.data['features'])-set(raw['fields']):raise EvaluationError('Frozen region feature mappings are incomplete.','region_features')
    if raw.get('representation'):
        shape(raw['representation'],{'field'},{'field'})
        if raw['representation']['field'] not in columns:raise EvaluationError('Frozen region representation is undeclared.')
    return artifact


def membership(region,records,unavailable,prepared):
    artifact=MembershipArtifact(region['artifact'],region.get('models',{}));features={};representations={}
    for key,descriptor in region['fields'].items():
        f=FeatureField.from_dict(descriptor);cells=[]
        for record,missing in zip(records,unavailable):
            cell=normalize(record.get(f.column),f)
            if f.column in missing:cell={**cell,'state':'unavailable','canonical':None}
            cells.append(cell)
        features[key]=cells
    if region.get('representation'):
        values=[];available=[]
        for record in records:
            v=record.get(region['representation']['field'])
            if isinstance(v,str):
                try:v=json.loads(v)
                except ValueError:v=None
            okay=isinstance(v,list) and bool(v) and all(type(x) in (int,float) and np.isfinite(x) for x in v)
            available.append(okay);values.append(v if okay else None)
        width=next((len(v) for v in values if v is not None),0)
        if width:
            valid=[okay and len(v)==width for v,okay in zip(values,available)]
            vectors=np.asarray([v if okay else [0.]*width for v,okay in zip(values,valid)],float)
            representations[artifact.data['representation']]={'vectors':vectors,'available':np.asarray(valid,bool)}
    cache={'_models':artifact.models,'_population_size':len(records),'_threads':prepared.config.threads,
        '_directory':prepared.work.root,'_membership_memory_bytes':prepared.config.max_rss_bytes//4}
    out=apply(artifact.data,features,representations,cache=cache,check=prepared.work.check)
    return ['member' if member else 'nonmember' if available else 'unavailable' for member,available in zip(out['member'],out['available'])]


def transitions(prepared,study):
    results=[]
    for region in study.regions:
        for view in prepared.views:
            if view['scope']=='original':continue
            counts=Counter();records=[];originals=[];unavailable=[]
            def flush():
                if not records:return
                a=membership(region,originals,unavailable,prepared);b=membership(region,records,unavailable,prepared)
                counts.update(zip(a,b));records.clear();originals.clear();unavailable.clear()
            for row in prepared.output_rows(view['id']):
                original=prepared.con.execute('SELECT payload FROM cg6_outputs WHERE view=? AND event_key=?',[view['predictor'].id,row['event_key']]).fetchone()
                if not original:raise EvaluationError('Frozen region root binding is absent.','region_alignment')
                records.append(row['input_record']);originals.append(json.loads(original[0])['input_record']);unavailable.append(row.get('unavailable_fields',[]))
                if len(records)>=512:flush()
            flush()
            results.append({'region':region['id'],'artifact_digest':region['artifact']['artifact_digest'],'predictor':view['predictor'].id,'scope':view['scope'],
                'transitions':[{'original':a,'transformed':b,'count':n} for (a,b),n in sorted(counts.items())],
                'scope_definition':'original frozen region versus transformed frozen membership; no boundary fitting'})
    return results
