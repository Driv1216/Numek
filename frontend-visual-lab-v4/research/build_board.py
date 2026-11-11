from pathlib import Path
import json, html
P=Path(__file__).parent
root=P.parents[1]
base=json.loads((root/'validation/regression/reports/bike_hour.json').read_text())
control=json.loads((root/'validation/regression/reports/bike_hour_components_removed.json').read_text())
r=base['profile']['regression']
(P/'content-evidence.json').write_text(json.dumps({'source':'validation/regression/reports/bike_hour.json','comparison_source':'validation/regression/reports/bike_hour_components_removed.json','status':'Existing internal validation examples; no new analytical run','dataset':base['dataset'],'profile':{k:base['profile'][k] for k in ['row_count','column_count','feature_count']},'scoring':base['scoring'],'findings':base['findings'],'relationship':r['relationships'][0],'histogram':r['target_statistics']['histogram'],'comparison':{'columns':control['profile']['column_count'],'finding_codes':[x['code'] for x in control['findings']],'scope':'Two separately saved regression runs. Not a newly executed M4 comparison; removal does not prove overall reliability.'}},indent=2))

def rect(x,y,w,h,c,rad=0,stroke=None):
 return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rad}" fill="{c}"'+(f' stroke="{stroke}"' if stroke else '')+'/>'
def text(x,y,s,size=16,c='#17213A',font='Manrope',weight=400):
 return f'<text x="{x}" y="{y}" font-family="{font}, sans-serif" font-size="{size}" font-weight="{weight}" fill="{c}">{html.escape(s)}</text>'
def lines(x,y,ss,size=16,c='#17213A',font='Manrope',weight=400,leading=None):
 return ''.join(text(x,y+i*(leading or size*1.14),s,size,c,font,weight) for i,s in enumerate(ss))
def line(x1,y1,x2,y2,c,width=1):return f'<path d="M{x1},{y1} L{x2},{y2}" fill="none" stroke="{c}" stroke-width="{width}"/>'
def path(d,c,w=1): return f'<path d="{d}" fill="none" stroke="{c}" stroke-width="{w}"/>'
def tag(x,y,s,c,bg,w=100):return rect(x,y,w,24,bg,12)+text(x+10,y+16,s,10,c)
def hist(x,y,w,h,color,bg):
 bins=r['target_statistics']['histogram']['bins']; peak=max(b['count'] for b in bins)
 s=rect(x,y,w,h,bg)
 for i,b in enumerate(bins):
  v=b['count']/peak*(h-22);s+=rect(x+i*w/len(bins),y+h-18-v,w/len(bins)*.78,v,color)
 s+=line(x,y+h-18,x+w,y+h-18,color)+text(x,y+h,'1',9,color)+text(x+w-95,y+h,'977 rentals / hour',9,color)
 return s

def svg(body,title):return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 690" role="img" aria-label="{html.escape(title)}">'+body+'</svg>'

def a():
 c='#2345E8'; ink='#171D39'; s=rect(0,0,650,690,'#F5F6FF')+rect(0,0,650,76,'#FFFFFF')
 s+=text(32,48,'NUMEK',25,ink,weight=700)+text(382,45,'DataTrust',13)+text(501,45,'Methodology',13)
 s+=lines(32,143,['Know what’s','inside your data.'],53,ink,weight=500,leading=57)
 s+=lines(34,248,['Reliability findings you can inspect.','Analysis that stays on your machine.'],16)
 s+=rect(34,298,177,42,c,21)+text(57,325,'Explore DataTrust',13,'white',weight=600)
 # three material sheets composed from actual evidence
 s+=rect(137,380,470,255,'#DDE1FF',10)+rect(90,407,470,255,'#BEC7F8',10)+rect(34,433,470,237,'white',10, '#D3D8ED')
 s+=text(58,468,'Bike Hour',19,ink,weight=700)+text(58,493,'17,379 rows / Regression',11,'#62677D')
 s+=tag(320,451,'Review needed','#922E32','#FFE6E1',150)
 s+=text(58,535,'cnt = casual + registered',22,c,weight=600)
 s+=line(59,558,472,558,'#E6E8F2')+lines(58,583,['The relationship is verified across 17,379 rows.','Both features are declared unavailable at prediction.'],12,ink,leading=21)
 s+=text(58,645,'Inspect the evidence',12,c,weight=600)
 # app: quiet split workspace with contextual preview
 s+=rect(666,0,534,320,'#FFFFFF')+rect(666,0,534,44,ink)+text(683,29,'NUMEK / DataTrust',13,'white',weight=600)+text(1072,28,'Local session',10,'#DDE1FF')
 s+=text(689,77,'Your analysis workspace',23,ink,weight=600)+text(689,101,'Open a local dataset or explore an example.',11,'#62677D')
 s+=rect(689,125,269,171,'#F3F5FF',7)+text(706,151,'Example datasets',12,ink,weight=700)
 for i,(n,k) in enumerate([('Bike Hour','Regression'),('Adult','Classification'),('Source reconciliation','Documents')]):
  y=181+i*41;s+=text(706,y,n,13,ink,weight=600)+text(706,y+15,k,10,'#62677D')
 s+=rect(973,125,207,171,c,7)+text(990,152,'Bike Hour',18,'white',weight=600)+hist(990,173,172,85,'#C7D0FF',c)+text(990,284,'Open example',12,'white')
 # results
 s+=rect(666,336,534,354,'#FFFFFF')+text(688,365,'Bike Hour / Findings',12,c,weight=600)+tag(1062,346,'Regression',ink,'#EDF0FF',117)
 s+=lines(688,401,['A target relationship','needs investigation.'],23,ink,weight=600)
 s+=rect(688,449,491,62,'#F2F4FF',8)+text(706,486,'cnt = casual + registered',23,c,weight=600)
 s+=text(688,540,'17,379 / 17,379 rows',20,ink,weight=600)+text(688,561,'Verified overlap · feature timing is user-declared',10,'#62677D')
 s+=line(688,577,1178,577,'#DBDFEF')+lines(688,599,['Observed algebra alone does not establish leakage.','Review feature derivation and intended prediction time.'],12,ink,leading=20)
 s+=text(688,663,'Evidence',12,c,weight=700)+text(796,663,'Method',12)+text(889,663,'Coverage',12)+text(1056,663,'No overall score',10,'#62677D')
 return svg(s,'Direction A: expanding evidence sheets, a split workspace and inline investigation')

def b():
 burg='#61233B'; rose='#F4DCE3'; white='#FFFDFC'; s=rect(0,0,650,690,burg)
 s+=text(29,42,'numek',30,white,'Newsreader')+text(32,96,'DataTrust',13,rose,'DM Sans')
 s+=lines(32,140,['Dataset','reliability,','made','readable.'],15,rose,'DM Sans',leading=23)
 s+=rect(175,29,447,503,'#DAB5C2')+rect(157,47,447,503,white)
 s+=text(183,82,'DataTrust / Example report',11,burg,'DM Sans',600)+text(183,139,'Bike Hour',39,burg,'Newsreader')
 s+=text(183,171,'Regression reliability review',13,burg,'DM Sans')+line(183,195,578,195,'#D9B5C2')
 s+=lines(183,239,['Two features tell the','same story as the target.'],28,burg,'Newsreader',leading=32)
 s+=text(183,329,'cnt = casual + registered',19,burg,'DM Sans',600)
 s+=lines(183,362,['The identity holds across 17,379 observations.','Both inputs are declared unavailable at prediction.','Review their provenance and collection timing.'],12,'#3F3038','DM Sans',leading=22)
 s+=line(183,430,578,430,'#D9B5C2')+text(183,460,'Evidence',12,burg,'DM Sans',600)+text(325,460,'Method',12,burg,'DM Sans')+text(453,460,'Coverage',12,burg,'DM Sans')
 s+=text(183,514,'Read the example report',12,burg,'DM Sans',600)
 s+=text(31,607,'Understand. Explain.',46,white,'Newsreader')+text(33,651,'Before the model, understand the data.',14,rose,'DM Sans')
 # home as a document reading room, no fake report history
 s+=rect(666,0,534,320,'#F8EEF1')+text(691,35,'numek / DataTrust',20,burg,'Newsreader')+text(1094,33,'Local session',10,burg,'DM Sans')
 s+=text(691,86,'A clearer starting point.',29,burg,'Newsreader')+text(691,112,'Choose an example or begin a local analysis.',12,burg,'DM Sans')
 for i,(title,kind) in enumerate([('Bike Hour','Regression'),('Adult','Classification'),('Source review','Documents')]):
  x=691+i*162;s+=rect(x,137,145,161,white)+rect(x,137,145,7,burg if i==0 else '#CDA8B5')+text(x+12,176,title,18,burg,'Newsreader')+text(x+12,200,kind,10,burg,'DM Sans')+line(x+12,222,x+132,222,'#E8D7DE')+text(x+12,273,'Open example',11,burg,'DM Sans')
 # result read mode with margin
 s+=rect(666,336,534,354,white)+rect(666,336,138,354,burg)
 s+=text(683,372,'Bike Hour',17,white,'Newsreader')
 for i,n in enumerate(['Overview','Findings','Evidence','Methods','Coverage']):s+=text(683,415+i*38,n,11,white if i==1 else '#D2A8B7','DM Sans')
 s+=text(826,368,'Finding / Target relationship',10,burg,'DM Sans')+lines(826,408,['Two features tell','the same story','as the target.'],30,burg,'Newsreader',leading=32)
 s+=text(826,520,'cnt = casual + registered',17,burg,'DM Sans',600)
 s+=lines(826,550,['Verified across all 17,379 observations.','Both inputs are declared unavailable at','prediction. Review their provenance.'],12,'#3F3038','DM Sans',leading=20)
 s+=line(826,610,1176,610,'#D9B5C2')+text(826,636,'Algebra does not establish leakage.',11,burg,'DM Sans')+text(826,666,'Method & evidence references',11,burg,'DM Sans')
 return svg(s,'Direction B: report-led typography, example report covers and a reading workspace')

def c():
 navy='#173B54'; citron='#D9ED4B'; blue='#517BC4'; s=rect(0,0,650,690,navy)
 s+=text(30,48,'NUMEK',28,citron,'Barlow Condensed',600)+text(384,43,'DataTrust',13,'#FFFFFF','IBM Plex Sans')+text(503,43,'Methodology',13,'#FFFFFF','IBM Plex Sans')
 s+=lines(30,133,['SEE THE DATA.','QUESTION THE INPUTS.'],62,'#FFFFFF','Barlow Condensed',600,64)
 s+=lines(32,239,['Dataset reliability, examined from both sides.','Inspect the evidence before you train.'],15,'#D7E5EA','IBM Plex Sans',leading=24)
 s+=rect(30,310,285,310,citron)+rect(327,310,293,310,'#E6EFF2')
 s+=text(49,344,'Original dataset',13,navy,'IBM Plex Sans',600)+text(346,344,'Components removed',13,navy,'IBM Plex Sans',600)
 s+=text(49,410,'17',68,navy,'Barlow Condensed',600)+text(112,408,'columns',13,navy,'IBM Plex Sans')+text(346,410,'15',68,navy,'Barlow Condensed',600)+text(409,408,'columns',13,navy,'IBM Plex Sans')
 for i,(label,vs) in enumerate([('Rows',('17,379','17,379')),('casual',('Included','Removed')),('registered',('Included','Removed'))]):
  y=455+i*43
  s+=text(49,y,label,12,navy,'IBM Plex Sans')+text(195,y,vs[0],12,navy,'IBM Plex Sans')+text(346,y,label,12,navy,'IBM Plex Sans')+text(490,y,vs[1],12,navy,'IBM Plex Sans')
 s+=text(49,588,'1 supported relationship',13,navy,'IBM Plex Sans',600)+text(346,588,'0 in searched methods',13,navy,'IBM Plex Sans',600)
 s+=text(30,656,'Explore the example',14,citron,'IBM Plex Sans',600)+text(316,655,'Two saved runs. No reliability verdict.',11,'#D7E5EA','IBM Plex Sans')
 # wide toolbar and paired session home
 s+=rect(666,0,534,320,'#F4F8F5')+rect(666,0,534,51,navy)+text(686,33,'DataTrust',19,'white','Barlow Condensed',600)+text(811,31,'Analyze',11,'white','IBM Plex Sans')+text(886,31,'Compare examples',11,citron,'IBM Plex Sans')+text(1090,31,'Local session',10,'white','IBM Plex Sans')
 s+=text(687,94,'Start with a question.',29,navy,'Barlow Condensed',600)+text(688,118,'Investigate a dataset, split, or supplied version.',12,navy,'IBM Plex Sans')
 s+=rect(686,140,238,146,'#E1EBEE')+rect(938,140,242,146,navy)
 s+=text(703,169,'Analyze one dataset',17,navy,'IBM Plex Sans',600)+text(957,169,'Examine a difference',17,citron,'IBM Plex Sans',600)
 s+=lines(703,210,['Bike Hour example','17,379 rows · Regression'],12,navy,'IBM Plex Sans',leading=24)+lines(957,210,['Original / components removed','Open the two saved reports'],12,'#FFFFFF','IBM Plex Sans',leading=24)
 # results two lanes plus interpretation
 s+=rect(666,336,534,354,'#F4F8F5')+text(686,366,'Bike Hour / Two saved runs',14,navy,'IBM Plex Sans',600)
 s+=rect(686,386,240,183,'#D9ED4B')+rect(938,386,242,183,'#E1EBEE')
 s+=text(702,415,'Original',15,navy,'IBM Plex Sans',600)+text(954,415,'Components removed',15,navy,'IBM Plex Sans',600)
 s+=text(702,455,'cnt = casual + registered',15,navy,'IBM Plex Sans',600)+lines(954,450,['No supported target relationship','in the searched scope.'],12,navy,'IBM Plex Sans',leading=20)
 s+=text(702,499,'17,379 verified overlap rows',12,navy,'IBM Plex Sans')+text(702,545,'Inspect original evidence',11,navy,'IBM Plex Sans')+text(954,545,'Inspect control evidence',11,navy,'IBM Plex Sans')
 s+=lines(686,603,['Removing two columns changes the finding.','It does not establish overall dataset reliability.'],15,navy,'IBM Plex Sans',leading=24)+text(686,669,'Same observations. Different supplied features. No overall score.',11,navy,'IBM Plex Sans')
 return svg(s,'Direction C: two-column comparison with preserved populations and separate interpretation')

def d():
 ink='#21182F'; lilac='#D9C9F0'; mint='#8ECFBA'; s=rect(0,0,650,690,ink)
 s+=text(32,47,'NUMEK',25,lilac,'Space Grotesk',600)+text(386,44,'DataTrust',13,'white','Space Grotesk')+text(508,44,'Methodology',13,'white','Space Grotesk')
 s+='<g transform="translate(0,-264)">'
 # genuine relationships, no abstract cloud
 s+=rect(33,414,183,70,'#382C48',8)+text(50,442,'casual',18,lilac,'Space Grotesk')+text(50,466,'Declared unavailable',10,'#CDBFDD','Space Grotesk')
 s+=rect(33,536,183,70,'#382C48',8)+text(50,564,'registered',18,lilac,'Space Grotesk')+text(50,588,'Declared unavailable',10,'#CDBFDD','Space Grotesk')
 s+=path('M216 449 H254 Q270 449 270 466 V494 H315',mint,2)+path('M216 571 H254 Q270 571 270 554 V510 H315',mint,2)
 s+=rect(315,462,124,79,mint,10)+text(336,493,'Sum',18,ink,'Space Grotesk',500)+text(336,519,'Verified',11,ink,'Space Grotesk')+line(439,501,486,501,mint,2)
 s+=rect(486,462,131,79,lilac,10)+text(507,495,'cnt',24,ink,'Space Grotesk',500)+text(507,521,'Target',11,ink,'Space Grotesk')
 s+='</g>'
 s+=text(34,382,'17,379 rows support this relationship.',12,mint,'Space Grotesk')
 s+=lines(32,465,['Every finding','has a source.'],57,lilac,'Space Grotesk',500,61)
 s+=lines(34,572,['Follow the evidence. Understand the method.','Keep the investigation local.'],15,'#E6DFF0','Space Grotesk',leading=25)
 s+=rect(33,625,175,42,mint,7)+text(52,652,'Follow an example',13,ink,'Space Grotesk',500)
 # app home horizontal sources palette plus main selection
 s+=rect(666,0,534,320,'#F3EDF9')+text(688,35,'DataTrust',18,ink,'Space Grotesk',600)+text(1080,33,'Local session',11,ink,'Space Grotesk')
 s+=text(688,86,'Choose your evidence.',27,ink,'Space Grotesk',500)
 for i,(n,k) in enumerate([('Table','Rows & features'),('Text','Passages & labels'),('Image','Assets & metadata')]):
  x=688+i*167;s+=rect(x,110,153,75,'#E3D7F0',10)+text(x+14,141,n,17,ink,'Space Grotesk',500)+text(x+14,164,k,10,ink,'Space Grotesk')
 s+=rect(688,204,490,92,ink,9)+text(706,232,'Bike Hour',18,lilac,'Space Grotesk',500)+text(706,253,'Explore a verified target relationship',11,'white','Space Grotesk')+text(706,277,'Example dataset / Regression',10,mint,'Space Grotesk')
 # result unique 3 columns evidence path
 s+=rect(666,336,534,354,ink)+text(688,367,'Bike Hour / Evidence trail',14,lilac,'Space Grotesk',500)
 for x,n in [(688,'Source fields'),(858,'Observed relationship'),(1041,'Interpretation')]:s+=text(x,405,n,10,'#BCAECA','Space Grotesk')
 s+=rect(688,425,145,51,'#382C48',6)+text(702,456,'casual',15,lilac,'Space Grotesk')+rect(688,490,145,51,'#382C48',6)+text(702,521,'registered',15,lilac,'Space Grotesk')
 s+=path('M833 450 H844 V481 H859 M833 515 H844 V481',mint,1.5)
 s+=rect(859,448,161,73,mint,6)+text(874,477,'Sum equals cnt',15,ink,'Space Grotesk',500)+text(874,503,'17,379 / 17,379 rows',10,ink,'Space Grotesk')
 s+=line(1020,482,1035,482,mint,1.5)+lines(1041,456,['Review feature','availability','and derivation.'],13,lilac,'Space Grotesk',leading=22)
 s+=line(688,570,1178,570,'#574863')+text(688,598,'Why this was surfaced',13,lilac,'Space Grotesk',600)+lines(688,622,['The identity is observed; input timing is supplied by the user.','Neither establishes actual model use or leakage.'],11,'#E3D7F0','Space Grotesk',leading=20)+text(688,672,'Open source rows',11,mint,'Space Grotesk')+text(1049,672,'Method & scope',11,mint,'Space Grotesk')
 return svg(s,'Direction D: a bounded source-to-finding trail and quiet lilac workspace')

def e():
 green='#174B40'; mint='#D5F2E4'; s=rect(0,0,650,690,mint)
 s+=text(25,109,'NUMEK',110,green,'Archivo',800)+text(468,54,'DataTrust',13,green,'Archivo')+text(468,83,'Open example',13,green,'Archivo',600)
 s+=rect(0,148,650,321,'white')+rect(0,148,650,42,green)+text(31,175,'DataTrust',13,'white','Archivo',600)+text(339,175,'Dataset     Findings     Report',11,mint,'Archivo')
 s+=text(31,228,'Bike Hour',24,green,'Archivo',600)+text(31,252,'17,379 rows · 17 columns · Regression',11,green,'Archivo')
 s+=rect(31,275,588,34,'#E8F6EF')+text(44,297,'Finding',11,green,'Archivo',600)+text(437,297,'Evidence',11,green,'Archivo',600)
 for i,(n,k) in enumerate([('Target relationship','17,379 rows'),('Declared availability','2 columns'),('IQR review candidates','1,192 / 17,379')]):
  y=335+i*40;s+=text(44,y,n,12,green,'Archivo')+text(437,y,k,12,green,'Archivo')+line(31,y+13,619,y+13,'#DBE7E1')
 s+=lines(31,529,['Your data.','Open to inspection.'],49,green,'Archivo',600,56)
 s+=text(33,629,'Findings, source evidence and clear reports.',15,green,'Archivo')
 s+=text(33,667,'Local execution. Inspectable methodology. HTML / PDF / JSON.',11,green,'Archivo')
 # application file/session table, navigation top and narrow tool rail
 s+=rect(666,0,534,320,'#FAFCFA')+rect(666,0,534,45,green)+text(687,29,'DataTrust',15,'white','Archivo',600)+text(838,28,'Analyze     Examples     Methodology',11,'#D5F2E4','Archivo')
 s+=text(688,90,'Start an analysis.',27,green,'Archivo',600)+rect(1035,66,143,34,mint,4)+text(1048,88,'Open local dataset',11,green,'Archivo',600)
 s+=text(688,126,'Example collection',11,green,'Archivo')
 for i,(n,k) in enumerate([('Bike Hour','Regression'),('Adult','Classification'),('Source reconciliation','Documents')]):
  y=160+i*52;s+=rect(688,y-21,490,43,mint if i==0 else '#F0F4F1',3)+text(703,y+4,n,13,green,'Archivo',600)+text(1024,y+4,k,11,green,'Archivo')
 s+=text(688,307,'Examples are bundled previews. Your local session is temporary.',10,green,'Archivo')
 # results side inspector distinct row arrangement
 s+=rect(666,336,534,354,'#FAFCFA')+rect(666,336,45,354,green)+text(679,370,'N',20,mint,'Archivo',800)
 for i in range(4):s+=rect(679,406+i*49,17,17,mint if i==1 else '#609587',3)
 s+=text(730,369,'Bike Hour',23,green,'Archivo',600)+text(730,396,'Findings',11,green,'Archivo')
 s+=rect(730,418,218,52,mint,3)+lines(742,439,['Supported target','relationship'],13,green,'Archivo',600,18)
 s+=text(742,502,'Declared availability',12,green,'Archivo')+text(742,553,'IQR review candidates',12,green,'Archivo')+text(742,604,'Near-constant fields',12,green,'Archivo')
 s+=rect(965,418,215,251,'white',3,'#CDDED5')+text(980,444,'Evidence',12,green,'Archivo',600)+lines(980,479,['cnt = casual','+ registered'],19,green,'Archivo',600,23)+text(980,542,'17,379 verified rows',12,green,'Archivo',600)
 s+=lines(980,574,['Both inputs are declared','unavailable at prediction.','Review timing and provenance.'],10,green,'Archivo',400,17)+text(980,650,'Open full evidence',11,green,'Archivo',600)
 return svg(s,'Direction E: product-first broad bands, a dataset table and a precise evidence inspector')

concepts=[
{'id':'a','title':'Make the evidence visible','thesis':'A finding unfolds into its supporting evidence.','type':'Manrope / open, precise, generously spaced','palette':['#171D39','#2345E8','#DDE1FF','#FFB5A6','#FFFFFF'],'influence':'Hyperbolic’s shift from rendered subject to line detail + Micro’s staged product reveal.','refs':['hyperbolic','micro'],'landing':'An oversized finding panel separates into source, method and coverage layers. Continue into a modality selector with actual example output, a local-execution explanation, an annotated report preview and the product entry.','home':'A horizontal application bar above a split workspace: example datasets on the left, a readable selected preview on the right.','results':'A focused finding expands in place into verified rows, the method and coverage. The key expression retains its position throughout.','motion':'A short, scroll-linked separation of evidence sheets; entering the app flattens the same sheets into working panels. One composed transition, then restrained disclosure.','risk':'Strongest product reveal; risks decorative depth or small text. Keep evidence flat and readable once it becomes interactive.','mobile':'Stack the evidence sheets in reading order; remove perspective and keep the finding visible above its evidence.','build':'Independent layout and tokens. CSS transforms and SVG, with Motion or GSAP only for the opening sequence.'},
{'id':'b','title':'Read the finding','thesis':'The report is the face of the product.','type':'Newsreader + DM Sans / expressive titles, calm evidence','palette':['#61233B','#F4DCE3','#FFFDFC','#2B2025','#AFB5DA'],'influence':'AI in Design’s continuity from cover to chapter + Siena’s typographic specificity and subject framing. No film or ticket motifs.','refs':['stateai','siena'],'landing':'A confident report cover leads directly into an actual finding. Alternate short conclusions, annotated figures and source notes; show report exports, broader analysis families, method limits and local product entry.','home':'A reading-oriented collection of bundled example reports with a prominent local-analysis action. It does not imply persistent saved history.','results':'A continuous report with compact chapter navigation and evidence in the margin; selecting a note opens the underlying reference beside the prose.','motion':'Large cover typography settles into a report heading. Chapter transitions are simple cuts and measured crossfades; no page-turn simulation.','risk':'Clearest stakeholder communication; could underplay technical depth. Keep source references, denominators and methodology one action away.','mobile':'Convert the chapter rail to a compact contents control; margin evidence follows its referenced paragraph.','build':'Dedicated document layout; typography and CSS carry the identity. Minimal motion, accessible anchored sections.'},
{'id':'c','title':'See what changed','thesis':'Comparison becomes the visual language.','type':'Barlow Condensed + IBM Plex Sans / compact display, legible measures','palette':['#173B54','#D9ED4B','#F4F8F5','#517BC4','#D7E5EA'],'influence':'Pudding’s explained relationships + ART+TECH’s bold data-led sections + Unseen’s clear visual shifts between chapters.','refs':['pudding','arttech','unseen'],'landing':'Open on two real saved runs of Bike Hour: original and components removed. A shared baseline exposes what changes and what does not. Follow with single-dataset diagnostics, temporal/split/version capabilities, evidence scope, exports and product entry.','home':'A wide toolbar and paired work area for one dataset or a supplied comparison. No permanent sidebar and no live-monitoring timeline.','results':'Aligned evidence lanes with fixed row labels, shared chart scales and explicit population counts; the interpretation sits beneath both.','motion':'Rows align before a change is emphasized; a user-controlled reveal compares views. Keyboard buttons provide the same information as dragging.','risk':'Best for analytical differences; risks implying that removing a finding means success. Keep the scope and remaining questions alongside the comparison.','mobile':'Toggle between the two datasets while retaining labels and scale, followed by a plain-language difference summary.','build':'Separate comparison layout, SVG plots and accessible view controls. Two existing reports stay distinct from a newly executed comparison.'},
{'id':'d','title':'Follow the source','thesis':'A bounded trail connects source, method and finding.','type':'Space Grotesk / distinctive labels and open numeric forms','palette':['#21182F','#D9C9F0','#8ECFBA','#FCFAFE','#AD5576'],'influence':'Phantom’s overview-to-index change + Pudding’s relationship encoding. Translate navigation between evidence scales, not their visual effects.','refs':['phantom','pudding'],'landing':'Start with source fields visibly forming one verified relationship. Selecting the finding reveals its actual evidence path. Continue with declared document reconciliation, modality examples, method/coverage disclosures, report exports and local entry.','home':'A light workspace organized around supplied sources, with a selected local example and an explicit action to begin analysis.','results':'A three-part source → method → interpretation view; only the selected relationship is drawn. Exact evidence IDs and source-row access remain visible.','motion':'Selecting an evidence item traces its short connection and updates a stable inspector. The application uses no ambient graph movement.','risk':'Most distinctive evidence navigation; can become a diagram that overwhelms the work. Bound the trail and always provide a table/list equivalent.','mobile':'Show the three steps vertically with clear labels; retain a simple evidence list instead of a draggable canvas.','build':'Dedicated source-oriented structure. Small semantic SVG paths and DOM inspectors; no force-directed network or 3D scene.'},
{'id':'e','title':'Open the work','thesis':'Put the useful software in the first viewport.','type':'Archivo / direct, broad, confident','palette':['#174B40','#D5F2E4','#FAFCFA','#609587','#E5C85A'],'influence':'LPAS’s large, cropped subject panels + Studio Null’s reduction to a few decisive elements. Linear is a secondary check on dense interface legibility.','refs':['lpas','null','linear'],'landing':'A large, usable DataTrust excerpt sits under the company statement. Broad sections switch between a dataset table, findings inspector and report. Follow with modality examples, local workflow, methodology and a direct app entry.','home':'A table-based local workbench with examples, a clear start action, top navigation and contextual previews.','results':'An ordered findings list beside an evidence inspector; expanding a finding retains the list position. Flat material and deliberate spacing provide hierarchy.','motion':'A crop opens to reveal the whole product, then ordinary direct manipulation takes over. Fast focus and selection feedback.','risk':'Most immediately usable; greatest risk of looking like ordinary SaaS. Distinctive typography, broad composition and real interactive evidence must do the work.','mobile':'Use a list-to-detail flow with a visible back control and preserved selection; the homepage product excerpt becomes a vertical sample.','build':'Independent row-oriented layout and compact inspector. CSS transitions, semantic tables and keyboard-first controls.'}
]
funcs=[a,b,c,d,e]
for c,f in zip(concepts,funcs):
 c['svg']=f();(P/'styleframes'/f"{c['id']}.svg").write_text(c['svg'])

refs=[
{'id':'hyperbolic','title':'Hyperbolic / Studio Freight','url':'https://hyperbolic.studiofreight.dev/','creator':'https://studiofreight.com/work/hyperbolic','images':['hyperbolic-hero.jpg','hyperbolic-detail.jpg'],'observation':'The oversized product sits off the left edge while a narrow right column explains it. On scroll, the same silhouette changes from a white render to violet line detail; the graphic continues into the next section.','application':'Keep a recognizable analytical object in place as the page reveals its evidence. The subject for NUMEK is the finding/report, not GPU hardware.','motion':'Observed the render-to-line-detail scroll states. Some media on the creator case study reported playback failure; original-site visuals rendered.','status':'Live hero and next section inspected; creator case study read.'},
{'id':'micro','title':'Micro / Reform Collective','url':'https://micro.reformcollective.com/','creator':'https://www.reformcollective.com/work/micro','images':['micro-hero.jpg','micro-workflow.jpg'],'observation':'An edge-framed opening scene gives way to an enormous mask, then a front-facing application preview. A small product-mode strip sits directly above the preview. The reveal has three distinct scales.','application':'Stage the transition from NUMEK’s proposition into a readable working product. Retain the deliberate framing, not the scenery, spheres or branded mask.','motion':'Scrolled through opening scene → central mask → application. The initial preload delayed access; no precise easing or performance measurement claimed.','status':'Live landing sequence and creator case study inspected.'},
{'id':'stateai','title':'AI in Design Report 2026 / ++hellohello','url':'https://stateofaidesign.com/','creator':'https://www.hellohello.is/case-studies/stateofai','images':['stateai-cover.jpg','stateai-chapter.jpg'],'observation':'The cover divides a small explanatory column from a dominant title. The Tools chapter reuses this asymmetry for its conclusion and chart, with the source immediately below the visual.','application':'Carry brand scale into the report without sacrificing chart labels or reading order. Pair conclusions with denominators, source notes and methodology.','motion':'Observed cover scrolling and navigated to the Tools chapter. The stable column alignment supplies continuity; no chart-hover behavior was tested.','status':'Live homepage and Tools chapter inspected. The supplied URL currently serves the 2026 edition.'},
{'id':'arttech','title':'ART+TECH Report 2023 / MoreSleep','url':'https://www.arttechreport.com/','creator':'https://www.awwwards.com/sites/art-tech-report-2023','images':['arttech-cover.jpg','arttech-reveal.jpg'],'observation':'One saturated field unifies display type and quantitative sections. In the demographic section, interacting with a tile reveals the chart while another tile returns to its label.','application':'Make evidence disclosure feel intentional and graphically distinctive. NUMEK’s default state must still expose the important conclusion and support keyboard interaction.','motion':'Clicked the visible gender tile; the bar chart appeared. Cover, demographic section and disclosure states captured.','status':'Discovered through the Awwwards project page; original site inspected.'},
{'id':'lpas','title':'LPAS / Studio Naam','url':'https://lpas.com/','creator':'https://studionaam.com/projects/lpas/','images':['lpas-hero.jpg','lpas-categories.jpg'],'observation':'The next subject is already visible as a narrow slice at the edge. Vertical scrolling advances a horizontal sequence of large images and substantial caption blocks; each panel has its own muted field.','application':'Use partial product views to promise the next analytical layer, and let sections expand into legible software. No architecture imagery or forced horizontal scrolling in the working app.','motion':'Observed and captured ten sequential scroll frames across category panels. Frame playback shows ordering, not original timing.','status':'Live opening and multiple category panels inspected; creator page checked.'},
{'id':'phantom','title':'Phantom Studios','url':'https://www.phantom.land/','creator':'https://www.phantom.land/','images':['phantom-overview.jpg','phantom-index.jpg'],'observation':'A spatial wall of work uses fixed edge controls; the bottom-left view switch replaces it with a highly compressed project index. Two presentations serve different levels of scanning.','application':'Let evidence overview and exact detail be different but connected views. Keep critical navigation in the DOM and avoid curved text or motion in reading mode.','motion':'Used the grid/list switch. Captured the spatial overview and the entering index state; not a complete project-detail journey.','status':'Live overview, scroll response and view switch inspected.'},
{'id':'pudding','title':'Hamilton / Shirley Wu, The Pudding','url':'https://pudding.cool/2017/03/hamilton/','creator':'https://pudding.cool/2017/03/hamilton/','images':['pudding-overview.jpg','pudding-filtered.jpg'],'observation':'Text introduces the meaning of each mark before the visualization groups them. The page explains relationship and filter semantics next to the intended analytical view.','application':'Teach one visual encoding, then reuse it for investigation. Every mark or connection in DataTrust must correspond to supplied evidence.','motion':'Observed marks moving from a field toward groups during scrolling. The later filter view remained incompletely rendered, so working filters and tooltip behavior are unverified.','status':'Partially rendered. Use only the observed explanatory sequencing, not claimed interaction quality.'},
{'id':'siena','title':'Siena Film Foundation / Niccolò Miranda','url':'https://siena.film/','creator':'https://siena.film/','images':['siena-cover.jpg','siena-main.jpg'],'observation':'A distinctive typographic entrance yields to an almost full-viewport subject, with supporting metadata attached to the edges and the next item visible below.','application':'Give the real product subject presence and distinctive typography. Do not borrow tickets, film texture, festival language or the entry gate.','motion':'Entered the site and observed the transition to the film presentation. Later navigation and individual film detail were not tested.','status':'Entry and main presentation inspected; capture includes an in-progress title transition.'},
{'id':'unseen','title':'Year in Review 2025 / Unseen Studio','url':'https://2025.unseen.co/','creator':'https://2025.unseen.co/','images':['unseen-cover.jpg','unseen-scroll.jpg'],'observation':'Display typography occupies offset positions within a textured field. Scrolling pushes the cover sideways and reveals a contrasting next scene.','application':'Use a decisive change of composition when moving from question to evidence. Preserve semantic order and provide a direct route to the product.','motion':'Observed the opening lateral scene transition only. No claims about later project interactions or mobile behavior.','status':'Live opening and first transition inspected.'},
{'id':'null','title':'Studio Null','url':'https://www.madebynull.com/','creator':'https://www.madebynull.com/','images':['null-overview.jpg','null-info.jpg'],'observation':'A single central object sits inside a very sparse frame. Opening Info brings readable content forward while the object loses definition behind it.','application':'Give one product object attention, then let the user’s reading task dominate. NUMEK should use an evidence/report object, not an unrelated sculpture.','motion':'Opened Info and observed the content layer and softened background. Did not submit the project form.','status':'Live opening and information disclosure inspected.'},
{'id':'linear','title':'Linear / secondary product reference','url':'https://linear.app/','creator':'https://linear.app/','images':['linear-product.jpg'],'observation':'The homepage’s app preview demonstrates one concrete working state with a narrow navigation column, strong issue title and quieter contextual information.','application':'Check density, hierarchy and selected-item clarity. Do not import Linear’s agent workflow, collaboration features or product claims into NUMEK.','motion':'Scrolled to inspect the product preview. This was the public marketing demo, not an authenticated application review.','status':'Public product preview only; secondary influence.'}
]
(P/'sources.json').write_text(json.dumps({'captured':'2026-10-16','viewport':'1280 × 720 default browser viewport','rights':'Reference screenshots retained for this private design research board; original creators retain their rights. No brand assets are used in NUMEK style frames.','references':refs},indent=2))
(P/'directions.json').write_text(json.dumps([{k:v for k,v in c.items() if k!='svg'} for c in concepts],indent=2))
# Standalone HTML includes inline SVG so locally bundled webfonts are applied consistently.
head='''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>NUMEK — Visual direction review</title><link rel="stylesheet" href="fonts.css"><link rel="stylesheet" href="board.css"></head><body><header><a class="brand" href="#top">NUMEK <span>Visual lab / v4</span></a><nav aria-label="Review sections"><a href="#directions">Five directions</a><a href="#research">Reference board</a><a href="#basis">Product basis</a></nav><span class="checkpoint">Creative-direction review</span></header><main id="top"><section class="intro"><p>Research → direction → your review</p><h1>Make the depth of<br>DataTrust visible.</h1><div><p>Five proposed identities, grounded in live reference studies and actual analytical evidence.</p><p class="muted">These are static composition studies, not the five runnable prototypes. The next phase starts after your direction review.</p></div></section><section id="directions"><div class="section-head"><h2>Five different starting points.</h2><span>Select a direction to examine all three experiences.</span></div><div class="choices" role="group" aria-label="Choose a direction">'''
for c in concepts:
 thumb=c['svg'].replace('viewBox="0 0 1200 690"','viewBox="0 0 650 690" preserveAspectRatio="xMidYMin slice"').replace('role="img"','aria-hidden="true"')
 head+=f'<button class="choice" data-id="{c["id"]}" aria-pressed="false"><div class="thumb">{thumb}</div><span class="choice-name"><b>{c["id"].upper()}</b>{c["title"]}</span></button>'
head+='''</div><article id="direction-detail" aria-live="polite"></article></section><section id="research"><div class="section-head"><div><p class="kicker">Observed, not assumed</p><h2>The reference board.</h2></div><span>Genuine browser captures / 16 October 2026</span></div><p class="research-intro">The useful ideas are framing, continuity, disclosure and information hierarchy. The photographs, logos, visual metaphors and proprietary compositions stay with their creators. Click any capture to inspect the original-sized image.</p><div class="references">'''
for ref in refs:
 head+=f'<article class="reference" id="ref-{ref["id"]}"><h3>{ref["title"]}</h3><div class="reference-images">'
 for im in ref['images']:head+=f'<a href="captures/{im}" target="_blank" aria-label="View full capture of {html.escape(ref["title"])}"><img src="captures/{im}" loading="lazy" alt="Actual browser capture: {html.escape(ref["title"])}"></a>'
 head+=f'</div><p>{ref["observation"]}</p><p><strong>For NUMEK.</strong> {ref["application"]}</p><details><summary>Motion observed & inspection limits</summary><p>{ref["motion"]}</p><p>{ref["status"]}</p></details><div class="source-links"><a href="{ref["url"]}" target="_blank" rel="noreferrer">Original site ↗</a><a href="{ref["creator"]}" target="_blank" rel="noreferrer">Source / creator ↗</a></div></article>'
head+='''</div><article class="motion-study"><div><h3>LPAS: a sequence you can inspect.</h3><p>Ten genuine browser captures across the scrolling category panels. Scrub through the frames or play them in order.</p><p class="muted">This is a sampled scroll sequence, not a real-time screen recording. Playback timing is illustrative. Capture timestamps are saved in <a href="motion/lpas/frames.json">the frame manifest</a>.</p><button id="play-frames" type="button">Play sequence</button><label for="frame-range">Captured frame <output id="frame-number">1 / 10</output></label><input type="range" id="frame-range" min="0" max="9" value="0"></div><img id="motion-image" src="motion/lpas/frame-00.jpg" alt="LPAS browser scroll sequence, frame 1 of 10"></article></section><section id="basis"><div class="section-head"><h2>One company. One factual foundation.</h2></div><div class="basis-grid"><div><h3>The common example</h3><p>Bike Hour, from the repository’s saved regression validation report: <strong>17,379 rows, 17 columns</strong>. The verified relationship is <strong>cnt = casual + registered</strong>. Both features are declared unavailable at prediction time.</p><p>The relationship has 100% finite-target coverage. That is evidence coverage, not a reliability score or a model-performance claim. Observed algebra alone does not prove leakage.</p><p>Direction C juxtaposes the original with a saved 15-column control. Those are two existing regression runs; this board has not run a new comparative analysis.</p><a href="content-evidence.json">Inspect the extracted source evidence</a></div><div><h3>What every concept will preserve</h3><p>NUMEK is the company. DataTrust is the implemented product. Classification scores retain their methodology; other families do not acquire an invented universal score.</p><p>Tabular, regression, comparative, temporal, text, image and cross-representation work are represented. ConfidenceGuard and HallucinationGuard remain future directions; audio is deferred.</p><p>Local execution, source evidence, explained methods, coverage limits and HTML/PDF/JSON reports remain central. Example collections are prototype content, not claims of persistent report history, accounts or hosted monitoring.</p></div><div><h3>The implementation after review</h3><p>Five independent concept layouts, each with a complete landing page, application home and results screen. Shared factual fixtures and navigation utilities only; no shared visual shell.</p><p>Desktop and mobile browser review, keyboard navigation, reduced motion, meaningful sample interactions, consistent screenshot sizes and a critical comparison.</p><p>All work stays in <code>frontend-visual-lab-v4/</code>. Production code and earlier experiments remain untouched. No commits, pushes or deployment.</p></div></div></section><footer><p>Prepared for direction review. Names describe the proposed presentation, not new products.</p><p>Source screenshots belong to their respective creators. NUMEK studies are original compositions.</p></footer></main><script src="board-data.js"></script><script src="board.js"></script></body></html>'''
(P/'index.html').write_text(head)
(P/'board-data.js').write_text('const concepts = '+json.dumps(concepts)+';')
print('Built research board, 5 static style frames and evidence fixture.')
