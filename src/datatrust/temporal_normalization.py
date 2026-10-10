"""Exact clocks and local scalar ingestion; no inferred temporal roles."""
from dataclasses import asdict, dataclass, replace
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import hashlib
from importlib import resources
import json
from pathlib import Path
import re
from zoneinfo import ZoneInfo
import pandas as pd
from datatrust.contracts import AnalysisConfig, CsvParseOptions, TaskSpec
from datatrust.ingestion import source_signature, verify_source
from datatrust.scalable import Relation, ingest, fail
from datatrust.temporal_contracts import ClockSpec

DAY = 86_400_000_000_000
EPOCH = datetime(1970,1,1)
ISO = re.compile(r'^(\d{4}-\d{2}-\d{2})(?:[T ](\d{2}:\d{2}:\d{2})(?:\.(\d+))?(Z|[+-]\d{2}:\d{2})?)?$')
ZONE_CACHE = {}


def zone(name):
    if name not in ZONE_CACHE:
        if not isinstance(name,str) or not re.fullmatch(r'[A-Za-z0-9_+\-/]+',name) or '..' in name: raise ValueError('Invalid IANA timezone name.')
        path=resources.files('tzdata.zoneinfo').joinpath(*name.split('/'))
        try:
            raw=path.read_bytes()
            with path.open('rb') as stream: z=ZoneInfo.from_file(stream,key=name)
        except (OSError,ValueError) as exc: raise ValueError(f'Unknown packaged IANA timezone: {name}') from exc
        ZONE_CACHE[name]=(z,hashlib.sha256(raw).hexdigest())
    return ZONE_CACHE[name][0]


def timezone_provenance():
    import tzdata
    return {'package':'tzdata','version':tzdata.__version__,'zones':{k:v[1] for k,v in sorted(ZONE_CACHE.items())}}


def wall_ticks(dt, fraction=0):
    d=dt.replace(tzinfo=None)-EPOCH
    return (d.days*86400+d.seconds)*10**9+dt.microsecond*1000+fraction


def parse_clock(value, spec, zone_value=None, fold_value=None, native=None):
    """Return (exact tick, state, precision, possible_end). No float timestamps."""
    if value is None:return None,'missing',None,None
    text=str(value)
    if spec.encoding=='native' and native:
        kind,unit,tz=native
        if kind=='timestamp':
            try: tick=int(text)*{'s':10**9,'ms':10**6,'us':1000,'ns':1}[unit]
            except (ValueError,KeyError):return None,'malformed',None,None
            if tick<wall_ticks(datetime(1,1,1)) or tick>wall_ticks(datetime(9999,12,31,23,59,59,999999),999):return None,'out_of_range',unit,None
            if tz:
                if spec.kind!='instant':return None,'incompatible_native_clock',unit,None
                return tick,'valid',unit,None
            # A native timestamp without zone remains a wall clock, unless resolved explicitly.
            try: dt=EPOCH+timedelta(microseconds=tick//1000);frac=tick%1000
            except OverflowError:return None,'out_of_range',unit,None
            if spec.kind=='local_datetime':return tick,'valid',unit,None
            return resolve_local(dt,frac,spec,zone_value,fold_value,unit)
        if kind=='date':
            try: d=date(1970,1,1)+timedelta(days=int(text))
            except (ValueError,OverflowError):return None,'out_of_range','day',None
            text=d.isoformat()
    if spec.encoding=='epoch':
        try:
            number=Decimal(text);tick=number*{'s':10**9,'ms':10**6,'us':1000,'ns':1}[spec.epoch_unit]
            if not tick.is_finite() or tick!=tick.to_integral_value():return None,'unsupported_precision',spec.epoch_unit,None
            tick=int(tick)
            if tick<wall_ticks(datetime(1,1,1)) or tick>wall_ticks(datetime(9999,12,31,23,59,59,999999),999):return None,'out_of_range',spec.epoch_unit,None
        except (InvalidOperation,ValueError):return None,'malformed',None,None
        if spec.kind!='instant':return None,'incompatible_epoch_clock',None,None
        return tick,'valid',spec.epoch_unit,None
    try:
        if spec.encoding=='format':
            frac=0;precision='second';parse_text=text
            if '%f' in spec.format:
                fractions=list(re.finditer(r'[.,](\d+)',text))
                if fractions:
                    match=fractions[-1];digits=match.group(1)
                    if len(digits)>9:return None,'unsupported_precision',None,None
                    nanos=int(digits.ljust(9,'0'));frac=nanos%1000;precision='ns' if len(digits)>6 else 'us'
                    parse_text=text[:match.start(1)]+digits[:6]+text[match.end(1):]
            dt=datetime.strptime(parse_text,spec.format)
            is_date=all(x not in spec.format for x in ('%H','%I','%M','%S'))
        else:
            match=ISO.fullmatch(text)
            if not match:return None,'malformed',None,None
            d,t,f,offset=match.groups();is_date=t is None
            if t and t[-2:]=='60':return None,'leap_second',None,None
            if f and len(f)>9:return None,'unsupported_precision',None,None
            ns=int((f or '').ljust(9,'0') or '0');frac=ns%1000
            dt=datetime.fromisoformat(d+('T'+t if t else '')+('.'+str(ns//1000).zfill(6) if t else '')+(('+00:00' if offset=='Z' else offset) if offset else ''))
            precision='day' if is_date else 'ns' if f and len(f)>6 else 'us' if f else 'second'
        if is_date:
            days=(dt.date()-date(1970,1,1)).days
            if spec.kind=='civil_date':return days,'valid','day',None
            if spec.kind=='local_datetime':return days*DAY,'date_interval','day',(days+1)*DAY
            if spec.date_convention!='start_of_day':return days*DAY,'date_interval','day',(days+1)*DAY
        if spec.kind=='civil_date':return None,'incompatible_date_clock',precision,None
        if dt.tzinfo:
            if spec.kind!='instant':return None,'unexpected_offset',precision,None
            return wall_ticks(dt.astimezone(timezone.utc),frac),'valid',precision,None
        if spec.kind=='local_datetime':return wall_ticks(dt,frac),'valid',precision,None
        return resolve_local(dt,frac,spec,zone_value,fold_value,precision)
    except (ValueError,OverflowError):return None,'malformed',None,None


def resolve_local(dt,frac,spec,zone_value,fold_value,precision):
    name=spec.timezone or zone_value
    if not name:return None,'unresolved_timezone',precision,None
    try:z=zone(str(name))
    except ValueError:return None,'invalid_timezone',precision,None
    candidates=[]
    for fold in (0,1):
        aware=dt.replace(tzinfo=z,fold=fold);utc=aware.astimezone(timezone.utc)
        if utc.astimezone(z).replace(tzinfo=None)==dt:
            tick=wall_ticks(utc,frac)
            if tick not in [x[1] for x in candidates]:candidates.append((fold,tick))
    if not candidates:return None,'nonexistent_local_time',precision,None
    if len(candidates)==1:return candidates[0][1],'valid',precision,None
    if spec.fold_column:
        if str(fold_value) not in {'0','1'}:return None,'invalid_fold',precision,None
        return dict(candidates)[int(fold_value)],'valid',precision,None
    if spec.ambiguity=='unresolved':return None,'ambiguous_local_time',precision,None
    return (min if spec.ambiguity=='earlier' else max)(x[1] for x in candidates),'valid',precision,None


def literal_tick(value,spec):
    # Contract endpoints are ISO civil/instant strings, except explicitly declared epochs.
    endpoint=replace(spec,column='_literal',encoding='iso' if spec.encoding in {'native','format'} else spec.encoding,format=None)
    tick,state,_,_=parse_clock(value,endpoint)
    if state!='valid':raise ValueError(f'Unresolved interval/assessment endpoint {value!r}: {state}.')
    return tick


def interval_ticks(interval,clock):
    start=literal_tick(interval.start,clock);end=literal_tick(interval.end,clock)
    if end<start:raise ValueError('Interval endpoints are reversed.')
    return start+(interval.closed in {'right','neither'}),end+(interval.closed in {'right','both'})


def all_clocks(spec,item):
    clocks=[]
    if item.temporal:clocks.append(item.temporal.clock)
    for a in spec.availability:
        if a.source_id==item.id:clocks.extend(x for x in (a.cutoff,a.availability,a.source_clock) if x)
    for h in spec.histories:
        if h.source_id==item.id:clocks.extend(x for x in (h.cutoff,h.source_observation_clock) if x)
        if h.history_source_id==item.id:clocks.extend(x for x in (h.availability,h.history_observation_clock) if x)
    for m in spec.maturity:
        if m.source_id==item.id:clocks.extend(x for x in (m.availability,m.source_clock) if x)
    for f in spec.evaluation.folds:
        if item.id in {f.train_source_id,f.evaluation_source_id}:clocks.extend(x for x in (f.origin,f.label_start,f.label_end) if x)
    for source in spec.inputs:
        if source.temporal and source.temporal.schedule.source_id==item.id:
            clocks.append(replace(source.temporal.clock,column=source.temporal.schedule.time_column))
    return tuple(dict((json.dumps(asdict(x),sort_keys=True),x) for x in clocks).values())


def lexical_columns(spec,item):
    cols=set(item.task.group_columns)|{k for k,v in item.config.features.semantic_types.items() if v=='identifier'}
    annotations=item.config.annotations
    if annotations:
        for target in item.task.target_names:
            status=annotations.per_target.get(target,annotations.default).status_column
            if status:cols.add(status)
    for c in all_clocks(spec,item):cols.update(x for x in (c.column,c.timezone_column,c.fold_column) if x)
    if item.temporal:
        cols.update(item.temporal.entity_columns+item.temporal.observation_keys)
        if item.temporal.measurement_column:cols.add(item.temporal.measurement_column)
    for h in spec.histories:
        if h.source_id==item.id:cols.update(h.observation_keys);cols.update([h.selected_revision_id_column] if h.selected_revision_id_column else [])
        if h.history_source_id==item.id:cols.update(h.history_keys);cols.update(x for x in (h.revision_id_column,h.tie_order_column,h.state_column) if x)
    for fold in spec.evaluation.folds:
        if item.id in {fold.train_source_id,fold.evaluation_source_id}:cols.update(fold.group_columns)
    for source in spec.inputs:
        if source.temporal and source.temporal.schedule.source_id==item.id:
            s=source.temporal.schedule;cols.update(s.entity_columns);cols.update(x for x in (s.measurement_column,s.collection_status_column) if x)
    return tuple(sorted(cols))


def parquet_preflight(path,limits):
    try:import pyarrow as pa;import pyarrow.parquet as pq
    except ImportError as exc:raise ValueError('Parquet requires the optional datatrust[parquet] dependency.') from exc
    path=Path(path)
    with path.open('rb') as f:
        if path.stat().st_size<12:raise ValueError('Invalid Parquet file.')
        f.seek(-8,2);footer=f.read(8)
        if footer[4:]!=b'PAR1':raise ValueError('Encrypted or invalid Parquet footer is unsupported.')
        if int.from_bytes(footer[:4],'little')>limits.parquet_metadata_bytes:fail('Parquet metadata exceeds configured decoding cap.','parquet_metadata_limit')
    reader=pq.ParquetFile(path,pre_buffer=False,memory_map=False,thrift_string_size_limit=limits.parquet_metadata_bytes,thrift_container_size_limit=limits.parquet_metadata_bytes)
    schema=reader.schema_arrow
    if len(set(schema.names))!=len(schema.names):raise ValueError('Parquet columns must have unique names.')
    for f in schema:
        t=f.type
        if not (pa.types.is_null(t) or pa.types.is_boolean(t) or pa.types.is_integer(t) or pa.types.is_floating(t) or pa.types.is_string(t) or pa.types.is_large_string(t) or pa.types.is_date(t) or pa.types.is_timestamp(t) or pa.types.is_decimal(t)):
            reader.close();raise ValueError(f'Unsupported flat scalar Parquet column {f.name}: {t}.')
    raw=reader.metadata
    uncompressed=sum(raw.row_group(g).column(c).total_uncompressed_size for g in range(raw.num_row_groups) for c in range(raw.num_columns))
    meta={'rows':raw.num_rows,'columns':raw.num_columns,'row_groups':raw.num_row_groups,'uncompressed_chunk_bytes':uncompressed,'serialized_footer_bytes':raw.serialized_size,'schema':str(schema),'decoder_peak_is_bounded':False}
    return reader,meta


def source_plan(inputs,limits,options):
    sources=[];decoded=0
    for item in inputs:
        size=Path(item.source.path).stat().st_size
        record={'source_id':item.id,'compressed_bytes':size,'format':item.source.format}
        if item.source.format=='parquet':
            reader,meta=parquet_preflight(item.source.path,limits);reader.close();record.update(meta);estimate=meta['uncompressed_chunk_bytes']*3
        else:estimate=size*6
        decoded+=estimate;sources.append(record)
    snapshots=sum(x['compressed_bytes'] for x in sources)
    projected_cells=sum(x.get('rows',0)*(len(item.temporal.measurements) if item.temporal and item.temporal.layout=='wide' else 1 if item.temporal else 0) for x,item in zip(sources,inputs))
    cell_workspace=projected_cells*160
    return {'sources':sources,'projected_known_measurement_cells':projected_cells,
        'estimated_peak_workspace_bytes':max(512*1024**2,snapshots+max(decoded,cell_workspace)+options.result_bytes+256*1024**2),
        'phase_estimates':{'snapshots':{'workspace_bytes':snapshots},'ingestion':{'workspace_bytes':decoded,'decoded_retention_target':options.batch_bytes,'memory_bytes':options.memory_bytes+options.batch_bytes*3},'normalization_required_sorts':{'workspace_bytes':cell_workspace,'memory_bytes':options.memory_bytes},'history_evaluation_behavior':{'workspace_bytes':None,'meaning':'Reassess actual cardinality, skew, requested populations and sort/join coexistence.'},'publication':{'workspace_bytes':options.result_bytes}},
        'upper_bound':False,'assumptions':['CSV row counts and variable widths are unknown before ingestion.','Native decoder allocations can precede batch checks.','Sort/join coexistence and cell expansion are reassessed using actual cardinalities.']}



@dataclass(frozen=True)
class _SourceDescriptor:
    id: str
    role: str
    dataset: object
    task: object
    config: object


def ingest_temporal(work,spec,item,limits):
    keys=lexical_columns(spec,item)
    if item.source.format=='csv':
        missing=dict(item.source.parsing.column_missing_policies)
        for clock in all_clocks(spec,item):missing.setdefault(clock.column,{'missing_policy':item.source.parsing.missing_policy,'na_values':item.source.parsing.na_values})
        overrides={**item.source.parsing.column_types,**{k:'string' for k in keys}}
        if item.task.kind=='regression':
            for target in item.task.target_names:overrides.setdefault(target,'numeric')
        # Explicit temporal/key declarations always preserve tokens before numeric inference.
        config=AnalysisConfig(parsing=replace(item.source.parsing,column_types=overrides,column_missing_policies=missing),limits=item.config.limits)
        stage=_SourceDescriptor(item.id,item.role,item.source,TaskSpec('dataset_profile',feature_columns=()),config)
        r=ingest(work,stage,keys);r.task=item.task;r.config=item.config;r.native={};r.decimals={}
        apply_base_roles(r,item)
        headers=[x['original'] for x in r.parsing['header_mapping']]
        if len(set(headers))!=len(headers):raise ValueError('Temporal CSV headers must have unique source names.')
        return r
    import pyarrow as pa
    path=Path(item.source.path).resolve();signature=source_signature(path)
    snapshot=path if path in work.owned_snapshots else work.root/('source-'+item.id+'.parquet');digest=hashlib.sha256()
    with path.open('rb') as original:
        owned=None if snapshot==path else snapshot.open('xb')
        try:
            for block in iter(lambda:original.read(1024**2),b''):
                digest.update(block)
                if owned:owned.write(block)
        finally:
            if owned:owned.close()
    source={'signature':signature,'sha256':digest.hexdigest(),'bytes':signature[2],'filename':item.source.source_filename or path.name}
    verify_source(path,source,'snapshot');reader,meta=parquet_preflight(snapshot,limits)
    try:
        names=tuple(reader.schema_arrow.names)
        if len(names)>work.options.max_columns or meta['rows']>work.options.max_rows:fail('Parquet row/column limit exceeded.')
        if set(keys)-set(names):raise ValueError('Unknown temporal/key columns: '+', '.join(sorted(set(keys)-set(names))))
        table='p'+str(len(work.con.execute('SHOW TABLES').fetchall()));raw=table+'_raw';cols=['c'+str(i) for i in range(len(names))]
        work.con.execute(f'CREATE TABLE {raw}(_row BIGINT,'+','.join(c+' VARCHAR' for c in cols)+')')
        native={};types={}
        def scalar_storage(f):
            t=f.type
            if f.name in keys or pa.types.is_timestamp(t) or pa.types.is_date(t):return 'VARCHAR'
            if pa.types.is_null(t) and item.task.kind=='regression' and f.name in item.task.target_names:return 'DOUBLE'
            return 'VARCHAR' if pa.types.is_string(t) or pa.types.is_large_string(t) or pa.types.is_decimal(t) or pa.types.is_null(t) else 'BOOLEAN' if pa.types.is_boolean(t) else 'UBIGINT' if pa.types.is_unsigned_integer(t) else 'BIGINT' if pa.types.is_integer(t) else 'DOUBLE'
        for f in reader.schema_arrow:
            types[f.name]=scalar_storage(f)
            if pa.types.is_timestamp(f.type):native[f.name]=('timestamp',f.type.unit,f.type.tz)
            elif pa.types.is_date(f.type):native[f.name]=('date','day',None)
        ordinal=0;peak_batch=0;batch_rows=max(1,min(65536,int(work.options.batch_bytes//max(128,len(names)*64,3*meta['uncompressed_chunk_bytes']/max(1,meta['rows'])))))
        # One iterator per row group, restarted at a smaller size for subsequent groups.
        for group in range(reader.num_row_groups):
            for batch in reader.iter_batches(batch_size=batch_rows,row_groups=[group],use_threads=False):
                peak_batch=max(peak_batch,batch.nbytes)
                if batch.nbytes>limits.decoded_batch_bytes:fail('Returned Parquet batch exceeds decoded-byte ceiling; native allocations may precede this check.','decoded_batch_limit')
                columns={};frame=None
                for i,f in enumerate(reader.schema_arrow):
                    array=batch.column(i);t=f.type
                    if pa.types.is_timestamp(t):native[f.name]=('timestamp',t.unit,t.tz);values=array.cast(pa.int64()).to_pylist()
                    elif pa.types.is_date(t):native[f.name]=('date','day',None);values=array.cast(pa.int32() if pa.types.is_date32(t) else pa.int64()).to_pylist();values=[None if x is None else x if pa.types.is_date32(t) else x//86400000 for x in values]
                    else:values=array.to_pylist()
                    if pa.types.is_decimal(t):values=[None if x is None else (format(x,'f').rstrip('0').rstrip('.') if '.' in format(x,'f') else format(x,'f')) for x in values]
                    values=[None if x is None else str(x) for x in values]
                    if any(len(x.encode('utf-8'))>work.options.max_record_bytes for x in values if x is not None):fail('Parquet scalar exceeds configured size.','record_limit')
                    columns[cols[i]]=values
                    types[f.name]=scalar_storage(f)
                    del values,array
                columns['_row']=range(ordinal+1,ordinal+batch.num_rows+1);frame=pd.DataFrame(columns)[['_row']+cols]
                work.con.register('_parquet_batch',frame)
                try:work.con.execute(f'INSERT INTO {raw} SELECT * FROM _parquet_batch')
                finally:work.con.unregister('_parquet_batch')
                ordinal+=batch.num_rows;observed=batch.nbytes/max(1,batch.num_rows)
                batch_rows=max(1,min(batch_rows,int(work.options.batch_bytes/max(1,observed*3))))
                del columns,frame,batch
                work.check(item.id+': Parquet ingestion')
        expressions=['_row']+[f'CAST({c} AS {types[n]}) AS {c}' for n,c in zip(names,cols)]
        work.con.execute(f'CREATE TABLE {table} AS SELECT '+','.join(expressions)+f' FROM {raw}');work.con.execute(f'DROP TABLE {raw}')
        parsing={'policy':'temporal_parquet_scalar_v1','typed_nulls':True,'native_clocks':native,'physical_schema':str(reader.schema),'logical_schema':meta['schema'],'metadata':meta,'largest_returned_batch_bytes':peak_batch,'fingerprint':hashlib.sha256(json.dumps({'schema':meta['schema'],'native':native},sort_keys=True).encode()).hexdigest()}
        r=Relation(item.id,item.role,table,names,types,{n:'typed_parquet' for n in names},ordinal,source,parsing,item.task,item.config,(),(),());r.native=native;r.decimals={f.name:(f.type.precision,f.type.scale) for f in reader.schema_arrow if pa.types.is_decimal(f.type)}
        apply_base_roles(r,item)
        return r
    finally:reader.close()


def apply_base_roles(r,item):
    from datatrust.annotations import effective_policy,resolve_roles
    roles=resolve_roles(r.names,item.task,item.config)
    r.task,r.config,_,base=effective_policy(r.names,item.task,item.config)
    r.features=tuple(roles['features']);r.metadata=tuple(roles['metadata'])
    r.parsing['base_task_policy']=base or {'classification':'classification_legacy_2026_08_13','regression':'regression_scalar_v1','dataset_profile':'dataset_profile_v1'}.get(r.task.kind,r.task.kind)


def normalize_clock(work,r,spec):
    if not hasattr(r,'clocks'):r.clocks={}
    key=json.dumps(asdict(spec),sort_keys=True)
    if key in r.clocks:return r.clocks[key]
    cols=[spec.column]+([spec.timezone_column] if spec.timezone_column else [])+([spec.fold_column] if spec.fold_column else [])
    table='clock'+str(len(work.con.execute('SHOW TABLES').fetchall()))
    work.con.execute(f'CREATE TABLE {table}(_row BIGINT,t HUGEINT,state VARCHAR,precision VARCHAR,possible_end HUGEINT)')
    # Separate cursor permits writes while fetching without collecting the source in memory.
    cursor=work.con.cursor();cursor.execute('SELECT _row,'+','.join(r.col(c) for c in cols)+f' FROM {r.table} ORDER BY _row')
    try:
        while True:
            rows=cursor.fetchmany(max(1,min(16384,work.options.batch_bytes//1024)))
            if not rows:break
            normalized=[]
            for row in rows:
                vals=dict(zip(cols,row[1:]));tick,state,precision,end=parse_clock(vals[spec.column],spec,vals.get(spec.timezone_column),vals.get(spec.fold_column),getattr(r,'native',{}).get(spec.column))
                normalized.append((row[0],str(tick) if tick is not None else None,state,precision,str(end) if end is not None else None))
            frame=pd.DataFrame(normalized,columns=['_row','t','state','precision','possible_end']);work.con.register('_clock_batch',frame)
            try:work.con.execute(f'INSERT INTO {table} SELECT _row,CAST(t AS HUGEINT),state,precision,CAST(possible_end AS HUGEINT) FROM _clock_batch')
            finally:work.con.unregister('_clock_batch')
            work.check(r.id+': exact clock normalization')
    finally:cursor.close()
    r.clocks[key]=table;return table


def key_sql(r,columns):
    if not columns:return "'[]'",'true'
    cs=[r.col(c) for c in columns]
    return 'CAST(to_json(list_value('+','.join('CAST('+c+' AS VARCHAR)' for c in cs)+')) AS VARCHAR)',' AND '.join(c+' IS NOT NULL' for c in cs)


def canonical_cells(work,r,item,config):
    s=item.temporal;clock=normalize_clock(work,r,s.clock);entity,entity_ok=key_sql(r,s.entity_columns);obs,obs_ok=key_sql(r,s.observation_keys)
    for m in s.measurements:
        if s.layout=='wide':r.col(m.column or m.name)
    if s.layout=='long':
        mc=r.col(s.measurement_column);vc=r.col(s.value_column)
        unknown=work.con.execute(f'SELECT count(*) FROM {r.table} WHERE {mc} IS NULL OR {mc} NOT IN (SELECT unnest(?::VARCHAR[]))',[[m.name for m in s.measurements]]).fetchone()[0]
        if unknown:raise ValueError('Long-form rows reference missing/undeclared measurement identities.')
    cells=r.rows*(len(s.measurements) if s.layout=='wide' else 1)
    if cells>config.limits.max_cells:fail('Normalized measurement-cell hard limit exceeded.','temporal_cell_limit')
    work.check(r.id+': projected normalized cells and sort reservation',cells*160)
    table=r.table+'_cells';parts=[]
    for m in s.measurements:
        c=r.col(m.column or m.name) if s.layout=='wide' else vc
        value=f'CAST({c} AS VARCHAR)';num=f'try_cast({c} AS DOUBLE)' if m.representation=='quantitative' else 'NULL::DOUBLE'
        numeric=f"CASE WHEN {c} IS NULL THEN 'missing' WHEN try_cast({c} AS DOUBLE) IS NULL THEN 'invalid' WHEN NOT isfinite(try_cast({c} AS DOUBLE)) THEN 'nonfinite' ELSE 'valid' END" if m.representation=='quantitative' else f"CASE WHEN {c} IS NULL THEN 'missing' ELSE 'valid' END"
        if m.representation=='boolean':
            token=f'lower(CAST({c} AS VARCHAR))'
            value=f"CASE WHEN {token} IN ('true','1') THEN 'true' WHEN {token} IN ('false','0') THEN 'false' ELSE CAST({c} AS VARCHAR) END"
            numeric=f"CASE WHEN {c} IS NULL THEN 'missing' WHEN {token} IN ('true','false','0','1') THEN 'valid' ELSE 'invalid' END"
        safe=f"CASE WHEN regexp_full_match({value}, '[+-]?[0-9]+') AND abs(try_cast({c} AS HUGEINT))>9007199254740992 OR NOT isfinite({num}) THEN NULL ELSE {num} END" if m.representation=='quantitative' else num
        if m.representation=='quantitative' and c==r.col(s.value_column if s.layout=='long' else m.column or m.name) and (s.value_column if s.layout=='long' else m.column or m.name) in getattr(r,'decimals',{}):
            significant=f"length(regexp_replace(regexp_replace(regexp_replace({value},'[^0-9]','','g'),'^0+',''),'0+$',''))"
            safe=f'CASE WHEN {significant}>15 THEN NULL ELSE {safe} END'
        # Observation keys never recover unknown temporal identities. For events with no keys, each source record remains distinct.
        identity=obs if s.observation_keys else 'CAST(_row AS VARCHAR)' if s.observation=='event' else "coalesce(CAST(t AS VARCHAR),'invalid:'||CAST(_row AS VARCHAR))"
        where=f' WHERE {mc}=?' if s.layout=='long' else ''
        parts.append((f"SELECT _row,{entity} entity,{entity_ok} entity_ok,{identity} observation_key,{obs_ok} observation_key_ok,? measurement,t,clock.state time_state,clock.precision,{value} AS value,{safe} num,{numeric} value_state,'supplied' cell_origin FROM {r.table} JOIN {clock} clock USING(_row)"+where,[m.name]+([m.name] if where else [])))
    # Avoid hundreds of simultaneous UNION pipelines for wide panels.
    for offset in range(0,len(parts),8):
        block=parts[offset:offset+8]
        work.check(r.id+': bounded measurement-cell materialization')
        work.con.execute((f'CREATE TABLE {table} AS ' if offset==0 else f'INSERT INTO {table} ')+ ' UNION ALL '.join(p[0] for p in block),[v for p in block for v in p[1]])
    r.dense_missing=0
    if s.layout=='long' and s.dense_long:
        # Fill only identities whose existence is supplied. Entirely absent observations remain absent.
        base=table+'_dense_identities'
        work.con.execute(f"CREATE TABLE {base} AS SELECT entity,observation_key,t,min(_row) _row,min(precision) AS precision FROM {table} WHERE entity_ok AND observation_key_ok AND time_state='valid' GROUP BY ALL")
        add=work.con.execute(f"SELECT count(*) FROM {base} b CROSS JOIN (SELECT unnest(?::VARCHAR[]) measurement) m WHERE NOT EXISTS(SELECT 1 FROM {table} x WHERE x.entity=b.entity AND x.observation_key=b.observation_key AND x.t=b.t AND x.measurement=m.measurement)",[[m.name for m in s.measurements]]).fetchone()[0]
        if cells+add>config.limits.max_cells:fail('Declared dense expansion exceeds normalized-cell limit.','temporal_cell_limit')
        work.con.execute(f"INSERT INTO {table} SELECT b._row,b.entity,true,b.observation_key,true,m.measurement,b.t,'valid',b.precision,NULL,NULL,'missing','declared_dense_missing' FROM {base} b CROSS JOIN (SELECT unnest(?::VARCHAR[]) measurement) m WHERE NOT EXISTS(SELECT 1 FROM {table} x WHERE x.entity=b.entity AND x.observation_key=b.observation_key AND x.t=b.t AND x.measurement=m.measurement)",[[m.name for m in s.measurements]])
        r.dense_missing=add;cells+=add
    series=work.con.execute(f'SELECT count(*) FROM (SELECT entity,measurement FROM {table} WHERE entity_ok GROUP BY ALL)').fetchone()[0]
    if series>config.limits.max_series:fail('Distinct temporal series hard limit exceeded.','temporal_series_limit')
    unique=table+'_unique'
    names=[m.name for m in s.measurements]
    for offset in range(0,len(names),8):
        work.check(r.id+': bounded exact identity/tie aggregation')
        command=f'CREATE TABLE {unique} AS ' if offset==0 else f'INSERT INTO {unique} '
        work.con.execute(command+f'''WITH semantic_ties AS(
            SELECT entity,measurement,observation_key,t,value,value_state,
            min(_row) _row,count(*) multiplicity,min(num) num FROM {table}
            WHERE entity_ok AND observation_key_ok AND time_state='valid' AND measurement IN(SELECT unnest(?::VARCHAR[])) GROUP BY ALL)
            SELECT entity,measurement,observation_key,t,min(_row) _row,sum(multiplicity)::BIGINT multiplicity,
            count(*) states,min(value) AS value,min(num) num,min(value_state) value_state
            FROM semantic_ties GROUP BY entity,measurement,observation_key,t''',[names[offset:offset+8]])
    r.cells=table;r.unique=unique;r.temporal=s;r.series=series;r.cell_count=cells
    r.parsing['temporal_fingerprint']=hashlib.sha256(json.dumps({'temporal':asdict(s),'parsing':r.parsing['fingerprint'],'timezone':timezone_provenance()},sort_keys=True).encode()).hexdigest()
    return table
