"""Build original, static composition studies for the direction checkpoint.

These are drawings, not implemented application screens. Run from any directory.
Only reads existing evidence; writes within this isolated lab.
"""
import csv
import html
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
OUT = HERE / 'studies'
OUT.mkdir(exist_ok=True)
data = json.loads((REPO / 'validation/regression/reports/bike_hour.json').read_text())
control = json.loads((REPO / 'validation/regression/reports/bike_hour_components_removed.json').read_text())
bins = data['profile']['regression']['target_statistics']['histogram']['bins']
with (REPO / 'validation/regression/data/prepared/bike_hour.csv').open() as f:
    sample = [r for _, r in zip(range(5), csv.DictReader(f))]

def rect(x,y,w,h,c,rx=0,stroke=None):
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{c}"'+(f' stroke="{stroke}"' if stroke else '')+'/>'
def line(x,y,x2,y2,c,w=1):
    return f'<path d="M{x} {y}H{x2}" stroke="{c}" stroke-width="{w}"/>' if y==y2 else f'<path d="M{x} {y}L{x2} {y2}" stroke="{c}" stroke-width="{w}"/>'
def text(x,y,s,size=18,c='#222',family='Arial, sans-serif',weight=400,extra=''):
    return f'<text x="{x}" y="{y}" fill="{c}" font-size="{size}" font-family="{family}" font-weight="{weight}" {extra}>{html.escape(str(s))}</text>'
def lines(x,y,ss,size=18,c='#222',family='Arial, sans-serif',weight=400,leading=None):
    return ''.join(text(x,y+i*(leading or size*1.15),s,size,c,family,weight) for i,s in enumerate(ss))
def hist(x,y,w,h,color,base='#aab1b0',background=False):
    s=text(x,y-13,'Rows / largest bin: 3,377',11,base)
    for i in range(4):
        yy=y+h-i*h/3
        s+=line(x,yy,x+w,yy,base,.5)
    for i,b in enumerate(bins):
        hh=b['count']/3377*h
        s+=rect(round(x+i*w/40,2),round(y+h-hh,2),round(w/40-2,2),round(hh,2),color)
    return s+text(x,y+h+22,'1',12,base)+text(x+w-30,y+h+22,'977',12,base)
def pill(x,y,w,s,bg,fg):
    return rect(x,y,w,34,bg,17)+text(x+15,y+22,s,13,fg)
def write(name,s,bg):
    (OUT/(name+'.svg')).write_text(f'<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720"><title>{html.escape(name)} — static composition study</title>'+rect(0,0,1280,720,bg)+s+'</svg>')

# 1: A report-centered identity. Offset document scale; quiet library; long-form result.
wine='#4b1437'; pink='#f4d6e3'; ink='#261624'; white='#fffdfd'; muted='#7a526b'
s=text(48,58,'NUMEK',27,wine,weight=700)+text(710,55,'DataTrust',15,wine)+text(842,55,'Methodology',15,wine)+pill(1070,28,160,'Explore a report',wine,white)
s+=lines(48,205,['A finding.', 'Its evidence.', 'Your next move.'],73,wine,'Georgia, serif',leading=79)
s+=lines(52,510,['Understand the data behind your AI.', 'DataTrust makes reliability findings inspectable.'],18,muted,leading=27)+pill(50,596,192,'Open DataTrust',wine,white)
s+=rect(701,119,489,566,'#d6b2c4')+rect(673,102,489,566,white)
s+=text(706,143,'DataTrust / Bike Sharing',15,wine)+line(706,162,1127,162,pink)
s+=lines(706,217,['The total is already', 'in the inputs.'],33,ink,'Georgia, serif')
s+=rect(706,286,421,66,pink)+text(724,328,'cnt = casual + registered',23,wine)
s+=hist(707,401,420,124,wine,'#987b8c')+text(707,566,'17,379 finite targets · counts per interval',13,muted)
s+=lines(707,611,['Review availability at prediction time.', 'Observed algebra alone does not prove leakage.'],14,muted,leading=22)
write('01-landing',s,pink)
s=text(44,52,'NUMEK / DataTrust',22,wine,weight=600)+text(790,52,'Reports',15,wine)+text(890,52,'Methods',15,muted)+pill(1060,28,170,'New local analysis',wine,white)
s+=text(48,152,'Your analysis library',49,wine,'Georgia, serif')+text(48,192,'Local session · Representative report collection',16,muted)
for i,(name,kind,note) in enumerate([('Bike Sharing','Regression','4 findings · 17,379 rows'),('Bike Sharing · selected inputs','Regression','1 finding · 17,379 rows'),('Connected evidence example','Cross-representation','Illustrative source review')]):
    y=249+i*122
    s+=line(48,y,1230,y,'#d6bacb')+text(56,y+42,name,25,wine,'Georgia, serif')+text(56,y+77,kind,15,muted)+text(721,y+50,note,17,wine)+text(1120,y+50,'Read',17,wine)
s+=rect(48,641,1182,37,pink)+text(65,665,'Reports explain findings, methods and coverage. Files remain on your machine.',15,wine)
write('01-home',s,white)
s=rect(0,0,1280,63,wine)+text(35,40,'NUMEK / DataTrust',20,white)+text(1040,40,'HTML  /  PDF  /  JSON',14,pink)
s+=lines(42,128,['Bike Sharing','Report outline'],16,muted,leading=40)+text(42,252,'Findings',16,wine,weight=700)+lines(42,299,['Population','Distributions','Methods','Coverage'],15,muted,leading=42)
s+=rect(286,95,682,594,white)+text(326,146,'Regression reliability review',15,muted)+lines(326,214,['The total is already', 'in the inputs.'],44,wine,'Georgia, serif')
s+=text(326,328,'cnt = casual + registered',25,wine)+line(326,348,916,348,pink,9)+hist(326,389,589,135,wine,muted)
s+=lines(326,586,['Verified across 17,379 overlapping rows.', 'Review the declared availability of both inputs.'],18,ink,leading=27)+text(326,661,'No universal regression score is defined.',14,muted)
s+=lines(1005,212,['Evidence note', '17,379 / 17,379 rows', '869 distinct targets'],16,wine,leading=32)+line(985,185,985,395,'#caa4bb')+lines(1005,430,['Interpretation', 'An arithmetic identity', 'does not establish', 'actual model use.'],16,muted,leading=28)
write('01-results',s,'#f8edf3')

# 2: Field-centered workbook. One extended table becomes an analytical inspector.
green='#064b38'; mint='#d4f4dc'; lime='#a5d3ad'; red='#b44835'; fg='#163b2b'
s=text(42,54,'numek',33,green,weight=800)+text(734,51,'DataTrust',16,green)+text(853,51,'How it works',16,green)+pill(1072,27,165,'Open the workspace',green,'white')
s+=lines(40,197,['LOOK', 'CLOSER.'],110,green,'Arial Narrow, Arial, sans-serif',900,104)
s+=lines(43,461,['Reliability starts with the details.', 'Investigate your dataset with DataTrust.'],20,fg,leading=29)
s+=text(46,659,'Local analysis. Explicit methods. Inspectable evidence.',15,green)
s+=rect(493,127,746,499,'#fff',3)+rect(504,165,220,421,mint)
for j,txt in enumerate(['casual','registered','cnt']):
    s+=text(530+j*221,151,txt,18,green,weight=700)
for i,row in enumerate(sample):
    y=200+i*52
    s+=line(509,y+14,1225,y+14,'#cfe1d4')
    for j,key in enumerate(['casual','registered','cnt']): s+=text(530+j*221,y,row[key],21,green)
s+=rect(510,452,709,151,green)+text(531,488,'A relationship worth reviewing',16,mint)+text(531,532,'cnt = casual + registered',28,'white')+text(531,572,'Verified over all 17,379 overlapping rows',15,mint)
write('02-landing',s,mint)
s=rect(0,0,62,720,green)+text(18,43,'n',28,'white',weight=800)
for i,t in enumerate(['⌕','+','▤','≡']): s+=text(20,121+i*61,t,23,'#daf3df')
s+=text(88,42,'DataTrust',20,green,weight=700)+text(298,42,'Bike Sharing',16,green)+pill(1074,18,177,'New local analysis',green,'white')
s+=text(88,111,'Explore your dataset',37,green,weight=700)+text(88,150,'17,379 rows    17 columns    Regression    Local session',15,green)
s+=rect(88,181,1161,43,green)+text(109,209,'Data',16,'white',weight=700)+text(231,209,'Findings 4',16,'#cce8d4')+text(395,209,'Methods & coverage',16,'#cce8d4')
headers=['Row','hr','temp','casual','registered','cnt']
for j,k in enumerate(headers): s+=text(110+j*182,267,k,16,green,weight=700)
for i,row in enumerate(sample):
    y=314+i*59
    s+=rect(89,y-25,1159,54,'#eff9f0' if i%2==0 else '#fff')
    for j,k in enumerate(['instant','hr','temp','casual','registered','cnt']):s+=text(110+j*182,y,row[k],18,fg)
s+=rect(88,621,1161,60,mint)+text(109,658,'Select a column to inspect its distribution and supporting findings.',17,green)
write('02-home',s,'#fff')
s=rect(0,0,62,720,green)+text(18,43,'n',28,'white',weight=800)+text(88,43,'DataTrust / Bike Sharing',20,green)+text(88,109,'Investigate the input set',38,green,weight=700)
s+=rect(88,150,736,50,green)+text(109,181,'Row         casual        registered        cnt',18,'white')
for i,row in enumerate(sample):
    y=244+i*58
    s+=line(88,y+21,823,y+21,'#c7dece')
    for j,k in enumerate(['instant','casual','registered','cnt']):s+=text(110+j*179,y,row[k],23,green)
s+=rect(860,150,376,529,mint)+text(888,194,'Column inspector',18,green,weight=700)+text(888,243,'casual',38,green,weight=700)
s+=lines(888,290,['Declared unavailable', 'at prediction time'],18,red,weight=700,leading=26)+text(888,374,'Finite targets',14,green)+text(888,414,'17,379 / 17,379',28,green)
s+=lines(888,475,['cnt = casual + registered', 'Review timing and derivation.', 'No leakage conclusion follows', 'from this identity alone.'],16,green,leading=28)+text(888,643,'Evidence / relationship.44',13,green)
s+=text(89,638,'Full dataset remains in context while one field opens.',17,green)
write('02-results',s,'#fff')

# 3: Evidence routes. Fixed, meaningful links; source and explanation share a workspace.
night='#182332'; violet='#cbb9fa'; pale='#eef0f7'; slate='#344253'; turquoise='#b9e9d8'
s=text(43,53,'[N] NUMEK',25,violet,weight=600)+text(840,52,'DataTrust',16,'white')+text(975,52,'Methods',16,'white')+pill(1100,27,139,'Inspect a finding',violet,night)
s+=lines(43,173,['Every finding', 'has a source.'],75,'#f9f8ff',weight=500,leading=80)+lines(49,382,['Follow the evidence behind dataset reliability.', 'DataTrust connects observations to explanations.'],19,'#b4bdca',leading=29)
s+=rect(49,490,310,137,slate,10)+text(71,523,'Source / bike_hour.csv',15,turquoise)+text(71,569,'casual + registered',25,'white')+text(71,606,'Declared feature availability',14,'#c6cfda')
s+='<path d="M359 559 C440 559 430 460 509 460" fill="none" stroke="#cbb9fa" stroke-width="2"/>'
s+=rect(509,392,336,169,violet,10)+text(535,431,'Observed relationship',16,night)+text(535,478,'cnt = casual + registered',22,night)+text(535,532,'17,379 matched rows',16,night)
s+='<path d="M845 460 C924 460 916 559 977 559" fill="none" stroke="#cbb9fa" stroke-width="2"/>'
s+=rect(977,490,260,137,slate,10)+text(997,525,'What to investigate',15,turquoise)+lines(997,564,['Availability at', 'prediction time'],24,'white',leading=28)
write('03-landing',s,night)
s=rect(0,0,1280,72,night)+text(28,46,'[N] DataTrust',23,violet)+text(319,44,'Local session',16,'#c4cbd5')+pill(1070,20,180,'New local analysis',violet,night)
s+=rect(0,72,302,648,night)+text(26,125,'Sources',22,'white')
for i,(a,b) in enumerate([('Bike Sharing','CSV · 17,379 rows'),('Selected input control','CSV · 15 columns'),('Document example','Illustrative local source')]):
    y=169+i*110
    s+=rect(17,y,268,88,slate if i==0 else night,7)+text(32,y+32,a,18,'white')+text(32,y+60,b,14,'#b5c2d0')
s+=text(338,132,'Findings in context',35,night,weight=600)+text(338,174,'Bike Sharing / Regression',16,slate)
for i,(a,b) in enumerate([('Input availability','casual, registered'),('Target relationship','cnt = casual + registered'),('Distribution review','casual · IQR candidates'),('Low variation','holiday · 97.12% top share')]):
    y=213+i*105
    s+=rect(327,y,512,89,'#e3dafa' if i==1 else '#fff',7)+text(350,y+33,a,20,night,weight=600)+text(350,y+65,b,15,slate)
s+=rect(871,99,378,590,'white',10)+text(896,143,'Supporting evidence',19,night)+text(896,219,'relationship.44',17,slate)+text(896,284,'17,379',49,night)+text(896,317,'overlapping rows',17,slate)+lines(896,410,['Observed equality is distinct', 'from declared availability.', 'Inspect both before drawing', 'a modeling conclusion.'],17,night,leading=30)
write('03-home',s,pale)
s=rect(0,0,1280,72,night)+text(28,45,'[N] DataTrust / Bike Sharing',22,violet)+text(1044,44,'Local evidence view',16,'#c6cfda')
s+=rect(20,97,283,596,night,8)+text(42,142,'Selected finding',17,'#b5c2d0')+lines(42,194,['Supported target', 'relationship'],25,'white',weight=600,leading=31)+text(42,302,'Review context',16,violet)+lines(42,348,['Names and algebra do', 'not establish actual', 'training-pipeline use.'],17,'#b5c2d0',leading=28)
s+=rect(325,97,573,596,'white',8)+text(353,143,'Exact supporting rows',24,night,weight=600)+rect(353,174,517,44,violet)+text(369,203,'Row       casual     registered     cnt',17,night)
for i,row in enumerate(sample):
    y=264+i*61
    for j,k in enumerate(['instant','casual','registered','cnt']):s+=text(371+j*130,y,row[k],23,night)
    s+=line(353,y+18,869,y+18,'#dde0e9')
s+=text(355,630,'Bounded examples · full support: 17,379 rows',15,slate)
s+=text(932,141,'Interpretation',22,night,weight=600)+lines(932,203,['cnt equals the sum of', 'casual and registered', 'over the verified overlap.'],18,night,leading=29)+lines(932,341,['Declared availability', 'Both inputs unavailable', 'at prediction time.'],17,slate,leading=30)+pill(930,516,306,'Open method and coverage',night,'white')+text(934,623,'No regression score defined.',15,slate)
write('03-results',s,pale)

# 4: Teach the finding through the real distribution; then let the chart become a workspace.
yellow='#f8ec8d'; blue='#203d99'; navy='#1e2850'; paper='#fffcdf'; amber='#d7bd47'
s=text(43,54,'numek',29,navy,weight=700)+text(750,51,'Explore DataTrust',16,navy)+text(940,51,'Our methods',16,navy)+pill(1090,28,146,'Try the example',navy,paper)
s+=text(46,156,'What is your data telling you?',52,navy,weight=600)+text(49,200,'Start with the evidence. Understand what needs investigation.',20,navy)
s+=hist(56,290,842,230,blue,'#8d884c')+text(56,576,'Bike Sharing / cnt',20,navy,weight=600)+text(56,608,'17,379 finite targets · 40 measured bins · bikes per interval',16,navy)
s+=rect(960,266,277,341,navy,22)+text(987,309,'A closer look',18,yellow)+text(987,371,'142',59,paper)+text(987,402,'median target count',16,paper)+lines(987,465,['Shape alone does not', 'establish a data error.', 'Open the finding to', 'inspect its context.'],17,paper,leading=28)
s+=text(52,681,'Understand the population. Inspect the finding. Read the method.',17,navy)
write('04-landing',s,yellow)
s=text(31,48,'numek / DataTrust',22,navy,weight=700)+text(690,47,'Analyses',16,navy)+text(805,47,'Methods',16,navy)+pill(1068,23,180,'New local analysis',navy,paper)
s+=text(38,130,'What needs your attention?',44,navy,weight=600)+text(39,169,'Bike Sharing · Regression · 17,379 rows',16,navy)
labels=['Input availability','Target relationship','Distribution review','Low variation']
for i,label in enumerate(labels):s+=rect(38+i*303,204,289,64,blue if i==1 else '#f0edce',14)+text(55+i*303,243,label,17,paper if i==1 else navy)
s+=hist(65,339,761,216,blue,'#8e936e')+text(65,610,'Distribution of cnt · median 142',19,navy)
s+=text(899,346,'Understand the total',25,navy,weight=600)+lines(899,398,['The target equals two', 'supplied input columns.', 'Inspect their availability', 'before modeling.'],20,navy,leading=31)+pill(897,562,321,'Explore the relationship',navy,paper)
s+=rect(37,653,1209,43,yellow,7)+text(54,680,'Local analysis · Read the evidence and coverage before interpreting findings.',15,navy)
write('04-home',s,paper)
s=text(35,48,'numek / DataTrust',22,navy,weight=700)+text(36,127,'How does the target relate to the inputs?',40,navy,weight=600)
s+=text(39,171,'A guided explanation of one observed relationship',17,navy)
s+=rect(60,264,313,149,blue,20)+text(85,313,'casual',25,paper)+text(85,370,'3',50,paper)
s+=text(400,357,'+',55,navy)+rect(474,264,313,149,'#99b4dc',20)+text(499,313,'registered',25,navy)+text(499,370,'13',50,navy)
s+=text(817,357,'=',55,navy)+rect(894,264,313,149,navy,20)+text(919,313,'cnt',25,yellow)+text(919,370,'16',50,paper)
s+=text(64,456,'Parsed row 1 · First bounded example',16,navy)+text(64,497,'The same identity holds across all 17,379 overlapping rows.',22,navy)
s+=rect(38,544,1208,136,'#fffef0',14)+text(63,581,'What this means',19,navy,weight=700)+text(63,617,'Review availability and derivation. Observed algebra alone does not prove leakage.',18,navy)+text(64,651,'Method: pair sum · Evidence: regression_relationship.44 · No universal regression score',14,navy)
write('04-results',s,yellow)

# 5: Paired space as a brand system. Source facts remain distinct from comparison effects.
electric='#254fdd'; orange='#ed9d5d'; frost='#edf2fc'; black='#142346'
s=text(38,53,'NUMEK',28,black,weight=900)+text(764,51,'DataTrust',16,black)+text(907,51,'Methodology',16,black)+pill(1094,26,147,'Explore analyses',electric,'white')
s+=text(43,151,'Put the evidence',66,black,weight=800)+text(43,226,'side by side.',66,black,weight=800)
s+=rect(39,286,589,347,electric)+rect(648,286,589,347,orange)
s+=text(65,327,'Bike Sharing',21,'white',weight=700)+text(65,362,'All supplied inputs',16,'white')+text(65,443,'17',75,'white',weight=800)+text(180,442,'columns',22,'white')+text(65,500,'cnt = casual + registered',25,'white')+text(65,592,'Observed target relationship',17,'white')
s+=text(674,327,'Bike Sharing',21,black,weight=700)+text(674,362,'Component inputs removed',16,black)+text(674,443,'15',75,black,weight=800)+text(790,442,'columns',22,black)+text(674,500,'No verified target relationship',23,black)+text(674,592,'Within the searched scope',17,black)
s+=text(43,682,'Two existing report fixtures shown. This is not a new comparative analysis result.',15,black)
write('05-landing',s,'#fff')
s=rect(0,0,1280,71,electric)+text(31,46,'NUMEK / DataTrust',23,'white',weight=800)+text(763,45,'Analyses',16,'white')+text(878,45,'Comparisons',16,'white')+text(1080,45,'New local analysis',16,'white')
s+=text(39,150,'A clear view of your analyses.',43,black,weight=700)+text(40,190,'Representative local session · No hosted history implied',16,black)
for i,(a,b,c) in enumerate([('Bike Sharing','17,379 rows / 17 columns','4 findings'),('Bike Sharing · selected inputs','17,379 rows / 15 columns','1 finding'),('Comparison example','Reference / current','Effects and support')]):
    y=237+i*112
    s+=rect(38,y,1203,90,frost if i<2 else '#fff',0)+rect(38,y,8,90,electric if i!=1 else orange)+text(68,y+38,a,24,black,weight=600)+text(68,y+68,b,15,black)+text(877,y+51,c,20,black)
s+=rect(38,617,1203,66,black)+text(64,657,'Comparison selection',18,'white')+text(534,657,'Reference report + current report',17,'white')+text(1090,657,'Open pair',18,'white')
write('05-home',s,'white')
s=rect(0,0,1280,69,electric)+text(28,44,'NUMEK / DataTrust',23,'white',weight=800)+text(949,44,'Fixture comparison study',16,'white')
s+=text(38,127,'The same data. A different input set.',38,black,weight=700)+text(39,166,'Existing report evidence displayed side by side; no new engine output is claimed.',16,black)
s+=rect(37,208,591,425,frost)+rect(651,208,591,425,'#fff0e3')+rect(37,208,591,7,electric)+rect(651,208,591,7,orange)
s+=text(62,255,'All supplied inputs',24,black,weight=700)+text(676,255,'Component inputs removed',24,black,weight=700)
s+=hist(64,300,527,131,electric,'#7b8db6')+hist(677,300,527,131,'#ad642d','#9b7f68')
s+=text(64,492,'Target cnt · same finite population',17,black)+text(677,492,'Target cnt · same finite population',17,black)+text(64,541,'1 verified target relationship',25,black,weight=700)+text(677,541,'0 verified target relationships',25,black,weight=700)
s+=text(64,585,'17,379 overlapping rows',17,black)+text(677,585,'Within the searched methods and scope',17,black)
s+=text(39,685,'Removing components does not establish model readiness. Read each report’s coverage.',16,black)
write('05-results',s,'#fff')

mock={
 'source':'validation/regression/reports/bike_hour.json',
 'control_source':'validation/regression/reports/bike_hour_components_removed.json',
 'note':'Existing engineering fixtures. No fresh analytical run or external validation claimed.',
 'rows':data['profile']['row_count'], 'columns':data['profile']['column_count'],
 'findings':data['findings'], 'scoring':data['scoring'],
 'target_statistics':data['profile']['regression']['target_statistics'],
 'relationship_groups':data['profile']['regression']['relationship_groups'],
 'sample_rows':sample,
 'control':{'rows':control['profile']['row_count'],'columns':control['profile']['column_count'],'findings':len(control['findings']),'relationships':control['profile']['regression']['relationship_groups']}
}
(HERE/'representative-content.json').write_text(json.dumps(mock,indent=2)+'\n')
(HERE/'studies.json').write_text(json.dumps({f.stem:f.read_text() for f in OUT.glob('*.svg')})+'\n')
print('Created 15 static composition studies and a curated evidence fixture.')
