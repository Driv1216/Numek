"""Retain already computed diagnostics and assess frozen explanations on features.

Validation only. No new learner, metric reducer, selection criterion or fitting.
Earlier trial files without these fields remain explicitly unrecorded.
"""
from collections import Counter
import copy
import hashlib
from pathlib import Path
import numpy as np

from confidenceguard.investigation_membership import apply,seal

VERSION='numek.cg4_gate_qualification_diagnostics/1.0'


def snapshot(result):
    panel=result.data['investigation'];chosen=set(panel['shortlist'])
    return {'schema_version':VERSION,'harness_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'selected_candidates':[copy.deepcopy({key:c[key] for key in ('id','strategy','head','membership_artifact','D','S','explanation','stability','selection_contribution','diagnostic_target_bindings') if key in c})
            for c in panel['candidates'] if c['id'] in chosen],
        'overlap':copy.deepcopy(panel['overlap']),
        'scope':'Recorded product D-perturbation diagnostics and D-fitted/S-assessed explanation evidence; no stability/recovery guarantee or universal fidelity pass label. Out-of-sample feature-only explanation assessment is separately recorded.'}


def explanation_fidelity(candidate,artifact,gate,features,representations,cache,check):
    explanation=candidate.get('explanation',{});kind=explanation.get('kind');n=len(gate['member'])
    if kind=='exact_predicate':
        if artifact['kind']!='structured':raise RuntimeError('A learned gate was incorrectly described as an exact predicate.')
        prediction=gate;basis='exact_definition_identity';defines=True
    elif kind=='approximate' and explanation.get('definition') is not None:
        definition=explanation['definition'];groups=definition.get('any_of',[definition.get('clauses',[])])
        fields=sorted({clause['field'] for group in groups for clause in group})
        surrogate=seal('structured',definition,features=fields)
        prediction=apply(surrogate,features,representations,cache=cache,check=check)
        basis='frozen_D_fitted_surrogate';defines=False
    else:return {'status':'unavailable','reason':explanation.get('reason') or 'no_frozen_surrogate_recorded','planned':n,
        'scope':'No replacement explanation was fitted on this population.'}
    known=np.asarray(gate['available'],bool);surrogate_known=np.asarray(prediction['available'],bool);joint=known&surrogate_known
    truth=np.asarray(gate['member'],bool)&joint;pred=np.asarray(prediction['member'],bool)&joint
    tp=int(np.count_nonzero(truth&pred));fp=int(np.count_nonzero(~truth&pred));fn=int(np.count_nonzero(truth&~pred));tn=int(np.count_nonzero(joint&~truth&~pred))
    return {'status':'measured','basis':basis,'defines_membership':defines,'planned':n,'gate_available':int(known.sum()),
        'surrogate_available':int(surrogate_known.sum()),'jointly_available':int(joint.sum()),'unavailable':n-int(joint.sum()),
        'gate_members_without_surrogate':int(np.count_nonzero(np.asarray(gate['member'],bool)&known&~surrogate_known)),
        'true_positive':tp,'false_positive':fp,'false_negative':fn,'true_negative':tn,
        'precision':tp/(tp+fp) if tp+fp else None,'recall':tp/(tp+fn) if tp+fn else None,
        'disagreement_rate':(fp+fn)/int(joint.sum()) if joint.any() else None,
        'surrogate_unavailable_reasons':dict(Counter(str(v) for v,a in zip(prediction['reason'],surrogate_known) if not a)),
        'scope':'Feature-only application of the already frozen definition; no labels or oracle truth used. Fidelity is conditional on joint applicability; all unavailable records stay visible against planned support.'}
