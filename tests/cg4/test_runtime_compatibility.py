import hashlib
import struct
import unicodedataplus as u
from datatrust.text_normalization import legacy_casefold,views,graphemes
from confidenceguard import PredictionBatchSpec
from .helpers import binary


def test_accepted_casefold_mapping_matches_every_baseline_unicode_scalar():
    actual=hashlib.sha256()
    for cp in range(0x110000):
        if 0xd800<=cp<=0xdfff:continue
        raw=legacy_casefold(chr(cp)).encode('utf8');actual.update(struct.pack('<II',cp,len(raw))+raw)
    assert actual.hexdigest()=='2aff313f0f232e183e2933c56313dcbad3c0b929f59cb65779ef89b5dee94f56'
    assert views('Straße İ Σς',('raw','casefold'))['casefold']=='strasse i\u0307 σσ'
    assert views('\u1c89\ua7cb\U00010d50',('raw','casefold'))['casefold']=='\u1c89\ua7cb\U00010d50'
    assert u.unidata_version=='16.0.0'
    assert views('e\u0301',('raw','nfc'))['nfc']=='é'
    assert graphemes('👩🏽\u200d💻')==['👩🏽\u200d💻']


def test_legacy_prediction_batch_positional_schema_and_serialization(tmp_path):
    spec=binary(tmp_path)
    batch=PredictionBatchSpec(spec.evaluation,'events','v1',({'run':'model'},),'supplied',False,'ingest','legacy','confidenceguard.prediction_batch_spec/1.0')
    assert batch.to_dict()['schema_version']=='confidenceguard.prediction_batch_spec/1.0'
    assert 'feature_views' not in batch.to_dict() and 'discovery_representations' not in batch.to_dict()
