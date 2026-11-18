"""Report Experience Stage 3: the concept catalogue, contextual examples and the per-report concept manifest
("Understand this report"). Presentation only."""
import base64
import copy
import hashlib
import html as htmlmod
import re
from pathlib import Path

import pandas as pd
import pytest
from pypdf import PdfReader

from datatrust import DataTrust, DatasetSpec, TaskSpec
from datatrust import report_identity as rid
from datatrust.renderer import render_analysis_result
from datatrust.report_concepts import CATALOGUE, CONCEPTS, FINDING_CONCEPTS, build_manifest, catalogue_bytes
from datatrust.report_context import BUILDERS, Example, Unavailable
from datatrust.report_layout import format_value
from datatrust.tabular_presentation import report_view

ROOT = Path(__file__).resolve().parents[1]
CASES = {
    'classification': ('validation/data/prepared/german_credit.csv', TaskSpec('classification', target='credit_risk')),
    'unlabeled': ('validation/data/prepared/german_credit.csv', TaskSpec('dataset_profile')),
    'regression': ('validation/regression/data/prepared/bike_hour.csv', TaskSpec('regression', target='cnt')),
}


@pytest.fixture(scope='module')
def results():
    return {family: DataTrust.from_spec(DatasetSpec(str(ROOT / path)), task).analyze_result() for family, (path, task) in CASES.items()}


def manifest_of(family, result):
    value = result.to_dict()
    return build_manifest(family, value, report_view(value))


def resolve(value, pointer):
    node = value
    for part in pointer.strip('/').split('/'):
        node = node[int(part)] if isinstance(node, list) else node[part]
    return node


@pytest.mark.parametrize('family', sorted(CASES))
def test_rendered_placements_and_guide_entries_are_exactly_the_manifest(results, family):
    result = results[family]
    html = render_analysis_result(result)
    manifest = manifest_of(family, result)
    assert manifest == manifest_of(family, copy.deepcopy(result))                     # deterministic
    placed = re.findall(r'class="dt-term[^"]*" id="([^"]+)"', html)
    assert sorted(placed) == sorted(p['anchor'] for p in manifest['placements'])
    entries = re.findall(r'class="dt-entry" id="concept-([^"]+)"', html)
    assert entries == [c['id'] for c in manifest['concepts']]
    ids = set(re.findall(r'\sid="([^"]+)"', html))
    for href in re.findall(r'href="#([^"]+)"', html):
        assert href in ids, href
    firsts = [p for p in manifest['placements'] if p['first']]
    assert len(firsts) == len(manifest['concepts']) == len({p['concept'] for p in firsts})
    # The guide sits before the technical appendix, yet includes the terms the appendix introduces after it.
    guide = html.index('id="understand"')
    later = [p for p in firsts if html.index(f'id="{p["anchor"]}"') > guide]
    assert later and all(f'id="concept-{p["concept"]}"' in html for p in later)


@pytest.mark.parametrize('family', sorted(CASES))
def test_without_script_every_term_link_reaches_its_definition(results, family):
    html = render_analysis_result(results[family])
    manifest = manifest_of(family, results[family])
    for p in manifest['placements']:
        entry = re.search(r'<div class="dt-entry" id="concept-%s".*?</div>' % re.escape(p['concept']), html, re.S).group(0)
        definition = manifest['by_id'][p['concept']]['definition']
        assert htmlmod.escape(definition, quote=False) in entry or definition in htmlmod.unescape(entry)


def test_methodology_variants_word_the_iqr_rule_for_each_policy():
    concept = CATALOGUE['iqr_outliers']
    legacy = concept.resolved('classification_legacy_2026_08_13')
    finite = concept.resolved('unlabeled_csv_profile_v1')
    regression = concept.resolved('tabular_regression_v1')
    assert 'all rows' in legacy['definition'] and 'non-finite values count as outside' in legacy['definition']
    assert 'finite values only' in finite['definition'] and 'at least four finite values' in finite['definition']
    assert regression['definition'] == finite['definition'] and regression['methodology_ref'] != finite['methodology_ref']


def test_every_methodology_reference_is_a_heading():
    headings = {line.lstrip('#').strip() for line in (ROOT / 'METHODOLOGY.md').read_text().splitlines() if line.startswith('#')}
    for concept in CONCEPTS:
        refs = [concept.methodology_ref] + [v.methodology_ref for v in concept.variants.values() if v.methodology_ref]
        for ref in refs:
            assert ref in headings, (concept.id, ref)


def test_catalogue_rules():
    for concept in CONCEPTS:
        assert len(concept.definition.split()) <= 60, concept.id
        if concept.example_builder:
            assert concept.example_builder in BUILDERS, concept.id
        if concept.depth == 'interpretive':
            assert concept.means and concept.does_not_mean
        for word in ('should ', 'must ', 'remove ', 'drop ', 'impute'):
            assert word not in (concept.definition + ' ' + (concept.means or '')).lower(), (concept.id, word)   # no advice
    for codes in FINDING_CONCEPTS.values():
        assert all(c in CATALOGUE for c in codes)


NUMBER = re.compile(r'-?\d[\d,]*(?:\.\d+)?')


@pytest.mark.parametrize('family', sorted(CASES))
def test_every_example_quotes_recorded_values_only(results, family):
    value = results[family].to_dict()
    manifest = manifest_of(family, results[family])
    examples = [c['example'] for c in manifest['concepts'] if c['example']]
    assert any('text' in e for e in examples)
    for example in examples:
        if 'unavailable' in example:
            assert example['unavailable'].strip()
            continue
        shown = set()
        for pointer, stored in example['values'].items():
            assert resolve(value, pointer) == stored, pointer
            shown |= {format_value(stored), str(stored)}
        wording = re.sub(r'\bQ[13]\b', '', example['text']).replace(' : 1.', '.')   # fixed wording, not quoted values
        for number in NUMBER.findall(wording):
            if number in ('1.5',):   # the methodology's constant, not a recorded value
                continue
            assert number in shown or any(number in s for s in shown if isinstance(s, str)), (number, example['text'])


def test_unavailable_examples_state_a_reason(tmp_path):
    frame = pd.DataFrame({'x': [1, 2, 3, 4, 5], 'y': ['a', 'b', 'a', 'b', 'a']})
    path = tmp_path / 'clean.csv'
    frame.to_csv(path, index=False)
    value = DataTrust.from_spec(DatasetSpec(str(path)), TaskSpec('classification', target='y')).analyze_result().to_dict()
    for name in ('missingness', 'guardrail', 'high_cardinality', 'leakage_review'):
        example = BUILDERS[name](value)
        assert isinstance(example, (Example, Unavailable))
        if isinstance(example, Unavailable):
            assert example.reason.endswith('.') and len(example.reason) > 20


def test_hostile_column_names_stay_inert_in_examples_and_guide(tmp_path):
    hostile = '<img src=x onerror=alert(1)>'
    frame = pd.DataFrame({hostile: [1, 2, 3, 4, 5, 6, 7, 8, 9, 400], 'y': ['a', 'b'] * 5})
    path = tmp_path / 'hostile.csv'
    frame.to_csv(path, index=False)
    result = DataTrust.from_spec(DatasetSpec(str(path)), TaskSpec('classification', target='y')).analyze_result()
    html = render_analysis_result(result)
    assert hostile not in html and '&lt;img src=x onerror=alert(1)&gt;' in html
    scripts = re.findall(r'<script(?![^>]*application/json)[^>]*>(.*?)</script>', html, re.S)
    assert len(scripts) == 1
    digest = base64.b64encode(hashlib.sha256(scripts[0].encode()).digest()).decode()
    assert f"sha256-{digest}" in htmlmod.unescape(html)


def test_catalogue_entries_are_part_of_their_families_identity_only():
    base = {f: rid.compute_digest(f) for f in rid.FAMILIES}
    def perturbed(target):
        return {f: rid.compute_digest(f, read_catalogue=lambda family: catalogue_bytes(family) + (b'x' if family == target else b''))
                for f in rid.FAMILIES}
    after = perturbed('classification')
    assert {f for f in base if base[f] != after[f]} == {'classification'}
    for family in ('text', 'image', 'cross'):                                  # each Stage 6 workflow carries its own entries
        assert {f for f in base if base[f] != perturbed(family)[f]} == {family}


def test_printed_reading_guide_resolves_every_page_reference(tmp_path, results):
    bundle = results['classification'].generate_artifacts(tmp_path / 'r.pdf', format='pdf')
    pages = [' '.join((p.extract_text() or '').split()) for p in PdfReader(bundle.pdf_path).pages]
    text = ' '.join(pages)
    guide = [i + 1 for i, p in enumerate(pages) if 'Reading guide' in p and 'Plain-language explanations' in p]
    assert guide
    refs = re.findall(r'Reading guide, p\. ?(\d*)\)', text)
    assert refs and all(refs) and all(int(r) >= guide[0] for r in refs)
    for leaked in ('Find a term', 'More in Understand this report', 'Understand this report —'):
        assert leaked not in text


def test_rewording_one_workflows_concept_changes_only_that_workflows_identity(monkeypatch):
    from dataclasses import replace
    import datatrust.report_catalogue as catalogue
    base = {f: rid.compute_digest(f) for f in rid.FAMILIES}
    reworded = tuple(replace(c, definition=c.definition + ' Reworded.') if c.id == 'split_overlap' else c for c in catalogue.CONCEPTS)
    monkeypatch.setattr(catalogue, 'CONCEPTS', reworded)
    after = {f: rid.compute_digest(f) for f in rid.FAMILIES}
    assert {f for f in base if base[f] != after[f]} == {'m4'}
    assert ('module', 'datatrust.report_catalogue') not in [d for f in rid.FAMILIES for d in rid.dependencies(f)]
