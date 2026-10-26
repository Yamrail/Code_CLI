"""Minimum declared HRRT compiler. Structural PASS is not domain acceptance."""
from .binder import need,text,digest,validate,instant,result,guarded,strict_int
from .semantic import inspect as inspect_semantic
from .drafting import calculate
from .native_bridge import module
REVISION='HRRT_TILE_COMPILER_R002_PRIVATE';SCHEMA='yr.hrrt-tile/1'
STAGES=('PARSE','BIND','TYPECHECK','LINK','STATIC_ANALYSIS','NUMERIC_CHECK','LOD_PRESERVATION_CHECK','EMIT')
BUILD_FIELDS=('source_snapshot_digest','source_artifact_revisions','semantic_core_revision','compiler_revision','compiler_schema_revision','ruleset_revision','fixture_revision','tile_schema_revision','projection_purpose','layer','zoom_level','time_window','coordinate_frame_revision','numeric_backend_revision','numeric_policy_revision','robust_predicate_policy_revision','geometry_kernel_revision','geometric_tolerance_policy_revision','domain_tolerance_policy_revision','rounding_policy_revision','canonical_numeric_serialization_revision')
STATES={'OBSERVED','ASSERTED','INFERRED','DECIDED','UNKNOWN','HOLD','CONFLICT','OPEN'}
def expected_dependencies(d,registry):
    policies=registry.data;core=d['semantic_core'];frame=registry.frame(d['frame_ref'])
    return {'source_snapshot_digest':d['source_ref']['sha256'],'source_artifact_revisions':dict(zip(core['source_artifact_ids'],core['source_revisions'])),'semantic_core_revision':core['semantic_core_revision'],'compiler_revision':REVISION,'compiler_schema_revision':SCHEMA,'ruleset_revision':'HRRT_DECLARED_BINDINGS_R1','fixture_revision':d['fixture_revision'],'tile_schema_revision':SCHEMA,'projection_purpose':d['purpose'],'layer':d['layer'],'zoom_level':d['zoom_level'],'time_window':d['time_window'],'coordinate_frame_revision':frame['coordinate_frame_revision'],'numeric_backend_revision':policies['NUMERIC_POLICY_REGISTRY']['numeric_backend_revision'],'numeric_policy_revision':policies['NUMERIC_POLICY_REGISTRY']['revision'],'robust_predicate_policy_revision':policies['ROBUST_PREDICATE_POLICY']['revision'],'geometry_kernel_revision':'EXACT_RATIONAL_2D_R1','geometric_tolerance_policy_revision':policies['GEOMETRY_TOLERANCE_POLICY']['revision'],'domain_tolerance_policy_revision':policies['GEOMETRY_TOLERANCE_POLICY']['domain_tolerance_ref']['revision'],'rounding_policy_revision':policies['ROUNDING_POLICY_REGISTRY']['revision'],'canonical_numeric_serialization_revision':policies['CANONICAL_NUMERIC_SERIALIZATION']['revision']}
def compile_tile(d,registry,pins,base):return guarded(_compile,d,registry,pins,base)
def _compile(d,registry,pins,base):
    stages=[]
    need(d.get('schema')==SCHEMA and all(k in d for k in ('tile_id','tile_revision','source_ref','semantic_core','projection','purpose','layer','zoom_level','time_window','frame_ref','fixture_revision','build_dependencies','parent_tile_ids','child_tile_ids','cross_tile_edges','epistemic_states','numeric_requests','lod_rollup','state_snapshot')),'E-TYPE-PARSE')
    need(text(d['tile_id']) and text(d['tile_revision']) and text(d['purpose']) and text(d['layer']) and strict_int(d['zoom_level']),'E-TYPE-IDENTITY');stages.append('PARSE')
    need(instant(d['time_window']['start'])<=instant(d['time_window']['end']),'E-TYPE-TIME_WINDOW')
    ref=d['source_ref'];validate(ref,pins.get(ref['artifact_id']),base,{'artifact_id':ref['artifact_id'],'revision':ref['revision']},{'tile_source':pins['$tile_source']})
    for key in ('parent_tile_ids','child_tile_ids','cross_tile_edges','epistemic_states','state_snapshot','numeric_requests','lod_rollup'):
        need(d[key]==pins['$tile_source'][key],'E-REV-SOURCE_CONTAMINATION_'+key)
    expected=expected_dependencies(d,registry);need(set(d['build_dependencies'])==set(BUILD_FIELDS) and d['build_dependencies']==expected,'E-REV-STALE_BUILD_DEPENDENCY');stages.append('BIND')
    semantic=inspect_semantic(d['semantic_core'],d['projection'],pins,base);need(semantic['verdict']=='PASS_RELATION_PRESERVATION_ONLY','E-SEM-'+','.join(semantic['reasons']))
    need(isinstance(d['epistemic_states'],list) and all(s['state'] in STATES for s in d['epistemic_states']),'E-TYPE-EPISTEMIC_ENUM')
    from pathlib import Path
    rg,_=module('revision');arts=[{'artifact_id':r['artifact_id'],'revision':r['revision'],'kind':'SOURCE','status':'OBSERVATION_ONLY','content_sha256':r['sha256'],'immutable_ref':r['sha256']} for r in d['semantic_core']['source_refs']+[ref]]
    unique={a['artifact_id']+'@'+a['revision']:a for a in arts};revision_case={'schema_version':rg.SCHEMA,'inspection_id':d['tile_id'],'required_artifact_ids':list({a['artifact_id'] for a in arts}),'artifacts':list(unique.values()),'dependencies':[],'packages':[]}
    rev_result=rg.audit(revision_case,Path(base));need(rev_result['verdict'] in {'PASS','PASS_WITH_INFO'},'E-REV-EVIDENCE_REVISION_GUARD');stages.append('TYPECHECK')
    ids=d['parent_tile_ids']+d['child_tile_ids']+[d['tile_id']];need(len(set(ids))==len(ids),'E-LINK-TILE_ID_COLLISION')
    need(isinstance(d['numeric_requests'],list),'E-TYPE-NUMERIC_REQUESTS')
    edges=d['cross_tile_edges'];need(isinstance(edges,list) and len({e['id'] for e in edges})==len(edges),'E-LINK-EDGE_COLLISION')
    for edge in edges:need(all(k in edge for k in ('id','from_tile','to_tile','revision','state','evidence_ref')) and text(edge['revision']) and edge['state'] in STATES and edge['evidence_ref'] in {r['artifact_id'] for r in d['semantic_core']['source_refs']},'E-LINK-UNRESOLVED_CROSS_TILE_EDGE')
    need(all(e['from_tile'] in ids and e['to_tile'] in ids for e in edges),'E-LINK-UNBOUND_TILE_ENDPOINT')
    need(d['projection']['semantic_snapshot']['dependency_edges']==d['semantic_core']['dependency_edges'],'E-LINK-DEPENDENCY_LOSS');stages.append('LINK')
    need(d['state_snapshot']==pins['$tile_source']['state_snapshot'],'E-SEM-HOLD_OR_UNKNOWN_LOST');need(d.get('authority_effect')=='NONE' and d.get('canonical_effect')=='NONE' and d.get('human_gate','NOT_EXECUTED')=='NOT_EXECUTED','E-AUTH-ESCALATION');stages.append('STATIC_ANALYSIS')
    calcs=[]
    for request in d['numeric_requests']:
        c=calculate(request,registry,pins,base);need(c['verdict']=='PASS_NUMERIC_CONTRACT_ONLY','E-NUM-'+','.join(c['reasons']));calcs.append(c)
    need(d.get('intermediate_rounding_events',[])==[],'E-NUM-INTERMEDIATE_ROUNDING_UNDECLARED');stages.append('NUMERIC_CHECK')
    retained={s['id'] for s in d['epistemic_states'] if s['state'] in {'UNKNOWN','HOLD','CONFLICT','OPEN'}}
    need(set(d['lod_rollup']['attention_ids'])==retained,'E-LOD-UNCERTAINTY_LOSS');need(set(d['lod_rollup']['cross_edge_ids'])=={e['id'] for e in edges},'E-LOD-CROSS_EDGE_LOSS');stages.append('LOD_PRESERVATION_CHECK')
    tile={'schema':SCHEMA,'subject':{'artifact_id':d['tile_id'],'revision':d['tile_revision']},'state_snapshot':d['state_snapshot'],'build_dependencies':expected,'build_key':digest(expected),'semantic_core_digest':digest(d['semantic_core']),'projection':d['projection'],'parent_tile_ids':d['parent_tile_ids'],'child_tile_ids':d['child_tile_ids'],'cross_tile_edges':edges,'epistemic_states':d['epistemic_states'],'lod_rollup':d['lod_rollup'],'numeric_results':calcs,'source_refs':d['semantic_core']['source_refs']+[ref],'authority_effect':'NONE','canonical_effect':'NONE','human_gate':'NOT_EXECUTED'};stages.append('EMIT')
    return result('PASS_COMPILE_STRUCTURAL_ONLY',tool_revision=REVISION,stages=stages,tile=tile,tile_sha256=digest(tile),dependency_manifest=expected,semantic_result=semantic,evidence_revision_result=rev_result,domain_correctness='NOT_CERTIFIED',human_acceptance='NOT_GRANTED')
