"""Byte/Revision admission for native Git receivers. Never an authority gate."""
import json, pathlib, re
from .reused.binder import need, sha, digest

IDENTITY={'account':'Yamrail','repository':'Yamrail/yamrail-evidence-ledger-private','branch':'migration/evidence-ledger-20260806',
 'prefix':'03_operations/architecture/20261005_ingridge_os_integrated_execution_r004'}
def safe_member(name):
    need(isinstance(name,str) and name and '\\' not in name and not name.startswith('/') and ':' not in name,'HOLD_TRANSPORT_PATH')
    parts=name.split('/');need(all(p not in {'','.', '..'} for p in parts),'HOLD_TRANSPORT_PATH')
    need(not any(p.endswith((' ','.')) for p in parts),'HOLD_TRANSPORT_WINDOWS_PATH_ALIAS')
    need(not any(re.fullmatch(r'(?i)(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?',p) for p in parts),'HOLD_TRANSPORT_WINDOWS_DEVICE')
    return True
def admit_members(manifest,members,observed,expected_commit):
    need(all(observed.get(k)==v for k,v in IDENTITY.items()),'HOLD_TRANSPORT_ACCOUNT_REPO_BRANCH_PREFIX')
    need(observed.get('commit')==expected_commit and re.fullmatch('[0-9a-f]{40}',expected_commit) is not None,'HOLD_TRANSPORT_REVISION')
    need(manifest.get('schema')=='ingridge.integration-manifest/1' and manifest.get('parent_commit')=='16404870b12c375d3c899113cce46f087e3b1546','HOLD_TRANSPORT_MANIFEST_SCHEMA_PARENT')
    need(manifest.get('revision')=='INGRIDGE_INTEGRATED_R004' and manifest.get('authority_effect')=='NONE','HOLD_TRANSPORT_MANIFEST_REVISION_AUTHORITY')
    need(set(manifest.get('excluded_sidecars',[]))=={'MANIFEST_R004.json','HASHES_R004.txt'},'HOLD_TRANSPORT_MANIFEST_EXCLUSION')
    records=manifest.get('members');need(isinstance(records,list) and records,'HOLD_TRANSPORT_MANIFEST_MISSING')
    names=[r['path'] for r in records]
    for name in names:safe_member(name)
    need(len(names)==len(set(names))==len({n.casefold() for n in names}),'HOLD_TRANSPORT_MEMBER_COLLISION')
    need(set(names)==set(members),'HOLD_TRANSPORT_MEMBER_SET')
    for r in records:
        raw=members[r['path']]
        need(sha(raw)==r['sha256'] and len(raw)==r['bytes'],'HOLD_TRANSPORT_MEMBER_BYTES:'+r['path'])
    return {'origin':'RECEIVER','immutable_commit':expected_commit,'manifest_digest':digest(manifest),'members_match':True,
      'member_count':len(names),'revision':manifest['revision'],'parent_commit':manifest['parent_commit'],'identity':observed,
      'state':'PC_RECEIVED','authority_effect':'NONE','human_acceptance':'NOT_GRANTED'}
def scan_secrets(members):
    patterns=[rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',rb'\bgh[pousr]_[A-Za-z0-9]{30,}\b',rb'\bAKIA[A-Z0-9]{16}\b',rb'\bgithub_pat_[A-Za-z0-9_]{40,}\b']
    hits=[]
    for name,raw in members.items():
        if any(re.search(p,raw) for p in patterns):hits.append(name)
    need(not hits,'HOLD_TRANSPORT_SECRET_MIX:'+','.join(hits));return {'scope':'DECLARED_PAYLOAD_HIGH_CONFIDENCE_PATTERN_SCAN','findings':[],'complete_secret_absence_guarantee':False}

class TransportAttempt:
    """Fault fixture for object creation/commit/ref boundaries and optimistic lock."""
    def __init__(self,base):self.base=base;self.phase='LOCAL_ONLY';self.commit=None;self.remote=None
    def blobs(self):need(self.phase=='LOCAL_ONLY','HOLD_TRANSPORT_PHASE');self.phase='BLOBS_CREATED'
    def committed(self,commit):need(self.phase=='BLOBS_CREATED','HOLD_TRANSPORT_PHASE');self.commit=commit;self.phase='COMMIT_CREATED'
    def update_ref(self,current):
        need(self.phase=='COMMIT_CREATED','HOLD_TRANSPORT_PHASE');need(current==self.base,'HOLD_TRANSPORT_CONCURRENT_UPDATE')
        self.remote=self.commit;self.phase='GITHUB_STORED';return self.remote
    def receipt(self):return {'phase':self.phase,'github_stored':self.remote is not None,'pc_received':False,'sol_ack':False,'work_started':False,'delivered':False}
