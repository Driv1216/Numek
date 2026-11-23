"""Domain-classifier investigation (plan G.7): descriptive by default, with an optional exploratory test.

**Design.**
- **Unit:** the entity, one row per entity per arm: the first in the window, in keyed order. Entities present in
  both arms are excluded and counted.
- **Features:** only declared context features. Outcome, identifier and post-cutoff columns are refused.
- **Split:** a keyed hash puts each entity in half A or half B, 50/50.
- **Model:** a HistGradientBoosting classifier (the CG6 pin) is fit on half A and scored on half B.

**Outputs (descriptive).**
- the held-out AUC, with no confidence interval claimed;
- held-out permutation importance, which is association, not cause;
- calibration of the domain probability.

**Exploratory test.**
- An exact permutation of arm labels among half-B entities, conditional on the fitted classifier: 10,000
  permutations, with tied scores getting average ranks.
- It is valid under the declared assumption that reference and current entities are exchangeable under H₀.
- It is labelled an exploratory single look and recorded in the investigation ledger, never as formal incident
  standing.
- It is refused below 300 entities per arm in half B.
- Q-DC (``validation/cg7/domain_protocol.json``) qualifies it.

**Temporal note.** Reference and current periods differ in time, so seasonality is itself a "difference".

**Reads.** The investigation reads covariates only, under a ``covariate_inspection`` reservation: outcome-bearing
facts are not readable under it.
"""
import hashlib
import hmac
import math

import numpy as np

from ...contracts import EvaluationError

MIN_FIT_ENTITIES = 50
MIN_TEST_ENTITIES = 300
PERMUTATIONS = 10000
REFUSED_FEATURES = ('y', 'outcome', 'label', 'id', 'entity', 'entity_key', 'event_key')


def _ranks(scores):
    order = np.argsort(scores, kind='mergesort')
    ranks = np.empty(len(scores))
    sorted_scores = scores[order]
    i = 0
    while i < len(scores):
        j = i
        while j + 1 < len(scores) and sorted_scores[j + 1] == sorted_scores[i]:
            j += 1
        ranks[order[i:j + 1]] = (i + j) / 2 + 1
        i = j + 1
    return ranks


def auc(scores, labels):
    ranks = _ranks(np.asarray(scores, float))
    labels = np.asarray(labels, bool)
    n1, n0 = labels.sum(), (~labels).sum()
    return float((ranks[labels].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def permutation_p(scores, labels, *, permutations=PERMUTATIONS, seed=0):
    """Exact Monte Carlo permutation p-value of the held-out AUC (one-sided, larger AUC), conditional on the scores."""
    ranks = _ranks(np.asarray(scores, float))
    labels = np.asarray(labels, bool)
    n1, n0 = int(labels.sum()), int((~labels).sum())
    observed = (ranks[labels].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)
    rng = np.random.default_rng(seed)
    exceed, done = 0, 0
    while done < permutations:
        chunk = min(1000, permutations - done)
        perm = np.argsort(rng.random((chunk, len(ranks))), axis=1)[:, :n1]
        stats = (ranks[perm].sum(axis=1) - n1 * (n1 + 1) / 2) / (n1 * n0)
        exceed += int((stats >= observed - 1e-12).sum())
        done += chunk
    return (1 + exceed) / (1 + permutations), float(observed)


def _split(secret, entity):
    return hmac.new(secret, b'domain-split:' + entity, hashlib.sha256).digest()[0] & 1


def _encode(rows, kinds):
    columns = sorted(kinds)
    categories = {c: sorted({str(r[c]) for r in rows if r.get(c) not in (None, '')}) for c in columns if kinds[c] == 'categorical'}
    matrix = np.full((len(rows), len(columns)), np.nan)
    for i, row in enumerate(rows):
        for j, c in enumerate(columns):
            v = row.get(c)
            if v in (None, ''):
                continue
            if kinds[c] == 'categorical':
                matrix[i, j] = categories[c].index(str(v))
            else:
                try:
                    number = float(v)
                except (TypeError, ValueError):
                    continue
                matrix[i, j] = number if math.isfinite(number) else np.nan
    return matrix, columns, np.array([kinds[c] == 'categorical' for c in columns])


def core(reference, current, kinds, secret, *, permutations=PERMUTATIONS, test=True, importance=True, seed=0):
    """``reference`` / ``current``: ordered [(entity_hash bytes, features dict)]. Returns the descriptive result."""
    from sklearn.ensemble import HistGradientBoostingClassifier
    if set(kinds) & set(REFUSED_FEATURES):
        raise EvaluationError('Outcome and identifier columns cannot be domain features.', 'domain_feature_refused')
    first = {}
    for arm, rows in ((0, reference), (1, current)):
        for entity, features in rows:
            first.setdefault((arm, entity), features)
    both = {e for (a, e) in first if a == 0} & {e for (a, e) in first if a == 1}
    rows = [(e, a, f) for (a, e), f in first.items() if e not in both]
    rows.sort(key=lambda r: (r[1], r[0]))
    half = np.array([_split(secret, e) for e, _a, _f in rows])
    labels = np.array([a for _e, a, _f in rows])
    matrix, columns, categorical = _encode([f for _e, _a, f in rows], kinds)
    a, b = half == 0, half == 1
    counts = {'reference_entities': int((labels == 0).sum()), 'current_entities': int((labels == 1).sum()),
              'excluded_in_both_arms': len(both), 'half_b': {'reference': int((labels[b] == 0).sum()), 'current': int((labels[b] == 1).sum())}}
    if min((labels[a] == 0).sum(), (labels[a] == 1).sum(), (labels[b] == 0).sum(), (labels[b] == 1).sum()) < MIN_FIT_ENTITIES:
        return {'state': 'insufficient_entities', 'counts': counts, 'minimum_per_arm_and_half': MIN_FIT_ENTITIES}
    model = HistGradientBoostingClassifier(max_iter=100, random_state=seed, early_stopping=False,
                                           categorical_features=categorical if categorical.any() else None)
    model.fit(matrix[a], labels[a])
    scores = model.predict_proba(matrix[b])[:, 1]
    held_out = auc(scores, labels[b])
    edges = np.linspace(0, 1, 11)
    bins = np.clip(np.digitize(scores, edges[1:-1]), 0, 9)
    calibration = [{'bin': int(k), 'mean_probability': float(scores[bins == k].mean()), 'current_rate': float(labels[b][bins == k].mean()),
                    'n': int((bins == k).sum())} for k in range(10) if (bins == k).any()]
    out = {'state': 'completed', 'counts': counts, 'features': columns, 'held_out_auc': held_out, 'auc_interval': None,
           'calibration': calibration, 'standing': 'descriptive',
           'qualifications': ['No confidence interval is claimed for the held-out AUC.',
                              'Permutation importance is association, not cause.',
                              'Reference and current periods differ in time: seasonality is itself a difference.']}
    if importance:
        from sklearn.inspection import permutation_importance
        result = permutation_importance(model, matrix[b], labels[b], scoring='roc_auc', n_repeats=5, random_state=seed)
        out['permutation_importance'] = sorted(({'feature': c, 'mean': float(m), 'std': float(s)}
                                                for c, m, s in zip(columns, result.importances_mean, result.importances_std)),
                                               key=lambda r: -r['mean'])
    if test:
        if min(counts['half_b']['reference'], counts['half_b']['current']) < MIN_TEST_ENTITIES:
            out['exploratory_test'] = {'state': 'refused', 'reason': f'fewer than {MIN_TEST_ENTITIES} entities per arm in half B'}
        else:
            p, observed = permutation_p(scores, labels[b], permutations=permutations, seed=seed)
            out['exploratory_test'] = {'state': 'completed', 'p_value': p, 'statistic': 'held_out_auc', 'observed': observed,
                                       'permutations': permutations, 'standing': 'exploratory single look',
                                       'assumption': 'reference and current entities are exchangeable under H0 (conditional on the fitted classifier)'}
    return out


def _rows(installation, ctx, start, end, purpose_metadata):
    """Ordered (entity hash, declared features) of a period, read under a covariate-only reservation."""
    from ...execution_context import ctx as run_ctx
    from ...history_contracts import instant
    from ..monitoring import context as deployment_context, packets, references, units as unit_rules, windows
    definition = ctx['definition']
    deployment = deployment_context.deployment(installation, ctx['incident']['deployment_id'])
    ws = deployment['workspace']
    k = ws.status()['catalog_sequence']
    spec = references.longitudinal_spec(definition, deployment['namespace'], start, end, k, windows.iso(instant(end)), window_id='domain')
    lease, governance = windows.reserve_window(ws.catalog, namespace=deployment['namespace'], k=k, ticks=(instant(start), instant(end)),
                                               purpose='covariate_inspection', metadata=purpose_metadata)
    try:
        result = run_ctx.run(_evaluate, (str(ws.path), spec, k, spec.as_of, governance), spec.config).data
        packets.publish(installation, lease, deployment['catalog_id'], [], [governance['reservation']['id']], lambda conn: None)
    except BaseException:
        ws.catalog.finish_attempt(lease, failed=True)
        raise
    units = (result['variants'].get(definition['variant']) or {}).get('units', [])
    secret = references.order_secret(installation, ctx['incident']['deployment_id'])
    units.sort(key=lambda u: unit_rules.order_key(secret, u['event_key']))
    return [(unit_rules.entity_hash(deployment['namespace'], u), u.get('features') or {}) for u in units], governance['reservation']['id']


def _evaluate(root, spec, k, as_of, governance, progress=None):
    from ...result import Inspection
    from ..monitoring import windows
    return Inspection(windows.evaluate_window(root, spec, k, as_of, governance, cohort_scopes=False, progress=progress),
                      {'status': 'completed', 'peak_workspace_bytes': 0})


def investigate(installation, ctx, spec):
    from ..monitoring import references, windows
    definition = ctx['definition']
    kinds = {name: ('numeric' if meaning == 'numeric' else 'categorical') for name, meaning in (definition.get('features') or {}).items()}
    if not kinds:
        raise EvaluationError('The domain classifier needs declared context features.', 'template_ineligible')
    start, end = ctx['span']
    reference, ref_use = _rows(installation, ctx, definition['reference']['start'], definition['reference']['end'],
                               {'investigation': spec['request_id'], 'arm': 'reference'})
    current, cur_use = _rows(installation, ctx, windows.iso(start), windows.iso(end),
                             {'investigation': spec['request_id'], 'arm': 'current'})
    secret = references.order_secret(installation, ctx['incident']['deployment_id'])
    result = core(reference, current, kinds, secret)
    result['evidence_uses'] = [ref_use, cur_use]
    observations = {}
    if result['state'] == 'completed':
        value = True if result['held_out_auc'] >= 0.6 else False if result['held_out_auc'] <= 0.55 else None
        if value is not None:
            observations['O-domain-shift'] = {'value': value, 'standing': 'P', 'evidence': {'held_out_auc': result['held_out_auc'],
                                                                                           'exploratory_test': result.get('exploratory_test')}}
    return {'summary': result, 'observations': observations}
