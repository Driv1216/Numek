"""Run with -I in a base-only installed-wheel environment, outside source imports."""
from pathlib import Path
import importlib.util,importlib.metadata,json,tempfile,csv,hashlib
import confidenceguard as cg
from confidenceguard.execution.devices import capabilities

ROOT=Path(__file__).resolve().parents[2]

def main():
    location=Path(cg.__file__).resolve();assert 'base312.nosync' in str(location) and 'site-packages' in str(location),location
    absent={p:importlib.util.find_spec(p) is None for p in ('torch','sklearn','skops','onnxruntime','safetensors')};assert all(absent.values()),absent
    temp=Path(tempfile.mkdtemp(prefix='cg6-wheel-'));source=temp/'input.csv'
    with source.open('w',newline='') as out:w=csv.writer(out);w.writerow(['id','x','y']);w.writerows((i,i/10,i/10) for i in range(8))
    task=cg.TaskDefinition('regression','Synthetic wheel target',units='items')
    predictor=cg.PredictorSpec('constant',task,'constant',(cg.FeatureField('x','x','float',role='model_input'),),(cg.OutputBinding('point'),),architecture={'values':{'output':.5}})
    spec=cg.ExecutionSpec((predictor,),(cg.SourceSpec('input',str(source)),),'input',('id',),'cg6-wheel',outcomes=cg.OutcomeSnapshotSpec('input','y',('id',)))
    result=cg.execute_predictor(spec,{'free_disk_bytes':1,'max_seconds':60,'max_details':2})
    result.generate_artifacts(temp/'report.html',format='html',json_path=temp/'report.json',audience='local')
    assert result.execution['status']=='completed' and len(result.private['output_rows'])==8
    for relative in ('static/execution-client.js','static/execution-panel.html','templates/execution_sections.html','schemas/contracts.json'):
        assert (location.parent/relative).is_file(),relative
    old=[]
    for directory in (ROOT/'validation/cg5/defect-corrections-20261105/reports',ROOT/'validation/cg5/review-corrections-20261104/reports-20261105/assessment',ROOT/'validation/cg5/review-corrections-20261104/reports-20261105/history'):
        for manifest in directory.glob('.confidenceguard-private/*/manifest.json'):
            for path in directory.glob('*.json'):
                try:value=json.loads(path.read_text())
                except (ValueError,UnicodeError):continue
                if not isinstance(value,dict) or value.get('analysis_id')!=manifest.parent.name or value.get('audience')=='shareable':continue
                opened=cg.EvaluationResult.from_dict(value,private=json.loads(manifest.read_text()))
                target=temp/('old-'+manifest.parent.name+'.html');opened.generate_artifacts(target,format='html',json_path=target.with_suffix('.json'),audience='shareable')
                old.append({'result':str(path.relative_to(ROOT)),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'analysis_id':value['analysis_id'],'reopened_without_model_or_solver_dependencies':True});break
    assert len(old)>=3,old
    receipt={'passed':True,'installed_location':str(location),'python':__import__('sys').version,'optional_ml_modules_absent':absent,
        'constant_execution_records':8,'actual_capabilities':capabilities(),'historical_artifacts':old,'no_source_imports':True}
    (ROOT/'validation/cg6/results/wheel-base-qualification.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps(receipt,indent=2))

if __name__=='__main__':main()
