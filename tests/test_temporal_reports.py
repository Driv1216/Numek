"""Report Experience Stage 5: the M5 temporal report on the shared contract. Historical display limits keep their
meaning; every finding is indexed; every capped topic is disclosed and listed in full; recorded values read as labelled
text rather than JSON; explanations follow the manifest. Presentation only."""
import copy
import html as htmlmod
import json
import re
from pathlib import Path

import pytest
from pypdf import PdfReader

from datatrust.renderer import render_analysis_result, write_report_artifacts
from datatrust.report_concepts import build_manifest
from datatrust.temporal_presentation import display, report_view

ROOT = Path(__file__).resolve().parents[1]
CASES = {'retail': ROOT / 'validation/m5/reports/retail.json',
         'beijing': ROOT / 'validation/m5/reports/beijing.json',
         'long_headers': ROOT / 'validation/m5/reports/controlled/long_headers_reviewed.json'}


class Stored:
    """A recorded result presented to the renderer as the milestone refresh scripts do (no reanalysis)."""
    def __init__(self, data):
        self._data, self.schema_version, self.source_paths = data, data['schema_version'], ()
    def to_dict(self):
        return self._data
    def json_text(self):
        return json.dumps(self._data, ensure_ascii=False, indent=2, allow_nan=False)
    def __getattr__(self, key):
        try:
            return self._data[key]
        except KeyError as exc:
            raise AttributeError(key) from exc


@pytest.fixture(scope='module')
def stored():
    return {name: Stored(json.loads(path.read_text())) for name, path in CASES.items()}


@pytest.fixture(scope='module')
def rendered(stored):
    return {name: render_analysis_result(result) for name, result in stored.items()}


def islands(html):
    return {m.group(1): json.loads(m.group(2)) for m in
            re.finditer(r'<script type="application/json" id="([^"]+)">(.*?)</script>', html, re.S) if m.group(1).endswith('-rows')}


@pytest.mark.parametrize('name', sorted(CASES))
def test_m5_report_follows_the_manifest_and_every_link_resolves(stored, rendered, name):
    html, value = rendered[name], stored[name].to_dict()
    manifest = build_manifest('temporal', value, report_view(stored[name]))
    placed = re.findall(r'class="dt-term[^"]*" id="([^"]+)"', html)
    assert sorted(placed) == sorted(p['anchor'] for p in manifest['placements'])
    assert re.findall(r'class="dt-entry" id="concept-([^"]+)"', html) == [c['id'] for c in manifest['concepts']]
    ids = re.findall(r'\sid="([^"]+)"', html)
    assert len(ids) == len(set(ids))
    for href in re.findall(r'href="#([^"]+)"', html):
        assert href in set(ids), href


@pytest.mark.parametrize('name', sorted(CASES))
def test_every_m5_finding_is_indexed_beyond_the_action_limit(stored, rendered, name):
    value, html = stored[name].to_dict(), rendered[name]
    view = report_view(stored[name])
    findings = [f for f in value['findings'] if f.get('code') != 'no_major_issues']
    assert [f['title'] for f in view['findings']] == [f['title'] for f in findings]
    text = htmlmod.unescape(html)
    for finding in findings:
        assert finding['title'] in text
    cards = value['context']['presentation']['executive_actions']
    assert len(view['actions']) == min(cards, len(value['findings']))   # the historical limit keeps its meaning
    if len(findings) > cards:
        assert (f'Summary view: {cards} of {len(findings)} findings shown as action cards (historical display limit)'
                in text)


def test_beijing_discloses_findings_beyond_the_action_cards(stored):
    view = report_view(stored['beijing'])
    assert len(view['findings']) == 15 and view['omitted_actions'] == 10


@pytest.mark.parametrize('name', sorted(CASES))
def test_m5_cells_read_as_labelled_text_not_json(rendered, name):
    html = rendered[name]
    cells = [htmlmod.unescape(re.sub(r'<[^>]+>', '', c)).strip() for c in re.findall(r'<td[^>]*>(.*?)</td>', html, re.S)]
    for data in islands(html).values():
        cells += [str(v) for row in data['rows'] for v in [row['entity'], *row['cells']]]
    jsonish = [c for c in cells if re.match(r'^[\[{]\s*["\'{\[]', c) or re.search(r'":\s', c)]
    assert not jsonish, jsonish[:3]


def test_display_labels_nested_records():
    assert display({'format': 'csv', 'role': 'primary'}) == 'format: csv · role: primary'
    assert display(['a', 'b']) == 'a, b'
    assert display([{'id': 1}, {'id': 2}]) == '(id: 1); (id: 2)'
    assert display({'clock': None}) == 'clock: not set' and display([]) == 'none'
    assert display(None) == 'Unavailable / unknown'      # the historical top-level wording is kept


@pytest.mark.parametrize('name', sorted(CASES))
def test_m5_capped_topics_are_disclosed_and_listed_in_full(stored, rendered, name):
    html, view = rendered[name], report_view(stored[name])
    data = islands(html)
    capped = [t for t in view['topics'] if t['total_rows'] > len(t['rows'])]
    for topic in capped:
        text = view['disclosures'][topic['id']]
        assert text.startswith(f"Summary view: {len(topic['rows']):,} of {topic['total_rows']:,} rows shown (historical display limit)")
        assert '“Complete tables:' in text and 'analysis.json →' in text
        unit = next(u for u in view['complete_tables'] if u['anchor'] == 'complete-' + topic['id'])
        rows = data[unit['table_id'] + '-rows']['rows']
        assert len(rows) == topic['total_rows']
        assert [r['entity'] for r in rows] == [r[0] for r in topic['all_rows']]
    assert len(view['complete_tables']) >= len(capped)


def test_m5_complete_profile_prints_the_complete_tables(tmp_path, stored):
    result = stored['retail']
    before = result.json_text()
    focused = write_report_artifacts(result, tmp_path / 'f.pdf', format='pdf')
    complete = write_report_artifacts(result, tmp_path / 'c.pdf', format='pdf', html_path=tmp_path / 'c.html', print_profile='complete')
    assert result.json_text() == before
    pages = lambda bundle: [' '.join((p.extract_text() or '').split()) for p in PdfReader(bundle.pdf_path).pages]
    focused_pages, complete_pages = pages(focused), pages(complete)
    assert 'not printed in this profile' in ' '.join(focused_pages)
    assert len(complete_pages) > len(focused_pages)
    assert focused.qa_metadata['print_profile'] == 'focused' and complete.qa_metadata['print_profile'] == 'complete'
    for title in (f['title'] for f in result.to_dict()['findings']):
        assert ' '.join(title.split()) in ' '.join(focused_pages)
    guide = [i + 1 for i, p in enumerate(focused_pages) if 'Reading guide' in p and 'Plain-language explanations' in p]
    refs = [int(n) for n in re.findall(r'Reading guide, p\. ?(\d+)\)', ' '.join(focused_pages))]
    assert guide and refs and all(guide[0] <= n <= len(focused_pages) for n in refs)


def test_investigation_filters_keep_the_contract(stored):
    value = copy.deepcopy(stored['beijing'].to_dict())
    family = next(r['check_id'] for r in value['evidence'] if r['check_id'] == 'behavior_windows')
    view = report_view(value, family=family)
    manifest = build_manifest('temporal', value, view)
    assert manifest['concepts'] and all(t['rows'] or not t['all_rows'] for t in view['topics'])


@pytest.mark.parametrize('name', ['beijing', 'retail'])
def test_every_finding_has_printed_evidence_in_the_focused_profile(stored, name):
    """Review H1 (gate 2): rows of each finding's evidence record print even beyond the per-topic limit, and distinct
    findings are never merged into one group."""
    value = stored[name].to_dict()
    view = report_view(stored[name])
    in_summary = {row['ref'].split(' ')[0] for t in view['topics'] for row in t['rows']}
    individual = {row['entity'].split(' ')[0] for u in view['referenced'].values() for row in u['rows'] if row['type'] == 'record'}
    for finding in value['findings']:
        for ref in finding['evidence_refs']:
            assert ref in in_summary | individual, (finding['title'], ref)
    groups = [row['label'] for u in view['referenced'].values() for row in u['rows'] if row['type'] == 'group']
    distinct = {(f['title'], f.get('measurement')) for f in value['findings']}
    assert len(groups) <= sum(1 for _ in view['referenced']) * len(distinct)
    for label in groups:
        assert any(title in label for title, _ in distinct)


def test_m5_appendix_disclosure_states_screen_and_print_counts(stored):
    """Review L2: the appendix summary shows more rows on screen than it prints."""
    view = report_view(stored['beijing'])
    text = view['disclosures']['appendix']
    assert text.startswith(f"Summary view: {len(view['appendix']):,} of {view['appendix_total']:,} rows shown")
    assert f"print shows the first {view['appendix_print_rows']:,}" in text
