"""Read-only final report/privacy audit; render pages separately for visual QA."""
import argparse,hashlib,json
from pathlib import Path
from pypdf import PdfReader

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,required=True);parser.add_argument('--out',type=Path,required=True);args=parser.parse_args();rows=[]
    for pdf in sorted(args.root.glob('*/*.pdf')):
        pages=PdfReader(pdf).pages;texts=[p.extract_text() for p in pages];text='\n'.join(texts);pdf.with_suffix('.pdf.txt').write_text(text)
        row={'file':str(pdf),'sha256':hashlib.sha256(pdf.read_bytes()).hexdigest(),'pages':len(pages),'nonempty_pages':all(t.strip() for t in texts),'decision_record_on_first_page':'Decision record' in texts[0]}
        assert row['nonempty_pages'] and row['decision_record_on_first_page']
        if pdf.stem=='shareable':
            local=json.loads((pdf.parent/'local.json').read_text());private_digests=list(local['policy'].get('behavior',{}))
            for extension in ('json','html','pdf.txt'):
                value=pdf.with_suffix('.'+extension).read_text()
                for marker in ('/Users/','"p_a"','"positive_column"','cg5-history-measure','"decision_costs"','"evaluation_costs"',*private_digests):assert marker not in value,(pdf,extension,marker)
                if pdf.parent.name=='regression':assert 'quantity_cost' not in value and 'pinball' not in value
            row['portable_text_scan']='passed'
        rows.append(row)
    assert len(rows)==6
    args.out.write_text(json.dumps({'reports':rows,'privacy_scope':'Shareable JSON, HTML and extracted PDF text; private paths, definitions, executable digests and declared economic names absent. Explicit local exports own protected bundles. Separate tests check that shareable-only export creates no bundle.'},indent=2)+'\n');print(json.dumps({'reports':len(rows),'passed':True}))
if __name__=='__main__':main()
