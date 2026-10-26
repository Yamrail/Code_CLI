"""Existing Evidence Shelf artifact_freeze adapter; no separate decision engine.

The host must protect this path independently of Worker-writable WorkLedger.
Every external seal is the exact native event, not a summary or reconstructed claim.
"""
from __future__ import annotations

import contextlib
import copy
import datetime as dt
import json
import os
import pathlib
import time

from .reused.binder import canonical, digest, need, sha, ContractError
from yr_tools.artifact_freeze import freeze


def long_path(path):
    value = str(pathlib.Path(path).resolve())
    if os.name == 'nt' and not value.startswith('\\\\?\\'):
        value = ('\\\\?\\UNC\\' + value[2:]) if value.startswith('\\\\') else '\\\\?\\' + value
    return pathlib.Path(value)


def path_key(path):
    value = str(pathlib.Path(path).resolve())
    if value.startswith('\\\\?\\UNC\\'):
        value = '\\\\' + value[8:]
    elif value.startswith('\\\\?\\'):
        value = value[4:]
    return os.path.normcase(value)


def write_new(path, raw):
    path = long_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


@contextlib.contextmanager
def writer_lock(ledger_root, ledger_id, timeout=5):
    """OS lock survives neither process exit nor handle close; no stale lock file."""
    root = long_path(ledger_root)
    lock_path = root.parent / ('ig003-' + sha(ledger_id.encode()) + '.lock')
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    stream = lock_path.open('a+b')
    if stream.seek(0, 2) == 0:
        stream.write(b'0')
        stream.flush()
    deadline = time.monotonic() + timeout
    acquired = False
    try:
        while not acquired:
            stream.seek(0)
            try:
                if os.name == 'nt':
                    import msvcrt
                    msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
            except OSError:
                need(time.monotonic() < deadline, 'HOLD_LEDGER_BUSY')
                time.sleep(0.01)
        yield
    finally:
        if acquired:
            stream.seek(0)
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
        stream.close()


class EvidenceShelfWitness:
    def __init__(self, root, ledger_id):
        self.root = long_path(root)
        self.ledger_id = ledger_id

    def bind_root(self, ledger_root):
        path = long_path(ledger_root)
        need(not hasattr(self, 'ledger_root') or self.ledger_root == path, 'HOLD_SHELF_ROOT_REBIND')
        self.ledger_root = path

    def _freeze(self, label, record):
        raw = canonical(record)
        source = self.root / 'staging' / (label + '.json')
        state_path = self.root / 'staging' / (label + '.state.json')
        write_new(source, raw)
        artifact_id = self.ledger_id + ':' + label
        revision = sha(raw)
        common = {'schema': 'yr.binding/1', 'artifact_id': artifact_id,
                  'namespace': 'INGRIDGE_PRIVATE_EVIDENCE_SHELF', 'revision': revision,
                  'parent_commit': '4f499fa6cf7159b3b07e563fa525738c1e006954',
                  'scope_epoch': 'IG003_R003', 'provenance_id': 'HOST_WORKLEDGER_RECORDER',
                  'record_class': 'EXECUTION'}
        ref = {**common, 'locator': source.relative_to(self.root).as_posix(), 'sha256': sha(raw)}
        snapshot = {key: {'state': 'OBSERVED', 'values': []} for key in
                    ('known_scope', 'verified_scope', 'unknown_points', 'holds',
                     'unresolved_points', 'not_guaranteed_scope')}
        snapshot['known_scope']['values'] = [self.ledger_id, label]
        snapshot['not_guaranteed_scope']['values'] = ['HUMAN_ACCEPTANCE', 'EXTERNAL_SHELF_COMPROMISE']
        state_record = {'subject': {'artifact_id': artifact_id, 'revision': revision},
                        'parent_commit': common['parent_commit'], 'scope_epoch': common['scope_epoch'],
                        'provenance_id': common['provenance_id'], 'state_snapshot': snapshot,
                        'authority_effect': 'NONE', 'canonical_effect': 'NONE', 'human_gate': 'NOT_EXECUTED'}
        state_raw = canonical(state_record)
        write_new(state_path, state_raw)
        state_ref = {**common, 'record_class': 'OBSERVATION',
                     'locator': state_path.relative_to(self.root).as_posix(), 'sha256': sha(state_raw)}
        request = {'schema': 'yr.artifact-freeze/1', 'operation': 'copy',
                   'artifact_id': artifact_id, 'revision': revision, 'source_ref': ref,
                   'state_ref': state_ref, 'state_snapshot': snapshot,
                   'destination_path': 'anchors/' + label + '.json', 'register_path': 'register.jsonl',
                   'authority_scope': 'PRIVATE_EXACT_EVENT_RETENTION_ONLY',
                   'authority_ref': 'YR-WO-INTENT-GUARD-R003',
                   'time_anchor': {'receipt_time': record.get('observed_at_host_utc', dt.datetime.now(dt.timezone.utc).isoformat()),
                                   'domain': 'HOST_OBSERVATION_NOT_INDEPENDENT_UTC'},
                   'provenance': {'class': 'EXACT_WORKLEDGER_EVENT', 'ledger_id': self.ledger_id},
                   'downstream_dependencies': [], 'supersedes': [],
                   'authority_effect': 'NONE', 'canonical_effect': 'NONE', 'human_gate': 'NOT_EXECUTED'}
        pin = {'input_digest': digest(request), 'source': {**ref, 'pin_origin': 'FROZEN_RUNNER_CHECKPOINT'},
               'state': {**state_ref, 'pin_origin': 'FROZEN_RUNNER_CHECKPOINT'},
               'authority_scope': request['authority_scope']}
        result = freeze(request, pin, self.root)
        need(result['verdict'] == 'PASS_ARTIFACT_FREEZE_RETENTION_ONLY',
             'HOLD_EXTERNAL_SEAL:' + str(result.get('reasons')))
        for path in (self.root / request['destination_path'], self.root / 'register.jsonl'):
            with path.open('ab') as stream:
                stream.flush()
                os.fsync(stream.fileno())
        return result['receipt']

    def initialize(self, plan, policy_sha256, ledger_root):
        need(not self.root.exists(), 'HOLD_EXTERNAL_LEDGER_ALREADY_BOUND')
        need(not self.root.is_relative_to(long_path(ledger_root)) and
             not long_path(ledger_root).is_relative_to(self.root), 'HOLD_SHELF_NOT_SEPARATE')
        self.root.mkdir(parents=True)
        self._freeze('000000', {'schema': 'yr.intent-shelf-genesis/3', 'ledger_id': self.ledger_id,
            'ledger_root': str(long_path(ledger_root)), 'plan_digest': digest(plan),
            'policy_sha256': policy_sha256, 'authority_effect': 'NONE'})

    def records(self):
        need((self.root / 'register.jsonl').is_file(), 'HOLD_EXTERNAL_ANCHOR_MISSING')
        try:
            receipts = [json.loads(line) for line in (self.root / 'register.jsonl').read_bytes().splitlines()]
            need(receipts, 'HOLD_EXTERNAL_ANCHOR_MISSING')
            paths = list((self.root / 'anchors').glob('*.json'))
            need(len(paths) == len(receipts), 'HOLD_EXTERNAL_REGISTER_GAP')
            result = []
            for receipt in receipts:
                path = self.root / receipt['storage_locator']
                raw = path.read_bytes()
                need(sha(raw) == receipt['sha256'] and len(raw) == receipt['bytes'], 'HOLD_EXTERNAL_ANCHOR_HASH')
                result.append(json.loads(raw))
            need(result[0]['ledger_id'] == self.ledger_id, 'HOLD_SHELF_LEDGER_BINDING')
            sequence, previous = 0, '0' * 64
            for event in result[1:]:
                if event.get('schema') in {'yr.intent-recovery-use/3', 'yr.intent-actual-observation/3'}:
                    continue
                sequence += 1
                core = {key: value for key, value in event.items() if key != 'event_hash'}
                need(event['sequence'] == sequence and event['previous_hash'] == previous and
                     digest(core) == event['event_hash'], 'HOLD_EXTERNAL_EVENT_CHAIN')
                previous = event['event_hash']
            return result
        except (OSError, ValueError, KeyError, TypeError) as exc:
            if isinstance(exc, ContractError):
                raise
            raise ContractError('HOLD_EXTERNAL_ANCHOR_UNREADABLE') from exc

    def events(self):
        return [record for record in self.records()[1:] if 'event_hash' in record]

    def latest(self):
        records = self.records()
        events = [record for record in records[1:] if 'event_hash' in record]
        return {'sequence': len(events), 'event_hash': events[-1]['event_hash'] if events else '0' * 64,
                'plan_digest': records[0]['plan_digest']}

    def used_approvals(self):
        result = set()
        for record in self.records()[1:]:
            if record.get('schema') == 'yr.intent-recovery-use/3':
                result.add(record['approval']['payload']['approval_id'])
            elif 'event_hash' in record:
                approval = record['data'].get('intent_guard', {}).get('approval')
                if approval is not None:
                    result.add(approval['payload']['approval_id'])
        return result

    def retain_actual_receipt(self, receipt, observer_class):
        need(hasattr(self, 'ledger_root'), 'HOLD_SHELF_ROOT_UNBOUND')
        with writer_lock(self.ledger_root, self.ledger_id):
            return self._retain_actual_receipt_locked(receipt, observer_class)

    def _retain_actual_receipt_locked(self, receipt, observer_class):
        need(observer_class in {'HOST_LOCAL_ZERO_COST', 'SYNTHETIC_FIXTURE'}, 'HOLD_ACTUAL_OBSERVER_CLASS')
        label = 'actual-' + digest(receipt)
        if (self.root / 'anchors' / (label + '.json')).exists():
            need(self.is_observed_receipt(receipt), 'HOLD_ACTUAL_OBSERVATION_COLLISION')
            return
        self._freeze(label, {'schema': 'yr.intent-actual-observation/3', 'ledger_id': self.ledger_id,
                            'observer_class': observer_class, 'receipt': copy.deepcopy(receipt),
                            'authority_effect': 'NONE'})

    def is_observed_receipt(self, receipt, environment=None):
        allowed = {'SYNTHETIC_FIXTURE'} if environment == 'SYNTHETIC_FIXTURE' else {'HOST_LOCAL_ZERO_COST'}
        if environment is None:
            allowed |= {'SYNTHETIC_FIXTURE'}
        return any(record.get('schema') == 'yr.intent-actual-observation/3' and
                   record.get('ledger_id') == self.ledger_id and record.get('receipt') == receipt
                   and record.get('observer_class') in allowed
                   and (record.get('observer_class') != 'HOST_LOCAL_ZERO_COST' or receipt.get('actual_minor') == 0)
                   for record in self.records()[1:])

    def verify(self, plan, journal, checkpoint):
        records = self.records()
        need(records[0]['plan_digest'] == digest(plan), 'HOLD_SHELF_PLAN_BINDING')
        latest = self.latest()
        need(checkpoint == latest, 'HOLD_EXTERNAL_CHECKPOINT_MISMATCH')
        expected = b''.join(canonical(event) + b'\n' for event in self.events())
        need(pathlib.Path(journal).read_bytes() == expected, 'HOLD_EXTERNAL_JOURNAL_MISMATCH')

    def stage(self, event):
        previous = self.latest()
        need(event['sequence'] == previous['sequence'] + 1 and event['previous_hash'] == previous['event_hash'],
             'HOLD_EXTERNAL_EVENT_ORDER')
        approval = event['data'].get('intent_guard', {}).get('approval')
        if approval is not None:
            need(approval['payload']['approval_id'] not in self.used_approvals(), 'HOLD_APPROVAL_REPLAY')
        return self._freeze('%06d' % event['sequence'], event)

    def consume_recovery(self, approval, anchor, at):
        approval_id = approval['payload']['approval_id']
        need(approval_id not in self.used_approvals(), 'HOLD_APPROVAL_REPLAY')
        self._freeze('recovery-' + sha(approval_id.encode()), {'schema': 'yr.intent-recovery-use/3',
                     'approval': copy.deepcopy(approval), 'anchor': anchor,
                     'observed_at_host_utc': at, 'authority_effect': 'NONE'})
