"""Immutable historical assessments and joint conservative disclosure."""
import copy
import json
from .contracts import EvaluationError, DisclosureSpec, digest, exact
from .result import EvaluationResult, SharedResult, completed_shape
from .history_contracts import HISTORY_RESULT, HISTORY_METHOD


def validate(data):
    if data.get('schema_version') != HISTORY_RESULT or data.get('methodology_id') != HISTORY_METHOD:
        raise EvaluationError('Unsupported longitudinal result.')
    completed_shape(data)
    history = data.get('history')
    if not isinstance(history, dict) or not isinstance(history.get('comparisons'), list) or not isinstance(history.get('windows'), list):
        raise EvaluationError('Invalid longitudinal evidence.')
    populations = {p['id']: p for p in data['coverage']['populations']}
    for comparison in history['comparisons']:
        for contrast in comparison.get('metrics', []):
            for side in ('reference', 'current'):
                if contrast.get(side + '_population_id') not in populations:
                    raise EvaluationError('Historical contrast population is missing.')
    for key in ('assessment_digest', 'projection_digest'):
        if key in data and key == 'projection_digest' and digest({k: v for k, v in data.items() if k != key}) != data[key]:
            raise EvaluationError('Historical projection identity differs.')


class LongitudinalResult(EvaluationResult):
    @classmethod
    def from_dict(cls, value, *, private=None):
        from .contracts import strict_json
        if isinstance(value, str): value = strict_json(value)
        validate(value)
        if value.get('audience') == 'shareable':
            if private is not None: raise EvaluationError('Shareable history cannot acquire private evidence.')
            return HistoricalShared(copy.deepcopy(value))
        if not isinstance(private, dict): raise EvaluationError('Protected history requires its manifest.')
        payload = {k: v for k, v in value.items() if k != 'binding'}
        binding = value.get('binding', {})
        if (digest(payload) != binding.get('analysis_digest') or private.get('analysis_digest') != binding.get('analysis_digest')
                or digest(private) != binding.get('private_manifest_digest') or private.get('analysis_id') != value['analysis_id']):
            raise EvaluationError('Historical assessment binding differs.')
        from .history_contracts import LongitudinalSpec
        LongitudinalSpec.from_dict(private['history_spec'])
        return cls({k: copy.deepcopy(v) for k, v in value.items() if k not in {'execution', 'binding'}},
                   copy.deepcopy(private), copy.deepcopy(value['execution']), copy.deepcopy(binding))

    @property
    def source_paths(self):
        root = getattr(self, '_workspace_location', self.private.get('workspace_root'))
        return (root,) if root else ()

    def to_dict(self, audience='shareable', disclosure=None):
        if audience == 'local': return self.to_private_dict()
        if audience != 'shareable': raise EvaluationError('Unsupported audience.')
        policy = disclosure or self.private['config']['disclosure']
        if isinstance(policy, dict): policy = DisclosureSpec.from_dict(policy)
        raw = self.to_private_dict()
        protected = policy.policy == 'conservative_aggregates_v1'
        # Joint withholding is intentionally conservative across the complete
        # window/restatement family; never permit a delta to undo a withheld cell.
        def family(m):
            if m['family'] in {'calibration','calibration_diagnostics','probability_quality','high_confidence','high_confidence_decision'}:return 'probability'
            if m['family'] in {'ranking','ranking_curve'}:return 'ranking'
            if m['family'] == 'outcome_availability':return 'label_observation'
            if m['family'] in {'performance','confusion','classification','regression','class_performance','failures'}:return 'performance'
            if any(v in m['metric'] for v in ('coverage','efficiency','interval','set_','pinball','crps','wis')):return 'uncertainty'
            return m['family']
        withheld=set()
        if protected:
            for m in raw['measurements']:
                if 0<int(m['denominator'])<policy.minimum_denominator or any(v is not None and 0<float(v)<policy.minimum_component for v in m.get('sensitive_counts',[])):
                    withheld.add(family(m))
        if withheld & {'performance','probability','uncertainty'}:withheld.update({'performance','probability','uncertainty'})
        unsafe=bool(withheld)
        aliases = {r['id']: 'variant_' + str(i+1) for i, r in enumerate(raw['runs'])}
        public = {'schema_version': HISTORY_RESULT, 'methodology_id': HISTORY_METHOD,
                  'analysis_id': raw['analysis_id'], 'generated_at': raw['generated_at'], 'name': 'ConfidenceGuard reliability history',
                  'audience': 'shareable', 'task': {'kind': raw['task']['kind']},
                  'runs': [{'id': aliases[r['id']], 'display_name': 'Variant ' + str(i+1), 'role': 'historical'} for i, r in enumerate(raw['runs'])],
                  'outcomes': {'interpretation': 'Supplied observed outcomes; representativeness and full-population performance are not established.'},
                  'comparison': None, 'measurements': [], 'checks': [], 'findings': [],
                  'coverage': {'population_provenance_version': '1.1', 'populations': [],
                               'analytical_scope': 'All admitted historical populations; exact lineage retained locally.',
                               'retention_limits': {}, 'limitations': raw['coverage']['limitations'],
                               'privacy_withholding': 'Related historical family withheld.' if unsafe else 'Disclosed aggregates under recorded policy.',
                               'not_anonymity_guarantee': True},
                  'execution': {'status': 'completed', 'backend': 'duckdb_local'},
                  'origin_binding': raw['binding'], 'disclosure': {**policy.to_dict(), 'display_labels': {}}}
        window_aliases={w['id']:'window_'+str(i+1) for i,w in enumerate(raw['history']['windows'])}
        scope_aliases={scope:'scope_'+str(i+1) for i,scope in enumerate(sorted({m['scope'] for m in raw['measurements']}))}
        def public_scope(scope):
            for window in sorted(window_aliases,key=len,reverse=True):
                if scope.startswith(window+'/'):
                    tail=scope[len(window)+1:]
                    if tail=='overall' or __import__('re').fullmatch(r'cohort_\d+/(category_\d+|bin_\d+|missing|other|invalid|out_of_range)',tail):return window_aliases[window]+'/'+tail
                    return window_aliases[window]+'/'+scope_aliases[scope]
            return scope_aliases.get(scope,'historical_scope')
        private_metrics = {'roc_pr_curve', 'ranking_score', 'selection_score', 'class_score_maximum'}
        metric_aliases = {}; visible_definitions = set()
        def definition_fields(item):
            if 'metric_key' not in item: return {}
            if protected:
                key = metric_aliases.setdefault(item['metric_key'], 'metric_' + str(len(metric_aliases)+1))
                return {'metric_key': key, 'metric_label': item['metric'] + ' [' + key + ']'}
            return {key: copy.deepcopy(item[key]) for key in ('metric_key','metric_label','metric_identity') if key in item}
        for measurement in raw['measurements']:
            if protected and (measurement['metric'] in private_metrics or family(measurement) in withheld): continue
            m = {k: copy.deepcopy(v) for k, v in measurement.items() if k not in {'sensitive_counts', 'disclosure_group', 'evidence_refs', 'data', 'metric_key', 'metric_label', 'metric_identity'}}
            m.update(definition_fields(measurement))
            m['run'] = aliases[m['run']];m['scope']=public_scope(m['scope']); m['evidence_refs'] = []; m['data'] = {}
            if not protected: m['data'] = copy.deepcopy(measurement['data'])
            public['measurements'].append(m)
            visible_definitions.add((measurement['run'], measurement.get('metric_key',measurement['metric'])))
        ids = {m['population_id'] for m in public['measurements']}
        public['coverage']['populations'] = [{**{k: p[k] for k in ('id', 'scope', 'denominator', 'denominator_kind')}, 'run': aliases[p['run']],'scope':public_scope(p['scope'])} for p in raw['coverage']['populations'] if p['id'] in ids]
        edge_aliases={e['id']:'comparison_'+str(i+1) for i,e in enumerate(raw['history']['comparisons'])}
        comparisons = []
        for index, edge in enumerate(raw['history']['comparisons']):
            record = {'id': 'comparison_' + str(index+1), 'kind': edge['kind'], 'status': edge['status'],
                      'reasons': edge['reasons'], 'metrics': []}
            for contrast in edge.get('metrics', []):
                if any(v not in {p['id'] for p in public['coverage']['populations']} for k,v in contrast.items() if k.endswith('_population_id')):continue
                item={k: copy.deepcopy(v) for k, v in contrast.items() if k in {'scope','metric', 'value', 'value_state', 'reference_population_id', 'current_population_id', 'inference', 'practical_assessment'}}
                item.update(definition_fields(contrast))
                if protected and 'inference' in item:
                    item['inference']={k:v for k,v in item['inference'].items() if k in {'status','reason','method','design','family_size','adjustment','level','exploratory','lower','upper','estimate','conditioning','scope','completed_replicates','minimum_replicates','nominal_tail_probability','block_length','bin_ns'}}
                record['metrics'].append(item)
            comparisons.append(record)
        public['history'] = {'windows': [{**w,'id':window_aliases[w['id']]} for w in raw['history']['windows']], 'comparisons': comparisons,
                             'catalog_sequence': raw['history']['catalog_sequence'], 'as_of': raw['history']['as_of'],
                             'maturity': raw['history']['maturity'], 'restates': raw['history'].get('restates'),
                             'scope': 'Associational evidence; no causal attribution, production approval or future coverage guarantee.',
                             'mix': [] if protected else [{**m,'comparison':edge_aliases[m['comparison']]} for m in raw['history']['mix']],
                             'drift': [] if protected else [{**d,'comparison':edge_aliases[d['comparison']]} for d in raw['history']['drift']],
                             'temporal': ([{'variant':aliases[v['variant']],'metric':v['metric'],**definition_fields(v),'points':[{**p,'window':window_aliases[p['window']]} for p in v['points']],'change_candidates':[],'interpretation':'Disclosed aggregate timeline; detailed temporal investigation retained locally.'} for v in raw['history']['temporal'] if (v['variant'],v.get('metric_key',v['metric'])) in visible_definitions] if protected else [{**v,'variant':aliases[v['variant']],'points':[{**p,'window':window_aliases[p['window']]} for p in v['points']],'change_candidates':[{**c,'window':window_aliases[c['window']]} for c in v['change_candidates']]} for v in raw['history']['temporal']]),
                             'joint_withholding': unsafe,'withheld_families':sorted(withheld)}
        public['checks'] = [{'id': 'check_' + str(i+1), 'applicability': c.get('applicability', 'applicable'),
                             'execution': c.get('execution', 'completed'), 'reason': c.get('reason')} for i, c in enumerate(raw['checks'])]
        public['findings'] = [{'code': 'joint_history_withholding' if unsafe else 'historical_qualification', 'priority': 'Review',
                               'message': 'Related historical evidence is withheld jointly.' if unsafe else 'Compare observed outcomes only under the displayed identity, maturity and observation qualifications.'}]
        public['projection_digest'] = digest(public)
        return exact(public)

    def resolve_evidence(self, reference, *, allowed_roots, reveal_values=False, max_characters=240):
        from .history_storage import Catalog, file_lock
        if not allowed_roots or not isinstance(reveal_values, bool) or not 1 <= max_characters <= 240:
            raise EvaluationError('Explicit authorized roots and bounded reveal are required.')
        root = getattr(self, '_workspace_location', self.private.get('workspace_root'))
        from pathlib import Path
        if not root or not any(Path(root).absolute() == Path(r).absolute() or Path(r).absolute() in Path(root).absolute().parents for r in allowed_roots):
            raise EvaluationError('Historical evidence root is not authorized.', 'roots_required')
        location = self.private['locators'].get(reference)
        if not location: raise EvaluationError('Unknown retained reference.', 'unknown_reference')
        catalog = Catalog(root)
        with file_lock(catalog.objects_lock, False):
            for fact in catalog.iter_facts('prediction', sequence=self.data['history']['catalog_sequence'],fact_digests=[location['fact_digest']],max_records=1):
                if fact['fact_digest'] != location['fact_digest']: continue
                result = {'reference': reference, 'status': 'resolved', 'values_disclosed': reveal_values}
                if reveal_values:
                    text = json.dumps(fact['payload'], ensure_ascii=True)
                    result.update(excerpt=text[:max_characters], excerpt_truncated=len(text) > max_characters)
                return result
        raise EvaluationError('Historical evidence was removed or is unavailable.', 'evidence_unavailable')


class HistoricalShared(SharedResult):
    def to_dict(self, audience='shareable', **kwargs):
        if audience != 'shareable': raise EvaluationError('Shareable history cannot recover exact evidence.')
        return copy.deepcopy(self.data)
