# Builds one contact sheet per captured reference for review (research/sheets/<id>.jpg).
# CAPTURE_SET=r4 reads research/r4/captures and writes research/r4/sheets instead.
import json, os, sys
from PIL import Image, ImageDraw
root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
base = os.path.join(root, os.environ['CAPTURE_SET']) if os.environ.get('CAPTURE_SET') else root
cap = os.path.join(base, 'captures'); out = os.path.join(base, 'sheets'); os.makedirs(out, exist_ok=True)
ids = sys.argv[1:] or sorted(os.listdir(cap))
for i in ids:
    d = os.path.join(cap, i)
    if not os.path.isdir(d): continue
    frames = sorted(f for f in os.listdir(d) if f.endswith('.jpg'))
    if not frames: continue
    tw, th = 480, 300; cols = 4; rows = (len(frames) + cols - 1) // cols
    sheet = Image.new('RGB', (cols * tw, rows * (th + 18)), 'white')
    dr = ImageDraw.Draw(sheet)
    for n, f in enumerate(frames):
        im = Image.open(os.path.join(d, f)).convert('RGB').resize((tw, th))
        x, y = (n % cols) * tw, (n // cols) * (th + 18)
        sheet.paste(im, (x, y + 18)); dr.text((x + 4, y + 3), f, fill='black')
    sheet.save(os.path.join(out, f'{i}.jpg'), quality=80)
print('ok')
