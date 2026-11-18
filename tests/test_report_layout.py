"""Report Experience Stage 1: the shared evidence-presentation contract, per-workflow presentation identity and the
shared shell. Presentation only: no analytical result is computed or changed here."""
import base64
import hashlib
import html as htmlmod
import json
import random
import re
from dataclasses import replace
from pathlib import Path

import pytest

from datatrust import report_identity as rid
from datatrust.report_layout import (
    ROWS_PER_PAGE, SUMMARY_ROWS, AccountingError, Field, FindingRef, Plan, Record, Signal, Unit, accounting,
    check_partition, disclosure, distinct_records, finding_unit, group_checks, locations, plan_print, plan_screen,
    render_unit, significance,
)

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / 'src/datatrust/templates'
FIELDS = (Field('missing', 'Missing', 'quantity'), Field('rate', 'Missing %', 'quantity'), Field('dtype', 'Type', 'category'),
          Field('source', 'Source', 'scope'), Field('note', 'Note', 'text'))


def record(n, signal=None, group=('feature', 'float64'), **values):
    base = {'missing': n % 17, 'rate': round((n % 17) / 3, 2), 'dtype': ['float64', 'int64', 'object'][n % 3],
            'source': ['train', 'test'][n % 2], 'note': f'note {n % 4}'}
    base.update(values)
    return Record(f'r{n}', f'column_{n:04d}', base, n, f'/profile/columns/{n}', signal, group)


def synthetic_unit(rng, size, view='V2', screen_limit=None):
    severities = ['High', 'Moderate', 'Low', None]
    records = []
    for n in range(size):
        if rng.random() < 0.55:
            details = [None, None, None, f'expr {rng.randrange(4)}']
            signal = Signal(rng.choice(['missing', 'outliers', 'constant']), rng.choice(severities), rng.choice(['', 'train']),
                            rng.choice(['', 'rule_a']), rng.choice(['', 'heuristic_candidate']),
                            rng.choice([None, rng.random() * 100]), rng.choice(details))
        else:
            signal = None
        records.append(record(n, signal, group=(rng.choice(['feature', 'target']), rng.choice(['float64', 'object']))))
    rng.shuffle(records)
    return Unit('u', 'Synthetic', view, FIELDS, tuple(records), noun='columns', pointer='/profile/columns',
                html_anchor='ev-columns', html_label='Technical evidence §B.2', screen_limit=screen_limit)


@pytest.mark.parametrize('seed', range(40))
def test_invariants_hold_for_every_profile_and_guideline(seed):
    rng = random.Random(seed)
    unit = synthetic_unit(rng, rng.choice([0, 1, 3, 4, 30, 120, 400]))
    for profile in ('focused', 'complete'):
        for pages in (1, 2):
            plan = plan_print(unit, profile, pages)
            check_partition(unit, plan)                                    # I1
            acct = accounting(unit, plan)
            assert acct['individual'] + acct['grouped'] + acct['referenced'] == acct['total'] == len(unit.records)
            groups = {r.signal.key for r in unit.records if r.signal}
            assert {g.key for g in plan.groups} == groups                   # R1: every distinct group appears
            for group in plan.groups:
                members = [r for r in unit.records if r.signal and r.signal.key == group.key]
                assert group.total == len(members)
                assert all(r.signal.key == group.key for r in group.individual)   # R2a: never merged across keys
                assert list(group.individual) == sorted(group.individual, key=significance)   # R2b order
                details = {r.signal.detail for r in members if r.signal.detail is not None}
                assert details <= {r.signal.detail for r in group.individual}   # distinct meaning always printed
                if profile == 'complete':
                    assert group.summary is None
                else:
                    limit = pages * ROWS_PER_PAGE[unit.table_kind]
                    repetitive = [r for r in group.individual if r.signal.detail is None or
                                  [m.key for m in group.individual if m.signal.detail == r.signal.detail][0] != r.key]
                    assert len(repetitive) <= max(0, limit - len(details)) or group.summary is None
                    if group.summary:
                        assert len(group.individual) >= min(limit, len(members) - group.summary.count)
            if profile == 'complete':
                assert not plan.summaries and len(plan.individual) == len(unit.records)


def test_space_neutral_rule_for_records_without_findings():
    small = Unit('s', 'S', 'V2', FIELDS, tuple(record(n) for n in range(SUMMARY_ROWS)))
    large = Unit('l', 'L', 'V2', FIELDS, tuple(record(n) for n in range(SUMMARY_ROWS + 1)))
    assert len(plan_print(small).individual) == SUMMARY_ROWS and not plan_print(small).summaries
    summary, = plan_print(large).summaries
    assert summary.kind == 'signal-free' and summary.count == SUMMARY_ROWS + 1


def test_summaries_use_only_stored_values_in_a_form_suited_to_each_field():
    records = tuple(record(n) for n in range(40))
    unit = Unit('s', 'S', 'V2', FIELDS, records)
    summary, = plan_print(unit).summaries
    fields = dict(summary.fields)
    stored = {f.key: [r.values[f.key] for r in records] for f in FIELDS}
    for key in ('missing', 'rate'):
        s = fields[key]
        assert s['kind'] == 'range' and s['min'] == min(stored[key]) and s['max'] == max(stored[key])
        assert next(r for r in records if r.entity == s['min_entity']).values[key] == s['min']
        assert next(r for r in records if r.entity == s['max_entity']).values[key] == s['max']
    assert fields['dtype']['kind'] == 'tally' and sum(c for _, c in fields['dtype']['counts']) == 40
    assert fields['source']['kind'] == 'scopes' and dict(fields['source']['counts']) == {'train': 20, 'test': 20}
    assert fields['note'] == {'kind': 'distinct', 'distinct': 4}          # free text is never summarised as values
    assert set(fields) == {f.key for f in FIELDS} and not {'mean', 'median'} & {k for s in fields.values() for k in s}


def test_treatment_depends_on_recorded_signals_and_order_never_on_values():
    rng = random.Random(7)
    unit = synthetic_unit(rng, 200)
    altered = replace(unit, records=tuple(replace(r, values={k: 'x' for k in r.values}) for r in unit.records))
    assert plan_print(unit).treatment() == plan_print(altered).treatment()
    shuffled = replace(unit, records=tuple(sorted(unit.records, key=lambda r: r.key, reverse=True)))
    assert plan_print(unit).treatment() == plan_print(shuffled).treatment()     # deterministic, input order free


def test_historical_display_limit_keeps_its_meaning_and_is_disclosed():
    unit = Unit('v1', 'Features', 'V1', FIELDS, tuple(record(n) for n in range(412)), noun='features',
                pointer='/profile/sources/dataset/columns', html_anchor='ev-features', html_label='Technical evidence §B.3',
                screen_limit=20)
    screen, printed = plan_screen(unit), plan_print(unit)
    assert [r.key for r in screen.individual] == [r.key for r in unit.records[:20]] == [r.key for r in printed.individual]
    assert len(screen.referenced) == 392 and not screen.summaries
    text = disclosure(unit, screen, printed)['text']
    assert text.startswith('Summary view: 20 of 412 features shown (historical display limit)')
    assert 'Technical evidence §B.3 in this HTML file' in text and 'analysis.json → /profile/sources/dataset/columns' in text
    with pytest.raises(ValueError):
        Unit('bad', 'B', 'V2', FIELDS, (), screen_limit=5)


def test_locations_disclosures_and_distinct_totals():
    unit = Unit('cols', 'Columns', 'V2', FIELDS, tuple(record(n) for n in range(50)), noun='columns',
                pointer='/profile/columns', html_anchor='ev-cols', html_label='§B.2')
    screen, printed = plan_screen(unit), plan_print(unit)
    places = locations([unit], [screen, printed])
    assert all({'json', 'html_detail', 'pdf'} <= v for v in places.values())   # grouped in print still lands in the PDF
    record_ = disclosure(unit, screen, printed)
    assert record_['print']['grouped'] == 50 and record_['print']['individual'] == 0
    assert record_['text'] == ('Detailed view, print: 50 columns computed · 0 printed individually · 50 summarised below · every row: '
                               '§B.2 in this HTML file and analysis.json → /profile/columns')
    assert disclosure(unit, screen, plan_print(unit, 'complete')) is None    # nothing grouped or referenced
    protected = replace(unit, unit_id='p', records=tuple(replace(r, protected=True) for r in unit.records))
    assert 'protected, local resolution only' in disclosure(protected, plan_screen(protected), plan_print(protected))['text']
    assert all('protected' in v for k, v in locations([protected], [plan_screen(protected)]).items())
    other = replace(unit, unit_id='other')
    assert distinct_records([unit, other]) == 50                              # I3: never the sum of unit counts


def test_coverage_is_carried_as_a_qualifier_never_counted():
    unit = Unit('c', 'C', 'V2', FIELDS, tuple(record(n) for n in range(10)), pointer='/x',
                coverage=('search bounded: 12,400 of 18,000 pairs examined',))
    record_ = disclosure(unit, plan_screen(unit), plan_print(unit))
    assert record_['print']['individual'] + record_['print']['grouped'] == 10
    assert record_['text'].endswith('Coverage: search bounded: 12,400 of 18,000 pairs examined')


def test_partition_violations_are_detected():
    unit = Unit('u', 'U', 'V2', FIELDS, tuple(record(n) for n in range(3)))
    with pytest.raises(AccountingError):
        check_partition(unit, Plan('u', 'print', 'focused', unit.records[:2], (), unit.records[1:]))
    with pytest.raises(AccountingError):
        check_partition(unit, Plan('u', 'print', 'focused', unit.records[:2], (), ()))
    with pytest.raises(ValueError):
        Unit('dup', 'D', 'V2', FIELDS, (record(1), record(1)))


def test_finding_index_never_merges_findings_that_read_differently():
    findings = [FindingRef(f'f{i}', title, 'Moderate', f'/findings/{i}', i, scope=scope, trigger=code)
                for i, (title, scope, code) in enumerate([('Window effects', 'PM10', 'window_effects'),
                                                          ('Window effects', 'TEMP', 'window_effects'),
                                                          ('Equal-value runs', 'PM10', 'runs'),
                                                          ('Window effects, second window pair', 'PM10', 'window_effects')])]
    unit = finding_unit(findings)
    plan = plan_print(unit)
    assert {r.key for r in plan.individual} == {'f0', 'f1', 'f2', 'f3'}    # every finding printed
    assert len(plan.groups) == 3 and not plan.summaries                     # scope and code separate groups
    pm10, = [g for g in plan.groups if g.key[1:3] == ('PM10', 'window_effects')]
    assert {r.key for r in pm10.individual} == {'f0', 'f3'}                 # same key, different reading: both printed
    many = finding_unit([FindingRef(f'g{i}', 'Equal-value run', 'Low', f'/findings/{i}', i, trigger='runs') for i in range(200)])
    many_plan = plan_print(many)
    assert len(many_plan.groups) == 1 and many_plan.summaries[0].count == 200 - ROWS_PER_PAGE['register-portrait']


def test_group_checks_matches_the_m3_ledger_exactly():
    from datatrust import AnalysisConfig, DataTrust, DatasetSpec, TaskSpec
    manifest = json.loads((ROOT / 'validation/m3/manifest.json').read_text())['datasets']['linnerud']
    result = DataTrust.from_spec(DatasetSpec(str(ROOT / 'validation/m3' / manifest['file'])), TaskSpec.from_dict(manifest['task']),
                                 AnalysisConfig.from_dict(manifest['config'])).analyze_result()
    from collections import defaultdict
    groups = defaultdict(list)                                                # the M3 projection's former inline code
    for c in result.checks:
        groups[(c.check_id, str(getattr(c.applicability, 'value', c.applicability)), str(getattr(c.execution, 'value', c.execution)), c.reason)].append(c.scope)
    expected = []
    for (check, app, execution, reason), scopes in groups.items():
        unique = list(dict.fromkeys(scopes))
        expected.append([check.replace('_', ' '), f'{len(scopes)} checks; {len(unique)} scopes: ' + ', '.join(unique[:3]) + (' ...' if len(unique) > 3 else ''),
                         app, execution, reason or 'Completed within declared scope'])
    assert group_checks(result.checks) == expected
    assert group_checks(result.to_dict()['checks']) == expected


# ——— Presentation identity ———

def test_identities_match_their_pins():
    pins = json.loads((ROOT / 'tests/fixtures/presentation_identities.json').read_text())
    assert pins['print_policy'] == rid.PRINT_POLICY_VERSION
    assert {f: rid.identity(f)['presentation_id'] for f in rid.FAMILIES} == pins['families']


def _perturbed(change):
    """Every family's digest with one input changed in memory."""
    def read_template(name):
        data = (TEMPLATES / name).read_bytes()
        return data + b'<!-- changed -->' if change == ('template', name) else data
    def read_module(name):
        data = rid._module_bytes(name)
        return data + b'\n# changed\n' if change == ('module', name) else data
    def read_function(name):
        data = rid._function_source(name)
        return data + b'# changed' if change == ('function', name) else data
    return {f: rid.compute_digest(f, read_template=read_template, read_module=read_module, read_function=read_function)
            for f in rid.FAMILIES}


def test_identity_is_dependency_aware():
    base = {f: rid.compute_digest(f) for f in rid.FAMILIES}
    def changed(change):
        after = _perturbed(change)
        return {f for f in base if after[f] != base[f]}
    own = {'regression': 'regression_report.html', 'unlabeled': 'unlabeled_report.html', 'm3': 'm3_report.html',
           'm4': 'm4_report.html', 'temporal': 'temporal_report.html', 'text': 'text_report.html',
           'image': 'image_report.html', 'cross': 'cross_report.html', 'classification': 'classification_report.html'}
    for family, template in own.items():
        assert changed(('template', template)) == {family}
    for family, module in {'m3': 'datatrust.presentation', 'm4': 'datatrust.m4_presentation',
                           'temporal': 'datatrust.temporal_presentation', 'text': 'datatrust.text_presentation',
                           'image': 'datatrust.image_presentation', 'cross': 'datatrust.cross_presentation'}.items():
        assert changed(('module', module)) == {family}
    assert changed(('template', 'report.html')) == set()                     # the frozen legacy report is outside every family
    assert changed(('module', 'datatrust.tabular_presentation')) == {'classification', 'regression', 'unlabeled'}
    assert changed(('template', '_tabular_layers.html')) == {'classification', 'regression', 'unlabeled'}
    assert changed(('template', '_report_base.css.html')) == {'classification', 'regression', 'unlabeled'}
    assert changed(('template', 'provenance.html')) == {'classification', 'regression', 'unlabeled', 'm3'}
    assert changed(('module', 'datatrust.report_layout')) == set(rid.FAMILIES)       # shared, so visibly shared
    assert changed(('template', 'guidance_layers.html')) == set(rid.FAMILIES)


def test_family_dispatch_and_identity_compatibility():
    assert [rid.family_of({'schema_version': v}) for v in ('1.7', '1.6', '1.5', '1.4', '1.3', '1.2')] == \
        ['cross', 'image', 'text', 'temporal', 'm4', 'm3']
    assert rid.family_of({'schema_version': '1.0', 'methodology_id': 'classification_legacy_2026_08_13'}) == 'classification'
    assert rid.family_of({'schema_version': '1.1', 'methodology_id': 'tabular_regression_v1', 'task': {'kind': 'regression'}}) == 'regression'
    assert rid.family_of({'schema_version': '1.0', 'methodology_id': 'unlabeled_csv_profile_v1', 'task': {'kind': 'dataset_profile'}}) == 'unlabeled'
    from datatrust.renderer import presentation_identity
    legacy = presentation_identity()
    assert set(legacy) == {'package_version', 'report_templates'} and re.fullmatch('[0-9a-f]{12}', legacy['report_templates'])
    assert presentation_identity('m4')['report_templates'] == rid.identity('m4')['presentation_id']


def test_base_stylesheet_is_the_legacy_report_style_byte_for_byte():
    legacy = re.search(r'<style>(.*?)</style>', (TEMPLATES / 'report.html').read_text(), re.S).group(1)
    assert (TEMPLATES / '_report_base.css.html').read_text() == legacy


# ——— Shared shell and evidence macros ———

FIXTURE = ("{% import '_report_shell.html' as shell %}{% import '_evidence.html' as ev %}<!doctype html><html lang=\"en\"><head>"
           "{{ shell.head(title) }}<style>{% include '_report_base.css.html' +%}{{ shell.page_rules('DataTrust test report') }}"
           "{{ shell.styles() }}</style></head><body><main><h1>{{ title }}</h1>{{ ev.unit_table(u) }}</main>{{ shell.script() }}</body></html>")
HOSTILE = '<script>alert(1)</script>"\'&</script>‮name'


def shell_report(unit, printed_profile='focused'):
    from datatrust.report_format import _analysis_env
    rendered = render_unit(unit, plan_screen(unit), plan_print(unit, printed_profile))
    return _analysis_env(None).from_string(FIXTURE).render(u=rendered, title='Shell <test>'), rendered


def hostile_unit(size=80):
    records = tuple(replace(record(n, Signal('missing', 'High', measure=float(n)) if n < 5 else None),
                            entity=(HOSTILE + str(n)) if n % 10 == 0 else f'column_{n:04d}') for n in range(size))
    return Unit('cols', 'Columns', 'V2', FIELDS, records, noun='columns', pointer='/profile/columns',
                html_anchor='ev-cols', html_label='§B.2')


def test_shell_carries_one_hashed_script_and_escapes_everything_else():
    html, rendered = shell_report(hostile_unit())
    scripts = re.findall(r'<script(?![^>]*application/json)[^>]*>(.*?)</script>', html, re.S)
    assert len(scripts) == 1
    digest = base64.b64encode(hashlib.sha256(scripts[0].encode()).digest()).decode()
    csp = htmlmod.unescape(re.search(r'http-equiv="Content-Security-Policy" content="([^"]+)"', html).group(1))
    assert csp == f"default-src 'none'; img-src data:; style-src 'unsafe-inline'; script-src 'sha256-{digest}'"
    assert '<script>alert(1)' not in html and 'Shell &lt;test&gt;' in html
    island = re.search(r'<script type="application/json" id="dt-cols-rows">(.*?)</script>', html, re.S).group(1)
    assert '</script' not in island.lower()
    data = json.loads(island)
    assert [row['entity'] for row in data['rows']] == [r.entity for r in plan_screen(hostile_unit()).individual]
    ids = re.findall(r'\sid="([^"]+)"', html)
    assert len(ids) == len(set(ids))
    assert rendered['disclosure'].startswith('Detailed view, print: 80 columns computed · 5 printed individually · 75 summarised below')
    assert '<noscript' not in html and html.count('class="dt-noscript"') == 1   # visible until the script has run


def test_complete_profile_needs_no_island_and_rows_stay_ordinary_html():
    html, rendered = shell_report(hostile_unit(12), 'complete')
    assert rendered['island'] is None and 'data-dt-island="' not in html and html.count('data-dt-entity="') == 12


def test_printed_pdf_holds_printed_rows_summaries_and_disclosure_but_no_screen_only_content(tmp_path):
    pypdf = pytest.importorskip('pypdf')
    from weasyprint import HTML
    html, _ = shell_report(hostile_unit())
    path = tmp_path / 'r.pdf'
    HTML(string=html).write_pdf(path)
    text = ' '.join(' '.join((p.extract_text() or '').split()) for p in pypdf.PdfReader(path).pages)
    assert 'column_0001' in text and 'column_0004' in text                     # High findings printed individually
    assert 'column_0006' not in text                                           # screen-only rows: data island only
    assert '75 more columns' in text or 'without findings' in text             # summarised, with a count
    assert '80 columns computed' in text and 'Show more' not in text and 'Find' not in text
    assert 'when the page' not in text                                         # the no-script notice is screen-only
