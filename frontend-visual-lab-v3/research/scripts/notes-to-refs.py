# Turns research/r4/notes.md into research/round-three/refs.json for the board.
# Each "## id — Name (meta) · STATUS" section becomes one reference with Seen / Take / Leave text,
# its captured frames, and an honest status (live, gallery, partial, inaccessible).
import json, os, re
root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
notes = open(os.path.join(root, 'r4', 'notes.md')).read()
urls = {r['id']: r for f in ('references-r4.json', 'references-r4b.json') for r in json.load(open(os.path.join(root, f)))}
refs = {}
for block in re.split(r'\n## ', notes)[1:]:
    head, *body = block.split('\n')
    m = re.match(r'([\w-]+) — (.+)', head)
    if not m: continue
    rid, title = m.group(1), m.group(2)
    text = '\n'.join(body)
    def part(label):
        mm = re.search(rf'{label}[^:]*:\s*(.+?)(?=\n(?:Seen|Take|Leave)\b|\Z)', text, re.S)
        return mm.group(1).strip().replace('\n', ' ') if mm else ''
    status = 'live'
    if 'INACCESSIBLE' in head: status = 'inaccessible'
    elif 'GALLERY' in head: status = 'gallery'
    elif 'PARTIAL' in head or 'partial' in head or 'FAILED' in head: status = 'partial'
    strength = 'strong' if '★' in head else 'weak' if ('weak' in head or 'not useful' in head or 'generic' in head) else 'useful'
    entry = refs.get(rid, {'id': rid})
    if 're-run' in head and rid in refs:  # a re-run note amends an earlier entry
        entry['rerun'] = (part('Seen') or text.strip().replace('\n', ' '))[:400]
        if status != 'live' and entry.get('status') == 'live' and rid != 'grids03': pass
        if rid == 'grids03': entry.update(status='live', strength='strong', title=title.split(' · ')[0].split(' (')[0], seen=part('Seen'), take=part('Take'), leave=part('Leave'))
        refs[rid] = entry; continue
    name, _, meta = title.partition(' (')
    capdir = os.path.join(root, 'r4', 'captures', rid)
    frames = sorted(f[:-4] for f in os.listdir(capdir) if f.endswith('.jpg')) if os.path.isdir(capdir) else []
    entry.update(title=name.split(' · ')[0].strip(), meta=meta.rstrip(')').split(') ·')[0].rstrip(')') if meta else '',
                 status=status, strength=strength, url=urls.get(rid, {}).get('url', ''), group=urls.get(rid, {}).get('group', ''),
                 seen=part('Seen'), take=part('Take'), leave=part('Leave'), frames=frames,
                 motion=os.path.exists(os.path.join(root, 'r4', 'motion', f'{rid}.mp4')))
    refs[rid] = entry
os.makedirs(os.path.join(root, 'round-three'), exist_ok=True)
json.dump(list(refs.values()), open(os.path.join(root, 'round-three', 'refs.json'), 'w'), indent=1, ensure_ascii=False)
print(len(refs), 'refs;', sum(r['status'] == 'live' for r in refs.values()), 'live;', sum(r.get('strength') == 'strong' for r in refs.values()), 'strong')
