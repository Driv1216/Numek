"""Frozen CG4 regions as monitored populations (plan G.2 "Regions", G.8).

A definition may declare regions, each with:
- an ``id``;
- a frozen CG4 membership ``artifact``;
- the region's ``source_standing``: ``H-confirmed`` (a confirmed CG4 hypothesis), ``S-selected`` (selected on
  development data) or ``exploratory``.

**Application.** Monitoring applies **structured** gates, which are data-only predicates over declared features.
- They are applied to each unit's declared context, with CG4's own ``apply``: three states (member, nonmember,
  unavailable), and exact lexical predicates.
- Membership uses covariates only, so restricting a detector to a region is predictable inclusion (R2.4).
- Diagnostic (CatBoost) and geometric gates need retained models or representations. They are refused here, as
  ``region_kind_unsupported_in_monitoring``.

**What regions enable.**
- The ``region_membership`` statistic, an exposure rate that is outcome-free.
- A ``params.region`` restriction on any statistic, for example matured error inside the region.
- Region shares in window packets.
"""
from ...contracts import EvaluationError

SOURCE_STANDINGS = ('H-confirmed', 'S-selected', 'exploratory')


def validate(regions, features):
    from ...investigation_membership import validate as validate_artifact
    out = []
    seen = set()
    for region in regions or ():
        if not isinstance(region, dict) or set(region) - {'id', 'artifact', 'source_standing', 'description'}:
            raise EvaluationError('A region declares id, artifact and source_standing.', 'invalid_definition')
        if not region.get('id') or region['id'] in seen:
            raise EvaluationError('Regions need unique ids.', 'invalid_definition')
        seen.add(region['id'])
        if region.get('source_standing') not in SOURCE_STANDINGS:
            raise EvaluationError('Region source standing is H-confirmed, S-selected or exploratory.', 'invalid_definition')
        artifact = validate_artifact(region['artifact'])
        if artifact['kind'] != 'structured':
            raise EvaluationError('Monitoring applies structured CG4 gates only; diagnostic and geometric gates need their '
                                  'retained models or representations.', 'region_kind_unsupported_in_monitoring')
        missing = set(artifact['features']) - set(features)
        if missing:
            raise EvaluationError(f'Region features must be retained context features: {sorted(missing)}.', 'region_feature_not_retained')
        out.append({**region, 'artifact': artifact})
    return out


def _clauses(artifact):
    p = artifact['parameters']
    return [c for group in (p['any_of'] if 'any_of' in p else [p['clauses']]) for c in group]


def annotate(units, regions):
    """Set ``unit['regions'] = {id: True | False | None}`` (None: unavailable). Returns the units."""
    if not regions or not units:
        return units
    from ...feature_contracts import FeatureField
    from ...features import normalize
    from ...investigation_membership import apply
    for region in regions:
        artifact = region['artifact']
        kinds = {c['field']: c['kind'] for c in _clauses(artifact)}
        features = {name: [normalize(u.get('features', {}).get(name), FeatureField(id=name, column=name, kind=kinds[name]))
                           for u in units] for name in artifact['features']}
        result = apply(artifact, features, {})
        for unit, member, available in zip(units, result['member'], result['available']):
            unit.setdefault('regions', {})[region['id']] = bool(member) if available else None
    return units


def features_of(region):
    return set(region['artifact']['features'])


def shares(units, regions):
    """Descriptive region shares of a window's selected units (members / units with a defined membership)."""
    out = {}
    for region in regions or ():
        states = [u.get('regions', {}).get(region['id']) for u in units]
        defined = [s for s in states if s is not None]
        out[region['id']] = {'members': sum(1 for s in defined if s), 'defined': len(defined), 'unavailable': len(states) - len(defined),
                             'share': (sum(1 for s in defined if s) / len(defined)) if defined else None,
                             'source_standing': region['source_standing']}
    return out
