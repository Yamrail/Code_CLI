from __future__ import annotations

import hashlib
import html
import json
import math
import re
import sys
from collections import defaultdict
from pathlib import Path


SUPPORTED = {
    "LINE",
    "LWPOLYLINE",
    "TEXT",
    "MTEXT",
    "CIRCLE",
    "ARC",
    "POINT",
    "SOLID",
    "3DFACE",
}

ACI = {
    1: "#ff4040",
    2: "#ffd23f",
    3: "#44d17a",
    4: "#46c7ff",
    5: "#5c73ff",
    6: "#d26bff",
    7: "#e8eef5",
}
FALLBACK = [
    "#68b5ff", "#ff8f70", "#7adf9a", "#f4d35e",
    "#b38cff", "#70d6ff", "#ff70a6", "#a8dadc",
]


class CadHold(Exception):
    def __init__(self, code: str, detail=None):
        super().__init__(code)
        self.code = code
        self.detail = detail


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def require_text(req: dict, key: str) -> str:
    value = req.get(key)
    if not isinstance(value, str) or not value.strip():
        raise CadHold("HOLD_METADATA_INCOMPLETE", key)
    return value.strip()


def parse_pairs(text: str):
    lines = text.splitlines()
    if len(lines) % 2:
        raise CadHold("HOLD_DXF_GROUP_PAIR_ODD")
    pairs = []
    for i in range(0, len(lines), 2):
        try:
            code = int(lines[i].strip())
        except ValueError as exc:
            raise CadHold("HOLD_DXF_GROUP_CODE_INVALID", lines[i]) from exc
        pairs.append((code, lines[i + 1].rstrip()))
    return pairs


def extract_entities(pairs):
    entities = []
    in_entities = False
    i = 0
    while i < len(pairs):
        code, value = pairs[i]
        if (
            code == 0
            and value == "SECTION"
            and i + 1 < len(pairs)
            and pairs[i + 1] == (2, "ENTITIES")
        ):
            in_entities = True
            i += 2
            continue
        if in_entities and code == 0 and value == "ENDSEC":
            break
        if in_entities and code == 0:
            etype = value
            body = []
            i += 1
            while i < len(pairs) and pairs[i][0] != 0:
                body.append(pairs[i])
                i += 1
            entities.append((etype, body))
            continue
        i += 1
    if not entities:
        raise CadHold("HOLD_DXF_ENTITIES_MISSING")
    unsupported = sorted({t for t, _ in entities if t not in SUPPORTED})
    if unsupported:
        raise CadHold("HOLD_UNSUPPORTED_ENTITY_TYPES", unsupported)
    return entities


def values(body, code):
    return [v for c, v in body if c == code]


def first(body, code, default=None):
    for c, v in body:
        if c == code:
            return v
    return default


def fnum(value, default=None):
    if value is None:
        if default is None:
            raise CadHold("HOLD_DXF_NUMERIC_VALUE_MISSING")
        return default
    try:
        out = float(value)
    except ValueError as exc:
        raise CadHold("HOLD_DXF_NUMERIC_VALUE_INVALID", value) from exc
    if not math.isfinite(out):
        raise CadHold("HOLD_DXF_NUMERIC_VALUE_INVALID", value)
    return out


def inum(value, default=0):
    if value is None:
        return default
    try:
        return int(float(value))
    except ValueError as exc:
        raise CadHold("HOLD_DXF_INTEGER_VALUE_INVALID", value) from exc


def layer_of(body):
    value = first(body, 8, "0")
    return value if value else "0"


def aci_of(body):
    raw = first(body, 62)
    if raw is None:
        return None
    return abs(inum(raw))


def layer_color(layer: str):
    digest = hashlib.sha256(layer.encode("utf-8")).digest()
    return FALLBACK[digest[0] % len(FALLBACK)]


def entity_color(body, layer):
    aci = aci_of(body)
    return ACI.get(aci, layer_color(layer))


def entity_points(etype, body):
    pts = []
    if etype == "LINE":
        pts = [
            (fnum(first(body, 10)), fnum(first(body, 20))),
            (fnum(first(body, 11)), fnum(first(body, 21))),
        ]
    elif etype == "LWPOLYLINE":
        current_x = None
        for code, value in body:
            if code == 10:
                current_x = fnum(value)
            elif code == 20 and current_x is not None:
                pts.append((current_x, fnum(value)))
                current_x = None
        if not pts:
            raise CadHold("HOLD_LWPOLYLINE_VERTEX_MISSING")
    elif etype in ("TEXT", "MTEXT", "POINT"):
        pts = [(fnum(first(body, 10)), fnum(first(body, 20)))]
    elif etype in ("CIRCLE", "ARC"):
        cx = fnum(first(body, 10))
        cy = fnum(first(body, 20))
        r = abs(fnum(first(body, 40)))
        pts = [(cx - r, cy - r), (cx + r, cy + r)]
    elif etype in ("SOLID", "3DFACE"):
        for xcode, ycode in ((10, 20), (11, 21), (12, 22), (13, 23)):
            xv = first(body, xcode)
            yv = first(body, ycode)
            if xv is not None and yv is not None:
                pts.append((fnum(xv), fnum(yv)))
        if len(pts) < 3:
            raise CadHold("HOLD_FACE_VERTEX_MISSING")
    return pts


def clean_text(value: str) -> str:
    value = value.replace("\\P", " / ")
    value = re.sub(r"\\[A-Za-z][^;]*;", "", value)
    return value


def collect_model(entities):
    model = []
    layers = defaultdict(int)
    bbox_points = []
    counts = defaultdict(int)
    for etype, body in entities:
        layer = layer_of(body)
        color = entity_color(body, layer)
        pts = entity_points(etype, body)
        bbox_points.extend(pts)
        counts[etype] += 1
        layers[layer] += 1
        model.append(
            {
                "type": etype,
                "body": body,
                "layer": layer,
                "color": color,
                "points": pts,
            }
        )
    if not bbox_points:
        raise CadHold("HOLD_DXF_GEOMETRY_MISSING")
    xs = [p[0] for p in bbox_points]
    ys = [p[1] for p in bbox_points]
    bbox = (min(xs), min(ys), max(xs), max(ys))
    return model, dict(sorted(layers.items())), dict(sorted(counts.items())), bbox


def esc_attr(value):
    return html.escape(str(value), quote=True)


def render_svg(model, bbox, width=1600, height=1000, margin=55):
    minx, miny, maxx, maxy = bbox
    dx = max(maxx - minx, 1e-9)
    dy = max(maxy - miny, 1e-9)
    scale = min((width - 2 * margin) / dx, (height - 2 * margin) / dy)

    def tx(x):
        return margin + (x - minx) * scale

    def ty(y):
        return margin + (maxy - y) * scale

    by_layer = defaultdict(list)

    for item in model:
        etype = item["type"]
        body = item["body"]
        layer = item["layer"]
        color = item["color"]
        attrs = (
            f'stroke="{color}" fill="none" stroke-width="1.6" '
            f'vector-effect="non-scaling-stroke"'
        )

        if etype == "LINE":
            (x1, y1), (x2, y2) = item["points"]
            node = f'<line x1="{tx(x1):.3f}" y1="{ty(y1):.3f}" x2="{tx(x2):.3f}" y2="{ty(y2):.3f}" {attrs}/>'
        elif etype == "LWPOLYLINE":
            pts = list(item["points"])
            closed = bool(inum(first(body, 70), 0) & 1)
            if closed and len(pts) > 1:
                pts.append(pts[0])
            points = " ".join(f"{tx(x):.3f},{ty(y):.3f}" for x, y in pts)
            node = f'<polyline points="{points}" {attrs}/>'
        elif etype in ("TEXT", "MTEXT"):
            x, y = item["points"][0]
            raw = "".join(values(body, 3) + values(body, 1)) if etype == "MTEXT" else (first(body, 1, "") or "")
            label = html.escape(clean_text(raw))
            h = abs(fnum(first(body, 40), 2.5))
            font_px = max(10.0, min(64.0, h * scale))
            angle = -fnum(first(body, 50), 0.0)
            node = (
                f'<text x="{tx(x):.3f}" y="{ty(y):.3f}" fill="{color}" stroke="none" '
                f'font-family="monospace" font-size="{font_px:.2f}" '
                f'transform="rotate({angle:.3f} {tx(x):.3f} {ty(y):.3f})">{label}</text>'
            )
        elif etype == "CIRCLE":
            cx = fnum(first(body, 10))
            cy = fnum(first(body, 20))
            r = abs(fnum(first(body, 40)))
            node = f'<circle cx="{tx(cx):.3f}" cy="{ty(cy):.3f}" r="{r * scale:.3f}" {attrs}/>'
        elif etype == "ARC":
            cx = fnum(first(body, 10))
            cy = fnum(first(body, 20))
            r = abs(fnum(first(body, 40)))
            start = fnum(first(body, 50), 0.0)
            end = fnum(first(body, 51), 0.0)
            while end < start:
                end += 360.0
            steps = max(12, min(180, int((end - start) / 4.0) + 1))
            pts = []
            for i in range(steps + 1):
                a = math.radians(start + (end - start) * i / steps)
                pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
            points = " ".join(f"{tx(x):.3f},{ty(y):.3f}" for x, y in pts)
            node = f'<polyline points="{points}" {attrs}/>'
        elif etype == "POINT":
            x, y = item["points"][0]
            node = f'<circle cx="{tx(x):.3f}" cy="{ty(y):.3f}" r="3.0" fill="{color}" stroke="none"/>'
        elif etype in ("SOLID", "3DFACE"):
            points = " ".join(f"{tx(x):.3f},{ty(y):.3f}" for x, y in item["points"])
            node = f'<polygon points="{points}" fill="{color}" fill-opacity="0.16" stroke="{color}" stroke-width="1.2"/>'
        else:
            raise CadHold("HOLD_UNSUPPORTED_ENTITY_TYPES", [etype])

        by_layer[layer].append(node)

    groups = []
    for layer in sorted(by_layer):
        body = "\n".join(by_layer[layer])
        groups.append(
            f'<g data-layer="{esc_attr(layer)}" aria-label="layer {esc_attr(layer)}">\n{body}\n</g>'
        )

    return (
        f'<svg id="cadSvg" xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {width} {height}" width="{width}" height="{height}" '
        f'role="img" aria-label="DXF deterministic preview">\n'
        '<rect x="0" y="0" width="100%" height="100%" fill="#111820"/>\n'
        + "\n".join(groups)
        + "\n</svg>\n"
    )


def build_viewer(svg: str, meta: dict, layers: dict):
    checks = []
    for layer, count in layers.items():
        checks.append(
            '<label><input class="layer-toggle" type="checkbox" checked '
            f'data-layer-name="{esc_attr(layer)}"> {html.escape(layer)} '
            f'<span>({count})</span></label>'
        )
    layer_controls = "\n".join(checks)
    meta_json = html.escape(json.dumps(meta, ensure_ascii=False, sort_keys=True))
    return f"""<!doctype html>
<html lang="ja">
<meta charset="utf-8">
<title>{html.escape(meta["drawing_id"])} / {html.escape(meta["source_revision"])}</title>
<style>
html,body{{margin:0;height:100%;background:#0b1118;color:#e8eef5;font-family:system-ui,sans-serif}}
#bar{{display:flex;gap:18px;align-items:center;padding:8px 12px;background:#141f2a;border-bottom:1px solid #31475b;white-space:nowrap;overflow:auto}}
#layout{{display:grid;grid-template-columns:280px 1fr;height:calc(100% - 48px)}}
#side{{padding:12px;overflow:auto;border-right:1px solid #31475b;background:#101922}}
#side label{{display:block;margin:7px 0}}
#stage{{overflow:hidden;touch-action:none}}
#stage svg{{width:100%;height:100%;display:block;cursor:grab}}
#stage svg.dragging{{cursor:grabbing}}
small{{opacity:.78}} button{{padding:5px 10px}}
</style>
<div id="bar"
 data-source-sha256="{meta["source_sha256"]}"
 data-source-revision="{esc_attr(meta["source_revision"])}">
<strong>{html.escape(meta["drawing_id"])}</strong>
<span>Revision: {html.escape(meta["source_revision"])}</span>
<span>{html.escape(meta["state_label"])}</span>
<span>Authority: {html.escape(meta["authority_state"])}</span>
<small>DXF SHA-256: {meta["source_sha256"]}</small>
<button id="fit" type="button">Fit</button>
</div>
<div id="layout">
<aside id="side"><h3>Layers</h3>{layer_controls}</aside>
<main id="stage">{svg}</main>
</div>
<script>
"use strict";
const svg=document.getElementById("cadSvg");
const initial={{x:0,y:0,w:1600,h:1000}};
let vb={{...initial}};
let drag=null;
function apply(){{svg.setAttribute("viewBox",`${{vb.x}} ${{vb.y}} ${{vb.w}} ${{vb.h}}`);}}
document.getElementById("fit").addEventListener("click",()=>{{vb={{...initial}};apply();}});
for(const cb of document.querySelectorAll(".layer-toggle")){{
 cb.addEventListener("change",()=>{{
  const name=cb.dataset.layerName;
  for(const g of svg.querySelectorAll("[data-layer]")){{
   if(g.dataset.layer===name) g.style.display=cb.checked?"":"none";
  }}
 }});
}}
svg.addEventListener("wheel",e=>{{
 e.preventDefault();
 const r=svg.getBoundingClientRect();
 const px=vb.x+(e.clientX-r.left)/r.width*vb.w;
 const py=vb.y+(e.clientY-r.top)/r.height*vb.h;
 const k=e.deltaY<0?0.88:1.14;
 vb.x=px-(px-vb.x)*k; vb.y=py-(py-vb.y)*k; vb.w*=k; vb.h*=k; apply();
}},{{passive:false}});
svg.addEventListener("pointerdown",e=>{{
 svg.setPointerCapture(e.pointerId); drag={{x:e.clientX,y:e.clientY,vx:vb.x,vy:vb.y}};
 svg.classList.add("dragging");
}});
svg.addEventListener("pointermove",e=>{{
 if(!drag)return;
 const r=svg.getBoundingClientRect();
 vb.x=drag.vx-(e.clientX-drag.x)/r.width*vb.w;
 vb.y=drag.vy-(e.clientY-drag.y)/r.height*vb.h; apply();
}});
function stop(){{drag=null;svg.classList.remove("dragging");}}
svg.addEventListener("pointerup",stop); svg.addEventListener("pointercancel",stop);
apply();
</script>
<!-- meta:{meta_json} -->
</html>
"""


def render(req: dict):
    drawing_id = require_text(req, "drawing_id")
    source_revision = require_text(req, "source_revision")
    state_label = require_text(req, "state_label")
    authority_state = require_text(req, "authority_state")

    source = Path(require_text(req, "source_dxf"))
    if not source.exists() or not source.is_file():
        raise CadHold("HOLD_SOURCE_DXF_MISSING")
    if source.suffix.lower() != ".dxf":
        raise CadHold("HOLD_SOURCE_NOT_DXF")

    raw = source.read_bytes()
    if b"AutoCAD Binary DXF" in raw[:64]:
        raise CadHold("HOLD_BINARY_DXF_UNSUPPORTED")
    source_hash = sha256_bytes(raw)
    expected_hash = req.get("expected_source_sha256")
    if expected_hash and expected_hash != source_hash:
        raise CadHold("FAIL_SOURCE_HASH_MISMATCH")

    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise CadHold("HOLD_DXF_NOT_UTF8") from exc

    pairs = parse_pairs(text)
    entities = extract_entities(pairs)
    model, layers, counts, bbox = collect_model(entities)

    expected_layers = req.get("expected_layers", [])
    if expected_layers is None:
        expected_layers = []
    if not isinstance(expected_layers, list) or not all(isinstance(x, str) for x in expected_layers):
        raise CadHold("HOLD_EXPECTED_LAYERS_INVALID")
    missing_layers = sorted(set(expected_layers) - set(layers))
    if missing_layers:
        raise CadHold("FAIL_EXPECTED_LAYER_MISSING", missing_layers)

    out_dir = Path(require_text(req, "output_dir"))
    out_dir.mkdir(parents=True, exist_ok=True)
    preview_path = out_dir / "preview.svg"
    viewer_path = out_dir / "viewer.html"
    receipt_path = out_dir / "preview_receipt.json"
    if any(p.exists() for p in (preview_path, viewer_path, receipt_path)):
        raise CadHold("HOLD_OUTPUT_EXISTS")

    svg = render_svg(model, bbox)
    meta = {
        "drawing_id": drawing_id,
        "source_revision": source_revision,
        "state_label": state_label,
        "authority_state": authority_state,
        "source_sha256": source_hash,
    }
    viewer = build_viewer(svg, meta, layers)

    svg_bytes = svg.encode("utf-8")
    viewer_bytes = viewer.encode("utf-8")
    preview_path.write_bytes(svg_bytes)
    viewer_path.write_bytes(viewer_bytes)

    receipt = {
        "disposition": "PASS_DXF_VISUALIZATION_SURFACE_READY",
        "drawing_id": drawing_id,
        "source_revision": source_revision,
        "state_label": state_label,
        "authority_state": authority_state,
        "source_dxf": str(source),
        "source_sha256": source_hash,
        "source_bytes": len(raw),
        "entity_count": len(model),
        "entity_types": counts,
        "layers": layers,
        "bbox_model": {
            "min_x": bbox[0], "min_y": bbox[1], "max_x": bbox[2], "max_y": bbox[3]
        },
        "preview_svg_sha256": sha256_bytes(svg_bytes),
        "viewer_html_sha256": sha256_bytes(viewer_bytes),
        "network_access": "NONE",
        "source_mutated": False,
        "authority_effect": "NONE",
        "human_visual_inspection_required": True,
    }
    receipt_path.write_text(
        json.dumps(receipt, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return receipt


def surface_guard(req: dict):
    root = Path(require_text(req, "surface_root"))
    if not root.exists() or not root.is_dir():
        raise CadHold("HOLD_SURFACE_ROOT_MISSING")
    viewer_path = root / "viewer.html"
    preview_path = root / "preview.svg"
    receipt_path = root / "preview_receipt.json"
    if not all(p.exists() for p in (viewer_path, preview_path, receipt_path)):
        raise CadHold("HOLD_SURFACE_ARTIFACT_MISSING")

    viewer = viewer_path.read_text(encoding="utf-8")
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))

    prohibited = {
        "FAIL_EXTERNAL_HTTP_REFERENCE": r"https?://",
        "FAIL_REMOTE_SCRIPT_REFERENCE": r"<script[^>]+src\s*=",
        "FAIL_NETWORK_API_PRESENT": r"\b(fetch\s*\(|XMLHttpRequest\b|WebSocket\b)",
        "FAIL_BROWSER_PRINT_PATH_PRESENT": r"window\s*\.\s*print\s*\(|Ctrl\s*\+\s*P",
    }
    for code, pattern in prohibited.items():
        if re.search(pattern, viewer, re.I):
            raise CadHold(code)

    expected_hash = require_text(req, "expected_source_sha256")
    expected_revision = require_text(req, "expected_revision")
    if receipt.get("source_sha256") != expected_hash:
        raise CadHold("FAIL_SURFACE_SOURCE_HASH_MISMATCH")
    if receipt.get("source_revision") != expected_revision:
        raise CadHold("FAIL_SURFACE_REVISION_MISMATCH")
    if expected_hash not in viewer:
        raise CadHold("FAIL_SURFACE_SOURCE_HASH_NOT_VISIBLE")
    if expected_revision not in viewer:
        raise CadHold("FAIL_SURFACE_REVISION_NOT_VISIBLE")

    return {
        "disposition": "PASS_OFFLINE_DXF_DISPLAY_SURFACE",
        "source_sha256": expected_hash,
        "source_revision": expected_revision,
        "network_access": "NONE",
        "authority_effect": "NONE",
    }


def run(req: dict):
    action = req.get("action")
    if action == "render":
        return render(req)
    if action == "surface_guard":
        return surface_guard(req)
    raise CadHold("HOLD_ACTION_UNSUPPORTED")


def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: cad_display_station.py REQUEST.json")
    request = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    try:
        result = run(request)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    except CadHold as exc:
        payload = {"disposition": "HOLD", "code": exc.code}
        if exc.detail is not None:
            payload["detail"] = exc.detail
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        raise SystemExit(2)


if __name__ == "__main__":
    main()
