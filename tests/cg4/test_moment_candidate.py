"""Independent references for a validation-only known-variance candidate."""
from decimal import Decimal,localcontext
from pathlib import Path
import numpy as np
import pytest
from scipy.optimize import brentq


@pytest.fixture
def moment(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2]/'validation/cg4'))
    import moment_candidate
    return moment_candidate


def test_influence_matches_high_precision_and_required_exponential_envelope(moment):
    values=np.r_[-np.logspace(-12,150,80),0.,np.logspace(-12,150,80)]
    actual=moment.influence(values)
    with localcontext() as context:
        context.prec=80
        for value,observed in zip(values,actual):
            x=Decimal.from_float(float(value));upper=(1+x+x*x/2).ln();lower=-(1-x+x*x/2).ln()
            expected=upper if x>=0 else lower
            assert observed==pytest.approx(float(expected),rel=3e-15,abs=1e-15)
            assert float(lower)-1e-12<=observed<=float(upper)+1e-12


def test_endpoints_enclose_independently_solved_untranslated_score_roots(moment):
    rng=np.random.default_rng(114);values=rng.lognormal(0,1.1,200)
    variance=(np.exp(1.1**2)-1)*np.exp(1.1**2)
    result=moment.mean_interval(values,variance_bound=float(variance),alpha=.0125)
    assert result['status']=='available'
    lam=np.sqrt(2*np.log(2/.0125)/(len(values)*variance));threshold=len(values)*lam**2*variance/2+np.log(2/.0125)
    def score(mu):
        # Independent direct formula is safe for this moderate reference input.
        z=lam*(values-mu)
        return float(np.where(z>=0,np.log(1+z+z*z/2),-np.log(1-z+z*z/2)).sum())
    lower=brentq(lambda mu:score(mu)-threshold,-100,100,xtol=1e-13)
    upper=brentq(lambda mu:score(mu)+threshold,-100,100,xtol=1e-13)
    assert result['lower']<=lower and result['upper']>=upper
    assert result['lower']==pytest.approx(lower,abs=1e-9)
    assert result['upper']==pytest.approx(upper,abs=1e-9)
    transformed=moment.mean_interval(1000+7*values,variance_bound=float(49*variance),alpha=.0125)
    assert transformed['status']=='available'
    assert transformed['lower']==pytest.approx(1000+7*result['lower'],abs=1e-8)
    assert transformed['upper']==pytest.approx(1000+7*result['upper'],abs=1e-8)


def test_missing_assumptions_numerical_work_and_cancellation_are_not_hidden(moment):
    values=np.linspace(-2,2,30)
    assert moment.mean_interval(values,variance_bound=None)['reason']=='positive_known_variance_bound_required'
    assert moment.mean_interval(values,variance_bound=1.,work_budget=10)['reason']=='numerical_work_admission'
    assert moment.mean_interval(values,variance_bound=1.,max_iterations=1)['reason']=='root_resolution_budget'
    class Cancelled(Exception):pass
    def cancel(*args):raise Cancelled()
    with pytest.raises(Cancelled):moment.mean_interval(values,variance_bound=1.,check=cancel)


@pytest.mark.parametrize('transform', ['identity','lower','absolute','sqrt'])
def test_ratio_boxes_match_independent_component_roots_and_corner_enumeration(moment,transform):
    from itertools import product
    rng=np.random.default_rng(992);member=rng.random(2000)<.5
    loss=2+rng.exponential(size=len(member))
    values=np.column_stack((np.where(~member,loss,0),~member,np.where(member,loss,0),member))
    bounds=[3.75,.25,3.75,.25];allocation=.05/32/4
    result=moment.contrast_interval(values,variance_bounds=bounds,family_size=32,
                                   transform=transform,nonnegative_numerator=True)
    assert result['status']=='available' and result['product_enabled'] is False
    assert result['component_alpha']==allocation and result['elementary_intervals']==4
    intervals=[]
    for column,variance in enumerate(bounds):
        raw=values[:,column];lam=np.sqrt(2*np.log(2/allocation)/(len(raw)*variance))
        threshold=len(raw)*lam*lam*variance/2+np.log(2/allocation)
        def score(mu):
            z=lam*(raw-mu)
            return np.where(z>=0,np.log(1+z+z*z/2),-np.log(1-z+z*z/2)).sum()
        intervals.append((brentq(lambda mu:score(mu)-threshold,-100,100),
                          brentq(lambda mu:score(mu)+threshold,-100,100)))
    def box(numerator,denominator):
        ratios=[a/b for a,b in product(intervals[numerator],intervals[denominator])]
        lo,hi=min(ratios),max(ratios)
        if transform=='lower':return -hi,-lo
        if transform=='absolute':return (0 if lo<=0<=hi else min(abs(lo),abs(hi))),max(abs(lo),abs(hi))
        if transform=='sqrt':return np.sqrt(max(0,lo)),np.sqrt(max(0,hi))
        return lo,hi
    a=box(2,3);b=box(0,1)
    assert result['lower']<=a[0]-b[1]+1e-11
    assert result['upper']>=a[1]-b[0]-1e-11
    assert result['lower']==pytest.approx(a[0]-b[1],abs=1e-8)
    assert result['upper']==pytest.approx(a[1]-b[0],abs=1e-8)


def test_ceiling_allocation_and_unavailable_denominators_keep_the_frozen_family(moment):
    rng=np.random.default_rng(5);loss=rng.normal(2,1,1000)
    values=np.column_stack((np.zeros((1000,2)),loss,np.ones(1000)))
    result=moment.contrast_interval(values,variance_bounds=[1.,.01],family_size=32,ceiling=1.)
    assert result['status']=='available' and result['elementary_intervals']==2
    assert result['component_alpha']==.05/32/2
    assert set(result['components'])=={'2','3'}
    assert result['family_size']==32
    sparse=np.zeros((1000,4));sparse[0,2:]=1
    refused=moment.contrast_interval(sparse,variance_bounds=[1.,1.],family_size=32,ceiling=0.)
    assert refused['reason']=='population_denominator_not_separated_from_zero'
    assert refused['family_size']==32 and len(refused['components'])==2
    assert moment.contrast_interval(values,variance_bounds=[1.],ceiling=0.)['reason']=='all_required_variance_bounds_must_be_declared'
    assert moment.contrast_interval(values,variance_bounds=[None,1.],ceiling=0.)['reason']=='component_interval_unavailable'
    assert moment.contrast_interval(values,variance_bounds=[1.,1.],ceiling=0.,transform='sqrt')['reason']=='known_nonnegative_numerator_required'
    bad=values.copy();bad[0,3]=0
    assert moment.contrast_interval(bad,variance_bounds=[1.,1.],ceiling=0.)['reason']=='invalid_unit_denominator_contributions'
