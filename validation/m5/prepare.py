"""Pinned, loss-conscious transformations of the approved public M5 corpus."""
from pathlib import Path
import csv
from datetime import datetime,timedelta
from decimal import Decimal,ROUND_HALF_EVEN
import hashlib
import io
import json
import shutil
import zipfile
import xml.etree.ElementTree as ET
import pyarrow as pa
import pyarrow.parquet as pq
from datatrust import *
from validation.m5.download import digest
ROOT=Path(__file__).parent;RAW=ROOT/'data/raw';OUT=ROOT/'data/prepared';MANIFESTS=ROOT/'manifests'
TRANSFORM='m5_public_corpus_v1'


def write_spec(name,inputs,**kw):
    spec=TemporalAuditSpec(tuple(inputs),dataset_name=name,**kw).to_dict()
    for x in spec['inputs']:x['source']['path']='../data/prepared/'+Path(x['source']['path']).name
    (MANIFESTS/(name+'.json')).write_text(json.dumps(spec,indent=2)+'\n')
    return spec


def analytical(name,path,temporal,task=None):return TemporalInputSpec(name,TemporalSourceSpec(str(path),'parquet' if path.suffix=='.parquet' else 'csv'),temporal,task=task or TaskSpec('dataset_profile'))


def run():
    OUT.mkdir(exist_ok=True,parents=True);MANIFESTS.mkdir(exist_ok=True);entries=[]
    pins=json.loads((RAW/'manifest.json').read_text())
    for name,record in pins.items():
        if digest(RAW/name)!=record['sha256']:raise ValueError('Pinned raw bytes changed: '+name)
    bike=ROOT.parent/'regression/data/raw/bike.zip'
    with zipfile.ZipFile(bike) as z:
        raw=z.read('hour.csv');rows=csv.DictReader(io.StringIO(raw.decode()))
        p=OUT/'bike.csv';n=0
        with p.open('w',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=['time','cnt','casual','registered','temp','hum','weathersit']);writer.writeheader()
            for row in rows:
                writer.writerow({'time':row['dteday']+'T'+row['hr'].zfill(2)+':00:00',**{k:row[k] for k in writer.fieldnames[1:]}});n+=1
    ts=TemporalSpec(ClockSpec('time',timezone='America/New_York'),tuple(MeasurementSpec(x,representation='categorical' if x=='weathersit' else 'quantitative',unit='count' if x in {'cnt','casual','registered'} else None) for x in writer.fieldnames[1:]),schedule=ScheduleSpec('fixed',cadence_ns='3600000000000',anchor='2011-01-01T00:00:00-05:00'))
    write_spec('bike',[analytical('bike',p,ts)],purpose='Hourly observations; timezone is an explicit validation assumption, unresolved DST folds stay unresolved. Components are not declared historically available.')
    entries.append({'name':'bike','rows':n,'raw_sha256':digest(bike),'member_sha256':hashlib.sha256(raw).hexdigest(),'license':'UCI CC BY 4.0','source':'https://archive.ics.uci.edu/dataset/275/bike+sharing+dataset','notes':'Combines supplied dteday and hr without repairing gaps or repeated local hours. Washington DC timezone is an explicit analysis declaration.'})
    # UCI distributes an outer archive containing the original station archive.
    with zipfile.ZipFile(RAW/'beijing.zip') as outer:
        member=next(x for x in outer.namelist() if x.endswith('.zip'));inner=outer.read(member)
    p=OUT/'beijing.csv';n=0;members={}
    with zipfile.ZipFile(io.BytesIO(inner)) as z,p.open('w',newline='') as f:
        writer=csv.writer(f);writer.writerow(['time','station','PM2.5','PM10','TEMP','PRES','DEWP','RAIN','WSPM','wd'])
        for member in sorted(x for x in z.namelist() if x.endswith('.csv')):
            raw=z.read(member);members[member]=hashlib.sha256(raw).hexdigest()
            for row in csv.DictReader(io.StringIO(raw.decode())):
                time=f"{int(row['year']):04d}-{int(row['month']):02d}-{int(row['day']):02d}T{int(row['hour']):02d}:00:00"
                writer.writerow([time]+[row[x] for x in writer.fieldnames[1:]] if hasattr(writer,'fieldnames') else [time,row['station']]+[row[x] for x in ['PM2.5','PM10','TEMP','PRES','DEWP','RAIN','WSPM','wd']]);n+=1
    ts=TemporalSpec(ClockSpec('time',timezone='Asia/Shanghai'),tuple(MeasurementSpec(x,representation='categorical' if x=='wd' else 'quantitative',unit='ug/m3' if x in {'PM2.5','PM10'} else None) for x in ['PM2.5','PM10','TEMP','PRES','DEWP','RAIN','WSPM','wd']),entity_columns=('station',),schedule=ScheduleSpec('fixed',cadence_ns='3600000000000',anchor='2013-03-01T00:00:00+08:00'),active_intervals=(ActiveInterval('2013-03-01T00:00:00+08:00','2017-03-01T00:00:00+08:00'),))
    write_spec('beijing',[analytical('beijing',p,ts)],purpose='Full twelve-station hourly panel. Supplied NA measurements remain missing cells, distinct from absent records.')
    entries.append({'name':'beijing','rows':n,'members':members,'license':'UCI CC BY 4.0','source':'https://archive.ics.uci.edu/dataset/501/beijing+multi+site+air+quality+data','notes':'Stable station/member order. Constructs explicit calendar clock from year/month/day/hour; NA is retained under declared CSV missing-token policy.'})
    # Stream the 370-client archive into flat typed Parquet without a full frame.
    p=OUT/'electricity.parquet';n=0;writer=None
    with zipfile.ZipFile(RAW/'electricity.zip') as z:
        member=next(x for x in z.namelist() if x.endswith('LD2011_2014.txt') and not x.startswith('__MACOSX'))
        with z.open(member) as binary:
            reader=csv.reader(io.TextIOWrapper(binary,encoding='utf-8'),delimiter=';');headers=next(reader);headers[0]='time';batch=[]
            def flush(batch):
                nonlocal writer
                arrays={'time':pa.array([datetime.fromisoformat(row[0]) for row in batch],type=pa.timestamp('s'))}
                arrays.update({name:pa.array([float(row[i].replace(',','.')) for row in batch],type=pa.float64()) for i,name in enumerate(headers[1:],1)})
                table=pa.table(arrays)
                if writer is None:writer=pq.ParquetWriter(p,table.schema,compression='zstd',version='2.6')
                writer.write_table(table)
            for row in reader:
                batch.append(row);n+=1
                if len(batch)==1024:flush(batch);batch=[]
            if batch:flush(batch)
            if writer:writer.close()
    ts=TemporalSpec(ClockSpec('time',kind='local_datetime',encoding='native'),tuple(MeasurementSpec(x,unit='kW') for x in headers[1:]))
    write_spec('electricity',[analytical('electricity',p,ts)],purpose='All 370 clients. Portuguese civil labels remain unresolved local times: DST spring zeros, autumn aggregated hours and pre-creation zero padding are retained, with no pristine-instant or outage assumption.')
    entries.append({'name':'electricity','rows':n,'measurements':len(headers)-1,'license':'UCI CC BY 4.0','source':'https://archive.ics.uci.edu/dataset/321/electricityloaddiagrams20112014','notes':'Semicolon/decimal-comma source converted to flat Parquet doubles, native naive timestamps. Source zeros and aggregated hours are not cleaned or interpreted as defects.'})
    # Stream the XLSX XML; retain invoice-line records and exact customer/product tokens.
    with zipfile.ZipFile(RAW/'retail.zip') as outer:xlsx=outer.read(next(x for x in outer.namelist() if x.endswith('.xlsx')))
    ns={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'};p=OUT/'retail.csv';n=0
    with zipfile.ZipFile(io.BytesIO(xlsx)) as z:
        strings=[''.join(x.itertext()) for x in ET.fromstring(z.read('xl/sharedStrings.xml')).findall('s:si',ns)]
        with z.open('xl/worksheets/sheet1.xml') as xml,p.open('w',newline='') as f:
            writer=csv.writer(f);writer.writerow(['time','InvoiceNo','StockCode','Quantity','UnitPrice','CustomerID','Country'])
            for event,row in ET.iterparse(xml,events=('end',)):
                if row.tag!='{'+ns['s']+'}row':continue
                vals=['']*8
                for cell in row.findall('s:c',ns):
                    col=ord(cell.attrib['r'][0])-65;v=cell.find('s:v',ns)
                    if v is None:continue
                    vals[col]=strings[int(v.text)] if cell.attrib.get('t')=='s' else v.text
                if row.attrib.get('r')!='1':
                    dt=datetime(1899,12,30)+timedelta(minutes=int((Decimal(vals[4])*1440).to_integral_value(rounding=ROUND_HALF_EVEN)));writer.writerow([dt.isoformat(timespec='seconds'),vals[0],vals[1],vals[3],vals[5],vals[6],vals[7]]);n+=1
                row.clear()
    ts=TemporalSpec(ClockSpec('time',kind='local_datetime'),(MeasurementSpec('Quantity',unit='items'),MeasurementSpec('UnitPrice',unit='GBP'),MeasurementSpec('Country',representation='categorical')),observation='event',entity_columns=('CustomerID',))
    write_spec('retail',[analytical('retail',p,ts)],purpose='Invoice-line events without an expected purchase cadence. Source-local minute labels, cancellations, negative quantities and missing customer keys remain visible.')
    entries.append({'name':'retail','rows':n,'xlsx_sha256':hashlib.sha256(xlsx).hexdigest(),'license':'UCI CC BY 4.0','source':'https://archive.ics.uci.edu/dataset/352/online+retail','notes':'XLSX 1900 calendar converted by exact-decimal nearest-minute rounding to displayed source minute labels; this convention is explicit. No timezone is inferred. Cancellation codes and literal customer identifiers retained.'})
    # Official archived ALFRED presentation contains these vintage columns, page 13.
    # This is a documented archival extract, not a complete revision history or live API feed.
    history=OUT/'alfred_history.csv';history.write_text('observation_date,value,vintage_date\n'+''.join(f'2010-01-01,{v},{d}\n' for d,v in [('2010-04-30','3.2'),('2010-05-27','3.0'),('2010-06-25','2.7'),('2010-07-30','3.7'),('2010-08-27','3.7')])+''.join(f'2010-04-01,{v},{d}\n' for d,v in [('2010-07-30','2.4'),('2010-08-27','1.6')]))
    p=OUT/'alfred.csv';p.write_text('observation_date,value,cutoff\n2010-01-01,3.7,2010-08-27\n2010-04-01,1.6,2010-08-27\n')
    clock=ClockSpec('observation_date',kind='civil_date');ts=TemporalSpec(clock,(MeasurementSpec('value',unit='percent annualized change',meaning='GDPC1_PCA'),),observation_keys=('observation_date',))
    h=FeatureHistorySpec('archived-vintages','alfred','history',('value',),('observation_date',),('observation_date',),{'value':'value'},ClockSpec('vintage_date',kind='civil_date'),ClockSpec('cutoff',kind='civil_date'))
    write_spec('alfred',[analytical('alfred',p,ts),TemporalInputSpec('history',TemporalSourceSpec(str(history)),role='history')],histories=(h,),purpose='Official archived five-vintage extract. Availability is known only at civil-day granularity; no intraday or complete-history assurance.')
    entries.append({'name':'alfred','rows':2,'history_rows':7,'license':'Published BEA GDP figures transcribed as facts from the cited official ALFRED archive; presentation reuse rights not asserted.','source':'https://alfred.stlouisfed.org/docs/alfred_capturing_data.pdf','notes':'Manual transcription of GDPC1_PCA vintage table from official archived PDF. Missing earlier-quarter vintage entries omitted as absence, not known missing. Release-day uncertainty preserved; completeness unknown.'})
    for entry in entries:
        files=[p for p in OUT.iterdir() if p.stem==entry['name'] or p.stem.startswith(entry['name']+'_')]
        entry.update(transform=TRANSFORM,prepared={p.name:{'sha256':digest(p),'bytes':p.stat().st_size} for p in files},manifest_sha256=digest(MANIFESTS/(entry['name']+'.json')))
    (OUT/'manifest.json').write_text(json.dumps({'transform':TRANSFORM,'pyarrow':pa.__version__,'datasets':entries},indent=2)+'\n')
    print(json.dumps([{'name':x['name'],'rows':x['rows']} for x in entries]),flush=True)
if __name__=='__main__':run()
