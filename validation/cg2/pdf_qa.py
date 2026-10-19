"""Render every page of selected final reports for visual inspection."""
import argparse
import json
from pathlib import Path
import subprocess
from PIL import Image,ImageDraw
from pypdf import PdfReader

def main():
    p=argparse.ArgumentParser();p.add_argument('--reports',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    a.out.mkdir(parents=True,exist_ok=False);records=[]
    for name in ['binary-shareable','multiclass-shareable','regression-local']:
        source=a.reports/(name+'.pdf');dest=a.out/name;dest.mkdir()
        pages=PdfReader(source).pages
        assert all(page.extract_text().strip() for page in pages)
        subprocess.run(['pdftoppm','-png','-scale-to','1000',str(source),str(dest/'page')],check=True)
        images=sorted(dest.glob('page-*.png'),key=lambda x:int(x.stem.split('-')[-1]))
        assert len(images)==len(pages)
        contacts=[]
        for start in range(0,len(images),4):
            sheet=Image.new('RGB',(1460,2080),'#d8dfe3');draw=ImageDraw.Draw(sheet)
            for i,path in enumerate(images[start:start+4]):
                image=Image.open(path).convert('RGB');image.thumbnail((710,1000));x=10+(i%2)*730;y=30+(i//2)*1040
                sheet.paste(image,(x,y));draw.text((x,y-20),f'{name} / page {start+i+1}',fill='black')
            target=dest/f'contact-{start//4+1}.png';sheet.save(target);contacts.append(str(target))
        records.append({'pdf':str(source),'pages':len(pages),'rendered_pages':len(images),'contact_sheets':contacts,'visual_review':'pending'})
    (a.out/'rendered.json').write_text(json.dumps(records,indent=2))
    print(json.dumps(records))

if __name__=='__main__':main()
