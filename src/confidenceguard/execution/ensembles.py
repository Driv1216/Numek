"""Supplied ensemble means and variability on complete common support."""
from dataclasses import replace
import copy
import numpy as np

from ..contracts import EvaluationError,DecisionSpec
from .contracts import OutputBinding,shape,strings


def validate_ensembles(ensembles,ids):
    ids=set(ids)
    for group in ensembles:
        shape(group,{'id','members','decision'},{'id','members'})
        from ..contracts import name
        name(group['id']);members=strings(group['members'],'ensemble members',True)
        if group['id'] in ids or not 2<=len(members)<=16 or set(members)-ids:raise EvaluationError('Ensembles require unique IDs and two to sixteen prior admitted members.')
        decision=DecisionSpec.from_dict(group.get('decision',{}))
        if decision.rule not in {'none','probability_argmax','probability_threshold'}:raise EvaluationError('An ensemble mean has no native score decision binding.')
        ids.add(group['id'])


def ensemble_semantics(ensembles):
    """Canonical effective definitions, including defaults and ordered members."""
    return [{'id':g['id'],'members':list(g['members']),
             'aggregation':'complete_common_support_arithmetic_mean_v1',
             'decision':DecisionSpec.from_dict(g.get('decision',{})).to_dict()}
            for g in ensembles]


def variability(parts,task):
    if task.kind=='regression':
        values=np.asarray([p['channels']['point'] for p in parts],float)
        return {'member_count':len(values),'standard_deviation':float(np.std(values)),'range':float(np.ptp(values)),
            'interpretation':'member variability; not a calibrated uncertainty distribution'}
    values=np.asarray([p['channels']['probabilities'] for p in parts],float);mean=values.mean(axis=0)
    def entropy(p):return float(-np.sum(p[p>0]*np.log(p[p>0])))
    votes=np.argmax(values,axis=1);counts=np.bincount(votes,minlength=len(task.classes))
    return {'member_count':len(parts),'probability_argmax_disagreement':1-float(counts.max()/len(parts)),
        'mean_probability_entropy':entropy(mean),'mean_member_entropy':float(np.mean([entropy(p) for p in values])),
        'interpretation':'probability-argmax diagnostic votes use declared class order for ties; neither consensus nor entropy is ground truth or calibrated uncertainty'}


class EnsembleAdapter:
    def __init__(self,group,members,prepared):
        self.members=members;self.prepared=prepared
        task=members[0].spec.task;channel='point' if task.kind=='regression' else 'probabilities'
        for m in members:
            if not any(b.channel==channel for b in m.spec.outputs):raise EvaluationError('Ensemble members require complete compatible point/probability outputs.','ensemble_output')
        binding=OutputBinding(channel,classes=task.classes if channel=='probabilities' else ())
        self.spec=replace(members[0].spec,id=group['id'],adapter='constant',entry=None,files=(),architecture={'values':{'output':0.}},outputs=(binding,),execution_view_only=True,
            decision=DecisionSpec.from_dict(group.get('decision',{})),provenance={'ensemble_members':[m.spec.predictor_digest for m in members],'aggregation':'complete_common_support_arithmetic_mean_v1'})
        self.realization={'kind':'cpu','loads':0,'batches':0,'rows':0,'retries':[],'runtime':members[0].realization.get('runtime',{}),'member_devices':{m.spec.id:m.realization['kind'] for m in members}}

    def predict_normalized(self,events):
        from .services import predict_batch
        from .adapters import normalize_outputs
        parts=[predict_batch(m,events,self.prepared) for m in self.members];outputs=[]
        channel=self.spec.outputs[0].channel
        for i in range(len(events)):
            members=[p[i] for p in parts]
            if any(m['execution']!='completed' or channel not in m['channels'] for m in members):outputs.append({'execution':'ensemble_member_unavailable','channels':{},'channel_failures':{},'decision':None});continue
            average=np.mean(np.asarray([m['channels'][channel] for m in members],float),axis=0)
            output=normalize_outputs({'output':np.asarray([average])},self.spec,1,self.prepared.config.probability_tolerance)[0]
            output['ensemble']={**variability(members,self.spec.task),'member_ids':[m.spec.id for m in self.members],'support':'all declared members'}
            outputs.append(output)
        self.realization['batches']+=1;self.realization['rows']+=len(events);return outputs

    def finish(self):return copy.deepcopy(self.realization)


def attach_ensembles(prepared,adapters):
    for group in prepared.spec.ensembles:adapters[group['id']]=EnsembleAdapter(group,[adapters[m] for m in group['members']],prepared)
