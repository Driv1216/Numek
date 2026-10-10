import copy
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from pypdf import PdfReader

from datatrust import DataTrust,AnalysisConfig,DatasetSpec,TaskSpec,RegressionOptions,TargetExpectations,RegressionRelationLimits
from datatrust.renderer import render_analysis_result,ArtifactCollisionError
from datatrust.pdf import PDFRenderError


def result(tmp_path,options=None):
    source=tmp_path/'source.csv';pd.DataFrame({'input':np.arange(40),'outcome':np.arange(40)}).to_csv(source,index=False)
    return DataTrust.from_spec(DatasetSpec(source,dataset_name='<Regression & review>'),TaskSpec('regression','outcome'),AnalysisConfig(regression=options)).analyze_result()


def test_eight_topics_pdf_json_no_reanalysis_and_no_score(tmp_path,monkeypatch):
    r=result(tmp_path,RegressionOptions(TargetExpectations('count',maximum=30,units='<b>bikes</b>')))
    before=copy.deepcopy(r.to_dict())
    monkeypatch.setattr(DataTrust,'analyze_result',lambda _:pytest.fail('export reanalyzed'))
    bundle=r.generate_artifacts(tmp_path/'report.pdf',format='pdf',json_path=tmp_path/'r.json')
    text=' '.join('\n'.join(page.extract_text() for page in PdfReader(bundle.pdf_path).pages).split())
    for heading in ['1. Regression Review Summary','2. Priority Review Actions','3. Dataset, Target, and Declared Expectations','4. Target Coverage and Distribution','5. Target Relationships and Feature Availability','6. Missingness, Repetition, and Feature Evidence','7. Coverage, Methods, Scoring Availability, and Limitations','8. Technical Appendix']:assert heading in text
    for forbidden in ['Overall reliability score','Risk band','R²','RMSE']:assert forbidden not in text
    html=Path(bundle.html_path).read_text()
    assert '&lt;b&gt;bikes&lt;/b&gt;' in html and '<b>bikes</b>' not in html
    assert '<svg' in html and 'Histogram count table' in text
    actions=html.split('2. Priority Review Actions')[1].split('3. Dataset, Target')[0]
    assert 'Based on 40 finite target values.' in actions
    assert all(label not in actions for label in ['Population: Name:', 'Denominator: Not set', 'Detail:', '..'])
    assert json.loads(Path(bundle.json_path).read_text())==before and r.to_dict()==before


@pytest.mark.parametrize('target_only',[False,True])
def test_presentation_empty_states_and_expected_inspection_bounds_leave_json_unchanged(tmp_path,target_only):
    from datatrust import FidelityInspectionLimits
    source=tmp_path/'scope.csv'
    frame=pd.DataFrame({'outcome':np.arange(40)})
    if not target_only:frame['input']=np.arange(40)**2
    frame.to_csv(source,index=False)
    config=AnalysisConfig(fidelity_inspection=FidelityInspectionLimits(max_records=2))
    r=DataTrust.from_spec(DatasetSpec(source),TaskSpec('regression','outcome'),config).analyze_result()
    before=r.json_text()
    html=render_analysis_result(r);main=html.split('8. Technical Appendix')[0]
    assert 'Observed relationship</th>' not in main and 'Example group rows / distinct targets</th>' not in main
    assert 'No target relationships were verified in the searched scope.' in main
    assert ('Repeated-input review does not apply without feature columns.' if target_only else
            'No target variation was observed within repeated inputs; no examples are available.') in main
    if target_only:assert 'User-declared availability</th>' not in main
    assert 'Source-token inspection coverage' in html and 'expected coverage disclosure, not an analysis failure' in html
    assert 'Analysis incomplete' not in html and r.json_text()==before
    # Unexpected inspection unavailability must retain its warning, not become planned coverage.
    warning=next(w for w in r.parsing_warnings if w['code']=='inspection_incomplete')
    warning['inspected_population']['stopping_reason']='inspection_unavailable'
    html=render_analysis_result(r)
    assert 'expected coverage disclosure, not an analysis failure' not in html
    assert '<strong>inspection_incomplete</strong>' in html


def test_small_relationship_technical_only_and_bounded_not_failure(tmp_path):
    r=result(tmp_path,RegressionOptions(relation_limits=RegressionRelationLimits(max_single_comparisons=1)))
    html=render_analysis_result(r)
    assert 'Configured pool/work limits intentionally bounded' in html and 'Analysis incomplete' not in html
    source=tmp_path/'tiny.csv';source.write_text('input,outcome\n1,1\n2,2\n')
    r=DataTrust(source,'outcome',task='regression').analyze_result()
    assert 'Qualified technical evidence only' in render_analysis_result(r)
    assert not any('relationships_' in f['code'] for f in r.findings)


def test_regression_artifact_safety_and_pdf_failure_retention(tmp_path,monkeypatch):
    r=result(tmp_path)
    with pytest.raises(ArtifactCollisionError):r.generate_artifacts(r.dataset.path)
    occupied=tmp_path/'occupied.html';occupied.write_text('unrelated')
    with pytest.raises(ArtifactCollisionError):r.generate_artifacts(occupied)
    def fail(*args,**kwargs):raise PDFRenderError('PDF unavailable')
    monkeypatch.setattr('datatrust.pdf.render_pdf_report',fail)
    with pytest.raises(PDFRenderError) as exc:r.generate_artifacts(tmp_path/'failed.pdf',format='pdf',json_path=tmp_path/'failed.json')
    assert Path(exc.value.artifacts.html_path).exists() and Path(exc.value.artifacts.json_path).exists()


@pytest.mark.parametrize('change_bytes',[False,True])
def test_pdf_metadata_only_changes_allowed_but_changed_bytes_rejected(tmp_path,monkeypatch,change_bytes):
    import weasyprint
    from datatrust.pdf import render_pdf_report
    from datatrust.ingestion import source_signature
    source=tmp_path/'canonical.html';source.write_text('<html><body>Outcome review</body></html>')
    signature=source_signature(source);calls=0
    def metadata_change(path):
        nonlocal calls
        calls+=1
        return (*signature[:4],signature[4]+calls)
    monkeypatch.setattr('datatrust.ingestion.source_signature',metadata_change)
    original=weasyprint.HTML
    class DuringConversion:
        def __init__(self,*args,**kwargs):self.html=original(*args,**kwargs)
        def write_pdf(self):
            content=self.html.write_pdf()
            if change_bytes:source.write_text('<html><body>Changed review</body></html>')
            return content
    monkeypatch.setattr(weasyprint,'HTML',DuringConversion)
    destination=tmp_path/'canonical.pdf'
    if change_bytes:
        with pytest.raises(PDFRenderError,match='changed during conversion'):render_pdf_report(source,destination)
        assert not destination.exists() and source.exists()
    else:
        render_pdf_report(source,destination)
        assert destination.read_bytes().startswith(b'%PDF')
