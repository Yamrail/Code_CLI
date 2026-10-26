"""Declared HumanEventLedger structure and derived projection; no legal determinations."""
import copy
from .binder import need,text,known_identity,instant,validate,result,guarded,no_authority,digest
from .event_graph import IDENTITIES,cycle_nodes
REVISION='HUMAN_EVENT_LEDGER_PROJECTION_ADAPTER_R005_PRIVATE'
EPISTEMIC={'OBSERVED','ASSERTED','DECIDED','INFERRED','CONFLICTING','UNKNOWN','UNREGISTERED','LOOKUP_FAILED'}
RECORD_STATES={'ACTIVE','ABSENT','DESTROYED','RECONSTRUCTED','CORRECTED','REVOKED','SUPERSEDED','UNKNOWN'}
RECOGNITION={'RECOGNIZED','PARTIALLY_RECOGNIZED','NOT_RECOGNIZED','CONTESTED','UNKNOWN'}
DEPENDENCIES={'CARE','ECONOMIC','GENETIC_PARENTAGE','GESTATIONAL_PARENTAGE','LEGAL_PARENTAGE','RESIDENCE','NATIONALITY','PROTECTION_STATUS','ASSET_TITLE','SOVEREIGN_CLAIM','DECISION_AUTHORITY','RECORD_ACCESS','TRAVEL_DOCUMENT','CHILD_LOCATION','HABITUAL_RESIDENCE','PHYSICAL_CUSTODY','LEGAL_CUSTODY','PARENTAL_AUTHORITY','TRAVEL_OR_RELOCATION_CONSENT','RETURN_PROCEEDING','CUSTODY_PROCEEDING','PROTECTIVE_ORDER','CRIMINAL_PROCESS','FOREIGN_PROCESS','JURISDICTION','LOCATION_CONFIDENTIALITY','NAVIGATION_ASSISTANCE','TRANSPORT_SUPPORT','APPOINTMENT_ACCOMPANIMENT','PEER_INTERPRETATION','PROCEDURAL_REFERRAL','HOUSING_REFERRAL','EMPLOYMENT_REFERRAL','EMERGENCY_CONTACT','TEMPORARY_LODGING','COMMUNITY_BRIDGE','TRUSTED_REFERRAL'}
RELATIONS={'GENETIC_PARENTAGE','GESTATIONAL_PARENTAGE','LEGAL_PARENTAGE','CARE','COHABITATION','ROMANTIC','MARRIAGE_OR_UNION','ECONOMIC_DEPENDENCY','RESIDENCE','ASSET_TITLE','EXECUTORSHIP','BENEFICIARY','GUARDIANSHIP'}
CLOCKS=('event_time','legal_effective_time','decision_time','record_time','observer_time','valid_from','valid_to')
REQUIRED={
 'identity':('person_id','identity_binding_state'),
 'event':('event_id','event_type','event_actor_refs','event_object_refs','affected_dependency_types','unaffected_dependency_types'),
 'authority':('authority_entity','jurisdiction','authority_basis','law_or_rule_version','decision_scope','authority_state'),
 'evidence':('source_ref','source_type','provenance','transformation_history','supporting_refs','contradicting_refs','missing_evidence','epistemic_state'),
 'record_surface':('record_system','record_status','record_origin','record_authority','record_loss_or_reconstruction_state'),
 'legal_state':('asserted_state','decided_state','current_projection')}
PROFILES={
 'inheritance':{'DEATH','LEGAL_PARENTAGE','MARRIAGE_OR_UNION','WILL_OR_TESTAMENT','ASSET_TITLE','EXECUTORSHIP','BENEFICIARY','SOVEREIGN_OR_COURT_AUTHORITY','EVIDENCE_PROVENANCE'},
 'nationality':{'BIRTH','NATIONALITY_EVENTS','RESIDENCE','SOVEREIGN_CLAIM','PROTECTION_STATUS','RECORD_SURFACE','AUTHORITY_RECOGNITION'},
 'care':{'CARE','ECONOMIC_DEPENDENCY','LEGAL_PARENTAGE','GUARDIANSHIP','DEATH_OR_INCAPACITY','FALLBACK_DEPENDENCY'},
 'family_relationship':{'GENETIC_PARENTAGE','GESTATIONAL_PARENTAGE','LEGAL_PARENTAGE','CARE','COHABITATION','ROMANTIC','MARRIAGE_OR_UNION'}}
def required(d,keys,reason):need(isinstance(d,dict) and all(k in d for k in keys),reason)
def inspect(ledger,pin,base,query=None):return guarded(_inspect,ledger,pin,base,query)
def _inspect(d,pin,base,query):
    need(d.get('schema')=='yr.human-event-ledger/1' and text(d.get('artifact_id')) and text(d.get('revision')),'HOLD_LEDGER_SCHEMA');no_authority(d)
    ref=d['source_ref'];payload={k:v for k,v in d.items() if k!='source_ref'}
    validate(ref,pin['source_pin'],base,pin['source_subject'],{'ledger_input':payload})
    events=d['events'];need(isinstance(events,list),'HOLD_LEDGER_EVENTS_TYPE');ids=[e['event']['event_id'] for e in events]
    need(len(set(ids))==len(ids) and all(text(i) for i in ids),'HOLD_LEDGER_EVENT_COLLISION')
    prior=pin.get('previous_events');need(isinstance(prior,list) and events[:len(prior)]==prior,'HOLD_LEDGER_HISTORY_REWRITE')
    unknown=[];persons=set();evidence_ids=[]
    for e in events:
        for plane,fields in REQUIRED.items():required(e.get(plane),fields,'HOLD_LEDGER_REQUIRED_'+plane)
        ident=e['identity'];need(text(ident['person_id']) and ident['identity_binding_state'] in IDENTITIES,'HOLD_LEDGER_IDENTITY_ENUM');persons.add(ident['person_id'])
        if ident['identity_binding_state'] in {'UNKNOWN','UNREGISTERED','LOOKUP_FAILED','CONFLICTING'}:unknown.append({'event_id':e['event']['event_id'],'plane':'identity','state':ident['identity_binding_state']})
        ev=e['event'];need(text(ev['event_type']) and isinstance(ev['event_actor_refs'],list) and isinstance(ev['event_object_refs'],list),'HOLD_LEDGER_EVENT_TYPE')
        a,u=ev['affected_dependency_types'],ev['unaffected_dependency_types'];need(isinstance(a,list) and isinstance(u,list) and set(a+u)<=DEPENDENCIES and not set(a)&set(u),'HOLD_DEPENDENCY_SCOPE_CONFLATION')
        temporal=e['temporal'];required(temporal,CLOCKS,'HOLD_LEDGER_CLOCK_DROPOUT')
        for clock in CLOCKS:
            value=temporal[clock]
            if value=='UNKNOWN':unknown.append({'event_id':ev['event_id'],'plane':clock,'state':'UNKNOWN'})
            else:instant(value)
        if temporal['valid_from']!='UNKNOWN' and temporal['valid_to']!='UNKNOWN':need(instant(temporal['valid_from'])<=instant(temporal['valid_to']),'HOLD_LEDGER_VALID_TIME_REVERSED')
        auth=e['authority'];need(all(text(auth[k]) for k in REQUIRED['authority']),'HOLD_LEDGER_AUTHORITY_VALUE')
        evidence=e['evidence'];need(evidence['epistemic_state'] in EPISTEMIC and text(evidence['source_type']) and text(evidence['provenance']),'HOLD_LEDGER_EVIDENCE_STATE')
        for key in ('transformation_history','supporting_refs','contradicting_refs','missing_evidence'):need(isinstance(evidence[key],list),'HOLD_LEDGER_EVIDENCE_TYPE')
        er=evidence['source_ref'];bound_event=copy.deepcopy(e);bound_event['evidence'].pop('source_ref');validate(er,pin['evidence_pins'][er['artifact_id']],base,pin['evidence_subjects'][er['artifact_id']],{'event_record':bound_event});evidence_ids.append(er['artifact_id'])
        for er in evidence['supporting_refs']+evidence['contradicting_refs']:validate(er,pin['evidence_pins'][er['artifact_id']],base,pin['evidence_subjects'][er['artifact_id']])
        if evidence['transformation_history']:
            for t in evidence['transformation_history']:
                required(t,('original_ref','transformed_ref','transformer','kind','conflict_of_interest'),'HOLD_TRANSFORMATION_CHANNEL_UNBOUND')
                need(t['original_ref']!=t['transformed_ref'] and text(t['transformer']) and text(t['kind']),'HOLD_ORIGINAL_TRANSFORMED_CONFLATION')
                for key in ('original_ref','transformed_ref'):
                    er=t[key];validate(er,pin['evidence_pins'][er['artifact_id']],base,pin['evidence_subjects'][er['artifact_id']])
        surface=e['record_surface'];need(surface['record_status'] in RECORD_STATES,'HOLD_RECORD_SURFACE_STATE')
        for relation in e.get('relations',[]):
            required(relation,('relation_type','valid_from','valid_to','source_refs','epistemic_state'),'HOLD_LEDGER_RELATION_FIELDS');need(relation['relation_type'] in RELATIONS and relation['epistemic_state'] in EPISTEMIC,'HOLD_LEDGER_RELATION_ENUM')
            for clock in ('valid_from','valid_to'):
                if relation[clock]=='UNKNOWN':unknown.append({'event_id':ev['event_id'],'plane':'relation_'+clock,'state':'UNKNOWN'})
                else:instant(relation[clock])
            if relation['valid_from']!='UNKNOWN' and relation['valid_to']!='UNKNOWN':need(instant(relation['valid_from'])<=instant(relation['valid_to']),'HOLD_RELATION_VALID_TIME_REVERSED')
            for er in relation['source_refs']:validate(er,pin['evidence_pins'][er['artifact_id']],base,pin['evidence_subjects'][er['artifact_id']])
        for r in e.get('recognitions',[]):
            required(r,('issuer_entity','observer_jurisdiction','scope','recognition_status','valid_from','valid_to','source_ref'),'HOLD_RECOGNITION_FIELDS');need(r['recognition_status'] in RECOGNITION,'HOLD_RECOGNITION_STATE')
            er=r['source_ref'];validate(er,pin['evidence_pins'][er['artifact_id']],base,pin['evidence_subjects'][er['artifact_id']])
        if 'proceeding' in e:
            p=e['proceeding'];required(p,('proceeding_id','forum','jurisdiction','case_or_docket_ref','stage','opened_at','current_status'),'HOLD_PROCEEDING_FIELDS')
            need(p['stage'] in {'PRE_ACTION','PENDING','INTERIM','FIRST_INSTANCE','APPEAL','REMAND','FINAL','ENFORCEMENT','CLOSED','UNKNOWN'},'HOLD_PROCEEDING_STAGE')
            for pos in p.get('party_positions',[]):
                required(pos,('party_ref','role','position_type','assertion','source_ref','effective_from','effective_to'),'HOLD_PARTY_POSITION_FIELDS');need(pos['position_type'] in {'CLAIM','ALLEGATION','ADMISSION','DENIAL','DEFENSE','COUNTERCLAIM','WITHDRAWAL','UNKNOWN'},'HOLD_PARTY_POSITION_STATE')
            for issue in p.get('issues',[]):required(issue,('issue_id','question','materiality','status'),'HOLD_ISSUE_FIELDS');need(issue['status'] in {'DISPUTED','UNDISPUTED','RESOLVED_NONFINAL','RESOLVED_FINAL','MOOT','UNKNOWN'},'HOLD_ISSUE_STATE')
            proof=p['proof'];required(proof,('burden_holder','standard_of_proof','presumption','rebuttal_status','evidence_refs','excluded_or_unavailable_evidence_refs'),'HOLD_PROCEDURAL_PROOF_FIELDS')
            for er in proof['evidence_refs']+proof['excluded_or_unavailable_evidence_refs']:validate(er,pin['evidence_pins'][er['artifact_id']],base,pin['evidence_subjects'][er['artifact_id']])
            for key in ('burden_holder','standard_of_proof','presumption','rebuttal_status'):
                if proof[key]=='UNKNOWN':unknown.append({'event_id':ev['event_id'],'plane':key,'state':'UNKNOWN'})
            layers=p['decision_layers'];required(layers,('finding_of_fact','holding','order','scope','finality','appeal_status','stay_status','enforceability','bound_party_scope','bound_subject_matter_scope','third_party_effect'),'HOLD_DECISION_LAYERS_FIELDS')
            need(layers['finality'] in {'NONFINAL','PARTIALLY_FINAL','FINAL','VACATED','SET_ASIDE','UNKNOWN'} and layers['appeal_status'] in {'NOT_AVAILABLE','AVAILABLE_NOT_FILED','FILED','PENDING','DISMISSED','RESOLVED','UNKNOWN'} and layers['enforceability'] in {'NOT_ENFORCEABLE','PROVISIONALLY_ENFORCEABLE','ENFORCEABLE','STAYED','UNKNOWN'},'HOLD_DECISION_ENUM')
            unknown.append({'event_id':ev['event_id'],'plane':'binding_effect','state':'HOLD_LOCAL_AUTHORITY_REQUIRED','proceeding':copy.deepcopy(p)})
    edges=d.get('dependency_edges');need(isinstance(edges,list),'HOLD_LEDGER_DEPENDENCY_TYPE')
    for edge in edges:need(edge['from'] in ids and edge['to'] in ids and edge['dependency_type'] in DEPENDENCIES and edge['epistemic_state'] in EPISTEMIC,'HOLD_LEDGER_DEPENDENCY_UNBOUND')
    edge_ids=[edge['id'] for edge in edges];need(all(text(i) for i in edge_ids) and len(set(edge_ids))==len(edge_ids),'HOLD_LEDGER_DEPENDENCY_IDENTITY')
    unknown.extend(_extensions(d,pin,base))
    cycles=cycle_nodes(ids,edges)
    if query is None:return result('PASS_LEDGER_RETENTION_ONLY',tool_revision=REVISION,ledger_digest=digest(payload),retained_event_ids=ids,person_ids=sorted(persons),unknowns=unknown,cycles=cycles,legal_effect='NOT_DETERMINED',source_history_preserved=True)
    required(query,('purpose','valid_time','observer_time','jurisdiction','law_version','binding_effect'),'HOLD_PROJECTION_QUERY_FIELDS')
    need(query['purpose'] in PROFILES and type(query['binding_effect']) is bool and text(query['jurisdiction']) and text(query['law_version']),'HOLD_PROJECTION_QUERY_TYPE')
    valid=instant(query['valid_time']);observed=instant(query['observer_time']);selected=[];projection_holds=[]
    for e in events:
        ev=e['event'];a=e['authority'];t=e['temporal']
        if a['jurisdiction']!=query['jurisdiction']:continue
        if ev['event_type'] not in PROFILES[query['purpose']]:continue
        if a['law_or_rule_version']!=query['law_version']:projection_holds.append({'event_id':ev['event_id'],'state':'HOLD_LAW_VERSION_MAPPING_UNKNOWN'})
        if any(t[k]=='UNKNOWN' for k in ('valid_from','valid_to','observer_time')):projection_holds.append({'event_id':ev['event_id'],'state':'HOLD_PROJECTION_TIME_UNKNOWN'});selected.append(copy.deepcopy(e));continue
        if instant(t['valid_from'])<=valid<=instant(t['valid_to']) and instant(t['observer_time'])<=observed:selected.append(copy.deepcopy(e))
    selected_ids={e['event']['event_id'] for e in selected};projected_edges=[copy.deepcopy(e) for e in edges if e['from'] in selected_ids and e['to'] in selected_ids]
    if query['binding_effect']:projection_holds.append({'state':'HOLD_LOCAL_AUTHORITY_REQUIRED','scope':'BINDING_EFFECT'})
    return result('HOLD_LOCAL_AUTHORITY_REQUIRED' if query['binding_effect'] else 'HOLD_PROJECTION_BINDING' if projection_holds else 'PASS_LEDGER_PROJECTION_STRUCTURAL_ONLY',tool_revision=REVISION,query=copy.deepcopy(query),source_ledger_digest=digest(payload),events=selected,dependency_edges=projected_edges,unknowns=unknown,holds=projection_holds,cycles_preserved=cycles,legal_effect='NOT_DETERMINED',history_mutated=False)


# These are the existing Human/Child/Sakae/Kabukicho workfaces, not another graph engine.
SUPPORT_TYPES={'NAVIGATION_ASSISTANCE','TRANSPORT_OR_RIDE_SUPPORT','APPOINTMENT_ACCOMPANIMENT','PEER_INTERPRETATION','DOCUMENT_READING_ASSISTANCE','PROCEDURAL_REFERRAL','HOUSING_REFERRAL','EMPLOYMENT_REFERRAL','EMERGENCY_CONTACT','TEMPORARY_LODGING','SHORT_TERM_FINANCIAL_ASSISTANCE','CHILDCARE_OR_DEPENDENT_SUPPORT','SOCIAL_EVENT_INVITATION','COMMUNITY_BRIDGE'}
SUPPORT_FIELDS=('support_edge_id','provider_ref','recipient_ref','support_type','observed_at','valid_from','valid_to','availability_state','source_ref','privacy_classification')
LEGAL_NAMEPLATE=('source_ref','source_type','jurisdiction','authority_entity','authority_basis','law_or_rule_version','valid_from','valid_to','decision_time','record_time','epistemic_state','conflict_state')
PROCEDURAL_NAMEPLATE=('proceeding_id','forum','jurisdiction','stage','decision_date','finality','appeal_status','stay_status','enforceability','bound_party_scope','bound_subject_matter_scope')
CHILD_PLANES=('PERSON_ID','DATE_OF_BIRTH','NATIONALITY_HISTORY','TRAVEL_DOCUMENT_STATUS','CURRENT_LOCATION_STATUS','LOCATION_CONFIDENTIALITY','HABITUAL_RESIDENCE_CLAIMS','BORDER_CROSSING_HISTORY','PHYSICAL_CUSTODY','LEGAL_CUSTODY','PARENTAL_AUTHORITY','CARE_HISTORY','TRAVEL_OR_RELOCATION_CONSENT','FAMILY_OR_CUSTODY_PROCEEDING','RETURN_PROCEEDING','PROTECTIVE_PROCEEDING','CRIMINAL_PROCEEDING','IMMIGRATION_OR_TRAVEL_DOCUMENT_PROCEEDING','FOREIGN_ENFORCEMENT_OR_EXTRADITION_PROCEEDING','ISSUING_AUTHORITY','JURISDICTION','AUTHORITY_BASIS','LAW_OR_RULE_VERSION','DECISION_SCOPE','DOMESTIC_RECOGNITION_OR_ENFORCEMENT_STATUS')
KAB_PLANES=('PERSON_CONTINUITY','HERITAGE_IF_RELEVANT_AND_SEPARATELY_SOURCED','NATIONALITY_HISTORY','PHYSICAL_LOCATION','RESIDENCE_OR_STAY_STATUS','IMMIGRATION_PROCEEDING','CONSENT_EVENT_HISTORY','COERCION_OR_CONTROL_INDICATORS','DOCUMENT_CONTROL','ABILITY_TO_EXIT','GESTATIONAL_RELATION','GENETIC_RELATION','INTENDED_PARENT_RELATION','LEGAL_PARENTAGE_PROJECTION','CARE','MEDICAL_CARE','INDEPENDENT_INTEREST_REPRESENTATION','NATIONALITY','TRAVEL_DOCUMENT','JURISDICTION','SUBNATIONAL_JURISDICTION','AUTHORITY_ENTITY','LAW_VERSION','PROCEEDING_STATE','SOURCE_REF','PROVENANCE','TRANSFORMATION_HISTORY','SUPPORTING_AND_CONTRADICTING_REFS','CARE_COST','MEDICAL_COST','CONTRACTUAL_PAYMENT','SUPPORT_OR_RECOURSE_CLAIM','FINAL_LIABILITY_IF_AND_WHEN_RESOLVED')
SENSITIVE_FIELDS={'exact_child_location','exact_home_address','helper_identity','community_meeting_location','religious_or_ethnic_affiliation','informal_support_contact','travel_pattern'}
PROHIBITED_COEFFICIENTS={'SEX','NATIONALITY','ETHNICITY','RELIGION','HERITAGE','SEX_WORK','IRREGULAR_MIGRATION'}

def _proof(ref,pin,base,key,value):
    return validate(ref,pin['evidence_pins'][ref['artifact_id']],base,pin['evidence_subjects'][ref['artifact_id']],{key:value})

def _extensions(d,pin,base,query=None):
    holds=[];supports=d.get('support_edges',[]);ids=[]
    need(isinstance(supports,list),'HOLD_SUPPORT_TYPE')
    for edge in supports:
        required(edge,SUPPORT_FIELDS,'HOLD_SUPPORT_FIELDS');ids.append(edge['support_edge_id'])
        need(all(text(edge[k]) for k in ('support_edge_id','provider_ref','recipient_ref','privacy_classification')) and edge['support_type'] in SUPPORT_TYPES and edge['availability_state'] in {'AVAILABLE','TEMPORARILY_UNAVAILABLE','ENDED','UNKNOWN'},'HOLD_SUPPORT_ENUM')
        need(instant(edge['valid_from'])<=instant(edge['valid_to']),'HOLD_SUPPORT_VALID_TIME');instant(edge['observed_at'])
        _proof(edge['source_ref'],pin,base,'support_edge_observation',{k:v for k,v in edge.items() if k!='source_ref'})
        need(edge.get('inferred_from_demographic') is False and edge.get('decision_authority')=='NONE','HOLD_SUPPORT_AUTHORITY_OR_DEMOGRAPHIC_PROMOTION')
        if edge.get('promoted_from_weak_tie') is True:
            transition=edge.get('transition_ref');need(isinstance(transition,dict),'HOLD_WEAK_TIE_PROMOTION_BASIS_MISSING')
            _proof(transition,pin,base,'observed_support_transition',{'support_edge_id':edge['support_edge_id'],'support_type':edge['support_type'],'epistemic_state':'OBSERVED'})
        if edge.get('edge_effect_state') is not None:need(edge['edge_effect_state'] in {'SUPPORTIVE_OBSERVED','BURDENSOME_OBSERVED','CONFLICTING','UNKNOWN'},'HOLD_SUPPORT_EFFECT_STATE')
        if edge['availability_state']=='UNKNOWN' or edge.get('edge_effect_state') in {'CONFLICTING','UNKNOWN'}:holds.append({'support_edge_id':edge['support_edge_id'],'state':'HOLD_SUPPORT_EFFECT_OR_AVAILABILITY_UNKNOWN'})
    need(len(set(ids))==len(ids),'HOLD_SUPPORT_EDGE_COLLISION')
    for route in d.get('access_routes',[]):
        required(route,('route_id','required_support_edge_ids','fallback_support_edge_ids','formal_legal_state','source_ref'),'HOLD_ACCESS_FIELDS')
        need(set(route['required_support_edge_ids']+route['fallback_support_edge_ids'])<=set(ids),'HOLD_ACCESS_ROUTE_UNBOUND')
        _proof(route['source_ref'],pin,base,'access_route_observation',{k:v for k,v in route.items() if k!='source_ref'})
        available={e['support_edge_id'] for e in supports if e['availability_state']=='AVAILABLE' and (query is None or instant(e['valid_from'])<=instant(query['valid_time'])<=instant(e['valid_to']) and instant(e['observed_at'])<=instant(query['observer_time']))}
        if not set(route['required_support_edge_ids'])<=available and not set(route['fallback_support_edge_ids'])&available:holds.append({'route_id':route['route_id'],'state':'HOLD_PRACTICAL_ACCESS_SINGLE_POINT_OF_FAILURE','formal_legal_state':copy.deepcopy(route['formal_legal_state'])})
    for surface,planes in (('child_cases',CHILD_PLANES),('kabukicho_cases',KAB_PLANES)):
        for case in d.get(surface,[]):
            required(case,('case_id','dependencies','source_ref'),'HOLD_DOMAIN_CASE_FIELDS');required(case['dependencies'],planes,'HOLD_DOMAIN_DEPENDENCY_DROPOUT')
            _proof(case['source_ref'],pin,base,'domain_case_observation',{k:v for k,v in case.items() if k!='source_ref'})
            need(case.get('risk_coefficients')==[],'HOLD_DEMOGRAPHIC_WRONGDOING_PROXY')
            for key,value in case['dependencies'].items():
                need(value is not None and type(value) is not bool,'HOLD_DOMAIN_DEPENDENCY_NULL')
                if value=='UNKNOWN' or isinstance(value,dict) and value.get('state') in {'UNKNOWN','HOLD','CONFLICTING'}:holds.append({'case_id':case['case_id'],'dependency':key,'state':'HOLD_DOMAIN_DEPENDENCY_UNKNOWN'})
            if surface=='kabukicho_cases':
                for key in ('CARE','MEDICAL_CARE'):
                    value=case['dependencies'][key];state=value.get('state') if isinstance(value,dict) else value
                    need(state not in {'ABSENT','SUSPENDED','NULL'},'HOLD_PROTECTIVE_HANDOFF_REQUIRED')
                need(case.get('care_suspended_for_unresolved_status') is False and case.get('immigration_relief_created') is False,'HOLD_CARE_OR_AUTHORITY_INTERLOCK')
                if case.get('immigration_action_affects_carrier') is True:
                    er=case.get('child_dependency_review_ref');need(isinstance(er,dict),'HOLD_CHILD_DEPENDENCY_REVIEW_REQUIRED');_proof(er,pin,base,'child_dependency_review',{'case_id':case['case_id'],'relief_created':False})
                if case.get('subnational_rule_material') is True:need(text(case['dependencies']['SUBNATIONAL_JURISDICTION']) and case['dependencies']['SUBNATIONAL_JURISDICTION']!='UNKNOWN','HOLD_SUBNATIONAL_JURISDICTION_REQUIRED')
    return holds

def _display_event(e,audience):
    event={'event_id':e['event']['event_id'],'person_id':e['identity']['person_id'],'event_type':e['event']['event_type'],'identity_binding_state':e['identity']['identity_binding_state'],'temporal':copy.deepcopy(e['temporal']),'authority':copy.deepcopy(e['authority']),'evidence_state':e['evidence']['epistemic_state'],'legal_state':copy.deepcopy(e['legal_state']),'record_surface':copy.deepcopy(e['record_surface']),'relations':copy.deepcopy(e.get('relations',[])),'recognitions':copy.deepcopy(e.get('recognitions',[]))}
    if 'proceeding' in e:event['proceeding']=copy.deepcopy(e['proceeding'])
    # Sensitive existence and exact locations are excluded on ordinary surfaces.
    if audience=='INTERNAL_AUDIT':event['source_ref']=copy.deepcopy(e['evidence']['source_ref'])
    return event

def project_presentation(ledger,pin,base,query,request):return guarded(_project_presentation,ledger,pin,base,query,request)
def _project_presentation(d,pin,base,query,request):
    required(request,('audience','automatic_binding_action','purpose_minimized','whole_social_graph_requested','sensitive_disclosure_requested','distribution_ready'),'HOLD_DISPLAY_REQUEST_FIELDS')
    need(request['audience'] in {'INTERNAL_AUDIT','PUBLIC','RESEARCH','DEMO','PROTECTED_WORKFLOW'} and request['automatic_binding_action']=='NONE' and request['purpose_minimized'] is True and request['whole_social_graph_requested'] is False,'HOLD_VISUALIZATION_ACTION_OR_SCOPE')
    need(type(request['sensitive_disclosure_requested']) is bool and type(request['distribution_ready']) is bool,'HOLD_DISPLAY_BOOLEAN')
    need(request['sensitive_disclosure_requested'] is False,'HOLD_SEPARATE_PROTECTED_DISCLOSURE_AUTHORITY_REQUIRED')
    source=_inspect(d,pin,base,query);need('events' in source,'HOLD_LEDGER_PROJECTION_UNAVAILABLE')
    holds=copy.deepcopy(source['holds'])+_extensions(d,pin,base,query)
    for e in source['events']:
        if any(not known_text(e['authority'][k]) for k in REQUIRED['authority']):holds.append({'event_id':e['event']['event_id'],'state':'HOLD_PRESENTATION_AUTHORITY_NAMEPLATE_UNKNOWN'})
        if e['identity']['identity_binding_state'] in {'UNKNOWN','UNREGISTERED','LOOKUP_FAILED','CONFLICTING'} or e['evidence']['epistemic_state'] in {'UNKNOWN','UNREGISTERED','LOOKUP_FAILED','CONFLICTING'} or e['authority']['authority_state']=='UNKNOWN':holds.append({'event_id':e['event']['event_id'],'state':'HOLD_PRESENTATION_SELECTED_STATE_UNKNOWN'})
    if request['audience'] in {'PUBLIC','RESEARCH','DEMO'}:holds.append({'state':'HOLD_PUBLICATION_AUTHORITY_NOT_BOUND','scope':'PRESENTATION_ONLY'})
    events=[_display_event(e,request['audience']) for e in source['events']];edge_displays=[]
    for edge in source['dependency_edges']:
        need(edge.get('edge_class') in {'FACTUAL_DEPENDENCY','LEGAL_OR_AUTHORITY'},'HOLD_EDGE_NAMEPLATE_CLASS_UNKNOWN')
        if edge['edge_class']=='LEGAL_OR_AUTHORITY':
            required(edge,LEGAL_NAMEPLATE,'HOLD_LEGAL_EDGE_NAMEPLATE')
            need(edge['epistemic_state'] in EPISTEMIC and all(text(edge[k]) for k in ('source_type','jurisdiction','authority_entity','authority_basis','law_or_rule_version','conflict_state')),'HOLD_LEGAL_EDGE_NAMEPLATE_TYPE')
            for key in ('valid_from','valid_to','decision_time','record_time'):
                if edge[key]=='UNKNOWN':holds.append({'edge_id':edge['id'],'state':'HOLD_LEGAL_EDGE_TIME_UNKNOWN'})
                else:instant(edge[key])
            if edge['epistemic_state'] in {'UNKNOWN','UNREGISTERED','LOOKUP_FAILED','CONFLICTING'} or edge['conflict_state'] in {'UNKNOWN','CONFLICTING'} or edge['authority_basis']=='UNKNOWN':holds.append({'edge_id':edge['id'],'state':'HOLD_LEGAL_EDGE_STATE_OR_AUTHORITY_UNKNOWN'})
            _proof(edge['source_ref'],pin,base,'legal_edge_nameplate',{k:edge[k] for k in LEGAL_NAMEPLATE if k!='source_ref'})
            if any(not known_text(edge[k]) for k in ('source_type','jurisdiction','authority_entity','authority_basis','law_or_rule_version','conflict_state')):holds.append({'edge_id':edge['id'],'state':'HOLD_LEGAL_EDGE_NAMEPLATE_UNKNOWN'})
        display=copy.deepcopy(edge)
        if request['audience']!='INTERNAL_AUDIT':display.pop('source_ref',None)
        edge_displays.append(display)
    for event in events:
        if 'proceeding' in event:
            p=event['proceeding'];layers=p['decision_layers']
            plate={k:p.get(k,layers.get(k,'UNKNOWN')) for k in PROCEDURAL_NAMEPLATE}
            # decision_date and decision_time are not aliases; absent binding remains HOLD.
            if plate['decision_date']=='UNKNOWN':holds.append({'event_id':event['event_id'],'state':'HOLD_PROCEDURAL_DECISION_DATE_BINDING_UNKNOWN'})
            else:instant(plate['decision_date'])
            event['procedural_nameplate']=plate
            if any(layers[k]=='UNKNOWN' for k in ('finality','appeal_status','enforceability','bound_party_scope','bound_subject_matter_scope')):holds.append({'event_id':event['event_id'],'state':'HOLD_PROCEDURAL_BOUND_SCOPE'})
            if request['distribution_ready'] and any(i['status'] in {'DISPUTED','UNKNOWN','RESOLVED_NONFINAL'} and i['materiality']=='MATERIAL' for i in p.get('issues',[])):holds.append({'event_id':event['event_id'],'state':'HOLD_BINDING_DISTRIBUTION'})
    need(request['distribution_ready'] is False or not holds,'HOLD_BINDING_DISTRIBUTION')
    all_ids={e['event']['event_id'] for e in d['events']};selected={e['event_id'] for e in events}
    view={'schema':'yr.ledger-presentation/1','source_ledger_digest':source['source_ledger_digest'],'query':copy.deepcopy(query),'events':events,'dependency_edges':edge_displays,'omitted_event_ids':sorted(all_ids-selected),'omission_meaning':'PURPOSE_TIME_JURISDICTION_FILTER_ONLY_NOT_NONEXISTENCE','unknowns':copy.deepcopy(source['unknowns']),'holds':holds,'support_history':[{'support_edge_id':e['support_edge_id'],'support_type':e['support_type'],'availability_state':e['availability_state'],'valid_from':e['valid_from'],'valid_to':e['valid_to'],'edge_effect_state':e.get('edge_effect_state','UNKNOWN')} for e in d.get('support_edges',[])],'access_routes':[{'route_id':r['route_id'],'formal_legal_state':copy.deepcopy(r['formal_legal_state'])} for r in d.get('access_routes',[])],'sensitive_fields':'REDACTED','publication_authority':'NOT_GRANTED','binding_effect':'NOT_GRANTED','automatic_binding_action':'NONE'}
    view['domain_cases']={surface:[{k:copy.deepcopy(v) for k,v in row.items() if k!='source_ref'} for row in d.get(surface,[])] for surface in ('child_cases','kabukicho_cases')}
    view=redact_sensitive(view,request['audience']);holds=redact_sensitive(holds,request['audience'])
    return result('HOLD_PRESENTATION_SCOPED' if holds else 'PASS_LEDGER_PRESENTATION_STRUCTURAL_ONLY',tool_revision=REVISION,view=view,view_sha256=digest(view),holds=holds,action_eligible=False)

def inspect_presentation(ledger,pin,base,query,request,proposed):return guarded(_inspect_presentation,ledger,pin,base,query,request,proposed)
def _inspect_presentation(d,pin,base,query,request,proposed):
    source=_project_presentation(d,pin,base,query,request)
    need(proposed==source['view'],'HOLD_PRESENTATION_SOURCE_STATE_AUTHORITY_OR_PRIVACY_CHANGE')
    return result(source['verdict'],tool_revision=REVISION,view_sha256=digest(proposed),holds=source['holds'],binding_effect='NOT_GRANTED',publication_authority='NOT_GRANTED')

def redact_sensitive(value,audience):
    if isinstance(value,list):return [redact_sensitive(v,audience) for v in value]
    if not isinstance(value,dict):return copy.deepcopy(value)
    out={}
    private={k.lower() for k in SENSITIVE_FIELDS}|{'current_location_status','physical_location','exact_location','current_child_location','home_address','helper_name','helper_contact','private_locator'}
    if audience in {'PUBLIC','RESEARCH','DEMO'}:private|={'person_id','provider_ref','recipient_ref','source_ref','source_refs','case_or_docket_ref','event_actor_refs','event_object_refs'}
    for k,v in value.items():
        if str(k).lower() in private:out[k]='UNKNOWN' if v=='UNKNOWN' else 'REDACTED'
        else:out[k]=redact_sensitive(v,audience)
    return out

def known_text(value):return known_identity(value) and value!='CONFLICTING'
