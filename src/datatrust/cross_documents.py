"""Bounded native extraction; offsets address extracted units, never PDF bytes."""
import io
import importlib.metadata
import zipfile
from pathlib import PurePosixPath
from datatrust.contracts import AnalysisError
from datatrust.cross_private_base import digest


def versions():
    result={}
    for n,v in {'pdfplumber':'0.11.9','python-docx':'1.2.0'}.items():
        try: actual=importlib.metadata.version(n)
        except importlib.metadata.PackageNotFoundError as exc: raise ValueError('Install datatrust[documents] for native document evidence.') from exc
        if actual!=v: raise ValueError('Install pinned datatrust[documents] parsers.')
        result[n]=actual
    return result


def extract(raw,fmt,limits,*,strategy='lines',pages=(),parts=('word/document.xml',),check=lambda:None):
    """Yield bounded units and a final coverage unit; malformed documents are data states."""
    if fmt=='pdf':
        import pdfplumber
        from pdfminer.pdfparser import PDFSyntaxError
        from pdfminer.pdfdocument import PDFEncryptionError, PDFPasswordIncorrect
        try:
            with pdfplumber.open(io.BytesIO(raw)) as doc:
                if doc.doc.encryption:
                    yield {'kind':'coverage','processed':0,'state':'unsupported_encrypted'};return
                if len(doc.pages)>limits.pages: raise AnalysisError('Document page limit exceeded.',code='page_limit')
                count=0;textfree=0;empty_pages=0;table_bounded=False;bound_pages=[];characters=0
                for page in doc.pages:
                    check()
                    if pages and page.page_number not in pages: continue
                    count+=1
                    text=page.extract_text(x_tolerance=3,y_tolerance=3) or ''
                    characters+=len(text)
                    if characters>limits.characters: raise AnalysisError('Extracted character limit exceeded.',code='character_limit')
                    empty=not text.strip() and not (page.images or page.lines or page.rects or page.curves or page.annots)
                    state='text_bearing' if text.strip() else 'empty_page' if empty else 'text_free'
                    textfree+=state=='text_free';empty_pages+=empty
                    chars=[{k:c.get(k) for k in ('text','x0','top','x1','bottom')} for c in page.chars]
                    yield {'kind':'text','page':page.page_number,'text':text,'span':[0,len(text)],'geometry':chars,'complete':True,'state':state,'representation':'pdf_extracted_text_v1'}
                    tables=page.find_tables({'vertical_strategy':strategy,'horizontal_strategy':strategy})
                    # A document-wide cap, not a cap reset for every page.
                    for ti,table in enumerate(tables):
                        if getattr(doc,'_numek_tables',0)>=limits.tables:
                            table_bounded=True;bound_pages.append(page.page_number);break
                        doc._numek_tables=getattr(doc,'_numek_tables',0)+1
                        rows=table.extract()
                        text_cells=sum(len(c or '') for row in rows for c in row)
                        characters+=text_cells
                        if characters>limits.characters: raise AnalysisError('Extracted table character limit exceeded.',code='character_limit')
                        yield {'kind':'table','page':page.page_number,'table':ti,'rows':rows,'bbox':list(table.bbox),'cells':[[list(c) if c else None for c in row.cells] for row in table.rows],'complete':True,'representation':'pdf_table_v1'}
                    page.close()
                missing_pages=sorted(set(pages)-set(range(1,len(doc.pages)+1)))
                yield {'kind':'coverage','processed':count,'total':len(doc.pages),'text_free':textfree,'empty_pages':empty_pages,'tables_bounded':table_bounded,'table_bound_pages':bound_pages,'characters':characters,'missing_pages':missing_pages,'state':'incomplete' if textfree or missing_pages else 'processed','layout_assurance':False}
        except AnalysisError: raise
        except (PDFSyntaxError,PDFEncryptionError,PDFPasswordIncorrect,ValueError,TypeError) as exc:
            yield {'kind':'coverage','processed':0,'state':'unreadable_or_unsupported','reason':type(exc).__name__}
        return
    from lxml import etree
    from docx import Document
    from docx.table import Table
    from docx.text.paragraph import Paragraph
    from docx.oxml import parse_xml
    ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as package:
            members=package.infolist()
            if len(members)>limits.zip_members or sum(x.file_size for x in members)>limits.expanded_docx_bytes: raise AnalysisError('DOCX expansion limit exceeded.',code='docx_expansion_limit')
            if len({x.filename for x in members})!=len(members): raise ValueError('Duplicate package members.')
            selected=[];unsupported=[]
            for member in members:
                name=member.filename;p=PurePosixPath(name)
                if p.is_absolute() or '..' in p.parts or member.flag_bits&1: raise ValueError('Unsafe/encrypted DOCX member.')
                if name.endswith('.xml') or name.endswith('.rels'):
                    if member.file_size>limits.xml_bytes: raise AnalysisError('DOCX XML limit exceeded.',code='xml_limit')
                    value=package.read(member)
                    if b'<!DOCTYPE' in value.upper() or b'<!ENTITY' in value.upper(): raise ValueError('Active XML is unsupported.')
                    tree=etree.fromstring(value,etree.XMLParser(resolve_entities=False,no_network=True,load_dtd=False,huge_tree=False))
                    if name.endswith('.rels') and any(x.get('TargetMode')=='External' and not x.get('Type','').endswith('/hyperlink') for x in tree): raise ValueError('External media relationships are unsupported; no resources loaded.')
                    if name=='word/document.xml' or name.startswith('word/header') or name.startswith('word/footer'):
                        wanted=name in parts or (name.startswith('word/header') and 'headers' in parts) or (name.startswith('word/footer') and 'footers' in parts)
                        if wanted: selected.append((name,tree))
                        else: unsupported.append(name)
                    elif name.startswith('word/') and name not in {'word/styles.xml','word/settings.xml','word/fontTable.xml','word/webSettings.xml','word/numbering.xml'} and not name.startswith('word/theme') and name.endswith('.xml'):
                        unsupported.append(name)
            document=Document(io.BytesIO(raw));processed=0;tables=0;characters=0;omissions=0;bounded=False
            for name,tree in selected:
                tree=parse_xml(etree.tostring(tree))
                nodes=tree.find('w:body',ns) if name=='word/document.xml' else tree
                for bi,node in enumerate(nodes):
                    check()
                    if etree.QName(node).localname=='sectPr': continue
                    location={'part':name,'block':bi,'xml_path':tree.getroottree().getpath(node)}
                    if etree._Element.xpath(node,'.//w:ins|.//w:del|.//w:txbxContent|.//w:altChunk',namespaces=ns) or etree.QName(node).localname not in {'p','tbl'}:
                        omissions+=1;yield {'kind':'unsupported',**location,'complete':False,'reason':'unsupported_revision_or_layout'};continue
                    processed+=1
                    if etree.QName(node).localname=='p':
                        text=Paragraph(node,document).text
                        characters+=len(text)
                        yield {'kind':'text',**location,'text':text,'span':[0,len(text)],'complete':True,'representation':'docx_paragraph_v1'}
                    else:
                        if tables>=limits.tables: bounded=True;continue
                        tables+=1;t=Table(node,document);seen=set();rows=[];cells=[];merged=False
                        if etree._Element.xpath(node,'.//w:tbl/w:tr',namespaces=ns): merged=True
                        for row in t.rows:
                            vals=[];locs=[]
                            for cell in row.cells:
                                path=tree.getroottree().getpath(cell._tc)
                                duplicate=path in seen;seen.add(path);merged|=duplicate
                                vals.append(cell.text);locs.append({'xml_path':path,'duplicate':duplicate})
                                characters+=len(cell.text)
                            rows.append(vals);cells.append(locs)
                        yield {'kind':'table',**location,'table':tables-1,'rows':rows,'cells':cells,'complete':not merged,'reason':'merged_or_nested_table' if merged else None,'representation':'docx_table_v1'}
                    if characters>limits.characters: raise AnalysisError('Document character limit exceeded.',code='character_limit')
            yield {'kind':'coverage','processed':processed,'unsupported_parts':unsupported,'unsupported_blocks':omissions,'tables_bounded':bounded,'characters':characters,'state':'incomplete' if omissions else 'processed','pagination':'unavailable'}
    except AnalysisError: raise
    except (zipfile.BadZipFile,KeyError,ValueError,etree.XMLSyntaxError) as exc:
        yield {'kind':'coverage','processed':0,'state':'unreadable_or_unsupported','reason':type(exc).__name__}


def unit_identity(unit): return digest(unit)
