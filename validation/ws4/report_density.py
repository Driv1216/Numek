"""Where a wide report's size comes from: HTML bytes per section and table rows per subsection.
Usage: python validation/ws4/report_density.py DATA_DIR"""
import re, sys, json, warnings; warnings.simplefilter('ignore')
from pathlib import Path
if __name__ == '__main__':
    sys.path[:0] = [str(Path(__file__).resolve().parents[2] / 'src')]
    from datatrust import DataTrust, DatasetSpec, TaskSpec
    from datatrust.renderer import write_report_artifacts
    D = Path(sys.argv[1])  # the --data directory of run_scalability.py, holding wide_1000.csv and wide_5000.csv
    out = {}
    for cols in (1000, 5000):
        r = DataTrust.from_spec(DatasetSpec(str(D / f'wide_{cols}.csv')), TaskSpec('classification', target='y')).analyze_result()
        o = D / f'density{cols}'; o.mkdir(exist_ok=True)
        for f in o.iterdir(): f.unlink()
        html = Path(write_report_artifacts(r, o / 'r.html', legacy_html=True).html_path).read_text()
        parts = re.split(r'(?=<section)', html)
        sizes = []
        for part in parts:
            h = re.search(r'<h2>([^<]+)</h2>', part)
            sizes.append((h.group(1) if h else part[:40].replace('\n', ' '), len(part)))
        total = sum(s for _, s in sizes)
        out[cols] = {'html_bytes': total, 'sections': [(n, s, round(100 * s / total, 1)) for n, s in sizes if s > total * 0.01]}
        tables = {name: len(re.findall(r'<tr>', seg)) for name, seg in [(m.group(1), m.group(0)) for m in re.finditer(r'<h3[^>]*>([^<]+)</h3>(.*?)(?=<h3|</section>)', html, re.S)]}
        out[cols]['table_rows_by_subsection'] = {k: v for k, v in sorted(tables.items(), key=lambda kv: -kv[1])[:6]}
        out[cols]['guidance_observed_lines'] = sum(len(i['observed']) for i in r.guidance['items'].values())
    print(json.dumps(out, indent=1))
