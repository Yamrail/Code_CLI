"""Inspect declared meaning bindings; do not infer meaning from token similarity."""
from .binder import need,text,digest,validate_set,no_authority,result,guarded
REVISION='SEMANTIC_CORE_PROJECTION_GUARD_R001_PRIVATE'
CORE_FIELDS=('semantic_core_id','semantic_core_revision','source_artifact_ids','source_revisions','concept_ids','invariant_ids','dependency_edges','authority_state','declared_unknowns','declared_holds','allowed_projection_types','prohibited_mutations')
PROJECTION_FIELDS=('projection_id','projection_revision','parent_semantic_core_id','parent_semantic_core_revision','source_artifact_refs','transformation_id','preserved_invariants','intentionally_omitted_fields','presentation_only_fields','projection_type','semantic_snapshot')
def inspect(core,projection,pins,base):return guarded(_inspect,core,projection,pins,base)
def _inspect(core,p,pins,base):
    need(isinstance(core,dict) and all(k in core for k in CORE_FIELDS),'HOLD_MISSING_SEMANTIC_CORE')
    need(isinstance(p,dict) and all(k in p for k in PROJECTION_FIELDS),'TRANSFORMATION_UNDECLARED')
    for k in ('semantic_core_id','semantic_core_revision'):need(text(core[k]),'HOLD_MISSING_SEMANTIC_CORE')
    cp=pins.get('$core',{});need(cp.get('pin_origin')=='FROZEN_RUNNER_CHECKPOINT' and cp.get('core_digest')==digest(core),'HOLD_DECLARED_CORE_UNBOUND')
    for k in ('source_artifact_ids','source_revisions','concept_ids','invariant_ids','dependency_edges','declared_unknowns','declared_holds','allowed_projection_types','prohibited_mutations'):need(isinstance(core[k],list),'HOLD_SEMANTIC_CORE_TYPE')
    need(p['parent_semantic_core_id']==core['semantic_core_id'],'DRIFT_DETECTED');need(p['parent_semantic_core_revision']==core['semantic_core_revision'],'REVISION_MISMATCH')
    need(p['projection_type'] in core['allowed_projection_types'],'HOLD_UNSUPPORTED_PROJECTION')
    need(text(p['transformation_id']) and text(p['projection_id']) and text(p['projection_revision']),'TRANSFORMATION_UNDECLARED')
    no_authority(core['authority_state']);need(p.get('authority_state')==core['authority_state'],'AUTHORITY_ESCALATION_DETECTED')
    need(all(isinstance(p[k],list) for k in ('preserved_invariants','intentionally_omitted_fields','presentation_only_fields','source_artifact_refs')),'HOLD_PROJECTION_TYPE')
    need(set(core['invariant_ids'])<=set(p['preserved_invariants']),'DRIFT_INVARIANT_LOST')
    need(not set(CORE_FIELDS)&set(p['intentionally_omitted_fields']),'HOLD_OR_UNKNOWN_LOST')
    snap=p['semantic_snapshot'];need(isinstance(snap,dict),'HOLD_AMBIGUOUS_SEMANTIC_BINDING')
    for k in CORE_FIELDS:
        need(k in snap and digest(snap[k])==digest(core[k]),'HOLD_OR_UNKNOWN_LOST' if k in ('declared_holds','declared_unknowns') else 'DEPENDENCY_BREAK' if k=='dependency_edges' else 'DRIFT_'+k.upper())
    for k in ('declared_claim_bindings','units','coordinate_system','numeric_tolerance','language_state','source_language','script_or_orthography','raw_diff_ref','next_action'):
        if k in core:need(k in snap and digest(snap[k])==digest(core[k]),'DRIFT_'+k.upper())
    need(p['source_artifact_refs']==core.get('source_refs'),'SOURCE_TRACE_BROKEN')
    need(len(core['source_artifact_ids'])==len(core['source_revisions'])==len(core.get('source_refs',[])),'HOLD_SOURCE_IDENTITY_SET')
    for id,rev,ref in zip(core['source_artifact_ids'],core['source_revisions'],core['source_refs']):need(ref['artifact_id']==id and ref['revision']==rev,'HOLD_SOURCE_REVISION_CONTINUITY')
    bound=validate_set(core['source_refs'],pins,base)
    claims=core.get('source_claim_bindings');need(isinstance(claims,list) and claims,'HOLD_AMBIGUOUS_SEMANTIC_BINDING')
    import json
    by={r['ref']['artifact_id']:json.loads(r['bytes']) for r in bound}
    for claim in claims:
        value=by[claim['source_artifact_id']]
        need(isinstance(claim['json_path'],list) and claim['json_path'],'HOLD_CLAIM_LOCATOR')
        for key in claim['json_path']:value=value[key]
        need(value==claim['declared_value'],'HOLD_EVIDENCE_CLAIM_MISMATCH')
    return result('PASS_RELATION_PRESERVATION_ONLY',tool_revision=REVISION,relation_state='RELATION_PRESERVED',semantic_core_digest=digest(core),projection_digest=digest(p),preserved_unknowns=core['declared_unknowns'],preserved_holds=core['declared_holds'],human_acceptance='NOT_GRANTED',value_judgment='NOT_PERFORMED')
