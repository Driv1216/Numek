"""One conservative disclosure projection shared by every portable representation."""
import copy
from .contracts import DisclosureSpec, digest, exact

PROJECTION_REVISION='cg1_review_corrections_v1'
RANKING_DETAILS={'roc_pr_curve','ranking_score','selection_score','class_score_maximum'}
SAFE_FINDINGS={
    'duplicate_keys':'Ambiguous prediction keys limit dependent analytical populations.',
    'missing_keys':'Missing prediction keys limit dependent analytical populations.',
    'invalid_probabilities':'Some supplied probabilities are invalid; independent valid decisions remain eligible.',
    'inline_conflicts':'An inline outcome copy disagrees with the authoritative reference; consult its assertion role and comparison eligibility.',
    'decision_rule_mismatches':'Supplied decisions do not always match the declared diagnostic rule.',
    'unresolved_issuance':'Issuance is not fully established; operational coverage claims are limited.',
    'not_held_out':'This run is not declared independent final evaluation; generalization is not established.',
    'inference_blocked':'Known repeated entities block independent-row intervals.',
    'paired_comparison_blocked':'Paired performance is unavailable under the current outcome, identity or timing declarations.',
    'zero_probability_observed_outcome':'An observed reference outcome received zero supplied probability.'}
SAFE_REASONS={'authoritative_outcomes_required','ambiguous_prediction_identities','conflicting_asserted_outcome_copy','ambiguous_outcome_identities','different_horizons','different_information_cutoffs','representation_or_policy_not_declared','conflicting_canonical_context_assertion','no_unique_context','interval_meaning_nominal_coverage_or_centrality_differs'}
LIMITATIONS=['Supplied outcomes are reference evidence, not independently verified truth.','Observed labels need not represent unobserved cases.','No universal score or production approval.','Unknown provenance does not establish out-of-sample evaluation.']


def safe_checks(raw,spec,runs,intervals):
    """Project typed checks, never arbitrary text, category inventories or exact counts."""
    identities={}
    for run in spec['runs']:
        rid=run['id'];alias=runs[rid]
        for method in ('probability_quality','supplied_intervals','fixed_policy_replay'):
            identities[method+':'+rid]=method+':'+alias
        for i,_ in enumerate(spec['cohorts']):
            for suffix in ('',':unresolved',':inventory'):
                identities[f'cohort_{i}:{rid}{suffix}']=f'cohort_{i}:{alias}{suffix}'
    identities.update({'paired_interval:'+k:'paired_interval:'+v for k,v in intervals.items()})
    output=[]
    for check in raw:
        if check.get('id') not in identities:continue
        if check.get('applicability') not in {'applicable','not_applicable','blocked'} or check.get('execution') not in {'completed','not_run'}:continue
        c={'id':identities[check['id']],'applicability':check['applicability'],'execution':check['execution'],'detail_disclosure':'exact details retained locally'}
        if check.get('reason') in SAFE_REASONS:c['reason']=check['reason']
        output.append(c)
    return output


def harden_shared(data):
    """Re-export legacy conservative projections safely, without inventing lost evidence."""
    data=copy.deepcopy(data)
    if data.get('schema_version')=='confidenceguard.evaluation_result/1.1':return data
    if data.get('disclosure',{}).get('policy')!='conservative_aggregates_v1' or data.get('coverage',{}).get('projection_revision')==PROJECTION_REVISION:return data
    data['measurements']=[m for m in data['measurements'] if m['metric'] not in RANKING_DETAILS]
    data['coverage']['projection_revision']=PROJECTION_REVISION
    data['coverage']['legacy_qualification']='Legacy projection: denominator lineage and discarded findings cannot be recovered; reevaluate original inputs for corrected provenance.'
    data['findings'].append({'code':'ranking_details_withheld','priority':'Information','message':'Exact ranking curves and native score summaries are withheld; scalar ranking metrics use all eligible score groups.'})
    data['origin_projection_digest']=data.pop('projection_digest')
    data['projection_digest']=digest(data)
    return data


def project(result,disclosure=None):
    policy=disclosure or DisclosureSpec.from_dict(result.private['config']['disclosure'])
    if isinstance(policy,dict):policy=DisclosureSpec.from_dict(policy)
    raw=result.to_private_dict();measurements=raw['measurements'];protected=set()
    if policy.policy=='conservative_aggregates_v1':
        # Even a large denominator can hide singleton score groups. Exact score cutoffs
        # identify predictive artifacts, and adjacent rates reveal cumulative small cells.
        if any(m['metric'] in RANKING_DETAILS for m in measurements):protected.add('ranking_curve')
        for m in measurements:
            n=int(m['denominator'])
            if 0<n<policy.minimum_denominator or any(0<float(v)<policy.minimum_component for v in m['sensitive_counts'] if v is not None):protected.add(m['disclosure_group'])
        # Paired transitions and deltas must not provide a second route into a withheld table.
        if any(m['family']=='comparison' and m['disclosure_group'] in protected for m in measurements):
            protected.update(m['disclosure_group'] for m in measurements if m['family']=='comparison' or m['scope']=='paired')
    classes={c:policy.display_labels.get(c,f'Class {i+1}') for i,c in enumerate(raw['task']['classes'])}
    runs={r['id']:f'run_{i+1}' for i,r in enumerate(raw['runs'])}
    cohorts={c['id']:f'cohort_{i}' for i,c in enumerate(result.private['spec']['cohorts'])}
    policy_aliases={p['id']:f'policy_{i+1}' for i,p in enumerate(result.private['spec']['policies'])}
    interval_aliases={v['id']:f'interval_{i+1}' for run in result.private['spec']['runs'] for i,v in enumerate(run['intervals'])}
    def labels(v):
        if isinstance(v,list):return [labels(x) for x in v]
        if isinstance(v,dict):
            out={}
            for k,x in v.items():
                if k in {'actual','predicted','class'} and isinstance(x,str):out[k]=classes.get(x,'Class unavailable')
                elif k in {'run','left_run','right_run','left','right'} and isinstance(x,str):out[k]=runs.get(x,x)
                elif k=='target' and isinstance(x,str) and x.startswith('class:'):out[k]='class:'+classes.get(x[6:],'Class unavailable')
                elif k=='interval' and isinstance(x,str):out[k]=interval_aliases.get(x,'supplied interval')
                elif k=='family' and isinstance(x,str) and x.startswith('policy:'):out[k]='policy:'+policy_aliases.get(x[7:],'supplied')
                else:out[k]=labels(x)
            return out
        return v
    output=[]
    for m in measurements:
        if m['disclosure_group'] in protected or policy.policy=='conservative_aggregates_v1' and m['metric'] in RANKING_DETAILS:continue
        m=labels(m)
        for k in ('sensitive_counts','disclosure_group','evidence_refs'):m.pop(k,None)
        # Population predicates contain original classes; publish an opaque identity and scope only.
        m['evidence_refs']=[];output.append(m)
    public_runs=[]
    for r in raw['runs']:
        d=r['decision_provenance']
        public_runs.append({'id':runs[r['id']],'display_name':r['display_name'],'version_alias':r['version_alias'],'role':r['role'],'decision_provenance':{'origin':'supplied' if r['representations']['hard_prediction'] else 'derived' if d['rule']!='none' else 'none','rule':d['rule'],'threshold':d['threshold'],'tie_policy':d['tie_policy']},'representations':r['representations']})
    comparison=raw['comparison']
    if comparison:
        comparison={'left':runs[comparison['left']],'right':runs[comparison['right']],'blocked_reasons':[x for x in comparison['blocked_reasons'] if x in SAFE_REASONS],'timing_qualification':comparison['timing_qualification'] if comparison['timing_qualification'] in {'unestablished','known_equal_on_shared_events'} else 'unestablished','scope':'matched supplied predictions; no isolated causal model or generalization claim'}
    findings=[{'code':'withheld_breakdowns','priority':'Information','message':'Some related breakdowns are withheld under the selected disclosure policy.'}] if protected else []
    for finding in raw['findings']:
        code=finding.get('code')
        if code not in SAFE_FINDINGS:continue
        if code=='zero_probability_observed_outcome' and not any(m['metric']=='log_loss' and m['value_state']=='positive_infinity' for m in output):continue
        f={'code':code,'priority':'Review','message':SAFE_FINDINGS[code]}
        if finding.get('run') in runs:f['run']=runs[finding['run']]
        if code=='paired_comparison_blocked':f['reasons']=[x for x in finding.get('reasons',[]) if x in SAFE_REASONS]
        findings.append(f)
    if policy.policy=='conservative_aggregates_v1' and any(m['metric'] in RANKING_DETAILS for m in measurements):
        findings.append({'code':'ranking_details_withheld','priority':'Information','message':'Exact ranking curves and native score summaries are withheld; scalar ranking metrics use all eligible score groups.'})
    # Only disclose population records needed by retained evidence, with no SQL,
    # source identities or class predicates. Include nested class/delta references.
    ids={m['population_id'] for m in output}
    def references(v):
        if isinstance(v,dict):
            for k,x in v.items():
                if k.endswith('population_id') and isinstance(x,str):ids.add(x)
                else:references(x)
        elif isinstance(v,list):
            for x in v:references(x)
    references(output)
    pops=[{k:(runs[p[k]] if k=='run' else p[k]) for k in ('id','run','scope','denominator','denominator_kind') if k in p} for p in raw['coverage']['populations'] if p['id'] in ids]
    coverage={'analytical_scope':'Completed admitted populations; exact coverage is retained in the protected bundle.','retention_limits':raw['coverage']['retention_limits'],'privacy_withholding':'Related breakdowns withheld' if protected else 'No configured small-count withholding triggered.','not_anonymity_guarantee':True,'projection_revision':PROJECTION_REVISION,'limitations':LIMITATIONS,'sampling':raw['coverage']['sampling'],'populations':pops}
    if raw['coverage'].get('population_provenance_version'):coverage['population_provenance_version']=raw['coverage']['population_provenance_version']
    else:coverage['legacy_qualification']='Legacy result: corrected denominator lineage requires reevaluation.'
    public={'schema_version':raw['schema_version'],'methodology_id':raw['methodology_id'],'analysis_id':raw['analysis_id'],'generated_at':raw['generated_at'],'name':raw['name'],'audience':'shareable','task':{'kind':raw['task']['kind'],'classes':list(classes.values()),'units':policy.display_labels.get('units','declared outcome units') if raw['task'].get('units') else None},'runs':public_runs,'outcomes':{'interpretation':'Supplied reference outcomes; correctness and population representativeness are not established.'},'comparison':comparison,'measurements':output,'checks':safe_checks(raw['checks'],result.private['spec'],runs,interval_aliases),'findings':findings,'coverage':coverage,'execution':{'status':raw['execution']['status'],'backend':'duckdb_local','methodology':raw['methodology_id']},'origin_binding':raw['binding'],'disclosure':policy.to_dict()}
    # User-provided category mappings are not implicitly embedded in a shareable policy manifest.
    public['disclosure']['display_labels']={}
    public['coverage']['retention_limits'].pop('retained_witnesses',None)
    if raw.get('schema_version')=='confidenceguard.evaluation_result/1.1':
        from .method_disclosure import project_methods
        project_methods(raw,public,runs)
    public['projection_digest']=digest(public)
    return exact(public)
