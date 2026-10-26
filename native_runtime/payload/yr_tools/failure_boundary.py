"""Local boundary validator. Failure collection and model connection never send."""
import re
from .binder import need,digest,text,validate,result,guarded,HEX,strict_int
REVISION='AI_AKIHABARA_FAILURE_AND_CONNECTION_BOUNDARY_R002_PRIVATE'
REQUIRED=('packet_schema_version','tool_family','tool_id','tool_revision','parent_revision','component_id','operation_stage_id','rule_id_if_any','failure_class','reason_code','expected_transition','actual_transition','postcondition_state','exit_class','runtime_class','runtime_version','os_class','dependency_versions','sanitized_failure_signature','deterministic_fixture_signature','first_observed_at_coarse','repeatability','local_recovery_attempted','source_revision_identity','worktree_identity_state')
CONNECTION=('provider','endpoint','service_or_model_id','credential_owner','credential_storage_boundary','allowed_operation','external_send_scope','cost_ceiling','timeout_retry_policy','disconnect_control','connection_receipt')
ID=re.compile(r'^[A-Za-z0-9_.-]{1,128}$')
def inspect(d,pin,base):return guarded(_inspect,d,pin,base)
def _inspect(d,pin,base):
    need(digest(d)==pin['input_digest'],'HOLD_FAILURE_INPUT_PIN');need(d['lane'] in {'L0_NORMAL_USE','L1_AUTOMATIC_FAILURE_PATTERN_RETURN','L2_EXPLICIT_DEPOT_REPAIR'},'HOLD_REPAIR_LANE')
    need(d['provider_auto_connect'] is False and d['hidden_fallback'] is False and d['bundled_shared_key'] is False,'HOLD_HIDDEN_PROVIDER_CALL');need(d['free_safety_features']==d['paid_safety_features']==pin['required_safety_features'],'HOLD_FREE_PAID_SAFETY_DIVERGENCE')
    need(d['network_lane_ids']==pin['network_lane_ids'] and len(set(d['network_lane_ids'].values()))==4,'HOLD_NETWORK_LANE_CONFLATION')
    connection=d['provider_connection']
    need(connection['state'] in {'OFF','DISCONNECTED','USER_OWNED_BOUND'},'HOLD_CONNECTION_STATE')
    if connection['state'] in {'OFF','DISCONNECTED'}:need(d['proposed_provider_call'] is False,'HOLD_SEND_AFTER_DISCONNECT')
    else:
        need(all(k in connection for k in CONNECTION),'HOLD_CONNECTION_SCOPE_MISSING');need(connection['credential_owner']==pin['credential_owner'] and connection['external_send_scope']==pin['external_send_scope'],'HOLD_CREDENTIAL_OWNERSHIP_UNKNOWN')
        for key in CONNECTION:
            if key in {'connection_receipt','cost_ceiling','timeout_retry_policy','disconnect_control'}:continue
            need(text(connection[key]),'HOLD_CONNECTION_VALUE_UNKNOWN:'+key)
        from .numeric import number
        need(number(connection['cost_ceiling'])>=0,'HOLD_CONNECTION_COST_UNKNOWN')
        retry=connection['timeout_retry_policy'];need(isinstance(retry,dict) and strict_int(retry.get('timeout_ms'),1) and strict_int(retry.get('max_retries')),'HOLD_CONNECTION_RETRY_UNKNOWN')
        control=connection['disconnect_control'];need(text(control) or isinstance(control,dict) and text(control.get('control_id')) and control.get('state')=='AVAILABLE','HOLD_CONNECTION_DISCONNECT_UNKNOWN')
        ref=connection['connection_receipt'];validate(ref,pin['connection_pin'],base,pin['connection_subject'],{'connection_scope':{k:connection[k] for k in CONNECTION if k!='connection_receipt'}})
    need(d['user_artifact_sha256_before']==d['user_artifact_sha256_after']==pin['user_artifact_sha256'],'HOLD_FAILURE_PACKET_BACKFLOW');need(d['secondary_use']==[],'HOLD_SECONDARY_PERSON_PROFILE_PROHIBITED')
    if d['lane']=='L0_NORMAL_USE':need(d['packet'] is None and d['user_work_collection']=='NONE','HOLD_NORMAL_USE_COLLECTION');return result('PASS_NORMAL_NO_COLLECTION_ONLY',tool_revision=REVISION,provider_state=connection['state'])
    if d['lane']=='L2_EXPLICIT_DEPOT_REPAIR':
        need(d['explicit_user_transfer'] is True,'HOLD_DEPOT_TRANSFER_NOT_EXPLICIT')
        if d['raw_required'] is True:return result('HOLD_RAW_REQUIRED',tool_revision=REVISION)
    packet=d['packet'];need(isinstance(packet,dict) and set(packet)==set(REQUIRED),'HOLD_FAILURE_PACKET_PRIVACY_VIOLATION');need(packet['packet_schema_version']=='YR_FAILURE_PACKET_R001' and packet['tool_revision']==pin['tool_revision'] and packet['source_revision_identity']==pin['source_revision_identity'],'HOLD_FAILURE_PACKET_REVISION_MISMATCH')
    need(type(packet['local_recovery_attempted']) is bool and packet['repeatability'] in {'REPRODUCIBLE','NOT_REPRODUCIBLE','UNKNOWN'},'HOLD_FAILURE_PACKET_TYPE')
    for k,v in packet.items():
        if k in {'sanitized_failure_signature','deterministic_fixture_signature'}:need(isinstance(v,str) and HEX.fullmatch(v),'HOLD_FAILURE_PACKET_PRIVACY_VIOLATION')
        elif k=='dependency_versions':need(isinstance(v,dict) and all(ID.fullmatch(str(a)) and isinstance(b,str) and ID.fullmatch(b) for a,b in v.items()),'HOLD_FAILURE_PACKET_PRIVACY_VIOLATION')
        elif k!='local_recovery_attempted':need(isinstance(v,str) and ID.fullmatch(v),'HOLD_FAILURE_PACKET_PRIVACY_VIOLATION')
    ref=d['failure_event_ref'];validate(ref,pin['failure_event_pin'],base,pin['failure_event_subject'],{'sanitized_packet':packet})
    return result('PASS_MINIMAL_FAILURE_PACKET_LOCAL_ONLY',tool_revision=REVISION,packet_sha256=digest(packet),provider_state=connection['state'],collector_state=d['collector_state'],external_send='NOT_EXECUTED',user_work_unchanged=True)
