"""Locked validation-only finite-variance score panels; no product activation."""
import argparse
from collections import Counter
import hashlib
import importlib.metadata
import json
from pathlib import Path
import time

import numpy as np
from scipy.stats import binomtest
from threadpoolctl import threadpool_limits

import moment_candidate as method

SCENARIOS=('normal_contrast','exponential_contrast','lognormal_contrast',
           'heavy_member_light_comparator','light_member_heavy_comparator',
           'unequal_complete_clusters','paired_common_heavy',
           'normal_ceiling','exponential_ceiling','lognormal_ceiling')
NEGATIVES=('understated_heavy_variance','shared_unmodelled_shock')
PROTOCOL={
    'schema_version':'numek.cg4_fixed_time_variance_candidate_panel/1.0','method':method.METHOD,
    'scenarios':list(SCENARIOS),'development_seeds':[0,9],'qualification_seeds':[260000,260999],
    'independent_units':400,'study_alpha':.05,'family_sizes':[1,10,32],
    'family_assignment':'1,10,32 cyclically by seed within each unchanged scenario; every claim retains its full allocation.',
    'allocation':'alpha / frozen family size / elementary components, two tails inside each scalar interval. Four components for contrasts, two for ceilings.',
    'variance_bounds':'Exact unconditional unit-contribution population variances of the declared generator, plus 1e-12 for constant denominators. Never empirical variance, outcome extrema, or conditional loss variance used in place of zero-inflated unit contributions.',
    'sampling':'IID units with random Bernoulli(.5) membership. Paired units share heavy outcomes; complete IID entities use size-weighted sums. Event-weighted ratios remain the estimand.',
    'diagnostics':'For each scenario and frozen family size, exact binomial excess-noncoverage and directional-error diagnostics use unconditional trial denominators and allocated alpha or alpha/2. Holm across all 90 diagnostics only after every locked trial completes. Conditional diagnostics and refusal counts also reported.',
    'screen':'All 10000 qualification trials complete; no rejected error diagnostic; simultaneous exact availability lower bounds exceed .90 for all 30 scenario/family strata. These are implementation/operating-envelope screens, not a proof or power qualification.',
    'negative_controls':{'scenarios':list(NEGATIVES),'seeds':[270000,270199],
        'scope':'Deliberately false variance or independence assumptions; outside the guarantee. Preserve every interval/error. These are not counted as valid-envelope qualification, and the method cannot detect all such violations.'},
    'width':'Report interval widths and truth-relative errors; conservative or uninformative intervals do not establish useful power.',
    'remaining':'Full joint-family simulations, separately locked power/resource/full-pipeline qualification and explicit frozen assumption/provenance contracts would be required before any product proposal. No repair of previously frozen BCa hypotheses or evidence reuse guarantees.'}


def mixture_variance(mean,variance):
    return .5*variance+.25*mean*mean


def cluster_moments():
    sizes=np.arange(1,51,dtype=float);probability=np.r_[.2*.8**np.arange(49),.8**49]
    return float(probability@sizes),float(probability@(sizes*sizes))


def sample(seed,scenario):
    rng=np.random.Generator(np.random.PCG64(seed));n=PROTOCOL['independent_units']
    member=rng.random(n)<.5;ceiling=None;truth=0.;heavy_mean=float(np.exp(1.5**2/2))
    heavy_variance=float(np.expm1(1.5**2)*np.exp(1.5**2));mean=0.;variance=1.
    if scenario=='paired_common_heavy':
        common=rng.lognormal(0,1.5,n);reference=common+rng.normal(size=n);current=common+rng.normal(size=n)
        return np.column_stack((reference,np.ones(n),current,np.ones(n))),[heavy_variance+1,1e-12,heavy_variance+1,1e-12],truth,ceiling
    if scenario=='unequal_complete_clusters':
        sizes=np.minimum(50,rng.geometric(.2,n));values=sizes*rng.normal(size=n)+rng.normal(0,.2*np.sqrt(sizes),n)
        es,es2=cluster_moments();numerator_variance=.5*(es2+.04*es)
        denominator_variance=.5*es2-(.5*es)**2
        columns=np.column_stack((np.where(~member,values,0),np.where(~member,sizes,0),np.where(member,values,0),np.where(member,sizes,0)))
        return columns,[numerator_variance,denominator_variance]*2,truth,ceiling
    if scenario in {'heavy_member_light_comparator','light_member_heavy_comparator'}:
        heavy=rng.lognormal(0,1.5,n)-heavy_mean;light=rng.normal(size=n)
        heavy_member=scenario.startswith('heavy_member');values=np.where(member,heavy if heavy_member else light,light if heavy_member else heavy)
        member_variance=heavy_variance if heavy_member else 1.;comparison_variance=1. if heavy_member else heavy_variance
        bounds=[mixture_variance(0,comparison_variance),.25,mixture_variance(0,member_variance),.25]
    else:
        if scenario.startswith('normal_'):values=rng.normal(size=n)
        elif scenario.startswith('exponential_'):values=rng.exponential(size=n);mean=1.
        elif scenario.startswith('lognormal_'):values=rng.lognormal(0,1.5,n);mean=heavy_mean;variance=heavy_variance
        else:raise ValueError('Unregistered locked scenario.')
        if scenario.endswith('_ceiling'):
            member=np.ones(n,bool);ceiling=0.;truth=mean;bounds=[variance,1e-12]
        else:bounds=[mixture_variance(mean,variance),.25]*2
    return np.column_stack((np.where(~member,values,0),(~member).astype(float),np.where(member,values,0),member.astype(float))),bounds,truth,ceiling


def negative_sample(seed,scenario):
    rng=np.random.Generator(np.random.PCG64(seed));n=PROTOCOL['independent_units']
    if scenario=='understated_heavy_variance':
        x=rng.lognormal(0,1.5,n);truth=float(np.exp(1.5**2/2));bound=.001
    elif scenario=='shared_unmodelled_shock':
        x=rng.normal()+rng.normal(0,.1,n);truth=0.;bound=1.01
    else:raise ValueError('Unregistered negative control.')
    return np.column_stack((np.zeros((n,2)),x,np.ones(n))),[bound,1e-12],truth,0.


def summarize(rows,negative=False):
    groups=[];diagnostics=[];complete=len(rows)==(400 if negative else 10000)
    strata=[(s,m) for s in (NEGATIVES if negative else SCENARIOS) for m in ([1] if negative else (1,10,32))]
    ci=lambda k,n,confidence=.95:[float(v) for v in binomtest(k,n).proportion_ci(confidence_level=confidence,method='exact')] if n else None
    for scenario,family in strata:
        selected=[r for r in rows if r['scenario']==scenario and r['family_size']==family];n=len(selected)
        if not n:continue
        available=[r for r in selected if r['result']['status']=='available'];k=len(available)
        lower=sum(r['result']['lower']>r['truth'] for r in available);upper=sum(r['result']['upper']<r['truth'] for r in available)
        availability=ci(k,n,1-.05/len(strata));widths=[r['result']['upper']-r['result']['lower'] for r in available]
        groups.append({'scenario':scenario,'family_size':family,'trials':n,'available':k,
            'lower_above_truth':lower,'upper_below_truth':upper,'noncoverage':lower+upper,
            'noncoverage_MC95_unconditional':ci(lower+upper,n),'noncoverage_MC95_conditional':ci(lower+upper,k),
            'availability_simultaneous_MC_interval':availability,'median_width':float(np.median(widths)) if widths else None,
            'maximum_width':max(widths) if widths else None,
            'refusals':dict(Counter(r['result'].get('reason') for r in selected if r['result']['status']!='available')),
            'availability_criterion_met':bool(complete and availability[0]>.90)})
        for name,count,error in [('total',lower+upper,.05/family),('lower',lower,.025/family),('upper',upper,.025/family)]:
            diagnostics.append({'scenario':scenario,'family_size':family,'diagnostic':name,'count':count,'denominator':n,
                'allocated_error':error,'p':float(binomtest(count,n,error,alternative='greater').pvalue),'Holm_rejected':None})
    if complete and not negative:
        stopped=False;ordered=sorted(diagnostics,key=lambda d:d['p'])
        for i,d in enumerate(ordered):
            rejected=not stopped and d['p']<=.05/(len(ordered)-i);d['Holm_rejected']=bool(rejected);stopped|=not rejected
    return {'groups':groups,'diagnostics':diagnostics,'panel_complete':complete,'negative_control':negative,
        'screen_met':bool(not negative and complete and all(g['availability_criterion_met'] for g in groups) and not any(d['Holm_rejected'] for d in diagnostics)),
        'product_enabled':False,'scope':'Conditional fixed-time mathematics requires true declared bounds and IID complete units. Simulation does not verify an external population assumption, prove useful power, enable the product, or repair arbitrary evidence reuse.'}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--panel',choices=('development','qualification','negative'),required=True);parser.add_argument('--out',required=True);args=parser.parse_args()
    directory=Path(args.out);directory.mkdir(parents=True,exist_ok=True)
    sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
    profile={'protocol':PROTOCOL,'panel':args.panel,'harness_sha256':sha(__file__),'method_sha256':sha(method.__file__),
             'runtime':{name:importlib.metadata.version(name) for name in ('numpy','scipy','threadpoolctl')}}
    digest=hashlib.sha256(json.dumps(profile,sort_keys=True).encode()).hexdigest();path=directory/'profile.json'
    if path.exists() and json.loads(path.read_text())!=profile:raise RuntimeError('Preserve prior profile and evidence.')
    if not path.exists():path.write_text(json.dumps(profile,indent=2,sort_keys=True)+'\n')
    negative=args.panel=='negative';start,stop=PROTOCOL['negative_controls']['seeds'] if negative else PROTOCOL[args.panel+'_seeds'];rows=[];manifest={}
    with threadpool_limits(limits=1):
        for scenario in (NEGATIVES if negative else SCENARIOS):
            for seed in range(start,stop+1):
                path=directory/f'{scenario}-{seed}.json';family=1 if negative else (1,10,32)[(seed-start)%3]
                if path.exists():
                    row=json.loads(path.read_text())
                    if row['profile_digest']!=digest or row['scenario']!=scenario or row['seed']!=seed or row['family_size']!=family:raise RuntimeError('Existing trial changed identity.')
                else:
                    begun=time.monotonic();values,bounds,truth,ceiling=(negative_sample if negative else sample)(seed,scenario)
                    result=method.contrast_interval(values,variance_bounds=bounds,family_size=family,ceiling=ceiling)
                    row={'scenario':scenario,'seed':seed,'family_size':family,'truth':truth,'result':result,'profile_digest':digest,
                         'input_sha256':hashlib.sha256(values.astype('<f8').tobytes()).hexdigest(),'seconds':time.monotonic()-begun}
                    path.write_text(json.dumps(row,indent=2,sort_keys=True,allow_nan=False)+'\n')
                rows.append(row);manifest[path.name]=sha(path)
            print(json.dumps({'scenario':scenario,'rows':len(rows),'panel':args.panel}),flush=True)
    final={'profile':profile,'trial_manifest':manifest,**summarize(rows,negative)}
    path=directory/'summary.json'
    if path.exists() and json.loads(path.read_text())!=final:raise RuntimeError('Completed panel differs; preserve it.')
    if not path.exists():path.write_text(json.dumps(final,indent=2,sort_keys=True,allow_nan=False)+'\n')


if __name__=='__main__':main()
