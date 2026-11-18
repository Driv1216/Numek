"""Convert one report HTML to PDF in its own process and describe the result.

Usage: python -m validation.report_experience.pdf_probe HTML PDF [--analyse]

The conversion mirrors datatrust.pdf.render_pdf_report: WeasyPrint with a fetcher that allows data: URIs and files inside
the report directory and refuses everything else. Timing covers layout (render) and PDF serialisation (write); peak RSS
is this process's maximum resident set size. With --analyse it also reports, per page: orientation, the vertical extent
used by content (a fill ratio), headings that start on the page, and table rows by table class. These read WeasyPrint's
internal box tree; they are validation instruments, not product code.
"""
import json
import resource
import sys
import time
from pathlib import Path
from urllib.parse import unquote, urlparse
from urllib.request import url2pathname


def _fetcher(root):
    from weasyprint import default_url_fetcher
    from weasyprint.urls import FatalURLFetchingError

    def fetch(url, timeout=10, ssl_context=None):
        parsed = urlparse(url)
        if parsed.scheme == 'data':
            return default_url_fetcher(url, timeout=timeout, ssl_context=ssl_context)
        if parsed.scheme == 'file':
            local = Path(url2pathname(unquote(parsed.path))).resolve()
            if local.is_relative_to(root):
                return default_url_fetcher(url, timeout=timeout, ssl_context=ssl_context)
        raise FatalURLFetchingError('Only local report resources are allowed.')
    return fetch


def _text(element):
    return ' '.join(''.join(element.itertext()).split()) if element is not None else ''


def describe(document):
    from weasyprint.formatting_structure import boxes
    pages = []
    for number, page in enumerate(document.pages, 1):
        page_box = page._page_box
        top = page_box.content_box_y()
        height = page_box.height
        state = {'bottom': top, 'headings': [], 'rows': {}}

        def walk(box, table_class):
            if isinstance(box, boxes.MarginBox):
                return
            if isinstance(box, boxes.TableBox) and box.element is not None:
                table_class = box.element.get('class') or '(unclassed)'
            if box.element_tag in ('h1', 'h2', 'h3') and isinstance(box, boxes.BlockBox):
                state['headings'].append({'level': box.element_tag, 'text': _text(box.element)[:120]})
            if isinstance(box, boxes.TableRowBox):
                state['rows'][table_class] = state['rows'].get(table_class, 0) + 1
            if isinstance(box, (boxes.LineBox, boxes.ReplacedBox, boxes.TableRowBox)):
                state['bottom'] = max(state['bottom'], box.position_y + box.margin_height())
            for child in getattr(box, 'children', ()) or ():
                walk(child, table_class)

        for child in page_box.children:
            walk(child, None)
        fill = max(0.0, min(1.0, (state['bottom'] - top) / height)) if height else None
        pages.append({'page': number, 'orientation': 'landscape' if page.width > page.height else 'portrait',
                      'fill': round(fill, 3) if fill is not None else None,
                      'headings': state['headings'], 'table_rows': state['rows']})
    return pages


def main(argv):
    from weasyprint import HTML
    html_path, pdf_path = Path(argv[0]).resolve(), Path(argv[1])
    analyse = '--analyse' in argv
    start = time.perf_counter()
    document = HTML(filename=str(html_path), url_fetcher=_fetcher(html_path.parent)).render()
    rendered = time.perf_counter()
    data = document.write_pdf()
    written = time.perf_counter()
    pdf_path.write_bytes(data)
    out = {'render_s': round(rendered - start, 4), 'write_s': round(written - rendered, 4),
           'total_s': round(written - start, 4), 'pages': len(document.pages), 'pdf_bytes': len(data),
           'peak_rss_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * (1 if sys.platform == 'darwin' else 1024)}
    if analyse:
        out['page_detail'] = describe(document)
        def count(nodes):
            return sum(1 + count(node[2]) for node in nodes)  # (label, target, children, state)
        out['bookmarks'] = count(document.make_bookmark_tree())
    print(json.dumps(out))


if __name__ == '__main__':
    main(sys.argv[1:])
