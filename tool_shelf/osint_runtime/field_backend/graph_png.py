"""Rasterize the closed OS graph SVG vocabulary with a fixed font and geometry.

This is deliberately not a general SVG interpreter. Unsupported presentation
fails locally; no text, transform, style, or shape is silently discarded.
"""
from __future__ import annotations

import hashlib
import io
import json
import math
import os
from pathlib import Path
import platform
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import threading
import unicodedata
import xml.etree.ElementTree as ET
import zlib

from PIL import Image, ImageDraw, ImageFont, PngImagePlugin, features, __version__
from PIL import _imaging, _imagingft

WIDTH, HEIGHT, SCALE = 1414, 1000, 2
MAX_SVG_BYTES, MAX_ELEMENTS, MAX_TEXT = 4 * 1024 * 1024, 2000, 32000
MAX_PNG_BYTES = 16 * 1024 * 1024
RENDER_TIMEOUT_SECONDS, REAP_TIMEOUT_SECONDS = 30, 5
_RENDER_SLOT = threading.BoundedSemaphore(1)
ROOT = Path(__file__).resolve().parents[1]
FONT = ROOT / 'frontend/fonts/YamrailBoard-Regular.ttf'
METRICS = ROOT / 'frontend/fonts/YamrailBoard-Regular.metrics.json'
FONT_SHA = 'fe4be4a7c74a871ddca7dbc7e61895dd35862334afd36e5874a121a4d4454ee4'
METRICS_SHA = '7a536935999798f62bb4340628c5934f9fcdb9224acfbc7f2a7241e68538c13d'
NS = 'http://www.w3.org/2000/svg'
NUMBER = re.compile(r'[-+]?(?:\d+(?:\.\d*)?|\.\d+)\Z')
ROTATE = re.compile(r'rotate\(\s*([-+]?0(?:\.0+)?)\s+([-+]?\d+(?:\.\d+)?)\s+([-+]?\d+(?:\.\d+)?)\s*\)\Z')
XML_DECL = re.compile(r'''\A<\?xml[ \t\r\n]+version=(["'])1\.0\1(?:[ \t\r\n]+encoding=(["'])(?:UTF-8|utf-8)\2)?(?:[ \t\r\n]+standalone=(["'])(?:yes|no)\3)?[ \t\r\n]*\?>''')
COLOR = re.compile(r'#[0-9a-fA-F]{6}\Z|#[0-9a-fA-F]{3}\Z')
SHARED = {'id', 'role', 'aria-label', 'tabindex', 'font-family', 'font-kerning', 'font-variant-ligatures', 'transform'}
ATTRS = {
    'svg': {'viewBox', 'width', 'height', 'preserveAspectRatio'},
    'g': set(), 'metadata': set(),
    'rect': {'x', 'y', 'width', 'height', 'fill', 'fill-opacity', 'stroke', 'stroke-width', 'stroke-opacity'},
    'line': {'x1', 'y1', 'x2', 'y2', 'fill', 'stroke', 'stroke-width', 'stroke-opacity', 'stroke-dasharray', 'vector-effect'},
    'polygon': {'points', 'fill', 'fill-opacity', 'stroke', 'stroke-width', 'stroke-opacity', 'vector-effect'},
    'text': {'x', 'y', 'fill', 'fill-opacity', 'stroke', 'font-size', 'text-anchor'},
}


def _fail(reason):
    raise ValueError('GRAPH_PNG_' + reason)


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _font_material():
    font, raw = FONT.read_bytes(), METRICS.read_bytes()
    if _sha(font) != FONT_SHA or _sha(raw) != METRICS_SHA:
        _fail('FONT_IDENTITY')
    metrics = json.loads(raw)
    if metrics.get('font_sha256') != FONT_SHA:
        _fail('FONT_IDENTITY')
    if __version__ != '12.3.0' or not features.check('freetype2'):
        _fail('RASTER_DEPENDENCY_IDENTITY')
    return font, metrics


def renderer_identity():
    """Stable code/native/font identity; no clock, host path, PID or randomness."""
    _font_material()
    modules = (Image, ImageDraw, ImageFont, PngImagePlugin, _imaging, _imagingft)
    return {
        'schema': 'yamrail.graph-fixed-png-renderer/1',
        'renderer': 'OS_FIXED_SVG_PRIMITIVES_PILLOW_V1',
        'source_sha256': _sha(Path(__file__).read_bytes()),
        'requirements_sha256': _sha((ROOT / 'requirements.txt').read_bytes()),
        'python': platform.python_version(), 'system': platform.system(), 'machine': platform.machine(),
        'python_executable_sha256': _sha(Path(sys.executable).read_bytes()),
        'pillow': __version__, 'freetype': features.version('freetype2'),
        'zlib': features.version('zlib'),
        'package_module_sha256': {m.__name__: _sha(Path(m.__file__).read_bytes()) for m in modules},
        'font_sha256': FONT_SHA, 'metrics_sha256': METRICS_SHA,
        'font_layout': 'BASIC_PER_GLYPH_FROZEN_ADVANCES',
        'master_canvas': {'width': WIDTH, 'height': HEIGHT},
        'output_dimensions': {'width': WIDTH * SCALE, 'height': HEIGHT * SCALE},
        'mode': 'RGB', 'scale': SCALE,
        'encoding': {'format': 'PNG', 'compress_level': 9, 'optimize': False, 'metadata': 'NONE'},
        'supported_svg_elements': sorted(ATTRS),
        'unsupported_text_shaping': 'COMBINING_MARKS_AND_CONTROL_CHARACTERS_REJECTED',
        'geometry_policy': 'FIXED_COORDINATES_PIXEL_RASTER_2X_BUTT_CAP_MITER_JOIN_LIMIT4',
        'max_svg_bytes': MAX_SVG_BYTES, 'max_elements': MAX_ELEMENTS,
        'max_text_codepoints': MAX_TEXT, 'max_font_sizes': 32,
        'concurrent_renders': 1, 'render_slot_wait_seconds': 5,
        'process_controller': {'protocol': 'PRIVATE_INPUT_ATOMIC_OUTPUT_V1',
            'worker': 'field_backend.graph_png --render-worker',
            'wall_deadline_seconds': RENDER_TIMEOUT_SECONDS, 'reap_timeout_seconds': REAP_TIMEOUT_SECONDS,
            'max_png_bytes': MAX_PNG_BYTES, 'shell': False,
            'environment': 'FIXED_PYTHON_FLAGS_RUNTIME_PATH_AND_WINDOWS_SYSTEM_DIRECTORIES_ONLY',
            'publication': 'PRIVATE_PARTIAL_FSYNC_ATOMIC_RENAME_AFTER_VALIDATION',
            'failure_cleanup': 'KILL_WAIT_REAP_CLEANUP_RELEASE_OR_EXPLICIT_LOCAL_FAILURE'},
    }


def _number(value, minimum=0, maximum=WIDTH):
    if not isinstance(value, str) or not NUMBER.fullmatch(value):
        _fail('NUMBER')
    result = float(value)
    if not math.isfinite(result) or not minimum <= result <= maximum:
        _fail('GEOMETRY_BOUND')
    return result


def _paint(value):
    if value == 'none':
        return None
    if not isinstance(value, str) or not COLOR.fullmatch(value):
        _fail('COLOR')
    value = value[1:]
    if len(value) == 3:
        value = ''.join(c * 2 for c in value)
    return tuple(int(value[i:i+2], 16) for i in (0, 2, 4))


def _attributes(node, tag):
    if tag not in ATTRS:
        _fail('UNSUPPORTED_ELEMENT')
    for key, value in node.attrib.items():
        if key not in ATTRS[tag] | SHARED and not re.fullmatch(r'data-[a-z0-9_-]+', key):
            _fail('UNSUPPORTED_ATTRIBUTE')
        if key == 'font-family' and value != 'YamrailBoard':
            _fail('FONT_SUBSTITUTION')
        if key in {'font-kerning', 'font-variant-ligatures'} and value != 'none':
            _fail('TEXT_SHAPING')
        if key == 'transform':
            matched = ROTATE.fullmatch(value)
            if not matched:
                _fail('UNSUPPORTED_TRANSFORM')
            _number(matched[2], maximum=WIDTH)
            _number(matched[3], maximum=HEIGHT)
        if key == 'vector-effect' and value != 'non-scaling-stroke':
            _fail('UNSUPPORTED_ATTRIBUTE')
    if tag not in {'text', 'metadata'} and node.text and node.text.strip():
        _fail('UNSUPPORTED_TEXT_NODE')
    if tag in {'text', 'metadata'} and len(node):
        _fail('UNSUPPORTED_ELEMENT')


def _commands(raw, metrics):
    if not isinstance(raw, bytes) or not 1 <= len(raw) <= MAX_SVG_BYTES:
        _fail('INPUT_BOUND')
    try:
        text = raw.decode('utf-8')
        prolog = text.removeprefix('\ufeff')
        declaration = XML_DECL.match(prolog)
        remainder = prolog[declaration.end():] if declaration else prolog
        if '<!DOCTYPE' in text.upper() or '<!ENTITY' in text.upper() or '<?' in remainder:
            _fail('ACTIVE_XML')
        root = ET.fromstring(text)
    except (UnicodeError, ET.ParseError):
        _fail('XML')
    if root.tag != '{' + NS + '}svg' or root.get('viewBox') != '0 0 1414 1000':
        _fail('FIXED_CANVAS')
    if (root.get('preserveAspectRatio') != 'xMidYMid meet' or root.get('font-family') != 'YamrailBoard'
            or root.get('font-kerning') != 'none' or root.get('font-variant-ligatures') != 'none'
            or _number(root.get('width'), maximum=WIDTH) != WIDTH
            or _number(root.get('height'), maximum=HEIGHT) != HEIGHT):
        _fail('FIXED_CANVAS')
    commands, count, text_count, font_sizes = [], 0, 0, set()

    def visit(node, depth=0):
        nonlocal count, text_count
        count += 1
        if count > MAX_ELEMENTS or depth > 8:
            _fail('ELEMENT_BOUND')
        if not isinstance(node.tag, str) or not node.tag.startswith('{' + NS + '}'):
            _fail('NAMESPACE')
        tag = node.tag.removeprefix('{' + NS + '}')
        if tag == 'svg' and node is not root:
            _fail('UNSUPPORTED_ELEMENT')
        _attributes(node, tag)
        if tag in {'rect', 'line', 'polygon', 'text'}:
            item = {'tag': tag}
            for paint in ('fill', 'stroke'):
                item[paint] = _paint(node.get(paint, '#000000' if paint == 'fill' else 'none'))
                if paint + '-opacity' in node.attrib:
                    item[paint + '_opacity'] = _number(node.get(paint + '-opacity'), maximum=1)
                else:
                    item[paint + '_opacity'] = 1
            item['stroke_width'] = _number(node.get('stroke-width', '1'), maximum=8)
            if tag == 'rect':
                x, y = _number(node.get('x', '0')), _number(node.get('y', '0'), maximum=HEIGHT)
                w = WIDTH if node.get('width') == '100%' else _number(node.get('width'))
                h = HEIGHT if node.get('height') == '100%' else _number(node.get('height'), maximum=HEIGHT)
                if not w or not h or x + w > WIDTH or y + h > HEIGHT:
                    _fail('GEOMETRY_BOUND')
                item['points'] = [(x, y), (x+w, y+h)]
            elif tag == 'line':
                item['points'] = [(_number(node.get('x1')), _number(node.get('y1'), maximum=HEIGHT)),
                                  (_number(node.get('x2')), _number(node.get('y2'), maximum=HEIGHT))]
                if item['fill'] is not None:
                    _fail('UNSUPPORTED_LINE_FILL')
                dash = node.get('stroke-dasharray')
                if dash is not None:
                    values = re.split(r'[ ,]+', dash.strip())
                    if len(values) != 2:
                        _fail('UNSUPPORTED_DASH')
                    item['dash'] = [_number(v, minimum=0.1, maximum=100) for v in values]
            elif tag == 'polygon':
                pairs = node.get('points', '').split()
                if not 3 <= len(pairs) <= 128:
                    _fail('POLYGON_BOUND')
                item['points'] = []
                for pair in pairs:
                    values = pair.split(',')
                    if len(values) != 2:
                        _fail('POLYGON_BOUND')
                    item['points'].append((_number(values[0]), _number(values[1], maximum=HEIGHT)))
            else:
                value = node.text or ''
                text_count += len(value)
                if len(value) > 4000 or text_count > MAX_TEXT:
                    _fail('TEXT_BOUND')
                if (node.get('text-anchor', 'start') != 'start' or item['stroke'] is not None):
                    _fail('UNSUPPORTED_TEXT_PAINT')
                advances = metrics['advances']
                if any(str(ord(c)) not in advances or unicodedata.category(c)[0] in {'C', 'M'} for c in value):
                    _fail('UNSUPPORTED_GLYPH_OR_SHAPING')
                size = _number(node.get('font-size'), minimum=1, maximum=64)
                font_sizes.add(size)
                if len(font_sizes) > 32:
                    _fail('FONT_RESOURCE_BOUND')
                x, y = _number(node.get('x')), _number(node.get('y'), maximum=HEIGHT)
                width = sum(advances[str(ord(c))] for c in value) * size / metrics['units_per_em']
                if y-size < 0 or y+size*0.3 > HEIGHT or x+width > WIDTH+0.001:
                    _fail('TEXT_GEOMETRY_BOUND')
                item.update(text=value, size=size, x=x, y=y)
            commands.append(item)
        for child in node:
            visit(child, depth+1)
            if child.tail and child.tail.strip():
                _fail('UNSUPPORTED_TEXT_NODE')
    visit(root)
    return commands


def _draw_layer(image, color, opacity, paint):
    if color is None or opacity == 0:
        return
    if opacity == 1:
        paint(ImageDraw.Draw(image), color)
    else:
        layer = Image.new('RGBA', image.size, (0, 0, 0, 0))
        paint(ImageDraw.Draw(layer), color + (round(opacity * 255),))
        image.paste(layer, (0, 0), layer)


def _segment(draw, a, b, color, width):
    length = math.hypot(b[0]-a[0], b[1]-a[1])
    if not length or not width:
        return
    x, y = -(b[1]-a[1])*width/(2*length), (b[0]-a[0])*width/(2*length)
    draw.polygon([(a[0]+x,a[1]+y),(b[0]+x,b[1]+y),
                  (b[0]-x,b[1]-y),(a[0]-x,a[1]-y)], fill=color)


def _line(draw, points, color, width, dash=None):
    a, b = points
    if not dash:
        _segment(draw, a, b, color, width)
        return
    length = math.hypot(b[0]-a[0], b[1]-a[1])
    if length == 0:
        return
    offset = 0.0
    while offset < length:
        end = min(offset+dash[0]*SCALE, length)
        _segment(draw, (a[0]+(b[0]-a[0])*offset/length, a[1]+(b[1]-a[1])*offset/length),
                 (a[0]+(b[0]-a[0])*end/length, a[1]+(b[1]-a[1])*end/length), color, width)
        offset += sum(dash)*SCALE


def _outline(draw, points, color, width):
    """SVG default closed stroke: butt segments and miter joins, limit four."""
    if not width:
        return
    for index, b in enumerate(points):
        a, c = points[index-1], points[(index+1) % len(points)]
        _segment(draw, a, b, color, width)
        u, v = (b[0]-a[0], b[1]-a[1]), (c[0]-b[0], c[1]-b[1])
        la, lb = math.hypot(*u), math.hypot(*v)
        if not la or not lb:
            continue
        u, v = (u[0]/la,u[1]/la), (v[0]/lb,v[1]/lb)
        cross = u[0]*v[1]-u[1]*v[0]
        if abs(cross) < 1e-12:
            continue
        side = -1 if cross > 0 else 1
        half = width/2
        n, m = (-u[1]*half*side,u[0]*half*side), (-v[1]*half*side,v[0]*half*side)
        start, end = (b[0]+n[0],b[1]+n[1]), (b[0]+m[0],b[1]+m[1])
        delta = (end[0]-start[0],end[1]-start[1])
        distance = (delta[0]*v[1]-delta[1]*v[0])/cross
        tip = (start[0]+distance*u[0], start[1]+distance*u[1])
        if math.hypot(tip[0]-b[0],tip[1]-b[1]) <= half*4:
            draw.polygon([b,start,tip,end], fill=color)
        else:
            draw.polygon([b,start,end], fill=color)


def _render_png_locked(svg_bytes):
    font_bytes, metrics = _font_material()
    commands = _commands(svg_bytes, metrics)  # Fully validate before allocating pixels.
    image = Image.new('RGB', (WIDTH*SCALE, HEIGHT*SCALE), '#ffffff')
    fonts = {}
    for item in commands:
        tag = item['tag']
        points = [(x*SCALE, y*SCALE) for x, y in item.get('points', [])]
        stroke_width = item['stroke_width']*SCALE
        if tag == 'text':
            size = item['size']
            if size not in fonts:
                fonts[size] = ImageFont.truetype(io.BytesIO(font_bytes), size*SCALE, layout_engine=ImageFont.Layout.BASIC)
            font = fonts[size]
            def glyphs(draw, color):
                x = item['x']
                for char in item['text']:
                    draw.text((x*SCALE, item['y']*SCALE), char, fill=color, font=font, anchor='ls')
                    x += metrics['advances'][str(ord(char))] * size / metrics['units_per_em']
            _draw_layer(image, item['fill'], item['fill_opacity'], glyphs)
        elif tag == 'line':
            _draw_layer(image, item['stroke'], item['stroke_opacity'],
                        lambda d, c: _line(d, points, c, stroke_width, item.get('dash')))
        else:
            def fill(draw, color):
                if tag == 'rect': draw.rectangle(points, fill=color)
                else: draw.polygon(points, fill=color)
            def stroke(draw, color):
                outline = points if tag == 'polygon' else [points[0], (points[1][0], points[0][1]), points[1], (points[0][0], points[1][1])]
                _outline(draw, outline, color, stroke_width)
            _draw_layer(image, item['fill'], item['fill_opacity'], fill)
            if item['stroke_width']:
                _draw_layer(image, item['stroke'], item['stroke_opacity'], stroke)
    output = io.BytesIO()
    image.save(output, format='PNG', optimize=False, compress_level=9)
    return output.getvalue()


def _validate_png(raw):
    """Bound and validate the complete fixed RGB object before it can return."""
    if (not isinstance(raw, bytes) or not 33 <= len(raw) <= MAX_PNG_BYTES
            or raw[:8] != b'\x89PNG\r\n\x1a\n' or raw[8:16] != b'\x00\x00\x00\rIHDR'
            or struct.unpack('>II', raw[16:24]) != (WIDTH*SCALE, HEIGHT*SCALE)
            or raw[24:29] != b'\x08\x02\x00\x00\x00'):
        _fail('WORKER_OUTPUT_INVALID')
    offset, tags, compressed = 8, [], []
    while offset < len(raw):
        if offset+12 > len(raw):
            _fail('WORKER_OUTPUT_INVALID')
        size = int.from_bytes(raw[offset:offset+4], 'big')
        tag, end = raw[offset+4:offset+8], offset+12+size
        if end > len(raw) or tag not in {b'IHDR', b'IDAT', b'IEND'}:
            _fail('WORKER_OUTPUT_INVALID')
        payload = raw[offset+8:offset+8+size]
        if zlib.crc32(tag+payload) & 0xffffffff != int.from_bytes(raw[end-4:end], 'big'):
            _fail('WORKER_OUTPUT_INVALID')
        tags.append(tag)
        if tag == b'IDAT': compressed.append(payload)
        if tag == b'IEND' and size:
            _fail('WORKER_OUTPUT_INVALID')
        offset = end
    if tags != [b'IHDR'] + [b'IDAT']*len(compressed) + [b'IEND'] or not compressed:
        _fail('WORKER_OUTPUT_INVALID')
    limit = HEIGHT*SCALE*(1+WIDTH*SCALE*3)
    decoder = zlib.decompressobj()
    try:
        pixels = decoder.decompress(b''.join(compressed), limit+1)
    except zlib.error:
        _fail('WORKER_OUTPUT_INVALID')
    if (len(pixels) != limit or not decoder.eof or decoder.unused_data or decoder.unconsumed_tail
            or any(pixels[i] not in range(5) for i in range(0, limit, 1+WIDTH*SCALE*3))):
        _fail('WORKER_OUTPUT_INVALID')


def _atomic_worker_file(path, raw):
    partial = path.with_name(path.name + '.partial')
    with partial.open('xb') as stream:
        for start in range(0, len(raw), 256*1024):
            stream.write(raw[start:start+256*1024])
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(partial, path)


def _worker_main(input_path, output_path, error_path):
    """The production child entry; a controlled harness can observe this call."""
    source, output, error = map(Path, (input_path, output_path, error_path))
    try:
        if (not all(path.is_absolute() for path in (source, output, error))
                or source.parent != output.parent or source.parent != error.parent
                or not source.parent.name.startswith('yr-graph-png-')
                or (source.name, output.name, error.name) != ('input.svg', 'output.png', 'error.json')
                or source.is_symlink() or source.parent.is_symlink()
                or output.exists() or error.exists()):
            _fail('WORKER_PATH_INVALID')
        with source.open('rb') as stream:
            raw = stream.read(MAX_SVG_BYTES+1)
        if not 1 <= len(raw) <= MAX_SVG_BYTES:
            _fail('INPUT_BOUND')
        result = _render_png_locked(raw)
        _validate_png(result)
        _atomic_worker_file(output, result)
        return 0
    except BaseException as failure:
        code = str(failure) if isinstance(failure, ValueError) else ''
        if re.fullmatch(r'GRAPH_PNG_[A-Z0-9_]{1,80}', code) is None:
            code = 'GRAPH_PNG_WORKER_FAILED'
        # The parent validates this tiny error document. It contains no source
        # text, local exception details, credential, clock, PID, or file path.
        try:
            if (error.parent == source.parent and error.name == 'error.json'
                    and error.parent.name.startswith('yr-graph-png-') and not error.exists()):
                _atomic_worker_file(error, json.dumps({'code': code}, separators=(',', ':')).encode())
        except BaseException:
            pass  # Nonzero exit remains a failure; the controller owns cleanup.
        return 2


def _spawn_worker(input_path, output_path, error_path):
    environment = {'PYTHONDONTWRITEBYTECODE': '1', 'PYTHONIOENCODING': 'utf-8',
                   'PYTHONUNBUFFERED': '1', 'PYTHONPATH': str(ROOT)}
    for name in ('SystemRoot', 'WINDIR'):
        if name in os.environ: environment[name] = os.environ[name]
    # Preserve a virtual environment executable path; resolving its symlink
    # would accidentally select the base interpreter and different packages.
    return subprocess.Popen([str(Path(sys.executable).absolute()), '-B', '-m',
        'field_backend.graph_png', '--render-worker', str(input_path), str(output_path), str(error_path)],
        cwd=ROOT, env=environment, shell=False, stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))


def _worker_failure(error_path):
    try:
        with error_path.open('rb') as stream:
            raw = stream.read(513)
        value = json.loads(raw)
        if (len(raw) <= 512 and isinstance(value, dict) and set(value) == {'code'}
                and isinstance(value['code'], str)
                and re.fullmatch(r'GRAPH_PNG_[A-Z0-9_]{1,80}', value['code'])):
            raise ValueError(value['code'])
    except (OSError, UnicodeError, json.JSONDecodeError, TypeError):
        pass
    _fail('WORKER_FAILED')


def render_png(svg_bytes):
    """Return a validated complete PNG, with a killable bounded child renderer."""
    if not isinstance(svg_bytes, bytes) or not 1 <= len(svg_bytes) <= MAX_SVG_BYTES:
        _fail('INPUT_BOUND')
    if not _RENDER_SLOT.acquire(timeout=5):
        _fail('RENDER_CAPACITY')
    workspace, process = None, None
    try:
        workspace = Path(tempfile.mkdtemp(prefix='yr-graph-png-')).resolve()
        source, output, error = [workspace/name for name in ('input.svg', 'output.png', 'error.json')]
        descriptor = os.open(source, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, 'wb') as stream:
            stream.write(svg_bytes); stream.flush(); os.fsync(stream.fileno())
        process = _spawn_worker(source, output, error)
        try:
            code = process.wait(timeout=RENDER_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            _fail('RENDER_TIMEOUT')
        if code:
            _worker_failure(error)
        if output.is_symlink():
            _fail('WORKER_OUTPUT_INVALID')
        with output.open('rb') as stream:
            raw = stream.read(MAX_PNG_BYTES+1)
        _validate_png(raw)
        return raw
    except (KeyboardInterrupt, SystemExit, GeneratorExit):
        _fail('RENDER_INTERRUPTED')
    except (OSError, subprocess.SubprocessError):
        _fail('WORKER_PROCESS_FAILED')
    finally:
        cleanup_failure = None
        if process is not None:
            try:
                if process.poll() is None: process.kill()
                process.wait(timeout=REAP_TIMEOUT_SECONDS)
            except BaseException:
                cleanup_failure = 'WORKER_REAP_FAILED'
        if workspace is not None:
            try:
                if (workspace.parent != Path(tempfile.gettempdir()).resolve()
                        or not workspace.name.startswith('yr-graph-png-') or workspace.is_symlink()):
                    _fail('WORKSPACE_SCOPE')
                shutil.rmtree(workspace)
            except BaseException:
                cleanup_failure = cleanup_failure or 'WORKSPACE_CLEANUP_FAILED'
        _RENDER_SLOT.release()
        if cleanup_failure:
            _fail(cleanup_failure)


if __name__ == '__main__':
    if len(sys.argv) == 5 and sys.argv[1] == '--render-worker':
        raise SystemExit(_worker_main(*sys.argv[2:]))
    raise SystemExit(2)
