"""Tensor allocation estimates before model preprocessing materializes a batch."""
import numpy as np
from ..contracts import EvaluationError


def tensor_bytes(adapter,event,prepared):
    p=adapter.spec.preprocessing;kind=p.get('kind','tabular')
    if hasattr(adapter,'parent'):
        return max(tensor_bytes(a,event,prepared) for a in [adapter.parent,*adapter.members])
    if hasattr(adapter,'members'):return max(tensor_bytes(m,event,prepared) for m in adapter.members)
    if kind=='text':return prepared.spec.limits.max_tokens*16
    if kind=='image':
        size=p.get('image_size')
        if size is None:
            from PIL import Image
            path=event['record'].get(adapter.spec.inputs[0].column)
            if path not in prepared.assets:return 0
            with Image.open(prepared.assets[path]) as image:size=(image.width,image.height)
        if len(size)!=2 or any(type(d) is not int or d<1 for d in size) or size[0]*size[1]>prepared.spec.limits.max_image_pixels:raise EvaluationError('Decoded image allocation exceeds admission.','image_limit')
        return size[0]*size[1]*3*4
    if kind=='tensor':
        row=getattr(adapter,'tensor_rows',{}).get(event['event_key'])
        return int(row.nbytes) if row is not None else 0
    width=sum(len(p.get('categories',{}).get(f.id,[]))+1 if f.id in p.get('categories',{}) else 1 for f in adapter.spec.inputs)
    return width*np.dtype(p.get('dtype',getattr(adapter,'device_spec',prepared.spec.device).precision)).itemsize
