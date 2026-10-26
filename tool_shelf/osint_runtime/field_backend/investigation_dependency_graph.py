"""Read-only process graph adapter for the existing fixed INGRIDGE pipeline.

This is a projection of persisted investigation references, never a replacement
for the model's silver board or a source-truth/adoption decision. The original
silver board renderer, font, metrics, vendor and export functions stay intact.
"""
from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

from . import silver_board_renderer as renderer
from .silver_export import self_contained_svg, vector_pdf

SCHEMA = 'yamrail.osint-dependency-graph/1'
KEY4 = ('workface_id', 'epoch', 'revision', 'input_sha256')
KEY7 = KEY4 + ('report_sha256', 'source_digest', 'graph_digest')
SHA = re.compile(r'[0-9a-f]{64}\Z')
CASE = re.compile(r'[0-9a-f]{32}\Z')
NS = 'http://www.w3.org/2000/svg'
WIDTH, HEIGHT = renderer.WIDTH, renderer.HEIGHT
ET.register_namespace('', NS)


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(',', ':'), allow_nan=False).encode('utf-8')


def digest(value):
    return hashlib.sha256(value).hexdigest()


def key(ref):
    if (not isinstance(ref, dict) or not CASE.fullmatch(str(ref.get('workface_id', '')))
            or any(type(ref.get(name)) is not int or ref[name] < 0 for name in ('epoch', 'revision'))
            or not SHA.fullmatch(str(ref.get('input_sha256', '')))):
        raise ValueError('OSINT_DEPENDENCY_GRAPH_REFERENCE_INVALID')
    return tuple(ref[name] for name in KEY4)


def verify_snapshot(snapshot):
    if (not isinstance(snapshot, dict) or snapshot.get('schema') != 'yamrail.osint-investigation-snapshot/1'
            or snapshot.get('read_only') is not True or snapshot.get('runtime_effect') != 'NONE'):
        raise ValueError('OSINT_DEPENDENCY_GRAPH_SNAPSHOT_REQUIRED')
    binding = snapshot.get('binding')
    key(binding)
    if (set(binding) != set(KEY7) or binding['workface_id'] != snapshot.get('id')
            or binding['report_sha256'] is not None and not SHA.fullmatch(str(binding['report_sha256']))
            or not all(SHA.fullmatch(str(binding.get(field, ''))) for field in ('source_digest', 'graph_digest'))
            or snapshot.get('snapshot_sha256') != digest(canonical({k:v for k,v in snapshot.items() if k != 'snapshot_sha256'}))):
        raise ValueError('OSINT_DEPENDENCY_GRAPH_SNAPSHOT_BINDING')
    source = {field: snapshot.get(field) for field in ('source_material', 'claims', 'previous_findings')}
    graph = {field: snapshot.get(field) for field in ('moot', 'previous_graph', 'continuity')}
    if (digest(canonical(source)) != binding['source_digest']
            or digest(canonical(graph)) != binding['graph_digest']):
        raise ValueError('OSINT_DEPENDENCY_GRAPH_SOURCE_MISMATCH')
    return binding


def _scene(snapshot, binding):
    continuity = snapshot.get('continuity') or {}
    nodes = {}
    for ref in [*continuity.get('ancestors', []), *continuity.get('parents', []), binding]:
        k = key(ref)
        if k not in nodes:
            nodes[k] = {'binding': dict(ref), 'record_state': 'UNKNOWN', 'created_at': None,
                        'typed_timestamps': None, 'material_count': None, 'claim_count': None}
    if len(nodes) > 15:
        raise ValueError('OSINT_DEPENDENCY_GRAPH_CANVAS_CAPACITY')
    current = nodes[key(binding)]
    current.update(record_state=snapshot.get('record_state', 'UNKNOWN'), created_at=snapshot.get('created_at'),
                   typed_timestamps=snapshot.get('typed_timestamps'),
                   material_count=len(snapshot.get('source_material') or []),
                   claim_count=len(snapshot.get('claims') or []))
    for entry in continuity.get('timeline', []):
        k = key(entry.get('binding'))
        if k in nodes and k != key(binding):
            nodes[k].update({field: entry.get(field) for field in ('record_state', 'created_at', 'typed_timestamps')})
    links = []
    for entry in continuity.get('links', []):
        parent, child = entry.get('parent'), entry.get('child')
        a, b = key(parent), key(child)
        if a not in nodes or b not in nodes or a == b:
            raise ValueError('OSINT_DEPENDENCY_GRAPH_LINEAGE_UNBOUND')
        if (a, b) not in links:
            links.append((a, b))
    # Current direct parents are explicit persisted references, not time-derived
    # causal claims. A missing saved edge is not filled by chronological order.
    for parent in continuity.get('parents', []):
        if (key(parent), key(binding)) not in links:
            raise ValueError('OSINT_DEPENDENCY_GRAPH_PARENT_EDGE_MISSING')
    incoming = {node: 0 for node in nodes}
    for _, child in links:
        incoming[child] += 1
    order = []
    queue = [node for node in nodes if incoming[node] == 0]
    while queue:
        node = queue.pop(0)
        order.append(node)
        for parent, child in links:
            if parent == node:
                incoming[child] -= 1
                if incoming[child] == 0:
                    queue.append(child)
    if len(order) != len(nodes):
        raise ValueError('OSINT_DEPENDENCY_GRAPH_CYCLE')
    return {'schema': 'yamrail.osint-dependency-process-scene/1',
            'binding': dict(binding), 'snapshot_sha256': snapshot['snapshot_sha256'],
            'nodes': [nodes[node] for node in order],
            'links': [{'parent': dict(nodes[a]['binding']), 'child': dict(nodes[b]['binding']),
                       'relation': 'PERSISTED_CONTEXT_REFERENCE', 'causation': 'NOT_INFERRED'} for a,b in links],
            'moot': snapshot.get('moot'), 'typed_timestamps': snapshot.get('typed_timestamps'),
            'unknown_count': len(snapshot.get('unresolved_unknowns') or []),
            'missing_fields': snapshot.get('missing_fields') or [],
            'model_output_is_source_evidence': False, 'authority_effect': 'NONE'}


def _render(scene, snapshot):
    # Reuse the same pinned renderer module, glyph metrics, font and actual CAD
    # primitive renderer. No browser layout, alternate font or bitmap renderer.
    if (digest(renderer.VENDOR.read_bytes()) != renderer.VENDOR_SHA256
            or digest(renderer.FONT.read_bytes()) != renderer.FONT_SHA256):
        raise ValueError('OSINT_DEPENDENCY_GRAPH_RENDERER_IDENTITY')
    renderer._metrics()
    model, texts, bounds = [], {}, []
    def primitive(kind, layer, color, points, body=()):
        model.append({'type': kind, 'body': list(body), 'layer': layer, 'color': color,
                      'points': [(x, HEIGHT-y) for x,y in points]})
    def line(layer, x1,y1,x2,y2,color='#b8c7d0'):
        primitive('LINE',layer,color,[(x1,y1),(x2,y2)])
    def rect(layer,x,y,w,h,fill='#f3f7fc'):
        primitive('SOLID',layer,fill,[(x,y),(x+w,y),(x+w,y+h),(x,y+h)])
        for a,b in [((x,y),(x+w,y)),((x+w,y),(x+w,y+h)),((x+w,y+h),(x,y+h)),((x,y+h),(x,y))]:
            line(layer,*a,*b)
    def text(layer,value,x,y,size,width,color='#102f3c'):
        if not isinstance(value,str) or '\n' in value or '\r' in value:
            raise ValueError('OSINT_DEPENDENCY_GRAPH_TEXT_NOT_FROZEN')
        measured=renderer._line_width(value,size)
        if measured>width+0.001 or x<0 or y-size<0 or x+measured>WIDTH or y+size*0.3>HEIGHT:
            raise ValueError('OSINT_DEPENDENCY_GRAPH_TEXT_GEOMETRY')
        token='YRDEPTEXT'+str(len(texts)).zfill(5)
        texts[token]=(value,size)
        bounds.append({'layer':layer,'x':x,'baseline':y,'font_size':size,
                       'measured_width':round(measured,6),'allowed_width':width})
        primitive('TEXT',layer,color,[(x,y)],[(1,token),(40,size),(50,0)])
    rect('00_frame',0.8,0.8,WIDTH-1.6,HEIGHT-1.6,'#ffffff')
    text('10_header','調査の依存関係と引継ぎ',22,38,26,1100)
    text('10_header','矢印は保存された参照関係です。出来事の因果を示しません。',22,68,15,1350,'#536873')
    line('11_rule',0,84,WIDTH,84)
    positions={}
    state_labels={'COMMITTED_HISTORICAL_RESULT':'確定結果あり','NO_COMMITTED_RESULT':'確定結果なし',
                  'UNKNOWN':'工程状態 UNKNOWN','PARTIAL':'部分情報あり'}
    for index,node in enumerate(scene['nodes']):
        ref=node['binding']; k=key(ref)
        x,y=22+(index%3)*465,112+(index//3)*151
        positions[k]=(x,y,438,130)
        layer='20_node_'+str(index)
        rect(layer,x,y,438,130)
        text(layer,'調査 '+str(index+1),x+12,y+23,17,410,'#0060df')
        text(layer,ref['workface_id'],x+12,y+44,12,410)
        text(layer,'Epoch '+str(ref['epoch'])+' / Revision '+str(ref['revision']),x+12,y+65,13,410)
        state=state_labels.get(node.get('record_state'),'工程状態は保存記録を参照')
        text(layer,state,x+12,y+86,14,410)
        created=node.get('created_at')
        if not isinstance(created,str) or len(created)>48:
            created='UNKNOWN'
        text(layer,'調査作成 '+created,x+12,y+105,11,410,'#536873')
        if node['material_count'] is not None:
            value='原資料 '+str(node['material_count'])+' / 記載 '+str(node['claim_count'])
        else:
            value='本文・資料・時刻の根拠は保存参照を継承'
        text(layer,value,x+12,y+123,11,410,'#536873')
    for index,link in enumerate(scene['links']):
        a,b=positions[key(link['parent'])],positions[key(link['child'])]
        layer='30_ref_'+str(index)
        if a[1]==b[1]:
            x1,y1=a[0]+a[2],a[1]+68
            x2,y2=b[0],b[1]+68
            if b[0]-a[0]>465:
                gutter=a[1]-8
                line(layer,x1,y1,x1+7,y1,'#0060df')
                line(layer,x1+7,y1,x1+7,gutter,'#0060df')
                line(layer,x1+7,gutter,x2-7,gutter,'#0060df')
                line(layer,x2-7,gutter,x2-7,y2,'#0060df')
                line(layer,x2-7,y2,x2,y2,'#0060df')
            else:
                line(layer,x1,y1,x2,y2,'#0060df')
            line(layer+'_arrow',x2,y2,x2-5,y2-4,'#0060df')
            line(layer+'_arrow',x2,y2,x2-5,y2+4,'#0060df')
        else:
            # Fixed inter-row gutter, never through text areas.
            x1,y1=a[0]+a[2]/2,a[1]+a[3]
            x2,y2=b[0]+b[2]/2,b[1]
            gutter=y1+10
            rail=1403+(index%5)*2
            line(layer,x1,y1,x1,gutter,'#0060df')
            line(layer,x1,gutter,rail,gutter,'#0060df')
            line(layer,rail,gutter,rail,y2-10,'#0060df')
            line(layer,rail,y2-10,x2,y2-10,'#0060df')
            line(layer,x2,y2-10,x2,y2,'#0060df')
            line(layer+'_arrow',x2,y2,x2-4,y2-5,'#0060df')
            line(layer+'_arrow',x2,y2,x2+4,y2-5,'#0060df')
    line('40_footer_rule',0,897,WIDTH,897)
    text('41_footer','未知事項 '+str(scene['unknown_count'])+'件 / 欠損項目 '+str(len(scene['missing_fields']))+'件。欠損を否定や矛盾へ変換しません。',22,923,16,1365)
    moots=scene.get('moot') or {}
    count=len(moots.get('moots') or []) if isinstance(moots,dict) else 0
    text('41_footer','Moot記録 '+str(count)+'件。未記録を不存在とは扱わず、原資料・モデル候補・時刻を区別して継承します。',22,952,15,1365)
    text('41_footer','本文・原資料・各時刻の原表記と正規化値は、同じ調査盤面とMDで確認できます。',22,980,14,1365,'#536873')
    raw=renderer._vendor_module().render_svg(model,(0,0,WIDTH,HEIGHT),width=WIDTH,height=HEIGHT,margin=0)
    svg=ET.fromstring(raw)
    svg.set('id','yamrail-dependency-graph')
    svg.set('role','group')
    svg.set('aria-label','調査の依存関係。矢印は保存参照であり、出来事の因果ではありません。')
    svg.set('preserveAspectRatio','xMidYMid meet')
    svg.set('font-family',renderer.FONT_FAMILY)
    svg.set('font-kerning','none');svg.set('font-variant-ligatures','none')
    svg.set('data-font-sha256',renderer.FONT_SHA256)
    svg.set('data-font-asset',renderer.FONT_URL)
    replaced=0
    for element in svg.iter():
        element.attrib.pop('vector-effect',None)
        if element.tag=='{'+NS+'}text':
            value,size=texts[element.text]
            element.text=value
            element.set('font-family',renderer.FONT_FAMILY);element.set('font-size',str(size))
            element.set('font-kerning','none');element.set('font-variant-ligatures','none')
            replaced+=1
        if element.tag=='{'+NS+'}polygon':element.set('fill-opacity','1')
    if replaced!=len(texts):raise ValueError('OSINT_DEPENDENCY_GRAPH_TEXT_IDENTITY')
    metadata={'schema':'yamrail.osint-dependency-graph-render/1','binding':dict(scene['binding']),
              'snapshot_sha256':snapshot['snapshot_sha256'],
              'source_digest':scene['binding']['source_digest'],'graph_digest':scene['binding']['graph_digest'],
              'scene_sha256':digest(canonical(scene)),
              'renderer_sha256':digest(Path(renderer.__file__).read_bytes()),
              'adapter_sha256':digest(Path(__file__).read_bytes()),
              'vendor_renderer_sha256':renderer.VENDOR_SHA256,'font_sha256':renderer.FONT_SHA256,
              'font_metrics_sha256':renderer.METRICS_SHA256,'font_family':renderer.FONT_FAMILY,
              'font_asset':renderer.FONT_URL,'logical_canvas':{'width':WIDTH,'height':HEIGHT},
              'text_reflow':False,'text_truncation':False,'font_substitution':False,
              'authority_effect':'NONE','source_truth':'NOT_ESTABLISHED_BY_RENDERING',
              'moot_framing':'Existing dependencies, unknown issues and process handoff; no new Moot transitions.',
              'node_count':len(scene['nodes']),'reference_count':len(scene['links']),
              'text_geometry':bounds,'vendor_render_invocations':1}
    ET.SubElement(svg,'{'+NS+'}metadata').text=canonical({k:v for k,v in metadata.items() if k!='text_geometry'}).decode('utf-8')
    serialized=ET.tostring(svg,encoding='unicode',short_empty_elements=True)+'\n'
    metadata['svg_sha256']=digest(serialized.encode('utf-8'))
    return {'svg':serialized,'metadata':metadata}


def dependency_graph(snapshot):
    binding=verify_snapshot(snapshot)
    scene=_scene(snapshot,binding)
    render=_render(scene,snapshot)
    return {'schema':SCHEMA,'binding':dict(binding),'snapshot_sha256':snapshot['snapshot_sha256'],
            'source_digest':binding['source_digest'],'graph_digest':binding['graph_digest'],
            'scene_sha256':digest(canonical(scene)),'scene':scene,'render':render,
            'read_only':True,'runtime_effect':'NONE','new_provider_calls':0,'authority_effect':'NONE'}


def export_dependency_graph(snapshot, output_format):
    if output_format not in {'svg','pdf'}:
        raise ValueError('OSINT_DEPENDENCY_GRAPH_EXPORT_FORMAT')
    graph=dependency_graph(snapshot)
    render=graph['render'];metadata=render['metadata']
    raw=render['svg'].encode('utf-8');node=ET.fromstring(raw)
    if metadata['svg_sha256']!=digest(raw) or digest(renderer.FONT.read_bytes())!=renderer.FONT_SHA256:
        raise ValueError('OSINT_DEPENDENCY_GRAPH_MASTER_BINDING')
    if output_format=='svg':
        data,mime=self_contained_svg(node,metadata['svg_sha256']),'image/svg+xml'
    else:
        data,mime=vector_pdf(raw,metadata),'application/pdf'
    if not 1<=len(data)<=16*1024*1024:
        raise ValueError('OSINT_DEPENDENCY_GRAPH_EXPORT_BOUND')
    return {'schema':'yamrail.osint-dependency-graph-export/1','format':output_format,
            'content_type':mime,'data_base64':base64.b64encode(data).decode('ascii'),
            'sha256':digest(data),'source_svg_sha256':metadata['svg_sha256'],
            'font_sha256':renderer.FONT_SHA256,'binding':dict(graph['binding']),
            'snapshot_sha256':graph['snapshot_sha256'],'source_digest':graph['source_digest'],
            'graph_digest':graph['graph_digest'],'scene_sha256':graph['scene_sha256'],
            'filename':'YamRail-OSINT-dependency-'+snapshot['id']+'.'+output_format,
            'runtime_effect':'NONE','new_provider_calls':0}
