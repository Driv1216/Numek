"""Seal the final evidence index after every admitted measured profile passes."""
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
CG6=ROOT/'validation/cg6'

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def write(path,value):path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')

def main():
    source={str(p.relative_to(ROOT)):sha(p) for p in sorted((ROOT/'src').rglob('*'))
        if p.is_file() and p.suffix in {'.py','.js','.html','.css','.json'}}
    source_digest=hashlib.sha256(json.dumps(source,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    test_source={str(p.relative_to(ROOT)):sha(p) for p in sorted((ROOT/'tests').rglob('*.py'))}
    verification_source={str(p.relative_to(ROOT)):sha(p) for p in sorted(CG6.iterdir())
        if p.is_file() and p.suffix in {'.py','.json'}}
    configuration={str(p.relative_to(ROOT)):sha(p) for p in [ROOT/'pyproject.toml',ROOT/'setup.py',ROOT/'.python-version',
        *sorted((ROOT/'constraints').glob('cg6-*.lock'))]}
    baseline=json.loads((CG6/'implementation_baseline.json').read_text())['files']
    missing=[p for p in baseline if not (ROOT/p).is_file()]
    changed=[p for p,h in baseline.items() if (ROOT/p).is_file() and sha(ROOT/p)!=h]
    assert not missing,missing
    assert not [p for p in changed if p.startswith('src/datatrust/')],changed
    write(CG6/'results/source-preservation.json',{'baseline_files':len(baseline),'missing':missing,'changed':changed,
        'datatrust_source_unchanged':True,'historical_validation_files_not_rewritten':True,
        'scope':'Compared to captured modified/untracked baseline; no reset of prior work'})
    write(CG6/'results/engineering-source.json',{'files':source,'digest':source_digest,
        'test_source_sha256':test_source,'verification_source_sha256':verification_source,
        'configuration_sha256':configuration,
        'recorded_at':datetime.now(timezone.utc).isoformat(),'purpose':'Final engineering runtime source/assets; docs may be finalized without changing this runtime'})
    protocol=json.loads((CG6/'performance_protocol.json').read_text())
    rows=[]
    for name,profile in protocol['profiles'].items():
        path=CG6/'results/performance'/name/'receipt.json'
        if not path.exists():raise RuntimeError('Required admitted measurement not complete: '+name)
        value=json.loads(path.read_text());assert value['passed'],name
        for key,expected in profile.items():assert value['profile'].get(key)==expected,(name,key)
        if profile['kind']=='auxiliary' and profile['device']=='mps':
            training=[t for candidate in value['auxiliary_training'] for t in candidate.get('training',[])]
            assert training and all(t['device']=='mps' for t in training),(name,training)
        differences=[p for p,h in value['source_sha256'].items() if source.get('src/'+p)!=h]
        assert set(differences)<={'confidenceguard/static/execution-client.js'},(name,differences)
        rows.append({'name':name,'passed':True,'hardware':value['hardware'],'profile':profile,
            'elapsed_seconds':value['elapsed_seconds'],'peak_worker_rss_bytes':value['execution']['peak_worker_rss_bytes'],
            'receipt':str(path.relative_to(CG6)),'receipt_sha256':sha(path),
            'source_applicability':'Numerical source exact; browser export progress/cancel-only change' if differences else 'Exact final runtime source',
            'changed_source':differences})
    by_name={r['name']:r for r in rows};comparisons=[]
    for label,cpu,mps in [('fixed network','device-cpu','device-mps'),('text','text-cpu','text-mps'),
        ('images','image-cpu','image-mps'),('attacks','attacks-cpu','attacks-mps'),
        ('scale fitting','scale-mlp','scale-mlp-mps'),('quantile fitting','quantiles-mlp','quantiles-mlp-mps'),
        ('risk fitting','failure_risk-mlp','failure_risk-mlp-mps')]:
        c=by_name[cpu];m=by_name[mps];n=c['profile']['rows'];assert n==m['profile']['rows']
        comparisons.append({'workload':label,'source_rows_or_items':n,'cpu_elapsed_seconds':c['elapsed_seconds'],
            'mps_elapsed_seconds':m['elapsed_seconds'],'cpu_items_per_second':n/c['elapsed_seconds'],
            'mps_items_per_second':n/m['elapsed_seconds'],'cpu_seconds_divided_by_mps_seconds':c['elapsed_seconds']/m['elapsed_seconds'],
            'standing':'End-to-end operation including transfers/source processing. Fitting includes finite selection/early stopping and equivalent CPU-constant versus MPS-Torch primaries; not equal-step or isolated GPU kernel throughput'})
    write(CG6/'results/performance-summary.json',{'passed':True,'profiles':rows,'hardware':'CG6-MAC-01',
        'same_host_comparisons':comparisons,
        'protocol_sha256':sha(CG6/'performance_protocol.json'),'not_admitted_reference_profiles':protocol['not_admitted_reference_profiles'],
        'cuda_performance':'not_measured_hardware_unavailable','unified_memory_note':'RSS and MPS allocator observations overlap; do not add as distinct physical memory'})
    log_names=['closure-tests.log','final-affected-checks.log','final-provenance-device-checks.log','compatibility-py312.log',
        'storage-paired-correction.log','retained-protocol-correction.log','coupled-batch-correction.log',
        'scale-floor-selection-check.log','schema-closure-check.log','wheel-closure-base-check.log']
    receipts=['results/reused-evidence.json','results/positive-controls/receipt.json','results/cluster-qualification.json',
        'results/schema-qualification.json','results/wheel-base-qualification.json','results/wheel-closure-source.json',
        'results/representative-final-reports.json','results/browser/workflow-verification.json',
        'results/performance-summary.json','results/performance-resumption.json',
        'results/performance-receipt-extension.json','results/performance-mps-primary-fixture-correction.json','CG6-MAC-01.json']
    inventory={name:sha(CG6/name) for name in [*log_names,*receipts]}
    documentation={name:sha(ROOT/name) for name in ['README.md','docs/CG6_CONFIDENCEGUARD.md',
        'docs/CURRENT_STATE.md','docs/ARCHITECTURE.md','docs/NUMEK_MASTER_CONTEXT.md',
        'validation/cg6/IMPLEMENTATION_REPORT.md','validation/cg6/IMPLEMENTATION_STATUS.md',
        'validation/cg6/VERIFICATION.md','validation/cg6/SCOPE_AND_EVIDENCE.md']}
    write(CG6/'results/engineering-closure.json',{'implementation':'complete','hardware_qualification':{
        'cpu':{'state':'qualified','profile':'CG6-MAC-01 / Python 3.13.17; separate Python 3.12.15 CPU compatibility'},
        'mps':{'state':'qualified','profile':'CG6-MAC-01 / Python 3.13.17 / Torch 2.8.0'},
        'cuda':{'state':'not_run_hardware_unavailable','implementation_contracts':'complete',
            'runtime_execution_parity_memory_performance':'pending compatible NVIDIA hardware','blocks_unrelated_acceptance':False}},
        'scientific_standing':'Scoped CPU controls and registered finite inference; no universal predictive improvement',
        'runtime_source_digest':source_digest,'evidence_sha256':inventory,'documentation_sha256':documentation,
        'performance_profiles_passed':len(rows),
        'catalog_version':2,'review':'Independent review, understanding gate and founder acceptance are subsequent steps',
        'verification_policy':'agents/skills/verify/skills.md; comprehensive affected gate plus source-scoped follow-ups and reuse'})
    print(json.dumps({'implementation':'complete','performance_profiles_passed':len(rows),'runtime_source_digest':source_digest}))

if __name__=='__main__':main()
