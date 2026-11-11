"""Bound scientific evidence reuse to actual changed code and proposal inputs."""
import ast
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import numpy as np
from confidenceguard import discovery_rules
from confidenceguard.features import normalize
from confidenceguard.feature_contracts import FeatureField
from confidenceguard.investigation_contracts import InvestigationLimits

ROOT=Path(__file__).resolve().parents[4]
OLD=ROOT/'validation/cg4/source-capsules.nosync/2632e65e5b1b98a3902189fd67b441c35cf97b3239ffc36c78faca2f21997ab8'

def functions(path):
    return {n.name:ast.dump(n,include_attributes=False) for n in ast.parse(path.read_text()).body if isinstance(n,ast.FunctionDef)}

same={}
for relative,names in {
    'src/confidenceguard/confirmation.py':['elementary_count','binomial_interval','bounded_interval','finite_interval','orient','classify','f1_interval','calibration_interval','approximate_interval','_method_refusal'],
    'src/confidenceguard/discovery_boosted.py':['propose'],
    'src/confidenceguard/discovery_regions.py':['propose'],
    'src/confidenceguard/investigation_reconciliation.py':['reconcile','adverse_value','marginal_selection_evidence','explanation','stability'],
}.items():
    a,b=functions(OLD/relative),functions(ROOT/relative)
    same[relative]={name:a[name]==b[name] for name in names}
old={'__package__':'confidenceguard'}
exec(compile((OLD/'src/confidenceguard/discovery_rules.py').read_text(),str(OLD/'src/confidenceguard/discovery_rules.py'),'exec'),old)
parity=[]
for seed in (0,1,2):
    rng=np.random.default_rng(seed);n=240
    features={name:[normalize(value,FeatureField(name,name,kind)) for value in values] for name,kind,values in (
        ('number','float',[repr(float(x)) for x in rng.uniform(-1,1,n)]),
        ('category','categorical',[str(int(x)) for x in rng.integers(0,3,n)]),
        ('integer','integer',[str(int(x)) for x in rng.integers(0,2,n)]))}
    eligible=np.ones(n,bool);loss=rng.integers(0,2,n).astype(float)
    objective=SimpleNamespace(spec=SimpleNamespace(direction='higher',metric='error_rate'),identity={})
    limits=InvestigationLimits(max_nodes=3000,candidates_per_strategy=16,max_depth=3)
    before,bs=old['propose'](features,eligible,loss,objective,limits)
    after,as_=discovery_rules.propose(features,eligible,loss,objective,limits)
    equal=before==after and {k:v for k,v in bs.items() if k!='proposal_vocabulary'}=={k:v for k,v in as_.items() if k!='proposal_vocabulary'}
    parity.append({'seed':seed,'observed_cells':sum(len(v) for v in features.values()),'same_proposals_and_search_bounds':equal})
result={'unchanged_functions':same,'all_selected_functions_unchanged':all(all(v.values()) for v in same.values()),
    'all_observed_rule_parity':parity,
    'retained_claims':'Five 40/40 panels and finite/entity-arm/null references retain original profiles and bytes. No new empirical rate is inferred.',
    'changed_scope':'H1 changes custom-cutoff retention/reconstruction and affected hypothesis admission; H2 changes replay exposure identities and legacy provenance admission; L1 adds atoms only when no observed values exist. Old invalid-covariate campaigns remain invalid evidence.',
    'resource_scope':'Bulk codec and native membership code unchanged; historical capture metadata/lifecycle changed. Old measured timings/bytes are not current timing/capacity claims.',
    'all_passed':all(all(v.values()) for v in same.values()) and all(p['same_proposals_and_search_bounds'] for p in parity)}
Path(__file__).with_suffix('.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
assert result['all_passed']
