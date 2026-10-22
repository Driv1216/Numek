"""Explicit M9 contracts. No document/model imports at package import time."""
from dataclasses import dataclass, field, asdict
from pathlib import Path
import json
import re

from datatrust.contracts import _construct, _positive, ReportArtifacts
from datatrust.text_contracts import Contract, nested, sequence, choice, selector
from datatrust.m4_contracts import ExecutionOptions
from datatrust.temporal_contracts import ClockSpec, exact_json


def names(value):
    if not isinstance(value, (list, tuple)) or not value or any(not isinstance(x, str) or not x for x in value):
        raise ValueError('A nonempty selector array is required.')
    return tuple(value)


@dataclass(frozen=True)
class CrossRepresentationInputSpec(Contract):
    id: str
    path: str
    kind: str = 'structured'
    format: str = 'csv'
    id_selector: str = 'id'
    text_selector: str = 'text'
    path_selector: str = 'path'
    split_selector: str | None = None
    role: str = 'dataset'
    language: str | None = None
    layout: str | None = None
    layout_selector: str | None = None
    asset_root: str | None = None
    metadata: dict = field(default_factory=dict)
    encoding: str = 'utf-8'
    delimiter: str = ','
    json_columns: tuple = ()

    def __post_init__(self):
        selector(self.id); selector(self.id_selector)
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', self.id): raise ValueError('Invalid source ID.')
        object.__setattr__(self, 'path', str(self.path))
        if not self.path: raise ValueError('Local source path is required.')
        choice(self.kind, {'structured','text','document','image'}, 'input kind')
        choice(self.format, {'csv','jsonl','parquet','txt','pdf','docx'}, 'input format')
        if self.format in {'pdf','docx'} and self.kind != 'document': raise ValueError('Native documents require document kind.')
        if self.format == 'txt' and self.kind != 'text': raise ValueError('TXT requires text kind.')
        if self.format == 'parquet' and self.kind != 'structured': raise ValueError('Parquet is flat structured data.')
        if not isinstance(self.metadata, dict): raise ValueError('metadata must be an object.')
        for x in (self.text_selector, self.path_selector, self.split_selector, self.layout_selector):
            if x is not None: selector(x)
        if len(self.delimiter) != 1: raise ValueError('Delimiter must be one character.')
        object.__setattr__(self, 'json_columns', tuple(self.json_columns))


@dataclass(frozen=True)
class RelationshipSpec(Contract):
    id: str
    left_source: str
    right_source: str
    left_keys: tuple = ('id',)
    right_keys: tuple = ('id',)
    namespace: str = 'declared'
    meaning: str = 'supporting_evidence'
    cardinality: str = 'one_to_many'
    required: str = 'required'
    inverse_required: bool = False
    key_representation: str = 'typed'
    association_source: str | None = None
    association_left: str = 'left_id'
    association_right: str = 'right_id'
    association_left_keys: tuple = ()
    association_right_keys: tuple = ()
    context: dict = field(default_factory=dict)
    availability: ClockSpec | None = None
    cutoff: ClockSpec | None = None
    valid_from: ClockSpec | None = None
    valid_to: ClockSpec | None = None
    version_mode: str = 'all'

    def __post_init__(self):
        for x in (self.id, self.left_source, self.right_source, self.namespace): selector(x)
        for n in ('left_keys','right_keys'): object.__setattr__(self,n,names(getattr(self,n)))
        if len(self.left_keys) != len(self.right_keys): raise ValueError('Relationship keys must have equal arity.')
        choice(self.cardinality, {'one_to_one','one_to_many','many_to_one','many_to_many'}, 'cardinality')
        choice(self.meaning, {'identity','supporting_evidence','caption','version','derivation'}, 'relationship meaning')
        choice(self.required, {'required','optional','unknown'}, 'requiredness')
        choice(self.key_representation, {'typed','lexical','nfc','numeric'}, 'key representation')
        choice(self.version_mode, {'all','exact','latest_as_of'}, 'version mode')
        if self.cardinality == 'many_to_many' and not self.association_source: raise ValueError('Many-to-many requires explicit association rows.')
        for n in ('association_left_keys','association_right_keys'):
            vals=getattr(self,n)
            if not isinstance(vals,(list,tuple)): raise ValueError('Association component selectors require arrays.')
            object.__setattr__(self,n,names(vals) if vals else ())
        if self.association_source and ((self.association_left_keys and len(self.association_left_keys)!=len(self.left_keys)) or (self.association_right_keys and len(self.association_right_keys)!=len(self.right_keys)) or len(self.left_keys)>1 and not (self.association_left_keys and self.association_right_keys)): raise ValueError('Composite association endpoints require matching component selectors.')
        if not isinstance(self.inverse_required,bool): raise ValueError('inverse_required must be boolean.')
        if not isinstance(self.context,dict) or any(not isinstance(v,(list,tuple)) or len(v)!=2 for v in self.context.values()): raise ValueError('context maps names to left/right selectors.')
        for pair in self.context.values():
            for x in pair: selector(x)
        for n in ('availability','cutoff','valid_from','valid_to'):
            if getattr(self,n) is not None: nested(self,n,ClockSpec)
        if bool(self.availability) != bool(self.cutoff): raise ValueError('Availability and cutoff must be paired.')
        if (self.valid_from or self.valid_to) and not self.cutoff: raise ValueError('Validity requires a cutoff.')
        if self.version_mode == 'latest_as_of' and not self.availability: raise ValueError('Latest-as-of requires explicit clocks.')
        if self.version_mode == 'exact' and 'version' not in self.context: raise ValueError('Exact version requires version context.')


@dataclass(frozen=True)
class DocumentMappingSpec(Contract):
    id: str
    layout: str = 'default'
    kind: str = 'label_value'
    labels: tuple = ()
    pattern: str = r'(?P<value>[^\n]+)'
    section: str | None = None
    pages: tuple = ()
    parts: tuple = ('word/document.xml',)
    headers: dict = field(default_factory=dict)
    value_column: str = 'value'
    row_column: str | None = None
    row_label: str | None = None
    row_selector: str | None = None
    context_columns: dict = field(default_factory=dict)
    strategy: str = 'lines'
    unit: str | None = None
    currency: str | None = None
    substitutions: dict = field(default_factory=dict)
    overrides: dict = field(default_factory=dict)

    def __post_init__(self):
        selector(self.id); selector(self.layout)
        choice(self.kind, {'label_value','table_field','text'}, 'document mapping')
        choice(self.strategy, {'lines','text'}, 'PDF table strategy')
        for n in ('labels','pages','parts'): object.__setattr__(self,n,tuple(getattr(self,n)))
        if any(isinstance(p,bool) or not isinstance(p,int) or p<1 for p in self.pages): raise ValueError('Pages are positive physical page numbers.')
        if self.kind == 'label_value' and not self.labels: raise ValueError('Label mapping requires labels.')
        if self.kind == 'table_field' and (self.value_column not in self.headers or not self.row_column or self.row_column not in self.headers or bool(self.row_label)==bool(self.row_selector)): raise ValueError('Table mapping requires headers, a row column and exactly one row binding.')
        if any(not isinstance(v,(list,tuple)) or not v for v in self.headers.values()): raise ValueError('Header aliases must be nonempty arrays.')
        if any(k not in self.headers for k in self.context_columns): raise ValueError('Context columns must be declared headers.')
        if any(p not in {'word/document.xml','headers','footers'} for p in self.parts): raise ValueError('Unsupported DOCX part selection.')
        import regex
        try:
            compiled=regex.compile(self.pattern)
            if self.kind=='label_value' and 'value' not in compiled.groupindex: raise ValueError('Pattern needs named value capture.')
        except regex.error as exc: raise ValueError('Invalid bounded capture pattern.') from exc
        if not isinstance(self.substitutions,dict) or not isinstance(self.overrides,dict): raise ValueError('Invalid substitutions/overrides.')
        for ref,override in self.overrides.items():
            if not isinstance(ref,str) or not isinstance(override,dict) or set(override)-{'page','part','block','table','row','column','span','document_id'}: raise ValueError('Invalid manual evidence override.')
            for k,v in override.items():
                if k in {'page','block','table','row','column'} and (isinstance(v,bool) or not isinstance(v,int) or v<0): raise ValueError('Override coordinates are nonnegative integers.')
            if 'span' in override:
                span=override['span']
                if not isinstance(span,(tuple,list)) or len(span)!=2 or any(isinstance(x,bool) or not isinstance(x,int) or x<0 for x in span) or span[1]<span[0]: raise ValueError('Override spans are half-open intervals.')


@dataclass(frozen=True)
class ReconciliationRule(Contract):
    id: str
    relationship: str
    field: str
    mapping: str | None = None
    right_field: str | None = None
    method: str = 'decimal'
    representation: str = 'raw'
    aliases: dict = field(default_factory=dict)
    tolerance: str = '0'
    factor: str = '1'
    decimal_separator: str = '.'
    thousands_separator: str | None = ','
    evidence_decimal_separator: str | None = None
    evidence_thousands_separator: str | None = None
    date_format: str = '%Y-%m-%d'
    evidence_date_format: str | None = None
    unit: str | None = None
    currency: str | None = None
    authority_role: str | None = None
    authority_source: str | None = None
    alternative_relationship: str | None = None
    claim_template: str | None = None
    claim_language: str | None = None

    def __post_init__(self):
        for x in (self.id,self.relationship,self.field): selector(x)
        object.__setattr__(self,'factor',str(self.factor));object.__setattr__(self,'tolerance',str(self.tolerance))
        if bool(self.mapping)==bool(self.right_field): raise ValueError('Rule requires exactly one mapping or right field.')
        choice(self.method, {'decimal','date','string','category','nli','image_text'}, 'comparison method')
        choice(self.representation, {'raw','nfc','casefold','whitespace'}, 'string representation')
        if not isinstance(self.aliases,dict) or any(not isinstance(k,str) or not isinstance(v,str) for k,v in self.aliases.items()): raise ValueError('Category aliases map strings to declared strings.')
        from decimal import Decimal, InvalidOperation
        try:
            a,b=Decimal(str(self.tolerance)),Decimal(str(self.factor))
            if not a.is_finite() or a<0 or not b.is_finite() or b==0: raise ValueError('Invalid tolerance/factor.')
        except InvalidOperation as exc: raise ValueError('Invalid decimal comparison.') from exc
        if self.decimal_separator not in {'.',','} or self.thousands_separator not in {None,',','.',' '} or self.decimal_separator==self.thousands_separator: raise ValueError('Explicit distinct numeric separators required.')
        if self.evidence_decimal_separator is not None and (self.evidence_decimal_separator not in {'.',','} or self.evidence_thousands_separator not in {None,',','.',' '} or self.evidence_decimal_separator==self.evidence_thousands_separator): raise ValueError('Invalid evidence numeric conventions.')
        if self.authority_role and self.authority_source: raise ValueError('Choose one authority binding.')
        if self.claim_template:
            import string
            if len(self.claim_template)>2000: raise ValueError('Claim template exceeds bound.')
            if any(f and (not f.isidentifier() or fmt or conv) for _,f,fmt,conv in string.Formatter().parse(self.claim_template)): raise ValueError('Claim templates accept simple mapped selectors only.')


@dataclass(frozen=True)
class CrossSeparationSpec(Contract):
    id: str
    left_source: str
    right_source: str
    left_keys: tuple = ('id',)
    right_keys: tuple = ('id',)
    mode: str = 'keys'
    required: bool = True
    left_path: tuple = ()
    right_path: tuple = ()
    left_splits: tuple = ()
    right_splits: tuple = ()
    def __post_init__(self):
        choice(self.mode, {'keys','content','assets','ancestry'}, 'separation mode')
        for n in ('left_keys','right_keys'): object.__setattr__(self,n,names(getattr(self,n)))
        if len(self.left_keys)!=len(self.right_keys): raise ValueError('Separation key arity differs.')
        for n in ('left_path','right_path'):
            object.__setattr__(self,n,tuple(getattr(self,n)))
            if len(getattr(self,n))>3: raise ValueError('Ancestry paths allow at most three relationships.')
        if not isinstance(self.required,bool): raise ValueError('Separation required must be boolean.')
        for n in ('left_splits','right_splits'):
            vals=getattr(self,n)
            if not isinstance(vals,(list,tuple)) or any(not isinstance(v,str) or not v for v in vals): raise ValueError('Explicit split scopes require strings.')
            object.__setattr__(self,n,tuple(vals))


@dataclass(frozen=True)
class CrossRepresentationAuditSpec(Contract):
    inputs: tuple
    relationships: tuple = ()
    mappings: tuple = ()
    rules: tuple = ()
    separation: tuple = ()
    allowed_roots: tuple = ()
    dataset_name: str | None = None
    purpose: str | None = None

    def __post_init__(self):
        for n,c in [('inputs',CrossRepresentationInputSpec),('relationships',RelationshipSpec),('mappings',DocumentMappingSpec),('rules',ReconciliationRule),('separation',CrossSeparationSpec)]: sequence(self,n,c)
        if not self.inputs: raise ValueError('At least one input required.')
        for n in ('inputs','relationships','mappings','rules','separation'):
            ids=[x.id for x in getattr(self,n)]
            if len(set(ids))!=len(ids): raise ValueError('Duplicate declaration ID.')
        sources={x.id:x for x in self.inputs};rels={x.id:x for x in self.relationships};maps={x.id:x for x in self.mappings}
        for r in self.relationships:
            if r.left_source not in sources or r.right_source not in sources or (r.association_source and r.association_source not in sources): raise ValueError('Unknown relationship endpoint.')
        for r in self.rules:
            if r.relationship not in rels or (r.mapping and r.mapping not in maps): raise ValueError('Unknown rule relationship/mapping.')
            rel=rels[r.relationship]
            if r.mapping and sources[rel.right_source].kind not in {'document','text'}: raise ValueError('Document mapping requires document/text evidence.')
            if r.authority_source and r.authority_source != rel.right_source: raise ValueError('Authority must name the declared evidence source.')
            if r.alternative_relationship:
                a=rels.get(r.alternative_relationship)
                if r.method!='image_text' or not a or a.left_source!=rel.left_source or sources[a.right_source].kind!='image': raise ValueError('Image alternatives require an explicit relationship from the same claim source.')
        for s in self.separation:
            if s.left_source not in sources or s.right_source not in sources: raise ValueError('Unknown separation endpoint.')
            terminals=[]
            for start,path in ((s.left_source,s.left_path),(s.right_source,s.right_path)):
                for rid in path:
                    if rid not in rels or rels[rid].left_source!=start or rels[rid].meaning!='derivation': raise ValueError('Ancestry requires an ordered derivation path.')
                    start=rels[rid].right_source
                terminals.append(start)
            if s.mode=='ancestry' and terminals[0]!=terminals[1]: raise ValueError('Ancestry paths must resolve to the same declared parent source.')
        object.__setattr__(self,'allowed_roots',tuple(str(x) for x in self.allowed_roots))
        for n,limit in (('dataset_name',120),('purpose',1000)):
            v=getattr(self,n)
            if v is not None:
                if not isinstance(v,str) or len(v)>limit: raise ValueError('Report context exceeds its string bound.')
                object.__setattr__(self,n,v.strip() or None)

    @classmethod
    def from_dict(cls,value,*,base_directory=None):
        result=_construct(cls,value)
        if base_directory:
            from dataclasses import replace
            def absolute(p): return str((Path(base_directory)/p).absolute()) if p else p
            result=replace(result,inputs=tuple(replace(x,path=absolute(x.path),asset_root=absolute(x.asset_root)) for x in result.inputs),allowed_roots=tuple(absolute(x) for x in result.allowed_roots))
        return result


@dataclass(frozen=True)
class CrossWorkLimits(Contract):
    inputs: int = 64
    declarations: int = 128
    associations: int = 10000000
    documents: int = 1000
    pages: int = 10000
    document_bytes: int = 128*1024**2
    expanded_docx_bytes: int = 256*1024**2
    xml_bytes: int = 16*1024**2
    zip_members: int = 10000
    characters: int = 50000000
    candidates: int = 100
    tables: int = 100
    region_chars: int = 10000
    discovery_visits: int = 100000000
    pattern_seconds: float = .05
    details: int = 100
    witnesses: int = 5
    private_bytes: int = 64*1024**2
    claims: int = 2000
    evidence_candidates: int = 5
    image_pairs: int = 2000
    model_seconds: float = 600
    image_assets: int = 100000
    image_pixels: int = 100000000000
    image_media_bytes: int = 128*1024**3
    image_media_per_input_bytes: int = 64*1024**3
    tokenizer_bytes: int = 64*1024**2
    tokenizer_tokens: int = 1000000
    def __post_init__(self):
        for n,v in asdict(self).items(): _positive(v,n,integer=n not in {'pattern_seconds','model_seconds'})


@dataclass(frozen=True)
class CrossModelOptions(Contract):
    nli_directory: str | None = None
    retrieval_directory: str | None = None
    image_text_directory: str | None = None
    def __post_init__(self):
        if self.nli_directory and not self.retrieval_directory: raise ValueError('NLI requires verified local E5 retrieval artifacts.')


@dataclass(frozen=True)
class CrossRepresentationAnalysisConfig(Contract):
    execution: ExecutionOptions = field(default_factory=ExecutionOptions)
    limits: CrossWorkLimits = field(default_factory=CrossWorkLimits)
    models: CrossModelOptions = field(default_factory=CrossModelOptions)
    seed: int = 0
    def __post_init__(self):
        for n,c in [('execution',ExecutionOptions),('limits',CrossWorkLimits),('models',CrossModelOptions)]: nested(self,n,c)
        if self.execution.backend!='duckdb_local': raise ValueError('M9 requires supervised DuckDB.')
        if isinstance(self.seed,bool) or not isinstance(self.seed,int) or not 0<=self.seed<2**64: raise ValueError('Invalid seed.')


@dataclass(frozen=True)
class CrossDisclosureOptions(Contract):
    excerpt_refs: tuple = ()
    image_refs: tuple = ()
    def __post_init__(self):
        for n in ('excerpt_refs','image_refs'):
            vals=tuple(getattr(self,n));object.__setattr__(self,n,vals)
            if len(vals)>20 or len(set(vals))!=len(vals): raise ValueError('At most 20 distinct disclosure references.')


@dataclass(frozen=True)
class CrossReportArtifacts(ReportArtifacts):
    private_manifest_path: str | None = None


@dataclass
class CrossRepresentationAuditResult:
    profile: dict
    checks: list
    evidence: list
    findings: list
    coverage: dict
    execution: dict
    generated_at: str
    private: dict = field(repr=False)
    schema_version: str = '1.7'
    methodology_id: str = 'cross_representation_reliability_v1'
    guidance: dict = field(default_factory=dict, kw_only=True)  # finding_guidance_v1 and later; absent before
    @property
    def source_paths(self): return tuple(dict.fromkeys((*self.private['files'],*self.private.get('unavailable',()))))
    @classmethod
    def from_dict(cls,value,*,private):
        from datatrust.cross_private import validate
        private,value=validate(private,value)
        value=dict(value)
        # Export identity belongs to a derivative; reviews bind the immutable original result.
        value['profile']=dict(value['profile'])
        for n in ('examples','disclosure','export_identity'): value['profile'].pop(n,None)
        result=cls(**value,private=private)
        return result
    def to_dict(self): return exact_json({n:getattr(self,n) for n in ('schema_version','methodology_id','profile','checks','evidence','findings','coverage','execution','generated_at')}|({'guidance':self.guidance} if self.guidance else {}))
    def json_text(self): return json.dumps(self.to_dict(),ensure_ascii=False,indent=2,allow_nan=False)
    def generate_artifacts(self,path,**kwargs):
        from datatrust.cross_private import generate_artifacts
        return generate_artifacts(self,path,**kwargs)
    def generate_report(self,path,**kwargs): return self.generate_artifacts(path,**kwargs).html_path
    def write_json(self,path,**kwargs):
        from datatrust.cross_private import write_json
        return write_json(self,path,**kwargs)
    def resolve_evidence(self,reference,*,allowed_roots,reveal_content=False):
        from datatrust.cross_private import resolve_evidence
        return resolve_evidence(self.private,reference,self.to_dict(),allowed_roots=allowed_roots,reveal_content=reveal_content)
    def review_dispositions(self,reviewer=None):
        from datatrust.cross_review import ReviewDispositionSet
        return ReviewDispositionSet.for_result(self,reviewer=reviewer)
