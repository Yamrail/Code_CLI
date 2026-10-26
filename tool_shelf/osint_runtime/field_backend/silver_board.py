"""Closed, lossless model-to-board joint. Data validation grants no authority."""
import copy
from datetime import date
import hashlib
import json
from pathlib import Path
import re
import unicodedata

DOMAINS = ('INFRA', 'LOGISTICS', 'ECONOMY', 'CULTURE_LANG', 'RUMOR')
SCHEMA_PATH = Path(__file__).with_name('silver_board_schema_R001.json')
SCHEMA_SHA256 = '1340d6beadbd8047045d1557062b119ac9a8790395d86e2583d2bce057a7eacf'
FORMAT_SHA256 = 'a52cd41defe61e55dd31441690c1f365fe65162b314f24a27b32e40a9d72da27'


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')


def sha(value):
    return hashlib.sha256(value).hexdigest()


def model_output_schema():
    value = json.loads(SCHEMA_PATH.read_bytes())
    if sha(canonical(value)) != SCHEMA_SHA256:
        raise ValueError('OSINT_BOARD_SCHEMA_UNBOUND')
    return value


def model_output_format():
    value = {'type': 'json_schema', 'name': 'yamrail_osint_silver_board_v1',
             'strict': True, 'schema': model_output_schema()}
    if sha(canonical(value)) != FORMAT_SHA256:
        raise ValueError('OSINT_BOARD_SCHEMA_UNBOUND')
    return value


def _shape(value, spec, root):
    if '$ref' in spec:
        _shape(value, root['$defs'][spec['$ref'].removeprefix('#/$defs/')], root)
        return
    if 'anyOf' in spec:
        for option in spec['anyOf']:
            try:
                _shape(value, option, root)
                return
            except ValueError:
                pass
        raise ValueError('OSINT_BOARD_OUTPUT_FORMAT_INVALID')
    kind = spec['type']
    if kind == 'null':
        valid = value is None
    elif kind == 'object':
        valid = isinstance(value, dict) and set(value) == set(spec['properties'])
        if valid:
            for key, item in value.items():
                _shape(item, spec['properties'][key], root)
    elif kind == 'array':
        valid = isinstance(value, list) and spec['minItems'] <= len(value) <= spec['maxItems']
        if valid:
            for item in value:
                _shape(item, spec['items'], root)
    elif kind == 'string':
        valid = (isinstance(value, str) and len(value) <= spec.get('maxLength', 1000000)
                 and ('enum' not in spec or value in spec['enum'])
                 and ('pattern' not in spec or re.fullmatch(spec['pattern'], value) is not None))
    else:
        valid = False
    if not valid:
        raise ValueError('OSINT_BOARD_OUTPUT_FORMAT_INVALID')


def display_units(text):
    if not isinstance(text, str) or not text.strip() or any(
            unicodedata.category(char).startswith('C') or char in '\n\r\t\u2028\u2029'
            for char in text):
        raise ValueError('OSINT_BOARD_LINE_INVALID')
    return sum(0 if unicodedata.combining(char) else
               2 if unicodedata.east_asian_width(char) in {'W', 'F', 'A'} else 1 for char in text)


def _lines(value, maximum):
    if any(display_units(line) > maximum for line in value):
        raise ValueError('OSINT_BOARD_LINE_OVERFLOW')


def source_ledger(packet, retrieval, binding):
    items = []
    for index, source in enumerate(packet['sources'], 1):
        items.append({'id': 'C' + str(index), 'kind': 'ATTACHED_SOURCE_COPY',
            'copy_sha256': source['body_sha256'], 'url': None,
            'original_text': source.get('body_text'), 'tool_call_ids': [],
            'origins': ['IMMUTABLE_INPUT_COPY'], 'independence_status': 'UNKNOWN'})
    if retrieval:
        manifest = retrieval['material']['manifest']
        by_url = {}
        for item in manifest['source_urls'] + [dict(note, origin='ACTUAL_MODEL_URL_CITATION')
                                               for note in manifest['citations']]:
            url = item['url']
            if url not in by_url:
                row = {'id': 'W' + str(len(by_url) + 1), 'kind': 'PUBLIC_WEB_TOOL_URL',
                       'copy_sha256': None, 'url': url, 'original_text': None,
                       'tool_call_ids': [], 'origins': [], 'independence_status': 'UNKNOWN'}
                by_url[url] = row
                items.append(row)
            row = by_url[url]
            if item['origin'] not in row['origins']:
                row['origins'].append(item['origin'])
            call = item.get('tool_call_id')
            if call and call not in row['tool_call_ids']:
                row['tool_call_ids'].append(call)
    ledger = {'schema': 'yamrail.osint-board-source-ledger/1',
              'binding': dict(binding), 'items': items}
    ledger['sha256'] = sha(canonical(ledger))
    return ledger


def validate_ledger(ledger):
    if (not isinstance(ledger, dict) or set(ledger) != {'schema', 'binding', 'items', 'sha256'}
            or ledger['schema'] != 'yamrail.osint-board-source-ledger/1'
            or not isinstance(ledger['items'], list)
            or ledger['sha256'] != sha(canonical({k: v for k, v in ledger.items() if k != 'sha256'}))):
        raise ValueError('OSINT_BOARD_SOURCE_LEDGER_BINDING')
    by_id = {}
    for row in ledger['items']:
        if (not isinstance(row, dict) or row.get('id') in by_id
                or not isinstance(row.get('id'), str) or not re.fullmatch(r'[CW][1-9][0-9]{0,3}', row['id'])
                or row.get('kind') not in {'ATTACHED_SOURCE_COPY', 'PUBLIC_WEB_TOOL_URL'}
                or row.get('independence_status') != 'UNKNOWN'):
            raise ValueError('OSINT_BOARD_SOURCE_LEDGER_BINDING')
        by_id[row['id']] = row
    return by_id


def validate_board(board, ledger):
    schema = model_output_schema()
    _shape(board, schema['properties']['board'], schema)
    sources = validate_ledger(ledger)
    if [lane['domain'] for lane in board['lanes']] != list(DOMAINS):
        raise ValueError('OSINT_BOARD_DOMAIN_ORDER')
    if not board['title'].strip() or len(board['title']) > 32:
        raise ValueError('OSINT_BOARD_LINE_INVALID')
    display_units(board['title'])
    _lines(board['coverage_lines'], 60)
    _lines(board['scope_lines'], 60)
    all_nodes = set()
    def references(refs):
        if len(set(refs)) != len(refs) or any(ref not in sources for ref in refs):
            raise ValueError('OSINT_BOARD_SOURCE_REFERENCE_UNBOUND')
    for lane in board['lanes']:
        local = set()
        for node in lane['nodes']:
            if node['id'] in all_nodes:
                raise ValueError('OSINT_BOARD_NODE_ID_DUPLICATE')
            all_nodes.add(node['id']); local.add(node['id'])
            _lines(node['lines'], 24); references(node['source_refs'])
            allowed = {'SOURCE_STATEMENT': {'ATTRIBUTED'}, 'PROPAGATION': {'ATTRIBUTED', 'LEAD', 'UNKNOWN'},
                       'CONDITIONAL_HYPOTHESIS': {'CONDITIONAL'}, 'LEAD': {'LEAD'}, 'UNKNOWN': {'UNKNOWN'}}
            if (node['status'] not in allowed[node['kind']]
                    or (node['status'] == 'ATTRIBUTED' and not node['source_refs'])):
                raise ValueError('OSINT_BOARD_STATUS_UNSUPPORTED')
        for edge in lane['edges']:
            references(edge['support_refs'])
            if edge['from'] not in local or edge['to'] not in local or edge['from'] == edge['to']:
                raise ValueError('OSINT_BOARD_EDGE_UNBOUND')
        warning = lane['distortion']
        if warning is not None:
            _lines(warning['lines'], 32); references(warning['source_refs'])
            for field, quote in (('original_ref', 'original_quote'), ('propagated_ref', 'propagated_quote')):
                alias = warning[field]
                if (alias not in warning['source_refs'] or alias not in sources
                        or not warning[quote] or not isinstance(sources[alias].get('original_text'), str)
                        or warning[quote] not in sources[alias]['original_text']):
                    raise ValueError('OSINT_BOARD_DISTORTION_QUOTE_UNBOUND')
    timeline_ids = set()
    for item in board['timeline']:
        _lines(item['lines'], 64); references(item['source_refs'])
        if item['id'] in timeline_ids:
            raise ValueError('OSINT_BOARD_NODE_ID_DUPLICATE')
        timeline_ids.add(item['id'])
        if item['expressed_date'] is not None:
            display_units(item['expressed_date'])
        if item['normalized_date'] is not None:
            date.fromisoformat(item['normalized_date'])
        if ((item['status'] == 'ATTRIBUTED' and not item['source_refs'])
                or (not item['source_refs'] and (item['expressed_date'] is not None or item['normalized_date'] is not None))):
            raise ValueError('OSINT_BOARD_STATUS_UNSUPPORTED')
    for item in board['next_stations']:
        references(item['source_refs'])
        for key in ('missing_lines', 'target_lines', 'discriminator_lines', 'value_lines'):
            _lines(item[key], 60)
        if item['status'] == 'ATTRIBUTED' and not item['source_refs']:
            raise ValueError('OSINT_BOARD_STATUS_UNSUPPORTED')
    for lines in board['footer'].values():
        _lines(lines, 140)
    return True


def parse_output(raw_text, ledger, binding):
    """Keep analysis exact even when a board fails its stricter geometry joint."""
    # Purpose-scoped dispatch only. The historical response path is unchanged.
    if isinstance(raw_text, str) and len(raw_text.encode('utf-8')) <= 262144:
        try:
            marker = json.loads(raw_text)
        except (ValueError, TypeError, UnicodeError):
            marker = None
        if isinstance(marker, dict) and marker.get('schema') == 'yamrail.osint-explanatory-graph/1':
            from .explanatory_graph import parse_output as parse_explanatory
            return parse_explanatory(raw_text, ledger, binding)
    def unique(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError('OSINT_BOARD_OUTPUT_FORMAT_INVALID')
            value[key] = item
        return value
    if not isinstance(raw_text, str) or len(raw_text.encode('utf-8')) > 262144:
        raise ValueError('OSINT_BOARD_OUTPUT_FORMAT_INVALID')
    try:
        parsed = json.loads(raw_text, object_pairs_hook=unique,
                            parse_constant=lambda _: (_ for _ in ()).throw(ValueError('OSINT_BOARD_OUTPUT_FORMAT_INVALID')))
    except (ValueError, TypeError, UnicodeError):
        raise ValueError('OSINT_BOARD_OUTPUT_FORMAT_INVALID') from None
    if not isinstance(parsed, dict) or not isinstance(parsed.get('analysis_markdown'), str) or not parsed['analysis_markdown'].strip():
        raise ValueError('OSINT_BOARD_OUTPUT_FORMAT_INVALID')
    analysis = parsed['analysis_markdown']
    projection = {'schema': 'yamrail.osint-silver-board-projection/1', 'binding': dict(binding),
                  'model_output_sha256': sha(raw_text.encode('utf-8')),
                  'analysis_sha256': sha(analysis.encode('utf-8')), 'schema_sha256': SCHEMA_SHA256,
                  'authority_effect': 'NONE', 'truth_state': 'UNVERIFIED_MODEL_CANDIDATE'}
    try:
        schema = model_output_schema(); _shape(parsed, schema, schema)
        if ledger['binding'] != binding:
            raise ValueError('OSINT_BOARD_SOURCE_LEDGER_BINDING')
        validate_board(parsed['board'], ledger)
        projection.update(state='MODEL_BOARD_CANDIDATE', board=copy.deepcopy(parsed['board']),
                          source_ledger=copy.deepcopy(ledger), board_sha256=sha(canonical(parsed['board'])),
                          source_ledger_sha256=ledger['sha256'])
    except (ValueError, KeyError, TypeError):
        projection.update(state='BOARD_UNAVAILABLE', board=None, reason='BOARD_CONTRACT_REJECTED',
                          source_ledger=copy.deepcopy(ledger), source_ledger_sha256=ledger.get('sha256'))
    return analysis, projection
