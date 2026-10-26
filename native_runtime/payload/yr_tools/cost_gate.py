"""Frozen billable tree and retained usage/rates; no model calls or prices built in."""
from .binder import need,digest,validate,strict_int,result,guarded,text
from .numeric import number,serial
REVISION='DETERMINISTIC_AGENT_COST_GATE_R003_PRIVATE'
def assess(d,pin,base):return guarded(_assess,d,pin,base)
def _assess(d,pin,base):
    need(pin.get('input_digest')==digest(d),'HOLD_COST_INPUT_PIN')
    need(d['execution_mode'] in {'NO_REDELEGATION','DECLARED_TOPOLOGY'} and d['sandbox_boundary_closed'] is True,'HOLD_COST_PREFLIGHT')
    for k in ('max_requests','max_retries','max_tool_calls','max_agent_depth'):need(strict_int(d[k]),'HOLD_COST_LIMIT_TYPE')
    need(d['model_auto_switch'] is False and d['leaf_may_redelegate'] is False,'REJECT_HIDDEN_REDELEGATION')
    need(d['declared_children']==d['observed_children'] and len(set(d['observed_children']))==len(d['observed_children']),'HOLD_EXECUTION_TREE')
    need(d['max_agent_depth']==0 and not d['observed_children'] if d['execution_mode']=='NO_REDELEGATION' else d['max_agent_depth']<=1,'HOLD_REDELEGATION_DEPTH')
    rate_ref=d['rate_snapshot_ref'];bound=validate(rate_ref,pin['rate'],base,pin['rate_subject']);rate=bound['record']['rates']
    need(d['requested_model_id']==d['resolved_model_id_expected'] and d['requested_model_id'] in d['allowed_models'],'HOLD_MODEL_IDENTITY')
    need(isinstance(rate,dict) and bool(rate) and all(number(v)>=0 for v in rate.values()),'HOLD_RATE_UNKNOWN')
    need(d['pricing_currency']==bound['record']['currency'],'HOLD_RATE_CURRENCY');ceiling=number(d['approved_cost_ceiling']);need(ceiling>=0,'HOLD_COST_CEILING_UNKNOWN')
    need(d['authority_scope']==pin['authority_scope'],'HOLD_COST_AUTHORITY_SCOPE')
    upper=d['worst_case_billable_bounds'];need(d['bound_scope']=='TOTAL_MISSION_INCLUDING_RETRIES' and set(upper)==set(rate) and all(strict_int(v) for v in upper.values()),'HOLD_COST_TREE_UNBOUNDED')
    worst=sum((upper[k]*number(rate[k]) for k in rate),number('0'));need(number(d['worst_case_cost'])==worst and worst<=ceiling,'HOLD_COST_WORST_CASE_BINDING')
    units_used={k:0 for k in rate}
    attempts=d['attempts'];need(isinstance(attempts,list) and len(attempts)<=d['max_requests'],'HOLD_ATTEMPT_LIMIT')
    ids=[a['attempt_id'] for a in attempts];need(len(set(ids))==len(ids),'HOLD_ATTEMPT_DUPLICATE');total=number('0')
    for attempt in attempts:
        need(attempt['provider_returned_model']==d['requested_model_id'] and attempt['service_tier']==d['service_tier'] and attempt['endpoint']==d['endpoint_family'],'HOLD_MODEL_TIER_ENDPOINT')
        need(strict_int(attempt['retry_index']) and attempt['retry_index']<=d['max_retries'] and attempt['spawn_depth']<=d['max_agent_depth'],'HOLD_RETRY_DEPTH')
        ref=attempt['usage_receipt_ref'];actual=validate(ref,pin['usage'][ref['artifact_id']],base,pin['usage_subjects'][ref['artifact_id']])['record']
        need(actual['usage']==attempt['usage'] and actual['attempt_id']==attempt['attempt_id'],'HOLD_USAGE_RECEIPT_BINDING')
        need(set(attempt['usage'])==set(rate),'HOLD_BILLABLE_LEAF_DROPOUT')
        for k,v in attempt['usage'].items():need(strict_int(v),'HOLD_USAGE_UNKNOWN');price=number(rate[k]);need(price>=0,'HOLD_RATE_UNKNOWN');total+=v*price;units_used[k]+=v
    need(all(units_used[k]<=upper[k] for k in rate),'HOLD_COST_LEAF_BOUND_EXCEEDED')
    need(total<=ceiling and number(d['worst_case_cost'])<=ceiling,'HOLD_COST_CEILING_EXCEEDED')
    need(d['worst_case_tree_complete'] is True and d['usage_observability_closed'] is True,'HOLD_COST_TREE_UNBOUNDED')
    need(number(d['locally_derived_cost'])==total,'HOLD_DERIVED_COST_MISMATCH')
    recon=d['provider_reconciliation'];need(recon['state'] in {'OBSERVED','PENDING','UNKNOWN'},'HOLD_RECON_STATE')
    if recon['state']!='OBSERVED':return result('COMPLETE_PENDING_RECON',tool_revision=REVISION,derived_cost=serial(total),currency=d['pricing_currency'],unknown_scope='PROVIDER_RECONCILIATION',external_model_call='NOT_EXECUTED')
    rr=recon['receipt_ref'];actual_recon=validate(rr,pin['reconciliation_pin'],base,pin['reconciliation_subject'])['record'];need(actual_recon['cost']==recon['cost'] and actual_recon['attempt_ids']==ids,'HOLD_PROVIDER_RECON_BINDING')
    need(number(recon['cost'])==total,'HOLD_PROVIDER_RECON_MISMATCH')
    return result('PASS_COST_PATH_ONLY',tool_revision=REVISION,derived_cost=serial(total),currency=d['pricing_currency'],all_attempts_metered=True,quality='NOT_CERTIFIED',authority='NOT_GRANTED')
