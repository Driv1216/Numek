"""Benchmarks share product decoders; references test their declared boundaries."""
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import sys

import numpy as np
import pytest

from confidenceguard.investigation_contracts import InvestigationLimits
from confidenceguard.investigation_membership import apply


def benchmark():
    directory=Path(__file__).resolve().parents[2]/'validation/cg4';sys.path.insert(0,str(directory))
    try:
        spec=importlib.util.spec_from_file_location('_cg4_baselines',directory/'compare_baselines.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
    finally:sys.path.pop(0)


def test_error_blind_centers_ignore_diagnostic_loss_and_freeze_nearest_membership():
    tool=benchmark();rng=np.random.default_rng(773);z=rng.normal(size=(256,2));eligible=np.ones(len(z),bool)
    reps={'v':{'id':'v','vectors':z,'available':eligible,'normalization':'none'}}
    limits=InvestigationLimits(minimum_discovery_support=1,stability_replicates=1)
    objective=SimpleNamespace(identity={'benchmark_reference':'fixed'})
    a={};b={}
    first=tool.geometric_baseline(reps,eligible,np.arange(len(z),dtype=float),objective,limits,a,lambda *args:None,clusters=True)
    second=tool.geometric_baseline(reps,eligible,-np.arange(len(z),dtype=float),objective,limits,b,lambda *args:None,clusters=True)
    assert a==b and [v['artifact'] for v in first]==[v['artifact'] for v in second]
    assert len(first)==16
    artifact=first[0]['artifact'];centers=np.array(json.loads(a[artifact['parameters']['geometry_digest']])['centers'])
    outside=np.array([[1e6,1e6]]);points=np.vstack((centers,outside))
    measured=apply(artifact,{}, {'v':{'vectors':points,'available':np.ones(len(points),bool)}},cache={'_models':a})
    expected=np.argmin(np.sum((points[:,None,:]-centers[None,:,:])**2,axis=2),axis=1)==artifact['parameters']['components'][0]
    assert np.array_equal(measured['member'][:-1],expected[:-1])
    assert measured['available'][:-1].all() and not measured['available'][-1]
    assert measured['reason'][-1]=='outside_frozen_geometric_support'


def test_comparison_has_a_fresh_panel_and_discloses_matched_selection_scope():
    protocol=benchmark().PROTOCOL
    assert protocol['seeds']['qualification']==[180000,180039]
    assert len(protocol['methods'])==6 and len(protocol['families'])==4
    assert 'one first selected gate' in protocol['selection']
    assert 'secondary' in protocol['selection'] and 'No H/oracle choice' in protocol['selection']


def test_paired_median_interval_uses_the_exact_binomial_count_bound():
    from math import comb
    tool=benchmark();gains=np.linspace(-1,1,40);result=tool.paired_gain_interval(gains)
    k=result['order_index_k'];bound=2*sum(comb(40,j) for j in range(k))/2**40
    next_bound=2*sum(comb(40,j) for j in range(k+1))/2**40
    assert bound<=.05/20<next_bound
    assert result['lower']==gains[k-1] and result['upper']==gains[40-k]
    assert result['binomial_error_bound']==pytest.approx(bound,abs=1e-15)
    assert tool.paired_gain_interval([.25]*40)['lower']==.25
    for bad in ([0.]*39,[float('nan')]*40,[2.]*40):
        with pytest.raises(ValueError):tool.paired_gain_interval(bad)
