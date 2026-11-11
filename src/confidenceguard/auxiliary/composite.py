"""Job-local primary plus frozen auxiliary application, with one model load."""
from dataclasses import replace
import copy
import numpy as np

from ..contracts import EvaluationError
from ..execution.adapters import Adapter
from ..execution.contracts import DeviceSpec,OutputBinding
from .contracts import AuxiliaryArtifact


class AuxiliaryAdapter:
    def __init__(self,prepared,artifact,parent,registrations):
        self.artifact=AuxiliaryArtifact.from_dict(artifact);self.parent=parent;self.prepared=prepared;self.members=[]
        a=self.artifact;channel={'scale':'scale','quantiles':'quantiles','failure_risk':'risk'}[a.kind]
        binding=OutputBinding(channel,levels=tuple(a.target['levels']) if channel=='quantiles' else (),direction='lower',meaning='selection')
        self.spec=replace(parent.spec,id=a.id,outputs=tuple(b for b in parent.spec.outputs if b.channel!=channel)+(binding,),execution_view_only=True,
            provenance={**parent.spec.provenance,'auxiliary_artifact':a.artifact_digest,'primary_predictor':a.parent_digest})
        for p in a.predictors:
            device=prepared.spec.device if p.adapter in {'torch','custom'} else DeviceSpec()
            adapter=Adapter(p,device,prepared.config,prepared.spec.limits,prepared.work,prepared.roots,registrations)
            prepared.attach(adapter);self.members.append(adapter)
        self.realization={'kind':parent.realization['kind'],'loads':len(self.members),'composite':True,'parent_predictor':parent.spec.id,'rows':0,'retries':[]}
        self.realization['runtime']=parent.realization.get('runtime',{})
        if 'host_registration' in parent.realization:self.realization['host_registration']=parent.realization['host_registration']

    def predict_normalized(self,events):
        from ..execution.services import predict_batch
        from .services import augment
        primary=predict_batch(self.parent,events,self.prepared)
        enriched=[augment(e,o,self.artifact.target.get('prediction_features',()),self.artifact.target.get('vector_field')) for e,o in zip(events,primary)]
        parts=[predict_batch(m,enriched,self.prepared) for m in self.members];outputs=[]
        a=self.artifact;channel={'scale':'scale','quantiles':'quantiles','failure_risk':'risk'}[a.kind]
        for i,base in enumerate(primary):
            output=copy.deepcopy(base);values=[];reason=None;repairs=[]
            for member in a.target['members']:
                selected=[parts[j][i] for j in range(member['start'],member['start']+member['count'])]
                if any(p['execution']!='completed' or p['channel_failures'] for p in selected):reason='auxiliary_output_unavailable';break
                if a.kind=='quantiles':
                    v=selected[0]['channels'].get('quantiles') if len(selected)==1 else [p['channels']['point'] for p in selected]
                    if a.target.get('quantile_rearrange'):
                        if any(x>y for x,y in zip(v,v[1:])):repairs.append({'channel':channel,'operation':'declared_quantile_rearrangement','original':list(v)})
                        v=sorted(v)
                    if any(x>y for x,y in zip(v,v[1:])):reason='crossed_quantiles';break
                else:v=selected[0]['channels']['score' if a.kind=='failure_risk' else channel]
                values.append(v)
            if reason:output['channel_failures'][channel]=reason
            else:
                matrix=np.asarray(values,float);average=np.mean(matrix,axis=0)
                output['channels'][channel]=average.tolist() if average.ndim else float(average)
                output['ensemble']={'members':len(values),'variance':np.var(matrix,axis=0).tolist(),'interpretation':'variability; no calibrated uncertainty claim'}
            output.setdefault('postprocessing',[]).extend(repairs+[item for part in parts for item in part[i].get('postprocessing',[])])
            outputs.append(output)
        self.realization['rows']+=len(events);return outputs

    def finish(self):return {**self.realization,'auxiliary_members':[m.finish() for m in self.members]}


def attach_auxiliaries(prepared,adapters,registrations):
    for artifact in prepared.spec.auxiliaries:
        parent=next((a for a in adapters.values() if a.spec.predictor_digest==artifact['parent_digest']),None)
        if parent is None:raise EvaluationError('Attached auxiliary parent differs.','auxiliary_parent')
        composite=AuxiliaryAdapter(prepared,artifact,parent,registrations);adapters[composite.spec.id]=composite
    return adapters
