"""Typed projection inspection over retained semantic core and durable events."""
from urllib.parse import urlsplit,parse_qsl
import re
from .binder import need,digest,text,validate,result,guarded,strict_int
from .semantic import inspect as semantic_inspect
REVISION='USER_INFORMATION_PROJECTION_GUARD_R001_PRIVATE'
DIMENSIONS={'consumer_kind':{'HUMAN','LLM','MACHINE_AUDITOR'},'work_domain':{'FIELD','ENGINEERING','OSINT','ACADEMIA','AUDIT'},'operational_role':{'OPERATOR','SUPERVISOR','ENGINEER','ANALYST','RESEARCHER','AUDITOR'},'density_preference':{'MINIMAL','OPERATIONAL','DETAILED','FULL'},'urgency':{'NORMAL','CURRENT_TASK_BLOCKED','IMMEDIATE_SAFETY'},'evidence_need':{'SUMMARY','TRACEABLE','REPRODUCIBLE'}}
ANCHORS=('current_task','current_state','next_action','safety_state')
def inspect(d,pin,base):return guarded(_inspect,d,pin,base)
def _inspect(d,pin,base):
    need(pin['input_digest']==digest(d),'HOLD_PROJECTION_INPUT_PIN');ctx=d['context'];need(set(ctx)==set(DIMENSIONS)|{'authority_scope'},'REJECT_SCALARIZATION')
    for k,values in DIMENSIONS.items():need(ctx[k] in values,'HOLD_PROFILE_DIMENSION_'+k)
    need(ctx['authority_scope']['source']=='SEPARATE_RECEIPT_ONLY' and ctx['authority_scope']['value'] in {'NONE','VIEW','APPROVE','RELEASE','OVERRIDE'},'REJECT_AUTHORITY_LEAK')
    authority=d['authority_ref'];r=validate(authority,pin['authority_pin'],base,pin['authority_subject'],{'projection_authority':ctx['authority_scope']})['record'];need(r['projection_authority']==pin['projection_authority'],'REJECT_AUTHORITY_LEAK')
    sem=semantic_inspect(d['semantic_core'],d['projection'],pin['semantic_pins'],base);need(sem['verdict']=='PASS_RELATION_PRESERVATION_ONLY','HOLD_PROJECTION_CONFLICT')
    need(d['anchor_order']==list(ANCHORS) and d['anchors']==pin['anchors'] and d['roundtrip_semantic_digest']==digest(d['semantic_core']),'HOLD_TRANSITION_DISCONTINUITY')
    need(d['canonical_snapshot']==pin['canonical_snapshot'] and set(d['retention_layers'])=={'CANONICAL_EVIDENCE','TELEMETRY','UI_PREFERENCE','ANALYTICS'} and len(set(d['retention_layers'].values()))==4,'REJECT_RETENTION_SCALARIZATION')
    need(d['telemetry_promoted_to_evidence'] is False,'REJECT_RETENTION_SCALARIZATION')
    if d['annoyance_signal']:need(set(d['visible_anchor_ids'])>=set(ANCHORS),'REJECT_COLLAPSE_BELOW_FLOOR')
    need(d['model_runtime_metadata']==pin['observed_model_runtime_metadata'],'REJECT_INVENTED_METADATA')
    if ctx['work_domain'] in {'OSINT','ACADEMIA','AUDIT'}:need(d['domain_value_fields']==pin['domain_value_fields'],'HOLD_DOMAIN_VALUE_ERASURE')
    notice=d['notice'];need(type(notice['human_action_required']) is bool and notice['scope']==pin['notice_scope'],'HOLD_NOTICE_SCOPE')
    if ctx['urgency']=='IMMEDIATE_SAFETY':need(notice['safety_notice_visible'] is True and notice['locked_scopes']==pin['affected_safety_scopes'],'STOP_SAFETY_NOTICE_SUPPRESSED')
    else:need(notice['global_safety_stop'] is False,'REJECT_STATE_COLLAPSE')
    need(notice['modal'] is False or (ctx['urgency']=='IMMEDIATE_SAFETY' or ctx['urgency']=='CURRENT_TASK_BLOCKED' and notice['human_action_required'] is True),'REJECT_INTERRUPTION_MISPLACEMENT')
    need(set(d['enabled_authority_controls'])<=set(pin['permitted_controls']),'REJECT_AUTHORITY_LEAK')
    for locator in d['public_locators']:
        url=urlsplit(locator);need(not url.username and not url.password and not url.fragment,'REJECT_SECRET_BEARING_LOCATOR')
        need(all(k.lower() not in {'token','jwt','key','secret','credential','authorization','access_token','code'} and not re.search(r'eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.',v) for k,v in parse_qsl(url.query)),'REJECT_SECRET_BEARING_LOCATOR')
        need(locator in pin['approved_opaque_locators'],'HOLD_OPAQUE_LOCATOR_UNPROVEN')
    if d['canonical_event'] is not None:
        event=d['canonical_event'];need(all(k in event for k in ('event_id','schema_revision','object_revision','sequence','idempotency_key','timestamp_source','payload_hash')) and strict_int(event['sequence']),'HOLD_DURABILITY_UNPROVEN')
        ref=d['durable_receipt_ref'];record=validate(ref,pin['durable_pin'],base,pin['durable_subject'],{'durable_event':event})['record'];need(record['durable_write_confirmed'] is True,'HOLD_DURABILITY_UNPROVEN')
    return result('PASS_TO_NONCANONICAL_RENDER',tool_revision=REVISION,semantic_digest=digest(d['semantic_core']),anchors=d['anchors'],context=ctx,holds=d['canonical_snapshot']['HOLD'],metadata=d['model_runtime_metadata'],semantic_result=sem,execution_privilege='NOT_GRANTED_BY_PROJECTION')
