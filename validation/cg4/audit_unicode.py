"""Exhaustive scalar case/whitespace fingerprints plus pinned normalization probes."""
import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import struct
import sys


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--out',required=True);args=parser.parse_args()
    import unicodedataplus as u
    import regex
    case=hashlib.sha256();spaces=[];mapping={}
    for cp in range(0x110000):
        if 0xd800<=cp<=0xdfff:continue
        char=chr(cp);folded=char.casefold();raw=folded.encode('utf8');case.update(struct.pack('<II',cp,len(raw))+raw)
        if char!=folded:mapping[str(cp)]=folded
        if char.isspace():spaces.append(cp)
    probes=['e\u0301','\u212a','Straße','İıΣςσ','\u1c89\u1c8a','\ua7cb\ua7cc\ua7cd','👩🏽\u200d💻','\u0915\u094d\u0937','a\u0315\u0300','\U0001cc00']
    normalized=[{'input':text,'nfc':u.normalize('NFC',text),'nfd':u.normalize('NFD',text),'graphemes':regex.findall(r'\X',text)} for text in probes]
    data={'python':sys.version,'unicode_package':importlib.metadata.version('unicodedataplus'),'pinned_unicode_version':u.unidata_version,
        'regex':importlib.metadata.version('regex'),'scalar_casefold_sha256':case.hexdigest(),'casefold_nonidentity_map':mapping,'whitespace_codepoints':spaces,'normalization_and_grapheme_probes':normalized}
    path=Path(args.out);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(data,ensure_ascii=True,sort_keys=True,indent=2)+'\n')
    print(json.dumps({'python':sys.version.split()[0],'casefold_sha256':case.hexdigest(),'nonidentity_mappings':len(mapping),'out':str(path)}))


if __name__=='__main__':main()
