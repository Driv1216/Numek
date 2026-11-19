"""Evidence governance: no protected evidence without a prior committed reservation.

Every outcome-bearing read declares a *purpose*. The purpose fixes the legacy
evidence-use class (which keeps ConfidenceGuard's overlap semantics exact) and
how sealed-reserve entities are treated:

``withhold``      reserve units are removed from the reservation (counted)
``refuse``        any reserve unit in the population refuses the reservation
``consume``       reserve units are admitted only with explicit consumption
                  (``reserve:consume``) and become spent at entity level
``covariates``    governed by the reserve's covariate policy (exclude/inspect)
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
    'aux_F':                       ('discovery_selection',      'refuse'),
    'aux_S':                       ('discovery_selection',      'refuse'),
    'confirmation':                ('confirmation',             'consume'),
    'assessment':                  ('confirmation',             'consume'),
    'numerical_recomputation':     ('numerical_recomputation',  'consume'),
    'covariate_inspection':        ('covariate_inspection',     'covariates'),
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
