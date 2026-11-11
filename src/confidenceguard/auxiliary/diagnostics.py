"""Descriptive failure-risk ranking with whole-score ties and explicit support."""
import numpy as np


def risk_diagnostics(truth, probability):
    y=np.asarray(truth,float);p=np.asarray(probability,float)
    order=np.argsort(p,kind='stable');y=y[order];p=p[order]
    n=len(y);positives=float(y.sum());negatives=n-positives
    ends=np.r_[np.flatnonzero(p[1:]!=p[:-1])+1,n]
    start=0;negative_before=0.;concordant=0.;coverage=[]
    cumulative=np.cumsum(y)
    for end in ends:
        pos=float(y[start:end].sum());neg=end-start-pos
        concordant+=pos*(negative_before+.5*neg);negative_before+=neg
        coverage.append({'threshold':float(p[end-1]),'accepted':int(end),'coverage':float(end/n),
                         'failures':int(cumulative[end-1]),'risk':float(cumulative[end-1]/end)})
        start=end
    # Descending thresholds include every member of a tie together. This is
    # threshold average precision, rather than a tie-dependent event ordering.
    desc=np.argsort(-p,kind='stable');dy=y[desc];dp=p[desc]
    dend=np.r_[np.flatnonzero(dp[1:]!=dp[:-1])+1,n];cum=np.cumsum(dy);previous=0.;ap=0.
    for end in dend:
        mass=float(cum[end-1]);ap+=(mass-previous)*mass/end;previous=mass
    # Bound the display without changing the exact ranking calculations.
    indices=sorted(set(np.linspace(0,len(coverage)-1,min(101,len(coverage)),dtype=int).tolist()))
    return {'support':n,'failures':int(positives),'nonfailures':int(negatives),'prevalence':positives/n,
            'auroc':concordant/(positives*negatives) if positives and negatives else None,
            'average_precision':ap/positives if positives else None,
            'undefined_reason':'both_outcome_classes_required' if not positives or not negatives else None,
            'risk_coverage':[coverage[i] for i in indices],'tie_policy':'whole_equal_score_groups',
            'standing':'descriptive on eligible observed targets; no population or future-risk guarantee'}
