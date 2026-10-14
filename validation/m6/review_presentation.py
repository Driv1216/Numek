"""Project completed M6 evidence into correction-pass exports; never re-audit."""
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw
from pypdf import PdfReader
from datatrust import TextAuditResult

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'results/review_corrections'
POPPLER = Path('/Users/drivyaanshyadav/.cache/codex-runtimes/codex-primary-runtime/dependencies/bin/override/pdftoppm')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run():
    old = json.loads((ROOT / 'results/verification.json').read_text())
    cases = {}
    for name, entry in old['new_evidence'].items():
        if 'pdf' in entry:
            cases[name] = ROOT / entry['pdf']['path']
    extra = json.loads((ROOT / 'results/presentation.json').read_text())
    for name in ('default', 'excerpt'):
        cases['controls_' + name] = ROOT / extra[name]['path']
    OUT.mkdir(mode=0o700, exist_ok=True)
    ledger = []
    with tempfile.TemporaryDirectory(prefix='numek-m6-review-pdf-') as scratch:
        for name, prior in cases.items():
            public_path = prior.with_suffix('.json')
            public = json.loads(public_path.read_text())
            audit = public['profile']['audit_id']
            private_path = prior.parent / '.datatrust-private' / audit / 'manifest.json'
            private = json.loads(private_path.read_text())
            refs = tuple(x['reference'] for x in public['profile'].get('excerpts', []))
            for key in ('export_fingerprint', 'export_identity', 'excerpts', 'disclosure'):
                public['profile'].pop(key, None)
            result = TextAuditResult(*(public[k] for k in ('profile', 'checks', 'evidence', 'findings', 'coverage', 'execution', 'generated_at')), private)
            analysis_digest = hashlib.sha256(result.json_text().encode()).hexdigest()
            directory = OUT / 'reports' / name
            directory.mkdir(parents=True, mode=0o700, exist_ok=True)
            artifacts = result.generate_artifacts(directory / (name + '.pdf'), format='pdf', json_path=directory / (name + '.json'), excerpt_refs=refs, allowed_roots=(str((ROOT / 'data/authored').resolve()),))
            pdf = Path(artifacts.pdf_path)
            exported = json.loads(Path(artifacts.json_path).read_text())
            assert exported['evidence'] == public['evidence']
            assert exported['findings'] == public['findings']
            assert exported['coverage'] == public['coverage']
            assert exported['profile']['export_identity']['completed_evidence_sha256'] == analysis_digest
            assert hashlib.sha256(result.json_text().encode()).hexdigest() == analysis_digest
            if not refs:
                assert 'SECRET_LABEL' not in Path(artifacts.json_path).read_text()
            else:
                assert '&lt;b&gt;' in Path(artifacts.html_path).read_text()
                assert '[U+202E]' in Path(artifacts.html_path).read_text()
            reader = PdfReader(pdf)
            assert all(len(page.extract_text() or '') > 20 for page in reader.pages)
            prefix = Path(scratch) / name
            subprocess.run([str(POPPLER), '-r', '110', '-png', str(pdf), str(prefix)], check=True, capture_output=True)
            pages = sorted(Path(scratch).glob(name + '-*.png'), key=lambda p: int(p.stem.rsplit('-', 1)[1]))
            assert len(pages) == len(reader.pages)
            contacts = []
            for start in range(0, len(pages), 4):
                sheet = Image.new('RGB', (1500, 2180), '#e7ebef')
                draw = ImageDraw.Draw(sheet)
                for i, page in enumerate(pages[start:start + 4]):
                    image = Image.open(page).convert('RGB')
                    image.thumbnail((720, 1035))
                    x, y = i % 2 * 750 + 10, i // 2 * 1090 + 30
                    sheet.paste(image, (x, y))
                    draw.text((x, y - 22), f'{name} page {start + i + 1}', fill='#123')
                contact = directory / f'pages-{start // 4 + 1}.jpg'
                sheet.save(contact, quality=92)
                contacts.append(str(contact.relative_to(ROOT)))
            entry = {'case': name, 'reused_completed_analysis': str(public_path.relative_to(ROOT)), 'prior_json_sha256': digest(public_path), 'prior_pdf_sha256': digest(prior), 'completed_analysis_sha256': analysis_digest, 'analysis_not_rerun': True, 'old_pages': len(PdfReader(prior).pages), 'pages': len(pages), 'report': str(pdf.relative_to(ROOT)), 'artifact_sha256': {k: digest(Path(getattr(artifacts, k + '_path'))) for k in ('html', 'json', 'pdf')}, 'qa_metadata': artifacts.qa_metadata, 'contacts': contacts, 'visual_review': 'pending', 'technical_evidence_unchanged': True, 'selection_evidence': 'Historical v1 selection retained; correction v2 allocation is verified by focused tests, not these reprojected audits.'}
            ledger.append(entry)
            (OUT / 'presentation.json').write_text(json.dumps(ledger, indent=2, allow_nan=False) + '\n')
            print(name, entry['old_pages'], '->', entry['pages'], 'pages', flush=True)


if __name__ == '__main__':
    run()
