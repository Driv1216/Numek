"""Stage 6D: the canonical reports render interpretation_v1, the same function the dashboards render.

- every case's report renders the summary sentences and "what would make this more conclusive" of interpret(), unchanged;
- a clean result's report states its completed scope;
- the dashboard companion carries the same interpretation the report rendered (one source; no drift).
"""
import html
import re

import pytest

from dashboard_harness import analysis, cases, folder, params
from datatrust.dashboard_companion import build
from datatrust.interpretation import interpret
from datatrust.report_identity import family_of
from validation.dashboard.corpus import _render, _stored

CASES = [c for c in cases() if c['composition'] != 'generic']


def report(case):
    value = analysis(case)
    return value, _render(_stored(value))


def text_of(page):
    return html.unescape(re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', page)))


@pytest.mark.parametrize('case', params(CASES))
def test_the_report_renders_the_interpretation_unchanged(case):
    value, page = report(case)
    interpretation = interpret(value, family_of(value))
    body = text_of(page)
    assert 'In brief' in body and interpretation['version'] in body
    for sentence in interpretation['summary']:
        assert re.sub(r'\s+', ' ', sentence['text']) in body, (case['name'], sentence['text'])
    for item in interpretation['more_conclusive']:
        assert item['label'] in body and item['why'] in body, (case['name'], item['key'])
    if interpretation['clean']:
        assert 'A clean result, and its scope' in body
    # one source: the dashboard companion carries exactly what the report rendered
    assert build(value)['interpretation'] == interpretation
