"""Independent fitting/metric references, conformal experiments and canonical exports."""
import argparse
import csv
import hashlib
import importlib.metadata
import json
import math
from pathlib import Path
import platform
import sys
import time
import numpy as np


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def close(a,b,*,atol=1e-8,rtol=1e-6):
    if not np.allclose(a,b,atol=atol,rtol=rtol):raise AssertionError((a,b))


def references(spec,result):
    from scipy.optimize import minimize,minimize_scalar
    from scipy.special import expit,logsumexp
    from sklearn.isotonic import IsotonicRegression
    from sklearn.calibration import _SigmoidCalibration
    from sklearn.metrics import roc_auc_score,average_precision_score
    with Path(spec['evaluation']['sources'][0]['path']).open() as f:records=list(csv.DictReader(f))
    fit=[r for r in records if r['role']=='F'];test=[r for r in records if r['role']=='E']
    task=spec['evaluation']['task'];kind=task['kind'];checks=[]
    methods={m['id']:m for m in result.private['fitted_methods']}
    def metric(run,key):return next(m for m in result.data['measurements'] if m['run']==run and m['scope']=='overall' and m['metric']==key)
    def check(label,actual,expected,**tolerance):
        close(actual,expected,**tolerance);checks.append({'check':label,'maximum_absolute_difference':float(np.max(np.abs(np.asarray(actual)-np.asarray(expected))))})
    if kind=='regression':
        y=np.array([float(r['outcome']) for r in test]);mu=np.array([float(r['prediction']) for r in test])
        lo=np.array([float(r['q05']) for r in test]);hi=np.array([float(r['q95']) for r in test])
        check('native MAE',metric('original','mae')['value'],np.mean(abs(mu-y)))
        for level,column in [(.05,'q05'),(.5,'q50'),(.95,'q95')]:
            q=np.array([float(r[column]) for r in test]);res=y-q
            check('pinball '+str(level),metric('original','pinball@'+str(level))['value'],np.mean(np.where(res>=0,level*res,(level-1)*res)))
        score=hi-lo+20*np.maximum(lo-y,0)+20*np.maximum(y-hi,0)
        check('WIS',metric('original','wis')['value'],np.mean((.5*abs(y-mu)+.05*score)/1.5))
        samples={r['id']:[] for r in test}
        with Path(spec['evaluation']['sources'][1]['path']).open() as f:
            for r in csv.DictReader(f):
                if r['id'] in samples:samples[r['id']].append(float(r['sample']))
        crps=[]
        for r in test:
            x=np.array(samples[r['id']]);outcome=float(r['outcome'])
            crps.append(np.abs(x-outcome).mean()-.5*np.abs(x[:,None]-x[None,:]).mean())
        check('empirical CRPS independent quadratic oracle',metric('original','empirical_crps')['value'],np.mean(crps))
        for key,artifact in methods.items():
            definition=artifact['definition'];scores=[]
            cal=[r for r in records if r['role']=='C']
            for r in cal:
                residual=abs(float(r['outcome'])-float(r['prediction']))
                scores.append(residual if key=='split' else residual/float(r['scale']) if key=='normalized' else max(float(r['q05'])-float(r['outcome']),float(r['outcome'])-float(r['q95'])))
            for threshold in artifact['parameters']['thresholds']:
                from fractions import Fraction
                nominal=Fraction(threshold['coverage']);k=((len(cal)+1)*nominal.numerator+nominal.denominator-1)//nominal.denominator
                if k>len(cal):assert threshold['threshold']['value_state']=='positive_infinity'
                else:check(key+' exact threshold '+threshold['coverage'],threshold['threshold']['value'],sorted(scores)[k-1])
        return checks
    classes=task['classes'];k=len(classes);yfit=np.array([int(r['outcome']) for r in fit]);y=np.array([int(r['outcome']) for r in test])
    if k==2:
        pf=np.array([float(r['probability']) for r in fit]);pe=np.array([float(r['probability']) for r in test]);native=np.array([float(r['score']) for r in fit]);native_test=np.array([float(r['score']) for r in test])
        inputs=np.c_[1-pf,pf];test_inputs=np.c_[1-pe,pe]
        sigmoid=_SigmoidCalibration().fit(native,yfit)
        iso=IsotonicRegression(out_of_bounds='clip').fit(pf,yfit)
        for key,artifact in methods.items():
            if artifact['definition']['kind'] not in {'platt','isotonic','beta','temperature','identity'}:continue
            params=artifact['parameters']
            if key=='platt':
                a,b=params['coefficients'];pred=expit(a*(native_test/params['scalar_scale']-params['mean'])/params['sd']+b)
                check('Platt fitted map vs sklearn independent sigmoid',pred,sigmoid.predict(native_test),atol=5e-5,rtol=5e-5)
            elif key=='isotonic':
                pred=np.interp(pe,params['knots'],params['values']);check('PAVA vs sklearn isotonic',pred,iso.predict(pe),atol=1e-12)
            elif key=='beta':
                design=np.c_[np.log(pf),-np.log1p(-pf),np.ones(len(pf))]
                ridge=1e-6
                def objective(theta):
                    z=design@theta
                    return np.mean(np.logaddexp(0,z)-yfit*z)+ridge*np.sum((theta-[1,1,0])**2)
                reference=minimize(objective,[1.,1.,0.],bounds=[(0,None),(0,None),(None,None)],method='L-BFGS-B',options={'ftol':1e-13,'gtol':1e-9})
                a,b,c=params['coefficients'];pred=expit(a*np.log(pe)-b*np.log1p(-pe)+c)
                expected=expit(np.c_[np.log(pe),-np.log1p(-pe),np.ones(len(pe))]@reference.x)
                check('Beta vs independent finite-difference objective',pred,expected,atol=3e-5,rtol=3e-5)
            elif key=='temperature':pred=None
            else:pred=pe
            if key=='temperature':
                z=np.log(inputs);zt=np.log(test_inputs)
                objective=lambda t:np.mean(logsumexp(z/np.exp(t),axis=1)-z[np.arange(len(z)),yfit]/np.exp(t))
                ref=minimize_scalar(objective,bounds=(-5,5),method='bounded')
                check('Binary temperature vs independent scalar optimizer',params['temperature'],np.exp(ref.x),atol=1e-4,rtol=1e-4)
                lp=zt/params['temperature'];lp-=logsumexp(lp,axis=1,keepdims=True);pred=np.exp(lp[:,1])
            check(key+' Brier',metric(key,'brier')['value'],np.mean((pred-y)**2))
            if np.any((pred==0)&(y==1)|(pred==1)&(y==0)):assert metric(key,'log_loss')['value_state']=='positive_infinity'
            else:check(key+' log loss',metric(key,'log_loss')['value'],np.mean(-np.log(np.where(y==1,pred,1-pred))))
            check(key+' ROC AUC',metric(key,'roc_auc')['value'],roc_auc_score(y,pred))
            check(key+' average precision',metric(key,'average_precision')['value'],average_precision_score(y,pred))
    else:
        p=np.array([[float(r['p'+str(i)]) for i in range(k)] for r in fit]);pt=np.array([[float(r['p'+str(i)]) for i in range(k)] for r in test])
        for key in ('temperature','dirichlet'):
            params=methods[key]['parameters']
            if key=='temperature':
                z=np.array([[float(r['z'+str(i)]) for i in range(k)] for r in fit]);zt=np.array([[float(r['z'+str(i)]) for i in range(k)] for r in test])
                obj=lambda t:np.mean(logsumexp(z/np.exp(t),axis=1)-z[np.arange(len(z)),yfit]/np.exp(t))
                ref=minimize_scalar(obj,bounds=(-5,5),method='bounded');check('Multiclass temperature independent fit',params['temperature'],np.exp(ref.x),atol=1e-4,rtol=1e-4)
                lp=zt/params['temperature']
            else:
                anchor=np.eye(k)-np.ones((k,k))/k;features=np.log(p)
                def objective(theta):
                    w=theta[:k*k].reshape(k,k);b=theta[k*k:];z=features@w.T+b
                    return np.mean(logsumexp(z,axis=1)-z[np.arange(len(z)),yfit])+.01*(np.sum((w-anchor)**2)+np.sum(b*b))
                ref=minimize(objective,np.r_[anchor.ravel(),np.zeros(k)],method='BFGS',options={'gtol':1e-7})
                observed=np.r_[np.array(params['weights']).ravel(),params['intercepts']]
                check('Dirichlet independent convex objective optimum',objective(observed),objective(ref.x),atol=1e-7,rtol=1e-7)
                lp=np.log(pt)@np.array(params['weights']).T+params['intercepts']
            lp-=logsumexp(lp,axis=1,keepdims=True);pred=np.exp(lp)
            check(key+' multiclass log loss',metric(key,'log_loss')['value'],np.mean(-lp[np.arange(len(y)),y]))
            check(key+' multiclass unhalved Brier',metric(key,'brier')['value'],np.mean(np.sum((pred-np.eye(k)[y])**2,axis=1)))
    return checks


def conformal_experiment(trials=1200):
    from scipy.stats import binomtest
    from confidenceguard.method_contracts import MethodSpec
    from confidenceguard.conformal import class_scores,score,construct,value_state,rank
    rng=np.random.default_rng(27491);n=39;nominal=.9;results=[]
    for kind in ['lac','aps','raps','split','normalized','cqr']:
        method=MethodSpec(kind,kind,'original',input='point' if kind=='split' else 'normalized' if kind=='normalized' else 'quantiles' if kind=='cqr' else 'probabilities',penalty=.05,k_reg=1)
        covered=0;efficiency=[]
        for _ in range(trials):
            if kind in {'lac','aps','raps'}:
                p=rng.dirichlet([.4,.8,1.2],n+1);y=np.array([rng.choice(3,p=v) for v in p])
                scores=score(method,p=p[:-1],y=y[:-1]);q=sorted(scores)[math.ceil((n+1)*nominal)-1]
                output=construct(method,{'threshold':value_state(q)},p=p[-1]);covered+=int(y[-1] in output['members']);efficiency.append(output['size'])
            else:
                scale=rng.uniform(.2,2,n+1);y=scale*rng.normal(size=n+1);mu=np.zeros(n+1);lo=-1.5*scale;hi=1.5*scale
                scores=score(method,y=y[:-1],point=mu[:-1],scale=scale[:-1],lower=lo[:-1],upper=hi[:-1]);q=sorted(scores)[math.ceil((n+1)*nominal)-1]
                output=construct(method,{'threshold':value_state(q)},point=0.,scale=scale[-1],lower=lo[-1],upper=hi[-1])
                yes=output['state']=='unbounded' or output['state']=='finite' and output['lower']['value']<=y[-1]<=output['upper']['value'];covered+=int(yes);efficiency.append(output['width']['value'])
        test=binomtest(covered,trials,p=nominal,alternative='less')
        assert test.pvalue>1e-4,(kind,covered,trials,test.pvalue)
        results.append({'method':kind,'trials':trials,'one_future_event_per_independent_calibration_trial':True,'calibration_records':n,'nominal':nominal,'covered':covered,'coverage':covered/trials,'mean_efficiency':float(np.mean(efficiency)),'one_sided_undercoverage_p':test.pvalue,'predeclared_rejection_level':1e-4})
    return results


def bootstrap_experiment(trials=160):
    from confidenceguard.inference import smooth_bootstrap
    from confidenceguard.method_contracts import InferenceSpec
    from scipy.stats import binomtest
    rng=np.random.default_rng(20261020);records={name:{'available':0,'covered':0,'unavailable':{}} for name in ['paired_iid','paired_cluster','iid_on_dependent_events_negative_control']}
    for trial in range(trials):
        effect=.2+rng.normal(0,.3,50);sizes=rng.integers(1,9,50)
        candidates={'paired_iid':np.c_[np.zeros(50),np.ones(50),effect,np.ones(50)],
                    'paired_cluster':np.c_[np.zeros(50),sizes,effect*sizes,sizes],
                    'iid_on_dependent_events_negative_control':np.c_[np.zeros(sizes.sum()),np.ones(sizes.sum()),np.repeat(effect,sizes),np.ones(sizes.sum())]}
        for name,values in candidates.items():
            request=InferenceSpec(mode='independent_clusters' if name=='paired_cluster' else 'independent_rows',metrics=['bias'],replicates=2500,seed=trial)
            result=smooth_bootstrap(values,request,family_size=1,check=lambda *a:None)
            record=records[name]
            if result['status']=='available':record['available']+=1;record['covered']+=int(result['lower']<=.2<=result['upper'])
            else:record['unavailable'][result['reason']]=record['unavailable'].get(result['reason'],0)+1
    for name,record in records.items():
        record.update(trials=trials,true_effect=.2,conditional_coverage=record['covered']/record['available'] if record['available'] else None,
                      interval_availability=record['available']/trials,nominal=.95,
                      qualification='Coverage among admitted published intervals is descriptive and conditioned on availability; refusals are reported separately. This experiment is not a universal bootstrap accuracy theorem.')
        if name!='iid_on_dependent_events_negative_control':
            p=binomtest(record['covered'],record['available'],p=.95,alternative='less').pvalue
            record['one_sided_undercoverage_p']=p
            assert p>1e-4,(name,record)
    return records


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--out',required=True,type=Path);parser.add_argument('--reference-path');parser.add_argument('--pdf',action='store_true');args=parser.parse_args()
    if args.reference_path:sys.path.append(args.reference_path)
    import jsonschema
    from confidenceguard import study,EvaluationResult
    from confidenceguard.schema import schemas,openapi,examples
    from .fixtures import prepare
    args.out.mkdir(parents=True,exist_ok=False);report={'python':platform.python_version(),'packages':{p:importlib.metadata.version(p) for p in ['numpy','scipy','scikit-learn','jsonschema']},'seed':20261019,'generator_sha256':sha(__file__),'cases':[]}
    definitions=schemas();jsonschema.Draft202012Validator.check_schema(definitions)
    for example in examples()['studies'].values():jsonschema.validate(example['spec'],{**definitions,'$ref':'#/$defs/TransportReliabilitySpec'})
    for kind in ['binary','multiclass','regression']:
        spec=prepare(args.out/'data',kind);tick=time.monotonic();result=study(spec);duration=time.monotonic()-tick
        checks=references(spec,result)
        for value in (result.to_private_dict(),result.to_dict()):jsonschema.validate(value,{**definitions,'$ref':'#/$defs/Result'})
        for method in result.private['fitted_methods']:jsonschema.validate(method,{**definitions,'$ref':'#/$defs/FittedMethod'})
        for assessment in result.data['cg2']['assessments']:jsonschema.validate(assessment,{**definitions,'$ref':'#/$defs/Assessment'})
        EvaluationResult.from_dict(result.to_private_dict(),private=result.private)
        artifacts=[]
        for audience in ['local','shareable']:
            path=args.out/'reports'/(kind+'-'+audience+('.pdf' if args.pdf else '.html'))
            output=result.generate_artifacts(path,format='pdf' if args.pdf else 'html',json_path=path.with_suffix('.json'),audience=audience)
            artifacts.append({'audience':audience,'html':str(Path(output.html_path).relative_to(args.out)),'pdf':str(Path(output.pdf_path).relative_to(args.out)) if output.pdf_path else None,'html_sha256':sha(output.html_path),'pdf_sha256':sha(output.pdf_path) if output.pdf_path else None})
            if audience=='shareable':
                text=Path(output.html_path).read_text();assert 'coefficients' not in text and 'scalar_scale' not in text
        report['cases'].append({'case':kind,'source_sha256':{s['id']:sha(s['path']) for s in spec['evaluation']['sources']},'checks':checks,'duration_seconds':duration,'execution':result.execution,'artifacts':artifacts})
    report['conformal_experiments']=conformal_experiment()
    report['bootstrap_experiments']=bootstrap_experiment()
    report['scope']='Internal mathematical/reference, schema, workflow and simulation evidence; not production, market, universal efficiency or future-coverage validation.'
    report['reference_checks']=sum(len(c['checks']) for c in report['cases'])
    (args.out/'verification.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'reference_checks':report['reference_checks'],'conformal_experiments':len(report['conformal_experiments']),'cases':len(report['cases'])}))


if __name__=='__main__':main()
