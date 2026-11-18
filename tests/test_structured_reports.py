"""Report Experience Stage 4: the M3 and M4 reports on the shared contract. Historical display limits keep their
meaning; every capped table is disclosed and listed in full; every finding is indexed; explanations follow the
manifest. Presentation only."""
import copy
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from pypdf import PdfReader

from datatrust import DataTrust, DatasetSpec, TaskSpec
from datatrust.renderer import render_analysis_result
from datatrust.report_concepts import build_manifest
from datatrust.report_identity import family_of

ROOT = Path(__file__).resolve().parents[1]


class Stored:
    """A recorded result presented to the renderer as the milestone refresh scripts do (no reanalysis)."""
    def __init__(self, data):
        self._data, self.schema_version, self.source_paths = data, data['schema_version'], ()
        if 'inputs' in data:
            self.inputs = data['inputs']
    def to_dict(self):
        return self._data
    def __getattr__(self, key):
        try:
            return self._data[key]
        except KeyError as exc:
            raise AttributeError(key) from exc


@pytest.fixture(scope='module')
def multilabel(tmp_path_factory):
    rng = np.random.default_rng(5)
    rows = 300
    frame = pd.DataFrame({f'feature_{i:02d}': np.round(rng.normal(size=rows), 3) for i in range(45)})
    labels = [f'label_{i:02d}' for i in range(12)]
    for name in labels:
        frame[name] = rng.integers(0, 2, rows)
    path = tmp_path_factory.mktemp('m3') / 'multilabel.csv'
    frame.to_csv(path, index=False)
    return DataTrust.from_spec(DatasetSpec(str(path)), TaskSpec('multilabel_classification', targets=tuple(labels))).analyze_result()


@pytest.fixture(scope='module')
def m4_wide():
    return Stored(json.loads((ROOT / 'validation/m4/results/reports/wide/analysis.json').read_text()))


def contract(result):
    html = render_analysis_result(result)
    value = result.to_dict()
    from datatrust.presentation import report_view as m3_view
    from datatrust.m4_presentation import report_view as m4_view
    view = (m3_view if value['schema_version'] == '1.2' else m4_view)(result)
    manifest = build_manifest(family_of(value), value, view)
    placed = re.findall(r'class="dt-term[^"]*" id="([^"]+)"', html)
    assert sorted(placed) == sorted(p['anchor'] for p in manifest['placements'])
    assert re.findall(r'class="dt-entry" id="concept-([^"]+)"', html) == [c['id'] for c in manifest['concepts']]
    ids = re.findall(r'\sid="([^"]+)"', html)
    assert len(ids) == len(set(ids))
    for href in re.findall(r'href="#([^"]+)"', html):
        assert href in set(ids), href
    return html, view


def islands(html):
    return {m.group(1): json.loads(m.group(2)) for m in
            re.finditer(r'<script type="application/json" id="([^"]+)">(.*?)</script>', html, re.S) if m.group(1).endswith('-rows')}


def test_m3_capped_tables_are_disclosed_and_listed_in_full(multilabel):
    html, view = contract(multilabel)
    omissions = {o['topic']: o for o in view['qa']['presentation_omissions']}
    assert omissions, 'the fixture must exercise the historical display limits'
    data = islands(html)
    for topic, o in omissions.items():
        if topic not in view['disclosures']:
            continue   # actions and cohort availability use their own wording
        text = view['disclosures'][topic]
        assert text.startswith(f"Summary view: {o['displayed']:,} of {o['computed']:,} rows shown (historical display limit)")
        assert 'analysis.json →' in text and '“Complete tables:' in text
    for unit in view['complete_tables']:
        rows = data[unit['table_id'] + '-rows']['rows']
        table = next(t for t in view['task_tables'] + view['feature_tables'] + view['annotation_tables'] + view['appendix']
                     if unit['anchor'] == 'complete-' + re.sub(r'[^a-z0-9]+', '-', str(t['topic']).lower()).strip('-')[:60])
        assert len(rows) == len(table['all_rows']) > len(table['rows'])
        assert [r['entity'] for r in rows] == [str(r[0]) for r in table['all_rows']]


def test_m3_every_finding_is_indexed_beyond_the_action_limit(multilabel):
    html, view = contract(multilabel)
    titles = [f['title'] for f in multilabel.findings if f.get('code') != 'no_major_issues']
    assert [f['title'] for f in view['findings']] == titles
    for title in titles:
        assert title in html


def test_m3_complete_profile_prints_the_complete_tables(tmp_path, multilabel):
    before = multilabel.json_text()
    focused = multilabel.generate_artifacts(tmp_path / 'f.pdf', format='pdf')
    complete = multilabel.generate_artifacts(tmp_path / 'c.pdf', format='pdf', html_path=tmp_path / 'c.html', print_profile='complete')
    assert multilabel.json_text() == before
    focused_text = ' '.join(' '.join((p.extract_text() or '').split()) for p in PdfReader(focused.pdf_path).pages)
    complete_text = ' '.join(' '.join((p.extract_text() or '').split()) for p in PdfReader(complete.pdf_path).pages)
    last = 'feature_44'
    assert 'not printed in this profile' in focused_text
    assert last in complete_text
    assert len(PdfReader(complete.pdf_path).pages) > len(PdfReader(focused.pdf_path).pages)
    assert focused.qa_metadata['print_profile'] == 'focused' and complete.qa_metadata['print_profile'] == 'complete'


def test_m4_signal_first_order_keeps_the_historical_limit(m4_wide):
    from datatrust.m4_presentation import _signals, report_view
    value = m4_wide.to_dict()
    view = report_view(m4_wide)
    limit = value['context']['presentation']['feature_details']
    assert len(view['tables']['features']) == limit                        # the limit keeps its meaning
    signals = _signals(value)
    ranks = [signals.get((r['source'], r['column']), 3) for r in view['tables']['features']]
    assert ranks == sorted(ranks)                                            # finding-referenced rows first
    html, view = contract(m4_wide)
    assert view['disclosures']['features'].startswith(f'Summary view: {limit:,} of ')
    rows = islands(html)
    complete = next(u for u in view['complete_tables'] if u['anchor'] == 'complete-features')
    assert len(rows[complete['table_id'] + '-rows']['rows']) > limit


def test_m4_exact_names_survive_display_shortening():
    stored = Stored(json.loads((ROOT / 'validation/m4/results/reports/long_headers/analysis.json').read_text()))
    from datatrust.m4_presentation import report_view
    value = stored.to_dict()
    long_names = [c['name'] for p in [value['profile']] for c in p['columns'] if len(c['name']) > 96]
    view = report_view(Stored(copy.deepcopy(value)))
    shown = [r['column'] for r in view['tables']['features']]
    if long_names and view['complete_tables']:
        data = islands(render_analysis_result(stored))
        complete = next(u for u in view['complete_tables'] if u['anchor'] == 'complete-features')
        assert any(n in row['entity'] for row in data[complete['table_id'] + '-rows']['rows'] for n in long_names)
    assert all(len(c) <= 96 for c in shown)


def test_m4_reports_render_contract_for_every_stored_case():
    for case in ('clean', 'contaminated', 'shifted', 'partial', 'wide', 'long_headers'):
        contract(Stored(json.loads((ROOT / f'validation/m4/results/reports/{case}/analysis.json').read_text())))


def test_m4_rows_referenced_by_findings_are_printed_beyond_the_limit(m4_wide):
    """Review H1 (gate 2): every finding-referenced row is printed individually or in a disclosed group."""
    from datatrust.m4_presentation import _signals, report_view
    value = m4_wide.to_dict()
    view = report_view(m4_wide)
    signals = set(_signals(value))
    shown = {(r.get('source', r.get('pair')), r.get('column')) for t in ('features', 'targets', 'effects') for r in view['tables'][t]}
    beyond = signals - shown
    assert beyond, 'the fixture must have finding-referenced rows beyond the historical limit'
    unit = view['referenced']['features']
    printed = unit['disclosure_record']['print'] if unit['disclosure_record'] else {'individual': len(beyond), 'grouped': 0}
    assert printed['individual'] + printed['grouped'] == len(beyond)
    complete = report_view(m4_wide, 'complete')
    assert not complete['referenced']                                    # the complete table prints every row once (R5)
    html, _ = contract(m4_wide)
    assert 'rows referenced by findings beyond the summary view' in html


def test_running_section_header_names_the_section_a_page_opens_in():
    """Review L4: every page after the first carries its section title."""
    from weasyprint import HTML
    stored = Stored(json.loads((ROOT / 'validation/m4/results/reports/contaminated/analysis.json').read_text()))
    doc = HTML(string=render_analysis_result(stored)).render()
    headers = [[d.text for b in page._page_box.descendants() if type(b).__name__ == 'MarginBox'
                for d in b.descendants() if getattr(d, 'text', None)] for page in doc.pages]
    headings = set(re.findall(r'<h2[^>]*>(.*?)</h2>', render_analysis_result(stored), re.S))
    assert len(doc.pages) > 1
    for page in headers[1:]:
        assert any(text in {re.sub(r'<[^>]+>', '', h).strip() for h in headings} | {'Reading guide'} for text in page)
