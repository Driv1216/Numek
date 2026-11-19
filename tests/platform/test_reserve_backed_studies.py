"""End to end: reserve-backed CG4 confirmation and CG5 policy assessment (G.8 ordering).

Controlled entity registration stands in for S4 ingestion: after a retained
history is ingested, a namespace reserve is created and every entity is
registered with an explicitly chosen state (entities whose id is a multiple of
10 are sealed reserve). The workflows then run unchanged through the public
workspace API.
"""
import json
import threading
from dataclasses import replace

import pytest

from confidenceguard import ConfirmationLook, ConfirmationSpec, EvaluationError, freeze_hypotheses
from confidenceguard.contracts import digest
from confidenceguard.evidence_use import EvidenceUseLedger


def _protocol(study='reserve-backed-study', looks=True):
    return ConfirmationSpec(study_id=study, batch_alpha=.025,
                            restatement_schedule=(ConfirmationLook('april', '2026-04-01T00:00:00Z', .025),) if looks else (),
                            upstream_independence='declared_independent', external_exposure='declared_unexposed',
                            declaration_author='fixture',
                            declaration_reason='Independent synthetic entities, locally protected study, no external study '
                                               'branches or earlier exposure.')


def _id(entity):
    return int(json.loads(entity)[0])          # normalized entity keys are JSON-encoded key tuples


def _register(ws, namespace, chosen):
    """Controlled reserve registration: ``chosen(entity) -> bool`` marks sealed-reserve entities."""
    from numek_platform.governance import reserve as reserves
    from numek_platform.secrets import FileSecretStore
    catalog = ws.catalog
    reserve_id = reserves.create_reserve(catalog.db, FileSecretStore(ws.path.parent / 'reserve-secrets'), catalog.scope,
                                         catalog.catalog_id, namespace, actor='fixture', fraction='0.1')
    opportunities = {f['payload']['entity']: f['key'] for f in catalog.iter_facts('opportunity')}
    k = ws.status()['catalog_sequence']
    with catalog.db.transaction() as conn:
        for entity in opportunities:
            conn.execute('''INSERT INTO entity_registry(org_id, catalog_id, unit_hash, namespace, first_seen_k, reserve_state,
                                                        reserve_id, reserve_version) VALUES (%s, %s, %s, %s, %s, %s, %s, 1)''',
                         (catalog.scope.org_id, catalog.catalog_id, bytes.fromhex(digest([namespace, entity])), namespace, k,
                          'reserve' if chosen(entity) else 'non_reserve', reserve_id))
    return reserve_id, opportunities


def _uses(ws, **match):
    with ws.catalog.db.connect() as conn:
        rows = conn.execute('SELECT * FROM evidence_uses WHERE catalog_id = %s ORDER BY created_at', (ws.catalog.catalog_id,)).fetchall()
    return [r for r in rows if all(r[k] == v for k, v in match.items())]


def _units(ws, column, units):
    with ws.catalog.db.connect() as conn:
        return {bytes(r['unit_hash']).hex(): r[column] for r in conn.execute(
            'SELECT unit_hash, spent_by_use FROM entity_registry WHERE catalog_id = %s AND unit_hash = ANY(%s)',
            (ws.catalog.catalog_id, [bytes.fromhex(u) for u in units]))}


@pytest.fixture
def cg4(platform, monkeypatch, tmp_path):
    from tests.cg4.test_history import retained
    from confidenceguard.investigation import identity_role
    monkeypatch.setenv('NUMEK_PLATFORM_DSN', platform.db.dsn)
    ws, spec = retained(tmp_path.resolve())
    ws.evidence_tracking(True)
    namespace = spec.roles.namespace
    reserve_id, opportunities = _register(ws, namespace, lambda entity: _id(entity) % 10 == 0)
    sealed = {e for e in opportunities if _id(e) % 10 == 0}
    roles = {e: identity_role(spec.roles, e) for e in opportunities}
    return {'ws': ws, 'spec': spec, 'ns': namespace, 'reserve_id': reserve_id, 'opportunities': opportunities,
            'sealed': sealed, 'sealed_H': {e for e in sealed if roles[e] == 'H'}, 'roles': roles}


def _hashes(world, entities):
    ns = world['ns']
    return ({digest([ns, world['opportunities'][e]]) for e in entities}, {digest([ns, e]) for e in entities})


def test_reserve_backed_cg4_confirmation_claims_before_inspection_and_reads_only_its_units(cg4):
    from numek_platform.governance import reserve as reserves
    ws, spec = cg4['ws'], cg4['spec']
    assert cg4['sealed_H'] and cg4['sealed'] - cg4['sealed_H']
    discovery = ws.investigate(spec)
    sealed_events, sealed_units = _hashes(cg4, cg4['sealed'])
    with ws.catalog.db.connect() as conn:                                  # D/S never saw a sealed entity
        touched = conn.execute('''SELECT count(*) AS n FROM exposure_registry WHERE catalog_id = %s AND member_kind = 'unit'
                                  AND hash = ANY(%s) AND (development_use OR outcome_exposed)''',
                               (ws.catalog.catalog_id, [bytes.fromhex(u) for u in sealed_units])).fetchone()['n']
    assert touched == 0
    frozen = freeze_hypotheses(discovery, confirmation=_protocol())
    assert not [u for u in EvidenceUseLedger(ws).records() if u['kind'] == 'reserve_claim']   # freezing claims nothing
    first = ws.confirm_investigation(frozen, request_id='first')
    assert any(a.get('H_outcomes_disclosed') for a in first.data['investigation']['assessments'])

    claims = [u for u in EvidenceUseLedger(ws).records() if u['kind'] == 'reserve_claim']
    h_events, h_units = _hashes(cg4, cg4['sealed_H'])
    assert len(claims) == 1 and claims[0]['unit_count'] == len(cg4['sealed_H'])
    assert claims[0]['family_digest'] == frozen.evidence_family_digest
    confirmation = _uses(ws, kind='confirmation', purpose='confirmation')
    assert len(confirmation) == 1 and confirmation[0]['reserve_consumed_units'] == len(cg4['sealed_H'])
    population = set(first.private['population_event_hashes']['H'])
    assert h_events <= population                                         # authorized population: its H reserve units
    assert not (sealed_events - h_events) & population                    # boundary: no other sealed entity
    spent = _units(ws, 'spent_by_use', sealed_units)
    assert {u for u, by in spent.items() if by} == h_units                # exactly the claim's units are spent
    assert set(spent[u] for u in h_units) == {claims[0]['id']}
    assert reserves.status(ws.catalog.db, ws.catalog.scope, cg4['reserve_id'])['spent'] == len(cg4['sealed_H'])

    # Retry: same request reproduces the result; a new attempt reuses the claim (one claim, no new spending).
    assert ws.confirm_investigation(frozen, request_id='first').to_private_dict() == first.to_private_dict()
    look = ws.restate_confirmation(first.data['analysis_id'], 'april', request_id='april')   # predeclared look
    assert look.private['memberships'] == first.private['memberships']
    assert set(look.private['population_event_hashes']['H']) == population
    assert len([u for u in EvidenceUseLedger(ws).records() if u['kind'] == 'reserve_claim']) == 1
    assert reserves.status(ws.catalog.db, ws.catalog.scope, cg4['reserve_id'])['spent'] == len(cg4['sealed_H'])


def test_unrelated_family_and_ordinary_workflows_never_see_another_studys_reserve_units(cg4):
    from confidenceguard.confirmation import inspect_confirmation
    ws, spec = cg4['ws'], cg4['spec']
    discovery = ws.investigate(spec)
    family = freeze_hypotheses(discovery, confirmation=_protocol())
    first = ws.confirm_investigation(family, request_id='first')
    h_events, _ = _hashes(cg4, cg4['sealed_H'])
    assert h_events <= set(first.private['population_event_hashes']['H'])
    other = freeze_hypotheses(discovery, confirmation=_protocol('another-study', looks=False))
    inspection = inspect_confirmation(other, workspace=ws, _protected=True)
    assert not h_events & set(inspection['_protected_population']['events'])        # A's units stay A's
    assert 'previously_exposed_confirmation_population' in inspection['admissibility_reasons']
    claims = [u for u in EvidenceUseLedger(ws).records() if u['kind'] == 'reserve_claim']
    assert [c['family_digest'] for c in claims] == [family.evidence_family_digest]   # nothing was left for B to claim

    # Ordinary workflow: roles from a data column cannot be decided from identities, so nothing is claimed
    # and sealed entities stay withheld.
    column = replace(spec, roles=replace(spec.roles, column='role'))
    from confidenceguard.confirmation import _reserve_claim
    from confidenceguard.investigation import arguments
    s, _c, roots = arguments(column, None, None)
    assert _reserve_claim(freeze_hypotheses(discovery, confirmation=_protocol('column-study')), s, roots, ws) is None


def test_interrupted_reserve_backed_study_keeps_its_claim_and_retry_resumes_it(cg4):
    from numek_platform.governance import reserve as reserves
    ws = cg4['ws']
    frozen = freeze_hypotheses(ws.investigate(cg4['spec']), confirmation=_protocol())
    cancel = threading.Event()
    cancel.set()
    with pytest.raises(EvaluationError):
        ws.confirm_investigation(frozen, cancel=cancel)                    # stops after the claim, before assessment
    claims = [u for u in EvidenceUseLedger(ws).records() if u['kind'] == 'reserve_claim']
    assert len(claims) == 1                                                # the claim (and its spending) persists
    assert reserves.status(ws.catalog.db, ws.catalog.scope, cg4['reserve_id'])['spent'] == len(cg4['sealed_H'])
    result = ws.confirm_investigation(frozen)                              # the retry resumes the same claim
    h_events, _ = _hashes(cg4, cg4['sealed_H'])
    assert h_events <= set(result.private['population_event_hashes']['H'])
    assert [u['id'] for u in EvidenceUseLedger(ws).records() if u['kind'] == 'reserve_claim'] == [claims[0]['id']]


def test_reserve_backed_cg5_policy_assessment_uses_only_its_claimed_E_units(platform, monkeypatch, tmp_path):
    from tests.cg4.test_history import retained
    from confidenceguard import PolicyAssessmentSpec, PolicyClaim, PolicyInputSpec, PolicyMetricSpec, PolicySpec, PolicyStudySpec
    from confidenceguard.contracts import TaskDefinition
    from confidenceguard.method_contracts import RoleSpec
    from confidenceguard.policy_history import identity_role
    monkeypatch.setenv('NUMEK_PLATFORM_DSN', platform.db.dsn)
    ws, old = retained(tmp_path.resolve())
    ws.evidence_tracking(True)
    ns = old.roles.namespace
    roles = RoleSpec(ns, proportions={'S': .5, 'E': .5}, unit='entity')
    _reserve_id, opportunities = _register(ws, ns, lambda entity: _id(entity) % 10 == 0)
    sealed = {e for e in opportunities if _id(e) % 10 == 0}
    sealed_E = {e for e in sealed if identity_role(roles, e) == 'E'}
    assert sealed_E and sealed - sealed_E
    inp = PolicyInputSpec(roles, history=old.history)
    task = TaskDefinition('binary_classification', 'fixture', ('0', '1'), '1')
    policy = PolicySpec(task, old.objectives[0].run, {'root': {'kind': 'action', 'action': {'kind': 'supplied'}}}, 'root',
                        {'kind': 'abstain'}, {'kind': 'unavailable'})
    metric = PolicyMetricSpec('accuracy', 'issued_accuracy', 'maximize')
    selected = ws.optimize_policies(PolicyStudySpec(inp, (metric,), candidates=(policy,)), {'free_disk_bytes': 1},
                                    request_id='selection')
    protocol = PolicyAssessmentSpec((PolicyClaim('requirement', selected.data['policy']['nomination']['policy_digest'], metric,
                                                 'ge', .1),), sampling='independent_rows', study_id='cg5-reserve-study',
                                    batch_alpha='0.05', upstream_independence='declared_independent',
                                    external_exposure='declared_unexposed', declaration_author='fixture',
                                    declaration_reason='Synthetic isolated event population for reserve assessment.')
    frozen = ws.freeze_policy_family(selected, assessment=protocol)
    result = ws.assess_policies(frozen, {'free_disk_bytes': 1}, request_id='assessment')
    assert result.data['policy']['assessments'][0]['state'] == 'supported'
    claims = [u for u in EvidenceUseLedger(ws).records() if u['kind'] == 'reserve_claim']
    assert len(claims) == 1 and claims[0]['unit_count'] == len(sealed_E)
    assessment = _uses(ws, kind='confirmation', purpose='confirmation')
    assert len(assessment) == 1 and assessment[0]['reserve_consumed_units'] == len(sealed_E)
    sealed_units = {digest([ns, e]) for e in sealed}
    spent = _units(ws, 'spent_by_use', sealed_units)
    assert {u for u, by in spent.items() if by} == {digest([ns, e]) for e in sealed_E}
    with ws.catalog.db.connect() as conn:                                  # selection (S) never saw a sealed entity
        touched = conn.execute('''SELECT count(*) AS n FROM exposure_registry WHERE catalog_id = %s AND member_kind = 'unit'
                                  AND hash = ANY(%s) AND (development_use OR outcome_exposed)''',
                               (ws.catalog.catalog_id, [bytes.fromhex(u) for u in sealed_units])).fetchone()['n']
    assert touched == 0
