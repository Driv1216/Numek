"""Pinned public views and four-image fixture. No runtime dataset loaders."""
import csv,gzip,hashlib,json,struct,tarfile,zlib,zipfile
from pathlib import Path
from datatrust import *

root=Path(__file__).parent;raw=root/'data/raw';out=root/'data/prepared';out.mkdir(parents=True,exist_ok=True)
manifest=json.loads((root/'data/manifest.json').read_text());cases={};prepared={}
for name,info in manifest.items():
    with (raw/name).open('rb') as f:d=hashlib.file_digest(f,'sha256').hexdigest()
    if d!=info['sha256']:raise ValueError('Pinned raw source changed.')


def write(name,rows):
    p=out/(name+'.jsonl');n=0
    with p.open('w') as f:
        for row in rows:f.write(json.dumps(row,ensure_ascii=False,allow_nan=False)+'\n');n+=1
    prepared[name]={'path':str(p),'rows':n,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
    return TextSourceSpec(str(p.resolve()))


def add(name,inputs,transform):
    spec=TextAuditSpec(tuple(inputs),allowed_roots=(str(out.resolve()),))
    config=TextAnalysisConfig(limits=TextWorkLimits(lexical_units=128,signature_work=1000000,shingle_positions=200000,verification_visits=2000000,details=10))
    cases[name]={'spec':spec.to_dict(),'config':config.to_dict(),'transformation':transform,'source_names':[]}

sms=zipfile.ZipFile(raw/'sms').read('SMSSpamCollection').decode('utf8').splitlines();p=out/'sms.csv'
with p.open('w',newline='') as f:
    writer=csv.writer(f);writer.writerow(['id','text','label'])
    for i,line in enumerate(sms):label,text=line.split('\t',1);writer.writerow([str(i),text,label])
prepared['sms']={'path':str(p),'rows':len(sms),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
add('sms',[TextInputSpec('sms',TextSourceSpec(str(p.resolve()),'csv'),(TextFieldSpec('text','text'),),id_selector='id',annotations=(TextAnnotationSpec('text','label',expectation='required'),))],'Original tab-separated label/text converted to quoted CSV; lexical physical ordinal IDs added; no content cleaning.')

for name in ['ud_english','ud_hindi']:
    rows=[]
    for block in (raw/name).read_text().split('\n\n'):
        if not block.strip():continue
        comments={};tokens=[];tags=[];nospace=[]
        for line in block.splitlines():
            if line.startswith('# ') and ' = ' in line:
                k,v=line[2:].split(' = ',1);comments[k]=v
            elif line and not line.startswith('#'):
                vals=line.split('\t')
                if vals[0].isdigit():tokens.append(vals[1]);tags.append(vals[3]);nospace.append('SpaceAfter=No' in vals[9])
        text=comments.get('text')
        origin='original_text_comment'
        if text is None:
            text=''.join(t+('' if ns else ' ') for t,ns in zip(tokens,nospace)).rstrip();origin='reconstructed_surface_from_supplied_words_and_spacing'
        rows.append({'id':comments.get('sent_id',str(len(rows))),'text':text,'tokens':tokens,'tags':tags,'text_origin':origin})
    source=write(name,rows)
    add(name,[TextInputSpec(name,source,(TextFieldSpec('text','text'),),id_selector='id',annotations=(TextAnnotationSpec('text','tags',kind='token',tokens_selector='tokens',expectation='required'),))],'Syntactic integer-ID words and UPOS retained; multiword/empty-node rows excluded explicitly. Original text comment retained where present; otherwise surface reconstructed from supplied SpaceAfter metadata. Alignment failures are retained, not repaired.')

squad=[]
for article in json.loads((raw/'squad').read_text())['data']:
    for paragraph in article['paragraphs']:
        for q in paragraph['qas']:
            squad.append({'id':q['id'],'context':paragraph['context'],'question':q['question'],'answerable':not q['is_impossible'],'answers':[{'start':a['answer_start'],'end':a['answer_start']+len(a['text']),'text':a['text']} for a in q['answers']]})
source=write('squad',squad)
add('squad',[TextInputSpec('qa',source,(TextFieldSpec('context','context',kind='context'),TextFieldSpec('question','question',kind='question')),id_selector='id',task=TextTaskSpec('qa'),annotations=(TextAnnotationSpec('context','answers',kind='qa',expectation='required',answerable_selector='answerable'),))],'Every dev-v2 question retained with repeated supplied context; answer end=start+Python-codepoint text length, and answerability is the explicit inverse of is_impossible. No answer repair.')

if (raw/'oasst').exists():
    conversations=[]
    with gzip.open(raw/'oasst','rt') as f:
        for i,line in enumerate(f):
            if i>=128:break
            tree=json.loads(line);node=tree['prompt'];messages=[]
            while node:
                messages.append({'role':'user' if node['role']=='prompter' else node['role'],'content':node['text'],'id':node['message_id']})
                replies=node.get('replies',[]);node=replies[0] if replies else None
            conversations.append({'id':tree['message_tree_id'],'messages':messages})
    source=write('oasst',conversations)
    add('oasst',[TextInputSpec('conversations',source,id_selector='id',task=TextTaskSpec('conversation'),conversation=TextConversationSpec())],'First 128 supplied trees, first source-ordered root-to-leaf path per tree, prompter mapped explicitly to user. Other branches and user metadata are outside this view, not audited.')

if (raw/'scifact').exists():
    with tarfile.open(raw/'scifact') as archive:
        names=archive.getnames()
        def read(suffix):
            member=next(n for n in names if n.endswith(suffix));data=archive.extractfile(member).read();return [json.loads(x) for x in data.splitlines() if x]
        corpus=read('corpus.jsonl');claims=read('claims_dev.jsonl')[:100]
    docs=[{'id':str(x['doc_id']),'text':'\n'.join(x['abstract'])} for x in corpus]
    queries=[{'id':str(x['id']),'text':x['claim']} for x in claims]
    qrels=[{'query':str(x['id']),'doc':str(doc),'relevance':1} for x in claims for doc in x['evidence']]
    chunks=[]
    for x in docs[:50]:
        pos=0
        for i,sentence in enumerate(x['text'].split('\n')[:2]):chunks.append({'id':x['id']+'-'+str(i),'parent':x['id'],'text':sentence,'start':pos,'end':pos+len(sentence)});pos+=len(sentence)+1
    ds=write('scifact_docs',docs);qs=write('scifact_queries',queries);js=write('scifact_judgments',qrels);cs=write('scifact_chunks',chunks)
    add('scifact',[TextInputSpec('docs',ds,(TextFieldSpec('text','text'),),role='documents',id_selector='id',retrieval=TextRetrievalSpec('document')),TextInputSpec('queries',qs,(TextFieldSpec('text','text',kind='query'),),role='evaluation',id_selector='id',retrieval=TextRetrievalSpec('query')),TextInputSpec('judgments',js,role='judgments',retrieval=TextRetrievalSpec('judgment',query_source='queries',query_selector='query',target_source='docs',target_selector='doc')),TextInputSpec('chunks',cs,(TextFieldSpec('text','text',kind='chunk'),),role='chunks',id_selector='id',retrieval=TextRetrievalSpec('chunk','docs','parent',field='text',parent_field='text',extractive=True))],'All corpus abstracts joined with explicit newline separators; first 100 dev claims; evidence-document bindings declared positive relevance; first two abstract sentences for first 50 documents retained as source-aligned extractive fixture chunks. Numeric IDs explicitly converted to lexical strings.')

assets=out/'pairing';assets.mkdir(exist_ok=True)
def png(color):
    def chunk(kind,value):return struct.pack('>I',len(value))+kind+value+struct.pack('>I',zlib.crc32(kind+value)&0xffffffff)
    return b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',8,8,8,2,0,0,0))+chunk(b'IDAT',zlib.compress((b'\x00'+bytes(color)*8)*8))+chunk(b'IEND',b'')
for i,color in enumerate([(20,90,120),(210,100,40),(70,150,90),(120,70,180)]):(assets/f'{i}.png').write_bytes(png(color))
pairs=[]
for i in range(16):
    image=f'pairing/{i%4}.png';checksum=hashlib.sha256((out/image).read_bytes()).hexdigest()
    if i==14:image='pairing/missing.png'
    if i==15:checksum='0'*64
    pairs.append({'id':str(i),'text':'Authored caption association '+str(i),'image':image,'checksum':checksum,'split':'train' if i<8 else 'evaluation'})
source=write('pairing',pairs)
add('pairing',[TextInputSpec('pairs',source,(TextFieldSpec('caption','text',kind='caption'),),id_selector='id',split_selector='split',assets=(AssetSpec('image','image',checksum_selector='checksum'),))],'Four authored valid 8x8 PNG assets and sixteen associations. Includes multiple captions/reuse across splits, one missing file and one expected-checksum mismatch; no visual correctness claim.')
for case in cases.values():
    for item in case['spec']['inputs']:item['source']['path']=str(Path(item['source']['path']).relative_to(root.resolve()))
    case['spec']['allowed_roots']=['data/prepared']
for value in prepared.values():value['path']=str(Path(value['path']).resolve().relative_to(root.resolve()))
(root/'data/prepared_manifest.json').write_text(json.dumps({'raw':manifest,'prepared':prepared,'cases':cases},indent=2)+'\n')
print(json.dumps({k:v['rows'] for k,v in prepared.items()}))
