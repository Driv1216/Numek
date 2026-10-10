"""M3 task dispatch inside the shared CSV orchestration path.

This module consumes the loaded frame and shared recording/optional-check
helpers. It never loads data, scores classification, or exports artifacts.
"""
from dataclasses import asdict
import numpy as np
from datatrust.annotations import annotation_coverage, feature_semantics, cohort_evidence, observation
from datatrust.contracts import AnnotationOptions, RegressionOptions, Applicability, ExecutionStatus, CheckOutcome
from datatrust.regression import multioutput_evidence
from datatrust.multilabel import multilabel_evidence, repeated_inputs
from datatrust.unsupervised import readiness_evidence
from datatrust.risks import build_unlabeled_findings


def analyze_tasks(data, task, config, roles, profile, checks, record, optional, checkpoint):
    semantics=feature_semantics(data,roles['features'],config.features)
    profile['feature_semantics']=semantics
    profile['declarations']={'annotations':asdict(config.annotations or AnnotationOptions()),'features':asdict(config.features),
                             'regression':asdict(config.regression) if config.regression else None,
                             'multilabel':asdict(config.multilabel) if config.multilabel else None}
    record('feature_semantics',['/profile/feature_semantics'],'selected input features',len(semantics))
    if roles['targets']:
        coverage,observed_counts=annotation_coverage(data,task,config.annotations,roles['groups'],max_examples=config.diagnostics.max_examples)
        profile['annotations']=coverage
        record('annotation_coverage',['/profile/annotations'],'parsed target cells',len(data)*len(roles['targets']))
        for i,c in enumerate(coverage['targets']):
            record('target_coverage',[f'/profile/annotations/targets/{i}'],'parsed rows',len(data),columns=[c['target']],scope=c['target'])
        cohorts=optional('annotation_cohorts',lambda:cohort_evidence(data,task,config.annotations,semantics,observed_counts,config.diagnostics,checkpoint))
        profile['annotation_cohorts']=cohorts
        if cohorts is not None: record('annotation_cohorts',['/profile/annotation_cohorts'],'within-file annotation populations',method='bounded_descriptive_population_contrasts')
    if task.kind=='classification':
        t=roles['targets'][0];obs=observation(data[t],task.kind)
        counts=data[t][obs['valid']].value_counts()
        profile['classification']={'target':t,'observed_count':int(obs['valid'].sum()),'distribution':[{'label':str(v),'count':int(c),'share':int(c)/int(obs['valid'].sum())} for v,c in counts.items()],
                                   'class_count':len(counts),'interpretation':'Supplied observed annotations, including unknown expectations and declared uncertain validity; correctness is not verified.'}
        if len(counts):record('classification_distribution',['/profile/classification'],'well-formed observed annotations',int(obs['valid'].sum()))
        else:checks.append(CheckOutcome('classification_distribution',Applicability.BLOCKED,ExecutionStatus.NOT_RUN,reason='No observed annotations. Coverage remains available.'))
        profile['repeated_inputs']=optional('annotation_repetition',lambda:repeated_inputs(data,roles['features'],roles['targets'],task.kind,config.diagnostics,annotations=config.annotations))
        if profile['repeated_inputs'] is not None:record('annotation_repetition',['/profile/repeated_inputs'],'selected input vectors')
    elif task.kind=='regression':
        profile['multioutput_regression']=optional('multioutput_regression',lambda:multioutput_evidence(data,roles['targets'],roles['features'],config.regression or RegressionOptions(),config.diagnostics,checkpoint,relationship_features=[s['column'] for s in semantics if s['quantitative_geometry']],annotations=config.annotations))
        r=profile['multioutput_regression']
        if r is not None:
            record('multioutput_regression',['/profile/multioutput_regression'],'finite observed targets; joint metrics use matched populations')
            for i,o in enumerate(r['outputs']):
                pointer=f'/profile/multioutput_regression/outputs/{i}'
                record('output_evidence',[pointer],'finite observed target',o['finite_count'],columns=[o['target']],scope=o['target'])
                if o['statistics']:
                    for name,reason in o['statistics']['unavailable_statistics'].items():
                        checks.append(CheckOutcome('regression_'+name,Applicability.BLOCKED,ExecutionStatus.NOT_RUN,scope=o['target'],reason=reason))
                if o['blocked_reason']:checks.append(CheckOutcome('regression_distribution',Applicability.BLOCKED,ExecutionStatus.NOT_RUN,scope=o['target'],reason=o['blocked_reason']))
                if o['search'] and o['search'].get('failure'):
                    failure=o['search']['failure'];checks.append(CheckOutcome('regression_relationships',execution=ExecutionStatus.SKIPPED if failure['reason_category']=='execution_interruption' else ExecutionStatus.FAILED,scope=o['target'],reason=failure['reason']))
            for dep in r['output_dependencies']:
                search=dep.get('identity_search')
                if search and search.get('failure'):
                    failure=search['failure']
                    checks.append(CheckOutcome('output_identity',execution=ExecutionStatus.SKIPPED if failure['reason_category']=='execution_interruption' else ExecutionStatus.FAILED,scope=' / '.join(dep['targets']),reason=failure['reason']))
    elif task.kind=='multilabel_classification':
        profile['multilabel']=optional('multilabel',lambda:multilabel_evidence(data,roles['targets'],config.multilabel,config.diagnostics,checkpoint))
        if profile['multilabel'] is not None:
            record('multilabel',['/profile/multilabel'],'observed binary assignments; pairs use joint known populations')
            if not profile['multilabel']['cardinality_denominator']:
                checks.append(CheckOutcome('multilabel_cardinality',Applicability.BLOCKED,ExecutionStatus.NOT_RUN,reason='No complete valid observed vectors.'))
            for pair in profile['multilabel']['pairs']:
                if not pair['jointly_observed']:
                    checks.append(CheckOutcome('multilabel_pair',Applicability.BLOCKED,ExecutionStatus.NOT_RUN,scope=' / '.join(pair['targets']),reason='No jointly observed assignments.'))
        profile['repeated_inputs']=optional('annotation_repetition',lambda:repeated_inputs(data,roles['features'],roles['targets'],task.kind,config.diagnostics,annotations=config.annotations))
        if profile['repeated_inputs'] is not None:record('annotation_repetition',['/profile/repeated_inputs'],'selected input vectors')
    elif task.kind in {'clustering','anomaly_detection'}:
        profile['readiness']=optional('readiness',lambda:readiness_evidence(data,roles['features'],semantics,config.features,task.kind,config.diagnostics,checkpoint))
        if profile['readiness'] is not None:record('readiness',['/profile/readiness'],'selected input representation',len(data),method='conditional_pre_model_readiness')
    findings=build_m3_findings(profile,task)
    narrative={'overall_assessment':'Pre-model evidence for the declared tabular task; no composite reliability score or model-quality verdict is defined.',
               'principal_evidence_summary':f"{len(data):,} parsed rows; {len(roles['features']):,} selected input feature{'s' if len(roles['features']) != 1 else ''}; {len(roles['targets']):,} target{'s' if len(roles['targets']) != 1 else ''}. " + ('Annotation coverage separates observation, expectation, metadata resolution, and declared uncertain validity.' if roles['targets'] else 'Representation assumptions and structural evidence qualify the available task diagnostics.'),
               'recommended_action':findings[0]['recommendation'] if findings else 'Review applicability, coverage, and representation assumptions before selecting downstream methods.',
               'limitations':'Observed annotations are supplied evidence, not verified ground truth. No model performance, representativeness, clustering quality, or anomaly correctness is established.'}
    return findings,narrative,{'status':'not_defined','values':None,'reason':'No validated composite scoring methodology is defined for these effective semantics.'}


def build_m3_findings(profile,task):
    structural=dict(profile,columns=[c for c in profile['columns'] if c['role']=='feature'],missing_cells=profile['missing_feature_cells'],missing_rate=profile['missing_feature_cell_rate'])
    findings=[f for f in build_unlabeled_findings(structural) if f['code']!='numeric_outlier_concentration']
    for f in findings:
        f['measurement_paths']=['/profile/columns'] if f.get('check_id') not in {'exact_duplicates','missingness'} else ['/profile/duplicate_rows'] if f['check_id']=='exact_duplicates' else ['/profile/missing_feature_cells']
        predicates={'fully_missing_columns':lambda c:c['unique_count']==0,
                    'column_missingness':lambda c:c['unique_count']>0 and c['missing_rate']>=25,
                    'constant_fields':lambda c:c['constant'] and c['unique_count']==1,
                    'near_constant_fields':lambda c:c['near_constant'] and not c['top_value_is_missing'],
                    'high_cardinality_categoricals':lambda c:c['high_cardinality'],
                    'non_finite_values':lambda c:c.get('numeric_summary') and c['numeric_summary']['non_finite_count']}
        if f['code'] in predicates:
            f['affected_columns']=[c['name'] for c in structural['columns'] if predicates[f['code']](c)]
            f['affected_count']=len(f['affected_columns'])
        f.pop('check_id',None)
    def add(code,title,severity,details,paths,advice,population):
        if not details:return
        findings.append({'code':code,'title':title,'severity':severity,'finding':f'{len(details)} affected declared fields or checks.',
                         'evidence':details,'affected_count':len(details),'population':population,'measurement_paths':paths,
                         'recommendation':advice,'modeling_impact':'Interpret against declared use and the reported observed populations; correctness is not established.',
                         'evidence_type':'review_observation'})
    targets=profile.get('annotations',{}).get('targets',[])
    definitions=[('invalid','invalid_annotations','Invalid annotation encodings','High','Review supplied encodings; invalid assignments are excluded from applicable diagnostics.'),
                 ('declaration_inconsistencies','annotation_declaration_conflicts','Annotation declaration conflicts','High','Reconcile the declared annotation state with the actual supplied value.'),
                 ('unresolved_metadata','unresolved_annotation_metadata','Unresolved annotation metadata','Moderate','Resolve missing or unmapped status tokens; valid supplied observations remain in descriptive evidence.')]
    for key,code,title,severity,advice in definitions:
        selected=[c for c in targets if c[key]]
        add(code,title,severity,[{'target':c['target'],'count':c[key],'denominator':c['total_rows']} for c in selected],['/profile/annotations'],advice,'parsed target cells; overlapping flags are separate')
    for severity in ('High','Moderate'):
        selected=[c for c in targets if c['unavailable_expected'] and ('High' if c['unavailable_expected']/c['expected']>=.25 else 'Moderate')==severity]
        add('expected_annotation_gaps_'+severity.lower(),'Unavailable expected annotations',severity,[{'target':c['target'],'unavailable':c['unavailable_expected'],'expected':c['expected'],'unknown_expectation':c['unknown_expectation_population'],'reasons':c['unavailable_expected_by_reason']} for c in selected],['/profile/annotations'],'Review resolved expected gaps alongside unknown-expectation coverage.','resolved expected annotations')
    cls=profile.get('classification')
    if cls and cls['observed_count']>=20 and cls['class_count']==1:
        add('constant_observed_class','One class in observed annotations','Moderate',[{'target':cls['target'],'observed_count':cls['observed_count']}],['/profile/classification'],'Review observed class support and annotation coverage; unobserved outcomes are unknown.','observed single-target annotations')
    m=profile.get('multilabel')
    if m:
        add('multilabel_declared_constraints','Recorded label constraints violated','High',[c for c in m['constraints'] if c['violated']],['/profile/multilabel'],'Review definite violations of user-declared constraints; partial unknown assignments can be inconclusive.','declared constraints on recorded assignments')
        for code,title,severity,selected in [('constant_observed_labels','Constant observed labels','Moderate',[c for c in m['labels'] if c['observed']>=20 and min(c['positive'],c['negative'])==0]),
                                             ('limited_label_support','Limited observed label support','Low',[c for c in m['labels'] if c['observed']>=30 and min(c['positive'],c['negative'])<5])]:
            add(code,title,severity,selected,['/profile/multilabel'],'Review label support for the intended use; internal review gates are not validated sample-size requirements.','observed assignments per label')
    r=profile.get('multioutput_regression')
    if r:
        add('numerical_target_constraints','Declared numerical constraints violated','High',[{'target':o['target'],**o['constraints']} for o in r['outputs'] if o['constraints'] and o['constraints']['violation_union_count']],['/profile/multioutput_regression'],'Review the declared range/type requirements and recorded finite values.','finite outputs, separately by units')
        selected=[]
        for o in r['outputs']:
            s=o['statistics']
            if s and s['precision_reason']:selected.append({'target':o['target'],'finite_count':s['finite_count'],'distinct_count':s['distinct_count'],'precision_reason':s['precision_reason']})
        add('limited_numerical_evidence','Limited numerical target evidence','Moderate',selected,['/profile/multioutput_regression'],'Review arithmetic limitations; retain exact counts and coverage.','finite observations by output')
        for code,title,priority,predicate,advice in [
            ('constant_numerical_outputs','Observed constant outputs','High',lambda s:s['distinct_count']==1,'Confirm the intended output and whether collection or selection explains the observed lack of variation.'),
            ('limited_finite_outputs','Limited finite output observations','Moderate',lambda s:s['finite_count']<4,'Review collection scope and blocked numerical methods. This is not a universal training-size requirement.'),
            ('output_concentration','Output concentration review','Low',lambda s:s['distinct_count']>1 and (s['finite_count']>=20 and (s['modal_share']>=95 or s['iqr']==0) or any(b['review_candidate'] for b in s['boundary_concentration'])),'Review legitimate point masses, measurement limits, and collection rules; concentration does not establish clipping or error.'),
            ('output_extreme_candidates','Marginal output extreme candidates','Low',lambda s:bool(s['extremes'] and s['extremes']['rate']>=5),'Review units and legitimate tails. IQR candidates do not establish incorrect observations.')]:
            selected=[{'target':o['target'],'finite_count':o['statistics']['finite_count'],'distinct_count':o['statistics']['distinct_count'],'modal_share':o['statistics']['modal_share'],'extremes':o['statistics']['extremes']} for o in r['outputs'] if o['statistics'] and predicate(o['statistics'])]
            add(code,title,priority,selected,['/profile/multioutput_regression'],advice,'finite observed values separately by output')
        unavailable=[{'feature':c,'availability':v} for c,v in r['feature_availability'].items() if v=='unavailable_at_prediction']
        add('declared_input_unavailability','Inputs declared unavailable at prediction time','High',unavailable,['/profile/multioutput_regression'],'Review the selected input set and declared prediction timing; this declaration does not establish actual model use or leakage.','user-declared input context')
        for availability,severity in [('unavailable_at_prediction','High'),('unknown','Moderate')]:
            selected=[{'target':o['target'],**g} for o in r['outputs'] for g in o['relationship_groups'] if g['action_eligible'] and g['availability']==availability]
            add('input_target_relationships_'+availability,'Verified input-target relationships',severity,selected,['/profile/multioutput_regression'],'Confirm prediction-time availability. Verified relationships apply only to their observed support, not missing outputs.','fully verified finite input-target overlaps')
    readiness=profile.get('readiness')
    if readiness:
        add('conditional_scale_review','Conditional quantitative scale review','Low',[r for r in readiness['scale_ratios'] if r['conditional_review']],['/profile/readiness'],'Review units and preprocessing for the chosen method; representation-dependent scale ratios do not prove similarity distortion.','separate declared and assumed quantitative populations')
    repetition=profile.get('repeated_inputs') or (r or {}).get('repeated_inputs')
    if repetition and repetition.get('varying_row_union'):
        add('observed_annotation_disagreement','Observed differences on repeated inputs','Low',[c for c in repetition['targets'] if c['varying_group_count']],['/profile/repeated_inputs'] if profile.get('repeated_inputs') else ['/profile/multioutput_regression'],'Review omitted context, stochastic outcomes, or annotation differences. No label is proven incorrect.','observed annotations grouped by selected inputs')
    row_unions=profile.get('annotations',{}).get('rows',{}).get('affected_row_unions',{})
    for f in findings:
        key={'invalid_annotations':'invalid','annotation_declaration_conflicts':'declaration_inconsistencies','unresolved_annotation_metadata':'unresolved_metadata','expected_annotation_gaps_high':'expected_gaps_high','expected_annotation_gaps_moderate':'expected_gaps_moderate'}.get(f['code'])
        if key is not None:f['affected_row_union']=row_unions[key]
    return sorted(findings,key=lambda f:{'High':0,'Moderate':1,'Low':2}[f['severity']])
