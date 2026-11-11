"""Shareable qualifications must not export protected exposure-ledger identities."""
import copy
import json
from pathlib import Path
from types import SimpleNamespace

from jinja2 import Environment, FileSystemLoader, select_autoescape
from confidenceguard.contracts import DisclosureSpec
from confidenceguard.investigation_disclosure import independence_label, project


def test_partial_local_identity_check_remains_qualified_without_private_aliases():
    value={'local_separation':'partially_checked',
        'local_identity_scope':'canonical_history_keys_original_aliases_incomplete',
        'original_source_aliases':['PRIVATE_SOURCE_ALIAS']}
    assert independence_label(value)=={k:v for k,v in value.items() if k!='original_source_aliases'}


def test_qualifications_preserve_limitations_without_identifiers_or_declarations():
    secret='CG4_PRIVATE_EXPOSURE_SENTINEL'
    independence={
        'local_separation':'system_checked','upstream':'declared_independent',
        'external_exposure':'declared_unexposed','exposure_continuity':'incomplete',
        'history_gap_basis':'current_scoped_declaration_not_system_verified_history',
        'ledger_gaps_declaration_qualified':['exposure_history_incomplete',secret],
        'ledger_enabled':True,'evidence_use':'predeclared_restatement_not_fresh_independent_evidence',
        'external_exposure_declaration_scope':'before_initial_H_access',
        'schedule_predeclared_and_locally_verified':True,
        'original_reservation_id':secret,'declaration_author':secret,'declaration_reason':secret,
        'future_protected_field':{'identity':secret}}
    raw={'schema_version':'confidenceguard.confirmation_assessment/1.0',
        'methodology_id':'failure_investigation_v1','analysis_id':'synthetic',
        'generated_at':'2026-10-25T00:00:00Z','execution':{'status':'completed'},
        'task':{'kind':'regression'},'investigation':{'stage':'confirmation','candidates':[],
            'assessments':[{'candidate_id':'protected_gate','state':'inconclusive',
                'strength':'descriptive','membership_scope':'supported_population',
                'support':{'planned':100,'available':100,'members':50,'nonmembers':50},
                'independence_qualification':independence}], 'notes':[secret]}}
    stub=SimpleNamespace(private={'config':{'disclosure':DisclosureSpec().to_dict()}},
                         to_private_dict=lambda:copy.deepcopy(raw))
    shared=project(stub); text=json.dumps(shared)
    assert secret not in text and 'original_reservation_id' not in text
    visible=shared['investigation']['assessments'][0]['independence_qualification']
    assert visible['exposure_continuity']=='incomplete'
    assert visible['history_gap_basis']=='current_scoped_declaration_not_system_verified_history'
    assert visible['evidence_use']=='predeclared_restatement_not_fresh_independent_evidence'
    assert visible['ledger_gaps_declaration_qualified']==['exposure_history_incomplete']
    assert raw['investigation']['assessments'][0]['independence_qualification']['original_reservation_id']==secret
    templates=Path(__file__).resolve().parents[2]/'src/confidenceguard/templates'
    env=Environment(loader=FileSystemLoader(templates),autoescape=select_autoescape(['html']))
    html=env.get_template('investigation_sections.html').render(result=shared)
    assert secret not in html and 'incomplete' in html


def test_qualification_projection_rejects_unexpected_values_conservatively():
    assert independence_label(None) is None
    assert independence_label({'local_separation':'private free-form value','ledger_enabled':1,
        'ledger_gaps_declaration_qualified':[{},None,'exposure_history_unavailable']})=={
            'ledger_gaps_declaration_qualified':['exposure_history_unavailable']}
