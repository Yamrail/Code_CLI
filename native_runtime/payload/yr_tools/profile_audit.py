"""Defined Profile/Privacy/Audit static workface. No ingest, API, deletion, or provider call."""

import copy,json

from .binder import need,text,known_identity,digest,validate,validate_set,instant,result,guarded,no_authority

from .numeric import number

from .binder import retained,sha

from . import execution_receipt

REVISION='PROFILE_PRIVACY_AUDIT_ADAPTER_R006_PRIVATE'

NODE_FIELDS=('profile_id','node_type','display_name','subject_ref','pseudonymous','purpose_ids','visibility','epistemic_state','usability_state','task_scope','evidence_refs','inference_refs','authority_ref','consent_or_basis_ref','retention_class','model_provider_route','egress_policy','correction_route','created_at','last_reviewed_at','revision_id','content_hash')

EDGE_FIELDS=('edge_id','from_profile_id','to_profile_id','relation','valid_from','valid_to','evidence_refs','authority_ref','revision_id')

CLAIM_FIELDS=('claim_id','profile_id','claim_type','statement','state','task_scope','evidence_refs','inference_method','reviewer','valid_time','revision_id')

AUTH_FIELDS=('authority_id','purpose_id','subject_scope','action_scope','source','basis_type','valid_from','valid_to','public_projection_allowed','external_model_allowed','cross_customer_learning_allowed','receipt')

RETENTION_FIELDS=('object_id','retention_class','purpose_id','start_at','review_at','delete_at','legal_hold_ref','deletion_state','deletion_receipt')

NODE_TYPES={'COUNTRY','DOMAIN','SPECIALTY','COMPANY','DEPARTMENT','TEAM','INDIVIDUAL'}

VISIBILITY={'PUBLIC','RESTRICTED','PRIVATE','HOLD'}

EPISTEMIC={'OBSERVED','INFERENCE','UNKNOWN','HOLD','CONTRADICTED','SUPERSEDED'}

USABILITY={'UNASSESSED','EXPERIMENTAL_ONLY','BOUNDED_USABLE','REPEATABLE_OPERATIONAL','VALIDATED_FOR_DEFINED_SCOPE','AUTHORIZED_FOR_DEFINED_SCOPE','HOLD'}

RELATIONS={'LOCATED_IN','OPERATES_IN','EMPLOYS','MEMBER_OF','REPORTS_TO','USES_STANDARD','DEPENDS_ON','PROVIDES_SERVICE_TO','SHARES_WORKFLOW_WITH','BELONGS_TO_SPECIALTY','AUTHORIZED_BY'}

RETENTION={'R0_EPHEMERAL','R1_OPERATIONAL_SHORT','R2_PROJECT_LIFECYCLE','R3_AUDIT_EVIDENCE','R4_PUBLIC_HISTORICAL','R5_LEGAL_HOLD'}

FORBIDDEN={'person_score','employee_ranking','personality_score','political_profiling','covert_employability','intelligence','personality','health','political_beliefs','religion','sexuality','ethnicity','private_family','employability','person_worth','country_score','company_ai_score','leaderboard','comparison_rank','secret','credential','raw_customer_trace'}

PUBLIC_FIELDS={'profile_id','revision_id','content_hash','generated_at','visibility','epistemic_state','usability_state','task_scope','claims','evidence_summary','unresolved','correction_route'}

def fields(d,keys,reason):need(isinstance(d,dict) and all(k in d for k in keys),reason)

def keys_recursive(value):

    if isinstance(value,dict):

        return {str(k).lower() for k in value}|set().union(*(keys_recursive(v) for v in value.values()),set())

    if isinstance(value,list):return set().union(*(keys_recursive(v) for v in value),set())

    return set()

def inspect(d,pin,base):return guarded(_inspect,d,pin,base)

def _inspect(d,pin,base):

    need(d.get('schema')=='yr.profile-audit/1','HOLD_PROFILE_SCHEMA');no_authority(d)

    payload={k:v for k,v in d.items() if k!='source_ref'};ref=d['source_ref']

    validate(ref,pin['source_pin'],base,pin['source_subject'],{'profile_input':payload})

    need(not keys_recursive({k:v for k,v in payload.items() if k!='inference_policy'})&FORBIDDEN,'HOLD_SENSITIVE_TRAIT_OR_RANKING_FIELD')

    policy=d['inference_policy'];fields(policy,('policy_id','allowed_claim_types','prohibited_claim_types','max_scope','sensitive_trait_inference','employee_ranking','automated_high_impact_decision'),'HOLD_INFERENCE_POLICY_FIELDS')

    need(all(policy[k]=='PROHIBITED' for k in ('sensitive_trait_inference','employee_ranking','automated_high_impact_decision')),'HOLD_INFERENCE_POLICY')

    need(isinstance(policy['allowed_claim_types'],list) and isinstance(policy['prohibited_claim_types'],list),'HOLD_INFERENCE_POLICY_TYPE')

    forbidden_claims=FORBIDDEN|{str(k).lower() for k in policy['prohibited_claim_types']}

    need(not {str(k).lower() for k in policy['allowed_claim_types']}&forbidden_claims,'HOLD_SENSITIVE_INFERENCE_POLICY')

    query=d['request'];fields(query,('profile_id','purpose_id','action','audience','subject_scope','observed_at','customer_id'),'HOLD_PROFILE_REQUEST_FIELDS')

    need(query['action'] in {'READ','WRITE_PLAN','PUBLIC_PROJECTION_PLAN','EGRESS_PLAN'} and query['audience'] in {'PUBLIC','AUTHENTICATED','INTERNAL_AUDIT'},'HOLD_PROFILE_REQUEST_TYPE');now=instant(query['observed_at'])

    nodes=d['nodes'];edges=d['edges'];claims=d['claims'];need(isinstance(nodes,list) and isinstance(edges,list) and isinstance(claims,list),'HOLD_PROFILE_GRAPH_TYPE')

    ids=[n['profile_id'] for n in nodes];need(all(text(i) for i in ids) and len(set(ids))==len(ids) and query['profile_id'] in ids,'HOLD_PROFILE_IDENTITY')

    by={n['profile_id']:n for n in nodes};unresolved={'unknown':[],'hold':[]};auths={}

    def authority(er):
        need(er['record_class']=='AUTHORITY','HOLD_PROFILE_AUTHORITY_RECORD_CLASS')

        validate(er,pin['evidence_pins'][er['artifact_id']],base,pin['evidence_subjects'][er['artifact_id']])
        if er['artifact_id'] in auths:return auths[er['artifact_id']]

        r=validate(er,pin['evidence_pins'][er['artifact_id']],base,pin['evidence_subjects'][er['artifact_id']])['record']['profile_authority'];fields(r,AUTH_FIELDS,'HOLD_PROFILE_AUTHORITY_FIELDS')

        need(all(known_text(r[k]) for k in ('authority_id','purpose_id','source','basis_type')) and isinstance(r['subject_scope'],list) and r['subject_scope'] and all(known_text(x) for x in r['subject_scope']) and isinstance(r['action_scope'],list) and r['action_scope'] and all(known_text(x) for x in r['action_scope']),'HOLD_PROFILE_AUTHORITY_IDENTITY_UNKNOWN')
        need(r['basis_type'] in {'PUBLIC_SOURCE','SELF_OPT_IN','ORG_AUTHORITY','CONTRACT','LEGAL_REQUIREMENT','OTHER_HOLD'},'HOLD_PROFILE_AUTHORITY_TYPE')

        need(r['basis_type']!='OTHER_HOLD' and query['purpose_id']==r['purpose_id'] and query['subject_scope'] in r['subject_scope'] and query['action'] in r['action_scope'],'HOLD_PROFILE_AUTHORITY_SCOPE')

        need(instant(r['valid_from'])<=now<=instant(r['valid_to']),'HOLD_PROFILE_AUTHORITY_EXPIRED')

        for k in ('public_projection_allowed','external_model_allowed','cross_customer_learning_allowed'):need(type(r[k]) is bool,'HOLD_PROFILE_AUTHORITY_BOOLEAN')

        need(isinstance(r['receipt'],dict),'HOLD_PROFILE_AUTHORITY_RECEIPT');receipt=r['receipt'];validate(receipt,pin['evidence_pins'][receipt['artifact_id']],base,pin['evidence_subjects'][receipt['artifact_id']],{'profile_authority_receipt':{k:v for k,v in r.items() if k!='receipt'}})

        auths[er['artifact_id']]=r;return r

    for n in nodes:

        fields(n,NODE_FIELDS,'HOLD_PROFILE_NODE_FIELDS');need(text(n['subject_ref']) and text(n['display_name']),'HOLD_PROFILE_SUBJECT_IDENTITY');need(n['node_type'] in NODE_TYPES and n['visibility'] in VISIBILITY and n['epistemic_state'] in EPISTEMIC and n['usability_state'] in USABILITY and type(n['pseudonymous']) is bool,'HOLD_PROFILE_NODE_ENUM')

        need(text(n['revision_id']) and text(n['content_hash']) and n['revision_id']!=n['content_hash'] and n['content_hash']==digest({k:v for k,v in n.items() if k!='content_hash'}),'HOLD_PROFILE_REVISION_HASH')

        need(isinstance(n['purpose_ids'],list) and n['purpose_ids'] and query['purpose_id'] in n['purpose_ids'] and isinstance(n['task_scope'],list) and n['task_scope'] and text(n['correction_route']),'HOLD_PROFILE_PURPOSE_OR_CORRECTION')

        need(instant(n['created_at'])<=instant(n['last_reviewed_at'])<=now and n['retention_class'] in RETENTION,'HOLD_PROFILE_TIME_OR_RETENTION')

        for er in n['evidence_refs']+n['inference_refs']:_evidence(er,pin,base,now)

        need(set(n['task_scope'])<=set(policy['max_scope']),'HOLD_PROFILE_INFERENCE_MAX_SCOPE')

        fields(n,('parent_revision','changed_by','change_reason'),'HOLD_PROFILE_REVISION_LINEAGE_FIELDS');need(text(n['changed_by']) and text(n['change_reason']),'HOLD_PROFILE_REVISION_CHANGE_REASON')

        a=authority(n['authority_ref'])

        if n['epistemic_state']=='UNKNOWN':unresolved['unknown'].append(n['profile_id'])

        if n['epistemic_state'] in {'HOLD','CONTRADICTED','SUPERSEDED'} or n['visibility']=='HOLD':unresolved['hold'].append(n['profile_id'])

        if n['node_type']=='INDIVIDUAL' or n['visibility']!='PUBLIC':

            need(isinstance(n['consent_or_basis_ref'],dict) and n['egress_policy'].get('state')=='DEFINED' and n['model_provider_route'].get('state') in {'OFF','APPROVED_BOUND'},'HOLD_NO_PROFILE_INGEST')

            er=n['consent_or_basis_ref'];validate(er,pin['evidence_pins'][er['artifact_id']],base,pin['evidence_subjects'][er['artifact_id']])

        if query['audience']=='PUBLIC' and n['profile_id']==query['profile_id']:need(n['visibility']=='PUBLIC' and n['node_type'] in {'COUNTRY','DOMAIN','SPECIALTY'} and a['public_projection_allowed'] is True,'HOLD_PUBLIC_PRIVATE_BOUNDARY')

        if query['action']=='EGRESS_PLAN':need(a['external_model_allowed'] is True and n['model_provider_route'].get('state')=='APPROVED_BOUND' and n['egress_policy'].get('state')=='DEFINED','HOLD_PROVIDER_DATA_BOUNDARY')

    edge_ids=[]

    for e in edges:

        fields(e,EDGE_FIELDS,'HOLD_PROFILE_EDGE_FIELDS');need(e['from_profile_id'] in by and e['to_profile_id'] in by and e['relation'] in RELATIONS and text(e['revision_id']),'HOLD_PROFILE_EDGE_BINDING');edge_ids.append(e['edge_id']);need(instant(e['valid_from'])<=instant(e['valid_to']),'HOLD_PROFILE_EDGE_TIME');validate_set(e['evidence_refs'],pin['evidence_pins'],base,pin['evidence_subjects']);authority(e['authority_ref'])

    need(len(set(edge_ids))==len(edge_ids),'HOLD_PROFILE_EDGE_COLLISION')

    cids=[]

    for c in claims:

        fields(c,CLAIM_FIELDS,'HOLD_PROFILE_CLAIM_FIELDS');need(text(c['claim_id']) and text(c['profile_id']) and text(c['statement']),'HOLD_PROFILE_CLAIM_IDENTITY');instant(c['valid_time']);need(c['profile_id'] in by and c['state'] in EPISTEMIC-{'SUPERSEDED'} and c['claim_type'] in policy['allowed_claim_types'] and c['claim_type'].lower() not in forbidden_claims,'HOLD_PROFILE_CLAIM_POLICY');cids.append(c['claim_id'])

        need(set(c['task_scope'])<=set(by[c['profile_id']]['task_scope']) and text(c['revision_id']),'HOLD_PROFILE_CLAIM_SCOPE');bound=[_evidence(er,pin,base,now) for er in c['evidence_refs']]

        if c['state']=='OBSERVED':need(bound and all(b['record']['source_class'] not in {'MODEL_INFERENCE','COMMUNITY_REPORT','CORRECTION_SUBMISSION'} for b in bound),'HOLD_UNREVIEWED_REPORT_PROMOTION')

        if c['state'] in {'UNKNOWN','HOLD','CONTRADICTED'}:unresolved['unknown' if c['state']=='UNKNOWN' else 'hold'].append(c['claim_id'])

    need(len(set(cids))==len(cids),'HOLD_PROFILE_CLAIM_COLLISION')

    previous=pin.get('previous_nodes');need(isinstance(previous,list),'HOLD_PROFILE_LINEAGE_UNBOUND')

    for prior in previous:

        need(prior in d['history_nodes'],'HOLD_PROFILE_HISTORY_REWRITE')

        current=by.get(prior['profile_id'])

        if current is not None and current['content_hash']!=prior['content_hash']:need(current['revision_id']!=prior['revision_id'] and current['parent_revision']==prior['revision_id'],'HOLD_PROFILE_SAME_REVISION_REPLACEMENT_OR_PARENT_LOSS')

    prior_ids={n['profile_id'] for n in previous}

    for n in nodes:

        if n['profile_id'] not in prior_ids:need(n['parent_revision'] is None,'HOLD_PROFILE_CREATION_PARENT_UNKNOWN')

    _collection_and_routes(d,pin,base,by,query)

    correction_result=_corrections(d['corrections'],pin,base)

    for row in d['corrections']:

        need(row['profile_id'] in by,'HOLD_CORRECTION_PROFILE_UNBOUND')

        if row['material'] and row['outcome']=='PENDING':unresolved['hold'].append(row['profile_id'])

    for r in d['retention_records']:

        fields(r,RETENTION_FIELDS,'HOLD_RETENTION_FIELDS');need(r['object_id'] in by and r['purpose_id']==query['purpose_id'] and r['retention_class']==by[r['object_id']]['retention_class'] and r['deletion_state'] in {'ACTIVE','PENDING','PARTIAL','DELETED','HOLD'},'HOLD_RETENTION_STATE')

        need(instant(r['start_at'])<=instant(r['review_at'])<=instant(r['delete_at']),'HOLD_RETENTION_TIME')

        if r['deletion_state']=='DELETED':

            er=r['deletion_receipt'];record=validate(er,pin['evidence_pins'][er['artifact_id']],base,pin['evidence_subjects'][er['artifact_id']])['record']

            need(er['record_class'] in {'EXECUTION','RECEIPT'} and record['deletion_receipt']['profile_id']==r['object_id'] and record['deletion_receipt']['actual_deletion_verified'] is True and record['deletion_receipt']['minimal_audit_lineage_retained'] is True,'HOLD_DELETION_UNVERIFIED')

    need({r['object_id'] for r in d['retention_records']}==set(ids),'HOLD_RETENTION_OBJECT_DROPOUT')

    learning=d['generalized_learning'];need(learning['customer_id']==query['customer_id'] and learning['raw_content_exported'] is False,'HOLD_CROSS_CUSTOMER_RAW_DATA')

    if learning['enabled'] is True:need(learning['sanitized'] is True and learning['contains_customer_identity'] is False and learning['approval_bound'] is True and all(a['cross_customer_learning_allowed'] for a in auths.values()),'HOLD_CROSS_CUSTOMER_ISOLATION')

    projection=d['response'];need(set(projection)==PUBLIC_FIELDS and projection['profile_id']==query['profile_id'],'HOLD_PROFILE_RESPONSE_SCHEMA')

    n=by[query['profile_id']]

    for k in ('revision_id','content_hash','visibility','epistemic_state','usability_state','task_scope','correction_route'):need(projection[k]==n[k],'HOLD_PROFILE_RESPONSE_LOSS_'+k)

    if query['audience']=='PUBLIC':

        need(not any(e['from_profile_id']==query['profile_id'] and by[e['to_profile_id']]['visibility']!='PUBLIC' or e['to_profile_id']==query['profile_id'] and by[e['from_profile_id']]['visibility']!='PUBLIC' for e in edges),'HOLD_PUBLIC_PRIVATE_EDGE_LEAK')

    need(projection['unresolved']==unresolved,'HOLD_PROFILE_UNKNOWN_OR_HOLD_LOSS');instant(projection['generated_at'])

    need(projection['claims']==[{k:c[k] for k in ('claim_id','claim_type','statement','state','task_scope','revision_id')} for c in claims if c['profile_id']==n['profile_id']],'HOLD_PROFILE_CLAIM_PROJECTION_LOSS')

    summary=[]

    for er in n['evidence_refs']:

        actual=validate(er,pin['evidence_pins'][er['artifact_id']],base,pin['evidence_subjects'][er['artifact_id']])['record'];summary.append({'evidence_id':er['artifact_id'],'content_hash':er['sha256'],'source_class':actual['source_class']})

        if query['audience']=='PUBLIC':need(actual['source_class'] in {'PUBLIC_PRIMARY','PUBLIC_SECONDARY'} and actual['access_class']=='PUBLIC','HOLD_PRIVATE_EVIDENCE_LOCATOR_LEAK')

    need(projection['evidence_summary']==summary,'HOLD_PROFILE_EVIDENCE_SUMMARY_LEAK')

    return result('PASS_PROFILE_AUDIT_STRUCTURAL_ONLY',tool_revision=REVISION,response=copy.deepcopy(projection),unresolved=unresolved,authority_snapshot_sha256=digest(auths),legal_mapping='HOLD_JURISDICTION_REVIEW',retention_period_legally_approved=False,provider_call='NOT_EXECUTED',deletion='NOT_EXECUTED',publication='NOT_AUTHORIZED_BY_TOOL')





EVIDENCE_FIELDS=('evidence_id','source_class','locator','acquired_at','observed_at','content_hash','access_class','contains_personal_data','contains_sensitive_data','minimization_applied','retention_class')

EVIDENCE_CLASSES={'PUBLIC_PRIMARY','PUBLIC_SECONDARY','ORGANIZATION_PROVIDED','SELF_PROVIDED','OBSERVED_WORK_RECORD','MODEL_INFERENCE','COMMUNITY_REPORT','CORRECTION_SUBMISSION'}

RECEIPT_KINDS={'PROFILE_CREATE_RECEIPT','PROFILE_MUTATION_RECEIPT','PUBLIC_PROJECTION_RECEIPT','CORRECTION_RECEIPT','DELETION_RECEIPT','AUTHORITY_CHANGE_RECEIPT','AUDIT_RECEIPT'}

CORRECTIONS={'FACTUAL_CORRECTION','ATTRIBUTION_ERROR','OUTDATED_DATA','MISSING_CONTEXT','INAPPROPRIATE_INFERENCE','VISIBILITY_OBJECTION','RETENTION_OBJECTION','DELETION_REQUEST'}

EXPOSURES=('AGGREGATE','ROLE_FUNCTION','PSEUDONYMOUS_NODE','IDENTIFIED_INDIVIDUAL','RAW_CONTENT')



def _evidence(ref,pin,base,now):

    bound=validate(ref,pin['evidence_pins'][ref['artifact_id']],base,pin['evidence_subjects'][ref['artifact_id']]);record=bound['record'];meta=record['profile_evidence'];fields(meta,EVIDENCE_FIELDS,'HOLD_PROFILE_EVIDENCE_METADATA')

    need(meta['evidence_id']==ref['artifact_id'] and meta['source_class'] in EVIDENCE_CLASSES and meta['retention_class'] in RETENTION and meta['access_class'] in {'PUBLIC','RESTRICTED','PRIVATE','HOLD'},'HOLD_PROFILE_EVIDENCE_ENUM')

    need(instant(meta['observed_at'])<=instant(meta['acquired_at'])<=now and type(meta['contains_personal_data']) is bool and type(meta['contains_sensitive_data']) is bool and type(meta['minimization_applied']) is bool,'HOLD_PROFILE_EVIDENCE_TIME_OR_TYPE')

    _,raw=retained(base,meta['locator']);need(sha(raw)==meta['content_hash'] and record.get('source_class')==meta['source_class'] and record.get('access_class')==meta['access_class'],'HOLD_PROFILE_EVIDENCE_SOURCE_HASH')

    return bound



def _collection_and_routes(d,pin,base,by,query):

    rows=d['collection_reviews'];need(isinstance(rows,list) and len(rows)==len(by),'HOLD_COLLECTION_REVIEW_DROPOUT');seen=[]

    for row in rows:

        fields(row,('profile_id','purpose_id','scope','subject_class','source_authority_ref','visibility','retention_class','inference_policy_id','correction_route','selected_exposure','least_exposure_sufficient','raw_data_necessity','receipt_ref'),'HOLD_COLLECTION_REVIEW_FIELDS')

        n=by[row['profile_id']];seen.append(n['profile_id'])

        need(row['purpose_id']==query['purpose_id'] and row['scope']==n['task_scope'] and row['subject_class']==n['node_type'] and row['source_authority_ref']==n['authority_ref'] and row['visibility']==n['visibility'] and row['retention_class']==n['retention_class'] and row['inference_policy_id']==d['inference_policy']['policy_id'] and row['correction_route']==n['correction_route'],'HOLD_COLLECTION_PURPOSE_SCOPE')

        need(row['selected_exposure'] in EXPOSURES and row['least_exposure_sufficient'] in EXPOSURES and row['selected_exposure']==row['least_exposure_sufficient'],'HOLD_LEAST_EXPOSURE_VIOLATION')

        need(text(row['raw_data_necessity']) or row['selected_exposure']!='RAW_CONTENT','HOLD_RAW_DATA_NECESSITY_UNJUSTIFIED')

        er=row['receipt_ref'];validate(er,pin['evidence_pins'][er['artifact_id']],base,pin['evidence_subjects'][er['artifact_id']],{'collection_review':{k:v for k,v in row.items() if k!='receipt_ref'}})

        route=n['model_provider_route'];egress=n['egress_policy']

        need(isinstance(route,dict) and route.get('state') in {'OFF','APPROVED_BOUND'} and isinstance(egress,dict) and egress.get('state')=='DEFINED','HOLD_PROVIDER_ROUTE_UNDEFINED')

        if route['state']=='APPROVED_BOUND':

            fields(route,('provider_id','deployment_route','data_boundary','receipt_ref'),'HOLD_PROVIDER_ROUTE_FIELDS');er=route['receipt_ref']

            validate(er,pin['evidence_pins'][er['artifact_id']],base,pin['evidence_subjects'][er['artifact_id']],{'provider_route':{k:v for k,v in route.items() if k!='receipt_ref'}})

            er=egress['receipt_ref'];validate(er,pin['evidence_pins'][er['artifact_id']],base,pin['evidence_subjects'][er['artifact_id']],{'egress_policy':{k:v for k,v in egress.items() if k!='receipt_ref'}})

            need(egress.get('profile_id')==n['profile_id'] and egress.get('purpose_id')==query['purpose_id'] and egress.get('provider_id')==route['provider_id'],'HOLD_PROVIDER_DATA_BOUNDARY')

    need(len(set(seen))==len(by),'HOLD_COLLECTION_REVIEW_COLLISION')



def inspect_corrections(corrections,pin,base):return guarded(_corrections,corrections,pin,base)

def _corrections(rows,pin,base):

    need(isinstance(rows,list),'HOLD_CORRECTION_TYPE');ids=[]

    for row in rows:

        fields(row,('request_id','profile_id','request_type','submission_ref','triage_ref','evidence_review_ref','material','local_hold','outcome','before_revision','after_revision','reason','receipt_ref'),'HOLD_CORRECTION_FIELDS');ids.append(row['request_id'])

        need(text(row['request_id']) and text(row['profile_id']) and row['request_type'] in CORRECTIONS and type(row['material']) is bool and type(row['local_hold']) is bool and (not row['material'] or row['local_hold'] is True),'HOLD_CORRECTION_MATERIAL_HOLD')

        need(row['outcome'] in {'PENDING','NEW_REVISION','REJECTED_WITH_REASON'} and text(row['reason']) and text(row['before_revision']),'HOLD_CORRECTION_OUTCOME')

        if row['outcome']=='NEW_REVISION':need(text(row['after_revision']) and row['after_revision']!=row['before_revision'],'HOLD_CORRECTION_SAME_REVISION_REPLACEMENT')

        if row['outcome']=='REJECTED_WITH_REASON':need(row['after_revision']==row['before_revision'],'HOLD_REJECTED_CORRECTION_CHANGED_REVISION')

        for key,proof_key in (('submission_ref','correction_submission'),('triage_ref','correction_triage'),('evidence_review_ref','correction_evidence_review'),('receipt_ref','correction_receipt')):

            er=row[key];expected={'request_id':row['request_id'],'profile_id':row['profile_id']}

            if key=='evidence_review_ref':expected.update(reviewed=True,auto_promoted=False)

            if key=='receipt_ref':expected.update(before_revision=row['before_revision'],after_revision=row['after_revision'],outcome=row['outcome'],reason=row['reason'])

            validate(er,pin['evidence_pins'][er['artifact_id']],base,pin['evidence_subjects'][er['artifact_id']],{proof_key:expected})

    need(len(set(ids))==len(ids),'HOLD_CORRECTION_REQUEST_COLLISION')

    return result('PASS_CORRECTION_RECEIPT_CONTRACT_ONLY',tool_revision=REVISION,retained_request_ids=ids,mutation='NOT_PERFORMED')



def inspect_profile_receipt(receipt,pin,base):return guarded(_profile_receipt,receipt,pin,base)

def _profile_receipt(r,pin,base):

    fields(r,('kind','profile_id','scope','before_revision','after_revision','action','authority','tests','time','hash','evidence_ref'),'HOLD_PROFILE_RECEIPT_FIELDS')

    need(r['kind'] in RECEIPT_KINDS and text(r['profile_id']) and isinstance(r['scope'],list) and r['scope'] and text(r['action']) and text(r['after_revision']),'HOLD_PROFILE_RECEIPT_IDENTITY')
    need(all(known_text(v) for v in r['scope']) and known_text(r['profile_id']) and known_text(r['after_revision']),'HOLD_PROFILE_RECEIPT_SCOPE_UNKNOWN')
    actions={'PROFILE_CREATE_RECEIPT':'CREATE','PROFILE_MUTATION_RECEIPT':'UPDATE','PUBLIC_PROJECTION_RECEIPT':'PUBLIC_PROJECTION','CORRECTION_RECEIPT':'CORRECTION','DELETION_RECEIPT':'DELETE','AUTHORITY_CHANGE_RECEIPT':'AUTHORITY_CHANGE','AUDIT_RECEIPT':'AUDIT'}
    need(r['action']==actions[r['kind']],'HOLD_PROFILE_RECEIPT_ACTION_KIND')
    if r['kind']=='PROFILE_CREATE_RECEIPT':need(r['before_revision'] is None,'HOLD_PROFILE_CREATE_REVISION_LINEAGE')
    else:need(known_text(r['before_revision']),'HOLD_PROFILE_RECEIPT_BEFORE_REVISION_UNKNOWN')
    if r['kind'] in {'PROFILE_MUTATION_RECEIPT','CORRECTION_RECEIPT','DELETION_RECEIPT','AUTHORITY_CHANGE_RECEIPT'}:need(r['before_revision']!=r['after_revision'],'HOLD_PROFILE_RECEIPT_SAME_REVISION_REPLACEMENT')

    need(r['hash']==digest({k:v for k,v in r.items() if k not in {'hash','evidence_ref'}}),'HOLD_PROFILE_RECEIPT_HASH');instant(r['time'])

    er=r['evidence_ref'];validate(er,pin['evidence_pins'][er['artifact_id']],base,pin['evidence_subjects'][er['artifact_id']],{'profile_action_receipt':{k:v for k,v in r.items() if k!='evidence_ref'}})

    authority=r['authority'];need(authority['record_class']=='AUTHORITY','HOLD_PROFILE_ACTION_AUTHORITY_CLASS')
    bound=validate(authority,pin['evidence_pins'][authority['artifact_id']],base,pin['evidence_subjects'][authority['artifact_id']])['record']['profile_authority'];fields(bound,AUTH_FIELDS,'HOLD_PROFILE_ACTION_AUTHORITY_FIELDS')
    need(all(known_text(bound[k]) for k in ('authority_id','purpose_id','source','basis_type')) and isinstance(bound['subject_scope'],list) and all(known_text(x) for x in bound['subject_scope']) and isinstance(bound['action_scope'],list) and all(known_text(x) for x in bound['action_scope']),'HOLD_PROFILE_ACTION_AUTHORITY_IDENTITY_UNKNOWN')
    for k in ('public_projection_allowed','external_model_allowed','cross_customer_learning_allowed'):need(type(bound[k]) is bool,'HOLD_PROFILE_ACTION_AUTHORITY_BOOLEAN')
    if r['kind']=='PUBLIC_PROJECTION_RECEIPT':need(bound['public_projection_allowed'] is True,'HOLD_PROFILE_PUBLIC_PROJECTION_PERMISSION')
    need(bound['basis_type'] in {'PUBLIC_SOURCE','SELF_OPT_IN','ORG_AUTHORITY','CONTRACT','LEGAL_REQUIREMENT'} and isinstance(bound['subject_scope'],list) and r['profile_id'] in bound['subject_scope'] and isinstance(bound['action_scope'],list) and r['action'] in bound['action_scope'],'HOLD_PROFILE_ACTION_AUTHORITY_SCOPE')
    need(instant(bound['valid_from'])<=instant(r['time'])<=instant(bound['valid_to']),'HOLD_PROFILE_ACTION_AUTHORITY_EXPIRED')
    ar=bound['receipt'];validate(ar,pin['evidence_pins'][ar['artifact_id']],base,pin['evidence_subjects'][ar['artifact_id']],{'profile_authority_receipt':{k:v for k,v in bound.items() if k!='receipt'}})

    need(isinstance(r['tests'],list) and r['tests'],'HOLD_PROFILE_RECEIPT_TESTS_MISSING')

    for test in r['tests']:

        _,raw=retained(base,test['locator']);receipt=json.loads(raw);need(sha(raw)==test['sha256'],'HOLD_PROFILE_TEST_RECEIPT_HASH');execution_receipt.validate(receipt,pin['execution_pins'][test['artifact_id']],base)

    return result('PASS_PROFILE_ACTION_RECEIPT_CONTRACT_ONLY',tool_revision=REVISION,kind=r['kind'],action='NOT_EXECUTED_BY_VALIDATOR')



def inspect_audit_package(audit,pin,base):return guarded(_audit_package,audit,pin,base)

def _audit_package(a,pin,base):

    fields(a,('audit_id','profile_schema_revision','source_commit','tested_projection_revision','authority_snapshot','provider_route_snapshot','validator_versions','fixtures','test_results','findings','unresolved_hold','auditor_identity','audit_time','receipt_hash'),'HOLD_PROFILE_AUDIT_PACKAGE_FIELDS')

    for key in ('profile_schema_revision','source_commit','tested_projection_revision','authority_snapshot','provider_route_snapshot'):need(a[key]==pin['current_dependencies'][key],'HOLD_STALE_PROFILE_AUDIT_DEPENDENCY_'+key)
    need(known_text(a['audit_id']) and all(known_text(a[k]) and known_text(pin['current_dependencies'][k]) for k in ('profile_schema_revision','source_commit','tested_projection_revision','authority_snapshot','provider_route_snapshot')),'HOLD_PROFILE_AUDIT_DEPENDENCY_UNKNOWN')
    need(isinstance(a['unresolved_hold'],list) and isinstance(pin['current_unresolved_hold'],list),'HOLD_PROFILE_AUDIT_HOLD_REGISTER_UNKNOWN')
    need(isinstance(a['validator_versions'],list) and bool(a['validator_versions']) and isinstance(a['fixtures'],list) and bool(a['fixtures']),'HOLD_PROFILE_AUDIT_ROSTER_EMPTY')

    need(text(a['auditor_identity']) and a['auditor_identity']==pin['independent_auditor_identity'] and a['auditor_identity']!=pin['implementer_identity'],'HOLD_PROFILE_AUDITOR_ROLE_NOT_INDEPENDENT')

    need(a['receipt_hash']==digest({k:v for k,v in a.items() if k!='receipt_hash'}),'HOLD_PROFILE_AUDIT_RECEIPT_HASH')

    instant(a['audit_time']);need(a['validator_versions']==pin['validator_versions'] and a['fixtures']==pin['fixtures'] and a['test_results'],'HOLD_PROFILE_AUDIT_EQUIPMENT_UNBOUND')

    for proof in a['test_results']:

        _,raw=retained(base,proof['locator']);er=json.loads(raw);need(sha(raw)==proof['sha256'],'HOLD_PROFILE_AUDIT_TEST_HASH');execution_receipt.validate(er,pin['execution_pins'][proof['artifact_id']],base)

        need(instant(er['finished_at'])<=instant(a['audit_time']),'HOLD_PROFILE_AUDIT_TIME_REVERSAL')
        ep=pin['execution_pins'][proof['artifact_id']]
        need(er['source_revision']==a['source_commit'] and er['fixture_revision']==a['tested_projection_revision'],'HOLD_PROFILE_AUDIT_EXECUTION_SUBJECT')
        need(any(v.get('validator')=='profile_audit' and v.get('revision')==er['tool_revision']==REVISION and v.get('source_sha256')==er['source_sha256'] for v in a['validator_versions']),'HOLD_PROFILE_AUDIT_EXECUTED_VALIDATOR_VERSION')
        need(any(v.get('revision')==er['fixture_revision'] and v.get('sha256')==er['fixture_sha256'] and known_text(v.get('fixture_id')) for v in a['fixtures']),'HOLD_PROFILE_AUDIT_EXECUTED_FIXTURE_IDENTITY')
        _,fixture_raw=retained(base,ep['fixture_locator']);fixture=json.loads(fixture_raw)
        need(isinstance(fixture,dict) and 'input' in fixture and 'pin' in fixture,'HOLD_PROFILE_AUDIT_RETAINED_INPUT_MISSING')
        replay=_inspect(fixture['input'],fixture['pin'],base)
        need(replay['verdict']=='PASS_PROFILE_AUDIT_STRUCTURAL_ONLY' and replay['response']['revision_id']==a['tested_projection_revision'] and replay['authority_snapshot_sha256']==a['authority_snapshot'] and digest([n['model_provider_route'] for n in fixture['input']['nodes']])==a['provider_route_snapshot'],'HOLD_PROFILE_AUDIT_RETAINED_DEPENDENCY_BINDING')
        need(er['results'] and all(row.get('projection_revision')==a['tested_projection_revision'] and row.get('tool_revision')==er['tool_revision'] and row.get('input_sha256')==digest(fixture['input']) for row in er['results']),'HOLD_PROFILE_AUDIT_ACTUAL_RESULT_SUBJECT')

    finding_ids=[];blocking=[]

    for f in a['findings']:

        fields(f,('finding_id','class','state','affected_workfaces','control_ref','test_ref','receipt_ref'),'HOLD_AUDIT_FINDING_FIELDS');need(f['class'] in {'CRITICAL','MATERIAL','OBSERVATION','INFO'} and f['state'] in {'OPEN','CLOSED'} and isinstance(f['affected_workfaces'],list),'HOLD_AUDIT_FINDING_ENUM');finding_ids.append(f['finding_id'])

        for key in ('control_ref','test_ref','receipt_ref'):

            er=f[key];validate(er,pin['evidence_pins'][er['artifact_id']],base,pin['evidence_subjects'][er['artifact_id']])

        if f['state']=='OPEN' and f['class'] in {'CRITICAL','MATERIAL'}:blocking.append(f)

    need(len(set(finding_ids))==len(finding_ids),'HOLD_AUDIT_FINDING_COLLISION')

    need(a['unresolved_hold']==pin['current_unresolved_hold'],'HOLD_PROFILE_AUDIT_HOLD_LOSS')

    return result('HOLD_PROFILE_AUDIT_SCOPED' if blocking or a['unresolved_hold'] else 'PASS_PROFILE_AUDIT_PACKAGE_BINDING_ONLY',tool_revision=REVISION,blocking_findings=copy.deepcopy(blocking),unresolved_hold=copy.deepcopy(a['unresolved_hold']),independent_role_binding=True,public_or_personal_processing_authorized=False)


def known_text(value):return known_identity(value)
