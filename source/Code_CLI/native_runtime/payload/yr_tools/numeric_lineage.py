"""Immutable sidecar/summary joint, derived independently from retained nodes."""
import json
from .binder import need,digest,sha,retained,result,guarded,strict_int,text,validate,validate_set,canonical
from pathlib import Path
REVISION='NUMERIC_LINEAGE_SIDECAR_R005_PRIVATE'
EVENT_FIELDS=('event_id','stage','input_refs','output_refs','quantity_class','unit','operation','tool_revision','formula_or_transform_revision','numeric_backend','precision_mode','coordinate_frame_ref','rounding','numeric_effect','source_revision','evidence_refs')
STAGES={'RAW','UNIT_CONVERSION','COORDINATE_TRANSFORM','COMPUTE','GEOMETRY_PREDICATE','ROUNDING','TOLERANCE_DECISION','CANONICAL_SERIALIZATION','DISPLAY','EMIT'}
DEPENDENCIES=('numeric_policy_revision','rounding_policy_revision','geometry_kernel_revision','robust_predicate_policy_revision','geometric_tolerance_policy_revision','coordinate_frame_revision','canonical_numeric_serialization_revision','execution_environment_ref')
def summarize(graph):
    nodes=graph['nodes'];edges=graph['edges'];need(isinstance(nodes,list) and isinstance(edges,list),'HOLD_LINEAGE_GRAPH_TYPE')
    ids=[n['event_id'] for n in nodes];need(len(set(ids))==len(ids),'HOLD_LINEAGE_NODE_DUPLICATE')
    for e in edges:need(e['from'] in ids and e['to'] in ids,'HOLD_LINEAGE_EDGE_UNBOUND')
    return {'derived_from_sidecar':True,'generator_revision':REVISION,'node_count':len(nodes),'edge_count':len(edges),'material_rounding_count':sum(n.get('material_rounding') is True for n in nodes),'representation_drift_count':sum(n['rounding']['kind']=='binary_representation' and n['rounding']['occurred'] is True for n in nodes),'unstable_topology_count':sum(n.get('topology_state')=='UNSTABLE' for n in nodes),'error_bound_status':'UNKNOWN' if any(n['numeric_effect']['determination']=='UNKNOWN' for n in nodes) else 'BOUNDED' if any(n['numeric_effect']['determination']=='BOUNDED' for n in nodes) else 'EXACT'}
def validate_lineage(entry,pin,base):return guarded(_validate,entry,pin,base)
def _validate(entry,pin,base,_graph_bytes=None):
    need(entry['artifact_id']==pin['artifact_id'] and entry['revision']==pin['revision'],'HOLD_LINEAGE_SUBJECT')
    count=pin.get('material_numeric_transformations');need(strict_int(count),'HOLD_MATERIAL_NUMERIC_COUNT_UNKNOWN')
    line=entry['numeric_lineage'];need(line['state'] in {'PRESENT','NOT_APPLICABLE','DEGRADED'},'HOLD_LINEAGE_STATE')
    need(line['dependencies']==pin['dependencies'] and all(text(line['dependencies'].get(k)) for k in DEPENDENCIES),'HOLD_STALE_NUMERIC_DERIVATION')
    if line['state']=='NOT_APPLICABLE':
        need(pin['material_numeric_transformations']==0 and line.get('reason')=='NO_MATERIAL_NUMERIC_TRANSFORMATION' and line.get('evidence_ref')==pin['no_numeric_evidence_ref'],'HOLD_NUMERIC_LINEAGE_STATE_MISMATCH')
        ref=line.get('evidence_ref');need(isinstance(ref,dict),'HOLD_NO_NUMERIC_EVIDENCE_UNBOUND')
        proof=validate(ref,pin['no_numeric_evidence_pin'],base,pin['no_numeric_evidence_subject'],{'no_material_numeric_transformation':True,'artifact_subject':{'artifact_id':entry['artifact_id'],'revision':entry['revision']}})
        return result('PASS_NO_NUMERIC_TRANSFORMATION_ONLY',tool_revision=REVISION,evidence_sha256=sha(proof['bytes']))
    need(line['state']=='PRESENT','HOLD_NUMERIC_LINEAGE_INCOMPLETE')
    if _graph_bytes is None:_,b=retained(base,line['sidecar']['uri'])
    else:b=_graph_bytes
    need(sha(b)==line['sidecar']['sha256'] and b,'HOLD_NUMERIC_LINEAGE_INCONSISTENT')
    g=json.loads(b);need(g['schema']=='numeric_lineage_graph/v1.0','HOLD_LINEAGE_SCHEMA');need(line['summary']==summarize(g),'HOLD_NUMERIC_LINEAGE_SUMMARY_MISMATCH')
    need(line['sidecar'].get('format')=='numeric_lineage_graph/v1.0','HOLD_LINEAGE_FORMAT')
    need(g.get('artifact_subject')=={'artifact_id':entry['artifact_id'],'revision':entry['revision']} and g.get('dependencies')==line['dependencies'],'HOLD_LINEAGE_SIDECAR_SUBJECT')
    material=[n['event_id'] for n in g['nodes'] if n['stage'] not in {'RAW','DISPLAY','EMIT'}]
    need(len(material)==count and set(material)==set(pin['material_event_ids']) and len(set(pin['material_event_ids']))==count,'HOLD_MATERIAL_NUMERIC_LINEAGE_MISSING')
    env=line['execution_environment_ref'];need(env['artifact_id']==line['dependencies']['execution_environment_ref'],'HOLD_NUMERIC_EXECUTION_ENVIRONMENT_UNBOUND')
    need(env['record_class']=='EXECUTION','HOLD_NUMERIC_ENVIRONMENT_NOT_EXECUTION')
    observed_env=validate(env,pin['execution_environment_pin'],base,pin['execution_environment_subject'])['record']['execution_environment']
    need(isinstance(observed_env,dict) and observed_env.get('origin')=='ACTUAL_RUNTIME_OBSERVATION' and all(text(observed_env.get(k)) for k in ('python','executable','os','machine','numeric_backend','precision_mode')),'HOLD_NUMERIC_EXECUTION_ENVIRONMENT_UNBOUND')
    for n in g['nodes']:
        need(all(k in n for k in EVENT_FIELDS) and n['stage'] in STAGES and all(text(n[k]) for k in ('event_id','quantity_class','unit','operation','tool_revision','formula_or_transform_revision','numeric_backend','precision_mode','source_revision')),'HOLD_LINEAGE_EVENT_FIELDS')
        need(isinstance(n['input_refs'],list) and isinstance(n['output_refs'],list) and n['output_refs'] and isinstance(n['coordinate_frame_ref'],dict),'HOLD_LINEAGE_VALUE_REFERENCES')
        proof=validate_set(n['evidence_refs'],pin['evidence_pins'],base,pin['evidence_subjects'])
        need(proof and all(p['ref']['record_class']=='EXECUTION' and p['record'].get('execution_origin')=='ACTUAL_LOCAL_PROCESS_EXECUTION' for p in proof),'HOLD_LINEAGE_EVENT_NOT_EXECUTED')
        need(any(p['record'].get('numeric_lineage_event')=={k:v for k,v in n.items() if k!='evidence_refs'} for p in proof),'HOLD_LINEAGE_EXECUTION_EVENT_UNBOUND')
        need(n['numeric_backend']==observed_env['numeric_backend'] and n['precision_mode']==observed_env['precision_mode'],'HOLD_LINEAGE_EVENT_EXECUTION_ENVIRONMENT_MISMATCH')
        need(all(k in n['rounding'] for k in ('occurred','kind','policy_ref','mode','digits_or_step')) and n['rounding']['kind'] in {'binary_representation','explicit_rounding','quantization','unit_conversion','coordinate_transform','serialization','display_only'},'HOLD_LINEAGE_ROUNDING_FIELDS')
        need(all(k in n['numeric_effect'] for k in ('observed_delta','ulp_delta','propagated_error_bound','determination')),'HOLD_LINEAGE_NUMERIC_EFFECT_FIELDS')
        need((type(n['rounding']['occurred']) is bool or n['rounding']['occurred']=='UNKNOWN') and n['numeric_effect']['determination'] in {'EXACT','BOUNDED','UNKNOWN'} and type(n.get('material_rounding')) is bool,'HOLD_LINEAGE_ENUM')
        if n['stage'] not in {'RAW','DISPLAY'} and n['rounding']['occurred'] is True:need(n.get('declared_intermediate_rounding_policy') is not None,'HOLD_UNDECLARED_INTERMEDIATE_ROUNDING')
    return result('PASS_NUMERIC_LINEAGE_RETENTION_ONLY',tool_revision=REVISION,sidecar_sha256=sha(b),summary=summarize(g),unknown_error_bound_preserved=line['summary']['error_bound_status']=='UNKNOWN')

def generate_sidecar(subject,dependencies,event_refs,pin,base,destination):return guarded(_generate_sidecar,subject,dependencies,event_refs,pin,base,destination)
def _generate_sidecar(subject,dependencies,event_refs,pin,base,destination):
    need(subject==pin['artifact_subject'] and dependencies==pin['dependencies'],'HOLD_LINEAGE_GENERATOR_SUBJECT')
    bound=validate_set(event_refs,pin['event_pins'],base,pin['event_subjects']);nodes=[]
    for proof in bound:
        event=proof['record']['numeric_lineage_event'];nodes.append({**event,'evidence_refs':[proof['ref']]})
    edges=[]
    for a in nodes:
        for b in nodes:
            if a['event_id']!=b['event_id'] and any(digest(o)==digest(i) for o in a['output_refs'] for i in b['input_refs']):edges.append({'from':a['event_id'],'to':b['event_id']})
    graph={'schema':'numeric_lineage_graph/v1.0','artifact_subject':subject,'dependencies':dependencies,'nodes':nodes,'edges':edges}
    path=(Path(base)/destination).resolve();need(path.is_relative_to(Path(base).resolve()) and not path.exists(),'HOLD_LINEAGE_CREATE_ONLY_DESTINATION')
    # Validate in memory using the exact schema; no file is written on an invalid event chain.
    raw=canonical(graph)
    entry={**subject,'numeric_lineage':{'state':'PRESENT','dependencies':dependencies,'sidecar':{'uri':destination,'sha256':sha(raw),'format':'numeric_lineage_graph/v1.0'},'summary':summarize(graph),'execution_environment_ref':pin['execution_environment_ref']}}
    checked=_validate(entry,pin['validation_pin'],base,raw);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('xb') as handle:handle.write(raw)
    need(path.read_bytes()==raw,'HOLD_LINEAGE_CREATE_READBACK');entry['numeric_lineage']['sidecar']['uri']=path.relative_to(Path(base).resolve()).as_posix()
    return result('PASS_NUMERIC_LINEAGE_GENERATION_RETENTION_ONLY',tool_revision=REVISION,entry=entry,sidecar_sha256=sha(raw),validation=checked)
