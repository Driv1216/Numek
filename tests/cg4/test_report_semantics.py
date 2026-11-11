from pathlib import Path
import pytest
from jinja2 import Environment,FileSystemLoader,select_autoescape


@pytest.mark.parametrize('threshold,expected',[(0.,'0.0'),(.15,'0.15'),(None,'Not frozen')])
def test_canonical_report_distinguishes_zero_material_threshold_from_missing(threshold,expected):
    templates=Path(__file__).resolve().parents[2]/'src/confidenceguard/templates'
    environment=Environment(loader=FileSystemLoader(templates),autoescape=select_autoescape(['html']))
    candidate={'id':'synthetic','strategy':'structured','state':'exploratory',
        'objective':{'metric':'error_rate','direction':'higher','units':'fraction','comparator':'complement','practical_threshold':threshold}}
    html=environment.get_template('investigation_sections.html').render(result={
        'investigation':{'stage':'discovery','candidates':[candidate]},'coverage':{}})
    assert 'Practical threshold: '+expected+'.' in html
    if threshold is not None:assert 'Not frozen' not in html


def test_shareable_report_does_not_describe_a_withheld_threshold_as_absent():
    templates=Path(__file__).resolve().parents[2]/'src/confidenceguard/templates'
    environment=Environment(loader=FileSystemLoader(templates),autoescape=select_autoescape(['html']))
    candidate={'id':'region_1','strategy':'geometric','state':'exploratory',
        'objective':{'metric':'error_rate','direction':'higher','units':'fraction','comparator':'complement'}}
    html=environment.get_template('investigation_sections.html').render(result={
        'audience':'shareable','investigation':{'stage':'discovery','candidates':[candidate]},'coverage':{}})
    assert 'Practical threshold: Not disclosed.' in html and 'Not frozen' not in html


@pytest.mark.parametrize('current',[True,False])
def test_overlap_table_discloses_display_and_retention_limits(current):
    templates=Path(__file__).resolve().parents[2]/'src/confidenceguard/templates'
    environment=Environment(loader=FileSystemLoader(templates),autoescape=select_autoescape(['html']))
    overlap={'shortlist_union_support':100,'pairs':[{'left':'a','right':'b','intersection':20,'union':100,'jaccard':.2}]*50}
    if current:overlap.update(total_overlapping_pairs=100,omitted_pairs=50)
    html=environment.get_template('investigation_sections.html').render(result={
        'investigation':{'stage':'discovery','candidates':[],'overlap':overlap},'coverage':{}})
    assert 'Showing 40 of 50 retained overlapping pairs.' in html
    assert 'Absence from this table does not establish disjointness.' in html
    assert ('50 were omitted' in html) if current else ('Complete pair coverage was not recorded' in html)


@pytest.mark.parametrize('disclosed',[False,True])
def test_population_baseline_is_explained_only_with_its_definition_disclosed(disclosed):
    templates=Path(__file__).resolve().parents[2]/'src/confidenceguard/templates'
    environment=Environment(loader=FileSystemLoader(templates),autoescape=select_autoescape(['html']))
    candidate={'id':'region','strategy':'structured','state':'exploratory'}
    if disclosed:candidate['proposal_source']='declared_ceiling_population_baseline_v1'
    html=environment.get_template('investigation_sections.html').render(result={
        'investigation':{'stage':'discovery','candidates':[candidate]},'coverage':{}})
    assert ('includes the whole admitted population' in html)==disclosed


def test_empty_overlap_has_counts_without_an_empty_table_header():
    templates=Path(__file__).resolve().parents[2]/'src/confidenceguard/templates'
    environment=Environment(loader=FileSystemLoader(templates),autoescape=select_autoescape(['html']))
    html=environment.get_template('investigation_sections.html').render(result={'investigation':{
        'stage':'discovery','candidates':[],'overlap':{'shortlist_union_support':120,'pairs':[],
            'total_overlapping_pairs':0,'omitted_pairs':0}},'coverage':{}})
    assert '120 distinct opportunities' in html and 'Showing 0 of 0 retained' in html
    assert '<th>Regions</th>' not in html and 'class="overlap-intro"' in html


def test_observed_label_scope_and_status_counts_are_visible_beside_findings():
    templates=Path(__file__).resolve().parents[2]/'src/confidenceguard/templates'
    environment=Environment(loader=FileSystemLoader(templates),autoescape=select_autoescape(['html']))
    html=environment.get_template('investigation_sections.html').render(result={
        'outcomes':{'scope':'observed_labels'},'coverage':{},'investigation':{'stage':'confirmation',
            'assessments':[{'hypothesis':'region_1','state':'unreproduced','strength':'finite_sample',
                'membership_scope':'full_population','outcome_status_states':{'final':120,'pending':40,'withdrawn':40,'invalid':40},
                'independence_qualification':{'local_identity_scope':'canonical_history_keys_original_aliases_incomplete'}}]}})
    assert 'observed labels only' in html and 'do not establish failure rates or reliability for unobserved outcomes' in html
    assert 'pending 40' in html and 'withdrawn 40' in html and 'invalid 40' in html
    assert 'observed labels only; no conclusion about unobserved outcomes' in html[html.index('region_1'):]
    assert 'missing overlap records do not prove prior evidence was untouched' in html


def test_report_places_explanation_applicability_beside_conditional_fidelity():
    templates=Path(__file__).resolve().parents[2]/'src/confidenceguard/templates'
    environment=Environment(loader=FileSystemLoader(templates),autoescape=select_autoescape(['html']))
    candidate={'id':'region','strategy':'catboost','state':'exploratory','explanation':{
        'kind':'approximate','fidelity':{'precision':.75,'recall':.75,'jointly_available':14,
            'planned':20,'unavailable':6,'gate_members_without_surrogate':3}}}
    html=environment.get_template('investigation_sections.html').render(result={
        'coverage':{},'investigation':{'stage':'discovery','candidates':[candidate]}})
    assert '14 jointly applicable of 20 planned S observations; 6 unavailable' in html
    assert '3 gate members lack an applicable explanation' in html
    assert 'Fidelity uses joint applicability' in html
