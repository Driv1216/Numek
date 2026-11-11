"""Audit the fixed realistic journeys; never select a favorable newest result."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import zipfile

ROOT=Path(__file__).resolve().parents[2]
RUNS={'bank':'realistic-bank-v2.json','wine':'realistic-wine-v3.json',
    'ag_news':'realistic-ag-news-v4.json','cifar10':'realistic-cifar10-v4.json'}


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(row):
    if row['status']!='completed' or row['T_DSH_overlap'] is not False:
        raise RuntimeError('Failed, invalidated or overlapping realistic workflow.')
    dataset=row['dataset'];profile=row['profile']
    if row['T_count']!=profile[dataset+'_train'] or row['evaluation_count']!=profile[dataset+'_evaluate']:
        raise RuntimeError('Realistic population differs from its declared profile.')
    journeys=row['journeys']
    if [j['kind'] for j in journeys]!=['natural','injected']:raise RuntimeError('Natural and injected evidence must stay distinct.')
    measured=[]
    for journey in journeys:
        populations=journey['population_measurements']
        if sum(populations[role]['planned'] for role in ('D','S','H'))!=row['evaluation_count']:
            raise RuntimeError('Role population no longer covers the admitted evaluation rows.')
        for role in ('D','S','H'):
            effects=populations[role]['selected_native_effects']
            if len(effects)!=journey['selected']:raise RuntimeError('Missing selected-gate native metric evidence.')
            for effect in effects:
                if effect['planned']!=populations[role]['planned'] or effect['available']+effect['unavailable']!=effect['planned']:
                    raise RuntimeError('Native membership availability lost planned support.')
        if any(a['state']!='statistically_inadmissible' or a['strength']!='descriptive' or
            not {'external_exposure_unknown','upstream_independence_unknown'}<=set(a.get('reason','').split(',')) for a in journey['assessments']):
            raise RuntimeError('Unknown public-data provenance must not establish independent confirmation.')
        h=populations['H']
        measured.append({'kind':journey['kind'],'selected_candidates':journey['selected'],'H':h,
            'assessment_states':dict(Counter(a['state'] for a in journey['assessments'])),
            'execution':journey['execution']})
    return measured


def source_references(required):
    """Find actual retained bytes, not reconstructed or inferred old sources."""
    references={}
    for relative,expected in required:
        path=ROOT/relative
        if path.is_file() and sha(path)==expected:references[(relative,expected)]={'kind':'file','path':relative}
    for manifest in sorted((ROOT/'validation/cg4/source-capsules.nosync').glob('*/source-manifest.json')):
        data=json.loads(manifest.read_text())
        for pair in required-references.keys():
            relative,expected=pair;path=manifest.parent/relative
            if data['files'].get(relative)==expected and path.is_file() and sha(path)==expected:
                references[pair]={'kind':'file','path':str(path.relative_to(ROOT))}
    for archive in sorted((ROOT/'validation/cg4/results').rglob('*.zip')):
        if not required-references.keys():break
        with zipfile.ZipFile(archive) as z:
            names=set(z.namelist())
            for pair in required-references.keys():
                relative,expected=pair
                if relative in names and z.getinfo(relative).file_size<=64*1024**2 and hashlib.sha256(z.read(relative)).hexdigest()==expected:
                    references[pair]={'kind':'archive_member','path':str(archive.relative_to(ROOT)),'member':relative}
    return references


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--out',required=True);args=parser.parse_args()
    records=[];required=set()
    for dataset,name in RUNS.items():
        path=ROOT/'validation/cg4/results'/name;row=json.loads(path.read_text())
        if row['dataset']!=dataset:raise RuntimeError('Dataset identity changed.')
        journeys=audit(row);required.update(row['source_sha256'].items())
        harness=next((p for p in (ROOT/'validation/cg4').glob('qualify_realistic*.py') if sha(p)==row['harness_sha256']),None)
        if harness is None:raise RuntimeError('Recorded realistic harness is not retained; resolve provenance before summarizing.')
        harness_relative=str(harness.relative_to(ROOT));required.add((harness_relative,row['harness_sha256']))
        records.append({'dataset':dataset,'path':str(path.relative_to(ROOT)),'sha256':sha(path),
            'source_sha256':row['source_sha256'],'harness_sha256':row['harness_sha256'],'harness_source':harness_relative,
            'T_count':row['T_count'],'evaluation_count':row['evaluation_count'],'acquisition':row['acquisition'],
            'predictor':row['predictor'],'encoder':row['encoder'],'journeys':journeys})
    origins=source_references(required)
    result={'schema_version':'numek.cg4_realistic_workflow_summary/1.0','runs':records,
        'source_references':[{'relative_source':pair[0],'sha256':pair[1],**origin} for pair,origin in sorted(origins.items())],
        'missing_recorded_source':[{'path':p,'sha256':h} for p,h in sorted(required-origins.keys())],
        'scope':'One fixed natural/injected journey per public dataset, with distinct source boundaries, benchmark-only T predictors, exact native H effects and unknown-independence refusals. No natural oracle truth, universal recovery/encoder claim, controlled resource comparison or independent confirmation is established. Dataset contents and model weights are excluded from review redistribution.'}
    result['aggregation_source_sha256']=sha(Path(__file__))
    path=Path(args.out)
    with path.open('x') as stream:json.dump(result,stream,sort_keys=True,indent=2,allow_nan=False);stream.write('\n')
    print(json.dumps({'datasets':list(RUNS),'missing_recorded_source':result['missing_recorded_source'],
        'injected_H_recovery':{r['dataset']:{k:r['journeys'][1]['H'][k] for k in ('precision','recall','IoU','unavailable')} for r in records}}))


if __name__=='__main__':main()
