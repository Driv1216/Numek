import csv
from confidenceguard.investigation_contracts import InvestigationSpec


def binary(tmp_path,n=720,strategies=('structured',)):
    path=tmp_path/'predictions.csv'
    with path.open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=['id','entity','y','decision','p','x','z','role']);writer.writeheader()
        for i in range(n):
            x=(i//3)%2;z=(i//6)%2;y=(i//12)%2;error=x!=z;prediction=y^error
            writer.writerow({'id':str(i),'entity':str(i),'y':str(y),'decision':str(prediction),'p':'.8' if prediction else '.2','x':str(x),'z':str(z),'role':('D','S','H')[i%3]})
    return InvestigationSpec.from_dict({'evaluation':{'task':{'kind':'binary_classification','outcome_definition':'fixture','classes':['0','1'],'positive_class':'1'},
        'sources':[{'id':'data','path':str(path)}],'runs':[{'id':'model','source':'data','model':{'id':'fixture','version':'v1'},'key_columns':['id'],'entity_columns':['entity'],'prediction':'decision','probabilities':{'positive_column':'p'}}],
        'outcomes':{'source':'data','column':'y','key_columns':['id']}},
        'roles':{'namespace':'fixture-'+tmp_path.name,'unit':'entity','column':'role'},
        'features':[{'id':'context','availability':'at_decision','fields':[{'id':'x','column':'x','kind':'categorical'},{'id':'z','column':'z','kind':'categorical'}]}],
        'objectives':[{'id':'errors','metric':'error_rate','run':'model','practical_threshold':.1}],
        'strategies':list(strategies),'limits':{'max_nodes':10000,'max_depth':3,'candidates_per_strategy':16,'shortlist':3,'stability_replicates':1}})
