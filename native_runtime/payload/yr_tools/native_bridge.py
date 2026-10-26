"""Explicit evidence-bound entrance to the retained native dependencies."""
import importlib.util,json,sys
from pathlib import Path
from .binder import need,validate,validate_set,digest,result,guarded,text
REVISION='NATIVE_BOUNDARY_R003_PRIVATE'
PATHS={'root':'root_cause_trace_guard_v1_1/root_cause_trace_guard.py','loop':'foreman_loop_stop_guard_v0_2/foreman_loop_stop_guard.py','next':'next_step_guard_v0_1/next_step_guard.py','work':'workface_split_cost_guard_v1_1/workface_split_cost_guard.py','definition':'superintendent_domain_conflict_yard_v0_2/domain_definition_unification_checker.py','temporal':'superintendent_domain_conflict_yard_v0_2/boundary_revision_temporal_guard.py','routing':'superintendent_domain_conflict_yard_v0_2/routing_cycle_and_hop_limiter.py','human':'human_first_guards_v1_2/guards.py','provisional':'provisional_drawing_issue_registration_guard_v1_1/guard.py','alias':'terminology_alias_guard_v0_1/alias_guard.py','revision':'evidence_revision_guard_v0_1/revision_guard.py','tape':'tape_cut_account_target_binding_guard_v1_1/tape_cut_account_target_binding_guard.py','availability':'human_availability_preservation_guard_v0_1/human_availability_preservation_guard.py','joint':'closure_bundle_joint_r2.py'}
PROGRESS={'PASS_IDENTITY_HANDOFF_EXACT','PASS_WITH_DECLARED_ALIAS','PASS_TAPE_CUT_READY','PASS_ROOT_CAUSE_CLOSED','PASS_SPLIT_JUSTIFIED','SINGLE_WORKFACE_PREFERRED','PASS_NO_HUMAN_INTERRUPT_REQUIRED','PASS_CONTRACT_ONLY','PASS_POST_REGISTRATION_BINDING_ONLY','PASS','PASS_WITH_INFO','CONTINUE_NECESSARY_POSITIVE_VALUE','NEXT_HOP_PERMITTED','PASS_HANDOFF_READY','PASS_DEFINITION_UNIFIED','PASS_BOUNDARY_REVISION_TEMPORAL','PASS_TECHNICAL_READY_HUMAN_ISSUE_REQUEST_BOUND'}
OBSERVATION_ONLY={'PASS_NON_ROOT_CLASSIFICATION','CLOSED_NO_NEXT_STEP','CLOSE_DELIVERABLE_COMPLETE','STOP_LOOP_STAGNATION_HANDOFF','STOP_LOW_MARGINAL_VALUE_HANDOFF','WAIT_RECEIPT','PASS_RETENTION_ONLY','NEXT_STEP_READY','MATCH','CONVERTIBLE','PASS_SINGLE_WORKFACE','WAIT_ISSUE_REQUEST','PASS_SINGLE_HUMAN_DECISION_PACKET_READY','PASS_SINGLE_HUMAN_ACTION_PACKET_READY','DEFER_HUMAN_INTERRUPT_CONTINUE_SAFE_WORK','PASS_HUMAN_EVENT_BINDING_ONLY'}
def module(component):
    need(component in PATHS,'HOLD_COMPONENT_UNKNOWN');p=Path(__file__).resolve().parents[1]/'native'/PATHS[component]
    name='yr_private_native_'+component;s=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(s);sys.modules[name]=m;s.loader.exec_module(m);return m,p
def revision(m):return next((getattr(m,k) for k in ('TOOL_REVISION','PRESENTATION_REVISION','REVISION','TOOL','VERSION') if hasattr(m,k)),None)
def invoke(component,m,data,base,extra):
    if component=='alias':return m.guard_identity_handoff(data['s'],data['t'])
    if component=='human':
        view=m.project(data);o=m.human_first_guard(data,view,m.digest(data));return {**o,'view':view}
    if component=='availability':return m.HumanAvailabilityPreservationGuard().evaluate(data).to_dict()
    if component=='revision':return m.audit(data,Path(base))
    if component=='next':return m.next_step(data)
    if component in {'root','work','provisional'}:
        for k in ('evidence_base','registration_base'):extra.pop(k,None)
        if component=='root':extra['evidence_base']=base
        if component=='work':extra['evidence_base']=base
        if component=='provisional':extra['registration_base']=base
        return m.assess(data,**extra)
    if component=='joint':return m.assess(data['envelope'],data['pin'],base)
    return m.assess(data)
def execute(component,call,pin,base):return guarded(_execute,component,call,pin,base)
def _execute(component,call,pin,base):
    need(call.get('schema')=='yr.native-call/1' and isinstance(call.get('data'),dict),'HOLD_NATIVE_CALL_SCHEMA')
    m,p=module(component);ref=call['input_ref'];subject={'artifact_id':ref['artifact_id'],'revision':ref['revision']}
    validate(ref,pin.get('input'),base,subject,{'native_input':call['data']})
    need(pin.get('component')==component and pin.get('native_revision')==revision(m),'HOLD_NATIVE_REVISION_IDENTITY')
    from .binder import sha
    need(pin.get('native_sha256')==sha(p.read_bytes()),'HOLD_NATIVE_CODE_REVISION')
    refs=call.get('evidence_refs');need(isinstance(refs,list),'HOLD_NATIVE_EVIDENCE_ROSTER')
    validate_set(refs,pin.get('evidence_pins'),base,pin.get('evidence_subjects'))
    tuples=[]
    if component=='alias':tuples=[v.get('revision_identity') for v in (call['data']['s'],call['data']['t']) if v.get('identity_class')=='ARTIFACT']
    if component=='tape':tuples=[call['data']['expected'].get('revision_identity'),call['data']['observed'].get('revision_identity')]
    for identity in tuples:
        need(isinstance(identity,dict) and any(identity=={'artifact_id':r['artifact_id'],'namespace':r['namespace'],'revision':r['revision'],'content_sha256':r['sha256']} for r in refs),'HOLD_ARTIFACT_REVISION_EVIDENCE_UNBOUND')
    extra=dict(call.get('native_extra',{}));need(digest(extra)==pin.get('native_extra_digest'),'HOLD_NATIVE_EXTRA_PIN')
    if component=='human':
        by={r['artifact_id']:validate(r,pin['evidence_pins'][r['artifact_id']],base) for r in refs}
        for e in call['data']['evidence']:
            if e['kind']=='SOURCE_EXCERPT' and e['retained'] is True:need(e['id'] in by and by[e['id']]['bytes'].decode('utf-8')==e['content'],'HOLD_HUMAN_EVIDENCE_BINDING')
    out=invoke(component,m,call['data'],base,extra);v=out.get('verdict',out.get('status',out.get('result')))
    if not text(v) or v not in PROGRESS|OBSERVATION_ONLY:
        return result('HOLD_NATIVE_VERDICT',native_verdict=v,native_output=out,native_revision=revision(m),tool_revision=REVISION,reason_codes=['KNOWN_BLOCKING_NATIVE_STATE' if text(v) and any(s in v for s in ('HOLD','FAIL','REJECT','STOP','BLOCK')) else 'UNKNOWN_VERDICT_HOLD'])
    return result('PASS_NATIVE_CONTRACT_ONLY',native_verdict=v,native_output=out,native_revision=revision(m),native_sha256=pin['native_sha256'],tool_revision=REVISION,input_sha256=ref['sha256'],progress_eligible=v in PROGRESS,retention_only=v in OBSERVATION_ONLY,source_truth='NOT_CERTIFIED')
