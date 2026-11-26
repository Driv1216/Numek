"""Shared harness for the results-dashboard tests: the representative corpus (validation/dashboard/cases.json) and a way
to run the app's own TypeScript projections in node against it.

The TypeScript is bundled with the frontend's esbuild and run in node, as tests/test_outcome_states.py does, so the
tests exercise exactly the code the browser runs. Everything skips cleanly when node or the frontend toolchain is absent,
and cases that have not been materialised (python -m validation.dashboard.corpus) are skipped, never failed.
"""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / 'frontend'
ESBUILD = FRONTEND / 'node_modules/.bin/esbuild'
MANIFEST = ROOT / 'validation/dashboard/cases.json'
WORK = ROOT / 'validation/report_experience/work.nosync/dashboard/cases'

COMPOSITIONS = {'classification', 'numeric', 'profile', 'annotation', 'multilabel', 'readiness', 'comparison', 'structure',
                'temporal', 'text', 'image', 'cross', 'generic'}
WORKFLOWS = {'core', 'm4', 'm5', 'm6', 'm7', 'm9'}

needs_node = pytest.mark.skipif(not (shutil.which('node') and ESBUILD.exists()), reason='node and the frontend toolchain are needed')


def manifest():
    return json.loads(MANIFEST.read_text())


def cases(**where):
    """Manifest cases, optionally filtered by field equality (composition='text') or tag (tag='clean')."""
    tag = where.pop('tag', None)
    return [c for c in manifest()['cases'] if all(c.get(k) == v for k, v in where.items()) and (tag is None or tag in c['tags'])]


def folder(case):
    return WORK / (case if isinstance(case, str) else case['name'])


def materialized(case):
    return (folder(case) / 'case.json').exists()


def analysis(case):
    """The materialised canonical JSON of a case, or a skip when it has not been built."""
    path = folder(case) / 'analysis.json'
    if not path.exists():
        pytest.skip(f"case {case if isinstance(case, str) else case['name']} is not materialised; run python -m validation.dashboard.corpus")
    return json.loads(path.read_text())


def record(case):
    path = folder(case) / 'case.json'
    if not path.exists():
        pytest.skip('case not materialised')
    return json.loads(path.read_text())


def params(selected=None, **where):
    """pytest parameters for manifest cases, with readable ids."""
    chosen = selected if selected is not None else cases(**where)
    return [pytest.param(c, id=c['name']) for c in chosen]


class Node:
    """One esbuild bundle of a TypeScript entry, callable from Python: call('fromAnalysis', analysis, 'regression')."""

    def __init__(self, entry, work: Path):
        self.work = work
        self.bundle = work / (Path(entry).stem + '.mjs')
        subprocess.run([str(ESBUILD), str(FRONTEND / entry), '--bundle', '--format=esm', '--platform=node', '--loader:.json=json',
                        f'--outfile={self.bundle}', '--log-level=error'], check=True)
        self.runner = work / 'run.mjs'
        self.runner.write_text(
            "import { readFileSync } from 'node:fs';\n"
            f"const mod = await import({json.dumps(self.bundle.as_uri())});\n"
            "const { name, args } = JSON.parse(readFileSync(process.argv[2], 'utf8'));\n"
            "const out = await mod[name](...args);\n"
            "process.stdout.write(JSON.stringify(out === undefined ? null : out));\n")

    def call(self, name, *args):
        payload = self.work / 'payload.json'
        payload.write_text(json.dumps({'name': name, 'args': args}))
        out = subprocess.run(['node', str(self.runner), str(payload)], capture_output=True, text=True)
        if out.returncode:
            raise AssertionError(f'{name} failed in node:\n{out.stderr[-2000:]}')
        return json.loads(out.stdout)
