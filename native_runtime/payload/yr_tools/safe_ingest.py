"""Side-effect-free Private Git write/readback joint validator."""
import hashlib
from .binder import need,text,digest,result,guarded,strict_int
REVISION='GITHUB_SAFE_INGEST_GATE_R001_PRIVATE'
def verify(d,pin):return guarded(_verify,d,pin)
def _verify(d,pin):
    need(pin.get('input_digest')==digest(d) and pin.get('pin_origin')=='FROZEN_RUNNER_CHECKPOINT','HOLD_INGEST_CHECKPOINT')
    need(d['repository']=='Yamrail/yamrail-evidence-ledger-private' and d['repository_private'] is True and d['repository_id']==1324194784 and d['observed_account']=='Yamrail','HOLD_ACCOUNT_TARGET_BINDING')
    need(text(d['branch']) and d['branch']!='migration/evidence-ledger-20260806' and d['force'] is False and d['operation']=='create','HOLD_WRITE_BOUNDARY')
    need(d['canonical_effect']=='NONE' and d['authority_effect']=='NONE' and d['human_gate']=='NOT_EXECUTED','HOLD_AUTHORITY')
    need(d['encoding']=='UTF-8' and d['caller_side_base64'] is False,'HOLD_ENCODING')
    need(d['pre_write_head']==d['head_recheck']==d['commit_parent'],'HOLD_HEAD_MOVED')
    need(d['phase'] in {'CANARY','PAYLOAD','RECEIPT'},'HOLD_PHASE_UNKNOWN')
    need(d['phase']=='CANARY' or d['canary']['write_readback_commit_pass'] is True and d['canary']['branch']==d['branch'] and d['canary']['after_test_receipt_sha256']==d['current_test_receipt_sha256'],'HOLD_CANARY_REQUIRED')
    need(d['resulting_head']==d['commit_sha'] and d['commit_created'] is True and d['branch_updated'] is True,'HOLD_COMMIT_NOT_BOUND')
    expected=d['expected_files'];readback=d['remote_readback_files'];allow=d['changed_file_allowlist']
    need(isinstance(expected,dict) and set(expected)==set(readback)==set(allow)==set(d['actual_changed_files']),'HOLD_UNEXPECTED_FILES')
    need(len(set(allow))==len(allow) and expected,'HOLD_FILE_ROSTER')
    need(set(expected).isdisjoint(d['parent_existing_paths']),'HOLD_EXISTING_OR_SAME_REVISION_OVERWRITE')
    need(d['parent_objects_unchanged'] is True and d['full_remote_readback'] is True,'HOLD_PARTIAL_READBACK')
    for path,meta in expected.items():
        need(path.startswith(d['new_candidate_prefix']) and '..' not in path.split('/'),'HOLD_TARGET_PATH_SCOPE')
        observed=readback[path];need(meta==observed and meta['bytes']>=0 and text(meta['sha256']) and text(meta['git_blob_sha']),'HOLD_REMOTE_BYTE_IDENTITY')
    need(d['manifest_sha256']==d['remote_manifest_sha256'],'HOLD_MANIFEST_HASH')
    if d['phase']=='CANARY':need(d['ascii_sentinel_match'] is True and d['japanese_sentinel_match'] is True,'HOLD_CANARY_SENTINEL')
    return result('PASS_REMOTE_READBACK_ONLY',tool_revision=REVISION,commit_sha=d['commit_sha'],branch=d['branch'],file_count=len(expected),canonical_promotion='NOT_PERFORMED')
