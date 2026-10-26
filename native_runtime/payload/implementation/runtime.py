"""Private synthetic procedure executor. Not an OS sandbox or LLM runtime."""
import copy, datetime, json, multiprocessing as mp, pathlib, time, uuid
from .reused.binder import canonical, digest, sha, need, ContractError

REVISION = 'INGRIDGE_INTEGRATED_SUPERVISOR_R004'
EDGES = {'HARD_DEPENDENCY','VERSIONED_BINDING','CURRENT_ROUTE_ONLY','UNKNOWN_HOLD','BLOCKS','PARALLEL_CANDIDATE','REVIEW_FEEDBACK'}
OPEN = {'HOLD','UNKNOWN','CONFLICT','OPEN'}
STAGES = ['PREFLIGHT','BOOT','BIND','RUN','INSPECT','PERSIST','ISSUE','QUIESCE','TEARDOWN','NEXT_BOOT']

def write_new(path, value):
    path=pathlib.Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('xb') as f: f.write(canonical(value))

def recorder_main(connection, path, max_bytes):
    """Separate process: append receipt before acknowledging. No Worker writes."""
    count=0;previous='0'*64;used=0
    with pathlib.Path(path).open('xb') as f:
        connection.send({'ready':True,'pid':__import__('os').getpid()})
        while True:
            message=connection.recv()
            if message is None: break
            try:
                count+=1
                event={**message,'sequence':count,'previous_hash':previous}
                event['event_hash']=digest(event);raw=canonical(event)+b'\n'
                if used+len(raw)>max_bytes:
                    connection.send({'error':'HOLD_RECORDER_LOG_CAPACITY'});break
                f.write(raw);f.flush();__import__('os').fsync(f.fileno())
                used+=len(raw);previous=event['event_hash']
                connection.send({'sequence':count,'event_hash':previous,'bytes':used})
            except (OSError,ValueError) as e:
                connection.send({'error':'HOLD_RECORDER_WRITE:'+str(e)});break

def inspect_log(path, checkpoint):
    previous='0'*64;events=[]
    try:
        for seq,line in enumerate(pathlib.Path(path).read_bytes().splitlines(),1):
            e=json.loads(line);observed=e.pop('event_hash')
            need(e['sequence']==seq and e['previous_hash']==previous,'HOLD_FDR_GAP_FORK_ORDER')
            need(digest(e)==observed,'HOLD_FDR_TAMPER')
            e['event_hash']=observed;previous=observed;events.append(e)
        need(bool(events) and len(events)==checkpoint['sequence'] and previous==checkpoint['event_hash'],'HOLD_FDR_TRUNCATION_OR_CHECKPOINT')
        return {'verdict':'PASS_DECLARED_FDR_SCOPE','count':len(events),'last_hash':previous}
    except (ContractError,ValueError,KeyError,OSError) as e:
        return {'verdict':'HOLD','reason':str(e)}

def dependency_check(board, operation):
    nodes={n['moot_id']:n for n in board['moots']};edges=board['edges'];reasons=[]
    need(len(nodes)==len(board['moots']),'HOLD_MOOT_ID_COLLISION')
    need(len({e['edge_id'] for e in edges})==len(edges),'HOLD_EDGE_COLLISION')
    adjacency={n:[] for n in nodes}
    for e in edges:
        need(e['type'] in EDGES,'HOLD_EDGE_TYPE')
        need(e['source'] in nodes and e['target'] in nodes,'HOLD_UNRESOLVED_REFERENCE')
        if e['type'] in {'HARD_DEPENDENCY','VERSIONED_BINDING'}:
            adjacency[e['target']].append(e['source'])
    visiting=set();visited=set()
    def walk(n):
        need(n not in visiting,'HOLD_DEPENDENCY_CYCLE')
        if n in visited:return
        visiting.add(n)
        for p in adjacency[n]:walk(p)
        visiting.remove(n);visited.add(n)
    need(operation in nodes,'HOLD_OPERATION_UNKNOWN');walk(operation)
    if nodes[operation]['status'] in OPEN:reasons.append('HOLD_OPERATION_STATE:'+operation)
    # Only edges in the required ancestry of this operation block it.
    for e in edges:
        if e['target'] not in visited:continue
        relevant=e['type'] in {'HARD_DEPENDENCY','VERSIONED_BINDING','UNKNOWN_HOLD','BLOCKS'}
        relevant=relevant or (e['type']=='CURRENT_ROUTE_ONLY' and operation in e['operation_scope'])
        if not relevant:continue
        source=nodes[e['source']]
        if e['state'] in OPEN or source['status'] in OPEN:reasons.append('HOLD_EDGE:'+e['edge_id'])
        if e['required_revision'] is not None and source['revision']!=e['required_revision']:reasons.append('HOLD_REVISION:'+e['edge_id'])
        if source.get('case_closed') and any(x['target']==source['moot_id'] and x['type']=='HARD_DEPENDENCY' and x['state'] in OPEN for x in edges):reasons.append('HOLD_FALSE_CLOSURE:'+source['moot_id'])
    return {'allowed':not reasons,'reasons':reasons,'required_nodes':sorted(visited)}

def cache_rebind(metadata, expected):
    keys=('artifact_identity','revision','purpose','subject_scope','principal_tenant_scope','policy_revision','environment','validity')
    need(all(k in metadata and k in expected for k in keys),'HOLD_CACHE_METADATA_MISSING')
    need(all(metadata[k]==expected[k] for k in keys),'HOLD_CACHE_SCOPE_OR_REVISION')
    need(metadata['validity']=='VALID' and metadata.get('revoked') is False,'HOLD_CACHE_EXPIRED_OR_REVOKED')
    need(metadata.get('license_state')=='SYNTHETIC_SELF_CREATED','HOLD_CACHE_PERMISSION')
    return {'verdict':'PASS_CACHE_SCOPE_ONLY','key':digest({k:metadata[k] for k in keys})}

def tool_check(raw, qualification, base):
    need(bool(raw),'HOLD_EMPTY_TOOL')
    need(qualification.get('sha256')==sha(raw),'HOLD_TOOL_HASH')
    need(qualification.get('environment')=='SYNTHETIC_PRIVATE','HOLD_TOOL_QUALIFICATION')
    root=pathlib.Path(base).resolve();p=(root/qualification.get('test_receipt_ref','MISSING')).resolve()
    need(p.is_relative_to(root) and p.is_file(),'HOLD_TOOL_RECEIPT_MISSING')
    receipt=json.loads(p.read_text(encoding='utf-8'))
    need(digest(receipt)==qualification.get('test_receipt_digest') and receipt.get('tool_sha256')==sha(raw) and receipt.get('exit_code')==0 and receipt.get('stdout')=='7\n' and receipt.get('origin')=='ACTUAL_LOCAL_SYNTHETIC_TOOL_EXECUTION','HOLD_TOOL_TEST_BINDING')
    return True

def approval_check(subject, approval):
    fields=('subject_id','revision','digest','scope')
    need(all(subject.get(k) is not None and subject[k]==approval.get(k) for k in fields),'HOLD_APPROVAL_SUBJECT')
    need(approval.get('decision')=='APPROVE' and approval.get('authority_ref')=='SYNTHETIC_TEST_ONLY','HOLD_APPROVAL_AUTHORITY')
    return {'verdict':'PASS_SYNTHETIC_BINDING_ONLY','human_approval':'NOT_GRANTED'}

def numeric_check(claim, rule):
    need(claim['unit']==rule['unit'],'NCR_UNIT_MISMATCH')
    need(claim['tolerance_origin']==rule['origin'] and rule['origin']=='SYNTHETIC_FIXTURE','NCR_TOLERANCE_ORIGIN')
    need(claim['evidence_ref'] in rule['evidence_refs'],'NCR_CLAIM_EVIDENCE')
    need(type(claim['value']) in {int,float} and abs(claim['value']-rule['nominal'])<=rule['tolerance'],'NCR_NUMERIC_RANGE')
    return True

class Supervisor:
    def __init__(self, root, board, authority, budget=None):
        self.root=pathlib.Path(root).resolve();self.root.mkdir(parents=True,exist_ok=False)
        self.board=copy.deepcopy(board);self.authority=copy.deepcopy(authority)
        self.budget=budget or {'log_bytes':2000000,'input_bytes':65536,'operation_seconds':3}
        self.run_id=uuid.uuid4().hex;self.epoch=1;self.active=False;self.state='PREFLIGHT'
        self.pending={};self.acquired={};self.admitted=set();self.delivered={};self.held=[];self.protection_active=True
        self.contents={};self.deliveries={};self.acquisition_sequence=0
        self.checkpoint={'sequence':0,'event_hash':'0'*64};self.recorder=None;self.pipe=None;self.recording_gap=False
        self.authority_pin=digest(self.authority);self.generation=0;self.input_bytes=0;self.started=time.perf_counter()
    def boot(self):
        need(self.authority['supervisor']=='PRESENT_CONFIRMED','HOLD_SUPERVISOR_ABSENT')
        parent,child=mp.get_context('spawn').Pipe()
        self.recorder=mp.get_context('spawn').Process(target=recorder_main,args=(child,str(self.root/'events.jsonl'),self.budget['log_bytes']),daemon=True)
        self.recorder.start();child.close();self.pipe=parent
        need(parent.poll(3),'HOLD_RECORDER_BOOT_TIMEOUT');ready=parent.recv();need(ready.get('ready'),'HOLD_RECORDER_BOOT')
        self.recorder_pid=ready['pid'];self.active=True;self.state='BOOT';self.record('BOOT',{'recorder_pid':self.recorder_pid,'recorder_precedes_broker':True});return self
    def record(self, event_type, details, source_time=None):
        if not self.recorder or not self.recorder.is_alive():
            self.active=False;self.recording_gap=True;raise ContractError('HOLD_FDR_UNAVAILABLE')
        now=datetime.datetime.now(datetime.timezone.utc).isoformat()
        event={'event_id':self.run_id+':'+str(self.checkpoint['sequence']+1),'run_id':self.run_id,'session_epoch':self.epoch,'event_type':event_type,'source_time':source_time,'observed_time':now,'received_time':now,'monotonic_ns':time.monotonic_ns(),'clock_domain':'HOST_OBSERVED_NOT_INDEPENDENT_UTC','causal_parent_ids':details.get('causal_parent_ids',[]),'record_order_predecessor':self.run_id+':'+str(self.checkpoint['sequence']) if self.checkpoint['sequence'] else None,'unrecorded_cause':'UNKNOWN_NOT_INFERRED_FROM_TIME_OR_ORDER','tool_revision':REVISION,'authority_ref':'CURRENT_USER_SCOPE_PRIVATE_ONLY','details':details}
        try:
            self.pipe.send(event);need(self.pipe.poll(3),'HOLD_RECORDER_ACK_TIMEOUT');ack=self.pipe.recv()
            need('error' not in ack,ack.get('error','HOLD_RECORDER_ERROR'))
            self.checkpoint=ack
            # Independent supervisor checkpoint path, not the recorder's own log.
            write_new(self.root/'checkpoints'/('%06d.json'%ack['sequence']),ack)
            return event['event_id']
        except (OSError,EOFError,ContractError):self.active=False;self.recording_gap=True;raise
    def preuse(self, operation, epoch, permit=None):
        need(self.active and epoch==self.epoch,'HOLD_CANCELLED_EPOCH')
        need(digest(self.authority)==self.authority_pin,'HOLD_AUTHORITY_CHANGED')
        need(self.authority['supervisor']=='PRESENT_CONFIRMED','HOLD_SUPERVISOR_ABSENT')
        need(self.authority['purpose_bound'],'HOLD_PURPOSE_UNBOUND')
        check=dependency_check(self.board,operation);need(check['allowed'],';'.join(check['reasons']))
        need(not self.recording_gap,'HOLD_OBSERVED_RECORDING_GAP')
        for effect_id,effect in self.pending.items():
            need(isinstance(effect,dict) and isinstance(effect.get('scope'),list) and bool(effect['scope']),'HOLD_PENDING_SCOPE_UNKNOWN:'+effect_id)
            need(effect.get('state') in {'QUEUED','IN_FLIGHT','UNKNOWN_COMPLETION','SETTLED_OBSERVED'},'HOLD_PENDING_STATE_UNKNOWN:'+effect_id)
            if effect['state']!='SETTLED_OBSERVED' and set(effect['scope']) & set(check['required_nodes']):
                raise ContractError('HOLD_PENDING_UNRESOLVED:'+effect_id)
        for hold in self.held:
            if hold.get('state') in OPEN:
                scope=hold.get('scope');need(isinstance(scope,list) and scope,'HOLD_SCOPE_UNKNOWN')
                need(not set(scope) & set(check['required_nodes']),'HOLD_RETAINED:'+hold['id'])
        if permit is not None:need(permit['operation']==operation and permit['board_digest']==digest(self.board) and permit['authority_digest']==digest(self.authority) and permit['epoch']==epoch,'HOLD_TOCTOU_CHANGED')
        return check
    def bind(self,operation):
        self.preuse(operation,self.epoch);self.state='BIND'
        permit={'operation':operation,'epoch':self.epoch,'board_digest':digest(self.board),'authority_digest':digest(self.authority)}
        self.record('BIND',permit);return permit
    def acquire_local(self,operation,relative,permit=None):
        self.preuse(operation,self.epoch,permit);self.state='RUN'
        self.record('REQUESTED',{'operation_id':operation,'adapter':'local_file','relative':relative})
        path=(self.root/'inputs'/relative).resolve();need(path.is_relative_to((self.root/'inputs').resolve()),'HOLD_PATH_ESCAPE')
        need(path.is_file() and not path.is_symlink(),'HOLD_INPUT_NOT_REGULAR')
        need(path.stat().st_size<=self.budget['input_bytes'],'HOLD_INPUT_CAPACITY')
        self.record('POLICY_ALLOW',{'operation_id':operation,'rule':'SYNTHETIC_INPUT_ROOT_ONLY'})
        raw=path.read_bytes();self.input_bytes+=len(raw)
        return self._acquire_occurrence(operation,raw,'local_file',relative,'LOCAL_SYNTHETIC_BYTES')
    def _acquire_occurrence(self,operation,raw,adapter,locator,source_revision):
        self.acquisition_sequence+=1
        identity=self.run_id+':acq:'+str(self.acquisition_sequence);content_id=sha(raw)
        event=self.record('ACQUIRED',{'artifact_id':identity,'acquisition_occurrence':identity,'content_id':content_id,'operation':operation,'source_locator':locator,'source_revision':source_revision,'bytes':len(raw),'adapter':adapter,'dedup_reuses_bytes_only':content_id in self.contents})
        self.contents.setdefault(content_id,raw)
        self.acquired[identity]={'raw':self.contents[content_id],'content_id':content_id,'event':event,'operation':operation,'source_locator':locator,'source_revision':source_revision,'session_epoch':self.epoch,'run_id':self.run_id}
        return identity
    def admit(self,identity):
        need(identity in self.acquired,'HOLD_NOT_ACQUIRED')
        self.preuse(self.acquired[identity]['operation'],self.epoch)
        self.record('ADMITTED',{'artifact_id':identity,'acquired_event':self.acquired[identity]['event'],'content_id':self.acquired[identity]['content_id'],'classification':'UNTRUSTED_SYNTHETIC_DATA_NOT_INSTRUCTION'});self.admitted.add(identity);return identity
    def deliver(self,identity,start,end):
        need(identity in self.acquired,'HOLD_NOT_ACQUIRED')
        self.preuse(self.acquired[identity]['operation'],self.epoch)
        need(identity in self.admitted,'HOLD_NOT_ADMITTED')
        raw=self.acquired[identity]['raw'];need(type(start) is int and type(end) is int and 0<=start<=end<=len(raw),'HOLD_DELIVERY_RANGE')
        selected=raw[start:end];eid=self.record('DELIVERED',{'artifact_id':identity,'acquired_event':self.acquired[identity]['event'],'range_bytes':[start,end],'sha256':sha(selected),'projection_revision':'WORKER_DATA_ONLY_R004'})
        receipt={'range':[start,end],'sha256':sha(selected),'event':eid,'acquisition_id':identity,'session_epoch':self.epoch}
        self.delivered[identity]=receipt;self.deliveries[eid]=copy.deepcopy(receipt);return selected
    def cite(self,identity,range_bytes,claim,delivery_id=None):
        need(identity in self.acquired,'HOLD_NOT_ACQUIRED')
        self.preuse(self.acquired[identity]['operation'],self.epoch)
        receipt=self.deliveries.get(delivery_id) if delivery_id is not None else self.delivered.get(identity)
        need(receipt is not None and receipt['acquisition_id']==identity and receipt['range']==range_bytes and receipt['session_epoch']==self.epoch,'HOLD_CITATION_NOT_DELIVERED')
        need(claim=='SYNTHETIC_VALUE_7' and self.acquired[identity]['raw'][slice(*range_bytes)]==b'7','NCR_CLAIM_EVIDENCE_MISMATCH')
        return self.record('USED_OR_CITED',{'artifact_id':identity,'content_id':self.acquired[identity]['content_id'],'source_locator':self.acquired[identity]['source_locator'],'source_revision':self.acquired[identity]['source_revision'],'range_bytes':range_bytes,'claim':claim,'delivered_event':receipt['event']})
    def request(self,proposal):
        """Only a typed proposal; no arbitrary code/tool/path execution facility."""
        need(isinstance(proposal,dict),'HOLD_PROPOSAL_TYPE')
        action=proposal.get('action')
        if action!='READ_SYNTHETIC':
            self.record('POLICY_DENY',{'action':action,'reason':'HOLD_NOT_ALLOWED_IO'})
            raise ContractError('HOLD_NOT_ALLOWED_IO')
        return self.acquire_local(proposal['operation'],proposal['relative'])
    def inspect(self,operation):
        self.state='INSPECT';check=self.preuse(operation,self.epoch)
        self.record('INSPECT',{'operation':operation,'dependency':check,'audit_scope':'SYNTHETIC_SUPERVISOR_BROKER_ONLY'})
        return check
    def begin_effect(self,effect_id,operation,effect_revision):
        self.preuse(operation,self.epoch);need(effect_id not in self.pending,'HOLD_EFFECT_ID_COLLISION')
        effect={'state':'IN_FLIGHT','scope':[operation],'origin_run_id':self.run_id,'origin_epoch':self.epoch,'effect_revision':effect_revision}
        event=self.record('EFFECT_PENDING',{'effect_id':effect_id,**effect})
        self.pending[effect_id]={**effect,'pending_event':event};return copy.deepcopy(self.pending[effect_id])
    def settle_effect(self,effect_id,receipt):
        need(effect_id in self.pending,'HOLD_EFFECT_UNKNOWN');effect=self.pending[effect_id]
        need(self.active and self.authority_pin==digest(self.authority),'HOLD_EFFECT_CURRENT_AUTHORITY')
        need(receipt.get('effect_id')==effect_id and receipt.get('effect_revision')==effect.get('effect_revision') and receipt.get('origin_run_id')==effect.get('origin_run_id') and receipt.get('origin_epoch')==effect.get('origin_epoch'),'HOLD_EFFECT_RECEIPT_BINDING')
        need(receipt.get('scope')==effect['scope'] and receipt.get('state')=='COMPLETION_OBSERVED' and receipt.get('origin')=='SYNTHETIC_TEST_ONLY' and receipt.get('authority_effect')=='NONE','HOLD_EFFECT_RECEIPT_QUALIFICATION')
        event=self.record('EFFECT_SETTLED_SYNTHETIC',{'effect_id':effect_id,'receipt':receipt})
        effect.update(state='SETTLED_OBSERVED',settlement_event=event,settlement_receipt=copy.deepcopy(receipt))
    def persist(self):
        self.state='PERSIST'
        record=copy.deepcopy({'schema':'ingridge.pending/2','revision':REVISION,'origin_run_id':self.run_id,'session_epoch':self.epoch,'board':self.board,'holds':self.held,'pending':self.pending,'recording_gap':self.recording_gap,'explicit_rebind_required':True,'implicit_context':None,'authority_effect':'NONE'})
        write_new(self.root/('pending-%d.json'%self.epoch),record)
        if not self.recording_gap:self.record('PERSIST',{'digest':digest(record),'record_class':'pending_workstate'})
        return record
    def issue(self):
        self.state='ISSUE';self.record('ISSUE_HOLD',{'reason':'CURRENT_HUMAN_ARTIFACT_APPROVAL_ABSENT'})
        raise ContractError('HOLD_HUMAN_ISSUE_GATE')
    def stop(self):
        self.active=False;self.state='QUIESCE'
        if self.recorder and self.recorder.is_alive():self.record('QUIESCE',{'pending':self.pending,'protection_continues':True})
        for effect in self.pending.values():
            if effect.get('state')!='SETTLED_OBSERVED':effect['state']='UNKNOWN_COMPLETION'
        self.epoch+=1
    def late_result(self,epoch,value):
        need(self.active and epoch==self.epoch,'HOLD_LATE_EPOCH_RESULT')
    def teardown(self):
        # No shared caches, host profiles, credentials or outside paths are touched.
        self.active=False;self.state='TEARDOWN'
        if self.recorder and self.recorder.is_alive():
            try:self.record('TEARDOWN',{'scratch_disposition':'NOT_REBOUND','pending':self.pending,'protected_state_retained':True});self.pipe.send(None)
            except (ContractError,OSError,EOFError):pass
            self.recorder.join(3)
        if self.recorder and self.recorder.is_alive():self.recorder.terminate();self.recorder.join(3)
        if self.pipe:self.pipe.close()
        self.acquired.clear();self.admitted.clear();self.delivered.clear();self.contents.clear();self.deliveries.clear()
        audit=inspect_log(self.root/'events.jsonl',self.checkpoint)
        if self.recording_gap:return {'verdict':'HOLD','reason':'HOLD_OBSERVED_RECORDING_GAP','prefix_integrity':audit}
        return audit
    def rebind_pending(self,record,expected_digest):
        need(record.get('explicit_rebind_required') and digest(record)==expected_digest,'HOLD_PENDING_REBIND')
        need(record.get('authority_effect')=='NONE','HOLD_PENDING_AUTHORITY_ESCALATION')
        self.board=copy.deepcopy(record['board']);self.held=copy.deepcopy(record['holds']);self.pending=copy.deepcopy(record['pending']);self.state='NEXT_BOOT'
        self.record('NEXT_BOOT',{'pending_digest':expected_digest,'origin_run_id':record.get('origin_run_id','LEGACY_UNKNOWN'),'origin_epoch':record['session_epoch'],'current_authority_digest':self.authority_pin,'implicit_context_inherited':False,'pending_restored':list(self.pending)})
        self.recording_gap=bool(record.get('recording_gap',False))

    def acquire_loopback(self,operation,url):
        import urllib.request,urllib.parse
        self.preuse(operation,self.epoch)
        parsed=urllib.parse.urlsplit(url)
        need(parsed.scheme=='http' and parsed.hostname=='127.0.0.1' and parsed.port and not parsed.username and not parsed.password,'HOLD_NON_LOOPBACK_NETWORK')
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self,*args,**kwargs):raise ContractError('HOLD_REDIRECT_NOT_AUTHORIZED')
        self.record('REQUESTED',{'adapter':'loopback_http','operation':operation,'url':url})
        self.record('POLICY_ALLOW',{'rule':'LOOPBACK_ONLY_NO_REDIRECT_NO_PROXY'})
        opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
        try:
            with opener.open(url,timeout=self.budget['operation_seconds']) as response:
                raw=response.read(self.budget['input_bytes']+1)
            need(len(raw)<=self.budget['input_bytes'],'HOLD_INPUT_CAPACITY')
            self.input_bytes+=len(raw);return self._acquire_occurrence(operation,raw,'loopback_http',url,'OBSERVED_LOOPBACK_BYTES')
        except Exception:
            self.held.append({'id':'H-LOOPBACK-ACQUIRE','state':'UNKNOWN','scope':[operation],'reason':'NO_OBSERVED_COMPLETION'});raise

    def reuse_cache(self,operation,raw,metadata,expected):
        self.preuse(operation,self.epoch);rebind=cache_rebind(metadata,expected)
        need(len(raw)<=self.budget['input_bytes'],'HOLD_INPUT_CAPACITY')
        need(metadata['artifact_identity']==sha(raw),'HOLD_CACHE_BYTE_IDENTITY')
        self.record('CACHE_REBIND',{'receipt':rebind,'hit':True,'sha256':sha(raw)})
        return self._acquire_occurrence(operation,raw,'cache',metadata['artifact_identity'],metadata['revision'])

def worker_projection(board):
    # Temporal metadata and audit ordering are not instructions for this Worker.
    return {'projection_revision':'WORKER_BOARD_R001','moots':[{k:n[k] for k in ('moot_id','revision','status','closure_condition')} for n in board['moots']],
            'edges':[{k:e[k] for k in ('edge_id','source','target','type','required_revision','state','operation_scope')} for e in board['edges']],
            'freshness_policy':'USE_TIME_REVISION_AND_AUTHORITY_RECHECK','holds_preserved':True}

def board_fixture():
    return {'moots':[{'moot_id':n,'revision':'R001','status':'ACTIVE','case_closed':False,'authority_scope':'SYNTHETIC_PRIVATE','closure_condition':'DEPENDENCIES_AND_TEST_RECEIPTS'} for n in ['SOURCE','MAIN','INDEPENDENT','OPTIONAL']],
            'edges':[{'edge_id':'E-MAIN','source':'SOURCE','target':'MAIN','type':'HARD_DEPENDENCY','operation_scope':['MAIN'],'required_revision':'R001','evidence_refs':['SYNTHETIC_SOURCE_R001'],'state':'RESOLVED','closure_condition':'CURRENT_VERSION_MATCH'},
                     {'edge_id':'E-OPTIONAL','source':'OPTIONAL','target':'MAIN','type':'CURRENT_ROUTE_ONLY','operation_scope':['OPTIONAL'],'required_revision':'R001','evidence_refs':[],'state':'RESOLVED','closure_condition':'ONLY_SELECTED_OPTIONAL_ROUTE'}]}

def authority_fixture():
    return {'supervisor':'PRESENT_CONFIRMED','purpose_bound':True,'scope':'SYNTHETIC_PRIVATE','epoch':1,'origin':'SYNTHETIC_TEST_ONLY','external_effect':'NONE'}
