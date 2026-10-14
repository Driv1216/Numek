"""Render every representative final PDF page; visual review remains explicit."""
import hashlib
import os
import json
from pathlib import Path
import shutil
import subprocess
from PIL import Image,ImageDraw
from pypdf import PdfReader

ROOT=Path(__file__).parent


def run():
    result_root=ROOT/os.environ.get('M7_RESULT_DIR','results'); target=result_root/'pdf_qa'; target.mkdir(exist_ok=True)
    records=[]
    cases=['unlabeled','classification','multilabel','detection','segmentation','comparison','disclosed']
    cases.append('model_release' if (result_root/'reports/model_release').exists() else 'model')
    cases.extend(case for case in ('partial','bounded') if (result_root/'reports'/case).exists())
    for case in cases:
        folder=result_root/'reports'/case; path=folder/('corrected.pdf' if (folder/'corrected.pdf').exists() else 'readable.pdf' if (folder/'readable.pdf').exists() else 'final.pdf' if (folder/'final.pdf').exists() else 'review.pdf')
        reader=PdfReader(path); pages=len(reader.pages)
        assert pages>0
        text='\n'.join(p.extract_text() or '' for p in reader.pages)
        for heading in ['Inventory','Decode and representations','Visual evidence','Annotation integrity','Dataset composition','Duplication candidates','Split and version comparisons','Methods and coverage']: assert heading in text,(case,heading)
        out=target/case; out.mkdir(exist_ok=True)
        subprocess.run([shutil.which('pdftoppm'),'-scale-to','1400','-png',str(path),str(out/'page')],check=True,capture_output=True)
        images=sorted(out.glob('page-*.png'))
        assert len(images)==pages
        for start in range(0,len(images),4):
            sheet=Image.new('RGB',(1000,1450),'#dce5df'); draw=ImageDraw.Draw(sheet)
            for i,imagepath in enumerate(images[start:start+4]):
                image=Image.open(imagepath); image.thumbnail((475,675)); x=12+(i%2)*500; y=28+(i//2)*720
                sheet.paste(image,(x,y)); draw.text((x,y-18),f'{case} {imagepath.stem}',fill='black')
            sheet.save(out/f'contact-{start//4+1}.jpg')
        records.append({'case':case,'pdf':str(path.relative_to(ROOT)),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'pages':pages,'rendered_pages':[str(p.relative_to(ROOT)) for p in images],'visual_review':'pending'})
    (target/'manifest.json').write_text(json.dumps({'records':records,'total_pages':sum(r['pages'] for r in records),'status':'rendered_visual_review_pending'},indent=2)+'\n')
    print([(r['case'],r['pages']) for r in records],flush=True)


if __name__=='__main__': run()
