"""Repair summary serialization using intact locked trials; never resimulate."""
import argparse
import hashlib
import importlib.metadata
import inspect
import json
from pathlib import Path

import qualify_component_power as power


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--input',required=True);parser.add_argument('--out',required=True);args=parser.parse_args()
    source=Path(args.input);output=Path(args.out)
    if output.exists():raise RuntimeError('Preserve previous evidence; choose a new output.')
    profile=json.loads((source/'profile.json').read_text())
    if profile['protocol']!=power.PROTOCOL or profile['panel']!='qualification':raise RuntimeError('Original locked power protocol differs.')
    functions=(power.composed,power.approximate_interval,power._replicates,power.preflight,power.sample,power.power_sample,power.support)
    for function in functions:
        if hashlib.sha256(inspect.getsource(function).encode()).hexdigest()!=profile['function_sha256'][function.__name__]:raise RuntimeError('Simulation or input code changed; refuse evidence reuse.')
    if profile['runtime']!={name:importlib.metadata.version(name) for name in profile['runtime']}:raise RuntimeError('Scientific runtime versions differ.')
    profile_digest=hashlib.sha256(json.dumps(profile,sort_keys=True).encode()).hexdigest()
    rows=[];files={}
    for scenario in power.SCENARIOS:
        for seed in range(200000,201000):
            path=source/f'{scenario}-{seed}.json';row=json.loads(path.read_text())
            if row['scenario']!=scenario or row['seed']!=seed or row['profile_digest']!=profile_digest or row['result']['status'] not in {'available','unavailable'}:raise RuntimeError('Trial identity or execution differs.')
            rows.append(row);files[path.name]=sha(path)
    allowed=set(files)|{'profile.json'}
    if {p.name for p in source.glob('*.json')}!=allowed:raise RuntimeError('Unexpected or missing original trial records.')
    result={'profile':profile,**power.summary(rows,'qualification'),
        'aggregation_correction':{'reason':'NumPy Boolean in criterion_met prevented summary JSON writing after all 3000 trials completed.',
            'simulation_rerun':False,'changed_acceptance_criteria':False,'input_profile_sha256':sha(source/'profile.json'),
            'original_summary_function_sha256':profile['function_sha256']['summary'],
            'corrected_summary_function_sha256':hashlib.sha256(inspect.getsource(power.summary).encode()).hexdigest(),
            'trial_manifest':files,'scope':'All simulation/input function identities, runtime versions, seed identities and protocol match. Only aggregate JSON scalar normalization changed.'}}
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('x') as stream:json.dump(result,stream,sort_keys=True,indent=2,allow_nan=False);stream.write('\n')
    print(json.dumps({k:result[k] for k in ('panel_complete','rows')},indent=2))


if __name__=='__main__':main()
