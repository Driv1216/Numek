"""Compose QA contact sheets and encode actual captured browser frames.

Optional artifact helper; Pillow is not required to serve the studies.
Capture inputs are produced with the browser tools, never by this script.
"""
from pathlib import Path
import json
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent / 'evidence'
NAMES = ['The data has a shape', 'No assumptions', 'Under the surface',
         'The analytical view', 'A matter of detail']
font = ImageFont.truetype('/System/Library/Fonts/Helvetica.ttc', 21)
small = ImageFont.truetype('/System/Library/Fonts/Helvetica.ttc', 13)

sheet = Image.new('RGB', (1504, 1960), '#f0f1ec')
draw = ImageDraw.Draw(sheet)
draw.text((22, 20), 'NUMEK / New direction studies', font=font, fill='#223025')
draw.text((1090, 27), 'Browser captures / 1440 × 900', font=small, fill='#586257')
for i, (key, name) in enumerate(zip('abcde', NAMES)):
    y = 74 + i * 372
    draw.text((22, y), f'{i+1:02d}  {name}', font=font, fill='#223025')
    for j, (screen, label) in enumerate(zip(
        ['landing', 'home', 'results'],
        ['Landing / motion composition', 'Application / session example',
         'Analysis / evidence detail'])):
        image = Image.open(ROOT / f'{key}-{screen}.jpg').convert('RGB')
        image.thumbnail((480, 300), Image.Resampling.LANCZOS)
        x = 22 + j * 492
        sheet.paste(image, (x, y + 34))
        draw.text((x, y + 342), label, font=small, fill='#586257')
sheet.save(ROOT / 'comparison.jpg', quality=94)

sheet = Image.new('RGB', (1504, 1572), '#f0f1ec')
draw = ImageDraw.Draw(sheet)
draw.text((22, 20), 'NUMEK / Five new visual studies', font=font, fill='#223025')
draw.text((22, 50), 'Open the studies to see the motion and source interactions.',
          font=small, fill='#586257')
for i, (key, name) in enumerate(zip('abcde', NAMES)):
    x, y = 22 + (i % 2) * 742, 92 + (i // 2) * 488
    image = Image.open(ROOT / f'{key}-landing.jpg').convert('RGB')
    image.thumbnail((720, 450), Image.Resampling.LANCZOS)
    sheet.paste(image, (x, y))
    draw.text((x, y + 459), f'{i+1:02d}  {name}', font=font, fill='#223025')
sheet.save(ROOT / 'landing-overview.jpg', quality=94)

for folder, output in [('motion-source', 'source-transition.gif'),
                       ('motion-layers', 'layers-transition.gif')]:
    timeline = json.loads((ROOT / folder / 'frames.json').read_text())
    images = []
    for entry in timeline:
        image = Image.open(ROOT / folder / entry['file']).convert('RGB')
        image.thumbnail((960, 600), Image.Resampling.LANCZOS)
        images.append(image)
    sample = Image.new('RGB', (images[0].width * 3, images[0].height))
    for x, i in enumerate([0, len(images) // 2, -1]):
        sample.paste(images[i], (x * images[0].width, 0))
    palette = sample.quantize(colors=192)
    images = [image.quantize(palette=palette, dither=Image.Dither.NONE)
              for image in images]
    durations = [max(20, timeline[i+1]['ms'] - entry['ms'])
                 for i, entry in enumerate(timeline[:-1])] + [900]
    durations[0] += 450
    images[0].save(ROOT / output, save_all=True, append_images=images[1:],
                   duration=durations, loop=0, optimize=False, disposal=2)
print('Comparison sheets and actual browser motion captures encoded.')
