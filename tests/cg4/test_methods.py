import csv
from dataclasses import replace
import numpy as np
import json
import pytest
from confidenceguard import investigate,DiscoveryRepresentationSpec,SourceSpec,MembershipArtifact
from .helpers import binary


def test_catboost_export_boundary_and_hidden_H_parity(tmp_path):
    spec=binary(tmp_path,strategies=('catboost',));result=investigate(spec)
    assert result.private['models'] and result.data['investigation']['candidates']
    assert all(f['export_membership_parity'] for s in result.data['investigation']['strategies'] for f in s['fits'] if f.get('execution')!='not_run')
    path=tmp_path/'predictions.csv'
    with path.open() as stream:rows=list(csv.DictReader(stream))
    for row in rows:
        if row['role']=='H':row['y']=str(1-int(row['y']))
    with path.open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    other=investigate(spec)
    assert result.private['models']==other.private['models']
    assert result.private['artifacts']==other.private['artifacts']


def test_geometric_and_landmark_frozen_OOS_support(tmp_path):
    spec=binary(tmp_path,strategies=('geometric','landmark'));n=720
    vectors=np.array([[(i//3)%2,(i//6)%2] for i in range(n)],dtype='<f4');np.save(tmp_path/'vectors.npy',vectors)
    (tmp_path/'keys.csv').write_text('id\n'+'\n'.join(map(str,range(n)))+'\n')
    representation=DiscoveryRepresentationSpec('vectors',matrix_path=str(tmp_path/'vectors.npy'),keys_source=SourceSpec('keys',str(tmp_path/'keys.csv')),key_columns=('id',),dimensions=2,availability='at_decision')
    spec=replace(spec,representations=(representation,),limits=replace(spec.limits,landmarks=16,neighbors=4))
    result=investigate(spec);artifacts=result.private['artifacts']
    assert {a['kind'] for a in artifacts.values()}=={'geometric','landmark'}
    status=next(s for s in result.data['investigation']['strategies'] if s['strategy']=='landmark')
    assert status['qualification']=='original_NUMEK_failed_promotion_profile'
    assert status['qualification_evidence']['promoted'] is False
    assert status['representations'][0]['qualification_evidence']==status['qualification_evidence']
    assert result.to_dict()['investigation']['landmark_qualification_evidence']==status['qualification_evidence']
    original=next(a for a in artifacts.values() if a['kind']=='geometric')
    gate=MembershipArtifact(original,result.private['models'])
    output=gate.apply({}, {'vectors':{'vectors':np.array([[0.,0.],[1000.,1000.],[np.nan,0.]]),'available':np.array([True,True,False])}})
    assert output['available'].tolist()==[True,False,False]
    assert not output['member'][1:].any()


def test_frozen_l2_transform_preserves_extreme_finite_directions():
    from confidenceguard.investigation_membership import transform_vectors
    values=np.array([[1e308,1e308],[1e-308,1e-308],[0.,0.],[float('nan'),1.]])
    normalized=transform_vectors(values,{'normalization':'l2','mean':None,'components':None})
    np.testing.assert_allclose(normalized[:2],np.full((2,2),1/np.sqrt(2)),rtol=1e-15)
    assert np.isnan(normalized[2:]).all()


def test_native_diagnostic_admission_rejects_inconsistent_tree_and_feature_references():
    from confidenceguard.contracts import digest,EvaluationError
    from confidenceguard.investigation_membership import validate_model
    model={'features_info':{'float_features':[{'flat_feature_index':0,'feature_index':0,'borders':[.5]}]},
           'oblivious_trees':[{'splits':[{'split_type':'FloatFeature','float_feature_index':0,'border':.5,'split_index':0}],'leaf_values':[0.,1.]}],
           'scale_and_bias':[1,[0]]}
    raw=json.dumps(model);assert validate_model(raw,digest(raw))==raw
    model['oblivious_trees'][0]['splits'][0]['float_feature_index']=1000000
    raw=json.dumps(model)
    with pytest.raises(EvaluationError):validate_model(raw,digest(raw))
    model['oblivious_trees'][0]['splits'][0]['float_feature_index']=0
    model['oblivious_trees'][0]['leaf_values'].append(2.)
    raw=json.dumps(model)
    with pytest.raises(EvaluationError):validate_model(raw,digest(raw))
