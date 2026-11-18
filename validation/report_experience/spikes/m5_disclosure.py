"""Confirm whether the M5 temporal report discloses findings beyond its executive-action limit.

Usage: PYTHONPATH=src:. .venv/bin/python -B -m validation.report_experience.spikes.m5_disclosure
The stored completed result is read only. An in-memory copy lowers the recorded presentation limit
(context.presentation.executive_actions, a display setting) so that the public cases, which have at most 5 findings, exercise
the limit. Nothing analytical changes. Beijing exceeds the recorded limit (15 findings, limit 5) without any change.
Output: spikes/results/m5_disclosure.json.
"""
import copy
import html as htmlmod
import json
import re
from pathlib import Path

from validation.report_experience.cases import VALIDATION, StoredResult

HERE = Path(__file__).resolve().parent


def text(html):
    return ' '.join(htmlmod.unescape(re.sub(r'<[^>]+>', ' ', html)).split())


def check(path, limit_holder, lower_to=None):
    from datatrust.renderer import render_analysis_result
    data = json.loads(Path(path).read_text())
    findings = data['findings']
    view = copy.deepcopy(data)
    holder = limit_holder(view)
    if lower_to is not None:
        holder['executive_actions'] = lower_to
    limit = holder.get('executive_actions', 5)
    raw = render_analysis_result(StoredResult(view))
    full = text(raw)
    beyond = findings[limit:]
    def located(finding):
        refs = finding.get('evidence_refs') or []
        return {'title': finding.get('title'), 'priority': finding.get('priority'), 'measurement': finding.get('measurement'),
                'evidence_refs': refs, 'refs_present_in_report': [r in raw for r in refs]}
    return {'stored_result': str(Path(path).relative_to(VALIDATION.parent)), 'findings': len(findings),
            'executive_limit': limit, 'limit_lowered_in_memory': lower_to is not None,
            'action_cards_rendered': raw.count('<article class="action"'),
            'findings_beyond_limit': [located(f) for f in beyond],
            'omission_statement_present': bool(re.search(r'\b(more|additional|omitted|further)\b[^.]{0,80}\b(finding|action|topic)', full, re.I))}


def main():
    out = {
        'm5_beijing_recorded_limit': check(VALIDATION / 'm5/reports/beijing.json', lambda d: d['context']['presentation']),
        'm5_retail_limit_lowered': check(VALIDATION / 'm5/reports/retail.json', lambda d: d['context']['presentation'], 1),
    }
    target = HERE / 'results' / 'm5_disclosure.json'
    target.write_text(json.dumps(out, indent=1) + '\n')
    print(json.dumps(out, indent=1))


if __name__ == '__main__':
    main()
