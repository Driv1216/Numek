"""Compare two measured phases case by case.

Usage: PYTHONPATH=src:. .venv/bin/python -B -m validation.report_experience.compare --before before --after after_stage2
Writes results/<after>/COMPARISON.md and prints it. The 'before' app variant is what the browser app produced then
(legacy_html); the 'after' canonical variant is the focused print profile, which is what the app produces now.
Analysis identity compares the normalised analysis JSON digests: they must be equal (presentation never changes
evidence). Timings are medians on one machine; they are not capacity guarantees.
"""
import argparse
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--before', default='before')
    parser.add_argument('--after', required=True)
    args = parser.parse_args()
    before = json.loads((HERE / 'results' / args.before / 'summary.json').read_text())['cases']
    after = json.loads((HERE / 'results' / args.after / 'summary.json').read_text())['cases']
    lines = [f'# Report Experience — {args.before} versus {args.after}', '',
             '| Case | Analysis JSON identical | Pages before (canonical / app) | Pages after (focused / complete) | '
             'PDF s before (canonical) → focused | Peak PDF RSS before → focused | HTML before → after (focused) | '
             'Pages < 40% fill after (focused, excl. last) | Finding titles in PDF (focused) |',
             '|---|---|---|---|---|---|---|---|---|']
    mismatches = []
    for name, a in after.items():
        b = before.get(name)
        if not b or 'unavailable' in a or 'unavailable' in b:
            lines.append(f'| {name} | — | — | — | — | — | — | — | {a.get("unavailable", "not in before")[:60]} |')
            continue
        same = a['analysis_json']['normalized_sha256'] == b['analysis_json']['normalized_sha256']
        if not same:
            mismatches.append(name)
        bv, av = b['variants'], a['variants']
        bc, ba = bv.get('canonical', {}), bv.get('app', {})
        af, ac = av.get('canonical', {}), av.get('complete', {})
        mib = lambda x: f"{x / 1024 ** 2:,.0f} MiB" if x else '—'
        lines.append(
            f"| {name} | {'yes' if same else '**NO**'} | {bc.get('pages', '—')} / {ba.get('pages', '—')} | "
            f"{af.get('pages', '—')} / {ac.get('pages', '—')} | {bc.get('pdf_total_s_median', '—')} → {af.get('pdf_total_s_median', '—')} | "
            f"{mib(bc.get('pdf_peak_rss_bytes_median'))} → {mib(af.get('pdf_peak_rss_bytes_median'))} | "
            f"{bc.get('html_bytes', 0):,} → {af.get('html_bytes', 0):,} | "
            f"{', '.join(map(str, af.get('fill', {}).get('pages_below_40pct_excluding_last', []))) or '—'} | "
            f"{af.get('finding_titles_in_pdf', '—')}/{af.get('findings_titles', '—')} |")
    lines += ['', f'Analysis JSON mismatches: {", ".join(mismatches) if mismatches else "none"}.']
    out = HERE / 'results' / args.after / 'COMPARISON.md'
    out.write_text('\n'.join(lines) + '\n')
    print('\n'.join(lines))


if __name__ == '__main__':
    main()
