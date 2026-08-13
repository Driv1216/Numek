from pathlib import Path
from urllib.parse import unquote, urlparse
from urllib.request import url2pathname


class PDFRenderError(RuntimeError):
    """Raised when the standalone HTML report cannot be converted to PDF."""


def render_pdf_report(html_path: Path, output_path: Path) -> str:
    """Convert a generated local HTML report to a cached PDF artifact."""
    source = Path(html_path).resolve()
    destination = Path(output_path)
    temporary = destination.with_suffix(destination.suffix + ".tmp")

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
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary.write_bytes(pdf_bytes)
        temporary.replace(destination)
        return str(destination)
    except (Exception, FatalURLFetchingError) as exc:
        temporary.unlink(missing_ok=True)
        raise PDFRenderError(
            "PDF generation is unavailable. Verify the documented WeasyPrint "
            "system dependencies, then try again. The HTML report is still available."
        ) from exc
