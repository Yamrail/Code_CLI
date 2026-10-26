"""OS-owned Graph issuance and immutable byte delivery; no job authority."""
from __future__ import annotations
import contextlib,copy,hashlib,importlib.metadata,json,pathlib,re,struct,threading,weakref,xml.etree.ElementTree as ET,zlib
from .graph_artifact_store import GraphArtifactStore,GraphStoreError,canonical,sha,MAX_BYTES

KINDS={'CONTENT','HISTORY'}
FORMATS={'png':'image/png','svg':'image/svg+xml','pdf':'application/pdf','receipt':'application/json','master':'application/json'}
_generation=threading.BoundedSemaphore(2)
_lock_guard=threading.Lock()
_locks=weakref.WeakValueDictionary()
ROOT=pathlib.Path(__file__).resolve().parents[1]
PRESENTATION_REVISION='YR-OSINT-A4-PRESENTATION-R001'
PDF_MARGIN_MM=8

class GraphArtifactError(ValueError):
    def __init__(self,code,status=409):super().__init__(code);self.code=code;self.status=status

@contextlib.contextmanager
def _selector_slot(lock):
    if not lock.acquire(blocking=False):raise GraphArtifactError('GRAPH_GENERATION_BUSY',503)
    try:yield
    finally:lock.release()

def _hex(v):return isinstance(v,str) and re.fullmatch('[0-9a-f]{64}',v) is not None
def _store(engine):
    value=getattr(engine,'_graph_artifact_store',None)
    if value is None:
        value=GraphArtifactStore(cloud_storage=engine.cloud_storage if engine.cloud_mode else None,local_root=engine.root)
        engine._graph_artifact_store=value
    return value

def _identity():
    from .graph_png import renderer_identity
    identity=copy.deepcopy(renderer_identity())
    identity['artifact_adapter_sha256']=sha(pathlib.Path(__file__).read_bytes())
    identity['server_adapters']={p:sha((ROOT/'field_backend'/p).read_bytes()) for p in
        ('silver_export.py','silver_board_renderer.py','investigation_dependency_graph.py','explanatory_graph.py','structured_md_renderer.py','document_versions.py')}
    identity['export_packages']={p:importlib.metadata.version(p) for p in ('reportlab','svglib','fonttools')}
    identity['presentation_revision']=PRESENTATION_REVISION
    identity['pdf_minimum_margin_mm']=PDF_MARGIN_MM
    return identity

def _present_master(raw,kind,master):
    """Versioned captions on a verified OS SVG; original renderers stay exact.

    Only renderer-owned caption positions change. MD excerpts, source numbers,
    graph nodes/edges, previous sealed artifacts and original metadata survive.
    """
    from .silver_export import self_contained_svg,vector_pdf
    ns='{http://www.w3.org/2000/svg}'
    node=ET.fromstring(raw);changes=[]
    replacements={'分からないこと':'分かっていないこと','条件付き見立て':'未検証の仮説',
        '資料の記載':'分かっていること（資料の記載）'}
    for group in node.findall(ns+'g'):
        layer=group.get('data-layer','');labels=group.findall(ns+'text')
        for index,item in enumerate(labels):
            before=item.text or '';after=before
            if layer=='10_header' and index==0:after='調査結果の簡易見取り図'
            elif layer=='10_header' and before in {
                '資料の記載・仮説・条件を区別。線はMDに明示された対応であり、独立した事実認定ではありません。',
                '矢印は保存された参照関係です。出来事の因果を示しません。'}:
                after='関連線は資料上の対応や関係を示します。因果関係や独立した事実認定を保証しません。'
            elif layer=='60_timeline_heading':after='現状'
            elif layer=='70_next_heading':after='今後の調査課題'
            elif layer.startswith('30_node_') and index==0:
                for old,new in replacements.items():
                    if re.fullmatch(r'[0-9]+ '+re.escape(old),before):after=before.split(' ',1)[0]+' '+new
            if after!=before:
                item.text=after;changes.append({'layer':layer,'caption_index':index,'before':before,'after':after})
    if node.get('data-derivation')=='STRUCTURED_MD_GRAPH':
        group=ET.SubElement(node,ns+'g',{'data-layer':'20_presentation_source_heading'})
        item=ET.SubElement(group,ns+'text',{'x':'16','y':'98','font-size':'11','font-family':'YamrailBoard','fill':'#0060df'})
        item.text='資料'
    node.set('aria-label','調査結果の簡易見取り図。'+('全体依存図' if kind=='HISTORY' else '資料と状態の詳細図'))
    node.set('data-presentation-revision',PRESENTATION_REVISION)
    rendered=ET.tostring(node,encoding='utf-8',xml_declaration=True)
    presentation={'revision':PRESENTATION_REVISION,'sheet':1 if kind=='HISTORY' else 2,
        'sheet_role':'A4_OVERVIEW_DEPENDENCY_GRAPH' if kind=='HISTORY' else 'A4_DETAILED_SOURCE_AND_STATE_GRAPH',
        'source_master_svg_sha256':sha(raw),'source_metadata':copy.deepcopy(master['renderer_metadata']),
        'caption_changes':changes,'graph_semantics_changed':False,'pdf_page_mm':[297,210],
        'pdf_minimum_margin_mm':PDF_MARGIN_MM,'original_source_and_prior_artifacts':'PRESERVED'}
    value=copy.deepcopy(master);value['presentation']=presentation;value['master_svg_sha256']=sha(rendered)
    value['renderer_metadata']={**value['renderer_metadata'],'svg_sha256':sha(rendered),'presentation_revision':PRESENTATION_REVISION}
    return rendered,self_contained_svg(node,sha(rendered)),vector_pdf(rendered,value['renderer_metadata'],margin_mm=PDF_MARGIN_MM),canonical(value)

def _answer(historical):
    source=(historical.get('received_analysis') or {}).get('frame') if historical.get('record_state')=='RECEIVED_UNCOMMITTED_RESULT' else historical.get('report')
    advisory=source.get('model_advisory',{}) if isinstance(source,dict) else {}
    text=advisory.get('analysis_markdown')
    if isinstance(text,str):
        value=sha(text.encode('utf-8'))
        if advisory.get('analysis_markdown_sha256')!=value:raise GraphArtifactError('GRAPH_ANSWER_DIGEST_MISMATCH')
        return value,'EXACT_ANALYSIS_MARKDOWN_UTF8'
    text=advisory.get('text')
    if isinstance(text,str):return sha(text.encode('utf-8')),'EXACT_MODEL_ADVISORY_UTF8'
    report=historical.get('report')
    if isinstance(report,dict):return sha(canonical(report)),'CANONICAL_STORED_REPORT_JSON'
    return None,'NO_PUBLISHED_ANSWER'

def _source(engine,principal,cid,kind,expected):
    ns,row=engine._history_row(principal,cid)
    historical=engine._history_payload(ns,row)
    selected=engine._investigation_snapshot_payload(ns,row,historical) if kind=='HISTORY' else historical
    binding=copy.deepcopy(selected.get('binding'))
    if not isinstance(binding,dict) or binding.get('workface_id')!=cid:raise GraphArtifactError('GRAPH_SOURCE_BINDING_UNAVAILABLE')
    if expected is not None and (not isinstance(expected,dict) or expected!=binding):raise GraphArtifactError('GRAPH_SOURCE_REVISION_CHANGED')
    answer,answer_kind=_answer(historical)
    if kind=='CONTENT' and answer is None:raise GraphArtifactError('GRAPH_ANSWER_UNAVAILABLE')
    if kind=='HISTORY' and historical.get('binding') is not None:
        if any(historical['binding'].get(k)!=binding.get(k) for k in ('workface_id','epoch','revision','input_sha256')):raise GraphArtifactError('GRAPH_SOURCE_REVISION_CHANGED')
    refs={k:copy.deepcopy(row.get(k)) for k in ('input_ref','answer_input_ref','last_answer_ref') if row.get(k) is not None}
    return ns,historical,selected,binding,answer,answer_kind,refs

def _master(historical,selected,binding,kind):
    if kind=='CONTENT':
        from .silver_export import verified_master
        raw,node,metadata,checked=verified_master(historical)
        if checked!=binding:raise GraphArtifactError('GRAPH_MASTER_SOURCE_MISMATCH')
        derived=historical.get('derived_content_graph') or {}
        graph=copy.deepcopy(derived.get('projection'))
        if not isinstance(graph,dict):
            frame=(historical.get('received_analysis') or {}).get('frame') if historical.get('record_state')=='RECEIVED_UNCOMMITTED_RESULT' else historical.get('report')
            graph=copy.deepcopy((frame or {}).get('model_advisory',{}).get('silver_board'))
        source_digest=metadata.get('source_ledger_sha256') or derived.get('source_ledger_sha256')
        if not _hex(source_digest):raise GraphArtifactError('GRAPH_SOURCE_EVIDENCE_DIGEST_UNAVAILABLE')
    else:
        from .investigation_dependency_graph import dependency_graph
        value=dependency_graph(selected);graph=copy.deepcopy(value['scene']);metadata=value['render']['metadata']
        raw=value['render']['svg'].encode('utf-8');node=ET.fromstring(raw)
        source_digest=value['source_digest']
    if not isinstance(raw,bytes) or not 1<=len(raw)<=262144 or sha(raw)!=metadata.get('svg_sha256'):
        raise GraphArtifactError('GRAPH_MASTER_VALIDATION_FAILED')
    master={'schema':'yamrail.osint-immutable-graph-master/1','graph_kind':kind,'source_binding':binding,
        'master_svg_sha256':sha(raw),'source_evidence_digest':source_digest,'graph':graph,
        'renderer_metadata':metadata,'evidence_class':'DERIVED_GRAPH_MASTER_NOT_ORIGINAL_SOURCE_EVIDENCE'}
    rendered,svg,pdf,master=_present_master(raw,kind,master)
    if not svg.startswith(b'<?xml') or not pdf.startswith(b'%PDF-'):raise GraphArtifactError('GRAPH_MASTER_VALIDATION_FAILED')
    return rendered,svg,pdf,master,source_digest

def _png(raw,identity):
    if (not isinstance(raw,bytes) or not 33<=len(raw)<=MAX_BYTES or raw[:8]!=b'\x89PNG\r\n\x1a\n'
            or raw[12:16]!=b'IHDR' or struct.unpack('>I',raw[8:12])[0]!=13):raise GraphArtifactError('GRAPH_PNG_VALIDATION_FAILED')
    width,height=struct.unpack('>II',raw[16:24]);wanted=identity.get('output_dimensions')
    if (wanted!={'width':width,'height':height} or not 1<=width<=4096 or not 1<=height<=4096
            or raw[24:29]!=b'\x08\x02\x00\x00\x00' or raw[-12:]!=b'\x00\x00\x00\x00IEND\xaeB`\x82'):raise GraphArtifactError('GRAPH_PNG_GEOMETRY_OR_FORMAT')
    offset=8;tags=[];compressed=[]
    while offset<len(raw):
        if offset+12>len(raw):raise GraphArtifactError('GRAPH_PNG_CHUNK_INVALID')
        size=struct.unpack('>I',raw[offset:offset+4])[0];tag=raw[offset+4:offset+8];end=offset+12+size
        if end>len(raw) or tag not in {b'IHDR',b'IDAT',b'IEND'}:raise GraphArtifactError('GRAPH_PNG_CHUNK_INVALID')
        payload=raw[offset+8:offset+8+size]
        if zlib.crc32(tag+payload)&0xffffffff!=struct.unpack('>I',raw[offset+8+size:end])[0]:raise GraphArtifactError('GRAPH_PNG_CRC_INVALID')
        tags.append(tag)
        if tag==b'IDAT':compressed.append(payload)
        offset=end
    if tags[0]!=b'IHDR' or tags[-1]!=b'IEND' or tags.count(b'IHDR')!=1 or tags.count(b'IEND')!=1 or not compressed:raise GraphArtifactError('GRAPH_PNG_CHUNK_INVALID')
    decoder=zlib.decompressobj();limit=height*(1+width*3)
    pixels=decoder.decompress(b''.join(compressed),limit+1)
    if len(pixels)!=limit or not decoder.eof or decoder.unused_data or decoder.unconsumed_tail:raise GraphArtifactError('GRAPH_PNG_PIXELS_INVALID')
    if any(pixels[i] not in range(5) for i in range(0,limit,1+width*3)):raise GraphArtifactError('GRAPH_PNG_FILTER_INVALID')

def _response(store,ns,cid,value):
    artifact_id=value['artifact_id'];receipt=json.loads(store.get_blob(ns,value['files']['receipt']))
    if receipt.get('WORKFACE_ID')!=cid or receipt.get('artifact_id')!=artifact_id:raise GraphArtifactError('GRAPH_RECEIPT_BINDING')
    files={}
    for fmt,ref in value['files'].items():
        if fmt not in FORMATS:raise GraphArtifactError('GRAPH_ARTIFACT_FORMAT')
        ext='json' if fmt in {'master','receipt'} else fmt
        files[fmt]={'url':'/private/osint/api/workfaces/'+cid+'/graph-artifacts/'+artifact_id+'/'+fmt,
            'sha256':ref['sha256'],'bytes':ref['bytes'],'content_type':FORMATS[fmt],
            'chunk_count':ref['chunk_count'],'storage':copy.deepcopy(ref['storage']),
            'filename':'YamRail-OSINT-'+receipt['GRAPH_KIND'].lower()+'-'+cid+'-'+artifact_id[:12]+'-'+fmt+'.'+ext}
    return {'schema':'yamrail.osint-graph-artifact-issue/1','artifact_id':artifact_id,'graph_kind':receipt['GRAPH_KIND'],
        **({'document_revision':receipt['DOCUMENT_REVISION']} if 'DOCUMENT_REVISION' in receipt else {}),
        'receipt':receipt,'files':files,'runtime_effect':'NONE','new_provider_calls':0,'authority_effect':'SERVER_ARTIFACT_BINDING_ONLY'}

def issue(engine,principal,cid,kind,expected=None,document_revision=None):
    if kind not in KINDS:raise GraphArtifactError('GRAPH_KIND_INVALID',400)
    try:
        store=_store(engine)
        document=None
        if document_revision is not None:
            if kind!='CONTENT' or not _hex(document_revision):raise GraphArtifactError('GRAPH_DOCUMENT_REVISION_INVALID',400)
            from .document_versions import graph_source
            ns,document,refs=graph_source(engine,principal,cid,document_revision)
            binding=copy.deepcopy(document['source_binding'])
            if expected is not None and expected!=binding:raise GraphArtifactError('GRAPH_SOURCE_REVISION_CHANGED')
            historical={'record_state':'CONFIRMED_GENERATED_DOCUMENT_REVISION'};selected={}
            answer=document['body_sha256'];answer_kind='EXACT_CONFIRMED_DOCUMENT_UTF8'
        else:ns,historical,selected,binding,answer,answer_kind,refs=_source(engine,principal,cid,kind,expected)
        identity=_identity()
        selector={'graph_kind':kind,'source_binding':binding,'snapshot_sha256':selected.get('snapshot_sha256'),
                  'answer_digest':answer,'renderer_identity':identity,
                  **({'document_revision':document_revision} if document is not None else {})}
        request_key=sha(canonical(selector));existing=store.request(ns,cid,request_key)
        if existing is not None:return _response(store,ns,cid,existing)
        with _lock_guard:
            lock=_locks.get((ns,request_key))
            if lock is None:lock=threading.Lock();_locks[(ns,request_key)]=lock
        with _selector_slot(lock):
            existing=store.request(ns,cid,request_key)
            if existing is not None:return _response(store,ns,cid,existing)
            if not _generation.acquire(blocking=False):raise GraphArtifactError('GRAPH_GENERATION_BUSY',503)
            try:
                if document is not None:
                    from .document_versions import graph_master
                    master_svg,svg,pdf,master,source_digest=graph_master(document,refs)
                else:master_svg,svg,pdf,master,source_digest=_master(historical,selected,binding,kind)
                from .graph_png import render_png
                first=render_png(master_svg);second=render_png(master_svg)
                _png(first,identity);_png(second,identity)
                if first!=second:raise GraphArtifactError('GRAPH_PNG_NONDETERMINISTIC')
                data={'png':first,'svg':svg,'pdf':pdf,'master':master}
                for raw in data.values():
                    if not 1<=len(raw)<=MAX_BYTES:raise GraphArtifactError('GRAPH_ARTIFACT_SIZE')
                receipt={'schema':'yamrail.osint-graph-artifact-receipt/1','request_key':request_key,'WORKFACE_ID':cid,'SOURCE_REVISION':binding,
                    'SOURCE_EVIDENCE_DIGEST':source_digest,'ANSWER_DIGEST':answer,'GRAPH_KIND':kind,
                    'MASTER_GRAPH_DIGEST':sha(master),'RENDERER_IDENTITY':identity,
                    'DELIVERED_ARTIFACT_SHA256':{k:sha(v) for k,v in data.items()},
                    'derived_delivery_storage':{k:store.blob_reference(ns,v,FORMATS[k]) for k,v in data.items()},
                    'receipt_storage_rule':'Receipt location is in the immutable issue index and issue response; excluded here to avoid self-reference.',
                    'answer_digest_kind':answer_kind,'source_record_state':historical.get('record_state'),
                    'source_encrypted_references':refs,'source_snapshot_sha256':selected.get('snapshot_sha256'),
                    'source_master_svg_sha256':sha(master_svg),'png_repeat_sha256':[sha(first),sha(second)],
                    'artifact_id_formula':'SHA256(canonical(receipt excluding artifact_id))','runtime_effect':'NONE','new_provider_calls':0,
                    'authority_effect':'SERVER_ARTIFACT_BINDING_ONLY','original_source_evidence':'PRESERVED_ENCRYPTED_NOT_REPLACED'}
                if document is not None:receipt.update(DOCUMENT_REVISION=document_revision,DOCUMENT_BODY_SHA256=document['body_sha256'],document_derivation='CONFIRMED_DOCUMENT_STRUCTURE')
                artifact_id=sha(canonical(receipt));receipt['artifact_id']=artifact_id;data['receipt']=canonical(receipt)
                stored={fmt:store.put_blob(ns,raw,FORMATS[fmt]) for fmt,raw in data.items()}
                value=store.publish(ns,cid,request_key,artifact_id,stored)
                return _response(store,ns,cid,value)
            finally:_generation.release()
    except GraphArtifactError:raise
    except GraphStoreError as error:raise GraphArtifactError(str(error),503) from None
    except KeyError:raise
    except Exception as error:
        code=error.args[0] if error.args else None
        if not isinstance(code,str) or re.fullmatch('GRAPH_PNG_[A-Z0-9_]+',code) is None:code='GRAPH_GENERATION_UNAVAILABLE'
        raise GraphArtifactError(code) from None

def retrieve(engine,principal,cid,artifact_id,fmt):
    if fmt not in FORMATS:raise GraphArtifactError('GRAPH_ARTIFACT_FORMAT',400)
    ns=engine.namespace(principal)
    try:
        store=_store(engine)
        value=store.artifact(ns,cid,artifact_id);response=_response(store,ns,cid,value)
        raw=store.get_blob(ns,value['files'][fmt]);descriptor=response['files'][fmt]
        if sha(raw)!=descriptor['sha256'] or len(raw)!=descriptor['bytes']:raise GraphArtifactError('GRAPH_DELIVERY_CORRUPT',503)
        if fmt not in {'receipt'} and response['receipt']['DELIVERED_ARTIFACT_SHA256'].get(fmt)!=descriptor['sha256']:raise GraphArtifactError('GRAPH_DELIVERY_RECEIPT_MISMATCH',503)
        return {**descriptor,'byte_count':len(raw),'bytes':raw,'artifact_id':artifact_id,'graph_kind':response['graph_kind']}
    except GraphArtifactError:raise
    except GraphStoreError as error:raise GraphArtifactError(str(error),503) from None
