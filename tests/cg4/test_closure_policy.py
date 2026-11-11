"""Founder scope revision protects new claims and preserves historical evidence."""
import copy
import json
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape


def test_capabilities_disclose_current_confirmation_standing():
    from confidenceguard.schema import capabilities
    policy=capabilities()['investigation']
    assert policy['closure_acceptance_revision']=='founder_approved_2026_10_28'
    assert policy['ranking_percentile_confirmation']=='refused_general_operating_envelope_not_qualified'
    assert policy['confirmation']==['registered_finite_sample_under_declared_assumptions']
    assert policy['entity_arm_finite']['general_entity_bootstrap_promoted'] is False


def test_actual_retained_approximate_assessment_renders_historical_warning():
    root=Path(__file__).resolve().parents[2]
    summary=json.loads((root/'validation/cg4/results/objective-ranking-ap-summary-v1.json').read_text())
    path=root/summary['trials'][0]['path'];original=path.read_bytes()
    row=json.loads(original)['assessments'][0];before=copy.deepcopy(row)
    assert row['strength']=='approximate'
    environment=Environment(loader=FileSystemLoader(root/'src/confidenceguard/templates'),
        autoescape=select_autoescape(['html']))
    html=environment.get_template('investigation_sections.html').render(result={
        'investigation':{'stage':'confirmation','assessments':[row]},'coverage':{},
        'outcomes':{'scope':'observed_labels'}})
    assert 'Historical approximate assessment' in html
    assert 'does not establish a new formal confirmation' in html
    assert row==before and path.read_bytes()==original
