"""Immutable derived Graph delivery storage, separate from run-session authority.

Original encrypted evidence is never changed. New PNG/SVG/PDF/JSON delivery
bytes live only below the existing private R004 owner namespace.
"""
from __future__ import annotations
import hashlib,json,os,pathlib,re,threading,uuid

COLLECTION='osint_workfaces_ingridge_r004'
BLOBS='graph_artifact_blobs_v1'
ARTIFACTS='graph_artifacts_v1'
REQUESTS='graph_artifact_requests_v1'
CHUNK_BYTES=256*1024
MAX_BYTES=16*1024*1024
_local_lock=threading.RLock()

class GraphStoreError(ValueError):pass
def canonical(v):return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf-8')
def sha(raw):return hashlib.sha256(raw).hexdigest()
def identifier(value,length=64):
    if not isinstance(value,str) or re.fullmatch('[0-9a-f]{'+str(length)+'}',value) is None:raise GraphStoreError('GRAPH_STORAGE_REFERENCE')
    return value

class GraphArtifactStore:
    def __init__(self, *,cloud_storage=None,local_root=None):
        self.cloud=cloud_storage
        self.root=pathlib.Path(local_root) if local_root is not None else None
        if self.cloud is not None and self.cloud.collection!=COLLECTION:raise GraphStoreError('GRAPH_STORAGE_PARTITION')
        if self.cloud is None and self.root is None:raise GraphStoreError('GRAPH_STORAGE_UNBOUND')

    def _owner(self,ns):
        identifier(ns)
        return self.cloud.tenant(ns) if self.cloud is not None else self.root/'tenants'/ns/'graph_artifacts_v1'

    def _read_doc(self,ns,collection,name):
        identifier(name)
        if self.cloud is not None:
            try:
                snap=self._owner(ns).collection(collection).document(name).get(timeout=15)
                return snap.to_dict() if snap.exists else None
            except Exception:raise GraphStoreError('GRAPH_STORAGE_READ') from None
        path=self._owner(ns)/collection/(name+'.json')
        try:return json.loads(path.read_bytes()) if path.is_file() else None
        except (OSError,ValueError):raise GraphStoreError('GRAPH_STORAGE_READ') from None

    @staticmethod
    def _local_create(path,raw):
        path.parent.mkdir(parents=True,exist_ok=True)
        # Publish a complete file atomically, with no replacement of old bytes.
        temporary=path.parent/('.partial-'+uuid.uuid4().hex)
        try:
            with temporary.open('xb') as stream:
                stream.write(raw);stream.flush();os.fsync(stream.fileno())
            try:os.link(temporary,path)
            except FileExistsError:
                if path.read_bytes()!=raw:raise GraphStoreError('GRAPH_STORAGE_IMMUTABLE_CONFLICT')
        finally:
            try:temporary.unlink()
            except FileNotFoundError:pass

    @staticmethod
    def _cloud_create(ref,value):
        try:ref.create(value,timeout=15)
        except Exception:
            try:
                snap=ref.get(timeout=15)
                if not snap.exists or snap.to_dict()!=value:raise GraphStoreError('GRAPH_STORAGE_IMMUTABLE_CONFLICT')
            except GraphStoreError:raise
            except Exception:raise GraphStoreError('GRAPH_STORAGE_WRITE') from None

    def blob_reference(self,ns,raw,content_type):
        identifier(ns)
        if not isinstance(raw,bytes) or not 1<=len(raw)<=MAX_BYTES:raise GraphStoreError('GRAPH_ARTIFACT_SIZE')
        digest=sha(raw)
        return {'sha256':digest,'bytes':len(raw),'chunk_count':(len(raw)+CHUNK_BYTES-1)//CHUNK_BYTES,'content_type':content_type,
            'storage':{'collection':COLLECTION,'owner_namespace':ns,'blob_collection':BLOBS,'blob_id':digest,
                'chunk_collection':'chunks','chunk_field':'bytes','chunk_name_format':'%06d',
                'encoding':'FIRESTORE_BYTES' if self.cloud is not None else 'LOCAL_BYTES'}}

    def put_blob(self,ns,raw,content_type):
        result=self.blob_reference(ns,raw,content_type)
        digest=result['sha256'];chunks=[raw[i:i+CHUNK_BYTES] for i in range(0,len(raw),CHUNK_BYTES)]
        metadata={'schema':'yamrail.osint-derived-graph-blob/1','sha256':digest,'bytes':len(raw),'chunk_count':len(chunks),
            'content_type':content_type,'storage_class':'DERIVED_DELIVERY_NOT_ORIGINAL_EVIDENCE','encryption':'GOOGLE_MANAGED_PRIVATE_FIRESTORE' if self.cloud is not None else 'LOCAL_QUALIFICATION_ONLY',
            'authority_effect':'NONE'}
        if self.cloud is not None:
            ref=self._owner(ns).collection(BLOBS).document(digest)
            for i,part in enumerate(chunks):self._cloud_create(ref.collection('chunks').document('%06d'%i),{'index':i,'bytes':part,'sha256':sha(part)})
            self._cloud_create(ref,metadata)
        else:
            with _local_lock:
                folder=self._owner(ns)/BLOBS/digest
                for i,part in enumerate(chunks):self._local_create(folder/('%06d.bin'%i),part)
                self._local_create(folder/'metadata.json',canonical(metadata))
        if self.get_blob(ns,result)!=raw:raise GraphStoreError('GRAPH_STORAGE_WRITE_READBACK')
        return result

    def get_blob(self,ns,ref):
        digest=identifier(ref.get('sha256'));size=ref.get('bytes');count=ref.get('chunk_count')
        if type(size) is not int or not 1<=size<=MAX_BYTES or type(count) is not int or count!=(size+CHUNK_BYTES-1)//CHUNK_BYTES:raise GraphStoreError('GRAPH_STORAGE_BLOB_BOUND')
        try:
            parts=[]
            if self.cloud is not None:
                doc=self._owner(ns).collection(BLOBS).document(digest);snap=doc.get(timeout=15)
                meta=snap.to_dict() if snap.exists else {}
                for i in range(count):
                    part=doc.collection('chunks').document('%06d'%i).get(timeout=15)
                    value=part.to_dict() if part.exists else {};raw=value.get('bytes')
                    wanted=min(CHUNK_BYTES,size-i*CHUNK_BYTES)
                    if not isinstance(raw,bytes) or len(raw)!=wanted or value.get('index')!=i or sha(raw)!=value.get('sha256'):raise GraphStoreError('GRAPH_STORAGE_CORRUPT')
                    parts.append(raw)
            else:
                folder=self._owner(ns)/BLOBS/digest;meta=json.loads((folder/'metadata.json').read_bytes())
                for i in range(count):
                    wanted=min(CHUNK_BYTES,size-i*CHUNK_BYTES)
                    with (folder/('%06d.bin'%i)).open('rb') as stream:part=stream.read(wanted+1)
                    if len(part)!=wanted:raise GraphStoreError('GRAPH_STORAGE_CORRUPT')
                    parts.append(part)
            raw=b''.join(parts)
            if (meta.get('sha256')!=digest or meta.get('bytes')!=size or meta.get('chunk_count')!=count
                    or meta.get('content_type')!=ref.get('content_type') or len(raw)!=size or sha(raw)!=digest):raise GraphStoreError('GRAPH_STORAGE_CORRUPT')
            return raw
        except GraphStoreError:raise
        except Exception:raise GraphStoreError('GRAPH_STORAGE_READ') from None

    def request(self,ns,cid,key):
        identifier(cid,32);value=self._read_doc(ns,REQUESTS,identifier(key))
        if value is None:return None
        if not isinstance(value,dict) or value.get('owner_namespace')!=ns or value.get('workface_id')!=cid or value.get('request_key')!=key:raise GraphStoreError('GRAPH_STORAGE_OWNER_BINDING')
        artifact=self.artifact(ns,cid,value['artifact_id'])
        if artifact.get('request_key')!=key:raise GraphStoreError('GRAPH_REQUEST_INDEX_CORRUPT')
        return artifact

    def artifact(self,ns,cid,artifact_id):
        identifier(cid,32);value=self._read_doc(ns,ARTIFACTS,identifier(artifact_id))
        if value is None:raise KeyError()
        if not isinstance(value,dict) or value.get('owner_namespace')!=ns or value.get('workface_id')!=cid or value.get('artifact_id')!=artifact_id:raise KeyError()
        receipt=self.get_blob(ns,value['files']['receipt'])
        try:decoded=json.loads(receipt)
        except (ValueError,UnicodeError):raise GraphStoreError('GRAPH_RECEIPT_CORRUPT') from None
        if (decoded.get('artifact_id')!=artifact_id or sha(canonical({k:v for k,v in decoded.items() if k!='artifact_id'}))!=artifact_id
                or decoded.get('WORKFACE_ID')!=cid or decoded.get('request_key')!=value.get('request_key')
                or set(value.get('files',{}))!={'png','svg','pdf','receipt','master'}):raise GraphStoreError('GRAPH_RECEIPT_CORRUPT')
        for fmt in ('png','svg','pdf','master'):
            if decoded.get('DELIVERED_ARTIFACT_SHA256',{}).get(fmt)!=value['files'][fmt].get('sha256'):raise GraphStoreError('GRAPH_RECEIPT_FILE_BINDING')
        return value

    def publish(self,ns,cid,key,artifact_id,files):
        identifier(cid,32);identifier(key);identifier(artifact_id)
        value={'schema':'yamrail.osint-issued-graph-index/1','state':'ISSUED','owner_namespace':ns,'workface_id':cid,
            'request_key':key,'artifact_id':artifact_id,'files':files,'authority_effect':'NONE'}
        request={k:value[k] for k in ('owner_namespace','workface_id','request_key','artifact_id')}
        if self.cloud is not None:
            from google.cloud import firestore
            owner=self._owner(ns);target=owner.collection(ARTIFACTS).document(artifact_id);lookup=owner.collection(REQUESTS).document(key)
            @firestore.transactional
            def publish(tx):
                old=lookup.get(transaction=tx);artifact=target.get(transaction=tx)
                if old.exists and canonical(old.to_dict())!=canonical(request):raise GraphStoreError('GRAPH_NONDETERMINISTIC_ISSUANCE')
                if artifact.exists and canonical(artifact.to_dict())!=canonical(value):raise GraphStoreError('GRAPH_STORAGE_IMMUTABLE_CONFLICT')
                if not artifact.exists:tx.create(target,value)
                if not old.exists:tx.create(lookup,request)
            try:publish(self.cloud.client.transaction(max_attempts=3))
            except GraphStoreError:raise
            except Exception:raise GraphStoreError('GRAPH_STORAGE_PUBLICATION') from None
        else:
            with _local_lock:
                old=self._read_doc(ns,REQUESTS,key)
                if old is not None and canonical(old)!=canonical(request):raise GraphStoreError('GRAPH_NONDETERMINISTIC_ISSUANCE')
                self._local_create(self._owner(ns)/ARTIFACTS/(artifact_id+'.json'),canonical(value))
                self._local_create(self._owner(ns)/REQUESTS/(key+'.json'),canonical(request))
        return self.artifact(ns,cid,artifact_id)
