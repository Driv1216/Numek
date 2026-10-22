"""Owned disk relations, whole-column interpretation and exact bounded reductions."""
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import tempfile
import time
from dataclasses import asdict, dataclass

import duckdb
import pandas as pd
from pandas._libs.parsers import STR_NA_VALUES

from datatrust.contracts import AnalysisConfig, AnalysisError, omit_default_delimiter
from datatrust.ingestion import source_signature, verify_source

PARSING_POLICY = 'scalable_csv_v1'
METHOD = 'm4_local_2026_10_10'


def fail(message, code='resource_limit', stage='scalable execution'):
    raise AnalysisError(message, code=code, stage=stage)


def token_digest(digest, row):
    for value in row:
        raw = value.encode('utf-8')
        digest.update(len(raw).to_bytes(8, 'big')); digest.update(raw)
    digest.update(b'\xff')


def available(path):
    p = Path(path)
    while not p.exists(): p = p.parent
    stat = os.statvfs(p)
    return stat.f_bavail * stat.f_frsize


def owned_inventory(root, snapshots=()):
    seen=set();total,files=inventory(root,seen)
    for path in snapshots:
        path=Path(path);s=path.stat();key=(s.st_dev,s.st_ino)
        if path.is_symlink():fail('Owned snapshots cannot be symlinks.')
        if key not in seen:
            charged=max(s.st_size,s.st_blocks*512);total+=charged
            files.append({'file':'sealed upload/'+path.name,'bytes':charged});seen.add(key)
    return total,files


def inventory(root, seen=None):
    """Never follow symlinks. Charge allocated or logical bytes, once per inode."""
    total = 0; files = []; seen = set() if seen is None else seen
    for directory, _, names in os.walk(root, followlinks=False):
        for name in names:
            p = Path(directory) / name
            try: s = p.lstat()
            except FileNotFoundError: continue  # DuckDB can remove spill files during monitoring.
            if p.is_symlink(): fail('An owned workspace contains a symlink.', 'workspace_integrity')
            key = (s.st_dev, s.st_ino)
            if key in seen: continue
            seen.add(key); size = max(s.st_size, s.st_blocks * 512)
            total += size; files.append({'file': str(p.relative_to(root)), 'bytes': size})
    return total, files


def cleanup_stale(parent):
    """Only marked immediate children whose original owner is inactive."""
    import psutil
    for root in Path(parent).glob('datatrust-m4-*'):
        marker=root/'owner.json'
        if root.is_symlink() or not root.is_dir() or marker.is_symlink() or not marker.is_file(): continue
        try:
            owner=json.loads(marker.read_text())
            if owner.get('kind')!='datatrust-m4-owned-workspace' or owner.get('uid')!=os.getuid() or owner.get('workspace')!=str(root.resolve()): continue
            try:
                process=psutil.Process(owner['pid'])
                active=abs(process.create_time()-owner['process_start'])<.01
            except psutil.NoSuchProcess: active=False
            if not active:
                inventory(root)  # Reject symlinks rather than traverse arbitrary paths.
                shutil.rmtree(root)
        except (OSError,ValueError,KeyError,AnalysisError,psutil.AccessDenied): continue


class Workspace:
    def __init__(self, options, inputs, progress=None, owned_snapshots=(), *, phase_plan=None, image_source_plan=None):
        self.options = options; self.progress = progress or (lambda value: None)
        self.input_count = len(inputs)
        self.owned_snapshots = tuple(Path(p).resolve() for p in owned_snapshots)
        self.started = time.monotonic(); self.peak = 0; self.phases = []
        sizes = [Path(i.dataset.path).stat().st_size for i in inputs] if image_source_plan is None else image_source_plan.metadata_sizes
        if image_source_plan is not None:
            from datatrust.image_sources import ValidatedImageSourcePlan
            if not isinstance(image_source_plan, ValidatedImageSourcePlan):
                raise ValueError('Image workspaces require an internally validated source plan.')
        for item, size in zip(inputs, sizes):
            tighter = item.config.limits.max_source_bytes if item.config and item.config.limits else None
            if size > min(options.max_source_bytes, tighter or options.max_source_bytes):
                fail(f'Input {item.id} exceeds the per-source byte limit.')
        if sum(sizes) > options.max_combined_source_bytes: fail('Combined input bytes exceed the job limit; aliases count for every role.')
        parent = Path(options.scratch_directory or tempfile.gettempdir()).resolve()
        if not parent.is_dir(): raise ValueError('Scratch directory must exist.')
        cleanup_stale(parent)
        self.estimate = (phase_plan["estimated_peak_workspace_bytes"] if phase_plan is not None else max(4 * 1024**3, 6 * sum(sizes)))
        self.phase_plan = phase_plan
        if self.estimate > options.workspace_bytes: fail(f'Estimated peak workspace {self.estimate} bytes exceeds budget {options.workspace_bytes}.')
        existing={}
        for p in self.owned_snapshots:
            s=p.stat();existing[(s.st_dev,s.st_ino)]=max(s.st_size,s.st_blocks*512)
            if available(p)<options.free_disk_bytes:fail('An owned-upload filesystem lacks the free-space reserve.','disk_preflight')
        already=sum(existing.values())
        if available(parent) < max(0,self.estimate-already) + options.free_disk_bytes:
            fail(f'Scratch filesystem needs estimated {self.estimate} additional bytes plus reserve {options.free_disk_bytes}.', 'disk_preflight')
        self.root = Path(tempfile.mkdtemp(prefix='datatrust-m4-', dir=parent))
        import psutil
        (self.root/'owner.json').write_text(json.dumps({'pid': os.getpid(), 'version': 1,'kind':'datatrust-m4-owned-workspace','uid':os.getuid(),'process_start':psutil.Process().create_time(),'workspace':str(self.root.resolve())}))
        try:
            self.con = duckdb.connect(str(self.root/'tokens.duckdb'))
            self.con.execute("SET autoinstall_known_extensions=false")
            self.con.execute("SET autoload_known_extensions=false")
            self.con.execute(f"SET memory_limit='{options.memory_bytes}B'")
            self.con.execute(f"SET threads={options.threads}")
            self.con.execute("SET preserve_insertion_order=false")
            self.con.execute("SET temp_directory=?", [str(self.root/'spill')])
            self.con.execute("SET enable_external_access=false")
            self.check('workspace initialized')
        except BaseException:
            self.close()
            raise

    def check(self, phase, addition=0):
        size, files = owned_inventory(self.root,self.owned_snapshots)
        self.peak = max(self.peak,size)
        self.estimate = max(self.estimate, size + addition)
        if size + addition > self.options.workspace_bytes:
            fail(f'{phase}: owned {size} bytes plus estimated addition {addition} exceeds workspace budget.')
        free = available(self.root)
        if free < addition + self.options.free_disk_bytes:
            fail(f'{phase}: available {free} bytes cannot cover addition {addition} and reserve {self.options.free_disk_bytes}.', 'disk_exhausted')
        for path in self.owned_snapshots:
            if available(path)<self.options.free_disk_bytes:fail('Owned-upload filesystem reserve was breached.','disk_exhausted')
        if time.monotonic() - self.started > self.options.max_seconds: fail('Analysis deadline exceeded.', 'deadline')
        remaining = self.options.workspace_bytes - size - 256 * 1024**2
        if remaining <= 0: fail('Workspace has no remaining spill/export reservation.')
        self.con.execute(f"SET max_temp_directory_size='{remaining}B'")
        entry = {'phase': phase, 'owned_bytes': size, 'available_bytes': free, 'estimated_addition': addition, 'files': files}
        self.phases.append(entry); self.phases = self.phases[-100:]
        self.progress({'stage': phase, 'workspace_bytes': size})

    def close(self):
        if hasattr(self, 'con'): self.con.close()
        if hasattr(self, 'root'): shutil.rmtree(self.root)


@dataclass
class Relation:
    id: str
    role: str
    table: str
    names: tuple
    types: dict
    representations: dict
    rows: int
    source: dict
    parsing: dict
    task: object
    config: object
    features: tuple
    metadata: tuple
    identifiers: tuple = ()

    def col(self, name):
        if name not in self.names: raise ValueError(f'Unknown column: {name}')
        return f'c{self.names.index(name)}'

    def finite(self, name):
        c = self.col(name)
        return f'{c} IS NOT NULL AND isfinite({c})' if self.types[name] in {'BIGINT','UBIGINT','DOUBLE'} else 'false'


def ingest(work, item, lexical_keys=()):
    options = work.options; config = item.config or AnalysisConfig(); parsing = config.parsing
    source_path = Path(item.dataset.path).resolve()
    if not source_path.is_file(): raise ValueError('Input must be a regular local CSV file.')
    signature = source_signature(source_path)
    snapshot = source_path if source_path in work.owned_snapshots else work.root/f'source-{hashlib.sha256(item.id.encode()).hexdigest()[:24]}.csv'
    digest = hashlib.sha256()
    if snapshot == source_path:
        with source_path.open('rb') as original:
            for block in iter(lambda: original.read(1024**2), b''): digest.update(block)
    else:
        with source_path.open('rb') as original, snapshot.open('xb') as owned:
            for block in iter(lambda: original.read(1024**2), b''):
                owned.write(block); digest.update(block)
    source = {'signature': signature, 'sha256': digest.hexdigest(), 'bytes': signature[2], 'filename': source_path.name}
    verify_source(source_path, source, 'snapshot')
    work.check(f'{item.id}: structural validation', source['bytes']*2)
    # Bounded logical records including embedded newlines; no permissive width repair.
    csv.field_size_limit(options.max_record_bytes)
    max_record = 1; record_bytes = 0; nonblank = False
    def lines(handle):
        nonlocal record_bytes, nonblank
        while True:
            line = handle.readline(options.max_record_bytes + 1)
            if not line: break
            record_bytes += len(line.encode(parsing.encoding))
            nonblank = nonblank or bool(line.strip(' \t\r\n'))
            if record_bytes > options.max_record_bytes: fail('Logical CSV record exceeds configured size.', 'record_limit')
            yield line
    structural = hashlib.sha256(); count = 0; headers = None
    try:
        with snapshot.open(encoding=parsing.encoding, newline='') as handle:
            reader = csv.reader(lines(handle), strict=True, delimiter=parsing.delimiter)
            for row in reader:
                used = record_bytes; record_bytes = 0; max_record = max(max_record, used)
                blank = not nonblank; nonblank = False
                if not row or blank: continue
                if headers is None:
                    headers = row
                    if headers[0].startswith('\ufeff'): headers[0] = headers[0][1:]
                    continue
                if len(row) != len(headers): fail('CSV record width differs from its header; records were not padded or dropped.', 'csv_structure')
                token_digest(structural, row); count += 1
                limit = min(options.max_rows, config.limits.max_rows or options.max_rows) if config.limits else options.max_rows
                if count > limit: fail(f'{item.id} exceeds the per-source row limit.')
    except (csv.Error, UnicodeError) as exc: fail(f'CSV structural validation failed: {exc}', 'csv_structure')
    if headers is None or not count: raise ValueError('Dataset needs a header and at least one data row.')
    # Reuse pandas header resolution, preserving case-distinct names internally by position.
    names = tuple(pd.read_csv(snapshot, encoding=parsing.encoding, sep=parsing.delimiter, nrows=0).columns)
    from datatrust.annotations import effective_policy
    task, config, _, base_method = effective_policy(names, item.task, config)
    from dataclasses import replace
    from datatrust.contracts import AnnotationOptions, AnnotationSpec
    if config.annotations is None:
        config = replace(config,annotations=AnnotationOptions(AnnotationSpec('expected') if base_method is None else AnnotationSpec()))
    item = replace(item, task=task, config=config)
    limit = min(options.max_columns, config.limits.max_columns or options.max_columns) if config.limits else options.max_columns
    if len(names) != len(headers) or len(names) > limit: fail('Header/column limit disagreement.', 'csv_structure')
    unknown = (set(parsing.column_types) | set(parsing.column_missing_policies) | set(lexical_keys) | set(item.task.target_names) | set(item.task.metadata_columns) | set(item.task.group_columns)) - set(names)
    if unknown: raise ValueError('Unknown declared columns: '+', '.join(sorted(unknown)))
    semantic = config.features.semantic_types
    if set(semantic)-set(names): raise ValueError('Unknown semantic columns.')
    lexical = set(lexical_keys) | set(item.task.group_columns) | {k for k,v in semantic.items() if v == 'identifier'}
    if set(lexical_keys)&set(item.task.target_names): raise ValueError('Comparison identity/group keys cannot also be target columns.')
    status = set()
    from datatrust.contracts import AnnotationOptions
    annotations = config.annotations or AnnotationOptions()
    for target in item.task.target_names:
        annotation = annotations.per_target.get(target, annotations.default)
        if annotation.status_column: status.add(annotation.status_column)
    if status-set(names): raise ValueError('Unknown annotation status column.')
    metadata = tuple(n for n in names if n in set(item.task.metadata_columns)|set(item.task.group_columns)|status)
    features = item.task.feature_columns if item.task.feature_columns is not None else tuple(n for n in names if n not in set(item.task.target_names)|set(metadata))
    if set(features)-set(names): raise ValueError('Unknown feature column.')
    table = f't{len(work.con.execute("SHOW TABLES").fetchall())}'
    raw = table+'_raw'
    cols = [f'c{i}' for i in range(len(names))]
    work.con.execute(f'CREATE TABLE {raw} (_row BIGINT, '+','.join(c+' VARCHAR' for c in cols)+')')
    observed = hashlib.sha256(); ordinal = 0
    chunk_rows = max(1, options.batch_bytes//(4*max_record+128*len(names)+8))
    for batch in pd.read_csv(snapshot, encoding=parsing.encoding, sep=parsing.delimiter, dtype=str, keep_default_na=False, na_filter=False, engine='c', chunksize=chunk_rows):
        if tuple(batch.columns) != names: fail('Tokenizer header disagreement.', 'csv_structure')
        for row in batch.itertuples(index=False, name=None): token_digest(observed, row)
        batch.columns = cols; batch.insert(0, '_row', range(ordinal+1, ordinal+len(batch)+1)); ordinal += len(batch)
        work.con.register('_batch', batch)
        work.con.execute(f'INSERT INTO {raw} SELECT * FROM _batch'); work.con.unregister('_batch')
        work.check(f'{item.id}: token staging')
    if ordinal != count or observed.digest() != structural.digest(): fail('Structural and C-tokenizer logical-token digests disagree.', 'csv_structure')
    representations = {}; expressions = []; types = {}
    for name,c in zip(names,cols):
        explicit = parsing.column_types.get(name)
        rep = explicit or ('string' if name in lexical else 'inference')
        policy = parsing.column_missing_policies.get(name)
        missing = policy.get('missing_policy','empty_only') if policy else 'empty_only' if name in lexical else parsing.missing_policy
        na = policy.get('na_values',()) if policy else parsing.na_values
        tokens = sorted(STR_NA_VALUES) if missing == 'pandas_default' else [''] if missing == 'empty_only' else list(na)
        work.con.execute(f'UPDATE {raw} SET {c}=NULL WHERE {c} IN (SELECT unnest(?::VARCHAR[]))', [tokens])
        n, integers, numbers, booleans = work.con.execute(f"SELECT count({c}),count(*) FILTER(WHERE regexp_full_match({c}, '[+-]?[0-9]+')),count(try_cast({c} AS DOUBLE)),count(*) FILTER(WHERE lower({c}) IN ('true','false')) FROM {raw}").fetchone()
        kind = 'VARCHAR'
        if not n and (explicit == 'numeric' or semantic.get(name) == 'quantitative' or item.task.kind == 'regression' and name in item.task.target_names): kind = 'DOUBLE'
        if rep != 'string' and n:
            if booleans == n and explicit != 'numeric': kind = 'BOOLEAN'
            elif integers == n:
                lo,hi = work.con.execute(f'SELECT min(try_cast({c} AS HUGEINT)),max(try_cast({c} AS HUGEINT)) FROM {raw}').fetchone()
                valid = work.con.execute(f'SELECT count(try_cast({c} AS HUGEINT)) FROM {raw}').fetchone()[0] == n
                if valid and -(2**63) <= lo and hi < 2**63: kind = 'BIGINT'
                elif valid and 0 <= lo and hi < 2**64: kind = 'UBIGINT'
                elif explicit == 'numeric': raise ValueError(f'{name}: integers exceed exact supported numeric identity.')
            elif numbers == n:
                unsafe = work.con.execute(f"SELECT count(*) FROM {raw} WHERE regexp_full_match({c}, '[+-]?[0-9]+') AND abs(try_cast({c} AS HUGEINT))>9007199254740992").fetchone()[0]
                if unsafe: raise ValueError(f'{name}: unsafe integer-to-float promotion; select string representation.')
                kind = 'DOUBLE'
            if explicit == 'numeric' and kind in {'VARCHAR','BOOLEAN'}: raise ValueError(f'{name}: invalid numeric override; values were not coerced.')
        if name in lexical and explicit == 'numeric' and n:
            from decimal import Decimal, InvalidOperation
            exact_integer = True; unsafe_integer = False; low = None; high = None
            cursor = work.con.execute(f'SELECT {c} FROM {raw} WHERE {c} IS NOT NULL')
            while True:
                values = cursor.fetchmany(4096)
                if not values: break
                for (token,) in values:
                    try: value = Decimal(token)
                    except InvalidOperation as exc: raise ValueError(f'{name}: numeric keys require valid finite numeric tokens.') from exc
                    if not value.is_finite(): raise ValueError(f'{name}: numeric keys must be finite.')
                    integral = value == value.to_integral_value()
                    if not integral:
                        converted=float(value)
                        if not math.isfinite(converted) or Decimal(str(converted))!=value:
                            raise ValueError(f'{name}: numeric key conversion would lose decimal identity; select string parsing.')
                    exact_integer &= integral
                    unsafe_integer |= integral and abs(value) > 2**53
                    low = value if low is None else min(low,value); high = value if high is None else max(high,value)
            if exact_integer and -(2**63) <= low and high < 2**63: kind = 'BIGINT'
            elif exact_integer and 0 <= low and high < 2**64: kind = 'UBIGINT'
            elif exact_integer or unsafe_integer: raise ValueError(f'{name}: numeric key equality cannot be represented losslessly; select string parsing.')
        types[name] = kind
        representations[name] = {'representation': 'unknown' if not n else kind, 'origin': 'explicit_parsing' if explicit else 'identifier_key_default' if name in lexical else 'whole_column_inference', 'missing_policy': missing, 'na_values': tokens if missing == 'custom' else []}
        expressions.append(f'CAST({c} AS {kind}) AS {c}')
    work.check(f'{item.id}: typed materialization', max(source['bytes']*2, count*len(names)*8))
    work.con.execute(f'CREATE TABLE {table} AS SELECT _row,'+','.join(expressions)+f' FROM {raw}')
    work.con.execute(f'DROP TABLE {raw}')
    if base_method is None and item.task.kind in {'classification','regression'}:
        target=item.task.target_names[0]; c=cols[names.index(target)]
        if item.task.kind=='classification': usable=work.con.execute(f'SELECT count({c}) FROM {table}').fetchone()[0]
        else: usable=work.con.execute(f'SELECT count(*) FROM {table} WHERE {c} IS NOT NULL AND isfinite({c})').fetchone()[0] if types[target] in {'BIGINT','UBIGINT','DOUBLE'} else 0
        if not usable: fail('Selected target has no usable observations under its accepted base-task policy.','invalid_target','target')
    fingerprint = hashlib.sha256(json.dumps({'policy':PARSING_POLICY,'options':omit_default_delimiter(asdict(parsing)),'representations':representations,'token_sha256':observed.hexdigest()},sort_keys=True).encode()).hexdigest()
    parsed = {'policy':PARSING_POLICY,'base_task_policy':base_method or {'classification':'classification_legacy_2026_08_13','regression':'regression_scalar_v1','dataset_profile':'dataset_profile_v1'}.get(item.task.kind,item.task.kind),'options':omit_default_delimiter(asdict(parsing)),'representations':representations,'fingerprint':fingerprint,'logical_token_sha256':observed.hexdigest(),'header_mapping':[{'position':i+1,'original':h,'resolved':n} for i,(h,n) in enumerate(zip(headers,names))]}
    return Relation(item.id,item.role,table,names,types,representations,count,source,parsed,item.task,config,tuple(features),metadata,tuple(n for n in names if n in lexical))


def quantiles(con, table, col, predicate, probabilities=(.01,.05,.25,.5,.75,.95,.99)):
    n = con.execute(f'SELECT count(*) FROM {table} WHERE {predicate}').fetchone()[0]
    if not n: return [None]*len(probabilities)
    indices = sorted({int(math.floor((n-1)*p))+1 for p in probabilities}|{int(math.ceil((n-1)*p))+1 for p in probabilities})
    positions = ','.join(map(str,indices))
    values = dict(con.execute(f'SELECT r,v FROM (SELECT {col} v,row_number() OVER(ORDER BY {col},_row) r FROM {table} WHERE {predicate}) WHERE r IN ({positions})').fetchall())
    out=[]
    for p in probabilities:
        rank=(n-1)*p; lo=values[int(math.floor(rank))+1]; hi=values[int(math.ceil(rank))+1]; f=rank-math.floor(rank)
        # Weighted interpolation avoids overflow of hi-lo; guard exact integers elsewhere.
        out.append(float(lo)*(1-f)+float(hi)*f if f else float(lo))
    return out


def precision(con, relation, name, predicate=None):
    c=relation.col(name); pred=predicate or relation.finite(name)
    n,lo,hi=con.execute(f'SELECT count(*),min({c}),max({c}) FROM {relation.table} WHERE {pred}').fetchone()
    if not n: return 'no_finite_population'
    if relation.types[name] in {'BIGINT','UBIGINT'} and max(abs(lo),abs(hi))>2**53: return 'unsafe_integer_geometry'
    if lo != hi and float(hi)-float(lo) <= 128*max(math.ulp(float(lo)),math.ulp(float(hi))): return 'unsafe_floating_resolution'
    return None


def grouped_overlap(con, left, right, columns, *, complete=False):
    if not columns: raise ValueError('Overlap needs a complete declared vector.')
    ac=[left.col(a) for a,b in columns]; bc=[right.col(b) for a,b in columns]
    for a,b in columns:
        ka,kb=left.types[a],right.types[b]
        numeric={'BIGINT','UBIGINT','DOUBLE'}
        if ka!=kb and not ({ka,kb} <= {'BIGINT','UBIGINT'}):
            if not {ka,kb}<=numeric: return {'blocked':'incompatible_representations'}
            integer_side,integer_name=(left,a) if ka!='DOUBLE' else (right,b)
            if integer_side.types[integer_name]!='DOUBLE' and precision(con,integer_side,integer_name): return {'blocked':'unsafe_numeric_key_alignment'}
    fields=','.join(f'{c} AS k{i}' for i,c in enumerate(ac)); rfields=','.join(f'{c} AS k{i}' for i,c in enumerate(bc))
    aw=' AND '.join(f'{c} IS NOT NULL'+(f' AND isfinite({c})' if left.types[a] in {'BIGINT','UBIGINT','DOUBLE'} else '') for (a,b),c in zip(columns,ac)) if complete else 'true'
    bw=' AND '.join(f'{c} IS NOT NULL'+(f' AND isfinite({c})' if right.types[b] in {'BIGINT','UBIGINT','DOUBLE'} else '') for (a,b),c in zip(columns,bc)) if complete else 'true'
    keys=','.join('k'+str(i) for i in range(len(columns))); join=' AND '.join(f'a.k{i} IS NOT DISTINCT FROM b.k{i}' for i in range(len(columns)))
    con.execute(f'CREATE OR REPLACE TEMP TABLE _overlap_a AS SELECT {fields},count(*) n FROM {left.table} WHERE {aw} GROUP BY {keys}')
    con.execute(f'CREATE OR REPLACE TEMP TABLE _overlap_b AS SELECT {rfields},count(*) n FROM {right.table} WHERE {bw} GROUP BY {keys}')
    sql=f'SELECT count(*),coalesce(sum(a.n),0),coalesce(sum(b.n),0),coalesce(sum(least(a.n,b.n)),0) FROM _overlap_a a JOIN _overlap_b b ON {join}'
    shared,ar,br,intersection=con.execute(sql).fetchone()
    con.execute('DROP TABLE _overlap_a');con.execute('DROP TABLE _overlap_b')
    eligible_a=con.execute(f'SELECT count(*) FROM {left.table} WHERE {aw}').fetchone()[0]; eligible_b=con.execute(f'SELECT count(*) FROM {right.table} WHERE {bw}').fetchone()[0]
    return {'shared_distinct_groups':shared,'left_rows':int(ar),'right_rows':int(br),'left_share':float(ar)/left.rows,'right_share':float(br)/right.rows,'multiset_intersection':int(intersection),'eligible_left':eligible_a,'eligible_right':eligible_b,'excluded_left':left.rows-eligible_a,'excluded_right':right.rows-eligible_b,'columns':[a for a,b in columns],'definition':'parsed equality; null equals null' if not complete else 'complete finite declared keys'}
