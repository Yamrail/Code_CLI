"""Independent synthetic typed HOLD reporting module."""
def hold_report(rows):
    states = ('HOLD', 'UNKNOWN', 'CONFLICT', 'OPEN', 'CLOSED')
    counts = {state: 0 for state in states}
    active = []
    seen = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError('A hold record must be an object')
        state = row.get('state')
        if state not in states:
            raise ValueError('Unknown typed hold state')
        identifier = row.get('id')
        scope = row.get('scope')
        global_stop = row.get('global_stop')
        if not isinstance(identifier, str) or not identifier or identifier in seen:
            raise ValueError('A unique non-empty hold id is required')
        if not isinstance(scope, list) or not all(isinstance(item, str) for item in scope):
            raise ValueError('Scope must be a list of strings')
        if type(global_stop) is not bool:
            raise ValueError('global_stop must be an explicit boolean')
        seen.add(identifier)
        counts[state] += 1
        if state != 'CLOSED':
            active.append({'id': identifier, 'state': state, 'scope': list(scope),
                           'global_stop': global_stop})
    active.sort(key=lambda row: row['id'])
    return {'counts': counts, 'open_items': active,
            'global_stop': any(row['global_stop'] for row in active)}
