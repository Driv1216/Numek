"""Materialise the dashboard redesign corpus (cases.json) into git-ignored work folders.

For each case it writes, under validation/report_experience/work.nosync/dashboard/cases/<name>/:
- analysis.json: the completed canonical JSON. Stored cases are copied byte for byte; matrix and controlled cases are
  built with their own builders.
- report.html: the canonical report rendered from that JSON with the current templates (no reanalysis).
- case.json: where it came from, its digest and the facts the tests check (methodology, schema, findings, run status).

Stored milestone files are only read. Nothing outside work.nosync is written.

    PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:. .venv/bin/python -B -m validation.dashboard.corpus [--heavy] [names...]
"""
import argparse
import hashlib
import json
import shutil
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
VALIDATION = REPO / 'validation'
MANIFEST = Path(__file__).with_name('cases.json')
WORK = VALIDATION / 'report_experience/work.nosync/dashboard'
CASES = WORK / 'cases'
NARRATIVE_ONLY = {'no_major_issues'}


def manifest():
    return json.loads(MANIFEST.read_text())


def case_dir(name):
    return CASES / name


def facts(value):
    """The recorded facts a case is checked against. Read only; nothing is computed into evidence."""
    findings = [f for f in value.get('findings') or [] if f.get('code') not in NARRATIVE_ONLY]
    ranks = sorted({str(f.get('priority') or f.get('severity') or f.get('meaning')) for f in findings})
    return {'methodology_id': value.get('methodology_id'), 'schema_version': value.get('schema_version'),
            'findings': len(findings), 'ranks': ranks, 'execution': (value.get('execution') or {}).get('status'),
            'scoring': (value.get('scoring') or {}).get('status') if isinstance(value.get('scoring'), dict) else None,
            'guidance': 'guidance' in value, 'checks': isinstance(value.get('checks'), list)}


def _matrix_builders():
    from validation.report_experience.cases import cases
    return {c.name: c for c in cases()}


def _result_json(result):
    return result.json_text() if hasattr(result, 'json_text') else json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False)


def _stored(value):
    """A recorded result presented to the renderer as the milestone refresh scripts do. Schema 1.0/1.1 JSON records its
    task as a plain {kind, target} pair; the renderer reads it as the TaskSpec it was serialised from."""
    from datatrust import TaskSpec
    from validation.report_experience.cases import StoredResult
    result = StoredResult(value)
    task = value.get('task')
    if isinstance(task, dict) and value.get('schema_version') in {'1.0', '1.1'}:
        result.task = TaskSpec(task['kind'], target=task.get('target'))
    return result


def _render(result):
    from datatrust.renderer import render_analysis_result
    return render_analysis_result(result)


def materialize(case, matrix=None, force=False):
    out = case_dir(case['name'])
    if (out / 'case.json').exists() and not force:
        return json.loads((out / 'case.json').read_text())
    tmp = out.with_name(out.name + '.building')
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    started = time.monotonic()
    source = case['source']
    if 'stored' in source:
        path = VALIDATION / source['stored']
        text = path.read_text()
        result = None
        origin = {'kind': 'stored', 'path': f"validation/{source['stored']}", 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
    elif 'matrix' in source:
        matrix = matrix if matrix is not None else _matrix_builders()
        result = matrix[source['matrix']].build()
        text = _result_json(result)
        origin = {'kind': 'matrix', 'case': source['matrix'], 'builder': 'validation/report_experience/cases.py'}
    else:
        from validation.dashboard import controlled
        name = source['controlled']
        inputs = tmp / 'inputs'
        inputs.mkdir()
        if name == 'generic_unknown_methodology':
            base = case_dir('german_credit') / 'analysis.json'
            if not base.exists():
                materialize(next(c for c in manifest()['cases'] if c['name'] == 'german_credit'), matrix)
            text = json.dumps(controlled.generic_unknown_methodology(inputs, base), ensure_ascii=False, indent=2)
            result = None
        else:
            result = controlled.BUILDERS[name](inputs)
            text = _result_json(result)
        origin = {'kind': 'controlled', 'builder': f'validation/dashboard/controlled.py:{name}'}
    value = json.loads(text)
    (tmp / 'analysis.json').write_text(text)
    if case['composition'] == 'generic':
        html = ('<!doctype html><meta charset="utf-8"><title>Synthetic test report</title>'
                '<p>Synthetic test-only report for an unknown methodology. No DataTrust template renders it.</p>')
    else:
        html = _render(result if result is not None and not isinstance(result, dict) else _stored(value))
    (tmp / 'report.html').write_text(html)
    record = {'name': case['name'], 'origin': origin, 'analysis_sha256': hashlib.sha256(text.encode()).hexdigest(),
              'facts': facts(value), 'build_seconds': round(time.monotonic() - started, 2)}
    (tmp / 'case.json').write_text(json.dumps(record, indent=1) + '\n')
    shutil.rmtree(out, ignore_errors=True)
    tmp.rename(out)
    return record


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('names', nargs='*')
    parser.add_argument('--heavy', action='store_true', help='also build the optional heavy cases (wide_*, tall_1m, unlabeled_wide)')
    parser.add_argument('--force', action='store_true')
    args = parser.parse_args(argv)
    cases = [c for c in manifest()['cases'] if (not args.names or c['name'] in args.names) and (args.heavy or args.names or not c.get('optional'))]
    matrix = _matrix_builders() if any('matrix' in c['source'] for c in cases) else None
    failed = []
    for case in cases:
        try:
            record = materialize(case, matrix, force=args.force)
            print(f"{case['name']:34} {record['facts']['methodology_id']:38} findings={record['facts']['findings']:<3} {record['facts']['execution']:9} {record['build_seconds']}s", flush=True)
        except Exception as exc:  # report every case, then fail
            failed.append(case['name'])
            print(f"{case['name']:34} FAILED: {type(exc).__name__}: {exc}", flush=True)
    if failed:
        print('failed:', ', '.join(failed))
        sys.exit(1)


if __name__ == '__main__':
    main()
