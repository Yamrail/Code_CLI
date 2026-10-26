"""Common execution evidence. Caller supplies actual retained process results."""
import json,platform,sys
from .binder import sha,digest,need,text,strict_int,time_chain,retained,no_authority
REVISION='COMMON_TEST_EXECUTION_RECEIPT_R003_PRIVATE'
REQUIRED=('artifact_id','tool_revision','source_revision','source_sha256','fixture_revision','fixture_sha256','command_or_runner_identity','environment_identity','started_at','finished_at','stdout_sha256','stderr_sha256','exit_code','test_count','pass_count','fail_count','result_sha256','authority_effect')
def command_identity(v):return text(v) or isinstance(v,list) and bool(v) and all(text(x) for x in v)
def environment_identity(v):return isinstance(v,dict) and all(text(v.get(k)) for k in ('python','executable','os','machine'))
def environment():return {'python':sys.version,'executable':sys.executable,'os':platform.platform(),'machine':platform.machine()}
def construct(*,artifact_id,tool_revision,source_revision,source_bytes,fixture_revision,fixture_bytes,command,started_at,finished_at,stdout,stderr,exit_code,results):
    need(all(text(v) for v in (artifact_id,tool_revision,source_revision,fixture_revision)),'HOLD_EXECUTION_IDENTITY_UNKNOWN')
    need(type(exit_code) is int and command_identity(command),'HOLD_EXECUTION_PROCESS_TYPE')
    need(isinstance(results,list) and all(isinstance(r,dict) and type(r.get('passed')) is bool for r in results),'HOLD_EXECUTION_RESULT_TYPE')
    time_chain({'start':started_at,'finish':finished_at},('start','finish'))
    count=len(results);passed=sum(r['passed'] for r in results)
    return {'schema':'yr.test-execution-receipt/1','receipt_revision':REVISION,'artifact_id':artifact_id,'tool_revision':tool_revision,'source_revision':source_revision,'source_sha256':sha(source_bytes),'fixture_revision':fixture_revision,'fixture_sha256':sha(fixture_bytes),'command_or_runner_identity':command,'environment_identity':environment(),'started_at':started_at,'finished_at':finished_at,'stdout_sha256':sha(stdout),'stderr_sha256':sha(stderr),'exit_code':exit_code,'test_count':count,'pass_count':passed,'fail_count':count-passed,'result_sha256':digest(results),'authority_effect':'NONE','canonical_effect':'NONE','human_gate':'NOT_EXECUTED','execution_origin':'ACTUAL_LOCAL_PROCESS_EXECUTION','results':results}
def validate(receipt,pin,base):
    need(isinstance(receipt,dict) and all(k in receipt for k in REQUIRED),'HOLD_EXECUTION_RECEIPT_DROPOUT')
    need(all(text(receipt.get(k)) for k in ('artifact_id','tool_revision','source_revision','fixture_revision')),'HOLD_EXECUTION_IDENTITY_UNKNOWN')
    need(isinstance(pin,dict) and receipt.get('schema')=='yr.test-execution-receipt/1' and text(receipt.get('receipt_revision')),'HOLD_EXECUTION_SCHEMA')
    need(type(receipt['exit_code']) is int and command_identity(receipt['command_or_runner_identity']) and environment_identity(receipt['environment_identity']),'HOLD_EXECUTION_PROCESS_TYPE')
    need(isinstance(receipt.get('results'),list) and all(isinstance(r,dict) and type(r.get('passed')) is bool for r in receipt['results']),'HOLD_EXECUTION_RESULT_TYPE')
    no_authority(receipt);need(receipt.get('execution_origin')=='ACTUAL_LOCAL_PROCESS_EXECUTION','HOLD_SELF_REPORTED_EXECUTION')
    for k in ('artifact_id','tool_revision','source_revision','source_sha256','fixture_revision','fixture_sha256','command_or_runner_identity'):
        need(receipt[k]==pin.get(k),'HOLD_EXECUTION_SUBJECT_'+k.upper())
    for k in ('source','fixture','stdout','stderr','result'):
        _,b=retained(base,pin[k+'_locator']);need(sha(b)==receipt[k+'_sha256'],'HOLD_EXECUTION_RETAINED_'+k.upper())
    need(digest(receipt['results'])==receipt['result_sha256'],'HOLD_EXECUTION_RESULT_HASH')
    for k in ('test_count','pass_count','fail_count'):need(strict_int(receipt[k]),'HOLD_EXECUTION_COUNTS')
    need(all(type(r.get('passed')) is bool for r in receipt['results']),'HOLD_EXECUTION_RESULT_TYPE')
    need(receipt['test_count']==len(receipt['results']) and receipt['pass_count']==sum(r['passed'] for r in receipt['results']) and receipt['test_count']==receipt['pass_count']+receipt['fail_count'],'HOLD_EXECUTION_COUNT_BINDING')
    time_chain(receipt,('started_at','finished_at'))
    need(receipt['exit_code']==0 and receipt['fail_count']==0 and receipt['test_count']>0,'HOLD_EXECUTION_NOT_PASS')
    return True
