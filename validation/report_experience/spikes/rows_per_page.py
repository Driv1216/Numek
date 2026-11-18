"""Stage 1: rows per printed page with the shared print styles, the input to report_layout.ROWS_PER_PAGE.

Usage: PYTHONPATH=src:. .venv/bin/python -B -m validation.report_experience.spikes.rows_per_page
Renders the shared shell and evidence macros (the same ones reports adopt from Stage 2) with 400 realistic rows per
table kind and counts table rows on pages at least 90% filled. Names cycle from 10 to 49 characters, so some wrap as real column names do; cells
hold values shaped like the classification column evidence. Output: spikes/results/rows_per_page_shell.json.
"""
import json
import statistics
from pathlib import Path

from validation.report_experience.measure import probe

HERE = Path(__file__).resolve().parent
WORK = HERE.parent / 'work.nosync' / 'spikes'

KINDS = {
    'evidence-landscape': ['Role', 'Type', 'Non-null', 'Missing', 'Missing %', 'Unique', 'Top share', 'Outliers', 'Outlier %', 'Flags'],
    'evidence-portrait': ['Type', 'Missing', 'Missing %', 'Unique', 'Outliers'],
    'register-portrait': ['Affected', 'Scope'],
}


def unit(kind, labels):
    from datatrust.report_layout import Field, Record, Unit
    fields = tuple(Field(f'f{i}', label, 'text' if label in ('Role', 'Type', 'Flags', 'Scope') else 'quantity')
                   for i, label in enumerate(labels))
    def value(i, label, n):
        if label == 'Role':
            return 'feature'
        if label == 'Type':
            return 'float64'
        if label in ('Flags',):
            return 'Outliers · Near constant' if n % 9 == 0 else ''
        if label == 'Scope':
            return 'dataset'
        return round(1000 + n * 7.31 + i, 2) if i % 2 else 5000 - n
    base = 'customer_account_balance_change_after_campaign'
    records = tuple(Record(f'r{n}', f'm{n:04d}_' + base[:4 + (n * 7) % 40],
                           {f'f{i}': value(i, label, n) for i, label in enumerate(labels)}, n, f'/profile/columns/{n}')
                    for n in range(400))
    return Unit(kind, f'Rows per page: {kind}', 'V2', fields, records, noun='columns', pointer='/profile/columns',
                table_kind=kind)


def main():
    from datatrust.report_format import _analysis_env
    from datatrust.report_layout import plan_print, plan_screen, render_unit
    env = _analysis_env(None)
    WORK.mkdir(parents=True, exist_ok=True)
    out = {}
    for kind, labels in KINDS.items():
        u = unit(kind, labels)
        rendered = render_unit(u, plan_screen(u), plan_print(u, 'complete'))
        appendix = kind.endswith('landscape')
        html = env.from_string(
            "{% import '_report_shell.html' as shell %}{% import '_evidence.html' as ev %}<!doctype html><html lang=\"en\"><head>"
            "{{ shell.head('Rows per page') }}<style>{% include '_report_base.css.html' +%}{{ shell.page_rules('DataTrust') }}{{ shell.styles() }}</style>"
            "</head><body><main>{% if appendix %}<section class=\"dt-appendix\">{% endif %}<h2>Evidence</h2>{{ ev.unit_table(u) }}"
            "{% if appendix %}</section>{% endif %}</main>{{ shell.script() }}</body></html>").render(u=rendered, appendix=appendix)
        path = WORK / f'rows_{kind}.html'
        path.write_text(html, encoding='utf-8')
        result = probe(path, WORK / f'rows_{kind}.pdf', analyse=True)
        full = [p['table_rows'].get('dt-evidence', 0) for p in result['page_detail']
                if p['fill'] is not None and p['fill'] >= 0.9 and p['table_rows'].get('dt-evidence')]
        out[kind] = {'fields': len(labels) + 1, 'pages': result['pages'], 'full_pages': len(full),
                     'rows_per_full_page': full, 'median': statistics.median(full) if full else None,
                     'minimum': min(full) if full else None,
                     'orientation': {p['orientation'] for p in result['page_detail']}.pop()}
        print(kind, out[kind]['median'], out[kind]['minimum'], out[kind]['orientation'], flush=True)
    target = HERE / 'results' / 'rows_per_page_shell.json'
    target.write_text(json.dumps(out, indent=1, default=list) + '\n')


if __name__ == '__main__':
    main()
