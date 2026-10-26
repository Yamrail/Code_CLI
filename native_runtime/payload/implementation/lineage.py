"""Claim joints and human source projection; no invented historical reasons."""
import json,urllib.parse
from .reused.binder import need, digest
from .workstate import validate_evidence

JOINTS=('input_revision','acquisition','admission','delivery','rule','tool','inspection','issue_condition')
def inspect_claim(base,claim,receipts):
    need(claim.get('id') and claim.get('subject_revision') and claim.get('claim_text'),'HOLD_CLAIM_IDENTITY')
    need(set(JOINTS)<=set(claim.get('joints',{})),'HOLD_CLAIM_JOINT_MISSING')
    for j in JOINTS:
        ref=claim['joints'][j];raw=validate_evidence(base,ref)
        need(j in receipts and receipts[j]['evidence_digest']==ref['sha256'],'HOLD_CLAIM_RECEIPT_JOINT:'+j)
        need(receipts[j]['claim_id']==claim['id'] and receipts[j]['subject_revision']==claim['subject_revision'],'HOLD_CLAIM_RECEIPT_SUBJECT:'+j)
        need(json.loads(raw)=={k:v for k,v in receipts[j].items() if k!='evidence_digest'},'HOLD_CLAIM_RECEIPT_BYTES:'+j)
    a=receipts['acquisition'];ad=receipts['admission'];de=receipts['delivery']
    need(a['occurrence']==ad['occurrence']==de['occurrence'],'HOLD_CLAIM_OCCURRENCE')
    need(a['content_id']==receipts['input_revision']['content_id'],'HOLD_CLAIM_SOURCE_BYTES')
    need(de['range_bytes']==claim['range_bytes'] and de['delivered_sha256']==claim['evidence_slice_sha256'],'HOLD_CLAIM_PRESENTED_RANGE')
    need(receipts['inspection']['passed'] is True and receipts['issue_condition']['state']=='READY_FOR_HUMAN_REVIEW','HOLD_CLAIM_INSPECTION_OR_ISSUE')
    need(receipts['issue_condition']['human_acceptance']=='NOT_GRANTED','HOLD_CLAIM_AUTHORITY')
    return {'claim_id':claim['id'],'joints':claim['joints'],'source_locator':a['source_locator'],'source_revision':receipts['input_revision']['source_revision'],'acquisition_occurrence':a['occurrence'],'delivery_occurrence':de['delivery_id'],'authority_effect':'NONE','human_acceptance':'NOT_GRANTED'}

def human_projection(claims):
    rows=[]
    for c in claims:
        source=c['source_locator'];p=urllib.parse.urlsplit(source)
        link=source if p.scheme in {'https','http'} and not p.username and not p.password and not p.query else None
        rows.append({'claim_id':c['claim_id'],'source_revision':c['source_revision'],'internal_source_locator':source,'human_source_link':link,'scope':'TRACEABLE_PRIVATE_REVIEW_ONLY','human_acceptance':'NOT_GRANTED'})
    return {'projection_revision':'HUMAN_TRACE_R004','claims':rows}

def check_projection(claims,projection):
    need(len(projection['claims'])==len(claims),'HOLD_HUMAN_CLAIM_LOSS')
    expected=human_projection(claims)
    need(digest(expected)==digest(projection),'HOLD_HUMAN_SOURCE_LINK_LOSS')
    return True
