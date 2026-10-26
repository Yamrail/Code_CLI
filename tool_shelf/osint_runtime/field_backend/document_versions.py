"""Owned generated-document revisions; no automatic run or canonical adoption."""
from __future__ import annotations
import copy,json,os,pathlib,re,threading,time,uuid,xml.etree.ElementTree as ET
from .document_guard import inspect_document,context_profile,protected_ranges,RULE_REVISION,MAX_DOCUMENT_BYTES
from .graph_artifact_store import GraphArtifactStore,GraphStoreError,canonical,sha,identifier,_local_lock

ROOTS='document_roots_v1';REVISIONS='document_revisions_v1';INSPECTIONS='document_inspections_v1';REVIEWS='document_context_reviews_v1';EXECUTIONS='document_inspection_executions_v1'
SURFACES={'REPORT','FIVE_LINE','FLASH','MARKDOWN','GRAPH_LABELS','OFFICIAL_DRAFT'}
_operations=threading.BoundedSemaphore(2)

class DocumentError(ValueError):
    def __init__(self,code,status=409):super().__init__(code);self.code=code;self.status=status

def _store(engine):
    return GraphArtifactStore(cloud_storage=engine.cloud_storage if engine.cloud_mode else None,local_root=engine.root)

def _create(store,ns,collection,name,value):
    identifier(name)
    if len(canonical(value))>850000:raise DocumentError('DOCUMENT_STORAGE_BOUND',400)
    if store.cloud is not None:store._cloud_create(store._owner(ns).collection(collection).document(name),value)
    else:
        with _local_lock:store._local_create(store._owner(ns)/collection/(name+'.json'),canonical(value))

def _read(store,ns,collection,name,cid):
    value=_doc_read(store,ns,collection,identifier(name))
    if value is None or value.get('owner_namespace')!=ns or value.get('workface_id')!=cid:raise KeyError()
    return value

def _doc_read(store,ns,collection,name):
    if store.cloud is not None:value=store._read_doc(ns,collection,name)
    else:
        path=store._owner(ns)/collection/(identifier(name)+'.json')
        try:
            with path.open('rb') as stream:raw=stream.read(850001)
        except FileNotFoundError:return None
        if len(raw)>850000:raise DocumentError('DOCUMENT_STORAGE_BOUND',503)
        value=json.loads(raw)
    if value is not None and (not isinstance(value,dict) or len(canonical(value))>850000):raise DocumentError('DOCUMENT_STORAGE_BOUND',503)
    return value

def _state(store,ns,root,expected=None,initial=False):
    """Only this small current pointer mutates; every body/inspection is immutable."""
    name=root['document_id']
    def check(old):
        if initial:
            if old is not None and (old.get('source_identity')!=root['source_identity']):raise DocumentError('DOCUMENT_ID_CONFLICT')
            return old if old is not None else root
        if old is None or old.get('current_revision')!=expected:raise DocumentError('DOCUMENT_REVISION_CHANGED')
        if old.get('state_version',0)!=root.get('state_version',0):raise DocumentError('DOCUMENT_STATE_CHANGED')
        return {**root,'state_version':old.get('state_version',0)+1}
    if store.cloud is not None:
        from google.cloud import firestore
        target=store._owner(ns).collection(ROOTS).document(name)
        @firestore.transactional
        def update(tx):
            snap=target.get(transaction=tx);old=snap.to_dict() if snap.exists else None;value=check(old)
            if not snap.exists:tx.create(target,value)
            elif value!=old:tx.set(target,value)
            return value
        try:return update(store.cloud.client.transaction(max_attempts=3))
        except DocumentError:raise
        except Exception:raise DocumentError('DOCUMENT_STORAGE_UNAVAILABLE',503) from None
    with _local_lock:
        old=_doc_read(store,ns,ROOTS,name);value=check(old)
        path=store._owner(ns)/ROOTS/(name+'.json')
        if old is None:store._local_create(path,canonical(value))
        elif old!=value:
            tmp=path.parent/('.partial-'+uuid.uuid4().hex)
            try:
                with tmp.open('xb') as stream:stream.write(canonical(value));stream.flush();os.fsync(stream.fileno())
                os.replace(tmp,path)
            finally:
                try:tmp.unlink()
                except FileNotFoundError:pass
        return value

def _body(value):
    if not isinstance(value,str):raise DocumentError('DOCUMENT_BODY_INVALID',400)
    try:size=len(value.encode('utf-8','strict'))
    except UnicodeError:raise DocumentError('DOCUMENT_BODY_INVALID',400) from None
    if not 1<=size<=MAX_DOCUMENT_BYTES:raise DocumentError('DOCUMENT_SIZE',400)
    return value

def _frame(historical):
    frame=(historical.get('received_analysis') or {}).get('frame') if historical.get('record_state')=='RECEIVED_UNCOMMITTED_RESULT' else historical.get('report')
    if not isinstance(frame,dict):raise DocumentError('DOCUMENT_GENERATED_SOURCE_UNAVAILABLE')
    return frame

def generated_source(engine,principal,cid,surface):
    if surface not in SURFACES:raise DocumentError('DOCUMENT_SURFACE_INVALID',400)
    ns,row=engine._history_row(principal,cid);historical=engine._history_payload(ns,row)
    binding=copy.deepcopy(historical.get('binding'));frame=_frame(historical)
    if not isinstance(binding,dict) or binding.get('workface_id')!=cid:raise DocumentError('DOCUMENT_SOURCE_BINDING')
    advisory=frame.get('model_advisory') or {};body=None
    if surface in {'REPORT','MARKDOWN','OFFICIAL_DRAFT'}:
        body=advisory.get('analysis_markdown')
        if isinstance(body,str) and sha(body.encode('utf-8'))!=advisory.get('analysis_markdown_sha256'):raise DocumentError('DOCUMENT_SOURCE_DIGEST')
        if body is None:body=frame.get('summary')
    elif surface in {'FIVE_LINE','FLASH'}:
        # These are actual generated stage text, never raw source outlines.
        rows=engine._history(ns)
        stage='FLASH' if surface=='FLASH' else 'IN_DEPTH'
        candidates=[x['details']['frame'] for x in rows if x.get('event_type')=='STAGE_PROGRESS'
                    and x.get('details',{}).get('case')==cid and x['details'].get('epoch')==binding.get('epoch')
                    and x['details'].get('revision')==binding.get('revision') and x['details'].get('frame',{}).get('stage')==stage]
        if candidates:
            value=candidates[-1];body=value.get('text') if surface=='FLASH' else '\n'.join(value.get('preview',{}).get('refined_summary',[]))
    else:
        graph=(historical.get('derived_content_graph') or {}).get('projection',{}).get('board')
        if not isinstance(graph,dict):graph=(advisory.get('silver_board') or {}).get('board')
        if isinstance(graph,dict):
            labels=[]
            for node in graph.get('nodes',[]):
                if isinstance(node,dict):
                    for key in ('label','title','text'):
                        if isinstance(node.get(key),str):labels.append(node[key]);break
            body='\n'.join(labels)
    if not isinstance(body,str) or not body.strip():raise DocumentError('DOCUMENT_SURFACE_UNAVAILABLE')
    _body(body)
    refs={k:copy.deepcopy(row.get(k)) for k in ('input_ref','answer_input_ref','last_answer_ref') if row.get(k) is not None}
    return ns,body,binding,refs

def _inspection(engine,store,ns,cid,revision,context):
    ctx=copy.deepcopy(context);ctx['language']=revision['language'];ctx['document_revision']=revision['revision_id']
    # Exception authority is an explicit reason bound to an actual candidate.
    if ctx.get('exceptions'):
        baseline=inspect_document(revision['body'],{**ctx,'exceptions':[]})
        candidates={(x['rule_id'],x['span']['start'],x['span']['end']) for x in baseline['findings']}
        if any((x.get('rule_id'),x.get('start'),x.get('end')) not in candidates for x in ctx['exceptions']):raise DocumentError('DOCUMENT_EXCEPTION_NOT_BOUND',400)
    wall=time.perf_counter_ns();cpu=time.thread_time_ns()
    result=inspect_document(revision['body'],ctx)
    cpu=time.thread_time_ns()-cpu;wall=time.perf_counter_ns()-wall
    inspection_id=sha(canonical(result))
    value={'owner_namespace':ns,'workface_id':cid,'document_id':revision['document_id'],
           'revision_id':revision['revision_id'],'inspection_id':inspection_id,'result':result}
    _create(store,ns,INSPECTIONS,inspection_id,value)
    execution={'schema':'yamrail.document-inspection-execution/1','owner_namespace':ns,'workface_id':cid,
               'document_id':revision['document_id'],'document_revision':revision['revision_id'],'inspection_id':inspection_id,
               'inspection_sha256':inspection_id,'document_sha256':revision['body_sha256'],'rule_revision':RULE_REVISION,
               'execution':'ACTUAL_CPU_FUNCTION_CALL','process_id':os.getpid(),'thread_id':threading.get_ident(),
               'thread_cpu_ns':cpu,'wall_ns':wall,'new_provider_calls':0,
               'runtime_identity':{key:os.environ[key] for key in ('K_REVISION','OSINT_HMI_SOURCE_COMMIT','OSINT_HMI_SOURCE_SHA256') if key in os.environ},
               'execution_nonce':uuid.uuid4().hex}
    execution['execution_id']=sha(canonical(execution));_create(store,ns,EXECUTIONS,execution['execution_id'],execution)
    return inspection_id,execution

def _revision(store,ns,cid,document_id,body,source,surface,language,actor,parent=None,reason=None):
    value={'schema':'yamrail.osint-document-revision/1','owner_namespace':ns,'workface_id':cid,'document_id':document_id,
           'parent_revision':None if parent is None else parent['revision_id'],'body':_body(body),'body_sha256':sha(body.encode('utf-8')),
           'source_binding':copy.deepcopy(source),'surface':surface,'language':language,'actor':actor,
           'revision_state':'CONFIRMED_GENERATED_SNAPSHOT' if parent is None else 'HUMAN_ADOPTED_REVISION',
           'adoption':{'confirmed':parent is not None,'reason':reason,'authority':'ORIGINAL_GENERATED_NOT_CANONICAL' if parent is None else 'EXPLICIT_HUMAN_EDIT_NOT_CANONICAL_ISSUANCE'},
           'diff':None,'authority_effect':'NONE'}
    if parent is not None:
        old=parent['body'];a=0
        while a<min(len(old),len(body)) and old[a]==body[a]:a+=1
        suffix=0
        while suffix<min(len(old)-a,len(body)-a) and old[len(old)-1-suffix]==body[len(body)-1-suffix]:suffix+=1
        b=len(old)-suffix;d=len(body)-suffix
        changes=[{'start':a,'end':b,'old':old[a:b],'new':body[a:d]}]
        value['diff']={'old_revision':parent['revision_id'],'old_body_sha256':parent['body_sha256'],
                       'new_body_sha256':value['body_sha256'],'offset_unit':'UNICODE_CODE_POINTS_HALF_OPEN','changes':changes}
    revision_id=sha(canonical(value));value['revision_id']=revision_id
    _create(store,ns,REVISIONS,revision_id,value)
    return value

def _envelope(store,ns,cid,root):
    revision=_read(store,ns,REVISIONS,root['current_revision'],cid)
    inspection=_read(store,ns,INSPECTIONS,root['current_inspection'],cid)
    if (revision['document_id']!=root['document_id'] or inspection['revision_id']!=revision['revision_id']
            or root['current_revision'] not in root['revision_ids']
            or sha(canonical(root['source_identity']))!=root['document_id']
            or sha(revision['body'].encode('utf-8'))!=revision['body_sha256']
            or sha(canonical({k:v for k,v in revision.items() if k!='revision_id'}))!=root['current_revision']
            or sha(canonical(inspection['result']))!=root['current_inspection']):raise DocumentError('DOCUMENT_STORAGE_BINDING',503)
    base='/private/osint/api/workfaces/'+cid+'/documents/'+root['document_id']+'/revisions/'+revision['revision_id']
    return {'schema':'yamrail.osint-document/1','document_id':root['document_id'],'current_revision':revision['revision_id'],
            'revision':revision,'inspection':{**inspection['result'],'inspection_id':inspection['inspection_id']},
            'files':{'md':{'url':base+'/md','filename':'YamRail-OSINT-'+root['document_id'][:12]+'-'+revision['revision_id'][:12]+'.md',
                           'content_type':'text/markdown; charset=utf-8','sha256':revision['body_sha256'],'bytes':len(revision['body'].encode('utf-8'))}},
            'context_reviews':copy.deepcopy(root.get('context_reviews',[])),
            'runtime_effect':'NONE','new_provider_calls':0,'authority_effect':'NONE'}

def create(engine,principal,cid,surface,language='ja',context=None):
    if language=='ja-JP':language='ja'
    if language not in {'ja','en','pt'}:raise DocumentError('DOCUMENT_LANGUAGE_INVALID',400)
    ns,body,source,refs=generated_source(engine,principal,cid,surface);store=_store(engine)
    ctx=copy.deepcopy(context or {});ctx['language']=language
    if surface=='OFFICIAL_DRAFT':ctx.setdefault('document_type','OFFICIAL')
    context_profile(ctx,body)
    identity={'source_binding':source,'surface':surface,'language':language,'original_body_sha256':sha(body.encode('utf-8'))}
    document_id=sha(canonical(identity))
    existing=_doc_read(store,ns,ROOTS,document_id)
    if existing is not None:
        if existing.get('owner_namespace')!=ns or existing.get('workface_id')!=cid:raise DocumentError('DOCUMENT_STORAGE_BINDING',503)
        _,current=revision(engine,principal,cid,existing['current_revision'])
        existing['current_inspection'],execution=_inspection(engine,store,ns,cid,current,ctx)
        return {**_envelope(store,ns,cid,_state(store,ns,existing,current['revision_id'])),'execution':execution}
    version=_revision(store,ns,cid,document_id,body,source,surface,language,{'class':'SERVER_GENERATED','source_references':refs})
    inspection_id,execution=_inspection(engine,store,ns,cid,version,ctx)
    root={'schema':'yamrail.osint-document-root/1','owner_namespace':ns,'workface_id':cid,'document_id':document_id,
          'source_identity':identity,'original_revision':version['revision_id'],'current_revision':version['revision_id'],
          'current_inspection':inspection_id,'revision_ids':[version['revision_id']],'context_reviews':[],'state_version':1}
    return {**_envelope(store,ns,cid,_state(store,ns,root,initial=True)),'execution':execution}

def get(engine,principal,cid,document_id):
    ns=engine.namespace(principal);store=_store(engine)
    return _envelope(store,ns,cid,_read(store,ns,ROOTS,document_id,cid))

def revision(engine,principal,cid,revision_id):
    ns=engine.namespace(principal);store=_store(engine);value=_read(store,ns,REVISIONS,revision_id,cid)
    if sha(value['body'].encode('utf-8'))!=value['body_sha256'] or sha(canonical({k:v for k,v in value.items() if k!='revision_id'}))!=revision_id:raise DocumentError('DOCUMENT_REVISION_CORRUPT',503)
    root=_read(store,ns,ROOTS,value['document_id'],cid)
    if revision_id not in root['revision_ids']:raise DocumentError('DOCUMENT_REVISION_NOT_CONFIRMED')
    return ns,value

def reinspect(engine,principal,cid,document_id,expected,context):
    ns=engine.namespace(principal);store=_store(engine);root=_read(store,ns,ROOTS,document_id,cid)
    if root['current_revision']!=expected:raise DocumentError('DOCUMENT_REVISION_CHANGED')
    _,value=revision(engine,principal,cid,expected)
    root['current_inspection'],execution=_inspection(engine,store,ns,cid,value,context)
    return {**_envelope(store,ns,cid,_state(store,ns,root,expected)),'execution':execution}

def adopt(engine,principal,cid,document_id,expected,body,reason,confirmation):
    if confirmation is not True or not isinstance(reason,str) or not 1<=len(reason)<=512:raise DocumentError('DOCUMENT_EXPLICIT_ADOPTION_REQUIRED',400)
    ns=engine.namespace(principal);store=_store(engine);root=_read(store,ns,ROOTS,document_id,cid)
    if root['current_revision']!=expected:raise DocumentError('DOCUMENT_REVISION_CHANGED')
    _,parent=revision(engine,principal,cid,expected);_body(body)
    if body==parent['body']:raise DocumentError('DOCUMENT_NO_CHANGE',400)
    value=_revision(store,ns,cid,document_id,body,parent['source_binding'],parent['surface'],parent['language'],
                    {'uid':principal.uid,'tenant':principal.tenant},parent,reason)
    old_inspection=_read(store,ns,INSPECTIONS,root['current_inspection'],cid)
    # Old spans/exceptions cannot silently migrate to a different body.
    ctx={k:v for k,v in old_inspection['result']['applicability'].items() if k not in {'protected_spans','exceptions'}}
    inspection_id,execution=_inspection(engine,store,ns,cid,value,ctx)
    root.update(current_revision=value['revision_id'],current_inspection=inspection_id,
                revision_ids=root['revision_ids']+[value['revision_id']])
    if len(root['revision_ids'])>128:raise DocumentError('DOCUMENT_REVISION_LIMIT')
    return {**_envelope(store,ns,cid,_state(store,ns,root,expected)),'execution':execution}

def markdown(engine,principal,cid,document_id,revision_id):
    _,value=revision(engine,principal,cid,revision_id)
    if value['document_id']!=document_id:raise KeyError()
    raw=value['body'].encode('utf-8')
    return {'bytes':raw,'byte_count':len(raw),'sha256':sha(raw),'content_type':'text/markdown; charset=utf-8',
            'filename':'YamRail-OSINT-'+document_id[:12]+'-'+revision_id[:12]+'.md','document_revision':revision_id}

def _link_review(store,ns,cid,document_id,request):
    # Merge this single append-only locator against a freshly read root. A
    # concurrent adoption/reinspection cannot be overwritten by an old snapshot.
    for attempt in range(3):
        current=_read(store,ns,ROOTS,document_id,cid);reviews=current.get('context_reviews',[])
        if any(x['request_id']==request['request_id'] for x in reviews):return
        if len(reviews)>=16:raise DocumentError('DOCUMENT_CONTEXT_REVIEW_LIMIT')
        current['context_reviews']=reviews+[{k:request[k] for k in ('request_id','document_revision','child_workface_id','state')}]
        try:_state(store,ns,current,current['current_revision']);return
        except DocumentError as error:
            if error.code not in {'DOCUMENT_STATE_CHANGED','DOCUMENT_REVISION_CHANGED'}:raise
    raise DocumentError('DOCUMENT_STATE_CHANGED')

def context_review(engine,principal,cid,document_id,body,request_id=None):
    ns=engine.namespace(principal);store=_store(engine)
    root=_read(store,ns,ROOTS,document_id,cid)
    if request_id is not None:
        request=_read(store,ns,REVIEWS,request_id,cid)
        if request.get('document_id')!=document_id:raise KeyError()
        _,document=revision(engine,principal,cid,request['document_revision'])
        _,child_row=engine._history_row(principal,request['child_workface_id'])
        child=engine.historical_result(principal,request['child_workface_id'])
        result={**request,'schema':'yamrail.osint-document-context-review/1','state':'REVIEW_NEEDED','suggestions':[],
                'authority_effect':'NON_CANONICAL','automatic_adoption':False,'provider_references':None}
        try:
            if (child_row.get('input_ref',{}).get('sha256')!=request['child_input_sha256']
                    or child_row.get('parent_bindings')!=[request['source_snapshot']]
                    or (child.get('binding') or {}).get('input_sha256')!=request['child_input_sha256']):return result
            from .document_context import MARKER,validate_input,validate_suggestions
            packet=engine._load(ns,child_row['input_ref'])
            payload=validate_input(packet,[request['source_snapshot']])
            if (payload is None or request.get('execution_contract')!=packet[MARKER]
                    or payload['document_id']!=document_id or payload['request_id']!=request_id
                    or payload['document_revision']!=document['revision_id']
                    or payload['body_sha256']!=document['body_sha256']):return result
            frame=_frame(child);advisory=frame.get('model_advisory') or {};text=advisory.get('analysis_markdown')
            if (advisory.get('document_context_review')!=packet[MARKER]
                    or (advisory.get('receipt') or {}).get('public_search_receipt') is not None):return result
            if not isinstance(text,str) or len(text.encode('utf-8'))>65536:return result
            parsed=validate_suggestions(text,payload)
            suggestions=[{**item,'explicit_diff':{'old':item['observed'],'new':item['suggested']},'authority':'NON_CANONICAL'}for item in parsed['suggestions']]
            result.update(state='NON_CANONICAL_SUGGESTIONS',suggestions=suggestions,provider_references=advisory.get('receipt'),child_source_binding=child.get('binding'))
            return result
        except (ValueError,TypeError,KeyError):return result
    required={'expected_revision','external_intent','information_class','permission','confirmation','request_key'}
    if (not isinstance(body,dict) or set(body)!=required or body['external_intent']!='REQUEST_EXTERNAL_CONTEXT_REVIEW'
            or body['information_class']!='PUBLIC_OSINT' or body['permission'] is not True or body['confirmation'] is not True):raise DocumentError('DOCUMENT_CONTEXT_REVIEW_AUTHORITY_REQUIRED',400)
    if root['current_revision']!=body['expected_revision']:raise DocumentError('DOCUMENT_REVISION_CHANGED')
    identifier(body['request_key']);request_id=sha(canonical({'document_id':document_id,'revision':body['expected_revision'],'request_key':body['request_key']}))
    existing=_doc_read(store,ns,REVIEWS,request_id)
    if existing is not None:
        if existing.get('workface_id')!=cid or existing.get('document_id')!=document_id:raise DocumentError('DOCUMENT_STORAGE_BINDING',503)
        _link_review(store,ns,cid,document_id,existing)
        return existing
    if len(root.get('context_reviews',[]))>=16:raise DocumentError('DOCUMENT_CONTEXT_REVIEW_LIMIT')
    _,document=revision(engine,principal,cid,body['expected_revision'])
    # The usual continuation freezes source lineage. Its normal explicit Start
    # still performs current admission/budget/worker checks; this creates no call.
    from .investigation_snapshot import snapshot_reference
    snapshot=engine.investigation_snapshot(principal,cid)
    base=document['source_binding']
    if (any(snapshot['binding'].get(k)!=base.get(k) for k in ('workface_id','epoch','revision','input_sha256','report_sha256'))
            or base.get('received_frame_sha256')!=(snapshot.get('received_analysis') or {}).get('frame_sha256')):raise DocumentError('DOCUMENT_SOURCE_REVISION_CHANGED')
    from .document_context import make_input
    question,execution_contract=make_input(document_id,document['revision_id'],document['body'],
        _read(store,ns,INSPECTIONS,root['current_inspection'],cid)['result']['applicability'],
        request_id,[snapshot_reference(snapshot)])
    if len(question)>32000:raise DocumentError('DOCUMENT_CONTEXT_REVIEW_SIZE',400)
    child=engine.continue_investigation(principal,question,[snapshot_reference(snapshot)],ready_to_start=True,
        idempotency_key=request_id,document_review=execution_contract)
    _,child_row=engine._history_row(principal,child['id'])
    request={'schema':'yamrail.osint-document-context-review/1','owner_namespace':ns,'workface_id':cid,'document_id':document_id,'document_revision':document['revision_id'],
             'request_id':request_id,'child_workface_id':child['id'],'child_input_sha256':child_row['input_ref']['sha256'],
             'prompt_sha256':sha(question.encode('utf-8')),'state':'PREPARED_NOT_SENT','source_snapshot':snapshot_reference(snapshot),
             'execution_contract':execution_contract,
             'explicit_intent':body['external_intent'],'information_class':'PUBLIC_OSINT','actor':{'uid':principal.uid,'tenant':principal.tenant},
            'new_provider_calls':0,'requires_existing_explicit_start':True,'authority_effect':'NON_CANONICAL'}
    _create(store,ns,REVIEWS,request_id,request)
    _link_review(store,ns,cid,document_id,request)
    return request

def graph_source(engine,principal,cid,revision_id):
    ns,value=revision(engine,principal,cid,revision_id);store=_store(engine)
    root=_read(store,ns,ROOTS,value['document_id'],cid)
    original=_read(store,ns,REVISIONS,root['original_revision'],cid)
    refs=copy.deepcopy(original['actor']['source_references'])
    return ns,value,refs

def graph_master(document,refs):
    """A bounded structural projection of the confirmed body, not a model response.

    Reuses MD structure extraction, fixed font metrics, PNG worker, SVG/PDF
    exporters and immutable Graph publication. Full exact text stays in MD.
    """
    from .md_structure import build
    from .silver_board_renderer import _line_width,FONT_FAMILY,FONT_SHA256
    from .silver_export import self_contained_svg,vector_pdf
    from .explanatory_graph import _source_binding
    body=document['body'];binding=document['source_binding']
    # Citation IDs without an original ledger remain explicitly unbound; this
    # projection never invents evidence to make human-edited text look verified.
    ledger={'items':[],'sha256':sha(canonical(refs))}
    base={k:binding[k] for k in ('workface_id','epoch','revision','input_sha256')}
    graph=build(body,ledger,base,{'state':'NO_MODEL_GRAPH'},_source_binding)
    ns='http://www.w3.org/2000/svg';ET.register_namespace('',ns)
    svg=ET.Element('{'+ns+'}svg',{'viewBox':'0 0 1414 1000','width':'1414','height':'1000','preserveAspectRatio':'xMidYMid meet',
                               'font-family':FONT_FAMILY,'font-kerning':'none','font-variant-ligatures':'none'})
    ET.SubElement(svg,'{'+ns+'}rect',{'x':'0','y':'0','width':'1414','height':'1000','fill':'#ffffff'})
    def text(value,x,y,size=18):
        element=ET.SubElement(svg,'{'+ns+'}text',{'x':str(x),'y':str(y),'font-size':str(size),'font-family':FONT_FAMILY,'fill':'#102f3c'})
        element.text=value
    text('生成文書の構造（本文の記載・原意は未検証）',24,36,23)
    text('文書版 '+document['revision_id'],24,63,13)
    nodes=graph['nodes'][:12];positions={n['id']:(24+(i%3)*464,96+(i//3)*208) for i,n in enumerate(nodes)}
    displayed=[]
    for edge in graph.get('edges',[]):
        if edge['from'] in positions and edge['to'] in positions:
            x,y=positions[edge['from']];a,b=positions[edge['to']]
            ET.SubElement(svg,'{'+ns+'}line',{'x1':str(x+218),'y1':str(y+88),'x2':str(a+218),'y2':str(b+88),'stroke':'#b8c7d0','stroke-width':'1','stroke-dasharray':'4 3'})
    for node in nodes:
        x,y=positions[node['id']]
        ET.SubElement(svg,'{'+ns+'}rect',{'x':str(x),'y':str(y),'width':'438','height':'184','fill':'#f3f7fc','stroke':'#b8c7d0','stroke-width':'1'})
        text(node['category']+' / '+str(node['md_span']['start'])+':'+str(node['md_span']['end']),x+10,y+23,13)
        lines=[];line='';shown=0
        for char in node['text']:
            if char in '\r\n':
                if line:lines.append(line);line=''
            elif _line_width(line+char,16)>414:
                lines.append(line);line=char
            else:line+=char
            if len(lines)>=7:break
            shown+=1
        if line and len(lines)<7:lines.append(line)
        for i,line in enumerate(lines):text(line,x+10,y+48+i*18,16)
        displayed.append({'node_id':node['id'],'source_span':node['md_span'],'displayed_lines':lines,'partial':shown<len(node['text'])})
    text('部分投影 '+str(len(nodes))+' / '+str(len(graph['nodes']))+'項目。全文・残余は同一文書版のMD。',24,962,16)
    master={'schema':'yamrail.osint-immutable-graph-master/1','graph_kind':'CONTENT','derivation':'CONFIRMED_DOCUMENT_STRUCTURE',
            'source_binding':binding,'document_revision':document['revision_id'],'document_body_sha256':document['body_sha256'],
            'graph':graph,'display_projection':displayed,'source_evidence_digest':sha(canonical(refs)),
            'evidence_class':'DERIVED_DOCUMENT_GRAPH_NOT_ORIGINAL_OR_MODEL_RESPONSE'}
    ET.SubElement(svg,'{'+ns+'}metadata').text=canonical(master).decode('utf-8')
    raw=ET.tostring(svg,encoding='utf-8');master['master_svg_sha256']=sha(raw)
    metadata={'svg_sha256':sha(raw),'font_sha256':FONT_SHA256,'binding':base}
    delivered=self_contained_svg(copy.deepcopy(svg),sha(raw));pdf=vector_pdf(raw,metadata,margin_mm=8)
    return raw,delivered,pdf,canonical(master),master['source_evidence_digest']

def execute(function,*args,**kwargs):
    if not _operations.acquire(blocking=False):raise DocumentError('DOCUMENT_INSPECTION_BUSY',503)
    try:return function(*args,**kwargs)
    except (DocumentError,KeyError):raise
    except (ValueError,GraphStoreError) as error:
        code=str(error)
        raise DocumentError(code if re.fullmatch('DOCUMENT_[A-Z0-9_]+',code) else 'DOCUMENT_INSPECTION_UNCONFIRMED',400) from None
    except Exception:raise DocumentError('DOCUMENT_INSPECTION_UNCONFIRMED',503) from None
    finally:_operations.release()
