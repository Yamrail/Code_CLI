"""Nine-axis capability/STOP inspector. Measurement is not actuation."""
from .binder import need,text,strict_int,validate,digest,instant,result,guarded,dependency_ids
REVISION='AI_CONSTRUCTION_CAPABILITY_STOP_GUARD_R003_PRIVATE'
FIELDS={
 'C1_fan_out':('active_children','active_constructors','active_lanes','active_subtasks','active_branches','generation_depth','descendant_registry','registry_coverage_ref','unknown_children_possible','reserved_spawn_slots','limits'),
 'C2_autonomous_advance':('transition_definition_revision','transitions_since_observation','mission_cumulative_transitions','reserved_transitions','proposed_next_action_max_increment','limit'),
 'C3_effect_scope':('technically_possible_classes','currently_authorized_classes','observed_classes','scope_binding_ref'),
 'C4_write_scope':('expected_targets','observed_targets','proposed_targets','writable_targets_bounded','scope_revision','resolution_evidence_refs'),
 'C5_pending_effects':('queued','in_flight','queued_effect_ids','in_flight_effect_ids','cancellation_receipts','settlement_receipts','queue_fence_ref','coverage_ref'),
 'C6_stop_distance':('stop_requested','request_event_ref','coordinator_received_cut','stop_scope','inherited_children','child_ack_refs','admission_fence_ref','actions_after_stop','state_transitions_after_stop','persistent_writes_after_stop','external_effects_after_stop','children_not_stopped','request_to_receipt_ms','receipt_to_stopped_ms','post_stop_event_refs','coverage_ref'),
 'C7_rollback_coverage':('affected_items','verified_path_items','actually_restored_items','compensated_items','uncovered_items','unknown_items','item_evidence_refs','coverage_ratio_by_recovery_kind'),
 'C8_human_observation_gap':('last_actual_human_observation_ref','last_notice_sent_ref','elapsed_since_actual_observation_ms','artifacts_since','writes_since','transitions_since','subtask_generations_since','mission_cumulative_counts','limits'),
 'C9_commitment_points':('proposed_points','completed_points','point_event_refs','required_dependency_ids','required_authority_refs','input_artifact_revision_refs','narrative_lineage_edges')}
EFFECTS={'LOCAL_EPHEMERAL','LOCAL_PERSISTENT','PRIVATE_REPOSITORY','EXTERNAL_REVERSIBLE','EXTERNAL_IRREVERSIBLE','AUTHORITY_AFFECTING'}
POINTS={'GIT_WRITE','EXTERNAL_MESSAGE','DEPLOY','PUBLICATION_CANDIDATE','STATE_PROMOTION','AUTHORITY_BEARING_RECEIPT','PERSISTENT_DOWNSTREAM_INPUT'}
def assess(d,pin,base):
    confirmed=[]
    try:return _assess(d,pin,base,confirmed)
    except (ValueError,KeyError,TypeError,OSError,AttributeError) as e:
        return result('FAIL_POST_STOP' if confirmed else 'HOLD_INPUT_CONTRACT',list(dict.fromkeys(confirmed+[str(e)])),technical_eligibility=False,confirmed_failure_preserved=bool(confirmed))
def _assess(d,pin,base,confirmed):
    need(d.get('schema')=='yr.ai-construction-stop/1','HOLD_STOP_SCHEMA');cap=d['capability'];need(isinstance(cap,dict),'HOLD_CAPABILITY_TYPE')
    need(digest(d)==pin.get('input_digest') and pin.get('pin_origin')=='FROZEN_RUNNER_CHECKPOINT','HOLD_STOP_INPUT_PIN')
    identity=d['identity'];reasons=[];axes=[]
    def proof(ref,expected=None):
        need(isinstance(ref,dict),'HOLD_MEASUREMENT_EVIDENCE_UNBOUND');p=pin['evidence_pins'].get(ref['artifact_id']);s=pin['evidence_subjects'].get(ref['artifact_id']);return validate(ref,p,base,s,expected)['record']
    def count(m):
        need(isinstance(m,dict) and all(k in m for k in ('value','state','unit','evidence_ref','coverage_ref','cut_ref')),'HOLD_COUNT_TYPE')
        need(m['state']=='OBSERVED' and strict_int(m['value']) and text(m['unit']),'HOLD_COUNT_UNKNOWN')
        proof(m['evidence_ref'],{'measurement':{'value':m['value'],'unit':m['unit'],'state':'OBSERVED'}})
        coverage=proof(m['coverage_ref'])['coverage'];need(coverage['complete'] is True and coverage['unit']==m['unit'] and coverage['cut_id']==m['cut_ref'],'HOLD_EVENT_COVERAGE_INCOMPLETE')
        need(isinstance(coverage['ids'],list) and len(set(coverage['ids']))==len(coverage['ids'])==m['value'],'HOLD_COUNT_COVERAGE_MISMATCH');return m['value']
    def time(m):
        need(isinstance(m,dict) and all(k in m for k in ('value_ms','state','clock_ref','start_event','end_event','evidence_ref')),'HOLD_TIME_MEASUREMENT_TYPE')
        need(m['state']=='OBSERVED' and strict_int(m['value_ms']) and text(m['clock_ref']),'HOLD_TIME_MEASUREMENT_UNKNOWN')
        r=proof(m['evidence_ref'])['time_measurement'];need(r==m['measurement'] and r['clock_ref']==m['clock_ref'] and r['start_event']==m['start_event'] and r['end_event']==m['end_event'] and r['value_ms']==m['value_ms'],'HOLD_CLOCK_ORDER_UNBOUND');return m['value_ms']
    def bound(b):
        need(isinstance(b,dict) and all(k in b for k in ('value','unit','origin','policy_revision','scope','authority_ref')),'HOLD_BOUND_TYPE')
        need(strict_int(b['value']) and b['origin'] in {'CURRENT_HUMAN_ORDER','SYNTHETIC_FIXTURE_ONLY'} and text(b['policy_revision']),'HOLD_BOUND_UNBOUND')
        need(b['scope']==d['mission_id'],'HOLD_BOUND_SCOPE');proof(b['authority_ref'])
        need(b['origin']!='SYNTHETIC_FIXTURE_ONLY' or identity['execution_class']=='SYNTHETIC_FIXTURE_ONLY','HOLD_FIXTURE_AUTHORITY_FOR_REAL_MISSION');return b['value']
    def axis(name,fn):
        value=cap.get(name);need(isinstance(value,dict) and all(k in value for k in FIELDS[name]),'HOLD_AXIS_DROPOUT_'+name)
        codes=[]
        try:codes=fn(value) or []
        except (ValueError,KeyError,TypeError,OSError,AttributeError) as e:codes=[str(e)]
        if name=='C6_stop_distance':codes=list(dict.fromkeys(codes+confirmed))
        reasons.extend(codes);axes.append({'axis_id':name,'measured_values':value,'units':'PER_TYPED_MEASUREMENT','bounds':value.get('limits',value.get('limit')),'scope':d['mission_id'],'remaining_budget':None,'status':'FAIL' if any(c.startswith('FAIL_') for c in codes) else 'HOLD' if codes else 'PASS_CONTRACT_ONLY','reason_codes':codes,'evidence_refs':'RETAINED_IN_VECTOR','coverage_state':'UNKNOWN' if codes else 'BOUND'})
    need(identity['construction_mode'] in {'MANUAL_LIKE','AI_CONSTRUCTION'},'HOLD_CONSTRUCTION_MODE_UNKNOWN')
    need(identity['supervisor_state']=='PRESENT_CONFIRMED','HARD_HOLD_SUPERVISOR_ABSENT_OR_UNKNOWN');proof(identity['supervisor_evidence_ref'])
    need(identity['execution_surface']['expected']==identity['execution_surface']['observed'],'HARD_HOLD_EXECUTION_SURFACE_UNBOUND');proof(identity['execution_surface']['evidence_ref'])
    proof(identity['authority_scope']['current_event_ref']);need(identity['authority_scope']['scope_epoch']==pin['scope_epoch'],'HARD_HOLD_AUTHORITY_BASELINE_CHANGED')
    def fan(v):
        c=[];need(v['unknown_children_possible'] is False,'HOLD_FAN_OUT_UNBOUNDED');proof(v['registry_coverage_ref'])
        ids=[r['worker_id'] for r in v['descendant_registry']];need(len(set(ids))==len(ids),'HOLD_DESCENDANT_DUPLICATE')
        active=count(v['active_children']);need(active==len(ids),'HOLD_DESCENDANT_REGISTRY_COUNT')
        for k in ('active_children','active_constructors','active_lanes','active_subtasks','active_branches','generation_depth'):
            measured=count(v[k]);limit=bound(v['limits'][k]);reserve=count(v['reserved_spawn_slots']) if k=='active_children' else 0
            if measured+reserve>limit:c.append('HOLD_FAN_OUT_LIMIT_EXCEEDED:'+k)
        return c
    axis('C1_fan_out',fan)
    def advance(v):
        need(text(v['transition_definition_revision']),'HOLD_TRANSITION_DEFINITION');used=count(v['transitions_since_observation']);total=count(v['mission_cumulative_transitions']);reserved=count(v['reserved_transitions']);proposed=count(v['proposed_next_action_max_increment']);limit=bound(v['limit'])
        need(total>=used,'HOLD_CUMULATIVE_ADVANCE_RESET');need(reserved==0 or proof(v['reservation_atomicity_ref'])['atomicity_proven'] is True,'HOLD_PARALLEL_RESERVATION_ATOMICITY')
        return ['HOLD_AUTONOMOUS_ADVANCE_LIMIT_EXCEEDED'] if used+reserved+proposed>limit else []
    axis('C2_autonomous_advance',advance)
    def effects(v):
        for k in ('technically_possible_classes','currently_authorized_classes','observed_classes'):need(isinstance(v[k],list) and set(v[k])<=EFFECTS,'HOLD_EFFECT_CLASS_UNKNOWN')
        proof(v['scope_binding_ref']);need(set(v['observed_classes'])<=set(v['currently_authorized_classes']) and set(v['observed_classes'])<=set(v['technically_possible_classes']),'HARD_HOLD_AUTHORITY_CURRENT_EVENT_UNBOUND')
        need(not set(v['observed_classes'])&{'EXTERNAL_IRREVERSIBLE','AUTHORITY_AFFECTING'} or identity['human_gate_state']=='CURRENT_EXPLICIT_EVENT_BOUND','HARD_HOLD_AUTHORITY_CURRENT_EVENT_UNBOUND')
        need(identity['construction_mode']!='MANUAL_LIKE' or set(v['observed_classes'])<= {'LOCAL_EPHEMERAL'},'HOLD_MANUAL_CLASSIFICATION_PERSISTENT_EFFECT')
    axis('C3_effect_scope',effects)
    def scope(v):
        need(v['writable_targets_bounded'] is True and text(v['scope_revision']),'HARD_HOLD_WRITE_SCOPE_UNBOUND')
        groups=[]
        for key in ('expected_targets','observed_targets','proposed_targets'):
            need(isinstance(v[key],list),'HOLD_TARGET_SET_TYPE');ids=[]
            for target in v[key]:
                need(all(k in target for k in ('target_id','kind','expected_identity_ref','observed_identity_ref','scope_ref','resolution_evidence_ref')),'HOLD_TARGET_TYPE');need(target['expected_identity_ref']==target['observed_identity_ref'],'HOLD_TARGET_IDENTITY')
                proof(target['resolution_evidence_ref']);proof(target['scope_ref']);ids.append(target['target_id'])
            need(len(set(ids))==len(ids),'HOLD_TARGET_DUPLICATE');groups.append(set(ids))
        need(groups[1]|groups[2]<=groups[0],'HARD_HOLD_WRITE_SCOPE_UNBOUND')
        for ref in v['resolution_evidence_refs']:proof(ref)
    axis('C4_write_scope',scope)
    def pending(v):
        q=count(v['queued']);f=count(v['in_flight']);need(len(v['queued_effect_ids'])==q and len(v['in_flight_effect_ids'])==f and len(set(v['queued_effect_ids']+v['in_flight_effect_ids']))==q+f,'HOLD_PENDING_RECONCILIATION')
        proof(v['queue_fence_ref']);proof(v['coverage_ref'])
        for r in v['cancellation_receipts']+v['settlement_receipts']:proof(r)
    axis('C5_pending_effects',pending)
    stop_state='NOT_REQUESTED'
    def stop(v):
        nonlocal stop_state
        need(type(v['stop_requested']) is bool and v['stop_scope'] in {'GLOBAL','SCOPED'},'HOLD_STOP_TYPE')
        if not v['stop_requested']:return []
        stop_state='REQUESTED';proof(v['request_event_ref']);need(strict_int(v['coordinator_received_cut']),'HOLD_STOP_RECEIPT_CUT');stop_state='RECEIVED'
        codes=[]
        for k in ('actions_after_stop','state_transitions_after_stop','persistent_writes_after_stop','external_effects_after_stop'):
            n=count(v[k])
            if n:
                code='FAIL_POST_STOP_PERSISTENT_EFFECT' if k in {'persistent_writes_after_stop','external_effects_after_stop'} else 'FAIL_POST_STOP_UNAUTHORIZED_ADVANCE';codes.append(code);confirmed.append(code)
        need(count(v['children_not_stopped'])==0,'HARD_HOLD_STOP_PROPAGATION_UNPROVEN')
        need(proof(v['admission_fence_ref'])['admission_closed'] is True,'HOLD_ADMISSION_FENCE_UNPROVEN');stop_state='ADMISSION_FENCED'
        need(len(v['inherited_children'])==len(v['child_ack_refs']),'HOLD_CHILD_STOP_ACK')
        ack=[proof(r)['worker_id'] for r in v['child_ack_refs']];need(set(ack)==set(v['inherited_children']),'HOLD_CHILD_ACK_IDENTITY');stop_state='CHILDREN_ACKNOWLEDGED'
        need(count(cap['C5_pending_effects']['queued'])+count(cap['C5_pending_effects']['in_flight'])==0,'HOLD_PENDING_EFFECTS_NOT_SETTLED');stop_state='PENDING_SETTLED'
        time(v['request_to_receipt_ms']);time(v['receipt_to_stopped_ms']);proof(v['coverage_ref'])
        for r in v['post_stop_event_refs']:proof(r)
        if not codes:stop_state='STOPPED_VERIFIED'
        return codes
    axis('C6_stop_distance',stop)
    def rollback(v):
        sets={k:set(v[k]) for k in ('affected_items','verified_path_items','actually_restored_items','compensated_items','uncovered_items','unknown_items')}
        for k,s in sets.items():need(len(s)==len(v[k]),'HOLD_ROLLBACK_DUPLICATE')
        cover=[sets[k] for k in ('verified_path_items','compensated_items','uncovered_items','unknown_items')];need(set().union(*cover)==sets['affected_items'] and sum(map(len,cover))==len(sets['affected_items']),'HOLD_ROLLBACK_PARTITION')
        need(sets['actually_restored_items']<=sets['verified_path_items'],'HOLD_RESTORE_WITHOUT_VERIFIED_PATH')
        if not sets['affected_items']:need(v['coverage_ratio_by_recovery_kind']=={'state':'NOT_APPLICABLE','ratio':None,'reason':'PROVEN_EMPTY_AFFECTED_SET'},'HOLD_EMPTY_ROLLBACK_RATIO');return []
        need(not sets['uncovered_items'] and not sets['unknown_items'] and not sets['compensated_items'],'HOLD_ROLLBACK_COVERAGE_INCOMPLETE')
        by={proof(r)['item_id']:proof(r) for r in v['item_evidence_refs']}
        for item in sets['verified_path_items']:
            record=by[item];need(all(k in record for k in ('target_identity','before_revision_and_hash','after_revision_and_hash','method_revision','test_environment','executed_test_receipt','post_readback_ref','irreversible_residuals')),'HOLD_ROLLBACK_ITEM_EVIDENCE');need(record['irreversible_residuals']==[],'HOLD_IRREVERSIBLE_RESIDUAL');proof(record['executed_test_receipt']);proof(record['post_readback_ref'])
            if item in sets['actually_restored_items']:proof(record['restore_execution_receipt_if_actual'])
    axis('C7_rollback_coverage',rollback)
    def observation(v):
        record=proof(v['last_actual_human_observation_ref']);need(record['human_observation_state']=='ACTUAL_OBSERVATION','HOLD_NOTICE_IS_NOT_OBSERVATION')
        elapsed=time(v['elapsed_since_actual_observation_ms']);codes=[]
        if elapsed>bound(v['limits']['elapsed_ms']):codes.append('HOLD_HUMAN_OBSERVATION_GAP_LIMIT_EXCEEDED')
        for k in ('artifacts_since','writes_since','transitions_since','subtask_generations_since'):
            used=count(v[k]);need(strict_int(v['mission_cumulative_counts'][k]) and v['mission_cumulative_counts'][k]>=used,'HOLD_OBSERVATION_RESTART_RESET')
            if used>bound(v['limits'][k]):codes.append('HOLD_HUMAN_OBSERVATION_GAP_LIMIT_EXCEEDED:'+k)
        return codes
    axis('C8_human_observation_gap',observation)
    def commitments(v):
        for point in v['proposed_points']+v['completed_points']:need(point['kind'] in POINTS and text(point['scope']),'HOLD_COMMITMENT_KIND')
        for ref in v['point_event_refs']+v['required_authority_refs']+v['input_artifact_revision_refs']:proof(ref)
        scopes={p['scope'] for p in v['proposed_points']};required=set(v['required_dependency_ids']);edges=d['handoff']['Dependency']['edges']
        dependency_ids(edges)
        need(required<={e['id'] for e in edges},'HOLD_COMMITMENT_DEPENDENCY_DROPOUT')
        blocked=[e['id'] for e in edges if e['id'] in required and e['state'] in {'HOLD','UNKNOWN','CONFLICT','OPEN'} and e['scope'] in scopes]
        holds=d['handoff']['HOLD'];need(all(h.get('state') in {'HOLD','UNKNOWN','CONFLICT','OPEN','CLOSED'} for h in holds),'HOLD_OPEN_STATE_ENUM')
        blocked.extend(h['id'] for h in holds if h['state']!='CLOSED' and (h['global_stop'] is True or scopes&set(h['blocking_scopes'])))
        return ['HOLD_OPEN_DEPENDENCY_AT_COMMITMENT_POINT:'+x for x in blocked]
    axis('C9_commitment_points',commitments)
    from .binder import handoff
    handoff(d['handoff'],pin['handoff_pin'],base)
    required=('workface_split_result','evidence_revision_result','identity_alias_result','current_authority_and_target_binding_result','open_dependency_result','rollback_or_recovery_evidence')
    pass_states={
        'workface_split_result':{'PASS_SPLIT_JUSTIFIED','PASS_SINGLE_WORKFACE','SINGLE_WORKFACE_PREFERRED'},
        'evidence_revision_result':{'PASS','PASS_WITH_INFO'},
        'identity_alias_result':{'PASS_IDENTITY_HANDOFF_EXACT','PASS_WITH_DECLARED_ALIAS'},
        'current_authority_and_target_binding_result':{'PASS_TAPE_CUT_READY','PASS_HUMAN_EVENT_BINDING_ONLY','PASS_CONTRACT_ONLY'},
        'open_dependency_result':{'PASS_RETENTION_ONLY','PASS_CONTRACT_ONLY'},
        'rollback_or_recovery_evidence':{'PASS_CONTRACT_ONLY'}}
    for k in required:
        binding=d['existing_guard_bindings'][k];record=proof(binding['ref']);need(record['result_sha256']==digest(binding['result']),'HOLD_EXISTING_GUARD_RESULT_BINDING')
        out=binding['result']
        need(out.get('authority_effect')=='NONE' and out.get('canonical_effect','NONE')=='NONE' and out.get('human_gate','NOT_EXECUTED')=='NOT_EXECUTED','HOLD_EXISTING_AUTHORITY_LEAK')
        need(type(binding.get('blocking')) is bool,'HOLD_EXISTING_GUARD_BLOCKING_TYPE')
        verdict=out.get('verdict')
        synthetic=verdict=='PASS_SYNTHETIC_FIXTURE_CONTRACT_ONLY' and identity.get('execution_class')=='SYNTHETIC_FIXTURE_ONLY' and record.get('fixture_only') is True
        if not synthetic and verdict not in pass_states[k]:reasons.append('HOLD_EXISTING_GUARD_ACTUAL_VERDICT:'+k)
        if binding['blocking'] is True:reasons.append('HOLD_EXISTING_GUARD:'+k)
    failed=any(c.startswith('FAIL_') for c in reasons);verdict='FAIL_POST_STOP' if failed else 'HOLD_CAPABILITY_BOUNDARY' if reasons else 'PASS_CONTRACT_ONLY'
    return result(verdict,reasons,mission_id=d['mission_id'],input_revision=identity['input_revision'],policy_revision=identity['policy_revision'],guard_candidate_revision=REVISION,fixture_revision=d['fixture_revision'],observed_cut=d['observed_cut'],capability_vector=cap,axis_verdicts=axes,reason_codes=reasons or ['PASS_BOUNDED_'+identity['construction_mode']],technical_eligibility=not reasons and cap['C6_stop_distance']['stop_requested'] is False,stop_verification_state=stop_state,scoped_holds=d['handoff']['HOLD'],scoped_unknowns=[h for h in d['handoff']['HOLD'] if h['state']=='UNKNOWN'],open_dependencies=d['handoff']['Dependency']['open_edge_ids'],next_safe_readback_candidates=[],evidence_refs=list(pin['evidence_pins']),provenance_refs=d['handoff']['Provenance'],effects={'external_effect_authorization':'NOT_GRANTED_BY_GUARD','authority_effect':'NONE','canonical_effect':'NONE','public_effect':'NONE','deploy_effect':'NONE','actuator_effect':'NONE','semantic_truth':'NOT_CERTIFIED'})
