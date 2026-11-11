"""Build the creative-direction checkpoint. Static studies, not prototypes."""
from pathlib import Path
import json
from html import escape as E

ROOT = Path(__file__).resolve().parent
STUDIES = ROOT / 'studies'
STUDIES.mkdir(exist_ok=True)

class Drawing:
    def __init__(self, bg, ink='#14222F'):
        self.ink = ink
        self.parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1100 700" role="img"><rect width="1100" height="700" fill="{bg}"/>']
    def rect(self,x,y,w,h,c,r=0,stroke=None):
        self.parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{c}"'+(f' stroke="{stroke}"' if stroke else '')+'/>')
    def text(self,x,y,t,size=16,c=None,font='Arial, sans-serif',weight=400,spacing=None):
        self.parts.append(f'<text x="{x}" y="{y}" font-family="{font}" font-size="{size}" font-weight="{weight}" fill="{c or self.ink}"'+(f' letter-spacing="{spacing}"' if spacing is not None else '')+f'>{E(str(t))}</text>')
    def lines(self,x,y,lines,size=16,leading=None,**kw):
        for i,t in enumerate(lines): self.text(x,y+i*(leading or size*1.15),t,size,**kw)
    def line(self,x,y,x2,y2,c='#CBD1D9',width=1,dash=None):
        self.parts.append(f'<path d="M{x},{y} L{x2},{y2}" stroke="{c}" stroke-width="{width}"'+(f' stroke-dasharray="{dash}"' if dash else '')+'/>')
    def circle(self,x,y,r,c): self.parts.append(f'<circle cx="{x}" cy="{y}" r="{r}" fill="{c}"/>')
    def path(self,d,c='none',stroke=None,width=1): self.parts.append(f'<path d="{d}" fill="{c}"'+(f' stroke="{stroke}" stroke-width="{width}"' if stroke else '')+'/>')
    def button(self,x,y,t,bg,fg,w=160,r=4):
        self.rect(x,y,w,40,bg,r); self.text(x+16,y+25,t,13,fg,weight=600)
    def histogram(self,x,y,w,h,color,muted='#D8E4EE'):
        bins=[9,42,66,68,65,103,85,106,115,95,52,56,59,27,22,24,13,13,10]
        self.line(x,y+h,x+w,y+h,muted)
        for i,n in enumerate(bins): self.rect(x+i*w/19,y+h-h*n/115,w/19-3,h*n/115,color,1)
        self.text(x,y+h+21,'2.33',11); self.text(x+w-65,y+h+21,'82.60 MPa',11)
    def row(self,x,y,w,label,value,c=None):
        self.text(x,y,label,14,c); self.text(x+w-100,y,value,14,c); self.line(x,y+17,x+w,y+17)
    def nav(self,brand='NUMEK',c=None,sub='DataTrust     Methodology',button='Explore DataTrust'):
        self.text(38,48,brand,26,c,weight=700,spacing=-1)
        self.text(410,45,sub,13,c)
        self.button(892,22,button,c or self.ink,'#14222F' if c in ('#FFF','#FFFFFF') else '#FFFFFF',170)
    def save(self,name):
        (STUDIES/(name+'.svg')).write_text(''.join(self.parts)+'</svg>')

def finding():
    a='#E54A2B'; blue='#214CD8'; ink='#14222F'
    d=Drawing('#F9FBFD');d.nav(c=ink)
    d.text(40,116,'DataTrust / Concrete / A finding, opened',14)
    d.lines(35,215,['25 rows repeat.', 'What comes next?'],89,90,weight=600,spacing=-5)
    d.lines(808,192,['Dataset reliability,', 'from evidence', 'to explanation.'],23,29)
    d.button(807,288,'Inspect this finding',a,'#FFF',220)
    d.rect(0,363,1100,234,blue)
    for x,heading,lines in [(40,'The observation',['25 rows repeat an earlier', 'complete parsed record.', '11 exact groups. 36 participating rows.']), (405,'The evidence',['Example parsed-row references', '73 / 78 / 81 / 84 / 87', '1,030 rows examined.']), (777,'The interpretation',['Valid repetition or unintended copying?', 'Review source context before', 'deciding whether to remove anything.'])]:
        d.text(x,403,heading,16,'#D3DEFF');d.lines(x,452,lines,17,29,c='#FFF')
    d.line(378,395,378,562,'#6C8AF1');d.line(749,395,749,562,'#6C8AF1')
    d.lines(40,640,['Understand the data before you train on it.', 'Inspectable analysis. Local execution. Reports that explain the evidence.'],20,28)
    d.save('finding-landing')
    d=Drawing('#F9FBFD');d.text(30,42,'NUMEK / DataTrust',23,weight=600);d.text(630,40,'Workspace     Methods     Exports',14)
    d.rect(0,67,1100,54,ink);d.text(30,101,'Current session',15,'#FFF');d.text(230,101,'Sample analyses',15,'#A9BACB');d.text(935,101,'Local execution',13,'#DAE7F0')
    d.text(35,184,'Start with a question.',44,weight=600,spacing=-2)
    d.text(37,219,'Open a dataset, then inspect the evidence that matters.',16)
    d.button(850,164,'New analysis',blue,'#FFF',200)
    d.text(36,288,'Open in this session',14,weight=600)
    for i,(title,typ,detail) in enumerate([('Concrete','Regression','1,030 rows / 9 columns'),('Evidence bundle demo','Connected representations','Illustrative document associations'),('Classification example','Classification','Scores apply only to this task policy')]):
        y=321+i*92;d.line(35,y,1060,y);d.text(37,y+38,title,23,weight=500);d.text(440,y+36,typ,15);d.text(723,y+36,detail,13)
    d.rect(35,612,1026,57,'#E6EEF8',5);d.text(55,646,'Concrete: 25 repeated rows. Open the finding to inspect its groups and source references.',16)
    d.save('finding-home')
    d=Drawing('#F9FBFD');d.text(30,43,'DataTrust / Concrete',23,weight=600);d.text(780,40,'Regression / No composite score',13)
    for x,w,t in [(30,285,'Finding'),(345,390,'Supporting evidence'),(765,305,'Interpretation')]:d.text(x,102,t,14,weight=600);d.line(x,119,x+w,119)
    d.rect(30,142,285,414,blue,8);d.lines(51,184,['Target variation', 'within repeated', 'inputs'],31,35,c='#FFF',weight=600)
    d.text(51,344,'9',100,'#FFFFFF',weight=600);d.text(51,379,'feature-identical groups',16,'#FFF');d.text(51,513,'20 participating rows',16,'#FFF')
    d.text(345,169,'Target range within one group',17,weight=600);d.text(345,212,'22.90–55.90 MPa',29,blue,weight=600)
    d.row(345,268,390,'Group rows','107 / 110');d.row(345,315,390,'Group rows','112 / 115');d.row(345,362,390,'Distinct targets','2');d.row(345,409,390,'Inputs','Identical')
    d.lines(765,176,['Variation can reflect repeated', 'measurements, stochastic outcomes,', 'or omitted context.'],16,27)
    d.rect(765,290,305,180,'#E6EEF8',6);d.lines(786,325,['Investigate next', '', 'Review source records and the', 'meaning of repeated measurements.', 'Keep legitimate repetition.'],16,25)
    d.line(30,601,1070,601);d.text(30,637,'Coverage and methods',16,weight=600);d.text(345,637,'Observed evidence / no automatic label correction',14)
    d.save('finding-results')

def report():
    plum='#352240';paper='#F7F5FF';yellow='#EDEA93';muted='#C1B2CA'
    d=Drawing(plum,'#FFFFFF');d.nav(c='#FFF',button='View sample report')
    d.lines(44,175,['Make the', 'evidence', 'understood.'],80,83,font='Baskerville, Georgia, serif')
    d.lines(48,466,['Dataset reliability, explained.', 'From technical detail to a report', 'you can put in someone’s hands.'],18,28,c='#E3DCE7')
    d.button(47,589,'Meet DataTrust',yellow,plum,180,20)
    d.rect(600,135,433,545,'#20112C',3);d.rect(574,109,433,545,paper,2)
    d.text(605,147,'NUMEK',18,plum,weight=700);d.text(841,145,'DataTrust report',12,plum)
    d.lines(606,214,['Concrete', 'Reliability review'],43,46,c=plum,font='Baskerville, Georgia, serif')
    d.line(606,287,975,287,'#D8D0E0');d.text(606,316,'Regression / 1,030 rows / 9 columns',12,plum)
    d.rect(605,348,370,100,yellow);d.text(621,376,'25 rows repeat an earlier record.',21,plum)
    d.lines(621,405,['11 exact groups. Review the source context', 'before deciding whether repetition is unintended.'],13,20,c=plum)
    d.text(606,482,'Target distribution',14,plum);d.ink=plum;d.histogram(606,505,365,88,plum)
    d.text(606,636,'Evidence, interpretation and limitations in one place.',11,plum)
    d.save('report-landing')
    d=Drawing('#ECE8F0',plum);d.rect(0,0,1100,74,plum);d.text(27,45,'numek',26,'#FFF',font='Baskerville, Georgia, serif');d.text(174,43,'DataTrust',17,'#FFF');d.text(803,43,'Sample desk    Local session',14,'#FFF')
    d.text(38,136,'Your analysis, ready to read.',37,font='Baskerville, Georgia, serif')
    d.text(39,175,'Reports opened in this session',15)
    for x,y,w,h,c in [(46,230,492,410,paper),(568,230,239,288,yellow),(831,230,231,288,'#DBD3E4')]:d.rect(x+7,y+8,w,h,'#DED7E4',2);d.rect(x,y,w,h,c,2)
    d.text(70,265,'Concrete',37,font='Baskerville, Georgia, serif');d.text(72,300,'Regression reliability review',16)
    d.line(70,326,510,326,'#D8D0E0');d.lines(72,367,['25 repeated rows', '9 groups with varying targets', '4 target IQR candidates'],22,43,font='Baskerville, Georgia, serif')
    d.text(72,582,'1,030 rows / 9 columns',13);d.text(72,613,'Continue reading',16,weight=600)
    d.lines(590,272,['Evidence', 'bundle demo'],29,32,font='Baskerville, Georgia, serif');d.lines(590,375,['Connected sources', 'Illustrative example'],14,24)
    d.lines(853,272,['Classification', 'example'],29,32,font='Baskerville, Georgia, serif');d.lines(853,375,['Explained scores', 'and guardrails'],14,24)
    d.button(570,567,'Start a new analysis',plum,'#FFF',238,20);d.save('report-home')
    d=Drawing('#ECE8F0',plum);d.rect(0,0,1100,65,plum);d.text(24,41,'DataTrust / Concrete',21,'#FFF',font='Baskerville, Georgia, serif');d.text(818,39,'HTML     PDF     JSON',14,'#FFF')
    d.text(27,122,'In this report',14,weight=600)
    for i,t in enumerate(['Overview','Priority findings','Target evidence','Feature evidence','Methods & coverage']):d.text(27,166+i*43,t,13)
    d.rect(216,87,592,595,paper);d.text(249,131,'Concrete',18);d.text(249,196,'A closer look at repetition',36,font='Baskerville, Georgia, serif')
    d.text(249,235,'25 rows repeat an earlier complete parsed record.',16)
    d.rect(249,267,521,82,yellow);d.text(266,300,'11 exact groups',24,font='Baskerville, Georgia, serif');d.text(266,326,'36 participating rows; largest group: 4',13)
    d.lines(249,389,['Repetition may represent valid repeated events, deliberate', 'weighting or unintended copying. Review the source context', 'before deciding whether any records should be removed.'],16,25)
    d.text(249,495,'Target distribution',16,weight=600);d.histogram(250,518,517,103,plum)
    d.text(838,131,'Evidence detail',16,weight=600);d.lines(838,176,['Parsed rows', '73, 78, 81, 84, 87', '', 'Population', '1,030 parsed rows', '', 'Method', 'Exact row comparison'],14,26)
    d.lines(838,488,['No composite score', 'is defined for regression.'],14,25);d.save('report-results')

def connected():
    bg='#EEEAFB';ink='#2A1740';violet='#6644D8';coral='#FCB3A0'
    d=Drawing(bg,ink);d.nav(c=ink)
    d.lines(40,160,['A finding is only as useful', 'as the evidence behind it.'],55,60,weight=500,spacing=-2)
    d.text(43,310,'DataTrust connects the observation to what you can inspect.',18)
    d.button(42,349,'Trace an example',violet,'#FFF',190,22)
    d.rect(42,447,252,188,'#FFF',12);d.text(62,478,'Source record',13,weight=600);d.text(62,520,'revenue',20);d.text(62,560,'12.4 million',32,violet,weight=500);d.text(62,608,'Illustrative evidence bundle',11)
    d.path('M294,540 C380,540 360,457 452,457','none',violet,3)
    d.rect(452,415,261,236,ink,12);d.text(472,448,'Declared comparison',13,'#E1D8FA');d.lines(472,494,['Values disagree.', 'Inspect context.'],28,34,c='#FFF',weight=500);d.text(472,621,'Fact / Candidate / Unresolved',12,'#E1D8FA')
    d.path('M713,535 C790,535 742,486 812,486','none',violet,3)
    d.rect(812,375,247,260,'#FFF',6);d.text(832,411,'Native document',13,weight=600)
    for i,w in enumerate([160,195,145,189,170]):d.rect(833,439+i*25,w,3,'#E6E0EE')
    d.rect(828,494,196,36,coral,3);d.text(836,518,'Revenue: 14.2 million',16);d.text(834,607,'Source context retained',12)
    d.save('connected-landing')
    d=Drawing('#FAF9FD',ink);d.rect(0,0,1100,71,bg);d.text(28,45,'numek / DataTrust',24,weight=500);d.text(537,42,'Sources      Relationships      Reports',14)
    d.text(32,130,'Follow the connection.',40,weight=500,spacing=-1.8);d.text(32,167,'Examples opened in this local session',15)
    d.rect(28,204,322,454,bg,12);d.text(48,242,'Open examples',14,weight=600)
    for y,title,sub in [(292,'Evidence bundle demo','Connected representations'),(391,'Concrete','Regression / 1,030 rows'),(490,'Classification example','Explained scoring policy')]:
        if y==292:d.rect(42,y-28,293,82,'#FFF',8)
        d.text(55,y,title,19,weight=500);d.text(55,y+27,sub,12)
    d.text(382,239,'Evidence bundle demo',26,weight=500);d.text(382,272,'Synthetic example / declared record-to-document relation',13)
    d.rect(380,307,282,175,'#FFF',8,'#DDD5ED');d.text(403,341,'Records',15);d.text(403,394,'revenue',27);d.text(403,440,'12.4 million',21,violet)
    d.line(663,396,731,396,violet,3);d.circle(697,396,7,violet)
    d.rect(731,307,326,175,bg,8);d.text(752,342,'Document field',15);d.text(752,394,'revenue',27);d.text(752,440,'14.2 million',21,violet)
    d.rect(380,507,678,123,ink,8);d.text(404,543,'A discrepancy in declared evidence',23,'#FFF');d.lines(404,579,['Open the exact source context before deciding what to change.', 'No general claim-verification or semantic-correctness guarantee.'],13,22,c='#DDD3EC')
    d.save('connected-home')
    d=Drawing('#FAF9FD',ink);d.rect(0,0,1100,68,ink);d.text(27,43,'DataTrust / Evidence bundle demo',21,'#FFF');d.text(785,41,'Illustrative source content',13,'#DDD3EC')
    d.text(30,118,'Declared values disagree',33,weight=500);d.text(30,151,'Record-to-document reconciliation / exact decimal comparison',14)
    d.rect(26,185,335,447,bg,12);d.text(48,223,'Source record',16,weight=600)
    for i,(t,v) in enumerate([('Entity','Example A'),('Period','2025'),('Field','revenue'),('Units','million')]):d.row(48,271+i*52,288,t,v)
    d.rect(43,496,301,89,'#FFF',8);d.text(62,528,'Record value',13);d.text(62,565,'12.4',35,violet)
    d.rect(383,185,430,447,'#FFF',8,'#DAD1E9');d.text(409,224,'Native document context',16,weight=600)
    d.text(410,280,'Example A / Annual statement',25,font='Georgia, serif')
    for i,w in enumerate([337,350,298,339,310,348,265]):d.rect(411,312+i*29,w,3,'#E7E1EF')
    d.rect(401,386,365,39,coral,2);d.text(413,413,'Revenue                     14.2 million',18)
    d.text(410,594,'Native text / supplied association',12)
    d.text(839,225,'Interpretation',16,weight=600);d.lines(839,270,['Observed discrepancy', '', 'The declared values differ.', 'Confirm entity, period,', 'units and authority.', '', 'An observation does not', 'establish which source', 'is correct.'],14,26)
    d.path('M361,540 C375,540 374,406 400,406','none',violet,3);d.text(30,674,'Exact evidence stays local. Portable reports omit source content by default.',13);d.save('connected-results')

def alongside():
    dark='#124D50';light='#D7EDE7';orange='#E86D41';ink='#10373A'
    d=Drawing('#F5F8F5',ink);d.nav(c=ink)
    d.rect(0,88,550,503,dark);d.rect(550,88,550,503,light)
    d.text(37,143,'DataTrust / Concrete',14,'#D7EDE7');d.text(587,143,'Identical inputs / one group',14,dark)
    d.lines(35,238,['Look closer.', 'See the', 'difference.'],77,80,c='#FFF',weight=500,spacing=-3)
    d.text(37,556,'Reliability is in the relationships.',19,'#FFF')
    d.text(585,208,'Compressive strength',18);d.text(583,303,'22.90',83,weight=500,spacing=-4);d.text(588,334,'Lower target in the group / MPa',14)
    d.line(588,370,1060,370,'#A4C3BA');d.text(583,461,'55.90',83,weight=500,spacing=-4);d.text(588,495,'Upper target in the group / MPa',14)
    d.rect(538,190,24,306,orange,12);d.circle(550,342,20,orange);d.line(545,342,555,342,'#FFF',2)
    d.text(37,639,'Same features can accompany different measurements.',20);d.text(37,669,'DataTrust makes the pattern visible and keeps the interpretation qualified.',15)
    d.button(843,621,'Inspect this group',dark,'#FFF',212,20);d.save('alongside-landing')
    d=Drawing('#F5F8F5',ink);d.rect(0,0,1100,72,dark);d.text(28,45,'NUMEK',24,'#FFF',weight=600);d.text(175,43,'DataTrust',17,'#FFF');d.text(677,43,'Datasets     Groups     Methods',14,'#D7EDE7')
    d.text(33,135,'A clear view of the source.',39,weight=500,spacing=-1.6);d.text(34,174,'Concrete / Regression / 1,030 rows / Local session example',15)
    d.rect(27,213,1045,62,light,6);d.text(48,251,'Source rows',17,weight=600);d.text(307,251,'8 features',14);d.text(518,251,'Target: strength_mpa',14);d.text(894,251,'Open analysis',14,weight=600)
    d.text(38,318,'Group',13,weight=600);d.text(216,318,'Evidence',13,weight=600);d.text(674,318,'Rows',13,weight=600);d.text(900,318,'Scope',13,weight=600)
    rows=[('Exact repetition','11 identical full-row groups','36','1,030 rows'),('Varying targets','9 feature-identical groups','20','1,030 rows'),('Target extremes','4 IQR review candidates','4','1,030 finite')]
    for i,(g,e,n,scope) in enumerate(rows):
        y=360+i*83;d.line(28,y-21,1072,y-21,'#BDD0CA');d.text(38,y+12,g,20);d.text(216,y+12,e,16);d.text(674,y+12,n,20);d.text(900,y+12,scope,14)
    d.rect(28,623,1044,45,dark,4);d.text(48,652,'Open any group to compare source evidence side by side.',16,'#FFF');d.save('alongside-home')
    d=Drawing('#F5F8F5',ink);d.text(28,44,'DataTrust / Concrete / Repeated inputs',23,weight=500);d.text(826,41,'Regression / No score',14)
    d.text(29,114,'One input pattern. Two observed targets.',35,weight=500,spacing=-1)
    for x,title,val,fill in [(29,'Lower target in the group','22.90',light),(565,'Upper target in the group','55.90','#E9EDE8')]:
        d.rect(x,150,507,365,fill,8);d.text(x+24,186,title,16);d.text(x+20,286,val,85,weight=500,spacing=-4);d.text(x+25,318,'Compressive strength / MPa',15)
        d.line(x+25,353,x+480,353,'#A4C3BA');d.text(x+25,391,'Input feature vector',16,weight=600);d.text(x+25,430,'Identical within this group',19);d.text(x+25,479,'4 records / 2 distinct target values',13)
    d.rect(29,538,1043,95,dark,7);d.text(50,571,'What needs investigation',18,'#FFF');d.lines(50,599,['Repeated measurements, stochastic outcomes and omitted context can explain this pattern.'],15,c='#D7EDE7')
    d.text(29,675,'Group source references: parsed rows 107, 110, 112, 115. No automatic correction is implied.',13);d.save('alongside-results')

def coverage():
    blue='#2923C7';ink='#201842';lilac='#DAD6F5';pink='#F2B5BD';white='#F8FAFD'
    d=Drawing(blue,'#FFF');d.nav(c='#FFF')
    d.lines(38,177,['Know what your', 'data is telling you.'],64,68,weight=500,spacing=-3)
    d.lines(40,294,['DataTrust brings the evidence into view.', 'Across datasets, representations and reports.'],18,27,c='#E7E4FF')
    d.button(40,357,'Explore a sample analysis',white,blue,220,20)
    d.rect(36,440,1030,216,white,18)
    d.text(62,479,'Concrete / Regression evidence',20,ink,weight=600)
    blocks=[(62,507,250,124,lilac,'1,030','finite targets'),(324,507,362,124,'#E1E9F5','25 repeated rows','11 groups / 36 participants'),(699,507,340,124,pink,'9 varying-target groups','20 participating rows')]
    for x,y,w,h,c,t,s in blocks:d.rect(x,y,w,h,c,9);d.text(x+17,y+47,t,30 if x==62 else 23,ink,weight=500);d.text(x+17,y+89,s,14,ink)
    d.text(692,375,'Evidence',20,'#FFF');d.text(812,375,'Context',20,'#FFF');d.text(917,375,'Coverage',20,'#FFF')
    d.line(737,394,737,440,'#A69DE9',2);d.line(850,394,850,440,'#A69DE9',2);d.line(960,394,960,440,'#A69DE9',2)
    d.save('coverage-landing')
    d=Drawing(white,ink);d.rect(0,0,75,700,blue);d.text(17,46,'N',30,'#FFF',weight=600)
    for y,t in [(140,'D'),(205,'E'),(270,'R'),(636,'?')]:d.circle(37,y-6,20,'#413BDB');d.text(30,y,t,16,'#FFF')
    d.text(106,44,'DataTrust',24,weight=600);d.text(830,43,'Local session / Samples',14)
    d.text(107,121,'What are you investigating?',39,weight=500,spacing=-1.8)
    d.rect(106,160,954,83,lilac,12);d.text(129,195,'Concrete',25,weight=500);d.text(129,223,'Regression / 1,030 rows / 9 columns',13);d.button(850,182,'Open analysis',blue,'#FFF',182,20)
    d.text(108,296,'Evidence available in this analysis',17,weight=600)
    for i,(name,scope,state) in enumerate([('Target distribution','1,030 finite targets','Computed'),('Exact repetition','1,030 complete rows','Computed'),('Repeated-input variation','19 input groups','Computed'),('Arithmetic relationships','Configured search scope','Bounded search')]):
        y=332+i*68;d.line(107,y+44,1059,y+44,'#DBDDE7');d.text(110,y+12,name,19);d.text(498,y+12,scope,14);d.circle(878,y+6,5,blue);d.text(895,y+12,state,13)
    d.rect(108,631,949,43,'#E9E6FA',8);d.text(129,658,'Other examples: connected evidence bundle / classification scoring',14);d.save('coverage-home')
    d=Drawing(white,ink);d.rect(0,0,75,700,blue);d.text(17,45,'N',30,'#FFF',weight=600);d.text(106,43,'DataTrust / Concrete',23,weight=500)
    d.text(105,114,'The evidence at a glance.',39,weight=500,spacing=-1.4)
    d.rect(106,148,952,45,'#E8E4F8',23);d.text(128,177,'Overview',14,blue,weight=600);d.text(291,177,'Findings',14);d.text(453,177,'Sources',14);d.text(614,177,'Methods',14);d.text(808,177,'Coverage',14)
    d.rect(106,215,578,270,lilac,14);d.text(128,253,'Target distribution / strength_mpa',18,weight=600);d.histogram(128,280,533,141,blue);d.text(129,471,'1,030 finite targets / recorded report evidence',12)
    d.rect(707,215,351,270,pink,14);d.text(730,254,'Repetition',19,weight=600);d.text(725,340,'25',83,weight=500);d.lines(731,385,['rows repeat an earlier record.', '11 groups / 36 participating rows.'],17,26);d.text(731,461,'Inspect before changing data',13)
    d.rect(106,509,952,135,'#FFFFFF',12,'#DAD6E9');d.text(129,548,'9 feature-identical groups have varying targets.',23,weight=500);d.lines(129,582,['This may reflect repeated measurements or omitted context.', 'No composite regression score is defined. Review scope and methods alongside the findings.'],15,25)
    d.save('coverage-results')

finding(); report(); connected(); alongside(); coverage()

directions=[
 dict(id='finding',name='Open the finding',short='The product starts with something worth investigating.',palette=['#F9FBFD','#14222F','#214CD8','#E54A2B','#E6EEF8'],type='Archivo Semi Condensed + Instrument Sans',layout='Asymmetric finding stage; horizontal application navigation; three reading lanes in results.',landing='An enlarged, inspectable finding is the opening visual. Scrolling opens its evidence, resolves the interpretation, then reveals modalities, methodology, local execution and exports.',home='A horizontal session workbench with clear dataset rows and one selected analysis. No service history or hosted monitoring.',results='Finding, source evidence and interpretation stay visible in adjacent lanes. The reader can open group details without losing the question.',motion='A single finding expands into its evidence lanes; selection highlights only the corresponding population. Reduced motion uses the same states without travel.',influence='AI in Design: bold-to-dense reading rhythm. Obys: typographic hierarchy. Linear: coherent selected-item detail.',risk='The headline and evidence stage must be composed together; otherwise this could regress into a conventional software hero.'),
 dict(id='report',name='A report worth reading',short='The report itself becomes the company’s most persuasive object.',palette=['#352240','#F7F5FF','#EDEA93','#C1B2CA','#ECE8F0'],type='Newsreader + Manrope',layout='Offset report leaf on a plum field; a session reading desk; chapter navigation and contextual evidence margins.',landing='A composed report opens into a continuous reading sequence: overview, finding, distribution, methods, coverage and local exports. Product evidence occupies the large visual surfaces.',home='Opened sample reports sit on a quiet reading desk with clear titles and task types. The desk represents the active local session.',results='A readable report with quiet chapter navigation, a technical evidence margin and an export toolbar. Detailed inspection remains available.',motion='The report changes scale and settles into a flat reading plane; margin annotations appear on selection. No page-curl imitation or motion in every panel.',influence='Micro: continuity between distinct material states. Siena: strong framing around the subject. AI in Design: navigable report hierarchy.',risk='The serif voice must still feel like technical software; dense evidence should use the sans face and remain quick to scan.'),
 dict(id='connected',name='Follow the evidence',short='Make the connection between an observation and its source visible.',palette=['#EEEAFB','#2A1740','#6644D8','#FCB3A0','#FAF9FD'],type='Bricolage Grotesque + Hanken Grotesk',layout='A composed source-to-finding-to-document panorama; relationship selection; exact source inspector.',landing='One real kind of DataTrust relationship carries the story: record → declared comparison → document context. Later sections show tabular, temporal, text and image evidence, private inspection and reports.',home='Sources and relationships take priority over metric cards. Sample cases include the same Concrete regression review and an explicitly synthetic connected-evidence bundle.',results='Source values and native document context sit beside the finding. Exact discrepancies, model candidates and unresolved evidence receive different treatments.',motion='Focus follows a selected connection, preserving source identity and context as the composition unfolds. The application uses direct highlight and panel resizing.',influence='Hamilton: one selection drives narrative and evidence. Hyperbolic: a technical thesis becomes a coherent graphic system. LPAS: a sustained spatial composition.',risk='The relationship graphic must stay bounded and legible. It must never become a free-floating network or imply general claim verification.'),
 dict(id='alongside',name='Put it side by side',short='Analytical precision expressed through aligned comparison.',palette=['#124D50','#D7EDE7','#F5F8F5','#E86D41','#10373A'],type='Space Grotesk + Source Sans 3',layout='A split landing composition; full-width source ledger; paired, aligned evidence panes.',landing='Two observations from the same feature-identical group establish the need for investigation. The story widens to repetition, dataset comparisons, timing and reports without calling every difference an error.',home='A source ledger organizes datasets and groups. One selection opens a paired comparison with shared labels and clear population boundaries.',results='Paired source evidence stays aligned. The Concrete example compares the lower and upper target within one observed group, while explaining legitimate causes.',motion='The dividing seam moves only to reveal a corresponding comparison. Shared axes and source identifiers stay fixed; keyboard controls provide the same states.',influence='LPAS: adjacent panels retain context. Hamilton: dim unrelated evidence rather than redrawing everything. ART+TECH: strong identities can contain disciplined statistical content.',risk='A seam or slider can become a gimmick. All essential values must remain visible and the layout must stack cleanly on narrow screens.'),
 dict(id='coverage',name='Bring the whole picture into view',short='Give evidence, context and analytical coverage equal visual weight.',palette=['#2923C7','#201842','#DAD6F5','#F2B5BD','#F8FAFD'],type='Sora + Public Sans',layout='A large composed evidence surface; compact navigation rail; a coverage-oriented analysis workspace with focused detail sheets.',landing='Evidence groups form a recognizable brand language. The selected dataset supplies meaningful numbers and a genuine distribution; later sections disclose modality scope, methods, local evidence and shareable reports.',home='The selected dataset anchors a coverage navigator. Computed diagnostics, bounded searches and unavailable evidence are distinguishable without an invented overall score.',results='A full-width analytical canvas groups related evidence; selecting a finding opens a detail sheet with source references and methods.',motion='Evidence groups reflow between overview and selected detail while retaining their identity. Application transitions are short and user-triggered.',influence='Cash App: UI primitives carry brand across scales. ART+TECH: statistical forms belong to the identity. Phantom: an overview can lead into focused content.',risk='This is closest to familiar product UI. Its composition, type scale and evidence grouping need the strongest iteration to avoid a generic card dashboard.')
]

sources=[
 dict(name='AI in Design Report 2026',by='++hellohello / Designer Fund',url='https://stateofaidesign.com/',image='ai-design-wide.jpg',other='ai-design-charts.jpg',note='The wide masthead yields to offset reading columns and then large, labeled charts. A persistent identity survives a substantial change in information density.',motion='Observed scroll transitions, navigation into the Tools chapter and chapter-level statistical graphics. The moving image band is subordinate to the report.',transfer='Use a finding or report preview at brand scale, then make it genuinely readable.',limit='Opening and Tools chapter inspected; not every chapter or case study.'),
 dict(name='Hamilton',by='Shirley Wu / The Pudding',url='https://pudding.cool/2017/03/hamilton/',image='hamilton-exploration.jpg',other='hamilton-hero.jpg',note='The same data marks carry identity and evidence. Narrative occupies one side while the selected relationship remains visible in the visualization.',motion='Observed marks reorganize after scrolling and unrelated song evidence dim around the current narrative. This takes time to settle.',transfer='Keep the source identifiers stable when a finding is selected; change emphasis instead of losing context.',limit='Scroll sequence inspected; exhaustive theme filtering and audio playback not tested. The site asks for a wide desktop viewport.'),
 dict(name='Micro',by='Reform Collective',url='https://micro.reformcollective.com/',case='https://www.reformcollective.com/work/micro',image='micro-live.jpg',other='micro-reveal.jpg',note='A strongly framed opening gives way to a dark central surface, while material and typography keep continuity. The creator case study connects brand work and interface treatment.',motion='Observed the framed landscape expand and the dark central shape emerge during scrolling. The captured pair records different scroll states.',transfer='Allow a report or evidence surface to change scale into the working product.',limit='Opening and first scroll transition inspected. No logged-in Micro interface was accessed.'),
 dict(name='Obys Experiment Space',by='Obys',url='https://experiment.obys.agency/',image='obys-space.jpg',other='obys-about.jpg',note='Oversized type creates a stable anchor for moving work. The About page retains the masthead but replaces the spatial archive with a more useful index and explanatory composition.',motion='Observed the depth-oriented moving archive and the transition to About. The index remains a usable alternative to the exhibition view.',transfer='Give the landing one orchestrated reveal; let the application use a quieter information structure.',limit='Space and About inspected. The 3D gallery itself is not proposed for the DataTrust application.'),
 dict(name='LPAS',by='Studio Naam',url='https://lpas.com/',case='https://studionaam.com/projects/lpas/',image='lpas-hero.jpg',other=None,note='Adjacent visual panels, generous left alignment and a persistent composition keep the subject in view. The content and navigation are organized by the client’s actual work.',motion='Observed the Listen/Plan/Analyze/Shape introduction widen into the homepage, plus menu opening. The first Explore click landed during the intro; later market scrolling was not verified.',transfer='Keep two source populations visible together and move the framing around them.',limit='Intro, home and menu inspected; market subpages not inspected.'),
 dict(name='Hyperbolic',by='Studio Freight',url='https://studiofreight.com/work/hyperbolic',image='hyperbolic-case.jpg',other=None,note='The creator’s case study ties the identity to a specific business argument and shows the system at different scales, from typography and physical renderings to navigation.',motion='Case-study media and scrolling inspected. Live Hyperbolic product interactions were not tested.',transfer='Derive a graphic grammar from evidence relationships, rather than adopting hardware imagery.',limit='Creator case study only. No live product or performance claims are inferred.'),
 dict(name='Cash App Brand Guidelines',by='Cash App / Index Studio',url='https://design.cash.app/',image='cash-graphic-ui.jpg',other=None,note='Small interface primitives sit beside expressive brand objects. The product’s visual vocabulary is recognizable without relying on one background or screen layout.',motion='Observed the animated overview. The Graphic UI click did not produce a confirmed route change; this capture is the overview, not a verified detail page.',transfer='Give DataTrust evidence states and source highlights a coherent visual grammar.',limit='Overview visually inspected; no Cash App account or transaction flow was opened.'),
 dict(name='ART+TECH Report 2023',by='ART+TECH Report / Awwwards discovery',url='https://www.arttechreport.com/',case='https://www.awwwards.com/sites/art-tech-report-2023',image='arttech-reading.jpg',other='arttech-home.jpg',note='The vivid opening changes into a restrained reading surface. Statistical graphics keep the rounded form vocabulary while titles, explanation and legend remain distinct.',motion='Observed the transition from blue opening composition to white statistical sections through scrolling.',transfer='Carry the identity into analytical visuals without sacrificing legends or denominators.',limit='Opening and one statistical section inspected, not the complete report.'),
 dict(name='Phantom Studios',by='Phantom',url='https://www.phantom.land/',image='phantom-home.jpg',other=None,note='The work overview is dense and panoramic, with small metadata and clear controls. A huge amount of subject matter remains visible at once.',motion='Observed the introductory title sequence settle into the project overview.',transfer='An overview may be visually rich, but DataTrust should always provide a bounded path into a selected finding.',limit='Opening and overview inspected. Pointer behavior and individual project pages were not evaluated.'),
 dict(name='Siena Film Foundation',by='Niccolò Miranda',url='https://siena.film/',image='siena-entered.jpg',other='siena-home.jpg',note='The entry mark resolves into a large, carefully framed subject, with persistent navigation and strongly differentiated metadata.',motion='Observed Enter transition and the film overview. The captured pair shows entry and post-entry states.',transfer='Make the analytical report the framed subject. The ticket shapes, film texture and cinema metaphor do not transfer.',limit='Entry and overview inspected; film detail pages not inspected.'),
 dict(name='Linear',by='Linear',url='https://linear.app/',image='linear-home.jpg',other=None,note='A large product preview has legible navigation, selected item context and a clear detail region. The product composition itself does much of the explanation.',motion='Opening and subsequent page content inspected; no authenticated workspace was accessed.',transfer='Preserve selection context and practical density when a marketing preview becomes an application screen.',limit='Secondary application-craft reference, not a proposed brand template.')
]

(ROOT/'directions.json').write_text(json.dumps(directions,indent=2))
(ROOT/'sources.json').write_text(json.dumps(sources,indent=2))

def source_card(s):
    shots=f'<a href="screenshots/{s["image"]}" target="_blank"><img src="screenshots/{s["image"]}" alt="Browser capture of {E(s["name"])}" loading="lazy"></a>'
    if s['other']: shots+=f'<a class="second" href="screenshots/{s["other"]}" target="_blank"><img src="screenshots/{s["other"]}" alt="Second observed state of {E(s["name"])}" loading="lazy"></a>'
    return f'''<article class="reference"><div class="ref-images">{shots}</div><div class="ref-copy"><h3><a href="{s['url']}" target="_blank" rel="noreferrer">{E(s['name'])} ↗</a></h3><small>{E(s['by'])}</small><p>{E(s['note'])}</p><p><b>Motion observed.</b> {E(s['motion'])}</p><p><b>NUMEK application.</b> {E(s['transfer'])}</p><details><summary>Scope of inspection</summary><p>{E(s['limit'])}</p>{f'<a href="{s["case"]}" target="_blank" rel="noreferrer">Creator / project source ↗</a>' if s.get('case') else ''}</details></div></article>'''

def direction_card(c,i):
    ident=c['id'];swatches=''.join(f'<span style="background:{v}" title="{v}"></span>' for v in c['palette'])
    figures=''.join(f'<figure><a href="studies/{ident}-{page}.svg" target="_blank"><img src="studies/{ident}-{page}.svg" alt="{E(c["name"])}: {label} composition study" loading="lazy"></a><figcaption>{label}</figcaption></figure>' for page,label in [('landing','Landing composition'),('home','Application home'),('results','Results composition')])
    return f'''<article class="direction" id="{ident}"><div class="direction-title"><div><small>Direction {i}</small><h2>{E(c['name'])}</h2><p>{E(c['short'])}</p></div><div class="swatches">{swatches}</div></div><div class="study-grid">{figures}</div><div class="direction-copy"><div><h3>One identity, three experiences</h3><p><b>Landing.</b> {E(c['landing'])}</p><p><b>Home.</b> {E(c['home'])}</p><p><b>Results.</b> {E(c['results'])}</p></div><div><h3>Craft and source</h3><p><b>Type candidates.</b> {E(c['type'])}. Studies use local system faces as visual stand-ins.</p><p><b>Motion.</b> {E(c['motion'])}</p><p><b>Influences.</b> {E(c['influence'])}</p><p class="risk"><b>Design risk.</b> {E(c['risk'])}</p></div></div></article>'''

html='''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>NUMEK — Creative direction checkpoint</title><style>
:root{font-family:Arial,sans-serif;color:#192523;background:#f5f7f6;font-synthesis:none}*{box-sizing:border-box}body{margin:0}a{color:inherit;text-underline-offset:4px}a:focus-visible,summary:focus-visible{outline:3px solid #245dd1;outline-offset:5px}header{padding:24px 4vw;display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid #cbd4cf;gap:18px}header b{font-size:27px;letter-spacing:-1.6px}header span{font-size:13px}nav{display:flex;gap:24px;font-size:14px}.intro{padding:74px 4vw 58px;display:grid;grid-template-columns:1.3fr 1fr;gap:8vw}.intro h1{font-size:clamp(40px,5.3vw,80px);font-weight:400;line-height:1.01;letter-spacing:-.055em;margin:0}.intro p{max-width:500px;font-size:17px;line-height:1.55}.notice{border-left:3px solid #486e60;padding-left:16px;font-size:14px!important}.jump{display:flex;gap:10px;flex-wrap:wrap;padding:0 4vw 42px}.jump a{background:#e4ebe7;border-radius:25px;padding:12px 18px;text-decoration:none;font-size:13px}.section-intro{padding:36px 4vw;background:#173c32;color:#fff;display:flex;justify-content:space-between;gap:40px}.section-intro h2{font-size:32px;font-weight:400;letter-spacing:-1px;margin:0}.section-intro p{max-width:650px;line-height:1.55;font-size:14px;margin:0}.direction{padding:52px 4vw 64px;border-bottom:1px solid #cbd4cf;scroll-margin-top:20px}.direction-title{display:flex;justify-content:space-between;align-items:center;gap:24px;margin-bottom:28px}.direction-title small{color:#4f665b;font-size:13px}.direction-title h2{font-size:clamp(30px,3.8vw,53px);letter-spacing:-.045em;font-weight:400;margin:12px 0}.direction-title p{font-size:17px;line-height:1.5;margin:0}.swatches{display:flex;flex-shrink:0}.swatches span{width:32px;height:44px;border:1px solid #19252318}.study-grid{display:grid;grid-template-columns:1.2fr 1fr;gap:16px}.study-grid figure{margin:0;min-width:0}.study-grid figure:first-child{grid-row:span 2;display:flex;flex-direction:column;justify-content:center;background:#e5ebe7;padding:24px}.study-grid img{display:block;width:100%;border:1px solid #152d2420}.study-grid figcaption{font-size:12px;padding:10px 0;color:#3b5548}.direction-copy{display:grid;grid-template-columns:1fr 1fr;gap:6vw;padding-top:22px}.direction-copy h3{font-size:18px;font-weight:500;letter-spacing:-.4px}.direction-copy p{font-size:14px;line-height:1.6;max-width:650px}.risk{background:#e8ece9;padding:15px}.references{padding:34px 4vw;display:grid;grid-template-columns:1fr 1fr;gap:32px}.reference{min-width:0;background:#fff;border:1px solid #d8dfda}.ref-images{display:grid;grid-template-columns:1fr;gap:4px;background:#d8dfda}.ref-images:has(.second){grid-template-columns:1fr 1fr}.ref-images img{display:block;width:100%;height:180px;object-fit:contain;background:#edf0ee}.ref-copy{padding:22px}.ref-copy h3{font-size:22px;font-weight:500;letter-spacing:-.7px;margin:0 0 9px}.ref-copy small{font-size:12px;color:#627369}.ref-copy p{font-size:13px;line-height:1.65}.ref-copy details{font-size:12px;margin-top:18px}summary{cursor:pointer}.motion{padding:36px 4vw;display:grid;grid-template-columns:1fr 1fr;gap:24px}.motion article{padding:20px;background:#e4ebe7}.motion h3{font-size:22px;font-weight:400;margin:0 0 12px}.motion p{font-size:13px;line-height:1.6}.states{display:grid;grid-template-columns:1fr 1fr;gap:8px}.states img{width:100%;display:block}.states small{display:block;margin-top:8px;font-size:11px}.comparison{padding:40px 4vw;overflow:auto}table{border-collapse:collapse;width:100%;font-size:13px;min-width:700px}th,td{padding:16px 20px 16px 0;text-align:left;vertical-align:top;border-bottom:1px solid #cbd4cf;line-height:1.5}th{font-weight:500;color:#54675c}.boundaries{padding:40px 4vw;display:grid;grid-template-columns:1fr 1fr;gap:5vw;background:#e5ebe7}.boundaries h3{font-size:24px;font-weight:400;margin-top:0}.boundaries p,.boundaries li{font-size:14px;line-height:1.7}.footer{padding:36px 4vw;background:#173c32;color:white;font-size:15px;line-height:1.6}.footer a{color:#fff}@media(max-width:760px){header{flex-wrap:wrap}nav{gap:14px}.intro,.direction-copy,.boundaries{grid-template-columns:1fr;gap:18px}.intro{padding-top:45px}.section-intro{display:block}.section-intro h2{margin-bottom:15px}.study-grid{grid-template-columns:1fr}.study-grid figure:first-child{grid-row:auto;padding:12px}.references,.motion{grid-template-columns:1fr}.direction-title{display:block}.swatches{margin-top:20px}.ref-images img{height:130px}}@media(prefers-reduced-motion:reduce){*{scroll-behavior:auto!important}}
</style></head><body><header><b>NUMEK</b><span>Visual lab v5 · Creative direction review</span><nav><a href="#directions">Directions</a><a href="#research">Research</a><a href="#comparison">Compare</a></nav></header><main><section class="intro"><h1>Five ways to make<br>the evidence<br>the experience.</h1><div><p>A visual proposal for NUMEK and DataTrust, grounded in the implemented product and direct browser research.</p><p class="notice">This is the requested creative-direction checkpoint. These are static composition studies, not runnable product prototypes or approved final identities. Open any study at full size.</p><p class="notice">The reference images are genuine browser captures. They are research material only and are not reused as NUMEK assets.</p></div></section><div class="jump">'''
html+=''.join(f'<a href="#{c["id"]}">{E(c["name"])}</a>' for c in directions)
html+='''</div><section class="section-intro" id="directions"><h2>Five directions</h2><p>Shared product truth; different composition, typography, application structure and motion. Each would become a complete landing page, a usable application home and an analytical results screen after review.</p></section>'''
html+=''.join(direction_card(c,i+1) for i,c in enumerate(directions))
html+='''<section class="section-intro" id="research"><h2>Research board</h2><p>Selected from the supplied library after inspection. Each observation separates what was actually seen from a proposed application to NUMEK. Capture sizes vary with the reference browser surface; no reference is claimed to have been exhaustively tested.</p></section><div class="references">'''
html+=''.join(source_card(s) for s in sources)
html+='''</div><section class="section-intro"><h2>Motion evidence</h2><p>Captured states show what changed. The browser interface did not expose continuous video recording, so these are state pairs rather than timing-accurate recordings. Motion observations describe only the interactions actually inspected.</p></section><div class="motion">'''
for title,one,two,labels,copy in [
 ('Micro: one composition changes state','micro-live.jpg','micro-reveal.jpg',['Opening frame','After scrolling'],'A framed scene gives way to a central dark surface. NUMEK translation: a report preview settles into its reading interface.'),
 ('Siena: framing survives the reveal','siena-home.jpg','siena-entered.jpg',['Before Enter','After Enter'],'The identity resolves into a dominant framed subject with persistent navigation. NUMEK translation: make the actual analytical report the subject; omit the entry gate.'),
 ('Obys: expressive view, readable index','obys-space.jpg','obys-about.jpg',['Space','About'],'The masthead remains recognizable while the content structure changes. NUMEK translation: marketing and investigation can have different densities within one identity.'),
 ('ART+TECH: identity into explanation','arttech-home.jpg','arttech-reading.jpg',['Opening','Statistical section'],'Expressive typography and statistical explanation share a vocabulary while their density changes. NUMEK translation: clear labels and populations survive the transition.')]:
    html+=f'<article><h3>{title}</h3><div class="states">'+''.join(f'<div><a href="screenshots/{im}" target="_blank"><img loading="lazy" src="screenshots/{im}" alt="{title}: {label}"></a><small>{label}</small></div>' for im,label in zip([one,two],labels))+f'</div><p>{copy}</p></article>'
html+='''</div><section class="section-intro" id="comparison"><h2>What actually differs</h2><p>The directions are not one shared component kit. Compare the opening subject, information architecture and result-reading behavior before judging color.</p></section><div class="comparison"><table><thead><tr><th>Direction</th><th>Landing subject</th><th>Application structure</th><th>Results behavior</th></tr></thead><tbody>'''
for c,subject,app,res in zip(directions,['An inspectable finding','A readable analytical report','An explicit evidence relationship','A paired observation','Evidence and coverage together'],['Horizontal session workbench','Report desk and reading workspace','Source/relationship selector','Full-width dataset and group ledger','Compact rail and coverage navigator'],['Three adjacent reading lanes','Report with evidence in the margin','Source record beside exact document context','Paired aligned evidence panes','Analytical overview with focused detail sheets']):
    html+=f'<tr><td><a href="#{c["id"]}">{E(c["name"])}</a></td><td>{subject}</td><td>{app}</td><td>{res}</td></tr>'
html+='''</tbody></table></div><section class="boundaries"><div><h3>Product truth in every direction</h3><p>NUMEK is the company. DataTrust is the implemented product. ConfidenceGuard and HallucinationGuard remain future directions. The prototypes will represent local execution, inspectable evidence and HTML/PDF/JSON reports.</p><p>Classification scores belong to their supported policy. No universal regression, temporal, text, image or connected-evidence score will be invented. Facts, candidates, coverage limits and unresolved context remain distinct.</p><p>The report-desk and session examples do not imply persistent history, accounts, cloud monitoring, certification or enterprise collaboration.</p></div><div><h3>Evidence and next step</h3><p>The shared Concrete values come from the existing completed regression report: 1,030 rows; 9 columns; 25 repeated rows; 11 exact groups; 36 participating rows; 9 feature-identical groups with varying targets and 20 participating rows. Its 19-bin target histogram is reproduced from that report.</p><p>The connected document example is explicitly synthetic. It illustrates an implemented interaction family without implying a customer case or general semantic guarantee.</p><p>After direction review: five independent implementations, full landing narratives, functional navigation, responsive iteration, consistent browser screenshots, and proportional verification. No production integration, commits or pushes.</p></div></section></main><footer class="footer">Ready for the single creative-direction review requested in the brief. Approve the set or name the directions you want adjusted before implementation.<br><a href="PROPOSAL.md">Concise proposal</a> · <a href="sources.json">Source and inspection record</a></footer></body></html>'''
(ROOT/'index.html').write_text(html)

overview='''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>NUMEK — five direction studies</title><style>*{box-sizing:border-box}body{margin:0;padding:28px;background:#EDF1EE;color:#192523;font-family:Arial,sans-serif}header{display:flex;justify-content:space-between;gap:28px;align-items:baseline;margin-bottom:24px}h1{font-size:29px;letter-spacing:-1.3px;font-weight:500;margin:0}header p{font-size:12px}.grid{display:grid;grid-template-columns:1fr 1fr;gap:22px}article{min-width:0}img{display:block;width:100%;border:1px solid #263E3020}h2{font-size:19px;font-weight:500;letter-spacing:-.6px;margin:10px 0 5px}p{font-size:12px;line-height:1.5;margin:0}a{color:inherit}.last{display:flex;flex-direction:column;justify-content:center;padding:30px;background:#173C32;color:white}.last h2{font-size:34px;line-height:1.08;letter-spacing:-1.2px}.last p{font-size:14px;margin-top:18px;line-height:1.7}@media(max-width:640px){.grid{grid-template-columns:1fr}header{display:block}}</style></head><body><header><h1>NUMEK / Five possible directions</h1><p>Creative-direction checkpoint · Static composition studies</p></header><main class="grid">'''
for i,c in enumerate(directions,1):
    overview+=f'<article><a href="index.html#{c["id"]}"><img src="studies/{c["id"]}-landing.svg" alt="{E(c["name"])} landing study"></a><h2>{i}. {E(c["name"])}</h2><p>{E(c["layout"])}</p></article>'
overview+='''<article class="last"><h2>One company.<br>Five ways to make<br>the product visible.</h2><p>The full board includes an application home and results composition for every direction, genuine reference captures, motion observations and the tradeoffs to assess before building.</p><p><a href="index.html">Open the complete review board</a></p></article></main></body></html>'''
(ROOT/'overview.html').write_text(overview)

ref_sheet='''<!doctype html><html lang="en"><head><meta charset="utf-8"><title>NUMEK — captured reference board</title><style>body{margin:0;padding:28px;background:#F3F5F3;font-family:Arial,sans-serif;color:#182B22}h1{font-size:29px;font-weight:400;letter-spacing:-1px;margin:0 0 8px}p{font-size:13px;margin:0 0 24px}main{display:grid;grid-template-columns:repeat(3,1fr);gap:18px}figure{margin:0;min-width:0;background:white;border:1px solid #CFD9D1}img{width:100%;aspect-ratio:16/10;object-fit:contain;background:#E4EAE5;display:block}figcaption{padding:14px;font-size:13px}small{display:block;font-size:10px;margin-top:7px;color:#526C5C;overflow-wrap:anywhere}a{color:inherit}</style></head><body><h1>Visual research / Captured from the actual sites</h1><p>Reference material only. Individual observation notes, motion states and inspection limits are in the <a href="index.html#research">complete board</a>.</p><main>'''
for s in sources:
    ref_sheet+=f'<figure><a href="{s["url"]}"><img src="screenshots/{s["image"]}" alt="{E(s["name"])} browser capture"></a><figcaption>{E(s["name"])}<small>{E(s["url"])}</small></figcaption></figure>'
ref_sheet+='</main></body></html>'
(ROOT/'reference-sheet.html').write_text(ref_sheet)

md='# NUMEK — creative direction checkpoint\n\nResearch and static composition studies only. Implementation awaits the review requested in the brief.\n\nOpen `research/index.html` for the visual board, actual browser captures, five three-screen studies and inspection limits.\n\n'
for i,c in enumerate(directions,1):
    md+=f'## {i}. {c["name"]}\n\n{c["short"]}\n\n- Structure: {c["layout"]}\n- Typeface candidates: {c["type"]}.\n- Palette: {", ".join(c["palette"])}.\n- Motion: {c["motion"]}\n- Actual influences: {c["influence"]}\n- Design risk: {c["risk"]}\n\n'
md+='''## Product and research basis

Read: repository README, master context, current state, architecture, frontend-design skill, proportional verification skill, regression engine/report contracts, cross-representation presentation/report contracts and completed Concrete report evidence. Earlier visual labs were preserved and were not used as design templates.

The current-state document contains an older image limitation that conflicts with its later M7/M9 sections; the implemented image and cross-representation modules, current README and later sections establish their actual scope. The master context has older M7 acceptance wording; current state records M1–M7 acceptance. Neither inconsistency changes this isolated exploration.

Concrete data source: `validation/regression/results/presentation_cleanup/concrete.json`. The studies use its actual aggregate counts, qualified interpretation, example target range and histogram. No analysis was rerun, and no validation evidence was changed. A source-record-to-document example is synthetic and labeled. Interface row lists represent opened session examples, not persistent report history.

Visual inspection: AI in Design (home, Tools chapter); Micro (creator case, opening and first reveal); Hamilton (opening and scroll narrative); Obys (Space and About); LPAS (intro, home, menu); Hyperbolic (creator case only); Cash App guidelines (overview); ART+TECH (Awwwards project, original opening and statistical section); Phantom (intro and overview); Siena (entry and overview); Linear (public marketing and product preview). Full per-source limits are in `sources.json`.

Awwwards website and experimental galleries were browsed for discovery; the data-visualization gallery timed out in the text browser. Individual ART+TECH work and its original site were then inspected. The library was curated, not exhaustively reviewed. No inaccessible interaction is treated as verified. The browser exposed screenshot capture but no continuous recording; before/after pairs are evidence of state, not real-time motion footage.

## Critical comparison

Open the finding gives the clearest direct product demonstration. A report worth reading has the strongest report-sharing identity but must preserve technical speed. Follow the evidence has the most specific connection to M9 and source inspection but must also handle ordinary tabular analysis well. Put it side by side is strongest for investigation and comparisons but needs a careful narrow-screen fallback. Bring the whole picture into view offers the broadest product system and is most at risk of looking conventional without composition refinement.

These are hypotheses illustrated by composition studies, not claims of achieved launch quality. All five still need complete landing pages, runnable interfaces, actual motion, responsive refinement and browser testing after review.

## Review request

Approve these five directions as the exploration set, or identify changes to make before building all five. This pause comes directly from section 10 of the user's brief: “Pause for my review at this single creative-direction checkpoint.” No skill adds an approval stage.
'''
(ROOT/'PROPOSAL.md').write_text(md)
