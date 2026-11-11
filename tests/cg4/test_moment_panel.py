"""Protect population assumptions and diagnostic denominators in the new prototype."""
from pathlib import Path
import numpy as np
import pytest


@pytest.fixture
def panel(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2]/'validation/cg4'))
    import qualify_moment
    return qualify_moment


def test_bounds_are_unconditional_unit_moments_and_complete_entity_totals(panel):
    assert panel.mixture_variance(3.,1.)==2.75
    # Independent tail-sum identities for truncated geometric first/second moments.
    es=sum(.8**(k-1) for k in range(1,51))
    es2=sum((2*k-1)*.8**(k-1) for k in range(1,51))
    assert panel.cluster_moments()==pytest.approx((es,es2))
    values,bounds,truth,ceiling=panel.sample(260000,'unequal_complete_clusters')
    assert len(values)==400 and truth==0 and ceiling is None
    assert bounds==pytest.approx([.5*es2+.02*es,.5*es2-.25*es**2]*2)
    assert np.all((values[:,1]>0)^(values[:,3]>0))
    assert np.all((values[:,1]+values[:,3])>=1)
    heavy_variance=float(np.expm1(2.25)*np.exp(2.25))
    _,bounds,_,_=panel.sample(260000,'heavy_member_light_comparator')
    assert bounds==pytest.approx([.5,.25,.5*heavy_variance,.25])
    _,bounds,_,_=panel.sample(260000,'paired_common_heavy')
    assert bounds==pytest.approx([heavy_variance+1,1e-12]*2)


def test_fresh_scenarios_are_deterministic_and_do_not_drop_conditional_zeroes(panel):
    for scenario in panel.SCENARIOS:
        a,b,truth,ceiling=panel.sample(260017,scenario);again=panel.sample(260017,scenario)
        assert np.array_equal(a,again[0]) and b==again[1]
        assert a.shape==(400,4) and np.isfinite(a).all()
        assert all(v>0 and np.isfinite(v) for v in b)
        assert len(b)==(2 if ceiling is not None else 4)
        if scenario!='paired_common_heavy' and ceiling is None:
            assert np.all((a[:,1]>0)^(a[:,3]>0))
            assert len(np.unique(a[:,3]>0))==2
            assert np.all(a[a[:,1]==0,0]==0) and np.all(a[a[:,3]==0,2]==0)


def test_refusal_and_negative_controls_never_count_as_successful_qualification(panel):
    rows=[{'scenario':'normal_contrast','family_size':32,'truth':0.,'result':{'status':'available','lower':1.,'upper':2.}},
          {'scenario':'normal_contrast','family_size':32,'truth':0.,'result':{'status':'unavailable','reason':'denominator'}}]
    summary=panel.summarize(rows);group=summary['groups'][0]
    assert group['trials']==2 and group['available']==1 and group['noncoverage']==1
    assert group['refusals']=={'denominator':1} and not summary['screen_met']
    assert all(d['denominator']==2 for d in summary['diagnostics'])
    assert summary['diagnostics'][0]['allocated_error']==.05/32
    negative=panel.summarize([{'scenario':'shared_unmodelled_shock','family_size':1,'truth':0.,
        'result':{'status':'available','lower':-1.,'upper':1.}}],negative=True)
    assert not negative['screen_met'] and all(d['Holm_rejected'] is None for d in negative['diagnostics'])
