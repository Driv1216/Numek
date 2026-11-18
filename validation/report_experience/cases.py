"""Report Experience Stage 0 matrix: which completed evidence each measured report is rendered from.

Two kinds of case:
- fresh: the analysis is run now with the current code (cheap core, M3 and regression workflows). Its analysis JSON is
  the integrity baseline for later stages.
- stored: the completed analysis JSON already recorded by an earlier milestone is re-rendered with the current templates.
  This is how every milestone has refreshed its reports (no reanalysis). The stored file is the baseline and is read only.

Nothing here changes analytical code or historical artifacts. Generated inputs live under work.nosync/ (git-ignored).
"""
import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
VALIDATION = REPO / 'validation'
WORK = Path(__file__).resolve().parent / 'work.nosync'

# The Bank Full declarations used by the contextual tests and the WS4 delivery check (tests/test_contextual.py).
BANK_CONTEXT = {"prediction": {"objective": "decide which clients to call", "point": "before the first contact"},
                "columns": {"duration": {"availability": "unavailable_at_prediction"},
                            "pdays": {"sentinels": [{"value": -1, "meaning": "not_applicable"}],
                                      "applies_when": {"column": "previous", "op": ">", "value": 0}, "unit": "days"},
                            "previous_campaign_outcome": {"placeholders": {"unknown": "not_applicable"},
                                                          "applies_when": {"column": "previous", "op": ">", "value": 0}},
                            "contact": {"placeholders": {"unknown": "not_collected"}}}}


def sha256(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b''):
            digest.update(chunk)
    return digest.hexdigest()


class StoredResult:
    """A completed, recorded result dict presented to the renderer exactly as the milestone refresh scripts do
    (validation/m4/refresh_reports.py): attribute reads come from the stored dict; nothing is recomputed."""

    def __init__(self, data):
        self._data = data
        self.schema_version = data['schema_version']
        self.source_paths = ()
        if 'inputs' in data:
            self.inputs = data['inputs']

    def to_dict(self):
        return self._data

    def json_text(self):
        return json.dumps(self._data, ensure_ascii=False, indent=2, allow_nan=False)

    def __getattr__(self, key):
        try:
            return self._data[key]
        except KeyError as exc:
            raise AttributeError(key) from exc


@dataclass
class Case:
    name: str
    group: str                 # matrix row (K)
    mode: str                  # fresh | stored
    description: str
    variants: tuple = ('canonical',)   # canonical = render_analysis_result; app = the browser app's legacy_html path
    build: object = None       # callable -> result
    stored_path: Path = None
    stored_html: Path = None   # an earlier rendering of the same stored JSON, for a fidelity check
    heavy: bool = False        # artifacts kept only under work.nosync/
    inputs: dict = field(default_factory=dict)


def _fresh(path, task, config=None, **options):
    def build():
        from datatrust import AnalysisConfig, DataTrust, DatasetSpec
        chosen = config if config is not None else (AnalysisConfig(**options) if options else None)
        return DataTrust.from_spec(DatasetSpec(str(path)), task, chosen).analyze_result()
    return build


def _stored(path):
    def build():
        return StoredResult(json.loads(Path(path).read_text()))
    return build


def wide_flagged_csv(path, rows=5000, cols=1000):
    """Deterministic wide data where many columns share the same problems, the shape that turns a printed register into
    hundreds of pages: 400 mostly-missing, 100 constant, 100 heavy-tailed, the rest ordinary."""
    if path.exists():
        return path
    import numpy as np
    import pandas as pd
    rng = np.random.default_rng(7)
    data = {}
    for i in range(cols - 1):
        if i < 400:
            values = np.round(rng.normal(size=rows), 3)
            values[rng.random(rows) < 0.6] = np.nan
        elif i < 500:
            values = np.full(rows, 1.0)
        elif i < 600:
            values = np.round(rng.standard_cauchy(rows), 3)
        else:
            values = np.round(rng.normal(size=rows), 3)
        data[f'm{i:04d}'] = values
    frame = pd.DataFrame(data)
    frame['y'] = rng.choice(['yes', 'no'], rows, p=[0.2, 0.8])
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)
    return path


def cases():
    from datatrust import AnalysisConfig, RegressionOptions, TaskSpec
    from validation.ws4.run_scalability import tall_csv, wide_csv
    prepared = VALIDATION / 'data/prepared'
    mutations = VALIDATION / 'data/mutations'
    adult_target = 'annual_income_over_50k'
    WORK.mkdir(parents=True, exist_ok=True)
    out = [
        Case('german_credit', '1 small classification', 'fresh', 'German Credit 1,000 x 21',
             ('canonical', 'app'), _fresh(prepared / 'german_credit.csv', TaskSpec('classification', target='credit_risk'))),
        Case('bank_full', '2 Bank Full', 'fresh', 'Bank Marketing 45,211 x 17, no declarations',
             ('canonical', 'app'), _fresh(prepared / 'bank_marketing.csv', TaskSpec('classification', target='subscribed_term_deposit'))),
        Case('bank_full_declared', '2 Bank Full', 'fresh', 'Bank Marketing with the contextual-test declarations',
             ('canonical', 'app'), _fresh(prepared / 'bank_marketing.csv', TaskSpec('classification', target='subscribed_term_deposit'), context=BANK_CONTEXT)),
        Case('german_unlabeled', '1 small classification', 'fresh', 'German Credit, target-free profile',
             ('canonical',), _fresh(prepared / 'german_credit.csv', TaskSpec('dataset_profile'))),
    ]
    for name in ('strong_leakage', 'feature_missingness_100', 'duplicates'):
        out.append(Case(f'mutation_{name}', '4 severe findings', 'fresh', f'Adult mutation: {name}', ('canonical',),
                        _fresh(mutations / f'{name}.csv', TaskSpec('classification', target=adult_target))))
    for cols in (200, 1000, 5000):
        path = WORK / f'wide_{cols}.csv'
        out.append(Case(f'wide_{cols}', '3 wide', 'fresh', f'WS4 wide generator: 5,000 rows x {cols} columns',
                        ('canonical', 'app'), lambda p=path, c=cols: _fresh(wide_csv(p, 5000, c), TaskSpec('classification', target='y'))(),
                        heavy=cols >= 1000, inputs={'generator': 'validation.ws4.run_scalability.wide_csv', 'rows': 5000, 'cols': cols}))
    flagged = WORK / 'wide_flagged_1000.csv'
    out.append(Case('wide_flagged_1000', '4 severe findings', 'fresh',
                    '5,000 x 1,000 with 400 mostly-missing, 100 constant and 100 heavy-tailed columns', ('canonical', 'app'),
                    lambda: _fresh(wide_flagged_csv(flagged), TaskSpec('classification', target='y'))(), heavy=True,
                    inputs={'generator': 'validation.report_experience.cases.wide_flagged_csv', 'seed': 7}))
    tall = WORK / 'tall_1m.csv'
    out.append(Case('tall_1m', '5 large', 'fresh', 'WS4 tall generator: 1M rows x 10 columns', ('canonical',),
                    lambda: _fresh(tall_csv(tall, 1_000_000), TaskSpec('classification', target='y'))(), heavy=True,
                    inputs={'generator': 'validation.ws4.run_scalability.tall_csv', 'rows': 1_000_000}))
    regression = json.loads((VALIDATION / 'regression/manifest.json').read_text())['datasets']['bike_hour']
    out.append(Case('bike_hour', '6 advanced and regression', 'fresh', 'Bike Sharing hourly regression (count expectations)',
                    ('canonical',), _fresh(VALIDATION / 'regression' / regression['file'], TaskSpec('regression', target='cnt'),
                                           regression=RegressionOptions.from_dict({'expectations': regression['expectations']}))))
    scene = json.loads((VALIDATION / 'm3/manifest.json').read_text())['datasets']['scene']
    out.append(Case('m3_scene', '6 advanced and regression', 'fresh', 'M3 Scene multilabel, 2,407 x 300',
                    ('canonical',), _fresh(VALIDATION / 'm3' / scene['file'], TaskSpec.from_dict(scene['task']),
                                           AnalysisConfig.from_dict(scene['config']))))
    for name in ('contaminated', 'wide', 'long_headers'):
        folder = VALIDATION / 'm4/results/reports' / name
        out.append(Case(f'm4_{name}', '6 advanced and regression', 'stored', f'M4 {name} (stored completed JSON)', ('canonical',),
                        _stored(folder / 'analysis.json'), folder / 'analysis.json', folder / 'report.html'))
    for name in ('retail', 'beijing'):
        path = VALIDATION / 'm5/reports' / f'{name}.json'
        out.append(Case(f'm5_{name}', '7 temporal', 'stored', f'M5 public corpus: {name}', ('canonical',),
                        _stored(path), path, VALIDATION / 'm5/reports' / f'{name}.html'))
    path = VALIDATION / 'm5/reports/controlled/long_headers_reviewed.json'
    out.append(Case('m5_long_headers', '7 temporal', 'stored', 'M5 controlled 16 long escaped headers', ('canonical',),
                    _stored(path), path, path.with_suffix('.html')))
    scifact = next((VALIDATION / 'm6/results/reports').glob('*/scifact.json'), None)
    if scifact:
        out.append(Case('m6_scifact', '8 text', 'stored', 'M6 SciFact, references-only default', ('canonical',),
                        _stored(scifact), scifact, scifact.with_suffix('.html')))
    for name, file in (('classification', 'final.json'),):
        path = VALIDATION / 'm7/results/reports' / name / file
        out.append(Case(f'm7_{name}', '9 image', 'stored', f'M7 {name}, private default', ('canonical',),
                        _stored(path), path, path.with_suffix('.html')))
    overlay = VALIDATION / 'm7/results/review_corrections/final-synthetic-overlay.json'
    if overlay.exists():
        out.append(Case('m7_overlay', '9 image', 'stored', 'M7 synthetic overlay, explicit disclosure', ('canonical',),
                        _stored(overlay), overlay, overlay.with_suffix('.html')))
    for name in ('pdf_financial', 'docx_financial'):
        path = VALIDATION / 'm9/results/reports' / f'{name}.json'
        out.append(Case(f'm9_{name}', '10 cross-representation', 'stored', f'M9 {name}', ('canonical',),
                        _stored(path), path, path.with_suffix('.html')))
    return out
