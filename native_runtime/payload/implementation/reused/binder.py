"""Common retained-byte, subject, Revision, epoch and provenance binding."""
import hashlib,json,re
from datetime import datetime,timezone
from pathlib import Path

REVISION='COMMON_BINDER_VALIDATOR_R002_PRIVATE';SCHEMA='yr.binding/1'
IDENTITY=('artifact_id','namespace','revision','sha256','parent_commit','scope_epoch','provenance_id','record_class')
HEX=re.compile(r'^[0-9a-f]{64}$')
class ContractError(ValueError):pass
def need(ok,reason):
    if not ok:raise ContractError(reason)
def canonical(d):return json.dumps(d,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf-8')
def sha(b):return hashlib.sha256(b).hexdigest()
def digest(d):return sha(canonical(d))
def text(v):return isinstance(v,str) and bool(v.strip())
def strict_int(v,minimum=0):return type(v) is int and v>=minimum
def instant(v):
    need(text(v),'HOLD_TIME_UNKNOWN')
    try:t=datetime.fromisoformat(v.replace('Z','+00:00'))
    except ValueError:raise ContractError('HOLD_TIME_TYPE')
    need(t.tzinfo is not None and t.utcoffset() is not None,'HOLD_TIMEZONE_UNKNOWN')
    return t.astimezone(timezone.utc)
def time_chain(t,keys):
    values=[instant(t[k]) for k in keys];need(values==sorted(values),'HOLD_TIME_REVERSAL');return values
def no_authority(d):
    need(d.get('authority_effect')=='NONE' and d.get('canonical_effect')=='NONE','HOLD_AUTHORITY_ESCALATION')
    need(d.get('human_gate','NOT_EXECUTED')=='NOT_EXECUTED','HOLD_HUMAN_GATE_SUBSTITUTION')
def retained(base,locator):
    need(text(locator),'HOLD_LOCATOR_UNKNOWN');root=Path(base).resolve();p=(root/locator).resolve()
    need(p.is_relative_to(root) and p.is_file(),'HOLD_REFERENCED_OBJECT_UNBOUND')
    return p,p.read_bytes()
def dependency_ids(edges):
    need(isinstance(edges,list),'HOLD_DEPENDENCY_TYPE')
    ids=[];open_ids=[]
    for edge in edges:
        need(isinstance(edge,dict) and text(edge.get('id')),'HOLD_DEPENDENCY_EDGE_TYPE')
        need(edge.get('state') in {'HOLD','UNKNOWN','CONFLICT','OPEN','CLOSED','RESOLVED','NOT_APPLICABLE'},'HOLD_DEPENDENCY_STATE_UNKNOWN')
        ids.append(edge['id'])
        if edge['state'] in {'HOLD','UNKNOWN','CONFLICT','OPEN'}:open_ids.append(edge['id'])
    need(len(set(ids))==len(ids),'HOLD_DEPENDENCY_EDGE_COLLISION')
    return open_ids
def validate(ref,pin,base,expected_subject=None,expected_record=None):
    need(isinstance(ref,dict) and isinstance(pin,dict),'HOLD_BINDING_TYPE')
    need(ref.get('schema')==pin.get('schema')==SCHEMA,'HOLD_BINDING_SCHEMA')
    need(pin.get('pin_origin')=='FROZEN_RUNNER_CHECKPOINT','HOLD_SEPARATE_PIN_UNBOUND')
    for k in IDENTITY:
        need(text(ref.get(k)) and ref.get(k)==pin.get(k),'HOLD_BINDING_'+k.upper())
    need(HEX.fullmatch(ref['sha256']) is not None,'HOLD_HASH_TYPE')
    p,b=retained(base,ref.get('locator'));need(sha(b)==ref['sha256'],'HOLD_EVIDENCE_HASH')
    need(ref['record_class'] in {'SOURCE','OBSERVATION','EXECUTION','DESIGN','AUTHORITY','RECEIPT'},'HOLD_RECORD_CLASS')
    observed=None
    if expected_subject is not None or expected_record is not None:
        try:observed=json.loads(b)
        except (ValueError,UnicodeError):raise ContractError('HOLD_EVIDENCE_RECORD_TYPE')
        need(isinstance(observed,dict),'HOLD_EVIDENCE_RECORD_TYPE')
        need(observed.get('subject')==expected_subject,'HOLD_RECEIPT_SUBJECT_MISMATCH')
        for k in ('parent_commit','scope_epoch','provenance_id'):
            need(observed.get(k)==pin[k],'HOLD_RECORD_'+k.upper())
        no_authority(observed)
        if expected_record is not None:
            need(all(k in observed and observed[k]==v for k,v in expected_record.items()),'HOLD_EVIDENCE_CLAIM_MISMATCH')
    return {'ref':dict(ref),'path':str(p),'bytes':b,'record':observed,'binding_state':'BOUND_OBSERVATION_ONLY'}
def validate_set(refs,pins,base,subjects=None):
    need(isinstance(refs,list) and isinstance(pins,dict),'HOLD_EVIDENCE_SET_TYPE')
    ids=[r.get('artifact_id') for r in refs if isinstance(r,dict)]
    need(len(ids)==len(refs) and len(set(ids))==len(ids),'HOLD_EVIDENCE_ID_COLLISION')
    return [validate(r,pins.get(r['artifact_id']),base,(subjects or {}).get(r['artifact_id'])) for r in refs]
def handoff(packet,pin,base):
    fields=('Revision','Evidence','Authority','HOLD','TimeAnchor','Dependency','Provenance')
    need(isinstance(packet,dict) and isinstance(pin,dict),'HOLD_HANDOFF_TYPE')
    need(pin.get('pin_origin')=='FROZEN_RUNNER_CHECKPOINT','HOLD_CHECKPOINT_ORIGIN')
    for k in fields:need(k in packet and k in pin and digest(packet[k])==digest(pin[k]),'HOLD_HANDOFF_'+k.upper())
    rev=packet['Revision'];need(all(text(rev.get(k)) for k in ('artifact_id','namespace','revision','source_revision','source_sha256')),'HOLD_REVISION_IDENTITY')
    _,raw=retained(base,rev['source_locator']);need(sha(raw)==rev['source_sha256'],'HOLD_SOURCE_REVISION_HASH')
    authority=packet['Authority'];no_authority(authority)
    need(authority.get('parent_commit')==rev['source_revision'] and text(authority.get('scope_epoch')),'HOLD_AUTHORITY_EPOCH')
    need(isinstance(packet['HOLD'],list),'HOLD_OPEN_REGISTER_TYPE')
    for h in packet['HOLD']:
        need(isinstance(h,dict) and h.get('state') in {'HOLD','UNKNOWN','CONFLICT','OPEN','CLOSED'} and isinstance(h.get('blocking_scopes'),list) and type(h.get('global_stop')) is bool,'HOLD_OPEN_STATE_TYPE')
    time_chain(packet['TimeAnchor'],('retrieval_time','execution_time','receipt_time'))
    dep=packet['Dependency'];need(isinstance(dep.get('edges'),list) and isinstance(dep.get('open_edge_ids'),list),'HOLD_DEPENDENCY_TYPE')
    need(type(dep.get('case_closed')) is bool,'HOLD_DEPENDENCY_CLOSURE_TYPE')
    observed_open=dependency_ids(dep['edges'])
    need(len(set(dep['open_edge_ids']))==len(dep['open_edge_ids']) and set(dep['open_edge_ids'])==set(observed_open),'HOLD_DEPENDENCY_OPEN_EDGE_LOSS')
    need(not (dep['case_closed'] and observed_open),'HOLD_CLOSED_WITH_OPEN_EDGE')
    _,graph=retained(base,dep['locator']);need(sha(graph)==dep['sha256'],'HOLD_DEPENDENCY_HASH')
    need(json.loads(graph)['edges']==dep['edges'],'HOLD_DEPENDENCY_EDGE_LOSS')
    prov=packet['Provenance'];_,raw=retained(base,prov['locator']);need(sha(raw)==prov['sha256'],'HOLD_PROVENANCE_HASH')
    known={s['source_id'] for s in json.loads(raw)['sources']};need(set(prov['source_ids'])<=known,'HOLD_PROVENANCE_SOURCE')
    validate_set(packet['Evidence'],pin['evidence_pins'],base,pin.get('evidence_subjects'))
    return True
def result(verdict,reasons=(),**data):
    return {'verdict':verdict,'reasons':list(reasons),'authority_effect':'NONE','canonical_effect':'NONE','human_gate':'NOT_EXECUTED','external_effect_allowed':False,**data}
def guarded(fn,*args,**kwargs):
    try:return fn(*args,**kwargs)
    except (ContractError,KeyError,TypeError,ValueError,OSError,AttributeError,OverflowError) as e:return result('HOLD_INPUT_CONTRACT',[str(e)])
