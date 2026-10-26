"""Structural UGC warning/provenance inspector; no legal determination."""
from .binder import need,digest,text,validate,instant,result,guarded
REVISION='CULTURAL_UGC_BOUNDARY_GUARD_R001_PRIVATE'
LAYERS={'LAW','RIGHTSHOLDER_GUIDELINE','EVENT_RULE','PLATFORM_RULE','COMMUNITY_NORM','OBSERVED_PRACTICE'}
STATES={'OBSERVED','INFERENCE','REVIEW_REQUIRED','WARN','HOLD','USER_PROCEED_NONCANONICAL','RIGHTS_CLEARANCE_REQUIRED','CANCELLED'}
AXES=('source_provenance','jurisdiction_effective_date','copyright_expression','derivative_work','trademark_brand','design_product_asset','choreography_performance','voice_engine_library_provider','persona_living_person','privacy_impersonation','event_zoning','platform_distribution','community_official_canon','testimony_fact_fiction','commerciality_scale_route','authority_publication_canonical')
NODES={'ORIGINAL_WORK','OFFICIAL_ASSET','CHARACTER','PERSON','PERSONA','MODEL_ASSET','VOICE_ENGINE','VOICE_LIBRARY','PERFORMANCE','CHOREOGRAPHY','DATASET','BOOK','COMMUNITY_DERIVATIVE','MEME','TRANSFORMED_PROMPT','GENERATED_ARTIFACT'}
EDGES={'DERIVED_FROM','REFERENCES','TRANSFORMS','DECOMPOSES_TO_FEATURES','COMMUNITY_NAMED','COMMUNITY_MUTATED','USES_MODEL_ASSET','USES_VOICE_LIBRARY','QUOTES','DISTRIBUTES_VIA'}
def inspect(d,pin,base):return guarded(_inspect,d,pin,base)
def _inspect(d,pin,base):
    need(digest(d)==pin['input_digest'] and d['artifact_identity']==pin['artifact_identity'],'HOLD_ARTIFACT_REVISION');need(set(d['axes'])==set(AXES),'HOLD_AXIS_SCALARIZATION')
    need(d['axes']==pin['axes'],'HOLD_SOURCE_AXIS_CONFLICT');need(d['gate_state'] in STATES,'HOLD_GATE_ENUM')
    need(d.get('final_legal_determination') is None and d.get('publication_effect')=='NONE' and d.get('canonical_effect')=='NONE','HOLD_LEGAL_OR_PUBLICATION_AUTHORITY_LEAK')
    source_ids=[]
    for s in d['source_nodes']:
        need(all(k in s for k in ('source_id','authority_layer','jurisdiction','effective_at','retrieved_at','revision_or_date','locator','content_hash','scope','status','ref')),'HOLD_SOURCE_FIELDS');need(s['authority_layer'] in LAYERS and s['status'] in {'OBSERVED','UNKNOWN','HOLD','SUPERSEDED'},'HOLD_SOURCE_LAYER_OR_ENUM');instant(s['retrieved_at'])
        need(s['effective_at']=='UNKNOWN' or instant(s['effective_at']) is not None,'HOLD_SOURCE_EFFECTIVE_TIME');need(s['ref']['sha256']==s['content_hash'] and s['ref']['locator']==s['locator'],'HOLD_SOURCE_HASH');validate(s['ref'],pin['source_pins'][s['ref']['artifact_id']],base,pin['source_subjects'][s['ref']['artifact_id']],{'source_node':{k:v for k,v in s.items() if k not in {'ref','locator','content_hash'}}});source_ids.append(s['source_id'])
    need(len(set(source_ids))==len(source_ids),'HOLD_SOURCE_COLLISION');ids=[n['id'] for n in d['provenance_nodes']];need(len(set(ids))==len(ids) and all(n['type'] in NODES for n in d['provenance_nodes']),'HOLD_PROVENANCE_NODE')
    for e in d['provenance_edges']:need(e['from'] in ids and e['to'] in ids and e['kind'] in EDGES and e['source_id'] in source_ids,'HOLD_PROVENANCE_EDGE')
    need(d['provenance_edges']==pin['provenance_edges'] and d['transformation_history']==pin['transformation_history'],'HOLD_TRANSFORM_PROVENANCE_LOSS')
    if d['transformation_history']:need(d['reinspection_identity']==d['artifact_identity'] and d['reinspection_input_sha256']==pin['current_transformed_input_sha256'],'HOLD_OLD_GATE_NEW_TRANSFORM')
    need(d['hold_ids']==pin['hold_ids'] and d['warning_ids']==pin['warning_ids'],'HOLD_WARNING_OR_HOLD_ERASURE')
    decision=d['human_decision']
    if decision is not None:
        need(decision['decision'] in {'PROCEED','REVISE','CANCEL'} and decision['authority']=='USER' and decision['yamrail_publication_authorized'] is False,'HOLD_HUMAN_DECISION_BOUNDARY')
        ref=d['human_decision_ref'];validate(ref,pin['human_decision_pin'],base,pin['human_decision_subject'],{'human_decision':decision})
        need(set(d['warning_ids'])<=set(decision['acknowledges_warning_ids']),'HOLD_WARNING_ACK_MISSING')
    need(d['gate_state']!='USER_PROCEED_NONCANONICAL' or decision is not None and decision['decision']=='PROCEED','HOLD_USER_PROCEED_NOT_BOUND')
    return result('PASS_CULTURAL_STRUCTURE_ONLY',tool_revision=REVISION,gate_event={'artifact_identity':d['artifact_identity'],'input_hash':digest(d),'source_nodes':d['source_nodes'],'provenance_edges':d['provenance_edges'],'authority_layers_seen':sorted({s['authority_layer'] for s in d['source_nodes']}),'jurisdictions_seen':sorted({s['jurisdiction'] for s in d['source_nodes']}),'warning_ids':d['warning_ids'],'hold_ids':d['hold_ids'],'transformation_history':d['transformation_history'],'gate_state':d['gate_state'],'canonical_effect':'NONE','publication_effect':'NONE'},legal_determination='NOT_PERFORMED',user_proceed_does_not_clear_holds=True)
