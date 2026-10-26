"""Purpose-scoped explanatory graph generation; legacy engineering pins remain.

MD is the content authority. A partial explanatory graph is a derived quotation
projection; appearance never determines MD acceptance. CAD/engineering contracts
and the immutable R001 schema are not relaxed by this request adapter.
"""
import copy
import hashlib
import json
import math
from .silver_board import SCHEMA_SHA256 as BASE_SCHEMA_SHA256, model_output_schema

NAME = 'yamrail_osint_explanatory_graph_r035'
REQUEST_FORMAT_NAME = NAME
LINE_CODEPOINT_LIMITS = {'header': 30, 'node': 12, 'distortion': 16,
    'timeline': 32, 'station': 30, 'footer': 70, 'expressed_date': 16}
_VISIBLE_LINE = r'^[^\u0000-\u001f\u007f-\u009f\u200b-\u200f\u2028-\u202e\u2060-\u206f\ufeff]+$'


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(',', ':'), allow_nan=False).encode('utf-8')


def _schema():
    value = copy.deepcopy(model_output_schema())
    board, defs = value['properties']['board']['properties'], value['$defs']
    def line(spec, maximum):
        spec['maxLength'] = maximum
        spec['minLength'] = 1
        spec['pattern'] = _VISIBLE_LINE
    line(board['coverage_lines']['items'], 30)
    line(board['scope_lines']['items'], 30)
    line(defs['node']['properties']['lines']['items'], 12)
    line(defs['distortion']['properties']['lines']['items'], 16)
    line(defs['timeline']['properties']['lines']['items'], 32)
    line(defs['timeline']['properties']['expressed_date']['anyOf'][0], 16)
    for field in ('missing_lines','target_lines','discriminator_lines','value_lines'):
        line(defs['station']['properties'][field]['items'], 30)
    for spec in board['footer']['properties'].values():
        line(spec['items'], 70)
    # Three longest W/C aliases fit the existing 197px node reference row.
    # The model selects references before output; no returned references are cut.
    for name in ('node','edge','distortion','timeline','station'):
        field = 'support_refs' if name == 'edge' else 'source_refs'
        defs[name]['properties'][field]['maxItems'] = 3
    return value


_LEGACY_REQUEST_SCHEMA = _schema()
LEGACY_REQUEST_SCHEMA_SHA256 = hashlib.sha256(canonical(_LEGACY_REQUEST_SCHEMA)).hexdigest()
_LEGACY_REQUEST_FORMAT = {'type': 'json_schema', 'name': 'yamrail_osint_content_board_r033',
    'strict': True, 'schema': _LEGACY_REQUEST_SCHEMA}
LEGACY_REQUEST_FORMAT_SHA256 = hashlib.sha256(canonical(_LEGACY_REQUEST_FORMAT)).hexdigest()
from .explanatory_graph import request_output_schema as _explanatory_schema
_REQUEST_SCHEMA = _explanatory_schema()
REQUEST_SCHEMA_SHA256 = hashlib.sha256(canonical(_REQUEST_SCHEMA)).hexdigest()
SCHEMA_SHA256 = REQUEST_SCHEMA_SHA256
_REQUEST_FORMAT = {'type': 'json_schema', 'name': NAME, 'strict': True, 'schema': _REQUEST_SCHEMA}
REQUEST_FORMAT_SHA256 = hashlib.sha256(canonical(_REQUEST_FORMAT)).hexdigest()


def request_output_schema():
    return copy.deepcopy(_REQUEST_SCHEMA)


def request_output_format():
    return copy.deepcopy(_REQUEST_FORMAT)


def legacy_request_output_format():
    return copy.deepcopy(_LEGACY_REQUEST_FORMAT)


def transport_metadata_numbers(value):
    """Canonicalize generated display metadata for Python/JS JSON hashing.

    Apply only to a newly generated render's metadata, never to model originals,
    source copies, input packets, receipt objects or already hash-bound ledgers.
    Mathematical geometry and the exact SVG master bytes remain unchanged.
    """
    if isinstance(value, dict):
        return {key: transport_metadata_numbers(item) for key, item in value.items()}
    if isinstance(value, list):
        return [transport_metadata_numbers(item) for item in value]
    if type(value) is float:
        if not math.isfinite(value):
            raise ValueError('OSINT_CONTENT_GRAPH_METADATA_NONFINITE')
        if value.is_integer() and abs(value) <= 9007199254740991:
            return int(value)
    return value


def board_request_context():
    return {'schema': 'yamrail.osint-explanatory-graph-generation-contract-r035/1',
        'request_schema_sha256': REQUEST_SCHEMA_SHA256, 'request_format_sha256': REQUEST_FORMAT_SHA256,
        'purpose': 'EXPLANATORY_PONCHI_DIAGRAM', 'canonical_content': 'VERIFIED_MD_REPORT',
        'graph_role': 'DERIVED_VISUAL_PROJECTION', 'precedence': 'MD_OVER_GRAPH',
        'output_envelope': 'One JSON object: schema yamrail.osint-explanatory-graph/1, analysis_markdown, graph (nullable). Write the complete MD first. Graph is optional and partial.',
        'node_policy': 'Select useful complete physical MD lines as md_quote, byte-exact after outer whitespace only. Never shorten, paraphrase or remove a negation/condition. Use a unique id and the relevant domain. Missing domains need no nodes. All display-node certainty remains UNKNOWN.',
        'source_policy': 'Use actual source_ledger C/W aliases only. Put the alias or its exact URL on the same quoted MD line. W URLs are tool references, not stored original pages or independent corroboration. Unknown source versions stay UNKNOWN.',
        'relationship_policy': 'Transfer a dependency only if the MD explicitly contains the full line: | <exact from md_quote> | <RELATION> | <exact to md_quote> | UNKNOWN | . Allowed RELATION: CITES, PROPAGATES, SUPPORTS_HYPOTHESIS, CONTRADICTS, PROPOSED_LINK. Put this exact line into edge.md_quote. It is a report statement, not a proof of truth or causality. If no explicit relation exists, omit the edge; never infer direction from co-occurrence.',
        'date_policy': 'Keep expressed and normalized dates distinct in the MD. Unverified dates and source versions remain UNKNOWN.',
        'full_report_policy': 'Preserve the complete report in analysis_markdown independently of graph generation or rendering. No extra graph-generation API call. No fabrication to fill the canvas.',
        'layout_policy': 'BEST_EFFORT; visual quality and full graph completeness are NON_BLOCKING.',
        'scope_boundary': {'applies_to': ['EXPLANATORY_PONCHI_DIAGRAM','PRESENTATION_GRAPH','POWERPOINT_EMBEDDED_ILLUSTRATION'],
            'not_applicable_to': ['CAD_DESIGN_DRAWING','CONSTRUCTION_DRAWING','AS_BUILT_DRAWING','ENGINEERING_DELIVERABLE'],
            'classification': 'USE_AND_ENGINEERING_RESPONSIBILITY_NOT_FILE_EXTENSION',
            'cad_geometry_dimensions_layers_lines_scales_basis_provenance': 'STRICT_UNCHANGED',
            'cad_independent_drawing_inspection': 'REQUIRED', 'no_cross_scope_relaxation': True},
        'authority_effect': 'NONE', 'claim_adoption': 'UNVERIFIED_MODEL_CANDIDATE'}
