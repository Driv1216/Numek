"""Spike (c) and fixtures for (d): what screen-only evidence costs WeasyPrint, by how it is held in the HTML.

Usage: PYTHONPATH=src:. .venv/bin/python -B -m validation.report_experience.spikes.hidden_cost [--runs 3]

Every variant prints the same visible content (a 120-row evidence table). The screen-only evidence is N further rows of a
12-column per-column evidence table (N = 5,000 and 15,000), held as:
  control    - absent
  per_row    - ordinary rows, each hidden in print by a class (@media print { .print-hidden { display: none } })
  container  - a separate screen-only table hidden in print by one rule on its wrapper
  template   - rows inside a <template> element (rendered on screen by script)
  json       - rows in a <script type="application/json"> data island (rendered on screen by script)
PDF conversion runs in a fresh process per run (validation.report_experience.pdf_probe). The fixtures are also used by the
browser spike (load and filter latency). Output: spikes/results/hidden_cost.json; fixtures under work.nosync/spikes/.
"""
import argparse
import html
import json
import statistics
from pathlib import Path

from validation.report_experience.measure import probe

HERE = Path(__file__).resolve().parent
FIXTURES = HERE.parent / 'work.nosync' / 'spikes'
FIELDS = ['Column', 'Role', 'Type', 'Non-null', 'Missing', 'Unique', 'Top share', 'Constant', 'Near constant',
          'High cardinality', 'Outliers', 'Flags']
STYLE = """<style>
body { font: 10pt/1.4 -apple-system, "Segoe UI", sans-serif; margin: 24px }
table { width: 100%; border-collapse: collapse; font-size: 8pt; table-layout: fixed }
th, td { border-bottom: 1px solid #d8e0e9; padding: 4px; text-align: left; overflow-wrap: anywhere }
thead { display: table-header-group } tr { break-inside: avoid }
.screen-table tbody { content-visibility: auto; contain-intrinsic-size: auto 20000px }
@page { size: A4 landscape; margin: 12mm }
@media print { .print-hidden, .screen-only { display: none } }
</style>"""
SCRIPT = """<script>
(function () {
  var data = document.getElementById('rows-json'), tpl = document.getElementById('rows-template');
  var body = document.getElementById('screen-body');
  if (data && body) {
    var rows = JSON.parse(data.textContent), frag = document.createDocumentFragment();
    rows.forEach(function (r) { var tr = document.createElement('tr'); r.forEach(function (c) { var td = document.createElement('td'); td.textContent = c; tr.appendChild(td); }); frag.appendChild(tr); });
    body.appendChild(frag);
  } else if (tpl && body) { body.appendChild(tpl.content.cloneNode(true)); }
  window.dtFilter = function (q) {
    var t0 = performance.now(), shown = 0;
    q = q.toLowerCase();
    document.querySelectorAll('#screen-body tr, tr.print-hidden').forEach(function (tr) {
      var hit = !q || tr.firstChild.textContent.toLowerCase().indexOf(q) >= 0; tr.hidden = !hit; if (hit) shown++;
    });
    return {ms: performance.now() - t0, shown: shown};
  };
  window.dtReady = performance.now();
})();
</script>"""


def row(index):
    flags = 'Outliers' if index % 37 == 0 else ''
    return [f'measurement_{index:05d}_with_a_long_name', 'feature', 'float64', '5000', f'{index % 7} (0.{index % 7}%)',
            f'{4000 + index % 900} ({80 + index % 9}.0%)', f'{index % 5}.02%', 'No', 'No', 'No', f'{index % 11} (0.{index % 11}%)', flags]


def cells(values):
    return ''.join(f'<td>{html.escape(v)}</td>' for v in values)


def build(variant, hidden):
    head = '<thead><tr>' + ''.join(f'<th>{f}</th>' for f in FIELDS) + '</tr></thead>'
    visible = ''.join(f'<tr>{cells(row(i))}</tr>' for i in range(120))
    parts = ['<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Hidden content spike</title>', STYLE, '</head><body>',
             f'<h1>Spike: {variant}, {hidden:,} screen-only rows</h1><h2>Printed evidence</h2><table>{head}<tbody>{visible}']
    extra = range(120, 120 + hidden)
    if variant == 'per_row':
        parts.append(''.join(f'<tr class="print-hidden">{cells(row(i))}</tr>' for i in extra) + '</tbody></table>')
    else:
        parts.append('</tbody></table>')
        if variant == 'container':
            parts.append(f'<div class="screen-only"><h2>All columns</h2><table class="screen-table">{head}<tbody id="screen-body">'
                         + ''.join(f'<tr>{cells(row(i))}</tr>' for i in extra) + '</tbody></table></div>')
        elif variant == 'template':
            parts.append(f'<div class="screen-only"><h2>All columns</h2><table class="screen-table">{head}<tbody id="screen-body"></tbody></table></div>'
                         '<template id="rows-template">' + ''.join(f'<tr>{cells(row(i))}</tr>' for i in extra) + '</template>')
        elif variant == 'json':
            data = json.dumps([row(i) for i in extra]).replace('</', '<\\/')
            parts.append(f'<div class="screen-only"><h2>All columns</h2><table class="screen-table">{head}<tbody id="screen-body"></tbody></table></div>'
                         f'<script type="application/json" id="rows-json">{data}</script>')
    parts.append(SCRIPT + '</body></html>')
    return ''.join(parts)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--runs', type=int, default=3)
    args = parser.parse_args()
    FIXTURES.mkdir(parents=True, exist_ok=True)
    results = {}
    for hidden in (5000, 15000):
        for variant in ('control', 'per_row', 'container', 'template', 'json'):
            if variant == 'control' and hidden != 5000:
                continue
            name = f'{variant}_{hidden}'
            path = FIXTURES / f'{name}.html'
            path.write_text(build(variant, 0 if variant == 'control' else hidden), encoding='utf-8')
            runs = [probe(path, FIXTURES / f'{name}.pdf', analyse=False) for _ in range(args.runs)]
            results[name] = {'html_bytes': path.stat().st_size, 'pages': runs[0]['pages'],
                             'pdf_total_s_median': round(statistics.median(r['total_s'] for r in runs), 3),
                             'pdf_total_s_runs': [r['total_s'] for r in runs],
                             'peak_rss_bytes_median': int(statistics.median(r['peak_rss_bytes'] for r in runs))}
            print(name, results[name], flush=True)
    control = results['control_5000']['pdf_total_s_median']
    for name, entry in results.items():
        entry['overhead_vs_control'] = round(entry['pdf_total_s_median'] / control - 1, 3)
    out = HERE / 'results' / 'hidden_cost.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({'visible_rows': 120, 'results': results}, indent=1) + '\n')


if __name__ == '__main__':
    main()
