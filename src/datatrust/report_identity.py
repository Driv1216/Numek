"""Per-workflow presentation identity: how a report was rendered, separately from how its evidence was computed.

Each presentation family (one per report workflow) is identified by a digest over exactly what can change its rendered
report:
- the family's template closure, resolved from its root templates through every include and import (jinja2.meta), so a
  partial added later cannot be missed;
- the Python presentation modules the family uses, by source bytes;
- optionally, the source of individual functions a family calls outside those modules (none at present);
- the concept-catalogue entries the family uses (report_concepts), so a concept added for another workflow never changes
  this one's identity;
- the print-policy version.
Changing one workflow's template or projection therefore changes only that workflow's identity; changing a shared
partial or module changes every family that depends on it, visibly.

Nothing here reads analytical code or results beyond the dispatch fields that select a family.
"""
import hashlib
import importlib
import importlib.util
import inspect
from functools import lru_cache
from pathlib import Path

TEMPLATES = Path(__file__).parent / 'templates'
PRINT_POLICY_VERSION = 'report_print_v1'
SHELL, SCRIPT = '_report_shell.html', '_report_script.js.html'
_SHARED_MODULES = ('datatrust.report_format', 'datatrust.report_layout')
_CONCEPTS = ('datatrust.report_concepts', 'datatrust.report_context')
_TABULAR = ('datatrust.tabular_presentation',) + _CONCEPTS

FAMILIES = {
    'classification': {'roots': ('classification_report.html',), 'modules': _SHARED_MODULES + _TABULAR},
    'regression': {'roots': ('regression_report.html',), 'modules': _SHARED_MODULES + _TABULAR},
    'unlabeled': {'roots': ('unlabeled_report.html',), 'modules': _SHARED_MODULES + _TABULAR},
    'm3': {'roots': ('m3_report.html',), 'modules': _SHARED_MODULES + _CONCEPTS + ('datatrust.presentation', 'datatrust.report_structured')},
    'm4': {'roots': ('m4_report.html',), 'modules': _SHARED_MODULES + _CONCEPTS + ('datatrust.m4_presentation', 'datatrust.report_structured')},
    'temporal': {'roots': ('temporal_report.html',), 'modules': _SHARED_MODULES + _CONCEPTS + ('datatrust.temporal_presentation', 'datatrust.report_structured')},
    'text': {'roots': ('text_report.html',), 'modules': _SHARED_MODULES + _CONCEPTS + ('datatrust.text_presentation', 'datatrust.report_structured')},
    'image': {'roots': ('image_report.html',), 'modules': _SHARED_MODULES + _CONCEPTS + ('datatrust.image_presentation', 'datatrust.report_structured')},
    'cross': {'roots': ('cross_report.html',), 'modules': _SHARED_MODULES + _CONCEPTS + ('datatrust.cross_presentation', 'datatrust.report_structured')},
}
_SCHEMA_FAMILY = {'1.7': 'cross', '1.6': 'image', '1.5': 'text', '1.4': 'temporal', '1.3': 'm4', '1.2': 'm3'}


def family_of(value):
    """The presentation family that renders this completed result (a result object or its dict), following the
    renderer's own dispatch order."""
    if not isinstance(value, dict):
        value = value.to_dict()
    family = _SCHEMA_FAMILY.get(str(value.get('schema_version')))
    if family:
        return family
    if value.get('methodology_id') == 'classification_legacy_2026_08_13':
        return 'classification'
    return 'regression' if (value.get('task') or {}).get('kind') == 'regression' else 'unlabeled'


def template_closure(roots, source=None):
    """Every template reachable from the roots through include, import and extends, sorted by name."""
    from jinja2 import Environment, meta
    env = Environment()
    read = source or (lambda name: (TEMPLATES / name).read_text(encoding='utf-8'))
    seen, pending = set(), list(roots)
    while pending:
        name = pending.pop()
        if name in seen:
            continue
        seen.add(name)
        for child in meta.find_referenced_templates(env.parse(read(name))):
            if child is None:
                raise ValueError(f'{name} references a template by a dynamic name; presentation identity needs literal names.')
            pending.append(child)
    return tuple(sorted(seen))


def _module_bytes(name):
    origin = importlib.util.find_spec(name).origin
    return Path(origin).read_bytes()


def _function_source(target):
    module, _, attribute = target.partition(':')
    return inspect.getsource(getattr(importlib.import_module(module), attribute)).encode()


def dependencies(family):
    """The exact inputs of a family's identity: (kind, name) pairs in a stable order."""
    spec = FAMILIES[family]
    names = template_closure(spec['roots'])
    if SHELL in names:
        names = tuple(sorted(set(names) | {SCRIPT}))
    return ([('template', name) for name in names]
            + [('module', name) for name in spec['modules']]
            + [('function', name) for name in spec.get('functions', ())])


def compute_digest(family, *, read_template=None, read_module=None, read_function=None, read_catalogue=None):
    """The family digest. The readers are injectable so tests can perturb one input in memory."""
    read_template = read_template or (lambda name: (TEMPLATES / name).read_bytes())
    read_module = read_module or _module_bytes
    read_function = read_function or _function_source
    readers = {'template': read_template, 'module': read_module, 'function': read_function}
    digest = hashlib.sha256(f'policy\0{PRINT_POLICY_VERSION}\0'.encode())
    spec = FAMILIES[family]
    names = template_closure(spec['roots'], source=lambda n: read_template(n).decode('utf-8'))
    if SHELL in names:   # the shell embeds the report script, which is read as bytes rather than included
        names = tuple(sorted(set(names) | {SCRIPT}))
    inputs = ([('template', n) for n in names] + [('module', n) for n in spec['modules']]
              + [('function', n) for n in spec.get('functions', ())])
    from datatrust.report_catalogue import catalogue_bytes
    inputs.append(('catalogue', family))   # only the concept entries this family uses
    readers['catalogue'] = read_catalogue or catalogue_bytes
    for kind, name in inputs:
        content = readers[kind](name)
        digest.update(f'{kind}\0{name}\0{len(content)}\0'.encode())
        digest.update(content)
    return digest.hexdigest()


def _package_version():
    from importlib.metadata import PackageNotFoundError, version
    try:
        return version('datatrust')
    except PackageNotFoundError:
        return 'not recorded'


@lru_cache(maxsize=None)
def identity(family):
    return {'family': family, 'presentation_id': f'{family}-{compute_digest(family)[:12]}',
            'package_version': _package_version(), 'print_policy': PRINT_POLICY_VERSION}


def presentation_line(family):
    value = identity(family)
    return f"DataTrust {value['package_version']}, report presentation {value['presentation_id']}"


@lru_cache(maxsize=1)
def all_templates_identity():
    """The digest of every report template: the identity used before per-workflow identity, kept for callers that
    render pages outside a single report family."""
    digest = hashlib.sha256()
    for path in sorted(TEMPLATES.glob('*.html')):
        digest.update(path.name.encode() + b'\0' + path.read_bytes())
    return {'package_version': _package_version(), 'report_templates': digest.hexdigest()[:12]}


def legacy_presentation_line():
    value = all_templates_identity()
    return f"DataTrust {value['package_version']}, report templates {value['report_templates']}"
