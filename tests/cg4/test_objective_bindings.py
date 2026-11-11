"""Independent references for diagnostic targets and authoritative estimands."""
import csv
from dataclasses import replace
import math
import numpy as np
import pytest
from confidenceguard import InvestigationSpec
from confidenceguard.investigation import arguments,prepared
from confidenceguard.investigation_objectives import bind
from confidenceguard.investigation_contracts import FailureObjectiveSpec
from .helpers import binary


def test_classification_objectives_bind_conditional_targets_and_native_metrics(tmp_path):
    spec=binary(tmp_path);s,c,roots=arguments(spec,None,None)
    references={'error_rate':(.5,240),'accuracy':(.5,240),'false_negative_rate':(.5,120),'false_positive_rate':(.5,120),
                'precision':(.5,120),'recall':(.5,120),'specificity':(.5,120),'f1':(.5,240),'brier':(.34,240),'log_loss':(-.5*math.log(.8*.2),240),
                'calibration_residual':(0.,240),'roc_auc':(.5,240),'average_precision':(.5,240)}
    with prepared(s,c,roots) as p:
        for metric,(expected,support) in references.items():
            objective=bind(FailureObjectiveSpec('objective',metric,'model'),p.store)
            keys,eligible,target=objective.training('D')
            measured=objective.evaluate("cg4_role='D'",'D_objective_reference')
            assert measured['value']==pytest.approx(expected),metric
            assert measured['support']==support,metric
            if metric not in {'f1'}:assert int(eligible.sum())==support,metric
            if metric=='false_negative_rate':
                bykey=p.run_records['model']
                assert all(bykey[k]['y']=='1' for k,e in zip(keys,eligible) if e)
                assert all(v==float(bykey[k]['decision']!='1') for k,e,v in zip(keys,eligible,target) if e)
            if metric=='false_positive_rate':assert all(p.run_records['model'][k]['y']=='0' for k,e in zip(keys,eligible) if e)
            if metric=='precision':assert all(p.run_records['model'][k]['decision']=='1' for k,e in zip(keys,eligible) if e)


def test_regression_and_uncertainty_objectives_keep_units_sign_and_denominators(tmp_path):
    source=tmp_path/'regression.csv'
    with source.open('w',newline='') as stream:
        writer=csv.writer(stream);writer.writerow(['id','entity','role','y','point','lower','upper','x'])
        for i in range(720):
            bad=(i//3)%2;y=float(i%13);point=y+(2 if bad else -.5)
            writer.writerow([i,i,('D','S','H')[i%3],y,point,point-1,point+1,bad])
    spec=InvestigationSpec.from_dict({'evaluation':{'task':{'kind':'regression','outcome_definition':'Synthetic continuous target','units':'metres','material_error':1},
        'sources':[{'id':'data','path':str(source)}],'runs':[{'id':'model','source':'data','model':{'id':'fixture','version':'v1'},'key_columns':['id'],'entity_columns':['entity'],'prediction':'point',
        'intervals':[{'id':'interval','lower':'lower','upper':'upper','meaning':'prediction','coverage':.9,'central':True}]}],
        'outcomes':{'source':'data','column':'y','key_columns':['id']}},'roles':{'namespace':'regression-binding','unit':'entity','column':'role'},
        'features':[{'id':'context','availability':'at_decision','fields':[{'id':'x','column':'x','kind':'categorical'}]}],
        'objectives':[{'id':'bias','metric':'bias','run':'model','units':'metres','direction':'absolute','practical_threshold':.5}],'strategies':['structured']})
    s,c,roots=arguments(spec,None,None)
    expected={'bias':.75,'mae':1.25,'mse':2.125,'rmse':math.sqrt(2.125),'material_error_rate':.5,
              'interval_coverage':.5,'interval_miscoverage':.5,'interval_width':2.,'central_interval_score':12.}
    with prepared(s,c,roots) as p:
        for metric,reference in expected.items():
            units='metres^2' if metric=='mse' else 'fraction' if metric in {'material_error_rate','interval_coverage','interval_miscoverage'} else 'metres'
            objective=bind(FailureObjectiveSpec('objective',metric,'model',interval='interval' if metric.startswith('interval_') or metric=='central_interval_score' else None,units=units),p.store)
            keys,eligible,target=objective.training('D');measurement=objective.evaluate("cg4_role='D'",'D_objective_reference')
            assert measurement['value']==pytest.approx(reference),metric
            assert measurement['support']==240 and eligible.sum()==240,metric
            if metric!='rmse':assert np.mean(target[eligible])==pytest.approx(reference),metric
            if metric=='bias':assert set(target[eligible])=={-.5,2.}
