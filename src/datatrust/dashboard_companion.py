"""The results dashboard's presentation companion (dashboard_companion_v1): the report-owned pieces a dashboard shows.

The dashboard draws its evidence from the canonical analysis JSON. What it must not reinvent is owned by each
workflow's report projection (`*_presentation.report_view`), which runs on that same JSON:
- reader-facing finding titles and ranks, including the evidence-meaning labels of the text and image workflows, which
  record no priority;
- the report's own review actions, where the report groups them (text: `executive_summary`; images: `executive_actions`);
- the concept catalogue entries the report explains;
- the report's own names for what the dashboard tiles show (text and image family titles and evidence meanings;
  records-and-documents section titles, population names, outcome labels and per-population explanations).

Links into the report are never assumed. Every locator is verified against the exact HTML bytes being served, the live
report or an immutable saved one, by reading their element ids and finding-index links:
- **anchor**: the report_view anchor exists, and the finding index links it with the same title;
- **section**: the report section that holds the finding's evidence exists (text workflow topics);
- **index_position**: the finding is listed, by title, in the served report's finding index;
- **none**: this report version has neither (older reports).

Nothing is analysed, nothing from the source data is read, and nothing beyond what the report renders from the same
JSON is returned. Results are cached per scope, keyed by the analysis and served-HTML digests, the report's
presentation identity and print profile, and the recorded disclosure context; a new live job or saved entry is a new
scope, and the small LRU drops what is no longer asked for.
"""
import hashlib
import json
import re
import threading
from collections import OrderedDict
from html.parser import HTMLParser

VERSION = 'dashboard_companion_v1'
NARRATIVE_ONLY = frozenset({'no_major_issues'})
PRIORITY_ORDER = {'high': 0, 'moderate': 1, 'low': 2}
# The text report's own action order (text_presentation.executive_summary); everything else after it.
MEANING_ORDER = {'deterministic_violation': 0, 'contextual_observation': 1, 'heuristic_candidate': 2, 'model_assisted_candidate': 3}
CONCEPT_FIELDS = ('id', 'term', 'definition', 'means', 'does_not_mean', 'methodology_ref', 'anchor')
# Every methodology a DataTrust report projection is written for; anything else is shown as recorded, without one.
KNOWN_METHODS = frozenset({
    'classification_legacy_2026_08_13', 'tabular_regression_v1', 'unlabeled_csv_profile_v1', 'tabular_partial_classification_v1',
    'tabular_annotation_regression_v1', 'tabular_multioutput_regression_v1', 'tabular_multilabel_v1', 'tabular_clustering_readiness_v1',
    'tabular_anomaly_readiness_v1', 'tabular_clustering_readiness_v2', 'tabular_anomaly_readiness_v2', 'tabular_role_profile_v1', 'm4_local_2026_10_10', 'm4_local_2026_11_25', 'temporal_reliability_v1', 'text_reliability_v1',
    'image_reliability_v1', 'cross_representation_reliability_v1'})
_CACHE_SIZE = 16


class _Recorded:
    """A completed result dict presented to a report projection exactly as the report renderer receives a stored
    result: attribute reads come from the dict, and schema 1.0/1.1 tasks read as the TaskSpec they were written from."""

    def __init__(self, value):
        self._value = value
        self.schema_version = value.get('schema_version')
        self.source_paths = ()
        task = value.get('task')
        if isinstance(task, dict) and self.schema_version in {'1.0', '1.1'}:
            from datatrust.contracts import TaskSpec
            self.task = TaskSpec(task['kind'], target=task.get('target'))

    def to_dict(self):
        return self._value

    def __getattr__(self, key):
        try:
            return self._value[key]
        except KeyError as exc:
            raise AttributeError(key) from exc


class _Locators(HTMLParser):
    """Element ids, finding-index rows (title, linked anchor) and the report's recorded presentation and print profile."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ids, self.rows = set(), []
        self._index_depth, self._row, self._cell, self._link = 0, None, None, None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if a.get('id'):
            self.ids.add(a['id'])
        if tag == 'table' and 'dt-index' in (a.get('class') or '').split():
            self._index_depth = 1
        elif tag == 'table' and self._index_depth:
            self._index_depth += 1
        if not self._index_depth:
            return
        if tag == 'tr':
            self._row = {'title': '', 'anchor': None, 'cells': 0, 'header': False}
        elif tag in {'td', 'th'} and self._row is not None:
            self._row['cells'] += 1
            self._row['header'] = self._row['header'] or tag == 'th'
            self._cell = self._row['cells']
        elif tag == 'a' and self._row is not None and self._cell == 1 and (a.get('href') or '').startswith('#'):
            self._row['anchor'] = a['href'][1:]

    def handle_endtag(self, tag):
        if tag == 'table' and self._index_depth:
            self._index_depth -= 1
        elif tag == 'tr' and self._row is not None:
            if not self._row['header'] and self._row['title'].strip():
                self.rows.append({'title': ' '.join(self._row['title'].split()), 'anchor': self._row['anchor']})
            self._row = None
        elif tag in {'td', 'th'}:
            self._cell = None

    def handle_data(self, data):
        if self._row is not None and self._cell == 1:
            self._row['title'] += data


def read_locators(html):
    """What a served report actually contains: ids, finding-index rows, presentation id and print profile."""
    text = html.decode('utf-8', 'replace') if isinstance(html, bytes) else html
    parser = _Locators()
    parser.feed(text)
    presentation = re.search(r'report presentation ([a-z0-9]+-[0-9a-f]{6,})', text)
    profile = re.search(r'Print profile: (focused|complete)', text)
    return {'ids': parser.ids, 'rows': parser.rows, 'presentation_id': presentation.group(1) if presentation else None,
            'print_profile': profile.group(1) if profile else None}


def _view(family, recorded):
    if family == 'cross':
        from datatrust.cross_presentation import report_view
        return report_view(recorded, 'focused')
    if family == 'image':
        from datatrust.image_presentation import report_view
        return report_view(recorded, 'focused')
    if family == 'text':
        from datatrust.text_presentation import report_view
        return report_view(recorded, 'focused')
    if family == 'temporal':
        from datatrust.temporal_presentation import report_view
        return report_view(recorded, profile_name='focused')
    if family == 'm4':
        from datatrust.m4_presentation import report_view
        return report_view(recorded, 'focused')
    if family == 'm3':
        from datatrust.presentation import report_view
        return report_view(recorded, 'focused')
    from datatrust.tabular_presentation import report_view
    return report_view(recorded.to_dict(), 'focused')


def _names(family, value, view):
    """The report's reader-facing names for the families, meanings, populations and outcomes this result records."""
    evidence = [e for e in value.get('evidence') or [] if isinstance(e, dict)]
    try:
        if family in {'text', 'image'}:
            from importlib import import_module
            p = import_module(f'datatrust.{family}_presentation')
            meanings = {e.get('meaning') for e in evidence} | {f.get('meaning') for f in value.get('findings') or [] if isinstance(f, dict)}
            return {'families': {e['family']: p.family_title(e['family']) for e in evidence if e.get('family')},
                    'meanings': {m: p.MEANINGS.get(m, str(m).replace('_', ' ').capitalize()) for m in meanings if m}}
        if family == 'cross':
            from datatrust import cross_presentation as p
            by_section = {s.get('id'): s.get('title') for s in (view or {}).get('sections') or []}
            statuses = {k for e in evidence for k, v in (e.get('data') or {}).items() if k in p.LABELS and not isinstance(v, (dict, list))}
            statuses |= {d.get('status') for e in evidence for d in (e.get('data') or {}).get('details') or [] if isinstance(d, dict) and d.get('status') in p.LABELS}
            return {'families': {f: by_section.get(sid) or f.replace('_', ' ').capitalize() for f, sid in p.SECTION_IDS.items() if any(e.get('family') == f for e in evidence)},
                    'populations': {e['population']: p.population_label(e['population']) for e in evidence if e.get('population')},
                    'statuses': {k: p.label(k) for k in sorted(statuses)},
                    'explanations': {e['id']: p.explanation(e['family'], e.get('data') or {}) for e in evidence if e.get('id') and e.get('family') in p.SECTION_IDS}}
    except Exception:
        return None
    return None


def _interpretation(family, value):
    """interpretation_v1 for a known methodology; None for one DataTrust has no projection for, or if it cannot be read."""
    if not family:
        return None
    try:
        from datatrust.interpretation import interpret
        return interpret(value, family)
    except Exception:
        return None


def _family(value):
    from datatrust.report_identity import family_of
    if value.get('methodology_id') not in KNOWN_METHODS:
        return None
    try:
        return family_of(_Recorded(value))
    except Exception:
        return None


def _title_key(title):
    return ' '.join(str(title or '').split())


def _locate(entry, title, family, finding, locators, sections, used):
    """The verified way into the served report for one finding (see the module docstring)."""
    if locators is None:
        return {'kind': 'none', 'value': None, 'reason': 'no report is available for this result'}
    anchor = entry.get('anchor') if entry else None
    rows = locators['rows']
    linked = [r for r in rows if r['anchor'] == anchor]
    if anchor and anchor in locators['ids']:
        if any(_title_key(r['title']) == _title_key(title) for r in linked):
            return {'kind': 'anchor', 'value': anchor, 'checked': 'index_link'}
        if not rows:  # a report without a finding index: the id exists, but its title could not be cross-checked
            return {'kind': 'anchor', 'value': anchor, 'checked': 'id_only'}
    section = sections.get(str(finding.get('id'))) if family == 'text' else None
    if section and f'topic-{section}' in locators['ids']:
        return {'kind': 'section', 'value': f'topic-{section}'}
    # The k-th row with this title, for the k-th finding with this title (titles repeat, e.g. temporal window effects).
    matching = [i for i, r in enumerate(rows) if _title_key(r['title']) == _title_key(title)]
    nth = used.setdefault(_title_key(title), 0)
    if nth < len(matching):
        used[_title_key(title)] += 1
        return {'kind': 'index_position', 'value': matching[nth] + 1, 'of': len(rows)}
    return {'kind': 'none', 'value': None, 'reason': 'this report version has no finding index entry for it'}


def _rank(finding, entry, family):
    meaning = finding.get('meaning')
    if family in {'text', 'image'} or (meaning and not (finding.get('severity') or finding.get('priority'))):
        label = (entry or {}).get('severity') or str(meaning or '').replace('_', ' ')
        label = label[:1].upper() + label[1:]
        return {'kind': 'evidence_meaning', 'value': meaning, 'label': label, 'order': MEANING_ORDER.get(meaning, len(MEANING_ORDER))}
    raw = str(finding.get('priority') or finding.get('severity') or '')
    return {'kind': 'priority', 'value': raw.capitalize(), 'label': raw.capitalize(), 'order': PRIORITY_ORDER.get(raw.lower(), 3)}


def build(value, html=None, presentation=None):
    """The companion for one completed result and the report HTML served with it (None when there is none).
    `presentation` is the identity recorded elsewhere for that HTML ({'id', 'source': 'manifest' | 'current'}), used when
    the report does not print its own (M4 to M9 reports do not)."""
    family = _family(value)
    recorded = _Recorded(value)
    view, view_error = None, None
    if family:
        try:
            view = _view(family, recorded)
        except Exception as exc:  # an older or unknown shape: the dashboard falls back to canonical titles
            view_error = f'{type(exc).__name__}: the report projection could not read this result'
    locators = read_locators(html) if html is not None else None
    if presentation and presentation.get('source') == 'current' and not presentation.get('id') and family:
        from datatrust.report_identity import identity
        presentation = {'id': identity(family)['presentation_id'], 'source': 'current'}
    entries = {}
    for position, entry in enumerate((view or {}).get('findings') or []):
        index = entry.get('index')
        if index is None:
            match = re.fullmatch(r'finding-(\d+)', str(entry.get('anchor') or ''))
            index = int(match.group(1)) if match else position
        entries.setdefault(index, entry)
    sections = {}
    for section in (view or {}).get('sections') or []:
        for item in section.get('records') or []:
            if isinstance(item, dict) and item.get('id') is not None and section.get('id'):
                sections.setdefault(str(item['id']), section['id'])
    findings, used = [], {}
    for index, finding in enumerate(value.get('findings') or []):
        if not isinstance(finding, dict) or finding.get('code') in NARRATIVE_ONLY:
            continue
        entry = entries.get(index)
        title = (entry or {}).get('title') or finding.get('title') or ' · '.join(str(finding[k]).replace('_', ' ') for k in ('family', 'meaning') if finding.get(k))
        findings.append({'index': index, 'ref': finding.get('id') or finding.get('code'), 'title': title, 'rank': _rank(finding, entry, family),
                         'effect': (entry or {}).get('effect'), 'locator': _locate(entry, title, family, finding, locators, sections, used)})
    actions = None
    if family == 'text' and view:
        actions = [{'family': a['family'], 'meaning': a['meaning'], 'action': a['action'], 'evidence_ids': a['evidence_ids'],
                    'observations': a['observations']} for a in view['executive']['actions']]
    elif family == 'image' and view:
        actions = [{'title': a['title'], 'meaning': a.get('meaning'), 'facts': a.get('facts') or [], 'action': a.get('action')} for a in view.get('actions') or []]
    concepts = []
    if view is not None:
        try:
            from datatrust.report_concepts import build_manifest
            concepts = [{k: c.get(k) for k in CONCEPT_FIELDS} for c in build_manifest(family, value, view)['concepts']]
        except Exception:
            concepts = []
    report = None
    if locators is not None:
        recorded = (presentation or {}) if not locators['presentation_id'] else {'id': locators['presentation_id'], 'source': 'report'}
        report = {'presentation_id': recorded.get('id'), 'presentation_source': recorded.get('source') if recorded.get('id') else None,
                  'print_profile': locators['print_profile'],
                  'finding_index': bool(locators['rows']), 'finding_index_rows': len(locators['rows']),
                  'sections': sorted(i for i in locators['ids'] if i.startswith('topic-'))}
    return {'companion': VERSION, 'family': family, 'methodology_id': value.get('methodology_id'), 'schema_version': value.get('schema_version'),
            'report': report, 'view_error': view_error, 'findings': findings, 'actions': actions, 'concepts': concepts,
            'names': _names(family, value, view) if view is not None else None,
            'interpretation': _interpretation(family, value)}


def disclosure_context(value):
    """The recorded disclosure settings that change what a report shows (M6/M7/M9 export identity and disclosure)."""
    profile = value.get('profile') if isinstance(value.get('profile'), dict) else {}
    context = {k: profile.get(k) for k in ('disclosure', 'export_identity') if profile.get(k) is not None}
    return json.dumps(context, sort_keys=True, default=str)


class Cache:
    """A small per-process cache. A key names the scope (one live job or one saved entry) and every input that changes
    the result: analysis and served-HTML digests, presentation identity, print profile and disclosure context."""

    def __init__(self, size=_CACHE_SIZE):
        self.size, self.items, self.lock = size, OrderedDict(), threading.Lock()

    def companion(self, scope, analysis_bytes, html_bytes, presentation=None):
        value = json.loads(analysis_bytes)
        if html_bytes is None:
            return build(value, None, presentation)
        locators = read_locators(html_bytes)
        key = (scope, hashlib.sha256(analysis_bytes).hexdigest(), hashlib.sha256(html_bytes).hexdigest(),
               locators['presentation_id'] or (presentation or {}).get('id'), locators['print_profile'], disclosure_context(value))
        with self.lock:
            if key in self.items:
                self.items.move_to_end(key)
                return self.items[key]
        result = build(value, html_bytes, presentation)
        with self.lock:
            self.items[key] = result
            self.items.move_to_end(key)
            while len(self.items) > self.size:
                self.items.popitem(last=False)
        return result

    def forget(self, scope):
        with self.lock:
            for key in [k for k in self.items if k[0] == scope]:
                del self.items[key]
