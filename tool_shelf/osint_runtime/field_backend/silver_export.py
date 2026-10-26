"""Export an authenticated stored SVG master; accept no client markup or layout."""
import base64
import hashlib
import io
import json
import re
from pathlib import Path
import threading
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent.parent
FONT = ROOT / 'frontend/fonts/YamrailBoard-Regular.ttf'
FONT_SHA = 'fe4be4a7c74a871ddca7dbc7e61895dd35862334afd36e5874a121a4d4454ee4'
SVG_NS = 'http://www.w3.org/2000/svg'
ET.register_namespace('', SVG_NS)
_font_lock = threading.Lock()
_pdf_render_lock = threading.Lock()
_font_ready = False

def digest(raw):
    return hashlib.sha256(raw).hexdigest()

def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')

def _verified_derived_graph(envelope,source,binding):
    """Authenticate a separate deterministic excerpt artifact, never a new report."""
    from .received_analysis import validate_advisory_md,is_explanatory_advisory
    from .explanatory_graph import PURPOSE,parse_output,derive_available_md,derive_structured_md,validate_projection
    from .silver_board_renderer import render_board
    from .content_board_contract import transport_metadata_numbers
    fields={'schema','state','reason','purpose','derivation','binding','canonical_md_sha256',
            'raw_model_output_sha256','source_ledger_sha256','original_projection_sha256',
            'projection','render','render_status','runtime_effect','new_provider_calls','authority_effect'}
    if (not isinstance(envelope,dict) or set(envelope)!=fields
            or envelope.get('schema')!='yamrail.osint-derived-content-graph/1'
            or envelope.get('derivation') not in {'AVAILABLE_MD_EXCERPTS','STRUCTURED_MD_GRAPH'}
            or envelope.get('state')!=envelope.get('derivation') or envelope.get('reason') is not None
            or envelope.get('purpose')!=PURPOSE
            or envelope.get('binding')!=binding or envelope.get('runtime_effect')!='NONE'
            or type(envelope.get('new_provider_calls')) is not int or envelope['new_provider_calls']!=0
            or envelope.get('authority_effect')!='NONE'):
        raise ValueError('OSINT_DERIVED_GRAPH_ENVELOPE_BINDING')
    advisory=source.get('model_advisory')
    base={key:binding[key] for key in ('workface_id','epoch','revision','input_sha256')}
    if not is_explanatory_advisory(advisory):raise ValueError('OSINT_DERIVED_GRAPH_PURPOSE')
    validate_advisory_md(advisory,base)
    parsed=json.loads(advisory['text'])
    if (envelope['derivation']=='AVAILABLE_MD_EXCERPTS'
            and ('graph' not in parsed or parsed['graph'] is not None)):
        raise ValueError('OSINT_DERIVED_GRAPH_ORIGINAL_BINDING')
    projection=envelope['projection']
    ledger=advisory.get('silver_board',{}).get('source_ledger')
    analysis,original=parse_output(advisory['text'],ledger,base)
    if (analysis!=advisory['analysis_markdown']
            or envelope['derivation']=='AVAILABLE_MD_EXCERPTS' and original.get('state')!='BOARD_UNAVAILABLE'
            or canonical(original)!=canonical(advisory.get('silver_board'))
            or envelope['canonical_md_sha256']!=advisory['analysis_markdown_sha256']
            or envelope['raw_model_output_sha256']!=digest(advisory['text'].encode('utf-8'))
            or envelope['source_ledger_sha256']!=ledger['sha256']
            or envelope['original_projection_sha256']!=digest(canonical(original))):
        raise ValueError('OSINT_DERIVED_GRAPH_ORIGINAL_BINDING')
    derive=derive_structured_md if envelope['derivation']=='STRUCTURED_MD_GRAPH' else derive_available_md
    expected_projection=derive(analysis,ledger,base,advisory['text'])
    validate_projection(projection,analysis,ledger,base,raw_model_text=advisory['text'])
    if (canonical(projection)!=canonical(expected_projection)
            or projection.get('state')!='MODEL_BOARD_CANDIDATE'):
        raise ValueError('OSINT_DERIVED_GRAPH_PROJECTION_BINDING')
    expected_render=render_board(projection['board'],base,ledger,purpose=PURPOSE,
                                 projection=projection,raw_model_text=advisory['text'])
    expected_render['metadata']['model_output_sha256']=projection['model_output_sha256']
    expected_render['metadata']['analysis_markdown_sha256']=advisory['analysis_markdown_sha256']
    expected_render['metadata']=transport_metadata_numbers(expected_render['metadata'])
    if (canonical(envelope['render'])!=canonical(expected_render)
            or envelope['render_status']!={'state':'FIXED_MASTER_SVG_READY','binding':base}):
        raise ValueError('OSINT_DERIVED_GRAPH_RENDER_BINDING')
    return envelope['render']


def verified_master(historical):
    if (historical.get('schema') != 'yamrail.osint-historical-result/1'
            or historical.get('read_only') is not True or historical.get('runtime_effect') != 'NONE'
            or historical.get('record_state') not in {'COMMITTED_HISTORICAL_RESULT','RECEIVED_UNCOMMITTED_RESULT'}):
        raise ValueError('OSINT_BOARD_STORED_RESULT_REQUIRED')
    report, binding = historical.get('report'), historical.get('binding')
    received=historical.get('record_state')=='RECEIVED_UNCOMMITTED_RESULT'
    if received:
        from .received_analysis import validate_received_analysis
        candidate=historical.get('received_analysis')
        validate_received_analysis(candidate)
        if (report is not None or not isinstance(binding,dict)
                or binding.get('report_sha256') is not None or binding.get('output_sha256') is not None
                or binding.get('received_frame_sha256')!=candidate['frame_sha256']
                or {key:binding.get(key) for key in ('workface_id','epoch','revision','input_sha256')}!=candidate['binding']):
            raise ValueError('OSINT_BOARD_RECEIVED_FRAME_BINDING')
        source=candidate['frame']
        artifact=source.get('silver_board_render')
    elif (not isinstance(report, dict) or not isinstance(binding, dict)
            or binding.get('workface_id') != historical.get('id')
            or digest(canonical(report)) != binding.get('report_sha256')):
        raise ValueError('OSINT_BOARD_REPORT_BINDING')
    else:
        source=report
        artifact=report.get('silver_board_render')
    if binding.get('workface_id')!=historical.get('id'):
        raise ValueError('OSINT_BOARD_REPORT_BINDING')
    from .received_analysis import is_explanatory_advisory,explanatory_graph_status
    advisory=source.get('model_advisory')
    explanatory=is_explanatory_advisory(advisory)
    derived=historical.get('derived_content_graph')
    # A failed optional presentation never replaces an existing valid master.
    # The old artifact retains its own binding and is checked below as before.
    if isinstance(derived,dict) and derived.get('state')=='LOCAL_HOLD':
        derived=None
    if derived is not None:
        artifact=_verified_derived_graph(derived,source,binding)
    elif explanatory:
        base={key:binding[key] for key in ('workface_id','epoch','revision','input_sha256')}
        graph_status=explanatory_graph_status(advisory,base,artifact,source.get('silver_board_render_status'))
        if graph_status['state']!='VALIDATED':
            raise ValueError('OSINT_EXPLANATORY_GRAPH_LOCAL_HOLD')
    if not isinstance(artifact, dict) or not isinstance(artifact.get('svg'), str) or not isinstance(artifact.get('metadata'), dict):
        raise ValueError('OSINT_BOARD_NOT_AVAILABLE')
    raw, metadata = artifact['svg'].encode('utf-8'), artifact['metadata']
    if (not 1 <= len(raw) <= 262144 or digest(raw) != metadata.get('svg_sha256')
            or metadata.get('font_sha256') != FONT_SHA
            or metadata.get('binding') != {key: binding[key] for key in ('workface_id', 'epoch', 'revision', 'input_sha256')}
            or digest(FONT.read_bytes()) != FONT_SHA):
        raise ValueError('OSINT_BOARD_MASTER_BINDING')
    if explanatory:
        renderers={digest((ROOT/'field_backend/silver_board_renderer.py').read_bytes())}
        if derived is None:
            # Immutable R035 originals remain exportable after this additive
            # derived-read adapter; derived artifacts are recomputed above.
            renderers.update({'61dd3905852c75e248ef726f6fa8efb726164bf9e47906fa52892d754d603ac8',
                              '004e2ef57a7d57abf103297a4ace7bbdaa014f02cd18f3405cf9f187510a5f50'})
        if metadata.get('renderer_sha256') not in renderers:
            raise ValueError('OSINT_EXPLANATORY_GRAPH_RENDERER_BINDING')
    if b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper():
        raise ValueError('OSINT_BOARD_EXTERNAL_RESOURCE_REJECTED')
    node = ET.fromstring(raw)
    if node.tag != '{'+SVG_NS+'}svg' or [float(v) for v in node.get('viewBox', '').split()] != [0, 0, 1414, 1000]:
        raise ValueError('OSINT_BOARD_FIXED_GEOMETRY')
    tags = {'svg', 'g', 'rect', 'line', 'polyline', 'polygon', 'path', 'circle', 'ellipse', 'text', 'tspan', 'defs', 'marker', 'title', 'desc', 'metadata'}
    for element in node.iter():
        if element.tag.removeprefix('{'+SVG_NS+'}') not in tags:
            raise ValueError('OSINT_BOARD_ACTIVE_MARKUP_REJECTED')
        for key, value in element.attrib.items():
            local_marker = key in {'marker-start', 'marker-mid', 'marker-end'} and re.fullmatch(r'url\(#[A-Za-z0-9_-]{1,64}\)', value)
            if key.lower().startswith('on') or key.rsplit('}', 1)[-1].lower() in {'href', 'src'} or ('url(' in value.lower() and not local_marker) or '@import' in value.lower():
                raise ValueError('OSINT_BOARD_EXTERNAL_RESOURCE_REJECTED')
    return raw, node, metadata, binding

def self_contained_svg(node, master_sha):
    """Embed only the same pinned glyphs; positions and visible text are unchanged."""
    from fontTools import subset
    from fontTools.ttLib import TTFont
    font = TTFont(FONT, recalcTimestamp=False)
    options = subset.Options()
    options.recalc_timestamp = False
    options.canonical_order = True
    tool = subset.Subsetter(options=options)
    tool.populate(text=''.join(node.itertext()))
    tool.subset(font)
    buf = io.BytesIO()
    font.save(buf, reorderTables=True)
    embedded = base64.b64encode(buf.getvalue()).decode('ascii')
    defs = ET.Element('{'+SVG_NS+'}defs')
    style = ET.SubElement(defs, '{'+SVG_NS+'}style', {'type': 'text/css'})
    style.text = ('@font-face{font-family:YamrailBoard;src:url(data:font/ttf;base64,'+embedded+
                  ') format("truetype");font-weight:400;font-style:normal;}text{font-family:YamrailBoard;font-kerning:none;font-variant-ligatures:none;}')
    node.insert(0, defs)
    node.set('data-source-master-sha256', master_sha)
    return ET.tostring(node, encoding='utf-8', xml_declaration=True)

def _vector_pdf_locked(raw, metadata, margin_mm=0):
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.graphics import renderPDF
    from svglib.svglib import svg2rlg
    from svglib.fonts import register_font, find_font
    global _font_ready
    with _font_lock:
        if not _font_ready:
            pdfmetrics.registerFont(TTFont('YamrailBoard', str(FONT)))
            pdfmetrics.registerFontFamily('YamrailBoard', normal='YamrailBoard', bold='YamrailBoard', italic='YamrailBoard', boldItalic='YamrailBoard')
            register_font('YamrailBoard', str(FONT), rlgFontName='YamrailBoard')
            if find_font('YamrailBoard') != ('YamrailBoard', True):
                raise ValueError('OSINT_BOARD_PDF_FONT_SUBSTITUTION')
            _font_ready = True
    drawing = svg2rlg(io.BytesIO(raw))
    if drawing is None or drawing.width <= 0 or drawing.height <= 0:
        raise ValueError('OSINT_BOARD_PDF_GEOMETRY')
    width, height = landscape(A4)
    if type(margin_mm) not in (int,float) or not 0<=margin_mm<=30:
        raise ValueError('OSINT_BOARD_PDF_MARGIN')
    inset=margin_mm*72/25.4
    factor = min((width-2*inset) / drawing.width, (height-2*inset) / drawing.height)
    output = io.BytesIO()
    pdf = canvas.Canvas(output, pagesize=(width, height), invariant=1, pageCompression=1)
    pdf.setTitle('YamRail OSINT')
    pdf.setCreator('YamRail OSINT fixed SVG master')
    pdf.setSubject('Source SVG SHA256 '+metadata['svg_sha256'])
    pdf.saveState()
    pdf.translate((width - drawing.width*factor)/2, (height-drawing.height*factor)/2)
    pdf.scale(factor, factor)
    renderPDF.draw(drawing, pdf, 0, 0)
    pdf.restoreState()
    pdf.showPage()
    pdf.save()
    return output.getvalue()

def vector_pdf(raw, metadata, *, margin_mm=0):
    # ReportLab's dynamic TTFont subsets are shared process state. One bounded
    # renderer at a time also avoids competing font/image work in this service.
    with _pdf_render_lock:
        return _vector_pdf_locked(raw, metadata, margin_mm)

def export_packet(historical, output_format):
    raw, node, metadata, binding = verified_master(historical)
    if output_format == 'svg':
        data, mime = self_contained_svg(node, metadata['svg_sha256']), 'image/svg+xml'
    elif output_format == 'pdf':
        data, mime = vector_pdf(raw, metadata), 'application/pdf'
    else:
        raise ValueError('OSINT_BOARD_EXPORT_FORMAT')
    if len(data) > 16 * 1024 * 1024:
        raise ValueError('OSINT_BOARD_EXPORT_BOUND')
    result={'schema': 'yamrail.osint-silver-board-export/1', 'format': output_format,
            'content_type': mime, 'data_base64': base64.b64encode(data).decode('ascii'),
            'sha256': digest(data), 'source_svg_sha256': metadata['svg_sha256'],
            'font_sha256': FONT_SHA, 'binding': binding,
            'filename': 'YamRail-OSINT-'+historical['id']+'.'+output_format,
            'runtime_effect': 'NONE', 'new_provider_calls': 0}
    if historical.get('record_state')=='RECEIVED_UNCOMMITTED_RESULT':
        result.update(record_state='RECEIVED_UNCOMMITTED_RESULT',
                      adoption_state='UNADOPTED_RECEIVED_ANALYSIS',
                      received_frame_sha256=historical['received_analysis']['frame_sha256'])
    if metadata.get('purpose')=='EXPLANATORY_PONCHI_DIAGRAM':
        result.update(purpose=metadata['purpose'],canonical_md_sha256=metadata['canonical_md_sha256'],
                      md_semantics_sha256=metadata['md_semantics_sha256'])
    if metadata.get('derivation') in {'AVAILABLE_MD_EXCERPTS','STRUCTURED_MD_GRAPH'}:
        envelope=historical['derived_content_graph']
        result.update(derivation=metadata['derivation'],
            derived_content_graph_sha256=digest(canonical(envelope)),
            raw_model_output_sha256=envelope['raw_model_output_sha256'],
            source_ledger_sha256=envelope['source_ledger_sha256'],
            original_projection_sha256=envelope['original_projection_sha256'])
    return result
