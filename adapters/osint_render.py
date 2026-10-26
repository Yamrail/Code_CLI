"""Pinned YamRail OSINT renderer, exposed as a local offline tool.

The original MD structure, dependency graph, CAD primitive engine, glyph
metrics, PNG worker and vector exporter are reused. No model/provider, network,
canonical ledger or application server is invoked by this adapter.
"""
from __future__ import annotations

import copy
import hashlib
import html
import importlib.metadata
import io
import json
import math
import re
import stat
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / 'tool_shelf/osint_runtime'
SOURCE_REF = '9f3a5e61b72a0517f683d3e7ccd22a0904782fec'
PR62_REF = '907593e0d045cfc926943d186eb0aa19ad7c92bb'
PROVENANCE_SHA256 = 'f3811f64f64702fd042f7a1815cfd242545d072e56acdcbe98f589f357ad141c'
CASE_SCHEMA = 'yamrail.code-cli.osint-case/1'
CLASSES = {'LIVE_REAL','LOCAL_EXECUTED','REPLAY_FROM_CAPTURED_EVIDENCE','SYNTHETIC_FIXTURE','STATIC_DIAGRAM','DESIGN_ONLY','UNKNOWN'}
NS = 'http://www.w3.org/2000/svg'
MARGIN_MM = 8
PAGE_MM = (297, 210)


class OsintRenderHold(ValueError):
    pass


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')


def sha(value):
    return hashlib.sha256(value).hexdigest()


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise OsintRenderHold('HOLD_DUPLICATE_JSON_KEY')
        result[key] = value
    return result


def _read_json(path, maximum=262144):
    path = Path(path)
    if path.is_symlink():
        raise OsintRenderHold('HOLD_INPUT_LINK')
    info = path.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or not 1 <= info.st_size <= maximum:
        raise OsintRenderHold('HOLD_INPUT_TYPE_OR_SIZE')
    raw = path.read_bytes()
    value = json.loads(raw.decode('utf-8'), object_pairs_hook=_unique,
                       parse_constant=lambda _: (_ for _ in ()).throw(OsintRenderHold('HOLD_NONFINITE_JSON')))
    return raw, value


def _label(value, name, maximum=96):
    if (not isinstance(value, str) or not 1 <= len(value) <= maximum or
            any(ord(c) < 32 or c in '\u2028\u2029' for c in value)):
        raise OsintRenderHold('HOLD_METADATA_' + name)
    return value


def _case(path):
    raw, value = _read_json(path)
    return _case_value(raw,value)


def _case_value(raw,value):
    fields = {'schema','case_id','title','owner','scope','as_of','issuer','evidence_class','report_markdown','sources'}
    if not isinstance(value, dict) or not fields <= set(value) or set(value) - fields - {'history_snapshot'}:
        raise OsintRenderHold('HOLD_CASE_CONTRACT')
    if value['schema'] != CASE_SCHEMA or not re.fullmatch('[a-f0-9]{32}', str(value['case_id'])):
        raise OsintRenderHold('HOLD_CASE_ID_OR_SCHEMA')
    for name in ('title','owner','scope','as_of','issuer'):
        _label(value[name], name.upper())
    if value['evidence_class'] not in CLASSES:
        raise OsintRenderHold('HOLD_EVIDENCE_CLASS')
    md = value['report_markdown']
    if not isinstance(md, str) or not 1 <= len(md.encode('utf-8')) <= 65536 or '\x00' in md:
        raise OsintRenderHold('HOLD_MARKDOWN_BYTES')
    if not isinstance(value['sources'], list) or not 1 <= len(value['sources']) <= 8:
        raise OsintRenderHold('HOLD_SOURCE_COUNT')
    seen = set()
    for row in value['sources']:
        required = {'id','title','issuer','url','observed_at','evidence_class','body_text','body_sha256'}
        if not isinstance(row, dict) or set(row) != required:
            raise OsintRenderHold('HOLD_SOURCE_CONTRACT')
        if not re.fullmatch(r'C[1-9][0-9]{0,3}', str(row['id'])) or row['id'] in seen:
            raise OsintRenderHold('HOLD_SOURCE_ID')
        seen.add(row['id'])
        for name in ('title','issuer','observed_at'):
            _label(row[name], 'SOURCE_' + name.upper())
        if row['evidence_class'] not in CLASSES or not isinstance(row['body_text'], str):
            raise OsintRenderHold('HOLD_SOURCE_CLASS_OR_BODY')
        body = row['body_text'].encode('utf-8')
        if not 1 <= len(body) <= 32768 or sha(body) != row['body_sha256']:
            raise OsintRenderHold('HOLD_ORIGINAL_BYTE_SHA256_MISMATCH')
        if row['url'] is not None and (not isinstance(row['url'], str) or not re.fullmatch(r'https://[^\s<>]{1,2040}', row['url'])):
            raise OsintRenderHold('HOLD_SOURCE_URL')
    return raw, value


def _native():
    # Import only this pinned local subtree. The public server/provider modules
    # are not started and no private engine state is loaded.
    provenance_raw = (RUNTIME / 'SOURCE_PROVENANCE.json').read_bytes()
    if sha(provenance_raw) != PROVENANCE_SHA256:
        raise OsintRenderHold('HOLD_RENDERER_PROVENANCE_ANCHOR')
    provenance = json.loads(provenance_raw)
    for entry in provenance['source_files']:
        path = RUNTIME / entry['path']
        if path.is_symlink() or not path.resolve().is_relative_to(RUNTIME.resolve()) or sha(path.read_bytes()) != entry['sha256']:
            raise OsintRenderHold('HOLD_PINNED_RENDERER_SOURCE_SHA256')
    if (ROOT/'tool_shelf/__init__.py').read_bytes() not in (b'',b'\n'):
        raise OsintRenderHold('HOLD_TOOL_SHELF_PACKAGE_ENTRY')
    from tool_shelf.osint_runtime.field_backend import (
        explanatory_graph, silver_board_renderer, silver_export,
        graph_png, graph_artifacts, investigation_dependency_graph,
        document_guard,
    )
    return explanatory_graph, silver_board_renderer, silver_export, graph_png, graph_artifacts, investigation_dependency_graph, document_guard


def _out(path):
    path = Path(path)
    if path.is_symlink():
        raise OsintRenderHold('HOLD_OUTPUT_LINK')
    path.mkdir(parents=True, exist_ok=True)
    if any(path.iterdir()):
        raise OsintRenderHold('HOLD_OUTPUT_NOT_FRESH')
    return path


def _save(path, value):
    path.write_bytes(canonical(value) + b'\n')


def _source_register(case, out):
    folder = out / 'sources'
    folder.mkdir()
    entries = []
    for source in case['sources']:
        body = source['body_text'].encode('utf-8')
        target = folder / (source['id'] + '.txt')
        target.write_bytes(body)
        entries.append({k: copy.deepcopy(v) for k, v in source.items() if k != 'body_text'} | {
            'path': 'sources/' + target.name,
            'ORIGINAL_BYTE_SHA256': sha(body), 'byte_count': len(body),
            'origin': 'EXACT_AUTHORED_SYNTHETIC_FIXTURE_UTF8_BYTES' if source['evidence_class'] == 'SYNTHETIC_FIXTURE' else 'CALLER_SUPPLIED_BYTES_ORIGIN_NOT_INDEPENDENTLY_AUTHENTICATED',
            'external_original_evidence_proven': False,
            'independence_status': 'UNKNOWN',
        })
    value = {'schema':'yamrail.code-cli.source-register/1','case_id':case['case_id'],
             'case_evidence_class':case['evidence_class'],'read_only_network_calls':0,
             'authority_effect':'NONE','sources':entries}
    _save(out / 'source_register.json', value)
    return value


def _ledger(case, binding):
    ledger = {'schema':'yamrail.osint-board-source-ledger/1','binding':binding,
              'items':[{'id':r['id'],'kind':'ATTACHED_SOURCE_COPY','copy_sha256':r['body_sha256'],
                        'url':None,'original_text':r['body_text'],'tool_call_ids':[],
                        'origins':['SYNTHETIC_FIXTURE' if r['evidence_class']=='SYNTHETIC_FIXTURE' else 'CALLER_SUPPLIED_COPY_NOT_INDEPENDENTLY_AUTHENTICATED'],
                        'independence_status':'UNKNOWN'} for r in case['sources']]}
    ledger['sha256'] = sha(canonical(ledger))
    return ledger


def _projection_case(raw,value,kind):
    """Quote a read-only native JSON capture; never reconstruct its state."""
    if not isinstance(value,dict) or value.get('schema')==CASE_SCHEMA:
        raise OsintRenderHold('HOLD_TYPED_JSON_PROJECTION_REQUIRED')
    schema=str(value.get('schema','')).lower()
    if kind=='WORKLEDGER':
        relevant=any(x in schema for x in ('workledger','workstate','projection','typed-graph','native-stage')) or any(k in value for k in ('events','stages','nodes','ledger'))
    else:
        relevant=any(x in schema for x in ('security','recon','readonly','source-review')) or any(k in value for k in ('findings','checked_files','reviewed_files'))
    if not relevant:raise OsintRenderHold('HOLD_UNSUPPORTED_'+kind+'_JSON_SCHEMA')
    # Only metadata values are displayed; secret-bearing literals are not an
    # eligible read-only report input. No source rewrite/redaction is implied.
    def sensitive(obj):
        if isinstance(obj,dict):
            for key,item in obj.items():
                if re.search(r'(?i)(?:api[_-]?key|password|access[_-]?token|client[_-]?secret|private[_-]?key)',key) and isinstance(item,str) and item not in {'UNKNOWN','HOLD','REDACTED','NOT_PRESENT','NOT_CONFIGURED',''}:
                    return True
                if sensitive(item):return True
        elif isinstance(obj,list):return any(sensitive(x) for x in obj)
        return False
    if sensitive(value):raise OsintRenderHold('HOLD_SENSITIVE_PROJECTION_FIELD')
    lines=['# '+kind+' read-only JSON projection','','## 分かっていること',
           '資料 C1 はローカルJSON写しである。外部原典や正本状態の認証ではない。']
    omitted=[]
    for key in sorted(value)[:8]:
        text=canonical(value[key]).decode('utf-8')
        if len(text)>600:
            omitted.append(key);continue
        lines.append('資料 C1 の記載 '+key+' = '+text)
    for key in sorted(value)[8:]:omitted.append(key)
    lines+=['','## 分からないこと','JSON記載の現在性・完全性・発行主体の独立性は UNKNOWN / HOLD。C1',
            '記録された参照や typed relation を、出来事の因果や実行権限へ昇格しない。C1',
            '','## 次の探索','調査員が C1 と既存WorkLedgerの証憑を照合し、許可された次工程を決める。',
            '','## ひとことで','元JSONは sources/C1.txt と original_input.json に原byteのまま保存。省略項目は索引を参照。C1']
    as_of=next((value[k] for k in ('as_of','observed_utc','generated_utc','created_at') if isinstance(value.get(k),str) and len(value[k])<=96),'UNKNOWN')
    source_class='SYNTHETIC_FIXTURE' if value.get('evidence_class')=='SYNTHETIC_FIXTURE' else 'UNKNOWN'
    case={'schema':CASE_SCHEMA,'case_id':sha(raw)[:32],'title':kind+' / read-only native JSON','owner':'YamRail local operator',
          'scope':'Captured JSON; declared state only','as_of':as_of,'issuer':'Caller JSON; origin unverified','evidence_class':source_class,
          'report_markdown':'\n'.join(lines)+'\n','sources':[{'id':'C1','title':kind+' JSON capture','issuer':'Caller JSON; origin unverified','url':None,'observed_at':as_of,'evidence_class':source_class,'body_text':raw.decode('utf-8'),'body_sha256':sha(raw)}]}
    _case_value(raw,case)
    case['_source_document']={'kind':kind,'ORIGINAL_JSON_BYTE_SHA256':sha(raw),'derived_md_sha256':sha(case['report_markdown'].encode('utf-8')),
                              'displayed_top_level_limit':8,'omitted_top_level_keys':omitted,'origin_authentication':'UNKNOWN','state_machine_reconstructed':False,'typed_relation_policy':'QUOTE_DECLARED_JSON_ONLY_NO_CAUSAL_PROMOTION'}
    case['_original_json']=raw
    return raw,case


def _report_case(path):
    raw,value=_read_json(path)
    if isinstance(value,dict) and value.get('schema')==CASE_SCHEMA:return (*_case_value(raw,value),'CONTENT')
    schema=str(value.get('schema','')).lower() if isinstance(value,dict) else ''
    kind='SECURITY' if any(x in schema for x in ('security','recon','source-review')) or isinstance(value,dict) and any(k in value for k in ('findings','checked_files','reviewed_files')) else 'WORKLEDGER'
    return (*_projection_case(raw,value,kind),kind)


def _annotate(native_raw, case, kernel, kind):
    """Versioned presentation captions; graph geometry, nodes and edges stay.

    Full metadata and source/issuer index are preserved in the receipts. Long
    metadata is rejected instead of silently truncating into another meaning.
    """
    node = ET.fromstring(native_raw)
    ns = '{' + NS + '}'
    groups = [g for g in node.findall(ns+'g') if g.get('data-layer') == '10_header']
    captions = [t for g in groups for t in g.findall(ns+'text')]
    changes = []
    if kind != 'HISTORY' and len(captions) >= 4:
        replacements = {
            0: ('Read-only OSINT | ' + case['title'], 22, 1000),
            2: ('Owner: ' + case['owner'] + ' | Scope: ' + case['scope'] + ' | As of: ' + case['as_of'], 13, 1378),
            3: ('Refs are not causality. ' + ' | '.join(r['id']+': '+r['title']+' / '+r['issuer'] for r in case['sources']), 11, 1378),
        }
        for index, (text, size, limit) in replacements.items():
            if kernel._line_width(text, size) > limit:
                raise OsintRenderHold('HOLD_VISIBLE_METADATA_OVERFLOW')
            changes.append({'caption':index,'original':captions[index].text,'derived':text})
            captions[index].text = text
    elif kind == 'HISTORY' and len(captions)>=2:
        replacements={0:('History | '+case['title'],26,1100),
                      1:('Refs are not causality | '+case['owner']+' | '+case['scope']+' | '+case['as_of']+' | '+'; '.join(s['id']+' '+s['issuer'] for s in case['sources']),11,1350)}
        for index,(text,size,limit) in replacements.items():
            if kernel._line_width(text,size)>limit:raise OsintRenderHold('HOLD_VISIBLE_METADATA_OVERFLOW')
            changes.append({'caption':index,'original':captions[index].text,'derived':text})
            captions[index].text=text;captions[index].set('font-size',str(size))
        for group in node.findall(ns+'g'):
            if group.get('data-layer','').startswith('20_node_'):
                texts=group.findall(ns+'text')
                if any(t.text==case['case_id'] for t in texts) and len(texts)>=6 and case['sources']:
                    text='Sources '+' '.join(s['id'] for s in case['sources'])+' | original bytes in source_register.json'
                    if kernel._line_width(text,11)>410:raise OsintRenderHold('HOLD_VISIBLE_SOURCE_IDS_OVERFLOW')
                    changes.append({'node_source_caption_original':texts[-1].text,'derived':text})
                    texts[-1].text=text
    return ET.tostring(node, encoding='utf-8', xml_declaration=True), changes


def _margin_svg(raw, exporter):
    source = ET.fromstring(raw)
    width, height = 1414, 1000
    factor = min((297-2*MARGIN_MM)/297, (210-2*MARGIN_MM)/210)
    x, y = width*(1-factor)/2, height*(1-factor)/2
    wrapper = ET.Element('{'+NS+'}svg', {'viewBox':'0 0 1414 1000','width':'297mm','height':'210mm',
                         'font-family':'YamrailBoard','preserveAspectRatio':'xMidYMid meet',
                         'data-presentation':'R008_UNIFORM_A4_8MM_MARGIN','data-source-svg-sha256':sha(raw)})
    ET.SubElement(wrapper,'{'+NS+'}rect',{'x':'0','y':'0','width':'1414','height':'1000','fill':'#ffffff'})
    group = ET.SubElement(wrapper,'{'+NS+'}g',{'transform':f'translate({x:.9f} {y:.9f}) scale({factor:.12f})'})
    for child in list(source): group.append(copy.deepcopy(child))
    return exporter.self_contained_svg(wrapper, sha(raw)), {'uniform_scale':factor,'translate_canvas':[x,y],
             'physical_page_mm':list(PAGE_MM),'minimum_margin_mm':MARGIN_MM,'graph_semantics_changed':False}


def _margin_png(raw):
    from PIL import Image
    original = Image.open(io.BytesIO(raw)).convert('RGB')
    factor = min((297-2*MARGIN_MM)/297, (210-2*MARGIN_MM)/210)
    size = (math.floor(original.width*factor), math.floor(original.height*factor))
    inner = original.resize(size, Image.Resampling.LANCZOS)
    page = Image.new('RGB', original.size, 'white')
    page.paste(inner, ((page.width-inner.width)//2, (page.height-inner.height)//2))
    output = io.BytesIO()
    page.save(output,format='PNG',compress_level=9,optimize=False)
    return output.getvalue()


def _files(out, names):
    return {name:{'sha256':sha((out/name).read_bytes()),'bytes':(out/name).stat().st_size} for name in names}


def _deliver(out, raw, metadata, graph, binding, case, register, kind, renderer_native, caption_changes):
    _, kernel, exporter, png, artifacts, _, _ = renderer_native
    native_png = png.render_png(raw)
    identity = png.renderer_identity()
    artifacts._png(native_png, identity)
    svg, presentation = _margin_svg(raw, exporter)
    final_png = _margin_png(native_png)
    pdf = exporter.vector_pdf(raw, {**metadata,'svg_sha256':sha(raw)}, margin_mm=MARGIN_MM)
    (out/'native_renderer.svg').write_bytes(metadata.pop('_native_original_svg'))
    (out/'graph_render_master.svg').write_bytes(raw)
    (out/'native_renderer.png').write_bytes(native_png)
    (out/'graph.svg').write_bytes(svg)
    (out/'graph.png').write_bytes(final_png)
    (out/'graph.pdf').write_bytes(pdf)
    master = {'schema':'yamrail.osint-immutable-graph-master/1','graph_kind':kind,
              'local_adapter_source_sha256':sha(Path(__file__).read_bytes()),
              'source_binding':binding,'master_svg_sha256':sha(raw),'graph':graph,
              'renderer_metadata':metadata,'renderer_identity':identity,
              'original_renderer_svg_sha256':sha((out/'native_renderer.svg').read_bytes()),
              'source_register_sha256':sha((out/'source_register.json').read_bytes()),
              'original_report_md_sha256':sha(case['report_markdown'].encode('utf-8')),
              'presentation':presentation | {'caption_changes':caption_changes},
              'case_metadata':{k:case[k] for k in ('case_id','title','owner','scope','as_of','issuer','evidence_class')},
              'source_issuer_index':[{k:s[k] for k in ('id','title','issuer','observed_at','evidence_class')} for s in case['sources']],
              'evidence_class':'LOCAL_EXECUTED','source_evidence_class':case['evidence_class'],
              'renderer_input_origin':'OPERATOR_AUTHORED_FIXTURE_OR_CALLER_DOCUMENT_NOT_NEW_MODEL_OUTPUT',
              'authority_effect':'NONE','source_truth':'NOT_ESTABLISHED_BY_RENDERING'}
    if case.get('_source_document'):master['source_document']=case['_source_document']
    _save(out/'graph_master.json',master)
    glyphs = metadata.get('glyph_substitution_codepoints', [])
    tree=ET.fromstring(raw)
    node_texts=[' '.join(t.text or '' for t in group.findall('{'+NS+'}text')) for group in tree.findall('{'+NS+'}g') if group.get('data-layer','').startswith(('30_node_','20_node_'))]
    visible_ids={s['id']:any(re.search(r'(?<![A-Za-z0-9_])'+re.escape(s['id'])+r'(?![A-Za-z0-9_])',t) for t in node_texts) for s in case['sources']}
    state='HOLD_RENDERED_WITH_GLYPH_SUBSTITUTION' if glyphs else 'PASS_PINNED_LOCAL_OSINT_RENDER'
    if visible_ids and not all(visible_ids.values()):state='HOLD_SOURCE_ID_NOT_VISIBLE_IN_NODE'
    receipt = {'schema':'yamrail.code-cli.osint-render-receipt/1','state':state,
               'local_adapter_source_sha256':sha(Path(__file__).read_bytes()),
               'evidence_class':'LOCAL_EXECUTED','source_evidence_class':case['evidence_class'],
               'graph_type':kind.lower(),'source_binding':binding,
               'source_pins':{'PR79':SOURCE_REF,'PR62':PR62_REF},
               'pin_usage':{'PR79':'EXECUTED_LOCAL_NATIVE_RENDER_MODULES','PR62':'EXACT_COMPARISON_REFERENCE_READ_UI_CODE_NOT_EXECUTED'},
               'source_provenance_sha256':sha((RUNTIME/'SOURCE_PROVENANCE.json').read_bytes()),
               'actual_reused_modules':['explanatory_graph','structured_md_renderer','silver_board_renderer','cad_display_station','graph_png','graph_artifacts._png','silver_export.vector_pdf'] if kind!='HISTORY' else ['investigation_dependency_graph','silver_board_renderer','cad_display_station','graph_png','graph_artifacts._png','silver_export.vector_pdf'],
               'files':_files(out,['graph.svg','graph.png','graph.pdf','graph_master.json','original_report.md','source_register.json','native_renderer.svg','native_renderer.png','graph_render_master.svg']),
               'source_ids_visible_in_nodes':visible_ids,
               'legend':'Explicit MD relations and shared citations are references, never inferred causation. UNKNOWN/HOLD stays unresolved.',
               'physical_page_mm':list(PAGE_MM),'minimum_margin_mm':MARGIN_MM,
               'font':{'family':'YamrailBoard','sha256':kernel.FONT_SHA256,'license':'OFL-1.1'},
               'glyph_qa':{'unsupported_glyphs':glyphs,'font_substitution':bool(glyphs),'scope':'FONT_COVERAGE_AND_NATIVE_GEOMETRY; VISUAL_QA_RECORDED_SEPARATELY'},
               'local_scope':'PINNED_OFFLINE_RENDERER_NOT_AUTHENTICATED_OSINT_SERVER_OR_SPONSOR_CALL',
               'new_provider_calls':0,'network_calls':0,'canonical_writes':0,
               'external_source_origin_authenticated':False,'human_release':'OWNER_RELEASE_PENDING'}
    if case.get('_source_document'):
        receipt['source_document']=case['_source_document']
        receipt['renderer_md_origin']='DERIVED_FROM_ORIGINAL_JSON_NOT_ORIGINAL_TARGET_SOURCE_MD'
        receipt['files'].update(_files(out,['original_input.json','derived_report.md']))
    _save(out/'graph_receipt.json',receipt)
    return receipt


def render_graph(case_path: Path, out: Path, graph_type='content') -> dict:
    if graph_type == 'history':
        _, case = _case(case_path)
        if 'history_snapshot' not in case:
            raise OsintRenderHold('HOLD_NATIVE_HISTORY_SNAPSHOT_REQUIRED')
        return _history_value(case['history_snapshot'],out,case)
    if graph_type in {'workledger','security'}:
        raw,value=_read_json(case_path)
        raw_case,case=_projection_case(raw,value,graph_type.upper())
        return _render_case(raw_case,case,out,graph_type.upper())
    if graph_type != 'content':
        raise OsintRenderHold('HOLD_GRAPH_TYPE')
    raw_case, case = _case(case_path)
    return _render_case(raw_case,case,out,'CONTENT')


def _render_case(raw_case,case,out,kind):
    native = _native()
    explanatory, kernel, _, _, _, _, _ = native
    binding = {'workface_id':case['case_id'],'epoch':0,'revision':1,'input_sha256':sha(raw_case)}
    ledger = _ledger(case,binding)
    # This existing transport name belongs to the historical renderer. Here it
    # is an explicit local fixture; no model response or generation is claimed.
    transport = canonical({'schema':'yamrail.osint-explanatory-graph/1','analysis_markdown':case['report_markdown'],'graph':None}).decode('utf-8')
    projection = explanatory.derive_structured_md(case['report_markdown'],ledger,binding,transport)
    result = kernel.render_board(projection['board'],binding,ledger,purpose=explanatory.PURPOSE,projection=projection,raw_model_text=transport)
    original = result['svg'].encode('utf-8')
    raw, changes = _annotate(original,case,kernel,kind)
    out = _out(out)
    register = _source_register(case,out)
    (out/'original_report.md').write_bytes(case['report_markdown'].encode('utf-8'))
    if case.get('_source_document'):
        (out/'original_input.json').write_bytes(case['_original_json'])
        (out/'derived_report.md').write_bytes(case['report_markdown'].encode('utf-8'))
    _save(out/'source_ledger.json',ledger)
    _save(out/'synthetic_renderer_transport.json',{'origin':'SYNTHETIC_OPERATOR_FIXTURE_NOT_MODEL_OUTPUT','transport':json.loads(transport)})
    metadata = dict(result['metadata']);metadata['_native_original_svg']=original
    return _deliver(out,raw,metadata,projection,binding,case,register,kind,native,changes)


def _history_value(snapshot,out,case=None):
    native = _native()
    _, kernel, _, _, _, dependencies, _ = native
    value = dependencies.dependency_graph(snapshot)
    if case is None and snapshot.get('code_cli_case') is not None:
        _,case=_case_value(canonical(snapshot['code_cli_case']),snapshot['code_cli_case'])
        if case['case_id']!=snapshot['id'] or sha(case['report_markdown'].encode('utf-8'))!=snapshot['binding']['report_sha256']:
            raise OsintRenderHold('HOLD_HISTORY_CASE_BINDING')
        material={s.get('source_ref'):s.get('copy_sha256') for s in snapshot.get('source_material',[]) if isinstance(s,dict)}
        if any(material.get(s['id'])!=s['body_sha256'] for s in case['sources']):
            raise OsintRenderHold('HOLD_HISTORY_SOURCE_BYTES_BINDING')
    if case is None:
        case = {'case_id':snapshot['id'],'title':'調査の依存関係と引継ぎ','owner':'Declared snapshot owner UNKNOWN',
                'scope':'Persisted context references only','as_of':str(snapshot.get('created_at') or 'UNKNOWN'),
                'issuer':'Declared snapshot issuer UNKNOWN','evidence_class':'UNKNOWN','sources':[],
                'report_markdown':'# Dependency snapshot\n\nReferences are not causality. Origin remains UNKNOWN.\n'}
    out = _out(out)
    register = _source_register(case,out)
    (out/'original_report.md').write_bytes(case['report_markdown'].encode('utf-8'))
    _save(out/'history_snapshot.json',snapshot)
    raw = value['render']['svg'].encode('utf-8')
    original=raw
    raw,changes=_annotate(raw,case,kernel,'HISTORY')
    metadata = dict(value['render']['metadata']);metadata['_native_original_svg']=original
    return _deliver(out,raw,metadata,value['scene'],value['binding'],case,register,'HISTORY',native,changes)


def history_graph(snapshot_path: Path, out: Path) -> dict:
    _, snapshot = _read_json(snapshot_path, maximum=1048576)
    return _history_value(snapshot,out)


def _report_pdf(text,path,font):
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_LEFT
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.pdfgen import canvas
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    metrics=json.loads((RUNTIME/'frontend/fonts/YamrailBoard-Regular.metrics.json').read_bytes())
    missing=sorted(set(ord(c) for c in text if c not in '\r\n\t' and str(ord(c)) not in metrics['advances']))
    if missing:
        raise OsintRenderHold('HOLD_REPORT_UNSUPPORTED_FONT_GLYPH')
    if 'YamrailReport' not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont('YamrailReport',str(font)))
    normal = ParagraphStyle('body',fontName='YamrailReport',fontSize=10.5,leading=15,spaceAfter=4,wordWrap='CJK',alignment=TA_LEFT,textColor=colors.HexColor('#102f3c'))
    heading = ParagraphStyle('heading',parent=normal,fontSize=16,leading=22,spaceBefore=9,spaceAfter=7,keepWithNext=True,textColor=colors.HexColor('#0060df'))
    blocks=[]
    for line in text.splitlines():
        if not line.strip():blocks.append(Spacer(1,3*mm));continue
        if line.startswith('#'):
            content=line.lstrip('#').strip();style=heading
        else:content=line;style=normal
        blocks.append(Paragraph(html.escape(content),style))
    def stable_canvas(*args,**kwargs):
        kwargs.update(invariant=1,pageCompression=1)
        return canvas.Canvas(*args,**kwargs)
    def footer(canvas,doc):
        canvas.saveState();canvas.setFont('YamrailReport',8)
        canvas.drawString(10*mm,9.5*mm,'LOCAL_EXECUTED / source class preserved / Human release pending')
        canvas.drawRightString(287*mm,9.5*mm,str(doc.page));canvas.restoreState()
    doc=SimpleDocTemplate(str(path),pagesize=landscape(A4),leftMargin=10*mm,rightMargin=10*mm,topMargin=10*mm,bottomMargin=13*mm,title='Read-only investigation report',author='YamRail local OSINT adapter')
    doc.build(blocks,canvasmaker=stable_canvas,onFirstPage=footer,onLaterPages=footer)


def make_report(case_path: Path, out: Path) -> dict:
    raw,case,kind=_report_case(case_path)
    native=_native()
    _,kernel,_,_,_,_,guard=native
    out=_out(out)
    register=_source_register(case,out)
    original=case['report_markdown'].encode('utf-8')
    (out/'original_report.md').write_bytes(original)
    if case.get('_source_document'):
        (out/'original_input.json').write_bytes(raw)
        (out/'derived_report.md').write_bytes(original)
    brief=[
        '1. Purpose: reconcile bounded source evidence before a coding task.',
        '2. Scope: '+case['scope']+'; source class '+case['evidence_class']+'.',
        '3. Method: exact source bytes -> frozen Markdown -> reused native typed graph.',
        '4. Finding: source statements, hypotheses and UNKNOWN/HOLD remain distinct.',
        '5. Next: Human investigator verifies sources and decides the authorized next step.',
    ]
    source_lines=[s['id']+' | '+s['title']+' | issuer '+s['issuer']+' | '+s['observed_at']+' | '+s['evidence_class']+' | SHA256 '+s['body_sha256'] for s in case['sources']]
    derived='# Read-only investigation report\n\n'+'\n'.join(brief)+'\n\n'+'Owner: '+case['owner']+'\nScope: '+case['scope']+'\nAs of: '+case['as_of']+'\nIssuer: '+case['issuer']+'\n\n## Preserved source Markdown\n\n'+case['report_markdown']+'\n\n## Source and issuer index\n\n'+'\n\n'.join(source_lines)+'\n\n## Remaining HOLD\n\nNo live sponsor query or new model inference occurred. Source independence, external origin and factual truth remain unverified. References do not establish causation. Human release and submission remain pending.\n'
    (out/'Report.md').write_bytes(derived.encode('utf-8'))
    (out/'report.md').write_bytes(derived.encode('utf-8'))
    inspection=guard.inspect_document(derived,{'language':'ja','document_type':'GENERAL','reader':'Hackathon judge and operator','destination':'Private candidate','medium':'HORIZONTAL'})
    _save(out/'document_inspection.json',inspection)
    _report_pdf(derived,out/'Report.pdf',kernel.FONT)
    (out/'report.pdf').write_bytes((out/'Report.pdf').read_bytes())
    graph=render_graph(case_path,out/'graph',graph_type=kind.lower())
    receipt={'schema':'yamrail.code-cli.osint-report-receipt/1','state':'PASS_PINNED_LOCAL_REPORT_AND_GRAPH' if graph['state']=='PASS_PINNED_LOCAL_OSINT_RENDER' else 'HOLD_REPORT_GRAPH_LOCAL','case_id':case['case_id'],
             'local_adapter_source_sha256':sha(Path(__file__).read_bytes()),
             'evidence_class':'LOCAL_EXECUTED','source_evidence_class':case['evidence_class'],'input_case_sha256':sha(raw),
             'ORIGINAL_MD_BYTE_SHA256':sha(original),'derived_report_md_sha256':sha(derived.encode('utf-8')),
             'original_md_preserved_exactly':(out/'original_report.md').read_bytes()==original,
             'five_line_initial_brief':brief,'source_register_sha256':sha((out/'source_register.json').read_bytes()),
             'graph_master_sha256':sha((out/'graph/graph_master.json').read_bytes()),'graph_receipt_sha256':sha((out/'graph/graph_receipt.json').read_bytes()),
             'document_guard':{'engine_sha256':guard.ENGINE_REVISION,'rule_revision':guard.RULE_REVISION,'status':inspection['status'],'findings':len(inspection['findings']),'document_mutation':'NONE','prose_correctness_certification':False},
             'files':_files(out,['Report.md','Report.pdf','report.md','report.pdf','original_report.md','source_register.json','document_inspection.json']),
             'source_pins':{'PR79':SOURCE_REF,'PR62':PR62_REF},'physical_page_mm':list(PAGE_MM),'minimum_margin_mm':MARGIN_MM,
             'new_provider_calls':0,'network_calls':0,'canonical_writes':0,'authority_effect':'NONE','external_release':'OWNER_RELEASE_PENDING'}
    if case.get('_source_document'):
        receipt['source_document']=case['_source_document']
        receipt['ORIGINAL_MD_BYTE_SHA256']=None
        receipt['DERIVED_MD_BYTE_SHA256']=sha(original)
        receipt['renderer_md_origin']='DERIVED_FROM_ORIGINAL_JSON_NOT_ORIGINAL_TARGET_SOURCE_MD'
        receipt['files'].update(_files(out,['original_input.json','derived_report.md']))
    _save(out/'report_receipt.json',receipt)
    return receipt
