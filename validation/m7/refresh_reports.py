"""Reproject frozen M7 evidence into a fresh report variant; never reanalyze."""
import json
from pathlib import Path
from datatrust import ImageAuditResult,ImageDisclosureOptions

ROOT=Path(__file__).parent


def run():
    for case in ['unlabeled','classification','multilabel','detection','segmentation','comparison','disclosed','model']:
        folder=ROOT/'results/reports'/case
        source=folder/('final.json' if (folder/'final.json').exists() else 'analysis.json')
        data=json.loads(source.read_text()); profile=dict(data['profile'])
        for key in ['examples','disclosure','export_identity']: profile.pop(key,None)
        private=json.loads((folder/'.datatrust-private'/profile['audit_id']/'manifest.json').read_text())
        result=ImageAuditResult(profile,data['checks'],data['evidence'],data['findings'],data['coverage'],data['execution'],data['generated_at'],private)
        disclosure=ImageDisclosureOptions(tuple(data['profile'].get('disclosure',{}).get('references',())),data['profile'].get('disclosure',{}).get('overlays',False),data['profile'].get('disclosure',{}).get('labels',False))
        a=result.generate_artifacts(folder/'readable.pdf',format='pdf',json_path=folder/'readable.json',disclosure=disclosure,allowed_roots=private['roots'])
        print(case,'reprojected',a.pdf_path,flush=True)


if __name__=='__main__': run()
