"""Capture today's results pages for every materialised dashboard case (plan Stage 0 baseline; section L).

Each case is saved into a throwaway history through the history's own record path, with the same metadata the app records
(`api_web._history_meta`). The packaged app is served in-process on loopback, and validation/dashboard/capture.mjs drives
headless Chromium over every saved entry at the five review sizes. Expanded chapters are captured at 1440 x 900.
It writes screenshots, page text and contact sheets under
validation/report_experience/work.nosync/dashboard/visual/<label>/. The user's own history and the repository are untouched.

    PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:. .venv/bin/python -B -m validation.dashboard.baseline [--label baseline] [names...]
"""
import argparse
import hashlib
import json
import secrets
import shutil
import subprocess
import tempfile
import threading
from pathlib import Path

from validation.dashboard.corpus import CASES, WORK, manifest

REPO = Path(__file__).resolve().parents[2]
SIZES = [[1920, 1080, 'w1920'], [1440, 900, 'w1440'], [1024, 768, 'w1024'], [768, 1024, 'w768'], [375, 812, 'w375']]
PLAYWRIGHT = REPO / 'frontend-visual-lab-v3/node_modules'


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save_all(history, chosen):
    from datatrust.api_web import _history_meta
    saved = []
    for case in chosen:
        folder = CASES / case['name']
        if not (folder / 'case.json').exists():
            continue
        json_path, html_path = folder / 'analysis.json', folder / 'report.html'
        meta = _history_meta(json_path)
        meta['dataset_name'] = meta['dataset_name'] or case['name']
        meta['source_filename'] = meta['source_filename'] or f"{case['name']} (dashboard corpus)"
        eid = history.record(workflow=case['workflow'], mode=case['mode'], meta=meta,
                             artifacts={'json': (json_path, _sha(json_path)), 'html': (html_path, _sha(html_path))})
        saved.append({'name': case['name'], 'id': eid})
    return saved


def contact_sheets(out, saved):
    from PIL import Image, ImageDraw
    sheets = out / 'sheets'
    sheets.mkdir(exist_ok=True)
    for entry in saved:
        folder = out / entry['name']
        for kind, frames in (('sizes', [f'{s[2]}-first.jpg' for s in SIZES]), ('chapters', sorted(p.name for p in folder.glob('w*-chapter-*.jpg')))):
            frames = [f for f in frames if (folder / f).exists()]
            if not frames:
                continue
            tw, th, cols = 560, 350, 3
            rows = (len(frames) + cols - 1) // cols
            sheet = Image.new('RGB', (cols * tw, rows * (th + 20)), 'white')
            draw = ImageDraw.Draw(sheet)
            for n, frame in enumerate(frames):
                image = Image.open(folder / frame).convert('RGB')
                image.thumbnail((tw, th))
                x, y = (n % cols) * tw, (n // cols) * (th + 20)
                sheet.paste(image, (x, y + 20))
                draw.text((x + 4, y + 4), frame, fill='black')
            sheet.save(sheets / f"{entry['name']}-{kind}.jpg", quality=82)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('names', nargs='*')
    parser.add_argument('--label', default='baseline')
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--chapters-at', default='w1440', help='the size label at which every chapter is opened and captured')
    args = parser.parse_args(argv)
    import logging
    from werkzeug.serving import make_server
    from datatrust.history import History
    logging.getLogger('werkzeug').setLevel(logging.ERROR)
    from datatrust.web import create_app

    chosen = [c for c in manifest()['cases'] if not args.names or c['name'] in args.names]
    out = WORK / 'visual' / args.label
    shutil.rmtree(out, ignore_errors=True)
    out.mkdir(parents=True)
    root = WORK / 'history'
    shutil.rmtree(root, ignore_errors=True)
    history = History(root)
    history.set_settings(saving='on')
    saved = save_all(history, chosen)
    token = secrets.token_urlsafe(24)
    with tempfile.TemporaryDirectory(prefix='datatrust-dashboard-') as workspace:
        app = create_app(Path(workspace), history=history, launch_token=token, classic_ui=False)
        server = make_server('127.0.0.1', args.port, app, threaded=True)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            plan = {'base': f'http://127.0.0.1:{args.port}', 'launch': token, 'out': str(out), 'playwright_dir': str(PLAYWRIGHT),
                    'sizes': SIZES, 'chapters_at': args.chapters_at, 'cases': saved}
            (out / 'plan.json').write_text(json.dumps({**plan, 'launch': 'redacted'}, indent=1))
            plan_file = out / '.plan.json'
            plan_file.write_text(json.dumps(plan))
            subprocess.run(['node', str(Path(__file__).with_name('capture.mjs')), str(plan_file)], check=True, cwd=REPO)
            plan_file.unlink()
        finally:
            server.shutdown()
            thread.join(timeout=5)
    contact_sheets(out, saved)
    results = json.loads((out / 'capture.json').read_text())
    waiting = [r for r in results if r['state'] != 'rendered']
    errors = [r for r in results if r['errors']]
    print(f"{len(saved)} cases · {len(results)} page captures · {sum(r['chapters'] for r in results)} chapters · "
          f"{len(waiting)} did not render · {len(errors)} with console errors → {out}")


if __name__ == '__main__':
    main()
