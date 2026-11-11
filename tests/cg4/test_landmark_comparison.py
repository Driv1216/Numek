"""Logical stopping bounds do not weaken the fixed positive promotion criterion."""
from pathlib import Path
import sys

import numpy as np
import pytest
from scipy.stats import binom

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'validation/cg4'))
from qualify_landmark_comparison import maximum_possible_median,paired_intervals


def test_futility_requires_unattainable_full_panel_median():
    assert maximum_possible_median([])==1.
    assert maximum_possible_median([-.5]*20)==.25
    assert maximum_possible_median([-.5]*21)==-.5
    assert maximum_possible_median([.10]*21)==.10  # equality can still pass
    for observed in ([.2,-.1,.05],[-.2]*21):
        upper=maximum_possible_median(observed)
        for fill in (-1.,0.,.3,1.):
            assert np.median([*observed,*([fill]*(40-len(observed)))])<=upper
    with pytest.raises(ValueError):maximum_possible_median([float('nan')])


def test_paired_uncertainty_allocations_and_conservative_tie_bounds():
    values=np.linspace(-.05,.5,40);result=paired_intervals(values,900)
    k=result['order_index_k'];ordered=np.sort(values)
    assert result['allocated_error']==.025
    assert 2*binom.cdf(k-1,40,.5)<=.025 and 2*binom.cdf(k,40,.5)>.025
    assert result['order_statistic_median_interval']==[ordered[k-1],ordered[40-k]]
    assert result['minimum_nominal_tail_draws']==250
    assert result['positive_lower_bounds']
    tied=paired_intervals(np.zeros(40),900)
    assert tied['paired_bootstrap_median_interval']==[0.,0.]
    assert tied['order_statistic_median_interval']==[0.,0.]
    assert not tied['positive_lower_bounds']
    with pytest.raises(ValueError):paired_intervals(values[:20],900)
