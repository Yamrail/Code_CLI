"""Durable work state. Memory is never an input, and replay never authorizes I/O.

Extends the retained R003 binder/recorder joints. Hashes detect corruption against
the frozen checkpoint; they are not an independent witness or tamperproof store.
"""
import copy, datetime, json, os, pathlib
from .reused.binder import canonical, digest, sha, need, ContractError, retained

REVISION='INGRIDGE_WORKSTATE_R004_INTENT_GUARD_R003'
from . import intent_budget as IG
from .shelf_witness import writer_lock,long_path
OPEN={'HOLD','UNKNOWN','CONFLICT','OPEN'}
MILESTONES={
 'ISSUE_REGISTERED':(),
 'GITHUB_STORED':('ISSUE_REGISTERED',),
 'PC_RECEIVED':('GITHUB_STORED',),
 'SOL_ACK':('PC_RECEIVED',),
 'WORK_STARTED':('SOL_ACK',),
 'TESTED':('WORK_STARTED',),
 'GITHUB_INTEGRATION_STORED':('TESTED',),
 'SENDER_READBACK':('GITHUB_INTEGRATION_STORED',),
 'RECEIVER_RECEIVED':('SENDER_READBACK',),
 'SOL_RECEIVER_ACK':('RECEIVER_RECEIVED',),
 'DELIVERED_REVIEW_READY':('SOL_RECEIVER_ACK',),
}
FORBIDDEN={'CANONICAL_PROMOTION','PUBLIC_RELEASE','PRODUCTION_DEPLOYMENT','ADDITIONAL_CHARGE','NEW_EXTERNAL_LLM','HOST_CHANGE','BULK_HOLD_RELEASE'}

def evidence_ref(base,locator,record_class,revision,subject):
    _,raw=retained(base,locator)
    return {'locator':locator,'sha256':sha(raw),'bytes':len(raw),'record_class':record_class,'revision':revision,'subject':subject}

def validate_evidence(base,ref):
    need(isinstance(ref,dict) and ref.get('record_class') in {'SOURCE','OBSERVATION','EXECUTION','AUTHORITY','RECEIPT','DESIGN'},'HOLD_EVIDENCE_CLASS')
    need(bool(ref.get('revision')) and bool(ref.get('subject')),'HOLD_EVIDENCE_REVISION_SUBJECT')
    _,raw=retained(base,ref.get('locator'))
    need(sha(raw)==ref.get('sha256') and len(raw)==ref.get('bytes'),'HOLD_EVIDENCE_BYTES')
    return raw

def validate_plan(base,plan):
    need(plan.get('schema')=='ingridge.workplan/1','HOLD_PLAN_SCHEMA')
    need(plan.get('parent_commit')=='16404870b12c375d3c899113cce46f087e3b1546','HOLD_PARENT_REVISION')
    need(plan.get('authority_effect')=='NONE','HOLD_PLAN_AUTHORITY')
    stages=plan.get('stages',[]);ids=[s['id'] for s in stages]
    need(ids and len(set(ids))==len(ids),'HOLD_STAGE_ID_COLLISION')
    by_id={s['id']:s for s in stages};visiting=set();visited=set()
    def walk(i):
        need(i in by_id and i not in visiting,'HOLD_PLAN_DEPENDENCY_CYCLE_OR_MISSING')
        if i in visited:return
        s=by_id[i];visiting.add(i)
        need(all(k in s for k in ('scope','dependencies','inputs','outputs','joints','required_joints','implementation','exit_criterion','next_if_hold','disposition','required_for_delivery')),'HOLD_STAGE_CONTRACT_MISSING')
        need(s['disposition'] in {'IMPLEMENTED','MATERIAL_GATE_HOLD','REFERENCE_ONLY'},'HOLD_STAGE_DISPOSITION')
        need(s['scope'] and s['exit_criterion'] and isinstance(s['joints'],dict) and type(s['required_for_delivery']) is bool,'HOLD_STAGE_CONTRACT_EMPTY')
        for d in s['dependencies']:walk(d)
        visiting.remove(i);visited.add(i)
    for i in ids:walk(i)
    return by_id

def blocked(state,scope):
    reasons=[]
    for h in state['holds'].values():
        if h['state'] in OPEN and (h.get('global_stop') or set(h['scope']) & set(scope)):reasons.append(h['id'])
    for i,p in state['pending'].items():
        if p['state']!='SETTLED_OBSERVED' and (not p['scope'] or set(p['scope']) & set(scope)):reasons.append('PENDING:'+i)
    return sorted(reasons)

def empty_state(plan):
    return {'schema':'ingridge.workstate/1','revision':REVISION,'plan_digest':digest(plan),'subject':plan['subject'],'parent_commit':plan['parent_commit'],
      'milestones':{},'stages':{s['id']:{'state':'NOT_STARTED','entry':None,'exit':None} for s in plan['stages']},
      'pending':{},'holds':{},'traces':{},'events':{},'epoch':1,'active':False,
      'authority_effect':'NONE','human_acceptance':'NOT_GRANTED','implicit_context':None,'recording_gap':False}

def check_stage(base,stage,state):
    need(stage['disposition']=='IMPLEMENTED','HOLD_STAGE_UNIMPLEMENTED:'+stage['id'])
    need(all(state['stages'][d]['state']=='DONE' for d in stage['dependencies']),'HOLD_STAGE_DEPENDENCY:'+stage['id'])
    need(not blocked(state,stage['scope']),'HOLD_STAGE_SCOPED:'+','.join(blocked(state,stage['scope'])))
    need(stage['implementation'],'HOLD_IMPLEMENTATION_MISSING:'+stage['id'])
    need(set(stage['required_joints'])<=set(stage['joints']),'HOLD_JOINT_MISSING:'+stage['id'])
    for r in stage['implementation']:validate_evidence(base,r)
    for joint,ref in stage['joints'].items():
        need(bool(ref),'HOLD_JOINT_MISSING:'+joint);validate_evidence(base,ref)
    for r in stage['inputs']:validate_evidence(base,r)

def apply_event(base,plan,state,event,intent_context=None):
    out=copy.deepcopy(state);kind=event['kind'];d=event['data'];eid=event['id'];refs=event['evidence']
    need(event['plan_digest']==state['plan_digest'] and event['subject']==state['subject'],'HOLD_EVENT_REVISION_SUBJECT')
    need(event['authority_effect']=='NONE' and event['human_acceptance']=='NOT_GRANTED','HOLD_EVENT_AUTHORITY_ESCALATION')
    need(all(p in state['events'] for p in event['causal_parent_ids']),'HOLD_CAUSAL_PARENT_MISSING')
    for r in refs:validate_evidence(base,r)
    need(refs,'HOLD_EVENT_EVIDENCE_MISSING')
    if plan.get('intent_budget'):
        need(intent_context is not None,'HOLD_INTENT_CONTEXT_REQUIRED')
        IG.apply_before(intent_context,state,event)
        if kind=='EFFECT_SETTLED':IG.validate_actual_refs(base,refs,d,validate_evidence)
    if kind=='RESUME':
        need(d.get('presence')=='CURRENT_CONFIRMED' and d.get('authority_digest')==plan['authority_digest'] and any(r['record_class']=='AUTHORITY' for r in refs),'HOLD_CURRENT_PRESENCE_OR_AUTHORITY')
        need(not out['recording_gap'],'HOLD_RECORDING_GAP');out['active']=True
    elif kind=='STOP':
        out['active']=False;out['epoch']+=1
        for p in out['pending'].values():
            if p['state']!='SETTLED_OBSERVED':p['state']='UNKNOWN_COMPLETION'
        for s in out['stages'].values():
            if s['state']=='ENTERED':s['state']='STOPPED'
    elif kind=='HOLD':
        need(d.get('id') and d.get('state') in OPEN and isinstance(d.get('scope'),list) and (d['scope'] or d.get('global_stop')),'HOLD_HOLD_SCOPE_UNKNOWN')
        need(d.get('reason') and d.get('next') and d['id'] not in out['holds'],'HOLD_HOLD_ID_OR_REASON')
        out['holds'][d['id']]={**copy.deepcopy(d),'evidence':refs,'event':eid}
    elif kind=='RECORDING_GAP':
        out['recording_gap']=True;out['active']=False
    elif kind=='EFFECT_PENDING':
        need(out['active'] and d.get('id') and d['id'] not in out['pending'],'HOLD_EFFECT_START')
        need(d.get('state') in {'QUEUED','IN_FLIGHT'} and d.get('scope') and d.get('effect_revision'),'HOLD_EFFECT_CONTRACT')
        need(d.get('origin_epoch')==out['epoch'],'HOLD_EFFECT_EPOCH')
        out['pending'][d['id']]={**copy.deepcopy(d),'event':eid,'evidence':refs}
    elif kind=='EFFECT_SETTLED':
        need(d['id'] in out['pending'],'HOLD_EFFECT_UNKNOWN');p=out['pending'][d['id']]
        need(out['active'] and d.get('origin_epoch')==p['origin_epoch'] and d.get('effect_revision')==p['effect_revision'] and d.get('scope')==p['scope'],'HOLD_EFFECT_SETTLEMENT_BINDING')
        need(d.get('completion')=='OBSERVED' and any(r['record_class']=='RECEIPT' and r['subject']==d['id'] for r in refs),'HOLD_EFFECT_SETTLEMENT_UNOBSERVED')
        p.update(state='SETTLED_OBSERVED',settlement_event=eid,settlement_evidence=refs)
    elif kind=='MILESTONE':
        name=d['name'];need(name in MILESTONES and name not in out['milestones'],'HOLD_MILESTONE_UNKNOWN_OR_DUPLICATE')
        need(all(p in out['milestones'] for p in MILESTONES[name]),'HOLD_MILESTONE_PREDECESSOR:'+name)
        incoming=name in {'ISSUE_REGISTERED','GITHUB_STORED','PC_RECEIVED','SOL_ACK','WORK_STARTED'}
        required_revision=plan.get('incoming_revision',plan['subject_revision']) if incoming else plan['subject_revision']
        need(d.get('receipt_subject')==plan['subject'] and d.get('payload_revision')==required_revision,'HOLD_MILESTONE_RECEIPT_SUBJECT')
        receipt_rows=[]
        for ref in refs:
            if ref['record_class']=='RECEIPT':
                try:receipt_rows.append(json.loads(validate_evidence(base,ref)))
                except (ValueError,UnicodeError):raise ContractError('HOLD_MILESTONE_RECEIPT_TYPE')
        need(any(row.get('milestone')==name and row.get('binding')==d and row.get('authority_effect')=='NONE' for row in receipt_rows),'HOLD_MILESTONE_RECEIPT_BYTES')
        if name in {'PC_RECEIVED','RECEIVER_RECEIVED'}:
            need(d.get('origin')=='RECEIVER' and d.get('members_match') is True and d.get('immutable_commit') and d.get('manifest_digest'),'HOLD_RECEIVER_QUALIFICATION')
            need(any(r['record_class']=='RECEIPT' for r in refs),'HOLD_RECEIVER_RECEIPT_MISSING')
        if name in {'SOL_ACK','SOL_RECEIVER_ACK'}:need(d.get('origin')=='SOL' and d.get('reconstruction_digest'),'HOLD_SOL_ACK_UNBOUND')
        if name=='WORK_STARTED':need(out['active'] and not out['recording_gap'],'HOLD_START_WITHOUT_CURRENT_PRESENCE')
        if name=='DELIVERED_REVIEW_READY':
            need(d.get('reconstruction_result')=='PASS' and d.get('scoped_remaining_holds_declared') is True,'HOLD_DELIVERY_RECONSTRUCTION')
            need(all(s['state']=='DONE' for i,s in out['stages'].items() if next(x for x in plan['stages'] if x['id']==i)['required_for_delivery']),'HOLD_DELIVERY_REQUIRED_STAGE_INCOMPLETE')
            need(not out['recording_gap'],'HOLD_DELIVERY_RECORD_GAP')
            need(not blocked(out,['DELIVERY']),'HOLD_DELIVERY_PENDING')
        out['milestones'][name]={'event':eid,'receipt':refs,'data':copy.deepcopy(d)}
    elif kind in {'STAGE_ENTER','STAGE_DONE'}:
        need(out['active'] and not out['recording_gap'],'HOLD_STAGE_WITHOUT_CURRENT_PRESENCE')
        need('WORK_STARTED' in out['milestones'],'HOLD_STAGE_BEFORE_WORK_STARTED')
        stage=next((s for s in plan['stages'] if s['id']==d['stage']),None);need(stage is not None,'HOLD_STAGE_UNKNOWN')
        check_stage(base,stage,out);s=out['stages'][stage['id']]
        if kind=='STAGE_ENTER':
            need(s['state'] in {'NOT_STARTED','STOPPED'},'HOLD_STAGE_ENTRY_ORDER');s.update(state='ENTERED',entry=eid,entry_evidence=refs)
        else:
            need(s['state']=='ENTERED','HOLD_STAGE_EXIT_WITHOUT_ENTRY')
            need(d.get('exit_criterion')==stage['exit_criterion'] and d.get('passed') is True,'HOLD_STAGE_EXIT_CRITERION')
            need(stage['outputs'] or stage.get('output_contracts'),'HOLD_STAGE_OUTPUT_MISSING')
            for r in stage['outputs']:validate_evidence(base,r)
            need({r['sha256'] for r in stage['outputs']} <= {r['sha256'] for r in refs},'HOLD_STAGE_OUTPUT_RECEIPT_MISSING')
            for contract in stage.get('output_contracts',[]):
                matching=[r for r in refs if r['locator']==contract['locator'] and r['subject']==contract['subject'] and r['revision']==contract['revision'] and r['record_class']==contract['record_class']]
                need(len(matching)==1,'HOLD_STAGE_OUTPUT_CONTRACT:'+stage['id'])
                observed=json.loads(validate_evidence(base,matching[0]))
                need(all(observed.get(k)==v for k,v in contract['required_result_fields'].items()),'HOLD_STAGE_OUTPUT_CONTRACT_BYTES:'+stage['id'])
            s.update(state='DONE',exit=eid,exit_evidence=refs)
    elif kind=='TRACE':
        need(d.get('id') and d['id'] not in out['traces'],'HOLD_TRACE_ID')
        need(d.get('trace_class') in {'OBSERVED','DERIVATION','HYPOTHESIS'} and d.get('source_cases'),'HOLD_TRACE_CLASS_OR_SOURCE')
        need(all(x in out['traces'] for x in d.get('parent_trace_ids',[])),'HOLD_TRACE_PARENT')
        need(d.get('reason_status') in {'CONTEMPORARY_RECORDED','UNKNOWN','LATER_HYPOTHESIS'},'HOLD_REASON_STATUS')
        need(not(d['reason_status']=='CONTEMPORARY_RECORDED' and not d.get('reason')),'HOLD_REASON_MISSING')
        need(not(d['reason_status']=='LATER_HYPOTHESIS' and d['trace_class']!='HYPOTHESIS'),'HOLD_RETROACTIVE_REASON_PROMOTION')
        out['traces'][d['id']]={**copy.deepcopy(d),'evidence':refs,'event':eid,'authority_effect':'NONE'}
    else:raise ContractError('HOLD_EVENT_KIND_UNKNOWN')
    if plan.get('intent_budget'):IG.apply_after(intent_context,state,out,event)
    out['events'][eid]={'kind':kind,'data':copy.deepcopy(d),'causal_parent_ids':event['causal_parent_ids'],'evidence':refs}
    return out

def replay(base,plan,journal,checkpoint,intent_context=None,fresh_actual_digest=None):
    if plan.get('intent_budget'):
        need(intent_context is not None,'HOLD_INTENT_CONTEXT_REQUIRED')
        intent_context.validate(plan,pathlib.Path(journal).parent)
        intent_context.witness.verify(plan,journal,checkpoint)
    validate_plan(base,plan);state=empty_state(plan);previous='0'*64
    rows=pathlib.Path(journal).read_bytes().splitlines()
    for n,line in enumerate(rows,1):
        e=json.loads(line);observed=e.pop('event_hash')
        need(e['sequence']==n and e['previous_hash']==previous and e['id']==plan['subject']+':'+str(n),'HOLD_WORKSTATE_GAP_FORK_ORDER')
        need(digest(e)==observed,'HOLD_WORKSTATE_EVENT_HASH');previous=observed
        state=apply_event(base,plan,state,e,intent_context)
    need(checkpoint=={'sequence':len(rows),'event_hash':previous,'plan_digest':digest(plan)},'HOLD_WORKSTATE_CHECKPOINT')
    if plan.get('intent_budget'):IG.external_actual_overlay(intent_context,state,fresh_actual_digest)
    return state

class WorkLedger:
    def __init__(self,base,plan,output,intent_context=None):
        self.base=long_path(base) if plan.get('intent_budget') else pathlib.Path(base).resolve();self.plan=copy.deepcopy(plan);validate_plan(base,plan)
        self.intent_context=intent_context
        self.root=long_path(output) if plan.get('intent_budget') else pathlib.Path(output).resolve()
        if plan.get('intent_budget'):
            need(intent_context is not None,'HOLD_INTENT_CONTEXT_REQUIRED')
            intent_context.validate(plan,output)
            intent_context.witness.initialize(plan,sha(intent_context.policy_bytes),output)
        self.root.mkdir(parents=True,exist_ok=False)
        self.journal=self.root/'events.jsonl';self.journal.write_bytes(b'')
        (self.root/'plan.json').write_bytes(canonical(self.plan))
        self.state=empty_state(plan);self.checkpoint={'sequence':0,'event_hash':'0'*64,'plan_digest':digest(plan)}
        (self.root/'checkpoint-000000.json').write_bytes(canonical(self.checkpoint))
    def append(self,kind,data,evidence,causal_parent_ids=()):
        if not self.plan.get('intent_budget'):
            return self._append_locked(kind,data,evidence,causal_parent_ids)
        need(self.intent_context is not None,'HOLD_INTENT_CONTEXT_REQUIRED')
        with writer_lock(self.root,self.intent_context.ledger_id):
            return self._append_locked(kind,data,evidence,causal_parent_ids)
    def _append_locked(self,kind,data,evidence,causal_parent_ids=(),fresh_actual_digest=None):
        # Memory fields are caches only. Every use starts with external replay.
        disk_plan=json.loads((self.root/'plan.json').read_bytes())
        need(digest(self.plan)==digest(disk_plan),'HOLD_PLAN_MEMORY_DIVERGENCE')
        disk_checkpoint=json.loads(sorted(self.root.glob('checkpoint-*.json'))[-1].read_bytes())
        disk_state=replay(self.base,disk_plan,self.journal,disk_checkpoint,self.intent_context,fresh_actual_digest)
        self.state=disk_state;self.checkpoint=disk_checkpoint
        if self.plan.get('intent_budget'):
            data=IG.prepare(self.intent_context,disk_state,disk_checkpoint,kind,data)
        n=disk_checkpoint['sequence']+1
        event={'id':self.plan['subject']+':'+str(n),'sequence':n,'previous_hash':disk_checkpoint['event_hash'],'kind':kind,'data':copy.deepcopy(data),'evidence':copy.deepcopy(evidence),'causal_parent_ids':list(causal_parent_ids),
          'plan_digest':digest(self.plan),'subject':self.plan['subject'],'revision':REVISION,'authority_effect':'NONE','human_acceptance':'NOT_GRANTED',
          'observed_at_host_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'source_time':data.get('source_time'),'clock_domain':'HOST_OBSERVED_NOT_INDEPENDENT_UTC'}
        state=apply_event(self.base,self.plan,disk_state,event,self.intent_context)
        event['event_hash']=digest(event)
        if self.plan.get('intent_budget'):
            self.intent_context.witness.stage(event)
        with self.journal.open('ab') as f:f.write(canonical(event)+b'\n');f.flush();os.fsync(f.fileno())
        checkpoint={'sequence':n,'event_hash':event['event_hash'],'plan_digest':digest(self.plan)}
        with (self.root/('checkpoint-%06d.json'%n)).open('xb') as f:f.write(canonical(checkpoint));f.flush();os.fsync(f.fileno())
        self.checkpoint=checkpoint;self.state=state;return event['id']
    @classmethod
    def open_existing(cls,base,plan,output,intent_context=None):
        if plan.get('intent_budget'):
            need(intent_context is not None,'HOLD_INTENT_CONTEXT_REQUIRED')
            with writer_lock(output,intent_context.ledger_id):
                return cls._open_existing_locked(base,plan,output,intent_context)
        return cls._open_existing_locked(base,plan,output,intent_context)
    @classmethod
    def _open_existing_locked(cls,base,plan,output,intent_context=None):
        self=cls.__new__(cls);self.intent_context=intent_context;self.base=long_path(base) if plan.get('intent_budget') else pathlib.Path(base).resolve();self.plan=copy.deepcopy(plan);self.root=long_path(output) if plan.get('intent_budget') else pathlib.Path(output).resolve();self.journal=self.root/'events.jsonl'
        need(digest(json.loads((self.root/'plan.json').read_bytes()))==digest(self.plan),'HOLD_EXISTING_PLAN_BINDING')
        self.checkpoint=json.loads(sorted(self.root.glob('checkpoint-*.json'))[-1].read_bytes());self.state=replay(base,plan,self.journal,self.checkpoint,intent_context)
        return self

    def bind_purpose(self,purpose_id,root_purpose_id,identity,evidence,parent_purpose_id=None):
        need(self.plan.get('intent_budget'),'HOLD_GUARDED_PLAN_REQUIRED')
        binding={'purpose_id':purpose_id,'root_purpose_id':root_purpose_id,
                 'parent_purpose_id':parent_purpose_id,'identity':copy.deepcopy(identity)}
        return self.append('TRACE',{'id':'PURPOSE:'+purpose_id,'trace_class':'DERIVATION',
            'source_cases':[r['locator'] for r in evidence],'parent_trace_ids':[],
            'reason_status':'CONTEMPORARY_RECORDED','reason':'HOST_ROOT_REGISTRY_AND_EXPLICIT_PURPOSE_LINEAGE',
            'intent_binding':binding},evidence)

    def reserve_attempt(self,attempt_id,purpose_id,root_purpose_id,operation_id,reserved_minor,evidence,approval=None):
        need(self.plan.get('intent_budget'),'HOLD_GUARDED_PLAN_REQUIRED')
        root=self.intent_context.policy['roots'].get(root_purpose_id)
        need(root is not None,'HOLD_ROOT_UNKNOWN')
        data={'id':attempt_id,'state':'IN_FLIGHT','scope':['INTENT_ROOT:'+root_purpose_id],
              'effect_revision':root['operations'][operation_id]['effect_revision'],
              'origin_epoch':self.state['epoch'],'intent_guard':{'purpose_id':purpose_id,
              'root_purpose_id':root_purpose_id,'operation_id':operation_id,'reserved_minor':reserved_minor,
              'currency':root['currency'],'minor_exponent':root['minor_exponent'],'approval':approval}}
        return self.append('EFFECT_PENDING',data,evidence)

    def observe_actual_cost(self,receipt,evidence,observer_class=None,approval=None):
        need(self.plan.get('intent_budget'),'HOLD_GUARDED_PLAN_REQUIRED')
        with writer_lock(self.root,self.intent_context.ledger_id):
            checkpoint=json.loads(sorted(self.root.glob('checkpoint-*.json'))[-1].read_bytes())
            current=replay(self.base,self.plan,self.journal,checkpoint,self.intent_context)
            IG.validate_cost_receipt(self.intent_context,current,receipt)
            IG.validate_actual_refs(self.base,evidence,{'id':receipt['id'],'receipt_binding':receipt},validate_evidence)
            already=self.intent_context.witness.is_observed_receipt(receipt,self.intent_context.environment)
            fresh=None
            if not already:
                allowed='SYNTHETIC_FIXTURE' if self.intent_context.environment=='SYNTHETIC_FIXTURE' else 'HOST_LOCAL_ZERO_COST'
                need(observer_class==allowed,'HOLD_INDEPENDENT_ACTUAL_OBSERVER_REQUIRED')
                need(allowed!='HOST_LOCAL_ZERO_COST' or receipt['actual_minor']==0,'HOLD_PAID_ACTUAL_OBSERVER_UNQUALIFIED')
                # All readers share this lock. A crash after sealing is projected
                # in full by replay and requires Human reconciliation to transfer.
                self.intent_context.witness._retain_actual_receipt_locked(receipt,observer_class)
                fresh=digest(receipt)
            return self._append_locked('TRACE',{'id':'ACTUAL:'+receipt['id']+':'+digest(receipt),
                'trace_class':'OBSERVED','source_cases':[r['locator'] for r in evidence],
                'parent_trace_ids':[],'reason_status':'CONTEMPORARY_RECORDED',
                'reason':'INDEPENDENT_SHELF_ACTUAL_OBSERVATION_NOT_SETTLEMENT_AUTHORITY',
                'cost_observation':copy.deepcopy(receipt),'intent_guard':{'approval':approval}},evidence,
                fresh_actual_digest=fresh)

    def settle_attempt(self,attempt_id,actual_minor,currency,receipt,evidence,approval=None):
        need(self.plan.get('intent_budget'),'HOLD_GUARDED_PLAN_REQUIRED')
        # Cached data is checked again by native append replay under its OS lock.
        pending=self.state['pending'].get(attempt_id)
        need(pending is not None,'HOLD_EFFECT_UNKNOWN')
        guard=pending['intent_guard']
        data={'id':attempt_id,'origin_epoch':pending['origin_epoch'],
              'effect_revision':pending['effect_revision'],'scope':pending['scope'],
              'completion':'OBSERVED','actual_minor':actual_minor,'currency':currency,
              'minor_exponent':guard['minor_exponent'],'receipt_binding':copy.deepcopy(receipt),
              'intent_guard':{'purpose_id':guard['purpose_id'],'root_purpose_id':guard['root_purpose_id'],
                              'currency':currency,'minor_exponent':guard['minor_exponent'],'approval':approval}}
        return self.append('EFFECT_SETTLED',data,evidence)

    @classmethod
    def reconcile_stopped(cls,base,plan,output,intent_context,approval,evidence):
        """Exact Human-authorized restoration only; preserves corrupt bytes first."""
        import shutil
        need(plan.get('intent_budget') and intent_context is not None,'HOLD_INTENT_CONTEXT_REQUIRED')
        root=long_path(output);intent_context.validate(plan,root)
        with writer_lock(root,intent_context.ledger_id):
            anchor=intent_context.witness.latest()
            event_bytes=b''.join(canonical(e)+b'\n' for e in intent_context.witness.events())
            binding={'journal_sha256':sha(event_bytes),'plan_digest':digest(plan),'restore_state':'STOPPED_UNKNOWN'}
            scope=intent_context.approval_scope('RECONCILE_STOPPED','ALL',None,binding,anchor)
            at=intent_context.now();intent_context.check_approval(approval,scope,at)
            intent_context.witness.consume_recovery(approval,anchor,at)
            backup=root.parent/('recovery-preserved-'+sha((root/'events.jsonl').read_bytes())[:24]+'-'+sha(canonical(approval))[:12])
            need(not backup.exists(),'HOLD_RECOVERY_BACKUP_COLLISION')
            shutil.copytree(root,backup)
            with (root/'events.jsonl').open('wb') as stream:stream.write(event_bytes);stream.flush();os.fsync(stream.fileno())
            checkpoint_path=root/('checkpoint-%06d.json'%anchor['sequence'])
            # Original checkpoint bytes survive in the create-only backup.
            with checkpoint_path.open('wb') as stream:stream.write(canonical(anchor));stream.flush();os.fsync(stream.fileno())
            stale=[p for p in root.glob('checkpoint-*.json') if int(p.stem.split('-')[1])>anchor['sequence']]
            need(not stale,'HOLD_EXTERNAL_ROLLBACK_NOT_AUTHORIZED')
            ledger=cls._open_existing_locked(base,plan,root,intent_context)
            ledger._append_locked('STOP',{'reason':'HUMAN_AUTHORIZED_EXACT_RECONCILIATION','approval_receipt_id':approval['payload']['approval_id']},evidence)
            return ledger


def reconstruction(base,plan,journal,checkpoint,intent_context=None):
    state=replay(base,plan,journal,checkpoint,intent_context)
    done=[];unfinished=[];next_steps=[]
    for s in plan['stages']:
        status=state['stages'][s['id']]['state'];row={'id':s['id'],'state':status,'scope':s['scope'],'exit_criterion':s['exit_criterion'],'entry':state['stages'][s['id']]['entry'],'exit':state['stages'][s['id']]['exit']}
        if status=='DONE':done.append(row);continue
        reasons=blocked(state,s['scope'])
        if s['disposition']!='IMPLEMENTED':reasons.append(s['disposition'])
        missing=[d for d in s['dependencies'] if state['stages'][d]['state']!='DONE']
        row.update(blockers=reasons,unfinished_dependencies=missing,required_action=s['next_if_hold']);unfinished.append(row)
        if reasons or missing:next_steps.append({'id':s['id'],'action':s['next_if_hold'],'blocked_by':reasons+missing})
        else:next_steps.append({'id':s['id'],'action':'RECONFIRM_CURRENT_PRESENCE_AND_AUTHORITY_THEN_ENTER','blocked_by':[]})
    return {'schema':'ingridge.reconstruction/1','parent_commit':plan['parent_commit'],'subject':plan['subject'],'plan_digest':digest(plan),'checkpoint':checkpoint,
      'done':done,'unfinished':unfinished,'next':next_steps,'holds':state['holds'],'pending':state['pending'],'milestones':state['milestones'],'traces':state['traces'],
      'model_memory_used':False,'chat_history_used':False,'user_zip_used':False,'authority_inherited':False,'execution_permitted_by_reconstruction':False,
      'intent_root_buckets':IG.projection(state,intent_context) if plan.get('intent_budget') else None,
      'last_recorded_active':state['active'],'presence':'RECONFIRM_BEFORE_NEW_EXECUTION','authority_effect':'NONE','human_acceptance':'NOT_GRANTED'}
