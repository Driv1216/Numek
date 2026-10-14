"""Bounded M6 search calibration. Independent all-pairs oracle, no customer tuning."""
import argparse
from collections import Counter
import hashlib
import itertools
import json
from pathlib import Path
import random
import time
import regex
from datatrust.text_search import PROFILES,HASH_VERSION,signature,candidate_pairs


def oracle_shingles(text):
    clusters=[m.group() for m in regex.finditer(r'\X',text)]
    return set(map(''.join,zip(clusters,clusters[1:],clusters[2:],clusters[3:],clusters[4:])))


def fixtures():
    rng=random.Random(617)
    boundary=[]
    for group in range(8):
        prefix=''.join(chr(0x4e00+rng.randrange(2000)) for _ in range(60))
        for variant in range(8):boundary.append(prefix+''.join(chr(0x6000+group*100+variant*8+i) for i in range(7)))
    bases=[
        'A local dataset contains documents, annotations, and references. The curator records source provenance and split membership. ',
        'प्रत्येक दस्तावेज़ का स्रोत और समय स्पष्ट होना चाहिए। पाठ में अलग अलग भाषाएँ और उचित उदाहरण मौजूद हैं। ',
        'Le corpus conserve les documents et leurs annotations originales. Les références indiquent la provenance des passages. ',
        'def inspect_source(path): return {"integrity": True, "records": list(read_records(path))} # retain original evidence\n',
    ]
    natural=[]
    for group in range(8):
        body=(bases[group%len(bases)]+''.join(rng.choice('abcdefghijklmnopqrstuvwxyz ') for _ in range(150)))*3
        for variant in range(8):natural.append(body+f' sample {group} version {variant} '+''.join(rng.choice('abcdefghijklmnopqrstuvwxyz') for _ in range(20)))
    long=[]
    for group in range(8):
        prefix=''.join(chr(0x4e00+rng.randrange(2000)) for _ in range(1156))
        for variant in range(8):long.append(prefix+''.join(chr(0x6500+rng.randrange(2000)) for _ in range(144)))
    template=[]
    for group in range(8):
        base='Header: source provenance. '+''.join(rng.choice('abcdefghi ') for _ in range(850))+'\n'
        for variant in range(8):template.append(base*6+f'account={group} value={variant} unique='+''.join(rng.choice('jklmnopqrst ') for _ in range(70)))
    return {'boundary_080':boundary,'natural_multilingual_code':natural,'long_eligible':long,'templated_content':template}


def calibrate():
    cases=fixtures();oracles={};signatures={};started=time.monotonic();records=[]
    for name,texts in cases.items():
        sets=[oracle_shingles(t) for t in texts]
        pairs=list(itertools.combinations(range(len(texts)),2))
        scores={p:len(sets[p[0]]&sets[p[1]])/len(sets[p[0]]|sets[p[1]]) for p in pairs}
        positives={p for p,s in scores.items() if s>=.8}
        if len(positives)<200:raise AssertionError(f'Insufficient positive support for {name}: {len(positives)}')
        if name=='boundary_080' and any(abs(scores[p]-.8)>1e-12 for p in positives):raise AssertionError('Boundary fixture must contain exact 0.80 pairs.')
        oracles[name]=(sets,pairs,scores,positives)
    for b,r in PROFILES:
        for name,texts in cases.items():signatures[b,r,name]=[signature(s,b,r,0) for s in oracles[name][0]]
        for cap in (1024,4096,16384):
            scopes=[];verification_work=0;signature_work=0
            for name,texts in cases.items():
                sets,pairs,scores,positives=oracles[name]
                uncapped,_=candidate_pairs(signatures[b,r,name],b,r,10**9,250000)
                selected,stats=candidate_pairs(signatures[b,r,name],b,r,cap,250000)
                hits=len(set(selected)&positives);recall=hits/len(positives)
                work=sum(len(sets[i])+len(sets[j]) for i,j in selected);verification_work+=work
                hash_work=sum(len(s)*b*r for s in sets);signature_work+=hash_work
                scopes.append({'fixture':name,'units':len(texts),'oracle_pairs':len(pairs),'oracle_positive_pairs':len(positives),'uncapped_candidate_recall':len(set(uncapped)&positives)/len(positives),'budgeted_recall':recall,'subthreshold_candidates':sum(scores[p]<.8 for p in selected),'verification_visits':work,'signature_work':hash_work,**stats})
            probability=1-(1-.8**r)**b
            records.append({'bands':b,'rows':r,'bucket_cap':cap,'ideal_p080':probability,'eligible':probability>=.99 and all(s['budgeted_recall']>=.99 and s['verification_visits']<=100000000 for s in scopes),'verification_work':verification_work,'signature_work':signature_work,'scopes':scopes})
    admissible=[r for r in records if r['eligible']]
    if not admissible:raise AssertionError('No shipping profile met fixed calibration criteria.')
    winner=min(admissible,key=lambda x:(x['verification_work'],x['signature_work'],x['bands'],x['rows'],x['bucket_cap']))
    b,r,cap=winner['bands'],winner['rows'],winner['bucket_cap']
    # Forced saturation: known high-overlap template family; oracle support is independent.
    saturated=[''.join(chr(0x4e00+j) for j in range(500))+str(i).zfill(8) for i in range(256)]
    sets=[oracle_shingles(t) for t in saturated];positive={p for p in itertools.combinations(range(256),2) if len(sets[p[0]]&sets[p[1]])/len(sets[p[0]]|sets[p[1]])>=.8}
    candidates,stats=candidate_pairs([signature(s,b,r,0) for s in sets],b,r,cap,1000)
    saturation={'oracle_positive_pairs':len(positive),'examined_candidates':len(candidates),'observed_recall':len(set(candidates)&positive)/len(positive),**stats}
    profile={k:winner[k] for k in ('bands','rows','bucket_cap')}
    profile.update(hash_version=HASH_VERSION,seed=0,threshold=.8,shingle_graphemes=5,calibration_fixture_hashes={k:hashlib.sha256(json.dumps(v,ensure_ascii=True).encode()).hexdigest() for k,v in cases.items()},calibration_claim='At least 99% observed recall in these ordinary fixtures only; production recall is unknown.',calibration_digest=hashlib.sha256(json.dumps(records,sort_keys=True).encode()).hexdigest())
    return profile,{'profile':profile,'grid':records,'saturation':saturation,'elapsed_seconds':time.monotonic()-started,'oracle':'independent_grapheme_zip_sets_all_pairs','runtime_seed':0}

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--publish-profile',action='store_true');args=parser.parse_args()
    profile,evidence=calibrate();root=Path(__file__).parent;out=root/'results';out.mkdir(exist_ok=True)
    (out/'calibration.json').write_text(json.dumps(evidence,indent=2))
    if args.publish_profile:(root.parents[1]/'src/datatrust/text_search_profile.json').write_text(json.dumps(profile,indent=2)+'\n')
    print(json.dumps({'selected':profile,'saturation':evidence['saturation'],'seconds':evidence['elapsed_seconds']}))
