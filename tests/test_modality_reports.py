"""Report Experience Stage 6: the M6 text, M7 image and M9 cross-representation reports on the shared contract. Every
finding is indexed; every abbreviated summary is disclosed and its retained entries listed in full; references stay
opaque and protected; source values and paths never appear by default; export evidence and the frozen executive summary
are unchanged. Presentation only."""
import hashlib
import html as htmlmod
import importlib
import json
import re
from pathlib import Path

import pytest

from datatrust.renderer import render_analysis_result
from datatrust.report_concepts import build_manifest
from datatrust.report_identity import family_of, identity

ROOT = Path(__file__).resolve().parents[1]
V = ROOT / 'validation'
CASES = {'m6_scifact': sorted((V / 'm6/results/reports').glob('*/scifact.json'))[0],
         'm7_classification': V / 'm7/results/reports/classification/final.json',
         'm7_overlay': V / 'm7/results/review_corrections/final-synthetic-overlay.json',
         'm9_pdf_financial': V / 'm9/results/reports/pdf_financial.json',
         'm9_docx_financial': V / 'm9/results/reports/docx_financial.json'}
PROJECTIONS = {'text': 'datatrust.text_presentation', 'image': 'datatrust.image_presentation', 'cross': 'datatrust.cross_presentation'}


class Stored:
    """A recorded export presented to the renderer as the milestone refresh scripts do (no reanalysis)."""
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
    out = {}
    for name, result in stored.items():
        value = result.to_dict()
        family = family_of(value)
        view = importlib.import_module(PROJECTIONS[family]).report_view(result)
        out[name] = (render_analysis_result(result), view, build_manifest(family, value, view))
    return out


def islands(html):
    return {m.group(1): json.loads(m.group(2)) for m in
            re.finditer(r'<script type="application/json" id="([^"]+)">(.*?)</script>', html, re.S) if m.group(1).endswith('-rows')}


@pytest.mark.parametrize('name', sorted(CASES))
def test_report_follows_the_manifest_and_every_link_resolves(stored, rendered, name):
    html, view, manifest = rendered[name]
    stored_policy = lambda _: ((stored[name].to_dict().get('profile') or {}).get('disclosure') or {}).get('policy')
    placed = re.findall(r'class="dt-term[^"]*" id="([^"]+)"', html)
    assert sorted(placed) == sorted(p['anchor'] for p in manifest['placements'])
    assert re.findall(r'class="dt-entry" id="concept-([^"]+)"', html) == [c['id'] for c in manifest['concepts']]
    ids = {c['id'] for c in manifest['concepts']}
    assert {'no_score', 'review_evidence', 'print_profile'} <= ids
    policy = stored_policy(manifest)
    assert ('protected_evidence' in ids) == (policy == 'references_only') and ('protected_evidence_disclosed' in ids) == (policy != 'references_only')
    ids = re.findall(r'\sid="([^"]+)"', html)
    assert len(ids) == len(set(ids))
    for href in re.findall(r'href="#([^"]+)"', html):
        assert href in set(ids), href
    assert 'Content-Security-Policy' in html


@pytest.mark.parametrize('name', sorted(CASES))
def test_every_finding_is_indexed_with_a_reader_facing_name(stored, rendered, name):
    html, view, _ = rendered[name]
    findings = stored[name].to_dict()['findings']
    assert [f['index'] for f in view['findings']] == list(range(len(findings)))
    text = htmlmod.unescape(html)
    for row in view['findings']:
        assert row['title'] in text and '_' not in row['title']     # never a raw family code
        assert row['anchor'] is None or f'id="{row["anchor"]}"' in html
    if findings and 'title' in findings[0]:
        assert [r['title'] for r in view['findings']] == [f['title'] for f in findings]


@pytest.mark.parametrize('name', sorted(CASES))
def test_no_raw_dumps_in_cells_or_complete_tables(rendered, name):
    html = rendered[name][0]
    visible = htmlmod.unescape(re.sub(r'<script.*?</script>|<style.*?</style>|<[^>]+>', ' ', html, flags=re.S))
    cells = [str(v) for data in islands(html).values() for row in data['rows'] for v in [row['entity'], *row['cells']]]
    for text in [visible, *cells]:
        assert not re.search(r"\{\s*['\"][^'\"]{1,40}['\"]\s*:", text), text[:200]


@pytest.mark.parametrize('name', sorted(CASES))
def test_abbreviated_summaries_are_disclosed_and_listed_in_full(rendered, name):
    html, view, _ = rendered[name]
    text = htmlmod.unescape(html)
    assert view['complete_tables'], 'each stored case abbreviates some retained evidence'
    data = islands(html)
    for unit in view['complete_tables']:
        rows = data[unit['table_id'] + '-rows']['rows'] if unit['island'] else unit['rows']
        assert rows
    for disclosure in view['disclosures'].values():
        assert disclosure.startswith('Summary view: ') and '(summary selection)' in disclosure
        assert '“Complete retained evidence:' in disclosure and 'analysis.json →' in disclosure
        assert disclosure in text
    assert '(historical display limit)' not in text                # these workflows have no PresentationLimits
    from datatrust.report_structured import REFERENCE
    for unit in view['complete_tables']:                            # opaque references are labelled protected (V4)
        rows = data[unit['table_id'] + '-rows']['rows'] if unit['island'] else []
        if any(REFERENCE.search(' '.join(map(str, [r['entity'], *r['cells']]))) for r in rows):
            assert 'source content: protected, local resolution only' in (unit['disclosure'] or ''), unit['title']


def test_m9_lists_every_retained_example(stored, rendered):
    html, view, _ = rendered['m9_pdf_financial']
    value = stored['m9_pdf_financial'].to_dict()
    data = islands(html)
    for i, e in enumerate(value['evidence']):
        details = e['data'].get('details') or []
        if len(details) > 5:
            unit = next(u for u in view['complete_tables'] if u['anchor'] == f"complete-{e['id']}-details".lower().replace('_', '-'))
            assert [r['entity'] for r in data[unit['table_id'] + '-rows']['rows']] == [d['target_id'] for d in details]


def test_m6_executive_summary_stays_frozen():
    """Export JSON fields (profile.summary and the action and finding counts) come from these two functions (plan I.3)."""
    import ast
    source = (ROOT / 'src/datatrust/text_presentation.py').read_text()
    body = {n.name: ast.get_source_segment(source, n) for n in ast.parse(source).body
            if isinstance(n, ast.FunctionDef) and n.name in ('display', 'executive_summary')}
    digest = hashlib.sha256((body['display'] + body['executive_summary']).encode()).hexdigest()
    assert digest == 'dfd9b90e2a3334c2fc0ba17a4a93020673869f8a33d0b4d1bb24dc8f1561bb18'


def _text_source(tmp_path):
    from datatrust import TextAuditSpec, TextFieldSpec, TextInputSpec, TextSourceSpec
    p = tmp_path / 'source.jsonl'
    p.write_text('\n'.join(json.dumps({'text': f'SECRET_MARKER shared passage {i % 2}', 'id': str(i)}) for i in range(4)))
    return TextAuditSpec((TextInputSpec('data', TextSourceSpec(str(p)), (TextFieldSpec('text', 'text'),), id_selector='id'),),
                         allowed_roots=(str(tmp_path),))


@pytest.mark.parametrize('profile', ['focused', 'complete'])
def test_text_exports_stay_private_and_bind_the_profile(tmp_path, profile):
    from datatrust import TextAnalysisConfig
    from datatrust.text import _execute
    result = _execute(_text_source(tmp_path), TextAnalysisConfig(near_duplicates=False, passages=False))
    before = result.json_text()
    out = tmp_path / 'report.html'
    art = result.generate_artifacts(out, json_path=tmp_path / 'report.json', print_profile=profile)
    html, exported = out.read_text(), json.loads(Path(art.json_path).read_text())
    assert result.json_text() == before
    assert 'SECRET_MARKER' not in html and str(tmp_path) not in html and 'source.jsonl' not in html
    meta = exported['profile']['export_identity']
    assert meta['canonical_html_sha256'] == hashlib.sha256(out.read_bytes()).hexdigest()
    assert meta['presentation_identity'] == identity('text')['presentation_id'] and meta['print_profile'] == profile
    assert art.qa_metadata['print_profile'] == profile


def test_cross_report_keeps_secret_values_and_paths_out(tmp_path):
    from datatrust import CrossRepresentationAnalysisConfig
    from datatrust.cross import _core, finalize
    from tests.m9.test_integrity import table_spec
    secret = 'PRIVATE_ID_SENTINEL'
    spec = table_spec(tmp_path, [{'id': secret, 'value': 1}, {'id': secret, 'value': 2}, {'value': 3}], [{'id': 'other', 'value': 0}])
    config = CrossRepresentationAnalysisConfig()
    result = finalize(_core(spec, config), spec, config)
    before = result.json_text()
    for profile in ('focused', 'complete'):
        html = render_analysis_result(result, print_profile=profile)
        assert secret not in html and str(tmp_path) not in html
        guide = html[html.index('id="understand"'):]
        assert secret not in guide and 'datatrust cross-evidence' in guide
    assert result.json_text() == before


def test_every_report_command_and_result_offers_the_print_profile():
    """Report Experience Stage 7: one print-profile choice across the CLI and every result type's export."""
    import inspect
    from click.testing import CliRunner
    from datatrust.cli import main
    for command in ('audit', 'compare', 'temporal', 'text', 'images', 'cross-representation'):
        assert '--print-profile' in CliRunner().invoke(main, [command, '--help']).output, command
    from datatrust.contracts import AnalysisResult
    from datatrust.m4_contracts import ComparisonResult
    from datatrust import cross_private, image_private, text_private
    for function in (AnalysisResult.generate_artifacts, ComparisonResult.generate_artifacts, ComparisonResult.generate_report,
                     text_private.generate_artifacts, image_private.generate_artifacts, cross_private.generate_artifacts):
        assert inspect.signature(function).parameters['print_profile'].default == 'focused'


@pytest.mark.parametrize('name', sorted(CASES))
def test_examples_quote_only_stored_values(stored, rendered, name):
    """Review L1: "In this report" examples for text, image and cross concepts quote values stored at their pointers."""
    value = stored[name].to_dict()
    def resolve(pointer):
        node = value
        for part in pointer.strip('/').split('/'):
            node = node[int(part)] if isinstance(node, list) else node[part]
        return node
    examples = [c['example'] for c in rendered[name][2]['concepts'] if c.get('example') and 'values' in c['example']]
    for example in examples:
        for pointer, stored_value in example['values'].items():
            assert resolve(pointer) == stored_value, pointer
    assert examples, 'each stored case quotes at least one example'


def test_every_opaque_reference_kind_is_labelled_protected(rendered):
    """Review M1: split, field and category references are protected like evidence and image references."""
    from datatrust.report_structured import REFERENCE
    for name in ('m6_scifact', 'm7_classification', 'm7_overlay'):
        html, view, _ = rendered[name]
        for unit in view['complete_tables']:
            text = json.dumps(unit.get('island') or unit['rows'])
            if re.search(r'\b(?:split|field|category)_[0-9a-f]{16,}\b', text):
                assert REFERENCE.search(text) and 'protected, local resolution only' in (unit['disclosure'] or ''), (name, unit['title'])
