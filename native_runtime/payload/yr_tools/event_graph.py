"""Declared v0.1.1 event-graph core; observed edges are inspected, never inferred."""
import hashlib,hmac,copy
from .binder import need,text,known_identity,strict_int,instant,validate,result,guarded,no_authority,digest
from .numeric import number
REVISION='SPATIOTEMPORAL_EVENT_GRAPH_PIPELINE_R005_PRIVATE'
IDENTITIES={'SAME','DISTINCT','OVERLAP','CONFLICTING','UNKNOWN','UNREGISTERED','LOOKUP_FAILED'}
OBSERVED={'SAME_PROCESS_SEQ','MONOTONIC_BEFORE','OBSERVED_BY','IPC_SEND_RECEIVE','CONTROLLER_ACTION','HEARTBEAT_OBSERVATION','CGROUP_STATE_CHANGE'}
INFERRED={'POSSIBLE_CAUSAL','POSSIBLE_PROPAGATION','POSSIBLE_COMMON_CAUSE'}
UNRESOLVED={'UNKNOWN','UNREGISTERED','LOOKUP_FAILED','CONFLICTING'}
def cycle_nodes(ids,edges):
    # Reachability from each node preserves directed cycles; no DAG rewriting.
    adj={i:[] for i in ids}
    for e in edges:adj[e['from']].append(e['to'])
    found=[]
    for origin in ids:
        seen=set();todo=list(adj[origin])
        while todo:
            item=todo.pop()
            if item==origin:found.append(origin);break
            if item not in seen:seen.add(item);todo.extend(adj[item])
    return found
def inspect(d,pin,base):return guarded(_inspect,d,pin,base)
def _inspect(d,pin,base):
    need(d.get('schema')=='yr.event-graph/1' and known_identity(d.get('run_id')),'HOLD_EVENT_GRAPH_SCHEMA');no_authority(d)
    ref=d['source_ref'];payload={k:v for k,v in d.items() if k!='source_ref'}
    validate(ref,pin['source_pin'],base,pin['source_subject'],{'graph_input':payload})
    need(d.get('request_dag') is False,'HOLD_DAG_NOT_QUALIFIED')
    nodes=d['nodes'];edges=d['edges'];relations=d['identity_relations']
    need(isinstance(nodes,list) and isinstance(edges,list) and isinstance(relations,list),'HOLD_EVENT_GRAPH_TYPE')
    ids=[n['id'] for n in nodes];need(all(known_identity(i) for i in ids) and len(set(ids))==len(ids),'HOLD_EVENT_NODE_IDENTITY')
    by={n['id']:n for n in nodes};unresolved=[]
    for r in relations:
        need(r['from'] in by and r['to'] in by and r['state'] in IDENTITIES,'HOLD_RELATION_TYPE')
        if r['state'] in UNRESOLVED:unresolved.append(r)
    for n in nodes:
        need(n['identity_state'] in IDENTITIES and known_identity(n['clock_domain_id']) and n['clock_domain_id'] not in UNRESOLVED and known_identity(n['process_id']) and n['process_id'] not in UNRESOLVED and strict_int(n['process_seq']),'HOLD_CLOCK_OR_IDENTITY_UNKNOWN')
        if n['identity_state'] in UNRESOLVED:unresolved.append({'node_id':n['id'],'state':n['identity_state']})
        need(number(n['monotonic_time'])>=0,'HOLD_MONOTONIC_TYPE');instant(n['wall_time']);instant(n['observer_time'])
    edge_ids=[]
    for e in edges:
        need(text(e['id']) and e['from'] in by and e['to'] in by,'HOLD_GRAPH_EDGE_UNBOUND');edge_ids.append(e['id'])
        need(e['kind'] in OBSERVED|INFERRED and e['epistemic_state']==('OBSERVED' if e['kind'] in OBSERVED else 'INFERRED'),'HOLD_EDGE_EPISTEMIC_PROMOTION')
        need(isinstance(e['basis'],dict) and text(e['basis'].get('basis_id')),'HOLD_EDGE_BASIS_UNBOUND')
        er=e['evidence_ref'];validate(er,pin['evidence_pins'][er['artifact_id']],base,pin['evidence_subjects'][er['artifact_id']],{'edge_observation':{k:v for k,v in e.items() if k!='evidence_ref'}})
        a,b=by[e['from']],by[e['to']]
        need(edge_basis_qualified(e,a,b),'HOLD_OBSERVED_EDGE_CORRELATION_OR_PAIR_UNBOUND')
        if e['kind']=='SAME_PROCESS_SEQ':need(a['process_id']==b['process_id'] and a['clock_domain_id']==b['clock_domain_id'] and a['process_seq']<b['process_seq'],'HOLD_PROCESS_SEQUENCE_UNBOUND')
        if e['kind']=='MONOTONIC_BEFORE':need(a['clock_domain_id']==b['clock_domain_id'] and number(a['monotonic_time'])<number(b['monotonic_time']),'HOLD_INCOMPARABLE_CLOCK_DOMAIN')
    need(len(set(edge_ids))==len(edge_ids),'HOLD_EDGE_COLLISION')
    cycles=cycle_nodes(ids,edges)
    return result('HOLD_GRAPH_EXPANSION' if unresolved else 'PASS_EVENT_GRAPH_STRUCTURAL_ONLY',tool_revision=REVISION,graph=copy.deepcopy(d),unresolved_relations=unresolved,cycle_nodes=cycles,cycle_state='CYCLE_DETECTED' if cycles else 'NO_CYCLE_IN_RETAINED_GRAPH',cycle_disposition='PRESERVE_AND_FLAG',wall_time_role='REFERENCE_ONLY',causal_attribution='NOT_CERTIFIED',progress_eligible=not unresolved)
def _pseudonymize(graph,run_secret):
    need(isinstance(run_secret,bytes) and len(run_secret)>=32 and text(graph['run_id']),'HOLD_PSEUDONYM_KEY_UNBOUND')
    def alias(value):return 'N_'+hmac.new(run_secret,(graph['run_id']+'\0'+value).encode('utf-8'),hashlib.sha256).hexdigest()[:24]
    nodes=[];mapping={}
    for n in graph['nodes']:
        for key in ('id','process_id','clock_domain_id'):mapping[n[key]]=alias(n[key])
        nodes.append({k:alias(n[k]) if k in {'id','process_id','clock_domain_id'} else n[k] for k in ('id','process_id','clock_domain_id','process_seq','monotonic_time','wall_time','observer_time','identity_state')})
    edges=[{'id':alias(e['id']),'from':alias(e['from']),'to':alias(e['to']),'kind':e['kind'],'epistemic_state':e['epistemic_state']} for e in graph['edges']]
    relations=[{'from':alias(r['from']),'to':alias(r['to']),'state':r['state']} for r in graph['identity_relations']]
    raw_by={n['id']:n for n in graph['nodes']}
    unresolved=graph.get('request_dag') is not False or any(r['state'] in UNRESOLVED for r in relations) or any(n['identity_state'] in UNRESOLVED or n['clock_domain_id'] in UNRESOLVED or n['process_id'] in UNRESOLVED for n in graph['nodes']) or any(not edge_basis_qualified(e,raw_by[e['from']],raw_by[e['to']]) for e in graph['edges'])
    return {'view':{'nodes':nodes,'edges':edges,'identity_relations':relations,'expansion_state':'HOLD_GRAPH_EXPANSION' if unresolved else 'PASS_STRUCTURAL_ONLY','scanner_mode':'HYPOTHESIZE_ONLY','run_view_id':alias(graph['run_id'])},'local_audit_mapping':mapping,'mapping_egress_allowed':False,'secret_egress_allowed':False}
def pseudonymize(graph,run_secret,pin=None,base=None):
    # The old unbound entry point is retained, but cannot issue upstream qualification.
    checked=inspect(graph,pin,base) if isinstance(pin,dict) and base is not None else result('HOLD_UPSTREAM_GRAPH_BINDING',['HOLD_SOURCE_PIN_AND_BASE_REQUIRED'])
    try:out=_pseudonymize(graph,run_secret)
    except (KeyError,TypeError,ValueError,AttributeError):
        checked=result('HOLD_PSEUDONYM_TRANSFORM',['HOLD_PSEUDONYM_KEY_OR_INPUT_TYPE'])
        out={'view':{'nodes':[],'edges':[],'identity_relations':[],'scanner_mode':'HYPOTHESIZE_ONLY'},'local_audit_mapping':{},'mapping_egress_allowed':False,'secret_egress_allowed':False}
    view=out['view'];view['upstream_verdict']=checked['verdict'];view['upstream_reasons']=checked['reasons'];view['producer_revision']=REVISION
    if checked['verdict']!='PASS_EVENT_GRAPH_STRUCTURAL_ONLY':view['expansion_state']='HOLD_GRAPH_EXPANSION'
    else:
        view['source_graph_digest']=digest(graph);view['qualified_source_sha256']=graph['source_ref']['sha256'];view['expansion_state']='PASS_STRUCTURAL_ONLY'
    return out

def inspect_hypotheses(hypotheses,view):return guarded(_hypotheses,hypotheses,view)
def _hypotheses(hypotheses,view):
    need(isinstance(hypotheses,list) and view['scanner_mode']=='HYPOTHESIZE_ONLY','HOLD_HYPOTHESIS_SCHEMA')
    need(view['expansion_state']=='PASS_STRUCTURAL_ONLY','HOLD_GRAPH_EXPANSION')
    known={e['id'] for e in view['edges']};ids=[]
    for h in hypotheses:
        need(set(h)<= {'hypothesis_id','anomaly_ref','mechanisms','epistemic_state','confidence'} and h['epistemic_state']=='HYPOTHESIS','HOLD_HYPOTHESIS_AUTHORITY_OR_CAUSAL_LEAK')
        need(text(h['hypothesis_id']) and text(h['anomaly_ref']) and isinstance(h['mechanisms'],list) and h['mechanisms'],'HOLD_HYPOTHESIS_TYPE');ids.append(h['hypothesis_id'])
        if 'confidence' in h:need(isinstance(h['confidence'],dict) and h['confidence'].get('role')=='ADVISORY_ONLY','HOLD_CONFIDENCE_PROMOTION')
        for m in h['mechanisms']:
            need(set(m)=={'candidate_type','mechanism_hypothesis','supporting_edge_refs','contradicting_edge_refs','missing_evidence_to_confirm'},'HOLD_HYPOTHESIS_FIELDS')
            need(m['candidate_type'] in {'STRUCTURAL_BREAK','TIMING_SKEW','STATE_INVERSION','CONCURRENCY_HAZARD'} and text(m['mechanism_hypothesis']),'HOLD_HYPOTHESIS_TYPE')
            need(set(m['supporting_edge_refs']+m['contradicting_edge_refs'])<=known and isinstance(m['missing_evidence_to_confirm'],list),'HOLD_HYPOTHESIS_EVIDENCE')
    need(len(set(ids))==len(ids),'HOLD_HYPOTHESIS_ID_COLLISION')
    return result('PASS_HYPOTHESIS_CONTRACT_ONLY',tool_revision=REVISION,hypotheses=copy.deepcopy(hypotheses),actual_scanner_execution='NOT_CERTIFIED',final_causal_attribution='NOT_GRANTED')

def edge_basis_qualified(edge,a,b):
    if edge['kind'] in INFERRED:return edge['epistemic_state']=='INFERRED'
    if edge['kind']=='SAME_PROCESS_SEQ':return a['process_id']==b['process_id'] and a['clock_domain_id']==b['clock_domain_id'] and strict_int(a['process_seq']) and strict_int(b['process_seq']) and a['process_seq']<b['process_seq']
    if edge['kind']=='MONOTONIC_BEFORE':return a['clock_domain_id']==b['clock_domain_id'] and a['clock_domain_id'] not in UNRESOLVED and number(a['monotonic_time'])<number(b['monotonic_time'])
    basis=edge['basis']
    pair=basis.get('observed_send_receive_pair')
    if isinstance(pair,dict) and pair.get('send_event_id')==a['id'] and pair.get('receive_event_id')==b['id']:return True
    for key in ('explicit_message_sequence','correlation_id','generation_id'):
        value=basis.get(key)
        if text(value) and value not in UNRESOLVED and a.get(key)==value and b.get(key)==value:return True
    return False
