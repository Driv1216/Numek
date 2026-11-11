"""Pinned CatBoost diagnostics: D-only fit, safe JSON, frozen score membership."""
import importlib.metadata
import json
from pathlib import Path
import numpy as np
from .contracts import EvaluationError,strict_json,digest
from .discovery_rules import heads
from .investigation_membership import seal,tabular,diagnostic_model,load_diagnostic_model


def propose(features,eligible,loss,objective,limits,directory,check=lambda *args:None,*,models=None,threads=2,reserve_fit=lambda:None):
    models=models if models is not None else {}
    if importlib.metadata.version('catboost')!='1.2.10':raise EvaluationError('Install pinned CG4 CatBoost.','diagnostic_runtime')
    from catboost import CatBoostClassifier,CatBoostRegressor,Pool
    columns=[{'id':fid,'kind':cells[0]['kind']} for fid,cells in sorted(features.items()) if cells and cells[0]['kind'] not in {'text','asset'}]
    if not columns:return [],{'strategy':'catboost','execution':'not_run','reason':'no_admitted_tabular_features'}
    matrix,cats,available,conversion=tabular(features,columns);selected=np.flatnonzero(eligible&available)
    if len(selected)<limits.minimum_discovery_support:return [],{'strategy':'catboost','execution':'not_run','reason':'insufficient_D_support'}
    candidates=[];fits=[]
    for head,target in heads(objective,loss):
        y=target[selected]
        if np.ptp(y)==0:
            fits.append({'head':head,'execution':'not_run','reason':'constant_D_diagnostic_target'});continue
        binary=set(np.unique(y)).issubset({0.,1.})
        pool=Pool(matrix[selected],label=y,cat_features=cats)
        for depth in (4,8):
            reserve_fit()
            check('CatBoost diagnostic fit')
            cls=CatBoostClassifier if binary else CatBoostRegressor
            model=cls(iterations=256,depth=depth,learning_rate=.05,l2_leaf_reg=3,random_seed=0,
                      thread_count=threads,task_type='CPU',allow_writing_files=False,verbose=False,
                      loss_function='Logloss' if binary else 'RMSE',bootstrap_type='No',random_strength=0,
                      one_hot_max_size=2,max_ctr_complexity=2)
            model.fit(pool)
            path=Path(directory)/f'diagnostic-{digest(objective.spec.id)[:20]}-{head}-{depth}.json'
            model.save_model(str(path),format='json',pool=pool)
            if path.stat().st_size>limits.max_artifact_bytes:raise EvaluationError('Diagnostic export exceeds artifact budget.','membership_artifact_limit')
            packet=strict_json(path.read_text());path.unlink()
            # Non-mathematical timestamps/GUIDs cannot make a deterministic fit
            # depend on wall time or an unrelated hidden H-label modification.
            info=packet.get('model_info',{})
            for key in ('model_guid','train_finish_time','training'):info.pop(key,None)
            model_json=json.dumps(packet,sort_keys=True,separators=(',',':'),ensure_ascii=True)
            model_digest=digest(model_json);models[model_digest]=model_json
            canonical=diagnostic_model(model_json)
            application=Pool(matrix,cat_features=cats)
            original=np.asarray(model.predict(application,prediction_type='RawFormulaVal',thread_count=threads),dtype=float).reshape(-1)
            score=np.asarray(canonical.predict(application,prediction_type='RawFormulaVal',thread_count=threads),dtype=float).reshape(-1)
            reload_score=np.asarray(load_diagnostic_model(model_json).predict(application,prediction_type='RawFormulaVal',thread_count=threads),dtype=float).reshape(-1)
            difference=float(np.max(np.abs(original-score)))
            if not np.allclose(original,score,rtol=0,atol=1e-12):raise EvaluationError('Diagnostic JSON export/reload score parity failed.','diagnostic_export_parity')
            if not np.array_equal(score,reload_score):raise EvaluationError('Canonical diagnostic scores changed on repeated JSON reload.','diagnostic_export_parity')
            thresholds=sorted(set(float(np.quantile(score[selected],q,method='linear')) for q in (.2,.4,.6,.8,.9,.95,.975,.99)))
            trainer_boundary_disagreements=0
            for i,threshold in enumerate(thresholds):
                for upper in (None,thresholds[i+1] if i+1<len(thresholds) else None):
                    if upper is None and i==len(thresholds)-1 and len(candidates) and candidates[-1]['artifact']['parameters']['threshold']==threshold:continue
                    mask=score>=threshold;reloaded=reload_score>=threshold;prior=original>=threshold
                    if upper is not None:mask&=score<upper;reloaded&=reload_score<upper;prior&=original<upper
                    if not np.array_equal(mask,reloaded):raise EvaluationError('Canonical diagnostic membership changed after reload.','diagnostic_export_parity')
                    # Trainer floats are not frozen membership. The exported,
                    # reloaded model defines scores before proposing any gate.
                    # Keep observed round-trip tie differences visible.
                    trainer_boundary_disagreements+=int(np.count_nonzero(mask!=prior))
                    support=int(np.count_nonzero(mask&eligible&available))
                    if support<limits.minimum_discovery_support:continue
                    params={'model_digest':model_digest,'columns':columns,'threshold':threshold,'upper':upper,
                            'head_sign':-1 if head=='negative' else 1,'runtime':'catboost/1.2.10-cpu'}
                    artifact=seal('catboost',params,features=[c['id'] for c in columns],objective=objective.identity)
                    candidates.append({'artifact':artifact,'D_conditional_support':support,'D_proxy_utility':float(np.mean(target[mask&eligible&available])),
                                       'head':head,'complexity':256*(2**depth),'export_score_max_difference':difference})
            fits.append({'head':head,'depth':depth,'trees':256,'D_support':len(selected),'objective':'Logloss' if binary else 'RMSE',
                         'export_score_max_difference':difference,'export_membership_parity':True,'threads':threads,
                         'membership_basis':'canonical_JSON_reload_before_threshold_definition',
                         'trainer_threshold_boundary_disagreements':trainer_boundary_disagreements})
            check('CatBoost frozen diagnostic export')
    return candidates[:limits.candidates_per_strategy],{'strategy':'catboost','fits':fits,'numeric_conversion_counts':conversion,
             'selection_refit':False,'qualification':'requires_objective_family_qualification','execution':'completed'}
