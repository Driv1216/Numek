"""Negative method evidence is visible without changing gates or metric semantics."""
import hashlib
import json
from pathlib import Path

from confidenceguard import schema
from confidenceguard.investigation_contracts import LANDMARK_PROMOTION_EVIDENCE


def test_landmark_promotion_status_matches_retained_negative_evidence():
    path=Path(__file__).resolve().parents[2]/'validation/cg4/results/landmark-matched-comparison-v1/summary.json'
    summary=json.loads(path.read_text());record=LANDMARK_PROMOTION_EVIDENCE
    assert hashlib.sha256(path.read_bytes()).hexdigest()==record['evidence_sha256']
    assert record['status']==summary['status'] and record['promoted'] is False
    family=summary['families'][0]
    assert record['completed_pairs']==len(family['pairs'])==21
    assert record['maximum_possible_median_IoU_gain']==family['maximum_possible_40_pair_median']
    assert record['maximum_possible_median_IoU_gain']<record['required_median_IoU_gain']
    capabilities=schema.capabilities()['investigation']
    assert capabilities['landmark_qualification_evidence']==record
    assert capabilities['landmark_standing']=='original_NUMEK_failed_promotion_profile'
    capabilities['landmark_qualification_evidence']['promoted']=True
    assert schema.capabilities()['investigation']['landmark_qualification_evidence']['promoted'] is False


def test_canonical_landmark_report_states_failed_profile_without_universal_claim():
    from jinja2 import Environment,FileSystemLoader,select_autoescape
    templates=Path(__file__).resolve().parents[2]/'src/confidenceguard/templates'
    environment=Environment(loader=FileSystemLoader(templates),autoescape=select_autoescape(['html']))
    html=environment.get_template('investigation_sections.html').render(result={
        'investigation':{'stage':'discovery','strategies':[{'strategy':'landmark','qualification':'original_NUMEK_failed_promotion_profile'}]},'coverage':{}})
    assert 'failed promotion on its locked synthetic curved-region profile' in html
    assert 'does not establish universal inferiority' in html
