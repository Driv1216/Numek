"""Deterministic, validation-only conversions of pinned official source files."""
import csv
import hashlib
import io
import json
import re
import subprocess
import tarfile
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
import pandas as pd

ROOT=Path(__file__).parent
SOURCES={
 'energy':{'archive':'energy.zip','archive_sha256':'499441eee27929a4b00417f58fd8c63c9cc14b8a71520cd0dd27fcb626738351',
           'download_url':'https://archive.ics.uci.edu/static/public/242/energy+efficiency.zip','source_url':'https://archive.ics.uci.edu/dataset/242/energy+efficiency',
           'attribution':'Tsanas, A. and Xifara, A. (2012), Energy Efficiency, UCI Machine Learning Repository. DOI 10.24432/C51307.', 'license':'CC BY 4.0 per UCI dataset page'},
 'scene':{'archive':'scene.rar','archive_sha256':'8dae3b1bb244544ff478dd85980fc92d8e6472b4b68dbc2fc915ceeb4d5f1bcc',
          'download_url':'https://sourceforge.net/projects/mulan/files/datasets/scene.rar/download','source_url':'https://mulan.sourceforge.net/datasets-mlc.html',
          'attribution':'Boutell, Luo, Shen and Brown (2004), Learning multi-label scene classification; dataset distributed by Mulan.',
          'license':'No explicit dataset license found in the distributed ARFF/XML files; availability does not establish an additional license.'},
 'linnerud':{'archive':'scikit-learn-1.7.2.tar.gz','archive_sha256':'363ca6f51164fce2ece13b59370ca4ec670a1b73188e0eb387f6ea99c2e2bf67',
             'download_url':'https://codeload.github.com/scikit-learn/scikit-learn/tar.gz/refs/tags/1.7.2','source_url':'https://scikit-learn.org/stable/modules/generated/sklearn.datasets.load_linnerud.html',
             'attribution':'Linnerud exercise/physiological tables distributed in official scikit-learn 1.7.2 release archive.',
             'license':'scikit-learn BSD-3-Clause; included release COPYING retained as source evidence.'}}


def digest(content):return hashlib.sha256(content).hexdigest()


def prepare():
    output=ROOT/'data/prepared';output.mkdir(parents=True,exist_ok=True);manifest={'sources':{},'datasets':{}}
    def member(name,filename):
        path=ROOT/'data/raw'/SOURCES[name]['archive']
        assert digest(path.read_bytes())==SOURCES[name]['archive_sha256']
        if name=='energy':
            with zipfile.ZipFile(path) as bundle: content=bundle.read(filename)
        elif name=='linnerud':
            with tarfile.open(path) as bundle:content=bundle.extractfile(filename).read()
        else:content=subprocess.check_output(['bsdtar','-xOf',str(path),filename])
        manifest['sources'].setdefault(name,{**SOURCES[name],'members':{}})['members'][filename]=digest(content)
        return content
    def save(name,frame,targets,config):
        path=output/(name+'.csv');text=frame.to_csv(index=False,lineterminator='\n');path.write_text(text)
        manifest['datasets'][name]={'file':str(path.relative_to(ROOT)),'sha256':digest(path.read_bytes()),'rows':len(frame),'columns':len(frame.columns),
                                    'task':{'kind':'multilabel_classification' if name=='scene' else 'regression','targets':targets},'config':config}
    energy=pd.read_excel(io.BytesIO(member('energy','ENB2012_data.xlsx')),engine='openpyxl')
    assert list(energy.columns)==['X1','X2','X3','X4','X5','X6','X7','X8','Y1','Y2'] and energy.shape==(768,10)
    mapping=dict(zip(energy.columns,['relative_compactness','surface_area','wall_area','roof_area','overall_height','orientation','glazing_area','glazing_distribution','heating_load','cooling_load']))
    energy=energy.rename(columns=mapping);manifest['sources']['energy']['column_mapping']=mapping
    save('energy',energy,['heating_load','cooling_load'],{'features':{'semantic_types':{'orientation':'categorical','glazing_distribution':'categorical',**{c:'quantitative' for c in list(energy.columns[:8]) if c not in {'orientation','glazing_distribution'}}}},'regression':{'expectations_by_target':{'heating_load':{'kind':'continuous'},'cooling_load':{'kind':'continuous'}}}})
    raw=member('scene','scene.arff').decode('utf-8');xml=member('scene','scene.xml');labels=[e.attrib['name'] for e in ET.fromstring(xml)]
    attributes=[];records=[];data=False
    for line in raw.splitlines():
        line=line.strip()
        if not line or line.startswith('%'):continue
        if data:
            if line.startswith('{'):raise ValueError('Only this pinned dense ARFF representation is supported.')
            row=next(csv.reader([line]));assert len(row)==len(attributes);records.append([float(v) if v!='?' else float('nan') for v in row])
        elif line.lower().startswith('@attribute'):
            match=re.fullmatch(r'@attribute\s+(\S+)\s+(numeric|\{0,1\})',line,re.I)
            if not match:raise ValueError('Unexpected pinned Scene attribute declaration: '+line)
            attributes.append(match[1].strip("'\""))
        elif line.lower()=='@data':data=True
    scene=pd.DataFrame(records,columns=attributes);assert scene.shape==(2407,300) and len(labels)==6 and set(labels)<=set(attributes)
    for label in labels:scene[label]=scene[label].astype('int64')
    manifest['sources']['scene']['label_roles_from_xml']=labels
    save('scene',scene,labels,{})
    ex=pd.read_csv(io.BytesIO(member('linnerud','scikit-learn-1.7.2/sklearn/datasets/data/linnerud_exercise.csv')),sep=r'\s+')
    ph=pd.read_csv(io.BytesIO(member('linnerud','scikit-learn-1.7.2/sklearn/datasets/data/linnerud_physiological.csv')),sep=r'\s+')
    member('linnerud','scikit-learn-1.7.2/sklearn/datasets/descr/linnerud.rst')
    member('linnerud','scikit-learn-1.7.2/COPYING')
    frame=pd.concat([ex,ph],axis=1);assert frame.shape==(20,6)
    save('linnerud',frame,list(ph.columns),{'features':{'semantic_types':{c:'quantitative' for c in ex.columns}},'regression':{'expectations_by_target':{c:{'kind':'continuous'} for c in ph.columns}}})
    (ROOT/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return manifest

if __name__=='__main__':print(json.dumps(prepare(),indent=2))
