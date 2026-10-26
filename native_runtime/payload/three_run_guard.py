"""Frozen-input inspection-budget assessor. No IO, clock, network or authority."""
from __future__ import annotations
import copy
import hashlib
import json
import re
from datetime import datetime

VERSION = 'YR-THREE-RUN-GUARD-1.0.2'
RULE = 'YR-RULE-THREE-LIVE-RUN-EVIDENCE-BASED-20261014-01'
RULE_SHA256 = '73264da083e3a97f55ba188c4f8c2e4d30baed94ccf5f2f5a1d7fada12c363c3'
STATES = {'NOT_EXECUTED', 'PASS_SCOPED', 'FAIL_OBSERVED', 'HOLD_BLOCKED', 'UNKNOWN'}
OFFLINE = {'STATIC_REVIEW', 'FIXTURE_ONLY_OFFLINE_RUN', 'HASH_OR_REMOTE_READBACK', 'REPORT_OR_RECORD_REVIEW'}
GROUNDS = {'OBSERVED_FAILURE', 'PREVIOUS_EVIDENCE_INVALIDATED', 'APPLICABLE_MANDATORY_CRITERION'}

def canonical_bytes(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')

def digest(value):
    return hashlib.sha256(canonical_bytes(value)).hexdigest()

def _time(s):
    if not isinstance(s, str):
        raise ValueError('timestamp missing')
    x = datetime.fromisoformat(s.replace('Z', '+00:00'))
    if x.utcoffset() is None:
        raise ValueError('timestamp needs timezone')
    return x

def assess(data):
    """Classify supplied records; never attest their origin or execute a run.

    SHA/locator binding verifies the frozen package, not truthful real-world
    authorship. Synthetic scenarios are always marked and counted separately.
    """
    x = copy.deepcopy(data)
    out = {'schema': 'yamrail.three-run-guard.output/1', 'tool_version': VERSION,
           'rule_revision': RULE, 'rule_sha256': RULE_SHA256,
           'workface_id': x.get('workface_id') if isinstance(x, dict) else None,
           'evaluation_mode': None, 'input_sha256': None,
           'run_plan': [], 'actual_run_count': 0, 'simulated_run_count': 0,
           'run_accounting': {}, 'additional_run_decisions': [],
           'inspection_state_per_edge': [], 'remaining_holds': [],
           'evidence_refs': [], 'contract_errors': [], 'rejected_claims': [],
           'workface_states': [], 'final_result': 'LOCAL_HOLD',
           'authority_effect': 'NONE', 'publication_effect': 'NONE',
           'canonical_effect': 'NONE', 'external_operations_performed': 0,
           'evidence_boundary': 'Frozen caller-supplied records; hashes do not authenticate real-world origin. Synthetic results never prove live acceptance.'}
    errors = out['contract_errors']
    def error(code, at):
        errors.append({'code': code, 'at': str(at)})
    def require(condition, code, at):
        if not condition:
            raise ValueError(code + '@' + str(at))
    def records(key):
        rows = x.get(key, [])
        require(isinstance(rows, list), 'EXPECTED_ARRAY', key)
        return rows
    def text(v):
        return isinstance(v, str) and bool(v.strip())
    def ident(rows, field, where):
        result = {}
        for row in rows:
            require(isinstance(row, dict) and text(row.get(field)), 'MISSING_ID', where)
            require(row[field] not in result, 'DUPLICATE_ID', where + '/' + row[field])
            result[row[field]] = row
        return result
    try:
        require(isinstance(x, dict), 'EXPECTED_OBJECT', 'input')
        out['input_sha256'] = digest(x)
        require(x.get('schema') == 'yamrail.three-run-guard.input/1', 'SCHEMA', 'input')
        require(x.get('mode') in ['SYNTHETIC', 'RECORDED'], 'MODE', 'mode')
        out['evaluation_mode'] = x['mode']
        require(all(text(x.get(k)) for k in ['workface_id', 'source_repo']), 'SOURCE_IDENTITY', 'input')
        require(isinstance(x.get('fixed_commit'), str) and re.fullmatch('[a-f0-9]{40}', x['fixed_commit']), 'FIXED_COMMIT', 'input')
        require(x.get('rule_revision') == RULE, 'RULE_REVISION', 'input')
        edges = ident(records('required_acceptance_edges'), 'edge_id', 'edges')
        require(edges and any(e.get('workface_id') == x['workface_id'] for e in edges.values()), 'MISSING_ACCEPTANCE_SCOPE', 'edges')
        for id, e in edges.items():
            require(all(text(e.get(k)) for k in ['workface_id', 'criterion', 'applicability_reason']), 'EDGE_CONTEXT', id)
            require(type(e.get('mandatory')) is bool and type(e.get('applicable')) is bool, 'EDGE_APPLICABILITY', id)
            require(e.get('inspection_kind') in OFFLINE | {'LIVE'}, 'INSPECTION_KIND', id)
            require(isinstance(e.get('depends_on', []), list), 'DEPENDENCIES', id)
            for dep in e.get('depends_on', []):
                require(isinstance(dep, dict) and dep.get('edge_id') in edges and dep.get('kind') in ['HARD_DEPENDENCY', 'CURRENT_ROUTE_ONLY', 'UNKNOWN_HOLD'], 'TYPED_DEPENDENCY', id)
        evidence = ident(records('evidence'), 'evidence_id', 'evidence')
        valid_evidence = {}
        locators = set()
        for id, ev in sorted(evidence.items()):
            if not text(ev.get('locator')) or ev.get('locator') in locators or not isinstance(ev.get('payload'), dict) or ev.get('sha256') != digest(ev.get('payload')):
                error('EVIDENCE_LOCATOR_OR_HASH_MISMATCH', id)
                continue
            locators.add(ev['locator']); valid_evidence[id] = ev
        changes = ident(records('change_events'), 'change_id', 'changes')
        def proof_refs(refs):
            return isinstance(refs, list) and bool(refs) and all(id in valid_evidence for id in refs)
        valid_changes = {}
        for id, change in sorted(changes.items()):
            if not proof_refs(change.get('evidence_refs')):
                error('CHANGE_EVIDENCE_MISSING', id); continue
            fields = ['change_id', 'from_commit', 'to_commit', 'affected_edges', 'invalidated_receipts', 'reason']
            if 'preserved_edges' in change: fields.append('preserved_edges')
            if not all(k in change for k in fields) or not text(change['reason']) or not set(change['affected_edges']) <= set(edges):
                error('CHANGE_CONTEXT', id); continue
            if not all(isinstance(change[k], str) and re.fullmatch('[a-f0-9]{40}', change[k]) for k in ['from_commit','to_commit']) or not set(change.get('preserved_edges', [])) <= set(edges) or set(change.get('preserved_edges', [])) & set(change['affected_edges']):
                error('CHANGE_ARTIFACT_OR_SCOPE', id); continue
            if not any(all(valid_evidence[r]['payload'].get(k) == change[k] for k in fields) for r in change['evidence_refs']):
                error('CHANGE_PROOF_MISMATCH', id); continue
            valid_changes[id] = change
        plans = records('planned_live_runs')
        require(len(plans) <= 3, 'PRIMARY_BUDGET_EXCEEDED', 'planned_live_runs')
        planned = {}; slots = {}
        for p in plans:
            require(type(p.get('slot')) is int and 1 <= p['slot'] <= 3 and p['slot'] not in slots, 'PRIMARY_SLOT', 'plan')
            slots[p['slot']] = p
            if p.get('status') == 'N/A':
                require(text(p.get('reason')) and not p.get('covered_edges'), 'NA_REASON', str(p['slot']))
                continue
            require(text(p.get('run_id')) and p['run_id'] not in planned, 'RUN_ID', 'plan')
            require(text(p.get('target')), 'EXPECTED_TARGET', p['run_id'])
            require(isinstance(p.get('covered_edges'), list) and p['covered_edges'] and set(p['covered_edges']) <= set(edges), 'RUN_EDGES', p['run_id'])
            require(all(edges[e]['applicable'] and edges[e]['inspection_kind'] == 'LIVE' for e in p['covered_edges']), 'LIVE_RUN_KIND', p['run_id'])
            planned[p['run_id']] = dict(p, run_class='PRIMARY')
        for slot in range(1, 4):
            p = slots.get(slot)
            out['run_plan'].append({'slot': slot, 'run_id': p.get('run_id') if p else None,
                'covered_edges': sorted(p.get('covered_edges', [])) if p else [],
                'status': ('N/A' if p.get('status') == 'N/A' else 'PLANNED') if p else 'UNUSED_NOT_NEEDED',
                'reason': p.get('reason', '') if p else 'No fill-to-three; absent slots do not create inspections.'})
        extras = ident(records('extra_requests'), 'request_id', 'extras'); used_conditions = set()
        extra_plans = {}
        for id, q in sorted(extras.items()):
            decision = {'request_id': id, 'decision': 'DENY_UNGROUNDED', 'edge_ids': sorted(q.get('edge_ids', [])), 'allowed_runs': 0, 'reason': ''}
            out['additional_run_decisions'].append(decision)
            kind = q.get('ground_class'); refs = q.get('evidence_refs', []); edge_ids = q.get('edge_ids', [])
            if kind not in GROUNDS:
                decision['reason'] = 'Speculation, reassurance and absence-of-defect proof do not justify another run.'; continue
            if not proof_refs(refs) or not isinstance(edge_ids, list) or not edge_ids or not set(edge_ids) <= set(edges):
                decision.update(decision='HOLD_REQUIRED_CONTEXT', reason='Missing frozen evidence or exact affected edges.'); continue
            if any(not edges[e]['applicable'] or edges[e]['inspection_kind'] != 'LIVE' for e in edge_ids):
                decision['reason'] = 'Offline or inapplicable checks do not justify additional live runs.'; continue
            payloads = [valid_evidence[r]['payload'] for r in refs]
            cids = q.get('change_ids', []); cs = [valid_changes[c] for c in cids if c in valid_changes]
            grounded = set()
            if kind == 'OBSERVED_FAILURE':
                for p in payloads:
                    if p.get('kind') == 'OBSERVED_FAILURE' and text(p.get('observation')) and p.get('result') == 'FAIL_OBSERVED':
                        grounded.update(p.get('edge_ids', []))
                if not cs or not all(set(edge_ids) <= set(c['affected_edges']) and c['to_commit'] == x['fixed_commit'] for c in cs):
                    decision.update(decision='HOLD_REQUIRED_CONTEXT', reason='Bind the local repair or changed execution conditions before a retry.'); continue
            elif kind == 'PREVIOUS_EVIDENCE_INVALIDATED':
                for c in cs:
                    if c['to_commit'] == x['fixed_commit'] and c['invalidated_receipts']:
                        grounded.update(c['affected_edges'])
                if not cs:
                    decision.update(decision='HOLD_REQUIRED_CONTEXT', reason='No verified old/new change and invalidated receipt binding.'); continue
            else:
                for p in payloads:
                    if p.get('kind') == 'APPLICABLE_MANDATORY_CRITERION' and p.get('applicable') is True and text(p.get('criterion_locator')) and text(p.get('why_three_slots_insufficient')):
                        grounded.update(p.get('edge_ids', []))
            if not set(edge_ids) <= grounded:
                decision.update(decision='DENY_UNGROUNDED', reason='Requested edges exceed the observed failure, invalidated evidence or applicable criterion.'); continue
            runs = q.get('runs', [])
            if type(q.get('requested_runs')) is not int or q['requested_runs'] <= 0 or not isinstance(runs, list) or len(runs) != q['requested_runs']:
                decision.update(decision='HOLD_REQUIRED_CONTEXT', reason='Finite requested count must match the explicit targeted run plan.'); continue
            # Only contributing grounds identify an allocation. A NOTE, a
            # reordered attachment or request-ID change cannot create a new
            # physical failure/change/required-condition combination.
            contributing = [p for p in payloads if set(p.get('edge_ids', [])) & set(edge_ids) and (
                (kind == 'OBSERVED_FAILURE' and p.get('kind') == 'OBSERVED_FAILURE' and p.get('result') == 'FAIL_OBSERVED' and text(p.get('observation'))) or
                (kind == 'APPLICABLE_MANDATORY_CRITERION' and p.get('kind') == 'APPLICABLE_MANDATORY_CRITERION' and p.get('applicable') is True and text(p.get('criterion_locator')) and text(p.get('why_three_slots_insufficient'))))]
            proof_hashes = sorted({digest({k:v for k,v in p.items() if k not in ['evidence_id','change_id','retest_conditions']}) for p in contributing})
            relevant_changes = [c for c in cs if set(c['affected_edges']) & set(edge_ids) and c['to_commit'] == x['fixed_commit']]
            change_hashes = sorted({digest({k:v for k,v in c.items() if k not in ['change_id','evidence_refs']}) for c in relevant_changes})
            fingerprint = digest({'kind': kind, 'proofs': proof_hashes, 'changes': change_hashes})
            conditions = {}
            for payload in contributing:
                for condition in payload.get('retest_conditions', []):
                    if isinstance(condition, dict) and text(condition.get('condition_id')) and text(condition.get('requirement')) and isinstance(condition.get('edge_ids'), list):
                        conditions[condition['condition_id']] = condition
            for c in relevant_changes:
                for ref in c['evidence_refs']:
                    for condition in valid_evidence[ref]['payload'].get('retest_conditions', []):
                        if isinstance(condition, dict) and text(condition.get('condition_id')) and text(condition.get('requirement')) and isinstance(condition.get('edge_ids'), list):
                            conditions[condition['condition_id']] = condition
            if any(not text(r.get('run_id')) or r.get('run_id') in planned or r.get('run_id') in extra_plans or not text(r.get('target')) or not text(r.get('reason')) or not r.get('covered_edges') or not set(r['covered_edges']) <= set(edge_ids) or r.get('condition_id') not in conditions or not set(r['covered_edges']) <= set(conditions.get(r.get('condition_id'), {}).get('edge_ids', [])) for r in runs) or len({r.get('run_id') for r in runs}) != len(runs) or len({r.get('condition_id') for r in runs}) != len(runs):
                decision.update(decision='HOLD_REQUIRED_CONTEXT', reason='Run IDs and targeted coverage must be unambiguous.'); continue
            allocations = {(fingerprint, digest({'edge_ids':sorted(conditions[r['condition_id']]['edge_ids']), 'requirement':conditions[r['condition_id']]['requirement']})) for r in runs}
            if allocations & used_conditions:
                decision['reason'] = 'The same grounded condition is already allocated; irrelevant attachments and new IDs do not justify retries.'; continue
            used_conditions |= allocations
            for r in runs:
                extra_plans[r['run_id']] = dict(r, run_class='ADDITIONAL', request_id=id)
            decision.update(decision='ALLOW_TARGETED', allowed_runs=len(runs), reason='Recorded basis covers only these edges; this is a plan assessment, not execution permission.')
        runmap = {**planned, **extra_plans}
        receipts = ident(records('executed_receipts'), 'receipt_id', 'receipts')
        observations = {id: [] for id in edges}; accepted = []; witnessed_live = []; excluded = []; run_ids = set()
        invalidated = {}
        for c in valid_changes.values():
            if c['to_commit'] == x['fixed_commit']:
                for rid in c['invalidated_receipts']: invalidated.setdefault(rid,set()).update(c['affected_edges'])
        for id, r in sorted(receipts.items()):
            if r.get('executed') is False:
                if any(z.get('state') == 'PASS_SCOPED' for z in r.get('edge_results', [])):
                    error('FALSE_PASS_UNEXECUTED', id)
                excluded.append({'receipt_id': id, 'reason': 'NOT_EXECUTED'}); continue
            fields = ['receipt_id', 'run_id', 'fixed_commit', 'target', 'executor', 'executed_at', 'inspection_kind', 'executed', 'edge_results', 'origin']
            if r.get('executed') is not True or not all(k in r for k in fields) or not proof_refs(r.get('evidence_refs')):
                error('RECEIPT_EVIDENCE_MISSING', id); excluded.append({'receipt_id': id, 'reason': 'CONTRACT_ERROR'}); continue
            matching = [valid_evidence[e]['payload'] for e in r['evidence_refs'] if all(valid_evidence[e]['payload'].get(k) == r[k] for k in fields)]
            if not matching or not text(r['target']) or not text(r['executor']):
                error('RECEIPT_PROOF_MISMATCH', id); excluded.append({'receipt_id': id, 'reason': 'CONTRACT_ERROR'}); continue
            if r['origin'] != ('SYNTHETIC' if x['mode'] == 'SYNTHETIC' else 'OBSERVED'):
                error('SYNTHETIC_LIVE_MIX', id); continue
            try: timestamp = _time(r['executed_at'])
            except (ValueError, TypeError): error('RECEIPT_TIME', id); continue
            if r['run_id'] in run_ids:
                error('DUPLICATE_EXECUTION_ID', id); continue
            run_ids.add(r['run_id'])
            results = r['edge_results']
            if not isinstance(results, list) or not results or any(z.get('edge_id') not in edges or z.get('state') not in STATES for z in results) or len({z['edge_id'] for z in results}) != len(results):
                error('RECEIPT_EDGE_RESULTS', id); continue
            if r['inspection_kind'] == 'LIVE': witnessed_live.append(r)
            if r['inspection_kind'] == 'LIVE':
                p = runmap.get(r['run_id'])
                if not p or r['target'] != p['target'] or {z['edge_id'] for z in results} != set(p['covered_edges']):
                    error('UNPLANNED_OR_BROADER_EXECUTION', id); continue
            elif r['inspection_kind'] not in OFFLINE or any(edges[z['edge_id']]['inspection_kind'] != r['inspection_kind'] for z in results):
                error('OFFLINE_LIVE_SUBSTITUTION', id); continue
            accepted.append(r)
            for z in results:
                eid = z['edge_id']
                preserved = any(c['from_commit'] == r['fixed_commit'] and c['to_commit'] == x['fixed_commit'] and eid in c.get('preserved_edges', []) for c in valid_changes.values())
                if eid in invalidated.get(id, set()) or (r['fixed_commit'] != x['fixed_commit'] and not preserved):
                    excluded.append({'receipt_id': id, 'edge_id': eid, 'reason': 'OLD_OR_INVALIDATED_EVIDENCE'})
                    observations[eid].append({'state': 'UNKNOWN', 'receipt_id': id, 'reason': 'Old or invalidated evidence; no implicit PASS inheritance.'})
                    continue
                observations[z['edge_id']].append({'state': z['state'], 'receipt_id': id, 'time': timestamp.isoformat(), 'evidence_refs': sorted(r['evidence_refs']), 'supersedes': r.get('supersedes_receipts', [])})
        recorded_live = [r for r in accepted if r['inspection_kind'] == 'LIVE']
        out['actual_run_count'] = len(witnessed_live) if x['mode'] == 'RECORDED' else 0
        out['simulated_run_count'] = len(witnessed_live) if x['mode'] == 'SYNTHETIC' else 0
        out['run_accounting'] = {'accepted_recorded_primary': sum(r['run_id'] in planned for r in recorded_live), 'accepted_recorded_additional': sum(r['run_id'] in extra_plans for r in recorded_live), 'not_executed_primary_run_ids': sorted(set(planned) - {r['run_id'] for r in recorded_live}), 'offline_receipts_not_in_three_run_count': sum(r['inspection_kind'] in OFFLINE for r in accepted), 'excluded_claims': excluded, 'recorded_consumption': [{'receipt_id':r['receipt_id'],'consumption':r.get('consumption')} for r in witnessed_live], 'invalidated_evidence_does_not_erase_execution_count':True,'tool_performed_live_calls': 0}
        states = {}; edge_refs = {}; reasons = {}
        for id, e in sorted(edges.items()):
            obs = sorted(observations[id], key=lambda z: (z.get('time', ''), z['receipt_id']))
            edge_refs[id] = sorted({r for z in obs for r in z.get('evidence_refs', [])})
            if not e['applicable']:
                states[id] = 'NOT_EXECUTED'; reasons[id] = 'N/A: ' + e['applicability_reason']; continue
            if not obs:
                states[id] = 'NOT_EXECUTED'; reasons[id] = 'No accepted execution evidence.'; continue
            # A later success cannot erase a failure without a justified targeted
            # retry and explicit receipt supersession. History remains in output.
            failures = [z for z in obs if z['state'] == 'FAIL_OBSERVED']
            last = obs[-1]; unresolved = []
            for f in failures:
                successor = next((z for z in obs if z['state'] == 'PASS_SCOPED' and f['receipt_id'] in z.get('supersedes', []) and any(r['receipt_id'] == z['receipt_id'] and r['run_id'] in extra_plans for r in accepted)), None)
                if not successor: unresolved.append(f)
            if unresolved:
                states[id] = 'FAIL_OBSERVED'; reasons[id] = 'Observed failures remain unresolved.'
            else:
                states[id] = last['state']; reasons[id] = last.get('reason', 'Scoped accepted execution record.')
        holds = ident(records('existing_holds'), 'hold_id', 'holds')
        hold_rows = []
        for id, h in sorted(holds.items()):
            require(isinstance(h.get('edge_ids'), list) and text(h.get('reason')), 'HOLD_CONTEXT', id)
            seed = set(h['edge_ids']) & set(edges); affected = set(seed)
            for _ in edges:
                added = {eid for eid, e in edges.items() if e['applicable'] and any(dep['kind'] == 'HARD_DEPENDENCY' and dep['edge_id'] in affected for dep in e.get('depends_on', []))}
                if added <= affected: break
                affected |= added
            for eid in affected:
                if states[eid] != 'FAIL_OBSERVED': states[eid] = 'HOLD_BLOCKED'
                reasons[eid] = 'Existing HOLD ' + id
            hold_rows.append({**h, 'affected_edges': sorted(affected), 'inherited_unchanged': True})
        # Required incomplete dependencies block only their hard descendants.
        for _ in edges:
            changed = False
            for id, e in sorted(edges.items()):
                bad = [dep['edge_id'] for dep in e.get('depends_on', []) if dep['kind'] == 'HARD_DEPENDENCY' and edges[dep['edge_id']]['applicable'] and states[dep['edge_id']] != 'PASS_SCOPED']
                if e['applicable'] and bad and states[id] not in ['FAIL_OBSERVED', 'HOLD_BLOCKED']:
                    states[id] = 'HOLD_BLOCKED'; reasons[id] = 'Required dependency unresolved: ' + ','.join(sorted(bad)); changed = True
            if not changed: break
        for id, e in sorted(edges.items()):
            out['inspection_state_per_edge'].append({'edge_id': id, 'workface_id': e['workface_id'], 'mandatory': e['mandatory'], 'applicable': e['applicable'], 'state': states[id], 'reason': reasons[id], 'evidence_refs': edge_refs[id], 'history': sorted(observations[id], key=lambda z: (z.get('time', ''), z['receipt_id']))})
            if e['mandatory'] and e['applicable'] and states[id] != 'PASS_SCOPED':
                hold_rows.append({'hold_id': 'UNMET:' + id, 'edge_ids': [id], 'affected_edges': [id], 'reason': reasons[id], 'state': states[id], 'basis': 'Existing required acceptance is unclosed; not a speculative new criterion.'})
        out['remaining_holds'] = sorted(hold_rows, key=lambda z: z['hold_id'])
        for wf in sorted({e['workface_id'] for e in edges.values()} | {x['workface_id']}):
            required = [id for id, e in edges.items() if e['workface_id'] == wf and e['applicable'] and e['mandatory']]
            out['workface_states'].append({'workface_id': wf, 'state': 'LOCAL_HOLD' if any(states[id] != 'PASS_SCOPED' for id in required) else 'READY_FOR_INDEPENDENT_REVIEW', 'required_edge_ids': sorted(required)})
        current = next(r['state'] for r in out['workface_states'] if r['workface_id'] == x['workface_id'])
        if x.get('claimed_inspection_state') == 'PASS_SCOPED' and current != 'READY_FOR_INDEPENDENT_REVIEW':
            error('FALSE_PASS', 'claimed_inspection_state'); out['rejected_claims'].append('PASS_SCOPED')
        if x.get('claimed_final_result') in ['PUBLIC_PASS', 'PUBLIC_RELEASED', 'CANONICAL', 'AUTHORITY_GRANTED']:
            error('AUTHORITY_OR_PUBLIC_PROMOTION_FORBIDDEN', 'claimed_final_result'); out['rejected_claims'].append(x['claimed_final_result'])
        out['evidence_refs'] = sorted(valid_evidence)
        out['final_result'] = 'LOCAL_HOLD' if errors else current
    except (ValueError, TypeError, KeyError, AttributeError) as exc:
        error('CONTRACT_ERROR', str(exc))
        out['final_result'] = 'LOCAL_HOLD'
    out['contract_errors'] = sorted(errors, key=lambda z: (z['code'], z['at']))
    return out
