"""Create-only local artifact freeze; registration is retention, not adoption."""
import hashlib,json
from pathlib import Path
from .binder import need,text,digest,sha,canonical,validate,retained,no_authority,instant,result,guarded
from .numeric_lineage import validate_lineage
REVISION='ARTIFACT_FREEZE_REGISTER_R003_PRIVATE'
def freeze(d,pin,base):return guarded(_freeze,d,pin,base)
def _freeze(d,pin,base):
    need(d.get('schema')=='yr.artifact-freeze/1' and d.get('operation') in {'copy','move','register_only'},'HOLD_FREEZE_REQUEST')
    no_authority(d);need(pin.get('input_digest')==digest(d),'HOLD_FREEZE_PIN')
    ref=d['source_ref'];validate(ref,pin['source'],base);source,raw=retained(base,ref['locator'])
    state=d['state_snapshot'];validate(d['state_ref'],pin['state'],base,{'artifact_id':ref['artifact_id'],'revision':ref['revision']},{'state_snapshot':state})
    for k in ('known_scope','verified_scope','unknown_points','holds','unresolved_points','not_guaranteed_scope'):
        need(isinstance(state.get(k),dict) and state[k].get('state') in {'OBSERVED','UNKNOWN'} and isinstance(state[k].get('values'),list),'HOLD_TYPED_STATE_SNAPSHOT')
        need(state[k]['state']=='OBSERVED' or state[k]['values']==[],'HOLD_UNKNOWN_STATE_ASSERTION')
    need(d['authority_scope']==pin['authority_scope'] and text(d['authority_ref']),'HOLD_FREEZE_AUTHORITY_BINDING');instant(d['time_anchor']['receipt_time'])
    need(ref['artifact_id']==d['artifact_id'] and ref['revision']==d['revision'],'HOLD_FREEZE_REVISION')
    root=Path(base).resolve();dest=(root/d['destination_path']).resolve();need(dest.is_relative_to(root) and dest!=source,'HOLD_FREEZE_DESTINATION')
    # A source Removal Gate is intentionally separate; this tool never executes it.
    need(d['operation']!='move','HOLD_SOURCE_REMOVAL_REQUIRES_CURRENT_AUTHORITY')
    if d['operation']=='register_only':dest=source
    source_state=None;source_dependencies=None
    try:source_record=json.loads(raw)
    except (ValueError,UnicodeError):source_record={}
    compiled=source_record.get('compiled_tile') if isinstance(source_record,dict) else None
    if isinstance(source_record,dict) and source_record.get('schema')=='yr.hrrt-tile/1':compiled=source_record
    if isinstance(compiled,dict) and ('numeric_results' in compiled or compiled.get('schema')=='yr.hrrt-tile/1'):
        need(compiled.get('schema')=='yr.hrrt-tile/1' and compiled.get('subject')=={'artifact_id':d['artifact_id'],'revision':d['revision']},'HOLD_COMPILED_SOURCE_IDENTITY')
        no_authority(compiled);source_state=compiled['state_snapshot'];source_dependencies=compiled['build_dependencies']
        for source_key,receipt_key in (('unknown','unknown_points'),('holds','holds')):
            need(source_state[source_key]==state[receipt_key]['values'],'HOLD_FREEZE_COMPILED_STATE_LOSS_'+source_key.upper())
        need(source_state['conflicts']+source_state['open_edges']==state['unresolved_points']['values'],'HOLD_FREEZE_COMPILED_OPEN_DEPENDENCY_LOSS')
        need(compiled['cross_tile_edges']==d['downstream_dependencies'],'HOLD_FREEZE_COMPILED_DEPENDENCY_LOSS')
        need(isinstance(compiled['numeric_results'],list),'HOLD_COMPILED_NUMERIC_TYPE')
        if compiled['numeric_results']:need(isinstance(d.get('numeric_lineage_entry'),dict),'HOLD_FREEZE_MATERIAL_NUMERIC_LINEAGE_MISSING')
        need(d.get('numeric_lineage_entry')==compiled.get('numeric_lineage_entry'),'HOLD_FREEZE_SOURCE_LINEAGE_BINDING')
    if pin.get('numeric_lineage') is not None:need(isinstance(d.get('numeric_lineage_entry'),dict),'HOLD_FREEZE_PINNED_NUMERIC_LINEAGE_MISSING')
    if d.get('numeric_lineage_entry') is not None:
        nl=validate_lineage(d['numeric_lineage_entry'],pin['numeric_lineage'],base);need(nl['verdict'] in {'PASS_NUMERIC_LINEAGE_RETENTION_ONLY','PASS_NO_NUMERIC_TRANSFORMATION_ONLY'},'HOLD_FREEZE_NUMERIC_LINEAGE')
    receipt={'schema':'yr.artifact-warranty/1','tool_revision':REVISION,'artifact_id':d['artifact_id'],'revision':d['revision'],'namespace':ref['namespace'],'source_locator':ref['locator'],'storage_locator':str(dest.relative_to(root)).replace('\\','/'),'sha256':sha(raw),'git_blob_sha':hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest(),'bytes':len(raw),'frozen_at_timeanchor':d['time_anchor'],'state_snapshot':state,'authority':{'ref':d['authority_ref'],'scope':d['authority_scope']},'provenance':d['provenance'],'downstream_dependencies':d['downstream_dependencies'],'supersedes':d['supersedes'],'numeric_lineage':d.get('numeric_lineage_entry'),'postcondition':'PASS_BYTES_AND_STATE_RETENTION_ONLY','authority_effect':'NONE','canonical_effect':'NONE','human_gate':'NOT_EXECUTED'}
    receipt['source_state_snapshot']=source_state;receipt['compiled_source_dependencies']=source_dependencies
    register=(root/d['register_path']).resolve();need(register.is_relative_to(root),'HOLD_REGISTER_SCOPE');register.parent.mkdir(parents=True,exist_ok=True)
    identity=(d['artifact_id'],d['revision'],ref['namespace']);previous=[]
    if register.exists():
        previous=[json.loads(s) for s in register.read_text(encoding='utf-8').splitlines() if s]
        for r in previous:
            if (r['artifact_id'],r['revision'],r['namespace'])==identity:
                need(r==receipt,'HOLD_SAME_REVISION_FREEZE_SNAPSHOT_COLLISION');need(dest.is_file() and dest.read_bytes()==raw,'HOLD_FREEZE_POST_READBACK');return result('PASS_ARTIFACT_FREEZE_RETENTION_ONLY',tool_revision=REVISION,receipt=receipt,registration_state='IDEMPOTENT_EXISTING_FROZEN_ENTRY',moot_production_wiring='NOT_EXECUTED')
    if d['operation']=='copy':
        if dest.exists():need(dest.is_file() and dest.read_bytes()==raw,'HOLD_SAME_REVISION_DESTINATION_COLLISION')
        else:
            dest.parent.mkdir(parents=True,exist_ok=True)
            with dest.open('xb') as out:out.write(raw)
    need(dest.read_bytes()==raw,'HOLD_FREEZE_POST_READBACK')
    with register.open('ab') as f:f.write(canonical(receipt)+b'\n')
    need(json.loads(register.read_bytes().splitlines()[-1])==receipt,'HOLD_REGISTER_POST_READBACK')
    return result('PASS_ARTIFACT_FREEZE_RETENTION_ONLY',tool_revision=REVISION,receipt=receipt,registration_state='APPENDED_ONCE_LOCAL_NONCANONICAL',moot_production_wiring='NOT_EXECUTED',truth='NOT_CERTIFIED',human_acceptance='NOT_GRANTED')
