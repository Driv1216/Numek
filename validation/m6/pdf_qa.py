"""Render every representative PDF page to review contact sheets."""
import hashlib,json,subprocess,tempfile
from pathlib import Path
from PIL import Image,ImageDraw
from pypdf import PdfReader
ROOT=Path(__file__).parent
POPPLER=Path('/Users/drivyaanshyadav/.cache/codex-runtimes/codex-primary-runtime/dependencies/bin/override/pdftoppm')

def run():
    public=json.loads((ROOT/'results/verification.json').read_text());paths={}
    for name,v in public['new_evidence'].items():
        if 'pdf' in v:paths[name]=ROOT/v['pdf']['path'] if 'path' in v['pdf'] else ROOT/v['artifact_directory']/(name+'.pdf')
    extra=json.loads((ROOT/'results/presentation.json').read_text())
    for name in ['default','excerpt']:paths['controls_'+name]=ROOT/extra[name]['path']
    out=ROOT/'results/pdf_qa';out.mkdir(exist_ok=True);ledger=[]
    with tempfile.TemporaryDirectory(prefix='numek-m6-pdf-') as scratch:
        for name,path in paths.items():
            reader=PdfReader(path);texts=[p.extract_text() or '' for p in reader.pages]
            assert all(len(t)>20 for t in texts)
            target=Path(scratch)/name
            subprocess.run([str(POPPLER),'-r','90','-png',str(path),str(target)],check=True,capture_output=True)
            pages=sorted(Path(scratch).glob(name+'-*.png'),key=lambda p:int(p.stem.rsplit('-',1)[1]))
            assert len(pages)==len(reader.pages)
            contacts=[]
            for start in range(0,len(pages),6):
                sheet=Image.new('RGB',(1200,2595),'#e7ebef');draw=ImageDraw.Draw(sheet)
                for i,page in enumerate(pages[start:start+6]):
                    im=Image.open(page).convert('RGB');im.thumbnail((580,820));x=(i%2)*600+10;y=(i//2)*865+30
                    sheet.paste(im,(x,y));draw.text((x,y-22),f'{name} — page {start+i+1}',fill='#123')
                contact=out/f'{name}-{start//6+1}.jpg';sheet.save(contact,quality=90);contacts.append(str(contact.relative_to(ROOT)))
            ledger.append({'report':str(path.relative_to(ROOT)),'pdf_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'pages':len(pages),'all_pages_have_text':True,'contacts':contacts,'visual_review':'pending'})
    (ROOT/'results/pdf_qa.json').write_text(json.dumps(ledger,indent=2)+'\n');print(json.dumps({x['report']:x['pages'] for x in ledger}))
if __name__=='__main__':run()
