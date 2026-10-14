"""Strict M7 contracts; importing them does not import image/model runtimes."""
from dataclasses import asdict, dataclass, field, replace
import copy
import json
import math
from pathlib import Path

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
        return exact_json(asdict(self))


def choice(value, values, label):
    if value not in values:
        raise ValueError(f'Unsupported {label}.')


def name(value):
    if not isinstance(value, str) or not value or any(ord(c) < 32 or 0xd800 <= ord(c) <= 0xdfff for c in value):
        raise ValueError('Names and selectors must be nonempty strings without controls.')


def nested(owner, key, cls):
    value = getattr(owner, key)
    if isinstance(value, dict):
        object.__setattr__(owner, key, cls.from_dict(value))
    elif not isinstance(value, cls):
        raise ValueError(f'{key} requires {cls.__name__}.')


def collection(owner, key, cls):
    values = getattr(owner, key)
    if not isinstance(values, (list, tuple)):
        raise ValueError(f'{key} requires an array.')
    converted = tuple(cls.from_dict(x) if isinstance(x, dict) else x for x in values)
    if any(not isinstance(x, cls) for x in converted):
        raise ValueError(f'Invalid {key}.')
    object.__setattr__(owner, key, converted)


@dataclass(frozen=True)
class ImageSourceSpec(Contract):
    path: str
    format: str = 'directory'
    asset_root: str = None
    layout: str = 'unlabeled'
    encoding: str = 'utf-8'
    json_columns: tuple = ()
    def __post_init__(self):
        name(str(self.path)); object.__setattr__(self, 'path', str(self.path))
        choice(self.format, {'directory', 'csv', 'jsonl', 'coco', 'yolo'}, 'image source format')
        choice(self.layout, {'unlabeled', 'class_subdirectories'}, 'directory layout')
        if self.layout != 'unlabeled' and self.format != 'directory':
            raise ValueError('Class subdirectories require a directory source.')
        if self.encoding not in {'utf-8', 'utf-8-sig'}:
            raise ValueError('Image manifests require UTF-8.')
        if not isinstance(self.json_columns, (list, tuple)) or len(set(self.json_columns)) != len(self.json_columns):
            raise ValueError('json_columns requires unique names.')
        for x in self.json_columns: name(x)
        object.__setattr__(self, 'json_columns', tuple(self.json_columns))
        if self.asset_root is not None: name(str(self.asset_root)); object.__setattr__(self, 'asset_root', str(self.asset_root))


@dataclass(frozen=True)
class ImageMappingSpec(Contract):
    path: str = 'path'
    logical_id: str = None
    split: str = None
    groups: tuple = ()
    labels: str = 'labels'
    objects: str = 'objects'
    mask: str = 'mask'
    status: str = None
    checksum: str = None
    width: str = 'width'
    height: str = 'height'
    def __post_init__(self):
        for key, value in asdict(self).items():
            if key == 'groups':
                if not isinstance(value, (tuple, list)) or len(set(value)) != len(value): raise ValueError('groups requires unique selectors.')
                for x in value: name(x)
                object.__setattr__(self, key, tuple(value))
            elif value is not None: name(value)


@dataclass(frozen=True)
class ImageTaskSpec(Contract):
    kind: str = 'unlabeled'
    def __post_init__(self):
        choice(self.kind, {'unlabeled', 'classification', 'multilabel_classification', 'detection', 'segmentation'}, 'image task')


@dataclass(frozen=True)
class ImageAnnotationSpec(Contract):
    scheme: str = 'default'
    categories: tuple = ()
    expectation: str = 'unknown'
    status_mapping: dict = field(default_factory=dict)
    box_format: str = 'xyxy'
    coordinate_frame: str = 'encoded'
    frame_width: int = None
    frame_height: int = None
    transform: tuple = ()
    mask_encoding: str = 'semantic_png'
    background: tuple = (0,)
    ignore: tuple = ()
    color_mapping: dict = field(default_factory=dict)
    missing_yolo_labels_are_negative: bool = False
    derive_coco_labels: bool = False
    associated_source: ImageSourceSpec = None
    associated_key: str = None
    def __post_init__(self):
        name(self.scheme)
        choice(self.expectation, {'required', 'optional', 'unknown', 'not_applicable'}, 'annotation expectation')
        choice(self.box_format, {'xyxy', 'xywh', 'normalized_cxcywh'}, 'box format')
        choice(self.coordinate_frame, {'encoded', 'oriented', 'declared', 'unknown'}, 'coordinate frame')
        choice(self.mask_encoding, {'semantic_png', 'binary_png', 'rgb_png', 'coco'}, 'mask encoding')
        for key in ('categories', 'background', 'ignore'):
            values = getattr(self, key)
            if not isinstance(values, (list, tuple)) or any(isinstance(v, bool) or not isinstance(v, (int, str)) for v in values): raise ValueError('Category declarations require scalar IDs.')
            if len(set(values)) != len(values): raise ValueError('Category declarations must be unique.')
            object.__setattr__(self, key, tuple(values))
        if set(self.background) & set(self.ignore): raise ValueError('Background and ignore values overlap.')
        if not isinstance(self.status_mapping, dict) or any(not isinstance(k, str) or v not in {'complete', 'partial', 'uncertain', 'intentionally_unlabeled', 'unknown'} for k, v in self.status_mapping.items()): raise ValueError('Invalid status mapping.')
        if not isinstance(self.color_mapping, dict): raise ValueError('Invalid color mapping.')
        for k, v in self.color_mapping.items():
            parts = k.split(',')
            if len(parts) != 3 or any(not p.isdigit() or not 0 <= int(p) <= 255 for p in parts) or isinstance(v, bool) or not isinstance(v, (int, str)): raise ValueError('RGB mappings use r,g,b keys and scalar categories.')
        for key in ('frame_width', 'frame_height'):
            if getattr(self, key) is not None: _positive(getattr(self, key), key, integer=True)
        if bool(self.frame_width) != bool(self.frame_height): raise ValueError('Declare both frame dimensions.')
        if self.transform:
            if self.coordinate_frame != 'declared' or not self.frame_width or not isinstance(self.transform, (list, tuple)) or len(self.transform) != 6 or any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in self.transform): raise ValueError('Declared affine frame requires dimensions and six finite coefficients.')
            a,b,_,d,e,_=self.transform
            if a*e-b*d == 0: raise ValueError('Frame mapping must be invertible.')
        if self.coordinate_frame == 'declared' and not self.transform: raise ValueError('Declared frame requires an affine mapping to encoded pixels.')
        object.__setattr__(self, 'transform', tuple(self.transform))
        for key in ('missing_yolo_labels_are_negative', 'derive_coco_labels'):
            if not isinstance(getattr(self, key), bool): raise ValueError(f'{key} must be boolean.')
        if self.associated_source is not None:
            nested(self, 'associated_source', ImageSourceSpec)
            if self.associated_source.format not in {'csv', 'jsonl'} or not self.associated_key: raise ValueError('Associated annotations require a manifest and exact key.')
            name(self.associated_key)


@dataclass(frozen=True)
class ImageInputSpec(Contract):
    id: str
    source: ImageSourceSpec
    task: ImageTaskSpec = field(default_factory=ImageTaskSpec)
    mapping: ImageMappingSpec = field(default_factory=ImageMappingSpec)
    annotations: ImageAnnotationSpec = field(default_factory=ImageAnnotationSpec)
    role: str = 'dataset'
    namespace: str = None
    def __post_init__(self):
        name(self.id)
        for key, cls in [('source', ImageSourceSpec), ('task', ImageTaskSpec), ('mapping', ImageMappingSpec), ('annotations', ImageAnnotationSpec)]: nested(self, key, cls)
        choice(self.role, {'dataset', 'train', 'validation', 'test', 'evaluation', 'reference', 'current'}, 'image role')
        if self.namespace is not None: name(self.namespace)
        if self.annotations.associated_source is not None and not self.mapping.logical_id: raise ValueError('Associated annotations require a declared primary logical key.')
        if self.source.layout == 'class_subdirectories' and self.task.kind != 'classification': raise ValueError('Class subdirectories require classification.')
        if self.source.format == 'yolo' and self.task.kind != 'detection': raise ValueError('YOLO supports detection only.')
        if self.source.format == 'coco' and self.task.kind in {'classification', 'multilabel_classification'} and not self.annotations.derive_coco_labels: raise ValueError('COCO classification requires explicit category derivation.')


@dataclass(frozen=True)
class ImageSplitRequirement(Contract):
    left: str
    right: str
    asset_separation: bool = False
    group_separation: bool = False
    group_mode: str = 'per_key'
    def __post_init__(self):
        name(self.left); name(self.right)
        if self.left == self.right: raise ValueError('Split pairs must differ.')
        if not isinstance(self.asset_separation, bool) or not isinstance(self.group_separation, bool): raise ValueError('Separation requirements must be boolean.')
        choice(self.group_mode, {'per_key','composite'}, 'group separation mode')


@dataclass(frozen=True)
class ImageComparisonSpec(Contract):
    reference: str
    current: str
    align_logical_keys: bool = True
    category_mapping: dict = field(default_factory=dict)
    def __post_init__(self):
        name(self.reference); name(self.current)
        if self.reference == self.current or not isinstance(self.align_logical_keys, bool): raise ValueError('Invalid version comparison.')
        if not isinstance(self.category_mapping, dict) or any(not isinstance(k, str) or isinstance(v, bool) or not isinstance(v, (str, int)) for k,v in self.category_mapping.items()): raise ValueError('Invalid category mapping.')


@dataclass(frozen=True)
class ImageAuditSpec(Contract):
    inputs: tuple
    split_requirements: tuple = ()
    comparisons: tuple = ()
    allowed_roots: tuple = ()
    dataset_name: str = None
    purpose: str = None
    def __post_init__(self):
        collection(self, 'inputs', ImageInputSpec); collection(self, 'split_requirements', ImageSplitRequirement); collection(self, 'comparisons', ImageComparisonSpec)
        ids={x.id for x in self.inputs}
        if not ids or len(ids) != len(self.inputs): raise ValueError('Unique image input IDs required.')
        if any({c.reference,c.current}-ids for c in self.comparisons): raise ValueError('Comparison references undeclared inputs.')
        if not isinstance(self.allowed_roots, (list, tuple)): raise ValueError('allowed_roots requires an array.')
        object.__setattr__(self, 'allowed_roots', tuple(str(Path(p).absolute()) for p in self.allowed_roots))
        for key, bound in [('dataset_name',120), ('purpose',1000)]:
            value=getattr(self,key)
            if value is not None and (not isinstance(value,str) or len(value)>bound or any(ord(c)<32 and c not in '\n\t' for c in value)): raise ValueError('Invalid report context.')
    @classmethod
    def from_dict(cls, value, *, base_directory=None):
        value=copy.deepcopy(value)
        if base_directory is not None:
            def source(s):
                for key in ('path','asset_root'):
                    if s.get(key): s[key]=str(Path(base_directory)/s[key])
            for x in value.get('inputs',[]):
                source(x['source'])
                if x.get('annotations',{}).get('associated_source'): source(x['annotations']['associated_source'])
            value['allowed_roots']=[str(Path(base_directory)/p) for p in value.get('allowed_roots',[])]
        return _construct(cls,value)


@dataclass(frozen=True)
class ImageSourceLimits(Contract):
    media_per_input_bytes: int = 64*1024**3
    combined_media_bytes: int = 128*1024**3
    asset_capture_bytes: int = 128*1024**2
    def __post_init__(self):
        for k,v in asdict(self).items(): _positive(v,k,integer=True)


@dataclass(frozen=True)
class ImageWorkLimits(Contract):
    assets: int = 100000
    occurrences: int = 1000000
    annotations: int = 10000000
    pixels_per_asset: int = 32000000
    decode_bytes: int = 512*1024**2
    decoded_pixels: int = 100000000000
    polygon_vertices: int = 10000000
    rle_runs: int = 10000000
    segmentation_pixels: int = 100000000
    posting_visits: int = 100000000
    hamming_comparisons: int = 50000000
    bucket_entries: int = 1024
    candidate_pairs: int = 250000
    embedding_images: int = 10000
    cosine_pairs: int = 25000000
    details: int = 100
    witnesses: int = 5
    private_bytes: int = 64*1024**2
    def __post_init__(self):
        for k,v in asdict(self).items(): _positive(v,k,integer=True)


@dataclass(frozen=True)
class ImageModelOptions(Contract):
    directory: str = None
    mode: str = 'default'
    max_seconds: float = 600
    def __post_init__(self):
        choice(self.mode, {'default','higher_quality'}, 'embedding mode')
        _positive(self.max_seconds,'embedding max_seconds')
        if self.directory is not None: name(str(self.directory)); object.__setattr__(self,'directory',str(self.directory))


def image_execution():
    return replace(ExecutionOptions(),max_source_bytes=1024**3,max_combined_source_bytes=4*1024**3)


@dataclass(frozen=True)
class ImageAnalysisConfig(Contract):
    execution: ExecutionOptions = field(default_factory=image_execution)
    source_limits: ImageSourceLimits = field(default_factory=ImageSourceLimits)
    limits: ImageWorkLimits = field(default_factory=ImageWorkLimits)
    models: ImageModelOptions = field(default_factory=ImageModelOptions)
    near_duplicates: bool = True
    hamming_radius: int = 6
    seed: int = 0
    quality_expectations: dict = field(default_factory=dict)
    def __post_init__(self):
        if isinstance(self.execution,dict): object.__setattr__(self,'execution',ExecutionOptions.from_dict({**asdict(image_execution()),**self.execution}))
        for k,c in [('execution',ExecutionOptions),('source_limits',ImageSourceLimits),('limits',ImageWorkLimits),('models',ImageModelOptions)]: nested(self,k,c)
        if self.execution.backend != 'duckdb_local': raise ValueError('Images require supervised DuckDB execution.')
        if not isinstance(self.near_duplicates,bool): raise ValueError('near_duplicates must be boolean.')
        if isinstance(self.hamming_radius,bool) or not isinstance(self.hamming_radius,int) or not 0<=self.hamming_radius<=6: raise ValueError('The seven-partition index supports radii 0–6.')
        if isinstance(self.seed,bool) or not isinstance(self.seed,int) or not 0<=self.seed<2**64: raise ValueError('seed requires an unsigned 64-bit integer.')
        allowed={'min_width','min_height','min_contrast','min_sharpness','max_dark_fraction','max_bright_fraction'}
        if not isinstance(self.quality_expectations,dict) or set(self.quality_expectations)-allowed or any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or v<0 for v in self.quality_expectations.values()): raise ValueError('Invalid quality expectations.')


@dataclass(frozen=True)
class ImageDisclosureOptions(Contract):
    references: tuple = ()
    overlays: bool = False
    labels: bool = False
    def __post_init__(self):
        if not isinstance(self.references,(list,tuple)) or len(self.references)>20 or len(set(self.references))!=len(self.references): raise ValueError('Select at most twenty distinct image references.')
        for ref in self.references: name(ref)
        object.__setattr__(self,'references',tuple(self.references))
        if not isinstance(self.overlays,bool) or not isinstance(self.labels,bool): raise ValueError('Disclosure selections must be boolean.')


@dataclass(frozen=True)
class ImageReportArtifacts(ReportArtifacts):
    private_manifest_path: str = field(default=None,kw_only=True)


@dataclass
class ImageAuditResult:
    profile: dict
    checks: list
    evidence: list
    findings: list
    coverage: dict
    execution: dict
    generated_at: str
    private: dict = field(repr=False)
    schema_version: str = '1.6'
    methodology_id: str = 'image_reliability_v1'
    @property
    def source_paths(self): return tuple(dict.fromkeys((*self.private['files'],*self.private.get('unavailable',()))))
    def to_dict(self): return exact_json({k:getattr(self,k) for k in ('schema_version','methodology_id','profile','checks','evidence','findings','coverage','execution','generated_at')})
    def json_text(self): return json.dumps(self.to_dict(),ensure_ascii=False,indent=2,allow_nan=False)
    def write_json(self,path,**kwargs):
        from datatrust.image_private import write_image_json
        return write_image_json(self,path,**kwargs)
    def generate_artifacts(self,path,**kwargs):
        from datatrust.image_private import generate_artifacts
        return generate_artifacts(self,path,**kwargs)
    def generate_report(self,path,**kwargs):
        artifacts=self.generate_artifacts(path,**kwargs)
        return artifacts.pdf_path or artifacts.html_path
    def resolve_evidence(self,reference,*,allowed_roots,reveal_image=False,overlays=False,labels=False):
        from datatrust.image_private import resolve_image_evidence
        return resolve_image_evidence(self.private,reference,self.to_dict(),allowed_roots=allowed_roots,reveal_image=reveal_image,overlays=overlays,labels=labels)
