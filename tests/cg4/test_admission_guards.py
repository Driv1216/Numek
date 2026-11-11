"""Boundary references for units, observable leakage and bounded geometry."""
import csv
from dataclasses import replace
from types import SimpleNamespace
import numpy as np
import pytest
from confidenceguard import EvaluationConfig,EvaluationError,FeatureField,FeatureViewSpec,investigate,freeze_hypotheses
from confidenceguard.discovery_regions import graph_neighbors
from confidenceguard.features import outcome_bound_fields
from confidenceguard.investigation_contracts import FailureObjectiveSpec,resolve_objective_units,confirmation_family_digest,ConfirmationSpec,FrozenHypothesisSet
from confidenceguard.investigation_membership import distance_block_rows,distances,distance_cache
from confidenceguard.representations import admit_aligned_matrix
from confidenceguard.contracts import digest
from .helpers import binary


def test_authoritative_units_and_explicit_incompatible_declarations():
    task=SimpleNamespace(units='metres')
    for metric,units in [('bias','metres'),('mse','metres^2'),('interval_coverage','fraction'),('log_loss','nats'),('r2','dimensionless')]:
        assert resolve_objective_units(FailureObjectiveSpec('o',metric,'run'),task).units==units
    with pytest.raises(EvaluationError) as wrong:resolve_objective_units(FailureObjectiveSpec('o','mse','run',units='metres'),task)
    assert wrong.value.code=='objective_units'
    assert resolve_objective_units(FailureObjectiveSpec('o','bias','run',units='kg'),SimpleNamespace(units=None)).units=='kg'
    for metric,direction in [('precision','lower'),('accuracy','lower'),('roc_auc','lower'),('bias','absolute'),('calibration_residual','absolute'),('error_rate','higher')]:
        assert FailureObjectiveSpec('o',metric,'run').direction==direction
    assert FailureObjectiveSpec('o','precision','run',direction='higher').direction=='higher'


def test_alignment_admission_and_adaptive_distance_blocks():
    config=EvaluationConfig(max_rss_bytes=48*1024**2)
    assert admit_aligned_matrix(100,768,'float32',config)==307200
    with pytest.raises(EvaluationError) as large:admit_aligned_matrix(1000000,768,'float32',config)
    assert large.value.code=='representation_memory_admission'
    assert distance_block_rows(512,16384,512*16384*16*3)==3
    with pytest.raises(EvaluationError):distance_block_rows(512,16384,512*16384*16-1)
    rng=np.random.default_rng(42);z=rng.normal(size=(23,17));centers=rng.normal(size=(11,17))
    budget=11*17*16*3*2
    actual=distance_cache(z,centers,'gate',{'_membership_memory_bytes':budget},lambda *args:None)
    assert np.array_equal(actual,distances(z,centers))


def test_duplicate_landmark_graph_excludes_self_and_keeps_stable_ties():
    graph=graph_neighbors(np.zeros((5,5)),2)
    assert [v.tolist() for v in graph]==[[1,2],[0,2],[0,1],[0,1],[0,1]]


def test_observable_label_source_alias_is_not_independent_membership(tmp_path):
    spec=binary(tmp_path)
    label_view=FeatureViewSpec('context',(FeatureField('label','y'),),source='copy',availability='at_decision')
    identities={'data':{'sha256':'a'*64,'bytes':42},'copy':{'sha256':'a'*64,'bytes':42}}
    assert outcome_bound_fields(spec.evaluation,[label_view],identities)=={'context.label'}
    assert outcome_bound_fields(spec.evaluation,[label_view],{})==set()  # absence proves nothing
    path=tmp_path/'predictions.csv'
    with path.open() as stream:rows=list(csv.DictReader(stream))
    for row in rows:row['decision']='0'
    with path.open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=rows[0]);writer.writeheader();writer.writerows(rows)
    spec=replace(spec,features=(replace(label_view,source='data'),),
                 evaluation=replace(spec.evaluation,runs=(replace(spec.evaluation.runs[0],probabilities=None),)))
    result=investigate(spec)
    assert result.private['known_outcome_features']==['context.label']
    with pytest.raises(EvaluationError) as leakage:freeze_hypotheses(result)
    assert leakage.value.code=='outcome_derived_membership'


def test_full_protocol_is_bound_and_legacy_family_bytes_remain_readable(tmp_path):
    result=investigate(binary(tmp_path));frozen=freeze_hypotheses(result)
    protocol=ConfirmationSpec.from_dict(frozen.data['confirmation_spec'])
    assert confirmation_family_digest(frozen.data['hypotheses'],replace(protocol,seed=protocol.seed+1))!=frozen.family_digest
    assert confirmation_family_digest(frozen.data['hypotheses'],replace(protocol,replicates=40000))!=frozen.family_digest
    packet=frozen.to_dict();packet['schema_version']='confidenceguard.frozen_hypothesis_set/1.0'
    packet['family_digest']=confirmation_family_digest(packet['hypotheses'],protocol,packet['schema_version'])
    packet['content_digest']=digest({k:v for k,v in packet.items() if k!='content_digest'})
    legacy=FrozenHypothesisSet(packet)
    assert legacy.to_dict()==packet and legacy.evidence_family_digest==frozen.evidence_family_digest
    old_optional=frozen.to_dict();old_optional['confirmation_spec'].pop('exposure_history_token')
    old_optional['content_digest']=digest({k:v for k,v in old_optional.items() if k!='content_digest'})
    assert FrozenHypothesisSet(old_optional).family_digest==frozen.family_digest
    changed=frozen.to_dict();changed['investigation_spec']['features'][0]['fields'][0]['kind']='integer'
    changed['content_digest']=digest({k:v for k,v in changed.items() if k!='content_digest'})
    with pytest.raises(EvaluationError) as mismatch:FrozenHypothesisSet(changed)
    assert mismatch.value.code=='membership_feature_contract'
