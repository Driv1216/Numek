"""Versioned priority decision table (plan I.8): evidence standing and impact.

The table is data. Its first matching row sets the priority, and the incident records the table
version, the row and a "why".

Operators may override the priority, with a reason. The override is an event and is notified.
"""
TABLE_VERSION = 'cg7_priority_v2'
TABLE = (
    {'id': 'formal_region_not_confirmed', 'when': {'standing': ('F',), 'region_source': ('S-selected', 'exploratory')},
     'priority': 'P2', 'why': 'Formal alarm scoped to a region that was selected or exploratory, not confirmed: '
                              'S-selected regions alone cannot produce P1.'},
    {'id': 'formal_region_low_exposure', 'when': {'standing': ('F',), 'region_share_below': 0.01}, 'priority': 'P2',
     'why': 'Formal alarm in a region holding under 1% of the monitored traffic.'},
    {'id': 'formal_tier1', 'when': {'standing': ('F',), 'tier': (1,)}, 'priority': 'P1',
     'why': 'Formal sequential alarm on a tier-1 deployment.'},
    {'id': 'formal', 'when': {'standing': ('F',)}, 'priority': 'P2', 'why': 'Formal sequential alarm.'},
    {'id': 'deterministic_critical_tier1', 'when': {'standing': ('D',), 'severity': ('critical',), 'tier': (1,)},
     'priority': 'P1', 'why': 'Critical deterministic violation on a tier-1 deployment.'},
    {'id': 'deterministic_high', 'when': {'standing': ('D',), 'severity': ('critical', 'high')}, 'priority': 'P2',
     'why': 'High-severity deterministic violation (for example a monitoring gap).'},
    {'id': 'practical', 'when': {'standing': ('P', 'D'), 'severity': ('high', 'medium')}, 'priority': 'P3',
     'why': 'Practical effect beyond a declared threshold, or a medium deterministic condition (descriptive).'},
    {'id': 'other', 'when': {}, 'priority': 'P4', 'why': 'Estimated, low-severity or informational evidence.'},
)
RANK = {'P1': 1, 'P2': 2, 'P3': 3, 'P4': 4}
INVARIANTS = ('Estimated (E) evidence alone never produces P1 or P2.',
              'S-selected or exploratory regions alone cannot produce P1.')


def decide(condition, tier, context=None):
    """Priority from evidence standing and impact (``context``: affected units, region share and source standing)."""
    context = context or {}
    for row in TABLE:
        when = row['when']
        if 'standing' in when and condition['standing'] not in when['standing']:
            continue
        if 'region_source' in when and context.get('region_source_standing') not in when['region_source']:
            continue
        if 'region_share_below' in when and not (context.get('region_share') is not None
                                                 and context['region_share'] < when['region_share_below']):
            continue
        if 'severity' in when and condition['severity'] not in when['severity']:
            continue
        if 'tier' in when and tier not in when['tier']:
            continue
        return row['priority'], {'table': TABLE_VERSION, 'rule': row['id'], 'why': row['why'],
                                 'inputs': {'standing': condition['standing'], 'severity': condition['severity'], 'tier': tier},
                                 'impact': context}
    raise AssertionError('the table ends with a catch-all row')


def at_least(priority, threshold):
    return RANK[priority] <= RANK[threshold]
