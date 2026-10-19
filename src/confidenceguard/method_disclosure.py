"""CG2 safe report summaries. Learned artifacts and fitting populations stay private."""

SAFE={'method_unavailable':'A requested method was unavailable on its frozen population.',
      'prior_membership_qualification':'Prior fitting/selection/calibration membership checks are unavailable or contradicted; external independence remains qualified.',
      'application_unavailable_outputs':'Some transformed outputs are unavailable; successful-output comparisons do not establish improvement on the planned population.',
      'independent_evaluation_unestablished':'No qualifying independent evaluation is established; fitted/application evidence does not prove improvement.',
      'coverage_assumptions_unestablished':'Ordinary future-population conformal coverage assumptions are not established.'}


def project_methods(raw,public,runs):
    cg=raw['cg2']; aliases={key:runs.get(key,f'method_{i+1}') for i,key in enumerate(cg['methods'])}
    candidates=set(cg['fit_status'])|{k for s in cg['selections'] for k in s['candidates']}
    for i,key in enumerate(sorted(candidates)):
        if key not in aliases:aliases[key]=f'candidate_{i+1}'
    assessed={a['method_digest']:a for a in cg.get('assessments',[])}
    methods=[]
    for key,v in cg['methods'].items():
        methods.append({'id':aliases[key],'method':v['method'],'algorithm_version':v['algorithm_version'],
                        'artifact_reference':v['artifact_digest'],'method_evidence_state':'independently_evaluated' if v['artifact_digest'] in assessed else 'fitted_only',
                        'application_evidence_state':'independently_evaluated' if v['artifact_digest'] in assessed else 'applied_unvalidated',
                        'independent_evaluation_does_not_imply_improvement':True})
    selections=[]
    for i,s in enumerate(cg['selections']):
        selections.append({'id':f'selection_{i+1}','objective':s['objective'],'selected':aliases.get(s['selected']),
                           'candidates':[{'id':aliases[k],'status':v['status']} for k,v in s['candidates'].items()],
                           'population_policy':'Frozen common inputs; failures do not renegotiate membership.',
                           'exact_selection_evidence':'retained locally'})
    public['cg2']={'operation':cg['operation'],'methods':methods,'selections':selections,
                   'separation':{k:v for k,v in cg['separation'].items() if isinstance(v,bool)},'inference':{'status':cg['inference']['status'],'conditioning':'Frozen fitted artifacts; excludes fitting and selection variability.'},
                   'assessment_policy':'Independent evaluation applies only to the exact method/application/population assessed. Reapplication is unvalidated.',
                   'population_policy':'Common inputs and paired outputs are distinct; native metrics are not substituted for matched comparisons.'}
    public['coverage']['projection_revision']='cg2_conservative_v1'
    public['coverage']['limitations']=raw['coverage']['limitations']
    for measurement in public['measurements']:
        for field in ('candidate_failures','candidate_undefined_records'):
            if field in measurement['data']:measurement['data'][field]={runs.get(k,aliases.get(k,'unavailable_candidate')):v for k,v in measurement['data'][field].items()}
        if 'uncertainty_status' in measurement:
            status=measurement['uncertainty_status']
            measurement['uncertainty_status']={k:v for k,v in status.items() if k in {'status','reason','reasons','execution'}}
        if 'uncertainty' in measurement:
            interval=measurement['uncertainty']
            measurement['uncertainty']={k:v for k,v in interval.items() if k in {'lower','upper','level','adjustment','family_size','method','sampling_unit','conditioning'}}
        if measurement['metric']=='frozen_bin_ece':
            measurement['data']={k:v for k,v in measurement['data'].items() if k not in {'edges','bins'}}
            measurement['data']['bin_details_disclosure']='Exact bin edges and detail retained locally.'
    public['findings'].extend({'code':f['code'],'priority':'Review','message':SAFE[f['code']]} for f in raw['findings'] if f['code'] in SAFE)
