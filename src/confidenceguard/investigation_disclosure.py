"""One conservative disclosure projection shared by every CG4 presentation."""
import copy
from .contracts import DisclosureSpec,digest
from .investigation_contracts import LANDMARK_PROMOTION_EVIDENCE


def objective_label(objective):
    # Labels are a disclosure vocabulary, not another analytical registry.
    # Free-form target IDs, interval IDs, names and units can identify people.
    safe={'accuracy','error_rate','false_negative_rate','false_positive_rate','precision','recall','specificity','f1',
        'brier','log_loss','reliability_diagram','calibration_residual','mae','mse','rmse','bias','material_error_rate',
        'median_absolute_error','p90_absolute_error','p95_absolute_error','r2','roc_auc','average_precision',
        'interval_coverage','interval_miscoverage','interval_width','central_interval_score'}
    return {'metric':objective['metric'] if objective.get('metric') in safe else 'protected_registered_metric',
        'direction':objective.get('direction'),'comparator':objective.get('comparator'),
        'units':objective.get('units') if objective.get('units') in {'fraction','probability','count','dimensionless','nats','target_units','target_units^2'} else 'Declared units retained locally'}


def independence_label(value):
    # Preserve conclusion qualifications without exporting protected ledger/use
    # identities or future free-form declarations added to private assessments.
    allowed={
        'local_separation':{'failed','system_checked','partially_checked'},
        'local_identity_scope':{'live_source_keys_and_available_local_aliases',
            'canonical_history_keys_and_retained_original_aliases','canonical_history_keys_original_aliases_incomplete'},
        'upstream':{'unknown','declared_independent','known_overlap'},
        'external_exposure':{'unknown','declared_unexposed','known_exposed'},
        'exposure_continuity':{'unknown','intact','incomplete','restore_unreconciled','unavailable'},
        'history_gap_basis':{'current_scoped_declaration_not_system_verified_history'},
        'evidence_use':{'predeclared_restatement_not_fresh_independent_evidence'},
        'external_exposure_declaration_scope':{'before_initial_H_access'},
        'sampling_design':{'independent_rows','independent_entities','independent_entity_arms','descriptive','unsupported_temporal'},
    }
    if not isinstance(value,dict):return None
    output={key:item for key,item in value.items() if key in allowed and isinstance(item,str) and item in allowed[key]}
    for key in ('ledger_enabled','schedule_predeclared_and_locally_verified'):
        if type(value.get(key)) is bool:output[key]=value[key]
    if isinstance(value.get('ledger_gaps_declaration_qualified'),list):
        output['ledger_gaps_declaration_qualified']=[item for item in value['ledger_gaps_declaration_qualified']
            if isinstance(item,str) and item in {'exposure_history_unavailable','exposure_history_incomplete'}]
    return output


def outcome_status_counts(value):
    allowed={'final','observed','provisional','invalid','conflicting','pending','withdrawn',
        'unresolved','unavailable_as_of','no_unique_snapshot'}
    return {key:n for key,n in value.items() if key in allowed and type(n) is int and n>=0} if isinstance(value,dict) else {}


def related_membership_risk(private,candidates,assessments,minimum):
    """Conservative pair-cell guard using exact protected ternary memberships.

    Bounded audit: missing alignment or excessive work withholds the related
    family. This is not differential privacy or protection against arbitrary
    external information and repeated releases.
    """
    groups={role:[c.get('membership_artifact') for c in candidates] for role in ('D','S')}
    frozen=private.get('frozen_hypotheses');declarations=frozen.get('hypotheses',[]) if isinstance(frozen,dict) else []
    hypotheses={h['id']:h['membership_artifact'] for h in declarations if isinstance(h,dict)
        and type(h.get('id')) is str and type(h.get('membership_artifact')) is str} if isinstance(declarations,list) else {}
    groups['H']=[hypotheses.get(a.get('hypothesis_id')) for a in assessments]
    stored=private.get('memberships')
    for role,artifacts in groups.items():
        if len(artifacts)<2:continue
        if not isinstance(stored,dict) or any(type(a) is not str for a in artifacts):return True
        decoded=set();records=None;decoded_bytes=0
        for artifact in dict.fromkeys(artifacts):
            owned=stored.get(artifact);packet=owned.get(role) if isinstance(owned,dict) else None
            if not isinstance(packet,dict) or type(packet.get('records')) is not int or packet['records']<0:return True
            n=packet['records'];size=(n+7)//8
            if records is not None and n!=records:return True
            records=n;decoded_bytes+=2*size
            if decoded_bytes>16*1024**2:return True
            raw=[packet.get(key) for key in ('member_bits','available_bits')]
            if any(type(value) is not str or len(value)!=2*size for value in raw):return True
            try:member,available=[int.from_bytes(bytes.fromhex(value),'little') for value in raw]
            except ValueError:return True
            if member.bit_length()>n or available.bit_length()>n or member&~available:return True
            decoded.add((member,available))
        masks=sorted(decoded)
        if (records+7)//8*len(masks)*(len(masks)-1)//2>256*1024**2:return True
        for i,(a,aa) in enumerate(masks):
            for b,ba in masks[i+1:]:
                common=aa&ba
                counts=((a&b).bit_count(),(a&common&~b).bit_count(),(b&common&~a).bit_count(),
                        (common&~(a|b)).bit_count(),(aa&~ba).bit_count(),(ba&~aa).bit_count(),
                        records-(aa|ba).bit_count())
                if any(0<count<minimum for count in counts):return True
    return False


def overlap_projection(value,aliases):
    """Exact aggregate authorization still does not authorize private identities."""
    if not isinstance(value,dict):return []
    output={key:value[key] for key in ('pair_limit','total_overlapping_pairs','omitted_pairs',
        'shortlist_union_support','selection_population') if type(value.get(key)) is int and value[key]>=0}
    output.update({key:value[key] for key in ('pair_coverage_complete','shortlist_pairs_complete',
        'shortlist_pairs_prioritized','counts_are_not_summed') if type(value.get(key)) is bool})
    output['pairs']=[]
    for pair in value.get('pairs',[]):
        if not isinstance(pair,dict) or pair.get('left') not in aliases or pair.get('right') not in aliases:
            # Incomplete legacy provenance must not imply complete public pairs.
            output['pair_coverage_complete']=False;output['shortlist_pairs_complete']=False
            continue
        row={key:pair[key] for key in ('intersection','union') if type(pair.get(key)) is int and pair[key]>=0}
        if type(pair.get('jaccard')) in {int,float} and 0<=pair['jaccard']<=1:row['jaccard']=pair['jaccard']
        row.update({key:pair[key] for key in ('left_contained','right_contained') if type(pair.get(key)) is bool})
        row.update(left=aliases[pair['left']],right=aliases[pair['right']]);output['pairs'].append(row)
    output['retained_pairs']=len(output['pairs'])
    return output


def project(result,disclosure=None):
    policy=disclosure or result.private['config']['disclosure']
    if isinstance(policy,dict):policy=DisclosureSpec.from_dict(policy)
    raw=result.to_private_dict();panel=raw['investigation'];candidates=panel.get('candidates',[]);assessments=panel.get('assessments',[])
    # A small component can be reconstructed by combining overlapping candidates.
    # Withhold the complete related family, not only its smallest displayed cell.
    protected=False
    for candidate in candidates:
        for record in [candidate.get(role,{}) for role in ('D','S')]+([candidate['selection_contribution']['evidence']] if candidate.get('selection_contribution') else []):
            counts=[record.get(k,0) for k in ('planned','available','members','nonmembers','unavailable','conditional_members','conditional_nonmembers')]
            counts.extend(record.get('sensitive_counts',[]))
            counts.extend(outcome_status_counts(record.get('outcome_status_states')).values())
            protected|=any(0<n<policy.minimum_component for n in counts)
            protected|=any(0<record.get(k,0)<policy.minimum_denominator for k in ('planned','available','conditional_members','conditional_nonmembers'))
        fidelity=candidate.get('explanation',{}).get('fidelity') or {}
        protected|=any(0<fidelity.get(k,0)<policy.minimum_component for k in
            ('true_positive','false_positive','false_negative','true_negative','unavailable','gate_members_without_surrogate'))
        protected|=any(0<fidelity.get(k,0)<policy.minimum_denominator for k in ('available','jointly_available'))
    for assessment in assessments:
        counts=assessment.get('support',{})
        protected|=any(isinstance(n,(int,float)) and 0<n<policy.minimum_component for n in counts.values())
        protected|=any(0<group.get(key,0)<policy.minimum_component for group in counts.get('ranking_class_support',[]) for key in ('independent_units','effective_units'))
        protected|=any(0<n<policy.minimum_component for n in assessment.get('sensitive_counts',[]))
        protected|=any(0<n<policy.minimum_component for n in outcome_status_counts(assessment.get('outcome_status_states')).values())
        protected|=any(0<counts.get(k,0)<policy.minimum_denominator for k in ('planned','available','conditional_members','conditional_nonmembers'))
    if not protected and policy.policy=='conservative_aggregates_v1':
        protected=related_membership_risk(result.private,candidates,assessments,policy.minimum_component)
    protected=protected and policy.policy=='conservative_aggregates_v1'
    aliases={c['id']:f'region_{i+1}' for i,c in enumerate(candidates)}
    if not candidates:aliases={a['candidate_id']:f'region_{i+1}' for i,a in enumerate(assessments)}
    public=[]
    for i,candidate in enumerate(candidates):
        item={'id':aliases[candidate['id']],'strategy':candidate['strategy'],'state':'exploratory',
              'objective':objective_label(candidate['objective']),
              'definition':'Protected frozen membership; exact gate retained locally','explanation':'Approximate explanation retained locally'}
        if not protected:
            for role in ('D','S'):
                record=candidate.get(role,{})
                item[role]={k:copy.deepcopy(record[k]) for k in ('planned','available','members','nonmembers','unavailable','conditional_members','conditional_nonmembers','effect','effect_state') if k in record}
                if record.get('outcome_status_states'):item[role]['outcome_status_states']=outcome_status_counts(record['outcome_status_states'])
        public.append(item)
    confirmed=[]
    for a in assessments:
        row={'hypothesis':aliases.get(a.get('candidate_id'),'frozen_region'),'state':a['state'],
             'strength':a.get('strength','descriptive'),'membership_scope':a.get('membership_scope'),
             'independence_qualification':independence_label(a.get('independence_qualification'))}
        if a.get('objective'):row['objective']=objective_label(a['objective'])
        if not protected:
            for key in ('interval','effect','effect_state','practical_threshold','support','reason','inference'):
                if key in a:row[key]=copy.deepcopy(a[key])
            if a.get('outcome_status_states'):row['outcome_status_states']=outcome_status_counts(a['outcome_status_states'])
        else:row.update(state='details_withheld',detail_disclosure='Related support and effect family withheld jointly')
        confirmed.append(row)
    overlap_disclosure={'state':'exact_aggregates_authorized'}
    if policy.policy=='conservative_aggregates_v1':
        overlap_disclosure={'state':'withheld','reason':'Conservative shareable overlap and unique union counts are retained locally; omission does not establish disjointness. Pair-cell checks alone do not qualify release of all higher-order overlap combinations.'}
    output={k:copy.deepcopy(raw[k]) for k in ('schema_version','methodology_id','analysis_id','generated_at','execution')}
    output.update(name='Failure discovery and investigation',audience='shareable',
                  task={'kind':raw['task']['kind'],'classes':[]},runs=[],outcomes={'scope':raw.get('outcomes',{}).get('scope') if raw.get('outcomes',{}).get('scope') in {'observed_labels','complete_population'} else 'Frozen declared outcome population'},comparison=None,
                  measurements=[],checks=[],findings=[{'code':'investigation_scope','priority':'Information','message':'Findings apply only to their recorded populations, assumptions and qualification envelope.'}],
                  coverage={'qualification':'Conditional membership, observation and independence scopes apply.','withheld_related_family':protected,'populations':[]},
                  investigation={'stage':panel['stage'],'candidates':public,'assessments':confirmed,
                     'strategies':[{k:v for k,v in s.items() if k in {'strategy','execution','qualification','search_complete','reason'}} for s in panel.get('strategies',[])],
                     'overlap':overlap_projection(panel.get('overlap'),aliases) if policy.policy=='exact_aggregates_v1' else [],
                     'overlap_disclosure':overlap_disclosure,
                     'history':[],'notes':[],'method_status':'Qualification is limited to recorded benchmark evidence.'},
                  disclosure={'policy':policy.policy,'minimum_denominator':policy.minimum_denominator,'minimum_component':policy.minimum_component,'learned_artifacts_exported':False})
    if panel.get('selection_policy')=='severity_material_excess_support_frontier_v2':output['investigation']['selection_policy']=panel['selection_policy']
    if any(s.get('strategy')=='landmark' for s in panel.get('strategies',[])):
        output['investigation']['landmark_qualification_evidence']=dict(LANDMARK_PROMOTION_EVIDENCE)
    output['projection_digest']=digest(output);return output
