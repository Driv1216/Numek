"""Independent algebra/reference checks for a disabled inference prototype."""
from pathlib import Path
import numpy as np
import pytest


@pytest.fixture
def candidate(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2]/'validation/cg4'))
    import studentized_candidate
    return studentized_candidate


def expanded_reference(values,weights,ceiling=None):
    sample=np.repeat(values,weights,axis=0);n=len(sample);mean=sample.mean(axis=0)
    right=mean[2]/mean[3]
    gradient=np.array([0.,0.,1/mean[3],-mean[2]/mean[3]**2])
    if ceiling is None:
        left=mean[0]/mean[1];gradient[:2]=[-1/mean[1],mean[0]/mean[1]**2]
    else:left=ceiling
    return right-left,float(np.sqrt(gradient@np.cov(sample,rowvar=False,ddof=1)@gradient/n))


def test_variance_matches_independently_expanded_resamples_including_pairing(candidate):
    rng=np.random.default_rng(17);n=120
    # Overlapping paired denominators and correlated loss terms.
    a=rng.normal(3,1,n);b=.6*a+rng.normal(0,.7,n);left=rng.random(n)<.8;right=rng.random(n)<.7
    values=np.column_stack((a*left,left,b*right,right));products=np.einsum('ni,nj->nij',values,values).reshape(n,16)
    for weights in [np.ones(n,dtype=int),*rng.multinomial(n,np.full(n,1/n),size=7)]:
        point,se,valid=candidate.estimates(weights@values,weights@products,n,[0.,0.])
        expected,expected_se=expanded_reference(values,weights)
        assert valid[0] and point[0]==pytest.approx(expected,abs=1e-12)
        assert se[0]==pytest.approx(expected_se,rel=1e-12)


def test_batching_preserves_draws_and_numerical_invariance(candidate):
    rng=np.random.default_rng(8);n=120;group=np.arange(n)<60;y=rng.normal(0,1,n)
    values=np.column_stack((y*~group,~group,y*group,group)).astype(float)
    first=candidate.studentized(values,replicates=1000,seed=33,batch_size=1)
    batch=candidate.studentized(values,replicates=1000,seed=33,batch_size=64)
    assert first['status']==batch['status']=='available'
    for key in ('lower','upper','estimate','standard_error'):assert first[key]==pytest.approx(batch[key],abs=1e-12)
    translated=values.copy();translated[:,0]+=1e6*translated[:,1];translated[:,2]+=1e6*translated[:,3]
    moved=candidate.studentized(translated,replicates=1000,seed=33,batch_size=64)
    assert moved['status']=='available'
    for key in ('lower','upper','standard_error'):assert moved[key]==pytest.approx(batch[key],abs=2e-9)
    scaled=values.copy();scaled[:,0]*=10;scaled[:,2]*=10
    larger=candidate.studentized(scaled,replicates=1000,seed=33)
    assert larger['lower']==pytest.approx(10*batch['lower'],abs=1e-12)
    assert larger['upper']==pytest.approx(10*batch['upper'],abs=1e-12)


def test_refusal_preserves_all_replicates_and_required_resolution(candidate):
    values=np.column_stack((np.zeros(40),np.ones(40),np.ones(40),np.ones(40)))
    assert candidate.studentized(values,replicates=20)['reason']=='insufficient_nominal_tail_resolution'
    assert candidate.studentized(values,replicates=1000)['reason']=='undefined_original_standard_error'
    values[0,2]=2
    result=candidate.studentized(values,replicates=1000,seed=3)
    assert result['status']=='unavailable' and result['invalid_replicates']>0
    assert result['reason']=='undefined_studentized_replicates' and result['completed_replicates']==1000
    counts=np.random.default_rng(3).multinomial(40,np.full(40,1/40),size=1000)[:,0]
    assert result['invalid_replicates']==int(((counts==0)|(counts==40)).sum())


@pytest.mark.parametrize('kind',['disjoint','paired','ceiling'])
def test_complete_intervals_match_independent_expanded_resampling(candidate,kind):
    rng=np.random.default_rng(88);n=40;a=rng.normal(3,1,n);b=.6*a+rng.normal(0,.7,n)
    left=np.arange(n)>=20 if kind=='disjoint' else np.ones(n,bool)
    right=~left if kind=='disjoint' else np.ones(n,bool)
    values=np.column_stack((a*left,left,b*right,right));ceiling=0. if kind=='ceiling' else None
    theta,se=expanded_reference(values,np.ones(n,dtype=int),ceiling)
    draws=np.random.default_rng(33).multinomial(n,np.full(n,1/n),size=2000)
    pivots=[]
    for weights in draws:
        point,scale=expanded_reference(values,weights,ceiling)
        pivots.append((point-theta)/scale)
    lo,hi=np.quantile(pivots,[.025,.975],method='linear')
    result=candidate.studentized(values,replicates=2000,seed=33,ceiling=ceiling)
    assert result['status']=='available'
    assert result['lower']==pytest.approx(theta-hi*se,rel=1e-11,abs=1e-11)
    assert result['upper']==pytest.approx(theta-lo*se,rel=1e-11,abs=1e-11)
