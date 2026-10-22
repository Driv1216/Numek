"""Strict M6 declarations. No model, Unicode or database imports at import time."""
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
import codecs
import json
from typing import Optional

from datatrust.contracts import _construct, _positive, ReportArtifacts
from datatrust.m4_contracts import ExecutionOptions
from datatrust.temporal_contracts import exact_json


class Contract:
    @classmethod
    def from_dict(cls, value):
        try:
            return _construct(cls, value)
        except (TypeError, AttributeError) as exc:
            raise ValueError(f'Invalid {cls.__name__} declaration.') from exc

    def to_dict(self):
        from datatrust.contracts import json_safe
        return json_safe(asdict(self))


def choice(value, choices, name):
    if value not in choices:
        raise ValueError(f'Unsupported {name}.')


def nested(owner, name, cls):
    value = getattr(owner, name)
    if isinstance(value, dict):
        object.__setattr__(owner, name, cls.from_dict(value))
    elif not isinstance(value, cls):
        raise ValueError(f'{name} requires {cls.__name__}.')


def sequence(owner, name, cls):
    values = getattr(owner, name)
    if not isinstance(values, (list, tuple)):
        raise ValueError(f'{name} requires an array.')
    result = tuple(cls.from_dict(v) if isinstance(v, dict) else v for v in values)
    if any(not isinstance(v, cls) for v in result):
        raise ValueError(f'Invalid {name}.')
    object.__setattr__(owner, name, result)


def selector(value):
    if not isinstance(value, str) or not value or any(0xd800<=ord(c)<=0xdfff for c in value):
        raise ValueError('Selectors must be nonempty field names or JSON Pointers.')
    if value.startswith('/'):
        import re
        if re.search(r'~(?![01])', value):
            raise ValueError('Invalid JSON Pointer escape.')


@dataclass(frozen=True)
class SourceLocation(Contract):
    source_id: str
    ordinal: int
    selector: str = ''
    byte_start: Optional[int] = None
    byte_length: Optional[int] = None
    line_start: Optional[int] = None
    line_end: Optional[int] = None
    nested_ordinal: Optional[int] = None
    span: Optional[tuple] = None
    def __post_init__(self):
        selector(self.source_id)
        for name in ('ordinal','byte_start','byte_length','line_start','line_end','nested_ordinal'):
            v=getattr(self,name)
            if v is not None and (isinstance(v,bool) or not isinstance(v,int) or v<0):raise ValueError('Source coordinates require nonnegative integers.')
        if self.selector:selector(self.selector)
        if self.span is not None:
            if not isinstance(self.span,(list,tuple)) or len(self.span)!=2 or any(isinstance(x,bool) or not isinstance(x,int) or x<0 for x in self.span) or self.span[1]<self.span[0]:raise ValueError('Source span requires an ordered half-open interval.')
            object.__setattr__(self,'span',tuple(self.span))


@dataclass(frozen=True)
class ContentRef(Contract):
    reference: str
    representation: str = 'raw'
    parent: Optional[str] = None
    def __post_init__(self):
        selector(self.reference);selector(self.representation)
        if self.parent:selector(self.parent)


@dataclass(frozen=True)
class AssetSpec(Contract):
    selector: str
    kind: str = 'text'
    encoding: str = 'utf-8'
    checksum_selector: Optional[str] = None
    def __post_init__(self):
        selector(self.selector)
        choice(self.kind, {'text', 'image'}, 'asset kind')
        codecs.lookup(self.encoding)
        object.__setattr__(self,'encoding',codecs.lookup(self.encoding).name)
        if self.checksum_selector: selector(self.checksum_selector)


@dataclass(frozen=True)
class TextSourceSpec(Contract):
    path: str
    format: str = 'jsonl'
    encoding: str = 'utf-8'
    delimiter: str = ','
    quotechar: str = '"'
    json_columns: tuple = ()
    def __post_init__(self):
        if not isinstance(self.path, (str, Path)) or not str(self.path):
            raise ValueError('A local source path is required.')
        object.__setattr__(self, 'path', str(self.path))
        choice(self.format, {'csv', 'jsonl'}, 'source format')
        codecs.lookup(self.encoding)
        object.__setattr__(self,'encoding',codecs.lookup(self.encoding).name)
        if self.format == 'jsonl' and self.encoding.lower().replace('_', '-') not in {'utf-8', 'utf-8-sig'}:
            raise ValueError('JSONL requires UTF-8 physical line framing.')
        if len(self.delimiter) != 1 or len(self.quotechar) != 1 or self.delimiter == self.quotechar:
            raise ValueError('CSV delimiter and quote must be distinct single characters.')
        if not isinstance(self.json_columns, (list, tuple)) or len(set(self.json_columns)) != len(self.json_columns):
            raise ValueError('json_columns requires unique field names.')
        for v in self.json_columns: selector(v)
        object.__setattr__(self, 'json_columns', tuple(self.json_columns))


@dataclass(frozen=True)
class TextFieldSpec(Contract):
    name: str
    selector: str
    kind: str = 'document'
    required: bool = False
    asset: Optional[AssetSpec] = None
    def __post_init__(self):
        selector(self.name); selector(self.selector)
        choice(self.kind, {'document', 'chunk', 'query', 'context', 'question', 'prompt', 'completion', 'caption', 'text'}, 'content kind')
        if not isinstance(self.required, bool): raise ValueError('required must be boolean.')
        if self.asset is not None: nested(self, 'asset', AssetSpec)
        if self.asset and self.asset.kind != 'text': raise ValueError('Content fields require text assets.')


@dataclass(frozen=True)
class TextAnnotationSpec(Contract):
    field: str
    selector: str
    kind: str = 'classification'
    expectation: str = 'unknown'
    tokens_selector: Optional[str] = None
    offset_unit: str = 'codepoint'
    scheme: str = 'none'
    allow_overlap: bool = True
    status_selector: Optional[str] = None
    required_statuses: tuple = ('complete',)
    answerable_selector: Optional[str] = None
    content_source: Optional[str] = None
    content_id_selector: Optional[str] = None
    def __post_init__(self):
        selector(self.field); selector(self.selector)
        choice(self.kind, {'classification','multilabel','token','span','qa'}, 'annotation kind')
        choice(self.expectation, {'required','optional','unknown','not_applicable'}, 'annotation expectation')
        choice(self.offset_unit, {'codepoint','utf8','utf16','token'}, 'offset unit')
        choice(self.scheme, {'none','BIO','BIOES','BILOU'}, 'tag scheme')
        if not isinstance(self.allow_overlap, bool): raise ValueError('allow_overlap must be boolean.')
        for v in (self.tokens_selector, self.status_selector, self.answerable_selector):
            if v: selector(v)
        if not isinstance(self.required_statuses,(list,tuple)) or any(lexical_status is None or not isinstance(lexical_status,str) or not lexical_status for lexical_status in self.required_statuses):raise ValueError('Required statuses require an array of strings.')
        object.__setattr__(self, 'required_statuses', tuple(self.required_statuses))
        if self.kind == 'token' and not self.tokens_selector: raise ValueError('Token labels require supplied tokens.')
        if self.content_source and not self.content_id_selector: raise ValueError('Associated annotations require an explicit content identity selector.')
        if self.content_id_selector: selector(self.content_id_selector)


@dataclass(frozen=True)
class TextTaskSpec(Contract):
    kind: str = 'corpus'
    input_fields: tuple = ()
    output_fields: tuple = ()
    required_outputs: bool = False
    def __post_init__(self):
        choice(self.kind, {'corpus','classification','multilabel','token','span','qa','generation','conversation','retrieval'}, 'text task')
        for name in ('input_fields','output_fields'):
            vals=getattr(self,name)
            if not isinstance(vals,(list,tuple)) or any(not isinstance(x,str) or not x for x in vals): raise ValueError('Task fields require names.')
            object.__setattr__(self,name,tuple(vals))
        if not isinstance(self.required_outputs,bool): raise ValueError('required_outputs must be boolean.')


@dataclass(frozen=True)
class TextConversationSpec(Contract):
    messages_selector: Optional[str] = 'messages'
    conversation_selector: Optional[str] = None
    order_selector: Optional[str] = None
    role_selector: str = 'role'
    content_selector: str = 'content'
    calls_selector: str = 'tool_calls'
    call_id_selector: str = 'tool_call_id'
    roles: tuple = ('system','developer','user','assistant','tool')
    require_tool_closure: bool = False
    require_completion: bool = False
    def __post_init__(self):
        for v in (self.messages_selector,self.conversation_selector,self.order_selector,self.role_selector,self.content_selector,self.calls_selector,self.call_id_selector):
            if v: selector(v)
        if self.messages_selector is None and not (self.conversation_selector and self.order_selector):
            raise ValueError('Flat messages require conversation identity and explicit order.')
        if not isinstance(self.roles,(list,tuple)):raise ValueError('Roles require an array.')
        object.__setattr__(self,'roles',tuple(self.roles))
        if not self.roles or any(not isinstance(x,str) or not x for x in self.roles): raise ValueError('Explicit roles are required.')
        for x in (self.require_tool_closure,self.require_completion):
            if not isinstance(x,bool): raise ValueError('Conversation requirements must be boolean.')


@dataclass(frozen=True)
class TextRetrievalSpec(Contract):
    kind: str = 'document'
    parent_source: Optional[str] = None
    parent_selector: Optional[str] = None
    field: Optional[str] = None
    parent_field: Optional[str] = None
    extractive: bool = False
    start_selector: str = 'start'
    end_selector: str = 'end'
    offset_unit: str = 'codepoint'
    query_source: Optional[str] = None
    query_selector: str = 'query_id'
    target_source: Optional[str] = None
    target_selector: str = 'document_id'
    grade_selector: str = 'relevance'
    positive_grades: tuple = (1,)
    def __post_init__(self):
        choice(self.kind, {'document','chunk','query','judgment','reference'}, 'retrieval kind')
        choice(self.offset_unit, {'codepoint','utf8','utf16'}, 'retrieval offsets')
        if not isinstance(self.extractive,bool): raise ValueError('extractive must be boolean.')
        for v in (self.parent_selector,self.start_selector,self.end_selector,self.query_selector,self.target_selector,self.grade_selector):
            if v: selector(v)
        if self.kind=='chunk' and not (self.parent_source and self.parent_selector): raise ValueError('Chunks require a parent binding.')
        if self.kind in {'judgment','reference'} and not (self.query_source and self.target_source): raise ValueError('References require query and target source bindings.')
        if not isinstance(self.positive_grades,(list,tuple)):raise ValueError('Positive grades require an array.')
        object.__setattr__(self,'positive_grades',tuple(self.positive_grades))
        if any(not isinstance(x,(str,int,float)) or isinstance(x,bool) for x in self.positive_grades): raise ValueError('Grades require finite scalar values.')
        json.dumps(self.positive_grades,allow_nan=False)


@dataclass(frozen=True)
class TextInputSpec(Contract):
    id: str
    source: TextSourceSpec
    fields: tuple = ()
    role: str = 'corpus'
    namespace: Optional[str] = None
    id_selector: Optional[str] = None
    split_selector: Optional[str] = None
    task: TextTaskSpec = field(default_factory=TextTaskSpec)
    annotations: tuple = ()
    conversation: Optional[TextConversationSpec] = None
    retrieval: Optional[TextRetrievalSpec] = None
    assets: tuple = ()
    def __post_init__(self):
        selector(self.id); nested(self,'source',TextSourceSpec); nested(self,'task',TextTaskSpec)
        sequence(self,'fields',TextFieldSpec); sequence(self,'annotations',TextAnnotationSpec); sequence(self,'assets',AssetSpec)
        for n,c in (('conversation',TextConversationSpec),('retrieval',TextRetrievalSpec)):
            if getattr(self,n) is not None: nested(self,n,c)
        choice(self.role, {'corpus','train','validation','test','evaluation','version','documents','chunks','queries','judgments','annotations'}, 'source role')
        for v in (self.id_selector,self.split_selector):
            if v: selector(v)
        names=[x.name for x in self.fields]
        if len(set(names))!=len(names): raise ValueError('Unique field names required.')
        if set(self.task.input_fields+self.task.output_fields)-set(names): raise ValueError('Task references undeclared fields.')
        if any(a.field not in names and not a.content_source for a in self.annotations): raise ValueError('Annotation field is undeclared.')


@dataclass(frozen=True)
class TextEvaluationSpec(Contract):
    comparisons: tuple = ()
    def __post_init__(self):
        if not isinstance(self.comparisons,(list,tuple)) or any(not isinstance(x,(list,tuple)) for x in self.comparisons):raise ValueError('Comparisons require an array of source pairs.')
        pairs=tuple(tuple(x) for x in self.comparisons)
        if any(len(x)!=2 or x[0]==x[1] for x in pairs) or len(set(pairs))!=len(pairs): raise ValueError('Comparisons require distinct unique source pairs.')
        object.__setattr__(self,'comparisons',pairs)


@dataclass(frozen=True)
class TextAuditSpec(Contract):
    inputs: tuple
    evaluation: TextEvaluationSpec = field(default_factory=TextEvaluationSpec)
    allowed_roots: tuple = ()
    def __post_init__(self):
        sequence(self,'inputs',TextInputSpec); nested(self,'evaluation',TextEvaluationSpec)
        sources={x.id:x for x in self.inputs}
        if not sources or len(sources)!=len(self.inputs): raise ValueError('Unique input IDs required.')
        for pair in self.evaluation.comparisons:
            if set(pair)-set(sources): raise ValueError('Comparison source is undeclared.')
        for item in self.inputs:
            for a in item.annotations:
                if a.content_source:
                    if a.content_source not in sources or not sources[a.content_source].id_selector or a.field not in {f.name for f in sources[a.content_source].fields}:raise ValueError('Associated annotation content binding is undeclared.')
            r=item.retrieval
            if r:
                for sid in (r.parent_source,r.query_source,r.target_source):
                    if sid and sid not in sources: raise ValueError('Relationship source is undeclared.')
                    if sid and not sources[sid].id_selector: raise ValueError('Relationship targets require explicit lexical identity selectors.')
                if r.field and r.field not in {f.name for f in item.fields}: raise ValueError('Relationship field is undeclared.')
                if r.parent_source and r.parent_field and r.parent_field not in {f.name for f in sources[r.parent_source].fields}: raise ValueError('Parent field is undeclared.')
        if not isinstance(self.allowed_roots,(list,tuple)) or any(not isinstance(p,(str,Path)) for p in self.allowed_roots):raise ValueError('Allowed roots require an array of paths.')
        object.__setattr__(self,'allowed_roots',tuple(str(Path(p).resolve()) for p in self.allowed_roots))
    @classmethod
    def from_dict(cls,value,*,base_directory=None):
        if base_directory is not None:
            import copy
            value=copy.deepcopy(value)
            value['allowed_roots']=[str((Path(base_directory)/p).resolve()) for p in value.get('allowed_roots',[])]
            for item in value.get('inputs',[]):item['source']['path']=str((Path(base_directory)/item['source']['path']).resolve())
        result=_construct(cls,value)
        return result


@dataclass(frozen=True)
class TextWorkLimits(Contract):
    max_depth: int = 32
    max_nested_items: int = 10000
    max_items: int = 30000000
    max_supplied_tokens: int = 100000000
    max_annotations: int = 50000000
    max_assets: int = 100000
    lexical_units: int = 50000
    lexical_graphemes: int = 20000
    shingle_positions: int = 25000000
    signature_work: int = 200000000
    candidates: int = 250000
    verification_visits: int = 100000000
    vocabulary_tokens: int = 100000000
    language_units: int = 10000
    embedding_windows: int = 2000
    windows_per_parent: int = 16
    semantic_pairs: int = 2000000
    tokenizer_bytes: int = 64*1024**2
    tokenizer_tokens: int = 1000000
    private_bytes: int = 32*1024**2
    details: int = 100
    witnesses: int = 5
    def __post_init__(self):
        for k,v in asdict(self).items(): _positive(v,k,integer=True)


@dataclass(frozen=True)
class TextModelOptions(Contract):
    language: bool = False
    languages: tuple = ('ENGLISH','HINDI','SPANISH','FRENCH','GERMAN','CHINESE','ARABIC')
    embedding_directory: Optional[str] = None
    embedding_revision: str = 'fd1525a9fd15316a2d503bf26ab031a61d056e98'
    long_documents: str = 'token_windows_v1'
    tokenizer: bool = False
    embeddings: bool = True
    def __post_init__(self):
        if not isinstance(self.language,bool): raise ValueError('language must be boolean.')
        if not isinstance(self.tokenizer,bool) or not isinstance(self.embeddings,bool):raise ValueError('Model selections must be boolean.')
        if self.tokenizer and not self.embedding_directory:raise ValueError('Tokenizer investigation requires the pinned local E5 directory.')
        choice(self.long_documents, {'token_windows_v1','exclude_long'}, 'long-document method')
        if self.embedding_revision!='fd1525a9fd15316a2d503bf26ab031a61d056e98': raise ValueError('M6 supports the pinned E5-small revision only.')
        if not isinstance(self.languages,(list,tuple)) or any(not isinstance(x,str) or not x for x in self.languages):raise ValueError('Languages require an array of names.')
        object.__setattr__(self,'languages',tuple(self.languages))
        if self.language and (len(self.languages)<2 or len(set(self.languages))!=len(self.languages)): raise ValueError('Language identification requires at least two distinct languages.')


@dataclass(frozen=True)
class TextAnalysisConfig(Contract):
    execution: ExecutionOptions = field(default_factory=ExecutionOptions)
    limits: TextWorkLimits = field(default_factory=TextWorkLimits)
    models: TextModelOptions = field(default_factory=TextModelOptions)
    representations: tuple = ('raw','nfc')
    seed: int = 0
    near_duplicates: bool = True
    passages: bool = True
    vocabulary: bool = True
    lexical_complete: bool = False
    near_threshold: float = .80
    minimum_passage: int = 50
    def __post_init__(self):
        nested(self,'execution',ExecutionOptions); nested(self,'limits',TextWorkLimits); nested(self,'models',TextModelOptions)
        if self.execution.backend!='duckdb_local': raise ValueError('Text requires supervised DuckDB execution.')
        for k in ('near_duplicates','passages','vocabulary','lexical_complete'):
            if not isinstance(getattr(self,k),bool): raise ValueError(f'{k} must be boolean.')
        if isinstance(self.seed,bool) or not isinstance(self.seed,int) or not 0<=self.seed<2**64: raise ValueError('seed must be an unsigned 64-bit integer.')
        if isinstance(self.near_threshold,bool) or not isinstance(self.near_threshold,(int,float)) or not 0<self.near_threshold<=1: raise ValueError('Invalid near threshold.')
        _positive(self.minimum_passage,'minimum_passage',integer=True)
        values=tuple(self.representations)
        if 'raw' not in values or len(set(values))!=len(values) or set(values)-{'raw','nfc','casefold','whitespace'}: raise ValueError('Explicit supported representations including raw required.')
        object.__setattr__(self,'representations',values)


@dataclass(frozen=True)
class TextReportArtifacts(ReportArtifacts):
    private_manifest_path: Optional[str] = field(default=None,kw_only=True)


@dataclass
class TextAuditResult:
    profile: dict
    checks: list
    evidence: list
    findings: list
    coverage: dict
    execution: dict
    generated_at: str
    private: dict = field(repr=False)
    schema_version: str = '1.5'
    methodology_id: str = 'text_reliability_v1'
    guidance: dict = field(default_factory=dict, kw_only=True)  # finding_guidance_v1 and later; absent before
    @property
    def source_paths(self): return tuple(self.private['protected_paths'])
    def to_dict(self):
        return exact_json({k:getattr(self,k) for k in ('schema_version','methodology_id','profile','checks','evidence','findings','coverage','execution','generated_at')}|({'guidance':self.guidance} if self.guidance else {}))
    def json_text(self): return json.dumps(self.to_dict(),ensure_ascii=False,indent=2,allow_nan=False)
    def write_json(self,path,**kwargs):
        from datatrust.text_private import write_text_json
        return write_text_json(self,path,**kwargs)
    def generate_artifacts(self,path,**kwargs):
        from datatrust.text_private import generate_artifacts
        return generate_artifacts(self,path,**kwargs)
    def generate_report(self,path,**kwargs):
        artifacts=self.generate_artifacts(path,**kwargs)
        return artifacts.pdf_path or artifacts.html_path
    def resolve_evidence(self,reference,*,allowed_roots,reveal_content=False,max_chars=240):
        from datatrust.text_private import resolve_evidence
        return resolve_evidence(self.private,reference,allowed_roots=allowed_roots,reveal_content=reveal_content,max_chars=max_chars,expected_digest=self.profile['private_manifest_sha256'])
