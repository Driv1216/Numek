"""Measure report composition and cost for the Report Experience matrix.

Usage:
  PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src .venv/bin/python -B -m validation.report_experience.measure \
      --phase before [--cases a,b] [--runs 3]

For each case and report variant it records:
- the completed result's identity: fresh cases write their analysis JSON and a digest that ignores only the documented
  volatile measurement fields (VOLATILE); stored cases record the digest of the stored file, which is never modified;
- HTML render time (median of runs; 5 runs when a render takes under 2 s), HTML bytes and table rows by section;
- PDF conversion in a separate process per run: median time, median peak RSS, pages, orientation, per-page fill ratio,
  page span of each h2 section, table rows per page by table class, bookmark count;
- whether every finding's title appears in the HTML text and in the PDF text.
Small artifacts are kept under results/<phase>/<case>/; large ones under work.nosync/ with their digests recorded.
Measurements describe this machine only; they are not capacity guarantees.
"""
import argparse
import hashlib
import html as htmlmod
import json
import os
import platform
import re
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from validation.report_experience.cases import REPO, WORK, cases, sha256

HERE = Path(__file__).resolve().parent
# Measured execution facts that differ between identical runs; analytical evidence is everything else.
VOLATILE = {'generated_at', 'elapsed_seconds', 'phase_seconds', 'duration_seconds', 'whole_job_seconds',
            'model_load_seconds', 'model_selection_seconds', 'final_verification_seconds', 'peak_worker_rss_bytes',
            'peak_workspace_bytes', 'peak_spill_bytes', 'frame_bytes', 'stage_seconds', 'seconds'}
SMALL_ARTIFACT_BYTES = 1_500_000


def normalized(value):
    if isinstance(value, dict):
        return {k: normalized(v) for k, v in value.items() if k not in VOLATILE}
    if isinstance(value, list):
        return [normalized(v) for v in value]
    return value


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=True, allow_nan=False).encode()).hexdigest()


def differing_paths(a, b, path='', out=None, limit=20):
    out = [] if out is None else out
    if len(out) >= limit:
        return out
    if isinstance(a, dict) and isinstance(b, dict):
        for key in sorted(set(a) | set(b)):
            differing_paths(a.get(key), b.get(key), f'{path}/{key}', out, limit)
    elif isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        for index, (x, y) in enumerate(zip(a, b)):
            differing_paths(x, y, f'{path}/{index}', out, limit)
    elif a != b:
        out.append(path)
    return out


def timed(function, runs):
    times, value = [], None
    while len(times) < runs:
        start = time.perf_counter()
        value = function()
        times.append(time.perf_counter() - start)
        if len(times) == 1 and times[0] < 2:
            runs = max(runs, 5)
    return value, times


def render_variant(result, variant):
    """canonical: the focused print profile; complete: the complete print profile; app: the browser app's exact path.
    Until Report Experience Stage 2 the app passed legacy_html=True (that is what the 'before' phase measured); from
    Stage 2 it renders the canonical report, so this variant follows whichever path web.py uses now."""
    from datatrust.renderer import render_analysis_result, write_report_artifacts
    if variant == 'canonical':
        return render_analysis_result(result)
    if variant == 'complete':
        return render_analysis_result(result, print_profile='complete')
    import inspect
    import datatrust.web
    legacy = 'legacy_html=' in inspect.getsource(datatrust.web.generate_report)
    with tempfile.TemporaryDirectory() as folder:
        artifacts = write_report_artifacts(result, Path(folder) / 'report.html', legacy_html=legacy and
                                           result.to_dict().get('methodology_id') == 'classification_legacy_2026_08_13')
        return Path(artifacts.html_path).read_text(encoding='utf-8')


def section_rows(html):
    """Table rows under each h2, the measure WS4 used to attribute report size."""
    out, current = {}, '(before first h2)'
    for part in re.split(r'(<h2[^>]*>.*?</h2>)', html, flags=re.S):
        heading = re.match(r'<h2[^>]*>(.*?)</h2>', part, flags=re.S)
        if heading:
            current = ' '.join(re.sub(r'<[^>]+>', '', heading.group(1)).split())[:80]
            continue
        rows = len(re.findall(r'<tr[\s>]', part))
        out[current] = out.get(current, 0) + rows
    return out


def plain(text):
    return ' '.join(htmlmod.unescape(re.sub(r'<[^>]+>', ' ', text)).split())


def reader_name(value, family):
    """M6 and M7 findings record a family code, not a title. From Stage 6 their reports name each finding with the
    workflow's reader-facing name; before Stage 6 the instrument looked for the raw code (Stage 0 finding 6)."""
    if not family:
        return None
    module = {'1.5': 'datatrust.text_presentation', '1.6': 'datatrust.image_presentation'}.get(value.get('schema_version'))
    if module:
        import importlib
        named = getattr(importlib.import_module(module), 'family_title', None)
        if named:
            return named(family)
    return family


def finding_titles(value):
    titles = []
    for finding in value.get('findings', []) or []:
        if not isinstance(finding, dict) or finding.get('code') == 'no_major_issues':
            continue
        title = finding.get('title') or reader_name(value, finding.get('family'))
        if title:
            titles.append(str(title))
    return titles


def probe(html_path, pdf_path, analyse):
    command = [sys.executable, '-B', '-m', 'validation.report_experience.pdf_probe', str(html_path), str(pdf_path)]
    if analyse:
        command.append('--analyse')
    env = dict(os.environ, PYTHONPATH=str(REPO / 'src') + os.pathsep + str(REPO), PYTHONDONTWRITEBYTECODE='1')
    completed = subprocess.run(command, capture_output=True, text=True, cwd=REPO, env=env)
    if completed.returncode:
        raise RuntimeError(completed.stderr[-2000:])
    return json.loads(completed.stdout)


def sections_by_page(pages):
    spans, current = {}, None
    for page in pages:
        for heading in page['headings']:
            if heading['level'] in ('h1', 'h2'):
                current = heading['text']
                spans.setdefault(current, {'first_page': page['page'], 'pages': set()})
        if current:
            spans[current]['pages'].add(page['page'])
    return {name: {'first_page': s['first_page'], 'pages_touched': len(s['pages'])} for name, s in spans.items()}


def measure_case(case, phase, runs, determinism):
    record = {'case': case.name, 'group': case.group, 'mode': case.mode, 'description': case.description,
              'inputs': case.inputs, 'variants': {}}
    start = time.perf_counter()
    result = case.build()
    record['analysis_or_load_s'] = round(time.perf_counter() - start, 3)
    value = result.to_dict()
    record['schema_version'] = value.get('schema_version')
    record['methodology_id'] = value.get('methodology_id')
    record['finding_count'] = len(value.get('findings', []) or [])
    keep = HERE / 'results' / phase / case.name
    big = WORK / phase / case.name
    keep.mkdir(parents=True, exist_ok=True)
    big.mkdir(parents=True, exist_ok=True)
    if case.mode == 'fresh':
        text = result.json_text()
        target = (big if case.heavy else keep) / 'analysis.json'
        target.write_text(text, encoding='utf-8')
        record['analysis_json'] = {'path': str(target.relative_to(REPO)), 'bytes': len(text.encode()),
                                   'sha256': hashlib.sha256(text.encode()).hexdigest(),
                                   'normalized_sha256': digest(normalized(json.loads(text))),
                                   'volatile_fields_ignored': sorted(VOLATILE)}
        if determinism:
            again = json.loads(case.build().json_text())
            same = digest(normalized(again)) == record['analysis_json']['normalized_sha256']
            record['analysis_json']['rerun_normalized_identical'] = same
            if not same:
                record['analysis_json']['rerun_differences'] = differing_paths(normalized(json.loads(text)), normalized(again))
    else:
        record['analysis_json'] = {'path': str(case.stored_path.relative_to(REPO)), 'sha256': sha256(case.stored_path),
                                   'normalized_sha256': digest(normalized(value)), 'stored_read_only': True}
    if case.name.startswith('m5_'):
        limits = (value.get('context') or {}).get('presentation', {})
        record['m5_action_disclosure'] = {'findings': record['finding_count'],
                                          'executive_actions_limit': limits.get('executive_actions')}
    titles = finding_titles(value)
    for variant in case.variants:
        html, times = timed(lambda: render_variant(result, variant), runs)
        folder = keep if len(html.encode()) <= SMALL_ARTIFACT_BYTES and not case.heavy else big
        html_path = folder / f'{variant}.html'
        html_path.write_text(html, encoding='utf-8')
        entry = {'html_path': str(html_path.relative_to(REPO)), 'html_bytes': len(html.encode()),
                 'html_sha256': hashlib.sha256(html.encode()).hexdigest(),
                 'html_render_s_median': round(statistics.median(times), 4), 'html_render_s_runs': [round(t, 4) for t in times],
                 'table_rows_by_section': section_rows(html)}
        if case.stored_html and case.stored_html.exists() and variant == 'canonical':
            entry['matches_stored_html'] = sha256(case.stored_html) == entry['html_sha256']
        pdf_path = folder / f'{variant}.pdf'
        detail = probe(html_path, pdf_path, analyse=True)
        pdf_runs = [detail]
        count = runs if detail['total_s'] >= 2 else max(runs, 5)
        for _ in range(count - 1):
            pdf_runs.append(probe(html_path, folder / f'{variant}.timing.pdf', analyse=False))
        (folder / f'{variant}.timing.pdf').unlink(missing_ok=True)
        pages = detail['page_detail']
        fills = [p['fill'] for p in pages if p['fill'] is not None]
        from pypdf import PdfReader
        pdf_text = ' '.join(' '.join((page.extract_text() or '').split()) for page in PdfReader(pdf_path).pages)
        html_text = plain(html)
        entry.update({
            'pdf_path': str(pdf_path.relative_to(REPO)), 'pdf_bytes': detail['pdf_bytes'], 'pdf_sha256': sha256(pdf_path),
            'pages': detail['pages'],
            'portrait_pages': sum(p['orientation'] == 'portrait' for p in pages),
            'landscape_pages': sum(p['orientation'] == 'landscape' for p in pages),
            'pdf_total_s_median': round(statistics.median(r['total_s'] for r in pdf_runs), 4),
            'pdf_total_s_runs': [r['total_s'] for r in pdf_runs],
            'pdf_render_s_median': round(statistics.median(r['render_s'] for r in pdf_runs), 4),
            'pdf_peak_rss_bytes_median': int(statistics.median(r['peak_rss_bytes'] for r in pdf_runs)),
            'bookmarks': detail['bookmarks'],
            'fill': {'mean': round(statistics.mean(fills), 3) if fills else None,
                     'pages_below_40pct': [p['page'] for p in pages if p['fill'] is not None and p['fill'] < 0.4],
                     'pages_below_40pct_excluding_last': [p['page'] for p in pages[:-1] if p['fill'] is not None and p['fill'] < 0.4]},
            'sections': sections_by_page(pages),
            'table_rows_per_page': [{'page': p['page'], 'orientation': p['orientation'], 'fill': p['fill'], 'rows': p['table_rows']}
                                    for p in pages if p['table_rows']],
            'findings_titles': len(titles),
            'finding_titles_in_html': sum(t in html_text for t in titles),
            'finding_titles_in_pdf': sum(' '.join(t.split()) in pdf_text for t in titles),
            'finding_titles_missing_from_pdf': [t for t in titles if ' '.join(t.split()) not in pdf_text][:20],
        })
        entry['page_detail'] = pages
        record['variants'][variant] = entry
        print(f"  {case.name}/{variant}: {detail['pages']} pages, html {entry['html_bytes']:,} B "
              f"{entry['html_render_s_median']}s, pdf {entry['pdf_total_s_median']}s", flush=True)
    (keep / 'metrics.json').write_text(json.dumps(record, indent=1, default=sorted) + '\n')
    return record


def environment():
    import duckdb
    import jinja2
    import pandas
    import weasyprint
    return {'python': platform.python_version(), 'platform': platform.platform(), 'machine': platform.machine(),
            'weasyprint': weasyprint.__version__, 'pandas': pandas.__version__, 'duckdb': duckdb.__version__,
            'jinja2': jinja2.__version__, 'git_head': subprocess.run(['git', 'rev-parse', 'HEAD'], capture_output=True,
                                                                     text=True, cwd=REPO).stdout.strip(),
            'capacity_guarantee': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--phase', required=True)
    parser.add_argument('--cases', default='')
    parser.add_argument('--runs', type=int, default=3)
    parser.add_argument('--determinism', default='german_credit,bank_full,bank_full_declared,bike_hour,m3_scene,german_unlabeled')
    parser.add_argument('--variants', default='', help="Override every case's variants, e.g. canonical,complete")
    args = parser.parse_args()
    chosen = set(filter(None, args.cases.split(',')))
    determinism = set(filter(None, args.determinism.split(',')))
    summary_path = HERE / 'results' / args.phase / 'summary.json'
    summary = json.loads(summary_path.read_text()) if summary_path.exists() else {'cases': {}}
    summary['environment'] = environment()
    for case in cases():
        if chosen and case.name not in chosen:
            continue
        if args.variants:
            case.variants = tuple(v for v in args.variants.split(',') if v != 'app' or 'app' in case.variants)
        print(case.name, flush=True)
        try:
            record = measure_case(case, args.phase, args.runs, case.name in determinism)
            summary['cases'][case.name] = {k: v for k, v in record.items() if k != 'variants'} | {
                'variants': {name: {k: v for k, v in entry.items() if k not in ('page_detail', 'table_rows_per_page')}
                             for name, entry in record['variants'].items()}}
        except Exception as exc:   # recorded, never hidden
            summary['cases'][case.name] = {'case': case.name, 'group': case.group, 'unavailable': f'{type(exc).__name__}: {exc}'[:2000]}
            print('  unavailable:', exc, flush=True)
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(json.dumps(summary, indent=1, default=sorted) + '\n')


if __name__ == '__main__':
    main()
