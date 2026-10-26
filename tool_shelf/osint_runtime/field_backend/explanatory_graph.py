"""Purpose-scoped, deterministic MD-to-explanatory-Graph transcription.

This verifies where text was transcribed, not the truth or natural-language
meaning of a model statement. Original MD and raw model bytes are never changed.
An invalid individual Graph item is omitted with an explicit UNKNOWN reason.
"""
import copy
import hashlib
import json
import re
import unicodedata

SCHEMA = 'yamrail.osint-explanatory-graph/1'
PURPOSE = 'EXPLANATORY_PONCHI_DIAGRAM'
DOMAINS = ('INFRA', 'LOGISTICS', 'ECONOMY', 'CULTURE_LANG', 'RUMOR')
RELATIONS = ('CITES', 'PROPAGATES', 'SUPPORTS_HYPOTHESIS', 'CONTRADICTS', 'PROPOSED_LINK')
BASE_SCHEMA_SHA256 = '1340d6beadbd8047045d1557062b119ac9a8790395d86e2583d2bce057a7eacf'
ID_PATTERN = r'^[a-z][a-z0-9_-]{0,31}$'
REF_PATTERN = r'^[CW][1-9][0-9]{0,3}$'
MAX_RAW_BYTES = 262144


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def text_sha(value):
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def _object(properties):
    return {'type': 'object', 'properties': properties, 'required': list(properties), 'additionalProperties': False}


def request_output_schema():
    string = lambda maximum: {'type': 'string', 'maxLength': maximum}
    refs = {'type': 'array', 'items': {'type': 'string', 'pattern': REF_PATTERN, 'maxLength': 5},
            'minItems': 0, 'maxItems': 6}
    ident = {'type': 'string', 'pattern': ID_PATTERN, 'maxLength': 32}
    node = _object({'id': ident, 'domain': {'type': 'string', 'enum': list(DOMAINS)},
                    'md_quote': string(2000), 'source_refs': refs})
    edge = _object({'from': ident, 'to': ident, 'relation': {'type': 'string', 'enum': list(RELATIONS)},
                    'md_quote': string(2000), 'support_refs': refs})
    graph = _object({'purpose': {'type': 'string', 'enum': [PURPOSE]},
                     'nodes': {'type': 'array', 'items': node, 'minItems': 0, 'maxItems': 15},
                     'edges': {'type': 'array', 'items': edge, 'minItems': 0, 'maxItems': 20}})
    return _object({'schema': {'type': 'string', 'enum': [SCHEMA]},
                    'analysis_markdown': string(98304), 'graph': {'anyOf': [{'type': 'null'}, graph]}})


SCHEMA_SHA256 = digest(request_output_schema())
REQUEST_FORMAT_NAME = 'yamrail_osint_explanatory_graph_r035'


def model_output_format():
    return {'type': 'json_schema', 'name': REQUEST_FORMAT_NAME, 'strict': True, 'schema': request_output_schema()}


FORMAT_SHA256 = digest(model_output_format())


def is_explanatory(projection):
    return isinstance(projection, dict) and projection.get('purpose') == PURPOSE


def _plain_line(value):
    return (isinstance(value, str) and 0 < len(value) <= 2000 and value.strip()
            and not any(unicodedata.category(c).startswith('C') or c in '\u2028\u2029' for c in value))


def _has_reference(line, alias, source):
    # Token boundaries prevent W1 from matching W10. No URL normalization or
    # prefix match is allowed; a Markdown closing delimiter may follow a URL.
    if re.search(r'(?<![A-Za-z0-9_])' + re.escape(alias) + r'(?![A-Za-z0-9_])', line):
        return True
    url = source.get('url')
    return (isinstance(url, str) and bool(url) and re.search(
        r'(?<![A-Za-z0-9_:/#?&=])' + re.escape(url) + r'(?=$|[\s<>\]\)])', line) is not None)


def _references(refs, line, sources):
    if (not isinstance(refs, list) or len(refs) > 6 or any(not isinstance(x, str) for x in refs)
            or len(set(refs)) != len(refs) or any(x not in sources for x in refs)):
        raise ValueError('SOURCE_REFERENCE_UNBOUND')
    if any(not _has_reference(line, alias, sources[alias]) for alias in refs):
        raise ValueError('SOURCE_REFERENCE_NOT_ON_MD_LINE')
    return refs


def _source_binding(alias, row):
    # URL receipt observation is not an original-page revision or corroboration.
    copied = row.get('kind') == 'ATTACHED_SOURCE_COPY'
    revision = row.get('source_revision') if copied else None
    if type(revision) not in (str, int) or revision == '':
        revision = None
    return {'source_ref': alias, 'source_revision': revision,
            'source_revision_state': 'DECLARED' if revision is not None else 'UNKNOWN',
            'copy_sha256': row.get('copy_sha256') if copied else None,
            'url': row.get('url'), 'provenance_state': 'UNKNOWN'}


def _validated_sources(ledger):
    from .silver_board import validate_ledger
    sources = validate_ledger(ledger)
    for alias, row in sources.items():
        if row['kind'] == 'ATTACHED_SOURCE_COPY':
            value = row.get('copy_sha256'); original = row.get('original_text')
            if (not alias.startswith('C') or not isinstance(value, str)
                    or re.fullmatch('[a-f0-9]{64}', value) is None
                    or original is not None and (not isinstance(original, str) or text_sha(original) != value)):
                raise ValueError('OSINT_MD_GRAPH_SOURCE_COPY_BINDING')
        elif (not alias.startswith('W') or not isinstance(row.get('url'), str)
              or not row['url'].startswith(('https://', 'http://'))
              or any(c.isspace() for c in row['url']) or row.get('copy_sha256') is not None
              or row.get('original_text') is not None):
            raise ValueError('OSINT_MD_GRAPH_WEB_OBSERVATION_BINDING')
    return sources


def _board(nodes, edges):
    lanes = []
    for domain in DOMAINS:
        local = [row for row in nodes if row['domain'] == domain]
        ids = {row['id'] for row in local}
        lanes.append({'domain': domain, 'nodes': [
            {'id': row['id'], 'kind': 'UNKNOWN', 'status': 'UNKNOWN', 'lines': [row['md_quote']],
             'source_refs': list(row['source_refs'])} for row in local],
            'edges': [{'from': row['from'], 'to': row['to'], 'relation': row['relation'],
                       'independence_status': 'UNKNOWN', 'support_refs': list(row['support_refs'])}
                      for row in edges if row['from'] in ids], 'distortion': None})
    return {'title': '調査内容の説明図', 'coverage_lines': ['正本MDの引用。部分表示を許容します。'],
            'scope_lines': ['OSINT説明表示専用'], 'lanes': lanes, 'timeline': [], 'next_stations': [],
            'footer': {'synthesis_lines': ['MDの同一行を転記した説明図です。事実認定ではありません。'],
                       'bottleneck_lines': ['表示していない内容・依存関係は不明のままです。'],
                       'moot_condition_lines': ['追加資料によりMDの見立てと探索点を更新してください。']}}


def _project(analysis, graph, ledger, binding, raw_sha):
    sources = _validated_sources(ledger)
    if ledger.get('binding') != binding:
        raise ValueError('OSINT_BOARD_SOURCE_LEDGER_BINDING')
    physical = {}
    for number, line in enumerate(analysis.split('\n'), 1):
        physical.setdefault(line.strip(), []).append(number)
    omissions, accepted_nodes, accepted_edges, node_receipts, edge_receipts = [], [], [], [], []
    def omit(kind, index, reason):
        omissions.append({'kind': kind, 'index': index, 'reason': reason, 'state': 'UNKNOWN'})
    if graph is None:
        omit('GRAPH', 0, 'GRAPH_NOT_PROVIDED')
        graph_nodes, graph_edges = [], []
    elif (not isinstance(graph, dict) or set(graph) != {'purpose', 'nodes', 'edges'}
          or graph.get('purpose') != PURPOSE or not isinstance(graph.get('nodes'), list)
          or not isinstance(graph.get('edges'), list) or len(graph['nodes']) > 15 or len(graph['edges']) > 20):
        omit('GRAPH', 0, 'GRAPH_STRUCTURE_OR_RESOURCE_BOUND')
        graph_nodes, graph_edges = [], []
    else:
        graph_nodes, graph_edges = graph['nodes'], graph['edges']
    seen = set()
    for index, node in enumerate(graph_nodes):
        try:
            if (not isinstance(node, dict) or set(node) != {'id', 'domain', 'md_quote', 'source_refs'}
                    or not isinstance(node['id'], str) or re.fullmatch(ID_PATTERN, node['id']) is None
                    or node['domain'] not in DOMAINS or not _plain_line(node['md_quote'])):
                raise ValueError('NODE_STRUCTURE_INVALID')
            if node['id'] in seen:
                raise ValueError('NODE_ID_DUPLICATE')
            # Reserve even an invalid first ID: a later duplicate cannot replace
            # what that ID meant in the original candidate.
            seen.add(node['id'])
            quote = node['md_quote'].strip()
            if quote not in physical:
                raise ValueError('NODE_NOT_FULL_MD_LINE')
            refs = _references(node['source_refs'], quote, sources)
            item = {**copy.deepcopy(node), 'md_quote': quote}
            accepted_nodes.append(item)
            node_receipts.append({'id': node['id'], 'domain': node['domain'], 'md_quote': quote,
                                  'md_line_numbers': physical[quote],
                                  'source_bindings': [_source_binding(ref, sources[ref]) for ref in refs]})
        except (ValueError, TypeError, KeyError) as error:
            omit('NODE', index, str(error) if isinstance(error, ValueError) else 'NODE_STRUCTURE_INVALID')
    by_id = {row['id']: row for row in accepted_nodes}
    seen_edges = set()
    for index, edge in enumerate(graph_edges):
        try:
            if (not isinstance(edge, dict) or set(edge) != {'from', 'to', 'relation', 'md_quote', 'support_refs'}
                    or not isinstance(edge['from'], str) or not isinstance(edge['to'], str)
                    or edge['from'] not in by_id or edge['to'] not in by_id or edge['from'] == edge['to']
                    or edge['relation'] not in RELATIONS or not _plain_line(edge['md_quote'])):
                raise ValueError('EDGE_STRUCTURE_OR_ENDPOINT_INVALID')
            identity = (edge['from'], edge['to'], edge['relation'])
            if identity in seen_edges:
                raise ValueError('EDGE_DUPLICATE')
            seen_edges.add(identity)
            left, right = by_id[edge['from']], by_id[edge['to']]
            expected = '| ' + left['md_quote'] + ' | ' + edge['relation'] + ' | ' + right['md_quote'] + ' | UNKNOWN |'
            quote = edge['md_quote'].strip()
            if quote != expected or quote not in physical:
                raise ValueError('EDGE_NOT_EXPLICIT_MD_RELATION_ROW')
            refs = _references(edge['support_refs'], quote, sources)
            accepted_edges.append({**copy.deepcopy(edge), 'md_quote': quote})
            edge_receipts.append({'from': edge['from'], 'to': edge['to'], 'relation': edge['relation'],
                                  'md_quote': quote, 'md_line_numbers': physical[quote],
                                  'source_bindings': [_source_binding(ref, sources[ref]) for ref in refs]})
        except (ValueError, TypeError, KeyError) as error:
            omit('EDGE', index, str(error) if isinstance(error, ValueError) else 'EDGE_STRUCTURE_OR_ENDPOINT_INVALID')
    semantics = {'schema': 'yamrail.osint-md-graph-semantics/1', 'purpose': PURPOSE,
                 'canonical_md_sha256': text_sha(analysis), 'model_output_sha256': raw_sha,
                 'source_ledger_sha256': ledger['sha256'],
                 'scope': 'EXACT_PHYSICAL_MD_LINE_TRANSCRIPTION_ONLY',
                 'truth_state': 'UNVERIFIED_MODEL_CANDIDATE', 'provenance_state': 'UNKNOWN',
                 'validation_state': ('PARTIAL_EXACT_TRANSCRIPTION' if omissions else 'EXACT_TRANSCRIPTION')
                                     if accepted_nodes else 'GRAPH_UNAVAILABLE',
                 'candidate_graph': copy.deepcopy(graph), 'nodes': node_receipts, 'edges': edge_receipts,
                 'omissions': omissions}
    projection = {'schema': 'yamrail.osint-silver-board-projection/1', 'binding': dict(binding),
                  'model_output_sha256': raw_sha, 'analysis_sha256': text_sha(analysis),
                  'schema_sha256': BASE_SCHEMA_SHA256, 'purpose': PURPOSE, 'md_semantics': semantics,
                  'authority_effect': 'NONE', 'truth_state': 'UNVERIFIED_MODEL_CANDIDATE',
                  'source_ledger': copy.deepcopy(ledger), 'source_ledger_sha256': ledger['sha256']}
    if accepted_nodes:
        board = _board(accepted_nodes, accepted_edges)
        validate_partial_board(board, ledger)
        projection.update(state='MODEL_BOARD_CANDIDATE', board=board, board_sha256=digest(board))
    else:
        projection.update(state='BOARD_UNAVAILABLE', board=None, reason='NO_VALID_MD_GRAPH_NODES')
    return projection


def parse_output(raw_text, ledger, binding):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('OSINT_BOARD_OUTPUT_FORMAT_INVALID')
            result[key] = value
        return result
    if not isinstance(raw_text, str) or len(raw_text.encode('utf-8')) > MAX_RAW_BYTES:
        raise ValueError('OSINT_BOARD_OUTPUT_FORMAT_INVALID')
    try:
        value = json.loads(raw_text, object_pairs_hook=unique,
                           parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    except (ValueError, TypeError, UnicodeError):
        raise ValueError('OSINT_BOARD_OUTPUT_FORMAT_INVALID') from None
    if (not isinstance(value, dict) or not {'schema', 'analysis_markdown'} <= set(value)
            or not set(value) <= {'schema', 'analysis_markdown', 'graph'}
            or value.get('schema') != SCHEMA or not isinstance(value.get('analysis_markdown'), str)
            or not value['analysis_markdown'].strip() or len(value['analysis_markdown']) > 98304):
        raise ValueError('OSINT_BOARD_OUTPUT_FORMAT_INVALID')
    analysis = value['analysis_markdown']
    # The request schema requires graph (nullable). Missing Graph on receipt is
    # still only a Graph-local defect, never a reason to erase intact MD.
    return analysis, _project(analysis, value.get('graph'), ledger, binding, text_sha(raw_text))


def derive_available_md(analysis, ledger, binding, raw_model_text):
    """Read-only excerpts for an authenticated R035 response with graph:null.

    Selection follows physical MD order, never relevance/domain classification.
    The original response, its unavailable projection and MD remain untouched.
    """
    received_analysis, original_projection = parse_output(raw_model_text, ledger, binding)
    raw_value = json.loads(raw_model_text)
    if (not isinstance(analysis, str) or analysis != received_analysis
            or 'graph' not in raw_value or raw_value['graph'] is not None):
        raise ValueError('OSINT_DERIVED_GRAPH_REQUIRES_EXACT_MD_AND_NULL_MODEL_GRAPH')
    sources = _validated_sources(ledger)
    selected=[]
    selection={'order':'PHYSICAL_MD_LINE_ASCENDING','maximum_nodes':15,
               'physical_line_count':len(analysis.split('\n')),'eligible_cited_line_count':0,
               'unknown_reference_line_count':0,'oversized_or_control_line_count':0,
               'over_reference_limit_line_count':0,'resource_omitted_line_count':0,
               'selected_line_numbers':[]}
    for number, physical in enumerate(analysis.split('\n'), 1):
        quote=physical.strip()
        # Detect unknown-looking references as well as known aliases. A line
        # containing W999, C0, etc. is never represented as fully bound.
        aliases=list(dict.fromkeys(re.findall(r'(?<![A-Za-z0-9_])[CW][0-9]+(?![A-Za-z0-9_])',quote)))
        if not aliases:continue
        if any(alias not in sources for alias in aliases):
            selection['unknown_reference_line_count']+=1;continue
        if len(aliases)>6:
            selection['over_reference_limit_line_count']+=1;continue
        if not _plain_line(quote):
            selection['oversized_or_control_line_count']+=1;continue
        selection['eligible_cited_line_count']+=1
        if len(selected)>=15:
            selection['resource_omitted_line_count']+=1;continue
        # These enum values are drawing slots only, explicitly not a claim
        # that a paragraph belongs to any semantic/domain category.
        selected.append({'id':'md_line_'+str(number),'domain':DOMAINS[len(selected)//3],
                         'md_quote':quote,'source_refs':aliases})
        selection['selected_line_numbers'].append(number)
    candidate={'purpose':PURPOSE,'nodes':selected,'edges':[]}
    projection=_project(analysis,candidate,ledger,binding,text_sha(raw_model_text))
    projection.update(derivation='AVAILABLE_MD_EXCERPTS',original_projection_sha256=digest(original_projection))
    semantics=projection['md_semantics']
    semantics.update(derivation='AVAILABLE_MD_EXCERPTS',
                     origin='SERVER_DETERMINISTIC_MD_EXCERPTS_NOT_MODEL_GRAPH',
                     domain_assignment='UNKNOWN_LAYOUT_SLOTS_ONLY',model_graph=None,
                     candidate_graph_role='DERIVED_LAYOUT_CANDIDATE_NOT_MODEL_GRAPH',selection=selection)
    for item in semantics['nodes']:
        item['layout_slot']=item['domain'];item['domain']='UNKNOWN'
    semantics['omissions'].append({'kind':'GRAPH','index':0,
        'reason':'MODEL_GRAPH_NOT_PROVIDED_DERIVED_MD_EXCERPTS_ONLY','state':'UNKNOWN'})
    semantics['validation_state']='PARTIAL_EXACT_TRANSCRIPTION' if selected else 'GRAPH_UNAVAILABLE'
    return projection


def derive_structured_md(analysis, ledger, binding, raw_model_text):
    """New read-only structure; old response/projection bytes are not rewritten."""
    from .silver_board import parse_output as parse_received_output
    from .md_structure import build, validate_structure
    received_analysis, original_projection=parse_received_output(raw_model_text,ledger,binding)
    if not isinstance(analysis,str) or analysis!=received_analysis or ledger.get('binding')!=binding:
        raise ValueError('STRUCTURED_MD_ORIGINAL_RESPONSE_BINDING')
    _validated_sources(ledger)
    parsed=json.loads(raw_model_text)
    board=build(analysis,ledger,binding,original_projection,_source_binding)
    validate_structure(board,ledger)
    semantics={'schema':'yamrail.osint-md-graph-semantics/1','purpose':PURPOSE,
        'derivation':'STRUCTURED_MD_GRAPH','origin':'DETERMINISTIC_EXPLICIT_MD_STRUCTURE',
        'canonical_md_sha256':text_sha(analysis),'model_output_sha256':text_sha(raw_model_text),
        'source_ledger_sha256':ledger['sha256'],'scope':'EXACT_MD_SPANS_SECTION_AND_EXPLICIT_RELATION_EXTRACTION',
        'truth_state':'UNVERIFIED_MODEL_CANDIDATE','provenance_state':'SOURCE_DEPENDENT_NOT_FACT_VERIFICATION',
        'validation_state':'STRUCTURED_EXACT_SPAN_PROJECTION','offset_unit':'UNICODE_CODE_POINTS',
        'candidate_graph_role':'DERIVED_MD_STRUCTURE_NOT_REPLACEMENT_MODEL_RESPONSE',
        'model_graph':copy.deepcopy(parsed.get('graph',parsed.get('board'))),
        'original_projection_sha256':digest(original_projection),
        'nodes':[{key:copy.deepcopy(node[key]) for key in ('id','md_span','context_span','category','section_id','source_refs',
                   'source_bindings','unbound_source_refs','topic','origin','polarity_spans','context_polarity_spans')} for node in board['nodes']],
        'edges':copy.deepcopy(board['edges']),'omissions':copy.deepcopy(board['omissions']),
        'selection':copy.deepcopy(board['selection'])}
    return {'schema':'yamrail.osint-silver-board-projection/1','binding':dict(binding),
        'model_output_sha256':text_sha(raw_model_text),'analysis_sha256':text_sha(analysis),
        'schema_sha256':BASE_SCHEMA_SHA256,'purpose':PURPOSE,'derivation':'STRUCTURED_MD_GRAPH',
        'original_projection_sha256':digest(original_projection),'md_semantics':semantics,
        'authority_effect':'NONE','truth_state':'UNVERIFIED_MODEL_CANDIDATE',
        'source_ledger':copy.deepcopy(ledger),'source_ledger_sha256':ledger['sha256'],
        'state':'MODEL_BOARD_CANDIDATE','board':board,'board_sha256':digest(board)}


def validate_projection(projection, analysis, ledger, binding, raw_model_text=None):
    """Recompute transcription; caller also binds candidate_graph to raw JSON.

    This function cannot authenticate a raw response it has not received. Engine
    and UI admission must compare parse_output(original_raw, ledger, binding).
    """
    if (not is_explanatory(projection) or not isinstance(analysis, str)
            or not isinstance(projection.get('md_semantics'), dict)
            or not isinstance(projection.get('model_output_sha256'), str)
            or re.fullmatch('[a-f0-9]{64}', projection['model_output_sha256']) is None):
        raise ValueError('OSINT_MD_GRAPH_PROJECTION_INVALID')
    if projection.get('derivation') == 'STRUCTURED_MD_GRAPH':
        if not isinstance(raw_model_text,str):
            raise ValueError('STRUCTURED_MD_ORIGINAL_RAW_REQUIRED')
        expected=derive_structured_md(analysis,ledger,binding,raw_model_text)
    elif projection.get('derivation') == 'AVAILABLE_MD_EXCERPTS':
        if not isinstance(raw_model_text,str):
            raise ValueError('OSINT_DERIVED_GRAPH_ORIGINAL_RAW_REQUIRED')
        expected=derive_available_md(analysis,ledger,binding,raw_model_text)
    else:
        expected = _project(analysis, projection['md_semantics'].get('candidate_graph'), ledger, binding,
                            projection['model_output_sha256'])
    if canonical(expected) != canonical(projection):
        raise ValueError('OSINT_MD_GRAPH_PROJECTION_MISMATCH')
    return True


def validate_partial_board(board, ledger):
    """Structural safety only; completeness and appearance are not admission gates."""
    sources = _validated_sources(ledger)
    if isinstance(board,dict) and board.get('schema')=='yamrail.osint-structured-md-graph/1':
        from .md_structure import validate_structure
        return validate_structure(board,ledger)
    if (not isinstance(board, dict) or set(board) != {'title', 'coverage_lines', 'scope_lines', 'lanes', 'timeline', 'next_stations', 'footer'}
            or not isinstance(board.get('lanes'), list) or len(board['lanes']) != 5
            or [row.get('domain') for row in board['lanes'] if isinstance(row, dict)] != list(DOMAINS)
            or board.get('timeline') != [] or board.get('next_stations') != []):
        raise ValueError('OSINT_MD_GRAPH_BOARD_INVALID')
    # Static scaffolding is presentation, not extra model claims.
    scaffold = _board([], [])
    if any(board[key] != scaffold[key] for key in ('title', 'coverage_lines', 'scope_lines', 'footer')):
        raise ValueError('OSINT_MD_GRAPH_SCAFFOLD_INVALID')
    global_ids = {node.get('id') for lane in board['lanes'] if isinstance(lane.get('nodes'), list)
                  for node in lane['nodes'] if isinstance(node, dict) and isinstance(node.get('id'), str)}
    all_ids = set(); count = 0; edge_count = 0
    for lane in board['lanes']:
        if (set(lane) != {'domain', 'nodes', 'edges', 'distortion'} or not isinstance(lane['nodes'], list)
                or not isinstance(lane['edges'], list) or lane['distortion'] is not None):
            raise ValueError('OSINT_MD_GRAPH_BOARD_INVALID')
        local = set()
        for node in lane['nodes']:
            if (not isinstance(node, dict) or set(node) != {'id', 'kind', 'status', 'lines', 'source_refs'}
                    or not isinstance(node['id'], str) or re.fullmatch(ID_PATTERN, node['id']) is None
                    or node['id'] in all_ids or node['kind'] != 'UNKNOWN' or node['status'] != 'UNKNOWN'
                    or not isinstance(node['lines'], list) or len(node['lines']) != 1 or not _plain_line(node['lines'][0])):
                raise ValueError('OSINT_MD_GRAPH_BOARD_INVALID')
            _references(node['source_refs'], node['lines'][0], sources)
            local.add(node['id']); all_ids.add(node['id']); count += 1
        for edge in lane['edges']:
            if (not isinstance(edge, dict) or set(edge) != {'from', 'to', 'relation', 'independence_status', 'support_refs'}
                    or not isinstance(edge['from'], str) or not isinstance(edge['to'], str)
                    or edge['from'] not in local or edge['to'] not in global_ids or edge['from'] == edge['to']
                    or edge['relation'] not in RELATIONS or edge['independence_status'] != 'UNKNOWN'
                    or not isinstance(edge['support_refs'], list) or len(edge['support_refs']) > 6
                    or any(not isinstance(ref, str) or ref not in sources for ref in edge['support_refs'])
                    or len(set(edge['support_refs'])) != len(edge['support_refs'])):
                raise ValueError('OSINT_MD_GRAPH_BOARD_INVALID')
            edge_count += 1
    if count > 15 or edge_count > 20:
        raise ValueError('OSINT_MD_GRAPH_RESOURCE_BOUND')
    return True
