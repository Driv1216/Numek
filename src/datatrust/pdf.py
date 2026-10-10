from pathlib import Path
from urllib.parse import unquote, urlparse
from urllib.request import url2pathname


class PDFRenderError(RuntimeError):
    """Raised when the standalone HTML report cannot be converted to PDF."""

    def __init__(self, message, *, artifacts=None):
        super().__init__(message)
        self.artifacts = artifacts


def render_pdf_report(html_path: Path, output_path: Path, *, expected_html_sha256=None) -> str:
    """Convert a generated local HTML report to a cached PDF artifact."""
    source = Path(html_path).resolve()
    destination = Path(output_path)
    from datatrust.renderer import ArtifactCollisionError, _new_destination, protect_source, publish_bytes
    from datatrust.ingestion import source_digest, source_signature
    protect_source(source, [destination])
    _new_destination(destination)
    signature = source_signature(source)
    digest = source_digest(source)
    if expected_html_sha256 is not None and digest != expected_html_sha256:
        raise PDFRenderError("Canonical HTML changed before conversion. The HTML report is still available.")

    try:
        from weasyprint import HTML, default_url_fetcher
        from weasyprint.urls import FatalURLFetchingError
    except Exception as exc:
        raise PDFRenderError(
            "PDF generation is unavailable. Verify the documented WeasyPrint "
            "system dependencies, then try again. The HTML report is still available."
        ) from exc

    allowed_root = source.parent

    def local_only_fetcher(url, timeout=10, ssl_context=None):
        parsed = urlparse(url)
        if parsed.scheme == "data":
            return default_url_fetcher(url, timeout=timeout, ssl_context=ssl_context)
        if parsed.scheme == "file":
            local_path = Path(url2pathname(unquote(parsed.path))).resolve()
            if not local_path.is_relative_to(allowed_root):
                raise FatalURLFetchingError(
                    "PDF resources must stay inside the report workspace."
                )
            return default_url_fetcher(url, timeout=timeout, ssl_context=ssl_context)
        raise FatalURLFetchingError("Remote PDF resources are not allowed.")

    try:
        pdf_bytes = HTML(filename=str(source), url_fetcher=local_only_fetcher).write_pdf()
        # Metadata-only ctime changes can follow publication on macOS. Verify
        # inode identity, size, mtime and bytes; a ctime-only change does not
        # change the canonical report. Dataset ingestion remains stricter.
        if source_signature(source)[:4] != signature[:4] or source_digest(source) != digest:
            raise PDFRenderError("Canonical HTML changed during conversion. The HTML report is still available.")
        return publish_bytes(destination, pdf_bytes)
    except ArtifactCollisionError:
        raise
    except PDFRenderError:
        raise
    except (Exception, FatalURLFetchingError) as exc:
        raise PDFRenderError(
            "PDF generation is unavailable. Verify the documented WeasyPrint "
            "system dependencies, then try again. The HTML report is still available."
        ) from exc
