"""Small pinned-encoder execution/parity panel, separate from recovery qualification."""
import argparse
from datetime import datetime,timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path
import tempfile
import time
import numpy as np
from confidenceguard import EvaluationConfig,DiscoveryRepresentationSpec,FeatureField,InvestigationLimits
from confidenceguard import compat
from confidenceguard.features import normalize
from confidenceguard.result import Inspection

ROOT=Path(__file__).resolve().parents[2]


def worker(kind,directory,model,profile,*,progress=None):
    from confidenceguard.representations import encode
    config=EvaluationConfig();work=compat.workspace(config,1024**3,progress)
    try:
        field=FeatureField('content','content','asset' if kind=='dinov2_image' else 'text')
        if kind=='dinov2_image':content=[str(Path(directory)/name) for name in ('flat.png','gradient.png')]+[None]
        else:content=['A synthetic report describes a delayed shipment.','एक परीक्षण दस्तावेज़। A synthetic report. '*1000,None]
        features={'context.content':[normalize(text,field) for text in content]};keys=['short','long_or_gradient','missing']
        spec=DiscoveryRepresentationSpec('encoder',kind=kind,field='context.content',model_directory=model,runtime_profile=profile,max_windows_per_event=2)
        rep,files=encode(spec,keys,features,work,config,InvestigationLimits(),(str(ROOT),directory),directory)
        return Inspection({'kind':kind,'profile':profile,'vectors':[vector.tolist() if available else None for vector,available in zip(rep['vectors'],rep['available'])],
            'available':rep['available'].tolist(),'reason':rep['reason'],'coverage':rep['coverage'],'provenance':rep['provenance'],
            'matrix_sha256':hashlib.sha256(rep['vectors'].tobytes()).hexdigest(),'input_files':files},
            {'status':'completed','peak_workspace_bytes':work.peak})
    finally:work.close()


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--profile',default='encoders_cpu_v1');parser.add_argument('--out',required=True);args=parser.parse_args()
    started=time.monotonic();results=[]
    with tempfile.TemporaryDirectory(prefix='numek-cg4-encoders-',dir='/private/tmp') as temporary:
        from PIL import Image
        Image.fromarray(np.full((96,96,3),127,dtype='uint8')).save(Path(temporary)/'flat.png')
        xy=np.indices((96,96));pixels=np.stack((xy[0]*2,xy[1]*2,(xy[0]+xy[1])%255),axis=-1).astype('uint8')
        Image.fromarray(pixels).save(Path(temporary)/'gradient.png')
        for kind,relative in [('e5_text','validation/m6/models/multilingual-e5-small'),('dinov2_image','validation/m7/models/dinov2-base')]:
            result=compat.supervise(worker,(kind,temporary,str(ROOT/relative),args.profile),EvaluationConfig())
            results.append({'data':result.data,'execution':result.execution})
    data={'schema_version':'numek.cg4_encoder_execution/1.0','generated_at':datetime.now(timezone.utc).isoformat(),
        'python':__import__('sys').version,'results':results,'seconds':time.monotonic()-started,
        'qualification_scope':'Publisher/runtime admission, bounded execution and synthetic vectors. Does not establish discovery recovery, realistic-dataset performance or encoder fidelity across untested platforms.'}
    path=Path(args.out);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x') as stream:json.dump(data,stream,sort_keys=True,indent=2,allow_nan=False);stream.write('\n')
    print(json.dumps({'python':data['python'],'seconds':data['seconds'],'outputs':[{'kind':r['data']['kind'],'available':r['data']['available'],'matrix_sha256':r['data']['matrix_sha256']} for r in results]}))


if __name__=='__main__':main()
