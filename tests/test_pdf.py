import pytest

from datatrust.pdf import PDFRenderError, render_pdf_report


def test_pdf_renderer_rejects_remote_resources(tmp_path):
    html_path = tmp_path / "report.html"
    pdf_path = tmp_path / "report.pdf"
    html_path.write_text(
        '<!doctype html><html><body><img src="https://example.com/image.png"></body></html>',
        encoding="utf-8",
    )

    with pytest.raises(PDFRenderError, match="HTML report is still available"):
        render_pdf_report(html_path, pdf_path)

    assert html_path.exists()
    assert not pdf_path.exists()
