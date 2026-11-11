from pathlib import Path
import subprocess,json
from PIL import Image,ImageDraw
root=Path(__file__).resolve().parent/'results'/'reports-final-v2';output=root/'visual';output.mkdir(exist_ok=True)
pages=[]
for path in sorted(root.glob('*/*.pdf')):
    prefix=output/(path.parent.name+'-'+path.stem)
    subprocess.run(['pdftoppm','-r','100','-png',str(path),str(prefix)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    rendered=sorted(output.glob(prefix.name+'-*.png'),key=lambda p:int(p.stem.rsplit('-',1)[1]))
    for i,p in enumerate(rendered,1):pages.append({'pdf':str(path),'page':i,'png':str(p)})
sheets=[]
for offset in range(0,len(pages),4):
    group=pages[offset:offset+4];canvas=Image.new('RGB',(1700,2420),'#cbd5e1');draw=ImageDraw.Draw(canvas)
    for j,entry in enumerate(group):
        im=Image.open(entry['png']).convert('RGB');im.thumbnail((827,1170));x=10+(j%2)*850;y=30+(j//2)*1210
        canvas.paste(im,(x,y));draw.text((x,y-20),entry['pdf'].split('reports-final-v2/')[1]+' - page '+str(entry['page']),fill='black')
    p=output/('sheet-'+str(offset//4+1).zfill(2)+'.png');canvas.save(p);sheets.append({'png':str(p),'pages':group})
(root/'visual-index.json').write_text(json.dumps({'page_count':len(pages),'sheets':sheets,'inspection':'pending'},indent=2)+'\n')
print('Rendered',len(pages),'pages into',len(sheets),'inspection sheets')
