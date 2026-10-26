"""Inspect emitted tiles against frozen source; compiler status is not evidence."""
from .binder import need,digest,result,guarded,validate
from .drafting import calculate
from .compiler import expected_dependencies,STAGES,SCHEMA
from .semantic import inspect
REVISION='HRRT_TILE_INSPECTOR_R004_PRIVATE'
def inspect_tile(tile,source,registry,pins,base):return guarded(_inspect,tile,source,registry,pins,base)
def _inspect(t,d,r,pins,base):
    need(t.get('schema')==d.get('schema')==SCHEMA,'E-TYPE-INSPECTOR_SCHEMA')
    need(d['numeric_requests']==pins['$tile_source']['numeric_requests'],'E-NUM-INSPECTOR_SOURCE_REQUEST_LOSS')
    need(d.get('authority_effect')=='NONE' and d.get('canonical_effect')=='NONE' and d.get('human_gate','NOT_EXECUTED')=='NOT_EXECUTED','E-AUTH-INSPECTOR_SOURCE_ESCALATION')
    ref=d['source_ref'];validate(ref,pins.get(ref['artifact_id']),base,{'artifact_id':ref['artifact_id'],'revision':ref['revision']},{'tile_source':pins['$tile_source']})
    expected=expected_dependencies(d,r);need(t['build_dependencies']==expected and t['build_key']==digest(expected),'E-REV-INSPECTOR_STALE')
    need(t['subject']=={'artifact_id':d['tile_id'],'revision':d['tile_revision']},'E-REV-INSPECTOR_SUBJECT')
    need(t['semantic_core_digest']==digest(d['semantic_core']),'E-SEM-INSPECTOR_CORE')
    sem=inspect(d['semantic_core'],t['projection'],pins,base);need(sem['verdict']=='PASS_RELATION_PRESERVATION_ONLY','E-SEM-INSPECTOR_PROJECTION')
    for key in ('parent_tile_ids','child_tile_ids','cross_tile_edges','epistemic_states','lod_rollup','state_snapshot'):
        need(t[key]==d[key] and d[key]==pins['$tile_source'][key],'E-LOD-INSPECTOR_LOSS_'+key)
    need(t['authority_effect']=='NONE' and t['canonical_effect']=='NONE' and t['human_gate']=='NOT_EXECUTED','E-AUTH-INSPECTOR_ESCALATION')
    need(t['source_refs']==d['semantic_core']['source_refs']+[d['source_ref']],'E-PROV-INSPECTOR_SOURCE_TRACE')
    need(len(t['numeric_results'])==len(d['numeric_requests']),'E-NUM-INSPECTOR_COUNT')
    for c,request in zip(t['numeric_results'],d['numeric_requests']):
        recomputed=calculate(request,r,pins,base);need(recomputed['verdict']=='PASS_NUMERIC_CONTRACT_ONLY' and c==recomputed,'E-NUM-INSPECTOR_RESULT_MISMATCH')
        need(c['source_revision']==request['source_ref']['revision'] and c['registry_sha256']==r.sha256,'E-NUM-INSPECTOR_REVISION')
        need(all(e['stage']=='DISPLAY' and e['rounding']['kind']=='display_only' for e in c['numeric_lineage']),'E-NUM-INSPECTOR_ROUNDING')
    if t.get('numeric_lineage_entry') is not None or pins.get('$numeric_lineage') is not None:
        from .numeric_lineage import validate_lineage,DEPENDENCIES
        entry=t['numeric_lineage_entry'];need({'artifact_id':entry['artifact_id'],'revision':entry['revision']}==t['subject'],'E-NUM-INSPECTOR_LINEAGE_SUBJECT')
        need(all(entry['numeric_lineage']['dependencies'][k]==expected[k] for k in DEPENDENCIES if k!='execution_environment_ref'),'E-NUM-INSPECTOR_LINEAGE_DEPENDENCY')
        lineage=validate_lineage(entry,pins['$numeric_lineage'],base);need(lineage['verdict'] in {'PASS_NUMERIC_LINEAGE_RETENTION_ONLY','PASS_NO_NUMERIC_TRANSFORMATION_ONLY'},'E-NUM-INSPECTOR_LINEAGE_BINDING')
    return result('PASS_TILE_INSPECTION_STRUCTURAL_ONLY',tool_revision=REVISION,tile_sha256=digest(t),build_key=t['build_key'],preserved_state_snapshot=t['state_snapshot'],source_traceable=True,semantic_result=sem,human_acceptance='NOT_GRANTED')
