"""Create additional synthetic-only browser evidence without rewriting prior inputs."""
import csv
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image

ROOT=Path(__file__).resolve().parents[2]


def main():
    parent=ROOT/'validation/cg4/browser_inputs_v2.nosync'
    folder=parent/'representation-workflow-v1'
    if folder.exists():raise RuntimeError('Preserve existing browser evidence; do not regenerate it in place.')
    folder.mkdir()
    with (parent/'predictions.csv').open() as stream:rows=list(csv.DictReader(stream))
    for x in (0,1):
        for z in (0,1):
            pixels=np.full((96,96,3),40,dtype='uint8')
            pixels[:,:,0]=80+140*x;pixels[:,:,2]=80+140*z
            pixels[::8,:,:]=220
            Image.fromarray(pixels).save(folder/f'context-{x}-{z}.png')
    for row in rows:
        x=int(row['x']);z=int(row['z'])
        row['content']=f'CG4_REP_PRIVATE_20261025 Synthetic route {"north" if x else "south"}; sensor {"high" if z else "low"}.'
        row['image']=f'context-{x}-{z}.png'
    source=folder/'predictions.csv'
    with source.open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    vectors=np.array([[float(r['x']),float(r['z'])] for r in rows],dtype='<f4')
    held=[i for i,r in enumerate(rows) if r['role']=='H']
    vectors[held[-3]:held[-3]+1]=1000.
    vectors[held[-2]]=np.nan
    np.save(folder/'supplied.npy',vectors,allow_pickle=False)
    spec=json.loads((parent/'spec.json').read_text())
    spec['evaluation']['sources'][0]['path']=str(source)
    spec['roles']['namespace']='cg4-browser-representation-workflow-v1'
    spec['name']='CG4 browser supplied representation with unavailable H membership'
    spec['features']=[];spec['strategies']=['geometric']
    spec['representations']=[{'id':'geometry','kind':'supplied','matrix_path':str(folder/'supplied.npy'),
        'keys_source':{'id':'vector_keys','path':str(source)},'key_columns':['id'],'dimensions':2,
        'availability':'at_decision','producer':'NUMEK synthetic context coordinates'}]
    (folder/'spec.json').write_text(json.dumps(spec,indent=2)+'\n')
    manifest={'customer_evidence':False,'purpose':'Browser workflow correctness, not recovery qualification.',
        'planned_rows':len(rows),'H_out_of_support_event':rows[held[-3]]['id'],
        'H_invalid_vector_event':rows[held[-2]]['id'],'content_sentinel':'CG4_REP_PRIVATE_20261025',
        'files':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.iterdir() if p.is_file()}}
    (folder/'input-manifest.json').write_text(json.dumps(manifest,sort_keys=True,indent=2)+'\n')
    print(json.dumps({'folder':str(folder),'rows':len(rows),'models_downloaded':False}))


if __name__=='__main__':main()
