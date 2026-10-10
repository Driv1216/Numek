"""Refresh owned human projections from completed JSON, without reanalysis."""
import json
from pathlib import Path
from types import SimpleNamespace
from datatrust.renderer import write_report_artifacts
from .verify import ROOT,digest


def run():
    manifest_path=ROOT/'results/verification.json';manifest=json.loads(manifest_path.read_text())
    for case in manifest['artifacts']:
        for relative,expected in case['files'].items():
            path=ROOT/relative
            if path.is_symlink() or digest(path)!=expected:raise ValueError('Owned evidence changed: '+relative)
        folder=ROOT/'results/reports'/case['name'];value=json.loads((folder/'analysis.json').read_text())
        result=SimpleNamespace(schema_version='1.3',execution=value['execution'],source_paths=(),to_dict=lambda v=value:v)
        if 'inputs' in value:result.inputs=value['inputs']
        (folder/'report.html').unlink();(folder/'report.pdf').unlink()
        bundle=write_report_artifacts(result,folder/'report.pdf',format='pdf')
        from pypdf import PdfReader
        pages=PdfReader(bundle.pdf_path).pages;case['pages']=len(pages)
        case['executive_pages']=next(i for i,p in enumerate(pages) if '3. Sources and declarations' in p.extract_text())
        assert len(pages)<=(16 if case['name']=='wide' else 12) and case['executive_pages']<=2
        for relative in case['files']:case['files'][relative]=digest(ROOT/relative)
    manifest_path.write_text(json.dumps(manifest,indent=2)+'\n')
    print('Refreshed six owned report projections from completed JSON; no reanalysis.')

if __name__=='__main__':run()
