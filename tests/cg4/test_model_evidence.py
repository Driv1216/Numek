import copy
import csv
from dataclasses import replace
import numpy as np
import pytest
from confidenceguard import InvestigationSpec,EvaluationError
from confidenceguard.investigation import arguments,prepared
from .helpers import binary


def test_supplied_model_hash_is_a_typed_declaration_not_publisher_authentication():
    from confidenceguard import DiscoveryRepresentationSpec
    value=DiscoveryRepresentationSpec('retained',kind='retained',model_digest='a'*64)
    assert value.model_digest=='a'*64
    for invalid in ('not-a-hash','A'*64,123):
        with pytest.raises(EvaluationError) as caught:DiscoveryRepresentationSpec('retained',kind='retained',model_digest=invalid)
        assert caught.value.code=='representation_identity'


def test_optional_pinned_encoder_dimensions_cannot_contradict_its_fixed_profile():
    from confidenceguard import DiscoveryRepresentationSpec
    for kind,dimensions in [('e5_text',384),('dinov2_image',768)]:
        valid=DiscoveryRepresentationSpec('encoder',kind=kind,field='context.content',model_directory='/synthetic/model',dimensions=dimensions)
        assert valid.dimensions==dimensions
        with pytest.raises(EvaluationError) as caught:
            DiscoveryRepresentationSpec('encoder',kind=kind,field='context.content',model_directory='/synthetic/model',dimensions=dimensions+1)
        assert caught.value.code=='vector_shape'


def test_model_specific_feature_and_vector_availability_uses_owner_clock(tmp_path):
    original=binary(tmp_path);path=tmp_path/'predictions.csv'
    with path.open() as stream:data=list(csv.DictReader(stream))
    for row in data:row.update(later='2026-01-02T00:00:00Z',earlier='2026-01-01T00:00:00Z',content_at='2026-01-01T12:00:00Z')
    with path.open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=data[0]);writer.writeheader();writer.writerows(data)
    value=original.to_dict();run=value['evaluation']['runs'][0];run['prediction_at']={'column':'later'}
    reference=copy.deepcopy(run);reference.update(id='reference',model={'id':'reference','version':'v1'},prediction_at={'column':'earlier'})
    value['evaluation']['runs'].append(reference)
    view={'id':'late','fields':[{'id':'x','column':'x','kind':'categorical','available_at':{'column':'content_at'}}],'availability':'dated','run':'model','owner':'prediction_revision'}
    other=copy.deepcopy(view);other.update(id='early',run='reference');value['features']=[view,other]
    np.save(tmp_path/'vectors.npy',np.ones((720,2),dtype='<f4'))
    value['representations']=[{'id':'early_vectors','run':'reference','matrix_path':str(tmp_path/'vectors.npy'),'keys_source':{'id':'keys','path':str(path)},'key_columns':['id'],'dimensions':2,'content_available_at':{'column':'content_at'}}]
    spec,config,roots=arguments(InvestigationSpec.from_dict(value),None,None)
    with prepared(spec,config,roots) as p:
        assert all(c['state']=='observed' for c in p.features['late.x'])
        assert all(c['state']=='unavailable' for c in p.features['early.x'])
        assert not p.representations['early_vectors']['available'].any()
        assert set(p.representations['early_vectors']['reason'])=={'content_unavailable_at_cutoff'}
    reference['entity_columns']=['x'];value['evaluation']['runs'][1]=reference
    spec,config,roots=arguments(value,None,None)
    with pytest.raises(EvaluationError) as caught:
        with prepared(spec,config,roots):pass
    assert caught.value.code=='investigation_entity_conflict'
