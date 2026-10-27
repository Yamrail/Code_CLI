"""Stdlib port of the fixed R009 Meterless projection contract.

SPDX-License-Identifier: Apache-2.0
Derived from Meterless/Meterless@1742dec56a66e58eef9dda2d2b865823758ca8cd
(EventStore and WorldModel upsert/relate/assertFact/canonical state operations).
Original Apache-2.0 license: native_runtime/meterless/LICENSE-Meterless.txt.
Only the operations used by reasoning_world_model.js are implemented. This is
an equivalent Python projection, not execution of the JavaScript engine.
"""
from __future__ import annotations
import copy,hashlib,json,math
from pathlib import Path
import sys
from decimal import Decimal

def _number(value):
    if not math.isfinite(value):return 'null'
    if value==0:return '0'
    text=repr(value).lower()
    if 1e-6<=abs(value)<1e21:
        return format(Decimal(text),'f').rstrip('0').rstrip('.') if '.' in format(Decimal(text),'f') else format(Decimal(text),'f')
    if 'e' in text:
        mantissa,exponent=text.split('e');mantissa=mantissa.removesuffix('.0');exponent=int(exponent)
        return mantissa+'e'+('+' if exponent>=0 else '-')+str(abs(exponent))
    return text.removesuffix('.0')

def js_json(value,*,canonical=False):
    if value is None:return 'null'
    if value is True:return 'true'
    if value is False:return 'false'
    if isinstance(value,str):return json.dumps(value,ensure_ascii=False,separators=(',',':'))
    if isinstance(value,int):return str(value)
    if isinstance(value,float):return _number(value)
    if isinstance(value,list):return '['+','.join(js_json(v,canonical=canonical) for v in value)+']'
    if isinstance(value,dict):
        keys=list(value)
        if canonical:keys.sort(key=lambda s:s.encode('utf-16-be','surrogatepass'))
        else:
            index=[k for k in keys if k.isascii() and k.isdigit() and str(int(k))==k and 0<=int(k)<4294967295]
            keys=sorted(index,key=int)+[k for k in keys if k not in index]
        return '{'+','.join(js_json(k)+':'+js_json(value[k],canonical=canonical) for k in keys)+'}'
    raise TypeError('Projection contract requires JSON values')

def _hash(value):return hashlib.sha256(value.encode('utf-8')).hexdigest()
def _truthy(value):return value is not None and value is not False and value!='' and not (isinstance(value,(int,float)) and (value==0 or math.isnan(value)))

class _World:
    def __init__(self):self.entities={};self.relationships={};self.facts={};self.audit=[];self.seq=0
    def _event(self):self.seq+=1;return 'evt_'+str(self.seq)
    def _audit(self,kind,source,summary,event):
        item={'seq':len(self.audit)+1,'at':source['at'],'kind':kind,'actor':source.get('by','system'),'summary':summary,'eventId':event}
        if 'runId' in source:item['runId']=source['runId']
        self.audit.append(item)
    def upsert(self,kind,key,attrs,source):
        ident=kind+':workledger:'+key
        if ident in self.entities:
            entity=self.entities[ident];entity['attrs'].update(copy.deepcopy(attrs));entity['updatedAt']=source['at'];entity['source']=copy.deepcopy(source)
        else:
            entity={'type':kind,'id':ident,'attrs':copy.deepcopy(attrs),'schemaVersion':1,'source':copy.deepcopy(source),'createdAt':source['at'],'updatedAt':source['at'],'aliases':[],'state':'active'}
            self.entities[ident]=entity
        self._audit('upsertEntity',source,ident+' ('+kind+')',self._event())
        return ident
    def relate(self,start,kind,end,valid_from,source):
        ident='rel_'+_hash(start+'|'+kind+'|'+end+'||'+valid_from)[:16]
        if ident in self.relationships:return
        # JS reserves validTo with undefined before schemaVersion. A later
        # supersession fills that existing property without moving its position.
        relation={'id':ident,'from':start,'type':kind,'to':end,'validFrom':valid_from,'validTo':None,'schemaVersion':1,'source':copy.deepcopy(source),'createdAt':source['at']}
        for old in self.relationships.values():
            if old['from']==start and old['type']==kind and old['to']!=end and not old.get('validTo') and not old.get('supersededBy'):
                old['validTo']=valid_from;old['supersededBy']=ident
        self.relationships[ident]=relation
        self._audit('relate',source,start+' -['+kind+']-> '+end,self._event())
    def fact(self,about,predicate,value,source):
        ident='fact_'+_hash(about+'|'+predicate+'|'+js_json(value,canonical=True)+'|'+source['at']+'|'+source['kind']+'|'+source.get('url',''))[:16]
        if ident in self.facts:return
        fact={'id':ident,'about':about,'predicate':predicate,'value':copy.deepcopy(value),'confidence':0.5,'source':copy.deepcopy(source),'assertedAt':source['at']}
        rivals=[old for old in self.facts.values() if old['about']==about and old['predicate']==predicate and not old.get('supersededBy')]
        winner=fact
        for old in rivals:
            if old['assertedAt']>winner['assertedAt']:winner=old
        self.facts[ident]=fact;event=self._event()
        for old in [fact,*rivals]:
            if old['id']!=winner['id']:old['supersededBy']=winner['id']
        entity=self.entities[about];entity['attrs'][predicate]=copy.deepcopy(winner['value']);entity['updatedAt']=source['at']
        self._audit('assertFact',source,about+'.'+predicate+' = '+js_json(winner['value'])+' (most-recent-wins)',event)
    def shape(self):
        return {'entities':[self.entities[k] for k in sorted(self.entities)],'contexts':[],'relationships':[{key:value for key,value in self.relationships[k].items() if key!='validTo' or value is not None} for k in sorted(self.relationships)],'facts':[self.facts[k] for k in sorted(self.facts)],'observations':[],'stories':[]}

def project(data):
    if data['source_of_truth']!='EXISTING_NATIVE_WORKLEDGER':raise ValueError('Native WorkLedger source required')
    world=_World()
    source={'kind':'native-workledger-readback','at':data['observed_utc'],'by':'INGRIDGE_HOST','url':'workledger:sha256:'+data['journal_sha256']}
    work=world.upsert('work-order',data['case_id'],{'native_checkpoint':data['checkpoint'],'budget':data['root_buckets']},source)
    workers={role:world.upsert('worker-role',role,{'execution':'DETERMINISTIC_SAMPLE_PROCESS'},source) for role in ['PLANNER','EXECUTOR','EVALUATOR']}
    for record in data['records']:
        origin={'kind':'native-recorded-worker-output','at':record['produced_utc'],'by':record['role'],'url':'workledger:trace:'+record['trace_id'],'runId':data['case_id']}
        world.upsert('work-order',data['case_id'],{'last_role':record['role'],'last_trace':record['trace_id']},origin)
        world.relate(work,'delegated-to',workers[record['role']],record['produced_utc'],origin)
        for predicate in ['selected_source','assessment','critique']:
            if _truthy(record.get(predicate)):world.fact(work,predicate,record[predicate],origin)
    shape=world.shape()
    return {'schema':'yamrail.r009.shared-world-model/1','engine':'Meterless World Model pinned upstream reference','upstream_commit':'1742dec56a66e58eef9dda2d2b865823758ca8cd','execution_class':'LOCAL_EXECUTED','input_class':'SYNTHETIC_FIXTURE','source_of_truth':'EXISTING_NATIVE_WORKLEDGER','canonical_writes':0,'derived_memory_only':True,'source_journal_sha256':data['journal_sha256'],'native_checkpoint':data['checkpoint'],'case_state':world.entities[work]['attrs'],'facts':shape['facts'],'relationships':shape['relationships'],'audit':world.audit,'derived_state_sha256':_hash(js_json(shape,canonical=True)),'authority_semantics':'Worker reports and supersession are observations, not Human approval or proof of claim truth.'}

def self_test():
    pin=json.loads(Path(__file__).with_name('WORLD_MODEL_FALLBACK_PIN.json').read_bytes())
    result=project(pin['probe_input']);raw=(js_json(result)+'\n').encode('utf-8')
    ok=hashlib.sha256(raw).hexdigest()==pin['probe_output_sha256'] and result['derived_state_sha256']==pin['probe_derived_state_sha256']
    return {'status':'PASS' if ok else 'FAIL','backend':'PYTHON_EQUIVALENT_PROJECTION','js_output_bytes_match_pinned_probe':ok,'projection_sha256':hashlib.sha256(raw).hexdigest(),'derived_state_sha256':result['derived_state_sha256'],'provider_calls':0}

if __name__=='__main__':
    if sys.argv[1:]==['--self-test']:
        result=self_test();print(js_json(result));sys.exit(0 if result['status']=='PASS' else 4)
    data=json.loads(Path(sys.argv[1]).read_bytes());sys.stdout.buffer.write((js_json(project(data))+'\n').encode('utf-8'))
