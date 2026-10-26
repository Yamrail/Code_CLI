"""Fixed R027 projection through the immutable INGRIDGE CAD primitive renderer.

The adapter never summarizes, wraps, trims or interprets the supplied line arrays.
The historical renderer remains byte-identical; its DXF text cleaning is bypassed
with placeholders that are replaced with the exact validated strings in XML.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import math
from functools import lru_cache
from pathlib import Path
import xml.etree.ElementTree as ET

WIDTH, HEIGHT = 1414, 1000
FONT_FAMILY = 'YamrailBoard'
FONT_SHA256 = 'fe4be4a7c74a871ddca7dbc7e61895dd35862334afd36e5874a121a4d4454ee4'
METRICS_SHA256 = '7a536935999798f62bb4340628c5934f9fcdb9224acfbc7f2a7241e68538c13d'
VENDOR_SHA256 = 'a16e158a5eadc10587e5cdc8fa7969610de83c0c01dca672254538a35c910a7b'
ROOT = Path(__file__).resolve().parents[1]
FONT = ROOT / 'frontend/fonts/YamrailBoard-Regular.ttf'
METRICS = ROOT / 'frontend/fonts/YamrailBoard-Regular.metrics.json'
VENDOR = ROOT / 'vendor/ingridge_cad_display_station_v1/cad_display_station.py'
FONT_URL = '/private/osint/canary/fonts/YamrailBoard-Regular.ttf'
NS = 'http://www.w3.org/2000/svg'
ET.register_namespace('', NS)
DOMAIN_LABELS = {
    'INFRA': 'インフラ・設備',
    'LOGISTICS': '物流・荷さばき・補給',
    'ECONOMY': '経済・調達・金融',
    'CULTURE_LANG': '文化・現地言語・動静',
    'RUMOR': '現地雑音・噂・未確認言説',
}
NODE_LABELS = {
    'SOURCE_STATEMENT': '前工程：記載の帰属',
    'PROPAGATION': '中工程：転載・派生',
    'CONDITIONAL_HYPOTHESIS': '後工程：条件付き仮説',
    'LEAD': '中工程：探索の手掛かり',
    'UNKNOWN': '中工程：未接続・未知',
}
STATUS_LABELS = {
    'ATTRIBUTED': '出典帰属', 'LEAD': '手掛かり',
    'CONDITIONAL': '条件付き', 'UNKNOWN': '不明',
    'CONTINUED_OBSERVATION': '継続観測',
    'CONTRADICTION_CANDIDATE': '矛盾候補',
}
TIME_LABELS = {'EVENT': '出来事', 'PUBLICATION': '発表', 'RETRIEVAL': '取得', 'UNKNOWN': '種別不明'}
INK, MUTED, BLUE, LINE, PALE, AMBER = '#102f3c', '#536873', '#0060df', '#b8c7d0', '#f3f7fc', '#8a5100'


class BoardRenderUnavailable(ValueError):
    """A local projection failure; the caller must preserve the original answer."""


def _canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(',', ':'), allow_nan=False).encode('utf-8')


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


@lru_cache(maxsize=1)
def _vendor_module():
    spec = importlib.util.spec_from_file_location('yamrail_immutable_ingridge_cad', VENDOR)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@lru_cache(maxsize=1)
def _metrics():
    raw = METRICS.read_bytes()
    if _sha(raw) != METRICS_SHA256:
        raise BoardRenderUnavailable('BOARD_FONT_METRICS_IDENTITY')
    value = json.loads(raw)
    if value.get('font_sha256') != FONT_SHA256:
        raise BoardRenderUnavailable('BOARD_FONT_METRICS_IDENTITY')
    return value


def _line_width(text, size):
    metrics = _metrics()
    try:
        units = sum(metrics['advances'][str(ord(char))] for char in text)
    except (KeyError, TypeError):
        raise BoardRenderUnavailable('BOARD_FONT_GLYPH_UNAVAILABLE') from None
    return units * size / metrics['units_per_em']


def render_board(board, binding, source_ledger, *, purpose=None, projection=None, raw_model_text=None):
    """Return {svg, metadata}; every content line is already semantically frozen.

    Screen and export consumers must retain this exact geometry and font identity.
    Authentication and fresh Revision/export admission remain the caller's duty.
    """
    if (purpose == 'EXPLANATORY_PONCHI_DIAGRAM' and isinstance(projection, dict)
            and projection.get('derivation') == 'STRUCTURED_MD_GRAPH'):
        from .structured_md_renderer import render_structured
        return render_structured(board,binding,source_ledger,projection=projection,raw_model_text=raw_model_text)
    from .silver_board import validate_board
    from .explanatory_graph import PURPOSE, validate_partial_board, is_explanatory
    explanatory = purpose == PURPOSE
    derived = explanatory and isinstance(projection,dict) and projection.get('derivation') == 'AVAILABLE_MD_EXCERPTS'
    if purpose is not None and not explanatory:
        raise BoardRenderUnavailable('BOARD_PURPOSE_UNSUPPORTED')
    if explanatory:
        if derived:
            from .explanatory_graph import validate_projection
            if not isinstance(raw_model_text,str):
                raise BoardRenderUnavailable('BOARD_DERIVED_ORIGINAL_RAW_REQUIRED')
            try:
                from .explanatory_graph import parse_output as parse_explanatory
                analysis,_=parse_explanatory(raw_model_text,source_ledger,binding)
                validate_projection(projection,analysis,source_ledger,binding,raw_model_text=raw_model_text)
            except (ValueError,TypeError,KeyError):
                raise BoardRenderUnavailable('BOARD_DERIVED_EXACT_MD_BINDING') from None
        validate_partial_board(board, source_ledger)
        if (not is_explanatory(projection) or projection.get('board') != board
                or projection.get('binding') != binding
                or projection.get('board_sha256') != _sha(_canonical(board))
                or projection.get('source_ledger_sha256') != source_ledger.get('sha256')
                or not isinstance(projection.get('md_semantics'), dict)
                or projection['md_semantics'].get('canonical_md_sha256') != projection.get('analysis_sha256')):
            raise BoardRenderUnavailable('BOARD_EXPLANATORY_PROJECTION_BINDING')
    else:
        validate_board(board, source_ledger)
    if (not isinstance(binding, dict) or set(binding) !=
            {'workface_id', 'epoch', 'revision', 'input_sha256'}
            or source_ledger.get('binding') != binding):
        raise BoardRenderUnavailable('BOARD_BINDING_MISMATCH')
    ledger_without_hash = {key: value for key, value in source_ledger.items() if key != 'sha256'}
    if source_ledger.get('sha256') != _sha(_canonical(ledger_without_hash)):
        raise BoardRenderUnavailable('BOARD_SOURCE_LEDGER_IDENTITY')
    if _sha(VENDOR.read_bytes()) != VENDOR_SHA256 or _sha(FONT.read_bytes()) != FONT_SHA256:
        raise BoardRenderUnavailable('BOARD_RENDERER_OR_FONT_IDENTITY')
    model, texts, layers, bounds = [], {}, {}, []

    def primitive(kind, layer, color, points, body=()):
        model.append({'type': kind, 'body': list(body), 'layer': layer,
                      'color': color, 'points': [(x, HEIGHT-y) for x, y in points]})

    def line(layer, x1, y1, x2, y2, color=LINE):
        primitive('LINE', layer, color, [(x1, y1), (x2, y2)])

    def rectangle(layer, x, y, width, height, fill=None, stroke=LINE):
        if fill:
            primitive('SOLID', layer, fill,
                      [(x, y), (x+width, y), (x+width, y+height), (x, y+height)])
        if stroke:
            line(layer, x, y, x+width, y, stroke)
            line(layer, x+width, y, x+width, y+height, stroke)
            line(layer, x+width, y+height, x, y+height, stroke)
            line(layer, x, y+height, x, y, stroke)

    def text(layer, value, x, baseline, size, width, color=INK):
        if not isinstance(value, str) or '\n' in value or '\r' in value:
            raise BoardRenderUnavailable('BOARD_LINE_NOT_FROZEN')
        measured = _line_width(value, size)
        # Explanatory text is a complete MD line. Font fitting preserves every
        # character; visual density is not a semantic admission condition.
        if explanatory and measured > width and measured > 0:
            size = size * width / measured
            measured = _line_width(value, size)
        if measured > width + 0.001 or x < 0 or baseline-size < 0 or x+measured > WIDTH or baseline+size*0.3 > HEIGHT:
            raise BoardRenderUnavailable('BOARD_TEXT_GEOMETRY_OVERFLOW')
        token = 'YRBOARDTEXT' + str(len(texts)).zfill(5)
        texts[token] = {'text': value, 'size': size, 'width': measured}
        bounds.append({'layer': layer, 'x': x, 'baseline': baseline,
                       'font_size': size, 'measured_width': round(measured, 6), 'allowed_width': width})
        primitive('TEXT', layer, color, [(x, baseline)], [(1, token), (40, size), (50, 0)])

    def semantic(layer, kind, refs=(), **extra):
        layers[layer] = {'kind': kind, 'source_refs': list(refs), **extra}

    def refs(layer, values, x, baseline, width):
        if values:
            text(layer, '出典 ' + ' '.join(values), x, baseline, 10, width, MUTED)

    # Only geometry is generated here. No DOM reflow, hidden detail or clipping.
    rectangle('00_frame', 0.8, 0.8, WIDTH-1.6, HEIGHT-1.6, '#ffffff', LINE)
    line('01_grid', 0, 80, WIDTH, 80)
    line('01_grid', 0, 900, WIDTH, 900)
    line('01_grid', 707, 80, 707, 900)
    line('01_grid', 707, 490, WIDTH, 490)
    for row in range(1, 5):
        line('01_grid', 0, 80+164*row, 707, 80+164*row)
    text('10_header', board['title'], 18, 36, 26, 855)
    text('10_header', board['coverage_lines'][0], 18, 66, 15, 855, MUTED)
    text('10_header', board['scope_lines'][0], 900, 34, 14, 495, MUTED)
    text('10_header', 'MDの記載・根拠・仮説のつながり' if explanatory else '依存関係・未知事項・工程間の引継ぎ', 900, 61, 13, 495, MUTED)
    text('10_header', '点線：MDの明示関係。真偽・独立性は不明' if explanatory else '点線：工程間の接続・独立性は未確認', 510, 66, 12, 365, MUTED)

    global_locations, global_labels = {}, {}
    if explanatory:
        for row_index, row_lane in enumerate(board['lanes']):
            step = 693 / max(1, len(row_lane['nodes']))
            for column, node in enumerate(row_lane['nodes']):
                global_locations[node['id']] = (14+step*column, 80+164*row_index+34, step-20, 106)
                global_labels[node['id']] = node['lines'][0]
    for index, lane in enumerate(board['lanes']):
        top = 80 + 164*index
        text(f'20_lane_{index}', '分野未分類・MD本文の引用' if derived else DOMAIN_LABELS[lane['domain']], 16, top+25, 18, 675, BLUE)
        locations = {}
        column_step = 693 / max(1, len(lane['nodes'])) if explanatory else 233
        card_width = column_step - 20 if explanatory else 213
        content_width = card_width - 16
        for column, node in enumerate(lane['nodes']):
            x, layer = 14+column_step*column, f'30_node_{index}_{column}'
            locations[node['id']] = (x, top+34, card_width, 106)
            semantic(layer, 'node', node['source_refs'], node_id=node['id'], domain=lane['domain'], status=node['status'], accessible_label=node['lines'][0])
            rectangle(layer, x, top+34, card_width, 106, PALE, LINE)
            text(layer, 'MD引用 / 不明' if explanatory else NODE_LABELS[node['kind']]+' / '+STATUS_LABELS[node['status']], x+8, top+50, 11, content_width, MUTED)
            for row, value in enumerate(node['lines']):
                text(layer, value, x+8, top+70+17*row, 16, content_width)
            refs(layer, node['source_refs'], x+8, top+135, content_width)
        for edge_index, edge in enumerate(lane['edges']):
            layer = f'40_edge_{index}_{edge_index}'
            labels = global_labels if explanatory else {node['id']: node['lines'][0] for node in lane['nodes']}
            semantic(layer, 'edge', edge['support_refs'], relation=edge['relation'], independence_status=edge['independence_status'], from_node=edge['from'], to_node=edge['to'], accessible_label=labels[edge['from']]+'から'+labels[edge['to']])
            positions = global_locations if explanatory else locations
            a, b = positions[edge['from']], positions[edge['to']]
            if explanatory and a[1] != b[1]:
                # Explicit MD relationships survive cross-domain presentation.
                # Crossings do not invalidate a semantic dependency.
                x1, y1 = a[0]+a[2], a[1]+a[3]/2
                x2, y2 = b[0], b[1]+b[3]/2
                line(layer, x1, y1, x2, y2, MUTED)
                length = math.hypot(x2-x1, y2-y1)
                ux, uy = (x2-x1)/length, (y2-y1)/length
                line(layer+'_arrow', x2, y2, x2-5*ux+3*uy, y2-5*uy-3*ux, MUTED)
                line(layer+'_arrow', x2, y2, x2-5*ux-3*uy, y2-5*uy+3*ux, MUTED)
                continue
            forward = a[0] < b[0]
            x1, x2 = (a[0]+a[2], b[0]) if forward else (a[0], b[0]+b[2])
            y = top+88+edge_index*(min(7, 45/max(1, len(lane['edges'])-1)) if explanatory else 7)
            direction = 1 if forward else -1
            if abs(a[0]-b[0]) > column_step + 0.001:
                # A non-adjacent relationship passes above the middle card.
                # No connector may run through another node's content.
                via1, via2 = x1+direction*7, x2-direction*7
                line(layer, x1, y, via1, y, MUTED)
                line(layer, via1, y, via1, top+32, MUTED)
                line(layer, via1, top+32, via2, top+32, MUTED)
                line(layer, via2, top+32, via2, y, MUTED)
                line(layer, via2, y, x2, y, MUTED)
            else:
                line(layer, x1, y, x2, y, MUTED)
            line(layer+'_arrow', x2, y, x2-direction*5, y-3, MUTED)
            line(layer+'_arrow', x2, y, x2-direction*5, y+3, MUTED)
        if lane['distortion'] is not None:
            warning = lane['distortion']
            layer = f'50_distortion_{index}'
            semantic(layer, 'distortion', warning['source_refs'], domain=lane['domain'], accessible_label=warning['lines'][0])
            text(layer, '転載変質：'+warning['lines'][0], 16, top+158, 12, 675, AMBER)

    text('60_timeline_heading', '時空間の突合', 725, 111, 21, 670, BLUE)
    if not board['timeline']:
        text('61_timeline_empty', 'この盤面には日付付き事象の記載がありません。', 725, 150, 17, 670, MUTED)
    for index, event in enumerate(board['timeline']):
        top, layer = 128+82*index, f'62_timeline_{index}'
        semantic(layer, 'timeline', event['source_refs'], event_id=event['id'], time_kind=event['time_kind'], accessible_label=event['lines'][0])
        expressed = event['expressed_date'] if event['expressed_date'] is not None else '原文日付なし'
        normalized = event['normalized_date'] if event['normalized_date'] is not None else '正規化未確定'
        text(layer, TIME_LABELS[event['time_kind']]+' / 原文 '+expressed+' / 正規化 '+normalized, 725, top+16, 13, 670, MUTED)
        for row, value in enumerate(event['lines']):
            text(layer, value, 738, top+38+20*row, 17, 657)
        refs(layer, event['source_refs'], 738, top+75, 657)
        if index < 3:
            line('63_timeline_guides', 725, top+23, 725, top+78, LINE)

    text('70_next_heading', '探索点・未接続事項は正本MDを参照' if explanatory else '次の測点 — 未接続を次工程へ引き継ぐ', 725, 520, 20, 670, BLUE)
    for index, station in enumerate(board['next_stations']):
        top, layer = 532+120*index, f'72_station_{index}'
        semantic(layer, 'next_station', station['source_refs'], domain=station['domain'], status=station['status'], accessible_label=station['missing_lines'][0])
        rectangle(layer, 720, top, 680, 115, '#ffffff', LINE)
        label = DOMAIN_LABELS[station['domain']]+' / '+STATUS_LABELS.get(station['status'], station['status'])
        text(layer, label, 730, top+15, 12, 660, BLUE)
        for row, (field, prefix) in enumerate((('missing_lines','欠落'), ('target_lines','観測'), ('discriminator_lines','分岐'), ('value_lines','価値'))):
            text(layer, prefix, 730, top+36+20*row, 12, 45, MUTED)
            text(layer, station[field][0], 778, top+36+20*row, 16, 612)
        refs(layer, station['source_refs'], 730, top+110, 660)

    for index, (field, label) in enumerate((('synthesis_lines','現在の見立て'), ('bottleneck_lines','構造的な制約'), ('moot_condition_lines','分岐・重心移動条件'))):
        baseline = 925+28*index
        text('80_footer', label, 16, baseline, 12, 108, BLUE)
        text('80_footer', board['footer'][field][0], 126, baseline, 18, 1270)

    # This is the actual reused primitive renderer, with an exact 1:1 transform.
    raw = _vendor_module().render_svg(model, (0, 0, WIDTH, HEIGHT),
                                      width=WIDTH, height=HEIGHT, margin=0)
    svg = ET.fromstring(raw)
    svg.set('id', 'yamrail-silver-board')
    svg.set('role', 'group')
    svg.set('aria-label', board['title']+'。分野別の判断材料と次の測点。')
    svg.set('preserveAspectRatio', 'xMidYMid meet')
    svg.set('data-board-schema', 'yamrail.osint-silver-board/1')
    svg.set('data-font-sha256', FONT_SHA256)
    svg.set('data-font-asset', FONT_URL)
    svg.set('font-family', FONT_FAMILY)
    svg.set('font-kerning', 'none')
    svg.set('font-variant-ligatures', 'none')
    svg.find('{'+NS+'}rect').set('fill', '#ffffff')
    replaced = 0
    for group in svg.findall('{'+NS+'}g'):
        layer = group.get('data-layer', '')
        info = layers.get(layer)
        if info:
            group.set('data-board-kind', info['kind'])
            group.set('data-source-refs', ' '.join(info['source_refs']))
            if info['source_refs']:
                group.set('tabindex', '0')
                group.set('role', 'button')
                group.set('aria-label', info['accessible_label']+'。出典 '+' '.join(info['source_refs'])+'を盤面外で読む')
            for key, value in info.items():
                if key not in {'kind', 'source_refs', 'accessible_label'}:
                    group.set('data-'+key.replace('_','-'), str(value))
        for element in group:
            if element.tag == '{'+NS+'}text':
                frozen = texts.get(element.text)
                if frozen is None:
                    raise BoardRenderUnavailable('BOARD_TEXT_REPLACEMENT_IDENTITY')
                element.text = frozen['text']
                element.set('font-family', FONT_FAMILY)
                element.set('font-size', str(frozen['size']))
                element.set('font-kerning', 'none')
                element.set('font-variant-ligatures', 'none')
                replaced += 1
            if element.tag == '{'+NS+'}polygon':
                element.set('fill-opacity', '1')
            element.attrib.pop('vector-effect', None)
            if layer.startswith('40_edge_') and not layer.endswith('_arrow'):
                element.set('stroke-dasharray', '4 3')
            if layer.startswith('72_station_') and element.tag == '{'+NS+'}line':
                element.set('stroke-dasharray', '4 3')
    if replaced != len(texts):
        raise BoardRenderUnavailable('BOARD_TEXT_REPLACEMENT_IDENTITY')
    metadata = {
        'schema': 'yamrail.osint-silver-board-render/1',
        'interface_spec_id': 'YR-UI-SILVER-RATIO-SURFACE-V1.1',
        'moot_framing': 'Existing dependencies, unknown issues and inter-stage handoff; not rejected hypotheses. No new Moot structures or transitions are generated.',
        'binding': dict(binding), 'board_sha256': _sha(_canonical(board)),
        'source_ledger_sha256': source_ledger['sha256'],
        'renderer_sha256': _sha(Path(__file__).read_bytes()),
        'vendor_renderer_sha256': VENDOR_SHA256,
        'vendor_source_status': 'PRIVATE_PROTOTYPE_NON_CANONICAL_REUSED_PRIMITIVES_ONLY',
        'font_sha256': FONT_SHA256, 'font_asset': FONT_URL, 'font_family': FONT_FAMILY,
        'font_metrics_sha256': METRICS_SHA256,
        'logical_canvas': {'width': WIDTH, 'height': HEIGHT},
        'zones': {'header': [0,0,1414,80], 'body': [0,80,1414,820],
                  'left': [0,80,707,820], 'timeline': [707,80,707,410],
                  'next_stations': [707,490,707,410], 'footer': [0,900,1414,100]},
        'physical_page_mm': [297,210], 'uniform_fit_mm': [296.94,210],
        'side_margin_mm': 0.03,
        'text_lines': len(texts), 'text_geometry': bounds,
        'primitive_count': len(model), 'vendor_render_invocations': 1,
        'text_reflow': False, 'text_truncation': False, 'font_substitution': False,
        'solid_verified_relationship_edges': 0,
        'authority_effect': 'NONE', 'source_truth': 'NOT_ESTABLISHED_BY_RENDERING',
    }
    if explanatory:
        metadata.update(purpose=PURPOSE,
                        canonical_md_sha256=projection['analysis_sha256'],
                        md_semantics_sha256=_sha(_canonical(projection['md_semantics'])),
                        semantic_validation=projection['md_semantics']['validation_state'],
                        responsibility_scope='OSINT_EXPLANATORY_PRESENTATION_ONLY_NOT_ENGINEERING_DELIVERABLE',
                        completeness_required=False, deterministic_font_fit=True)
        svg.set('data-purpose', PURPOSE)
        if derived:
            metadata.update(derivation='AVAILABLE_MD_EXCERPTS',domain_assignment='UNKNOWN_LAYOUT_SLOTS_ONLY',
                            origin='SERVER_DETERMINISTIC_MD_EXCERPTS_NOT_MODEL_GRAPH')
            svg.set('data-derivation','AVAILABLE_MD_EXCERPTS')
    content = ET.SubElement(svg, '{'+NS+'}metadata')
    content.text = _canonical({key: value for key, value in metadata.items() if key != 'text_geometry'}).decode('utf-8')
    serialized = ET.tostring(svg, encoding='unicode', short_empty_elements=True)+'\n'
    metadata['svg_sha256'] = _sha(serialized.encode('utf-8'))
    return {'svg': serialized, 'metadata': metadata}
