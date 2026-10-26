"""R003 policy projections inside the existing WorkLedger, never a second ledger.

The host owns Context, its fixed root registry, worker identity, Human key ring,
clock and Evidence Shelf. Worker request data cannot provide these capabilities.
No signing, provider dispatch, automatic recovery or approval creation is here.
"""
from __future__ import annotations

import copy
import datetime as dt
import json
import pathlib
import re
import unicodedata
from dataclasses import dataclass

from .reused.binder import ContractError, canonical, digest, need, sha

REVISION = 'YR_IG_003_WORKLEDGER_PATCH_R003'
IDENTITY_FIELDS = ('orders', 'drawings', 'artifacts', 'scopes', 'lineage')
MAX_INT = (1 << 63) - 1


def integer(value, minimum=0):
    need(type(value) is int and minimum <= value <= MAX_INT, 'HOLD_INTEGER_COST_OR_LIMIT')
    return value


def text(value):
    need(type(value) is str and bool(value.strip()), 'HOLD_IDENTITY_TEXT')
    return value


def instant(value):
    try:
        result = dt.datetime.fromisoformat(text(value).replace('Z', '+00:00'))
        need(result.utcoffset() is not None, 'HOLD_APPROVAL_TIMEZONE')
        return result.astimezone(dt.timezone.utc)
    except (TypeError, ValueError):
        raise ContractError('HOLD_APPROVAL_TIME')


def normalize(value):
    value = unicodedata.normalize('NFKC', text(value)).replace('\\', '/').casefold()
    return re.sub(r'\s+', ' ', value).strip().rstrip('/')


def identity(value):
    need(type(value) is dict and set(value) == set(IDENTITY_FIELDS), 'HOLD_IDENTITY_DIMENSIONS')
    result = {}
    for key in IDENTITY_FIELDS:
        rows = value[key]
        need(type(rows) is list and rows, 'HOLD_IDENTITY_SET:' + key)
        result[key] = sorted(set(normalize(item) for item in rows))
    return result


def relation(left, right):
    """Exact drawing/resource alias; partial scope/lineage is an explicit unknown."""
    a, b = identity(left), identity(right)
    if set(a['drawings']) & set(b['drawings']):
        return 'ALIAS_DENY'
    # Resource IDs are canonical Artifact/module locators, not Worker labels.
    if set(a['artifacts']) & set(b['artifacts']):
        return 'ALIAS_DENY'
    # Parent resources are partial overlaps, not newly independent modules.
    if any(x.startswith(y + '/') or y.startswith(x + '/') for x in a['artifacts'] for y in b['artifacts']):
        return 'UNKNOWN_HOLD'
    if any(set(a[key]) & set(b[key]) for key in ('orders', 'scopes', 'lineage')):
        return 'UNKNOWN_HOLD'
    return 'ALLOW'


def used_approvals(state):
    return {row['data']['intent_guard']['approval']['payload']['approval_id']
            for row in state['events'].values()
            if row['data'].get('intent_guard', {}).get('approval') is not None}


@dataclass(frozen=True)
class Context:
    """Only instantiated by the trusted local host, never from a Worker claim."""
    ledger_id: str
    ledger_root: pathlib.Path
    policy_bytes: bytes
    worker_id: str
    witness: object
    human_keys: dict
    revocations: object
    clock: object
    environment: str = 'LOCAL_PRIVATE'

    def __post_init__(self):
        from .shelf_witness import long_path
        object.__setattr__(self, 'ledger_root', long_path(self.ledger_root))

    @property
    def policy(self):
        return json.loads(self.policy_bytes)

    def validate(self, plan, output):
        from .shelf_witness import path_key
        need(path_key(output) == path_key(self.ledger_root), 'HOLD_LEDGER_PATH_BINDING')
        expected = {'schema': 'yr.intent-budget/3', 'ledger_id': self.ledger_id,
                    'policy_sha256': sha(self.policy_bytes)}
        need(plan.get('intent_budget') == expected, 'HOLD_HOST_POLICY_BINDING')
        policy = self.policy
        need(policy.get('schema') == 'yr.intent-root-registry/3', 'HOLD_ROOT_REGISTRY')
        need(policy.get('environment') == self.environment, 'HOLD_ENVIRONMENT_BINDING')
        need(type(policy.get('roots')) is dict and policy['roots'], 'HOLD_ROOT_REGISTRY')
        need(self.witness.ledger_id == self.ledger_id, 'HOLD_SHELF_LEDGER_BINDING')
        self.witness.bind_root(self.ledger_root)
        roots = policy['roots']
        for root_id, root in roots.items():
            text(root_id)
            integer(root['max_attempts'], 1)
            integer(root['max_cost_minor'])
            need(root['currency'] in {'USD', 'JPY', 'EUR'}, 'HOLD_CURRENCY')
            integer(root['minor_exponent'])
            need(root['minor_exponent'] <= 9, 'HOLD_COST_SCALE')
            identity(root['identity'])
            need(self.worker_id in root['workers'] or self.worker_id in policy.get('host_workers', []),
                 'HOLD_WORKER_NOT_REGISTERED')
            for operation, bound in root['operations'].items():
                text(operation)
                integer(bound['upper_cost_minor'])
                text(bound['effect_revision'])
            for other_id, other in roots.items():
                if other_id != root_id:
                    need(relation(root['identity'], other['identity']) == 'ALLOW',
                         'HOLD_ROOT_REGISTRY_OVERLAP')

    def now(self):
        return instant(self.clock()).isoformat()

    def approval_scope(self, action, root_id, attempt_id, binding, anchor):
        return {'action': action, 'ledger_id': self.ledger_id,
                'root_purpose_id': root_id, 'attempt_id': attempt_id,
                'binding_sha256': digest(binding), 'anchor': copy.deepcopy(anchor)}

    def check_approval(self, envelope, expected, at, state=None, current=True):
        """No key, revoked key/approval, wrong scope, expiry or replay => closed."""
        need(type(envelope) is dict, 'HOLD_HUMAN_APPROVAL_REQUIRED')
        try:
            key_id, payload = envelope['key_id'], envelope['payload']
            key = self.human_keys.get(key_id)
            need(key is not None and key.get('role') == 'HUMAN', 'HOLD_HUMAN_KEY_MISSING')
            need(payload['decision'] == 'APPROVE' and payload['issuer_type'] == 'HUMAN',
                 'HOLD_AI_DRAFT_CANNOT_APPROVE')
            need(payload['environment'] == self.environment, 'HOLD_APPROVAL_ENVIRONMENT')
            need(payload['scope'] == expected, 'HOLD_APPROVAL_SCOPE')
            text(payload['approval_id'])
            need(instant(payload['issued_at']) <= instant(at) < instant(payload['expires_at']),
                 'HOLD_APPROVAL_EXPIRED')
            from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
            from cryptography.exceptions import InvalidSignature
            try:
                Ed25519PublicKey.from_public_bytes(bytes.fromhex(key['public_hex'])).verify(
                    bytes.fromhex(envelope['signature_hex']), canonical(payload))
            except (InvalidSignature, ValueError, TypeError):
                raise ContractError('HOLD_HUMAN_SIGNATURE_INVALID')
            if current:
                revoked = self.revocations()
                need(type(revoked) is dict and revoked.get('state') == 'CURRENT',
                     'HOLD_REVOCATION_STATUS_UNKNOWN')
                need(key_id not in revoked['key_ids'] and payload['approval_id'] not in revoked['approval_ids'],
                     'HOLD_APPROVAL_REVOKED')
                need(payload['approval_id'] not in self.witness.used_approvals(), 'HOLD_APPROVAL_REPLAY')
            if state is not None:
                need(payload['approval_id'] not in used_approvals(state), 'HOLD_APPROVAL_REPLAY')
            return payload['approval_id']
        except (KeyError, TypeError, ValueError) as exc:
            if isinstance(exc, ContractError):
                raise
            raise ContractError('HOLD_APPROVAL_MALFORMED') from exc


def intent_bindings(state):
    # Existing TRACE stores its data directly (not wrapped in another state).
    return {row['intent_binding']['purpose_id']: row['intent_binding']
            for row in state['traces'].values() if 'intent_binding' in row}


def projection(state, context):
    result = {root_id: {'root_purpose_id': root_id, 'attempts_used': 0,
                       'reserved_minor': 0, 'actual_minor': 0, 'unsettled': [],
                       'currency': root['currency'], 'minor_exponent': root['minor_exponent']}
              for root_id, root in context.policy['roots'].items()}
    for attempt_id, pending in state['pending'].items():
        guard = pending.get('intent_guard')
        if guard is None:
            continue
        bucket = result[guard['root_purpose_id']]
        bucket['attempts_used'] += 1
        observed = max(pending.get('actual_minor', 0), pending.get('known_cost_minor', 0),
                       pending.get('external_known_cost_minor', 0))
        bucket['actual_minor'] += observed
        if pending['state'] != 'SETTLED_OBSERVED':
            bucket['reserved_minor'] += max(guard['reserved_minor'] - observed, 0)
            bucket['unsettled'].append(attempt_id)
    for bucket in result.values():
        bucket['committed_minor'] = bucket['actual_minor'] + bucket['reserved_minor']
        bucket['unsettled'].sort()
    return result


def root_hold(state, root_id):
    return [row['id'] for row in state['holds'].values()
            if row['state'] in {'HOLD', 'UNKNOWN', 'OPEN', 'CONFLICT'} and
            (row.get('global_stop') or 'INTENT_ROOT:' + root_id in row.get('scope', []))]


def validate_cost_receipt(context, state, observation):
    pending = state['pending'].get(observation.get('id'))
    need(pending is not None and pending.get('intent_guard'), 'HOLD_COST_ATTEMPT_UNKNOWN')
    root_id = pending['intent_guard']['root_purpose_id']
    root = context.policy['roots'][root_id]
    need(observation['currency'] == root['currency'] and observation['minor_exponent'] == root['minor_exponent'],
         'HOLD_CURRENCY_OR_SCALE')
    integer(observation['actual_minor'])
    need(observation['origin_epoch'] == pending['origin_epoch'] and observation['scope'] == pending['scope'] and
         observation['effect_revision'] == pending['effect_revision'] and observation['completion'] == 'OBSERVED',
         'HOLD_ACTUAL_RECEIPT_BINDING')
    return pending, root_id


def external_actual_overlay(context, state, fresh_actual_digest=None):
    """Replay facts sealed outside the native journal, including interrupted writes.

    This is a projection of the existing Shelf, never a new authority or ledger.
    The private fresh digest is usable only inside the single writer transaction
    that first retains the observation and immediately appends its native TRACE.
    """
    booked = {digest(row['cost_observation']) for row in state['traces'].values()
              if 'cost_observation' in row}
    for record in context.witness.records()[1:]:
        if record.get('schema') != 'yr.intent-actual-observation/3':
            continue
        observation = record['receipt']
        receipt_digest = digest(observation)
        if receipt_digest in booked or receipt_digest == fresh_actual_digest:
            continue
        need(context.witness.is_observed_receipt(observation, context.environment), 'HOLD_ACTUAL_OBSERVER_ENVIRONMENT')
        pending, root_id = validate_cost_receipt(context, state, observation)
        # These are cumulative actual-cost observations for one effect. A
        # previously booked higher total already includes an older observation;
        # a newly observed higher total always opens a new reconciliation latch.
        if pending.get('cost_observation_event') and observation['actual_minor'] <= pending['known_cost_minor']:
            continue
        pending['external_known_cost_minor'] = max(pending.get('external_known_cost_minor', 0), observation['actual_minor'])
        pending.setdefault('external_unreconciled_receipts', []).append(receipt_digest)
        if pending['state'] != 'SETTLED_OBSERVED':
            pending['state'] = 'UNKNOWN_COMPLETION'
        refs = [{'external_receipt_sha256': receipt_digest, 'ledger_id': context.ledger_id}]
        latch(state, root_id, observation['id'], 'EXTERNAL_ACTUAL_UNRECONCILED', 'SHELF:' + receipt_digest, refs)
        if observation['actual_minor'] > pending['intent_guard']['reserved_minor']:
            latch(state, root_id, observation['id'], 'UNDER_RESERVED_ACTUAL', 'SHELF:' + receipt_digest, refs)
        if projection(state, context)[root_id]['committed_minor'] > context.policy['roots'][root_id]['max_cost_minor']:
            latch(state, root_id, observation['id'], 'ROOT_COST_EXCEEDED', 'SHELF:' + receipt_digest, refs)


def prepare(context, state, checkpoint, kind, data):
    data = copy.deepcopy(data)
    if kind == 'TRACE' and ('intent_binding' in data or 'cost_observation' in data) or kind in {'EFFECT_PENDING', 'EFFECT_SETTLED'}:
        guard = data.setdefault('intent_guard', {})
        need('allow_parallel' not in data and 'allow_parallel' not in guard, 'HOLD_WORKER_PARALLEL_FLAG')
        guard['worker_id'] = context.worker_id
        guard['checked_at'] = context.now()
        guard['prior_anchor'] = copy.deepcopy(checkpoint)
        last_times = [row['data']['intent_guard']['checked_at'] for row in state['events'].values()
                      if 'checked_at' in row['data'].get('intent_guard', {})]
        need(not last_times or instant(guard['checked_at']) >= max(map(instant, last_times)), 'HOLD_CLOCK_REVERSED')
        if kind == 'EFFECT_PENDING':
            bucket = projection(state, context).get(guard.get('root_purpose_id'))
            need(bucket is not None, 'HOLD_ROOT_UNKNOWN')
            need(not root_hold(state, guard['root_purpose_id']), 'HOLD_INTENT_LATCHED')
            if bucket['unsettled']:
                scope = context.approval_scope('PARALLEL_CLAIM', guard['root_purpose_id'], data['id'],
                                               parallel_binding(data), checkpoint)
                context.check_approval(guard.get('approval'), scope, guard['checked_at'], state)
        elif kind == 'TRACE' and 'cost_observation' in data:
            observation = data['cost_observation']
            pending, root_id = validate_cost_receipt(context, state, observation)
            if pending.get('external_unreconciled_receipts') or data.get('external_reconciliation'):
                data['external_reconciliation'] = True
                scope = context.approval_scope('RECONCILE_COST_OBSERVATION', root_id, observation['id'],
                                               observation, checkpoint)
                context.check_approval(guard.get('approval'), scope, guard['checked_at'], state)
        elif kind == 'EFFECT_SETTLED':
            pending = state['pending'].get(data.get('id'))
            need(pending is not None, 'HOLD_EFFECT_UNKNOWN')
            need(pending['state'] != 'SETTLED_OBSERVED', 'HOLD_DOUBLE_SETTLEMENT')
            if pending['state'] == 'UNKNOWN_COMPLETION' or root_hold(state, guard.get('root_purpose_id')):
                scope = context.approval_scope('RECONCILE_ATTEMPT', guard['root_purpose_id'], data['id'],
                                               settlement_binding(data), checkpoint)
                context.check_approval(guard.get('approval'), scope, guard['checked_at'], state)
    return data


def parallel_binding(data):
    guard = data['intent_guard']
    return {key: copy.deepcopy(value) for key, value in guard.items()
            if key not in {'approval', 'checked_at', 'prior_anchor'}} | {'attempt_id': data['id']}


def settlement_binding(data):
    return {key: copy.deepcopy(value) for key, value in data.items() if key != 'intent_guard'} | {
        'root_purpose_id': data['intent_guard']['root_purpose_id']}


def apply_before(context, state, event):
    kind, data = event['kind'], event['data']
    if kind not in {'TRACE', 'EFFECT_PENDING', 'EFFECT_SETTLED'}:
        return
    if kind == 'TRACE' and not ('intent_binding' in data or 'cost_observation' in data):
        return
    guard = data.get('intent_guard')
    need(type(guard) is dict, 'HOLD_INTENT_BINDING_REQUIRED')
    need('allow_parallel' not in data and 'allow_parallel' not in guard, 'HOLD_WORKER_PARALLEL_FLAG')
    instant(guard['checked_at'])
    need(guard['prior_anchor']['sequence'] == event['sequence'] - 1 and
         guard['prior_anchor']['event_hash'] == event['previous_hash'], 'HOLD_APPROVAL_ANCHOR')
    known = intent_bindings(state)
    if kind == 'TRACE' and 'cost_observation' in data:
        observation = data['cost_observation']
        pending, root_id = validate_cost_receipt(context, state, observation)
        root = context.policy['roots'][root_id]
        need(guard['worker_id'] in root['workers'], 'HOLD_WORKER_NOT_REGISTERED')
        need(context.witness.is_observed_receipt(observation, context.environment), 'HOLD_INDEPENDENT_ACTUAL_RECEIPT_REQUIRED')
        need(observation['actual_minor'] >= max(pending.get('known_cost_minor', 0), pending.get('external_known_cost_minor', 0)),
             'HOLD_ACTUAL_COST_DOWNWARD_REVISION')
        if data.get('external_reconciliation'):
            scope = context.approval_scope('RECONCILE_COST_OBSERVATION', root_id, observation['id'],
                                           observation, guard['prior_anchor'])
            context.check_approval(guard.get('approval'), scope, guard['checked_at'], state, current=False)
        else:
            need(guard.get('approval') is None, 'HOLD_UNUSED_APPROVAL')
        return
    if kind == 'TRACE':
        binding = data['intent_binding']
        purpose_id, parent = text(binding['purpose_id']), binding['parent_purpose_id']
        root_id = binding['root_purpose_id']
        need(purpose_id not in known, 'HOLD_PURPOSE_ID_DUPLICATE')
        if parent is None:
            for previous in known.values():
                if previous['parent_purpose_id'] is None:
                    rel = relation(binding['identity'], previous['identity'])
                    need(rel == 'ALLOW', rel)
        need(root_id in context.policy['roots'], 'HOLD_ROOT_UNKNOWN')
        root = context.policy['roots'][root_id]
        need(guard['worker_id'] in root['workers'], 'HOLD_WORKER_NOT_REGISTERED')
        if parent is None:
            need(purpose_id == root_id and identity(binding['identity']) == identity(root['identity']),
                 'UNKNOWN_HOLD_ROOT_NOT_HOST_REGISTERED')
        else:
            need(parent in known and known[parent]['root_purpose_id'] == root_id, 'HOLD_PURPOSE_LINEAGE')
            # Descendants inherit one root. They may narrow scopes, never own a budget.
            need('max_attempts' not in binding and 'max_cost_minor' not in binding, 'HOLD_CHILD_BUDGET')
            normalized, allowed = identity(binding['identity']), identity(root['identity'])
            need(set(normalized['artifacts']) <= set(allowed['artifacts']) and
                 set(normalized['scopes']) <= set(allowed['scopes']), 'UNKNOWN_HOLD_CHILD_SCOPE')
        return
    purpose_id, root_id = guard.get('purpose_id'), guard.get('root_purpose_id')
    need(purpose_id in known and known[purpose_id]['root_purpose_id'] == root_id, 'HOLD_PURPOSE_LINEAGE')
    root = context.policy['roots'][root_id]
    need(guard['worker_id'] in root['workers'], 'HOLD_WORKER_NOT_REGISTERED')
    need(data['scope'] == ['INTENT_ROOT:' + root_id], 'HOLD_ROOT_SCOPE_BINDING')
    need(guard.get('currency') == root['currency'] and guard.get('minor_exponent') == root['minor_exponent'],
         'HOLD_CURRENCY_OR_SCALE')
    bucket = projection(state, context)[root_id]
    if kind == 'EFFECT_PENDING':
        need(not root_hold(state, root_id), 'HOLD_INTENT_LATCHED')
        need(bucket['attempts_used'] < root['max_attempts'], 'HOLD_ROOT_ATTEMPT_LIMIT')
        need(data['id'] not in state['pending'], 'HOLD_ATTEMPT_DUPLICATE')
        operation = root['operations'].get(guard.get('operation_id'))
        need(operation is not None and data['effect_revision'] == operation['effect_revision'], 'HOLD_OPERATION_BOUND')
        reserve = integer(guard['reserved_minor'])
        need(reserve >= operation['upper_cost_minor'], 'HOLD_UNDER_RESERVATION')
        need(bucket['committed_minor'] + reserve <= root['max_cost_minor'], 'HOLD_ROOT_COST_LIMIT')
        if bucket['unsettled']:
            envelope = guard.get('approval')
            scope = context.approval_scope('PARALLEL_CLAIM', root_id, data['id'], parallel_binding(data), guard['prior_anchor'])
            context.check_approval(envelope, scope, guard['checked_at'], state, current=False)
            permit = envelope['payload'].get('parallel')
            need(type(permit) is dict and integer(permit['max_inflight'], 2) > len(bucket['unsettled']),
                 'HOLD_PARALLEL_LIMIT')
            owners = {state['pending'][attempt]['intent_guard']['worker_id'] for attempt in bucket['unsettled']}
            need(owners | {guard['worker_id']} <= set(permit['workers']), 'HOLD_PARALLEL_WORKER_SCOPE')
        else:
            need(guard.get('approval') is None, 'HOLD_UNUSED_APPROVAL')
    else:
        pending = state['pending'].get(data.get('id'))
        need(pending is not None, 'HOLD_EFFECT_UNKNOWN')
        need(pending['state'] != 'SETTLED_OBSERVED', 'HOLD_DOUBLE_SETTLEMENT')
        need(pending['intent_guard']['root_purpose_id'] == root_id and
             pending['intent_guard']['purpose_id'] == purpose_id, 'HOLD_SETTLEMENT_ROOT')
        integer(data['actual_minor'])
        need(pending.get('known_cost_minor') == data['actual_minor'], 'HOLD_ACTUAL_COST_NOT_BOOKED')
        need(data.get('receipt_binding') == {key: data[key] for key in
             ('id', 'effect_revision', 'origin_epoch', 'scope', 'actual_minor', 'currency', 'minor_exponent', 'completion')},
             'HOLD_ACTUAL_RECEIPT_BINDING')
        need(data['currency'] == root['currency'] and data['minor_exponent'] == root['minor_exponent'], 'HOLD_CURRENCY_OR_SCALE')
        if pending['state'] == 'UNKNOWN_COMPLETION' or root_hold(state, root_id):
            scope = context.approval_scope('RECONCILE_ATTEMPT', root_id, data['id'], settlement_binding(data), guard['prior_anchor'])
            context.check_approval(guard.get('approval'), scope, guard['checked_at'], state, current=False)
        else:
            need(guard.get('approval') is None, 'HOLD_UNUSED_APPROVAL')


def latch(state, root_id, attempt_id, reason, event_id, refs):
    hold_id = 'IG003:' + reason + ':' + attempt_id
    previous = state['holds'].get(hold_id)
    if previous is not None and previous['state'] != 'CLOSED':
        return
    record = {'id': hold_id, 'state': 'HOLD',
        'scope': ['INTENT_ROOT:' + root_id], 'reason': reason,
        'next': 'HUMAN_SIGNED_EXACT_RECONCILIATION_REQUIRED', 'global_stop': False,
        'event': event_id, 'evidence': copy.deepcopy(refs), 'guard_created': True}
    if previous is not None:
        record['previous_closure'] = copy.deepcopy(previous)
    state['holds'][hold_id] = record


def apply_after(context, before, out, event):
    kind, data = event['kind'], event['data']
    if kind == 'TRACE' and 'cost_observation' in data:
        observation = data['cost_observation']
        pending = out['pending'][observation['id']]
        pending['known_cost_minor'] = observation['actual_minor']
        pending['cost_observation_event'] = event['id']
        guard = pending['intent_guard']
        root_id = guard['root_purpose_id']
        if data.get('external_reconciliation'):
            if pending['state'] != 'SETTLED_OBSERVED':
                pending['state'] = 'UNKNOWN_COMPLETION'
                latch(out, root_id, observation['id'], 'UNKNOWN_COMPLETION', event['id'], event['evidence'])
            pending.pop('external_unreconciled_receipts', None)
            pending.pop('external_known_cost_minor', None)
            latch(out, root_id, observation['id'], 'EXTERNAL_ACTUAL_UNRECONCILED', event['id'], event['evidence'])
        if observation['actual_minor'] > guard['reserved_minor']:
            latch(out, root_id, observation['id'], 'UNDER_RESERVED_ACTUAL', event['id'], event['evidence'])
        if projection(out, context)[root_id]['committed_minor'] > context.policy['roots'][root_id]['max_cost_minor']:
            latch(out, root_id, observation['id'], 'ROOT_COST_EXCEEDED', event['id'], event['evidence'])
    elif kind == 'EFFECT_SETTLED':
        pending = out['pending'][data['id']]
        guard = pending['intent_guard']
        pending['actual_minor'] = data['actual_minor']
        pending['currency'] = data['currency']
        root_id = guard['root_purpose_id']
        # Only this new guard's UNKNOWN latch can be closed by exact Human scope.
        if data['intent_guard'].get('approval') is not None:
            for hold in out['holds'].values():
                if hold.get('guard_created') and hold['id'] in {
                        'IG003:UNKNOWN_COMPLETION:' + data['id'], 'IG003:EXTERNAL_ACTUAL_UNRECONCILED:' + data['id']}:
                    hold.update(state='CLOSED', closed_by=event['id'],
                                approval_id=data['intent_guard']['approval']['payload']['approval_id'])
        total = projection(out, context)[root_id]['committed_minor']
        if data['actual_minor'] > guard['reserved_minor']:
            latch(out, root_id, data['id'], 'UNDER_RESERVED_ACTUAL', event['id'], event['evidence'])
        if total > context.policy['roots'][root_id]['max_cost_minor']:
            latch(out, root_id, data['id'], 'ROOT_COST_EXCEEDED', event['id'], event['evidence'])
    elif kind in {'STOP', 'RECORDING_GAP'}:
        for attempt_id, pending in out['pending'].items():
            if pending.get('intent_guard') and pending['state'] != 'SETTLED_OBSERVED':
                pending['state'] = 'UNKNOWN_COMPLETION'
                latch(out, pending['intent_guard']['root_purpose_id'], attempt_id,
                      'UNKNOWN_COMPLETION', event['id'], event['evidence'])


def validate_actual_refs(base, refs, data, validate_evidence):
    matches = []
    for ref in refs:
        if ref['record_class'] == 'RECEIPT' and ref['subject'] == data['id']:
            raw = validate_evidence(base, ref)
            try:
                matches.append(json.loads(raw))
            except (ValueError, UnicodeError):
                raise ContractError('HOLD_ACTUAL_RECEIPT_TYPE')
    need(len(matches) == 1 and matches[0] == data['receipt_binding'], 'HOLD_ACTUAL_RECEIPT_BYTES')


def inspection_projection(state, context, assessment_input, assessor):
    """Existing 3RUN stays the classifier. Reservations are an additional view."""
    expected = {attempt_id for attempt_id, pending in state['pending'].items()
                if pending.get('intent_guard') and pending['state'] == 'SETTLED_OBSERVED'}
    observed = {row['run_id'] for row in assessment_input.get('executed_receipts', [])}
    need(observed == expected, 'HOLD_3RUN_HISTORY_OMISSION')
    result = assessor(copy.deepcopy(assessment_input))
    return {'schema': 'yr.intent-three-run-projection/3', 'assessment': result,
            'root_buckets': projection(state, context), 'holds': copy.deepcopy(state['holds']),
            'authority_effect': 'NONE', 'human_acceptance': 'NOT_GRANTED',
            'reservation_is_live_execution': False}
