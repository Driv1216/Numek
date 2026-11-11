"""Seal this correction pass without rewriting any prior CG6 receipt."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[3]
HERE=Path(__file__).resolve().parent


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path,value):path.write_text(json.dumps(value,indent=2)+'\n')


def main():
    baseline=json.loads((HERE/'baseline.json').read_text())
    missing=[name for name in baseline['source'] if not (ROOT/name).is_file()]
    changed=[name for name,h in baseline['source'].items() if (ROOT/name).is_file() and sha(ROOT/name)!=h]
    historical_changed=[name for name,h in baseline['historical_receipts'].items() if sha(ROOT/name)!=h]
    assert not missing and not historical_changed,(missing,historical_changed)
    assert not any(name.startswith('src/datatrust/') for name in changed)
    for path in (HERE/'baseline-documents').rglob('*.md'):
        original=str(path.relative_to(HERE/'baseline-documents'))
        assert sha(path)==baseline['source'][original],original
    runtime={str(p.relative_to(ROOT)):sha(p) for p in sorted((ROOT/'src').rglob('*'))
             if p.is_file() and p.suffix in {'.py','.js','.css','.html','.json'}}
    tests={str(p.relative_to(ROOT)):sha(p) for p in sorted((ROOT/'tests').rglob('*.py'))}
    identity=hashlib.sha256(json.dumps(runtime,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    gates=[]
    for label in ('integration-py313','compatibility-py312','lineage-py313','lineage-py312'):
        value=json.loads((HERE/(label+'.json')).read_text())
        assert value['passed'],label
        differences=[p for p,h in runtime.items() if value['runtime_source_sha256'].get(p)!=h]
        if label.startswith('lineage-'):
            assert not differences and value['test_source_sha256']==tests,label
        else:
            assert set(differences)=={'src/confidenceguard/execution/bridge.py','src/confidenceguard/execution/restatement.py'},(label,differences)
            assert all(tests.get(p)==h for p,h in value['test_source_sha256'].items()),label
            assert set(tests)-set(value['test_source_sha256'])=={'tests/cg6/test_review_auxiliary_lineage.py'},label
        assert value['log_sha256']==sha(HERE/(label+'.log')),label
        lines=(HERE/(label+'.log')).read_text().splitlines()
        summary=next(line.strip('= ') for line in reversed(lines) if re.search(r'\d+ passed.* in ',line))
        gates.append({'name':label,'summary':summary,'receipt_sha256':sha(HERE/(label+'.json')),
                      'elapsed_seconds':value['elapsed_seconds'],'changed_runtime_since_gate':differences,
                      'standing':'exact_final_source' if not differences else 'reused_except_two_R1_reuse_writers_covered_by_lineage_gates'})
    package=json.loads((HERE/'final-package-receipt.json').read_text())
    assert package['passed'] and {'src/'+k:v for k,v in package['files'].items()}==runtime
    assert sha(ROOT/package['wheel'])==package['wheel_sha256']
    report=HERE/'REVIEW_CORRECTIONS.md'
    report.write_text(report.read_text().replace('CORRECTED_SOURCE_DIGEST',identity))
    documents=[ROOT/p for p in (
        'docs/NUMEK_MASTER_CONTEXT.md','docs/CURRENT_STATE.md','docs/ARCHITECTURE.md',
        'docs/CG6_CONFIDENCEGUARD.md','validation/cg6/IMPLEMENTATION_REPORT.md',
        'validation/cg6/IMPLEMENTATION_STATUS.md','validation/cg6/VERIFICATION.md')]+[report]
    source={'files':runtime,'digest':identity,'test_source_sha256':tests,
        'verification_source_sha256':{str(p.relative_to(ROOT)):sha(p) for p in sorted(HERE.glob('*.py'))},
        'documentation_sha256':{str(p.relative_to(ROOT)):sha(p) for p in documents},
        'prior_reviewed_source':baseline['reviewed_source_digest'],
        'recorded_at':datetime.now(timezone.utc).isoformat()}
    write(HERE/'source-identity.json',source)
    write(HERE/'preservation.json',{'missing_baseline_files':missing,
        'changed_existing_files':changed,'datatrust_source_unchanged':True,
        'historical_receipts_unchanged':True,'baseline_sha256':sha(HERE/'baseline.json')})
    receipts={p.name:sha(p) for p in sorted(HERE.iterdir()) if p.is_file() and p.suffix in {'.json','.log','.md'} and p.name!='closure.json'}
    write(HERE/'closure.json',{'status':'R1-R6 implemented and engineering-verified',
        'runtime_source_digest':identity,'corrections':{f'R{i}':'implemented_and_verified' for i in range(1,7)},
        'gates':gates,'package_source_files_verified':package['source_files_verified'],
        'evidence_sha256':receipts,'unresolved_blocking_issues':[],
        'reused':'Unchanged scientific kernels/envelopes and historical lifecycle/interface/rendering evidence, with scoped correction-gate supplements; see REVIEW_CORRECTIONS.md.',
        'not_rerun':['655-test broad suite','CPU scientific positive-control campaign',
                     'cluster simulation campaign','21 performance profiles','browser campaign','PDF campaign','base-only installed-wheel campaign'],
        'cuda_runtime_qualification':'not_run_hardware_unavailable',
        'understanding_gate':'not_started','founder_acceptance':'not_claimed'})
    print(json.dumps({'status':'implemented_and_verified','runtime_source_digest':identity,'gates':gates},indent=2))


if __name__=='__main__':main()
