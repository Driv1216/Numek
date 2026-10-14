"""Small shared M9 identity primitive; no corpus or model dependencies."""
import hashlib
import json


def digest(value):
    from decimal import Decimal
    def scalar(v):
        if isinstance(v,Decimal): return {'decimal_lexeme':str(v)}
        raise TypeError('Unsupported identity value.')
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=True,allow_nan=False,separators=(',',':'),default=scalar).encode()).hexdigest()
