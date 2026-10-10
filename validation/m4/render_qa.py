"""Render all selected PDF pages for visual inspection; no page removal."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
from PIL import Image,ImageDraw
from .verify import ROOT,digest


def run(renderer):
    results=ROOT/'results';manifest=json.loads((results/'verification.json').read_text());qa=results/'visual_qa';qa.mkdir(exist_ok=True);records=[]
    for case in manifest['artifacts']:
        folder=qa/case['name'];folder.mkdir(exist_ok=True)
        prefix='page-v'+digest(results/'reports'/case['name']/'report.pdf')[:8]
        subprocess.run([renderer,'-png','-r','105',str(results/'reports'/case['name']/'report.pdf'),str(folder/prefix)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        pages=[folder/f'{prefix}-{i:0{len(str(case["pages"]))}d}.png' for i in range(1,case['pages']+1)]
        sheets=[]
        for start in range(0,len(pages),2):
            imgs=[Image.open(p).convert('RGB') for p in pages[start:start+2]]
            sheet=Image.new('RGB',(sum(i.width for i in imgs),max(i.height for i in imgs)+30),'#e6edf0');draw=ImageDraw.Draw(sheet);x=0
            for p,im in zip(pages[start:start+2],imgs):sheet.paste(im,(x,30));draw.text((x+10,8),case['name']+' '+p.stem,fill='black');x+=im.width
            target=folder/('sheet-'+str(start//2+1)+'.png');sheet.save(target);sheets.append(str(target.relative_to(ROOT)))
        records.append({'case':case['name'],'pdf_sha256':digest(results/'reports'/case['name']/'report.pdf'),'pages':len(pages),'pngs':[{'path':str(p.relative_to(ROOT)),'sha256':digest(p)} for p in pages],'sheets':sheets,'status':'awaiting_visual_inspection'})
    (qa/'manifest.json').write_text(json.dumps(records,indent=2)+'\n');print([(r['case'],r['pages']) for r in records])

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--renderer',default='pdftoppm');run(parser.parse_args().renderer)
