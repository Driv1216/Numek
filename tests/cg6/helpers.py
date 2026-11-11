import csv
import hashlib
from pathlib import Path

CFG={'free_disk_bytes':1,'max_seconds':180,'max_details':4}


def execution(tmp_path,*,regression=False,n=60):
    from confidenceguard import (ExecutionSpec,PredictorSpec,OutputBinding,TaskDefinition,
                                FeatureField,SourceSpec,OutcomeSnapshotSpec,DecisionSpec,RoleSpec)
    path=tmp_path/'inputs.csv'
    with path.open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=['id','entity','x','z','y','role','batch'])
        writer.writeheader()
        for i in range(n):writer.writerow({'id':str(i),'entity':str(i),'x':i/n,'z':i%3,'y':i/n if regression else 'yes' if i%2 else 'no','role':('F','S','C','E')[i%4],'batch':i//10})
    task=TaskDefinition('regression','observed',units='items') if regression else TaskDefinition('binary_classification','observed',classes=('no','yes'),positive_class='yes')
    predictor=PredictorSpec('model',task,'constant',(FeatureField('x','x','float',role='model_input'),),
        (OutputBinding('point'),) if regression else (OutputBinding('probabilities',classes=('no','yes')),),
        architecture={'values':{'output':.5 if regression else [.25,.75]}},decision=DecisionSpec(rule='none' if regression else 'probability_argmax'))
    namespace='cg6-test-'+tmp_path.name
    return ExecutionSpec((predictor,),(SourceSpec('input',str(path)),),'input',('id',),namespace,entity_columns=('entity',),
        outcomes=OutcomeSnapshotSpec('input','y',('id',)),roles=RoleSpec(namespace=namespace,column='role',values={v:v for v in 'FSCE'},unit='entity'))


def file(path,name=None):
    from confidenceguard import ArtifactFile
    return ArtifactFile(name or Path(path).name,str(path),hashlib.sha256(Path(path).read_bytes()).hexdigest())
