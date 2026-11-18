"""Report Experience Stage 2: the classification, regression and unlabeled reports on the shared evidence contract.
Presentation only: these tests check what is printed, summarised and disclosed, never an analytical value."""
import copy
import html as htmlmod
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from pypdf import PdfReader

from datatrust import DataTrust, DatasetSpec, TaskSpec
from datatrust.renderer import render_analysis_result, write_html_report
from datatrust.report_layout import ROWS_PER_PAGE, accounting, plan_print, plan_screen
from datatrust.tabular_presentation import column_units, report_view

ROOT = Path(__file__).resolve().parents[1]
ADULT = 'annual_income_over_50k'


def text_of(markup):
    return ' '.join(htmlmod.unescape(re.sub(r'<[^>]+>', ' ', markup)).split())


def pdf_text(path):
    return ' '.join(' '.join((p.extract_text() or '').split()) for p in PdfReader(path).pages)


def analyse(path, task):
    return DataTrust.from_spec(DatasetSpec(str(path)), task).analyze_result()


@pytest.fixture(scope='module')
def flagged(tmp_path_factory):
    """Wide data where many columns share a problem: 120 mostly-missing, 60 constant, 40 heavy-tailed."""
    rng = np.random.default_rng(11)
    rows = 600
    data = {}
    for i in range(260):
        if i < 120:
            values = np.round(rng.normal(size=rows), 3); values[rng.random(rows) < 0.6] = np.nan
        elif i < 180:
            values = np.full(rows, 2.0)
        elif i < 220:
            values = np.round(rng.standard_cauchy(rows), 3)
        else:
            values = np.round(rng.normal(size=rows), 3)
        data[f'measure_{i:03d}'] = values
    frame = pd.DataFrame(data)
    frame['y'] = rng.choice(['yes', 'no'], rows)
    path = tmp_path_factory.mktemp('flagged') / 'flagged.csv'
    frame.to_csv(path, index=False)
    return analyse(path, TaskSpec('classification', target='y'))


CASES = [
    ('validation/data/mutations/strong_leakage.csv', TaskSpec('classification', target=ADULT)),
    ('validation/data/mutations/feature_missingness_100.csv', TaskSpec('classification', target=ADULT)),
    ('validation/data/prepared/german_credit.csv', TaskSpec('dataset_profile')),
    ('validation/regression/data/prepared/bike_hour.csv', TaskSpec('regression', target='cnt')),
]


@pytest.mark.parametrize('path,task', CASES)
@pytest.mark.parametrize('profile', ['focused', 'complete'])
def test_every_finding_is_printed_and_exports_never_reanalyse(tmp_path, monkeypatch, path, task, profile):
    result = analyse(ROOT / path, task)
    before = result.json_text()
    import datatrust.core
    monkeypatch.setattr(datatrust.core, 'run_analysis', lambda *a, **k: pytest.fail('export re-ran the analysis'))
    bundle = result.generate_artifacts(tmp_path / 'r.pdf', format='pdf', print_profile=profile)
    assert result.json_text() == before                                   # canonical analysis JSON unchanged
    text = pdf_text(bundle.pdf_path)
    for finding in result.findings:
        if finding.get('code') != 'no_major_issues':
            assert ' '.join(finding['title'].split()) in text, finding['title']
    assert f'Print profile: {profile}' in text or task.kind != 'classification'
    assert bundle.qa_metadata['print_profile'] == profile


def _printed_pairs(result, profile):
    """(entity, semantic field) for every printed value, individual or inside a summary."""
    same = {'missing_cell': 'missing', 'unique_cell': 'unique', 'outlier_cell': 'outliers'}
    units, _, _ = column_units(result.to_dict(), profile)
    pairs = []
    for unit in units:
        plan = plan_print(unit, profile)
        entity = {r.key: r.entity for r in unit.records}
        printed = [r.entity for r in plan.individual] + [entity[k] for s in plan.summaries for k in s.record_keys]
        for name in printed:
            pairs += [(name, same.get(f.key, f.key)) for f in unit.fields]
    return pairs, units


@pytest.mark.parametrize('profile', ['focused', 'complete'])
def test_no_value_is_printed_twice_for_the_same_column(flagged, profile):
    pairs, _ = _printed_pairs(flagged, profile)
    duplicates = {p for p in pairs if pairs.count(p) > 1}
    assert not duplicates, sorted(duplicates)[:5]


def test_focused_print_groups_repetition_and_accounts_for_every_column(flagged):
    units, signals, columns = column_units(flagged.to_dict(), 'focused')
    by_id = {u.unit_id: u for u in units}
    assert {'col-missingness', 'col-variation', 'col-all', 'col-numeric'} <= set(by_id)
    for unit in units:
        screen, printed = plan_screen(unit), plan_print(unit, 'focused')
        for plan in (screen, printed):
            a = accounting(unit, plan)
            assert a['individual'] + a['grouped'] + a['referenced'] == a['total']
        for group in printed.groups:
            limit = ROWS_PER_PAGE[unit.table_kind]
            assert len(group.individual) <= max(limit, len({r.signal.detail for r in group.individual if r.signal.detail}))
            assert group.summary is None or group.summary.count == group.total - len(group.individual)
    missing = plan_print(by_id['col-missingness'], 'focused')
    assert len(missing.individual) == ROWS_PER_PAGE['evidence-landscape'] and missing.summaries[0].count == 120 - len(missing.individual)
    ranked = [r.signal.measure for r in missing.individual]
    assert ranked == sorted(ranked, reverse=True)                          # most missing printed first
    assert not plan_print(by_id['col-all'], 'focused').individual          # the complete table is screen-only here
    complete = {u.unit_id: u for u in column_units(flagged.to_dict(), 'complete')[0]}
    assert len(plan_print(complete['col-all'], 'complete').individual) == len(columns)
    assert not plan_print(complete['col-missingness'], 'complete').individual   # signal tables would repeat the complete table


def test_pointers_and_anchors_in_disclosures_resolve(flagged):
    value = flagged.to_dict()
    markup = render_analysis_result(flagged)
    ids = set(re.findall(r'\sid="([^"]+)"', markup))
    view = report_view(value, 'focused')
    def resolve(pointer):
        node = value
        for part in pointer.strip('/').split('/'):
            node = node[int(part)] if isinstance(node, list) else node[part]
        return node
    disclosures = [u['disclosure_record'] for u in view['columns'].values() if u['disclosure_record']]
    assert disclosures
    for record in disclosures:
        for place in record['where']:
            if place['location'] == 'json':
                resolve(place['pointer'])
            if place['location'] == 'html_detail':
                assert place['anchor'] in ids
    for href in re.findall(r'href="#([^"]+)"', markup):
        assert href in ids


def test_flagged_pdf_length_follows_problems_not_columns(tmp_path, flagged):
    focused = flagged.generate_artifacts(tmp_path / 'f.pdf', format='pdf')
    complete = flagged.generate_artifacts(tmp_path / 'c.pdf', format='pdf', html_path=tmp_path / 'c.html', print_profile='complete')
    pages_f, pages_c = len(PdfReader(focused.pdf_path).pages), len(PdfReader(complete.pdf_path).pages)
    assert pages_f < pages_c
    text = pdf_text(focused.pdf_path)
    assert 'more columns, summarised' in text and 'Detailed view, not printed in this profile: all 261 columns are listed' in text


def test_frozen_legacy_report_and_the_current_opt_in(tmp_path):
    source = ROOT / 'validation/data/prepared/german_credit.csv'
    audit = DataTrust(str(source), 'credit_risk')
    legacy = Path(audit.generate_report(str(tmp_path / 'legacy.html')))
    assert '<meta http-equiv="Content-Security-Policy"' not in legacy.read_text()   # frozen bytes: no shell
    current = Path(audit.generate_report(str(tmp_path / 'current.html'), presentation='current'))
    assert '<meta http-equiv="Content-Security-Policy"' in current.read_text() and 'Column evidence' in current.read_text()
    with pytest.raises(ValueError):
        DataTrust.from_spec(DatasetSpec(str(source)), TaskSpec('dataset_profile')).generate_report(str(tmp_path / 'x.html'), presentation='legacy')


def test_cli_report_style_and_print_profile(tmp_path):
    from click.testing import CliRunner
    from datatrust.cli import main
    source = str(ROOT / 'validation/data/prepared/german_credit.csv')
    runner = CliRunner()
    plain = runner.invoke(main, ['audit', source, '--target', 'credit_risk', '--out', str(tmp_path / 'a.html')])
    assert plain.exit_code == 0, plain.output
    assert 'Content-Security-Policy' not in (tmp_path / 'a.html').read_text()
    current = runner.invoke(main, ['audit', source, '--target', 'credit_risk', '--out', str(tmp_path / 'b.html'), '--report-style', 'current',
                                   '--print-profile', 'complete'])
    assert current.exit_code == 0, current.output
    assert 'Print profile: complete' in text_of((tmp_path / 'b.html').read_text())
    refused = runner.invoke(main, ['audit', source, '--target', 'credit_risk', '--out', str(tmp_path / 'c.pdf'), '--format', 'pdf',
                                   '--report-style', 'legacy'])
    assert refused.exit_code != 0


def test_rendering_is_deterministic_and_escapes_column_names(tmp_path):
    frame = pd.DataFrame({'<script>alert(1)</script>': [1, 1, 1, 1, 1], 'ok': [1, 2, 3, 4, 50], 'y': ['a', 'b', 'a', 'b', 'a']})
    path = tmp_path / 'hostile.csv'
    frame.to_csv(path, index=False)
    result = analyse(path, TaskSpec('classification', target='y'))
    first, second = render_analysis_result(copy.deepcopy(result)), render_analysis_result(copy.deepcopy(result))
    assert first == second
    assert '<script>alert(1)' not in first
    for island in re.findall(r'<script type="application/json" id="[^"]+">(.*?)</script>', first, re.S):
        assert '</script' not in island.lower()
        json.loads(island)


def test_observation_lines_match_the_longest_column_name():
    from datatrust.tabular_presentation import entity_prefix
    names = {'a', 'a: b', 'income', 'income: net'}
    assert entity_prefix('a: b: 3 of 10 rows missing (30.0%).', names) == 'a: b'
    assert entity_prefix('income: net: 1 distinct value.', names) == 'income: net'
    assert entity_prefix('income: 2 of 9 rows.', names) == 'income'
    assert entity_prefix('Majority-class baseline 88.3%; majority : minority 7.55 : 1.', names) is None


def test_every_table_control_has_its_own_accessible_name(flagged):
    """Report Experience Stage 8: screen-reader users navigating form fields hear which table each control filters."""
    from datatrust.renderer import render_analysis_result
    html = render_analysis_result(flagged)
    tags = [t for t in re.findall(r'<input type="search"[^>]*>', html) if 'dt-guide-search' not in t]
    names = [(re.search(r'aria-label="([^"]*)"', t) or [None, ''])[1] for t in tags]
    assert names and all(n.startswith('Find in ') for n in names) and len(set(names)) == len(names)
    more = re.findall(r'id="[^"]+-more" aria-label="([^"]+)"', html)
    assert len(set(more)) == len(more) and all(m.startswith('Show more ') for m in more)
    for table_id, title_id in re.findall(r'<table class="dt-evidence[^"]*" id="([^"]+)" aria-labelledby="([^"]+)"', html):
        assert f'id="{title_id}"' in html


def test_every_element_id_is_unique_and_every_link_resolves(flagged):
    """Review M3: column tables and repeated rule rows used to share element ids."""
    from datatrust.renderer import render_analysis_result
    html = render_analysis_result(flagged)
    ids = re.findall(r'\sid="([^"]+)"', html)
    assert len(ids) == len(set(ids))
    for href in re.findall(r'href="#([^"]+)"', html):
        assert href in set(ids), href
    for data in re.findall(r'<script type="application/json" id="[^"]+">(.*?)</script>', html, re.S):
        anchors = [row['anchor'] for row in json.loads(data).get('rows', []) if row.get('anchor')]
        assert len(anchors) == len(set(anchors))


def test_long_recorded_lists_print_a_disclosed_count():
    """Review L6: a recorded sentence naming hundreds of columns keeps every name on screen and prints the first ones."""
    from datatrust.report_format import long_list
    names = [f'm{i:04d}' for i in range(400)]
    markup = str(long_list('Feature columns with at least 50% missing values require resolution: ' + ', '.join(names) + '.'))
    assert all(name in markup for name in names)                                  # the screen text is unchanged
    assert '<span class="dt-print-only"> … and 388 more' in markup and 'm0011<span class="dt-screen-only">' in markup
    assert str(long_list('a, b, c: <b>short</b>.')) == 'a, b, c: &lt;b&gt;short&lt;/b&gt;.'   # short lists untouched, escaped


def test_legacy_html_api_path_still_renders_the_frozen_report(tmp_path):
    """Review L5: write_report_artifacts(..., legacy_html=True) stays available for API compatibility."""
    from datatrust.renderer import write_report_artifacts
    result = analyse(ROOT / 'validation/data/prepared/german_credit.csv', TaskSpec('classification', target='credit_risk'))
    artifacts = write_report_artifacts(result, tmp_path / 'legacy.html', legacy_html=True)
    html = Path(artifacts.html_path).read_text()
    assert 'Technical Appendix' in html and 'id="understand"' not in html and 'data-dt-island' not in html
