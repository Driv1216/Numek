"""Create a genuine old-format synthetic capture, then apply current safeguards.

No old fact is edited to manufacture a missing-marker case. The producer source
is an explicitly supplied, hash-verified earlier CG4 source capsule.
"""
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[2]


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def capture(root,expected,legacy_context=False):
    import confidenceguard
    from confidenceguard import ReliabilityWorkspace,WorkspaceConfig
    if not Path(confidenceguard.__file__).resolve().is_relative_to(expected):raise RuntimeError('Old capture imports escaped their recorded source.')
    for name,columns in [('predictions.csv',['id','entity','y','decision','when','available','status']),('features.csv',['id','status'])]:
        with (root/name).open('x',newline='') as stream:
            writer=csv.writer(stream);writer.writerow(columns)
            for i in range(720):
                y=(i//12)%2;error=(i//3)%2!=(i//6)%2
                writer.writerow([i,i,y,y^error,'2026-01-01T00:00:00Z','2026-01-02T00:00:00Z','observed' if error else 'final'] if name=='predictions.csv' else [i,'ready' if (i//11)%2 else 'held'])
    views=[{'id':'context','source':'data','availability':'at_decision','fields':[{'id':'status','column':'status','kind':'categorical'}]},
        {'id':'independent','source':'external','availability':'at_decision','fields':[{'id':'status','column':'status','kind':'categorical'}]}]
    evaluation={'task':{'kind':'binary_classification','classes':['0','1'],'positive_class':'1','outcome_definition':'Synthetic old-capture provenance fixture'},
        'sources':[{'id':'data','path':str(root/'predictions.csv')},{'id':'external','path':str(root/'features.csv')}],
        'runs':[{'id':'model','source':'data','model':{'id':'legacy-synthetic','version':'v1'},'key_columns':['id'],'entity_columns':['entity'],'prediction':'decision','prediction_at':{'column':'when'}}],
        'outcomes':{'source':'data','column':'y','key_columns':['id'],'status_column':'status','available_at':{'column':'available'}}}
    ws=ReliabilityWorkspace.initialize(root/'workspace',WorkspaceConfig(saving=True,free_disk_bytes=1))
    ws.ingest({'schema_version':'confidenceguard.prediction_batch_spec/2.0','namespace':'legacy-status-example',
        'outcome_definition_version':'v1','evaluation':evaluation,
        'bindings':[{'run':'model',**({'features':{'status':'categorical'}} if legacy_context else {})}],
        'feature_views':[] if legacy_context else views})
    features=list(ws.catalog.iter_facts('feature'))
    if len(features)!=(0 if legacy_context else 1440) or any('known_outcome_fields' in f['payload'] for f in features):
        raise RuntimeError('This producer did not create the required genuine legacy missing-marker case.')
    descriptor={'workspace':str(ws.path),'variant':ws.models()[0]['id'],'views':views[:1] if legacy_context else views,'feature_facts':len(features),
        'context_facts':sum(1 for _ in ws.catalog.iter_facts('context')),
        'old_import_path':str(Path(confidenceguard.__file__).relative_to(expected)),
        'objects':{str(p.relative_to(ws.path)):sha(p) for p in (ws.path/'objects').rglob('*') if p.is_file()}}
    (root/'capture.json').write_text(json.dumps(descriptor,indent=2,sort_keys=True)+'\n')


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--source-identity');parser.add_argument('--out')
    parser.add_argument('--capture-worker');parser.add_argument('--expected-source');args=parser.parse_args()
    # Fixed fixture mode is passed through the environment to the old producer;
    # it never changes analytical procedures or qualification acceptance targets.
    legacy_context=os.environ.get('NUMEK_CG4_LEGACY_CONTEXT')=='1'
    if args.capture_worker:
        capture(Path(args.capture_worker),Path(args.expected_source),legacy_context);return
    from run_locked_qualification import snapshot
    capsule,identity=snapshot(args.source_identity)
    from confidenceguard import ReliabilityWorkspace,InvestigationSpec,EvaluationError,freeze_hypotheses
    with tempfile.TemporaryDirectory(prefix='numek-cg4-legacy-status-',dir='/private/tmp') as temporary:
        root=Path(temporary)
        subprocess.run([sys.executable,'-B',str(Path(__file__).resolve()),'--capture-worker',str(root),'--expected-source',str(capsule)],
            cwd=capsule,env={**os.environ,'PYTHONPATH':str(capsule/'src')},check=True)
        descriptor=json.loads((root/'capture.json').read_text());ws=ReliabilityWorkspace(descriptor['workspace'])
        if not descriptor['objects'] or legacy_context and not descriptor['context_facts']:
            raise RuntimeError('The old capture contains no immutable evidence for this control.')
        spec=InvestigationSpec.from_dict({'name':'Legacy outcome-status contamination control',
            'history':{'workspace_path':str(ws.path),'selection':{'namespace':'legacy-status-example','variants':[descriptor['variant']],
                'as_of':'2026-02-01T00:00:00Z','windows':[{'id':'jan','start':'2026-01-01T00:00:00Z','end':'2026-02-01T00:00:00Z'}]}},
            'roles':{'namespace':'legacy-status-example','unit':'entity'},'features':descriptor['views'],
            'objectives':[{'id':'error','run':descriptor['variant'],'metric':'error_rate','practical_threshold':.1}],
            'strategies':['structured'],'limits':{'max_nodes':2000,'max_depth':3,'candidates_per_strategy':16,'stability_replicates':1}})
        result=ws.investigate(spec)
        from confidenceguard.investigation import arguments,prepared
        s,c,roots=arguments(spec,None,None)
        with prepared(s,c,roots) as p:
            recovered_keys=p.store.cg4_original_keys;recovered_sources=p.store.cg4_source_identities
            if len(p.records)!=720 or len(recovered_keys)!=720 or len(recovered_sources)!=720:
                raise RuntimeError('Original retained identities were not reconstructed for every fixture event.')
            if set(recovered_keys.values())!={json.dumps([str(i)],separators=(',',':')) for i in range(720)}:
                raise RuntimeError('Reconstructed lexical identities differ from the original keys.')
        if result.private['known_outcome_features']!=['context.status']:raise RuntimeError('Legacy origin was missed or an unrelated source was falsely blocked.')
        if not result.data['investigation']['shortlist']:raise RuntimeError('The contaminated discovery control proposed no hypothesis.')
        try:freeze_hypotheses(result)
        except EvaluationError as exc:
            if exc.code!='outcome_derived_membership':raise
            refusal=exc.code
        else:raise RuntimeError('Legacy outcome-derived membership incorrectly froze.')
        if any(sha(ws.path/p)!=h for p,h in descriptor['objects'].items()):raise RuntimeError('An original immutable object changed.')
        record={'schema_version':'numek.cg4_legacy_outcome_origin_check/1.0','producer_source_identity':identity,
            'capture_kind':'legacy_binding_context' if legacy_context else 'typed_feature_without_marker',
            'producer_manifest_sha256':sha(capsule/'source-manifest.json'),'old_feature_facts_without_marker':descriptor['feature_facts'],
            'old_context_facts':descriptor['context_facts'],
            'reconstructed_original_events':len(recovered_keys),'reconstructed_source_aliases_for_events':len(recovered_sources),
            'original_immutable_objects':len(descriptor['objects']),'original_objects_unchanged':True,
            'known_outcome_fields':result.private['known_outcome_features'],'unrelated_same_named_column_not_blocked':None if legacy_context else True,
            'unrelated_column_control_assessed':not legacy_context,
            'freeze_refusal':refusal,'formal_confirmation_performed':False,'harness_sha256':sha(Path(__file__)),
            'current_source_sha256':{name:sha(ROOT/name) for name in ['src/confidenceguard/features.py','src/confidenceguard/investigation_history.py']},
            'scope':'Synthetic backward-compatibility and positive-contamination control only. Old captures are actually generated by the recorded earlier code; no marker/fact edits, no H assessment, no inferred independence from missing metadata. Temporary raw evidence is not customer data.'}
        with Path(args.out).open('x') as stream:json.dump(record,stream,indent=2,sort_keys=True);stream.write('\n')
        print(json.dumps(record,sort_keys=True))


if __name__=='__main__':main()
