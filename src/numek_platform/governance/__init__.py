"""Evidence governance: no protected evidence without a prior committed reservation.

Every outcome-bearing read declares a *purpose*. The purpose fixes the legacy
evidence-use class (which keeps ConfidenceGuard's overlap semantics exact) and
how sealed-reserve entities are treated:

``withhold``      reserve units are removed from the reservation (counted)
``refuse``        any reserve unit in the population refuses the reservation
``consume``       reserve units are admitted only with explicit consumption
                  (``reserve:consume``) and become spent at entity level
``covariates``    governed by the reserve's covariate policy (exclude/inspect)

``selection_access`` (class ``access``) authorizes reading a population without
recording outcome exposure. ConfidenceGuard workers use it where v2 read
outcomes without a ledger entry: the governed exposure (if any) is recorded
separately by the caller's own evidence-use record, as in v2.

``reserve_claim`` (class ``confirmation``) is the G.8 study claim: after a
confirmation family is frozen, the sealed-reserve entities eligible for its
assessment role are identified from identities only and reserved and consumed
in one transaction, before any inspection reads them. It allocates no error
budget and is not itself an assessment; the family's own later reservations
may overlap it.
"""
from ..errors import PlatformError

#               purpose:            (legacy class,              reserve mode)
PURPOSES = {
    'monitoring_outcome':          ('outcome_disclosure',       'withhold'),
    'detector':                    ('outcome_disclosure',       'withhold'),
    'reference':                   ('outcome_disclosure',       'withhold'),
    'outcome_disclosure':          ('outcome_disclosure',       'withhold'),
    'export':                      ('outcome_disclosure',       'consume'),
    'fit_F':                       ('discovery_selection',      'refuse'),
    'select_S':                    ('discovery_selection',      'refuse'),
    'calibrate_C':                 ('discovery_selection',      'refuse'),
    'discover_D':                  ('discovery_selection',      'refuse'),
    'select_S4':                   ('discovery_selection',      'refuse'),
    'policy_S':                    ('discovery_selection',      'refuse'),
    'discovery_selection':         ('discovery_selection',      'refuse'),
    'aux_F':                       ('discovery_selection',      'refuse'),
    'aux_S':                       ('discovery_selection',      'refuse'),
    'confirmation':                ('confirmation',             'consume'),
    'assessment':                  ('confirmation',             'consume'),
    'numerical_recomputation':     ('numerical_recomputation',  'consume'),
    'covariate_inspection':        ('covariate_inspection',     'covariates'),
    'selection_access':            ('access',                   'withhold'),
    'reserve_claim':               ('confirmation',             'consume'),
}
CONFIRMATION_CLASSES = ('confirmation', 'numerical_recomputation')
REPLAY_PURPOSES = ('historical_replay', 'outcome_restatement', 'policy_historical_replay', 'policy_outcome_restatement')
SOURCE_ALIAS_POLICY = 'canonical_and_original_source_aliases_v1'
COMPLETE_IDENTITY_SCOPE = 'canonical_history_keys_and_retained_original_aliases'


def purpose_rules(purpose):
    try:
        return PURPOSES[purpose]
    except KeyError:
        raise PlatformError('Unknown evidence-use purpose.', 'invalid_purpose') from None
