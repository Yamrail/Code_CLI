# CAD_DISPLAY_STATION_V1

- status: PRIVATE_PROTOTYPE / NON_CANONICAL
- purpose: DXFを生成して終わりにせず、人間が同じ工区で出来形を目視確認できるローカル表示設備を提供する。
- authority_effect: NONE
- network_access: NONE
- source_mutation: PROHIBITED

## Principle

```text
DXF
-> SOURCE HASH / REVISION CHECK
-> ENTITY / LAYER INSPECTION
-> DETERMINISTIC SVG PREVIEW
-> LOCAL HTML VIEWER
-> VISUAL INSPECTION BY HUMAN
-> OPTIONAL PDF EXPORT GUARD

DXF_CREATED != VISUALLY_INSPECTED
PREVIEW != CANONICAL ISSUE
UNSUPPORTED_ENTITY != SILENT_DROP
```

## Supported DXF profile

ASCII DXF:
- LINE
- LWPOLYLINE
- TEXT
- MTEXT
- CIRCLE
- ARC
- POINT
- SOLID
- 3DFACE

未対応ENTITYは黙って欠落させず `HOLD_UNSUPPORTED_ENTITY_TYPES` で停止する。

## Output

- `preview.svg`
- `viewer.html`
- `preview_receipt.json`

viewer.html:
- レイヤ表示/非表示
- Fit
- マウスホイール拡大縮小
- ドラッグ移動
- DXF source hash / Revision / Drawing ID 常時表示
- 外部通信なし

## Run

```text
python -B cad_display_station.py fixtures/example_request.json
python -B cad_display_station.py fixtures/example_surface_guard.json
python -B test_cad_display_station.py
```

## Invariants

- SOURCE_DXF_IMMUTABLE
- SOURCE_REVISION_REQUIRED
- SOURCE_SHA256_RECORDED
- UNSUPPORTED_ENTITY_MUST_HOLD
- NO_EXTERNAL_NETWORK
- NO_BROWSER_PRINT_AS_EXPORT
- NO_OUTPUT_OVERWRITE
- PREVIEW_AUTHORITY_EFFECT_NONE
- REVISION_DIFFERENCE_IS_DIFFERENT_ARTIFACT
- HUMAN_VISUAL_INSPECTION_REQUIRED_FOR_DRAWING_ACCEPTANCE

## Adjacent tools

```text
DXF generator
    |
    v
CAD_DISPLAY_STATION_V1
    |
    +--> preview.svg
    +--> viewer.html
    |
    v
Human visual inspection
    |
    v
Plotter / PDF generator
    |
    v
PDF_EXPORT_DOWNLOAD_GUARD_V1
```

本工具は正本発行権限、公開権限、施工承認権限を持たない。
