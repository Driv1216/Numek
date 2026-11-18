"""Spike (b): which print features WeasyPrint 69.x actually supports, checked against real PDF text.

Usage: PYTHONPATH=src:. .venv/bin/python -B -m validation.report_experience.spikes.weasy_features
Each check renders a small fixture and inspects the PDF text per page. Output: spikes/results/weasyprint_features.json.
"""
import json
from io import BytesIO
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / 'results'

FIXTURE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src data:; style-src 'unsafe-inline'; script-src 'sha256-AAAA'">
<style>
@page { size: A4 portrait; margin: 15mm; @top-left { content: string(section); font-size: 8pt } @bottom-right { content: "Page " counter(page) " of " counter(pages); font-size: 8pt } }
@page appendix { size: A4 landscape }
h2 { string-set: section content() }
.part { break-before: page }
.appendix { page: appendix; break-before: page }
a.term::after { content: " (see Reading guide, p. " target-counter(attr(href url), page) ")" }
a.termnum::after { content: " [G" target-counter(attr(href url), concept) "]" }
.entry { counter-increment: concept }
.screen-only { }
@media print { .screen-only, [popover], .dt-hide-print { display: none } }
h3.nobookmark { bookmark-level: none }
</style></head><body>
<h1>Spike report</h1>
<h2>Decision summary</h2>
<p>First use of <a class="term" href="#concept-iqr">IQR outliers</a> and <a class="termnum" href="#concept-guardrail">guardrail</a>.</p>
<p>Reference to hidden target <a class="term" href="#concept-hidden">hidden concept</a>.</p>
<div popover id="pop">POPOVER_TEXT_WITH_PRINT_RULE</div>
<div popover id="pop2" style="">POPOVER_TEXT_INLINE_STYLE_ONLY</div>
<details><summary>DETAILS_SUMMARY</summary><p>DETAILS_BODY_TEXT</p></details>
<template><p>TEMPLATE_TEXT</p></template>
<script type="application/json" id="island">{"x": "ISLAND_TEXT"}</script>
<div class="screen-only">SCREEN_ONLY_TEXT</div>
<h2 class="part">Findings</h2><p>Findings body.</p>
<h3 class="nobookmark">Not in outline</h3>
<section class="appendix"><h2>Technical evidence</h2><p>Landscape appendix.</p></section>
<section class="part"><h2>Reading guide</h2>
<div class="entry" id="concept-guardrail"><h3>Guardrail</h3><p>Definition.</p></div>
<div class="entry" id="concept-iqr"><h3>IQR outliers</h3><p>Definition.</p></div>
<div class="entry dt-hide-print" id="concept-hidden"><h3>Hidden</h3></div>
</section></body></html>"""

POPOVER_NO_RULE = """<!doctype html><html><body><p>Visible.</p><div popover>POPOVER_WITHOUT_ANY_RULE</div></body></html>"""


def pages_text(data):
    from pypdf import PdfReader
    return [' '.join((p.extract_text() or '').split()) for p in PdfReader(BytesIO(data)).pages]


def main():
    from weasyprint import HTML
    OUT.mkdir(parents=True, exist_ok=True)
    document = HTML(string=FIXTURE).render()
    data = document.write_pdf()
    (OUT / 'weasyprint_features.pdf').write_bytes(data)
    texts = pages_text(data)
    joined = ' | '.join(texts)
    guide_page = next(i + 1 for i, t in enumerate(texts) if 'Reading guide' in t and 'IQR outliers Definition' in t)
    def tree(nodes):
        return [{'label': n[0], 'children': tree(n[2])} for n in nodes]
    outline = tree(document.make_bookmark_tree())
    plain = HTML(string=POPOVER_NO_RULE).write_pdf()
    checks = {
        'pages': len(texts),
        'page_text': texts,
        'target_counter_page': {'expected_page': guide_page,
                                'resolved': f'(see Reading guide, p. {guide_page})' in texts[0]},
        'target_counter_custom_counter': {'resolved': '[G1]' in texts[0]},
        'target_counter_to_print_hidden_target': {'text_after_link': texts[0].split('hidden concept')[1][:40]},
        'string_set_running_header': {'findings_page_header': texts[1][:40], 'resolved': texts[1].startswith('Findings')},
        'landscape_named_page': document.pages[2].width > document.pages[2].height,
        'bookmarks': outline,
        'h3_bookmark_level_none_excluded': 'Not in outline' not in json.dumps(outline),
        'popover_hidden_by_print_rule': 'POPOVER_TEXT_WITH_PRINT_RULE' not in joined,
        'popover_without_rule_printed': 'POPOVER_WITHOUT_ANY_RULE' in ' '.join(pages_text(plain)),
        'details_body_printed': 'DETAILS_BODY_TEXT' in joined,
        'template_content_printed': 'TEMPLATE_TEXT' in joined,
        'json_island_printed': 'ISLAND_TEXT' in joined,
        'screen_only_hidden': 'SCREEN_ONLY_TEXT' not in joined,
        'meta_csp_tolerated': True,
    }
    (OUT / 'weasyprint_features.json').write_text(json.dumps(checks, indent=1) + '\n')
    print(json.dumps({k: v for k, v in checks.items() if k != 'page_text'}, indent=1))


if __name__ == '__main__':
    main()
