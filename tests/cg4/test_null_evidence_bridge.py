"""Current selection/freezing invariants supporting finite-null evidence reuse."""
import csv
from dataclasses import replace

import numpy as np

from confidenceguard import investigate, freeze_hypotheses, confirm_investigation, inspect_confirmation, ConfirmationSpec
from confidenceguard.feature_contracts import DiscoveryRepresentationSpec
from .helpers import binary


def test_H_labels_cannot_choose_or_revise_the_three_strategy_frozen_family(tmp_path):
    spec=binary(tmp_path, strategies=('structured','catboost','geometric'))
    path=tmp_path/'predictions.csv'
    with path.open() as stream:rows=list(csv.DictReader(stream))
    np.save(tmp_path/'vectors.npy', np.array([[float(r['x']),float(r['z'])] for r in rows],dtype='<f4'))
    spec=replace(spec, representations=(DiscoveryRepresentationSpec(id='geometry',
        matrix_path=str(tmp_path/'vectors.npy'),keys_source=spec.evaluation.sources[0],
        key_columns=('id',),dimensions=2,availability='at_decision'),))
    policy=ConfirmationSpec(upstream_independence='declared_independent',external_exposure='declared_unexposed',
        declaration_author='Synthetic bridge fixture',declaration_reason='Independent synthetic rows; fixed D/S/H assignment; isolated test.')
    original=investigate(spec);frozen=freeze_hypotheses(original,confirmation=policy)
    first=confirm_investigation(frozen)
    family=len(frozen.data['hypotheses'])
    assert family and any(a['state']=='confirmed' for a in first.data['investigation']['assessments'])
    assert all(a['interval']['family_size']==family for a in first.data['investigation']['assessments'] if 'interval' in a)
    for row in rows:
        if row['role']=='H':row['y']=str(1-int(row['y']))
    with path.open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=rows[0]);writer.writeheader();writer.writerows(rows)
    changed=investigate(spec);refrozen=freeze_hypotheses(changed,confirmation=policy)
    assert changed.private['artifacts']==original.private['artifacts']
    assert changed.private['models']==original.private['models']
    assert changed.data['investigation']['shortlist']==original.data['investigation']['shortlist']
    assert refrozen.data['hypotheses']==frozen.data['hypotheses']
    assert refrozen.family_digest==frozen.family_digest
    assert refrozen.data['files']!=frozen.data['files']  # Snapshot, not a new claim.
    preview=inspect_confirmation(refrozen)
    assert 'known_session_exposure' in preview['admissibility_reasons']
    refused=confirm_investigation(refrozen).data['investigation']['assessments']
    assert all(a['state']=='statistically_inadmissible' and not a['H_outcomes_disclosed'] for a in refused)
